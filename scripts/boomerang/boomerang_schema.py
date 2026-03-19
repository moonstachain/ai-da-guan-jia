from __future__ import annotations

from typing import Any, Iterable


def text(name: str, *, multiline: bool = False) -> dict[str, Any]:
    return {"name": name, "type": "multiline_text" if multiline else "text"}


def number(name: str, *, formatter: str | None = None) -> dict[str, Any]:
    field: dict[str, Any] = {"name": name, "type": "number"}
    if formatter:
        field["property"] = {"formatter": formatter}
    return field


def datetime_field(name: str, *, formatter: str = "yyyy-MM-dd") -> dict[str, Any]:
    return {"name": name, "type": "datetime", "property": {"date_formatter": formatter, "auto_fill": False}}


def single_select(name: str, options: Iterable[str]) -> dict[str, Any]:
    return {"name": name, "type": "single_select", "options": [opt for opt in options if str(opt).strip()]}


def multi_select(name: str, options: Iterable[str]) -> dict[str, Any]:
    return {"name": name, "type": "multi_select", "options": [opt for opt in options if str(opt).strip()]}


def url(name: str) -> dict[str, Any]:
    return {"name": name, "type": "url"}


def checkbox(name: str) -> dict[str, Any]:
    return {"name": name, "type": "checkbox"}


def formula(name: str, expression: str) -> dict[str, Any]:
    return {"name": name, "type": "formula", "property": {"formula_expression": expression}}


def autonumber(name: str) -> dict[str, Any]:
    return {"name": name, "type": "auto_number"}


def _base_options() -> list[str]:
    return ["苏州", "广东", "合计"]


def t01_fields() -> list[dict[str, Any]]:
    return [
        text("record_key"),
        datetime_field("month", formatter="yyyy-MM-dd"),
        single_select("base", _base_options()),
        number("gmv", formatter="0.00"),
        number("effective_sales", formatter="0.00"),
        number("service_fee_income", formatter="0.00"),
        number("total_orders", formatter="0"),
        number("auction_orders", formatter="0"),
        number("fixed_price_orders", formatter="0"),
        formula("avg_order_value", "IF([gmv]>0,[gmv]/[total_orders],0)"),
        number("sku_listed", formatter="0"),
        number("sku_sold", formatter="0"),
        formula("listing_conversion_rate", "IF([sku_listed]>0,[sku_sold]/[sku_listed],0)"),
        number("items_received", formatter="0"),
        number("items_rejected", formatter="0"),
        formula("rejection_rate", "IF([items_received]>0,[items_rejected]/[items_received],0)"),
        number("active_sellers", formatter="0"),
        formula("avg_consign_per_seller", "IF([active_sellers]>0,[items_received]/[active_sellers],0)"),
        number("new_customers", formatter="0"),
        number("mau", formatter="0"),
        number("return_rate", formatter="0.00%"),
        number("stale_items_60d", formatter="0"),
        number("auction_success_rate", formatter="0.00%"),
        number("avg_bid_rounds", formatter="0.0"),
        number("inventory_turnover_days", formatter="0.0"),
        number("daily_auth_capacity", formatter="0"),
        text("notes", multiline=True),
    ]


def t02_fields() -> list[dict[str, Any]]:
    return [
        text("record_key"),
        datetime_field("month", formatter="yyyy-MM-dd"),
        number("revenue_commission", formatter="0.00"),
        number("revenue_membership", formatter="0.00"),
        number("revenue_ip_content", formatter="0.00"),
        number("revenue_other", formatter="0.00"),
        formula("revenue_total", "[revenue_commission]+[revenue_membership]+[revenue_ip_content]+[revenue_other]"),
        number("cost_salary", formatter="0.00"),
        number("cost_rent", formatter="0.00"),
        number("cost_tech", formatter="0.00"),
        number("cost_logistics", formatter="0.00"),
        number("cost_marketing", formatter="0.00"),
        number("cost_auth", formatter="0.00"),
        number("cost_travel", formatter="0.00"),
        number("cost_platform_fee", formatter="0.00"),
        number("cost_other", formatter="0.00"),
        formula(
            "opex_total",
            "[cost_salary]+[cost_rent]+[cost_tech]+[cost_logistics]+[cost_marketing]+[cost_auth]+[cost_travel]+[cost_platform_fee]+[cost_other]",
        ),
        formula("gross_profit", "[revenue_total]-[cost_platform_fee]"),
        formula("operating_profit", "[revenue_total]-[opex_total]"),
        formula("operating_margin", "IF([revenue_total]>0,[operating_profit]/[revenue_total],0)"),
        number("cash_inflow_operations", formatter="0.00"),
        number("cash_outflow_operations", formatter="0.00"),
        formula("net_cash_operations", "[cash_inflow_operations]-[cash_outflow_operations]"),
        number("borrowings", formatter="0.00"),
        number("cash_balance", formatter="0.00"),
        number("headcount", formatter="0"),
        number("auth_team_size", formatter="0"),
        text("notes", multiline=True),
    ]


