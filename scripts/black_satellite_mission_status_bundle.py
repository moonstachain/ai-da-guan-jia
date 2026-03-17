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
DEFAULT_SPLIT_PROTOCOL_MD = PROJECT_ROOT / "docs" / "ai-da-guan-jia-miaoda-surface-data-model-split-v1.md"
DEFAULT_DUTY_BUNDLE_JSON = (
    RUNS_ROOT
    / "2026-03-16"
    / "adagj-black-satellite-pmo-duty-officer-v1"
    / "duty-officer-bundle.json"
)
DEFAULT_CLEANUP_MANIFEST_JSON = (
    RUNS_ROOT
    / "2026-03-16"
    / "adagj-black-satellite-governance-cleanup-01"
    / "run-manifest.json"
)
DEFAULT_RUNTIME_GAP_BUNDLE_JSON = (
    RUNS_ROOT
    / "2026-03-16"
    / "adagj-dashboard-runtime-gap-bundle-01"
    / "dashboard-runtime-gap-bundle.json"
)


@dataclass
class MissionContext:
    run_id: str
    created_at: str
    output_dir: Path
    summary_json: Path
    governance_json: Path
    contract_json: Path
    protocol_md: Path
    split_protocol_md: Path
    duty_bundle_json: Path
    cleanup_manifest_json: Path
    runtime_gap_bundle_json: Path
    heartbeat_json: Path


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
            return path.resolve()
    raise FileNotFoundError(f"Unable to find current heartbeat for {window_id}")


def summary_map(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("window_id") or ""): item
        for item in summary.get("windows", [])
        if isinstance(item, dict) and str(item.get("window_id") or "").strip()
    }


def governance_map(govern: dict[str, Any]) -> dict[str, dict[str, Any]]:
    decisions = govern.get("decisions", []) if isinstance(govern.get("decisions"), list) else govern.get("windows", [])
    return {
        str(item.get("window_id") or ""): item
        for item in decisions
        if isinstance(item, dict) and str(item.get("window_id") or "").strip()
    }


def find_gap(runtime_gap_bundle: dict[str, Any], gap_id: str) -> dict[str, Any]:
    for item in runtime_gap_bundle.get("runtime_model_gaps", []):
        if isinstance(item, dict) and str(item.get("gap_id") or "") == gap_id:
            return item
    return {}


