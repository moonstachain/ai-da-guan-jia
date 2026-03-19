from __future__ import annotations

import argparse
import json
import os
import re
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import parse
import xml.etree.ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.feishu_deploy import FeishuBitableAPI
from scripts.create_kangbo_signal_tables import DEFAULT_ACCOUNT_ID, load_feishu_credentials

FEISHU_BASE_LINK = "https://h52xu4gwob.feishu.cn/base/IqZhbMJJxaq8D4sHOvkciaWFnid"
WORKBOOK_PATH = Path("/tmp/files-codex2/mirror_exhaustive_mapping.xlsx")
TARGET_TABLE_NAME = "L1_历史镜像表"
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "ai-da-guan-jia" / "runs"
SHEET_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

FIELD_TYPE_TEXT = 1
FIELD_TYPE_NUMBER = 2


@dataclass
class ParsedWorkbook:
    sheet_name: str
    headers: list[str]
    rows: list[dict[str, Any]]


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def load_client(account_id: str) -> FeishuBitableAPI:
    creds = load_feishu_credentials(account_id)
    os.environ["FEISHU_APP_ID"] = creds["app_id"]
    os.environ["FEISHU_APP_SECRET"] = creds["app_secret"]
    return FeishuBitableAPI(creds["app_id"], creds["app_secret"])


def _read_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    shared_xml = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for node in shared_xml.findall("a:si", SHEET_NS):
        parts = [text.text or "" for text in node.iter(f"{MAIN_NS}t")]
        values.append("".join(parts))
    return values


