#!/usr/bin/env bash
set -euo pipefail

DEPLOY_ROOT="${DEPLOY_ROOT:-$HOME/rd-agent-fin-quant-poc}"
REPO_URL="${REPO_URL:-https://github.com/microsoft/RD-Agent.git}"
REPO_REF="${REPO_REF:-main}"
PROJECT_DIR_NAME="${PROJECT_DIR_NAME:-RD-Agent}"
CONDA_HOME="${CONDA_HOME:-$HOME/miniforge3}"
ENV_NAME="${ENV_NAME:-rdagent}"
PYTHON_VERSION="${PYTHON_VERSION:-3.10}"
DATA_ROOT="${DATA_ROOT:-$HOME/.qlib/qlib_data/cn_data}"
ENV_TEMPLATE_PATH="${ENV_TEMPLATE_PATH:-}"
QLIB_CN_COMMUNITY_DATA_URL="${QLIB_CN_COMMUNITY_DATA_URL:-https://github.com/chenditc/investment_data/releases/latest/download/qlib_bin.tar.gz}"
SKIP_APT_INSTALL=0
SKIP_DOCKER_INSTALL=0
SKIP_DATA_PREP=0
INSTALL_PYQLIB=1

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
Usage: bootstrap_rd_agent_fin_quant.sh [options]

Options:
  --deploy-root <path>         Parent directory for the remote PoC workspace.
  --repo-url <url>             RD-Agent git URL.
  --repo-ref <ref>             Git ref to checkout. Default: main.
  --project-dir-name <name>    Checkout directory name. Default: RD-Agent.
  --conda-home <path>          Miniforge install path.
  --env-name <name>            Conda environment name. Default: rdagent.
  --python-version <version>   Conda Python version. Default: 3.10.
  --data-root <path>           Qlib CN data directory.
  --env-template-path <path>   Uploaded .env template to copy into the repo.
  --community-data-url <url>   Optional fallback tarball URL for Qlib CN data.
  --skip-apt-install           Skip apt package installation.
  --skip-docker-install        Skip Docker installation and group wiring.
  --skip-data-prep             Skip Qlib CN data preparation.
  --skip-pyqlib-install        Skip explicit pyqlib install step.
  --help                       Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --deploy-root)
      DEPLOY_ROOT="${2:-}"
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
    --python-version)
      PYTHON_VERSION="${2:-}"
      shift 2
      ;;
    --data-root)
      DATA_ROOT="${2:-}"
      shift 2
      ;;
    --env-template-path)
      ENV_TEMPLATE_PATH="${2:-}"
      shift 2
      ;;
    --community-data-url)
      QLIB_CN_COMMUNITY_DATA_URL="${2:-}"
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
      INSTALL_PYQLIB=0
      shift
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
if [[ -n "$ENV_TEMPLATE_PATH" ]]; then
  ENV_TEMPLATE_PATH="$(expand_path "$ENV_TEMPLATE_PATH")"
fi

REPO_DIR="${DEPLOY_ROOT}/${PROJECT_DIR_NAME}"
BOOTSTRAP_STATE_DIR="${DEPLOY_ROOT}/artifacts"
SUMMARY_PATH="${BOOTSTRAP_STATE_DIR}/bootstrap-summary.json"
NEEDS_DOCKER_RELOGIN=0
DATA_STATUS="skipped"

sudo_run() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

ensure_apt_packages() {
  if [[ "$SKIP_APT_INSTALL" -eq 1 ]]; then
    return
  fi
  sudo_run apt-get update
  sudo_run apt-get install -y \
    bash \
    build-essential \
    ca-certificates \
    curl \
    git \
    libffi-dev \
    libssl-dev \
    pkg-config \
    wget \
    zstd
}

ensure_docker() {
  if [[ "$SKIP_DOCKER_INSTALL" -eq 1 ]]; then
    return
  fi
  if ! command -v docker >/dev/null 2>&1; then
    sudo_run apt-get install -y docker.io docker-compose-plugin
  else
    sudo_run apt-get install -y docker.io docker-compose-plugin >/dev/null 2>&1 || true
  fi
  if ! getent group docker >/dev/null 2>&1; then
    sudo_run groupadd docker
  fi
  if ! id -nG "$USER" | tr ' ' '\n' | grep -qx docker; then
    sudo_run usermod -aG docker "$USER"
    NEEDS_DOCKER_RELOGIN=1
  fi
  sudo_run systemctl enable --now docker >/dev/null 2>&1 || true
}

ensure_miniforge() {
  if [[ -x "${CONDA_HOME}/bin/conda" ]]; then
    return
  fi
  local installer
  installer="$(mktemp /tmp/miniforge-XXXXXX.sh)"
  curl -L \
    https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh \
    -o "$installer"
  bash "$installer" -b -p "$CONDA_HOME"
  rm -f "$installer"
}

