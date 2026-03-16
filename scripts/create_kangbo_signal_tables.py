from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.r12_kangbo_signal_spec import (
        MANIFEST_FILE,
        NEW_BASE_LINK,
        TABLE_ID_MAP_FILE,
        TABLE_SPECS,
        TARGET_APP_TOKEN,
        save_table_ids,
        write_manifest_json,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution path
    from r12_kangbo_signal_spec import (
        MANIFEST_FILE,
        NEW_BASE_LINK,
        TABLE_ID_MAP_FILE,
        TABLE_SPECS,
        TARGET_APP_TOKEN,
        save_table_ids,
        write_manifest_json,
    )


BRIDGE_SCRIPT = Path.home() / ".codex" / "skills" / "feishu-bitable-bridge" / "scripts" / "feishu_bitable_bridge.py"
OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"
DEFAULT_ACCOUNT_ID = "feishu-claw"


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


def run_bridge_sync(*, manifest_path: Path, apply: bool, account_id: str = DEFAULT_ACCOUNT_ID) -> dict[str, Any]:
    if not BRIDGE_SCRIPT.exists():
        raise RuntimeError(f"bridge script not found: {BRIDGE_SCRIPT}")

    creds = load_feishu_credentials(account_id)
    env = dict(os.environ)
    env["FEISHU_APP_ID"] = creds["app_id"]
    env["FEISHU_APP_SECRET"] = creds["app_secret"]

    command = [
        sys.executable,
        str(BRIDGE_SCRIPT),
        "sync-base-schema",
        "--link",
        NEW_BASE_LINK,
        "--manifest",
        str(manifest_path),
        "--apply" if apply else "--dry-run",
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    payload_text = completed.stdout.strip() or completed.stderr.strip()
    if completed.returncode != 0:
        raise RuntimeError(payload_text or f"bridge sync failed with exit code {completed.returncode}")
    return json.loads(payload_text)


def extract_table_ids(result: dict[str, Any]) -> dict[str, str]:
    ids: dict[str, str] = {}
    tables = result.get("tables") or []
    for table in TABLE_SPECS:
        match = next((item for item in tables if item.get("table_name") == table["table_name"]), None)
        if not match:
            raise RuntimeError(f"table {table['table_name']} missing from bridge result")
        table_id = str(match.get("table_id") or "").strip()
        if not table_id:
            raise RuntimeError(f"table {table['table_name']} did not return a table_id")
        ids[table["key"]] = table_id
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the R12-V2 Kangbo signal tables in Feishu.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    args = parser.parse_args()

    manifest_path = write_manifest_json(MANIFEST_FILE)
    apply_changes = bool(args.apply)
    result = run_bridge_sync(manifest_path=manifest_path, apply=apply_changes, account_id=args.account_id)

    output: dict[str, Any] = {
        "status": result.get("status"),
        "mode": result.get("mode"),
        "target_app_token": TARGET_APP_TOKEN,
        "manifest_path": str(manifest_path),
        "table_id_file": str(TABLE_ID_MAP_FILE),
        "tables": result.get("tables") or [],
        "output_path": result.get("output_path"),
    }
    if apply_changes:
        table_ids = extract_table_ids(result)
        save_table_ids(table_ids)
        output["table_ids"] = table_ids

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
