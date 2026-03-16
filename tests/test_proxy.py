from __future__ import annotations

import importlib
import json
import threading
import urllib.error
import urllib.request
from contextlib import contextmanager
from unittest.mock import patch

from proxy import routes
from proxy.server import BIND_ADDRESS, create_server


def _request_json(url: str, token: str | None = None) -> tuple[int, dict]:
    request = urllib.request.Request(url, method="GET")
    if token is not None:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.getcode(), json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


@contextmanager
def _running_server(token: str = "test-token"):
    server = create_server(port=0, proxy_token=token)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_proxy_modules_import_without_error() -> None:
    assert importlib.import_module("proxy.server")
    assert importlib.import_module("proxy.routes")


def test_server_starts_and_responds_to_health() -> None:
    with _running_server() as server, patch(
        "proxy.server.routes.handle_health",
        return_value={"status": "ok", "feishu_available": True},
    ):
        status, payload = _request_json(
            f"http://127.0.0.1:{server.server_port}/health",
            token="test-token",
        )

    assert status == 200
    assert payload == {"status": "ok", "feishu_available": True}


def test_request_without_token_returns_401() -> None:
    with _running_server() as server:
        status, payload = _request_json(f"http://127.0.0.1:{server.server_port}/health")

    assert status == 401
    assert payload == {"error": "unauthorized"}


def test_request_with_wrong_token_returns_401() -> None:
    with _running_server() as server:
        status, payload = _request_json(
            f"http://127.0.0.1:{server.server_port}/health",
            token="wrong-token",
        )

    assert status == 401
    assert payload == {"error": "unauthorized"}


def test_request_with_correct_token_returns_200() -> None:
    with _running_server() as server, patch(
        "proxy.server.routes.handle_health",
        return_value={"status": "ok", "feishu_available": True},
    ):
        status, payload = _request_json(
            f"http://127.0.0.1:{server.server_port}/health",
            token="test-token",
        )

    assert status == 200
    assert payload["status"] == "ok"


def test_health_route_uses_feishu_client_availability() -> None:
    routes.reset_client()
    with patch("proxy.routes.FeishuClient") as mock_client_cls:
        mock_client_cls.return_value.available = False

        payload = routes.handle_health()

    assert payload == {"status": "ok", "feishu_available": False}


def test_list_tables_route_returns_tables() -> None:
    routes.reset_client()
    with patch("proxy.routes.FeishuClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.available = True
        mock_client.list_bitable_tables.return_value = {
            "tables": [{"table_id": "tbl1", "name": "Main"}],
            "count": 1,
        }

        payload = routes.handle_list_tables("app-token")

    assert payload == {"tables": [{"table_id": "tbl1", "name": "Main"}], "count": 1}


def test_read_records_route_returns_records() -> None:
    routes.reset_client()
    with patch("proxy.routes.FeishuClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.available = True
        mock_client.read_bitable_records.return_value = {
            "records": [{"record_id": "rec1"}],
            "total": 1,
        }

        payload = routes.handle_read_records("app-token", "table-token", 50)

    assert payload == {"records": [{"record_id": "rec1"}], "total": 1}


def test_read_doc_route_returns_title_and_content() -> None:
    routes.reset_client()
    with patch("proxy.routes.FeishuClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.available = True
        mock_client.read_doc.return_value = {"title": "Doc", "content": "Body"}

        payload = routes.handle_read_doc("doc-token")

    assert payload == {"title": "Doc", "content": "Body"}


def test_read_wiki_route_returns_content() -> None:
    routes.reset_client()
    with patch("proxy.routes.FeishuClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.available = True
        mock_client.read_wiki_node.return_value = {
            "title": "Wiki",
            "content": "Body",
        }

        payload = routes.handle_read_wiki("space", "node")

    assert payload == {"title": "Wiki", "content": "Body"}


def test_missing_required_param_returns_400() -> None:
    with _running_server() as server:
        status, payload = _request_json(
            f"http://127.0.0.1:{server.server_port}/bitable/tables",
            token="test-token",
        )

    assert status == 400
    assert payload == {"error": "missing required parameter: app_token"}


def test_invalid_route_returns_404() -> None:
    with _running_server() as server:
        status, payload = _request_json(
            f"http://127.0.0.1:{server.server_port}/nope",
            token="test-token",
        )

    assert status == 404
    assert payload == {"error": "not found"}


def test_feishu_client_unavailable_returns_503() -> None:
    with _running_server() as server, patch(
        "proxy.server.routes.handle_list_tables",
        return_value={"error": "Feishu client unavailable", "code": "service_unavailable"},
    ):
        status, payload = _request_json(
            f"http://127.0.0.1:{server.server_port}/bitable/tables?app_token=test",
            token="test-token",
        )

    assert status == 503
    assert payload["code"] == "service_unavailable"


def test_server_binds_only_to_localhost() -> None:
    server = create_server(port=0, proxy_token="test-token")
    try:
        assert server.server_address[0] == BIND_ADDRESS
    finally:
        server.server_close()
