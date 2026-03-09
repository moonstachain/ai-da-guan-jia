# Evolution Log Schema

## Canonical Path

Write each run to:

`artifacts/ai-da-guan-jia/runs/YYYY-MM-DD/<run-id>/`

## Required Files

- `situation-map.md`
- `route.json`
- `evolution.json`
- `evolution.md`
- `feishu-payload.json`

## evolution.json Required Fields

- `run_id`
- `created_at`
- `task_text`
- `goal_model`
- `autonomy_judgment`
- `global_optimum_judgment`
- `reuse_judgment`
- `verification_judgment`
- `evolution_judgment`
- `max_distortion`
- `skills_considered`
- `skills_selected`
- `human_boundary`
- `verification_result`
- `effective_patterns`
- `wasted_patterns`
- `evolution_candidates`
- `feishu_sync_status`

## Type Conventions

- `skills_considered`: array of machine names in ranked order or considered order.
- `skills_selected`: array of final machine names.
- `verification_result`: object with at least `status`, plus optional `evidence` and `open_questions`.
- `effective_patterns`: array of strings.
- `wasted_patterns`: array of strings.
- `evolution_candidates`: array of strings. Keep them as proposals, not applied mutations.

## Feishu Mirror Mapping

Flatten `evolution.json` into these human-readable fields:

- `日志ID`
- `时间`
- `任务简述`
- `目标模型`
- `当前最大失真`
- `已评估技能`
- `最终调用技能`
- `人类边界`
- `验真结论`
- `有效做法`
- `浪费动作`
- `进化候选`
- `同步状态`
