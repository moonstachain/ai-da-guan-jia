from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.sync_r11_v2_skill_inventory_feishu import bootstrap_client
from scripts.sync_governance_dashboard_base import api, list_fields, list_records


PVDG_BASE = "PVDgbdWYFaDLBiss0hlcM5WRnQc"
VECTOR_TABLE_ID = "tblx8lmiEkUzAnON"
COLLAB_TABLE_ID = "tbl67a3vUXDaIjRF"
TASK_ID_RE = re.compile(r"TS-[A-Z0-9-]+(?=[^A-Z0-9-]|$)")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply dashboard close-task hooks for TS-* runs.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--run-dir", required=True)
    return parser.parse_args(argv)


def compare_key(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str("" if value is None else value).strip()


def normalize_fields(fields: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in fields.items():
        if value is None:
            continue
        if value == "":
            continue
        normalized[key] = value
    return normalized


def upsert_rows(
    client: Any,
    app_token: str,
    table_id: str,
    primary_field: str,
    rows: list[dict[str, Any]],
    *,
    dry_run: bool,
    preserve_empty_fields: set[str] | None = None,
) -> list[dict[str, Any]]:
    existing = {
        compare_key((row.get("fields") or {}).get(primary_field)): row
        for row in list_records(client, app_token, table_id)
    }
    results: list[dict[str, Any]] = []
    keep_empty = preserve_empty_fields or set()
    for raw in rows:
        fields = normalize_fields(raw)
        for key in keep_empty:
            if key in raw and raw[key] == "":
                fields[key] = ""
        key = compare_key(fields.get(primary_field))
        current = existing.get(key)
        action = "update" if current else "create"
        if dry_run:
            results.append({"action": action, "primary_value": key, "fields": fields})
            continue
        if current:
            record_id = str(current.get("record_id") or current.get("id") or "").strip()
            api(client, "PUT", f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}", {"fields": fields})
            results.append({"action": "update", "primary_value": key, "record_id": record_id})
        else:
            payload = api(client, "POST", f"/bitable/v1/apps/{app_token}/tables/{table_id}/records", {"fields": fields})
            record = ((payload.get("data") or {}).get("record") or {})
            results.append(
                {
                    "action": "create",
                    "primary_value": key,
                    "record_id": str(record.get("record_id") or record.get("id") or "").strip(),
                }
            )
    return results


def count_actions(rows: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"create": 0, "update": 0}
    for row in rows:
        summary[row["action"]] += 1
    return summary


def now_ms() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp() * 1000)


def extract_task_id(task_text: str) -> str:
    match = TASK_ID_RE.search(task_text or "")
    return match.group(0) if match else ""


def normalize_vector_status(status: str) -> str:
    lowered = str(status or "").strip().lower()
    if lowered in {"completed", "success", "passed", "done"}:
        return "已完成"
    if lowered in {"blocked", "apply_blocked_missing_credentials", "dry_run_failed"}:
        return "阻塞"
    if lowered in {"failed", "error", "partial"}:
        return "失败"
    return "进行中"


def summarize_text(text: str, limit: int = 120) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def build_collab_row(evolution: dict[str, Any], worklog: dict[str, Any], task_id: str) -> dict[str, Any]:
    timestamp = now_ms()
    verification = (evolution.get("verification_result") or {}) if isinstance(evolution.get("verification_result"), dict) else {}
    status = str(verification.get("status") or "")
    run_id = str(evolution.get("run_id") or worklog.get("run_id") or "").strip()
    summary = summarize_text(
        worklog.get("completion_summary")
        or worklog.get("verification_evidence_summary")
        or evolution.get("task_text")
        or task_id
    )
    row = {
        "interaction_id": f"triparty-close-{run_id}" if run_id else f"triparty-{timestamp}",
        "timestamp": timestamp,
        "from_role": "Codex",
        "to_role": "Human",
        "interaction_type": "task_close" if status not in {"blocked", "failed", "error"} else "evidence",
        "summary": summary,
        "round_ref": task_id,
        "quality_score": 5 if normalize_vector_status(status) == "已完成" else 4,
    }
    return row


def build_vector_row(evolution: dict[str, Any], worklog: dict[str, Any], task_id: str) -> dict[str, Any]:
    verification = (evolution.get("verification_result") or {}) if isinstance(evolution.get("verification_result"), dict) else {}
    status = normalize_vector_status(str(verification.get("status") or ""))
    summary = summarize_text(
        worklog.get("completion_summary")
        or worklog.get("verification_evidence_summary")
        or evolution.get("task_text")
        or task_id
    )
    row: dict[str, Any] = {
        "task_id": task_id,
        "status": status,
        "handoff_summary": summary,
    }
    if status == "已完成":
        row["completion_date"] = now_ms()
        row["blockers"] = ""
    else:
        open_questions = verification.get("open_questions") or []
        blockers = " | ".join(str(item).strip() for item in open_questions if str(item).strip())
        if blockers:
            row["blockers"] = blockers
    return row


def build_result(
    *,
    mode: str,
    task_id: str,
    collab_actions: list[dict[str, Any]],
    vector_actions: list[dict[str, Any]],
    run_dir: Path,
    status: str,
    reason: str = "",
) -> dict[str, Any]:
    result = {
        "mode": mode,
        "status": status,
        "task_id": task_id,
        "executed_at": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
        "reason": reason,
        "collab_action_summary": count_actions(collab_actions),
        "vector_action_summary": count_actions(vector_actions),
    }
    filename = f"dashboard-close-hooks-{mode}.json"
    result_path = run_dir / filename
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result["result_path"] = str(result_path)
    return result


def run_hooks(*, run_dir: Path, apply_changes: bool) -> dict[str, Any]:
    evolution_path = run_dir / "evolution.json"
    worklog_path = run_dir / "worklog.json"
    if not evolution_path.exists() or not worklog_path.exists():
        raise FileNotFoundError("run_dir must contain evolution.json and worklog.json")

    evolution = json.loads(evolution_path.read_text(encoding="utf-8"))
    worklog = json.loads(worklog_path.read_text(encoding="utf-8"))
    task_text = str(evolution.get("task_text") or "")
    task_id = extract_task_id(task_text)
    mode = "apply" if apply_changes else "dry-run"
    if not task_id:
        return build_result(
            mode=mode,
            task_id="",
            collab_actions=[],
            vector_actions=[],
            run_dir=run_dir,
            status="skipped_not_ts_task",
            reason="task_text did not contain a TS-* identifier",
        )

    client = bootstrap_client()
    collab_row = build_collab_row(evolution, worklog, task_id)
    vector_row = build_vector_row(evolution, worklog, task_id)
    collab_actions = upsert_rows(client, PVDG_BASE, COLLAB_TABLE_ID, "interaction_id", [collab_row], dry_run=not apply_changes)
    vector_actions = upsert_rows(client, PVDG_BASE, VECTOR_TABLE_ID, "task_id", [vector_row], dry_run=not apply_changes)
    return build_result(
        mode=mode,
        task_id=task_id,
        collab_actions=collab_actions,
        vector_actions=vector_actions,
        run_dir=run_dir,
        status="dashboard_hook_applied" if apply_changes else "dashboard_hook_preview_ready",
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_hooks(run_dir=Path(args.run_dir), apply_changes=bool(args.apply))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
