from __future__ import annotations

from ontology.types import (
    Action,
    ComponentDomain,
    ControlLevel,
    Entity,
    EntityType,
    EvidenceAtom,
    OwnerMode,
    Permission,
    PermissionBoundary,
    WritebackEvent,
    WritebackResult,
)


def _is_valid_enum_member(value: object, enum_cls: type) -> bool:
    try:
        enum_cls(value)
        return True
    except (TypeError, ValueError):
        return False


def validate_entity(entity: Entity) -> list[str]:
    """
    检查 Entity 的必填字段和枚举值是否合法。
    返回错误信息列表，空列表表示验证通过。
    """
    errors: list[str] = []

    if not entity.entity_id:
        errors.append("entity_id must not be empty")
    if not _is_valid_enum_member(entity.entity_type, EntityType):
        errors.append("entity_type must be a valid EntityType")
    if not _is_valid_enum_member(entity.component_domain, ComponentDomain):
        errors.append("component_domain must be a valid ComponentDomain")
    if not _is_valid_enum_member(entity.control_level, ControlLevel):
        errors.append("control_level must be a valid ControlLevel")
    if not _is_valid_enum_member(entity.owner_mode, OwnerMode):
        errors.append("owner_mode must be a valid OwnerMode")

    return errors


def validate_action_permission(action: Action, permissions: list[Permission]) -> bool:
    """
    检查给定的 Action 是否有对应的 Permission 允许执行。
    """
    if not action.requires_permission:
        return True

    for permission in permissions:
        if action.action_type not in permission.action_types:
            continue
        if permission.boundary == PermissionBoundary.FORBIDDEN:
            continue
        if action.human_boundary and permission.boundary != PermissionBoundary.NEEDS_APPROVAL:
            continue
        return True

    return False


def check_closure_readiness(
    path_routed: bool,
    result_verified: bool,
    evolution_recorded: bool,
    next_captured: bool,
) -> bool:
    """
    四条闭环规则，全部为 True 才返回 True。
    """
    return all([path_routed, result_verified, evolution_recorded, next_captured])


def validate_writeback_chain(
    action: Action,
    writeback: WritebackEvent,
    evidence: EvidenceAtom,
) -> list[str]:
    """
    检查"动作→写回→证据"硬链是否完整。
    """
    errors: list[str] = []

    if writeback.action_id != action.action_id:
        errors.append("writeback.action_id must match action.action_id")
    if writeback.target_entity_id != action.target_entity_id:
        errors.append("writeback.target_entity_id must match action.target_entity_id")
    if writeback.evidence_ref != evidence.evidence_id:
        errors.append("writeback.evidence_ref must match evidence.evidence_id")
    if writeback.result == WritebackResult.FAILED:
        errors.append("writeback.result must not be FAILED")

    return errors

