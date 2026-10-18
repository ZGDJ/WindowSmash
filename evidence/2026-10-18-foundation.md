# Foundation verification

Date: 2026-10-18. Tasks M0.1/M0.3; FSD-012; source-only.

Base: `4b512d2ad44f2312d47d5ba5746f96a27eda3653`, branch `docs/rollback-foundation`. Tested working changes are identified by this branch's foundation commit and the exact implementation hashes below; no self-referential final commit hash is asserted. No gameplay claim.

Independent challenge required explicit version/fixture versus full-roster scope, host continuation inventory, separate proof levels, fail-closed hooks, deferred library/checkpoint choice, honest research gates and bounded packets. Incorporated into FSD/ADRs/workflow.

Owner confirmed 13.0.5/full roster and pushes/draft PRs. Product: SmashRollback; fork retains ZGDJ/WindowSmash. No merge/release/paid-resource/recurring-run authorization assumed.

## Verification

Environment: Windows, Python 3.12.3, Windows PowerShell; no private game inputs. Primary agent integrated two subagents: scope challenge/review and validator implementation.

- `python tools/check_project_docs.py`: exit 0, all curated local links and task contracts valid. Final ledger has 24 tasks and 113 relative effort units; only foundation work is complete.
- `python -m unittest discover -s tests -p test_project_docs.py -v`: initial 12 tests passed; expanded validator now has 16 tests covering restart fields and effort grouping in addition to dependency/status/evidence/link failures.
- `python -m unittest discover -s tests -v`: 32 tests passed, exit 0, with approved temporary-file permissions. Includes all 16 project-validator and 16 inherited utility tests.
- `git diff --check`: exit 0. No runtime implementation changed.

Exact SHA-256 of tested implementation:

- `tools/check_project_docs.py`: `AB8681D6A003E733FDB6AA7A8D2FC2B73D73EAD283B3D3ECF64EA708E8FD471C`
- `tests/test_project_docs.py`: `C3E94D9450F5FD0F67F85BFE4581A117932C178DF2E262A58669CC7B3D70843D`

Independent final scope review verified five corrections: frame-input dependency on boundary discovery, upstream semantic comparisons (FSD-013/M3.4), split-task accounting, enforced handoff fields, and same-tape replay wording. Reviewer ran the validator successfully and reported no remaining draft-PR scope blocker.

Verdict: M0.1 and M0.3 acceptance satisfied. No gameplay, deterministic replay, restored state, performance, cross-machine or CI-run claim is made. Relay runtime was untouched and its known intermittent failure was not rerun/waived; M0.4 owns investigation. Source-only CI is future M0.5 work. Raw test output remains in this session; committed summaries/hashes identify results without private content.
