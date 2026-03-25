#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.feishu_deploy import FeishuBitableAPI


APP_TOKEN = "PVDgbdWYFaDLBiss0hlcM5WRnQc"
TABLE_L0 = "tblhOrpxXp0hPzOu"
TABLE_STRATEGIC = "tblB9JQ4cROTBUnr"
TABLE_VECTOR = "tblx8lmiEkUzAnON"

STATUS_REPLACED = "已被PROJ-V2-CLONE替代"
DATE_MS = 1742860800000

L0_FIELDS = {
    "frontstage_focus": "PROJ-V2-CLONE Phase 1 完成，Phase 2 待启动",
    "runtime_state": "healthy",
    "risk_level": "low",
    "total_tests_passed": 464,
    "total_commits": 23,
    "pending_human_actions": 1,
    "system_blockers": 0,
    "last_evolution_status": "completed",
}

GROUP2_CREATE_ROWS = [
    {
        "task_id": "PROJ-V2-CLONE-01",
        "project_id": "PROJ-V2-CLONE",
        "project_name": "V2同事复制产品化",
        "project_status": "进行中",
        "task_name": "Phase 1: Shared-Core Scaffold + Clone-Seed + Probe适配",
        "task_status": "已完成",
        "priority": "P0",
        "owner": "Codex",
        "start_date": DATE_MS,
        "completion_date": DATE_MS,
        "evidence_ref": "commits: c24c16c, 971e127, 19ca3cb, 271c494",
        "notes": "4个atomic commits。控制面14文件+longxia实例+clone-seed+probe --instance。",
    },
    {
        "task_id": "PROJ-V2-CLONE-02",
        "project_id": "PROJ-V2-CLONE",
        "project_name": "V2同事复制产品化",
        "project_status": "进行中",
        "task_name": "Phase 2: Feishu MVP Cockpit + Health Probe激活",
        "task_status": "待启动",
        "priority": "P0",
        "owner": "Codex",
        "blockers": "等待clone Base飞书坐标",
        "dependencies": "PROJ-V2-CLONE-01",
        "notes": "4张飞书表 + health-probe cron + sync-agent live测试",
    },
    {
        "task_id": "PROJ-V2-CLONE-03",
        "project_id": "PROJ-V2-CLONE",
        "project_name": "V2同事复制产品化",
        "project_status": "进行中",
        "task_name": "Phase 3: COLLEAGUE-INIT激活 + Feedback Loop",
        "task_status": "待启动",
        "priority": "P1",
        "owner": "Codex",
        "dependencies": "PROJ-V2-CLONE-02",
        "notes": "COLLEAGUE-INIT + 激活SOP + feedback-digest + Day 6 dogfood",
    },
]

GROUP2_COMPLETION_UPDATES = [
    {"task_id": "TS-V1-01", "fields": {"completion_date": DATE_MS}},
    {"task_id": "TS-MIRROR-02", "fields": {"completion_date": DATE_MS}},
    {"task_id": "TS-MIRROR-02A", "fields": {"completion_date": DATE_MS}},
]

GROUP3_CREATE_ROWS = [
    {
        "task_id": "PROJ-V2-CLONE-01",
        "task_name": "Phase 1: Scaffold + Clone-Seed + Probe",
        "vector": "V2",
        "phase": "P0",
        "week": 1,
        "executor": "Codex",
        "status": "已完成",
        "start_date": DATE_MS,
        "completion_date": DATE_MS,
        "handoff_summary": "控制面14文件 + longxia实例 + clone-seed + probe --instance",
    },
    {
        "task_id": "PROJ-V2-CLONE-02",
        "task_name": "Phase 2: Feishu MVP Cockpit + Health Probe",
        "vector": "V2",
        "phase": "P0",
        "week": 1,
        "executor": "Codex",
        "status": "待启动",
        "dependencies": "PROJ-V2-CLONE-01",
        "blockers": "等待clone Base飞书坐标",
    },
    {
        "task_id": "PROJ-V2-CLONE-03",
        "task_name": "Phase 3: Activation + Feedback Loop",
        "vector": "V2",
        "phase": "P1",
        "week": 1,
        "executor": "Codex",
        "status": "待启动",
        "dependencies": "PROJ-V2-CLONE-02",
    },
]

