from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcp_server_feishu.feishu_client import FeishuClient


def extract_wiki_token(input_str: str) -> str:
    match = re.search(r"/wiki/([a-zA-Z0-9]+)", input_str)
    if match:
        return match.group(1)
    token = input_str.split("?", 1)[0].rstrip("/").split("/")[-1]
    return token


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


def get_wiki_node_info(client: FeishuClient, wiki_token: str) -> dict[str, Any]:
    payload = api(client, "GET", f"/wiki/v2/spaces/get_node?token={wiki_token}")
    node = (payload.get("data", {}) or {}).get("node", {}) or {}
    return {
        "obj_type": str(node.get("obj_type", "")).strip(),
        "obj_token": str(node.get("obj_token", "")).strip(),
        "title": str(node.get("title", "")).strip(),
        "node_token": str(node.get("node_token", wiki_token)).strip(),
        "space_id": str(node.get("space_id", "")).strip(),
        "parent_node_token": str(node.get("parent_node_token", "")).strip(),
    }


def read_docx_content(client: FeishuClient, document_id: str) -> str:
    payload = client.read_doc(document_id)
    if payload.get("error"):
        return f"⚠️ 读取文档内容失败: {payload['error']}"
    content = str(payload.get("content", "")).strip()
    return content or "⚠️ 文档内容为空"


def read_doc_legacy(client: FeishuClient, doc_token: str) -> str:
    try:
        payload = api(client, "GET", f"/doc/v2/{doc_token}/raw_content")
        data = payload.get("data", {}) or payload
        return str(data.get("content", "")).strip() or "⚠️ 文档内容为空"
    except Exception as exc:
        return f"⚠️ 读取旧版文档失败: {exc}"


def read_bitable_summary(client: FeishuClient, app_token: str) -> str:
    tables = paged_items(client, f"/bitable/v1/apps/{app_token}/tables")
    lines = [f"## 多维表格摘要（共 {len(tables)} 张表）", "", "| 表名 | table_id | 记录数 |", "|------|----------|--------|"]
    for table in tables:
        table_id = str(table.get("table_id", "")).strip()
        name = str(table.get("name", "unnamed")).strip()
        count = len(paged_items(client, f"/bitable/v1/apps/{app_token}/tables/{table_id}/records")) if table_id else 0
        lines.append(f"| {name} | {table_id} | {count} 条 |")
    return "\n".join(lines)


def render_output(node: dict[str, Any], token: str, content: str) -> str:
    return f"# {node['title']}\n\n> Wiki token: {token} | 类型: {node['obj_type']} | obj_token: {node['obj_token']}\n\n{content}\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="飞书 Wiki 页面内容读取器")
    parser.add_argument("wiki_token", help="Wiki token 或完整 URL")
    parser.add_argument("--output", "-o", help="输出文件路径")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)

    client = FeishuClient()
    if not client.available:
        raise SystemExit("FEISHU_APP_ID / FEISHU_APP_SECRET are required")

    token = extract_wiki_token(args.wiki_token)
    node = get_wiki_node_info(client, token)
    obj_type = node["obj_type"]
    if obj_type == "docx":
        content = read_docx_content(client, node["obj_token"])
    elif obj_type == "doc":
        content = read_doc_legacy(client, node["obj_token"])
    elif obj_type == "bitable":
        content = read_bitable_summary(client, node["obj_token"])
    else:
        content = f"⚠️ 暂不支持自动读取该类型: {obj_type or 'unknown'}"

    output = (
        json.dumps({"wiki_token": token, "node_info": node, "content": content}, ensure_ascii=False, indent=2)
        if args.json
        else render_output(node, token, content)
    )
    if args.output:
        Path(args.output).write_text(output + ("" if output.endswith("\n") else "\n"), encoding="utf-8")
        print(f"✅ 已输出到: {args.output}")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
