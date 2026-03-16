from __future__ import annotations

import json
from typing import Any

from ontology.types import (
    Action,
    AgentCapability,
    DecisionRecord,
    Entity,
    EvidenceAtom,
    Permission,
    Policy,
    Relation,
    State,
    WritebackEvent,
)

TYPE_MAP = {
    "Entity": Entity,
    "Action": Action,
    "Policy": Policy,
    "Permission": Permission,
    "EvidenceAtom": EvidenceAtom,
    "DecisionRecord": DecisionRecord,
    "AgentCapability": AgentCapability,
    "WritebackEvent": WritebackEvent,
    "Relation": Relation,
    "State": State,
}


def to_json(obj: Any, indent: int = 2) -> str:
    """把任何 ontology 对象序列化为 JSON 字符串"""
    return json.dumps(obj.to_dict(), indent=indent, ensure_ascii=False)


def from_json(json_str: str, target_type_name: str) -> Any:
    """从 JSON 字符串反序列化为指定类型"""
    cls = TYPE_MAP[target_type_name]
    return cls.from_dict(json.loads(json_str))

