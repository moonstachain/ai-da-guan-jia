#!/usr/bin/env python3
"""Task-specific closeout for PROJ-V2-CLONE-03."""

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
    EVOLUTION_TABLE_NAME,
    INSTANCE_ID,
    TASK_TRACKER_NAME,
    TASK_TRACKER_RECORD_ID,
    epoch_seconds,
    load_feishu_api,
    local_date,
    table_meta,
    upsert_record_by_primary,
    write_json_atomic,
)
RUNS_ROOT = REPO_ROOT / "artifacts" / "ai-da-guan-jia" / "runs"
FEEDBACK_DIGEST = REPO_ROOT / "scripts" / "feedback_digest.py"
DOGFOOD_VERIFY = REPO_ROOT / "scripts" / "dogfood_verify.py"
STRATEGIC_TASK_APP = "PVDgbdWYFaDLBiss0hlcM5WRnQc"
STRATEGIC_TASK_TABLE = "tblB9JQ4cROTBUnr"


def make_run_dir(run_name: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = RUNS_ROOT / datetime.now().date().isoformat() / f"adagj-{run_name}-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_clone_task_tracker_row(instance_id: str) -> dict[str, Any]:
    api = load_feishu_api()
    meta = table_meta(instance_id, TASK_TRACKER_NAME)
    now = datetime.now(timezone.utc)
    record = {
        "task_id": TASK_TRACKER_RECORD_ID,
        "task_name": "COLLEAGUE-INIT 激活引导 + Feedback Loop",
        "status": "completed",
        "priority": "P0",
        "owner": "Codex",
        "evidence": "artifacts/ai-da-guan-jia/clones/instances/longxia/CLONE-INIT.md;docs/onboarding-sop.md;docs/activation-prompt.md;scripts/feedback_digest.py;scripts/dogfood_verify.py",
        "start_date": epoch_seconds(now),
        "completion_date": epoch_seconds(now),
        "notes": "Phase 1-3 deliverables landed; dogfood verify script ready.",
    }
    result = upsert_record_by_primary(
        api,
        app_token=meta["base_app_token"],
        table_id=meta["table_id"],
        primary_field=meta["primary_field"],
        record=record,
    )
    return {
        "table_name": TASK_TRACKER_NAME,
        "table_id": meta["table_id"],
        "primary_value": TASK_TRACKER_RECORD_ID,
        "action": result["action"],
        "record_id": result["record_id"],
        "fields": record,
    }


def write_strategic_task_row(instance_id: str) -> dict[str, Any]:
    api = load_feishu_api()
    now = datetime.now(timezone.utc)
    record = {
        "task_id": TASK_TRACKER_RECORD_ID,
        "project_id": "PROJ-V2-CLONE",
        "project_name": "PROJ-V2-CLONE 人机激活工厂",
        "project_status": "进行中",
        "task_name": "COLLEAGUE-INIT 激活引导 + Feedback Loop",
        "task_status": "已完成",
        "priority": "P0",
        "owner": "Codex",
        "start_date": epoch_seconds(now),
        "completion_date": epoch_seconds(now),
        "blockers": "",
        "evidence_ref": "artifacts/ai-da-guan-jia/clones/instances/longxia/CLONE-INIT.md;docs/onboarding-sop.md;docs/activation-prompt.md;scripts/feedback_digest.py;scripts/dogfood_verify.py",
        "dependencies": "PROJ-V2-CLONE-01, PROJ-V2-CLONE-02",
        "notes": "Phase 1-3 deliverables landed; dogfood verify script ready.",
    }
    result = upsert_record_by_primary(
        api,
        app_token=STRATEGIC_TASK_APP,
        table_id=STRATEGIC_TASK_TABLE,
        primary_field="task_id",
        record=record,
    )
    return {
        "table_name": "战略任务追踪表",
        "table_id": STRATEGIC_TASK_TABLE,
        "primary_value": TASK_TRACKER_RECORD_ID,
        "action": result["action"],
        "record_id": result["record_id"],
        "fields": record,
    }


def write_evolution_row(instance_id: str) -> dict[str, Any]:
    api = load_feishu_api()
    meta = table_meta(instance_id, EVOLUTION_TABLE_NAME)
    today = local_date()
    run_id = f"{TASK_TRACKER_RECORD_ID}-{today}"
    record = {
        "run_id": run_id,
        "date": epoch_seconds(datetime.now(timezone.utc)),
        "task_ref": TASK_TRACKER_RECORD_ID,
        "input": "TaskSpec requested CLONE-INIT formalization, onboarding SOP, activation prompt, feedback-digest, collab-log automation, health-probe enhancement, and dogfood verify.",
        "output": "Delivered longxia CLONE-INIT V20, onboarding SOP, activation prompt, feedback_digest.py, dogfood_verify.py, and probe enhancements.",
        "lesson_learned": "Activation tasks need an explicit INIT version reminder, a human-readable SOP, and a machine-checkable dogfood report before the first real dogfood loop.",
    }
    result = upsert_record_by_primary(
        api,
        app_token=meta["base_app_token"],
        table_id=meta["table_id"],
        primary_field=meta["primary_field"],
        record=record,
    )
    return {
        "table_name": EVOLUTION_TABLE_NAME,
        "table_id": meta["table_id"],
        "primary_value": run_id,
        "action": result["action"],
        "record_id": result["record_id"],
        "fields": record,
    }


def run_subprocess(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    payload_text = completed.stdout.strip() or completed.stderr.strip()
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        payload = {"raw_output": payload_text}
    payload["returncode"] = completed.returncode
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Close out PROJ-V2-CLONE-03.")
    parser.add_argument("--instance", default=INSTANCE_ID)
    args = parser.parse_args(argv)

    instance_id = str(args.instance or INSTANCE_ID).strip() or INSTANCE_ID
    run_dir = make_run_dir("proj-v2-clone-03-closeout")
    summary = {
        "instance_id": instance_id,
        "run_dir": str(run_dir),
        "clone_task_tracker": write_clone_task_tracker_row(instance_id),
        "strategic_task_tracker": write_strategic_task_row(instance_id),
        "evolution_log": write_evolution_row(instance_id),
    }
    feedback_summary = (
        "PROJ-V2-CLONE-03 closeout: longxia CLONE-INIT V20, SOP, activation prompt, feedback digest, collab log, and dogfood verify delivered."
    )
    feedback_cmd = [
        "python3",
        str(FEEDBACK_DIGEST),
        "--instance",
        instance_id,
        "--apply",
        "--collab-log",
        "--collab-summary",
        feedback_summary,
    ]
    summary["feedback_digest"] = run_subprocess(feedback_cmd)

    health_cmd = ["python3", str(REPO_ROOT / "work" / "ai-da-guan-jia" / "tools" / "health_probe.py"), "--instance", instance_id]
    summary["health_probe"] = run_subprocess(health_cmd)

    verify_cmd = ["python3", str(DOGFOOD_VERIFY), "--instance", instance_id]
    summary["dogfood_verify"] = run_subprocess(verify_cmd)

    output_path = run_dir / "proj-v2-clone-03-closeout.json"
    write_json_atomic(output_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
