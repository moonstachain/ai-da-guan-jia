#!/usr/bin/env python3
"""Shared helpers for PROJ-V2-CLONE-03 activation / feedback / dogfood."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.feishu_deploy import FeishuBitableAPI  # noqa: E402
from scripts.create_kangbo_signal_tables import DEFAULT_ACCOUNT_ID, load_feishu_credentials  # noqa: E402


INSTANCE_ID = "longxia"
CLONE_ROOT = REPO_ROOT / "artifacts" / "ai-da-guan-jia" / "clones"
CURRENT_ROOT = CLONE_ROOT / "current"
INSTANCE_ROOT = CLONE_ROOT / "instances" / INSTANCE_ID
FEEDBACK_INBOX_ROOT = CURRENT_ROOT / "feedback-inbox"
TASK_TRACKER_APP = "PVDgbdWYFaDLBiss0hlcM5WRnQc"
TASK_TRACKER_TABLE = "tblB9JQ4cROTBUnr"
TASK_TRACKER_NAME = "COO_Task_Tracker"
COLLAB_TABLE_NAME = "COO_Collab_Log"
EVOLUTION_TABLE_NAME = "COO_Evolution_Log"
TASK_TRACKER_RECORD_ID = "PROJ-V2-CLONE-03"


@dataclass(frozen=True)
class FeedbackSource:
    path: Path
    rel_path: str
    mtime: datetime
    sha1: str
    size: int
    text: str


def now_local() -> datetime:
    return datetime.now().astimezone()


def local_date() -> str:
    return now_local().date().isoformat()


def epoch_seconds(value: datetime | str | int | float | None) -> int | str:
    if value in {None, ""}:
        return ""
    if isinstance(value, (int, float)):
        integer = int(value)
        return integer // 1000 if abs(integer) >= 10**12 else integer
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return ""
        if text.isdigit():
            integer = int(text)
            return integer // 1000 if abs(integer) >= 10**12 else integer
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return text
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp_path.replace(path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def load_table_registry(instance_id: str = INSTANCE_ID) -> dict[str, Any]:
    path = CLONE_ROOT / "instances" / instance_id / "feishu-bridge" / "table-registry.json"
    payload = read_json(path, default={})
    return payload if isinstance(payload, dict) else {}


def load_feishu_api(account_id: str = DEFAULT_ACCOUNT_ID) -> FeishuBitableAPI:
    creds = load_feishu_credentials(account_id)
    return FeishuBitableAPI(creds["app_id"], creds["app_secret"])


def table_meta(instance_id: str, table_name: str) -> dict[str, Any]:
    registry = load_table_registry(instance_id)
    tables = registry.get("tables") or {}
    table = tables.get(table_name)
    if not isinstance(table, dict):
        raise RuntimeError(f"Missing {table_name} in table-registry.json for {instance_id}")
    table_id = str(table.get("table_id") or "").strip()
    primary_field = str(table.get("primary_field") or "").strip()
    if not table_id or not primary_field:
        raise RuntimeError(f"Incomplete table registry for {table_name}: table_id={table_id!r}, primary_field={primary_field!r}")
    return {
        "base_app_token": str(registry.get("base_app_token") or "").strip(),
        "base_link": str(registry.get("feishu_link") or "").strip(),
        "table_id": table_id,
        "primary_field": primary_field,
        "field_ids": table.get("field_ids") or {},
        "purpose": str(table.get("purpose") or "").strip(),
    }


def instance_paths(instance_id: str = INSTANCE_ID) -> dict[str, Path]:
    instance_root = CLONE_ROOT / "instances" / instance_id
    return {
        "instance_root": instance_root,
        "clone_state_dir": instance_root / "clone-state",
        "feedback_dir": instance_root / "feedback",
        "feishu_bridge_dir": instance_root / "feishu-bridge",
        "feedback_inbox_dir": FEEDBACK_INBOX_ROOT,
    }


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_feedback_sources(instance_id: str = INSTANCE_ID) -> list[FeedbackSource]:
    paths = instance_paths(instance_id)
    feedback_dir = paths["feedback_dir"]
    if not feedback_dir.exists():
        return []
    sources: list[FeedbackSource] = []
    for item in sorted(feedback_dir.rglob("*")):
        if not item.is_file() or item.name.startswith("."):
            continue
        try:
            text = item.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            continue
        sources.append(
            FeedbackSource(
                path=item,
                rel_path=str(item.relative_to(feedback_dir)),
                mtime=datetime.fromtimestamp(item.stat().st_mtime, tz=timezone.utc),
                sha1=hashlib.sha1(text.encode("utf-8")).hexdigest(),
                size=item.stat().st_size,
                text=text,
            )
        )
    return sources


def _clean_excerpt(text: str, limit: int = 180) -> str:
    compact = " ".join(line.strip() for line in text.splitlines() if line.strip())
    return compact[:limit] + ("…" if len(compact) > limit else "")


def summarize_feedback_sources(sources: list[FeedbackSource]) -> dict[str, list[str]]:
    completed: list[str] = []
    lessons: list[str] = []
    proposals: list[str] = []
    raw_notes: list[str] = []

    for source in sources:
        raw_notes.append(f"{source.rel_path}: {_clean_excerpt(source.text)}")
        for line in source.text.splitlines():
            text = line.strip()
            if not text:
                continue
            lower = text.lower()
            if any(marker in lower for marker in ("lesson", "learned", "复盘", "经验", "启发", "坑")) or "下一步" in text:
                lessons.append(text.lstrip("-*1234567890. ）"))
            if any(marker in lower for marker in ("proposal", "capability", "能力", "建议", "提案", "升级")):
                proposals.append(text.lstrip("-*1234567890. ）"))
            if any(marker in lower for marker in ("完成", "done", "completed", "closed", "已交付", "已完成")):
                completed.append(text.lstrip("-*1234567890. ）"))

    def dedupe(items: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            normalized = item.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result

    return {
        "completed": dedupe(completed),
        "lessons": dedupe(lessons),
        "proposals": dedupe(proposals),
        "raw_notes": dedupe(raw_notes),
    }


def render_feedback_digest(instance_id: str, sources: list[FeedbackSource], summary: dict[str, list[str]]) -> str:
    today = local_date()
    lines = [
        f"# {instance_id} feedback digest",
        "",
        f"- date: {today}",
        f"- instance_id: {instance_id}",
        f"- source_count: {len(sources)}",
        "",
    ]
    if not sources:
        lines.extend(
            [
                "## Snapshot",
                "",
                "- No feedback files were present in the instance feedback directory.",
                "- This is still a valid heartbeat digest for the first activation loop.",
                "",
            ]
        )
    else:
        lines.extend(["## Sources", ""])
        for source in sources:
            lines.append(f"- `{source.rel_path}` · mtime={source.mtime.astimezone().isoformat()} · sha1={source.sha1[:8]} · size={source.size}")
        lines.extend(["", "## Completed", ""])
        lines.extend([f"- {item}" for item in summary["completed"]] or ["- none"])
        lines.extend(["", "## Lessons Learned", ""])
        lines.extend([f"- {item}" for item in summary["lessons"]] or ["- none"])
        lines.extend(["", "## Capability Proposals", ""])
        lines.extend([f"- {item}" for item in summary["proposals"]] or ["- none"])
        lines.extend(["", "## Raw Notes", ""])
        lines.extend([f"- {item}" for item in summary["raw_notes"]] or ["- none"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def find_record_by_primary(records: list[dict[str, Any]], primary_field: str, primary_value: str) -> dict[str, Any] | None:
    needle = str(primary_value or "").strip()
    for record in records:
        fields = record.get("fields") or {}
        if str(fields.get(primary_field) or "").strip() == needle:
            return record
    return None


def upsert_record_by_primary(
    api: FeishuBitableAPI,
    *,
    app_token: str,
    table_id: str,
    primary_field: str,
    record: dict[str, Any],
) -> dict[str, Any]:
    primary_value = str(record.get(primary_field) or "").strip()
    if not primary_value:
        raise RuntimeError(f"missing primary field {primary_field}")
    records = api.list_records(app_token, table_id)
    current = find_record_by_primary(records, primary_field, primary_value)
    if current and str(current.get("record_id") or "").strip():
        current_fields = current.get("fields") or {}
        if current_fields != record:
            api.batch_update_records(
                app_token,
                table_id,
                [{"record_id": str(current.get("record_id") or "").strip(), "fields": record}],
            )
            action = "updated"
        else:
            action = "noop"
        return {
            "action": action,
            "record_id": str(current.get("record_id") or "").strip(),
            "fields": current_fields,
        }

    api.batch_create_records(app_token, table_id, [record])
    refreshed = api.list_records(app_token, table_id)
    created = find_record_by_primary(refreshed, primary_field, primary_value)
    return {
        "action": "created",
        "record_id": str(created.get("record_id") or "").strip() if created else "",
        "fields": record,
    }


def stable_log_id(prefix: str, date: str, suffix: str) -> str:
    return f"{prefix}-{date}-{suffix}".replace(" ", "-")
