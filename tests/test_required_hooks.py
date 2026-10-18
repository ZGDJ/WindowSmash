"""Synthetic critical-hook gates; no actual battle hook or gameplay is qualified."""
from contextlib import ExitStack, redirect_stdout
import io
import importlib.util
import os
from pathlib import Path
import struct
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
try:
    import baseline_manifest
    import eh
    import recomp
    import required_hooks
finally:
    sys.path.pop(0)

BASE = 0x7100000000
ADDRESS = BASE + 16
SIG = ["d503201f", "d65f03c0"]


class RequiredHookTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="required-hooks-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.runtime = self.root / "runtime"
        self.runtime.mkdir()
        self.pin = {"module": "main", "build_id": "12" * 31 + "A0", "sha256": "ab" * 32, "signature": SIG}
        self.required = {ADDRESS: self.pin}
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(redirect_stdout(io.StringIO()))

    def source(self, address=ADDRESS):
        return (f"/* rollback-required: main {self.pin['build_id']} {self.pin['sha256']} */\n"
                f"/* signature: {' '.join(SIG)} */\nHLE_WRAP({address:x}) {{}}\n")

    def write(self, text):
        (self.runtime / "hle_test.c").write_text(text)

    def patch(self, target, name, **kwargs):
        return self.stack.enter_context(patch.object(target, name, **kwargs))

    def module(self, starts=(16,)):
        image = bytearray(128)
        for start in starts:
            struct.pack_into("<II", image, start, 0xD503201F, 0xD65F03C0)
        return SimpleNamespace(image=image, text=SimpleNamespace(mem=0, end=128),
                               u32=lambda at: struct.unpack_from("<I", image, at)[0], build_id="synthetic")

    def resolve(self, starts=(16,), sizes=None, wraps=None):
        with patch.object(recomp, "hle_wraps", return_value=wraps or {ADDRESS: SIG}):
            return recomp.resolve_wraps(self.module(starts), BASE, sizes or {start: 8 for start in starts}, "main", self.required)

    def test_strict_declaration_and_full_identity(self):
        self.write(self.source())
        self.assertEqual(required_hooks.declarations(self.runtime), self.required)

    def test_malformed_orphan_empty_and_uninformative_signatures_fail(self):
        cases = [self.source().replace("12" * 31 + "A0", "ABC"),
                 self.source().replace("ab" * 32, "xyz"),
                 self.source().splitlines()[0] + "\n",
                 self.source().replace("/* signature: " + " ".join(SIG) + " */", "/* signature:  */"),
                 self.source().replace(" ".join(SIG), "........"),
                 self.source().replace(" ".join(SIG), "bad"),
                 self.source().replace("HLE_WRAP", "OTHER_WRAP"),
                 self.source().replace("rollback-required:", "rollback-required :")]
        for text in cases:
            with self.subTest(text=text):
                self.write(text)
                with self.assertRaises(ValueError):
                    required_hooks.declarations(self.runtime)

    def test_duplicate_and_optional_alias_of_required_declarations_fail(self):
        for text in (self.source() * 2, self.source() + f"HLE_WRAP({ADDRESS:x}) {{}}\n"):
            self.write(text)
            with self.assertRaises(ValueError):
                required_hooks.declarations(self.runtime)

    def test_unique_original_and_relocated_functions(self):
        forward, moved = self.resolve()
        self.assertEqual(forward[16], ("wrap", f"hle_wrap_{ADDRESS:x}"))
        self.assertEqual(moved, [])
        forward, moved = self.resolve((32,))
        self.assertIn(32, forward)
        self.assertEqual(moved, [(ADDRESS, BASE + 32)])

    def test_missing_changed_and_ambiguous_even_at_original_address_fail(self):
        for starts, sizes in (((), {16: 8}), ((32,), {16: 8}), ((16, 32), {16: 8, 32: 8}), ((16,), {16: 4})):
            with self.subTest(starts=starts, sizes=sizes), self.assertRaisesRegex(ValueError, "signature matches"):
                self.resolve(starts, sizes)

    def test_undeclared_function_start_is_not_a_match(self):
        with self.assertRaises(ValueError):
            self.resolve((16,), {32: 8})

    def test_collisions_fail_in_both_address_orders(self):
        for optional in (BASE + 8, BASE + 24):
            with self.subTest(optional=optional), self.assertRaisesRegex(ValueError, "collides"):
                self.resolve(wraps={ADDRESS: SIG, optional: SIG})

    def test_optional_missing_and_ambiguous_behavior_is_preserved(self):
        with patch.object(recomp, "hle_wraps", return_value={BASE + 8: SIG}):
            self.assertEqual(recomp.resolve_wraps(self.module(()), BASE, {16: 8}, "main", {}), ({}, []))
            self.assertEqual(recomp.resolve_wraps(self.module((16, 32)), BASE, {16: 8, 32: 8}, "main", {}), ({}, []))
        with patch.object(recomp, "hle_wraps", return_value={ADDRESS: SIG}):
            # Existing optional original-address fast path remains supported.
            self.assertIn(16, recomp.resolve_wraps(self.module((16, 32)), BASE, {16: 8, 32: 8}, "main", {})[0])

    def test_module_identity_rejects_header_and_content_drift(self):
        path = self.root / "main"
        raw = bytearray(256)
        raw[:4] = b"NSO0"
        raw[0x40:0x60] = bytes.fromhex(self.pin["build_id"])
        path.write_bytes(raw)
        self.pin["sha256"] = baseline_manifest.module_identity(path)["sha256"]
        recomp.validate_hook_identity(path, "main", self.required)
        for at in (0x40, 0x80):
            changed = bytearray(raw)
            changed[at] ^= 1
            path.write_bytes(changed)
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                recomp.validate_hook_identity(path, "main", self.required)
        path.unlink()
        with self.assertRaises(OSError):
            recomp.validate_hook_identity(path, "main", self.required)

    def test_standalone_link_rejects_before_compiler_work(self):
        self.patch(recomp, "required_wraps", return_value=self.required)
        for proof in (None, {}, {ADDRESS: {**self.pin, "sha256": "00" * 32}}):
            with self.assertRaisesRegex(ValueError, "recomp.py all"):
                recomp.link([], str(self.root / "ssbu.exe"), validated_hooks=proof)

    def test_link_never_supplies_missing_original_alias_for_required_hook(self):
        import cc
        self.patch(recomp, "required_wraps", return_value=self.required)
        self.patch(recomp, "hle_wraps", return_value={ADDRESS: SIG, BASE + 8: SIG})
        self.patch(recomp, "hle_names", return_value=set())
        self.patch(cc, "RUNTIME", new=str(self.runtime))
        self.patch(cc, "compile_cached", return_value=([], 0))
        exe = self.root / "ssbu.exe"
        def fake_link(objects, output, options):
            Path(output).write_bytes(b"synthetic")
        linker = self.patch(cc, "link", side_effect=fake_link)
        self.assertTrue(recomp.link([], str(exe), validated_hooks=self.required))
        self.assertEqual(linker.call_args.args[2], [f"/alternatename:f_{BASE + 8:x}_orig=rt_wrap_missing"])

    def setup_all(self):
        self.patch(recomp, "required_wraps", return_value=self.required)
        self.patch(recomp, "TREE", new=str(self.root))
        paths = {"main": str(self.root / "main"), "sdk": str(self.root / "sdk")}
        self.patch(recomp, "module_paths", return_value=paths)
        identity = self.patch(recomp, "validate_hook_identity")
        self.patch(recomp, "check")
        self.patch(recomp, "tools_fingerprint", return_value="fp")
        self.patch(recomp, "Module", return_value=self.module())
        for name in paths:
            Path(paths[name]).write_bytes(b"input")
            image = self.root / "dump/modules" / (name + ".reloc.bin")
            image.parent.mkdir(parents=True, exist_ok=True)
            image.write_bytes(b"stale image")
            os.utime(image, (2000000000, 2000000000))
        self.patch(recomp.modcache, "build_info", side_effect=lambda target: ("synthetic", recomp.MODULES[Path(target).name], Path(target).name, "fp"))
        self.patch(recomp.modcache, "write_stamp")
        self.patch(recomp, "compile_dir", return_value=True)
        build = self.patch(recomp, "build", return_value=self.required)
        image = self.patch(recomp, "image")
        link = self.patch(recomp, "link", return_value=True)
        return paths, identity, build, image, link

    def test_required_warm_cache_regenerates_code_and_image_optional_cache_reuses(self):
        paths, identity, build, image, link = self.setup_all()
        self.assertTrue(recomp.build_all("exefs", str(self.root / "build"), 1))
        build.assert_called_once_with(paths["main"], str(self.root / "build/main"), 1, 40000)
        image.assert_called_once_with(paths["main"], str(self.root / "dump/modules/main.reloc.bin"))
        self.assertEqual(link.call_args.kwargs["validated_hooks"], self.required)

    def test_missing_module_and_identity_mismatch_fail_before_cache_work(self):
        paths, identity, build, image, link = self.setup_all()
        paths.pop("main")
        with self.assertRaisesRegex(ValueError, "missing"):
            recomp.build_all("exefs", str(self.root / "build"), 1)
        paths["main"] = str(self.root / "main")
        identity.side_effect = ValueError("identity mismatch")
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            recomp.build_all("exefs", str(self.root / "build"), 1)
        build.assert_not_called()
        image.assert_not_called()
        link.assert_not_called()

    def test_failed_validation_does_not_reach_link(self):
        _, _, build, _, link = self.setup_all()
        build.side_effect = ValueError("ambiguous required hook")
        with self.assertRaises(ValueError):
            recomp.build_all("exefs", str(self.root / "build"), 1)
        link.assert_not_called()

    def test_module_drift_during_compile_does_not_reach_link(self):
        _, identity, _, _, link = self.setup_all()
        identity.side_effect = [None, ValueError("module changed during build")]
        with self.assertRaisesRegex(ValueError, "changed during build"):
            recomp.build_all("exefs", str(self.root / "build"), 1)
        link.assert_not_called()

    def test_worker_scratch_image_can_be_forced_fresh(self):
        self.patch(recomp, "TREE", new=str(self.root))
        mod = self.module()
        path = Path(recomp.image_file(mod))
        path.write_bytes(b"x" * len(mod.image))
        recomp.image_file(mod, force=True)
        self.assertEqual(path.read_bytes(), mod.image)

    def test_real_build_validates_before_emission_and_refreshes_worker_image(self):
        self.patch(recomp, "TREE", new=str(self.root))
        self.patch(recomp, "required_wraps", return_value=self.required)
        self.patch(recomp, "hle_wraps", return_value={ADDRESS: SIG})
        self.patch(recomp, "hle_names", return_value=set())
        self.patch(recomp, "unwind_jumpto", return_value={})
        self.patch(recomp, "setjmp_targets", return_value={})
        self.patch(recomp, "module_table", return_value=("synthetic module table", 0, 0))
        self.patch(eh, "landing_pads", return_value={})
        path = self.root / "main"
        header = bytearray(256)
        header[:4] = b"NSO0"
        header[0x40:0x60] = bytes.fromhex(self.pin["build_id"])
        path.write_bytes(header)
        self.pin["sha256"] = baseline_manifest.module_identity(path)["sha256"]
        mod = self.module()
        mod.exports = []
        load = self.patch(recomp, "load", return_value=(mod, {16: {"eh"}}, [(16, 8)]))
        scratch = Path(recomp.image_file(mod))
        scratch.write_bytes(b"x" * len(mod.image))
        emitted = []
        class Workers:
            def __enter__(workers):
                return workers
            def __exit__(workers, *args):
                pass
            def imap_unordered(workers, function, tasks):
                for index, chunk, outdir in tasks:
                    emitted.append(chunk)
                    name = f"g{index:04d}.c"
                    Path(outdir, name).write_text("synthetic generated function")
                    yield name, set(), 2, 2, 0, []
        pool = self.patch(recomp, "Pool", return_value=Workers())
        result = recomp.build(str(path), str(self.root / "generated"), 1, 40000)
        self.assertEqual(result, self.required)
        self.assertEqual(scratch.read_bytes(), mod.image)
        self.assertEqual(emitted, [[(16, 8)]])
        self.assertEqual(pool.call_args.args[2][3][16], ("wrap", f"hle_wrap_{ADDRESS:x}"))
        pool.reset_mock()
        ambiguous = self.module((16, 32))
        ambiguous.exports = []
        load.return_value = (ambiguous, {16: {"eh"}, 32: {"eh"}}, [(16, 8), (32, 8)])
        with self.assertRaisesRegex(ValueError, "2 signature matches"):
            recomp.build(str(path), str(self.root / "ambiguous"), 1, 40000)
        pool.assert_not_called()

    def test_declaration_changes_invalidate_generation_fingerprint(self):
        self.patch(recomp, "required_wraps", return_value=self.required)
        before = recomp.tools_fingerprint()
        self.pin["sha256"] = "00" * 32
        self.assertNotEqual(before, recomp.tools_fingerprint())

    def test_linux_rejects_required_and_malformed_declarations(self):
        required_hooks.reject_unvalidated_builder(self.runtime, "test builder")
        self.write(self.source())
        with self.assertRaisesRegex(ValueError, "unsupported"):
            required_hooks.reject_unvalidated_builder(self.runtime, "test builder")
        self.write("/* rollback-required: bad */\n")
        with self.assertRaisesRegex(ValueError, "malformed"):
            required_hooks.reject_unvalidated_builder(self.runtime, "test builder")

    def test_alternate_build_entrypoints_reject_before_writes_or_compilers(self):
        self.write(self.source())
        toolchain = ModuleType("toolchain")
        for name in ("CLANG", "DXVK_INCLUDE", "DXVK_LIBS", "LLVM", "REPO", "RUNTIME", "SYSROOT",
                     "TOOLCHAIN", "VKD3D_BUILD", "VKD3D_SRC", "PORT_DIR"):
            setattr(toolchain, name, str(self.root))
        toolchain.RUNTIME = str(self.runtime)
        toolchain.CFLAGS = []
        toolchain.default_port = lambda: str(self.root)
        for name in ("compile_each", "read_port_stamp", "run", "same_path", "write_port_stamp"):
            setattr(toolchain, name, lambda *args: self.fail("unexpected toolchain work"))
        tools = Path(__file__).resolve().parents[1] / "tools"
        import cc
        for filename, entries in (("build_linux.py", ("main", "link", "runtime_jobs")), ("wintest.py", ("main",))):
            with self.subTest(filename=filename), patch.dict(sys.modules, {"toolchain": toolchain}), \
                    patch.object(cc, "RUNTIME", str(self.runtime)), patch.object(sys, "path", list(sys.path)):
                spec = importlib.util.spec_from_file_location("synthetic_builder", tools / "linux" / filename)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                with patch.object(module.os, "makedirs") as mkdir:
                    for entry in entries:
                        with self.assertRaisesRegex(ValueError, "unsupported"):
                            getattr(module, entry)()
                    mkdir.assert_not_called()


if __name__ == "__main__":
    unittest.main()
