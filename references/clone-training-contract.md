# Clone Training Contract

## Purpose

Run one clone training round through the existing `route -> evolution -> worklog` closure path.

## Commands

```bash
python3 scripts/ai_da_guan_jia.py register-clone --clone-id acme-alpha --customer-id acme --display-name "Acme Alpha" --goal-model "提高客户成功率" --memory-namespace "clone/acme-alpha" --report-owner "hay"
python3 scripts/ai_da_guan_jia.py train-clone --clone-id acme-alpha --target-capability "技能训练方法学"
python3 scripts/ai_da_guan_jia.py train-clone --clone-id acme-alpha --target-capability "客户交付闭环" --task "训练这个 clone 用最小 skill 组合完成交付闭环"
```

## Required Run Fields

Every clone training round must write these fields into `route.json`, `evolution.json`, and `worklog.json`:

- `run_kind`
- `clone_id`
- `customer_id`
- `org_id`
- `tenant_id`
- `actor_type`
- `role_template_id`
- `visibility_policy`
- `service_tier`
- `manager_clone_id`
- `training_cycle_id`
- `target_capability`
- `score_before`
- `score_after`
- `promotion_recommendation`
- `budget_weight`

## Required Behavior

- Prefer the smallest sufficient skill chain.
- Always include the shared `ai-da-guan-jia` governor in the training chain.
- Escalate to `skill-trainer-recursive` when the capability gap is methodology-heavy.
- Treat `score_before -> score_after` as the minimum training trace.
- Preserve unresolved privileged boundaries as explicit open questions instead of pretending completion.

## Non-Goals

- Do not auto-ingest customer knowledge bases in v1.
- Do not auto-run browser or privileged external execution in v1.
- Do not auto-promote, auto-hibernate, or auto-change budgets in v1.
