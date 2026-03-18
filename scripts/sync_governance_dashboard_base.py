from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.runtime_control import RuntimeControlPlane
from mcp_server_feishu.feishu_client import FeishuClient


TARGET_APP_TOKEN = "PVDgbdWYFaDLBiss0hlcM5WRnQc"
RUNTIME_SOURCE_APP_TOKEN = "PHp2wURl2i6SyBkDtmGcuaEenag"
OLD_GOVERNANCE_APP_TOKEN = "XkzJb6QDtaL21wshfUXcsn5knyg"

TABLE_SPECS = (
    {
        "name": "L0_运行态总控",
        "source_app_token": RUNTIME_SOURCE_APP_TOKEN,
        "source_table_id": "tblnRCmMS7QBMtHI",
        "managed_by_runtime_control": True,
    },
    {
        "name": "组件热图",
        "source_app_token": OLD_GOVERNANCE_APP_TOKEN,
        "source_table_id": "tblBZfqAcFJzjOmd",
    },
    {
        "name": "战略链路",
        "source_app_token": OLD_GOVERNANCE_APP_TOKEN,
        "source_table_id": "tblDfGetDlvYZ7iN",
    },
    {
        "name": "组件责任",
        "source_app_token": OLD_GOVERNANCE_APP_TOKEN,
        "source_table_id": "tblHjuh31vwrcqG2",
    },
    {
        "name": "进化轨迹",
        "source_app_token": OLD_GOVERNANCE_APP_TOKEN,
        "source_table_id": "tbl68xR3EBKy6hG5",
    },
    {
        "name": "决策记录",
        "source_app_token": OLD_GOVERNANCE_APP_TOKEN,
        "source_table_id": "tbl0m8Ir7tedNDkt",
    },
)


@dataclass(frozen=True)
class TableSyncResult:
    name: str
    source_app_token: str
    source_table_id: str
    target_table_id: str
    primary_field: str
    created_records: int
    updated_records: int
    source_record_count: int


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap and sync the new Feishu governance dashboard base.")
    parser.add_argument("--target-app-token", default=TARGET_APP_TOKEN)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--output",
        default="artifacts/ai-da-guan-jia/governance-base-sync-latest.json",
        help="Where to write the sync report JSON.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    client = FeishuClient()
    if not client.available:
        raise SystemExit("FEISHU_APP_ID / FEISHU_APP_SECRET are required")

    tables_before = list_tables(client, args.target_app_token)
    results: list[TableSyncResult] = []
    table_mapping: dict[str, dict[str, Any]] = {}

    for spec in TABLE_SPECS:
        result = sync_table_spec(client, args.target_app_token, spec, dry_run=args.dry_run)
        results.append(result)
        table_mapping[spec["name"]] = {
            "target_app_token": args.target_app_token,
            "target_table_id": result.target_table_id,
            "source_app_token": spec["source_app_token"],
            "source_table_id": spec["source_table_id"],
            "primary_field": result.primary_field,
            "source_record_count": result.source_record_count,
        }

    payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "target_app_token": args.target_app_token,
        "dry_run": bool(args.dry_run),
        "existing_tables_before": tables_before,
        "tables": [result.__dict__ for result in results],
        "table_mapping": table_mapping,
    }
    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def sync_table_spec(
    client: FeishuClient,
    target_app_token: str,
    spec: dict[str, Any],
    *,
    dry_run: bool,
) -> TableSyncResult:
    table_name = str(spec["name"]).strip()
    source_app_token = str(spec["source_app_token"]).strip()
    source_table_id = str(spec["source_table_id"]).strip()

    if spec.get("managed_by_runtime_control"):
        source_fields = list_fields(client, source_app_token, source_table_id)
        if dry_run:
            target_table_id = existing_table_id(client, target_app_token, table_name) or f"dryrun::{table_name}"
        else:
            target_table_id = RuntimeControlPlane(
                client=client,
                app_token=target_app_token,
                table_name=table_name,
            ).ensure_table()
    else:
        source_fields = list_fields(client, source_app_token, source_table_id)
        target_table_id = ensure_cloned_table(
            client,
            target_app_token,
            table_name,
            source_fields=source_fields,
            dry_run=dry_run,
        )

    primary_field = primary_field_name(source_fields)
    source_records = list_records(client, source_app_token, source_table_id)
    created_records, updated_records = upsert_records(
        client,
        target_app_token,
        target_table_id,
        source_records,
        primary_field=primary_field,
        dry_run=dry_run,
    )
    return TableSyncResult(
        name=table_name,
        source_app_token=source_app_token,
        source_table_id=source_table_id,
        target_table_id=target_table_id,
        primary_field=primary_field,
        created_records=created_records,
        updated_records=updated_records,
        source_record_count=len(source_records),
    )


