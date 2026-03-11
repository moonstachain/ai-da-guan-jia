# Strategic Governor Contract

Use `strategy-governor` to maintain the strategic operating system for AI大管家.

## Purpose

Turn the skill universe from a loose toolbox into a governed system with:

- strategic goals
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
- `initiative-registry.json`
- `active-threads.json`
- `initiative-brief.json`
- `thread-proposal.json`
- `skill-gap-report.json`
- `recruitment-candidate.json`
- `agent-scorecard.json`
- `budget-profile.json`
- `chain-scorecard.json`
- `object-scorecard.json`
- `routing-credit.json`
- `autonomy-tier.json`
- `budget-ledger.json`
- `incentive-decision.json`
- `governance-dashboard.md`
- `org-taxonomy.md`
- `governance-penalty-rules.md`
- `promotion-demotion-policy.md`
- `strategic-proposal.md`

## Rule

Default autonomy level is `建议 + 待批`.

The strategic layer may propose new threads, initiatives, and skill recruitment, but must not silently execute high-impact expansion work.

## Governance Notes

- `execution_chain` is the default primary evaluation target.
- `agent-scorecard.json` remains the skill-facing substrate, but `chain-scorecard.json` is the first-class full-task ledger.
- `budget-profile.json` defines the task budget tiers; `budget-ledger.json` records budget outcomes over recent runs.
- `incentive-decision.json` records the final lever decision across `调用权 / 自治权 / 资源权 / 进化权`.
