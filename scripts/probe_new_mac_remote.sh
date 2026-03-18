#!/bin/zsh
set -euo pipefail

SSH_BIN="${SSH_BIN:-ssh}"
SSH_TIMEOUT="${SSH_TIMEOUT:-5}"
PORT="22"
HOST=""
USER_NAME=""
CODEX_APP_PATH="/Applications/Codex.app"
JSON_OUTPUT="0"

usage() {
  cat <<'EOF'
Usage: scripts/probe_new_mac_remote.sh --host <lan-host> [options]

Options:
  --host <lan-host>          Required LAN host or IP.
  --user <ssh-user>          Optional SSH user.
  --port <port>              SSH port. Default: 22.
  --codex-app-path <path>    Remote Codex.app path. Default: /Applications/Codex.app
  --json                     Print machine-readable JSON.
  --help                     Show this help.
EOF
}

log() {
  printf '[probe] %s\n' "$1"
}

fail_with_status() {
  local probe_status="$1"
  local message="$2"
  if [[ "$JSON_OUTPUT" == "1" ]]; then
    python3 - "$probe_status" "$message" <<'PY'
import json
import sys
status, message = sys.argv[1:3]
print(json.dumps({"status": status, "message": message}, ensure_ascii=False, indent=2))
PY
  else
    printf '[probe] %s: %s\n' "$probe_status" "$message" >&2
  fi
  exit 1
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
    fail_with_status "host_unreachable" "$ssh_output"
  fi
  if [[ "$ssh_output" == *"Connection refused"* ]]; then
    fail_with_status "ssh_unreachable" "$ssh_output"
  fi
  if [[ "$ssh_output" == *"Permission denied"* ]]; then
    fail_with_status "ssh_auth_required" "$ssh_output"
  fi
  fail_with_status "ssh_unreachable" "$ssh_output"
}

report_value() {
  local raw_report="$1"
  local key="$2"
  printf '%s\n' "$raw_report" | awk -F'=' -v needle="$key" '$1 == needle {print $2; exit}'
}

main() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --host)
        HOST="${2:-}"
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
      --codex-app-path)
        CODEX_APP_PATH="${2:-}"
        shift 2
        ;;
      --json)
        JSON_OUTPUT="1"
        shift
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

  [[ -n "$HOST" ]] || fail_with_status "invalid_arguments" "missing required --host"

  local ssh_probe_output
  if ! ssh_probe_output="$(run_ssh "printf connected" 2>&1)"; then
    classify_ssh_failure "$ssh_probe_output"
  fi

  if [[ "$ssh_probe_output" != *"connected"* ]]; then
    classify_ssh_failure "$ssh_probe_output"
  fi

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
has_cmd() { command -v "\$1" >/dev/null 2>&1 && printf '1' || printf '0'; }
printf 'HAS_GIT=%s\n' "\$(has_cmd git)"
printf 'HAS_PYTHON3=%s\n' "\$(has_cmd python3)"
if command -v python3 >/dev/null 2>&1; then
  python3 - <<'PY'
import sys
print(f"PYTHON_VERSION={sys.version.split()[0]}")
print("PYTHON_OK=1" if sys.version_info >= (3, 11) else "PYTHON_OK=0")
PY
else
  printf 'PYTHON_VERSION=\n'
  printf 'PYTHON_OK=0\n'
fi
printf 'HAS_NODE=%s\n' "\$(has_cmd node)"
if command -v node >/dev/null 2>&1; then
  node - <<'JS'
const version = process.versions.node;
const major = Number(version.split('.')[0]);
console.log("NODE_VERSION=" + version);
console.log("NODE_OK=" + (major >= 20 ? 1 : 0));
JS
else
  printf 'NODE_VERSION=\n'
  printf 'NODE_OK=0\n'
fi
if [[ -d $(printf '%q' "$CODEX_APP_PATH") ]]; then
  printf 'HAS_CODEX_APP=1\n'
else
  printf 'HAS_CODEX_APP=0\n'
fi
EOF
)

  local remote_command
  remote_command="zsh -lc $(printf '%q' "$remote_script")"

  local remote_report
  if ! remote_report="$(run_ssh "$remote_command" 2>&1)"; then
    classify_ssh_failure "$remote_report"
  fi

  local has_git
  local has_python3
  local has_node
  local has_codex_app
  local python_ok
  local node_ok
  local python_version
  local node_version
  has_git="$(report_value "$remote_report" "HAS_GIT")"
  has_python3="$(report_value "$remote_report" "HAS_PYTHON3")"
  has_node="$(report_value "$remote_report" "HAS_NODE")"
  has_codex_app="$(report_value "$remote_report" "HAS_CODEX_APP")"
  python_ok="$(report_value "$remote_report" "PYTHON_OK")"
  node_ok="$(report_value "$remote_report" "NODE_OK")"
  python_version="$(report_value "$remote_report" "PYTHON_VERSION")"
  node_version="$(report_value "$remote_report" "NODE_VERSION")"

  local missing_commands=()
  [[ "$has_git" == "1" ]] || missing_commands+=("git")
  [[ "$has_python3" == "1" ]] || missing_commands+=("python3")
  [[ "$has_node" == "1" ]] || missing_commands+=("node")

  local probe_status="ready"
  local message="remote host is ready for restore bootstrap"
  if [[ "${#missing_commands[@]}" -gt 0 || "$python_ok" != "1" || "$node_ok" != "1" ]]; then
    probe_status="missing_prereqs"
    message="missing or outdated prerequisites"
  elif [[ "$has_codex_app" != "1" ]]; then
    probe_status="missing_codex_app"
    message="Codex.app is missing"
  fi

  if [[ "$JSON_OUTPUT" == "1" ]]; then
    python3 - "$probe_status" "$message" "$python_version" "$node_version" "$has_codex_app" "$has_git" "$has_python3" "$has_node" "$python_ok" "$node_ok" "${(j:,:)missing_commands}" <<'PY'
import json
import sys

status, message, python_version, node_version, has_codex_app, has_git, has_python3, has_node, python_ok, node_ok, missing_commands = sys.argv[1:]
payload = {
    "status": status,
    "message": message,
    "host_reachable": True,
    "ssh_reachable": True,
    "codex_app_present": has_codex_app == "1",
    "git_present": has_git == "1",
    "python3_present": has_python3 == "1",
    "node_present": has_node == "1",
    "python_version": python_version,
    "node_version": node_version,
    "python_ok": python_ok == "1",
    "node_ok": node_ok == "1",
    "missing_commands": [x for x in missing_commands.split(",") if x],
}
print(json.dumps(payload, ensure_ascii=False, indent=2))
PY
    exit 0
  fi

  log "host reachable: yes"
  log "ssh reachable: yes"
  log "git present: ${has_git:-0}"
  log "python3 present: ${has_python3:-0} (${python_version:-unknown})"
  log "node present: ${has_node:-0} (${node_version:-unknown})"
  log "Codex.app present: ${has_codex_app:-0}"
  if [[ "$probe_status" == "ready" ]]; then
    log "status: ready"
  else
    log "status: $probe_status"
    log "message: $message"
    if [[ "${#missing_commands[@]}" -gt 0 ]]; then
      log "missing commands: ${(j:, :)missing_commands}"
    fi
  fi
}

main "$@"
