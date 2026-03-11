# Feishu Governance Sync Contract

## Purpose

Mirror every governance review into the Feishu base `治理信用总账`.

Local governance ledgers remain canonical. Feishu is the readable collaboration surface only.

## Link Resolution

- `AI_DA_GUAN_JIA_GOVERNANCE_FEISHU_LINK`
- No fallback to the old review base

## Required Order

1. Generate local governance ledgers and review artifacts.
2. Ensure the governance base schema via `sync-base-schema`.
3. Upsert all 8 governance tables by stable primary key.
4. Write `sync-result.json`.
5. If the human later resolves `A` / `B` / `C`, sync the updated review state again.

## Commands

```bash
python3 scripts/ai_da_guan_jia.py review-governance --daily --sync-feishu
python3 scripts/ai_da_guan_jia.py review-governance --backfill
python3 scripts/ai_da_guan_jia.py review-governance --resolve-action A --run-id adagj-governance-review-20260311-090000 --sync-feishu
```

## Failure Handling

- If the governance link, bridge script, or manifest is missing, keep all local files and write `sync-result.json`.
- If schema sync fails, do not upsert any records.
- If one table fails, record partial failure in `sync-result.json` and keep the rest for replay.
- Do not treat Feishu as canonical if it diverges from local governance ledgers.
