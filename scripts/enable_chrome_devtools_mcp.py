#!/usr/bin/env python3
"""Enable the chrome-devtools MCP entry once runtime prerequisites are ready."""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path


CONFIG_PATH = Path.home() / ".codex" / "config.toml"
SECTION_NAME = "[mcp_servers.chrome-devtools]"


def resolve_node() -> bool:
    return shutil.which("node") is not None


def resolve_npx() -> bool:
    return shutil.which("npx") is not None


def main() -> int:
    if not CONFIG_PATH.exists():
        print(f"Missing Codex config: {CONFIG_PATH}", file=sys.stderr)
        return 1
    if not resolve_node() or not resolve_npx():
        print("chrome-devtools MCP was not enabled: node and npx must both be available.", file=sys.stderr)
        return 1

    text = CONFIG_PATH.read_text(encoding="utf-8")
    if SECTION_NAME not in text:
        print(f"Missing section {SECTION_NAME} in {CONFIG_PATH}", file=sys.stderr)
        return 1

    section_pattern = re.compile(
        r"(\[mcp_servers\.chrome-devtools\]\n(?:[^\[]*\n?)*)",
        re.MULTILINE,
    )
    match = section_pattern.search(text)
    if not match:
        print("Could not locate chrome-devtools MCP section.", file=sys.stderr)
        return 1

    section = match.group(1)
    if "enabled = true" in section:
        print("chrome-devtools MCP is already enabled.")
        return 0
    if "enabled = false" not in section:
        print("chrome-devtools MCP section does not contain enabled = false.", file=sys.stderr)
        return 1

    updated_section = section.replace("enabled = false", "enabled = true", 1)
    updated_text = text[: match.start(1)] + updated_section + text[match.end(1) :]
    CONFIG_PATH.write_text(updated_text, encoding="utf-8")
    print(f"Enabled chrome-devtools MCP in {CONFIG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
