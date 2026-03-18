#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SSH_BIN="${SSH_BIN:-ssh}"
SSH_TIMEOUT="${SSH_TIMEOUT:-5}"
PORT="22"
HOST=""
USER_NAME=""
SOURCE_ID=""
WORKSPACE_ROOT=""
OUTPUT_ROOT="${OUTPUT_ROOT:-${REPO_ROOT}/output/ai-da-guan-jia/remote-hosts-v2}"
REPO_OVERRIDE=""
STAMP="$(date '+%Y%m%d-%H%M%S')"

usage() {
  cat <<'EOF'
Usage: scripts/remote_self_governance_audit.sh --host <lan-host> --workspace-root <path> --source-id <source-id> [options]

Options:
  --host <lan-host>            Required LAN host or IP.
  --workspace-root <path>      Required remote workspace root.
  --source-id <source-id>      Required stable source id, e.g. satellite-03.
  --user <ssh-user>            Optional SSH user.
  --port <port>                SSH port. Default: 22.
  --repo <owner/name>          Optional GitHub ops repo override.
  --output-root <path>         Artifact root. Default: output/ai-da-guan-jia/remote-hosts-v2
  --help                       Show this help.
EOF
}

artifact_dir() {
  printf '%s/%s/self-governance/%s' "$OUTPUT_ROOT" "$SOURCE_ID" "$STAMP"
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
      --source-id)
        SOURCE_ID="${2:-}"
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
      --repo)
        REPO_OVERRIDE="${2:-}"
        shift 2
        ;;
      --output-root)
        OUTPUT_ROOT="${2:-}"
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

  [[ -n "$HOST" && -n "$WORKSPACE_ROOT" && -n "$SOURCE_ID" ]] || { usage >&2; exit 1; }

  local local_artifact_dir local_audit_dir remote_audit_dir remote_stdout_log
  local_artifact_dir="$(artifact_dir)"
  local_audit_dir="${local_artifact_dir}/remote-audit"
  remote_audit_dir="${WORKSPACE_ROOT}/output/ai-da-guan-jia/self-governance/${SOURCE_ID}/${STAMP}"
  remote_stdout_log="${local_artifact_dir}/remote-command.log"
  mkdir -p "$local_audit_dir"

  local remote_script
  remote_script=$(cat <<EOF
set -euo pipefail
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:\$PATH"
if command -v brew >/dev/null 2>&1; then
  eval "\$(brew shellenv)"
  PY311_PREFIX="\$(brew --prefix python@3.11 2>/dev/null || true)"
  NODE20_PREFIX="\$(brew --prefix node@20 2>/dev/null || true)"
  if [[ -n "\$PY311_PREFIX" ]]; then
    export PATH="\$PY311_PREFIX/libexec/bin:\$PATH"
  fi
  if [[ -n "\$NODE20_PREFIX" ]]; then
    export PATH="\$NODE20_PREFIX/bin:\$PATH"
  fi
fi

WORKSPACE_ROOT=$(printf '%q' "$WORKSPACE_ROOT")
SOURCE_ID=$(printf '%q' "$SOURCE_ID")
REMOTE_AUDIT_DIR=$(printf '%q' "$remote_audit_dir")
AI_SCRIPT="\$WORKSPACE_ROOT/work/ai-da-guan-jia/scripts/ai_da_guan_jia.py"
REVIEWS_ROOT="\$WORKSPACE_ROOT/work/ai-da-guan-jia/artifacts/ai-da-guan-jia/reviews"
GOV_REVIEWS_ROOT="\$WORKSPACE_ROOT/work/ai-da-guan-jia/artifacts/ai-da-guan-jia/governance/reviews"
STRATEGY_CURRENT_ROOT="\$WORKSPACE_ROOT/work/ai-da-guan-jia/artifacts/ai-da-guan-jia/strategy/current"

mkdir -p "\$REMOTE_AUDIT_DIR"

python3 "\$AI_SCRIPT" inventory-skills --output "\$REMOTE_AUDIT_DIR/skills-inventory.json" > "\$REMOTE_AUDIT_DIR/inventory-skills.log"

python3 "\$AI_SCRIPT" review-skills --daily > "\$REMOTE_AUDIT_DIR/review-skills.log"
review_run_id="\$(awk -F': ' '/^run_id:/ {print \$2}' "\$REMOTE_AUDIT_DIR/review-skills.log" | tail -n 1)"
review_status="\$(awk -F': ' '/^status:/ {print \$2}' "\$REMOTE_AUDIT_DIR/review-skills.log" | tail -n 1)"
review_run_dir=""
if [[ -n "\$review_run_id" ]]; then
  review_run_dir="\$(python3 - "\$REVIEWS_ROOT" "\$review_run_id" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
run_id = sys.argv[2]
matches = sorted(root.glob(f"*/{run_id}"))
print(matches[-1] if matches else "")
PY
)"
fi
if [[ -n "\$review_run_dir" && -d "\$review_run_dir" ]]; then
  cp -R "\$review_run_dir" "\$REMOTE_AUDIT_DIR/skill-review-run"
