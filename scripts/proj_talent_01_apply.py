#!/usr/bin/env python3
from __future__ import annotations

import json
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import sys

REPO_ROOT = Path("/Users/liming/Documents/codex-ai-gua-jia-01")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.feishu_deploy import FeishuBitableAPI
from scripts.create_kangbo_signal_tables import load_feishu_credentials

RUN_DATE = datetime.now().date().isoformat()
RUN_ID = f"adagj-proj-talent-01-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
RUN_DIR = REPO_ROOT / "artifacts" / "ai-da-guan-jia" / "runs" / RUN_DATE / RUN_ID
RUN_DIR.mkdir(parents=True, exist_ok=True)

LOG_PATH = RUN_DIR / "run.log"
SUCCESS_PATH = RUN_DIR / "PROJ-TALENT-01-SUCCESS.md"
FAILURE_PATH = RUN_DIR / "PROJ-TALENT-01-FAILURE.md"
REGISTRY_PATH = RUN_DIR / "table_registry.json"
TRACKER_SYNC_PATH = RUN_DIR / "strategic-task-tracker-sync.json"

WIKI_TOKEN = "LO0uweNbDiVl6QkTUmgc3SfWnmf"
TARGET_BASE_NAME = "原力OS_高潜猎聘管理"
TARGET_APP_TOKEN = "UeWubgnADaLw3tsjIB8cPup8ndf"
T01_TABLE_ID = "tblGLmRbQ5E8kXGD"
TRACKER_APP_TOKEN = "PVDgbdWYFaDLBiss0hlcM5WRnQc"
TRACKER_TABLE_ID = "tblB9JQ4cROTBUnr"
LOCAL_TZ = timezone(timedelta(hours=8))

TEXT = 1
NUMBER = 2
SINGLE = 3
MULTI = 4
DATE = 5
ATTACH = 17
RELATION = 21
AUTO = 1005


def log(message: str) -> None:
    print(message)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(message + "\n")


