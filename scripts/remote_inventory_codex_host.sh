#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SSH_BIN="${SSH_BIN:-ssh}"
SSH_TIMEOUT="${SSH_TIMEOUT:-5}"
PORT="22"
HOST=""
USER_NAME=""
SOURCE_ID=""
WORKSPACE_ROOT=""
OUTPUT_ROOT="${OUTPUT_ROOT:-${REPO_ROOT}/output/ai-da-guan-jia/remote-hosts}"
CLIENT_MODE="auto"
CODEX_APP_PATH="/Applications/Codex.app"

usage() {
  cat <<'EOF'
Usage: scripts/remote_inventory_codex_host.sh --host <lan-host> --workspace-root <path> --source-id <source-id> [options]

Options:
  --host <lan-host>          Required LAN host or IP.
  --workspace-root <path>    Required remote workspace root.
  --source-id <source-id>    Required stable source id, e.g. satellite-03.
  --user <ssh-user>          Optional SSH user.
  --port <port>              SSH port. Default: 22.
  --client-mode <mode>       auto | codex-app | vscode-agent. Default: auto.
  --codex-app-path <path>    Remote Codex.app path. Default: /Applications/Codex.app
  --output-root <path>       Artifact root. Default: output/ai-da-guan-jia/remote-hosts
  --help                     Show this help.
EOF
}

artifact_dir() {
  printf '%s/%s' "$OUTPUT_ROOT" "$SOURCE_ID"
}

target_host() {
  if [[ -n "$USER_NAME" ]]; then
    printf '%s@%s' "$USER_NAME" "$HOST"
  else
    printf '%s' "$HOST"
  fi
}

run_ssh() {
  local target
  target="$(target_host)"
  "$SSH_BIN" \
    -o BatchMode=yes \
    -o ConnectTimeout="$SSH_TIMEOUT" \
    -o StrictHostKeyChecking=accept-new \
    -p "$PORT" \
    "$target" \
    "$@"
}

classify_ssh_failure() {
  local ssh_output="$1"
  if [[ "$ssh_output" == *"Could not resolve hostname"* || "$ssh_output" == *"No route to host"* || "$ssh_output" == *"Connection timed out"* || "$ssh_output" == *"Operation timed out"* ]]; then
    printf 'inventory failed: %s\n' "$ssh_output" >&2
    exit 1
  fi
  if [[ "$ssh_output" == *"Connection refused"* || "$ssh_output" == *"Permission denied"* ]]; then
    printf 'inventory failed: %s\n' "$ssh_output" >&2
    exit 1
  fi
  printf 'inventory failed: %s\n' "$ssh_output" >&2
  exit 1
}

