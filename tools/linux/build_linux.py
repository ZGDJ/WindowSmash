#!/usr/bin/env python3
"""Build the game for x86-64 Linux, on this Windows machine (the toolchain: tools/linux/toolchain.py).

Usage: build_linux.py [--port <dir>] [--out <dir>] [--jobs N] [--runtime-only] [--link-only] [--replace]

The recompiled game is the C the Windows build already generated (tools/recomp.py writes it into
<port>/build/{main,subsdk0,sdk,nro/*}); this compiles each file again for Linux, next to nothing
of the Windows objects, into <out>/<module>/. <port> is a game tree: the port's own (dump/ and
build/ at its top) or a game version's folder of the same layout, e.g. v13.0.5 - the default when
it is built (toolchain.default_port). Files with exception landing sites (guest C++ try/catch) are
compiled as C++ (see recomp.h). The runtime is runtime/*.c with the Linux platform layer
(runtime/linux), and the program links against DXVK (Direct3D 11 on Vulkan), SDL2, vkd3d-shader
(built by build_vkd3d.py), libopus and libvpx, the last three statically.
Incremental: a file is compiled again when its source is newer than its object. <out> holds one
tree's game (port.txt): build another tree's into another <out> (e.g. build-linux-11.0.0), or
give --replace to start this one over."""
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from required_hooks import reject_unvalidated_builder

from toolchain import (CFLAGS, CLANG, DXVK_INCLUDE, DXVK_LIBS, LLVM, REPO, RUNTIME, SYSROOT, TOOLCHAIN, VKD3D_BUILD, VKD3D_SRC,
                       compile_each, default_port, read_port_stamp, run, same_path, write_port_stamp)


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


PORT = os.path.abspath(arg("--port") or default_port())
OUT = os.path.abspath(arg("--out", os.path.join(REPO, "build-linux")))
JOBS = int(arg("--jobs", str(max(4, (os.cpu_count() or 8) - 2))))
GEN = os.path.join(OUT, "gen")

RUNTIME_INCLUDES = ["-I", os.path.join(RUNTIME, "linux", "include"), "-I", os.path.join(DXVK_INCLUDE, "windows"),
                    "-I", os.path.join(DXVK_INCLUDE, "directx"), "-I", os.path.join(SYSROOT, "usr", "include", "SDL2"),
                    "-I", os.path.join(VKD3D_SRC, "include"), "-I", GEN]
RUNTIME_DEFINES = ["-D_GNU_SOURCE", "-D_REENTRANT", "-DSSBU_HAVE_OPUS", "-DSSBU_HAVE_VPX"]


def modules():
    """(name, generated C directory, output directory) for every module the Windows build has."""
    build = os.path.join(PORT, "build")
    found = [(n, os.path.join(build, n), os.path.join(OUT, n)) for n in ("main", "subsdk0", "sdk")]
    nro = os.path.join(build, "nro")
    if os.path.isdir(nro):
        found += [(n, os.path.join(nro, n), os.path.join(OUT, "nro", n)) for n in sorted(os.listdir(nro))
                  if os.path.exists(os.path.join(nro, n, "manifest.tsv"))]
    return [m for m in found if os.path.exists(os.path.join(m[1], "manifest.tsv"))]


def use_tree():
    """<out>'s game objects must all be from one tree: of another tree's, one newer than this
    tree's source would be kept, and one this tree has no source for linked. So another tree's
    are only started over with --replace."""
    built = read_port_stamp(OUT)
    game = [os.path.join(OUT, n) for n in ("main", "subsdk0", "sdk", "nro")]
    if (built is None or not same_path(built, PORT)) and any(os.path.isdir(d) for d in game):
        if "--replace" not in sys.argv or "--link-only" in sys.argv:
            raise SystemExit(f"{OUT} holds the game compiled from {built or 'another tree'}: build {PORT}'s into another "
                             f"--out, or give --replace (without --link-only) to start this one over")
        print(f"{OUT} holds the game compiled from {built or 'another tree'}: compiling {PORT}'s from the start")
        for path in game:
            shutil.rmtree(path, ignore_errors=True)
        for name in ("ssbu", "ssbu.syms", "ssbu.map", "ssbu.rsp"):
            if os.path.exists(os.path.join(OUT, name)):
                os.remove(os.path.join(OUT, name))
    write_port_stamp(OUT, PORT)


