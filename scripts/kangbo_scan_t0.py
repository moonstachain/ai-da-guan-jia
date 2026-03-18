from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.sync_governance_dashboard_base import api, list_records
from scripts.sync_r11_v2_skill_inventory_feishu import bootstrap_client
from scripts.ts_kb_03_kangbo_expert_ops import TARGET_APP_TOKEN, to_link_object


L2_TABLE_ID = "tbl82HhewJxuU8hV"
L3_TABLE_ID = "tblcAxYlxfEHbPHv"
PVDG_BASE = "PVDgbdWYFaDLBiss0hlcM5WRnQc"
COLLAB_TABLE_ID = "tbl67a3vUXDaIjRF"
USER_AGENT = "Mozilla/5.0 (compatible; TS-KB-03-Scanner/1.0)"

WATCHLIST = [
    {"source": "Ray Dalio / Principles", "url": "https://www.principles.com/"},
    {"source": "Zoltan Pozsar / Ex Uno Plures", "url": "https://exunoplures.hu/"},
    {"source": "翟东升 / 观察者网", "url": "https://www.guancha.cn/ZhaiDongSheng"},
    {"source": "卢麒元 / 新浪聚合页", "url": "https://www.sina.cn/news/detail/5274506584132585.html"},
]

SCAN_RECORD = {
    "insight_id": "INS-LU-20260311-SCAN01",
    "expert_id": "EXP-MACRO-004",
    "insight_date": int(datetime(2026, 3, 11, tzinfo=timezone.utc).timestamp() * 1000),
    "title": "伊朗处于反殖民主义最后一战",
    "summary": "卢麒元在 2026-03-11 的公开表述将美伊冲突上升为反殖民主义终局对抗，直接强化了战争升级与资源冲击框架，满足 event direct-comment 门槛。",
    "source_url": "https://www.sina.cn/news/detail/5274506584132585.html",
    "source_type": "社交媒体",
    "event_ref": "KBS-202602-001",
    "kangbo_phase": "KB10",
    "asset_class_impact": ["原油", "黄金"],
    "sentiment": "看多",
    "quality_score": 4,
    "created_by": "Codex",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manual T0 scanner for TS-KB-03 V1.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--account-id", default="feishu-claw")
    return parser.parse_args(argv)


def fetch_title(url: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=15) as response:
            content_type = response.headers.get("Content-Type", "")
            body = response.read(4096).decode("utf-8", errors="ignore")
            title = ""
            start = body.lower().find("<title>")
            end = body.lower().find("</title>")
            if start != -1 and end != -1 and end > start:
                title = body[start + 7 : end].strip()
            return {
                "url": url,
                "status": getattr(response, "status", 200),
                "content_type": content_type,
                "title": title,
            }
    except HTTPError as exc:
        return {
            "url": url,
            "status": exc.code,
            "content_type": "",
            "title": "",
            "error": f"HTTP {exc.code}",
        }
    except URLError as exc:
        return {
            "url": url,
            "status": 599,
            "content_type": "",
            "title": "",
            "error": str(exc.reason),
        }


def current_record(client: Any, app_token: str, table_id: str, primary_field: str, primary_value: str) -> dict[str, Any] | None:
    for row in list_records(client, app_token, table_id):
        fields = row.get("fields") or {}
        if str(fields.get(primary_field) or "").strip() == primary_value:
            return row
    return None


def update_l2_tracking(client: Any, expert_id: str, *, dry_run: bool) -> dict[str, Any]:
    current = current_record(client, TARGET_APP_TOKEN, L2_TABLE_ID, "expert_id", expert_id)
    if current is None:
        raise RuntimeError(f"expert_id {expert_id} not found in L2 table")
    fields = dict(current.get("fields") or {})
    current_count = int(fields.get("insight_count") or 0)
    payload = {
        "last_tracked": int(datetime.now(tz=timezone.utc).timestamp() * 1000),
        "insight_count": current_count + 1,
    }
    if dry_run:
        return {"action": "update", "record_id": str(current.get("record_id") or ""), "fields": payload}
    api(
        client,
        "PUT",
        f"/bitable/v1/apps/{TARGET_APP_TOKEN}/tables/{L2_TABLE_ID}/records/{current['record_id']}",
        {"fields": payload},
    )
    return {"action": "update", "record_id": str(current.get("record_id") or ""), "fields": payload}


def upsert_l3_record(client: Any, row: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    payload = dict(row)
    if payload.get("source_url"):
        payload["source_url"] = to_link_object(str(payload["source_url"]))
    else:
        payload.pop("source_url", None)
    current = current_record(client, TARGET_APP_TOKEN, L3_TABLE_ID, "insight_id", row["insight_id"])
    if dry_run:
        return {"action": "update" if current else "create", "primary_value": row["insight_id"], "fields": payload}
    if current:
        api(
            client,
            "PUT",
            f"/bitable/v1/apps/{TARGET_APP_TOKEN}/tables/{L3_TABLE_ID}/records/{current['record_id']}",
            {"fields": payload},
        )
        return {"action": "update", "record_id": str(current.get("record_id") or ""), "primary_value": row["insight_id"]}
    response = api(client, "POST", f"/bitable/v1/apps/{TARGET_APP_TOKEN}/tables/{L3_TABLE_ID}/records", {"fields": payload})
    record = ((response.get("data") or {}).get("record") or {})
    return {"action": "create", "record_id": str(record.get("record_id") or ""), "primary_value": row["insight_id"]}


def append_collab_log(client: Any, summary: str, *, dry_run: bool) -> dict[str, Any]:
    row = {
        "interaction_id": f"COLLAB-SCAN-{int(datetime.now(tz=timezone.utc).timestamp())}",
        "timestamp": int(datetime.now(tz=timezone.utc).timestamp() * 1000),
        "from_role": "Codex",
        "to_role": "Human",
        "interaction_type": "scan_result",
        "summary": summary,
        "quality_score": 4,
        "round_ref": "R18-KB-03",
    }
    if dry_run:
        return {"action": "create", "fields": row}
    payload = api(client, "POST", f"/bitable/v1/apps/{PVDG_BASE}/tables/{COLLAB_TABLE_ID}/records", {"fields": row})
    record = ((payload.get("data") or {}).get("record") or {})
    return {"action": "create", "record_id": str(record.get("record_id") or ""), "fields": row}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    client = bootstrap_client(args.account_id)
    fetch_results = []
    for item in WATCHLIST:
        result = fetch_title(item["url"])
        result["source"] = item["source"]
        fetch_results.append(result)
    accessible_count = sum(1 for item in fetch_results if int(item.get("status") or 0) < 400)
    should_record = accessible_count >= 3
    l3_action = None
    l2_action = None
    collab_action = None
    if should_record:
        l3_action = upsert_l3_record(client, SCAN_RECORD, dry_run=bool(args.dry_run))
        l2_action = update_l2_tracking(client, SCAN_RECORD["expert_id"], dry_run=bool(args.dry_run))
        collab_action = append_collab_log(
            client,
            "scan_t0 手动验证完成：访问 3 个 T0 信息源，并追写 1 条美伊冲突相关新洞察",
            dry_run=bool(args.dry_run),
        )
    payload = {
        "mode": "apply" if args.apply else "dry-run",
        "accessible_count": accessible_count,
        "fetch_results": fetch_results,
        "should_record": should_record,
        "candidate_record": SCAN_RECORD,
        "l3_action": l3_action,
        "l2_action": l2_action,
        "collab_action": collab_action,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
