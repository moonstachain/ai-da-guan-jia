#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

REPO_ROOT = Path(__file__).resolve().parent.parent
OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"
DEFAULT_ACCOUNT_ID = "feishu-claw"
DEFAULT_APP_TOKEN = "IqZhbMJJxaq8D4sHOvkciaWFnid"

TEXT_FIELD = 1
NUMBER_FIELD = 2
SINGLE_SELECT_FIELD = 3
DATE_FIELD = 5


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_feishu_credentials(account_id: str = DEFAULT_ACCOUNT_ID) -> dict[str, str]:
    if os.getenv("FEISHU_APP_ID") and os.getenv("FEISHU_APP_SECRET"):
        return {"app_id": os.environ["FEISHU_APP_ID"], "app_secret": os.environ["FEISHU_APP_SECRET"]}

    if OPENCLAW_CONFIG.exists():
        config = json.loads(OPENCLAW_CONFIG.read_text(encoding="utf-8"))
        accounts = (((config.get("channels") or {}).get("feishu") or {}).get("accounts") or {})
        account = accounts.get(account_id) or {}
        app_id = str(account.get("appId") or "").strip()
        app_secret = str(account.get("appSecret") or "").strip()
        if app_id and app_secret:
            return {"app_id": app_id, "app_secret": app_secret}

    raise RuntimeError("Missing Feishu credentials in FEISHU_APP_ID/FEISHU_APP_SECRET and ~/.openclaw/openclaw.json")


