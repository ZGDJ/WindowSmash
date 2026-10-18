"""Source-only CLI/evidence safeguards; no game, native compiler or Unicorn required."""
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
try:
    import difftest
    import functest
finally:
    sys.path.pop(0)


class DifferentialCliTests(unittest.TestCase):
    def test_defaults_and_zero_display_limit(self):
        diff = difftest.parse_args(["fixture.nso", "--show", "0"])
        func = functest.parse_args(["fixture.nso", "--show", "0"])
        self.assertEqual((diff.per_template, diff.states, diff.jobs, diff.show), (4, 16, 16, 0))
        self.assertEqual((func.functions, func.states, func.jobs, func.max_insns, func.show),
                         (3000, 8, 8, 4000, 0))

    def test_execution_counts_must_be_positive(self):
        for module, options in (
            (difftest, ("--per-template", "--states", "--jobs")),
            (functest, ("--functions", "--states", "--jobs", "--max-insns")),
        ):
            for option in options:
                for value in ("0", "-1", "not-a-number"):
                    with self.subTest(tool=module.__name__, option=option, value=value):
                        errors = io.StringIO()
                        with contextlib.redirect_stderr(errors), self.assertRaises(SystemExit) as result:
                            module.parse_args(["fixture.nso", option, value])
                        self.assertEqual(result.exception.code, 2)
                        self.assertIn(option, errors.getvalue())

    def test_incomplete_arguments_and_negative_display_limit_fail(self):
        for module in (difftest, functest):
            for args in ([], ["fixture.nso", "--states"], ["fixture.nso", "--show", "-1"]):
                with self.subTest(tool=module.__name__, args=args):
                    with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as result:
                        module.parse_args(args)
                    self.assertEqual(result.exception.code, 2)

    def test_empty_comparisons_are_inconclusive(self):
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            self.assertEqual(difftest.comparison_exit_code(0, []), 2)
        self.assertIn("INCONCLUSIVE", errors.getvalue())
        self.assertIn("no completed state comparisons", errors.getvalue())

    def test_nonempty_success_and_mismatch_keep_existing_status(self):
        self.assertEqual(difftest.comparison_exit_code(1, []), 0)
        self.assertEqual(difftest.comparison_exit_code(2, ["native fault"]), 1)

    def test_empty_function_selection_stops_before_native_build(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.object(functest.cc, "ROOT", root), \
                 patch.object(functest, "Module") as module, \
                 patch.object(functest, "discover", return_value=({}, {})), \
                 patch.object(functest, "Lifter"), \
                 patch.object(functest.cc, "compile_one") as compile_one, \
                 patch.object(sys, "argv", ["functest.py", "fixture.nso"]), \
                 contextlib.redirect_stdout(io.StringIO()), \
                 contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(functest.main(), 2)
                module.assert_called_once_with("fixture.nso")
                compile_one.assert_not_called()

    def test_real_cli_rejects_bad_counts_before_loading_private_inputs(self):
        for script in ("difftest.py", "functest.py"):
            with self.subTest(script=script):
                result = subprocess.run(
                    [sys.executable, str(TOOLS / script), "missing-private-input.nso", "--states", "0"],
                    capture_output=True, text=True, timeout=20,
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("--states", result.stderr)
                self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
