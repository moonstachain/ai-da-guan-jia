"""Clean business data from a source Feishu base and sync it into a target base."""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dashboard.feishu_deploy import FeishuBitableAPI, normalize_record, schema_field_to_feishu_field


PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parent
BUSINESS_SCHEMA_DIR = PACKAGE_DIR / "business_schemas"
BUSINESS_ARTIFACT_DIR = REPO_ROOT / "artifacts" / "business-dashboard-sync"
BUSINESS_DASHBOARD_SPEC_PATH = PACKAGE_DIR / "business_dashboard_spec.json"
MIAODA_PROMPT_PATH = REPO_ROOT / "specs" / "miaoda-business-dashboard-prompt.md"
OPENCLAW_CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"

SOURCE_TABLE_FILE_MAP = {
    "客户机会主表": "customer_opportunities.json",
    "阶段漏斗表": "stage_funnel.json",
    "服务线表": "service_lines.json",
    "订单事实表": "order_facts.json",
    "跟进与证据表": "followup_evidence.json",
    "交付阶段表": "delivery_stages.json",
    "学员/客户档案表": "customer_profiles.json",
    "交付项目表": "delivery_projects.json",
    "目标预算表": "target_budget.json",
    "经营节奏表": "operating_rhythm.json",
    "私域运营事实表": "private_domain_ops.json",
    "内容流量事实表": "content_traffic.json",
    "数据表": "raw_staging.json",
}

LINK_FIELD_TEXTS = {"服务线", "当前阶段", "关联订单", "关联证据", "关联交付", "来源订单", "来源机会", "升单机会"}
DASHBOARD_TABLE_SPECS: list[dict[str, Any]] = [
    {
        "table_name": "L0_经营总览",
        "file_name": "l0_overview.json",
        "purpose": "年度目标追踪 + 月度经营健康度",
        "fields": [
            {"name": "year_target", "type": "number"},
            {"name": "ytd_amount", "type": "number"},
            {"name": "ytd_completion", "type": "number"},
            {"name": "current_month", "type": "text"},
            {"name": "month_amount", "type": "number"},
            {"name": "month_order_count", "type": "number"},
            {"name": "month_avg_price", "type": "number"},
            {"name": "high_value_ratio", "type": "number"},
            {"name": "active_customers", "type": "number"},
            {"name": "pipeline_amount", "type": "number"},
            {"name": "repurchase_pool", "type": "number"},
            {"name": "top_risk", "type": "text"},
            {"name": "business_conclusion", "type": "text"},
            {"name": "last_refresh", "type": "number"},
        ],
    },
    {
        "table_name": "L2_增长驾驶舱",
        "file_name": "l2_growth.json",
        "purpose": "线索、订单与裂变增长总览",
        "fields": [
            {"name": "year_month", "type": "text"},
            {"name": "public_leads", "type": "number"},
            {"name": "private_leads", "type": "number"},
            {"name": "new_orders", "type": "number"},
            {"name": "new_amount", "type": "number"},
            {"name": "new_customers", "type": "number"},
            {"name": "repurchase_opportunities", "type": "number"},
            {"name": "referral_leads", "type": "number"},
            {"name": "referral_closed", "type": "number"},
            {"name": "referral_amount", "type": "number"},
            {"name": "growth_conclusion", "type": "text"},
        ],
    },
    {
        "table_name": "L2_履约驾驶舱",
        "file_name": "l2_fulfillment.json",
        "purpose": "交付项目、价值核销与超期风险总览",
        "fields": [
            {"name": "year_month", "type": "text"},
            {"name": "new_fulfillments", "type": "number"},
            {"name": "in_service", "type": "number"},
            {"name": "completed", "type": "number"},
            {"name": "total_value", "type": "number"},
            {"name": "used_value", "type": "number"},
            {"name": "value_rate", "type": "number"},
            {"name": "overdue_count", "type": "number"},
            {"name": "private_board_total", "type": "number"},
            {"name": "private_board_used", "type": "number"},
            {"name": "private_board_rate", "type": "number"},
        ],
    },
    {
        "table_name": "L2_销售驾驶舱",
        "file_name": "l2_sales.json",
        "purpose": "按月按销售负责人观察成交与跟进效率",
        "fields": [
            {"name": "year_month", "type": "text"},
            {"name": "sales_owner", "type": "text"},
            {"name": "new_leads", "type": "number"},
            {"name": "opportunities", "type": "number"},
            {"name": "signed_amount", "type": "number"},
            {"name": "fulfilled_value", "type": "number"},
            {"name": "high_value_opps", "type": "number"},
            {"name": "follow_actions", "type": "number"},
            {"name": "avg_unit_price", "type": "number"},
            {"name": "fulfillment_rate", "type": "number"},
        ],
    },
    {
        "table_name": "L2_客户价值分析",
        "file_name": "l2_customer_value.json",
        "purpose": "客户累计价值、来源与经营策略分析",
        "fields": [
            {"name": "customer_name", "type": "text"},
            {"name": "total_amount", "type": "number"},
            {"name": "order_count", "type": "number"},
            {"name": "customer_tier", "type": "single_select", "options": ["战略客户", "成长客户", "普通客户"]},
            {"name": "main_lead_source", "type": "text"},
            {"name": "main_product", "type": "text"},
            {"name": "sales_owner", "type": "text"},
            {"name": "first_sign_date", "type": "text"},
            {"name": "last_sign_date", "type": "text"},
            {"name": "strategy", "type": "text"},
        ],
    },
]


