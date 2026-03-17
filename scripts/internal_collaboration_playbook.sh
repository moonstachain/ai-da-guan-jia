#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MVP_SCRIPT="${SCRIPT_DIR}/internal_ops_mvp.sh"
CLONE_CURRENT_ROOT="${AI_DA_GUAN_JIA_CLONE_CURRENT_ROOT:-${SCRIPT_DIR}/../artifacts/ai-da-guan-jia/clones/current}"
GUIDE_PATH="${SCRIPT_DIR}/../AI大管家-同事协作成长路径说明.md"
CONTRACT_PATH="${SCRIPT_DIR}/../references/internal-collaboration-lifecycle-contract.md"
MVP_GUIDE_PATH="${SCRIPT_DIR}/../AI大管家-内部同事版第一闭环MVP启用说明.md"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/internal_collaboration_playbook.sh bootstrap <clone-id> "<display-name>" [report-owner] [manager-clone-id]
  bash scripts/internal_collaboration_playbook.sh midday [report-date]
  bash scripts/internal_collaboration_playbook.sh evening [report-date]
  bash scripts/internal_collaboration_playbook.sh status [clone-id]
  bash scripts/internal_collaboration_playbook.sh phase-map
  bash scripts/internal_collaboration_playbook.sh colleague-loop
  bash scripts/internal_collaboration_playbook.sh founder-loop
  bash scripts/internal_collaboration_playbook.sh evolution-loop
  bash scripts/internal_collaboration_playbook.sh org-scale
  bash scripts/internal_collaboration_playbook.sh perfect-state
  bash scripts/internal_collaboration_playbook.sh overview

Commands:
  bootstrap       Register and start the first internal ops-management colleague clone.
  midday          Run the noon internal review from the existing MVP toolchain.
  evening         Run the evening internal review from the existing MVP toolchain.
  status          Infer the current lifecycle phase from local canonical artifacts.
  phase-map       Print the full Phase 0 -> Phase 4 collaboration map.
  colleague-loop  Print the colleague-side daily operating loop.
  founder-loop    Print the founder-side monitoring and intervention loop.
  evolution-loop  Print what AI大管家 must capture and how proposals get promoted.
  org-scale       Print the Phase 4 replication rules.
  perfect-state   Print the target end-state across colleague / founder / AI layers.
  overview        Print the full lifecycle overview in one place.
EOF
}

delegate_to_mvp() {
  bash "${MVP_SCRIPT}" "$@"
}

print_phase_map() {
  cat <<'EOF'
Phase 0: 激活与边界定型
- 目标: 让同事拥有独立岗位实例，不再共用 founder 会话。
- 成果: clone_id / memory_namespace / scorecard / training history ready.
- 验收: bootstrap 成功，internal portfolio 可见，clone governance dry-run 可见。

Phase 1: 学会和 AI大管家 协作
- 目标: 建立早上定重点、白天续上下文、晚上收口的固定节奏。
- 成果: 真实任务被压成 next_step / blocker / evidence / closure_state。
- 验收: 连续 5 天真实任务闭环，80% 任务进入明确 closure state。

Phase 2: 岗位半自治操盘
- 目标: AI大管家 代管 intake、压任务、优先级、blocker、evidence、收口建议。
- 成果: 同事形成重点清楚、阻塞清楚、收口清楚的稳定节奏。
- 验收: founder 手工催办和追问下降 30%+。

Phase 3: 从会用升级到会进化
- 目标: 同事的岗位经验开始变成组织方法，而不只是个人执行效率。
- 成果: recurring patterns、skill chains、distortion、boundaries、method candidates 进入 capability proposals。
- 验收: capability_proposals 可复核，可做 shared_core / tenant_local / reject 决策。

Phase 4: 组织复制与共享治理
- 目标: 把成熟路径复制到第二位同事和第二个岗位，不复制 repo 和 skill 仓库。
- 成果: 总部仍看一个主库，但可以比较多个岗位实例的评分和风险。
- 验收: 第二位同事接入时，只复制实例配置，不复制治理核心。
EOF
}

