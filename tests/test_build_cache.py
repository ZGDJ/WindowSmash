"""Synthetic compile-cache contracts; no compiler installation or game data required."""
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
try:
    import cc
    import modcache
    import recomp
finally:
    sys.path.pop(0)


class BuildCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="build-cache-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = self.root / "runtime"
        self.runtime.mkdir()
        self.header = self.runtime / "recomp.h"
        self.header.write_text("typedef int Cpu;\n")
        (self.runtime / "host.c").write_text("int host;\n")
        self.compiler = self.root / "compiler.exe"
        self.compiler.write_bytes(b"synthetic compiler version 1")
        self.module = self.root / "module"
        self.module.mkdir()
        (self.module / "manifest.tsv").write_text("g0.c\t1\t1\n")
        (self.module / "g0.c").write_text("int guest;\n")
        (self.module / "g_module.c").write_text("int module;\n")
        self.calls = []
        self.fail_compile = False
        for p in (patch.object(cc, "RUNTIME", str(self.runtime)),
                  patch.object(cc, "CLANG", str(self.compiler)),
                  patch.object(cc, "CFLAGS", ["/I", str(self.runtime)]),
                  patch.object(cc.shutil, "which", side_effect=lambda path: path),
                  patch.object(cc, "compile_each", side_effect=self.compile),
                  patch.object(recomp, "hle_names", return_value=set()),
                  patch.object(recomp, "hle_wraps", return_value={})):
            p.start()
            self.addCleanup(p.stop)
        self.output = redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def compile(self, jobs, workers):
        self.calls.append([Path(src).name for src, _obj, _opt in jobs])
        for src, obj, opt in jobs:
            # Even a failed compiler can leave a new-looking partial output.
            Path(obj).write_bytes(("partial" if self.fail_compile else "complete").encode()
                                  + Path(src).read_bytes() + opt.encode())
        return [(jobs[0][0], "synthetic failure")] if self.fail_compile and jobs else []

    def build_module(self, directory=None):
        return recomp.compile_dir(str(directory or self.module), 2)

    def change_preserving_time(self, path, contents):
        before = path.stat()
        path.write_text(contents)
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))

    def test_unchanged_reuses_and_missing_object_rebuilds_only_missing(self):
        self.assertTrue(self.build_module())
        self.assertEqual(self.calls, [["g0.c", "g_module.c"]])
        self.calls.clear()
        self.assertTrue(self.build_module())
        self.assertEqual(self.calls, [])
        (self.module / "g0.obj").unlink()
        self.assertTrue(self.build_module())
        self.assertEqual(self.calls, [["g0.c"]])

    def test_header_contents_invalidate_even_with_preserved_timestamp(self):
        self.assertTrue(self.build_module())
        self.change_preserving_time(self.header, "typedef long Cpu;\n")
        self.calls.clear()
        self.assertTrue(self.build_module())
        self.assertEqual(self.calls, [["g0.c", "g_module.c"]])

    def test_added_and_removed_nested_headers_invalidate(self):
        self.assertTrue(self.build_module())
        nested = self.runtime / "include"
        nested.mkdir()
        header = nested / "new.h"
        header.write_text("int nested;\n")
        self.calls.clear()
        self.assertTrue(self.build_module())
        self.assertEqual(self.calls, [["g0.c", "g_module.c"]])
        header.unlink()
        self.calls.clear()
        self.assertTrue(self.build_module())
        self.assertEqual(self.calls, [["g0.c", "g_module.c"]])

    def test_source_contents_invalidate_even_with_preserved_timestamp(self):
        self.assertTrue(self.build_module())
        self.change_preserving_time(self.module / "g0.c", "int changed_guest;\n")
        self.calls.clear()
        self.assertTrue(self.build_module())
        self.assertEqual(self.calls, [["g0.c"]])

    def test_flags_and_per_source_optimization_invalidate(self):
        self.assertTrue(self.build_module())
        cc.CFLAGS.append("/DNEW_ABI")
        self.calls.clear()
        self.assertTrue(self.build_module())
        self.assertEqual(self.calls, [["g0.c", "g_module.c"]])
        (self.module / "manifest.tsv").write_text("g0.c\t1\t30000\n")
        self.calls.clear()
        self.assertTrue(self.build_module())
        self.assertEqual(self.calls, [["g0.c"]])

    def test_compiler_contents_and_path_invalidate(self):
        self.assertTrue(self.build_module())
        self.compiler.write_bytes(b"synthetic compiler version two")
        self.calls.clear()
        self.assertTrue(self.build_module())
        self.assertEqual(self.calls, [["g0.c", "g_module.c"]])
        other = self.root / "other-compiler.exe"
        other.write_bytes(self.compiler.read_bytes())
        self.calls.clear()
        with patch.object(cc, "CLANG", str(other)):
            self.assertTrue(self.build_module())
        self.assertEqual(self.calls, [["g0.c", "g_module.c"]])

    def test_compiler_environment_invalidate(self):
        with patch.dict(os.environ, {"INCLUDE": "sdk-one"}):
            self.assertTrue(self.build_module())
        self.calls.clear()
        with patch.dict(os.environ, {"INCLUDE": "sdk-two"}):
            self.assertTrue(self.build_module())
        self.assertEqual(self.calls, [["g0.c", "g_module.c"]])

    def test_missing_and_corrupt_stamps_rebuild_legacy_objects(self):
        self.assertTrue(self.build_module())
        stamp = self.module / "compile.txt"
        stamp.unlink()
        self.calls.clear()
        self.assertTrue(self.build_module())
        self.assertEqual(self.calls, [["g0.c", "g_module.c"]])
        for invalid in ("not json", "[]", '{"sources": []}'):
            stamp.write_text(invalid)
            self.calls.clear()
            self.assertTrue(self.build_module())
            self.assertEqual(self.calls, [["g0.c", "g_module.c"]])

    def test_failed_batch_and_exception_force_complete_retry(self):
        self.assertTrue(self.build_module())
        self.header.write_text("int new_abi;\n")
        self.fail_compile = True
        self.calls.clear()
        self.assertFalse(self.build_module())
        self.assertEqual(self.calls, [["g0.c", "g_module.c"]])
        self.assertFalse((self.module / "compile.txt").exists())
        self.fail_compile = False
        self.calls.clear()
        self.assertTrue(self.build_module())
        self.assertEqual(self.calls, [["g0.c", "g_module.c"]])
        self.header.write_text("int another_abi;\n")
        with patch.object(cc, "compile_each", side_effect=RuntimeError("interrupted")):
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                self.build_module()
        self.assertFalse((self.module / "compile.txt").exists())
        self.calls.clear()
        self.assertTrue(self.build_module())
        self.assertEqual(self.calls, [["g0.c", "g_module.c"]])

    def test_success_without_objects_does_not_publish_stamp(self):
        with patch.object(cc, "compile_each", return_value=[]):
            self.assertFalse(self.build_module())
        self.assertFalse((self.module / "compile.txt").exists())
        self.calls.clear()
        self.assertTrue(self.build_module())
        self.assertEqual(self.calls, [["g0.c", "g_module.c"]])

    def test_adoption_stays_warm_and_recompile_does_not_mutate_donor(self):
        self.assertTrue(self.build_module())
        donor = {path.name: path.read_bytes() for path in self.module.iterdir()}
        target = self.root / "adopted"
        linked, _copied = modcache.adopt(str(self.module), str(target))
        self.assertGreater(linked, 0, "fixture must exercise hard links")
        self.assertTrue(os.path.samefile(self.module / "g0.obj", target / "g0.obj"))
        self.calls.clear()
        self.assertTrue(self.build_module(target))
        self.assertEqual(self.calls, [])
        self.header.write_text("int changed_abi;\n")
        self.assertTrue(self.build_module(target))
        self.assertEqual(self.calls, [["g0.c", "g_module.c"]])
        self.assertFalse(os.path.samefile(self.module / "g0.obj", target / "g0.obj"))
        self.assertFalse(os.path.samefile(self.module / "compile.txt", target / "compile.txt"))
        self.assertEqual({p.name: p.read_bytes() for p in self.module.iterdir()}, donor)

    def test_runtime_and_generated_tables_follow_headers_and_retry_failure(self):
        exe = self.root / "ssbu.exe"

        def fake_link(objects, output, options):
            Path(output).write_bytes(b"synthetic executable")

        with patch.object(cc, "link", side_effect=fake_link) as link:
            self.assertTrue(recomp.link([], str(exe)))
            expected = [["host.c", "hle_table.c", "nro_table.c"]]
            self.assertEqual(self.calls, expected)
            self.calls.clear()
            self.assertTrue(recomp.link([], str(exe)))
            self.assertEqual(self.calls, [])
            self.change_preserving_time(self.header, "int changed_abi;\n")
            self.fail_compile = True
            self.assertFalse(recomp.link([], str(exe)))
            self.assertEqual(self.calls, expected)
            self.assertEqual(link.call_count, 2)
            self.fail_compile = False
            self.calls.clear()
            self.assertTrue(recomp.link([], str(exe)))
            self.assertEqual(self.calls, expected)
            self.assertEqual(link.call_count, 3)


if __name__ == "__main__":
    unittest.main()
