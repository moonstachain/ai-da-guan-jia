#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlencode

REPO_ROOT = Path(__file__).resolve().parent.parent
OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"
DEFAULT_ACCOUNT_ID = "feishu-claw"
DEFAULT_APP_TOKEN = "IqZhbMJJxaq8D4sHOvkciaWFnid"

TEXT_FIELD = 1
RELATION_FIELD = 21

K_CODE_RE = re.compile(r"\bK\d+\b")
AT_CODE_RE = re.compile(r"\bAT-\d+\b")
AC_CODE_RE = re.compile(r"\bAC-\d+\b")
DX_CODE_RE = re.compile(r"\bDX-\d+\b")
WV_CODE_RE = re.compile(r"\bWV-\d+\b")
ATOM_CODE_RE = re.compile(r"\b(?:FL|BL|VL)-[A-Z]{2}-\d{2}\b")
ATOM_RANGE_RE = re.compile(r"\b((?:FL|BL|VL)-[A-Z]{2}-)(\d{2})~(\d{2})\b")


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
        headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "relation-remap-apply/1.0"},
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
    headers = {"Authorization": f"Bearer {token}", "User-Agent": "relation-remap-apply/1.0"}
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


def primary_field_name(fields: list[dict[str, Any]]) -> str:
    primary = next((field for field in fields if field.get("is_primary")), None)
    if not primary:
        raise RuntimeError("table has no primary field")
    return field_name(primary)


def sanitize_field_name(name: str) -> str:
    cleaned = re.sub(r"\s+", "", name)
    cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "field"


def normalize_property(field_type: int, property_value: Any) -> dict[str, Any] | None:
    if not isinstance(property_value, dict) or not property_value:
        return None
    if field_type == RELATION_FIELD:
        return dict(property_value)
    return dict(property_value)


def ensure_relation_field(
    token: str,
    app_token: str,
    source_table_id: str,
    source_field: str,
    *,
    target_table_id: str,
    back_field_name: str,
    multiple: bool = True,
) -> dict[str, Any]:
    link_field_name = f"{source_field}_link"
    current = {field_name(item): item for item in list_fields(token, app_token, source_table_id)}
    if link_field_name in current:
        return current[link_field_name]
    body = {
        "field_name": link_field_name,
        "type": RELATION_FIELD,
        "property": {
            "table_id": target_table_id,
            "multiple": bool(multiple),
            "back_field_name": back_field_name,
        },
    }
    created = api(token, "POST", f"/bitable/v1/apps/{app_token}/tables/{source_table_id}/fields", body=body)
    field = ((created.get("data") or {}).get("field") or {})
    if not field:
        refreshed = {field_name(item): item for item in list_fields(token, app_token, source_table_id)}
        field = refreshed.get(link_field_name) or {}
    if not field:
        raise RuntimeError(f"failed to create relation field {link_field_name} on {source_table_id}")
    return field


def batch_request(
    token: str,
    method: str,
    path: str,
    records: list[dict[str, Any]],
    *,
    chunk_size: int = 500,
) -> None:
    for start in range(0, len(records), chunk_size):
        chunk = records[start : start + chunk_size]
        if not chunk:
            continue
        api(token, method, path, body={"records": chunk})


