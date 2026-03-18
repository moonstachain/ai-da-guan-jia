#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

pause_before_close() {
  print ""
  read '?看完后按回车关闭窗口... ' || true
}

run_and_pause() {
  local rc=0
  if ! "${SCRIPT_DIR}/black_satellite.sh" "$@"; then
    rc=$?
  fi

  print ""
  if (( rc == 0 )); then
    print "已经完成。"
  else
    print "这一步没有成功。"
    print "通常重新试一次就行；如果还是不行，把这个窗口完整截图发给我。"
  fi
  pause_before_close
  return $rc
}

show_usage() {
  cat <<'EOF'
用法：
  black_satellite_human_action.sh shell
  black_satellite_human_action.sh status
  black_satellite_human_action.sh selfcheck
  black_satellite_human_action.sh model-gpt54
  black_satellite_human_action.sh model-claude4
  black_satellite_human_action.sh model-kimi
EOF
}

action="${1:-}"

case "$action" in
  shell)
    print "正在打开黑色卫星机终端..."
    print "如果你看到 [black-satellite] connected to ... 就说明已经连上了。"
    print ""
    exec "${SCRIPT_DIR}/black_satellite.sh" shell
    ;;
  status)
    print "正在查看当前模型..."
    print "成功时你会看到 current provider 和 current model。"
    print ""
    run_and_pause status
    ;;
  selfcheck)
    print "正在执行黑色卫星 CLI 一键自检..."
    print "这一步会检查并修复 code/codex CLI 暴露，然后跑一次最小 codex exec。"
    print "成功时你会看到远端文件路径和 completed 结果。"
    print ""
    local rc=0
    if ! "${SCRIPT_DIR}/black_satellite_cli_selfcheck.sh"; then
      rc=$?
    fi
    print ""
    if (( rc == 0 )); then
      print "黑色卫星 CLI 自检已完成。"
    else
      print "黑色卫星 CLI 自检没有成功。"
      print "通常重新试一次就行；如果还是不行，把这个窗口完整截图发给我。"
    fi
    pause_before_close
    return $rc
    ;;
  model-gpt54)
    print "正在把黑色卫星机切回 GPT-5.4..."
    print "成功时你会看到 activated_provider=or-gpt54。"
    print ""
    run_and_pause model gpt54
    ;;
  model-claude4)
    print "正在把黑色卫星机切到 Claude..."
    print "成功时你会看到 activated_provider=or-claude4。"
    print ""
    run_and_pause model claude4
    ;;
  model-kimi)
    print "正在把黑色卫星机切到 Kimi..."
    print "成功时你会看到 activated_provider=or-kimi-k2。"
    print ""
    run_and_pause model kimi
    ;;
  *)
    show_usage
    exit 1
    ;;
esac
