# AI大管家 I-AUTO-001 Governance Linkage Phase 3 v1

## Goal

把 `I-AUTO-001` 从 `propose-only MVP` 推进到 `proposal quality -> governance` 的真实联动阶段。

这轮不改系统边界：

- 仍然是 `建议 + 待批`
- 不把 proposal 自动升级成执行
- 不用单次漂亮输出替代长期治理判断

## What Changed

本轮把 proposal 信号接进了两条治理链：

1. `strategy-governor` 默认 scorecard 链
   - `build_agent_scorecard`
   - `build_routing_credit`
   - `build_autonomy_tiers`

2. `review-governance` 写回链
   - `build_skill_governance_rows`
   - `governance_writeback_rows`

因此，无论当前环境有没有 `governance/current`，proposal quality 都不再只是说明文字，而会进入治理分。

## New Governance Signals

Phase 3 新增并复用这些字段：

- `proposal_support_count`
- `proposal_support_rate`
- `proposal_quality`
- `proposal_target_binding_rate`
- `proposal_boundary_discipline`
- `proposal_governance_score`

这些信号来自真实 run 的 `route.json`，不是从 `evolution.json` 反推的口头总结。

## Scoring Logic

proposal quality 主要由 5 类东西构成：

- readiness: `verified / waiting_human / blocked`
- structural completeness: hidden state、evidence、boundary、thread proposal 是否完整
- evidence quality: facts、inferences、verification targets、source paths 是否足够
- boundary discipline: 是否明确写出 `governance_boundary` 和 `human_approval_required`
- target binding: 是否真的挂到 `goal_id / initiative_id`

治理映射原则：

- scorecard 会显示 proposal 信号
- routing credit 会给 bounded proposal bonus
- autonomy tier 对高 tier 增加 proposal quality gate
- `waiting_human` 视为边界纪律成立，不视为失败

## Expected Output Shape

Phase 3 之后，以下文件会体现 proposal-governance linkage：

- `artifacts/ai-da-guan-jia/strategy/current/agent-scorecard.json`
- `artifacts/ai-da-guan-jia/strategy/current/routing-credit.json`
- `artifacts/ai-da-guan-jia/strategy/current/autonomy-tier.json`
- `artifacts/ai-da-guan-jia/strategy/current/governance-dashboard.md`

## Validation Target

这轮至少验证 3 件事：

- 至少 1 个 skill 出现 `proposal_support_count > 0`
- 至少 1 个 skill 的 `routing_credit` 因 proposal 信号发生正向变化
- autonomy tier 对有 proposal 证据但质量不足的对象保留 gate

## Current Phase Judgment

如果验证通过，`I-AUTO-001` 就可以视为完成：

- Phase 1: 方法层收口
- Phase 2: 提案回路 MVP
- Phase 3: 治理联动

下一步再进入 Phase 4：组织扩张，把 proposal 对象从 thread 扩展到 clone、workflow、skill recruitment。
