from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))

from dashboard.feishu_deploy import FeishuBitableAPI, normalize_record
from scripts.create_kangbo_signal_tables import DEFAULT_ACCOUNT_ID, load_feishu_credentials

APP_TOKEN = "IqZhbMJJxaq8D4sHOvkciaWFnid"
BASE_LINK = f"https://h52xu4gwob.feishu.cn/base/{APP_TOKEN}"
DOCX_PATH = Path("/tmp/ts-kb-07-files/TS-KB-07_十五五政策信号层_TaskSpec_v1.docx")
XLSX_PATH = Path("/tmp/ts-kb-07-files/L5_十五五政策信号智库_schema_v2.xlsx")

ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "ai-da-guan-jia" / "runs"

TEXT_FIELD = 1
NUMBER_FIELD = 2
SINGLE_SELECT_FIELD = 3
MULTI_SELECT_FIELD = 4
URL_FIELD = 15
CHECKBOX_FIELD = 7


@dataclass(frozen=True)
class SheetPayload:
    table_name: str
    fields: list[dict[str, Any]]
    records: list[dict[str, Any]]


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def load_feishu_client(account_id: str) -> FeishuBitableAPI:
    creds = load_feishu_credentials(account_id)
    os.environ["FEISHU_APP_ID"] = creds["app_id"]
    os.environ["FEISHU_APP_SECRET"] = creds["app_secret"]
    return FeishuBitableAPI(creds["app_id"], creds["app_secret"])


