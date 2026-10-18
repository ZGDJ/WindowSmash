# Evidence: baseline architecture foundation

- Date / author: 2026-10-18 / root integration agent.
- Review: independent `hook_design` agent reviewed manifest and hook architecture; root owns acceptance.
- Tasks / requirements: M1.1, FSD-001, FSD-011. Source-only evidence.
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
