from __future__ import annotations

from typing import Any

from mcp_server_feishu.feishu_client import FeishuClient


SERVICE_UNAVAILABLE_CODE = "service_unavailable"
_client: FeishuClient | None = None


def get_client() -> FeishuClient:
    global _client
    if _client is None:
        _client = FeishuClient()
    return _client


def reset_client() -> None:
    global _client
    _client = None


def _service_unavailable() -> dict[str, Any] | None:
    client = get_client()
    if client.available:
        return None
    return {
        "error": "Feishu client unavailable",
        "code": SERVICE_UNAVAILABLE_CODE,
    }


def handle_health() -> dict[str, Any]:
    client = get_client()
    return {"status": "ok", "feishu_available": client.available}


def handle_list_tables(app_token: str) -> dict[str, Any]:
    error = _service_unavailable()
    if error is not None:
        return error
    return get_client().list_bitable_tables(app_token)


def handle_read_records(app_token: str, table_id: str, page_size: int = 100) -> dict[str, Any]:
    error = _service_unavailable()
    if error is not None:
        return error
    return get_client().read_bitable_records(app_token, table_id, page_size)


def handle_read_doc(document_id: str) -> dict[str, Any]:
    error = _service_unavailable()
    if error is not None:
        return error
    return get_client().read_doc(document_id)


def handle_read_wiki(space_id: str, node_token: str) -> dict[str, Any]:
    error = _service_unavailable()
    if error is not None:
        return error
    return get_client().read_wiki_node(space_id, node_token)
