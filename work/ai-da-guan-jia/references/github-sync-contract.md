# GitHub Sync Contract

## Purpose

Mirror one meaningful AI大管家 run into GitHub without changing the local run directory's role as source of truth.

## Commands

```bash
python3 scripts/ai_da_guan_jia.py sync-github --run-id adagj-20260310-120000 --phase intake --dry-run
python3 scripts/ai_da_guan_jia.py sync-github --run-id adagj-20260310-120000 --phase intake --apply
python3 scripts/ai_da_guan_jia.py sync-github --run-id adagj-20260310-120000 --phase closure --dry-run
python3 scripts/ai_da_guan_jia.py sync-github --run-id adagj-20260310-120000 --phase closure --apply
```

## Order

1. Read local `route.json`, `evolution.json`, and `github-task.json`.
2. Regenerate `github-payload.json` and `github-sync-plan.md`.
3. Reuse or create one issue keyed by `github_task_key`.
4. Normalize labels and body to the current taxonomy.
5. Upsert one closure comment for `phase=closure`.
6. If Project config exists, add or update the Project item.
7. Write `github-sync-result.json`.

## Environment

- `AI_DA_GUAN_JIA_GITHUB_OPS_REPO`
- `AI_DA_GUAN_JIA_GITHUB_DOT_GITHUB_REPO`
- `AI_DA_GUAN_JIA_GITHUB_PROJECT_OWNER`
- `AI_DA_GUAN_JIA_GITHUB_PROJECT_NUMBER`
- `AI_DA_GUAN_JIA_GITHUB_API_URL` (optional)
- `GITHUB_TOKEN` for REST fallback

## Backend Priority

1. `gh` CLI with authenticated `gh auth status`
2. GitHub REST/GraphQL with `GITHUB_TOKEN`
3. Local payload only when neither is available

## Idempotence

- `github_task_key` is the external key.
- Re-runs update the existing issue, closure comment, and Project item.
- Do not duplicate cards or comments for the same run/task key pair.