def t03_fields() -> list[dict[str, Any]]:
    channel_fields = [
        number("new_customers_total", formatter="0"),
        number("new_customers_douyin", formatter="0"),
        number("new_customers_xiaohongshu", formatter="0"),
        number("new_customers_video_account", formatter="0"),
        number("new_customers_wechat", formatter="0"),
        number("new_customers_miniprogram", formatter="0"),
        number("new_customers_private_domain", formatter="0"),
        number("new_customers_offline", formatter="0"),
    ]
    layer_fields = [
        number("head_customers_count", formatter="0"),
        number("head_revenue", formatter="0.00"),
        number("head_revenue_share", formatter="0.00%"),
        number("waist_customers_count", formatter="0"),
        number("waist_revenue", formatter="0.00"),
        number("waist_revenue_share", formatter="0.00%"),
        number("tail_customers_count", formatter="0"),
        number("tail_revenue", formatter="0.00"),
        number("tail_revenue_share", formatter="0.00%"),
    ]
    lifecycle_fields = [
        number("registered_members", formatter="0"),
        number("paying_members", formatter="0"),
        number("member_conversion_rate", formatter="0.00%"),
        number("repurchase_rate", formatter="0.00%"),
        number("ltv", formatter="0.00"),
        number("churn_count_90d", formatter="0"),
        number("churn_rate_90d", formatter="0.00%"),
        number("member_signup_count", formatter="0"),
        number("member_order_conversion_rate", formatter="0.00%"),
    ]
    region_fields = [
        text("region"),
        number("region_user_count", formatter="0"),
        number("region_arpu", formatter="0.00"),
    ]
    complaint_fields = [
        number("complaint_count", formatter="0"),
        text("complaint_type"),
        number("avg_handle_time_days", formatter="0.0"),
        number("satisfaction_score", formatter="0.0"),
    ]
    return [
        text("record_key"),
        datetime_field("month", formatter="yyyy-MM-dd"),
        single_select("base", _base_options()),
        single_select("segment_type", ["客户分层", "复购", "生命周期", "流失", "会员", "区域", "客诉", "新客"]),
        text("segment_name"),
        *layer_fields,
        *lifecycle_fields,
        *channel_fields,
        *region_fields,
        *complaint_fields,
        text("notes", multiline=True),
    ]


def t04_fields() -> list[dict[str, Any]]:
    return [
        text("record_key"),
        datetime_field("month", formatter="yyyy-MM-dd"),
        single_select("base", _base_options()),
        text("category"),
        number("items_received", formatter="0"),
        number("items_listed", formatter="0"),
        number("items_sold", formatter="0"),
        formula("sell_through_rate", "IF([items_listed]>0,[items_sold]/[items_listed],0)"),
        number("gmv", formatter="0.00"),
        number("effective_sales", formatter="0.00"),
        number("auction_orders", formatter="0"),
        number("fixed_price_orders", formatter="0"),
        number("avg_unit_price", formatter="0.00"),
        number("inventory_turnover_days", formatter="0.0"),
        number("listing_count", formatter="0"),
        number("delisting_count", formatter="0"),
        number("auth_team_size", formatter="0"),
        number("auth_output", formatter="0"),
        number("stale_items_60d", formatter="0"),
        number("return_rate", formatter="0.00%"),
        text("notes", multiline=True),
    ]


