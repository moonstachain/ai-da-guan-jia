#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp_server_feishu.feishu_client import FeishuClient


DATA_PATH = PROJECT_ROOT / "data" / "skill_inventory.json"
OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"
DEFAULT_ACCOUNT_ID = "feishu-claw"
TARGET_APP_TOKEN = "PVDgbdWYFaDLBiss0hlcM5WRnQc"
TABLE_NAME = "Skill全景盘点表"
TEXT_FIELD = 1

FIELD_NAMES = [
    "skill_id",
    "skill_name",
    "source_repo",
    "file_path",
    "source_type",
    "description",
    "trigger_keywords",
    "dependencies",
    "last_updated",
    "status",
    "category",
    "quadrant",
    "action_recommendation",
]


def load_feishu_credentials(account_id: str = DEFAULT_ACCOUNT_ID) -> dict[str, str]:
    if os.getenv("FEISHU_APP_ID") and os.getenv("FEISHU_APP_SECRET"):
        return {
            "app_id": os.environ["FEISHU_APP_ID"],
            "app_secret": os.environ["FEISHU_APP_SECRET"],
        }

    if OPENCLAW_CONFIG.exists():
        config = json.loads(OPENCLAW_CONFIG.read_text(encoding="utf-8"))
        accounts = (((config.get("channels") or {}).get("feishu") or {}).get("accounts") or {})
        account = accounts.get(account_id) or {}
        app_id = str(account.get("appId") or "").strip()
        app_secret = str(account.get("appSecret") or "").strip()
        if app_id and app_secret:
            return {"app_id": app_id, "app_secret": app_secret}

    raise RuntimeError("Missing Feishu credentials in FEISHU_APP_ID/FEISHU_APP_SECRET and ~/.openclaw/openclaw.json")


def bootstrap_client(account_id: str = DEFAULT_ACCOUNT_ID) -> FeishuClient:
    creds = load_feishu_credentials(account_id)
    os.environ["FEISHU_APP_ID"] = creds["app_id"]
    os.environ["FEISHU_APP_SECRET"] = creds["app_secret"]
    client = FeishuClient()
    if not client.available:
        raise RuntimeError("Feishu client unavailable after credential bootstrap")
    return client


def api(
    client: FeishuClient,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    *,
    query: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request_path = path
    if query:
        request_path = f"{path}?{urlencode(query)}"
    payload = client._request(method, request_path, body)
    if "error" in payload:
        raise RuntimeError(str(payload["error"]))
    code = payload.get("code", 0)
    if code not in (0, "0", None):
        raise RuntimeError(str(payload.get("msg") or payload.get("error") or f"Feishu API error {code}"))
    return payload


def list_tables(client: FeishuClient, app_token: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page_token = ""
    while True:
        query = {"page_size": 100}
        if page_token:
            query["page_token"] = page_token
        payload = api(client, "GET", f"/bitable/v1/apps/{app_token}/tables", query=query)
        data = payload.get("data", {}) or {}
        items.extend(list(data.get("items", []) or []))
        if not data.get("has_more"):
            break
        page_token = str(data.get("page_token") or "").strip()
        if not page_token:
            break
    return items


def list_fields(client: FeishuClient, app_token: str, table_id: str) -> list[dict[str, Any]]:
    return list(
        (api(client, "GET", f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields", query={"page_size": 500}).get("data", {}) or {}).get("items", [])
        or []
    )


def list_records(client: FeishuClient, app_token: str, table_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page_token = ""
    while True:
        query = {"page_size": 500}
        if page_token:
            query["page_token"] = page_token
        payload = api(client, "GET", f"/bitable/v1/apps/{app_token}/tables/{table_id}/records", query=query)
        data = payload.get("data", {}) or {}
        items.extend(list(data.get("items", []) or []))
        if not data.get("has_more"):
            break
        page_token = str(data.get("page_token") or "").strip()
        if not page_token:
            break
    return items


def ensure_table(client: FeishuClient, app_token: str) -> str:
    for table in list_tables(client, app_token):
        if str(table.get("name") or "").strip() == TABLE_NAME:
            table_id = str(table.get("table_id") or "").strip()
            ensure_fields(client, app_token, table_id)
            return table_id

    created = api(client, "POST", f"/bitable/v1/apps/{app_token}/tables", {"table": {"name": TABLE_NAME}})
    table_id = str((((created.get("data") or {}).get("table") or {}).get("table_id")) or "")
    if not table_id:
        raise RuntimeError("Failed to create Skill全景盘点表")
    ensure_fields(client, app_token, table_id)
    return table_id


def ensure_fields(client: FeishuClient, app_token: str, table_id: str) -> None:
    fields = list_fields(client, app_token, table_id)
    primary = next((field for field in fields if field.get("is_primary")), fields[0] if fields else None)
    if primary is not None and str(primary.get("field_name") or "").strip() != "skill_id":
        api(
            client,
            "PUT",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{primary['field_id']}",
            {"field_name": "skill_id", "type": TEXT_FIELD},
        )
        fields = list_fields(client, app_token, table_id)

    names = {str(field.get("field_name") or "").strip() for field in fields}
    for field_name in FIELD_NAMES[1:]:
        if field_name in names:
            continue
        api(
            client,
            "POST",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
            {"field_name": field_name, "type": TEXT_FIELD},
        )


def normalize_skill_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "skill_id": str(item.get("skill_id") or ""),
        "skill_name": str(item.get("skill_name") or ""),
        "source_repo": str(item.get("source_repo") or ""),
        "file_path": str(item.get("file_path") or ""),
        "source_type": str(item.get("source_type") or ""),
        "description": str(item.get("description") or ""),
        "trigger_keywords": " | ".join(item.get("trigger_keywords") or []),
        "dependencies": " | ".join(item.get("dependencies") or []),
        "last_updated": str(item.get("last_updated") or ""),
        "status": str(item.get("status") or ""),
        "category": str(item.get("category") or ""),
        "quadrant": str(item.get("quadrant") or ""),
        "action_recommendation": str(item.get("action_recommendation") or ""),
    }


def chunked(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def sync_records(client: FeishuClient, app_token: str, table_id: str, rows: list[dict[str, Any]]) -> dict[str, int]:
    existing = list_records(client, app_token, table_id)
    by_skill_id = {
        str((item.get("fields") or {}).get("skill_id") or "").strip(): str(item.get("record_id") or "").strip()
        for item in existing
    }
    to_create: list[dict[str, Any]] = []
    to_update: list[dict[str, Any]] = []

    for row in rows:
        record_id = by_skill_id.get(row["skill_id"])
        if record_id:
            to_update.append({"record_id": record_id, "fields": row})
        else:
            to_create.append({"fields": row})

    for batch in chunked(to_create, 500):
        api(
            client,
            "POST",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
            {"records": batch},
        )
    for batch in chunked(to_update, 500):
        api(
            client,
            "POST",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_update",
            {"records": batch},
        )
    return {"created": len(to_create), "updated": len(to_update)}


def main() -> int:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    rows = [normalize_skill_row(item) for item in payload.get("skills", [])]
    client = bootstrap_client()
    table_id = ensure_table(client, TARGET_APP_TOKEN)
    result = sync_records(client, TARGET_APP_TOKEN, table_id, rows)
    readback = list_records(client, TARGET_APP_TOKEN, table_id)
    output = {
        "app_token": TARGET_APP_TOKEN,
        "table_name": TABLE_NAME,
        "table_id": table_id,
        "inventory_count": len(rows),
        "created": result["created"],
        "updated": result["updated"],
        "readback_count": len(readback),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
