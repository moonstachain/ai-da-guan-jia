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
EXPECTED_SKILLS_MIN="${EXPECTED_SKILLS_MIN:-20}"
VERIFY_CODEX_APP_MODE="${VERIFY_CODEX_APP_MODE:-warn}"
VERIFY_MCP_MODE="${VERIFY_MCP_MODE:-warn}"
VERIFY_UNIT_TEST_MODE="${VERIFY_UNIT_TEST_MODE:-warn}"
VERIFY_UNIT_TEST_TIMEOUT_SECONDS="${VERIFY_UNIT_TEST_TIMEOUT_SECONDS:-180}"
BROWSER_SKILL_SMOKE_COMMAND=""

usage() {
  cat <<'EOF'
Usage: scripts/remote_verify_codex_host.sh --host <lan-host> --workspace-root <path> --source-id <source-id> [options]

Options:
  --host <lan-host>                   Required LAN host or IP.
  --workspace-root <path>             Required remote workspace root.
  --source-id <source-id>             Required stable source id, e.g. satellite-03.
  --user <ssh-user>                   Optional SSH user.
  --port <port>                       SSH port. Default: 22.
  --client-mode <mode>                auto | codex-app | vscode-agent. Default: auto.
  --expected-skills-min <count>       Expected minimum inventory count. Default: 20.
  --verify-codex-app-mode <mode>      strict | warn | skip. Default: warn.
  --verify-mcp-mode <mode>            strict | warn | skip. Default: warn.
  --verify-unit-test-mode <mode>      strict | warn | skip. Default: warn.
  --verify-unit-test-timeout <sec>    Unit test timeout seconds. Default: 180.
  --browser-smoke-command <command>   Optional browser smoke command run on remote host.
  --output-root <path>                Artifact root. Default: output/ai-da-guan-jia/remote-hosts
  --help                              Show this help.
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

upload_remote_file() {
  local local_path="$1"
  local remote_path="$2"
  run_ssh "mkdir -p $(printf '%q' "$(dirname "$remote_path")")"
  run_ssh "cat > $(printf '%q' "$remote_path")" <"$local_path"
}

write_payload() {
  python3 - "$@" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

(
    verify_status,
    source_id,
    host,
    user_name,
    workspace_root,
    returncode,
    log_path,
    client_mode,
    codex_mode,
    mcp_mode,
    unit_test_mode,
    unit_test_timeout_seconds,
    payload_path,
) = sys.argv[1:14]
payload = {
    "checked_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    "status": verify_status,
    "source_id": source_id,
    "host": host,
    "user": user_name,
    "workspace_root": workspace_root,
    "returncode": int(returncode),
    "log_path": log_path,
    "client_mode": client_mode,
    "verify_modes": {
        "codex_app": codex_mode,
        "mcp": mcp_mode,
        "unit_tests": unit_test_mode,
    },
    "unit_test_timeout_seconds": int(unit_test_timeout_seconds),
}
Path(payload_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(payload_path)
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
      --expected-skills-min)
        EXPECTED_SKILLS_MIN="${2:-}"
        shift 2
        ;;
      --verify-codex-app-mode)
        VERIFY_CODEX_APP_MODE="${2:-}"
        shift 2
        ;;
      --verify-mcp-mode)
        VERIFY_MCP_MODE="${2:-}"
        shift 2
        ;;
      --verify-unit-test-mode)
        VERIFY_UNIT_TEST_MODE="${2:-}"
        shift 2
        ;;
      --verify-unit-test-timeout)
        VERIFY_UNIT_TEST_TIMEOUT_SECONDS="${2:-}"
        shift 2
        ;;
      --browser-smoke-command)
        BROWSER_SKILL_SMOKE_COMMAND="${2:-}"
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

  [[ -n "$HOST" && -n "$WORKSPACE_ROOT" && -n "$SOURCE_ID" ]] || { usage >&2; exit 1; }

  mkdir -p "$(artifact_dir)"
  local verify_log verify_json remote_env remote_script rc verify_status payload_path
  local remote_verify_root remote_verify_script remote_mcp_script
  verify_log="$(artifact_dir)/verify.log"
  verify_json="$(artifact_dir)/verify.json"
  remote_verify_root="/tmp/ai-da-guan-jia-verify-${SOURCE_ID}-$$"
  remote_verify_script="${remote_verify_root}/verify-restore.sh"
  remote_mcp_script="${remote_verify_root}/scripts/check_codex_mcp.py"

  local effective_codex_mode effective_mcp_mode
  effective_codex_mode="$VERIFY_CODEX_APP_MODE"
  effective_mcp_mode="$VERIFY_MCP_MODE"
  if [[ "$CLIENT_MODE" == "vscode-agent" ]]; then
    if [[ "$effective_codex_mode" == "warn" ]]; then
      effective_codex_mode="skip"
    fi
    if [[ "$effective_mcp_mode" == "warn" ]]; then
      effective_mcp_mode="skip"
    fi
  fi

  remote_env="EXPECTED_SKILLS_MIN=$(printf '%q' "$EXPECTED_SKILLS_MIN") WORKSPACE_ROOT=$(printf '%q' "$WORKSPACE_ROOT") VERIFY_CODEX_APP_MODE=$(printf '%q' "$effective_codex_mode") VERIFY_MCP_MODE=$(printf '%q' "$effective_mcp_mode") VERIFY_UNIT_TEST_MODE=$(printf '%q' "$VERIFY_UNIT_TEST_MODE") VERIFY_UNIT_TEST_TIMEOUT_SECONDS=$(printf '%q' "$VERIFY_UNIT_TEST_TIMEOUT_SECONDS") CHECK_CODEX_MCP_SCRIPT_PATH=$(printf '%q' "$remote_mcp_script")"
  if [[ -n "$BROWSER_SKILL_SMOKE_COMMAND" ]]; then
    remote_env="$remote_env BROWSER_SKILL_SMOKE_CMD=$(printf '%q' "$BROWSER_SKILL_SMOKE_COMMAND")"
  fi
  remote_script="cd $(printf '%q' "$WORKSPACE_ROOT") && $remote_env $(printf '%q' "$remote_verify_script")"

  : >"$verify_log"
  set +e
  (
    upload_remote_file "${REPO_ROOT}/verify-restore.sh" "$remote_verify_script"
    upload_remote_file "${REPO_ROOT}/scripts/check_codex_mcp.py" "$remote_mcp_script"
    run_ssh "chmod +x $(printf '%q' "$remote_verify_script")"
    run_ssh "zsh -lc $(printf '%q' "$remote_script")"
    verify_rc=$?
    run_ssh "rm -rf $(printf '%q' "$remote_verify_root")" >/dev/null 2>&1 || true
    exit "$verify_rc"
  ) >"$verify_log" 2>&1
  rc=$?
  set -e

  if [[ "$rc" -eq 0 ]]; then
    verify_status="verify_complete"
  else
    verify_status="verify_failed"
  fi

  payload_path="$(write_payload "$verify_status" "$SOURCE_ID" "$HOST" "$USER_NAME" "$WORKSPACE_ROOT" "$rc" "$verify_log" "$CLIENT_MODE" "$effective_codex_mode" "$effective_mcp_mode" "$VERIFY_UNIT_TEST_MODE" "$VERIFY_UNIT_TEST_TIMEOUT_SECONDS" "$verify_json")"
  printf 'verify_log: %s\n' "$verify_log"
  printf 'verify_json: %s\n' "$payload_path"
  printf 'status: %s\n' "$verify_status"

  if [[ "$rc" -ne 0 ]]; then
    exit "$rc"
  fi
}

main "$@"
