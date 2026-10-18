# GGPO contract and Smash rollback design

This is the design/acceptance companion to [FSD](FSD.md), not implemented functionality. [ADR-0006](../adr/0006-ggpo-contract-and-slippi-methods.md) accepts this interface direction; library adoption still needs a pinned build and working engine callbacks. Sources below were inspected on 2026-10-18. GGPO is the integration reference; Slippi is a source of methods, not a drop-in Ultimate backend.

## Frame and ownership contract

Project convention: `S[f]` is authoritative state immediately before consuming both players' input `I[f]`; `step(S[f], I[f]) = S[f+1]`. Document how the chosen GGPO revision numbers callbacks relative to this convention. Save an initial checkpoint before any speculative input. Correcting input at f restores S[f], then reruns every affected tick exactly once in order. Presentation count and fighter animation advancement are separate from this clock; hitlag/freeze does not imply a stopped network frame.

Checkpoint capture is at the proven quiescent boundary, not arbitrary native execution. Include authoritative input history, pending commands, simulation counters, RNG, allocation/object identity and native continuation invariants. Input records and confirmed-input receipt history used by the coordinator survive a simulation rewind. Never rewind sockets, acknowledgments or already-received corrected inputs with battle RAM.

Define three separate horizons: simulated state, latest actual input available for every player, and frames eligible for irreversible commit. Receipt/ACK alone does not prove corrected simulation has been rerun and validated. The implementation must define a conservative commit rule and how it obtains that signal; the public GGPO interface inspected does not expose a generic confirmed-frame getter. Do not invent one.

Checkpoint buffers remain immutable and valid until their owner releases them. Restoring cannot invalidate retained snapshots through aliasing. Define allocation failure, stale snapshot, double-free and session-close behavior. A K-tick correction horizon generally needs the current boundary plus K prior boundaries in a simple per-tick ring; derive exact retention from chosen frame convention, input delay and backend, and test oldest-boundary access. Never evict state still needed by an accepted correction.

## Implementation boundaries

Preserve the current C/HLE runtime. Establish a small offline engine interface for input, one tick, capture, restore and diagnostics before adding a session backend. The engine owns authoritative state; the coordinator owns input receipt/history, prediction and confirmation; host services own external effects. A checkpoint must not capture the coordinator or sockets. Keep device polling outside replay and effect policy outside the transport.

Do not choose a generic snapshot framework, replacement scheduler or transport abstraction ahead of measured failures. Begin with explicit state coverage and a simple bounded checkpoint ring once safe capture is demonstrated. Add selective copying or compression only after correctness and profiling justify them. One offline driver and the eventual network coordinator must use the same battle stepping path.

During M2 boundary discovery, trace `ipc_vi.c` buffer recycling/events, `ipc_audio.c` buffer release/events and `gpu.c` guest timestamp writes. Skipping display or muting audio must not prevent guest-visible completion or substitute wall-clock-dependent results during catch-up. Compare audio-device-present/absent and presentation-enabled/suppressed paths. Record service queues and completion state in the ownership inventory; avoid assuming they are cosmetic.

## GGPO adapter obligations

