#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AI_SCRIPT="${SCRIPT_DIR}/ai_da_guan_jia.py"
STRATEGY_ROOT="${SCRIPT_DIR}/../artifacts/ai-da-guan-jia/strategy/current"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/personal_decision_cockpit.sh morning "<prompt>"
  bash scripts/personal_decision_cockpit.sh status
  bash scripts/personal_decision_cockpit.sh review
  bash scripts/personal_decision_cockpit.sh strategy
  bash scripts/personal_decision_cockpit.sh evening
  bash scripts/personal_decision_cockpit.sh feedback <run-id> <label> <comment> [by]
  bash scripts/personal_decision_cockpit.sh pipeline "<prompt>"
  bash scripts/personal_decision_cockpit.sh verify <run-id> [--adversarial]
  bash scripts/personal_decision_cockpit.sh state <run-id> [show|advance|block]
  bash scripts/personal_decision_cockpit.sh harness "<prompt>"
  bash scripts/personal_decision_cockpit.sh stream-morning "<prompt>"
  bash scripts/personal_decision_cockpit.sh stream-cycle <run-id>
  bash scripts/personal_decision_cockpit.sh stream-close <run-id> "<task>"
  bash scripts/personal_decision_cockpit.sh evolve-scan [hours]
  bash scripts/personal_decision_cockpit.sh evolve-digest [date]
  bash scripts/personal_decision_cockpit.sh evolve-daemon [interval]
  bash scripts/personal_decision_cockpit.sh window-spawn <role> "<task>"
  bash scripts/personal_decision_cockpit.sh window-status
  bash scripts/personal_decision_cockpit.sh window-assembly

Commands:
  morning   Run route with a single daily north-star prompt.
  status    Print the current strategic proposal and initiative brief.
  review    Run governance review for the day.
  strategy  Refresh the strategic current artifacts.
  evening   Run review, then strategy refresh.
  feedback  Record one human feedback line for a run.
  pipeline  Run 3-layer governance judgment pipeline (v2).
  verify    Verify a run's evidence bundle (v2, supports --adversarial).
  state     Show/advance/block a run's lifecycle state (v2).
  harness   Recommend skill combination for a task (v2).
EOF
}

print_status() {
  echo "== Strategic Proposal =="
  sed -n '1,24p' "${STRATEGY_ROOT}/strategic-proposal.md"
  echo
  echo "== Initiative Brief =="
  sed -n '1,120p' "${STRATEGY_ROOT}/initiative-brief.json"
}

cmd="${1:-help}"
if [[ $# -gt 0 ]]; then
  shift
fi

case "${cmd}" in
  morning)
    prompt="${1:-}"
    if [[ -z "${prompt}" ]]; then
      echo "morning requires a prompt" >&2
      usage
      exit 1
    fi
    python3 "${AI_SCRIPT}" route --prompt "${prompt}"
    ;;
  status)
    print_status
    ;;
  review)
    python3 "${AI_SCRIPT}" review-governance --daily
    ;;
  strategy)
    python3 "${AI_SCRIPT}" strategy-governor
    ;;
  evening)
    python3 "${AI_SCRIPT}" review-governance --daily
    python3 "${AI_SCRIPT}" strategy-governor
    print_status
    ;;
  feedback)
    run_id="${1:-}"
    label="${2:-}"
    comment="${3:-}"
    by="${4:-liming}"
    if [[ -z "${run_id}" || -z "${label}" || -z "${comment}" ]]; then
      echo "feedback requires <run-id> <label> <comment> [by]" >&2
      usage
      exit 1
    fi
    python3 "${AI_SCRIPT}" record-human-feedback --run-id "${run_id}" --label "${label}" --comment "${comment}" --by "${by}"
    ;;
  pipeline)
    prompt="${1:-}"
    if [[ -z "${prompt}" ]]; then
      echo "pipeline requires a prompt" >&2
      usage
      exit 1
    fi
    python3 "${AI_SCRIPT}" governance-pipeline --prompt "${prompt}"
    ;;
  verify)
    run_id="${1:-}"
    if [[ -z "${run_id}" ]]; then
      echo "verify requires a run-id" >&2
      usage
      exit 1
    fi
    shift
    python3 "${AI_SCRIPT}" verify --run-id "${run_id}" "$@"
    ;;
  state)
    run_id="${1:-}"
    if [[ -z "${run_id}" ]]; then
      echo "state requires a run-id" >&2
      usage
      exit 1
    fi
    action="${2:-show}"
    python3 "${AI_SCRIPT}" run-state --run-id "${run_id}" --action "${action}"
    ;;
  harness)
    prompt="${1:-}"
    if [[ -z "${prompt}" ]]; then
      echo "harness requires a prompt" >&2
      usage
      exit 1
    fi
    python3 "${AI_SCRIPT}" skill-harness --prompt "${prompt}"
    ;;
  stream-morning)
    prompt="${1:-}"
    if [[ -z "${prompt}" ]]; then
      echo "stream-morning requires a prompt" >&2
      usage
      exit 1
    fi
    python3 "${SCRIPT_DIR}/streaming_executor.py" morning --prompt "${prompt}"
    ;;
  stream-cycle)
    run_id="${1:-}"
    if [[ -z "${run_id}" ]]; then
      echo "stream-cycle requires a run-id" >&2
      usage
      exit 1
    fi
    python3 "${SCRIPT_DIR}/streaming_executor.py" full-cycle --run-id "${run_id}"
    ;;
  stream-close)
    run_id="${1:-}"
    task="${2:-}"
    if [[ -z "${run_id}" || -z "${task}" ]]; then
      echo "stream-close requires <run-id> <task>" >&2
      usage
      exit 1
    fi
    python3 "${SCRIPT_DIR}/streaming_executor.py" close --run-id "${run_id}" --task "${task}"
    ;;
  evolve-scan)
    hours="${1:-1}"
    python3 "${SCRIPT_DIR}/auto_evolve_daemon.py" scan --hours "${hours}"
    ;;
  evolve-digest)
    date_arg="${1:-}"
    if [[ -n "${date_arg}" ]]; then
      python3 "${SCRIPT_DIR}/auto_evolve_daemon.py" digest --date "${date_arg}"
    else
      python3 "${SCRIPT_DIR}/auto_evolve_daemon.py" digest
    fi
    ;;
  evolve-daemon)
    interval="${1:-3600}"
    python3 "${SCRIPT_DIR}/auto_evolve_daemon.py" daemon --interval "${interval}"
    ;;
  window-spawn)
    role="${1:-}"
    task="${2:-}"
    if [[ -z "${role}" || -z "${task}" ]]; then
      echo "window-spawn requires <role> <task>" >&2
      usage
      exit 1
    fi
    python3 "${SCRIPT_DIR}/window_agents.py" spawn --role "${role}" --task "${task}"
    ;;
  window-status)
    python3 "${SCRIPT_DIR}/window_agents.py" status
    ;;
  window-assembly)
    python3 "${SCRIPT_DIR}/window_agents.py" morning-assembly
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "unknown command: ${cmd}" >&2
    usage
    exit 1
    ;;
esac