def fetch_tenant_access_token(app_id: str, app_secret: str) -> str:
    import urllib.request

    payload = json.dumps({"app_id": app_id, "app_secret": app_secret}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "relation-aware-manifest-apply/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))
    if result.get("code") not in (0, "0", None):
        raise RuntimeError(str(result.get("msg") or result.get("error") or result))
    return str(result["tenant_access_token"])


def api(
    token: str,
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
) -> dict[str, Any]:
    import urllib.request

    url = f"https://open.feishu.cn/open-apis{path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    headers = {"Authorization": f"Bearer {token}", "User-Agent": "relation-aware-manifest-apply/1.0"}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    request = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("code") not in (0, "0", None):
        raise RuntimeError(str(payload.get("msg") or payload.get("error") or payload))
    return payload


def list_tables(token: str, app_token: str) -> list[dict[str, Any]]:
    payload = api(token, "GET", f"/bitable/v1/apps/{app_token}/tables", query={"page_size": 200})
    return list(((payload.get("data") or {}).get("items") or []))


def list_fields(token: str, app_token: str, table_id: str) -> list[dict[str, Any]]:
    payload = api(token, "GET", f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields", query={"page_size": 500})
    return list(((payload.get("data") or {}).get("items") or []))


def list_records(token: str, app_token: str, table_id: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    page_token = ""
    while True:
        query = {"page_size": 500}
        if page_token:
            query["page_token"] = page_token
        payload = api(token, "GET", f"/bitable/v1/apps/{app_token}/tables/{table_id}/records", query=query)
        data = payload.get("data") or {}
        records.extend(list(data.get("items") or []))
        if not data.get("has_more"):
            break
        page_token = str(data.get("page_token") or "").strip()
        if not page_token:
            break
    return records


def field_name(field: dict[str, Any]) -> str:
    return str(field.get("field_name") or field.get("name") or "").strip()


def normalize_property(field_type: int, property_value: Any) -> dict[str, Any] | None:
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
            options.append(cleaned)
        return {"options": options} if options else None
    return dict(property_value)


def ensure_table(token: str, app_token: str, table_name: str) -> tuple[str, bool]:
    existing = next((table for table in list_tables(token, app_token) if str(table.get("name") or "").strip() == table_name), None)
    if existing:
        return str(existing.get("table_id") or "").strip(), False
    created = api(token, "POST", f"/bitable/v1/apps/{app_token}/tables", body={"table": {"name": table_name}})
    table = (created.get("data") or {}).get("table") or {}
    table_id = str(table.get("table_id") or "").strip()
    if not table_id:
        table_id = next((table.get("table_id") for table in list_tables(token, app_token) if str(table.get("name") or "").strip() == table_name), "")
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
    prop = normalize_property(int(primary.get("type") or TEXT_FIELD), primary.get("property"))
    if prop:
        body["property"] = prop
    api(token, "PUT", f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{primary['field_id']}", body=body)


def ensure_field(token: str, app_token: str, table_id: str, spec: dict[str, Any]) -> None:
    current = {field_name(item): item for item in list_fields(token, app_token, table_id)}
    name = str(spec["name"]).strip()
    if not name or name in current:
        return
    field_type = int(spec.get("feishu_type") or spec.get("type") or TEXT_FIELD)
    body: dict[str, Any] = {"field_name": name, "type": field_type}
    prop = normalize_property(field_type, spec.get("property"))
    if prop:
        body["property"] = prop
    api(token, "POST", f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields", body=body)


def batch_request(token: str, method: str, path: str, records: list[dict[str, Any]], *, chunk_size: int = 500) -> None:
    for start in range(0, len(records), chunk_size):
        chunk = records[start : start + chunk_size]
        if not chunk:
            continue
        api(token, method, path, body={"records": chunk})


def existing_index(records: list[dict[str, Any]], primary_field: str) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for record in records:
        fields = record.get("fields") or {}
        key = fields.get(primary_field)
        if key not in (None, ""):
            index[str(key)] = record
    return index


def base_relation_note(relation_target: str, status: str) -> dict[str, Any]:
    return {"target_table_name": relation_target, "target_resolution_status": status, "mode": "logical_only"}


def normalize_field_desc(field: dict[str, Any]) -> dict[str, Any]:
    field_type = str(field.get("type") or "text").strip()
    desc: dict[str, Any] = {
        "name": str(field.get("name") or "").strip(),
        "logical_type": "text",
        "feishu_type": TEXT_FIELD,
    }
    if field_type == "text":
        return desc
    if field_type == "自动编号":
        desc["logical_type"] = "auto_number"
        desc["feishu_type"] = TEXT_FIELD
        desc["notes"] = "Live apply stores text fallback until auto-number field creation is intentionally upgraded."
        return desc
    if field_type.startswith("关联(") and field_type.endswith(")"):
        desc["logical_type"] = "relation_reference"
        desc["feishu_type"] = TEXT_FIELD
        desc["relation_target"] = field_type[len("关联(") : -1]
        desc["notes"] = "Relation is preserved in manifest; live apply stores text reference fallback."
        return desc
    if field_type == "日期":
        desc["logical_type"] = "date"
        desc["feishu_type"] = DATE_FIELD
        desc["property"] = {"date_formatter": "yyyy-MM-dd", "auto_fill": False}
        return desc
    if field_type == "单选":
        desc["logical_type"] = "single_select"
        desc["feishu_type"] = SINGLE_SELECT_FIELD
        options = [str(item).strip() for item in (field.get("options") or []) if str(item).strip()]
        desc["property"] = {"options": [{"name": item} for item in options]}
        return desc
    if field_type == "多行文本":
        desc["logical_type"] = "multiline_text"
        desc["feishu_type"] = TEXT_FIELD
        desc["notes"] = "Live apply uses text field; manifest preserves multiline intent."
        return desc
    return desc


def build_live_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    tables: list[dict[str, Any]] = []
    relation_edges_payload: list[dict[str, Any]] = []
    for table in manifest.get("tables") or []:
        table_name = str(table.get("table_name") or table.get("name") or "").strip()
        schema = list(table.get("fields") or [])
        fields = [normalize_field_desc(field) for field in schema]
        relations: list[dict[str, Any]] = []
        for edge in table.get("relation_edges") or []:
            if not isinstance(edge, dict):
                continue
            relation = {
                "field_name": str(edge.get("field") or edge.get("field_name") or "").strip(),
                "relation_kind": str(edge.get("mode") or "logical_only"),
                "target_table_name": str(edge.get("target") or edge.get("target_table_name") or "").strip(),
                "target_resolution_status": "logical_only",
                "fallback_field_type": TEXT_FIELD,
            }
            if relation["field_name"]:
                relations.append(relation)
                relation_edges_payload.append(
                    {
                        "source_table_name": table_name,
                        "field_name": relation["field_name"],
                        "target_table_name": relation["target_table_name"],
                        "target_resolution_status": relation["target_resolution_status"],
                    }
                )
        # Annotate fields with relation metadata when manifest already carries it.
        for field in fields:
            relation_target = field.get("relation", {}).get("target") if isinstance(field.get("relation"), dict) else ""
            if relation_target:
                field["relation"] = {
                    "relation_kind": "semantic_reference",
                    "target_table_name": relation_target,
                    "target_resolution_status": "logical_only",
                    "fallback_field_type": field["feishu_type"],
                }
        tables.append(
            {
                "table_name": table_name,
                "primary_field": str(table.get("primary_field") or (schema[0]["name"] if schema else "")).strip(),
                "seed_count": len(table.get("seed_data") or table.get("seed_rows") or []),
                "row_count": len(table.get("seed_data") or table.get("seed_rows") or []),
                "fields": fields,
                "relations": relations,
                "seed_data": list(table.get("seed_data") or table.get("seed_rows") or []),
                "table_id": "",
                "apply_status": "pending",
            }
        )
    return {
        "schema_version": "relation-aware-schema-manifest-v1",
        "generated_at": str((manifest.get("meta") or {}).get("generated_at") or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")),
        "task_id": str((manifest.get("meta") or {}).get("task_id") or manifest.get("task_id") or "unknown"),
        "base_name": str((manifest.get("meta") or {}).get("base_name") or manifest.get("base_name") or "康波周期总控舱"),
        "base_link": str((manifest.get("meta") or {}).get("base_link") or manifest.get("base_link") or ""),
        "app_token": str((manifest.get("meta") or {}).get("base_app_token") or manifest.get("app_token") or DEFAULT_APP_TOKEN),
        "tables": tables,
        "relation_edges": relation_edges_payload,
        "notes": [
            "Live apply uses text/date/select fields supported by the current Feishu base.",
            "Relation semantics are preserved in the manifest even when the live table stores text fallbacks.",
        ],
    }


def manifest_markdown(manifest: dict[str, Any]) -> str:
    lines = [
        f"# {manifest['task_id']} relation-aware schema manifest",
        "",
        f"- Base: `{manifest['base_name']}`",
        f"- App token: `{manifest['app_token']}`",
        f"- Generated at: `{manifest['generated_at']}`",
        "",
        "## Tables",
    ]
    for table in manifest["tables"]:
        lines.extend(
            [
                "",
                f"### {table['table_name']}",
                f"- Primary field: `{table['primary_field']}`",
                f"- Rows: `{table['row_count']}`",
                f"- Seed rows: `{table['seed_count']}`",
            ]
        )
        if table["relations"]:
            lines.append("- Relation edges:")
            for relation in table["relations"]:
                lines.append(f"  - `{relation['field_name']}` -> `{relation['target_table_name']}` ({relation['target_resolution_status']})")
        else:
            lines.append("- Relation edges: none")
        lines.append("- Fields:")
        for field in table["fields"]:
            relation = field.get("relation")
            relation_text = ""
            if relation:
                relation_text = f" -> {relation['target_table_name']} [{relation['target_resolution_status']}]"
            note = f" | {field['notes']}" if field.get("notes") else ""
            lines.append(f"  - `{field['name']}`: `{field['logical_type']}` / Feishu `{field['feishu_type']}`{relation_text}{note}")
    return "\n".join(lines) + "\n"


def ensure_live_schema(token: str, app_token: str, manifest: dict[str, Any]) -> dict[str, Any]:
    table_ids: dict[str, str] = {}
    summary_tables: list[dict[str, Any]] = []
    for table in manifest["tables"]:
        table_id, created = ensure_table(token, app_token, table["table_name"])
        ensure_primary_field(token, app_token, table_id, table["primary_field"])
        for field in table["fields"][1:]:
            ensure_field(token, app_token, table_id, field)
        table_ids[table["table_name"]] = table_id
        summary_tables.append(
            {
                "table_name": table["table_name"],
                "table_id": table_id,
                "created": created,
                "field_count": len(list_fields(token, app_token, table_id)),
                "primary_field": table["primary_field"],
            }
        )
    return {"table_ids": table_ids, "tables": summary_tables}


def upsert_seed_rows(token: str, app_token: str, manifest: dict[str, Any], table_ids: dict[str, str]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for table in manifest["tables"]:
        table_name = table["table_name"]
        rows = list(table.get("seed_data") or [])
        if not rows:
            results[table_name] = {"seed_rows": 0, "created": 0, "updated": 0}
            continue
        table_id = table_ids[table_name]
        primary_field = table["primary_field"]
        existing = existing_index(list_records(token, app_token, table_id), primary_field)
        create_payload: list[dict[str, Any]] = []
        update_payload: list[dict[str, Any]] = []
        for row in rows:
            key = str(row.get(primary_field) or "").strip()
            if not key:
                raise RuntimeError(f"seed row missing primary field {primary_field} for {table_name}")
            current = existing.get(key)
            if current:
                update_payload.append({"record_id": current["record_id"], "fields": row})
            else:
                create_payload.append({"fields": row})
        batch_request(token, "POST", f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create", create_payload)
        batch_request(token, "POST", f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_update", update_payload)
        results[table_name] = {"seed_rows": len(rows), "created": len(create_payload), "updated": len(update_payload)}
    return results


def counts_after_apply(token: str, app_token: str, table_ids: dict[str, str]) -> dict[str, int]:
    return {table_name: len(list_records(token, app_token, table_id)) for table_name, table_id in table_ids.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a relation-aware Feishu schema manifest with seed rows.")
    parser.add_argument("--manifest", required=True, help="Path to the relation-aware schema manifest JSON.")
    parser.add_argument("--output-dir", help="Directory to write normalized manifest and result artifacts.")
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    parser.add_argument("--app-token", default=DEFAULT_APP_TOKEN)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    manifest = read_json(manifest_path)
    live_manifest = build_live_manifest(manifest)

    output_dir = Path(args.output_dir).resolve() if args.output_dir else manifest_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    normalized_manifest_path = output_dir / f"{manifest_path.stem}.normalized.json"
    normalized_md_path = output_dir / f"{manifest_path.stem}.md"
    result_path = output_dir / f"{manifest_path.stem}.apply-result.json"
    write_json(normalized_manifest_path, live_manifest)
    normalized_md_path.write_text(manifest_markdown(live_manifest), encoding="utf-8")

    creds = load_feishu_credentials(args.account_id)
    token = fetch_tenant_access_token(creds["app_id"], creds["app_secret"])

    if args.dry_run:
        preview = {
            "status": "preview_ready",
            "mode": "dry-run",
            "app_token": args.app_token,
            "manifest_path": str(manifest_path),
            "normalized_manifest_path": str(normalized_manifest_path),
            "normalized_markdown_path": str(normalized_md_path),
            "tables": [
                {
                    "table_name": table["table_name"],
                    "primary_field": table["primary_field"],
                    "seed_count": table["seed_count"],
                    "field_count": len(table["fields"]),
                    "relations": table["relations"],
                }
                for table in live_manifest["tables"]
            ],
        }
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return 0

    live_result = ensure_live_schema(token, args.app_token, live_manifest)
    table_ids = live_result["table_ids"]
    seed_result = upsert_seed_rows(token, args.app_token, live_manifest, table_ids)
    counts = counts_after_apply(token, args.app_token, table_ids)
    apply_result = {
        "status": "applied",
        "mode": "apply",
        "app_token": args.app_token,
        "table_ids": table_ids,
        "tables": live_result["tables"],
        "seed_result": seed_result,
        "record_counts": counts,
        "manifest_path": str(manifest_path),
        "normalized_manifest_path": str(normalized_manifest_path),
        "normalized_markdown_path": str(normalized_md_path),
    }
    write_json(result_path, apply_result)
    print(json.dumps(apply_result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
