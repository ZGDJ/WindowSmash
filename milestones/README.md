# Milestones and work ledger

This is the **only task-status source of truth**. [FSD](../docs/FSD.md) owns requirements, [ADRs](../adr/README.md) decisions, [workflow](../docs/AGENT_WORKFLOW.md) execution and [evidence](../evidence/README.md) results.

Target: Windows x64, Ultimate 13.0.5/full roster, competitive 1v1/no items. No rollback capability is verified. Do not implement 11.0.0 first.

## How to use

Statuses: `todo` (readiness computed), `in_progress` (claimed), `blocked` (explicit missing prerequisite), `done` (acceptance/evidence verified). Status is the checkbox equivalent; do not duplicate checklists elsewhere. Owner includes agent/session and UTC timestamp while claimed. Done requires all dependencies done and repository-relative evidence. Requirement references map work, not certification of an entire requirement.

Run `python tools/check_project_docs.py` for calculated counts, effort totals and ready tasks. Sizes 1/2/3/5/8 are relative effort, not time/tokens. Split size-8 work before implementation. Negative research needs remediation dependencies before advancing capability gates. Never mark blocked work done to free the queue.

## M0 - Foundation and source reliability

### M0.1 - Project contract and scope
- Status: done
- Depends: none
- Size: 3
- Requirement: FSD-012
- Evidence: evidence/2026-10-18-foundation.md
- Acceptance: FSD/ADRs/workflow/ledger agree with owner scope; independent challenge addressed; links validate.
- Owner: unassigned
- Next: Maintain contract as decisions evolve; select ready source work.
- Blocker: none

### M0.2 - Preserve upstream baseline evidence
- Status: done
- Depends: none
- Size: 1
- Requirement: FSD-012
- Evidence: evidence/2026-10-18-upstream-baseline.md
- Acceptance: Pin source and record actual utility/relay outcomes, limitations and architecture findings.
- Owner: unassigned
- Next: Use baseline to distinguish inherited failures.
- Blocker: none

### M0.3 - Mechanically validate project contract
- Status: done
- Depends: M0.2
- Size: 2
- Requirement: FSD-012
- Evidence: evidence/2026-10-18-foundation.md
- Acceptance: Stdlib validator rejects invalid dependencies/status/requirements/evidence/links; meaningful synthetic tests pass.
- Owner: unassigned
- Next: Run validator on each project-contract change.
- Blocker: none

### M0.4 - Investigate relay ordering intermittency
- Status: todo
- Depends: M0.2
- Size: 2
- Requirement: FSD-012
- Evidence: none
- Acceptance: Reproduce/minimize ordering failure or report bounded negative investigation and follow-up; no silent quarantine.
- Owner: unassigned
- Next: Inspect asynchronous room creation/test synchronization.
- Blocker: none

### M0.5 - Source-only CI
- Status: todo
- Depends: M0.1, M0.3
- Size: 2
- Requirement: FSD-011, FSD-012
- Evidence: none
- Acceptance: Fork CI runs contract and appropriate source tests on Windows without private data; flaky suite policy explicit.
- Owner: unassigned
- Next: Add minimal workflow without private runners/data.
- Blocker: none

### M0.6 - Audit GGPO and Smash-specific design
- Status: done
- Depends: M0.1, M0.3
- Size: 2
- Requirement: FSD-012, FSD-014, FSD-015
- Evidence: evidence/2026-10-18-ggpo-slippi-audit.md
- Acceptance: Primary GGPO/Slippi sources inspected; design/FSD/dependencies address adapter, input-history and terminal-state gaps; independent review and validator pass.
- Owner: unassigned
- Next: Use the accepted contract in engine and session work; revalidate backend specifics when pinning dependencies.
- Blocker: none

## M1 - Reproducible 13.0.5 baseline

### M1.1 - Input and build identity tooling
- Status: todo
- Depends: M0.1, M0.3
- Size: 3
- Requirement: FSD-001, FSD-011
- Evidence: none
- Acceptance: Manifest schema/tool captures version/runtime/toolchain/content identities and passes synthetic tests without exposing data.
- Owner: unassigned
- Next: Inspect install_version.py and define manifest.
- Blocker: none

