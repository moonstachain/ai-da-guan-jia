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
OUTPUT_ROOT="${OUTPUT_ROOT:-${REPO_ROOT}/output/ai-da-guan-jia/remote-hosts}"
CODEX_APP_PATH="/Applications/Codex.app"
CLIENT_MODE="auto"
JSON_OUTPUT="0"

usage() {
  cat <<'EOF'
Usage: scripts/probe_remote_codex_host.sh --host <lan-host> --source-id <source-id> [options]

Options:
  --host <lan-host>          Required LAN host or IP.
  --source-id <source-id>    Required stable source id, e.g. satellite-03.
  --user <ssh-user>          Optional SSH user.
  --port <port>              SSH port. Default: 22.
  --client-mode <mode>       auto | codex-app | vscode-agent. Default: auto.
  --codex-app-path <path>    Remote Codex.app path. Default: /Applications/Codex.app
  --output-root <path>       Artifact root. Default: output/ai-da-guan-jia/remote-hosts
  --json                     Print machine-readable JSON after writing probe.json.
  --help                     Show this help.
EOF
}

artifact_key() {
  printf '%s' "${SOURCE_ID:-$HOST}"
}

artifact_dir() {
  printf '%s/%s' "$OUTPUT_ROOT" "$(artifact_key)"
}

