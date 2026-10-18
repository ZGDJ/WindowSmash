# Agent entry point

Target Ultimate 13.0.5, Windows x64, full-roster competitive 1v1 rollback.
Rollback is unproven; never turn synthetic test results into gameplay claims.

## Context and ownership

- Read `milestones/README.md` first; it alone owns task status and dependencies.
- Read selected FSD requirements, relevant ADRs and affected source next.
- `docs/AGENT_WORKFLOW.md` defines packets; `docs/VALIDATION.md` defines evidence.
- Inspect `git status` and nested instructions; preserve unrelated edits.
- Claim one ready task with owner and UTC timestamp; avoid overlapping writers.

## Execute and verify

- Work autonomously within acceptance criteria; ordinary local edits/tests need no reconfirmation.
- Investigate unknown battle boundaries/state ownership before assuming interfaces.
- Prefer original recompiled behavior; justify semantic changes with ADRs and evidence.
- Compare semantic changes to pinned upstream behavior; self-consistent replay alone is insufficient.
- Critical hooks must uniquely validate against 13.0.5 and fail closed on mismatch.
- Run affected checks, fix introduced regressions, and record commands/results.
- Synthetic tests use disposable fixtures; run without asking at every step.
- Run `python tools/check_project_docs.py` after project-documentation changes.
- Done requires acceptance evidence and done dependencies; the validator checks structure, not truth.
- Missing private inputs block game tests; mocks cannot close game-backed gates.
- Update the ledger and leave a brief handoff before ending or switching work.

## Authorized collaboration

- Owner authorizes implementation, tests, commits, pushes to the fork and draft PRs.
- Use feature branches and draft PRs against the fork, not upstream; verify remotes first.
- Merges, releases, paid resources and destructive history changes need explicit authorization.
- Delegate disjoint investigations or high-risk state/scheduling review when useful.
- Assign exclusive edit scopes; integration owns the final verdict.
- Keep private inputs/generated code/dumps out of Git; use ignored `artifacts/local/`.
- Commit sanitized evidence; preserve notices and do not invent a project-wide license.
- Do not schedule recurring execution merely because this workflow supports autonomy.
