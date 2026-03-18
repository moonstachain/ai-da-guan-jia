# Strategic Governor Contract

Use `strategy-governor` to maintain the strategic operating system for AI大管家.

## Purpose

Turn the skill universe from a loose toolbox into a governed system with:

- strategic goals
- theme registry
- strategy registry
- experiment registry
- workflow registry
- canonical thread remap registry
- initiative registry
- active thread tracking
- skill gap reporting
- recruitment candidates
- agent scorecards

## Canonical Location

Write the current strategic state under:

`artifacts/ai-da-guan-jia/strategy/current/`

## Required Files

- `strategic-goals.json`
- `strategy-map.json`
- `theme-registry.json`
- `strategy-registry.json`
- `experiment-registry.json`
- `workflow-registry.json`
- `canonical-thread-registry.json`
- `initiative-registry.json`
- `active-threads.json`
- `initiative-brief.json`
- `thread-proposal.json`
- `skill-gap-report.json`
- `recruitment-candidate.json`
- `agent-scorecard.json`
- `clone-scorecard.json`
- `routing-credit.json`
- `autonomy-tier.json`
- `cbm-mapping-view.json`
- `cbm-mapping-view.md`
- `governance-dashboard.md`
- `org-taxonomy.md`
- `governance-penalty-rules.md`
- `promotion-demotion-policy.md`
- `strategic-proposal.md`

## Rule

Default autonomy level is `建议 + 待批`.

The strategic layer may propose new threads, initiatives, and skill recruitment, but must not silently execute high-impact expansion work.

The strategic layer must now maintain a dual-axis view:

- `goal_id` tracks governance alignment
- `theme / strategy / experiment / workflow` track production position

Specific enforcement:

- `theme-registry.json` only keeps the fixed v1 seed themes
- `theme-human-ai-coevolution` is the only `active` theme in this phase
- the current operating program may apply a `frontstage focus override` without changing the registry-active theme
- `canonical-thread-registry.json` is the runtime answer for `canonical_thread -> disposition -> goal_id -> theme_id -> strategy_slot -> experiment_slot -> next_blocker`
- allowed dispositions are `frontstage_now`, `background_merge_queue`, `waiting_human_boundary`, `deferred_after_narrowing`, and `candidate_pool`
- the governance frontstage cap is `3`, and the benchmark thread stays outside the working load
- `experiment` is the mandatory MVP bridge object between strategy and workflow
- `workflow-registry.json` may only contain rows whose linked strategy is already `validated`
- governance mainline closure strategies stay frozen at `strategy + experiment + verdict` in this phase; they do not emit workflows yet
- `cbm-mapping-view.json` must stay read-only and explain how IBM-style `component_domain x control_level` has been rewritten into the current `goal_id + theme/strategy/experiment/workflow + operational ontology` stack
- `cbm-mapping-view.md` must name both absorbed structure and still-missing runtime bindings; do not claim full CBM adoption when `execute` rows still lack action/writeback coverage

It must also consume the clone factory artifacts from `artifacts/ai-da-guan-jia/clones/current/` and surface clone portfolio status inside the governance dashboard.
