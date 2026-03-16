from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


VALID_TIERS = {"core", "ops", "experimental"}
VALID_STATUS = {"active", "experimental", "deprecated"}
VALID_COMPONENT_DOMAINS = {"governance", "sales", "delivery", "clone"}
VALID_CONTROL_LEVELS = {"direct", "control", "execute"}


def _normalize_text(value: str) -> str:
    return value.strip().lower()


def _split_ascii_tokens(text: str) -> list[str]:
    return [token for token in re.split(r"[\s,.;:!?/\\|()\[\]{}<>\-_'\"`]+", text) if token]


def _chinese_bigrams(text: str) -> list[str]:
    chars = [char for char in text if "\u4e00" <= char <= "\u9fff"]
    if len(chars) < 2:
        return chars
    return ["".join(chars[index : index + 2]) for index in range(len(chars) - 1)]


def _extract_keywords(text: str) -> set[str]:
    normalized = _normalize_text(text)
    ascii_tokens = _split_ascii_tokens(normalized)
    ascii_bigrams: list[str] = []
    for token in ascii_tokens:
        if len(token) > 3:
            ascii_bigrams.extend(token[index : index + 2] for index in range(len(token) - 1))
    return set(ascii_tokens + ascii_bigrams + _chinese_bigrams(normalized))


def _skill_keyword_set(skill: dict[str, Any]) -> set[str]:
    parts = [
        skill.get("id", ""),
        skill.get("name", ""),
        skill.get("description", ""),
        *skill.get("input_tags", []),
        *skill.get("output_tags", []),
    ]
    keywords: set[str] = set()
    for part in parts:
        keywords.update(_extract_keywords(str(part)))
    return keywords


class SkillManifest:
    """读取 skill-manifest.json，提供查询接口"""

    def __init__(self, manifest_path: str):
        """加载 manifest 文件"""
        self.manifest_path = Path(manifest_path)
        self.data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        self.skills = list(self.data.get("skills", []))

    def list_skills(self, tier: str = None, status: str = None) -> list[dict[str, Any]]:
        """按 tier 和/或 status 过滤 skill 列表"""
        skills = self.skills
        if tier is not None:
            skills = [skill for skill in skills if skill.get("tier") == tier]
        if status is not None:
            skills = [skill for skill in skills if skill.get("status") == status]
        return skills

    def get_skill(self, skill_id: str) -> dict[str, Any] | None:
        """按 id 精确查找"""
        for skill in self.skills:
            if skill.get("id") == skill_id:
                return skill
        return None

    def find_by_tags(self, input_tags: list[str]) -> list[dict[str, Any]]:
        """找所有 input_tags 与给定标签有交集的 skill"""
        tag_set = {_normalize_text(tag) for tag in input_tags}
        return [
            skill
            for skill in self.skills
            if tag_set.intersection({_normalize_text(tag) for tag in skill.get("input_tags", [])})
        ]

    def find_by_domain(self, component_domain: str, control_level: str = None) -> list[dict[str, Any]]:
        """按组件域和控制层级过滤"""
        filtered = [
            skill
            for skill in self.skills
            if component_domain in skill.get("component_domains", [])
        ]
        if control_level is not None:
            filtered = [
                skill for skill in filtered if control_level in skill.get("control_levels", [])
            ]
        return filtered