### M1.2 - Build and complete 13.0.5 offline matches
- Status: blocked
- Depends: M1.1
- Size: 5
- Requirement: FSD-001
- Evidence: none
- Acceptance: Actual 13.0.5 build and three complete fixture matches satisfy FSD-001 with identified artifacts.
- Owner: unassigned
- Next: Locate owner-supplied inputs/fonts/toolchain; record prerequisites.
- Blocker: No private 13.0.5 inputs/build available in current checkout.

### M1.3 - Critical hook validation
- Status: todo
- Depends: M1.1
- Size: 3
- Requirement: FSD-011
- Evidence: none
- Acceptance: Required hooks fail closed for missing/ambiguous/mismatched identity; negative tests pass; actual battle hooks qualify in M2.1.
- Owner: unassigned
- Next: Inspect resolve_wraps and required-versus-optional semantics.
- Blocker: none

## M2 - Controlled simulation

### M2.1 - Discover tick and continuation boundary
- Status: todo
- Depends: M1.2, M1.3
- Size: 8
- Requirement: FSD-002, FSD-005
- Evidence: none
- Acceptance: Trace version-specific tick boundary and worker/fiber invariants; remediate unsafe continuations before closing this capability gate.
- Owner: unassigned
- Next: Split trace, job inventory and safe-boundary proof packets.
- Blocker: none

### M2.2 - Two-player frame input tapes
- Status: todo
- Depends: M1.2, M1.3, M2.1
- Size: 5
- Requirement: FSD-003
- Evidence: none
- Acceptance: Both logical input lanes, discovered sampling cadence and game-side history satisfy FSD-003; include press/hold/release/buffered actions and hitlag-sensitive correction outcomes.
- Owner: unassigned
- Next: Separate tape schema from game consumption hooks.
- Blocker: none

### M2.3 - Single-tick driver
- Status: todo
- Depends: M2.1, M2.2
- Size: 5
- Requirement: FSD-002
- Evidence: none
- Acceptance: 600 steps independent of presentation cadence with authoritative jobs quiescent; independent review recorded.
- Owner: unassigned
- Next: Integrate explicit driver with proven boundary.
- Blocker: none

## M3 - State and determinism

### M3.1 - State ownership and hash oracle
- Status: todo
- Depends: M2.3
- Size: 5
- Requirement: FSD-004, FSD-005
- Evidence: none
- Acceptance: Inventory restored/reconstructible/excluded state including host continuations; justified exclusions and per-region diagnostics.
- Owner: unassigned
- Next: Map state owners and allocator/object lifetimes.
- Blocker: none

### M3.2 - Prove forward replay
- Status: todo
- Depends: M3.1, M3.4
- Size: 8
- Requirement: FSD-004
- Evidence: none
- Acceptance: Two runs of the same 10,000-tick input tape match every frame locally and cross-process; divergence artifacts preserved.
- Owner: unassigned
- Next: Split clock/RNG/scheduling/FP investigation by observed failures.
- Blocker: none

### M3.3 - Select checkpoint representation
- Status: todo
- Depends: M3.1
- Size: 3
- Requirement: FSD-005
- Evidence: none
- Acceptance: ADR chooses representation from measured state/continuation evidence and specifies restore/lifecycle invariants.
- Owner: unassigned
- Next: Compare pages versus selective state without assuming stack rewind.
- Blocker: none

### M3.4 - Behavioral reference comparisons
- Status: todo
- Depends: M2.3
- Size: 5
- Requirement: FSD-013
- Evidence: none
- Acceptance: Named battle mechanics compared with pinned upstream 13.0.5 behavior; instrumentation differences/limitations documented and no unexplained semantic changes.
- Owner: unassigned
- Next: Define representative damage/timing/movement/collision reference cases alongside the replay harness.
- Blocker: none

## M4 - Offline rollback proof

### M4.1 - Restore and replay correctness
- Status: todo
- Depends: M3.2, M3.3, M6.1
- Size: 8
- Requirement: FSD-005
- Evidence: none
- Acceptance: FSD-005 counts/depths and named early mechanics fixtures pass uninterrupted oracle, including altered spawn/ownership/allocation/RNG paths; independent review passes.
- Owner: unassigned
- Next: Split capture/restore, lifecycle and replay test packets.
- Blocker: none

### M4.2 - Prediction correction and effects
- Status: todo
- Depends: M4.1
- Size: 8
- Requirement: FSD-006
- Evidence: none
- Acceptance: Wrong-input and repeated overlapping corrections match oracle; effect policy and render-on/off hashes pass, oldest history/resource growth tested and reviewed.
- Owner: unassigned
- Next: Split classification, suppression and correction-oracle packets.
- Blocker: none