def t05_fields() -> list[dict[str, Any]]:
    return [
        text("record_key"),
        datetime_field("month", formatter="yyyy-MM-dd"),
        single_select("base", _base_options()),
        number("logistics_outbound_tickets", formatter="0"),
        number("logistics_inbound_tickets", formatter="0"),
        number("logistics_outbound_cost", formatter="0.00"),
        number("logistics_inbound_cost", formatter="0.00"),
        formula("logistics_total_cost", "[logistics_outbound_cost]+[logistics_inbound_cost]"),
        formula(
            "logistics_avg_ticket_cost",
            "IF(([logistics_outbound_tickets]+[logistics_inbound_tickets])>0,[logistics_total_cost]/([logistics_outbound_tickets]+[logistics_inbound_tickets]),0)",
        ),
        number("avg_ticket_cost_outbound", formatter="0.00"),
        number("avg_ticket_cost_inbound", formatter="0.00"),
        number("sop_days_inbound_to_listed", formatter="0.0"),
        number("inventory_turnover_days", formatter="0.0"),
        number("rejection_rate", formatter="0.00%"),
        number("inspection_pass_rate", formatter="0.00%"),
        number("daily_auth_capacity", formatter="0"),
        text("notes", multiline=True),
    ]


def t06_fields() -> list[dict[str, Any]]:
    return [
        text("record_key"),
        datetime_field("month", formatter="yyyy-MM-dd"),
        single_select("platform", ["抖音", "视频号", "小红书", "公众号", "直播", "私域"]),
        single_select("content_type", ["杨老师IP", "品类专家IP", "直播", "投放", "其他内容"]),
        number("posts_count", formatter="0"),
        number("views", formatter="0"),
        number("engagements", formatter="0"),
        number("followers", formatter="0"),
        number("gmv_from_content", formatter="0.00"),
        number("live_sessions", formatter="0"),
        number("live_avg_viewers", formatter="0"),
        number("live_gmv", formatter="0.00"),
        number("paid_spend", formatter="0.00"),
        number("paid_views", formatter="0"),
        number("paid_engagements", formatter="0"),
        number("roi", formatter="0.00"),
        number("conversion_rate", formatter="0.00%"),
        text("notes", multiline=True),
    ]


def t07_fields() -> list[dict[str, Any]]:
    return [
        text("record_key"),
        text("scenario"),
        text("year"),
        number("annual_gmv", formatter="0.00"),
        number("annual_revenue", formatter="0.00"),
        number("rev_commission", formatter="0.00"),
        number("rev_ip_content", formatter="0.00"),
        number("rev_membership", formatter="0.00"),
        number("rev_data_ad", formatter="0.00"),
        number("annual_opex", formatter="0.00"),
        number("total_orders", formatter="0"),
        number("monthly_sku_needed", formatter="0"),
        number("monthly_sellers_needed", formatter="0"),
        text("assumptions_note", multiline=True),
    ]


def t08_fields() -> list[dict[str, Any]]:
    return [
        text("record_key"),
        text("company"),
        text("country"),
        text("model_type"),
        text("data_year"),
        number("gmv", formatter="0.00"),
        number("revenue", formatter="0.00"),
        number("take_rate", formatter="0.00"),
        number("gross_margin", formatter="0.00"),
        number("ebitda_margin", formatter="0.00"),
        number("headcount", formatter="0"),
        number("auth_team_size", formatter="0"),
        number("active_buyers", formatter="0"),
        number("active_sellers", formatter="0"),
        number("category_count", formatter="0"),
        number("countries_served", formatter="0"),
        text("ai_capability"),
        number("funding_total", formatter="0.00"),
        number("latest_valuation", formatter="0.00"),
        text("key_strength", multiline=True),
        text("key_weakness", multiline=True),
        text("lesson_for_boomerang", multiline=True),
    ]


def t09_fields() -> list[dict[str, Any]]:
    return [
        text("record_key"),
        text("initiative_id"),
        text("dimension"),
        text("initiative_name"),
        single_select("priority", ["P0关键路径", "P1重要", "P2增强"]),
        text("target_quarter"),
        single_select("status", ["待启动", "筹备中", "进行中", "已完成", "暂停"]),
        number("estimated_investment", formatter="0.00"),
        number("expected_revenue_impact", formatter="0.00"),
        text("benchmark_ref", multiline=True),
        text("kpi_metric"),
        text("kpi_current"),
        text("kpi_target"),
    ]


