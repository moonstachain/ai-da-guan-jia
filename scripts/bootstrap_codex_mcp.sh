#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env.codex-mcp"

if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  echo "Loaded ${ENV_FILE}"
else
  echo "No ${ENV_FILE} found; continuing with current shell environment."
fi

python3 "${ROOT_DIR}/scripts/check_codex_mcp.py"