GROUP3_STATUS_UPDATES = [
    {"task_id": "TS-V2-02", "fields": {"status": STATUS_REPLACED}},
    {"task_id": "TS-V2-03", "fields": {"status": STATUS_REPLACED}},
    {"task_id": "TS-V2-04", "fields": {"status": STATUS_REPLACED}},
    {"task_id": "TS-V2-05", "fields": {"status": STATUS_REPLACED}},
]

GROUP4_ROW = {
    "task_id": "PROJ-FEISHU-FIX-01",
    "project_id": "PROJ-FEISHU-FIX",
    "project_name": "飞书数据质量P0修复",
    "project_status": "已完成",
    "task_name": "L0修复 + 战略任务补写 + 三向量更新 + 龙虾表归档",
    "task_status": "已完成",
    "priority": "P0",
    "owner": "Codex",
    "start_date": DATE_MS,
    "completion_date": DATE_MS,
    "evidence_ref": "commit f4911d9 + feishu-fix-partial-report.md + verification_result.json",
    "notes": "P0紧急修复4项。T1-T3 Codex完成，T4 Ray手动归档龙虾表。",
}

L0_SKIPPED_FIELDS = ["active_round", "last_evolution_round", "last_refresh"]


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def load_client() -> FeishuBitableAPI:
    app_id = str(os.environ.get("FEISHU_APP_ID") or "").strip()
    app_secret = str(os.environ.get("FEISHU_APP_SECRET") or "").strip()
    if not app_id or not app_secret:
        raise RuntimeError("Missing FEISHU_APP_ID or FEISHU_APP_SECRET")
    return FeishuBitableAPI(app_id, app_secret)


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def retry(label: str, func: Any, *, attempts: int = 5, base_delay: float = 1.5) -> Any:
    last_exc: Exception | None = None
    for index in range(attempts):
        try:
            return func()
        except (TimeoutError, URLError, ConnectionError, OSError) as exc:
            last_exc = exc
            if index + 1 >= attempts:
                break
            delay = base_delay * (2**index)
            print(f"[proj-feishu-fix-01] retry {label} after {exc!r} in {delay:.1f}s", file=sys.stderr)
            time.sleep(delay)
    assert last_exc is not None
    raise last_exc


def field_lookup(api: FeishuBitableAPI, table_id: str) -> dict[str, dict[str, Any]]:
    fields = retry(f"list_fields:{table_id}", lambda: api.list_fields(APP_TOKEN, table_id))
    return {
        str(field.get("field_name") or field.get("name") or "").strip(): field
        for field in fields
        if str(field.get("field_name") or field.get("name") or "").strip()
    }


def records_by_task_id(api: FeishuBitableAPI, table_id: str) -> dict[str, dict[str, Any]]:
    records = retry(f"list_records:{table_id}", lambda: api.list_records(APP_TOKEN, table_id))
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        fields = record.get("fields") or {}
        task_id = str(fields.get("task_id") or "").strip()
        if task_id:
            indexed[task_id] = record
    return indexed


def first_record(api: FeishuBitableAPI, table_id: str) -> dict[str, Any]:
    records = retry(f"first_record:{table_id}", lambda: api.list_records(APP_TOKEN, table_id))
    if not records:
        raise RuntimeError(f"table {table_id} has no records")
    return records[0]


def compare_subset(actual: dict[str, Any], expected: dict[str, Any]) -> dict[str, dict[str, Any]]:
    diff: dict[str, dict[str, Any]] = {}
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if str(actual_value) != str(expected_value):
            diff[key] = {"expected": expected_value, "actual": actual_value}
    return diff


