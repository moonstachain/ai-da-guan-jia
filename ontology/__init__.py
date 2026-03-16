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
from ontology.validators import (
    check_closure_readiness,
    validate_action_permission,
    validate_entity,
    validate_writeback_chain,
)