ensure_repo() {
  mkdir -p "${DEPLOY_ROOT}" "${DEPLOY_ROOT}/logs" "${DEPLOY_ROOT}/state" "${BOOTSTRAP_STATE_DIR}"
  if [[ -d "${REPO_DIR}/.git" ]]; then
    git -C "$REPO_DIR" fetch --tags origin
    git -C "$REPO_DIR" checkout "$REPO_REF"
    git -C "$REPO_DIR" pull --ff-only origin "$REPO_REF" || true
  else
    git clone --depth 1 --branch "$REPO_REF" "$REPO_URL" "$REPO_DIR"
  fi
}

conda_run() {
  "${CONDA_HOME}/bin/conda" run -n "$ENV_NAME" "$@"
}

ensure_conda_env() {
  if ! "${CONDA_HOME}/bin/conda" env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
    "${CONDA_HOME}/bin/conda" create -y -n "$ENV_NAME" "python=${PYTHON_VERSION}"
  fi
  conda_run python -m pip install --upgrade pip setuptools wheel
}

ensure_python_deps() {
  if [[ "$INSTALL_PYQLIB" -eq 1 ]]; then
    conda_run python -m pip install --upgrade pyqlib
  fi
  conda_run python -m pip install -e "$REPO_DIR"
}

ensure_env_template() {
  if [[ -z "$ENV_TEMPLATE_PATH" || ! -f "$ENV_TEMPLATE_PATH" ]]; then
    return
  fi
  cp "$ENV_TEMPLATE_PATH" "${REPO_DIR}/.env.example"
  if [[ ! -f "${REPO_DIR}/.env" ]]; then
    cp "$ENV_TEMPLATE_PATH" "${REPO_DIR}/.env"
  fi
}

prepare_cn_data() {
  if [[ "$SKIP_DATA_PREP" -eq 1 ]]; then
    DATA_STATUS="skipped"
    return
  fi

  mkdir -p "$DATA_ROOT"
  if find "$DATA_ROOT" -mindepth 1 -print -quit 2>/dev/null | grep -q .; then
    DATA_STATUS="existing"
    return
  fi

  if conda_run python -m qlib.cli.data qlib_data --target_dir "$DATA_ROOT" --region cn; then
    DATA_STATUS="downloaded"
    return
  fi

  if conda_run python -m qlib.run.get_data qlib_data --target_dir "$DATA_ROOT" --region cn; then
    DATA_STATUS="downloaded_legacy"
    return
  fi

  local community_archive
  community_archive="$(mktemp /tmp/qlib-cn-community-XXXXXX.tar.gz)"
  if curl -fL "$QLIB_CN_COMMUNITY_DATA_URL" -o "$community_archive"; then
    rm -rf "${DATA_ROOT:?}"/*
    tar -zxvf "$community_archive" -C "$DATA_ROOT" --strip-components=1 >/dev/null
    rm -f "$community_archive"
    DATA_STATUS="downloaded_community"
  else
    rm -f "$community_archive"
    DATA_STATUS="manual_required"
  fi
}

write_summary() {
  python3 - "$SUMMARY_PATH" "$DEPLOY_ROOT" "$REPO_DIR" "$ENV_NAME" "$CONDA_HOME" "$DATA_ROOT" "$REPO_REF" "$DATA_STATUS" "$NEEDS_DOCKER_RELOGIN" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

(
    summary_path,
    deploy_root,
    repo_dir,
    env_name,
    conda_home,
    data_root,
    repo_ref,
    data_status,
    needs_relogin,
) = sys.argv[1:10]

payload = {
    "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    "deploy_root": deploy_root,
    "repo_dir": repo_dir,
    "conda_env": env_name,
    "conda_home": conda_home,
    "data_root": data_root,
    "repo_ref": repo_ref,
    "data_status": data_status,
    "needs_docker_relogin": needs_relogin == "1",
}
Path(summary_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(summary_path)
PY
}

main() {
  ensure_apt_packages
  ensure_docker
  ensure_miniforge
  ensure_repo
  ensure_conda_env
  ensure_python_deps
  ensure_env_template
  prepare_cn_data
  write_summary

  printf 'bootstrap_summary=%s\n' "$SUMMARY_PATH"
  printf 'repo_dir=%s\n' "$REPO_DIR"
  printf 'conda_env=%s\n' "$ENV_NAME"
  printf 'data_root=%s\n' "$DATA_ROOT"
  printf 'data_status=%s\n' "$DATA_STATUS"
  printf 'needs_docker_relogin=%s\n' "$NEEDS_DOCKER_RELOGIN"
}

main "$@"