def ensure_cloned_table(
    client: FeishuClient,
    target_app_token: str,
    table_name: str,
    *,
    source_fields: list[dict[str, Any]],
    dry_run: bool,
) -> str:
    existing_id = existing_table_id(client, target_app_token, table_name)
    if existing_id:
        ensure_fields_match(client, target_app_token, existing_id, source_fields, dry_run=dry_run)
        return existing_id

    if dry_run:
        return f"dryrun::{table_name}"

    created = api(
        client,
        "POST",
        f"/bitable/v1/apps/{target_app_token}/tables",
        {"table": {"name": table_name}},
    )
    table = (created.get("data", {}) or {}).get("table", {}) or {}
    table_id = str(table.get("table_id", "")).strip()
    if not table_id:
        table_id = existing_table_id(client, target_app_token, table_name)
    if not table_id:
        raise RuntimeError(f"failed to create table {table_name}")
    ensure_fields_match(client, target_app_token, table_id, source_fields, dry_run=dry_run)
    return table_id


def ensure_fields_match(
    client: FeishuClient,
    target_app_token: str,
    target_table_id: str,
    source_fields: list[dict[str, Any]],
    *,
    dry_run: bool,
) -> str:
    target_fields = list_fields(client, target_app_token, target_table_id) if not dry_run else []
    source_primary = next((field for field in source_fields if field.get("is_primary")), source_fields[0] if source_fields else None)
    if source_primary is None:
        return ""

    source_primary_name = field_name(source_primary)
    source_primary_type = int(source_primary.get("type") or 1)
    effective_primary_name = source_primary_name
    if not dry_run and target_fields:
        target_primary = next((field for field in target_fields if field.get("is_primary")), target_fields[0])
        target_primary_name = field_name(target_primary)
        target_primary_type = int(target_primary.get("type") or 1)
        rename_primary_to = ""
        if source_primary_type == 1 and target_primary_type == 1:
            rename_primary_to = source_primary_name
        elif target_primary_name in {"多行文本", "文本", ""}:
            rename_primary_to = "sync_primary_key"
            effective_primary_name = rename_primary_to
        else:
            effective_primary_name = target_primary_name
        if rename_primary_to and target_primary_name != rename_primary_to:
            api(
                client,
                "PUT",
                f"/bitable/v1/apps/{target_app_token}/tables/{target_table_id}/fields/{target_primary['field_id']}",
                {"field_name": rename_primary_to, "type": target_primary_type},
            )
            target_fields = list_fields(client, target_app_token, target_table_id)
        else:
            effective_primary_name = target_primary_name

    target_names = {field_name(item) for item in target_fields}
    for field in source_fields:
        name = field_name(field)
        if not name or name == effective_primary_name:
            continue
        if name in target_names:
            continue
        if dry_run:
            continue
        body: dict[str, Any] = {
            "field_name": name,
            "type": int(field.get("type") or 1),
        }
        property_payload = sanitize_field_property(int(field.get("type") or 1), field.get("property"))
        if property_payload:
            body["property"] = property_payload
        api(
            client,
            "POST",
            f"/bitable/v1/apps/{target_app_token}/tables/{target_table_id}/fields",
            body,
        )
        target_names.add(name)
    return effective_primary_name


