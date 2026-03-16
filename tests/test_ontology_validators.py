from __future__ import annotations

from ontology.types import (
    Action,
    ComponentDomain,
    Confidence,
    ControlLevel,
    Entity,
    EntityType,
    EvidenceAtom,
    OwnerMode,
    Permission,
    PermissionBoundary,
    SourceType,
    WritebackEvent,
    WritebackResult,
)
from ontology.validators import (
    check_closure_readiness,
    validate_action_permission,
    validate_entity,
    validate_writeback_chain,
)


def _build_entity() -> Entity:
    return Entity(
        entity_id="task-001",
        entity_type=EntityType.TASK,
        status="active",
        component_domain=ComponentDomain.GOVERNANCE,
        control_level=ControlLevel.CONTROL,
        owner_mode=OwnerMode.AI,
    )


def _build_action(*, requires_permission: bool = True, human_boundary: bool = False) -> Action:
    return Action(
        action_id="act-001",
        action_type="close_task",
        target_entity_id="task-001",
        requires_permission=requires_permission,
        human_boundary=human_boundary,
    )


def _build_evidence() -> EvidenceAtom:
    return EvidenceAtom(
        evidence_id="evi-001",
        source_type=SourceType.SYSTEM_OUTPUT,
        content="task closed",
        confidence=Confidence.CONFIRMED,
    )


def _build_writeback(*, result: WritebackResult = WritebackResult.SUCCESS) -> WritebackEvent:
    return WritebackEvent(
        writeback_id="wb-001",
        target_entity_id="task-001",
        action_id="act-001",
        timestamp="2026-03-16T12:45:00Z",
        result=result,
        evidence_ref="evi-001",
    )


def test_validate_entity_returns_no_errors_for_valid_entity() -> None:
    assert validate_entity(_build_entity()) == []


def test_validate_entity_reports_empty_entity_id() -> None:
    entity = _build_entity()
    entity.entity_id = ""

    errors = validate_entity(entity)

    assert "entity_id must not be empty" in errors


def test_validate_action_permission_returns_true_when_permission_not_required() -> None:
    assert validate_action_permission(_build_action(requires_permission=False), []) is True


def test_validate_action_permission_returns_true_for_matching_permission() -> None:
    permission = Permission(
        permission_id="perm-001",
        agent_id="agent-1",
        action_types=["close_task"],
        boundary=PermissionBoundary.AUTONOMOUS,
    )

    assert validate_action_permission(_build_action(), [permission]) is True


def test_validate_action_permission_rejects_forbidden_permission() -> None:
    permission = Permission(
        permission_id="perm-002",
        agent_id="agent-1",
        action_types=["close_task"],
        boundary=PermissionBoundary.FORBIDDEN,
    )

    assert validate_action_permission(_build_action(), [permission]) is False


def test_validate_action_permission_rejects_autonomous_for_human_boundary() -> None:
    permission = Permission(
        permission_id="perm-003",
        agent_id="agent-1",
        action_types=["close_task"],
        boundary=PermissionBoundary.AUTONOMOUS,
    )

    assert validate_action_permission(_build_action(human_boundary=True), [permission]) is False


def test_check_closure_readiness_returns_true_when_all_flags_are_true() -> None:
    assert check_closure_readiness(True, True, True, True) is True


def test_check_closure_readiness_returns_false_for_incomplete_combinations() -> None:
    assert check_closure_readiness(False, True, True, True) is False
    assert check_closure_readiness(True, True, False, True) is False


def test_validate_writeback_chain_returns_no_errors_for_complete_chain() -> None:
    assert validate_writeback_chain(_build_action(), _build_writeback(), _build_evidence()) == []


def test_validate_writeback_chain_reports_action_id_mismatch() -> None:
    writeback = _build_writeback()
    writeback.action_id = "act-999"

    errors = validate_writeback_chain(_build_action(), writeback, _build_evidence())

    assert "writeback.action_id must match action.action_id" in errors


def test_validate_writeback_chain_reports_failed_result() -> None:
    errors = validate_writeback_chain(
        _build_action(),
        _build_writeback(result=WritebackResult.FAILED),
        _build_evidence(),
    )

    assert "writeback.result must not be FAILED" in errors
