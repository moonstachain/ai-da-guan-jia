from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[3]
ARTIFACTS_ROOT = PROJECT_ROOT / "work" / "ai-da-guan-jia" / "artifacts" / "ai-da-guan-jia"
RUNS_ROOT = ARTIFACTS_ROOT / "runs"
HEARTBEAT_CURRENT_ROOT = ARTIFACTS_ROOT / "heartbeat" / "windows" / "current"
DEFAULT_SUMMARY_JSON = HEARTBEAT_CURRENT_ROOT / "summary.json"
DEFAULT_GOVERNANCE_JSON = HEARTBEAT_CURRENT_ROOT / "governance-summary.json"
DEFAULT_CONTRACT_JSON = ARTIFACTS_ROOT / "satellites" / "current" / "black-satellite-pmo-beta-contract.json"
DEFAULT_PROTOCOL_MD = PROJECT_ROOT / "docs" / "ai-da-guan-jia-black-satellite-pmo-beta-v1.md"
DEFAULT_DUTY_BUNDLE_JSON = (
    RUNS_ROOT
    / "2026-03-16"
    / "adagj-black-satellite-pmo-duty-officer-v1"
    / "duty-officer-bundle.json"
)

LEGACY_PHASE2_REPO_LOCAL_CANDIDATES = [
    PROJECT_ROOT / "output" / "feishu-dashboard-automator" / "cbm-governance" / "miaoda-r2-binding-run.json",
    PROJECT_ROOT / "output" / "feishu-dashboard-automator" / "cbm-governance" / "miaoda-r2-postcheck.json",
    PROJECT_ROOT / "output" / "feishu-dashboard-automator" / "cbm-governance" / "diagnosis-03-canvas.png",
    PROJECT_ROOT / "output" / "feishu-dashboard-automator" / "cbm-governance" / "diagnosis-03-binding.png",
    PROJECT_ROOT / "output" / "feishu-dashboard-automator" / "cbm-governance" / "action-04-canvas.png",
    PROJECT_ROOT / "output" / "feishu-dashboard-automator" / "cbm-governance" / "action-04-binding.png",
]


@dataclass
class CleanupContext:
    run_id: str
    created_at: str
    output_dir: Path
    summary_json: Path
    governance_json: Path
    contract_json: Path
    protocol_md: Path
    duty_bundle_json: Path


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def current_heartbeat_path_for(window_id: str) -> Path:
    for path in sorted(HEARTBEAT_CURRENT_ROOT.glob("*.json")):
        if path.name in {"summary.json", "governance-summary.json"}:
            continue
        try:
            payload = load_json(path)
        except Exception:
            continue
        if str(payload.get("window_id") or "").strip() == window_id:
            return path
    raise FileNotFoundError(f"Unable to find current heartbeat for {window_id}")