artifact_path() {
  printf '%s/probe.json' "$(artifact_dir)"
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

build_payload() {
  python3 - "$@" <<'PY'
import json
import sys
from datetime import datetime, timezone

(
    status,
    message,
    host,
    user_name,
    port,
    source_id,
    client_mode,
    host_reachable,
    ssh_reachable,
    codex_app_present,
    vscode_app_present,
    code_cli_present,
    git_present,
    python3_present,
    node_present,
    os_name,
    arch,
    docker_present,
    docker_version,
    python_version,
    node_version,
    python_ok,
    node_ok,
    missing_commands,
) = sys.argv[1:25]

payload = {
    "checked_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    "status": status,
    "message": message,
    "host": host,
    "user": user_name,
    "port": int(port),
    "source_id": source_id,
    "client_mode": client_mode,
    "host_reachable": host_reachable == "1",
    "ssh_reachable": ssh_reachable == "1",
    "codex_app_present": codex_app_present == "1",
    "vscode_app_present": vscode_app_present == "1",
    "code_cli_present": code_cli_present == "1",
    "git_present": git_present == "1",
    "python3_present": python3_present == "1",
    "node_present": node_present == "1",
    "os_name": os_name,
    "arch": arch,
    "docker_present": docker_present == "1",
    "docker_version": docker_version,
    "python_version": python_version,
    "node_version": node_version,
    "python_ok": python_ok == "1",
    "node_ok": node_ok == "1",
    "missing_commands": [item for item in missing_commands.split(",") if item],
}
print(json.dumps(payload, ensure_ascii=False, indent=2))
PY
}

write_payload() {
  local payload="$1"
  mkdir -p "$(artifact_dir)"
  printf '%s\n' "$payload" > "$(artifact_path)"
  if [[ "$JSON_OUTPUT" == "1" ]]; then
    printf '%s\n' "$payload"
  else
    printf 'probe_json: %s\n' "$(artifact_path)"
    printf 'status: %s\n' "$(printf '%s\n' "$payload" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')"
  fi
}

fail_with_payload() {
  local probe_status="$1"
  local message="$2"
  local payload
  payload="$(build_payload \
    "$probe_status" "$message" "$HOST" "$USER_NAME" "$PORT" "$SOURCE_ID" "$CLIENT_MODE" \
    "0" "0" "0" "0" "0" "0" "0" "0" "" "" "0" "" "" "" "0" "0" "")"
  write_payload "$payload"
  exit 1
}

classify_ssh_failure() {
  local ssh_output="$1"
  if [[ "$ssh_output" == *"Could not resolve hostname"* || "$ssh_output" == *"No route to host"* || "$ssh_output" == *"Connection timed out"* || "$ssh_output" == *"Operation timed out"* ]]; then
    fail_with_payload "host_unreachable" "$ssh_output"
  fi
  if [[ "$ssh_output" == *"Connection refused"* ]]; then
    fail_with_payload "ssh_unreachable" "$ssh_output"
  fi
  if [[ "$ssh_output" == *"Permission denied"* ]]; then
    fail_with_payload "ssh_auth_required" "$ssh_output"
  fi
  fail_with_payload "ssh_unreachable" "$ssh_output"
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

  [[ -n "$HOST" ]] || fail_with_payload "invalid_arguments" "missing required --host"
  [[ -n "$SOURCE_ID" ]] || fail_with_payload "invalid_arguments" "missing required --source-id"

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
printf 'OS_NAME=%s\n' "\$(uname -s 2>/dev/null || printf unknown)"
printf 'ARCH=%s\n' "\$(uname -m 2>/dev/null || printf unknown)"
printf 'HAS_DOCKER=%s\n' "\$(has_cmd docker)"
if command -v docker >/dev/null 2>&1; then
  printf 'DOCKER_VERSION=%s\n' "\$(docker --version 2>/dev/null | head -n 1)"
else
  printf 'DOCKER_VERSION=\n'
fi
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
HAS_CODEX_APP=0
if [[ -d $(printf '%q' "$CODEX_APP_PATH") ]]; then
  HAS_CODEX_APP=1
fi
printf 'HAS_CODEX_APP=%s\n' "\$HAS_CODEX_APP"
HAS_VSCODE_APP=0
if [[ -d "/Applications/Visual Studio Code.app" ]]; then
  HAS_VSCODE_APP=1
fi
printf 'HAS_VSCODE_APP=%s\n' "\$HAS_VSCODE_APP"
printf 'HAS_CODE_CLI=%s\n' "\$(has_cmd code)"
REMOTE_CLIENT_MODE=$(printf '%q' "$CLIENT_MODE")
if [[ "\$REMOTE_CLIENT_MODE" == "auto" ]]; then
  if [[ "\$HAS_VSCODE_APP" == "1" || "\$(has_cmd code)" == "1" ]]; then
    REMOTE_CLIENT_MODE="vscode-agent"
  elif [[ "\$HAS_CODEX_APP" == "1" ]]; then
    REMOTE_CLIENT_MODE="codex-app"
  else
    REMOTE_CLIENT_MODE="unknown"
  fi
fi
printf 'CLIENT_MODE=%s\n' "\$REMOTE_CLIENT_MODE"
EOF
)

  local remote_report
  if ! remote_report="$(run_ssh "zsh -lc $(printf '%q' "$remote_script")" 2>&1)"; then
    classify_ssh_failure "$remote_report"
  fi

  local has_git has_python3 has_node has_codex_app has_vscode_app has_code_cli
  local has_docker os_name arch docker_version
  local python_ok node_ok python_version node_version resolved_client_mode
  has_git="$(report_value "$remote_report" "HAS_GIT")"
  has_python3="$(report_value "$remote_report" "HAS_PYTHON3")"
  has_node="$(report_value "$remote_report" "HAS_NODE")"
  has_docker="$(report_value "$remote_report" "HAS_DOCKER")"
  has_codex_app="$(report_value "$remote_report" "HAS_CODEX_APP")"
  has_vscode_app="$(report_value "$remote_report" "HAS_VSCODE_APP")"
  has_code_cli="$(report_value "$remote_report" "HAS_CODE_CLI")"
  os_name="$(report_value "$remote_report" "OS_NAME")"
  arch="$(report_value "$remote_report" "ARCH")"
  docker_version="$(report_value "$remote_report" "DOCKER_VERSION")"
  python_ok="$(report_value "$remote_report" "PYTHON_OK")"
  node_ok="$(report_value "$remote_report" "NODE_OK")"
  python_version="$(report_value "$remote_report" "PYTHON_VERSION")"
  node_version="$(report_value "$remote_report" "NODE_VERSION")"
  resolved_client_mode="$(report_value "$remote_report" "CLIENT_MODE")"

  local missing_commands=()
  [[ "$has_git" == "1" ]] || missing_commands+=("git")
  [[ "$has_python3" == "1" ]] || missing_commands+=("python3")
  [[ "$has_node" == "1" ]] || missing_commands+=("node")

  local probe_status="ready"
  local message="remote host is ready for satellite onboarding"
  if [[ "${#missing_commands[@]}" -gt 0 || "$python_ok" != "1" || "$node_ok" != "1" ]]; then
    probe_status="missing_prereqs"
    message="missing or outdated prerequisites"
  elif [[ "$resolved_client_mode" == "codex-app" && "$has_codex_app" != "1" ]]; then
    probe_status="missing_client"
    message="Codex.app is missing for codex-app mode"
  elif [[ "$resolved_client_mode" == "vscode-agent" && "$has_vscode_app" != "1" && "$has_code_cli" != "1" ]]; then
    probe_status="missing_client"
    message="Visual Studio Code is missing for vscode-agent mode"
  elif [[ "$resolved_client_mode" == "unknown" && "$has_codex_app" != "1" && "$has_vscode_app" != "1" && "$has_code_cli" != "1" ]]; then
    probe_status="missing_client"
    message="No supported Codex client was detected"
  fi

  local payload
  payload="$(build_payload \
    "$probe_status" "$message" "$HOST" "$USER_NAME" "$PORT" "$SOURCE_ID" "$resolved_client_mode" \
    "1" "1" "$has_codex_app" "$has_vscode_app" "$has_code_cli" "$has_git" "$has_python3" "$has_node" \
    "$os_name" "$arch" "$has_docker" "$docker_version" "$python_version" "$node_version" "$python_ok" "$node_ok" "${(j:,:)missing_commands}")"
  write_payload "$payload"

  if [[ "$probe_status" != "ready" ]]; then
    exit 1
  fi
}

main "$@"
