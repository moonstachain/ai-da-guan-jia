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
from scripts.create_kangbo_signal_tables import DEFAULT_ACCOUNT_ID, load_feishu_credentials
from scripts.boomerang.boomerang_sync import task_tracker_rows_for_brm, write_task_tracker


DEFAULT_REGISTRY_PATH = REPO_ROOT / "artifacts" / "boomerang" / "table_registry.json"
DEFAULT_PAYLOAD_PATH = REPO_ROOT / "data" / "boomerang" / "seed_phase2_payload.json"
DEFAULT_REPORT_PATH = REPO_ROOT / "artifacts" / "boomerang" / "seed_phase2_report.json"
RUNS_ROOT = REPO_ROOT / "artifacts" / "boomerang" / "runs"

READ_ONLY_TYPES = {17, 19, 20, 21, 22}
FIELD_TYPE_NUMBER = 2
FIELD_TYPE_SINGLE_SELECT = 3
FIELD_TYPE_MULTI_SELECT = 4
FIELD_TYPE_DATETIME = 5
FIELD_TYPE_CHECKBOX = 7

TARGET_TABLES = [
    "T07_财务建模",
    "T08_对标矩阵",
    "T09_进化追踪",
    "T10_估值测算",
]

KEY_FIELDS = {
    "T07_财务建模": ["scenario", "year"],
    "T08_对标矩阵": ["company", "data_year"],
    "T09_进化追踪": ["initiative_id"],
    "T10_估值测算": ["round", "target_year"],
}


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def load_client(account_id: str) -> FeishuBitableAPI:
    creds = load_feishu_credentials(account_id)
    os.environ["FEISHU_APP_ID"] = creds["app_id"]
    os.environ["FEISHU_APP_SECRET"] = creds["app_secret"]
    return FeishuBitableAPI(creds["app_id"], creds["app_secret"])


def normalize_name(name: str) -> str:
    return str(name or "").strip().replace(" ", "").replace("（", "(").replace("）", ")")


