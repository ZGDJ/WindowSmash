# ADR-0003: 13.0.5 and full roster from the start

Status: accepted by owner. Date: 2026-10-18.

Decision: all new game-backed work targets 13.0.5, not an initial 11.0.0 port. Pin runtime/compiler/module/content identities; critical hooks validate uniquely. Full roster including DLC/selected Mii configurations is mandatory.

A small 13.0.5 fixture discovers tick/restore behavior, then expands mechanics coverage. It does not reduce the product roster. Fixture and unresolved rules/hardware live in [FSD](../docs/FSD.md).

Alternative: upstream's primary 11.0.0 target might simplify initial setup but adds later migration. Owner chose version alignment immediately. Existing later-version tooling is not compatibility proof; missing 13.0.5 data/build/gameplay is a genuine gate.

Reconsider target only with owner direction. Refine fixtures with recorded rationale; never downgrade version/roster silently.
