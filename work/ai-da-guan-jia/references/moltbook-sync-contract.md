# Moltbook Sync Contract

## Purpose

Use Moltbook as a non-canonical community observation mirror of the local run state.

This contract is V1 only. It prepares a human-review package and does not publish automatically.
For the next stage, use one shared multi-agent board and verify visibility before upgrading any run to `published`.

## Environment Variables

- `AI_DA_GUAN_JIA_MOLTBOOK_URL`
  Optional target page URL for the community mirror.
  Default: `https://www.moltbook.com/skill.md`
- `AI_DA_GUAN_JIA_MOLTBOOK_MODE`
  V1 only supports `manual_bridge`.
- `AI_DA_GUAN_JIA_MOLTBOOK_API_KEY`
  Optional. If present, `publish-moltbook` should prefer the API publish path before browser automation.
- `AI_DA_GUAN_JIA_MOLTBOOK_API_BASE`
  Optional API base override. Default should point at the public Moltbook API base.
- `AI_DA_GUAN_JIA_MOLTBOOK_POST_ENDPOINT`
  Optional publish endpoint override. Default should point at the post-create path.

## Required Order

1. Write the local canonical run.
2. Finish self-evaluation and verify that `next_step` is real.
3. Generate `moltbook-payload.json` and `moltbook-status.md`.
4. Run `sync-moltbook --dry-run` to preview the package.
5. Run `sync-moltbook --prepare` to mark the package as ready for human review.

## Commands

Dry run:

```bash
python3 scripts/ai_da_guan_jia.py sync-moltbook --run-id adagj-20260309-101500 --dry-run
```

Prepare:

```bash
python3 scripts/ai_da_guan_jia.py sync-moltbook --run-id adagj-20260309-101500 --prepare
```

Board aggregate:

```bash
python3 scripts/ai_da_guan_jia.py prepare-moltbook-board --board-id ai-da-guan-jia-overview
```

Semi-automatic publish:

```bash
python3 scripts/ai_da_guan_jia.py publish-moltbook --board-id ai-da-guan-jia-overview
python3 scripts/ai_da_guan_jia.py publish-moltbook --board-id ai-da-guan-jia-overview --apply
```

Verify visibility:

```bash
python3 scripts/ai_da_guan_jia.py verify-moltbook-publish --board-id ai-da-guan-jia-overview --published-url "https://www.moltbook.com/..."
```

## Output Contract

Each run directory must contain:

- `moltbook-payload.json`
- `moltbook-status.md`
- `moltbook-sync-result.json`

Each board directory must contain:

- `moltbook-board.json`
- `moltbook-board.md`
- `moltbook-publish-result.json`
- `moltbook-api-payload.json` when the API path is prepared

The Markdown summary must contain exactly these fields:

- task / project name
- current phase
- overall status
- owner skill / agent
- completed this round
- current blockers
- next step
- recent update
- run id / local evidence pointer

## Failure Handling

- If the URL is missing, keep the payload local and set `moltbook_sync_status=not_configured`.
- If the mode is unsupported, fail loudly and set `moltbook_sync_status=blocked`.
- If `next_step` is empty, fail before writing a misleading community summary.
- `ready_for_review` means the package or draft exists; it must never be reported as community-visible.
- Only mark `published` after page-open + visible content evidence + screenshot are all present.
- `publish-moltbook` should prefer API publish when a Moltbook API key is configured; otherwise it should probe multiple likely compose pages instead of checking only the homepage.
- Do not implement auto publish, auto login, or feedback writeback in V1.
