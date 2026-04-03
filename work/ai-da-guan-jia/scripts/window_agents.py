#!/usr/bin/env python3
"""Multi-Agent Window Deployment — True context isolation for 总控台/运营主线/支线.

Inspired by Claude Agent SDK's subagent pattern:
- Each window role has isolated context, restricted tools, and defined boundaries
- Communication happens through artifacts/ directory (shared filesystem)
- No window can modify another window's state directly

Usage:
    python3 window_agents.py spawn --role controller --task "..."
    python3 window_agents.py spawn --role mainline --task "..."
    python3 window_agents.py spawn --role branch --task "..." --branch-id B1
    python3 window_agents.py status
    python3 window_agents.py morning-assembly
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
ARTIFACTS_ROOT = SKILL_DIR / "artifacts" / "ai-da-guan-jia"
WINDOW_STATE_ROOT = ARTIFACTS_ROOT / "windows"
AI_SCRIPT = SCRIPT_DIR / "ai_da_guan_jia.py"


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
# Window Role Definitions (Claude Agent SDK compatible)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class WindowRole:
    """Defines a window agent's capabilities and constraints."""
    name: str
    display_name: str
    allowed_commands: tuple[str, ...]   # Which ai_da_guan_jia.py subcommands this role can use
    forbidden_commands: tuple[str, ...]  # Explicitly forbidden
    context_scope: str                   # What this role can see
    description: str
    max_concurrent: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "allowed_commands": list(self.allowed_commands),
            "forbidden_commands": list(self.forbidden_commands),
            "context_scope": self.context_scope,
            "description": self.description,
            "max_concurrent": self.max_concurrent,
        }


# The three fixed roles from AI大管家's window model
ROLES: dict[str, WindowRole] = {
    "controller": WindowRole(
        name="controller",
        display_name="总控台",
        allowed_commands=(
            "route", "governance-pipeline", "review-governance", "strategy-governor",
            "run-state", "verify", "skill-harness", "inventory-skills",
        ),
        forbidden_commands=(
            "record-evolution", "sync-feishu", "close-task",
            "get-biji", "flomo-zsxq-poll", "tool-glue-zsxq",
        ),
        context_scope="north_star + all run states + evolution summaries + strategy artifacts",
        description="只做裁决、统筹、路线、验真、收口。不直接执行任何 skill。",
    ),
    "mainline": WindowRole(
        name="mainline",
        display_name="运营主线",
        allowed_commands=(
            "record-evolution", "sync-feishu", "close-task",
            "get-biji", "feishu-km", "run-state",
            "governance-pipeline", "verify",
        ),
        forbidden_commands=(
            "route", "review-governance", "strategy-governor",
            "inventory-skills",
        ),
        context_scope="current run task_spec + skill_combo + execution artifacts",
        description="承接当天主线任务，组织推进，消费支线结果。不能修改路由决策。",
    ),
    "branch": WindowRole(
        name="branch",
        display_name="支线",
        allowed_commands=(
            "record-evolution", "run-state", "verify",
            "governance-pipeline",
        ),
        forbidden_commands=(
            "route", "review-governance", "strategy-governor",
            "sync-feishu", "close-task", "inventory-skills",
        ),
        context_scope="single subtask spec only — no access to other branches or mainline state",
        description="单目标合同，不改主线状态，不擅自扩 scope。",
        max_concurrent=5,
    ),
}


# ═══════════════════════════════════════════════════════════════════════════
# Window Session Management
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class WindowSession:
    session_id: str
    role: str
    task: str
    branch_id: str
    status: str  # "active" | "completed" | "blocked"
    started_at: str
    updated_at: str
    run_ids: list[str]
    output_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "role": self.role,
            "task": self.task,
            "branch_id": self.branch_id,
            "status": self.status,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "run_ids": self.run_ids,
            "output_summary": self.output_summary,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WindowSession:
        return cls(
            session_id=d["session_id"],
            role=d["role"],
            task=d["task"],
            branch_id=d.get("branch_id", ""),
            status=d["status"],
            started_at=d["started_at"],
            updated_at=d["updated_at"],
            run_ids=d.get("run_ids", []),
            output_summary=d.get("output_summary", ""),
        )


