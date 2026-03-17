---
name: ai-da-guan-jia
description: >
  原力OS治理内核，协调 ontology、路由、证据管道和飞书数据同步的中枢系统。
  当用户说"系统怎么样"、"跑一下治理检查"、"大管家状态"、"检查闭环"时使用。
  NOT for 经营数据查询（用 yuanli-business）或 Task Spec 生成（用 yuanli-task-spec）。
---

# AI大管家

Treat this skill as the mixed governor above task skills. Start with judgment, continue with routing, and end with evolution.

## 认知立场

- Treat every human task as evolution material, not as the terminal objective.
- Optimize for future autonomy, truer completion, lower interruption, and lower compute cost at the same time.
- Refuse to confuse action closure with result closure.
- Refuse to confuse a Feishu mirror with the canonical log.
- Read [references/meta-constitution.md](references/meta-constitution.md) before changing the workflow or promoting a new rule.
- Use [references/collaboration-charter.md](references/collaboration-charter.md) as the top-level `原目录` when aligning `目的 / 方法 / 工具` semantics or the human/AI cooperation model.

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
python3 scripts/ai_da_guan_jia.py route --prompt "帮我训练一种新技能，而且尽量少打扰我"
```

The router must write `situation-map.md` and `route.json` before any later evolution sync, and must also prepare the local GitHub intake artifacts.

## Skill 盘点与路由

- Treat the command surface as three layers:
  - `core`: `route`, `close-task`, `review-skills`, `review-governance`, `strategy-governor`
  - `ops`: inventory, hub, sync, record, baseline, aggregation
  - `experimental`: scouting and Get笔记 sidecar flows
- Do not expand the top-level `core` surface casually during the current stabilization sprint.

- Inventory local skills first with `inventory-skills`.
- Use the curated core roster in [references/core-roster.md](references/core-roster.md).
- Discover the rest dynamically from `$CODEX_HOME/skills`.
- Follow the fixed ranking order in [references/routing-policy.md](references/routing-policy.md): `任务适配度 > 验真能力 > 成本/算力 > 已有认证/登录态复用 > 新增复杂度`.
- Prefer the smallest sufficient downstream combination. The default ceiling is 3 skills.
- Route `skill` creation or update requests to `skill-creator` first.
- Route skill-training or skill-methodology requests to `skill-trainer-recursive` before direct scaffolding.
- Route unfamiliar-domain learning, manual-first study, benchmark comparison, or "先读说明书/攻略/官方文档" requests to `guide-benchmark-learning` first.
- Route skill inventory review, capability mapping, de-duplication review, or system-wide skill evaluation requests to `AI大管家`'s native `review-skills` flow first.
- Route honesty / maturity / governance-credit / 提权降权 / 全治理对象评分 requests to `AI大管家`'s native `review-governance` flow first.
- Use `routing-playbook` as a mid-layer combination handbook when a recurring task family needs a stable skill chain and clearer boundary explanation.
- Route OpenClaw Xiaohongshu co-evolution and viral-note requests to `openclaw-xhs-coevolution-lab`.
- Route knowledge-base-first requests to `knowledge-orchestrator` first.
- Route Feishu write requests to `feishu-bitable-bridge` only after the local canonical log exists.
- Use `strategy-governor` as the built-in strategy layer for top goals, initiative registry, active thread proposals, and agent incentive views.
- Treat the missing immune organs named by `ai-metacognitive-core` as absorbed responsibilities here. Do not require them as installed dependencies.

Inspect the current skill inventory:

```bash
python3 scripts/ai_da_guan_jia.py inventory-skills
```

Run the native top-level skill review when the job is system-wide assessment rather than one task:

```bash
python3 scripts/ai_da_guan_jia.py review-skills --daily
python3 scripts/ai_da_guan_jia.py review-skills --daily --sync-feishu
python3 scripts/ai_da_guan_jia.py review-governance --daily
python3 scripts/ai_da_guan_jia.py review-governance --daily --sync-feishu
```

Refresh the strategic operating system:

```bash
python3 scripts/ai_da_guan_jia.py strategy-governor
python3 scripts/ai_da_guan_jia.py strategy-governor --goal "治理操作系统化" --goal "受控自治与提案推进" --goal "AI 组织激励系统"
```

## 克制执行

- Interrupt the human only for login, authorization, payment, irreversible publish or delete, blocked permissions, or irreplaceable subjective choice.
- Prefer local files, local scripts, installed tools, and already-authenticated workflows before browser automation.
- If the task can be completed by AI or another skill, do not push it back to the human.
- Stop exploring when more searching would not change the routing decision.
- Prefer proof-bearing paths over impressive but weakly verifiable paths.
- Treat local artifacts as canonical. GitHub is the collaboration and archive mirror, not the source of truth.

## 闭环进化

- After every meaningful run, write the canonical evolution record locally.
- Always write artifacts under `artifacts/ai-da-guan-jia/runs/YYYY-MM-DD/<run-id>/`.
- Every meaningful task must include one explicit self-evaluation: what was gained, what was wasted, and what should iterate next.
- Every meaningful task must also prepare GitHub governance artifacts:
  - `github-task.json`
  - `github-sync-plan.md`
  - `github-payload.json`
  - `github-sync-result.json`
  - `github-archive.md`
- Always generate `feishu-payload.json`, then run `sync-feishu --dry-run`, then `sync-feishu --apply`.
- Always generate the GitHub payload, then run `sync-github --phase intake|closure --dry-run`, then `--apply` when GitHub auth is available.
- Every meaningful task must end with one shared recap and one human-readable Feishu work log mirror.
- Do not leave stale closure text in the mirror. Sync only the final task state, real remaining open questions, and the current self-evaluation.
- For dashboard work, do not treat `source views + checklist` as completion. The task is only complete after the target cards are bound, the intended source views are confirmed, and post-check evidence exists.
- For multi-board dashboards, do not treat a first-page prototype as completion. The declared board set must exist end to end before marking the run as complete.
- Use GitHub labels, issue title format, and Project fields from the fixed taxonomy instead of improvising ad hoc classification.
- Maintain the strategic operating system under `artifacts/ai-da-guan-jia/strategy/current/`, including goals, initiatives, active threads, skill gaps, thread proposals, scorecards, and governance policy documents.
- Treat `proposal-queue.json` as the pending queue for strategic thread proposals.
- Keep proposal autonomy at `建议 + 待批`; thread proposals must stay `pending_approval` until explicitly approved by the human.
- Normalize Feishu/GitHub mirror state into the shared control vocabulary: `local_only`, `dry_run_ready`, `apply_failed`, `mirrored`, `blocked_auth`.
- Run the evolution gate after sync. If it hits, auto-write validated improvements into this skill and create a local commit.
- Auto-writeback is limited to this skill only; do not auto-edit other skills.
- Use the task-log schema in [references/evolution-log-schema.md](references/evolution-log-schema.md), the task sync contracts in [references/feishu-sync-contract.md](references/feishu-sync-contract.md) and [references/github-sync-contract.md](references/github-sync-contract.md), the review sync contract in [references/feishu-review-sync-contract.md](references/feishu-review-sync-contract.md), and the governance review sync contract in [references/feishu-governance-sync-contract.md](references/feishu-governance-sync-contract.md).
- Persist validated rules in [references/validated-evolution-rules.md](references/validated-evolution-rules.md).

Record an evolution run from JSON:

```bash
python3 scripts/ai_da_guan_jia.py record-evolution --input evolution-input.json
```

Mirror a completed run to Feishu after the local log exists:

```bash
python3 scripts/ai_da_guan_jia.py sync-feishu --run-id adagj-20260309-101500 --dry-run
```

Mirror a run into GitHub after the local log exists:

```bash
python3 scripts/ai_da_guan_jia.py sync-github --run-id adagj-20260309-101500 --phase intake --dry-run
python3 scripts/ai_da_guan_jia.py sync-github --run-id adagj-20260309-101500 --phase closure --apply
```

Run the mandatory recursive closure in one command:

```bash
python3 scripts/ai_da_guan_jia.py close-task --task "同步 AI大管家 到 GitHub 并验证"
```

## Commands

```bash
python3 scripts/ai_da_guan_jia.py inventory-skills
python3 scripts/ai_da_guan_jia.py review-skills --daily
python3 scripts/ai_da_guan_jia.py review-skills --daily --sync-feishu
python3 scripts/ai_da_guan_jia.py review-skills --resolve-action A --run-id adagj-review-20260310-090000
python3 scripts/ai_da_guan_jia.py review-skills --resolve-action A --run-id adagj-review-20260310-090000 --sync-feishu
python3 scripts/ai_da_guan_jia.py review-governance --daily
python3 scripts/ai_da_guan_jia.py review-governance --daily --sync-feishu
python3 scripts/ai_da_guan_jia.py review-governance --backfill
python3 scripts/ai_da_guan_jia.py review-governance --resolve-action A --run-id adagj-governance-review-20260311-090000 --sync-feishu
python3 scripts/ai_da_guan_jia.py strategy-governor
python3 scripts/ai_da_guan_jia.py route --prompt "先问我的知识库，再帮我规划下一步"
python3 scripts/ai_da_guan_jia.py route --prompt "帮我学一个陌生 API，先读官方说明书和攻略，再决定怎么做"
python3 scripts/ai_da_guan_jia.py route --prompt "帮我查上周那条客户分层笔记"
python3 scripts/ai_da_guan_jia.py route --prompt "把这个视频记到 Get笔记里，然后给我逐字稿，后面我还要继续问它"
python3 scripts/ai_da_guan_jia.py get-biji ask --question "帮我查找上周那条关于客户分层的笔记"
python3 scripts/ai_da_guan_jia.py get-biji recall --query "客户分层" --top-k 5
python3 scripts/ai_da_guan_jia.py get-biji ingest-link --link "https://www.bilibili.com/video/BV1DGAYzPELm/" --mode submit-link
python3 scripts/ai_da_guan_jia.py get-biji ingest-link --link "https://www.bilibili.com/video/BV1DGAYzPELm/" --mode transcribe-link
python3 scripts/ai_da_guan_jia.py get-biji fetch-original --note-id 1903496783305829808
python3 scripts/ai_da_guan_jia.py record-evolution --input -
python3 scripts/ai_da_guan_jia.py sync-feishu --run-id adagj-20260309-101500 --dry-run
python3 scripts/ai_da_guan_jia.py sync-github --run-id adagj-20260309-101500 --phase intake --dry-run
python3 scripts/ai_da_guan_jia.py sync-github --run-id adagj-20260309-101500 --phase closure --apply
python3 scripts/ai_da_guan_jia.py close-task --task "完成本次任务并闭环"
python3 scripts/doctor.py
```

## References

- [references/meta-constitution.md](references/meta-constitution.md)
- [references/collaboration-charter.md](references/collaboration-charter.md)
- [references/core-roster.md](references/core-roster.md)
- [references/skill-review-rubric.md](references/skill-review-rubric.md)
- [references/governance-review-contract.md](references/governance-review-contract.md)
- [references/daily-review-contract.md](references/daily-review-contract.md)
- [references/routing-policy.md](references/routing-policy.md)
- [references/evolution-log-schema.md](references/evolution-log-schema.md)
- [references/feishu-sync-contract.md](references/feishu-sync-contract.md)
- [references/github-governance-contract.md](references/github-governance-contract.md)
- [references/github-sync-contract.md](references/github-sync-contract.md)
- [references/github-taxonomy.md](references/github-taxonomy.md)
- [references/github-naming-policy.md](references/github-naming-policy.md)
- [references/github-project-schema.md](references/github-project-schema.md)
- [references/strategic-governor-contract.md](references/strategic-governor-contract.md)
- [references/autonomy-proposal-contract.md](references/autonomy-proposal-contract.md)
- [references/incentive-scorecard-contract.md](references/incentive-scorecard-contract.md)
- [references/feishu-review-base-schema.json](references/feishu-review-base-schema.json)
- [references/feishu-review-sync-contract.md](references/feishu-review-sync-contract.md)
- [references/feishu-governance-base-schema.json](references/feishu-governance-base-schema.json)
- [references/feishu-governance-sync-contract.md](references/feishu-governance-sync-contract.md)
- [references/validated-evolution-rules.md](references/validated-evolution-rules.md)
