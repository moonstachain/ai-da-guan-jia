#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AI_SCRIPT="${AI_SCRIPT:-${SCRIPT_DIR}/ai_da_guan_jia.py}"
CLONE_CURRENT_ROOT="${SCRIPT_DIR}/../artifacts/ai-da-guan-jia/clones/current"
GUIDE_PATH="${SCRIPT_DIR}/../AI大管家-内部同事版第一闭环MVP启用说明.md"
DEFAULT_REPORT_DATE="$(date +%F)"
DEFAULT_ORG_ID="${AI_DA_GUAN_JIA_INTERNAL_ORG_ID:-yuanli-hq}"
DEFAULT_TENANT_ID="${AI_DA_GUAN_JIA_INTERNAL_TENANT_ID:-yuanli-hq}"
DEFAULT_CUSTOMER_ID="${AI_DA_GUAN_JIA_INTERNAL_CUSTOMER_ID:-yuanli-hq}"
DEFAULT_REPORT_OWNER="${AI_DA_GUAN_JIA_INTERNAL_REPORT_OWNER:-liming}"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/internal_ops_mvp.sh bootstrap <clone-id> "<display-name>" [report-owner] [manager-clone-id]
  bash scripts/internal_ops_mvp.sh midday [report-date]
  bash scripts/internal_ops_mvp.sh evening [report-date]
  bash scripts/internal_ops_mvp.sh status
  bash scripts/internal_ops_mvp.sh checklist

Commands:
  bootstrap  Register the single internal ops-management clone, refresh the internal portfolio, and prepare a Feishu dry-run bundle.
  midday     Run the noon internal portfolio review and clone governance Feishu dry-run.
  evening    Run the evening internal portfolio review and clone governance Feishu dry-run.
  status     Show the latest internal portfolio artifacts and the MVP guide path.
  checklist  Print the fixed phrases, Day 0-5 checklist, and direct CLI equivalents.
EOF
}

run_review() {
  local report_date="$1"
  python3 "${AI_SCRIPT}" review-clones --portfolio internal --date "${report_date}"
}

run_sync_dry_run() {
  local report_date="$1"
  python3 "${AI_SCRIPT}" sync-feishu --surface clone_governance --portfolio internal --report-date "${report_date}" --dry-run
}

print_fixed_phrases() {
  cat <<'EOF'
Fixed Feishu phrases:
1. 今天最该看什么
2. 帮我接个任务：...
3. 我现在有哪些任务
4. 继续昨天那个
5. 把这事闭环

Daily operating rule:
- Morning: 只用“今天最该看什么”，任务不清时再说“帮我接个任务：...”
- Daytime: 只用“我现在有哪些任务 / 继续昨天那个 / 原力原力 记一下 ...”
- Evening: 固定用“把这事闭环”
- Frontstage cap: 同时最多 3 条活跃任务
- Allowed closure states: completed / blocked_needs_user / blocked_system / failed_partial
EOF
}

print_week_plan() {
  cat <<'EOF'
Day 0:
- 注册 1 位中台管理同事 clone
- 打开同事飞书入口、internal portfolio、clone governance 内部视图
- 确认对方只需记住 5 句固定话术

Day 1-2:
- 只验证“早上定重点 -> 白天跟进 -> 晚上收口”
- 不改模板结构，只记录真实 friction

Day 3:
- 只调一次 ops-management 模板
- 调整项只能是目标模型、推荐 skill chain、禁止越权边界、评分指标

Day 4-5:
- 连续稳定跑，不新增功能
- 只看是否减少 founder 手工催办和追问

Founder noon/evening checks:
- 中午：看 waiting_human / blocked_* / 风险与决策表
- 晚上：看收口状态、evidence、blocker 是否清楚

Direct CLI equivalents:
- python3 scripts/ai_da_guan_jia.py register-clone --clone-id <clone-id> --customer-id yuanli-hq --display-name "<display-name>" --org-id yuanli-hq --tenant-id yuanli-hq --actor-type employee --role-template-id ops-management --visibility-policy hq_internal_full --service-tier internal_core --report-owner liming
- python3 scripts/ai_da_guan_jia.py review-clones --portfolio internal
- python3 scripts/ai_da_guan_jia.py sync-feishu --surface clone_governance --portfolio internal --dry-run
- python3 scripts/ai_da_guan_jia.py train-clone --clone-id <clone-id> --target-capability "日常推进闭环"
EOF
}

