# Daily Review Contract

Use this contract for the daily 09:00 AI大管家 skill review.

## Goal

Produce one lightweight but actionable review of the whole installed skill system, then wait for the human to choose a direction.

## Required Outputs

Every daily review must produce:

- `inventory.json`
- `review.json`
- `review.md`
- `action-candidates.json`
- `github-sources.json`
- `findings.json`
- `feishu-sync-bundle.json`
- `review-state.json` update
- `sync-result.json` after `--sync-feishu`

## Required Review Sections

`review.md` must always contain exactly these sections:

1. `今日结构变化`
2. `当前最值得关注的问题`
3. `3 个候选进化动作`
4. `当前等待你做的选择`

## Human Collaboration Rule

- Generate exactly 3 candidate actions.
- Label them `A`, `B`, and `C`.
- Ask the human to reply with one choice only.
- Do not modify any skill during the daily review.
- If the previous review is still awaiting a human choice, do not open a new round.

## Default Non-Goals

- Do not auto-apply the top-ranked action.
- Do not sync systems other than the configured Feishu review base.
- Do not archive the thread.
- Do not turn one daily review into a permanent governance rule without later validation.