def needs(obj, *srcs):
    return not os.path.exists(obj) or os.path.getmtime(obj) < max(os.path.getmtime(s) for s in srcs)


def has_landing_sites(path):
    with open(path, "rb") as f:
        return b"__try" in f.read()


def game_jobs():
    recomp_h = os.path.join(RUNTIME, "recomp.h")
    jobs = []
    for name, src_dir, out_dir in modules():
        with open(os.path.join(src_dir, "manifest.tsv")) as f:
            rows = [line.split("\t") for line in f.read().splitlines() if line]
        for fname, _insns, biggest in rows + [["g_module.c", "0", "0"]]:
            src = os.path.join(src_dir, fname)
            obj = os.path.join(out_dir, fname[:-2] + ".o")
            # very large functions make the optimiser superlinear; build those at a lower level (as on Windows)
            opt = "-O1" if int(biggest) > 20000 or fname == "g_module.c" else "-O2"
            if not needs(obj, src, recomp_h):
                continue
            if fname != "g_module.c" and has_landing_sites(src):
                # As C++, a huge function full of landing sites (lua2cpp item/fighter tables: up to
                # 210k instructions, 41k sites) takes the optimiser hours even at -O1 - and seconds
                # at -O0. Those are one-off set-up code; 38k-instruction ones still take 20 s at -O1.
                if int(biggest) > 50000:
                    opt = "-O0"
                wrapper = os.path.join(out_dir, fname[:-2] + "_cxx.cpp")
                os.makedirs(out_dir, exist_ok=True)
                text = '#include "recomp.h"\nextern "C" {\n#include "%s"\n}\n' % src.replace("\\", "/")
                if not os.path.exists(wrapper) or open(wrapper).read() != text:
                    with open(wrapper, "w") as f:
                        f.write(text)
                jobs.append((wrapper, obj, opt))
            else:
                jobs.append((src, obj, opt))
    return jobs


def hle_names():
    names = set()
    for n in os.listdir(RUNTIME):
        if n.endswith(".c"):
            with open(os.path.join(RUNTIME, n), encoding="utf-8") as f:
                names |= set(re.findall(r"^HLE\((\w+)\)", f.read(), re.M))
    return sorted(names)


def hle_wraps():
    """The guest functions the runtime wraps (HLE_WRAP(<address>), as tools/recomp.py finds them)."""
    found = set()
    for n in os.listdir(RUNTIME):
        if n.endswith(".c"):
            with open(os.path.join(RUNTIME, n), encoding="utf-8") as f:
                found |= {int(a, 16) for a in re.findall(r"^HLE_WRAP\(([0-9a-fA-F]+)\)", f.read(), re.M)}
    return sorted(found)


def write_if_changed(path, text):
    if os.path.exists(path) and open(path, encoding="utf-8").read() == text:
        return False
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return True


def overlay_font():
    """gen/overlay_font.h: the debug overlay's glyphs, drawn by GDI here as the Windows build does."""
    os.makedirs(GEN, exist_ok=True)
    header = os.path.join(GEN, "overlay_font.h")
    tool_src = os.path.join(REPO, "tools", "linux", "make_overlay_font.c")
    if not needs(header, tool_src):
        return True
    exe = os.path.join(GEN, "make_overlay_font.exe")
    code, out = run([os.path.join(LLVM, "clang-cl.exe"), "/nologo", "/O1", "-w", "-fuse-ld=lld", tool_src, "/Fe" + exe, "/link", "gdi32.lib", "user32.lib"])
    if code or subprocess.run([exe, header]).returncode:
        print("could not make the overlay font:\n" + out)
        return False
    return True


