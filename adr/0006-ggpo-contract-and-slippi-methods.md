# ADR-0006: GGPO-shaped engine contract and Slippi methods

Status: accepted interface/research direction; library adoption deferred. Date: 2026-10-18.

Context: the initial plan captured generic rewind requirements but lacked precise input/state ownership, confirmation/transition rules and Smash-specific correction cases. Slippi provides useful game-specific patterns, not portable Ultimate memory layouts.

Decision: make the engine adapter GGPO-compatible in responsibilities (save/load/free/log/step/events) and validate it offline before networking. Adopt the [rollback design contract](../docs/ROLLBACK_DESIGN.md), including before-input checkpoints, persistent coordinator history, confirmation barriers, explicit input-history/fixture coverage and forced replay diagnostics. GGPO is the primary library candidate/reference; pin and prove the actual integration in M5.1/M5.2. Do not invent a confirmed-frame API or assume a successful connection agrees battle state.

Alternative: invent a custom protocol/state interface first. Rejected as the default because it adds uncertainty before the engine boundary works. A different backend needs a documented reason and equivalent contract tests. Slippi's own game/runtime design is a methodological reference, not proof that it uses the GGPO API or supports this runtime.

Consequences: two new offline gates cover adapter ownership and speculative lifecycle/confirmation. Early mechanics fixtures precede rewind; full roster remains later qualification. Do not duplicate networking machinery already provided by the chosen library. No library is installed or code copied in this decision.

Reconsider if native continuations cannot meet the contract or the selected library cannot expose the state/progress needed for safe confirmation. Preserve correctness while documenting an adapter extension or alternate backend.
