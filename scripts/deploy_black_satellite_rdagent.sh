#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

exec "$PYTHON_BIN" \
  "${REPO_ROOT}/work/ai-da-guan-jia/scripts/ai_da_guan_jia.py" \
  deploy-rdagent-fin-quant \
  --alias "黑色" \
  "$@"
