#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from python_calamine import CalamineWorkbook

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.feishu_deploy import FeishuBitableAPI, normalize_record
from scripts.boomerang.ts_brm_01_build_base import api_request, ensure_table_fields, load_api, resolve_app_token


TASK_ID = "TS-YSE-CSKB-01"
BASE_NAME = "YSE_财税战略知识库"
WIKI_TOKEN = "NMVywtxVLiXdVskrlhZc3LIWnHe"
DEFAULT_SOURCE = Path("/Users/liming/Downloads/files (14).zip")
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "yse-cskb"
DEFAULT_REGISTRY_PATH = DEFAULT_ARTIFACT_ROOT / "table_registry.json"
DEFAULT_ACCOUNT_ID = "feishu-claw"
DEFAULT_BATCH_SIZE = 200


def text(name: str, *, multiline: bool = False) -> dict[str, Any]:
    return {"name": name, "type": "multiline_text" if multiline else "text"}


def single_select(name: str, options: list[str]) -> dict[str, Any]:
    return {"name": name, "type": "single_select", "options": [opt for opt in options if str(opt).strip()]}


def chunked(items: list[Any], size: int) -> list[list[Any]]:
    return [items[idx : idx + size] for idx in range(0, len(items), size)]


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def load_source_workbook(source: Path) -> tuple[Path, CalamineWorkbook]:
    if source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as archive:
            xlsx_members = [name for name in archive.namelist() if name.lower().endswith(".xlsx")]
            if not xlsx_members:
                raise RuntimeError(f"No .xlsx file found in {source}")
            temp_dir = Path(tempfile.mkdtemp(prefix="yse-cskb-"))
            extracted = Path(archive.extract(xlsx_members[0], temp_dir))
            return extracted, CalamineWorkbook.from_path(extracted)
    if not source.exists():
        raise FileNotFoundError(source)
    return source, CalamineWorkbook.from_path(source)


