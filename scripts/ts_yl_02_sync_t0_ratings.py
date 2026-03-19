#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.relation_remap_apply import (
    DEFAULT_ACCOUNT_ID,
    DEFAULT_APP_TOKEN,
    api,
    fetch_tenant_access_token,
    list_fields,
    list_records,
    load_feishu_credentials,
    primary_field_name,
)

DEFAULT_MANIFEST = Path("/tmp/ts_yl_02_input/t9s-scores-manifest.json")
RUN_DIR = Path("/Users/liming/Documents/codex-ai-gua-jia-01/artifacts/ai-da-guan-jia/runs/2026-03-18/adagj-20260318-tsyl02-apply6")
T0_TABLE_ID = "tblqGqZjr5xrSdpe"
APP_TOKEN = DEFAULT_APP_TOKEN
TARGET_FIELDS = ["觉醒端评级", "现金流端评级", "三角闭环健康度", "最近更新日期"]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_manifest(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise ValueError("manifest must be a JSON object")
    return payload


def field_index(records: list[dict[str, Any]], primary_field: str) -> dict[str, str]:
    index: dict[str, str] = {}
    for record in records:
        fields = record.get("fields") or {}
        key = str(fields.get(primary_field) or "").strip()
        record_id = str(record.get("record_id") or "").strip()
        if key and record_id:
            index[key] = record_id
    return index


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync TS-YL-02 T0 rating fields from the score manifest.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--output-dir", default=str(RUN_DIR))
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    normalized_manifest_path = output_dir / f"{manifest_path.stem}.t0-sync.normalized.json"
    result_path = output_dir / f"{manifest_path.stem}.t0-sync.apply-result.json"
    write_json(normalized_manifest_path, load_manifest(manifest_path))

    manifest = load_manifest(manifest_path)
    t0_updates = list(manifest.get("t0_updates") or [])
    if not t0_updates:
        raise RuntimeError("manifest does not contain t0_updates")

    creds = load_feishu_credentials(args.account_id)
    token = fetch_tenant_access_token(creds["app_id"], creds["app_secret"])
    records = list_records(token, APP_TOKEN, T0_TABLE_ID)
    fields = list_fields(token, APP_TOKEN, T0_TABLE_ID)
    primary_field = primary_field_name(fields)
    record_ids = field_index(records, primary_field)

    previews: list[dict[str, Any]] = []
    updates: list[dict[str, Any]] = []
    for row in t0_updates:
        student_id = str(row.get("学员ID") or "").strip()
        record_id = record_ids.get(student_id)
        if not record_id:
            raise RuntimeError(f"missing T0 record for 学员ID={student_id}")
        payload = {k: v for k, v in row.items() if k != "学员ID"}
        previews.append({"学员ID": student_id, "record_id": record_id, "fields": payload})
        updates.append({"record_id": record_id, "fields": payload})

    if args.dry_run:
        preview = {
            "status": "preview_ready",
            "mode": "dry-run",
            "table_id": T0_TABLE_ID,
            "record_count": len(records),
            "updates": previews,
        }
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return 0

    for item in updates:
        api(token, "PUT", f"/bitable/v1/apps/{APP_TOKEN}/tables/{T0_TABLE_ID}/records/{item['record_id']}", body={"fields": item["fields"]})

    refreshed = list_records(token, APP_TOKEN, T0_TABLE_ID)
    by_student = {str((rec.get("fields") or {}).get("学员ID") or "").strip(): rec for rec in refreshed}
    verification: list[dict[str, Any]] = []
    for row in t0_updates:
        student_id = str(row.get("学员ID") or "").strip()
        current = (by_student.get(student_id) or {}).get("fields") or {}
        verification.append(
            {
                "学员ID": student_id,
                "觉醒端评级": current.get("觉醒端评级"),
                "现金流端评级": current.get("现金流端评级"),
                "三角闭环健康度": current.get("三角闭环健康度"),
                "最近更新日期": current.get("最近更新日期"),
            }
        )

    result = {
        "status": "applied",
        "mode": "apply",
        "table_id": T0_TABLE_ID,
        "record_count": len(refreshed),
        "updated_rows": len(updates),
        "updates": previews,
        "verification": verification,
        "target_fields": TARGET_FIELDS,
    }
    write_json(result_path, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