def _key_part(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_app_token(registry: dict[str, Any]) -> str:
    for key in ("app_token", "appToken", "base_token", "baseToken"):
        token = str(registry.get(key) or "").strip()
        if token:
            return token
    raise RuntimeError("table_registry.json missing app_token")


def resolve_table_id(registry: dict[str, Any], table_name: str) -> str:
    tables = registry.get("tables") or {}
    if isinstance(tables, dict):
        direct = tables.get(table_name)
        if isinstance(direct, dict):
            table_id = str(direct.get("table_id") or direct.get("tableId") or "").strip()
            if table_id:
                return table_id
        if isinstance(direct, str):
            return direct
        for name, payload in tables.items():
            if normalize_name(name) == normalize_name(table_name):
                if isinstance(payload, dict):
                    table_id = str(payload.get("table_id") or payload.get("tableId") or "").strip()
                    if table_id:
                        return table_id
                if isinstance(payload, str):
                    return payload
    if isinstance(tables, list):
        for item in tables:
            name = str(item.get("table_name") or item.get("name") or "").strip()
            if not name:
                continue
            if normalize_name(name) == normalize_name(table_name):
                table_id = str(item.get("table_id") or item.get("tableId") or "").strip()
                if table_id:
                    return table_id
    raise RuntimeError(f"table_registry.json missing table_id for {table_name}")


def list_fields(api: FeishuBitableAPI, app_token: str, table_id: str) -> dict[str, dict[str, Any]]:
    fields = api.list_fields(app_token, table_id)
    return {
        str(item.get("field_name") or item.get("name") or "").strip(): item
        for item in fields
        if str(item.get("field_name") or item.get("name") or "").strip()
    }


def normalize_datetime(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        integer = int(value)
        if abs(integer) >= 10**12:
            return integer // 1000
        return integer
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        integer = int(text)
        if abs(integer) >= 10**12:
            return integer // 1000
        return integer
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return int(parsed.timestamp())
    except ValueError:
        return None


def normalize_number(value: Any) -> int | float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return int(value) if float(value).is_integer() else float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def normalize_value(value: Any, field_type: int) -> Any | None:
    if value is None or value == "":
        return None
    if field_type == FIELD_TYPE_NUMBER:
        return normalize_number(value)
    if field_type == FIELD_TYPE_DATETIME:
        return normalize_datetime(value)
    if field_type == FIELD_TYPE_CHECKBOX:
        return bool(value)
    if field_type == FIELD_TYPE_MULTI_SELECT:
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        text = str(value).strip()
        return [text] if text else None
    if field_type == FIELD_TYPE_SINGLE_SELECT:
        return str(value).strip() if str(value).strip() else None
    return str(value).strip() if str(value).strip() else None


def normalize_record(
    row: dict[str, Any],
    field_lookup: dict[str, dict[str, Any]],
    warnings: list[str],
    *,
    table_name: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in row.items():
        field = field_lookup.get(key)
        if field is None:
            continue
        field_type = int(field.get("type") or 1)
        if field_type in READ_ONLY_TYPES:
            continue
        normalized = normalize_value(value, field_type)
        if normalized is None or normalized == []:
            if field_type == FIELD_TYPE_DATETIME and value not in {"", None}:
                warnings.append(f"{table_name}.{key} datetime value not parsed: {value}")
            continue
        payload[key] = normalized
    return payload


def record_key(row: dict[str, Any], key_fields: list[str]) -> str:
    record_id = _key_part(row.get("record_id"))
    if record_id:
        return record_id
    parts = []
    for field in key_fields:
        part = _key_part(row.get(field))
        if not part:
            return ""
        parts.append(part)
    return "||".join(parts)


def record_key_from_fields(fields: dict[str, Any], key_fields: list[str]) -> str:
    parts = []
    for field in key_fields:
        part = _key_part(fields.get(field))
        if not part:
            return ""
        parts.append(part)
    return "||".join(parts)


def batch(items: list[dict[str, Any]], size: int = 50) -> list[list[dict[str, Any]]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def upsert_records(
    api: FeishuBitableAPI,
    app_token: str,
    table_id: str,
    rows: list[dict[str, Any]],
    *,
    key_fields: list[str],
    field_lookup: dict[str, dict[str, Any]],
    apply_changes: bool,
    warnings: list[str],
    table_name: str,
) -> dict[str, Any]:
    existing_records = api.list_records(app_token, table_id)
    existing_index = {
        record_key_from_fields(record.get("fields") or {}, key_fields): record
        for record in existing_records
        if record_key_from_fields(record.get("fields") or {}, key_fields)
    }
    to_create: list[dict[str, Any]] = []
    to_update: list[dict[str, Any]] = []
    missing_keys: list[int] = []

    for idx, row in enumerate(rows):
        key = record_key(row, key_fields)
        if not key:
            missing_keys.append(idx)
            continue
        payload = normalize_record(row, field_lookup, warnings, table_name=table_name)
        if not payload:
            continue
        existing = existing_index.get(key)
        if existing and existing.get("record_id"):
            to_update.append({"record_id": existing["record_id"], "fields": payload})
        else:
            to_create.append({"fields": payload})

    if apply_changes:
        for chunk in batch(to_create, 50):
            if chunk:
                api._request(
                    f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
                    method="POST",
                    payload={"records": chunk},
                )
        for chunk in batch(to_update, 50):
            if chunk:
                api._request(
                    f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_update",
                    method="POST",
                    payload={"records": chunk},
                )

    refreshed = api.list_records(app_token, table_id)
    return {
        "existing_count": len(existing_records),
        "created_count": len(to_create),
        "updated_count": len(to_update),
        "record_count": len(refreshed),
        "missing_key_rows": missing_keys,
    }


def write_log(log_path: Path, lines: list[str]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def run(*, apply_changes: bool, registry_path: Path, payload_path: Path, report_path: Path, account_id: str) -> dict[str, Any]:
    registry = load_json(registry_path)
    payload = load_json(payload_path)
    app_token = resolve_app_token(registry)
    api = load_client(account_id)

    warnings: list[str] = []
    table_results: list[dict[str, Any]] = []
    for table_name in TARGET_TABLES:
        rows = payload.get(table_name)
        if rows is None:
            rows = next(
                (value for key, value in payload.items() if normalize_name(key) == normalize_name(table_name)),
                None,
            )
        if rows is None:
            raise RuntimeError(f"seed payload missing table: {table_name}")
        if not isinstance(rows, list):
            raise RuntimeError(f"seed payload for {table_name} must be a list")

        prepared_rows: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item.pop("record_id", None)
            item["record_key"] = record_key(item, KEY_FIELDS.get(table_name, []))
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

    report = {
        "status": "applied" if apply_changes else "dry-run",
        "mode": "apply" if apply_changes else "dry-run",
        "registry_path": str(registry_path),
        "payload_path": str(payload_path),
        "app_token": app_token,
        "tables": table_results,
        "warnings": warnings,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if apply_changes:
        completion_date_ms = int(datetime.now().timestamp() * 1000)
        tracker_rows = task_tracker_rows_for_brm(
            task_status_by_id={
                "TS-BRM-01": "已完成",
                "TS-BRM-02": "已完成",
                "TS-BRM-03": "已完成",
            },
            completion_date_by_id={
                "TS-BRM-01": completion_date_ms,
                "TS-BRM-02": completion_date_ms,
                "TS-BRM-03": completion_date_ms,
            },
            evidence_ref_by_id={
                "TS-BRM-01": str(registry_path),
                "TS-BRM-02": str(report_path),
                "TS-BRM-03": str(report_path),
            },
            notes_by_id={
                "TS-BRM-01": "Phase 1 tables built",
                "TS-BRM-02": "Phase 1 ingest completed",
                "TS-BRM-03": "Phase 2 analysis seed completed",
            },
        )
        write_task_tracker(api, tracker_rows, apply=True)

    log_path = RUNS_ROOT / datetime.now().strftime("%Y-%m-%d") / "ts-brm-03-log.md"
    log_lines = [
        f"## TS-BRM-03 {report['mode']} {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"- registry: {registry_path}",
        f"- payload: {payload_path}",
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
    write_log(log_path, log_lines)

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed TS-BRM-03 analysis-layer tables (T07-T10) into Feishu Bitable.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--payload", type=Path, default=DEFAULT_PAYLOAD_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    args = parser.parse_args()

    try:
        result = run(
            apply_changes=bool(args.apply),
            registry_path=args.registry,
            payload_path=args.payload,
            report_path=args.report,
            account_id=args.account_id,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:  # pragma: no cover - preserve failure evidence
        pending_payloads = {}
        try:
            pending_payloads = load_json(args.payload)
        except Exception:
            pending_payloads = {}
        failure = {
            "status": "failed",
            "error": str(exc),
            "registry_path": str(args.registry),
            "payload_path": str(args.payload),
            "pending_payloads": pending_payloads,
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(failure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        log_path = RUNS_ROOT / datetime.now().strftime("%Y-%m-%d") / "ts-brm-03-log.md"
        write_log(
            log_path,
            [
                f"## TS-BRM-03 failed {datetime.now().isoformat(timespec='seconds')}",
                "",
                f"- error: {exc}",
                f"- registry: {args.registry}",
                f"- payload: {args.payload}",
            ],
        )
        print(json.dumps(failure, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
