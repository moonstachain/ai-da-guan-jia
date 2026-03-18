#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SSH_SCRIPT="${SCRIPT_DIR}/ssh_with_codex_identities.sh"
KNOWN_HOSTS_FILE="/tmp/codex_satellite_known_hosts"
ARTIFACT_ROOT="${SCRIPT_DIR}/../artifacts/black-satellite-cli-selfcheck"

DEFAULT_HOST="liming@172.16.77.38"
FALLBACK_HOST="liming@192.168.31.86"
LEGACY_HOST="liming@MacBook-Pro-2.local"

REPAIR="1"
RUN_EXEC="1"
JSON_OUTPUT="0"
TARGET_HOST="${BLACK_SATELLITE_HOST:-}"
RUN_STAMP="$(date +%Y%m%d-%H%M%S)"
RUN_DIR="${ARTIFACT_ROOT}/${RUN_STAMP}"
LOG_FILE="${RUN_DIR}/run.log"
SUMMARY_FILE="${RUN_DIR}/summary.json"

usage() {
  cat <<'EOF'
Usage:
  scripts/black_satellite_cli_selfcheck.sh [options]

Options:
  --host <user@host>    Override the target host.
  --no-repair           Only inspect; do not create symlinks or write PATH exposure.
  --skip-exec           Skip the final `codex exec` MVP step.
  --json                Print the final summary as JSON.
  -h, --help            Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      TARGET_HOST="${2:-}"
      shift 2
      ;;
    --no-repair)
      REPAIR="0"
      shift
      ;;
    --skip-exec)
      RUN_EXEC="0"
      shift
      ;;
    --json)
      JSON_OUTPUT="1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      print -u2 -- "Unknown argument: $1"
      usage >&2
      exit 1
      ;;
  esac
done

mkdir -p "$RUN_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

say() {
  print -- "[black-satellite-selfcheck] $*"
}

resolve_host() {
  if [[ -n "$TARGET_HOST" ]]; then
    print -- "$TARGET_HOST"
    return 0
  fi

  local -a candidates=("$DEFAULT_HOST" "$FALLBACK_HOST" "$LEGACY_HOST")
  local candidate
  for candidate in "${candidates[@]}"; do
    if "$SSH_SCRIPT" \
      -o BatchMode=yes \
      -o ConnectTimeout=4 \
      -o StrictHostKeyChecking=accept-new \
      -o UserKnownHostsFile="$KNOWN_HOSTS_FILE" \
      "$candidate" "exit" >/dev/null 2>&1; then
      print -- "$candidate"
      return 0
    fi
  done

  print -u2 -- "Could not reach black satellite via ${candidates[*]}"
  return 1
}

REMOTE_HOST="$(resolve_host)"
say "目标黑色卫星: ${REMOTE_HOST}"
say "本轮工件目录: ${RUN_DIR}"

run_remote() {
  "$SSH_SCRIPT" \
    -o StrictHostKeyChecking=accept-new \
    -o UserKnownHostsFile="$KNOWN_HOSTS_FILE" \
    "$REMOTE_HOST" "$@"
}

collect_probe() {
  run_remote 'zsh -s' <<'EOF'
APP_CODE="/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
APP_CODEX="/Applications/Codex.app/Contents/Resources/codex"
LOCAL_BIN="$HOME/.local/bin"
ZPROFILE="$HOME/.zprofile"

printf 'hostname=%s\n' "$(hostname)"
printf 'user=%s\n' "$(whoami)"
printf 'vscode_app_present=%s\n' "$([[ -d "/Applications/Visual Studio Code.app" ]] && echo 1 || echo 0)"
printf 'codex_app_present=%s\n' "$([[ -d "/Applications/Codex.app" ]] && echo 1 || echo 0)"
printf 'local_bin_present=%s\n' "$([[ -d "$LOCAL_BIN" ]] && echo 1 || echo 0)"
printf 'zprofile_present=%s\n' "$([[ -f "$ZPROFILE" ]] && echo 1 || echo 0)"
printf 'code_link_present=%s\n' "$([[ -L "$LOCAL_BIN/code" ]] && echo 1 || echo 0)"
printf 'codex_link_present=%s\n' "$([[ -L "$LOCAL_BIN/codex" ]] && echo 1 || echo 0)"
printf 'code_cli_raw=%s\n' "$(command -v code || true)"
printf 'codex_cli_raw=%s\n' "$(command -v codex || true)"

LOGIN_REPORT="$(zsh -lc '
  printf "path=%s\n" "$PATH"
  printf "code_cli=%s\n" "$(command -v code || true)"
  printf "codex_cli=%s\n" "$(command -v codex || true)"
  if command -v code >/dev/null 2>&1; then
    code --version | sed -n "1,2p" | awk "NR==1{printf \"code_version=%s\n\",\$0} NR==2{printf \"code_commit=%s\n\",\$0}"
  else
    printf "code_version=\n"
    printf "code_commit=\n"
  fi
  if command -v codex >/dev/null 2>&1; then
    codex --version | sed -n "1p" | awk "{printf \"codex_version=%s\n\",\$0}"
  else
    printf "codex_version=\n"
  fi
')"
printf '%s\n' "$LOGIN_REPORT"
EOF
}

REMOTE_PROBE_BEFORE="$(collect_probe)"
print -- "$REMOTE_PROBE_BEFORE" > "${RUN_DIR}/probe-before.txt"

