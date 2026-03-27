#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.feishu_deploy import FeishuBitableAPI
from scripts.boomerang.ts_brm_01_build_base import api_request, ensure_table_fields, feishu_field_payload, load_api


TASK_ID = "PROJ-YSE-SMART-YOUTH-01"
TARGET_BASE_NAME = "智能少年·AI造物·统一驾驶舱"
DEFAULT_BASE_LINK = "https://h52xu4gwob.feishu.cn/wiki/N5tkwGJWoiVZqBkObwdcnI3inpf?from=from_copylink"
DEFAULT_ACCOUNT_ID = "feishu-claw"
SHANGHAI_TZ = timezone(timedelta(hours=8))
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "ai-da-guan-jia" / "runs"
PROJECT_ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "smart-youth"

PHASE_OPTIONS = ("ORIGIN", "AWAKENING", "DECODE", "CRAFT", "ALIGN", "LAUNCH", "ORBIT", "SPARK")
PERSONA_OPTIONS = ("英雄", "探险家", "小丑", "魔术师", "创造者", "革命者", "智者", "天真者", "照顾者", "情人", "统治者", "凡夫")
HIGHLIGHT_OPTIONS = ("L0无", "L1内部认可", "L2社群认可", "L3行业认可", "L4媒体资本认可")
MOTIVATION_OPTIONS = ("L1外部压力", "L2关系驱动", "L3竞争驱动", "L4内驱")
STATUS_OPTIONS = ("在训", "暂停", "毕业", "流失")
BASE_RATING_OPTIONS = ("L", "M", "H")
GRADE_OPTIONS = (
    "小学1年级",
    "小学2年级",
    "小学3年级",
    "小学4年级",
    "小学5年级",
    "小学6年级",
    "初中1年级",
    "初中2年级",
    "初中3年级",
    "高中1年级",
    "高中2年级",
    "高中3年级",
)
SOURCE_OPTIONS = ("短视频", "转介绍", "学校合作", "水月渠道", "活动引流", "其他")
PRODUCT_LINE_OPTIONS = ("3万标准营", "30万VIP陪跑", "300万机构合作", "体验营")
STAGE_OPTIONS = ("关卡1找自己", "关卡2原力觉醒", "关卡3商科科创", "关卡4三角整合", "关卡5探索营", "关卡6先锋营", "关卡7竞技赛", "关卡8引爆SPARK")
RANKING_OPTIONS = ("L0内部完成", "L1内部认可", "L2社群认可", "L3行业认可", "L4媒体资本认可")
ACTIVITY_TYPE_OPTIONS = ("训练营", "周末课", "日常练习", "比赛", "Demo_Day", "外部活动", "线上辅导", "1对1")
MODULE_OPTIONS = ("原力觉醒", "科学创业", "科技创新", "商业叙事", "AI工具", "动手造物")
ATTENDANCE_OPTIONS = ("全程", "部分", "缺席", "线上参与")
SOCRATIC_OPTIONS = ("H", "M", "L")
NARRATIVE_STAGE_OPTIONS = ("前英雄期", "觉醒期", "英雄已启程")
ZPD_OPTIONS = ("偏难", "命中", "偏易")
BLOOM_OPTIONS = ("L1记忆", "L2理解", "L3应用", "L4分析", "L5评估", "L6创造")
JTBD_OPTIONS = ("L1功能层", "L2情感层", "L3社交层")
REVIEW_OPTIONS = ("未复核", "已复核", "存疑")
PORTER_OPTIONS = ("L1无依据", "L2功能差异", "L3成本优势", "L4差异化定位", "L5护城河")
KOLBERG_OPTIONS = ("L1服从权威", "L2互惠交换", "L3关系维持", "L4规则意识", "L5原则驱动")
MILESTONE_TYPE_OPTIONS = ("燃料确认", "组队完成", "首件作品上线", "首条真实反馈", "首次小额付费", "首单真实成交", "比赛获奖", "外部投资意向", "媒体报道", "Phase晋级", "孵化触发")
CONTENT_VALUE_OPTIONS = ("招生", "融资", "媒体", "仅内部")
AUTH_STATUS_OPTIONS = ("未授权", "已口头授权", "已书面授权")
PUBLISHED_CHANNEL_OPTIONS = ("视频号", "抖音", "小红书", "LinkedIn", "朋友圈", "官网")
PROJECT_STATUS_OPTIONS = ("创意阶段", "原型阶段", "测试阶段", "已完成", "已获奖", "商业化中")
TECH_STACK_OPTIONS = ("ESP32", "Python", "Apple_Vision_Pro", "Gemini_API", "GPT", "Claude", "3D打印", "Arduino", "其他")
BUSINESS_VALUE_OPTIONS = ("无", "有潜力", "已有意向", "已有投资")
ASSET_TYPE_OPTIONS = ("视频", "照片", "PPT", "文字", "音频", "证书")
ASSET_AUTH_OPTIONS = ("已授权", "待授权", "未授权")
ACHIEVEMENT_OPTIONS = ("燃料点燃", "三角对齐", "首件作品", "首次付费", "引爆时刻")
USAGE_SCENARIO_OPTIONS = ("招生", "融资", "媒体", "国际赛事", "仅内部")
CHANNEL_SOURCE_OPTIONS = ("短视频引流", "水月渠道", "学校合作", "转介绍", "活动引流")
RENEWAL_STATUS_OPTIONS = ("首次", "续费", "升级")
ROLE_OPTIONS = ("总教头", "首席导师", "助教", "特邀导师")
EXPERTISE_OPTIONS = ("商科", "科创", "AI工具", "硬件", "仿真", "叙事", "设计")
TOOL_OPTIONS = ("坎贝尔英雄之旅", "维果茨基ZPD", "马斯洛动机", "德韦克思维模式", "布鲁姆认知", "JTBD用户任务", "费曼检验", "d.school共情", "波特竞争", "科尔伯格道德")
ORG_TYPE_OPTIONS = ("公立学校", "私立学校", "国际学校", "培训机构", "政府机构")
ENGAGEMENT_OPTIONS = ("潜在", "初次接触", "方案沟通", "合同谈判", "已签约", "已交付", "流失")
COOPERATION_OPTIONS = ("AI造物进校", "TTT培训", "联合招生", "研究院合作")


@dataclass(frozen=True)
class TableSpec:
    table_key: str
    table_name: str
    primary_field: str
    fields: tuple[dict[str, Any], ...]
    records: tuple[dict[str, Any], ...] = ()

    @property
    def field_names(self) -> list[str]:
        return [str(field["name"]) for field in self.fields]


@dataclass(frozen=True)
class ViewConditionSpec:
    field_name: str
    operator: str
    value: Any


@dataclass(frozen=True)
class ViewSpec:
    table_key: str
    view_name: str
    conditions: tuple[ViewConditionSpec, ...] = ()
    view_type: str = "grid"
    layout_note: str = ""


def text(name: str) -> dict[str, Any]:
    return {"name": name, "type": "text"}


def number(name: str) -> dict[str, Any]:
    return {"name": name, "type": "number"}


def single_select(name: str, options: tuple[str, ...]) -> dict[str, Any]:
    return {"name": name, "type": "single_select", "options": list(options)}


def multi_select(name: str, options: tuple[str, ...]) -> dict[str, Any]:
    return {"name": name, "type": "multi_select", "options": list(options)}


def datetime_field(name: str) -> dict[str, Any]:
    return {"name": name, "type": "datetime", "property": {"date_formatter": "yyyy-MM-dd"}}


