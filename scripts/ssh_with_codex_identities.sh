#!/bin/zsh
set -euo pipefail

exec /usr/bin/ssh \
  -i "$HOME/.ssh/github_liming_m5" \
  -i "$HOME/.ssh/github_old_mac" \
  "$@"
