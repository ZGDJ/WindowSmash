# Autonomous work and Astra sizing

Start with [AGENTS.md](../AGENTS.md) and [ledger](../milestones/README.md); load only relevant requirements, ADRs and source. These conventions serve GPT-6 Astra and other agents; they do not configure an API/model.

## Work loop

1. Inspect the worktree; select unclaimed dependency-ready work. Independent source tasks can proceed around private-data blockers.
2. Claim with owner/session and UTC timestamp; set `in_progress` and next action. Claims coordinate, not lock. Coordinate before taking active/stale claims.
3. Define a falsifiable investigation or cohesive implementation. Investigate unknown ownership before coding assumptions.
4. Implement, run affected checks, inspect the diff, record evidence. Fix introduced regressions; keep baseline failures visible.
5. Independently review high-risk continuation/state/scheduling work.
6. Done requires acceptance evidence and completed dependencies. Negative research can finish an investigation, not a capability gate: create remediation and rewire dependencies.
7. Continue authorized work or hand off exact blockers. Do not spin or invent recurring schedules.

## Packet template

```text
Task/outcome: Mx.y / one sentence
Context: requirement, ADR, source symbols, relevant prior evidence
Ownership: exact files/subsystem; other active writers
Non-goals: deferred scope
Approach: bounded experiment/implementation
Acceptance: observable result + command/manual procedure
Artifacts: code/tests + evidence + ledger update
Split/stop: missing prerequisite, architecture decision, excessive scope
Handoff: results, uncertainty, next action
```

## Keep changes readable and removable

- Use the [source map](UPSTREAM.md#source-seams) to find existing owners before adding a file or abstraction. Keep one owner for each fact, state buffer and clock.
- Keep new battle hooks thin. Put checkpoint policy and session coordination behind the proven battle boundary; do not spread networking decisions through HLE services or generated game code.
- Prefer a concrete function or module over a plugin system, generic scheduler or configuration layer. Extract shared code only when actual callers need the same contract.
- For a new subsystem, document its inputs, outputs, state owner, cleanup and failure behavior next to the interface. Explain invariants and reasons; avoid comments that narrate the code.
- Keep experiments in a removable module or tool with explicit entry/exit points. A local revert must restore the previous path without a data migration; test the disabled path when introducing runtime integration. Do not add dormant rollback hooks before the boundary is known.
- Avoid bulk renames, formatting and source moves in behavioral fixes. Preserve upstream comparability and keep tests with the behavior they protect.

## Calculate scope without false precision

Use 1/2/3/5/8 relative effort units: 1 bounded source check/change; 2–3 focused subsystem; 5 substantial research/integration; 8 high uncertainty requiring decomposition before implementation. These are not hours, tokens or model calls. Discovery may expand scope.

When splitting a coarse task, replace its entry with new uniquely numbered child tasks and rewire every downstream dependency to the required children. Retire the parent ID in the evidence/handoff with its old scope and replacement IDs; do not reuse it. Do not count parent effort alongside children. Preserve completed task history and never renumber unrelated work.

`python tools/check_project_docs.py` computes counts, effort and ready work. Weighted closed scope is `done effort / total effort`, not probability of success or a schedule. Critical research gates matter more than percentages. Explain re-estimation in evidence.

Use Astra for difficult state ownership, determinism and architecture; keep routine packets compact. Use the configured model unless explicitly changed. Parallelize disjoint investigations, avoid duplicate writers and whole-repo rereads. Repeat passing suites only for new risk.

Record actual model/effort, elapsed time and token usage only when tools expose them; unknown stays unknown. Forecast from measured comparable packets. If applicable, API token cost is `(uncached input * input rate + cached input * cache rate + output * output rate) / 1,000,000`, plus applicable tool/cache-write costs. Verify current rates/surface first; effort units do not predict spend. No paid API budget is authorized.

This approach follows [official Astra guidance](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra), consulted 2026-10-18: concise reusable context, useful boundaries, and avoiding redundant work. Task sizes are project conventions, not vendor guarantees.

## Authorization

Owner permits implementation, tests, commits, pushes to the fork and draft PRs. Merges/releases/paid resources/destructive history stay explicit. Verify PR base/remotes; do not target upstream accidentally. Put durable findings in evidence/ledger, not duplicate transcripts. This workflow does not schedule continuous execution.