def runtime_jobs():
    reject_unvalidated_builder(RUNTIME, "the Linux builder")
    os.makedirs(GEN, exist_ok=True)
    rt_out = os.path.join(OUT, "rt")
    headers = [os.path.join(RUNTIME, n) for n in os.listdir(RUNTIME) if n.endswith(".h")] + \
              [os.path.join(RUNTIME, "linux", "include", "windows.h")]
    sources = [os.path.join(RUNTIME, n) for n in sorted(os.listdir(RUNTIME))
               if re.fullmatch(r"(host|kernel|gpu\w*|hle\w*|ipc\w*|net\w*)\.c", n)]
    sources += [os.path.join(RUNTIME, "linux", n) for n in sorted(os.listdir(os.path.join(RUNTIME, "linux")))
                if n.endswith((".c", ".cpp"))]
    jobs = []
    for src in sources:
        obj = os.path.join(rt_out, os.path.basename(src).rsplit(".", 1)[0] + ".o")
        if needs(obj, src, *headers):
            jobs.append((src, obj, "-O2", RUNTIME_INCLUDES + RUNTIME_DEFINES))
    names = hle_names()
    table = os.path.join(GEN, "hle_table.c")
    changed = write_if_changed(table, '#include "host.h"\n\n' + "".join(f"GuestFn hle_{n};\n" for n in names)
                               + "const HleEntry hle_table[] = {\n" + "".join(f'    {{"{n}", hle_{n}}},\n' for n in names)
                               + f"    {{0, 0}}\n}};\nconst u32 hle_count = {len(names)};\n")
    if changed or needs(os.path.join(rt_out, "hle_table.o"), table, *headers):
        jobs.append((table, os.path.join(rt_out, "hle_table.o"), "-O1", RUNTIME_INCLUDES + RUNTIME_DEFINES))
    # A wrapped function this game version has no module for: the original its wrapper names
    # (f_<address>_orig, which nothing reaches) is rt_wrap_missing. The Windows link says so
    # with /alternatename (tools/recomp.py); here it is a weak stub a module's own replaces.
    missing = os.path.join(GEN, "wrap_missing.c")
    changed = write_if_changed(missing, '#include "host.h"\n\nvoid rt_wrap_missing(Cpu *c);\n'
                               + "".join(f"__attribute__((weak)) void f_{a:x}_orig(Cpu *c) {{ rt_wrap_missing(c); }}\n"
                                         for a in hle_wraps()))
    if changed or needs(os.path.join(rt_out, "wrap_missing.o"), missing, *headers):
        jobs.append((missing, os.path.join(rt_out, "wrap_missing.o"), "-O1", RUNTIME_INCLUDES + RUNTIME_DEFINES))
    nros =[n for n, src, _o in modules() if os.path.basename(os.path.dirname(src)) == "nro"]
    nro_table = os.path.join(GEN, "nro_table.c")
    changed = write_if_changed(nro_table, '#include "module.h"\n\n' + "".join(f"extern const RtModule rt_module_{n};\n" for n in nros)
                               + "const RtModule *const rt_nro_modules[] = {" + "".join(f"&rt_module_{n}, " for n in nros) + "0};\n"
                               + f"const u32 rt_nro_count = {len(nros)};\n")
    if changed or needs(os.path.join(rt_out, "nro_table.o"), nro_table):
        jobs.append((nro_table, os.path.join(rt_out, "nro_table.o"), "-O1", ["-I", RUNTIME]))
    return jobs


def compile_all(jobs, what):
    if not jobs:
        print(f"{what}: up to date")
        return True
    t0 = time.time()
    failures = []
    # biggest first: a few files take minutes, and started last they would hold up the end
    def source_size(job):   # (a C++ wrapper's size is that of the generated file it includes)
        src = job[0]
        if src.endswith("_cxx.cpp"):
            src = re.findall(r'#include "([^"]+)"', open(src).read())[-1]
        return os.path.getsize(src)
    jobs = sorted(jobs, key=source_size, reverse=True)
    from concurrent.futures import as_completed
    with ThreadPoolExecutor(JOBS) as pool:
        futures = [pool.submit(compile_each, [job], 1) for job in jobs]
        for done, fut in enumerate(as_completed(futures), 1):
            failures += fut.result()
            if done % 64 == 0 or done == len(jobs):
                print(f"{what}: {done}/{len(jobs)} compiled, {time.time() - t0:,.0f}s", flush=True)
    for src, err in failures[:8]:
        print(f"FAILED {src}:\n{err[:3000]}")
    return not failures


