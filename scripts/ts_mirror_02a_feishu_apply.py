#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.feishu_deploy import FeishuBitableAPI
from scripts.create_kangbo_signal_tables import DEFAULT_ACCOUNT_ID, load_feishu_credentials

APP_TOKEN = "IqZhbMJJxaq8D4sHOvkciaWFnid"
EVENT_TABLE_ID = "tbl5v57S6EUDFbNO"
MATRIX_TABLE_ID = "tbl7xvp71C22Nwog"
MIRROR_TABLE_ID = "tblbFFR8KqgJ88lE"

INPUT_DIR = Path("/tmp/ts-mirror-02a")
EVENTS_PATH = INPUT_DIR / "bw50-new-events.json"
MATRIX_PATH = INPUT_DIR / "bw50-new-matrix.json"
BACKFILL_PATH = INPUT_DIR / "mirror-backfill.json"

ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "ai-da-guan-jia" / "runs"


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_client(account_id: str) -> FeishuBitableAPI:
    creds = load_feishu_credentials(account_id)
    os.environ["FEISHU_APP_ID"] = creds["app_id"]
    os.environ["FEISHU_APP_SECRET"] = creds["app_secret"]
    return FeishuBitableAPI(creds["app_id"], creds["app_secret"])


def normalize_number(value: Any) -> int | float | str:
    if value in {"", None}:
        return ""
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    if not text:
        return ""
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return text


def is_blank(value: Any) -> bool:
    return value in ("", None, [])


