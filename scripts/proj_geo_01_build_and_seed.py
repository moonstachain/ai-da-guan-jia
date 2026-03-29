#!/usr/bin/env python3
"""PROJ-GEO-01: build and seed the Phase 1 GEO Feishu base."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.feishu_deploy import FeishuBitableAPI, normalize_record, schema_field_to_feishu_field
from scripts.create_kangbo_signal_tables import DEFAULT_ACCOUNT_ID, load_feishu_credentials


TASK_ID = "PROJ-GEO-01"
BASE_LINK = "https://h52xu4gwob.feishu.cn/wiki/N68XwFCHjiWaa3kwgeCcKRELnoe?from=from_copylink"
BASE_TITLE = "原力GEO-操作系统"
TRIAL_SCOPE = "YSE"
SHANGHAI_TZ = timezone(timedelta(hours=8))

ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "proj-geo-01"
DOCS_ROOT = Path("/Users/liming/Documents")

TEXT_FIELD = "text"
NUMBER_FIELD = "number"
SINGLE_SELECT_FIELD = "single_select"
MULTI_SELECT_FIELD = "multi_select"
DATETIME_FIELD = "datetime"


def now_local() -> datetime:
    return datetime.now(tz=SHANGHAI_TZ).replace(microsecond=0)


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_client(account_id: str = DEFAULT_ACCOUNT_ID) -> FeishuBitableAPI:
    creds = load_feishu_credentials(account_id)
    os.environ["FEISHU_APP_ID"] = creds["app_id"]
    os.environ["FEISHU_APP_SECRET"] = creds["app_secret"]
    return FeishuBitableAPI(creds["app_id"], creds["app_secret"])


def req(api: FeishuBitableAPI, path: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return api._request(path, method=method, payload=payload)


def table_by_name(api: FeishuBitableAPI, app_token: str, table_name: str) -> dict[str, Any] | None:
    return next((table for table in api.list_tables(app_token) if str(table.get("name") or "").strip() == table_name), None)


def list_fields(api: FeishuBitableAPI, app_token: str, table_id: str) -> list[dict[str, Any]]:
    return api.list_fields(app_token, table_id)


def list_records(api: FeishuBitableAPI, app_token: str, table_id: str) -> list[dict[str, Any]]:
    return api.list_records(app_token, table_id)


def field_name(field: dict[str, Any]) -> str:
    return str(field.get("field_name") or field.get("name") or "").strip()


def field_type(field: dict[str, Any]) -> int:
    try:
        return int(field.get("type") or 0)
    except (TypeError, ValueError):
        return 0


def field_options(field: dict[str, Any]) -> list[str]:
    property_value = field.get("property") or {}
    options = property_value.get("options") or []
    return [str(item.get("name") or "").strip() for item in options if str(item.get("name") or "").strip()]


def merge_options(current: list[str], desired: list[str]) -> list[str]:
    merged = [item for item in current if item]
    for item in desired:
        if item and item not in merged:
            merged.append(item)
    return merged


def field(field_name_value: str, field_type_value: str, *, options: list[str] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": field_name_value, "type": field_type_value}
    if options:
        payload["options"] = options
    return payload


def text(name: str) -> dict[str, Any]:
    return field(name, TEXT_FIELD)


def number(name: str) -> dict[str, Any]:
    return field(name, NUMBER_FIELD)


def single_select(name: str, options: list[str]) -> dict[str, Any]:
    return field(name, SINGLE_SELECT_FIELD, options=options)


def multi_select(name: str, options: list[str]) -> dict[str, Any]:
    return field(name, MULTI_SELECT_FIELD, options=options)


def datetime_field(name: str) -> dict[str, Any]:
    return field(name, DATETIME_FIELD)


def feishu_payload(schema_field: dict[str, Any]) -> dict[str, Any]:
    return schema_field_to_feishu_field(schema_field)


def desired_feishu_fields(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [feishu_payload(item) for item in fields]


def ensure_table(
    api: FeishuBitableAPI,
    app_token: str,
    *,
    table_name: str,
    primary_field: str,
    fields: list[dict[str, Any]],
    apply: bool,
    legacy_name: str | None = None,
) -> dict[str, Any]:
    current = table_by_name(api, app_token, table_name)
    created_table = False
    if current is None and legacy_name:
        current = table_by_name(api, app_token, legacy_name)

    if current is None:
        if not apply:
            return {
                "table_name": table_name,
                "table_id": "",
                "created": False,
                "field_count": len(fields),
                "status": "planned_create",
                "renamed_from": legacy_name or "",
            }
        created = api.create_table(app_token, table_name, desired_feishu_fields(fields))
        table_id = str(created.get("table_id") or "").strip()
        if not table_id:
            raise RuntimeError(f"failed to create table {table_name}")
        current = {"table_id": table_id, "name": table_name}
        created_table = True

    table_id = str(current.get("table_id") or "").strip()
    if not table_id:
        raise RuntimeError(f"table {table_name} missing table_id")

    current_name = str(current.get("name") or "").strip()
    if current_name != table_name and apply:
        req(api, f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}", method="PATCH", payload={"name": table_name})

    current_fields = list_fields(api, app_token, table_id)
    primary = next((item for item in current_fields if item.get("is_primary")), None)
    if primary and field_name(primary) != primary_field and apply:
        req(
            api,
            f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{primary['field_id']}",
            method="PUT",
            payload={"field_name": primary_field, "type": field_type(primary)},
        )
        current_fields = list_fields(api, app_token, table_id)

    fields_by_name = {field_name(item): item for item in current_fields}
    desired = desired_feishu_fields(fields)
    created_fields: list[str] = []
    updated_fields: list[str] = []

    for desired_schema_field, desired_payload in zip(fields, desired, strict=True):
        name = str(desired_schema_field["name"])
        existing = fields_by_name.get(name)
        if existing is None:
            if apply:
                req(
                    api,
                    f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
                    method="POST",
                    payload=desired_payload,
                )
                created_fields.append(name)
            continue

        if field_type(existing) != int(desired_payload["type"]):
            if apply:
                req(
                    api,
                    f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{existing['field_id']}",
                    method="PUT",
                    payload=desired_payload,
                )
                updated_fields.append(name)
            continue

        if desired_payload["type"] in {3, 4}:
            desired_options = [item["name"] for item in desired_payload.get("property", {}).get("options", [])]
            current_options = field_options(existing)
            merged = merge_options(current_options, desired_options)
            if merged != current_options and apply:
                req(
                    api,
                    f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{existing['field_id']}",
                    method="PUT",
                    payload={
                        "field_name": name,
                        "type": desired_payload["type"],
                        "property": {"options": [{"name": option} for option in merged]},
                    },
                )
                updated_fields.append(name)

    return {
        "table_name": table_name,
        "table_id": table_id,
        "created": created_table,
        "field_count": len(list_fields(api, app_token, table_id)) if apply else len(fields),
        "status": "verified" if apply else "planned_verify",
        "created_fields": created_fields,
        "updated_fields": updated_fields,
        "renamed_from": legacy_name or "",
        "primary_field": primary_field,
    }


def normalize_rows(schema_fields: list[dict[str, Any]], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    schema = {"fields": schema_fields}
    return [normalize_record(schema, row) for row in rows]


def existing_index(records: list[dict[str, Any]], primary_field: str) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for record in records:
        fields = record.get("fields") or {}
        key = str(fields.get(primary_field) or "").strip()
        if key:
            index[key] = record
    return index


def delete_records(api: FeishuBitableAPI, app_token: str, table_id: str, record_ids: list[str]) -> int:
    deleted = 0
    for record_id in record_ids:
        req(api, f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}", method="DELETE")
        deleted += 1
    return deleted


def upsert_rows(
    api: FeishuBitableAPI,
    app_token: str,
    *,
    table_id: str,
    primary_field: str,
    schema_fields: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    apply: bool,
) -> dict[str, Any]:
    normalized_rows = normalize_rows(schema_fields, rows)
    existing_records = list_records(api, app_token, table_id)
    blank_record_ids = [
        str(record.get("record_id") or "").strip()
        for record in existing_records
        if not str((record.get("fields") or {}).get(primary_field) or "").strip()
        and str(record.get("record_id") or "").strip()
    ]
    if apply and blank_record_ids:
        delete_records(api, app_token, table_id, blank_record_ids)
        existing_records = [record for record in existing_records if str(record.get("record_id") or "").strip() not in set(blank_record_ids)]

    existing = existing_index(existing_records, primary_field)
    create_payload: list[dict[str, Any]] = []
    update_payload: list[dict[str, Any]] = []

    for row in normalized_rows:
        key = str(row.get(primary_field) or "").strip()
        if not key:
            raise RuntimeError(f"missing primary field {primary_field} in payload row")
        current = existing.get(key)
        if current:
            update_payload.append({"record_id": current["record_id"], "fields": row})
        else:
            create_payload.append(row)

    if apply:
        if create_payload:
            api.batch_create_records(app_token, table_id, create_payload)
        if update_payload:
            api.batch_update_records(app_token, table_id, update_payload)

    return {
        "primary_field": primary_field,
        "row_count": len(normalized_rows),
        "would_create": len(create_payload),
        "would_update": len(update_payload),
        "blank_records_deleted": len(blank_record_ids) if apply else 0,
        "status": "applied" if apply else "preview_ready",
    }


def build_manifest(now_value: datetime) -> dict[str, Any]:
    distill_terms = build_distill_rows(now_value)
    content_rows = build_content_rows(now_value)
    publish_rows = build_publish_rows(now_value)
    monitor_rows = build_monitor_rows(now_value)
    snapshot_rows = build_snapshot_rows(now_value)

    tables = [
        {
            "table_name": "T01_蒸馏词库",
            "legacy_name": "数据表",
            "primary_field": "ID",
            "fields": [
                text("ID"),
                text("主关键词"),
                text("拓展问题"),
                single_select("所属产品线", ["YSE", "CEO密训营/私董会", "八万四千", "智能少年", "原力龙虾"]),
                single_select("优先级", ["P0", "P1", "P2"]),
                single_select("当前收录状态", ["未收录", "待验证", "部分收录", "已收录"]),
                multi_select("已收录平台", ["DeepSeek", "豆包", "文心一言", "通义千问", "腾讯元宝"]),
            ],
            "records": distill_terms,
        },
        {
            "table_name": "T02_品牌知识库",
            "primary_field": "产品线",
            "fields": [
                text("产品线"),
                text("品牌描述"),
                text("差异化卖点"),
                text("数据案例"),
                text("关键词"),
            ],
            "records": [
                {
                    "产品线": "YSE",
                    "品牌描述": (
                        "YSE原力战略引擎是原力OS体系下的AI原生战略咨询与GEO试点。"
                        "它不是泛内容投放，而是用蒸馏词、品牌知识库、内容生成、发布、监测形成闭环，"
                        "让AI搜索回答里优先出现原力与YSE。"
                    ),
                    "差异化卖点": (
                        "1. 品牌可见性 + 可信证据 + AI答案占位一体化。\n"
                        "2. 依托飞书 + Codex + Claude，不另起技术栈。\n"
                        "3. 先做YSE单点试点，再复制到其他产品线。\n"
                        "4. 回旋镖局等重案例可直接沉淀成证据包。"
                    ),
                    "数据案例": (
                        "回旋镖局案例：2025年GMV 1,811万、订单8,479单、首年经营利润107万。\n"
                        "供给侧：23名外部鉴定师日均46件，6000万目标需要鉴定产能扩容7.2倍。\n"
                        "结论：信任基础设施和证据链是AI搜索可见性的底层资产。"
                    ),
                    "关键词": "GEO；AI搜索优化；原力OS；飞书；Codex；Claude；品牌可见性；证据链；回旋镖局；万里茶道",
                }
            ],
        },
        {
            "table_name": "T03_内容库",
            "primary_field": "内容ID",
            "fields": [
                text("内容ID"),
                text("标题"),
                text("正文"),
                text("蒸馏词ID"),
                single_select("内容类型", ["行业科普", "产品对比", "案例分析", "问答文", "方法论输出", "试点复盘"]),
                datetime_field("创建时间"),
            ],
            "records": content_rows,
        },
        {
            "table_name": "T04_发布记录",
            "primary_field": "发布ID",
            "fields": [
                text("发布ID"),
                text("内容ID"),
                single_select("发布平台", ["公众号", "知乎", "百家号", "头条号", "企鹅号", "搜狐", "网易", "小红书", "抖音", "B站", "CSDN", "简书"]),
                datetime_field("发布时间"),
                single_select("状态", ["待审核", "待发布", "已发布", "需重写", "已下线"]),
                text("文章URL"),
            ],
            "records": publish_rows,
        },
        {
            "table_name": "T05_收录监测",
            "primary_field": "查询ID",
            "fields": [
                text("查询ID"),
                text("蒸馏词ID"),
                single_select("AI平台", ["DeepSeek", "豆包", "文心一言", "通义千问", "腾讯元宝"]),
                datetime_field("查询时间"),
                single_select("是否收录", ["是", "否"]),
                number("排名"),
                text("竞品"),
            ],
            "records": monitor_rows,
        },
        {
            "table_name": "T06_运营快照",
            "primary_field": "快照ID",
            "fields": [
                text("快照ID"),
                datetime_field("日期"),
                number("总蒸馏词"),
                number("已收录数"),
                number("收录率"),
                text("各平台分布"),
            ],
            "records": snapshot_rows,
        },
    ]

    return {
        "task_id": TASK_ID,
        "project_name": BASE_TITLE,
        "base_link": BASE_LINK,
        "trial_scope": TRIAL_SCOPE,
        "generated_at": iso(now_value),
        "source_materials": [
            str(DOCS_ROOT / "会议纪要/【原力战略】/原力GEO/原力GEO系统_全链路搭建路线图_V1.docx"),
            str(DOCS_ROOT / "会议纪要/【水月旧物造】/杨老师-回旋镖局-交付物/回旋镖局_战略诊断报告_V1 (1).docx"),
            str(DOCS_ROOT / "会议纪要/【水月旧物造】/杨老师-回旋镖局-交付物/供给侧瓶颈深度分析.docx"),
            str(DOCS_ROOT / "会议纪要/【水月旧物造】/杨老师-回旋镖局-交付物/这份报告的核心逻辑.docx"),
            str(DOCS_ROOT / "会议纪要/【水月旧物造】/杨老师-回旋镖局-交付物/全球标杆对标分析：七维度战略框架.docx"),
        ],
        "tables": tables,
    }


def build_distill_rows(now_value: datetime) -> list[dict[str, Any]]:
    specs = [
        ("原力GEO是什么", "原力GEO是什么意思；GEO和SEO有什么区别；怎么让AI把品牌变成答案", "P0"),
        ("YSE原力战略引擎是什么", "YSE是什么；YSE适合什么企业；YSE如何服务AI搜索优化", "P0"),
        ("飞书+Codex+Claude怎么搭GEO", "飞书怎么做底座；Codex负责什么；Claude负责什么", "P0"),
        ("如何建立品牌知识库", "品牌知识库要放什么；如何把案例变成证据；品牌知识库怎么维护", "P0"),
        ("如何让AI回答里出现品牌", "怎么让原力出现在AI回答；如何占位答案；品牌可见性怎么做", "P0"),
        ("GEO和SEO有什么区别", "GEO和SEO的核心差异；AI搜索和网页搜索的区别；答案占位是什么意思", "P0"),
        ("什么是蒸馏词", "蒸馏词怎么定义；问题词怎么筛选；为什么要用自然语言问题", "P0"),
        ("AI搜索优化怎么做", "AI搜索优化步骤；内容怎么设计；监测怎么做", "P0"),
        ("AI战略咨询公司推荐", "企业问AI战略咨询时会推荐谁；原力如何进入推荐；YSE如何被识别", "P0"),
        ("如何把案例转成知识资产", "案例怎么沉淀；如何抽出证据链；怎么供AI引用", "P0"),
        ("AI原生战略咨询怎么选", "什么是AI原生咨询；如何选择适合的咨询公司；YSE有什么特点", "P1"),
        ("战略诊断报告怎么写", "报告结构怎么写；诊断结论怎么提炼；如何形成可执行建议", "P1"),
        ("企业如何做AI原生转型", "AI原生转型怎么分阶段；如何和原力OS协同；先做什么后做什么", "P1"),
        ("原力OS两头怼工作法是什么", "两头怼是什么；前台和后台怎么协作；GEO怎么嵌进去", "P1"),
        ("如何做周度复盘看板", "复盘要看哪些指标；怎么跟踪收录；如何调整下周动作", "P1"),
        ("如何判断GEO是否有效", "收录率怎么定义；排名怎么看；怎么证明品牌在进步", "P1"),
        ("品牌可见性如何量化", "可见性怎么衡量；要看哪些平台；如何看品牌出现频次", "P1"),
        ("如何把业务问题变成蒸馏词", "业务问题怎么问成自然语言；如何从客户问法抽取词；如何定优先级", "P1"),
        ("内容不是软文应该怎么写", "GEO内容和软文的区别；高质量内容怎么写；如何让AI可提取", "P1"),
        ("AI更喜欢什么样的文章", "AI喜欢结构化吗；AI更看重证据吗；标题和正文怎么写", "P1"),
        ("为什么结构化内容更容易被收录", "标题层级怎么做；表格和FAQ有什么用；结构化如何提升可读性", "P1"),
        ("权威数据为什么会影响AI推荐", "数据证据怎么放；引用什么数字最有用；如何避免空话", "P1"),
        ("如何让品牌案例更像证据", "案例要讲什么；数字怎么写；如何形成可引用证据", "P1"),
        ("GEO内容类型有哪些", "科普文、问答文、案例文、方法论文怎么分；不同类型怎么排期", "P1"),
        ("试点复盘怎么做", "试点复盘看什么；如何判断要继续还是扩写；如何进入下一轮", "P1"),
        ("品牌知识库怎么搭", "知识库字段怎么定；内容怎么维护；证据包怎么归档", "P1"),
        ("如何把会议纪要变成知识资产", "会议纪要如何提炼；怎么抽问法；怎么做成知识库条目", "P1"),
        ("原力OS适合什么企业", "哪些企业适合原力OS；什么样的团队需要GEO；什么场景更有效", "P1"),
        ("原力GEO试点为什么先做YSE", "为什么先做YSE；为什么不同时铺开；如何利用现有素材", "P1"),
        ("原力OS为什么要做GEO", "GEO和原力OS的关系；为什么要做AI答案占位；与现有体系如何衔接", "P1"),
        ("回旋镖局是什么", "回旋镖局的业务本质；C2B2C怎么理解；为什么适合作为案例资产", "P2"),
        ("回旋镖局为什么能盈利", "首年盈利来自哪里；单位经济模型怎样；盈利模型能否复制", "P2"),
        ("文化艺术品C2B2C是什么意思", "C2B2C如何运作；信任中间商是什么；跟普通电商有什么区别", "P2"),
        ("什么是保真保价保交付", "三个价值主张如何落地；如何变成品牌信任点；如何写进知识库", "P2"),
        ("鉴定产能为什么是硬天花板", "为什么产能受限；如何从人力转向系统；如何影响增长", "P2"),
        ("AI预筛+专家复核怎么做", "AI预筛解决什么；专家复核解决什么；如何形成三层信任体系", "P2"),
        ("前置筛选为什么能减少白跑", "为什么会白跑；如何在线预审；如何降低无效寄售", "P2"),
        ("拍卖和一口价有什么区别", "拍卖的优势是什么；一口价的边界是什么；如何做混合模式", "P2"),
        ("回旋镖局的差异化壁垒是什么", "杨老师IP、鉴定能力、交易机制如何组合；壁垒如何形成", "P2"),
        ("万里茶道IP怎么带动交易", "IP如何变内容；内容如何变专场；如何带动交易闭环", "P2"),
        ("文化艺术品交易平台推荐", "AI为什么会推荐某平台；信任与效率如何平衡；原力可借鉴什么", "P2"),
        ("文化艺术品鉴定平台推荐", "鉴定平台怎么选；谁具备信任资产；AI会怎么理解专业性", "P2"),
        ("非标品交易为什么依赖信任基础设施", "非标品的风险是什么；为什么信任是前提；怎样规模化", "P2"),
        ("信任基础设施如何规模化", "人治如何变成机制；数据如何沉淀；系统如何放大信任", "P2"),
        ("卖家寄售为什么会流失", "为什么会白跑；预期差怎么解决；如何提升寄售体验", "P2"),
        ("货源结构单一怎么办", "如何做品类平衡；非珠宝品类如何提升；如何找新供给", "P2"),
        ("滞销堆积怎么治理", "滞销为什么出现；如何提前治理；怎样减少库存压力", "P2"),
        ("6000万GMV目标怎么拆解", "增长目标怎么拆；产能、货盘、复购如何联动；如何看可行性", "P2"),
        ("2026年回旋镖局增长路径是什么", "2026增长路径如何设计；哪些杠杆最关键；如何从1到10", "P2"),
        ("千匠守艺出海计划能带来什么", "海外叙事怎么和国内交易联动；如何形成双飞轮；如何反哺YSE", "P2"),
    ]

    rows: list[dict[str, Any]] = []
    for index, (main_keyword, extended_questions, priority) in enumerate(specs, start=1):
        rows.append(
            {
                "ID": f"YSE-D{index:02d}",
                "主关键词": main_keyword,
                "拓展问题": extended_questions,
                "所属产品线": "YSE",
                "优先级": priority,
                "当前收录状态": "未收录",
                "已收录平台": [],
            }
        )
    return rows


def build_content_rows(now_value: datetime) -> list[dict[str, Any]]:
    specs = [
        (
            "YSE-C01",
            "从SEO到GEO：为什么AI时代品牌要先占答案",
            "YSE-D01",
            "行业科普",
            (
                "1. 先解释SEO和GEO的差异。\n"
                "2. 再说明AI搜索时代，品牌必须先占答案。\n"
                "3. 用YSE试点说明闭环：蒸馏词→知识库→内容→发布→监测。\n"
                "4. 结尾给出试点顺序与下一步动作。"
            ),
            0,
        ),
        (
            "YSE-C02",
            "YSE原力战略引擎是什么？用飞书+Codex+Claude搭出AI原生战略系统",
            "YSE-D02",
            "方法论输出",
            (
                "1. 解释YSE是什么，以及它在原力OS中的位置。\n"
                "2. 展示飞书、Codex、Claude各自承担的角色。\n"
                "3. 说明为什么先做YSE单点试点。\n"
                "4. 给出复制到其他产品线的路径。"
            ),
            12,
        ),
        (
            "YSE-C03",
            "回旋镖局案例告诉我们：信任基础设施才是非标品的护城河",
            "YSE-D31",
            "案例分析",
            (
                "1. 讲回旋镖局的商业本质和信任基础设施。\n"
                "2. 用盈利、GMV、鉴定产能等数据说明约束。\n"
                "3. 抽出可复用的证据资产。\n"
                "4. 说明为什么这类案例适合作为品牌知识库。"
            ),
            24,
        ),
        (
            "YSE-C04",
            "AI战略咨询公司推荐时，AI为什么应该提到原力OS",
            "YSE-D09",
            "问答文",
            (
                "1. 还原用户会怎样问AI战略咨询推荐。\n"
                "2. 说明AI为什么应该把原力放进推荐名单。\n"
                "3. 列出需要的证据链和案例。\n"
                "4. 给出可直接复用的回答结构模板。"
            ),
            36,
        ),
        (
            "YSE-C05",
            "如何建立品牌知识库：从案例包到证据链",
            "YSE-D04",
            "方法论输出",
            (
                "1. 说明品牌知识库不是资料堆。\n"
                "2. 给出品牌描述、差异化卖点、数据案例、关键词四块。\n"
                "3. 用YSE和回旋镖局做示例。\n"
                "4. 给出后续维护方式。"
            ),
            48,
        ),
        (
            "YSE-C06",
            "GEO内容不是软文：一篇能被AI提取的文章长什么样",
            "YSE-D06",
            "行业科普",
            (
                "1. 解释GEO内容和普通软文的区别。\n"
                "2. 说明什么样的结构更容易被AI提取。\n"
                "3. 展示如何嵌入品牌独有词和数字证据。\n"
                "4. 用问答式收束，让答案更清晰。"
            ),
            60,
        ),
        (
            "YSE-C07",
            "品牌可见性怎么做周度复盘？50个蒸馏词的第一性原理",
            "YSE-D15",
            "试点复盘",
            (
                "1. 蒸馏词如何定义以及为什么要分P0/P1/P2。\n"
                "2. 周度复盘要看哪些指标。\n"
                "3. 如何判断某个词继续、停掉还是扩写。\n"
                "4. 如何把结果回写到下一周。"
            ),
            72,
        ),
        (
            "YSE-C08",
            "文化艺术品交易平台的信任难题，为什么要靠AI预筛",
            "YSE-D36",
            "案例分析",
            (
                "1. 回旋镖局信任难题与供给侧约束。\n"
                "2. 讲AI预筛+专家复核的三层信任体系。\n"
                "3. 说明它对YSE内容资产的启发。\n"
                "4. 结尾把案例转成可引用证据。"
            ),
            84,
        ),
        (
            "YSE-C09",
            "万里茶道IP如何变成内容和交易闭环",
            "YSE-D40",
            "案例分析",
            (
                "1. 解释万里茶道IP与平台品类的匹配点。\n"
                "2. 展示内容如何变成主题专场和交易入口。\n"
                "3. 说明IP如何成为AI可引用的证据。\n"
                "4. 给出YSE可复用的表达方式。"
            ),
            96,
        ),
        (
            "YSE-C10",
            "原力GEO Phase 1试点复盘模板：从内容到收录的闭环表",
            "YSE-D49",
            "试点复盘",
            (
                "1. 试点复盘看哪些环节：词、内容、发布、监测、回写。\n"
                "2. 如何判断收录有无推进。\n"
                "3. 何时应该扩词、补文或改写。\n"
                "4. 下一轮如何扩到其他产品线。"
            ),
            108,
        ),
    ]

    rows: list[dict[str, Any]] = []
    for content_id, title, distill_id, content_type, outline, minute_offset in specs:
        rows.append(
            {
                "内容ID": content_id,
                "标题": title,
                "正文": outline,
                "蒸馏词ID": distill_id,
                "内容类型": content_type,
                "创建时间": iso(now_value + timedelta(minutes=minute_offset)),
            }
        )
    return rows


def build_publish_rows(now_value: datetime) -> list[dict[str, Any]]:
    specs = [
        ("YSE-P01-ZHIHU", "YSE-C01", "知乎"),
        ("YSE-P02-GZH", "YSE-C02", "公众号"),
        ("YSE-P03-BAIJIA", "YSE-C03", "百家号"),
    ]
    rows: list[dict[str, Any]] = []
    for publish_id, content_id, platform in specs:
        rows.append(
            {
                "发布ID": publish_id,
                "内容ID": content_id,
                "发布平台": platform,
                "状态": "待审核",
            }
        )
    return rows


def build_monitor_rows(now_value: datetime) -> list[dict[str, Any]]:
    specs = [
        ("YSE-Q01-DS", "YSE-D09", "DeepSeek"),
        ("YSE-Q01-DB", "YSE-D09", "豆包"),
        ("YSE-Q01-WXYJ", "YSE-D09", "文心一言"),
        ("YSE-Q01-TYQW", "YSE-D09", "通义千问"),
        ("YSE-Q01-TXYB", "YSE-D09", "腾讯元宝"),
    ]
    rows: list[dict[str, Any]] = []
    for query_id, distill_id, platform in specs:
        rows.append(
            {
                "查询ID": query_id,
                "蒸馏词ID": distill_id,
                "AI平台": platform,
                "查询时间": iso(now_value),
                "是否收录": "否",
                "竞品": "暂无",
            }
        )
    return rows


def build_snapshot_rows(now_value: datetime) -> list[dict[str, Any]]:
    return [
        {
            "快照ID": "YSE-SN-20260329",
            "日期": iso(now_value),
            "总蒸馏词": 50,
            "已收录数": 0,
            "收录率": 0,
            "各平台分布": "DeepSeek 1次查询/0收录；豆包 1次查询/0收录；文心一言 1次查询/0收录；通义千问 1次查询/0收录；腾讯元宝 1次查询/0收录",
        }
    ]


def apply_manifest(api: FeishuBitableAPI, app_token: str, manifest: dict[str, Any], *, apply: bool) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for table_spec in manifest["tables"]:
        table_result = ensure_table(
            api,
            app_token,
            table_name=table_spec["table_name"],
            primary_field=table_spec["primary_field"],
            fields=table_spec["fields"],
            apply=apply,
            legacy_name=table_spec.get("legacy_name"),
        )
        table_id = str(table_result.get("table_id") or "").strip()
        record_result: dict[str, Any] | None = None
        if table_id:
            record_result = upsert_rows(
                api,
                app_token,
                table_id=table_id,
                primary_field=table_spec["primary_field"],
                schema_fields=table_spec["fields"],
                rows=table_spec["records"],
                apply=apply,
            )
        results.append(
            {
                "table_name": table_spec["table_name"],
                "table_id": table_id,
                "primary_field": table_spec["primary_field"],
                "table_result": table_result,
                "record_result": record_result,
            }
        )
    return {
        "mode": "apply" if apply else "dry-run",
        "status": "applied" if apply else "preview_ready",
        "tables": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and seed the Phase 1 GEO Feishu base.")
    parser.add_argument("--link", default=BASE_LINK)
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    apply_changes = bool(args.apply)
    run_now = now_local()
    run_dir = ARTIFACT_ROOT / f"run-{run_now.strftime('%Y%m%d-%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = build_manifest(run_now)
    manifest_path = run_dir / "geo_phase1_manifest.json"
    result_path = run_dir / "geo_phase1_result.json"
    write_json(manifest_path, manifest)

    api = load_client(args.account_id)
    app_token = api.resolve_app_token(args.link)

    payload = {
        "task_id": TASK_ID,
        "base_link": args.link,
        "app_token": app_token,
        "project_name": BASE_TITLE,
        "trial_scope": TRIAL_SCOPE,
        "generated_at": iso(run_now),
        "apply": apply_changes,
        "manifest_path": str(manifest_path),
    }
    payload.update(apply_manifest(api, app_token, manifest, apply=apply_changes))
    payload["result_path"] = str(result_path)
    write_json(result_path, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