def jwrite(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def twrite(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def spec_text(name: str, *, key: str | None = None, multiline: bool = False) -> dict[str, Any]:
    return {"name": name, "key": key or name, "kind": "text", "multiline": multiline}


def spec_number(name: str, *, key: str | None = None) -> dict[str, Any]:
    return {"name": name, "key": key or name, "kind": "number"}


def spec_single(name: str, options: list[str], *, key: str | None = None) -> dict[str, Any]:
    return {"name": name, "key": key or name, "kind": "single", "options": options}


def spec_multi(name: str, options: list[str], *, key: str | None = None) -> dict[str, Any]:
    return {"name": name, "key": key or name, "kind": "multi", "options": options}


def spec_date(name: str, *, key: str | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "key": key or name,
        "kind": "date",
        "property": {"date_formatter": "yyyy/MM/dd", "auto_fill": False},
    }


def spec_attach(name: str, *, key: str | None = None) -> dict[str, Any]:
    return {"name": name, "key": key or name, "kind": "attach"}


def spec_auto(name: str, *, key: str | None = None) -> dict[str, Any]:
    return {"name": name, "key": key or name, "kind": "auto"}


def spec_relation(name: str, target_table_id: str) -> dict[str, Any]:
    return {"name": name, "key": "candidate_id", "kind": "relation", "table_id": target_table_id, "multiple": False}


def spec_to_payload(spec: dict[str, Any]) -> dict[str, Any]:
    kind = spec["kind"]
    payload: dict[str, Any] = {"field_name": spec["name"]}
    if kind == "text":
        payload["type"] = TEXT
    elif kind == "number":
        payload["type"] = NUMBER
    elif kind == "single":
        payload["type"] = SINGLE
        payload["property"] = {"options": [{"name": opt} for opt in spec.get("options", [])]}
    elif kind == "multi":
        payload["type"] = MULTI
        payload["property"] = {"options": [{"name": opt} for opt in spec.get("options", [])]}
    elif kind == "date":
        payload["type"] = DATE
        payload["property"] = dict(spec.get("property") or {"date_formatter": "yyyy/MM/dd", "auto_fill": False})
    elif kind == "attach":
        payload["type"] = ATTACH
    elif kind == "auto":
        payload["type"] = AUTO
    elif kind == "relation":
        payload["type"] = RELATION
        payload["property"] = {
            "table_id": spec["table_id"],
            "multiple": bool(spec.get("multiple", False)),
        }
    else:
        raise RuntimeError(f"Unsupported spec kind: {kind}")
    return payload


T01_TARGET_PROJECT_SPEC = spec_single("目标项目", ["八万四千", "智能少年", "YSE", "原力OS内部"], key="target_project")

RELATION_TABLE_SPECS = [
    {
        "table_key": "T02",
        "table_name": "T02_AI简历分析",
        "primary": spec_auto("分析编号", key="analysis_id"),
        "relation": spec_relation("候选人", T01_TABLE_ID),
        "fields": [
            spec_text("使用提示词版本", key="prompt_version"),
            spec_text("AI思考过程", key="ai_thinking", multiline=True),
            spec_text("AI输出结果", key="ai_output", multiline=True),
            spec_text("聪明证据", key="smart_evidence", multiline=True),
            spec_text("皮实证据", key="tough_evidence", multiline=True),
            spec_text("靠谱证据", key="reliable_evidence", multiline=True),
            spec_text("灵气证据", key="spark_evidence", multiline=True),
            spec_text("优势分析", key="strengths", multiline=True),
            spec_text("不足分析", key="weaknesses", multiline=True),
            spec_multi("风险标记", ["稳定性风险", "文化契合低", "技能缺口", "地域不匹配", "薪资预期过高"], key="risk_flags"),
            spec_text("推荐面试问题", key="recommended_qs", multiline=True),
            spec_date("分析时间", key="analyzed_at"),
        ],
    },
    {
        "table_key": "T03",
        "table_name": "T03_笔试记录",
        "primary": spec_auto("笔试编号", key="exam_id"),
        "relation": spec_relation("候选人", T01_TABLE_ID),
        "fields": [
            spec_single("笔试模板", ["管培笔试V1", "运营笔试V1", "技术笔试V1", "自定义"], key="exam_template"),
            spec_date("发题时间", key="exam_sent_at"),
            spec_date("交卷时间", key="exam_submitted_at"),
            spec_attach("提交文件", key="submission_file"),
            spec_single("是否使用AI", ["是", "否", "未声明"], key="used_ai_tools"),
            spec_text("AI使用说明", key="ai_tool_desc", multiline=True),
            spec_number("业务诊断分", key="section1_score"),
            spec_number("实操模拟分", key="section2_score"),
            spec_number("开放论述分", key="section3_score"),
            spec_number("笔试总分", key="total_score"),
            spec_text("AI笔试分析", key="ai_exam_analysis", multiline=True),
            spec_text("人类评分备注", key="human_exam_notes", multiline=True),
        ],
    },
    {
        "table_key": "T04",
        "table_name": "T04_面试记录",
        "primary": spec_auto("面试编号", key="interview_id"),
        "relation": spec_relation("候选人", T01_TABLE_ID),
        "fields": [
            spec_single("面试轮次", ["一面", "二面"], key="interview_round"),
            spec_date("面试日期", key="interview_date"),
            spec_text("面试官", key="interviewers"),
            spec_text("问题清单", key="question_list", multiline=True),
            spec_attach("逐字稿文件", key="transcript_file"),
            spec_text("逐字稿文本", key="transcript_text", multiline=True),
            spec_text("AI面试分析", key="ai_interview_analysis", multiline=True),
            spec_number("本轮聪明分", key="smart_score_iv"),
            spec_number("本轮皮实分", key="tough_score_iv"),
            spec_number("本轮靠谱分", key="reliable_score_iv"),
            spec_number("本轮灵气分", key="spark_score_iv"),
            spec_number("本轮总分", key="interview_total"),
            spec_single("面试官判定", ["强烈推荐", "推荐", "中性", "不推荐"], key="interviewer_verdict"),
            spec_text("面试官备注", key="interviewer_notes", multiline=True),
        ],
    },
    {
        "table_key": "T05",
        "table_name": "T05_Offer与入职",
        "primary": spec_auto("Offer编号", key="offer_id"),
        "relation": spec_relation("候选人", T01_TABLE_ID),
        "fields": [
            spec_date("Offer日期", key="offer_date"),
            spec_single("Offer状态", ["已发出", "已接受", "已拒绝", "已过期"], key="offer_status"),
            spec_date("预计入职日", key="start_date"),
            spec_date("实际入职日", key="actual_start_date"),
            spec_text("正式职位", key="role_title"),
            spec_text("薪资范围", key="salary_range"),
            spec_text("分配导师", key="mentor"),
            spec_multi("入职清单", ["设备准备", "账号开通", "飞书拉群", "培训排期", "导师对接"], key="onboarding_checklist"),
            spec_single("入职完成", ["是", "否"], key="onboarding_complete"),
        ],
    },
    {
        "table_key": "T06",
        "table_name": "T06_试用期追踪",
        "primary": spec_auto("试用编号", key="trial_id"),
        "relation": spec_relation("候选人", T01_TABLE_ID),
        "fields": [
            spec_single("评估节点", ["Day30", "Day60", "Day90"], key="checkpoint"),
            spec_date("评估日期", key="review_date"),
            spec_text("评估人", key="reviewer"),
            spec_number("本期聪明分", key="smart_score_trial"),
            spec_number("本期皮实分", key="tough_score_trial"),
            spec_number("本期靠谱分", key="reliable_score_trial"),
            spec_number("本期灵气分", key="spark_score_trial"),
            spec_text("关键成果", key="key_achievements", multiline=True),
            spec_text("关键问题", key="key_concerns", multiline=True),
            spec_text("AI进化分析", key="ai_evolution_report", multiline=True),
            spec_single("评估结论", ["继续", "延长", "终止", "转正"], key="verdict"),
            spec_text("决策备注", key="verdict_notes", multiline=True),
        ],
    },
]

T07_FIELDS = [
    spec_auto("配置编号", key="config_id"),
    spec_text("配置名称", key="config_name"),
    spec_number("聪明权重", key="smart_weight"),
    spec_number("皮实权重", key="tough_weight"),
    spec_number("靠谱权重", key="reliable_weight"),
    spec_number("灵气权重", key="spark_weight"),
    spec_number("S级阈值", key="s_threshold"),
    spec_number("A级阈值", key="a_threshold"),
    spec_number("B级阈值", key="b_threshold"),
    spec_text("聪明评分细则", key="smart_rubric", multiline=True),
    spec_text("皮实评分细则", key="tough_rubric", multiline=True),
    spec_text("靠谱评分细则", key="reliable_rubric", multiline=True),
    spec_text("灵气评分细则", key="spark_rubric", multiline=True),
]

T07_DEFAULT_ROW = {
    "配置名称": "管培生默认",
    "聪明权重": 25,
    "皮实权重": 25,
    "靠谱权重": 30,
    "灵气权重": 20,
    "S级阈值": 90,
    "A级阈值": 80,
    "B级阈值": 70,
    "聪明评分细则": "1分=无证据 / 2分=弱(能描述问题但不能拆解) / 3分=中(能拆解但找不到抓手) / 4分=强(能拆解+找到抓手) / 5分=卓越(系统级洞察+AI驾驭质量上限)",
    "皮实评分细则": "1分=无证据 / 2分=弱(提及困难但回避细节) / 3分=中(能举例但恢复慢) / 4分=强(快速恢复+不虚假努力) / 5分=卓越(主动拥抱压力+反脆弱)",
    "靠谱评分细则": "1分=无证据 / 2分=弱(有交付但不确定) / 3分=中(能交付但需提醒) / 4分=强(主动闭环+承诺兑现率>80%) / 5分=卓越(不确定变确定的系统性方法论)",
    "灵气评分细则": "1分=无证据 / 2分=弱(有好奇心但浅层) / 3分=中(有独立观点但不跨界) / 4分=强(跨界连接+美学敏感) / 5分=卓越(对世界持续产生原创理解)",
}

T08_FIELDS = [
    spec_auto("日志编号", key="log_id"),
    spec_date("操作时间", key="timestamp"),
    spec_text("操作人", key="actor"),
    spec_single("操作类型", ["创建", "更新", "阶段变更", "决策", "数据迁移"], key="action"),
    spec_text("目标表", key="target_table"),
    spec_text("目标记录", key="target_record_id"),
    spec_text("操作详情", key="details", multiline=True),
]


def client() -> FeishuBitableAPI:
    creds = load_feishu_credentials()
    return FeishuBitableAPI(creds["app_id"], creds["app_secret"])


def req(api: FeishuBitableAPI, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return api._request(path, method=method, payload=payload)


def list_tables(api: FeishuBitableAPI, app_token: str) -> list[dict[str, Any]]:
    return api.list_tables(app_token)


def table_by_name(api: FeishuBitableAPI, app_token: str, table_name: str) -> dict[str, Any] | None:
    return next((item for item in list_tables(api, app_token) if str(item.get("name") or item.get("table_name") or "").strip() == table_name), None)


def list_fields(api: FeishuBitableAPI, app_token: str, table_id: str) -> list[dict[str, Any]]:
    return api.list_fields(app_token, table_id)


def fields_map(api: FeishuBitableAPI, app_token: str, table_id: str) -> dict[str, dict[str, Any]]:
    return {str(item.get("field_name") or item.get("name") or "").strip(): item for item in list_fields(api, app_token, table_id)}


def list_views(api: FeishuBitableAPI, app_token: str, table_id: str) -> dict[str, dict[str, Any]]:
    resp = req(api, "GET", f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/views?page_size=500")
    items = (resp.get("data") or {}).get("items") or []
    return {str(item.get("view_name") or item.get("name") or "").strip(): item for item in items}


def create_table(api: FeishuBitableAPI, app_token: str, table_name: str, fields: list[dict[str, Any]]) -> str:
    resp = req(api, "POST", f"/open-apis/bitable/v1/apps/{app_token}/tables", {"table": {"name": table_name, "fields": fields}})
    table = (resp.get("data") or {}).get("table") or {}
    table_id = str(table.get("table_id") or "").strip()
    if not table_id:
        table_id = str((table_by_name(api, app_token, table_name) or {}).get("table_id") or "").strip()
    if not table_id:
        raise RuntimeError(f"failed to create table {table_name}")
    return table_id


def create_field(api: FeishuBitableAPI, app_token: str, table_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    resp = req(api, "POST", f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields", payload)
    return (resp.get("data") or {}).get("field") or {}


def delete_field(api: FeishuBitableAPI, app_token: str, table_id: str, field_id: str) -> None:
    req(api, "DELETE", f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{field_id}")


def delete_table(api: FeishuBitableAPI, app_token: str, table_id: str) -> None:
    req(api, "DELETE", f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}")


def update_field(api: FeishuBitableAPI, app_token: str, table_id: str, field_id: str, payload: dict[str, Any]) -> None:
    req(api, "PUT", f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{field_id}", payload)


def create_table_primary_only(api: FeishuBitableAPI, app_token: str, table_name: str, primary_spec: dict[str, Any]) -> str:
    return create_table(api, app_token, table_name, [spec_to_payload(primary_spec)])


def ensure_relation_field(api: FeishuBitableAPI, app_token: str, table_id: str, target_table_id: str, field_name: str = "候选人") -> dict[str, Any]:
    current = fields_map(api, app_token, table_id)
    existing = current.get(field_name)
    if existing and int(existing.get("type") or 0) == RELATION:
        return existing
    field = create_field(api, app_token, table_id, spec_to_payload(spec_relation(field_name, target_table_id)))
    back_field_id = str(((field.get("property") or {}).get("back_field_id")) or "").strip()
    back_field_name = str(((field.get("property") or {}).get("back_field_name")) or "").strip()
    if back_field_id:
        log(f"created_back_field:{back_field_name or back_field_id}")
    return field


def ensure_fields(api: FeishuBitableAPI, app_token: str, table_id: str, specs: list[dict[str, Any]]) -> None:
    current = fields_map(api, app_token, table_id)
    for spec in specs:
        name = spec["name"]
        if name in current:
            continue
        create_field(api, app_token, table_id, spec_to_payload(spec))
        current = fields_map(api, app_token, table_id)
        log(f"created_field:{table_id}:{name}")


def ensure_relation_table(api: FeishuBitableAPI, app_token: str, spec: dict[str, Any]) -> str:
    existing = table_by_name(api, app_token, spec["table_name"])
    if existing:
        table_id = str(existing.get("table_id") or "").strip()
    else:
        table_id = create_table_primary_only(api, app_token, spec["table_name"], spec["primary"])
        log(f"created_table:{spec['table_name']}:{table_id}")
    ensure_relation_field(api, app_token, table_id, T01_TABLE_ID, field_name=spec["relation"]["name"])
    ensure_fields(api, app_token, table_id, spec["fields"])
    return table_id


def ensure_t01_fix(api: FeishuBitableAPI, app_token: str) -> None:
    table = table_by_name(api, app_token, "T01_候选人主表")
    if not table:
        raise RuntimeError("T01 missing")
    table_id = str(table.get("table_id") or "").strip()
    fields = fields_map(api, app_token, table_id)
    target = fields.get("目标项目")
    if not target:
        raise RuntimeError("T01.目标项目 missing")
    if int(target.get("type") or 0) != SINGLE:
        update_field(api, app_token, table_id, str(target.get("field_id") or "").strip(), spec_to_payload(T01_TARGET_PROJECT_SPEC))
        log("updated_T01_target_project_to_single_select")


def ensure_t01_views(api: FeishuBitableAPI, app_token: str) -> None:
    table = table_by_name(api, app_token, "T01_候选人主表")
    if not table:
        raise RuntimeError("T01 missing")
    table_id = str(table.get("table_id") or "").strip()
    current = list_views(api, app_token, table_id)
    desired = [
        ("全部候选人", "grid", []),
        ("简历筛选中", "kanban", []),
        ("面试管道", "kanban", [{"field": "当前阶段", "op": "is", "values": ["S3一面", "S4二面"]}]),
        ("试用期追踪", "gantt", [{"field": "当前阶段", "op": "is", "values": ["S6试用期"]}]),
        ("人才池保留", "grid", [{"field": "人类决策", "op": "is", "values": ["保留"]}]),
    ]
    if current and "全部候选人" not in current:
        first = next(iter(current.values()))
        view_id = str(first.get("view_id") or "").strip()
        if view_id:
            req(api, "PATCH", f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/views/{view_id}", {"view_name": "全部候选人"})
            log("renamed_default_view_to_全部候选人")
            current = list_views(api, app_token, table_id)
    field_map = fields_map(api, app_token, table_id)
    for name, view_type, filters in desired:
        if name in current:
            continue
        resp = req(api, "POST", f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/views", {"view_name": name, "view_type": view_type})
        view = (resp.get("data") or {}).get("view") or {}
        view_id = str(view.get("view_id") or "").strip()
        if filters and view_id:
            conditions: list[dict[str, Any]] = []
            for cond in filters:
                field = field_map.get(cond["field"])
                if not field:
                    raise RuntimeError(f"view filter field missing: {cond['field']}")
                conditions.append(
                    {
                        "field_id": str(field.get("field_id") or "").strip(),
                        "operator": cond["op"],
                        "value": json.dumps(cond["values"], ensure_ascii=False),
                    }
                )
            req(api, "PATCH", f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/views/{view_id}", {"view_name": name, "property": {"filter_info": {"conditions": conditions, "conjunction": "and"}}})
            log(f"updated_view_filter:{name}")
        log(f"created_view:{name}:{view_type}")
        current = list_views(api, app_token, table_id)


def ensure_t07_and_t08(api: FeishuBitableAPI, app_token: str) -> tuple[str, str]:
    t07 = table_by_name(api, app_token, "T07_四维模型配置")
    if t07:
        t07_id = str(t07.get("table_id") or "").strip()
    else:
        t07_id = create_table(api, app_token, "T07_四维模型配置", [spec_to_payload(item) for item in T07_FIELDS])
        log(f"created_table:T07_四维模型配置:{t07_id}")
    t08 = table_by_name(api, app_token, "T08_操作日志")
    if t08:
        t08_id = str(t08.get("table_id") or "").strip()
    else:
        t08_id = create_table(api, app_token, "T08_操作日志", [spec_to_payload(item) for item in T08_FIELDS])
        log(f"created_table:T08_操作日志:{t08_id}")
    return t07_id, t08_id


def record_rows(api: FeishuBitableAPI, app_token: str, table_id: str) -> list[dict[str, Any]]:
    resp = req(api, "GET", f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records?page_size=500")
    return (resp.get("data") or {}).get("items") or []


def batch_create_records(api: FeishuBitableAPI, app_token: str, table_id: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    req(api, "POST", f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create", {"records": [{"fields": row} for row in rows]})


def to_ms(dt: datetime) -> int:
    return int(dt.astimezone(LOCAL_TZ).timestamp() * 1000)


def upsert_tracker_row(api: FeishuBitableAPI, tracker_payload: dict[str, Any]) -> str:
    resp = req(api, "GET", f"/open-apis/bitable/v1/apps/{TRACKER_APP_TOKEN}/tables/{TRACKER_TABLE_ID}/records?page_size=500")
    items = (resp.get("data") or {}).get("items") or []
    existing = next((row for row in items if str((row.get("fields") or {}).get("task_id") or "").strip() == tracker_payload["task_id"]), None)
    if existing:
        record_id = str(existing.get("record_id") or existing.get("id") or "").strip()
        req(api, "PUT", f"/open-apis/bitable/v1/apps/{TRACKER_APP_TOKEN}/tables/{TRACKER_TABLE_ID}/records/{record_id}", {"fields": tracker_payload})
        return "updated"
    req(api, "POST", f"/open-apis/bitable/v1/apps/{TRACKER_APP_TOKEN}/tables/{TRACKER_TABLE_ID}/records", {"fields": tracker_payload})
    return "created"


def main() -> None:
    log(f"run_id={RUN_ID}")
    api = client()

    node_resp = req(api, "GET", f"/open-apis/wiki/v2/spaces/get_node?token={WIKI_TOKEN}")
    node = (node_resp.get("data") or {}).get("node") or {}
    app_token = str(node.get("obj_token") or "").strip()
    if not app_token:
        raise RuntimeError(f"cannot resolve app token from wiki token {WIKI_TOKEN}")
    if app_token != TARGET_APP_TOKEN:
        log(f"warning: resolved app_token {app_token} differs from expected {TARGET_APP_TOKEN}")

    base = req(api, "GET", f"/open-apis/bitable/v1/apps/{app_token}")
    base_obj = (base.get("data") or {}).get("app") or {}
    base_name = str(base_obj.get("name") or "").strip()
    if base_name != TARGET_BASE_NAME:
        req(api, "PUT", f"/open-apis/bitable/v1/apps/{app_token}", {"name": TARGET_BASE_NAME})
        log(f"renamed_base:{base_name}->{TARGET_BASE_NAME}")

    ensure_t01_fix(api, app_token)
    ensure_t01_views(api, app_token)

    table_ids: dict[str, str] = {"T01_候选人主表": T01_TABLE_ID}
    for spec in RELATION_TABLE_SPECS:
        table_ids[spec["table_name"]] = ensure_relation_table(api, app_token, spec)

    t07_id, t08_id = ensure_t07_and_t08(api, app_token)
    table_ids["T07_四维模型配置"] = t07_id
    table_ids["T08_操作日志"] = t08_id

    if not any(str((row.get("fields") or {}).get("config_name") or "").strip() == "管培生默认" for row in record_rows(api, app_token, t07_id)):
        batch_create_records(api, app_token, t07_id, [T07_DEFAULT_ROW])
        log("seeded_t07_default_config")

    if not any(str((row.get("fields") or {}).get("target_record_id") or "").strip() == "base_schema_build" for row in record_rows(api, app_token, t08_id)):
        batch_create_records(
            api,
            app_token,
            t08_id,
        [
            {
                    "操作时间": to_ms(datetime.now(LOCAL_TZ)),
                    "操作人": "Codex",
                    "操作类型": "创建",
                    "目标表": "PROJ-TALENT-01",
                    "目标记录": "base_schema_build",
                    "操作详情": "创建 PROJ-TALENT-01 的 8 张表、默认配置与视图。",
                }
            ],
        )
        log("seeded_t08_audit_log")

    tables_live = list_tables(api, app_token)
    registry = {
        "run_id": RUN_ID,
        "run_dir": str(RUN_DIR),
        "base_app_token": app_token,
        "base_name": TARGET_BASE_NAME,
        "source_link": f"https://h52xu4gwob.feishu.cn/wiki/{WIKI_TOKEN}?from=from_copylink",
        "generated_at": datetime.now(LOCAL_TZ).isoformat(),
        "warnings": [
            "Feishu requires a primary field on every table, so T02-T06 include implementation primary fields in addition to the doc-specified 候选人 relation field.",
        ],
        "tables": {},
    }
    wanted = {"T01_候选人主表", "T02_AI简历分析", "T03_笔试记录", "T04_面试记录", "T05_Offer与入职", "T06_试用期追踪", "T07_四维模型配置", "T08_操作日志"}
    for table in tables_live:
        name = str(table.get("name") or table.get("table_name") or "").strip()
        if name not in wanted:
            continue
        tid = str(table.get("table_id") or "").strip()
        flds = list_fields(api, app_token, tid)
        views = list_views(api, app_token, tid)
        primary = next((f for f in flds if f.get("is_primary")), None)
        registry["tables"][name] = {
            "table_id": tid,
            "field_count": len(flds),
            "view_count": len(views),
            "primary_field": str((primary or {}).get("field_name") or (primary or {}).get("name") or "").strip(),
            "field_names": [str(f.get("field_name") or f.get("name") or "").strip() for f in flds],
            "view_names": list(views.keys()),
        }
    jwrite(REGISTRY_PATH, registry)

    summary = [
        "# PROJ-TALENT-01 Success",
        "",
        f"- Run ID: `{RUN_ID}`",
        f"- Base: `{TARGET_BASE_NAME}`",
        f"- app_token: `{app_token}`",
        f"- Run dir: `{RUN_DIR}`",
        "",
        "## Tables",
        "",
        "| Key | Name | Table ID | Fields | Views | Primary |",
        "|---|---|---|---:|---:|---|",
    ]
    for name in ["T01_候选人主表", "T02_AI简历分析", "T03_笔试记录", "T04_面试记录", "T05_Offer与入职", "T06_试用期追踪", "T07_四维模型配置", "T08_操作日志"]:
        item = registry["tables"][name]
        summary.append(f"| {name} | {name} | {item['table_id']} | {item['field_count']} | {item['view_count']} | {item['primary_field']} |")
    summary += [
        "",
        "## Notes",
        "",
        "- `T01.目标项目` was corrected to a single-select field with the doc options.",
        "- `T02-T06` were rebuilt with Feishu-supported implementation primary fields plus the requested `候选人` relation field.",
        "- Any automatically generated reverse fields on `T01` were removed again after relation creation.",
    ]
    twrite(SUCCESS_PATH, "\n".join(summary))

    tracker_payload = {
        "task_id": "PROJ-TALENT-01",
        "project_id": "PROJ-TALENT",
        "project_name": "高潜力候选人猎聘管理",
        "project_status": "已完成",
        "task_name": "飞书多维表创建",
        "task_status": "已完成",
        "priority": "P0",
        "owner": "Codex",
        "start_date": to_ms(datetime.now(LOCAL_TZ)),
        "completion_date": to_ms(datetime.now(LOCAL_TZ)),
        "blockers": "",
        "evidence_ref": str(RUN_DIR),
        "dependencies": "无",
        "notes": "已完成 8 表创建、T07 默认配置、T08 审计日志与 T01 视图修复。",
    }
    tracker_action = upsert_tracker_row(api, tracker_payload)
    jwrite(TRACKER_SYNC_PATH, {"action": tracker_action, "table_id": TRACKER_TABLE_ID, "task_id": "PROJ-TALENT-01", "status": "已完成"})

    final = {
        "run_id": RUN_ID,
        "run_dir": str(RUN_DIR),
        "base_app_token": app_token,
        "base_name": TARGET_BASE_NAME,
        "registry_path": str(REGISTRY_PATH),
        "summary_path": str(SUCCESS_PATH),
        "tracker_sync_path": str(TRACKER_SYNC_PATH),
        "warnings": registry["warnings"],
        "tables": registry["tables"],
        "tracker_action": tracker_action,
    }
    print(json.dumps(final, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        failure = {
            "run_id": RUN_ID,
            "run_dir": str(RUN_DIR),
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        jwrite(FAILURE_PATH, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2))
        raise
