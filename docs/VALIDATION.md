# Validation contract

Distinct proof levels: **source-only**, **game-backed local**, **cross-process/cross-machine/network**. One cannot close another. Run at repository root:

```powershell
python tools/check_project_docs.py
python -m unittest discover -s tests -v
python -I tools/test_ssbu_relay.py -v
```

Project checks use Python 3.12+; inherited config/save tests need Windows PowerShell; relay tests need loopback UDP. Full build prerequisites are in [BUILDING.md](BUILDING.md). Synthetic tests use disposable files. Separate permission failures from defects and retry only with legitimate permissions.

[Baseline evidence](../evidence/2026-10-18-upstream-baseline.md): 16 utility tests passed; 27/28 relay tests passed, with room-ordering failing in the suite and passing alone. This intermittent concern is not a waiver. Added validator tests change counts; record actual output.

## Evidence and closure

Use [TEMPLATE.md](../evidence/TEMPLATE.md): task/requirement, tested revision/diff identity, environment, commands/exit codes, expected/actual results, artifacts and reviewer. Game evidence also requires executable/module/content identity, fixture/rules/seed, tape hash, hardware/drivers/compiler, frames/trials and first divergence.

Before committing, identify base plus a diff hash/patch artifact; never invent a self-referential commit. Keep private raw traces under ignored `artifacts/local/`, committing sanitized summaries/hashes. State raw retention. Missing inputs mean blocked, not skipped-success. Reviewer compares acceptance with evidence; structural checks cannot certify truth.

## Oracles and failures

Inventory authoritative/excluded/reconstructible state including native continuation invariants. Use per-frame region hashes; justify exclusions and pointer normalization without hiding aliasing. Compare restores with an uninterrupted oracle and corrected predictions with an all-correct-input oracle. Preserve divergence/seed/minimized tape even if reruns pass.

For semantic changes, also compare named mechanics to the pinned upstream recomp under equivalent conditions (FSD-013). Record instrumentation/input differences and unavailable comparisons. Deterministic replay of modified behavior cannot prove preservation of the original behavior.

Apply trial counts/depths from [FSD.md](FSD.md); no silent reductions or empty-fixture passes. Use event logs plus audiovisual checks as applicable. Report tails/memory, not just averages. Reopen affected tasks/dependencies when evidence invalidates assumptions. Independently review high-risk state/scheduling changes.

CI green covers only jobs run. Private 13.0.5 gameplay remains a separate gate. Never upload game data or run untrusted PRs on private-data runners.
