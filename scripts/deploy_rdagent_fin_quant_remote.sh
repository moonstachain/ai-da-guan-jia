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
PYTHON_VERSION="3.10"
DATA_ROOT='$HOME/.qlib/qlib_data/cn_data'
REPO_URL="https://github.com/microsoft/RD-Agent.git"
REPO_REF="main"
OUTPUT_ROOT="${OUTPUT_ROOT:-${REPO_ROOT}/output/rd-agent-fin-quant/remote-hosts}"
ENV_FILE=""
SKIP_APT_INSTALL=0
SKIP_DOCKER_INSTALL=0
SKIP_DATA_PREP=0
SKIP_PYQLIB_INSTALL=0

BUNDLE_ROOT="${REPO_ROOT}/distribution/rd-agent-fin-quant"
REMOTE_BOOTSTRAP="${BUNDLE_ROOT}/remote/bootstrap_rd_agent_fin_quant.sh"
ENV_TEMPLATE="${BUNDLE_ROOT}/rdagent.env.example"

usage() {
  cat <<'EOF'
Usage: scripts/deploy_rdagent_fin_quant_remote.sh --host <host> [options]

Options:
  --host HOSTNAME_OR_IP         Required remote Ubuntu host or IP.
  --user SSH_USER               Optional SSH user.
  --port <port>                 SSH port. Default: 22.
  --workspace-root <path>       Remote parent directory. Default: $HOME/rd-agent-fin-quant-poc
  --conda-home <path>           Remote Miniforge install path. Default: $HOME/miniforge3
  --env-name <name>             Conda env name. Default: rdagent
  --python-version <version>    Conda Python version. Default: 3.10
  --data-root <path>            Remote Qlib CN data path. Default: $HOME/.qlib/qlib_data/cn_data
  --repo-url <url>              RD-Agent Git URL.
  --repo-ref <ref>              Git ref to deploy. Default: main
  --env-file <path>             Optional private .env file to upload after bootstrap.
  --skip-apt-install            Skip apt package installation.
  --skip-docker-install         Skip Docker installation.
  --skip-data-prep              Skip Qlib data preparation.
  --skip-pyqlib-install         Skip explicit pyqlib install during bootstrap.
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

run_ssh_tty() {
  local target
  target="$(target_host)"
  "$SSH_BIN" \
    -tt \
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

write_summary() {
  python3 - "$@" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

(
    output_path,
    host,
    user_name,
    workspace_root,
    conda_home,
    env_name,
    data_root,
    repo_ref,
    env_uploaded,
    remote_summary_path,
    local_log_path,
) = sys.argv[1:12]

payload = {
    "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    "host": host,
    "user": user_name,
    "workspace_root": workspace_root,
    "conda_home": conda_home,
    "conda_env": env_name,
    "data_root": data_root,
    "repo_ref": repo_ref,
    "env_uploaded": env_uploaded == "1",
    "remote_summary_path": remote_summary_path,
    "local_log_path": local_log_path,
}
Path(output_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(output_path)
PY
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
      --python-version)
        PYTHON_VERSION="${2:-}"
        shift 2
        ;;
      --data-root)
        DATA_ROOT="${2:-}"
        shift 2
        ;;
      --repo-url)
        REPO_URL="${2:-}"
        shift 2
        ;;
      --repo-ref)
        REPO_REF="${2:-}"
        shift 2
        ;;
      --env-file)
        ENV_FILE="${2:-}"
        shift 2
        ;;
      --skip-apt-install)
        SKIP_APT_INSTALL=1
        shift
        ;;
      --skip-docker-install)
        SKIP_DOCKER_INSTALL=1
        shift
        ;;
      --skip-data-prep)
        SKIP_DATA_PREP=1
        shift
        ;;
      --skip-pyqlib-install)
        SKIP_PYQLIB_INSTALL=1
        shift
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
  [[ -f "$REMOTE_BOOTSTRAP" ]] || { printf 'missing bundle bootstrap: %s\n' "$REMOTE_BOOTSTRAP" >&2; exit 1; }
  [[ -f "$ENV_TEMPLATE" ]] || { printf 'missing env template: %s\n' "$ENV_TEMPLATE" >&2; exit 1; }
  if [[ -n "$ENV_FILE" && ! -f "$ENV_FILE" ]]; then
    printf 'env file not found: %s\n' "$ENV_FILE" >&2
    exit 1
  fi

  mkdir -p "$(artifact_dir)"

  local remote_root remote_bootstrap remote_template remote_log remote_summary bootstrap_cmd local_log local_summary
  remote_root="/tmp/rd-agent-fin-quant-bootstrap-${HOST//[^A-Za-z0-9._-]/-}-$$"
  remote_bootstrap="${remote_root}/bootstrap.sh"
  remote_template="${remote_root}/rdagent.env.example"
  remote_log="${remote_root}/bootstrap.log"
  remote_summary="${WORKSPACE_ROOT}/artifacts/bootstrap-summary.json"
  local_log="$(artifact_dir)/deploy.log"
  local_summary="$(artifact_dir)/deploy-summary.json"

  upload_remote_file "$REMOTE_BOOTSTRAP" "$remote_bootstrap"
  upload_remote_file "$ENV_TEMPLATE" "$remote_template"

  bootstrap_cmd="chmod +x $(printf '%q' "$remote_bootstrap") && bash $(printf '%q' "$remote_bootstrap") --deploy-root $(printf '%q' "$WORKSPACE_ROOT") --conda-home $(printf '%q' "$CONDA_HOME") --env-name $(printf '%q' "$ENV_NAME") --python-version $(printf '%q' "$PYTHON_VERSION") --data-root $(printf '%q' "$DATA_ROOT") --repo-url $(printf '%q' "$REPO_URL") --repo-ref $(printf '%q' "$REPO_REF") --env-template-path $(printf '%q' "$remote_template")"
  if [[ "$SKIP_APT_INSTALL" -eq 1 ]]; then
    bootstrap_cmd="${bootstrap_cmd} --skip-apt-install"
  fi
  if [[ "$SKIP_DOCKER_INSTALL" -eq 1 ]]; then
    bootstrap_cmd="${bootstrap_cmd} --skip-docker-install"
  fi
  if [[ "$SKIP_DATA_PREP" -eq 1 ]]; then
    bootstrap_cmd="${bootstrap_cmd} --skip-data-prep"
  fi
  if [[ "$SKIP_PYQLIB_INSTALL" -eq 1 ]]; then
    bootstrap_cmd="${bootstrap_cmd} --skip-pyqlib-install"
  fi

  : >"$local_log"
  run_ssh_tty "$bootstrap_cmd 2>&1 | tee $(printf '%q' "$remote_log")" >"$local_log"

  if [[ -n "$ENV_FILE" ]]; then
    upload_remote_file "$ENV_FILE" "${WORKSPACE_ROOT}/RD-Agent/.env"
  fi

  local env_uploaded_flag="0"
  if [[ -n "$ENV_FILE" ]]; then
    env_uploaded_flag="1"
  fi

  write_summary \
    "$local_summary" \
    "$HOST" \
    "$USER_NAME" \
    "$WORKSPACE_ROOT" \
    "$CONDA_HOME" \
    "$ENV_NAME" \
    "$DATA_ROOT" \
    "$REPO_REF" \
    "$env_uploaded_flag" \
    "$remote_summary" \
    "$local_log" >/dev/null

  printf 'deploy_log=%s\n' "$local_log"
  printf 'deploy_summary=%s\n' "$local_summary"
  printf 'remote_summary=%s\n' "$remote_summary"
}

main "$@"