def _sheet_target(zf: zipfile.ZipFile, sheet_name: str) -> str:
    workbook_xml = ET.fromstring(zf.read("xl/workbook.xml"))
    sheets = workbook_xml.find("a:sheets", SHEET_NS)
    if sheets is None:
        raise RuntimeError("workbook has no sheets")
    target_rid = ""
    for sheet in sheets.findall("a:sheet", SHEET_NS):
        if str(sheet.attrib.get("name") or "").strip() == sheet_name:
            target_rid = str(sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id") or "").strip()
            break
    if not target_rid:
        first_sheet = sheets.find("a:sheet", SHEET_NS)
        if first_sheet is None:
            raise RuntimeError(f"sheet not found: {sheet_name}")
        target_rid = str(first_sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id") or "").strip()

    rels_xml = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    for rel in rels_xml:
        if rel.attrib.get("Id") == target_rid:
            target = str(rel.attrib.get("Target") or "").strip()
            if not target.startswith("xl/"):
                target = f"xl/{target.lstrip('./')}"
            return target
    raise RuntimeError(f"sheet target not found for {sheet_name}")


def _cell_text(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    value_node = cell.find("a:v", SHEET_NS)
    if cell_type == "s" and value_node is not None:
        return shared_strings[int(value_node.text or "0")]
    if cell_type == "inlineStr":
        inline_node = cell.find("a:is", SHEET_NS)
        if inline_node is None:
          return ""
        return "".join(text.text or "" for text in inline_node.iter(f"{MAIN_NS}t"))
    if value_node is not None and value_node.text is not None:
        return value_node.text
    return ""


def parse_workbook(path: Path, sheet_name: str = "L1_历史镜像_穷尽版") -> ParsedWorkbook:
    with zipfile.ZipFile(path) as zf:
        shared_strings = _read_shared_strings(zf)
        target = _sheet_target(zf, sheet_name)
        sheet_xml = ET.fromstring(zf.read(target))

    rows: list[dict[str, str]] = []
    headers: list[str] = []
    for row_index, row in enumerate(sheet_xml.findall(".//a:row", SHEET_NS), start=1):
        values: dict[str, str] = {}
        for cell in row.findall("a:c", SHEET_NS):
            ref = str(cell.attrib.get("r") or "").strip()
            if not ref:
                continue
            values[ref] = _cell_text(cell, shared_strings)
        if row_index == 1:
            columns = sorted(
                values.keys(),
                key=lambda ref: (re.sub(r"\D", "", ref), re.sub(r"\d", "", ref)),
            )
            headers = [values[col] for col in columns]
            continue
        if not values:
            continue
        row_data: dict[str, Any] = {}
        for col_index, header in enumerate(headers, start=1):
            if not header:
                continue
            cell_ref = f"{chr(64 + col_index)}{row_index}"
            row_data[header] = values.get(cell_ref, "")
        rows.append(row_data)
    return ParsedWorkbook(sheet_name=sheet_name, headers=headers, rows=rows)


def normalize_value(field_type: int, value: Any) -> Any:
    if value is None or value == "":
        return ""
    if field_type == FIELD_TYPE_NUMBER:
        text = str(value).strip()
        if not text:
            return ""
        try:
            number = float(text)
        except ValueError:
            return text
        if number.is_integer():
            return int(number)
        return number
    return str(value)


def table_schema() -> list[dict[str, Any]]:
    return [
        {"name": "mirror_id", "type": FIELD_TYPE_TEXT},
        {"name": "source_event_id", "type": FIELD_TYPE_TEXT},
        {"name": "source_event_name", "type": FIELD_TYPE_TEXT},
        {"name": "kangbo_event_id", "type": FIELD_TYPE_TEXT},
        {"name": "kangbo_event_name", "type": FIELD_TYPE_TEXT},
        {"name": "kangbo_year", "type": FIELD_TYPE_NUMBER},
        {"name": "analogy_type", "type": FIELD_TYPE_TEXT},
        {"name": "similarity_score", "type": FIELD_TYPE_NUMBER},
        {"name": "analogy_reasoning", "type": FIELD_TYPE_TEXT},
        {"name": "key_difference", "type": FIELD_TYPE_TEXT},
        {"name": "historical_asset_impact", "type": FIELD_TYPE_TEXT},
        {"name": "linked_bw50_event_id", "type": FIELD_TYPE_TEXT},
        {"name": "status", "type": FIELD_TYPE_TEXT},
    ]


def feishu_fields() -> list[dict[str, Any]]:
    return [{"field_name": field["name"], "type": field["type"]} for field in table_schema()]


def ensure_table(api: FeishuBitableAPI, app_token: str, *, apply_changes: bool) -> dict[str, Any]:
    tables = api.list_tables(app_token)
    table = next((item for item in tables if str(item.get("name") or "").strip() == TARGET_TABLE_NAME), None)
    created = False
    if table is None:
        if not apply_changes:
            return {"table_name": TARGET_TABLE_NAME, "table_id": "", "status": "planned_create", "created": False}
        created_payload = api.create_table(app_token, TARGET_TABLE_NAME, feishu_fields())
        table_id = str(created_payload.get("table_id") or "").strip()
        if not table_id:
            raise RuntimeError(f"failed to create {TARGET_TABLE_NAME}")
        created = True
    else:
        table_id = str(table.get("table_id") or "").strip()
        if not table_id:
            raise RuntimeError(f"existing table {TARGET_TABLE_NAME} has no table_id")

    existing_fields = {str(field.get("field_name") or "").strip(): field for field in api.list_fields(app_token, table_id)}
    for field in table_schema():
        current = existing_fields.get(field["name"])
        if current is None:
            if apply_changes:
                api._request(
                    f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
                    method="POST",
                    payload={"field_name": field["name"], "type": field["type"]},
                )
            continue
        if int(current.get("type") or 0) != field["type"]:
            raise RuntimeError(
                f"Field type mismatch for {TARGET_TABLE_NAME}.{field['name']}: expected {field['type']}, got {current.get('type')}"
            )

    return {"table_name": TARGET_TABLE_NAME, "table_id": table_id, "status": "created" if created else "existing", "created": created}


def build_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    schema = {field["name"]: field["type"] for field in table_schema()}
    payloads: list[dict[str, Any]] = []
    for row in rows:
        record: dict[str, Any] = {}
        for field_name, field_type in schema.items():
            value = row.get(field_name, "")
            normalized = normalize_value(field_type, value)
            if normalized == "" or normalized == []:
                continue
            record[field_name] = normalized
        payloads.append(record)
    return payloads


def batch(items: list[dict[str, Any]], size: int = 500) -> list[list[dict[str, Any]]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def record_key(record: dict[str, Any]) -> str:
    return str((record.get("fields") or {}).get("mirror_id") or "").strip()


def upsert_records(
    api: FeishuBitableAPI,
    app_token: str,
    table_id: str,
    rows: list[dict[str, Any]],
    *,
    apply_changes: bool,
) -> dict[str, Any]:
    existing_records = api.list_records(app_token, table_id)
    existing_index = {record_key(record): record for record in existing_records if record_key(record)}
    records_to_create: list[dict[str, Any]] = []
    records_to_update: list[dict[str, Any]] = []

    for row in rows:
        mirror_id = str(row.get("mirror_id") or "").strip()
        if not mirror_id:
            continue
        payload = build_records([row])[0]
        existing = existing_index.get(mirror_id)
        if existing and existing.get("record_id"):
            records_to_update.append({"record_id": existing["record_id"], "fields": payload})
        else:
            records_to_create.append({"fields": payload})

    if apply_changes:
        for chunk in batch(records_to_create, 50):
            if chunk:
                api._request(
                    f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
                    method="POST",
                    payload={"records": chunk},
                )
        for chunk in batch(records_to_update, 50):
            if chunk:
                api._request(
                    f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_update",
                    method="POST",
                    payload={"records": chunk},
                )

    refreshed = api.list_records(app_token, table_id)
    refreshed_index = {record_key(record): record for record in refreshed if record_key(record)}
    sample_records = list(sorted(refreshed_index))[:3]
    return {
        "existing_count": len(existing_records),
        "created_count": len(records_to_create),
        "updated_count": len(records_to_update),
        "record_count": len(refreshed_index),
        "sample_records": sample_records,
    }


def run(*, apply_changes: bool, account_id: str) -> dict[str, Any]:
    workbook = parse_workbook(WORKBOOK_PATH)
    api = load_client(account_id)
    app_token = api.resolve_app_token(FEISHU_BASE_LINK)
    table_result = ensure_table(api, app_token, apply_changes=apply_changes)
    if not table_result.get("table_id"):
        return {
            "status": "preview_ready",
            "app_token": app_token,
            "table_result": table_result,
            "sheet_name": workbook.sheet_name,
            "record_count": len(workbook.rows),
            "sample_records": [row.get("mirror_id") for row in workbook.rows[:3]],
        }

    mirror_rows = workbook.rows
    write_result = upsert_records(api, app_token, str(table_result["table_id"]), mirror_rows, apply_changes=apply_changes)
    result = {
        "status": "applied" if apply_changes else "preview_ready",
        "app_token": app_token,
        "base_link": FEISHU_BASE_LINK,
        "table_id": table_result["table_id"],
        "table_name": TARGET_TABLE_NAME,
        "sheet_name": workbook.sheet_name,
        "seed_count": len(mirror_rows),
        **table_result,
        **write_result,
    }
    artifact_dir = ARTIFACT_ROOT / datetime.now().strftime("%Y-%m-%d") / f"adagj-{now_stamp()}-ts-mirror-02"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "feishu-mirror-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Write TS-MIRROR-02 history mirror rows to Feishu Bitable.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    args = parser.parse_args()

    try:
        result = run(apply_changes=bool(args.apply), account_id=args.account_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:  # pragma: no cover - preserve failure evidence
        failure_dir = ARTIFACT_ROOT / datetime.now().strftime("%Y-%m-%d") / f"adagj-{now_stamp()}-ts-mirror-02"
        failure_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "status": "failed",
            "error": str(exc),
            "workbook_path": str(WORKBOOK_PATH),
        }
        (failure_dir / "mirror_write_failure.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
