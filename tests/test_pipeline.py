from __future__ import annotations

import json
from pathlib import Path

import pytest

from ontology.pipeline import EvidencePipeline, TaskRun, close_task
from ontology.types import (
    Action,
    ComponentDomain,
    Confidence,
    ControlLevel,
    DecisionRecord,
    Entity,
    EntityType,
    EvidenceAtom,
    OwnerMode,
    SourceType,
    WritebackEvent,
    WritebackResult,
)


def _build_complete_run() -> TaskRun:
    entity = Entity(
        entity_id="task-r5",
        entity_type=EntityType.TASK,
        status="active",
        component_domain=ComponentDomain.GOVERNANCE,
        control_level=ControlLevel.CONTROL,
        owner_mode=OwnerMode.AI,
    )
    actions = [
        Action("act-1", "create_module", "task-r5", False),
        Action("act-2", "write_tests", "task-r5", False),
    ]
    evidence = [
        EvidenceAtom("ev-1", SourceType.SYSTEM_OUTPUT, "16 passed", Confidence.CONFIRMED),
        EvidenceAtom("ev-2", SourceType.EXPLICIT_STATEMENT, "need one more round", Confidence.PROVISIONAL),
    ]
    writebacks = [
        WritebackEvent("wb-1", "task-r5", "act-1", "2026-03-16T12:00:00Z", WritebackResult.SUCCESS, "ev-1"),
        WritebackEvent("wb-2", "task-r5", "act-2", "2026-03-16T12:10:00Z", WritebackResult.PARTIAL, "ev-2"),
    ]
    decisions = [
        DecisionRecord(
            decision_id="dec-1",
            decision_type="route_selection",
            rationale="选择了最小充分路径",
            evidence_refs=["ev-1"],
        )
    ]
    return TaskRun(
        run_id="run-r5-001",
        round_id="R5",
        objective="实现 evidence pipeline",
        component_domain=ComponentDomain.GOVERNANCE,
        control_level=ControlLevel.CONTROL,
        target_entity=entity,
        actions_taken=actions,
        evidence_collected=evidence,
        writebacks=writebacks,
        decisions=decisions,
        routing_rationale="选择了最小充分路径",
    )


def _build_empty_run() -> TaskRun:
    entity = Entity(
        entity_id="task-r5-empty",
        entity_type=EntityType.TASK,
        status="draft",
        component_domain=ComponentDomain.GOVERNANCE,
        control_level=ControlLevel.CONTROL,
        owner_mode=OwnerMode.AI,
    )
    return TaskRun(
        run_id="run-empty",
        round_id="R5",
        objective="empty run",
        component_domain=ComponentDomain.GOVERNANCE,
        control_level=ControlLevel.CONTROL,
        target_entity=entity,
    )


def test_taskrun_can_be_created() -> None:
    run = _build_complete_run()
    assert run.run_id == "run-r5-001"
    assert run.target_entity.entity_id == "task-r5"


def test_taskrun_defaults_are_empty_lists() -> None:
    run = _build_empty_run()
    assert run.actions_taken == []
    assert run.evidence_collected == []
    assert run.writebacks == []
    assert run.decisions == []
    assert run.human_boundary_log == []


def test_collect_evidence_returns_expected_evidence_count(tmp_path: Path) -> None:
    summary = EvidencePipeline(str(tmp_path)).collect_evidence(_build_complete_run())
    assert summary["evidence_count"] == 2


def test_collect_evidence_returns_expected_confidence_distribution(tmp_path: Path) -> None:
    summary = EvidencePipeline(str(tmp_path)).collect_evidence(_build_complete_run())
    assert summary["confidence_distribution"] == {"confirmed": 1, "provisional": 1}


def test_collect_evidence_returns_expected_writeback_results(tmp_path: Path) -> None:
    summary = EvidencePipeline(str(tmp_path)).collect_evidence(_build_complete_run())
    assert summary["writeback_results"] == {"success": 1, "partial": 1}


def test_collect_evidence_empty_run_returns_zero_counts(tmp_path: Path) -> None:
    summary = EvidencePipeline(str(tmp_path)).collect_evidence(_build_empty_run())
    assert summary["evidence_count"] == 0
    assert summary["writeback_count"] == 0


def test_collect_evidence_includes_decision_and_action_counts(tmp_path: Path) -> None:
    summary = EvidencePipeline(str(tmp_path)).collect_evidence(_build_complete_run())
    assert summary["decision_count"] == 1
    assert summary["actions_count"] == 2


def test_collect_evidence_preserves_human_boundary_events(tmp_path: Path) -> None:
    run = _build_complete_run()
    run.human_boundary_log.append("waiting for approval")
    summary = EvidencePipeline(str(tmp_path)).collect_evidence(run)
    assert summary["human_boundary_events"] == ["waiting for approval"]


def test_check_closure_complete_run_marks_routed_and_verified(tmp_path: Path) -> None:
    closure = EvidencePipeline(str(tmp_path)).check_closure(_build_complete_run())
    assert closure["path_routed"] is True
    assert closure["result_verified"] is True


