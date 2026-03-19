from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any


CAPABILITY_PATH = Path(__file__).resolve().parents[2] / "capabilities" / "yuanlios_strategic_task_tracker.json"
OPENCLAW_CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"
DEFAULT_ACCOUNT_ID = "feishu-claw"
FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"
SHANGHAI_TZ = timezone(timedelta(hours=8))


class StrategicTaskFeishuError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def load_capability_config() -> dict[str, Any]:
    if not CAPABILITY_PATH.exists():
        raise StrategicTaskFeishuError(f"capability file not found: {CAPABILITY_PATH}")
    return json.loads(CAPABILITY_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_feishu_credentials(account_id: str = DEFAULT_ACCOUNT_ID) -> dict[str, str]:
    app_id = str(os.getenv("FEISHU_APP_ID") or "").strip()
    app_secret = str(os.getenv("FEISHU_APP_SECRET") or "").strip()
    if app_id and app_secret:
        return {"app_id": app_id, "app_secret": app_secret}

    if OPENCLAW_CONFIG_PATH.exists():
        config = json.loads(OPENCLAW_CONFIG_PATH.read_text(encoding="utf-8"))
        accounts = (((config.get("channels") or {}).get("feishu") or {}).get("accounts") or {})
        account = accounts.get(account_id) or {}
        app_id = str(account.get("appId") or "").strip()
        app_secret = str(account.get("appSecret") or "").strip()
        if app_id and app_secret:
            return {"app_id": app_id, "app_secret": app_secret}

    raise StrategicTaskFeishuError(
        "missing Feishu credentials: set FEISHU_APP_ID/FEISHU_APP_SECRET or configure ~/.openclaw/openclaw.json"
    )


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts = [_normalize_text(item) for item in value]
        return "、".join([part for part in parts if part])
    if isinstance(value, dict):
        for key in ("name", "text", "value", "label", "display_text"):
            candidate = value.get(key)
            if candidate not in {None, ""}:
                return _normalize_text(candidate)
        return json.dumps(value, ensure_ascii=False) if value else ""
    return str(value).strip()


def _normalize_datetime(value: Any) -> str:
    if value in {None, ""}:
        return ""
    if isinstance(value, dict):
        for key in ("value", "timestamp", "text", "date"):
            candidate = value.get(key)
            if candidate not in {None, ""}:
                return _normalize_datetime(candidate)
        return ""
    if isinstance(value, list):
        return _normalize_datetime(value[0]) if value else ""
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if abs(timestamp) < 10**11:
            timestamp *= 1000
        return datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).astimezone(SHANGHAI_TZ).isoformat()
    text = str(value).strip()
    if not text:
        return ""
    if text.isdigit():
        timestamp = int(text)
        if abs(timestamp) < 10**11:
            timestamp *= 1000
        return datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).astimezone(SHANGHAI_TZ).isoformat()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(SHANGHAI_TZ).isoformat()
    except ValueError:
        return text


def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    fields = record.get("fields") or record
    if not isinstance(fields, dict):
        fields = {}
    return {
        "project_id": _normalize_text(fields.get("project_id")),
        "project_name": _normalize_text(fields.get("project_name")),
        "project_status": _normalize_text(fields.get("project_status")) or "进行中",
        "task_id": _normalize_text(fields.get("task_id")),
        "task_name": _normalize_text(fields.get("task_name")),
        "task_status": _normalize_text(fields.get("task_status")) or "待启动",
        "priority": _normalize_text(fields.get("priority")) or "P1",
        "owner": _normalize_text(fields.get("owner")) or "未指定",
        "start_date": _normalize_datetime(fields.get("start_date")),
        "completion_date": _normalize_datetime(fields.get("completion_date")),
        "blockers": _normalize_text(fields.get("blockers")),
        "evidence_ref": _normalize_text(fields.get("evidence_ref")),
        "dependencies": _normalize_text(fields.get("dependencies")),
        "notes": _normalize_text(fields.get("notes")),
    }


class FeishuBitableAPI:
    def __init__(self, app_id: str, app_secret: str, *, base_url: str = FEISHU_BASE_URL) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = base_url.rstrip("/")
        self._tenant_access_token: str | None = None
        self._token_expires_at = 0.0

    def _request(self, path: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        body = None
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if path != "/auth/v3/tenant_access_token/internal":
            headers["Authorization"] = f"Bearer {self.tenant_access_token()}"
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            raise StrategicTaskFeishuError(str(exc)) from exc
        if data.get("code") not in {0, None}:
            raise StrategicTaskFeishuError(f"Feishu API error for {path}: {json.dumps(data, ensure_ascii=False)}")
        return data

    def tenant_access_token(self) -> str:
        now = time.time()
        if self._tenant_access_token and now < self._token_expires_at:
            return self._tenant_access_token
        payload = self._request(
            "/auth/v3/tenant_access_token/internal",
            method="POST",
            payload={"app_id": self.app_id, "app_secret": self.app_secret},
        )
        token = str(payload.get("tenant_access_token") or "").strip()
        expire = int(payload.get("expire", 7200) or 7200)
        if not token:
            raise StrategicTaskFeishuError("failed to obtain tenant_access_token")
        self._tenant_access_token = token
        self._token_expires_at = now + max(expire - 60, 60)
        return token

    def list_records(self, app_token: str, table_id: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page_token = ""
        while True:
            path = f"/bitable/v1/apps/{app_token}/tables/{table_id}/records?page_size=500"
            if page_token:
                path += f"&page_token={urllib.parse.quote(page_token)}"
            payload = self._request(path)
            data = payload.get("data") or {}
            items.extend(data.get("items") or [])
            if not data.get("has_more"):
                return items
            page_token = str(data.get("page_token") or "").strip()
            if not page_token:
                return items


def read_strategic_tasks() -> dict[str, Any]:
    capability = load_capability_config()
    mirror_surface = capability.get("mirror_surface") or {}
    base_id = str(mirror_surface.get("base_id") or "").strip()
    table_id = str(mirror_surface.get("table_id") or "").strip()
    table_name = str(mirror_surface.get("table_name") or "战略任务追踪").strip()
    if not base_id or not table_id:
        raise StrategicTaskFeishuError("strategic task capability is missing base_id/table_id")

    creds = load_feishu_credentials()
    client = FeishuBitableAPI(creds["app_id"], creds["app_secret"])
    records = client.list_records(base_id, table_id)
    normalized = [_normalize_record(record) for record in records]
    normalized = [item for item in normalized if item.get("task_id")]
    return {
        "source": "feishu",
        "base_id": base_id,
        "table_id": table_id,
        "table_name": table_name,
        "record_count": len(normalized),
        "records": normalized,
        "fetched_at": datetime.now(tz=SHANGHAI_TZ).isoformat(),
    }