def upsert_records(
    client: FeishuClient,
    target_app_token: str,
    target_table_id: str,
    source_records: list[dict[str, Any]],
    *,
    primary_field: str,
    dry_run: bool,
) -> tuple[int, int]:
    if not source_records:
        return 0, 0
    if dry_run:
        return len(source_records), 0

    target_fields = list_fields(client, target_app_token, target_table_id)
    target_field_types = {
        field_name(field): int(field.get("type") or 1)
        for field in target_fields
        if field_name(field)
    }
    target_primary_name = primary_field_name(target_fields)
    target_records = list_records(client, target_app_token, target_table_id)
    existing_by_key: dict[str, str] = {}
    for record in target_records:
        fields = record.get("fields", {}) or {}
        key = compare_key(fields.get(primary_field))
        if key:
            existing_by_key[key] = str(record.get("record_id") or record.get("id") or "").strip()

    to_create: list[dict[str, Any]] = []
    to_update: list[dict[str, Any]] = []
    for record in source_records:
        fields = normalize_fields(dict(record.get("fields", {}) or {}), target_field_types)
        key = compare_key(fields.get(primary_field))
        if not key:
            continue
        if target_primary_name and target_primary_name not in fields:
            fields[target_primary_name] = key
        record_id = existing_by_key.get(key, "")
        if record_id:
            to_update.append({"record_id": record_id, "fields": fields})
        else:
            to_create.append({"fields": fields})

    batch_request(client, "POST", f"/bitable/v1/apps/{target_app_token}/tables/{target_table_id}/records/batch_create", to_create)
    batch_request(client, "POST", f"/bitable/v1/apps/{target_app_token}/tables/{target_table_id}/records/batch_update", to_update)
    return len(to_create), len(to_update)


def batch_request(client: FeishuClient, method: str, path: str, records: list[dict[str, Any]], *, size: int = 500) -> None:
    for start in range(0, len(records), size):
        chunk = records[start : start + size]
        if not chunk:
            continue
        api(client, method, path, {"records": chunk})


def list_tables(client: FeishuClient, app_token: str) -> list[dict[str, Any]]:
    payload = api(client, "GET", f"/bitable/v1/apps/{app_token}/tables?page_size=500")
    return list((payload.get("data", {}) or {}).get("items", []) or [])


def existing_table_id(client: FeishuClient, app_token: str, table_name: str) -> str:
    for table in list_tables(client, app_token):
        if str(table.get("name", "")).strip() == table_name:
            return str(table.get("table_id", "")).strip()
    return ""


def list_fields(client: FeishuClient, app_token: str, table_id: str) -> list[dict[str, Any]]:
    return paged_items(client, f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields")


def list_records(client: FeishuClient, app_token: str, table_id: str) -> list[dict[str, Any]]:
    return paged_items(client, f"/bitable/v1/apps/{app_token}/tables/{table_id}/records")


def paged_items(client: FeishuClient, path: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page_token = ""
    while True:
        query = {"page_size": 500}
        if page_token:
            query["page_token"] = page_token
        request_path = f"{path}?{urlencode(query)}"
        payload = api(client, "GET", request_path)
        data = payload.get("data", {}) or {}
        items.extend(list(data.get("items", []) or []))
        if not data.get("has_more"):
            break
        page_token = str(data.get("page_token", "")).strip()
        if not page_token:
            break
    return items


def primary_field_name(fields: list[dict[str, Any]]) -> str:
    primary = next((field for field in fields if field.get("is_primary")), fields[0] if fields else None)
    if primary is None:
        raise RuntimeError("source table has no fields")
    return field_name(primary)


def field_name(field: dict[str, Any]) -> str:
    return str(field.get("field_name") or field.get("name") or "").strip()


def compare_key(value: Any) -> str:
    return str("" if value is None else value).strip()


def normalize_fields(fields: dict[str, Any], target_field_types: dict[str, int]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for name, value in fields.items():
        field_type = int(target_field_types.get(name, 1))
        normalized_value = normalize_value(value, field_type)
        if normalized_value is _DROP:
            continue
        normalized[name] = normalized_value
    return normalized


class _DropValue:
    pass


_DROP = _DropValue()


def normalize_value(value: Any, field_type: int) -> Any:
    if value is None:
        return _DROP
    if field_type != 2:
        return value
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    if not text:
        return _DROP
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError as exc:
            raise RuntimeError(f"cannot coerce number field value {value!r}") from exc


def sanitize_field_property(field_type: int, property_value: Any) -> dict[str, Any] | None:
    if not isinstance(property_value, dict) or not property_value:
        return None
    if field_type in {3, 4}:
        options = []
        for option in property_value.get("options", []) or []:
            if not isinstance(option, dict):
                continue
            name = str(option.get("name", "")).strip()
            if not name:
                continue
            cleaned = {"name": name}
            if option.get("color") is not None:
                cleaned["color"] = option.get("color")
            options.append(cleaned)
        return {"options": options} if options else None
    return dict(property_value)


def api(
    client: FeishuClient,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = client._request(method, path, body)
    if payload.get("error"):
        raise RuntimeError(str(payload["error"]))
    code = payload.get("code", 0)
    if code not in (0, "0", None):
        raise RuntimeError(str(payload.get("msg") or payload))
    return payload


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