print_colleague_loop() {
  cat <<'EOF'
Colleague daily loop:
- Morning: 先说“今天最该看什么”，不清楚时再说“帮我接个任务：...”
- Daytime: 只做“我现在有哪些任务 / 继续昨天那个 / 原力原力 记一下 ...”
- Evening: 固定说“把这事闭环”

Colleague responsibilities:
- 提供目标、上下文、业务判断、边界动作
- 不自己先拆一堆碎步骤
- 不让 AI 同时扮演多个岗位
- 不把 GitHub 或底表当工作入口

Frontstage limits:
- 同时最多 3 条活跃任务
- 任务只允许 4 种 closure_state:
  completed / blocked_needs_user / blocked_system / failed_partial
EOF
}

print_founder_loop() {
  cat <<'EOF'
Founder monitoring loop:
- 中午: 看 waiting_human / blocked_* / 风险与决策表
- 晚上: 看 closure_state、evidence、blocker、明日训练建议

Founder responsibilities:
- 默认看摘要，不看全量细节
- 只对审批、付款、发布、删除、法务确认等高影响边界拍板
- 复核 capability proposals，决定 shared core 晋升与否

Founder summary-first questions:
- 现在谁在推进
- 谁卡住了
- 哪件事在等我拍板
- 哪个 clone 在变强，哪个 clone 在失真

Founder drill-down objects:
- task_runs
- capability_proposals
- alerts_decisions
- portfolio-daily-report
EOF
}

print_evolution_loop() {
  cat <<'EOF'
AI大管家 evolution loop:
1. 从真实任务里抓 recurring task patterns
2. 识别有效 skill chains
3. 识别 distortion patterns
4. 识别人类边界 patterns
5. 提炼 role-method candidates

Canonical sinks:
- task-runs.json
- training-cycles.json
- clone-scorecard.json
- capability-proposals.json
- alerts-decisions.json

Promotion path:
instance-local improvement
-> capability_proposals
-> HQ review
-> promote_shared_core / keep_tenant_local / reject

Truth rule:
- 不把聊天顺滑当闭环
- 不把看板亮了当减负
- 不把 Feishu 镜像当 canonical
EOF
}

print_org_scale() {
  cat <<'EOF'
Phase 4 replication rules:
- 共享同一个 AI大管家 治理核
- 每位同事一个独立 clone
- 每位同事一个主岗位模板
- 总部仍看一个主库和一个 HQ cockpit
- 不复制 repo
- 不复制 skill 仓库

Scale-out order:
1. 中台管理 first
2. 第二位同事接入
3. 产品或交付岗位接入
4. 财务 / 法务等高风险岗位最后接入

What HQ compares:
- score shift
- distortion rate
- blocker visibility
- proposal quality
- promotion recommendation
EOF
}

print_perfect_state() {
  cat <<'EOF'
Perfect state:
- 同事层: 每个人都有岗位副驾，工作被压成清晰推进和可验证收口。
- Founder 层: 默认看摘要，异常时下钻，不再靠亲自盯人维持推进。
- AI大管家 层: 不断吸收真实岗位经验，反哺 role templates、skill chains、boundary rules、scorecard metrics 和 governance rules。
EOF
}