def t10_fields() -> list[dict[str, Any]]:
    return [
        text("record_key"),
        text("round"),
        text("target_year"),
        number("gmv_basis", formatter="0.00"),
        number("revenue_basis", formatter="0.00"),
        number("valuation_multiple_low", formatter="0.00"),
        number("valuation_multiple_high", formatter="0.00"),
        number("funding_amount", formatter="0.00"),
        number("dilution_pct", formatter="0.00%"),
        text("use_of_funds", multiline=True),
        text("key_milestones", multiline=True),
        text("benchmark_company"),
        number("benchmark_multiple", formatter="0.00"),
    ]


def t11_fields() -> list[dict[str, Any]]:
    return [
        text("record_key"),
        datetime_field("month", formatter="yyyy-MM-dd"),
        number("gmv", formatter="0.00"),
        number("effective_sales", formatter="0.00"),
        number("revenue_total", formatter="0.00"),
        number("service_fee_income", formatter="0.00"),
        number("total_orders", formatter="0"),
        number("active_sellers", formatter="0"),
        number("new_customers", formatter="0"),
        number("mau", formatter="0"),
        number("inventory_turnover_days", formatter="0.0"),
        number("return_rate", formatter="0.00%"),
        number("opex_total", formatter="0.00"),
        number("operating_profit", formatter="0.00"),
        number("operating_margin", formatter="0.00%"),
        text("notes", multiline=True),
    ]


def t12_fields() -> list[dict[str, Any]]:
    return [
        text("record_key"),
        text("config_key"),
        text("config_value", multiline=True),
        text("config_group"),
        text("source_sheet"),
        text("source_note", multiline=True),
        datetime_field("updated_at", formatter="yyyy-MM-dd"),
        text("updated_by"),
        checkbox("is_active"),
        text("notes", multiline=True),
    ]


TABLE_SPECS = [
    {
        "table_key": "T01",
        "table_name": "T01_月度经营数据",
        "primary_field": "record_key",
        "layer": "录入层",
        "fields": t01_fields(),
    },
    {
        "table_key": "T02",
        "table_name": "T02_月度财务数据",
        "primary_field": "record_key",
        "layer": "录入层",
        "fields": t02_fields(),
    },
    {
        "table_key": "T03",
        "table_name": "T03_客户分析",
        "primary_field": "record_key",
        "layer": "业务层",
        "fields": t03_fields(),
    },
    {
        "table_key": "T04",
        "table_name": "T04_品类分析",
        "primary_field": "record_key",
        "layer": "业务层",
        "fields": t04_fields(),
    },
    {
        "table_key": "T05",
        "table_name": "T05_供应链效率",
        "primary_field": "record_key",
        "layer": "业务层",
        "fields": t05_fields(),
    },
    {
        "table_key": "T06",
        "table_name": "T06_内容与IP",
        "primary_field": "record_key",
        "layer": "业务层",
        "fields": t06_fields(),
    },
    {
        "table_key": "T07",
        "table_name": "T07_财务建模",
        "primary_field": "record_key",
        "layer": "分析层",
        "fields": t07_fields(),
    },
    {
        "table_key": "T08",
        "table_name": "T08_对标矩阵",
        "primary_field": "record_key",
        "layer": "分析层",
        "fields": t08_fields(),
    },
    {
        "table_key": "T09",
        "table_name": "T09_进化追踪",
        "primary_field": "record_key",
        "layer": "分析层",
        "fields": t09_fields(),
    },
    {
        "table_key": "T10",
        "table_name": "T10_估值测算",
        "primary_field": "record_key",
        "layer": "分析层",
        "fields": t10_fields(),
    },
    {
        "table_key": "T11",
        "table_name": "T11_月度经营快照",
        "primary_field": "record_key",
        "layer": "补充",
        "fields": t11_fields(),
    },
    {
        "table_key": "T12",
        "table_name": "T12_元数据与配置",
        "primary_field": "record_key",
        "layer": "补充",
        "fields": t12_fields(),
    },
]


INFERENCE_NOTES = {
    "T03": "字段由TS-BRM-02映射表与客户分析Sheet清单反推，后续可按实际数据源增删。",
    "T04": "字段由TS-BRM-02品类分析映射反推，暂不含完整品类枚举。",
    "T05": "字段由TS-BRM-02供应链效率映射反推。",
    "T06": "字段由TS-BRM-02内容与IP映射反推。",
    "T11": "快照字段用于仪表盘聚合，后续可与T01/T02口径对齐。",
    "T12": "元数据与配置字段用于记录映射口径与基准说明。",
}
