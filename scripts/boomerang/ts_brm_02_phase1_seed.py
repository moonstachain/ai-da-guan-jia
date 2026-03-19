from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from python_calamine import CalamineWorkbook

from dashboard.feishu_deploy import FeishuBitableAPI


ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "boomerang"


@dataclass
class TableTarget:
    name: str
    table_id: str
    fields: list[dict[str, Any]]


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    _ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _excel_date_to_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, (int, float)):
        if value <= 0:
            return None
        return date(1899, 12, 30) + timedelta(days=int(value))
    text = _normalize_text(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m", "%Y/%m"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.date()
        except ValueError:
            continue
    if text.endswith("月"):
        digits = "".join(ch for ch in text if ch.isdigit())
        if digits:
            month = int(digits)
            return date(2025, month, 1)
    return None


def month_key(value: Any, *, default_year: int = 2025) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        if value > 10000:
            dt = date(1899, 12, 30) + timedelta(days=int(value))
            return dt.strftime("%Y-%m")
    text = _normalize_text(value)
    if not text:
        return None
    if "-" in text or "/" in text:
        text = text.replace("/", "-")
        parts = text.split("-")
        if len(parts) >= 2 and parts[0].isdigit():
            year = int(parts[0])
            month = int(parts[1])
            return f"{year:04d}-{month:02d}"
    if text.endswith("月"):
        digits = "".join(ch for ch in text if ch.isdigit())
        if digits:
            month = int(digits)
            return f"{default_year:04d}-{month:02d}"
    return None


def month_to_timestamp_ms(value: str) -> int | None:
    if not value:
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m")
    except ValueError:
        return None
    return int(datetime(parsed.year, parsed.month, 1).timestamp() * 1000)


def read_sheet(path: Path, name: str) -> list[list[Any]]:
    wb = CalamineWorkbook.from_path(path)
    if name not in wb.sheet_names:
        raise RuntimeError(f"Missing sheet {name}")
    return wb.get_sheet_by_name(name).to_python()


def find_header_row(rows: list[list[Any]], label: str) -> int:
    for idx, row in enumerate(rows):
        if _normalize_text(row[0]) == label:
            return idx
    return -1


def safe_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) and not math.isnan(float(value)):
        return float(value)
    text = _normalize_text(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _sum_numbers(values: Iterable[Any]) -> float:
    total = 0.0
    for item in values:
        number = safe_number(item)
        if number is None:
            continue
        total += number
    return total


def normalize_base(value: str) -> str | None:
    text = _normalize_text(value)
    if not text:
        return None
    if text in {"苏州总部", "苏州", "苏州基地"}:
        return "苏州"
    if text in {"广东基地", "广东", "广东基地 "}:
        return "广东"
    if text in {"合计", "总计", "整体"}:
        return "合计"
    return text


def extract_income_by_base(path: Path) -> tuple[dict[tuple[str, str], dict[str, float]], dict[str, float]]:
    rows = read_sheet(path, "2.1、2.3 、2.6月度收入明细、毛利净利率")
    header_idx = find_header_row(rows, "月份")
    if header_idx == -1:
        raise RuntimeError("Missing header row in income sheet")
    header = [str(c).strip() if c is not None else "" for c in rows[header_idx]]
    index = {name: idx for idx, name in enumerate(header) if name}
    month_idx = index.get("月份")
    base_idx = index.get("端口")
    gmv_idx = index.get("GMV")
    effective_idx = index.get("有效销售额")
    fee_idx = index.get("回旋镖局服务费")
    platform_idx = index.get("平台费")
    if month_idx is None or base_idx is None:
        raise RuntimeError("Income sheet missing month or base column")
    current_month = None
    by_base: dict[tuple[str, str], dict[str, float]] = {}
    platform_fee_by_month: dict[str, float] = {}
    for row in rows[header_idx + 1 :]:
        month_raw = row[month_idx] if month_idx < len(row) else ""
        if _normalize_text(month_raw):
            current_month = month_key(month_raw)
        if not current_month:
            continue
        base_raw = row[base_idx] if base_idx < len(row) else ""
        base = normalize_base(base_raw)
        if not base or base in {"合计", "总计"}:
            continue
        key = (current_month, base)
        metrics = by_base.setdefault(key, {})
        if gmv_idx is not None and gmv_idx < len(row):
            metrics["gmv"] = metrics.get("gmv", 0.0) + (safe_number(row[gmv_idx]) or 0.0)
        if effective_idx is not None and effective_idx < len(row):
            metrics["effective_sales"] = metrics.get("effective_sales", 0.0) + (safe_number(row[effective_idx]) or 0.0)
        if fee_idx is not None and fee_idx < len(row):
            metrics["service_fee_income"] = metrics.get("service_fee_income", 0.0) + (safe_number(row[fee_idx]) or 0.0)
        if platform_idx is not None and platform_idx < len(row):
            platform_fee_by_month[current_month] = platform_fee_by_month.get(current_month, 0.0) + (
                safe_number(row[platform_idx]) or 0.0
            )
    return by_base, platform_fee_by_month


def extract_cost_structure(path: Path) -> dict[str, dict[str, float]]:
    rows = read_sheet(path, "2.2 、2.9成本结构明细")
    header_idx = find_header_row(rows, "月份")
    if header_idx == -1:
        raise RuntimeError("Missing header row in cost structure sheet")
    header = [str(c).strip() if c is not None else "" for c in rows[header_idx]]
    index = {name: idx for idx, name in enumerate(header) if name}
    month_idx = index.get("月份")
    month_data: dict[str, dict[str, float]] = {}
    for row in rows[header_idx + 1 :]:
        month_raw = row[month_idx] if month_idx is not None and month_idx < len(row) else ""
        month = month_key(month_raw)
        if not month:
            continue
        record = month_data.setdefault(month, {})
        for field, alias in (
            ("cost_tech", "小程序投入成本"),
            ("packaging", "包装耗材"),
            ("accessories", "货品配饰"),
            ("inspection", "检测费"),
            ("office", "办公费"),
            ("cost_marketing", "推广费"),
            ("cost_travel", "差旅费"),
            ("service_fee", "服务费"),
            ("platform_fee_cost", "平台费"),
            ("entertainment", "招待费"),
            ("welfare", "福利费"),
            ("cost_salary", "工资及社保"),
            ("cost_rent", "房租水电"),
        ):
            idx = index.get(alias)
            if idx is None or idx >= len(row):
                continue
            value = safe_number(row[idx])
            if value is None:
                continue
            record[field] = value
    return month_data


def extract_orders(path: Path) -> dict[str, dict[str, float]]:
    rows = read_sheet(path, "2.2-1月度订单量(拍卖单vs一口价单拆分)")
    header_idx = find_header_row(rows, "月份")
    if header_idx == -1:
        raise RuntimeError("Missing header row in orders sheet")
    base_row = rows[header_idx]
    type_row = rows[header_idx + 2] if header_idx + 2 < len(rows) else []
    metrics: dict[str, dict[str, float]] = {}
    for row in rows[header_idx + 3 :]:
        month = month_key(row[0]) if row else None
        if not month:
            continue
        month_metrics = metrics.setdefault(month, {})
        base_totals: dict[str, dict[str, float]] = {}
        total_orders = 0.0
        current_base = None
        for idx in range(1, min(len(base_row), len(type_row), len(row))):
            base_cell = normalize_base(base_row[idx])
            if base_cell:
                current_base = base_cell
            base = current_base
            order_type = _normalize_text(type_row[idx])
            cell = row[idx] if idx < len(row) else ""
            value = safe_number(cell)
            if value is None:
                continue
            if order_type in {"一口价", "拍卖"} and base:
                base_bucket = base_totals.setdefault(base, {"fixed": 0.0, "auction": 0.0})
                if order_type == "一口价":
                    base_bucket["fixed"] += value
                else:
                    base_bucket["auction"] += value
            if order_type == "总订单量":
                total_orders = value
        for base, bucket in base_totals.items():
            month_metrics[f"fixed_price_orders::{base}"] = bucket["fixed"]
            month_metrics[f"auction_orders::{base}"] = bucket["auction"]
            month_metrics[f"total_orders::{base}"] = bucket["fixed"] + bucket["auction"]
        if total_orders:
            month_metrics["total_orders::合计"] = total_orders
    return metrics


def extract_sku_listed(path: Path) -> dict[str, float]:
    rows = read_sheet(path, "2.2-2商品上架数、上架转化率(上架一售出)")
    header_idx = find_header_row(rows, "所属")
    if header_idx == -1:
        return {}
    header = [str(c).strip() if c is not None else "" for c in rows[header_idx]]
    index = {name: idx for idx, name in enumerate(header) if name}
    base_idx = index.get("所属")
    count_idx = index.get("上架商品数")
    if base_idx is None or count_idx is None:
        return {}
    result: dict[str, float] = {}
    for row in rows[header_idx + 1 :]:
        base = normalize_base(row[base_idx]) if base_idx < len(row) else None
        if not base:
            continue
        value = safe_number(row[count_idx]) if count_idx < len(row) else None
        if value is None:
            continue
        result[base] = value
    return result


def extract_receipts(path: Path) -> dict[str, float]:
    rows = read_sheet(path, "2.4-1月度收货量(技术拉取)")
    header_idx = find_header_row(rows, "签收月份")
    if header_idx == -1:
        return {}
    header = [str(c).strip() if c is not None else "" for c in rows[header_idx]]
    index = {name: idx for idx, name in enumerate(header) if name}
    month_idx = index.get("签收月份")
    count_idx = index.get("签收数量")
    if month_idx is None or count_idx is None:
        return {}
    totals: dict[str, float] = {}
    for row in rows[header_idx + 1 :]:
        month = month_key(row[month_idx]) if month_idx < len(row) else None
        if not month:
            continue
        count = safe_number(row[count_idx]) if count_idx < len(row) else None
        if count is None:
            continue
        totals[month] = totals.get(month, 0.0) + count
    return totals


def extract_receipts_by_category(path: Path) -> list[dict[str, Any]]:
    rows = read_sheet(path, "2.4-1月度收货量(技术拉取)")
    header_idx = find_header_row(rows, "签收月份")
    if header_idx == -1:
        return []
    header = [str(c).strip() if c is not None else "" for c in rows[header_idx]]
    index = {name: idx for idx, name in enumerate(header) if name}
    month_idx = index.get("签收月份")
    primary_idx = index.get("一级品类")
    secondary_idx = index.get("二级品类")
    count_idx = index.get("签收数量")
    results = []
    for row in rows[header_idx + 1 :]:
        month = month_key(row[month_idx]) if month_idx is not None and month_idx < len(row) else None
        primary = _normalize_text(row[primary_idx]) if primary_idx is not None and primary_idx < len(row) else ""
        secondary = _normalize_text(row[secondary_idx]) if secondary_idx is not None and secondary_idx < len(row) else ""
        count = safe_number(row[count_idx]) if count_idx is not None and count_idx < len(row) else None
        if not month or not primary or count is None:
            continue
        results.append(
            {
                "month": month,
                "category_primary": primary,
                "category_secondary": secondary,
                "items_received": count,
            }
        )
    return results


def extract_rejections(path: Path) -> dict[str, float]:
    rows = read_sheet(path, "2.4-2不通过原因统计及状态占比(技术拉取）")
    header_idx = find_header_row(rows, "鉴定月份")
    if header_idx == -1:
        return {}
    header = [str(c).strip() if c is not None else "" for c in rows[header_idx]]
    index = {name: idx for idx, name in enumerate(header) if name}
    month_idx = index.get("鉴定月份")
    count_idx = index.get("不通过数量")
    totals: dict[str, float] = {}
    for row in rows[header_idx + 1 :]:
        month = month_key(row[month_idx]) if month_idx is not None and month_idx < len(row) else None
        if not month:
            continue
        count = safe_number(row[count_idx]) if count_idx is not None and count_idx < len(row) else None
        if count is None:
            continue
        totals[month] = totals.get(month, 0.0) + count
    return totals


def extract_active_sellers(path: Path) -> dict[str, float]:
    rows = read_sheet(path, "2.4-7寄售卖家(技术拉取)")
    header_idx = find_header_row(rows, "寄卖月份")
    if header_idx == -1:
        return {}
    header = [str(c).strip() if c is not None else "" for c in rows[header_idx]]
    index = {name: idx for idx, name in enumerate(header) if name}
    month_idx = index.get("寄卖月份")
    count_idx = index.get("寄卖人数")
    result: dict[str, float] = {}
    for row in rows[header_idx + 1 :]:
        month = month_key(row[month_idx]) if month_idx is not None and month_idx < len(row) else None
        count = safe_number(row[count_idx]) if count_idx is not None and count_idx < len(row) else None
        if not month or count is None:
            continue
        result[month] = count
    return result


def extract_new_customers(path: Path) -> dict[str, float]:
    rows = read_sheet(path, "2.5-2新客获取数获客渠道来源(小红书抖音视频号私域")
    if not rows:
        return {}
    header = [str(c).strip() if c is not None else "" for c in rows[0]]
    month_cols: dict[int, str] = {}
    for idx, value in enumerate(header):
        month = month_key(value)
        if month:
            month_cols[idx] = month
    result: dict[str, float] = {month: 0.0 for month in month_cols.values()}
    for row in rows[1:]:
        channel = _normalize_text(row[0]) if row else ""
        if not channel:
            continue
        for idx, month in month_cols.items():
            if idx >= len(row):
                continue
            value = safe_number(row[idx])
            if value is None:
                continue
            result[month] = result.get(month, 0.0) + value
    return result


def extract_mau(path: Path) -> dict[str, float]:
    rows = read_sheet(path, "2.2-9小程序DAU、MAU")
    header_idx = find_header_row(rows, "月份")
    if header_idx == -1:
        return {}
    result: dict[str, float] = {}
    for row in rows[header_idx + 1 :]:
        month = month_key(row[0]) if row else None
        count = safe_number(row[1]) if len(row) > 1 else None
        if not month or count is None:
            continue
        result[month] = count
    return result


def extract_stale_items(path: Path) -> dict[str, float]:
    rows = read_sheet(path, "2.2-8滞销商品(技术拉取)")
    header_idx = find_header_row(rows, "上架月份")
    if header_idx == -1:
        return {}
    result: dict[str, float] = {}
    for row in rows[header_idx + 1 :]:
        month = month_key(row[0]) if row else None
        count = safe_number(row[1]) if len(row) > 1 else None
        if not month or count is None:
            continue
        result[month] = count
    return result


def extract_auction_metrics(path: Path) -> dict[str, dict[str, float]]:
    rows = read_sheet(path, "2.2-6拍卖场次(技术拉取)")
    header_idx = find_header_row(rows, "月份")
    if header_idx == -1:
        return {}
    header = [str(c).strip() if c is not None else "" for c in rows[header_idx]]
    index = {name: idx for idx, name in enumerate(header) if name}
    month_idx = index.get("月份")
    success_idx = index.get("成功率_百分比")
    avg_idx = index.get("平均每场竞价轮次")
    result: dict[str, dict[str, float]] = {}
    for row in rows[header_idx + 1 :]:
        month = month_key(row[month_idx]) if month_idx is not None and month_idx < len(row) else None
        if not month:
            continue
        metrics = result.setdefault(month, {})
        if success_idx is not None and success_idx < len(row):
            value = safe_number(row[success_idx])
            if value is not None:
                metrics["auction_success_rate"] = value / 100 if value > 1 else value
        if avg_idx is not None and avg_idx < len(row):
            value = safe_number(row[avg_idx])
            if value is not None:
                metrics["avg_bid_rounds"] = value
    return result


def extract_inventory_turnover(path: Path) -> dict[str, float]:
    rows = read_sheet(path, "2.2-3SKU库存周转天数(从入库到售出的平均天数)")
    result: dict[str, float] = {}
    for row in rows:
        base = normalize_base(row[0]) if row else None
        if not base or base == "合计":
            continue
        value_text = _normalize_text(row[1]) if len(row) > 1 else ""
        if value_text.endswith("天"):
            value_text = value_text.replace("天", "")
        value = safe_number(value_text)
        if value is None:
            continue
        result[base] = value
    return result


def extract_logistics_cost(path: Path) -> dict[str, dict[str, float]]:
    rows = read_sheet(path, "2.4-4物流成本明细(收货发货按物流商分)及平均单票物流")
    header_idx = find_header_row(rows, "月份")
    if header_idx == -1:
        return {}
    header = [str(c).strip() if c is not None else "" for c in rows[header_idx]]
    index = {name: idx for idx, name in enumerate(header) if name}
    month_idx = index.get("月份")
    type_idx = index.get("类型")
    count_idx = index.get("订单票数 (单)")
    cost_idx = index.get("物流总成本 (元)")
    avg_idx = index.get("平均单票费用 (元/单)")
    result: dict[str, dict[str, float]] = {}
    current_month = None
    for row in rows[header_idx + 1 :]:
        if month_idx is not None and month_idx < len(row):
            if _normalize_text(row[month_idx]):
                current_month = month_key(row[month_idx])
        if not current_month:
            continue
        flow_type = _normalize_text(row[type_idx]) if type_idx is not None and type_idx < len(row) else ""
        if not flow_type:
            continue
        record = result.setdefault(current_month, {})
        count = safe_number(row[count_idx]) if count_idx is not None and count_idx < len(row) else None
        cost = safe_number(row[cost_idx]) if cost_idx is not None and cost_idx < len(row) else None
        avg = safe_number(row[avg_idx]) if avg_idx is not None and avg_idx < len(row) else None
        prefix = "outbound" if flow_type == "发货" else "inbound"
        if count is not None:
            record[f"{prefix}_tickets"] = record.get(f"{prefix}_tickets", 0.0) + count
        if cost is not None:
            record[f"{prefix}_cost"] = record.get(f"{prefix}_cost", 0.0) + cost
        if avg is not None:
            record[f"{prefix}_avg_cost"] = avg
    return result


def extract_customer_segment(path: Path) -> list[dict[str, Any]]:
    rows = read_sheet(path, "2.5-1客户分层统计")
    header_idx = find_header_row(rows, "分层级")
    if header_idx == -1:
        return []
    header = [str(c).strip() if c is not None else "" for c in rows[header_idx]]
    index = {name: idx for idx, name in enumerate(header) if name}
    tier_idx = index.get("分层级")
    count_idx = index.get("客户数量")
    tier2_idx = index.get("分层等级")
    month_idx = index.get("订单日期")
    sales_idx = index.get("求和项:销售额")
    share_idx = index.get("销售额占比")
    results: list[dict[str, Any]] = []
    current_tier = None
    for row in rows[header_idx + 1 :]:
        tier = _normalize_text(row[tier_idx]) if tier_idx is not None and tier_idx < len(row) else ""
        if tier:
            current_tier = tier
            count = safe_number(row[count_idx]) if count_idx is not None and count_idx < len(row) else None
            sales = safe_number(row[sales_idx]) if sales_idx is not None and sales_idx < len(row) else None
            share = safe_number(row[share_idx]) if share_idx is not None and share_idx < len(row) else None
            if current_tier and count is not None:
                results.append(
                    {
                        "segment": current_tier,
                        "customer_count": count,
                        "sales_total": sales,
                        "sales_share": share,
                        "source": "2.5-1客户分层统计",
                    }
                )
        tier2 = _normalize_text(row[tier2_idx]) if tier2_idx is not None and tier2_idx < len(row) else ""
        if tier2:
            current_tier = tier2
        month = month_key(row[month_idx]) if month_idx is not None and month_idx < len(row) else None
        sales = safe_number(row[sales_idx]) if sales_idx is not None and sales_idx < len(row) else None
        share = safe_number(row[share_idx]) if share_idx is not None and share_idx < len(row) else None
        if current_tier and month and sales is not None:
            results.append(
                {
                    "segment": current_tier,
                    "month": month,
                    "sales_total": sales,
                    "sales_share": share,
                    "source": "2.5-1客户分层统计",
                }
            )
    return results


def extract_customer_segment_tech(path: Path) -> list[dict[str, Any]]:
    rows = read_sheet(path, "2.5-1客户分层统计(技术拉取)")
    header = [str(c).strip() if c is not None else "" for c in rows[0]]
    index = {name: idx for idx, name in enumerate(header) if name}
    results: list[dict[str, Any]] = []
    for row in rows[1:]:
        tier_idx = index.get("客户分层")
        tier = _normalize_text(row[tier_idx]) if tier_idx is not None and tier_idx < len(row) else ""
        if not tier:
            continue
        results.append(
            {
                "segment": tier,
                "customer_count": safe_number(row[index.get("客户数", -1)]) if index.get("客户数") is not None else None,
                "customer_share": safe_number(row[index.get("客户数占比_百分比", -1)])
                if index.get("客户数占比_百分比") is not None
                else None,
                "sales_total": safe_number(row[index.get("分层总消费金额", -1)])
                if index.get("分层总消费金额") is not None
                else None,
                "sales_share": safe_number(row[index.get("消费金额占比_百分比", -1)])
                if index.get("消费金额占比_百分比") is not None
                else None,
                "avg_spend": safe_number(row[index.get("人均消费金额", -1)])
                if index.get("人均消费金额") is not None
                else None,
                "avg_orders": safe_number(row[index.get("人均订单数", -1)])
                if index.get("人均订单数") is not None
                else None,
                "avg_order_value": safe_number(row[index.get("客单价", -1)]) if index.get("客单价") is not None else None,
                "source": "2.5-1客户分层统计(技术拉取)",
            }
        )
    return results


def extract_repeat_rate(path: Path) -> list[dict[str, Any]]:
    rows = read_sheet(path, "2.5-3客户复购率")
    header_idx = find_header_row(rows, "月份")
    if header_idx == -1:
        return []
    result: list[dict[str, Any]] = []
    for row in rows[header_idx + 1 :]:
        month = month_key(row[0]) if row else None
        if not month:
            continue
        result.append(
            {
                "month": month,
                "transaction_count": safe_number(row[1]) if len(row) > 1 else None,
                "repeat_rate": safe_number(row[2]) if len(row) > 2 else None,
                "source": "2.5-3客户复购率",
            }
        )
    return result


def extract_ltv(path: Path) -> list[dict[str, Any]]:
    rows = read_sheet(path, "2.5-4客户生命周期价值")
    if len(rows) < 3:
        return []
    values = rows[2]
    result = {
        "registered_members": safe_number(values[0]) if len(values) > 0 else None,
        "paying_members": safe_number(values[1]) if len(values) > 1 else None,
        "conversion_rate": safe_number(values[2]) if len(values) > 2 else None,
        "source": "2.5-4客户生命周期价值",
    }
    return [result]


def extract_churn(path: Path) -> list[dict[str, Any]]:
    rows = read_sheet(path, "2.5-5客户流失率")
    header_idx = find_header_row(rows, "月份")
    if header_idx == -1:
        return []
    result = []
    for row in rows[header_idx + 1 :]:
        month = month_key(row[0]) if row else None
        if not month:
            continue
        result.append(
            {
                "month": month,
                "churn_90d_count": safe_number(row[1]) if len(row) > 1 else None,
                "churn_7d_rate": safe_number(row[2]) if len(row) > 2 else None,
                "source": "2.5-5客户流失率",
            }
        )
    return result


def extract_member_conversion(path: Path) -> list[dict[str, Any]]:
    rows = read_sheet(path, "2.5-7会员转化量(技术拉取)")
    header_idx = find_header_row(rows, "月份")
    if header_idx == -1:
        return []
    result = []
    for row in rows[header_idx + 1 :]:
        month = month_key(row[0]) if row else None
        if not month:
            continue
        result.append(
            {
                "month": month,
                "members_registered": safe_number(row[1]) if len(row) > 1 else None,
                "members_ordered": safe_number(row[2]) if len(row) > 2 else None,
                "member_conversion_rate": safe_number(row[3]) if len(row) > 3 else None,
                "members_registered_total": safe_number(row[4]) if len(row) > 4 else None,
                "members_ordered_total": safe_number(row[5]) if len(row) > 5 else None,
                "source": "2.5-7会员转化量",
            }
        )
    return result


def extract_category_listing(path: Path) -> dict[str, dict[str, float]]:
    rows = read_sheet(path, "2.7拍卖保证金沉淀")
    header_idx = find_header_row(rows, "分类ID")
    if header_idx == -1:
        return {}
    header = [str(c).strip() if c is not None else "" for c in rows[header_idx]]
    index = {name: idx for idx, name in enumerate(header) if name}
    name_idx = index.get("分类名称")
    listed_idx = index.get("上架商品数量")
    delisted_idx = index.get("下架商品数量")
    result: dict[str, dict[str, float]] = {}
    for row in rows[header_idx + 1 :]:
        name = _normalize_text(row[name_idx]) if name_idx is not None and name_idx < len(row) else ""
        if not name:
            continue
        result[name] = {
            "listed_count": safe_number(row[listed_idx]) if listed_idx is not None and listed_idx < len(row) else None,
            "delisted_count": safe_number(row[delisted_idx]) if delisted_idx is not None and delisted_idx < len(row) else None,
        }
    return result


def extract_auth_team(path: Path) -> dict[str, dict[str, float]]:
    rows = read_sheet(path, "2.7-4鉴定师团队")
    header_idx = find_header_row(rows, "所属类别")
    if header_idx == -1:
        return {}
    header = [str(c).strip() if c is not None else "" for c in rows[header_idx]]
    index = {name: idx for idx, name in enumerate(header) if name}
    name_idx = index.get("所属类别")
    count_idx = index.get("鉴定师数量")
    output_idx = index.get("累计鉴定产出量（件）")
    accuracy_idx = index.get("鉴定准确率")
    result: dict[str, dict[str, float]] = {}
    for row in rows[header_idx + 1 :]:
        name = _normalize_text(row[name_idx]) if name_idx is not None and name_idx < len(row) else ""
        if not name or name == "合计":
            continue
        result[name] = {
            "auth_team_size": safe_number(row[count_idx]) if count_idx is not None and count_idx < len(row) else None,
            "auth_output": safe_number(row[output_idx]) if output_idx is not None and output_idx < len(row) else None,
            "auth_accuracy": safe_number(row[accuracy_idx]) if accuracy_idx is not None and accuracy_idx < len(row) else None,
        }
    return result


def extract_sop_efficiency(path: Path) -> list[dict[str, Any]]:
    rows = read_sheet(path, "2.4-8上架SOP执行效率(单件商品从入库到上架的平均工时)")
    header_idx = find_header_row(rows, "类目")
    if header_idx == -1:
        return []
    results = []
    for row in rows[header_idx + 1 :]:
        category = _normalize_text(row[0]) if row else ""
        if not category:
            continue
        value_text = _normalize_text(row[1]) if len(row) > 1 else ""
        results.append(
            {
                "category_primary": category,
                "sop_days": value_text,
                "source": "2.4-8上架SOP执行效率",
            }
        )
    return results


def extract_fans_growth(path: Path) -> list[dict[str, Any]]:
    rows = read_sheet(path, "各平台粉丝量及增长趋势(视频号抖音小红书矩阵号)")
    header = [str(c).strip() if c is not None else "" for c in rows[0]]
    index = {name: idx for idx, name in enumerate(header) if name}
    result = []
    for row in rows[1:]:
        platform_idx = index.get("平台")
        platform = _normalize_text(row[platform_idx]) if platform_idx is not None and platform_idx < len(row) else ""
        if not platform:
            continue
        period_idx = index.get("统计周期")
        publish_idx = index.get("内容发布总频次（条 / 篇）")
        avg_idx = index.get("单条平均播放 / 阅读量")
        total_idx = index.get("总播放 / 阅读量")
        like_idx = index.get("总点赞数")
        comment_idx = index.get("总评论数")
        share_idx = index.get("总转发数")
        result.append(
            {
                "channel": platform,
                "period": _normalize_text(row[period_idx]) if period_idx is not None and period_idx < len(row) else "",
                "publish_count": safe_number(row[publish_idx]) if publish_idx is not None and publish_idx < len(row) else None,
                "avg_views": safe_number(row[avg_idx]) if avg_idx is not None and avg_idx < len(row) else None,
                "total_views": safe_number(row[total_idx]) if total_idx is not None and total_idx < len(row) else None,
                "likes": safe_number(row[like_idx]) if like_idx is not None and like_idx < len(row) else None,
                "comments": safe_number(row[comment_idx]) if comment_idx is not None and comment_idx < len(row) else None,
                "shares": safe_number(row[share_idx]) if share_idx is not None and share_idx < len(row) else None,
                "source": "各平台粉丝量及增长趋势",
            }
        )
    return result


def extract_live_metrics(path: Path) -> list[dict[str, Any]]:
    rows = read_sheet(path, "直播场次、场均观看人数、场均成交额、直播引流到小程序转化率")
    header_idx = find_header_row(rows, "指标")
    if header_idx == -1:
        return []
    result = []
    for row in rows[header_idx + 1 :]:
        metric = _normalize_text(row[0]) if row else ""
        if not metric:
            continue
        result.append(
            {
                "metric": metric,
                "value": _normalize_text(row[1]) if len(row) > 1 else "",
                "note": _normalize_text(row[2]) if len(row) > 2 else "",
                "source": "直播场次",
            }
        )
    return result


def extract_ip_comparison(path: Path) -> list[dict[str, Any]]:
    rows = read_sheet(path, "杨老师IP内容vs品类专家IP内容的流量与转化对比")
    header_idx = find_header_row(rows, "指标类别")
    if header_idx == -1:
        return []
    result = []
    for row in rows[header_idx + 1 :]:
        metric = _normalize_text(row[0]) if row else ""
        if not metric:
            continue
        result.append(
            {
                "metric": metric,
                "ip_value": safe_number(row[1]) if len(row) > 1 else None,
                "expert_value": safe_number(row[2]) if len(row) > 2 else None,
                "overall_value": safe_number(row[3]) if len(row) > 3 else None,
                "source": "杨老师IP对比",
            }
        )
    return result


def extract_content_ads(path: Path) -> list[dict[str, Any]]:
    rows = read_sheet(path, "内容投放")
    header = [str(c).strip() if c is not None else "" for c in rows[0]]
    index = {name: idx for idx, name in enumerate(header) if name}
    result = []
    for row in rows[1:]:
        order_idx = index.get("订单编号")
        order_id = _normalize_text(row[order_idx]) if order_idx is not None and order_idx < len(row) else ""
        if not order_id:
            continue
        spend_idx = index.get("投放金额（元）")
        view_idx = index.get("总播放量")
        engagement_idx = index.get("总互动量（爱心赞 + 拇指赞 + 关注 + 组件点击）")
        revenue_idx = index.get("转化收益（元）")
        roi_idx = index.get("ROI（%）")
        cpa_idx = index.get("单均获客成本（元 / 关注）")
        status_idx = index.get("订单状态")
        result.append(
            {
                "order_id": order_id,
                "spend": safe_number(row[spend_idx]) if spend_idx is not None and spend_idx < len(row) else None,
                "total_views": safe_number(row[view_idx]) if view_idx is not None and view_idx < len(row) else None,
                "engagement": _normalize_text(row[engagement_idx])
                if engagement_idx is not None and engagement_idx < len(row)
                else "",
                "conversion_revenue": safe_number(row[revenue_idx]) if revenue_idx is not None and revenue_idx < len(row) else None,
                "roi": safe_number(row[roi_idx]) if roi_idx is not None and roi_idx < len(row) else None,
                "cpa": _normalize_text(row[cpa_idx]) if cpa_idx is not None and cpa_idx < len(row) else "",
                "status": _normalize_text(row[status_idx]) if status_idx is not None and status_idx < len(row) else "",
                "source": "内容投放",
            }
        )
    return result


def extract_headcount(path: Path) -> dict[str, float]:
    rows = read_sheet(path, "2.7-3员工流失率及招聘到岗周期")
    if not rows:
        return {}
    header = [str(c).strip() if c is not None else "" for c in rows[0]]
    month_cols: dict[int, str] = {}
    for idx, value in enumerate(header):
        month = month_key(value)
        if month:
            month_cols[idx] = month
    totals: dict[str, float] = {month: 0.0 for month in month_cols.values()}
    for row in rows[1:]:
        dept = _normalize_text(row[0]) if row else ""
        if not dept:
            continue
        for idx, month in month_cols.items():
            if idx >= len(row):
                continue
            value = safe_number(row[idx])
            if value is None:
                continue
            totals[month] = totals.get(month, 0.0) + value
    return totals


def extract_cashflow(path: Path) -> dict[str, dict[str, float]]:
    rows = read_sheet(path, "2.4现金流量表")
    header_idx = find_header_row(rows, "项目")
    if header_idx == -1:
        return {}
    header = [str(c).strip() if c is not None else "" for c in rows[header_idx]]
    month_cols: dict[int, str] = {}
    for idx, value in enumerate(header):
        if value.endswith("月金额"):
            month = month_key(value.replace("金额", ""))
            if month:
                month_cols[idx] = month
    targets = {
        "cash_sales": "销售产成品、商品、提供劳务收到的现金",
        "cash_other_in": "收到其他与经营活动有关的现金",
        "cash_purchase": "购买原材料、商品、接受劳务支付的现金",
        "cash_salary": "支付的职工薪酬",
        "cash_tax": "支付的税费",
        "cash_other_out": "支付其他与经营活动有关的现金",
        "borrowings": "取得借款收到的现金",
        "cash_balance": "期末现金余额",
    }
    results: dict[str, dict[str, float]] = {month: {} for month in month_cols.values()}
    for row in rows[header_idx + 1 :]:
        label = _normalize_text(row[0])
        if not label:
            continue
        key = None
        for field_key, needle in targets.items():
            if needle in label:
                key = field_key
                break
        if not key:
            continue
        for idx, month in month_cols.items():
            if idx >= len(row):
                continue
            value = safe_number(row[idx])
            if value is None:
                continue
            results[month][key] = value
    return results


def table_aliases() -> dict[str, dict[str, list[str]]]:
    return {
        "T01_月度经营数据": {
            "month": ["month", "月份", "月度"],
            "base": ["base", "基地", "所属"],
            "gmv": ["gmv", "GMV"],
            "effective_sales": ["effective_sales", "有效销售额"],
            "service_fee_income": ["service_fee_income", "服务费", "回旋镖局服务费"],
            "total_orders": ["total_orders", "总订单量"],
            "auction_orders": ["auction_orders", "拍卖订单", "拍卖"],
            "fixed_price_orders": ["fixed_price_orders", "一口价订单", "一口价"],
            "sku_listed": ["sku_listed", "上架商品数", "上架数"],
            "sku_sold": ["sku_sold", "售出商品数", "售出"],
            "items_received": ["items_received", "签收数量", "收货量"],
            "items_rejected": ["items_rejected", "不通过数量", "拒收数量"],
            "active_sellers": ["active_sellers", "寄卖人数"],
            "new_customers": ["new_customers", "新客获取数"],
            "mau": ["mau", "MAU", "活跃用户"],
            "stale_items_60d": ["stale_items_60d", "滞销商品", "超过60天未售出"],
            "auction_success_rate": ["auction_success_rate", "成功率"],
            "avg_bid_rounds": ["avg_bid_rounds", "平均每场竞价轮次"],
            "inventory_turnover_days": ["inventory_turnover_days", "库存周转天数"],
            "daily_auth_capacity": ["daily_auth_capacity", "日均鉴定件数"],
        },
        "T02_月度财务数据": {
            "month": ["month", "月份", "月度"],
            "revenue_commission": ["revenue_commission", "服务费收入", "回旋镖局服务费"],
            "cost_salary": ["cost_salary", "工资及社保"],
            "cost_rent": ["cost_rent", "房租水电"],
            "cost_tech": ["cost_tech", "小程序投入成本"],
            "cost_logistics": ["cost_logistics", "物流总成本"],
            "cost_marketing": ["cost_marketing", "推广费"],
            "cost_travel": ["cost_travel", "差旅费"],
            "cost_platform_fee": ["cost_platform_fee", "平台费"],
            "cost_other": ["cost_other", "其他成本"],
            "cash_inflow_operations": ["cash_inflow_operations", "经营现金流入"],
            "cash_outflow_operations": ["cash_outflow_operations", "经营现金流出"],
            "borrowings": ["borrowings", "借款"],
            "cash_balance": ["cash_balance", "期末现金余额"],
            "headcount": ["headcount", "在岗人数", "员工总数"],
            "auth_team_size": ["auth_team_size", "鉴定师总数"],
        },
        "T03_客户分析": {
            "month": ["month", "月份", "月度", "时间"],
            "segment": ["segment", "tier", "分层", "层级", "等级"],
            "metric": ["metric", "指标", "指标名称"],
            "value": ["value", "数值", "值", "数据"],
            "value_ratio": ["ratio", "占比", "比率", "比例"],
            "customer_count": ["customer_count", "客户数量", "客户数"],
            "sales_total": ["sales_total", "销售额", "贡献额", "消费金额"],
            "sales_share": ["sales_share", "销售额占比", "贡献占比"],
            "transaction_count": ["transaction_count", "交易笔数"],
            "repeat_rate": ["repeat_rate", "复购率"],
            "registered_members": ["registered_members", "总注册会员数"],
            "paying_members": ["paying_members", "有消费会员数"],
            "conversion_rate": ["conversion_rate", "转化率"],
            "churn_90d_count": ["churn_90d_count", "流失客户数"],
            "churn_7d_rate": ["churn_7d_rate", "流失率"],
            "members_registered": ["members_registered", "注册会员数"],
            "members_ordered": ["members_ordered", "下单会员数"],
            "member_conversion_rate": ["member_conversion_rate", "注册当月转化率"],
            "members_registered_total": ["members_registered_total", "累计注册会员数"],
            "members_ordered_total": ["members_ordered_total", "累计下单会员数"],
            "source": ["source", "来源"],
        },
        "T04_品类分析": {
            "month": ["month", "月份"],
            "category_primary": ["category_primary", "一级品类", "品类"],
            "category_secondary": ["category_secondary", "二级品类"],
            "items_received": ["items_received", "签收数量", "收货量"],
            "listed_count": ["listed_count", "上架商品数量"],
            "delisted_count": ["delisted_count", "下架商品数量"],
            "auth_team_size": ["auth_team_size", "鉴定师数量"],
            "auth_output": ["auth_output", "累计鉴定产出量"],
            "auth_accuracy": ["auth_accuracy", "鉴定准确率"],
            "source": ["source", "来源"],
        },
        "T05_供应链效率": {
            "month": ["month", "月份"],
            "flow_type": ["flow_type", "类型", "收发"],
            "tickets": ["tickets", "票数", "订单票数"],
            "total_cost": ["total_cost", "物流总成本", "总成本"],
            "avg_cost": ["avg_cost", "平均单票费用"],
            "category_primary": ["category_primary", "类目", "品类"],
            "sop_days": ["sop_days", "平均天数"],
            "base": ["base", "基地"],
            "inventory_turnover_days": ["inventory_turnover_days", "库存周转天数"],
            "source": ["source", "来源"],
        },
        "T06_内容与IP": {
            "channel": ["channel", "平台", "渠道"],
            "period": ["period", "统计周期"],
            "publish_count": ["publish_count", "发布频次", "发布总频次"],
            "avg_views": ["avg_views", "单条平均播放", "单条平均阅读"],
            "total_views": ["total_views", "总播放", "总阅读"],
            "likes": ["likes", "点赞"],
            "comments": ["comments", "评论"],
            "shares": ["shares", "转发"],
            "metric": ["metric", "指标"],
            "value": ["value", "数值", "值"],
            "note": ["note", "说明"],
            "ip_value": ["ip_value", "IP"],
            "expert_value": ["expert_value", "专家"],
            "overall_value": ["overall_value", "整体"],
            "order_id": ["order_id", "订单编号"],
            "spend": ["spend", "投放金额"],
            "engagement": ["engagement", "互动量"],
            "conversion_revenue": ["conversion_revenue", "转化收益"],
            "roi": ["roi", "ROI"],
            "cpa": ["cpa", "获客成本"],
            "status": ["status", "状态"],
            "source": ["source", "来源"],
        },
    }


def resolve_field(field_names: list[str], aliases: list[str]) -> str | None:
    normalized = {name: name for name in field_names}
    lower = {name.lower(): name for name in field_names}
    for alias in aliases:
        if alias in normalized:
            return alias
        if alias.lower() in lower:
            return lower[alias.lower()]
    for alias in aliases:
        alias_lower = alias.lower()
        for name in field_names:
            if alias in name or alias_lower in name.lower():
                return name
    return None


def build_field_map(field_names: list[str], alias_map: dict[str, list[str]]) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for key, aliases in alias_map.items():
        match = resolve_field(field_names, aliases)
        if match:
            resolved[key] = match
    return resolved


def load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _read_json(path)


def _table_entry(registry: dict[str, Any], table_name: str) -> dict[str, Any] | None:
    tables = registry.get("tables") or registry.get("table_registry") or registry.get("table_map")
    if isinstance(tables, dict):
        entry = tables.get(table_name) or tables.get(table_name.replace("_", ""))
        if isinstance(entry, dict):
            return entry
    if isinstance(tables, list):
        for item in tables:
            name = str(item.get("table_name") or item.get("name") or item.get("key") or "")
            if name == table_name:
                return item
    return None


def resolve_table_target(registry: dict[str, Any], table_name: str) -> TableTarget | None:
    entry = _table_entry(registry, table_name)
    if not entry:
        return None
    table_id = str(entry.get("table_id") or entry.get("id") or "").strip()
    fields = entry.get("fields") or []
    if not isinstance(fields, list):
        fields = []
    return TableTarget(name=table_name, table_id=table_id, fields=fields)


def build_schema(fields: list[dict[str, Any]]) -> dict[str, Any]:
    type_map = {
        1: "text",
        2: "number",
        3: "single_select",
        4: "multi_select",
        5: "datetime",
        7: "checkbox",
        15: "url",
        17: "text",
        18: "text",
        22: "number",
    }
    schema_fields = []
    for field in fields:
        name = str(field.get("field_name") or field.get("name") or "").strip()
        if not name:
            continue
        raw_type = field.get("type") or field.get("field_type") or field.get("ui_type")
        if isinstance(raw_type, str):
            field_type = raw_type.lower()
        else:
            field_type = type_map.get(int(raw_type)) if raw_type is not None else "text"
        schema_fields.append({"name": name, "type": field_type})
    return {"fields": schema_fields}


def coerce_records(
    records: list[dict[str, Any]],
    field_map: dict[str, str],
    schema: dict[str, Any],
) -> list[dict[str, Any]]:
    schema_fields = {field["name"]: field for field in schema.get("fields", [])}
    output = []
    for record in records:
        mapped: dict[str, Any] = {}
        for key, value in record.items():
            target = field_map.get(key)
            if not target:
                continue
            mapped[target] = value
        normalized: dict[str, Any] = {}
        for name, value in mapped.items():
            field = schema_fields.get(name, {})
            field_type = str(field.get("type") or "").lower()
            if field_type == "datetime":
                if isinstance(value, str):
                    ts = month_to_timestamp_ms(value)
                    if ts is not None:
                        normalized[name] = ts
                        continue
                if isinstance(value, (int, float)):
                    normalized[name] = int(value)
                    continue
            if field_type == "number":
                number = safe_number(value)
                if number is not None:
                    normalized[name] = number
                    continue
            if value is None or value == "":
                continue
            normalized[name] = value
        if normalized:
            output.append(normalized)
    return output


def build_t01_records(data_stat: Path, finance: Path) -> list[dict[str, Any]]:
    income_by_base, _ = extract_income_by_base(finance)
    orders = extract_orders(data_stat)
    sku_listed = extract_sku_listed(data_stat)
    receipts = extract_receipts(data_stat)
    rejections = extract_rejections(data_stat)
    sellers = extract_active_sellers(data_stat)
    new_customers = extract_new_customers(data_stat)
    mau = extract_mau(data_stat)
    stale = extract_stale_items(data_stat)
    auction_metrics = extract_auction_metrics(data_stat)
    inventory_turnover = extract_inventory_turnover(data_stat)

    months = set()
    for month, _ in income_by_base.keys():
        months.add(month)
    months.update(orders.keys())
    months.update(receipts.keys())
    months.update(rejections.keys())
    months.update(sellers.keys())
    months.update(new_customers.keys())
    months.update(mau.keys())
    months.update(stale.keys())
    months.update(auction_metrics.keys())
    months = sorted(m for m in months if m)

    records: list[dict[str, Any]] = []
    bases = ["苏州", "广东", "合计"]
    for month in months:
        base_records: dict[str, dict[str, Any]] = {base: {"month": month, "base": base} for base in bases}
        for (m, base), metrics in income_by_base.items():
            if m != month:
                continue
            target = base_records.get(base)
            if not target:
                continue
            target.update(metrics)
        for base in ["苏州", "广东"]:
            key_fixed = f"fixed_price_orders::{base}"
            key_auction = f"auction_orders::{base}"
            key_total = f"total_orders::{base}"
            if month in orders:
                target = base_records[base]
                if key_fixed in orders[month]:
                    target["fixed_price_orders"] = orders[month][key_fixed]
                if key_auction in orders[month]:
                    target["auction_orders"] = orders[month][key_auction]
                if key_total in orders[month]:
                    target["total_orders"] = orders[month][key_total]
        if month in orders and "total_orders::合计" in orders[month]:
            base_records["合计"]["total_orders"] = orders[month]["total_orders::合计"]
        for base, value in sku_listed.items():
            if base in base_records:
                base_records[base]["sku_listed"] = value
        if month in receipts:
            base_records["合计"]["items_received"] = receipts[month]
        if month in rejections:
            base_records["合计"]["items_rejected"] = rejections[month]
        if month in sellers:
            base_records["合计"]["active_sellers"] = sellers[month]
        if month in new_customers:
            base_records["合计"]["new_customers"] = new_customers[month]
        if month in mau:
            base_records["合计"]["mau"] = mau[month]
        if month in stale:
            base_records["合计"]["stale_items_60d"] = stale[month]
        if month in auction_metrics:
            base_records["合计"].update(auction_metrics[month])
        for base, value in inventory_turnover.items():
            if base in base_records:
                base_records[base]["inventory_turnover_days"] = value
        for base in bases:
            base_records[base]["daily_auth_capacity"] = 46
        records.extend(base_records.values())
    return records


def build_t02_records(data_stat: Path, finance: Path) -> list[dict[str, Any]]:
    income_by_base, platform_fee = extract_income_by_base(finance)
    cost_struct = extract_cost_structure(finance)
    logistics = extract_logistics_cost(data_stat)
    cashflow = extract_cashflow(finance)
    headcount = extract_headcount(data_stat)

    monthly_service_fee: dict[str, float] = {}
    for (month, _), metrics in income_by_base.items():
        monthly_service_fee[month] = monthly_service_fee.get(month, 0.0) + metrics.get("service_fee_income", 0.0)

    months = set(monthly_service_fee.keys())
    months.update(cost_struct.keys())
    months.update(logistics.keys())
    months.update(cashflow.keys())
    months.update(headcount.keys())
    months = sorted(m for m in months if m)

    records = []
    for month in months:
        record: dict[str, Any] = {"month": month}
        if month in monthly_service_fee:
            record["revenue_commission"] = monthly_service_fee[month]
        if month in platform_fee:
            record["cost_platform_fee"] = platform_fee[month]
        cost = cost_struct.get(month, {})
        if cost:
            record["cost_salary"] = cost.get("cost_salary")
            record["cost_rent"] = cost.get("cost_rent")
            record["cost_tech"] = cost.get("cost_tech")
            record["cost_marketing"] = cost.get("cost_marketing")
            record["cost_travel"] = cost.get("cost_travel")
            record["cost_other"] = _sum_numbers(
                [
                    cost.get("packaging"),
                    cost.get("accessories"),
                    cost.get("inspection"),
                    cost.get("office"),
                    cost.get("entertainment"),
                    cost.get("welfare"),
                    cost.get("service_fee"),
                ]
            )
        if month in logistics:
            record["cost_logistics"] = _sum_numbers(
                [
                    logistics[month].get("inbound_cost"),
                    logistics[month].get("outbound_cost"),
                ]
            )
        if month in cashflow:
            inflow = _sum_numbers([cashflow[month].get("cash_sales"), cashflow[month].get("cash_other_in")])
            outflow = _sum_numbers(
                [
                    cashflow[month].get("cash_purchase"),
                    cashflow[month].get("cash_salary"),
                    cashflow[month].get("cash_tax"),
                    cashflow[month].get("cash_other_out"),
                ]
            )
            record["cash_inflow_operations"] = inflow
            record["cash_outflow_operations"] = outflow
            if cashflow[month].get("borrowings") is not None:
                record["borrowings"] = cashflow[month].get("borrowings")
            if cashflow[month].get("cash_balance") is not None:
                record["cash_balance"] = cashflow[month].get("cash_balance")
        if month in headcount:
            record["headcount"] = headcount[month]
        record["auth_team_size"] = 23
        records.append(record)
    return records


def build_t03_records(data_stat: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    records.extend(extract_customer_segment(data_stat))
    records.extend(extract_customer_segment_tech(data_stat))
    records.extend(extract_repeat_rate(data_stat))
    records.extend(extract_ltv(data_stat))
    records.extend(extract_churn(data_stat))
    records.extend(extract_member_conversion(data_stat))
    return records


def build_t04_records(data_stat: Path, finance: Path) -> list[dict[str, Any]]:
    receipts = extract_receipts_by_category(data_stat)
    listing = extract_category_listing(finance)
    auth = extract_auth_team(data_stat)
    for record in receipts:
        primary = record.get("category_primary")
        if primary in listing:
            record.update(listing[primary])
        if primary in auth:
            record.update(auth[primary])
    return receipts


def build_t05_records(data_stat: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    logistics = extract_logistics_cost(data_stat)
    for month, metrics in logistics.items():
        records.append(
            {
                "month": month,
                "flow_type": "发货",
                "tickets": metrics.get("outbound_tickets"),
                "total_cost": metrics.get("outbound_cost"),
                "avg_cost": metrics.get("outbound_avg_cost"),
                "source": "2.4-4物流成本明细",
            }
        )
        records.append(
            {
                "month": month,
                "flow_type": "收货",
                "tickets": metrics.get("inbound_tickets"),
                "total_cost": metrics.get("inbound_cost"),
                "avg_cost": metrics.get("inbound_avg_cost"),
                "source": "2.4-4物流成本明细",
            }
        )
    records.extend(extract_sop_efficiency(data_stat))
    inventory = extract_inventory_turnover(data_stat)
    for base, value in inventory.items():
        records.append(
            {
                "base": base,
                "inventory_turnover_days": value,
                "source": "2.2-3SKU库存周转天数",
            }
        )
    return records


def build_t06_records(data_stat: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    records.extend(extract_fans_growth(data_stat))
    records.extend(extract_live_metrics(data_stat))
    records.extend(extract_ip_comparison(data_stat))
    records.extend(extract_content_ads(data_stat))
    return records


def detect_metric_mode(field_names: list[str]) -> bool:
    return resolve_field(field_names, ["metric", "指标"]) is not None and resolve_field(field_names, ["value", "数值"]) is not None


def project_records_metric(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    projected = []
    for record in records:
        if "metric" in record and "value" in record:
            projected.append(record)
            continue
        for key, value in record.items():
            if key in {"month", "segment", "category_primary", "category_secondary", "source"}:
                continue
            if value is None or value == "":
                continue
            projected.append(
                {
                    "month": record.get("month"),
                    "segment": record.get("segment"),
                    "category_primary": record.get("category_primary"),
                    "category_secondary": record.get("category_secondary"),
                    "metric": key,
                    "value": value,
                    "source": record.get("source"),
                }
            )
    return projected


def write_records(
    api: FeishuBitableAPI,
    app_token: str,
    table_id: str,
    rows: list[dict[str, Any]],
) -> int:
    inserted = 0
    for start in range(0, len(rows), 500):
        batch = rows[start : start + 500]
        if not batch:
            continue
        api.batch_create_records(app_token, table_id, batch)
        inserted += len(batch)
    return inserted


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed TS-BRM-02 Phase1 data into Feishu Bitable.")
    parser.add_argument("--registry", default=str(ARTIFACT_ROOT / "table_registry.json"))
    parser.add_argument("--data-stat", default=str(Path("/Users/liming/Documents/会议纪要/【水月旧物造】/老杨回旋镖/数据统计.xlsx")))
    parser.add_argument("--finance-xls", default=str(Path("/Users/liming/Documents/会议纪要/【水月旧物造】/老杨回旋镖/财务尽调数据.xls")))
    parser.add_argument("--base-link", default="")
    parser.add_argument("--app-token", default="")
    parser.add_argument("--output", default=str(ARTIFACT_ROOT / "seed_phase1_report.json"))
    parser.add_argument("--log", default="")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    registry_path = Path(args.registry)
    registry = load_registry(registry_path)
    data_stat = Path(args.data_stat)
    finance = Path(args.finance_xls)
    apply_changes = bool(args.apply)

    tables = [
        "T01_月度经营数据",
        "T02_月度财务数据",
        "T03_客户分析",
        "T04_品类分析",
        "T05_供应链效率",
        "T06_内容与IP",
    ]

    extracted = {
        "T01_月度经营数据": build_t01_records(data_stat, finance),
        "T02_月度财务数据": build_t02_records(data_stat, finance),
        "T03_客户分析": build_t03_records(data_stat),
        "T04_品类分析": build_t04_records(data_stat, finance),
        "T05_供应链效率": build_t05_records(data_stat),
        "T06_内容与IP": build_t06_records(data_stat),
    }

    app_token = _normalize_text(args.app_token) or _normalize_text(registry.get("app_token"))
    base_link = _normalize_text(args.base_link) or _normalize_text(registry.get("base_link"))
    api = None
    if apply_changes:
        if not app_token and not base_link:
            raise RuntimeError("Missing app_token or base_link for apply mode")
        from dashboard.feishu_deploy import required_credentials

        app_id, app_secret = required_credentials()
        api = FeishuBitableAPI(app_id, app_secret)
        if not app_token and base_link:
            app_token = api.resolve_app_token(base_link)

    results = []
    for table_name in tables:
        target = resolve_table_target(registry, table_name)
        table_fields = target.fields if target else []
        field_names = [str(f.get("field_name") or f.get("name") or "") for f in table_fields if f]
        field_names = [name for name in field_names if name]
        alias_map = table_aliases().get(table_name, {})
        field_map = build_field_map(field_names, alias_map) if field_names else {}
        if not field_map and field_names:
            field_map = {name: name for name in field_names}
        schema = build_schema(table_fields) if table_fields else {"fields": []}

        raw_records = extracted.get(table_name, [])
        if detect_metric_mode(field_names):
            raw_records = project_records_metric(raw_records)

        mapped_records = coerce_records(raw_records, field_map, schema) if field_map else raw_records

        status = "dry-run" if not apply_changes else "pending"
        inserted = 0
        error = ""
        if apply_changes:
            if not target or not target.table_id:
                status = "skipped_missing_table_id"
            elif not mapped_records:
                status = "skipped_no_records"
            else:
                inserted = write_records(api, app_token, target.table_id, mapped_records)
                status = "inserted"
        results.append(
            {
                "table": table_name,
                "table_id": target.table_id if target else "",
                "records_extracted": len(raw_records),
                "records_ready": len(mapped_records),
                "status": status,
                "error": error,
                "field_map": field_map,
            }
        )

    report = {
        "mode": "apply" if apply_changes else "dry-run",
        "registry_path": str(registry_path),
        "data_stat_path": str(data_stat),
        "finance_path": str(finance),
        "app_token": app_token,
        "tables": results,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

    output_path = Path(args.output)
    _write_json(output_path, report)

    log_path = Path(args.log) if args.log else ARTIFACT_ROOT / "runs" / datetime.now().strftime("%Y-%m-%d") / "ts-brm-02-log.md"
    _ensure_dir(log_path.parent)
    log_lines = [
        f"# TS-BRM-02 Phase1 Log ({report['mode']})",
        "",
        f"Generated at: {report['generated_at']}",
        f"Registry: {report['registry_path']}",
        "",
        "| Table | Extracted | Ready | Status |",
        "| --- | ---: | ---: | --- |",
    ]
    for item in results:
        log_lines.append(
            f"| {item['table']} | {item['records_extracted']} | {item['records_ready']} | {item['status']} |"
        )
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