def validate_manifest(manifest_path: str) -> list[str]:
    """
    验证 manifest 文件格式是否合法。
    """
    path = Path(manifest_path)
    errors: list[str] = []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"manifest file not found: {manifest_path}"]
    except json.JSONDecodeError as exc:
        return [f"manifest is not valid JSON: {exc}"]

    if "version" not in payload:
        errors.append("manifest must contain top-level version")
    if "skills" not in payload:
        errors.append("manifest must contain top-level skills")
        return errors
    if not isinstance(payload["skills"], list):
        errors.append("manifest skills must be a list")
        return errors

    seen_ids: set[str] = set()
    required_fields = {"id", "name", "tier", "description", "status"}
    for index, skill in enumerate(payload["skills"]):
        prefix = f"skills[{index}]"
        missing = sorted(required_fields.difference(skill))
        if missing:
            errors.append(f"{prefix} missing required fields: {', '.join(missing)}")
            continue

        skill_id = skill["id"]
        if skill_id in seen_ids:
            errors.append(f"duplicate skill id: {skill_id}")
        seen_ids.add(skill_id)

        if skill["tier"] not in VALID_TIERS:
            errors.append(f"{prefix} has invalid tier: {skill['tier']}")
        if skill["status"] not in VALID_STATUS:
            errors.append(f"{prefix} has invalid status: {skill['status']}")

        invalid_domains = sorted(
            set(skill.get("component_domains", [])).difference(VALID_COMPONENT_DOMAINS)
        )
        if invalid_domains:
            errors.append(f"{prefix} has invalid component_domains: {', '.join(invalid_domains)}")

        invalid_levels = sorted(
            set(skill.get("control_levels", [])).difference(VALID_CONTROL_LEVELS)
        )
        if invalid_levels:
            errors.append(f"{prefix} has invalid control_levels: {', '.join(invalid_levels)}")

    return errors


def route_task(
    task_description: str,
    manifest: SkillManifest,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    给定任务描述和可选上下文，返回路由建议。
    """
    context = context or {}
    task_keywords = _extract_keywords(task_description)
    ranked: list[dict[str, Any]] = []

    candidate_skills = manifest.skills
    component_domain = context.get("component_domain")
    control_level = context.get("control_level")
    if component_domain:
        candidate_skills = manifest.find_by_domain(component_domain, control_level)
    elif control_level:
        candidate_skills = [
            skill for skill in candidate_skills if control_level in skill.get("control_levels", [])
        ]

    for skill in candidate_skills:
        skill_keywords = _skill_keyword_set(skill)
        overlap = task_keywords.intersection(skill_keywords)
        if overlap:
            score = len(overlap) / max(len(task_keywords), 1)
            ranked.append(
                {
                    "skill": skill,
                    "overlap": sorted(overlap),
                    "match_score": round(score, 3),
                }
            )

    if not ranked:
        fallback = manifest.get_skill("route")
        if fallback is not None:
            ranked.append(
                {
                    "skill": fallback,
                    "overlap": [],
                    "match_score": 0.2,
                }
            )

    ranked.sort(
        key=lambda item: (
            item["match_score"],
            item["skill"].get("tier") == "core",
            -len(item["skill"].get("dependencies", [])),
        ),
        reverse=True,
    )

    recommended_items = ranked[:3]
    if recommended_items and recommended_items[0]["match_score"] >= 0.6:
        recommended_items = recommended_items[:1]

    recommended_skills = [
        {
            "skill_id": item["skill"]["id"],
            "match_reason": (
                f"任务关键词命中 {', '.join(item['overlap'])}"
                if item["overlap"]
                else "未命中明确关键词，使用通用路由兜底"
            ),
            "match_score": item["match_score"],
        }
        for item in recommended_items
    ]

    if not recommended_skills:
        warnings = ["no matching skills found in manifest"]
        rationale = "manifest 中没有找到可用技能，建议先补充 skill manifest"
    else:
        warnings = []
        if component_domain and not candidate_skills:
            warnings.append("context filters removed all manifest candidates")
        rationale = (
            "优先选择关键词命中最高且能最小充分覆盖任务的技能组合"
            if len(recommended_skills) > 1
            else f"优先选择 {recommended_skills[0]['skill_id']}，因为它最贴近当前任务描述"
        )

    selected_skill_defs = [
        manifest.get_skill(item["skill_id"]) for item in recommended_skills if manifest.get_skill(item["skill_id"])
    ]
    human_boundary_needed = any(
        bool(skill.get("human_boundary_required")) for skill in selected_skill_defs
    )

    return {
        "recommended_skills": recommended_skills,
        "routing_rationale": rationale,
        "human_boundary_needed": human_boundary_needed,
        "warnings": warnings,
    }
