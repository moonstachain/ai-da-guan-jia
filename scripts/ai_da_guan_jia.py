#!/usr/bin/env python3
"""Local helper and router for the ai-da-guan-jia skill."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
CODEX_HOME = Path(os.getenv("CODEX_HOME", str(Path.home() / ".codex"))).resolve()
SKILLS_ROOT = CODEX_HOME / "skills"
ARTIFACTS_ROOT = SKILL_DIR / "artifacts" / "ai-da-guan-jia"
RUNS_ROOT = ARTIFACTS_ROOT / "runs"
INVENTORY_ROOT = ARTIFACTS_ROOT / "inventory"
SOUL_ROOT = ARTIFACTS_ROOT / "soul"
DEFAULT_BRIDGE = (
    CODEX_HOME / "skills" / "feishu-bitable-bridge" / "scripts" / "feishu_bitable_bridge.py"
)
DEFAULT_FEISHU_LINK = "https://h52xu4gwob.feishu.cn/wiki/FwG2wbljSiQrtPkTt8RcLAbxnvd?table=tblRho6nKw6aC0IO&view=vewNwnYDbj"
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
]


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
    return {"name": name, "description": description}


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
    skill_creation = any(
        phrase in text
        for phrase in [
            "做一个 skill",
            "做一个新 skill",
            "新 skill",
            "做个 skill",
            "create skill",
            "new skill",
            "update skill",
            "更新 skill",
            "修改 skill",
            "skill.md",
        ]
    )
    knowledge_first = (
        "知识库" in text
        or "knowledge base" in text
        or "notebooklm" in text
        or ("先问" in text and ("知识库" in text or "资料库" in text))
    )
    feishu = any(
        phrase in text
        for phrase in ["飞书", "feishu", "多维表", "bitable", "wiki", "同步飞书", "base"]
    )
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
        "skill_creation": skill_creation,
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
    if signals["skill_creation"]:
        wanted.append("skill-creator")
    if signals["knowledge_first"]:
        wanted.append("knowledge-orchestrator")
    if signals["feishu"]:
        wanted.append("feishu-bitable-bridge")
    if signals["evolution"]:
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

    for item in ranked:
        if len(selected) >= 3:
            break
        if item["name"] in selected or item["task_fit_score"] <= 0:
            continue
        selected.append(item["name"])

    omitted = [name for name in wanted if name not in selected]
    return selected[:3], normalize_list(omitted)


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
    if signals["skill_creation"]:
        return "把大管家做成口号，而不是可调用、可验证、可沉淀的 skill 包。"
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
        "selection_ceiling": 3,
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
        "situation_map": situation_map,
    }
    write_json(run_dir / "route.json", route_payload)
    (run_dir / "situation-map.md").write_text(
        render_situation_map(situation_map, prompt),
        encoding="utf-8",
    )
    print(f"run_id: {run_id}")
    print(f"run_dir: {run_dir}")
    print(f"selected: {', '.join(selected) if selected else 'none'}")
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
        "selection_ceiling": 3,
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
        "selection_ceiling": 3,
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
    }
    save_evolution_bundle(run_dir, evolution, route_payload)

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
    close_task.set_defaults(func=command_close_task)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
