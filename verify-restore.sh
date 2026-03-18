#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-${SCRIPT_DIR}}"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
EXPECTED_SKILLS_MIN="${EXPECTED_SKILLS_MIN:-100}"
BROWSER_SKILL_SMOKE_CMD="${BROWSER_SKILL_SMOKE_CMD:-}"
VERIFY_CODEX_APP_MODE="${VERIFY_CODEX_APP_MODE:-strict}"
VERIFY_MCP_MODE="${VERIFY_MCP_MODE:-strict}"
VERIFY_UNIT_TEST_MODE="${VERIFY_UNIT_TEST_MODE:-strict}"
VERIFY_UNIT_TEST_TIMEOUT_SECONDS="${VERIFY_UNIT_TEST_TIMEOUT_SECONDS:-180}"
CHECK_CODEX_MCP_SCRIPT_PATH="${CHECK_CODEX_MCP_SCRIPT_PATH:-$WORKSPACE_ROOT/scripts/check_codex_mcp.py}"
WORKSPACE_AI_SCRIPT="${WORKSPACE_ROOT}/work/ai-da-guan-jia/scripts/ai_da_guan_jia.py"
SKILL_AI_SCRIPT="${CODEX_HOME}/skills/ai-da-guan-jia/scripts/ai_da_guan_jia.py"
WORKSPACE_DOCTOR_SCRIPT="${WORKSPACE_ROOT}/work/ai-da-guan-jia/scripts/doctor.py"
LEGACY_WORKSPACE_DOCTOR_SCRIPT="${WORKSPACE_ROOT}/scripts/doctor.py"
SKILL_DOCTOR_SCRIPT="${CODEX_HOME}/skills/ai-da-guan-jia/scripts/doctor.py"
AI_DA_GUAN_JIA_SCRIPT=""
DOCTOR_SCRIPT=""
PYTHON_BIN="${PYTHON_BIN:-}"
NODE_BIN="${NODE_BIN:-}"

FAILURES=0
WARNINGS=0

load_homebrew_env() {
  export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
  if command -v brew >/dev/null 2>&1; then
    eval "$(brew shellenv)"
    local py311_prefix
    local node20_prefix
    py311_prefix="$(brew --prefix python@3.11 2>/dev/null || true)"
    node20_prefix="$(brew --prefix node@20 2>/dev/null || true)"
    if [[ -n "$py311_prefix" ]]; then
      export PATH="$py311_prefix/libexec/bin:$PATH"
    fi
    if [[ -n "$node20_prefix" ]]; then
      export PATH="$node20_prefix/bin:$PATH"
    fi
  fi
}

log() {
  printf '[verify] %s\n' "$1"
}

warn() {
  printf '[verify] WARN: %s\n' "$1"
  WARNINGS=$((WARNINGS + 1))
}

fail() {
  printf '[verify] FAIL: %s\n' "$1" >&2
  FAILURES=$((FAILURES + 1))
}

require_file() {
  local path="$1"
  if [[ ! -e "$path" ]]; then
    fail "missing required path: $path"
  else
    log "found $path"
  fi
}

require_command() {
  local name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    fail "missing command: $name"
  else
    log "found command: $name"
  fi
}

normalize_mode() {
  local value="$1"
  case "$value" in
    strict|warn|skip)
      printf '%s' "$value"
      ;;
    *)
      printf 'strict'
      ;;
  esac
}

handle_check_failure() {
  local mode="$1"
  local message="$2"
  case "$mode" in
    warn)
      warn "$message"
      ;;
    skip)
      log "skip requested: $message"
      ;;
    *)
      fail "$message"
      ;;
  esac
}

first_existing_path() {
  local candidate
  for candidate in "$@"; do
    [[ -n "$candidate" ]] || continue
    if [[ -e "$candidate" ]]; then
      printf '%s' "$candidate"
      return 0
    fi
  done
  return 1
}

check_python_version() {
  "$1" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
}

check_node_version() {
  "$1" - <<'JS'
const major = Number(process.versions.node.split('.')[0]);
process.exit(major >= 20 ? 0 : 1);
JS
}

