#!/bin/zsh
set -euo pipefail

provider_id="${1:-or-gpt54}"
exec /Users/liming/Documents/codex-ai-gua-jia-01/scripts/black_satellite.sh model "${provider_id}"