The pinned [public API](https://github.com/pond3r/ggpo/blob/7ddadef8546a7d99ff0b3530c6056bc8ee4b9c0a/src/include/ggponet.h) requires save/load/free and diagnostic callbacks plus one-frame advancement and event handling. Use `ggpo_synchronize_input` (singular in this header) for normal and replayed frames. Notify `ggpo_advance_frame` only after a successful tick. Replay uses historical synchronized input, not fresh device sampling or resubmission. Service `ggpo_idle`; respect synchronization/prediction errors. Handle time-sync and disconnect events without changing simulated tick duration. Frame delay and prediction horizon are distinct settings.

Use a deterministic, fixed-size input encoding with initialized bytes and explicit player mapping. Record startup configuration and seed/state agreement independently of network connection success. Avoid reentrant session calls from arbitrary workers; define one coordinator thread and callback ordering/ownership before implementation. These are project integration constraints, not claims that all runtime jobs must be serialized.

The [developer guide](https://github.com/pond3r/ggpo/blob/7ddadef8546a7d99ff0b3530c6056bc8ee4b9c0a/doc/DeveloperGuide.md) requires deterministic simulation, encapsulated state and simulation without rendering. Our GPU service may still need guest-visible work during a non-presenting tick; proving that separation is our responsibility.

Use forced offline restore/replay testing before networking. Once the library is integrated, exercise [GGPO's synctest backend](https://github.com/pond3r/ggpo/blob/7ddadef8546a7d99ff0b3530c6056bc8ee4b9c0a/src/lib/ggpo/backends/synctest.cpp) with deterministic checksums and readable state diffs. Also retain independent uninterrupted/all-correct oracles and upstream behavior comparisons: backend self-consistency cannot establish original gameplay accuracy. Synthetic adapter tests do not close actual-battle gates.

## Ultimate-specific fixture obligations

These are investigation/test categories, not assertions about undocumented Ultimate structures, addresses or exact sampling cadence. Pin all cases to 13.0.5 and record the discovered implementation.

- **Input history:** press/hold/release edges, buffered actions, analog transitions, player mappings and per-player profiles. Trace polling/consumption before assuming one sample suffices. If meaningful ordered subsamples exist, encode them; do not discard them to fit a preferred API. Store authoritative game-side previous input/buffer/counters in checkpoints. Test late corrections around hitlag and DI/SDI-sensitive sequences against gameplay outcomes, not only tape bytes.
- **Combat state:** shields/parries, hitlag/hitstun, launch/landing/tech/ledge transitions, grabs/throws and repeated-hit interactions. Discover authoritative counters, collision history, hit eligibility and motion/script state; do not snapshot only position/damage.
- **Object and fighter lifetimes:** corrections that create or prevent spawning, destroy/recreate objects, change ownership and alter future allocations. Include companions/multiple battle entities, transformations, resource meters, delayed actions and RNG-dependent mechanics wherever present in the selected roster. One-v-one means two players, not necessarily two authoritative objects.
- **Initialization:** preload/complete required modules/assets before a shared ready barrier, or make later authoritative loading deterministic. Pin fighter variants/Mii moves, stage forms, rules, control profiles and seeds; each player's chosen profile must be represented consistently on both peers, not necessarily identical to the other player's profile.
- **Match end:** incorrect last-stock KO corrected to survival, changed simultaneous-KO result, timeout/last-hit changes and disconnect while an outcome is speculative. Defer module/object teardown, results publication, saves and irreversible transitions until the causal frame is safely committed, or prove the transition is rewindable. Do not leave this gap under the phrase 'transitions outside rollback.'
- **Repeated correction:** multiple overlapping late inputs, repeated restores of one boundary, oldest retained checkpoint, rejected too-old corrections, and long-run resource growth. Preserve failing tapes and first divergent subsystem.

Select a small explicit mechanics fixture set before M4.1; exhaustive roster qualification remains M6.2. Every listed mechanic becomes a verified case or a documented not-applicable entry for that fixture. The full product still requires all roster entries and declared interaction classes.

## Effects, session boundaries and failure policy

Maintain an event policy for audio, rumble, camera/UI, file writes and network output: deferred, deduplicated, reconstructed or intentionally speculative. Audio already heard cannot be erased; document that artifact instead of promising impossible cancellation. Execute all gameplay-affecting work while suppressing intermediate presentation. Compare rendering-enabled and presentation-suppressed authoritative hashes, then separately inspect audiovisual behavior.

Agree initial state before advancing; build identity is insufficient. Match/session epochs reject late packets from a previous match, especially immediate rematches. Test initial-hash mismatch, old-epoch packets, temporary interruption, prediction cap, resume, disconnect and peer frame skew. Apply pacing outside simulation; no variable gameplay delta time to compensate for lag. A checksum mismatch must produce a bounded diagnostic failure, not silent continued 'healthy' play.

## What to learn from Slippi

The project's [component overview](https://github.com/project-slippi/slippi-wiki/blob/master/GETTING_STARTED.md) places rollback across game assembly modifications and emulator code. Our analogous division is battle hooks plus a host rollback coordinator. This supports targeted integration; it does not establish Ultimate feasibility.

The pinned [SlippiSavestate.cpp](https://github.com/project-slippi/Ishiiruka/blob/60f7b63496fb6ec7b9180a04f16f3edc0ad89fe2/Source/Core/Core/Slippi/SlippiSavestate.cpp) selects memory regions, computes heap bounds and preserves excluded blocks during restore. Learn the process of proving state coverage and optimizing only measured exclusions. Its active capture path should not be described as a generic complete Dolphin snapshot. Do not copy Melee addresses/exclusions into Ultimate or infer that audio is universally safe to omit. WindowSmash still needs its own native stack/fiber/service proof.

The pinned [SlippiNetplay.cpp](https://github.com/project-slippi/Ishiiruka/blob/60f7b63496fb6ec7b9180a04f16f3edc0ad89fe2/Source/Core/Core/Slippi/SlippiNetplay.cpp) handles frame-indexed input queues, acknowledgments and frame-associated checksums. The [EXI integration](https://github.com/project-slippi/Ishiiruka/blob/60f7b63496fb6ec7b9180a04f16f3edc0ad89fe2/Source/Core/Core/HW/EXI_DeviceSlippi.cpp) distinguishes finalized frames and stalls for unavailable input beyond a bounded window. Transfer the disciplines of bounded history, finalization and pacing; derive our limits experimentally. Do not copy Melee delay/window constants or its emulator timing.

These inspected components show a custom game/emulator integration; they are not evidence that Slippi is a GGPO drop-in or that its networking can be copied unchanged. GGPO callback conformance and Slippi-inspired engineering are separate ideas. No third-party code is copied or dependency added by this audit; check applicable licenses before any later reuse.
