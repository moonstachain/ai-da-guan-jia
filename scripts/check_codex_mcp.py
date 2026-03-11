#!/usr/bin/env python3
"""Check Codex MCP readiness for the adopted server set."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


CODEX_CONFIG = Path.home() / ".codex" / "config.toml"
CODEX_BIN = Path("/Applications/Codex.app/Contents/Resources/codex")


def resolve_node() -> str | None:
    explicit = os.getenv("YUANLI_NODE_BIN", "").strip()
    if explicit:
        path = Path(explicit).expanduser()
        if path.exists() and os.access(path, os.X_OK):
            return str(path)
        return None
    which_value = shutil.which("node")
    if which_value:
        return which_value
    candidates = [
        Path.home() / ".local" / "bin" / "node",
    ]
    for base in [Path.home() / ".local" / "lib", Path.home() / ".local"]:
        if base.exists():
            candidates.extend(sorted(base.glob("node-v*/bin/node"), reverse=True))
    for candidate in candidates:
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def read_mcp(name: str) -> dict[str, object]:
    cmd = [str(CODEX_BIN), "mcp", "get", name, "--json"]
    completed = subprocess.run(cmd, capture_output=True, text=True)
    if completed.returncode != 0:
        return {"name": name, "ok": False, "error": completed.stderr.strip() or completed.stdout.strip()}
    stdout = completed.stdout
    json_start = stdout.find("{")
    if json_start == -1:
        return {"name": name, "ok": False, "error": "No JSON payload in codex mcp get output."}
    payload = json.loads(stdout[json_start:])
    payload["ok"] = True
    return payload


def summarize() -> tuple[list[str], int]:
    lines: list[str] = []
    failures = 0

    lines.append(f"config: {'present' if CODEX_CONFIG.exists() else 'missing'} -> {CODEX_CONFIG}")
    lines.append(f"codex: {'present' if CODEX_BIN.exists() else 'missing'} -> {CODEX_BIN}")

    context7 = read_mcp("context7")
    github = read_mcp("github")
    chrome = read_mcp("chrome-devtools")

    if context7.get("ok"):
        enabled = context7.get("enabled")
        transport = context7.get("transport", {})
        url = transport.get("url") if isinstance(transport, dict) else None
        lines.append(f"context7: {'ok' if enabled else 'disabled'} -> {url}")
    else:
        failures += 1
        lines.append(f"context7: error -> {context7.get('error', 'unknown error')}")

    github_token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN", "").strip()
    if github.get("ok"):
        enabled = github.get("enabled")
        token_state = "present" if github_token else "missing"
        lines.append(f"github: {'ok' if enabled else 'disabled'} -> token {token_state}")
        if not github_token:
            failures += 1
    else:
        failures += 1
        lines.append(f"github: error -> {github.get('error', 'unknown error')}")

    node_bin = resolve_node()
    npx_bin = shutil.which("npx")
    if chrome.get("ok"):
        enabled = chrome.get("enabled")
        lines.append(
            "chrome-devtools: "
            f"{'enabled' if enabled else 'disabled'} -> "
            f"node {'present' if node_bin else 'missing'}, npx {'present' if npx_bin else 'missing'}"
        )
        if enabled and (not node_bin or not npx_bin):
            failures += 1
    else:
        failures += 1
        lines.append(f"chrome-devtools: error -> {chrome.get('error', 'unknown error')}")

    return lines, failures


def main() -> int:
    lines, failures = summarize()
    print("Codex MCP readiness")
    print("===================")
    for line in lines:
        print(f"- {line}")
    if failures:
        print(f"\nResult: needs attention ({failures} item(s))")
        return 1
    print("\nResult: ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
