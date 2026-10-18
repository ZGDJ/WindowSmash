# Functional specification: SmashRollback

Revision: 2026-10-18. Requirements live here; [milestones](../milestones/README.md) own status and [ADRs](../adr/README.md) own decisions.

The [GGPO/Smash design contract](ROLLBACK_DESIGN.md) defines frame conventions, adapter ownership, confirmation and primary-source Slippi learnings. It is required design context for FSD-002 through FSD-010 and FSD-014/015.

## Vision and fixture

Preserve Ultimate battle behavior on Windows x64 with competitive 1v1 rollback. **13.0.5 and the full roster are the target from the start.** Keep recompiled logic and recover interfaces/state needed to control it. A frame means an authoritative simulation tick, not a presented buffer. A checkpoint must reproduce future authoritative behavior.

Provisional experiment: 13.0.5 Mario mirror, Final Destination, three stocks, seven minutes, hazards/stage morph/spirits/Final Smash meter off, normal launch rate, no items or CPU. This is a test fixture, not a universal tournament ruleset or roster limit. Add object-heavy fighters before closing rewind coverage; qualify DLC and selected Mii configurations explicitly.

Open choices: available private inputs; final stage/rules list and Mii settings; minimum hardware; acceptable input delay/window/network envelope. Source-only work can proceed; mock gameplay cannot replace missing private inputs.

## Requirements

### FSD-001 - Reproducible baseline

Record source/diff identity, executable/toolchain/config hashes, module/content identifiers, fixture and tape. Acceptance: reproducible 13.0.5 build and three consecutive scripted offline matches including KO, respawn and return to menu. Tooling can precede private inputs; gameplay acceptance cannot be waived.

### FSD-002 - Simulation stepping and safe boundary

Advance one battle tick, then quiesce authoritative jobs; document native thread/fiber continuation invariants. Initially keep loading/match transitions outside the rewind window. Acceptance: 600 commanded ticks produce 600 simulation steps independently of rendering cadence, with no outstanding authoritative mutation at capture. A present counter is not a tick oracle.

Keeping transitions outside the window requires FSD-015's confirmation barrier; it does not permit speculative teardown. Tick/input semantics must remain correct across hitlag/freeze/slowdown, independently of visible animation.

### FSD-003 - Two frame-indexed input lanes

Version both players' buttons/sticks/sampling metadata and profile mapping. Discover the meaningful polling/consumption cadence before enforcing one sample per tick; preserve ordered subsamples if needed. Never poll live devices during historical replay. Acceptance: independent player control, correct press/hold/release/buffered-input history, and gameplay outcomes invariant under host input changes/display cadence, including corrections around hitlag and DI/SDI-sensitive fixtures. Checkpoint game-side input history/counters as authoritative state.

### FSD-004 - Deterministic forward replay

Investigate time, RNG, scheduling, FP and loading. Acceptance: two 10,000-tick replays from identical state/inputs agree every tick, first locally then in separate processes. Cross-machine qualification is FSD-009. Justify hash exclusions and pointer normalization; pixels are not the authoritative oracle. Preserve first-divergence reports. This sample does not prove all gameplay.

### FSD-005 - Complete checkpoints

Inventory guest memory, allocators, scripts, fighters/articles, stage, RNG, queues, clocks/jobs, native stacks/fibers/handles, GPU writes and audio. Classify each as restored, reconstructible or excluded with evidence. Acceptance: save/advance/restore/replay equals an uninterrupted oracle at depths 1/2/4/8 for at least 100 boundaries each, covering attacks, grabs, hitstop, projectiles, allocation churn and KO/respawn. Include object-heavy fixtures. Prove native continuation coverage; heap-plus-Cpu is not presumed sufficient.

Include speculative spawn prevented by correction and absent spawn created by correction, destruction/recreation/ownership changes, future allocation identities and RNG advancement. Test companions/multiple entities and relevant transformation/resource mechanics through named fixtures. Coordinator receive/ACK/input history survives restoration; do not rewind it with simulation state.

### FSD-006 - Prediction correction and effects

Correct deliberately wrong remote inputs after 1/2/4/8 ticks. Acceptance: match an all-correct reference at every corrected boundary; no duplicate gameplay/audio events, speculative save/network writes, stale resources or deadlocks. Suppress intermediate presentation while retaining needed GPU writes/events. Event logs and documented audiovisual inspection prove different aspects.

Test overlapping corrections, repeated restores and oldest retained state with bounded resource growth. Compare presentation-enabled and suppressed authoritative hashes. Specify effect deferral/deduplication/reconstruction and permitted speculative artifacts: sound already heard cannot be undone. No replay-induced duplicate effects is a requirement; impossible erasure is not.

### FSD-007 - Performance and memory

Measure checkpoint size, capture/restore, simulation, presentation, p95/p99 catch-up and peak memory. Target 60 Hz (~16.67 ms/display interval). Acceptance: agreed hardware floor/window and declared budget met in heavy scenes. Eight-tick correctness tests do not promise an eight-tick performance envelope. Unresolved hardware/window blocks release. No FPS-only acceptance.

