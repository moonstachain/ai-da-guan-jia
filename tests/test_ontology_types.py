from __future__ import annotations

from ontology.serializers import from_json, to_json
from ontology.types import (
    Action,
    AgentCapability,
    ComponentDomain,
    Confidence,
    ControlLevel,
    DecisionRecord,
    Enforcement,
    Entity,
    EntityType,
    EvidenceAtom,
    OwnerMode,
    Permission,
    PermissionBoundary,
    Policy,
    Relation,
    SourceType,
    State,
    WritebackEvent,
    WritebackResult,
)


def test_all_core_types_support_happy_path_creation() -> None:
    entity = Entity(
        entity_id="task-001",
        entity_type=EntityType.TASK,
        status="active",
        component_domain=ComponentDomain.GOVERNANCE,
        control_level=ControlLevel.CONTROL,
        owner_mode=OwnerMode.AI,
    )
    action = Action(
        action_id="act-001",
        action_type="route",
        target_entity_id=entity.entity_id,
        requires_permission=True,
    )
    policy = Policy(
        policy_id="pol-001",
        scope="governance/control",
        rule="must review",
        enforcement=Enforcement.HARD_BLOCK,
    )
    permission = Permission(
        permission_id="perm-001",
        agent_id="agent-1",
        action_types=["route"],
        boundary=PermissionBoundary.AUTONOMOUS,
    )
    evidence = EvidenceAtom(
        evidence_id="evi-001",
        source_type=SourceType.SYSTEM_OUTPUT,
        content="route completed",
        confidence=Confidence.CONFIRMED,
    )
    decision = DecisionRecord(
        decision_id="dec-001",
        decision_type="route_selection",
        rationale="smallest capable path",
        evidence_refs=[evidence.evidence_id],
    )
    capability = AgentCapability(
        agent_id="agent-1",
        capabilities=["route"],
        limitations=["no deploy"],
    )
    writeback = WritebackEvent(
        writeback_id="wb-001",
        target_entity_id=entity.entity_id,
        action_id=action.action_id,
        timestamp="2026-03-16T12:00:00Z",
        result=WritebackResult.SUCCESS,
        evidence_ref=evidence.evidence_id,
    )
    relation = Relation(
        relation_id="rel-001",
        source_entity_id="goal-1",
        target_entity_id=entity.entity_id,
        relation_type="depends_on",
    )
    state = State(
        state_id="state-001",
        entity_id=entity.entity_id,
        state_value="running",
        timestamp="2026-03-16T12:00:00Z",
    )

    assert entity.entity_type == EntityType.TASK
    assert action.requires_permission is True
    assert policy.enforcement == Enforcement.HARD_BLOCK
    assert permission.boundary == PermissionBoundary.AUTONOMOUS
    assert evidence.confidence == Confidence.CONFIRMED
    assert decision.alternatives_considered == []
    assert capability.success_rate_hint == ""
    assert writeback.result == WritebackResult.SUCCESS
    assert relation.relation_type == "depends_on"
    assert state.trigger_action_id == ""


def test_entity_component_domain_enum_coverage() -> None:
    domains = [
        ComponentDomain.GOVERNANCE,
        ComponentDomain.SALES,
        ComponentDomain.DELIVERY,
        ComponentDomain.CLONE,
    ]

    entities = [
        Entity(
            entity_id=f"entity-{domain.value}",
            entity_type=EntityType.TASK,
            status="active",
            component_domain=domain,
            control_level=ControlLevel.CONTROL,
            owner_mode=OwnerMode.SHARED,
        )
        for domain in domains
    ]

    assert [entity.component_domain for entity in entities] == domains


def test_entity_control_level_enum_coverage() -> None:
    levels = [ControlLevel.DIRECT, ControlLevel.CONTROL, ControlLevel.EXECUTE]

    entities = [
        Entity(
            entity_id=f"entity-{level.value}",
            entity_type=EntityType.THREAD,
            status="active",
            component_domain=ComponentDomain.GOVERNANCE,
            control_level=level,
            owner_mode=OwnerMode.HUMAN,
        )
        for level in levels
    ]

    assert [entity.control_level for entity in entities] == levels


def test_to_dict_from_dict_round_trip_for_core_types() -> None:
    entity = Entity(
        entity_id="task-001",
        entity_type=EntityType.TASK,
        status="active",
        component_domain=ComponentDomain.GOVERNANCE,
        control_level=ControlLevel.CONTROL,
        owner_mode=OwnerMode.AI,
    )
    action = Action(
        action_id="act-001",
        action_type="close",
        target_entity_id="task-001",
        requires_permission=True,
        human_boundary=True,
    )
    evidence = EvidenceAtom(
        evidence_id="evi-001",
        source_type=SourceType.BEHAVIOR_TRACE,
        content="human approved",
        confidence=Confidence.PROVISIONAL,
        source_ref="approval-log",
    )
    writeback = WritebackEvent(
        writeback_id="wb-001",
        target_entity_id="task-001",
        action_id="act-001",
        timestamp="2026-03-16T12:30:00Z",
        result=WritebackResult.PARTIAL,
        evidence_ref="evi-001",
        canonical_path="canonical/writebacks/wb-001.json",
    )

    assert entity == Entity.from_dict(entity.to_dict())
    assert action == Action.from_dict(action.to_dict())
    assert evidence == EvidenceAtom.from_dict(evidence.to_dict())
    assert writeback == WritebackEvent.from_dict(writeback.to_dict())


def test_to_json_from_json_round_trip_for_entity() -> None:
    entity = Entity(
        entity_id="task-002",
        entity_type=EntityType.GOAL,
        status="queued",
        component_domain=ComponentDomain.SALES,
        control_level=ControlLevel.DIRECT,
        owner_mode=OwnerMode.SHARED,
        canonical_path="canonical/entities/task-002.json",
    )

    json_str = to_json(entity)
    restored = from_json(json_str, "Entity")

    assert restored == entity
    assert "\"entity_type\": \"goal\"" in json_str

