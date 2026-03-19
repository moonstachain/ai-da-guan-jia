from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.feishu_deploy import FeishuBitableAPI
from scripts.boomerang.boomerang_sync import build_phase1_rows
from scripts.create_kangbo_signal_tables import DEFAULT_ACCOUNT_ID, load_feishu_credentials
from scripts.ts_brm_03_analysis_seed import (
    batch,
    list_fields,
    load_json,
    normalize_name,
    normalize_datetime,
    normalize_record,
    record_key,
    record_key_from_fields,
    resolve_app_token,
    resolve_table_id,
    upsert_records,
)


DEFAULT_REGISTRY_PATH = REPO_ROOT / "artifacts" / "boomerang" / "table_registry.json"
DEFAULT_REPORT_PATH = REPO_ROOT / "artifacts" / "boomerang" / "seed_phase1_report.json"
RUNS_ROOT = REPO_ROOT / "artifacts" / "boomerang" / "runs"

TASK_TRACKER_APP = "PVDgbdWYFaDLBiss0hlcM5WRnQc"
TASK_TRACKER_TABLE = "tblB9JQ4cROTBUnr"

TARGET_TABLES = [
    "T01_月度经营数据",
    "T02_月度财务数据",
    "T03_客户分析",
    "T04_品类分析",
    "T05_供应链效率",
    "T06_内容与IP",
]

KEY_FIELDS = {
    "T01_月度经营数据": ["month", "base", "notes"],
    "T02_月度财务数据": ["month"],
    "T03_客户分析": ["month", "segment_type", "segment_name"],
    "T04_品类分析": ["month", "category", "notes"],
    "T05_供应链效率": [
        "month",
        "logistics_outbound_tickets",
        "logistics_inbound_tickets",
        "logistics_outbound_cost",
        "logistics_inbound_cost",
        "logistics_avg_ticket_cost",
        "notes",
    ],
    "T06_内容与IP": ["month", "platform", "content_type", "notes"],
}


def load_client(account_id: str) -> FeishuBitableAPI:
    creds = load_feishu_credentials(account_id)
    os.environ["FEISHU_APP_ID"] = creds["app_id"]
    os.environ["FEISHU_APP_SECRET"] = creds["app_secret"]
    return FeishuBitableAPI(creds["app_id"], creds["app_secret"])


def batch_create(api: FeishuBitableAPI, app_token: str, table_id: str, rows: list[dict[str, Any]]) -> None:
    for chunk in batch(rows, 50):
        if chunk:
            api._request(
                f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
                method="POST",
                payload={"records": chunk},
            )


def batch_update(api: FeishuBitableAPI, app_token: str, table_id: str, rows: list[dict[str, Any]]) -> None:
    for chunk in batch(rows, 50):
        if chunk:
            api._request(
                f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_update",
                method="POST",
                payload={"records": chunk},
            )


def task_tracker_payload(*, task_status: str, evidence_ref: str, notes: str, completion_date_ms: int | None) -> dict[str, Any]:
    payload = {
        "task_id": "TS-BRM-02",
        "project_id": "PROJ-BOOMERANG",
        "project_name": "回旋镖局战略经营驾驶舱",
        "project_status": "进行中",
        "task_name": "回旋镖局飞书多维表历史数据灌入（Phase 1: 6张表）",
        "task_status": task_status,
        "priority": "P0",
        "owner": "Codex",
        "evidence_ref": evidence_ref,
        "notes": notes,
    }
    if completion_date_ms is not None:
        payload["completion_date"] = completion_date_ms
    return payload


def upsert_task_tracker(api: FeishuBitableAPI, *, payload: dict[str, Any], apply_changes: bool) -> dict[str, Any]:
    existing = api.list_records(TASK_TRACKER_APP, TASK_TRACKER_TABLE)
    existing_by_task_id = {
        str((record.get("fields") or {}).get("task_id") or "").strip(): record for record in existing
    }
    current = existing_by_task_id.get(payload["task_id"])
    create_payload: list[dict[str, Any]] = []
    update_payload: list[dict[str, Any]] = []
    action = "none"
    if current:
        update_payload.append({"record_id": current.get("record_id") or current.get("id"), "fields": payload})
        action = "update"
    else:
        create_payload.append(payload)
        action = "create"
    if apply_changes and create_payload:
        batch_create(api, TASK_TRACKER_APP, TASK_TRACKER_TABLE, [{"fields": row} for row in create_payload])
    if apply_changes and update_payload:
        batch_update(api, TASK_TRACKER_APP, TASK_TRACKER_TABLE, update_payload)
    return {"action": action, "applied": apply_changes}


