#!/usr/bin/env python3
"""Dogfood verification for PROJ-V2-CLONE-03."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.clone03_common import (
    COLLAB_TABLE_NAME,
    EVOLUTION_TABLE_NAME,
    INSTANCE_ID,
    TASK_TRACKER_NAME,
    TASK_TRACKER_RECORD_ID,
    instance_paths,
    load_feishu_api,
    local_date,
    stable_log_id,
    table_meta,
)
HEALTH_PROBE = REPO_ROOT / "work" / "ai-da-guan-jia" / "tools" / "health_probe.py"
RUNS_ROOT = REPO_ROOT / "artifacts" / "ai-da-guan-jia" / "runs"


def make_run_dir(run_name: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = RUNS_ROOT / datetime.now().date().isoformat() / f"adagj-{run_name}-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def list_records(api, app_token: str, table_id: str) -> list[dict[str, Any]]:
    return api.list_records(app_token, table_id)


def find_record(records: list[dict[str, Any]], primary_field: str, primary_value: str) -> dict[str, Any] | None:
    needle = str(primary_value or "").strip()
    for record in records:
        fields = record.get("fields") or {}
        if str(fields.get(primary_field) or "").strip() == needle:
            return record
    return None


def run_health_probe(instance_id: str) -> dict[str, Any]:
    command = ["python3", str(HEALTH_PROBE), "--instance", instance_id]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    payload_text = completed.stdout.strip() or completed.stderr.strip()
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        payload = {"ok": False, "error": payload_text or f"health probe failed with exit code {completed.returncode}"}
    payload["returncode"] = completed.returncode
    return payload


def verify(instance_id: str) -> dict[str, Any]:
    api = load_feishu_api()
    task_meta = table_meta(instance_id, TASK_TRACKER_NAME)
    collab_meta = table_meta(instance_id, COLLAB_TABLE_NAME)
    evo_meta = table_meta(instance_id, EVOLUTION_TABLE_NAME)
    paths = instance_paths(instance_id)
    today = local_date()

    task_records = list_records(api, task_meta["base_app_token"], task_meta["table_id"])
    task_record = find_record(task_records, task_meta["primary_field"], TASK_TRACKER_RECORD_ID)
    task_ok = bool(task_record) and str((task_record or {}).get("fields", {}).get("status") or "").strip() == "completed"

    evo_records = list_records(api, evo_meta["base_app_token"], evo_meta["table_id"])
    evo_record_id = f"{TASK_TRACKER_RECORD_ID}-{today}"
    evo_record = find_record(evo_records, evo_meta["primary_field"], evo_record_id)
    evo_ok = bool(evo_record) and str((evo_record or {}).get("fields", {}).get("task_ref") or "").strip() == TASK_TRACKER_RECORD_ID

    collab_records = list_records(api, collab_meta["base_app_token"], collab_meta["table_id"])
    collab_record_id = stable_log_id(instance_id, today, "activation-collab")
    collab_record = find_record(collab_records, collab_meta["primary_field"], collab_record_id)
    collab_ok = bool(collab_record) and str((collab_record or {}).get("fields", {}).get("action_type") or "").strip() == "execution"

    feedback_digest_path = paths["feedback_inbox_dir"] / f"{instance_id}-{today}.md"
    feedback_state_path = paths["clone_state_dir"] / "feedback-digest-state.json"
    health = run_health_probe(instance_id)
    feedback_ok = feedback_digest_path.exists() and feedback_digest_path.stat().st_size > 0

    checks = {
        "task_tracker": task_ok,
        "evolution_log": evo_ok,
        "collab_log": collab_ok,
        "feedback_digest": feedback_ok,
        "health_probe": bool(health.get("ok")),
    }
    report = {
        "instance_id": instance_id,
        "date": today,
        "checks": checks,
        "task_tracker_record": task_record or {},
        "evolution_log_record": evo_record or {},
        "collab_log_record": collab_record or {},
        "feedback_digest_path": str(feedback_digest_path),
        "feedback_digest_state_path": str(feedback_state_path),
        "health_probe": health,
        "all_passed": all(checks.values()),
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the longxia dogfood loop.")
    parser.add_argument("--instance", default=INSTANCE_ID)
    args = parser.parse_args(argv)

    instance_id = str(args.instance or INSTANCE_ID).strip() or INSTANCE_ID
    run_dir = make_run_dir("dogfood-verify")
    report = verify(instance_id)
    report["run_dir"] = str(run_dir)
    output_path = run_dir / "dogfood-verification-report.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