resolve_python_bin() {
  local candidate resolved
  for candidate in "$PYTHON_BIN" python3 python3.12 python3.11 /usr/local/bin/python3 /opt/homebrew/bin/python3; do
    [[ -n "$candidate" ]] || continue
    resolved="$candidate"
    if [[ "$resolved" != /* ]]; then
      resolved="$(command -v "$resolved" 2>/dev/null || true)"
    fi
    [[ -n "$resolved" && -x "$resolved" ]] || continue
    if check_python_version "$resolved" >/dev/null 2>&1; then
      printf '%s' "$resolved"
      return 0
    fi
  done
  return 1
}

resolve_node_bin() {
  local candidate resolved
  for candidate in "$NODE_BIN" node /usr/local/bin/node /opt/homebrew/bin/node; do
    [[ -n "$candidate" ]] || continue
    resolved="$candidate"
    if [[ "$resolved" != /* ]]; then
      resolved="$(command -v "$resolved" 2>/dev/null || true)"
    fi
    [[ -n "$resolved" && -x "$resolved" ]] || continue
    if check_node_version "$resolved" >/dev/null 2>&1; then
      printf '%s' "$resolved"
      return 0
    fi
  done
  return 1
}

run_unit_tests_with_timeout() {
  "$PYTHON_BIN" - "$WORKSPACE_ROOT/tests" "$VERIFY_UNIT_TEST_TIMEOUT_SECONDS" <<'PY'
import subprocess
import sys

tests_root, timeout_seconds = sys.argv[1], int(sys.argv[2])
try:
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", tests_root],
        timeout=timeout_seconds,
        check=False,
    )
except subprocess.TimeoutExpired:
    print(f"[verify] unit test suite timed out after {timeout_seconds}s", file=sys.stderr)
    raise SystemExit(124)
raise SystemExit(completed.returncode)
PY
}

main() {
  load_homebrew_env

  VERIFY_CODEX_APP_MODE="$(normalize_mode "$VERIFY_CODEX_APP_MODE")"
  VERIFY_MCP_MODE="$(normalize_mode "$VERIFY_MCP_MODE")"
  VERIFY_UNIT_TEST_MODE="$(normalize_mode "$VERIFY_UNIT_TEST_MODE")"
  AI_DA_GUAN_JIA_SCRIPT="$(first_existing_path "$WORKSPACE_AI_SCRIPT" "$SKILL_AI_SCRIPT" || true)"
  DOCTOR_SCRIPT="$(first_existing_path "$WORKSPACE_DOCTOR_SCRIPT" "$LEGACY_WORKSPACE_DOCTOR_SCRIPT" "$SKILL_DOCTOR_SCRIPT" || true)"

  require_command git
  PYTHON_BIN="$(resolve_python_bin || true)"
  NODE_BIN="$(resolve_node_bin || true)"
  if [[ -z "$PYTHON_BIN" ]]; then
    fail "missing python3 >= 3.11"
  else
    log "found command: python3"
    log "using python interpreter: $PYTHON_BIN"
  fi
  if [[ -z "$NODE_BIN" ]]; then
    fail "missing node >= 20"
  else
    log "found command: node"
    log "using node interpreter: $NODE_BIN"
  fi

  if [[ -d /Applications/Codex.app ]]; then
    log "found /Applications/Codex.app"
  else
    handle_check_failure "$VERIFY_CODEX_APP_MODE" "Codex.app is missing in /Applications"
  fi

  log "python3 version is >= 3.11"
  log "node version is >= 20"

  require_file "$CODEX_HOME/config.toml"
  require_file "$CHECK_CODEX_MCP_SCRIPT_PATH"

  if [[ -z "$AI_DA_GUAN_JIA_SCRIPT" ]]; then
    fail "missing ai_da_guan_jia.py in workspace or $CODEX_HOME"
  else
    require_file "$AI_DA_GUAN_JIA_SCRIPT"
  fi

  if [[ -n "$DOCTOR_SCRIPT" ]]; then
    require_file "$DOCTOR_SCRIPT"
    log "running ai-da-guan-jia doctor"
    if ! "$PYTHON_BIN" "$DOCTOR_SCRIPT"; then
      fail "ai-da-guan-jia doctor.py failed"
    fi
  else
    warn "doctor.py is unavailable in workspace and $CODEX_HOME; skipping"
  fi

  if [[ "$VERIFY_MCP_MODE" == "skip" ]]; then
    log "skip requested: check_codex_mcp.py"
  else
    log "running check_codex_mcp.py"
    if ! "$PYTHON_BIN" "$CHECK_CODEX_MCP_SCRIPT_PATH"; then
      handle_check_failure "$VERIFY_MCP_MODE" "check_codex_mcp.py failed"
    fi
  fi

  log "running inventory-skills"
  local inventory_output
  if inventory_output="$("$PYTHON_BIN" "$AI_DA_GUAN_JIA_SCRIPT" inventory-skills)"; then
    log "inventory-skills completed"
    printf '%s\n' "$inventory_output"
    local count
    count="$(printf '%s\n' "$inventory_output" | awk -F': ' '/^count:/ {print $2}' | tail -n 1)"
    if [[ -z "$count" || "$count" -lt "$EXPECTED_SKILLS_MIN" ]]; then
      fail "inventory count below expected minimum (${EXPECTED_SKILLS_MIN})"
    fi
  else
    fail "inventory-skills command failed"
  fi

  if [[ "$VERIFY_UNIT_TEST_MODE" == "skip" ]]; then
    log "skip requested: unit test suite"
  else
    log "running unit test suite (timeout ${VERIFY_UNIT_TEST_TIMEOUT_SECONDS}s)"
    if ! run_unit_tests_with_timeout; then
      handle_check_failure "$VERIFY_UNIT_TEST_MODE" "unit test suite failed"
    fi
  fi

  log "running sample route"
  if ! "$PYTHON_BIN" "$AI_DA_GUAN_JIA_SCRIPT" route --prompt "帮我学一个陌生 API，先读官方说明书和攻略，再决定怎么做"; then
    fail "sample route failed"
  fi

  if [[ -n "$BROWSER_SKILL_SMOKE_CMD" ]]; then
    log "running browser skill smoke command"
    if ! zsh -lc "$BROWSER_SKILL_SMOKE_CMD"; then
      fail "browser skill smoke command failed"
    fi
  else
    log "browser skill smoke skipped (set BROWSER_SKILL_SMOKE_CMD to enable)"
  fi

  if [[ "$FAILURES" -gt 0 ]]; then
    printf '\n[verify] restore verification failed with %s issue(s)\n' "$FAILURES" >&2
    exit 1
  fi

  if [[ "$WARNINGS" -gt 0 ]]; then
    printf '\n[verify] restore verification passed with %s warning(s)\n' "$WARNINGS"
    exit 0
  fi

  printf '\n[verify] restore verification passed\n'
}

main "$@"