def split_upsert_rows(
    api: FeishuBitableAPI,
    table_id: str,
    desired_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    current = records_by_task_id(api, table_id)
    to_create: list[dict[str, Any]] = []
    to_update: list[dict[str, Any]] = []
    for row in desired_rows:
        task_id = str(row.get("task_id") or "").strip()
        if not task_id:
            continue
        existing = current.get(task_id)
        if existing:
            record_id = str(existing.get("record_id") or existing.get("id") or "").strip()
            if record_id:
                to_update.append({"record_id": record_id, "fields": row})
        else:
            to_create.append(row)
    return to_create, to_update


def ensure_single_select_option(
    api: FeishuBitableAPI,
    table_id: str,
    field_name: str,
    option_name: str,
    *,
    apply_changes: bool,
) -> dict[str, Any]:
    fields = field_lookup(api, table_id)
    field = fields.get(field_name)
    if not field:
        raise RuntimeError(f"missing field {field_name} on table {table_id}")
    options = list(((field.get("property") or {}).get("options") or []))
    existing_names = {str(option.get("name") or "").strip() for option in options if str(option.get("name") or "").strip()}
    if option_name in existing_names:
        return {"field_name": field_name, "option_name": option_name, "missing": False, "patched": False}
    if not apply_changes:
        return {"field_name": field_name, "option_name": option_name, "missing": True, "patched": False}

    merged: list[dict[str, Any]] = []
    for option in options:
        name = str(option.get("name") or "").strip()
        if not name:
            continue
        cleaned: dict[str, Any] = {"name": name}
        if option.get("id"):
            cleaned["id"] = option["id"]
        if option.get("color") is not None:
            cleaned["color"] = option["color"]
        merged.append(cleaned)
    merged.append({"name": option_name})
    retry(
        f"update_field_option:{table_id}:{field_name}",
        lambda: api._request(
            f"/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{table_id}/fields/{field['field_id']}",
            method="PUT",
            payload={
                "field_name": field_name,
                "type": int(field.get("type") or 3),
                "property": {"options": merged},
            },
        ),
    )
    return {"field_name": field_name, "option_name": option_name, "missing": False, "patched": True}


def apply_batch_create(api: FeishuBitableAPI, table_id: str, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    retry(f"batch_create:{table_id}", lambda: api.batch_create_records(APP_TOKEN, table_id, rows))
    return len(rows)


def apply_batch_update(api: FeishuBitableAPI, table_id: str, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    retry(f"batch_update:{table_id}", lambda: api.batch_update_records(APP_TOKEN, table_id, rows))
    return len(rows)


def plan_group1(api: FeishuBitableAPI) -> dict[str, Any]:
    record = first_record(api, TABLE_L0)
    record_id = str(record.get("record_id") or record.get("id") or "").strip()
    actual = record.get("fields") or {}
    return {
        "table_id": TABLE_L0,
        "record_id": record_id,
        "update_fields": dict(L0_FIELDS),
        "skipped_fields": list(L0_SKIPPED_FIELDS),
        "current_snapshot": {key: actual.get(key) for key in list(L0_FIELDS) + L0_SKIPPED_FIELDS},
    }


def run_group1(api: FeishuBitableAPI, *, apply_changes: bool) -> dict[str, Any]:
    plan = plan_group1(api)
    result = {"group": 1, "plan": plan}
    if not apply_changes:
        result["mode"] = "dry-run"
        return result
    apply_batch_update(api, TABLE_L0, [{"record_id": plan["record_id"], "fields": dict(L0_FIELDS)}])
    actual = first_record(api, TABLE_L0).get("fields") or {}
    result["mode"] = "apply"
    result["applied"] = True
    result["verification"] = {
        "record_id": plan["record_id"],
        "ok": not compare_subset(actual, L0_FIELDS),
        "diff": compare_subset(actual, L0_FIELDS),
        "skipped_fields": list(L0_SKIPPED_FIELDS),
    }
    return result


def plan_group2(api: FeishuBitableAPI) -> dict[str, Any]:
    existing = records_by_task_id(api, TABLE_STRATEGIC)
    create_rows, update_rows = split_upsert_rows(api, TABLE_STRATEGIC, GROUP2_CREATE_ROWS)
    completion_updates: list[dict[str, Any]] = []
    for item in GROUP2_COMPLETION_UPDATES:
        task_id = item["task_id"]
        current = existing.get(task_id)
        if not current:
            raise RuntimeError(f"missing expected strategic task record: {task_id}")
        record_id = str(current.get("record_id") or current.get("id") or "").strip()
        completion_updates.append({"record_id": record_id, "fields": dict(item["fields"])})
    return {
        "table_id": TABLE_STRATEGIC,
        "create_rows": create_rows,
        "update_rows": update_rows + completion_updates,
        "completion_updates": completion_updates,
    }


def run_group2(api: FeishuBitableAPI, *, apply_changes: bool) -> dict[str, Any]:
    plan = plan_group2(api)
    result = {"group": 2, "plan": plan}
    if not apply_changes:
        result["mode"] = "dry-run"
        return result

    created = apply_batch_create(api, TABLE_STRATEGIC, plan["create_rows"])
    updated = apply_batch_update(api, TABLE_STRATEGIC, plan["update_rows"])
    current = records_by_task_id(api, TABLE_STRATEGIC)
    verification: dict[str, Any] = {"created": [], "updated": []}
    for row in GROUP2_CREATE_ROWS:
        actual = (current.get(str(row["task_id"])) or {}).get("fields") or {}
        verification["created"].append(
            {
                "task_id": row["task_id"],
                "ok": not compare_subset(actual, row),
                "diff": compare_subset(actual, row),
            }
        )
    for item in GROUP2_COMPLETION_UPDATES:
        actual = (current.get(str(item["task_id"])) or {}).get("fields") or {}
        verification["updated"].append(
            {
                "task_id": item["task_id"],
                "ok": not compare_subset(actual, item["fields"]),
                "diff": compare_subset(actual, item["fields"]),
            }
        )
    verification["ok"] = all(
        item["ok"] for item in verification["created"] + verification["updated"]
    )
    result["mode"] = "apply"
    result["applied"] = {"created": created, "updated": updated}
    result["verification"] = verification
    return result


def plan_group3(api: FeishuBitableAPI, *, apply_changes: bool) -> dict[str, Any]:
    option_state = ensure_single_select_option(
        api,
        TABLE_VECTOR,
        "status",
        STATUS_REPLACED,
        apply_changes=apply_changes,
    )
    create_rows, update_rows = split_upsert_rows(api, TABLE_VECTOR, GROUP3_CREATE_ROWS)
    existing = records_by_task_id(api, TABLE_VECTOR)
    status_updates: list[dict[str, Any]] = []
    for item in GROUP3_STATUS_UPDATES:
        task_id = item["task_id"]
        current = existing.get(task_id)
        if not current:
            raise RuntimeError(f"missing expected vector task record: {task_id}")
        record_id = str(current.get("record_id") or current.get("id") or "").strip()
        status_updates.append({"record_id": record_id, "fields": dict(item["fields"])})
    return {
        "table_id": TABLE_VECTOR,
        "schema_patch": option_state,
        "create_rows": create_rows,
        "update_rows": update_rows + status_updates,
    }


def run_group3(api: FeishuBitableAPI, *, apply_changes: bool) -> dict[str, Any]:
    plan = plan_group3(api, apply_changes=apply_changes)
    result = {"group": 3, "plan": plan}
    if not apply_changes:
        result["mode"] = "dry-run"
        return result

    patched = plan["schema_patch"].get("patched")
    created = apply_batch_create(api, TABLE_VECTOR, plan["create_rows"])
    updated = apply_batch_update(api, TABLE_VECTOR, plan["update_rows"])
    current = records_by_task_id(api, TABLE_VECTOR)
    verification: dict[str, Any] = {"patched_option": bool(patched), "created": [], "updated": []}
    for row in GROUP3_CREATE_ROWS:
        actual = (current.get(str(row["task_id"])) or {}).get("fields") or {}
        verification["created"].append(
            {
                "task_id": row["task_id"],
                "ok": not compare_subset(actual, row),
                "diff": compare_subset(actual, row),
            }
        )
    for item in GROUP3_STATUS_UPDATES:
        actual = (current.get(str(item["task_id"])) or {}).get("fields") or {}
        verification["updated"].append(
            {
                "task_id": item["task_id"],
                "ok": not compare_subset(actual, item["fields"]),
                "diff": compare_subset(actual, item["fields"]),
            }
        )
    verification["ok"] = bool(plan["schema_patch"].get("patched") or not plan["schema_patch"].get("missing")) and all(
        item["ok"] for item in verification["created"] + verification["updated"]
    )
    result["mode"] = "apply"
    result["applied"] = {"patched_option": bool(patched), "created": created, "updated": updated}
    result["verification"] = verification
    return result


def plan_group4(api: FeishuBitableAPI) -> dict[str, Any]:
    create_rows, update_rows = split_upsert_rows(api, TABLE_STRATEGIC, [GROUP4_ROW])
    return {"table_id": TABLE_STRATEGIC, "create_rows": create_rows, "update_rows": update_rows}


def run_group4(api: FeishuBitableAPI, *, apply_changes: bool) -> dict[str, Any]:
    plan = plan_group4(api)
    result = {"group": 4, "plan": plan}
    if not apply_changes:
        result["mode"] = "dry-run"
        return result

    created = apply_batch_create(api, TABLE_STRATEGIC, plan["create_rows"])
    updated = apply_batch_update(api, TABLE_STRATEGIC, plan["update_rows"])
    current = records_by_task_id(api, TABLE_STRATEGIC)
    actual = (current.get("PROJ-FEISHU-FIX-01") or {}).get("fields") or {}
    result["mode"] = "apply"
    result["applied"] = {"created": created, "updated": updated}
    result["verification"] = {
        "task_id": "PROJ-FEISHU-FIX-01",
        "ok": not compare_subset(actual, GROUP4_ROW),
        "diff": compare_subset(actual, GROUP4_ROW),
    }
    return result


def build_dry_run_result(api: FeishuBitableAPI) -> dict[str, Any]:
    return {
        "mode": "dry-run",
        "run_id": None,
        "created_at": datetime.now().isoformat(),
        "groups": {
            "group1": plan_group1(api),
            "group2": plan_group2(api),
            "group3": plan_group3(api, apply_changes=False),
            "group4": plan_group4(api),
        },
    }


def build_apply_result(api: FeishuBitableAPI) -> dict[str, Any]:
    group_results = {
        "group1": run_group1(api, apply_changes=True),
        "group2": run_group2(api, apply_changes=True),
        "group3": run_group3(api, apply_changes=True),
        "group4": run_group4(api, apply_changes=True),
    }
    verification = {
        "status": "completed",
        "all_aligned": all(
            group_results[key]["verification"]["ok"] for key in ["group1", "group2", "group3", "group4"]
        ),
        "evidence": {
            "group1": group_results["group1"]["verification"],
            "group2": group_results["group2"]["verification"],
            "group3": group_results["group3"]["verification"],
            "group4": group_results["group4"]["verification"],
        },
        "open_questions": [],
    }
    return {
        "mode": "apply",
        "run_id": None,
        "created_at": datetime.now().isoformat(),
        "groups": group_results,
        "verification_result": verification,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the PROJ-FEISHU-FIX-01 Feishu API write sequence.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Plan all four groups without writing to Feishu.")
    mode.add_argument("--apply", action="store_true", help="Apply all four groups to Feishu in order.")
    parser.add_argument(
        "--run-dir",
        default="",
        help="Optional artifact directory. Defaults to artifacts/ai-da-guan-jia/runs/YYYY-MM-DD/<run-id>/.",
    )
    return parser.parse_args(argv)


def default_run_dir(mode_name: str) -> Path:
    now = datetime.now()
    return (
        REPO_ROOT
        / "artifacts"
        / "ai-da-guan-jia"
        / "runs"
        / now.strftime("%Y-%m-%d")
        / f"adagj-{now.strftime('%Y%m%d-%H%M%S')}-feishu-fix-01-sync-{mode_name}"
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    mode_name = "dry-run" if args.dry_run else "apply"
    run_dir = Path(args.run_dir).expanduser().resolve() if args.run_dir else default_run_dir(mode_name)
    run_dir.mkdir(parents=True, exist_ok=True)

    api = load_client()
    print(f"[proj-feishu-fix-01] mode={mode_name} run_dir={run_dir}")

    if args.dry_run:
        result = build_dry_run_result(api)
        result["run_id"] = run_dir.name
        result["artifact_dir"] = str(run_dir)
        result["artifact_path"] = str(write_json(run_dir / "dry-run.json", result))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    result = build_apply_result(api)
    result["run_id"] = run_dir.name
    result["artifact_dir"] = str(run_dir)
    result["artifact_path"] = str(write_json(run_dir / "apply.json", result))
    verification = dict(result["verification_result"])
    verification["artifact_dir"] = str(run_dir)
    verification["artifact_path"] = str(write_json(run_dir / "verification_result.json", verification))
    result["verification_result"] = verification
    write_json(run_dir / "apply.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if verification.get("all_aligned") else 1


if __name__ == "__main__":
    raise SystemExit(main())