render_summary() {
  python3 - "$1" "$2" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
target = Path(sys.argv[2])
workspace = payload.get("workspace", {})
codex = payload.get("codex", {})
client = payload.get("client", {})
counts = codex.get("counts", {})
browser = payload.get("browser", {})
mvp_execution = payload.get("mvp_execution", {})
surface_lookup = {
    item.get("surface", ""): item
    for item in browser.get("surfaces", [])
    if isinstance(item, dict)
}

lines = [
    "# Remote Inventory Summary",
    "",
    f"- Source ID: `{payload.get('source_id', '')}`",
    f"- Host: `{payload.get('host', '')}`",
    f"- Status: `{payload.get('status', '')}`",
    f"- Client Mode: `{client.get('client_mode', '')}`",
    f"- Workspace Exists: `{workspace.get('exists', False)}`",
    f"- Workspace Script Exists: `{workspace.get('workspace_ai_script_exists', False)}`",
    f"- Emit Intake Available: `{workspace.get('workspace_emit_available', False)}`",
    f"- Codex Config Exists: `{codex.get('config_exists', False)}`",
    f"- Top-level Skills: `{counts.get('top_level_skills', 0)}`",
    f"- Automations: `{counts.get('automations', 0)}`",
    f"- Session State Present: `{codex.get('state_5_exists', False)}`",
    f"- Archived Sessions Present: `{codex.get('archived_sessions_exists', False)}`",
    f"- Browser MVP Status: `{mvp_execution.get('status', 'unknown')}`",
    f"- Browser Next Ready Surface: `{mvp_execution.get('next_ready_surface', '') or 'none'}`",
    f"- Browser Priority Order: `{' -> '.join(browser.get('priority_order', [])) or 'none'}`",
    f"- Feishu Session: `{surface_lookup.get('feishu', {}).get('status', 'unknown')}`",
    f"- Get笔记 Session: `{surface_lookup.get('get_biji', {}).get('status', 'unknown')}`",
    f"- Other Browser Session: `{surface_lookup.get('other_browser', {}).get('status', 'unknown')}`",
]
target.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

main() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --host)
        HOST="${2:-}"
        shift 2
        ;;
      --workspace-root)
        WORKSPACE_ROOT="${2:-}"
        shift 2
        ;;
      --source-id)
        SOURCE_ID="${2:-}"
        shift 2
        ;;
      --user)
        USER_NAME="${2:-}"
        shift 2
        ;;
      --port)
        PORT="${2:-}"
        shift 2
        ;;
      --client-mode)
        CLIENT_MODE="${2:-}"
        shift 2
        ;;
      --codex-app-path)
        CODEX_APP_PATH="${2:-}"
        shift 2
        ;;
      --output-root)
        OUTPUT_ROOT="${2:-}"
        shift 2
        ;;
      --help)
        usage
        exit 0
        ;;
      *)
        printf 'unknown argument: %s\n' "$1" >&2
        usage >&2
        exit 1
        ;;
    esac
  done

  [[ -n "$HOST" ]] || { usage >&2; exit 1; }
  [[ -n "$WORKSPACE_ROOT" ]] || { usage >&2; exit 1; }
  [[ -n "$SOURCE_ID" ]] || { usage >&2; exit 1; }

  mkdir -p "$(artifact_dir)"

  local remote_script
  remote_script=$(cat <<EOF
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:\$PATH"
if command -v brew >/dev/null 2>&1; then
  eval "\$(brew shellenv)"
  PY311_PREFIX="\$(brew --prefix python@3.11 2>/dev/null || true)"
  NODE20_PREFIX="\$(brew --prefix node@20 2>/dev/null || true)"
  if [[ -n "\$PY311_PREFIX" ]]; then
    export PATH="\$PY311_PREFIX/libexec/bin:\$PATH"
  fi
  if [[ -n "\$NODE20_PREFIX" ]]; then
    export PATH="\$NODE20_PREFIX/bin:\$PATH"
  fi
fi
REMOTE_WORKSPACE_ROOT=$(printf '%q' "$WORKSPACE_ROOT")
REMOTE_SOURCE_ID=$(printf '%q' "$SOURCE_ID")
REMOTE_CLIENT_MODE=$(printf '%q' "$CLIENT_MODE")
REMOTE_CODEX_APP_PATH=$(printf '%q' "$CODEX_APP_PATH")
export REMOTE_WORKSPACE_ROOT REMOTE_SOURCE_ID REMOTE_CLIENT_MODE REMOTE_CODEX_APP_PATH
python3 - <<'PY'
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def run_version(command: list[str]) -> str:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=15, check=False)
    except Exception:
        return ""
    return (completed.stdout or completed.stderr).strip()