def event_payloads(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for row in rows:
        payload = {
            "event_id": str(row.get("eventId") or "").strip(),
            "event_name": str(row.get("eventName") or "").strip(),
            "event_date": str(row.get("eventDate") or "").strip(),
            "end_date": "",
            "factor_type": str(row.get("factorType") or "").strip(),
            "severity": normalize_number(row.get("severity")),
            "summary": str(row.get("summary") or "").strip(),
            "causal_chain": "",
            "kangbo_phase": str(row.get("kangboPhase") or "").strip(),
            "related_kangbo_event_id": "",
        }
        payloads.append({k: v for k, v in payload.items() if not is_blank(v)})
    return payloads


def matrix_payloads(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for row in rows:
        payload = {
            "matrix_id": str(row.get("matrixId") or "").strip(),
            "event_id": str(row.get("eventId") or "").strip(),
            "asset_id": str(row.get("assetId") or "").strip(),
            "direction": str(row.get("direction") or "").strip(),
            "magnitude_pct": str(row.get("magnitudePct") or "").strip(),
            "peak_drawdown_pct": "",
            "recovery_months": "",
            "price_before": str(row.get("priceBefore") or "").strip(),
            "price_after": str(row.get("priceAfter") or "").strip(),
            "transmission_mechanism": str(row.get("transmissionMechanism") or "").strip(),
            "time_lag": str(row.get("timeLag") or "").strip(),
            "expert_commentary": str(row.get("expertCommentary") or "").strip(),
        }
        payloads.append({k: v for k, v in payload.items() if not is_blank(v)})
    return payloads


def record_index(records: list[dict[str, Any]], field_name: str) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for record in records:
        fields = record.get("fields") or {}
        key = str(fields.get(field_name) or "").strip()
        if key:
            index[key] = record
    return index


def count_nonempty(records: list[dict[str, Any]], field_name: str) -> int:
    count = 0
    for record in records:
        value = (record.get("fields") or {}).get(field_name)
        if not is_blank(value):
            count += 1
    return count


def upsert_named_rows(
    api: FeishuBitableAPI,
    *,
    app_token: str,
    table_id: str,
    primary_field: str,
    rows: list[dict[str, Any]],
    apply_changes: bool,
) -> dict[str, Any]:
    existing_records = api.list_records(app_token, table_id)
    existing = record_index(existing_records, primary_field)
    created_rows: list[dict[str, Any]] = []
    updated_rows: list[dict[str, Any]] = []
    for row in rows:
        primary_value = str(row.get(primary_field) or "").strip()
        if not primary_value:
            raise RuntimeError(f"missing primary field {primary_field}")
        current = existing.get(primary_value)
        if current and current.get("record_id"):
            updated_rows.append({"record_id": current["record_id"], "fields": row})
        else:
            created_rows.append({"fields": row})

    if apply_changes:
        for item in updated_rows:
            api._request(
                f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{item['record_id']}",
                method="PUT",
                payload={"fields": item["fields"]},
            )
        for chunk_start in range(0, len(created_rows), 500):
            chunk = created_rows[chunk_start : chunk_start + 500]
            if chunk:
                api.batch_create_records(app_token, table_id, [item["fields"] for item in chunk])

    refreshed = api.list_records(app_token, table_id)
    return {
        "table_id": table_id,
        "primary_field": primary_field,
        "existing_count": len(existing_records),
        "created_count": len(created_rows),
        "updated_count": len(updated_rows),
        "record_count": len(refreshed),
        "sample_records": [str((record.get("fields") or {}).get(primary_field) or "").strip() for record in refreshed[:3]],
    }


def backfill_mirror_links(
    api: FeishuBitableAPI,
    *,
    app_token: str,
    table_id: str,
    rows: list[dict[str, Any]],
    apply_changes: bool,
) -> dict[str, Any]:
    existing_records = api.list_records(app_token, table_id)
    by_mirror_id = record_index(existing_records, "mirror_id")
    before_linked = count_nonempty(existing_records, "linked_bw50_event_id")
    updates: list[dict[str, Any]] = []
    missing: list[str] = []
    for row in rows:
        mirror_id = str(row.get("mirror_id") or "").strip()
        linked_id = str(row.get("linked_bw50_event_id") or "").strip()
        if not mirror_id or not linked_id:
            continue
        current = by_mirror_id.get(mirror_id)
        if not current or not current.get("record_id"):
            missing.append(mirror_id)
            continue
        updates.append({"record_id": current["record_id"], "fields": {"linked_bw50_event_id": linked_id}})

    if missing:
        raise RuntimeError(f"Missing mirror rows for: {', '.join(missing)}")

    if apply_changes:
        for item in updates:
            api._request(
                f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{item['record_id']}",
                method="PUT",
                payload={"fields": item["fields"]},
            )

    refreshed = api.list_records(app_token, table_id)
    after_linked = count_nonempty(refreshed, "linked_bw50_event_id")
    verification = []
    refreshed_by_id = record_index(refreshed, "mirror_id")
    for row in rows:
        mirror_id = str(row.get("mirror_id") or "").strip()
        linked_id = str(row.get("linked_bw50_event_id") or "").strip()
        current = refreshed_by_id.get(mirror_id) or {}
        verification.append(
            {
                "mirror_id": mirror_id,
                "linked_bw50_event_id": (current.get("fields") or {}).get("linked_bw50_event_id"),
                "expected": linked_id,
            }
        )

    return {
        "table_id": table_id,
        "updated_count": len(updates),
        "linked_count_before": before_linked,
        "linked_count_after": after_linked,
        "record_count": len(refreshed),
        "sample_records": [item["mirror_id"] for item in rows[:3]],
        "verification": verification,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply TS-MIRROR-02A Feishu writes and mirror backfill.")
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--output-dir", default="")
    args = parser.parse_args()

    if not EVENTS_PATH.exists() or not MATRIX_PATH.exists() or not BACKFILL_PATH.exists():
        raise FileNotFoundError("Missing TS-MIRROR-02A source JSON files in /tmp/ts-mirror-02a")

    events = load_json(EVENTS_PATH)
    matrix = load_json(MATRIX_PATH)
    backfill = load_json(BACKFILL_PATH)
    if not isinstance(events, list) or not isinstance(matrix, list) or not isinstance(backfill, list):
        raise RuntimeError("Expected list JSON payloads for events, matrix, and backfill")

    artifact_dir = Path(args.output_dir).resolve() if args.output_dir else ARTIFACT_ROOT / datetime.now().strftime("%Y-%m-%d") / f"adagj-{now_stamp()}-ts-mirror-02a"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    write_json(artifact_dir / "input-events.normalized.json", events)
    write_json(artifact_dir / "input-matrix.normalized.json", matrix)
    write_json(artifact_dir / "input-backfill.normalized.json", backfill)

    creds = load_feishu_credentials(args.account_id)
    os.environ["FEISHU_APP_ID"] = creds["app_id"]
    os.environ["FEISHU_APP_SECRET"] = creds["app_secret"]
    api = FeishuBitableAPI(creds["app_id"], creds["app_secret"])

    event_rows = event_payloads(events)
    matrix_rows = matrix_payloads(matrix)

    event_result = upsert_named_rows(
        api,
        app_token=APP_TOKEN,
        table_id=EVENT_TABLE_ID,
        primary_field="event_id",
        rows=event_rows,
        apply_changes=args.apply,
    )
    matrix_result = upsert_named_rows(
        api,
        app_token=APP_TOKEN,
        table_id=MATRIX_TABLE_ID,
        primary_field="matrix_id",
        rows=matrix_rows,
        apply_changes=args.apply,
    )
    mirror_result = backfill_mirror_links(
        api,
        app_token=APP_TOKEN,
        table_id=MIRROR_TABLE_ID,
        rows=backfill,
        apply_changes=args.apply,
    )

    result = {
        "status": "applied" if args.apply else "dry-run",
        "app_token": APP_TOKEN,
        "phase1_bw50_events": event_result,
        "phase1_matrix": matrix_result,
        "phase1_mirror_backfill": mirror_result,
    }
    result_path = artifact_dir / "ts-mirror-02a-feishu-result.json"
    write_json(result_path, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
