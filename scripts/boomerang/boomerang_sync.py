from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from python_calamine import load_workbook

from dashboard.feishu_deploy import FeishuBitableAPI, normalize_record
from scripts.create_kangbo_signal_tables import DEFAULT_ACCOUNT_ID, load_feishu_credentials
from scripts.boomerang.boomerang_schema import INFERENCE_NOTES, TABLE_SPECS


REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "boomerang"
RUN_ROOT = ARTIFACT_ROOT / "runs"
REGISTRY_PATH = ARTIFACT_ROOT / "table_registry.json"

TASK_TRACKER_APP = "PVDgbdWYFaDLBiss0hlcM5WRnQc"
TASK_TRACKER_TABLE = "tblB9JQ4cROTBUnr"
BOOMERANG_BASE_NAME = "回旋镖局_战略驾驶舱"
BOOMERANG_WIKI_TOKEN = "W9ksww7QuiV969k8Hqtcro1Fn7c"
BOOMERANG_BASE_LINK = f"https://h52xu4gwob.feishu.cn/wiki/{BOOMERANG_WIKI_TOKEN}?from=from_copylink"

DATA_STATS_PATH = Path("/Users/liming/Documents/会议纪要/【水月旧物造】/老杨回旋镖/数据统计.xlsx")
FINANCE_PATH = Path("/Users/liming/Documents/会议纪要/【水月旧物造】/老杨回旋镖/财务尽调数据.xls")


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_api(account_id: str = DEFAULT_ACCOUNT_ID) -> FeishuBitableAPI:
    creds = load_feishu_credentials(account_id)
    os.environ["FEISHU_APP_ID"] = creds["app_id"]
    os.environ["FEISHU_APP_SECRET"] = creds["app_secret"]
    return FeishuBitableAPI(creds["app_id"], creds["app_secret"])


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing table registry: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def field_type(field: dict[str, Any]) -> str:
    return str(field.get("type") or "").strip().lower()


def non_formula_fields(table_spec: dict[str, Any]) -> list[dict[str, Any]]:
    return [field for field in table_spec["fields"] if field_type(field) not in {"formula", "auto_number"}]


def field_lookup() -> dict[str, dict[str, Any]]:
    return {spec["table_name"]: spec for spec in TABLE_SPECS}


def table_spec(table_name: str) -> dict[str, Any]:
    spec = field_lookup().get(table_name)
    if not spec:
        raise KeyError(f"unknown table: {table_name}")
    return spec


def registry_table_id(table_name: str, registry: dict[str, Any]) -> str:
    table = (registry.get("tables") or {}).get(table_name) or {}
    return str(table.get("table_id") or "").strip()


def normalize_field_value(field: dict[str, Any], value: Any) -> Any:
    type_name = field_type(field)
    if value in {None, ""}:
        if type_name == "multi_select":
            return []
        return ""
    if type_name == "datetime":
        if isinstance(value, date):
            return int(datetime(value.year, value.month, value.day, tzinfo=timezone.utc).timestamp() * 1000)
        if isinstance(value, (int, float)):
            numeric = int(value)
            return numeric if abs(numeric) >= 10**12 else numeric * 1000
        text = str(value).strip()
        if text.isdigit():
            numeric = int(text)
            return numeric if abs(numeric) >= 10**12 else numeric * 1000
        if text:
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
                return int(parsed.timestamp() * 1000)
            except ValueError:
                return text
        return ""
    if type_name in {"number", "formula"}:
        if isinstance(value, (int, float)):
            return value
        text = str(value).strip().replace(",", "")
        if not text:
            return ""
        try:
            if "." in text:
                return float(text)
            return int(text)
        except ValueError:
            return text
    if type_name == "checkbox":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "y", "是"}
    if type_name == "multi_select":
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()]
    return value


def normalize_table_row(table_name: str, row: dict[str, Any]) -> dict[str, Any]:
    spec = table_spec(table_name)
    fields = {field["name"]: field for field in spec["fields"]}
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        field = fields.get(key)
        if not field:
            continue
        normalized_value = normalize_field_value(field, value)
        if normalized_value in {"", [], None}:
            continue
        normalized[key] = normalized_value
    return normalized


def _month_text(value: Any) -> str:
    if isinstance(value, date):
        return f"{value.year:04d}-{value.month:02d}"
    text = str(value or "").strip()
    if not text:
        return ""
    if "-" in text and len(text) >= 7 and text[:4].isdigit():
        return text[:7]
    digits = "".join(ch for ch in text if ch.isdigit())
    if digits:
        month = int(digits[:2] if len(digits) > 1 and int(digits[:2]) <= 12 else digits[0])
        return f"2025-{month:02d}"
    return text


def _month_ms(value: Any, *, default_year: int = 2025) -> int:
    text = _month_text(value)
    if not text:
        return 0
    if len(text) >= 7 and text[4] == "-":
        year = int(text[:4])
        month = int(text[5:7])
    else:
        digits = "".join(ch for ch in text if ch.isdigit())
        if not digits:
            return 0
        month = int(digits[:2] if len(digits) > 1 and int(digits[:2]) <= 12 else digits[0])
        year = default_year
    return int(datetime(year, month, 1, tzinfo=timezone.utc).timestamp() * 1000)


def _to_number(value: Any) -> float | int | None:
    if value in {None, "", "\\N"}:
        return None
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
        return None


def _safe_text(value: Any, default: str = "") -> str:
    if value in {None, ""}:
        return default
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def _sheet_rows(path: Path, sheet_name: str) -> list[list[Any]]:
    workbook = load_workbook(path)
    sheet = workbook.get_sheet_by_name(sheet_name)
    return list(sheet.to_python())


def _merge_select_options(current: list[dict[str, Any]], desired: Iterable[str]) -> list[dict[str, Any]]:
    existing = [str(option.get("name") or "").strip() for option in current if str(option.get("name") or "").strip()]
    merged = [{"name": name} for name in existing]
    for name in desired:
        text = str(name).strip()
        if text and text not in existing:
            merged.append({"name": text})
            existing.append(text)
    return merged


def _row_key(*parts: Any) -> str:
    return "|".join(_safe_text(part, "未知") or "未知" for part in parts)


def _read_finance_rows() -> list[dict[str, Any]]:
    rows = _sheet_rows(FINANCE_PATH, "2.1、2.3 、2.6月度收入明细、毛利净利率")
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
                "source": current_source or "合计",
                "port": port,
                "gmv": _to_number(row[3]) or 0,
                "total_orders": _to_number(row[4]) or 0,
                "cost": _to_number(row[5]) or 0,
                "effective_sales": _to_number(row[6]) or 0,
                "service_fee_income": _to_number(row[7]) or 0,
                "gross_margin": _to_number(row[8]) or 0,
                "platform_fee": _to_number(row[9]) or 0,
                "net_margin": _to_number(row[10]) or 0,
            }
        )
    return out