def _read_shared_strings(zf: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    values: list[str] = []
    for si in root.findall("a:si", ns):
        values.append("".join(t.text or "" for t in si.findall(".//a:t", ns)))
    return values


def _cell_value(cell: ET.Element, shared: list[str], ns: dict[str, str]) -> str:
    t = cell.attrib.get("t")
    if t == "inlineStr":
        return "".join(t.text or "" for t in cell.findall(".//a:is//a:t", ns))
    if t == "s":
        value = cell.find("a:v", ns)
        if value is None or not (value.text or "").strip():
            return ""
        return shared[int(value.text)]
    if t == "b":
        value = cell.find("a:v", ns)
        return "TRUE" if value is not None and value.text == "1" else "FALSE"
    value = cell.find("a:v", ns)
    if value is not None and value.text is not None:
        return value.text
    return "".join(t.text or "" for t in cell.findall(".//a:t", ns))


def read_xlsx_table(path: Path, sheet_name: str) -> list[dict[str, Any]]:
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    with ZipFile(path) as zf:
        shared = _read_shared_strings(zf)
        workbook = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        relmap = {rel.attrib["Id"]: rel.attrib["Target"].lstrip("/") for rel in rels}
        target = None
        for sheet in workbook.findall("a:sheets/a:sheet", ns):
            if sheet.attrib.get("name") == sheet_name:
                rel_id = sheet.attrib[f"{{{ns['r']}}}id"]
                target = relmap[rel_id]
                break
        if not target:
            raise RuntimeError(f"Missing sheet {sheet_name}")
        sheet_root = ET.fromstring(zf.read(target))
        rows: list[list[str]] = []
        for row in sheet_root.findall(".//a:sheetData/a:row", ns):
            vals: list[str] = []
            for cell in row.findall("a:c", ns):
                vals.append(_cell_value(cell, shared, ns))
            rows.append(vals)
    if not rows:
        return []
    headers = rows[0]
    records: list[dict[str, Any]] = []
    for raw_row in rows[1:]:
        row = {headers[i]: raw_row[i] if i < len(raw_row) else "" for i in range(len(headers))}
        records.append(row)
    return records


def read_sheet_payloads() -> dict[str, SheetPayload]:
    l0_rows = read_xlsx_table(XLSX_PATH, "L0_五次五年规划宏观对比")
    annual_rows = read_xlsx_table(XLSX_PATH, "L5_政策信号年度对比")
    asset_rows = read_xlsx_table(XLSX_PATH, "L5_政策资产映射")
    matrix_rows = read_xlsx_table(XLSX_PATH, "L5_六年信号矩阵")

    return {
        "L0_五次五年规划宏观对比": SheetPayload(
            table_name="L0_五次五年规划宏观对比",
            fields=[
                {"name": "dimension", "type": "text"},
                {"name": "fyp_11", "type": "text"},
                {"name": "fyp_12", "type": "text"},
                {"name": "fyp_13", "type": "text"},
                {"name": "fyp_14", "type": "text"},
                {"name": "fyp_15", "type": "text"},
                {"name": "trend_25yr", "type": "text"},
                {"name": "investment_implication", "type": "text"},
                {"name": "kangbo_cross", "type": "text"},
            ],
            records=l0_rows,
        ),
        "L5_政策信号年度对比": SheetPayload(
            table_name="L5_政策信号年度对比",
            fields=[
                {"name": "signal_id", "type": "text"},
                {"name": "year", "type": "number"},
                {"name": "five_year_plan", "type": "text"},
                {"name": "signal_layer", "type": "single_select", "options": sorted(_unique_nonempty(annual_rows, "signal_layer"))},
                {"name": "dimension", "type": "single_select", "options": sorted(_unique_nonempty(annual_rows, "dimension"))},
                {"name": "indicator", "type": "text"},
                {"name": "value_text", "type": "text"},
                {"name": "value_numeric", "type": "number"},
                {"name": "yoy_change", "type": "text"},
                {"name": "direction", "type": "text"},
                {"name": "source_section", "type": "text"},
                {"name": "original_wording", "type": "text"},
                {"name": "significance", "type": "text"},
                {"name": "investment_implication", "type": "text"},
                {"name": "related_asset_class", "type": "text"},
                {"name": "confidence", "type": "single_select", "options": sorted(_unique_nonempty(annual_rows, "confidence"))},
                {"name": "source_url", "type": "url"},
            ],
            records=annual_rows,
        ),
        "L5_政策资产映射": SheetPayload(
            table_name="L5_政策资产映射",
            fields=[
                {"name": "mapping_id", "type": "text"},
                {"name": "policy_signal_id", "type": "text"},
                {"name": "asset_class", "type": "text"},
                {"name": "sub_sector", "type": "text"},
                {"name": "specific_target", "type": "text"},
                {"name": "signal_direction", "type": "single_select", "options": sorted(_unique_nonempty(asset_rows, "signal_direction"))},
                {"name": "policy_driver", "type": "text"},
                {"name": "roe_range", "type": "text"},
                {"name": "competition_level", "type": "text"},
                {"name": "market_size", "type": "text"},
                {"name": "kangbo_cross_ref", "type": "text"},
                {"name": "investment_thesis", "type": "text"},
                {"name": "risk_warning", "type": "text"},
                {"name": "time_horizon", "type": "text"},
                {"name": "priority", "type": "single_select", "options": sorted(_unique_nonempty(asset_rows, "priority"))},
            ],
            records=asset_rows,
        ),
        "L5_六年信号矩阵": SheetPayload(
            table_name="L5_六年信号矩阵",
            fields=[
                {"name": "indicator", "type": "text"},
                {"name": "y2021", "type": "text"},
                {"name": "y2022", "type": "text"},
                {"name": "y2023", "type": "text"},
                {"name": "y2024", "type": "text"},
                {"name": "y2025", "type": "text"},
                {"name": "y2026", "type": "text"},
                {"name": "trend", "type": "text"},
                {"name": "investment_signal", "type": "text"},
            ],
            records=matrix_rows,
        ),
    }


def _unique_nonempty(rows: list[dict[str, Any]], key: str) -> list[str]:
    values = []
    seen = set()
    for row in rows:
        value = str(row.get(key) or "").strip()
        if value and value not in seen:
            seen.add(value)
            values.append(value)
    return values


def to_link_object(url: str) -> dict[str, str] | None:
    value = str(url or "").strip()
    if not value:
        return None
    return {"link": value, "text": value}


def field_type_payload(field: dict[str, Any]) -> dict[str, Any]:
    field_type = {
        "text": TEXT_FIELD,
        "number": NUMBER_FIELD,
        "single_select": SINGLE_SELECT_FIELD,
        "multi_select": MULTI_SELECT_FIELD,
        "url": URL_FIELD,
        "checkbox": CHECKBOX_FIELD,
    }[field["type"]]
    payload = {"field_name": field["name"], "type": field_type}
    if field["type"] in {"single_select", "multi_select"}:
        payload["property"] = {"options": [{"name": option} for option in field.get("options", [])]}
    return payload


def list_tables(api: FeishuBitableAPI, app_token: str) -> dict[str, dict[str, Any]]:
    return {str(item.get("name") or "").strip(): item for item in api.list_tables(app_token)}


def list_fields(api: FeishuBitableAPI, app_token: str, table_id: str) -> dict[str, dict[str, Any]]:
    return {str(item.get("field_name") or "").strip(): item for item in api.list_fields(app_token, table_id)}


def ensure_table(api: FeishuBitableAPI, app_token: str, spec: SheetPayload, *, apply: bool) -> dict[str, Any]:
    existing_tables = list_tables(api, app_token)
    table = existing_tables.get(spec.table_name)
    created = False
    if table:
        table_id = str(table.get("table_id") or "").strip()
    else:
        if not apply:
            return {"table_name": spec.table_name, "table_id": "", "created": False, "status": "planned_create"}
        created_table = api.create_table(app_token, spec.table_name, [field_type_payload(field) for field in spec.fields])
        table_id = str(created_table.get("table_id") or "").strip()
        created = True
    if not table_id:
        raise RuntimeError(f"Unable to resolve table_id for {spec.table_name}")

    current_fields = list_fields(api, app_token, table_id) if apply or created else {}
    created_fields: list[str] = []
    option_updates: dict[str, list[str]] = {}
    for field in spec.fields:
        existing = current_fields.get(field["name"])
        payload = field_type_payload(field)
        if not existing:
            created_fields.append(field["name"])
            if apply and table:
                api._request(
                    f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
                    method="POST",
                    payload=payload,
                )
            continue
        if int(existing.get("type") or 0) != payload["type"]:
            raise RuntimeError(
                f"Field type mismatch for {spec.table_name}.{field['name']}: expected {payload['type']}, got {existing.get('type')}"
            )
        if field["type"] in {"single_select", "multi_select"} and apply:
            current_options = [str(option.get("name") or "").strip() for option in ((existing.get("property") or {}).get("options") or [])]
            missing = [option for option in field.get("options", []) if option not in current_options]
            if missing:
                merged = [{"name": option} for option in current_options if option]
                merged.extend({"name": option} for option in missing)
                api._request(
                    f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{existing['field_id']}",
                    method="PUT",
                    payload={"field_name": field["name"], "type": payload["type"], "property": {"options": merged}},
                )
                option_updates[field["name"]] = missing
    return {
        "table_name": spec.table_name,
        "table_id": table_id,
        "created": created,
        "status": "created" if created else "existing",
        "created_fields": created_fields,
        "option_updates": option_updates,
        "expected_fields": len(spec.fields),
    }


def batch_create(api: FeishuBitableAPI, app_token: str, table_id: str, rows: list[dict[str, Any]]) -> int:
    created = 0
    for start in range(0, len(rows), 500):
        batch = rows[start : start + 500]
        if batch:
            api.batch_create_records(app_token, table_id, batch)
            created += len(batch)
    return created


def seed_table(api: FeishuBitableAPI, app_token: str, table_id: str, spec: SheetPayload, *, apply: bool) -> dict[str, Any]:
    normalized = [normalize_record({"fields": spec.fields}, row) for row in spec.records]
    field_types = {field["name"]: field["type"] for field in spec.fields}
    for record in normalized:
        for field_name, field_type in field_types.items():
            if field_type == "url" and field_name in record:
                link_value = to_link_object(record[field_name])
                if link_value is None:
                    record.pop(field_name, None)
                else:
                    record[field_name] = link_value
    existing = api.list_records(app_token, table_id)
    existing_count = len(existing)
    expected_count = len(normalized)
    if existing_count not in {0, expected_count}:
        raise RuntimeError(f"Table {spec.table_name} already has {existing_count} records; expected 0 or {expected_count}.")
    created_count = 0
    if apply and existing_count == 0:
        created_count = batch_create(api, app_token, table_id, normalized)
    verified_count = len(api.list_records(app_token, table_id))
    return {
        "table_name": spec.table_name,
        "table_id": table_id,
        "existing_records": existing_count,
        "expected_records": expected_count,
        "created_records": created_count,
        "verified_records": verified_count,
        "status": "seeded" if created_count else ("already_seeded" if verified_count == expected_count else "planned_seed"),
    }


def resolve_table_counts(api: FeishuBitableAPI, app_token: str, table_ids: dict[str, str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table_name, table_id in table_ids.items():
        counts[table_name] = len(api.list_records(app_token, table_id))
    return counts


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(*, apply: bool, account_id: str, output_dir: Path | None = None) -> dict[str, Any]:
    sheets = read_sheet_payloads()
    creds = load_feishu_credentials(account_id)
    api = FeishuBitableAPI(creds["app_id"], creds["app_secret"])
    app_token = api.resolve_app_token(BASE_LINK)

    artifacts = output_dir or ARTIFACT_ROOT / datetime.now().strftime("%Y-%m-%d") / f"adagj-{now_stamp()}-ts-kb-07"
    artifacts.mkdir(parents=True, exist_ok=True)

    table_results: list[dict[str, Any]] = []
    table_ids: dict[str, str] = {}

    for spec in sheets.values():
        table_result = ensure_table(api, app_token, spec, apply=apply)
        table_ids[spec.table_name] = table_result["table_id"]
        table_results.append(table_result)

    seed_results: dict[str, Any] = {}
    for spec in sheets.values():
        seed_results[spec.table_name] = seed_table(api, app_token, table_ids[spec.table_name], spec, apply=apply)

    record_counts = resolve_table_counts(api, app_token, table_ids)
    result = {
        "status": "applied" if apply else "dry-run",
        "app_token": app_token,
        "base_link": BASE_LINK,
        "table_ids": table_ids,
        "table_results": table_results,
        "seed_results": seed_results,
        "record_counts": record_counts,
        "seed_counts": {name: len(spec.records) for name, spec in sheets.items()},
    }
    write_json(artifacts / "ts-kb-07-feishu-result.json", result)
    write_json(artifacts / "feishu-input-summary.json", {name: {"records": len(spec.records), "fields": [field["name"] for field in spec.fields]} for name, spec in sheets.items()})
    return {"artifact_dir": str(artifacts), **result}


def main() -> int:
    parser = argparse.ArgumentParser(description="Wire TS-KB-07 policy signal tables into Feishu.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    parser.add_argument("--output-dir", default="")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve() if args.output_dir else None
    result = run(apply=bool(args.apply), account_id=args.account_id, output_dir=output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
