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

PHASE_OPTIONS = ("ORIGIN", "AWAKENING", "DECODE", "CRAFT", "ALIGN", "LAUNCH", "ORBIT")
PERSONA_OPTIONS = ("英雄", "探险家", "小丑", "魔术师", "创造者", "革命者", "智者", "天真者", "照顾者", "情人", "统治者", "凡夫")
HIGHLIGHT_OPTIONS = ("L0无", "L1内部认可", "L2社群认可", "L3行业认可", "L4媒体资本认可")
MOTIVATION_OPTIONS = ("L1外部压力", "L2关系驱动", "L3竞争驱动", "L4内驱")
STATUS_OPTIONS = ("在训", "暂停", "毕业", "流失")
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
MILESTONE_TYPE_OPTIONS = ("第一次", "比赛获奖", "外部认可", "媒体报道", "投资意向", "产品发布", "用户反馈", "导师评语", "家长反馈", "学校展示", "社群分享")
CONTENT_VALUE_OPTIONS = ("招生", "融资", "媒体", "仅内部")
AUTH_STATUS_OPTIONS = ("未授权", "已口头授权", "已书面授权")
PUBLISHED_CHANNEL_OPTIONS = ("视频号", "抖音", "小红书", "LinkedIn", "朋友圈", "官网")
PROJECT_STATUS_OPTIONS = ("创意阶段", "原型阶段", "测试阶段", "已完成", "已获奖", "商业化中")
TECH_STACK_OPTIONS = ("ESP32", "Python", "Apple_Vision_Pro", "Gemini_API", "GPT", "Claude", "3D打印", "Arduino", "其他")
BUSINESS_VALUE_OPTIONS = ("无", "有潜力", "已有意向", "已有投资")
ASSET_TYPE_OPTIONS = ("视频", "照片", "PPT", "文字", "音频", "证书")
ASSET_AUTH_OPTIONS = ("已授权", "待授权", "未授权")
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
    return table_id, "existing"


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
    return {
        "table_key": spec.table_key,
        "table_name": spec.table_name,
        "table_id": table_id,
        "primary_field": spec.primary_field,
        "field_count": len(fields),
        "record_count": len(api.list_records(app_token, table_id)),
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
                text("责任助教"),
                text("家长姓名"),
                text("家长电话"),
                single_select("家长画像", ("焦虑型", "放养型", "投资型", "陪伴型")),
                single_select("状态", STATUS_OPTIONS),
                text("备注"),
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
                    "责任助教": "梁老师",
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
                    "责任助教": "梁老师",
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
                    "责任助教": "梁老师",
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
                number("时长分钟"),
                multi_select("模块", MODULE_OPTIONS),
                single_select("出勤状态", ATTENDANCE_OPTIONS),
                single_select("苏格拉底评级", SOCRATIC_OPTIONS),
                number("发言样本量"),
                number("英雄叙事评分"),
                single_select("叙事阶段", NARRATIVE_STAGE_OPTIONS),
                single_select("ZPD状态", ZPD_OPTIONS),
                single_select("布鲁姆认知层级", BLOOM_OPTIONS),
                single_select("JTBD挖掘层级", JTBD_OPTIONS),
                number("同理心设计五步"),
                text("D1证据"),
                text("D2证据"),
                text("D3证据"),
                text("D5证据"),
                text("D6证据"),
                text("金句名场面"),
                text("助教观察"),
                text("总教头批注"),
                url("录音链接"),
                text("AI转写摘要"),
                text("填写人"),
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
                text("总教头判断"),
                text("评估人"),
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
                    "D5抗压逆商": 2,
                    "D5行为证据": "面子心强 失败时容易沮丧",
                    "D5差值": 0,
                    "D6商业叙事": 2,
                    "D6行为证据": "只会说做了个帮盲人的东西",
                    "D6差值": 0,
                    "总分": 11,
                    "评估人": "文涛",
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
                    "D5抗压逆商": 4,
                    "D5行为证据": "Moonshot前一晚通宵没崩是关键突破 Claude误解框架时不气馁坚持判断选Gemini",
                    "D5差值": 2,
                    "D6商业叙事": 5,
                    "D6行为证据": "从做了个帮盲人的东西到让投资人当场掏钱 9个月3个量级跃升",
                    "D6差值": 3,
                    "总分": 23,
                    "费曼完整度": 4,
                    "总教头判断": "最强特质是问题感知+商业叙事 下一个突破口是D4仿真试错密度",
                    "评估人": "文涛",
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
                single_select("高光层级", RANKING_OPTIONS),
                text("外部认可来源"),
                single_select("关联Phase", PHASE_OPTIONS),
                url("证据链接"),
                single_select("内容资产价值", CONTENT_VALUE_OPTIONS),
                single_select("授权状态", AUTH_STATUS_OPTIONS),
                multi_select("已发布渠道", PUBLISHED_CHANNEL_OPTIONS),
                text("下一轮发射台"),
            ),
            records=(
                {
                    "里程碑ID": "M001",
                    "孩子ID": "S001",
                    "孩子姓名": "游小鹏",
                    "里程碑日期": "2025-08-15",
                    "里程碑类型": "第一次",
                    "标题": "第一次说出让我忘记时间的事",
                    "可引用金句": "那段时间我觉得我的人生可能就废了。但我说，不能再这样下去了。",
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
                    "里程碑类型": "外部认可",
                    "标题": "Google工程师深度认可Gemini进阶版",
                    "可引用金句": "融合Gemini多模态的新版获谷歌工程师深度认可",
                    "高光层级": "L3行业认可",
                    "关联Phase": "ALIGN",
                    "内容资产价值": "招生",
                    "授权状态": "已书面授权",
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
                text("授权主体"),
                multi_select("可用场景", USAGE_SCENARIO_OPTIONS),
                text("脱敏要求"),
                text("可引用金句"),
                multi_select("已发布渠道", PUBLISHED_CHANNEL_OPTIONS),
                url("文件链接"),
                text("备注"),
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
        "| 表名 | table_id | 字段数 | 记录数 | 动作 |",
        "|------|----------|--------|--------|------|",
    ]
    for item in table_results:
        lines.append(
            f"| {item['table_name']} | {item['table_id']} | {item['field_count']} | {item['record_count']} | {item['action']} |"
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
            table_result.update(
                {
                    "expected_count": len(spec.records),
                    "existing_count": 0,
                    "deleted_count": 0,
                    "inserted_count": len(spec.records),
                    "status": "planned_seed" if spec.records else "planned_empty",
                    "field_count": len(spec.fields),
                    "record_count": len(spec.records),
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
