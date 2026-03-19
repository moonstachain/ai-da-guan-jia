from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from dashboard.feishu_deploy import FeishuBitableAPI
from python_calamine import load_workbook


REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "boomerang"
RUN_ROOT = ARTIFACT_ROOT / "runs"
REGISTRY_PATH = ARTIFACT_ROOT / "table_registry.json"

TASK_TRACKER_APP = "PVDgbdWYFaDLBiss0hlcM5WRnQc"
TASK_TRACKER_TABLE = "tblB9JQ4cROTBUnr"

WIKI_NODE_TOKEN = "W9ksww7QuiV969k8Hqtcro1Fn7c"
TARGET_APP_TOKEN = "LDrsbKwysadY4UsHb44cZOwDn4O"
TARGET_BASE_NAME = "回旋镖局_战略驾驶舱"
TARGET_BASE_LINK = f"https://h52xu4gwob.feishu.cn/wiki/{WIKI_NODE_TOKEN}?from=from_copylink"

DATA_STATS_PATH = Path("/Users/liming/Documents/会议纪要/【水月旧物造】/老杨回旋镖/数据统计.xlsx")
FINANCE_PATH = Path("/Users/liming/Documents/会议纪要/【水月旧物造】/老杨回旋镖/财务尽调数据.xls")

TEXT = 1
NUMBER = 2
SINGLE_SELECT = 3
MULTI_SELECT = 4
DATETIME = 5
CHECKBOX = 7
URL = 15
FORMULA = 19


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: int
    property: dict[str, Any] | None = None
    fallback_type: int | None = None


@dataclass(frozen=True)
class TableSpec:
    key: str
    table_name: str
    primary_field: str
    fields: list[FieldSpec]


def _field(name: str, type_id: int, *, property: dict[str, Any] | None = None, fallback_type: int | None = None) -> FieldSpec:
    return FieldSpec(name=name, type=type_id, property=property, fallback_type=fallback_type)


def text_field(name: str) -> FieldSpec:
    return _field(name, TEXT)


def number_field(name: str) -> FieldSpec:
    return _field(name, NUMBER)


def select_field(name: str, *options: str) -> FieldSpec:
    return _field(name, SINGLE_SELECT, property={"options": [{"name": option} for option in options if str(option).strip()]})


def multi_select_field(name: str, *options: str) -> FieldSpec:
    return _field(name, MULTI_SELECT, property={"options": [{"name": option} for option in options if str(option).strip()]})


def datetime_field(name: str, fmt: str = "yyyy-MM") -> FieldSpec:
    return _field(name, DATETIME, property={"auto_fill": False, "date_formatter": fmt})


def url_field(name: str) -> FieldSpec:
    return _field(name, URL)


def checkbox_field(name: str) -> FieldSpec:
    return _field(name, CHECKBOX)


def formula_field(name: str, expression: str, *, fallback_type: int = NUMBER) -> FieldSpec:
    return _field(name, FORMULA, property={"formula_expression": expression}, fallback_type=fallback_type)


def select_options(*values: str) -> dict[str, Any]:
    return {"options": [{"name": value} for value in values if str(value).strip()]}


def _table_specs() -> list[TableSpec]:
    return [
        TableSpec(
            key="T01_月度经营数据",
            table_name="T01_月度经营数据",
            primary_field="record_key",
            fields=[
                text_field("record_key"),
                datetime_field("month"),
                select_field("base", "苏州", "广东", "合计"),
                select_field("source_channel", "线上", "私域", "合计"),
                select_field("port", "苏州", "广东", "合计"),
                number_field("gmv"),
                number_field("total_orders"),
                number_field("auction_orders"),
                number_field("fixed_price_orders"),
                number_field("effective_sales"),
                number_field("service_fee_income"),
                number_field("cost"),
                number_field("gross_margin"),
                number_field("platform_fee"),
                number_field("net_margin"),
                number_field("sku_listed"),
                number_field("sku_sold"),
                number_field("items_received"),
                number_field("items_rejected"),
                number_field("active_sellers"),
                number_field("new_customers"),
                number_field("mau"),
                number_field("stale_items_60d"),
                number_field("auction_success_rate"),
                number_field("avg_bid_rounds"),
                number_field("inventory_turnover_days"),
                number_field("daily_auth_capacity"),
                text_field("notes"),
            ],
        ),
        TableSpec(
            key="T02_月度财务数据",
            table_name="T02_月度财务数据",
            primary_field="record_key",
            fields=[
                text_field("record_key"),
                datetime_field("month"),
                number_field("revenue_commission"),
                number_field("revenue_membership"),
                number_field("revenue_ip_content"),
                number_field("revenue_other"),
                formula_field("revenue_total", "[revenue_commission]+[revenue_membership]+[revenue_ip_content]+[revenue_other]"),
                number_field("cost_salary"),
                number_field("cost_rent"),
                number_field("cost_tech"),
                number_field("cost_logistics"),
                number_field("cost_marketing"),
                number_field("cost_auth"),
                number_field("cost_travel"),
                number_field("cost_platform_fee"),
                number_field("cost_other"),
                formula_field("opex_total", "[cost_salary]+[cost_rent]+[cost_tech]+[cost_logistics]+[cost_marketing]+[cost_auth]+[cost_travel]+[cost_platform_fee]+[cost_other]"),
                formula_field("gross_profit", "[revenue_total]-[cost_platform_fee]"),
                formula_field("operating_profit", "[revenue_total]-[opex_total]"),
                formula_field("operating_margin", "IF([revenue_total]>0,[operating_profit]/[revenue_total],0)"),
                number_field("cash_inflow_operations"),
                number_field("cash_outflow_operations"),
                formula_field("net_cash_operations", "[cash_inflow_operations]-[cash_outflow_operations]"),
                number_field("borrowings"),
                number_field("cash_balance"),
                number_field("headcount"),
                number_field("auth_team_size"),
                text_field("notes"),
            ],
        ),
        TableSpec(
            key="T03_客户分析",
            table_name="T03_客户分析",
            primary_field="record_key",
            fields=[
                text_field("record_key"),
                datetime_field("month"),
                select_field("analysis_type", "客户分层", "复购率", "生命周期价值", "流失率", "获客渠道", "会员转化"),
                select_field("segment", "头部", "腰部", "长尾", "全量", "未知"),
                select_field("channel", "视频号", "公众号", "抖音", "小红书", "小程序下单", "企微客服", "私域", "合计"),
                number_field("customer_count"),
                number_field("contribution_amount"),
                number_field("contribution_share"),
                number_field("repeat_rate"),
                number_field("repeat_interval_days"),
                number_field("ltv"),
                number_field("registered_members"),
                number_field("paying_members"),
                number_field("first_order_conversion"),
                number_field("churn_customers_90d"),
                number_field("churn_rate_90d"),
                number_field("avg_order_value"),
                number_field("active_customers"),
                number_field("new_customers"),
                text_field("source_sheet"),
                text_field("source_metric"),
                text_field("source_row_key"),
                text_field("notes"),
            ],
        ),
        TableSpec(
            key="T04_品类分析",
            table_name="T04_品类分析",
            primary_field="record_key",
            fields=[
                text_field("record_key"),
                datetime_field("month"),
                select_field("analysis_type", "收货结构", "上架结构", "转化结构", "鉴定结构", "退货结构"),
                text_field("category"),
                text_field("subcategory"),
                select_field("base", "苏州", "广东", "合计", "未知"),
                number_field("received_count"),
                number_field("listed_count"),
                number_field("sold_count"),
                number_field("return_count"),
                number_field("sell_through_rate"),
                number_field("listing_conversion_rate"),
                number_field("inventory_turnover_days"),
                number_field("appraisal_count"),
                number_field("rejection_count"),
                number_field("gross_margin"),
                number_field("share_of_total"),
                number_field("growth_rate"),
                text_field("source_sheet"),
                text_field("source_metric"),
                text_field("source_row_key"),
                text_field("notes"),
            ],
        ),
        TableSpec(
            key="T05_供应链效率",
            table_name="T05_供应链效率",
            primary_field="record_key",
            fields=[
                text_field("record_key"),
                datetime_field("month"),
                select_field("metric_family", "物流", "收货", "上架SOP", "库存周转", "系统对接"),
                select_field("base", "苏州", "广东", "合计", "未知"),
                text_field("logistics_partner"),
                text_field("product_category"),
                number_field("tickets_inbound"),
                number_field("tickets_outbound"),
                number_field("total_tickets"),
                number_field("total_cost"),
                number_field("avg_ticket_cost"),
                number_field("avg_sop_hours"),
                number_field("turnover_days"),
                number_field("rejection_count"),
                number_field("rejection_rate"),
                number_field("warehouse_cycle_days"),
                number_field("avg_receipt_days"),
                number_field("avg_listing_days"),
                select_field("bottleneck_type", "物流", "仓储", "鉴定", "系统", "未知"),
                text_field("source_sheet"),
                text_field("source_metric"),
                text_field("source_row_key"),
                text_field("notes"),
            ],
        ),
        TableSpec(
            key="T06_内容与IP",
            table_name="T06_内容与IP",
            primary_field="record_key",
            fields=[
                text_field("record_key"),
                datetime_field("month", "yyyy-MM-dd"),
                select_field("channel", "抖音", "视频号", "小红书", "微信公众号", "直播", "投放", "其他"),
                select_field("platform", "抖音", "视频号", "小红书", "微信公众号", "小程序", "其他"),
                select_field("content_type", "内容发布", "直播", "IP内容", "付费投放", "增长矩阵", "其他"),
                select_field("metric_family", "发布", "播放", "互动", "转化", "粉丝", "投放", "ROI"),
                number_field("publish_count"),
                number_field("live_sessions"),
                number_field("avg_viewers"),
                number_field("plays"),
                number_field("engagement_count"),
                number_field("gmv"),
                number_field("conversion_rate"),
                number_field("ad_spend"),
                number_field("roi"),
                number_field("followers"),
                number_field("followers_growth"),
                text_field("content_theme"),
                text_field("source_sheet"),
                text_field("source_metric"),
                text_field("source_row_key"),
                text_field("notes"),
            ],
        ),
        TableSpec(
            key="T07_财务建模",
            table_name="T07_财务建模",
            primary_field="record_key",
            fields=[
                text_field("record_key"),
                select_field("scenario", "实际", "保底", "挑战", "保守"),
                text_field("year"),
                number_field("annual_gmv"),
                number_field("annual_revenue"),
                number_field("rev_commission"),
                number_field("rev_ip_content"),
                number_field("rev_membership"),
                number_field("rev_data_ad"),
                number_field("annual_opex"),
                number_field("total_orders"),
                number_field("monthly_sku_needed"),
                number_field("monthly_sellers_needed"),
                number_field("take_rate"),
                number_field("revenue_margin"),
                number_field("opex_ratio"),
                number_field("revenue_per_order"),
                text_field("assumptions_note"),
                text_field("source_version"),
            ],
        ),
        TableSpec(
            key="T08_对标矩阵",
            table_name="T08_对标矩阵",
            primary_field="record_key",
            fields=[
                text_field("record_key"),
                text_field("company"),
                select_field("country", "中国", "美国", "日本", "荷兰", "其他"),
                text_field("model_type"),
                text_field("data_year"),
                number_field("gmv"),
                number_field("revenue"),
                number_field("take_rate"),
                number_field("gross_margin"),
                number_field("ebitda_margin"),
                number_field("headcount"),
                number_field("auth_team_size"),
                number_field("active_buyers"),
                number_field("active_sellers"),
                number_field("category_count"),
                number_field("countries_served"),
                text_field("ai_capability"),
                number_field("funding_total"),
                number_field("latest_valuation"),
                text_field("key_strength"),
                text_field("key_weakness"),
                text_field("lesson_for_boomerang"),
                number_field("benchmark_rank"),
                text_field("source_note"),
            ],
        ),
        TableSpec(
            key="T09_进化追踪",
            table_name="T09_进化追踪",
            primary_field="record_key",
            fields=[
                text_field("record_key"),
                text_field("initiative_id"),
                select_field("dimension", "D1信任基础设施", "D2供给引擎", "D3需求引擎", "D4交易机制", "D5内容与IP", "D6技术与数据", "D7收入模型"),
                text_field("initiative_name"),
                select_field("priority", "P0关键路径", "P1重要", "P2增强"),
                text_field("target_quarter"),
                select_field("status", "待启动", "筹备中", "进行中", "已完成", "阻塞"),
                number_field("estimated_investment"),
                number_field("expected_revenue_impact"),
                text_field("benchmark_ref"),
                text_field("kpi_metric"),
                text_field("kpi_current"),
                text_field("kpi_target"),
                text_field("owner"),
                text_field("dependency"),
                text_field("initiative_type"),
                number_field("roi_estimate"),
                number_field("payback_months"),
                select_field("risk_level", "低", "中", "高", "极高"),
                select_field("is_key_path", "是", "否"),
                text_field("strategic_theme"),
                text_field("action_stage"),
                text_field("source_note"),
            ],
        ),
        TableSpec(
            key="T10_估值测算",
            table_name="T10_估值测算",
            primary_field="record_key",
            fields=[
                text_field("record_key"),
                text_field("round"),
                text_field("target_year"),
                number_field("gmv_basis"),
                number_field("revenue_basis"),
                number_field("valuation_multiple_low"),
                number_field("valuation_multiple_high"),
                number_field("funding_amount"),
                number_field("dilution_pct"),
                text_field("use_of_funds"),
                text_field("key_milestones"),
                text_field("benchmark_company"),
                number_field("benchmark_multiple"),
                number_field("implied_valuation_low"),
                number_field("implied_valuation_high"),
                number_field("post_money_low"),
                number_field("post_money_high"),
                text_field("scenario_label"),
                text_field("source_note"),
            ],
        ),
        TableSpec(
            key="T11_月度经营快照",
            table_name="T11_月度经营快照",
            primary_field="record_key",
            fields=[
                text_field("record_key"),
                datetime_field("month"),
                text_field("snapshot_name"),
                number_field("gmv"),
                number_field("revenue"),
                number_field("opex"),
                number_field("profit"),
                number_field("orders"),
                number_field("active_sellers"),
                number_field("active_buyers"),
                number_field("content_reach"),
                number_field("customer_health_score"),
                number_field("supply_chain_score"),
                number_field("tech_health_score"),
                text_field("strategic_priority"),
                text_field("notes"),
            ],
        ),
        TableSpec(
            key="T12_元数据与配置",
            table_name="T12_元数据与配置",
            primary_field="config_key",
            fields=[
                text_field("config_key"),
                text_field("config_value"),
                select_field("value_type", "string", "number", "json", "date", "boolean"),
                text_field("scope"),
                text_field("source_table"),
                text_field("source_sheet"),
                text_field("source_field"),
                checkbox_field("enabled"),
                text_field("version"),
                text_field("owner"),
                text_field("description"),
                datetime_field("updated_at", "yyyy-MM-dd HH:mm"),
                text_field("notes"),
            ],
        ),
    ]


