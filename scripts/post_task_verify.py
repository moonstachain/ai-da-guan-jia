#!/usr/bin/env python3
"""
post_task_verify.py - Task Spec 执行后的自动闭环验证与修复

This script is intentionally repair-first:
- It can auto-create or auto-update known closure patch rows in Feishu.
- It can audit INIT against the live Feishu strategic task tracker.
- It always writes verification_result.json under artifacts/ai-da-guan-jia/runs/YYYY-MM-DD/<run-id>/.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.feishu_deploy import FeishuBitableAPI  # noqa: E402
from scripts.create_kangbo_signal_tables import DEFAULT_ACCOUNT_ID, load_feishu_credentials  # noqa: E402


TASK_TRACKER_APP = "PVDgbdWYFaDLBiss0hlcM5WRnQc"
TASK_TRACKER_TABLE = "tblB9JQ4cROTBUnr"
INIT_PATH = REPO_ROOT / "yuanli-os-claude" / "CLAUDE-INIT.md"
PATCH_PATH = REPO_ROOT / "references" / "codex-closure-strategic-task-patch-4.json"
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "ai-da-guan-jia" / "runs"
DEFAULT_OWNER = "Codex"
DEFAULT_PROJECT = {
    "project_id": "R18",
    "project_name": "R18 三向量扩展 + 驾驶舱 2.0 + 康波智库",
    "project_status": "进行中",
}


FIELD_TYPE_NAME_BY_ID = {
    1: "text",
    2: "number",
    3: "single_select",
    4: "multi_select",
    5: "datetime",
    7: "checkbox",
}


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def load_client(account_id: str = DEFAULT_ACCOUNT_ID) -> FeishuBitableAPI:
    creds = load_feishu_credentials(account_id)
    os.environ["FEISHU_APP_ID"] = creds["app_id"]
    os.environ["FEISHU_APP_SECRET"] = creds["app_secret"]
    return FeishuBitableAPI(creds["app_id"], creds["app_secret"])


def load_patch_entries(patch_path: Path = PATCH_PATH) -> list[dict[str, Any]]:
    if not patch_path.exists():
        raise FileNotFoundError(f"missing closure patch file: {patch_path}")
    payload = json.loads(patch_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError(f"invalid patch payload in {patch_path}")
    return [item for item in payload if isinstance(item, dict) and item.get("task_id")]


def load_patch_index(patch_path: Path = PATCH_PATH) -> dict[str, dict[str, Any]]:
    return {str(item["task_id"]): item for item in load_patch_entries(patch_path)}


def _field_name(field: dict[str, Any]) -> str:
    return str(field.get("field_name") or field.get("name") or "").strip()


def _field_type(field: dict[str, Any]) -> int:
    try:
        return int(field.get("type") or 0)
    except (TypeError, ValueError):
        return 0


def field_map(api: FeishuBitableAPI) -> dict[str, dict[str, Any]]:
    fields = api.list_fields(TASK_TRACKER_APP, TASK_TRACKER_TABLE)
    return {name: field for field in fields if (name := _field_name(field))}


def records_by_task_id(api: FeishuBitableAPI) -> dict[str, dict[str, Any]]:
    records = api.list_records(TASK_TRACKER_APP, TASK_TRACKER_TABLE)
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        fields = record.get("fields") or {}
        task_id = str(fields.get("task_id") or "").strip()
        if task_id:
            indexed[task_id] = record
    return indexed


def _to_datetime_value(value: Any) -> int | str:
    if value in {"", None}:
        return ""
    if isinstance(value, (int, float)):
        integer = int(value)
        return integer // 1000 if abs(integer) >= 10**12 else integer
    text = str(value).strip()
    if not text:
        return ""
    if text.isdigit():
        integer = int(text)
        return integer // 1000 if abs(integer) >= 10**12 else integer
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return int(parsed.timestamp())
    except ValueError:
        return text


def _to_number_value(value: Any) -> int | float | str:
    if value in {"", None}:
        return ""
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    if not text:
        return ""
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return text


def normalize_value(field: dict[str, Any], value: Any) -> Any:
    field_type = _field_type(field)
    if field_type == 5:
        return _to_datetime_value(value)
    if field_type == 2:
        return _to_number_value(value)
    if field_type == 7:
        if isinstance(value, bool):
            return value
        if value in {"true", "True", 1, "1"}:
            return True
        if value in {"false", "False", 0, "0"}:
            return False
        return bool(value)
    if field_type == 4:
        if value in {"", None}:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()]
    if value in {"", None}:
        return ""
    return str(value)


def normalize_row(row: dict[str, Any], fields: dict[str, dict[str, Any]]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        if key == "record_id":
            continue
        field = fields.get(key)
        if not field:
            continue
        normalized_value = normalize_value(field, value)
        if normalized_value == "" or normalized_value == [] or normalized_value is None:
            continue
        normalized[key] = normalized_value
    return normalized


def compare_rows(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    diff: dict[str, Any] = {}
    for key, expected_value in expected.items():
        if actual.get(key) != expected_value:
            diff[key] = {"expected": expected_value, "actual": actual.get(key)}
    return diff


def infer_task_status(line: str) -> str:
    if "已完成" in line:
        return "已完成"
    if "进行中" in line:
        return "进行中"
    if "阻塞" in line:
        return "阻塞"
    if "待启动" in line:
        return "待启动"
    if "草案待审" in line:
        return "草案待审"
    if "已审批待执行" in line:
        return "已审批待执行"
    return "未知"


def extract_init_task_specs(init_path: Path = INIT_PATH) -> list[dict[str, str]]:
    if not init_path.exists():
        return []
    specs: list[dict[str, str]] = []
    pattern = re.compile(r"^\s*-\s+`?(?P<task_id>(?:TS|I)-[A-Z0-9-]+)`?\s+(?P<label>.*?)[：:]\s*(?P<desc>.*)$")
    for line in init_path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if not match:
            continue
        task_id = match.group("task_id").strip()
        label = match.group("label").strip()
        desc = match.group("desc").strip()
        specs.append(
            {
                "task_id": task_id,
                "task_name": label,
                "init_status": infer_task_status(desc or line),
                "raw_line": line.strip(),
            }
        )
    return specs


def merge_patch_fields(task_id: str, patch_index: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    patch = patch_index.get(task_id)
    if not patch:
        return None
    fields = dict(patch.get("fields") or {})
    if patch.get("operation") == "batch_create":
        fields.setdefault("owner", DEFAULT_OWNER)
        fields.update({key: value for key, value in DEFAULT_PROJECT.items() if key not in fields})
    return fields


def ensure_patch_rows(
    api: FeishuBitableAPI,
    *,
    patch_index: dict[str, dict[str, Any]],
    apply: bool,
) -> dict[str, Any]:
    fields = field_map(api)
    current_records = records_by_task_id(api)
    actions: list[dict[str, Any]] = []
    to_create: list[dict[str, Any]] = []
    to_update: list[dict[str, Any]] = []

    for task_id, patch in patch_index.items():
        desired_fields = merge_patch_fields(task_id, patch_index)
        if not desired_fields:
            continue
        normalized_desired = normalize_row(desired_fields, fields)
        current = current_records.get(task_id)
        if not current or not str(current.get("record_id") or "").strip():
            actions.append({"task_id": task_id, "action": "create", "fields": normalized_desired})
            to_create.append(normalized_desired)
            continue
        current_fields = current.get("fields") or {}
        normalized_current = normalize_row(current_fields, fields)
        diff = compare_rows(normalized_desired, normalized_current)
        if diff:
            actions.append(
                {
                    "task_id": task_id,
                    "action": "update",
                    "record_id": str(current.get("record_id") or "").strip(),
                    "diff": diff,
                }
            )
            to_update.append({"record_id": str(current.get("record_id") or "").strip(), "fields": normalized_desired})
        else:
            actions.append({"task_id": task_id, "action": "noop", "record_id": str(current.get("record_id") or "").strip()})

    if apply:
        if to_create:
            api.batch_create_records(TASK_TRACKER_APP, TASK_TRACKER_TABLE, to_create)
        if to_update:
            api.batch_update_records(TASK_TRACKER_APP, TASK_TRACKER_TABLE, to_update)

    refreshed = records_by_task_id(api)
    return {
        "patch_source": str(PATCH_PATH),
        "expected_patch_tasks": len(patch_index),
        "actions": actions,
        "created": sum(1 for item in actions if item["action"] == "create"),
        "updated": sum(1 for item in actions if item["action"] == "update"),
        "noop": sum(1 for item in actions if item["action"] == "noop"),
        "verified_patch_tasks": sum(1 for task_id in patch_index if task_id in refreshed),
    }


def repair_status_drift(
    api: FeishuBitableAPI,
    *,
    init_tasks: list[dict[str, str]],
    apply: bool,
) -> dict[str, Any]:
    fields = field_map(api)
    current_records = records_by_task_id(api)
    drift: list[dict[str, Any]] = []
    updates: list[dict[str, Any]] = []

    for spec in init_tasks:
        task_id = spec["task_id"]
        expected = spec["init_status"]
        if expected == "未知":
            continue
        current = current_records.get(task_id)
        if not current or not str(current.get("record_id") or "").strip():
            drift.append({"task_id": task_id, "reason": "missing_in_feishu", "expected_status": expected})
            continue
        actual = str((current.get("fields") or {}).get("task_status") or "").strip()
        if actual != expected:
            diff = {"task_status": {"expected": expected, "actual": actual}}
            drift.append({"task_id": task_id, "record_id": str(current.get("record_id") or "").strip(), "diff": diff})
            updates.append(
                {
                    "record_id": str(current.get("record_id") or "").strip(),
                    "fields": normalize_row({"task_status": expected}, fields),
                }
            )

    if apply and updates:
        api.batch_update_records(TASK_TRACKER_APP, TASK_TRACKER_TABLE, updates)

    refreshed = records_by_task_id(api)
    remaining_drift: list[dict[str, Any]] = []
    missing_in_feishu: list[dict[str, Any]] = []
    for spec in init_tasks:
        task_id = spec["task_id"]
        expected = spec["init_status"]
        current = refreshed.get(task_id)
        if not current:
            missing_in_feishu.append(spec)
            continue
        actual = str((current.get("fields") or {}).get("task_status") or "").strip()
        if expected != "未知" and actual != expected:
            remaining_drift.append(
                {
                    "task_id": task_id,
                    "record_id": str(current.get("record_id") or "").strip(),
                    "expected_status": expected,
                    "actual_status": actual,
                }
            )

    return {
        "init_total": len(init_tasks),
        "missing_in_feishu": missing_in_feishu,
        "status_drift": remaining_drift,
        "all_aligned": len(missing_in_feishu) == 0 and len(remaining_drift) == 0,
        "updates_applied": len(updates),
    }


def verify_single_task(
    api: FeishuBitableAPI,
    *,
    task_id: str,
    expected_status: str,
    patch_index: dict[str, dict[str, Any]],
    apply: bool,
) -> dict[str, Any]:
    fields = field_map(api)
    current_records = records_by_task_id(api)
    current = current_records.get(task_id)
    patch_fields = merge_patch_fields(task_id, patch_index)

    if not current or not str(current.get("record_id") or "").strip():
        if not patch_fields:
            return {
                "task_id": task_id,
                "result": "FAIL",
                "reason": f"task_id '{task_id}' not found and no patch payload is available",
                "action_required": "Add the task to the closure patch bundle or create it manually in Feishu.",
            }
        desired_fields = dict(patch_fields)
        desired_fields["task_status"] = expected_status or str(desired_fields.get("task_status") or "")
        normalized = normalize_row(desired_fields, fields)
        if apply:
            api.batch_create_records(TASK_TRACKER_APP, TASK_TRACKER_TABLE, [normalized])
        refreshed = records_by_task_id(api).get(task_id)
        return {
            "task_id": task_id,
            "result": "REPAIRED",
            "action": "create",
            "desired_status": expected_status,
            "fields_written": normalized,
            "feishu_status": str((refreshed or {}).get("fields", {}).get("task_status") or ""),
            "record_id": str((refreshed or {}).get("record_id") or ""),
        }

    current_fields = current.get("fields") or {}
    actual_status = str(current_fields.get("task_status") or "").strip()
    desired_fields = dict(patch_fields or {})
    desired_fields["task_status"] = expected_status or desired_fields.get("task_status") or actual_status
    normalized_desired = normalize_row(desired_fields, fields) if desired_fields else {"task_status": expected_status}
    diff = compare_rows({"task_status": expected_status}, {"task_status": actual_status})
    patch_diff = compare_rows(normalized_desired, normalize_row(current_fields, fields)) if patch_fields else diff
    if patch_diff and apply:
        api.batch_update_records(
            TASK_TRACKER_APP,
            TASK_TRACKER_TABLE,
            [{"record_id": str(current.get("record_id") or "").strip(), "fields": normalized_desired}],
        )
        current = records_by_task_id(api).get(task_id) or current
        current_fields = current.get("fields") or {}
        actual_status = str(current_fields.get("task_status") or "").strip()
        return {
            "task_id": task_id,
            "result": "REPAIRED",
            "action": "update",
            "record_id": str(current.get("record_id") or "").strip(),
            "desired_status": expected_status,
            "feishu_status": actual_status,
            "fields_written": normalized_desired,
        }

    if actual_status != expected_status:
        return {
            "task_id": task_id,
            "result": "DRIFT",
            "reason": f"Feishu status='{actual_status}' but expected='{expected_status}'",
            "record_id": str(current.get("record_id") or "").strip(),
            "action_required": f"Run batch_update to set status to '{expected_status}'",
        }

    if patch_diff:
        return {
            "task_id": task_id,
            "result": "DRIFT",
            "reason": "task row differs from closure patch bundle",
            "record_id": str(current.get("record_id") or "").strip(),
            "diff": patch_diff,
        }

    return {
        "task_id": task_id,
        "result": "PASS",
        "feishu_status": actual_status,
        "record_id": str(current.get("record_id") or "").strip(),
    }


def write_verification_result(result: dict[str, Any], run_id: str | None = None) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d")
    effective_run_id = run_id or f"adagj-post-task-verify-{now_stamp()}"
    run_dir = ARTIFACT_ROOT / stamp / effective_run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    output_path = run_dir / "verification_result.json"
    result["artifact_dir"] = str(run_dir)
    result["artifact_path"] = str(output_path)
    result["run_id"] = effective_run_id
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


def build_full_audit_result(api: FeishuBitableAPI, *, apply: bool, patch_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    before_count = len(records_by_task_id(api))
    patch_result = ensure_patch_rows(api, patch_index=patch_index, apply=apply)
    init_tasks = extract_init_task_specs()
    init_result = repair_status_drift(api, init_tasks=init_tasks, apply=apply)
    after_count = len(records_by_task_id(api))
    all_aligned = bool(patch_result["verified_patch_tasks"] == len(patch_index) and init_result["all_aligned"])
    result = {
        "mode": "full_audit",
        "audit_time": datetime.now().isoformat(),
        "feishu_total_before": before_count,
        "feishu_total_after": after_count,
        "patch_result": patch_result,
        "init_result": init_result,
        "all_aligned": all_aligned,
        "repair_applied": apply,
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Post-task Feishu alignment verification.")
    parser.add_argument("--task-id", help="Verify or repair a single task_id.")
    parser.add_argument("--expected-status", default="已完成", help="Expected status for --task-id.")
    parser.add_argument("--full-audit", action="store_true", help="Audit INIT against Feishu and repair known drift.")
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    args = parser.parse_args(argv)

    if not args.task_id and not args.full_audit:
        parser.error("Must specify --task-id or --full-audit")

    api = load_client(args.account_id)
    patch_index = load_patch_index()

    if args.full_audit:
        result = build_full_audit_result(api, apply=True, patch_index=patch_index)
    else:
        result = verify_single_task(
            api,
            task_id=str(args.task_id).strip(),
            expected_status=str(args.expected_status).strip() or "已完成",
            patch_index=patch_index,
            apply=True,
        )
        result["mode"] = "single_task"
        result["expected_status"] = str(args.expected_status).strip() or "已完成"
        result["repair_applied"] = result.get("result") in {"REPAIRED", "PASS"}
        result["all_aligned"] = result.get("result") in {"PASS", "REPAIRED"}
        result["audit_time"] = datetime.now().isoformat()

    output_path = write_verification_result(result)
    result["artifact_path"] = str(output_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result.get("all_aligned"):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
