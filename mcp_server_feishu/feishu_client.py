from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any


class FeishuClient:
    """飞书 Open API 最小客户端，只读操作"""

    BASE_URL = "https://open.feishu.cn/open-apis"

    def __init__(self):
        """
        从环境变量读取 FEISHU_APP_ID 和 FEISHU_APP_SECRET。
        如果缺失，设置 self.available = False。
        不在构造时获取 token，延迟到第一次调用时获取。
        """
        self.app_id = os.environ.get("FEISHU_APP_ID")
        self.app_secret = os.environ.get("FEISHU_APP_SECRET")
        self.available = bool(self.app_id and self.app_secret)
        self._token: str | None = None
        self._token_expires: float = 0.0

    def _missing_credentials_error(self) -> dict[str, str]:
        if not self.app_id:
            return {"error": "FEISHU_APP_ID 未设置", "code": "missing_credentials"}
        if not self.app_secret:
            return {"error": "FEISHU_APP_SECRET 未设置", "code": "missing_credentials"}
        return {"error": "飞书凭证未配置", "code": "missing_credentials"}

    def _decode_response(self, response: Any) -> dict[str, Any]:
        payload = response.read()
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        return json.loads(payload)

    def _ensure_token(self) -> str | None:
        """
        获取 tenant_access_token。
        """
        if not self.available:
            return None
        now = time.time()
        if self._token and now < self._token_expires:
            return self._token

        body = json.dumps(
            {"app_id": self.app_id, "app_secret": self.app_secret},
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.BASE_URL}/auth/v3/tenant_access_token/internal",
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                payload = self._decode_response(response)
        except urllib.error.HTTPError as exc:
            try:
                payload = self._decode_response(exc)
            except Exception:
                return None
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            return None

        token = payload.get("tenant_access_token")
        expire = int(payload.get("expire", 7200) or 7200)
        if not token:
            return None
        self._token = token
        self._token_expires = now + max(expire - 60, 60)
        return self._token

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        通用请求方法。
        自动带 Authorization: Bearer {token} 头。
        返回 JSON 解析后的 dict。
        网络错误返回 {"error": "...", "code": "network_error"}。
        """
        if not self.available:
            return self._missing_credentials_error()

        token = self._ensure_token()
        if token is None:
            return {"error": "tenant_access_token 获取失败", "code": "token_error"}

        data = None
        headers = {"Authorization": f"Bearer {token}"}
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"

        request = urllib.request.Request(
            f"{self.BASE_URL}{path}",
            data=data,
            headers=headers,
            method=method.upper(),
        )

        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return self._decode_response(response)
        except urllib.error.HTTPError as exc:
            try:
                payload = self._decode_response(exc)
                payload.setdefault("code", "http_error")
                return payload
            except Exception:
                return {"error": str(exc), "code": "http_error"}
        except urllib.error.URLError as exc:
            return {"error": str(exc.reason), "code": "network_error"}
        except json.JSONDecodeError as exc:
            return {"error": f"invalid JSON response: {exc}", "code": "invalid_json"}
        except OSError as exc:
            return {"error": str(exc), "code": "network_error"}

    def read_doc(self, document_id: str) -> dict[str, Any]:
        """
        读取云文档内容。
        """
        payload = self._request("GET", f"/docx/v1/documents/{document_id}/raw_content")
        if "error" in payload:
            return payload
        data = payload.get("data", payload)
        content = data.get("content") or data.get("raw_content") or ""
        title = data.get("title") or data.get("document", {}).get("title") or ""
        return {"content": content, "title": title}

    def read_wiki_node(self, space_id: str, node_token: str) -> dict[str, Any]:
        """
        读取知识库节点。
        """
        payload = self._request("GET", f"/wiki/v2/spaces/{space_id}/nodes/{node_token}")
        if "error" in payload:
            return payload
        data = payload.get("data", payload)
        node = data.get("node", data)
        result = {
            "title": node.get("title", ""),
            "node_type": node.get("obj_type", node.get("node_type", "")),
            "obj_token": node.get("obj_token", ""),
        }
        if result["node_type"] == "doc":
            doc_payload = self.read_doc(result["obj_token"])
            if "error" in doc_payload:
                return doc_payload
            result["content"] = doc_payload.get("content", "")
            if not result["title"]:
                result["title"] = doc_payload.get("title", "")
        return result

    def read_bitable_records(self, app_token: str, table_id: str, page_size: int = 100) -> dict[str, Any]:
        """
        读取多维表格记录。
        """
        payload = self._request(
            "GET",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records?page_size={page_size}",
        )
        if "error" in payload:
            return payload
        data = payload.get("data", payload)
        items = data.get("items") or data.get("records") or []
        total = data.get("total", len(items))
        return {"records": items, "total": total}

    def list_bitable_tables(self, app_token: str) -> dict[str, Any]:
        """
        列出多维表格中的所有数据表。
        """
        payload = self._request("GET", f"/bitable/v1/apps/{app_token}/tables")
        if "error" in payload:
            return payload
        data = payload.get("data", payload)
        items = data.get("items") or data.get("tables") or []
        tables = [
            {"table_id": item.get("table_id", ""), "name": item.get("name", "")}
            for item in items
        ]
        return {"tables": tables}

