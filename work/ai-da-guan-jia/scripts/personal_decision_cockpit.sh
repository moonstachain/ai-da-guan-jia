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

Commands:
  morning   Run route with a single daily north-star prompt.
  status    Print the current strategic proposal and initiative brief.
  review    Run governance review for the day.
  strategy  Refresh the strategic current artifacts.
  evening   Run review, then strategy refresh.
  feedback  Record one human feedback line for a run.
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
  help|-h|--help)
    usage
    ;;
  *)
    echo "unknown command: ${cmd}" >&2
    usage
    exit 1
    ;;
esac
