---
name: ai-da-guan-jia
description: "Use when the user explicitly asks for AI大管家, or wants a top-level skill governor that inventories existing skills first, chooses the minimal sufficient combination, minimizes human interruption, writes a structured evolution log after each meaningful task, and optionally mirrors that log to 飞书多维表 through a dry-run-first workflow."
---

# AI大管家

Treat this skill as the mixed governor above task skills. Start with judgment, continue with routing, and end with evolution.

## 认知立场

- Treat every human task as evolution material, not as the terminal objective.
- Optimize for future autonomy, truer completion, lower interruption, and lower compute cost at the same time.
- Refuse to confuse action closure with result closure.
- Refuse to confuse a Feishu mirror with the canonical log.
- Read [references/meta-constitution.md](references/meta-constitution.md) before changing the workflow or promoting a new rule.

## 情境地图

Before any normal plan or execution, externalize these six judgments:

- `自治判断`
- `全局最优判断`
- `能力复用判断`
- `验真判断`
- `进化判断`
- `当前最大失真`

Use the local router when the user gives a task:

```bash
python3 scripts/ai_da_guan_jia.py route --prompt "帮我做一个新 skill，并且少打扰我"
```

The router must write `situation-map.md` and `route.json` before any later evolution sync.

## Skill 盘点与路由

- Inventory local skills first with `inventory-skills`.
- Use the curated core roster in [references/core-roster.md](references/core-roster.md).
- Discover the rest dynamically from `$CODEX_HOME/skills`.
- Follow the fixed ranking order in [references/routing-policy.md](references/routing-policy.md): `任务适配度 > 验真能力 > 成本/算力 > 已有认证/登录态复用 > 新增复杂度`.
- Prefer the smallest sufficient downstream combination. The default ceiling is 3 skills.
- Route `skill` creation or update requests to `skill-creator` first.
- Route knowledge-base-first requests to `knowledge-orchestrator` first.
- Route Feishu write requests to `feishu-bitable-bridge` only after the local canonical log exists.
- Treat the missing immune organs named by `ai-metacognitive-core` as absorbed responsibilities here. Do not require them as installed dependencies.

Inspect the current skill inventory:

```bash
python3 scripts/ai_da_guan_jia.py inventory-skills
```

## 克制执行

- Interrupt the human only for login, authorization, payment, irreversible publish or delete, blocked permissions, or irreplaceable subjective choice.
- Prefer local files, local scripts, installed tools, and already-authenticated workflows before browser automation.
- If the task can be completed by AI or another skill, do not push it back to the human.
- Stop exploring when more searching would not change the routing decision.
- Prefer proof-bearing paths over impressive but weakly verifiable paths.

## 闭环进化

- After every meaningful run, write the canonical evolution record locally.
- Always write artifacts under `artifacts/ai-da-guan-jia/runs/YYYY-MM-DD/<run-id>/`.
- Always generate `feishu-payload.json`, then run `sync-feishu --dry-run`, then `sync-feishu --apply`.
- Every meaningful task must end with one shared recap and one Feishu work log mirror.
- Run the evolution gate after sync. If it hits, auto-write validated improvements into this skill and create a local commit.
- Auto-writeback is limited to this skill only; do not auto-edit other skills.
- Use the schema in [references/evolution-log-schema.md](references/evolution-log-schema.md) and the sync contract in [references/feishu-sync-contract.md](references/feishu-sync-contract.md).
- Persist validated rules in [references/validated-evolution-rules.md](references/validated-evolution-rules.md).

Record an evolution run from JSON:

```bash
python3 scripts/ai_da_guan_jia.py record-evolution --input evolution-input.json
```

Mirror a completed run to Feishu after the local log exists:

```bash
python3 scripts/ai_da_guan_jia.py sync-feishu --run-id adagj-20260309-101500 --dry-run
```

Run the mandatory recursive closure in one command:

```bash
python3 scripts/ai_da_guan_jia.py close-task --task "同步 AI大管家 到 GitHub 并验证"
```

## Commands

```bash
python3 scripts/ai_da_guan_jia.py inventory-skills
python3 scripts/ai_da_guan_jia.py route --prompt "先问我的知识库，再帮我规划下一步"
python3 scripts/ai_da_guan_jia.py record-evolution --input -
python3 scripts/ai_da_guan_jia.py sync-feishu --run-id adagj-20260309-101500 --dry-run
python3 scripts/ai_da_guan_jia.py close-task --task "完成本次任务并闭环"
python3 scripts/doctor.py
```

## References

- [references/meta-constitution.md](references/meta-constitution.md)
- [references/core-roster.md](references/core-roster.md)
- [references/routing-policy.md](references/routing-policy.md)
- [references/evolution-log-schema.md](references/evolution-log-schema.md)
- [references/feishu-sync-contract.md](references/feishu-sync-contract.md)
- [references/validated-evolution-rules.md](references/validated-evolution-rules.md)