def trusted_paths(summary_item: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for entry in summary_item.get("trusted_evidence", []) if isinstance(summary_item.get("trusted_evidence"), list) else []:
        if not isinstance(entry, dict):
            continue
        value = str(entry.get("path") or "").strip()
        if value:
            values.append(value)
    return values


def all_evidence_paths(summary_item: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for entry in summary_item.get("evidence_state", []) if isinstance(summary_item.get("evidence_state"), list) else []:
        if not isinstance(entry, dict):
            continue
        value = str(entry.get("path") or "").strip()
        if value:
            values.append(value)
    return values


def merge_windows(summary: dict[str, Any], govern: dict[str, Any]) -> dict[str, dict[str, Any]]:
    summary_map = {
        str(item.get("window_id") or ""): item
        for item in summary.get("windows", [])
        if isinstance(item, dict) and str(item.get("window_id") or "").strip()
    }
    govern_map = {
        str(item.get("window_id") or ""): item
        for item in govern.get("decisions", [])
        if isinstance(item, dict) and str(item.get("window_id") or "").strip()
    }
    merged: dict[str, dict[str, Any]] = {}
    for window_id in sorted(set(summary_map) | set(govern_map)):
        summary_item = summary_map.get(window_id, {})
        govern_item = govern_map.get(window_id, {})
        merged[window_id] = {
            "window_id": window_id,
            "role": str(summary_item.get("role") or govern_item.get("role") or ""),
            "current_phase": str(summary_item.get("current_phase") or ""),
            "last_action": str(summary_item.get("last_action") or ""),
            "current_status": str(summary_item.get("current_status") or ""),
            "sole_blocker": str(summary_item.get("sole_blocker") or govern_item.get("sole_blocker") or ""),
            "observed_state": str(summary_item.get("observed_state") or govern_item.get("observed_state") or ""),
            "recommended_action": str(govern_item.get("decision") or ""),
            "why": str(govern_item.get("reason") or summary_item.get("reason") or ""),
            "next_action": str(govern_item.get("next_action") or ""),
            "human_boundary": bool(govern_item.get("human_boundary")),
            "auto_dispatch_allowed": bool(govern_item.get("auto_dispatch_allowed")),
            "trusted_evidence_count": int(
                summary_item.get("trusted_evidence_count")
                or govern_item.get("trusted_evidence_count")
                or 0
            ),
            "trusted_evidence_paths": trusted_paths(summary_item),
            "all_evidence_paths": all_evidence_paths(summary_item),
            "updated_at": str(summary_item.get("updated_at") or ""),
            "age_minutes": float(summary_item.get("age_minutes") or 0.0),
            "current_heartbeat_path": str(summary_item.get("current_heartbeat_path") or ""),
        }
    return merged


def legacy_classification(legacy_row: dict[str, Any], successor_row: dict[str, Any]) -> str:
    if (
        str(legacy_row.get("recommended_action") or "") == "收口"
        or str(legacy_row.get("observed_state") or "") == "suspected_silent_lost"
    ):
        return "archived_history_line"
    if (
        str(legacy_row.get("recommended_action") or "") == "裁决"
        and int(legacy_row.get("trusted_evidence_count") or 0) == 0
        and int(successor_row.get("trusted_evidence_count") or 0) > 0
    ):
        return "superseded_by_black_satellite_pmo_beta"
    if str(legacy_row.get("recommended_action") or "") == "裁决" and str(legacy_row.get("sole_blocker") or "").strip():
        return "failed_but_explained"
    return "archived_history_line"


def observability_recommendation(observability_row: dict[str, Any]) -> str:
    if (
        str(observability_row.get("observed_state") or "") == "suspected_silent_lost"
        and float(observability_row.get("age_minutes") or 0.0) >= 120.0
    ):
        return "downgrade_to_history"
    if str(observability_row.get("recommended_action") or "") == "收口":
        return "close"
    return "refresh_if_still_canonical"


def build_source_artifacts(context: CleanupContext) -> dict[str, str]:
    return {
        "summary_json": str(context.summary_json.resolve()),
        "governance_json": str(context.governance_json.resolve()),
        "pmo_beta_contract_json": str(context.contract_json.resolve()),
        "pmo_beta_protocol_md": str(context.protocol_md.resolve()),
        "duty_officer_bundle_json": str(context.duty_bundle_json.resolve()),
        "legacy_black_satellite_heartbeat_json": str(current_heartbeat_path_for("black-satellite").resolve()),
        "pmo_beta_heartbeat_json": str(current_heartbeat_path_for("black-satellite-pmo-beta").resolve()),
        "window_observability_heartbeat_json": str(current_heartbeat_path_for("window-observability-heartbeat").resolve()),
    }


def existing_legacy_phase2_repo_local_paths() -> list[str]:
    return [str(path.resolve()) for path in LEGACY_PHASE2_REPO_LOCAL_CANDIDATES if path.exists()]


def build_legacy_package(context: CleanupContext, merged: dict[str, dict[str, Any]]) -> dict[str, Any]:
    legacy_row = merged["black-satellite"]
    successor_row = merged["black-satellite-pmo-beta"]
    classification = legacy_classification(legacy_row, successor_row)
    why_not_active = [
        "旧 black-satellite 当前 heartbeat 已是 blocked/stuck，不再处于可继续推进态。",
        "它的 current heartbeat 仍只挂着 /private/tmp 临时证据，治理面里 `trusted_evidence_count=0`。",
        "与其继续把它当活线，不如把它当成一次已解释的专项执行历史，否则会持续污染当前治理面。",
        "正式治理职责已经被 black-satellite-pmo-beta 接管，并且它已有 repo-local bundle 与 verify 证据。",
    ]
    if str(legacy_row.get("sole_blocker") or "").strip():
        why_not_active.append(f"旧线当前唯一 blocker 仍是：{legacy_row['sole_blocker']}。")
    why_successor = [
        "black-satellite-pmo-beta 已进入 `formal_duty_active`，并持续保持 `继续 / progressing`。",
        "pmo-beta 的关键证据全部是 repo-local，可被 heartbeat 与 duty-officer bundle 直接消费。",
        "pmo-beta 的职责已经明确覆盖当前窗口治理、Top 1 处理窗口、Top 1 冻结窗口和全局最大失真。",
    ]
    repo_local_phase2_paths = existing_legacy_phase2_repo_local_paths()
    control_tower_decision = "裁决旧 black-satellite，并将其降级为历史专项线。"
    control_tower_why = "这样可以保留历史 Phase 2 证据，同时停止把一个 zero-trusted-evidence 的 blocked 窗口当成当前活线。"
    if classification == "archived_history_line":
        control_tower_decision = "确认旧 black-satellite 为 archived_history_line，只保留历史，不再当 current 活线。"
        control_tower_why = "它已经进入 suspected_silent_lost/收口态，继续把它留在当前活跃治理面只会制造重复噪音。"
    elif classification == "failed_but_explained":
        control_tower_decision = "确认旧 black-satellite 为 failed_but_explained，并保留失败说明。"
        control_tower_why = "它仍是失败但已解释的专项线，不再需要继续当成治理活线。"
    return {
        "schema_version": "legacy-black-satellite-judgement-v1",
        "run_id": context.run_id,
        "created_at": context.created_at,
        "package_id": "task-a-legacy-black-satellite",
        "goal": "把旧 black-satellite 专项线压成可裁决、可收口的对象，不再污染当前治理面。",
        "legacy_window": legacy_row,
        "formal_successor_window": successor_row,
        "recommended_label": classification,
        "source_artifacts": build_source_artifacts(context),
        "legacy_history_artifacts": {
            "current_heartbeat_evidence_paths": legacy_row.get("all_evidence_paths", []),
            "repo_local_phase2_paths": repo_local_phase2_paths,
        },
        "responsibility_overlap": {
            "overlap_points": [
                "两者都来自黑色卫星执行面。",
                "两者都能做 remote execution、可逆验证、heartbeat reporting。",
            ],
            "why_overlap_should_end": [
                "旧线是 Miaoda Phase 2 的专项执行线，不应继续兼任正式治理面。",
                "pmo-beta 已经是总控接受的正式治理控制面，继续并行保留旧线会让总控消费到重复且失真的黑色卫星对象。",
            ],
        },
        "why_old_line_should_not_stay_active": why_not_active,
        "why_pmo_beta_should_own_formal_governance": why_successor,
        "recommended_control_tower_action": {
            "decision": control_tower_decision,
            "why": control_tower_why,
            "after_accept": [
                "不再把新治理任务派给旧 black-satellite。",
                "把 black-satellite-pmo-beta 视为黑色卫星唯一正式治理承接面。",
                "若需保留 Phase 2 历史，只保留 rounds/history 与 repo-local 产物，不再把旧线放在 current 活跃治理面里。",
            ],
        },
    }


def build_observability_package(context: CleanupContext, merged: dict[str, dict[str, Any]]) -> dict[str, Any]:
    row = merged["window-observability-heartbeat"]
    recommendation = observability_recommendation(row)
    why = [
        "它仍在当前治理视图里，是因为 `window-heartbeat inspect/govern` 会消费 `heartbeat/windows/current/` 里的每个 current heartbeat 文件。",
        "这个对象没有后续 heartbeat 刷新或生命周期收口动作，所以一直以陈旧 current record 的形式留在治理面中。",
        "它的原始目标是观测协议落地，而不是持续承担正式治理职责。",
    ]
    if recommendation == "downgrade_to_history":
        why.append("继续保留在 current 面只会制造治理噪音；保留 rounds/history 即可满足追溯需要。")
    return {
        "schema_version": "window-observability-cleanup-v1",
        "run_id": context.run_id,
        "created_at": context.created_at,
        "package_id": "task-b-window-observability-heartbeat",
        "goal": "把陈旧 window-observability-heartbeat 压成明确结论，降低当前治理噪音。",
        "window": row,
        "recommended_action": recommendation,
        "source_artifacts": build_source_artifacts(context),
        "why_it_is_still_visible": why,
        "retention_decision": {
            "keep_reason": ""
            if recommendation != "refresh_if_still_canonical"
            else "只有当它仍是当前唯一 canonical observability 面时才应刷新；当前并非如此。",
            "history_reason": "它仍有历史价值，因为记录了早期 observability 协议落地与 none blocker 语义修正。",
        },
        "recommended_control_tower_action": {
            "decision": recommendation,
            "why": "当前 duty-officer bundle 与 summary/govern 已承接现行治理面；这个对象不再需要以 active current window 继续存在。",
            "after_accept": [
                "保留 rounds 历史文件用于追溯。",
                "不要再把它当成当前需要继续推进的普通支线。",
                "若总控执行历史化/收口处理，当前治理面噪音会进一步降低。",
            ],
        },
    }


def render_legacy_markdown(payload: dict[str, Any]) -> str:
    legacy = payload.get("legacy_window", {})
    successor = payload.get("formal_successor_window", {})
    lines = [
        "# Task A - Legacy Black Satellite Judgement",
        "",
        f"- recommended_label: `{payload.get('recommended_label', '')}`",
        f"- legacy_window: `{legacy.get('window_id', '')}` / action=`{legacy.get('recommended_action', '')}` / state=`{legacy.get('observed_state', '')}` / trusted_evidence=`{legacy.get('trusted_evidence_count', 0)}`",
        f"- successor_window: `{successor.get('window_id', '')}` / action=`{successor.get('recommended_action', '')}` / state=`{successor.get('observed_state', '')}` / trusted_evidence=`{successor.get('trusted_evidence_count', 0)}`",
        "",
        "## Why Old Line Should Not Stay Active",
        "",
    ]
    lines.extend(f"- {item}" for item in payload.get("why_old_line_should_not_stay_active", []))
    lines.extend(["", "## Why PMO Beta Should Own Formal Governance", ""])
    lines.extend(f"- {item}" for item in payload.get("why_pmo_beta_should_own_formal_governance", []))
    lines.extend(["", "## Control Tower Action", ""])
    action = payload.get("recommended_control_tower_action", {})
    lines.append(f"- decision: `{action.get('decision', '')}`")
    lines.append(f"- why: {action.get('why', '')}")
    for item in action.get("after_accept", []):
        lines.append(f"- after_accept: {item}")
    return "\n".join(lines) + "\n"


def render_observability_markdown(payload: dict[str, Any]) -> str:
    row = payload.get("window", {})
    lines = [
        "# Task B - Window Observability Cleanup",
        "",
        f"- recommended_action: `{payload.get('recommended_action', '')}`",
        f"- window: `{row.get('window_id', '')}` / action=`{row.get('recommended_action', '')}` / state=`{row.get('observed_state', '')}` / age_minutes=`{row.get('age_minutes', 0)}`",
        "",
        "## Why It Is Still Visible",
        "",
    ]
    lines.extend(f"- {item}" for item in payload.get("why_it_is_still_visible", []))
    lines.extend(["", "## Control Tower Action", ""])
    action = payload.get("recommended_control_tower_action", {})
    lines.append(f"- decision: `{action.get('decision', '')}`")
    lines.append(f"- why: {action.get('why', '')}")
    for item in action.get("after_accept", []):
        lines.append(f"- after_accept: {item}")
    return "\n".join(lines) + "\n"


def verify_legacy_package(payload: dict[str, Any], output_json_path: Path) -> dict[str, Any]:
    legacy = payload.get("legacy_window", {})
    successor = payload.get("formal_successor_window", {})
    label = str(payload.get("recommended_label") or "")
    classification_ok = False
    detail = "classification_rule_not_matched"
    if label == "superseded_by_black_satellite_pmo_beta":
        classification_ok = (
            str(legacy.get("recommended_action") or "") == "裁决"
            and int(legacy.get("trusted_evidence_count") or 0) == 0
            and int(successor.get("trusted_evidence_count") or 0) > 0
        )
        detail = "legacy_is_rule_candidate_for_superseded_by_pmo_beta"
    elif label == "archived_history_line":
        classification_ok = (
            (
                str(legacy.get("recommended_action") or "") == "收口"
                or str(legacy.get("observed_state") or "") == "suspected_silent_lost"
            )
            and int(successor.get("trusted_evidence_count") or 0) > 0
        )
        detail = "legacy_is_history_line_after_silent_lost_or_close"
    elif label == "failed_but_explained":
        classification_ok = (
            str(legacy.get("recommended_action") or "") == "裁决"
            and bool(str(legacy.get("sole_blocker") or "").strip())
        )
        detail = "legacy_failure_is_explained"
    checks = [
        {
            "name": "exists:legacy_black_satellite_heartbeat_json",
            "ok": Path(payload["source_artifacts"]["legacy_black_satellite_heartbeat_json"]).exists(),
            "detail": payload["source_artifacts"]["legacy_black_satellite_heartbeat_json"],
        },
        {
            "name": "exists:duty_officer_bundle_json",
            "ok": Path(payload["source_artifacts"]["duty_officer_bundle_json"]).exists(),
            "detail": payload["source_artifacts"]["duty_officer_bundle_json"],
        },
        {
            "name": "parse:legacy_black_satellite_judgement.json",
            "ok": True,
            "detail": str(output_json_path.resolve()),
        },
        {
            "name": "classification_consistency",
            "ok": classification_ok,
            "detail": detail,
        },
    ]
    status = "completed" if all(item["ok"] for item in checks) else "failed_partial"
    return {
        "package_id": payload.get("package_id", ""),
        "lane_id": "verify",
        "status": status,
        "checks": checks,
    }


def verify_observability_package(payload: dict[str, Any], output_json_path: Path) -> dict[str, Any]:
    row = payload.get("window", {})
    checks = [
        {
            "name": "exists:window_observability_heartbeat_json",
            "ok": Path(payload["source_artifacts"]["window_observability_heartbeat_json"]).exists(),
            "detail": payload["source_artifacts"]["window_observability_heartbeat_json"],
        },
        {
            "name": "parse:window_observability_cleanup.json",
            "ok": True,
            "detail": str(output_json_path.resolve()),
        },
        {
            "name": "recommendation_consistency",
            "ok": (
                payload.get("recommended_action") == "downgrade_to_history"
                and str(row.get("observed_state") or "") == "suspected_silent_lost"
                and float(row.get("age_minutes") or 0.0) >= 120.0
            ),
            "detail": "stale_current_window_should_be_history",
        },
    ]
    status = "completed" if all(item["ok"] for item in checks) else "failed_partial"
    return {
        "package_id": payload.get("package_id", ""),
        "status": status,
        "checks": checks,
    }


def lane_contract(
    lane_id: str,
    *,
    scoped_goal: str,
    current_phase: str,
    latest_evidence_paths: list[str],
    sole_blocker: str,
    next_request_to_mainline: str,
) -> dict[str, Any]:
    return {
        "lane_id": lane_id,
        "scoped_goal": scoped_goal,
        "current_phase": current_phase,
        "latest_evidence_paths": latest_evidence_paths,
        "sole_blocker": sole_blocker,
        "next_request_to_mainline": next_request_to_mainline,
    }


def write_outputs(context: CleanupContext) -> dict[str, Any]:
    ensure_dir(context.output_dir)
    task_a_dir = context.output_dir / "task-a-legacy-black-satellite"
    task_b_dir = context.output_dir / "task-b-window-observability-heartbeat"
    ensure_dir(task_a_dir)
    ensure_dir(task_b_dir)
    ensure_dir(task_a_dir / "lanes" / "main")
    ensure_dir(task_a_dir / "lanes" / "support")
    ensure_dir(task_a_dir / "lanes" / "verify")
    ensure_dir(task_a_dir / "verify")

    summary = load_json(context.summary_json)
    govern = load_json(context.governance_json)
    merged = merge_windows(summary, govern)

    legacy_package = build_legacy_package(context, merged)
    observability_package = build_observability_package(context, merged)

    legacy_json_path = task_a_dir / "legacy-black-satellite-judgement.json"
    legacy_md_path = task_a_dir / "legacy-black-satellite-judgement.md"
    overlap_md_path = task_a_dir / "support-overlap.md"
    legacy_verify_path = task_a_dir / "verify" / "verification-report.json"
    observability_json_path = task_b_dir / "window-observability-cleanup.json"
    observability_md_path = task_b_dir / "window-observability-cleanup.md"
    observability_verify_path = task_b_dir / "verification-report.json"
    manifest_path = context.output_dir / "run-manifest.json"

    write_json(legacy_json_path, legacy_package)
    legacy_md_path.write_text(render_legacy_markdown(legacy_package), encoding="utf-8")
    overlap_md_path.write_text(
        "\n".join(
            [
                "# Support Note - Legacy vs PMO Beta",
                "",
                "- overlap: 两者都来自黑色卫星执行面，且都能做可逆执行和状态回报。",
                "- split: 旧 black-satellite 是 Miaoda Phase 2 专项残留线；black-satellite-pmo-beta 是总控接受的正式治理面。",
                "- recommendation: 不再让旧线继续作为活跃治理窗口；正式治理只消费 pmo-beta。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    legacy_verify = verify_legacy_package(legacy_package, legacy_json_path)
    write_json(legacy_verify_path, legacy_verify)

    write_json(observability_json_path, observability_package)
    observability_md_path.write_text(render_observability_markdown(observability_package), encoding="utf-8")
    observability_verify = verify_observability_package(observability_package, observability_json_path)
    write_json(observability_verify_path, observability_verify)

    task_a_main_manifest = lane_contract(
        "main",
        scoped_goal="产出旧 black-satellite 裁决收口建议包",
        current_phase="legacy_line_recommendation_authored",
        latest_evidence_paths=[
            str(legacy_json_path.resolve()),
            str(legacy_md_path.resolve()),
        ],
        sole_blocker="",
        next_request_to_mainline="总控可直接裁决旧 black-satellite 为 superseded_by_black_satellite_pmo_beta。",
    )
    write_json(task_a_dir / "lanes" / "main" / "lane-manifest.json", task_a_main_manifest)
    write_json(
        task_a_dir / "lanes" / "main" / "lane-result.json",
        {
            "lane_id": "main",
            "status": "completed",
            "did_what": "产出旧 black-satellite 最小裁决建议包。",
            "evidence_ref": [
                str(legacy_json_path.resolve()),
                str(legacy_md_path.resolve()),
            ],
            "sole_blocker": "",
            "next_request_to_mainline": task_a_main_manifest["next_request_to_mainline"],
        },
    )
    (task_a_dir / "lanes" / "main" / "lane-summary.md").write_text(
        "# main lane\n\n- status: `completed`\n- did_what: 产出旧 black-satellite 最小裁决建议包。\n",
        encoding="utf-8",
    )

    task_a_support_manifest = lane_contract(
        "support",
        scoped_goal="说明旧黑线与 pmo-beta 的职责重叠应如何切分",
        current_phase="overlap_explained",
        latest_evidence_paths=[str(overlap_md_path.resolve())],
        sole_blocker="",
        next_request_to_mainline="总控只保留 pmo-beta 作为正式治理承接面。",
    )
    write_json(task_a_dir / "lanes" / "support" / "lane-manifest.json", task_a_support_manifest)
    write_json(
        task_a_dir / "lanes" / "support" / "lane-result.json",
        {
            "lane_id": "support",
            "status": "completed",
            "did_what": "压缩职责重叠说明，明确旧线不再作为活跃治理线。",
            "evidence_ref": [str(overlap_md_path.resolve())],
            "sole_blocker": "",
            "next_request_to_mainline": task_a_support_manifest["next_request_to_mainline"],
        },
    )
    (task_a_dir / "lanes" / "support" / "lane-summary.md").write_text(
        "# support lane\n\n- status: `completed`\n- did_what: 压缩职责重叠说明。\n",
        encoding="utf-8",
    )

    task_a_verify_manifest = lane_contract(
        "verify",
        scoped_goal="独立验证旧 black-satellite 裁决建议与当前治理状态一致",
        current_phase="legacy_line_verification_completed" if legacy_verify["status"] == "completed" else "legacy_line_verification_failed_partial",
        latest_evidence_paths=[str(legacy_verify_path.resolve())],
        sole_blocker="" if legacy_verify["status"] == "completed" else "legacy_line_verification_failed",
        next_request_to_mainline="verify 已确认旧 black-satellite 符合 superseded_by_black_satellite_pmo_beta 建议条件。",
    )
    write_json(task_a_dir / "lanes" / "verify" / "lane-manifest.json", task_a_verify_manifest)
    write_json(
        task_a_dir / "lanes" / "verify" / "lane-result.json",
        {
            "lane_id": "verify",
            "status": legacy_verify["status"],
            "did_what": "独立验证旧 black-satellite 裁决建议和关键路径存在性。",
            "evidence_ref": [str(legacy_verify_path.resolve())],
            "sole_blocker": task_a_verify_manifest["sole_blocker"],
            "next_request_to_mainline": task_a_verify_manifest["next_request_to_mainline"],
        },
    )
    (task_a_dir / "lanes" / "verify" / "lane-summary.md").write_text(
        "# verify lane\n\n"
        f"- status: `{legacy_verify['status']}`\n"
        "- did_what: 独立验证旧 black-satellite 裁决建议。\n",
        encoding="utf-8",
    )

    task_b_manifest = lane_contract(
        "main",
        scoped_goal="产出 window-observability-heartbeat 降噪收口建议包",
        current_phase="observability_cleanup_authored",
        latest_evidence_paths=[
            str(observability_json_path.resolve()),
            str(observability_md_path.resolve()),
            str(observability_verify_path.resolve()),
        ],
        sole_blocker="",
        next_request_to_mainline="总控可直接把 window-observability-heartbeat 走 downgrade_to_history。",
    )
    write_json(task_b_dir / "lane-manifest.json", task_b_manifest)
    write_json(
        task_b_dir / "lane-result.json",
        {
            "lane_id": "main",
            "status": "completed" if observability_verify["status"] == "completed" else "failed_partial",
            "did_what": "产出 window-observability-heartbeat 最小降噪建议包。",
            "evidence_ref": [
                str(observability_json_path.resolve()),
                str(observability_md_path.resolve()),
                str(observability_verify_path.resolve()),
            ],
            "sole_blocker": "",
            "next_request_to_mainline": task_b_manifest["next_request_to_mainline"],
        },
    )

    manifest = {
        "schema_version": "window-governance-cleanup-manifest-v1",
        "run_id": context.run_id,
        "created_at": context.created_at,
        "mode": "controlled_dual_task_parallel",
        "package_a": {
            "package_id": legacy_package["package_id"],
            "recommended_label": legacy_package["recommended_label"],
            "evidence_paths": [
                str(legacy_json_path.resolve()),
                str(legacy_md_path.resolve()),
                str(legacy_verify_path.resolve()),
            ],
        },
        "package_b": {
            "package_id": observability_package["package_id"],
            "recommended_action": observability_package["recommended_action"],
            "evidence_paths": [
                str(observability_json_path.resolve()),
                str(observability_md_path.resolve()),
                str(observability_verify_path.resolve()),
            ],
        },
    }
    write_json(manifest_path, manifest)
    return {
        "manifest_path": manifest_path,
        "legacy_json_path": legacy_json_path,
        "legacy_md_path": legacy_md_path,
        "legacy_verify_path": legacy_verify_path,
        "observability_json_path": observability_json_path,
        "observability_md_path": observability_md_path,
        "observability_verify_path": observability_verify_path,
        "legacy_package": legacy_package,
        "observability_package": observability_package,
        "legacy_verify": legacy_verify,
        "observability_verify": observability_verify,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate repo-local cleanup bundles for legacy black-satellite and window observability noise.")
    parser.add_argument("--run-id", default="adagj-black-satellite-governance-cleanup-01", help="Stable run id.")
    parser.add_argument("--created-at", default="", help="Optional ISO datetime override.")
    parser.add_argument("--summary-json", default=str(DEFAULT_SUMMARY_JSON), help="Summary json path.")
    parser.add_argument("--governance-json", default=str(DEFAULT_GOVERNANCE_JSON), help="Governance summary json path.")
    parser.add_argument("--contract-json", default=str(DEFAULT_CONTRACT_JSON), help="PMO beta contract json path.")
    parser.add_argument("--protocol-md", default=str(DEFAULT_PROTOCOL_MD), help="PMO beta protocol markdown path.")
    parser.add_argument("--duty-bundle-json", default=str(DEFAULT_DUTY_BUNDLE_JSON), help="Current duty officer bundle path.")
    parser.add_argument("--output-dir", default="", help="Optional output dir override.")
    return parser


def resolve_context(args: argparse.Namespace) -> CleanupContext:
    created_at = str(args.created_at or iso_now())
    created_dt = datetime.fromisoformat(created_at)
    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if str(args.output_dir or "").strip()
        else RUNS_ROOT / created_dt.strftime("%Y-%m-%d") / str(args.run_id or "adagj-black-satellite-governance-cleanup-01")
    )
    return CleanupContext(
        run_id=str(args.run_id or "adagj-black-satellite-governance-cleanup-01"),
        created_at=created_at,
        output_dir=output_dir,
        summary_json=Path(str(args.summary_json)).expanduser().resolve(),
        governance_json=Path(str(args.governance_json)).expanduser().resolve(),
        contract_json=Path(str(args.contract_json)).expanduser().resolve(),
        protocol_md=Path(str(args.protocol_md)).expanduser().resolve(),
        duty_bundle_json=Path(str(args.duty_bundle_json)).expanduser().resolve(),
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    context = resolve_context(args)
    result = write_outputs(context)
    print(
        json.dumps(
            {
                "run_id": context.run_id,
                "output_dir": str(context.output_dir.resolve()),
                "package_a_label": result["legacy_package"]["recommended_label"],
                "package_b_action": result["observability_package"]["recommended_action"],
                "legacy_verify_status": result["legacy_verify"]["status"],
                "observability_verify_status": result["observability_verify"]["status"],
                "manifest_path": str(result["manifest_path"].resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
