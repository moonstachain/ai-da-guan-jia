from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from mcp_server.tools import (
    list_artifacts,
    list_skills,
    read_artifact,
    route_task_tool,
    write_artifact,
)

try:
    import mcp.server.stdio
    import mcp.types as mcp_types
    from mcp.server.lowlevel import NotificationOptions, Server
    from mcp.server.models import InitializationOptions

    MCP_SDK_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised in environments without the SDK
    MCP_SDK_AVAILABLE = False


SERVER_NAME = "ai-da-guan-jia"
SERVER_VERSION = "0.1.0"

TOOL_DEFINITIONS = [
    {
        "name": "read_artifact",
        "description": "读取本地 canonical artifact 文件",
        "inputSchema": {
            "type": "object",
            "required": ["path"],
            "properties": {"path": {"type": "string"}},
        },
    },
    {
        "name": "write_artifact",
        "description": "写入本地 canonical artifact 文件",
        "inputSchema": {
            "type": "object",
            "required": ["path", "content"],
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
        },
    },
    {
        "name": "list_artifacts",
        "description": "列出 artifacts 目录下的文件",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prefix": {"type": "string"},
                "max_depth": {"type": "integer"},
            },
        },
    },
    {
        "name": "list_skills",
        "description": "查询 skill manifest，支持按 tier/domain/level 过滤",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tier": {"type": "string"},
                "component_domain": {"type": "string"},
                "control_level": {"type": "string"},
            },
        },
    },
    {
        "name": "route_task",
        "description": "给定任务描述，推荐最小充分的 skill 组合",
        "inputSchema": {
            "type": "object",
            "required": ["task_description"],
            "properties": {
                "task_description": {"type": "string"},
                "component_domain": {"type": "string"},
                "control_level": {"type": "string"},
            },
        },
    },
]

TOOL_HANDLERS = {
    "read_artifact": read_artifact,
    "write_artifact": write_artifact,
    "list_artifacts": list_artifacts,
    "list_skills": list_skills,
    "route_task": route_task_tool,
}


def _dispatch_tool(name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return {"error": f"unknown tool: {name}"}
    return handler(arguments or {})


def _json_rpc_response(request_id: Any, result: dict[str, Any] | None = None, error: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    return payload


def _handle_fallback_request(request: dict[str, Any]) -> dict[str, Any] | None:
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
                "isError": "error" in result,
            },
        )
    return _json_rpc_response(
        request_id,
        error={"code": -32601, "message": f"method not found: {method}"},
    )


async def _run_fallback_stdio_server() -> None:
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            response = _json_rpc_response(
                None,
                error={"code": -32700, "message": f"invalid JSON: {exc}"},
            )
            print(json.dumps(response, ensure_ascii=False), flush=True)
            continue

        response = _handle_fallback_request(request)
        if response is not None:
            print(json.dumps(response, ensure_ascii=False), flush=True)


if MCP_SDK_AVAILABLE:  # pragma: no branch - runtime selection
    server = Server(SERVER_NAME)

    @server.list_tools()
    async def handle_list_tools() -> list[mcp_types.Tool]:
        return [
            mcp_types.Tool(
                name=tool["name"],
                description=tool["description"],
                inputSchema=tool["inputSchema"],
            )
            for tool in TOOL_DEFINITIONS
        ]

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict[str, Any]) -> mcp_types.CallToolResult:
        result = _dispatch_tool(name, arguments)
        return mcp_types.CallToolResult(
            content=[
                mcp_types.TextContent(
                    type="text",
                    text=json.dumps(result, ensure_ascii=False),
                )
            ],
            structuredContent=result,
            isError="error" in result,
        )


async def main() -> None:
    if MCP_SDK_AVAILABLE:
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name=SERVER_NAME,
                    server_version=SERVER_VERSION,
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
        return

    await _run_fallback_stdio_server()


if __name__ == "__main__":
    asyncio.run(main())

