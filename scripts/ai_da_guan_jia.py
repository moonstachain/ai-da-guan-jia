#!/usr/bin/env python3
"""Local helper and router for the ai-da-guan-jia skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from get_biji_connector import (
    GetBijiAPIError,
    GetBijiConfigError,
    ask as get_biji_api_ask,
    recall as get_biji_api_recall,
)

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
CODEX_HOME = Path(os.getenv("CODEX_HOME", str(Path.home() / ".codex"))).resolve()
SKILLS_ROOT = CODEX_HOME / "skills"
ARTIFACTS_ROOT = SKILL_DIR / "artifacts" / "ai-da-guan-jia"
RUNS_ROOT = ARTIFACTS_ROOT / "runs"
INVENTORY_ROOT = ARTIFACTS_ROOT / "inventory"
REVIEWS_ROOT = ARTIFACTS_ROOT / "reviews"
REVIEW_STATE_PATH = ARTIFACTS_ROOT / "review-state.json"
GOVERNANCE_ROOT = ARTIFACTS_ROOT / "governance"
GOVERNANCE_CURRENT_ROOT = GOVERNANCE_ROOT / "current"
GOVERNANCE_REVIEWS_ROOT = GOVERNANCE_ROOT / "reviews"
GOVERNANCE_REVIEW_STATE_PATH = GOVERNANCE_ROOT / "review-state.json"
SOUL_ROOT = ARTIFACTS_ROOT / "soul"
STRATEGY_ROOT = ARTIFACTS_ROOT / "strategy"
STRATEGY_CURRENT_ROOT = STRATEGY_ROOT / "current"
HUB_ROOT = ARTIFACTS_ROOT / "hub"
HUB_CURRENT_ROOT = HUB_ROOT / "current"
HUB_OUTBOX_ROOT = HUB_ROOT / "outbox"
HUB_REPOS_ROOT = HUB_ROOT / "repos"
SKILL_SCOUT_ROOT = ARTIFACTS_ROOT / "skill-scout"
SKILL_SCOUT_CURRENT_ROOT = SKILL_SCOUT_ROOT / "current"
GET_BIJI_ROOT = ARTIFACTS_ROOT / "get-biji"
GET_BIJI_CURRENT_ROOT = GET_BIJI_ROOT / "current"
GET_BIJI_LINK_INDEX_PATH = GET_BIJI_CURRENT_ROOT / "link-index.json"
GET_BIJI_TRANSCRIPT_SCRIPT = CODEX_HOME / "skills" / "get-biji-transcript" / "scripts" / "get_biji_transcript.py"
SKILL_SCOUT_CHANNEL_CHOICES = ["github", "x", "xiaohongshu", "bilibili"]
SKILL_SCOUT_DEDUPE_DAYS = 7
DEFAULT_BRIDGE = (
    CODEX_HOME / "skills" / "feishu-bitable-bridge" / "scripts" / "feishu_bitable_bridge.py"
)
DEFAULT_FEISHU_LINK = "https://h52xu4gwob.feishu.cn/wiki/FwG2wbljSiQrtPkTt8RcLAbxnvd?from=from_copylink&table=tblDR8XbK5fxun4x&view=vewbJgjzHr"
DEFAULT_REVIEW_FEISHU_LINK = "https://h52xu4gwob.feishu.cn/wiki/UzRjwDDLyi9OP4kEIHkcin1Gnhc?from=from_copylink"
REVIEW_SCHEMA_MANIFEST = SKILL_DIR / "references" / "feishu-review-base-schema.json"
REVIEW_SYNC_CONTRACT = SKILL_DIR / "references" / "feishu-review-sync-contract.md"
DEFAULT_GOVERNANCE_FEISHU_LINK = ""
GOVERNANCE_SCHEMA_MANIFEST = SKILL_DIR / "references" / "feishu-governance-base-schema.json"
GOVERNANCE_SYNC_CONTRACT = SKILL_DIR / "references" / "feishu-governance-sync-contract.md"
DEFAULT_GITHUB_BASE_URL = "https://github.com"
DEFAULT_GITHUB_API_URL = "https://api.github.com"
DEFAULT_GITHUB_OPS_REPO_NAME = "ai-task-ops"
DEFAULT_GITHUB_DOT_GITHUB_REPO = ".github"
GITHUB_TYPE_CHOICES = ["research", "spec", "implement", "debug", "review", "sync", "publish", "governance"]
GITHUB_DOMAIN_CHOICES = ["github", "feishu", "openai", "skill-system", "content", "data", "ops"]
GITHUB_STATE_CHOICES = ["intake", "routed", "in_progress", "waiting_human", "blocked", "verified", "archived"]
GITHUB_ARTIFACT_CHOICES = ["skill", "code", "doc", "workflow", "dataset", "integration", "report"]
PRIMARY_COMMANDS = ["route", "close-task", "review-skills", "review-governance", "strategy-governor"]
MIRROR_STATUS_CHOICES = ["local_only", "dry_run_ready", "apply_failed", "mirrored", "blocked_auth"]
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
    "verification_capability",
    "predicted_token_efficiency",
    "predicted_time_efficiency",
    "auth_reuse_score",
    "chain_simplicity",
]
ROUTE_SCORE_WEIGHTS = {
    "task_fit_score": 30,
    "verification_capability": 25,
    "predicted_token_efficiency": 15,
    "predicted_time_efficiency": 10,
    "auth_reuse_score": 10,
    "chain_simplicity": 10,
}
CLOSURE_SCORE_WEIGHTS = {
    "closure_quality": 25,
    "verification_strength": 20,
    "token_efficiency": 15,
    "time_efficiency": 15,
    "interruption_efficiency": 10,
    "reuse_contribution": 5,
    "handoff_coherence": 5,
    "strategic_alignment": 5,
}
DEFAULT_BUDGET_PROFILES = {
    "micro": {
        "soft_token_cap": 4000,
        "hard_token_cap": 8000,
        "soft_time_cap": 10,
        "hard_time_cap": 20,
        "intended_for": ["问答", "单点检索", "轻分析"],
    },
    "standard": {
        "soft_token_cap": 12000,
        "hard_token_cap": 24000,
        "soft_time_cap": 30,
        "hard_time_cap": 60,
        "intended_for": ["单 deliverable", "单链路执行"],
    },
    "deep": {
        "soft_token_cap": 30000,
        "hard_token_cap": 60000,
        "soft_time_cap": 90,
        "hard_time_cap": 180,
        "intended_for": ["多步分析", "复杂规划", "多来源核验"],
    },
    "expedition": {
        "soft_token_cap": 60000,
        "hard_token_cap": 120000,
        "soft_time_cap": 240,
        "hard_time_cap": 480,
        "intended_for": ["开放探索", "跨系统执行", "长链路调度"],
    },
}
ROUTE_SCORECARD_VERSION = "adagj-route-v1"
CLOSURE_SCORECARD_VERSION = "adagj-closure-v1"
HONESTY_GATE_MIN = 70.0
VERIFICATION_GATE_MIN = 4
GOVERNANCE_WINDOW_LIMIT = 120
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
    "governance_signal_status",
    "credit_influenced_selection",
    "proposal_authority_summary",
]

GOVERNANCE_AGENT_NAMES = {
    "ai-da-guan-jia",
    "knowledge-orchestrator",
    "routing-playbook",
    "self-evolution-max",
    "skill-trainer-recursive",
}

GOVERNANCE_TYPES = ["skill", "workflow", "agent", "component"]
HONESTY_HARDENING_PRIORITY = [
    "ai-da-guan-jia",
    "skill-trainer-recursive",
    "knowledge-orchestrator",
    "playwright",
    "figma",
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
SKILL_SCOUT_SEEDS = [
    {
        "seed_id": "x-reader",
        "group_id": "seed-x-reader",
        "title": "x-reader",
        "repo_or_resource": "runesleo/x-reader",
        "dedupe_key": "repo:runesleo/x-reader",
        "source_kind": "github_repo",
        "status_hint": "watch",
        "recommendation_hint": "likely_adopt",
        "official_sources": ["https://github.com/runesleo/x-reader"],
        "discovery_sources": [
            {"channel": "github", "url": "https://github.com/runesleo/x-reader", "notes": "Official README and install path."},
            {"channel": "xiaohongshu", "url": "https://www.xiaohongshu.com/search_result?keyword=x-reader", "notes": "Public discovery layer only."},
            {"channel": "bilibili", "url": "https://search.bilibili.com/all?keyword=x-reader", "notes": "Public discovery layer only."},
            {"channel": "x", "url": "https://x.com/search?q=x-reader", "notes": "Public discovery layer only."},
        ],
        "matched_local_skills": ["playwright", "feishu-reader", "get-biji-transcript"],
        "matched_review_problems": ["外部平台公共内容读取与链接解析仍缺统一入口。"],
        "embedded_first_party_evidence": [
            "README documents multi-platform export capability.",
            "README explicitly lists xiaohongshu.com support.",
            "README explicitly lists bilibili.com support.",
        ],
        "learning_value": "优先承担小红书/B站公共内容读取与链接解析。",
        "adoption_path": "先做公共链接解析试点，再决定是否固化为 skill/tool 依赖。",
    },
    {
        "seed_id": "agent-reach",
        "group_id": "seed-browser-agents",
        "title": "Agent Reach",
        "repo_or_resource": "Panniantong/agent-reach",
        "dedupe_key": "repo:Panniantong/agent-reach",
        "source_kind": "github_repo",
        "status_hint": "watch",
        "recommendation_hint": "watch",
        "official_sources": [
            "https://raw.githubusercontent.com/Panniantong/agent-reach/main/docs/install.md",
            "https://github.com/Panniantong/agent-reach",
        ],
        "discovery_sources": [
            {"channel": "github", "url": "https://github.com/Panniantong/agent-reach", "notes": "Official repo and install guide."},
            {"channel": "x", "url": "https://x.com/search?q=%22Agent%20Reach%22", "notes": "Public discovery layer only."},
        ],
        "matched_local_skills": ["playwright", "playwright-interactive"],
        "matched_review_problems": ["外部浏览器代理与发现层仍缺统一治理。"],
        "embedded_first_party_evidence": ["Install guide exists in first-party docs."],
        "learning_value": "作为浏览器代理与外部发现候选，先补官方安装与运行前提。",
        "adoption_path": "先核验安装前提和最小可运行链路，再决定是否进入 adoption queue。",
    },
    {
        "seed_id": "browserwing",
        "group_id": "seed-browser-agents",
        "title": "BrowserWing",
        "repo_or_resource": "browserwing/browserwing",
        "dedupe_key": "repo:browserwing/browserwing",
        "source_kind": "github_repo",
        "status_hint": "watch",
        "recommendation_hint": "watch",
        "official_sources": [
            "https://raw.githubusercontent.com/browserwing/browserwing/main/INSTALL.md",
            "https://github.com/browserwing/browserwing",
        ],
        "discovery_sources": [
            {"channel": "github", "url": "https://github.com/browserwing/browserwing", "notes": "Official repo and install guide."},
            {"channel": "x", "url": "https://x.com/search?q=browserwing", "notes": "Public discovery layer only."},
        ],
        "matched_local_skills": ["playwright", "playwright-interactive"],
        "matched_review_problems": ["现有浏览器执行链路可用，但缺升级备选。"],
        "embedded_first_party_evidence": ["INSTALL.md exists in first-party repo."],
        "learning_value": "只在现有浏览器执行链路不够时升级。",
        "adoption_path": "保留观察位，不主动替换现有 Playwright 链路。",
    },
    {
        "seed_id": "clawhub-obsidian",
        "group_id": "seed-clawhub",
        "title": "ClawHub obsidian",
        "repo_or_resource": "npx clawhub@latest install obsidian",
        "dedupe_key": "topic:clawhub-obsidian",
        "source_kind": "tool_install",
        "status_hint": "blocked_env",
        "recommendation_hint": "blocked_env",
        "official_sources": [
            "https://docs.clawhub.ai/getting-started/introduction",
            "https://docs.clawhub.ai/security/2026-01-security-notice",
        ],
        "discovery_sources": [
            {"channel": "github", "url": "https://github.com/search?q=clawhub+obsidian", "notes": "Discovery only; official docs stay source of truth."},
        ],
        "matched_local_skills": ["openclaw-xhs-coevolution-lab"],
        "matched_review_problems": ["OpenClaw 到 Obsidian 的写入链路尚未接通。"],
        "embedded_first_party_evidence": [
            "ClawHub docs say skills install into the current workspace.",
            "ClawHub published a 2026 security notice; white-list governance is required.",
        ],
        "learning_value": "价值高，但当前机器缺 node/npm/npx，且需通过 ClawHub 白名单与安全检查。",
        "adoption_path": "进入 adoption queue，不进入自动安装。",
    },
    {
        "seed_id": "clawhub-find-skills",
        "group_id": "seed-clawhub",
        "title": "ClawHub find-skills",
        "repo_or_resource": "npx clawhub@latest install find-skills",
        "dedupe_key": "topic:clawhub-find-skills",
        "source_kind": "tool_install",
        "status_hint": "blocked_env",
        "recommendation_hint": "blocked_env",
        "official_sources": [
            "https://docs.clawhub.ai/getting-started/introduction",
            "https://docs.clawhub.ai/security/2026-01-security-notice",
        ],
        "discovery_sources": [
            {"channel": "github", "url": "https://github.com/search?q=clawhub+find-skills", "notes": "Discovery only; official docs stay source of truth."},
        ],
        "matched_local_skills": ["ai-da-guan-jia"],
        "matched_review_problems": ["主动找 skill 解决问题的外部补强能力值得观察。"],
        "embedded_first_party_evidence": [
            "ClawHub docs say skills install into the current workspace.",
            "ClawHub published a 2026 security notice; white-list governance is required.",
        ],
        "learning_value": "作为主动找 skill 的候选，但先处理环境与安全边界。",
        "adoption_path": "进入 adoption queue，不进入自动安装。",
    },
    {
        "seed_id": "proactive-agent-1-2-4",
        "group_id": "seed-proactive-agent",
        "title": "proactive-agent-1-2-4",
        "repo_or_resource": "npx clawhub install proactive-agent-1-2-4",
        "dedupe_key": "topic:proactive-agent-1-2-4",
        "source_kind": "tool_install",
        "status_hint": "blocked_risk",
        "recommendation_hint": "blocked_risk",
        "official_sources": [
            "https://docs.clawhub.ai/getting-started/introduction",
            "https://docs.clawhub.ai/security/2026-01-security-notice",
        ],
        "discovery_sources": [
            {"channel": "github", "url": "https://github.com/search?q=proactive-agent-1-2-4", "notes": "Discovery only; official docs stay source of truth."},
            {"channel": "x", "url": "https://x.com/search?q=%22proactive-agent-1-2-4%22", "notes": "Public discovery layer only."},
        ],
        "matched_local_skills": ["self-evolution-max", "jiyao-youyao-haiyao-zaiyao"],
        "matched_review_problems": ["自我迭代主动 Agent 候选需要先界定方法论与权限边界。"],
        "embedded_first_party_evidence": ["The install path is mediated by ClawHub and inherits its security constraints."],
        "learning_value": "先观察方法论与权限边界，不进自动安装队列。",
        "adoption_path": "仅保留观察与风险说明。",
    },
]
AUTONOMY_TIERS = ["observe", "suggest", "trusted-suggest", "guarded-autonomy"]
PROPOSAL_AUTHORITY_BY_TIER = {
    "observe": "passive-candidate",
    "suggest": "proposal-candidate",
    "trusted-suggest": "priority-proposal-candidate",
    "guarded-autonomy": "strong-proposal-candidate",
}
MAX_ROUTING_CREDIT_ADJUSTMENT = 1200
MAX_ROUTING_CREDIT_RATIO = 0.12
INTAKE_BUNDLE_VERSION = "intake-bundle-v1"
DEFAULT_EXPECTED_SOURCES = ["main-hub", "satellite-01", "satellite-02"]
TASK_EVIDENCE_PRIORITY = {
    "github_task_key": 4,
    "run_id": 3,
    "session_key": 2,
    "normalized_task_hash": 1,
}
TASK_PROOF_PRIORITY = {
    "evolution_worklog": 4,
    "route": 3,
    "session": 2,
    "github_metadata": 1,
}


def resolve_task_feishu_link(link_override: str | None = None) -> str:
    candidates = [
        (link_override or "").strip(),
        os.getenv("AI_DA_GUAN_JIA_FEISHU_LINK", "").strip(),
        DEFAULT_FEISHU_LINK.strip(),
    ]
    for candidate in candidates:
        if candidate:
            return candidate
    return ""


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
    "get-biji-transcript": SkillProfile(
        name="get-biji-transcript",
        role="Operate Get笔记 for link ingestion, note generation, transcript extraction, and original-note fetches.",
        strengths=["Get笔记 authenticated session reuse", "Link ingestion", "Transcript extraction"],
        weaknesses=["Depends on a live logged-in web session and page stability"],
        boundary="Use when the task is specifically about Get笔记 ingestion, original transcript fetches, or browser-driven note capture.",
        keywords=[
            "get-biji-transcript",
            "get笔记",
            "得到笔记",
            "biji",
            "逐字稿",
            "转写",
            "导入链接",
            "原文提取",
        ],
        verification_strength=4,
        cost_efficiency=3,
        auth_reuse=5,
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
    "agency-engineering-rapid-prototyper": SkillProfile(
        name="agency-engineering-rapid-prototyper",
        role="Turn a structured MVP or PoC brief into a validation-first prototype bundle without drifting into production-grade system design.",
        strengths=["Prototype scoping", "Validation-first build plans", "Fastest-stack selection", "Prototype handoff bundles"],
        weaknesses=["Should not absorb production frontend or backend implementation work"],
        boundary="Use only for MVP, PoC, prototype, or 3-day validation work; do not use for pure React page implementation or backend architecture.",
        keywords=[
            "agency-engineering-rapid-prototyper",
            "rapid prototyper",
            "prototype",
            "mvp",
            "poc",
            "proof of concept",
            "3-day prototype",
            "3天原型",
            "快速验证",
            "最小可行",
            "原型",
        ],
        verification_strength=4,
        cost_efficiency=5,
        auth_reuse=1,
        complexity_penalty=1,
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


def repo_storage_name(repo: str) -> str:
    return repo.replace("/", "__")


def hub_repo_dir(repo: str) -> Path:
    return HUB_REPOS_ROOT / repo_storage_name(repo)


def hostname_slug() -> str:
    raw = socket.gethostname().strip() or "unknown-host"
    return normalize_slug_part(raw)


def default_source_id() -> str:
    value = os.getenv("AI_DA_GUAN_JIA_SOURCE_ID", "").strip()
    if value:
        return normalize_slug_part(value)
    return hostname_slug()


def resolve_expected_sources(values: list[str] | None = None) -> list[str]:
    if values:
        sources = [normalize_slug_part(item) for item in values if str(item).strip()]
    else:
        raw = os.getenv("AI_DA_GUAN_JIA_EXPECTED_SOURCES", "").strip()
        if raw:
            sources = [normalize_slug_part(item) for item in raw.split(",") if item.strip()]
        else:
            sources = list(DEFAULT_EXPECTED_SOURCES)
    if "main-hub" not in sources:
        sources.insert(0, "main-hub")
    normalized: list[str] = []
    seen: set[str] = set()
    for source in sources:
        if not source or source in seen:
            continue
        seen.add(source)
        normalized.append(source)
    return normalized


def artifact_shape(skill_dir: Path) -> dict[str, bool]:
    return {
        "SKILL.md": (skill_dir / "SKILL.md").exists(),
        "scripts": (skill_dir / "scripts").exists(),
        "references": (skill_dir / "references").exists(),
        "assets": (skill_dir / "assets").exists(),
        "agents": (skill_dir / "agents").exists(),
    }


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
    return load_state_file(REVIEW_STATE_PATH)


def save_review_state(payload: dict[str, Any]) -> None:
    save_state_file(REVIEW_STATE_PATH, payload)


def default_state_payload() -> dict[str, Any]:
    return {
        "status": "idle",
        "latest_run_id": "",
        "pending_action_ids": [],
        "carryover_pending_action_ids": [],
    }


def load_state_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return default_state_payload()
    try:
        payload = read_json(path)
    except Exception:
        return default_state_payload()
    if not isinstance(payload, dict):
        return default_state_payload()
    merged = default_state_payload()
    merged.update(payload)
    return merged


def save_state_file(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    merged = default_state_payload()
    merged.update(payload)
    write_json(path, merged)


def load_governance_review_state() -> dict[str, Any]:
    return load_state_file(GOVERNANCE_REVIEW_STATE_PATH)


def save_governance_review_state(payload: dict[str, Any]) -> None:
    save_state_file(GOVERNANCE_REVIEW_STATE_PATH, payload)


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


def generate_governance_review_run_id(timestamp: datetime | None = None) -> str:
    stamp = (timestamp or now_local()).strftime("%Y%m%d-%H%M%S")
    return f"adagj-governance-review-{stamp}"


def allocate_governance_review_run_id(created_at: str) -> str:
    dt = parse_datetime(created_at)
    base = generate_governance_review_run_id(dt)
    candidate = base
    index = 1
    while (GOVERNANCE_REVIEWS_ROOT / dt.strftime("%Y-%m-%d") / candidate).exists():
        candidate = f"{base}-{index:02d}"
        index += 1
    return candidate


def governance_review_run_dir_for(run_id: str, created_at: str | None = None) -> Path:
    dt = parse_datetime(created_at)
    return ensure_dir(GOVERNANCE_REVIEWS_ROOT / dt.strftime("%Y-%m-%d") / run_id)


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


def generate_skill_scout_run_id(timestamp: datetime | None = None) -> str:
    stamp = (timestamp or now_local()).strftime("%Y%m%d-%H%M%S")
    return f"adagj-skill-scout-{stamp}"


def allocate_skill_scout_run_id(created_at: str) -> str:
    dt = parse_datetime(created_at)
    base = generate_skill_scout_run_id(dt)
    candidate = base
    index = 1
    while (SKILL_SCOUT_ROOT / dt.strftime("%Y-%m-%d") / candidate).exists():
        candidate = f"{base}-{index:02d}"
        index += 1
    return candidate


def skill_scout_run_dir_for(run_id: str, created_at: str | None = None) -> Path:
    dt = parse_datetime(created_at)
    return ensure_dir(SKILL_SCOUT_ROOT / dt.strftime("%Y-%m-%d") / run_id)


def latest_skill_scout_briefing_path() -> Path | None:
    current_path = SKILL_SCOUT_CURRENT_ROOT / "latest-briefing.json"
    if current_path.exists():
        return current_path
    candidates = sorted(SKILL_SCOUT_ROOT.glob("*/*/briefing.json"), key=lambda item: str(item))
    return candidates[-1] if candidates else None


def load_latest_skill_scout_briefing() -> dict[str, Any]:
    path = latest_skill_scout_briefing_path()
    if not path:
        return {}
    payload = load_optional_json(path)
    if payload:
        payload["_path"] = str(path)
    return payload


def scout_environment_snapshot() -> dict[str, Any]:
    commands = {
        "node": shutil.which("node") or "",
        "npm": shutil.which("npm") or "",
        "npx": shutil.which("npx") or "",
        "gh": shutil.which("gh") or "",
        "docker": shutil.which("docker") or "",
    }
    obsidian_path = Path("/Applications/Obsidian.app")
    blockers = []
    for name in ["node", "npm", "npx", "gh", "docker"]:
        if not commands[name]:
            blockers.append(f"{name}_missing")
    return {
        "commands": commands,
        "obsidian_installed": obsidian_path.exists(),
        "obsidian_path": str(obsidian_path),
        "blockers": blockers,
    }


def scout_http_fetch(url: str, *, timeout: int = 8) -> dict[str, Any]:
    request = urllib_request.Request(
        url,
        headers={
            "User-Agent": "ai-da-guan-jia/skill-scout",
            "Accept": "text/html,application/json,text/plain;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urllib_request.urlopen(request, timeout=timeout) as response:
            raw = response.read(4096)
            text = raw.decode("utf-8", errors="replace")
            return {
                "url": url,
                "status": "fetched",
                "http_status": getattr(response, "status", 200),
                "sample": truncate_text(re.sub(r"\s+", " ", text), 400),
            }
    except urllib_error.HTTPError as error:
        return {"url": url, "status": "http_error", "http_status": error.code, "sample": str(error)}
    except urllib_error.URLError as error:
        return {"url": url, "status": "blocked", "http_status": 0, "sample": str(error)}
    except Exception as error:  # pragma: no cover
        return {"url": url, "status": "blocked", "http_status": 0, "sample": str(error)}


def within_recent_days(created_at: str, *, days: int) -> bool:
    if not created_at:
        return False
    try:
        created = parse_datetime(created_at)
    except Exception:
        return False
    return (now_local() - created).days < days


def load_recent_skill_scout_dedupe(days: int = SKILL_SCOUT_DEDUPE_DAYS) -> dict[str, dict[str, Any]]:
    dedupe: dict[str, dict[str, Any]] = {}
    for path in sorted(SKILL_SCOUT_ROOT.glob("*/*/scored-shortlist.json")):
        rows = load_optional_json_list(path)
        for row in rows:
            created_at = str(row.get("created_at") or "")
            if not within_recent_days(created_at, days=days):
                continue
            dedupe_key = str(row.get("dedupe_key") or "").strip()
            if not dedupe_key:
                continue
            dedupe[dedupe_key] = {
                "created_at": created_at,
                "total_score": float(row.get("total_score", 0)),
                "first_party_evidence_count": int(row.get("first_party_evidence_count", 0)),
                "source": "skill-scout",
            }
    for path in sorted((ARTIFACTS_ROOT / "github-scout").glob("*/*/scored-shortlist.json")):
        rows = load_optional_json_list(path)
        for row in rows:
            created_at = str(row.get("created_at") or path.parent.parent.name)
            if not within_recent_days(created_at, days=days):
                continue
            repo = str(row.get("repo_or_resource") or "").strip()
            if not repo:
                continue
            dedupe.setdefault(
                f"repo:{repo}",
                {
                    "created_at": created_at,
                    "total_score": float(row.get("total_score", 0)),
                    "first_party_evidence_count": 1,
                    "source": "github-scout",
                },
            )
    return dedupe


def scout_score_breakdown(seed: dict[str, Any], environment: dict[str, Any], fetched_sources: list[dict[str, Any]]) -> dict[str, int]:
    seed_id = str(seed["seed_id"])
    node_ready = bool(environment["commands"]["node"] and environment["commands"]["npm"] and environment["commands"]["npx"])
    docker_ready = bool(environment["commands"]["docker"])
    fetched_count = len([item for item in fetched_sources if item.get("status") == "fetched"])
    blueprint_match = {
        "x-reader": 5,
        "agent-reach": 4,
        "browserwing": 4,
        "clawhub-obsidian": 5,
        "clawhub-find-skills": 4,
        "proactive-agent-1-2-4": 3,
    }.get(seed_id, 3)
    first_party_strength = min(5, len(seed.get("embedded_first_party_evidence", [])) + fetched_count)
    freshness = 4 if seed_id in {"x-reader", "agent-reach", "browserwing"} else 3
    implementability = {
        "x-reader": 5,
        "agent-reach": 3,
        "browserwing": 3,
        "clawhub-obsidian": 3,
        "clawhub-find-skills": 3,
        "proactive-agent-1-2-4": 2,
    }.get(seed_id, 3)
    environment_fit = 4
    if seed_id.startswith("clawhub-") and not node_ready:
        environment_fit = 1
    elif seed_id == "browserwing" and not docker_ready:
        environment_fit = 2
    elif seed_id == "agent-reach" and not environment["commands"]["gh"]:
        environment_fit = 3
    safety_risk = {
        "x-reader": 1,
        "agent-reach": 2,
        "browserwing": 2,
        "clawhub-obsidian": 4,
        "clawhub-find-skills": 4,
        "proactive-agent-1-2-4": 5,
    }.get(seed_id, 3)
    return {
        "蓝图匹配度": blueprint_match,
        "一手来源充分度": first_party_strength,
        "新鲜度": freshness,
        "可落地度": implementability,
        "环境适配度": environment_fit,
        "安全风险": safety_risk,
    }


def scout_total_score(scores: dict[str, int]) -> float:
    return round(
        scores["蓝图匹配度"] * 20
        + scores["一手来源充分度"] * 18
        + scores["新鲜度"] * 12
        + scores["可落地度"] * 18
        + scores["环境适配度"] * 16
        - scores["安全风险"] * 10,
        2,
    )


def scout_status_for_seed(seed: dict[str, Any], scores: dict[str, int], environment: dict[str, Any]) -> str:
    seed_id = str(seed["seed_id"])
    node_ready = bool(environment["commands"]["node"] and environment["commands"]["npm"] and environment["commands"]["npx"])
    if seed_id.startswith("clawhub-") and not node_ready:
        return "blocked_env"
    if seed_id == "proactive-agent-1-2-4":
        return "blocked_risk"
    if scores["安全风险"] >= 5:
        return "blocked_risk"
    if scores["环境适配度"] <= 1:
        return "blocked_env"
    return str(seed.get("status_hint") or "watch")


def scout_reason(seed: dict[str, Any], status: str) -> str:
    if status == "blocked_env":
        return "当前机器缺少 node/npm/npx 或相关 CLI，先进入 adoption queue，不执行安装。"
    if status == "blocked_risk":
        return "先观察方法论与权限边界，避免把主动性工具直接升为自动执行。"
    if seed["seed_id"] == "x-reader":
        return "适合作为小红书/B站公共内容读取与链接解析入口，且与现有阅读链路互补。"
    if seed["seed_id"] == "browserwing":
        return "保留为浏览器执行升级备选，不主动替换现有 Playwright。"
    if seed["seed_id"] == "agent-reach":
        return "先补官方安装与运行前提，再决定是否引入为浏览器代理层。"
    return str(seed.get("learning_value") or "")


def build_skill_scout_summary(
    shortlist: list[dict[str, Any]],
    observation_only: list[dict[str, Any]],
    adoption_queue: list[dict[str, Any]],
    environment: dict[str, Any],
) -> dict[str, Any]:
    blockers = normalize_list(environment.get("blockers"))
    return {
        "shortlist_titles": [item["title"] for item in shortlist],
        "shortlist_count": len(shortlist),
        "observation_only_count": len(observation_only),
        "adoption_queue_count": len(adoption_queue),
        "env_blockers": blockers,
        "top_candidate": shortlist[0]["title"] if shortlist else "",
    }


def render_skill_scout_briefing(briefing: dict[str, Any]) -> str:
    lines = [
        "# Skill Scout Briefing",
        "",
        "## 今日推送说明",
        "",
        f"- 渠道: {' | '.join(briefing['channels'])}",
        f"- 去重窗口: {briefing['dedupe_window_days']} 天",
        f"- shortlist 数量: {briefing['shortlist_count']}",
        "",
        "## 今日 3 条以内推荐",
        "",
    ]
    for item in briefing["shortlist"]:
        lines.extend(
            [
                f"### {item['rank']}. {item['title']}",
                "",
                f"- 状态: {item['status']}",
                f"- 推荐理由: {item['recommend_reason']}",
                f"- 学习路径: {item['learn_how']}",
                f"- 使用时机: {item['use_when']}",
                "",
            ]
        )
    lines.extend(["## 今天没推但值得观察的候选", ""])
    for item in briefing["observation_only"][:5]:
        lines.append(f"- {item['title']} :: {item['status']} :: {item['reserve_note']}")
    lines.extend(["", "## 环境阻塞", ""])
    for blocker in briefing["env_blockers"]:
        lines.append(f"- {blocker}")
    return "\n".join(lines)


def build_skill_scout_feishu_payload(briefing: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    return {
        "generated_at": iso_now(),
        "run_id": briefing["run_id"],
        "summary": briefing["summary"],
        "mirror_status": briefing["mirror_status"],
        "artifact_path": str((run_dir / "briefing.json").resolve()),
        "shortlist": [
            {
                "title": item["title"],
                "status": item["status"],
                "recommend_reason": item["recommend_reason"],
                "learn_how": item["learn_how"],
                "use_when": item["use_when"],
            }
            for item in briefing["shortlist"]
        ],
    }


def persist_skill_scout_current_state(
    *,
    briefing: dict[str, Any],
    adoption_queue: list[dict[str, Any]],
    dedupe_history: dict[str, Any],
) -> None:
    ensure_dir(SKILL_SCOUT_CURRENT_ROOT)
    write_json(SKILL_SCOUT_CURRENT_ROOT / "latest-briefing.json", briefing)
    write_json(SKILL_SCOUT_CURRENT_ROOT / "adoption-queue.json", adoption_queue)
    write_json(SKILL_SCOUT_CURRENT_ROOT / "dedupe-history.json", dedupe_history)


def run_skill_scout_daily(channels: list[str], *, sync_feishu: bool = False) -> dict[str, Any]:
    created_at = iso_now()
    run_id = allocate_skill_scout_run_id(created_at)
    run_dir = skill_scout_run_dir_for(run_id, created_at)
    environment = scout_environment_snapshot()
    dedupe_history = load_recent_skill_scout_dedupe()
    source_scan: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    review_state = load_review_state()
    for seed in SKILL_SCOUT_SEEDS:
        official_fetches = []
        for url in seed.get("official_sources", []):
            fetch_result = scout_http_fetch(url)
            official_fetches.append(fetch_result)
            source_scan.append(
                {
                    "source_type": "official",
                    "channel": "github" if "github" in url or "raw.githubusercontent" in url else "web",
                    "url": url,
                    "collected_at": created_at,
                    "notes": fetch_result["status"],
                }
            )
        for discovery in seed.get("discovery_sources", []):
            if discovery["channel"] not in channels:
                continue
            source_scan.append(
                {
                    "source_type": "discovery",
                    "channel": discovery["channel"],
                    "url": discovery["url"],
                    "collected_at": created_at,
                    "notes": discovery["notes"],
                }
            )
        scores = scout_score_breakdown(seed, environment, official_fetches)
        status = scout_status_for_seed(seed, scores, environment)
        total_score = scout_total_score(scores)
        first_party_evidence_count = min(
            5,
            len(seed.get("embedded_first_party_evidence", []))
            + len([item for item in official_fetches if item["status"] == "fetched"]),
        )
        prior = dedupe_history.get(seed["dedupe_key"], {})
        has_new_first_party = first_party_evidence_count > int(prior.get("first_party_evidence_count", 0))
        score_up = total_score > float(prior.get("total_score", 0))
        dedupe_blocked = bool(prior) and not has_new_first_party and not score_up
        candidates.append(
            {
                "seed_id": seed["seed_id"],
                "group_id": seed["group_id"],
                "title": seed["title"],
                "dedupe_key": seed["dedupe_key"],
                "repo_or_resource": seed["repo_or_resource"],
                "source_kind": seed["source_kind"],
                "scores": scores,
                "score_breakdown": scores,
                "total_score": total_score,
                "first_party_evidence_count": first_party_evidence_count,
                "status": status,
                "recommend_reason": scout_reason(seed, status),
                "learn_how": str(seed.get("adoption_path") or ""),
                "use_when": str(seed.get("learning_value") or ""),
                "matched_local_skills": seed.get("matched_local_skills", []),
                "matched_review_problems": seed.get("matched_review_problems", []),
                "heat_evidence": [
                    item["url"] for item in seed.get("discovery_sources", []) if item["channel"] in channels
                ],
                "official_sources": seed.get("official_sources", []),
                "official_fetches": official_fetches,
                "embedded_first_party_evidence": seed.get("embedded_first_party_evidence", []),
                "dedupe_blocked": dedupe_blocked,
                "dedupe_reason": (
                    f"7 天内已有同主题推荐且没有更高分或新增一手证据（来源: {prior.get('source', '')}）。"
                    if dedupe_blocked
                    else ""
                ),
                "recommendation_hint": seed.get("recommendation_hint", "watch"),
                "created_at": created_at,
            }
        )

    candidates.sort(key=lambda item: item["total_score"], reverse=True)
    shortlist = [item for item in candidates if not item["dedupe_blocked"] and item["status"] != "reject"][:3]
    for index, item in enumerate(shortlist, start=1):
        item["rank"] = index
        item["reserve_note"] = ""
    observation_only = []
    for item in candidates:
        if item in shortlist:
            continue
        copy = dict(item)
        copy["reserve_note"] = copy["dedupe_reason"] or "继续观察，不进入今日 shortlist。"
        observation_only.append(copy)
    adoption_queue = [
        {
            "title": item["title"],
            "status": item["status"],
            "repo_or_resource": item["repo_or_resource"],
            "why": item["recommend_reason"],
            "next_step": item["learn_how"],
        }
        for item in candidates
        if item["status"] in {"blocked_env", "blocked_risk"} or item.get("recommendation_hint") == "likely_adopt"
    ]
    seed_watch_status = []
    for group_id in sorted({item["group_id"] for item in candidates}):
        group_rows = [item for item in candidates if item["group_id"] == group_id]
        group_status = "watch"
        if any(item["status"] == "blocked_risk" for item in group_rows):
            group_status = "blocked_risk"
        elif any(item["status"] == "blocked_env" for item in group_rows):
            group_status = "blocked_env"
        seed_watch_status.append(
            {
                "group_id": group_id,
                "status": group_status,
                "items": [item["title"] for item in group_rows],
                "top_item": group_rows[0]["title"] if group_rows else "",
            }
        )
    summary = build_skill_scout_summary(shortlist, observation_only, adoption_queue, environment)
    mirror_status = "mirror_blocked_missing_config"
    if sync_feishu and os.getenv("AI_DA_GUAN_JIA_GITHUB_SCOUT_FEISHU_LINK", "").strip() and os.getenv(
        "AI_DA_GUAN_JIA_GITHUB_SCOUT_PRIMARY_FIELD", ""
    ).strip():
        mirror_status = "preview_only_not_implemented"
    briefing = {
        "run_id": run_id,
        "created_at": created_at,
        "channels": channels,
        "dedupe_window_days": SKILL_SCOUT_DEDUPE_DAYS,
        "review_state": review_state,
        "review_pending": review_state.get("status") == "awaiting_human_choice",
        "shortlist_count": len(shortlist),
        "shortlist": shortlist,
        "observation_only": observation_only,
        "summary": summary,
        "seed_watch_items": seed_watch_status,
        "adoption_queue_count": len(adoption_queue),
        "env_blockers": summary["env_blockers"],
        "mirror_status": mirror_status,
    }
    write_json(run_dir / "source-scan.json", source_scan)
    write_json(run_dir / "candidate-pool.json", candidates)
    write_json(run_dir / "seed-watch-status.json", seed_watch_status)
    write_json(run_dir / "scored-shortlist.json", shortlist)
    write_json(run_dir / "briefing.json", briefing)
    write_json(run_dir / "feishu-payload.json", build_skill_scout_feishu_payload(briefing, run_dir))
    write_json(run_dir / "sync-result.json", {"run_id": run_id, "status": mirror_status, "generated_at": iso_now()})
    (run_dir / "briefing.md").write_text(render_skill_scout_briefing(briefing), encoding="utf-8")
    persist_skill_scout_current_state(briefing=briefing, adoption_queue=adoption_queue, dedupe_history=dedupe_history)
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "shortlist_count": len(shortlist),
        "mirror_status": mirror_status,
        "summary": summary,
    }


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
    scout_briefing: dict[str, Any] | None = None,
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
    scout_briefing = scout_briefing or {}
    scout_shortlist = scout_briefing.get("shortlist") if isinstance(scout_briefing.get("shortlist"), list) else []
    env_blockers = normalize_list(scout_briefing.get("env_blockers"))
    if scout_shortlist:
        top_item = scout_shortlist[0]
        actions.append(
            {
                "id": "A",
                "type": "外部线索转化",
                "title": "处理外部高价值线索",
                "problem": f"{top_item.get('title', '外部候选')} 当前被评为 {top_item.get('status', 'watch')}，值得纳入本地 adoption queue。",
                "proposed_change": "把 shortlist 第一名转成最小验证任务，补一手证据、边界说明和接入前置条件。",
                "expected_gain": "让 09:00 晨会不只看本地库存，也能稳定吸收外部有效信号。",
                "risk": "如果跳过白名单与环境检查，容易把外部热度误当成立即可用能力。",
                "recommended_next_step": str(top_item.get("learn_how") or top_item.get("use_when") or "先做最小验证。"),
            }
        )
    elif env_blockers:
        actions.append(
            {
                "id": "A",
                "type": "环境治理",
                "title": "先处理外部线索接入的环境阻塞",
                "problem": "当前 skill scout 已识别外部候选，但运行环境仍缺基础 CLI。",
                "proposed_change": "先把 node/npm/npx/gh/docker 的真实需求和白名单边界补齐，再决定是否开放安装。",
                "expected_gain": "减少后续 adoption queue 的假推进。",
                "risk": "如果环境先行过度扩张，会把治理问题错做成安装问题。",
                "recommended_next_step": "先核对 node/npm/npx/gh/docker 哪些是真刚需，哪些继续保持缺省。",
            }
        )
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
    scout_briefing = load_latest_skill_scout_briefing()
    actions = candidate_actions_for_review(inventory, overlaps, missing_capabilities, scout_briefing)
    strategy_map = build_strategy_map(load_strategy_goals(), inventory)
    scout_summary = scout_briefing.get("summary") if isinstance(scout_briefing.get("summary"), dict) else {}
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
        "external_signal_summary": {
            "shortlist_count": int(scout_summary.get("shortlist_count", 0)),
            "shortlist_titles": normalize_list(scout_summary.get("shortlist_titles")),
            "observation_only_count": int(scout_summary.get("observation_only_count", 0)),
            "adoption_queue_count": int(scout_summary.get("adoption_queue_count", 0)),
        },
        "seed_watch_items": scout_briefing.get("seed_watch_items", []) if isinstance(scout_briefing.get("seed_watch_items"), list) else [],
        "adoption_queue_count": int(scout_briefing.get("adoption_queue_count", 0) or scout_summary.get("adoption_queue_count", 0) or 0),
        "env_blockers": normalize_list(scout_briefing.get("env_blockers")),
        "status": "awaiting_human_choice",
    }


def latest_component_register_path() -> Path | None:
    candidates = sorted(RUNS_ROOT.glob("*/*/component-register.json"), key=lambda item: str(item))
    return candidates[-1] if candidates else None


def load_component_register() -> dict[str, Any]:
    path = latest_component_register_path()
    if not path:
        return {"components": [], "path": ""}
    payload = read_json(path)
    if not isinstance(payload, dict):
        return {"components": [], "path": str(path)}
    payload["path"] = str(path)
    return payload


def component_structure_level(component: dict[str, Any]) -> str:
    return str(component.get("maturity") or "L0").strip() or "L0"


def component_display_name(component: dict[str, Any]) -> str:
    return str(component.get("component_name") or component.get("name") or "unnamed-component")


def linked_run_paths(records: list[dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    for record in records:
        created_at = str(record.get("created_at") or "")
        run_id = str(record.get("run_id") or "")
        if not created_at or not run_id:
            continue
        path = run_dir_for(run_id, created_at) / "evolution.json"
        refs.append(str(path))
    return refs


def evidence_grade_from_flags(
    *,
    has_external_verification: bool,
    has_local_run_evidence: bool,
) -> str:
    if has_external_verification:
        return "A"
    if has_local_run_evidence:
        return "B"
    return "C"


def evidence_grade_score(grade: str) -> int:
    return {"A": 95, "B": 75, "C": 45}.get(grade, 45)


def normalized_verification_status(status: str) -> str:
    text = status.strip().lower()
    if text in {"passed", "success", "done", "complete", "completed"}:
        return "completed"
    if text in {"partial", "warning", "warn", "mixed", "部分验证"}:
        return "partial"
    if text in {"failed", "error", "blocked"}:
        return "failed"
    return "unverified"


def run_truth_metrics(records: list[dict[str, Any]]) -> dict[str, float]:
    total = max(1, len(records))
    claim_points = 0.0
    evidence_points = 0.0
    boundary_points = 0.0
    distortion_points = 0.0
    closure_points = 0.0
    closure_completed = 0.0
    open_question_total = 0
    evidence_total = 0
    effective_total = 0
    candidate_total = 0
    external_hits = 0
    for record in records:
        verification = normalize_verification_result(record.get("verification_result"))
        status = normalized_verification_status(str(verification.get("status") or ""))
        evidence = normalize_list(verification.get("evidence"))
        open_questions = normalize_list(verification.get("open_questions"))
        max_distortion = normalize_prompt(str(record.get("max_distortion") or ""))
        boundary = str(record.get("human_boundary") or "").strip()
        effective = normalize_list(record.get("effective_patterns"))
        candidates = normalize_list(record.get("evolution_candidates"))
        evidence_total += len(evidence)
        open_question_total += len(open_questions)
        effective_total += len(effective)
        candidate_total += len(candidates)
        if str(record.get("feishu_sync_status") or "").strip() == "synced_applied" or str(record.get("github_issue_url") or "").strip():
            external_hits += 1

        if status == "completed" and not open_questions:
            claim_points += 1.0
            closure_completed += 1.0
            closure_points += 1.0
        elif status == "partial":
            claim_points += 0.75 if open_questions else 0.55
            closure_points += 0.85 if open_questions else 0.45
        elif status == "failed":
            claim_points += 0.5
            closure_points += 0.7 if open_questions else 0.35
        else:
            claim_points += 0.45
            closure_points += 0.35

        if evidence:
            evidence_points += min(1.0, 0.35 + len(evidence) * 0.2)
        if boundary:
            boundary_points += 1.0
        elif open_questions:
            boundary_points += 0.3

        distortion_penalty = 0.0
        if open_questions:
            distortion_penalty += min(0.8, len(open_questions) * 0.2)
        if max_distortion and max_distortion not in {"none", "无", "n/a"}:
            distortion_penalty += 0.2
        distortion_points += max(0.0, 1.0 - min(1.0, distortion_penalty))

    return {
        "claim_integrity": round((claim_points / total) * 100, 2),
        "evidence_traceability": round((evidence_points / total) * 100, 2),
        "boundary_integrity": round((boundary_points / total) * 100, 2),
        "distortion_control": round((distortion_points / total) * 100, 2),
        "closure_truthfulness": round((closure_points / total) * 100, 2),
        "closure_reliability": round((closure_completed / total) * 100, 2),
        "open_question_density": round(open_question_total / total, 2),
        "evidence_density": round(evidence_total / total, 2),
        "effective_density": round(effective_total / total, 2),
        "candidate_density": round(candidate_total / total, 2),
        "external_hits": float(external_hits),
    }


def honesty_score_from_dimensions(dimensions: dict[str, float]) -> float:
    return round(
        dimensions["claim_integrity"] * 0.25
        + dimensions["evidence_traceability"] * 0.25
        + dimensions["boundary_integrity"] * 0.15
        + dimensions["distortion_control"] * 0.20
        + dimensions["closure_truthfulness"] * 0.15,
        2,
    )


def measured_honesty_score(records: list[dict[str, Any]], dimensions: dict[str, float]) -> float | None:
    if not records:
        return None
    return honesty_score_from_dimensions(dimensions)


def honesty_gate_passed_from_score(honesty_score: float | None) -> bool:
    return honesty_score is None or honesty_score >= 70


def honesty_sort_value(honesty_score: float | None) -> float:
    if honesty_score is None:
        return -1.0
    return float(honesty_score)


def honesty_is_low(honesty_score: float | None) -> bool:
    return honesty_score is not None and honesty_score < 70


def maturity_score_from_dimensions(
    *,
    closure_reliability: float,
    workflow_hardness: float,
    reuse_reliability: float,
    cost_efficiency: float,
    autonomy_safety: float,
    evolution_learning: float,
) -> float:
    return round(
        closure_reliability * 0.25
        + workflow_hardness * 0.20
        + reuse_reliability * 0.15
        + cost_efficiency * 0.15
        + autonomy_safety * 0.10
        + evolution_learning * 0.15,
        2,
    )


def governance_tier(
    *,
    honesty_score: float | None,
    maturity_score: float,
    evidence_grade: str,
    run_support_count: int,
    open_question_density: float,
) -> str:
    if honesty_is_low(honesty_score) or (evidence_grade == "C" and run_support_count == 0):
        return "Low"
    if (
        honesty_score is not None
        and honesty_score >= 85
        and maturity_score >= 75
        and evidence_grade in {"A", "B"}
        and run_support_count >= 2
        and open_question_density <= 0.35
    ):
        return "High"
    if honesty_score is None:
        if maturity_score >= 50 and evidence_grade in {"A", "B"}:
            return "Mid"
        return "Low"
    if honesty_score >= 70 and maturity_score >= 50 and evidence_grade in {"A", "B"}:
        return "Mid"
    return "Low"


def routing_effect_for_object(honesty_score: float | None, governance_score: float) -> str:
    if honesty_score is None:
        return "neutral"
    if honesty_score < 70:
        return "no_positive_adjustment"
    if governance_score >= 80:
        return "boosted"
    return "neutral"


def autonomy_cap_for_object(honesty_score: float | None, governance_score: float) -> str:
    if honesty_score is None:
        return "observe"
    if honesty_score < 70:
        return "suggest"
    if governance_score >= 85:
        return "guarded-autonomy"
    if governance_score >= 70:
        return "trusted-suggest"
    if governance_score >= 50:
        return "suggest"
    return "observe"


def writeback_trust_for_object(object_type: str, honesty_score: float | None, maturity_score: float) -> bool:
    if object_type not in {"skill", "agent"}:
        return False
    return honesty_score is not None and honesty_score >= 85 and maturity_score >= 75


def strategic_fit_for_skill(item: dict[str, Any]) -> float:
    return 95.0 if strategic_goal_for_item(item) in {"G1", "G2", "G3"} else 60.0


def strategic_fit_for_component(component: dict[str, Any]) -> float:
    if str(component.get("super_module") or "").strip():
        return 90.0
    return 65.0


def structure_level_score(value: str) -> float:
    normalized = value.strip().upper()
    mapping = {
        "L0": 20.0,
        "L0-L1": 30.0,
        "L1": 45.0,
        "L1-L2": 55.0,
        "L2": 70.0,
        "L2-L3": 82.0,
        "L3": 92.0,
    }
    return mapping.get(normalized, 35.0)


def workflow_registry_from_runs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for record in records:
        selected = normalize_list(record.get("skills_selected"))
        if len(selected) < 2:
            continue
        key = " -> ".join(selected)
        entry = grouped.setdefault(
            key,
            {
                "workflow_id": f"workflow:{stable_hash(key)}",
                "display_name": key,
                "selected_skills": selected,
                "run_ids": [],
                "task_samples": [],
            },
        )
        entry["run_ids"].append(str(record.get("run_id") or ""))
        if len(entry["task_samples"]) < 5:
            entry["task_samples"].append(str(record.get("task_text") or ""))
    rows = []
    for key, entry in grouped.items():
        if len(entry["run_ids"]) < 2:
            continue
        rows.append(
            {
                "workflow_id": entry["workflow_id"],
                "display_name": entry["display_name"],
                "selected_skills": entry["selected_skills"],
                "run_count": len(entry["run_ids"]),
                "run_ids": entry["run_ids"],
                "task_samples": entry["task_samples"],
                "structure_level": "L2" if len(entry["run_ids"]) >= 4 else "L1",
            }
        )
    rows.sort(key=lambda item: (item["run_count"], item["display_name"]), reverse=True)
    return rows


def workflow_run_map(records: list[dict[str, Any]], registry: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_name = {" -> ".join(item["selected_skills"]): item["workflow_id"] for item in registry}
    mapping: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        selected = normalize_list(record.get("skills_selected"))
        if len(selected) < 2:
            continue
        workflow_id = by_name.get(" -> ".join(selected))
        if not workflow_id:
            continue
        mapping.setdefault(workflow_id, []).append(record)
    return mapping


def governance_inventory_map(inventory: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item["name"]): item for item in inventory}


def prior_governance_tiers() -> dict[str, str]:
    path = GOVERNANCE_CURRENT_ROOT / "governance-object-ledger.json"
    payload = load_optional_json(path)
    rows = payload.get("objects") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return {}
    result: dict[str, str] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        object_id = str(item.get("object_id") or "").strip()
        tier = str(item.get("tier_low_mid_high") or "").strip()
        if object_id and tier:
            result[object_id] = tier
    return result


def build_skill_governance_rows(
    inventory: list[dict[str, Any]],
    recent_runs: list[dict[str, Any]],
    *,
    carryover_action_ids: list[str],
) -> list[dict[str, Any]]:
    inventory_map = governance_inventory_map(inventory)
    run_map: dict[str, list[dict[str, Any]]] = {}
    for record in recent_runs:
        for skill in normalize_list(record.get("skills_selected")):
            run_map.setdefault(skill, []).append(record)
    rows: list[dict[str, Any]] = []
    for name, item in sorted(inventory_map.items()):
        records = run_map.get(name, [])
        metrics = run_truth_metrics(records)
        has_external = metrics["external_hits"] > 0
        has_runs = bool(records)
        evidence_grade = evidence_grade_from_flags(
            has_external_verification=has_external or bool(item.get("source_repo")),
            has_local_run_evidence=has_runs or item.get("resource_score", 0) >= 2,
        )
        profile = CORE_PROFILES.get(name)
        cost_efficiency = float((profile.cost_efficiency if profile else 3) * 20)
        workflow_hardness = min(100.0, float(item.get("resource_score", 0)) / 4 * 100)
        reuse_reliability = min(100.0, len(records) * 15.0)
        autonomy_safety = min(100.0, metrics["boundary_integrity"] * 0.6 + metrics["distortion_control"] * 0.4)
        evolution_learning = min(100.0, metrics["effective_density"] * 18 + metrics["candidate_density"] * 14)
        maturity_score = maturity_score_from_dimensions(
            closure_reliability=metrics["closure_reliability"],
            workflow_hardness=workflow_hardness,
            reuse_reliability=reuse_reliability,
            cost_efficiency=cost_efficiency,
            autonomy_safety=autonomy_safety,
            evolution_learning=evolution_learning,
        )
        honesty_score = measured_honesty_score(records, metrics)
        governance_score = round(
            (honesty_score if honesty_score is not None else 70.0) * 0.45
            + maturity_score * 0.35
            + (evidence_grade_score(evidence_grade) * 0.6 + strategic_fit_for_skill(item) * 0.4) * 0.20,
            2,
        )
        tier = governance_tier(
            honesty_score=honesty_score,
            maturity_score=maturity_score,
            evidence_grade=evidence_grade,
            run_support_count=len(records),
            open_question_density=metrics["open_question_density"],
        )
        rows.append(
            {
                "object_id": f"skill:{name}",
                "object_type": "skill",
                "display_name": name,
                "source_refs": sorted(filter(None, [str(item.get("path") or ""), *linked_run_paths(records)])),
                "evidence_grade": evidence_grade,
                "structure_level": str(item.get("resource_completeness") or "low"),
                "honesty_score": honesty_score,
                "honesty_status": "insufficient_evidence" if honesty_score is None else "measured",
                "maturity_score": maturity_score,
                "governance_score": governance_score,
                "tier_low_mid_high": tier,
                "routing_effect": routing_effect_for_object(honesty_score, governance_score),
                "autonomy_cap": autonomy_cap_for_object(honesty_score, governance_score),
                "writeback_trust": writeback_trust_for_object("skill", honesty_score, maturity_score),
                "carryover_action_ids": carryover_action_ids,
                "last_reviewed_at": iso_now(),
                "claim_integrity": metrics["claim_integrity"],
                "evidence_traceability": metrics["evidence_traceability"],
                "boundary_integrity": metrics["boundary_integrity"],
                "distortion_control": metrics["distortion_control"],
                "closure_truthfulness": metrics["closure_truthfulness"],
                "closure_reliability": metrics["closure_reliability"],
                "workflow_hardness": round(workflow_hardness, 2),
                "reuse_reliability": round(reuse_reliability, 2),
                "cost_efficiency": round(cost_efficiency, 2),
                "autonomy_safety": round(autonomy_safety, 2),
                "evolution_learning": round(evolution_learning, 2),
                "run_support_count": len(records),
                "open_question_density": metrics["open_question_density"],
                "inventory_layer": item.get("layer"),
                "inventory_cluster": item.get("cluster"),
            }
        )
    rows.sort(key=lambda item: (item["governance_score"], honesty_sort_value(item.get("honesty_score"))), reverse=True)
    return rows


def build_workflow_governance_rows(
    registry: list[dict[str, Any]],
    workflow_runs: dict[str, list[dict[str, Any]]],
    *,
    carryover_action_ids: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for workflow in registry:
        records = workflow_runs.get(workflow["workflow_id"], [])
        metrics = run_truth_metrics(records)
        evidence_grade = evidence_grade_from_flags(
            has_external_verification=metrics["external_hits"] > 0,
            has_local_run_evidence=bool(records),
        )
        workflow_hardness = structure_level_score(str(workflow.get("structure_level") or "L1"))
        reuse_reliability = min(100.0, workflow["run_count"] * 18.0)
        cost_efficiency = max(40.0, 88.0 - max(0, len(workflow["selected_skills"]) - 2) * 8.0)
        autonomy_safety = min(100.0, metrics["boundary_integrity"] * 0.55 + metrics["distortion_control"] * 0.45)
        evolution_learning = min(100.0, metrics["effective_density"] * 20 + metrics["candidate_density"] * 12)
        maturity_score = maturity_score_from_dimensions(
            closure_reliability=metrics["closure_reliability"],
            workflow_hardness=workflow_hardness,
            reuse_reliability=reuse_reliability,
            cost_efficiency=cost_efficiency,
            autonomy_safety=autonomy_safety,
            evolution_learning=evolution_learning,
        )
        honesty_score = measured_honesty_score(records, metrics)
        governance_score = round(
            (honesty_score if honesty_score is not None else 70.0) * 0.45
            + maturity_score * 0.35
            + (evidence_grade_score(evidence_grade) * 0.7 + 85.0 * 0.3) * 0.20,
            2,
        )
        rows.append(
            {
                "object_id": workflow["workflow_id"],
                "object_type": "workflow",
                "display_name": workflow["display_name"],
                "source_refs": sorted(filter(None, linked_run_paths(records))),
                "evidence_grade": evidence_grade,
                "structure_level": workflow["structure_level"],
                "honesty_score": honesty_score,
                "honesty_status": "insufficient_evidence" if honesty_score is None else "measured",
                "maturity_score": maturity_score,
                "governance_score": governance_score,
                "tier_low_mid_high": governance_tier(
                    honesty_score=honesty_score,
                    maturity_score=maturity_score,
                    evidence_grade=evidence_grade,
                    run_support_count=len(records),
                    open_question_density=metrics["open_question_density"],
                ),
                "routing_effect": routing_effect_for_object(honesty_score, governance_score),
                "autonomy_cap": autonomy_cap_for_object(honesty_score, governance_score),
                "writeback_trust": False,
                "carryover_action_ids": carryover_action_ids,
                "last_reviewed_at": iso_now(),
                "claim_integrity": metrics["claim_integrity"],
                "evidence_traceability": metrics["evidence_traceability"],
                "boundary_integrity": metrics["boundary_integrity"],
                "distortion_control": metrics["distortion_control"],
                "closure_truthfulness": metrics["closure_truthfulness"],
                "closure_reliability": metrics["closure_reliability"],
                "workflow_hardness": round(workflow_hardness, 2),
                "reuse_reliability": round(reuse_reliability, 2),
                "cost_efficiency": round(cost_efficiency, 2),
                "autonomy_safety": round(autonomy_safety, 2),
                "evolution_learning": round(evolution_learning, 2),
                "run_support_count": len(records),
                "open_question_density": metrics["open_question_density"],
                "selected_skills": workflow["selected_skills"],
                "run_count": workflow["run_count"],
            }
        )
    rows.sort(key=lambda item: (item["governance_score"], honesty_sort_value(item.get("honesty_score"))), reverse=True)
    return rows


def build_agent_governance_rows(
    inventory: list[dict[str, Any]],
    recent_runs: list[dict[str, Any]],
    *,
    carryover_action_ids: list[str],
) -> list[dict[str, Any]]:
    inventory_map = governance_inventory_map(inventory)
    names = [name for name in sorted(inventory_map) if name in GOVERNANCE_AGENT_NAMES]
    rows: list[dict[str, Any]] = []
    for name in names:
        item = inventory_map[name]
        records = [record for record in recent_runs if name in normalize_list(record.get("skills_selected"))]
        metrics = run_truth_metrics(records)
        evidence_grade = evidence_grade_from_flags(
            has_external_verification=metrics["external_hits"] > 0,
            has_local_run_evidence=bool(records),
        )
        workflow_hardness = min(100.0, float(item.get("resource_score", 0)) / 4 * 100 + 10.0)
        reuse_reliability = min(100.0, len(records) * 18.0)
        cost_efficiency = 70.0 if name != "self-evolution-max" else 58.0
        autonomy_safety = min(100.0, metrics["boundary_integrity"] * 0.7 + metrics["distortion_control"] * 0.3)
        evolution_learning = min(100.0, metrics["effective_density"] * 18 + metrics["candidate_density"] * 20)
        maturity_score = maturity_score_from_dimensions(
            closure_reliability=metrics["closure_reliability"],
            workflow_hardness=workflow_hardness,
            reuse_reliability=reuse_reliability,
            cost_efficiency=cost_efficiency,
            autonomy_safety=autonomy_safety,
            evolution_learning=evolution_learning,
        )
        honesty_score = measured_honesty_score(records, metrics)
        governance_score = round(
            (honesty_score if honesty_score is not None else 70.0) * 0.45
            + maturity_score * 0.35
            + (evidence_grade_score(evidence_grade) * 0.5 + 92.0 * 0.5) * 0.20,
            2,
        )
        rows.append(
            {
                "object_id": f"agent:{name}",
                "object_type": "agent",
                "display_name": name,
                "source_refs": sorted(filter(None, [str(item.get("path") or ""), *linked_run_paths(records)])),
                "evidence_grade": evidence_grade,
                "structure_level": str(item.get("resource_completeness") or "low"),
                "honesty_score": honesty_score,
                "honesty_status": "insufficient_evidence" if honesty_score is None else "measured",
                "maturity_score": maturity_score,
                "governance_score": governance_score,
                "tier_low_mid_high": governance_tier(
                    honesty_score=honesty_score,
                    maturity_score=maturity_score,
                    evidence_grade=evidence_grade,
                    run_support_count=len(records),
                    open_question_density=metrics["open_question_density"],
                ),
                "routing_effect": routing_effect_for_object(honesty_score, governance_score),
                "autonomy_cap": autonomy_cap_for_object(honesty_score, governance_score),
                "writeback_trust": writeback_trust_for_object("agent", honesty_score, maturity_score),
                "carryover_action_ids": carryover_action_ids,
                "last_reviewed_at": iso_now(),
                "claim_integrity": metrics["claim_integrity"],
                "evidence_traceability": metrics["evidence_traceability"],
                "boundary_integrity": metrics["boundary_integrity"],
                "distortion_control": metrics["distortion_control"],
                "closure_truthfulness": metrics["closure_truthfulness"],
                "closure_reliability": metrics["closure_reliability"],
                "workflow_hardness": round(workflow_hardness, 2),
                "reuse_reliability": round(reuse_reliability, 2),
                "cost_efficiency": round(cost_efficiency, 2),
                "autonomy_safety": round(autonomy_safety, 2),
                "evolution_learning": round(evolution_learning, 2),
                "run_support_count": len(records),
                "open_question_density": metrics["open_question_density"],
            }
        )
    rows.sort(key=lambda item: (item["governance_score"], honesty_sort_value(item.get("honesty_score"))), reverse=True)
    return rows


def build_component_governance_rows(
    component_payload: dict[str, Any],
    *,
    carryover_action_ids: list[str],
) -> list[dict[str, Any]]:
    components = component_payload.get("components") if isinstance(component_payload.get("components"), list) else []
    source_path = str(component_payload.get("path") or "")
    rows: list[dict[str, Any]] = []
    for component in components:
        if not isinstance(component, dict):
            continue
        entropy_risks = normalize_list(component.get("entropy_risks"))
        negative_levers = normalize_list(component.get("negative_entropy_levers"))
        metrics = {
            "claim_integrity": min(100.0, 55.0 + len(normalize_list(component.get("outputs"))) * 8.0),
            "evidence_traceability": 82.0 if source_path else 40.0,
            "boundary_integrity": 90.0 if str(component.get("human_boundary") or "").strip() else 45.0,
            "distortion_control": max(30.0, 100.0 - len(entropy_risks) * 12.0),
            "closure_truthfulness": 78.0 if str(component.get("next_todo") or "").strip() else 52.0,
            "closure_reliability": structure_level_score(component_structure_level(component)),
            "open_question_density": round(len(entropy_risks) / max(1, len(negative_levers) + len(entropy_risks)), 2),
            "effective_density": float(len(negative_levers)),
            "candidate_density": 1.0 if str(component.get("next_todo") or "").strip() else 0.0,
            "external_hits": 0.0,
        }
        honesty_score = honesty_score_from_dimensions(metrics)
        workflow_hardness = structure_level_score(component_structure_level(component))
        reuse_reliability = min(100.0, len(normalize_list(component.get("current_skills"))) * 18.0)
        cost_efficiency = 72.0
        autonomy_safety = min(100.0, metrics["boundary_integrity"] * 0.65 + metrics["distortion_control"] * 0.35)
        evolution_learning = min(100.0, len(negative_levers) * 15.0 + (12.0 if metrics["candidate_density"] else 0.0))
        maturity_score = maturity_score_from_dimensions(
            closure_reliability=metrics["closure_reliability"],
            workflow_hardness=workflow_hardness,
            reuse_reliability=reuse_reliability,
            cost_efficiency=cost_efficiency,
            autonomy_safety=autonomy_safety,
            evolution_learning=evolution_learning,
        )
        evidence_grade = evidence_grade_from_flags(
            has_external_verification=False,
            has_local_run_evidence=bool(source_path),
        )
        governance_score = round(
            honesty_score * 0.45
            + maturity_score * 0.35
            + (evidence_grade_score(evidence_grade) * 0.5 + strategic_fit_for_component(component) * 0.5) * 0.20,
            2,
        )
        rows.append(
            {
                "object_id": f"component:{stable_hash(component_display_name(component))}",
                "object_type": "component",
                "display_name": component_display_name(component),
                "source_refs": [source_path] if source_path else [],
                "evidence_grade": evidence_grade,
                "structure_level": component_structure_level(component),
                "honesty_score": honesty_score,
                "maturity_score": maturity_score,
                "governance_score": governance_score,
                "tier_low_mid_high": governance_tier(
                    honesty_score=honesty_score,
                    maturity_score=maturity_score,
                    evidence_grade=evidence_grade,
                    run_support_count=1 if source_path else 0,
                    open_question_density=metrics["open_question_density"],
                ),
                "routing_effect": routing_effect_for_object(honesty_score, governance_score),
                "autonomy_cap": autonomy_cap_for_object(honesty_score, governance_score),
                "writeback_trust": False,
                "carryover_action_ids": carryover_action_ids,
                "last_reviewed_at": iso_now(),
                "claim_integrity": metrics["claim_integrity"],
                "evidence_traceability": metrics["evidence_traceability"],
                "boundary_integrity": metrics["boundary_integrity"],
                "distortion_control": metrics["distortion_control"],
                "closure_truthfulness": metrics["closure_truthfulness"],
                "closure_reliability": metrics["closure_reliability"],
                "workflow_hardness": round(workflow_hardness, 2),
                "reuse_reliability": round(reuse_reliability, 2),
                "cost_efficiency": round(cost_efficiency, 2),
                "autonomy_safety": round(autonomy_safety, 2),
                "evolution_learning": round(evolution_learning, 2),
                "run_support_count": 1 if source_path else 0,
                "open_question_density": metrics["open_question_density"],
                "system_or_theme": component.get("system_or_theme"),
                "business_chain": component.get("business_chain"),
            }
        )
    rows.sort(key=lambda item: (item["governance_score"], item["honesty_score"]), reverse=True)
    return rows


def governance_evidence_index(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence_rows: list[dict[str, Any]] = []
    for row in rows:
        for index, ref in enumerate(normalize_list(row.get("source_refs")), start=1):
            evidence_rows.append(
                {
                    "Evidence Key": f"{row['object_id']}:{index}",
                    "Object ID": row["object_id"],
                    "对象类型": row["object_type"],
                    "对象名称": row["display_name"],
                    "证据等级": row["evidence_grade"],
                    "证据路径": ref,
                }
            )
    return evidence_rows


def transitions_from_previous(rows: list[dict[str, Any]], previous: dict[str, str]) -> dict[str, list[str]]:
    promoted: list[str] = []
    demoted: list[str] = []
    unchanged: list[str] = []
    rank = {"Low": 0, "Mid": 1, "High": 2}
    for row in rows:
        current = str(row["tier_low_mid_high"])
        prior = previous.get(str(row["object_id"]))
        if not prior:
            unchanged.append(str(row["display_name"]))
            continue
        if rank.get(current, 0) > rank.get(prior, 0):
            promoted.append(str(row["display_name"]))
        elif rank.get(current, 0) < rank.get(prior, 0):
            demoted.append(str(row["display_name"]))
        else:
            unchanged.append(str(row["display_name"]))
    return {"promoted": promoted, "demoted": demoted, "unchanged": unchanged}


def governance_control_tower(
    all_rows: list[dict[str, Any]],
    transitions: dict[str, list[str]],
    governance_window: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    skill_rows = [item for item in all_rows if item["object_type"] == "skill"]
    workflow_rows = [item for item in all_rows if item["object_type"] == "workflow"]
    promote = [
        {
            "name": str(item["display_name"]),
            "why": "高治理分且诚实度过门槛，可继续提权。",
            "routing_effect": str(item.get("routing_effect") or ""),
            "autonomy_cap": str(item.get("autonomy_cap") or ""),
        }
        for item in sorted(
            [
                row
                for row in skill_rows
                if honesty_gate_passed_from_score(row.get("honesty_score")) and row.get("tier_low_mid_high") in {"Mid", "High"}
            ],
            key=lambda row: (float(row.get("governance_score", 0)), honesty_sort_value(row.get("honesty_score"))),
            reverse=True,
        )[:5]
    ]
    demote = [
        {
            "name": str(item["display_name"]),
            "why": "诚实度或成熟度不足，应该继续降权或限制自治。",
            "routing_effect": str(item.get("routing_effect") or ""),
            "autonomy_cap": str(item.get("autonomy_cap") or ""),
        }
        for item in sorted(
            [row for row in skill_rows if honesty_is_low(row.get("honesty_score"))],
            key=lambda row: (honesty_sort_value(row.get("honesty_score")), float(row.get("governance_score", 0))),
        )[:5]
    ]
    retire = [
        {
            "name": str(item["display_name"]),
            "why": "最近支持度低且治理档位低，适合并入 reference 或降为非默认路线。",
        }
        for item in sorted(
            [
                row
                for row in skill_rows
                if int(row.get("run_support_count", 0)) == 0 and row.get("tier_low_mid_high") == "Low"
            ],
            key=lambda row: (float(row.get("governance_score", 0)), str(row.get("display_name"))),
        )[:5]
    ]
    harden = [
        {
            "name": str(item["display_name"]),
            "run_count": int(item.get("run_count", 0)),
            "why": "多 skill 工作流已稳定出现，但仍需 contract/post-check/boundary card。",
        }
        for item in sorted(
            workflow_rows,
            key=lambda row: (-int(row.get("run_count", 0)), honesty_sort_value(row.get("honesty_score"))),
        )[:5]
    ]
    return {
        "promote": promote,
        "demote": demote,
        "retire": retire,
        "workflow_hardening": harden,
        "transition_snapshot": [
            {"direction": "promoted", "names": transitions.get("promoted", [])[:8]},
            {"direction": "demoted", "names": transitions.get("demoted", [])[:8]},
        ],
        "comparable_window": governance_window,
    }


def governance_candidate_actions(
    *,
    all_rows: list[dict[str, Any]],
    low_honesty: list[dict[str, Any]],
    transitions: dict[str, list[str]],
    carryover_action_ids: list[str],
) -> list[dict[str, Any]]:
    skill_rows = [item for item in all_rows if item["object_type"] == "skill"]
    skill_by_name = {str(item["display_name"]): item for item in skill_rows}
    worst_names: list[str] = []
    for name in HONESTY_HARDENING_PRIORITY:
        row = skill_by_name.get(name)
        if row and honesty_is_low(row.get("honesty_score")):
            worst_names.append(name)
    if len(worst_names) < 4:
        fallback = sorted(
            [item for item in skill_rows if honesty_is_low(item.get("honesty_score"))],
            key=lambda item: (-int(item.get("run_support_count", 0)), honesty_sort_value(item.get("honesty_score")), str(item["display_name"])),
        )
        for item in fallback:
            name = str(item["display_name"])
            if name not in worst_names:
                worst_names.append(name)
            if len(worst_names) >= 6:
                break
    workflow_rows = [item for item in all_rows if item["object_type"] == "workflow"]
    low_workflow = [item for item in workflow_rows if item["tier_low_mid_high"] == "Low"]
    actions = [
        {
            "id": "A",
            "type": "honesty hardening",
            "title": "优先修复低诚实度对象",
            "problem": f"当前低诚实度对象主要集中在 {' | '.join(worst_names[:4]) or 'none'}。",
            "proposed_change": "补真实完成边界、开放问题披露和证据追踪，先修最失真的对象，再谈提权。",
            "expected_gain": "先把失真率降下来，避免成熟度或路由信用被虚高信号污染。",
            "risk": "如果同时修太多对象，会把治理动作摊薄。",
            "recommended_next_step": (
                f"先按固定顺序处理 {' -> '.join(worst_names[:5])}。"
                if worst_names
                else "先处理当前最低诚实度对象的 claim/evidence/boundary 三项。"
            ),
        },
        {
            "id": "B",
            "type": "workflow hardening",
            "title": "加厚稳定多 skill 工作流",
            "problem": f"当前识别出 {len(workflow_rows)} 条稳定工作流，其中 {len(low_workflow)} 条仍处于 Low。",
            "proposed_change": "把高频多 skill 链补成显式 workflow registry，并为低诚实或低成熟链增加 post-check 与边界卡。",
            "expected_gain": "减少路由正确但闭环失真的情况，把 skill 组合升级成可验证 workflow。",
            "risk": "如果 workflow 粒度切得太细，会重新制造治理噪音。",
            "recommended_next_step": "先从 run_count 最高的前 3 条 workflow 做 hardening 样板。",
        },
        {
            "id": "C",
            "type": "governance policy",
            "title": "按诚实度门槛收紧提权",
            "problem": f"本轮有 {len(low_honesty)} 个对象不满足 honesty gate；carry-over 动作: {' | '.join(carryover_action_ids) or 'none'}。",
            "proposed_change": "对不达标对象统一执行 routing 不加分、自治上限 suggest、writeback_trust=false，并继续记录 carry-over。",
            "expected_gain": "把治理信用和真实诚实度绑定起来，避免伪闭环对象被持续提权。",
            "risk": "初期会让一部分对象降级，看起来变‘严格’。",
            "recommended_next_step": (
                f"重点复核本轮降级对象：{' | '.join(transitions['demoted'][:4]) or 'none'}。"
            ),
        },
    ]
    return actions


def governance_summary(all_rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {name: 0 for name in GOVERNANCE_TYPES}
    tiers = {"Low": 0, "Mid": 0, "High": 0}
    low_honesty: list[str] = []
    for row in all_rows:
        counts[str(row["object_type"])] = counts.get(str(row["object_type"]), 0) + 1
        tiers[str(row["tier_low_mid_high"])] = tiers.get(str(row["tier_low_mid_high"]), 0) + 1
        if honesty_is_low(row.get("honesty_score")):
            low_honesty.append(str(row["display_name"]))
    return {
        "object_counts": counts,
        "tier_counts": tiers,
        "low_honesty_objects": low_honesty[:12],
    }


def governance_readiness_from_hub(summary: dict[str, Any] | None = None) -> dict[str, Any]:
    summary = summary or latest_hub_summary()
    missing_sources = normalize_list(summary.get("missing_sources")) if isinstance(summary, dict) else []
    transport = summary.get("transport", {}) if isinstance(summary, dict) else {}
    remote_ready = bool(transport.get("remote_reachable"))
    github_backend = str(transport.get("github_backend") or "").strip()
    governance_feishu_configured = bool(os.getenv("AI_DA_GUAN_JIA_GOVERNANCE_FEISHU_LINK", "").strip())
    transport_ready = remote_ready and bool(github_backend)
    multi_source_ready = not missing_sources
    formal_governance_ready = transport_ready and multi_source_ready and governance_feishu_configured
    blockers: list[str] = []
    if not transport_ready:
        blockers.append("hub_transport_not_ready")
    if missing_sources:
        blockers.append("missing_sources")
    if not governance_feishu_configured:
        blockers.append("governance_feishu_not_configured")
    return {
        "transport_ready": transport_ready,
        "multi_source_ready": multi_source_ready,
        "formal_governance_ready": formal_governance_ready,
        "missing_sources": missing_sources,
        "github_backend": github_backend or "none",
        "remote_reachable": remote_ready,
        "governance_feishu_configured": governance_feishu_configured,
        "blockers": blockers,
        "stage": "formal" if formal_governance_ready else "baseline_only",
    }


def latest_governance_review_payload() -> dict[str, Any]:
    state = load_governance_review_state()
    run_id = str(state.get("latest_run_id") or "").strip()
    if not run_id:
        return {}
    try:
        run_dir = find_governance_review_run_dir(run_id)
    except FileNotFoundError:
        return {}
    payload = load_optional_json(run_dir / "review.json")
    return payload if isinstance(payload, dict) else {}


def governance_review_summary_text(review: dict[str, Any]) -> str:
    summary = review["summary"]
    readiness = review.get("readiness", {})
    window = review.get("governance_window", {})
    readiness_note = "当前仅可视为本地基线" if readiness.get("stage") == "baseline_only" else "当前已具备正式治理前提"
    return (
        f"本轮共评估 {review['objects_total']} 个治理对象；"
        f"Low/Mid/High = {summary['tier_counts']['Low']}/{summary['tier_counts']['Mid']}/{summary['tier_counts']['High']}；"
        f"当前低诚实度风险对象包括 {' | '.join(summary['low_honesty_objects'][:3]) or 'none'}；"
        f"可比较窗口 aware/legacy = {window.get('governance_aware_runs', 0)}/{window.get('legacy_runs', 0)}；"
        f"{readiness_note}。"
    )


def build_governance_review_payload(
    *,
    run_id: str,
    created_at: str,
    mode: str,
    skill_rows: list[dict[str, Any]],
    workflow_rows: list[dict[str, Any]],
    agent_rows: list[dict[str, Any]],
    component_rows: list[dict[str, Any]],
    carryover_action_ids: list[str],
) -> dict[str, Any]:
    all_rows = [*skill_rows, *workflow_rows, *agent_rows, *component_rows]
    previous = prior_governance_tiers()
    transitions = transitions_from_previous(all_rows, previous)
    low_honesty = [item for item in all_rows if honesty_is_low(item.get("honesty_score"))]
    readiness = governance_readiness_from_hub()
    window = governance_window_summary(iter_evolution_records(limit=GOVERNANCE_WINDOW_LIMIT), limit=GOVERNANCE_WINDOW_LIMIT)
    control_tower = governance_control_tower(all_rows, transitions, window)
    review = {
        "run_id": run_id,
        "created_at": created_at,
        "mode": mode,
        "objects_total": len(all_rows),
        "summary": governance_summary(all_rows),
        "readiness": readiness,
        "governance_window": window,
        "control_tower": control_tower,
        "carryover_action_ids": carryover_action_ids,
        "transitions": transitions,
        "low_honesty_objects": [
            {
                "object_id": item["object_id"],
                "display_name": item["display_name"],
                "object_type": item["object_type"],
                "honesty_score": item["honesty_score"],
                "tier_low_mid_high": item["tier_low_mid_high"],
            }
            for item in sorted(low_honesty, key=lambda item: item["honesty_score"])[:20]
        ],
        "candidate_actions": governance_candidate_actions(
            all_rows=all_rows,
            low_honesty=low_honesty,
            transitions=transitions,
            carryover_action_ids=carryover_action_ids,
        ),
        "status": "awaiting_human_choice" if mode == "daily" else "backfill_ready",
        "formal_governance_conclusion": bool(readiness["formal_governance_ready"]),
    }
    return review


def governance_rows_to_primary_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(
            {
                "Object ID": row["object_id"],
                "对象类型": row["object_type"],
                "对象名称": row["display_name"],
                "证据等级": row["evidence_grade"],
                "结构层级": str(row["structure_level"]),
                "诚实度": str(row["honesty_score"]),
                "成熟度": str(row["maturity_score"]),
                "治理分": str(row["governance_score"]),
                "档位": row["tier_low_mid_high"],
                "路由影响": row["routing_effect"],
                "自治上限": row["autonomy_cap"],
                "写回信任": "true" if row["writeback_trust"] else "false",
                "Carry-over 动作": " | ".join(normalize_list(row.get("carryover_action_ids"))),
                "最近评估时间": row["last_reviewed_at"],
            }
        )
    return result


def governance_review_batch_row(review: dict[str, Any], run_dir: Path) -> dict[str, str]:
    summary = review["summary"]
    window = review.get("governance_window", {})
    control_tower = review.get("control_tower", {})
    return {
        "Review ID": review["run_id"],
        "日期": parse_datetime(review["created_at"]).strftime("%Y-%m-%d"),
        "创建时间": review["created_at"],
        "模式": review["mode"],
        "状态": review["status"],
        "对象总数": str(review["objects_total"]),
        "对象分布": json.dumps(summary["object_counts"], ensure_ascii=False),
        "档位分布": json.dumps(summary["tier_counts"], ensure_ascii=False),
        "低诚实度对象": " | ".join(summary["low_honesty_objects"]),
        "新晋对象": " | ".join(review["transitions"]["promoted"][:8]),
        "降级对象": " | ".join(review["transitions"]["demoted"][:8]),
        "治理窗口": json.dumps(window, ensure_ascii=False),
        "提权建议": " | ".join(item["name"] for item in control_tower.get("promote", [])),
        "降权建议": " | ".join(item["name"] for item in control_tower.get("demote", [])),
        "退役建议": " | ".join(item["name"] for item in control_tower.get("retire", [])),
        "工作流加厚建议": " | ".join(item["name"] for item in control_tower.get("workflow_hardening", [])),
        "Carry-over 动作": " | ".join(review["carryover_action_ids"]),
        "推荐动作": " | ".join(f"{item['id']}: {item['title']}" for item in review["candidate_actions"]),
        "review.md路径": str((run_dir / "review.md").resolve()),
        "review.json路径": str((run_dir / "review.json").resolve()),
    }


def build_governance_sync_bundle(
    *,
    review: dict[str, Any],
    all_rows: list[dict[str, Any]],
    skill_rows: list[dict[str, Any]],
    workflow_rows: list[dict[str, Any]],
    agent_rows: list[dict[str, Any]],
    component_rows: list[dict[str, Any]],
    run_dir: Path,
) -> dict[str, Any]:
    actions = []
    control_tower = review.get("control_tower", {})
    for action in review["candidate_actions"]:
        actions.append(
            {
                "Action Key": f"{review['run_id']}:{action['id']}",
                "Review ID": review["run_id"],
                "动作ID": action["id"],
                "动作类型": action["type"],
                "标题": action["title"],
                "问题": action["problem"],
                "建议改动": action["proposed_change"],
                "预期收益": action["expected_gain"],
                "风险": action["risk"],
                "下一步建议": action["recommended_next_step"],
                "是否被选中": "true" if review.get("selected_action_id") == action["id"] else "false",
            }
        )
    return {
        "generated_at": iso_now(),
        "run_id": review["run_id"],
        "summary": governance_review_summary_text(review),
        "tables": {
            "评估批次": [governance_review_batch_row(review, run_dir)],
            "治理对象总账": governance_rows_to_primary_table(all_rows),
            "技能评分": governance_rows_to_primary_table(skill_rows),
            "工作流评分": governance_rows_to_primary_table(workflow_rows),
            "治理Agent评分": governance_rows_to_primary_table(agent_rows),
            "组件评分": governance_rows_to_primary_table(component_rows),
            "候选治理动作": actions,
            "证据索引": governance_evidence_index(all_rows),
        },
    }


def render_governance_review_markdown(review: dict[str, Any]) -> str:
    summary = review["summary"]
    readiness = review.get("readiness", {})
    window = review.get("governance_window", {})
    control_tower = review.get("control_tower", {})
    lines = [
        "# Daily Governance Review",
        "",
        "## 今日治理总览",
        "",
        f"- 对象总数: {review['objects_total']}",
        f"- 对象分布: {json.dumps(summary['object_counts'], ensure_ascii=False)}",
        f"- 档位分布: {json.dumps(summary['tier_counts'], ensure_ascii=False)}",
        f"- 低诚实度对象: {' | '.join(summary['low_honesty_objects']) or 'none'}",
        f"- carry-over 动作: {' | '.join(review['carryover_action_ids']) or 'none'}",
        f"- 治理阶段: {readiness.get('stage', 'baseline_only')}",
        f"- 正式治理前提已满足: {bool(review.get('formal_governance_conclusion', False))}",
        f"- 治理阻塞: {' | '.join(normalize_list(readiness.get('blockers'))) or 'none'}",
        f"- 可比较窗口: aware={window.get('governance_aware_runs', 0)} / legacy={window.get('legacy_runs', 0)} / ready={window.get('comparable_window_ready', False)}",
        "",
        "## 当前最值得关注的问题",
        "",
        f"- 新晋对象: {' | '.join(review['transitions']['promoted'][:8]) or 'none'}",
        f"- 降级对象: {' | '.join(review['transitions']['demoted'][:8]) or 'none'}",
        f"- 低诚实度对象样本: {' | '.join(item['display_name'] for item in review['low_honesty_objects'][:5]) or 'none'}",
        "",
        "## 治理控制台建议",
        "",
        f"- 提权建议: {' | '.join(item['name'] for item in control_tower.get('promote', [])) or 'none'}",
        f"- 降权建议: {' | '.join(item['name'] for item in control_tower.get('demote', [])) or 'none'}",
        f"- 退役建议: {' | '.join(item['name'] for item in control_tower.get('retire', [])) or 'none'}",
        f"- 工作流加厚建议: {' | '.join(item['name'] for item in control_tower.get('workflow_hardening', [])) or 'none'}",
        "",
        "## 3 个候选治理动作",
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
            "请回复 `A` / `B` / `C` 之一；即使上一轮未决，下一轮每日治理盘点仍会继续，并把旧动作挂为 carry-over。",
            "",
        ]
    )
    return "\n".join(lines)


def governance_writeback_rows(skill_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    scorecard: list[dict[str, Any]] = []
    routing_credit: list[dict[str, Any]] = []
    autonomy_tier: list[dict[str, Any]] = []
    for row in skill_rows:
        honesty_score = row.get("honesty_score")
        honesty_unknown = honesty_score is None
        honesty_gate_passed = honesty_gate_passed_from_score(honesty_score)
        maturity_score = float(row["maturity_score"])
        governance_score = float(row["governance_score"])
        positive_credit = max(0.0, round(governance_score - 40.0, 2))
        gated_credit = 0.0 if honesty_is_low(honesty_score) else positive_credit
        if honesty_unknown:
            final_tier = "observe"
        elif honesty_is_low(honesty_score):
            final_tier = "suggest"
        else:
            final_tier = str(row["autonomy_cap"])
        token_efficiency = round(min(1.0, max(0.2, float(row["cost_efficiency"]) / 100)), 2)
        time_efficiency = round(min(1.0, max(0.2, float(row["workflow_hardness"]) / 100)), 2)
        handoff_coherence = round(min(1.0, max(0.2, float(row["boundary_integrity"]) / 100)), 2)
        closure_score = weighted_score(
            {
                "closure_quality": clamp_score(float(row["closure_reliability"]) / 20, low=0, high=5),
                "verification_strength": clamp_score(float(row["evidence_traceability"]) / 20, low=0, high=5),
                "token_efficiency": clamp_score(token_efficiency * 5, low=0, high=5),
                "time_efficiency": clamp_score(time_efficiency * 5, low=0, high=5),
                "interruption_efficiency": clamp_score((1.2 - (0.4 if float(row["boundary_integrity"]) >= 70 else 0.8)) * 4, low=0, high=5),
                "reuse_contribution": clamp_score(float(row["reuse_reliability"]) / 20, low=0, high=5),
                "handoff_coherence": clamp_score(handoff_coherence * 5, low=0, high=5),
                "strategic_alignment": 5 if float(row["governance_score"]) >= 60 else 3,
            },
            CLOSURE_SCORE_WEIGHTS,
        )
        scorecard.append(
            {
                "skill": row["display_name"],
                "evaluation_target": "skill",
                "scorecard_version": CLOSURE_SCORECARD_VERSION,
                "closure_quality": round(float(row["closure_reliability"]) / 100, 2),
                "verification_strength": round(float(row["evidence_traceability"]) / 20, 2),
                "token_efficiency": token_efficiency,
                "time_efficiency": time_efficiency,
                "reuse_contribution": int(round(float(row["reuse_reliability"]) / 10)),
                "handoff_coherence": handoff_coherence,
                "distortion_rate": round(max(0.0, 1.0 - float(row["distortion_control"]) / 100), 2),
                "strategic_alignment": round(1.0 if float(row["governance_score"]) >= 60 else 0.5, 2),
                "human_interruption_cost": round(0.4 if float(row["boundary_integrity"]) >= 70 else 0.8, 2),
                "closure_score": closure_score,
                "honesty_score": honesty_score,
                "honesty_status": row.get("honesty_status", "measured"),
                "maturity_score": maturity_score,
                "governance_score": governance_score,
                "tier_low_mid_high": row["tier_low_mid_high"],
                "writeback_trust": row["writeback_trust"],
            }
        )
        routing_credit.append(
            {
                "skill": row["display_name"],
                "routing_credit": gated_credit,
                "honesty_gate_passed": honesty_gate_passed,
                "honesty_status": row.get("honesty_status", "measured"),
                "closure_score": closure_score,
                "explanation": (
                    "当前缺少近期运行证据，先保持软门禁，不直接判定为低诚实度。"
                    if honesty_unknown
                    else (
                        "诚实度未达门槛，不给予正向路由加成。"
                        if honesty_is_low(honesty_score)
                        else "按治理分给予路由信用，同时保留诚实度门槛。"
                    )
                ),
            }
        )
        autonomy_tier.append(
            {
                "skill": row["display_name"],
                "autonomy_tier": final_tier,
                "routing_credit": gated_credit,
                "closure_score": closure_score,
                "honesty_gate_passed": honesty_gate_passed,
                "honesty_status": row.get("honesty_status", "measured"),
            }
        )
    routing_credit.sort(key=lambda item: item["routing_credit"], reverse=True)
    autonomy_tier.sort(key=lambda item: (AUTONOMY_TIERS.index(item["autonomy_tier"]), -item["routing_credit"]))
    return scorecard, routing_credit, autonomy_tier


def write_governance_current_bundle(
    *,
    skill_rows: list[dict[str, Any]],
    workflow_rows: list[dict[str, Any]],
    agent_rows: list[dict[str, Any]],
    component_rows: list[dict[str, Any]],
    review: dict[str, Any],
    workflow_registry: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    ensure_dir(GOVERNANCE_CURRENT_ROOT)
    ensure_dir(STRATEGY_CURRENT_ROOT)
    all_rows = [*skill_rows, *workflow_rows, *agent_rows, *component_rows]
    recent_runs = iter_evolution_records(limit=GOVERNANCE_WINDOW_LIMIT)
    calibration = governance_calibration_payload(recent_runs)
    write_json(
        GOVERNANCE_CURRENT_ROOT / "governance-object-ledger.json",
        {"generated_at": iso_now(), "objects": all_rows, "review_run_id": review["run_id"]},
    )
    write_json(GOVERNANCE_CURRENT_ROOT / "skills-governance.json", skill_rows)
    write_json(GOVERNANCE_CURRENT_ROOT / "workflows-governance.json", workflow_rows)
    write_json(GOVERNANCE_CURRENT_ROOT / "agents-governance.json", agent_rows)
    write_json(GOVERNANCE_CURRENT_ROOT / "components-governance.json", component_rows)
    write_json(GOVERNANCE_CURRENT_ROOT / "workflow-registry.json", workflow_registry)
    write_json(GOVERNANCE_CURRENT_ROOT / "evidence-index.json", evidence_rows)
    write_json(GOVERNANCE_CURRENT_ROOT / "governance-calibration.json", calibration)
    scorecard, routing_credit, autonomy_tier = governance_writeback_rows(skill_rows)
    write_json(STRATEGY_CURRENT_ROOT / "agent-scorecard.json", scorecard)
    write_json(STRATEGY_CURRENT_ROOT / "routing-credit.json", routing_credit)
    write_json(STRATEGY_CURRENT_ROOT / "autonomy-tier.json", autonomy_tier)
    write_json(
        STRATEGY_CURRENT_ROOT / "writeback-trust.json",
        [
            {
                "skill": row["display_name"],
                "writeback_trust": bool(row["writeback_trust"]),
                "honesty_gate_passed": honesty_gate_passed_from_score(row.get("honesty_score")),
                "honesty_status": row.get("honesty_status", "measured"),
            }
            for row in skill_rows
        ],
    )
    return {
        "all_rows": all_rows,
        "scorecard": scorecard,
        "routing_credit": routing_credit,
        "autonomy_tier": autonomy_tier,
        "governance_calibration": calibration,
    }


def write_governance_review_materials(
    run_dir: Path,
    *,
    review: dict[str, Any],
    skill_rows: list[dict[str, Any]],
    workflow_rows: list[dict[str, Any]],
    agent_rows: list[dict[str, Any]],
    component_rows: list[dict[str, Any]],
    workflow_registry: list[dict[str, Any]],
) -> dict[str, Any]:
    all_rows = [*skill_rows, *workflow_rows, *agent_rows, *component_rows]
    evidence_rows = governance_evidence_index(all_rows)
    current_bundle = write_governance_current_bundle(
        skill_rows=skill_rows,
        workflow_rows=workflow_rows,
        agent_rows=agent_rows,
        component_rows=component_rows,
        review=review,
        workflow_registry=workflow_registry,
        evidence_rows=evidence_rows,
    )
    bundle = build_governance_sync_bundle(
        review=review,
        all_rows=all_rows,
        skill_rows=skill_rows,
        workflow_rows=workflow_rows,
        agent_rows=agent_rows,
        component_rows=component_rows,
        run_dir=run_dir,
    )
    write_json(run_dir / "review.json", review)
    write_json(run_dir / "governance-object-ledger.json", {"objects": all_rows})
    write_json(run_dir / "skills-governance.json", skill_rows)
    write_json(run_dir / "workflows-governance.json", workflow_rows)
    write_json(run_dir / "agents-governance.json", agent_rows)
    write_json(run_dir / "components-governance.json", component_rows)
    write_json(run_dir / "workflow-registry.json", workflow_registry)
    write_json(run_dir / "evidence-index.json", evidence_rows)
    write_json(run_dir / "action-candidates.json", review["candidate_actions"])
    write_json(run_dir / "feishu-sync-bundle.json", bundle)
    (run_dir / "review.md").write_text(render_governance_review_markdown(review), encoding="utf-8")
    return {"bundle": bundle, "current_bundle": current_bundle}


def honesty_hardening_targets(skill_rows: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    by_name = {str(item["display_name"]): item for item in skill_rows}
    targets: list[dict[str, Any]] = []
    for name in HONESTY_HARDENING_PRIORITY:
        row = by_name.get(name)
        if row and honesty_is_low(row.get("honesty_score")):
            targets.append(row)
    if len(targets) < limit:
        fallback = sorted(
            [item for item in skill_rows if honesty_is_low(item.get("honesty_score")) and item not in targets],
            key=lambda item: (-int(item.get("run_support_count", 0)), honesty_sort_value(item.get("honesty_score")), str(item["display_name"])),
        )
        targets.extend(fallback[: max(0, limit - len(targets))])
    return targets[:limit]


def dimension_gaps(row: dict[str, Any]) -> list[str]:
    mapping = [
        ("claim_integrity", "claim_integrity"),
        ("evidence_traceability", "evidence_traceability"),
        ("boundary_integrity", "boundary_integrity"),
        ("distortion_control", "distortion_control"),
        ("closure_truthfulness", "closure_truthfulness"),
    ]
    gaps = [label for key, label in mapping if float(row.get(key, 0)) < 70]
    return gaps


def build_honesty_hardening_brief(skill_rows: list[dict[str, Any]]) -> dict[str, Any]:
    targets = honesty_hardening_targets(skill_rows)
    rows = []
    for index, row in enumerate(targets, start=1):
        gaps = dimension_gaps(row)
        rows.append(
            {
                "priority": index,
                "object_id": row["object_id"],
                "skill": row["display_name"],
                "current_honesty_score": row["honesty_score"],
                "current_tier": row["tier_low_mid_high"],
                "run_support_count": row.get("run_support_count", 0),
                "focus_dimensions": [gap for gap in gaps if gap in {"claim_integrity", "evidence_traceability", "boundary_integrity"}] or gaps[:3],
                "source_refs": normalize_list(row.get("source_refs"))[:5],
                "required_fixes": [
                    "明确宣称完成范围，只写真实完成，不偷带未完成部分。",
                    "补最小证据链，至少能追到 run / artifact / 外部镜像之一。",
                    "补人类边界和禁止自动越界说明。",
                ],
                "acceptance_signals": [
                    "honesty_score >= 70",
                    "routing_credit 不再被 honesty gate 清零",
                    "review-governance 中从 Low 进入 Mid 或至少脱离低诚实度样本名单",
                ],
            }
        )
    return {
        "generated_at": iso_now(),
        "title": "Honesty Hardening Brief",
        "targets": rows,
    }


def render_honesty_hardening_markdown(brief: dict[str, Any]) -> str:
    lines = ["# Honesty Hardening Brief", ""]
    for item in brief.get("targets", []):
        lines.extend(
            [
                f"## P{item['priority']} {item['skill']}",
                "",
                f"- Object ID: `{item['object_id']}`",
                f"- Current Honesty: `{item['current_honesty_score']}`",
                f"- Current Tier: `{item['current_tier']}`",
                f"- Run Support Count: `{item['run_support_count']}`",
                f"- Focus Dimensions: {' | '.join(item['focus_dimensions']) or 'none'}",
                f"- Source Refs: {' | '.join(item['source_refs']) or 'none'}",
                f"- Required Fixes: {' | '.join(item['required_fixes'])}",
                f"- Acceptance Signals: {' | '.join(item['acceptance_signals'])}",
                "",
            ]
        )
    return "\n".join(lines)


def build_workflow_hardening_brief(
    workflow_rows: list[dict[str, Any]],
    workflow_registry: list[dict[str, Any]],
) -> dict[str, Any]:
    registry_map = {str(item["workflow_id"]): item for item in workflow_registry}
    targets = sorted(
        workflow_rows,
        key=lambda item: (-int(item.get("run_count", 0)), honesty_sort_value(item.get("honesty_score")), str(item["display_name"])),
    )[:3]
    rows = []
    for index, row in enumerate(targets, start=1):
        registry = registry_map.get(str(row["object_id"]), {})
        rows.append(
            {
                "priority": index,
                "workflow_id": row["object_id"],
                "display_name": row["display_name"],
                "selected_skills": normalize_list(registry.get("selected_skills") or row.get("selected_skills")),
                "task_samples": normalize_list(registry.get("task_samples"))[:5],
                "current_tier": row["tier_low_mid_high"],
                "current_honesty_score": row["honesty_score"],
                "current_maturity_score": row["maturity_score"],
                "required_contract": [
                    "触发条件",
                    "输出契约",
                    "post-check",
                    "human boundary card",
                    "failure examples",
                ],
                "acceptance_signals": [
                    "workflow tier 升到 Mid",
                    "workflow honesty_score >= 70",
                    "review-governance 中 workflow 不再主要靠单个 skill 临场发挥",
                ],
            }
        )
    return {
        "generated_at": iso_now(),
        "title": "Workflow Hardening Brief",
        "targets": rows,
    }


def render_workflow_hardening_markdown(brief: dict[str, Any]) -> str:
    lines = ["# Workflow Hardening Brief", ""]
    for item in brief.get("targets", []):
        lines.extend(
            [
                f"## P{item['priority']} {item['display_name']}",
                "",
                f"- Workflow ID: `{item['workflow_id']}`",
                f"- Selected Skills: {' -> '.join(item['selected_skills']) or 'none'}",
                f"- Task Samples: {' | '.join(item['task_samples']) or 'none'}",
                f"- Current Tier: `{item['current_tier']}`",
                f"- Current Honesty: `{item['current_honesty_score']}`",
                f"- Current Maturity: `{item['current_maturity_score']}`",
                f"- Required Contract: {' | '.join(item['required_contract'])}",
                f"- Acceptance Signals: {' | '.join(item['acceptance_signals'])}",
                "",
            ]
        )
    return "\n".join(lines)


def build_governance_policy_brief(review: dict[str, Any]) -> dict[str, Any]:
    readiness = review.get("readiness", {})
    return {
        "generated_at": iso_now(),
        "title": "Governance Policy Brief",
        "selected_action_id": review.get("selected_action_id", ""),
        "policy": {
            "honesty_gate": "honesty_score < 70 时 routing_credit 不加分、autonomy 上限 suggest、writeback_trust=false",
            "baseline_stage": "多源接入 + transport + governance Feishu 未完成前，所有 governance score 只视为本地基线",
            "carryover_rule": "上一轮未决动作进入下一轮 carry-over，不阻塞日评",
        },
        "current_blockers": normalize_list(readiness.get("blockers")),
        "acceptance_signals": [
            "transport_ready = true",
            "missing_sources = none",
            "governance Feishu sync 可成功 apply",
        ],
    }


def render_governance_policy_markdown(brief: dict[str, Any]) -> str:
    policy = brief.get("policy", {})
    lines = [
        "# Governance Policy Brief",
        "",
        f"- Selected Action: `{brief.get('selected_action_id', '')}`",
        f"- Honesty Gate: {policy.get('honesty_gate', '')}",
        f"- Baseline Stage Rule: {policy.get('baseline_stage', '')}",
        f"- Carry-over Rule: {policy.get('carryover_rule', '')}",
        f"- Current Blockers: {' | '.join(brief.get('current_blockers', [])) or 'none'}",
        f"- Acceptance Signals: {' | '.join(brief.get('acceptance_signals', [])) or 'none'}",
        "",
    ]
    return "\n".join(lines)


def write_governance_action_artifacts(
    *,
    run_dir: Path,
    review: dict[str, Any],
    skill_rows: list[dict[str, Any]],
    workflow_rows: list[dict[str, Any]],
    workflow_registry: list[dict[str, Any]],
) -> list[str]:
    selected = str(review.get("selected_action_id") or "").strip().upper()
    generated: list[str] = []
    if selected == "A":
        brief = build_honesty_hardening_brief(skill_rows)
        write_json(run_dir / "honesty-hardening-brief.json", brief)
        (run_dir / "honesty-hardening-brief.md").write_text(render_honesty_hardening_markdown(brief), encoding="utf-8")
        write_json(GOVERNANCE_CURRENT_ROOT / "honesty-hardening-brief.json", brief)
        (GOVERNANCE_CURRENT_ROOT / "honesty-hardening-brief.md").write_text(render_honesty_hardening_markdown(brief), encoding="utf-8")
        generated.extend(["honesty-hardening-brief.json", "honesty-hardening-brief.md"])
    elif selected == "B":
        brief = build_workflow_hardening_brief(workflow_rows, workflow_registry)
        write_json(run_dir / "workflow-hardening-brief.json", brief)
        (run_dir / "workflow-hardening-brief.md").write_text(render_workflow_hardening_markdown(brief), encoding="utf-8")
        write_json(GOVERNANCE_CURRENT_ROOT / "workflow-hardening-brief.json", brief)
        (GOVERNANCE_CURRENT_ROOT / "workflow-hardening-brief.md").write_text(render_workflow_hardening_markdown(brief), encoding="utf-8")
        generated.extend(["workflow-hardening-brief.json", "workflow-hardening-brief.md"])
    elif selected == "C":
        brief = build_governance_policy_brief(review)
        write_json(run_dir / "governance-policy-brief.json", brief)
        (run_dir / "governance-policy-brief.md").write_text(render_governance_policy_markdown(brief), encoding="utf-8")
        write_json(GOVERNANCE_CURRENT_ROOT / "governance-policy-brief.json", brief)
        (GOVERNANCE_CURRENT_ROOT / "governance-policy-brief.md").write_text(render_governance_policy_markdown(brief), encoding="utf-8")
        generated.extend(["governance-policy-brief.json", "governance-policy-brief.md"])
    return generated

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
    governance = load_governance_signals()
    routing_credit_map = governance["routing_credit"] if isinstance(governance.get("routing_credit"), dict) else {}
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
    for item in review.get("external_signal_summary", {}).get("shortlist_titles", []):
        findings.append(
            {
                "type": "external_signal",
                "title": item,
                "object_1": item,
                "object_2": "",
                "conclusion": "该候选已进入最新 skill scout shortlist，需要在本地治理语境下判断是 watch、验证还是入 adoption queue。",
                "suggested_rule": "外部高置信候选先补一手证据和接入边界，再决定是否升级为本地能力。",
            }
        )
    for blocker in normalize_list(review.get("env_blockers")):
        findings.append(
            {
                "type": "scout_env_blocker",
                "title": blocker,
                "object_1": blocker,
                "object_2": "",
                "conclusion": "外部线索接入已识别出环境阻塞项，当前默认不自动安装。",
                "suggested_rule": "优先治理真实必需的环境前置，避免把探索任务变成全面装机。",
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
    if routing_credit_map:
        sorted_credit = sorted(routing_credit_map.items(), key=lambda item: item[1], reverse=True)
        risky = [
            (name, credit)
            for name, credit in sorted_credit
            if credit >= 40 and usage_counts.get(name, 0) == 0
        ]
        fallback = [
            (name, usage)
            for name, usage in sorted(usage_counts.items(), key=lambda item: item[1], reverse=True)
            if usage >= 2 and routing_credit_map.get(name, 0) < 20
        ]
        if risky:
            findings.append(
                {
                    "type": "routing_credit_risk",
                    "title": "高 credit 但低任务适配的风险 skill",
                    "object_1": " | ".join(f"{name} ({credit:.1f})" for name, credit in risky[:5]),
                    "object_2": "",
                    "conclusion": "这些 skill 的治理信用较高，但近期没有进入实际闭环，说明它们更像潜力资产而不是当前稳态主力。",
                    "suggested_rule": "补边界说明和失败样例，避免 routing credit 被误当成跨域通行证。",
                }
            )
        if fallback:
            findings.append(
                {
                    "type": "routing_credit_fallback",
                    "title": "高使用但低 credit 的回退候选",
                    "object_1": " | ".join(f"{name} ({usage})" for name, usage in fallback[:5]),
                    "object_2": "",
                    "conclusion": "这些 skill 仍在一线反复承担任务，但治理信用偏低，说明 scorecard 与真实使用之间还需要校准。",
                    "suggested_rule": "复核闭环证据、失真惩罚和复用贡献，必要时调整 credit 公式。",
                }
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
            "proposal_status": "pending_approval",
            "approval_state": "pending",
            "launch_state": "not_started",
            "external_execution_allowed": False,
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
            "proposal_status": "pending_approval",
            "approval_state": "pending",
            "launch_state": "not_started",
            "external_execution_allowed": False,
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
            "proposal_status": "pending_approval",
            "approval_state": "pending",
            "launch_state": "not_started",
            "external_execution_allowed": False,
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


def build_chain_scorecard(recent_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in recent_runs[:120]:
        skills_selected = normalize_list(record.get("skills_selected"))
        budget_profile = record.get("budget_profile") if isinstance(record.get("budget_profile"), dict) else {}
        if not budget_profile:
            budget_profile = resolve_budget_profile(
                detect_signals(str(record.get("task_text") or "")),
                skills_selected,
            )
        closure_assessment = build_closure_assessment(
            verification=normalize_verification_result(record.get("verification_result")),
            skills_selected=skills_selected,
            effective_patterns=normalize_list(record.get("effective_patterns")),
            governance_status=str(record.get("governance_signal_status") or "missing"),
            human_boundary=str(record.get("human_boundary") or ""),
            budget_profile=budget_profile,
            observed_token_usage=(
                float(record["observed_token_usage"])
                if str(record.get("observed_token_usage") or "").strip()
                else None
            ),
            observed_duration_minutes=(
                float(record["observed_duration_minutes"])
                if str(record.get("observed_duration_minutes") or "").strip()
                else None
            ),
        )
        rows.append(
            {
                "run_id": str(record.get("run_id") or ""),
                "created_at": str(record.get("created_at") or ""),
                "evaluation_target": "execution_chain",
                "scorecard_version": CLOSURE_SCORECARD_VERSION,
                "task_text": str(record.get("task_text") or ""),
                "skills_selected": skills_selected,
                "budget_tier": budget_profile.get("tier"),
                "closure_score": closure_assessment["closure_score"],
                "metrics": closure_assessment["metrics"],
                "gates": closure_assessment["gates"],
                "budget_assessment": closure_assessment["budget_assessment"],
            }
        )
    rows.sort(key=lambda item: (item["closure_score"], item["created_at"]), reverse=True)
    return rows


def build_object_scorecard(
    *,
    inventory: list[dict[str, Any]],
    recent_runs: list[dict[str, Any]],
    governance_skill_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if governance_skill_rows:
        scorecard, _, autonomy_tier = governance_writeback_rows(governance_skill_rows)
        autonomy_map = {item["skill"]: item for item in autonomy_tier}
        rows: list[dict[str, Any]] = []
        for item in scorecard:
            autonomy_item = autonomy_map.get(item["skill"], {})
            rows.append(
                {
                    "object_type": "skill",
                    "object_name": item["skill"],
                    "evaluation_target": item.get("evaluation_target", "skill"),
                    "scorecard_version": item.get("scorecard_version", CLOSURE_SCORECARD_VERSION),
                    "closure_score": item.get("closure_score", 0),
                    "routing_credit": autonomy_item.get("routing_credit", 0),
                    "autonomy_tier": autonomy_item.get("autonomy_tier", "observe"),
                    "writeback_trust": bool(item.get("writeback_trust")),
                    "metrics": {
                        "closure_quality": item.get("closure_quality"),
                        "verification_strength": item.get("verification_strength"),
                        "token_efficiency": item.get("token_efficiency"),
                        "time_efficiency": item.get("time_efficiency"),
                        "reuse_contribution": item.get("reuse_contribution"),
                        "handoff_coherence": item.get("handoff_coherence"),
                        "distortion_rate": item.get("distortion_rate"),
                    },
                }
            )
        rows.sort(key=lambda item: item["closure_score"], reverse=True)
        return rows

    agent_scorecard = build_agent_scorecard(inventory, recent_runs)
    routing_credit = build_routing_credit(agent_scorecard)
    autonomy_tier = build_autonomy_tiers(agent_scorecard, routing_credit)
    credit_map = {item["skill"]: item for item in routing_credit}
    tier_map = {item["skill"]: item for item in autonomy_tier}
    rows = []
    for item in agent_scorecard:
        rows.append(
            {
                "object_type": "skill",
                "object_name": item["skill"],
                "evaluation_target": item.get("evaluation_target", "skill"),
                "scorecard_version": item.get("scorecard_version", CLOSURE_SCORECARD_VERSION),
                "closure_score": item.get("closure_score", 0),
                "routing_credit": credit_map.get(item["skill"], {}).get("routing_credit", 0),
                "autonomy_tier": tier_map.get(item["skill"], {}).get("autonomy_tier", "observe"),
                "writeback_trust": False,
                "metrics": {
                    "closure_quality": item.get("closure_quality"),
                    "verification_strength": item.get("verification_strength"),
                    "token_efficiency": item.get("token_efficiency"),
                    "time_efficiency": item.get("time_efficiency"),
                    "reuse_contribution": item.get("reuse_contribution"),
                    "handoff_coherence": item.get("handoff_coherence"),
                    "distortion_rate": item.get("distortion_rate"),
                },
            }
        )
    rows.sort(key=lambda item: item["closure_score"], reverse=True)
    return rows


def build_budget_ledger(recent_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ledger: list[dict[str, Any]] = []
    for record in recent_runs[:120]:
        task_text = str(record.get("task_text") or "")
        skills_selected = normalize_list(record.get("skills_selected"))
        budget_profile = record.get("budget_profile") if isinstance(record.get("budget_profile"), dict) else {}
        if not budget_profile:
            budget_profile = resolve_budget_profile(detect_signals(task_text), skills_selected)
        assessment = budget_assessment(
            budget_profile,
            observed_token_usage=(
                float(record["observed_token_usage"])
                if str(record.get("observed_token_usage") or "").strip()
                else None
            ),
            observed_duration_minutes=(
                float(record["observed_duration_minutes"])
                if str(record.get("observed_duration_minutes") or "").strip()
                else None
            ),
            selected_skills=skills_selected,
        )
        ledger.append(
            {
                "run_id": str(record.get("run_id") or ""),
                "created_at": str(record.get("created_at") or ""),
                "budget_profile": budget_profile,
                "selected_skills": skills_selected,
                "observed_token_usage": assessment["observed_token_usage"],
                "observed_duration_minutes": assessment["observed_duration_minutes"],
                "token_efficiency": assessment["token_efficiency"],
                "time_efficiency": assessment["time_efficiency"],
                "token_measurement_mode": assessment["token_measurement_mode"],
                "time_measurement_mode": assessment["time_measurement_mode"],
                "soft_budget_exceeded": assessment["soft_budget_exceeded"],
                "hard_budget_exceeded": assessment["hard_budget_exceeded"],
            }
        )
    ledger.sort(key=lambda item: item["created_at"], reverse=True)
    return ledger


def build_incentive_decisions(recent_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for record in recent_runs[:120]:
        task_text = str(record.get("task_text") or "")
        skills_selected = normalize_list(record.get("skills_selected"))
        budget_profile = record.get("budget_profile") if isinstance(record.get("budget_profile"), dict) else {}
        if not budget_profile:
            budget_profile = resolve_budget_profile(detect_signals(task_text), skills_selected)
        closure_assessment = build_closure_assessment(
            verification=normalize_verification_result(record.get("verification_result")),
            skills_selected=skills_selected,
            effective_patterns=normalize_list(record.get("effective_patterns")),
            governance_status=str(record.get("governance_signal_status") or "missing"),
            human_boundary=str(record.get("human_boundary") or ""),
            budget_profile=budget_profile,
            observed_token_usage=(
                float(record["observed_token_usage"])
                if str(record.get("observed_token_usage") or "").strip()
                else None
            ),
            observed_duration_minutes=(
                float(record["observed_duration_minutes"])
                if str(record.get("observed_duration_minutes") or "").strip()
                else None
            ),
        )
        decision = build_incentive_decision(
            closure_assessment=closure_assessment,
            selected_skills=skills_selected,
            governance_status=str(record.get("governance_signal_status") or "missing"),
        )
        decision["run_id"] = str(record.get("run_id") or "")
        decision["created_at"] = str(record.get("created_at") or "")
        decision["closure_score"] = closure_assessment["closure_score"]
        decisions.append(decision)
    decisions.sort(key=lambda item: (item["closure_score"], item["created_at"]), reverse=True)
    return decisions


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
        token_efficiency = round(1.0 if reuse_contribution <= 2 else 0.8 if reuse_contribution <= 5 else 0.6, 2)
        time_efficiency = round(max(0.4, 1.0 - min(distortion_rate, 3) * 0.15), 2)
        handoff_coherence = round(max(0.4, 1.0 - min(reuse_contribution, 6) * 0.08), 2)
        closure_score = weighted_score(
            {
                "closure_quality": clamp_score(closure_quality * 5, low=0, high=5),
                "verification_strength": clamp_score(min(verification_strength, 5), low=0, high=5),
                "token_efficiency": clamp_score(token_efficiency * 5, low=0, high=5),
                "time_efficiency": clamp_score(time_efficiency * 5, low=0, high=5),
                "interruption_efficiency": clamp_score((1.2 - human_interruption_cost) * 4, low=0, high=5),
                "reuse_contribution": clamp_score(min(reuse_contribution, 5), low=0, high=5),
                "handoff_coherence": clamp_score(handoff_coherence * 5, low=0, high=5),
                "strategic_alignment": clamp_score(strategic_alignment * 5, low=0, high=5),
            },
            CLOSURE_SCORE_WEIGHTS,
        )
        rows.append(
            {
                "skill": name,
                "evaluation_target": "skill",
                "scorecard_version": CLOSURE_SCORECARD_VERSION,
                "closure_quality": closure_quality,
                "verification_strength": verification_strength,
                "token_efficiency": token_efficiency,
                "time_efficiency": time_efficiency,
                "reuse_contribution": reuse_contribution,
                "handoff_coherence": handoff_coherence,
                "distortion_rate": distortion_rate,
                "strategic_alignment": strategic_alignment,
                "human_interruption_cost": human_interruption_cost,
                "closure_score": closure_score,
            }
        )
    rows.sort(key=lambda item: (item["closure_quality"], item["verification_strength"], item["reuse_contribution"]), reverse=True)
    return rows


def build_routing_credit(scorecard: list[dict[str, Any]]) -> list[dict[str, Any]]:
    credits: list[dict[str, Any]] = []
    for item in scorecard:
        composite = round(
            float(item.get("closure_score", 0))
            + float(item.get("strategic_alignment", 0)) * 10
            - float(item.get("distortion_rate", 0)) * 10
            - float(item.get("human_interruption_cost", 0)) * 8,
            2,
        )
        credits.append(
            {
                "skill": item["skill"],
                "routing_credit": composite,
                "closure_score": float(item.get("closure_score", 0)),
                "explanation": "奖励真闭环、强验真、战略对齐和预算内完成；惩罚高失真和高人类打扰成本。",
            }
        )
    credits.sort(key=lambda item: item["routing_credit"], reverse=True)
    return credits


def build_autonomy_tiers(scorecard: list[dict[str, Any]], routing_credit: list[dict[str, Any]]) -> list[dict[str, Any]]:
    credits = {item["skill"]: item["routing_credit"] for item in routing_credit}
    tiers: list[dict[str, Any]] = []
    for item in scorecard:
        credit = credits.get(item["skill"], 0.0)
        if credit >= 80 and float(item.get("distortion_rate", 0)) <= 0.3:
            tier = "guarded-autonomy"
        elif credit >= 65:
            tier = "trusted-suggest"
        elif credit >= 45:
            tier = "suggest"
        else:
            tier = "observe"
        tiers.append(
            {
                "skill": item["skill"],
                "autonomy_tier": tier,
                "routing_credit": credit,
                "closure_score": float(item.get("closure_score", 0)),
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
    hub_summary: dict[str, Any] | None = None,
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
        lines.append(
            f"- {item['id']} [{item['goal_id']}] {item['title']} :: status={item.get('proposal_status', 'pending_approval')} :: approval={item.get('approval_state', 'pending')}"
        )
    if hub_summary:
        lines.extend(
            [
                "",
                "## Latest Hub Audit",
                "",
                f"- Sources: {hub_summary.get('sources_total', 0)}",
                f"- Expected Sources: {' | '.join(hub_summary.get('expected_sources', [])) or 'none'}",
                f"- Missing Sources: {' | '.join(hub_summary.get('missing_sources', [])) or 'none'}",
                f"- Tasks: {hub_summary.get('tasks_total', 0)}",
                f"- Skills: {hub_summary.get('skills_total', 0)}",
                f"- Task Maturity H/M/L: {hub_summary.get('task_maturity', {}).get('High', 0)} / {hub_summary.get('task_maturity', {}).get('Medium', 0)} / {hub_summary.get('task_maturity', {}).get('Low', 0)}",
                f"- Skill Maturity H/M/L: {hub_summary.get('skill_maturity', {}).get('High', 0)} / {hub_summary.get('skill_maturity', {}).get('Medium', 0)} / {hub_summary.get('skill_maturity', {}).get('Low', 0)}",
            ]
        )
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
            "- Do not reward low token or short completion time when closure quality or verification strength fails the gate.",
            "- Penalize high human interruption when the task did not require a human boundary.",
            "- Penalize chain inflation when multi-agent stacking does not materially improve closure.",
            "- Penalize hard-budget overruns by default unless the run proves meaningfully stronger closure.",
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
            "- Promote a skill when closure score stays high, verification stays strong, and budget performance remains acceptable.",
            "- Promote guarded autonomy only after repeated honest runs; honesty gate is still a hard precondition.",
            "- Demote a skill when it creates repeated open questions, pseudo-completion, overlap, or unnecessary human interruption.",
            "- Promotion changes routing priority, autonomy tier, resource preference, and writeback trust, not the skill's identity.",
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
    proposal_queue = proposal_queue_from_threads(thread_proposals)
    recruitment = build_recruitment_candidates(gap_report)
    calibration = governance_calibration_payload(recent_runs)
    governance_skill_rows = load_optional_json_list(GOVERNANCE_CURRENT_ROOT / "skills-governance.json")
    if governance_skill_rows:
        scorecard, routing_credit, autonomy_tier = governance_writeback_rows(governance_skill_rows)
    else:
        scorecard = build_agent_scorecard(inventory, recent_runs)
        routing_credit = build_routing_credit(scorecard)
        autonomy_tier = build_autonomy_tiers(scorecard, routing_credit)
    budget_profile = {
        "generated_at": iso_now(),
        "mode": "tiered",
        "profiles": DEFAULT_BUDGET_PROFILES,
        "scorecard_version": ROUTE_SCORECARD_VERSION,
    }
    chain_scorecard = build_chain_scorecard(recent_runs)
    object_scorecard = build_object_scorecard(
        inventory=inventory,
        recent_runs=recent_runs,
        governance_skill_rows=governance_skill_rows or None,
    )
    budget_ledger = build_budget_ledger(recent_runs)
    incentive_decision = build_incentive_decisions(recent_runs)
    initiative_brief = initiatives[0] if initiatives else {}
    hub_summary = latest_hub_summary()
    hub_recommendations = latest_hub_recommendations()

    write_json(STRATEGY_CURRENT_ROOT / "strategic-goals.json", goals)
    write_json(STRATEGY_CURRENT_ROOT / "strategy-map.json", strategy_map)
    write_json(STRATEGY_CURRENT_ROOT / "initiative-registry.json", initiatives)
    write_json(STRATEGY_CURRENT_ROOT / "active-threads.json", active_threads)
    write_json(STRATEGY_CURRENT_ROOT / "initiative-brief.json", initiative_brief)
    write_json(STRATEGY_CURRENT_ROOT / "thread-proposal.json", thread_proposals)
    write_json(STRATEGY_CURRENT_ROOT / "proposal-queue.json", proposal_queue)
    write_json(STRATEGY_CURRENT_ROOT / "skill-gap-report.json", gap_report)
    write_json(STRATEGY_CURRENT_ROOT / "recruitment-candidate.json", recruitment)
    write_json(STRATEGY_CURRENT_ROOT / "agent-scorecard.json", scorecard)
    write_json(STRATEGY_CURRENT_ROOT / "budget-profile.json", budget_profile)
    write_json(STRATEGY_CURRENT_ROOT / "chain-scorecard.json", chain_scorecard)
    write_json(STRATEGY_CURRENT_ROOT / "object-scorecard.json", object_scorecard)
    write_json(STRATEGY_CURRENT_ROOT / "routing-credit.json", routing_credit)
    write_json(STRATEGY_CURRENT_ROOT / "autonomy-tier.json", autonomy_tier)
    write_json(STRATEGY_CURRENT_ROOT / "budget-ledger.json", budget_ledger)
    write_json(STRATEGY_CURRENT_ROOT / "incentive-decision.json", incentive_decision)
    write_json(STRATEGY_CURRENT_ROOT / "governance-calibration.json", calibration)
    if governance_skill_rows:
        write_json(
            STRATEGY_CURRENT_ROOT / "writeback-trust.json",
            [
                {
                    "skill": row["display_name"],
                    "writeback_trust": bool(row["writeback_trust"]),
                    "honesty_gate_passed": honesty_gate_passed_from_score(row.get("honesty_score")),
                    "honesty_status": row.get("honesty_status", "measured"),
                }
                for row in governance_skill_rows
            ],
        )
    (STRATEGY_CURRENT_ROOT / "governance-dashboard.md").write_text(
        render_governance_dashboard(strategy_map, initiatives, active_threads, gap_report, thread_proposals, scorecard, hub_summary),
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
                f"- Proposal queue status: {' | '.join(item['proposal_status'] for item in proposal_queue[:3]) or 'none'}",
                (
                    f"- Hub audit snapshot: sources={hub_summary.get('sources_total', 0)} tasks={hub_summary.get('tasks_total', 0)} skills={hub_summary.get('skills_total', 0)}"
                    if hub_summary
                    else "- Hub audit snapshot: none"
                ),
                (
                    f"- Hub next step: {hub_recommendations.get('next_steps', [{}])[0].get('title', 'none')}"
                    if hub_recommendations.get("next_steps")
                    else "- Hub next step: none"
                ),
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
        "proposal_queue": proposal_queue,
        "recruitment": recruitment,
        "scorecard": scorecard,
        "budget_profile": budget_profile,
        "chain_scorecard": chain_scorecard,
        "object_scorecard": object_scorecard,
        "routing_credit": routing_credit,
        "autonomy_tier": autonomy_tier,
        "budget_ledger": budget_ledger,
        "incentive_decision": incentive_decision,
        "governance_calibration": calibration,
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
        "外部线索数": str(review.get("external_signal_summary", {}).get("shortlist_count", 0)),
        "adoption queue 数": str(review.get("adoption_queue_count", 0)),
        "环境阻塞": " | ".join(normalize_list(review.get("env_blockers"))) or "none",
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
        f"- 外部 shortlist: {' | '.join(review.get('external_signal_summary', {}).get('shortlist_titles', [])) or 'none'}",
        f"- 外部 adoption queue: {review.get('adoption_queue_count', 0)}",
        f"- 环境阻塞: {' | '.join(normalize_list(review.get('env_blockers'))) or 'none'}",
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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def normalize_prompt(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def normalize_slug_part(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", normalize_prompt(value))
    normalized = normalized.strip("-")
    return normalized or "unknown"


def stable_hash(*parts: str) -> str:
    text = "||".join(part.strip() for part in parts if part and part.strip())
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


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


def clamp_score(value: float, *, low: int = 1, high: int = 5) -> int:
    return max(low, min(high, int(round(value))))


def chain_simplicity_from_penalty(complexity_penalty: int) -> int:
    return clamp_score(6 - complexity_penalty)


def predicted_time_efficiency_from_profile(
    cost_efficiency: int,
    auth_reuse: int,
    complexity_penalty: int,
) -> int:
    return clamp_score((cost_efficiency + auth_reuse + chain_simplicity_from_penalty(complexity_penalty)) / 3)


def weighted_score(
    metrics: dict[str, float],
    weights: dict[str, int],
    *,
    scale_max: int = 5,
) -> float:
    total_weight = sum(weights.values()) or 1
    weighted_total = 0.0
    for key, weight in weights.items():
        weighted_total += float(metrics.get(key, 0)) * weight
    return round((weighted_total / (scale_max * total_weight)) * 100, 2)


def verification_status_is_complete(status: str) -> bool:
    return status.strip().lower() in {"completed", "done", "passed", "success", "verified"}


def verification_strength_score(verification: dict[str, Any]) -> int:
    evidence_count = len(normalize_list(verification.get("evidence")))
    open_questions = len(normalize_list(verification.get("open_questions")))
    status = str(verification.get("status") or "")
    base = 5 if verification_status_is_complete(status) else 2
    return clamp_score(base + min(evidence_count, 3) - min(open_questions, 2))


def closure_quality_score(verification: dict[str, Any]) -> int:
    open_questions = len(normalize_list(verification.get("open_questions")))
    status = str(verification.get("status") or "")
    if verification_status_is_complete(status) and open_questions == 0:
        return 5
    if verification_status_is_complete(status):
        return 4
    if status.strip().lower() in {"partial", "in_progress", "preview_ready"}:
        return 2
    return 1


def pseudo_completion_flag(verification: dict[str, Any]) -> bool:
    status = str(verification.get("status") or "")
    evidence_count = len(normalize_list(verification.get("evidence")))
    open_questions = len(normalize_list(verification.get("open_questions")))
    return verification_status_is_complete(status) and (evidence_count == 0 or open_questions >= 3)


def interruption_efficiency_score(human_boundary: str) -> int:
    text = human_boundary.lower()
    if "do not interrupt" in text or "高自治" in human_boundary:
        return 5
    if "only interrupt" in text:
        return 4
    return 3


def handoff_coherence_score(skills_selected: list[str]) -> int:
    if len(skills_selected) <= 1:
        return 5
    if len(skills_selected) == 2:
        return 4
    if len(skills_selected) == 3:
        return 3
    return 2


def strategic_alignment_score(skills_selected: list[str], governance_status: str) -> int:
    if "ai-da-guan-jia" in skills_selected:
        return 5
    if governance_status == "loaded":
        return 4
    return 3


def budget_tier_for_signals(signals: dict[str, bool]) -> str:
    if signals["multi_agent"] or signals["feishu"]:
        return "expedition"
    if signals["manual_first_learning"] or signals["skill_training"] or signals["skill_inventory_review"]:
        return "deep"
    if signals["skill_creation"] or signals["knowledge_first"] or signals["evolution"]:
        return "standard"
    return "micro"


def resolve_budget_profile(signals: dict[str, bool], selected_skills: list[str] | None = None) -> dict[str, Any]:
    tier = budget_tier_for_signals(signals)
    profile = dict(DEFAULT_BUDGET_PROFILES[tier])
    selected_total = len(selected_skills or [])
    if selected_total >= 3 and tier != "expedition":
        upgraded_tier = "deep" if tier == "standard" else "expedition" if tier == "deep" else tier
        if upgraded_tier != tier:
            tier = upgraded_tier
            profile = dict(DEFAULT_BUDGET_PROFILES[tier])
    profile["tier"] = tier
    profile["task_chain_size"] = selected_total
    profile["scorecard_version"] = ROUTE_SCORECARD_VERSION
    profile["budget_mode"] = "tiered"
    return profile


def efficiency_score_against_budget(
    observed_value: float | None,
    *,
    soft_cap: float,
    hard_cap: float,
    fallback: int,
) -> tuple[int, str]:
    if observed_value is None:
        return fallback, "predicted_proxy"
    if observed_value <= soft_cap:
        return 5, "observed"
    if observed_value <= hard_cap:
        return 3, "observed"
    return 1, "observed"


def budget_assessment(
    budget_profile: dict[str, Any],
    *,
    observed_token_usage: float | None = None,
    observed_duration_minutes: float | None = None,
    selected_skills: list[str] | None = None,
) -> dict[str, Any]:
    selected_total = len(selected_skills or [])
    fallback_token = 5 if selected_total <= 1 else 4 if selected_total == 2 else 3
    fallback_time = 5 if selected_total <= 1 else 4 if selected_total == 2 else 3
    token_score, token_mode = efficiency_score_against_budget(
        observed_token_usage,
        soft_cap=float(budget_profile["soft_token_cap"]),
        hard_cap=float(budget_profile["hard_token_cap"]),
        fallback=fallback_token,
    )
    time_score, time_mode = efficiency_score_against_budget(
        observed_duration_minutes,
        soft_cap=float(budget_profile["soft_time_cap"]),
        hard_cap=float(budget_profile["hard_time_cap"]),
        fallback=fallback_time,
    )
    soft_overrun = bool(
        (observed_token_usage is not None and observed_token_usage > float(budget_profile["soft_token_cap"]))
        or (observed_duration_minutes is not None and observed_duration_minutes > float(budget_profile["soft_time_cap"]))
    )
    hard_overrun = bool(
        (observed_token_usage is not None and observed_token_usage > float(budget_profile["hard_token_cap"]))
        or (observed_duration_minutes is not None and observed_duration_minutes > float(budget_profile["hard_time_cap"]))
    )
    return {
        "budget_profile": budget_profile,
        "observed_token_usage": observed_token_usage,
        "observed_duration_minutes": observed_duration_minutes,
        "token_efficiency": token_score,
        "time_efficiency": time_score,
        "token_measurement_mode": token_mode,
        "time_measurement_mode": time_mode,
        "soft_budget_exceeded": soft_overrun,
        "hard_budget_exceeded": hard_overrun,
    }


def build_route_gates(
    *,
    ranked: list[dict[str, Any]],
    selected: list[str],
    signals: dict[str, bool],
) -> dict[str, Any]:
    ranked_by_name = {item["name"]: item for item in ranked}
    selected_rows = [ranked_by_name[name] for name in selected if name in ranked_by_name]
    honesty_gate = all(bool(item.get("honesty_gate_passed", True)) for item in selected_rows)
    honesty_unknown = any(item.get("honesty_score") is None for item in selected_rows)
    verification_gate = bool(selected_rows) and all(
        int(item.get("verification_capability", 0) or 0) >= VERIFICATION_GATE_MIN for item in selected_rows
    )
    boundary_summary = determine_human_boundary(signals)
    boundary_gate = bool(boundary_summary.strip())
    return {
        "honesty_gate": {
            "passed": honesty_gate,
            "mode": "soft-pass" if honesty_unknown else "enforced",
            "threshold": HONESTY_GATE_MIN,
        },
        "verification_gate": {
            "passed": verification_gate,
            "threshold": VERIFICATION_GATE_MIN,
        },
        "boundary_gate": {
            "passed": boundary_gate,
            "requires_human_checkpoint": bool(signals["hard_boundary"] or signals["feishu"]),
            "summary": boundary_summary,
        },
    }


def build_closure_assessment(
    *,
    verification: dict[str, Any],
    skills_selected: list[str],
    effective_patterns: list[str],
    governance_status: str,
    human_boundary: str,
    budget_profile: dict[str, Any],
    observed_token_usage: float | None = None,
    observed_duration_minutes: float | None = None,
) -> dict[str, Any]:
    budget = budget_assessment(
        budget_profile,
        observed_token_usage=observed_token_usage,
        observed_duration_minutes=observed_duration_minutes,
        selected_skills=skills_selected,
    )
    metrics = {
        "closure_quality": closure_quality_score(verification),
        "verification_strength": verification_strength_score(verification),
        "token_efficiency": budget["token_efficiency"],
        "time_efficiency": budget["time_efficiency"],
        "interruption_efficiency": interruption_efficiency_score(human_boundary),
        "reuse_contribution": clamp_score(len(normalize_list(effective_patterns)) or len(skills_selected) or 1),
        "handoff_coherence": handoff_coherence_score(skills_selected),
        "strategic_alignment": strategic_alignment_score(skills_selected, governance_status),
    }
    closure_score = weighted_score(metrics, CLOSURE_SCORE_WEIGHTS)
    return {
        "scorecard_version": CLOSURE_SCORECARD_VERSION,
        "metrics": metrics,
        "closure_score": closure_score,
        "gates": {
            "closure_quality_passed": metrics["closure_quality"] >= 3,
            "verification_strength_passed": metrics["verification_strength"] >= 3,
            "pseudo_completion": pseudo_completion_flag(verification),
        },
        "budget_assessment": budget,
    }


def build_incentive_decision(
    *,
    closure_assessment: dict[str, Any],
    selected_skills: list[str],
    governance_status: str,
) -> dict[str, Any]:
    metrics = closure_assessment["metrics"]
    gates = closure_assessment["gates"]
    budget = closure_assessment["budget_assessment"]
    decision = {
        "evaluation_target": "execution_chain",
        "selected_skills": normalize_list(selected_skills),
        "governance_signal_status": governance_status,
        "levers": {
            "调用权": "hold",
            "自治权": "hold",
            "资源权": "hold",
            "进化权": "hold",
        },
        "penalties": [],
        "reasons": [],
    }
    if gates["pseudo_completion"] or not gates["closure_quality_passed"] or not gates["verification_strength_passed"]:
        decision["levers"] = {
            "调用权": "decrease",
            "自治权": "downgrade_review",
            "资源权": "restrict",
            "进化权": "freeze_writeback",
        }
        if gates["pseudo_completion"]:
            decision["penalties"].append("伪完成")
        if not gates["verification_strength_passed"]:
            decision["penalties"].append("结果不可证")
        decision["reasons"].append("真闭环或验真门槛未通过，成本表现不能抵消结果失真。")
        return decision
    if budget["hard_budget_exceeded"]:
        decision["levers"]["资源权"] = "manual_budget_review"
        decision["penalties"].append("超预算但无默认豁免")
        decision["reasons"].append("触发 hard cap，默认需要预算复盘或中止建议。")
    elif budget["soft_budget_exceeded"]:
        decision["levers"]["资源权"] = "soft_budget_review"
        decision["reasons"].append("结果成立，但超过 soft cap，应复盘预算档位。")
    if closure_assessment["closure_score"] >= 80:
        decision["levers"]["调用权"] = "increase"
        decision["levers"]["自治权"] = "promote_candidate"
        if not budget["hard_budget_exceeded"]:
            decision["levers"]["资源权"] = "prefer"
        decision["levers"]["进化权"] = "allow_writeback_candidate"
        decision["reasons"].append("高闭环、高验真且成本表现可接受。")
    elif closure_assessment["closure_score"] >= 65:
        decision["levers"]["调用权"] = "prefer"
        decision["levers"]["自治权"] = "trusted_suggest_candidate"
        decision["reasons"].append("结果稳定，可进入优先候选池。")
    if metrics["handoff_coherence"] <= 2:
        decision["penalties"].append("链路膨胀")
    if metrics["interruption_efficiency"] <= 2:
        decision["penalties"].append("无必要打断")
    return decision


GET_BIJI_URL_RE = re.compile(r"https?://[^\s)>\"]+", re.IGNORECASE)
GET_BIJI_NOTE_ID_PATTERNS = [
    re.compile(r"/note/(\d+)", re.IGNORECASE),
    re.compile(r"\bnote[\s_-]*id\b[^\d]*(\d{8,})", re.IGNORECASE),
    re.compile(r"笔记\s*id[^\d]*(\d{8,})", re.IGNORECASE),
    re.compile(r"\bnote\b[^\d]{0,8}(\d{8,})", re.IGNORECASE),
]
GET_BIJI_ROUTE_FIELDS = [
    "recommended_entrypoint",
    "primary_action",
    "human_route_summary",
    "recommended_actions",
]


def first_url_in_text(text: str) -> str:
    match = GET_BIJI_URL_RE.search(text or "")
    if not match:
        return ""
    return match.group(0).rstrip(").,!?]>")


def extract_get_biji_note_id(text: str) -> str:
    prompt_text = text or ""
    for pattern in GET_BIJI_NOTE_ID_PATTERNS:
        match = pattern.search(prompt_text)
        if match:
            return next((group for group in match.groups() if group), "")
    return ""


def prompt_has_any(text: str, phrases: list[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def get_biji_follow_up_requested(text: str) -> bool:
    return prompt_has_any(
        text,
        [
            "后面我还要继续问",
            "后面还要继续问",
            "后面还要问",
            "之后还要继续问",
            "以后还要继续问",
            "后续继续问",
            "之后还能问",
            "后面还能问",
            "继续问它",
            "还能问它",
        ],
    )


def quote_cli_arg(value: str) -> str:
    return shlex.quote(str(value))


def get_biji_cli_command(parts: list[str]) -> str:
    return " ".join(quote_cli_arg(part) for part in parts)


def build_get_biji_route_action(
    *,
    step_index: int,
    action: str,
    reason: str,
    inputs: dict[str, Any],
    cli_parts: list[str],
    expected_artifacts: list[str],
    verification_note: str,
    blocking_boundary: str = "",
) -> dict[str, Any]:
    return {
        "step_index": step_index,
        "action": action,
        "reason": reason,
        "inputs": inputs,
        "cli_command": get_biji_cli_command(cli_parts),
        "expected_artifacts": expected_artifacts,
        "verification_note": verification_note,
        "blocking_boundary": blocking_boundary,
    }


def plan_get_biji_actions(prompt: str) -> dict[str, Any]:
    text = normalize_prompt(prompt)
    raw_prompt = str(prompt or "").strip()
    script_path = str((SCRIPT_DIR / "ai_da_guan_jia.py").resolve())
    url = first_url_in_text(raw_prompt)
    note_id = extract_get_biji_note_id(raw_prompt)
    wants_transcript = prompt_has_any(text, ["逐字稿", "原始逐字稿", "原文", "转写", "transcript", "original"])
    wants_follow_up = get_biji_follow_up_requested(text)
    wants_original = wants_transcript and bool(note_id)
    ingest_phrases = [
        "记到get笔记",
        "记录到get笔记",
        "保存到get笔记",
        "存到get笔记",
        "添加到get笔记",
        "导入链接",
        "导入到get笔记",
        "记下来",
        "存到笔记",
        "添加到笔记",
        "这个b站链接",
        "这个视频",
        "这个链接",
    ]
    wants_ingest = bool(url) or prompt_has_any(text, ingest_phrases)
    if not wants_ingest and prompt_has_any(text, ["链接", "视频", "文章", "网页"]):
        wants_ingest = prompt_has_any(text, ["记到", "记录到", "保存到", "存到", "添加到", "导入"])
    wants_recall = prompt_has_any(
        text,
        [
            "找回",
            "召回",
            "搜索",
            "搜一下",
            "检索",
            "关键词",
            "片段",
            "命中",
        ],
    )

    actions: list[dict[str, Any]] = []
    if wants_original:
        actions.append(
            build_get_biji_route_action(
                step_index=1,
                action="get_biji.fetch_original",
                reason="The prompt provides a note id and asks for the original transcript path.",
                inputs={"note_id": note_id},
                cli_parts=[
                    "python3",
                    script_path,
                    "get-biji",
                    "fetch-original",
                    "--note-id",
                    note_id or "<note-id>",
                ],
                expected_artifacts=[
                    "get-biji-request.json",
                    "get-biji-response.json",
                    "get-biji-record.json",
                    "transcript-<note-id>-<timestamp>.txt when original exists",
                    "transcript-<note-id>-<timestamp>.json when original exists",
                ],
                verification_note="Expect transcript txt/json artifacts, or an explicit note that original transcript is unavailable.",
                blocking_boundary="" if note_id else "Need an explicit Get笔记 note id.",
            )
        )
        summary = "直接按 note id 走原始逐字稿提取。"
    elif wants_ingest:
        mode = "transcribe-link" if wants_transcript else "submit-link"
        link_value = url or "<external-link>"
        actions.append(
            build_get_biji_route_action(
                step_index=1,
                action="get_biji.ingest_link",
                reason="The prompt is asking to store external content into Get笔记 rather than query an existing note.",
                inputs={"link": link_value, "mode": mode},
                cli_parts=[
                    "python3",
                    script_path,
                    "get-biji",
                    "ingest-link",
                    "--link",
                    link_value,
                    "--mode",
                    mode,
                ],
                expected_artifacts=[
                    "get-biji-request.json",
                    "get-biji-response.json",
                    "get-biji-record.json",
                    "note evidence from Get笔记 web import",
                    "transcript txt/json artifacts when mode=transcribe-link and original exists",
                ],
                verification_note=(
                    "Expect note generation evidence plus a clear transcript-versus-summary boundary for the imported link."
                ),
                blocking_boundary="" if url else "Need the original external link to execute the ingest step.",
            )
        )
        if wants_follow_up:
            actions.append(
                build_get_biji_route_action(
                    step_index=2,
                    action="get_biji.ask",
                    reason="After ingestion, use ask for natural-language follow-ups; switch to recall if the next step is only keyword retrieval.",
                    inputs={"question": "<follow-up-question>"},
                    cli_parts=[
                        "python3",
                        script_path,
                        "get-biji",
                        "ask",
                        "--question",
                        "<follow-up-question>",
                    ],
                    expected_artifacts=[
                        "get-biji-request.json",
                        "get-biji-response.json",
                        "get-biji-record.json",
                    ],
                    verification_note="Subsequent ask calls should return a non-empty answer or an explicit empty-answer explanation.",
                    blocking_boundary="Run this after the ingest step has succeeded.",
                )
            )
            summary = "先导入链接到 Get笔记，并尽量拿逐字稿；导入成功后，再用 ask 继续追问内容。"
        elif wants_transcript:
            summary = "先按链接导入到 Get笔记，并优先走逐字稿提取路径。"
        else:
            summary = "先按链接导入到 Get笔记，生成可复用的笔记记录。"
    elif wants_recall:
        query = raw_prompt
        actions.append(
            build_get_biji_route_action(
                step_index=1,
                action="get_biji.recall",
                reason="The prompt is phrased as retrieval or keyword recall rather than a direct natural-language question.",
                inputs={"query": query, "top_k": 5},
                cli_parts=[
                    "python3",
                    script_path,
                    "get-biji",
                    "recall",
                    "--query",
                    query,
                    "--top-k",
                    "5",
                ],
                expected_artifacts=[
                    "get-biji-request.json",
                    "get-biji-response.json",
                    "get-biji-record.json",
                ],
                verification_note="Expect retrieval hits, or a success=true no_hits result.",
            )
        )
        summary = "先走 Get笔记 召回，按关键词把可能相关的笔记片段找出来。"
    else:
        question = raw_prompt
        actions.append(
            build_get_biji_route_action(
                step_index=1,
                action="get_biji.ask",
                reason="Default to the OpenAPI question-answer path for natural-language note lookup and summarization.",
                inputs={"question": question},
                cli_parts=[
                    "python3",
                    script_path,
                    "get-biji",
                    "ask",
                    "--question",
                    question,
                ],
                expected_artifacts=[
                    "get-biji-request.json",
                    "get-biji-response.json",
                    "get-biji-record.json",
                ],
                verification_note="Expect a non-empty answer, or an explicit empty-answer explanation.",
            )
        )
        summary = "先走 Get笔记 问答接口，直接按自然语言问题去查相关笔记内容。"

    return {
        "recommended_entrypoint": "get_biji",
        "primary_action": actions[0]["action"],
        "human_route_summary": summary,
        "recommended_actions": actions,
    }


def detect_signals(prompt: str) -> dict[str, bool]:
    text = normalize_prompt(prompt)
    explicit_get_biji = any(
        phrase in text
        for phrase in [
            "get笔记",
            "得到笔记",
            "biji",
            "逐字稿",
            "原文提取",
            "导入链接",
            "转写",
            "transcript",
        ]
    )
    implicit_get_biji = (
        ("笔记" in text and prompt_has_any(text, ["查", "问", "找回", "召回", "搜索", "检索", "总结", "note"]))
        or bool(extract_get_biji_note_id(prompt))
    )
    get_biji = explicit_get_biji or implicit_get_biji
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
        "get_biji": get_biji,
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


def verification_targets(signals: dict[str, bool], get_biji_plan: dict[str, Any] | None = None) -> list[str]:
    targets: list[str] = []
    if signals["get_biji"]:
        if get_biji_plan and isinstance(get_biji_plan.get("recommended_actions"), list):
            seen: set[str] = set()
            for action in get_biji_plan["recommended_actions"]:
                action_name = str(action.get("action") or "").strip()
                if action_name == "get_biji.ask":
                    message = "Need a non-empty answer payload or an explicit empty-answer explanation for the ask step."
                elif action_name == "get_biji.recall":
                    message = "Need retrieval hits or a success=true no_hits result for the recall step."
                elif action_name == "get_biji.ingest_link":
                    message = "Need note generation evidence, dedupe status when relevant, and a clear transcript-versus-summary boundary for the ingest step."
                elif action_name == "get_biji.fetch_original":
                    message = "Need transcript txt/json artifacts or an explicit note that the original transcript route is unavailable."
                else:
                    message = "Need get-biji-request.json, get-biji-response.json, and get-biji-record.json."
                if message not in seen:
                    seen.add(message)
                    targets.append(message)
        else:
            targets.append(
                "Need get-biji-request.json, get-biji-response.json, get-biji-record.json, a verification note about API versus web path, and transcript/note evidence when the web path is used."
            )
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
    governance: dict[str, Any] | None = None,
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
    if name == "get-biji-transcript" and signals["get_biji"]:
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
    predicted_time_efficiency = predicted_time_efficiency_from_profile(
        cost_score,
        auth_reuse_score,
        complexity_penalty,
    )
    chain_simplicity = chain_simplicity_from_penalty(complexity_penalty)
    route_metrics = {
        "task_fit_score": task_fit,
        "verification_capability": verification_score,
        "predicted_token_efficiency": cost_score,
        "predicted_time_efficiency": predicted_time_efficiency,
        "auth_reuse_score": auth_reuse_score,
        "chain_simplicity": chain_simplicity,
    }
    base_total = (
        task_fit * 10000
        + verification_score * 100
        + cost_score * 10
        + auth_reuse_score
        - complexity_penalty
    )
    governance = governance or {}
    governance_status = str(governance.get("status") or "missing")
    routing_credit_map = governance.get("routing_credit") if isinstance(governance.get("routing_credit"), dict) else {}
    autonomy_tier_map = governance.get("autonomy_tier") if isinstance(governance.get("autonomy_tier"), dict) else {}
    scorecard_map = governance.get("scorecard") if isinstance(governance.get("scorecard"), dict) else {}
    routing_credit = float(routing_credit_map.get(name, 0) or 0)
    autonomy_tier = str(autonomy_tier_map.get(name, "observe") or "observe").strip() or "observe"
    if autonomy_tier not in AUTONOMY_TIERS:
        autonomy_tier = "observe"
    scorecard_row = scorecard_map.get(name) if isinstance(scorecard_map.get(name), dict) else {}
    honesty_score = scorecard_row.get("honesty_score")
    honesty_gate_passed = honesty_gate_passed_from_score(honesty_score)
    verification_gate_passed = verification_score >= VERIFICATION_GATE_MIN
    boundary_gate_passed = True
    proposal_authority = proposal_authority_for_tier(autonomy_tier)
    credit_adjustment = routing_credit_adjustment(base_total, task_fit, routing_credit)
    route_score = weighted_score(route_metrics, ROUTE_SCORE_WEIGHTS)
    total = base_total + credit_adjustment
    if hits:
        rationale = f"Matched signals: {', '.join(hits[:4])}"
    elif name in mentioned:
        rationale = "Explicitly named in the prompt."
    elif task_fit > 0:
        rationale = "Selected through a hard routing rule."
    else:
        rationale = "No strong match signal."
    governance_reasons: list[str] = []
    if governance_status == "missing":
        governance_reasons.append("Governance signals unavailable; using rule-only routing.")
    else:
        governance_reasons.append(f"Governance signals {governance_status}.")
        if credit_adjustment > 0:
            governance_reasons.append(
                f"Routing credit {routing_credit:.1f} added bounded adjustment +{credit_adjustment}."
            )
        elif routing_credit > 0 and task_fit <= 0:
            governance_reasons.append("Routing credit ignored because task_fit_score is 0.")
        elif routing_credit > 0:
            governance_reasons.append(f"Routing credit {routing_credit:.1f} did not change ranking materially.")
        else:
            governance_reasons.append("No routing credit available for this skill.")
        governance_reasons.append(
            f"Autonomy tier {autonomy_tier} maps to proposal authority {proposal_authority}."
        )
        if honesty_score is not None:
            governance_reasons.append(
                "Honesty gate passed."
                if honesty_gate_passed
                else f"Honesty gate failed at {honesty_score:.1f} < {HONESTY_GATE_MIN:.0f}."
            )

    return {
        "name": name,
        "description": skill["description"],
        "path": skill["path"],
        "is_core": skill["is_core"],
        "scorecard_version": ROUTE_SCORECARD_VERSION,
        "task_fit_score": task_fit,
        "verification_capability": verification_score,
        "predicted_token_efficiency": cost_score,
        "predicted_time_efficiency": predicted_time_efficiency,
        "verification_score": verification_score,
        "cost_score": cost_score,
        "auth_reuse_score": auth_reuse_score,
        "chain_simplicity": chain_simplicity,
        "complexity_penalty": complexity_penalty,
        "route_metrics": route_metrics,
        "route_score": route_score,
        "honesty_score": honesty_score,
        "honesty_gate_passed": honesty_gate_passed,
        "verification_gate_passed": verification_gate_passed,
        "boundary_gate_passed": boundary_gate_passed,
        "base_total_score": base_total,
        "routing_credit": routing_credit,
        "routing_credit_adjustment": credit_adjustment,
        "autonomy_tier": autonomy_tier,
        "proposal_authority": proposal_authority,
        "governance_signal_status": governance_status,
        "governance_rationale": " ".join(governance_reasons),
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
    if signals["get_biji"]:
        wanted.append("get-biji-transcript")
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


def credit_influenced_selection(ranked: list[dict[str, Any]], selected: list[str]) -> bool:
    selected_set = set(selected)
    for item in ranked:
        if item["name"] not in selected_set:
            continue
        if int(item.get("routing_credit_adjustment") or 0) > 0:
            return True
    return False


def selected_proposal_authority_summary(
    ranked: list[dict[str, Any]],
    selected: list[str],
) -> dict[str, list[str]]:
    ranked_by_name = {item["name"]: item for item in ranked}
    summary = {
        "strong_suggestion_skills": [],
        "priority_suggestion_skills": [],
        "execution_focused_skills": [],
    }
    for name in selected:
        item = ranked_by_name.get(name, {})
        authority = str(item.get("proposal_authority") or "passive-candidate")
        if authority == "strong-proposal-candidate":
            summary["strong_suggestion_skills"].append(name)
        elif authority == "priority-proposal-candidate":
            summary["priority_suggestion_skills"].append(name)
        else:
            summary["execution_focused_skills"].append(name)
    for key, values in summary.items():
        summary[key] = normalize_list(values)
    return summary


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


def summarize_session_index() -> list[dict[str, Any]]:
    rows = read_jsonl(CODEX_HOME / "session_index.jsonl")
    sessions: list[dict[str, Any]] = []
    for row in rows:
        session_id = str(row.get("id") or "").strip()
        title = str(row.get("thread_name") or "").strip()
        updated_at = str(row.get("updated_at") or "").strip()
        if not session_id or not title:
            continue
        normalized_title = normalize_prompt(title)
        sessions.append(
            {
                "session_id": session_id,
                "thread_name": title,
                "updated_at": updated_at,
                "normalized_title": normalized_title,
                "normalized_task_hash": stable_hash(normalized_title),
            }
        )
    return sessions


def summarize_local_runs() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not RUNS_ROOT.exists():
        return rows
    run_dirs = sorted(
        [path for path in RUNS_ROOT.glob("*/*") if path.is_dir()],
        key=lambda item: str(item),
    )
    for run_dir in run_dirs:
        route_payload = load_optional_json(run_dir / "route.json")
        evolution = load_optional_json(run_dir / "evolution.json")
        worklog = load_optional_json(run_dir / "worklog.json")
        github_task = load_optional_json(run_dir / "github-task.json")
        task_text = str(evolution.get("task_text") or route_payload.get("task_text") or "").strip()
        if not task_text:
            task_text = run_dir.name
        created_at = str(evolution.get("created_at") or route_payload.get("created_at") or "")
        verification = normalize_verification_result(evolution.get("verification_result"))
        selected_skills = normalize_list(evolution.get("skills_selected") or route_payload.get("selected_skills"))
        evidence_types: list[str] = []
        if evolution:
            evidence_types.append("evolution")
        if worklog or (run_dir / "worklog.md").exists():
            evidence_types.append("worklog")
        if route_payload:
            evidence_types.append("route")
        proof_strength = (
            "evolution_worklog"
            if ("evolution" in evidence_types or "worklog" in evidence_types)
            else "route"
            if "route" in evidence_types
            else "github_metadata"
        )
        github_task_key = str(
            evolution.get("github_task_key")
            or github_task.get("classification", {}).get("task_key")
            or ""
        ).strip()
        rows.append(
            {
                "run_id": str(evolution.get("run_id") or route_payload.get("run_id") or run_dir.name),
                "run_dir": str(run_dir),
                "created_at": created_at,
                "task_text": task_text,
                "normalized_title": normalize_prompt(task_text),
                "normalized_task_hash": stable_hash(normalize_prompt(task_text)),
                "selected_skills": selected_skills,
                "verification_result": verification,
                "verification_status": str(verification.get("status") or ""),
                "github_task_key": github_task_key,
                "github_sync_status": str(evolution.get("github_sync_status") or github_task.get("github_sync_status") or ""),
                "evidence_types": evidence_types,
                "proof_strength": proof_strength,
                "structured_artifacts": sorted(
                    [
                        name
                        for name in [
                            "route.json",
                            "evolution.json",
                            "worklog.json",
                            "worklog.md",
                            "github-task.json",
                            "github-payload.json",
                        ]
                        if (run_dir / name).exists()
                    ]
                ),
            }
        )
    return rows


def summarize_local_automations() -> list[dict[str, Any]]:
    automations_root = CODEX_HOME / "automations"
    rows: list[dict[str, Any]] = []
    if not automations_root.exists():
        return rows
    for automation_dir in sorted(path for path in automations_root.iterdir() if path.is_dir()):
        config_path = automation_dir / "automation.toml"
        payload: dict[str, Any] = {}
        if config_path.exists() and tomllib is not None:
            try:
                with config_path.open("rb") as handle:
                    parsed = tomllib.load(handle)
                if isinstance(parsed, dict):
                    payload = parsed
            except Exception:
                payload = {}
        rows.append(
            {
                "id": automation_dir.name,
                "path": str(config_path),
                "exists": config_path.exists(),
                "name": str(payload.get("name") or automation_dir.name),
                "status": str(payload.get("status") or "UNKNOWN"),
                "rrule": str(payload.get("rrule") or ""),
                "prompt": str(payload.get("prompt") or ""),
            }
        )
    return rows


def collect_top_level_skill_inventory() -> list[dict[str, Any]]:
    inventory = build_review_inventory()
    rows: list[dict[str, Any]] = []
    for item in inventory:
        shape = artifact_shape(Path(item["path"]))
        rows.append(
            {
                **item,
                "artifact_shape": shape,
                "artifact_shape_score": sum(1 for value in shape.values() if value),
                "installed": True,
            }
        )
    return rows


def local_git_skill_repos() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in collect_top_level_skill_inventory():
        repo = str(item.get("git_origin_repo") or "").strip()
        if not repo:
            continue
        rows.append(
            {
                "skill": item["name"],
                "repo": repo,
                "source_type": item.get("source_type", ""),
            }
        )
    return rows


def github_summary_payload(skills: list[dict[str, Any]], runs: list[dict[str, Any]]) -> dict[str, Any]:
    sync_status_counts: dict[str, int] = {}
    for item in runs:
        status = str(item.get("github_sync_status") or "missing")
        sync_status_counts[status] = sync_status_counts.get(status, 0) + 1
    return {
        "generated_at": iso_now(),
        "hub_repo": resolve_github_ops_repo(),
        "github_backend": detect_github_backend(),
        "default_owner": default_github_owner(),
        "github_sources": build_github_sources(skills),
        "local_skill_repos": local_git_skill_repos(),
        "run_github_sync_status_counts": sync_status_counts,
    }


def machine_profile_payload(source_id: str) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "hostname": socket.gethostname(),
        "hostname_slug": hostname_slug(),
        "user": os.getenv("USER", ""),
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "generated_at": iso_now(),
        "codex_home": str(CODEX_HOME),
        "skill_root": str(SKILLS_ROOT),
        "role": "canonical_hub" if source_id == "main-hub" else "satellite_reporter",
    }


def bundle_roots_for_source(source_id: str) -> tuple[Path, Path]:
    generated_at = now_local()
    day = generated_at.strftime("%Y-%m-%d")
    stamp = generated_at.strftime("%Y%m%d-%H%M%S")
    latest_root = HUB_OUTBOX_ROOT / "sources" / source_id / "latest"
    snapshot_root = HUB_OUTBOX_ROOT / "sources" / source_id / "snapshots" / day / stamp
    return latest_root, snapshot_root


def clear_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    ensure_dir(path)


def copy_bundle_to_target(source: Path, target: Path) -> None:
    clear_directory(target)
    for child in source.iterdir():
        if child.is_dir():
            shutil.copytree(child, target / child.name)
        else:
            shutil.copy2(child, target / child.name)


def bundle_manifest(
    *,
    source_id: str,
    mode: str,
    skills: list[dict[str, Any]],
    sessions: list[dict[str, Any]],
    runs: list[dict[str, Any]],
    automations: list[dict[str, Any]],
    local_repo_dir: str,
) -> dict[str, Any]:
    return {
        "schema_version": INTAKE_BUNDLE_VERSION,
        "generated_at": iso_now(),
        "source_id": source_id,
        "mode": mode,
        "counts": {
            "skills": len(skills),
            "sessions": len(sessions),
            "runs": len(runs),
            "automations": len(automations),
        },
        "hub_repo": resolve_github_ops_repo(),
        "hub_repo_local_dir": local_repo_dir,
    }


def render_satellite_onboarding(repo: str, expected_sources: list[str]) -> str:
    lines = [
        "# Satellite Onboarding",
        "",
        f"- Hub repo: `{repo}`",
        f"- Expected sources: {' | '.join(expected_sources)}",
        "",
        "## First Full Intake",
        "",
    ]
    for source_id in expected_sources:
        if source_id == "main-hub":
            continue
        lines.extend(
            [
                f"### {source_id}",
                "",
                "```bash",
                f"python3 scripts/ai_da_guan_jia.py emit-intake-bundle --source-id {source_id} --mode full",
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Recurring Delta Intake",
            "",
            "```bash",
            "python3 scripts/ai_da_guan_jia.py emit-intake-bundle --source-id <source-id> --mode delta",
            "```",
            "",
            "## Canonical Hub Refresh",
            "",
            "```bash",
            "python3 scripts/ai_da_guan_jia.py aggregate-hub --source-id main-hub",
            "python3 scripts/ai_da_guan_jia.py audit-maturity --source-id main-hub",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def write_intake_bundle(bundle_root: Path, payloads: dict[str, Any], notes: str) -> None:
    ensure_dir(bundle_root)
    for name, payload in payloads.items():
        if name.endswith(".md"):
            (bundle_root / name).write_text(str(payload), encoding="utf-8")
        else:
            write_json(bundle_root / name, payload)
    (bundle_root / "ingest-notes.md").write_text(notes, encoding="utf-8")


def determine_human_boundary(signals: dict[str, bool]) -> str:
    if signals["hard_boundary"] or signals["feishu"]:
        return "Only interrupt the user for login, authorization, payment, irreversible publish or delete, or blocked external permissions."
    return "Default to high autonomy. Do not interrupt the user unless a truly human-only boundary appears."


def determine_max_distortion(signals: dict[str, bool]) -> str:
    if signals["get_biji"]:
        return "把 Get笔记 OpenAPI 检索层和网页采集层混成一条能力，导致调用路径、验真方式和预期结果失真。"
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
    return "把低 token、快完成、少对话误当成高质量闭环。"


def build_situation_map(
    prompt: str,
    selected: list[str],
    signals: dict[str, bool],
) -> dict[str, str]:
    selected_text = ", ".join(selected) if selected else "none selected yet"
    global_optimum = "Prefer the smallest sufficient local skill combination before heavier exploration or browser work."
    reuse = f"First reuse: {selected_text}. Discover other local skills only when the core roster is insufficient."
    verification = "Completion requires an artifact check and a goal check; command success alone is never enough."
    if signals["get_biji"]:
        global_optimum = "Split Get笔记 into API retrieval and web ingestion paths; do not force one interface to pretend to cover both."
        reuse = (
            f"First reuse: {selected_text}. Keep local canonical records as source of truth and treat Get笔记 as an external knowledge source."
        )
        verification = (
            "Completion requires get-biji request/response/record artifacts plus clear evidence of whether the result came from API retrieval or web ingestion."
        )
    return {
        "自治判断": determine_human_boundary(signals),
        "全局最优判断": global_optimum,
        "能力复用判断": reuse,
        "验真判断": verification,
        "进化判断": "Every meaningful run must produce effective patterns, wasted patterns, and candidate improvements before closure.",
        "当前最大失真": determine_max_distortion(signals),
    }


def render_situation_map(situation_map: dict[str, str], prompt: str) -> str:
    lines = ["# Situation Map", "", f"- `任务`: {prompt}", ""]
    for key in ["自治判断", "全局最优判断", "能力复用判断", "验真判断", "进化判断", "当前最大失真"]:
        lines.append(f"- `{key}`: {situation_map[key]}")
    governance_note = str(situation_map.get("治理提权判断") or "").strip()
    if governance_note:
        lines.append(f"- `治理提权判断`: {governance_note}")
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


def run_command_capture(
    command: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            cwd=str(cwd) if cwd else None,
            timeout=timeout,
        )
        return {
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "returncode": 124,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "timed_out": True,
        }


def normalize_get_biji_link(link: str) -> str:
    parsed = urllib_parse.urlsplit(link.strip())
    return urllib_parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def load_get_biji_link_index() -> dict[str, dict[str, Any]]:
    if not GET_BIJI_LINK_INDEX_PATH.exists():
        return {}
    payload = read_json(GET_BIJI_LINK_INDEX_PATH)
    if not isinstance(payload, dict):
        return {}
    return {
        str(key): value
        for key, value in payload.items()
        if isinstance(key, str) and isinstance(value, dict)
    }


def save_get_biji_link_index(index: dict[str, dict[str, Any]]) -> None:
    ensure_dir(GET_BIJI_CURRENT_ROOT)
    write_json(GET_BIJI_LINK_INDEX_PATH, index)


def parse_labeled_lines(*chunks: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for chunk in chunks:
        for raw_line in str(chunk or "").splitlines():
            if ":" not in raw_line:
                continue
            key, value = raw_line.split(":", 1)
            parsed[normalize_prompt(key).replace(" ", "_")] = value.strip()
    return parsed


def write_get_biji_artifacts(
    run_dir: Path,
    *,
    request_payload: dict[str, Any],
    response_payload: dict[str, Any],
    record_payload: dict[str, Any],
) -> None:
    write_json(run_dir / "get-biji-request.json", request_payload)
    write_json(run_dir / "get-biji-response.json", response_payload)
    write_json(run_dir / "get-biji-record.json", record_payload)


def lookup_get_biji_link(link: str) -> dict[str, Any] | None:
    return load_get_biji_link_index().get(normalize_get_biji_link(link))


def store_get_biji_link_record(link: str, payload: dict[str, Any]) -> None:
    index = load_get_biji_link_index()
    key = normalize_get_biji_link(link)
    current = index.get(key, {})
    merged = {
        **current,
        **payload,
        "link": key,
        "updated_at": iso_now(),
    }
    index[key] = merged
    save_get_biji_link_index(index)


def verify_get_biji_transcript_tool() -> None:
    if not GET_BIJI_TRANSCRIPT_SCRIPT.exists():
        raise FileNotFoundError(f"Get笔记 transcript script not found: {GET_BIJI_TRANSCRIPT_SCRIPT}")


def build_get_biji_record(
    *,
    source: str,
    operation: str,
    success: bool,
    topic_id: str,
    query: str,
    answer: str = "",
    hits: list[dict[str, Any]] | None = None,
    raw_response_path: Path,
    verification_note: str,
    run_id: str,
    metadata: dict[str, Any] | None = None,
    error: str = "",
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "created_at": iso_now(),
        "source": source,
        "operation": operation,
        "success": success,
        "topic_id": topic_id,
        "query": query,
        "answer": answer,
        "hits": hits or [],
        "raw_response_path": str(raw_response_path.resolve()),
        "verification_note": verification_note,
        "error": error,
        "metadata": metadata or {},
    }


def execute_get_biji_api_ask(args: argparse.Namespace, run_dir: Path, run_id: str) -> int:
    request_payload = {
        "operation": "get_biji.ask",
        "question": args.question,
        "topic_id": str(args.topic_id or "").strip(),
        "knowledge_base_id": str(args.knowledge_base_id or "").strip(),
        "user": str(args.user or "ai-da-guan-jia").strip(),
    }
    response_path = run_dir / "get-biji-response.json"
    try:
        result = get_biji_api_ask(
            question=args.question,
            topic_id=args.topic_id,
            knowledge_base_id=args.knowledge_base_id,
            user=args.user,
            raw_response_path=response_path,
        )
        record_payload = build_get_biji_record(
            source=result.source,
            operation=result.operation,
            success=result.success,
            topic_id=result.topic_id,
            query=result.query,
            answer=result.answer,
            hits=result.hits,
            raw_response_path=Path(result.raw_response_path),
            verification_note=result.verification_note,
            run_id=run_id,
            metadata=result.metadata,
            error=result.error,
        )
        write_get_biji_artifacts(
            run_dir,
            request_payload=request_payload,
            response_payload=read_json(response_path),
            record_payload=record_payload,
        )
        print(f"run_id: {run_id}")
        print(f"run_dir: {run_dir}")
        print(f"source: {result.source}")
        print(f"operation: {result.operation}")
        print(f"success: {result.success}")
        print(f"topic_id: {result.topic_id}")
        print(f"answer_present: {bool(result.answer)}")
        print(f"hit_count: {len(result.hits)}")
        print(f"raw_response_path: {result.raw_response_path}")
        print(f"verification_note: {result.verification_note}")
        return 0 if result.success else 1
    except (GetBijiConfigError, GetBijiAPIError, ValueError) as exc:
        response_payload = {"error": str(exc)}
        record_payload = build_get_biji_record(
            source="get_biji_api",
            operation="get_biji.ask",
            success=False,
            topic_id=str(args.topic_id or os.getenv("GET_BIJI_TOPIC_ID", "")).strip(),
            query=str(args.question or "").strip(),
            raw_response_path=run_dir / "get-biji-response.json",
            verification_note=str(exc),
            run_id=run_id,
            error=str(exc),
        )
        write_get_biji_artifacts(run_dir, request_payload=request_payload, response_payload=response_payload, record_payload=record_payload)
        print(str(exc), file=sys.stderr)
        print(f"run_id: {run_id}")
        print(f"run_dir: {run_dir}")
        return 1


def execute_get_biji_api_recall(args: argparse.Namespace, run_dir: Path, run_id: str) -> int:
    request_payload = {
        "operation": "get_biji.recall",
        "query": args.query,
        "topic_id": str(args.topic_id or "").strip(),
        "knowledge_base_id": str(args.knowledge_base_id or "").strip(),
        "top_k": int(args.top_k),
    }
    response_path = run_dir / "get-biji-response.json"
    try:
        result = get_biji_api_recall(
            query=args.query,
            topic_id=args.topic_id,
            knowledge_base_id=args.knowledge_base_id,
            top_k=args.top_k,
            raw_response_path=response_path,
        )
        record_payload = build_get_biji_record(
            source=result.source,
            operation=result.operation,
            success=result.success,
            topic_id=result.topic_id,
            query=result.query,
            hits=result.hits,
            raw_response_path=Path(result.raw_response_path),
            verification_note=result.verification_note,
            run_id=run_id,
            metadata=result.metadata,
            error=result.error,
        )
        write_get_biji_artifacts(
            run_dir,
            request_payload=request_payload,
            response_payload=read_json(response_path),
            record_payload=record_payload,
        )
        print(f"run_id: {run_id}")
        print(f"run_dir: {run_dir}")
        print(f"source: {result.source}")
        print(f"operation: {result.operation}")
        print(f"success: {result.success}")
        print(f"topic_id: {result.topic_id}")
        print(f"hit_count: {len(result.hits)}")
        print(f"raw_response_path: {result.raw_response_path}")
        print(f"verification_note: {result.verification_note}")
        return 0
    except (GetBijiConfigError, GetBijiAPIError, ValueError) as exc:
        response_payload = {"error": str(exc)}
        record_payload = build_get_biji_record(
            source="get_biji_api",
            operation="get_biji.recall",
            success=False,
            topic_id=str(args.topic_id or os.getenv("GET_BIJI_TOPIC_ID", "")).strip(),
            query=str(args.query or "").strip(),
            raw_response_path=run_dir / "get-biji-response.json",
            verification_note=str(exc),
            run_id=run_id,
            error=str(exc),
        )
        write_get_biji_artifacts(run_dir, request_payload=request_payload, response_payload=response_payload, record_payload=record_payload)
        print(str(exc), file=sys.stderr)
        print(f"run_id: {run_id}")
        print(f"run_dir: {run_dir}")
        return 1


def execute_get_biji_web_command(
    *,
    command: list[str],
    run_dir: Path,
    request_payload: dict[str, Any],
    operation: str,
    source_query: str,
    topic_id: str,
    run_id: str,
    link_for_index: str = "",
) -> int:
    result = run_command_capture(command, cwd=run_dir, timeout=max(30, int(request_payload.get("timeout_seconds", 300)) + 30))
    parsed = parse_labeled_lines(result.get("stdout", ""), result.get("stderr", ""))
    response_payload: dict[str, Any] = {
        "command_result": result,
        "parsed_output": parsed,
    }
    verification_note = "Command failed before producing structured evidence."
    success = int(result.get("returncode", 1)) == 0
    note_id = parsed.get("note_id", "")
    note_title = parsed.get("title", "")
    answer = ""
    hits: list[dict[str, Any]] = []
    if parsed.get("saved_result"):
        result_path = Path(parsed["saved_result"])
        if result_path.exists():
            response_payload["script_result"] = read_json(result_path)
            note_id = str(response_payload["script_result"].get("note_id") or note_id).strip()
            note_title = str(response_payload["script_result"].get("note_title") or note_title).strip()
    if parsed.get("saved_workflow_json"):
        workflow_path = Path(parsed["saved_workflow_json"])
        if workflow_path.exists():
            response_payload["workflow_result"] = read_json(workflow_path)
            note_id = str(response_payload["workflow_result"].get("note_id") or note_id).strip()
            note_title = str(response_payload["workflow_result"].get("note_title") or note_title).strip()
            response_payload["workflow_result_path"] = str(workflow_path.resolve())
    transcript_json = parsed.get("saved_transcript_json", "")
    transcript_txt = parsed.get("saved_transcript_txt", "")
    if operation == "get_biji.ingest_link":
        if success and transcript_txt:
            verification_note = "Get笔记 web ingestion succeeded and produced an original transcript artifact."
        elif success:
            verification_note = "Get笔记 web ingestion succeeded and produced a note artifact."
        elif "did not expose an original transcript" in str(result.get("stderr") or ""):
            verification_note = "Get笔记 imported the link but only exposed a summary note, not an original transcript."
        elif "not logged in" in str(result.get("stderr") or ""):
            verification_note = "Get笔记 session is not logged in."
    elif operation == "get_biji.fetch_original":
        if success and transcript_txt:
            verification_note = "Get笔记 original transcript fetch succeeded and produced transcript artifacts."
        elif "not logged in" in str(result.get("stderr") or ""):
            verification_note = "Get笔记 session is not logged in."
    record_payload = build_get_biji_record(
        source="get_biji_web",
        operation=operation,
        success=success,
        topic_id=topic_id,
        query=source_query,
        answer=answer,
        hits=hits,
        raw_response_path=run_dir / "get-biji-response.json",
        verification_note=verification_note,
        run_id=run_id,
        metadata={
            "note_id": note_id,
            "note_title": note_title,
            "transcript_json": transcript_json,
            "transcript_txt": transcript_txt,
            "script_path": str(GET_BIJI_TRANSCRIPT_SCRIPT),
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "deduped": False,
        },
        error="" if success else str(result.get("stderr") or result.get("stdout") or "").strip(),
    )
    write_get_biji_artifacts(run_dir, request_payload=request_payload, response_payload=response_payload, record_payload=record_payload)
    if link_for_index:
        store_get_biji_link_record(
            link_for_index,
            {
                "note_id": note_id,
                "note_title": note_title,
                "topic_id": topic_id,
                "operation": operation,
                "success": success,
                "transcript_json": transcript_json,
                "transcript_txt": transcript_txt,
                "raw_response_path": str((run_dir / "get-biji-response.json").resolve()),
                "record_path": str((run_dir / "get-biji-record.json").resolve()),
                "run_id": run_id,
            },
        )
    print(f"run_id: {run_id}")
    print(f"run_dir: {run_dir}")
    print(f"source: get_biji_web")
    print(f"operation: {operation}")
    print(f"success: {success}")
    if note_id:
        print(f"note_id: {note_id}")
    if note_title:
        print(f"title: {note_title}")
    if transcript_txt:
        print(f"transcript_txt: {transcript_txt}")
    print(f"verification_note: {verification_note}")
    return 0 if success else 1


def execute_get_biji_ingest_link(args: argparse.Namespace, run_dir: Path, run_id: str) -> int:
    verify_get_biji_transcript_tool()
    normalized_link = normalize_get_biji_link(args.link)
    request_payload = {
        "operation": "get_biji.ingest_link",
        "link": normalized_link,
        "mode": args.mode,
        "topic_id": str(args.topic_id or os.getenv("GET_BIJI_TOPIC_ID", "")).strip(),
        "timeout_seconds": int(args.timeout_seconds),
    }
    existing = lookup_get_biji_link(normalized_link)
    if existing:
        record_payload = build_get_biji_record(
            source="get_biji_web",
            operation="get_biji.ingest_link",
            success=bool(existing.get("success", True)),
            topic_id=str(existing.get("topic_id") or request_payload["topic_id"]).strip(),
            query=normalized_link,
            raw_response_path=run_dir / "get-biji-response.json",
            verification_note="Reused existing Get笔记 link mapping from local canonical index.",
            run_id=run_id,
            metadata={**existing, "deduped": True},
            error="" if existing.get("success", True) else "reused_failed_record",
        )
        write_get_biji_artifacts(
            run_dir,
            request_payload=request_payload,
            response_payload={"deduped": True, "existing_record": existing},
            record_payload=record_payload,
        )
        print(f"run_id: {run_id}")
        print(f"run_dir: {run_dir}")
        print("source: get_biji_web")
        print("operation: get_biji.ingest_link")
        print("deduped: true")
        print(f"note_id: {existing.get('note_id', '')}")
        print("verification_note: Reused existing Get笔记 link mapping from local canonical index.")
        return 0 if existing.get("success", True) else 1
    command = [
        "python3",
        str(GET_BIJI_TRANSCRIPT_SCRIPT),
        args.mode,
        "--link",
        normalized_link,
        "--output-dir",
        str(run_dir),
        "--timeout-seconds",
        str(args.timeout_seconds),
    ]
    return execute_get_biji_web_command(
        command=command,
        run_dir=run_dir,
        request_payload=request_payload,
        operation="get_biji.ingest_link",
        source_query=normalized_link,
        topic_id=request_payload["topic_id"],
        run_id=run_id,
        link_for_index=normalized_link,
    )


def execute_get_biji_fetch_original(args: argparse.Namespace, run_dir: Path, run_id: str) -> int:
    verify_get_biji_transcript_tool()
    request_payload = {
        "operation": "get_biji.fetch_original",
        "note_id": str(args.note_id).strip(),
        "topic_id": str(args.topic_id or os.getenv("GET_BIJI_TOPIC_ID", "")).strip(),
        "timeout_seconds": int(args.timeout_seconds),
    }
    command = [
        "python3",
        str(GET_BIJI_TRANSCRIPT_SCRIPT),
        "fetch-original",
        "--note-id",
        str(args.note_id).strip(),
        "--output-dir",
        str(run_dir),
    ]
    return execute_get_biji_web_command(
        command=command,
        run_dir=run_dir,
        request_payload=request_payload,
        operation="get_biji.fetch_original",
        source_query=str(args.note_id).strip(),
        topic_id=request_payload["topic_id"],
        run_id=run_id,
    )


def command_get_biji(args: argparse.Namespace) -> int:
    created_at = iso_now()
    run_id = str(args.run_id or allocate_run_id(created_at))
    run_dir = run_dir_for(run_id, created_at)
    if args.get_biji_command == "ask":
        return execute_get_biji_api_ask(args, run_dir, run_id)
    if args.get_biji_command == "recall":
        return execute_get_biji_api_recall(args, run_dir, run_id)
    if args.get_biji_command == "ingest-link":
        return execute_get_biji_ingest_link(args, run_dir, run_id)
    if args.get_biji_command == "fetch-original":
        return execute_get_biji_fetch_original(args, run_dir, run_id)
    raise ValueError(f"Unsupported get-biji command: {args.get_biji_command}")


def module_available(name: str) -> bool:
    try:
        import importlib.util

        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def command_status(result: dict[str, Any], *, success_codes: set[int] | None = None) -> str:
    allowed = success_codes or {0}
    if result.get("timed_out"):
        return "failed"
    return "passed" if int(result.get("returncode", 1)) in allowed else "blocked"


def path_access_snapshot(path: Path) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "readable": False,
        "sample_entries": [],
        "error": "",
    }
    if not path.exists():
        entry["error"] = "missing"
        return entry
    try:
        if path.is_dir():
            sample = sorted(item.name for item in path.iterdir())[:5]
            entry["sample_entries"] = sample
        else:
            path.read_bytes()[:0]
        entry["readable"] = True
    except Exception as exc:
        entry["error"] = str(exc)
    return entry


def collect_file_system_baseline() -> dict[str, Any]:
    targets = [
        Path.home(),
        Path.home() / "Desktop",
        Path.home() / "Documents",
        CODEX_HOME,
        SKILL_DIR,
    ]
    checks = [path_access_snapshot(path) for path in targets]
    status = "passed" if all(item["exists"] and item["readable"] for item in checks) else "failed"
    return {
        "status": status,
        "checks": checks,
    }


def collect_script_baseline(run_dir: Path) -> dict[str, Any]:
    doctor = run_command_capture(["python3", str(SCRIPT_DIR / "doctor.py")], cwd=SKILL_DIR)
    skills = discover_skills()
    inventory_payload = {
        "generated_at": iso_now(),
        "skills_root": str(SKILLS_ROOT),
        "count": len(skills),
        "skills": skills,
    }
    inventory_path = run_dir / "skills-inventory.json"
    write_json(inventory_path, inventory_payload)
    return {
        "status": command_status(doctor),
        "doctor": doctor,
        "inventory_count": len(skills),
        "inventory_path": str(inventory_path.resolve()),
    }


def collect_applescript_baseline() -> dict[str, Any]:
    ping = run_command_capture(["osascript", "-e", 'return "applecript-ok"'])
    processes = run_command_capture(
        ["osascript", "-e", 'tell application "System Events" to get name of every process'],
        timeout=30,
    )
    process_names = []
    if int(processes.get("returncode", 1)) == 0:
        process_names = [
            item.strip()
            for item in str(processes.get("stdout") or "").split(",")
            if item.strip()
        ]
    active_reuse_targets = [
        name for name in process_names if name in {"Google Chrome", "Safari", "Feishu", "WeChat", "Codex"}
    ]
    status = "passed" if command_status(ping) == "passed" and command_status(processes) == "passed" else "failed"
    return {
        "status": status,
        "ping": ping,
        "process_count": len(process_names),
        "active_reuse_targets": active_reuse_targets,
        "process_sample": process_names[:20],
    }


def collect_gui_baseline(run_dir: Path) -> dict[str, Any]:
    ui_scripting = run_command_capture(
        ["osascript", "-e", 'tell application "System Events" to tell process "Finder" to get name of every window'],
        timeout=30,
    )
    capture_path = run_dir / "desktop-smoke.png"
    screen_capture = run_command_capture(["screencapture", "-x", str(capture_path)], timeout=30)
    capture_exists = capture_path.exists()
    if int(screen_capture.get("returncode", 1)) != 0 and capture_path.exists():
        capture_path.unlink(missing_ok=True)
    statuses = {command_status(ui_scripting), "passed" if capture_exists else command_status(screen_capture)}
    if statuses == {"passed"}:
        status = "passed"
    elif "passed" in statuses:
        status = "partial"
    else:
        status = "blocked"
    return {
        "status": status,
        "ui_scripting": ui_scripting,
        "screen_capture": screen_capture,
        "screen_capture_path": str(capture_path.resolve()) if capture_exists else "",
    }


def run_browser_smoke_test(url: str, run_dir: Path) -> dict[str, Any]:
    screenshot_path = run_dir / "browser-smoke.png"
    if not module_available("playwright"):
        return {
            "status": "blocked",
            "url": url,
            "engine": "",
            "title": "",
            "headline": "",
            "screenshot_path": "",
            "login_reuse_status": "unavailable",
            "error": "python module playwright is not installed",
        }
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return {
            "status": "blocked",
            "url": url,
            "engine": "",
            "title": "",
            "headline": "",
            "screenshot_path": "",
            "login_reuse_status": "unavailable",
            "error": str(exc),
        }

    attempts = [
        ("chrome", {"channel": "chrome", "headless": True}),
        ("chromium", {"headless": True}),
    ]
    errors: list[str] = []
    try:
        with sync_playwright() as playwright:
            for engine_name, launch_kwargs in attempts:
                try:
                    browser = playwright.chromium.launch(**launch_kwargs)
                    page = browser.new_page()
                    page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    title = page.title()
                    headline = ""
                    locator = page.locator("h1")
                    if locator.count():
                        headline = locator.first.inner_text(timeout=3000).strip()
                    page.screenshot(path=str(screenshot_path), full_page=True)
                    browser.close()
                    return {
                        "status": "passed",
                        "url": page.url,
                        "engine": engine_name,
                        "title": title,
                        "headline": headline,
                        "screenshot_path": str(screenshot_path.resolve()),
                        "login_reuse_status": "not_verified_existing_profile",
                        "error": "",
                    }
                except Exception as exc:
                    errors.append(f"{engine_name}: {exc}")
            return {
                "status": "blocked",
                "url": url,
                "engine": "",
                "title": "",
                "headline": "",
                "screenshot_path": "",
                "login_reuse_status": "not_verified_existing_profile",
                "error": " | ".join(errors),
            }
    except Exception as exc:
        return {
            "status": "blocked",
            "url": url,
            "engine": "",
            "title": "",
            "headline": "",
            "screenshot_path": "",
            "login_reuse_status": "not_verified_existing_profile",
            "error": str(exc),
        }


def collect_external_sync_readiness() -> dict[str, Any]:
    bridge_path = Path(os.getenv("AI_DA_GUAN_JIA_FEISHU_BRIDGE_SCRIPT", str(DEFAULT_BRIDGE))).resolve()
    explicit_feishu_link = os.getenv("AI_DA_GUAN_JIA_FEISHU_LINK", "").strip()
    default_feishu_link_available = bool(DEFAULT_FEISHU_LINK.strip())
    feishu_status = (
        "passed"
        if bridge_path.exists() and explicit_feishu_link
        else "partial"
        if bridge_path.exists() and default_feishu_link_available
        else "blocked"
    )
    github_repo = resolve_github_ops_repo()
    github_backend = detect_github_backend()
    gh_path = shutil.which("gh") or ""
    github_status = "passed" if github_repo and github_backend["backend"] else "blocked"
    return {
        "feishu": {
            "status": feishu_status,
            "bridge_script": str(bridge_path),
            "bridge_exists": bridge_path.exists(),
            "explicit_link_configured": bool(explicit_feishu_link),
            "default_link_available": default_feishu_link_available,
        },
        "github": {
            "status": github_status,
            "gh_path": gh_path,
            "repo": github_repo,
            "backend": github_backend["backend"],
            "reason": github_backend["reason"],
            "token_present": bool(os.getenv("GITHUB_TOKEN", "").strip()),
        },
    }


def summarize_capability_baseline(payload: dict[str, Any]) -> dict[str, str]:
    browser = payload["browser"]
    gui = payload["gui"]
    external = payload["external_sync"]
    lines = [
        f"文件与脚本基线 {payload['file_system']['status']} / {payload['scripts']['status']}",
        f"AppleScript 与系统事件 {payload['applescript']['status']}",
        f"浏览器自动化 {browser['status']}，引擎 {browser['engine'] or 'none'}",
        f"GUI 桌面能力 {gui['status']}",
        f"Feishu {external['feishu']['status']}，GitHub {external['github']['status']}",
    ]
    if browser.get("login_reuse_status") and browser["login_reuse_status"] != "verified":
        lines.append("现有登录态复用未直接验真，仍需按具体业务场景补一次真实网页登录流。")
    return {
        "summary": "；".join(lines),
        "next_step": (
            "优先继续走本地文件 + 本地脚本 + 浏览器自动化；涉及登录态、发布、授权或外部写入时再补人类确认。"
        ),
    }


def capability_overall_status(payload: dict[str, Any]) -> str:
    core_statuses = [
        payload["file_system"]["status"],
        payload["scripts"]["status"],
        payload["applescript"]["status"],
        payload["browser"]["status"],
    ]
    if any(status == "failed" for status in core_statuses):
        return "failed"
    optional_statuses = [
        payload["gui"]["status"],
        payload["external_sync"]["feishu"]["status"],
        payload["external_sync"]["github"]["status"],
    ]
    if any(status in {"partial", "blocked", "failed"} for status in optional_statuses):
        return "partial"
    return "passed"


def render_capability_baseline_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Capability Baseline",
        "",
        f"- Run ID: `{payload['run_id']}`",
        f"- Created At: `{payload['created_at']}`",
        f"- Overall Status: `{payload['overall_status']}`",
        "",
        "## Summary",
        "",
        f"- {summary['summary']}",
        f"- {summary['next_step']}",
        "",
        "## File System",
        "",
    ]
    for item in payload["file_system"]["checks"]:
        sample = ", ".join(item["sample_entries"]) or "none"
        lines.append(
            f"- `{item['path']}` :: exists={item['exists']} readable={item['readable']} sample={sample or 'none'}"
        )
    lines.extend(
        [
            "",
            "## Scripts",
            "",
            f"- Status: `{payload['scripts']['status']}`",
            f"- Inventory Count: `{payload['scripts']['inventory_count']}`",
            f"- Inventory Path: `{payload['scripts']['inventory_path']}`",
            f"- Doctor Return Code: `{payload['scripts']['doctor']['returncode']}`",
            "",
            "## Automation Surface",
            "",
            f"- AppleScript: `{payload['applescript']['status']}`",
            f"- Active Reuse Targets: {', '.join(payload['applescript']['active_reuse_targets']) or 'none'}",
            f"- Browser: `{payload['browser']['status']}` via `{payload['browser']['engine'] or 'none'}` on `{payload['browser']['url']}`",
            f"- Browser Title: {payload['browser']['title'] or 'none'}",
            f"- Browser Screenshot: `{payload['browser']['screenshot_path'] or 'none'}`",
            f"- Login Reuse Status: `{payload['browser']['login_reuse_status']}`",
            f"- GUI Desktop: `{payload['gui']['status']}`",
            f"- GUI Screenshot: `{payload['gui']['screen_capture_path'] or 'none'}`",
            "",
            "## External Sync",
            "",
            f"- Feishu: `{payload['external_sync']['feishu']['status']}`",
            f"- Feishu Bridge: `{payload['external_sync']['feishu']['bridge_script']}`",
            f"- Feishu Explicit Link Configured: `{payload['external_sync']['feishu']['explicit_link_configured']}`",
            f"- GitHub: `{payload['external_sync']['github']['status']}`",
            f"- GitHub Repo: `{payload['external_sync']['github']['repo'] or 'none'}`",
            f"- GitHub Backend: `{payload['external_sync']['github']['backend'] or 'none'}`",
            f"- GitHub Reason: `{payload['external_sync']['github']['reason'] or 'none'}`",
            "",
        ]
    )
    return "\n".join(lines)


def command_capability_baseline(args: argparse.Namespace) -> int:
    created_at = str(args.created_at or iso_now())
    run_id = str(args.run_id or allocate_run_id(created_at))
    run_dir = run_dir_for(run_id, created_at)
    browser_url = str(args.browser_url or "https://example.com").strip()

    payload = {
        "run_id": run_id,
        "created_at": created_at,
        "default_execution_surface": [
            "local-files",
            "local-scripts",
            "browser-automation",
            "authenticated-session-reuse",
        ],
        "gui_policy": "on_demand_only_after_browser_or_script_path_fails",
        "file_system": collect_file_system_baseline(),
        "scripts": collect_script_baseline(run_dir),
        "applescript": collect_applescript_baseline(),
        "browser": run_browser_smoke_test(browser_url, run_dir) if not args.skip_browser else {
            "status": "skipped",
            "url": browser_url,
            "engine": "",
            "title": "",
            "headline": "",
            "screenshot_path": "",
            "login_reuse_status": "skipped",
            "error": "",
        },
        "gui": collect_gui_baseline(run_dir) if not args.skip_gui else {
            "status": "skipped",
            "ui_scripting": {},
            "screen_capture": {},
            "screen_capture_path": "",
        },
        "external_sync": collect_external_sync_readiness(),
    }
    payload["overall_status"] = capability_overall_status(payload)
    payload["summary"] = summarize_capability_baseline(payload)
    write_json(run_dir / "capability-baseline.json", payload)
    (run_dir / "capability-baseline.md").write_text(
        render_capability_baseline_markdown(payload),
        encoding="utf-8",
    )
    print(f"run_id: {run_id}")
    print(f"run_dir: {run_dir}")
    print(f"overall_status: {payload['overall_status']}")
    print(f"browser_status: {payload['browser']['status']}")
    print(f"gui_status: {payload['gui']['status']}")
    print(f"feishu_status: {payload['external_sync']['feishu']['status']}")
    print(f"github_status: {payload['external_sync']['github']['status']}")
    return 0


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


def load_optional_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = read_json(path)
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def load_governance_signals() -> dict[str, Any]:
    routing_credit_items = load_optional_json_list(STRATEGY_CURRENT_ROOT / "routing-credit.json")
    autonomy_tier_items = load_optional_json_list(STRATEGY_CURRENT_ROOT / "autonomy-tier.json")
    scorecard_items = load_optional_json_list(STRATEGY_CURRENT_ROOT / "agent-scorecard.json")
    writeback_trust_items = load_optional_json_list(STRATEGY_CURRENT_ROOT / "writeback-trust.json")

    if not routing_credit_items and not autonomy_tier_items and not scorecard_items and not writeback_trust_items:
        return {
            "status": "missing",
            "routing_credit": {},
            "autonomy_tier": {},
            "scorecard": {},
            "writeback_trust": {},
        }

    routing_credit = {
        str(item.get("skill") or "").strip(): float(item.get("routing_credit") or 0)
        for item in routing_credit_items
        if str(item.get("skill") or "").strip()
    }
    autonomy_tier = {
        str(item.get("skill") or "").strip(): str(item.get("autonomy_tier") or "observe").strip() or "observe"
        for item in autonomy_tier_items
        if str(item.get("skill") or "").strip()
    }
    scorecard = {
        str(item.get("skill") or "").strip(): item
        for item in scorecard_items
        if str(item.get("skill") or "").strip()
    }
    writeback_trust = {
        str(item.get("skill") or "").strip(): bool(item.get("writeback_trust"))
        for item in writeback_trust_items
        if str(item.get("skill") or "").strip()
    }
    status = "loaded" if routing_credit_items and autonomy_tier_items else "partial"
    return {
        "status": status,
        "routing_credit": routing_credit,
        "autonomy_tier": autonomy_tier,
        "scorecard": scorecard,
        "writeback_trust": writeback_trust,
    }


def proposal_authority_for_tier(tier: str) -> str:
    return PROPOSAL_AUTHORITY_BY_TIER.get(tier, "passive-candidate")


def routing_credit_adjustment(base_total: float, task_fit_score: int, routing_credit: float) -> int:
    if task_fit_score <= 0 or routing_credit <= 0:
        return 0
    bounded_by_base = int(base_total * MAX_ROUTING_CREDIT_RATIO)
    bounded_by_credit = int(round(routing_credit * 10))
    return max(0, min(MAX_ROUTING_CREDIT_ADJUSTMENT, bounded_by_base, bounded_by_credit))


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


def canonical_mirror_status(machine_status: str, *, system: str) -> str:
    normalized = machine_status.strip()
    if not normalized:
        return "local_only"
    if normalized in {"payload_only_local"}:
        return "local_only"
    if normalized in {
        "dry_run_preview_ready",
        "github_preview_ready",
        "github_intake_preview_ready",
        "github_closure_preview_ready",
    }:
        return "dry_run_ready"
    if normalized in {
        "synced_applied",
        "governance_synced_applied",
        "review_synced_applied",
        "github_intake_synced_applied",
        "github_closure_synced_applied",
    }:
        return "mirrored"
    if "blocked_missing_auth" in normalized:
        return "blocked_auth"
    if "blocked_" in normalized or "missing_link" in normalized or "missing_bridge" in normalized:
        return "apply_failed"
    if normalized.endswith("_failed") or normalized in {"apply_failed", "dry_run_failed", "governance_sync_failed"}:
        return "apply_failed"
    if system == "github" and normalized == "pending_intake":
        return "local_only"
    return "apply_failed"


def governance_window_summary(recent_runs: list[dict[str, Any]], limit: int = GOVERNANCE_WINDOW_LIMIT) -> dict[str, Any]:
    window = recent_runs[:limit]
    total = len(window)
    aware = [item for item in window if str(item.get("governance_signal_status") or "").strip() in {"loaded", "partial"}]
    legacy = [item for item in window if item not in aware]
    comparable = bool(aware)
    latest_aware = aware[0] if aware else {}
    oldest_aware = aware[-1] if aware else {}
    return {
        "window_size": total,
        "governance_aware_runs": len(aware),
        "legacy_runs": len(legacy),
        "comparable_window_ready": comparable,
        "aware_ratio": round(len(aware) / total, 2) if total else 0.0,
        "effective_window_start": str(oldest_aware.get("created_at") or ""),
        "effective_window_end": str(latest_aware.get("created_at") or ""),
        "route_scorecard_version": ROUTE_SCORECARD_VERSION,
        "closure_scorecard_version": CLOSURE_SCORECARD_VERSION,
    }


def governance_calibration_payload(recent_runs: list[dict[str, Any]]) -> dict[str, Any]:
    window = governance_window_summary(recent_runs)
    return {
        "generated_at": iso_now(),
        "governance_window": window,
        "versions": {
            "route_scorecard_version": ROUTE_SCORECARD_VERSION,
            "closure_scorecard_version": CLOSURE_SCORECARD_VERSION,
            "honesty_gate_min": HONESTY_GATE_MIN,
        },
        "mixing_rule": (
            "Do not compare legacy runs with governance-aware runs in promotion/demotion decisions. "
            "Use the comparable window only."
        ),
    }


def proposal_queue_from_threads(thread_proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    for item in thread_proposals:
        queue.append(
            {
                "proposal_id": item["id"],
                "goal_id": item["goal_id"],
                "initiative_id": item["initiative_id"],
                "title": item["title"],
                "proposal_status": item.get("proposal_status", "pending_approval"),
                "approval_state": item.get("approval_state", "pending"),
                "launch_state": item.get("launch_state", "not_started"),
                "external_execution_allowed": bool(item.get("external_execution_allowed", False)),
            }
        )
    return queue


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
        "feishu_mirror_status": canonical_mirror_status(str(evolution["feishu_sync_status"]), system="feishu"),
        "github_sync_status": str(evolution.get("github_sync_status") or ""),
        "github_mirror_status": canonical_mirror_status(str(evolution.get("github_sync_status") or ""), system="github"),
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
        f"- Canonical Mirror Status: {worklog['github_mirror_status']}",
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


def latest_bundle_directories() -> dict[str, Path]:
    candidates: dict[str, tuple[Path, str]] = {}
    roots = [HUB_OUTBOX_ROOT / "sources"]
    repo = resolve_github_ops_repo()
    if repo:
        roots.append(hub_repo_dir(repo) / "sources")
    for root in roots:
        if not root.exists():
            continue
        for latest_dir in root.glob("*/latest"):
            manifest_path = latest_dir / "manifest.json"
            if not manifest_path.exists():
                continue
            manifest = load_optional_json(manifest_path)
            source_id = str(manifest.get("source_id") or latest_dir.parent.name).strip()
            generated_at = str(manifest.get("generated_at") or "")
            current = candidates.get(source_id)
            if current is None or generated_at >= current[1]:
                candidates[source_id] = (latest_dir, generated_at)
    return {source_id: path for source_id, (path, _) in candidates.items()}


def load_bundle_payloads(bundle_root: Path) -> dict[str, Any]:
    return {
        "manifest": load_optional_json(bundle_root / "manifest.json"),
        "machine_profile": load_optional_json(bundle_root / "machine-profile.json"),
        "skills": load_optional_json_list(bundle_root / "skills.json"),
        "sessions": load_optional_json_list(bundle_root / "sessions.json"),
        "runs": load_optional_json_list(bundle_root / "runs.json"),
        "github_summary": load_optional_json(bundle_root / "github-summary.json"),
        "automations": load_optional_json_list(bundle_root / "automations.json"),
    }


def previous_latest_bundle(source_id: str) -> dict[str, Any]:
    repo = resolve_github_ops_repo()
    for root in [hub_repo_dir(repo) / "sources" / source_id / "latest", HUB_OUTBOX_ROOT / "sources" / source_id / "latest"]:
        manifest_path = root / "manifest.json"
        if manifest_path.exists():
            return load_bundle_payloads(root)
    return {}


def filter_delta_payloads(
    source_id: str,
    skills: list[dict[str, Any]],
    sessions: list[dict[str, Any]],
    runs: list[dict[str, Any]],
    automations: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    previous = previous_latest_bundle(source_id)
    manifest = previous.get("manifest", {}) if isinstance(previous.get("manifest"), dict) else {}
    previous_generated_at = str(manifest.get("generated_at") or "")
    previous_skill_names = {str(item.get("name") or "") for item in previous.get("skills", []) if isinstance(item, dict)}
    previous_session_keys = {
        f"{item.get('session_id', '')}:{item.get('updated_at', '')}"
        for item in previous.get("sessions", [])
        if isinstance(item, dict)
    }
    previous_run_keys = {
        f"{item.get('run_id', '')}:{item.get('created_at', '')}"
        for item in previous.get("runs", [])
        if isinstance(item, dict)
    }
    previous_automation_keys = {
        f"{item.get('id', '')}:{item.get('status', '')}:{item.get('rrule', '')}"
        for item in previous.get("automations", [])
        if isinstance(item, dict)
    }
    delta_skills = [item for item in skills if str(item.get("name") or "") not in previous_skill_names]
    delta_sessions = [
        item
        for item in sessions
        if f"{item.get('session_id', '')}:{item.get('updated_at', '')}" not in previous_session_keys
        and str(item.get("updated_at") or "") >= previous_generated_at
    ]
    delta_runs = [
        item
        for item in runs
        if f"{item.get('run_id', '')}:{item.get('created_at', '')}" not in previous_run_keys
        and str(item.get("created_at") or "") >= previous_generated_at
    ]
    delta_automations = [
        item
        for item in automations
        if f"{item.get('id', '')}:{item.get('status', '')}:{item.get('rrule', '')}" not in previous_automation_keys
    ]
    return delta_skills, delta_sessions, delta_runs, delta_automations


def task_key_type(observation: dict[str, Any]) -> str:
    if observation.get("github_task_key"):
        return "github_task_key"
    if observation.get("run_id"):
        return "run_id"
    if observation.get("session_id") and observation.get("normalized_title"):
        return "session_key"
    return "normalized_task_hash"


def canonical_task_key(observation: dict[str, Any]) -> str:
    if observation.get("github_task_key"):
        return f"github:{observation['github_task_key']}"
    if observation.get("run_id"):
        return f"run:{observation['run_id']}"
    if observation.get("session_id") and observation.get("normalized_title"):
        return f"session:{observation['session_id']}::{observation['normalized_title']}"
    return f"hash:{observation.get('normalized_task_hash') or stable_hash(observation.get('task_text', ''))}"


def task_observations_from_bundle(source_id: str, bundle: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in bundle.get("runs", []):
        if not isinstance(run, dict):
            continue
        task_text = str(run.get("task_text") or "").strip()
        normalized_title = normalize_prompt(task_text) if task_text else ""
        proof_strength = str(run.get("proof_strength") or "route")
        verification = run.get("verification_result") if isinstance(run.get("verification_result"), dict) else {}
        rows.append(
            {
                "source_id": source_id,
                "origin_type": "run",
                "task_text": task_text,
                "normalized_title": normalized_title,
                "normalized_task_hash": str(run.get("normalized_task_hash") or stable_hash(normalized_title)),
                "run_id": str(run.get("run_id") or "").strip(),
                "session_id": "",
                "github_task_key": str(run.get("github_task_key") or "").strip(),
                "created_at": str(run.get("created_at") or "").strip(),
                "selected_skills": normalize_list(run.get("selected_skills")),
                "verification_result": normalize_verification_result(verification),
                "structured_artifacts": normalize_list(run.get("structured_artifacts")),
                "evidence_types": normalize_list(run.get("evidence_types")),
                "proof_strength": proof_strength,
                "key_type": "",
            }
        )
    for session in bundle.get("sessions", []):
        if not isinstance(session, dict):
            continue
        task_text = str(session.get("thread_name") or "").strip()
        normalized_title = normalize_prompt(task_text)
        rows.append(
            {
                "source_id": source_id,
                "origin_type": "session",
                "task_text": task_text,
                "normalized_title": normalized_title,
                "normalized_task_hash": str(session.get("normalized_task_hash") or stable_hash(normalized_title)),
                "run_id": "",
                "session_id": str(session.get("session_id") or "").strip(),
                "github_task_key": "",
                "created_at": str(session.get("updated_at") or "").strip(),
                "selected_skills": [],
                "verification_result": {"status": "", "evidence": [], "open_questions": []},
                "structured_artifacts": [],
                "evidence_types": ["session"],
                "proof_strength": "session",
                "key_type": "",
            }
        )
    for row in rows:
        row["key_type"] = task_key_type(row)
    return rows


def merge_task_observation(base: dict[str, Any], observation: dict[str, Any]) -> dict[str, Any]:
    candidate = dict(base)
    base_key_priority = TASK_EVIDENCE_PRIORITY.get(str(base.get("key_type") or ""), 0)
    obs_key_priority = TASK_EVIDENCE_PRIORITY.get(str(observation.get("key_type") or ""), 0)
    base_proof_priority = TASK_PROOF_PRIORITY.get(str(base.get("proof_strength") or ""), 0)
    obs_proof_priority = TASK_PROOF_PRIORITY.get(str(observation.get("proof_strength") or ""), 0)
    if (obs_key_priority, obs_proof_priority, str(observation.get("created_at") or "")) > (
        base_key_priority,
        base_proof_priority,
        str(base.get("created_at") or ""),
    ):
        candidate.update(
            {
                key: value
                for key, value in observation.items()
                if key
                in {
                    "task_text",
                    "normalized_title",
                    "run_id",
                    "session_id",
                    "github_task_key",
                    "created_at",
                    "verification_result",
                    "proof_strength",
                    "key_type",
                }
                and value
            }
        )
    candidate["selected_skills"] = normalize_list(candidate.get("selected_skills")) + [
        item for item in normalize_list(observation.get("selected_skills")) if item not in normalize_list(candidate.get("selected_skills"))
    ]
    candidate["structured_artifacts"] = normalize_list(candidate.get("structured_artifacts")) + [
        item for item in normalize_list(observation.get("structured_artifacts")) if item not in normalize_list(candidate.get("structured_artifacts"))
    ]
    candidate["evidence_types"] = normalize_list(candidate.get("evidence_types")) + [
        item for item in normalize_list(observation.get("evidence_types")) if item not in normalize_list(candidate.get("evidence_types"))
    ]
    candidate["source_refs"] = normalize_list(candidate.get("source_refs")) + [
        item
        for item in [f"{observation.get('source_id')}:{observation.get('origin_type')}:{observation.get('run_id') or observation.get('session_id') or observation.get('normalized_task_hash')}"]
        if item not in normalize_list(candidate.get("source_refs"))
    ]
    if candidate.get("proof_strength") == "session" and observation.get("proof_strength") != "session":
        candidate["proof_strength"] = observation.get("proof_strength")
    verification = normalize_verification_result(candidate.get("verification_result"))
    obs_verification = normalize_verification_result(observation.get("verification_result"))
    if not verification.get("status") and obs_verification.get("status"):
        candidate["verification_result"] = obs_verification
    return candidate


def task_maturity(task: dict[str, Any]) -> str:
    text = str(task.get("task_text") or "").strip()
    verification = normalize_verification_result(task.get("verification_result"))
    has_closed_form = bool(
        {"evolution", "worklog"} & set(normalize_list(task.get("evidence_types")))
    )
    has_verify = bool(str(verification.get("status") or "").strip()) or bool(normalize_list(verification.get("evidence")))
    if text and has_closed_form and has_verify:
        return "High"
    if text and (
        task.get("run_id")
        or task.get("session_id")
        or normalize_list(task.get("structured_artifacts"))
    ):
        return "Medium"
    return "Low"


def aggregate_task_ledger(source_bundles: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    canonical: dict[str, dict[str, Any]] = {}
    hash_to_keys: dict[str, list[str]] = {}
    for source_id, bundle in source_bundles.items():
        for observation in task_observations_from_bundle(source_id, bundle):
            key = canonical_task_key(observation)
            task = canonical.get(key)
            if task is None:
                task = {
                    **observation,
                    "canonical_task_key": key,
                    "source_refs": [],
                }
            task = merge_task_observation(task, observation)
            canonical[key] = task
            hash_key = str(task.get("normalized_task_hash") or "")
            if hash_key:
                hash_to_keys.setdefault(hash_key, [])
                if key not in hash_to_keys[hash_key]:
                    hash_to_keys[hash_key].append(key)
    for keys in hash_to_keys.values():
        if len(keys) <= 1:
            continue
        ranked = sorted(
            (canonical[key] for key in keys if key in canonical),
            key=lambda item: (
                TASK_EVIDENCE_PRIORITY.get(str(item.get("key_type") or ""), 0),
                TASK_PROOF_PRIORITY.get(str(item.get("proof_strength") or ""), 0),
                str(item.get("created_at") or ""),
            ),
            reverse=True,
        )
        winner = ranked[0]
        for loser in ranked[1:]:
            if winner["canonical_task_key"] == loser["canonical_task_key"]:
                continue
            winner = merge_task_observation(winner, loser)
            canonical.pop(loser["canonical_task_key"], None)
        canonical[winner["canonical_task_key"]] = winner
    rows: list[dict[str, Any]] = []
    for task in canonical.values():
        task["maturity"] = task_maturity(task)
        rows.append(task)
    rows.sort(key=lambda item: (str(item.get("created_at") or ""), item["canonical_task_key"]))
    return rows


def aggregate_skill_ledger(source_bundles: dict[str, dict[str, Any]], task_ledger: list[dict[str, Any]]) -> list[dict[str, Any]]:
    usage_counts: dict[str, int] = {}
    for task in task_ledger:
        for skill in normalize_list(task.get("selected_skills")):
            usage_counts[skill] = usage_counts.get(skill, 0) + 1
    overlap_lookup: dict[str, list[str]] = {}
    synthetic_inventory: list[dict[str, Any]] = []
    merged: dict[str, dict[str, Any]] = {}
    for source_id, bundle in source_bundles.items():
        for skill in bundle.get("skills", []):
            if not isinstance(skill, dict):
                continue
            name = str(skill.get("name") or "").strip()
            if not name:
                continue
            artifact = skill.get("artifact_shape") if isinstance(skill.get("artifact_shape"), dict) else {}
            item = merged.setdefault(
                name,
                {
                    "name": name,
                    "description": str(skill.get("description") or ""),
                    "installed_on_sources": [],
                    "origin_repo": str(skill.get("source_repo") or ""),
                    "artifact_shape": {
                        "SKILL.md": False,
                        "scripts": False,
                        "references": False,
                        "assets": False,
                        "agents": False,
                    },
                    "usage_evidence_count": 0,
                    "overlap_flags": [],
                    "resource_score": 0,
                    "type": str(skill.get("type") or ""),
                    "layer": str(skill.get("layer") or ""),
                },
            )
            if source_id not in item["installed_on_sources"]:
                item["installed_on_sources"].append(source_id)
            if not item["origin_repo"]:
                item["origin_repo"] = str(skill.get("source_repo") or "")
            for key in item["artifact_shape"]:
                item["artifact_shape"][key] = bool(item["artifact_shape"].get(key) or artifact.get(key))
            item["usage_evidence_count"] = usage_counts.get(name, 0)
            item["resource_score"] = sum(1 for value in item["artifact_shape"].values() if value)
            synthetic_inventory.append(
                {
                    "name": name,
                    "description": str(skill.get("description") or ""),
                    "directory_name": str(skill.get("directory_name") or name),
                    "layer": str(skill.get("layer") or ""),
                    "cluster": str(skill.get("cluster") or ""),
                    "type": str(skill.get("type") or ""),
                    "resource_score": int(skill.get("resource_score") or item["resource_score"]),
                }
            )
    for pair in boundary_overlap_pairs(synthetic_inventory):
        reason = str(pair.get("reason") or "")
        for skill_name in normalize_list(pair.get("skills")):
            overlap_lookup.setdefault(skill_name, [])
            if reason and reason not in overlap_lookup[skill_name]:
                overlap_lookup[skill_name].append(reason)
    rows: list[dict[str, Any]] = []
    for item in merged.values():
        item["installed_on_sources"].sort()
        item["overlap_flags"] = sorted(overlap_lookup.get(item["name"], []))
        if item["overlap_flags"]:
            maturity = "Low"
        elif item["type"] == "persona":
            maturity = "Medium" if item["artifact_shape"]["SKILL.md"] and item["resource_score"] >= 4 and item["usage_evidence_count"] > 0 else "Low"
        elif item["artifact_shape"]["SKILL.md"] and item["resource_score"] >= 3 and item["usage_evidence_count"] > 0:
            maturity = "High"
        elif item["artifact_shape"]["SKILL.md"] and (item["resource_score"] >= 2 or item["usage_evidence_count"] > 0):
            maturity = "Medium"
        else:
            maturity = "Low"
        item["maturity"] = maturity
        rows.append(item)
    rows.sort(key=lambda item: item["name"])
    return rows


def build_source_status(
    source_bundles: dict[str, dict[str, Any]],
    *,
    expected_sources: list[str] | None = None,
    bootstrap_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bootstrap_status = bootstrap_status or load_optional_json(HUB_ROOT / "bootstrap-status.json")
    expected = resolve_expected_sources(expected_sources or normalize_list(bootstrap_status.get("expected_sources")))
    connected = sorted(source_bundles.keys())
    missing = [item for item in expected if item not in connected]
    rows = []
    for source_id in expected:
        bundle = source_bundles.get(source_id, {})
        manifest = bundle.get("manifest", {}) if isinstance(bundle.get("manifest"), dict) else {}
        profile = bundle.get("machine_profile", {}) if isinstance(bundle.get("machine_profile"), dict) else {}
        rows.append(
            {
                "source_id": source_id,
                "status": "connected" if source_id in connected else "missing",
                "generated_at": str(manifest.get("generated_at") or ""),
                "role": str(profile.get("role") or ("canonical_hub" if source_id == "main-hub" else "satellite_reporter")),
                "hostname": str(profile.get("hostname") or ""),
            }
        )
    return {
        "generated_at": iso_now(),
        "expected_sources": expected,
        "connected_sources": connected,
        "missing_sources": missing,
        "rows": rows,
    }


def build_inventory_summary(
    source_bundles: dict[str, dict[str, Any]],
    task_ledger: list[dict[str, Any]],
    skill_ledger: list[dict[str, Any]],
    *,
    source_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_status = source_status or build_source_status(source_bundles)
    task_counts = {"High": 0, "Medium": 0, "Low": 0}
    skill_counts = {"High": 0, "Medium": 0, "Low": 0}
    for item in task_ledger:
        task_counts[str(item.get("maturity") or "Low")] += 1
    for item in skill_ledger:
        skill_counts[str(item.get("maturity") or "Low")] += 1
    transport_status = load_optional_json(HUB_ROOT / "transport-status.json")
    return {
        "generated_at": iso_now(),
        "sources_total": len(source_bundles),
        "source_ids": sorted(source_bundles.keys()),
        "expected_sources": source_status.get("expected_sources", []),
        "connected_sources": source_status.get("connected_sources", []),
        "missing_sources": source_status.get("missing_sources", []),
        "tasks_total": len(task_ledger),
        "skills_total": len(skill_ledger),
        "task_maturity": task_counts,
        "skill_maturity": skill_counts,
        "transport": {
            "hub_repo": transport_status.get("hub_repo", ""),
            "remote_reachable": bool(transport_status.get("remote_probe", {}).get("reachable")),
            "github_backend": str(transport_status.get("github_backend", {}).get("backend") or ""),
        },
    }


def build_recommendations(
    task_ledger: list[dict[str, Any]],
    skill_ledger: list[dict[str, Any]],
    source_bundles: dict[str, dict[str, Any]],
    *,
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = summary or build_inventory_summary(source_bundles, task_ledger, skill_ledger)
    low_persona = [item["name"] for item in skill_ledger if item.get("maturity") == "Low" and str(item.get("type") or "") == "persona"]
    overlap = [item["name"] for item in skill_ledger if normalize_list(item.get("overlap_flags"))]
    missing_sources = normalize_list(summary.get("missing_sources"))
    remote_reachable = bool(summary.get("transport", {}).get("remote_reachable"))
    github_backend = str(summary.get("transport", {}).get("github_backend") or "")
    return {
        "generated_at": iso_now(),
        "root_causes": [
            "技能库未同步" if missing_sources else "三端来源已全部接入",
            "统一 task ledger 已建立，但跨端覆盖仍未完整" if missing_sources else "统一 task ledger 已建立并具备三端覆盖",
            "GitHub hub 仍待真正远端连通" if not remote_reachable else "GitHub hub 已具备远端 transport",
            "GitHub auth/tooling 不完整" if not github_backend else "GitHub backend 已有可用通道",
            "run schema 基本可聚合",
        ],
        "next_steps": [
            {
                "priority": 1,
                "title": "先打通 ai-task-ops 远端 transport",
                "why": "当前 hub 远端不可达，必须先完成 GitHub 仓创建与 auth，才能让三端 bundle 真正汇入统一公网中枢。",
            },
            {
                "priority": 2,
                "title": "让另外两台机器完成首次 full intake",
                "why": f"当前仍缺少来源: {' | '.join(missing_sources) or 'none'}；三端接管成立前不进入正式治理日常。",
            },
            {
                "priority": 3,
                "title": "优先 hardening 高频低成熟度技能",
                "why": f"当前低成熟度 persona/workflow 仍多，典型包括: {' | '.join(low_persona[:8]) or 'none'}。",
            },
        ],
        "deferred_next_steps": [
            {
                "priority": 4,
                "title": "清理 overlap 与重复命名",
                "why": f"当前存在边界冲突或重复的技能包括: {' | '.join(overlap[:8]) or 'none'}。",
            }
        ],
    }


def render_analysis_report(
    summary: dict[str, Any],
    recommendations: dict[str, Any],
    task_ledger: list[dict[str, Any]],
    skill_ledger: list[dict[str, Any]],
) -> str:
    top_tasks = [item for item in task_ledger if item.get("maturity") == "High"][:5]
    low_skills = [item["name"] for item in skill_ledger if item.get("maturity") == "Low"][:10]
    lines = [
        "# Hub Analysis Report",
        "",
        "## 全量盘点",
        "",
        f"- 来源数: {summary['sources_total']}",
        f"- 任务总数: {summary['tasks_total']}",
        f"- 技能总数: {summary['skills_total']}",
        f"- 来源列表: {' | '.join(summary['source_ids']) or 'none'}",
        f"- 预期来源: {' | '.join(summary.get('expected_sources', [])) or 'none'}",
        f"- 缺失来源: {' | '.join(summary.get('missing_sources', [])) or 'none'}",
        f"- GitHub transport: repo={summary.get('transport', {}).get('hub_repo', '') or 'none'} reachable={summary.get('transport', {}).get('remote_reachable', False)} backend={summary.get('transport', {}).get('github_backend', '') or 'none'}",
        "",
        "## 成熟度评价",
        "",
        f"- 任务 High / Medium / Low: {summary['task_maturity']['High']} / {summary['task_maturity']['Medium']} / {summary['task_maturity']['Low']}",
        f"- 技能 High / Medium / Low: {summary['skill_maturity']['High']} / {summary['skill_maturity']['Medium']} / {summary['skill_maturity']['Low']}",
        f"- 高成熟任务样本: {' | '.join(item['task_text'] for item in top_tasks) or 'none'}",
        f"- 低成熟技能样本: {' | '.join(low_skills) or 'none'}",
        "",
        "## 下一步推动建议",
        "",
    ]
    for item in recommendations.get("next_steps", []):
        lines.append(f"- P{item['priority']}: {item['title']} :: {item['why']}")
    for item in recommendations.get("deferred_next_steps", []):
        lines.append(f"- Deferred P{item['priority']}: {item['title']} :: {item['why']}")
    lines.append("")
    return "\n".join(lines)


def build_push_order(summary: dict[str, Any], governance_review: dict[str, Any] | None = None) -> dict[str, Any]:
    readiness = governance_readiness_from_hub(summary)
    governance_review = governance_review or {}
    recommended_action = ""
    action_titles = {
        str(item.get("id") or ""): str(item.get("title") or "")
        for item in governance_review.get("candidate_actions", [])
        if isinstance(item, dict)
    } if isinstance(governance_review, dict) else {}
    if "A" in action_titles:
        recommended_action = "A"
    priorities = [
        {
            "priority": 1,
            "title": "先打通外部 transport",
            "status": "done" if readiness["transport_ready"] else "blocked",
            "why": "治理系统已能跑，但 GitHub transport 和治理 Feishu 镜像未同时具备时，只能算本地基线。",
            "acceptance": [
                "remote_reachable = true",
                "github_backend != none",
                "AI_DA_GUAN_JIA_GOVERNANCE_FEISHU_LINK 已配置",
            ],
        },
        {
            "priority": 2,
            "title": "补齐三端来源",
            "status": "done" if readiness["multi_source_ready"] else "blocked",
            "why": "全量盘点首先要求来源全量；单机视角不能视为正式治理结论。",
            "acceptance": [
                "source-registry 出现 main-hub / satellite-01 / satellite-02",
                "Missing Sources = none",
            ],
        },
        {
            "priority": 3,
            "title": "执行治理动作 A 的第一批诚实度样板",
            "status": "ready" if readiness["transport_ready"] or governance_review else "pending",
            "why": "当前最缺的是高质量治理样板，而不是继续调分公式。",
            "acceptance": [
                "5 个样板对象产出 honesty hardening brief",
                "至少 2 个对象从低诚实度样本名单中移出",
                "routing / autonomy 的 gate 变化可观察",
            ],
            "recommended_action_id": recommended_action,
            "recommended_action_title": action_titles.get(recommended_action, ""),
        },
        {
            "priority": 4,
            "title": "孵化 workflow-hardening",
            "status": "pending",
            "why": "当前已有 3 条稳定 workflow，可在样板对象之后转成显式 hardening brief。",
            "acceptance": [
                "生成 workflow hardening brief",
                "至少 2/3 workflow 从 Low 进入 Mid",
            ],
        },
        {
            "priority": 5,
            "title": "最后推进 G2/G3 器官化",
            "status": "pending",
            "why": "提案自治与激励体系必须建立在可信 workflow 和多源治理账本上。",
            "acceptance": [
                "agent-incentive-governor 不再只是缺口",
                "promotion/demotion 建议稳定生成",
            ],
        },
    ]
    return {
        "generated_at": iso_now(),
        "readiness": readiness,
        "priorities": priorities,
        "summary": {
            "current_stage": readiness["stage"],
            "recommended_next_action_id": recommended_action,
            "missing_sources": readiness["missing_sources"],
        },
    }


def render_push_order_markdown(payload: dict[str, Any]) -> str:
    readiness = payload.get("readiness", {})
    lines = [
        "# Push Order",
        "",
        f"- Current Stage: `{readiness.get('stage', 'baseline_only')}`",
        f"- Transport Ready: `{readiness.get('transport_ready', False)}`",
        f"- Multi Source Ready: `{readiness.get('multi_source_ready', False)}`",
        f"- Formal Governance Ready: `{readiness.get('formal_governance_ready', False)}`",
        f"- Blockers: {' | '.join(normalize_list(readiness.get('blockers'))) or 'none'}",
        "",
    ]
    for item in payload.get("priorities", []):
        lines.extend(
            [
                f"## P{item['priority']} {item['title']}",
                "",
                f"- Status: `{item['status']}`",
                f"- Why: {item['why']}",
                f"- Acceptance: {' | '.join(item.get('acceptance', [])) or 'none'}",
                (
                    f"- Recommended Governance Action: {item.get('recommended_action_id', '')} {item.get('recommended_action_title', '')}".rstrip()
                    if item.get("recommended_action_id")
                    else ""
                ),
                "",
            ]
        )
    return "\n".join(line for line in lines if line != "")


def write_push_order_outputs(summary: dict[str, Any], governance_review: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = build_push_order(summary, governance_review)
    write_json(HUB_CURRENT_ROOT / "readiness-status.json", payload["readiness"])
    write_json(HUB_CURRENT_ROOT / "push-order.json", payload)
    (HUB_CURRENT_ROOT / "push-order.md").write_text(render_push_order_markdown(payload), encoding="utf-8")
    return payload


def write_hub_current_outputs(
    *,
    source_bundles: dict[str, dict[str, Any]],
    task_ledger: list[dict[str, Any]],
    skill_ledger: list[dict[str, Any]],
    source_status: dict[str, Any],
    summary: dict[str, Any],
    recommendations: dict[str, Any],
) -> None:
    ensure_dir(HUB_CURRENT_ROOT)
    transport_status = load_optional_json(HUB_ROOT / "transport-status.json")
    governance_review = latest_governance_review_payload()
    write_json(
        HUB_CURRENT_ROOT / "source-registry.json",
        [
            {
                "source_id": source_id,
                "generated_at": bundle.get("manifest", {}).get("generated_at", ""),
                "role": bundle.get("machine_profile", {}).get("role", ""),
                "hostname": bundle.get("machine_profile", {}).get("hostname", ""),
            }
            for source_id, bundle in sorted(source_bundles.items())
        ],
    )
    write_json(HUB_CURRENT_ROOT / "source-status.json", source_status)
    write_json(HUB_CURRENT_ROOT / "transport-status.json", transport_status)
    write_json(HUB_CURRENT_ROOT / "task-ledger.json", task_ledger)
    write_json(HUB_CURRENT_ROOT / "skill-ledger.json", skill_ledger)
    write_json(
        HUB_CURRENT_ROOT / "maturity-scorecard.json",
        {
            "generated_at": iso_now(),
            "task_maturity": summary["task_maturity"],
            "skill_maturity": summary["skill_maturity"],
        },
    )
    write_json(HUB_CURRENT_ROOT / "inventory-summary.json", summary)
    write_json(HUB_CURRENT_ROOT / "recommendations.json", recommendations)
    (HUB_CURRENT_ROOT / "analysis-report.md").write_text(
        render_analysis_report(summary, recommendations, task_ledger, skill_ledger),
        encoding="utf-8",
    )
    write_push_order_outputs(summary, governance_review)


def latest_hub_summary() -> dict[str, Any]:
    return load_optional_json(HUB_CURRENT_ROOT / "inventory-summary.json")


def latest_hub_recommendations() -> dict[str, Any]:
    return load_optional_json(HUB_CURRENT_ROOT / "recommendations.json")


def build_strategy_hub_audit_summary(
    summary: dict[str, Any] | None = None,
    recommendations: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = summary or latest_hub_summary()
    recommendations = recommendations or latest_hub_recommendations()
    source_status = load_optional_json(HUB_CURRENT_ROOT / "source-status.json")
    transport_status = load_optional_json(HUB_CURRENT_ROOT / "transport-status.json")
    return {
        "generated_at": iso_now(),
        "canonical_root": str(HUB_CURRENT_ROOT),
        "summary": summary,
        "source_status": source_status,
        "transport_status": transport_status,
        "recommendations": recommendations,
        "consistency": {
            "missing_sources_match": normalize_list(summary.get("missing_sources")) == normalize_list(source_status.get("missing_sources")),
            "connected_sources_match": normalize_list(summary.get("connected_sources")) == normalize_list(source_status.get("connected_sources")),
            "transport_match": bool(summary.get("transport", {}).get("remote_reachable")) == bool(transport_status.get("remote_probe", {}).get("reachable")),
        },
    }


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


def find_governance_review_run_dir(run_id: str) -> Path:
    for date_dir in sorted(GOVERNANCE_REVIEWS_ROOT.glob("*")) if GOVERNANCE_REVIEWS_ROOT.exists() else []:
        candidate = date_dir / run_id
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"governance review run_id not found: {run_id}")


def resolve_review_feishu_link(link_override: str | None = None) -> str:
    return (
        link_override
        or os.getenv("AI_DA_GUAN_JIA_REVIEW_FEISHU_LINK")
        or os.getenv("AI_DA_GUAN_JIA_FEISHU_LINK")
        or DEFAULT_REVIEW_FEISHU_LINK
    ).strip()


def resolve_governance_feishu_link(link_override: str | None = None) -> str:
    return (
        link_override
        or os.getenv("AI_DA_GUAN_JIA_GOVERNANCE_FEISHU_LINK")
        or DEFAULT_GOVERNANCE_FEISHU_LINK
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


def write_governance_review_sync_result(run_dir: Path, payload: dict[str, Any]) -> None:
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


def sync_governance_review_to_feishu(
    run_id: str,
    *,
    link_override: str | None = None,
    bridge_script_override: str | None = None,
) -> tuple[int, str]:
    run_dir = find_governance_review_run_dir(run_id)
    review = read_json(run_dir / "review.json")
    skill_rows = load_optional_json_list(run_dir / "skills-governance.json")
    workflow_rows = load_optional_json_list(run_dir / "workflows-governance.json")
    agent_rows = load_optional_json_list(run_dir / "agents-governance.json")
    component_rows = load_optional_json_list(run_dir / "components-governance.json")
    workflow_registry = load_optional_json_list(run_dir / "workflow-registry.json")
    if not isinstance(review, dict):
        raise RuntimeError(f"governance review artifacts are incomplete for {run_id}")

    materials = write_governance_review_materials(
        run_dir,
        review=review,
        skill_rows=skill_rows,
        workflow_rows=workflow_rows,
        agent_rows=agent_rows,
        component_rows=component_rows,
        workflow_registry=workflow_registry,
    )
    bundle = materials["bundle"]
    bridge_script = Path(
        bridge_script_override
        or os.getenv("AI_DA_GUAN_JIA_FEISHU_BRIDGE_SCRIPT", str(DEFAULT_BRIDGE))
    ).resolve()
    link = resolve_governance_feishu_link(link_override)

    if not link:
        payload = sync_result_payload(
            run_id=run_id,
            mode="apply",
            status="governance_sync_blocked_missing_link",
            link="",
            reason="No governance Feishu link configured.",
        )
        write_governance_review_sync_result(run_dir, payload)
        return 1, payload["status"]
    if not bridge_script.exists():
        payload = sync_result_payload(
            run_id=run_id,
            mode="apply",
            status="governance_sync_blocked_missing_bridge",
            link=link,
            reason=f"bridge script not found: {bridge_script}",
        )
        write_governance_review_sync_result(run_dir, payload)
        return 1, payload["status"]
    if not GOVERNANCE_SCHEMA_MANIFEST.exists():
        payload = sync_result_payload(
            run_id=run_id,
            mode="apply",
            status="governance_sync_blocked_missing_manifest",
            link=link,
            reason=f"governance schema manifest not found: {GOVERNANCE_SCHEMA_MANIFEST}",
        )
        write_governance_review_sync_result(run_dir, payload)
        return 1, payload["status"]

    command_results: list[dict[str, Any]] = []
    schema_command = [
        "python3",
        str(bridge_script),
        "sync-base-schema",
        "--link",
        link,
        "--manifest",
        str(GOVERNANCE_SCHEMA_MANIFEST),
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
            status="governance_sync_failed",
            link=link,
            reason="schema sync failed",
            command_results=command_results,
        )
        write_governance_review_sync_result(run_dir, payload)
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
        status="governance_synced_applied" if not failed else "governance_sync_failed",
        link=link,
        reason="" if not failed else "One or more governance table upserts failed.",
        command_results=command_results,
    )
    write_governance_review_sync_result(run_dir, payload)
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
        "治理提权判断": (
            "Governance-weighted routing influenced this run."
            if evolution.get("governance_signal_status") != "missing"
            else "Governance-weighted routing was unavailable for this run."
        ),
    }
    (run_dir / "situation-map.md").write_text(
        render_situation_map(situation_map, evolution["task_text"]),
        encoding="utf-8",
    )
    write_json(run_dir / "route.json", route_payload)
    write_json(run_dir / "evolution.json", evolution)
    if isinstance(evolution.get("closure_assessment"), dict):
        write_json(run_dir / "closure-assessment.json", evolution["closure_assessment"])
    if isinstance(evolution.get("incentive_decision"), dict):
        write_json(run_dir / "incentive-decision.json", evolution["incentive_decision"])
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
    budget_profile = evolution.get("budget_profile") if isinstance(evolution.get("budget_profile"), dict) else {}
    closure_assessment = (
        evolution.get("closure_assessment") if isinstance(evolution.get("closure_assessment"), dict) else {}
    )
    incentive_decision = (
        evolution.get("incentive_decision") if isinstance(evolution.get("incentive_decision"), dict) else {}
    )
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
        f"- Governance Signal Status: {evolution.get('governance_signal_status') or 'missing'}",
        f"- Credit Influenced Selection: {bool(evolution.get('credit_influenced_selection', False))}",
        f"- Proposal Authority Summary: {json.dumps(evolution.get('proposal_authority_summary') or {}, ensure_ascii=False)}",
        "",
        "## Verification",
        "",
        f"- Status: {verification['status']}",
        f"- Evidence: {' | '.join(normalize_list(verification['evidence'])) or 'none'}",
        f"- Open Questions: {' | '.join(normalize_list(verification['open_questions'])) or 'none'}",
        "",
        "## Budget And Incentive",
        "",
        f"- Budget Tier: {budget_profile.get('tier') or 'none'}",
        f"- Soft Token Cap: {budget_profile.get('soft_token_cap') or 'none'}",
        f"- Hard Token Cap: {budget_profile.get('hard_token_cap') or 'none'}",
        f"- Soft Time Cap: {budget_profile.get('soft_time_cap') or 'none'} minutes",
        f"- Hard Time Cap: {budget_profile.get('hard_time_cap') or 'none'} minutes",
        f"- Observed Token Usage: {evolution.get('observed_token_usage') if evolution.get('observed_token_usage') is not None else 'unknown'}",
        f"- Observed Duration Minutes: {evolution.get('observed_duration_minutes') if evolution.get('observed_duration_minutes') is not None else 'unknown'}",
        f"- Closure Score: {closure_assessment.get('closure_score', 'none')}",
        f"- Closure Gates: {json.dumps(closure_assessment.get('gates') or {}, ensure_ascii=False)}",
        f"- Incentive Levers: {json.dumps(incentive_decision.get('levers') or {}, ensure_ascii=False)}",
        f"- Incentive Penalties: {' | '.join(normalize_list(incentive_decision.get('penalties'))) or 'none'}",
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
            f"- GitHub Mirror Status: `{canonical_mirror_status(str(evolution.get('github_sync_status') or ''), system='github')}`",
            f"- Archive Status: `{evolution.get('github_archive_status') or 'none'}`",
            f"- Closure Comment URL: {evolution.get('github_closure_comment_url') or 'none'}",
        ]
    )
    lines.extend(
        [
            "",
            f"- Feishu Sync Status: `{evolution['feishu_sync_status']}`",
            f"- Feishu Mirror Status: `{canonical_mirror_status(str(evolution['feishu_sync_status']), system='feishu')}`",
            "",
        ]
    )
    return "\n".join(lines)


def bootstrap_hub_repo(repo: str, expected_sources: list[str] | None = None) -> dict[str, Any]:
    expected_sources = resolve_expected_sources(expected_sources)
    ensure_dir(HUB_ROOT)
    ensure_dir(HUB_REPOS_ROOT)
    ensure_dir(HUB_CURRENT_ROOT)
    ensure_dir(HUB_OUTBOX_ROOT)
    repo_dir = hub_repo_dir(repo)
    ensure_dir(repo_dir)
    ensure_dir(repo_dir / "sources")
    ensure_dir(repo_dir / "reports" / "main-hub" / "latest")
    ensure_dir(repo_dir / "contracts")
    (repo_dir / "README.md").write_text(
        "\n".join(
            [
                "# AI Task Ops Hub",
                "",
                f"- Canonical repo target: `{repo}`",
                "- This repo stores intake bundles mirrored from each machine and canonical hub reports.",
                "- Local ai-da-guan-jia artifacts remain the source of truth.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (repo_dir / "contracts" / "intake-bundle-v1.md").write_text(
        "\n".join(
            [
                "# Intake Bundle Contract",
                "",
                "- Fixed files: manifest.json, machine-profile.json, skills.json, sessions.json, runs.json, github-summary.json, automations.json, ingest-notes.md",
                "- Source bundles live under sources/<source-id>/latest and sources/<source-id>/snapshots/YYYY-MM-DD/<timestamp>",
                "- Canonical hub reports live under reports/main-hub/latest",
                "",
            ]
        ),
        encoding="utf-8",
    )
    onboarding_text = render_satellite_onboarding(repo, expected_sources)
    (repo_dir / "ONBOARDING.md").write_text(onboarding_text, encoding="utf-8")
    (HUB_ROOT / "satellite-onboarding.md").write_text(onboarding_text, encoding="utf-8")
    source_topology = {
        "generated_at": iso_now(),
        "hub_repo": repo,
        "expected_sources": expected_sources,
        "canonical_source": "main-hub",
        "satellite_sources": [item for item in expected_sources if item != "main-hub"],
    }
    write_json(HUB_ROOT / "source-topology.json", source_topology)
    write_json(repo_dir / "contracts" / "source-topology.json", source_topology)
    remote_probe = {
        "remote": f"git@github.com:{repo}.git",
        "reachable": False,
        "stderr": "",
        "stdout": "",
    }
    if repo:
        completed = subprocess.run(
            ["git", "ls-remote", f"git@github.com:{repo}.git", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        remote_probe["reachable"] = completed.returncode == 0
        remote_probe["stdout"] = completed.stdout.strip()
        remote_probe["stderr"] = completed.stderr.strip()
    result = {
        "generated_at": iso_now(),
        "hub_repo": repo,
        "hub_repo_dir": str(repo_dir),
        "expected_sources": expected_sources,
        "gh_installed": bool(shutil.which("gh")),
        "github_backend": detect_github_backend(),
        "github_token_configured": bool(os.getenv("GITHUB_TOKEN", "").strip()),
        "remote_probe": remote_probe,
    }
    write_json(HUB_ROOT / "bootstrap-status.json", result)
    write_json(HUB_ROOT / "transport-status.json", result)
    return result


def command_bootstrap_hub(args: argparse.Namespace) -> int:
    repo = resolve_github_ops_repo(args.repo)
    result = bootstrap_hub_repo(repo, expected_sources=args.expected_source)
    print(f"hub_repo: {repo}")
    print(f"hub_repo_dir: {result['hub_repo_dir']}")
    print(f"expected_sources: {', '.join(result['expected_sources'])}")
    print(f"gh_installed: {result['gh_installed']}")
    print(f"github_backend: {result['github_backend'].get('backend') or 'none'}")
    print(f"remote_reachable: {result['remote_probe']['reachable']}")
    return 0


def command_emit_intake_bundle(args: argparse.Namespace) -> int:
    source_id = normalize_slug_part(args.source_id.strip())
    mode = str(args.mode)
    repo = resolve_github_ops_repo(args.repo)
    bootstrap_hub_repo(repo)
    local_repo_dir = hub_repo_dir(repo)
    full_skills = collect_top_level_skill_inventory()
    full_sessions = summarize_session_index()
    full_runs = summarize_local_runs()
    full_automations = summarize_local_automations()
    skills = full_skills
    sessions = full_sessions
    runs = full_runs
    automations = full_automations
    if mode == "delta":
        skills, sessions, runs, automations = filter_delta_payloads(source_id, skills, sessions, runs, automations)
    github_summary = github_summary_payload(skills, runs)
    latest_github_summary = github_summary_payload(full_skills, full_runs)
    latest_root, snapshot_root = bundle_roots_for_source(source_id)
    payloads = {
        "manifest.json": bundle_manifest(
            source_id=source_id,
            mode=mode,
            skills=skills,
            sessions=sessions,
            runs=runs,
            automations=automations,
            local_repo_dir=str(local_repo_dir),
        ),
        "machine-profile.json": machine_profile_payload(source_id),
        "skills.json": skills,
        "sessions.json": sessions,
        "runs.json": runs,
        "github-summary.json": github_summary,
        "automations.json": automations,
    }
    latest_payloads = {
        "manifest.json": bundle_manifest(
            source_id=source_id,
            mode="full",
            skills=full_skills,
            sessions=full_sessions,
            runs=full_runs,
            automations=full_automations,
            local_repo_dir=str(local_repo_dir),
        ),
        "machine-profile.json": machine_profile_payload(source_id),
        "skills.json": full_skills,
        "sessions.json": full_sessions,
        "runs.json": full_runs,
        "github-summary.json": latest_github_summary,
        "automations.json": full_automations,
    }
    notes = "\n".join(
        [
            "# Intake Notes",
            "",
            f"- Source ID: `{source_id}`",
            f"- Mode: `{mode}`",
            f"- Skills: {len(skills)}",
            f"- Sessions: {len(sessions)}",
            f"- Runs: {len(runs)}",
            f"- Automations: {len(automations)}",
            "",
        ]
    )
    latest_notes = "\n".join(
        [
            "# Intake Notes",
            "",
            f"- Source ID: `{source_id}`",
            "- Mode: `full`",
            f"- Skills: {len(full_skills)}",
            f"- Sessions: {len(full_sessions)}",
            f"- Runs: {len(full_runs)}",
            f"- Automations: {len(full_automations)}",
            "",
        ]
    )
    write_intake_bundle(snapshot_root, payloads, notes)
    write_intake_bundle(latest_root, latest_payloads, latest_notes)
    repo_latest = local_repo_dir / "sources" / source_id / "latest"
    repo_snapshot = local_repo_dir / "sources" / source_id / "snapshots" / now_local().strftime("%Y-%m-%d") / snapshot_root.name
    copy_bundle_to_target(snapshot_root, repo_snapshot)
    write_intake_bundle(repo_latest, latest_payloads, latest_notes)
    print(f"source_id: {source_id}")
    print(f"mode: {mode}")
    print(f"snapshot_root: {snapshot_root}")
    print(f"latest_root: {latest_root}")
    print(f"repo_latest: {repo_latest}")
    print(f"skills: {len(skills)}")
    print(f"sessions: {len(sessions)}")
    print(f"runs: {len(runs)}")
    return 0


def command_aggregate_hub(args: argparse.Namespace) -> int:
    source_id = normalize_slug_part(args.source_id.strip())
    repo = resolve_github_ops_repo(args.repo)
    bootstrap_hub_repo(repo, expected_sources=args.expected_source)
    bundles = latest_bundle_directories()
    if source_id not in bundles:
        # Make the local machine visible even if emit-intake-bundle was not run yet.
        synthetic_args = argparse.Namespace(source_id=source_id, mode="full", repo=repo)
        command_emit_intake_bundle(synthetic_args)
        bundles = latest_bundle_directories()
    source_bundles = {bundle_source_id: load_bundle_payloads(path) for bundle_source_id, path in bundles.items()}
    task_ledger = aggregate_task_ledger(source_bundles)
    skill_ledger = aggregate_skill_ledger(source_bundles, task_ledger)
    source_status = build_source_status(source_bundles, expected_sources=args.expected_source)
    summary = build_inventory_summary(source_bundles, task_ledger, skill_ledger, source_status=source_status)
    recommendations = build_recommendations(task_ledger, skill_ledger, source_bundles, summary=summary)
    write_hub_current_outputs(
        source_bundles=source_bundles,
        task_ledger=task_ledger,
        skill_ledger=skill_ledger,
        source_status=source_status,
        summary=summary,
        recommendations=recommendations,
    )
    repo_report_root = hub_repo_dir(repo) / "reports" / source_id / "latest"
    clear_directory(repo_report_root)
    for name in [
        "source-registry.json",
        "source-status.json",
        "transport-status.json",
        "task-ledger.json",
        "skill-ledger.json",
        "maturity-scorecard.json",
        "inventory-summary.json",
        "analysis-report.md",
        "recommendations.json",
        "readiness-status.json",
        "push-order.json",
        "push-order.md",
    ]:
        shutil.copy2(HUB_CURRENT_ROOT / name, repo_report_root / name)
    print(f"source_id: {source_id}")
    print(f"sources_total: {summary['sources_total']}")
    print(f"missing_sources: {', '.join(summary.get('missing_sources', [])) or 'none'}")
    print(f"tasks_total: {summary['tasks_total']}")
    print(f"skills_total: {summary['skills_total']}")
    print(f"hub_current_root: {HUB_CURRENT_ROOT}")
    return 0


def command_audit_maturity(args: argparse.Namespace) -> int:
    summary = latest_hub_summary()
    if not summary:
        aggregate_args = argparse.Namespace(source_id=args.source_id, repo=args.repo, expected_source=args.expected_source)
        command_aggregate_hub(aggregate_args)
        summary = latest_hub_summary()
    task_ledger = load_optional_json_list(HUB_CURRENT_ROOT / "task-ledger.json")
    skill_ledger = load_optional_json_list(HUB_CURRENT_ROOT / "skill-ledger.json")
    source_registry = load_optional_json_list(HUB_CURRENT_ROOT / "source-registry.json")
    source_bundles = {
        str(item.get("source_id") or ""): {"machine_profile": item}
        for item in source_registry
        if str(item.get("source_id") or "").strip()
    }
    recommendations = build_recommendations(
        task_ledger,
        skill_ledger,
        source_bundles,
        summary=summary,
    )
    (HUB_CURRENT_ROOT / "analysis-report.md").write_text(
        render_analysis_report(summary, recommendations, task_ledger, skill_ledger),
        encoding="utf-8",
    )
    write_json(HUB_CURRENT_ROOT / "recommendations.json", recommendations)
    push_order = write_push_order_outputs(summary, latest_governance_review_payload())
    write_json(STRATEGY_CURRENT_ROOT / "hub-audit-summary.json", build_strategy_hub_audit_summary(summary, recommendations))
    write_strategy_operating_system()
    print(f"tasks_total: {summary.get('tasks_total', 0)}")
    print(f"skills_total: {summary.get('skills_total', 0)}")
    print(f"task_maturity: {summary.get('task_maturity', {})}")
    print(f"skill_maturity: {summary.get('skill_maturity', {})}")
    print(f"current_stage: {push_order.get('readiness', {}).get('stage', 'baseline_only')}")
    print(f"transport_ready: {push_order.get('readiness', {}).get('transport_ready', False)}")
    print(f"analysis_report: {HUB_CURRENT_ROOT / 'analysis-report.md'}")
    return 0


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
    governance = load_governance_signals()
    ranked = [score_candidate(prompt, skill, signals, mentioned, governance) for skill in skills]
    ranked.sort(key=lambda item: item["total_score"], reverse=True)
    selected, omitted = choose_skills(prompt, ranked, signals, mentioned)
    budget_profile = resolve_budget_profile(signals, selected)
    route_gates = build_route_gates(ranked=ranked, selected=selected, signals=signals)
    get_biji_plan = plan_get_biji_actions(prompt) if signals["get_biji"] else {}
    situation_map = build_situation_map(prompt, selected, signals)
    situation_map["治理提权判断"] = (
        "Governance-weighted routing is active; routing credit only adjusts near-tie candidates."
        if governance["status"] != "missing"
        else "Governance-weighted routing is unavailable; fallback to rule-only routing."
    )
    created_at = iso_now()
    run_id = args.run_id or allocate_run_id(created_at)
    run_dir = run_dir_for(run_id, created_at)
    route_payload = {
        "run_id": run_id,
        "created_at": created_at,
        "task_text": prompt,
        "routing_order": ROUTING_ORDER,
        "route_scorecard_version": ROUTE_SCORECARD_VERSION,
        "signals": signals,
        "governance_signal_status": governance["status"],
        "credit_influenced_selection": credit_influenced_selection(ranked, selected),
        "skills_considered": [item["name"] for item in ranked],
        "candidate_rankings": ranked[:10],
        "selected_skills": selected,
        "route_gates": route_gates,
        "budget_profile": budget_profile,
        "proposal_authority_summary": selected_proposal_authority_summary(ranked, selected),
        "omitted_due_to_selection_ceiling": omitted,
        "selection_ceiling": selection_ceiling(signals),
        "human_boundary": determine_human_boundary(signals),
        "verification_targets": verification_targets(signals, get_biji_plan),
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
    route_payload.update(get_biji_plan)
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
    if route_payload.get("primary_action"):
        print(f"primary_action: {route_payload['primary_action']}")
    if route_payload.get("human_route_summary"):
        print(f"route_summary: {route_payload['human_route_summary']}")
    for action in route_payload.get("recommended_actions", []):
        index = int(action.get("step_index", 0) or 0)
        if index <= 0:
            continue
        print(f"next_command_{index}: {action.get('cli_command', '')}")
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


def command_skill_scout(args: argparse.Namespace) -> int:
    if not args.daily:
        raise ValueError("skill-scout currently requires --daily.")
    channels = normalize_list(args.channels) or SKILL_SCOUT_CHANNEL_CHOICES
    invalid = [item for item in channels if item not in SKILL_SCOUT_CHANNEL_CHOICES]
    if invalid:
        raise ValueError(f"unsupported channels: {', '.join(invalid)}")
    result = run_skill_scout_daily(channels, sync_feishu=args.sync_feishu)
    print(f"run_id: {result['run_id']}")
    print(f"run_dir: {result['run_dir']}")
    print(f"shortlist_count: {result['shortlist_count']}")
    print(f"mirror_status: {result['mirror_status']}")
    print(f"env_blockers: {', '.join(result['summary'].get('env_blockers', [])) or 'none'}")
    return 0


def command_review_governance(args: argparse.Namespace) -> int:
    state = load_governance_review_state()
    if args.resolve_action:
        run_id = str(args.run_id or state.get("latest_run_id") or "").strip()
        if not run_id:
            raise ValueError("--run-id is required when no latest governance review run exists.")
        status = {
            "latest_run_id": run_id,
            "status": "resolved",
            "pending_action_ids": [],
            "carryover_pending_action_ids": [],
            "selected_action_id": str(args.resolve_action).strip(),
            "resolved_at": iso_now(),
        }
        save_governance_review_state(status)
        run_dir = None
        try:
            run_dir = find_governance_review_run_dir(run_id)
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
                    skill_rows = load_optional_json_list(run_dir / "skills-governance.json")
                    workflow_rows = load_optional_json_list(run_dir / "workflows-governance.json")
                    agent_rows = load_optional_json_list(run_dir / "agents-governance.json")
                    component_rows = load_optional_json_list(run_dir / "components-governance.json")
                    workflow_registry = load_optional_json_list(run_dir / "workflow-registry.json")
                    write_governance_review_materials(
                        run_dir,
                        review=review_payload,
                        skill_rows=skill_rows,
                        workflow_rows=workflow_rows,
                        agent_rows=agent_rows,
                        component_rows=component_rows,
                        workflow_registry=workflow_registry,
                    )
                    generated_artifacts = write_governance_action_artifacts(
                        run_dir=run_dir,
                        review=review_payload,
                        skill_rows=skill_rows,
                        workflow_rows=workflow_rows,
                        workflow_registry=workflow_registry,
                    )
                else:
                    generated_artifacts = []
            else:
                generated_artifacts = []
        else:
            generated_artifacts = []
        print("status: resolved")
        print(f"run_id: {run_id}")
        print(f"selected_action_id: {status['selected_action_id']}")
        print(f"generated_artifacts: {', '.join(generated_artifacts) or 'none'}")
        if args.sync_feishu and run_dir is not None:
            sync_code, sync_status = sync_governance_review_to_feishu(
                run_id,
                link_override=args.link,
                bridge_script_override=args.bridge_script,
            )
            print(f"sync_status: {sync_status}")
            return sync_code
        return 0

    if not args.daily and not args.backfill:
        raise ValueError("review-governance requires --daily, --backfill, or --resolve-action.")

    created_at = iso_now()
    run_id = allocate_governance_review_run_id(created_at)
    run_dir = governance_review_run_dir_for(run_id, created_at)
    inventory = build_review_inventory()
    recent_runs = iter_evolution_records(limit=5000)
    workflow_registry = workflow_registry_from_runs(recent_runs)
    workflow_runs = workflow_run_map(recent_runs, workflow_registry)
    component_payload = load_component_register()
    carryover = normalize_list(state.get("carryover_pending_action_ids"))
    if state.get("status") == "awaiting_human_choice":
        carryover.extend(normalize_list(state.get("pending_action_ids")))
    carryover = normalize_list(carryover)
    mode = "backfill" if args.backfill else "daily"
    if mode == "backfill":
        carryover = []

    skill_rows = build_skill_governance_rows(inventory, recent_runs, carryover_action_ids=carryover)
    workflow_rows = build_workflow_governance_rows(workflow_registry, workflow_runs, carryover_action_ids=carryover)
    agent_rows = build_agent_governance_rows(inventory, recent_runs, carryover_action_ids=carryover)
    component_rows = build_component_governance_rows(component_payload, carryover_action_ids=carryover)
    review = build_governance_review_payload(
        run_id=run_id,
        created_at=created_at,
        mode=mode,
        skill_rows=skill_rows,
        workflow_rows=workflow_rows,
        agent_rows=agent_rows,
        component_rows=component_rows,
        carryover_action_ids=carryover,
    )
    write_governance_review_materials(
        run_dir,
        review=review,
        skill_rows=skill_rows,
        workflow_rows=workflow_rows,
        agent_rows=agent_rows,
        component_rows=component_rows,
        workflow_registry=workflow_registry,
    )
    if mode == "daily":
        save_governance_review_state(
            {
                "latest_run_id": run_id,
                "status": "awaiting_human_choice",
                "pending_action_ids": [action["id"] for action in review["candidate_actions"]],
                "carryover_pending_action_ids": carryover,
                "created_at": created_at,
            }
        )
    else:
        save_governance_review_state(
            {
                "latest_run_id": state.get("latest_run_id", ""),
                "status": state.get("status", "idle"),
                "pending_action_ids": normalize_list(state.get("pending_action_ids")),
                "carryover_pending_action_ids": normalize_list(state.get("carryover_pending_action_ids")),
                "created_at": state.get("created_at", ""),
            }
        )

    print(f"status: {review['status']}")
    print(f"mode: {mode}")
    print(f"run_id: {run_id}")
    print(f"run_dir: {run_dir}")
    print(f"objects_total: {review['objects_total']}")
    print(f"candidate_actions: {', '.join(action['id'] for action in review['candidate_actions'])}")
    print(f"carryover_actions: {', '.join(review['carryover_action_ids']) or 'none'}")
    window = review.get("governance_window", {})
    print(
        "governance_window: "
        f"aware={window.get('governance_aware_runs', 0)} "
        f"legacy={window.get('legacy_runs', 0)} "
        f"ready={window.get('comparable_window_ready', False)}"
    )
    if args.sync_feishu:
        sync_code, sync_status = sync_governance_review_to_feishu(
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
    print(f"proposal_queue: {len(bundle['proposal_queue'])}")
    print(f"recruitment_candidates: {len(bundle['recruitment'])}")
    print(f"scorecard_entries: {len(bundle['scorecard'])}")
    print(
        "governance_window: "
        f"aware={bundle['governance_calibration']['governance_window']['governance_aware_runs']} "
        f"legacy={bundle['governance_calibration']['governance_window']['legacy_runs']}"
    )
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
    governance = load_governance_signals()
    governance_status = str(
        payload.get("governance_signal_status")
        or route_payload.get("governance_signal_status")
        or governance.get("status")
        or "missing"
    )
    credit_influenced = bool(
        payload.get("credit_influenced_selection")
        if "credit_influenced_selection" in payload
        else route_payload.get("credit_influenced_selection", False)
    )
    proposal_authority_summary = payload.get("proposal_authority_summary")
    if not isinstance(proposal_authority_summary, dict):
        route_summary = route_payload.get("proposal_authority_summary")
        proposal_authority_summary = route_summary if isinstance(route_summary, dict) else {}
    human_boundary = str(
        payload.get("human_boundary") or route_payload.get("human_boundary") or determine_human_boundary(signals)
    )
    budget_profile = payload.get("budget_profile") if isinstance(payload.get("budget_profile"), dict) else {}
    if not budget_profile:
        route_budget_profile = route_payload.get("budget_profile")
        if isinstance(route_budget_profile, dict):
            budget_profile = route_budget_profile
    if not budget_profile:
        budget_profile = resolve_budget_profile(signals, selected)
    observed_token_usage = None
    if str(payload.get("observed_token_usage") or "").strip():
        observed_token_usage = float(payload["observed_token_usage"])
    observed_duration_minutes = None
    if str(payload.get("observed_duration_minutes") or "").strip():
        observed_duration_minutes = float(payload["observed_duration_minutes"])

    closure_assessment = build_closure_assessment(
        verification=normalize_verification_result(payload.get("verification_result")),
        skills_selected=selected,
        effective_patterns=normalize_list(payload.get("effective_patterns")),
        governance_status=governance_status,
        human_boundary=human_boundary,
        budget_profile=budget_profile,
        observed_token_usage=observed_token_usage,
        observed_duration_minutes=observed_duration_minutes,
    )
    incentive_decision = build_incentive_decision(
        closure_assessment=closure_assessment,
        selected_skills=selected,
        governance_status=governance_status,
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
        "governance_signal_status": governance_status,
        "credit_influenced_selection": credit_influenced,
        "proposal_authority_summary": proposal_authority_summary,
        "budget_profile": budget_profile,
        "observed_token_usage": observed_token_usage,
        "observed_duration_minutes": observed_duration_minutes,
        "closure_assessment": closure_assessment,
        "incentive_decision": incentive_decision,
    }

    get_biji_plan = plan_get_biji_actions(task_text) if signals["get_biji"] else {}
    route_payload = {
        "run_id": run_id,
        "created_at": created_at,
        "task_text": task_text,
        "routing_order": ROUTING_ORDER,
        "route_scorecard_version": ROUTE_SCORECARD_VERSION,
        "signals": signals,
        "governance_signal_status": governance_status,
        "credit_influenced_selection": credit_influenced,
        "skills_considered": evolution["skills_considered"],
        "candidate_rankings": route_payload.get("candidate_rankings", []),
        "selected_skills": evolution["skills_selected"],
        "route_gates": route_payload.get("route_gates")
        or {
            "honesty_gate": {"passed": True, "mode": "record-only", "threshold": HONESTY_GATE_MIN},
            "verification_gate": {"passed": bool(route_payload.get("verification_targets")), "threshold": VERIFICATION_GATE_MIN},
            "boundary_gate": {
                "passed": True,
                "requires_human_checkpoint": bool(signals["hard_boundary"] or signals["feishu"]),
                "summary": human_boundary,
            },
        },
        "budget_profile": budget_profile,
        "proposal_authority_summary": proposal_authority_summary,
        "omitted_due_to_selection_ceiling": route_payload.get("omitted_due_to_selection_ceiling", []),
        "selection_ceiling": selection_ceiling(signals),
        "human_boundary": human_boundary,
        "verification_targets": route_payload.get("verification_targets", verification_targets(signals, get_biji_plan)),
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
    for field in GET_BIJI_ROUTE_FIELDS:
        if field not in route_payload and field in get_biji_plan:
            route_payload[field] = get_biji_plan[field]
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
    link = resolve_task_feishu_link(link_override)
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
            "reason": "Neither AI_DA_GUAN_JIA_FEISHU_LINK nor the built-in default Feishu link is configured.",
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
    governance = load_governance_signals()
    ranked = [score_candidate(task_text, skill, signals, mentioned, governance) for skill in skills]
    ranked.sort(key=lambda item: item["total_score"], reverse=True)
    selected, omitted = choose_skills(task_text, ranked, signals, mentioned)
    get_biji_plan = plan_get_biji_actions(task_text) if signals["get_biji"] else {}
    situation_map = build_situation_map(task_text, selected, signals)
    situation_map["治理提权判断"] = (
        "Governance-weighted routing is active; routing credit only adjusts near-tie candidates."
        if governance["status"] != "missing"
        else "Governance-weighted routing is unavailable; fallback to rule-only routing."
    )
    human_boundary = str(args.human_boundary or determine_human_boundary(signals))
    route_payload = {
        "run_id": run_id,
        "created_at": created_at,
        "task_text": task_text,
        "routing_order": ROUTING_ORDER,
        "signals": signals,
        "governance_signal_status": governance["status"],
        "credit_influenced_selection": credit_influenced_selection(ranked, selected),
        "skills_considered": [item["name"] for item in ranked],
        "candidate_rankings": ranked[:10],
        "selected_skills": selected,
        "proposal_authority_summary": selected_proposal_authority_summary(ranked, selected),
        "omitted_due_to_selection_ceiling": omitted,
        "selection_ceiling": selection_ceiling(signals),
        "human_boundary": human_boundary,
        "verification_targets": verification_targets(signals, get_biji_plan),
        "feishu_plan": [
            "write local canonical evolution log",
            "generate feishu-payload.json",
            "run sync-feishu --dry-run",
            "run sync-feishu --apply",
        ],
        "situation_map": situation_map,
    }
    route_payload.update(get_biji_plan)

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
        "governance_signal_status": governance["status"],
        "credit_influenced_selection": credit_influenced_selection(ranked, selected),
        "proposal_authority_summary": selected_proposal_authority_summary(ranked, selected),
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
    parser = argparse.ArgumentParser(
        description="Local helper for the ai-da-guan-jia skill.",
        epilog=(
            "command groups:\n"
            "  core: route, close-task, review-skills, review-governance, strategy-governor\n"
            "  ops: inventory-skills, bootstrap-hub, emit-intake-bundle, aggregate-hub, audit-maturity, capability-baseline, record-evolution, sync-feishu, sync-github\n"
            "  experimental: get-biji, skill-scout"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser("inventory-skills", help="[ops] Scan local skills and write a normalized inventory.")
    inventory.add_argument("--output", help="Optional output JSON path.")
    inventory.set_defaults(func=command_inventory_skills)

    bootstrap = subparsers.add_parser(
        "bootstrap-hub",
        help="[ops] Prepare the local hub mirror for the ai-task-ops intake repository and record auth/readiness status.",
    )
    bootstrap.add_argument("--repo", help="Optional GitHub hub repo override in owner/name format.")
    bootstrap.add_argument("--expected-source", action="append", help="Expected source id for the three-terminal topology. Repeatable.")
    bootstrap.set_defaults(func=command_bootstrap_hub)

    emit = subparsers.add_parser(
        "emit-intake-bundle",
        help="[ops] Capture local skills, sessions, runs, GitHub summary, and automations into a fixed intake bundle.",
    )
    emit.add_argument("--source-id", required=True, help="Stable source id for this machine.")
    emit.add_argument("--mode", choices=["full", "delta"], default="full", help="Bundle mode label.")
    emit.add_argument("--repo", help="Optional GitHub hub repo override in owner/name format.")
    emit.set_defaults(func=command_emit_intake_bundle)

    aggregate = subparsers.add_parser(
        "aggregate-hub",
        help="[ops] Merge all latest source bundles into the canonical hub ledgers and reports.",
    )
    aggregate.add_argument("--source-id", default="main-hub", help="Canonical hub source id. Defaults to main-hub.")
    aggregate.add_argument("--repo", help="Optional GitHub hub repo override in owner/name format.")
    aggregate.add_argument("--expected-source", action="append", help="Expected source id for topology status. Repeatable.")
    aggregate.set_defaults(func=command_aggregate_hub)

    audit = subparsers.add_parser(
        "audit-maturity",
        help="[ops] Score tasks and skills into High/Medium/Low maturity and refresh the hub analysis outputs.",
    )
    audit.add_argument("--source-id", default="main-hub", help="Canonical hub source id. Defaults to main-hub.")
    audit.add_argument("--repo", help="Optional GitHub hub repo override in owner/name format.")
    audit.add_argument("--expected-source", action="append", help="Expected source id for topology status. Repeatable.")
    audit.set_defaults(func=command_audit_maturity)

    route = subparsers.add_parser("route", help="[core] Build a situation map and route the task to the best local skills.")
    route.add_argument("--prompt", required=True, help="Task prompt to analyze.")
    route.add_argument("--run-id", help="Optional run id override.")
    route.set_defaults(func=command_route)

    get_biji = subparsers.add_parser(
        "get-biji",
        help="[experimental] Use the Get笔记 dual-track integration for API retrieval or web ingestion.",
    )
    get_biji_subparsers = get_biji.add_subparsers(dest="get_biji_command", required=True)

    get_biji_ask = get_biji_subparsers.add_parser("ask", help="Query Get笔记 through the OpenAPI question-answer path.")
    get_biji_ask.add_argument("--question", required=True, help="Natural-language question sent to Get笔记.")
    get_biji_ask.add_argument("--topic-id", help="Optional topic id override. Defaults to GET_BIJI_TOPIC_ID.")
    get_biji_ask.add_argument("--knowledge-base-id", help="Optional knowledge base identifier.")
    get_biji_ask.add_argument("--user", default="ai-da-guan-jia", help="OpenAPI user identifier.")
    get_biji_ask.add_argument("--run-id", help="Optional run id override.")
    get_biji_ask.set_defaults(func=command_get_biji)

    get_biji_recall = get_biji_subparsers.add_parser("recall", help="Recall candidate notes or chunks from Get笔记.")
    get_biji_recall.add_argument("--query", required=True, help="Query text used for retrieval.")
    get_biji_recall.add_argument("--topic-id", help="Optional topic id override. Defaults to GET_BIJI_TOPIC_ID.")
    get_biji_recall.add_argument("--knowledge-base-id", help="Optional knowledge base identifier.")
    get_biji_recall.add_argument("--top-k", type=int, default=5, help="Desired retrieval count.")
    get_biji_recall.add_argument("--run-id", help="Optional run id override.")
    get_biji_recall.set_defaults(func=command_get_biji)

    get_biji_ingest = get_biji_subparsers.add_parser(
        "ingest-link",
        help="Ingest an external link into Get笔记 using the existing web skill.",
    )
    get_biji_ingest.add_argument("--link", required=True, help="External link to import into Get笔记.")
    get_biji_ingest.add_argument(
        "--mode",
        choices=["submit-link", "transcribe-link"],
        default="submit-link",
        help="Use submit-link for note generation or transcribe-link for transcript extraction.",
    )
    get_biji_ingest.add_argument("--topic-id", help="Optional topic id to record alongside the link mapping.")
    get_biji_ingest.add_argument("--timeout-seconds", type=int, default=300, help="Seconds to wait for Get笔记 note generation.")
    get_biji_ingest.add_argument("--run-id", help="Optional run id override.")
    get_biji_ingest.set_defaults(func=command_get_biji)

    get_biji_original = get_biji_subparsers.add_parser(
        "fetch-original",
        help="Fetch the original transcript for an existing Get笔记 note id.",
    )
    get_biji_original.add_argument("--note-id", required=True, help="Get笔记 note id.")
    get_biji_original.add_argument("--topic-id", help="Optional topic id to associate with this fetch.")
    get_biji_original.add_argument("--timeout-seconds", type=int, default=300, help="Reserved for contract symmetry.")
    get_biji_original.add_argument("--run-id", help="Optional run id override.")
    get_biji_original.set_defaults(func=command_get_biji)

    review = subparsers.add_parser(
        "review-skills",
        help="[core] Review top-level installed skills, generate 3 candidate evolution actions, or resolve the current review choice.",
    )
    review_mode = review.add_mutually_exclusive_group(required=True)
    review_mode.add_argument("--daily", action="store_true", help="Run the daily top-level skill review flow.")
    review_mode.add_argument("--resolve-action", help="Mark the latest review or the provided run id as resolved by action id.")
    review.add_argument("--run-id", help="Optional review run id override for --resolve-action.")
    review.add_argument("--sync-feishu", action="store_true", help="Sync the review bundle into the review Feishu base.")
    review.add_argument("--link", help="Optional review Feishu wiki/base link override.")
    review.add_argument("--bridge-script", help="Optional bridge script path override.")
    review.set_defaults(func=command_review_skills)

    scout = subparsers.add_parser("skill-scout", help="[experimental] Scan fixed external skill seeds and produce a deduped daily shortlist.")
    scout.add_argument("--daily", action="store_true", help="Run the daily scout flow.")
    scout.add_argument("--channels", nargs="*", help="Subset of channels to scan. Defaults to github x xiaohongshu bilibili.")
    scout.add_argument("--sync-feishu", action="store_true", help="Generate scout mirror status and payload.")
    scout.set_defaults(func=command_skill_scout)

    governance_review = subparsers.add_parser(
        "review-governance",
        help="[core] Review governance honesty and maturity across skills, workflows, agents, and components.",
    )
    governance_mode = governance_review.add_mutually_exclusive_group(required=True)
    governance_mode.add_argument("--daily", action="store_true", help="Run the daily governance review flow.")
    governance_mode.add_argument("--backfill", action="store_true", help="Backfill governance ledgers from historical artifacts.")
    governance_mode.add_argument("--resolve-action", help="Mark the latest governance review or the provided run id as resolved by action id.")
    governance_review.add_argument("--run-id", help="Optional governance review run id override for --resolve-action.")
    governance_review.add_argument("--sync-feishu", action="store_true", help="Sync the governance review bundle into the governance Feishu base.")
    governance_review.add_argument("--link", help="Optional governance Feishu wiki/base link override.")
    governance_review.add_argument("--bridge-script", help="Optional bridge script path override.")
    governance_review.set_defaults(func=command_review_governance)

    strategy = subparsers.add_parser(
        "strategy-governor",
        help="[core] Generate the strategic operating-system artifacts: goals, initiatives, threads, gaps, scorecards, and governance dashboard.",
    )
    strategy.add_argument("--goal", action="append", help="Override one strategic goal title. Repeatable; first three are used.")
    strategy.set_defaults(func=command_strategy_governor)

    capability = subparsers.add_parser(
        "capability-baseline",
        help="[ops] Verify the local AI copilot baseline: files, scripts, AppleScript, browser automation, GUI surface, and external sync readiness.",
    )
    capability.add_argument("--run-id", help="Optional run id override.")
    capability.add_argument("--created-at", help="Optional ISO datetime override.")
    capability.add_argument("--browser-url", default="https://example.com", help="Public URL used for the browser smoke test.")
    capability.add_argument("--skip-browser", action="store_true", help="Skip the browser smoke test.")
    capability.add_argument("--skip-gui", action="store_true", help="Skip Finder/System Events and screenshot smoke tests.")
    capability.set_defaults(func=command_capability_baseline)

    record = subparsers.add_parser("record-evolution", help="[ops] Write the canonical evolution record from JSON input.")
    record.add_argument("--input", required=True, help="JSON file path or - for stdin.")
    record.set_defaults(func=command_record_evolution)

    sync = subparsers.add_parser("sync-feishu", help="[ops] Mirror a completed local run into Feishu via the bridge skill.")
    mode = sync.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Generate or preview the Feishu sync without applying changes.")
    mode.add_argument("--apply", action="store_true", help="Apply the Feishu sync after authorization.")
    sync.add_argument("--run-id", required=True, help="Run id to mirror.")
    sync.add_argument("--link", help="Optional Feishu wiki/base link override.")
    sync.add_argument("--primary-field", help="Optional primary field override.")
    sync.add_argument("--bridge-script", help="Optional bridge script path override.")
    sync.set_defaults(func=command_sync_feishu)

    github_sync = subparsers.add_parser("sync-github", help="[ops] Mirror a completed local run into GitHub issue/project surfaces.")
    github_mode = github_sync.add_mutually_exclusive_group(required=True)
    github_mode.add_argument("--dry-run", action="store_true", help="Preview the GitHub sync without applying changes.")
    github_mode.add_argument("--apply", action="store_true", help="Apply the GitHub sync.")
    github_sync.add_argument("--run-id", required=True, help="Run id to mirror.")
    github_sync.add_argument("--phase", choices=["intake", "closure"], required=True, help="Sync phase to execute.")
    github_sync.add_argument("--repo", help="Optional GitHub ops repo override in owner/name format.")
    github_sync.set_defaults(func=command_sync_github)

    close_task = subparsers.add_parser(
        "close-task",
        help="[core] Run the mandatory closure loop: recap, Feishu dry-run/apply, and evolution writeback.",
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