print_status() {
  local requested_clone_id="${1:-}"
  python3 - "${CLONE_CURRENT_ROOT}" "${requested_clone_id}" "${GUIDE_PATH}" "${CONTRACT_PATH}" "${MVP_GUIDE_PATH}" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
requested_clone_id = sys.argv[2].strip()
guide_path = sys.argv[3]
contract_path = sys.argv[4]
mvp_guide_path = sys.argv[5]


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def as_list(value):
    return value if isinstance(value, list) else []


registry = as_list(load_json(root / "clone-registry.json", []))
scorecards = as_list(load_json(root / "clone-scorecard.json", []))
task_runs = as_list(load_json(root / "task-runs.json", []))
training_cycles = as_list(load_json(root / "training-cycles.json", []))
capability_proposals = as_list(load_json(root / "capability-proposals.json", []))
alerts = as_list(load_json(root / "alerts-decisions.json", []))
portfolio_report = load_json(root / "portfolio-daily-report.json", {})

internal_employee_rows = [
    row
    for row in registry
    if str(row.get("portfolio_scope") or "") == "internal"
    and str(row.get("actor_type") or "") in {"employee", "founder"}
]
internal_role_templates = sorted(
    {
        str(row.get("role_template_id") or "").strip()
        for row in internal_employee_rows
        if str(row.get("role_template_id") or "").strip()
    }
)

target = {}
if requested_clone_id:
    target = next((row for row in registry if str(row.get("clone_id") or "") == requested_clone_id), {})
if not target:
    target = next(
        (
            row
            for row in internal_employee_rows
            if str(row.get("role_template_id") or "") == "ops-management"
        ),
        {},
    )
if not target:
    target = internal_employee_rows[0] if internal_employee_rows else (registry[0] if registry else {})

clone_id = str(target.get("clone_id") or "")
scorecard = next((row for row in scorecards if str(row.get("clone_id") or "") == clone_id), {})
clone_task_runs = [row for row in task_runs if str(row.get("clone_id") or "") == clone_id]
clone_training_cycles = [row for row in training_cycles if str(row.get("clone_id") or "") == clone_id]
clone_proposals = [row for row in capability_proposals if str(row.get("clone_id") or "") == clone_id]
clone_alerts = [row for row in alerts if str(row.get("clone_id") or "") == clone_id]
open_alerts = [
    row
    for row in clone_alerts
    if str(row.get("status") or "").strip() in {"", "open", "pending_approval", "pending_hq_review"}
]
approval_alerts = [row for row in open_alerts if bool(row.get("approval_required"))]

sections = portfolio_report.get("sections") if isinstance(portfolio_report.get("sections"), dict) else {}
top_risk = ""
for row in sections.get("当前最大失真与主要风险", []):
    if clone_id and str(row.get("clone_id") or "") not in {"", clone_id}:
        continue
    top_risk = str(row.get("summary") or "").strip()
    if top_risk:
        break
if not top_risk and open_alerts:
    top_risk = str(open_alerts[0].get("title") or "").strip()

next_training = ""
for row in sections.get("明日训练建议", []):
    if clone_id and str(row.get("clone_id") or "") not in {"", clone_id}:
        continue
    next_training = str(row.get("summary") or "").strip()
    if next_training:
        break

promotion_summary = ""
for row in sections.get("候选晋升 / 降权 / 休眠", []):
    if clone_id and str(row.get("clone_id") or "") not in {"", clone_id}:
        continue
    promotion_summary = str(row.get("summary") or "").strip()
    if promotion_summary:
        break

latest_proposal = str(clone_proposals[0].get("proposal_title") or "").strip() if clone_proposals else ""
training_runs = int(float(scorecard.get("training_runs") or 0))
routing_priority = float(scorecard.get("routing_priority") or 0.0)


def infer_phase():
    if not clone_id:
        return (
            "Phase 0",
            "还没有发现可用的 internal colleague clone，本轮仍停留在激活前。",
            "先完成 bootstrap，并确认 internal portfolio 和 clone governance dry-run 已生成。",
            "注册第一位同事，跑通第一天真实任务。",
        )
    if len(internal_employee_rows) >= 2 and len(internal_role_templates) >= 2:
        return (
            "Phase 4",
            "已经看到多位内部同事或多个内部岗位模板，系统进入组织复制与共享治理阶段。",
            "比较不同岗位 clone 的评分变化、失真率和高价值方法，再决定模板复制和提权降权。",
            "确保第二位同事接入时仍复用同一个治理核，而不是复制 repo 或 skill 仓库。",
        )
    if clone_proposals:
        return (
            "Phase 3",
            "已经出现 capability proposals，说明这位同事的真实工作正在转成可复核的方法资产。",
            "优先复核 capability proposals，决定 shared core 晋升、tenant-local 保留，还是驳回。",
            "把最新提案走完 HQ review，避免进化材料停留在漂亮提法层。",
        )
    if training_runs >= 5 or len(clone_task_runs) >= 5 or routing_priority >= 55:
        return (
            "Phase 2",
            "训练与执行样本已经累积到可稳定运转，当前更像岗位半自治操盘而不是新手协作试水。",
            "盯住 waiting_human / blocked_* / 风险与决策表，验证 founder 追问和催办是否真实下降。",
            "继续把前台活跃任务压在 3 条以内，并巩固重点清楚、阻塞清楚、收口清楚。",
        )
    if len(clone_task_runs) > 0 or len(clone_training_cycles) > 0 or training_runs > 0:
        return (
            "Phase 1",
            "已经有真实任务和训练痕迹，说明同事正在学习和 AI大管家 协作。",
            "继续盯真实任务是否都能落到明确 closure_state，而不是模糊推进中。",
            "把 5 天真实任务闭环跑满，并至少两次正确拦在人类边界。",
        )
    return (
        "Phase 0",
        "clone 已注册，但还没有看到足够的真实任务样本，当前仍属于激活与边界定型。",
        "确认同事会用固定口令或等价本地入口，并开始第一条真实任务。",
        "让 bootstrap 后的第一天真实任务进入 task_runs 与 evening close-out。",
    )


phase_name, phase_reason, founder_focus, next_gate = infer_phase()

print(f"guide_path: {guide_path}")
print(f"contract_path: {contract_path}")
print(f"mvp_guide_path: {mvp_guide_path}")
print(f"clone_root: {root}")
print(f"current_phase: {phase_name}")
print(f"phase_reason: {phase_reason}")
print(f"founder_focus: {founder_focus}")
print(f"next_gate: {next_gate}")
print(f"clone_id: {clone_id or 'not_bootstrapped'}")
print(f"display_name: {str(target.get('display_name') or '').strip() or 'n/a'}")
print(f"role_template_id: {str(target.get('role_template_id') or '').strip() or 'n/a'}")
print(f"portfolio_scope: {str(target.get('portfolio_scope') or portfolio_report.get('portfolio') or '').strip() or 'n/a'}")
print(f"internal_employee_clone_count: {len(internal_employee_rows)}")
print(f"internal_role_template_count: {len(internal_role_templates)}")
print(f"task_run_count: {len(clone_task_runs)}")
print(f"training_cycle_count: {len(clone_training_cycles)}")
print(f"training_runs: {training_runs}")
print(f"capability_proposal_count: {len(clone_proposals)}")
print(f"open_alert_count: {len(open_alerts)}")
print(f"approval_required_alert_count: {len(approval_alerts)}")
print(f"routing_priority: {round(routing_priority, 2)}")
print(f"autonomy_cap: {str(scorecard.get('autonomy_cap') or '').strip() or 'n/a'}")
print(f"promotion_recommendation: {str(scorecard.get('promotion_recommendation') or '').strip() or 'n/a'}")
print(f"top_risk: {top_risk or 'n/a'}")
print(f"next_training_suggestion: {next_training or 'n/a'}")
print(f"latest_proposal: {latest_proposal or 'n/a'}")
print(f"promotion_summary: {promotion_summary or 'n/a'}")
PY
}

