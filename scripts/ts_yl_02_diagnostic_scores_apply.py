#!/usr/bin/env python3
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

from scripts.relation_remap_apply import (  # noqa: E402
    DEFAULT_ACCOUNT_ID,
    DEFAULT_APP_TOKEN,
    api,
    ensure_relation_field,
    field_name,
    fetch_tenant_access_token,
    list_fields,
    list_records,
    list_tables,
    load_feishu_credentials,
    primary_field_name,
    record_id_index,
)

MANIFEST_PATH = Path("/Users/liming/Downloads/files (3).zip")
DEFAULT_EXTRACTED_MANIFEST = Path("/tmp/ts_yl_02_input/t9s-scores-manifest.json")
TARGET_TABLE_NAME = "T9S_诊断评分记录"
TARGET_RELATION_TABLES = {
    "学员ID": {
        "table_name": "T4_企业模式诊断表",
        "table_id": "tblCHuXSGfM3WRQC",
        "primary_field": "诊断ID",
        "multiple": False,
    },
    "控制点编号": {
        "table_name": "T9_32维诊断控制点",
        "table_id": "tblVs2BhDbdW6BpI",
        "primary_field": "编号",
        "multiple": False,
    },
}
TEXT_FIELD = 1
SINGLE_SELECT_FIELD = 3
RELATION_FIELD = 21
DEFAULT_BATCH_SIZE = 100


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def table_by_name(token: str, app_token: str, table_name: str) -> dict[str, Any] | None:
    return next((table for table in list_tables(token, app_token) if str(table.get("name") or "").strip() == table_name), None)


def ensure_table(token: str, app_token: str, table_name: str) -> tuple[str, bool]:
    existing = table_by_name(token, app_token, table_name)
    if existing:
        return str(existing.get("table_id") or "").strip(), False
    created = api(token, "POST", f"/bitable/v1/apps/{app_token}/tables", body={"table": {"name": table_name}})
    table = ((created.get("data") or {}).get("table") or {})
    table_id = str(table.get("table_id") or "").strip()
    if not table_id:
        existing = table_by_name(token, app_token, table_name)
        table_id = str((existing or {}).get("table_id") or "").strip()
    if not table_id:
        raise RuntimeError(f"failed to create table {table_name}")
    return table_id, True