def _sessions_file() -> Path:
    return ensure_dir(WINDOW_STATE_ROOT) / "sessions.json"


def _load_sessions() -> list[WindowSession]:
    sf = _sessions_file()
    if sf.exists():
        try:
            data = read_json(sf)
            return [WindowSession.from_dict(s) for s in data]
        except Exception:
            pass
    return []


def _save_sessions(sessions: list[WindowSession]) -> None:
    write_json(_sessions_file(), [s.to_dict() for s in sessions])


def _gen_session_id(role: str) -> str:
    return f"win-{role}-{time.strftime('%Y%m%d-%H%M%S')}"


def spawn_window(role_name: str, task: str, branch_id: str = "") -> WindowSession:
    """Spawn a new window agent session."""
    if role_name not in ROLES:
        raise ValueError(f"Unknown role: {role_name}. Valid: {list(ROLES.keys())}")

    role = ROLES[role_name]
    sessions = _load_sessions()

    # Check max_concurrent
    active_count = sum(1 for s in sessions if s.role == role_name and s.status == "active")
    if active_count >= role.max_concurrent:
        raise ValueError(
            f"Max concurrent sessions for {role.display_name} is {role.max_concurrent}. "
            f"Currently {active_count} active."
        )

    session = WindowSession(
        session_id=_gen_session_id(role_name),
        role=role_name,
        task=task,
        branch_id=branch_id,
        status="active",
        started_at=iso_now(),
        updated_at=iso_now(),
        run_ids=[],
    )
    sessions.append(session)
    _save_sessions(sessions)

    # Write the session contract (isolation boundary)
    contract = {
        "session_id": session.session_id,
        "role": role.to_dict(),
        "task": task,
        "branch_id": branch_id,
        "contract": {
            "you_can": list(role.allowed_commands),
            "you_cannot": list(role.forbidden_commands),
            "you_see": role.context_scope,
            "communicate_via": f"{WINDOW_STATE_ROOT}/{session.session_id}/",
            "rule": role.description,
        },
        "started_at": session.started_at,
    }
    session_dir = ensure_dir(WINDOW_STATE_ROOT / session.session_id)
    write_json(session_dir / "contract.json", contract)

    return session


def complete_window(session_id: str, summary: str = "") -> WindowSession:
    """Mark a window session as completed."""
    sessions = _load_sessions()
    for s in sessions:
        if s.session_id == session_id:
            s.status = "completed"
            s.updated_at = iso_now()
            s.output_summary = summary
            _save_sessions(sessions)
            return s
    raise ValueError(f"Session not found: {session_id}")


def list_active_sessions() -> list[dict[str, Any]]:
    """List all active window sessions."""
    sessions = _load_sessions()
    return [s.to_dict() for s in sessions if s.status == "active"]


# ═══════════════════════════════════════════════════════════════════════════
# Morning Assembly (09:00 合并晨会)
# ═══════════════════════════════════════════════════════════════════════════

def morning_assembly() -> dict[str, Any]:
    """Generate the 09:00 morning assembly output.

    Fixed 5 segments:
    1. 总控台今日定盘
    2. 运营主线今日合同
    3. 支线编排建议
    4. 人机协作优化提案
    5. 待裁决项
    """
    sessions = _load_sessions()
    active = [s for s in sessions if s.status == "active"]

    # Load today's digest if available
    today = time.strftime("%Y-%m-%d")
    digest_path = ARTIFACTS_ROOT / "evolution-digests" / f"digest-{today}.json"
    digest = {}
    if digest_path.exists():
        try:
            digest = read_json(digest_path)
        except Exception:
            pass

    # Load recent anomalies
    anomalies = digest.get("anomalies", [])

    assembly = {
        "date": today,
        "generated_at": iso_now(),
        "segments": {
            "1_controller_brief": {
                "title": "总控台今日定盘",
                "active_controller_sessions": [s.to_dict() for s in active if s.role == "controller"],
                "yesterday_completion_rate": digest.get("completion_rate", "N/A"),
                "pending_decisions": len(anomalies),
            },
            "2_mainline_contract": {
                "title": "运营主线今日合同",
                "active_mainline_sessions": [s.to_dict() for s in active if s.role == "mainline"],
                "evolution_candidates": digest.get("evolution_candidates", [])[:3],
            },
            "3_branch_arrangement": {
                "title": "支线编排建议",
                "active_branches": [s.to_dict() for s in active if s.role == "branch"],
                "max_parallel": ROLES["branch"].max_concurrent,
                "slots_available": ROLES["branch"].max_concurrent - sum(1 for s in active if s.role == "branch"),
            },
            "4_human_ai_optimization": {
                "title": "人机协作优化提案",
                "effective_patterns": digest.get("effective_patterns", [])[:3],
                "wasted_patterns": digest.get("wasted_patterns", [])[:3],
            },
            "5_pending_decisions": {
                "title": "待裁决项",
                "anomalies": anomalies[:5],
                "blocked_sessions": [s.to_dict() for s in sessions if s.status == "blocked"],
            },
        },
    }

    # Persist assembly
    assembly_dir = ensure_dir(WINDOW_STATE_ROOT / "assemblies")
    write_json(assembly_dir / f"assembly-{today}.json", assembly)

    return assembly


