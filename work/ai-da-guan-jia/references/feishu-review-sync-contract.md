# Feishu Review Sync Contract

## Purpose

Mirror every daily `AI大管家` review into the Feishu base `技能盘点` as structured tables.  
Local review artifacts remain canonical; Feishu is the readable mirror and collaboration surface.

## Link Resolution

- `AI_DA_GUAN_JIA_REVIEW_FEISHU_LINK`
  Optional override for the review base.
- Fallback: `AI_DA_GUAN_JIA_FEISHU_LINK`
- Built-in default: `https://h52xu4gwob.feishu.cn/wiki/UzRjwDDLyi9OP4kEIHkcin1Gnhc?from=from_copylink`

## Required Order

1. Generate the local review artifacts.
2. Write `github-sources.json`, `findings.json`, and `feishu-sync-bundle.json`.
3. Ensure the Feishu base schema via `sync-base-schema`.
4. Upsert all 5 review tables by stable primary key.
5. Write `sync-result.json`.
6. If the human later selects `A` / `B` / `C`, sync the updated review state again.

## Commands

Daily review and sync:

```bash
python3 scripts/ai_da_guan_jia.py review-skills --daily --sync-feishu
```

Resolve one action and sync state:

```bash
python3 scripts/ai_da_guan_jia.py review-skills --resolve-action A --run-id adagj-review-20260310-090000 --sync-feishu
```

Direct schema sync:

```bash
python3 /Users/hay2045/.codex/skills/feishu-bitable-bridge/scripts/feishu_bitable_bridge.py sync-base-schema --link "$AI_DA_GUAN_JIA_REVIEW_FEISHU_LINK" --manifest /Users/hay2045/.codex/skills/ai-da-guan-jia/references/feishu-review-base-schema.json --apply
```

## Tables

- `复盘批次`
- `技能清单快照`
- `候选进化动作`
- `关键发现`
- `GitHub来源`

All tables use text-like fields only in v1 so `upsert-records` remains reliable and idempotent.

## Failure Handling

- If the review link, bridge script, or schema manifest is missing, keep all local artifacts and write `sync-result.json`.
- If schema sync fails, do not try record upserts.
- If one table upsert fails, keep the rest of the results in `sync-result.json` for replay.
- Do not treat Feishu as canonical if local review artifacts and Feishu diverge.