def link():
    reject_unvalidated_builder(RUNTIME, "the Linux builder")
    objs = []
    rt_out = os.path.join(OUT, "rt")
    objs += sorted(os.path.join(rt_out, n) for n in os.listdir(rt_out) if n.endswith(".o"))
    for _name, _src, out_dir in modules():
        objs += sorted(os.path.join(out_dir, n) for n in os.listdir(out_dir) if n.endswith(".o"))
    exe = os.path.join(OUT, "ssbu")
    rsp = exe + ".rsp"
    with open(rsp, "w") as f:
        f.write("\n".join('"%s"' % o.replace("\\", "/") for o in objs))
    lib = os.path.join(SYSROOT, "usr", "lib", "x86_64-linux-gnu")
    t0 = time.time()
    code, out = run([CLANG, "--target=x86_64-linux-gnu", "--sysroot=" + SYSROOT, "-fuse-ld=lld", "-no-pie", "@" + rsp, "-o", exe,
                     os.path.join(VKD3D_BUILD, "linux", "libvkd3d-shader.a"), os.path.join(lib, "libopus.a"), os.path.join(lib, "libvpx.a"),
                     "-L" + DXVK_LIBS, "-l:libdxvk_d3d11.so.0", "-l:libdxvk_dxgi.so.0", "-l:libSDL2-2.0.so.0",
                     "-lstdc++", "-lm", "-lpthread", "-ldl", "-lrt",
                     "-Wl,-rpath,$ORIGIN/lib", "-Wl,--allow-shlib-undefined", "-Wl,-z,noexecstack", "-Wl,--build-id",
                     "-Wl,-Map=" + exe + ".map"])
    if code:
        errors = [l for l in out.splitlines() if "error" in l.lower()] or out.splitlines()
        print("link failed\n" + "\n".join(errors)[:6000])
        return False
    syms = subprocess.run([os.path.join(LLVM, "llvm-nm.exe"), "-n", "--defined-only", exe], capture_output=True, text=True)
    with open(os.path.join(OUT, "ssbu.syms"), "w", newline="\n") as f:
        f.write(syms.stdout)
    print(f"linked {len(objs)} objects into {exe} ({os.path.getsize(exe) / 1048576:,.0f} MB) in {time.time() - t0:,.0f}s")
    return True


def dxvk_libs():
    """The DXVK libraries under their sonames (the release's symbolic links do not survive on Windows)."""
    for so in ("libdxvk_d3d11.so", "libdxvk_dxgi.so"):
        target = os.path.join(DXVK_LIBS, so + ".0")
        if not os.path.exists(target):
            real = [n for n in os.listdir(DXVK_LIBS) if n.startswith(so + ".0.")]
            if not real:
                raise SystemExit(f"{so}: not in {DXVK_LIBS}")
            with open(os.path.join(DXVK_LIBS, real[0]), "rb") as a, open(target, "wb") as b:
                b.write(a.read())


def main():
    reject_unvalidated_builder(RUNTIME, "the Linux builder")
    os.makedirs(OUT, exist_ok=True)
    if not os.path.exists(os.path.join(VKD3D_BUILD, "linux", "libvkd3d-shader.a")):
        raise SystemExit("vkd3d-shader is not built: run tools/linux/build_vkd3d.py linux")
    dxvk_libs()
    if not modules():
        raise SystemExit(f"no recompiled game in {os.path.join(PORT, 'build')} (tools/recomp.py all)")
    print(f"game tree: {PORT}")
    if "--runtime-only" not in sys.argv:
        use_tree()
    if "--link-only" not in sys.argv:
        if not overlay_font() or not compile_all(runtime_jobs(), "runtime"):
            return False
        if "--runtime-only" in sys.argv:
            return True
        if not compile_all(game_jobs(), "game"):
            return False
    return link()


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
