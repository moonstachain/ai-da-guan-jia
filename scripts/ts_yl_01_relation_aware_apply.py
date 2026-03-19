#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_ROOT = Path.home() / ".codex" / "skills" / "feishu-bitable-bridge"
OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"
DEFAULT_ACCOUNT_ID = "feishu-claw"

TARGET_APP_TOKEN = "IqZhbMJJxaq8D4sHOvkciaWFnid"
TARGET_BASE_LINK = "https://h52xu4gwob.feishu.cn/wiki/INApw2UoXiSeMTkBMVFc5daVnle?from=from_copylink"
TABLE_ID_MAP_FILE = REPO_ROOT / "artifacts" / "ts-yl-01" / "table_ids.json"

TEXT_FIELD = 1
NUMBER_FIELD = 2
SINGLE_SELECT_FIELD = 3
DATE_FIELD = 5

SOURCE_BUNDLE = REPO_ROOT / "artifacts" / "ai-da-guan-jia" / "runs" / "2026-03-18" / "adagj-20260318-172718-000000" / "t6-t11-propose-only-bundle.json"
RUN_DIR = SOURCE_BUNDLE.parent
RELATION_MANIFEST_FILE = RUN_DIR / "t6-t11-relation-aware-schema-manifest.json"
RELATION_MANIFEST_MD = RUN_DIR / "t6-t11-relation-aware-schema-manifest.md"
APPLY_RESULT_FILE = RUN_DIR / "t6-t11-live-apply-result.json"


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
    headers = {"Authorization": f"Bearer {token}", "User-Agent": "ts-yl-01-relation-aware-apply/1.0"}
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


