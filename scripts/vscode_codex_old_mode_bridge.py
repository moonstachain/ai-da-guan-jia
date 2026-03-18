#!/usr/bin/env python3
"""Prepare VS Code Codex extension state to match the old-machine API-key mode."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import sqlite3
import subprocess
import sys
import time
from typing import Any


TARGET_EXTENSION = "openai.chatgpt"
TARGET_EXTENSION_VERSION = "26.311.21342"
TARGET_VIEW_KEY = "workbench.view.extension.codexViewContainer.state.hidden"
TARGET_STATE_KEY = "openai.chatgpt"

SANITIZED_STATE = {
    "viewed2025-09-15-nux": True,
    "viewed2025-09-15-apikey-auth-nux": True,
    "persisted-atom-state": {
        "codexCloudAccess": "disabled",
        "prompt-history": [],
        "agent-mode": "full-access",
        "skip-full-access-confirm": True,
    },
    "use-copilot-auth-if-available": False,
    "queued-follow-ups": {},
}

SANITIZED_VIEW = [{"id": "chatgpt.sidebarView", "isHidden": False}]


def now_stamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_command(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, check=False)


def parse_flag_value(argv: list[str], flag: str) -> str:
    for index, token in enumerate(argv):
        if token == flag and index + 1 < len(argv):
            return argv[index + 1]
        if token.startswith(flag + "="):
            return token.split("=", 1)[1]
    return ""


def detect_vscode_process_context() -> dict[str, str]:
    result = run_command(["/bin/sh", "-lc", "ps -ax -ww -o user=,command="])
    context = {
        "owner": "",
        "user_data_dir": "",
        "extensions_dir": "",
        "app_path": "",
    }
    if result.returncode != 0:
        return context
    for line in result.stdout.splitlines():
        if "Visual Studio Code.app/Contents/MacOS/Code" not in line:
            continue
        parts = line.strip().split(None, 1)
        command = parts[1] if len(parts) == 2 else line.strip()
        argv = shlex.split(command)
        app_index = next((index for index, token in enumerate(argv) if token.endswith("/Visual Studio Code.app/Contents/MacOS/Code")), -1)
        if app_index == -1:
            continue
        context["owner"] = parts[0] if len(parts) == 2 else ""
        context["app_path"] = argv[app_index]
        context["user_data_dir"] = parse_flag_value(argv, "--user-data-dir")
        context["extensions_dir"] = parse_flag_value(argv, "--extensions-dir")
        return context
    return context


def detect_vscode_cli(explicit_path: str = "") -> Path:
    candidates = [
        Path(explicit_path).expanduser() if explicit_path else None,
        Path("/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"),
        Path.home() / "Applications" / "Visual Studio Code.app" / "Contents" / "Resources" / "app" / "bin" / "code",
        Path("/Volumes/VS Code/Visual Studio Code.app/Contents/Resources/app/bin/code"),
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    raise FileNotFoundError("Could not find Visual Studio Code CLI")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def backup_path(src: Path, backup_root: Path, home: Path) -> None:
    if not src.exists():
        return
    rel = src.relative_to(home) if src.is_relative_to(home) else src.relative_to(Path("/"))
    dst = backup_root / rel
    ensure_parent(dst)
    shutil.copy2(src, dst)


def path_is_writable(path: Path) -> bool:
    current = path
    while True:
        current_text = str(current)
        try:
            if os.path.exists(current_text):
                return os.access(current_text, os.W_OK)
        except PermissionError:
            return False
        if current == current.parent:
            return False
        current = current.parent


def os_access(path: Path, *, writable: bool = False) -> bool:
    mode = 2 if writable else 4
    return path.exists() and os.access(path, mode)


def find_openai_extension_entry(extensions_json: Path) -> dict[str, Any] | None:
    data = load_json(extensions_json, [])
    if not isinstance(data, list):
        return None
    for item in data:
        if not isinstance(item, dict):
            continue
        ident = ((item.get("identifier") or {}).get("id") or "")
        if ident == TARGET_EXTENSION:
            return item
    return None


def install_extension_if_needed(cli_path: Path, extensions_dir: Path, user_data_dir: Path, expected_version: str) -> tuple[str, str]:
    extensions_json = extensions_dir / "extensions.json"
    entry = find_openai_extension_entry(extensions_json)
    if entry and str(entry.get("version") or "") == expected_version:
        return expected_version, "already_installed"

    base_argv = [str(cli_path)]
    if user_data_dir:
        base_argv.extend(["--user-data-dir", str(user_data_dir)])
    if extensions_dir:
        base_argv.extend(["--extensions-dir", str(extensions_dir)])

    exact = run_command([*base_argv, "--install-extension", f"{TARGET_EXTENSION}@{expected_version}", "--force"])
    if exact.returncode == 0:
        entry = find_openai_extension_entry(extensions_json)
        return str((entry or {}).get("version") or expected_version), "installed_exact"

    latest = run_command([*base_argv, "--install-extension", TARGET_EXTENSION, "--force"])
    if latest.returncode != 0:
        raise RuntimeError(
            "Failed to install VS Code OpenAI extension: "
            + (latest.stderr.strip() or latest.stdout.strip() or "unknown error")
        )
    entry = find_openai_extension_entry(extensions_json)
    return str((entry or {}).get("version") or ""), "installed_latest"


def upsert_state(db_path: Path, key: str, payload: Any) -> None:
    ensure_parent(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS ItemTable (key TEXT UNIQUE ON CONFLICT REPLACE, value BLOB)")
        conn.execute("INSERT OR REPLACE INTO ItemTable (key, value) VALUES (?, ?)", (key, json.dumps(payload, ensure_ascii=False)))
        conn.commit()
    finally:
        conn.close()


def read_state(db_path: Path, key: str) -> Any:
    if not db_path.exists():
        return None
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT value FROM ItemTable WHERE key = ?", (key,)).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return row[0]


def build_context(args: argparse.Namespace) -> dict[str, Path | str]:
    home = Path.home()
    running = detect_vscode_process_context()
    user_data_dir = Path(args.user_data_dir).expanduser() if args.user_data_dir else (
        Path(running["user_data_dir"]).expanduser() if running["user_data_dir"] else home / "Library" / "Application Support" / "Code"
    )
    extensions_dir = Path(args.extensions_dir).expanduser() if args.extensions_dir else (
        Path(running["extensions_dir"]).expanduser() if running["extensions_dir"] else home / ".vscode" / "extensions"
    )
    cli_path = detect_vscode_cli(args.vscode_cli)
    return {
        "home": home,
        "user_data_dir": user_data_dir,
        "extensions_dir": extensions_dir,
        "storage_dir": user_data_dir / "User" / "globalStorage",
        "state_db": user_data_dir / "User" / "globalStorage" / "state.vscdb",
        "storage_json": user_data_dir / "User" / "globalStorage" / "storage.json",
        "extensions_json": extensions_dir / "extensions.json",
        "cli_path": cli_path,
        "running_owner": running["owner"],
        "running_user_data_dir": running["user_data_dir"],
        "running_extensions_dir": running["extensions_dir"],
        "running_app_path": running["app_path"],
    }


def command_prepare(args: argparse.Namespace) -> int:
    ctx = build_context(args)
    home = ctx["home"]
    user_data_dir = ctx["user_data_dir"]
    extensions_dir = ctx["extensions_dir"]
    state_db = ctx["state_db"]
    storage_json = ctx["storage_json"]
    extensions_json = ctx["extensions_json"]

    targets = [user_data_dir, extensions_dir, state_db.parent, storage_json.parent]
    blocked = [str(path) for path in targets if not path_is_writable(Path(path))]
    if blocked:
        raise SystemExit("Not writable: " + ", ".join(blocked))

    backup_root = Path(home) / "backups" / f"vscode-codex-old-mode-{now_stamp()}"
    backup_root.mkdir(parents=True, exist_ok=True)
    for src in [extensions_json, state_db, storage_json]:
        backup_path(Path(src), backup_root, Path(home))

    installed_version, install_mode = install_extension_if_needed(
        Path(ctx["cli_path"]),
        Path(extensions_dir),
        Path(user_data_dir),
        args.extension_version,
    )
    upsert_state(Path(state_db), TARGET_STATE_KEY, SANITIZED_STATE)
    upsert_state(Path(state_db), TARGET_VIEW_KEY, SANITIZED_VIEW)

    print(f"backup_dir={backup_root}")
    print(f"user_data_dir={user_data_dir}")
    print(f"extensions_dir={extensions_dir}")
    print(f"vscode_cli={ctx['cli_path']}")
    print(f"openai_extension_version={installed_version}")
    print(f"install_mode={install_mode}")
    print(f"running_owner={ctx['running_owner']}")
    print(f"running_user_data_dir={ctx['running_user_data_dir']}")
    return 0


def command_verify(args: argparse.Namespace) -> int:
    ctx = build_context(args)
    state = read_state(Path(ctx["state_db"]), TARGET_STATE_KEY)
    view = read_state(Path(ctx["state_db"]), TARGET_VIEW_KEY)
    ext_entry = find_openai_extension_entry(Path(ctx["extensions_json"]))
    print(f"user_data_dir={ctx['user_data_dir']}")
    print(f"extensions_dir={ctx['extensions_dir']}")
    print(f"vscode_cli={ctx['cli_path']}")
    print(f"running_owner={ctx['running_owner']}")
    print(f"running_user_data_dir={ctx['running_user_data_dir']}")
    print(f"openai_extension_present={bool(ext_entry)}")
    if ext_entry:
        print(f"openai_extension_version={ext_entry.get('version')}")
    print(f"openai_state_present={state is not None}")
    if isinstance(state, dict):
        persisted = state.get("persisted-atom-state") if isinstance(state.get("persisted-atom-state"), dict) else {}
        print(f"codex_cloud_access={persisted.get('codexCloudAccess')}")
        print(f"agent_mode={persisted.get('agent-mode')}")
        print(f"skip_full_access_confirm={persisted.get('skip-full-access-confirm')}")
        print(f"viewed_apikey_nux={state.get('viewed2025-09-15-apikey-auth-nux')}")
    print(f"codex_view_present={view is not None}")
    print(f"codex_view={json.dumps(view, ensure_ascii=False) if view is not None else 'missing'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-data-dir", help="Override the VS Code user-data-dir to prepare.")
    parser.add_argument("--extensions-dir", help="Override the VS Code extensions-dir to prepare.")
    parser.add_argument("--vscode-cli", help="Override the VS Code CLI path.")
    parser.add_argument("--extension-version", default=TARGET_EXTENSION_VERSION, help="Preferred openai.chatgpt extension version.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Backup and prepare VS Code Codex extension state.")
    prepare.set_defaults(func=command_prepare)

    verify = subparsers.add_parser("verify", help="Inspect the prepared VS Code Codex extension state.")
    verify.set_defaults(func=command_verify)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
