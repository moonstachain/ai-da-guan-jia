#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
CAPABILITY_DIR = BACKEND_ROOT / "capabilities"
REGISTRY_PATH = REPO_ROOT / "artifacts" / "smart-youth" / "smart-youth-table-registry.json"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.smart_youth_base_build_and_seed import build_table_specs  # noqa: E402


FIELD_TYPE_MAP: dict[str, int] = {
    "text": 1,
    "number": 2,
    "single_select": 3,
    "multi_select": 4,
    "datetime": 5,
    "checkbox": 7,
    "url": 15,
}

BIZ_TYPE_MAP: dict[str, str] = {
    "text": "Text",
    "number": "Number",
    "single_select": "SingleSelect",
    "multi_select": "MultiSelect",
    "datetime": "DateTime",
    "checkbox": "Checkbox",
    "url": "URL",
}


@dataclass(frozen=True)
class CapabilitySpec:
    capability_id: str
    table_key: str
    name: str
    description: str
    search_hint: str


CAPABILITY_SPECS: tuple[CapabilitySpec, ...] = (
    CapabilitySpec(
        capability_id="smart_youth_student_profile",
        table_key="T01",
        name="智能少年 - 学员档案",
        description="查询学员主档案表",
        search_hint="按孩子ID、姓名、状态或关卡读取学员主档案",
    ),
    CapabilitySpec(
        capability_id="smart_youth_activity_log",
        table_key="T02",
        name="智能少年 - 活动日志",
        description="查询活动与学习日志",
        search_hint="按孩子ID、日期或苏格拉底评级读取活动日志",
    ),
    CapabilitySpec(
        capability_id="smart_youth_growth_eval",
        table_key="T03",
        name="智能少年 - 六维评估",
        description="查询六维成长评估记录",
        search_hint="按孩子ID、评估日期或总教头复核读取评估记录",
    ),
    CapabilitySpec(
        capability_id="smart_youth_milestones",
        table_key="T04",
        name="智能少年 - 里程碑",
        description="查询里程碑与高光时刻",
        search_hint="按孩子ID、里程碑日期或高光层级读取里程碑记录",
    ),
    CapabilitySpec(
        capability_id="smart_youth_projects",
        table_key="T05",
        name="智能少年 - 作品项目",
        description="查询作品与项目",
        search_hint="按孩子ID、项目状态或商业价值读取项目记录",
    ),
    CapabilitySpec(
        capability_id="smart_youth_assets",
        table_key="T06",
        name="智能少年 - 对外展示资产",
        description="查询对外展示资产与授权记录",
        search_hint="按孩子ID、授权状态或可用场景读取展示资产",
    ),
    CapabilitySpec(
        capability_id="smart_youth_orders",
        table_key="T07",
        name="智能少年 - 产品线成交",
        description="查询产品线与成交记录",
        search_hint="按孩子ID、产品线或续费状态读取成交记录",
    ),
)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing smart-youth registry: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def capability_actions(search_hint: str) -> list[dict[str, Any]]:
    return [
        {
            "key": "searchRecords",
            "name": "搜索记录",
            "description": search_hint,
            "outputMode": "unary",
        }
    ]


def build_capability_payload(spec: CapabilitySpec, registry: dict[str, Any]) -> dict[str, Any]:
    tables = registry.get("tables") or {}
    table_entry = tables.get({
        "T01": "T01_学员主档案",
        "T02": "T02_活动与学习日志",
        "T03": "T03_六维成长评估",
        "T04": "T04_里程碑与高光时刻",
        "T05": "T05_作品与项目",
        "T06": "T06_对外展示资产",
        "T07": "T07_产品线与成交",
    }[spec.table_key])
    if not table_entry:
        raise KeyError(f"missing table entry for {spec.table_key}")

    spec_lookup = {table.table_key: table for table in build_table_specs()}
    table_spec = spec_lookup[spec.table_key]

    fields: list[dict[str, Any]] = []
    field_ids = table_entry.get("field_ids") or {}
    for field in table_spec.fields:
        field_name = str(field["name"])
        field_type = str(field["type"]).strip().lower()
        field_id = str(field_ids.get(field_name) or "").strip()
        if not field_id:
            raise KeyError(f"missing field id for {spec.table_key}.{field_name}")
        fields.append(
            {
                "id": field_id,
                "name": field_name,
                "type": FIELD_TYPE_MAP[field_type],
                "bizType": BIZ_TYPE_MAP[field_type],
                "readable": True,
                "writeable": False,
            }
        )

    return {
        "id": spec.capability_id,
        "pluginKey": "@official-plugins/feishu-bitable",
        "pluginVersion": "1.0.7",
        "name": spec.name,
        "description": spec.description,
        "tableKey": spec.table_key,
        "tableName": str(table_entry.get("table_name") or ""),
        "mirrorSurface": {
            "baseId": str(registry.get("app_token") or ""),
            "tableId": str(table_entry.get("table_id") or ""),
        },
        "formValue": {
            "tableID": str(table_entry.get("table_id") or ""),
            "fields": fields,
        },
        "actions": capability_actions(spec.search_hint),
        "queryContract": {
            "supportedOperators": ["equals", "not_equals", "contains", "in", "gt", "gte", "lt", "lte"],
            "defaultSort": "descending",
            "limit": 100,
        },
    }


def write_capabilities(*, dry_run: bool) -> list[dict[str, Any]]:
    registry = load_registry()
    ensure_dir(CAPABILITY_DIR)
    payloads: list[dict[str, Any]] = []
    for spec in CAPABILITY_SPECS:
        payload = build_capability_payload(spec, registry)
        payloads.append(payload)
        if dry_run:
            continue
        output_path = CAPABILITY_DIR / f"{spec.capability_id}.json"
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payloads


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Smart Youth capability JSON files.")
    parser.add_argument("--dry-run", action="store_true", help="Print the planned payloads without writing files.")
    args = parser.parse_args(argv)

    payloads = write_capabilities(dry_run=args.dry_run)
    print(json.dumps({"count": len(payloads), "dry_run": args.dry_run, "capabilities": payloads}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