show_status() {
  echo "guide_path: ${GUIDE_PATH}"
  echo "clone_root: ${CLONE_CURRENT_ROOT}"
  echo
  if [[ -f "${CLONE_CURRENT_ROOT}/portfolio-daily-report.md" ]]; then
    echo "== portfolio-daily-report.md =="
    sed -n '1,140p' "${CLONE_CURRENT_ROOT}/portfolio-daily-report.md"
    echo
  else
    echo "portfolio-daily-report.md not generated yet. Run:"
    echo "  bash scripts/internal_ops_mvp.sh midday"
    echo
  fi
  if [[ -f "${CLONE_CURRENT_ROOT}/sync-result.json" ]]; then
    echo "== sync-result.json =="
    sed -n '1,120p' "${CLONE_CURRENT_ROOT}/sync-result.json"
  else
    echo "sync-result.json not generated yet. Run:"
    echo "  bash scripts/internal_ops_mvp.sh midday"
  fi
}

bootstrap_clone() {
  local clone_id="${1:-}"
  local display_name="${2:-}"
  local report_owner="${3:-${DEFAULT_REPORT_OWNER}}"
  local manager_clone_id="${4:-}"
  local report_date="${DEFAULT_REPORT_DATE}"
  local -a register_command

  if [[ -z "${clone_id}" || -z "${display_name}" ]]; then
    echo "bootstrap requires <clone-id> and <display-name>" >&2
    usage
    exit 1
  fi

  register_command=(
    python3
    "${AI_SCRIPT}"
    register-clone
    --clone-id
    "${clone_id}"
    --customer-id
    "${DEFAULT_CUSTOMER_ID}"
    --display-name
    "${display_name}"
    --org-id
    "${DEFAULT_ORG_ID}"
    --tenant-id
    "${DEFAULT_TENANT_ID}"
    --actor-type
    employee
    --role-template-id
    ops-management
    --visibility-policy
    hq_internal_full
    --service-tier
    internal_core
    --report-owner
    "${report_owner}"
  )
  if [[ -n "${manager_clone_id}" ]]; then
    register_command+=(--manager-clone-id "${manager_clone_id}")
  fi

  "${register_command[@]}"

  run_review "${report_date}"
  run_sync_dry_run "${report_date}"

  echo
  echo "bootstrap_ready: true"
  echo "clone_id: ${clone_id}"
  echo "report_date: ${report_date}"
  echo "guide_path: ${GUIDE_PATH}"
  echo "next_step: 让同事今天开始只按固定话术跑真实任务。"
  echo
  print_fixed_phrases
  echo
  print_week_plan
}

midday_review() {
  local report_date="${1:-${DEFAULT_REPORT_DATE}}"
  run_review "${report_date}"
  run_sync_dry_run "${report_date}"
  echo
  echo "midday_focus:"
  echo "- 看 waiting_human / blocked_* / 风险与决策表"
  echo "- 只处理 founder 必须拍板的边界动作"
  echo "- 不扩岗位、不接客户、不改 workflow"
}

evening_review() {
  local report_date="${1:-${DEFAULT_REPORT_DATE}}"
  run_review "${report_date}"
  run_sync_dry_run "${report_date}"
  echo
  echo "evening_focus:"
  echo "- 让同事用“把这事闭环”收口"
  echo "- 确认 evidence、blocker、closure_state 已写清"
  echo "- 第二天继续只跑真实任务，不开新功能线程"
}

command="${1:-help}"
if [[ $# -gt 0 ]]; then
  shift
fi

case "${command}" in
  bootstrap)
    bootstrap_clone "$@"
    ;;
  midday)
    midday_review "$@"
    ;;
  evening)
    evening_review "$@"
    ;;
  status)
    show_status
    ;;
  checklist)
    print_fixed_phrases
    echo
    print_week_plan
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "unknown command: ${command}" >&2
    usage
    exit 1
    ;;
esac