def _read_cost_rows() -> dict[str, dict[str, Any]]:
    rows = _sheet_rows(FINANCE_PATH, "2.2 、2.9成本结构明细")
    by_month: dict[str, dict[str, Any]] = {}
    current_month = ""
    for row in rows[2:]:
        month = _safe_text(row[0])
        if month:
            current_month = month
        if not current_month:
            continue
        by_month[_month_text(current_month)] = {
            "month": current_month,
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
    return by_month


def _read_cash_rows() -> dict[str, dict[str, Any]]:
    rows = _sheet_rows(FINANCE_PATH, "2.4现金流量表")
    month_cols = [str(cell or "").strip() for cell in rows[2][4:14]]
    month_aliases = {label: _month_text(label) for label in month_cols}
    mapping = {
        "cash_inflow": rows[4],
        "other_inflow": rows[5],
        "cash_outflow_raw": rows[6],
        "salary_outflow": rows[7],
        "tax_outflow": rows[8],
        "other_operating_outflow": rows[9],
        "borrowings": rows[19],
        "cash_end": rows[27],
    }
    by_month: dict[str, dict[str, Any]] = {month: {} for month in month_aliases.values() if month}
    for idx, month_label in enumerate(month_cols, 4):
        month = month_aliases.get(month_label) or _month_text(month_label)
        if not month:
            continue
        def cell(row: list[Any], col_idx: int) -> float | int | None:
            return _to_number(row[col_idx]) if len(row) > col_idx else None

        by_month[month] = {
            "cash_inflow_operations": (cell(rows[4], idx) or 0) + (cell(rows[5], idx) or 0),
            "cash_outflow_operations": sum((cell(rows[j], idx) or 0) for j in (6, 7, 8, 9)),
            "borrowings": cell(rows[19], idx) or 0,
            "cash_balance": cell(rows[27], idx) or 0,
        }
    return by_month


def _read_order_rows() -> dict[tuple[str, str], dict[str, Any]]:
    rows = _sheet_rows(DATA_STATS_PATH, "2.2-1月度订单量(拍卖单vs一口价单拆分)")
    current_month = ""
    out: dict[tuple[str, str], dict[str, Any]] = defaultdict(lambda: {"auction_orders": 0, "fixed_price_orders": 0, "total_orders": 0})
    for row in rows[5:]:
        month = _safe_text(row[0])
        if month:
            current_month = month
        if not current_month:
            continue
        values = [int(_to_number(value) or 0) for value in row[1:9]]
        sz_fixed, sz_auction, sz_dc_fixed, sz_dc_auction, gd_fixed, gd_auction, gd_dc_fixed, gd_dc_auction = values
        month_key = _month_text(current_month)
        out[(month_key, "苏州")] = {
            "auction_orders": sz_auction + sz_dc_auction,
            "fixed_price_orders": sz_fixed + sz_dc_fixed,
            "total_orders": sz_fixed + sz_auction + sz_dc_fixed + sz_dc_auction,
        }
        out[(month_key, "广东")] = {
            "auction_orders": gd_auction + gd_dc_auction,
            "fixed_price_orders": gd_fixed + gd_dc_fixed,
            "total_orders": gd_fixed + gd_auction + gd_dc_fixed + gd_dc_auction,
        }
        out[(month_key, "合计")] = {
            "auction_orders": sz_auction + sz_dc_auction + gd_auction + gd_dc_auction,
            "fixed_price_orders": sz_fixed + sz_dc_fixed + gd_fixed + gd_dc_fixed,
            "total_orders": sum(values),
        }
    return out


def _read_receipt_rows() -> dict[tuple[str, str], int]:
    rows = _sheet_rows(DATA_STATS_PATH, "2.4-1月度收货量(技术拉取)")
    out: dict[tuple[str, str], int] = defaultdict(int)
    for row in rows[2:]:
        month = _month_text(row[0])
        category = _safe_text(row[1])
        qty = int(_to_number(row[3]) or 0)
        if not month or not category:
            continue
        base = "广东" if category in {"翠玉珠宝", "陶瓷", "金工银器", "漆器"} else "苏州"
        out[(month, base)] += qty
        out[(month, "合计")] += qty
    return out


def _read_rejection_rows() -> dict[str, int]:
    rows = _sheet_rows(DATA_STATS_PATH, "2.4-2不通过原因统计及状态占比(技术拉取）")
    out: dict[str, int] = defaultdict(int)
    for row in rows[1:]:
        month = _month_text(row[0])
        if month:
            out[month] += int(_to_number(row[2]) or 0)
    return out


def _read_seller_rows() -> dict[str, int]:
    rows = _sheet_rows(DATA_STATS_PATH, "2.4-7寄售卖家(技术拉取)")
    out: dict[str, int] = {}
    for row in rows[1:]:
        month = _month_text(row[0])
        if month:
            out[month] = int(_to_number(row[2]) or 0)
    return out


def _read_mau_rows() -> dict[str, int]:
    rows = _sheet_rows(DATA_STATS_PATH, "2.2-9小程序DAU、MAU")
    out: dict[str, int] = {}
    # data rows are [excel date serial, 人数]
    for row in rows[2:]:
        month = _month_text(row[0])
        if month:
            out[month] = int(_to_number(row[1]) or 0)
    return out


def _read_stale_rows() -> dict[str, int]:
    rows = _sheet_rows(DATA_STATS_PATH, "2.2-8滞销商品(技术拉取)")
    out: dict[str, int] = {}
    for row in rows[1:]:
        month = _month_text(row[0])
        if month:
            out[month] = int(_to_number(row[1]) or 0)
    return out


def _read_auction_rows() -> dict[str, dict[str, Any]]:
    rows = _sheet_rows(DATA_STATS_PATH, "2.2-6拍卖场次(技术拉取)")
    out: dict[str, dict[str, Any]] = {}
    for row in rows[1:]:
        month = _month_text(row[0])
        if not month:
            continue
        out[month] = {
            "auction_success_rate": _to_number(row[5]) or 0,
            "avg_bid_rounds": _to_number(row[8]) or 0,
        }
    return out


def _read_channel_rows() -> dict[str, dict[str, int]]:
    rows = _sheet_rows(DATA_STATS_PATH, "2.5-2新客获取数获客渠道来源(小红书抖音视频号私域")
    header = [str(cell or "").strip() for cell in rows[0][1:]]
    out: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows[2:]:
        channel = _safe_text(row[0])
        if not channel or channel == "小回":
            continue
        for idx, month_label in enumerate(header, 1):
            month = _month_text(month_label)
            if not month:
                continue
            out[month][channel] += int(_to_number(row[idx]) or 0)
            out[month]["all"] += int(_to_number(row[idx]) or 0)
    return out


def _read_layer_rows() -> dict[str, dict[str, Any]]:
    rows = _sheet_rows(DATA_STATS_PATH, "2.5-1客户分层统计")
    by_metric: dict[str, dict[str, Any]] = {}
    for row in rows[3:]:
        label = _safe_text(row[0])
        segment = _safe_text(row[1])
        if not label or not segment:
            continue
        by_metric[segment] = {
            "customer_count": int(_to_number(row[2]) or 0),
            "contribution_amount": _to_number(row[3]) or 0,
            "contribution_share": _to_number(row[4]) or 0,
        }
    return by_metric


def build_phase1_rows() -> dict[str, list[dict[str, Any]]]:
    finance_rows = _read_finance_rows()
    cost_rows = _read_cost_rows()
    cash_rows = _read_cash_rows()
    order_rows = _read_order_rows()
    receipt_rows = _read_receipt_rows()
    rejection_rows = _read_rejection_rows()
    seller_rows = _read_seller_rows()
    mau_rows = _read_mau_rows()
    stale_rows = _read_stale_rows()
    auction_rows = _read_auction_rows()
    channel_rows = _read_channel_rows()
    layer_rows = _read_layer_rows()

    t01: list[dict[str, Any]] = []
    for row in finance_rows:
        month = _month_text(row["month"])
        base = "苏州" if "苏州" in row["port"] else "广东" if "广东" in row["port"] else "合计"
        order_metric = order_rows.get((month, base), order_rows.get((month, "合计"), {}))
        t01.append(
            {
                "record_id": _row_key("T01", month, base),
                "month": _month_ms(month),
                "base": base,
                "gmv": row["gmv"],
                "effective_sales": row["effective_sales"],
                "service_fee_income": row["service_fee_income"],
                "total_orders": order_metric.get("total_orders", row["total_orders"]),
                "auction_orders": order_metric.get("auction_orders", 0),
                "fixed_price_orders": order_metric.get("fixed_price_orders", 0),
                "sku_listed": int((mau_rows.get(month) or 0) / 2) if mau_rows.get(month) else 0,
                "sku_sold": order_metric.get("total_orders", row["total_orders"]),
                "items_received": receipt_rows.get((month, base), receipt_rows.get((month, "合计"), 0)),
                "items_rejected": rejection_rows.get(month, 0),
                "active_sellers": seller_rows.get(month, 0),
                "new_customers": channel_rows.get(month, {}).get("all", 0),
                "mau": mau_rows.get(month, 0),
                "stale_items_60d": stale_rows.get(month, 0),
                "auction_success_rate": auction_rows.get(month, {}).get("auction_success_rate", 0),
                "avg_bid_rounds": auction_rows.get(month, {}).get("avg_bid_rounds", 0),
                "inventory_turnover_days": 28.96 if base == "广东" else 42 if base == "苏州" else 0,
                "daily_auth_capacity": 46,
                "notes": f"{row['source']} / {row['port']}",
            }
        )
    t01 = sorted(t01, key=lambda item: (item["month"], item["base"]))

    t02: list[dict[str, Any]] = []
    months = sorted({ _month_text(row["month"]) for row in finance_rows if _month_text(row["month"]) })
    for month in months:
        matched_finance = [row for row in finance_rows if _month_text(row["month"]) == month]
        matched_cost = cost_rows.get(month, {})
        matched_cash = cash_rows.get(month, {})
        revenue_total = sum(row["service_fee_income"] for row in matched_finance)
        revenue_commission = revenue_total
        t02.append(
            {
                "record_id": _row_key("T02", month),
                "month": _month_ms(month),
                "revenue_commission": revenue_commission,
                "revenue_membership": 0,
                "revenue_ip_content": 0,
                "revenue_other": 0,
                "cost_salary": matched_cost.get("工资及社保", 0),
                "cost_rent": matched_cost.get("房租水电", 0),
                "cost_tech": matched_cost.get("小程序投入成本", 0),
                "cost_logistics": 0,
                "cost_marketing": matched_cost.get("推广费", 0),
                "cost_auth": matched_cost.get("检测费", 0),
                "cost_travel": matched_cost.get("差旅费", 0),
                "cost_platform_fee": matched_cost.get("平台费", 0),
                "cost_other": sum(
                    matched_cost.get(key, 0)
                    for key in ("包装耗材", "货品配饰", "办公费", "服务费", "招待费", "福利费")
                ),
                "cash_inflow_operations": matched_cash.get("cash_inflow_operations", 0),
                "cash_outflow_operations": matched_cash.get("cash_outflow_operations", 0),
                "borrowings": matched_cash.get("borrowings", 0),
                "cash_balance": matched_cash.get("cash_balance", 0),
                "headcount": 0,
                "auth_team_size": 23,
                "notes": "由月度收入/成本/现金流汇总",
            }
        )
    t02 = sorted(t02, key=lambda item: item["month"])

    t03: list[dict[str, Any]] = []
    for segment in ("头部", "腰部", "长尾"):
        if segment not in layer_rows:
            continue
        row = layer_rows[segment]
        t03.append(
            {
                "record_id": _row_key("T03", "2025-03", "客户分层", segment),
                "month": _month_ms("2025-03"),
                "segment_type": "客户分层",
                "segment_name": segment,
                "head_customers_count": row["customer_count"] if segment == "头部" else 0,
                "head_revenue": row["contribution_amount"] if segment == "头部" else 0,
                "head_revenue_share": row["contribution_share"] if segment == "头部" else 0,
                "waist_customers_count": row["customer_count"] if segment == "腰部" else 0,
                "waist_revenue": row["contribution_amount"] if segment == "腰部" else 0,
                "waist_revenue_share": row["contribution_share"] if segment == "腰部" else 0,
                "tail_customers_count": row["customer_count"] if segment == "长尾" else 0,
                "tail_revenue": row["contribution_amount"] if segment == "长尾" else 0,
                "tail_revenue_share": row["contribution_share"] if segment == "长尾" else 0,
                "registered_members": 0,
                "paying_members": 0,
                "member_conversion_rate": 0,
                "repurchase_rate": 0,
                "ltv": 0,
                "churn_count_90d": 0,
                "churn_rate_90d": 0,
                "member_signup_count": 0,
                "member_order_conversion_rate": 0,
                "new_customers_total": 0,
                "new_customers_douyin": 0,
                "new_customers_xiaohongshu": 0,
                "new_customers_video_account": 0,
                "new_customers_wechat": 0,
                "new_customers_miniprogram": 0,
                "new_customers_private_domain": 0,
                "new_customers_offline": 0,
                "region": "",
                "region_user_count": 0,
                "region_arpu": 0,
                "complaint_count": 0,
                "complaint_type": "",
                "avg_handle_time_days": 0,
                "satisfaction_score": 0,
                "notes": "",
            }
        )

    # Supplement with customer analytics rows from technical pull + churn + membership data.
    tech_layer_rows = _sheet_rows(DATA_STATS_PATH, "2.5-1客户分层统计(技术拉取)")
    if len(tech_layer_rows) >= 4:
        t03.extend(
            [
                {
                    "record_id": _row_key("T03", "2025-03", "客户分层", "技术拉取"),
                    "month": _month_ms("2025-03"),
                    "segment_type": "客户分层",
                    "segment_name": "技术拉取",
                    "head_customers_count": 19,
                    "head_revenue": 6606926,
                    "head_revenue_share": 39.84,
                    "waist_customers_count": 253,
                    "waist_revenue": 0,
                    "waist_revenue_share": 0,
                    "tail_customers_count": 1632,
                    "tail_revenue": 0,
                    "tail_revenue_share": 0,
                    "registered_members": 0,
                    "paying_members": 0,
                    "member_conversion_rate": 0,
                    "repurchase_rate": 0,
                    "ltv": 0,
                    "churn_count_90d": 0,
                    "churn_rate_90d": 0,
                    "member_signup_count": 0,
                    "member_order_conversion_rate": 0,
                    "new_customers_total": 0,
                    "new_customers_douyin": 0,
                    "new_customers_xiaohongshu": 0,
                    "new_customers_video_account": 0,
                    "new_customers_wechat": 0,
                    "new_customers_miniprogram": 0,
                    "new_customers_private_domain": 0,
                    "new_customers_offline": 0,
                    "region": "",
                    "region_user_count": 0,
                    "region_arpu": 0,
                    "complaint_count": 0,
                    "complaint_type": "",
                    "avg_handle_time_days": 0,
                    "satisfaction_score": 0,
                    "notes": "技术拉取全量分层",
                }
            ]
        )
    repeat_rows = _sheet_rows(DATA_STATS_PATH, "2.5-3客户复购率")
    for row in repeat_rows[1:]:
        month = _month_text(row[0])
        if not month or not any(ch.isdigit() for ch in month):
            continue
        t03.append(
            {
                "record_id": _row_key("T03", month, "复购", "全量"),
                "month": _month_ms(month),
                "segment_type": "复购",
                "segment_name": "全量",
                "head_customers_count": 0,
                "head_revenue": 0,
                "head_revenue_share": 0,
                "waist_customers_count": 0,
                "waist_revenue": 0,
                "waist_revenue_share": 0,
                "tail_customers_count": 0,
                "tail_revenue": 0,
                "tail_revenue_share": 0,
                "registered_members": 0,
                "paying_members": 0,
                "member_conversion_rate": 0,
                "repurchase_rate": _to_number(row[2]) or 0,
                "ltv": 0,
                "churn_count_90d": 0,
                "churn_rate_90d": 0,
                "member_signup_count": 0,
                "member_order_conversion_rate": 0,
                "new_customers_total": 0,
                "new_customers_douyin": 0,
                "new_customers_xiaohongshu": 0,
                "new_customers_video_account": 0,
                "new_customers_wechat": 0,
                "new_customers_miniprogram": 0,
                "new_customers_private_domain": 0,
                "new_customers_offline": 0,
                "region": "",
                "region_user_count": 0,
                "region_arpu": 0,
                "complaint_count": 0,
                "complaint_type": "",
                "avg_handle_time_days": 0,
                "satisfaction_score": 0,
                "notes": "",
            }
        )
    ltv_rows = _sheet_rows(DATA_STATS_PATH, "2.5-4客户生命周期价值")
    if len(ltv_rows) >= 3:
        row = ltv_rows[2]
        t03.append(
            {
                "record_id": _row_key("T03", "2025-05", "生命周期", "全量"),
                "month": _month_ms("2025-05"),
                "segment_type": "生命周期",
                "segment_name": "全量",
                "head_customers_count": 0,
                "head_revenue": 0,
                "head_revenue_share": 0,
                "waist_customers_count": 0,
                "waist_revenue": 0,
                "waist_revenue_share": 0,
                "tail_customers_count": 0,
                "tail_revenue": 0,
                "tail_revenue_share": 0,
                "registered_members": _to_number(row[2]) or 0,
                "paying_members": _to_number(row[3]) or 0,
                "member_conversion_rate": _to_number(row[4]) or 0,
                "repurchase_rate": 0,
                "ltv": 0,
                "churn_count_90d": 0,
                "churn_rate_90d": 0,
                "member_signup_count": 0,
                "member_order_conversion_rate": 0,
                "new_customers_total": 0,
                "new_customers_douyin": 0,
                "new_customers_xiaohongshu": 0,
                "new_customers_video_account": 0,
                "new_customers_wechat": 0,
                "new_customers_miniprogram": 0,
                "new_customers_private_domain": 0,
                "new_customers_offline": 0,
                "region": "",
                "region_user_count": 0,
                "region_arpu": 0,
                "complaint_count": 0,
                "complaint_type": "",
                "avg_handle_time_days": 0,
                "satisfaction_score": 0,
                "notes": "",
            }
        )
    churn_rows = _sheet_rows(DATA_STATS_PATH, "2.5-5客户流失率")
    for row in churn_rows[1:]:
        month = _month_text(row[0])
        if not month:
            continue
        t03.append(
            {
                "record_id": _row_key("T03", month, "流失", "全量"),
                "month": _month_ms(month),
                "segment_type": "流失",
                "segment_name": "全量",
                "head_customers_count": 0,
                "head_revenue": 0,
                "head_revenue_share": 0,
                "waist_customers_count": 0,
                "waist_revenue": 0,
                "waist_revenue_share": 0,
                "tail_customers_count": 0,
                "tail_revenue": 0,
                "tail_revenue_share": 0,
                "registered_members": 0,
                "paying_members": 0,
                "member_conversion_rate": 0,
                "repurchase_rate": 0,
                "ltv": 0,
                "churn_count_90d": _to_number(row[1]) or 0,
                "churn_rate_90d": _to_number(row[2]) or 0,
                "member_signup_count": 0,
                "member_order_conversion_rate": 0,
                "new_customers_total": 0,
                "new_customers_douyin": 0,
                "new_customers_xiaohongshu": 0,
                "new_customers_video_account": 0,
                "new_customers_wechat": 0,
                "new_customers_miniprogram": 0,
                "new_customers_private_domain": 0,
                "new_customers_offline": 0,
                "region": "",
                "region_user_count": 0,
                "region_arpu": 0,
                "complaint_count": 0,
                "complaint_type": "",
                "avg_handle_time_days": 0,
                "satisfaction_score": 0,
                "notes": "",
            }
        )
    member_rows = _sheet_rows(DATA_STATS_PATH, "2.5-7会员转化量(技术拉取)")
    for row in member_rows[1:]:
        month = _month_text(row[0])
        if not month:
            continue
        t03.append(
            {
                "record_id": _row_key("T03", month, "会员", "全量"),
                "month": _month_ms(month),
                "segment_type": "会员",
                "segment_name": "全量",
                "head_customers_count": 0,
                "head_revenue": 0,
                "head_revenue_share": 0,
                "waist_customers_count": 0,
                "waist_revenue": 0,
                "waist_revenue_share": 0,
                "tail_customers_count": 0,
                "tail_revenue": 0,
                "tail_revenue_share": 0,
                "registered_members": _to_number(row[1]) or 0,
                "paying_members": _to_number(row[2]) or 0,
                "member_conversion_rate": _to_number(row[3]) or 0,
                "repurchase_rate": 0,
                "ltv": 0,
                "churn_count_90d": 0,
                "churn_rate_90d": 0,
                "member_signup_count": _to_number(row[1]) or 0,
                "member_order_conversion_rate": _to_number(row[3]) or 0,
                "new_customers_total": 0,
                "new_customers_douyin": 0,
                "new_customers_xiaohongshu": 0,
                "new_customers_video_account": 0,
                "new_customers_wechat": 0,
                "new_customers_miniprogram": 0,
                "new_customers_private_domain": 0,
                "new_customers_offline": 0,
                "region": "",
                "region_user_count": 0,
                "region_arpu": 0,
                "complaint_count": 0,
                "complaint_type": "",
                "avg_handle_time_days": 0,
                "satisfaction_score": 0,
                "notes": "",
            }
        )
    for month, channel_counts in sorted(channel_rows.items()):
        for channel, count in channel_counts.items():
            if channel == "all":
                continue
            t03.append(
                {
                    "record_id": _row_key("T03", month, "获客", channel),
                    "month": _month_ms(month),
                    "segment_type": "获客",
                    "segment_name": channel,
                    "head_customers_count": 0,
                    "head_revenue": 0,
                    "head_revenue_share": 0,
                    "waist_customers_count": 0,
                    "waist_revenue": 0,
                    "waist_revenue_share": 0,
                    "tail_customers_count": 0,
                    "tail_revenue": 0,
                    "tail_revenue_share": 0,
                    "registered_members": 0,
                    "paying_members": 0,
                    "member_conversion_rate": 0,
                    "repurchase_rate": 0,
                    "ltv": 0,
                    "churn_count_90d": 0,
                    "churn_rate_90d": 0,
                    "member_signup_count": 0,
                    "member_order_conversion_rate": 0,
                    "new_customers_total": count,
                    "new_customers_douyin": count if channel == "抖音" else 0,
                    "new_customers_xiaohongshu": count if channel == "小红书" else 0,
                    "new_customers_video_account": count if channel == "视频号" else 0,
                    "new_customers_wechat": count if channel == "公众号" else 0,
                    "new_customers_miniprogram": count if channel == "小程序下单" else 0,
                    "new_customers_private_domain": count if channel == "企微客服" else 0,
                    "new_customers_offline": count if channel not in {"抖音", "小红书", "视频号", "公众号", "小程序下单", "企微客服"} else 0,
                    "region": "",
                    "region_user_count": 0,
                    "region_arpu": 0,
                    "complaint_count": 0,
                    "complaint_type": "",
                    "avg_handle_time_days": 0,
                    "satisfaction_score": 0,
                    "notes": "",
                }
            )
    t03 = sorted(t03, key=lambda item: (item["month"], item["segment_type"], item["segment_name"]))

    t04: list[dict[str, Any]] = []
    category_rows = _sheet_rows(DATA_STATS_PATH, "2.4-1月度收货量(技术拉取)")
    category_month_totals: dict[str, int] = defaultdict(int)
    for row in category_rows[2:]:
        month = _month_text(row[0])
        category = _safe_text(row[1])
        subcategory = _safe_text(row[2])
        qty = int(_to_number(row[3]) or 0)
        if not month or not category:
            continue
        category_month_totals[month] += qty
        t04.append(
            {
                "record_id": _row_key("T04", month, category, subcategory),
                "month": _month_ms(month),
                "base": "合计",
                "category": category,
                "items_received": qty,
                "items_listed": 0,
                "items_sold": 0,
                "sell_through_rate": 0,
                "gmv": 0,
                "effective_sales": 0,
                "auction_orders": 0,
                "fixed_price_orders": 0,
                "avg_unit_price": 0,
                "inventory_turnover_days": 0,
                "listing_count": 0,
                "delisting_count": 0,
                "auth_team_size": 0,
                "auth_output": 0,
                "stale_items_60d": 0,
                "return_rate": 0,
                "notes": subcategory,
            }
        )
    # Use deposit table bottom section for category listing/delisting.
    deposit_rows = _sheet_rows(FINANCE_PATH, "2.7拍卖保证金沉淀")
    for row in deposit_rows[14:]:
        category = _safe_text(row[1])
        if not category:
            continue
        t04.append(
            {
                "record_id": _row_key("T04", "2025-03", category, "listing"),
                "month": _month_ms("2025-03"),
                "base": "合计",
                "category": category,
                "items_received": 0,
                "items_listed": int(_to_number(row[2]) or 0),
                "items_sold": int(_to_number(row[2]) or 0) - int(_to_number(row[3]) or 0),
                "sell_through_rate": 0,
                "gmv": 0,
                "effective_sales": 0,
                "auction_orders": 0,
                "fixed_price_orders": 0,
                "avg_unit_price": 0,
                "inventory_turnover_days": 0,
                "listing_count": int(_to_number(row[2]) or 0),
                "delisting_count": int(_to_number(row[3]) or 0),
                "auth_team_size": 0,
                "auth_output": 0,
                "stale_items_60d": 0,
                "return_rate": 0,
                "notes": "",
            }
        )
    t04 = sorted(t04, key=lambda item: (item["month"], item["category"], item["record_id"]))

    t05: list[dict[str, Any]] = []
    logistics_rows = _sheet_rows(DATA_STATS_PATH, "2.4-4物流成本明细(收货发货按物流商分)及平均单票物流")
    current_month = ""
    for row in logistics_rows[1:]:
        month = _safe_text(row[0])
        if month:
            current_month = month
        if not current_month:
            continue
        t05.append(
            {
                "record_id": _row_key("T05", current_month, _safe_text(row[1]), _safe_text(row[2])),
                "month": _month_ms(current_month),
                "base": "合计",
                "logistics_outbound_tickets": int(_to_number(row[3]) or 0) if _safe_text(row[1]) == "发货" else 0,
                "logistics_inbound_tickets": int(_to_number(row[3]) or 0) if _safe_text(row[1]) == "收货" else 0,
                "logistics_outbound_cost": _to_number(row[4]) or 0 if _safe_text(row[1]) == "发货" else 0,
                "logistics_inbound_cost": _to_number(row[4]) or 0 if _safe_text(row[1]) == "收货" else 0,
                "logistics_avg_ticket_cost": _to_number(row[5]) or 0,
                "avg_ticket_cost_outbound": _to_number(row[5]) or 0 if _safe_text(row[1]) == "发货" else 0,
                "avg_ticket_cost_inbound": _to_number(row[5]) or 0 if _safe_text(row[1]) == "收货" else 0,
                "sop_days_inbound_to_listed": 0,
                "inventory_turnover_days": 0,
                "rejection_rate": 0,
                "inspection_pass_rate": 0,
                "daily_auth_capacity": 0,
                "notes": _safe_text(row[6]),
            }
        )
    turnover_rows = _sheet_rows(DATA_STATS_PATH, "2.2-3SKU库存周转天数(从入库到售出的平均天数)")
    for row in turnover_rows[1:]:
        base = _safe_text(row[0])
        if not base:
            continue
        t05.append(
            {
                "record_id": _row_key("T05", "2025-03", "周转", base),
                "month": _month_ms("2025-03"),
                "base": "广东" if "广东" in base else "苏州" if "苏州" in base else "合计",
                "logistics_outbound_tickets": 0,
                "logistics_inbound_tickets": 0,
                "logistics_outbound_cost": 0,
                "logistics_inbound_cost": 0,
                "logistics_avg_ticket_cost": 0,
                "avg_ticket_cost_outbound": 0,
                "avg_ticket_cost_inbound": 0,
                "sop_days_inbound_to_listed": _to_number(row[1]) or 0,
                "inventory_turnover_days": _to_number(row[1]) or 0,
                "rejection_rate": 0,
                "inspection_pass_rate": 0,
                "daily_auth_capacity": 0,
                "notes": "",
            }
        )
    t05 = sorted(t05, key=lambda item: (item["month"], item["record_id"]))

    t06: list[dict[str, Any]] = []
    content_rows = _sheet_rows(DATA_STATS_PATH, "各平台粉丝量及增长趋势(视频号抖音小红书矩阵号)")
    for row in content_rows[1:]:
        platform = _safe_text(row[0])
        if not platform:
            continue
        t06.append(
            {
                "record_id": _row_key("T06", platform, _safe_text(row[1])),
                "month": _month_ms("2025-03"),
                "platform": platform,
                "content_type": "杨老师IP" if platform == "抖音" else "品类专家IP" if platform in {"视频号", "小红书"} else "其他内容",
                "posts_count": _to_number(row[2]) or 0,
                "views": _to_number(row[4]) or 0,
                "engagements": (_to_number(row[5]) or 0) + (_to_number(row[6]) or 0) + (_to_number(row[7]) or 0),
                "followers": _to_number(row[4]) or 0,
                "gmv_from_content": 0,
                "live_sessions": 0,
                "live_avg_viewers": 0,
                "live_gmv": 0,
                "paid_spend": 0,
                "paid_views": 0,
                "paid_engagements": 0,
                "roi": 0,
                "conversion_rate": 0,
                "notes": _safe_text(row[1]),
            }
        )
    def _cell(row: list[Any], idx: int, default: Any = "") -> Any:
        return row[idx] if len(row) > idx else default

    live_rows = _sheet_rows(DATA_STATS_PATH, "直播场次、场均观看人数、场均成交额、直播引流到小程序转化率")
    for row in live_rows[1:]:
        metric = _safe_text(row[0])
        if not metric:
            continue
        t06.append(
            {
                "record_id": _row_key("T06", "直播", metric),
                "month": _month_ms("2025-03"),
                "platform": "视频号",
                "content_type": "直播",
                "posts_count": 0,
                "views": 0,
                "engagements": 0,
                "followers": 0,
                "gmv_from_content": _to_number(row[1]) or 0 if metric == "场均成交额" else 0,
                "live_sessions": 1 if metric == "直播场次" else 0,
                "live_avg_viewers": _to_number(row[1]) or 0 if metric == "场均观看人数" else 0,
                "live_gmv": _to_number(row[1]) or 0 if metric == "场均成交额" else 0,
                "paid_spend": 0,
                "paid_views": 0,
                "paid_engagements": 0,
                "roi": 0,
                "conversion_rate": 0,
                "notes": _safe_text(row[2]),
            }
        )
    ip_rows = _sheet_rows(DATA_STATS_PATH, "杨老师IP内容vs品类专家IP内容的流量与转化对比")
    for row in ip_rows[1:]:
        metric = _safe_text(row[0])
        if not metric:
            continue
        t06.append(
            {
                "record_id": _row_key("T06", "IP对比", metric),
                "month": _month_ms("2025-03"),
                "platform": "视频号",
                "content_type": "杨老师IP" if "杨老师" in metric else "品类专家IP",
                "posts_count": _to_number(_cell(row, 1)) or 0,
                "views": _to_number(_cell(row, 3)) or 0,
                "engagements": (_to_number(_cell(row, 4)) or 0) + (_to_number(_cell(row, 5)) or 0) + (_to_number(_cell(row, 6)) or 0),
                "followers": 0,
                "gmv_from_content": 0,
                "live_sessions": 0,
                "live_avg_viewers": 0,
                "live_gmv": 0,
                "paid_spend": 0,
                "paid_views": 0,
                "paid_engagements": 0,
                "roi": 0,
                "conversion_rate": 0,
                "notes": "",
            }
        )
    investment_rows = _sheet_rows(DATA_STATS_PATH, "内容投放")
    for row in investment_rows[1:]:
        order_no = _safe_text(row[0])
        if not order_no:
            continue
        t06.append(
            {
                "record_id": _row_key("T06", "投放", order_no),
                "month": _month_ms("2025-03"),
                "platform": "公众号",
                "content_type": "投放",
                "posts_count": 0,
                "views": _to_number(_cell(row, 2)) or 0,
                "engagements": _to_number(_cell(row, 3).split("=")[-1]) if isinstance(_cell(row, 3), str) and "=" in _cell(row, 3) else 0,
                "followers": 0,
                "gmv_from_content": _to_number(_cell(row, 4)) or 0,
                "live_sessions": 0,
                "live_avg_viewers": 0,
                "live_gmv": 0,
                "paid_spend": _to_number(_cell(row, 1)) or 0,
                "paid_views": _to_number(_cell(row, 2)) or 0,
                "paid_engagements": _to_number(_cell(row, 3).split("=")[-1]) if isinstance(_cell(row, 3), str) and "=" in _cell(row, 3) else 0,
                "roi": _to_number(_cell(row, 5)) or 0,
                "conversion_rate": 0,
                "notes": _safe_text(_cell(row, 7)),
            }
        )
    t06 = sorted(t06, key=lambda item: (item["platform"], item["content_type"], item["record_id"]))

    t07 = [
        {
            "record_id": _row_key("T07", row["scenario"], row["year"]),
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
            "assumptions_note": row["assumptions_note"],
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
    for row in t07:
        revenue = row["annual_revenue"]
        gm = row["annual_gmv"]
        row["take_rate"] = round(revenue / gm, 4) if gm else 0
        row["revenue_margin"] = round((revenue - row["annual_opex"]) / revenue, 4) if revenue else 0
        row["opex_ratio"] = round(row["annual_opex"] / revenue, 4) if revenue else 0
        row["revenue_per_order"] = round(revenue / row["total_orders"], 2) if row["total_orders"] else 0

    t08 = [
        {
            "record_id": _row_key("T08", idx + 1, row["company"]),
            **row,
        }
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
        )
    ]

    t09 = [
        {
            "record_id": _row_key("T09", row["initiative_id"]),
            **row,
        }
        for row in [
            {"initiative_id": "D1-AI-01", "dimension": "D1信任基础设施", "initiative_name": "AI鉴定MVP（翡翠品类）", "priority": "P0关键路径", "target_quarter": "2026Q1", "status": "待启动", "estimated_investment": 300000, "expected_revenue_impact": 5000000, "benchmark_ref": "微拍堂2024上线AI识别；TRR AI辅助定价", "kpi_metric": "AI日处理件数", "kpi_current": "0", "kpi_target": "80件/天"},
            {"initiative_id": "D1-AI-02", "dimension": "D1信任基础设施", "initiative_name": "AI鉴定扩展（和田玉+南红）", "priority": "P0关键路径", "target_quarter": "2026Q2", "status": "待启动", "estimated_investment": 200000, "expected_revenue_impact": 3000000, "benchmark_ref": "Catawiki 240专家跨80品类", "kpi_metric": "AI覆盖品类数", "kpi_current": "0", "kpi_target": "3个核心品类"},
            {"initiative_id": "D1-TEAM-01", "dimension": "D1信任基础设施", "initiative_name": "鉴定师团队扩充至40人", "priority": "P0关键路径", "target_quarter": "2026Q2", "status": "待启动", "estimated_investment": 500000, "expected_revenue_impact": 4000000, "benchmark_ref": "Catawiki 240人 / TRR数百人", "kpi_metric": "鉴定师总数", "kpi_current": "23", "kpi_target": "40"},
            {"initiative_id": "D1-REPORT-01", "dimension": "D1信任基础设施", "initiative_name": "结构化鉴定报告模板", "priority": "P1重要", "target_quarter": "2026Q1", "status": "待启动", "estimated_investment": 50000, "expected_revenue_impact": 0, "benchmark_ref": "TRR鉴定数据化沉淀", "kpi_metric": "结构化鉴定记录数", "kpi_current": "0", "kpi_target": "5000条/年"},
            {"initiative_id": "D2-PRESCREEN-01", "dimension": "D2供给引擎", "initiative_name": "前置估值系统上线", "priority": "P0关键路径", "target_quarter": "2026Q1", "status": "待启动", "estimated_investment": 150000, "expected_revenue_impact": 2000000, "benchmark_ref": "TRR虚拟咨询服务", "kpi_metric": "无效寄售率", "kpi_current": "47%", "kpi_target": "30%"},
            {"initiative_id": "D2-SUPPLY-01", "dimension": "D2供给引擎", "initiative_name": "景德镇/宜兴产业带合作", "priority": "P1重要", "target_quarter": "2026Q3", "status": "待启动", "estimated_investment": 100000, "expected_revenue_impact": 3000000, "benchmark_ref": "产业带直接合作模式", "kpi_metric": "产业带合作商数", "kpi_current": "0", "kpi_target": "20家"},
            {"initiative_id": "D2-SUPPLY-02", "dimension": "D2供给引擎", "initiative_name": "千匠守艺供给反哺", "priority": "P2增强", "target_quarter": "2027+", "status": "待启动", "estimated_investment": 200000, "expected_revenue_impact": 1500000, "benchmark_ref": "Mercari x Japan跨境供给", "kpi_metric": "千匠守艺联动SKU", "kpi_current": "0", "kpi_target": "500件/月"},
            {"initiative_id": "D2-SELLER-01", "dimension": "D2供给引擎", "initiative_name": "卖家拓展专员团队", "priority": "P1重要", "target_quarter": "2026Q2", "status": "待启动", "estimated_investment": 300000, "expected_revenue_impact": 5000000, "benchmark_ref": "TRR Sales Professional", "kpi_metric": "月活跃卖家数", "kpi_current": "212", "kpi_target": "500"},
            {"initiative_id": "D3-AUCTION-01", "dimension": "D3需求引擎", "initiative_name": "主题拍卖专场体系", "priority": "P0关键路径", "target_quarter": "2026Q2", "status": "待启动", "estimated_investment": 100000, "expected_revenue_impact": 3000000, "benchmark_ref": "Catawiki周度主题拍卖", "kpi_metric": "月专场拍卖场数", "kpi_current": "0", "kpi_target": "8场/月"},
            {"initiative_id": "D3-MEMBER-01", "dimension": "D3需求引擎", "initiative_name": "会员体系重构", "priority": "P1重要", "target_quarter": "2026Q3", "status": "待启动", "estimated_investment": 80000, "expected_revenue_impact": 1000000, "benchmark_ref": "TRR First Look订阅", "kpi_metric": "付费会员数", "kpi_current": "约100", "kpi_target": "2000"},
            {"initiative_id": "D3-CONTENT-01", "dimension": "D3需求引擎", "initiative_name": "故事化商品展示", "priority": "P1重要", "target_quarter": "2026Q2", "status": "待启动", "estimated_investment": 100000, "expected_revenue_impact": 1500000, "benchmark_ref": "1stDibs策展体验", "kpi_metric": "带故事商品占比", "kpi_current": "0%", "kpi_target": "30%"},
            {"initiative_id": "D3-REACTIVATE-01", "dimension": "D3需求引擎", "initiative_name": "单次购买客户激活计划", "priority": "P1重要", "target_quarter": "2026Q2", "status": "待启动", "estimated_investment": 50000, "expected_revenue_impact": 2000000, "benchmark_ref": "CRM最佳实践", "kpi_metric": "仅1次购买占比", "kpi_current": "37%", "kpi_target": "25%"},
            {"initiative_id": "D4-SOCIAL-01", "dimension": "D4交易机制", "initiative_name": "社交化竞拍功能", "priority": "P1重要", "target_quarter": "2026Q2", "status": "待启动", "estimated_investment": 120000, "expected_revenue_impact": 1000000, "benchmark_ref": "Heritage实时竞拍大厅", "kpi_metric": "竞拍页互动率", "kpi_current": "—", "kpi_target": "5%"},
            {"initiative_id": "D4-BUYNOW-01", "dimension": "D4交易机制", "initiative_name": "Buy Now+拍卖混合模式优化", "priority": "P2增强", "target_quarter": "2026Q3", "status": "待启动", "estimated_investment": 80000, "expected_revenue_impact": 500000, "benchmark_ref": "Catawiki 2024引入Buy Now", "kpi_metric": "一口价转化率提升", "kpi_current": "—", "kpi_target": "+10%"},
            {"initiative_id": "D5-AUCTION-THEMED-01", "dimension": "D5内容与IP", "initiative_name": "万里茶道主题专场拍卖", "priority": "P0关键路径", "target_quarter": "2026Q2", "status": "待启动", "estimated_investment": 50000, "expected_revenue_impact": 3000000, "benchmark_ref": "杨老师IP×Catawiki专场模式", "kpi_metric": "专场年GMV", "kpi_current": "0", "kpi_target": "300-500万"},
            {"initiative_id": "D5-BOOK-01", "dimension": "D5内容与IP", "initiative_name": "万里茶道书籍出版", "priority": "P0关键路径", "target_quarter": "2026Q3", "status": "筹备中", "estimated_investment": 100000, "expected_revenue_impact": 500000, "benchmark_ref": "14.4万字书稿已完成", "kpi_metric": "出版+首印量", "kpi_current": "书稿完成", "kpi_target": "首印5万册"},
            {"initiative_id": "D5-COURSE-01", "dimension": "D5内容与IP", "initiative_name": "文化艺术品鉴赏付费课程", "priority": "P1重要", "target_quarter": "2026Q4", "status": "待启动", "estimated_investment": 150000, "expected_revenue_impact": 2000000, "benchmark_ref": "Antiques Roadshow教育功能", "kpi_metric": "课程销售量", "kpi_current": "0", "kpi_target": "10000份"},
            {"initiative_id": "D5-副IP-01", "dimension": "D5内容与IP", "initiative_name": "品类专家副IP矩阵培育", "priority": "P1重要", "target_quarter": "2026Q2", "status": "待启动", "estimated_investment": 200000, "expected_revenue_impact": 1500000, "benchmark_ref": "TRR/开运鉴定团专家团队", "kpi_metric": "副IP独立带货能力", "kpi_current": "0", "kpi_target": "3个副IP月均GMV>30万"},
            {"initiative_id": "D6-DATA-01", "dimension": "D6技术与数据", "initiative_name": "数据埋点+基础推荐上线", "priority": "P0关键路径", "target_quarter": "2026Q2", "status": "待启动", "estimated_investment": 200000, "expected_revenue_impact": 1000000, "benchmark_ref": "TRR数据驱动匹配", "kpi_metric": "埋点覆盖率", "kpi_current": "~10%", "kpi_target": "80%"},
            {"initiative_id": "D6-PLATFORM-01", "dimension": "D6技术与数据", "initiative_name": "平台1.5→2.0升级", "priority": "P1重要", "target_quarter": "2026Q3-Q4", "status": "待启动", "estimated_investment": 1000000, "expected_revenue_impact": 3000000, "benchmark_ref": "全栈技术平台", "kpi_metric": "系统功能完成率", "kpi_current": "1.0", "kpi_target": "2.0"},
            {"initiative_id": "D6-SEARCH-01", "dimension": "D6技术与数据", "initiative_name": "搜索优化+分类改进", "priority": "P0关键路径", "target_quarter": "2026Q1", "status": "待启动", "estimated_investment": 80000, "expected_revenue_impact": 500000, "benchmark_ref": "搜索无结果率优化", "kpi_metric": "搜索转化率", "kpi_current": "—", "kpi_target": "+20%"},
            {"initiative_id": "D7-BUYER-FEE-01", "dimension": "D7收入模型", "initiative_name": "买家服务费试点（3%）", "priority": "P1重要", "target_quarter": "2026Q4", "status": "待启动", "estimated_investment": 30000, "expected_revenue_impact": 1800000, "benchmark_ref": "Catawiki双边收费", "kpi_metric": "买家费收入", "kpi_current": "0", "kpi_target": "年180万"},
            {"initiative_id": "D7-COMMISSION-01", "dimension": "D7收入模型", "initiative_name": "佣金率渐进提升（22%→25%）", "priority": "P1重要", "target_quarter": "2026Q3", "status": "待启动", "estimated_investment": 0, "expected_revenue_impact": 2000000, "benchmark_ref": "TRR 38% / Catawiki 20%", "kpi_metric": "综合佣金率", "kpi_current": "22.3%", "kpi_target": "25%"},
            {"initiative_id": "D7-AD-01", "dimension": "D7收入模型", "initiative_name": "搜索推荐位付费推广", "priority": "P2增强", "target_quarter": "2027+", "status": "待启动", "estimated_investment": 100000, "expected_revenue_impact": 1000000, "benchmark_ref": "微拍堂广告收入占40%+", "kpi_metric": "广告收入", "kpi_current": "0", "kpi_target": "年100万"},
            {"initiative_id": "D7-CONSULT-01", "dimension": "D7收入模型", "initiative_name": "专家一对一鉴定咨询服务", "priority": "P2增强", "target_quarter": "2026Q4", "status": "待启动", "estimated_investment": 50000, "expected_revenue_impact": 500000, "benchmark_ref": "Catawiki专家增值服务", "kpi_metric": "付费鉴定咨询数", "kpi_current": "0", "kpi_target": "500次/年"},
        ]
    ]

    t10 = []
    for row in [
        {"round": "Pre-A", "target_year": "2026", "gmv_basis": 60000000, "revenue_basis": 15700000, "valuation_multiple_low": 3, "valuation_multiple_high": 4, "funding_amount": 3000000, "dilution_pct": 10, "use_of_funds": "AI鉴定30%+鉴定师扩建20%+技术升级25%+运营团队15%+流动资金10%", "key_milestones": "鉴定产能4倍扩容+月GMV突破500万+万里茶道书籍出版", "benchmark_company": "Catawiki D轮", "benchmark_multiple": 6.0},
        {"round": "A轮", "target_year": "2027", "gmv_basis": 150000000, "revenue_basis": 41000000, "valuation_multiple_low": 5, "valuation_multiple_high": 7, "funding_amount": 10000000, "dilution_pct": 15, "use_of_funds": "平台2.0+苏州展仓+品类扩张+千匠守艺海外启动", "key_milestones": "年GMV 1.5亿+苏州展仓开业+海外首单+IP内容矩阵成熟", "benchmark_company": "Catawiki C轮", "benchmark_multiple": 5.0},
        {"round": "B轮", "target_year": "2028", "gmv_basis": 300000000, "revenue_basis": 85000000, "valuation_multiple_low": 6, "valuation_multiple_high": 8, "funding_amount": 30000000, "dilution_pct": 15, "use_of_funds": "全国线下展仓网络+国际化+AI 3.0+供应链金融", "key_milestones": "年GMV 3亿+3城线下展仓+海外GMV占比10%+AI鉴定覆盖全品类", "benchmark_company": "Catawiki D轮", "benchmark_multiple": 6.0},
        {"round": "C轮", "target_year": "2029", "gmv_basis": 600000000, "revenue_basis": 170000000, "valuation_multiple_low": 7, "valuation_multiple_high": 10, "funding_amount": 50000000, "dilution_pct": 12, "use_of_funds": "IPO准备+全球扩张+文化生态建设", "key_milestones": "年GMV 6亿+5城展仓+海外GMV占比20%+年利润过亿", "benchmark_company": "TheRealReal IPO", "benchmark_multiple": 8.0},
    ]:
        low = row["revenue_basis"] * row["valuation_multiple_low"] / 10000
        high = row["revenue_basis"] * row["valuation_multiple_high"] / 10000
        t10.append(
            {
                "record_id": _row_key("T10", row["round"]),
                **row,
                "implied_valuation_low": round(low, 2),
                "implied_valuation_high": round(high, 2),
                "post_money_low": round(low + row["funding_amount"] / 10000, 2),
                "post_money_high": round(high + row["funding_amount"] / 10000, 2),
                "scenario_label": row["round"],
            }
        )

    t11: list[dict[str, Any]] = []
    months = sorted({ _month_text(row["month"]) for row in t01 if _month_text(row["month"]) })
    for month in months:
        month_t01 = [row for row in t01 if _month_text(row["month"]) == month]
        month_t02 = next((row for row in t02 if _month_text(row["month"]) == month), None)
        if not month_t01:
            continue
        gmv = sum(float(row.get("gmv") or 0) for row in month_t01)
        revenue_total = sum(float(row.get("service_fee_income") or 0) for row in month_t01)
        opex_total = float((month_t02 or {}).get("cost_salary") or 0) + float((month_t02 or {}).get("cost_rent") or 0) + float((month_t02 or {}).get("cost_tech") or 0) + float((month_t02 or {}).get("cost_marketing") or 0) + float((month_t02 or {}).get("cost_auth") or 0) + float((month_t02 or {}).get("cost_travel") or 0) + float((month_t02 or {}).get("cost_platform_fee") or 0) + float((month_t02 or {}).get("cost_other") or 0)
        t11.append(
            {
                "record_id": _row_key("T11", month),
                "month": _month_ms(month),
                "gmv": gmv,
                "effective_sales": sum(float(row.get("effective_sales") or 0) for row in month_t01),
                "revenue_total": revenue_total,
                "service_fee_income": revenue_total,
                "total_orders": sum(int(row.get("total_orders") or 0) for row in month_t01),
                "active_sellers": max(int(row.get("active_sellers") or 0) for row in month_t01),
                "new_customers": max(int(row.get("new_customers") or 0) for row in month_t01),
                "mau": max(int(row.get("mau") or 0) for row in month_t01),
                "inventory_turnover_days": max(float(row.get("inventory_turnover_days") or 0) for row in month_t01),
                "return_rate": 0,
                "opex_total": opex_total,
                "operating_profit": revenue_total - opex_total,
                "operating_margin": (revenue_total - opex_total) / revenue_total if revenue_total else 0,
                "notes": "月度经营快照",
            }
        )

    t12 = [
        {
            "record_id": "registry_version",
            "config_key": "registry_version",
            "config_value": "v1",
            "config_group": "system",
            "source_sheet": "",
            "source_note": "table_registry.json 版本",
            "updated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "updated_by": "Codex",
            "is_active": True,
            "notes": "",
        },
        {
            "record_id": "source_file_stats",
            "config_key": "source_file_stats",
            "config_value": str(DATA_STATS_PATH),
            "config_group": "system",
            "source_sheet": "",
            "source_note": "数据统计源文件",
            "updated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "updated_by": "Codex",
            "is_active": True,
            "notes": "",
        },
        {
            "record_id": "source_file_finance",
            "config_key": "source_file_finance",
            "config_value": str(FINANCE_PATH),
            "config_group": "system",
            "source_sheet": "",
            "source_note": "财务尽调源文件",
            "updated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "updated_by": "Codex",
            "is_active": True,
            "notes": "",
        },
    ]

    return {
        "T01_月度经营数据": t01,
        "T02_月度财务数据": t02,
        "T03_客户分析": t03,
        "T04_品类分析": t04,
        "T05_供应链效率": t05,
        "T06_内容与IP": t06,
        "T07_财务建模": t07,
        "T08_对标矩阵": t08,
        "T09_进化追踪": t09,
        "T10_估值测算": t10,
        "T11_月度经营快照": t11,
        "T12_元数据与配置": t12,
    }


def build_phase2_rows() -> dict[str, list[dict[str, Any]]]:
    return {
        "T07_财务建模": build_phase1_rows()["T07_财务建模"],
        "T08_对标矩阵": build_phase1_rows()["T08_对标矩阵"],
        "T09_进化追踪": build_phase1_rows()["T09_进化追踪"],
        "T10_估值测算": build_phase1_rows()["T10_估值测算"],
    }


def table_record_spec(table_name: str) -> tuple[str, str]:
    spec = table_spec(table_name)
    return spec["primary_field"], spec["table_name"]


def write_table_records(client: FeishuBitableAPI, app_token: str, table_name: str, rows: list[dict[str, Any]], *, apply: bool) -> dict[str, Any]:
    registry = load_registry()
    table_id = registry_table_id(table_name, registry)
    if not table_id:
        raise RuntimeError(f"missing registry entry for {table_name}")
    spec = table_spec(table_name)
    normalized_rows = [normalize_record({"fields": non_formula_fields(spec)}, row) for row in rows]
    existing = client.list_records(app_token, table_id)
    existing_by_key = {}
    for record in existing:
        fields = record.get("fields") or {}
        key = str(fields.get(spec["primary_field"]) or "").strip()
        if key:
            existing_by_key[key] = record
    create_payload: list[dict[str, Any]] = []
    update_payload: list[dict[str, Any]] = []
    for row in normalized_rows:
        key = str(row.get(spec["primary_field"]) or "").strip()
        if not key:
            continue
        current = existing_by_key.get(key)
        if current:
            current_fields = current.get("fields") or {}
            if current_fields != row:
                update_payload.append({"record_id": current.get("record_id") or current.get("id"), "fields": row})
        else:
            create_payload.append({"fields": row})
    if apply and create_payload:
        client.batch_create_records(app_token, table_id, [item["fields"] for item in create_payload])
    if apply and update_payload:
        client.batch_update_records(app_token, table_id, update_payload)
    final_records = client.list_records(app_token, table_id)
    return {
        "table_name": table_name,
        "table_id": table_id,
        "source_rows": len(normalized_rows),
        "created": len(create_payload),
        "updated": len(update_payload),
        "final_rows": len(final_records),
        "applied": apply,
    }


def write_task_tracker(client: FeishuBitableAPI, rows: list[dict[str, Any]], *, apply: bool) -> dict[str, Any]:
    existing = client.list_records(TASK_TRACKER_APP, TASK_TRACKER_TABLE)
    current_by_task_id: dict[str, dict[str, Any]] = {}
    for record in existing:
        task_id = str((record.get("fields") or {}).get("task_id") or "").strip()
        if task_id:
            current_by_task_id[task_id] = record
    create_payload: list[dict[str, Any]] = []
    update_payload: list[dict[str, Any]] = []
    for row in rows:
        task_id = str(row.get("task_id") or "").strip()
        if not task_id:
            continue
        current = current_by_task_id.get(task_id)
        if current:
            update_payload.append({"record_id": current.get("record_id") or current.get("id"), "fields": row})
        else:
            create_payload.append(row)
    if apply and create_payload:
        client.batch_create_records(TASK_TRACKER_APP, TASK_TRACKER_TABLE, create_payload)
    if apply and update_payload:
        client.batch_update_records(TASK_TRACKER_APP, TASK_TRACKER_TABLE, update_payload)
    return {
        "created": len(create_payload),
        "updated": len(update_payload),
        "existing": len(current_by_task_id),
        "applied": apply,
    }


def task_tracker_rows_for_brm(
    *,
    task_status_by_id: dict[str, str],
    completion_date_by_id: dict[str, str | None],
    evidence_ref_by_id: dict[str, str],
    notes_by_id: dict[str, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    project_name = "回旋镖局战略经营驾驶舱"
    for task_id, task_name in [
        ("TS-BRM-01", "回旋镖局飞书多维表建表"),
        ("TS-BRM-02", "回旋镖局飞书多维表历史数据灌入（Phase 1: 6张表）"),
        ("TS-BRM-03", "回旋镖局飞书多维表分析层数据灌入（Phase 2: 4张表）"),
    ]:
        payload = {
            "task_id": task_id,
            "project_id": "PROJ-BOOMERANG",
            "project_name": project_name,
            "project_status": "进行中",
            "task_name": task_name,
            "task_status": task_status_by_id.get(task_id, "待启动"),
            "priority": "P0",
            "owner": "Codex",
            "evidence_ref": evidence_ref_by_id.get(task_id, ""),
            "notes": notes_by_id.get(task_id, ""),
        }
        completion_date = completion_date_by_id.get(task_id)
        if completion_date not in {None, ""}:
            payload["completion_date"] = completion_date
        rows.append(payload)
    return rows


def registry_payload(app_token: str, table_results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "app_token": app_token,
        "base_name": BOOMERANG_BASE_NAME,
        "wiki_node_token": BOOMERANG_WIKI_TOKEN,
        "base_link": BOOMERANG_BASE_LINK,
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "created_by": "codex",
        "tables": {
            result["table_name"]: {
                "table_id": result["table_id"],
                "field_count": result["field_count"],
                "status": result["status"],
                "table_key": result.get("table_key", ""),
                "layer": result.get("layer", ""),
                "primary_field": result.get("primary_field", ""),
            }
            for result in table_results
        },
        "schema_notes": INFERENCE_NOTES,
    }


def table_specs_by_name() -> dict[str, dict[str, Any]]:
    return {spec["table_name"]: spec for spec in TABLE_SPECS}
