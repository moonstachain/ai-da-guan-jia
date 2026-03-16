from __future__ import annotations

import json
from pathlib import Path

from ontology.router import SkillManifest, route_task, validate_manifest


MANIFEST_PATH = Path(__file__).resolve().parent.parent / "skill-manifest.json"


def test_skill_manifest_loads_manifest() -> None:
    manifest = SkillManifest(str(MANIFEST_PATH))
    assert manifest.data["version"] == "1.0.0"


def test_list_skills_without_filters_returns_all() -> None:
    manifest = SkillManifest(str(MANIFEST_PATH))
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert len(manifest.list_skills()) == len(payload["skills"])


def test_list_skills_core_returns_five() -> None:
    manifest = SkillManifest(str(MANIFEST_PATH))
    assert len(manifest.list_skills(tier="core")) == 5


def test_get_skill_route_returns_expected_skill() -> None:
    manifest = SkillManifest(str(MANIFEST_PATH))
    route_skill = manifest.get_skill("route")
    assert route_skill is not None
    assert route_skill["name"] == "Route"


def test_get_skill_nonexistent_returns_none() -> None:
    manifest = SkillManifest(str(MANIFEST_PATH))
    assert manifest.get_skill("nonexistent") is None


def test_find_by_tags_returns_route_for_task_description() -> None:
    manifest = SkillManifest(str(MANIFEST_PATH))
    results = manifest.find_by_tags(["task_description"])
    assert any(skill["id"] == "route" for skill in results)


def test_find_by_domain_governance_returns_multiple_skills() -> None:
    manifest = SkillManifest(str(MANIFEST_PATH))
    assert len(manifest.find_by_domain("governance")) > 1


def test_find_by_domain_governance_direct_returns_subset() -> None:
    manifest = SkillManifest(str(MANIFEST_PATH))
    governance_skills = manifest.find_by_domain("governance")
    direct_governance_skills = manifest.find_by_domain("governance", "direct")
    assert len(direct_governance_skills) < len(governance_skills)


def test_route_task_returns_recommended_skills_dict() -> None:
    manifest = SkillManifest(str(MANIFEST_PATH))
    result = route_task("帮我路由一个任务", manifest)
    assert "recommended_skills" in result
    assert isinstance(result["recommended_skills"], list)


def test_route_task_recommended_skills_is_not_empty() -> None:
    manifest = SkillManifest(str(MANIFEST_PATH))
    result = route_task("帮我路由一个任务", manifest)
    assert result["recommended_skills"]


def test_route_task_contains_routing_rationale() -> None:
    manifest = SkillManifest(str(MANIFEST_PATH))
    result = route_task("帮我路由一个任务", manifest)
    assert result["routing_rationale"]


def test_route_task_closure_keyword_recommends_close_task() -> None:
    manifest = SkillManifest(str(MANIFEST_PATH))
    result = route_task("帮我完成一个任务并闭环", manifest)
    recommended_ids = [item["skill_id"] for item in result["recommended_skills"]]
    assert "close-task" in recommended_ids


def test_validate_manifest_returns_no_errors_for_valid_manifest() -> None:
    assert validate_manifest(str(MANIFEST_PATH)) == []


def test_validate_manifest_reports_missing_skills_field(tmp_path: Path) -> None:
    invalid_manifest = tmp_path / "invalid-skill-manifest.json"
    invalid_manifest.write_text(
        json.dumps({"version": "1.0.0"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    errors = validate_manifest(str(invalid_manifest))

    assert any("skills" in error for error in errors)
