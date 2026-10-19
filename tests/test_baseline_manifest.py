"""Disposable inventory fixtures; no real compiler, game, keys or executable required."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
try:
    import baseline_manifest as manifest
finally:
    sys.path.pop(0)


class BaselineManifestTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="baseline-test-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.tree = self.root / "private user" / "game"
        self.tree.mkdir(parents=True)
        self.output = self.root / "baseline.json"
        self.write("version.txt", b"13.0.5\n# private metadata never copied\n")
        header = bytearray(0x100)
        header[:4] = b"NSO0"
        header[0x40:0x60] = bytes.fromhex("12" * 31 + "A0")
        for name in ("main", "sdk", "subsdk0"):
            self.write("dump/exefs/" + name, header)
            self.write("dump/modules/" + name + ".reloc.bin", b"synthetic relocated image")
        header[:4] = bytes(4)
        header[0x10:0x14] = b"NRO0"
        self.write("dump/nro/mario.nro", header)
        self.write("dump/nro/bases.txt", b"mario 7200000000 7200001000 FAKE\n")
        for font in manifest.FONTS:
            self.write("dump/fonts/" + font, b"font fixture")
        self.write("build/ssbu.exe", b"synthetic executable, never executed")
        self.write("assets/content.bin", struct.pack("<10Q", 80, 80, 0, 80, 0, 80, 0, 80, 0, 80) + b"data")
        self.write("dump/modules/romfs.cfg", b"assets/content.bin\n0\n")
        # Sentinels must never appear in a serialized report or be selected for hashing.
        self.write("prod.keys", b"PRIVATE KEY SENTINEL")
        self.write("save/player-name.txt", b"PRIVATE SAVE SENTINEL")
        for target, value in (("source_identity", {"revision": "f" * 40, "files": {"runtime/host.c": "hash"}}),
                              ("toolchain_identity", {"compiler": "synthetic", "compile_identity": "test"})):
            mock = patch.object(manifest, target, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)

    def write(self, name, data):
        path = self.tree / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def capture(self):
        return manifest.capture(self.tree)

    def cli(self, command, *extra):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return manifest.main([command, "--tree", str(self.tree), "--manifest", str(self.output), *extra])

    def test_capture_verify_and_full_module_id(self):
        self.assertEqual(self.cli("capture"), 0)
        self.assertEqual(self.cli("verify"), 0)
        data = json.loads(self.output.read_text())
        self.assertEqual(data["modules"]["exefs/main"]["build_id"], "12" * 31 + "A0")
        self.assertEqual(data["missing"], [])
        manifest.validate_manifest(data)

    def test_output_has_no_external_paths_keys_saves_or_source_config_text(self):
        cfg = self.tree / "dump/modules/romfs.cfg"
        cfg.write_text(str(self.tree / "assets/content.bin") + "\n0\n")
        text = json.dumps(self.capture())
        for private in (str(self.root), "private user", "PRIVATE", "prod.keys", "player-name", "metadata never copied"):
            self.assertNotIn(private, text)

    def test_content_change_with_preserved_timestamp_is_detected(self):
        self.assertEqual(self.cli("capture"), 0)
        path = self.tree / "assets/content.bin"
        old = path.stat()
        path.write_bytes(path.read_bytes()[:-4] + b"EDIT")
        os.utime(path, ns=(old.st_atime_ns, old.st_mtime_ns))
        self.assertEqual(self.cli("verify"), 1)

    def test_optional_artifacts_and_fighter_inventory_cannot_drift_silently(self):
        for name in ("dump/modules/aoc.cfg", "build/codec.dll", "dump/modules/other.reloc.bin", "dump/nro/other.nro"):
            with self.subTest(name=name):
                before = self.capture()
                data = (self.tree / "dump/nro/mario.nro").read_bytes() if name.endswith(".nro") else b"changed"
                path = self.write(name, data)
                self.assertNotEqual(before["fingerprint"], self.capture()["fingerprint"])
                path.unlink()

    def test_missing_or_bad_inputs_are_incomplete_not_successful(self):
        for name in ("build/ssbu.exe", "dump/exefs/main", "dump/modules/romfs.cfg", "dump/modules/main.reloc.bin"):
            with self.subTest(name=name):
                path = self.tree / name
                before = path.read_bytes()
                path.unlink()
                self.assertEqual(self.cli("capture"), 2)
                self.assertTrue(json.loads(self.output.read_text())["missing"])
                self.assertEqual(self.cli("verify"), 2)
                self.output.unlink()
                path.write_bytes(before)
        self.write("version.txt", b"11.0.0\n")
        self.assertEqual(self.cli("capture"), 2)

    def test_wrong_module_format_and_missing_compiler_are_reported(self):
        self.write("dump/exefs/main", b"not a module")
        with patch.object(manifest, "toolchain_identity", return_value=None):
            missing = self.capture()["missing"]
        self.assertIn("module main", missing)
        self.assertIn("Windows compiler/toolchain", missing)

    def test_relocation_of_content_paths_preserves_identity(self):
        before = self.capture()
        source = self.tree / "assets/content.bin"
        self.write("dump/modules/romfs.cfg", (str(source) + "\n0\n").encode())
        moved = self.root / "another private folder"
        shutil.copytree(self.tree, moved)
        (moved / "dump/modules/romfs.cfg").write_text(str(moved / "assets/content.bin") + "\n0\n")
        self.assertEqual(before, manifest.capture(moved))

    def test_layered_sources_map_and_bounds(self):
        entries = [(0, 0, 0, 0), (8, 0, 0xFFFFFFFF, 0)]
        layer = b"SSBUROM1" + struct.pack("<QII", 16, 2, 0) + b"".join(struct.pack("<QQII", *e) for e in entries)
        self.write("dump/modules/romfs.layers", layer)
        self.write("dump/modules/romfs.cfg", b"layered\ndump/modules/romfs.layers\nassets/content.bin\n")
        before = self.capture()
        self.assertEqual(before["missing"], [])
        self.assertEqual(before["romfs"]["size"], 16)
        self.write("dump/modules/romfs.layers", layer[:-24] + struct.pack("<QQII", 8, 0, 9, 0))
        self.assertIn("RomFS configuration/content", self.capture()["missing"])

    def test_bad_offset_layer_map_and_version_do_not_leak_paths(self):
        for data in (b"assets/content.bin\n-1\n", b"assets/content.bin\n9999\n", b"layered\nmissing-map\nmissing-content\n"):
            self.write("dump/modules/romfs.cfg", data)
            result = self.capture()
            self.assertIn("RomFS configuration/content", result["missing"])
            self.assertNotIn("missing-content", json.dumps(result))

    def test_layered_source_limit_matches_runtime(self):
        self.write("dump/modules/romfs.layers", b"SSBUROM1" + struct.pack("<QIIQQII", 8, 1, 0, 0, 0, 8, 0))
        self.write("dump/modules/romfs.cfg", ("layered\ndump/modules/romfs.layers\n" + "assets/content.bin\n" * 9).encode())
        self.assertIn("RomFS configuration/content", self.capture()["missing"])

    def test_module_hash_and_header_are_one_observation(self):
        path = self.tree / "dump/exefs/main"
        before = manifest.module_identity(path)
        real = manifest.file_identity

        def replace_after_observation(path, *args):
            result = real(path, *args)
            changed = bytearray(Path(path).read_bytes())
            changed[0x40:0x60] = bytes(32)
            Path(path).write_bytes(changed)
            return result

        with patch.object(manifest, "file_identity", side_effect=replace_after_observation):
            self.assertEqual(manifest.module_identity(path), before)
        self.assertNotEqual(manifest.module_identity(path), before)

    def test_existing_output_is_preserved_and_bad_manifest_rejected(self):
        self.assertEqual(self.cli("capture"), 0)
        before = self.output.read_bytes()
        self.assertEqual(self.cli("capture"), 2)
        self.assertEqual(self.output.read_bytes(), before)
        for data in ([], {"schema_version": 99}, {**json.loads(before), "fingerprint": "0" * 64}):
            self.output.write_text(json.dumps(data))
            self.assertEqual(self.cli("verify"), 2)

    def test_fixture_and_tape_are_explicit_hashes(self):
        fixture = self.root / "private-fixture.json"
        tape = self.root / "private-tape.bin"
        fixture.write_bytes(b"rules fixture")
        tape.write_bytes(b"input tape")
        extra = ("--fixture", str(fixture), "--tape", str(tape))
        self.assertEqual(self.cli("capture", *extra), 0)
        self.assertEqual(self.cli("verify", *extra), 0)
        self.assertEqual(self.cli("verify"), 1)
        tape.write_bytes(b"different tape")
        self.assertEqual(self.cli("verify", *extra), 1)


class SourceIdentityTests(unittest.TestCase):
    def test_toolchain_records_selected_linker_and_library_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            compiler, linker = root / "clang-cl.exe", root / "lld-link.exe"
            compiler.write_bytes(b"compiler")
            linker.write_bytes(b"linker")
            with patch.object(manifest.cc, "CLANG", str(compiler)), \
                    patch.object(manifest.shutil, "which", return_value=str(compiler)), \
                    patch.object(manifest.cc, "compile_identity", return_value="compile"), \
                    patch.object(manifest.cc, "OPUS_LIBS", []), \
                    patch.object(manifest.cc, "VPX_LIBS", []):
                before = manifest.toolchain_identity()
                linker.write_bytes(b"different linker")
                self.assertNotEqual(before["linker"], manifest.toolchain_identity()["linker"])
                with patch.dict(os.environ, {"LIB": "changed private library path"}):
                    after = manifest.toolchain_identity()
                    self.assertNotEqual(before["library_environment"], after["library_environment"])
                    self.assertNotIn("private library path", json.dumps(after))
                linker.unlink()
                with patch.object(manifest.shutil, "which", side_effect=[str(compiler), None]):
                    self.assertIsNone(manifest.toolchain_identity())

    def test_changed_file_during_inspection_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.bin"
            path.write_bytes(b"initial")

            def change(stream):
                path.write_bytes(b"changed size")
                return {}

            with self.assertRaisesRegex(ValueError, "changed during capture"):
                manifest.file_identity(path, change)

    def test_tracked_deletion_untracked_source_and_dirty_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "runtime").mkdir()
            path = root / "runtime/host.c"
            path.write_text("initial")
            subprocess.run(["git", "-C", str(root), "add", "runtime"], check=True)
            subprocess.run(["git", "-C", str(root), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                            "commit", "-qm", "fixture"], check=True)
            before = manifest.source_identity(root)
            path.write_text("changed")
            self.assertNotEqual(before, manifest.source_identity(root))
            path.unlink()
            self.assertIsNone(manifest.source_identity(root)["files"]["runtime/host.c"])
            (root / "runtime/new.c").write_text("new")
            self.assertIn("runtime/new.c", manifest.source_identity(root)["files"])


if __name__ == "__main__":
    unittest.main()