def url(name: str) -> dict[str, Any]:
    return {"name": name, "type": "url"}


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def shanghai_now() -> datetime:
    return datetime.now(tz=SHANGHAI_TZ)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def split_tokens(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        tokens: list[str] = []
        for item in value:
            tokens.extend(split_tokens(item))
        return tokens
    text_value = normalize_text(value)
    if not text_value:
        return []
    pieces = re.split(r"[,\n，、;/+|]+", text_value)
    return [piece.strip() for piece in pieces if piece.strip()]


def to_ms(value: Any) -> int | str:
    if value in {None, ""}:
        return ""
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=SHANGHAI_TZ)
        return int(dt.timestamp() * 1000)
    if isinstance(value, date):
        dt = datetime(value.year, value.month, value.day, tzinfo=SHANGHAI_TZ)
        return int(dt.timestamp() * 1000)
    if isinstance(value, (int, float)):
        numeric = int(value)
        return numeric if abs(numeric) >= 10**12 else numeric * 1000
    text_value = normalize_text(value)
    if not text_value:
        return ""
    if text_value.isdigit():
        numeric = int(text_value)
        return numeric if abs(numeric) >= 10**12 else numeric * 1000
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text_value):
        parsed_date = date.fromisoformat(text_value)
        dt = datetime(parsed_date.year, parsed_date.month, parsed_date.day, tzinfo=SHANGHAI_TZ)
        return int(dt.timestamp() * 1000)
    try:
        parsed = datetime.fromisoformat(text_value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=SHANGHAI_TZ)
        return int(parsed.timestamp() * 1000)
    except ValueError:
        return text_value


def normalize_value(field: dict[str, Any], value: Any) -> Any:
    if value is None or value == "" or value == []:
        return None
    field_type = str(field.get("type") or "text").strip().lower()
    if field_type == "datetime":
        return to_ms(value)
    if field_type == "number":
        if isinstance(value, (int, float)):
            return value
        text_value = normalize_text(value).replace(",", "")
        if not text_value:
            return None
        try:
            return int(text_value)
        except ValueError:
            try:
                return float(text_value)
            except ValueError:
                return text_value
    if field_type == "single_select":
        text_value = normalize_text(value)
        return text_value or None
    if field_type == "multi_select":
        if isinstance(value, list):
            tokens = [normalize_text(item) for item in value if normalize_text(item)]
            return tokens or None
        tokens = split_tokens(value)
        return tokens or None
    if field_type == "url":
        if isinstance(value, dict):
            link = normalize_text(value.get("link"))
            text_value = normalize_text(value.get("text")) or link
            if not link:
                return None
            return {"link": link, "text": text_value}
        text_value = normalize_text(value)
        if not text_value:
            return None
        return {"link": text_value, "text": text_value}
    text_value = normalize_text(value)
    return text_value or None


