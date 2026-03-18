from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcp_server_feishu.feishu_client import FeishuClient


TARGET_APP_TOKEN = "IqZhbMJJxaq8D4sHOvkciaWFnid"
L1_EVENT_SIGNAL_TABLE_ID = "tbl6QgzUgcXq4HO5"
HOTSPOT_TABLE_NAME = "L1.5_热点深度剖析"
DRY_RUN_TABLE_ID = "dryrun_hotspot_table"
ARTIFACT_PATH = REPO_ROOT / "artifacts" / "r12-v2-hotspot" / "result.json"

TEXT_FIELD = 1
NUMBER_FIELD = 2
SINGLE_SELECT_FIELD = 3
DATE_FIELD = 5
CHECKBOX_FIELD = 7

HOTSPOT_FIELD_SPECS: list[dict[str, Any]] = [
    {"field_name": "analysis_id", "type": TEXT_FIELD},
    {"field_name": "source_event_id", "type": TEXT_FIELD},
    {"field_name": "analysis_date", "type": DATE_FIELD, "property": {"date_formatter": "yyyy-MM-dd", "auto_fill": False}},
    {"field_name": "headline", "type": TEXT_FIELD},
    {"field_name": "political_trigger", "type": TEXT_FIELD},
    {"field_name": "policy_deadlock", "type": TEXT_FIELD},
    {"field_name": "only_exit", "type": TEXT_FIELD},
    {"field_name": "adversary_incentive", "type": TEXT_FIELD},
    {
        "field_name": "adversary_time_preference",
        "type": SINGLE_SELECT_FIELD,
        "property": {"options": [{"name": "发动者"}, {"name": "对手"}, {"name": "均衡"}]},
    },
    {"field_name": "adversary_offramp", "type": TEXT_FIELD},
    {"field_name": "third_party_matrix", "type": TEXT_FIELD},
    {"field_name": "system_self_reinforcing", "type": CHECKBOX_FIELD},
    {"field_name": "dominant_narrative", "type": TEXT_FIELD},
    {"field_name": "counter_narrative", "type": TEXT_FIELD},
    {"field_name": "narrative_winner", "type": TEXT_FIELD},
    {"field_name": "escalation_probability", "type": NUMBER_FIELD},
    {"field_name": "duration_estimate", "type": TEXT_FIELD},
    {"field_name": "termination_conditions", "type": TEXT_FIELD},
    {"field_name": "base_case_scenario", "type": TEXT_FIELD},
    {"field_name": "investment_implication", "type": TEXT_FIELD},
]

L1_BACKLINK_FIELDS: list[dict[str, Any]] = [
    {"field_name": "deep_analysis_id", "type": TEXT_FIELD},
    {"field_name": "escalation_probability", "type": NUMBER_FIELD},
    {"field_name": "duration_estimate", "type": TEXT_FIELD},
]


def to_feishu_date(date_text: str) -> int:
    dt = datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