def path_has_payload(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_file():
        try:
            return path.stat().st_size > 0
        except OSError:
            return False
    try:
        next(path.iterdir())
        return True
    except (OSError, StopIteration):
        return False


def build_browser_surface(surface: str, profile_paths: list[Path], evidence_paths: list[Path] | None = None) -> dict[str, object]:
    evidence_paths = evidence_paths or []
    ready = any(path_has_payload(path) for path in [*profile_paths, *evidence_paths])
    return {
        "surface": surface,
        "status": "ready" if ready else "blocked_login",
        "profile_paths": [str(path) for path in profile_paths],
        "evidence_paths": [str(path) for path in evidence_paths],
        "human_action_required": [] if ready else ["login_browser"],
    }


workspace_root = Path(os.environ["REMOTE_WORKSPACE_ROOT"]).expanduser()
source_id = os.environ["REMOTE_SOURCE_ID"]
client_mode = os.environ["REMOTE_CLIENT_MODE"]
codex_app_path = Path(os.environ["REMOTE_CODEX_APP_PATH"])
home = Path.home()
codex_home = home / ".codex"
skills_root = codex_home / "skills"
automations_root = codex_home / "automations"
workspace_ai_script = workspace_root / "work" / "ai-da-guan-jia" / "scripts" / "ai_da_guan_jia.py"
skill_ai_script = skills_root / "ai-da-guan-jia" / "scripts" / "ai_da_guan_jia.py"
verify_script = workspace_root / "verify-restore.sh"
vscode_app = Path("/Applications/Visual Studio Code.app")
code_cli = shutil.which("code")
feishu_reader_profile = skills_root / "feishu-reader" / "state" / "browser-profile" / "feishu-reader"
feishu_bitable_profile = skills_root / "feishu-bitable-bridge" / "state" / "browser-profile"
get_biji_profile = skills_root / "get-biji-transcript" / "state" / "browser-profile" / "get-biji"
get_biji_env = skills_root / "ai-da-guan-jia" / "state" / "get-biji.env"
chrome_profile = home / "Library" / "Application Support" / "Google" / "Chrome"

resolved_client_mode = client_mode
if resolved_client_mode == "auto":
    if vscode_app.exists() or code_cli:
        resolved_client_mode = "vscode-agent"
    elif codex_app_path.exists():
        resolved_client_mode = "codex-app"
    else:
        resolved_client_mode = "unknown"

workspace_emit_available = False
if workspace_ai_script.exists():
    completed = subprocess.run(
        [shutil.which("python3") or "python3", str(workspace_ai_script), "emit-intake-bundle", "--help"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    workspace_emit_available = completed.returncode == 0

skill_inventory_count = 0
if skill_ai_script.exists():
    completed = subprocess.run(
        [shutil.which("python3") or "python3", str(skill_ai_script), "inventory-skills"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if completed.returncode == 0:
        for line in completed.stdout.splitlines():
            if line.startswith("count:"):
                try:
                    skill_inventory_count = int(line.split(":", 1)[1].strip())
                except ValueError:
                    skill_inventory_count = 0
                break

top_level_skills = len(list(skills_root.glob("*/SKILL.md"))) + len(list(skills_root.glob(".system/*/SKILL.md")))
automation_count = len([path for path in automations_root.glob("*") if path.is_dir()]) if automations_root.exists() else 0

if not workspace_root.exists():
    status = "inventory_blocked_missing_workspace"
    message = "Remote workspace root is missing."
elif not workspace_ai_script.exists():
    status = "inventory_blocked_missing_workspace_script"
    message = "Workspace ai_da_guan_jia.py is missing."
else:
    status = "inventory_complete"
    message = "Remote inventory completed."

browser_surfaces = [
    build_browser_surface("feishu", [feishu_reader_profile, feishu_bitable_profile]),
    build_browser_surface("get_biji", [get_biji_profile], [get_biji_env]),
    build_browser_surface("other_browser", [chrome_profile]),
]
browser_priority_order = ["feishu", "get_biji", "other_browser"]
ready_surfaces = [item["surface"] for item in browser_surfaces if item.get("status") == "ready"]
blocked_surfaces = [item["surface"] for item in browser_surfaces if item.get("status") != "ready"]
next_ready_surface = next((surface for surface in browser_priority_order if surface in ready_surfaces), "")

payload = {
    "checked_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    "status": status,
    "message": message,
    "source_id": source_id,
    "host": os.uname().nodename,
    "client": {
        "client_mode": resolved_client_mode,
        "codex_app_present": codex_app_path.exists(),
        "vscode_app_present": vscode_app.exists(),
        "code_cli_present": bool(code_cli),
    },
    "workspace": {
        "root": str(workspace_root),
        "exists": workspace_root.exists(),
        "verify_restore_exists": verify_script.exists(),
        "workspace_ai_script_exists": workspace_ai_script.exists(),
        "workspace_emit_available": workspace_emit_available,
    },
    "codex": {
        "home": str(codex_home),
        "exists": codex_home.exists(),
        "config_exists": (codex_home / "config.toml").exists(),
        "state_5_exists": (codex_home / "state_5.sqlite").exists(),
        "sessions_exists": (codex_home / "sessions").exists(),
        "archived_sessions_exists": (codex_home / "archived_sessions").exists(),
        "skill_ai_script_exists": skill_ai_script.exists(),
        "skill_inventory_count": skill_inventory_count,
        "counts": {
            "top_level_skills": top_level_skills,
            "automations": automation_count,
        },
    },
    "toolchain": {
        "python_version": run_version(["python3", "--version"]),
        "node_version": run_version(["node", "--version"]),
        "git_version": run_version(["git", "--version"]),
    },
    "browser": {
        "priority_order": browser_priority_order,
        "ready_surfaces": ready_surfaces,
        "blocked_surfaces": blocked_surfaces,
        "surfaces": browser_surfaces,
    },
    "mvp_execution": {
        "task_kind": "browser_login_execution",
        "executor_source_id": source_id,
        "priority_order": browser_priority_order,
        "next_ready_surface": next_ready_surface,
        "status": "ready" if next_ready_surface else "blocked_needs_user",
        "all_blocked_final_status": "blocked_needs_user",
        "required_human_action": [] if next_ready_surface else ["login_browser_once"],
        "closure_owner": "main-hub",
    },
}
print(json.dumps(payload, ensure_ascii=False, indent=2))
PY
EOF
)

  local inventory_json
  if ! inventory_json="$(run_ssh "zsh -lc $(printf '%q' "$remote_script")" 2>&1)"; then
    classify_ssh_failure "$inventory_json"
  fi

  local inventory_path summary_path
  inventory_path="$(artifact_dir)/inventory.json"
  summary_path="$(artifact_dir)/inventory-summary.md"
  printf '%s\n' "$inventory_json" > "$inventory_path"
  render_summary "$inventory_path" "$summary_path"

  printf 'inventory_json: %s\n' "$inventory_path"
  printf 'inventory_summary: %s\n' "$summary_path"
  printf 'status: %s\n' "$(python3 - "$inventory_path" <<'PY'
import json
import sys
from pathlib import Path
print(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["status"])
PY
)"

  if [[ "$(python3 - "$inventory_path" <<'PY'
import json
import sys
from pathlib import Path
print(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["status"])
PY
)" != "inventory_complete" ]]; then
    exit 1
  fi
}

main "$@"
