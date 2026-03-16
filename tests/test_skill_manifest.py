from __future__ import annotations

import json
from pathlib import Path

from ontology.router import VALID_COMPONENT_DOMAINS, VALID_CONTROL_LEVELS, validate_manifest


MANIFEST_PATH = Path(__file__).resolve().parent.parent / "skill-manifest.json"


def test_manifest_exists_and_is_parseable() -> None:
    assert MANIFEST_PATH.exists()
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)


def test_validate_manifest_returns_no_errors() -> None:
    assert validate_manifest(str(MANIFEST_PATH)) == []


def test_manifest_contains_at_least_thirteen_skills() -> None:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert len(payload["skills"]) >= 13


def test_core_tier_has_five_skills() -> None:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert sum(skill["tier"] == "core" for skill in payload["skills"]) == 5


def test_ops_tier_has_seven_or_more_skills() -> None:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert sum(skill["tier"] == "ops" for skill in payload["skills"]) >= 7


def test_experimental_tier_has_two_skills() -> None:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert sum(skill["tier"] == "experimental" for skill in payload["skills"]) == 2


def test_all_skill_ids_are_unique() -> None:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    skill_ids = [skill["id"] for skill in payload["skills"]]
    assert len(skill_ids) == len(set(skill_ids))


def test_all_component_domains_are_valid() -> None:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for skill in payload["skills"]:
        assert set(skill["component_domains"]).issubset(VALID_COMPONENT_DOMAINS)


def test_all_control_levels_are_valid() -> None:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for skill in payload["skills"]:
        assert set(skill["control_levels"]).issubset(VALID_CONTROL_LEVELS)
