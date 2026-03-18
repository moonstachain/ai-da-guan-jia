#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SSH_BIN="${SSH_BIN:-ssh}"
SSH_TIMEOUT="${SSH_TIMEOUT:-10}"
PORT="22"
HOST=""
USER_NAME=""
WORKSPACE_ROOT='$HOME/rd-agent-fin-quant-poc'
CONDA_HOME='$HOME/miniforge3'
ENV_NAME="rdagent"
DATA_ROOT='$HOME/.qlib/qlib_data/cn_data'
UI_PORT="19899"
OUTPUT_ROOT="${OUTPUT_ROOT:-${REPO_ROOT}/output/rd-agent-fin-quant/remote-hosts}"
UI_CHECK_MODE="warn"
HEALTH_CHECK_MODE="warn"
SMOKE_CHECK_MODE="warn"
HEALTH_COMMAND=""
UI_COMMAND=""
SMOKE_COMMAND=""

BUNDLE_ROOT="${REPO_ROOT}/distribution/rd-agent-fin-quant"
REMOTE_VERIFY="${BUNDLE_ROOT}/remote/verify_rd_agent_fin_quant.sh"

usage() {
  cat <<'EOF'
Usage: scripts/verify_rdagent_fin_quant_remote.sh --host <host> [options]

Options:
  --host HOSTNAME_OR_IP         Required remote Ubuntu host or IP.
  --user SSH_USER               Optional SSH user.
  --port <port>                 SSH port. Default: 22.
  --workspace-root <path>       Remote parent directory. Default: $HOME/rd-agent-fin-quant-poc
  --conda-home <path>           Remote Miniforge install path. Default: $HOME/miniforge3
  --env-name <name>             Conda env name. Default: rdagent
  --data-root <path>            Remote Qlib CN data path. Default: $HOME/.qlib/qlib_data/cn_data
  --ui-port <port>              Loopback port for UI probe. Default: 19899
  --ui-check-mode <mode>        strict | warn | skip. Default: warn
  --health-check-mode <mode>    strict | warn | skip. Default: warn
  --smoke-check-mode <mode>     strict | warn | skip. Default: warn
  --health-command <command>    Optional health-check command.
  --ui-command <command>        Optional UI command.
  --smoke-command <command>     Optional smoke command.
  --output-root <path>          Local artifact root.
  --help                        Show this help.

Note:
  Replace placeholder values with real strings. Do not type angle brackets
  like <host> into zsh commands you intend to run directly.
EOF
}

artifact_dir() {
  printf '%s/%s' "$OUTPUT_ROOT" "${HOST}"
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
      --workspace-root)
        WORKSPACE_ROOT="${2:-}"
        shift 2
        ;;
      --conda-home)
        CONDA_HOME="${2:-}"
        shift 2
        ;;
      --env-name)
        ENV_NAME="${2:-}"
        shift 2
        ;;
      --data-root)
        DATA_ROOT="${2:-}"
        shift 2
        ;;
      --ui-port)
        UI_PORT="${2:-}"
        shift 2
        ;;
      --ui-check-mode)
        UI_CHECK_MODE="${2:-}"
        shift 2
        ;;
      --health-check-mode)
        HEALTH_CHECK_MODE="${2:-}"
        shift 2
        ;;
      --smoke-check-mode)
        SMOKE_CHECK_MODE="${2:-}"
        shift 2
        ;;
      --health-command)
        HEALTH_COMMAND="${2:-}"
        shift 2
        ;;
      --ui-command)
        UI_COMMAND="${2:-}"
        shift 2
        ;;
      --smoke-command)
        SMOKE_COMMAND="${2:-}"
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
  [[ -f "$REMOTE_VERIFY" ]] || { printf 'missing remote verify helper: %s\n' "$REMOTE_VERIFY" >&2; exit 1; }

  mkdir -p "$(artifact_dir)"

  local remote_root remote_verify remote_json local_log local_json verify_cmd
  remote_root="/tmp/rd-agent-fin-quant-verify-${HOST//[^A-Za-z0-9._-]/-}-$$"
  remote_verify="${remote_root}/verify.sh"
  remote_json="${remote_root}/verify-summary.json"
  local_log="$(artifact_dir)/verify.log"
  local_json="$(artifact_dir)/verify.json"

  upload_remote_file "$REMOTE_VERIFY" "$remote_verify"

  verify_cmd="chmod +x $(printf '%q' "$remote_verify") && bash $(printf '%q' "$remote_verify") --deploy-root $(printf '%q' "$WORKSPACE_ROOT") --conda-home $(printf '%q' "$CONDA_HOME") --env-name $(printf '%q' "$ENV_NAME") --data-root $(printf '%q' "$DATA_ROOT") --output-json $(printf '%q' "$remote_json") --ui-port $(printf '%q' "$UI_PORT") --ui-check-mode $(printf '%q' "$UI_CHECK_MODE") --health-check-mode $(printf '%q' "$HEALTH_CHECK_MODE") --smoke-check-mode $(printf '%q' "$SMOKE_CHECK_MODE")"
  if [[ -n "$HEALTH_COMMAND" ]]; then
    verify_cmd="${verify_cmd} --health-command $(printf '%q' "$HEALTH_COMMAND")"
  fi
  if [[ -n "$UI_COMMAND" ]]; then
    verify_cmd="${verify_cmd} --ui-command $(printf '%q' "$UI_COMMAND")"
  fi
  if [[ -n "$SMOKE_COMMAND" ]]; then
    verify_cmd="${verify_cmd} --smoke-command $(printf '%q' "$SMOKE_COMMAND")"
  fi

  : >"$local_log"
  run_ssh "$verify_cmd" >"$local_log"
  run_ssh "cat $(printf '%q' "$remote_json")" >"$local_json"

  printf 'verify_log=%s\n' "$local_log"
  printf 'verify_json=%s\n' "$local_json"
}

main "$@"
