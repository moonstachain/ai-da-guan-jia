# Claude Code Workflow Bridge

This bridge is the canonical entrypoint for treating `moonstachain/claude-code` as a benchmarkable porting workspace inside AI大管家.

## Canonical stance

- Treat the repo as a Python-first porting workspace and capability index, not as a finished runtime.
- Use `evaluate-external-skill` with `runtime_target=multi_harness` when reviewing this repo as an external asset.
- Absorb only the layers that improve governance, routing, task closure, and bridge discipline.
- Keep UI-heavy and runtime-heavy surfaces outside the first integration wave.

## Deep integration order

1. `skills / routing / review`
2. `task / session / memory / evolution`
3. `agents / worktree / remote / mcp / plugin`
4. `review / security / cost / parity`
5. `components / utils / screens` only after the layers above stabilize

## Absorb now

- `main.py` entrypoints that expose manifest, summary, route, and per-entry views
- `runtime.py` routing behavior as a benchmark for prompt-to-target mapping
- `tasks.py`, `context.py`, and `cost_tracker.py` as task, context, and budget scaffolding
- `parity_audit.py` as a proof-bearing verification gate

## Keep benchmark-only for now

- Token-overlap routing
- Manifest/report generation
- Parity measurement against the archived snapshot

## Linked artifacts

- [Deep integration report](../docs/moonstachain-claude-code-deep-integration-report-v1.md)
- [`evaluate-external-skill`](../work/ai-da-guan-jia/SKILL.md)
- [External skill absorption matrix](../docs/ai-da-guan-jia-external-skill-absorption-matrix-v1.md)