HOTSPOT_RECORD: dict[str, Any] = {
    "analysis_id": "HDA-202603-001",
    "source_event_id": "KBS-202602-001",
    "analysis_date": to_feishu_date("2026-03-17"),
    "headline": "从谎言到战争的必然路径：美伊冲突的博弈结构分析",
    "political_trigger": "2026年3月特朗普支持率跌至第二任期最低（昆尼皮亚克37%/福克斯43%），独立选民仅28%支持。IEEPA关税被最高法院6:3裁定违宪，需退还33万家企业1660亿美元。2月净失去9.2万工作岗位。DOGE裁员只制造失业未提升效率。面对8个月后中期选举，常规政策工具全部堵死。",
    "policy_deadlock": "减税需国会立法（众议院多数仅剩几票）；贸易谈判信誉被TACO模式（Trump Always Chickens Out）消耗殆尽；美联储不会在通胀压力下降息；36万亿国债意味着财政空间极其有限。所有常规经济/外交工具均不可用。",
    "only_exit": "军事行动：不需国会、立刻产生新闻效果、可重塑'被迫应战'叙事。委内瑞拉1月的'成功'（快速/干净/有经济收益/零美军伤亡）提供了可复制的模板认知——在特朗普框架里，伊朗只是放大版委内瑞拉。",
    "adversary_incentive": "IRGC收益持续性累积：霍尔木兹封锁使其成为全球石油流通守门人；影子舰队通过自有安全通道对华出口折价石油每天赚钱；油价越高→收入越高→对华议价能力越强→国际战略价值越大。轰炸反而强化国内合法性——每张被炸学校照片都是民族主义动员素材。",
    "adversary_time_preference": "对手",
    "adversary_offramp": "IRGC选择极其清晰：现在停=拿到好交易，再等几周=拿到更好的。每多一天，特朗普政治压力+1，IRGC要价基础+1。哈梅内伊死后，实际指挥官瓦希迪和傀儡最高领袖莫杰塔巴既无制动能力也无制动意愿。",
    "third_party_matrix": "俄罗斯：高油价每天多进几十亿美元+美军事资源被中东吸走+西方制裁体系被迫拆解→强化升级。中国：104天战略石油储备+煤化工替代+全球80%光伏产能，外交措辞从'敦促保持海峡开放'变为'呼吁停止军事冲突'（注意不是'开放海峡'）→被动受益。欧洲/日本/韩国：想停战但无杠杆→被动受损。海湾国家：想停战但被IRGC无人机攻击→被动卷入。格局：有杠杆的人没意愿，有意愿的人没杠杆。",
    "system_self_reinforcing": True,
    "dominant_narrative": "'伊朗封锁了海峡所以你的油价涨了，我们得打赢伊朗才能降油价。'3秒可理解。在加油站价格牌、手机推送、30秒电视片段这些渠道里，它就是全部的故事。",
    "counter_narrative": "'美国先斩首了伊朗最高领袖，这是始于2018年退出核协议的一系列升级的延续，伊朗封锁是报复。'需5分钟+历史背景知识。因果链中缺失环节（美国先动手）存在于长篇调查报道和外交政策期刊里，99%选民永远不会去读。",
    "narrative_winner": "3秒叙事。在注意力经济中，认知投入与受众规模成反比。一条推文可以定义一场战争的叙事，五千字政策分析改变不了任何人的投票。恐惧面前，正确一文不值。",
    "escalation_probability": 75,
    "duration_estimate": "数月至数年。约翰逊从'不派兵'到58000阵亡用了10年，每一步都是上一步的必然延伸。特朗普从'结束无尽的战争'到讨论地面入侵用时更短。对战争持续时间的系统性低估是结构性认知偏差——发动者永远低估对手意志和承受力。",
    "termination_conditions": "A.IRGC内部分裂（概率低，当前无制动器）B.美国国内反战规模化（需数月，但本土威胁叙事可持续压制）C.中俄主导多方调解（双方无动机）D.军事决定性胜利（概率极低，9000万人口+扎格罗斯山脉+意识形态韧性）E.宣布胜利撤退（这次不行，霍尔木兹封锁不会因美国撤退自动解除）",
    "base_case_scenario": "持续消耗战，霍尔木兹半封锁成为新常态，油价维持80-120美元区间，VIX长期高位运行25-40，全球经济进入1973型滞胀模式。",
    "investment_implication": "结构性状态切换而非事件冲击。核心判断：(1)Trump Put失效——战时下跌股市变成'敌人造成的损害'而非止损信号；(2)1973类比但更严重——当时霍尔木兹未被封锁，2026是物理性封锁+水雷，人类历史上从未有大国发动战争的直接后果是切断自己经济命脉且控制权在对手手里；(3)贵金属唯一确定方向——1973黄金42→180、1971黄金35→120、1914黄金流向美国；(4)化工是中国视角结构性受益者——煤化工替代+光伏锂电产能；(5)不要抄底美股——机构保护性看跌+散户抄底资金耗尽后瀑布式下跌。",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create and seed the R12-V2 hotspot deep-analysis layer.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def api(client: FeishuClient, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = client._request(method, path, body)
    if payload.get("error"):
        raise RuntimeError(str(payload["error"]))
    code = payload.get("code", 0)
    if code not in (0, "0", None):
        raise RuntimeError(json.dumps(payload, ensure_ascii=False))
    return payload


def paged_items(client: FeishuClient, path: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page_token = ""
    while True:
        query = {"page_size": 500}
        if page_token:
            query["page_token"] = page_token
        payload = api(client, "GET", f"{path}?{urlencode(query)}")
        data = payload.get("data", {}) or {}
        items.extend(list(data.get("items", []) or []))
        if not data.get("has_more"):
            break
        page_token = str(data.get("page_token", "")).strip()
        if not page_token:
            break
    return items


def list_tables(client: FeishuClient, app_token: str) -> list[dict[str, Any]]:
    return paged_items(client, f"/bitable/v1/apps/{app_token}/tables")


def list_fields(client: FeishuClient, app_token: str, table_id: str) -> list[dict[str, Any]]:
    return paged_items(client, f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields")


def list_records(client: FeishuClient, app_token: str, table_id: str) -> list[dict[str, Any]]:
    return paged_items(client, f"/bitable/v1/apps/{app_token}/tables/{table_id}/records")


def field_name(field: dict[str, Any]) -> str:
    return str(field.get("field_name") or field.get("name") or "").strip()


def sanitize_property(field_type: int, property_value: Any) -> dict[str, Any] | None:
    if not isinstance(property_value, dict) or not property_value:
        return None
    if field_type in {SINGLE_SELECT_FIELD}:
        options = []
        for option in property_value.get("options", []) or []:
            if not isinstance(option, dict):
                continue
            name = str(option.get("name", "")).strip()
            if not name:
                continue
            cleaned: dict[str, Any] = {"name": name}
            if option.get("color") is not None:
                cleaned["color"] = option["color"]
            options.append(cleaned)
        return {"options": options} if options else None
    return dict(property_value)


def existing_table_id(client: FeishuClient, app_token: str, table_name: str) -> str:
    for table in list_tables(client, app_token):
        if str(table.get("name", "")).strip() == table_name:
            return str(table.get("table_id", "")).strip()
    return ""


def ensure_table(client: FeishuClient, app_token: str, table_name: str, field_specs: list[dict[str, Any]], *, dry_run: bool) -> tuple[str, list[str]]:
    created_fields: list[str] = []
    table_id = existing_table_id(client, app_token, table_name)
    if not table_id:
        if dry_run:
            return DRY_RUN_TABLE_ID, created_fields
        created = api(client, "POST", f"/bitable/v1/apps/{app_token}/tables", {"table": {"name": table_name}})
        table = (created.get("data", {}) or {}).get("table", {}) or {}
        table_id = str(table.get("table_id", "")).strip() or existing_table_id(client, app_token, table_name)
        if not table_id:
            raise RuntimeError(f"failed to create table {table_name}")

    current_fields = list_fields(client, app_token, table_id) if not dry_run else []
    current_names = {field_name(item): item for item in current_fields}
    primary_name = field_specs[0]["field_name"]
    if not dry_run and current_fields:
        primary_field = next((field for field in current_fields if field.get("is_primary")), current_fields[0])
        if field_name(primary_field) != primary_name:
            api(
                client,
                "PUT",
                f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{primary_field['field_id']}",
                {"field_name": primary_name, "type": int(primary_field.get('type') or TEXT_FIELD)},
            )
            current_fields = list_fields(client, app_token, table_id)
            current_names = {field_name(item): item for item in current_fields}

    for field in field_specs[1:]:
        name = field["field_name"]
        if name in current_names:
            continue
        if dry_run:
            created_fields.append(name)
            continue
        body: dict[str, Any] = {"field_name": name, "type": field["type"]}
        prop = sanitize_property(field["type"], field.get("property"))
        if prop:
            body["property"] = prop
        api(client, "POST", f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields", body)
        created_fields.append(name)
        current_names[name] = {"field_name": name}
    return table_id, created_fields


def ensure_backlink_fields(client: FeishuClient, app_token: str, table_id: str, *, dry_run: bool) -> list[str]:
    current_fields = list_fields(client, app_token, table_id) if not dry_run else []
    current_names = {field_name(item) for item in current_fields}
    created: list[str] = []
    for field in L1_BACKLINK_FIELDS:
        if field["field_name"] in current_names:
            continue
        if dry_run:
            created.append(field["field_name"])
            continue
        api(
            client,
            "POST",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
            {"field_name": field["field_name"], "type": field["type"]},
        )
        created.append(field["field_name"])
        current_names.add(field["field_name"])
    return created


def upsert_record(client: FeishuClient, app_token: str, table_id: str, primary_field: str, fields: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    records = [] if dry_run and table_id == DRY_RUN_TABLE_ID else list_records(client, app_token, table_id)
    key = str(fields.get(primary_field, "")).strip()
    existing = next((record for record in records if str((record.get("fields") or {}).get(primary_field, "")).strip() == key), None)
    if dry_run:
        return {
            "action": "update" if existing else "create",
            "table_id": table_id,
            "primary_field": primary_field,
            "primary_value": key,
            "fields": fields,
        }
    if existing:
        record_id = str(existing.get("record_id") or existing.get("id") or "").strip()
        payload = api(client, "PUT", f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}", {"fields": fields})
        return {"action": "update", "record_id": record_id, "payload": payload}
    payload = api(client, "POST", f"/bitable/v1/apps/{app_token}/tables/{table_id}/records", {"fields": fields})
    data = payload.get("data", {}) or {}
    record = data.get("record", data) or {}
    return {"action": "create", "record_id": str(record.get("record_id") or record.get("id") or "").strip(), "payload": payload}


def update_l1_signal(client: FeishuClient, *, dry_run: bool) -> dict[str, Any]:
    records = list_records(client, TARGET_APP_TOKEN, L1_EVENT_SIGNAL_TABLE_ID)
    target = next((record for record in records if str((record.get("fields") or {}).get("event_id", "")).strip() == HOTSPOT_RECORD["source_event_id"]), None)
    if target is None:
        raise RuntimeError(f"source event {HOTSPOT_RECORD['source_event_id']} not found in L1_康波事件信号")
    current_fields = dict(target.get("fields", {}) or {})
    patch_fields = {
        "deep_analysis_id": HOTSPOT_RECORD["analysis_id"],
        "escalation_probability": HOTSPOT_RECORD["escalation_probability"],
        "duration_estimate": HOTSPOT_RECORD["duration_estimate"],
    }
    merged_fields = dict(current_fields)
    merged_fields.update(patch_fields)
    if dry_run:
        return {"record_id": str(target.get("record_id") or target.get("id") or ""), "fields": patch_fields, "mode": "structured"}
    record_id = str(target.get("record_id") or target.get("id") or "").strip()
    payload = api(
        client,
        "PUT",
        f"/bitable/v1/apps/{TARGET_APP_TOKEN}/tables/{L1_EVENT_SIGNAL_TABLE_ID}/records/{record_id}",
        {"fields": patch_fields},
    )
    return {"record_id": record_id, "fields": patch_fields, "mode": "structured", "payload": payload}


def readback_record(client: FeishuClient, app_token: str, table_id: str, primary_field: str, primary_value: str) -> dict[str, Any] | None:
    for record in list_records(client, app_token, table_id):
        if str((record.get("fields") or {}).get(primary_field, "")).strip() == primary_value:
            return record
    return None


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    client = FeishuClient()
    if not client.available:
        raise SystemExit("FEISHU_APP_ID / FEISHU_APP_SECRET are required")

    table_id, created_fields = ensure_table(
        client,
        TARGET_APP_TOKEN,
        HOTSPOT_TABLE_NAME,
        HOTSPOT_FIELD_SPECS,
        dry_run=args.dry_run,
    )
    created_backlink_fields = ensure_backlink_fields(client, TARGET_APP_TOKEN, L1_EVENT_SIGNAL_TABLE_ID, dry_run=args.dry_run)
    hotspot_result = upsert_record(
        client,
        TARGET_APP_TOKEN,
        table_id,
        "analysis_id",
        HOTSPOT_RECORD,
        dry_run=args.dry_run,
    )
    l1_result = update_l1_signal(client, dry_run=args.dry_run)

    hotspot_readback = None if args.dry_run else readback_record(client, TARGET_APP_TOKEN, table_id, "analysis_id", HOTSPOT_RECORD["analysis_id"])
    l1_readback = None if args.dry_run else readback_record(client, TARGET_APP_TOKEN, L1_EVENT_SIGNAL_TABLE_ID, "event_id", HOTSPOT_RECORD["source_event_id"])

    payload = {
        "mode": "dry-run" if args.dry_run else "apply",
        "target_app_token": TARGET_APP_TOKEN,
        "hotspot_table_name": HOTSPOT_TABLE_NAME,
        "hotspot_table_id": table_id,
        "created_hotspot_fields": created_fields,
        "created_l1_backlink_fields": created_backlink_fields,
        "hotspot_result": hotspot_result,
        "l1_link_result": l1_result,
        "hotspot_readback": hotspot_readback,
        "l1_readback": l1_readback,
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
