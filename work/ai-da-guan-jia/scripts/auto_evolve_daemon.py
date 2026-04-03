#!/usr/bin/env python3
"""Auto-Evolve Daemon — Autonomous evolution material accumulation.

Inspired by Karpathy's autoresearch autonomous iteration loop:
- Scans artifacts/ for recent changes
- Extracts effective/wasted patterns
- Accumulates evolution candidates
- Generates daily evolution digest for human review
- NEVER executes irreversible actions — only accumulates material

Usage:
    python3 auto_evolve_daemon.py scan [--hours 1]       # One-shot scan
    python3 auto_evolve_daemon.py digest [--date today]   # Generate daily digest
    python3 auto_evolve_daemon.py daemon [--interval 3600] # Background daemon mode
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
ARTIFACTS_ROOT = SKILL_DIR / "artifacts" / "ai-da-guan-jia"
RUNS_ROOT = ARTIFACTS_ROOT / "runs"
EVOLUTION_ARCHIVE = ARTIFACTS_ROOT / "evolution-archive"
DIGEST_ROOT = ARTIFACTS_ROOT / "evolution-digests"


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


# ═══════════════════════════════════════════════════════════════════════════
# Scan Engine
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ScanResult:
    scanned_at: str
    runs_scanned: int
    new_patterns: list[dict[str, Any]]
    new_candidates: list[dict[str, Any]]
    anomalies: list[dict[str, str]]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "scanned_at": self.scanned_at,
            "runs_scanned": self.runs_scanned,
            "new_patterns": self.new_patterns,
            "new_candidates": self.new_candidates,
            "anomalies": self.anomalies,
            "summary": self.summary,
        }


def _recent_run_dirs(hours: float = 1.0) -> list[Path]:
    """Find run directories modified in the last N hours."""
    cutoff = time.time() - hours * 3600
    dirs: list[Path] = []
    if not RUNS_ROOT.exists():
        return dirs
    for date_dir in sorted(RUNS_ROOT.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        for run_dir in date_dir.iterdir():
            if not run_dir.is_dir():
                continue
            # Check any file modified after cutoff
            try:
                latest_mtime = max(f.stat().st_mtime for f in run_dir.iterdir() if f.is_file())
                if latest_mtime >= cutoff:
                    dirs.append(run_dir)
            except (ValueError, OSError):
                continue
    return dirs


def _extract_patterns_from_evolution(evo: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    """Extract (effective, wasted, candidates) from an evolution record."""
    effective = [str(p) for p in evo.get("effective_patterns", []) if p]
    wasted = [str(p) for p in evo.get("wasted_patterns", []) if p]
    candidates = [str(p) for p in evo.get("evolution_candidates", []) if p]
    return effective, wasted, candidates


def _is_boilerplate(pattern: str) -> bool:
    """Check if a pattern is likely generic boilerplate."""
    generic = [
        "canonical-first closure",
        "promote the strongest",
        "standard verification",
        "write route, evolution",
        "default to high autonomy",
    ]
    lower = pattern.lower()
    return any(g in lower for g in generic)


def _detect_anomalies(run_dir: Path) -> list[dict[str, str]]:
    """Detect potential issues in a run directory."""
    anomalies = []

    # Check: route.json exists but no evolution.json after >1h
    route = run_dir / "route.json"
    evo = run_dir / "evolution.json"
    if route.exists() and not evo.exists():
        route_age = time.time() - route.stat().st_mtime
        if route_age > 3600:
            anomalies.append({
                "type": "stale_route",
                "run_id": run_dir.name,
                "detail": f"route.json is {route_age / 3600:.1f}h old with no evolution record",
            })

    # Check: evolution exists but feishu-payload missing
    if evo.exists() and not (run_dir / "feishu-payload.json").exists():
        anomalies.append({
            "type": "missing_sync",
            "run_id": run_dir.name,
            "detail": "evolution.json exists but feishu-payload.json is missing",
        })

    # Check: state.json stuck in executing for >2h
    state_file = run_dir / "state.json"
    if state_file.exists():
        try:
            state = read_json(state_file)
            if state.get("current_state") == "executing":
                updated = state.get("updated_at", "")
                if updated:
                    updated_dt = datetime.fromisoformat(updated)
                    age = (datetime.now().astimezone() - updated_dt).total_seconds()
                    if age > 7200:
                        anomalies.append({
                            "type": "stuck_executing",
                            "run_id": run_dir.name,
                            "detail": f"State stuck in 'executing' for {age / 3600:.1f}h",
                        })
        except Exception:
            pass

    return anomalies


def scan(hours: float = 1.0) -> ScanResult:
    """Scan recent runs and extract evolution material."""
    runs = _recent_run_dirs(hours)
    all_patterns: list[dict[str, Any]] = []
    all_candidates: list[dict[str, Any]] = []
    all_anomalies: list[dict[str, str]] = []

    for run_dir in runs:
        evo_path = run_dir / "evolution.json"
        if evo_path.exists():
            try:
                evo = read_json(evo_path)
                effective, wasted, candidates = _extract_patterns_from_evolution(evo)

                for p in effective:
                    if not _is_boilerplate(p):
                        all_patterns.append({
                            "type": "effective",
                            "pattern": p,
                            "run_id": run_dir.name,
                            "task": str(evo.get("task_text", ""))[:100],
                        })
                for p in wasted:
                    if not _is_boilerplate(p):
                        all_patterns.append({
                            "type": "wasted",
                            "pattern": p,
                            "run_id": run_dir.name,
                            "task": str(evo.get("task_text", ""))[:100],
                        })
                for c in candidates:
                    if not _is_boilerplate(c):
                        all_candidates.append({
                            "candidate": c,
                            "run_id": run_dir.name,
                            "task": str(evo.get("task_text", ""))[:100],
                        })
            except Exception:
                pass

        all_anomalies.extend(_detect_anomalies(run_dir))

    result = ScanResult(
        scanned_at=iso_now(),
        runs_scanned=len(runs),
        new_patterns=all_patterns,
        new_candidates=all_candidates,
        anomalies=all_anomalies,
        summary=f"Scanned {len(runs)} runs: {len(all_patterns)} patterns, {len(all_candidates)} candidates, {len(all_anomalies)} anomalies",
    )

    # Persist scan result
    scan_dir = ensure_dir(EVOLUTION_ARCHIVE / "scans")
    write_json(scan_dir / f"scan-{time.strftime('%Y%m%d-%H%M%S')}.json", result.to_dict())

    return result


# ═══════════════════════════════════════════════════════════════════════════
# Daily Digest
# ═══════════════════════════════════════════════════════════════════════════

def generate_digest(date_str: str | None = None) -> dict[str, Any]:
    """Generate a daily evolution digest from all runs of the given date."""
    target_date = date_str or time.strftime("%Y-%m-%d")
    date_dir = RUNS_ROOT / target_date

    if not date_dir.exists():
        return {"date": target_date, "error": "No runs found for this date"}

    all_effective: list[str] = []
    all_wasted: list[str] = []
    all_candidates: list[str] = []
    skills_used: Counter = Counter()
    run_count = 0
    completed_count = 0
    anomalies: list[dict[str, str]] = []

    for run_dir in sorted(date_dir.iterdir()):
        if not run_dir.is_dir():
            continue
        run_count += 1

        # Extract from evolution
        evo_path = run_dir / "evolution.json"
        if evo_path.exists():
            try:
                evo = read_json(evo_path)
                effective, wasted, candidates = _extract_patterns_from_evolution(evo)
                all_effective.extend(p for p in effective if not _is_boilerplate(p))
                all_wasted.extend(p for p in wasted if not _is_boilerplate(p))
                all_candidates.extend(c for c in candidates if not _is_boilerplate(c))
                for s in evo.get("skills_selected", []):
                    skills_used[s] += 1
            except Exception:
                pass

        # Check completion
        if (run_dir / "close-task.json").exists():
            completed_count += 1

        state_file = run_dir / "state.json"
        if state_file.exists():
            try:
                state = read_json(state_file)
                if state.get("current_state") == "closed":
                    completed_count += 1
            except Exception:
                pass

        anomalies.extend(_detect_anomalies(run_dir))

    # Deduplicate patterns
    unique_effective = list(dict.fromkeys(all_effective))
    unique_wasted = list(dict.fromkeys(all_wasted))
    unique_candidates = list(dict.fromkeys(all_candidates))

    digest = {
        "date": target_date,
        "generated_at": iso_now(),
        "runs_total": run_count,
        "runs_completed": completed_count,
        "completion_rate": round(completed_count / max(run_count, 1), 2),
        "top_skills": skills_used.most_common(5),
        "effective_patterns": unique_effective,
        "wasted_patterns": unique_wasted,
        "evolution_candidates": unique_candidates,
        "anomalies": anomalies,
        "digest_summary": (
            f"{target_date}: {run_count} runs, {completed_count} completed ({round(completed_count / max(run_count, 1) * 100)}%), "
            f"{len(unique_effective)} effective patterns, {len(unique_wasted)} wasted patterns, "
            f"{len(unique_candidates)} evolution candidates, {len(anomalies)} anomalies"
        ),
    }

    # Persist digest
    digest_path = ensure_dir(DIGEST_ROOT) / f"digest-{target_date}.json"
    write_json(digest_path, digest)

    # Also write human-readable markdown
    md_lines = [
        f"# Evolution Digest — {target_date}\n",
        f"- Runs: {run_count} total, {completed_count} completed ({round(completed_count / max(run_count, 1) * 100)}%)",
        f"- Top skills: {', '.join(f'{s}({c})' for s, c in skills_used.most_common(5)) or 'none'}",
        "",
    ]
    if unique_effective:
        md_lines.append("## Effective Patterns")
        for p in unique_effective:
            md_lines.append(f"- {p}")
        md_lines.append("")
    if unique_wasted:
        md_lines.append("## Wasted Patterns")
        for p in unique_wasted:
            md_lines.append(f"- {p}")
        md_lines.append("")
    if unique_candidates:
        md_lines.append("## Evolution Candidates")
        for c in unique_candidates:
            md_lines.append(f"- {c}")
        md_lines.append("")
    if anomalies:
        md_lines.append("## Anomalies")
        for a in anomalies:
            md_lines.append(f"- [{a['type']}] {a['run_id']}: {a['detail']}")
        md_lines.append("")

    md_path = ensure_dir(DIGEST_ROOT) / f"digest-{target_date}.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    return digest


# ═══════════════════════════════════════════════════════════════════════════
# Daemon Mode
# ═══════════════════════════════════════════════════════════════════════════

def run_daemon(interval_seconds: int = 3600) -> None:
    """Run the auto-evolve daemon. Scans periodically, generates digest at end of day."""
    print(f"[auto-evolve] daemon started, interval={interval_seconds}s")
    print(f"[auto-evolve] artifacts: {ARTIFACTS_ROOT}")
    print(f"[auto-evolve] Ctrl+C to stop\n")

    last_digest_date = ""

    try:
        while True:
            # Periodic scan
            result = scan(hours=interval_seconds / 3600)
            print(f"[{time.strftime('%H:%M:%S')}] {result.summary}")

            if result.new_candidates:
                print(f"  📋 New candidates: {len(result.new_candidates)}")
                for c in result.new_candidates[:3]:
                    print(f"    - {c['candidate'][:80]}")

            if result.anomalies:
                print(f"  ⚠️  Anomalies: {len(result.anomalies)}")
                for a in result.anomalies[:3]:
                    print(f"    - [{a['type']}] {a['detail'][:80]}")

            # Generate daily digest at end of day (after 22:00)
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")
            if now.hour >= 22 and today != last_digest_date:
                print(f"\n[{time.strftime('%H:%M:%S')}] Generating daily digest...")
                digest = generate_digest(today)
                print(f"  📊 {digest['digest_summary']}")
                last_digest_date = today

            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        print(f"\n[auto-evolve] daemon stopped at {iso_now()}")


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="auto_evolve_daemon",
        description="Auto-evolve daemon: autonomous evolution material accumulation.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    s = sub.add_parser("scan", help="One-shot scan of recent runs.")
    s.add_argument("--hours", type=float, default=1.0, help="Hours to look back.")

    d = sub.add_parser("digest", help="Generate daily evolution digest.")
    d.add_argument("--date", help="Date in YYYY-MM-DD format (default: today).")

    dm = sub.add_parser("daemon", help="Run background daemon.")
    dm.add_argument("--interval", type=int, default=3600, help="Scan interval in seconds.")

    args = parser.parse_args(argv)

    if args.command == "scan":
        result = scan(hours=args.hours)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "digest":
        digest = generate_digest(args.date)
        print(json.dumps(digest, ensure_ascii=False, indent=2))
        return 0

    if args.command == "daemon":
        run_daemon(interval_seconds=args.interval)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
