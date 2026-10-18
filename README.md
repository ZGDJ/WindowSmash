# SmashRollback

A Windows x64 research fork of [WindowSmash](https://github.com/SNO2207/WindowSmash), targeting **Ultimate 13.0.5, the full fighter roster, and competitive 1v1 rollback battles with no items**.

**Rollback is not implemented or verified.** Retain the upstream AArch64-to-C recompilation and runtime; recover the simulation boundaries and state needed for deterministic replay. Full game decompilation is not a prerequisite. The first experiment uses a small fixture on 13.0.5; full-roster qualification remains a required product milestone.

## Start here

- [Milestones](milestones/README.md): the only task-status source of truth.
- [Functional specification](docs/FSD.md): requirements, acceptance gates and open choices.
- [Architecture decisions](adr/README.md): accepted, proposed and deferred decisions.
- [GGPO and Smash rollback contract](docs/ROLLBACK_DESIGN.md): callback responsibilities, Ultimate fixtures and transferable Slippi methods.
- [Agent instructions](AGENTS.md) and [workflow](docs/AGENT_WORKFLOW.md): autonomous execution and handoffs.
- [Validation](docs/VALIDATION.md) and [evidence](evidence/README.md): what has actually been demonstrated.
- [Upstream architecture/provenance](docs/UPSTREAM.md): inherited capabilities and limitations.

## First prove rewind

Run a pinned offline two-player battle from an input tape. Save at a safe simulation boundary, advance, restore, and replay. Authoritative state must match an uninterrupted reference every frame. Then verify corrected predictions, effect reconciliation and catch-up cost before integrating networking.

Guest RAM alone is insufficient: native threads, fibers and services retain other state. Rendering at 60 FPS does not prove sufficient resimulation headroom.

## Build and verify

Use the inherited [build](docs/BUILDING.md), [version](docs/VERSIONS.md) and [technical](docs/TECHNICAL.md) guides. Supply matching 13.0.5 inputs/fonts locally. No game data, keys, generated game code or personal saves belong in Git.

Source checks (Python 3.12+ for project checks; full build requirements differ):

```powershell
python tools/check_project_docs.py
python -m unittest discover -s tests -v
python -I tools/test_ssbu_relay.py -v
```

Relay tests need loopback UDP. These tests do not demonstrate gameplay or rollback.

The [source CI workflow](.github/workflows/source-checks.yml) runs the same checks on Windows with Python 3.12 and 3.14. See the [practical audit](evidence/2026-10-18-practical-audit.md) for repaired build/test gaps and the next implementation priorities.

## Provenance

Fork: [ZGDJ/WindowSmash](https://github.com/ZGDJ/WindowSmash). Baseline: `4b512d2ad44f2312d47d5ba5746f96a27eda3653`.

The [preserved upstream README](README-UPSTREAM.md) describes upstream releases/features, not this fork's rollback capability. Local Wireless transport is inherited experimental functionality. Preserve [notices and licensing status](NOTICE.md); this fork does not relicense upstream code.
