#!/bin/zsh
set -euo pipefail

host="${1:-liming@limingdeMacBook-Pro.local}"
action="${2:-prepare}"
remote_script="/Users/liming/Documents/codex-ai-gua-jia-01/scripts/vscode_codex_old_mode_bridge.py"

exec /Users/liming/Documents/codex-ai-gua-jia-01/scripts/ssh_with_codex_identities.sh \
  -t \
  "${host}" \
  "python3 ${remote_script} ${action}"
