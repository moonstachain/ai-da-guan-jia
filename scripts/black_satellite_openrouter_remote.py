#!/usr/bin/env python3
"""Remote OpenRouter workflow helper for the black satellite machine."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shlex
import socket
import subprocess
import sys
from typing import Sequence


HOST_LABEL = "black-satellite"
REPO_ROOT = Path("/Users/liming/Documents/codex-ai-gua-jia-01")
BRIDGE_SCRIPT = REPO_ROOT / "scripts" / "ccswitch_openrouter_bridge.py"
REMOTE_SELF = REPO_ROOT / "scripts" / "black_satellite_openrouter_remote.py"

PROVIDER_ALIASES = {
    "gpt54": "or-gpt54",
    "gpt-5.4": "or-gpt54",
    "claude4": "or-claude4",
    "claude-sonnet-4": "or-claude4",
    "gemini25": "or-gemini25",
    "gemini-2.5": "or-gemini25",
    "glm45": "or-glm45",
    "glm-4.5": "or-glm45",
    "kimi": "or-kimi-k2",
    "kimi-k2": "or-kimi-k2",
    "minimax": "or-minimax-m1",
    "minimax-m1": "or-minimax-m1",
}

CLI_PATHS = {
    "codex": Path.home() / ".local" / "bin" / "codex",
    "claude": Path.home() / ".local" / "bin" / "claude",
    "gemini": Path.home() / ".local" / "bin" / "gemini",
}


def build_env() -> dict[str, str]:
    env = os.environ.copy()
    path_parts = [
        str(Path.home() / ".local" / "bin"),
        str(Path.home() / ".npm-global" / "bin"),
        "/opt/homebrew/opt/node@20/bin",
        "/opt/homebrew/bin",
        env.get("PATH", ""),
    ]
    env["PATH"] = ":".join(part for part in path_parts if part)
    return env


def resolve_cli_path(tool: str) -> Path | None:
    env = build_env()
    discovered = shutil.which(tool, path=env["PATH"])
    if discovered:
        return Path(discovered)

    fallback_paths = {
        "codex": [
            Path.home() / ".local" / "bin" / "codex",
            Path("/Applications/Codex.app/Contents/Resources/codex"),
        ],
        "claude": [
            Path.home() / ".local" / "bin" / "claude",
        ],
        "gemini": [
            Path.home() / ".local" / "bin" / "gemini",
        ],
    }
    for candidate in fallback_paths.get(tool, []):
        if candidate.exists():
            return candidate
    return None


def run_bridge(*args: str, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    command = ["python3", str(BRIDGE_SCRIPT), *args]
    return subprocess.run(
        command,
        check=True,
        text=True,
        capture_output=capture_output,
        env=build_env(),
    )


def parse_verify_output() -> dict[str, str]:
    completed = run_bridge("verify", capture_output=True)
    parsed: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def resolve_provider(raw: str) -> str:
    provider = raw.strip()
    if provider in PROVIDER_ALIASES:
        return PROVIDER_ALIASES[provider]
    if provider.startswith("or-"):
        return provider
    return provider


def print_shell_banner(status: dict[str, str]) -> None:
    hostname = socket.gethostname()
    current = status.get("current_codex_provider") or status.get("current_claude_provider") or "unknown"
    model = status.get("codex_model") or status.get("claude_model") or "unknown"
    print(f"[{HOST_LABEL}] connected to {hostname}")
    print(f"[{HOST_LABEL}] current provider: {current}")
    print(f"[{HOST_LABEL}] current model: {model}")
    print(f"[{HOST_LABEL}] cwd: {Path.cwd()}")
    print(f"[{HOST_LABEL}] shortcuts: or-status | or-use claude4 | codex | claude | gemini")


def enter_workspace() -> None:
    if REPO_ROOT.exists():
        os.chdir(REPO_ROOT)


def exec_login_shell() -> int:
    enter_workspace()
    status = parse_verify_output()
    print_shell_banner(status)
    env = build_env()
    os.execvpe("/bin/zsh", ["zsh", "-l"], env)
    return 0


def activate_provider(provider_id: str) -> int:
    resolved = resolve_provider(provider_id)
    run_bridge("activate", "--provider-id", resolved)
    return 0


def show_status() -> int:
    run_bridge("verify")
    return 0


def install_shortcuts() -> int:
    local_bin = Path.home() / ".local" / "bin"
    local_bin.mkdir(parents=True, exist_ok=True)

    def write_symlink(name: str, target: Path) -> None:
        link = local_bin / name
        if link.exists() or link.is_symlink():
            try:
                if link.resolve() == target.resolve():
                    print(f"installed={link}")
                    return
            except FileNotFoundError:
                pass
            link.unlink()
        link.symlink_to(target)
        print(f"installed={link} -> {target}")

    wrappers = {
        "or-use": f"#!/bin/zsh\nexec python3 {shlex.quote(str(REMOTE_SELF))} model \"$@\"\n",
        "or-status": f"#!/bin/zsh\nexec python3 {shlex.quote(str(REMOTE_SELF))} status\n",
    }
    for name, content in wrappers.items():
        target = local_bin / name
        target.write_text(content, encoding="utf-8")
        target.chmod(0o755)
        print(f"installed={target}")

    for tool in ("codex", "claude", "gemini"):
        resolved = resolve_cli_path(tool)
        if resolved is None:
            print(f"skipped={tool} (missing on PATH)")
            continue
        write_symlink(tool, resolved)
    return 0


def exec_cli(tool: str, args: Sequence[str]) -> int:
    enter_workspace()
    path = resolve_cli_path(tool)
    if path is None:
        fallback = CLI_PATHS[tool]
        raise FileNotFoundError(f"Missing CLI for {tool}: {fallback}")
    env = build_env()
    os.execvpe(str(path), [tool, *args], env)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("shell", help="Show status, then enter a login shell.")
    subparsers.add_parser("status", help="Print current OpenRouter provider status.")
    subparsers.add_parser("install-shortcuts", help="Install or-use/or-status into ~/.local/bin.")

    model_parser = subparsers.add_parser("model", help="Activate an OpenRouter provider.")
    model_parser.add_argument("provider_id", help="Provider id or alias, e.g. or-claude4 or kimi.")

    for tool in CLI_PATHS:
        tool_parser = subparsers.add_parser(tool, help=f"Exec {tool} on the remote machine.")
        tool_parser.add_argument("args", nargs=argparse.REMAINDER)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args, extra = parser.parse_known_args(argv)

    if args.command == "shell":
        return exec_login_shell()
    if args.command == "status":
        return show_status()
    if args.command == "install-shortcuts":
        return install_shortcuts()
    if args.command == "model":
        return activate_provider(args.provider_id)
    if args.command in CLI_PATHS:
        forwarded = list(getattr(args, "args", []))
        forwarded.extend(extra)
        return exec_cli(args.command, forwarded)

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
