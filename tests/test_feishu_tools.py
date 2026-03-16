from __future__ import annotations

import json
import os
import subprocess
from unittest.mock import patch

from mcp_server_feishu.feishu_client import FeishuClient
from mcp_server_feishu.tools import (
    feishu_list_tables,
    feishu_read_doc,
    feishu_read_records,
    feishu_read_wiki,
)


class _MockResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_feishu_read_doc_returns_error_when_app_id_missing(monkeypatch) -> None:
    monkeypatch.delenv("FEISHU_APP_ID", raising=False)
    monkeypatch.setenv("FEISHU_APP_SECRET", "test-secret")

    result = feishu_read_doc({"document_id": "doc123"})

    assert result["success"] is False
    assert result["code"] == "missing_credentials"


def test_feishu_list_tables_returns_error_when_app_secret_missing(monkeypatch) -> None:
    monkeypatch.setenv("FEISHU_APP_ID", "test-app")
    monkeypatch.delenv("FEISHU_APP_SECRET", raising=False)

    result = feishu_list_tables({"app_token": "app123"})

    assert result["success"] is False
    assert result["code"] == "missing_credentials"


def test_ensure_token_success_caches_token(monkeypatch) -> None:
    monkeypatch.setenv("FEISHU_APP_ID", "test-app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "test-secret")
    client = FeishuClient()

    with patch("urllib.request.urlopen", return_value=_MockResponse({"tenant_access_token": "tenant-token", "expire": 7200})) as mocked:
        token_first = client._ensure_token()
        token_second = client._ensure_token()

    assert token_first == "tenant-token"
    assert token_second == "tenant-token"
    assert mocked.call_count == 1


def test_ensure_token_failure_returns_none(monkeypatch) -> None:
    monkeypatch.setenv("FEISHU_APP_ID", "test-app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "test-secret")
    client = FeishuClient()

    with patch("urllib.request.urlopen", return_value=_MockResponse({"code": 9999, "msg": "fail"})):
        assert client._ensure_token() is None


def test_read_doc_success_returns_title_and_content(monkeypatch) -> None:
    monkeypatch.setenv("FEISHU_APP_ID", "test-app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "test-secret")
    client = FeishuClient()

    with patch.object(client, "_request", return_value={"data": {"title": "Doc title", "content": "Doc body"}}):
        result = client.read_doc("doc123")

    assert result == {"title": "Doc title", "content": "Doc body"}


def test_read_doc_network_error_returns_error_dict(monkeypatch) -> None:
    monkeypatch.setenv("FEISHU_APP_ID", "test-app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "test-secret")
    client = FeishuClient()

    with patch.object(client, "_request", return_value={"error": "network down", "code": "network_error"}):
        result = client.read_doc("doc123")

    assert result["code"] == "network_error"


def test_read_bitable_records_success_returns_records(monkeypatch) -> None:
    monkeypatch.setenv("FEISHU_APP_ID", "test-app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "test-secret")
    client = FeishuClient()

    with patch.object(client, "_request", return_value={"data": {"items": [{"record_id": "rec1"}], "total": 1}}):
        result = client.read_bitable_records("app123", "tbl123")

    assert result == {"records": [{"record_id": "rec1"}], "total": 1}


def test_list_bitable_tables_success_returns_tables(monkeypatch) -> None:
    monkeypatch.setenv("FEISHU_APP_ID", "test-app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "test-secret")
    client = FeishuClient()

    with patch.object(client, "_request", return_value={"data": {"items": [{"table_id": "tbl1", "name": "Main"}]}}):
        result = client.list_bitable_tables("app123")

    assert result == {"tables": [{"table_id": "tbl1", "name": "Main"}]}


def test_feishu_read_doc_tool_returns_success_true(monkeypatch) -> None:
    monkeypatch.setenv("FEISHU_APP_ID", "test-app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "test-secret")

    with patch("mcp_server_feishu.tools.FeishuClient.read_doc", return_value={"title": "Doc", "content": "Body"}):
        result = feishu_read_doc({"document_id": "doc123"})

    assert result == {"title": "Doc", "content": "Body", "success": True}


def test_feishu_read_wiki_doc_node_returns_content(monkeypatch) -> None:
    monkeypatch.setenv("FEISHU_APP_ID", "test-app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "test-secret")

    with patch(
        "mcp_server_feishu.tools.FeishuClient.read_wiki_node",
        return_value={"title": "Wiki", "node_type": "doc", "content": "Wiki body"},
    ):
        result = feishu_read_wiki({"space_id": "space123", "node_token": "node123"})

    assert result == {"title": "Wiki", "node_type": "doc", "content": "Wiki body", "success": True}


def test_feishu_list_tables_returns_tables_and_count(monkeypatch) -> None:
    monkeypatch.setenv("FEISHU_APP_ID", "test-app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "test-secret")

    with patch(
        "mcp_server_feishu.tools.FeishuClient.list_bitable_tables",
        return_value={"tables": [{"table_id": "tbl1", "name": "Main"}]},
    ):
        result = feishu_list_tables({"app_token": "app123"})

    assert result == {"tables": [{"table_id": "tbl1", "name": "Main"}], "count": 1, "success": True}


def test_feishu_read_records_returns_records_and_total(monkeypatch) -> None:
    monkeypatch.setenv("FEISHU_APP_ID", "test-app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "test-secret")

    with patch(
        "mcp_server_feishu.tools.FeishuClient.read_bitable_records",
        return_value={"records": [{"record_id": "rec1"}], "total": 1},
    ):
        result = feishu_read_records({"app_token": "app123", "table_id": "tbl123"})

    assert result == {"records": [{"record_id": "rec1"}], "total": 1, "success": True}


def test_all_tools_return_error_for_missing_required_params(monkeypatch) -> None:
    monkeypatch.setenv("FEISHU_APP_ID", "test-app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "test-secret")

    assert feishu_read_doc({})["success"] is False
    assert feishu_read_wiki({"space_id": "space-only"})["success"] is False
    assert feishu_list_tables({})["success"] is False
    assert feishu_read_records({"app_token": "app-only"})["success"] is False


def test_server_module_starts_without_import_error(monkeypatch) -> None:
    env = dict(os.environ)
    env.pop("FEISHU_APP_ID", None)
    env.pop("FEISHU_APP_SECRET", None)
    request = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        ensure_ascii=False,
    ) + "\n"

    proc = subprocess.run(
        ["python3", "-m", "mcp_server_feishu.server"],
        cwd="/Users/liming/Documents/codex-ai-gua-jia-01",
        input=request,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert proc.returncode == 0
    assert "\"serverInfo\"" in proc.stdout