# ═══════════════════════════════════════════════════════════════════════════
# Claude Agent SDK Integration Config
# ═══════════════════════════════════════════════════════════════════════════

def generate_agent_sdk_config() -> dict[str, Any]:
    """Generate Claude Agent SDK compatible configuration for window agents.

    This config can be used with Claude Code's Agent tool:
    - subagent_type maps to window role
    - tools restriction maps to allowed_commands
    - context isolation via session directory
    """
    config = {
        "generated_at": iso_now(),
        "agent_definitions": {},
    }

    for role_name, role in ROLES.items():
        config["agent_definitions"][role_name] = {
            "subagent_type": role.name,
            "display_name": role.display_name,
            "description": role.description,
            "tools": list(role.allowed_commands),
            "forbidden_tools": list(role.forbidden_commands),
            "context_scope": role.context_scope,
            "max_concurrent": role.max_concurrent,
            "system_prompt_suffix": (
                f"你是 AI大管家 的 {role.display_name} 窗口。\n"
                f"你的职责：{role.description}\n"
                f"你可以使用的命令：{', '.join(role.allowed_commands)}\n"
                f"你不能使用的命令：{', '.join(role.forbidden_commands)}\n"
                f"你只能看到：{role.context_scope}\n"
                f"通过 artifacts/ 目录与其他窗口交换数据，不能直接修改其他窗口的状态。"
            ),
        }

    config_path = ensure_dir(WINDOW_STATE_ROOT) / "agent-sdk-config.json"
    write_json(config_path, config)
    return config


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="window_agents",
        description="Multi-agent window deployment with context isolation.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("spawn", help="Spawn a new window agent session.")
    sp.add_argument("--role", required=True, choices=list(ROLES.keys()))
    sp.add_argument("--task", required=True)
    sp.add_argument("--branch-id", default="")

    cp = sub.add_parser("complete", help="Complete a window session.")
    cp.add_argument("--session-id", required=True)
    cp.add_argument("--summary", default="")

    sub.add_parser("status", help="List active window sessions.")
    sub.add_parser("morning-assembly", help="Generate 09:00 morning assembly.")
    sub.add_parser("agent-config", help="Generate Agent SDK config.")

    args = parser.parse_args(argv)

    if args.command == "spawn":
        session = spawn_window(args.role, args.task, args.branch_id)
        print(f"session_id: {session.session_id}")
        print(f"role: {session.role} ({ROLES[session.role].display_name})")
        print(f"contract: {WINDOW_STATE_ROOT / session.session_id / 'contract.json'}")
        return 0

    if args.command == "complete":
        session = complete_window(args.session_id, args.summary)
        print(f"session_id: {session.session_id} → {session.status}")
        return 0

    if args.command == "status":
        active = list_active_sessions()
        if not active:
            print("No active window sessions.")
        else:
            for s in active:
                role = ROLES.get(s["role"])
                print(f"  [{s['role']}] {role.display_name if role else '?'}: {s['task'][:60]} ({s['session_id']})")
        return 0

    if args.command == "morning-assembly":
        assembly = morning_assembly()
        print(json.dumps(assembly, ensure_ascii=False, indent=2))
        return 0

    if args.command == "agent-config":
        config = generate_agent_sdk_config()
        print(json.dumps(config, ensure_ascii=False, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