@dataclass(frozen=True)
class TableBundle:
    table_name: str
    file_name: str
    schema: dict[str, Any]
    records: list[dict[str, Any]]


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _read_openclaw_credentials() -> tuple[str, str] | None:
    if not OPENCLAW_CONFIG_PATH.exists():
        return None
    payload = json.loads(OPENCLAW_CONFIG_PATH.read_text(encoding="utf-8"))
    account = payload.get("channels", {}).get("feishu", {}).get("accounts", {}).get("feishu-claw", {})
    app_id = str(account.get("appId") or "").strip()
    app_secret = str(account.get("appSecret") or "").strip()
    if not app_id or not app_secret:
        return None
    return app_id, app_secret


def resolve_feishu_credentials() -> tuple[str, str]:
    app_id = str(os.getenv("FEISHU_APP_ID") or "").strip()
    app_secret = str(os.getenv("FEISHU_APP_SECRET") or "").strip()
    if app_id and app_secret:
        return app_id, app_secret
    openclaw = _read_openclaw_credentials()
    if openclaw is not None:
        return openclaw
    raise RuntimeError("Missing FEISHU_APP_ID / FEISHU_APP_SECRET and ~/.openclaw/openclaw.json fallback.")


class BusinessSyncAPI(FeishuBitableAPI):
    def create_field(self, app_token: str, table_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._request(
            f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
            method="POST",
            payload=payload,
        )
        return (response.get("data") or {}).get("field") or (response.get("data") or {})

    def delete_record(self, app_token: str, table_id: str, record_id: str) -> None:
        self._request(
            f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
            method="DELETE",
        )


def _field_options(field: dict[str, Any]) -> list[str]:
    property_payload = field.get("property") or {}
    options = property_payload.get("options") or []
    return [str(item.get("name") or "").strip() for item in options if str(item.get("name") or "").strip()]


def _source_field_to_schema(field: dict[str, Any]) -> dict[str, Any]:
    field_name = str(field.get("field_name") or field.get("name") or "").strip()
    field_type = int(field.get("type") or 1)
    if field_type == 2:
        schema_type = "number"
    elif field_type == 3:
        schema_type = "single_select"
    elif field_type == 5:
        schema_type = "datetime"
    else:
        schema_type = "text"
    payload: dict[str, Any] = {
        "name": field_name,
        "type": schema_type,
        "source_type": field_type,
    }
    if schema_type == "single_select":
        payload["options"] = _field_options(field)
    return payload


def flatten_cell(value: Any) -> Any:
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        flattened: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = str(item.get("text") or item.get("name") or item.get("token") or "").strip()
                if text:
                    flattened.append(text)
            else:
                text = str(item).strip()
                if text:
                    flattened.append(text)
        return " | ".join(flattened)
    if isinstance(value, dict):
        return str(value.get("text") or value.get("name") or value.get("token") or "").strip()
    return str(value).strip()


def _normalize_source_value(field: dict[str, Any], value: Any) -> Any:
    normalized = flatten_cell(value)
    field_type = str(field.get("type") or "").strip().lower()
    if normalized in {"", None}:
        return ""
    if field_type == "number":
        if isinstance(normalized, (int, float)):
            return normalized
        text = str(normalized).replace(",", "").strip()
        try:
            return int(text)
        except ValueError:
            try:
                return round(float(text), 2)
            except ValueError:
                return ""
    return normalized


def _normalize_source_record(schema: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    fields_by_name = {field["name"]: field for field in schema.get("fields", [])}
    for key, value in record.items():
        field = fields_by_name.get(key)
        if not field:
            continue
        normalized = _normalize_source_value(field, value)
        if normalized == "":
            continue
        output[key] = normalized
    return output


def _month_key(value: Any) -> str:
    if value in {"", None}:
        return ""
    if isinstance(value, (int, float)):
        seconds = int(value)
        if seconds >= 10**12:
            seconds //= 1000
        return datetime.fromtimestamp(seconds, tz=UTC).strftime("%Y-%m")
    text = str(value).strip()
    if not text:
        return ""
    for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d", "%m.%d", "%Y-%m", "%Y.%m"):
        try:
            parsed = datetime.strptime(text, fmt)
            if fmt == "%m.%d":
                return f"2026-{parsed.month:02d}"
            return parsed.strftime("%Y-%m")
        except ValueError:
            continue
    return text[:7]


def _date_text(value: Any) -> str:
    if value in {"", None}:
        return ""
    if isinstance(value, (int, float)):
        seconds = int(value)
        if seconds >= 10**12:
            seconds //= 1000
        return datetime.fromtimestamp(seconds, tz=UTC).strftime("%Y-%m-%d")
    return str(value).strip()


def _number(value: Any) -> float:
    if value in {"", None}:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _most_common(values: list[str]) -> str:
    filtered = [value for value in values if value]
    if not filtered:
        return ""
    return Counter(filtered).most_common(1)[0][0]


def _tier_for_amount(total_amount: float) -> str:
    if total_amount >= 50000:
        return "战略客户"
    if total_amount >= 10000:
        return "成长客户"
    return "普通客户"


def _strategy_for_tier(tier: str, order_count: int) -> str:
    if tier == "战略客户":
        return "高频经营，优先推进升单与转介绍。"
    if tier == "成长客户":
        return "持续跟进需求，围绕中客单产品做复购转化。"
    if order_count >= 2:
        return "保留连接，观察复购窗口并补强信任。"
    return "轻量维护，优先沉淀画像与后续触达节奏。"


def fetch_all_records(api: FeishuBitableAPI, app_token: str, table_id: str) -> list[dict[str, Any]]:
    return api.list_records(app_token, table_id)


def fetch_source_bundle(api: BusinessSyncAPI, source_link: str) -> tuple[list[TableBundle], dict[str, list[dict[str, Any]]]]:
    app_token = api.resolve_app_token(source_link)
    bundles: list[TableBundle] = []
    rows_by_table: dict[str, list[dict[str, Any]]] = {}
    tables = api.list_tables(app_token)
    for table in tables:
        table_name = str(table.get("name") or table.get("table_name") or "").strip()
        file_name = SOURCE_TABLE_FILE_MAP.get(table_name)
        if not file_name:
            continue
        table_id = str(table.get("table_id") or "").strip()
        fields = api.list_fields(app_token, table_id)
        schema = {
            "table_name": table_name,
            "layer": "L1",
            "purpose": f"清理后的业务源表：{table_name}",
            "fields": [_source_field_to_schema(field) for field in fields],
        }
        records = [
            _normalize_source_record(schema, item.get("fields") or {})
            for item in fetch_all_records(api, app_token, table_id)
        ]
        records = [item for item in records if item]
        rows_by_table[table_name] = records
        bundles.append(TableBundle(table_name=table_name, file_name=file_name, schema=schema, records=records))
    return bundles, rows_by_table


def build_dashboard_records(rows_by_table: dict[str, list[dict[str, Any]]]) -> list[TableBundle]:
    orders = rows_by_table.get("订单事实表", [])
    opportunities = rows_by_table.get("客户机会主表", [])
    deliveries = rows_by_table.get("交付项目表", [])
    customers = rows_by_table.get("学员/客户档案表", [])
    evidence = rows_by_table.get("跟进与证据表", [])
    private_ops = rows_by_table.get("私域运营事实表", [])

    order_rows: list[dict[str, Any]] = []
    first_month_by_customer: dict[str, str] = {}
    customer_amounts: defaultdict[str, float] = defaultdict(float)
    customer_orders: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    orders_by_id: dict[str, dict[str, Any]] = {}

    for row in orders:
        month = _month_key(row.get("订单日期"))
        customer = str(row.get("客户名称") or "").strip()
        amount = _number(row.get("支付金额"))
        normalized = {
            "month": month,
            "customer_name": customer,
            "amount": amount,
            "owner": str(row.get("主转化归属") or row.get("流量归属") or "").strip(),
            "source": str(row.get("订单来源") or "").strip(),
            "service_line": str(row.get("服务线") or "").strip(),
            "order_id": str(row.get("订单ID") or "").strip(),
            "date_text": _date_text(row.get("订单日期")),
        }
        order_rows.append(normalized)
        if customer:
            if month and (customer not in first_month_by_customer or month < first_month_by_customer[customer]):
                first_month_by_customer[customer] = month
            customer_amounts[customer] += amount
            customer_orders[customer].append(normalized)
        if normalized["order_id"]:
            orders_by_id[normalized["order_id"]] = normalized

    current_month = max((row["month"] for row in order_rows if row["month"]), default=datetime.now().strftime("%Y-%m"))
    ytd_orders = [row for row in order_rows if row["month"] and int(row["month"][:4]) >= 2025]
    current_month_orders = [row for row in order_rows if row["month"] == current_month]
    pipeline_amount = sum(
        _number(item.get("预估成交金额"))
        for item in opportunities
        if str(item.get("当前状态") or "").strip() not in {"已成交", "已关闭", "丢单"}
    )
    repurchase_pool = sum(1 for row in customers if str(row.get("是否邀请复训") or "").strip() == "是")
    high_value_orders = [row for row in current_month_orders if row["amount"] >= 10000]
    l0_row = {
        "year_target": 10000000,
        "ytd_amount": round(sum(row["amount"] for row in ytd_orders), 2),
        "ytd_completion": round(sum(row["amount"] for row in ytd_orders) / 10000000, 4) if ytd_orders else 0,
        "current_month": current_month,
        "month_amount": round(sum(row["amount"] for row in current_month_orders), 2),
        "month_order_count": len(current_month_orders),
        "month_avg_price": round(sum(row["amount"] for row in current_month_orders) / len(current_month_orders), 2) if current_month_orders else 0,
        "high_value_ratio": round(len(high_value_orders) / len(current_month_orders), 4) if current_month_orders else 0,
        "active_customers": len(customers),
        "pipeline_amount": round(pipeline_amount, 2),
        "repurchase_pool": repurchase_pool,
        "top_risk": "高客单依赖度高，需拓宽中客单产品线",
        "business_conclusion": f"{current_month} 共成交 {len(current_month_orders)} 单，需同步关注在谈商机与复购窗口。",
        "last_refresh": _now_ms(),
    }

    months = sorted({row["month"] for row in order_rows if row["month"]} | { _month_key(row.get("日期")) for row in private_ops if _month_key(row.get("日期")) })
    growth_rows: list[dict[str, Any]] = []
    sales_rows: list[dict[str, Any]] = []
    fulfillment_rows: list[dict[str, Any]] = []

    evidence_by_month_owner: defaultdict[tuple[str, str], int] = defaultdict(int)
    for row in evidence:
        month = _month_key(row.get("记录时间"))
        owner = str(row.get("记录人") or "").strip()
        if month:
            evidence_by_month_owner[(month, owner)] += 1

    delivery_rows: list[dict[str, Any]] = []
    for row in deliveries:
        order_ids = [part.strip() for part in str(row.get("来源订单") or "").split("|") if part.strip()]
        total_value = sum(orders_by_id.get(order_id, {}).get("amount", 0) for order_id in order_ids)
        service_line = str(row.get("服务线") or "").strip()
        stage = str(row.get("当前交付阶段") or "").strip()
        start_month = _month_key(row.get("开始时间"))
        end_month = _month_key(row.get("结束时间"))
        delivery_rows.append(
            {
                "start_month": start_month,
                "end_month": end_month,
                "service_line": service_line,
                "stage": stage,
                "risk": str(row.get("当前风险") or "").strip(),
                "owner": str(row.get("交付负责人") or "").strip(),
                "total_value": total_value,
                "used_value": total_value if any(token in stage for token in ("完成", "已结项", "已交付")) else 0,
            }
        )

    for month in months:
        private_rows = [row for row in private_ops if _month_key(row.get("日期")) == month]
        month_orders = [row for row in order_rows if row["month"] == month]
        unique_new_customers = {
            row["customer_name"] for row in month_orders if row["customer_name"] and first_month_by_customer.get(row["customer_name"]) == month
        }
        repeat_customers = Counter(row["customer_name"] for row in month_orders if row["customer_name"])
        growth_rows.append(
            {
                "year_month": month,
                "public_leads": int(sum(_number(row.get("新增加私")) for row in private_rows)),
                "private_leads": int(sum(1 for row in private_rows if _number(row.get("当日私域流水")) > 0)),
                "new_orders": len(month_orders),
                "new_amount": round(sum(row["amount"] for row in month_orders), 2),
                "new_customers": len(unique_new_customers),
                "repurchase_opportunities": sum(1 for customer, count in repeat_customers.items() if customer and count >= 2),
                "referral_leads": 0,
                "referral_closed": 0,
                "referral_amount": 0,
                "growth_conclusion": f"{month} 新增 {len(month_orders)} 单，重点观察高客单与复购客户。",
            }
        )

        month_deliveries = [row for row in delivery_rows if row["start_month"] == month or row["end_month"] == month]
        in_service = sum(1 for row in delivery_rows if row["start_month"] and row["start_month"] <= month and (not row["end_month"] or row["end_month"] >= month))
        completed = sum(1 for row in delivery_rows if row["end_month"] == month and row["used_value"] > 0)
        total_value = sum(row["total_value"] for row in month_deliveries)
        used_value = sum(row["used_value"] for row in month_deliveries)
        private_board_total = sum(row["total_value"] for row in month_deliveries if "私董" in row["service_line"])
        private_board_used = sum(row["used_value"] for row in month_deliveries if "私董" in row["service_line"])
        fulfillment_rows.append(
            {
                "year_month": month,
                "new_fulfillments": sum(1 for row in delivery_rows if row["start_month"] == month),
                "in_service": in_service,
                "completed": completed,
                "total_value": round(total_value, 2),
                "used_value": round(used_value, 2),
                "value_rate": round(used_value / total_value, 4) if total_value else 0,
                "overdue_count": sum(1 for row in month_deliveries if row["risk"]),
                "private_board_total": round(private_board_total, 2),
                "private_board_used": round(private_board_used, 2),
                "private_board_rate": round(private_board_used / private_board_total, 4) if private_board_total else 0,
            }
        )

        owners = sorted({row["owner"] for row in month_orders if row["owner"]})
        for owner in owners:
            owner_orders = [row for row in month_orders if row["owner"] == owner]
            signed_amount = sum(row["amount"] for row in owner_orders)
            related_opps = {
                str(item.get("机会ID") or "").strip()
                for item in opportunities
                if str(item.get("主转化归属") or "").strip() == owner
            }
            owner_delivery_value = sum(row["used_value"] for row in delivery_rows if row["owner"] == owner and (row["end_month"] == month or row["start_month"] == month))
            sales_rows.append(
                {
                    "year_month": month,
                    "sales_owner": owner,
                    "new_leads": len({row["customer_name"] for row in owner_orders if row["customer_name"] and first_month_by_customer.get(row["customer_name"]) == month}),
                    "opportunities": len(related_opps),
                    "signed_amount": round(signed_amount, 2),
                    "fulfilled_value": round(owner_delivery_value, 2),
                    "high_value_opps": sum(1 for row in owner_orders if row["amount"] >= 10000),
                    "follow_actions": evidence_by_month_owner[(month, owner)],
                    "avg_unit_price": round(signed_amount / len(owner_orders), 2) if owner_orders else 0,
                    "fulfillment_rate": round(owner_delivery_value / signed_amount, 4) if signed_amount else 0,
                }
            )

    customer_rows: list[dict[str, Any]] = []
    for customer_name, items in sorted(customer_orders.items()):
        total_amount = round(customer_amounts[customer_name], 2)
        tier = _tier_for_amount(total_amount)
        sources = [item["source"] for item in items if item["source"]]
        service_lines = [item["service_line"] for item in items if item["service_line"]]
        owners = [item["owner"] for item in items if item["owner"]]
        dates = sorted(item["date_text"] for item in items if item["date_text"])
        customer_rows.append(
            {
                "customer_name": customer_name,
                "total_amount": total_amount,
                "order_count": len(items),
                "customer_tier": tier,
                "main_lead_source": _most_common(sources),
                "main_product": _most_common(service_lines),
                "sales_owner": _most_common(owners),
                "first_sign_date": dates[0] if dates else "",
                "last_sign_date": dates[-1] if dates else "",
                "strategy": _strategy_for_tier(tier, len(items)),
            }
        )

    spec_by_name = {item["table_name"]: item for item in DASHBOARD_TABLE_SPECS}
    return [
        TableBundle("L0_经营总览", spec_by_name["L0_经营总览"]["file_name"], spec_by_name["L0_经营总览"], [l0_row]),
        TableBundle("L2_增长驾驶舱", spec_by_name["L2_增长驾驶舱"]["file_name"], spec_by_name["L2_增长驾驶舱"], growth_rows),
        TableBundle("L2_履约驾驶舱", spec_by_name["L2_履约驾驶舱"]["file_name"], spec_by_name["L2_履约驾驶舱"], fulfillment_rows),
        TableBundle("L2_销售驾驶舱", spec_by_name["L2_销售驾驶舱"]["file_name"], spec_by_name["L2_销售驾驶舱"], sales_rows),
        TableBundle("L2_客户价值分析", spec_by_name["L2_客户价值分析"]["file_name"], spec_by_name["L2_客户价值分析"], customer_rows),
    ]


def write_schema_files(source_bundles: list[TableBundle], dashboard_bundles: list[TableBundle], *, schema_dir: Path = BUSINESS_SCHEMA_DIR) -> list[Path]:
    schema_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for bundle in [*source_bundles, *dashboard_bundles]:
        path = schema_dir / bundle.file_name
        path.write_text(json.dumps(bundle.schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(path)
    return written


def write_dashboard_spec(path: Path = BUSINESS_DASHBOARD_SPEC_PATH) -> Path:
    payload = {
        "goal": "用更新版业务事实源生成经营、增长、履约、销售、客户价值五个驾驶舱。",
        "source_tables": list(SOURCE_TABLE_FILE_MAP),
        "dashboards": DASHBOARD_TABLE_SPECS,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def render_miaoda_prompt() -> str:
    lines = [
        "# 妙搭业务驾驶舱提示词",
        "",
        "请基于以下 5 张飞书多维表搭建一个业务驾驶舱页面，风格要求简洁、清晰、偏经营指挥舱：",
        "",
    ]
    for spec in DASHBOARD_TABLE_SPECS:
        lines.append(f"- `{spec['table_name']}`：{spec['purpose']}")
    lines.extend(
        [
            "",
            "页面布局要求：",
            "1. 顶部单独放 `L0_经营总览`，做 CEO 一眼看懂的总览卡。",
            "2. 第二屏左右两列放 `L2_增长驾驶舱` 和 `L2_销售驾驶舱`。",
            "3. 第三屏左右两列放 `L2_履约驾驶舱` 和 `L2_客户价值分析`。",
            "4. 所有金额字段显示为人民币，完成率字段显示百分比。",
            "5. 每个区块至少包含 1 个趋势图、1 个关键指标卡、1 个结论/风险提示。",
            "6. 不要直接展示原始 JSON；只展示可操作的图表和关键结论。",
            "",
            "交互要求：",
            "1. 可以按月份筛选 L2 驾驶舱。",
            "2. 可以按销售负责人筛选销售驾驶舱。",
            "3. 客户价值分析支持按客户分层筛选。",
        ]
    )
    return "\n".join(lines) + "\n"


def write_miaoda_prompt(path: Path = MIAODA_PROMPT_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_miaoda_prompt(), encoding="utf-8")
    return path


class BusinessDashboardMigrator:
    def __init__(self, api: BusinessSyncAPI, *, artifact_dir: Path = BUSINESS_ARTIFACT_DIR) -> None:
        self.api = api
        self.artifact_dir = artifact_dir
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

    def _ensure_table(self, app_token: str, bundle: TableBundle, existing_tables: dict[str, dict[str, Any]]) -> str:
        existing = existing_tables.get(bundle.table_name)
        feishu_fields = [schema_field_to_feishu_field(field) for field in bundle.schema["fields"]]
        if existing is None:
            created = self.api.create_table(app_token, bundle.table_name, feishu_fields)
            table_id = str(created.get("table_id") or "")
            existing_tables[bundle.table_name] = {"table_id": table_id, "name": bundle.table_name}
            return table_id
        table_id = str(existing.get("table_id") or "")
        current_fields = {
            str(field.get("field_name") or field.get("name") or ""): int(field.get("type") or 0)
            for field in self.api.list_fields(app_token, table_id)
        }
        for field_payload in feishu_fields:
            current = current_fields.get(field_payload["field_name"])
            if current is None:
                self.api.create_field(app_token, table_id, field_payload)
            elif current != field_payload["type"]:
                raise RuntimeError(
                    f"Field type mismatch for {bundle.table_name}.{field_payload['field_name']}: {current} != {field_payload['type']}"
                )
        return table_id

    def _seed_table(self, app_token: str, table_id: str, bundle: TableBundle, *, apply_changes: bool) -> dict[str, Any]:
        existing_records = self.api.list_records(app_token, table_id)
        expected_count = len(bundle.records)
        if not apply_changes:
            status = "planned_seed" if not existing_records else "planned_verify_only"
            return {
                "status": status,
                "expected_records": expected_count,
                "verified_records": len(existing_records),
                "inserted_records": 0,
            }
        if existing_records and len(existing_records) == expected_count:
            return {
                "status": "already_seeded",
                "expected_records": expected_count,
                "verified_records": len(existing_records),
                "inserted_records": 0,
            }
        if existing_records:
            for record in existing_records:
                record_id = str(record.get("record_id") or "").strip()
                if record_id:
                    self.api.delete_record(app_token, table_id, record_id)
        normalized_rows = [normalize_record(bundle.schema, row) for row in bundle.records]
        inserted = 0
        for start in range(0, len(normalized_rows), 500):
            batch = [row for row in normalized_rows[start : start + 500] if row]
            if batch:
                self.api.batch_create_records(app_token, table_id, batch)
                inserted += len(batch)
        verified = len(self.api.list_records(app_token, table_id))
        return {
            "status": "seeded",
            "expected_records": expected_count,
            "verified_records": verified,
            "inserted_records": inserted,
        }

    def migrate(self, source_link: str, target_link: str, *, apply_changes: bool) -> dict[str, Any]:
        source_bundles, rows_by_table = fetch_source_bundle(self.api, source_link)
        dashboard_bundles = build_dashboard_records(rows_by_table)
        write_schema_files(source_bundles, dashboard_bundles)
        dashboard_spec_path = write_dashboard_spec()
        prompt_path = write_miaoda_prompt()

        target_app_token = self.api.resolve_app_token(target_link)
        existing_tables = {
            str(item.get("name") or item.get("table_name") or ""): item
            for item in self.api.list_tables(target_app_token)
        }
        results: list[dict[str, Any]] = []
        for bundle in [*source_bundles, *dashboard_bundles]:
            table_id = self._ensure_table(target_app_token, bundle, existing_tables)
            seed_result = self._seed_table(target_app_token, table_id, bundle, apply_changes=apply_changes)
            results.append(
                {
                    "table_name": bundle.table_name,
                    "table_id": table_id,
                    **seed_result,
                }
            )

        payload = {
            "mode": "apply" if apply_changes else "dry-run",
            "source_link": source_link,
            "target_link": target_link,
            "source_table_count": len(source_bundles),
            "dashboard_table_count": len(dashboard_bundles),
            "tables": results,
            "schema_dir": str(BUSINESS_SCHEMA_DIR),
            "dashboard_spec_path": str(dashboard_spec_path),
            "miaoda_prompt_path": str(prompt_path),
        }
        artifact_path = self.artifact_dir / f"business-dashboard-sync-{_now_stamp()}.json"
        artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        payload["artifact_path"] = str(artifact_path)
        return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clean business source tables and sync them into a target Feishu base.")
    parser.add_argument("--source-link", required=True, help="Updated Feishu source bitable wiki/base link.")
    parser.add_argument("--target-link", required=True, help="Feishu target bitable wiki/base link.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    app_id, app_secret = resolve_feishu_credentials()
    api = BusinessSyncAPI(app_id, app_secret)
    migrator = BusinessDashboardMigrator(api)
    result = migrator.migrate(args.source_link, args.target_link, apply_changes=bool(args.apply or not args.dry_run))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
