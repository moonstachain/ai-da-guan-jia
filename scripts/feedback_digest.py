#!/usr/bin/env python3
"""Aggregate longxia feedback files into the central feedback inbox.

Phase 2 deliverable:
- scan `artifacts/ai-da-guan-jia/clones/instances/longxia/feedback/`
- render `artifacts/ai-da-guan-jia/clones/current/feedback-inbox/longxia-YYYY-MM-DD.md`
- optionally mirror a Codex execution summary into COO_Collab_Log
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.clone03_common import (
    COLLAB_TABLE_NAME,
    INSTANCE_ID,
    INSTANCE_ROOT,
    ensure_dir,
    epoch_seconds,
    instance_paths,
    list_feedback_sources,
    load_feishu_api,
    local_date,
    render_feedback_digest,
    stable_log_id,
    summarize_feedback_sources,
    table_meta,
    upsert_record_by_primary,
    write_json_atomic,
)
RUNS_ROOT = REPO_ROOT / "artifacts" / "ai-da-guan-jia" / "runs"


def make_run_dir(run_name: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = RUNS_ROOT / datetime.now().date().isoformat() / f"adagj-{run_name}-{stamp}"
    ensure_dir(run_dir)
    return run_dir


def build_digest_payload(instance_id: str, collab_summary: str | None = None) -> dict[str, Any]:
    paths = instance_paths(instance_id)
    sources = list_feedback_sources(instance_id)
    summary = summarize_feedback_sources(sources)
    digest_md = render_feedback_digest(instance_id, sources, summary)
    digest_file = paths["feedback_inbox_dir"] / f"{instance_id}-{local_date()}.md"
    state_file = INSTANCE_ROOT / "clone-state" / "feedback-digest-state.json"
    payload = {
        "instance_id": instance_id,
        "source_count": len(sources),
        "source_files": [source.rel_path for source in sources],
        "completed": summary["completed"],
        "lessons": summary["lessons"],
        "proposals": summary["proposals"],
        "raw_notes": summary["raw_notes"],
        "digest_file": str(digest_file),
        "state_file": str(state_file),
        "digest_markdown": digest_md,
        "collab_summary": collab_summary or "",
    }
    return payload


def write_digest_files(payload: dict[str, Any]) -> None:
    digest_file = Path(payload["digest_file"])
    state_file = Path(payload["state_file"])
    ensure_dir(digest_file.parent)
    digest_file.write_text(payload["digest_markdown"], encoding="utf-8")
    state_payload = {
        "instance_id": payload["instance_id"],
        "source_count": payload["source_count"],
        "source_files": payload["source_files"],
        "last_digest_at": datetime.now(timezone.utc).isoformat(),
        "digest_file": payload["digest_file"],
        "completed": payload["completed"],
        "lessons": payload["lessons"],
        "proposals": payload["proposals"],
    }
    write_json_atomic(state_file, state_payload)


def write_collab_log(instance_id: str, summary: str) -> dict[str, Any]:
    api = load_feishu_api()
    meta = table_meta(instance_id, COLLAB_TABLE_NAME)
    date = local_date()
    log_id = stable_log_id(instance_id, date, "activation-collab")
    record = {
        "log_id": log_id,
        "timestamp": epoch_seconds(datetime.now(timezone.utc)),
        "actor": "Codex",
        "action_type": "execution",
        "summary": summary,
        "visibility": "both",
    }
    result = upsert_record_by_primary(
        api,
        app_token=meta["base_app_token"],
        table_id=meta["table_id"],
        primary_field=meta["primary_field"],
        record=record,
    )
    return {
        "log_id": log_id,
        "table_id": meta["table_id"],
        "base_app_token": meta["base_app_token"],
        "action": result["action"],
        "record_id": result["record_id"],
        "fields": record,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aggregate longxia feedback into the central inbox.")
    parser.add_argument("--instance", default=INSTANCE_ID)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--collab-log", action="store_true", help="Also write a COO_Collab_Log execution row.")
    parser.add_argument("--collab-summary", default="", help="Summary to use for the collab log record.")
    args = parser.parse_args(argv)

    instance_id = str(args.instance or INSTANCE_ID).strip() or INSTANCE_ID
    run_dir = make_run_dir("feedback-digest")
    payload = build_digest_payload(instance_id, collab_summary=str(args.collab_summary or "").strip() or None)
    report = {
        "instance_id": instance_id,
        "mode": "apply" if args.apply else "dry-run",
        "run_dir": str(run_dir),
        "digest_file": payload["digest_file"],
        "state_file": payload["state_file"],
        "source_count": payload["source_count"],
        "source_files": payload["source_files"],
        "completed": payload["completed"],
        "lessons": payload["lessons"],
        "proposals": payload["proposals"],
        "collab_log_requested": bool(args.collab_log),
    }
    if args.apply:
        write_digest_files(payload)
        report["digest_written"] = True
        if args.collab_log:
            collab_summary = payload["collab_summary"] or (
                f"{instance_id} feedback digest completed with {payload['source_count']} source files."
            )
            collab_result = write_collab_log(instance_id, collab_summary)
            report["collab_log"] = collab_result
    else:
        report["digest_markdown"] = payload["digest_markdown"]
        if args.collab_log:
            report["collab_log_preview"] = {
                "log_id": stable_log_id(instance_id, local_date(), "activation-collab"),
                "summary": payload["collab_summary"] or f"{instance_id} feedback digest preview with {payload['source_count']} source files.",
            }

    output_path = run_dir / "feedback-digest.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