### FSD-008 - Versioned rollback session

After offline gates, add frame-numbered inputs, prediction caps, delay, acknowledgments/redundancy, bounded history, validation/checksums and disconnects. Handshake compares runtime/executable/module/content/rules/input-schema identities, not just main build ID. Acceptance: incompatible peers reject before battle; confirmed state matches the offline oracle; missing input causes bounded stall/abort. Library/topology remain undecided.

Use the GGPO reference contract rather than duplicating a selected library's transport. Agree seeded initial battle state and readiness, explicit slot/profile mapping and a match epoch. Test old-epoch packets during rematch, initial-hash mismatch, time-sync/frame skew, interruption/resume and disconnect during speculative end. Pacing must not change gameplay tick duration. Obtain a valid confirmation horizon through the chosen adapter; connection success or receipt ACK is insufficient. Desync causes a bounded diagnostic failure.

### FSD-009 - Impairments and cross-machine proof

Reproduce delay, jitter, loss, duplication, reordering and bursts. Initial test cases: RTT 0/50/100/150 ms, jitter 0/10/30 ms, loss 0/1/3 percent; these are tests, not support promises. Acceptance: declared pairwise cases across two machines maintain confirmed-state agreement and latency/disconnect policy. Preserve failing seeds; qualify CPU/GPU/compiler differences explicitly.

### FSD-010 - Full-roster competitive coverage

Enumerate 13.0.5 fighters including DLC/selected Mii configurations and version rules/stage coverage. Acceptance: every fighter has representative mechanics, gameplay, rewind/correction and performance evidence; define pairwise/high-risk interactions without claiming every matchup from one test per fighter. Track untested/failed/verified. Full-roster milestone stays open until every entry qualifies. No items does not remove fighter-created objects/RNG.

Select explicit early input-history, combat, lifecycle/RNG and terminal-event fixtures before the first rewind gate; see design contract. Mark non-applicable mechanics with reasons. Preload required modules/assets before ready or prove deterministic later loading. Full-roster coverage remains distinct from the initial fixture set.

### FSD-011 - Hooks and safe artifacts

Critical hooks uniquely match pinned module identity or disable rollback with an actionable error. Acceptance: missing/ambiguous/changed-signature negative tests; source CI requires no private data; evidence sanitized. Preserve notices and resolve distribution policy before release. No generated game code or dumps in Git.

### FSD-012 - Verifiable autonomy

One ledger, dependency gates, bounded packets and evidence-backed status. Acceptance: new agents identify ready work, run checks and leave reproducible handoffs. Validator rejects invalid task/dependency/status/evidence references; it cannot certify gameplay truth. Independently review high-risk state/scheduling work.

### FSD-013 - Preserve battle behavior

Self-consistent replay can still reproduce an incorrect simulation. For changes affecting battle semantics, compare representative mechanics/outcomes with the pinned upstream 13.0.5 recompilation wherever practical, using identical conditions and documenting instrumentation/input differences. Acceptance: named behavioral cases and reference outputs, no unexplained changes in damage/timing/movement/collision outcomes, and explicit limitations for unavailable comparisons. Unresolved unexplained changes block qualification. This does not assert equivalence to console hardware; upstream bugs remain separately identifiable.

### FSD-014 - GGPO adapter and forced replay diagnostics

Define before-input checkpoint numbering, save/load/free/log/step/event ownership, immutable buffer lifetime, coordinator-thread/reentrancy rules and fixed deterministic input encoding. Acceptance: boundary/ownership tests cover initial state, retained buffer aliases, allocation failure, oldest checkpoint and session cleanup; actual battle forced restore/replay uses the same stepping interface. On GGPO adoption, run its synctest backend and verify failed synchronization/prediction does not advance simulation or resubmit fresh input during replay. Record exact dependency revision; synthetic callbacks do not certify battle correctness.

### FSD-015 - Confirmation-safe lifecycle

Speculative last-stock KO, simultaneous lethal outcomes and timeout/last-hit changes must remain correctable. Defer teardown/results/save/module unload until causal inputs have been corrected and the outcome is committed, or prove all transition state rewindable. Acceptance: offline late-input tests reverse apparent terminal outcomes, preserve required state/resources and commit exactly once; networking subsequently tests disconnect and immediate rematch/old epoch. A fabricated offline confirmation schedule tests the barrier but does not prove the network confirmation signal.

## Non-goals and decision gates

Initial exclusions: full source recovery, Nintendo online interoperability, ranked/public services, anti-cheat, spectators, four players, items, arbitrary versions, Linux rollback and game-content distribution. Preserve inherited features without expanding acceptance scope.

If FSD-002 through FSD-006 cannot pass, broaden targeted decompilation or restructure continuations through an ADR. Profile before revising performance scope; never weaken correctness criteria merely to close milestones.
