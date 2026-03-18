from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcp_server_feishu.feishu_client import FeishuClient


WIKI_TOKEN = "Zge0wIkDDiGPsskJlLFcuT9Pnac"
TABLE_NAME = "原力OS进化编年史"
PROMPT_PATH = Path("/tmp/miaoda-evolution-page-prompt.md")
ARTIFACT_PATH = REPO_ROOT / "artifacts" / "r15-evolution-chronicle" / "result.json"
DATA_PATH = REPO_ROOT / "data" / "r15_evolution_chronicle_records.json"
DRY_RUN_TABLE_ID = "dryrun_evolution_chronicle"

TEXT_FIELD = 1
NUMBER_FIELD = 2
SINGLE_SELECT_FIELD = 3
DATE_FIELD = 5

FIELD_SPECS: list[dict[str, Any]] = [
    {"field_name": "milestone_id", "type": TEXT_FIELD},
    {
        "field_name": "version",
        "type": SINGLE_SELECT_FIELD,
        "property": {"options": [{"name": "1.0"}, {"name": "2.0"}]},
    },
    {"field_name": "phase", "type": TEXT_FIELD},
    {"field_name": "date", "type": DATE_FIELD, "property": {"date_formatter": "yyyy-MM-dd", "auto_fill": False}},
    {"field_name": "milestone_name", "type": TEXT_FIELD},
    {"field_name": "organ_gained", "type": TEXT_FIELD},
    {"field_name": "capability_before", "type": TEXT_FIELD},
    {"field_name": "capability_after", "type": TEXT_FIELD},
    {"field_name": "machine_description", "type": TEXT_FIELD},
    {"field_name": "human_translation", "type": TEXT_FIELD},
    {"field_name": "what_solved", "type": TEXT_FIELD},
    {"field_name": "what_unsolved", "type": TEXT_FIELD},
    {
        "field_name": "evidence_level",
        "type": SINGLE_SELECT_FIELD,
        "property": {"options": [{"name": "L1"}, {"name": "L2"}, {"name": "L3"}, {"name": "L4"}]},
    },
    {"field_name": "evidence_refs", "type": TEXT_FIELD},
    {"field_name": "commit_hash", "type": TEXT_FIELD},
    {"field_name": "tests_passed", "type": NUMBER_FIELD},
]

