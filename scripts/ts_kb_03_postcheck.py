from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.r12_kangbo_signal_spec import TARGET_APP_TOKEN as KANGBO_APP_TOKEN
from scripts.sync_r11_v2_skill_inventory_feishu import bootstrap_client, list_fields, list_records, list_tables
from scripts.ts_kb_03_kangbo_expert_ops import TABLE_ID_MAP_FILE


ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "ts-kb-03"
CAPABILITY_DIR = ARTIFACT_ROOT / "capabilities"
POSTCHECK_PATH = ARTIFACT_ROOT / "postcheck.json"
L1_TABLE_ID = "tbl6QgzUgcXq4HO5"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Post-check TS-KB-03 live Feishu state and export Miaoda capability JSON files.")
    parser.add_argument("--account-id", default="feishu-claw")
    parser.add_argument("--write-capabilities", action="store_true")
    return parser.parse_args(argv)


def biz_type_name(field_type: int) -> str:
    mapping = {
        1: "Text",
        2: "Number",
        3: "SingleSelect",
        4: "MultiSelect",
        5: "DateTime",
        15: "URL",
    }
    return mapping.get(int(field_type), str(field_type))


def load_table_ids() -> dict[str, str]:
    return json.loads(TABLE_ID_MAP_FILE.read_text(encoding="utf-8"))


def simplify_field(field: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "field_id": str(field.get("field_id") or ""),
        "field_name": str(field.get("field_name") or field.get("name") or ""),
        "type": int(field.get("type") or 0),
        "biz_type": biz_type_name(int(field.get("type") or 0)),
    }
    options = [str(item.get("name") or "").strip() for item in ((field.get("property") or {}).get("options") or [])]
    options = [item for item in options if item]
    if options:
        payload["enum_values"] = options
    return payload


def table_summary(client: Any, table_id: str) -> dict[str, Any]:
    table_meta = next((item for item in list_tables(client, KANGBO_APP_TOKEN) if str(item.get("table_id") or "").strip() == table_id), None)
    fields = list_fields(client, KANGBO_APP_TOKEN, table_id)
    records = list_records(client, KANGBO_APP_TOKEN, table_id)
    return {
        "table_id": table_id,
        "table_name": str((table_meta or {}).get("name") or ""),
        "record_count": len(records),
        "field_count": len(fields),
        "fields": [simplify_field(item) for item in fields],
        "sample_primary_values": [
            next(iter((record.get("fields") or {}).values()), "")
            for record in records[:5]
        ],
    }


def capability_payload(*, capability_id: str, name: str, description: str, table_id: str, fields: list[dict[str, Any]]) -> dict[str, Any]:
    form_fields: list[dict[str, Any]] = []
    for field in fields:
        item = {
            "id": field["field_id"],
            "name": field["field_name"],
            "type": field["type"],
            "bizType": field["biz_type"],
            "readable": True,
            "writeable": False,
        }
        enum_values = field.get("enum_values") or []
        if enum_values:
            item["enumValues"] = enum_values
        form_fields.append(item)
    return {
        "id": capability_id,
        "pluginKey": "@official-plugins/feishu-bitable",
        "pluginVersion": "1.0.7",
        "name": name,
        "description": description,
        "icon": "",
        "paramsSchema": {},
        "formValue": {
            "tableID": table_id,
            "fields": form_fields,
        },
        "actions": [
            {
                "key": "searchRecords",
                "name": "搜索记录",
                "description": f"搜索{name}数据",
                "outputMode": "unary",
            }
        ],
    }


def export_capabilities(payload: dict[str, Any]) -> list[str]:
    CAPABILITY_DIR.mkdir(parents=True, exist_ok=True)
    exported: list[str] = []
    expert_network = payload["tables"]["expert_network"]
    expert_insights = payload["tables"]["expert_insights"]
    files = {
        "yuanlios_expert_network.json": capability_payload(
            capability_id="yuanlios_expert_network",
            name="原力智库 - 专家网络",
            description="基于飞书多维表格查询康波智库 L2_专家智库 表数据，支持 searchRecords 查询操作",
            table_id=expert_network["table_id"],
            fields=expert_network["fields"],
        ),
        "yuanlios_expert_insights.json": capability_payload(
            capability_id="yuanlios_expert_insights",
            name="原力智库 - 专家洞察",
            description="基于飞书多维表格查询康波智库 L3_专家洞察 表数据，支持 searchRecords 查询操作",
            table_id=expert_insights["table_id"],
            fields=expert_insights["fields"],
        ),
    }
    for filename, content in files.items():
        path = CAPABILITY_DIR / filename
        path.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        exported.append(str(path))
    return exported


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not (os.getenv("FEISHU_APP_ID") and os.getenv("FEISHU_APP_SECRET")):
        client = bootstrap_client(args.account_id)
    else:
        client = bootstrap_client(args.account_id)

    table_ids = load_table_ids()
    payload = {
        "app_token": KANGBO_APP_TOKEN,
        "tables": {
            "l1_signal": table_summary(client, L1_TABLE_ID),
            "expert_network": table_summary(client, table_ids["expert_network"]),
            "expert_insights": table_summary(client, table_ids["expert_insights"]),
        },
    }
    if args.write_capabilities:
        payload["capability_files"] = export_capabilities(payload)
    POSTCHECK_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
