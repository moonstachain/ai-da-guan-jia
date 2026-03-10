# Evolution Log Schema

## Canonical Path

Write each run to:

`artifacts/ai-da-guan-jia/runs/YYYY-MM-DD/<run-id>/`

## Required Files

- `situation-map.md`
- `route.json`
- `evolution.json`
- `evolution.md`
- `worklog.json`
- `worklog.md`
- `soul.md`
- `feishu-payload.json`
- `feishu-sync-result.json`
- `github-task.json`
- `github-payload.json`
- `github-sync-plan.md`
- `github-sync-result.json`
- `github-archive.md`

## Closure Discipline

Every meaningful task must record three self-evaluation dimensions before Feishu sync:

- `effective_patterns`: what the run genuinely gained or validated.
- `wasted_patterns`: what created friction, waste, or pseudo-progress.
- `evolution_candidates`: what should change next time.

Do not sync stale open questions. `verification_result.open_questions` must reflect only the real remaining issues after closure.

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
- `evolution_judgment_detail`
- `evolution_writeback_applied`
- `evolution_writeback_commit`
- `github_task_key`
- `github_issue_url`
- `github_project_url`
- `github_repo`
- `github_sync_status`
- `github_classification`
- `github_archive_status`
- `github_closure_comment_url`

## Type Conventions

- `skills_considered`: array of machine names in ranked order or considered order.
- `skills_selected`: array of final machine names.
- `verification_result`: object with at least `status`, plus optional `evidence` and `open_questions`.
- `effective_patterns`: array of strings.
- `wasted_patterns`: array of strings.
- `evolution_candidates`: array of strings. Keep them as proposals, not applied mutations.
- Treat the three fields above as the minimum self-review payload for every meaningful run.
- `evolution_judgment_detail`: object with `hit`, `positive_signals`, `blockers`, and trace counters.
- `evolution_writeback_applied`: bool. True only when this run wrote validated updates into this skill.
- `evolution_writeback_commit`: git commit hash for automatic writeback, or empty.
- `github_classification`: object with `type`, `domain`, `state`, `artifact`, `slug`, and `task_key`.
- `github_sync_status`: machine-readable status for the GitHub mirror lifecycle.
- `github_archive_status`: `not_archived`, `active`, or `archived`.

## Feishu Mirror Mapping

Flatten `worklog.json` into these human-readable fields:

- `日志ID`
- `运行标题`
- `时间`
- `记录日期`
- `接收任务`
- `工作目标`
- `工作状态`
- `完成情况`
- `完成方式`
- `调用技能`
- `技能数量`
- `验真状态`
- `验真证据摘要`
- `验真开放问题`
- `人类边界`
- `后续建议`
- `同步状态`

## GitHub Mirror Mapping

Use the local run directory as source of truth and mirror the task into GitHub with:

- one central issue in the configured ops repo
- prefixed labels for `type`, `domain`, `state`, and `artifact`
- one stable closure comment keyed by `github_task_key`
- one Project item when project config is available

Do not treat GitHub as canonical if the local run files diverge.
