# PROJ-TALENT-03 Scripts

This folder now includes a minimal S0 resume intake pipeline that stays offline-safe by default.

## Files

- `resume_parser.py`
  - Parse `PDF`, `DOCX`, or `TXT` resumes into normalized JSON.
- `resume_watcher.py`
  - Watch an inbox folder, parse resumes, call `talent_scorer.py` when present, and write to Feishu `T01/T02`.
- `email_collector.py`
  - Pull resume attachments or plain-text bodies from IMAP into the watcher inbox.
- `feishu_writer.py`
  - Write one parsed resume plus one score payload into Feishu and optionally notify A/B candidates.

## Runtime Layout

Default runtime folders live under `tmp/proj-talent-03/`:

- `inbox/`
- `parsed/`
- `scores/`
- `archive/`
- `error/`

## Dependencies

Required:

- Python 3.9+

Optional but recommended:

- `python-docx` for richer `DOCX` extraction
- `pdfplumber` or `pypdf` for `PDF` extraction
- `watchdog` for native filesystem watching
- `FEISHU_APP_ID` and `FEISHU_APP_SECRET`, or Feishu credentials in `~/.openclaw/openclaw.json`

## Quick Start

Parse one resume locally:

```bash
python3 scripts/resume_parser.py /path/to/resume.pdf --output tmp/proj-talent-03/parsed/sample.json
```

Dry-run the watcher once:

```bash
python3 scripts/resume_watcher.py process
```

Actually process queued resumes and write to Feishu:

```bash
python3 scripts/resume_watcher.py process --apply
```

Watch the inbox continuously:

```bash
python3 scripts/resume_watcher.py watch --apply --interval-seconds 5
```

Collect IMAP attachments into the inbox:

```bash
python3 scripts/email_collector.py \
  --host imap.example.com \
  --username recruiter@example.com \
  --password "$IMAP_PASSWORD" \
  --apply
```

Write one parsed resume and one score payload directly:

```bash
python3 scripts/feishu_writer.py \
  --resume-json tmp/proj-talent-03/parsed/sample.json \
  --score-json tmp/proj-talent-03/scores/sample.json \
  --apply
```

## Scorer Integration

`resume_watcher.py` does not implement the AI scorer itself. It looks for `scripts/talent_scorer.py` and runs:

```bash
python3 scripts/talent_scorer.py --resume-json {resume_json} --output {score_json}
```

You can override that with:

```bash
python3 scripts/resume_watcher.py process --scorer-command "python3 scripts/talent_scorer.py --resume-json {resume_json} --output {score_json}" --apply
```

If the scorer is missing or fails, the watcher falls back to a local heuristic score so the intake path remains runnable.

## Notifications

Notification is optional and only fires for grades in `S,A,B` by default.

- Bot webhook path:
  - `--notify-webhook https://open.feishu.cn/open-apis/bot/v2/hook/...`
- Internal Feishu message path:
  - `--notify-chat-id oc_xxx`

## Verification

1. Drop a `PDF`, `DOCX`, or `TXT` file into `tmp/proj-talent-03/inbox/`.
2. Run `python3 scripts/resume_watcher.py process`.
3. Confirm you get:
   - parsed JSON in `tmp/proj-talent-03/parsed/`
   - score JSON in `tmp/proj-talent-03/scores/`
   - dry-run Feishu payload summary in stdout
4. Re-run with `--apply` after Feishu credentials and scorer are ready.

## Scope Lock

- No crawler support
- No enterprise API signup flow
- No interview-stage automation
