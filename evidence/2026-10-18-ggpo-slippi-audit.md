# GGPO / Smash / Slippi alignment audit

Date: 2026-10-18. Task M0.6; FSD-012/014/015. Source-only documentation audit, not rollback execution. Base `e7052f8`; changes on `docs/rollback-foundation`.

## Sources inspected

GGPO commit `7ddadef8546a7d99ff0b3530c6056bc8ee4b9c0a`: developer guide, public callback/API header and synctest backend. Slippi Ishiiruka commit `60f7b63496fb6ec7b9180a04f16f3edc0ad89fe2`: SlippiSavestate.cpp, SlippiNetplay.cpp and EXI_DeviceSlippi.cpp; also the project's component overview. Commit identities retrieved through GitHub API. Primary-source links and distinctions are in [ROLLBACK_DESIGN.md](../docs/ROLLBACK_DESIGN.md).

## Findings and changes

1. Existing generic rewind gates aligned broadly, but lacked a precise callback/frame/ownership contract. Added FSD-014 and M4.4 with before-input numbering, checkpoint lifetime, coordinator history separation and offline forced replay; actual GGPO synctest belongs to library integration.
2. Excluding transitions from rewind left predicted terminal events unsafe. Added FSD-015/M4.5 and made performance/network gates depend on lifecycle proof.
3. Current-input polling omitted game-side history and assumed sampling cadence prematurely. Strengthened input discovery, press/hold/release/buffering and hitlag-sensitive correction requirements.
4. Added altered object lifetimes, allocation identity/RNG, overlapping corrections, oldest retained state and resource-growth tests. M4.1 now requires the early mechanics fixture matrix.
5. Added initial-state agreement, match epochs, old-packet rejection, peer pacing, confirmation-signal design and desync failure policy.
6. Recorded transferable Slippi methods without copying Melee addresses/exclusions, asserting GGPO use, or treating Dolphin snapshots as portable to native fibers.

No runtime behavior or third-party dependency changed. No third-party code copied. The docs validator now includes the new design file in its curated link checks. The prior foundation's 24-task/113-unit totals remain historical; current scope is recalculated from the ledger.

Independent reviewer identified Smash-specific gaps before editing and checked the final files. No remaining blockers: offline engine contract M4.4 precedes actual backend integration, terminal barrier M4.5 gates networking, and early fixtures gate M4.1. Reviewer independently ran document validation successfully.

## Verification and verdict

Windows / Python 3.12.3. `python tools/check_project_docs.py`: exit 0, 27 tasks / 123 relative effort units, valid dependencies/links. `python -m unittest discover -s tests -p test_project_docs.py -v`: all 16 tests passed, exit 0. `git diff --check`: exit 0. Changed validator SHA-256: `4C46357B81D288A2934CD7D19F600010FC1B476935AEDD2734CEE78D336AA62B` (only curated document coverage changed). Raw output retained in this session, not committed.

Verdict: M0.6 documentation audit acceptance satisfied. No game-backed gate closed, no GGPO library linked, no network/session/snapshot implementation tested. Unchanged runtime/source utility tests were not redundantly rerun; their previous 32-test baseline remains historical evidence, not a new run. External source observations are scoped to the pinned revisions. Doc structure passes do not prove rollback feasibility.
