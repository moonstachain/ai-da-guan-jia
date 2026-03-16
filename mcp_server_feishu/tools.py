from __future__ import annotations

from typing import Any

from mcp_server_feishu.feishu_client import FeishuClient


MISSING_CREDENTIALS_MESSAGE = (
    "飞书凭证未配置，请设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET 环境变量"
)


def _credentials_guard() -> tuple[FeishuClient, dict[str, Any] | None]:
    client = FeishuClient()
    if not client.available:
        return client, {
            "error": MISSING_CREDENTIALS_MESSAGE,
            "code": "missing_credentials",
            "success": False,
        }
    return client, None


def feishu_read_doc(params: dict[str, Any]) -> dict[str, Any]:
    """
    读取飞书云文档。
    """
    client, error = _credentials_guard()
    if error is not None:
        return error
    document_id = str(params.get("document_id", "") or "").strip()
    if not document_id:
        return {"error": "缺少 document_id", "success": False}
    result = client.read_doc(document_id)
    if "error" in result:
        return {"error": result["error"], "code": result.get("code"), "success": False}
    return {
        "title": result.get("title", ""),
        "content": result.get("content", ""),
        "success": True,
    }


def feishu_read_wiki(params: dict[str, Any]) -> dict[str, Any]:
    """
    读取飞书知识库节点。
    """
    client, error = _credentials_guard()
    if error is not None:
        return error
    space_id = str(params.get("space_id", "") or "").strip()
    node_token = str(params.get("node_token", "") or "").strip()
    if not space_id or not node_token:
        return {"error": "缺少 space_id 或 node_token", "success": False}
    result = client.read_wiki_node(space_id, node_token)
    if "error" in result:
        return {"error": result["error"], "code": result.get("code"), "success": False}
    return {
        "title": result.get("title", ""),
        "node_type": result.get("node_type", ""),
        "content": result.get("content", ""),
        "success": True,
    }


def feishu_list_tables(params: dict[str, Any]) -> dict[str, Any]:
    """
    列出飞书多维表格中的所有数据表。
    """
    client, error = _credentials_guard()
    if error is not None:
        return error
    app_token = str(params.get("app_token", "") or "").strip()
    if not app_token:
        return {"error": "缺少 app_token", "success": False}
    result = client.list_bitable_tables(app_token)
    if "error" in result:
        return {"error": result["error"], "code": result.get("code"), "success": False}
    tables = result.get("tables", [])
    return {"tables": tables, "count": len(tables), "success": True}


def feishu_read_records(params: dict[str, Any]) -> dict[str, Any]:
    """
    读取飞书多维表格记录。
    """
    client, error = _credentials_guard()
    if error is not None:
        return error
    app_token = str(params.get("app_token", "") or "").strip()
    table_id = str(params.get("table_id", "") or "").strip()
    if not app_token or not table_id:
        return {"error": "缺少 app_token 或 table_id", "success": False}
    page_size = params.get("page_size", 100)
    try:
        page_size = int(page_size)
    except (TypeError, ValueError):
        return {"error": "page_size 必须是整数", "success": False}
    result = client.read_bitable_records(app_token, table_id, page_size=page_size)
    if "error" in result:
        return {"error": result["error"], "code": result.get("code"), "success": False}
    return {
        "records": result.get("records", []),
        "total": result.get("total", 0),
        "success": True,
    }

