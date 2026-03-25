#!/usr/bin/env python3
"""Check Task Master AI readiness on this machine."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


DEFAULT_NODE22 = Path("/opt/homebrew/opt/node@22/bin/node")
DEFAULT_NODE22_BIN_DIR = DEFAULT_NODE22.parent
WORKDIR = Path("/tmp/taskmaster-verification")
TIMEOUT_SECONDS = int(os.getenv("TASK_MASTER_CHECK_TIMEOUT_SECONDS", "90"))


def node_major_version(node_bin: str) -> int | None:
    try:
        completed = subprocess.run(
            [node_bin, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return None
    version = completed.stdout.strip().lstrip("v")
    major = version.split(".", 1)[0]
    try:
        return int(major)
    except ValueError:
        return None


def resolve_node() -> str | None:
    explicit = os.getenv("TASK_MASTER_NODE_BIN", "").strip()
    if explicit:
        path = Path(explicit).expanduser()
        if path.exists() and os.access(path, os.X_OK):
            return str(path)
        return None

    current = shutil.which("node")
    if current and (node_major_version(current) or 0) >= 22:
        return current

    if DEFAULT_NODE22.exists() and os.access(DEFAULT_NODE22, os.X_OK):
        return str(DEFAULT_NODE22)

    return None


def run_help(node_bin: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = f"{DEFAULT_NODE22_BIN_DIR}:{env.get('PATH', '')}"
    return subprocess.run(
        ["npx", "-y", "task-master-ai", "--help"],
        cwd=str(WORKDIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
    )


def main() -> int:
    WORKDIR.mkdir(parents=True, exist_ok=True)
    print("Task Master AI readiness")
    print("========================")

    node_bin = resolve_node()
    if not node_bin:
        print(f"- node: missing or below v22 (preferred: {DEFAULT_NODE22})")
        print("\nResult: needs attention (node >= 22 required)")
        return 1

    major = node_major_version(node_bin)
    print(f"- node: {node_bin} (major={major})")

    try:
        completed = run_help(node_bin)
    except subprocess.TimeoutExpired as exc:
        print(f"- task-master-ai --help: timeout after {TIMEOUT_SECONDS}s")
        if exc.stderr:
            print(f"  stderr so far: {exc.stderr[:2000]}")
        print("\nResult: needs attention (help command timed out)")
        return 1

    print(f"- task-master-ai --help: returncode={completed.returncode}")
    if completed.stdout.strip():
        print(f"  stdout: {completed.stdout.strip()[:2000]}")
    if completed.stderr.strip():
        print(f"  stderr: {completed.stderr.strip()[:2000]}")

    if completed.returncode != 0:
        print("\nResult: needs attention (help command failed)")
        return 1

    print("\nResult: ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
