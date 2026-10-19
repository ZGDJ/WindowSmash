#!/usr/bin/env python3
"""Capture/verify a sanitized baseline inventory. Stdlib only; never launches the game.

The manifest records observed files, not proof that an executable was built from them.
Missing prerequisites produce a useful report and exit 2, never a qualified baseline.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

import cc
from bundle_ssbu import FONTS

ROOT = Path(__file__).resolve().parents[1]
TARGET = {"game": "Super Smash Bros. Ultimate", "version": "13.0.5", "platform": "windows-x64"}
CHUNK = 8 * 1024 * 1024


def digest_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def file_identity(path, inspect=None):
    """Hash in bounded memory and reject a file changed while it was being read."""
    with Path(path).open("rb") as stream:
        before = os.fstat(stream.fileno())
        digest = hashlib.sha256()
        while block := stream.read(CHUNK):
            digest.update(block)
        stream.seek(0)
        extra = inspect(stream) if inspect else {}
        after = os.fstat(stream.fileno())
    current = Path(path).stat()
    # Windows Python 3.12 can give different ctime values for stat and fstat.
    identity = lambda stat: (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
    if (identity(before) != identity(after) or identity(after) != identity(current)
            or before.st_ctime_ns != after.st_ctime_ns):
        raise ValueError("an input changed during capture; stop writers and capture again")
    return {"size": before.st_size, "sha256": digest.hexdigest(), **extra}


def module_identity(path):
    def inspect(stream):
        header = stream.read(0x100)
        if len(header) < 0x100 or (header[:4] != b"NSO0" and header[0x10:0x14] != b"NRO0"):
            raise ValueError("invalid module header")
        # Do not use Module.build_id's historical trailing-nibble abbreviation for new pins.
        return {"build_id": header[0x40:0x60].hex().upper()}
    return file_identity(path, inspect)


def source_identity(root):
    """Hash tracked build sources plus untracked source additions; never enumerate private trees."""
    def git(*args):
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True)
        return result.stdout

    revision = git("rev-parse", "HEAD").decode().strip()
    names = git("ls-files", "--cached", "--others", "--exclude-standard", "-z", "--",
                "runtime", "tools", "third_party", "requirements.txt", "requirements-dev.txt")
    files = {}
    for name in sorted(set(names.decode().split("\0")) - {""}):
        path = root / name
        # A tracked deletion is part of the identity, not a silently ignored source change.
        files[name] = file_identity(path) if path.is_file() else None
    if not files:
        raise ValueError("no build sources found in the source repository")
    return {"revision": revision, "files": files}


def toolchain_identity():
    compiler = shutil.which(cc.CLANG)
    if compiler is None:
        return None
    # Match cc.link's explicit lld selection, including a PATH-only clang-cl.
    linker = Path(cc.CLANG).parent / "lld-link.exe"
    if not linker.is_file():
        linker = shutil.which("link.exe")
    if not linker:
        return None
    return {
        "compiler": file_identity(compiler),
        "linker": file_identity(linker),
        "compile_identity": cc.compile_identity(),
        "library_environment": digest_json({key: os.environ.get(key, "") for key in ("LIB", "LIBPATH")}),
        "python": list(sys.version_info[:3]),
        "optional_libraries": [file_identity(p) for p in cc.OPUS_LIBS + cc.VPX_LIBS],
    }


def romfs_identity(tree):
    """Resolve configuration as the runtime does when started from the selected tree.

    Path strings are deliberately excluded; source order, offset/map and file bytes remain.
    Layered images are fingerprinted by their backing files, not expanded into a huge image.
    """
    lines = (tree / "dump/modules/romfs.cfg").read_text(encoding="utf-8-sig").splitlines()

    def resolve(text):
        path = Path(text)
        return path if path.is_absolute() else tree / path

    if not lines or any(not line for line in lines):
        raise ValueError("empty RomFS configuration")
    if lines[0] != "layered":
        if len(lines) != 2 or not lines[1].isdigit():
            raise ValueError("plain RomFS configuration needs a source and nonnegative offset")
        source, offset = resolve(lines[0]), int(lines[1])
        def inspect(stream):
            if offset + 80 > os.fstat(stream.fileno()).st_size:
                raise ValueError("RomFS offset is outside its source")
            stream.seek(offset)
            if struct.unpack("<Q", stream.read(8))[0] != 80:
                raise ValueError("RomFS header is missing at the configured offset")
            return {}
        info = file_identity(source, inspect)
        return {"kind": "plain", "offset": offset, "source": info}
    if not 3 <= len(lines) <= 10:
        raise ValueError("layered RomFS configuration needs a map and one to eight sources")
    map_path = resolve(lines[1])
    sources = [file_identity(resolve(line)) for line in lines[2:]]
    def inspect(stream):
        header = stream.read(24)
        if len(header) != 24 or header[:8] != b"SSBUROM1":
            raise ValueError("invalid RomFS layer map header")
        size, count, reserved = struct.unpack("<QII", header[8:])
        if not size or not count or reserved or os.fstat(stream.fileno()).st_size != 24 + count * 24:
            raise ValueError("invalid RomFS layer map size")
        previous = None
        for _ in range(count):
            at, offset, source, reserved = struct.unpack("<QQII", stream.read(24))
            if reserved or at >= size or (previous is None and at != 0):
                raise ValueError("invalid RomFS layer entry")
            if previous is not None:
                check_layer(previous, at, sources)
            previous = (at, offset, source)
        check_layer(previous, size, sources)
        return {"image_size": size}
    map_info = file_identity(map_path, inspect)
    return {"kind": "layered", "size": map_info.pop("image_size"), "map": map_info, "sources": sources}


def check_layer(entry, end, sources):
    at, offset, source = entry
    if at >= end:
        raise ValueError("RomFS layers must be strictly ordered")
    if source != 0xFFFFFFFF and (source >= len(sources) or offset + end - at > sources[source]["size"]):
        raise ValueError("RomFS layer exceeds its source")


def capture(tree, *, root=ROOT, fixture=None, tape=None):
    tree, root = Path(tree).resolve(), Path(root).resolve()
    missing = []

    def observe(label, reader):
        try:
            return reader()
        except (OSError, ValueError, UnicodeError, struct.error, subprocess.SubprocessError):
            # Do not leak external filenames, usernames, config contents or compiler errors.
            missing.append(label)
            return None

    version_file = tree / "version.txt"
    version = observe("version.txt", lambda: version_file.read_text(encoding="utf-8-sig").splitlines()[0]
                      if version_file.stat().st_size else "")
    if version != TARGET["version"]:
        missing.append("declared version must be 13.0.5")
    modules = {}
    for name in ("main", "sdk", "subsdk0"):
        modules["exefs/" + name] = observe("module " + name, lambda name=name: module_identity(tree / "dump/exefs" / name))
    nros = sorted((tree / "dump/nro").glob("*.nro"))
    if not nros:
        missing.append("fighter modules (dump/nro/*.nro)")
    for path in nros:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", path.name):
            raise ValueError("unexpected fighter module filename")
        modules["nro/" + path.name] = observe("fighter module " + path.name, lambda path=path: module_identity(path))
    files = {}
    for name in ["dump/nro/bases.txt", *("dump/fonts/" + font for font in FONTS), "build/ssbu.exe",
                 *("dump/modules/" + name + ".reloc.bin" for name in ("main", "sdk", "subsdk0"))]:
        files[name] = observe(name, lambda name=name: file_identity(tree / name))
    # Optional is explicit: adding DLC, relocated images or runtime DLLs changes the identity.
    optional = [tree / "dump/modules/aoc.cfg", *sorted((tree / "dump/modules").glob("*.reloc.bin")),
                *sorted((tree / "build").glob("*.dll")), *sorted((tree / "build").rglob("compile.txt"))]
    for path in optional:
        name = path.relative_to(tree).as_posix()
        files[name] = observe(name, lambda path=path: file_identity(path)) if path.exists() else None
    toolchain = observe("Windows compiler/toolchain", toolchain_identity)
    if toolchain is None and "Windows compiler/toolchain" not in missing:
        missing.append("Windows compiler/toolchain")
    data = {
        "schema_version": 1, "target": TARGET,
        "source": observe("source repository", lambda: source_identity(root)),
        "toolchain": toolchain,
        "declared_version": version if version == TARGET["version"] else None,
        "modules": modules, "files": files,
        "romfs": observe("RomFS configuration/content", lambda: romfs_identity(tree)),
        "fixture": observe("fixture", lambda: file_identity(fixture)) if fixture else None,
        "tape": observe("input tape", lambda: file_identity(tape)) if tape else None,
        "missing": sorted(set(missing)),
    }
    return {**data, "fingerprint": digest_json(data)}


def validate_manifest(data):
    if not isinstance(data, dict) or data.get("schema_version") != 1 or data.get("target") != TARGET:
        raise ValueError("unsupported manifest schema or target")
    expected = {"schema_version", "target", "source", "toolchain", "declared_version", "modules", "files",
                "romfs", "fixture", "tape", "missing", "fingerprint"}
    if set(data) != expected or not isinstance(data["missing"], list):
        raise ValueError("invalid manifest fields")
    if data["fingerprint"] != digest_json({k: v for k, v in data.items() if k != "fingerprint"}):
        raise ValueError("manifest fingerprint mismatch")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("capture", "verify"))
    parser.add_argument("--tree", type=Path, default=ROOT)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--tape", type=Path)
    args = parser.parse_args(argv)
    try:
        baseline = None
        if args.command == "verify":
            baseline = json.loads(args.manifest.read_text(encoding="utf-8"))
            validate_manifest(baseline)
        actual = capture(args.tree, fixture=args.fixture, tape=args.tape)
        if args.command == "capture":
            # Exclusive creation protects both existing evidence and accidental input destinations.
            with args.manifest.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(actual, stream, indent=2, sort_keys=True)
                stream.write("\n")
        if actual["missing"]:
            print("INCOMPLETE: " + "; ".join(actual["missing"]))
            return 2
        if baseline is not None:
            changed = [key for key in actual if key != "fingerprint" and actual[key] != baseline[key]]
            if changed:
                print("MISMATCH: " + ", ".join(changed))
                return 1
        print("MATCH" if baseline else "CAPTURED", actual["fingerprint"])
        return 0
    except (OSError, ValueError, UnicodeError, IndexError):
        print("ERROR: invalid/unreadable manifest or input, or capture destination already exists", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
