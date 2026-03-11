#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-${SCRIPT_DIR}}"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
EXPECTED_SKILLS_MIN="${EXPECTED_SKILLS_MIN:-100}"

FAILURES=0

log() {
  printf '[verify] %s\n' "$1"
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

check_python_version() {
  python3 - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
}

check_node_version() {
  node - <<'JS'
const major = Number(process.versions.node.split('.')[0]);
process.exit(major >= 20 ? 0 : 1);
JS
}

main() {
  require_command git
  require_command python3
  require_command node

  if [[ -d /Applications/Codex.app ]]; then
    log "found /Applications/Codex.app"
  else
    fail "Codex.app is missing in /Applications"
  fi

  if ! check_python_version; then
    fail "python3 must be >= 3.11"
  else
    log "python3 version is >= 3.11"
  fi

  if ! check_node_version; then
    fail "node must be >= 20"
  else
    log "node version is >= 20"
  fi

  require_file "$CODEX_HOME/config.toml"
  require_file "$CODEX_HOME/skills/ai-da-guan-jia/scripts/doctor.py"
  require_file "$CODEX_HOME/skills/ai-da-guan-jia/scripts/ai_da_guan_jia.py"
  require_file "$WORKSPACE_ROOT/scripts/check_codex_mcp.py"

  if ! python3 "$CODEX_HOME/skills/ai-da-guan-jia/scripts/doctor.py"; then
    fail "ai-da-guan-jia doctor.py failed"
  fi

  if ! python3 "$WORKSPACE_ROOT/scripts/check_codex_mcp.py"; then
    fail "check_codex_mcp.py failed"
  fi

  local inventory_output
  if inventory_output="$(python3 "$CODEX_HOME/skills/ai-da-guan-jia/scripts/ai_da_guan_jia.py" inventory-skills)"; then
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

  if ! python3 -m unittest discover -s "$WORKSPACE_ROOT/tests"; then
    fail "unit test suite failed"
  fi

  if ! python3 "$CODEX_HOME/skills/ai-da-guan-jia/scripts/ai_da_guan_jia.py" route --prompt "帮我学一个陌生 API，先读官方说明书和攻略，再决定怎么做"; then
    fail "sample route failed"
  fi

  if [[ "$FAILURES" -gt 0 ]]; then
    printf '\n[verify] restore verification failed with %s issue(s)\n' "$FAILURES" >&2
    exit 1
  fi

  printf '\n[verify] restore verification passed\n'
}

main "$@"
