#!/bin/zsh
set -euo pipefail

provider_id="${1:-or-gpt54}"
remote_script="/Users/liming/Documents/codex-ai-gua-jia-01/scripts/ccswitch_openrouter_bridge.py"

exec /Users/liming/Documents/codex-ai-gua-jia-01/scripts/ssh_with_codex_identities.sh \
  -t \
  liming@172.16.77.38 \
  "python3 ${remote_script} activate --provider-id ${provider_id}"