def run(*, apply_changes: bool, registry_path: Path, report_path: Path, account_id: str) -> dict[str, Any]:
    registry = load_json(registry_path)
    app_token = resolve_app_token(registry)
    api = load_client(account_id)

    warnings: list[str] = []
    phase1_rows = build_phase1_rows()
    table_results: list[dict[str, Any]] = []

    for table_name in TARGET_TABLES:
        rows = phase1_rows.get(table_name, [])
        prepared_rows: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            record_id = str(item.pop("record_id", "")).strip()
            if "month" in item:
                normalized_month = normalize_datetime(item["month"])
                if normalized_month is not None:
                    item["month"] = normalized_month
            item["record_key"] = record_id or record_key(item, KEY_FIELDS.get(table_name, []))
            prepared_rows.append(item)
        table_id = resolve_table_id(registry, table_name)
        fields = list_fields(api, app_token, table_id)
        if prepared_rows:
            unknown_fields = sorted({key for key in prepared_rows[0].keys() if key not in fields})
            if unknown_fields:
                warnings.append(f"{table_name} has payload fields not in Feishu table: {unknown_fields}")

        key_fields = ["record_key"]
        missing_fields = [name for name in key_fields if name not in fields]
        if missing_fields:
            raise RuntimeError(f"{table_name} missing key fields in Feishu: {missing_fields}")

        result = upsert_records(
            api,
            app_token,
            table_id,
            prepared_rows,
            key_fields=key_fields,
            field_lookup=fields,
            apply_changes=apply_changes,
            warnings=warnings,
            table_name=table_name,
        )
        table_results.append(
            {
                "table_name": table_name,
                "table_id": table_id,
                "seed_count": len(prepared_rows),
                "key_fields": key_fields,
                "natural_key_fields": KEY_FIELDS.get(table_name, []),
                **result,
            }
        )

    completion_date = int(datetime.now().timestamp() * 1000) if apply_changes else None
    tracker_payload = task_tracker_payload(
        task_status="已完成" if apply_changes else "进行中",
        evidence_ref=str(report_path),
        notes="TS-BRM-02 phase1 ingest",
        completion_date_ms=completion_date,
    )
    tracker_result = upsert_task_tracker(api, payload=tracker_payload, apply_changes=apply_changes)

    report = {
        "status": "applied" if apply_changes else "dry-run",
        "mode": "apply" if apply_changes else "dry-run",
        "registry_path": str(registry_path),
        "app_token": app_token,
        "tables": table_results,
        "warnings": warnings,
        "task_tracker": tracker_result,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    log_path = RUNS_ROOT / datetime.now().strftime("%Y-%m-%d") / "ts-brm-02-log.md"
    log_lines = [
        f"## TS-BRM-02 {report['mode']} {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"- registry: {registry_path}",
        f"- app_token: {app_token}",
    ]
    for table in table_results:
        log_lines.append(
            f"- {table['table_name']}: seed={table['seed_count']} created={table['created_count']} updated={table['updated_count']} existing={table['existing_count']}"
        )
    if warnings:
        log_lines.append("")
        log_lines.append("Warnings:")
        log_lines.extend([f"- {item}" for item in warnings])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="TS-BRM-02: ingest phase1 historical data for T01-T06.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    args = parser.parse_args()

    try:
        result = run(
            apply_changes=bool(args.apply),
            registry_path=args.registry,
            report_path=args.report,
            account_id=args.account_id,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:  # pragma: no cover - preserve failure evidence
        failure = {
            "status": "failed",
            "error": str(exc),
            "registry_path": str(args.registry),
            "report_path": str(args.report),
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(failure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        log_path = RUNS_ROOT / datetime.now().strftime("%Y-%m-%d") / "ts-brm-02-log.md"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            "\n".join(
                [
                    f"## TS-BRM-02 failed {datetime.now().isoformat(timespec='seconds')}",
                    "",
                    f"- error: {exc}",
                    f"- registry: {args.registry}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        print(json.dumps(failure, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
