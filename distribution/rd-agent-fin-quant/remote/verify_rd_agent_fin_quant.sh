#!/usr/bin/env bash
set -euo pipefail

DEPLOY_ROOT="${DEPLOY_ROOT:-$HOME/rd-agent-fin-quant-poc}"
PROJECT_DIR_NAME="${PROJECT_DIR_NAME:-RD-Agent}"
CONDA_HOME="${CONDA_HOME:-$HOME/miniforge3}"
ENV_NAME="${ENV_NAME:-rdagent}"
DATA_ROOT="${DATA_ROOT:-$HOME/.qlib/qlib_data/cn_data}"
OUTPUT_JSON="${OUTPUT_JSON:-$DEPLOY_ROOT/artifacts/verify-summary.json}"
UI_PORT="${UI_PORT:-19899}"
UI_CHECK_MODE="${UI_CHECK_MODE:-warn}"
HEALTH_CHECK_MODE="${HEALTH_CHECK_MODE:-warn}"
SMOKE_CHECK_MODE="${SMOKE_CHECK_MODE:-warn}"
HEALTH_COMMAND="${HEALTH_COMMAND:-}"
UI_COMMAND="${UI_COMMAND:-}"
SMOKE_COMMAND="${SMOKE_COMMAND:-}"

expand_path() {
  local raw="$1"
  python3 - "$raw" <<'PY'
import os
import sys

raw = sys.argv[1]
print(os.path.expanduser(os.path.expandvars(raw)))
PY
}

usage() {
  cat <<'EOF'
Usage: verify_rd_agent_fin_quant.sh [options]

Options:
  --deploy-root <path>         Parent directory for the remote PoC workspace.
  --project-dir-name <name>    Checkout directory name. Default: RD-Agent.
  --conda-home <path>          Miniforge install path.
  --env-name <name>            Conda environment name. Default: rdagent.
  --data-root <path>           Qlib CN data directory.
  --output-json <path>         JSON output path.
  --ui-port <port>             Loopback port for UI probe.
  --ui-check-mode <mode>       strict | warn | skip.
  --health-check-mode <mode>   strict | warn | skip.
  --smoke-check-mode <mode>    strict | warn | skip.
  --health-command <command>   Optional health-check command.
  --ui-command <command>       Optional UI command.
  --smoke-command <command>    Optional smoke command.
  --help                       Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --deploy-root)
      DEPLOY_ROOT="${2:-}"
      shift 2
      ;;
    --project-dir-name)
      PROJECT_DIR_NAME="${2:-}"
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
    --output-json)
      OUTPUT_JSON="${2:-}"
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
    --help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

DEPLOY_ROOT="$(expand_path "$DEPLOY_ROOT")"
CONDA_HOME="$(expand_path "$CONDA_HOME")"
DATA_ROOT="$(expand_path "$DATA_ROOT")"
OUTPUT_JSON="$(expand_path "$OUTPUT_JSON")"

REPO_DIR="${DEPLOY_ROOT}/${PROJECT_DIR_NAME}"
ENV_FILE="${REPO_DIR}/.env"

conda_run() {
  "${CONDA_HOME}/bin/conda" run -n "$ENV_NAME" "$@"
}

normalize_optional_check() {
  local mode="$1"
  local command_value="$2"
  local repo_dir="$3"
  if [[ "$mode" == "skip" ]]; then
    printf '{"status":"skipped","rc":0,"reason":"mode=skip"}'
    return
  fi
  if [[ -z "$command_value" ]]; then
    printf '{"status":"skipped","rc":0,"reason":"command not provided"}'
    return
  fi
  set +e
  conda_run bash -lc "cd $(printf '%q' "$repo_dir") && $command_value"
  local rc=$?
  set -e
  if [[ "$rc" -eq 0 ]]; then
    printf '{"status":"passed","rc":0}'
    return
  fi
  if [[ "$mode" == "strict" ]]; then
    printf '{"status":"failed","rc":%s}' "$rc"
  else
    printf '{"status":"warn","rc":%s}' "$rc"
  fi
}

probe_ui() {
  local mode="$1"
  local command_value="$2"
  local port="$3"
  local repo_dir="$4"
  if [[ "$mode" == "skip" ]]; then
    printf '{"status":"skipped","rc":0,"reason":"mode=skip"}'
    return
  fi
  if [[ -z "$command_value" ]]; then
    printf '{"status":"skipped","rc":0,"reason":"command not provided"}'
    return
  fi

  local ui_log ui_pid rc
  ui_log="$(mktemp /tmp/rdagent-ui-log-XXXXXX.txt)"
  ui_pid="$(mktemp /tmp/rdagent-ui-pid-XXXXXX.txt)"

  set +e
  conda_run bash -lc "cd $(printf '%q' "$repo_dir") && nohup $command_value > $(printf '%q' "$ui_log") 2>&1 & echo \$! > $(printf '%q' "$ui_pid")"
  rc=$?
  if [[ "$rc" -eq 0 ]]; then
    sleep 12
    python3 - "$port" <<'PY'
import sys
import urllib.request

port = int(sys.argv[1])
with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10) as response:
    if response.status < 200 or response.status >= 500:
        raise SystemExit(1)
PY
    rc=$?
  fi

  if [[ -f "$ui_pid" ]]; then
    local pid
    pid="$(cat "$ui_pid" 2>/dev/null || true)"
    if [[ -n "$pid" ]]; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
  fi
  rm -f "$ui_pid"
  set -e

  if [[ "$rc" -eq 0 ]]; then
    printf '{"status":"passed","rc":0,"log_path":"%s"}' "$ui_log"
    return
  fi
  if [[ "$mode" == "strict" ]]; then
    printf '{"status":"failed","rc":%s,"log_path":"%s"}' "$rc" "$ui_log"
  else
    printf '{"status":"warn","rc":%s,"log_path":"%s"}' "$rc" "$ui_log"
  fi
}