def track_statuses(
    *,
    heartbeat: dict[str, Any],
    summary: dict[str, Any],
    cleanup_manifest: dict[str, Any],
    runtime_gap_bundle: dict[str, Any],
) -> list[dict[str, Any]]:
    summary_windows = summary_map(summary)
    legacy_window = summary_windows.get("black-satellite", {})
    observability_window = summary_windows.get("window-observability-heartbeat", {})

    cleanup_absorbed = (
        str(legacy_window.get("accepted_cleanup_label") or "") == "archived_history_line"
        and str(observability_window.get("accepted_cleanup_label") or "") == "downgrade_to_history"
    )
    runtime_observability_gap = find_gap(runtime_gap_bundle, "runtime_source_view_observability")
    alias_contract_gap = find_gap(runtime_gap_bundle, "display_field_alias_contract")

    return [
        {
            "track_id": "pmo_beta_and_duty_officer",
            "status": "accepted_and_operational",
            "completion_percent": 92,
            "why": "黑色卫星已被接受为正式 `半自动远程控制面 + 窗口治理值班官 v1`，且 heartbeat 与值班 bundle 已稳定可消费。",
            "evidence_hint": str(heartbeat.get("current_phase") or ""),
        },
        {
            "track_id": "governance_cleanup_absorption",
            "status": "accepted_expression_absorbed" if cleanup_absorbed else "cleanup_accepted_but_expression_not_fully_absorbed",
            "completion_percent": 88 if cleanup_absorbed else 72,
            "why": "旧 black-satellite 与 window-observability-heartbeat 的历史化结论已被接受，并已进入 current summary 表达层；剩余工作在生命周期层吸收。",
            "evidence_hint": json.dumps(
                {
                    "legacy_label": legacy_window.get("accepted_cleanup_label", ""),
                    "observability_label": observability_window.get("accepted_cleanup_label", ""),
                    "package_a": cleanup_manifest.get("package_a", {}).get("recommended_label", ""),
                    "package_b": cleanup_manifest.get("package_b", {}).get("recommended_action", ""),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        },
        {
            "track_id": "miaoda_runtime_model_and_repo_local_verify",
            "status": "expected_contract_ready_waiting_live_reverify",
            "completion_percent": 78,
            "why": "diagnosis-03 / action-04 的 expected contract 与 reverify checklist 已固定，但 live source-view / binding evidence 仍待页面执行面回传。",
            "evidence_hint": json.dumps(
                {
                    "runtime_source_view_observability": runtime_observability_gap.get("status", ""),
                    "display_field_alias_contract": alias_contract_gap.get("status", ""),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        },
        {
            "track_id": "original_miaoda_phase2_end_to_end",
            "status": "out_of_scope_waiting_external_surface_signal",
            "completion_percent": 65,
            "why": "最终 live preview / real binding / final truth judgement 保留给页面执行面与运营主线，黑色卫星只做 support/verify。",
            "evidence_hint": "页面执行面仍未回传新的 live source-view / binding 证据。",
        },
    ]


def governance_view(
    *,
    summary: dict[str, Any],
    govern: dict[str, Any],
) -> list[dict[str, Any]]:
    summary_windows = summary_map(summary)
    govern_windows = governance_map(govern)
    window_ids = [
        "black-satellite",
        "black-satellite-pmo-beta",
        "operations-mainline",
        "window-observability-heartbeat",
    ]
    rows: list[dict[str, Any]] = []
    for window_id in window_ids:
        summary_item = summary_windows.get(window_id, {})
        govern_item = govern_windows.get(window_id, {})
        rows.append(
            {
                "window_id": window_id,
                "role": str(summary_item.get("role") or ""),
                "observed_state": str(govern_item.get("observed_state") or summary_item.get("observed_state") or ""),
                "recommended_action": str(govern_item.get("recommended_action") or govern_item.get("decision") or ""),
                "why": str(govern_item.get("governance_reason") or govern_item.get("reason") or summary_item.get("reason") or ""),
                "display_state": str(summary_item.get("display_state") or ""),
                "accepted_cleanup_label": str(summary_item.get("accepted_cleanup_label") or ""),
                "sole_blocker": str(summary_item.get("sole_blocker") or govern_item.get("sole_blocker") or ""),
            }
        )
    return rows


def stable_interfaces(context: MissionContext) -> list[dict[str, Any]]:
    return [
        {
            "interface_id": "window-heartbeat-current",
            "purpose": "让总控消费黑色卫星当前阶段、状态、唯一 blocker 与 repo-local 证据路径。",
            "source_path": str(context.heartbeat_json.resolve()),
            "keep_rule": "继续使用 `current_phase / current_status / latest_evidence_paths / sole_blocker`。",
        },
        {
            "interface_id": "window-governance-expression-layer",
            "purpose": "让总控看到已吸收后的 current summary/govern，而不是旧表象。",
            "source_path": str(context.governance_json.resolve()),
            "keep_rule": "继续使用 `display_state / accepted_cleanup_label / recommended_action`。",
        },
        {
            "interface_id": "duty-officer-bundle",
            "purpose": "作为总控消费当前窗口状态、Top 1 处理窗口、Top 1 冻结窗口和最大失真的正式面。",
            "source_path": str(context.duty_bundle_json.resolve()),
            "keep_rule": "只有窗口状态、唯一 blocker 或关键证据变化时才刷新。",
        },
        {
            "interface_id": "cleanup-package",
            "purpose": "作为旧 black-satellite 与 window-observability-heartbeat 的唯一历史化依据。",
            "source_path": str(context.cleanup_manifest_json.resolve()),
            "keep_rule": "结论已成立后不重复分析，只在生命周期吸收时被引用。",
        },
        {
            "interface_id": "dashboard-runtime-gap-bundle",
            "purpose": "作为 diagnosis-03 / action-04 的 expected contract 与 reverify 基线。",
            "source_path": str(context.runtime_gap_bundle_json.resolve()),
            "keep_rule": "只在 spec 或 live evidence 真实变化时刷新。",
        },
    ]


def remaining_work(runtime_gap_bundle: dict[str, Any]) -> dict[str, Any]:
    runtime_gap_ids = [
        str(item.get("gap_id") or "")
        for item in runtime_gap_bundle.get("runtime_model_gaps", [])
        if isinstance(item, dict)
    ]
    return {
        "black_satellite_owned": [
            {
                "work_id": "maintain_formal_duty_state",
                "owner": "black-satellite-pmo-beta",
                "status": "ongoing",
                "next_step": "只在窗口状态、唯一 blocker 或关键证据真实变化时刷新 heartbeat 与 duty-officer bundle。",
            },
            {
                "work_id": "consume_next_live_page_evidence",
                "owner": "black-satellite-pmo-beta",
                "status": "waiting_external_signal",
                "next_step": "页面执行面回传新的 bind-cards/post-check 证据后，按 4 条 reverify 规则完成 support/verify。",
            },
        ],
        "external_dependencies": [
            {
                "work_id": "lifecycle_absorb_old_lines",
                "owner": "总控/主枢纽",
                "status": "pending_external",
                "why": "cleanup 结论已成立，但生命周期层真正历史化仍保留给总控与主枢纽。",
            },
            {
                "work_id": "page_surface_realign_and_republish",
                "owner": "页面执行面 / 人类",
                "status": "pending_external",
                "why": "正确 preview 重发、真实 page object 对齐、最终 source-view 绑定不属于黑色卫星职责。",
            },
        ],
        "next_reverify_checks": [
            {
                "check_id": "selected_source_view_exact_match",
                "expectation": "selected_source_view 与 expected view_name exact 对齐。",
            },
            {
                "check_id": "binding_evidence_kind_live",
                "expectation": "binding_evidence_kind 不再是 `page_source_static_json`。",
            },
            {
                "check_id": "source_evidence_upgraded",
                "expectation": "source_evidence 不再是 `plan_only_not_observed_in_ui`。",
            },
            {
                "check_id": "action_04_truth_classified",
                "expectation": "action-04 基于 live evidence 落入四分类之一。",
            },
        ],
        "runtime_gap_ids": runtime_gap_ids,
        "current_biggest_unfinished": "页面执行面仍未回传新的 live source-view / binding evidence，因此黑色卫星最后一段 support/verify 还不能触发。",
        "next_external_signal_needed": "页面执行面回传：已重发当前 app，可复验；并提供新的 bind-cards / post-check repo-local 证据。",
    }


def acceptance_definition() -> list[str]:
    return [
        "总控默认把黑色卫星当作正式 `PMO Beta + 值班官` 使用，而不是一次性支线。",
        "旧 `black-satellite` 与 `window-observability-heartbeat` 不再被当成活跃推进线消费。",
        "`diagnosis-03 / action-04` 的 repo-local expected contract 与 reverify contract 已被实际用过至少一轮。",
        "页面执行面与运营主线能基于黑色卫星产物完成最后诚实复验，而不需要黑色卫星继续做模型层探索。",
    ]


def default_boundaries(contract: dict[str, Any]) -> dict[str, Any]:
    role_boundary = contract.get("role_boundary", {}) if isinstance(contract.get("role_boundary"), dict) else {}
    split_rule = contract.get("miaoda_split_rule", {}) if isinstance(contract.get("miaoda_split_rule"), dict) else {}
    return {
        "black_satellite_can_do": role_boundary.get("can_do", []),
        "black_satellite_cannot_do": role_boundary.get("cannot_do", []),
        "retained_by_main_hub": role_boundary.get("retained_by_main_hub", []),
        "retained_by_human": role_boundary.get("retained_by_human", []),
        "miaoda_surface_split": split_rule,
    }


def source_artifacts(context: MissionContext) -> dict[str, str]:
    return {
        "heartbeat_json": str(context.heartbeat_json.resolve()),
        "summary_json": str(context.summary_json.resolve()),
        "governance_json": str(context.governance_json.resolve()),
        "duty_officer_bundle_json": str(context.duty_bundle_json.resolve()),
        "cleanup_manifest_json": str(context.cleanup_manifest_json.resolve()),
        "runtime_gap_bundle_json": str(context.runtime_gap_bundle_json.resolve()),
        "pmo_beta_contract_json": str(context.contract_json.resolve()),
        "pmo_beta_protocol_md": str(context.protocol_md.resolve()),
        "miaoda_split_protocol_md": str(context.split_protocol_md.resolve()),
    }


def build_bundle(context: MissionContext) -> dict[str, Any]:
    heartbeat = load_json(context.heartbeat_json)
    summary = load_json(context.summary_json)
    govern = load_json(context.governance_json)
    contract = load_json(context.contract_json)
    duty_bundle = load_json(context.duty_bundle_json)
    cleanup_manifest = load_json(context.cleanup_manifest_json)
    runtime_gap_bundle = load_json(context.runtime_gap_bundle_json)
    tracks = track_statuses(
        heartbeat=heartbeat,
        summary=summary,
        cleanup_manifest=cleanup_manifest,
        runtime_gap_bundle=runtime_gap_bundle,
    )
    return {
        "schema_version": "black-satellite-mission-status-bundle-v1",
        "run_id": context.run_id,
        "created_at": context.created_at,
        "mission_owner": "black-satellite-pmo-beta",
        "mission_role": "半自动远程控制面 + 窗口治理值班官 v1 + Miaoda Phase 2 support/verify 面",
        "bundle_goal": "把黑色卫星总体目标、完成度、稳定接口与剩余收尾动作压成 repo-local 可复用对象，供总控直接消费。",
        "source_artifacts": source_artifacts(context),
        "mission_summary": {
            "overall_goal": [
                "把黑色卫星从一次性页面专项支线升级成可被总控持续调度的正式治理面。",
                "把旧 black-satellite 与旧观测噪音压成可历史化对象，避免继续污染治理视图。",
                "把 diagnosis-03 / action-04 的 runtime data model、expected binding、expected evidence chain 固化成 repo-local verify 合同。",
            ],
            "current_judgement": "黑色卫星职责内的大头已完成，当前主要处于等待页面执行面回传 live 证据后的最后 support/verify 阶段。",
        },
        "completion_assessment": {
            "black_satellite_owned_completion_percent": 85,
            "original_miaoda_phase2_end_to_end_completion_percent": 65,
            "tracks": tracks,
        },
        "current_state": {
            "heartbeat_phase": str(heartbeat.get("current_phase") or ""),
            "heartbeat_status": str(heartbeat.get("current_status") or ""),
            "last_action": str(heartbeat.get("last_action") or ""),
            "sole_blocker": str(heartbeat.get("sole_blocker") or ""),
            "latest_evidence_paths": heartbeat.get("latest_evidence_paths", []),
            "governance_windows": governance_view(summary=summary, govern=govern),
            "current_top_priority_window": duty_bundle.get("top_priority_window", {}),
            "current_top_frozen_window": duty_bundle.get("top_frozen_window", {}),
            "current_global_max_distortion": duty_bundle.get("global_max_distortion", {}),
        },
        "stable_interfaces": stable_interfaces(context),
        "remaining_work": remaining_work(runtime_gap_bundle),
        "acceptance_definition": acceptance_definition(),
        "default_boundaries": default_boundaries(contract),
    }


def render_bundle_markdown(bundle: dict[str, Any]) -> str:
    completion = bundle.get("completion_assessment", {})
    current_state = bundle.get("current_state", {})
    remaining = bundle.get("remaining_work", {})
    lines = [
        "# Black Satellite Mission Status Bundle",
        "",
        f"- run_id: `{bundle.get('run_id', '')}`",
        f"- created_at: `{bundle.get('created_at', '')}`",
        f"- owned_completion: `{completion.get('black_satellite_owned_completion_percent', 0)}%`",
        f"- end_to_end_completion: `{completion.get('original_miaoda_phase2_end_to_end_completion_percent', 0)}%`",
        f"- heartbeat_phase: `{current_state.get('heartbeat_phase', '')}`",
        f"- heartbeat_status: `{current_state.get('heartbeat_status', '')}`",
        f"- current_biggest_unfinished: {remaining.get('current_biggest_unfinished', '')}",
        "",
        "## Tracks",
        "",
    ]
    for track in completion.get("tracks", []):
        lines.extend(
            [
                f"- `{track.get('track_id', '')}` | status=`{track.get('status', '')}` | completion=`{track.get('completion_percent', 0)}%`",
                f"  - why: {track.get('why', '')}",
            ]
        )
    lines.extend(["", "## Stable Interfaces", ""])
    for item in bundle.get("stable_interfaces", []):
        lines.extend(
            [
                f"- `{item.get('interface_id', '')}`",
                f"  - purpose: {item.get('purpose', '')}",
                f"  - source_path: `{item.get('source_path', '')}`",
                f"  - keep_rule: {item.get('keep_rule', '')}",
            ]
        )
    lines.extend(["", "## Remaining Work", ""])
    for item in remaining.get("black_satellite_owned", []):
        lines.append(f"- owned:`{item.get('work_id', '')}` -> {item.get('next_step', '')}")
    for item in remaining.get("external_dependencies", []):
        lines.append(f"- external:`{item.get('work_id', '')}` / owner=`{item.get('owner', '')}` -> {item.get('why', '')}")
    return "\n".join(lines) + "\n"


def render_quickstart(bundle: dict[str, Any]) -> str:
    completion = bundle.get("completion_assessment", {})
    remaining = bundle.get("remaining_work", {})
    return "\n".join(
        [
            "# Black Satellite Mission Quickstart",
            "",
            "- 何时打开：总控要快速判断黑色卫星总体完成度、是否还能继续自治、以及下一跳该等谁时。",
            "- 先看 3 行：",
            f"  - `owned_completion`: {completion.get('black_satellite_owned_completion_percent', 0)}%",
            f"  - `current_biggest_unfinished`: {remaining.get('current_biggest_unfinished', '')}",
            f"  - `next_external_signal_needed`: {remaining.get('next_external_signal_needed', '')}",
            "- 决策方法：",
            "  - 如果缺的是页面执行面 live 证据，就保持黑色卫星在 support/verify 边界，不把页面最终修复推给它。",
            "  - 如果旧线生命周期吸收还没做，就引用 cleanup package，不重新分析旧 black-satellite。",
            "  - 如果 live 证据已经回传，就按 runtime gap bundle 的 4 条 reverify checks 触发最后一段 support/verify。",
        ]
    ) + "\n"


def verify_bundle(bundle: dict[str, Any], context: MissionContext, bundle_json_path: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    required_paths = [
        context.heartbeat_json,
        context.summary_json,
        context.governance_json,
        context.contract_json,
        context.duty_bundle_json,
        context.cleanup_manifest_json,
        context.runtime_gap_bundle_json,
        context.protocol_md,
        context.split_protocol_md,
        bundle_json_path,
        context.output_dir / "run-manifest.json",
        context.output_dir / "support" / "quickstart.md",
    ]
    for path in required_paths:
        checks.append({"name": f"exists:{path.name}", "ok": path.exists(), "detail": str(path.resolve())})
    for path in [
        context.heartbeat_json,
        context.summary_json,
        context.governance_json,
        context.contract_json,
        context.duty_bundle_json,
        context.cleanup_manifest_json,
        context.runtime_gap_bundle_json,
        bundle_json_path,
    ]:
        try:
            json.loads(path.read_text(encoding="utf-8"))
            checks.append({"name": f"parse:{path.name}", "ok": True, "detail": "json_parse_ok"})
        except Exception as exc:  # pragma: no cover - defensive
            checks.append({"name": f"parse:{path.name}", "ok": False, "detail": f"json_parse_failed:{exc}"})

    summary = load_json(context.summary_json)
    summary_windows = summary_map(summary)
    runtime_gap_bundle = load_json(context.runtime_gap_bundle_json)
    cleanup_manifest = load_json(context.cleanup_manifest_json)
    current_state = bundle.get("current_state", {})
    remaining = bundle.get("remaining_work", {})
    completion = bundle.get("completion_assessment", {})

    checks.append(
        {
            "name": "cleanup:legacy_label_absorbed",
            "ok": str(summary_windows.get("black-satellite", {}).get("accepted_cleanup_label") or "") == "archived_history_line",
            "detail": str(summary_windows.get("black-satellite", {}).get("accepted_cleanup_label") or ""),
        }
    )
    checks.append(
        {
            "name": "cleanup:observability_label_absorbed",
            "ok": str(summary_windows.get("window-observability-heartbeat", {}).get("accepted_cleanup_label") or "") == "downgrade_to_history",
            "detail": str(summary_windows.get("window-observability-heartbeat", {}).get("accepted_cleanup_label") or ""),
        }
    )
    checks.append(
        {
            "name": "cleanup:manifest_matches_expected_labels",
            "ok": (
                str(cleanup_manifest.get("package_a", {}).get("recommended_label") or "") == "archived_history_line"
                and str(cleanup_manifest.get("package_b", {}).get("recommended_action") or "") == "downgrade_to_history"
            ),
            "detail": json.dumps(
                {
                    "package_a": cleanup_manifest.get("package_a", {}).get("recommended_label", ""),
                    "package_b": cleanup_manifest.get("package_b", {}).get("recommended_action", ""),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        }
    )
    checks.append(
        {
            "name": "runtime-gap:focus_cards_match",
            "ok": runtime_gap_bundle.get("focus_card_ids") == ["diagnosis-03", "action-04"],
            "detail": json.dumps(runtime_gap_bundle.get("focus_card_ids", []), ensure_ascii=False),
        }
    )
    checks.append(
        {
            "name": "runtime-gap:open_gap_ids_match",
            "ok": set(remaining.get("runtime_gap_ids", [])) == {"runtime_source_view_observability", "display_field_alias_contract"},
            "detail": json.dumps(remaining.get("runtime_gap_ids", []), ensure_ascii=False),
        }
    )
    checks.append(
        {
            "name": "bundle:completion_assessment_present",
            "ok": completion.get("black_satellite_owned_completion_percent") == 85 and completion.get("original_miaoda_phase2_end_to_end_completion_percent") == 65,
            "detail": json.dumps(
                {
                    "owned": completion.get("black_satellite_owned_completion_percent", 0),
                    "end_to_end": completion.get("original_miaoda_phase2_end_to_end_completion_percent", 0),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        }
    )
    checks.append(
        {
            "name": "bundle:current_window_id_matches_heartbeat",
            "ok": str(context.heartbeat_json.name).endswith(".json") and "black-satellite-pmo-beta" in str(context.heartbeat_json),
            "detail": str(current_state.get("heartbeat_phase") or ""),
        }
    )
    checks.append(
        {
            "name": "bundle:biggest_unfinished_mentions_live_evidence",
            "ok": "live source-view / binding evidence" in str(remaining.get("current_biggest_unfinished") or ""),
            "detail": str(remaining.get("current_biggest_unfinished") or ""),
        }
    )
    status = "completed" if all(item.get("ok") for item in checks) else "failed_partial"
    return {
        "schema_version": "black-satellite-mission-status-verify-v1",
        "run_id": context.run_id,
        "status": status,
        "checks": checks,
    }


def write_bundle(context: MissionContext) -> dict[str, Any]:
    ensure_dir(context.output_dir)
    ensure_dir(context.output_dir / "support")
    ensure_dir(context.output_dir / "verify")
    bundle = build_bundle(context)
    bundle_json_path = context.output_dir / "black-satellite-mission-status-bundle.json"
    bundle_md_path = context.output_dir / "black-satellite-mission-status-bundle.md"
    quickstart_path = context.output_dir / "support" / "quickstart.md"
    verify_path = context.output_dir / "verify" / "verification-report.json"
    manifest_path = context.output_dir / "run-manifest.json"

    write_json(bundle_json_path, bundle)
    bundle_md_path.write_text(render_bundle_markdown(bundle), encoding="utf-8")
    quickstart_path.write_text(render_quickstart(bundle), encoding="utf-8")
    write_json(
        manifest_path,
        {
            "schema_version": "black-satellite-mission-status-manifest-v1",
            "run_id": context.run_id,
            "created_at": context.created_at,
            "bundle_json": str(bundle_json_path.resolve()),
            "bundle_md": str(bundle_md_path.resolve()),
            "support_quickstart": str(quickstart_path.resolve()),
            "verify_report": str(verify_path.resolve()),
            "replay_command": f"python3 {SCRIPT_PATH} --run-id {context.run_id} --output-dir {context.output_dir}",
        },
    )
    verification = verify_bundle(bundle, context, bundle_json_path)
    write_json(verify_path, verification)
    return {
        "bundle": bundle,
        "verification": verification,
        "bundle_json_path": bundle_json_path,
        "bundle_md_path": bundle_md_path,
        "quickstart_path": quickstart_path,
        "verify_path": verify_path,
        "manifest_path": manifest_path,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate repo-local black-satellite mission status bundle.")
    parser.add_argument("--run-id", default="adagj-black-satellite-mission-status-01", help="Stable run id.")
    parser.add_argument("--created-at", default="", help="Optional ISO datetime override.")
    parser.add_argument("--summary-json", default=str(DEFAULT_SUMMARY_JSON), help="Current summary json path.")
    parser.add_argument("--governance-json", default=str(DEFAULT_GOVERNANCE_JSON), help="Current governance summary path.")
    parser.add_argument("--contract-json", default=str(DEFAULT_CONTRACT_JSON), help="PMO beta contract path.")
    parser.add_argument("--protocol-md", default=str(DEFAULT_PROTOCOL_MD), help="PMO beta protocol markdown path.")
    parser.add_argument("--split-protocol-md", default=str(DEFAULT_SPLIT_PROTOCOL_MD), help="Miaoda split protocol markdown path.")
    parser.add_argument("--duty-bundle-json", default=str(DEFAULT_DUTY_BUNDLE_JSON), help="Duty officer bundle json path.")
    parser.add_argument("--cleanup-manifest-json", default=str(DEFAULT_CLEANUP_MANIFEST_JSON), help="Cleanup manifest json path.")
    parser.add_argument("--runtime-gap-bundle-json", default=str(DEFAULT_RUNTIME_GAP_BUNDLE_JSON), help="Runtime gap bundle json path.")
    parser.add_argument("--heartbeat-json", default="", help="Optional current heartbeat json path override.")
    parser.add_argument("--output-dir", default="", help="Optional output dir override.")
    return parser


def resolve_context(args: argparse.Namespace) -> MissionContext:
    created_at = str(args.created_at or iso_now())
    created_dt = datetime.fromisoformat(created_at)
    output_dir = (
        Path(str(args.output_dir)).expanduser().resolve()
        if str(args.output_dir or "").strip()
        else RUNS_ROOT / created_dt.strftime("%Y-%m-%d") / str(args.run_id or "adagj-black-satellite-mission-status-01")
    )
    heartbeat_json = (
        Path(str(args.heartbeat_json)).expanduser().resolve()
        if str(args.heartbeat_json or "").strip()
        else current_heartbeat_path_for("black-satellite-pmo-beta")
    )
    return MissionContext(
        run_id=str(args.run_id or "adagj-black-satellite-mission-status-01"),
        created_at=created_at,
        output_dir=output_dir,
        summary_json=Path(str(args.summary_json)).expanduser().resolve(),
        governance_json=Path(str(args.governance_json)).expanduser().resolve(),
        contract_json=Path(str(args.contract_json)).expanduser().resolve(),
        protocol_md=Path(str(args.protocol_md)).expanduser().resolve(),
        split_protocol_md=Path(str(args.split_protocol_md)).expanduser().resolve(),
        duty_bundle_json=Path(str(args.duty_bundle_json)).expanduser().resolve(),
        cleanup_manifest_json=Path(str(args.cleanup_manifest_json)).expanduser().resolve(),
        runtime_gap_bundle_json=Path(str(args.runtime_gap_bundle_json)).expanduser().resolve(),
        heartbeat_json=heartbeat_json,
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    context = resolve_context(args)
    result = write_bundle(context)
    print(
        json.dumps(
            {
                "run_id": context.run_id,
                "output_dir": str(context.output_dir.resolve()),
                "verification_status": result["verification"]["status"],
                "bundle_json": str(result["bundle_json_path"].resolve()),
                "verify_report": str(result["verify_path"].resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
