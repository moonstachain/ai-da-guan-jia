#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

from opencli_runtime import resolve_token


def check_command(name: str) -> dict:
    path = shutil.which(name)
    result = {"command": name, "found": bool(path), "path": path}
    if not path:
        return result
    try:
        completed = subprocess.run(
            [name, "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        result["version"] = (completed.stdout or completed.stderr).strip().splitlines()[:1]
    except Exception as exc:  # pragma: no cover
        result["error"] = str(exc)
    return result


def main() -> int:
    resolved = resolve_token()
    report = {
        "node": check_command("node"),
        "npm": check_command("npm"),
        "opencli": check_command("opencli"),
        "playwright_mcp_extension_token_present": bool(resolved),
        "playwright_mcp_extension_token_source": resolved[1] if resolved else "missing",
    }

    opencli_path = report["opencli"].get("path")
    if opencli_path:
        try:
            env = os.environ.copy()
            if resolved:
                env["PLAYWRIGHT_MCP_EXTENSION_TOKEN"] = resolved[0]
            completed = subprocess.run(
                [opencli_path, "list", "-f", "json"],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            report["opencli_list_exit_code"] = completed.returncode
            if completed.returncode == 0 and completed.stdout.strip():
                parsed = json.loads(completed.stdout)
                if isinstance(parsed, list):
                    report["registry_entries"] = len(parsed)
                else:
                    report["registry_type"] = type(parsed).__name__
            else:
                report["opencli_list_stderr"] = completed.stderr.strip()
        except Exception as exc:  # pragma: no cover
            report["opencli_probe_error"] = str(exc)

    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