def normalize_record(spec: TableSpec, row: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for field in spec.fields:
        field_name = str(field["name"])
        if field_name not in row:
            continue
        value = normalize_value(field, row[field_name])
        if value is None or value == "" or value == []:
            continue
        normalized[field_name] = value
    return normalized


def table_fields_payload(spec: TableSpec) -> list[dict[str, Any]]:
    return [feishu_field_payload(field) for field in spec.fields]


def build_view_specs() -> list[ViewSpec]:
    return [
        ViewSpec(
            table_key="T01",
            view_name="学员全景",
            conditions=(ViewConditionSpec("状态", "is", "在训"),),
            layout_note="按当前Phase分组 + D1基线评级排序",
        ),
        ViewSpec(
            table_key="T02",
            view_name="D1燃料追踪",
            conditions=(
                ViewConditionSpec("苏格拉底评级", "is", "H"),
                ViewConditionSpec("人工复核状态", "is", "已复核"),
            ),
            layout_note="按孩子ID分组 + 苏格拉底评级时间排序",
        ),
        ViewSpec(
            table_key="T03",
            view_name="六维折线图",
            conditions=(ViewConditionSpec("总教头复核", "is", "已复核"),),
            layout_note="按孩子ID + 评估时间点 + 差值字段拉折线",
        ),
        ViewSpec(
            table_key="T04",
            view_name="高光时刻墙",
            conditions=(ViewConditionSpec("授权状态", "is", "已书面授权"),),
            layout_note="按里程碑类型分组 + 授权状态=已授权",
        ),
        ViewSpec(
            table_key="T06",
            view_name="内容资产看板",
            conditions=(ViewConditionSpec("授权状态", "isNot", "未授权"),),
            layout_note="按授权状态分组 + 待授权优先",
        ),
    ]


def view_specs_for_table(table_key: str) -> tuple[ViewSpec, ...]:
    return tuple(spec for spec in build_view_specs() if spec.table_key == table_key)


def rename_base(api: FeishuBitableAPI, app_token: str, name: str) -> dict[str, Any]:
    response = api_request(api, f"/open-apis/bitable/v1/apps/{app_token}", method="PUT", payload={"name": name})
    return response.get("data", {}).get("app", {}) or response.get("data", {}) or {}


def rename_table(api: FeishuBitableAPI, app_token: str, table_id: str, name: str) -> dict[str, Any]:
    response = api_request(api, f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}", method="PATCH", payload={"name": name})
    return response.get("data", {}).get("table", {}) or response.get("data", {}) or {}


def list_tables_by_name(api: FeishuBitableAPI, app_token: str) -> dict[str, dict[str, Any]]:
    tables = api.list_tables(app_token)
    return {normalize_text(item.get("name") or item.get("table_name") or ""): item for item in tables}


def list_fields_by_name(api: FeishuBitableAPI, app_token: str, table_id: str) -> dict[str, dict[str, Any]]:
    fields = api.list_fields(app_token, table_id)
    return {normalize_text(item.get("field_name") or item.get("name") or ""): item for item in fields}


def list_views_by_name(api: FeishuBitableAPI, app_token: str, table_id: str) -> dict[str, dict[str, Any]]:
    response = api_request(api, f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/views?page_size=500")
    items = (response.get("data") or {}).get("items") or []
    return {normalize_text(item.get("view_name") or item.get("name") or ""): item for item in items}


def _view_condition_value(field: dict[str, Any], value: Any) -> str:
    field_type = int(field.get("type") or 0)
    property_payload = field.get("property") or {}
    options = property_payload.get("options") or []
    option_ids_by_name = {
        normalize_text(option.get("name") or ""): normalize_text(option.get("id") or "")
        for option in options
        if normalize_text(option.get("name") or "") and normalize_text(option.get("id") or "")
    }

    if field_type in {3, 4} and option_ids_by_name:
        if isinstance(value, list):
            labels = [normalize_text(item) for item in value if normalize_text(item)]
        else:
            label = normalize_text(value)
            labels = [label] if label else []
        option_ids = [option_ids_by_name[label] for label in labels if label in option_ids_by_name]
        if not option_ids:
            raise RuntimeError(f"View filter option missing in live base for field {field.get('field_name') or field.get('name')}")
        return json.dumps(option_ids, ensure_ascii=False)

    if isinstance(value, list):
        tokens = [normalize_text(item) for item in value if normalize_text(item)]
    else:
        text_value = normalize_text(value)
        tokens = [text_value] if text_value else []
    return json.dumps(tokens, ensure_ascii=False)


def build_view_property_payload(
    view_spec: ViewSpec,
    fields_by_name: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if not view_spec.conditions:
        return None
    conditions: list[dict[str, Any]] = []
    for condition in view_spec.conditions:
        field = fields_by_name.get(condition.field_name)
        if not field:
            raise RuntimeError(f"View filter field missing in live base: {view_spec.table_key}.{condition.field_name}")
        field_id = normalize_text(field.get("field_id") or field.get("id") or "")
        if not field_id:
            raise RuntimeError(f"View filter field id missing in live base: {view_spec.table_key}.{condition.field_name}")
        conditions.append(
            {
                "field_id": field_id,
                "operator": condition.operator,
                "value": _view_condition_value(field, condition.value),
            }
        )
    return {"filter_info": {"conditions": conditions, "conjunction": "and"}}


def create_view(api: FeishuBitableAPI, app_token: str, table_id: str, view_name: str, view_type: str = "grid") -> dict[str, Any]:
    response = api_request(
        api,
        f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/views",
        method="POST",
        payload={"view_name": view_name, "view_type": view_type},
    )
    return response.get("data", {}).get("view", {}) or response.get("data", {}) or {}


def update_view(
    api: FeishuBitableAPI,
    app_token: str,
    table_id: str,
    view_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    response = api_request(
        api,
        f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/views/{view_id}",
        method="PATCH",
        payload=payload,
    )
    return response.get("data", {}).get("view", {}) or response.get("data", {}) or {}


def delete_all_records(api: FeishuBitableAPI, app_token: str, table_id: str) -> int:
    deleted = 0
    for record in api.list_records(app_token, table_id):
        record_id = normalize_text(record.get("record_id") or record.get("id") or "")
        if not record_id:
            continue
        api_request(api, f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}", method="DELETE")
        deleted += 1
    return deleted


def ensure_table(
    api: FeishuBitableAPI,
    app_token: str,
    spec: TableSpec,
    *,
    apply: bool,
    existing_tables: dict[str, dict[str, Any]],
) -> tuple[str, str]:
    table = existing_tables.get(spec.table_name)
    source_name = spec.table_name

    if table is None and spec.table_key == "T01":
        placeholder = existing_tables.get("数据表")
        if placeholder is not None and not existing_tables.get(spec.table_name):
            table = placeholder
            source_name = "数据表"

    if table is None:
        if not apply:
            return f"dryrun::{spec.table_name}", "planned_create"
        created = api.create_table(app_token, spec.table_name, table_fields_payload(spec))
        table_id = normalize_text(created.get("table_id") or "")
        if not table_id:
            raise RuntimeError(f"Failed to create table {spec.table_name}: {json.dumps(created, ensure_ascii=False)}")
        ensure_table_views(api, app_token, table_id, spec, apply=True)
        return table_id, "created"

    table_id = normalize_text(table.get("table_id") or "")
    current_name = normalize_text(table.get("name") or table.get("table_name") or "")
    if apply and current_name != spec.table_name:
        rename_table(api, app_token, table_id, spec.table_name)
    elif not apply and current_name != spec.table_name:
        return table_id or f"dryrun::{spec.table_name}", f"planned_rename_from_{source_name}"

    if apply:
        ensure_table_fields(
            api,
            app_token,
            table_id,
            {"table_name": spec.table_name, "fields": list(spec.fields)},
            apply=True,
            log_lines=[],
        )
        ensure_table_views(api, app_token, table_id, spec, apply=True)
    return table_id, "existing"


def ensure_table_views(
    api: FeishuBitableAPI,
    app_token: str,
    table_id: str,
    spec: TableSpec,
    *,
    apply: bool,
) -> list[dict[str, Any]]:
    view_specs = view_specs_for_table(spec.table_key)
    if not view_specs:
        return []
    if not table_id or table_id.startswith("dryrun::"):
        return [
            {
                "view_name": view_spec.view_name,
                "view_type": view_spec.view_type,
                "layout_note": view_spec.layout_note,
                "status": "planned",
            }
            for view_spec in view_specs
        ]

    fields_by_name = {
        normalize_text(item.get("field_name") or item.get("name") or ""): item
        for item in api.list_fields(app_token, table_id)
    }
    views_by_name = list_views_by_name(api, app_token, table_id)
    results: list[dict[str, Any]] = []
    for view_spec in view_specs:
        current = views_by_name.get(view_spec.view_name)
        action = "existing"
        if current is None:
            if not apply:
                results.append(
                    {
                        "view_name": view_spec.view_name,
                        "view_type": view_spec.view_type,
                        "layout_note": view_spec.layout_note,
                        "status": "planned_create",
                    }
                )
                continue
            created = create_view(api, app_token, table_id, view_spec.view_name, view_spec.view_type)
            view_id = normalize_text(created.get("view_id") or "")
            if not view_id:
                raise RuntimeError(f"Failed to create view {spec.table_key}.{view_spec.view_name}: {json.dumps(created, ensure_ascii=False)}")
            views_by_name[view_spec.view_name] = created
            current = created
            action = "created"
        view_id = normalize_text(current.get("view_id") or "")
        if not view_id:
            raise RuntimeError(f"Missing view_id for {spec.table_key}.{view_spec.view_name}")
        if current.get("view_type") and normalize_text(current.get("view_type") or "") != view_spec.view_type:
            raise RuntimeError(
                f"View type mismatch for {spec.table_key}.{view_spec.view_name}: "
                f"expected {view_spec.view_type}, got {current.get('view_type')}"
            )
        property_payload = build_view_property_payload(view_spec, fields_by_name)
        if property_payload and apply:
            updated = update_view(
                api,
                app_token,
                table_id,
                view_id,
                {"view_name": view_spec.view_name, "property": property_payload},
            )
            action = "updated" if action == "existing" else action
            if updated:
                views_by_name[view_spec.view_name] = updated
                current = updated
        results.append(
            {
                "view_name": view_spec.view_name,
                "view_id": view_id,
                "view_type": view_spec.view_type,
                "layout_note": view_spec.layout_note,
                "status": action if apply else "planned_update" if property_payload else "planned",
            }
        )
    return results


def seed_table(api: FeishuBitableAPI, app_token: str, table_id: str, spec: TableSpec, *, apply: bool) -> dict[str, Any]:
    expected_count = len(spec.records)
    if not apply:
        return {
            "expected_count": expected_count,
            "existing_count": 0,
            "deleted_count": 0,
            "inserted_count": expected_count,
            "status": "planned_seed" if expected_count else "planned_empty",
        }

    existing_records = api.list_records(app_token, table_id)
    deleted_count = 0
    if existing_records:
        deleted_count = delete_all_records(api, app_token, table_id)

    inserted_count = 0
    if expected_count:
        normalized_rows = [normalize_record(spec, row) for row in spec.records]
        for start in range(0, len(normalized_rows), 500):
            batch = [row for row in normalized_rows[start : start + 500] if row]
            if batch:
                api.batch_create_records(app_token, table_id, batch)
                inserted_count += len(batch)

    verified_count = len(api.list_records(app_token, table_id))
    if verified_count != expected_count:
        raise RuntimeError(
            f"Seed count mismatch for {spec.table_name}: expected {expected_count}, got {verified_count}"
        )
    return {
        "expected_count": expected_count,
        "existing_count": len(existing_records),
        "deleted_count": deleted_count,
        "inserted_count": inserted_count,
        "status": "seeded" if expected_count else "emptied",
    }


def table_registry_entry(api: FeishuBitableAPI, app_token: str, spec: TableSpec, table_id: str) -> dict[str, Any]:
    fields = api.list_fields(app_token, table_id)
    field_ids = {normalize_text(field.get("field_name") or field.get("name") or ""): normalize_text(field.get("field_id") or "") for field in fields}
    views = list_views_by_name(api, app_token, table_id) if table_id and not table_id.startswith("dryrun::") else {}
    view_names = list(views.keys()) or [view_spec.view_name for view_spec in view_specs_for_table(spec.table_key)]
    return {
        "table_key": spec.table_key,
        "table_name": spec.table_name,
        "table_id": table_id,
        "primary_field": spec.primary_field,
        "field_count": len(fields),
        "record_count": len(api.list_records(app_token, table_id)),
        "view_count": len(view_names),
        "views": view_names,
        "field_ids": field_ids,
    }


def build_table_specs() -> list[TableSpec]:
    return [
        TableSpec(
            table_key="T01",
            table_name="T01_学员主档案",
            primary_field="孩子ID",
            fields=(
                text("孩子ID"),
                text("姓名"),
                text("昵称"),
                single_select("性别", ("男", "女")),
                number("出生年份"),
                number("当前年龄"),
                single_select("年级", GRADE_OPTIONS),
                text("学校名称"),
                single_select("来源渠道", SOURCE_OPTIONS),
                single_select("产品线", PRODUCT_LINE_OPTIONS),
                datetime_field("入营日期"),
                single_select("当前Phase", PHASE_OPTIONS),
                single_select("当前关卡", STAGE_OPTIONS),
                single_select("原力人格主型", PERSONA_OPTIONS),
                single_select("原力人格副型", PERSONA_OPTIONS),
                single_select("原力人格第三型", PERSONA_OPTIONS),
                text("内在驱动方向"),
                single_select("铁三角初始位置", ("科技方法端", "灵性原力端", "商业价值端")),
                text("代表作品"),
                single_select("最高高光层级", HIGHLIGHT_OPTIONS),
                single_select("动机层级", MOTIVATION_OPTIONS),
                single_select("D1基线评级", BASE_RATING_OPTIONS),
                single_select("D3基线评级", BASE_RATING_OPTIONS),
                single_select("D6基线评级", BASE_RATING_OPTIONS),
                single_select("肖像权授权", ("已授权", "未授权")),
                multi_select("已解锁成就", ACHIEVEMENT_OPTIONS),
                single_select("关卡代号", PHASE_OPTIONS),
                text("责任助教"),
                text("家长姓名"),
                text("家长电话"),
                single_select("家长画像", ("焦虑型", "放养型", "投资型", "陪伴型")),
                single_select("状态", STATUS_OPTIONS),
            ),
            records=(
                {
                    "孩子ID": "S001",
                    "姓名": "游小鹏",
                    "昵称": "小鹏",
                    "性别": "男",
                    "出生年份": 2013,
                    "当前年龄": 13,
                    "年级": "小学6年级",
                    "学校名称": "清实学校",
                    "来源渠道": "学校合作",
                    "产品线": "3万标准营",
                    "入营日期": "2025-06-01",
                    "当前Phase": "ALIGN",
                    "当前关卡": "关卡4三角整合",
                    "原力人格主型": "英雄",
                    "原力人格副型": "创造者",
                    "原力人格第三型": "革命者",
                    "内在驱动方向": "帮助弱势群体用AI解决生活问题",
                    "铁三角初始位置": "科技方法端",
                    "代表作品": "妆点你的眼",
                    "最高高光层级": "L4媒体资本认可",
                    "动机层级": "L4内驱",
                    "D1基线评级": "H",
                    "D3基线评级": "H",
                    "D6基线评级": "H",
                    "肖像权授权": "已授权",
                    "已解锁成就": ["燃料点燃", "三角对齐", "首件作品"],
                    "关卡代号": "ALIGN",
                    "责任助教": "梁老师",
                    "家长姓名": "涛哥",
                    "家长电话": "",
                    "家长画像": "投资型",
                    "状态": "在训",
                },
                {
                    "孩子ID": "S002",
                    "姓名": "高思予",
                    "昵称": "思予",
                    "性别": "女",
                    "出生年份": 2014,
                    "当前年龄": 12,
                    "年级": "小学5年级",
                    "学校名称": "清实学校",
                    "来源渠道": "学校合作",
                    "产品线": "3万标准营",
                    "入营日期": "2026-03-02",
                    "当前Phase": "DECODE",
                    "当前关卡": "关卡1找自己",
                    "原力人格主型": "探险家",
                    "原力人格副型": "小丑",
                    "原力人格第三型": "魔术师",
                    "内在驱动方向": "探索未知/不被束缚",
                    "铁三角初始位置": "灵性原力端",
                    "代表作品": "不摸鱼",
                    "最高高光层级": "L1内部认可",
                    "动机层级": "L3竞争驱动",
                    "D1基线评级": "H",
                    "D3基线评级": "M",
                    "D6基线评级": "H",
                    "肖像权授权": "已授权",
                    "关卡代号": "DECODE",
                    "责任助教": "梁老师",
                    "家长姓名": "",
                    "家长电话": "",
                    "家长画像": "陪伴型",
                    "状态": "在训",
                },
                {
                    "孩子ID": "S003",
                    "姓名": "吕嘉禾",
                    "昵称": "嘉禾",
                    "性别": "男",
                    "出生年份": 2013,
                    "当前年龄": 13,
                    "年级": "小学6年级",
                    "学校名称": "清实学校",
                    "来源渠道": "学校合作",
                    "产品线": "3万标准营",
                    "入营日期": "2026-03-02",
                    "当前Phase": "DECODE",
                    "当前关卡": "关卡1找自己",
                    "铁三角初始位置": "科技方法端",
                    "内在驱动方向": "数学计算/工程基础",
                    "最高高光层级": "L1内部认可",
                    "D1基线评级": "M",
                    "D3基线评级": "H",
                    "D6基线评级": "L",
                    "肖像权授权": "未授权",
                    "关卡代号": "DECODE",
                    "责任助教": "梁老师",
                    "家长姓名": "",
                    "家长电话": "",
                    "家长画像": "放养型",
                    "状态": "在训",
                },
            ),
        ),
        TableSpec(
            table_key="T02",
            table_name="T02_活动与学习日志",
            primary_field="日志ID",
            fields=(
                text("日志ID"),
                text("孩子ID"),
                text("孩子姓名"),
                datetime_field("日期"),
                single_select("类型", ACTIVITY_TYPE_OPTIONS),
                text("活动名称"),
                single_select("对应Phase", PHASE_OPTIONS),
                single_select("出勤状态", ATTENDANCE_OPTIONS),
                single_select("苏格拉底评级", SOCRATIC_OPTIONS),
                number("发言样本量"),
                single_select("样本量状态", ("充足", "不足")),
                single_select("人工复核状态", ("未复核", "已复核", "需复核")),
                number("主动提问次数"),
                number("追问最深层数"),
                number("深挖语言频次"),
                text("持续停留话题"),
                text("D1一句话总结"),
                single_select("与上次D1对比", ("上升", "持平", "下降", "首次")),
                text("关键行为记录"),
                number("英雄叙事评分"),
                single_select("叙事阶段", NARRATIVE_STAGE_OPTIONS),
                single_select("ZPD状态", ZPD_OPTIONS),
                single_select("布鲁姆认知层级", BLOOM_OPTIONS),
                single_select("JTBD挖掘层级", JTBD_OPTIONS),
                number("同理心设计五步"),
                text("D1证据"),
                text("D2证据"),
                text("D3表现观察"),
                text("D5表现观察"),
                text("D6表现观察"),
                text("金句名场面"),
                text("助教观察"),
                text("总教头批注"),
                url("录音链接"),
                text("AI转写摘要"),
                text("填写人"),
                text("提取模型"),
                text("提取提示词版本"),
                datetime_field("提取时间"),
                text("下一步建议动作"),
            ),
            records=(
                {
                    "日志ID": "L001",
                    "孩子ID": "S001",
                    "孩子姓名": "游小鹏",
                    "日期": "2026-02-05",
                    "类型": "比赛",
                    "活动名称": "Moonshot48黑客松·妆点你的眼",
                    "对应Phase": "ALIGN",
                    "出勤状态": "全程",
                    "苏格拉底评级": "H",
                    "发言样本量": 18,
                    "样本量状态": "充足",
                    "人工复核状态": "已复核",
                    "主动提问次数": 8,
                    "追问最深层数": 4,
                    "深挖语言频次": 12,
                    "持续停留话题": "有·反复追问视障用户怎么判断位置",
                    "D1一句话总结": "对视障人群化妆自主权有强烈使命感",
                    "与上次D1对比": "上升",
                    "关键行为记录": "Moonshot48冠军；董科含（前YC/奇绩创坛）现场提出投资20万美金意向——全场最年轻，唯一小学生技术实现者",
                    "英雄叙事评分": 4,
                    "叙事阶段": "英雄已启程",
                    "ZPD状态": "命中",
                    "布鲁姆认知层级": "L6创造",
                    "JTBD挖掘层级": "L3社交层",
                    "同理心设计五步": 4,
                    "D1证据": "对视障人群的具体痛点有天然敏感",
                    "D2证据": "主动追问产品如何解决真实场景问题",
                    "D3表现观察": "组内唯一技术实现者；独立实现Apple Vision+Gemini+STT/TTS全栈；自己写语音转文字功能",
                    "D5表现观察": "技术迭代对话中遇Claude误解框架仍坚持选型，主动决策换Gemini 2.0 Flash",
                    "D6表现观察": "路演时用「盲人也爱美」开场，现场震撼；谷歌老师说「没想到是这么小的孩子」",
                    "金句名场面": "12岁的他，用AI让盲人第一次独立完成了化妆。",
                    "助教观察": "48小时内保持高密度迭代，能自己判断模型选型",
                    "总教头批注": "趁热安排DGX Spark黑客松作为下一个高光时刻；协助硬件化方向立项",
                    "AI转写摘要": "从用户痛点、技术方案到商业叙事均已形成闭环",
                    "填写人": "Rosy",
                    "提取模型": "Claude Sonnet 4",
                    "提取提示词版本": "V1.1",
                    "提取时间": "2026-02-05",
                    "下一步建议动作": "趁热安排DGX Spark黑客松作为下一个高光时刻；协助硬件化方向立项",
                },
                {
                    "日志ID": "L002",
                    "孩子ID": "S001",
                    "孩子姓名": "游小鹏",
                    "日期": "2026-03-12",
                    "类型": "外部活动",
                    "活动名称": "Google Cloud技术交流活动",
                    "对应Phase": "ALIGN",
                    "出勤状态": "全程",
                    "苏格拉底评级": "H",
                    "发言样本量": 9,
                    "样本量状态": "充足",
                    "人工复核状态": "已复核",
                    "主动提问次数": 5,
                    "追问最深层数": 3,
                    "深挖语言频次": 8,
                    "持续停留话题": "有·持续追问技术问答场景",
                    "D1一句话总结": "现场表达具备强烈的自驱与讲述感",
                    "与上次D1对比": "上升",
                    "关键行为记录": "Google Cloud老师评价完全没想到是这么小的孩子",
                    "英雄叙事评分": 3,
                    "叙事阶段": "英雄已启程",
                    "ZPD状态": "命中",
                    "布鲁姆认知层级": "L5评估",
                    "JTBD挖掘层级": "L3社交层",
                    "同理心设计五步": 3,
                    "D1证据": "能在外部活动中主动追问老师",
                    "D2证据": "对模型与平台的能力边界有比较意识",
                    "D3表现观察": "活动中能清楚描述自己的作品结构",
                    "D5表现观察": "面对外部老师的提问不怯场",
                    "D6表现观察": "在技术问答中能自然形成展示叙事",
                    "金句名场面": "完全没想到是这么小的孩子",
                    "助教观察": "表现稳定，能在外部场合完整表达",
                    "总教头批注": "可作为招生场景的外部可信背书",
                    "AI转写摘要": "外部交流中展现出成熟的表达和技术讲述能力",
                    "填写人": "Rosy",
                    "提取模型": "Claude Sonnet 4",
                    "提取提示词版本": "V1.1",
                    "提取时间": "2026-03-12",
                    "下一步建议动作": "整理成招生用短视频切片与海报文案",
                },
                {
                    "日志ID": "L003",
                    "孩子ID": "S001",
                    "孩子姓名": "游小鹏",
                    "日期": "2026-03-15",
                    "类型": "线上辅导",
                    "活动名称": "技术迭代对话（编程沟通记录）",
                    "对应Phase": "ALIGN",
                    "出勤状态": "全程",
                    "苏格拉底评级": "H",
                    "发言样本量": 11,
                    "样本量状态": "充足",
                    "人工复核状态": "已复核",
                    "主动提问次数": 6,
                    "追问最深层数": 4,
                    "深挖语言频次": 9,
                    "持续停留话题": "有·持续围绕模型选型和技术实现方式",
                    "D1一句话总结": "问题定义与技术判断都在持续升级",
                    "与上次D1对比": "上升",
                    "关键行为记录": "自主决策Gemini 2.0 Flash选型；独立实现Apple Vision Framework；语音转文字自研",
                    "英雄叙事评分": 4,
                    "叙事阶段": "英雄已启程",
                    "ZPD状态": "命中",
                    "布鲁姆认知层级": "L6创造",
                    "JTBD挖掘层级": "L3社交层",
                    "同理心设计五步": 4,
                    "D1证据": "能主动判断方案是否真正解决用户问题",
                    "D2证据": "对AI工具链的对比判断越来越清楚",
                    "D3表现观察": "自主决策Gemini 2.0 Flash选型；独立实现Apple Vision Framework；语音转文字自研",
                    "D5表现观察": "Claude误解框架时不气馁，坚持判断后切换到更合适的模型",
                    "D6表现观察": "能把技术路径讲成听得懂的项目故事",
                    "金句名场面": "技术不是堆功能，而是把问题拆开再重组",
                    "助教观察": "对话中能主动纠错，并快速迭代实现路径",
                    "总教头批注": "该批次已进入稳定上升通道",
                    "AI转写摘要": "模型选型、实现路径与表达方式都更主动",
                    "填写人": "梁老师",
                    "提取模型": "Claude Sonnet 4",
                    "提取提示词版本": "V1.1",
                    "提取时间": "2026-03-15",
                    "下一步建议动作": "保持高密度技术对话，尽快做下一轮公开展示",
                },
                {
                    "日志ID": "L004",
                    "孩子ID": "S001",
                    "孩子姓名": "游小鹏",
                    "日期": "2026-03-02",
                    "类型": "训练营",
                    "活动名称": "清实学校开营",
                    "对应Phase": "AWAKENING",
                    "出勤状态": "全程",
                    "苏格拉底评级": "M",
                    "发言样本量": 6,
                    "样本量状态": "不足",
                    "人工复核状态": "未复核",
                    "主动提问次数": 2,
                    "追问最深层数": 2,
                    "深挖语言频次": 3,
                    "持续停留话题": "有·开营阶段持续观察孩子状态",
                    "D1一句话总结": "入营后开始形成更清晰的问题意识",
                    "与上次D1对比": "首次",
                    "关键行为记录": "入营第1天；与高思予/吕嘉禾初见",
                    "英雄叙事评分": 2,
                    "叙事阶段": "前英雄期",
                    "ZPD状态": "偏难",
                    "布鲁姆认知层级": "L2理解",
                    "JTBD挖掘层级": "L2情感层",
                    "同理心设计五步": 2,
                    "D1证据": "对新环境有明显观察和适应过程",
                    "D2证据": "刚接触训练营时主要处于熟悉阶段",
                    "D3表现观察": "初次接触时已能跟上基本流程",
                    "D5表现观察": "对任务要求的理解需要更多引导",
                    "D6表现观察": "表达仍偏简单但开始出现主动意愿",
                    "金句名场面": "先让孩子把话说完，再看问题在哪里",
                    "助教观察": "适应期状态稳定",
                    "总教头批注": "适合作为基线记录和后续对比起点",
                    "AI转写摘要": "开营首周的观察以适应与信任建立为主",
                    "填写人": "梁老师",
                    "提取模型": "Claude Sonnet 4",
                    "提取提示词版本": "V1.1",
                    "提取时间": "2026-03-02",
                    "下一步建议动作": "继续建立安全感，鼓励孩子开口描述自己的问题",
                },
            ),
        ),
        TableSpec(
            table_key="T03",
            table_name="T03_六维成长评估",
            primary_field="评估ID",
            fields=(
                text("评估ID"),
                text("孩子ID"),
                text("孩子姓名"),
                text("评估时间点"),
                datetime_field("评估日期"),
                single_select("总教头复核", REVIEW_OPTIONS),
                number("D1发现问题"),
                text("D1行为证据"),
                number("D1差值"),
                number("D2AI驾驭"),
                text("D2行为证据"),
                number("D2差值"),
                number("D3动手造物"),
                text("D3行为证据"),
                number("D3差值"),
                number("D4仿真试错"),
                text("D4行为证据"),
                number("D4差值"),
                number("D5抗压逆商"),
                text("D5行为证据"),
                number("D5差值"),
                number("D6商业叙事"),
                text("D6行为证据"),
                number("D6差值"),
                number("总分"),
                number("费曼完整度"),
                single_select("波特竞争层级", PORTER_OPTIONS),
                single_select("科尔伯格协作动机", KOLBERG_OPTIONS),
                single_select("综合潜力评级", ("观察期", "有潜力", "强潜力", "顶级苗子")),
                single_select("三轮验证进度", ("第1轮完成", "第2轮完成", "第3轮完成")),
                single_select("推荐下一步", ("继续当前阶段", "推进下一阶段", "回ORIGIN找燃料", "1对1加强")),
                text("总教头判断"),
                text("总教头备注"),
            ),
            records=(
                {
                    "评估ID": "E001",
                    "孩子ID": "S001",
                    "孩子姓名": "游小鹏",
                    "评估时间点": "入营基线",
                    "评估日期": "2025-06-01",
                    "总教头复核": "已复核",
                    "D1发现问题": 3,
                    "D1行为证据": "对弱势群体有天然同理心 但问题定义能力尚未训练",
                    "D1差值": 0,
                    "D2AI驾驭": 2,
                    "D2行为证据": "会用ChatGPT基础对话 未接触过多模态",
                    "D2差值": 0,
                    "D3动手造物": 2,
                    "D3行为证据": "有编程基础 曾一度放弃后自主重回",
                    "D3差值": 0,
                    "D4仿真试错": 1,
                    "D4行为证据": "初测时对仿真思维仍在建立中",
                    "D4差值": 0,
                    "D5抗压逆商": 2,
                    "D5行为证据": "面子心强 失败时容易沮丧",
                    "D5差值": 0,
                    "D6商业叙事": 2,
                    "D6行为证据": "只会说做了个帮盲人的东西",
                    "D6差值": 0,
                    "总分": 11,
                    "费曼完整度": 1,
                    "波特竞争层级": "L1无依据",
                    "科尔伯格协作动机": "L2互惠交换",
                    "综合潜力评级": "顶级苗子",
                    "三轮验证进度": "第2轮完成",
                    "推荐下一步": "推进下一阶段",
                    "总教头判断": "最强特质是同理心 下一个突破口是D4仿真试错",
                    "总教头备注": "面子心强但自驱力极强；Moonshot冠军后D1/D3/D6全部验证到H级；建议直接进ESP32先锋评估。评估人：文涛",
                },
                {
                    "评估ID": "E002",
                    "孩子ID": "S001",
                    "孩子姓名": "游小鹏",
                    "评估时间点": "ALIGN阶段 Moonshot48后",
                    "评估日期": "2026-03-01",
                    "总教头复核": "已复核",
                    "D1发现问题": 5,
                    "D1行为证据": "Moonshot48全程主动追问视障用户痛点3层 项目选题来自真实社会问题而非老师指定",
                    "D1差值": 2,
                    "D2AI驾驭": 4,
                    "D2行为证据": "主动选型Gemini 2.0 Flash vs其他模型 熟练使用Claude Code 能评估不同模型能力差异",
                    "D2差值": 2,
                    "D3动手造物": 5,
                    "D3行为证据": "组内唯一技术实现者 Apple Vision+Gemini+STT/TTS全栈独立实现 自写语音转文字模块",
                    "D3差值": 3,
                    "D4仿真试错": 3,
                    "D4行为证据": "开始能在高压场景下主动验证方案路径",
                    "D4差值": 2,
                    "D5抗压逆商": 4,
                    "D5行为证据": "Moonshot前一晚通宵没崩是关键突破 Claude误解框架时不气馁坚持判断选Gemini",
                    "D5差值": 2,
                    "D6商业叙事": 5,
                    "D6行为证据": "从做了个帮盲人的东西到让投资人当场掏钱 9个月3个量级跃升",
                    "D6差值": 3,
                    "总分": 23,
                    "费曼完整度": 4,
                    "波特竞争层级": "L4差异化定位",
                    "科尔伯格协作动机": "L3关系维持",
                    "综合潜力评级": "强潜力",
                    "三轮验证进度": "第1轮完成",
                    "推荐下一步": "继续当前阶段",
                    "总教头判断": "最强特质是问题感知+商业叙事 下一个突破口是D4仿真试错密度",
                    "总教头备注": "日常观测也已进入明显上升通道，适合和比赛高光一起看；评估人：文涛",
                },
            ),
        ),
        TableSpec(
            table_key="T04",
            table_name="T04_里程碑与高光时刻",
            primary_field="里程碑ID",
            fields=(
                text("里程碑ID"),
                text("孩子ID"),
                text("孩子姓名"),
                datetime_field("里程碑日期"),
                single_select("里程碑类型", MILESTONE_TYPE_OPTIONS),
                text("标题"),
                text("可引用金句"),
                text("详细记录"),
                text("记录人"),
                single_select("高光层级", RANKING_OPTIONS),
                text("外部认可来源"),
                single_select("关联Phase", PHASE_OPTIONS),
                url("证据链接"),
                single_select("内容资产价值", CONTENT_VALUE_OPTIONS),
                single_select("授权状态", AUTH_STATUS_OPTIONS),
                multi_select("已发布渠道", PUBLISHED_CHANNEL_OPTIONS),
                text("下一轮发射台"),
                text("众筹结算主体"),
            ),
            records=(
                {
                    "里程碑ID": "M001",
                    "孩子ID": "S001",
                    "孩子姓名": "游小鹏",
                    "里程碑日期": "2025-08-15",
                    "里程碑类型": "燃料确认",
                    "标题": "第一次说出让我忘记时间的事",
                    "可引用金句": "那段时间我觉得我的人生可能就废了。但我说，不能再这样下去了。",
                    "记录人": "梁老师",
                    "高光层级": "L0内部完成",
                    "关联Phase": "ORIGIN",
                    "内容资产价值": "仅内部",
                    "授权状态": "已口头授权",
                },
                {
                    "里程碑ID": "M002",
                    "孩子ID": "S001",
                    "孩子姓名": "游小鹏",
                    "里程碑日期": "2026-02-07",
                    "里程碑类型": "比赛获奖",
                    "标题": "Moonshot48黑客松冠军",
                    "可引用金句": "12岁的他，用AI让盲人第一次独立完成了化妆。",
                    "详细记录": "2026.2.5-7 Moonshot48黑客松 Group5 小学生唯一技术实现者 48小时全栈实现 Apple Vision Pro+Gemini API+语音交互",
                    "记录人": "Rosy",
                    "高光层级": "L4媒体资本认可",
                    "外部认可来源": "前YC/奇绩创坛 董科含（投资人）$20万意向",
                    "关联Phase": "ALIGN",
                    "内容资产价值": "融资",
                    "授权状态": "已书面授权",
                    "下一轮发射台": "以Moonshot冠军为起点 冲DGX Spark黑客松（3月29日）建立连续高光叙事",
                },
                {
                    "里程碑ID": "M003",
                    "孩子ID": "S001",
                    "孩子姓名": "游小鹏",
                    "里程碑日期": "2026-03-15",
                    "里程碑类型": "外部投资意向",
                    "标题": "Google工程师深度认可Gemini进阶版",
                    "可引用金句": "融合Gemini多模态的新版获谷歌工程师深度认可",
                    "记录人": "Rosy",
                    "高光层级": "L3行业认可",
                    "外部认可来源": "Google工程师",
                    "关联Phase": "ALIGN",
                    "内容资产价值": "招生",
                    "授权状态": "已书面授权",
                },
                {
                    "里程碑ID": "M004",
                    "孩子ID": "S001",
                    "孩子姓名": "游小鹏",
                    "里程碑日期": "2026-03-29",
                    "里程碑类型": "比赛获奖",
                    "标题": "DGX Spark黑客松备战中",
                    "可引用金句": "（3月29日训练营后更新）",
                    "记录人": "Rosy",
                    "高光层级": "L0内部完成",
                    "关联Phase": "ALIGN",
                    "内容资产价值": "仅内部",
                    "授权状态": "未授权",
                    "下一轮发射台": "3月29日训练营后立即更新本条记录",
                },
            ),
        ),
        TableSpec(
            table_key="T05",
            table_name="T05_作品与项目",
            primary_field="项目ID",
            fields=(
                text("项目ID"),
                text("孩子ID"),
                text("孩子姓名"),
                text("项目名称"),
                text("一句话描述"),
                text("解决的问题"),
                multi_select("技术栈", TECH_STACK_OPTIONS),
                single_select("状态", PROJECT_STATUS_OPTIONS),
                datetime_field("起始日期"),
                datetime_field("最新更新"),
                url("Demo链接"),
                url("展示视频"),
                text("参赛记录"),
                single_select("商业价值", BUSINESS_VALUE_OPTIONS),
            ),
            records=(
                {
                    "项目ID": "P001",
                    "孩子ID": "S001",
                    "孩子姓名": "游小鹏",
                    "项目名称": "妆点你的眼",
                    "一句话描述": "用AI让视障人士独立完成化妆",
                    "解决的问题": "全球3700万视障人士无法独立化妆 依赖他人 失去尊严",
                    "状态": "已获奖",
                    "起始日期": "2025-12-01",
                    "最新更新": "2026-03-15",
                    "参赛记录": "Moonshot48冠军 Google活动展示",
                    "商业价值": "已有投资",
                },
            ),
        ),
        TableSpec(
            table_key="T06",
            table_name="T06_对外展示资产",
            primary_field="资产ID",
            fields=(
                text("资产ID"),
                text("孩子ID"),
                text("孩子姓名"),
                text("关联里程碑ID"),
                text("资产名称"),
                single_select("资产类型", ASSET_TYPE_OPTIONS),
                single_select("授权状态", ASSET_AUTH_OPTIONS),
                datetime_field("授权有效期"),
                text("授权主体"),
                multi_select("可用场景", USAGE_SCENARIO_OPTIONS),
                text("脱敏要求"),
                text("可引用金句"),
                multi_select("已发布渠道", PUBLISHED_CHANNEL_OPTIONS),
                url("文件链接"),
                text("备注"),
            ),
            records=(
                {"资产ID": "AST001", "孩子ID": "S001", "孩子姓名": "游小鹏", "关联里程碑ID": "M002", "资产名称": "Moonshot48路演视频（妆点你的眼）", "资产类型": "视频", "授权状态": "已授权", "授权有效期": "2027-02-07", "授权主体": "家长+孩子", "可用场景": ["招生", "融资", "媒体"], "脱敏要求": "无需脱敏", "可引用金句": "12岁，用AI让盲人第一次独立完成了化妆", "已发布渠道": ["视频号", "官网"]},
                {"资产ID": "AST002", "孩子ID": "S001", "孩子姓名": "游小鹏", "关联里程碑ID": "M002", "资产名称": "Moonshot48比赛PPT（全9页）", "资产类型": "PPT", "授权状态": "已授权", "授权有效期": "2027-02-07", "授权主体": "家长+孩子", "可用场景": ["招生", "媒体"], "可引用金句": "我们验证了：视障女性也希望尝试化妆，这样的困境真实存在", "已发布渠道": ["官网"]},
                {"资产ID": "AST003", "孩子ID": "S001", "孩子姓名": "游小鹏", "资产名称": "原力人格测评报告（英雄+创造者+革命者）", "资产类型": "文字", "授权状态": "已授权", "授权有效期": "2027-03-15", "授权主体": "家长+孩子", "可用场景": ["招生", "仅内部"], "脱敏要求": "隐藏家庭信息", "可引用金句": "有志者事竟成·你想象得到的我就能让它成真·规则就是拿来打破的", "已发布渠道": ["朋友圈"]},
                {"资产ID": "AST004", "孩子ID": "S001", "孩子姓名": "游小鹏", "关联里程碑ID": "M003", "资产名称": "Google Cloud活动现场照片", "资产类型": "照片", "授权状态": "已授权", "授权有效期": "2027-03-15", "授权主体": "家长+孩子", "可用场景": ["招生", "媒体"], "可引用金句": "谷歌工程师说：完全没想到是这么小的孩子", "已发布渠道": ["视频号", "小红书"]},
                {"资产ID": "AST005", "孩子ID": "S001", "孩子姓名": "游小鹏", "资产名称": "清实学校学习记录（3周日志）", "资产类型": "文字", "授权状态": "已授权", "授权有效期": "2027-03-31", "授权主体": "家长+孩子", "可用场景": ["仅内部", "招生"], "脱敏要求": "不暴露家庭地址", "已发布渠道": ["官网"]},
                {"资产ID": "AST006", "孩子ID": "S001", "孩子姓名": "游小鹏", "资产名称": "编程技术沟通记录（Gemini选型）", "资产类型": "文字", "授权状态": "已授权", "授权有效期": "2027-03-31", "授权主体": "内部授权", "可用场景": ["仅内部"], "已发布渠道": []},
                {"资产ID": "AST007", "孩子ID": "S001", "孩子姓名": "游小鹏", "资产名称": "价值识别访谈录音", "资产类型": "音频", "授权状态": "待授权", "授权主体": "家长", "可用场景": ["仅内部"], "脱敏要求": "需删除敏感个人经历描述", "备注": "脱敏完成前不对外"},
                {"资产ID": "AST008", "孩子ID": "S002", "孩子姓名": "高思予", "资产名称": "原力人格测评报告（探险家+小丑+魔术师）", "资产类型": "文字", "授权状态": "待授权", "授权主体": "家长", "可用场景": ["仅内部"], "脱敏要求": "隐藏家庭信息", "备注": "待家长确认后再对外"},
                {"资产ID": "AST009", "孩子ID": "S003", "孩子姓名": "吕嘉禾", "资产名称": "清实学校学习记录", "资产类型": "文字", "授权状态": "待授权", "授权主体": "家长", "可用场景": ["仅内部"], "脱敏要求": "不暴露家庭地址", "备注": "待家长确认后再对外"},
            ),
        ),
        TableSpec(
            table_key="T07",
            table_name="T07_产品线与成交",
            primary_field="成交ID",
            fields=(
                text("成交ID"),
                text("孩子ID"),
                text("家长姓名"),
                single_select("产品线", PRODUCT_LINE_OPTIONS),
                number("成交金额"),
                datetime_field("成交日期"),
                single_select("渠道来源", CHANNEL_SOURCE_OPTIONS),
                text("关联机构ID"),
                single_select("续费状态", RENEWAL_STATUS_OPTIONS),
                text("备注"),
            ),
            records=(
                {"成交ID": "ORD001", "孩子ID": "S001", "家长姓名": "（保密）", "产品线": "3万标准营", "成交金额": 30000, "成交日期": "2025-06-01", "渠道来源": "学校合作", "续费状态": "首次"},
                {"成交ID": "ORD002", "孩子ID": "S002", "家长姓名": "（保密）", "产品线": "3万标准营", "成交金额": 30000, "成交日期": "2026-03-02", "渠道来源": "学校合作", "续费状态": "首次"},
                {"成交ID": "ORD003", "孩子ID": "S003", "家长姓名": "（保密）", "产品线": "3万标准营", "成交金额": 30000, "成交日期": "2026-03-02", "渠道来源": "学校合作", "续费状态": "首次"},
            ),
        ),
        TableSpec(
            table_key="T08",
            table_name="T08_机构合作追踪",
            primary_field="机构ID",
            fields=(
                text("机构ID"),
                text("机构名称"),
                single_select("类型", ORG_TYPE_OPTIONS),
                text("地区"),
                text("决策人"),
                single_select("接洽状态", ENGAGEMENT_OPTIONS),
                single_select("合作模式", COOPERATION_OPTIONS),
                number("预估年合同额"),
                number("实际签约额"),
                text("下一步行动"),
                datetime_field("最新跟进日期"),
                text("备注"),
            ),
            records=(
                {
                    "机构ID": "ORG001",
                    "机构名称": "清实学校",
                    "类型": "私立学校",
                    "地区": "广东清远",
                    "接洽状态": "已签约",
                    "合作模式": "AI造物进校",
                },
                {
                    "机构ID": "ORG002",
                    "机构名称": "WAB京西学校",
                    "类型": "国际学校",
                    "地区": "北京",
                    "接洽状态": "方案沟通",
                    "合作模式": "AI造物进校",
                },
            ),
        ),
        TableSpec(
            table_key="T09",
            table_name="T09_助教与导师",
            primary_field="人员ID",
            fields=(
                text("人员ID"),
                text("姓名"),
                single_select("角色", ROLE_OPTIONS),
                multi_select("专长", EXPERTISE_OPTIONS),
                text("联系方式"),
                single_select("状态", ("在岗", "兼职", "离岗")),
            ),
            records=(
                {"人员ID": "STAFF001", "姓名": "文涛", "角色": "总教头", "专长": ["商科", "AI工具", "叙事"], "状态": "在岗"},
                {"人员ID": "STAFF002", "姓名": "梁老师", "角色": "助教", "专长": ["AI工具", "科创"], "状态": "在岗"},
                {"人员ID": "STAFF003", "姓名": "明哥", "角色": "首席导师", "专长": ["商科"], "状态": "兼职"},
                {"人员ID": "STAFF004", "姓名": "罗斯博士", "角色": "特邀导师", "专长": ["硬件", "仿真", "科创"], "状态": "兼职"},
            ),
        ),
        TableSpec(
            table_key="T10",
            table_name="T10_评估工具库",
            primary_field="评估记录ID",
            fields=(
                text("评估记录ID"),
                text("孩子ID"),
                text("关联活动ID"),
                single_select("工具名称", TOOL_OPTIONS),
                text("评估结果"),
                number("量化评分"),
                text("证据"),
                text("评估人"),
                datetime_field("评估日期"),
            ),
        ),
    ]


def write_registry_and_report(
    *,
    run_dir: Path,
    registry_path: Path,
    report_path: Path,
    mode: str,
    base_before: dict[str, Any],
    base_after: dict[str, Any],
    app_token: str,
    source_link: str,
    table_results: list[dict[str, Any]],
) -> None:
    registry = {
        "task_id": TASK_ID,
        "mode": mode,
        "source_link": source_link,
        "app_token": app_token,
        "base_name_before": normalize_text(base_before.get("name") or ""),
        "base_name_after": normalize_text(base_after.get("name") or TARGET_BASE_NAME),
        "created_at": shanghai_now().isoformat(),
        "tables": {item["table_name"]: item for item in table_results},
    }
    write_json(registry_path, registry)

    lines = [
        f"# {TASK_ID} 建表与灌数报告",
        "",
        f"- Mode: `{mode}`",
        f"- Base: `{registry['base_name_after']}`",
        f"- app_token: `{app_token}`",
        f"- Source: `{source_link}`",
        f"- Run Dir: `{run_dir}`",
        "",
        "## Tables",
        "",
        "| 表名 | table_id | 字段数 | 视图数 | 记录数 | 动作 |",
        "|------|----------|--------|--------|--------|------|",
    ]
    for item in table_results:
        lines.append(
            f"| {item['table_name']} | {item['table_id']} | {item['field_count']} | {item.get('view_count', 0)} | {item['record_count']} | {item['action']} |"
        )
    write_text(report_path, "\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and seed the Smart Youth Feishu base.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--link", default=DEFAULT_BASE_LINK, help="Feishu wiki or base link.")
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--project-artifact-root", default=str(PROJECT_ARTIFACT_ROOT))
    args = parser.parse_args()

    apply_changes = bool(args.apply)
    source_link = str(args.link).strip()
    run_id = normalize_text(args.run_id) or f"adagj-{now_stamp()}-smart-youth-01"
    run_dir = ARTIFACT_ROOT / datetime.now().date().isoformat() / run_id
    ensure_dir(run_dir)
    project_artifact_root = Path(args.project_artifact_root).expanduser().resolve()
    ensure_dir(project_artifact_root)

    api = load_api(args.account_id)
    # The source link already resolves to an existing base token; use it directly.
    app_token = api.resolve_app_token(source_link)

    base_before = api._request(f"/open-apis/bitable/v1/apps/{app_token}", method="GET").get("data", {}).get("app", {}) or {}
    if apply_changes and normalize_text(base_before.get("name") or "") != TARGET_BASE_NAME:
        rename_base(api, app_token, TARGET_BASE_NAME)
    base_after = api._request(f"/open-apis/bitable/v1/apps/{app_token}", method="GET").get("data", {}).get("app", {}) or {}

    existing_tables = list_tables_by_name(api, app_token)
    table_specs = build_table_specs()
    table_results: list[dict[str, Any]] = []

    for spec in table_specs:
        table_id, action = ensure_table(api, app_token, spec, apply=apply_changes, existing_tables=existing_tables)
        table_result: dict[str, Any] = {
            "table_key": spec.table_key,
            "table_name": spec.table_name,
            "table_id": table_id,
            "action": action,
            "expected_seed_count": len(spec.records),
        }
        if apply_changes:
            seed_result = seed_table(api, app_token, table_id, spec, apply=True)
            field_summary = table_registry_entry(api, app_token, spec, table_id)
            table_result.update(seed_result)
            table_result.update(field_summary)
        else:
            planned_view_names = [view_spec.view_name for view_spec in view_specs_for_table(spec.table_key)]
            table_result.update(
                {
                    "expected_count": len(spec.records),
                    "existing_count": 0,
                    "deleted_count": 0,
                    "inserted_count": len(spec.records),
                    "status": "planned_seed" if spec.records else "planned_empty",
                    "field_count": len(spec.fields),
                    "record_count": len(spec.records),
                    "view_count": len(planned_view_names),
                    "views": planned_view_names,
                    "field_ids": {},
                }
            )
        table_results.append(table_result)

    if apply_changes:
        current_tables = list_tables_by_name(api, app_token)
        if len(current_tables) != len(table_specs):
            raise RuntimeError(f"Expected {len(table_specs)} tables, found {len(current_tables)}")

    registry_path = run_dir / "smart-youth-table-registry.json"
    report_path = run_dir / "smart-youth-build-report.md"
    mirror_registry_path = project_artifact_root / "smart-youth-table-registry.json"
    write_registry_and_report(
        run_dir=run_dir,
        registry_path=registry_path,
        report_path=report_path,
        mode="apply" if apply_changes else "dry-run",
        base_before=base_before,
        base_after=base_after,
        app_token=app_token,
        source_link=source_link,
        table_results=table_results,
    )
    if apply_changes:
        # Keep a project-level copy for easier handoff.
        write_json(mirror_registry_path, json.loads(registry_path.read_text(encoding="utf-8")))

    summary = {
        "task_id": TASK_ID,
        "mode": "apply" if apply_changes else "dry-run",
        "run_id": run_id,
        "run_dir": str(run_dir),
        "base_name_before": normalize_text(base_before.get("name") or ""),
        "base_name_after": normalize_text(base_after.get("name") or TARGET_BASE_NAME),
        "app_token": app_token,
        "source_link": source_link,
        "registry_path": str(registry_path),
        "project_registry_path": str(mirror_registry_path),
        "report_path": str(report_path),
        "table_count": len(table_results),
        "tables": table_results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
