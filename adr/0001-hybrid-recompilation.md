# ADR-0001: Hybrid recompilation

Status: accepted direction; feasibility unproven. Date: 2026-10-18.

Context: upstream supplies execution/graphics/services, but no verified rewind boundary. Full decompilation broadens scope beyond battle systems.

Decision: retain recompiled behavior; recover battle stepping, input/state ownership and scheduling through HLE/HLE_WRAP instrumentation and selective replacement. Prove [offline gates](../docs/FSD.md) before networking.

Alternatives: full decomp improves source control but does not solve determinism automatically; whole-process snapshots still face host/device state; a rewritten battle engine needs much broader equivalence testing.

Consequences: saves platform work but still requires substantial reverse engineering. Reconsider if boundaries cannot be isolated, state remains unbounded or replay is unaffordable. Expand targeted reconstruction from failing evidence, not automatically into full decomp.
