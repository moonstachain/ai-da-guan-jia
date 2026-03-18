#!/bin/zsh
set -euo pipefail

default_host="liming@172.16.77.38"
fallback_host="liming@192.168.31.86"
legacy_hostname_host="liming@MacBook-Pro-2.local"
ssh_script="/Users/liming/Documents/codex-ai-gua-jia-01/scripts/ssh_with_codex_identities.sh"
remote_script="/Users/liming/Documents/codex-ai-gua-jia-01/scripts/black_satellite_openrouter_remote.py"
known_hosts_file="/tmp/codex_satellite_known_hosts"

usage() {
  cat <<'EOF'
Usage:
  scripts/black_satellite.sh shell
  scripts/black_satellite.sh status
  scripts/black_satellite.sh model <provider>
  scripts/black_satellite.sh codex [args...]
  scripts/black_satellite.sh claude [args...]
  scripts/black_satellite.sh gemini [args...]

Provider aliases:
  gpt54 claude4 gemini25 glm45 kimi minimax
EOF
}

if (( $# == 0 )); then
  usage
  exit 1
fi

resolve_host() {
  if [[ -n "${BLACK_SATELLITE_HOST:-}" ]]; then
    print -- "$BLACK_SATELLITE_HOST"
    return 0
  fi

  local -a candidates=()
  candidates+=("$default_host" "$fallback_host" "$legacy_hostname_host")

  local candidate
  for candidate in "${candidates[@]}"; do
    if "$ssh_script" \
      -o BatchMode=yes \
      -o ConnectTimeout=4 \
      -o StrictHostKeyChecking=accept-new \
      -o UserKnownHostsFile="$known_hosts_file" \
      "$candidate" \
      "exit" >/dev/null 2>&1; then
      print -- "$candidate"
      return 0
    fi
  done

  print -u2 -- "Could not reach black satellite via ${candidates[*]}"
  return 1
}

command_name="$1"
shift

host="$(resolve_host)"

remote_argv=(python3 "$remote_script" "$command_name")
if (( $# > 0 )); then
  remote_argv+=("$@")
fi
quoted_remote_argv=("${(@qq)remote_argv}")
remote_inner_cmd="${(j: :)quoted_remote_argv}"
remote_cmd="/bin/zsh -lc ${(qq)remote_inner_cmd}"

case "$command_name" in
  shell|model|codex|claude|gemini)
    exec "$ssh_script" \
      -o StrictHostKeyChecking=accept-new \
      -o UserKnownHostsFile="$known_hosts_file" \
      -tt "$host" "$remote_cmd"
    ;;
  status|install-shortcuts)
    exec "$ssh_script" \
      -o StrictHostKeyChecking=accept-new \
      -o UserKnownHostsFile="$known_hosts_file" \
      "$host" "$remote_cmd"
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    usage
    exit 1
    ;;
esac
