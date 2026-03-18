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

from dashboard.runtime_control import RuntimeControlPlane
from scripts.dashboard_close_task_hooks import now_ms, upsert_rows
from scripts.sync_r11_v2_skill_inventory_feishu import bootstrap_client, list_fields, list_records, list_tables
from scripts.sync_governance_dashboard_base import api


PVDG_BASE = "PVDgbdWYFaDLBiss0hlcM5WRnQc"
OLD_GOVERNANCE_BASE = "XkzJb6QDtaL21wshfUXcsn5knyg"
VECTOR_TABLE_ID = "tblx8lmiEkUzAnON"
COLLAB_TABLE_ID = "tbl67a3vUXDaIjRF"
CHRONICLE_TABLE_ID = "tblpNcHFMZpsiu1P"
RUN_DIR = (
    REPO_ROOT
    / "work/ai-da-guan-jia/artifacts/ai-da-guan-jia/runs/2026-03-17/adagj-20260317-224356-000000"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Patch TS-KB-03 closure rows into governance mirrors.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--account-id", default="feishu-claw")
    return parser.parse_args(argv)


def normalize_fields(fields: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in fields.items() if value is not None}


def maybe_int(value: Any) -> Any:
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    return value


def field_name_set(client: Any, app_token: str, table_id: str) -> set[str]:
    return {str(item.get("field_name") or item.get("name") or "").strip() for item in list_fields(client, app_token, table_id)}


def find_table_id(client: Any, app_token: str, table_name: str) -> str:
    for table in list_tables(client, app_token):
        if str(table.get("name") or "").strip() == table_name:
            return str(table.get("table_id") or "").strip()
    return ""


def upsert_single(
    client: Any,
    app_token: str,
    table_id: str,
    primary_field: str,
    row: dict[str, Any],
    *,
    dry_run: bool,
) -> list[dict[str, Any]]:
    return upsert_rows(client, app_token, table_id, primary_field, [normalize_fields(row)], dry_run=dry_run)


def build_rows() -> dict[str, Any]:
    completion_ms = now_ms()
    return {
        "vector": {
            "task_id": "TS-KB-03",
            "task_name": "康波智库完整落地",
            "vector": "V2",
            "phase": "P1",
            "week": 2,
            "executor": "大管家",
            "status": "已完成",
            "completion_date": completion_ms,
            "handoff_summary": "康波智库 L2×33 / L3 seed×48 已落地，scan_t0 首轮手动验真已追写 1 条增量洞察，expert capability JSON 已导出。",
            "blockers": "",
        },
        "collab": [
            {
                "interaction_id": "COLLAB-20260317-TSKB03-001",
                "timestamp": completion_ms - 180000,
                "from_role": "Claude",
                "to_role": "Codex",
                "interaction_type": "task_spec",
                "summary": "TS-KB-03 FINAL 分发：康波智库完整落地执行终稿",
                "quality_score": 4,
                "round_ref": "R18-KB-03",
            },
            {
                "interaction_id": "COLLAB-20260317-TSKB03-002",
                "timestamp": completion_ms - 120000,
                "from_role": "Codex",
                "to_role": "Human",
                "interaction_type": "evidence",
                "summary": "TS-KB-03 完成：L2×33、L3 seed×48、scan_t0 增量×1、capability 导出完成",
                "quality_score": 5,
                "round_ref": "R18-KB-03",
            },
        ],
        "chronicle": {
            "milestone_id": "EVO-2.0-KB",
            "version": "2.0",
            "phase": "R18",
            "date": completion_ms,
            "milestone_name": "康波智库三层专家体系",
            "organ_gained": "投研层专家网络与洞察层",
            "machine_description": "L1 事件信号之上新增 L2 专家智库 33 条、L3 专家洞察 48 条 seed，并验证 scan_t0 Hook V1。",
            "human_translation": "投研从零散观点升级为可追踪的专家网络与洞察层。",
            "what_solved": "专家观点追踪体系化，康波前台具备接入专家雷达的数据底座。",
            "what_unsolved": "scan_t1/scan_t2 仍是手动入口，定时自动化与付费研报抓取尚未闭环。",
            "evidence_level": "api_verified",
        },
        "evolution": {
            "round_id": "R18-KB-03",
            "status": "completed",
            "gained": "康波智库33专家+48洞察+scan_t0 Hook V1",
            "component_domain": "投研层",
            "date": completion_ms,
        },
    }


def filter_known_fields(row: dict[str, Any], available_fields: set[str]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key in available_fields}


def verify(client: Any, evolution_table_id: str) -> dict[str, Any]:
    vector_rows = list_records(client, PVDG_BASE, VECTOR_TABLE_ID)
    collab_rows = list_records(client, PVDG_BASE, COLLAB_TABLE_ID)
    chronicle_rows = list_records(client, PVDG_BASE, CHRONICLE_TABLE_ID)
    evolution_rows = list_records(client, OLD_GOVERNANCE_BASE, evolution_table_id) if evolution_table_id else []
    runtime = RuntimeControlPlane(client=client).get_current() or {}
    vector = next((row.get("fields") or {} for row in vector_rows if str((row.get("fields") or {}).get("task_id") or "") == "TS-KB-03"), {})
    collab_ids = sorted(
        str((row.get("fields") or {}).get("interaction_id") or "")
        for row in collab_rows
        if str((row.get("fields") or {}).get("round_ref") or "") == "R18-KB-03"
    )
    chronicle = next((row.get("fields") or {} for row in chronicle_rows if str((row.get("fields") or {}).get("milestone_id") or "") == "EVO-2.0-KB"), {})
    evolution = next((row.get("fields") or {} for row in evolution_rows if str((row.get("fields") or {}).get("round_id") or "") == "R18-KB-03"), {})
    return {
        "vector_status": vector,
        "collab_ids": collab_ids,
        "chronicle": chronicle,
        "evolution": evolution,
        "runtime_control": {
            "last_evolution_round": runtime.get("last_evolution_round"),
            "last_evolution_status": runtime.get("last_evolution_status"),
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    client = bootstrap_client(args.account_id)
    dry_run = bool(args.dry_run)
    rows = build_rows()

    collab_actions = upsert_rows(client, PVDG_BASE, COLLAB_TABLE_ID, "interaction_id", rows["collab"], dry_run=dry_run)
    vector_actions = upsert_rows(client, PVDG_BASE, VECTOR_TABLE_ID, "task_id", [rows["vector"]], dry_run=dry_run)

    chronicle_fields = field_name_set(client, PVDG_BASE, CHRONICLE_TABLE_ID)
    chronicle_row = filter_known_fields(rows["chronicle"], chronicle_fields)
    chronicle_actions = upsert_single(client, PVDG_BASE, CHRONICLE_TABLE_ID, "milestone_id", chronicle_row, dry_run=dry_run)

    evolution_table_id = find_table_id(client, OLD_GOVERNANCE_BASE, "进化轨迹")
    evolution_actions: list[dict[str, Any]] = []
    if evolution_table_id:
        evolution_fields = field_name_set(client, OLD_GOVERNANCE_BASE, evolution_table_id)
        evolution_row = filter_known_fields(rows["evolution"], evolution_fields)
        primary_field = "round_id" if "round_id" in evolution_fields else next(iter(evolution_fields))
        evolution_actions = upsert_single(
            client,
            OLD_GOVERNANCE_BASE,
            evolution_table_id,
            primary_field,
            evolution_row,
            dry_run=dry_run,
        )

    runtime_control = RuntimeControlPlane(client=client)
    current_runtime = runtime_control.get_current() or {}
    runtime_payload = dict(current_runtime)
    for key in ["pending_human_actions", "system_blockers", "total_commits", "total_tests_passed"]:
        if key in runtime_payload:
            runtime_payload[key] = maybe_int(runtime_payload[key])
    runtime_payload["last_evolution_round"] = "R18-KB-03"
    runtime_payload["last_evolution_status"] = "completed"
    runtime_result = runtime_control.upsert(runtime_payload, dry_run=dry_run)

    payload = {
        "mode": "apply" if not dry_run else "dry-run",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
        "collab_action_summary": {"create": sum(1 for item in collab_actions if item["action"] == "create"), "update": sum(1 for item in collab_actions if item["action"] == "update")},
        "vector_action_summary": {"create": sum(1 for item in vector_actions if item["action"] == "create"), "update": sum(1 for item in vector_actions if item["action"] == "update")},
        "chronicle_action_summary": {"create": sum(1 for item in chronicle_actions if item["action"] == "create"), "update": sum(1 for item in chronicle_actions if item["action"] == "update")},
        "evolution_action_summary": {"create": sum(1 for item in evolution_actions if item["action"] == "create"), "update": sum(1 for item in evolution_actions if item["action"] == "update")},
        "runtime_control_result": runtime_result,
        "evolution_table_id": evolution_table_id,
    }
    if not dry_run:
        payload["verification"] = verify(client, evolution_table_id)
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RUN_DIR / f"ts-kb-03-governance-patch-{'apply' if not dry_run else 'dry-run'}.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
