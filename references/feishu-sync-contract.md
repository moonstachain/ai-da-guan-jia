# Feishu Sync Contract

## Purpose

Use Feishu as a readable mirror of the local evolution log. Do not use it as the canonical record.

## Environment Variables

- `AI_DA_GUAN_JIA_FEISHU_LINK`
  A Feishu wiki or base link that `feishu-bitable-bridge` can inspect.
- `AI_DA_GUAN_JIA_FEISHU_PRIMARY_FIELD`
  Optional. Defaults to `日志ID`.
- `AI_DA_GUAN_JIA_FEISHU_BRIDGE_SCRIPT`
  Optional override for the bridge script path. By default it points to the local `feishu-bitable-bridge` skill.

## Required Order

1. Write the local canonical run.
2. Generate `feishu-payload.json`.
3. Run `sync-feishu --dry-run`.
4. Run `sync-feishu --apply` only after explicit authorization.

## Commands

Dry run:

```bash
python3 scripts/ai_da_guan_jia.py sync-feishu --run-id adagj-20260309-101500 --dry-run
```

Apply:

```bash
python3 scripts/ai_da_guan_jia.py sync-feishu --run-id adagj-20260309-101500 --apply
```

## Bridge Contract

The underlying bridge command is:

```bash
python3 "$AI_DA_GUAN_JIA_FEISHU_BRIDGE_SCRIPT" upsert-records --link "$AI_DA_GUAN_JIA_FEISHU_LINK" --primary-field "日志ID" --payload-file feishu-payload.json --dry-run
```

The payload shape is a single JSON object keyed by the Chinese field names listed in [evolution-log-schema.md](evolution-log-schema.md).

## Failure Handling

- If the Feishu link is missing, keep the payload locally and mark sync status as payload-only.
- If the bridge script is missing, keep the payload locally and mark sync status as bridge-missing.
- If `--apply` is requested without the prerequisites, fail loudly.
