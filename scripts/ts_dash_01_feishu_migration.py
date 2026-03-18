from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcp_server_feishu.feishu_client import FeishuClient
from scripts.sync_governance_dashboard_base import api, list_fields, list_records, list_tables


TEXT_FIELD = 1
NUMBER_FIELD = 2
SINGLE_SELECT_FIELD = 3
DATE_FIELD = 5
CHECKBOX_FIELD = 7

PH2_BASE = "PHp2wURl2i6SyBkDtmGcuaEenag"
PVDG_BASE = "PVDgbdWYFaDLBiss0hlcM5WRnQc"

RUNTIME_TABLE_ID = "tblnRCmMS7QBMtHI"
AUDIT_TABLE_ID = "tblYnhPN5JyMNwrU"
RESPONSIBILITY_TABLE_ID = "tblQr3eRlg34c7zB"
HEATMAP_TABLE_ID = "tblPGUAH2hcMqWMz"

DEFAULT_RUN_DIR = (
    REPO_ROOT
    / "work/ai-da-guan-jia/artifacts/ai-da-guan-jia/runs/2026-03-17/adagj-20260317-195016-000000"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the TS-DASH-01 Feishu migration.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--run-dir", default=str(DEFAULT_RUN_DIR))
    return parser.parse_args(argv)


def field_name(field: dict[str, Any]) -> str:
    return str(field.get("field_name") or field.get("name") or "").strip()


def field_lookup(fields: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for field in fields:
        name = field_name(field)
        if name:
            result[name] = field
    return result


def table_id_by_name(client: FeishuClient, app_token: str, table_name: str) -> str:
    for table in list_tables(client, app_token):
        if str(table.get("name") or "").strip() == table_name:
            return str(table.get("table_id") or "").strip()
    return ""


def sanitize_property(field_type: int, property_value: Any) -> dict[str, Any] | None:
    if not isinstance(property_value, dict) or not property_value:
        return None
    if field_type == SINGLE_SELECT_FIELD:
        options = []
        for option in property_value.get("options", []) or []:
            if not isinstance(option, dict):
                continue
            name = str(option.get("name") or "").strip()
            if not name:
                continue
            cleaned = {"name": name}
            if option.get("color") is not None:
                cleaned["color"] = option["color"]
            if option.get("id"):
                cleaned["id"] = option["id"]
            options.append(cleaned)
        return {"options": options} if options else None
    return dict(property_value)


def compare_key(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str("" if value is None else value).strip()


def primary_field_name(fields: list[dict[str, Any]]) -> str:
    primary = next((field for field in fields if field.get("is_primary")), fields[0] if fields else None)
    if primary is None:
        raise RuntimeError("table has no fields")
    return field_name(primary)


def normalize_record_fields(values: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for key, value in values.items():
        if value is None:
            continue
        if value == "":
            continue
        fields[key] = value
    return fields


def ensure_single_select_options(
    client: FeishuClient,
    app_token: str,
    table_id: str,
    field: dict[str, Any],
    *,
    dry_run: bool,
) -> list[str]:
    if int(field["type"]) != SINGLE_SELECT_FIELD:
        return []
    current_fields = field_lookup(list_fields(client, app_token, table_id))
    current = current_fields.get(field["field_name"])
    if current is None:
        return []
    property_payload = dict(current.get("property") or {})
    existing_options = list(property_payload.get("options") or [])
    existing_names = {str(option.get("name") or "").strip() for option in existing_options}
    wanted = [
        str(option.get("name") or "").strip()
        for option in (field.get("property", {}) or {}).get("options", []) or []
        if str(option.get("name") or "").strip()
    ]
    missing = [name for name in wanted if name not in existing_names]
    if not missing:
        return []
    if dry_run:
        return missing

    merged_options = []
    for option in existing_options:
        name = str(option.get("name") or "").strip()
        if not name:
            continue
        cleaned = {"name": name}
        if option.get("id"):
            cleaned["id"] = option["id"]
        if option.get("color") is not None:
            cleaned["color"] = option["color"]
        merged_options.append(cleaned)
    for name in missing:
        merged_options.append({"name": name})
    api(
        client,
        "PUT",
        f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{current['field_id']}",
        {
            "field_name": field["field_name"],
            "type": SINGLE_SELECT_FIELD,
            "property": {"options": merged_options},
        },
    )
    return missing


def ensure_fields_for_table(
    client: FeishuClient,
    app_token: str,
    table_id: str,
    field_specs: list[dict[str, Any]],
    *,
    dry_run: bool,
) -> dict[str, Any]:
    current_fields = {}
    if not (dry_run and table_id.startswith("dryrun::")):
        current_fields = field_lookup(list_fields(client, app_token, table_id))
    created_fields: list[str] = []
    option_updates: dict[str, list[str]] = {}
    for spec in field_specs:
        name = spec["field_name"]
        current = current_fields.get(name)
        if current is None:
            created_fields.append(name)
            if not dry_run:
                body: dict[str, Any] = {"field_name": name, "type": spec["type"]}
                prop = sanitize_property(spec["type"], spec.get("property"))
                if prop:
                    body["property"] = prop
                api(client, "POST", f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields", body)
            continue
        if int(spec["type"]) == SINGLE_SELECT_FIELD:
            missing = ensure_single_select_options(client, app_token, table_id, spec, dry_run=dry_run)
            if missing:
                option_updates[name] = missing
    return {"created_fields": created_fields, "option_updates": option_updates}


def ensure_table(
    client: FeishuClient,
    app_token: str,
    table_spec: dict[str, Any],
    *,
    dry_run: bool,
) -> dict[str, Any]:
    table_name = table_spec["table_name"]
    existing_id = table_id_by_name(client, app_token, table_name)
    table_created = False
    table_id = existing_id
    if not table_id:
        table_created = True
        if not dry_run:
            created = api(client, "POST", f"/bitable/v1/apps/{app_token}/tables", {"table": {"name": table_name}})
            table = (created.get("data", {}) or {}).get("table", {}) or {}
            table_id = str(table.get("table_id") or "").strip() or table_id_by_name(client, app_token, table_name)
        else:
            table_id = f"dryrun::{table_name}"
    if not table_id:
        raise RuntimeError(f"failed to resolve table id for {table_name}")

    created_fields: list[str] = []
    option_updates: dict[str, list[str]] = {}
    if not dry_run:
        current_fields = list_fields(client, app_token, table_id)
        primary = next((field for field in current_fields if field.get("is_primary")), current_fields[0] if current_fields else None)
        if primary is None:
            raise RuntimeError(f"table {table_name} has no primary field")
        primary_name = field_name(primary)
        desired_primary = table_spec["primary_field"]
        if primary_name != desired_primary["field_name"] or int(primary.get("type") or TEXT_FIELD) != int(desired_primary["type"]):
            body: dict[str, Any] = {
                "field_name": desired_primary["field_name"],
                "type": desired_primary["type"],
            }
            prop = sanitize_property(desired_primary["type"], desired_primary.get("property"))
            if prop:
                body["property"] = prop
            api(client, "PUT", f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{primary['field_id']}", body)
    created = ensure_fields_for_table(client, app_token, table_id, table_spec["fields"], dry_run=dry_run)
    created_fields.extend(created["created_fields"])
    option_updates.update(created["option_updates"])
    return {
        "table_id": table_id,
        "table_created": table_created,
        "created_fields": created_fields,
        "option_updates": option_updates,
    }


def upsert_rows(
    client: FeishuClient,
    app_token: str,
    table_id: str,
    primary_field: str,
    rows: list[dict[str, Any]],
    *,
    dry_run: bool,
) -> list[dict[str, Any]]:
    existing = {}
    if not (dry_run and table_id.startswith("dryrun::")):
        existing = {compare_key((row.get("fields") or {}).get(primary_field)): row for row in list_records(client, app_token, table_id)}
    results: list[dict[str, Any]] = []
    for row in rows:
        fields = normalize_record_fields(deepcopy(row))
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


def now_epoch_ms() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp() * 1000)


def ts_dash_01_spec() -> dict[str, Any]:
    single = lambda options: {"options": [{"name": name} for name in options]}
    datetime_property = {"date_formatter": "yyyy-MM-dd HH:mm", "auto_fill": False}

    existing_tables = [
        {
            "label": "L0_运行态总控",
            "app_token": PH2_BASE,
            "table_id": RUNTIME_TABLE_ID,
            "field_specs": [
                {"field_name": "agent_generation", "type": TEXT_FIELD},
                {"field_name": "v1_status", "type": SINGLE_SELECT_FIELD, "property": single(["规划中", "进行中", "已完成"])},
                {"field_name": "v2_status", "type": SINGLE_SELECT_FIELD, "property": single(["规划中", "进行中", "已完成"])},
                {"field_name": "v3_status", "type": SINGLE_SELECT_FIELD, "property": single(["未启动", "规划中", "进行中", "已完成"])},
                {"field_name": "d8_score", "type": NUMBER_FIELD, "property": {"formatter": "0.0"}},
                {"field_name": "d9_score", "type": NUMBER_FIELD, "property": {"formatter": "0.0"}},
                {"field_name": "d10_score", "type": NUMBER_FIELD, "property": {"formatter": "0.0"}},
                {"field_name": "total_score_40", "type": NUMBER_FIELD, "property": {"formatter": "0.0"}},
            ],
            "primary_field": "active_round",
            "rows": [
                {
                    "active_round": "R17",
                    "agent_generation": "第二代末期→第三代入口",
                    "v1_status": "规划中",
                    "v2_status": "规划中",
                    "v3_status": "未启动",
                    "d8_score": 0,
                    "d9_score": 0,
                    "d10_score": 0,
                    "total_score_40": 17,
                }
            ],
        },
        {
            "label": "治理成熟度评估",
            "app_token": PVDG_BASE,
            "table_id": AUDIT_TABLE_ID,
            "field_specs": [
                {"field_name": "d8_score", "type": NUMBER_FIELD, "property": {"formatter": "0.0"}},
                {"field_name": "d9_score", "type": NUMBER_FIELD, "property": {"formatter": "0.0"}},
                {"field_name": "d10_score", "type": NUMBER_FIELD, "property": {"formatter": "0.0"}},
                {"field_name": "total_score_40", "type": NUMBER_FIELD, "property": {"formatter": "0.0"}},
                {"field_name": "dimension_group", "type": TEXT_FIELD},
            ],
            "primary_field": "audit_id",
            "rows": [
                {
                    "audit_id": "GOV-AUDIT-20260317",
                    "d8_score": 0,
                    "d9_score": 0,
                    "d10_score": 0,
                    "total_score_40": 17,
                    "dimension_group": "系统基础/治理结构/扩展就绪/三方协同",
                }
            ],
        },
        {
            "label": "组件责任",
            "app_token": PVDG_BASE,
            "table_id": RESPONSIBILITY_TABLE_ID,
            "field_specs": [
                {"field_name": "collaboration_mode", "type": SINGLE_SELECT_FIELD, "property": single(["独立", "协作", "待认领"])},
                {"field_name": "v2_assignable", "type": CHECKBOX_FIELD},
            ],
            "primary_field": "sync_primary_key",
            "rows": [
                {"sync_primary_key": "公域获客", "collaboration_mode": "独立", "v2_assignable": False},
                {"sync_primary_key": "私域转化", "collaboration_mode": "独立", "v2_assignable": False},
                {"sync_primary_key": "销售成交", "collaboration_mode": "独立", "v2_assignable": False},
                {"sync_primary_key": "产品交付", "collaboration_mode": "独立", "v2_assignable": False},
                {"sync_primary_key": "财务经营", "collaboration_mode": "独立", "v2_assignable": False},
                {"sync_primary_key": "治理控制", "collaboration_mode": "独立", "v2_assignable": False},
            ],
        },
        {
            "label": "组件热图",
            "app_token": PVDG_BASE,
            "table_id": HEATMAP_TABLE_ID,
            "field_specs": [
                {"field_name": "vector_tag", "type": SINGLE_SELECT_FIELD, "property": single(["V1", "V2", "V3", "核心", "无"])},
            ],
            "primary_field": "sync_primary_key",
            "rows": [],
        },
    ]

    new_tables = [
        {
            "table_name": "三向量进度",
            "app_token": PVDG_BASE,
            "primary_field": {"field_name": "task_id", "type": TEXT_FIELD},
            "fields": [
                {"field_name": "task_name", "type": TEXT_FIELD},
                {"field_name": "vector", "type": SINGLE_SELECT_FIELD, "property": single(["V1", "V2", "V3", "GH"])},
                {"field_name": "phase", "type": SINGLE_SELECT_FIELD, "property": single(["P0", "P1", "P2", "P3"])},
                {"field_name": "week", "type": NUMBER_FIELD, "property": {"formatter": "0.0"}},
                {"field_name": "executor", "type": SINGLE_SELECT_FIELD, "property": single(["Claude", "大管家", "人类", "妙搭"])},
                {"field_name": "status", "type": SINGLE_SELECT_FIELD, "property": single(["待启动", "进行中", "已完成", "阻塞"])},
                {"field_name": "dependencies", "type": TEXT_FIELD},
                {"field_name": "start_date", "type": DATE_FIELD, "property": datetime_property},
                {"field_name": "completion_date", "type": DATE_FIELD, "property": datetime_property},
                {"field_name": "handoff_summary", "type": TEXT_FIELD},
                {"field_name": "blockers", "type": TEXT_FIELD},
            ],
            "rows": [
                {"task_id": "TS-GH-01", "task_name": "GitHub治理盘点", "vector": "GH", "phase": "P0", "week": 1, "executor": "大管家", "status": "进行中"},
                {"task_id": "TS-V1-01", "task_name": "卫星机治理对齐", "vector": "V1", "phase": "P0", "week": 1, "executor": "大管家", "status": "进行中"},
                {"task_id": "TS-V2-01", "task_name": "INIT模板化", "vector": "V2", "phase": "P0", "week": 1, "executor": "大管家", "status": "进行中"},
                {"task_id": "TS-V1-02", "task_name": "机器注册表", "vector": "V1", "phase": "P1", "week": 2, "executor": "大管家", "status": "待启动"},
                {"task_id": "TS-V2-02", "task_name": "飞书Base初始化脚本", "vector": "V2", "phase": "P1", "week": 2, "executor": "大管家", "status": "待启动"},
                {"task_id": "TS-V2-03", "task_name": "妙搭驾驶舱模板化", "vector": "V2", "phase": "P1", "week": 2, "executor": "人类", "status": "待启动"},
                {"task_id": "TS-V1-03", "task_name": "任务分发路由", "vector": "V1", "phase": "P2", "week": 3, "executor": "大管家", "status": "待启动"},
                {"task_id": "TS-V2-04", "task_name": "业务模块拆分", "vector": "V2", "phase": "P2", "week": 3, "executor": "Claude", "status": "待启动"},
                {"task_id": "TS-V3-01", "task_name": "行业模板设计", "vector": "V3", "phase": "P2", "week": 3, "executor": "Claude", "status": "待启动"},
                {"task_id": "TS-V1-04", "task_name": "虚机部署脚本", "vector": "V1", "phase": "P3", "week": 4, "executor": "大管家", "status": "待启动"},
                {"task_id": "TS-V2-05", "task_name": "同事onboarding SOP", "vector": "V2", "phase": "P3", "week": 4, "executor": "Claude", "status": "待启动"},
                {"task_id": "TS-V3-02", "task_name": "客户初始化工具", "vector": "V3", "phase": "P3", "week": 4, "executor": "大管家", "status": "待启动"},
                {"task_id": "TS-V3-03", "task_name": "客户驾驶舱产品化", "vector": "V3", "phase": "P3", "week": 4, "executor": "人类", "status": "待启动"},
                {"task_id": "TS-V3-04", "task_name": "定价与交付SOP", "vector": "V3", "phase": "P3", "week": 4, "executor": "Claude", "status": "待启动"},
            ],
        },
        {
            "table_name": "三方协同日志",
            "app_token": PVDG_BASE,
            "primary_field": {"field_name": "interaction_id", "type": TEXT_FIELD},
            "fields": [
                {"field_name": "timestamp", "type": DATE_FIELD, "property": datetime_property},
                {"field_name": "from_role", "type": SINGLE_SELECT_FIELD, "property": single(["Claude", "大管家", "人类"])},
                {"field_name": "to_role", "type": SINGLE_SELECT_FIELD, "property": single(["Claude", "大管家", "人类"])},
                {"field_name": "interaction_type", "type": SINGLE_SELECT_FIELD, "property": single(["task_spec", "handoff", "approval", "feedback", "escalation"])},
                {"field_name": "summary", "type": TEXT_FIELD},
                {"field_name": "quality_score", "type": NUMBER_FIELD, "property": {"formatter": "0.0"}},
                {"field_name": "artifact_ref", "type": TEXT_FIELD},
                {"field_name": "round_ref", "type": TEXT_FIELD},
            ],
            "rows": [],
        },
        {
            "table_name": "记忆层健康度",
            "app_token": PVDG_BASE,
            "primary_field": {"field_name": "layer_id", "type": NUMBER_FIELD, "property": {"formatter": "0.0"}},
            "fields": [
                {"field_name": "layer_name", "type": TEXT_FIELD},
                {"field_name": "health_status", "type": SINGLE_SELECT_FIELD, "property": single(["健康", "有漂移", "异常", "不适用"])},
                {"field_name": "last_sync_time", "type": DATE_FIELD, "property": datetime_property},
                {"field_name": "drift_detected", "type": CHECKBOX_FIELD},
                {"field_name": "drift_detail", "type": TEXT_FIELD},
                {"field_name": "health_score", "type": NUMBER_FIELD, "property": {"formatter": "0.0"}},
                {"field_name": "notes", "type": TEXT_FIELD},
            ],
            "rows": [
                {"layer_id": 1, "layer_name": "本地 Canonical", "health_status": "健康", "drift_detected": False, "health_score": 5, "notes": "artifacts 体系完整运行"},
                {"layer_id": 2, "layer_name": "MD 制度记忆", "health_status": "健康", "drift_detected": False, "health_score": 5, "notes": "三份合同 + memory.md 已补齐"},
                {"layer_id": 3, "layer_name": "GitHub 分发", "health_status": "有漂移", "drift_detected": True, "drift_detail": "1482未提交文件待处理，盘点进行中", "health_score": 3, "notes": "1482未提交文件待处理，盘点进行中"},
                {"layer_id": 4, "layer_name": "飞书前台", "health_status": "健康", "drift_detected": False, "health_score": 4, "notes": "驾驶舱在线，部分指标卡待重绑"},
                {"layer_id": 5, "layer_name": "对话临时", "health_status": "不适用", "drift_detected": False, "health_score": 0, "notes": "对话层天然临时，不评分"},
            ],
        },
    ]
    return {"existing_tables": existing_tables, "new_tables": new_tables}


def verify_existing_field_names(client: FeishuClient, app_token: str, table_id: str, field_specs: list[dict[str, Any]]) -> list[str]:
    fields = field_lookup(list_fields(client, app_token, table_id))
    missing = []
    for spec in field_specs:
        if spec["field_name"] not in fields:
            missing.append(spec["field_name"])
    return missing


def verify_record_count(client: FeishuClient, app_token: str, table_id: str) -> int:
    return len(list_records(client, app_token, table_id))


def build_markdown_report(result: dict[str, Any]) -> str:
    lines = [
        "# TS-DASH-01 Feishu Table Migration Report",
        "",
        f"- Mode: `{result['mode']}`",
        f"- Timestamp: `{result['timestamp']}`",
        "",
        "## Existing Tables",
        "",
    ]
    for item in result["existing_tables"]:
        lines.append(f"### {item['label']}")
        lines.append("")
        lines.append(f"- Status: `{item['status']}`")
        lines.append(f"- Table ID: `{item['table_id']}`")
        lines.append(f"- Created Fields: {', '.join(item['created_fields']) if item['created_fields'] else 'none'}")
        if item["option_updates"]:
            lines.append(f"- Option Updates: `{json.dumps(item['option_updates'], ensure_ascii=False)}`")
        else:
            lines.append("- Option Updates: none")
        lines.append(f"- Row Actions: `{item['row_action_summary']}`")
        if item.get("verification"):
            lines.append(f"- Verification: `{json.dumps(item['verification'], ensure_ascii=False)}`")
        if item.get("error"):
            lines.append(f"- Error: `{item['error']}`")
        lines.append("")
    lines.extend(["## New Tables", ""])
    for item in result["new_tables"]:
        lines.append(f"### {item['table_name']}")
        lines.append("")
        lines.append(f"- Status: `{item['status']}`")
        lines.append(f"- Table ID: `{item['table_id']}`")
        lines.append(f"- Table Created: `{item['table_created']}`")
        lines.append(f"- Created Fields: {', '.join(item['created_fields']) if item['created_fields'] else 'none'}")
        lines.append(f"- Row Actions: `{item['row_action_summary']}`")
        if item.get("verification"):
            lines.append(f"- Verification: `{json.dumps(item['verification'], ensure_ascii=False)}`")
        if item.get("error"):
            lines.append(f"- Error: `{item['error']}`")
        lines.append("")
    lines.extend(
        [
            "## New Table IDs",
            "",
            f"- 三向量进度: `{result['new_table_ids'].get('三向量进度', '')}`",
            f"- 三方协同日志: `{result['new_table_ids'].get('三方协同日志', '')}`",
            f"- 记忆层健康度: `{result['new_table_ids'].get('记忆层健康度', '')}`",
            "",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def run_migration(*, apply_changes: bool, run_dir: Path) -> dict[str, Any]:
    client = FeishuClient()
    if not client.available:
        raise RuntimeError("FEISHU_APP_ID / FEISHU_APP_SECRET are required")

    spec = ts_dash_01_spec()
    result: dict[str, Any] = {
        "mode": "apply" if apply_changes else "dry-run",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
        "existing_tables": [],
        "new_tables": [],
        "new_table_ids": {},
    }

    for table_spec in spec["existing_tables"]:
        table_result: dict[str, Any] = {
            "label": table_spec["label"],
            "table_id": table_spec["table_id"],
            "status": "success",
            "created_fields": [],
            "option_updates": {},
            "row_action_summary": {"create": 0, "update": 0},
        }
        try:
            created = ensure_fields_for_table(
                client,
                table_spec["app_token"],
                table_spec["table_id"],
                table_spec["field_specs"],
                dry_run=not apply_changes,
            )
            rows = upsert_rows(
                client,
                table_spec["app_token"],
                table_spec["table_id"],
                table_spec["primary_field"],
                table_spec["rows"],
                dry_run=not apply_changes,
            )
            summary = {"create": 0, "update": 0}
            for row in rows:
                summary[row["action"]] += 1
            table_result["created_fields"] = created["created_fields"]
            table_result["option_updates"] = created["option_updates"]
            table_result["row_action_summary"] = summary
            if apply_changes:
                verification = {
                    "missing_fields": verify_existing_field_names(client, table_spec["app_token"], table_spec["table_id"], table_spec["field_specs"]),
                }
                if table_spec["label"] == "L0_运行态总控":
                    runtime_rows = list_records(client, table_spec["app_token"], table_spec["table_id"])
                    target = next((row for row in runtime_rows if (row.get("fields") or {}).get("active_round") == "R17"), None)
                    verification["agent_generation"] = str((target or {}).get("fields", {}).get("agent_generation", ""))
                table_result["verification"] = verification
        except Exception as exc:
            table_result["status"] = "failed"
            table_result["error"] = str(exc)
        result["existing_tables"].append(table_result)

    for table_spec in spec["new_tables"]:
        table_result: dict[str, Any] = {
            "table_name": table_spec["table_name"],
            "table_id": "",
            "status": "success",
            "table_created": False,
            "created_fields": [],
            "option_updates": {},
            "row_action_summary": {"create": 0, "update": 0},
        }
        try:
            ensured = ensure_table(client, table_spec["app_token"], table_spec, dry_run=not apply_changes)
            rows = upsert_rows(
                client,
                table_spec["app_token"],
                ensured["table_id"],
                table_spec["primary_field"]["field_name"],
                table_spec["rows"],
                dry_run=not apply_changes,
            )
            summary = {"create": 0, "update": 0}
            for row in rows:
                summary[row["action"]] += 1
            table_result["table_id"] = ensured["table_id"]
            table_result["table_created"] = ensured["table_created"]
            table_result["created_fields"] = ensured["created_fields"]
            table_result["option_updates"] = ensured["option_updates"]
            table_result["row_action_summary"] = summary
            result["new_table_ids"][table_spec["table_name"]] = ensured["table_id"]
            if apply_changes:
                verification = {
                    "missing_fields": verify_existing_field_names(
                        client,
                        table_spec["app_token"],
                        ensured["table_id"],
                        [table_spec["primary_field"], *table_spec["fields"]],
                    ),
                    "record_count": verify_record_count(client, table_spec["app_token"], ensured["table_id"]),
                }
                table_result["verification"] = verification
        except Exception as exc:
            table_result["status"] = "failed"
            table_result["error"] = str(exc)
        result["new_tables"].append(table_result)

    run_dir.mkdir(parents=True, exist_ok=True)
    handoff_path = run_dir / "handoff.json"
    report_path = run_dir / "feishu-table-migration-report.md"
    raw_path = run_dir / f"ts-dash-01-feishu-migration-{result['mode']}.json"
    result["artifacts"] = {
        "handoff_json": str(handoff_path),
        "report_md": str(report_path),
        "raw_json": str(raw_path),
    }
    raw_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    handoff_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(build_markdown_report(result), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir = Path(args.run_dir)
    result = run_migration(apply_changes=bool(args.apply), run_dir=run_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