if [[ "$REPAIR" == "1" ]]; then
  say "准备写入远端 CLI 暴露配置"
  say "写入内容 1/3: 创建 ~/.local/bin"
  say "写入内容 2/3: 建立 code/codex 符号链接"
  say "写入内容 3/3: 如缺失则向 ~/.zprofile 追加 PATH 暴露段"
  run_remote 'zsh -s' <<'EOF'
set -euo pipefail
mkdir -p "$HOME/.local/bin"
ln -sf "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code" "$HOME/.local/bin/code"
ln -sf "/Applications/Codex.app/Contents/Resources/codex" "$HOME/.local/bin/codex"
if [[ ! -f "$HOME/.zprofile" ]]; then
  touch "$HOME/.zprofile"
fi
if ! grep -q "AI大管家 for black satellite CLI exposure" "$HOME/.zprofile"; then
  cat >> "$HOME/.zprofile" <<'BLOCK'

# Added by AI大管家 for black satellite CLI exposure
export PATH="$HOME/.local/bin:$PATH"
BLOCK
fi
EOF
else
  say "按要求跳过远端写入修复"
fi

REMOTE_PROBE_AFTER="$(collect_probe)"
print -- "$REMOTE_PROBE_AFTER" > "${RUN_DIR}/probe-after.txt"

say "远端 CLI 复验结果:"
print -- "$REMOTE_PROBE_AFTER"

EXEC_STATUS="skipped"
EXEC_RESULT_PATH=""
EXEC_RESULT_CONTENT=""
EXEC_LAST_MESSAGE=""

if [[ "$RUN_EXEC" == "1" ]]; then
  say "开始执行最小 Codex MVP"
  say "MVP 内容: 让黑色卫星上的 codex exec 在 /tmp 下创建一个文本文件，并把文件路径回给我"
  run_remote 'zsh -lc '\''rm -f /tmp/black_satellite_codex_exec.txt /tmp/black_satellite_codex_last.txt && codex exec --skip-git-repo-check -C /tmp --full-auto --color never -o /tmp/black_satellite_codex_last.txt "Create the file /tmp/black_satellite_codex_exec.txt containing exactly this single line: black satellite codex exec ok. Then reply with only the absolute path to the file."'\'''
  EXEC_LAST_MESSAGE="$(run_remote 'cat /tmp/black_satellite_codex_last.txt')"
  EXEC_RESULT_CONTENT="$(run_remote 'cat /tmp/black_satellite_codex_exec.txt')"
  EXEC_RESULT_PATH="/tmp/black_satellite_codex_exec.txt"
  EXEC_STATUS="completed"
  print -- "$EXEC_LAST_MESSAGE" > "${RUN_DIR}/codex-last-message.txt"
  print -- "$EXEC_RESULT_CONTENT" > "${RUN_DIR}/codex-created-file.txt"
  say "Codex 最后回复: ${EXEC_LAST_MESSAGE}"
  say "远端结果文件: ${EXEC_RESULT_PATH}"
  say "远端结果内容: ${EXEC_RESULT_CONTENT}"
else
  say "按要求跳过 codex exec"
fi

python3 - "$SUMMARY_FILE" "$REMOTE_HOST" "$REPAIR" "$RUN_EXEC" "$EXEC_STATUS" "$EXEC_RESULT_PATH" "$EXEC_RESULT_CONTENT" "$EXEC_LAST_MESSAGE" <<'PY'
import json
import sys
from pathlib import Path

summary_file, remote_host, repair, run_exec, exec_status, exec_result_path, exec_result_content, exec_last_message = sys.argv[1:]
run_dir = Path(summary_file).parent
before = (run_dir / "probe-before.txt").read_text(encoding="utf-8")
after = (run_dir / "probe-after.txt").read_text(encoding="utf-8")

def parse_probe(text: str) -> dict[str, str]:
    result = {}
    for line in text.splitlines():
      if "=" not in line:
        continue
      key, value = line.split("=", 1)
      result[key.strip()] = value.strip()
    return result

payload = {
    "remote_host": remote_host,
    "repair_enabled": repair == "1",
    "exec_enabled": run_exec == "1",
    "probe_before": parse_probe(before),
    "probe_after": parse_probe(after),
    "exec_status": exec_status,
    "exec_result_path": exec_result_path,
    "exec_result_content": exec_result_content,
    "exec_last_message": exec_last_message,
    "artifacts": {
        "run_dir": str(run_dir),
        "log_file": str(run_dir / "run.log"),
        "probe_before": str(run_dir / "probe-before.txt"),
        "probe_after": str(run_dir / "probe-after.txt"),
    },
}
Path(summary_file).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

say "总结文件已写入: ${SUMMARY_FILE}"
if [[ "$JSON_OUTPUT" == "1" ]]; then
  cat "$SUMMARY_FILE"
else
  say "完成。关键结果:"
  say "- 远端命中: ${REMOTE_HOST}"
  say "- code CLI: $(grep '^code_cli=' "${RUN_DIR}/probe-after.txt" | head -n1 | cut -d= -f2-)"
  say "- codex CLI: $(grep '^codex_cli=' "${RUN_DIR}/probe-after.txt" | head -n1 | cut -d= -f2-)"
  say "- codex exec: ${EXEC_STATUS}"
  if [[ -n "$EXEC_RESULT_PATH" ]]; then
    say "- 远端文件: ${EXEC_RESULT_PATH}"
  fi
fi
