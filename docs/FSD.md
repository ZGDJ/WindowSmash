# Functional specification: SmashRollback

Revision: 2026-10-18. Requirements live here; [milestones](../milestones/README.md) own status and [ADRs](../adr/README.md) own decisions.

## Vision and fixture

Preserve Ultimate battle behavior on Windows x64 with competitive 1v1 rollback. **13.0.5 and the full roster are the target from the start.** Keep recompiled logic and recover interfaces/state needed to control it. A frame means an authoritative simulation tick, not a presented buffer. A checkpoint must reproduce future authoritative behavior.

Provisional experiment: 13.0.5 Mario mirror, Final Destination, three stocks, seven minutes, hazards/stage morph/spirits/Final Smash meter off, normal launch rate, no items or CPU. This is a test fixture, not a universal tournament ruleset or roster limit. Add object-heavy fighters before closing rewind coverage; qualify DLC and selected Mii configurations explicitly.

Open choices: available private inputs; final stage/rules list and Mii settings; minimum hardware; acceptable input delay/window/network envelope. Source-only work can proceed; mock gameplay cannot replace missing private inputs.

## Requirements

### FSD-001 - Reproducible baseline

Record source/diff identity, executable/toolchain/config hashes, module/content identifiers, fixture and tape. Acceptance: reproducible 13.0.5 build and three consecutive scripted offline matches including KO, respawn and return to menu. Tooling can precede private inputs; gameplay acceptance cannot be waived.

### FSD-002 - Simulation stepping and safe boundary

Advance one battle tick, then quiesce authoritative jobs; document native thread/fiber continuation invariants. Initially keep loading/match transitions outside the rewind window. Acceptance: 600 commanded ticks produce 600 simulation steps independently of rendering cadence, with no outstanding authoritative mutation at capture. A present counter is not a tick oracle.

### FSD-003 - Two frame-indexed input lanes

Version both players' buttons/sticks/sampling metadata. Poll devices once at the chosen boundary, never during historical replay. Acceptance: independent player control, stable repeated reads per tick, and replay invariant under host input changes/display cadence.

### FSD-004 - Deterministic forward replay

Investigate time, RNG, scheduling, FP and loading. Acceptance: two 10,000-tick replays from identical state/inputs agree every tick, first locally then in separate processes. Cross-machine qualification is FSD-009. Justify hash exclusions and pointer normalization; pixels are not the authoritative oracle. Preserve first-divergence reports. This sample does not prove all gameplay.

### FSD-005 - Complete checkpoints

Inventory guest memory, allocators, scripts, fighters/articles, stage, RNG, queues, clocks/jobs, native stacks/fibers/handles, GPU writes and audio. Classify each as restored, reconstructible or excluded with evidence. Acceptance: save/advance/restore/replay equals an uninterrupted oracle at depths 1/2/4/8 for at least 100 boundaries each, covering attacks, grabs, hitstop, projectiles, allocation churn and KO/respawn. Include object-heavy fixtures. Prove native continuation coverage; heap-plus-Cpu is not presumed sufficient.

### FSD-006 - Prediction correction and effects

Correct deliberately wrong remote inputs after 1/2/4/8 ticks. Acceptance: match an all-correct reference at every corrected boundary; no duplicate gameplay/audio events, speculative save/network writes, stale resources or deadlocks. Suppress intermediate presentation while retaining needed GPU writes/events. Event logs and documented audiovisual inspection prove different aspects.

### FSD-007 - Performance and memory

Measure checkpoint size, capture/restore, simulation, presentation, p95/p99 catch-up and peak memory. Target 60 Hz (~16.67 ms/display interval). Acceptance: agreed hardware floor/window and declared budget met in heavy scenes. Eight-tick correctness tests do not promise an eight-tick performance envelope. Unresolved hardware/window blocks release. No FPS-only acceptance.

### FSD-008 - Versioned rollback session

After offline gates, add frame-numbered inputs, prediction caps, delay, acknowledgments/redundancy, bounded history, validation/checksums and disconnects. Handshake compares runtime/executable/module/content/rules/input-schema identities, not just main build ID. Acceptance: incompatible peers reject before battle; confirmed state matches the offline oracle; missing input causes bounded stall/abort. Library/topology remain undecided.

### FSD-009 - Impairments and cross-machine proof

Reproduce delay, jitter, loss, duplication, reordering and bursts. Initial test cases: RTT 0/50/100/150 ms, jitter 0/10/30 ms, loss 0/1/3 percent; these are tests, not support promises. Acceptance: declared pairwise cases across two machines maintain confirmed-state agreement and latency/disconnect policy. Preserve failing seeds; qualify CPU/GPU/compiler differences explicitly.

### FSD-010 - Full-roster competitive coverage

Enumerate 13.0.5 fighters including DLC/selected Mii configurations and version rules/stage coverage. Acceptance: every fighter has representative mechanics, gameplay, rewind/correction and performance evidence; define pairwise/high-risk interactions without claiming every matchup from one test per fighter. Track untested/failed/verified. Full-roster milestone stays open until every entry qualifies. No items does not remove fighter-created objects/RNG.

### FSD-011 - Hooks and safe artifacts

Critical hooks uniquely match pinned module identity or disable rollback with an actionable error. Acceptance: missing/ambiguous/changed-signature negative tests; source CI requires no private data; evidence sanitized. Preserve notices and resolve distribution policy before release. No generated game code or dumps in Git.

### FSD-012 - Verifiable autonomy

One ledger, dependency gates, bounded packets and evidence-backed status. Acceptance: new agents identify ready work, run checks and leave reproducible handoffs. Validator rejects invalid task/dependency/status/evidence references; it cannot certify gameplay truth. Independently review high-risk state/scheduling work.

### FSD-013 - Preserve battle behavior

Self-consistent replay can still reproduce an incorrect simulation. For changes affecting battle semantics, compare representative mechanics/outcomes with the pinned upstream 13.0.5 recompilation wherever practical, using identical conditions and documenting instrumentation/input differences. Acceptance: named behavioral cases and reference outputs, no unexplained changes in damage/timing/movement/collision outcomes, and explicit limitations for unavailable comparisons. Unresolved unexplained changes block qualification. This does not assert equivalence to console hardware; upstream bugs remain separately identifiable.

## Non-goals and decision gates

Initial exclusions: full source recovery, Nintendo online interoperability, ranked/public services, anti-cheat, spectators, four players, items, arbitrary versions, Linux rollback and game-content distribution. Preserve inherited features without expanding acceptance scope.

If FSD-002 through FSD-006 cannot pass, broaden targeted decompilation or restructure continuations through an ADR. Profile before revising performance scope; never weaken correctness criteria merely to close milestones.