fi

python3 "\$AI_SCRIPT" review-governance --daily > "\$REMOTE_AUDIT_DIR/review-governance.log"
governance_run_id="\$(awk -F': ' '/^run_id:/ {print \$2}' "\$REMOTE_AUDIT_DIR/review-governance.log" | tail -n 1)"
governance_status="\$(awk -F': ' '/^status:/ {print \$2}' "\$REMOTE_AUDIT_DIR/review-governance.log" | tail -n 1)"
governance_run_dir=""
if [[ -n "\$governance_run_id" ]]; then
  governance_run_dir="\$(python3 - "\$GOV_REVIEWS_ROOT" "\$governance_run_id" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
run_id = sys.argv[2]
matches = sorted(root.glob(f"*/{run_id}"))
print(matches[-1] if matches else "")
PY
)"
fi
if [[ -n "\$governance_run_dir" && -d "\$governance_run_dir" ]]; then
  cp -R "\$governance_run_dir" "\$REMOTE_AUDIT_DIR/governance-review-run"
fi

python3 "\$AI_SCRIPT" strategy-governor > "\$REMOTE_AUDIT_DIR/strategy-governor.log"
if [[ -d "\$STRATEGY_CURRENT_ROOT" ]]; then
  cp -R "\$STRATEGY_CURRENT_ROOT" "\$REMOTE_AUDIT_DIR/strategy-current"
fi

python3 "\$AI_SCRIPT" emit-intake-bundle --source-id "\$SOURCE_ID" --mode full ${REPO_OVERRIDE:+--repo $(printf '%q' "$REPO_OVERRIDE")} > "\$REMOTE_AUDIT_DIR/emit-intake-bundle.log"
bundle_snapshot_root="\$(awk -F': ' '/^snapshot_root:/ {print \$2}' "\$REMOTE_AUDIT_DIR/emit-intake-bundle.log" | tail -n 1)"
bundle_latest_root="\$(awk -F': ' '/^latest_root:/ {print \$2}' "\$REMOTE_AUDIT_DIR/emit-intake-bundle.log" | tail -n 1)"

