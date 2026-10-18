# Validation contract

Distinct proof levels: **source-only**, **game-backed local**, **cross-process/cross-machine/network**. One cannot close another. Run at repository root:

```powershell
python tools/check_project_docs.py
python -m unittest discover -s tests -v
python -I tools/test_ssbu_relay.py -v
```

Project checks use Python 3.12+; inherited config/save tests need Windows PowerShell; relay tests need loopback UDP. Full build prerequisites are in [BUILDING.md](BUILDING.md). Synthetic tests use disposable files. Separate permission failures from defects and retry only with legitimate permissions.

[Source CI](../.github/workflows/source-checks.yml) runs these same commands on Windows with Python 3.12 (minimum project-check version) and 3.14 (full-workflow Python version). It uses disposable synthetic data and loopback UDP, with no game inputs, secrets, package installation or self-hosted runner. The latter steps still run after an earlier failure to expose independent failures; the job remains failed. Actions are pinned to commits. See [GitHub's Python workflow guidance](https://docs.github.com/en/actions/tutorials/build-and-test-code/python).

Do not hide intermittent tests with retries, skips or `continue-on-error`. Preserve the first failure and minimize it; reruns diagnose reliability, not erase the failure. Keep unrelated checks running, then fix the test or product with a regression. [Baseline evidence](../evidence/2026-10-18-upstream-baseline.md) preserves the original relay failure; [audit evidence](../evidence/2026-10-18-practical-audit.md) records the clock-tie reproducer and fix.

Game-backed `difftest.py` and `functest.py` use exit 0 for nonempty comparison without hard mismatches, 1 for mismatches and 2 for invalid arguments or zero completed comparisons. A nonempty run still does not prove sufficient coverage: evidence must name selected cases, compared/skipped counts and exclusions. Set fixture-specific minimum coverage before qualification; do not treat one surviving comparison as full coverage.

## Evidence and closure

Use [TEMPLATE.md](../evidence/TEMPLATE.md): task/requirement, tested revision/diff identity, environment, commands/exit codes, expected/actual results, artifacts and reviewer. Game evidence also requires executable/module/content identity, fixture/rules/seed, tape hash, hardware/drivers/compiler, frames/trials and first divergence.

Before committing, identify base plus a diff hash/patch artifact; never invent a self-referential commit. Keep private raw traces under ignored `artifacts/local/`, committing sanitized summaries/hashes. State raw retention. Missing inputs mean blocked, not skipped-success. Reviewer compares acceptance with evidence; structural checks cannot certify truth.

## Oracles and failures

Inventory authoritative/excluded/reconstructible state including native continuation invariants. Use per-frame region hashes; justify exclusions and pointer normalization without hiding aliasing. Compare restores with an uninterrupted oracle and corrected predictions with an all-correct-input oracle. Preserve divergence/seed/minimized tape even if reruns pass.

For semantic changes, also compare named mechanics to the pinned upstream recomp under equivalent conditions (FSD-013). Record instrumentation/input differences and unavailable comparisons. Deterministic replay of modified behavior cannot prove preservation of the original behavior.

Apply the [GGPO/Smash contract](ROLLBACK_DESIGN.md): before-input frame boundaries, immutable checkpoint ownership, force-replay/synctest diagnostics, repeated overlapping correction, oldest-history tests and confirmation-safe terminal outcomes. Never compare hashes from different epochs or mismatched before/after-input boundaries. Callback mocks validate integration plumbing only. Record effect-policy artifacts separately from authoritative divergence.

Apply trial counts/depths from [FSD.md](FSD.md); no silent reductions or empty-fixture passes. Use event logs plus audiovisual checks as applicable. Report tails/memory, not just averages. Reopen affected tasks/dependencies when evidence invalidates assumptions. Independently review high-risk state/scheduling changes.

CI green covers only jobs run. Private 13.0.5 gameplay remains a separate gate. Never upload game data or run untrusted PRs on private-data runners.
