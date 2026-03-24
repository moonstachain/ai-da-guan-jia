#!/usr/bin/env python3
"""Local-first clone health probe (TS-V2 PHASE0 D3).

This script scans a clone-local root and updates:
1) clone-state/clone-scorecard.json
2) .health/heartbeat.json
3) clone-state/alerts-decisions.json (append on anomalies)

It only uses the Python standard library and keeps Feishu-independent
behavior on the default path. Optional webhook push is supported.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib import error, request


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DIMENSION_KEYS = [
    "D1_strategy_alignment",
    "D2_execution_quality",
    "D3_closure_rate",
    "D4_workflow_reuse",
    "D5_feedback_quality",
    "D6_autonomy_level",
    "D7_drift_frequency",
    "D8_skill_utilization",
    "D9_human_boundary_respect",
    "D10_evolution_contribution",
]


@dataclass
class ProbeState:
    assumptions: list[str]
    errors: list[str]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def resolve_repo_root() -> Path:
    try:
        return Path(__file__).resolve().parents[3]
    except IndexError:
        return Path.cwd()


def clone_scorecard_aggregate_path() -> Path:
    return resolve_repo_root() / "artifacts" / "ai-da-guan-jia" / "clones" / "current" / "clone-scorecard-aggregate.json"


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path, default: Any, state: ProbeState) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:  # noqa: BLE001
        state.errors.append(f"failed to read json {path}: {exc}")
        return default


def write_json_atomic(path: Path, payload: Any, dry_run: bool) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        tmp_path.replace(path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def to_local_date(dt: datetime) -> str:
    return dt.astimezone().date().isoformat()


def parse_datetime_candidate(value: str) -> datetime | None:
    candidate = (value or "").strip()
    if not candidate:
        return None
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def extract_status_tokens(obj: Any) -> list[str]:
    tokens: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_l = str(key).lower()
            if key_l in {"status", "result", "outcome", "state", "final_status"} and isinstance(value, str):
                tokens.append(value.lower())
            else:
                tokens.extend(extract_status_tokens(value))
    elif isinstance(obj, list):
        for item in obj:
            tokens.extend(extract_status_tokens(item))
    return tokens


def classify_run_status(run_unit: Path, state: ProbeState) -> str:
    candidates: list[Path] = []
    if run_unit.is_dir():
        for file_name in ("route.json", "evolution.json", "worklog.json", "status.json", "summary.json"):
            file_path = run_unit / file_name
            if file_path.exists():
                candidates.append(file_path)
    elif run_unit.is_file() and run_unit.suffix.lower() == ".json":
        candidates.append(run_unit)

    tokens: list[str] = []
    for candidate in candidates:
        payload = read_json(candidate, default={}, state=state)
        tokens.extend(extract_status_tokens(payload))

    text = " ".join(tokens)
    if any(marker in text for marker in ("fail", "error", "abort", "timeout", "cancel")):
        return "failed"
    if any(marker in text for marker in ("success", "completed", "done", "ok", "pass")):
        return "completed"
    return "completed"


def most_recent_mtime(path: Path) -> datetime | None:
    if path.is_file():
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    if not path.exists():
        return None
    latest = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    for child in path.rglob("*"):
        try:
            child_m = datetime.fromtimestamp(child.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if child_m > latest:
            latest = child_m
    return latest


def scan_runs(runs_dir: Path, state: ProbeState) -> dict[str, Any]:
    today = datetime.now().astimezone().date()
    completed_by_day: dict[str, int] = {}
    failed_today = 0
    completed_today = 0
    sessions_today = 0
    last_active: datetime | None = None
    has_history = False

    if not runs_dir.exists():
        state.assumptions.append(f"{runs_dir} missing; treat as no run history")
        return {
            "tasks_completed_today": 0,
            "tasks_failed_today": 0,
            "sessions_today": 0,
            "completed_by_day": completed_by_day,
            "last_active_session": None,
            "has_run_history": False,
        }

    date_dirs = [p for p in runs_dir.iterdir() if p.is_dir() and DATE_RE.match(p.name)]
    if date_dirs:
        units: list[tuple[Path, datetime, str]] = []
        for date_dir in sorted(date_dirs):
            for unit in sorted(date_dir.iterdir()):
                run_time = most_recent_mtime(unit) or datetime.fromtimestamp(date_dir.stat().st_mtime, tz=timezone.utc)
                units.append((unit, run_time, date_dir.name))
    else:
        units = []
        for unit in sorted(runs_dir.iterdir()):
            run_time = most_recent_mtime(unit) or datetime.fromtimestamp(unit.stat().st_mtime, tz=timezone.utc)
            units.append((unit, run_time, to_local_date(run_time)))

    for unit, run_time, run_day in units:
        has_history = True
        status = classify_run_status(unit, state)
        if last_active is None or run_time > last_active:
            last_active = run_time

        if run_day not in completed_by_day:
            completed_by_day[run_day] = 0
        if status == "completed":
            completed_by_day[run_day] += 1

        if run_time.astimezone().date() == today:
            sessions_today += 1
            if status == "failed":
                failed_today += 1
            else:
                completed_today += 1

    return {
        "tasks_completed_today": completed_today,
        "tasks_failed_today": failed_today,
        "sessions_today": sessions_today,
        "completed_by_day": completed_by_day,
        "last_active_session": iso_utc(last_active) if last_active else None,
        "has_run_history": has_history,
    }


def parse_governance_dashboard(path: Path, state: ProbeState) -> dict[str, Any]:
    if not path.exists():
        state.assumptions.append(f"{path} missing; governance maturity defaults to 0")
        return {"governance_maturity": 0, "stale_hours": None, "updated_at": None}

    text = ""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        state.errors.append(f"failed to read governance dashboard {path}: {exc}")

    maturity = 0
    patterns = [
        r"governance[_\s-]?maturity\s*[:=]\s*(\d+)",
        r"治理成熟度[^\d]{0,8}(\d+)",
        r"\bmaturity\s*[:=]\s*(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            maturity = int(match.group(1))
            break
    if maturity == 0 and text:
        maybe_number = re.search(r"\b([0-4]?\d)\b", text)
        if maybe_number:
            maturity = int(maybe_number.group(1))

    updated_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    stale_hours = (now_utc() - updated_at).total_seconds() / 3600.0
    return {
        "governance_maturity": maturity,
        "stale_hours": stale_hours,
        "updated_at": iso_utc(updated_at),
    }


def scan_feedback(feedback_dir: Path, state: ProbeState) -> dict[str, Any]:
    if not feedback_dir.exists():
        state.assumptions.append(f"{feedback_dir} missing; feedback_pending defaults to 0")
        return {"feedback_pending": 0, "codex_proposals_today": 0, "last_feedback_activity": None}

    pending = 0
    proposals_today = 0
    latest: datetime | None = None
    today = datetime.now().astimezone().date()

    for item in feedback_dir.rglob("*"):
        if not item.is_file():
            continue
        pending += 1
        item_time = datetime.fromtimestamp(item.stat().st_mtime, tz=timezone.utc)
        if latest is None or item_time > latest:
            latest = item_time
        if item_time.astimezone().date() == today and "proposal" in item.name.lower():
            proposals_today += 1

    return {
        "feedback_pending": pending,
        "codex_proposals_today": proposals_today,
        "last_feedback_activity": iso_utc(latest) if latest else None,
    }


def clamp_dimension(value: int) -> int:
    return max(0, min(4, int(value)))


def map_ratio_to_dimension(value: float | None) -> int:
    if value is None:
        return 0
    return clamp_dimension(round(value * 4))


def compute_skill_utilization(tasks_completed_today: int, sessions_today: int, proposals_today: int) -> int:
    signal = tasks_completed_today + proposals_today + (1 if sessions_today > 0 else 0)
    ratio = min(1.0, signal / 4.0)
    return map_ratio_to_dimension(ratio)


def normalize_dimensions(payload: dict[str, Any]) -> dict[str, int]:
    normalized: dict[str, int] = {}
    source = payload if isinstance(payload, dict) else {}
    for key in DIMENSION_KEYS:
        normalized[key] = clamp_dimension(int(source.get(key, 0))) if str(source.get(key, "0")).isdigit() else 0
    return normalized


def update_scorecard(
    scorecard_path: Path,
    clone_id: str,
    tasks_completed_today: int,
    tasks_failed_today: int,
    sessions_today: int,
    codex_proposals_today: int,
    state: ProbeState,
    dry_run: bool,
) -> tuple[dict[str, Any], float | None]:
    today = datetime.now().astimezone().date().isoformat()
    payload = read_json(scorecard_path, default=None, state=state)

    if tasks_completed_today + tasks_failed_today > 0:
        closure_ratio = tasks_completed_today / (tasks_completed_today + tasks_failed_today)
    else:
        closure_ratio = None

    d3_value = map_ratio_to_dimension(closure_ratio)
    d8_value = compute_skill_utilization(tasks_completed_today, sessions_today, codex_proposals_today)

    def build_from_object(obj: dict[str, Any]) -> dict[str, Any]:
        scorecard_obj = dict(obj)
        scorecard_obj["clone_id"] = str(scorecard_obj.get("clone_id") or clone_id)
        scorecard_obj["period"] = today
        dimensions = normalize_dimensions(scorecard_obj.get("dimensions", {}))
        dimensions["D3_closure_rate"] = d3_value
        dimensions["D8_skill_utilization"] = d8_value
        scorecard_obj["dimensions"] = dimensions
        scorecard_obj["total"] = sum(dimensions.values())
        scorecard_obj["trend"] = scorecard_obj.get("trend") or "new"
        if not isinstance(scorecard_obj.get("top_pain_points"), list):
            scorecard_obj["top_pain_points"] = []
        if not isinstance(scorecard_obj.get("skill_usage"), dict):
            scorecard_obj["skill_usage"] = {}
        scorecard_obj["skill_usage"]["codex_proposals_today"] = int(codex_proposals_today)
        return scorecard_obj

    if isinstance(payload, dict):
        updated_payload = build_from_object(payload)
    elif isinstance(payload, list):
        updated_list = list(payload)
        if updated_list and isinstance(updated_list[-1], dict) and str(updated_list[-1].get("period", "")) == today:
            updated_list[-1] = build_from_object(updated_list[-1])
        else:
            updated_list.append(build_from_object({}))
        updated_payload = updated_list
    else:
        updated_payload = build_from_object({})
        if payload not in (None, {}, []):
            state.errors.append(f"unexpected scorecard shape at {scorecard_path}, replaced with default object")

    write_json_atomic(scorecard_path, updated_payload, dry_run=dry_run)
    scorecard_obj = updated_payload[-1] if isinstance(updated_payload, list) else updated_payload
    return scorecard_obj, closure_ratio


def load_alerts(alert_path: Path, state: ProbeState) -> tuple[list[dict[str, Any]], str]:
    payload = read_json(alert_path, default=None, state=state)
    if isinstance(payload, dict):
        alerts = payload.get("alerts")
        if isinstance(alerts, list):
            return [a for a in alerts if isinstance(a, dict)], "object"
        state.errors.append(f"{alert_path} missing alerts array; reset to empty")
        return [], "object"
    if isinstance(payload, list):
        return [a for a in payload if isinstance(a, dict)], "list"
    if payload is None:
        return [], "object"
    state.errors.append(f"unexpected alerts shape at {alert_path}; reset to schema object")
    return [], "object"


def next_alert_id(existing_alerts: list[dict[str, Any]]) -> str:
    max_n = 0
    for alert in existing_alerts:
        alert_id = str(alert.get("alert_id", ""))
        match = re.match(r"^ALT-(\d+)$", alert_id)
        if match:
            max_n = max(max_n, int(match.group(1)))
    return f"ALT-{max_n + 1}"


def build_new_alerts(
    clone_id: str,
    closure_ratio: float | None,
    governance_stale_hours: float | None,
    completed_by_day: dict[str, int],
    has_run_history: bool,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    now = iso_utc(now_utc())

    if governance_stale_hours is not None and governance_stale_hours > 72:
        items.append(
            {
                "clone_id": clone_id,
                "type": "drift",
                "severity": "warning",
                "message": f"governance-dashboard.md stale for {governance_stale_hours:.1f}h (>72h)",
                "timestamp": now,
                "decision": "investigate",
                "resolved": False,
                "resolved_at": None,
                "resolution_note": None,
            }
        )

    if has_run_history:
        today = datetime.now().astimezone().date()
        recent_days = [(today - timedelta(days=idx)).isoformat() for idx in range(0, 3)]
        if all(int(completed_by_day.get(day, 0)) == 0 for day in recent_days):
            items.append(
                {
                    "clone_id": clone_id,
                    "type": "inactive",
                    "severity": "warning",
                    "message": "tasks completed stayed 0 for three consecutive days",
                    "timestamp": now,
                    "decision": "investigate",
                    "resolved": False,
                    "resolved_at": None,
                    "resolution_note": None,
                }
            )

    if closure_ratio is not None and closure_ratio < 0.3:
        items.append(
            {
                "clone_id": clone_id,
                "type": "low_closure_rate",
                "severity": "warning",
                "message": f"closure_rate={closure_ratio:.2f} (<0.30)",
                "timestamp": now,
                "decision": "investigate",
                "resolved": False,
                "resolved_at": None,
                "resolution_note": None,
            }
        )

    return items


def append_alerts(alert_path: Path, new_alerts: list[dict[str, Any]], state: ProbeState, dry_run: bool) -> tuple[list[dict[str, Any]], int]:
    existing, shape = load_alerts(alert_path, state)
    if new_alerts:
        next_id = next_alert_id(existing)
        seq = int(next_id.split("-")[1])
        for alert in new_alerts:
            alert["alert_id"] = f"ALT-{seq}"
            seq += 1
            existing.append(alert)

    if shape == "list":
        payload: Any = existing
    else:
        payload = {"alerts": existing}
    write_json_atomic(alert_path, payload, dry_run=dry_run)

    active = 0
    for alert in existing:
        if not bool(alert.get("resolved", False)):
            active += 1
    return existing, active


def resolve_clone_identity(root: Path, clone_state_dir: Path, arg_clone_id: str | None, arg_tenant_id: str | None, state: ProbeState) -> tuple[str, str]:
    clone_id = arg_clone_id
    tenant_id = arg_tenant_id

    if clone_id and tenant_id:
        return clone_id, tenant_id

    registry_path = clone_state_dir / "clone-registry.json"
    registry = read_json(registry_path, default=None, state=state)
    candidate: dict[str, Any] = {}
    if isinstance(registry, dict):
        candidate = registry
    elif isinstance(registry, list) and registry and isinstance(registry[0], dict):
        candidate = registry[0]

    if not clone_id:
        clone_id = str(candidate.get("clone_id") or f"clone-{root.name}")
    if not tenant_id:
        tenant_id = str(candidate.get("tenant_id") or f"tenant-{root.name}")

    if not registry_path.exists():
        state.assumptions.append("clone-state/clone-registry.json missing; clone_id and tenant_id inferred from root name")
    return clone_id, tenant_id


def resolve_instance_identity(instance_id: str, state: ProbeState) -> tuple[str, str]:
    registry_path = resolve_repo_root() / "artifacts" / "ai-da-guan-jia" / "clones" / "current" / "clone-registry.json"
    registry = read_json(registry_path, default=None, state=state)
    clone_id = instance_id
    tenant_id = f"tenant-{instance_id}"
    if isinstance(registry, list):
        for row in registry:
            if not isinstance(row, dict):
                continue
            if str(row.get("clone_id") or "") == instance_id:
                clone_id = str(row.get("clone_id") or instance_id)
                tenant_id = str(row.get("tenant_id") or tenant_id)
                return clone_id, tenant_id
    state.assumptions.append(f"clone-registry.json missing entry for {instance_id}; identity inferred from instance_id")
    return clone_id, tenant_id


def update_scorecard_aggregate(
    aggregate_path: Path,
    instance_id: str,
    clone_id: str,
    scorecard_obj: dict[str, Any],
    status: str,
    state: ProbeState,
    dry_run: bool,
) -> None:
    payload = read_json(aggregate_path, default=None, state=state)
    items: list[dict[str, Any]] = []
    if isinstance(payload, list):
        items = [row for row in payload if isinstance(row, dict)]
    elif payload not in (None, {}):
        state.errors.append(f"unexpected scorecard aggregate shape at {aggregate_path}; reset to empty list")

    updated_at = iso_utc(now_utc())
    entry = {
        "instance_id": instance_id,
        "clone_id": clone_id,
        "period": scorecard_obj.get("period"),
        "dimensions": scorecard_obj.get("dimensions"),
        "total": scorecard_obj.get("total"),
        "status": status,
        "updated_at": updated_at,
    }
    replaced = False
    for idx, row in enumerate(items):
        if str(row.get("instance_id") or "") == instance_id:
            items[idx] = entry
            replaced = True
            break
    if not replaced:
        items.append(entry)
    write_json_atomic(aggregate_path, items, dry_run=dry_run)


def resolve_endpoint(root: Path, clone_state_dir: Path, arg_endpoint: str | None, state: ProbeState) -> str:
    if arg_endpoint is not None:
        return arg_endpoint.strip()

    for candidate in (clone_state_dir / "config.json", root / "config.json"):
        payload = read_json(candidate, default=None, state=state)
        if isinstance(payload, dict):
            endpoint = payload.get("mother_feedback_endpoint")
            if isinstance(endpoint, str) and endpoint.strip():
                return endpoint.strip()
    return ""


def push_webhook(endpoint: str, heartbeat: dict[str, Any], timeout: int, state: ProbeState) -> bool:
    body = json.dumps(heartbeat, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            _ = resp.read()
        return True
    except (error.URLError, error.HTTPError, TimeoutError) as exc:
        state.errors.append(f"webhook push failed: {exc}")
        return False


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    state = ProbeState(assumptions=[], errors=[])
    instance_id = str(args.instance or "").strip()
    if instance_id:
        root = resolve_repo_root() / "artifacts" / "ai-da-guan-jia" / "clones" / "instances" / instance_id
    else:
        root = Path(args.root).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"root path does not exist: {root}")

    clone_state_dir = root / "clone-state"
    health_dir = root / ".health"
    runs_dir = root / "runs"
    feedback_dir = root / "feedback"
    governance_path = root / "governance-dashboard.md"

    if instance_id:
        clone_id, tenant_id = resolve_instance_identity(instance_id, state)
    else:
        clone_id, tenant_id = resolve_clone_identity(
            root=root,
            clone_state_dir=clone_state_dir,
            arg_clone_id=args.clone_id,
            arg_tenant_id=args.tenant_id,
            state=state,
        )
    run_stats = scan_runs(runs_dir, state)
    governance_stats = parse_governance_dashboard(governance_path, state)
    feedback_stats = scan_feedback(feedback_dir, state)
    last_active = run_stats.get("last_active_session") or feedback_stats.get("last_feedback_activity") or governance_stats.get("updated_at")
    if not last_active:
        last_active = iso_utc(now_utc())

    scorecard_path = clone_state_dir / ("scorecard.json" if instance_id else "clone-scorecard.json")
    scorecard_obj, closure_ratio = update_scorecard(
        scorecard_path=scorecard_path,
        clone_id=clone_id,
        tasks_completed_today=int(run_stats["tasks_completed_today"]),
        tasks_failed_today=int(run_stats["tasks_failed_today"]),
        sessions_today=int(run_stats["sessions_today"]),
        codex_proposals_today=int(feedback_stats["codex_proposals_today"]),
        state=state,
        dry_run=args.dry_run,
    )

    new_alerts = build_new_alerts(
        clone_id=clone_id,
        closure_ratio=closure_ratio,
        governance_stale_hours=governance_stats["stale_hours"],
        completed_by_day=run_stats["completed_by_day"],
        has_run_history=bool(run_stats["has_run_history"]),
    )
    alerts_path = clone_state_dir / ("alerts.json" if instance_id else "alerts-decisions.json")
    _, alerts_active = append_alerts(alerts_path, new_alerts=new_alerts, state=state, dry_run=args.dry_run)

    status = "healthy"
    if alerts_active > 0:
        status = "degraded"
    if any("critical" == str(a.get("severity", "")).lower() for a in new_alerts):
        status = "unhealthy"

    heartbeat = {
        "clone_id": clone_id,
        "tenant_id": tenant_id,
        "timestamp": iso_utc(now_utc()),
        "last_active_session": last_active,
        "sessions_today": int(run_stats["sessions_today"]),
        "tasks_completed_today": int(run_stats["tasks_completed_today"]),
        "tasks_failed_today": int(run_stats["tasks_failed_today"]),
        "codex_proposals_today": int(feedback_stats["codex_proposals_today"]),
        "governance_maturity": int(governance_stats["governance_maturity"]),
        "feedback_pending": int(feedback_stats["feedback_pending"]),
        "alerts_active": int(alerts_active),
        "status": status,
    }
    if state.assumptions:
        heartbeat["assumptions"] = state.assumptions
    if state.errors:
        heartbeat["errors"] = state.errors

    heartbeat_path = health_dir / "heartbeat.json"
    write_json_atomic(heartbeat_path, heartbeat, dry_run=args.dry_run)

    if instance_id:
        update_scorecard_aggregate(
            aggregate_path=clone_scorecard_aggregate_path(),
            instance_id=instance_id,
            clone_id=clone_id,
            scorecard_obj=scorecard_obj,
            status=status,
            state=state,
            dry_run=args.dry_run,
        )

    endpoint = resolve_endpoint(root, clone_state_dir, args.endpoint, state)
    webhook_sent = False
    if endpoint and not args.dry_run:
        webhook_sent = push_webhook(endpoint, heartbeat, timeout=args.webhook_timeout, state=state)

    return {
        "root": str(root),
        "instance_id": instance_id or None,
        "dry_run": bool(args.dry_run),
        "heartbeat_path": str(heartbeat_path),
        "scorecard_path": str(scorecard_path),
        "alerts_path": str(alerts_path),
        "new_alerts_count": len(new_alerts),
        "webhook_endpoint_configured": bool(endpoint),
        "webhook_sent": webhook_sent,
        "heartbeat": heartbeat,
        "scorecard": scorecard_obj,
        "assumptions": state.assumptions,
        "errors": state.errors,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TS-V2 PHASE0 D3 local health probe")
    parser.add_argument("--root", default=".", help="Clone-local root directory to scan")
    parser.add_argument("--instance", help="Optional clone instance id to scan under artifacts/ai-da-guan-jia/clones/instances/")
    parser.add_argument("--clone-id", help="Optional override for clone_id")
    parser.add_argument("--tenant-id", help="Optional override for tenant_id")
    parser.add_argument("--endpoint", help="Optional webhook endpoint override")
    parser.add_argument("--webhook-timeout", type=int, default=10, help="Webhook timeout in seconds (default: 10)")
    parser.add_argument("--dry-run", action="store_true", help="Compute and print payload without writing files")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = run_probe(args)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1

    output = {
        "ok": len(result.get("errors", [])) == 0,
        "summary": {
            "root": result["root"],
            "instance_id": result.get("instance_id"),
            "dry_run": result["dry_run"],
            "heartbeat_path": result["heartbeat_path"],
            "scorecard_path": result["scorecard_path"],
            "alerts_path": result["alerts_path"],
            "new_alerts_count": result["new_alerts_count"],
            "webhook_endpoint_configured": result["webhook_endpoint_configured"],
            "webhook_sent": result["webhook_sent"],
            "status": result["heartbeat"]["status"],
            "alerts_active": result["heartbeat"]["alerts_active"],
        },
    }
    if result.get("assumptions"):
        output["assumptions"] = result["assumptions"]
    if result.get("errors"):
        output["errors"] = result["errors"]
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
