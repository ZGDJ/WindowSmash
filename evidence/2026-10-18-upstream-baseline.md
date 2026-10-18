# Upstream source baseline

Date: 2026-10-18. Task: M0.2, supporting FSD-012; no gameplay requirement completed.

Source: clean `4b512d2ad44f2312d47d5ba5746f96a27eda3653`. Windows, Python 3.12.3, Windows PowerShell. No private game inputs/build. Independent runtime/rollback subagents reviewed source; primary agent reconciled findings.

`python -m unittest discover -s tests -v`: initial sandbox run had one temporary-file Move permission failure. Approved unrestricted rerun: 16 passed, exit 0.

`python -I tools/test_ssbu_relay.py -v`: sandbox run stalled and was interrupted. Approved loopback run: 27/28 passed, exit 1. `Listing.test_order_keeps_through_ping_jitter` swapped expected near-room order. Isolated command `python -I tools/test_ssbu_relay.py Listing.test_order_keeps_through_ping_jitter -v`: passed, exit 0. Root cause unresolved; M0.4 tracks it.

Raw output was observed in the originating session; no raw log committed. Commands are reproducible source checks. Current suite counts change with new tests.

Source audit: real AOT translation and useful HLE_WRAP seams; native continuations/service state outside RAM; live player-one input; wall-clock presentation; Local Wireless forwarding; no battle rollback coordinator found. [Source map](../docs/UPSTREAM.md).

No game build, 13.0.5 match, battle tick discovery, restoration, determinism or performance test was run. Upstream claims were not reproduced. Verdict: supports scoped investigation, not feasibility certification.
