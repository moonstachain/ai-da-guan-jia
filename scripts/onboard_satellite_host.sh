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
REPO_OVERRIDE=""
EXPECTED_SKILLS_MIN="${EXPECTED_SKILLS_MIN:-20}"
VERIFY_CODEX_APP_MODE="${VERIFY_CODEX_APP_MODE:-warn}"
VERIFY_MCP_MODE="${VERIFY_MCP_MODE:-warn}"
VERIFY_UNIT_TEST_MODE="${VERIFY_UNIT_TEST_MODE:-warn}"
VERIFY_UNIT_TEST_TIMEOUT_SECONDS="${VERIFY_UNIT_TEST_TIMEOUT_SECONDS:-180}"
BROWSER_SKILL_SMOKE_COMMAND=""
EXPECTED_SOURCES=()

usage() {
  cat <<'EOF'
Usage: scripts/onboard_satellite_host.sh --host <lan-host> --workspace-root <path> --source-id <source-id> [options]

Options:
  --host <lan-host>                   Required LAN host or IP.
  --workspace-root <path>             Required remote workspace root.
  --source-id <source-id>             Required stable source id, e.g. satellite-03.
  --user <ssh-user>                   Optional SSH user.
  --port <port>                       SSH port. Default: 22.
  --client-mode <mode>                auto | codex-app | vscode-agent. Default: auto.
  --codex-app-path <path>             Remote Codex.app path. Default: /Applications/Codex.app
  --repo <owner/name>                 Optional GitHub ops repo override.
  --expected-source <source-id>       Additional expected source for aggregate-hub. Repeatable.
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

build_expected_sources() {
  local status_path topology_path seed_path
  status_path="${REPO_ROOT}/work/ai-da-guan-jia/artifacts/ai-da-guan-jia/hub/current/source-status.json"
  topology_path="${REPO_ROOT}/work/ai-da-guan-jia/artifacts/ai-da-guan-jia/hub/source-topology.json"
  seed_path=""
  if [[ -f "$status_path" ]]; then
    seed_path="$status_path"
  elif [[ -f "$topology_path" ]]; then
    seed_path="$topology_path"
  fi
  local discovered=()
  if [[ -n "$seed_path" ]]; then
    discovered=("${(@f)$(python3 - "$seed_path" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for item in payload.get("expected_sources", []):
    print(item)
PY
)}")
  fi
  local merged=("${discovered[@]}" "${EXPECTED_SOURCES[@]}" "main-hub" "$SOURCE_ID")
  local seen=""
  EXPECTED_SOURCES=()
  local item
  for item in "${merged[@]}"; do
    [[ -n "$item" ]] || continue
    if [[ " $seen " == *" $item "* ]]; then
      continue
    fi
    seen="$seen $item"
    EXPECTED_SOURCES+=("$item")
  done
}

result_json_path() {
  printf '%s/onboarding-result.json' "$(artifact_dir)"
}

write_result() {
  python3 - "$@" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

(
    result_path,
    final_status,
    message,
    source_id,
    host,
    user_name,
    workspace_root,
    repo_name,
    expected_sources,
) = sys.argv[1:10]

payload = {
    "completed_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    "final_status": final_status,
    "message": message,
    "source_id": source_id,
    "host": host,
    "user": user_name,
    "workspace_root": workspace_root,
    "repo": repo_name,
    "expected_sources": [item for item in expected_sources.split(",") if item],
    "probe_json": str(Path(result_path).with_name("probe.json")),
    "inventory_json": str(Path(result_path).with_name("inventory.json")),
    "verify_json": str(Path(result_path).with_name("verify.json")),
    "emit_log": str(Path(result_path).with_name("emit-bundle.log")),
    "aggregate_log": str(Path(result_path).with_name("aggregate.log")),
    "audit_log": str(Path(result_path).with_name("audit.log")),
}
Path(result_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(result_path)
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
      --repo)
        REPO_OVERRIDE="${2:-}"
        shift 2
        ;;
      --expected-source)
        EXPECTED_SOURCES+=("${2:-}")
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
  build_expected_sources

  local expected_source_args=()
  local expected_source
  for expected_source in "${EXPECTED_SOURCES[@]}"; do
    expected_source_args+=(--expected-source "$expected_source")
  done

  if ! "${SCRIPT_DIR}/probe_remote_codex_host.sh" \
    --host "$HOST" \
    --source-id "$SOURCE_ID" \
    --user "$USER_NAME" \
    --port "$PORT" \
    --client-mode "$CLIENT_MODE" \
    --codex-app-path "$CODEX_APP_PATH" \
    --output-root "$OUTPUT_ROOT"; then
    write_result "$(result_json_path)" "blocked_needs_user" "probe step failed" "$SOURCE_ID" "$HOST" "$USER_NAME" "$WORKSPACE_ROOT" "$REPO_OVERRIDE" "${(j:,:)EXPECTED_SOURCES}" >/dev/null
    exit 1
  fi

  local resolved_client_mode
  resolved_client_mode="$(python3 - "$(artifact_dir)/probe.json" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(payload.get("client_mode", "auto"))
