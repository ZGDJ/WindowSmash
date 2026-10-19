# Evidence: baseline architecture foundation

- Date / author: 2026-10-18 / root integration agent.
- Review: independent `hook_design` agent reviewed manifest and hook architecture; root owns acceptance.
- Tasks / requirements: M1.1, M1.3, FSD-001, FSD-011. Source-only evidence.
- Manifest implementation revision: `7cfb11744c1f1284fc0a6040d6af44ce0e79b4f6`.
- Environment: local Windows PowerShell, Python 3.12, disposable synthetic files and Git repository.
- Private prerequisites: no game modules, RomFS, fonts, runtime executable or Windows compiler available.

## Manifest verification

`python -m unittest discover -s tests -p test_baseline_manifest.py -v` passed 16/16 tests
(2.659 seconds, exit 0). Cases cover successful capture/verification, full module IDs including
trailing zero nibbles, content drift with preserved timestamps, missing required files, optional
inventory additions, malformed module/config/map/schema, source deletion/dirty/untracked files,
fixture/tape changes, non-overwriting output, and exclusion of external paths/config contents.
Linker changes, library-environment changes, missing linker and changes during a file read are
also covered. The synthetic executable/compiler/module files are intentionally not real binaries.

Independent review found missing required relocated startup images, a nine-source layered map
accepted beyond the runtime's eight-source limit, and a possible mixed module hash/header
observation across two reads. Those are fixed and covered by regressions. Compiler-only identity
also gained linker and library-environment identities. Initial file-change detection rejected
unchanged files because Windows Python 3.12 stat/fstat ctime differed; it now compares ctime only
within the same open descriptor and checks device/inode/size/mtime across descriptors.

`python -m unittest discover -s tests -v` passed all 67 source tests (8.743 seconds, exit 0).
`python tools/check_project_docs.py` and `git diff --check` passed (exit 0).

Real-checkout preflight (`python tools/baseline_manifest.py capture --manifest
artifacts/local/baseline-preflight-reviewed.json`) reported incomplete prerequisites with exit 2,
as expected. The
diagnostic is ignored/local and contains hashes/role names, no game bytes. No complete private
baseline or gameplay trial was produced. Raw synthetic fixtures are deleted by their tests;
sanitized outcomes are retained here.

M1.1 acceptance is satisfied for inventory tooling. The manifest documents its limits: observed
inventory is not build provenance or version authentication; capture requires stopped writers;
external SDK/system-library bytes are not exhaustively tracked; the path-sensitive compile
digest is not a cross-machine network compatibility identity. M1.2 remains blocked on private
inputs/toolchain and actual complete-match evidence.

## Required-hook verification

Implementation revision: `81efe6829dfc2895c34bd1de7a71169c4701902e`. The `hook_design`
agent implemented the guard; `build_cache_fix` independently reviewed the build/cache/link
paths and root reviewed the final diff and integration tests.

Critical hooks use adjacent source metadata with module name, full build ID, whole-file SHA-256
and a constrained signature. The build rejects missing/mismatched modules, malformed/orphan or
duplicate declarations, zero/multiple signature matches, and collisions involving a required
wrapper. The original-address fast path remains only for optional hooks. Required modules
regenerate C, relocated images and the worker scratch image; other modules keep normal caching.
The end-to-end Windows build passes its validation result directly to linking. Standalone link
cannot accept required declarations, and required originals receive no missing-hook fallback.

Review found an alternate route in `tools/linux/wintest.py`: it could link cached game objects
with newly compiled runtime hooks. Both that builder and the Linux builder now reject required
declarations before output/compiler work. Tests import their real entry points with a fake
toolchain and assert the early rejection. No native compiler is used in those tests.

Review also demonstrated a test gap: replacing real `build()` with a raising function did not
fail any of the original 19 hook tests because the build orchestration tests mocked generation.
The added real-`build()` regression retains actual identity checks, signature resolution and
scratch-image writing, with synthetic loading/emission. It checks successful worker forwarding
and rejects ambiguity before workers start. Two in-memory mutations confirm it fails if forced
scratch refresh is removed (one assertion failure) or resolution is removed (one missing-forward
error). Mutations were never written to repository files.

Final local `python -m unittest discover -s tests -v`: 87/87 pass in 8.800 seconds, exit 0,
including 16 manifest and 20 required-hook tests. `python -I tools/test_ssbu_relay.py -v`:
32/32 pass in 22.063 seconds, exit 0. `git diff --check`: pass, exit 0.

M1.3's tooling acceptance is satisfied. There are no production required-hook declarations;
an empty set does not validate any battle boundary. Concurrency is unsupported: checks detect
observed input drift, not transient replacement/reversion between reads or manual output edits.
Compiler execution, real hook installation, game semantics, performance and rollback are untested.
M2.1 must discover and qualify actual 13.0.5 hooks after M1.2's private baseline is available.