def batch_request_resilient(
    token: str,
    method: str,
    path: str,
    records: list[dict[str, Any]],
    *,
    chunk_size: int = 500,
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []

    def _apply(chunk: list[dict[str, Any]]) -> None:
        if not chunk:
            return
        try:
            api(token, method, path, body={"records": chunk})
        except Exception as exc:  # pragma: no cover - network/platform guarded
            if len(chunk) == 1:
                failures.append({"record_id": chunk[0].get("record_id"), "error": str(exc), "fields": chunk[0].get("fields")})
                return
            mid = max(1, len(chunk) // 2)
            _apply(chunk[:mid])
            _apply(chunk[mid:])

    for start in range(0, len(records), chunk_size):
        _apply(records[start : start + chunk_size])
    return failures


def existing_index(records: list[dict[str, Any]], primary_field: str) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for record in records:
        fields = record.get("fields") or {}
        key = fields.get(primary_field)
        if key not in (None, ""):
            index[str(key)] = record
    return index


def record_id_index(records: list[dict[str, Any]], key_field: str) -> dict[str, str]:
    index: dict[str, str] = {}
    for record in records:
        fields = record.get("fields") or {}
        key = str(fields.get(key_field) or "").strip()
        record_id = str(record.get("record_id") or "").strip()
        if key and record_id:
            index[key] = record_id
    return index


def build_t6_name_index(records: list[dict[str, Any]]) -> tuple[dict[str, str], dict[str, str], list[str]]:
    by_id: dict[str, str] = {}
    by_name: dict[str, str] = {}
    names: list[str] = []
    for record in records:
        fields = record.get("fields") or {}
        rid = str(record.get("record_id") or "").strip()
        proto_id = str(fields.get("原型ID") or "").strip()
        proto_name = str(fields.get("原型名称") or "").strip()
        if rid and proto_id:
            by_id[proto_id] = rid
        if rid and proto_name:
            by_name[proto_name] = rid
            names.append(proto_name)
    names = sorted(set(names), key=len, reverse=True)
    return by_id, by_name, names


def build_t1_k_index(records: list[dict[str, Any]]) -> dict[str, str]:
    non_empty = [record for record in records if str((record.get("fields") or {}).get("KB02") or "").strip()]
    mapping: dict[str, str] = {}
    for idx, record in enumerate(non_empty, start=1):
        mapping[f"K{idx}"] = str(record.get("record_id") or "").strip()
    return mapping


def parse_code_tokens(value: Any, pattern: re.Pattern[str]) -> list[str]:
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    return list(dict.fromkeys(pattern.findall(text)))


def expand_atom_codes(text: str) -> list[str]:
    if not text or text in {"(壁垒层)", "(原型层，无直接原子对应)"}:
        return []
    tokens: list[str] = []
    for raw in re.split(r"[,+，、;；\s]+", text):
        token = raw.strip()
        if not token:
            continue
        match = ATOM_RANGE_RE.search(token)
        if match:
            prefix, start, end = match.groups()
            for number in range(int(start), int(end) + 1):
                tokens.append(f"{prefix}{number:0{len(start)}d}")
            continue
        atom = ATOM_CODE_RE.search(token)
        if atom:
            tokens.append(atom.group(0))
    return list(dict.fromkeys(tokens))


def parse_k_codes(text: Any) -> list[str]:
    if text is None:
        return []
    return list(dict.fromkeys(K_CODE_RE.findall(str(text))))


def parse_name_tokens(text: Any, known_names: list[str]) -> list[str]:
    if text is None:
        return []
    s = str(text).strip()
    if not s:
        return []
    if "所有原型" in s:
        return list(known_names)
    normalized = s
    normalized = normalized.replace("：", "+").replace(":", "+")
    normalized = normalized.replace("；", "+").replace(";", "+")
    normalized = normalized.replace("、", "+").replace(",", "+").replace("，", "+")
    normalized = normalized.replace("/", "+").replace("｜", "+").replace("|", "+")
    normalized = normalized.replace("(", "+").replace(")", "+")
    matches: list[str] = []
    for name in known_names:
        if name and name in normalized:
            matches.append(name)
    return list(dict.fromkeys(matches))


def link_values_for_edge(
    edge: dict[str, Any],
    source_value: Any,
    *,
    target_indexes: dict[str, Any],
) -> list[str]:
    target_table = str(edge["target_table"])
    source_field = str(edge["source_field"])
    source_table = str(edge["source_table"])

    if target_table == "T1_康波阶段表":
        k_codes = parse_k_codes(source_value)
        return [target_indexes["t1_k_map"][code] for code in k_codes if code in target_indexes["t1_k_map"]]

    if target_table == "T2_58原子组件主表":
        if source_table == "T9_32维诊断控制点":
            codes = expand_atom_codes(str(source_value or ""))
            return [target_indexes["t2_by_id"][code] for code in codes if code in target_indexes["t2_by_id"]]
        codes = parse_code_tokens(source_value, ATOM_CODE_RE)
        return [target_indexes["t2_by_id"][code] for code in codes if code in target_indexes["t2_by_id"]]

    if target_table == "T4_企业模式诊断表":
        codes = parse_code_tokens(source_value, DX_CODE_RE)
        return [target_indexes["t4_by_id"][code] for code in codes if code in target_indexes["t4_by_id"]]

    if target_table == "T6_12原型人格主表":
        if str(edge.get("precision") or "") == "descriptive":
            names = parse_name_tokens(source_value, target_indexes["t6_names"])
            return [target_indexes["t6_by_name"][name] for name in names if name in target_indexes["t6_by_name"]]
        codes = parse_code_tokens(source_value, AT_CODE_RE)
        return [target_indexes["t6_by_id"][code] for code in codes if code in target_indexes["t6_by_id"]]

    if target_table == "T7_原型组合映射表":
        codes = parse_code_tokens(source_value, AC_CODE_RE)
        return [target_indexes["t7_by_id"][code] for code in codes if code in target_indexes["t7_by_id"]]

    if target_table == "T12_财富三观认知表":
        codes = parse_code_tokens(source_value, WV_CODE_RE)
        return [target_indexes["t12_by_id"][code] for code in codes if code in target_indexes["t12_by_id"]]

    if target_table == "T14_个人资产配置诊断":
        codes = parse_code_tokens(source_value, DX_CODE_RE)
        return [target_indexes["t14_by_id"][code] for code in codes if code in target_indexes["t14_by_id"]]

    return []


def should_use_name_matching(edge: dict[str, Any]) -> bool:
    return str(edge.get("precision") or "") == "descriptive"


def source_field_link_name(edge: dict[str, Any]) -> str:
    return f"{str(edge['source_field']).strip()}_link"


def back_field_name(edge: dict[str, Any]) -> str:
    source_table_code = str(edge["source_table"]).split("_", 1)[0]
    return sanitize_field_name(f"{source_table_code}_{edge['source_field']}_back")


def normalize_edge(edge: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_table": str(edge["source_table"]),
        "source_table_id": str(edge["source_table_id"]),
        "source_field": str(edge["source_field"]),
        "target_table": str(edge["target_table"]),
        "target_table_id": str(edge["target_table_id"]),
        "batch": int(edge.get("batch") or 0),
        "precision": str(edge.get("precision") or ""),
        "match_note": str(edge.get("match_note") or ""),
        "action": str(edge.get("action") or ""),
        "link_field_name": source_field_link_name(edge),
        "back_field_name": back_field_name(edge),
    }


def build_live_manifest(manifest: dict[str, Any], selected_batch: int | None) -> dict[str, Any]:
    edges = [normalize_edge(edge) for edge in manifest.get("edges") or []]
    if selected_batch in (1, 2):
        edges = [edge for edge in edges if edge["batch"] == selected_batch]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        grouped[edge["source_table"]].append(edge)
    return {
        "schema_version": "relation-remap-manifest-v1",
        "generated_at": str((manifest.get("meta") or {}).get("generated_at") or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")),
        "task_id": str((manifest.get("meta") or {}).get("task_id") or manifest.get("task_id") or "unknown"),
        "base_name": str((manifest.get("meta") or {}).get("base_name") or manifest.get("base_name") or "康波周期总控舱"),
        "app_token": str((manifest.get("meta") or {}).get("base_app_token") or manifest.get("app_token") or DEFAULT_APP_TOKEN),
        "selected_batch": selected_batch or "all",
        "edges": edges,
        "tables": grouped,
        "notes": [
            "Every relation field is added as a separate *_link column so the original text columns stay intact.",
            "Bidirectional Feishu relation fields are created with type 21 and a unique back field name.",
        ],
    }


def manifest_markdown(manifest: dict[str, Any]) -> str:
    lines = [
        f"# {manifest['task_id']} relation remap manifest",
        "",
        f"- Base: `{manifest['base_name']}`",
        f"- App token: `{manifest['app_token']}`",
        f"- Generated at: `{manifest['generated_at']}`",
        f"- Selected batch: `{manifest['selected_batch']}`",
        "",
        "## Edges",
    ]
    for edge in manifest["edges"]:
        lines.extend(
            [
                "",
                f"### {edge['source_table']} -> {edge['target_table']}",
                f"- Source field: `{edge['source_field']}`",
                f"- Link field: `{edge['link_field_name']}`",
                f"- Back field: `{edge['back_field_name']}`",
                f"- Batch: `{edge['batch']}`",
                f"- Precision: `{edge['precision']}`",
                f"- Match note: {edge['match_note']}",
            ]
        )
    return "\n".join(lines) + "\n"


def prepare_target_indexes(token: str, app_token: str, manifest: dict[str, Any]) -> dict[str, Any]:
    indexes: dict[str, Any] = {}
    needed_tables = {edge["target_table_id"] for edge in manifest["edges"]}
    table_map = {str(table.get("table_id") or ""): table for table in list_tables(token, app_token)}
    table_name_by_id: dict[str, str] = {}
    for edge in manifest["edges"]:
        table_name_by_id.setdefault(edge["target_table_id"], edge["target_table"])
    for table_id in needed_tables:
        table = table_map.get(table_id)
        if not table:
            raise RuntimeError(f"target table missing from base: {table_id}")
        records = list_records(token, app_token, table_id)
        fields = list_fields(token, app_token, table_id)
        primary_name = primary_field_name(fields)
        table_name = table_name_by_id.get(table_id, str(table.get("name") or "").strip())
        indexes[table_name] = {
            "records": records,
            "fields": fields,
            "primary": primary_name,
        }

    t6_records = indexes["T6_12原型人格主表"]["records"]
    t6_by_id, t6_by_name, t6_names = build_t6_name_index(t6_records)
    t1_records = indexes["T1_康波阶段表"]["records"]
    indexes.update(
        {
            "t6_by_id": t6_by_id,
            "t6_by_name": t6_by_name,
            "t6_names": t6_names,
            "t1_k_map": build_t1_k_index(t1_records),
        }
    )
    if "T4_企业模式诊断表" in indexes:
        indexes["t4_by_id"] = record_id_index(indexes["T4_企业模式诊断表"]["records"], "诊断ID")
    if "T7_原型组合映射表" in indexes:
        indexes["t7_by_id"] = record_id_index(indexes["T7_原型组合映射表"]["records"], "组合ID")
    if "T12_财富三观认知表" in indexes:
        indexes["t12_by_id"] = record_id_index(indexes["T12_财富三观认知表"]["records"], "命题ID")
    if "T2_58原子组件主表" in indexes:
        indexes["t2_by_id"] = record_id_index(indexes["T2_58原子组件主表"]["records"], "原子ID")
    return indexes


def ensure_tables_and_fields(token: str, app_token: str, manifest: dict[str, Any]) -> dict[str, Any]:
    summary: list[dict[str, Any]] = []
    table_field_cache: dict[str, list[dict[str, Any]]] = {}
    for edge in manifest["edges"]:
        source_table_id = edge["source_table_id"]
        source_table_name = edge["source_table"]
        if source_table_id not in table_field_cache:
            table_field_cache[source_table_id] = list_fields(token, app_token, source_table_id)
        source_fields = table_field_cache[source_table_id]
        target_table_id = edge["target_table_id"]
        link_field_name = edge["link_field_name"]
        back_name = edge["back_field_name"]
        existing_names = {field_name(item) for item in source_fields}
        created = False
        if link_field_name not in existing_names:
            ensure_relation_field(
                token,
                app_token,
                source_table_id,
                edge["source_field"],
                target_table_id=target_table_id,
                back_field_name=back_name,
                multiple=True,
            )
            created = True
            table_field_cache[source_table_id] = list_fields(token, app_token, source_table_id)
        summary.append(
            {
                "source_table": source_table_name,
                "source_table_id": source_table_id,
                "source_field": edge["source_field"],
                "link_field_name": link_field_name,
                "back_field_name": back_name,
                "target_table": edge["target_table"],
                "target_table_id": target_table_id,
                "created": created,
            }
        )
    return {"field_summary": summary}


def upsert_edge_relations(token: str, app_token: str, edge: dict[str, Any], target_indexes: dict[str, Any]) -> dict[str, Any]:
    source_table_id = edge["source_table_id"]
    link_field_name = edge["link_field_name"]
    source_table_name = edge["source_table"]
    primary_name = primary_field_name(list_fields(token, app_token, source_table_id))
    source_records = list_records(token, app_token, source_table_id)

    updates: list[dict[str, Any]] = []
    skipped = 0
    for record in source_records:
        fields = record.get("fields") or {}
        value = fields.get(edge["source_field"])
        links = link_values_for_edge(edge, value, target_indexes=target_indexes)
        if not links:
            skipped += 1
            continue
        updates.append({"record_id": record["record_id"], "fields": {link_field_name: links}})

    record_failures: list[dict[str, Any]] = []
    for chunk_start in range(0, len(updates), 500):
        chunk = updates[chunk_start : chunk_start + 500]
        try:
            api(token, "POST", f"/bitable/v1/apps/{app_token}/tables/{source_table_id}/records/batch_update", body={"records": chunk})
        except Exception:
            record_failures.extend(
                batch_request_resilient(
                    token,
                    "POST",
                    f"/bitable/v1/apps/{app_token}/tables/{source_table_id}/records/batch_update",
                    chunk,
                )
            )

    # Re-read the table to count records with the new link field populated.
    refreshed = list_records(token, app_token, source_table_id)
    linked = 0
    for record in refreshed:
        value = (record.get("fields") or {}).get(link_field_name)
        if value not in (None, "", []):
            linked += 1

    return {
        "source_table": source_table_name,
        "source_table_id": source_table_id,
        "source_field": edge["source_field"],
        "link_field_name": link_field_name,
        "primary_field": primary_name,
        "source_rows": len(source_records),
        "linked_rows": linked,
        "skipped_rows": skipped,
        "would_update_rows": len(updates),
        "failed_rows": len(record_failures),
        "failures": record_failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a relation-remap Feishu manifest with link fields and seed migration.")
    parser.add_argument("--manifest", required=True, help="Path to the relation-remap manifest JSON.")
    parser.add_argument("--output-dir", help="Directory to write normalized manifest and result artifacts.")
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    parser.add_argument("--app-token", default=DEFAULT_APP_TOKEN)
    parser.add_argument("--batch", choices=["1", "2", "all"], default="all")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    manifest = read_json(manifest_path)
    selected_batch = None if args.batch == "all" else int(args.batch)
    live_manifest = build_live_manifest(manifest, selected_batch)

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
            "selected_batch": live_manifest["selected_batch"],
            "edge_count": len(live_manifest["edges"]),
            "tables": {
                table_name: [
                    {
                        "source_field": edge["source_field"],
                        "link_field_name": edge["link_field_name"],
                        "target_table": edge["target_table"],
                        "precision": edge["precision"],
                        "batch": edge["batch"],
                    }
                    for edge in edges
                ]
                for table_name, edges in live_manifest["tables"].items()
            },
        }
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return 0

    target_indexes = prepare_target_indexes(token, args.app_token, live_manifest)
    field_summary = ensure_tables_and_fields(token, args.app_token, live_manifest)

    edge_results: list[dict[str, Any]] = []
    for edge in live_manifest["edges"]:
        try:
            edge_results.append(upsert_edge_relations(token, args.app_token, edge, target_indexes))
        except Exception as exc:  # pragma: no cover - network/platform guarded
            edge_results.append(
                {
                    "source_table": edge["source_table"],
                    "source_table_id": edge["source_table_id"],
                    "source_field": edge["source_field"],
                    "link_field_name": edge["link_field_name"],
                    "target_table": edge["target_table"],
                    "target_table_id": edge["target_table_id"],
                    "error": str(exc),
                }
            )

    apply_result = {
        "status": "applied",
        "mode": "apply",
        "app_token": args.app_token,
        "selected_batch": live_manifest["selected_batch"],
        "manifest_path": str(manifest_path),
        "normalized_manifest_path": str(normalized_manifest_path),
        "normalized_markdown_path": str(normalized_md_path),
        "field_summary": field_summary["field_summary"],
        "edge_results": edge_results,
    }
    write_json(result_path, apply_result)
    print(json.dumps(apply_result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