main() {
  mkdir -p "$(dirname "$OUTPUT_JSON")"

  local os_name arch docker_bin docker_info_rc conda_exists env_exists env_file_exists data_exists import_json
  local health_json ui_json smoke_json env_ready="true"
  os_name="$(uname -s)"
  arch="$(uname -m)"
  docker_bin="$(command -v docker || true)"
  docker_info_rc=0
  if [[ -n "$docker_bin" ]]; then
    set +e
    docker info >/dev/null 2>&1
    docker_info_rc=$?
    set -e
  else
    docker_info_rc=127
  fi
  if [[ -x "${CONDA_HOME}/bin/conda" ]]; then
    conda_exists="true"
  else
    conda_exists="false"
  fi
  if [[ "$conda_exists" == "true" ]]; then
    if "${CONDA_HOME}/bin/conda" env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
      env_exists="true"
    else
      env_exists="false"
    fi
  else
    env_exists="false"
  fi
  if [[ -f "$ENV_FILE" ]]; then
    env_file_exists="true"
    if grep -Eq '^OPENAI_API_KEY=$' "$ENV_FILE"; then
      env_ready="false"
    fi
  else
    env_file_exists="false"
    env_ready="false"
  fi
  if find "$DATA_ROOT" -mindepth 1 -print -quit 2>/dev/null | grep -q .; then
    data_exists="true"
  else
    data_exists="false"
  fi

  import_json='{"status":"failed","reason":"conda env unavailable"}'
  if [[ "$conda_exists" == "true" ]]; then
    set +e
    local import_output
    import_output="$(conda_run python -c 'import importlib.util, json; print(json.dumps({"rdagent": importlib.util.find_spec("rdagent") is not None, "pyqlib": importlib.util.find_spec("qlib") is not None}))')"
    local import_rc=$?
    set -e
    if [[ "$import_rc" -eq 0 ]]; then
      local import_output_json
      import_output_json="$(printf '%s\n' "$import_output" | awk 'NF {line=$0} END {print line}')"
      if python3 - "$import_output_json" <<'PY' >/dev/null 2>&1
import json
import sys

json.loads(sys.argv[1])
PY
      then
        import_json="{\"status\":\"passed\",\"modules\":${import_output_json}}"
      else
        import_json="{\"status\":\"failed\",\"reason\":\"import output was not valid json\"}"
      fi
    else
      import_json="{\"status\":\"failed\",\"reason\":\"import check failed\"}"
    fi
  fi

  health_json="$(normalize_optional_check "$HEALTH_CHECK_MODE" "$HEALTH_COMMAND" "$REPO_DIR")"
  smoke_json="$(normalize_optional_check "$SMOKE_CHECK_MODE" "$SMOKE_COMMAND" "$REPO_DIR")"
  ui_json="$(probe_ui "$UI_CHECK_MODE" "$UI_COMMAND" "$UI_PORT" "$REPO_DIR")"

  python3 - "$OUTPUT_JSON" "$os_name" "$arch" "$docker_bin" "$docker_info_rc" "$conda_exists" "$env_exists" "$env_file_exists" "$env_ready" "$data_exists" "$REPO_DIR" "$ENV_FILE" "$DATA_ROOT" "$import_json" "$health_json" "$ui_json" "$smoke_json" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

(
    output_json,
    os_name,
    arch,
    docker_bin,
    docker_info_rc,
    conda_exists,
    env_exists,
    env_file_exists,
    env_ready,
    data_exists,
    repo_dir,
    env_file,
    data_root,
    import_json,
    health_json,
    ui_json,
    smoke_json,
) = sys.argv[1:18]

payload = {
    "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    "host_checks": {
        "os": os_name,
        "arch": arch,
        "docker_bin": docker_bin,
        "docker_info_rc": int(docker_info_rc),
        "conda_exists": conda_exists == "true",
        "env_exists": env_exists == "true",
    },
    "repo": {
        "repo_dir": repo_dir,
        "env_file": env_file,
        "env_file_exists": env_file_exists == "true",
        "env_ready": env_ready == "true",
    },
    "data": {
        "data_root": data_root,
        "data_present": data_exists == "true",
    },
    "imports": json.loads(import_json),
    "optional_checks": {
        "health": json.loads(health_json),
        "ui": json.loads(ui_json),
        "smoke": json.loads(smoke_json),
    },
}

hard_fail = False
if payload["host_checks"]["os"] != "Linux":
    hard_fail = True
if payload["host_checks"]["arch"] not in {"x86_64", "amd64"}:
    hard_fail = True
if not payload["host_checks"]["docker_bin"]:
    hard_fail = True
if payload["host_checks"]["docker_info_rc"] != 0:
    hard_fail = True
if not payload["host_checks"]["conda_exists"]:
    hard_fail = True
if not payload["host_checks"]["env_exists"]:
    hard_fail = True
if not payload["repo"]["env_file_exists"]:
    hard_fail = True
if not payload["repo"]["env_ready"]:
    hard_fail = True
if not payload["data"]["data_present"]:
    hard_fail = True
if payload["imports"]["status"] != "passed":
    hard_fail = True

optional_failed = any(
    entry.get("status") == "failed"
    for entry in payload["optional_checks"].values()
)
optional_warn = any(
    entry.get("status") == "warn"
    for entry in payload["optional_checks"].values()
)

if hard_fail or optional_failed:
    payload["status"] = "failed"
elif optional_warn:
    payload["status"] = "warn"
else:
    payload["status"] = "passed"

Path(output_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(output_json)
PY
}

main