TABLE_SPECS = _table_specs()
TABLE_SPEC_BY_KEY = {spec.key: spec for spec in TABLE_SPECS}


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def now_day() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def load_feishu_client(account_id: str = "feishu-claw") -> FeishuBitableAPI:
    from scripts.create_kangbo_signal_tables import load_feishu_credentials

    creds = load_feishu_credentials(account_id)
    os.environ["FEISHU_APP_ID"] = creds["app_id"]
    os.environ["FEISHU_APP_SECRET"] = creds["app_secret"]
    return FeishuBitableAPI(creds["app_id"], creds["app_secret"])


def field_payload(field: FieldSpec) -> dict[str, Any]:
    payload: dict[str, Any] = {"field_name": field.name, "type": field.type}
    if field.property:
        payload["property"] = field.property
    return payload


def list_tables(client: FeishuBitableAPI, app_token: str) -> list[dict[str, Any]]:
    return client.list_tables(app_token)


def list_fields(client: FeishuBitableAPI, app_token: str, table_id: str) -> list[dict[str, Any]]:
    return client.list_fields(app_token, table_id)


def _field_name(field: dict[str, Any]) -> str:
    return str(field.get("field_name") or field.get("name") or "").strip()


def _field_type(field: dict[str, Any]) -> int:
    try:
        return int(field.get("type") or 0)
    except (TypeError, ValueError):
        return 0


def _create_table_empty(client: FeishuBitableAPI, app_token: str, table_name: str) -> str:
    created = client._request(f"/open-apis/bitable/v1/apps/{app_token}/tables", method="POST", payload={"table": {"name": table_name}})
    table = (created.get("data") or {}).get("table") or {}
    table_id = str(table.get("table_id") or "").strip()
    if not table_id:
        tables = list_tables(client, app_token)
        match = next((item for item in tables if str(item.get("name") or "").strip() == table_name), None)
        table_id = str((match or {}).get("table_id") or "").strip()
    if not table_id:
        raise RuntimeError(f"failed to create or resolve table id for {table_name}")
    return table_id


def _ensure_primary_field(client: FeishuBitableAPI, app_token: str, table_id: str, primary_field: str, *, apply: bool) -> str:
    fields = list_fields(client, app_token, table_id)
    primary = next((field for field in fields if field.get("is_primary")), fields[0] if fields else None)
    if primary is None:
        raise RuntimeError(f"table {table_id} has no primary field")
    current_name = _field_name(primary)
    if current_name == primary_field:
        return current_name
    if not apply:
        return primary_field
    client._request(
        f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{primary['field_id']}",
        method="PUT",
        payload={"field_name": primary_field, "type": _field_type(primary)},
    )
    return primary_field


def _field_exists(existing_fields: dict[str, dict[str, Any]], field_name: str) -> bool:
    return field_name in existing_fields


def _merge_select_options(current: list[dict[str, Any]], desired: list[str]) -> list[dict[str, Any]]:
    existing_names = [str(item.get("name") or "").strip() for item in current if str(item.get("name") or "").strip()]
    merged = [{"name": name} for name in existing_names]
    for name in desired:
        if name not in existing_names:
            merged.append({"name": name})
    return merged


def _create_field_with_fallback(
    client: FeishuBitableAPI,
    app_token: str,
    table_id: str,
    field: FieldSpec,
    *,
    apply: bool,
) -> dict[str, Any]:
    payload = field_payload(field)
    if not apply:
        return {"field_name": field.name, "type": field.type}

    try:
        result = client._request(
            f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
            method="POST",
            payload=payload,
        )
        return (result.get("data") or {}).get("field") or {}
    except Exception:
        if field.type == FORMULA:
            fallback = field.fallback_type or NUMBER
            payload = {"field_name": field.name, "type": fallback}
            result = client._request(
                f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
                method="POST",
                payload=payload,
            )
            return (result.get("data") or {}).get("field") or {}
        raise


def ensure_table(client: FeishuBitableAPI, app_token: str, spec: TableSpec, *, apply: bool) -> dict[str, Any]:
    existing = next((item for item in list_tables(client, app_token) if str(item.get("name") or "").strip() == spec.table_name), None)
    created = False
    if existing:
        table_id = str(existing.get("table_id") or "").strip()
        if not table_id:
            raise RuntimeError(f"table {spec.table_name} missing table_id")
    else:
        if not apply:
            return {
                "table_name": spec.table_name,
                "table_id": "",
                "created": False,
                "status": "planned_create",
                "field_count": len(spec.fields),
            }
        table_id = _create_table_empty(client, app_token, spec.table_name)
        created = True

    primary_field_name = _ensure_primary_field(client, app_token, table_id, spec.primary_field, apply=apply)
    current_fields = {_field_name(field): field for field in list_fields(client, app_token, table_id)}
    created_fields: list[str] = []
    option_updates: dict[str, list[str]] = {}

    for field in spec.fields:
        if field.name == primary_field_name:
            continue
        existing_field = current_fields.get(field.name)
        if existing_field:
            if field.type in {SINGLE_SELECT, MULTI_SELECT} and field.property:
                current_options = ((existing_field.get("property") or {}).get("options") or [])
                desired_options = [str(item.get("name") or "").strip() for item in field.property.get("options", [])]
                merged = _merge_select_options(current_options, desired_options)
                if apply and merged != current_options:
                    client._request(
                        f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{existing_field['field_id']}",
                        method="PUT",
                        payload={"field_name": field.name, "type": field.type, "property": {"options": merged}},
                    )
                    option_updates[field.name] = [item["name"] for item in merged]
            continue
        created_field = _create_field_with_fallback(client, app_token, table_id, field, apply=apply)
        if created_field:
            created_fields.append(field.name)
        current_fields[field.name] = created_field or {"field_name": field.name, "type": field.type}

    verified_fields = list_fields(client, app_token, table_id) if apply else []
    return {
        "table_name": spec.table_name,
        "table_id": table_id,
        "created": created,
        "created_fields": created_fields,
        "field_count": len(verified_fields) if apply else len(spec.fields),
        "status": "verified" if apply else "planned_create",
        "primary_field": primary_field_name,
        "option_updates": option_updates,
    }


def ensure_tables(client: FeishuBitableAPI, app_token: str, *, apply: bool) -> list[dict[str, Any]]:
    return [ensure_table(client, app_token, spec, apply=apply) for spec in TABLE_SPECS]


