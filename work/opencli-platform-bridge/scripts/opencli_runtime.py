#!/usr/bin/env python3
from __future__ import annotations

import os
import re
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None


TOKEN_ENV_VAR = "PLAYWRIGHT_MCP_EXTENSION_TOKEN"
CODEX_CONFIG_PATH = Path.home() / ".codex" / "config.toml"
SHELL_RC_PATH = Path.home() / ".zshrc"
TOKEN_EXPORT_RE = re.compile(
    rf"^\s*export\s+{re.escape(TOKEN_ENV_VAR)}=(?P<quote>['\"]?)(?P<value>[^'\"]+)(?P=quote)\s*$"
)


def token_from_env() -> tuple[str, str] | None:
    token = os.environ.get(TOKEN_ENV_VAR, "").strip()
    if token:
        return token, "env"
    return None


def token_from_codex_config(path: Path = CODEX_CONFIG_PATH) -> tuple[str, str] | None:
    if tomllib is None or not path.exists():
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    mcp_servers = data.get("mcp_servers")
    if not isinstance(mcp_servers, dict):
        return None
    playwright = mcp_servers.get("playwright")
    if not isinstance(playwright, dict):
        return None
    env = playwright.get("env")
    if not isinstance(env, dict):
        return None
    token = str(env.get(TOKEN_ENV_VAR) or "").strip()
    if token:
        return token, "codex_config"
    return None


def token_from_shell_rc(path: Path = SHELL_RC_PATH) -> tuple[str, str] | None:
    if not path.exists():
        return None
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            match = TOKEN_EXPORT_RE.match(line)
            if match:
                token = match.group("value").strip()
                if token:
                    return token, "shell_rc"
    except Exception:
        return None
    return None


def resolve_token() -> tuple[str, str] | None:
    for loader in (token_from_env, token_from_codex_config, token_from_shell_rc):
        resolved = loader()
        if resolved:
            return resolved
    return None


def runtime_env() -> tuple[dict[str, str], str]:
    env = os.environ.copy()
    resolved = resolve_token()
    if not resolved:
        return env, "missing"
    token, source = resolved
    env[TOKEN_ENV_VAR] = token
    return env, source

