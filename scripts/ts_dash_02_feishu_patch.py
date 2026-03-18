from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.runtime_control import RuntimeControlPlane
from scripts.dashboard_close_task_hooks import count_actions, now_ms, upsert_rows
from scripts.sync_governance_dashboard_base import api, list_fields, list_records
from scripts.sync_r11_v2_skill_inventory_feishu import bootstrap_client


PVDG_BASE = "PVDgbdWYFaDLBiss0hlcM5WRnQc"
LIVE_RUNTIME_BASE = "PHp2wURl2i6SyBkDtmGcuaEenag"
AUDIT_TABLE_ID = "tblYnhPN5JyMNwrU"
VECTOR_TABLE_ID = "tblx8lmiEkUzAnON"
COLLAB_TABLE_ID = "tbl67a3vUXDaIjRF"

DEFAULT_RUN_DIR = (
    REPO_ROOT
    / "work/ai-da-guan-jia/artifacts/ai-da-guan-jia/runs/2026-03-17/adagj-20260317-205850-000000"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply TS-DASH-02 Feishu data patch.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--run-dir", default=str(DEFAULT_RUN_DIR))
    return parser.parse_args(argv)


def field_names(client: Any, app_token: str, table_id: str) -> set[str]:
    return {str(item.get("field_name") or item.get("name") or "").strip() for item in list_fields(client, app_token, table_id)}


def maybe_int(value: Any) -> Any:
    text = str(value).strip()
    if not text:
        return value
    if text.isdigit():
        return int(text)
    return value


def collab_signature(fields: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(fields.get("from_role") or "").strip(),
        str(fields.get("to_role") or "").strip(),
        str(fields.get("interaction_type") or "").strip(),
        str(fields.get("summary") or "").strip(),
        str(fields.get("round_ref") or "").strip(),
    )


def reconcile_collab_rows(client: Any, desired_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    existing = list_records(client, PVDG_BASE, COLLAB_TABLE_ID)
    canonical_by_signature: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    duplicate_record_ids: list[str] = []
    wanted_signatures = {collab_signature(row) for row in desired_rows}
    for row in existing:
        fields = row.get("fields") or {}
        signature = collab_signature(fields)
        if signature not in wanted_signatures:
            continue
        if signature not in canonical_by_signature:
            canonical_by_signature[signature] = row
            continue
        record_id = str(row.get("record_id") or row.get("id") or "").strip()
        if record_id:
            duplicate_record_ids.append(record_id)

    reconciled: list[dict[str, Any]] = []
    for row in desired_rows:
        updated = dict(row)
        canonical = canonical_by_signature.get(collab_signature(updated))
        if canonical:
            current_id = str((canonical.get("fields") or {}).get("interaction_id") or "").strip()
            if current_id:
                updated["interaction_id"] = current_id
        reconciled.append(updated)
    return reconciled, duplicate_record_ids


def delete_records(client: Any, app_token: str, table_id: str, record_ids: list[str]) -> int:
    deleted = 0
    for record_id in record_ids:
        api(client, "DELETE", f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}")
        deleted += 1
    return deleted


def build_spec() -> dict[str, Any]:
    completion_time = now_ms()
    earlier_1 = completion_time - int(timedelta(hours=6).total_seconds() * 1000)
    earlier_2 = completion_time - int(timedelta(hours=5, minutes=10).total_seconds() * 1000)
    earlier_3 = completion_time - int(timedelta(hours=4, minutes=45).total_seconds() * 1000)
    earlier_4 = completion_time - int(timedelta(hours=1, minutes=30).total_seconds() * 1000)
    earlier_5 = completion_time - int(timedelta(minutes=20).total_seconds() * 1000)

    scoring = {
        "d8_score": 1,
        "d9_score": 1,
        "d10_score": 2,
        "total_score": 21,
        "total_score_40": 21,
        "dimension_group": "系统基础/治理结构/扩展就绪/三方协同",
        "rationale": {
            "d8": "根据当前体系，Codex 可执行验真闭环但无并行调度，因此 D8 评为 1/4。",
            "d9": "Claude↔Codex 已有 Task Spec 合同但无自动分发，因此 D9 评为 1/4。",
            "d10": "人类仍是全链路瓶颈，单人承担全部 owner，但已有稳定审批与交接，所以 D10 评为 2/4。",
        },
    }

    vector_rows = [
        {
            "task_id": "TS-GH-01",
            "status": "已完成",
            "completion_date": completion_time,
            "handoff_summary": "5仓盘点完成，309 未提交文件已分类。",
            "blockers": "",
        },
        {
            "task_id": "TS-V2-01",
            "status": "已完成",
            "completion_date": completion_time,
            "handoff_summary": "INIT V16-lite 四层分离版已落地。",
            "blockers": "",
        },
        {
            "task_id": "TS-V1-01",
            "status": "阻塞",
            "blockers": "卫星机系统blocked（与 INIT 对齐）",
            "handoff_summary": "",
        },
        {
            "task_id": "TS-DASH-01",
            "task_name": "飞书多维表改造",
            "vector": "V2",
            "phase": "P1",
            "week": 2,
            "executor": "大管家",
            "status": "已完成",
            "completion_date": completion_time,
            "handoff_summary": "飞书表改造完成，PHp2 + PVDg 双 Base。",
            "blockers": "",
        },
    ]

    collab_rows = [
        {
            "interaction_id": f"triparty-{earlier_1}",
            "timestamp": earlier_1,
            "from_role": "Claude",
            "to_role": "Human",
            "interaction_type": "task_spec",
            "summary": "驾驶舱2.0规划文档输出",
            "quality_score": 4,
            "round_ref": "R18-DASH-01",
        },
        {
            "interaction_id": f"triparty-{earlier_2}",
            "timestamp": earlier_2,
            "from_role": "Human",
            "to_role": "Codex",
            "interaction_type": "approval",
            "summary": "批准飞书表改造执行",
            "quality_score": 5,
            "round_ref": "R18-DASH-01",
        },
        {
            "interaction_id": f"triparty-{earlier_3}",
            "timestamp": earlier_3,
            "from_role": "Codex",
            "to_role": "Human",
            "interaction_type": "evidence",
            "summary": "PHp2+PVDg双Base改造完成",
            "quality_score": 4,
            "round_ref": "R18-DASH-01",
        },
        {
            "interaction_id": f"triparty-{earlier_4}",
            "timestamp": earlier_4,
            "from_role": "Human",
            "to_role": "Claude",
            "interaction_type": "feedback",
            "summary": "驾驶舱2.0代码重写启动",
            "quality_score": 5,
            "round_ref": "R18-DASH-02",
        },
        {
            "interaction_id": f"triparty-{earlier_5}",
            "timestamp": earlier_5,
            "from_role": "Claude",
            "to_role": "Codex",
            "interaction_type": "task_spec",
            "summary": "TS-DASH-02数据补齐任务分发",
            "quality_score": 4,
            "round_ref": "R18-DASH-02",
        },
    ]
    return {
        "scoring": scoring,
        "vector_rows": vector_rows,
        "collab_rows": collab_rows,
        "runtime_control": {
            "active_round": "R18",
            "frontstage_focus": "R18 三向量扩展 + 驾驶舱 2.0",
        },
    }


def verify(client: Any) -> dict[str, Any]:
    audit_rows = list_records(client, PVDG_BASE, AUDIT_TABLE_ID)
    vector_rows = list_records(client, PVDG_BASE, VECTOR_TABLE_ID)
    collab_rows = list_records(client, PVDG_BASE, COLLAB_TABLE_ID)
    audit = audit_rows[0]["fields"] if audit_rows else {}
    vector_by_id = {str((row.get("fields") or {}).get("task_id") or ""): row.get("fields", {}) for row in vector_rows}
    collab_ids = sorted(str((row.get("fields") or {}).get("interaction_id") or "") for row in collab_rows)
    return {
        "audit_scores": {
            "d8_score": audit.get("d8_score"),
            "d9_score": audit.get("d9_score"),
            "d10_score": audit.get("d10_score"),
            "total_score": audit.get("total_score"),
            "total_score_40": audit.get("total_score_40"),
            "dimension_group": audit.get("dimension_group"),
        },
        "vector_status": {
            "TS-GH-01": vector_by_id.get("TS-GH-01", {}),
            "TS-V2-01": vector_by_id.get("TS-V2-01", {}),
            "TS-V1-01": vector_by_id.get("TS-V1-01", {}),
            "TS-DASH-01": vector_by_id.get("TS-DASH-01", {}),
        },
        "collab_seed_count": len(collab_rows),
        "collab_seed_ids": [value for value in collab_ids if value.startswith("triparty-")],
        "missing_fields": {
            "audit": sorted({"d8_score", "d9_score", "d10_score", "total_score", "total_score_40", "dimension_group"} - field_names(client, PVDG_BASE, AUDIT_TABLE_ID)),
            "vector": sorted({"completion_date", "handoff_summary", "blockers"} - field_names(client, PVDG_BASE, VECTOR_TABLE_ID)),
            "collab": sorted({"from_role", "to_role", "interaction_type", "summary", "round_ref"} - field_names(client, PVDG_BASE, COLLAB_TABLE_ID)),
        },
    }


def markdown_report(result: dict[str, Any]) -> str:
    lines = [
        "# TS-DASH-02 Data Patch Report",
        "",
        f"- Mode: `{result['mode']}`",
        f"- Timestamp: `{result['timestamp']}`",
        "",
        "## Score Update",
        "",
        f"- D8: `{result['scoring']['d8_score']}`",
        f"- D9: `{result['scoring']['d9_score']}`",
        f"- D10: `{result['scoring']['d10_score']}`",
        f"- Total Score: `{result['scoring']['total_score']}/40`",
        "",
        "## Score Rationale",
        "",
        f"- D8: {result['scoring_rationale']['d8']}",
        f"- D9: {result['scoring_rationale']['d9']}",
        f"- D10: {result['scoring_rationale']['d10']}",
        "",
        "## Vector Patch",
        "",
        f"- Actions: `{json.dumps(result['vector_action_summary'], ensure_ascii=False)}`",
        "",
        "## Collaboration Seed",
        "",
        f"- Actions: `{json.dumps(result['collab_action_summary'], ensure_ascii=False)}`",
        "",
    ]
    if "verification" in result:
        lines.extend(["## Verification", "", f"- Payload: `{json.dumps(result['verification'], ensure_ascii=False)}`", ""])
    return "\n".join(lines).strip() + "\n"


def run_patch(*, apply_changes: bool, run_dir: Path) -> dict[str, Any]:
    client = bootstrap_client()

    spec = build_spec()
    result: dict[str, Any] = {
        "mode": "apply" if apply_changes else "dry-run",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
        "scoring": {
            "d8_score": spec["scoring"]["d8_score"],
            "d9_score": spec["scoring"]["d9_score"],
            "d10_score": spec["scoring"]["d10_score"],
            "total_score": spec["scoring"]["total_score"],
            "total_score_40": spec["scoring"]["total_score_40"],
        },
        "scoring_rationale": spec["scoring"]["rationale"],
    }

    audit_rows = [
        {
            "audit_id": "GOV-AUDIT-20260317",
            "d8_score": spec["scoring"]["d8_score"],
            "d9_score": spec["scoring"]["d9_score"],
            "d10_score": spec["scoring"]["d10_score"],
            "total_score": spec["scoring"]["total_score"],
            "total_score_40": spec["scoring"]["total_score_40"],
            "dimension_group": spec["scoring"]["dimension_group"],
        }
    ]
    audit_actions = upsert_rows(client, PVDG_BASE, AUDIT_TABLE_ID, "audit_id", audit_rows, dry_run=not apply_changes)
    vector_actions = upsert_rows(
        client,
        PVDG_BASE,
        VECTOR_TABLE_ID,
        "task_id",
        spec["vector_rows"],
        dry_run=not apply_changes,
        preserve_empty_fields={"handoff_summary", "blockers"},
    )
    collab_rows, duplicate_collab_record_ids = reconcile_collab_rows(client, spec["collab_rows"])
    collab_actions = upsert_rows(client, PVDG_BASE, COLLAB_TABLE_ID, "interaction_id", collab_rows, dry_run=not apply_changes)
    live_runtime = RuntimeControlPlane(client=client, app_token=LIVE_RUNTIME_BASE, table_name="L0_运行态总控")
    governance_runtime = RuntimeControlPlane(client=client, app_token=PVDG_BASE, table_name="L0_运行态总控")
    live_current = live_runtime.get_current() or {}
    governance_current = governance_runtime.get_current() or {}
    runtime_fields_live = {
        "active_round": spec["runtime_control"]["active_round"],
        "frontstage_focus": spec["runtime_control"]["frontstage_focus"],
        "total_tests_passed": maybe_int(live_current.get("total_tests_passed")),
        "total_commits": maybe_int(live_current.get("total_commits")),
    }
    runtime_fields_governance = {
        "active_round": spec["runtime_control"]["active_round"],
        "frontstage_focus": spec["runtime_control"]["frontstage_focus"],
        "total_tests_passed": maybe_int(governance_current.get("total_tests_passed", live_current.get("total_tests_passed"))),
        "total_commits": maybe_int(governance_current.get("total_commits", live_current.get("total_commits"))),
    }
    runtime_live_action = live_runtime.upsert(runtime_fields_live, dry_run=not apply_changes)
    runtime_governance_action = governance_runtime.upsert(runtime_fields_governance, dry_run=not apply_changes)
    result["audit_action_summary"] = count_actions(audit_actions)
    result["vector_action_summary"] = count_actions(vector_actions)
    result["collab_action_summary"] = count_actions(collab_actions)
    result["runtime_control"] = {
        "live_base": runtime_live_action,
        "governance_base": runtime_governance_action,
    }
    result["collab_duplicate_cleanup_candidates"] = len(duplicate_collab_record_ids)

    if apply_changes:
        result["collab_duplicate_cleanup_deleted"] = delete_records(client, PVDG_BASE, COLLAB_TABLE_ID, duplicate_collab_record_ids)
        result["verification"] = verify(client)
        result["verification"]["runtime_control"] = {
            "live_base": live_runtime.get_current(),
            "governance_base": governance_runtime.get_current(),
        }

    run_dir.mkdir(parents=True, exist_ok=True)
    raw_json = run_dir / f"ts-dash-02-feishu-patch-{result['mode']}.json"
    handoff_json = run_dir / "handoff.json"
    report_md = run_dir / "feishu-data-patch-report.md"
    rationale_md = run_dir / "ts-dash-02-scoring-rationale.md"
    raw_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    handoff_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_md.write_text(markdown_report(result), encoding="utf-8")
    rationale_md.write_text(
        "\n".join(
            [
                "# TS-DASH-02 Scoring Rationale",
                "",
                f"- D8: {spec['scoring']['rationale']['d8']}",
                f"- D9: {spec['scoring']['rationale']['d9']}",
                f"- D10: {spec['scoring']['rationale']['d10']}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    result["artifacts"] = {
        "raw_json": str(raw_json),
        "handoff_json": str(handoff_json),
        "report_md": str(report_md),
        "rationale_md": str(rationale_md),
    }
    return result


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_patch(apply_changes=bool(args.apply), run_dir=Path(args.run_dir))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