### M4.3 - Performance and supported window
- Status: todo
- Depends: M4.2, M4.4, M4.5
- Size: 5
- Requirement: FSD-007
- Evidence: none
- Acceptance: Hardware/window selected and p95/p99 catch-up/memory budgets met; failures drive profiling.
- Owner: unassigned
- Next: Agree hardware floor and scene matrix before claiming supported limits.
- Blocker: none

### M4.4 - GGPO-shaped adapter and offline diagnostics
- Status: todo
- Depends: M4.1
- Size: 3
- Requirement: FSD-014
- Evidence: none
- Acceptance: Engine save/load/free/log/step contract tested on actual battle; initial/oldest checkpoints, buffer ownership and forced replay diagnostic cases pass. Actual GGPO synctest adoption follows M5.2.
- Owner: unassigned
- Next: Implement the proven engine boundary without duplicating transport; document callback numbering and coordinator ownership.
- Blocker: none

### M4.5 - Speculative terminal-state barrier
- Status: todo
- Depends: M4.2
- Size: 5
- Requirement: FSD-015
- Evidence: none
- Acceptance: Wrong predicted last-stock KO/timeout/simultaneous outcome can be corrected offline; no premature teardown/unload/save/result and exactly one committed outcome.
- Owner: unassigned
- Next: Test simulated confirmation schedules and resource retention; network confirmation remains M5.2.
- Blocker: none

## M5 - Online sessions

### M5.1 - Session architecture and library choice
- Status: todo
- Depends: M4.3
- Size: 3
- Requirement: FSD-008
- Evidence: none
- Acceptance: Resolve ADR-0004/0006 with offline evidence; pin GGPO candidate or justify alternate backend; specify initial-state/epoch, confirmation-signal access, delay/prediction/pacing and disconnect policy.
- Owner: unassigned
- Next: Evaluate integration at the established engine boundary.
- Blocker: none

### M5.2 - Two-peer rollback integration
- Status: todo
- Depends: M5.1
- Size: 8
- Requirement: FSD-008, FSD-014, FSD-015
- Evidence: none
- Acceptance: Actual adapter synctest and two-peer oracle pass; failed sync never advances; initial-state mismatch, old epochs, prediction limit, time-sync, disconnect/rematch and terminal confirmation pass.
- Owner: unassigned
- Next: Split handshake, history, coordinator and disconnect packets.
- Blocker: none

### M5.3 - Impairment and cross-machine qualification
- Status: todo
- Depends: M5.2
- Size: 5
- Requirement: FSD-009
- Evidence: none
- Acceptance: FSD-009 matrix on two machines with seeds, confirmed-state agreement and latency/disconnect evidence.
- Owner: unassigned
- Next: Define reproducible pairwise impairment fixtures.
- Blocker: none

## M6 - Full-roster qualification

### M6.1 - Roster mechanics and competitive rules matrix
- Status: todo
- Depends: M1.1
- Size: 3
- Requirement: FSD-010
- Evidence: none
- Acceptance: Enumerate 13.0.5 fighters/DLC/Mii and approved stages/rules; entries initially untested; select named early input-history/combat/lifecycle/RNG/terminal fixtures before M4.1, plus full-roster interaction plan.
- Owner: unassigned
- Next: Confirm stage/Mii choices and inventory mechanics.
- Blocker: none

### M6.2 - Qualify every fighter and interaction classes
- Status: todo
- Depends: M4.3, M6.1
- Size: 8
- Requirement: FSD-010
- Evidence: none
- Acceptance: Every roster entry and declared high-risk interaction has gameplay/rewind/correction/performance evidence; failures visible.
- Owner: unassigned
- Next: Split by mechanics families and disjoint evidence ownership.
- Blocker: none

### M6.3 - Product qualification and release readiness
- Status: todo
- Depends: M5.3, M6.2, M0.5
- Size: 5
- Requirement: FSD-007, FSD-009, FSD-010, FSD-011
- Evidence: none
- Acceptance: Supported hardware/network/rules/roster claims match evidence; distribution policy resolved; review complete without automatic publication.
- Owner: unassigned
- Next: Prepare release candidate qualification; publication requires separate authorization.
- Blocker: none
