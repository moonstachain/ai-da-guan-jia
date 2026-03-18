from __future__ import annotations

from scripts.dashboard_close_task_hooks import (
    build_collab_row,
    build_vector_row,
    extract_task_id,
    normalize_vector_status,
)
from scripts.ts_dash_02_feishu_patch import build_spec


def test_ts_dash_02_build_spec_matches_task_doc() -> None:
    spec = build_spec()

    assert spec["scoring"]["d8_score"] == 1
    assert spec["scoring"]["d9_score"] == 1
    assert spec["scoring"]["d10_score"] == 2
    assert spec["scoring"]["total_score"] == 21
    assert spec["scoring"]["total_score_40"] == 21
    assert spec["runtime_control"]["active_round"] == "R18"
    assert spec["runtime_control"]["frontstage_focus"] == "R18 三向量扩展 + 驾驶舱 2.0"

    vector_rows = {row["task_id"]: row for row in spec["vector_rows"]}
    assert vector_rows["TS-GH-01"]["status"] == "已完成"
    assert vector_rows["TS-V2-01"]["status"] == "已完成"
    assert vector_rows["TS-V1-01"]["status"] == "阻塞"
    assert vector_rows["TS-DASH-01"]["status"] == "已完成"

    collab_rows = spec["collab_rows"]
    assert len(collab_rows) == 5
    assert collab_rows[0]["from_role"] == "Claude"
    assert collab_rows[0]["to_role"] == "Human"
    assert collab_rows[0]["interaction_id"].startswith("triparty-")
    assert collab_rows[-1]["summary"] == "TS-DASH-02数据补齐任务分发"


def test_dashboard_hook_helpers_build_expected_rows() -> None:
    evolution = {
        "run_id": "adagj-20260317-210449-000000",
        "task_text": "执行 TS-DASH-02 并完成闭环",
        "verification_result": {
            "status": "completed",
            "open_questions": [],
        },
    }
    worklog = {
        "completion_summary": "completed; evidence: 飞书数据补齐与 hook 落地。",
        "verification_evidence_summary": "飞书数据补齐与 hook 落地。",
    }

    assert extract_task_id(evolution["task_text"]) == "TS-DASH-02"
    assert normalize_vector_status("completed") == "已完成"
    assert normalize_vector_status("blocked") == "阻塞"
    assert normalize_vector_status("failed") == "失败"

    collab_row = build_collab_row(evolution, worklog, "TS-DASH-02")
    assert collab_row["interaction_id"] == "triparty-close-adagj-20260317-210449-000000"
    assert collab_row["from_role"] == "Codex"
    assert collab_row["to_role"] == "Human"
    assert collab_row["round_ref"] == "TS-DASH-02"

    vector_row = build_vector_row(evolution, worklog, "TS-DASH-02")
    assert vector_row["task_id"] == "TS-DASH-02"
    assert vector_row["status"] == "已完成"
    assert "completion_date" in vector_row
    assert vector_row["blockers"] == ""