def write_registry(
    *,
    app_token: str,
    base_name: str,
    table_results: list[dict[str, Any]],
    output_path: Path = REGISTRY_PATH,
) -> dict[str, Any]:
    payload = {
        "app_token": app_token,
        "base_name": base_name,
        "wiki_node_token": WIKI_NODE_TOKEN,
        "base_link": TARGET_BASE_LINK,
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "created_by": "codex",
        "tables": {
            result["table_name"]: {
                "table_id": result["table_id"],
                "field_count": result["field_count"],
                "status": result["status"],
                "primary_field": result.get("primary_field", ""),
            }
            for result in table_results
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing registry: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def table_id_from_registry(registry: dict[str, Any], table_name: str) -> str:
    table = (registry.get("tables") or {}).get(table_name) or {}
    return str(table.get("table_id") or "").strip()


def _month_text_to_month_start_ms(month_text: str, year: int = 2025) -> int:
    text = str(month_text or "").strip()
    if not text:
        return 0
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return 0
    month = int(digits[:2] if len(digits) > 1 and int(digits[:2]) <= 12 else digits[0])
    dt = datetime(year, month, 1, tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _date_to_month_text(value: Any) -> str:
    if value in {None, ""}:
        return ""
    if isinstance(value, date):
        return f"{value.year:04d}-{value.month:02d}"
    text = str(value).strip()
    if not text:
        return ""
    if "-" in text and len(text) >= 7 and text[:4].isdigit():
        return text[:7]
    digits = "".join(ch for ch in text if ch.isdigit())
    if digits:
        month = int(digits[:2] if len(digits) > 1 and int(digits[:2]) <= 12 else digits[0])
        return f"2025-{month:02d}"
    return text


def _to_number(value: Any) -> int | float | None:
    if value in {"", None, "\\N"}:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip().replace(",", "")
    if not text or text in {"-", "—"}:
        return None
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return None


def _safe_text(value: Any, default: str = "") -> str:
    if value in {None, ""}:
        return default
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def _row_key(*parts: Any) -> str:
    return "|".join(_safe_text(part, "未知") or "未知" for part in parts)


def _as_month_ms_from_value(value: Any) -> int:
    if isinstance(value, date):
        return int(datetime(value.year, value.month, 1, tzinfo=timezone.utc).timestamp() * 1000)
    if isinstance(value, datetime):
        return int(datetime(value.year, value.month, 1, tzinfo=timezone.utc).timestamp() * 1000)
    return _month_text_to_month_start_ms(_safe_text(value))


def _iter_rows(path: Path, sheet_name: str) -> list[list[Any]]:
    wb = load_workbook(path)
    ws = wb.get_sheet_by_name(sheet_name)
    return list(ws.to_python())


def _normalize_month_label(text: Any) -> str:
    if isinstance(text, date):
        return f"{text.year:04d}-{text.month:02d}"
    value = _safe_text(text)
    if not value:
        return ""
    if value.endswith("月"):
        digits = "".join(ch for ch in value if ch.isdigit())
        if digits:
            return f"2025-{int(digits):02d}"
    if len(value) >= 7 and value[:4].isdigit():
        return value[:7]
    return value


def _group_monthly_finance_rows(rows: list[list[Any]]) -> list[dict[str, Any]]:
    header = rows[1]
    out: list[dict[str, Any]] = []
    current_month = ""
    current_source = ""
    for row in rows[2:]:
        month = _safe_text(row[0])
        source = _safe_text(row[1])
        port = _safe_text(row[2])
        if month:
            current_month = month
        if source:
            current_source = source
        if not current_month or not port:
            continue
        out.append(
            {
                "month": current_month,
                "source_channel": current_source or "合计",
                "port": port,
                "gmv": _to_number(row[3]) or 0,
                "total_orders": _to_number(row[4]) or 0,
                "cost": _to_number(row[5]) or 0,
                "effective_sales": _to_number(row[6]) or 0,
                "service_fee_income": _to_number(row[7]) or 0,
                "gross_margin": _to_number(row[8]) or 0,
                "platform_fee": _to_number(row[9]) or 0,
                "net_margin": _to_number(row[10]) if len(row) > 10 else None,
            }
        )
    return out


def _aggregate_order_rows(rows: list[list[Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    current_month = ""
    for row in rows[5:]:
        month = _safe_text(row[0])
        if month:
            current_month = month
        if not current_month:
            continue
        values = [_to_number(value) or 0 for value in row[1:9]]
        sz_fixed, sz_auction, sz_dc_fixed, sz_dc_auction, gd_fixed, gd_auction, gd_dc_fixed, gd_dc_auction = values
        out.extend(
            [
                {
                    "month": current_month,
                    "base": "苏州",
                    "source_channel": "寄售",
                    "port": "苏州",
                    "auction_orders": sz_auction,
                    "fixed_price_orders": sz_fixed,
                    "total_orders": sz_fixed + sz_auction,
                },
                {
                    "month": current_month,
                    "base": "苏州",
                    "source_channel": "大c",
                    "port": "苏州",
                    "auction_orders": sz_dc_auction,
                    "fixed_price_orders": sz_dc_fixed,
                    "total_orders": sz_dc_fixed + sz_dc_auction,
                },
                {
                    "month": current_month,
                    "base": "广东",
                    "source_channel": "寄售",
                    "port": "广东",
                    "auction_orders": gd_auction,
                    "fixed_price_orders": gd_fixed,
                    "total_orders": gd_fixed + gd_auction,
                },
                {
                    "month": current_month,
                    "base": "广东",
                    "source_channel": "大c",
                    "port": "广东",
                    "auction_orders": gd_dc_auction,
                    "fixed_price_orders": gd_dc_fixed,
                    "total_orders": gd_dc_fixed + gd_dc_auction,
                },
            ]
        )
    return out


def _load_sheet_map(path: Path, name: str) -> list[dict[str, Any]]:
    rows = _iter_rows(path, name)
    if name == "2.1、2.3 、2.6月度收入明细、毛利净利率":
        return _group_monthly_finance_rows(rows)
    if name == "2.2 、2.9成本结构明细":
        header = rows[1]
        out = []
        current_month = ""
        for row in rows[2:]:
            month = _safe_text(row[0])
            if month:
                current_month = month
            if not current_month:
                continue
            out.append(
                {
                    "month": current_month,
                    "metric_family": "成本",
                    "小程序投入成本": _to_number(row[1]) or 0,
                    "包装耗材": _to_number(row[2]) or 0,
                    "货品配饰": _to_number(row[3]) or 0,
                    "检测费": _to_number(row[4]) or 0,
                    "办公费": _to_number(row[5]) or 0,
                    "推广费": _to_number(row[6]) or 0,
                    "差旅费": _to_number(row[7]) or 0,
                    "服务费": _to_number(row[8]) or 0,
                    "平台费": _to_number(row[9]) or 0,
                    "招待费": _to_number(row[10]) or 0,
                    "福利费": _to_number(row[11]) or 0,
                    "工资及社保": _to_number(row[12]) or 0,
                    "房租水电": _to_number(row[13]) or 0,
                    "全年合计": _to_number(row[14]) or 0,
                }
            )
        return out
    return []


def build_phase1_rows() -> dict[str, list[dict[str, Any]]]:
    finance_income_rows = _load_sheet_map(FINANCE_PATH, "2.1、2.3 、2.6月度收入明细、毛利净利率")
    cost_rows = _load_sheet_map(FINANCE_PATH, "2.2 、2.9成本结构明细")
    cash_rows = _iter_rows(FINANCE_PATH, "2.4现金流量表")
    deposit_rows = _iter_rows(FINANCE_PATH, "2.7拍卖保证金沉淀")

    t01_rows: list[dict[str, Any]] = []
    for row in finance_income_rows:
        month = _normalize_month_label(row["month"])
        base = "苏州" if "苏州" in row.get("port", "") else "广东" if "广东" in row.get("port", "") else "合计"
        channel = row.get("source_channel") or "合计"
        record = {
            "record_key": _row_key("T01", month, base, channel, row.get("port")),
            "month": _as_month_ms_from_value(month),
            "base": base,
            "source_channel": channel,
            "port": row.get("port") or base,
            "gmv": row.get("gmv") or 0,
            "total_orders": row.get("total_orders") or 0,
            "auction_orders": row.get("auction_orders") or 0,
            "fixed_price_orders": row.get("fixed_price_orders") or 0,
            "effective_sales": row.get("effective_sales") or 0,
            "service_fee_income": row.get("service_fee_income") or 0,
            "cost": row.get("cost") or 0,
            "gross_margin": row.get("gross_margin") or 0,
            "platform_fee": row.get("platform_fee") or 0,
            "net_margin": row.get("net_margin") or 0,
            "sku_listed": 0,
            "sku_sold": 0,
            "items_received": 0,
            "items_rejected": 0,
            "active_sellers": 0,
            "new_customers": 0,
            "mau": 0,
            "stale_items_60d": 0,
            "auction_success_rate": 0,
            "avg_bid_rounds": 0,
            "inventory_turnover_days": 0,
            "daily_auth_capacity": 46,
            "notes": "源自财务尽调月度收入明细",
        }
        t01_rows.append(record)

    order_rows = _aggregate_order_rows(_iter_rows(DATA_STATS_PATH, "2.2-1月度订单量(拍卖单vs一口价单拆分)"))
    order_by_month_base_channel = {(_normalize_month_label(item["month"]), item["base"], item["source_channel"]): item for item in order_rows}
    for row in t01_rows:
        key = (_normalize_month_label(row["month"]), row["base"], row["source_channel"])
        order_data = order_by_month_base_channel.get(key, {})
        row.update(
            {
                "auction_orders": order_data.get("auction_orders", row["auction_orders"]),
                "fixed_price_orders": order_data.get("fixed_price_orders", row["fixed_price_orders"]),
                "total_orders": order_data.get("total_orders", row["total_orders"]),
            }
        )

    listing_rows = _iter_rows(DATA_STATS_PATH, "2.2-2商品上架数、上架转化率(上架一售出)")
    listing_metrics = {}
    for row in listing_rows[3:]:
        base = _safe_text(row[0])
        if not base:
            continue
        listing_metrics[base] = {
            "sku_listed": _to_number(row[1]) or 0,
        }
    for row in t01_rows:
        row["sku_listed"] = listing_metrics.get(row["base"], {}).get("sku_listed", row["sku_listed"])
        row["sku_sold"] = row["total_orders"]

    receipt_rows = _iter_rows(DATA_STATS_PATH, "2.4-1月度收货量(技术拉取)")
    receipt_month_base: dict[tuple[str, str], int] = defaultdict(int)
    category_totals: dict[str, int] = defaultdict(int)
    for row in receipt_rows[2:]:
        month = _normalize_month_label(row[0])
        base = "广东" if _safe_text(row[1]).strip() in {"翠玉珠宝", "陶瓷", "金工银器", "漆器"} else "苏州"
        qty = int(_to_number(row[3]) or 0)
        receipt_month_base[(month, base)] += qty
        category_totals[_safe_text(row[1])] += qty
    for row in t01_rows:
        month = _normalize_month_label(row["month"])
        row["items_received"] = receipt_month_base.get((month, row["base"]), 0)

    rejection_rows = _iter_rows(DATA_STATS_PATH, "2.4-2不通过原因统计及状态占比(技术拉取）")
    rejected_by_month = defaultdict(int)
    for row in rejection_rows[1:]:
        month = _normalize_month_label(row[0])
        rejected_by_month[month] += int(_to_number(row[2]) or 0)
    for row in t01_rows:
        row["items_rejected"] = rejected_by_month.get(_normalize_month_label(row["month"]), 0)

    sellers_rows = _iter_rows(DATA_STATS_PATH, "2.4-7寄售卖家(技术拉取)")
    sellers_by_month = { _normalize_month_label(row[0]): int(_to_number(row[2]) or 0) for row in sellers_rows[1:] if _safe_text(row[0]) }
    for row in t01_rows:
        row["active_sellers"] = sellers_by_month.get(_normalize_month_label(row["month"]), row["active_sellers"])

    acquisition_rows = _iter_rows(DATA_STATS_PATH, "2.5-2新客获取数获客渠道来源(小红书抖音视频号私域")
    new_customers_by_month = defaultdict(int)
    for row in acquisition_rows[2:]:
        channel = _safe_text(row[0])
        if not channel or channel == "小回":
            continue
        for idx, month_label in enumerate(acquisition_rows[0][1:], 1):
            month = _normalize_month_label(month_label)
            new_customers_by_month[month] += int(_to_number(row[idx]) or 0)
    for row in t01_rows:
        row["new_customers"] = new_customers_by_month.get(_normalize_month_label(row["month"]), 0)

    mau_rows = _iter_rows(DATA_STATS_PATH, "2.2-9小程序DAU、MAU")
    mau_by_month = {}
    for row in mau_rows[2:]:
        month = _normalize_month_label(row[0])
        if month:
            mau_by_month[month] = int(_to_number(row[2]) or 0)
    for row in t01_rows:
        row["mau"] = mau_by_month.get(_normalize_month_label(row["month"]), row["mau"])

    stale_rows = _iter_rows(DATA_STATS_PATH, "2.2-8滞销商品(技术拉取)")
    stale_by_month = defaultdict(int)
    for row in stale_rows[1:]:
        month = _normalize_month_label(row[0])
        if month:
            stale_by_month[month] += int(_to_number(row[3]) or 0)
    for row in t01_rows:
        row["stale_items_60d"] = stale_by_month.get(_normalize_month_label(row["month"]), 0)

    auction_rows = _iter_rows(DATA_STATS_PATH, "2.2-6拍卖场次(技术拉取)")
    auction_by_month = {}
    for row in auction_rows[2:]:
        month = _normalize_month_label(row[0])
        if not month:
            continue
        auction_by_month[month] = {
            "auction_success_rate": _to_number(row[3]) or 0,
            "avg_bid_rounds": _to_number(row[4]) or 0,
        }
    for row in t01_rows:
        metrics = auction_by_month.get(_normalize_month_label(row["month"]), {})
        row["auction_success_rate"] = metrics.get("auction_success_rate", 0)
        row["avg_bid_rounds"] = metrics.get("avg_bid_rounds", 0)

    t01_rows = sorted(t01_rows, key=lambda item: (item["month"], item["base"], item["source_channel"]))

    t02_rows: list[dict[str, Any]] = []
    cost_by_month = { _normalize_month_label(row["month"]): row for row in cost_rows[2:] if _safe_text(row["month"]) }
    cash_months = ["3月金额", "4月金额", "5月金额", "6月金额", "7月金额", "8月金额", "9月金额", "10月金额", "11月金额", "12月金额"]
    cash_metric_rows = { _safe_text(row[0]).strip(): row for row in cash_rows[4:] if _safe_text(row[0]).strip() }
    for month in sorted({ _normalize_month_label(row["month"]) for row in t01_rows if _normalize_month_label(row["month"]) }):
        cost_row = cost_by_month.get(month.replace("-", "月")) or cost_by_month.get(month)
        if not cost_row:
            continue
        month_key = month
        finance_row = next((row for row in finance_income_rows if _normalize_month_label(row["month"]) == month_key and row.get("source_channel") == "线上"), None)
        total_revenue = sum(item["service_fee_income"] for item in t01_rows if _normalize_month_label(item["month"]) == month_key)
        opex = _to_number(cost_row.get("全年合计")) or 0
        revenue_commission = total_revenue
        cash_inflow = 0.0
        cash_outflow = 0.0
        if cash_metric_rows:
            sales_row = cash_rows[4]
            outflow_row = cash_rows[9]
            cash_inflow = sum(_to_number(value) or 0 for value in sales_row[4:14] if value not in {"", None})
            cash_outflow = sum(_to_number(value) or 0 for value in outflow_row[4:14] if value not in {"", None})
        t02_rows.append(
            {
                "record_key": _row_key("T02", month_key),
                "month": _as_month_ms_from_value(month_key),
                "revenue_commission": revenue_commission,
                "revenue_membership": 0,
                "revenue_ip_content": 0,
                "revenue_other": 0,
                "cost_salary": _to_number(cost_row.get("工资及社保")) or 0,
                "cost_rent": _to_number(cost_row.get("房租水电")) or 0,
                "cost_tech": _to_number(cost_row.get("小程序投入成本")) or 0,
                "cost_logistics": 0,
                "cost_marketing": _to_number(cost_row.get("推广费")) or 0,
                "cost_auth": _to_number(cost_row.get("检测费")) or 0,
                "cost_travel": _to_number(cost_row.get("差旅费")) or 0,
                "cost_platform_fee": _to_number(cost_row.get("平台费")) or 0,
                "cost_other": sum(_to_number(cost_row.get(col)) or 0 for col in ("包装耗材", "货品配饰", "办公费", "服务费", "招待费", "福利费")),
                "cash_inflow_operations": cash_inflow,
                "cash_outflow_operations": cash_outflow,
                "borrowings": 0,
                "cash_balance": 0,
                "headcount": 0,
                "auth_team_size": 23,
                "notes": "源自财务尽调月度成本与现金流量表",
            }
        )
    t02_rows = sorted(t02_rows, key=lambda item: item["month"])

    t03_rows: list[dict[str, Any]] = []
    customer_rows = _iter_rows(DATA_STATS_PATH, "2.5-1客户分层统计")
    for row in customer_rows[3:]:
        month = _normalize_month_label(row[0])
        label = _safe_text(row[1])
        if not month or not label:
            continue
        t03_rows.append(
            {
                "record_key": _row_key("T03", month, "客户分层", label),
                "month": _as_month_ms_from_value(month),
                "analysis_type": "客户分层",
                "segment": label,
                "channel": "合计",
                "customer_count": _to_number(row[2]) or 0,
                "contribution_amount": _to_number(row[3]) or 0,
                "contribution_share": _to_number(row[4]) or 0,
                "repeat_rate": 0,
                "repeat_interval_days": 0,
                "ltv": 0,
                "registered_members": 0,
                "paying_members": 0,
                "first_order_conversion": 0,
                "churn_customers_90d": 0,
                "churn_rate_90d": 0,
                "avg_order_value": 0,
                "active_customers": 0,
                "new_customers": 0,
                "source_sheet": "2.5-1客户分层统计",
                "source_metric": "客户分层",
                "source_row_key": label,
                "notes": "",
            }
        )

    tech_rows = _iter_rows(DATA_STATS_PATH, "2.5-1客户分层统计(技术拉取)")
    if tech_rows:
        t03_rows.append(
            {
                "record_key": _row_key("T03", "2025-03", "客户分层", "全量"),
                "month": _as_month_ms_from_value("2025-03"),
                "analysis_type": "客户分层",
                "segment": "全量",
                "channel": "合计",
                "customer_count": 19 + 253 + 1632,
                "contribution_amount": 6606926,
                "contribution_share": 39.84,
                "repeat_rate": 0,
                "repeat_interval_days": 0,
                "ltv": 0,
                "registered_members": 0,
                "paying_members": 0,
                "first_order_conversion": 0,
                "churn_customers_90d": 0,
                "churn_rate_90d": 0,
                "avg_order_value": 0,
                "active_customers": 0,
                "new_customers": 0,
                "source_sheet": "2.5-1客户分层统计(技术拉取)",
                "source_metric": "客户分层",
                "source_row_key": "技术拉取总览",
                "notes": "",
            }
        )

    repeat_rows = _iter_rows(DATA_STATS_PATH, "2.5-3客户复购率")
    for row in repeat_rows[1:]:
        month = _normalize_month_label(row[0])
        if not month:
            continue
        t03_rows.append(
            {
                "record_key": _row_key("T03", month, "复购率", "全量"),
                "month": _as_month_ms_from_value(month),
                "analysis_type": "复购率",
                "segment": "全量",
                "channel": "合计",
                "customer_count": 0,
                "contribution_amount": 0,
                "contribution_share": 0,
                "repeat_rate": _to_number(row[2]) or 0,
                "repeat_interval_days": 0,
                "ltv": 0,
                "registered_members": 0,
                "paying_members": 0,
                "first_order_conversion": 0,
                "churn_customers_90d": 0,
                "churn_rate_90d": 0,
                "avg_order_value": 0,
                "active_customers": 0,
                "new_customers": 0,
                "source_sheet": "2.5-3客户复购率",
                "source_metric": "复购率",
                "source_row_key": month,
                "notes": "",
            }
        )

    ltv_rows = _iter_rows(DATA_STATS_PATH, "2.5-4客户生命周期价值")
    if ltv_rows:
        t03_rows.append(
            {
                "record_key": _row_key("T03", "2025-05", "生命周期价值", "全量"),
                "month": _as_month_ms_from_value("2025-05"),
                "analysis_type": "生命周期价值",
                "segment": "全量",
                "channel": "合计",
                "customer_count": 0,
                "contribution_amount": 0,
                "contribution_share": 0,
                "repeat_rate": 0,
                "repeat_interval_days": 0,
                "ltv": _to_number(ltv_rows[2][3]) or 0,
                "registered_members": _to_number(ltv_rows[2][2]) or 0,
                "paying_members": _to_number(ltv_rows[2][3]) or 0,
                "first_order_conversion": _to_number(ltv_rows[2][4]) or 0,
                "churn_customers_90d": 0,
                "churn_rate_90d": 0,
                "avg_order_value": 0,
                "active_customers": 0,
                "new_customers": 0,
                "source_sheet": "2.5-4客户生命周期价值",
                "source_metric": "生命周期价值",
                "source_row_key": "注册与支付转化",
                "notes": "",
            }
        )

    churn_rows = _iter_rows(DATA_STATS_PATH, "2.5-5客户流失率")
    for row in churn_rows[1:]:
        month = _normalize_month_label(row[0])
        if not month:
            continue
        t03_rows.append(
            {
                "record_key": _row_key("T03", month, "流失率", "全量"),
                "month": _as_month_ms_from_value(month),
                "analysis_type": "流失率",
                "segment": "全量",
                "channel": "合计",
                "customer_count": 0,
                "contribution_amount": 0,
                "contribution_share": 0,
                "repeat_rate": 0,
                "repeat_interval_days": 0,
                "ltv": 0,
                "registered_members": 0,
                "paying_members": 0,
                "first_order_conversion": 0,
                "churn_customers_90d": _to_number(row[1]) or 0,
                "churn_rate_90d": _to_number(row[2]) or 0,
                "avg_order_value": 0,
                "active_customers": 0,
                "new_customers": 0,
                "source_sheet": "2.5-5客户流失率",
                "source_metric": "流失率",
                "source_row_key": month,
                "notes": "",
            }
        )

    member_rows = _iter_rows(DATA_STATS_PATH, "2.5-7会员转化量(技术拉取)")
    for row in member_rows[1:]:
        month = _normalize_month_label(row[0])
        if not month:
            continue
        t03_rows.append(
            {
                "record_key": _row_key("T03", month, "会员转化", "全量"),
                "month": _as_month_ms_from_value(month),
                "analysis_type": "会员转化",
                "segment": "全量",
                "channel": "合计",
                "customer_count": 0,
                "contribution_amount": 0,
                "contribution_share": 0,
                "repeat_rate": 0,
                "repeat_interval_days": 0,
                "ltv": 0,
                "registered_members": _to_number(row[1]) or 0,
                "paying_members": _to_number(row[2]) or 0,
                "first_order_conversion": _to_number(row[3]) or 0,
                "churn_customers_90d": 0,
                "churn_rate_90d": 0,
                "avg_order_value": 0,
                "active_customers": 0,
                "new_customers": 0,
                "source_sheet": "2.5-7会员转化量(技术拉取)",
                "source_metric": "会员转化",
                "source_row_key": month,
                "notes": "",
            }
        )

    channel_rows = _iter_rows(DATA_STATS_PATH, "2.5-2新客获取数获客渠道来源(小红书抖音视频号私域")
    if channel_rows:
        month_labels = [label for label in channel_rows[0][1:] if _safe_text(label)]
        for row in channel_rows[2:]:
            channel = _safe_text(row[0])
            if not channel or channel == "小回":
                continue
            for idx, month_label in enumerate(month_labels, 1):
                month = _normalize_month_label(month_label)
                t03_rows.append(
                    {
                        "record_key": _row_key("T03", month, "获客渠道", channel),
                        "month": _as_month_ms_from_value(month),
                        "analysis_type": "获客渠道",
                        "segment": "全量",
                        "channel": channel,
                        "customer_count": 0,
                        "contribution_amount": 0,
                        "contribution_share": 0,
                        "repeat_rate": 0,
                        "repeat_interval_days": 0,
                        "ltv": 0,
                        "registered_members": 0,
                        "paying_members": 0,
                        "first_order_conversion": 0,
                        "churn_customers_90d": 0,
                        "churn_rate_90d": 0,
                        "avg_order_value": 0,
                        "active_customers": 0,
                        "new_customers": _to_number(row[idx]) or 0,
                        "source_sheet": "2.5-2新客获取数获客渠道来源(小红书抖音视频号私域",
                        "source_metric": "获客渠道",
                        "source_row_key": f"{channel}:{month}",
                        "notes": "",
                    }
                )

    t03_rows = sorted(t03_rows, key=lambda item: (item["month"], item["analysis_type"], item["segment"], item["channel"]))

    receipt_by_month_category = defaultdict(int)
    receipt_rows = _iter_rows(DATA_STATS_PATH, "2.4-1月度收货量(技术拉取)")
    for row in receipt_rows[2:]:
        month = _normalize_month_label(row[0])
        category = _safe_text(row[1])
        qty = int(_to_number(row[3]) or 0)
        if month and category:
            receipt_by_month_category[(month, category)] += qty
    t04_rows: list[dict[str, Any]] = []
    for (month, category), qty in sorted(receipt_by_month_category.items()):
        t04_rows.append(
            {
                "record_key": _row_key("T04", month, category),
                "month": _as_month_ms_from_value(month),
                "analysis_type": "收货结构",
                "category": category,
                "subcategory": "合计",
                "base": "未知",
                "received_count": qty,
                "listed_count": 0,
                "sold_count": 0,
                "return_count": 0,
                "sell_through_rate": 0,
                "listing_conversion_rate": 0,
                "inventory_turnover_days": 0,
                "appraisal_count": 0,
                "rejection_count": 0,
                "gross_margin": 0,
                "share_of_total": 0,
                "growth_rate": 0,
                "source_sheet": "2.4-1月度收货量(技术拉取)",
                "source_metric": "签收数量",
                "source_row_key": f"{month}:{category}",
                "notes": "",
            }
        )

    sell_rows = _iter_rows(DATA_STATS_PATH, "2.2-2商品上架数、上架转化率(上架一售出)")
    for row in sell_rows[3:]:
        base = _safe_text(row[0])
        if not base:
            continue
        t04_rows.append(
            {
                "record_key": _row_key("T04", "2025-03", base, "上架"),
                "month": _as_month_ms_from_value("2025-03"),
                "analysis_type": "上架结构",
                "category": "合计",
                "subcategory": "合计",
                "base": base,
                "received_count": 0,
                "listed_count": _to_number(row[1]) or 0,
                "sold_count": 0,
                "return_count": 0,
                "sell_through_rate": _to_number(row[3]) or 0,
                "listing_conversion_rate": _to_number(row[3]) or 0,
                "inventory_turnover_days": 0,
                "appraisal_count": 0,
                "rejection_count": 0,
                "gross_margin": 0,
                "share_of_total": _to_number(row[2]) or 0,
                "growth_rate": 0,
                "source_sheet": "2.2-2商品上架数、上架转化率(上架一售出)",
                "source_metric": "上架商品数/上架转化率",
                "source_row_key": base,
                "notes": "",
            }
        )
    t04_rows = sorted(t04_rows, key=lambda item: (item["month"], item["analysis_type"], item["category"], item["base"]))

    t05_rows: list[dict[str, Any]] = []
    logistics_rows = _iter_rows(DATA_STATS_PATH, "2.4-4物流成本明细(收货发货按物流商分)及平均单票物流")
    for row in logistics_rows[1:]:
        month = _normalize_month_label(row[0])
        if not month:
            continue
        t05_rows.append(
            {
                "record_key": _row_key("T05", month, row[1], row[2]),
                "month": _as_month_ms_from_value(month),
                "metric_family": "物流",
                "base": "合计",
                "logistics_partner": _safe_text(row[2]),
                "product_category": "合计",
                "tickets_inbound": _to_number(row[3]) or 0,
                "tickets_outbound": 0,
                "total_tickets": _to_number(row[3]) or 0,
                "total_cost": _to_number(row[4]) or 0,
                "avg_ticket_cost": _to_number(row[5]) or 0,
                "avg_sop_hours": 0,
                "turnover_days": 0,
                "rejection_count": 0,
                "rejection_rate": 0,
                "warehouse_cycle_days": 0,
                "avg_receipt_days": 0,
                "avg_listing_days": 0,
                "bottleneck_type": "物流",
                "source_sheet": "2.4-4物流成本明细(收货发货按物流商分)及平均单票物流",
                "source_metric": "物流总成本",
                "source_row_key": f"{month}:{row[1]}:{row[2]}",
                "notes": _safe_text(row[6]),
            }
        )
    sop_rows = _iter_rows(DATA_STATS_PATH, "2.4-8上架SOP执行效率(单件商品从入库到上架的平均工时)")
    for row in sop_rows[1:]:
        month = _normalize_month_label(row[0])
        if not month:
            continue
        t05_rows.append(
            {
                "record_key": _row_key("T05", month, "SOP", _safe_text(row[1])),
                "month": _as_month_ms_from_value(month),
                "metric_family": "上架SOP",
                "base": "未知",
                "logistics_partner": "",
                "product_category": _safe_text(row[1]),
                "tickets_inbound": 0,
                "tickets_outbound": 0,
                "total_tickets": 0,
                "total_cost": 0,
                "avg_ticket_cost": 0,
                "avg_sop_hours": _to_number(row[2]) or 0,
                "turnover_days": 0,
                "rejection_count": 0,
                "rejection_rate": 0,
                "warehouse_cycle_days": 0,
                "avg_receipt_days": 0,
                "avg_listing_days": 0,
                "bottleneck_type": "仓储",
                "source_sheet": "2.4-8上架SOP执行效率(单件商品从入库到上架的平均工时)",
                "source_metric": "平均工时",
                "source_row_key": f"{month}:{_safe_text(row[1])}",
                "notes": "",
            }
        )
    turnover_rows = _iter_rows(DATA_STATS_PATH, "2.2-3SKU库存周转天数(从入库到售出的平均天数)")
    for row in turnover_rows[1:]:
        category = _safe_text(row[0])
        if not category:
            continue
        t05_rows.append(
            {
                "record_key": _row_key("T05", "2025-03", "库存周转", category),
                "month": _as_month_ms_from_value("2025-03"),
                "metric_family": "库存周转",
                "base": "合计",
                "logistics_partner": "",
                "product_category": category,
                "tickets_inbound": 0,
                "tickets_outbound": 0,
                "total_tickets": 0,
                "total_cost": 0,
                "avg_ticket_cost": 0,
                "avg_sop_hours": 0,
                "turnover_days": _to_number(row[1]) or 0,
                "rejection_count": 0,
                "rejection_rate": 0,
                "warehouse_cycle_days": _to_number(row[1]) or 0,
                "avg_receipt_days": 0,
                "avg_listing_days": 0,
                "bottleneck_type": "仓储",
                "source_sheet": "2.2-3SKU库存周转天数(从入库到售出的平均天数)",
                "source_metric": "周转天数",
                "source_row_key": category,
                "notes": "",
            }
        )
    t05_rows = sorted(t05_rows, key=lambda item: (item["month"], item["metric_family"], item["product_category"]))

    t06_rows: list[dict[str, Any]] = []
    content_rows = _iter_rows(DATA_STATS_PATH, "各平台粉丝量及增长趋势(视频号抖音小红书矩阵号)")
    for row in content_rows[1:]:
        platform = _safe_text(row[0])
        if not platform:
            continue
        period = _safe_text(row[1])
        t06_rows.append(
            {
                "record_key": _row_key("T06", platform, period),
                "month": _as_month_ms_from_value("2025-03"),
                "channel": platform,
                "platform": platform,
                "content_type": "内容发布",
                "metric_family": "发布",
                "publish_count": _to_number(row[2]) or 0,
                "live_sessions": 0,
                "avg_viewers": _to_number(row[3]) or 0,
                "plays": _to_number(row[4]) or 0,
                "engagement_count": (_to_number(row[5]) or 0) + (_to_number(row[6]) or 0) + (_to_number(row[7]) or 0),
                "gmv": 0,
                "conversion_rate": 0,
                "ad_spend": 0,
                "roi": 0,
                "followers": _to_number(row[4]) or 0,
                "followers_growth": 0,
                "content_theme": "",
                "source_sheet": "各平台粉丝量及增长趋势(视频号抖音小红书矩阵号)",
                "source_metric": "发布与互动",
                "source_row_key": f"{platform}:{period}",
                "notes": period,
            }
        )
    live_rows = _iter_rows(DATA_STATS_PATH, "直播场次、场均观看人数、场均成交额、直播引流到小程序转化率")
    for row in live_rows[1:]:
        metric = _safe_text(row[0])
        if not metric:
            continue
        t06_rows.append(
            {
                "record_key": _row_key("T06", "直播", metric),
                "month": _as_month_ms_from_value("2025-03"),
                "channel": "直播",
                "platform": "视频号",
                "content_type": "直播",
                "metric_family": "转化",
                "publish_count": 0,
                "live_sessions": 1 if metric == "直播场次" else 0,
                "avg_viewers": _to_number(row[1]) or 0,
                "plays": 0,
                "engagement_count": 0,
                "gmv": 0,
                "conversion_rate": _to_number(row[1]) or 0,
                "ad_spend": 0,
                "roi": 0,
                "followers": 0,
                "followers_growth": 0,
                "content_theme": "",
                "source_sheet": "直播场次、场均观看人数、场均成交额、直播引流到小程序转化率",
                "source_metric": metric,
                "source_row_key": metric,
                "notes": _safe_text(row[2]),
            }
        )
    ip_rows = _iter_rows(DATA_STATS_PATH, "杨老师IP内容vs品类专家IP内容的流量与转化对比")
    for row in ip_rows[1:]:
        metric = _safe_text(row[0])
        if not metric:
            continue
        t06_rows.append(
            {
                "record_key": _row_key("T06", "IP对比", metric),
                "month": _as_month_ms_from_value("2025-03"),
                "channel": "合计",
                "platform": "视频号",
                "content_type": "IP内容",
                "metric_family": "互动",
                "publish_count": _to_number(row[1]) or 0,
                "live_sessions": 0,
                "avg_viewers": _to_number(row[2]) or 0,
                "plays": _to_number(row[3]) or 0,
                "engagement_count": (_to_number(row[4]) or 0) + (_to_number(row[5]) or 0) + (_to_number(row[6]) or 0),
                "gmv": 0,
                "conversion_rate": 0,
                "ad_spend": 0,
                "roi": 0,
                "followers": 0,
                "followers_growth": 0,
                "content_theme": "杨老师 vs 品类专家",
                "source_sheet": "杨老师IP内容vs品类专家IP内容的流量与转化对比",
                "source_metric": metric,
                "source_row_key": metric,
                "notes": "",
            }
        )
   投放_rows = _iter_rows(DATA_STATS_PATH, "内容投放")
    for row in 投放_rows[1:]:
        order_id = _safe_text(row[0])
        if not order_id:
            continue
        t06_rows.append(
            {
                "record_key": _row_key("T06", "投放", order_id),
                "month": _as_month_ms_from_value("2025-03"),
                "channel": "投放",
                "platform": "公众号",
                "content_type": "付费投放",
                "metric_family": "投放",
                "publish_count": 0,
                "live_sessions": 0,
                "avg_viewers": 0,
                "plays": _to_number(row[2]) or 0,
                "engagement_count": _to_number(row[3]) or 0,
                "gmv": _to_number(row[4]) or 0,
                "conversion_rate": 0,
                "ad_spend": _to_number(row[1]) or 0,
                "roi": _to_number(row[5]) or 0,
                "followers": 0,
                "followers_growth": 0,
                "content_theme": "",
                "source_sheet": "内容投放",
                "source_metric": "投放记录",
                "source_row_key": order_id,
                "notes": _safe_text(row[7]),
            }
        )
    t06_rows = sorted(t06_rows, key=lambda item: (item["channel"], item["content_type"], item["record_key"]))

    t07_rows = [
        {
            "record_key": _row_key("T07", row["scenario"], row["year"]),
            "scenario": row["scenario"],
            "year": row["year"],
            "annual_gmv": row["annual_gmv"],
            "annual_revenue": row["annual_revenue"],
            "rev_commission": row["rev_commission"],
            "rev_ip_content": row["rev_ip_content"],
            "rev_membership": row["rev_membership"],
            "rev_data_ad": row["rev_data_ad"],
            "annual_opex": row["annual_opex"],
            "total_orders": row["total_orders"],
            "monthly_sku_needed": row["monthly_sku_needed"],
            "monthly_sellers_needed": row["monthly_sellers_needed"],
            "take_rate": round((row["annual_revenue"] / row["annual_gmv"]) * 100, 2) if row["annual_gmv"] else 0,
            "revenue_margin": round((row["annual_revenue"] - row["annual_opex"]) / row["annual_revenue"], 4) if row["annual_revenue"] else 0,
            "opex_ratio": round(row["annual_opex"] / row["annual_revenue"], 4) if row["annual_revenue"] else 0,
            "revenue_per_order": round(row["annual_revenue"] / row["total_orders"], 2) if row["total_orders"] else 0,
            "assumptions_note": row["assumptions_note"],
            "source_version": "TS-BRM-03",
        }
        for row in [
            {"scenario": "实际", "year": "2025", "annual_gmv": 18107963, "annual_revenue": 2979750, "rev_commission": 2979750, "rev_ip_content": 0, "rev_membership": 0, "rev_data_ad": 0, "annual_opex": 1874592, "total_orders": 8479, "monthly_sku_needed": 1746, "monthly_sellers_needed": 200, "assumptions_note": "2025年5-12月实际运营数据（8个月）"},
            {"scenario": "保底", "year": "2026", "annual_gmv": 60000000, "annual_revenue": 15700000, "rev_commission": 13200000, "rev_ip_content": 1000000, "rev_membership": 500000, "rev_data_ad": 0, "annual_opex": 6000000, "total_orders": 31579, "monthly_sku_needed": 4386, "monthly_sellers_needed": 500, "assumptions_note": "核心假设：鉴定产能4倍扩容+卖家扩至500人+品类扩张"},
            {"scenario": "挑战", "year": "2026", "annual_gmv": 100000000, "annual_revenue": 26200000, "rev_commission": 22000000, "rev_ip_content": 2000000, "rev_membership": 1200000, "rev_data_ad": 0, "annual_opex": 8000000, "total_orders": 52632, "monthly_sku_needed": 7310, "monthly_sellers_needed": 800, "assumptions_note": "需全面突破：AI鉴定+融资+苏州展仓+IP全面变现"},
            {"scenario": "保守", "year": "2026", "annual_gmv": 30000000, "annual_revenue": 7850000, "rev_commission": 6600000, "rev_ip_content": 500000, "rev_membership": 250000, "rev_data_ad": 0, "annual_opex": 4000000, "total_orders": 15789, "monthly_sku_needed": 2193, "monthly_sellers_needed": 300, "assumptions_note": "仅解决鉴定瓶颈，其他维度渐进提升"},
            {"scenario": "保底", "year": "2027", "annual_gmv": 150000000, "annual_revenue": 41000000, "rev_commission": 30000000, "rev_ip_content": 5000000, "rev_membership": 2000000, "rev_data_ad": 1000000, "annual_opex": 12000000, "total_orders": 78947, "monthly_sku_needed": 10965, "monthly_sellers_needed": 1200, "assumptions_note": "品类扩张+苏州展仓+千匠守艺海外启动"},
            {"scenario": "保底", "year": "2028", "annual_gmv": 300000000, "annual_revenue": 85000000, "rev_commission": 55000000, "rev_ip_content": 12000000, "rev_membership": 8000000, "rev_data_ad": 5000000, "annual_opex": 20000000, "total_orders": 157895, "monthly_sku_needed": 21930, "monthly_sellers_needed": 3000, "assumptions_note": "平台化+国际化+IP生态全面成熟"},
        ]
    ]

    t08_rows = []
    for idx, row in enumerate(
        [
            {"company": "回旋镖局", "country": "中国", "model_type": "C2B2C寄售", "data_year": "2025", "gmv": 1811, "revenue": 298, "take_rate": 22.3, "gross_margin": 98.9, "ebitda_margin": 36.0, "headcount": 30, "auth_team_size": 23, "active_buyers": 2016, "active_sellers": 212, "category_count": 8, "countries_served": 1, "ai_capability": "无", "funding_total": 0, "latest_valuation": 0, "key_strength": "杨老师IP（近3亿播放）+首年盈利+入仓鉴定信任模式", "key_weakness": "鉴定产能受限+品类单一+技术基础薄弱", "lesson_for_boomerang": "自身基线数据"},
            {"company": "TheRealReal", "country": "美国", "model_type": "C2B2C寄售", "data_year": "2024", "gmv": 1281300, "revenue": 420000, "take_rate": 33.0, "gross_margin": 74.5, "ebitda_margin": 1.6, "headcount": 3011, "auth_team_size": 500, "active_buyers": 972000, "active_sellers": 0, "category_count": 50, "countries_served": 10, "ai_capability": "定价,推荐", "funding_total": 210000, "latest_valuation": 350000, "key_strength": "全球最大奢侈品寄售平台+强鉴定团队+品牌认知", "key_weakness": "烧了10年才盈利+利润率极低+重资产模式", "lesson_for_boomerang": "回旋镖局的精益模式效率远超TRR；Sales Professional模式值得借鉴"},
            {"company": "Catawiki", "country": "荷兰", "model_type": "专家策展拍卖", "data_year": "2024", "gmv": 35000, "revenue": 7000, "take_rate": 20.0, "gross_margin": 65.0, "ebitda_margin": 5.0, "headcount": 600, "auth_team_size": 240, "active_buyers": 0, "active_sellers": 0, "category_count": 80, "countries_served": 60, "ai_capability": "推荐", "funding_total": 28000, "latest_valuation": 425000, "key_strength": "240专家策展+80品类+全球60国+拍卖+Buy Now混合", "key_weakness": "无创始人IP+品类深度不如垂直平台", "lesson_for_boomerang": "最接近的进化终态对标；专家策展+主题拍卖模式可直接借鉴"},
            {"company": "微拍堂", "country": "中国", "model_type": "B2C平台", "data_year": "2021", "gmv": 28350000, "revenue": 68460, "take_rate": 2.4, "gross_margin": 60.0, "ebitda_margin": 14.5, "headcount": 1000, "auth_team_size": 0, "active_buyers": 3900000, "active_sellers": 78000, "category_count": 8, "countries_served": 1, "ai_capability": "鉴定", "funding_total": 14000, "latest_valuation": 0, "key_strength": "国内最大文玩垂直平台+GMV规模巨大+腾讯/IDG投资", "key_weakness": "假货泛滥+不入仓不鉴定+品牌信任缺失", "lesson_for_boomerang": "回旋镖局的入仓鉴定模式正是微拍堂最大的短板；证明了文玩市场规模（千亿级）"},
            {"company": "Mercari", "country": "日本", "model_type": "C2C综合", "data_year": "2024", "gmv": 700000, "revenue": 225400, "take_rate": 10.0, "gross_margin": 39.0, "ebitda_margin": 15.0, "headcount": 2000, "auth_team_size": 0, "active_buyers": 23000000, "active_sellers": 0, "category_count": 100, "countries_served": 3, "ai_capability": "推荐", "funding_total": 52500, "latest_valuation": 1400000, "key_strength": "日本最大C2C平台+极简上架体验+跨境能力", "key_weakness": "非垂直平台+无专业鉴定+非标品深度不足", "lesson_for_boomerang": "极简上架体验（1分钟上架）和跨境模式值得借鉴"},
            {"company": "1stDibs", "country": "美国", "model_type": "B2C策展", "data_year": "2024", "gmv": 35000, "revenue": 5950, "take_rate": 17.0, "gross_margin": 70.0, "ebitda_margin": -10.0, "headcount": 400, "auth_team_size": 50, "active_buyers": 0, "active_sellers": 5000, "category_count": 30, "countries_served": 20, "ai_capability": "推荐", "funding_total": 70000, "latest_valuation": 21000, "key_strength": "高端定位+全球经销商网络+艺术品细分", "key_weakness": "持续亏损+高端市场天花板明显", "lesson_for_boomerang": "高端策展模式的定位参考；证明了高Take Rate（17%）在艺术品领域可行"},
            {"company": "Heritage Auctions", "country": "美国", "model_type": "传统+线上拍卖", "data_year": "2024", "gmv": 1050000, "revenue": 0, "take_rate": 0, "gross_margin": 0, "ebitda_margin": 0, "headcount": 500, "auth_team_size": 130, "active_buyers": 0, "active_sellers": 0, "category_count": 40, "countries_served": 5, "ai_capability": "无", "funding_total": 0, "latest_valuation": 0, "key_strength": "美国最大收藏品拍卖行+130专家+品类深度极致", "key_weakness": "传统拍卖模式+门槛高+数字化程度有限", "lesson_for_boomerang": "品类极致细分和专家深度是长期竞争力；拍卖作为核心交易机制的验证"},
            {"company": "玩物得志", "country": "中国", "model_type": "直播+鉴定", "data_year": "2021", "gmv": 2835000, "revenue": 0, "take_rate": 0, "gross_margin": 0, "ebitda_margin": 0, "headcount": 500, "auth_team_size": 0, "active_buyers": 5820000, "active_sellers": 0, "category_count": 8, "countries_served": 1, "ai_capability": "无", "funding_total": 7000, "latest_valuation": 0, "key_strength": "月活最大（582万）+快速融资+直播创新", "key_weakness": "投诉量最高（4993条）+假货问题严重", "lesson_for_boomerang": "直播获客效率高但信任成本也高；回旋镖局应避免走流量优先的路线"},
        ]
    ):
        t08_rows.append(
            {
                "record_key": _row_key("T08", idx + 1, row["company"]),
                **row,
                "benchmark_rank": idx + 1,
                "source_note": "TS-BRM-03",
            }
        )

    t09_rows = [
        {
            "record_key": _row_key("T09", row["initiative_id"]),
            "initiative_id": row["initiative_id"],
            "dimension": row["dimension"],
            "initiative_name": row["initiative_name"],
            "priority": row["priority"],
            "target_quarter": row["target_quarter"],
            "status": row["status"],
            "estimated_investment": row["estimated_investment"],
            "expected_revenue_impact": row["expected_revenue_impact"],
            "benchmark_ref": row["benchmark_ref"],
            "kpi_metric": row["kpi_metric"],
            "kpi_current": row["kpi_current"],
            "kpi_target": row["kpi_target"],
            "owner": row.get("owner", ""),
            "dependency": row.get("dependency", ""),
            "initiative_type": row.get("initiative_type", ""),
            "roi_estimate": row.get("roi_estimate", 0),
            "payback_months": row.get("payback_months", 0),
            "risk_level": row.get("risk_level", "中"),
            "is_key_path": row.get("is_key_path", "是"),
            "strategic_theme": row.get("strategic_theme", ""),
            "action_stage": row.get("action_stage", ""),
            "source_note": "TS-BRM-03",
        }
        for row in [
            {"initiative_id": "D1-AI-01", "dimension": "D1信任基础设施", "initiative_name": "AI鉴定MVP（翡翠品类）", "priority": "P0关键路径", "target_quarter": "2026Q1", "status": "待启动", "estimated_investment": 300000, "expected_revenue_impact": 5000000, "benchmark_ref": "微拍堂2024上线AI识别；TRR AI辅助定价", "kpi_metric": "AI日处理件数", "kpi_current": "0", "kpi_target": "80件/天", "roi_estimate": 16.7, "payback_months": 6, "risk_level": "高", "is_key_path": "是", "strategic_theme": "信任底座", "action_stage": "启动"},
            {"initiative_id": "D1-AI-02", "dimension": "D1信任基础设施", "initiative_name": "AI鉴定扩展（和田玉+南红）", "priority": "P0关键路径", "target_quarter": "2026Q2", "status": "待启动", "estimated_investment": 200000, "expected_revenue_impact": 3000000, "benchmark_ref": "Catawiki 240专家跨80品类", "kpi_metric": "AI覆盖品类数", "kpi_current": "0", "kpi_target": "3个核心品类", "roi_estimate": 15.0, "payback_months": 6, "risk_level": "高", "is_key_path": "是", "strategic_theme": "信任底座", "action_stage": "筹备"},
            {"initiative_id": "D1-TEAM-01", "dimension": "D1信任基础设施", "initiative_name": "鉴定师团队扩充至40人", "priority": "P0关键路径", "target_quarter": "2026Q2", "status": "待启动", "estimated_investment": 500000, "expected_revenue_impact": 4000000, "benchmark_ref": "Catawiki 240人 / TRR数百人", "kpi_metric": "鉴定师总数", "kpi_current": "23", "kpi_target": "40", "roi_estimate": 8.0, "payback_months": 8, "risk_level": "中", "is_key_path": "是", "strategic_theme": "组织能力", "action_stage": "筹备"},
            {"initiative_id": "D1-REPORT-01", "dimension": "D1信任基础设施", "initiative_name": "结构化鉴定报告模板", "priority": "P1重要", "target_quarter": "2026Q1", "status": "待启动", "estimated_investment": 50000, "expected_revenue_impact": 0, "benchmark_ref": "TRR鉴定数据化沉淀", "kpi_metric": "结构化鉴定记录数", "kpi_current": "0", "kpi_target": "5000条/年", "roi_estimate": 0, "payback_months": 0, "risk_level": "低", "is_key_path": "否", "strategic_theme": "标准化", "action_stage": "启动"},
            {"initiative_id": "D2-PRESCREEN-01", "dimension": "D2供给引擎", "initiative_name": "前置估值系统上线", "priority": "P0关键路径", "target_quarter": "2026Q1", "status": "待启动", "estimated_investment": 150000, "expected_revenue_impact": 2000000, "benchmark_ref": "TRR虚拟咨询服务", "kpi_metric": "无效寄售率", "kpi_current": "47%", "kpi_target": "30%", "roi_estimate": 13.3, "payback_months": 5, "risk_level": "中", "is_key_path": "是", "strategic_theme": "供给筛选", "action_stage": "启动"},
            {"initiative_id": "D2-SUPPLY-01", "dimension": "D2供给引擎", "initiative_name": "景德镇/宜兴产业带合作", "priority": "P1重要", "target_quarter": "2026Q3", "status": "待启动", "estimated_investment": 100000, "expected_revenue_impact": 3000000, "benchmark_ref": "产业带直接合作模式", "kpi_metric": "产业带合作商数", "kpi_current": "0", "kpi_target": "20家", "roi_estimate": 30.0, "payback_months": 4, "risk_level": "中", "is_key_path": "否", "strategic_theme": "供给扩张", "action_stage": "筹备"},
            {"initiative_id": "D2-SUPPLY-02", "dimension": "D2供给引擎", "initiative_name": "千匠守艺供给反哺", "priority": "P2增强", "target_quarter": "2027+", "status": "待启动", "estimated_investment": 200000, "expected_revenue_impact": 1500000, "benchmark_ref": "Mercari x Japan跨境供给", "kpi_metric": "千匠守艺联动SKU", "kpi_current": "0", "kpi_target": "500件/月", "roi_estimate": 7.5, "payback_months": 10, "risk_level": "中", "is_key_path": "否", "strategic_theme": "跨域协同", "action_stage": "规划"},
            {"initiative_id": "D2-SELLER-01", "dimension": "D2供给引擎", "initiative_name": "卖家拓展专员团队", "priority": "P1重要", "target_quarter": "2026Q2", "status": "待启动", "estimated_investment": 300000, "expected_revenue_impact": 5000000, "benchmark_ref": "TRR Sales Professional", "kpi_metric": "月活跃卖家数", "kpi_current": "212", "kpi_target": "500", "roi_estimate": 16.7, "payback_months": 6, "risk_level": "中", "is_key_path": "是", "strategic_theme": "供给增长", "action_stage": "启动"},
            {"initiative_id": "D3-AUCTION-01", "dimension": "D3需求引擎", "initiative_name": "主题拍卖专场体系", "priority": "P0关键路径", "target_quarter": "2026Q2", "status": "待启动", "estimated_investment": 100000, "expected_revenue_impact": 3000000, "benchmark_ref": "Catawiki周度主题拍卖", "kpi_metric": "月专场拍卖场数", "kpi_current": "0", "kpi_target": "8场/月", "roi_estimate": 30.0, "payback_months": 4, "risk_level": "中", "is_key_path": "是", "strategic_theme": "拍卖增长", "action_stage": "启动"},
            {"initiative_id": "D3-MEMBER-01", "dimension": "D3需求引擎", "initiative_name": "会员体系重构", "priority": "P1重要", "target_quarter": "2026Q3", "status": "待启动", "estimated_investment": 80000, "expected_revenue_impact": 1000000, "benchmark_ref": "TRR First Look订阅", "kpi_metric": "付费会员数", "kpi_current": "约100", "kpi_target": "2000", "roi_estimate": 12.5, "payback_months": 8, "risk_level": "中", "is_key_path": "否", "strategic_theme": "会员增长", "action_stage": "筹备"},
            {"initiative_id": "D3-CONTENT-01", "dimension": "D3需求引擎", "initiative_name": "故事化商品展示", "priority": "P1重要", "target_quarter": "2026Q2", "status": "待启动", "estimated_investment": 100000, "expected_revenue_impact": 1500000, "benchmark_ref": "1stDibs策展体验", "kpi_metric": "带故事商品占比", "kpi_current": "0%", "kpi_target": "30%", "roi_estimate": 15.0, "payback_months": 6, "risk_level": "中", "is_key_path": "否", "strategic_theme": "内容转化", "action_stage": "启动"},
            {"initiative_id": "D3-REACTIVATE-01", "dimension": "D3需求引擎", "initiative_name": "单次购买客户激活计划", "priority": "P1重要", "target_quarter": "2026Q2", "status": "待启动", "estimated_investment": 50000, "expected_revenue_impact": 2000000, "benchmark_ref": "CRM最佳实践", "kpi_metric": "仅1次购买占比", "kpi_current": "37%", "kpi_target": "25%", "roi_estimate": 40.0, "payback_months": 3, "risk_level": "中", "is_key_path": "否", "strategic_theme": "客户激活", "action_stage": "启动"},
            {"initiative_id": "D4-SOCIAL-01", "dimension": "D4交易机制", "initiative_name": "社交化竞拍功能", "priority": "P1重要", "target_quarter": "2026Q2", "status": "待启动", "estimated_investment": 120000, "expected_revenue_impact": 1000000, "benchmark_ref": "Heritage实时竞拍大厅", "kpi_metric": "竞拍页互动率", "kpi_current": "—", "kpi_target": "5%", "roi_estimate": 8.3, "payback_months": 8, "risk_level": "中", "is_key_path": "否", "strategic_theme": "竞拍体验", "action_stage": "筹备"},
            {"initiative_id": "D4-BUYNOW-01", "dimension": "D4交易机制", "initiative_name": "Buy Now+拍卖混合模式优化", "priority": "P2增强", "target_quarter": "2026Q3", "status": "待启动", "estimated_investment": 80000, "expected_revenue_impact": 500000, "benchmark_ref": "Catawiki 2024引入Buy Now", "kpi_metric": "一口价转化率提升", "kpi_current": "—", "kpi_target": "+10%", "roi_estimate": 6.3, "payback_months": 10, "risk_level": "低", "is_key_path": "否", "strategic_theme": "交易机制", "action_stage": "规划"},
            {"initiative_id": "D5-AUCTION-THEMED-01", "dimension": "D5内容与IP", "initiative_name": "万里茶道主题专场拍卖", "priority": "P0关键路径", "target_quarter": "2026Q2", "status": "待启动", "estimated_investment": 50000, "expected_revenue_impact": 3000000, "benchmark_ref": "杨老师IP×Catawiki专场模式", "kpi_metric": "专场年GMV", "kpi_current": "0", "kpi_target": "300-500万", "roi_estimate": 60.0, "payback_months": 2, "risk_level": "中", "is_key_path": "是", "strategic_theme": "IP驱动", "action_stage": "启动"},
            {"initiative_id": "D5-BOOK-01", "dimension": "D5内容与IP", "initiative_name": "万里茶道书籍出版", "priority": "P0关键路径", "target_quarter": "2026Q3", "status": "筹备中", "estimated_investment": 100000, "expected_revenue_impact": 500000, "benchmark_ref": "14.4万字书稿已完成", "kpi_metric": "出版+首印量", "kpi_current": "书稿完成", "kpi_target": "首印5万册", "roi_estimate": 5.0, "payback_months": 12, "risk_level": "中", "is_key_path": "是", "strategic_theme": "内容变现", "action_stage": "筹备"},
            {"initiative_id": "D5-COURSE-01", "dimension": "D5内容与IP", "initiative_name": "文化艺术品鉴赏付费课程", "priority": "P1重要", "target_quarter": "2026Q4", "status": "待启动", "estimated_investment": 150000, "expected_revenue_impact": 2000000, "benchmark_ref": "Antiques Roadshow教育功能", "kpi_metric": "课程销售量", "kpi_current": "0", "kpi_target": "10000份", "roi_estimate": 13.3, "payback_months": 8, "risk_level": "中", "is_key_path": "否", "strategic_theme": "教育内容", "action_stage": "规划"},
            {"initiative_id": "D5-副IP-01", "dimension": "D5内容与IP", "initiative_name": "品类专家副IP矩阵培育", "priority": "P1重要", "target_quarter": "2026Q2", "status": "待启动", "estimated_investment": 200000, "expected_revenue_impact": 1500000, "benchmark_ref": "TRR/开运鉴定团专家团队", "kpi_metric": "副IP独立带货能力", "kpi_current": "0", "kpi_target": "3个副IP月均GMV>30万", "roi_estimate": 7.5, "payback_months": 10, "risk_level": "中", "is_key_path": "否", "strategic_theme": "副IP矩阵", "action_stage": "筹备"},
            {"initiative_id": "D6-DATA-01", "dimension": "D6技术与数据", "initiative_name": "数据埋点+基础推荐上线", "priority": "P0关键路径", "target_quarter": "2026Q2", "status": "待启动", "estimated_investment": 200000, "expected_revenue_impact": 1000000, "benchmark_ref": "TRR数据驱动匹配", "kpi_metric": "埋点覆盖率", "kpi_current": "~10%", "kpi_target": "80%", "roi_estimate": 5.0, "payback_months": 10, "risk_level": "中", "is_key_path": "是", "strategic_theme": "数据底座", "action_stage": "启动"},
            {"initiative_id": "D6-PLATFORM-01", "dimension": "D6技术与数据", "initiative_name": "平台1.5→2.0升级", "priority": "P1重要", "target_quarter": "2026Q3-Q4", "status": "待启动", "estimated_investment": 1000000, "expected_revenue_impact": 3000000, "benchmark_ref": "全栈技术平台", "kpi_metric": "系统功能完成率", "kpi_current": "1.0", "kpi_target": "2.0", "roi_estimate": 3.0, "payback_months": 12, "risk_level": "高", "is_key_path": "否", "strategic_theme": "平台升级", "action_stage": "规划"},
            {"initiative_id": "D6-SEARCH-01", "dimension": "D6技术与数据", "initiative_name": "搜索优化+分类改进", "priority": "P0关键路径", "target_quarter": "2026Q1", "status": "待启动", "estimated_investment": 80000, "expected_revenue_impact": 500000, "benchmark_ref": "搜索无结果率优化", "kpi_metric": "搜索转化率", "kpi_current": "—", "kpi_target": "+20%", "roi_estimate": 6.3, "payback_months": 6, "risk_level": "中", "is_key_path": "是", "strategic_theme": "搜索体验", "action_stage": "启动"},
            {"initiative_id": "D7-BUYER-FEE-01", "dimension": "D7收入模型", "initiative_name": "买家服务费试点（3%）", "priority": "P1重要", "target_quarter": "2026Q4", "status": "待启动", "estimated_investment": 30000, "expected_revenue_impact": 1800000, "benchmark_ref": "Catawiki双边收费", "kpi_metric": "买家费收入", "kpi_current": "0", "kpi_target": "年180万", "roi_estimate": 60.0, "payback_months": 2, "risk_level": "中", "is_key_path": "否", "strategic_theme": "收入拓展", "action_stage": "规划"},
            {"initiative_id": "D7-COMMISSION-01", "dimension": "D7收入模型", "initiative_name": "佣金率渐进提升（22%→25%）", "priority": "P1重要", "target_quarter": "2026Q3", "status": "待启动", "estimated_investment": 0, "expected_revenue_impact": 2000000, "benchmark_ref": "TRR 38% / Catawiki 20%", "kpi_metric": "综合佣金率", "kpi_current": "22.3%", "kpi_target": "25%", "roi_estimate": 0, "payback_months": 0, "risk_level": "中", "is_key_path": "否", "strategic_theme": "收费模型", "action_stage": "规划"},
            {"initiative_id": "D7-AD-01", "dimension": "D7收入模型", "initiative_name": "搜索推荐位付费推广", "priority": "P2增强", "target_quarter": "2027+", "status": "待启动", "estimated_investment": 100000, "expected_revenue_impact": 1000000, "benchmark_ref": "微拍堂广告收入占40%+", "kpi_metric": "广告收入", "kpi_current": "0", "kpi_target": "年100万", "roi_estimate": 10.0, "payback_months": 12, "risk_level": "低", "is_key_path": "否", "strategic_theme": "广告化", "action_stage": "规划"},
            {"initiative_id": "D7-CONSULT-01", "dimension": "D7收入模型", "initiative_name": "专家一对一鉴定咨询服务", "priority": "P2增强", "target_quarter": "2026Q4", "status": "待启动", "estimated_investment": 50000, "expected_revenue_impact": 500000, "benchmark_ref": "Catawiki专家增值服务", "kpi_metric": "付费鉴定咨询数", "kpi_current": "0", "kpi_target": "500次/年", "roi_estimate": 10.0, "payback_months": 12, "risk_level": "低", "is_key_path": "否", "strategic_theme": "增值服务", "action_stage": "规划"},
        ]
    ]

    t10_rows = []
    for row in [
        {"round": "Pre-A", "target_year": "2026", "gmv_basis": 60000000, "revenue_basis": 15700000, "valuation_multiple_low": 3, "valuation_multiple_high": 4, "funding_amount": 3000000, "dilution_pct": 10, "use_of_funds": "AI鉴定30%+鉴定师扩建20%+技术升级25%+运营团队15%+流动资金10%", "key_milestones": "鉴定产能4倍扩容+月GMV突破500万+万里茶道书籍出版", "benchmark_company": "Catawiki D轮", "benchmark_multiple": 6.0, "scenario_label": "Pre-A"},
        {"round": "A轮", "target_year": "2027", "gmv_basis": 150000000, "revenue_basis": 41000000, "valuation_multiple_low": 5, "valuation_multiple_high": 7, "funding_amount": 10000000, "dilution_pct": 15, "use_of_funds": "平台2.0+苏州展仓+品类扩张+千匠守艺海外启动", "key_milestones": "年GMV 1.5亿+苏州展仓开业+海外首单+IP内容矩阵成熟", "benchmark_company": "Catawiki C轮", "benchmark_multiple": 5.0, "scenario_label": "A轮"},
        {"round": "B轮", "target_year": "2028", "gmv_basis": 300000000, "revenue_basis": 85000000, "valuation_multiple_low": 6, "valuation_multiple_high": 8, "funding_amount": 30000000, "dilution_pct": 15, "use_of_funds": "全国线下展仓网络+国际化+AI 3.0+供应链金融", "key_milestones": "年GMV 3亿+3城线下展仓+海外GMV占比10%+AI鉴定覆盖全品类", "benchmark_company": "Catawiki D轮", "benchmark_multiple": 6.0, "scenario_label": "B轮"},
        {"round": "C轮", "target_year": "2029", "gmv_basis": 600000000, "revenue_basis": 170000000, "valuation_multiple_low": 7, "valuation_multiple_high": 10, "funding_amount": 50000000, "dilution_pct": 12, "use_of_funds": "IPO准备+全球扩张+文化生态建设", "key_milestones": "年GMV 6亿+5城展仓+海外GMV占比20%+年利润过亿", "benchmark_company": "TheRealReal IPO", "benchmark_multiple": 8.0, "scenario_label": "C轮"},
    ]:
        implied_low = row["revenue_basis"] * row["valuation_multiple_low"] / 10000
        implied_high = row["revenue_basis"] * row["valuation_multiple_high"] / 10000
        t10_rows.append(
            {
                "record_key": _row_key("T10", row["round"]),
                **row,
                "implied_valuation_low": round(implied_low, 2),
                "implied_valuation_high": round(implied_high, 2),
                "post_money_low": round(implied_low + row["funding_amount"] / 10000, 2),
                "post_money_high": round(implied_high + row["funding_amount"] / 10000, 2),
                "source_note": "TS-BRM-03",
            }
        )

    t11_rows = []
    summary_by_month = defaultdict(lambda: {"gmv": 0, "revenue": 0, "opex": 0, "profit": 0, "orders": 0, "active_sellers": 0, "active_buyers": 0})
    for row in t01_rows:
        month = _normalize_month_label(row["month"])
        summary_by_month[month]["gmv"] += row["gmv"] or 0
        summary_by_month[month]["orders"] += row["total_orders"] or 0
        summary_by_month[month]["active_sellers"] = max(summary_by_month[month]["active_sellers"], row["active_sellers"] or 0)
    for row in t02_rows:
        month = _normalize_month_label(row["month"])
        summary_by_month[month]["revenue"] += row["revenue_total"] if isinstance(row.get("revenue_total"), (int, float)) else 0
        summary_by_month[month]["opex"] += row["opex_total"] if isinstance(row.get("opex_total"), (int, float)) else 0
    for month, metrics in sorted(summary_by_month.items()):
        if not month:
            continue
        t11_rows.append(
            {
                "record_key": _row_key("T11", month),
                "month": _as_month_ms_from_value(month),
                "snapshot_name": f"{month}经营快照",
                "gmv": metrics["gmv"],
                "revenue": metrics["revenue"],
                "opex": metrics["opex"],
                "profit": metrics["revenue"] - metrics["opex"],
                "orders": metrics["orders"],
                "active_sellers": metrics["active_sellers"],
                "active_buyers": 0,
                "content_reach": 0,
                "customer_health_score": 0,
                "supply_chain_score": 0,
                "tech_health_score": 0,
                "strategic_priority": "P0",
                "notes": "由 T01/T02 汇总生成",
            }
        )

    t12_rows = [
        {
            "config_key": "registry_version",
            "config_value": "v1",
            "value_type": "string",
            "scope": "system",
            "source_table": "table_registry",
            "source_sheet": "",
            "source_field": "",
            "enabled": True,
            "version": "v1",
            "owner": "Codex",
            "description": "回旋镖局表注册表版本",
            "updated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "notes": "",
        },
        {
            "config_key": "source_file_stats",
            "config_value": str(DATA_STATS_PATH),
            "value_type": "string",
            "scope": "system",
            "source_table": "source",
            "source_sheet": "",
            "source_field": "",
            "enabled": True,
            "version": "v1",
            "owner": "Codex",
            "description": "数据统计源文件",
            "updated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "notes": "",
        },
        {
            "config_key": "source_file_finance",
            "config_value": str(FINANCE_PATH),
            "value_type": "string",
            "scope": "system",
            "source_table": "source",
            "source_sheet": "",
            "source_field": "",
            "enabled": True,
            "version": "v1",
            "owner": "Codex",
            "description": "财务尽调源文件",
            "updated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "notes": "",
        },
    ]

    return {
        "T01_月度经营数据": t01_rows,
        "T02_月度财务数据": t02_rows,
        "T03_客户分析": t03_rows,
        "T04_品类分析": t04_rows,
        "T05_供应链效率": t05_rows,
        "T06_内容与IP": t06_rows,
        "T07_财务建模": t07_rows,
        "T08_对标矩阵": t08_rows,
        "T09_进化追踪": t09_rows,
        "T10_估值测算": t10_rows,
        "T11_月度经营快照": t11_rows,
        "T12_元数据与配置": t12_rows,
    }


def normalize_record_value(field: FieldSpec, value: Any) -> Any:
    if field.type == DATETIME:
        if value in {None, ""}:
            return ""
        if isinstance(value, (int, float)):
            integer = int(value)
            return integer if abs(integer) >= 10**12 else integer * 1000
        if isinstance(value, date):
            return int(datetime(value.year, value.month, value.day, tzinfo=timezone.utc).timestamp() * 1000)
        text = _safe_text(value)
        if not text:
            return ""
        if text.isdigit():
            integer = int(text)
            return integer if abs(integer) >= 10**12 else integer * 1000
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return int(parsed.timestamp() * 1000)
        except ValueError:
            return text
    if field.type == NUMBER or field.type == FORMULA:
        if value in {None, ""}:
            return ""
        if isinstance(value, (int, float)):
            return value
        text = _safe_text(value).replace(",", "")
        try:
            if "." in text:
                return float(text)
            return int(text)
        except ValueError:
            return text
    if field.type == CHECKBOX:
        if isinstance(value, bool):
            return value
        text = _safe_text(value).lower()
        return text in {"1", "true", "yes", "y", "是"}
    if field.type == MULTI_SELECT:
        if value in {None, ""}:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()]
    if value in {None, ""}:
        return ""
    return value


def normalize_row_for_table(row: dict[str, Any], spec: TableSpec) -> dict[str, Any]:
    fields = {field.name: field for field in spec.fields}
    payload: dict[str, Any] = {}
    for key, value in row.items():
        field = fields.get(key)
        if not field:
            continue
        normalized = normalize_record_value(field, value)
        if normalized in {"", [], None}:
            continue
        payload[key] = normalized
    return payload


def batch_create_records(client: FeishuBitableAPI, app_token: str, table_id: str, rows: list[dict[str, Any]]) -> int:
    created = 0
    for start in range(0, len(rows), 500):
        batch = rows[start : start + 500]
        if not batch:
            continue
        client.batch_create_records(app_token, table_id, batch)
        created += len(batch)
    return created


def batch_update_records(client: FeishuBitableAPI, app_token: str, table_id: str, rows: list[dict[str, Any]]) -> int:
    updated = 0
    for start in range(0, len(rows), 500):
        batch = rows[start : start + 500]
        if not batch:
            continue
        client.batch_update_records(app_token, table_id, batch)
        updated += len(batch)
    return updated


def write_records_for_table(client: FeishuBitableAPI, app_token: str, spec: TableSpec, rows: list[dict[str, Any]], *, apply: bool) -> dict[str, Any]:
    table_id = table_id_from_registry(load_registry(), spec.table_name)
    if not table_id:
        raise RuntimeError(f"missing table_id in registry for {spec.table_name}")
    normalized_rows = [normalize_row_for_table(row, spec) for row in rows]
    existing = client.list_records(app_token, table_id)
    existing_by_key = {str((record.get("fields") or {}).get(spec.primary_field) or ""): record for record in existing}
    to_create: list[dict[str, Any]] = []
    to_update: list[dict[str, Any]] = []
    for row in normalized_rows:
        primary_value = str(row.get(spec.primary_field) or "")
        if not primary_value:
            continue
        record = existing_by_key.get(primary_value)
        if record:
            current = record.get("fields") or {}
            if current != row:
                to_update.append({"record_id": record.get("record_id") or record.get("id"), "fields": row})
        else:
            to_create.append({"fields": row})
    if apply and to_create:
        batch_create_records(client, app_token, table_id, [item["fields"] for item in to_create])
    if apply and to_update:
        batch_update_records(client, app_token, table_id, to_update)
    refreshed = client.list_records(app_token, table_id)
    return {
        "table_name": spec.table_name,
        "table_id": table_id,
        "primary_field": spec.primary_field,
        "source_rows": len(normalized_rows),
        "existing_rows": len(existing),
        "to_create": len(to_create),
        "to_update": len(to_update),
        "final_rows": len(refreshed),
        "applied": apply,
    }


def build_task_tracker_payload(task_id: str, *, task_name: str, project_id: str, task_status: str, priority: str, completion_date: str | None = None, evidence_ref: str = "", notes: str = "", project_name: str = "回旋镖局战略经营驾驶舱") -> dict[str, Any]:
    payload = {
        "task_id": task_id,
        "project_id": project_id,
        "project_name": project_name,
        "project_status": "进行中",
        "task_name": task_name,
        "task_status": task_status,
        "priority": priority,
        "owner": "Codex",
        "evidence_ref": evidence_ref,
        "notes": notes,
    }
    if completion_date:
        payload["completion_date"] = completion_date
    return payload


def upsert_task_tracker_rows(client: FeishuBitableAPI, rows: list[dict[str, Any]], *, apply: bool) -> dict[str, Any]:
    existing = client.list_records(TASK_TRACKER_APP, TASK_TRACKER_TABLE)
    existing_by_task_id = {}
    for record in existing:
        task_id = str((record.get("fields") or {}).get("task_id") or "").strip()
        if task_id:
            existing_by_task_id[task_id] = record
    create_payload: list[dict[str, Any]] = []
    update_payload: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    for row in rows:
        task_id = str(row.get("task_id") or "").strip()
        if not task_id:
            continue
        current = existing_by_task_id.get(task_id)
        if current:
            update_payload.append({"record_id": current.get("record_id") or current.get("id"), "fields": row})
            actions.append({"task_id": task_id, "action": "update"})
        else:
            create_payload.append(row)
            actions.append({"task_id": task_id, "action": "create"})
    if apply and create_payload:
        batch_create_records(client, TASK_TRACKER_APP, TASK_TRACKER_TABLE, create_payload)
    if apply and update_payload:
        batch_update_records(client, TASK_TRACKER_APP, TASK_TRACKER_TABLE, update_payload)
    return {
        "existing": len(existing_by_task_id),
        "created": len(create_payload),
        "updated": len(update_payload),
        "actions": actions,
    }

