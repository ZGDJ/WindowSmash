# ADR-0004: Input-driven local battle

Status: proposed; library/protocol/topology deferred. Date: 2026-10-18.

Context: inherited Local Wireless forwards session traffic, not a rollback interface.

Proposal: two logical inputs drive a local battle on each PC, coordinated by a separate rollback session. Reuse lobby concepts only where compatible; avoid competing battle synchronization systems.

Alternative: retaining Local Wireless battle progression requires reverse-engineering its delays/timeouts/state. Local mode instead requires two input lanes and reproducible initialization; its semantic equivalence needs proof.

Consequences: evaluate GGPO/other integration only after offline gates. A library cannot supply missing engine state/stepping. No transport dependency chosen by this proposal.

Promote after local two-input simulation, rewind/correction and performance pass, with [FSD-008](../docs/FSD.md) design. Reconsider if local mode changes gameplay or cannot be driven reproducibly.
