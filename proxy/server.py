"""
Feishu HTTP Proxy — 让 Claude 通过 web_fetch 读取飞书数据

启动方式：
  python -m proxy.server

默认监听：http://127.0.0.1:9800

环境变量：
  FEISHU_APP_ID       - 飞书 App ID（复用 R4）
  FEISHU_APP_SECRET   - 飞书 App Secret（复用 R4）
  PROXY_TOKEN         - proxy 访问令牌（Claude 调用时带在 header 里）
  PROXY_PORT          - 监听端口（默认 9800）
"""

from __future__ import annotations

import json
import os
import secrets
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from proxy import routes


DEFAULT_PORT = 9800
BIND_ADDRESS = "127.0.0.1"


class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True


class FeishuProxyHandler(BaseHTTPRequestHandler):
    """
    只读 Feishu HTTP proxy 路由。
    """

    server_version = "FeishuProxy/0.1"

    def do_GET(self) -> None:
        if not self._check_auth():
            self._error_response("unauthorized", status=401)
            return

        parsed = urllib.parse.urlparse(self.path)
        params = {
            key: values[-1]
            for key, values in urllib.parse.parse_qs(parsed.query, keep_blank_values=True).items()
        }

        try:
            if parsed.path == "/health":
                self._json_response(routes.handle_health())
                return
            if parsed.path == "/bitable/tables":
                app_token = self._required_param(params, "app_token")
                self._respond_result(routes.handle_list_tables(app_token))
                return
            if parsed.path == "/bitable/records":
                app_token = self._required_param(params, "app_token")
                table_id = self._required_param(params, "table_id")
                page_size = int(params.get("page_size", "100"))
                self._respond_result(routes.handle_read_records(app_token, table_id, page_size))
                return
            if parsed.path == "/doc":
                document_id = self._required_param(params, "document_id")
                self._respond_result(routes.handle_read_doc(document_id))
                return
            if parsed.path == "/wiki":
                space_id = self._required_param(params, "space_id")
                node_token = self._required_param(params, "node_token")
                self._respond_result(routes.handle_read_wiki(space_id, node_token))
                return
            self._error_response("not found", status=404)
        except ValueError as exc:
            self._error_response(str(exc), status=400)
        except Exception as exc:
            self._error_response(f"internal server error: {exc}", status=500)

    def _required_param(self, params: dict[str, str], name: str) -> str:
        value = str(params.get(name, "") or "").strip()
        if not value:
            raise ValueError(f"missing required parameter: {name}")
        return value

    def _respond_result(self, result: dict[str, Any]) -> None:
        if result.get("code") == routes.SERVICE_UNAVAILABLE_CODE:
            self._json_response(result, status=503)
            return
        self._json_response(result)

    def _check_auth(self) -> bool:
        expected = getattr(self.server, "proxy_token", "")
        header = self.headers.get("Authorization", "")
        if not expected:
            return False
        return secrets.compare_digest(header, f"Bearer {expected}")

    def _json_response(self, data: dict[str, Any], status: int = 200) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _error_response(self, message: str, status: int = 400) -> None:
        self._json_response({"error": message}, status=status)

    def log_message(self, format: str, *args: Any) -> None:
        return


def create_server(port: int | None = None, proxy_token: str | None = None) -> ReusableHTTPServer:
    if port is None:
        port = int(os.environ.get("PROXY_PORT", str(DEFAULT_PORT)))
    if proxy_token is None:
        proxy_token = str(os.environ.get("PROXY_TOKEN", "") or "")
    server = ReusableHTTPServer((BIND_ADDRESS, port), FeishuProxyHandler)
    server.proxy_token = proxy_token
    return server


def main() -> None:
    port = int(os.environ.get("PROXY_PORT", str(DEFAULT_PORT)))
    proxy_token = str(os.environ.get("PROXY_TOKEN", "") or "")
    generated = False
    if not proxy_token:
        proxy_token = secrets.token_urlsafe(24)
        generated = True

    server = create_server(port=port, proxy_token=proxy_token)
    print(f"Feishu proxy listening on http://{BIND_ADDRESS}:{port}")
    if generated:
        print(f"Generated PROXY_TOKEN={proxy_token}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