print_overview() {
  echo "guide_path: ${GUIDE_PATH}"
  echo "contract_path: ${CONTRACT_PATH}"
  echo "mvp_guide_path: ${MVP_GUIDE_PATH}"
  echo
  print_phase_map
  echo
  print_colleague_loop
  echo
  print_founder_loop
  echo
  print_evolution_loop
  echo
  print_org_scale
  echo
  print_perfect_state
}

command="${1:-help}"
if [[ $# -gt 0 ]]; then
  shift
fi

case "${command}" in
  bootstrap)
    delegate_to_mvp bootstrap "$@"
    echo
    echo "playbook_path: ${GUIDE_PATH}"
    echo "recommended_next:"
    echo "- bash scripts/internal_collaboration_playbook.sh status ${1:-}"
    echo "- bash scripts/internal_collaboration_playbook.sh phase-map"
    ;;
  midday)
    delegate_to_mvp midday "$@"
    echo
    echo "recommended_next: bash scripts/internal_collaboration_playbook.sh founder-loop"
    ;;
  evening)
    delegate_to_mvp evening "$@"
    echo
    echo "recommended_next: bash scripts/internal_collaboration_playbook.sh status"
    ;;
  status)
    print_status "$@"
    ;;
  phase-map)
    print_phase_map
    ;;
  colleague-loop)
    print_colleague_loop
    ;;
  founder-loop)
    print_founder_loop
    ;;
  evolution-loop)
    print_evolution_loop
    ;;
  org-scale)
    print_org_scale
    ;;
  perfect-state)
    print_perfect_state
    ;;
  overview)
    print_overview
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
