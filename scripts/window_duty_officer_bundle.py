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
DEFAULT_TRIAL_RUN_DIR = RUNS_ROOT / "2026-03-15" / "adagj-black-satellite-pmo-beta-trial-01"

ACTION_PRIORITY = {
    "裁决": 0,
    "等待": 1,
    "继续": 2,
    "收口": 3,
}


@dataclass
class BundleContext:
    run_id: str
    created_at: str
    output_dir: Path
    summary_json: Path
    governance_json: Path
    contract_json: Path
    protocol_md: Path
    trial_run_dir: Path | None


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def trusted_paths(summary_item: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for entry in summary_item.get("trusted_evidence", []) if isinstance(summary_item.get("trusted_evidence"), list) else []:
        if not isinstance(entry, dict):
            continue
        value = str(entry.get("path") or "").strip()
        if value:
            paths.append(value)
    return paths


def build_windows(summary: dict[str, Any], govern: dict[str, Any]) -> list[dict[str, Any]]:
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
    windows: list[dict[str, Any]] = []
    for window_id, decision in govern_map.items():
        summary_item = summary_map.get(window_id, {})
        windows.append(
            {
                "window_id": window_id,
                "role": str(summary_item.get("role") or decision.get("role") or ""),
                "current_phase": str(summary_item.get("current_phase") or ""),
                "current_status": str(summary_item.get("current_status") or ""),
                "observed_state": str(decision.get("observed_state") or summary_item.get("observed_state") or ""),
                "recommended_action": str(decision.get("decision") or ""),
                "why": str(decision.get("reason") or summary_item.get("reason") or ""),
                "next_action": str(decision.get("next_action") or ""),
                "sole_blocker": str(decision.get("sole_blocker") or summary_item.get("sole_blocker") or ""),
                "human_boundary": bool(decision.get("human_boundary")),
                "auto_dispatch_allowed": bool(decision.get("auto_dispatch_allowed")),
                "trusted_evidence_count": int(
                    decision.get("trusted_evidence_count")
                    or summary_item.get("trusted_evidence_count")
                    or 0
                ),
                "trusted_evidence_paths": trusted_paths(summary_item),
                "current_heartbeat_path": str(summary_item.get("current_heartbeat_path") or ""),
                "updated_at": str(summary_item.get("updated_at") or ""),
                "age_minutes": float(summary_item.get("age_minutes") or 0.0),
            }
        )
    windows.sort(key=lambda row: (ACTION_PRIORITY.get(row["recommended_action"], 99), row["window_id"]))
    return windows


def priority_score(row: dict[str, Any]) -> float:
    action = str(row.get("recommended_action") or "")
    base = {
        "裁决": 400.0,
        "等待": 250.0,
        "继续": 180.0,
        "收口": 120.0,
    }.get(action, 0.0)
    if str(row.get("sole_blocker") or "").strip():
        base += 50.0
    if bool(row.get("auto_dispatch_allowed")):
        base += 10.0
    base += min(float(row.get("age_minutes") or 0.0), 120.0)
    return base


def freeze_score(row: dict[str, Any]) -> float:
    if str(row.get("recommended_action") or "") != "等待":
        return -1.0
    base = 300.0
    if str(row.get("sole_blocker") or "").strip():
        base += 50.0
    base += min(float(row.get("age_minutes") or 0.0), 120.0)
    return base


def top_priority_window(windows: list[dict[str, Any]]) -> dict[str, Any]:
    if not windows:
        return {}
    return max(windows, key=priority_score)


def top_frozen_window(windows: list[dict[str, Any]]) -> dict[str, Any]:
    waiting_rows = [row for row in windows if str(row.get("recommended_action") or "") == "等待"]
    if not waiting_rows:
        return {}
    return max(waiting_rows, key=freeze_score)


def global_max_distortion(windows: list[dict[str, Any]]) -> dict[str, Any]:
    for row in windows:
        if (
            str(row.get("recommended_action") or "") == "裁决"
            and int(row.get("trusted_evidence_count") or 0) == 0
        ):
            return {
                "window_id": str(row.get("window_id") or ""),
                "summary": "把无可信 repo-local 证据的旧窗口继续当成活跃执行面，会误导总控继续消费一个本应先裁决的 stuck 窗口。",
                "why": f"{row.get('window_id', '')} 当前是 `{row.get('recommended_action', '')}`，但 `trusted_evidence_count=0`，只剩旧临时路径与历史动作文本。",
            }
    frozen = top_frozen_window(windows)
    if frozen:
        return {
            "window_id": str(frozen.get("window_id") or ""),
            "summary": "把真实等待态误当成可继续推进，会让总控越过当前外部等待边界。",
            "why": f"{frozen.get('window_id', '')} 当前应保持 `{frozen.get('recommended_action', '')}`，否则会掩盖真实 blocker：{frozen.get('sole_blocker', '')}",
        }
    return {
        "window_id": "",
        "summary": "当前未识别到更大的治理失真。",
        "why": "",
    }


def action_counts(windows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in windows:
        key = str(row.get("recommended_action") or "")
        counts[key] = counts.get(key, 0) + 1
    return counts


def to_priority_view(row: dict[str, Any]) -> dict[str, Any]:
    if not row:
        return {}
    return {
        "window_id": str(row.get("window_id") or ""),
        "recommended_action": str(row.get("recommended_action") or ""),
        "why": str(row.get("why") or ""),
        "next_action": str(row.get("next_action") or ""),
        "sole_blocker": str(row.get("sole_blocker") or ""),
    }


def source_artifacts(context: BundleContext) -> dict[str, str]:
    payload = {
        "summary_json": str(context.summary_json.resolve()),
        "governance_json": str(context.governance_json.resolve()),
        "pmo_beta_contract_json": str(context.contract_json.resolve()),
        "pmo_beta_protocol_md": str(context.protocol_md.resolve()),
    }
    if context.trial_run_dir:
        payload["prior_trial_run_dir"] = str(context.trial_run_dir.resolve())
    return payload


def build_bundle(context: BundleContext) -> dict[str, Any]:
    summary = load_json(context.summary_json)
    govern = load_json(context.governance_json)
    windows = build_windows(summary, govern)
    top_priority = top_priority_window(windows)
    top_frozen = top_frozen_window(windows)
    max_distortion = global_max_distortion(windows)
    return {
        "schema_version": "window-duty-officer-bundle-v1",
        "run_id": context.run_id,
        "created_at": context.created_at,
        "duty_officer_role": "黑色卫星 PMO Beta Duty Officer v1",
        "bundle_goal": "为总控提供当前窗口清单、推荐动作、最优先处理窗口、应保持冻结窗口和唯一最大失真。",
        "source_artifacts": source_artifacts(context),
        "active_window_summary": {
            "window_count": len(windows),
            "recommended_action_counts": action_counts(windows),
            "top_priority_window_id": str(top_priority.get("window_id") or ""),
            "top_frozen_window_id": str(top_frozen.get("window_id") or ""),
        },
        "top_priority_window": to_priority_view(top_priority),
        "top_frozen_window": to_priority_view(top_frozen),
        "global_max_distortion": max_distortion,
        "windows": windows,
        "operator_quickstart": {
            "when_to_open": "总控在准备判断当前多窗口下一步动作前打开，尤其是存在 stuck 与 waiting 混合状态时。",
            "first_three_lines": [
                "top_priority_window",
                "top_frozen_window",
                "global_max_distortion",
            ],
            "decision_rule": [
                "先处理 `top_priority_window`，通常对应 `裁决`。",
                "若 `top_frozen_window` 存在，则不要越过它当前的等待边界。",
                "再按 windows 列表消费每个窗口的 `recommended_action / why / next_action`。",
                "只有具备 repo-local 可信证据时才允许把窗口视为可继续推进。",
            ],
        },
    }


def render_bundle_markdown(bundle: dict[str, Any]) -> str:
    summary = bundle.get("active_window_summary", {})
    lines = [
        "# Duty Officer Bundle",
        "",
        f"- run_id: `{bundle.get('run_id', '')}`",
        f"- created_at: `{bundle.get('created_at', '')}`",
        f"- window_count: `{summary.get('window_count', 0)}`",
        f"- recommended_action_counts: `{json.dumps(summary.get('recommended_action_counts', {}), ensure_ascii=False, sort_keys=True)}`",
        "",
        "## First Three Lines",
        "",
    ]
    top_priority = bundle.get("top_priority_window", {})
    top_frozen = bundle.get("top_frozen_window", {})
    distortion = bundle.get("global_max_distortion", {})
    lines.extend(
        [
            f"- top_priority_window: `{top_priority.get('window_id', '')}` -> `{top_priority.get('recommended_action', '')}`",
            f"  - why: {top_priority.get('why', '')}",
            f"  - next_action: {top_priority.get('next_action', '')}",
            f"- top_frozen_window: `{top_frozen.get('window_id', '')}` -> `{top_frozen.get('recommended_action', '')}`",
            f"  - why: {top_frozen.get('why', '')}",
            f"  - blocker: {top_frozen.get('sole_blocker', '')}",
            f"- global_max_distortion: `{distortion.get('window_id', '')}`",
            f"  - summary: {distortion.get('summary', '')}",
            f"  - why: {distortion.get('why', '')}",
            "",
            "## Windows",
            "",
        ]
    )
    for row in bundle.get("windows", []):
        lines.extend(
            [
                f"- `{row.get('window_id', '')}` | role=`{row.get('role', '')}` | action=`{row.get('recommended_action', '')}` | state=`{row.get('observed_state', '')}` | status=`{row.get('current_status', '')}` | trusted_evidence=`{row.get('trusted_evidence_count', 0)}`",
                f"  - why: {row.get('why', '')}",
                f"  - blocker: {row.get('sole_blocker', '')}",
                f"  - next_action: {row.get('next_action', '')}",
            ]
        )
    lines.extend(["", "## Source Artifacts", ""])
    for key, value in bundle.get("source_artifacts", {}).items():
        lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines) + "\n"


def support_quickstart(bundle: dict[str, Any]) -> str:
    top_priority = bundle.get("top_priority_window", {})
    top_frozen = bundle.get("top_frozen_window", {})
    distortion = bundle.get("global_max_distortion", {})
    return "\n".join(
        [
            "# Duty Officer Quickstart",
            "",
            "- 打开时机：总控在准备对多窗口做 `继续 / 等待 / 裁决 / 收口` 判断前打开。",
            "- 先看 3 行：",
            f"  - `top_priority_window`: {top_priority.get('window_id', '')} / {top_priority.get('recommended_action', '')}",
            f"  - `top_frozen_window`: {top_frozen.get('window_id', '')} / {top_frozen.get('recommended_action', '')}",
            f"  - `global_max_distortion`: {distortion.get('window_id', '')}",
            "- 决策方法：",
            "  - 先处理 `top_priority_window`。",
            "  - 对 `top_frozen_window` 保持冻结，不越过当前等待边界。",
            "  - 再按 windows 列表逐窗消费 `recommended_action / why / next_action`。",
            "  - 只有有 repo-local 可信证据时才放行 `继续`。",
        ]
    ) + "\n"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def verify_bundle(bundle: dict[str, Any], context: BundleContext, bundle_json_path: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    required_paths = [
        context.summary_json,
        context.governance_json,
        context.contract_json,
        context.protocol_md,
        bundle_json_path,
        context.output_dir / "duty-officer-manifest.json",
        context.output_dir / "support" / "quickstart.md",
    ]
    for path in required_paths:
        checks.append(
            {
                "name": f"exists:{path.name}",
                "ok": path.exists(),
                "detail": str(path.resolve()),
            }
        )
    for path in [context.summary_json, context.governance_json, context.contract_json, bundle_json_path]:
        try:
            json.loads(path.read_text(encoding="utf-8"))
            checks.append({"name": f"parse:{path.name}", "ok": True, "detail": "json_parse_ok"})
        except Exception as exc:  # pragma: no cover - defensive
            checks.append({"name": f"parse:{path.name}", "ok": False, "detail": f"json_parse_failed:{exc}"})
    summary = load_json(context.summary_json)
    govern = load_json(context.governance_json)
    summary_windows = {
        str(item.get("window_id") or ""): item
        for item in summary.get("windows", [])
        if isinstance(item, dict)
    }
    govern_windows = {
        str(item.get("window_id") or ""): item
        for item in govern.get("decisions", [])
        if isinstance(item, dict)
    }
    mismatches: list[str] = []
    for row in bundle.get("windows", []):
        window_id = str(row.get("window_id") or "")
        summary_item = summary_windows.get(window_id)
        govern_item = govern_windows.get(window_id)
        if not summary_item or not govern_item:
            mismatches.append(f"missing_source:{window_id}")
            continue
        if str(row.get("recommended_action") or "") != str(govern_item.get("decision") or ""):
            mismatches.append(f"decision_mismatch:{window_id}")
        if str(row.get("current_status") or "") != str(summary_item.get("current_status") or ""):
            mismatches.append(f"status_mismatch:{window_id}")
        if str(row.get("observed_state") or "") != str(govern_item.get("observed_state") or ""):
            mismatches.append(f"observed_state_mismatch:{window_id}")
    checks.append(
        {
            "name": "bundle_consistency",
            "ok": not mismatches,
            "detail": ", ".join(mismatches) or "bundle_matches_current_summary_and_govern",
        }
    )
    status = "completed" if all(item.get("ok") for item in checks) else "failed_partial"
    return {
        "run_id": context.run_id,
        "lane_id": "verify",
        "status": status,
        "checks": checks,
    }


def write_bundle(context: BundleContext) -> dict[str, Any]:
    ensure_dir(context.output_dir)
    ensure_dir(context.output_dir / "lanes" / "main")
    ensure_dir(context.output_dir / "lanes" / "support")
    ensure_dir(context.output_dir / "lanes" / "verify")
    ensure_dir(context.output_dir / "support")
    ensure_dir(context.output_dir / "verify")

    bundle = build_bundle(context)
    bundle_json_path = context.output_dir / "duty-officer-bundle.json"
    bundle_md_path = context.output_dir / "duty-officer-bundle.md"
    manifest_path = context.output_dir / "duty-officer-manifest.json"
    quickstart_path = context.output_dir / "support" / "quickstart.md"
    verify_report_path = context.output_dir / "verify" / "verification-report.json"

    write_json(bundle_json_path, bundle)
    bundle_md_path.write_text(render_bundle_markdown(bundle), encoding="utf-8")
    quickstart_path.write_text(support_quickstart(bundle), encoding="utf-8")

    manifest = {
        "schema_version": "window-duty-officer-manifest-v1",
        "run_id": context.run_id,
        "created_at": context.created_at,
        "duty_role": "Black-Satellite PMO Beta Duty Officer v1",
        "replay_command": (
            f"python3 {SCRIPT_PATH} --run-id {context.run_id} "
            f"--output-dir {context.output_dir}"
        ),
        "source_artifacts": source_artifacts(context),
        "bundle_files": [
            str(bundle_json_path.resolve()),
            str(bundle_md_path.resolve()),
            str(quickstart_path.resolve()),
            str(verify_report_path.resolve()),
        ],
    }
    write_json(manifest_path, manifest)

    main_manifest = lane_contract(
        "main",
        scoped_goal="产出正式 duty-officer bundle",
        current_phase="duty_bundle_authored",
        latest_evidence_paths=[
            str(bundle_json_path.resolve()),
            str(bundle_md_path.resolve()),
            str(manifest_path.resolve()),
        ],
        sole_blocker="",
        next_request_to_mainline="先看 duty-officer bundle 的 top_priority_window、top_frozen_window、global_max_distortion。",
    )
    main_result = {
        "lane_id": "main",
        "status": "completed",
        "did_what": "产出正式 duty-officer bundle 与 manifest。",
        "evidence_ref": [
            "duty-officer-bundle.json",
            "duty-officer-bundle.md",
            "duty-officer-manifest.json",
        ],
        "sole_blocker": "",
        "next_request_to_mainline": main_manifest["next_request_to_mainline"],
    }
    write_json(context.output_dir / "lanes" / "main" / "lane-manifest.json", main_manifest)
    write_json(context.output_dir / "lanes" / "main" / "lane-result.json", main_result)
    (context.output_dir / "lanes" / "main" / "lane-summary.md").write_text(
        "# main lane\n\n"
        "- status: `completed`\n"
        "- did_what: 产出正式 duty-officer bundle 与 manifest。\n"
        f"- next_request_to_mainline: {main_manifest['next_request_to_mainline']}\n",
        encoding="utf-8",
    )

    support_manifest = lane_contract(
        "support",
        scoped_goal="压缩成总控可直接消费的 3 行 quickstart",
        current_phase="quickstart_authored",
        latest_evidence_paths=[str(quickstart_path.resolve())],
        sole_blocker="",
        next_request_to_mainline="总控下一轮先看 top_priority_window、top_frozen_window、global_max_distortion 这 3 行。",
    )
    support_result = {
        "lane_id": "support",
        "status": "completed",
        "did_what": "产出最短 quickstart，压缩总控消费路径。",
        "evidence_ref": ["support/quickstart.md", "duty-officer-bundle.md"],
        "sole_blocker": "",
        "next_request_to_mainline": support_manifest["next_request_to_mainline"],
    }
    write_json(context.output_dir / "lanes" / "support" / "lane-manifest.json", support_manifest)
    write_json(context.output_dir / "lanes" / "support" / "lane-result.json", support_result)
    (context.output_dir / "lanes" / "support" / "lane-summary.md").write_text(
        "# support lane\n\n"
        "- status: `completed`\n"
        "- did_what: 产出最短 quickstart，压缩总控消费路径。\n"
        f"- next_request_to_mainline: {support_manifest['next_request_to_mainline']}\n",
        encoding="utf-8",
    )

    verification_report = verify_bundle(bundle, context, bundle_json_path)
    write_json(verify_report_path, verification_report)
    verify_manifest = lane_contract(
        "verify",
        scoped_goal="验证 bundle 路径、JSON 与关键判断一致性",
        current_phase="verification_completed" if verification_report["status"] == "completed" else "verification_failed_partial",
        latest_evidence_paths=[
            str(verify_report_path.resolve()),
            str(context.summary_json.resolve()),
            str(context.governance_json.resolve()),
        ],
        sole_blocker="" if verification_report["status"] == "completed" else "bundle_consistency_check_failed",
        next_request_to_mainline="verify 已确认关键判断与当前 summary/govern 一致。",
    )
    verify_result = {
        "lane_id": "verify",
        "status": verification_report["status"],
        "did_what": "独立验证 bundle 所引用路径存在、JSON 可解析、关键判断与当前 summary/govern 一致。",
        "evidence_ref": ["verify/verification-report.json", "duty-officer-bundle.json"],
        "sole_blocker": verify_manifest["sole_blocker"],
        "next_request_to_mainline": verify_manifest["next_request_to_mainline"],
    }
    write_json(context.output_dir / "lanes" / "verify" / "lane-manifest.json", verify_manifest)
    write_json(context.output_dir / "lanes" / "verify" / "lane-result.json", verify_result)
    (context.output_dir / "lanes" / "verify" / "lane-summary.md").write_text(
        "# verify lane\n\n"
        f"- status: `{verify_result['status']}`\n"
        "- did_what: 独立验证 bundle 所引用路径存在、JSON 可解析、关键判断与当前 summary/govern 一致。\n"
        f"- next_request_to_mainline: {verify_manifest['next_request_to_mainline']}\n",
        encoding="utf-8",
    )
    return {
        "bundle": bundle,
        "manifest": manifest,
        "verification_report": verification_report,
        "bundle_json_path": bundle_json_path,
        "bundle_md_path": bundle_md_path,
        "manifest_path": manifest_path,
        "quickstart_path": quickstart_path,
        "verify_report_path": verify_report_path,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate the repo-local window duty officer bundle.")
    parser.add_argument("--run-id", default="adagj-black-satellite-pmo-duty-officer-v1", help="Stable run id.")
    parser.add_argument("--created-at", default="", help="Optional ISO datetime override.")
    parser.add_argument("--summary-json", default=str(DEFAULT_SUMMARY_JSON), help="Window heartbeat summary json.")
    parser.add_argument("--governance-json", default=str(DEFAULT_GOVERNANCE_JSON), help="Window heartbeat governance summary json.")
    parser.add_argument("--contract-json", default=str(DEFAULT_CONTRACT_JSON), help="PMO Beta contract json.")
    parser.add_argument("--protocol-md", default=str(DEFAULT_PROTOCOL_MD), help="PMO Beta protocol markdown.")
    parser.add_argument("--trial-run-dir", default=str(DEFAULT_TRIAL_RUN_DIR), help="Optional prior trial run dir.")
    parser.add_argument("--output-dir", default="", help="Optional output dir override.")
    return parser


def resolve_context(args: argparse.Namespace) -> BundleContext:
    created_at = str(args.created_at or iso_now())
    created_dt = datetime.fromisoformat(created_at)
    output_dir = (
        Path(str(args.output_dir)).expanduser().resolve()
        if str(args.output_dir or "").strip()
        else RUNS_ROOT / created_dt.strftime("%Y-%m-%d") / str(args.run_id)
    )
    trial_run_dir = Path(str(args.trial_run_dir)).expanduser().resolve() if str(args.trial_run_dir or "").strip() else None
    return BundleContext(
        run_id=str(args.run_id),
        created_at=created_at,
        output_dir=output_dir,
        summary_json=Path(str(args.summary_json)).expanduser().resolve(),
        governance_json=Path(str(args.governance_json)).expanduser().resolve(),
        contract_json=Path(str(args.contract_json)).expanduser().resolve(),
        protocol_md=Path(str(args.protocol_md)).expanduser().resolve(),
        trial_run_dir=trial_run_dir,
    )


def main() -> int:
    args = build_parser().parse_args()
    context = resolve_context(args)
    result = write_bundle(context)
    print(
        json.dumps(
            {
                "run_id": context.run_id,
                "output_dir": str(context.output_dir.resolve()),
                "bundle_json": str(result["bundle_json_path"].resolve()),
                "bundle_md": str(result["bundle_md_path"].resolve()),
                "verification_status": result["verification_report"]["status"],
                "top_priority_window": result["bundle"].get("top_priority_window", {}),
                "top_frozen_window": result["bundle"].get("top_frozen_window", {}),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["verification_report"]["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