echo "remote_audit_dir: \$REMOTE_AUDIT_DIR"
echo "review_run_id: \$review_run_id"
echo "review_status: \$review_status"
echo "review_run_dir: \$review_run_dir"
echo "governance_run_id: \$governance_run_id"
echo "governance_status: \$governance_status"
echo "governance_run_dir: \$governance_run_dir"
echo "bundle_snapshot_root: \$bundle_snapshot_root"
echo "bundle_latest_root: \$bundle_latest_root"
EOF
)

  run_ssh "zsh -lc $(printf '%q' "$remote_script")" >"$remote_stdout_log" 2>&1

  local review_run_id governance_run_id bundle_snapshot_root bundle_latest_root
  review_run_id="$(awk -F': ' '/^review_run_id:/ {print $2}' "$remote_stdout_log" | tail -n 1)"
  governance_run_id="$(awk -F': ' '/^governance_run_id:/ {print $2}' "$remote_stdout_log" | tail -n 1)"
  bundle_snapshot_root="$(awk -F': ' '/^bundle_snapshot_root:/ {print $2}' "$remote_stdout_log" | tail -n 1)"
  bundle_latest_root="$(awk -F': ' '/^bundle_latest_root:/ {print $2}' "$remote_stdout_log" | tail -n 1)"

  run_ssh "tar -C $(printf '%q' "$remote_audit_dir") -czf - ." | tar -C "$local_audit_dir" -xzf -

  if [[ -n "$bundle_snapshot_root" && -n "$bundle_latest_root" ]]; then
    local remote_source_root snapshot_relative local_source_root
    remote_source_root="$(dirname "$bundle_latest_root")"
    snapshot_relative="${bundle_snapshot_root#${remote_source_root}/}"
    local_source_root="${REPO_ROOT}/work/ai-da-guan-jia/artifacts/ai-da-guan-jia/hub/outbox/sources/${SOURCE_ID}"
    mkdir -p "$local_source_root"
    run_ssh "tar -C $(printf '%q' "$remote_source_root") -czf - latest $(printf '%q' "$snapshot_relative")" | tar -C "$local_source_root" -xzf -
  fi

  local bootstrap_cmd aggregate_cmd audit_cmd
  bootstrap_cmd=(
    python3
    "${REPO_ROOT}/work/ai-da-guan-jia/scripts/ai_da_guan_jia.py"
    bootstrap-hub
  )
  aggregate_cmd=(
    python3
    "${REPO_ROOT}/work/ai-da-guan-jia/scripts/ai_da_guan_jia.py"
    aggregate-hub
    --source-id
    main-hub
  )
  audit_cmd=(
    python3
    "${REPO_ROOT}/work/ai-da-guan-jia/scripts/ai_da_guan_jia.py"
    audit-maturity
    --source-id
    main-hub
  )
  if [[ -n "$REPO_OVERRIDE" ]]; then
    bootstrap_cmd+=(--repo "$REPO_OVERRIDE")
    aggregate_cmd+=(--repo "$REPO_OVERRIDE")
    audit_cmd+=(--repo "$REPO_OVERRIDE")
  fi

  "${bootstrap_cmd[@]}" >"${local_artifact_dir}/bootstrap-hub.log" 2>&1
  "${aggregate_cmd[@]}" >"${local_artifact_dir}/aggregate-hub.log" 2>&1
  "${audit_cmd[@]}" >"${local_artifact_dir}/audit-maturity.log" 2>&1

  python3 - "$REPO_ROOT" "$local_artifact_dir" "$SOURCE_ID" "$review_run_id" "$governance_run_id" <<'PY'
import json
import sys
from collections import Counter
from pathlib import Path

repo_root = Path(sys.argv[1])
artifact_dir = Path(sys.argv[2])
source_id = sys.argv[3]
review_run_id = sys.argv[4]
governance_run_id = sys.argv[5]
audit_dir = artifact_dir / "remote-audit"
bundle_dir = (
    repo_root
    / "work"
    / "ai-da-guan-jia"
    / "artifacts"
    / "ai-da-guan-jia"
    / "hub"
    / "outbox"
    / "sources"
    / source_id
    / "latest"
)

def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def parse_key_value_log(path: Path) -> dict[str, str]:
    result = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        if ": " not in line:
            continue
        key, value = line.split(": ", 1)
        result[key.strip()] = value.strip()
    return result

skills_inventory = load_json(audit_dir / "skills-inventory.json", {})
skills_rows = load_json(bundle_dir / "skills.json", [])
session_rows = load_json(bundle_dir / "sessions.json", [])
run_rows = load_json(bundle_dir / "runs.json", [])
automation_rows = load_json(bundle_dir / "automations.json", [])
review_payload = load_json(audit_dir / "skill-review-run" / "review.json", {})
governance_payload = load_json(audit_dir / "governance-review-run" / "review.json", {})
strategy_log = parse_key_value_log(audit_dir / "strategy-governor.log")

verification_counts = Counter(str(item.get("verification_status") or "missing") for item in run_rows)
proof_counts = Counter(str(item.get("proof_strength") or "missing") for item in run_rows)
github_sync_counts = Counter(str(item.get("github_sync_status") or "missing") for item in run_rows)
selected_skill_counts = Counter()
for item in run_rows:
    for skill in item.get("selected_skills", []) or []:
        selected_skill_counts[str(skill)] += 1

