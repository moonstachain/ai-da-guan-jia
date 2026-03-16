from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from mcp_server_feishu.tools import (
    feishu_list_tables,
    feishu_read_doc,
    feishu_read_records,
    feishu_read_wiki,
)


SERVER_NAME = "ai-da-guan-jia-feishu"
SERVER_VERSION = "0.1.0"

TOOL_DEFINITIONS = [
    {
        "name": "feishu_read_doc",
        "description": "读取飞书云文档内容",
        "inputSchema": {
            "type": "object",
            "required": ["document_id"],
            "properties": {"document_id": {"type": "string"}},
        },
    },
    {
        "name": "feishu_read_wiki",
        "description": "读取飞书知识库节点",
        "inputSchema": {
            "type": "object",
            "required": ["space_id", "node_token"],
            "properties": {
                "space_id": {"type": "string"},
                "node_token": {"type": "string"},
            },
        },
    },
    {
        "name": "feishu_list_tables",
        "description": "列出飞书多维表格中的所有数据表",
        "inputSchema": {
            "type": "object",
            "required": ["app_token"],
            "properties": {"app_token": {"type": "string"}},
        },
    },
    {
        "name": "feishu_read_records",
        "description": "读取飞书多维表格中的记录",
        "inputSchema": {
            "type": "object",
            "required": ["app_token", "table_id"],
            "properties": {
                "app_token": {"type": "string"},
                "table_id": {"type": "string"},
                "page_size": {"type": "integer"},
            },
        },
    },
]

TOOL_HANDLERS = {
    "feishu_read_doc": feishu_read_doc,
    "feishu_read_wiki": feishu_read_wiki,
    "feishu_list_tables": feishu_list_tables,
    "feishu_read_records": feishu_read_records,
}


def _dispatch_tool(name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return {"error": f"unknown tool: {name}", "success": False}
    return handler(arguments or {})


def _json_rpc_response(
    request_id: Any,
    result: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    return payload


def _handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params", {}) or {}

    if method == "initialize":
        return _json_rpc_response(
            request_id,
            {
                "protocolVersion": "2025-06-18",
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "capabilities": {"tools": {"listChanged": False}},
            },
        )
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return _json_rpc_response(request_id, {"tools": TOOL_DEFINITIONS})
    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        result = _dispatch_tool(tool_name, arguments)
        return _json_rpc_response(
            request_id,
            {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                "structuredContent": result,
                "isError": not bool(result.get("success", False)),
            },
        )
    return _json_rpc_response(
        request_id,
        error={"code": -32601, "message": f"method not found: {method}"},
    )


async def main() -> None:
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            print(
                json.dumps(
                    _json_rpc_response(
                        None,
                        error={"code": -32700, "message": f"invalid JSON: {exc}"},
                    ),
                    ensure_ascii=False,
                ),
                flush=True,
            )
            continue

        response = _handle_request(request)
        if response is not None:
            print(json.dumps(response, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    asyncio.run(main())

