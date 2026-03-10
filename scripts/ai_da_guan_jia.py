#!/usr/bin/env python3
"""Local helper and router for the ai-da-guan-jia skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
CODEX_HOME = Path(os.getenv("CODEX_HOME", str(Path.home() / ".codex"))).resolve()
SKILLS_ROOT = CODEX_HOME / "skills"
ARTIFACTS_ROOT = SKILL_DIR / "artifacts" / "ai-da-guan-jia"
RUNS_ROOT = ARTIFACTS_ROOT / "runs"
INVENTORY_ROOT = ARTIFACTS_ROOT / "inventory"
REVIEWS_ROOT = ARTIFACTS_ROOT / "reviews"
REVIEW_STATE_PATH = ARTIFACTS_ROOT / "review-state.json"
SOUL_ROOT = ARTIFACTS_ROOT / "soul"
STRATEGY_ROOT = ARTIFACTS_ROOT / "strategy"
STRATEGY_CURRENT_ROOT = STRATEGY_ROOT / "current"
DEFAULT_BRIDGE = (
    CODEX_HOME / "skills" / "feishu-bitable-bridge" / "scripts" / "feishu_bitable_bridge.py"
)
DEFAULT_FEISHU_LINK = "https://h52xu4gwob.feishu.cn/wiki/FwG2wbljSiQrtPkTt8RcLAbxnvd?from=from_copylink&table=tblDR8XbK5fxun4x&view=vewbJgjzHr"
DEFAULT_REVIEW_FEISHU_LINK = "https://h52xu4gwob.feishu.cn/wiki/UzRjwDDLyi9OP4kEIHkcin1Gnhc?from=from_copylink"
REVIEW_SCHEMA_MANIFEST = SKILL_DIR / "references" / "feishu-review-base-schema.json"
REVIEW_SYNC_CONTRACT = SKILL_DIR / "references" / "feishu-review-sync-contract.md"
DEFAULT_GITHUB_BASE_URL = "https://github.com"
DEFAULT_GITHUB_API_URL = "https://api.github.com"
DEFAULT_GITHUB_OPS_REPO_NAME = "ai-task-ops"
DEFAULT_GITHUB_DOT_GITHUB_REPO = ".github"
GITHUB_TYPE_CHOICES = ["research", "spec", "implement", "debug", "review", "sync", "publish", "governance"]
GITHUB_DOMAIN_CHOICES = ["github", "feishu", "openai", "skill-system", "content", "data", "ops"]
GITHUB_STATE_CHOICES = ["intake", "routed", "in_progress", "waiting_human", "blocked", "verified", "archived"]
GITHUB_ARTIFACT_CHOICES = ["skill", "code", "doc", "workflow", "dataset", "integration", "report"]
GITHUB_SKIP_PATTERNS = {
    "hi",
    "hello",
    "hey",
    "yo",
    "thanks",
    "thank you",
    "ok",
    "okay",
    "好的",
    "收到",
    "谢谢",
    "你好",
    "在吗",
}
ROUTING_ORDER = [
    "task_fit_score",
    "verification_score",
    "cost_score",
    "auth_reuse_score",
    "complexity_penalty",
]
REQUIRED_EVOLUTION_FIELDS = [
    "run_id",
    "created_at",
    "task_text",
    "goal_model",
    "autonomy_judgment",
    "global_optimum_judgment",
    "reuse_judgment",
    "verification_judgment",
    "evolution_judgment",
    "max_distortion",
    "skills_considered",
    "skills_selected",
    "human_boundary",
    "verification_result",
    "effective_patterns",
    "wasted_patterns",
    "evolution_candidates",
    "feishu_sync_status",
    "evolution_judgment_detail",
    "evolution_writeback_applied",
    "evolution_writeback_commit",
    "github_task_key",
    "github_issue_url",
    "github_project_url",
    "github_repo",
    "github_sync_status",
    "github_classification",
    "github_archive_status",
    "github_closure_comment_url",
]

REVIEW_RUBRIC = [
    "顺手度",
    "闭环度",
    "复用度",
    "证据度",
    "边界清晰度",
    "进化潜力",
]

REVIEW_ACTION_TYPES = [
    "路由修正",
    "workflow hardening",
    "去重/合并",
    "新建中层 skill",
]
AUTONOMY_TIERS = ["observe", "suggest", "trusted-suggest", "guarded-autonomy"]


@dataclass(frozen=True)
class SkillProfile:
    name: str
    role: str
    strengths: list[str]
    weaknesses: list[str]
    boundary: str
    keywords: list[str]
    verification_strength: int
    cost_efficiency: int
    auth_reuse: int
    complexity_penalty: int


CORE_PROFILES: dict[str, SkillProfile] = {
    "ai-da-guan-jia": SkillProfile(
        name="ai-da-guan-jia",
        role="Govern the local skill system, route to the smallest sufficient combination, and close the loop with review and evolution artifacts.",
        strengths=["Skill inventory", "Intentional routing", "Review and evolution closure"],
        weaknesses=["Needs middle-layer skills and clear route rules to stay smooth"],
        boundary="Use as the top-level governor when the job is choosing, reviewing, or evolving the local skill system itself.",
        keywords=["ai-da-guan-jia", "大管家", "盘点", "能力地图", "评估", "skill review", "inventory review"],
        verification_strength=5,
        cost_efficiency=4,
        auth_reuse=2,
        complexity_penalty=1,
    ),
    "ai-metacognitive-core": SkillProfile(
        name="ai-metacognitive-core",
        role="Expose distortion risk, truth conditions, and collaboration boundaries.",
        strengths=["Meta judgment", "Pseudo-completion detection", "Boundary clarity"],
        weaknesses=["Does not deliver domain work alone"],
        boundary="Use as a judgment layer before or around domain execution.",
        keywords=["ai-metacognitive-core", "元认知", "失真", "假完成", "认知", "judgment"],
        verification_strength=5,
        cost_efficiency=3,
        auth_reuse=1,
        complexity_penalty=1,
    ),
    "jiyao-youyao-haiyao": SkillProfile(
        name="jiyao-youyao-haiyao",
        role="Drive minimal-interruption, proof-first, cheapest-reliable execution.",
        strengths=["Autonomy", "Cost control", "Escalation discipline"],
        weaknesses=["Not domain-specific"],
        boundary="Use as the execution layer when the main risk is waste or interruption.",
        keywords=[
            "jiyao-youyao-haiyao",
            "少打扰",
            "低打扰",
            "end-to-end",
            "自己搞定",
            "autonomous",
            "minimal interruption",
        ],
        verification_strength=4,
        cost_efficiency=5,
        auth_reuse=2,
        complexity_penalty=1,
    ),
    "jiyao-youyao-haiyao-zaiyao": SkillProfile(
        name="jiyao-youyao-haiyao-zaiyao",
        role="Handle complex multi-step execution with strong convergence and short reflection.",
        strengths=["Complex workflow control", "Reflection discipline"],
        weaknesses=["Heavier than needed for simple work"],
        boundary="Use when the task is clearly complex and multi-stage.",
        keywords=[
            "jiyao-youyao-haiyao-zaiyao",
            "复杂任务",
            "多步骤",
            "multi-step",
            "workflow",
            "全局最优",
        ],
        verification_strength=4,
        cost_efficiency=4,
        auth_reuse=2,
        complexity_penalty=2,
    ),
    "skill-creator": SkillProfile(
        name="skill-creator",
        role="Create or update Codex skills with the correct skeleton and validation flow.",
        strengths=["Skill scaffolding", "Validation", "Progressive disclosure design"],
        weaknesses=["Not a meta-governor"],
        boundary="Route here first when the task is to create or update a skill.",
        keywords=[
            "skill-creator",
            "skill",
            "create skill",
            "new skill",
            "新 skill",
            "更新 skill",
            "做一个 skill",
            "做一个新 skill",
            "skill.md",
        ],
        verification_strength=5,
        cost_efficiency=5,
        auth_reuse=1,
        complexity_penalty=1,
    ),
    "skill-trainer-recursive": SkillProfile(
        name="skill-trainer-recursive",
        role="Train new skills through strategic intent, first principles, benchmark alignment, and recursive MVP evaluation.",
        strengths=["Intent modeling", "First-principles decomposition", "Benchmark alignment", "Skill training loops"],
        weaknesses=["Heavier than direct scaffolding when the user only needs a quick one-off skill file"],
        boundary="Use before direct scaffolding when the user wants to train a skill method, not merely generate one.",
        keywords=[
            "skill-trainer-recursive",
            "训练新技能",
            "训练技能",
            "技能训练",
            "设计技能方法学",
            "训练技能的技能",
            "first principles",
            "benchmark",
        ],
        verification_strength=5,
        cost_efficiency=4,
        auth_reuse=1,
        complexity_penalty=2,
    ),
    "guide-benchmark-learning": SkillProfile(
        name="guide-benchmark-learning",
        role="Learn unfamiliar capabilities by reading manuals, official docs, benchmark guides, and comparable cases before execution.",
        strengths=["Manual-first learning", "Source hierarchy discipline", "Execution-readiness judgment", "Reusable handbooks"],
        weaknesses=["Does not execute domain work by itself"],
        boundary="Use when the task is unfamiliar enough that learning should happen before execution or skill training.",
        keywords=[
            "guide-benchmark-learning",
            "学习",
            "入门",
            "先读",
            "官方文档",
            "说明书",
            "攻略",
            "教程",
            "最佳实践",
            "对标",
            "benchmark",
            "best practice",
            "api 文档",
            "manual",
            "guide",
        ],
        verification_strength=5,
        cost_efficiency=4,
        auth_reuse=2,
        complexity_penalty=1,
    ),
    "openai-docs": SkillProfile(
        name="openai-docs",
        role="Fetch authoritative OpenAI documentation and treat official docs as the source of truth.",
        strengths=["Official docs first", "Current citations", "Product-specific scope control"],
        weaknesses=["Only covers OpenAI domains"],
        boundary="Use after a manual-first learning decision when the domain is OpenAI products or APIs.",
        keywords=[
            "openai",
            "chatgpt",
            "responses api",
            "realtime api",
            "apps sdk",
            "agents sdk",
            "codex",
            "openai docs",
        ],
        verification_strength=5,
        cost_efficiency=4,
        auth_reuse=2,
        complexity_penalty=1,
    ),
    "openclaw-xhs-coevolution-lab": SkillProfile(
        name="openclaw-xhs-coevolution-lab",
        role="Turn real OpenClaw co-evolution experiments into Xiaohongshu viral note blueprints and iterative content systems.",
        strengths=["Content positioning", "Topic ideation", "Evidence-first Xiaohongshu blueprints", "Co-evolution narrative framing"],
        weaknesses=["Does not publish content by itself in v1"],
        boundary="Use when the task is about OpenClaw, Xiaohongshu, co-evolution storytelling, or viral note strategy rather than direct publishing.",
        keywords=[
            "openclaw-xhs-coevolution-lab",
            "openclaw",
            "open claw",
            "小红书",
            "xhs",
            "爆款",
            "博主",
            "图文笔记",
            "共进化",
            "内容赛道",
        ],
        verification_strength=4,
        cost_efficiency=4,
        auth_reuse=2,
        complexity_penalty=1,
    ),
    "knowledge-orchestrator": SkillProfile(
        name="knowledge-orchestrator",
        role="Ask the knowledge base first, then synthesize and plan from it.",
        strengths=["Knowledge-first workflow", "Raw answer preservation"],
        weaknesses=["Depends on external knowledge system state"],
        boundary="Route here first when the user wants the knowledge base queried before planning.",
        keywords=[
            "knowledge-orchestrator",
            "知识库",
            "knowledge base",
            "notebooklm",
            "先问",
            "kb",
        ],
        verification_strength=4,
        cost_efficiency=3,
        auth_reuse=3,
        complexity_penalty=2,
    ),
    "self-evolution-max": SkillProfile(
        name="self-evolution-max",
        role="Run versioned plan-execute-evaluate-iterate loops.",
        strengths=["Iteration loops", "MVP strategy", "Feedback cycles"],
        weaknesses=["Heavier than a one-shot task router"],
        boundary="Use when the task is explicitly iterative or feedback-driven.",
        keywords=[
            "self-evolution-max",
            "迭代",
            "进化",
            "feedback",
            "mvp",
            "循环",
            "复盘",
        ],
        verification_strength=4,
        cost_efficiency=3,
        auth_reuse=1,
        complexity_penalty=2,
    ),
    "agency-agents-orchestrator": SkillProfile(
        name="agency-agents-orchestrator",
        role="Coordinate multi-agent or multi-role pipelines with QA loops.",
        strengths=["Pipeline coordination", "QA loop orchestration"],
        weaknesses=["Can overshoot for smaller tasks"],
        boundary="Use when the job truly needs staged agent orchestration.",
        keywords=[
            "agency-agents-orchestrator",
            "orchestrator",
            "pipeline",
            "qa",
            "多 agent",
            "多角色",
            "统筹开发",
        ],
        verification_strength=4,
        cost_efficiency=2,
        auth_reuse=1,
        complexity_penalty=3,
    ),
    "feishu-bitable-bridge": SkillProfile(
        name="feishu-bitable-bridge",
        role="Inspect or safely upsert Feishu bitable records with preview-first semantics.",
        strengths=["Schema-aware sync", "Preview before apply", "Safe external writes"],
        weaknesses=["External-system dependent"],
        boundary="Use only after the local canonical log and Feishu payload already exist.",
        keywords=[
            "feishu-bitable-bridge",
            "飞书",
            "多维表",
            "bitable",
            "wiki",
            "base",
            "同步飞书",
        ],
        verification_strength=5,
        cost_efficiency=2,
        auth_reuse=5,
        complexity_penalty=2,
    ),
}


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def now_local() -> datetime:
    return datetime.now().astimezone()


def iso_now() -> str:
    return now_local().isoformat(timespec="seconds")


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_frontmatter(text: str) -> dict[str, Any]:
    match = re.match(r"^---\n(.*?)\n---(?:\n|$)", text, re.DOTALL)
    if not match:
        return {}
    frontmatter = match.group(1)
    try:
        import yaml  # type: ignore

        payload = yaml.safe_load(frontmatter)
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass

    result: dict[str, Any] = {}
    lines = frontmatter.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if ":" not in line:
            index += 1
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if value in {"|", ">", "|-", ">-"}:
            index += 1
            block: list[str] = []
            while index < len(lines) and (lines[index].startswith("  ") or not lines[index].strip()):
                stripped = lines[index].strip()
                if stripped:
                    block.append(stripped)
                index += 1
            result[key] = " ".join(block)
            continue
        result[key] = value.strip("\"'")
        index += 1
    return result


def read_skill_metadata(skill_md: Path) -> dict[str, Any] | None:
    try:
        payload = parse_frontmatter(load_text(skill_md))
    except Exception:
        return None
    name = str(payload.get("name") or "").strip()
    description = str(payload.get("description") or "").strip()
    if not name:
        return None
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    source = str(metadata.get("source") or "").strip() if isinstance(metadata, dict) else ""
    return {"name": name, "description": description, "source": source}


def discover_skill_files() -> list[Path]:
    if not SKILLS_ROOT.exists():
        return []
    files = list(SKILLS_ROOT.glob("*/SKILL.md"))
    files.extend(SKILLS_ROOT.glob(".system/*/SKILL.md"))
    return sorted(path.resolve() for path in files if path.is_file())


def discover_skills() -> list[dict[str, Any]]:
    skills: list[dict[str, Any]] = []
    seen: set[str] = set()
    for skill_md in discover_skill_files():
        metadata = read_skill_metadata(skill_md)
        if not metadata:
            continue
        name = metadata["name"]
        if name in seen:
            continue
        seen.add(name)
        profile = CORE_PROFILES.get(name)
        entry = {
            "name": name,
            "description": metadata["description"],
            "path": str(skill_md.parent),
            "is_core": profile is not None,
            "role": profile.role if profile else "Discovered local skill. Read SKILL.md before use.",
            "strengths": profile.strengths if profile else ["Discover from SKILL.md on demand"],
            "weaknesses": profile.weaknesses if profile else ["No curated profile yet"],
            "boundary": profile.boundary if profile else "Read the skill before routing real work to it.",
        }
        skills.append(entry)
    return sorted(skills, key=lambda item: item["name"])


def discover_top_level_skill_files() -> list[Path]:
    if not SKILLS_ROOT.exists():
        return []
    return sorted(path.resolve() for path in SKILLS_ROOT.glob("*/SKILL.md") if path.is_file())


def skill_layer(name: str) -> str:
    if name.startswith(("ai-", "jiyao-", "skill-")) or name in {"knowledge-orchestrator", "self-evolution-max", "guide-benchmark-learning"}:
        return "元治理层"
    if name.startswith("agency-"):
        return "专家角色层"
    if name.startswith(("feishu-", "notion-", "github-", "gh-")) or name in {
        "figma",
        "figma-implement-design",
        "playwright",
        "playwright-interactive",
        "openai-docs",
        "cloudflare-deploy",
        "linear",
        "atlas",
        "chatgpt-apps",
        "screenshot",
    }:
        return "平台/工具集成层"
    return "垂直工作流层"


def skill_resource_flags(skill_dir: Path) -> dict[str, bool]:
    return {
        "scripts": (skill_dir / "scripts").exists(),
        "references": (skill_dir / "references").exists(),
        "assets": (skill_dir / "assets").exists(),
        "agents": (skill_dir / "agents").exists(),
    }


def metadata_source_repo(source: str) -> str:
    value = source.strip()
    if not value:
        return ""
    return value.split(":", 1)[0].strip()


def git_origin_repo(skill_dir: Path) -> str:
    if not (skill_dir / ".git").exists():
        return ""
    completed = subprocess.run(
        ["git", "-C", str(skill_dir), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return ""
    raw = completed.stdout.strip()
    if raw.startswith("git@github.com:"):
        raw = raw.split(":", 1)[1]
    elif "github.com/" in raw:
        raw = raw.split("github.com/", 1)[1]
    raw = raw.removesuffix(".git").strip("/")
    return raw


def skill_cluster(name: str) -> str:
    if name in {"ai-da-guan-jia", "ai-metacognitive-core", "routing-playbook", "self-evolution-max", "guide-benchmark-learning"} or name.startswith("jiyao-"):
        return "AI大管家治理簇"
    if name.startswith("skill-") or name == "strategy-skill-template":
        return "技能生产簇"
    if skill_layer(name) == "平台/工具集成层":
        return "平台簇"
    if name.startswith("agency-"):
        return "agency簇"
    return "垂直workflow簇"


def skill_type(name: str) -> str:
    layer = skill_layer(name)
    if layer == "元治理层":
        return "governance"
    if layer == "平台/工具集成层":
        return "platform"
    if name.startswith("agency-"):
        return "persona"
    return "workflow"


def resource_completeness(resources: dict[str, bool]) -> str:
    enabled = [key for key, value in resources.items() if value]
    if len(enabled) == 4:
        return "full-stack"
    if len(enabled) >= 2:
        return "partial"
    if enabled:
        return "minimal"
    return "empty"


def ease_of_use_judgment(item: dict[str, Any]) -> str:
    if item["type"] == "persona":
        return "更像角色说明，需 hardening 才顺手"
    if item["resource_score"] == 4:
        return "闭环强，适合高频调用"
    if item["layer"] == "平台/工具集成层" and item["resource_score"] >= 2:
        return "平台边界清楚，日常较顺手"
    if item["resource_score"] <= 1:
        return "轻结构，顺手度依赖记忆"
    return "可用，但仍需更清楚的组合手册"


def boundary_note(name: str) -> str:
    notes = {
        "figma": "与 figma-implement-design 共享设计入口，需要按总入口 vs 1:1 实现分流。",
        "figma-implement-design": "与 figma 的边界在 1:1 设计实现，而不是泛 Figma 上下文读取。",
        "jiyao-youyao-haiyao": "与 zaiyao 的边界在复杂度；简单自治优先用本 skill。",
        "jiyao-youyao-haiyao-zaiyao": "只有复杂多阶段任务才升级到 zaiyao。",
        "knowledge-orchestrator": "不要与 Notion 研究型 skill 混成同一个入口。",
        "youquant-backtest": "与 youquant-backtest-automation 存在明确重叠，应优先收敛。",
        "youquant-backtest-automation": "与 youquant-backtest 存在明确重叠，应优先收敛。",
    }
    return notes.get(name, "")


def build_review_inventory() -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for skill_md in discover_top_level_skill_files():
        metadata = read_skill_metadata(skill_md)
        if not metadata:
            continue
        resources = skill_resource_flags(skill_md.parent)
        metadata_repo = metadata_source_repo(str(metadata.get("source") or ""))
        git_repo = git_origin_repo(skill_md.parent)
        source_repo = metadata_repo or git_repo
        source_type = "metadata.source" if metadata_repo else "git-origin" if git_repo else "local-native"
        item = {
            "name": metadata["name"],
            "directory_name": skill_md.parent.name,
            "description": metadata["description"],
            "path": str(skill_md.parent),
            "layer": skill_layer(metadata["name"]),
            "cluster": skill_cluster(metadata["name"]),
            "type": skill_type(metadata["name"]),
            "resources": resources,
            "resource_score": sum(1 for value in resources.values() if value),
            "resource_completeness": resource_completeness(resources),
            "source": str(metadata.get("source") or ""),
            "source_repo": source_repo,
            "source_type": source_type,
            "git_origin_repo": git_repo,
        }
        item["ease_of_use_judgment"] = ease_of_use_judgment(item)
        item["boundary_note"] = boundary_note(item["name"])
        inventory.append(
            item
        )
    return sorted(inventory, key=lambda item: item["name"])


def load_review_state() -> dict[str, Any]:
    if not REVIEW_STATE_PATH.exists():
        return {"status": "idle", "latest_run_id": "", "pending_action_ids": []}
    try:
        payload = read_json(REVIEW_STATE_PATH)
    except Exception:
        return {"status": "idle", "latest_run_id": "", "pending_action_ids": []}
    if not isinstance(payload, dict):
        return {"status": "idle", "latest_run_id": "", "pending_action_ids": []}
    return payload


def save_review_state(payload: dict[str, Any]) -> None:
    ensure_dir(ARTIFACTS_ROOT)
    write_json(REVIEW_STATE_PATH, payload)


def generate_review_run_id(timestamp: datetime | None = None) -> str:
    stamp = (timestamp or now_local()).strftime("%Y%m%d-%H%M%S")
    return f"adagj-review-{stamp}"


def allocate_review_run_id(created_at: str) -> str:
    dt = parse_datetime(created_at)
    base = generate_review_run_id(dt)
    candidate = base
    index = 1
    while (REVIEWS_ROOT / dt.strftime("%Y-%m-%d") / candidate).exists():
        candidate = f"{base}-{index:02d}"
        index += 1
    return candidate


def review_run_dir_for(run_id: str, created_at: str | None = None) -> Path:
    dt = parse_datetime(created_at)
    return ensure_dir(REVIEWS_ROOT / dt.strftime("%Y-%m-%d") / run_id)


def latest_review_inventory() -> list[dict[str, Any]]:
    if not REVIEWS_ROOT.exists():
        return []
    review_dirs = sorted([path for path in REVIEWS_ROOT.glob("*/*") if path.is_dir()], key=lambda item: str(item))
    for run_dir in reversed(review_dirs):
        inventory_path = run_dir / "inventory.json"
        if not inventory_path.exists():
            continue
        payload = read_json(inventory_path)
        if isinstance(payload, dict):
            items = payload.get("skills")
            if isinstance(items, list):
                return items
    return []


def inventory_changes(current: list[dict[str, Any]], previous: list[dict[str, Any]]) -> dict[str, Any]:
    if not previous:
        return {
            "added": [],
            "removed": [],
            "delta": 0,
            "baseline_created": True,
        }
    current_names = {str(item.get("directory_name") or item["name"]) for item in current}
    previous_names = {str(item.get("directory_name") or item["name"]) for item in previous}
    added = sorted(current_names - previous_names)
    removed = sorted(previous_names - current_names)
    return {
        "added": added,
        "removed": removed,
        "delta": len(current_names) - len(previous_names),
        "baseline_created": False,
    }


def display_skill_label(item: dict[str, Any]) -> str:
    directory_name = str(item.get("directory_name") or "").strip()
    name = str(item.get("name") or "").strip()
    if directory_name and directory_name != name:
        return f"{directory_name} ({name})"
    return name


def duplicate_description_pairs(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    descriptions: dict[str, list[dict[str, Any]]] = {}
    for item in inventory:
        description = str(item.get("description") or "").strip()
        if not description:
            continue
        descriptions.setdefault(description, []).append(item)
    pairs: list[dict[str, Any]] = []
    for description, items in sorted(descriptions.items()):
        if len(items) <= 1:
            continue
        pairs.append(
            {
                "skills": sorted(display_skill_label(item) for item in items),
                "reason": "description_duplicate",
                "evidence": description,
            }
        )
    return pairs


def boundary_overlap_pairs(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    names = {item["name"] for item in inventory}
    explicit_pairs = [
        ("figma", "figma-implement-design", "总入口 vs 1:1 设计实现"),
        ("jiyao-youyao-haiyao", "jiyao-youyao-haiyao-zaiyao", "自治执行 vs 复杂多阶段执行"),
        ("knowledge-orchestrator", "notion-research-documentation", "知识库优先规划 vs Notion 研究沉淀"),
        ("knowledge-orchestrator", "notion-meeting-intelligence", "知识库优先规划 vs Notion 会议材料"),
    ]
    overlaps: list[dict[str, Any]] = []
    for left, right, reason in explicit_pairs:
        if left in names and right in names:
            overlaps.append({"skills": [left, right], "reason": reason})
    overlaps.extend(duplicate_description_pairs(inventory))
    return overlaps


def strong_clusters(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    full_stack = [item["name"] for item in inventory if item["resource_score"] == 4]
    platform_strong = [
        item["name"]
        for item in inventory
        if item["name"] in {"figma", "playwright", "spreadsheet", "slides", "speech", "cloudflare-deploy", "feishu-open-platform"}
    ]
    clusters: list[dict[str, Any]] = []
    if full_stack:
        clusters.append(
            {
                "name": "工作流完整度高",
                "skills": full_stack,
                "why": "scripts/references/assets/agents 四件套齐，闭环和证据度都更强。",
            }
        )
    if platform_strong:
        clusters.append(
            {
                "name": "平台证据型技能",
                "skills": platform_strong,
                "why": "依赖明确工具链和官方来源，调用边界清晰，实战顺手度高。",
            }
        )
    return clusters


def weak_clusters(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    agency_skills = [item["name"] for item in inventory if item["name"].startswith("agency-")]
    low_evidence = [item["name"] for item in inventory if item["resource_score"] <= 1]
    clusters: list[dict[str, Any]] = []
    if agency_skills:
        clusters.append(
            {
                "name": "人格说明型技能过多",
                "skills": agency_skills[:12],
                "skill_count": len(agency_skills),
                "why": "大量 skill 更像专家 persona，而不是有脚本、有验真的工作流 skill。",
            }
        )
    if low_evidence:
        clusters.append(
            {
                "name": "轻结构技能偏多",
                "skills": low_evidence[:12],
                "skill_count": len(low_evidence),
                "why": "references/assets 缺失较多，导致顺手度和复用度依赖记忆而不是工件。",
            }
        )
    return clusters


def missing_middle_layer_capabilities(inventory: list[dict[str, Any]]) -> list[str]:
    names = {item["name"] for item in inventory}
    missing: list[str] = []
    if "routing-playbook" not in names:
        missing.append("routing-playbook")
    if "guide-benchmark-learning" not in names:
        missing.append("guide-benchmark-learning")
    if "workflow-hardening" not in names:
        missing.append("workflow-hardening")
    if "skill-deduper" not in names:
        missing.append("skill-deduper")
    if "skill-inventory-review" not in names:
        missing.append("skill-inventory-review")
    return missing


def candidate_actions_for_review(
    inventory: list[dict[str, Any]],
    overlaps: list[dict[str, Any]],
    missing_capabilities: list[str],
) -> list[dict[str, Any]]:
    agency_count = len([item for item in inventory if item["name"].startswith("agency-")])
    duplicate_names = sorted(
        {
            skill
            for pair in overlaps
            if pair.get("reason") == "description_duplicate"
            for skill in pair.get("skills", [])
        }
    )
    actions: list[dict[str, Any]] = []
    if "routing-playbook" in missing_capabilities:
        actions.append(
            {
                "id": "A",
                "type": "新建中层 skill",
                "title": "新建 routing-playbook",
                "problem": f"现有 {len(inventory)} 个顶层 skill 缺少一个把常见任务映射成稳定组合的中层调用手册。",
                "proposed_change": "创建 routing-playbook，沉淀高频任务到 skill 组合、默认顺序、边界和验真清单。",
                "expected_gain": "显著降低调用摩擦，让 AI大管家 从会选 skill 进化到会稳定编排 skill。",
                "risk": "如果 playbook 写得过宽，会重新制造路由重叠。",
                "recommended_next_step": "先选 8 到 12 个高频任务，写成最小组合 playbook MVP。",
            }
        )
    if agency_count >= 20:
        actions.append(
            {
                "id": "B",
                "type": "workflow hardening",
                "title": "加厚高频 agency 技能",
                "problem": f"当前有 {agency_count} 个 agency 角色型 skill，很多更像 persona，而不是可验证的工作流。",
                "proposed_change": "优先把 engineering/testing/project 三簇里最常用的 5 到 8 个 role 加上 scripts、references、固定输出契约。",
                "expected_gain": "把‘会思考’升级成‘能稳定交付’，明显提升日常顺手度。",
                "risk": "如果一次加厚太多，会把 hardening 变成大范围重写。",
                "recommended_next_step": "先挑一个簇做试点，例如 agency-engineering-*。",
            }
        )
    actions.append(
        {
            "id": "C",
            "type": "去重/合并",
            "title": "处理重复和边界冲突",
            "problem": "当前已经出现重复 description 和相邻 skill 边界不够利落的问题。",
            "proposed_change": (
                "先处理 youquant-backtest / youquant-backtest-automation 这类明确重复，"
                "再为 figma / figma-implement-design、jiyao-*、knowledge-orchestrator vs notion-* 增加边界说明。"
            ),
            "expected_gain": "降低命名噪音和误路由，提升边界清晰度。",
            "risk": "如果合并过猛，可能破坏已有习惯触发词。",
            "recommended_next_step": (
                "先做一张 overlap 清单，再决定哪些合并、哪些只补边界说明。"
                if duplicate_names
                else "先补一轮边界说明，再决定是否继续收敛名称。"
            ),
        }
    )
    if len(actions) < 3:
        actions.append(
            {
                "id": "Z",
                "type": "路由修正",
                "title": "收紧 review 和高频任务的路由信号",
                "problem": "当前路由仍主要依赖关键词命中，容易在相近技能之间产生偏差。",
                "proposed_change": "为高频任务补硬路由和边界词，尤其是 review、平台研究、知识优先和复杂自治执行之间的分流。",
                "expected_gain": "减少误路由，让 AI大管家 更像真正顺手的总调度器。",
                "risk": "如果规则写得过死，会牺牲新场景的灵活性。",
                "recommended_next_step": "先从最近 10 次任务里抽取误路由样本，补最小一轮信号词和边界规则。",
            }
        )
    for index, action in enumerate(actions[:3]):
        action["id"] = chr(ord("A") + index)
    return actions[:3]


def build_review_payload(
    inventory: list[dict[str, Any]],
    *,
    created_at: str,
    run_id: str,
) -> dict[str, Any]:
    by_layer: dict[str, int] = {}
    for item in inventory:
        by_layer[item["layer"]] = by_layer.get(item["layer"], 0) + 1
    previous = latest_review_inventory()
    changes = inventory_changes(inventory, previous)
    overlaps = boundary_overlap_pairs(inventory)
    missing_capabilities = missing_middle_layer_capabilities(inventory)
    actions = candidate_actions_for_review(inventory, overlaps, missing_capabilities)
    strategy_map = build_strategy_map(load_strategy_goals(), inventory)
    return {
        "run_id": run_id,
        "created_at": created_at,
        "skills_total": len(inventory),
        "skills_by_layer": by_layer,
        "github_sources_count": len(build_github_sources(inventory)),
        "structure_changes": changes,
        "rubric": REVIEW_RUBRIC,
        "strong_clusters": strong_clusters(inventory),
        "weak_clusters": weak_clusters(inventory),
        "overlap_pairs": overlaps,
        "missing_middle_layer_capabilities": missing_capabilities,
        "candidate_actions": actions,
        "strategy_stage_theme": strategy_map["stage_theme"],
        "strategy_highest_goal": strategy_map["highest_goal"],
        "status": "awaiting_human_choice",
    }


def build_github_sources(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in inventory:
        repo = str(item.get("source_repo") or "").strip()
        if not repo:
            continue
        entry = grouped.setdefault(
            repo,
            {
                "repo": repo,
                "evidence_types": set(),
                "skill_names": [],
                "representative_skills": [],
            },
        )
        entry["evidence_types"].add(str(item.get("source_type") or "local-native"))
        entry["skill_names"].append(item["name"])
        if len(entry["representative_skills"]) < 6:
            entry["representative_skills"].append(item["name"])

    results: list[dict[str, Any]] = []
    for repo, entry in sorted(grouped.items()):
        count = len(entry["skill_names"])
        recommend_back_publish = repo.startswith("moonstachain/")
        evaluation = (
            "大规模 persona 来源库，适合作为角色母体，不适合作为本地闭环工作的直接替代。"
            if repo == "msitarzewski/agency-agents"
            else "本地原生演化仓库，值得继续沉淀方法与工作流。"
            if recommend_back_publish
            else "上游来源可作为 benchmark 或导入证据。"
        )
        results.append(
            {
                "repo": repo,
                "evidence_types": sorted(entry["evidence_types"]),
                "mapped_skill_count": count,
                "representative_skills": sorted(entry["representative_skills"]),
                "evaluation": evaluation,
                "suggest_back_publish": recommend_back_publish,
            }
        )
    return results


def review_summary_text(review: dict[str, Any]) -> str:
    strong = review["strong_clusters"][0]["name"] if review["strong_clusters"] else "none"
    weak = review["weak_clusters"][0]["name"] if review["weak_clusters"] else "none"
    missing = " / ".join(review["missing_middle_layer_capabilities"][:3]) or "none"
    return (
        f"本轮共盘点 {review['skills_total']} 个顶层 skill；"
        f"当前最强集群是 {strong}，最弱集群是 {weak}；"
        f"最值得优先补的中层能力是 {missing}。"
    )


def review_findings(review: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    usage_counts = recent_selected_skill_counts(limit=80)
    for cluster in review.get("strong_clusters", []):
        findings.append(
            {
                "type": "strong_cluster",
                "title": cluster["name"],
                "object_1": " | ".join(cluster.get("skills", [])[:6]),
                "object_2": "",
                "conclusion": cluster.get("why", ""),
                "suggested_rule": "继续加厚 playbook、失败样例和跨 skill 组合说明。",
            }
        )
    for cluster in review.get("weak_clusters", []):
        findings.append(
            {
                "type": "weak_cluster",
                "title": cluster["name"],
                "object_1": " | ".join(cluster.get("skills", [])[:6]),
                "object_2": "",
                "conclusion": cluster.get("why", ""),
                "suggested_rule": "优先 hardening 高频项，不做大范围同时重写。",
            }
        )
    if "guide-benchmark-learning" in {item["name"] for item in build_review_inventory()}:
        guide_usage = usage_counts.get("guide-benchmark-learning", 0)
        if guide_usage == 0:
            findings.append(
                {
                    "type": "weak_cluster",
                    "title": "说明书优先学习层未形成使用习惯",
                    "object_1": "guide-benchmark-learning",
                    "object_2": "",
                    "conclusion": "本地已经安装 manual-first learning skill，但最近运行记录还没有把它真正用起来。",
                    "suggested_rule": "遇到陌生 API、平台、方法或新流程时，先走 guide-benchmark-learning 再决定执行链。",
                }
            )
    for pair in review.get("overlap_pairs", []):
        skills = pair.get("skills", [])
        findings.append(
            {
                "type": "overlap_pair",
                "title": " / ".join(skills),
                "object_1": skills[0] if skills else "",
                "object_2": skills[1] if len(skills) > 1 else "",
                "conclusion": pair.get("reason", ""),
                "suggested_rule": "补边界说明，确认是收敛命名还是仅修正文案。",
            }
        )
    for missing in review.get("missing_middle_layer_capabilities", []):
        findings.append(
            {
                "type": "missing_middle_layer",
                "title": missing,
                "object_1": missing,
                "object_2": "",
                "conclusion": f"当前仍缺少 {missing} 这一类中层能力。",
                "suggested_rule": "只在高频场景成立后再补，不追求一次补齐所有空位。",
            }
        )
    findings.extend(
        [
            {
                "type": "best_path",
                "title": "skill 训练主路径",
                "object_1": "ai-da-guan-jia",
                "object_2": "skill-trainer-recursive -> skill-creator",
                "conclusion": "训练 skill 应先过方法训练，再做脚手架落地。",
                "suggested_rule": "不要因为 prompt 出现 skill 一词就直接吸到 skill-creator。",
            },
            {
                "type": "misroute_risk",
                "title": "复盘误吸到 self-evolution-max",
                "object_1": "ai-da-guan-jia review",
                "object_2": "self-evolution-max",
                "conclusion": "系统盘点与能力地图应优先走 review path，而不是多轮迭代实验路径。",
                "suggested_rule": "出现 盘点/能力地图/去重/skill review 时先走 review-skills。",
            },
        ]
    )
    return findings


def default_strategic_goals() -> list[dict[str, Any]]:
    return [
        {
            "id": "G1",
            "title": "治理操作系统化",
            "theme": "从技能集合升级为可治理的 AI operating system",
            "success_definition": "任何任务、skill、initiative 都能被映射到统一 taxonomy 和治理视图。",
            "priority": 1,
        },
        {
            "id": "G2",
            "title": "受控自治与提案推进",
            "theme": "先做到高质量提案自治，而不是全自动执行",
            "success_definition": "AI大管家 能围绕战略目标持续生成 thread proposals、initiative decomposition 和 skill 招募建议。",
            "priority": 2,
        },
        {
            "id": "G3",
            "title": "AI 组织激励系统",
            "theme": "奖励治理质量、低失真和可复用贡献",
            "success_definition": "agent/skill 的路由优先级、自治权限和资源额度与 scorecard 挂钩。",
            "priority": 3,
        },
    ]


def load_strategy_goals() -> list[dict[str, Any]]:
    ensure_dir(STRATEGY_CURRENT_ROOT)
    path = STRATEGY_CURRENT_ROOT / "strategic-goals.json"
    if path.exists():
        payload = read_json(path)
        if isinstance(payload, list) and payload:
            return [item for item in payload if isinstance(item, dict)]
    goals = default_strategic_goals()
    write_json(path, goals)
    return goals


def strategic_goal_for_item(item: dict[str, Any]) -> str:
    cluster = str(item.get("cluster") or "")
    name = str(item.get("name") or "")
    if cluster == "AI大管家治理簇" or name.startswith(("ai-", "jiyao-", "skill-")):
        return "G1"
    if name in {"agency-agents-orchestrator", "knowledge-orchestrator", "routing-playbook"}:
        return "G2"
    return "G3" if name.startswith("agency-") else "G1"


def strategic_goal_for_run(record: dict[str, Any]) -> str:
    task = normalize_prompt(str(record.get("task_text") or ""))
    if any(word in task for word in ["治理", "taxonomy", "github", "命名", "盘点", "review"]):
        return "G1"
    if any(word in task for word in ["自治", "thread", "initiative", "招兵买马", "strategy"]):
        return "G2"
    if any(word in task for word in ["激励", "scorecard", "提权", "降权", "自治权", "资源权"]):
        return "G3"
    return "G1"


def strategic_gap_candidates(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    names = {item["name"] for item in inventory}
    candidates: list[dict[str, Any]] = []
    wanted = [
        ("workflow-hardening", "G1", "治理操作系统化", "缺少把高频 persona skill 加厚为可验证工作流的中层能力。"),
        ("skill-deduper", "G1", "治理操作系统化", "缺少专门负责重复命名、边界冲突、合并策略的器官。"),
        ("strategy-governor", "G2", "受控自治与提案推进", "缺少围绕战略目标做 initiative 和 thread proposal 的常驻器官。"),
        ("agent-incentive-governor", "G3", "AI 组织激励系统", "缺少 scorecard、提权、降权和资源杠杆的治理器官。"),
    ]
    for name, goal_id, goal_title, reason in wanted:
        if name not in names:
            candidates.append(
                {
                    "candidate_skill": name,
                    "goal_id": goal_id,
                    "goal_title": goal_title,
                    "reason": reason,
                    "action": "recruit_or_incubate",
                }
            )
    return candidates


def build_strategy_map(goals: list[dict[str, Any]], inventory: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"G1": 0, "G2": 0, "G3": 0}
    for item in inventory:
        counts[strategic_goal_for_item(item)] = counts.get(strategic_goal_for_item(item), 0) + 1
    return {
        "generated_at": iso_now(),
        "stage_theme": "从强执行体升级为受控自治的 AI 治理系统",
        "highest_goal": "让 AI大管家 从任务路由器进化成战略提案者 + 组织编排者 + 治理审计者。",
        "goals": goals,
        "skill_distribution_by_goal": counts,
    }


def build_initiative_registry(goals: list[dict[str, Any]], inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    names = {item["name"] for item in inventory}
    return [
        {
            "id": "I-GOV-001",
            "goal_id": "G1",
            "title": "统一治理视图",
            "status": "active",
            "summary": "把 strategic goals、initiative registry、active threads、taxonomy 统一成一个治理面板。",
            "required_capabilities": ["ai-da-guan-jia", "routing-playbook"],
            "gap_level": "medium" if "routing-playbook" not in names else "low",
        },
        {
            "id": "I-AUTO-001",
            "goal_id": "G2",
            "title": "提案自治引擎",
            "status": "active",
            "summary": "围绕战略目标自动形成 initiative、thread、skill gap 和招募建议。",
            "required_capabilities": ["ai-da-guan-jia", "strategy-governor", "skill-trainer-recursive"],
            "gap_level": "high" if "strategy-governor" not in names else "medium",
        },
        {
            "id": "I-INC-001",
            "goal_id": "G3",
            "title": "AI 激励评分体系",
            "status": "active",
            "summary": "把路由信用、自治层级、资源权和写回权绑定到 scorecard。",
            "required_capabilities": ["ai-da-guan-jia", "agent-incentive-governor"],
            "gap_level": "high" if "agent-incentive-governor" not in names else "medium",
        },
    ]


def build_active_threads(goals: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    threads: list[dict[str, Any]] = []
    for record in iter_evolution_records(limit=limit):
        verification = normalize_verification_result(record.get("verification_result"))
        status = str(verification.get("status") or "")
        open_questions = normalize_list(verification.get("open_questions"))
        thread_status = "archived" if status in {"completed", "done", "passed", "success"} and not open_questions else "active"
        threads.append(
            {
                "run_id": str(record.get("run_id") or ""),
                "task_text": str(record.get("task_text") or ""),
                "goal_id": strategic_goal_for_run(record),
                "status": thread_status,
                "selected_skills": normalize_list(record.get("skills_selected")),
                "open_questions": open_questions,
            }
        )
    return threads


def build_skill_gap_report(
    inventory: list[dict[str, Any]],
    initiatives: list[dict[str, Any]],
    recent_runs: list[dict[str, Any]],
) -> dict[str, Any]:
    missing_middle = missing_middle_layer_capabilities(inventory)
    overlaps = boundary_overlap_pairs(inventory)
    frequently_used = recent_selected_skill_counts(limit=80)
    under_hardened = sorted(
        [
            {
                "skill": item["name"],
                "use_count": frequently_used.get(item["name"], 0),
                "resource_score": item["resource_score"],
            }
            for item in inventory
            if frequently_used.get(item["name"], 0) >= 2 and item["resource_score"] <= 1
        ],
        key=lambda item: (item["use_count"], -item["resource_score"]),
        reverse=True,
    )
    return {
        "generated_at": iso_now(),
        "missing_middle_layers": missing_middle,
        "overlap_pairs": overlaps[:10],
        "under_hardened_high_use_skills": under_hardened[:12],
        "initiative_gaps": [item for item in initiatives if item["gap_level"] != "low"],
        "summary": "优先补 strategy-governor / workflow-hardening / skill-deduper / incentive governor 这类中层器官。",
    }


def build_thread_proposals(
    goals: list[dict[str, Any]],
    initiatives: list[dict[str, Any]],
    gap_report: dict[str, Any],
) -> list[dict[str, Any]]:
    proposals = [
        {
            "id": "TP-001",
            "goal_id": "G1",
            "initiative_id": "I-GOV-001",
            "title": "建立统一治理视图与战略 review",
            "expected_gain": "让系统能回答当前战略目标、initiative、blocked threads 和 skill gap。",
            "resource_cost": "medium",
            "verification": "生成 strategy-map.json、initiative-registry.json、governance-dashboard.md，并在 daily review 中引用。",
            "required_skills": ["ai-da-guan-jia", "routing-playbook"],
            "requires_human_approval": True,
        },
        {
            "id": "TP-002",
            "goal_id": "G2",
            "initiative_id": "I-AUTO-001",
            "title": "建立提案自治引擎",
            "expected_gain": "能围绕战略目标稳定提出新线程和 skill 招募建议。",
            "resource_cost": "medium",
            "verification": "生成 3 个高质量 thread proposals，并给出复用 vs 新建判断。",
            "required_skills": ["ai-da-guan-jia", "skill-trainer-recursive"],
            "requires_human_approval": True,
        },
        {
            "id": "TP-003",
            "goal_id": "G3",
            "initiative_id": "I-INC-001",
            "title": "建立 agent scorecard 与提权机制",
            "expected_gain": "把路由优先级、自治权限和资源预算绑定到治理质量。",
            "resource_cost": "low",
            "verification": "生成 agent-scorecard.json、routing-credit.json、autonomy-tier.json。",
            "required_skills": ["ai-da-guan-jia"],
            "requires_human_approval": True,
        },
    ]
    if gap_report.get("missing_middle_layers"):
        proposals[0]["notes"] = f"当前缺口: {' | '.join(gap_report['missing_middle_layers'][:4])}"
    return proposals


def build_recruitment_candidates(gap_report: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": "RC-001",
            "candidate_skill": "strategy-governor",
            "goal_id": "G2",
            "why_now": "系统已经有 review 和 route，但还缺稳定的战略提案器官。",
            "reuse_vs_new": "new",
            "incubation_brief": "生成战略目标分解、initiative 候选、thread proposal 和招募建议。",
        },
        {
            "id": "RC-002",
            "candidate_skill": "workflow-hardening",
            "goal_id": "G1",
            "why_now": "高频 persona skill 需要向 scripts/references/output contract 加厚。",
            "reuse_vs_new": "new",
            "incubation_brief": "识别高使用低 resource_score skill，并生成 hardening brief。",
        },
        {
            "id": "RC-003",
            "candidate_skill": "agent-incentive-governor",
            "goal_id": "G3",
            "why_now": "当前还没有正式的提权/降权和路由信用治理器官。",
            "reuse_vs_new": "new",
            "incubation_brief": "根据 scorecard 生成 autonomy tier、routing credit 和 promotion/demotion 建议。",
        },
    ]


def build_agent_scorecard(inventory: list[dict[str, Any]], recent_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected_counts = recent_selected_skill_counts(limit=120)
    verification_counts: dict[str, list[dict[str, Any]]] = {}
    for record in recent_runs:
        verification = normalize_verification_result(record.get("verification_result"))
        for skill in normalize_list(record.get("skills_selected")):
            verification_counts.setdefault(skill, []).append(verification)
    rows: list[dict[str, Any]] = []
    for item in inventory:
        name = item["name"]
        verifications = verification_counts.get(name, [])
        completed = len(
            [
                v for v in verifications
                if str(v.get("status") or "").strip().lower() in {"completed", "done", "passed", "success"}
            ]
        )
        evidence_total = sum(len(normalize_list(v.get("evidence"))) for v in verifications)
        open_questions_total = sum(len(normalize_list(v.get("open_questions"))) for v in verifications)
        selected_total = max(1, len(verifications))
        closure_quality = round(completed / selected_total, 2)
        verification_strength = round(evidence_total / selected_total, 2)
        distortion_rate = round(open_questions_total / selected_total, 2)
        reuse_contribution = selected_counts.get(name, 0)
        strategic_alignment = 1.0 if strategic_goal_for_item(item) in {"G1", "G2", "G3"} else 0.5
        human_interruption_cost = 1.0 if "授权" in item.get("boundary", "") or "human" in item.get("boundary", "").lower() else 0.4
        rows.append(
            {
                "skill": name,
                "closure_quality": closure_quality,
                "verification_strength": verification_strength,
                "reuse_contribution": reuse_contribution,
                "distortion_rate": distortion_rate,
                "strategic_alignment": strategic_alignment,
                "human_interruption_cost": human_interruption_cost,
            }
        )
    rows.sort(key=lambda item: (item["closure_quality"], item["verification_strength"], item["reuse_contribution"]), reverse=True)
    return rows


def build_routing_credit(scorecard: list[dict[str, Any]]) -> list[dict[str, Any]]:
    credits: list[dict[str, Any]] = []
    for item in scorecard:
        composite = round(
            item["closure_quality"] * 40
            + item["verification_strength"] * 15
            + min(item["reuse_contribution"], 10) * 3
            + item["strategic_alignment"] * 20
            - item["distortion_rate"] * 10
            - item["human_interruption_cost"] * 8,
            2,
        )
        credits.append(
            {
                "skill": item["skill"],
                "routing_credit": composite,
                "explanation": "奖励真闭环、强验真、战略对齐和可复用贡献；惩罚高失真和高人类打扰成本。",
            }
        )
    credits.sort(key=lambda item: item["routing_credit"], reverse=True)
    return credits


def build_autonomy_tiers(scorecard: list[dict[str, Any]], routing_credit: list[dict[str, Any]]) -> list[dict[str, Any]]:
    credits = {item["skill"]: item["routing_credit"] for item in routing_credit}
    tiers: list[dict[str, Any]] = []
    for item in scorecard:
        credit = credits.get(item["skill"], 0.0)
        if credit >= 55 and item["distortion_rate"] <= 0.3:
            tier = "guarded-autonomy"
        elif credit >= 35:
            tier = "trusted-suggest"
        elif credit >= 15:
            tier = "suggest"
        else:
            tier = "observe"
        tiers.append(
            {
                "skill": item["skill"],
                "autonomy_tier": tier,
                "routing_credit": credit,
            }
        )
    tiers.sort(key=lambda item: (AUTONOMY_TIERS.index(item["autonomy_tier"]), -item["routing_credit"]))
    return tiers


def render_governance_dashboard(
    strategy_map: dict[str, Any],
    initiatives: list[dict[str, Any]],
    active_threads: list[dict[str, Any]],
    gap_report: dict[str, Any],
    thread_proposals: list[dict[str, Any]],
    scorecard: list[dict[str, Any]],
) -> str:
    lines = [
        "# Governance Dashboard",
        "",
        f"- Stage Theme: {strategy_map['stage_theme']}",
        f"- Highest Goal: {strategy_map['highest_goal']}",
        "",
        "## Strategic Goals",
        "",
    ]
    for goal in strategy_map["goals"]:
        lines.append(f"- {goal['id']}: {goal['title']} :: {goal['theme']}")
    lines.extend(
        [
            "",
            "## Active Initiatives",
            "",
        ]
    )
    for item in initiatives:
        lines.append(f"- {item['id']} [{item['goal_id']}] {item['title']} :: {item['status']} :: gap={item['gap_level']}")
    lines.extend(
        [
            "",
            "## Active Threads",
            "",
            f"- Total tracked threads: {len(active_threads)}",
            f"- Archived: {len([item for item in active_threads if item['status'] == 'archived'])}",
            f"- Active: {len([item for item in active_threads if item['status'] != 'archived'])}",
            "",
            "## Current Gaps",
            "",
            f"- Missing middle layers: {' | '.join(gap_report['missing_middle_layers']) or 'none'}",
            f"- Under-hardened high-use skills: {' | '.join(item['skill'] for item in gap_report['under_hardened_high_use_skills'][:6]) or 'none'}",
            "",
            "## Proposal Queue",
            "",
        ]
    )
    for item in thread_proposals:
        lines.append(f"- {item['id']} [{item['goal_id']}] {item['title']} :: approval={item['requires_human_approval']}")
    lines.extend(
        [
            "",
            "## Top Routing Credit",
            "",
        ]
    )
    for item in scorecard[:10]:
        lines.append(
            f"- {item['skill']}: closure={item['closure_quality']} verify={item['verification_strength']} reuse={item['reuse_contribution']} distortion={item['distortion_rate']}"
        )
    lines.append("")
    return "\n".join(lines)


def render_org_taxonomy(inventory: list[dict[str, Any]]) -> str:
    by_cluster: dict[str, list[str]] = {}
    for item in inventory:
        by_cluster.setdefault(str(item["cluster"]), []).append(item["name"])
    lines = ["# Org Taxonomy", "", "## Clusters", ""]
    for cluster, names in sorted(by_cluster.items()):
        lines.append(f"- {cluster}: {' | '.join(sorted(names)[:12])}")
    lines.extend(
        [
            "",
            "## Governance Axes",
            "",
            "- Goal Axis: G1 治理 / G2 受控自治 / G3 激励系统",
            "- Skill Axis: governance / platform / workflow / persona",
            "- Lifecycle Axis: active / archived / overlap-risk / under-hardened",
            "",
        ]
    )
    return "\n".join(lines)


def render_governance_penalty_rules() -> str:
    return "\n".join(
        [
            "# Governance Penalty Rules",
            "",
            "- Penalize pseudo-completion more than slow completion.",
            "- Penalize high human interruption when the task did not require a human boundary.",
            "- Penalize repeated overlap creation and redundant new-skill proposals.",
            "- Penalize high throughput without evidence, closure, or reusable artifacts.",
            "",
        ]
    )


def render_promotion_demotion_policy() -> str:
    return "\n".join(
        [
            "# Promotion Demotion Policy",
            "",
            "- Promote a skill when closure quality stays high, distortion stays low, and reuse contribution is proven.",
            "- Demote a skill when it creates repeated open questions, overlap, or unnecessary human interruption.",
            "- Promotion changes routing priority, autonomy tier, and writeback trust, not the skill's identity.",
            "",
        ]
    )


def write_strategy_operating_system(
    goals: list[dict[str, Any]] | None = None,
    *,
    inventory: list[dict[str, Any]] | None = None,
    recent_runs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ensure_dir(STRATEGY_CURRENT_ROOT)
    inventory = inventory or build_review_inventory()
    recent_runs = recent_runs or iter_evolution_records(limit=120)
    goals = goals or load_strategy_goals()
    strategy_map = build_strategy_map(goals, inventory)
    initiatives = build_initiative_registry(goals, inventory)
    active_threads = build_active_threads(goals, limit=30)
    gap_report = build_skill_gap_report(inventory, initiatives, recent_runs)
    thread_proposals = build_thread_proposals(goals, initiatives, gap_report)
    recruitment = build_recruitment_candidates(gap_report)
    scorecard = build_agent_scorecard(inventory, recent_runs)
    routing_credit = build_routing_credit(scorecard)
    autonomy_tier = build_autonomy_tiers(scorecard, routing_credit)
    initiative_brief = initiatives[0] if initiatives else {}

    write_json(STRATEGY_CURRENT_ROOT / "strategic-goals.json", goals)
    write_json(STRATEGY_CURRENT_ROOT / "strategy-map.json", strategy_map)
    write_json(STRATEGY_CURRENT_ROOT / "initiative-registry.json", initiatives)
    write_json(STRATEGY_CURRENT_ROOT / "active-threads.json", active_threads)
    write_json(STRATEGY_CURRENT_ROOT / "initiative-brief.json", initiative_brief)
    write_json(STRATEGY_CURRENT_ROOT / "thread-proposal.json", thread_proposals)
    write_json(STRATEGY_CURRENT_ROOT / "skill-gap-report.json", gap_report)
    write_json(STRATEGY_CURRENT_ROOT / "recruitment-candidate.json", recruitment)
    write_json(STRATEGY_CURRENT_ROOT / "agent-scorecard.json", scorecard)
    write_json(STRATEGY_CURRENT_ROOT / "routing-credit.json", routing_credit)
    write_json(STRATEGY_CURRENT_ROOT / "autonomy-tier.json", autonomy_tier)
    (STRATEGY_CURRENT_ROOT / "governance-dashboard.md").write_text(
        render_governance_dashboard(strategy_map, initiatives, active_threads, gap_report, thread_proposals, scorecard),
        encoding="utf-8",
    )
    (STRATEGY_CURRENT_ROOT / "org-taxonomy.md").write_text(render_org_taxonomy(inventory), encoding="utf-8")
    (STRATEGY_CURRENT_ROOT / "governance-penalty-rules.md").write_text(render_governance_penalty_rules(), encoding="utf-8")
    (STRATEGY_CURRENT_ROOT / "promotion-demotion-policy.md").write_text(render_promotion_demotion_policy(), encoding="utf-8")
    (STRATEGY_CURRENT_ROOT / "strategic-proposal.md").write_text(
        "\n".join(
            [
                "# Strategic Proposal",
                "",
                "## Current Recommendation",
                "",
                "先做治理底座，再做提案自治，最后做激励制度化。",
                "",
                f"- Highest gap: {' | '.join(gap_report['missing_middle_layers'][:3]) or 'none'}",
                f"- First initiative: {initiative_brief.get('title') or 'none'}",
                f"- First thread proposal: {thread_proposals[0]['title'] if thread_proposals else 'none'}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {
        "strategy_map": strategy_map,
        "initiatives": initiatives,
        "active_threads": active_threads,
        "gap_report": gap_report,
        "thread_proposals": thread_proposals,
        "recruitment": recruitment,
        "scorecard": scorecard,
        "routing_credit": routing_credit,
        "autonomy_tier": autonomy_tier,
    }


def review_artifact_paths(run_dir: Path) -> dict[str, str]:
    return {
        "review_md_path": str((run_dir / "review.md").resolve()),
        "review_json_path": str((run_dir / "review.json").resolve()),
        "inventory_json_path": str((run_dir / "inventory.json").resolve()),
        "action_candidates_json_path": str((run_dir / "action-candidates.json").resolve()),
        "github_sources_json_path": str((run_dir / "github-sources.json").resolve()),
        "findings_json_path": str((run_dir / "findings.json").resolve()),
        "feishu_sync_bundle_path": str((run_dir / "feishu-sync-bundle.json").resolve()),
        "sync_result_path": str((run_dir / "sync-result.json").resolve()),
        "strategy_map_path": str((STRATEGY_CURRENT_ROOT / "strategy-map.json").resolve()),
        "initiative_registry_path": str((STRATEGY_CURRENT_ROOT / "initiative-registry.json").resolve()),
        "active_threads_path": str((STRATEGY_CURRENT_ROOT / "active-threads.json").resolve()),
        "governance_dashboard_path": str((STRATEGY_CURRENT_ROOT / "governance-dashboard.md").resolve()),
    }


def build_review_sync_bundle(
    review: dict[str, Any],
    inventory: list[dict[str, Any]],
    github_sources: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    *,
    run_dir: Path,
) -> dict[str, Any]:
    artifact_paths = review_artifact_paths(run_dir)
    selected_action_id = str(review.get("selected_action_id") or "")
    review_status = str(review.get("status") or "awaiting_human_choice")
    actions = []
    for action in review["candidate_actions"]:
        actions.append(
            {
                "Action Key": f"{review['run_id']}::{action['id']}",
                "Review ID": review["run_id"],
                "动作ID": action["id"],
                "动作类型": action["type"],
                "标题": action["title"],
                "问题": action["problem"],
                "建议改动": action["proposed_change"],
                "预期收益": action["expected_gain"],
                "风险": action["risk"],
                "下一步建议": action["recommended_next_step"],
                "是否被选中": "是" if selected_action_id == action["id"] else "否",
                "是否已完成": "是" if review_status == "resolved" and selected_action_id == action["id"] else "否",
            }
        )

    snapshot_rows = []
    for item in inventory:
        snapshot_key = str(item.get("directory_name") or item["name"])
        snapshot_rows.append(
            {
                "Snapshot ID": f"{review['run_id']}::{snapshot_key}",
                "Review ID": review["run_id"],
                "Skill 名": display_skill_label(item),
                "主层级": item["layer"],
                "簇": item["cluster"],
                "类型": item["type"],
                "资源完整度": item["resource_completeness"],
                "有无 scripts": "是" if item["resources"]["scripts"] else "否",
                "有无 references": "是" if item["resources"]["references"] else "否",
                "GitHub来源": item["source_repo"],
                "来源类型": item["source_type"],
                "顺手度判断": item["ease_of_use_judgment"],
                "边界备注": item["boundary_note"],
            }
        )

    finding_rows = []
    for finding in findings:
        slug = re.sub(r"[^a-z0-9]+", "-", finding["title"].lower()).strip("-")
        if not slug:
            slug = hashlib.sha1(finding["title"].encode("utf-8")).hexdigest()[:10]
        finding_rows.append(
            {
                "Finding ID": f"{review['run_id']}::{finding['type']}::{slug}",
                "Review ID": review["run_id"],
                "发现类型": finding["type"],
                "标题": finding["title"],
                "对象1": finding["object_1"],
                "对象2": finding["object_2"],
                "结论": finding["conclusion"],
                "建议规则": finding["suggested_rule"],
            }
        )

    github_rows = []
    for source in github_sources:
        github_rows.append(
            {
                "Source Key": f"{review['run_id']}::{source['repo']}",
                "Review ID": review["run_id"],
                "仓库": source["repo"],
                "证据类型": " | ".join(source["evidence_types"]),
                "本地映射 skill 数": str(source["mapped_skill_count"]),
                "代表 skill": " | ".join(source["representative_skills"]),
                "评价": source["evaluation"],
                "是否建议反向沉淀": "是" if source["suggest_back_publish"] else "否",
            }
        )

    batch_row = {
        "Review ID": review["run_id"],
        "日期": parse_datetime(review["created_at"]).strftime("%Y-%m-%d"),
        "创建时间": review["created_at"],
        "状态": review_status,
        "本地技能数": str(review["skills_total"]),
        "GitHub来源数": str(len(github_sources)),
        "层级分布": json.dumps(review["skills_by_layer"], ensure_ascii=False),
        "总评摘要": review_summary_text(review),
        "最强区块": " | ".join(cluster["name"] for cluster in review["strong_clusters"]) or "none",
        "最弱区块": " | ".join(cluster["name"] for cluster in review["weak_clusters"]) or "none",
        "中层缺口": " | ".join(review["missing_middle_layer_capabilities"]) or "none",
        "战略主题": str(review.get("strategy_stage_theme") or ""),
        "最高目标": str(review.get("strategy_highest_goal") or ""),
        "推荐动作": " | ".join(f"{action['id']}: {action['title']}" for action in review["candidate_actions"]),
        "已选动作": selected_action_id or "",
        "review.md路径": artifact_paths["review_md_path"],
        "review.json路径": artifact_paths["review_json_path"],
        "strategy-map路径": artifact_paths["strategy_map_path"],
        "initiative-registry路径": artifact_paths["initiative_registry_path"],
    }
    if review.get("resolved_at"):
        batch_row["resolved_at"] = str(review["resolved_at"])

    return {
        "generated_at": iso_now(),
        "run_id": review["run_id"],
        "skills_total": review["skills_total"],
        "github_sources_count": len(github_sources),
        "summary": review_summary_text(review),
        "tables": {
            "复盘批次": [batch_row],
            "技能清单快照": snapshot_rows,
            "候选进化动作": actions,
            "关键发现": finding_rows,
            "GitHub来源": github_rows,
        },
    }


def write_review_materials(
    run_dir: Path,
    *,
    inventory_payload: dict[str, Any],
    review: dict[str, Any],
) -> dict[str, Any]:
    strategy_bundle = write_strategy_operating_system(inventory=inventory_payload["skills"])
    github_sources = build_github_sources(inventory_payload["skills"])
    findings = review_findings(review)
    bundle = build_review_sync_bundle(
        review,
        inventory_payload["skills"],
        github_sources,
        findings,
        run_dir=run_dir,
    )
    write_json(run_dir / "inventory.json", inventory_payload)
    write_json(run_dir / "review.json", review)
    write_json(run_dir / "action-candidates.json", review["candidate_actions"])
    write_json(run_dir / "github-sources.json", github_sources)
    write_json(run_dir / "findings.json", findings)
    write_json(run_dir / "feishu-sync-bundle.json", bundle)
    (run_dir / "review.md").write_text(render_review_markdown(review), encoding="utf-8")
    return {"github_sources": github_sources, "findings": findings, "bundle": bundle, "strategy_bundle": strategy_bundle}


def render_review_markdown(review: dict[str, Any]) -> str:
    changes = review["structure_changes"]
    strong_names = [cluster["name"] for cluster in review["strong_clusters"]]
    weak_names = [cluster["name"] for cluster in review["weak_clusters"]]
    overlap_preview = [
        f"{' / '.join(item['skills'])}: {item['reason']}"
        for item in review["overlap_pairs"][:5]
    ]
    lines = [
        "# Daily Skill Review",
        "",
        "## 今日结构变化",
        "",
        f"- 顶层 skill 总数: {review['skills_total']}",
        f"- GitHub 来源数: {review.get('github_sources_count', 0)}",
        f"- 分层统计: {json.dumps(review['skills_by_layer'], ensure_ascii=False)}",
        (
            "- 这是第一轮 review，后续才会开始比较新增/移除。"
            if changes.get("baseline_created")
            else f"- 新增: {', '.join(changes['added'][:10]) or 'none'}"
        ),
        (
            ""
            if changes.get("baseline_created")
            else f"- 移除: {', '.join(changes['removed'][:10]) or 'none'}"
        ),
        "",
        "## 当前最值得关注的问题",
        "",
        f"- 当前最强集群: {' | '.join(strong_names) or 'none'}",
        f"- 当前最弱集群: {' | '.join(weak_names) or 'none'}",
        f"- 主要重叠: {' | '.join(overlap_preview) or 'none'}",
        f"- 缺失的中层能力: {' | '.join(review['missing_middle_layer_capabilities']) or 'none'}",
        f"- 战略主题: {review.get('strategy_stage_theme') or 'none'}",
        f"- 当前最高目标: {review.get('strategy_highest_goal') or 'none'}",
        "",
        "## 3 个候选进化动作",
        "",
    ]
    for action in review["candidate_actions"]:
        lines.extend(
            [
                f"### {action['id']}. {action['title']}",
                "",
                f"- 类型: {action['type']}",
                f"- 问题: {action['problem']}",
                f"- 改动: {action['proposed_change']}",
                f"- 收益: {action['expected_gain']}",
                f"- 风险: {action['risk']}",
                f"- 下一步: {action['recommended_next_step']}",
                "",
            ]
        )
    lines.extend(
        [
            "## 当前等待你做的选择",
            "",
            "请用户回复 `A` / `B` / `C` 之一；在你选择之前，不开新一轮每日盘点。",
            "",
        ]
    )
    return "\n".join(lines)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_prompt(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = [value]
    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def detect_signals(prompt: str) -> dict[str, bool]:
    text = normalize_prompt(prompt)
    manual_first_learning = any(
        phrase in text
        for phrase in [
            "学习",
            "入门",
            "先读",
            "官方文档",
            "说明书",
            "攻略",
            "教程",
            "最佳实践",
            "对标",
            "benchmark",
            "best practice",
            "api 文档",
            "manual",
            "guide",
        ]
    )
    openai_learning = any(
        phrase in text
        for phrase in [
            "openai",
            "chatgpt",
            "responses api",
            "agents sdk",
            "apps sdk",
            "realtime api",
            "codex",
        ]
    )
    openclaw_xhs = any(
        phrase in text
        for phrase in [
            "openclaw",
            "open claw",
            "小红书",
            "xhs",
            "爆款",
            "博主",
            "共进化",
            "图文笔记",
            "内容赛道",
        ]
    )
    skill_training = any(
        phrase in text
        for phrase in [
            "训练新技能",
            "训练一种新技能",
            "训练一个新技能",
            "训练技能",
            "训练 skill",
            "skill trainer",
            "skill training",
            "设计技能方法学",
            "训练技能的技能",
            "学会",
            "内化",
            "母题库",
        ]
    )
    if not skill_training and ("训练" in text or "train" in text) and "skill" in text:
        skill_training = True
    skill_creation = any(
        phrase in text
        for phrase in [
            "做一个 skill",
            "做一个新 skill",
            "新 skill",
            "新技能",
            "训练新技能",
            "训练一种新技能",
            "训练一个新技能",
            "训练 skill",
            "训练一个 skill",
            "打造一个 skill",
            "封装成 skill",
            "做个 skill",
            "create skill",
            "new skill",
            "update skill",
            "更新 skill",
            "修改 skill",
            "skill.md",
        ]
    )
    skill_inventory_review = any(
        phrase in text
        for phrase in [
            "盘点",
            "能力地图",
            "评估",
            "审计",
            "去重",
            "skill review",
            "inventory review",
            "skill inventory",
        ]
    )
    if skill_inventory_review:
        skill_creation = False
        skill_training = False
    knowledge_first = (
        "知识库" in text
        or "knowledge base" in text
        or "notebooklm" in text
        or ("先问" in text and ("知识库" in text or "资料库" in text))
    )
    feishu_reference = any(
        phrase in text
        for phrase in ["飞书", "feishu", "多维表", "bitable", "wiki", "base"]
    )
    feishu_action = any(
        phrase in text
        for phrase in ["同步", "回写", "写入", "读取", "抓取", "打开", "新建表", "upsert", "sync", "mirror"]
    )
    feishu = feishu_reference and feishu_action
    evolution = any(
        phrase in text
        for phrase in ["迭代", "进化", "feedback", "mvp", "复盘", "self-evolution"]
    )
    multi_agent = any(
        phrase in text
        for phrase in ["multi-agent", "orchestrator", "pipeline", "qa", "多 agent", "多角色"]
    )
    autonomy = any(
        phrase in text
        for phrase in [
            "少打扰",
            "低打扰",
            "别老问",
            "自己搞定",
            "端到端",
            "end-to-end",
            "minimal interruption",
        ]
    )
    metacognition = any(
        phrase in text
        for phrase in ["元认知", "失真", "假完成", "边界", "judgment", "distortion"]
    )
    hard_boundary = any(
        phrase in text
        for phrase in ["授权", "登录", "login", "payment", "支付", "发布", "删除", "审批", "approval"]
    )
    return {
        "manual_first_learning": manual_first_learning,
        "openai_learning": openai_learning,
        "openclaw_xhs": openclaw_xhs,
        "skill_training": skill_training,
        "skill_creation": skill_creation,
        "skill_inventory_review": skill_inventory_review,
        "knowledge_first": knowledge_first,
        "feishu": feishu,
        "evolution": evolution,
        "multi_agent": multi_agent,
        "autonomy": autonomy,
        "metacognition": metacognition,
        "hard_boundary": hard_boundary,
    }


def explicit_mentions(prompt: str, skill_names: list[str]) -> list[str]:
    text = normalize_prompt(prompt)
    mentioned: list[str] = []
    for name in skill_names:
        if f"${name}" in text or name in text:
            mentioned.append(name)
    return mentioned


def verification_targets(signals: dict[str, bool]) -> list[str]:
    targets: list[str] = []
    if signals["manual_first_learning"]:
        targets.append(
            "Need source-map.json, benchmark-grid.md, learning-handbook.md, execution-readiness.md, and an explicit source-of-truth versus reference-guide split before execution."
        )
    if signals["skill_inventory_review"]:
        targets.append(
            "Need correct top-level skill counting, explicit exclusion of artifacts/**, a structured review summary, and exactly 3 candidate evolution actions."
        )
    if signals["openclaw_xhs"]:
        targets.append(
            "Need account positioning, topic hooks, note structure, evidence requirements, and viral logic before the OpenClaw Xiaohongshu strategy can be called complete."
        )
    if signals["skill_training"]:
        targets.append(
            "Need intent-canvas.json, first_principles.md, benchmark-map.json, candidate-skill-spec.md, and eval-report.json before the run can be called trained."
        )
    if signals["skill_creation"]:
        targets.append("Need SKILL.md, agents/openai.yaml, required resources, and validator success.")
    if signals["knowledge_first"]:
        targets.append("Need raw knowledge answers preserved before synthesis or planning.")
    if signals["feishu"]:
        targets.append("Need local canonical log and a Feishu dry-run preview before any apply.")
    if not targets:
        targets.append("Need an artifact check plus a goal check before reporting completion.")
    return targets


def score_candidate(
    prompt: str,
    skill: dict[str, Any],
    signals: dict[str, bool],
    mentioned: list[str],
) -> dict[str, Any]:
    text = normalize_prompt(prompt)
    name = skill["name"]
    profile = CORE_PROFILES.get(name)
    keywords = [kw.lower() for kw in (profile.keywords if profile else [name])]
    hits = [kw for kw in keywords if kw and kw in text]
    explicit_bonus = 4 if name in mentioned else 0
    special_bonus = 0
    if name == "openclaw-xhs-coevolution-lab" and signals["openclaw_xhs"]:
        special_bonus = 4
    if name == "ai-da-guan-jia" and signals["skill_inventory_review"]:
        special_bonus = 5
    if name == "skill-trainer-recursive" and signals["skill_training"]:
        special_bonus = 4
    if name == "guide-benchmark-learning" and signals["manual_first_learning"]:
        special_bonus = 5
    if name == "openai-docs" and signals["manual_first_learning"] and signals["openai_learning"]:
        special_bonus = 4
    if name == "skill-creator" and signals["skill_creation"]:
        special_bonus = 4
    if name == "knowledge-orchestrator" and signals["knowledge_first"]:
        special_bonus = 4
    if name == "feishu-bitable-bridge" and signals["feishu"]:
        special_bonus = 4
    if name == "self-evolution-max" and signals["evolution"]:
        special_bonus = 3
    if name == "agency-agents-orchestrator" and signals["multi_agent"]:
        special_bonus = 3
    if name == "jiyao-youyao-haiyao" and signals["autonomy"]:
        special_bonus = 3
    if name == "ai-metacognitive-core" and signals["metacognition"]:
        special_bonus = 3
    task_fit = min(5, len(hits) + explicit_bonus + special_bonus)
    if signals["skill_inventory_review"] and name in {"skill-creator", "self-evolution-max"}:
        task_fit = 0
    if task_fit == 0 and name == "jiyao-youyao-haiyao" and not any(signals.values()):
        task_fit = 1

    verification_score = profile.verification_strength if profile else 2
    cost_score = profile.cost_efficiency if profile else 2
    auth_reuse_score = profile.auth_reuse if profile else 1
    complexity_penalty = profile.complexity_penalty if profile else 2
    total = (
        task_fit * 10000
        + verification_score * 100
        + cost_score * 10
        + auth_reuse_score
        - complexity_penalty
    )
    if hits:
        rationale = f"Matched signals: {', '.join(hits[:4])}"
    elif name in mentioned:
        rationale = "Explicitly named in the prompt."
    elif task_fit > 0:
        rationale = "Selected through a hard routing rule."
    else:
        rationale = "No strong match signal."

    return {
        "name": name,
        "description": skill["description"],
        "path": skill["path"],
        "is_core": skill["is_core"],
        "task_fit_score": task_fit,
        "verification_score": verification_score,
        "cost_score": cost_score,
        "auth_reuse_score": auth_reuse_score,
        "complexity_penalty": complexity_penalty,
        "total_score": total,
        "rationale": rationale,
    }


def choose_skills(
    prompt: str,
    ranked: list[dict[str, Any]],
    signals: dict[str, bool],
    mentioned: list[str],
) -> tuple[list[str], list[str]]:
    candidate_names = [item["name"] for item in ranked]
    selected: list[str] = []
    wanted: list[str] = []

    wanted.extend(mentioned)
    if signals["manual_first_learning"]:
        wanted.append("guide-benchmark-learning")
        if signals["openai_learning"]:
            wanted.append("openai-docs")
    if signals["skill_inventory_review"]:
        wanted.append("ai-da-guan-jia")
        wanted.append("ai-metacognitive-core")
    if signals["openclaw_xhs"]:
        wanted.append("openclaw-xhs-coevolution-lab")
    if signals["skill_training"]:
        wanted.append("skill-trainer-recursive")
    if signals["skill_creation"]:
        wanted.append("skill-creator")
    if signals["knowledge_first"]:
        wanted.append("knowledge-orchestrator")
    if signals["feishu"]:
        wanted.append("feishu-bitable-bridge")
    if signals["evolution"] and not signals["skill_inventory_review"]:
        wanted.append("self-evolution-max")
    if signals["multi_agent"]:
        wanted.append("agency-agents-orchestrator")
    if signals["autonomy"]:
        wanted.append("jiyao-youyao-haiyao")
    if signals["metacognition"]:
        wanted.append("ai-metacognitive-core")

    for name in wanted:
        if name in candidate_names and name not in selected:
            selected.append(name)

    if not selected:
        for item in ranked:
            if item["task_fit_score"] > 0:
                selected.append(item["name"])
                break

    ceiling = selection_ceiling(signals)
    for item in ranked:
        if len(selected) >= ceiling:
            break
        if item["name"] in selected or item["task_fit_score"] <= 0:
            continue
        selected.append(item["name"])

    omitted = [name for name in wanted if name not in selected]
    return selected[:ceiling], normalize_list(omitted)


def selection_ceiling(signals: dict[str, bool]) -> int:
    if signals["manual_first_learning"] and signals["skill_training"]:
        return 4
    return 3


def generate_run_id(timestamp: datetime | None = None) -> str:
    stamp = (timestamp or now_local()).strftime("%Y%m%d-%H%M%S-%f")
    return f"adagj-{stamp}"


def parse_datetime(value: str | None) -> datetime:
    if not value:
        return now_local()
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def run_dir_for(run_id: str, created_at: str | None = None) -> Path:
    dt = parse_datetime(created_at)
    return ensure_dir(RUNS_ROOT / dt.strftime("%Y-%m-%d") / run_id)


def allocate_run_id(created_at: str) -> str:
    base = generate_run_id(parse_datetime(created_at))
    candidate = base
    index = 1
    while (RUNS_ROOT / parse_datetime(created_at).strftime("%Y-%m-%d") / candidate).exists():
        candidate = f"{base}-{index:02d}"
        index += 1
    return candidate


def find_run_dir(run_id: str) -> Path:
    for date_dir in sorted(RUNS_ROOT.glob("*")):
        candidate = date_dir / run_id
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"run_id not found: {run_id}")


def determine_human_boundary(signals: dict[str, bool]) -> str:
    if signals["hard_boundary"] or signals["feishu"]:
        return "Only interrupt the user for login, authorization, payment, irreversible publish or delete, or blocked external permissions."
    return "Default to high autonomy. Do not interrupt the user unless a truly human-only boundary appears."


def determine_max_distortion(signals: dict[str, bool]) -> str:
    if signals["manual_first_learning"]:
        return "在陌生领域里直接执行，而没有先读说明书、官方文档、攻略和 benchmark。"
    if signals["openclaw_xhs"]:
        return "把 OpenClaw 共进化内容做成泛 AI 资讯或空洞教程，而没有真实实验感和可模仿张力。"
    if signals["skill_training"]:
        return "把技能训练误解成直接生成 SKILL.md，而没有先吃透战略意图、第一性原理和标杆。"
    if signals["skill_creation"]:
        return "把大管家做成口号，而不是可调用、可验证、可沉淀的 skill 包。"
    if signals["skill_inventory_review"]:
        return "把一次盘点写成抽象评论，而没有形成可执行进化动作。"
    if signals["knowledge_first"]:
        return "跳过知识库原始答案，直接凭印象规划。"
    if signals["feishu"]:
        return "把飞书镜像误当成 canonical source。"
    if signals["evolution"]:
        return "把一次复盘误写成永久制度，而没有证据证明它可复用。"
    return "把统筹误解成堆叠更多 skill，而不是选最小充分组合。"


def build_situation_map(
    prompt: str,
    selected: list[str],
    signals: dict[str, bool],
) -> dict[str, str]:
    selected_text = ", ".join(selected) if selected else "none selected yet"
    return {
        "自治判断": determine_human_boundary(signals),
        "全局最优判断": "Prefer the smallest sufficient local skill combination before heavier exploration or browser work.",
        "能力复用判断": f"First reuse: {selected_text}. Discover other local skills only when the core roster is insufficient.",
        "验真判断": "Completion requires an artifact check and a goal check; command success alone is never enough.",
        "进化判断": "Every meaningful run must produce effective patterns, wasted patterns, and candidate improvements before closure.",
        "当前最大失真": determine_max_distortion(signals),
    }


def render_situation_map(situation_map: dict[str, str], prompt: str) -> str:
    lines = ["# Situation Map", "", f"- `任务`: {prompt}", ""]
    for key in ["自治判断", "全局最优判断", "能力复用判断", "验真判断", "进化判断", "当前最大失真"]:
        lines.append(f"- `{key}`: {situation_map[key]}")
    lines.append("")
    return "\n".join(lines)


def summarize_verification(result: dict[str, Any]) -> str:
    status = str(result.get("status") or "unverified").strip()
    evidence = normalize_list(result.get("evidence"))
    if evidence:
        return f"{status}; evidence: {' | '.join(evidence)}"
    return status


def truncate_text(value: str, max_len: int) -> str:
    text = value.strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def normalize_slug_part(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return re.sub(r"-{2,}", "-", text) or "task"


def derive_prompt_keywords(prompt: str) -> list[str]:
    ascii_words = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-_/]{1,30}", prompt.lower())
    cleaned: list[str] = []
    stopwords = {
        "please",
        "help",
        "with",
        "this",
        "that",
        "task",
        "need",
        "want",
        "make",
        "build",
        "update",
        "sync",
    }
    for word in ascii_words:
        token = word.strip("-_/")
        if len(token) < 3 or token in stopwords:
            continue
        cleaned.append(normalize_slug_part(token))
    return cleaned[:4]


def infer_github_type(prompt: str) -> str:
    text = normalize_prompt(prompt)
    mapping = [
        ("debug", ["debug", "bug", "报错", "修复", "异常", "失败", "排障", "fix ci"]),
        ("review", ["review", "审查", "审计", "盘点", "评估", "复盘"]),
        ("sync", ["sync", "同步", "镜像", "回写", "归档"]),
        ("publish", ["publish", "发布", "上线", "推送", "deploy"]),
        ("implement", ["implement", "实现", "开发", "编码", "写代码", "修"]),
        ("spec", ["spec", "设计", "方案", "规划", "架构", "需求", "plan"]),
        ("research", ["research", "调研", "研究", "benchmark", "攻略", "说明书", "官方文档"]),
        ("governance", ["governance", "治理", "规范", "命名", "分类", "管理"]),
    ]
    for label, patterns in mapping:
        if any(item in text for item in patterns):
            return label
    return "implement"


def infer_github_domain(prompt: str, selected_skills: list[str]) -> str:
    text = normalize_prompt(prompt)
    if any(item in text for item in ["github", "pull request", "pr", "issue", "repo", "仓库"]):
        return "github"
    if any(item in text for item in ["飞书", "feishu", "bitable", "wiki", "lark"]):
        return "feishu"
    if any(item in text for item in ["openai", "chatgpt", "responses api", "apps sdk", "codex"]):
        return "openai"
    if any(item in text for item in ["skill", "skills", "大管家", "router", "路由", "盘点"]) or any(
        name.startswith(("ai-", "skill-")) for name in selected_skills
    ):
        return "skill-system"
    if any(item in text for item in ["内容", "选题", "小红书", "公众号", "文章", "publish"]):
        return "content"
    if any(item in text for item in ["dataset", "数据", "csv", "excel", "spreadsheet", "分析"]):
        return "data"
    return "ops"


def infer_github_artifact(prompt: str, selected_skills: list[str]) -> str:
    text = normalize_prompt(prompt)
    if "skill" in text or any(name.startswith(("ai-", "skill-")) for name in selected_skills):
        return "skill"
    if any(item in text for item in ["workflow", "流程", "route", "router", "governance"]):
        return "workflow"
    if any(item in text for item in ["doc", "文档", "plan", "spec", "方案", "readme"]):
        return "doc"
    if any(item in text for item in ["dataset", "表", "csv", "excel", "jsonl"]):
        return "dataset"
    if any(item in text for item in ["api", "integration", "mcp", "bridge", "sync", "feishu"]):
        return "integration"
    if any(item in text for item in ["report", "summary", "brief", "review"]):
        return "report"
    return "code"


def should_skip_github_management(prompt: str, signals: dict[str, bool]) -> tuple[bool, str]:
    normalized = normalize_prompt(prompt)
    compact = normalized.replace(" ", "")
    if compact in GITHUB_SKIP_PATTERNS:
        return True, "casual_prompt"
    if len(compact) <= 4 and not any(signals.values()):
        return True, "too_short_without_verifiable_work"
    if compact in {"?", "？", "1", "yes", "no"}:
        return True, "non_actionable_prompt"
    return False, ""


def github_hash8(task_text: str) -> str:
    return hashlib.sha1(task_text.strip().encode("utf-8")).hexdigest()[:8]


def github_title_slug(prompt: str, type_name: str, domain: str) -> str:
    keywords = derive_prompt_keywords(prompt)
    if keywords:
        return normalize_slug_part("-".join(keywords[:3]))
    return normalize_slug_part(f"{type_name}-{domain}-task")


def github_display_title(prompt: str) -> str:
    return truncate_text(prompt.strip() or "未命名任务", 60)


def github_issue_title(classification: dict[str, Any], prompt: str) -> str:
    return f"[{classification['type']}/{classification['domain']}] {classification['slug']} | {github_display_title(prompt)}"


def github_labels(classification: dict[str, Any]) -> list[str]:
    return [
        f"type:{classification['type']}",
        f"domain:{classification['domain']}",
        f"state:{classification['state']}",
        f"artifact:{classification['artifact']}",
    ]


def default_github_owner() -> str:
    repo = git_origin_repo(SKILL_DIR)
    if not repo or "/" not in repo:
        return ""
    return repo.split("/", 1)[0]


def resolve_github_ops_repo(repo_override: str | None = None) -> str:
    value = (repo_override or os.getenv("AI_DA_GUAN_JIA_GITHUB_OPS_REPO", "")).strip()
    if value:
        return value
    owner = default_github_owner()
    return f"{owner}/{DEFAULT_GITHUB_OPS_REPO_NAME}" if owner else ""


def resolve_dot_github_repo(repo_override: str | None = None) -> str:
    value = (repo_override or os.getenv("AI_DA_GUAN_JIA_GITHUB_DOT_GITHUB_REPO", "")).strip()
    if value:
        return value
    owner = default_github_owner()
    return f"{owner}/{DEFAULT_GITHUB_DOT_GITHUB_REPO}" if owner else ""


def resolve_github_project_owner() -> str:
    return (
        os.getenv("AI_DA_GUAN_JIA_GITHUB_PROJECT_OWNER", "").strip()
        or default_github_owner()
    )


def resolve_github_project_number() -> int:
    raw = os.getenv("AI_DA_GUAN_JIA_GITHUB_PROJECT_NUMBER", "").strip()
    if not raw:
        return 0
    try:
        return int(raw)
    except ValueError:
        return 0


def github_issue_body(
    *,
    task_key: str,
    run_id: str,
    prompt: str,
    route_payload: dict[str, Any],
    classification: dict[str, Any],
    run_dir: Path,
) -> str:
    selected = ", ".join(normalize_list(route_payload.get("selected_skills"))) or "none"
    verification_targets_text = "\n".join(f"- {item}" for item in normalize_list(route_payload.get("verification_targets")))
    return "\n".join(
        [
            f"<!-- ai-da-guan-jia-task:{task_key} -->",
            "# AI大管家 Task Mirror",
            "",
            f"- Task Key: `{task_key}`",
            f"- Run ID: `{run_id}`",
            f"- Local Run Dir: `{run_dir}`",
            f"- Type: `{classification['type']}`",
            f"- Domain: `{classification['domain']}`",
            f"- Artifact: `{classification['artifact']}`",
            f"- State: `{classification['state']}`",
            f"- Selected Skills: {selected}",
            "",
            "## Request",
            "",
            prompt.strip(),
            "",
            "## Verification Targets",
            "",
            verification_targets_text or "- Need an artifact check plus a goal check before reporting completion.",
        ]
    )


def build_github_classification(
    *,
    task_text: str,
    created_at: str,
    selected_skills: list[str],
    verification_status: str | None = None,
) -> dict[str, Any]:
    type_name = infer_github_type(task_text)
    domain = infer_github_domain(task_text, selected_skills)
    artifact = infer_github_artifact(task_text, selected_skills)
    verification_norm = (verification_status or "").strip().lower()
    state = "verified" if verification_norm in {"passed", "success", "done", "complete", "completed"} else "routed"
    slug = github_title_slug(task_text, type_name, domain)
    task_key = f"tsk-{parse_datetime(created_at).strftime('%Y%m%d')}-{type_name}-{domain}-{slug}-{github_hash8(task_text)}"
    return {
        "type": type_name,
        "domain": domain,
        "state": state,
        "artifact": artifact,
        "slug": slug,
        "task_key": task_key,
    }


def build_github_task_record(
    *,
    run_id: str,
    created_at: str,
    task_text: str,
    route_payload: dict[str, Any],
    run_dir: Path,
    verification_status: str | None = None,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    existing = existing or {}
    skip, reason = should_skip_github_management(task_text, route_payload.get("signals", {}))
    selected = normalize_list(route_payload.get("selected_skills"))
    classification = build_github_classification(
        task_text=task_text,
        created_at=created_at,
        selected_skills=selected,
        verification_status=verification_status,
    )
    classification["state"] = existing.get("classification", {}).get("state") or classification["state"]
    if skip:
        classification["state"] = "blocked"
    target_repo = resolve_github_ops_repo(existing.get("github_repo"))
    project_owner = resolve_github_project_owner()
    project_number = resolve_github_project_number()
    issue_title = github_issue_title(classification, task_text)
    payload = {
        "run_id": run_id,
        "created_at": created_at,
        "task_text": task_text,
        "skip_github_management": skip,
        "skip_reason": reason,
        "classification": classification,
        "issue_title": issue_title,
        "issue_labels": github_labels(classification),
        "issue_body": github_issue_body(
            task_key=classification["task_key"],
            run_id=run_id,
            prompt=task_text,
            route_payload=route_payload,
            classification=classification,
            run_dir=run_dir,
        ),
        "github_repo": target_repo,
        "dot_github_repo": resolve_dot_github_repo(existing.get("dot_github_repo")),
        "github_project_owner": project_owner,
        "github_project_number": project_number,
        "github_project_url": existing.get("github_project_url")
        or (
            f"{DEFAULT_GITHUB_BASE_URL}/orgs/{project_owner}/projects/{project_number}"
            if project_owner and project_number
            else ""
        ),
        "issue_number": existing.get("issue_number"),
        "issue_url": existing.get("issue_url", ""),
        "issue_node_id": existing.get("issue_node_id", ""),
        "project_item_id": existing.get("project_item_id", ""),
        "closure_comment_id": existing.get("closure_comment_id", ""),
        "closure_comment_url": existing.get("closure_comment_url", ""),
        "github_sync_status": existing.get("github_sync_status", "pending_intake"),
        "github_archive_status": existing.get("github_archive_status", "not_archived"),
    }
    return payload


def render_github_sync_plan(github_task: dict[str, Any], phase: str) -> str:
    classification = github_task["classification"]
    lines = [
        "# GitHub Sync Plan",
        "",
        f"- Phase: `{phase}`",
        f"- Skip GitHub Management: `{github_task['skip_github_management']}`",
        f"- Task Key: `{classification['task_key']}`",
        f"- Repo: `{github_task['github_repo'] or 'unconfigured'}`",
        f"- Project: `{github_task['github_project_url'] or 'unconfigured'}`",
        f"- Issue Title: {github_task['issue_title']}",
        f"- Labels: {', '.join(github_task['issue_labels'])}",
        "",
        "## Classification",
        "",
        f"- Type: `{classification['type']}`",
        f"- Domain: `{classification['domain']}`",
        f"- State: `{classification['state']}`",
        f"- Artifact: `{classification['artifact']}`",
        "",
    ]
    if github_task["skip_github_management"]:
        lines.extend(
            [
                "## Result",
                "",
                f"- Skip reason: `{github_task['skip_reason']}`",
                "- No GitHub issue or project sync should be attempted for this run.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Execution Order",
                "",
                "1. Ensure the central ops issue exists or reuse the existing issue by task key.",
                "2. Normalize labels and issue body to the current task classification.",
                "3. If project config exists, add or update the issue in the configured Project.",
                "4. On closure, write a stable closure comment and update archive state.",
                "",
            ]
        )
    return "\n".join(lines)


def render_github_archive_markdown(
    github_task: dict[str, Any],
    evolution: dict[str, Any],
    run_dir: Path,
) -> str:
    verification = evolution["verification_result"]
    lines = [
        "# GitHub Archive",
        "",
        f"- Task Key: `{github_task['classification']['task_key']}`",
        f"- Run ID: `{evolution['run_id']}`",
        f"- Issue URL: {github_task.get('issue_url') or 'pending'}",
        f"- Project URL: {github_task.get('github_project_url') or 'pending'}",
        f"- Closure Comment URL: {github_task.get('closure_comment_url') or 'pending'}",
        f"- Archive Status: `{github_task.get('github_archive_status') or 'not_archived'}`",
        "",
        "## Verification",
        "",
        f"- Status: `{verification['status']}`",
        f"- Evidence: {' | '.join(normalize_list(verification.get('evidence'))) or 'none'}",
        f"- Open Questions: {' | '.join(normalize_list(verification.get('open_questions'))) or 'none'}",
        "",
        "## Evolution",
        "",
        f"- Effective Patterns: {' | '.join(normalize_list(evolution.get('effective_patterns'))) or 'none'}",
        f"- Wasted Patterns: {' | '.join(normalize_list(evolution.get('wasted_patterns'))) or 'none'}",
        f"- Next Iteration: {' | '.join(normalize_list(evolution.get('evolution_candidates'))) or 'none'}",
        "",
        f"- Local Run Dir: `{run_dir}`",
        "",
    ]
    return "\n".join(lines)


def project_status_name(classification_state: str) -> str:
    mapping = {
        "intake": "Inbox",
        "routed": "Inbox",
        "in_progress": "In Progress",
        "waiting_human": "Waiting",
        "blocked": "Waiting",
        "verified": "Verified",
        "archived": "Archived",
    }
    return mapping.get(classification_state, "Inbox")


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = read_json(path)
    return payload if isinstance(payload, dict) else {}


def build_github_closure_comment(
    github_task: dict[str, Any],
    evolution: dict[str, Any],
    run_dir: Path,
) -> str:
    verification = evolution["verification_result"]
    task_key = github_task["classification"]["task_key"]
    return "\n".join(
        [
            f"<!-- ai-da-guan-jia-closure:{task_key} -->",
            "## AI大管家 Closure",
            "",
            f"- Run ID: `{evolution['run_id']}`",
            f"- Verification: `{verification['status']}`",
            f"- Evidence: {' | '.join(normalize_list(verification.get('evidence'))) or 'none'}",
            f"- Open Questions: {' | '.join(normalize_list(verification.get('open_questions'))) or 'none'}",
            f"- Effective Patterns: {' | '.join(normalize_list(evolution.get('effective_patterns'))) or 'none'}",
            f"- Wasted Patterns: {' | '.join(normalize_list(evolution.get('wasted_patterns'))) or 'none'}",
            f"- Next Iteration: {' | '.join(normalize_list(evolution.get('evolution_candidates'))) or 'none'}",
            f"- Local Run Dir: `{run_dir}`",
        ]
    )


def prepare_github_materials(run_dir: Path, phase: str) -> dict[str, Any]:
    route_payload = load_optional_json(run_dir / "route.json")
    evolution = load_optional_json(run_dir / "evolution.json")
    existing = load_optional_json(run_dir / "github-task.json")
    task_text = str(evolution.get("task_text") or route_payload.get("task_text") or "").strip()
    created_at = str(evolution.get("created_at") or route_payload.get("created_at") or iso_now())
    run_id = str(evolution.get("run_id") or route_payload.get("run_id") or run_dir.name)
    selected_skills = normalize_list(evolution.get("skills_selected") or route_payload.get("selected_skills"))
    verification = normalize_verification_result(evolution.get("verification_result"))
    route_payload = {
        "run_id": run_id,
        "created_at": created_at,
        "task_text": task_text,
        "signals": route_payload.get("signals", detect_signals(task_text)),
        "selected_skills": selected_skills,
        "verification_targets": route_payload.get("verification_targets", verification_targets(detect_signals(task_text))),
    }
    github_task = build_github_task_record(
        run_id=run_id,
        created_at=created_at,
        task_text=task_text,
        route_payload=route_payload,
        run_dir=run_dir,
        verification_status=str(verification.get("status") or ""),
        existing=existing,
    )
    if phase == "intake":
        github_task["classification"]["state"] = "blocked" if github_task["skip_github_management"] else "routed"
    else:
        status = str(verification.get("status") or "").strip().lower()
        has_open_questions = bool(normalize_list(verification.get("open_questions")))
        if status in {"failed", "error", "blocked"}:
            github_task["classification"]["state"] = "blocked"
        elif status in {"partial", "warning", "warn", "mixed"}:
            github_task["classification"]["state"] = "verified"
        elif status in {"passed", "success", "done", "complete", "completed"} and not has_open_questions:
            github_task["classification"]["state"] = "archived"
        else:
            github_task["classification"]["state"] = "verified"
    github_task["issue_labels"] = github_labels(github_task["classification"])
    github_task["issue_title"] = github_issue_title(github_task["classification"], task_text)
    github_task["issue_body"] = github_issue_body(
        task_key=github_task["classification"]["task_key"],
        run_id=run_id,
        prompt=task_text,
        route_payload=route_payload,
        classification=github_task["classification"],
        run_dir=run_dir,
    )
    write_json(run_dir / "github-task.json", github_task)
    (run_dir / "github-sync-plan.md").write_text(
        render_github_sync_plan(github_task, phase),
        encoding="utf-8",
    )
    payload = {
        "phase": phase,
        "run_id": run_id,
        "created_at": created_at,
        "task_key": github_task["classification"]["task_key"],
        "repo": github_task["github_repo"],
        "project_url": github_task["github_project_url"],
        "classification": github_task["classification"],
        "issue": {
            "title": github_task["issue_title"],
            "body": github_task["issue_body"],
            "labels": github_task["issue_labels"],
            "number": github_task.get("issue_number"),
            "url": github_task.get("issue_url", ""),
        },
        "skip_github_management": github_task["skip_github_management"],
        "skip_reason": github_task["skip_reason"],
    }
    if evolution:
        payload["closure_comment"] = build_github_closure_comment(github_task, evolution, run_dir)
        payload["archive_status"] = github_task["classification"]["state"]
        (run_dir / "github-archive.md").write_text(
            render_github_archive_markdown(github_task, evolution, run_dir),
            encoding="utf-8",
        )
    write_json(run_dir / "github-payload.json", payload)
    return {"route": route_payload, "evolution": evolution, "github_task": github_task, "payload": payload}


def github_api_url(path: str) -> str:
    base = os.getenv("AI_DA_GUAN_JIA_GITHUB_API_URL", DEFAULT_GITHUB_API_URL).rstrip("/")
    return f"{base}/{path.lstrip('/')}"


def detect_github_backend() -> dict[str, str]:
    gh_path = shutil.which("gh")
    if gh_path:
        status = subprocess.run(
            ["gh", "auth", "status", "--hostname", "github.com"],
            capture_output=True,
            text=True,
            check=False,
        )
        if status.returncode == 0:
            return {"backend": "gh", "reason": ""}
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        return {"backend": "rest", "reason": ""}
    if gh_path:
        return {"backend": "", "reason": "gh_installed_but_not_authenticated"}
    return {"backend": "", "reason": "gh_missing_and_github_token_missing"}


def github_rest_json(method: str, path: str, payload: Any | None = None) -> tuple[int, Any, str]:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ai-da-guan-jia",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    raw = None if payload is None else json.dumps(payload).encode("utf-8")
    if raw is not None:
        headers["Content-Type"] = "application/json"
    request = urllib_request.Request(github_api_url(path), data=raw, method=method, headers=headers)
    try:
        with urllib_request.urlopen(request) as response:
            text = response.read().decode("utf-8")
            parsed = json.loads(text) if text.strip() else {}
            return response.status, parsed, ""
    except urllib_error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = None
        message = body or str(error)
        return error.code, parsed, message
    except urllib_error.URLError as error:
        return 0, None, str(error)


def github_graphql_json(query: str, variables: dict[str, Any]) -> tuple[int, Any, str]:
    backend = detect_github_backend()
    if backend["backend"] == "gh":
        command = ["gh", "api", "graphql", "-f", f"query={query}"]
        for key, value in variables.items():
            flag = "-F" if isinstance(value, int) else "-f"
            command.extend([flag, f"{key}={value}"])
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            return completed.returncode, None, completed.stderr or completed.stdout
        parsed = json.loads(completed.stdout) if completed.stdout.strip() else {}
        return 200, parsed, ""
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        return 0, None, backend["reason"] or "missing_github_auth"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "ai-da-guan-jia",
    }
    request = urllib_request.Request(
        github_api_url("graphql"),
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        method="POST",
        headers=headers,
    )
    try:
        with urllib_request.urlopen(request) as response:
            text = response.read().decode("utf-8")
            parsed = json.loads(text) if text.strip() else {}
            return response.status, parsed, ""
    except urllib_error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = None
        return error.code, parsed, body or str(error)


def github_api_json(method: str, path: str, payload: Any | None = None) -> tuple[int, Any, str]:
    backend = detect_github_backend()
    if backend["backend"] == "gh":
        command = ["gh", "api", "-X", method, path, "-H", "Accept: application/vnd.github+json"]
        if payload is not None:
            command.extend(["--input", "-"])
            completed = subprocess.run(
                command,
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                check=False,
            )
        else:
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            return completed.returncode, None, completed.stderr or completed.stdout
        parsed = json.loads(completed.stdout) if completed.stdout.strip() else {}
        return 200, parsed, ""
    return github_rest_json(method, path, payload)


def parse_repo(repo: str) -> tuple[str, str]:
    owner, name = repo.split("/", 1)
    return owner, name


def find_existing_issue(repo: str, task_key: str) -> dict[str, Any] | None:
    query = urllib_parse.quote_plus(f'repo:{repo} "{task_key}" in:body')
    _, payload, _ = github_api_json("GET", f"search/issues?q={query}")
    items = payload.get("items") if isinstance(payload, dict) else None
    if isinstance(items, list) and items:
        first = items[0]
        return first if isinstance(first, dict) else None
    return None


def ensure_issue(repo: str, github_task: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    notes: list[str] = []
    owner, name = parse_repo(repo)
    issue_number = github_task.get("issue_number")
    issue = None
    if issue_number:
        _, issue, _ = github_api_json("GET", f"repos/{owner}/{name}/issues/{issue_number}")
    if not issue:
        issue = find_existing_issue(repo, github_task["classification"]["task_key"])
        if issue:
            notes.append("reused_existing_issue_by_task_key")
    payload = {
        "title": github_task["issue_title"],
        "body": github_task["issue_body"],
        "labels": github_task["issue_labels"],
    }
    if issue and issue.get("number"):
        _, updated, _ = github_api_json("PATCH", f"repos/{owner}/{name}/issues/{issue['number']}", payload)
        return (updated or issue), notes
    _, created, _ = github_api_json("POST", f"repos/{owner}/{name}/issues", payload)
    return created, notes


def list_issue_comments(repo: str, issue_number: int) -> list[dict[str, Any]]:
    owner, name = parse_repo(repo)
    _, payload, _ = github_api_json("GET", f"repos/{owner}/{name}/issues/{issue_number}/comments?per_page=100")
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        return [item for item in payload["items"] if isinstance(item, dict)]
    return []


def upsert_closure_comment(repo: str, issue_number: int, task_key: str, body: str) -> dict[str, Any] | None:
    marker = f"<!-- ai-da-guan-jia-closure:{task_key} -->"
    owner, name = parse_repo(repo)
    for comment in list_issue_comments(repo, issue_number):
        if marker in str(comment.get("body") or ""):
            _, updated, _ = github_api_json(
                "PATCH",
                f"repos/{owner}/{name}/issues/comments/{comment['id']}",
                {"body": body},
            )
            return updated or comment
    _, created, _ = github_api_json(
        "POST",
        f"repos/{owner}/{name}/issues/{issue_number}/comments",
        {"body": body},
    )
    return created


def fetch_project_meta(owner: str, number: int) -> dict[str, Any]:
    query = """
    query($owner:String!, $number:Int!) {
      organization(login:$owner) {
        projectV2(number:$number) {
          id
          url
          fields(first:50) {
            nodes {
              __typename
              ... on ProjectV2FieldCommon { id name }
              ... on ProjectV2SingleSelectField { options { id name } }
            }
          }
        }
      }
      user(login:$owner) {
        projectV2(number:$number) {
          id
          url
          fields(first:50) {
            nodes {
              __typename
              ... on ProjectV2FieldCommon { id name }
              ... on ProjectV2SingleSelectField { options { id name } }
            }
          }
        }
      }
    }
    """
    _, payload, _ = github_graphql_json(query, {"owner": owner, "number": number})
    data = payload.get("data") if isinstance(payload, dict) else {}
    for root in ("organization", "user"):
        node = data.get(root) if isinstance(data, dict) else None
        if isinstance(node, dict) and isinstance(node.get("projectV2"), dict):
            return node["projectV2"]
    return {}


def find_project_item(owner: str, number: int, issue_node_id: str) -> dict[str, Any]:
    query = """
    query($owner:String!, $number:Int!) {
      organization(login:$owner) {
        projectV2(number:$number) {
          items(first:100) {
            nodes { id content { ... on Issue { id url number } } }
          }
        }
      }
      user(login:$owner) {
        projectV2(number:$number) {
          items(first:100) {
            nodes { id content { ... on Issue { id url number } } }
          }
        }
      }
    }
    """
    _, payload, _ = github_graphql_json(query, {"owner": owner, "number": number})
    data = payload.get("data") if isinstance(payload, dict) else {}
    for root in ("organization", "user"):
        node = data.get(root) if isinstance(data, dict) else None
        project = node.get("projectV2") if isinstance(node, dict) else None
        items = project.get("items", {}).get("nodes") if isinstance(project, dict) else None
        if not isinstance(items, list):
            continue
        for item in items:
            content = item.get("content") if isinstance(item, dict) else None
            if isinstance(content, dict) and str(content.get("id") or "") == issue_node_id:
                return item
    return {}


def ensure_project_item(
    github_task: dict[str, Any],
    issue_node_id: str,
    run_id: str,
    verification_status: str,
) -> tuple[str, str, list[str]]:
    owner = github_task.get("github_project_owner") or resolve_github_project_owner()
    number = int(github_task.get("github_project_number") or 0)
    if not owner or not number or not issue_node_id:
        return "", github_task.get("github_project_url", ""), ["project_unconfigured"]
    project = fetch_project_meta(owner, number)
    if not project:
        return "", github_task.get("github_project_url", ""), ["project_lookup_failed"]
    project_id = str(project.get("id") or "")
    project_url = str(project.get("url") or github_task.get("github_project_url") or "")
    item = find_project_item(owner, number, issue_node_id)
    notes: list[str] = []
    if item:
        item_id = str(item.get("id") or "")
    else:
        mutation = """
        mutation($projectId:ID!, $contentId:ID!) {
          addProjectV2ItemById(input:{projectId:$projectId, contentId:$contentId}) {
            item { id }
          }
        }
        """
        _, payload, _ = github_graphql_json(mutation, {"projectId": project_id, "contentId": issue_node_id})
        item_id = (
            payload.get("data", {})
            .get("addProjectV2ItemById", {})
            .get("item", {})
            .get("id", "")
            if isinstance(payload, dict)
            else ""
        )
        if item_id:
            notes.append("project_item_created")
    fields = {}
    for node in project.get("fields", {}).get("nodes", []):
        if isinstance(node, dict) and node.get("name"):
            fields[str(node["name"])] = node
    updates = {
        "Status": project_status_name(github_task["classification"]["state"]),
        "Task Key": github_task["classification"]["task_key"],
        "Type": github_task["classification"]["type"],
        "Domain": github_task["classification"]["domain"],
        "Verification": verification_status or "unverified",
        "Target Repo": github_task["github_repo"],
        "Run ID": run_id,
        "Archived At": parse_datetime(iso_now()).strftime("%Y-%m-%d")
        if github_task["classification"]["state"] == "archived"
        else "",
    }
    for field_name, value in updates.items():
        field = fields.get(field_name)
        if not field or not item_id:
            continue
        typename = str(field.get("__typename") or "")
        field_id = str(field.get("id") or "")
        mutation = ""
        variables: dict[str, Any] = {"projectId": project_id, "itemId": item_id, "fieldId": field_id}
        if typename == "ProjectV2SingleSelectField":
            options = {str(option.get("name")): str(option.get("id")) for option in field.get("options", []) if isinstance(option, dict)}
            option_id = options.get(str(value))
            if not option_id:
                notes.append(f"project_field_option_missing:{field_name}")
                continue
            variables["optionId"] = option_id
            mutation = """
            mutation($projectId:ID!, $itemId:ID!, $fieldId:ID!, $optionId:String!) {
              updateProjectV2ItemFieldValue(input:{
                projectId:$projectId,
                itemId:$itemId,
                fieldId:$fieldId,
                value:{singleSelectOptionId:$optionId}
              }) { projectV2Item { id } }
            }
            """
        elif field_name == "Archived At":
            if not value:
                continue
            variables["date"] = str(value)
            mutation = """
            mutation($projectId:ID!, $itemId:ID!, $fieldId:ID!, $date:Date!) {
              updateProjectV2ItemFieldValue(input:{
                projectId:$projectId,
                itemId:$itemId,
                fieldId:$fieldId,
                value:{date:$date}
              }) { projectV2Item { id } }
            }
            """
        else:
            variables["text"] = str(value)
            mutation = """
            mutation($projectId:ID!, $itemId:ID!, $fieldId:ID!, $text:String!) {
              updateProjectV2ItemFieldValue(input:{
                projectId:$projectId,
                itemId:$itemId,
                fieldId:$fieldId,
                value:{text:$text}
              }) { projectV2Item { id } }
            }
            """
        github_graphql_json(mutation, variables)
    return item_id, project_url, notes


def update_github_files_after_sync(run_dir: Path, github_task: dict[str, Any], payload: dict[str, Any]) -> None:
    write_json(run_dir / "github-task.json", github_task)
    write_json(run_dir / "github-sync-result.json", payload)
    evolution_path = run_dir / "evolution.json"
    if evolution_path.exists():
        evolution = load_optional_json(evolution_path)
        evolution["github_task_key"] = github_task["classification"]["task_key"]
        evolution["github_issue_url"] = str(github_task.get("issue_url") or "")
        evolution["github_project_url"] = str(github_task.get("github_project_url") or "")
        evolution["github_repo"] = str(github_task.get("github_repo") or "")
        evolution["github_sync_status"] = str(github_task.get("github_sync_status") or payload["status"])
        evolution["github_classification"] = github_task["classification"]
        evolution["github_archive_status"] = str(github_task.get("github_archive_status") or "not_archived")
        evolution["github_closure_comment_url"] = str(github_task.get("closure_comment_url") or "")
        write_json(evolution_path, evolution)
        write_json(run_dir / "worklog.json", build_worklog(evolution, run_dir))
        (run_dir / "worklog.md").write_text(render_worklog_markdown(build_worklog(evolution, run_dir)), encoding="utf-8")
        (run_dir / "evolution.md").write_text(render_evolution_markdown(evolution), encoding="utf-8")
        write_json(run_dir / "feishu-payload.json", make_feishu_payload(build_worklog(evolution, run_dir)))


def sync_github_run(
    run_id: str,
    *,
    phase: str,
    apply: bool,
    repo_override: str | None = None,
) -> tuple[int, str]:
    run_dir = find_run_dir(run_id)
    materials = prepare_github_materials(run_dir, phase)
    github_task = materials["github_task"]
    if repo_override:
        github_task["github_repo"] = repo_override.strip()
    status = "github_preview_ready" if not apply else "github_synced_applied"
    reason = ""
    command_results: list[dict[str, Any]] = []
    if github_task["skip_github_management"]:
        status = "github_skipped_meaningless_task"
        result = {
            "phase": phase,
            "mode": "apply" if apply else "dry-run",
            "status": status,
            "executed_at": iso_now(),
            "reason": github_task["skip_reason"],
            "command_results": [],
        }
        github_task["github_sync_status"] = status
        update_github_files_after_sync(run_dir, github_task, result)
        return 0, status
    repo = str(github_task.get("github_repo") or "").strip()
    if not repo:
        status = "github_blocked_missing_repo"
        reason = "AI_DA_GUAN_JIA_GITHUB_OPS_REPO is not configured."
    backend = detect_github_backend()
    if not reason and not backend["backend"]:
        status = "github_blocked_missing_auth"
        reason = backend["reason"]
    if reason:
        result = {
            "phase": phase,
            "mode": "apply" if apply else "dry-run",
            "status": status,
            "executed_at": iso_now(),
            "reason": reason,
            "repo": repo,
            "command_results": command_results,
        }
        github_task["github_sync_status"] = status
        update_github_files_after_sync(run_dir, github_task, result)
        return (1 if apply else 0), status
    if not apply:
        status = f"github_{phase}_preview_ready"
        result = {
            "phase": phase,
            "mode": "dry-run",
            "status": status,
            "executed_at": iso_now(),
            "repo": repo,
            "project_url": github_task.get("github_project_url", ""),
            "payload_file": str((run_dir / "github-payload.json").resolve()),
            "command_results": command_results,
        }
        github_task["github_sync_status"] = status
        update_github_files_after_sync(run_dir, github_task, result)
        return 0, status

    issue, notes = ensure_issue(repo, github_task)
    command_results.append({"step": "ensure_issue", "notes": notes, "issue_number": issue.get("number") if isinstance(issue, dict) else None})
    if not issue or not issue.get("number"):
        status = f"github_{phase}_apply_failed"
        result = {
            "phase": phase,
            "mode": "apply",
            "status": status,
            "executed_at": iso_now(),
            "repo": repo,
            "reason": "Failed to create or update GitHub issue.",
            "command_results": command_results,
        }
        github_task["github_sync_status"] = status
        update_github_files_after_sync(run_dir, github_task, result)
        return 1, status

    github_task["issue_number"] = int(issue["number"])
    github_task["issue_url"] = str(issue.get("html_url") or issue.get("url") or "")
    github_task["issue_node_id"] = str(issue.get("node_id") or "")
    if phase == "closure":
        comment = upsert_closure_comment(
            repo,
            int(issue["number"]),
            github_task["classification"]["task_key"],
            materials["payload"].get("closure_comment", ""),
        )
        if comment:
            github_task["closure_comment_id"] = str(comment.get("id") or "")
            github_task["closure_comment_url"] = str(comment.get("html_url") or comment.get("url") or "")
            command_results.append({"step": "upsert_closure_comment", "comment_id": github_task["closure_comment_id"]})
    item_id, project_url, project_notes = ensure_project_item(
        github_task,
        github_task.get("issue_node_id", ""),
        run_id,
        str(materials["evolution"].get("verification_result", {}).get("status") or ""),
    )
    if item_id:
        github_task["project_item_id"] = item_id
    if project_url:
        github_task["github_project_url"] = project_url
    command_results.append({"step": "ensure_project_item", "item_id": item_id, "notes": project_notes})
    github_task["github_sync_status"] = f"github_{phase}_synced_applied"
    github_task["github_archive_status"] = (
        "archived" if github_task["classification"]["state"] == "archived" else "active"
    )
    result = {
        "phase": phase,
        "mode": "apply",
        "status": github_task["github_sync_status"],
        "executed_at": iso_now(),
        "repo": repo,
        "issue_url": github_task["issue_url"],
        "project_url": github_task["github_project_url"],
        "closure_comment_url": github_task.get("closure_comment_url", ""),
        "payload_file": str((run_dir / "github-payload.json").resolve()),
        "command_results": command_results,
    }
    update_github_files_after_sync(run_dir, github_task, result)
    return 0, github_task["github_sync_status"]


def format_run_title(task_text: str, created_at: str) -> str:
    created = parse_datetime(created_at)
    task_part = truncate_text(task_text or "未命名任务", 32)
    return f"{task_part} ｜ {created.strftime('%Y-%m-%d %H:%M')}"


def summarize_verification_evidence(result: dict[str, Any]) -> str:
    evidence = normalize_list(result.get("evidence"))
    return " | ".join(evidence)


def summarize_open_questions(result: dict[str, Any]) -> str:
    return "\n".join(normalize_list(result.get("open_questions")))


def human_sync_status(machine_status: str) -> str:
    mapping = {
        "payload_only_local": "未同步",
        "payload_only_missing_link": "同步异常",
        "payload_only_missing_bridge": "同步异常",
        "apply_blocked_missing_link": "同步异常",
        "apply_blocked_missing_bridge": "同步异常",
        "dry_run_preview_ready": "待同步预览",
        "synced_applied": "已同步",
        "apply_failed": "同步异常",
        "dry_run_failed": "同步异常",
    }
    return mapping.get(machine_status, machine_status or "未同步")


def human_work_status(verification_status: str) -> str:
    normalized = verification_status.strip().lower()
    if normalized in {"passed", "success", "done", "complete", "completed"}:
        return "已完成"
    if normalized in {"partial", "warning", "warn", "mixed"}:
        return "部分完成"
    if normalized in {"failed", "error", "blocked"}:
        return "需返工"
    return "待验证"


def build_completion_method(evolution: dict[str, Any]) -> str:
    selected = normalize_list(evolution["skills_selected"])
    if selected:
        return f"调用技能：{', '.join(selected)}"
    return "未调用下游 skill"


def build_follow_up_suggestions(evolution: dict[str, Any]) -> str:
    suggestions = normalize_list(evolution["evolution_candidates"])
    if not suggestions:
        suggestions = normalize_list(evolution["verification_result"].get("open_questions"))
    return "\n".join(suggestions)


def build_worklog(evolution: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    verification = evolution["verification_result"]
    created_at = str(evolution["created_at"])
    soul_path = run_dir / "soul.md"
    work_status = human_work_status(str(verification["status"]))
    return {
        "run_id": str(evolution["run_id"]),
        "run_title": format_run_title(str(evolution["task_text"]), created_at),
        "created_at": created_at,
        "record_date": parse_datetime(created_at).strftime("%Y-%m-%d"),
        "task_text": str(evolution["task_text"]),
        "work_goal": str(evolution["goal_model"]),
        "work_status": work_status,
        "completion_summary": summarize_verification(verification),
        "completion_method": build_completion_method(evolution),
        "selected_skills": normalize_list(evolution["skills_selected"]),
        "skill_count": len(normalize_list(evolution["skills_selected"])),
        "verification_status": str(verification["status"]),
        "verification_evidence_summary": summarize_verification_evidence(verification),
        "verification_open_questions": summarize_open_questions(verification),
        "human_boundary": str(evolution["human_boundary"]),
        "follow_up_suggestions": build_follow_up_suggestions(evolution),
        "sync_status": human_sync_status(str(evolution["feishu_sync_status"])),
        "github_sync_status": str(evolution.get("github_sync_status") or ""),
        "github_issue_url": str(evolution.get("github_issue_url") or ""),
        "github_project_url": str(evolution.get("github_project_url") or ""),
        "github_task_key": str(evolution.get("github_task_key") or ""),
        "local_run_dir": str(run_dir.resolve()),
        "worklog_json_path": str((run_dir / "worklog.json").resolve()),
        "soul_md_path": str(soul_path.resolve()),
        "route_json_path": str((run_dir / "route.json").resolve()),
        "evolution_json_path": str((run_dir / "evolution.json").resolve()),
    }


def render_worklog_markdown(worklog: dict[str, Any]) -> str:
    lines = [
        "# Work Log",
        "",
        f"- 运行标题: {worklog['run_title']}",
        f"- 时间: {worklog['created_at']}",
        f"- 工作状态: {worklog['work_status']}",
        "",
        "## 接收任务",
        "",
        worklog["task_text"],
        "",
        "## 工作目标",
        "",
        worklog["work_goal"],
        "",
        "## 完成情况",
        "",
        worklog["completion_summary"],
        "",
        "## 完成方式",
        "",
        worklog["completion_method"],
        "",
        "## 调用技能",
        "",
        ", ".join(worklog["selected_skills"]) or "none",
        "",
        "## 验真",
        "",
        f"- 状态: {worklog['verification_status']}",
        f"- 证据: {worklog['verification_evidence_summary'] or 'none'}",
        f"- 开放问题: {worklog['verification_open_questions'] or 'none'}",
        "",
        "## 人类边界",
        "",
        worklog["human_boundary"],
        "",
        "## 后续建议",
        "",
        worklog["follow_up_suggestions"] or "none",
        "",
        "## GitHub Mirror",
        "",
        f"- Task Key: {worklog['github_task_key'] or 'none'}",
        f"- Sync Status: {worklog['github_sync_status'] or 'none'}",
        f"- Issue URL: {worklog['github_issue_url'] or 'none'}",
        f"- Project URL: {worklog['github_project_url'] or 'none'}",
        "",
    ]
    return "\n".join(lines)


def render_soul_markdown(evolution: dict[str, Any], run_dir: Path) -> str:
    verification = evolution["verification_result"]
    lines = [
        "# Soul Log",
        "",
        f"- Run ID: `{evolution['run_id']}`",
        f"- Created At: `{evolution['created_at']}`",
        "",
        "## 我今天接到了什么任务",
        "",
        str(evolution["task_text"]),
        "",
        "## 我为什么把它当成进化材料",
        "",
        str(evolution["goal_model"]),
        "",
        "## 今天最大的失真风险",
        "",
        str(evolution["max_distortion"]),
        "",
        "## 我是怎么判断自治与边界的",
        "",
        f"- 自治判断: {evolution['autonomy_judgment']}",
        f"- 人类边界: {evolution['human_boundary']}",
        "",
        "## 这次哪些做法真的让我变强",
        "",
    ]
    lines.extend(f"- {item}" for item in (normalize_list(evolution["effective_patterns"]) or ["none"]))
    lines.extend(["", "## 这次哪些动作只是消耗", ""])
    lines.extend(f"- {item}" for item in (normalize_list(evolution["wasted_patterns"]) or ["none"]))
    lines.extend(["", "## 下次我应该如何进化", ""])
    lines.extend(f"- {item}" for item in (normalize_list(evolution["evolution_candidates"]) or ["none"]))
    lines.extend(
        [
            "",
            "## 验真",
            "",
            f"- 状态: {verification['status']}",
            f"- 证据: {' | '.join(normalize_list(verification['evidence'])) or 'none'}",
            f"- 开放问题: {' | '.join(normalize_list(verification['open_questions'])) or 'none'}",
            "",
            f"- Run Dir: `{run_dir}`",
            "",
        ]
    )
    return "\n".join(lines)


def append_daily_soul_log(evolution: dict[str, Any]) -> Path:
    created = parse_datetime(str(evolution["created_at"]))
    daily_path = ensure_dir(SOUL_ROOT) / f"{created.strftime('%Y-%m-%d')}.md"
    entry_lines = [
        f"## {created.strftime('%H:%M')} {evolution['run_id']}",
        "",
        f"- 任务: {evolution['task_text']}",
        f"- 最大失真: {evolution['max_distortion']}",
        f"- 有效做法: {' | '.join(normalize_list(evolution['effective_patterns'])) or 'none'}",
        f"- 浪费动作: {' | '.join(normalize_list(evolution['wasted_patterns'])) or 'none'}",
        f"- 进化候选: {' | '.join(normalize_list(evolution['evolution_candidates'])) or 'none'}",
        "",
    ]
    if daily_path.exists():
        existing = daily_path.read_text(encoding="utf-8").rstrip() + "\n\n"
    else:
        existing = f"# Soul Diary {created.strftime('%Y-%m-%d')}\n\n"
    daily_path.write_text(existing + "\n".join(entry_lines), encoding="utf-8")
    return daily_path


def iter_evolution_records(limit: int = 50) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not RUNS_ROOT.exists():
        return records
    run_dirs = sorted(
        [path for path in RUNS_ROOT.glob("*/*") if path.is_dir()],
        key=lambda item: str(item),
    )
    for run_dir in reversed(run_dirs):
        evolution_path = run_dir / "evolution.json"
        if not evolution_path.exists():
            continue
        try:
            payload = read_json(evolution_path)
        except Exception:
            continue
        if isinstance(payload, dict):
            records.append(payload)
        if len(records) >= limit:
            break
    return records


def recent_selected_skill_counts(limit: int = 50) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in iter_evolution_records(limit=limit):
        for name in normalize_list(record.get("skills_selected")):
            counts[name] = counts.get(name, 0) + 1
    return counts


def normalize_text_list(value: Any) -> list[str]:
    return [item.strip().lower() for item in normalize_list(value)]


def evaluate_evolution_judgment(evolution: dict[str, Any]) -> dict[str, Any]:
    evidence = normalize_list(evolution.get("verification_result", {}).get("evidence"))
    open_questions = normalize_list(evolution.get("verification_result", {}).get("open_questions"))
    candidates = normalize_list(evolution.get("evolution_candidates"))
    wasted = normalize_text_list(evolution.get("wasted_patterns"))
    verification_status = str(evolution.get("verification_result", {}).get("status") or "").strip().lower()
    history = iter_evolution_records(limit=80)
    history = [item for item in history if str(item.get("run_id")) != str(evolution.get("run_id"))]
    historical_wasted: list[str] = []
    for item in history:
        historical_wasted.extend(normalize_text_list(item.get("wasted_patterns")))

    repeat_hits = sorted({item for item in wasted if item and item in historical_wasted})
    has_repeated_failure_pattern = bool(repeat_hits)
    has_reusable_routing_or_verification = bool(
        [text for text in candidates if any(key in text.lower() for key in ("route", "routing", "验真", "verify", "verification", "规则", "policy"))]
    )
    has_boundary_adjustment_with_evidence = bool(
        evidence and [text for text in candidates if any(key in text.lower() for key in ("边界", "boundary", "授权", "interrupt", "打扰"))]
    )
    has_cost_or_interrupt_reduction = bool(
        [text for text in candidates if any(key in text.lower() for key in ("算力", "compute", "cost", "少打扰", "低打扰", "autonomy", "自动化"))]
    ) and verification_status in {"passed", "success", "done", "complete", "completed", "partial", "warning", "warn", "mixed"}

    blockers: list[str] = []
    if not evidence and not open_questions:
        blockers.append("no_evidence")
    if candidates and all(any(key in item.lower() for key in ("感觉", "主观", "guess", "maybe")) for item in candidates):
        blockers.append("subjective_only")
    if not has_repeated_failure_pattern and len(candidates) <= 1 and not has_reusable_routing_or_verification:
        blockers.append("one_off_or_weak_signal")
    dna_conflicts = [
        item
        for item in candidates
        if any(key in item.lower() for key in ("skip verification", "ignore verification", "treat feishu as canonical", "跳过验真", "飞书作为唯一真相"))
    ]
    if dna_conflicts:
        blockers.append("dna_conflict")

    positive_signals: list[str] = []
    if has_repeated_failure_pattern:
        positive_signals.append("repeated_failure_pattern")
    if has_reusable_routing_or_verification:
        positive_signals.append("reusable_routing_or_verification_rule")
    if has_boundary_adjustment_with_evidence:
        positive_signals.append("boundary_adjustment_with_evidence")
    if has_cost_or_interrupt_reduction:
        positive_signals.append("cost_or_interrupt_reduction_without_verification_loss")

    hit = bool(positive_signals) and not blockers
    return {
        "hit": hit,
        "positive_signals": positive_signals,
        "repeat_hits": repeat_hits,
        "blockers": blockers,
        "evidence_count": len(evidence),
        "open_question_count": len(open_questions),
    }


def apply_evolution_writeback(evolution: dict[str, Any]) -> tuple[bool, list[Path]]:
    candidates = normalize_list(evolution.get("evolution_candidates"))
    if not candidates:
        return False, []
    path = SKILL_DIR / "references" / "validated-evolution-rules.md"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if not existing.strip():
        existing = "# Validated Evolution Rules\n\n"
    lines = existing.rstrip().splitlines()
    changed = False
    run_id = str(evolution["run_id"])
    timestamp = str(evolution["created_at"])
    for candidate in candidates:
        entry = f"- [{run_id}] {timestamp} :: {candidate}"
        if entry in lines:
            continue
        lines.append(entry)
        changed = True
    if changed:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return changed, [path] if changed else []


def git_commit_paths(paths: list[Path], run_id: str) -> str:
    if not paths:
        return ""
    add_command = ["git", "-C", str(SKILL_DIR), "add", *[str(path) for path in paths]]
    added = subprocess.run(add_command, capture_output=True, text=True, check=False)
    if added.returncode != 0:
        return ""
    check = subprocess.run(
        ["git", "-C", str(SKILL_DIR), "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=False,
    )
    if check.returncode != 0 or not check.stdout.strip():
        return ""
    message = f"evolve(ai-da-guan-jia): apply validated loop improvement {run_id}"
    committed = subprocess.run(
        ["git", "-C", str(SKILL_DIR), "commit", "-m", message],
        capture_output=True,
        text=True,
        check=False,
    )
    if committed.returncode != 0:
        return ""
    sha = subprocess.run(
        ["git", "-C", str(SKILL_DIR), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return sha.stdout.strip() if sha.returncode == 0 else ""


def find_review_run_dir(run_id: str) -> Path:
    for date_dir in sorted(REVIEWS_ROOT.glob("*")) if REVIEWS_ROOT.exists() else []:
        candidate = date_dir / run_id
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"review run_id not found: {run_id}")


def resolve_review_feishu_link(link_override: str | None = None) -> str:
    return (
        link_override
        or os.getenv("AI_DA_GUAN_JIA_REVIEW_FEISHU_LINK")
        or os.getenv("AI_DA_GUAN_JIA_FEISHU_LINK")
        or DEFAULT_REVIEW_FEISHU_LINK
    ).strip()


def sync_result_payload(
    *,
    run_id: str,
    mode: str,
    status: str,
    link: str,
    reason: str = "",
    command_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "mode": mode,
        "status": status,
        "executed_at": iso_now(),
        "link": link,
        "reason": reason,
        "command_results": command_results or [],
    }


def run_json_command(command: list[str]) -> tuple[subprocess.CompletedProcess[str], dict[str, Any] | None]:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    parsed: dict[str, Any] | None = None
    if completed.stdout.strip():
        try:
            payload = json.loads(completed.stdout)
            if isinstance(payload, dict):
                parsed = payload
        except Exception:
            parsed = None
    return completed, parsed


def write_review_sync_result(run_dir: Path, payload: dict[str, Any]) -> None:
    write_json(run_dir / "sync-result.json", payload)
    review_path = run_dir / "review.json"
    if not review_path.exists():
        return
    review = read_json(review_path)
    if not isinstance(review, dict):
        return
    review["feishu_sync_status"] = payload["status"]
    review["feishu_sync_result_path"] = str((run_dir / "sync-result.json").resolve())
    review["last_synced_at"] = payload["executed_at"]
    write_json(review_path, review)


def sync_review_to_feishu(
    run_id: str,
    *,
    link_override: str | None = None,
    bridge_script_override: str | None = None,
) -> tuple[int, str]:
    run_dir = find_review_run_dir(run_id)
    review = read_json(run_dir / "review.json")
    inventory_payload = read_json(run_dir / "inventory.json")
    if not isinstance(review, dict) or not isinstance(inventory_payload, dict):
        raise RuntimeError(f"review artifacts are incomplete for {run_id}")

    materials = write_review_materials(run_dir, inventory_payload=inventory_payload, review=review)
    bundle = materials["bundle"]
    bridge_script = Path(
        bridge_script_override
        or os.getenv("AI_DA_GUAN_JIA_FEISHU_BRIDGE_SCRIPT", str(DEFAULT_BRIDGE))
    ).resolve()
    link = resolve_review_feishu_link(link_override)

    if not link:
        payload = sync_result_payload(
            run_id=run_id,
            mode="apply",
            status="review_sync_blocked_missing_link",
            link="",
            reason="No review Feishu link configured.",
        )
        write_review_sync_result(run_dir, payload)
        return 1, payload["status"]
    if not bridge_script.exists():
        payload = sync_result_payload(
            run_id=run_id,
            mode="apply",
            status="review_sync_blocked_missing_bridge",
            link=link,
            reason=f"bridge script not found: {bridge_script}",
        )
        write_review_sync_result(run_dir, payload)
        return 1, payload["status"]
    if not REVIEW_SCHEMA_MANIFEST.exists():
        payload = sync_result_payload(
            run_id=run_id,
            mode="apply",
            status="review_sync_blocked_missing_manifest",
            link=link,
            reason=f"review schema manifest not found: {REVIEW_SCHEMA_MANIFEST}",
        )
        write_review_sync_result(run_dir, payload)
        return 1, payload["status"]

    command_results: list[dict[str, Any]] = []
    schema_command = [
        "python3",
        str(bridge_script),
        "sync-base-schema",
        "--link",
        link,
        "--manifest",
        str(REVIEW_SCHEMA_MANIFEST),
        "--apply",
    ]
    schema_completed, schema_payload = run_json_command(schema_command)
    command_results.append(
        {
            "step": "sync-base-schema",
            "command": schema_command,
            "returncode": schema_completed.returncode,
            "stdout": schema_completed.stdout,
            "stderr": schema_completed.stderr,
            "parsed": schema_payload,
        }
    )
    if schema_completed.returncode != 0 or not schema_payload:
        payload = sync_result_payload(
            run_id=run_id,
            mode="apply",
            status="review_sync_failed",
            link=link,
            reason="schema sync failed",
            command_results=command_results,
        )
        write_review_sync_result(run_dir, payload)
        return 1, payload["status"]

    tables_meta = {
        item["table_name"]: item
        for item in schema_payload.get("tables", [])
        if isinstance(item, dict) and item.get("table_name")
    }

    failed = False
    for table_name, records in bundle["tables"].items():
        payload_path = run_dir / f"{table_name}.payload.json"
        write_json(payload_path, records)
        meta = tables_meta.get(table_name, {})
        upsert_command = [
            "python3",
            str(bridge_script),
            "upsert-records",
            "--link",
            link,
            "--table-id",
            str(meta.get("table_id") or ""),
            "--primary-field",
            str(meta.get("primary_field") or ""),
            "--payload-file",
            str(payload_path),
            "--apply",
        ]
        upsert_completed, upsert_payload = run_json_command(upsert_command)
        command_results.append(
            {
                "step": f"upsert:{table_name}",
                "table_name": table_name,
                "command": upsert_command,
                "returncode": upsert_completed.returncode,
                "stdout": upsert_completed.stdout,
                "stderr": upsert_completed.stderr,
                "parsed": upsert_payload,
            }
        )
        if upsert_completed.returncode != 0:
            failed = True

    payload = sync_result_payload(
        run_id=run_id,
        mode="apply",
        status="review_synced_applied" if not failed else "review_sync_failed",
        link=link,
        reason="" if not failed else "One or more table upserts failed.",
        command_results=command_results,
    )
    write_review_sync_result(run_dir, payload)
    return (0 if not failed else 1), payload["status"]


def make_feishu_payload(
    worklog: dict[str, Any],
    *,
    sync_status_override: str | None = None,
) -> dict[str, str]:
    payload_sync_status = sync_status_override or str(worklog["sync_status"])
    return {
        "日志ID": str(worklog["run_id"]),
        "运行标题": str(worklog["run_title"]),
        "时间": str(worklog["created_at"]),
        "记录日期": str(worklog["record_date"]),
        "接收任务": str(worklog["task_text"]),
        "工作目标": str(worklog["work_goal"]),
        "工作状态": str(worklog["work_status"]),
        "完成情况": str(worklog["completion_summary"]),
        "完成方式": str(worklog["completion_method"]),
        "调用技能": ", ".join(normalize_list(worklog["selected_skills"])),
        "技能数量": str(worklog["skill_count"]),
        "验真状态": str(worklog["verification_status"]),
        "验真证据摘要": str(worklog["verification_evidence_summary"]),
        "验真开放问题": str(worklog["verification_open_questions"]),
        "人类边界": str(worklog["human_boundary"]),
        "后续建议": str(worklog["follow_up_suggestions"]),
        "同步状态": payload_sync_status,
        "本地运行目录": str(worklog["local_run_dir"]),
        "worklog.json路径": str(worklog["worklog_json_path"]),
        "soul.md路径": str(worklog["soul_md_path"]),
    }


def normalize_verification_result(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return {
            "status": str(raw.get("status") or "unverified"),
            "evidence": normalize_list(raw.get("evidence")),
            "open_questions": normalize_list(raw.get("open_questions")),
        }
    if isinstance(raw, str) and raw.strip():
        return {"status": raw.strip(), "evidence": [], "open_questions": []}
    return {"status": "unverified", "evidence": [], "open_questions": []}


def load_input_payload(path_value: str) -> dict[str, Any]:
    if path_value == "-":
        raw = sys.stdin.read()
        payload = json.loads(raw)
    else:
        payload = read_json(Path(path_value))
    if not isinstance(payload, dict):
        raise ValueError("record-evolution input must be a JSON object")
    return payload


def save_evolution_bundle(run_dir: Path, evolution: dict[str, Any], route_payload: dict[str, Any]) -> None:
    situation_map = {
        "自治判断": evolution["autonomy_judgment"],
        "全局最优判断": evolution["global_optimum_judgment"],
        "能力复用判断": evolution["reuse_judgment"],
        "验真判断": evolution["verification_judgment"],
        "进化判断": evolution["evolution_judgment"],
        "当前最大失真": evolution["max_distortion"],
    }
    (run_dir / "situation-map.md").write_text(
        render_situation_map(situation_map, evolution["task_text"]),
        encoding="utf-8",
    )
    write_json(run_dir / "route.json", route_payload)
    write_json(run_dir / "evolution.json", evolution)
    (run_dir / "evolution.md").write_text(render_evolution_markdown(evolution), encoding="utf-8")
    worklog = build_worklog(evolution, run_dir)
    write_json(run_dir / "worklog.json", worklog)
    (run_dir / "worklog.md").write_text(render_worklog_markdown(worklog), encoding="utf-8")
    (run_dir / "soul.md").write_text(render_soul_markdown(evolution, run_dir), encoding="utf-8")
    append_daily_soul_log(evolution)
    write_json(run_dir / "feishu-payload.json", make_feishu_payload(worklog))


def render_evolution_markdown(evolution: dict[str, Any]) -> str:
    verification = evolution["verification_result"]
    detail = evolution.get("evolution_judgment_detail") or {}
    lines = [
        "# Evolution Log",
        "",
        f"- Run ID: `{evolution['run_id']}`",
        f"- Created At: `{evolution['created_at']}`",
        "",
        "## Task",
        "",
        evolution["task_text"],
        "",
        "## Goal Model",
        "",
        evolution["goal_model"],
        "",
        "## Situation Map",
        "",
        f"- `自治判断`: {evolution['autonomy_judgment']}",
        f"- `全局最优判断`: {evolution['global_optimum_judgment']}",
        f"- `能力复用判断`: {evolution['reuse_judgment']}",
        f"- `验真判断`: {evolution['verification_judgment']}",
        f"- `进化判断`: {evolution['evolution_judgment']}",
        f"- `当前最大失真`: {evolution['max_distortion']}",
        "",
        "## Skill Routing",
        "",
        f"- Considered: {', '.join(normalize_list(evolution['skills_considered']))}",
        f"- Selected: {', '.join(normalize_list(evolution['skills_selected']))}",
        f"- Human Boundary: {evolution['human_boundary']}",
        "",
        "## Verification",
        "",
        f"- Status: {verification['status']}",
        f"- Evidence: {' | '.join(normalize_list(verification['evidence'])) or 'none'}",
        f"- Open Questions: {' | '.join(normalize_list(verification['open_questions'])) or 'none'}",
        "",
        "## Effective Patterns",
        "",
    ]
    effective = normalize_list(evolution["effective_patterns"]) or ["none"]
    lines.extend(f"- {item}" for item in effective)
    lines.extend(["", "## Wasted Patterns", ""])
    wasted = normalize_list(evolution["wasted_patterns"]) or ["none"]
    lines.extend(f"- {item}" for item in wasted)
    lines.extend(["", "## Evolution Candidates", ""])
    candidates = normalize_list(evolution["evolution_candidates"]) or ["none"]
    lines.extend(f"- {item}" for item in candidates)
    lines.extend(
        [
            "",
            "## Evolution Gate",
            "",
            f"- Hit: {detail.get('hit', False)}",
            f"- Positive Signals: {' | '.join(normalize_list(detail.get('positive_signals'))) or 'none'}",
            f"- Blockers: {' | '.join(normalize_list(detail.get('blockers'))) or 'none'}",
            f"- Writeback Applied: {bool(evolution.get('evolution_writeback_applied', False))}",
            f"- Writeback Commit: {str(evolution.get('evolution_writeback_commit') or 'none')}",
            "",
            "## GitHub Mirror",
            "",
            f"- Task Key: `{evolution.get('github_task_key') or 'none'}`",
            f"- Repo: `{evolution.get('github_repo') or 'none'}`",
            f"- Issue URL: {evolution.get('github_issue_url') or 'none'}",
            f"- Project URL: {evolution.get('github_project_url') or 'none'}",
            f"- GitHub Sync Status: `{evolution.get('github_sync_status') or 'none'}`",
            f"- Archive Status: `{evolution.get('github_archive_status') or 'none'}`",
            f"- Closure Comment URL: {evolution.get('github_closure_comment_url') or 'none'}",
        ]
    )
    lines.extend(["", f"- Feishu Sync Status: `{evolution['feishu_sync_status']}`", ""])
    return "\n".join(lines)


def command_inventory_skills(args: argparse.Namespace) -> int:
    skills = discover_skills()
    ensure_dir(INVENTORY_ROOT)
    output_path = Path(args.output).resolve() if args.output else INVENTORY_ROOT / (
        f"skills-{now_local().strftime('%Y%m%d-%H%M%S')}.json"
    )
    payload = {
        "generated_at": iso_now(),
        "skills_root": str(SKILLS_ROOT),
        "count": len(skills),
        "skills": skills,
    }
    write_json(output_path, payload)
    print(f"inventory: {output_path}")
    print(f"count: {len(skills)}")
    return 0


def command_route(args: argparse.Namespace) -> int:
    prompt = args.prompt.strip()
    if not prompt:
        raise ValueError("--prompt cannot be empty")
    skills = discover_skills()
    signals = detect_signals(prompt)
    mentioned = explicit_mentions(prompt, [item["name"] for item in skills])
    ranked = [score_candidate(prompt, skill, signals, mentioned) for skill in skills]
    ranked.sort(key=lambda item: item["total_score"], reverse=True)
    selected, omitted = choose_skills(prompt, ranked, signals, mentioned)
    situation_map = build_situation_map(prompt, selected, signals)
    created_at = iso_now()
    run_id = args.run_id or allocate_run_id(created_at)
    run_dir = run_dir_for(run_id, created_at)
    route_payload = {
        "run_id": run_id,
        "created_at": created_at,
        "task_text": prompt,
        "routing_order": ROUTING_ORDER,
        "signals": signals,
        "skills_considered": [item["name"] for item in ranked],
        "candidate_rankings": ranked[:10],
        "selected_skills": selected,
        "omitted_due_to_selection_ceiling": omitted,
        "selection_ceiling": selection_ceiling(signals),
        "human_boundary": determine_human_boundary(signals),
        "verification_targets": verification_targets(signals),
        "feishu_plan": (
            [
                "write local canonical evolution log",
                "generate feishu-payload.json",
                "run sync-feishu --dry-run",
                "run sync-feishu --apply only after explicit authorization",
            ]
            if signals["feishu"]
            else []
        ),
        "github_plan": [
            "write github-task.json",
            "write github-sync-plan.md",
            "run sync-github --phase intake --dry-run",
            "run sync-github --phase intake --apply when GitHub auth is available",
        ],
        "situation_map": situation_map,
    }
    write_json(run_dir / "route.json", route_payload)
    (run_dir / "situation-map.md").write_text(
        render_situation_map(situation_map, prompt),
        encoding="utf-8",
    )
    materials = prepare_github_materials(run_dir, "intake")
    github_dry_status = "skipped"
    github_apply_status = "skipped"
    _, github_dry_status = sync_github_run(run_id, phase="intake", apply=False)
    if github_dry_status == "github_intake_preview_ready":
        _, github_apply_status = sync_github_run(run_id, phase="intake", apply=True)
    print(f"run_id: {run_id}")
    print(f"run_dir: {run_dir}")
    print(f"selected: {', '.join(selected) if selected else 'none'}")
    print(f"github_task_key: {materials['github_task']['classification']['task_key']}")
    print(f"github_skip: {materials['github_task']['skip_github_management']}")
    print(f"github_sync_dry_run: {github_dry_status}")
    print(f"github_sync_apply: {github_apply_status}")
    return 0


def command_review_skills(args: argparse.Namespace) -> int:
    state = load_review_state()
    if args.resolve_action:
        run_id = str(args.run_id or state.get("latest_run_id") or "").strip()
        if not run_id:
            raise ValueError("--run-id is required when no latest review run exists.")
        status = {
            "latest_run_id": run_id,
            "status": "resolved",
            "pending_action_ids": [],
            "selected_action_id": str(args.resolve_action).strip(),
            "resolved_at": iso_now(),
        }
        save_review_state(status)
        run_dir = None
        try:
            run_dir = find_review_run_dir(run_id)
        except FileNotFoundError:
            run_dir = None
        if run_dir is not None:
            review_path = run_dir / "review.json"
            if review_path.exists():
                review_payload = read_json(review_path)
                if isinstance(review_payload, dict):
                    review_payload["status"] = "resolved"
                    review_payload["selected_action_id"] = status["selected_action_id"]
                    review_payload["resolved_at"] = status["resolved_at"]
                    inventory_payload = read_json(run_dir / "inventory.json") if (run_dir / "inventory.json").exists() else None
                    if isinstance(inventory_payload, dict):
                        write_review_materials(run_dir, inventory_payload=inventory_payload, review=review_payload)
                    else:
                        write_json(review_path, review_payload)
        print(f"status: resolved")
        print(f"run_id: {run_id}")
        print(f"selected_action_id: {status['selected_action_id']}")
        if args.sync_feishu and run_dir is not None:
            sync_code, sync_status = sync_review_to_feishu(
                run_id,
                link_override=args.link,
                bridge_script_override=args.bridge_script,
            )
            print(f"sync_status: {sync_status}")
            return sync_code
        return 0

    if not args.daily:
        raise ValueError("review-skills requires --daily or --resolve-action.")

    if state.get("status") == "awaiting_human_choice":
        print("status: awaiting_human_choice")
        print(f"run_id: {state.get('latest_run_id', '')}")
        print(f"pending_action_ids: {', '.join(normalize_list(state.get('pending_action_ids')))}")
        if args.sync_feishu and args.run_id:
            sync_code, sync_status = sync_review_to_feishu(
                str(args.run_id),
                link_override=args.link,
                bridge_script_override=args.bridge_script,
            )
            print(f"sync_status: {sync_status}")
            return sync_code
        return 0

    created_at = iso_now()
    run_id = allocate_review_run_id(created_at)
    run_dir = review_run_dir_for(run_id, created_at)
    inventory = build_review_inventory()
    review = build_review_payload(inventory, created_at=created_at, run_id=run_id)
    inventory_payload = {
        "generated_at": created_at,
        "skills_root": str(SKILLS_ROOT),
        "mode": "top_level_only",
        "excluded_patterns": ["artifacts/**/SKILL.md", ".system/*/SKILL.md"],
        "count": len(inventory),
        "skills": inventory,
    }
    write_review_materials(run_dir, inventory_payload=inventory_payload, review=review)
    save_review_state(
        {
            "latest_run_id": run_id,
            "status": "awaiting_human_choice",
            "pending_action_ids": [action["id"] for action in review["candidate_actions"]],
            "created_at": created_at,
        }
    )
    print(f"status: awaiting_human_choice")
    print(f"run_id: {run_id}")
    print(f"run_dir: {run_dir}")
    print(f"skills_total: {review['skills_total']}")
    print(f"candidate_actions: {', '.join(action['id'] for action in review['candidate_actions'])}")
    if args.sync_feishu:
        sync_code, sync_status = sync_review_to_feishu(
            run_id,
            link_override=args.link,
            bridge_script_override=args.bridge_script,
        )
        print(f"sync_status: {sync_status}")
        return sync_code
    return 0


def command_strategy_governor(args: argparse.Namespace) -> int:
    goals = load_strategy_goals()
    if args.goal:
        supplied = normalize_list(args.goal)
        goals = []
        for index, title in enumerate(supplied[:3], start=1):
            goals.append(
                {
                    "id": f"G{index}",
                    "title": title,
                    "theme": title,
                    "success_definition": "Need initiative mapping, thread proposals, and governance visibility.",
                    "priority": index,
                }
            )
        write_json(STRATEGY_CURRENT_ROOT / "strategic-goals.json", goals)
    bundle = write_strategy_operating_system(goals=goals)
    print(f"strategy_root: {STRATEGY_CURRENT_ROOT}")
    print(f"goals: {len(bundle['strategy_map']['goals'])}")
    print(f"initiatives: {len(bundle['initiatives'])}")
    print(f"thread_proposals: {len(bundle['thread_proposals'])}")
    print(f"recruitment_candidates: {len(bundle['recruitment'])}")
    print(f"scorecard_entries: {len(bundle['scorecard'])}")
    return 0


def command_record_evolution(args: argparse.Namespace) -> int:
    payload = load_input_payload(args.input)
    created_at = str(payload.get("created_at") or iso_now())
    run_id = str(payload.get("run_id") or allocate_run_id(created_at))
    run_dir = run_dir_for(run_id, created_at)
    route_path = run_dir / "route.json"
    route_payload = read_json(route_path) if route_path.exists() else {}

    task_text = str(payload.get("task_text") or route_payload.get("task_text") or "").strip()
    if not task_text:
        raise ValueError("record-evolution input must include task_text")

    selected = normalize_list(payload.get("skills_selected") or route_payload.get("selected_skills"))
    considered = normalize_list(payload.get("skills_considered") or route_payload.get("skills_considered"))
    signals = detect_signals(task_text)
    situation_map = build_situation_map(task_text, selected, signals)
    human_boundary = str(
        payload.get("human_boundary") or route_payload.get("human_boundary") or determine_human_boundary(signals)
    )

    evolution = {
        "run_id": run_id,
        "created_at": created_at,
        "task_text": task_text,
        "goal_model": str(payload.get("goal_model") or "Use the task to improve future routing, execution, and truthfulness."),
        "autonomy_judgment": str(payload.get("autonomy_judgment") or situation_map["自治判断"]),
        "global_optimum_judgment": str(payload.get("global_optimum_judgment") or situation_map["全局最优判断"]),
        "reuse_judgment": str(payload.get("reuse_judgment") or situation_map["能力复用判断"]),
        "verification_judgment": str(payload.get("verification_judgment") or situation_map["验真判断"]),
        "evolution_judgment": str(payload.get("evolution_judgment") or situation_map["进化判断"]),
        "max_distortion": str(payload.get("max_distortion") or situation_map["当前最大失真"]),
        "skills_considered": considered,
        "skills_selected": selected,
        "human_boundary": human_boundary,
        "verification_result": normalize_verification_result(payload.get("verification_result")),
        "effective_patterns": normalize_list(payload.get("effective_patterns")),
        "wasted_patterns": normalize_list(payload.get("wasted_patterns")),
        "evolution_candidates": normalize_list(payload.get("evolution_candidates")),
        "feishu_sync_status": str(payload.get("feishu_sync_status") or "payload_only_local"),
        "evolution_judgment_detail": payload.get("evolution_judgment_detail") if isinstance(payload.get("evolution_judgment_detail"), dict) else {},
        "evolution_writeback_applied": bool(payload.get("evolution_writeback_applied") or False),
        "evolution_writeback_commit": str(payload.get("evolution_writeback_commit") or ""),
        "github_task_key": str(payload.get("github_task_key") or ""),
        "github_issue_url": str(payload.get("github_issue_url") or ""),
        "github_project_url": str(payload.get("github_project_url") or ""),
        "github_repo": str(payload.get("github_repo") or resolve_github_ops_repo()),
        "github_sync_status": str(payload.get("github_sync_status") or "pending_intake"),
        "github_classification": payload.get("github_classification") if isinstance(payload.get("github_classification"), dict) else {},
        "github_archive_status": str(payload.get("github_archive_status") or "not_archived"),
        "github_closure_comment_url": str(payload.get("github_closure_comment_url") or ""),
    }

    route_payload = {
        "run_id": run_id,
        "created_at": created_at,
        "task_text": task_text,
        "routing_order": ROUTING_ORDER,
        "signals": signals,
        "skills_considered": evolution["skills_considered"],
        "candidate_rankings": route_payload.get("candidate_rankings", []),
        "selected_skills": evolution["skills_selected"],
        "omitted_due_to_selection_ceiling": route_payload.get("omitted_due_to_selection_ceiling", []),
        "selection_ceiling": selection_ceiling(signals),
        "human_boundary": human_boundary,
        "verification_targets": route_payload.get("verification_targets", verification_targets(signals)),
        "feishu_plan": route_payload.get("feishu_plan", []),
        "situation_map": {
            "自治判断": evolution["autonomy_judgment"],
            "全局最优判断": evolution["global_optimum_judgment"],
            "能力复用判断": evolution["reuse_judgment"],
            "验真判断": evolution["verification_judgment"],
            "进化判断": evolution["evolution_judgment"],
            "当前最大失真": evolution["max_distortion"],
        },
    }
    save_evolution_bundle(run_dir, evolution, route_payload)
    prepare_github_materials(run_dir, "closure")
    print(f"run_id: {run_id}")
    print(f"run_dir: {run_dir}")
    for field in REQUIRED_EVOLUTION_FIELDS:
        if field not in evolution:
            raise AssertionError(f"missing field after write: {field}")
    return 0


def update_evolution_sync_status(run_dir: Path, status: str) -> None:
    evolution_path = run_dir / "evolution.json"
    evolution = read_json(evolution_path)
    evolution["feishu_sync_status"] = status
    write_json(evolution_path, evolution)
    worklog = build_worklog(evolution, run_dir)
    write_json(run_dir / "worklog.json", worklog)
    (run_dir / "worklog.md").write_text(render_worklog_markdown(worklog), encoding="utf-8")
    (run_dir / "soul.md").write_text(render_soul_markdown(evolution, run_dir), encoding="utf-8")
    write_json(run_dir / "feishu-payload.json", make_feishu_payload(worklog))
    (run_dir / "evolution.md").write_text(render_evolution_markdown(evolution), encoding="utf-8")


def run_feishu_sync(
    run_id: str,
    *,
    apply: bool,
    link_override: str | None,
    primary_field_override: str | None,
    bridge_script_override: str | None,
    print_status: bool = True,
) -> tuple[int, str]:
    run_dir = find_run_dir(run_id)
    evolution_path = run_dir / "evolution.json"
    if not evolution_path.exists():
        raise FileNotFoundError(f"missing evolution.json for run {run_id}")
    evolution = read_json(evolution_path)
    worklog = build_worklog(evolution, run_dir)
    payload_path = run_dir / "feishu-payload.json"
    payload_status = "已同步" if apply else "待同步预览"
    write_json(payload_path, make_feishu_payload(worklog, sync_status_override=payload_status))

    bridge_script = Path(
        bridge_script_override
        or os.getenv("AI_DA_GUAN_JIA_FEISHU_BRIDGE_SCRIPT", str(DEFAULT_BRIDGE))
    ).resolve()
    link = (link_override or os.getenv("AI_DA_GUAN_JIA_FEISHU_LINK", DEFAULT_FEISHU_LINK)).strip()
    primary_field = primary_field_override or os.getenv("AI_DA_GUAN_JIA_FEISHU_PRIMARY_FIELD", "日志ID")
    mode = "apply" if apply else "dry-run"
    result_path = run_dir / "feishu-sync-result.json"

    if not link:
        status = "apply_blocked_missing_link" if apply else "payload_only_missing_link"
        result = {
            "mode": mode,
            "status": status,
            "executed_at": iso_now(),
            "payload_file": str(payload_path),
            "reason": "AI_DA_GUAN_JIA_FEISHU_LINK is not configured.",
        }
        write_json(result_path, result)
        update_evolution_sync_status(run_dir, status)
        if print_status:
            print(status)
        return (1, status) if apply else (0, status)

    if not bridge_script.exists():
        status = "apply_blocked_missing_bridge" if apply else "payload_only_missing_bridge"
        result = {
            "mode": mode,
            "status": status,
            "executed_at": iso_now(),
            "payload_file": str(payload_path),
            "reason": f"bridge script not found: {bridge_script}",
        }
        write_json(result_path, result)
        update_evolution_sync_status(run_dir, status)
        if print_status:
            print(status)
        return (1, status) if apply else (0, status)

    command = [
        "python3",
        str(bridge_script),
        "upsert-records",
        "--link",
        link,
        "--primary-field",
        primary_field,
        "--payload-file",
        str(payload_path),
        "--apply" if apply else "--dry-run",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    success = completed.returncode == 0
    status = (
        "synced_applied"
        if (success and apply)
        else "dry_run_preview_ready"
        if success
        else "apply_failed"
        if apply
        else "dry_run_failed"
    )
    result = {
        "mode": mode,
        "status": status,
        "executed_at": iso_now(),
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "payload_file": str(payload_path),
        "primary_field": primary_field,
        "link": link,
    }
    write_json(result_path, result)
    update_evolution_sync_status(run_dir, status)
    if print_status:
        print(status)
    return completed.returncode, status


def command_sync_feishu(args: argparse.Namespace) -> int:
    returncode, _ = run_feishu_sync(
        args.run_id,
        apply=bool(args.apply),
        link_override=args.link,
        primary_field_override=args.primary_field,
        bridge_script_override=args.bridge_script,
    )
    return returncode


def command_sync_github(args: argparse.Namespace) -> int:
    returncode, status = sync_github_run(
        args.run_id,
        phase=str(args.phase),
        apply=bool(args.apply),
        repo_override=args.repo,
    )
    print(status)
    return returncode


def command_close_task(args: argparse.Namespace) -> int:
    task_text = args.task.strip()
    if not task_text:
        raise ValueError("--task cannot be empty")

    created_at = str(args.created_at or iso_now())
    run_id = str(args.run_id or allocate_run_id(created_at))
    run_dir = run_dir_for(run_id, created_at)

    skills = discover_skills()
    signals = detect_signals(task_text)
    mentioned = explicit_mentions(task_text, [item["name"] for item in skills])
    ranked = [score_candidate(task_text, skill, signals, mentioned) for skill in skills]
    ranked.sort(key=lambda item: item["total_score"], reverse=True)
    selected, omitted = choose_skills(task_text, ranked, signals, mentioned)
    situation_map = build_situation_map(task_text, selected, signals)
    human_boundary = str(args.human_boundary or determine_human_boundary(signals))
    route_payload = {
        "run_id": run_id,
        "created_at": created_at,
        "task_text": task_text,
        "routing_order": ROUTING_ORDER,
        "signals": signals,
        "skills_considered": [item["name"] for item in ranked],
        "candidate_rankings": ranked[:10],
        "selected_skills": selected,
        "omitted_due_to_selection_ceiling": omitted,
        "selection_ceiling": selection_ceiling(signals),
        "human_boundary": human_boundary,
        "verification_targets": verification_targets(signals),
        "feishu_plan": [
            "write local canonical evolution log",
            "generate feishu-payload.json",
            "run sync-feishu --dry-run",
            "run sync-feishu --apply",
        ],
        "situation_map": situation_map,
    }

    evolution = {
        "run_id": run_id,
        "created_at": created_at,
        "task_text": task_text,
        "goal_model": str(args.goal or "Close the task with verification, reusable patterns, and recursive improvement."),
        "autonomy_judgment": situation_map["自治判断"],
        "global_optimum_judgment": situation_map["全局最优判断"],
        "reuse_judgment": situation_map["能力复用判断"],
        "verification_judgment": situation_map["验真判断"],
        "evolution_judgment": situation_map["进化判断"],
        "max_distortion": str(args.max_distortion or situation_map["当前最大失真"]),
        "skills_considered": route_payload["skills_considered"],
        "skills_selected": selected,
        "human_boundary": human_boundary,
        "verification_result": {
            "status": str(args.verification_status or "completed"),
            "evidence": normalize_list(args.evidence),
            "open_questions": normalize_list(args.open_question),
        },
        "effective_patterns": normalize_list(args.effective_pattern),
        "wasted_patterns": normalize_list(args.wasted_pattern),
        "evolution_candidates": normalize_list(args.evolution_candidate),
        "feishu_sync_status": "payload_only_local",
        "evolution_judgment_detail": {},
        "evolution_writeback_applied": False,
        "evolution_writeback_commit": "",
        "github_task_key": "",
        "github_issue_url": "",
        "github_project_url": "",
        "github_repo": resolve_github_ops_repo(),
        "github_sync_status": "pending_intake",
        "github_classification": {},
        "github_archive_status": "not_archived",
        "github_closure_comment_url": "",
    }
    save_evolution_bundle(run_dir, evolution, route_payload)
    prepare_github_materials(run_dir, "closure")

    dry_code, dry_status = run_feishu_sync(
        run_id,
        apply=False,
        link_override=args.link,
        primary_field_override=args.primary_field,
        bridge_script_override=args.bridge_script,
        print_status=False,
    )
    if dry_code != 0 or dry_status != "dry_run_preview_ready":
        print(f"run_id: {run_id}")
        print(f"run_dir: {run_dir}")
        print(f"sync_dry_run: {dry_status}")
        print("sync_apply: skipped")
        return dry_code if dry_code != 0 else 1

    apply_code, apply_status = run_feishu_sync(
        run_id,
        apply=True,
        link_override=args.link,
        primary_field_override=args.primary_field,
        bridge_script_override=args.bridge_script,
        print_status=False,
    )
    if apply_code != 0:
        print(f"run_id: {run_id}")
        print(f"run_dir: {run_dir}")
        print(f"sync_dry_run: {dry_status}")
        print(f"sync_apply: {apply_status}")
        return apply_code

    github_dry_code, github_dry_status = sync_github_run(run_id, phase="closure", apply=False, repo_override=args.repo)
    github_apply_status = "skipped"
    if github_dry_status in {"github_closure_preview_ready"}:
        _, github_apply_status = sync_github_run(run_id, phase="closure", apply=True, repo_override=args.repo)

    evolution_path = run_dir / "evolution.json"
    evolution_after_sync = read_json(evolution_path)
    detail = evaluate_evolution_judgment(evolution_after_sync)
    evolution_after_sync["evolution_judgment_detail"] = detail
    evolution_after_sync["evolution_judgment"] = (
        "Hit validated evolution rules; writeback applied."
        if detail["hit"]
        else "No validated evolution writeback this run."
    )
    changed, paths = apply_evolution_writeback(evolution_after_sync) if detail["hit"] else (False, [])
    commit_sha = git_commit_paths(paths, run_id) if changed else ""
    evolution_after_sync["evolution_writeback_applied"] = bool(commit_sha)
    evolution_after_sync["evolution_writeback_commit"] = commit_sha
    write_json(evolution_path, evolution_after_sync)
    write_json(run_dir / "worklog.json", build_worklog(evolution_after_sync, run_dir))
    write_json(run_dir / "feishu-payload.json", make_feishu_payload(build_worklog(evolution_after_sync, run_dir)))
    (run_dir / "worklog.md").write_text(
        render_worklog_markdown(build_worklog(evolution_after_sync, run_dir)),
        encoding="utf-8",
    )
    (run_dir / "soul.md").write_text(render_soul_markdown(evolution_after_sync, run_dir), encoding="utf-8")
    (run_dir / "evolution.md").write_text(render_evolution_markdown(evolution_after_sync), encoding="utf-8")

    print(f"run_id: {run_id}")
    print(f"run_dir: {run_dir}")
    print(f"sync_dry_run: {dry_status}")
    print(f"sync_apply: {apply_status}")
    print(f"github_sync_dry_run: {github_dry_status}")
    print(f"github_sync_apply: {github_apply_status}")
    print(f"evolution_hit: {detail['hit']}")
    print(f"evolution_writeback_applied: {evolution_after_sync['evolution_writeback_applied']}")
    if evolution_after_sync["evolution_writeback_commit"]:
        print(f"evolution_writeback_commit: {evolution_after_sync['evolution_writeback_commit']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local helper for the ai-da-guan-jia skill.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser("inventory-skills", help="Scan local skills and write a normalized inventory.")
    inventory.add_argument("--output", help="Optional output JSON path.")
    inventory.set_defaults(func=command_inventory_skills)

    route = subparsers.add_parser("route", help="Build a situation map and route the task to the best local skills.")
    route.add_argument("--prompt", required=True, help="Task prompt to analyze.")
    route.add_argument("--run-id", help="Optional run id override.")
    route.set_defaults(func=command_route)

    review = subparsers.add_parser(
        "review-skills",
        help="Review top-level installed skills, generate 3 candidate evolution actions, or resolve the current review choice.",
    )
    review_mode = review.add_mutually_exclusive_group(required=True)
    review_mode.add_argument("--daily", action="store_true", help="Run the daily top-level skill review flow.")
    review_mode.add_argument("--resolve-action", help="Mark the latest review or the provided run id as resolved by action id.")
    review.add_argument("--run-id", help="Optional review run id override for --resolve-action.")
    review.add_argument("--sync-feishu", action="store_true", help="Sync the review bundle into the review Feishu base.")
    review.add_argument("--link", help="Optional review Feishu wiki/base link override.")
    review.add_argument("--bridge-script", help="Optional bridge script path override.")
    review.set_defaults(func=command_review_skills)

    strategy = subparsers.add_parser(
        "strategy-governor",
        help="Generate the strategic operating-system artifacts: goals, initiatives, threads, gaps, scorecards, and governance dashboard.",
    )
    strategy.add_argument("--goal", action="append", help="Override one strategic goal title. Repeatable; first three are used.")
    strategy.set_defaults(func=command_strategy_governor)

    record = subparsers.add_parser("record-evolution", help="Write the canonical evolution record from JSON input.")
    record.add_argument("--input", required=True, help="JSON file path or - for stdin.")
    record.set_defaults(func=command_record_evolution)

    sync = subparsers.add_parser("sync-feishu", help="Mirror a completed local run into Feishu via the bridge skill.")
    mode = sync.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Generate or preview the Feishu sync without applying changes.")
    mode.add_argument("--apply", action="store_true", help="Apply the Feishu sync after authorization.")
    sync.add_argument("--run-id", required=True, help="Run id to mirror.")
    sync.add_argument("--link", help="Optional Feishu wiki/base link override.")
    sync.add_argument("--primary-field", help="Optional primary field override.")
    sync.add_argument("--bridge-script", help="Optional bridge script path override.")
    sync.set_defaults(func=command_sync_feishu)

    github_sync = subparsers.add_parser("sync-github", help="Mirror a completed local run into GitHub issue/project surfaces.")
    github_mode = github_sync.add_mutually_exclusive_group(required=True)
    github_mode.add_argument("--dry-run", action="store_true", help="Preview the GitHub sync without applying changes.")
    github_mode.add_argument("--apply", action="store_true", help="Apply the GitHub sync.")
    github_sync.add_argument("--run-id", required=True, help="Run id to mirror.")
    github_sync.add_argument("--phase", choices=["intake", "closure"], required=True, help="Sync phase to execute.")
    github_sync.add_argument("--repo", help="Optional GitHub ops repo override in owner/name format.")
    github_sync.set_defaults(func=command_sync_github)

    close_task = subparsers.add_parser(
        "close-task",
        help="Run the mandatory closure loop: recap, Feishu dry-run/apply, and evolution writeback.",
    )
    close_task.add_argument("--task", required=True, help="Task summary for this run.")
    close_task.add_argument("--goal", help="Goal model statement.")
    close_task.add_argument("--verification-status", default="completed", help="Verification status for this task.")
    close_task.add_argument("--evidence", action="append", help="Verification evidence item. Repeatable.")
    close_task.add_argument("--open-question", action="append", help="Open verification question. Repeatable.")
    close_task.add_argument("--effective-pattern", action="append", help="Effective pattern. Repeatable.")
    close_task.add_argument("--wasted-pattern", action="append", help="Wasted pattern. Repeatable.")
    close_task.add_argument("--evolution-candidate", action="append", help="Evolution candidate. Repeatable.")
    close_task.add_argument("--human-boundary", help="Optional explicit human boundary statement.")
    close_task.add_argument("--max-distortion", help="Optional max distortion statement.")
    close_task.add_argument("--run-id", help="Optional run id override.")
    close_task.add_argument("--created-at", help="Optional ISO datetime override.")
    close_task.add_argument("--link", help="Optional Feishu wiki/base link override.")
    close_task.add_argument("--primary-field", help="Optional primary field override.")
    close_task.add_argument("--bridge-script", help="Optional bridge script path override.")
    close_task.add_argument("--repo", help="Optional GitHub ops repo override in owner/name format.")
    close_task.set_defaults(func=command_close_task)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
