# ADR-0002: Explicit continuation coverage

Status: accepted constraint; snapshot representation deferred. Date: 2026-10-18.

Context: native stacks/fibers, host thread/wait tables and setjmp/device state extend beyond guest RAM.

Decision: capture only at quiescent battle boundaries with documented invariants for every authoritative continuation. Inventory restored/reconstructible/excluded state. Compare replay with uninterrupted references. Do not discard GPU/event work merely because it looks graphical.

Alternatives: broad committed pages may help once host coverage is solved; selective serialization needs ownership knowledge; explicit resumable execution/deterministic scheduling is a fallback. No format selected yet.

Consequences: discovery gates implementation. Reconsider when changing worker/fiber state survives boundaries or services cannot be reconstructed; create a design ADR before altering execution semantics. See [FSD-002/005/006](../docs/FSD.md).
