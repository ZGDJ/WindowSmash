# Practical architecture and testing audit

- Date / authors: 2026-10-18; root integration, runtime_audit, relay_reliability and build_cache_fix sessions.
- Reviewer: root reviewed all changes; relay_reliability independently challenged build-cache implementation and tests.
- Tasks: M0.4, M0.5, M0.7, M1.4. Requirements: FSD-001, FSD-002, FSD-005, FSD-011, FSD-012, FSD-013.
- Level: source-only. No private game inputs, native game compilation, emulator comparison or battle execution.
- Base revision: `5e9d9cc`. Tested implementation: relay `57e7b98`, differential safeguards `596b94c`, build cache `058dd84`. Planning/CI changes are recorded in the subsequent commits on this branch.
- Local environment: Windows x64, Python 3.12.3, Windows PowerShell available. Model token/effort accounting unavailable.

## Decisions and changes

Keep the inherited C/HLE architecture and existing roadmap. Its checkpoint, native continuation,
input-history, behavioral-reference and terminal-confirmation gates already address the main
rollback risks. A scheduler rewrite, generic snapshot framework or new transport layer is not
justified before an actual battle boundary has been demonstrated.

The actionable gaps were reliability of the build/test evidence and concrete service probes:

1. **Stale Windows objects.** `recomp.compile_dir` only compared generated C/object mtimes;
   generated runtime tables also missed header changes. The generation fingerprint did not
   identify compiled-object inputs. `cc.compile_cached` now tracks source/header contents,
   compiler identity, flags, per-source optimization and relevant environment separately.
   Failed batches leave no valid compile stamp; adopted hardlinks are unlinked before writing.
   M1.2 now depends on this source-level repair, M1.4.
2. **Relay ordering ties.** Windows Python 3.12.3's monotonic clock reported `GetTickCount64()`
   with 0.015625-second resolution. Distinct adverts could share creation timestamps, leaving
   stable sorting dependent on unordered set iteration. Partition room dictionaries preserve
   insertion order for ties; refreshing a room preserves its place and reopening moves it last.
   No transport format changes, sleeps, retries or skipped tests were added.
3. **Empty differential success.** Both comparison tools could exit successfully with zero
   completed comparisons. Positive execution counts are validated before input loading; empty
   selections and all-skipped comparisons return exit 2 / INCONCLUSIVE. Nonempty results retain
   pass/mismatch exits 0/1. This is a minimum safeguard, not fixture coverage certification.
4. **Missing CI.** The Windows workflow runs documentation checks, all source unit tests and
   loopback relay tests with Python 3.12 and 3.14. It uses pinned actions, read-only repository
   permission, bounded duration and no private runner/data. Failures remain failures; independent
   later checks still run. [GitHub's Python workflow guidance](https://docs.github.com/en/actions/tutorials/build-and-test-code/python)
   informed the workflow; action commit pins were resolved from the official repositories.
5. **Concrete replay hazards.** `runtime/ipc_vi.c` releases display buffers/signals events from
   its vsync worker; `runtime/ipc_audio.c` reports buffer completion after device playback;
   `runtime/gpu.c` writes host-time-derived timestamps into guest memory. The design and M2 gates
   now explicitly trace these paths during suppressed presentation and audio-device variations.
   Source inspection establishes the paths, not their effect on an actual battle.

The existing agent workflow now states ownership, cleanup and erasability rules without adding
another architecture document. Thin hooks, one battle-stepping path, and local removable
experiments keep future changes reviewable. The build guide's conflicting 11.0.0 input row now
matches the established 13.0.5 target. Status stays exclusively in the milestone ledger.

## Reproduction and validation

Before changes, all 32 source unit tests passed. The relay investigation ran the original
ordering test 30 times: 13 failures; all 64 observed list responses had tied creation timestamps.
The new fixed-time regression failed against the original relay (exit 1).

After the relay repair, 30 original loopback cases plus 30 fixed-time regressions passed (60/60,
exit 0); `python -I tools/test_ssbu_relay.py -v` passed all 29 tests in 22.103 seconds. Repeat with:

```powershell
@'
import sys, unittest
sys.path.insert(0, 'tools')
import test_ssbu_relay as T
suite = unittest.TestSuite()
for _ in range(30):
    suite.addTest(T.Listing('test_order_keeps_through_ping_jitter'))
    suite.addTest(T.ListingOrder('test_equal_timestamps_keep_advertisement_order'))
result = unittest.TextTestRunner().run(suite)
sys.exit(not result.wasSuccessful())
'@ | python -I -
```

The first integrated `python -m unittest discover -s tests -v` run passed 51 tests (6.090 seconds,
exit 0). Independent review then deliberately replaced compile identity with a constant and
found four invalidation tests still passed: their assertions could read a previous compile call.
This was a test defect, not evidence that cache invalidation was verified. Fresh call assertions
now clear the recorded calls before each expected rebuild. After that correction, five focused
header/compiler/environment/flags tests all fail against constant compile identity (5 failures,
zero errors), and all 12 build-cache tests pass against the actual implementation. The mutation
is in-memory only and was not committed. The experiment also exposed a test boolean shadowing
`unittest.TestCase.fail`; it was renamed so failed assertions report correctly.

Final integrated `python -m unittest discover -s tests -v`: 51/51 pass in 6.147 seconds, exit 0.
`python tools/check_project_docs.py`: pass, exit 0. `git diff --check`: pass, exit 0.
Hosted CI remains to be observed before closing M0.5.

## Limits and handoff

External SDK/codec headers replaced in place still need an isolated fresh build without donor
trees. Standalone `recomp.py link` expects compiled module directories; use `all` or run `compile`
first. Compiler digest memoization assumes executable stat fields are not all preserved across
a binary replacement. Concurrent writers to one build folder are unsupported. Linux's separate
build path is unchanged and not certified by this Windows work. Source hash scanning cost on a
full generated tree is unmeasured.

Test fixtures are disposable; console output was reviewed, with sanitized outcomes retained here.
No private traces or game artifacts were produced. CI green proves the jobs run, not translation
correctness, 13.0.5 gameplay, deterministic replay, rollback or performance.

Next implement M1.1's input/build manifest, then validate critical hooks and obtain the private
13.0.5 baseline for M1.2. Split the high-uncertainty M2.1 investigation before implementation.
Keep full-roster qualification and GGPO adoption behind the existing actual-battle gates.