summary = {
    "source_id": source_id,
    "local_artifact_dir": str(artifact_dir),
    "bundle_dir": str(bundle_dir),
    "skills_inventory_count": int(skills_inventory.get("count") or len(skills_rows)),
    "bundle_counts": {
        "skills": len(skills_rows),
        "sessions": len(session_rows),
        "runs": len(run_rows),
        "automations": len(automation_rows),
    },
    "run_quality": {
        "completed_runs": verification_counts.get("completed", 0),
        "partial_runs": verification_counts.get("partial", 0),
        "blocked_needs_user_runs": verification_counts.get("blocked_needs_user", 0),
        "failed_partial_runs": verification_counts.get("failed_partial", 0),
        "proof_strength_counts": dict(sorted(proof_counts.items())),
        "verification_status_counts": dict(sorted(verification_counts.items())),
        "github_sync_status_counts": dict(sorted(github_sync_counts.items())),
        "structured_run_count": sum(1 for item in run_rows if item.get("structured_artifacts")),
    },
    "review_skills": {
        "run_id": review_run_id,
        "status": str(review_payload.get("status") or ""),
        "skills_total": int(review_payload.get("skills_total") or 0),
        "candidate_actions_count": len(review_payload.get("candidate_actions") or []),
        "strong_clusters_count": len(review_payload.get("strong_clusters") or []),
        "weak_clusters_count": len(review_payload.get("weak_clusters") or []),
    },
    "review_governance": {
        "run_id": governance_run_id,
        "status": str(governance_payload.get("status") or ""),
        "mode": str(governance_payload.get("mode") or ""),
        "objects_total": int(governance_payload.get("objects_total") or 0),
        "candidate_actions_count": len(governance_payload.get("candidate_actions") or []),
        "carryover_action_ids_count": len(governance_payload.get("carryover_action_ids") or []),
    },
    "strategy": {
        key: int(value)
        for key, value in strategy_log.items()
        if key in {
            "goals",
            "themes",
            "strategies",
            "experiments",
            "workflows",
            "initiatives",
            "thread_proposals",
            "proposal_queue",
            "recruitment_candidates",
            "scorecard_entries",
            "clone_scorecard_entries",
            "cbm_mapping_rows",
        }
        and str(value).isdigit()
    },
    "top_selected_skills": [
        {"skill": name, "count": count}
        for name, count in selected_skill_counts.most_common(10)
    ],
}

summary_path = artifact_dir / "self-governance-summary.json"
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Remote Self Governance Audit",
    "",
    f"- Source ID: `{source_id}`",
    f"- Skills inventory: {summary['skills_inventory_count']}",
    f"- Sessions indexed: {summary['bundle_counts']['sessions']}",
    f"- Structured runs: {summary['bundle_counts']['runs']}",
    f"- Completed runs: {summary['run_quality']['completed_runs']}",
    f"- Review skills status: `{summary['review_skills']['status'] or 'missing'}`",
    f"- Governance objects total: {summary['review_governance']['objects_total']}",
    f"- Governance action candidates: {summary['review_governance']['candidate_actions_count']}",
    "",
    "## Top Selected Skills",
    "",
]
top_selected = summary["top_selected_skills"]
if top_selected:
    for item in top_selected:
        lines.append(f"- {item['skill']}: {item['count']}")
else:
    lines.append("- none")
summary_md = artifact_dir / "self-governance-summary.md"
summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(summary_path)
print(summary_md)
PY

  printf 'artifact_dir: %s\n' "$local_artifact_dir"
  printf 'remote_audit_dir: %s\n' "$remote_audit_dir"
  printf 'review_run_id: %s\n' "$review_run_id"
  printf 'governance_run_id: %s\n' "$governance_run_id"
  printf 'summary_json: %s\n' "${local_artifact_dir}/self-governance-summary.json"
  printf 'summary_md: %s\n' "${local_artifact_dir}/self-governance-summary.md"
}

main "$@"
