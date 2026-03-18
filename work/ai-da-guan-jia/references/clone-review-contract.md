# Clone Review Contract

## Purpose

Aggregate all registered clones into one daily portfolio review and proposal queue.

This is the review-like contract for clone portfolio outputs and future mirror sync.

## Command

```bash
python3 scripts/ai_da_guan_jia.py review-clones
python3 scripts/ai_da_guan_jia.py review-clones --date 2026-03-11
python3 scripts/ai_da_guan_jia.py review-clones --portfolio internal
python3 scripts/ai_da_guan_jia.py sync-feishu --surface clone_governance --portfolio internal --dry-run
python3 scripts/ai_da_guan_jia.py sync-feishu --surface clone_governance --portfolio client --dry-run
python3 scripts/ai_da_guan_jia.py sync-feishu --surface clone_governance --portfolio all --apply
```

## Required Outputs

- `role-template-registry.json`
- `org-registry.json`
- `clone-scorecard.json`
- `clone-autonomy-tier.json`
- `promotion-queue.json`
- `budget-allocation.json`
- `task-runs.json`
- `training-cycles.json`
- `capability-proposals.json`
- `alerts-decisions.json`
- `portfolio-daily-report.json`
- `portfolio-daily-report.md`
- `feishu-sync-bundle.json`

## Required Feishu Mirror Tables

- `组织/租户表`
- `角色模板表`
- `AI实例注册表`
- `运行日志表`
- `训练轮次表`
- `能力提案表`
- `实例评分表`
- `风险与决策表`

## portfolio-daily-report.md Required Sections

1. `今日新增与状态变化`
2. `克隆体排名与分层`
3. `候选晋升 / 降权 / 休眠`
4. `当前最大失真与主要风险`
5. `明日训练建议`

## Review Rules

- Rank clones by governance-weighted training quality, not raw task count.
- Penalize distortion and unnecessary human interruption more than slow progress.
- Keep promotion, demotion, hibernation, and budget changes as proposals that require human approval.
- Support `internal / client / all` portfolio slices; default day-to-day mirrors stay `client` unless the human explicitly asks for a wider HQ view.
- Persist local internal portfolio artifacts when `review-clones --portfolio internal` is used so one employee MVP can run without a separate control plane.
- Keep the HQ base schema stable so Feishu and 妙搭 can bind one shared control tower with role-specific views.
- Treat Feishu and GitHub as mirrors only after the local portfolio report exists.