MIAODA_PROMPT = """# 原力OS 进化图谱 — 妙搭子页搭建提示词

## 角色
你是一个高端 SaaS 仪表盘设计师。请在原力OS治理驾驶舱应用中新增一个子页，名为"进化图谱"。

## 设计风格
与治理驾驶舱一致：深色科技风（#060a12 底色）、毛玻璃卡片、Cyan/Green/Amber/Red 四色信号灯。

## 数据源
绑定飞书多维表 `原力OS进化编年史`（在治理 wiki base 中）。

## 页面 7 个区块

### 区块 1：价值主张（全宽）
- 主标题："让 AI 和人类像共同经营一家公司一样，各司其职、递归进化"
- 三列卡片：
  - 递归进化（Cyan 强调）：任何一次动作的价值在于能否成为下一轮更强行动的燃料
  - 技能统帅（Green 强调）：不替代专业 skill，但知道该调哪几个的最小充分组合
  - 人类友好（Amber 强调）：最小化人类体力消耗和认知摩擦，能自治就不打扰

### 区块 2：DNA → 六判断推演图（全宽）
用流程图展示：
三条 DNA → 六个隐含要求（记忆/验真/知道能力/路由/边界/打扰有值）→ 交叉产生六判断（自治/全局最优/能力复用/验真/进化/最大失真）
颜色：递归进化相关的用 Cyan，技能统帅用 Green，人类友好用 Amber，交叉产物用 Purple。

### 区块 3：1.0 进化时间线（左半，Cyan 主色）
绑定 `原力OS进化编年史` 表，筛选 version=1.0。
- 垂直时间线，左侧渐变竖线
- 每个里程碑：日期 + milestone_name + human_translation
- 6 个阶段用不同透明度区分

### 区块 4：2.0 进化时间线（右半，Purple 主色）
绑定 `原力OS进化编年史` 表，筛选 version=2.0。
- 同样的垂直时间线格式
- 增加 tests_passed 和 commit_hash 辅助信息
- 7 个阶段用不同透明度区分

### 区块 5：三次真进化 + 三次自我纠偏（全宽，双列）
左列（绿色强调）：
1. Canonical-first：真相源先于镜像成立
2. 从任务到战略：从做任务变成有方向有节奏有仪表盘
3. 从对话到系统：从一次性对话变成可测试代码+可查询数据+可操作仪表盘

右列（红色警告色）：
1. 不把飞书镜像误当 canonical
2. 不把治理成熟误当业务执行成熟
3. 不把 Skill 数量误当能力成熟度

### 区块 6：现在在哪里（全宽数字仪表盘）
- 4 个大数字：169 Tests / 15 Commits / 143 Skills / 34 Milestones
- 最大失真条：治理层 92% Mature → 获客/交付 12% Weak
- 下一步队列：新Base统一 → 康波L1.5建表 → Skill合并 → 案例库导入

### 区块 7：完整进化 Log（全宽表格）
直接嵌入 `原力OS进化编年史` 表的视图。
- 可按 version 筛选（1.0 / 2.0）
- 可按 phase 排序
- 显示列：milestone_id / date / milestone_name / human_translation / evidence_level
"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create the R15 evolution chronicle table and seed 34 milestones.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def load_records() -> list[dict[str, Any]]:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return list(payload.get("records", []))


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


def discover_app_token(client: FeishuClient) -> str:
    payload = api(client, "GET", f"/wiki/v2/spaces/get_node?token={WIKI_TOKEN}")
    node = (payload.get("data", {}) or {}).get("node", {}) or {}
    obj_type = str(node.get("obj_type", "")).strip()
    if obj_type != "bitable":
        raise RuntimeError(f"expected bitable wiki node, got {obj_type or 'unknown'}")
    app_token = str(node.get("obj_token", "")).strip()
    if not app_token:
        raise RuntimeError("wiki node did not return obj_token")
    return app_token


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
    if field_type == SINGLE_SELECT_FIELD:
        options = []
        for option in property_value.get("options", []) or []:
            if not isinstance(option, dict):
                continue
            name = str(option.get("name", "")).strip()
            if not name:
                continue
            cleaned = {"name": name}
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


def ensure_table(client: FeishuClient, app_token: str, table_name: str, *, dry_run: bool) -> tuple[str, list[str]]:
    created_fields: list[str] = []
    table_id = existing_table_id(client, app_token, table_name)
    if not table_id:
        if dry_run:
            return DRY_RUN_TABLE_ID, [field["field_name"] for field in FIELD_SPECS[1:]]
        created = api(client, "POST", f"/bitable/v1/apps/{app_token}/tables", {"table": {"name": table_name}})
        table = (created.get("data", {}) or {}).get("table", {}) or {}
        table_id = str(table.get("table_id", "")).strip() or existing_table_id(client, app_token, table_name)
        if not table_id:
            raise RuntimeError(f"failed to create table {table_name}")

    current_fields = list_fields(client, app_token, table_id) if not dry_run else []
    current_names = {field_name(item): item for item in current_fields}
    primary_name = FIELD_SPECS[0]["field_name"]
    if not dry_run and current_fields:
        primary_field = next((field for field in current_fields if field.get("is_primary")), current_fields[0])
        if field_name(primary_field) != primary_name:
            api(
                client,
                "PUT",
                f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{primary_field['field_id']}",
                {"field_name": primary_name, "type": int(primary_field.get("type") or TEXT_FIELD)},
            )
            current_fields = list_fields(client, app_token, table_id)
            current_names = {field_name(item): item for item in current_fields}

    for field in FIELD_SPECS[1:]:
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
    return table_id, created_fields


def normalize_fields(record: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for key, value in record.items():
        if value is None or value == "":
            continue
        if key == "date":
            fields[key] = int(value)
            continue
        if key == "tests_passed":
            fields[key] = int(value)
            continue
        fields[key] = value
    return fields


def upsert_record(client: FeishuClient, app_token: str, table_id: str, fields: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    records = [] if dry_run and table_id == DRY_RUN_TABLE_ID else list_records(client, app_token, table_id)
    primary_value = str(fields["milestone_id"]).strip()
    existing = next((record for record in records if str((record.get("fields") or {}).get("milestone_id", "")).strip() == primary_value), None)
    if dry_run:
        return {
            "action": "update" if existing else "create",
            "table_id": table_id,
            "primary_value": primary_value,
            "fields": fields,
        }
    if existing:
        record_id = str(existing.get("record_id") or existing.get("id") or "").strip()
        payload = api(client, "PUT", f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}", {"fields": fields})
        return {"action": "update", "record_id": record_id, "payload": payload}
    payload = api(client, "POST", f"/bitable/v1/apps/{app_token}/tables/{table_id}/records", {"fields": fields})
    record = ((payload.get("data", {}) or {}).get("record", {}) or {})
    return {"action": "create", "record_id": str(record.get("record_id") or record.get("id") or "").strip(), "payload": payload}


def readback_records(client: FeishuClient, app_token: str, table_id: str) -> list[dict[str, Any]]:
    return list_records(client, app_token, table_id)


def write_prompt_file() -> str:
    PROMPT_PATH.write_text(MIAODA_PROMPT + "\n", encoding="utf-8")
    return str(PROMPT_PATH)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    client = FeishuClient()
    if not client.available:
        raise SystemExit("FEISHU_APP_ID / FEISHU_APP_SECRET are required")

    app_token = discover_app_token(client)
    records = load_records()
    table_id, created_fields = ensure_table(client, app_token, TABLE_NAME, dry_run=args.dry_run)

    write_results = []
    for record in records:
        write_results.append(
            {
                "milestone_id": record["milestone_id"],
                **upsert_record(client, app_token, table_id, normalize_fields(record), dry_run=args.dry_run),
            }
        )

    prompt_path = write_prompt_file()
    readback = [] if args.dry_run else readback_records(client, app_token, table_id)
    readback_sample = []
    for row in readback[:3]:
        fields = row.get("fields", {}) or {}
        readback_sample.append(
            {
                "milestone_id": fields.get("milestone_id"),
                "milestone_name": fields.get("milestone_name"),
                "version": fields.get("version"),
            }
        )

    payload = {
        "mode": "dry-run" if args.dry_run else "apply",
        "wiki_token": WIKI_TOKEN,
        "app_token": app_token,
        "table_name": TABLE_NAME,
        "table_id": table_id,
        "created_fields": created_fields,
        "records_expected": len(records),
        "write_results": write_results,
        "readback_count": len(readback),
        "readback_sample": readback_sample,
        "prompt_path": prompt_path,
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
