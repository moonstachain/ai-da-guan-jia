from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from mcp_server_feishu.feishu_client import FeishuClient

try:
    from scripts.r12_kangbo_signal_spec import NEW_BASE_LINK, TARGET_APP_TOKEN
except ModuleNotFoundError:  # pragma: no cover - direct script execution path
    from r12_kangbo_signal_spec import NEW_BASE_LINK, TARGET_APP_TOKEN


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRIDGE_SCRIPT = Path.home() / ".codex" / "skills" / "feishu-bitable-bridge" / "scripts" / "feishu_bitable_bridge.py"


def feishu_credentials_present() -> bool:
    return bool(os.getenv("FEISHU_APP_ID", "").strip() and os.getenv("FEISHU_APP_SECRET", "").strip())


def inspect_table(table_id: str, *, limit: int = 10) -> dict[str, Any]:
    if feishu_credentials_present():
        return inspect_table_via_openapi(table_id)
    return inspect_table_via_bridge(table_id, limit=limit)


def inspect_table_via_openapi(table_id: str) -> dict[str, Any]:
    client = FeishuClient()
    if not client.available:
        raise RuntimeError("FEISHU_APP_ID / FEISHU_APP_SECRET are missing; cannot use OpenAPI path")

    tables_payload = client.list_bitable_tables(TARGET_APP_TOKEN)
    if tables_payload.get("error"):
        raise RuntimeError(f"list_bitable_tables failed: {tables_payload}")
    table_meta = next((item for item in tables_payload.get("tables", []) if item["table_id"] == table_id), None)
    if table_meta is None:
        raise RuntimeError(f"table_id {table_id} was not found in app {TARGET_APP_TOKEN}")

    records_payload = client.read_bitable_records(TARGET_APP_TOKEN, table_id, page_size=100)
    if records_payload.get("error"):
        raise RuntimeError(f"read_bitable_records failed: {records_payload}")

    raw_fields = client._request("GET", f"/bitable/v1/apps/{TARGET_APP_TOKEN}/tables/{table_id}/fields")
    if raw_fields.get("error"):
        raise RuntimeError(f"list fields failed: {raw_fields}")
    field_items = raw_fields.get("data", raw_fields).get("items") or []

    return {
        "base": {"obj_token": TARGET_APP_TOKEN},
        "table": {"table_id": table_id, "name": table_meta["name"], "record_count": len(records_payload.get("records", []))},
        "fields": [
            {"field_id": item.get("field_id", ""), "name": item.get("field_name") or item.get("name") or ""}
            for item in field_items
        ],
        "records": records_payload.get("records", []),
        "mode": "openapi",
    }


def inspect_table_via_bridge(table_id: str, *, limit: int = 10) -> dict[str, Any]:
    if not BRIDGE_SCRIPT.exists():
        raise RuntimeError(f"bridge script not found: {BRIDGE_SCRIPT}")
    command = [
        "python3",
        str(BRIDGE_SCRIPT),
        "inspect-link",
        "--link",
        NEW_BASE_LINK,
        "--table-id",
        table_id,
        "--limit",
        str(limit),
    ]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit={completed.returncode}"
        raise RuntimeError(f"bridge inspect failed: {detail}")
    return json.loads(completed.stdout)
