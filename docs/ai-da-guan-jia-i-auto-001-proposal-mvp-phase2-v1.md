# AI大管家 `I-AUTO-001` Proposal MVP Phase 2 v1

## Summary

这一轮把 `I-AUTO-001 提案自治引擎` 从 Phase 1 的方法层，推进到了 Phase 2 的最小可运行回路：

`signal -> hidden_state_hypothesis -> proposal -> evidence gate -> 待批`

本轮仍然坚持边界：

`建议 + 待批`

没有把 proposal output 偷渡成静默执行。

## 本轮新增

### 1. Proposal Contract 升级

`work/ai-da-guan-jia/references/autonomy-proposal-contract.md` 现在已经补齐：

- `hidden_state_hypothesis` 模板
- `evidence_bundle` 模板
- `verified / waiting_human / blocked` 判定口径
- Phase 2 最小 route output contract

### 2. Route 输出升级

`work/ai-da-guan-jia/scripts/ai_da_guan_jia.py route` 现在会额外输出：

- `goal_id`
- `initiative_id`
- `theme_id`
- `strategy_id`
- `hidden_state_hypothesis`
- `reuse_vs_new_judgment`
- `evidence_bundle`
- `fact_inference_split`
- `boundary_assessment`
- `proposal_candidates`
- `thread_proposal`
- `initiative_decomposition`
- `skill_recruitment_suggestion`
- `proposal_readiness`
- `blocked_reason`

### 3. Proposal Prompt 路由修正

proposal-specific prompt 现在会把 `ai-da-guan-jia` 强制纳入最小组合，不再被通用自治 skill 链条盖过去。

## 真实样本

### Workspace Sample

- Prompt：
  `围绕 G2 / I-AUTO-001 做一个提案回路 MVP：输出 hidden_state_hypothesis、evidence_bundle、thread proposal 与 initiative_decomposition，保持建议 + 待批边界，尽量少打扰我。`
- Run：
  `/Users/liming/Documents/codex-ai-gua-jia-01/work/ai-da-guan-jia/artifacts/ai-da-guan-jia/runs/2026-03-15/adagj-i-auto-001-proposal-mvp-phase2-sample-v1`

结果：

- `selected_skills` = `ai-da-guan-jia`, `self-evolution-max`, `jiyao-youyao-haiyao`
- `proposal_readiness` = `waiting_human`
- `thread_proposal.title` = `把 I-AUTO-001 的提案回路 MVP 跑通`

### Live Canonical Sample

- Run：
  `/Users/liming/.codex/skills/ai-da-guan-jia/artifacts/ai-da-guan-jia/runs/2026-03-15/adagj-i-auto-001-proposal-mvp-phase2-sample-v1`

结果：

- `proposal_readiness` = `waiting_human`
- `hidden_state_hypothesis` 已保留在 canonical `route.json`
- `evolution.json` 状态 = `completed`
- `github_sync_status` = `github_intake_synced_applied`

## Canonical 状态更新

live canonical 已同步这些关键对象：

- `initiative-brief.json` 已切到 `I-AUTO-001`
- `TP-002` 已保持 `approved / active`
- `proposal-queue.json` 中 `TP-002` 已更新为 `approved`
- `strategic-proposal.md` 已把当前推荐推进到 Phase 3
- `governance-dashboard.md` 已把 `TP-002` 与 next focus 改成 Phase 3 治理联动

## 当前结论

Phase 2 已经站住，意义在于：

- proposal 不再只是语言解释，而是结构化对象
- 事实、推断、边界、待批状态已经分开
- `I-AUTO-001` 已经有第一条真实 propose-only 样本

下一阶段自然进入：

`Phase 3：治理联动`