def test_check_closure_without_routing_rationale_returns_path_routed_false(tmp_path: Path) -> None:
    run = _build_complete_run()
    run.routing_rationale = ""
    closure = EvidencePipeline(str(tmp_path)).check_closure(run)
    assert closure["path_routed"] is False


def test_check_closure_without_confirmed_evidence_returns_result_verified_false(tmp_path: Path) -> None:
    run = _build_complete_run()
    run.evidence_collected = [EvidenceAtom("ev-x", SourceType.SYSTEM_OUTPUT, "pending", Confidence.PROVISIONAL)]
    closure = EvidencePipeline(str(tmp_path)).check_closure(run)
    assert closure["result_verified"] is False


def test_check_closure_missing_lists_unsatisfied_conditions(tmp_path: Path) -> None:
    closure = EvidencePipeline(str(tmp_path)).check_closure(_build_empty_run())
    assert "path_routed" in closure["missing"]
    assert "result_verified" in closure["missing"]
    assert "next_captured" in closure["missing"]


def test_validate_chains_complete_chain_returns_empty_errors(tmp_path: Path) -> None:
    assert EvidencePipeline(str(tmp_path)).validate_chains(_build_complete_run()) == []


def test_validate_chains_action_id_mismatch_returns_error(tmp_path: Path) -> None:
    run = _build_complete_run()
    run.writebacks[0].action_id = "act-missing"
    errors = EvidencePipeline(str(tmp_path)).validate_chains(run)
    assert any("missing action" in error for error in errors)


def test_validate_chains_failed_writeback_returns_error(tmp_path: Path) -> None:
    run = _build_complete_run()
    run.writebacks[0].result = WritebackResult.FAILED
    errors = EvidencePipeline(str(tmp_path)).validate_chains(run)
    assert "writeback.result must not be FAILED" in errors


def test_generate_evolution_log_contains_required_fields(tmp_path: Path) -> None:
    log = EvidencePipeline(str(tmp_path)).generate_evolution_log(
        _build_complete_run(),
        gained=["evidence pipeline 自动化"],
        wasted=[],
        next_iterate=["R6 做人类仪表盘"],
        capability_delta="闭环力",
    )
    for key in ("round_id", "timestamp", "status", "context", "closure_check", "gained", "wasted", "next_iterate"):
        assert key in log


def test_generate_evolution_log_complete_run_returns_completed(tmp_path: Path) -> None:
    log = EvidencePipeline(str(tmp_path)).generate_evolution_log(
        _build_complete_run(),
        gained=["evidence pipeline 自动化"],
        wasted=[],
        next_iterate=["R6 做人类仪表盘"],
        capability_delta="闭环力",
    )
    assert log["status"] == "completed"


def test_generate_evolution_log_chain_errors_return_failed_partial(tmp_path: Path) -> None:
    run = _build_complete_run()
    run.writebacks[0].result = WritebackResult.FAILED
    log = EvidencePipeline(str(tmp_path)).generate_evolution_log(
        run,
        gained=["evidence pipeline 自动化"],
        wasted=[],
        next_iterate=["R6 做人类仪表盘"],
        capability_delta="闭环力",
    )
    assert log["status"] == "failed_partial"


def test_generate_evolution_log_human_boundary_returns_blocked_needs_user(tmp_path: Path) -> None:
    run = _build_complete_run()
    run.human_boundary_log.append("need human approval")
    log = EvidencePipeline(str(tmp_path)).generate_evolution_log(
        run,
        gained=["evidence pipeline 自动化"],
        wasted=[],
        next_iterate=["R6 做人类仪表盘"],
        capability_delta="闭环力",
    )
    assert log["status"] == "blocked_needs_user"


def test_generate_evolution_log_missing_confirmed_evidence_returns_blocked_system(tmp_path: Path) -> None:
    run = _build_complete_run()
    run.evidence_collected = [EvidenceAtom("ev-x", SourceType.SYSTEM_OUTPUT, "pending", Confidence.PROVISIONAL)]
    run.writebacks[0].evidence_ref = "ev-x"
    run.writebacks[1].evidence_ref = "ev-x"
    log = EvidencePipeline(str(tmp_path)).generate_evolution_log(
        run,
        gained=["evidence pipeline 自动化"],
        wasted=[],
        next_iterate=["R6 做人类仪表盘"],
        capability_delta="闭环力",
    )
    assert log["status"] == "blocked_system"


def test_generate_evolution_log_preserves_gained_list(tmp_path: Path) -> None:
    gained = ["evidence pipeline 自动化"]
    log = EvidencePipeline(str(tmp_path)).generate_evolution_log(
        _build_complete_run(), gained=gained, wasted=[], next_iterate=["R6 做人类仪表盘"], capability_delta="闭环力"
    )
    assert log["gained"] == gained


def test_generate_evolution_log_preserves_capability_delta(tmp_path: Path) -> None:
    log = EvidencePipeline(str(tmp_path)).generate_evolution_log(
        _build_complete_run(),
        gained=["evidence pipeline 自动化"],
        wasted=[],
        next_iterate=["R6 做人类仪表盘"],
        capability_delta="闭环力",
    )
    assert log["capability_delta"] == "闭环力"


