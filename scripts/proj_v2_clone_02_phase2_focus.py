#!/usr/bin/env python3
"""Phase 2 + weekly focus Feishu writer for PROJ-V2-CLONE-02.

This script does the heavy lifting requested by the TaskSpec:
- create 5 Bitable tables with exact field types
- write the longxia bridge config with real table IDs
- upsert the phase 2 strategic task and weekly focus records
- generate the MVP coverage mapping and the weekly focus capability file
- run post-write verification hooks when apply mode is used

The dry-run path never mutates Feishu or repo files outside the run artifact
directory. The apply path only touches the five target tables and the local
bridge / dashboard artifacts called out in the spec.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
MIAODA_ROOT = Path("/Users/liming/Documents/会议纪要/【任务备份】/历史备份/miaoda-v2")
FEISHU_BRIDGE_SCRIPT = Path.home() / ".codex" / "skills" / "feishu-bitable-bridge" / "scripts" / "feishu_bitable_bridge.py"
INSTANCE_ID = "longxia"
BASE_APP_TOKEN = "PVDgbdWYFaDLBiss0hlcM5WRnQc"
BASE_LINK = f"https://h52xu4gwob.feishu.cn/base/{BASE_APP_TOKEN}"
BRIDGE_BASE_DIR = REPO_ROOT / "artifacts" / "ai-da-guan-jia" / "clones" / "instances" / INSTANCE_ID / "feishu-bridge"
TABLE_REGISTRY_PATH = BRIDGE_BASE_DIR / "table-registry.json"
SYNC_CONFIG_PATH = BRIDGE_BASE_DIR / "sync-config.json"
CLAUDE_INIT_PATH = REPO_ROOT / "yuanli-os-claude" / "CLAUDE-INIT.md"
CLAUDE_INIT_TEMPLATE_PATH = REPO_ROOT / "yuanli-os-claude" / "CLAUDE-INIT-TEMPLATE.md"
MIAODA_CAPABILITIES_DIR = MIAODA_ROOT / "server" / "capabilities"
MIAODA_TYPES_PATH = MIAODA_ROOT / "client" / "src" / "types" / "dashboard.ts"
MIAODA_HOOK_PATH = MIAODA_ROOT / "client" / "src" / "hooks" / "useDashboardData.ts"
MIAODA_PAGE_PATH = MIAODA_ROOT / "client" / "src" / "pages" / "DashboardPage" / "DashboardPage.tsx"
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "ai-da-guan-jia" / "runs"
MANIFEST_NAME = "proj-v2-clone-02-phase2-manifest.json"
CAPABILITY_NAME = "yuanlios_weekly_focus_bitable.json"

TEXT_FIELD = 1
NUMBER_FIELD = 2
SINGLE_SELECT_FIELD = 3
DATETIME_FIELD = 5


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: str
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class TableSpec:
    table_name: str
    primary_field: str
    fields: tuple[FieldSpec, ...]
    purpose: str


TABLE_SPECS: tuple[TableSpec, ...] = (
    TableSpec(
        table_name="COO_Task_Tracker",
        primary_field="task_id",
        purpose="clone task state machine",
        fields=(
            FieldSpec("task_id", "text"),
            FieldSpec("task_name", "text"),
            FieldSpec("status", "single_select", ("not_started", "in_progress", "completed", "blocked")),
            FieldSpec("priority", "single_select", ("P0", "P1", "P2")),
            FieldSpec("owner", "text"),
            FieldSpec("evidence", "text"),
            FieldSpec("start_date", "datetime"),
            FieldSpec("completion_date", "datetime"),
            FieldSpec("notes", "text"),
        ),
    ),
    TableSpec(
        table_name="COO_Evolution_Log",
        primary_field="run_id",
        purpose="post-task review",
        fields=(
            FieldSpec("run_id", "text"),
            FieldSpec("date", "datetime"),
            FieldSpec("task_ref", "text"),
            FieldSpec("input", "text"),
            FieldSpec("output", "text"),
            FieldSpec("lesson_learned", "text"),
        ),
    ),
    TableSpec(
        table_name="COO_Collab_Log",
        primary_field="log_id",
        purpose="bi-directional collab record",
        fields=(
            FieldSpec("log_id", "text"),
            FieldSpec("timestamp", "datetime"),
            FieldSpec("actor", "text"),
            FieldSpec("action_type", "single_select", ("task_spec", "execution", "review", "feedback", "approval")),
            FieldSpec("summary", "text"),
            FieldSpec("visibility", "single_select", ("hq_internal", "clone_only", "both")),
        ),
    ),
    TableSpec(
        table_name="COO_Ops_Data",
        primary_field="date",
        purpose="operational metrics",
        fields=(
            FieldSpec("date", "datetime"),
            FieldSpec("channel", "text"),
            FieldSpec("metric_name", "text"),
            FieldSpec("metric_value", "number"),
            FieldSpec("trend", "single_select", ("up", "down", "flat")),
        ),
    ),
    TableSpec(
        table_name="本周聚焦",
        primary_field="week_id",
        purpose="decision focus card",
        fields=(
            FieldSpec("week_id", "text"),
            FieldSpec("top_risk", "text"),
            FieldSpec("top_risk_action", "text"),
            FieldSpec("most_urgent_task", "text"),
            FieldSpec("most_urgent_reason", "text"),
            FieldSpec("highest_priority_next", "text"),
            FieldSpec("governance_score", "number"),
            FieldSpec("governance_trend", "single_select", ("up", "down", "flat")),
            FieldSpec("clone_health_summary", "text"),
            FieldSpec("generated_by", "single_select", ("Claude", "Human", "Codex")),
            FieldSpec("generated_at", "datetime"),
        ),
    ),
)

STRATEGIC_TASK_SPEC = TableSpec(
    table_name="战略任务追踪表",
    primary_field="task_id",
    purpose="strategic task tracker",
    fields=(
        FieldSpec("task_id", "text"),
        FieldSpec("project_id", "text"),
        FieldSpec("project_name", "text"),
        FieldSpec("project_status", "single_select", ("进行中", "已完成", "已归档")),
        FieldSpec("task_name", "text"),
        FieldSpec("task_status", "single_select", ("已完成", "进行中", "阻塞", "待启动")),
        FieldSpec("priority", "single_select", ("P0", "P1", "P2")),
        FieldSpec("owner", "single_select", ("Claude", "Codex", "人类", "妙搭")),
        FieldSpec("start_date", "datetime"),
        FieldSpec("completion_date", "datetime"),
        FieldSpec("blockers", "text"),
        FieldSpec("evidence_ref", "text"),
        FieldSpec("dependencies", "text"),
        FieldSpec("notes", "text"),
    ),
)

STRATEGIC_TASK_TABLE_ID = "tblB9JQ4cROTBUnr"

FOCUS_RECORD = {
    "week_id": "2026-W13",
    "top_risk": "PROJ-V2-CLONE Phase 2/3 执行窗口紧张，7天目标可能需要延展到10天",
    "top_risk_action": "Phase 2今天启动，确保4张表+probe在2天内完成。Phase 3紧跟。",
    "most_urgent_task": "PROJ-V2-CLONE-02",
    "most_urgent_reason": "Phase 1已完成，Phase 2是同事激活的前置依赖。每晚1天=同事晚用1天。",
    "highest_priority_next": "Phase 2建表+probe激活 → Phase 3 COLLEAGUE-INIT + dogfood",
    "governance_score": 26,
    "governance_trend": "up",
    "clone_health_summary": "longxia实例已初始化，控制面14文件就绪，probe可读取。飞书4表待建。",
    "generated_by": "Claude",
    "generated_at": 1742860800000,
}

TASK_PHASE2_RECORD = {
    "task_id": "PROJ-V2-CLONE-02",
    "project_id": "R18",
    "project_name": "R18 三向量扩展 + 驾驶舱 2.0 + 康波智库",
    "project_status": "进行中",
    "task_name": "Feishu MVP Cockpit + Health Probe 激活",
    "task_status": "已完成",
    "priority": "P0",
    "owner": "Codex",
    "start_date": "2026-03-25T00:00:00+08:00",
    "completion_date": "2026-03-25T00:00:00+08:00",
    "blockers": "",
    "evidence_ref": "artifacts/ai-da-guan-jia/runs",
    "dependencies": "PROJ-V2-CLONE-01 Gate PASSED",
    "notes": "Phase 2 MVP Cockpit 5表建表、bridge dry-run、health probe 与 weekly focus card wiring 完成。",
}

TASK_DASH_RECORD = {
    "task_id": "PROJ-DASH-P1-01",
    "project_id": "R18",
    "project_name": "R18 三向量扩展 + 驾驶舱 2.0 + 康波智库",
    "project_status": "进行中",
    "task_name": "新增\"本周聚焦\"飞书表 + 驾驶舱决策聚焦卡片",
    "task_status": "已完成",
    "priority": "P1",
    "owner": "Codex",
    "start_date": "2026-03-25T00:00:00+08:00",
    "completion_date": "2026-03-25T00:00:00+08:00",
    "blockers": "",
    "evidence_ref": "miaoda-v2/server/capabilities/yuanlios_weekly_focus_bitable.json",
    "dependencies": "",
    "notes": "本周聚焦飞书表与 Dashboard 顶部决策卡片已接入真实数据。",
}


def shanghai_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def now_stamp() -> str:
    return shanghai_now().strftime("%Y%m%d-%H%M%S")


def load_credentials() -> tuple[str, str]:
    from scripts.create_kangbo_signal_tables import load_feishu_credentials

    creds = load_feishu_credentials()
    os.environ["FEISHU_APP_ID"] = creds["app_id"]
    os.environ["FEISHU_APP_SECRET"] = creds["app_secret"]
    return creds["app_id"], creds["app_secret"]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def field_type_id(field_type: str) -> int:
    normalized = str(field_type or "").strip().lower()
    if normalized == "text":
        return TEXT_FIELD
    if normalized == "number":
        return NUMBER_FIELD
    if normalized == "single_select":
        return SINGLE_SELECT_FIELD
    if normalized == "datetime":
        return DATETIME_FIELD
    raise ValueError(f"Unsupported field type: {field_type}")


def field_payload(field: FieldSpec) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "field_name": field.name,
        "type": field_type_id(field.type),
    }
    if field.options:
        payload["property"] = {"options": [{"name": option} for option in field.options]}
    return payload


def bridge_manifest_payload() -> dict[str, Any]:
    return {
        "base_name": "PROJ-V2-CLONE-02 Phase 2 + 本周聚焦",
        "tables": [
            {
                "table_name": spec.table_name,
                "primary_field": spec.primary_field,
                "fields": [field.name for field in spec.fields],
                "views": ["全部"],
            }
            for spec in TABLE_SPECS
        ],
    }


def lookup_table(api: Any, app_token: str, table_name: str) -> dict[str, Any] | None:
    for table in api.list_tables(app_token):
        if str(table.get("name") or "").strip() == table_name:
            return table
    return None


def list_fields_by_name(api: Any, app_token: str, table_id: str) -> dict[str, dict[str, Any]]:
    fields = api.list_fields(app_token, table_id)
    return {str(item.get("field_name") or item.get("name") or "").strip(): item for item in fields if str(item.get("field_name") or item.get("name") or "").strip()}


def ensure_field_options(api: Any, app_token: str, table_id: str, field: FieldSpec, current: dict[str, Any], *, apply: bool) -> list[str]:
    if field.type != "single_select":
        return []
    current_options = [str(option.get("name") or "").strip() for option in ((current.get("property") or {}).get("options") or [])]
    missing = [option for option in field.options if option not in current_options]
    if not missing or not apply:
        return missing
    merged = [{"name": option} for option in current_options if option]
    merged.extend({"name": option} for option in missing)
    api._request(
        f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{current['field_id']}",
        method="PUT",
        payload={"field_name": field.name, "type": field_type_id(field.type), "property": {"options": merged}},
    )
    return missing


def ensure_table(api: Any, app_token: str, spec: TableSpec, *, apply: bool) -> dict[str, Any]:
    existing = lookup_table(api, app_token, spec.table_name)
    created = False
    if existing is None and apply:
        created = True
        created_payload = api.create_table(app_token, spec.table_name, [field_payload(field) for field in spec.fields])
        table_id = str(created_payload.get("table_id") or "")
    else:
        table_id = str((existing or {}).get("table_id") or "")

    if not table_id:
        return {
            "table_name": spec.table_name,
            "table_id": "",
            "status": "planned_create" if existing is None else "missing_table_id",
            "created": False,
            "expected_fields": len(spec.fields),
            "field_ids": {},
            "field_types": {},
            "option_updates": {},
            "primary_field": spec.primary_field,
            "purpose": spec.purpose,
        }

    if created:
        # Feishu may need a beat to expose the freshly created fields.
        subprocess.run(["sleep", "1"], check=False)

    current_fields = list_fields_by_name(api, app_token, table_id)
    created_fields: list[str] = []
    option_updates: dict[str, list[str]] = {}
    field_ids: dict[str, str] = {}
    field_types: dict[str, int] = {}
    for field in spec.fields:
        current = current_fields.get(field.name)
        if current is None:
            created_fields.append(field.name)
            if apply and not created:
                api._request(
                    f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
                    method="POST",
                    payload=field_payload(field),
                )
            continue
        actual_type = int(current.get("type") or 0)
        expected_type = field_type_id(field.type)
        if actual_type != expected_type:
            raise RuntimeError(
                f"Field type mismatch for {spec.table_name}.{field.name}: expected {expected_type}, got {actual_type}"
            )
        field_ids[field.name] = str(current.get("field_id") or "")
        field_types[field.name] = actual_type
        missing = ensure_field_options(api, app_token, table_id, field, current, apply=apply)
        if missing:
            option_updates[field.name] = missing

    refreshed_fields = list_fields_by_name(api, app_token, table_id)
    for field_name, field in refreshed_fields.items():
        field_ids.setdefault(field_name, str(field.get("field_id") or ""))
        field_types.setdefault(field_name, int(field.get("type") or 0))

    return {
        "table_name": spec.table_name,
        "table_id": table_id,
        "status": "created" if created else ("existing" if existing else "created"),
        "created": created,
        "expected_fields": len(spec.fields),
        "created_fields": created_fields,
        "field_ids": field_ids,
        "field_types": field_types,
        "option_updates": option_updates,
        "primary_field": spec.primary_field,
        "purpose": spec.purpose,
    }


def normalize_fields(schema_fields: tuple[FieldSpec, ...], row: dict[str, Any]) -> dict[str, Any]:
    from dashboard.feishu_deploy import normalize_record

    schema = {
        "fields": [
            {"name": field.name, "type": field.type, "options": list(field.options)}
            for field in schema_fields
        ]
    }
    return normalize_record(schema, row)


def index_by_primary(records: list[dict[str, Any]], primary_field: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        fields = record.get("fields") or {}
        value = fields.get(primary_field)
        if value in {None, ""}:
            continue
        indexed[str(value)] = record
    return indexed


def upsert_row(
    api: Any,
    app_token: str,
    spec: TableSpec,
    row: dict[str, Any],
    *,
    apply: bool,
    table_id_override: str | None = None,
) -> dict[str, Any]:
    if table_id_override:
        table_id = table_id_override
    else:
        table = lookup_table(api, app_token, spec.table_name)
        if table is None:
            raise RuntimeError(f"table missing: {spec.table_name}")
        table_id = str(table.get("table_id") or "")
    normalized = normalize_fields(spec.fields, row)
    primary_value = str(normalized.get(spec.primary_field) or "").strip()
    if not primary_value:
        raise RuntimeError(f"missing primary value for {spec.table_name}: {spec.primary_field}")

    existing_records = api.list_records(app_token, table_id)
    existing_index = index_by_primary(existing_records, spec.primary_field)
    existing = existing_index.get(primary_value)
    action = "planned_create"
    record_id = ""
    if existing:
        action = "planned_update"
        record_id = str(existing.get("record_id") or existing.get("id") or "")

    if apply:
        if existing:
            api.batch_update_records(app_token, table_id, [{"record_id": record_id, "fields": normalized}])
            action = "updated"
        else:
            api.batch_create_records(app_token, table_id, [normalized])
            action = "created"

    refreshed = api.list_records(app_token, table_id)
    return {
        "table_name": spec.table_name,
        "table_id": table_id,
        "primary_field": spec.primary_field,
        "primary_value": primary_value,
        "action": action,
        "created_count": 1 if action == "created" else 0,
        "updated_count": 1 if action == "updated" else 0,
        "record_count": len(refreshed),
        "record_id": record_id,
        "fields": normalized,
    }


def run_json_command(command: list[str], *, env: dict[str, str] | None = None) -> dict[str, Any]:
    completed = subprocess.run(command, capture_output=True, text=True, check=False, env=env)
    payload: dict[str, Any] = {}
    text = (completed.stdout or completed.stderr or "").strip()
    if text:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {"raw_output": text}
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "parsed": payload,
    }


def patch_markdown_section(path: Path, *, anchor: str, insert_before: str, additions: list[str]) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    if all(addition in text for addition in additions):
        return False
    if anchor not in text:
        return False
    block = "\n".join(additions) + "\n\n"
    new_text = text.replace(insert_before, block + insert_before, 1)
    if new_text == text:
        return False
    path.write_text(new_text, encoding="utf-8")
    return True


def update_claude_init(paths: tuple[Path, ...], table_results: list[dict[str, Any]]) -> list[str]:
    additions = [
        *[
            f"- Phase 2 MVP Cockpit 表：`{result['table_name']} / {result['table_id']}`"
            for result in table_results
        if result["table_name"] != "本周聚焦"
        ],
        next(
            f"- 本周聚焦：`本周聚焦 / {result['table_id']}`"
            for result in table_results
            if result["table_name"] == "本周聚焦"
        ),
    ]
    updated: list[str] = []
    for path in paths:
        if patch_markdown_section(path, anchor="## 前台摘要", insert_before="## 前台摘要", additions=additions):
            updated.append(str(path))
    return updated


def write_instance_configs(table_results: list[dict[str, Any]], manifest_path: Path) -> dict[str, Any]:
    table_registry = {
        "instance_id": INSTANCE_ID,
        "clone_id": INSTANCE_ID,
        "feishu_link": BASE_LINK,
        "base_app_token": BASE_APP_TOKEN,
        "main_table_id": "pending",
        "task_table_id": "pending",
        "evolution_table_id": "pending",
        "scorecard_table_id": "pending",
        "primary_field": "",
        "tables": {
            result["table_name"]: {
                "table_id": result["table_id"],
                "primary_field": result["primary_field"],
                "purpose": result["purpose"],
                "field_ids": result["field_ids"],
            }
            for result in table_results
        },
        "updated_at": shanghai_now().isoformat(timespec="seconds"),
    }
    sync_config = {
        "instance_id": INSTANCE_ID,
        "surface": "clone_governance",
        "portfolio": "internal",
        "report_date": shanghai_now().date().isoformat(),
        "cron": "0 9 * * *",
        "mode": "cron-first",
        "link": BASE_LINK,
        "feishu_link": BASE_LINK,
        "bridge_script": str(FEISHU_BRIDGE_SCRIPT),
        "manifest": str(manifest_path),
        "updated_at": shanghai_now().isoformat(timespec="seconds"),
    }
    write_json(TABLE_REGISTRY_PATH, table_registry)
    write_json(SYNC_CONFIG_PATH, sync_config)
    return {"table_registry": table_registry, "sync_config": sync_config}


def build_instance_configs_payload(table_results: list[dict[str, Any]], manifest_path: Path) -> dict[str, Any]:
    return {
        "table_registry": {
            "instance_id": INSTANCE_ID,
            "clone_id": INSTANCE_ID,
            "feishu_link": BASE_LINK,
            "base_app_token": BASE_APP_TOKEN,
            "main_table_id": "pending",
            "task_table_id": "pending",
            "evolution_table_id": "pending",
            "scorecard_table_id": "pending",
            "primary_field": "",
            "tables": {
                result["table_name"]: {
                    "table_id": result["table_id"],
                    "primary_field": result["primary_field"],
                    "purpose": result["purpose"],
                    "field_ids": result["field_ids"],
                }
                for result in table_results
            },
            "updated_at": shanghai_now().isoformat(timespec="seconds"),
        },
        "sync_config": {
            "instance_id": INSTANCE_ID,
            "surface": "clone_governance",
            "portfolio": "internal",
            "report_date": shanghai_now().date().isoformat(),
            "cron": "0 9 * * *",
            "mode": "cron-first",
            "link": BASE_LINK,
            "feishu_link": BASE_LINK,
            "bridge_script": str(FEISHU_BRIDGE_SCRIPT),
            "manifest": str(manifest_path),
            "updated_at": shanghai_now().isoformat(timespec="seconds"),
        },
    }


def write_weekly_focus_capability(table_result: dict[str, Any]) -> Path:
    capability = build_weekly_focus_capability_payload(table_result)
    capability_path = MIAODA_CAPABILITIES_DIR / CAPABILITY_NAME
    write_json(capability_path, capability)
    return capability_path


def build_weekly_focus_capability_payload(table_result: dict[str, Any]) -> dict[str, Any]:
    field_ids = table_result["field_ids"]
    def fid(name: str) -> str:
        return str(field_ids.get(name) or "")

    return {
        "id": "yuanlios_weekly_focus_bitable",
        "pluginKey": "@official-plugins/feishu-bitable",
        "pluginVersion": "1.0.7",
        "name": "原力OS仪表盘 - 本周聚焦",
        "description": "基于飞书多维表格查询本周聚焦表数据，支持searchRecords查询操作",
        "icon": "",
        "paramsSchema": {},
        "formValue": {
            "tableID": table_result["table_id"],
            "fields": [
                {"id": fid("week_id"), "name": "week_id", "type": TEXT_FIELD, "bizType": "Text", "readable": True, "writeable": False},
                {"id": fid("top_risk"), "name": "top_risk", "type": TEXT_FIELD, "bizType": "Text", "readable": True, "writeable": False},
                {"id": fid("top_risk_action"), "name": "top_risk_action", "type": TEXT_FIELD, "bizType": "Text", "readable": True, "writeable": False},
                {"id": fid("most_urgent_task"), "name": "most_urgent_task", "type": TEXT_FIELD, "bizType": "Text", "readable": True, "writeable": False},
                {"id": fid("most_urgent_reason"), "name": "most_urgent_reason", "type": TEXT_FIELD, "bizType": "Text", "readable": True, "writeable": False},
                {"id": fid("highest_priority_next"), "name": "highest_priority_next", "type": TEXT_FIELD, "bizType": "Text", "readable": True, "writeable": False},
                {"id": fid("governance_score"), "name": "governance_score", "type": NUMBER_FIELD, "bizType": "Number", "readable": True, "writeable": False},
                {
                    "id": fid("governance_trend"),
                    "name": "governance_trend",
                    "type": SINGLE_SELECT_FIELD,
                    "bizType": "SingleSelect",
                    "readable": True,
                    "writeable": False,
                    "enumValues": ["up", "down", "flat"],
                },
                {"id": fid("clone_health_summary"), "name": "clone_health_summary", "type": TEXT_FIELD, "bizType": "Text", "readable": True, "writeable": False},
                {
                    "id": fid("generated_by"),
                    "name": "generated_by",
                    "type": SINGLE_SELECT_FIELD,
                    "bizType": "SingleSelect",
                    "readable": True,
                    "writeable": False,
                    "enumValues": ["Claude", "Human", "Codex"],
                },
                {"id": fid("generated_at"), "name": "generated_at", "type": DATETIME_FIELD, "bizType": "DateTime", "readable": True, "writeable": False},
            ],
        },
        "actions": [
            {
                "key": "searchRecords",
                "name": "搜索记录",
                "description": "搜索本周聚焦表记录",
                "outputMode": "unary",
            }
        ],
    }


def write_coverage_mapping(table_results: list[dict[str, Any]], run_dir: Path) -> Path:
    mapping = [
        ("任务状态追踪", "MVP覆盖", "COO_Task_Tracker"),
        ("执行后复盘", "MVP覆盖", "COO_Evolution_Log"),
        ("协同记录", "MVP覆盖", "COO_Collab_Log"),
        ("运营指标", "MVP覆盖", "COO_Ops_Data"),
        ("本周聚焦", "MVP覆盖", "本周聚焦"),
        ("clone注册", "已有", "AI实例注册表"),
        ("训练轮次", "已有", "训练轮次表"),
        ("能力提案", "已有", "能力提案表"),
        ("实例评分", "已有", "实例评分表"),
        ("告警/每日报告", "deferred", "Phase 3 或后续"),
    ]
    lines = [
        "# PROJ-V2-CLONE-02 / PROJ-DASH-P1-01 Coverage Mapping",
        "",
        "| 契约要求 | 覆盖状态 | 覆盖表 / 去向 |",
        "|---|---|---|",
    ]
    for requirement, status, surface in mapping:
        lines.append(f"| {requirement} | {status} | {surface} |")
    lines.extend(
        [
            "",
            "## Real Tables",
            "",
        ]
    )
    for result in table_results:
        lines.append(f"- `{result['table_name']}` -> `{result['table_id']}`")
    path = run_dir / "coverage-mapping.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def build_run_dir(run_id: str) -> Path:
    run_dir = ARTIFACT_ROOT / shanghai_now().strftime("%Y-%m-%d") / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def run_health_probe() -> dict[str, Any]:
    command = ["python3", str(REPO_ROOT / "work" / "ai-da-guan-jia" / "tools" / "health_probe.py"), "--instance", INSTANCE_ID]
    return run_json_command(command)


def run_bridge_dry_run(manifest_path: Path) -> dict[str, Any]:
    env = dict(os.environ)
    env["AI_DA_GUAN_JIA_FEISHU_BASE_TOKEN"] = BASE_APP_TOKEN
    command = [
        "python3",
        str(FEISHU_BRIDGE_SCRIPT),
        "sync-base-schema",
        "--link",
        BASE_LINK,
        "--manifest",
        str(manifest_path),
        "--dry-run",
    ]
    return run_json_command(command, env=env)


def run_sync_feishu_dry_run() -> dict[str, Any]:
    command = [
        "python3",
        str(REPO_ROOT / "scripts" / "ai_da_guan_jia.py"),
        "sync-feishu",
        "--surface",
        "clone_governance",
        "--instance",
        INSTANCE_ID,
        "--dry-run",
    ]
    return run_json_command(command)


def summarize_plan(table_results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "base_app_token": BASE_APP_TOKEN,
        "base_link": BASE_LINK,
        "tables": [
            {
                "table_name": spec.table_name,
                "primary_field": spec.primary_field,
                "fields": [field.name for field in spec.fields],
            }
            for spec in TABLE_SPECS
        ],
        "existing_tables": [
            {
                "table_name": result["table_name"],
                "table_id": result["table_id"],
                "status": result["status"],
                "created": result["created"],
                "created_fields": result.get("created_fields", []),
                "option_updates": result.get("option_updates", {}),
            }
            for result in table_results
        ],
        "focus_record": FOCUS_RECORD,
        "task_records": [TASK_PHASE2_RECORD, TASK_DASH_RECORD],
    }


def run(*, apply: bool, run_id: str) -> dict[str, Any]:
    from dashboard.feishu_deploy import FeishuBitableAPI

    app_id, app_secret = load_credentials()
    api = FeishuBitableAPI(app_id, app_secret)
    app_token = BASE_APP_TOKEN
    run_dir = build_run_dir(run_id)
    manifest_path = run_dir / MANIFEST_NAME
    write_json(manifest_path, bridge_manifest_payload())

    table_results: list[dict[str, Any]] = []
    for spec in TABLE_SPECS:
        table_results.append(ensure_table(api, app_token, spec, apply=apply))

    strategic_record_results: list[dict[str, Any]] = []
    focus_record_results: list[dict[str, Any]] = []
    if apply:
        strategic_record_results.append(
            upsert_row(
                api,
                app_token,
                STRATEGIC_TASK_SPEC,
                TASK_PHASE2_RECORD,
                apply=True,
                table_id_override=STRATEGIC_TASK_TABLE_ID,
            )
        )
        strategic_record_results.append(
            upsert_row(
                api,
                app_token,
                STRATEGIC_TASK_SPEC,
                TASK_DASH_RECORD,
                apply=True,
                table_id_override=STRATEGIC_TASK_TABLE_ID,
            )
        )
        focus_spec = next(spec for spec in TABLE_SPECS if spec.table_name == "本周聚焦")
        focus_record_results.append(upsert_row(api, app_token, focus_spec, FOCUS_RECORD, apply=True))
    else:
        strategic_record_results.append(
            upsert_row(
                api,
                app_token,
                STRATEGIC_TASK_SPEC,
                TASK_PHASE2_RECORD,
                apply=False,
                table_id_override=STRATEGIC_TASK_TABLE_ID,
            )
        )
        strategic_record_results.append(
            upsert_row(
                api,
                app_token,
                STRATEGIC_TASK_SPEC,
                TASK_DASH_RECORD,
                apply=False,
                table_id_override=STRATEGIC_TASK_TABLE_ID,
            )
        )
        focus_record_results.append(
            {
                "table_name": "本周聚焦",
                "table_id": "",
                "primary_field": "week_id",
                "primary_value": FOCUS_RECORD["week_id"],
                "action": "planned_create",
                "created_count": 0,
                "updated_count": 0,
                "record_count": 0,
                "record_id": "",
                "fields": normalize_fields(next(spec.fields for spec in TABLE_SPECS if spec.table_name == "本周聚焦"), FOCUS_RECORD),
            }
        )

    config_payload = build_instance_configs_payload(table_results, manifest_path)
    capability_preview = build_weekly_focus_capability_payload(next(result for result in table_results if result["table_name"] == "本周聚焦"))
    coverage_path = write_coverage_mapping(table_results, run_dir)
    capability_path = ""
    claude_init_updates: list[str] = []
    if apply:
        table_registry = write_instance_configs(table_results, manifest_path)
        capability_path = str(write_weekly_focus_capability(next(result for result in table_results if result["table_name"] == "本周聚焦")))
        claude_init_updates = update_claude_init((CLAUDE_INIT_PATH, CLAUDE_INIT_TEMPLATE_PATH), table_results)
    else:
        table_registry = config_payload

    bridge_dry_run = run_bridge_dry_run(manifest_path)
    health_probe = run_health_probe() if apply else {}
    sync_feishu_dry_run = run_sync_feishu_dry_run() if apply else {}

    result = {
        "status": "applied" if apply else "dry-run",
        "run_id": run_id,
        "run_dir": str(run_dir),
        "base_app_token": BASE_APP_TOKEN,
        "base_link": BASE_LINK,
        "tables": table_results,
        "strategic_task_records": strategic_record_results,
        "focus_records": focus_record_results,
        "table_registry_path": str(TABLE_REGISTRY_PATH),
        "sync_config_path": str(SYNC_CONFIG_PATH),
        "table_registry": table_registry["table_registry"],
        "sync_config": table_registry["sync_config"],
        "capability_path": capability_path,
        "capability_preview": capability_preview,
        "coverage_path": str(coverage_path),
        "claude_init_updates": claude_init_updates,
        "bridge_manifest_path": str(manifest_path),
        "bridge_dry_run": bridge_dry_run,
        "health_probe": health_probe,
        "sync_feishu_dry_run": sync_feishu_dry_run,
        "plan": summarize_plan(table_results),
    }
    artifact_path = run_dir / ("apply.json" if apply else "dry-run.json")
    write_json(artifact_path, result)
    result["artifact_path"] = str(artifact_path)
    verification_path = run_dir / "verification_result.json"
    write_json(verification_path, result)
    result["verification_path"] = str(verification_path)
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create PROJ-V2-CLONE-02 phase 2 cockpit tables and the weekly focus table.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--run-id", default=f"adagj-proj-v2-clone-02-phase2-focus-{now_stamp()}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run(apply=bool(args.apply), run_id=str(args.run_id))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
