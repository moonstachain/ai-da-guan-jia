# Internal Ops MVP Contract

## Purpose

Run the first internal colleague MVP as one `ops-management` employee clone with one fixed 5-day operating loop.

This contract covers `Phase 0` and `Phase 1` of the larger internal collaboration lifecycle.
For the full path, see `references/internal-collaboration-lifecycle-contract.md`.

## Scope

- One colleague only
- `org_id = yuanli-hq`
- `tenant_id = yuanli-hq`
- `actor_type = employee`
- `role_template_id = ops-management`
- Feishu frontstage only
- AI大管家 backend only

## Commands

```bash
bash scripts/internal_ops_mvp.sh bootstrap ops-mvp-001 "中台管理试点同事"
bash scripts/internal_ops_mvp.sh midday
bash scripts/internal_ops_mvp.sh evening
python3 scripts/ai_da_guan_jia.py review-clones --portfolio internal
python3 scripts/ai_da_guan_jia.py sync-feishu --surface clone_governance --portfolio internal --dry-run
```

## Fixed Phrases

1. `今天最该看什么`
2. `帮我接个任务：...`
3. `我现在有哪些任务`
4. `继续昨天那个`
5. `把这事闭环`

## Required Closure States

- `completed`
- `blocked_needs_user`
- `blocked_system`
- `failed_partial`

## Required Review Focus

- Keep the frontstage to at most `3` active tasks.
- The founder checks the loop only twice a day: noon and evening.
- Noon review must prioritize `waiting_human / blocked_* / 风险与决策表`.
- Evening review must verify `closure_state + evidence + blocker`.

## Required Outputs

- `clone-registry.json`
- `clone-training-state.json`
- `org-registry.json`
- `clone-scorecard.json`
- `task-runs.json`
- `alerts-decisions.json`
- `portfolio-daily-report.json`
- `portfolio-daily-report.md`
- `feishu-sync-bundle.json`
- `sync-result.json`

## Non-Goals

- Do not onboard a second employee in week one.
- Do not onboard any client tenant in week one.
- Do not expand to finance or legal high-risk loops in week one.
- Do not treat dashboard brightness as proof of reduced management load.
