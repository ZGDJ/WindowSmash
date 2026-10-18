import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location('check_project_docs', Path(__file__).resolve().parents[1] / 'tools/check_project_docs.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class ProjectDocsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in checker.CURATED:
            self.write(name, '# Document\n')
        self.write('docs/FSD.md', '### FSD-001 - Determinism\n')
        self.write('evidence/result.md', '# Verified result\n')

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

    def task(self, identifier='M0.1', status='todo', depends='none', evidence='none', requirement='FSD-001',
             owner='test agent / session', blocker='Missing test fixture'):
        return (f'### {identifier} - Test task\n- Status: {status}\n- Depends: {depends}\n'
                f'- Size: 3\n- Requirement: {requirement}\n- Evidence: {evidence}\n'
                '- Acceptance: Replay produces the same state hash.\n'
                f'- Owner: {owner}\n- Next: Run replay fixture.\n- Blocker: {blocker}\n\n')

    def errors(self, ledger):
        self.write('milestones/README.md', ledger)
        return checker.validate(self.root)[0]

    def test_valid_readiness_and_cli(self):
        ledger = (self.task(status='done', evidence='evidence/result.md')
                  + self.task('M0.2', depends='M0.1')
                  + self.task('M0.3', depends='M0.2')
                  + self.task('M0.4', status='blocked'))
        self.assertEqual([], self.errors(ledger))
        self.assertEqual(['M0.2'], checker.validate(self.root)[2])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(0, checker.main(['--root', str(self.root)]))
        self.assertIn('Total relative effort: 12', output.getvalue())
        self.assertIn('Closed scope effort: 3/12 (not feasibility or capability confidence)', output.getvalue())
        self.assertIn('M0: tasks=4, effort=12, closed scope effort=3/12', output.getvalue())
        self.assertIn('Ready tasks: M0.2', output.getvalue())

    def test_milestone_effort_is_grouped_and_numerically_ordered(self):
        self.errors(self.task('M10.1') + self.task('M2.1', status='done', evidence='evidence/result.md')
                    + self.task('M2.2').replace('- Size: 3', '- Size: 5'))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(0, checker.main(['--root', str(self.root)]))
        text = output.getvalue()
        self.assertIn('M2: tasks=2, effort=8, closed scope effort=3/8', text)
        self.assertIn('M10: tasks=1, effort=3, closed scope effort=0/3', text)
        self.assertLess(text.index('M2:'), text.index('M10:'))

    def test_restart_fields_required(self):
        for field, value in (('Owner', 'test agent / session'), ('Next', 'Run replay fixture.'),
                             ('Blocker', 'Missing test fixture')):
            for replacement in ('', f'- {field}: '):
                with self.subTest(field=field, replacement=replacement):
                    errors = self.errors(self.task().replace(f'- {field}: {value}', replacement))
                    self.assertTrue(any(f'nonempty {field}' in error for error in errors))

    def test_active_task_requires_owner(self):
        errors = self.errors(self.task(status='in_progress', owner='unassigned'))
        self.assertTrue(any('requires an assigned Owner' in error for error in errors))

    def test_blocked_task_requires_reason(self):
        errors = self.errors(self.task(status='blocked', blocker='none'))
        self.assertTrue(any('requires a concrete Blocker' in error for error in errors))

    def test_done_requires_existing_evidence(self):
        for evidence in ('none', 'evidence/missing.md', '../outside.md'):
            with self.subTest(evidence=evidence):
                self.assertTrue(any('evidence' in error for error in self.errors(self.task(status='done', evidence=evidence))))

    def test_dependency_cycle(self):
        errors = self.errors(self.task(depends='M0.2') + self.task('M0.2', depends='M0.1'))
        self.assertTrue(any('cycle' in error for error in errors))

    def test_unknown_requirement(self):
        self.assertTrue(any('unknown requirement' in error for error in self.errors(self.task(requirement='FSD-999'))))

    def test_invalid_status(self):
        self.assertTrue(any('invalid status' in error for error in self.errors(self.task(status='complete'))))

    def test_duplicate_ids(self):
        self.assertTrue(any('Duplicate' in error for error in self.errors(self.task() + self.task())))

    def test_broken_local_links(self):
        self.write('README.md', '[Missing](docs/missing.md#heading)\n[Web](https://example.com)\n[Here](#heading)\n')
        errors = self.errors(self.task())
        self.assertEqual(1, len(errors))
        self.assertIn('broken local link', errors[0])

    def test_valid_links_and_code_examples(self):
        self.write('README.md', '[FSD](docs/FSD.md#section)\n[FSD reference][fsd]\n[fsd]: docs/FSD.md\n```md\n[Example](missing.md)\n```\n')
        self.assertEqual([], self.errors(self.task()))

    def test_dependency_blocks_active_or_done(self):
        for status in ('in_progress', 'done'):
            with self.subTest(status=status):
                errors = self.errors(self.task() + self.task('M0.2', status=status, depends='M0.1', evidence='evidence/result.md'))
                self.assertTrue(any('requires completed dependency' in error for error in errors))

    def test_unknown_dependency(self):
        self.assertTrue(any('unknown dependency' in error for error in self.errors(self.task(depends='M9.9'))))

    def test_missing_acceptance_and_bad_effort(self):
        errors = self.errors(self.task().replace('- Size: 3', '- Size: 13').replace('- Acceptance: Replay produces the same state hash.', ''))
        self.assertTrue(any('Acceptance' in error for error in errors))
        self.assertTrue(any('invalid effort' in error for error in errors))

    def test_cli_failure(self):
        self.errors(self.task(status='invalid'))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(1, checker.main(['--root', str(self.root)]))


if __name__ == '__main__':
    unittest.main()