PY
)"

  if ! "${SCRIPT_DIR}/remote_inventory_codex_host.sh" \
    --host "$HOST" \
    --workspace-root "$WORKSPACE_ROOT" \
    --source-id "$SOURCE_ID" \
    --user "$USER_NAME" \
    --port "$PORT" \
    --client-mode "$resolved_client_mode" \
    --codex-app-path "$CODEX_APP_PATH" \
    --output-root "$OUTPUT_ROOT"; then
    write_result "$(result_json_path)" "blocked_needs_user" "inventory step failed" "$SOURCE_ID" "$HOST" "$USER_NAME" "$WORKSPACE_ROOT" "$REPO_OVERRIDE" "${(j:,:)EXPECTED_SOURCES}" >/dev/null
    exit 1
  fi

  local verify_args=(
    --host "$HOST"
    --workspace-root "$WORKSPACE_ROOT"
    --source-id "$SOURCE_ID"
    --user "$USER_NAME"
    --port "$PORT"
    --client-mode "$resolved_client_mode"
    --expected-skills-min "$EXPECTED_SKILLS_MIN"
    --verify-codex-app-mode "$VERIFY_CODEX_APP_MODE"
    --verify-mcp-mode "$VERIFY_MCP_MODE"
    --verify-unit-test-mode "$VERIFY_UNIT_TEST_MODE"
    --verify-unit-test-timeout "$VERIFY_UNIT_TEST_TIMEOUT_SECONDS"
    --output-root "$OUTPUT_ROOT"
  )
  if [[ -n "$BROWSER_SKILL_SMOKE_COMMAND" ]]; then
    verify_args+=(--browser-smoke-command "$BROWSER_SKILL_SMOKE_COMMAND")
  fi
  if ! "${SCRIPT_DIR}/remote_verify_codex_host.sh" "${verify_args[@]}"; then
    write_result "$(result_json_path)" "failed_partial" "verify step failed" "$SOURCE_ID" "$HOST" "$USER_NAME" "$WORKSPACE_ROOT" "$REPO_OVERRIDE" "${(j:,:)EXPECTED_SOURCES}" >/dev/null
    exit 1
  fi

  local repo_name emit_log aggregate_log audit_log
  repo_name="$REPO_OVERRIDE"
  emit_log="$(artifact_dir)/emit-bundle.log"
  aggregate_log="$(artifact_dir)/aggregate.log"
  audit_log="$(artifact_dir)/audit.log"

  local remote_emit_script
  remote_emit_script=$(cat <<EOF
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
python3 $(printf '%q' "${WORKSPACE_ROOT}/work/ai-da-guan-jia/scripts/ai_da_guan_jia.py") emit-intake-bundle --source-id $(printf '%q' "$SOURCE_ID") --mode full ${REPO_OVERRIDE:+--repo $(printf '%q' "$REPO_OVERRIDE")}
EOF
)

  if ! run_ssh "zsh -lc $(printf '%q' "$remote_emit_script")" >"$emit_log" 2>&1; then
    write_result "$(result_json_path)" "failed_partial" "emit-intake-bundle failed" "$SOURCE_ID" "$HOST" "$USER_NAME" "$WORKSPACE_ROOT" "$REPO_OVERRIDE" "${(j:,:)EXPECTED_SOURCES}" >/dev/null
    exit 1
  fi

  local snapshot_root latest_root remote_source_root snapshot_relative local_source_root
  snapshot_root="$(awk -F': ' '/^snapshot_root:/ {print $2}' "$emit_log" | tail -n 1)"
  latest_root="$(awk -F': ' '/^latest_root:/ {print $2}' "$emit_log" | tail -n 1)"
  [[ -n "$snapshot_root" && -n "$latest_root" ]] || {
    write_result "$(result_json_path)" "failed_partial" "emit-intake-bundle did not return bundle paths" "$SOURCE_ID" "$HOST" "$USER_NAME" "$WORKSPACE_ROOT" "$REPO_OVERRIDE" "${(j:,:)EXPECTED_SOURCES}" >/dev/null
    exit 1
  }
  remote_source_root="$(dirname "$latest_root")"
  snapshot_relative="${snapshot_root#${remote_source_root}/}"
  local_source_root="${REPO_ROOT}/work/ai-da-guan-jia/artifacts/ai-da-guan-jia/hub/outbox/sources/${SOURCE_ID}"
  mkdir -p "$local_source_root"
  rm -rf "${local_source_root}/latest"
  if ! run_ssh "tar -C $(printf '%q' "$remote_source_root") -czf - latest $(printf '%q' "$snapshot_relative")" | tar -C "$local_source_root" -xzf -; then
    write_result "$(result_json_path)" "failed_partial" "bundle pullback failed" "$SOURCE_ID" "$HOST" "$USER_NAME" "$WORKSPACE_ROOT" "$REPO_OVERRIDE" "${(j:,:)EXPECTED_SOURCES}" >/dev/null
    exit 1
  fi

  local bootstrap_cmd aggregate_cmd audit_cmd
  bootstrap_cmd=(
    python3
    "${REPO_ROOT}/work/ai-da-guan-jia/scripts/ai_da_guan_jia.py"
    bootstrap-hub
  )
  aggregate_cmd=(
    python3
    "${REPO_ROOT}/work/ai-da-guan-jia/scripts/ai_da_guan_jia.py"
    aggregate-hub
    --source-id
    main-hub
  )
  audit_cmd=(
    python3
    "${REPO_ROOT}/work/ai-da-guan-jia/scripts/ai_da_guan_jia.py"
    audit-maturity
    --source-id
    main-hub
  )
  if [[ -n "$REPO_OVERRIDE" ]]; then
    bootstrap_cmd+=(--repo "$REPO_OVERRIDE")
    aggregate_cmd+=(--repo "$REPO_OVERRIDE")
    audit_cmd+=(--repo "$REPO_OVERRIDE")
  fi
  bootstrap_cmd+=("${expected_source_args[@]}")
  aggregate_cmd+=("${expected_source_args[@]}")
  audit_cmd+=("${expected_source_args[@]}")

  if ! {
    "${bootstrap_cmd[@]}"
    "${aggregate_cmd[@]}"
  } >"$aggregate_log" 2>&1; then
    write_result "$(result_json_path)" "failed_partial" "hub aggregate failed" "$SOURCE_ID" "$HOST" "$USER_NAME" "$WORKSPACE_ROOT" "$REPO_OVERRIDE" "${(j:,:)EXPECTED_SOURCES}" >/dev/null
    exit 1
  fi

  if ! "${audit_cmd[@]}" >"$audit_log" 2>&1; then
    write_result "$(result_json_path)" "failed_partial" "maturity audit failed" "$SOURCE_ID" "$HOST" "$USER_NAME" "$WORKSPACE_ROOT" "$REPO_OVERRIDE" "${(j:,:)EXPECTED_SOURCES}" >/dev/null
    exit 1
  fi

  local result_path
  result_path="$(write_result "$(result_json_path)" "completed" "satellite onboarding completed" "$SOURCE_ID" "$HOST" "$USER_NAME" "$WORKSPACE_ROOT" "$REPO_OVERRIDE" "${(j:,:)EXPECTED_SOURCES}")"
  printf 'onboarding_result: %s\n' "$result_path"
  printf 'status: completed\n'
}

main "$@"
