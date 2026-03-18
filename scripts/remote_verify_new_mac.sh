#!/bin/zsh
set -euo pipefail

SSH_BIN="${SSH_BIN:-ssh}"
SSH_TIMEOUT="${SSH_TIMEOUT:-5}"
PORT="22"
HOST=""
USER_NAME=""
WORKSPACE_ROOT=""
EXPECTED_SKILLS_MIN="${EXPECTED_SKILLS_MIN:-100}"
BROWSER_SKILL_SMOKE_COMMAND=""

usage() {
  cat <<'EOF'
Usage: scripts/remote_verify_new_mac.sh --host <lan-host> --workspace-root <path> [options]

Options:
  --host <lan-host>                   Required LAN host or IP.
  --workspace-root <path>             Required remote workspace root.
  --user <ssh-user>                   Optional SSH user.
  --port <port>                       SSH port. Default: 22.
  --expected-skills-min <count>       Expected minimum inventory count. Default: 100.
  --browser-smoke-command <command>   Optional browser skill smoke command run on remote host.
  --help                              Show this help.
EOF
}

log() {
  printf '[remote-verify] %s\n' "$1"
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
    -o BatchMode=yes \
    -o ConnectTimeout="$SSH_TIMEOUT" \
    -o StrictHostKeyChecking=accept-new \
    -p "$PORT" \
    "$target" \
    "$@"
}

main() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --host)
        HOST="${2:-}"
        shift 2
        ;;
      --workspace-root)
        WORKSPACE_ROOT="${2:-}"
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
      --expected-skills-min)
        EXPECTED_SKILLS_MIN="${2:-}"
        shift 2
        ;;
      --browser-smoke-command)
        BROWSER_SKILL_SMOKE_COMMAND="${2:-}"
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

  if [[ -z "$HOST" || -z "$WORKSPACE_ROOT" ]]; then
    usage >&2
    exit 1
  fi

  local remote_env
  remote_env="EXPECTED_SKILLS_MIN=$(printf '%q' "$EXPECTED_SKILLS_MIN") WORKSPACE_ROOT=$(printf '%q' "$WORKSPACE_ROOT")"
  if [[ -n "$BROWSER_SKILL_SMOKE_COMMAND" ]]; then
    remote_env="$remote_env BROWSER_SKILL_SMOKE_CMD=$(printf '%q' "$BROWSER_SKILL_SMOKE_COMMAND")"
  fi

  local remote_script
  remote_script="cd $(printf '%q' "$WORKSPACE_ROOT") && $remote_env ./verify-restore.sh"

  log "running verify-restore.sh on $(target_host):$WORKSPACE_ROOT"
  run_ssh "zsh -lc $(printf '%q' "$remote_script")"
  log "remote verify passed"
}

main "$@"
