from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import Enum
from typing import Any, Type, TypeVar


class EntityType(str, Enum):
    TASK = "task"
    THREAD = "thread"
    ASSET = "asset"
    SKILL = "skill"
    DATASOURCE = "datasource"
    GOAL = "goal"
    THEME = "theme"
    STRATEGY = "strategy"
    EXPERIMENT = "experiment"
    WORKFLOW = "workflow"


class ComponentDomain(str, Enum):
    GOVERNANCE = "governance"
    SALES = "sales"
    DELIVERY = "delivery"
    CLONE = "clone"


class ControlLevel(str, Enum):
    DIRECT = "direct"
    CONTROL = "control"
    EXECUTE = "execute"


class OwnerMode(str, Enum):
    HUMAN = "human"
    AI = "ai"
    SHARED = "shared"


class Enforcement(str, Enum):
    HARD_BLOCK = "hard_block"
    SOFT_WARN = "soft_warn"
    AUDIT_ONLY = "audit_only"


class PermissionBoundary(str, Enum):
    AUTONOMOUS = "autonomous"
    NEEDS_APPROVAL = "needs_approval"
    FORBIDDEN = "forbidden"


class SourceType(str, Enum):
    EXPLICIT_STATEMENT = "explicit_statement"
    BEHAVIOR_TRACE = "behavior_trace"
    REPEATED_PATTERN = "repeated_pattern"
    INFERENCE = "inference"
    SYSTEM_OUTPUT = "system_output"
    SCREENSHOT = "screenshot"


class Confidence(str, Enum):
    CONFIRMED = "confirmed"
    PROVISIONAL = "provisional"
    SUPERSEDED = "superseded"


class WritebackResult(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


EnumType = TypeVar("EnumType", bound=Enum)
DataClassType = TypeVar("DataClassType")


def _serialize_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    return value


def _to_dict(instance: Any) -> dict[str, Any]:
    return {
        field_info.name: _serialize_value(getattr(instance, field_info.name))
        for field_info in fields(instance)
    }


def _coerce_enum(value: Any, enum_cls: Type[EnumType]) -> EnumType:
    if isinstance(value, enum_cls):
        return value
    return enum_cls(value)


@dataclass
class Entity:
    entity_id: str
    entity_type: EntityType
    status: str
    component_domain: ComponentDomain
    control_level: ControlLevel
    owner_mode: OwnerMode
    canonical_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls: Type["Entity"], data: dict[str, Any]) -> "Entity":
        return cls(
            entity_id=data["entity_id"],
            entity_type=_coerce_enum(data["entity_type"], EntityType),
            status=data["status"],
            component_domain=_coerce_enum(data["component_domain"], ComponentDomain),
            control_level=_coerce_enum(data["control_level"], ControlLevel),
            owner_mode=_coerce_enum(data["owner_mode"], OwnerMode),
            canonical_path=data.get("canonical_path", ""),
        )


@dataclass
class Action:
    action_id: str
    action_type: str
    target_entity_id: str
    requires_permission: bool
    policy_ref: str = ""
    human_boundary: bool = False

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls: Type["Action"], data: dict[str, Any]) -> "Action":
        return cls(
            action_id=data["action_id"],
            action_type=data["action_type"],
            target_entity_id=data["target_entity_id"],
            requires_permission=data["requires_permission"],
            policy_ref=data.get("policy_ref", ""),
            human_boundary=data.get("human_boundary", False),
        )


@dataclass
class Policy:
    policy_id: str
    scope: str
    rule: str
    enforcement: Enforcement

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls: Type["Policy"], data: dict[str, Any]) -> "Policy":
        return cls(
            policy_id=data["policy_id"],
            scope=data["scope"],
            rule=data["rule"],
            enforcement=_coerce_enum(data["enforcement"], Enforcement),
        )


@dataclass
class Permission:
    permission_id: str
    agent_id: str
    action_types: list[str]
    boundary: PermissionBoundary

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls: Type["Permission"], data: dict[str, Any]) -> "Permission":
        return cls(
            permission_id=data["permission_id"],
            agent_id=data["agent_id"],
            action_types=list(data["action_types"]),
            boundary=_coerce_enum(data["boundary"], PermissionBoundary),
        )


@dataclass
class EvidenceAtom:
    evidence_id: str
    source_type: SourceType
    content: str
    confidence: Confidence
    source_ref: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls: Type["EvidenceAtom"], data: dict[str, Any]) -> "EvidenceAtom":
        return cls(
            evidence_id=data["evidence_id"],
            source_type=_coerce_enum(data["source_type"], SourceType),
            content=data["content"],
            confidence=_coerce_enum(data["confidence"], Confidence),
            source_ref=data.get("source_ref", ""),
        )


@dataclass
class DecisionRecord:
    decision_id: str
    decision_type: str
    rationale: str
    evidence_refs: list[str]
    alternatives_considered: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls: Type["DecisionRecord"], data: dict[str, Any]) -> "DecisionRecord":
        return cls(
            decision_id=data["decision_id"],
            decision_type=data["decision_type"],
            rationale=data["rationale"],
            evidence_refs=list(data["evidence_refs"]),
            alternatives_considered=list(data.get("alternatives_considered", [])),
        )


@dataclass
class AgentCapability:
    agent_id: str
    capabilities: list[str]
    limitations: list[str]
    success_rate_hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls: Type["AgentCapability"], data: dict[str, Any]) -> "AgentCapability":
        return cls(
            agent_id=data["agent_id"],
            capabilities=list(data["capabilities"]),
            limitations=list(data["limitations"]),
            success_rate_hint=data.get("success_rate_hint", ""),
        )


@dataclass
class WritebackEvent:
    writeback_id: str
    target_entity_id: str
    action_id: str
    timestamp: str
    result: WritebackResult
    evidence_ref: str = ""
    canonical_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls: Type["WritebackEvent"], data: dict[str, Any]) -> "WritebackEvent":
        return cls(
            writeback_id=data["writeback_id"],
            target_entity_id=data["target_entity_id"],
            action_id=data["action_id"],
            timestamp=data["timestamp"],
            result=_coerce_enum(data["result"], WritebackResult),
            evidence_ref=data.get("evidence_ref", ""),
            canonical_path=data.get("canonical_path", ""),
        )


@dataclass
class Relation:
    relation_id: str
    source_entity_id: str
    target_entity_id: str
    relation_type: str

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls: Type["Relation"], data: dict[str, Any]) -> "Relation":
        return cls(
            relation_id=data["relation_id"],
            source_entity_id=data["source_entity_id"],
            target_entity_id=data["target_entity_id"],
            relation_type=data["relation_type"],
        )


@dataclass
class State:
    state_id: str
    entity_id: str
    state_value: str
    timestamp: str
    trigger_action_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls: Type["State"], data: dict[str, Any]) -> "State":
        return cls(
            state_id=data["state_id"],
            entity_id=data["entity_id"],
            state_value=data["state_value"],
            timestamp=data["timestamp"],
            trigger_action_id=data.get("trigger_action_id", ""),
        )