def test_save_evolution_log_writes_file_to_expected_path(tmp_path: Path) -> None:
    pipeline = EvidencePipeline(str(tmp_path))
    log = pipeline.generate_evolution_log(
        _build_complete_run(),
        gained=["evidence pipeline 自动化"],
        wasted=[],
        next_iterate=["R6 做人类仪表盘"],
        capability_delta="闭环力",
    )
    saved_path = pipeline.save_evolution_log(log)
    assert saved_path.endswith("artifacts" if False else "R5-run-r5-001.json")


def test_save_evolution_log_written_json_is_parseable(tmp_path: Path) -> None:
    pipeline = EvidencePipeline(str(tmp_path))
    log = pipeline.generate_evolution_log(
        _build_complete_run(),
        gained=["evidence pipeline 自动化"],
        wasted=[],
        next_iterate=["R6 做人类仪表盘"],
        capability_delta="闭环力",
    )
    saved_path = pipeline.save_evolution_log(log)
    payload = json.loads(Path(saved_path).read_text(encoding="utf-8"))
    assert payload["round_id"] == "R5"


def test_save_evolution_log_creates_intermediate_directories(tmp_path: Path) -> None:
    pipeline = EvidencePipeline(str(tmp_path / "nested-artifacts"))
    log = pipeline.generate_evolution_log(
        _build_complete_run(),
        gained=["evidence pipeline 自动化"],
        wasted=[],
        next_iterate=["R6 做人类仪表盘"],
        capability_delta="闭环力",
    )
    saved_path = pipeline.save_evolution_log(log)
    assert Path(saved_path).parent.exists()


def test_run_full_pipeline_returns_complete_result_shape(tmp_path: Path) -> None:
    result = EvidencePipeline(str(tmp_path)).run_full_pipeline(
        _build_complete_run(),
        gained=["evidence pipeline 自动化"],
        wasted=[],
        next_iterate=["R6 做人类仪表盘"],
        capability_delta="闭环力",
    )
    assert set(result) == {"evolution_log", "saved_path", "closure_status", "chain_errors", "evidence_summary"}


def test_run_full_pipeline_saved_path_exists(tmp_path: Path) -> None:
    result = EvidencePipeline(str(tmp_path)).run_full_pipeline(
        _build_complete_run(),
        gained=["evidence pipeline 自动化"],
        wasted=[],
        next_iterate=["R6 做人类仪表盘"],
        capability_delta="闭环力",
    )
    assert Path(result["saved_path"]).exists()


def test_run_full_pipeline_complete_run_has_all_closure_checks_true(tmp_path: Path) -> None:
    result = EvidencePipeline(str(tmp_path)).run_full_pipeline(
        _build_complete_run(),
        gained=["evidence pipeline 自动化"],
        wasted=[],
        next_iterate=["R6 做人类仪表盘"],
        capability_delta="闭环力",
    )
    assert result["evolution_log"]["closure_check"]["path_routed"] is True
    assert result["evolution_log"]["closure_check"]["result_verified"] is True
    assert result["evolution_log"]["closure_check"]["evolution_recorded"] is True
    assert result["evolution_log"]["closure_check"]["next_captured"] is True


def test_close_task_matches_pipeline_status(tmp_path: Path) -> None:
    direct = EvidencePipeline(str(tmp_path / "direct")).run_full_pipeline(
        _build_complete_run(),
        gained=["evidence pipeline 自动化"],
        wasted=[],
        next_iterate=["R6 做人类仪表盘"],
        capability_delta="闭环力",
    )
    wrapped = close_task(
        run=_build_complete_run(),
        gained=["evidence pipeline 自动化"],
        wasted=[],
        next_iterate=["R6 做人类仪表盘"],
        capability_delta="闭环力",
        artifacts_dir=str(tmp_path / "wrapped"),
    )
    assert wrapped["evolution_log"]["status"] == direct["evolution_log"]["status"]


def test_close_task_complete_run_returns_completed(tmp_path: Path) -> None:
    result = close_task(
        run=_build_complete_run(),
        gained=["evidence pipeline 自动化"],
        wasted=[],
        next_iterate=["R6 做人类仪表盘"],
        capability_delta="闭环力",
        artifacts_dir=str(tmp_path),
    )
    assert result["evolution_log"]["status"] == "completed"


def test_empty_gained_raises_validation_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="gained"):
        close_task(
            run=_build_complete_run(),
            gained=[],
            wasted=[],
            next_iterate=["R6 做人类仪表盘"],
            capability_delta="闭环力",
            artifacts_dir=str(tmp_path),
        )


def test_empty_next_iterate_raises_validation_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="next_iterate"):
        close_task(
            run=_build_complete_run(),
            gained=["evidence pipeline 自动化"],
            wasted=[],
            next_iterate=[],
            capability_delta="闭环力",
            artifacts_dir=str(tmp_path),
        )