def row_records(rows: list[list[Any]], field_names: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in rows[1:]:
        if not any(normalize_text(cell) for cell in row):
            continue
        record: dict[str, Any] = {}
        for idx, field_name in enumerate(field_names):
            value = row[idx] if idx < len(row) else ""
            if normalize_text(value):
                record[field_name] = value
        records.append(record)
    return records


def kb03_records(rows: list[list[Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    case_names = rows[0][1:]
    field_names = [
        "案例编号",
        "行业",
        "客户画像",
        "介入前状态",
        "核心痛点",
        "解决方案",
        "使用模式",
        "量化效果",
        "交付周期",
        "收费模式",
        "关键成功要素",
        "可复用知识",
    ]
    records: list[dict[str, Any]] = []
    for col_idx, case_name in enumerate(case_names, start=1):
        record: dict[str, Any] = {"案例名称": case_name}
        for row_idx, field_name in enumerate(field_names, start=1):
            value = rows[row_idx][col_idx] if row_idx < len(rows) and col_idx < len(rows[row_idx]) else ""
            if normalize_text(value):
                record[field_name] = value
        records.append(record)
    return records


def kb05_records(rows: list[list[Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in rows[1:]:
        if not any(normalize_text(cell) for cell in row):
            continue
        record = {
            "阶段": row[0] if len(row) > 0 else "",
            "序号": row[1] if len(row) > 1 else "",
            "资料名称": row[2] if len(row) > 2 else "",
            "近两年": row[3] if len(row) > 3 else "",
            "当年最近期": row[4] if len(row) > 4 else "",
            "获取方式": row[5] if len(row) > 5 else "",
            "分析目的": row[6] if len(row) > 6 else "",
            "AI自动化可行性": row[7] if len(row) > 7 else "",
        }
        records.append(record)
    return records


def row_key_from_fields(*fields: str):
    def _key(source: dict[str, Any]) -> str:
        parts = [normalize_text(source.get(field)) for field in fields]
        return "|".join(parts).strip("|")

    return _key


TABLE_SPECS: list[dict[str, Any]] = [
    {
        "table_key": "T01",
        "table_name": "T01_财税政策知识库",
        "sheet_name": "KB-01 财税政策知识库",
        "primary_field": "编号",
        "fields": [
            text("编号"),
            text("政策节点"),
            single_select(
                "政策类别",
                [
                    "征管体系",
                    "行业监管",
                    "税法变更",
                    "反避税",
                    "社保征管",
                    "优惠政策",
                    "征管执法",
                    "个税",
                    "进项抵扣",
                    "出口退税",
                    "用工成本",
                    "资金管理",
                    "税率基础",
                    "法律风险",
                    "征管技术",
                    "行业风险",
                    "运营风险",
                ],
            ),
            text("核心要点", multiline=True),
            single_select("风险等级", ["极高", "高", "中", "利好", "基础"]),
            text("生效时间"),
            text("影响行业"),
            text("应对策略关键词"),
            text("数据来源"),
        ],
        "records_fn": lambda rows: row_records(
            rows,
            ["编号", "政策节点", "政策类别", "核心要点", "风险等级", "生效时间", "影响行业", "应对策略关键词", "数据来源"],
        ),
    },
    {
        "table_key": "T02",
        "table_name": "T02_架构方案模式库",
        "sheet_name": "KB-02 架构方案模式库",
        "primary_field": "编号",
        "fields": [
            text("编号"),
            text("模式名称"),
            single_select("模式类别", ["主体拆分", "业务重组", "股权架构", "风险管理", "成本优化", "战略架构", "资金管理", "运营优化"]),
            text("核心机制", multiline=True),
            text("适用场景"),
            text("合规依据"),
            text("预期效果"),
            text("风险红线"),
            text("案例映射"),
        ],
        "records_fn": lambda rows: row_records(
            rows, ["编号", "模式名称", "模式类别", "核心机制", "适用场景", "合规依据", "预期效果", "风险红线", "案例映射"]
        ),
    },
    {
        "table_key": "T03",
        "table_name": "T03_案例数据库",
        "sheet_name": "KB-03 案例数据库",
        "primary_field": "案例编号",
        "fields": [
            text("案例编号"),
            text("案例名称"),
            text("行业"),
            text("客户画像"),
            text("介入前状态"),
            text("核心痛点"),
            text("解决方案", multiline=True),
            text("使用模式"),
            text("量化效果", multiline=True),
            text("交付周期"),
            text("收费模式"),
            text("关键成功要素"),
            text("可复用知识", multiline=True),
        ],
        "records_fn": kb03_records,
    },
    {
        "table_key": "T04",
        "table_name": "T04_服务产品定价库",
        "sheet_name": "KB-04 服务产品定价库",
        "primary_field": "产品层级",
        "fields": [
            text("产品层级"),
            text("产品名称"),
            text("服务内容", multiline=True),
            text("交付成果"),
            text("定价标准"),
            text("服务周期"),
            text("目标转化"),
            text("对应YSE层"),
        ],
        "records_fn": lambda rows: row_records(
            rows, ["产品层级", "产品名称", "服务内容", "交付成果", "定价标准", "服务周期", "目标转化", "对应YSE层"]
        ),
    },
    {
        "table_key": "T05",
        "table_name": "T05_尽调工具库",
        "sheet_name": "KB-05 尽调工具库",
        "primary_field": "序号",
        "record_key_fn": row_key_from_fields("阶段", "序号"),
        "fields": [
            single_select("阶段", ["L1前置资料", "L2基础资料"]),
            text("序号"),
            text("资料名称"),
            single_select("近两年", ["√", "空"]),
            text("当年最近期"),
            text("获取方式"),
            text("分析目的"),
            single_select(
                "AI自动化可行性",
                [
                    "高-可自动解析",
                    "高-自动识别",
                    "高-可自动计算",
                    "高-可自动比对",
                    "高-可自动分析",
                    "高-OCR识别",
                    "中-需规则引擎",
                    "中-需AI识别",
                    "中-分类标注",
                    "中-AI辅助审阅",
                    "低-需人工解读",
                    "低-需人工理解",
                    "低-需人工评估",
                ],
            ),
        ],
        "records_fn": kb05_records,
    },
    {
        "table_key": "T06",
        "table_name": "T06_话术与转化库",
        "sheet_name": "KB-06 话术与转化库",
        "primary_field": "话术编号",
        "fields": [
            text("话术编号"),
            text("话术名称"),
            text("使用场景"),
            text("话术结构"),
            text("核心话术要点", multiline=True),
            text("转化目标"),
            text("来源文件"),
        ],
        "records_fn": lambda rows: row_records(
            rows, ["话术编号", "话术名称", "使用场景", "话术结构", "核心话术要点", "转化目标", "来源文件"]
        ),
    },
    {
        "table_key": "T07",
        "table_name": "T07_行业基准库",
        "sheet_name": "KB-07 行业基准库",
        "primary_field": "行业",
        "fields": [
            text("行业"),
            text("典型营收规模"),
            text("增值税税负基准"),
            text("所得税贡献率基准"),
            text("人效比基准"),
            text("常见痛点"),
            text("推荐模式组合"),
            text("案例映射"),
        ],
        "records_fn": lambda rows: row_records(
            rows, ["行业", "典型营收规模", "增值税税负基准", "所得税贡献率基准", "人效比基准", "常见痛点", "推荐模式组合", "案例映射"]
        ),
    },
]


def resolve_folder_base(api: FeishuBitableAPI, *, apply: bool, app_token_override: str | None = None) -> tuple[str, dict[str, Any]]:
    return resolve_app_token(
        api,
        wiki_token=WIKI_TOKEN,
        base_name=BASE_NAME,
        apply=apply,
        folder_token_override=None,
        app_token_override=app_token_override,
    )


def ensure_table(app_api: FeishuBitableAPI, app_token: str, table_name: str, fields: list[dict[str, Any]], *, apply: bool) -> str:
    if not apply and app_token.startswith("dryrun::"):
        return f"dryrun::{table_name}"
    existing = {str(item.get("name") or item.get("table_name") or "").strip(): item for item in app_api.list_tables(app_token)}
    table = existing.get(table_name)
    if table and str(table.get("table_id") or "").strip():
        table_id = str(table.get("table_id") or "").strip()
    else:
        if not apply:
            return f"dryrun::{table_name}"
        payload = api_request(
            app_api,
            f"/open-apis/bitable/v1/apps/{app_token}/tables",
            method="POST",
            payload={"table": {"name": table_name}},
        )
        data = payload.get("data") or {}
        created = data.get("table") or data
        table_id = str(created.get("table_id") or "").strip()
        if not table_id:
            raise RuntimeError(f"Failed to create table {table_name}: {json.dumps(payload, ensure_ascii=False)}")

    ensure_table_fields(
        app_api,
        app_token,
        table_id,
        {"table_name": table_name, "fields": fields},
        apply=apply,
        log_lines=[],
    )
    return table_id


def record_primary(record: dict[str, Any], primary_field: str) -> str:
    return str((record.get("fields") or {}).get(primary_field) or "").strip()


def upsert_seed_rows(
    api: FeishuBitableAPI,
    *,
    app_token: str,
    table_id: str,
    schema: dict[str, Any],
    rows: list[dict[str, Any]],
    primary_field: str,
    record_key_fn: Any | None,
    apply: bool,
) -> dict[str, Any]:
    normalized_rows = [normalize_record(schema, row) for row in rows]
    existing_records = api.list_records(app_token, table_id) if apply else []
    key_fn = record_key_fn or (lambda source: str((source.get(primary_field) or "")).strip())
    existing_index = {
        key_fn(record.get("fields") or {}): record
        for record in existing_records
        if key_fn(record.get("fields") or {})
    }

    to_create: list[dict[str, Any]] = []
    to_update: list[dict[str, Any]] = []
    for row in normalized_rows:
        key = key_fn(row)
        if not key:
            continue
        existing = existing_index.get(key)
        if existing and str(existing.get("record_id") or "").strip():
            current_fields = existing.get("fields") or {}
            if current_fields != row:
                to_update.append({"record_id": existing["record_id"], "fields": row})
        else:
            to_create.append(row)

    if apply:
        for chunk in chunked(to_create, DEFAULT_BATCH_SIZE):
            if chunk:
                api.batch_create_records(app_token, table_id, chunk)
        for chunk in chunked(to_update, DEFAULT_BATCH_SIZE):
            if chunk:
                api.batch_update_records(app_token, table_id, chunk)

    refreshed = api.list_records(app_token, table_id) if apply else []
    refreshed_index = {
        key_fn(record.get("fields") or {}): record
        for record in refreshed
        if key_fn(record.get("fields") or {})
    }
    expected_count = len(normalized_rows)
    actual_count = len(refreshed_index) if apply else 0
    if apply and actual_count != expected_count:
        raise RuntimeError(
            f"Seed count mismatch for {table_id}: expected {expected_count}, got {actual_count}. "
            f"created={len(to_create)} updated={len(to_update)}"
        )

    return {
        "expected_count": expected_count,
        "actual_count": actual_count if apply else expected_count,
        "created_count": len(to_create) if apply else len(to_create),
        "updated_count": len(to_update) if apply else len(to_update),
    }


def build_registry(
    *,
    source_path: Path,
    base_name: str,
    app_token: str,
    table_ids: dict[str, str],
    counts: dict[str, int],
) -> dict[str, Any]:
    tables: dict[str, dict[str, Any]] = {}
    for spec in TABLE_SPECS:
        table_name = spec["table_name"]
        tables[table_name] = {
            "table_id": table_ids[table_name],
            "records": counts[table_name],
        }
    return {
        "base_name": base_name,
        "app_token": app_token,
        "wiki_node": WIKI_TOKEN,
        "tables": tables,
        "created_at": datetime.now().date().isoformat(),
        "created_by": f"Codex via {TASK_ID}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and seed the YSE财税战略知识库 Feishu base.")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="Path to the extracted .xlsx workbook.")
    parser.add_argument("--registry-path", default=str(DEFAULT_REGISTRY_PATH))
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    parser.add_argument("--app-token", default="")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    source_path = Path(args.source).expanduser().resolve()
    xlsx_path, workbook = load_source_workbook(source_path)
    apply_changes = bool(args.apply)
    artifact_registry_path = Path(args.registry_path).expanduser().resolve()
    artifact_registry_path.parent.mkdir(parents=True, exist_ok=True)

    api = load_api(args.account_id)
    app_token, resolve_meta = resolve_folder_base(api, apply=apply_changes, app_token_override=args.app_token or None)

    seed_results: dict[str, dict[str, Any]] = {}
    table_ids: dict[str, str] = {}
    counts: dict[str, int] = {}

    for spec in TABLE_SPECS:
        rows = workbook.get_sheet_by_name(spec["sheet_name"]).to_python()
        records = spec["records_fn"](rows)
        table_id = ensure_table(api, app_token, spec["table_name"], spec["fields"], apply=apply_changes)
        table_ids[spec["table_name"]] = table_id

        schema = {"fields": spec["fields"]}
        seed_result = upsert_seed_rows(
            api,
            app_token=app_token,
            table_id=table_id,
            schema=schema,
            rows=records,
            primary_field=spec["primary_field"],
            record_key_fn=spec.get("record_key_fn"),
            apply=apply_changes,
        )
        seed_results[spec["table_name"]] = seed_result
        counts[spec["table_name"]] = seed_result["actual_count"]

    registry = build_registry(
        source_path=xlsx_path,
        base_name=BASE_NAME,
        app_token=app_token,
        table_ids=table_ids,
        counts=counts,
    )

    artifact_registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    output = {
        "mode": "apply" if apply_changes else "dry-run",
        "source": str(xlsx_path),
        "resolve_meta": resolve_meta,
        "registry_path": str(artifact_registry_path),
        "registry": registry,
        "seed_results": seed_results,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