def ensure_primary_field(token: str, app_token: str, table_id: str, desired_name: str) -> None:
    fields = list_fields(token, app_token, table_id)
    primary = next((field for field in fields if field.get("is_primary")), None)
    if primary is None:
        raise RuntimeError(f"table {table_id} has no primary field")
    if field_name(primary) == desired_name:
        return
    body = {"field_name": desired_name, "type": int(primary.get("type") or TEXT_FIELD)}
    prop = primary.get("property")
    if isinstance(prop, dict) and prop:
        body["property"] = prop
    api(token, "PUT", f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{primary['field_id']}", body=body)


def ensure_field(
    token: str,
    app_token: str,
    table_id: str,
    *,
    name: str,
    field_type: int,
    property_payload: dict[str, Any] | None = None,
) -> bool:
    current = {field_name(item): item for item in list_fields(token, app_token, table_id)}
    if name in current:
        return False
    body: dict[str, Any] = {"field_name": name, "type": field_type}
    if property_payload:
        body["property"] = property_payload
    api(token, "POST", f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields", body=body)
    return True


def ensure_single_select_field(token: str, app_token: str, table_id: str, name: str, options: list[str]) -> bool:
    property_payload = {"options": [{"name": opt} for opt in options if str(opt).strip()]}
    return ensure_field(token, app_token, table_id, name=name, field_type=SINGLE_SELECT_FIELD, property_payload=property_payload)


def batch_request(token: str, method: str, path: str, records: list[dict[str, Any]], *, chunk_size: int = DEFAULT_BATCH_SIZE) -> None:
    for start in range(0, len(records), chunk_size):
        chunk = records[start : start + chunk_size]
        if not chunk:
            continue
        api(token, method, path, body={"records": chunk})


def chunked(seq: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [seq[i : i + size] for i in range(0, len(seq), size)]


def build_relation_indexes(token: str, app_token: str) -> dict[str, Any]:
    indexes: dict[str, Any] = {}
    for source_field, spec in TARGET_RELATION_TABLES.items():
        table = table_by_name(token, app_token, spec["table_name"])
        if not table:
            raise RuntimeError(f"target table missing: {spec['table_name']}")
        table_id = str(table.get("table_id") or "").strip()
        fields = list_fields(token, app_token, table_id)
        primary_name = primary_field_name(fields)
        records = list_records(token, app_token, table_id)
        indexes[source_field] = {
            "table_id": table_id,
            "primary_field": primary_name,
            "record_id_by_primary": record_id_index(records, primary_name),
            "record_count": len(records),
        }
    return indexes


def normalize_seed_row(row: dict[str, Any], relation_indexes: dict[str, Any]) -> dict[str, Any]:
    normalized = {key: value for key, value in row.items() if value not in (None, "")}
    student_id = str(row.get("学员ID") or "").strip()
    control_point = str(row.get("控制点编号") or "").strip()
    student_record_id = relation_indexes["学员ID"]["record_id_by_primary"].get(student_id)
    control_record_id = relation_indexes["控制点编号"]["record_id_by_primary"].get(control_point)
    if not student_record_id:
        raise RuntimeError(f"missing T4 record for 学员ID={student_id}")
    if not control_record_id:
        raise RuntimeError(f"missing T9 record for 控制点编号={control_point}")
    normalized["学员ID_link"] = [student_record_id]
    normalized["控制点编号_link"] = [control_record_id]
    return normalized


def ensure_schema(token: str, app_token: str, table_id: str) -> dict[str, Any]:
    created_table = False
    created_table_id = table_id
    if not created_table_id:
        created_table_id, created_table = ensure_table(token, app_token, TARGET_TABLE_NAME)
    ensure_primary_field(token, app_token, created_table_id, "评分ID")

    field_created = []
    field_created.append(("学员ID_link", ensure_relation_field(
        token,
        app_token,
        created_table_id,
        "学员ID",
        target_table_id=TARGET_RELATION_TABLES["学员ID"]["table_id"],
        back_field_name="T9S_学员ID_back",
        multiple=False,
    )))
    field_created.append(("控制点编号_link", ensure_relation_field(
        token,
        app_token,
        created_table_id,
        "控制点编号",
        target_table_id=TARGET_RELATION_TABLES["控制点编号"]["table_id"],
        back_field_name="T9S_控制点编号_back",
        multiple=False,
    )))
    ensure_field(token, app_token, created_table_id, name="学员姓名", field_type=TEXT_FIELD)
    ensure_field(token, app_token, created_table_id, name="企业名称", field_type=TEXT_FIELD)
    ensure_field(token, app_token, created_table_id, name="控制点名称", field_type=TEXT_FIELD)
    ensure_field(token, app_token, created_table_id, name="所属模块", field_type=TEXT_FIELD)
    ensure_field(token, app_token, created_table_id, name="当前评分", field_type=TEXT_FIELD)
    ensure_field(token, app_token, created_table_id, name="评分依据", field_type=TEXT_FIELD)
    ensure_single_select_field(token, app_token, created_table_id, "优先级", ["P0", "P1", "P2"])
    ensure_field(token, app_token, created_table_id, name="上次评分", field_type=TEXT_FIELD)
    ensure_field(token, app_token, created_table_id, name="评分变化", field_type=TEXT_FIELD)
    return {
        "table_id": created_table_id,
        "created_table": created_table,
        "relation_field_names": [item[0] for item in field_created],
    }


def upsert_rows(
    token: str,
    app_token: str,
    table_id: str,
    primary_field: str,
    rows: list[dict[str, Any]],
    relation_indexes: dict[str, Any],
) -> dict[str, Any]:
    existing = {str((record.get("fields") or {}).get(primary_field) or "").strip(): record for record in list_records(token, app_token, table_id)}
    relation_payload_by_key: dict[str, dict[str, Any]] = {}
    record_id_by_key: dict[str, str] = {}
    created_rows = 0
    updated_rows = 0
    for row in rows:
        key = str(row.get(primary_field) or "").strip()
        if not key:
            raise RuntimeError(f"seed row missing primary field: {primary_field}")
        payload = normalize_seed_row(row, relation_indexes)
        scalar_payload = {
            field: value
            for field, value in payload.items()
            if field not in {"学员ID", "控制点编号", "学员ID_link", "控制点编号_link"}
        }
        relation_payload_by_key[key] = {
            "学员ID_link": payload["学员ID_link"],
            "控制点编号_link": payload["控制点编号_link"],
        }
        current = existing.get(key)
        if current:
            record_id = str(current["record_id"] or "").strip()
            if not record_id:
                raise RuntimeError(f"existing record missing record_id for primary {key}")
            update_payload = {field: value for field, value in scalar_payload.items() if field != primary_field}
            api(token, "PUT", f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}", body={"fields": update_payload})
            record_id_by_key[key] = record_id
            updated_rows += 1
        else:
            response = api(token, "POST", f"/bitable/v1/apps/{app_token}/tables/{table_id}/records", body={"fields": scalar_payload})
            record = ((response.get("data") or {}).get("record") or {})
            record_id = str(record.get("record_id") or record.get("id") or "").strip()
            if not record_id:
                records = ((response.get("data") or {}).get("records") or [])
                first = records[0] if records else {}
                record_id = str(first.get("record_id") or first.get("id") or "").strip()
            if not record_id:
                raise RuntimeError(f"failed to create record for primary {key}")
            record_id_by_key[key] = record_id
            created_rows += 1

    update_relation_payload: list[dict[str, Any]] = []
    for key, record_id in record_id_by_key.items():
        payload = relation_payload_by_key.get(key)
        if not payload:
            continue
        update_relation_payload.append({"record_id": record_id, "fields": payload})
    for chunk in chunked(update_relation_payload, DEFAULT_BATCH_SIZE):
        batch_request(token, "POST", f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_update", chunk)

    refreshed = list_records(token, app_token, table_id)
    linked_rows = 0
    for record in refreshed:
        fields = record.get("fields") or {}
        if fields.get("学员ID_link") not in (None, "", []):
            linked_rows += 1
    return {
        "seed_rows": len(rows),
        "prepared_rows": len(rows),
        "created_rows": created_rows,
        "updated_rows": updated_rows,
        "total_rows_after": len(refreshed),
        "linked_rows_after": linked_rows,
    }


def render_markdown(manifest: dict[str, Any], result: dict[str, Any]) -> str:
    table = manifest["tables"][0]
    lines = [
        f"# {manifest['meta']['task_id']}",
        "",
        f"- Table: `{table['table_name']}`",
        f"- Seed rows: `{table['seed_rows']}`",
        f"- Live table id: `{result['table_id']}`",
        f"- Created table: `{result['created_table']}`",
        f"- Linked rows after apply: `{result['upsert_result']['linked_rows_after']}`",
        "",
        "## Fields",
    ]
    for field in table["fields"]:
        lines.append(f"- `{field['name']}`: `{field['type']}`")
    lines.append("")
    lines.append("## Relation Fields")
    lines.append("- `学员ID_link` -> `T4_企业模式诊断表`")
    lines.append("- `控制点编号_link` -> `T9_32维诊断控制点`")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply TS-YL-02 diagnostic score records to Feishu.")
    parser.add_argument("--manifest", default=str(DEFAULT_EXTRACTED_MANIFEST), help="Path to the extracted manifest JSON.")
    parser.add_argument("--output-dir", help="Directory for run artifacts.")
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    parser.add_argument("--app-token", default=DEFAULT_APP_TOKEN)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    manifest = read_json(manifest_path)
    table_manifest = manifest["tables"][0]
    output_dir = Path(args.output_dir).resolve() if args.output_dir else REPO_ROOT / "artifacts" / "ai-da-guan-jia" / "runs" / datetime.now().strftime("%Y-%m-%d") / f"adagj-{datetime.now().strftime('%Y%m%d-%H%M%S')}-tsyl02"
    output_dir.mkdir(parents=True, exist_ok=True)
    normalized_manifest_path = output_dir / f"{manifest_path.stem}.normalized.json"
    normalized_md_path = output_dir / f"{manifest_path.stem}.md"
    result_path = output_dir / f"{manifest_path.stem}.apply-result.json"
    write_json(normalized_manifest_path, manifest)

    creds = load_feishu_credentials(args.account_id)
    token = fetch_tenant_access_token(creds["app_id"], creds["app_secret"])

    table = table_by_name(token, args.app_token, TARGET_TABLE_NAME)
    table_id = str((table or {}).get("table_id") or "").strip()
    table_created = False
    if not table_id:
        table_id, table_created = ensure_table(token, args.app_token, TARGET_TABLE_NAME)

    schema_result = ensure_schema(token, args.app_token, table_id)
    relation_indexes = build_relation_indexes(token, args.app_token)

    if args.dry_run:
        preview = {
            "status": "preview_ready",
            "mode": "dry-run",
            "app_token": args.app_token,
            "manifest_path": str(manifest_path),
            "normalized_manifest_path": str(normalized_manifest_path),
            "normalized_markdown_path": str(normalized_md_path),
            "table_id": table_id,
            "table_created": table_created or schema_result["created_table"],
            "seed_rows": table_manifest["seed_rows"],
            "relation_indexes": {
                key: {"table_id": value["table_id"], "primary_field": value["primary_field"], "record_count": value["record_count"]}
                for key, value in relation_indexes.items()
            },
        }
        normalized_md_path.write_text(render_markdown(manifest, {"table_id": table_id, "created_table": table_created, "upsert_result": {"linked_rows_after": 0}}), encoding="utf-8")
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return 0

    upsert_result = upsert_rows(
        token,
        args.app_token,
        table_id,
        table_manifest["primary_field"],
        list(table_manifest["seed_data"]),
        relation_indexes,
    )
    normalized_md_path.write_text(render_markdown(manifest, {"table_id": table_id, "created_table": table_created or schema_result["created_table"], "upsert_result": upsert_result}), encoding="utf-8")
    result = {
        "status": "applied",
        "mode": "apply",
        "app_token": args.app_token,
        "manifest_path": str(manifest_path),
        "normalized_manifest_path": str(normalized_manifest_path),
        "normalized_markdown_path": str(normalized_md_path),
        "table_id": table_id,
        "table_created": table_created or schema_result["created_table"],
        "relation_field_names": schema_result["relation_field_names"],
        "relation_indexes": {
            key: {"table_id": value["table_id"], "primary_field": value["primary_field"], "record_count": value["record_count"]}
            for key, value in relation_indexes.items()
        },
        "upsert_result": upsert_result,
    }
    write_json(result_path, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
