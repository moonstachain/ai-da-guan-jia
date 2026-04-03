#!/usr/bin/env python3
"""Streaming Executor — Real-time progress feedback for AI大管家 long-running tasks.

Inspired by Claude Code's streaming tool execution pattern:
- Shows real-time progress instead of blocking "waiting..."
- Each step emits status as it completes
- Supports cancellation via KeyboardInterrupt

Usage:
    python3 streaming_executor.py morning --prompt "..."
    python3 streaming_executor.py full-cycle --run-id <id>
    python3 streaming_executor.py close --run-id <id> --task "..."
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
AI_SCRIPT = SCRIPT_DIR / "ai_da_guan_jia.py"
GOV_SCRIPT = SCRIPT_DIR / "governance_engine.py"

# ANSI colors for terminal
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_CYAN = "\033[36m"
_BLUE = "\033[34m"

# Status symbols
_CHECK = f"{_GREEN}✓{_RESET}"
_CROSS = f"{_RED}✗{_RESET}"
_ARROW = f"{_CYAN}→{_RESET}"
_SPIN_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


def _ts() -> str:
    return time.strftime("%H:%M:%S")


def _emit(icon: str, msg: str, detail: str = "") -> None:
    """Emit a streaming progress line."""
    ts = f"{_DIM}[{_ts()}]{_RESET}"
    detail_str = f" {_DIM}— {detail}{_RESET}" if detail else ""
    print(f"{ts} {icon} {msg}{detail_str}", flush=True)


def _run_step(label: str, cmd: list[str], capture: bool = False) -> tuple[int, str]:
    """Run a subprocess step with streaming feedback."""
    _emit(f"{_CYAN}⏳{_RESET}", f"{_BOLD}{label}{_RESET}", f"running...")
    t0 = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        elapsed = time.monotonic() - t0
        elapsed_str = f"{elapsed:.1f}s"
        if result.returncode == 0:
            _emit(_CHECK, f"{label}", f"done in {elapsed_str}")
            return 0, result.stdout.strip()
        else:
            _emit(_CROSS, f"{label}", f"failed ({elapsed_str})")
            if result.stderr:
                for line in result.stderr.strip().split("\n")[:3]:
                    _emit(" ", f"  {_DIM}{line}{_RESET}")
            return result.returncode, result.stderr.strip()
    except subprocess.TimeoutExpired:
        _emit(_CROSS, f"{label}", "timeout (300s)")
        return 1, "timeout"
    except KeyboardInterrupt:
        _emit(f"{_YELLOW}⚠{_RESET}", f"{label}", "cancelled by user")
        raise


def _run_pipeline(prompt: str) -> dict[str, Any]:
    """Run governance pipeline and parse JSON output."""
    code, output = _run_step(
        "治理流水线",
        ["python3", str(AI_SCRIPT), "governance-pipeline", "--prompt", prompt, "--json"],
        capture=True,
    )
    if code == 0 and output:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
    return {"final_decision": "error", "layers_executed": 0}


# ═══════════════════════════════════════════════════════════════════════════
# Streaming Workflows
# ═══════════════════════════════════════════════════════════════════════════

def stream_morning(prompt: str) -> int:
    """Morning workflow with streaming progress."""
    print(f"\n{_BOLD}=== 🌅 Morning Cockpit ==={_RESET}\n")

    # Step 1: Governance Pipeline
    pipeline = _run_pipeline(prompt)
    decision = pipeline.get("final_decision", "unknown")
    layers = pipeline.get("layers_executed", 0)
    _emit(_ARROW, f"决策: {_BOLD}{decision}{_RESET}", f"layers: {layers}")

    if decision == "block":
        _emit(f"{_RED}🚫{_RESET}", "任务被阻断", "需要人类介入（登录/授权/不可逆操作）")
        return 1

    # Step 2: Route
    code, output = _run_step(
        "路由分析",
        ["python3", str(AI_SCRIPT), "route", "--prompt", prompt],
    )
    if code != 0:
        return code

    # Extract run_id from output
    run_id = ""
    for line in output.split("\n"):
        if line.startswith("run_id:"):
            run_id = line.split(":", 1)[1].strip()
            break

    if run_id:
        # Step 3: State machine advance
        _run_step(
            "状态推进 → executing",
            ["python3", str(AI_SCRIPT), "run-state", "--run-id", run_id, "--action", "advance"],
        )

        # Step 4: Skill recommendation
        code, harness_output = _run_step(
            "技能推荐",
            ["python3", str(AI_SCRIPT), "skill-harness", "--prompt", prompt],
            capture=True,
        )
        if code == 0 and harness_output:
            try:
                harness = json.loads(harness_output)
                combo = harness.get("recommended_combo", [])
                if combo:
                    names = [s["skill"] for s in combo[:3]]
                    _emit(_ARROW, f"推荐技能: {_BOLD}{', '.join(names)}{_RESET}")
            except json.JSONDecodeError:
                pass

    # Summary
    print(f"\n{_BOLD}=== Morning Summary ==={_RESET}")
    _emit(_CHECK, f"run_id: {run_id}" if run_id else "路由完成")
    _emit(_ARROW, f"decision: {decision}")
    print()
    return 0


def stream_full_cycle(run_id: str) -> int:
    """Full lifecycle: execute → verify → evolve → sync → close, with streaming."""
    print(f"\n{_BOLD}=== ⚡ Full Cycle: {run_id} ==={_RESET}\n")

    # Show current state
    code, state_output = _run_step(
        "检查当前状态",
        ["python3", str(AI_SCRIPT), "run-state", "--run-id", run_id, "--action", "show"],
        capture=True,
    )
    if code != 0:
        return code

    current_state = "unknown"
    try:
        state_data = json.loads(state_output)
        current_state = state_data.get("current_state", "unknown")
    except json.JSONDecodeError:
        pass
    _emit(_ARROW, f"当前状态: {_BOLD}{current_state}{_RESET}")

    # Advance through states
    steps = [
        ("advancing to executing", "executing"),
        ("advancing to evidence_collected", "evidence_collected"),
    ]
    for label, target in steps:
        if current_state in ("closed", "blocked"):
            break
        code, _ = _run_step(
            f"状态推进 → {target}",
            ["python3", str(AI_SCRIPT), "run-state", "--run-id", run_id,
             "--action", "advance", "--target", target],
        )
        if code == 0:
            current_state = target

    # Adversarial verification
    code, verify_output = _run_step(
        "对抗验真",
        ["python3", str(AI_SCRIPT), "verify", "--run-id", run_id, "--adversarial"],
        capture=True,
    )
    if code == 0:
        try:
            report = json.loads(verify_output)
            _emit(_ARROW, f"验真结果: {_BOLD}{report.get('verdict', 'unknown')}{_RESET}",
                   report.get("summary", ""))
        except json.JSONDecodeError:
            pass
    else:
        _emit(f"{_YELLOW}⚠{_RESET}", "验真未通过", "检查 verification-report.json")

    # Summary
    print(f"\n{_BOLD}=== Cycle Summary ==={_RESET}")
    _emit(_ARROW, f"final_state: {current_state}")
    print()
    return 0


def stream_close(run_id: str, task: str) -> int:
    """Streaming close-task with pre-verification."""
    print(f"\n{_BOLD}=== 🔒 Close Task: {run_id} ==={_RESET}\n")

    # Step 1: Pre-close adversarial verification
    code, verify_output = _run_step(
        "闭环前对抗验真",
        ["python3", str(AI_SCRIPT), "verify", "--run-id", run_id, "--adversarial"],
        capture=True,
    )
    verdict = "unknown"
    if code == 0:
        try:
            report = json.loads(verify_output)
            verdict = report.get("verdict", "unknown")
            _emit(_ARROW, f"验真: {_BOLD}{verdict}{_RESET}", report.get("summary", ""))
        except json.JSONDecodeError:
            pass

    if verdict == "failed":
        _emit(f"{_RED}🚫{_RESET}", "验真失败，不建议关闭", "请先补齐缺失的 artifacts")
        return 1

    # Step 2: Close task
    code, _ = _run_step(
        "执行 close-task",
        ["python3", str(AI_SCRIPT), "close-task", "--task", task, "--run-id", run_id],
    )

    # Step 3: Final state
    if code == 0:
        _run_step(
            "状态推进 → closed",
            ["python3", str(AI_SCRIPT), "run-state", "--run-id", run_id,
             "--action", "advance", "--target", "closed"],
        )

    print(f"\n{_BOLD}=== Close Summary ==={_RESET}")
    _emit(_CHECK if code == 0 else _CROSS, f"close-task {'成功' if code == 0 else '失败'}")
    print()
    return code


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="streaming_executor",
        description="Streaming executor for AI大管家 with real-time progress.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    m = sub.add_parser("morning", help="Morning workflow with streaming.")
    m.add_argument("--prompt", required=True)

    f = sub.add_parser("full-cycle", help="Full lifecycle with streaming.")
    f.add_argument("--run-id", required=True)

    c = sub.add_parser("close", help="Pre-verified close-task with streaming.")
    c.add_argument("--run-id", required=True)
    c.add_argument("--task", required=True)

    args = parser.parse_args(argv)

    if args.command == "morning":
        return stream_morning(args.prompt)
    if args.command == "full-cycle":
        return stream_full_cycle(args.run_id)
    if args.command == "close":
        return stream_close(args.run_id, args.task)
    return 1


if __name__ == "__main__":
    sys.exit(main())
