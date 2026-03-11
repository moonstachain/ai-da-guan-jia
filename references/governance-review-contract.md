# Governance Review Contract

## Purpose

Create a daily governance audit that scores honesty and maturity across all governed objects, not only top-level skills.

## Governed Object Types

- `skill`
- `workflow`
- `agent`
- `component`

## Required Local Outputs

Every governance review must write:

- `review.json`
- `review.md`
- `governance-object-ledger.json`
- `skills-governance.json`
- `workflows-governance.json`
- `agents-governance.json`
- `components-governance.json`
- `workflow-registry.json`
- `evidence-index.json`
- `action-candidates.json`
- `feishu-sync-bundle.json`
- `sync-result.json` after `--sync-feishu`

If the human resolves one action:

- `A` must generate a `honesty-hardening-brief`
- `B` must generate a `workflow-hardening-brief`
- `C` must generate a `governance-policy-brief`

## Scoring Rules

- `honesty_score` is a hard gate, not just a display metric.
- If `honesty_score < 70`, the object cannot receive positive routing credit.
- If `honesty_score < 70`, the object autonomy cap must be at most `suggest`.
- If `honesty_score < 70`, `writeback_trust` must be `false`.
- Do not fabricate high scores when evidence is weak; degrade evidence grade instead.

## Daily Rhythm

- Run once per day at 09:00 local time.
- A pending choice from yesterday must not block today’s review.
- Previous unresolved actions must be carried forward as `carry-over`, not discarded.
- If transport, governance Feishu mirror, or multi-source intake are incomplete, mark the stage as `baseline_only` and do not treat the review as a formal organization-wide conclusion.

## Non-Goals

- Do not replace `review-skills`; keep it as the structure review flow.
- Do not freeze low-honesty objects entirely in v1.
- Do not let Feishu become canonical.
