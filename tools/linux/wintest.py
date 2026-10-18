#!/usr/bin/env python3
"""Try the Linux build's graphics path on Windows: the Windows program, built from this tree's
runtime with the game objects the Windows build already has, drawing through DXVK (its d3d11.dll
and dxgi.dll beside the program) and - with --vkd3d - compiling HLSL with vkd3d-shader instead
of fxc. Renderer problems that DXVK or vkd3d-shader would cause on Linux show up here, on this
machine's GPU, without a Linux machine.

Usage: wintest.py [--port <game tree>] [--out <dir>] [--vkd3d] [--native-d3d]

Writes <out>/ssbu_test.exe (default <out>: linux-toolchain/test/wintest). Nothing is written into
the port's own build. --native-d3d leaves DXVK out (Windows' own Direct3D, for comparing)."""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "tools"))
import cc  # noqa: E402  (the Windows toolchain, from this tree)
from required_hooks import reject_unvalidated_builder
from toolchain import PORT_DIR, TOOLCHAIN, VKD3D_BUILD, VKD3D_SRC  # noqa: E402


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


PORT = os.path.abspath(arg("--port", PORT_DIR))
OUT = os.path.abspath(arg("--out", os.path.join(TOOLCHAIN, "test", "wintest")))
VKD3D = "--vkd3d" in sys.argv


def main():
    reject_unvalidated_builder(cc.RUNTIME, "the Windows renderer test builder")
    rt = os.path.join(OUT, "rt")
    os.makedirs(rt, exist_ok=True)
    import re
    sources = [n for n in sorted(os.listdir(cc.RUNTIME)) if re.fullmatch(r"(host|kernel|gpu\w*|hle\w*|ipc\w*|debug\w*|net\w*)\.c", n)]
    jobs = []
    for n in sources:
        flags = ["/DD3DCompile=rt_vkd3d_D3DCompile"] if VKD3D and n in ("gpu_d3d11.c", "gpu_overlay.c") else []
        if VKD3D and n == "gpu_shader.c":
            flags = ["/DSSBU_HLSL_FOR_VKD3D"]   # (the HLSL the Linux build writes for vkd3d-shader)
        jobs.append((os.path.join(cc.RUNTIME, n), os.path.join(rt, n[:-2] + ".obj"), flags))
    if VKD3D:   # (only then linked with vkd3d-shader.lib)
        jobs.append((os.path.join(cc.RUNTIME, "linux", "d3dcompile_vkd3d.c"), os.path.join(rt, "d3dcompile_vkd3d.obj"),
                     ["/DLIBVKD3D_SHADER_SOURCE", "/I", os.path.join(VKD3D_SRC, "include")]))
    # (the Windows build's own tables: the same modules)
    jobs += [(os.path.join(PORT, "build", "rt", n), os.path.join(rt, n[:-2] + ".obj"), []) for n in ("hle_table.c", "nro_table.c")]
    import subprocess
    from concurrent.futures import ThreadPoolExecutor

    def one(job):
        src, obj, flags = job
        r = subprocess.run([cc.CLANG, "/c", "/O2", *cc.CFLAGS, *flags, src, "/Fo" + obj], capture_output=True, text=True)
        return (src, r.stdout + r.stderr) if r.returncode else None
    with ThreadPoolExecutor(8) as pool:
        failures = [f for f in pool.map(one, jobs) if f]
    for src, err in failures:
        print(f"FAILED {src}:\n{err[:3000]}")
    if failures:
        return False
    objs = [j[1] for j in jobs]
    build = os.path.join(PORT, "build")
    dirs = [os.path.join(build, n) for n in ("main", "subsdk0", "sdk")]
    dirs += [os.path.join(build, "nro", n) for n in sorted(os.listdir(os.path.join(build, "nro")))]
    for d in dirs:
        objs += sorted(os.path.join(d, n) for n in os.listdir(d) if n.endswith(".obj"))
    exe = os.path.join(OUT, "ssbu_test.exe")
    if VKD3D:
        cc.EXTRA_LIBS.append(os.path.join(VKD3D_BUILD, "windows", "vkd3d-shader.lib"))
    cc.link(objs, exe)
    for dll in ("d3d11.dll", "dxgi.dll"):
        target = os.path.join(OUT, dll)
        if "--native-d3d" in sys.argv:
            if os.path.exists(target):
                os.remove(target)
        else:
            shutil.copy2(os.path.join(TOOLCHAIN, "dxvk-win", "dxvk-3.1.1", "x64", dll), target)
    print(f"{exe} ({os.path.getsize(exe) / 1048576:,.0f} MB): {'DXVK' if '--native-d3d' not in sys.argv else 'Windows Direct3D'}, "
          f"{'vkd3d-shader' if VKD3D else 'fxc'} compiling HLSL")
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