def fetch_tenant_access_token(app_id: str, app_secret: str) -> str:
    import urllib.request

    payload = json.dumps({"app_id": app_id, "app_secret": app_secret}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "ts-yl-01-relation-aware-apply/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))
    if result.get("code") not in (0, "0", None):
        raise RuntimeError(str(result.get("msg") or result.get("error") or result))
    return str(result["tenant_access_token"])


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
        desc["notes"] = "Feishu live apply uses text fallback until auto-number field creation is verified."
        return desc
    if field_type.startswith("关联(") and field_type.endswith(")"):
        desc["logical_type"] = "relation_reference"
        desc["feishu_type"] = TEXT_FIELD
        desc["relation_target"] = field_type[len("关联(") : -1]
        desc["notes"] = "Relation is tracked in manifest; live apply stores a text reference fallback."
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


def target_reference(logical_table: str) -> dict[str, Any]:
    live_targets = {
        "T1_康波阶段": {"table_name": "康波阶段表", "table_id": "tbl57waor719IPFV", "status": "confirmed"},
        "T2_原子组件": {"table_name": "原子组件", "table_id": "", "status": "logical_only"},
        "T4_企业诊断": {"table_name": "企业诊断", "table_id": "", "status": "logical_only"},
    }
    if logical_table in live_targets:
        return deepcopy(live_targets[logical_table])
    return {"table_name": logical_table, "table_id": "", "status": "logical_only"}


def build_relation_manifest(bundle: dict[str, Any]) -> dict[str, Any]:
    relation_edges = {
        ("T6_12原型人格主表", "适配原子"): "T2_原子组件",
        ("T6_12原型人格主表", "最佳搭配"): "T6_12原型人格主表",
        ("T6_12原型人格主表", "冲突原型"): "T6_12原型人格主表",
        ("T7_原型组合映射表", "主原型"): "T6_12原型人格主表",
        ("T7_原型组合映射表", "辅原型"): "T6_12原型人格主表",
        ("T7_原型组合映射表", "学员案例"): "T4_企业诊断",
        ("T8_品类模板表", "康波适配"): "T1_康波阶段",
        ("T8_品类模板表", "适配原型"): "T6_12原型人格主表",
        ("T8_品类模板表", "学员案例"): "T4_企业诊断",
        ("T9_32维诊断控制点", "对应原子"): "T2_原子组件",
        ("T10_原型×康波策略", "原型ID"): "T6_12原型人格主表",
        ("T10_原型×康波策略", "康波阶段"): "T1_康波阶段",
        ("T11_进化日志schema", "学员"): "T4_企业诊断",
    }

    tables: list[dict[str, Any]] = []
    for table in bundle.get("tables") or []:
        table_name = str(table.get("name") or "").strip()
        schema = list(table.get("schema") or [])
        fields = [normalize_field_desc(field) for field in schema]
        relation_fields = []
        for field in fields:
            relation_key = (table_name, field["name"])
            if relation_key not in relation_edges:
                continue
            logical_target = relation_edges[relation_key]
            relation_target = target_reference(logical_target)
            relation_fields.append(
                {
                    "field_name": field["name"],
                    "relation_kind": "semantic_reference",
                    "target_table_name": logical_target,
                    "target_table_id": relation_target["table_id"],
                    "target_live_table_name": relation_target["table_name"],
                    "target_resolution_status": relation_target["status"],
                    "fallback_field_type": field["feishu_type"],
                }
            )
            field["relation"] = relation_fields[-1]
        tables.append(
            {
                "table_name": table_name,
                "primary_field": str(schema[0]["name"]).strip() if schema else "",
                "seed_count": len(table.get("seed_rows") or []),
                "row_count": int(table.get("row_count") or 0),
                "fields": fields,
                "relations": relation_fields,
                "table_id": "",
                "apply_status": "pending",
            }
        )

    relation_edges_payload = []
    for (source_table, field_name_), target_table in relation_edges.items():
        target_ref = target_reference(target_table)
        relation_edges_payload.append(
            {
                "source_table_name": source_table,
                "field_name": field_name_,
                "target_table_name": target_table,
                "target_live_table_name": target_ref["table_name"],
                "target_table_id": target_ref["table_id"],
                "target_resolution_status": target_ref["status"],
            }
        )

    return {
        "schema_version": "ts-yl-01-relation-aware-schema-manifest-v1",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "task_id": "TS-YL-01",
        "base_name": "康波周期总控舱",
        "base_link": TARGET_BASE_LINK,
        "app_token": TARGET_APP_TOKEN,
        "source_bundle": str(SOURCE_BUNDLE),
        "table_count": len(tables),
        "tables": tables,
        "relation_edges": relation_edges_payload,
        "notes": [
            "Live apply uses text/date/select fields that Feishu Open API already supports in this base.",
            "Relation semantics are preserved in the manifest even when the live table cannot yet express the link field type.",
            "T11_进化日志schema has no seed rows in the source bundle, so apply only creates the schema.",
        ],
    }


def manifest_markdown(manifest: dict[str, Any]) -> str:
    lines = [
        f"# {manifest['task_id']} relation-aware schema manifest",
        "",
        f"- Base: `{manifest['base_name']}`",
        f"- App token: `{manifest['app_token']}`",
        f"- Source bundle: `{manifest['source_bundle']}`",
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
                lines.append(
                    f"  - `{relation['field_name']}` -> `{relation['target_table_name']}`"
                    f" ({relation['target_resolution_status']})"
                )
        else:
            lines.append("- Relation edges: none")
        lines.append("- Fields:")
        for field in table["fields"]:
            note = f" | {field['notes']}" if field.get("notes") else ""
            relation = field.get("relation")
            relation_text = ""
            if relation:
                relation_text = f" -> {relation['target_table_name']} [{relation['target_resolution_status']}]"
            lines.append(
                f"  - `{field['name']}`: `{field['logical_type']}` / Feishu `{field['feishu_type']}`{relation_text}{note}"
            )
    return "\n".join(lines) + "\n"


def ensure_live_schema(token: str, manifest: dict[str, Any]) -> dict[str, Any]:
    table_ids: dict[str, str] = {}
    summary_tables: list[dict[str, Any]] = []
    for table in manifest["tables"]:
        table_id, created = ensure_table(token, TARGET_APP_TOKEN, table["table_name"])
        ensure_primary_field(token, TARGET_APP_TOKEN, table_id, table["primary_field"])
        for field in table["fields"][1:]:
            ensure_field(token, TARGET_APP_TOKEN, table_id, field)
        table_ids[table["table_name"]] = table_id
        summary_tables.append(
            {
                "table_name": table["table_name"],
                "table_id": table_id,
                "created": created,
                "field_count": len(list_fields(token, TARGET_APP_TOKEN, table_id)),
                "primary_field": table["primary_field"],
            }
        )
    return {"table_ids": table_ids, "tables": summary_tables}


def upsert_seed_rows(token: str, bundle: dict[str, Any], table_ids: dict[str, str]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for table in bundle.get("tables") or []:
        table_name = str(table.get("name") or "").strip()
        rows = list(table.get("seed_rows") or [])
        if not rows:
            results[table_name] = {"seed_rows": 0, "created": 0, "updated": 0}
            continue
        table_id = table_ids[table_name]
        primary_field = str(table.get("schema")[0]["name"]).strip()
        existing = existing_index(list_records(token, TARGET_APP_TOKEN, table_id), primary_field)
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
        batch_request(token, "POST", f"/bitable/v1/apps/{TARGET_APP_TOKEN}/tables/{table_id}/records/batch_create", create_payload)
        batch_request(token, "POST", f"/bitable/v1/apps/{TARGET_APP_TOKEN}/tables/{table_id}/records/batch_update", update_payload)
        results[table_name] = {
            "seed_rows": len(rows),
            "created": len(create_payload),
            "updated": len(update_payload),
        }
    return results


def counts_after_apply(token: str, table_ids: dict[str, str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table_name, table_id in table_ids.items():
        counts[table_name] = len(list_records(token, TARGET_APP_TOKEN, table_id))
    return counts


def update_canonical_artifacts(
    *,
    manifest: dict[str, Any],
    live_result: dict[str, Any],
    counts: dict[str, int],
    seed_result: dict[str, Any],
) -> None:
    evolution_path = RUN_DIR / "evolution.json"
    worklog_path = RUN_DIR / "worklog.json"
    feishu_payload_path = RUN_DIR / "feishu-payload.json"
    claude_handoff_path = RUN_DIR / "claude_handoff.json"

    if evolution_path.exists():
        evolution = read_json(evolution_path)
        evolution.update(
            {
                "closure_state": "live_apply_complete",
                "verdict": "completed",
                "enhancer_status": "live_applied",
                "feishu_sync_status": "live_applied",
                "feishu_mirror_state": "live_applied",
                "evolution_writeback_applied": True,
                "evolution_writeback_commit": "",
                "pending_human_feedback": "无",
            }
        )
        verification = evolution.get("verification_result") or {}
        if isinstance(verification, dict):
            evidence = list(verification.get("evidence") or [])
            evidence.append(
                "Feishu live apply 已完成：6 张新表创建/确认，种子写入完成，table_id 已回填。"
            )
            verification.update(
                {
                    "status": "complete",
                    "evidence": evidence,
                    "open_questions": [],
                }
            )
            evolution["verification_result"] = verification
        evolution["table_id_map"] = live_result["table_ids"]
        evolution["table_counts_after_apply"] = counts
        write_json(evolution_path, evolution)

    if worklog_path.exists():
        worklog = read_json(worklog_path)
        worklog.update(
            {
                "work_status": "已完成",
                "completion_summary": "已补成 relation-aware schema manifest，并完成 6 张表 live Feishu apply 与 table_id 回填。",
                "verification_status": "verified",
                "sync_status": "已同步",
                "feishu_sync_status": "live_applied",
                "feishu_mirror_state": "live_applied",
                "pending_human_feedback": "无",
                "follow_up_suggestions": [
                    "如果后续要把关系字段从文本引用升级为真正的关联字段，可继续补 relation remap 到 T1/T2/T4 的 live table_id。",
                    "下一轮可以直接使用 table_ids.json 和本次 manifest 作为 T6-T11 的 canonical 入口。",
                ],
            }
        )
        write_json(worklog_path, worklog)

    if feishu_payload_path.exists():
        feishu_payload = read_json(feishu_payload_path)
        feishu_payload.update(
            {
                "工作状态": "已完成",
                "完成情况": "live apply complete; relation-aware schema manifest built; table_id backfilled; seeds applied.",
                "验真状态": "complete",
                "同步状态": "已同步",
                "表ID映射": live_result["table_ids"],
                "表记录数": counts,
            }
        )
        write_json(feishu_payload_path, feishu_payload)

    if claude_handoff_path.exists():
        claude_handoff = read_json(claude_handoff_path)
        claude_handoff.update(
            {
                "verification_status": "complete",
                "feishu_sync_status": "live_applied",
                "github_sync_status": claude_handoff.get("github_sync_status", ""),
                "recommended_next_action": "如需把文本引用升级为真正关联字段，可再做一轮 relation remap。",
                "open_questions": [],
                "new_artifacts": [
                    str(RELATION_MANIFEST_FILE),
                    str(RELATION_MANIFEST_MD),
                    str(TABLE_ID_MAP_FILE),
                    str(APPLY_RESULT_FILE),
                ],
            }
        )
        write_json(claude_handoff_path, claude_handoff)


def build_summary_lines(manifest: dict[str, Any], live_result: dict[str, Any], counts: dict[str, int], seed_result: dict[str, Any]) -> str:
    lines = [
        f"- manifest: {RELATION_MANIFEST_FILE}",
        f"- table_ids: {TABLE_ID_MAP_FILE}",
        f"- apply_result: {APPLY_RESULT_FILE}",
        "",
        "## Table IDs",
    ]
    for table_name, table_id in live_result["table_ids"].items():
        lines.append(f"- {table_name}: {table_id}")
    lines.extend(["", "## Record Counts"])
    for table_name, count in counts.items():
        lines.append(f"- {table_name}: {count}")
    lines.extend(["", "## Seed Results"])
    for table_name, result in seed_result.items():
        lines.append(
            f"- {table_name}: seeds={result['seed_rows']} created={result['created']} updated={result['updated']}"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a relation-aware manifest and live-apply the TS-YL-01 Feishu tables.")
    parser.add_argument("--bundle", default=str(SOURCE_BUNDLE), help="Path to the propose-only bundle JSON.")
    parser.add_argument("--run-dir", default=str(RUN_DIR), help="Run directory for artifacts.")
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    bundle_path = Path(args.bundle).resolve()
    run_dir = Path(args.run_dir).resolve()
    bundle = read_json(bundle_path)
    manifest = build_relation_manifest(bundle)
    write_json(RELATION_MANIFEST_FILE, manifest)
    RELATION_MANIFEST_MD.write_text(manifest_markdown(manifest), encoding="utf-8")

    creds = load_feishu_credentials(args.account_id)
    token = fetch_tenant_access_token(creds["app_id"], creds["app_secret"])

    if args.dry_run:
        preview = {
            "status": "preview_ready",
            "mode": "dry-run",
            "manifest_path": str(RELATION_MANIFEST_FILE),
            "manifest_markdown_path": str(RELATION_MANIFEST_MD),
            "base_token": TARGET_APP_TOKEN,
            "tables": [
                {
                    "table_name": table["table_name"],
                    "primary_field": table["primary_field"],
                    "seed_count": table["seed_count"],
                    "field_count": len(table["fields"]),
                    "relations": table["relations"],
                }
                for table in manifest["tables"]
            ],
        }
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return 0

    live_result = ensure_live_schema(token, manifest)
    table_ids = live_result["table_ids"]
    write_json(TABLE_ID_MAP_FILE, table_ids)
    seed_result = upsert_seed_rows(token, bundle, table_ids)
    counts = counts_after_apply(token, table_ids)
    apply_result = {
        "status": "applied",
        "mode": "apply",
        "app_token": TARGET_APP_TOKEN,
        "table_ids": table_ids,
        "tables": live_result["tables"],
        "seed_result": seed_result,
        "record_counts": counts,
        "manifest_path": str(RELATION_MANIFEST_FILE),
        "manifest_markdown_path": str(RELATION_MANIFEST_MD),
    }
    write_json(APPLY_RESULT_FILE, apply_result)
    update_canonical_artifacts(manifest=manifest, live_result=live_result, counts=counts, seed_result=seed_result)
    print(json.dumps(apply_result, ensure_ascii=False, indent=2))
    print(build_summary_lines(manifest, live_result, counts, seed_result), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
