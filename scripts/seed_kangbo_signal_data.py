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
        NEW_BASE_LINK,
        SEED_RESULT_FILE,
        TABLE_SPECS,
        load_table_ids,
        save_seed_result,
        seed_payload_paths,
        write_seed_payloads,
    )
    from scripts.create_kangbo_signal_tables import BRIDGE_SCRIPT, DEFAULT_ACCOUNT_ID, load_feishu_credentials
except ModuleNotFoundError:  # pragma: no cover - direct script execution path
    from r12_kangbo_signal_spec import (
        NEW_BASE_LINK,
        SEED_RESULT_FILE,
        TABLE_SPECS,
        load_table_ids,
        save_seed_result,
        seed_payload_paths,
        write_seed_payloads,
    )
    from create_kangbo_signal_tables import BRIDGE_SCRIPT, DEFAULT_ACCOUNT_ID, load_feishu_credentials


def run_bridge_upsert(
    *,
    link: str,
    table_id: str,
    primary_field: str,
    payload_file: Path,
    apply: bool,
    account_id: str = DEFAULT_ACCOUNT_ID,
) -> dict[str, Any]:
    if not BRIDGE_SCRIPT.exists():
        raise RuntimeError(f"bridge script not found: {BRIDGE_SCRIPT}")

    creds = load_feishu_credentials(account_id)
    env = dict(os.environ)
    env["FEISHU_APP_ID"] = creds["app_id"]
    env["FEISHU_APP_SECRET"] = creds["app_secret"]

    command = [
        sys.executable,
        str(BRIDGE_SCRIPT),
        "upsert-records",
        "--link",
        link,
        "--table-id",
        table_id,
        "--primary-field",
        primary_field,
        "--payload-file",
        str(payload_file),
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
        raise RuntimeError(payload_text or f"bridge upsert failed with exit code {completed.returncode}")
    return json.loads(payload_text)


def summarize_upsert_result(raw: dict[str, Any]) -> dict[str, Any]:
    summary = raw.get("summary") or {}
    preview = raw.get("preview") or {}
    result = raw.get("result") or {}

    if summary and not preview:
        preview = {
            "would_create": summary.get("creates"),
            "would_update": summary.get("updates"),
            "unchanged": summary.get("unchanged"),
            "errors": summary.get("errors"),
            "can_apply": summary.get("can_apply"),
        }
    if summary and not result and raw.get("mode") == "apply":
        result = {
            "created": summary.get("creates_applied", summary.get("creates")),
            "updated": summary.get("updates_applied", summary.get("updates")),
            "unchanged": summary.get("unchanged"),
            "errors": summary.get("errors"),
        }
    row_count = raw.get("row_count")
    if row_count is None and summary:
        row_count = sum(
            int(summary.get(key) or 0)
            for key in ("creates", "updates", "creates_applied", "updates_applied", "unchanged")
        )
    return {
        "row_count": row_count,
        "preview": preview or None,
        "result": result or None,
        "mode": raw.get("mode"),
        "status": raw.get("status"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the R12-V2 Kangbo signal demo data into Feishu.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    args = parser.parse_args()

    apply_changes = bool(args.apply)
    table_ids = load_table_ids()
    write_seed_payloads()

    payloads = seed_payload_paths()
    results: list[dict[str, Any]] = []
    for table in TABLE_SPECS:
        table_key = table["key"]
        raw_result = run_bridge_upsert(
            link=NEW_BASE_LINK,
            table_id=table_ids[table_key],
            primary_field=table["primary_field"],
            payload_file=payloads[table_key],
            apply=apply_changes,
            account_id=args.account_id,
        )
        result = summarize_upsert_result(raw_result)
        results.append(
            {
                "table_key": table_key,
                "table_name": table["table_name"],
                "table_id": table_ids[table_key],
                "primary_field": table["primary_field"],
                "row_count": result["row_count"],
                "preview": result["preview"],
                "result": result["result"],
                "mode": result["mode"],
                "status": result["status"],
                "output_path": raw_result.get("output_path"),
                "preview_path": raw_result.get("preview_path"),
            }
        )

    payload = {
        "mode": "apply" if apply_changes else "dry-run",
        "results": results,
    }
    save_seed_result(payload, SEED_RESULT_FILE)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
