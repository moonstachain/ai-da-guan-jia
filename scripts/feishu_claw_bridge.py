#!/usr/bin/env python3
"""AutoClaw / Feishu frontdesk bridge for AI大管家.

This bridge keeps AutoClaw as the default frontend surface, preserves
Feishu as an optional collaboration adapter, and reuses the local
AI大管家 routing logic as the backend orchestration layer.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import hmac
import importlib.util
import io
import json
import os
import re
import sys
import time
from datetime import datetime
from dataclasses import dataclass, field, replace
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

try:
    import lark_oapi as lark
except ImportError:  # pragma: no cover - optional runtime dependency
    lark = None


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from finance_adapter import FinanceAdapter  # noqa: E402

AI_DA_GUAN_JIA_SCRIPT = PROJECT_ROOT / "work" / "ai-da-guan-jia" / "scripts" / "ai_da_guan_jia.py"
DISTRIBUTION_ROOT = PROJECT_ROOT / "distribution" / "ai-da-guan-jia-openclaw"
DISTRIBUTION_CAPABILITIES_PATH = DISTRIBUTION_ROOT / "capabilities.json"
DISTRIBUTION_CREDENTIALS_PATH = DISTRIBUTION_ROOT / "credentials.example.json"
DISTRIBUTION_INSTALL_PROMPT_TEMPLATE = DISTRIBUTION_ROOT / "install-prompt.template.txt"
FINANCE_DEMO_DATA_PATH = DISTRIBUTION_ROOT / "finance-demo-data.json"
FRONTEND_GUIDE_PATH = PROJECT_ROOT / "docs" / "ai-da-guan-jia-openclaw-package.md"
USER_AGENT = "ai-da-guan-jia-feishu-bridge/0.1"
FRONTDESK_STATE_ROOT = PROJECT_ROOT / "derived" / "feishu" / "frontdesk-state"
SESSION_STORE_PATH = FRONTDESK_STATE_ROOT / "sessions.json"
IDEMPOTENCY_STORE_PATH = FRONTDESK_STATE_ROOT / "idempotency-events.json"
FRONTDESK_CAPTURE_ROOT = FRONTDESK_STATE_ROOT / "captures"
CANONICAL_CAPTURE_DIRNAME = "frontdesk-captures"
NON_CLOSURE_VERIFICATION_STATUSES = {
    "",
    "home",
    "missing_context",
    "missing_run",
    "route_only",
    "route_planned",
    "planned",
    "judged_not_executed",
    "human_boundary",
    "bundle_processed",
    "canonical_tasks_read",
    "canonical_focus_read",
    "captured",
    "captured_canonical",
}
HOME_ENTRIES = [
    {"name": "给我接个任务", "scene": "task_intake", "wave": "P0", "prompt": "帮我把这件事理清并排个推进顺序"},
    {"name": "继续昨天那个", "scene": "resume_context", "wave": "P0", "prompt": "继续昨天那个"},
    {"name": "看我的任务", "scene": "my_tasks", "wave": "P0", "prompt": "我现在有哪些任务"},
    {"name": "今天最该看什么", "scene": "today_focus", "wave": "P0", "prompt": "今天最该看什么"},
    {"name": "问 小猫 在推什么", "scene": "project_heartbeat", "wave": "P0", "prompt": "小猫现在在推什么"},
    {"name": "帮我做判断", "scene": "judgment", "wave": "P0", "prompt": "这件事该不该做"},
    {"name": "记一下", "scene": "note_capture", "wave": "P0", "prompt": "原力原力 记一下 明天要确认 Minutes 凭证"},
    {"name": "帮我查资料", "scene": "knowledge_lookup", "wave": "P0", "prompt": "我该先问飞书知识库、Get笔记，还是直接做 Deep Research"},
    {"name": "帮我收个口", "scene": "close_loop", "wave": "P0", "prompt": "把这事闭环"},
    {"name": "交给 PC 深工", "scene": "handoff_to_pc", "wave": "P0", "prompt": "这件事交给 PC 继续"},
    {"name": "查金融资讯", "scene": "finance_news_search", "wave": "P1", "prompt": "今天半导体板块有什么消息"},
    {"name": "查金融数据", "scene": "finance_data_query", "wave": "P1", "prompt": "查下平安银行 PE、PB 和收盘价"},
    {"name": "智能选股", "scene": "stock_screen", "wave": "P1", "prompt": "按 PE < 20、近20日涨幅 > 10%、所属行业 = 半导体 选股"},
]
WAKE_WORDS = ["原力原力"]
HOME_KEYWORDS = ["首页", "菜单", "帮助", "help", "能做什么", "可以做什么", "入口", "home", "start"]
TODAY_FOCUS_KEYWORDS = ["今天最该看什么", "今天该看什么", "今日重点", "daily focus", "morning review", "治理巡检"]
RESUME_KEYWORDS = ["继续昨天那个", "继续上次", "接着上次", "继续这个", "上次那个", "昨天那个", "现在卡哪了", "卡在哪了", "resume", "pick up where we left off"]
MY_TASKS_KEYWORDS = ["我的任务", "我现在有哪些任务", "我的 run", "我的run", "活跃任务", "有哪些阻塞", "待我拍板", "任务列表", "my tasks", "my runs"]
PROJECT_HEARTBEAT_KEYWORDS = [
    "小猫现在在推什么",
    "小猫在推什么",
    "小猫现在卡哪了",
    "小猫现在卡哪",
    "小猫这一小时你催了谁",
    "小猫这一小时催了谁",
    "p猫现在在推什么",
    "p猫在推什么",
    "p猫现在卡哪了",
    "p猫现在卡哪",
    "p猫这一小时你催了谁",
    "p猫这一小时催了谁",
    "项目现在卡哪了",
    "项目现在卡哪",
    "这一小时你催了谁",
    "这一小时催了谁",
    "小时推进简报",
    "现在总推进在推什么",
]
HANDOFF_TO_PC_KEYWORDS = ["交给pc", "交给 pc", "切到pc", "切到 pc", "回pc", "回 pc", "电脑上继续", "回电脑", "pc继续", "handoff to pc"]
CLOSE_LOOP_KEYWORDS = ["闭环", "收口", "收尾", "结案", "复盘", "close task", "close it"]
APPROVAL_KEYWORDS = ["审批", "批准", "批不批", "要不要发", "要不要发布", "要不要删", "要不要授权", "要不要付款", "你建议我选哪个", "该选哪个"]
KNOWLEDGE_KEYWORDS = ["查资料", "查飞书知识库", "ask.feishu", "aily", "get笔记", "得到笔记", "逐字稿", "召回", "找那条笔记", "知识库"]
JUDGMENT_KEYWORDS = ["该不该", "先做哪条", "优先级", "值不值得", "怎么判断", "怎么取舍", "风险", "判断一下"]
LIGHT_KNOWLEDGE_PREFIXES = ["搜一下", "查一下", "问一下", "找一下", "搜搜", "查查", "问问", "找找"]
NOTE_CAPTURE_PREFIXES = ["记一下", "记下", "记住", "记个", "记一条", "帮我记一下", "帮我记住"]
FINANCE_NEWS_KEYWORDS = ["新闻", "资讯", "消息", "headline", "快讯", "研报摘要"]
FINANCE_DATA_KEYWORDS = ["行情", "财务", "估值", "市盈率", "pe", "市净率", "pb", "净值", "收盘价", "trade date", "财报"]
FINANCE_SCREEN_KEYWORDS = ["选股", "筛股", "筛选", "规则选股", "stock screener"]
FINANCE_CONTEXT_KEYWORDS = [
    "股票",
    "a股",
    "港股",
    "基金",
    "指数",
    "etf",
    "板块",
    "行业",
    "证券",
    "平安银行",
    "中芯国际",
    "半导体",
    "银行",
]
FRONTDESK_COLLOQUIAL_PREFIXES = [
    "你帮我",
    "你给我",
    "帮我",
    "给我",
    "那个",
    "这个",
    "诶",
    "哎",
    "欸",
    "嗯",
    "额",
    "呃",
    "你",
]
RESUME_SEMANTIC_VERBS = ["能看到", "看到", "还记得", "记得", "找到", "接上", "续上", "恢复"]
RESUME_SEMANTIC_REFERENCES = ["上一个", "上个", "上次", "刚才", "刚刚", "昨天", "之前", "那个"]
RESUME_SEMANTIC_OBJECTS = ["任务", "那个", "事情", "项目", "run", "上下文"]
DEFAULT_AUTONOMY_BOUNDARY_HINT = "default to high autonomy"
TASK_COPILOT_REPLY_OPTIONS = "如果我理解对了，你可以回：继续推进；如果你想改目标，就把新目标再说一句；如果要切深工，就说：这件事交给 PC 继续。"
BUNDLABLE_FRONTDESK_SCENES = {
    "home",
    "resume_context",
    "my_tasks",
    "today_focus",
    "project_heartbeat",
    "judgment",
    "note_capture",
    "knowledge_lookup",
    "close_loop",
    "handoff_to_pc",
    "approval",
    "finance_news_search",
    "finance_data_query",
    "stock_screen",
}
ACTIVE_TASK_STATUSES = {"active", "planned", "in_progress", "ready", "ready_for_close"}
BLOCKED_TASK_STATUSES = {"blocked", "blocked_needs_user", "blocked_system", "failed_partial"}
WAITING_HUMAN_STATES = {"needs_input", "needs_approval", "waiting_human", "required", "pending"}
INSTALL_GUIDE_URLS = {
    "feishu": "https://open.feishu.cn/",
    "get_biji": "https://www.biji.com/openapi",
}


@dataclass
class FrontdeskReply:
    scene: str
    title: str
    sections: list[tuple[str, str]]
    run_id: str = ""
    session_id: str = ""
    status: str = "ok"
    summary: str = ""
    next_step: str = ""
    human_boundary: str = ""
    verification_status: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    footer: list[str] = field(default_factory=list)

    def as_text(self) -> str:
        lines = [self.title]
        for heading, content in self.sections:
            lines.append("")
            lines.append(f"{heading}：{content}")
        for item in self.footer:
            if item:
                lines.append("")
                lines.append(item)
        return "\n".join(lines)

    def as_card(self) -> dict[str, Any]:
        elements = [{"tag": "markdown", "content": f"**{heading}**\n{content}"} for heading, content in self.sections]
        for item in self.footer:
            if item:
                elements.append({"tag": "markdown", "content": item})
        return {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": self.title}},
            "elements": elements,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene": self.scene,
            "title": self.title,
            "text": self.as_text(),
            "card": self.as_card(),
            "run_id": self.run_id,
            "session_id": self.session_id,
            "status": self.status,
            "summary": self.summary,
            "next_step": self.next_step,
            "human_boundary": self.human_boundary,
            "verification_status": self.verification_status,
            "metadata": self.metadata,
        }


@dataclass
class FrontdeskSessionState:
    session_id: str = ""
    chat_id: str = ""
    tenant_key: str = ""
    user_open_id: str = ""
    scene: str = ""
    last_scene: str = ""
    task_text: str = ""
    last_user_goal: str = ""
    run_id: str = ""
    active_run_id: str = ""
    active_thread_id: str = ""
    active_task_ids: list[str] = field(default_factory=list)
    requested_frontdesk_state: str = ""
    last_card_message_id: str = ""
    produced_evidence: bool = False
    verification_evidence: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    effective_patterns: list[str] = field(default_factory=list)
    wasted_patterns: list[str] = field(default_factory=list)
    evolution_candidates: list[str] = field(default_factory=list)
    human_boundary: str = ""
    pending_human_boundary: str = ""
    max_distortion: str = ""
    last_verification_status: str = ""
    runtime_owner: str = ""
    owner_heartbeat_at: str = ""
    last_event_source: str = ""
    last_event_id: str = ""
    last_user_message_id: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "chat_id": self.chat_id,
            "tenant_key": self.tenant_key,
            "user_open_id": self.user_open_id,
            "scene": self.scene,
            "last_scene": self.last_scene or self.scene,
            "task_text": self.task_text,
            "last_user_goal": self.last_user_goal or self.task_text,
            "run_id": self.run_id,
            "active_run_id": self.active_run_id or self.run_id,
            "active_thread_id": self.active_thread_id,
            "active_task_ids": self.active_task_ids,
            "requested_frontdesk_state": self.requested_frontdesk_state,
            "last_card_message_id": self.last_card_message_id,
            "produced_evidence": self.produced_evidence,
            "verification_evidence": self.verification_evidence,
            "open_questions": self.open_questions,
            "effective_patterns": self.effective_patterns,
            "wasted_patterns": self.wasted_patterns,
            "evolution_candidates": self.evolution_candidates,
            "human_boundary": self.human_boundary,
            "pending_human_boundary": self.pending_human_boundary or self.human_boundary,
            "max_distortion": self.max_distortion,
            "last_verification_status": self.last_verification_status,
            "runtime_owner": self.runtime_owner,
            "owner_heartbeat_at": self.owner_heartbeat_at,
            "last_event_source": self.last_event_source,
            "last_event_id": self.last_event_id,
            "last_user_message_id": self.last_user_message_id,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "FrontdeskSessionState":
        data = payload or {}
        return cls(
            session_id=str(data.get("session_id", "")).strip(),
            chat_id=str(data.get("chat_id", "")).strip(),
            tenant_key=str(data.get("tenant_key", "")).strip(),
            user_open_id=str(data.get("user_open_id", "")).strip(),
            scene=str(data.get("scene", "")).strip(),
            last_scene=str(data.get("last_scene", "")).strip(),
            task_text=str(data.get("task_text", "")).strip(),
            last_user_goal=str(data.get("last_user_goal", "")).strip(),
            run_id=str(data.get("run_id", "")).strip(),
            active_run_id=str(data.get("active_run_id", "")).strip(),
            active_thread_id=str(data.get("active_thread_id", "")).strip(),
            active_task_ids=[str(item) for item in data.get("active_task_ids", [])],
            requested_frontdesk_state=str(data.get("requested_frontdesk_state", "")).strip(),
            last_card_message_id=str(data.get("last_card_message_id", "")).strip(),
            produced_evidence=bool(data.get("produced_evidence", False)),
            verification_evidence=[str(item) for item in data.get("verification_evidence", [])],
            open_questions=[str(item) for item in data.get("open_questions", [])],
            effective_patterns=[str(item) for item in data.get("effective_patterns", [])],
            wasted_patterns=[str(item) for item in data.get("wasted_patterns", [])],
            evolution_candidates=[str(item) for item in data.get("evolution_candidates", [])],
            human_boundary=str(data.get("human_boundary", "")).strip(),
            pending_human_boundary=str(data.get("pending_human_boundary", "")).strip(),
            max_distortion=str(data.get("max_distortion", "")).strip(),
            last_verification_status=str(data.get("last_verification_status", "")).strip(),
            runtime_owner=str(data.get("runtime_owner", "")).strip(),
            owner_heartbeat_at=str(data.get("owner_heartbeat_at", "")).strip(),
            last_event_source=str(data.get("last_event_source", "")).strip(),
            last_event_id=str(data.get("last_event_id", "")).strip(),
            last_user_message_id=str(data.get("last_user_message_id", "")).strip(),
            updated_at=str(data.get("updated_at", "")).strip(),
        )


def normalize_text(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def text_has_any(text: str, phrases: list[str]) -> bool:
    return any(phrase.lower() in text for phrase in phrases)


def shorten(text: str, limit: int = 140) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def build_footer(run_id: str = "", extra: list[str] | None = None) -> list[str]:
    footer: list[str] = []
    if run_id:
        footer.append(f"run id: {run_id}")
    if extra:
        footer.extend([item for item in extra if item])
    return footer


def strip_frontdesk_line_prefix(text: str) -> str:
    value = str(text or "").strip()
    return re.sub(r"^\s*(?:[-*•]+|\d+[\.\、\)\-]*)\s*", "", value).strip()


def strip_wake_prefix(text: str) -> tuple[str, bool]:
    value = str(text or "").strip()
    for wake_word in WAKE_WORDS:
        if not value.startswith(wake_word):
            continue
        remainder = value[len(wake_word):]
        if remainder and remainder[0] not in {" ", "\t", ",", "，", ":", "：", ";", "；", "!", "！", "?", "？", "-", "—"}:
            continue
        return remainder.lstrip(" \t,，:：;；!！?？-—"), True
    return value, False


def strip_colloquial_prefix(text: str) -> str:
    value = str(text or "").strip()
    while value:
        value = value.lstrip(" \t,，:：;；!！?？-—")
        changed = False
        for phrase in sorted(FRONTDESK_COLLOQUIAL_PREFIXES, key=len, reverse=True):
            if not value.startswith(phrase):
                continue
            value = value[len(phrase) :].lstrip(" \t,，:：;；!！?？-—")
            changed = True
            break
        if not changed:
            break
    return value


def normalize_frontdesk_line(text: str) -> tuple[str, bool]:
    stripped = strip_frontdesk_line_prefix(text)
    stripped = strip_colloquial_prefix(stripped)
    stripped, wake_used = strip_wake_prefix(stripped)
    stripped = strip_colloquial_prefix(stripped)
    return stripped, wake_used


def startswith_any(text: str, phrases: list[str]) -> bool:
    normalized = normalize_text(text)
    return any(normalized.startswith(normalize_text(phrase)) for phrase in phrases)


def strip_note_capture_prefix(text: str) -> str:
    value = str(text or "").strip()
    for phrase in sorted(NOTE_CAPTURE_PREFIXES, key=len, reverse=True):
        if value.startswith(phrase):
            return value[len(phrase):].lstrip(" \t,，:：;；!！?？-—")
    return value


def strip_light_knowledge_prefix(text: str) -> str:
    value = str(text or "").strip()
    for phrase in sorted(LIGHT_KNOWLEDGE_PREFIXES, key=len, reverse=True):
        if value.startswith(phrase):
            return value[len(phrase):].lstrip(" \t,，:：;；!！?？-—")
    return value


def looks_like_lightweight_knowledge_query(text: str) -> bool:
    return startswith_any(text, LIGHT_KNOWLEDGE_PREFIXES)


def _looks_like_finance_context(text: str) -> bool:
    normalized = normalize_text(text)
    if re.search(r"\b\d{6}\.(?:sz|sh|bj|of)\b", normalized, flags=re.IGNORECASE):
        return True
    if re.search(r"\b\d{6}\b", normalized):
        return True
    return text_has_any(normalized, FINANCE_CONTEXT_KEYWORDS) or text_has_any(normalized, FINANCE_DATA_KEYWORDS)


def looks_like_finance_news_query(text: str) -> bool:
    normalized = normalize_text(text)
    return _looks_like_finance_context(text) and text_has_any(normalized, FINANCE_NEWS_KEYWORDS)


def looks_like_finance_data_query(text: str) -> bool:
    normalized = normalize_text(text)
    return _looks_like_finance_context(text) and text_has_any(normalized, FINANCE_DATA_KEYWORDS)


def looks_like_stock_screen_query(text: str) -> bool:
    normalized = normalize_text(text)
    if text_has_any(normalized, FINANCE_SCREEN_KEYWORDS):
        return True
    if _looks_like_finance_context(text) and any(keyword in normalized for keyword in ["pe ", "pe<", "pe>", "市盈率", "市净率", "营收同比", "20日涨幅", "近20日"]):
        return True
    return False


def looks_like_resume_context_query(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return False
    if text_has_any(normalized, RESUME_KEYWORDS):
        return True
    has_verb = any(normalize_text(phrase) in normalized for phrase in RESUME_SEMANTIC_VERBS)
    has_reference = any(normalize_text(phrase) in normalized for phrase in RESUME_SEMANTIC_REFERENCES)
    has_object = any(normalize_text(phrase) in normalized for phrase in RESUME_SEMANTIC_OBJECTS)
    return has_verb and has_reference and has_object


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def build_session_id(user_context: dict[str, Any] | None = None) -> str:
    data = user_context or {}
    tenant_key = str(data.get("tenant_key", "")).strip() or "no-tenant"
    user_open_id = str(data.get("open_id") or data.get("user_open_id") or "").strip() or "no-user"
    chat_id = str(data.get("chat_id", "")).strip() or "no-chat"
    return "::".join([tenant_key, user_open_id, chat_id])


def classify_frontdesk_scene(text: str, signals: dict[str, bool], *, wake_used: bool = False) -> str:
    normalized = normalize_text(text)
    if not normalized or text_has_any(normalized, HOME_KEYWORDS):
        return "home"
    if wake_used and startswith_any(text, NOTE_CAPTURE_PREFIXES):
        return "note_capture"
    if text_has_any(normalized, TODAY_FOCUS_KEYWORDS):
        return "today_focus"
    if text_has_any(normalized, MY_TASKS_KEYWORDS):
        return "my_tasks"
    if normalized == "p猫" or text_has_any(normalized, PROJECT_HEARTBEAT_KEYWORDS):
        return "project_heartbeat"
    if looks_like_resume_context_query(text):
        return "resume_context"
    if text_has_any(normalized, CLOSE_LOOP_KEYWORDS):
        return "close_loop"
    if text_has_any(normalized, HANDOFF_TO_PC_KEYWORDS):
        return "handoff_to_pc"
    if signals.get("hard_boundary") or text_has_any(normalized, APPROVAL_KEYWORDS):
        return "approval"
    if looks_like_stock_screen_query(text):
        return "stock_screen"
    if looks_like_finance_data_query(text):
        return "finance_data_query"
    if looks_like_finance_news_query(text):
        return "finance_news_search"
    if looks_like_lightweight_knowledge_query(text):
        return "knowledge_lookup"
    if signals.get("get_biji") or signals.get("feishu_km") or signals.get("knowledge_first") or text_has_any(normalized, KNOWLEDGE_KEYWORDS):
        return "knowledge_lookup"
    if text_has_any(normalized, JUDGMENT_KEYWORDS):
        return "judgment"
    return "task_intake"


class FrontdeskSessionStore:
    def __init__(self, path: Path | None = None):
        self.path = Path(path or SESSION_STORE_PATH)
        self._sessions: dict[str, FrontdeskSessionState] = {}
        self._loaded = False

    def get(self, session_id: str) -> FrontdeskSessionState | None:
        self._ensure_loaded()
        if not session_id:
            return None
        state = self._sessions.get(session_id)
        if state is None:
            return None
        return FrontdeskSessionState.from_dict(state.to_dict())

    def upsert(self, state: FrontdeskSessionState) -> None:
        self._ensure_loaded()
        if not state.session_id:
            return
        self._sessions[state.session_id] = FrontdeskSessionState.from_dict(state.to_dict())
        self._save()

    def all_sessions(self) -> list[FrontdeskSessionState]:
        self._ensure_loaded()
        return [FrontdeskSessionState.from_dict(state.to_dict()) for state in self._sessions.values()]

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self.path.exists():
            return
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        sessions = payload.get("sessions", payload) if isinstance(payload, dict) else {}
        if not isinstance(sessions, dict):
            return
        for session_id, value in sessions.items():
            state = FrontdeskSessionState.from_dict(value if isinstance(value, dict) else {})
            if not state.session_id:
                state.session_id = str(session_id).strip()
            self._sessions[state.session_id] = state

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"sessions": {session_id: state.to_dict() for session_id, state in self._sessions.items()}}
        temp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self.path)


def load_ai_da_guan_jia_module():
    script_dir = str(AI_DA_GUAN_JIA_SCRIPT.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    spec = importlib.util.spec_from_file_location("feishu_bridge_ai_da_guan_jia", AI_DA_GUAN_JIA_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load AI大管家 script from {AI_DA_GUAN_JIA_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def json_dumps(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def to_builtin_payload(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): to_builtin_payload(item) for key, item in value.items() if item is not None}
    if isinstance(value, (list, tuple, set)):
        return [to_builtin_payload(item) for item in value]
    if hasattr(value, "__dict__"):
        data = {
            str(key): to_builtin_payload(item)
            for key, item in vars(value).items()
            if not str(key).startswith("_") and item is not None
        }
        return data
    return str(value)


def coerce_longconn_event_payload(event: Any, *, default_event_type: str = "im.message.receive_v1") -> dict[str, Any]:
    payload = to_builtin_payload(event)
    if not isinstance(payload, dict):
        raise TypeError(f"Expected long connection event payload to be a dict, got {type(payload)!r}")
    header = payload.get("header")
    if not isinstance(header, dict):
        header = {}
        payload["header"] = header
    header.setdefault("event_type", default_event_type)
    return payload


def load_distribution_metadata() -> dict[str, Any]:
    if DISTRIBUTION_CAPABILITIES_PATH.exists():
        return json.loads(DISTRIBUTION_CAPABILITIES_PATH.read_text(encoding="utf-8"))
    return {
        "bundle_id": "ai-da-guan-jia-openclaw",
        "display_name": "原力OS",
        "short_description": "AutoClaw 自用版前台总控 Skill：接任务、做判断、选知识源、准备收口",
        "frontdesk_scenes": [],
        "tool_contracts": [],
        "credential_guides": [],
    }


def load_distribution_credentials() -> dict[str, Any]:
    if DISTRIBUTION_CREDENTIALS_PATH.exists():
        return json.loads(DISTRIBUTION_CREDENTIALS_PATH.read_text(encoding="utf-8"))
    return {"required": {}, "optional": {}, "readiness_states": []}


def resolve_bundle_source() -> str:
    return os.getenv("AI_DA_GUAN_JIA_OPENCLAW_SOURCE", str(DISTRIBUTION_ROOT)).strip() or str(DISTRIBUTION_ROOT)


def render_install_prompt() -> str:
    template = DISTRIBUTION_INSTALL_PROMPT_TEMPLATE.read_text(encoding="utf-8")
    replacements = {
        "{{skill_source}}": resolve_bundle_source(),
        "{{capabilities_path}}": str(DISTRIBUTION_CAPABILITIES_PATH),
        "{{frontend_guide}}": str(FRONTEND_GUIDE_PATH),
        "{{feishu_guide_url}}": INSTALL_GUIDE_URLS["feishu"],
        "{{get_biji_guide_url}}": INSTALL_GUIDE_URLS["get_biji"],
    }
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)
    return rendered


def env_present(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def inspect_installation_state(*, auth_client: "FeishuAuthClient" | None = None, verify_runtime: bool = False) -> dict[str, Any]:
    metadata = load_distribution_metadata()
    bundle_exists = DISTRIBUTION_ROOT.exists()
    feishu_configured = env_present("FEISHU_APP_ID") and env_present("FEISHU_APP_SECRET")
    get_biji_configured = env_present("GET_BIJI_API_KEY") and env_present("GET_BIJI_TOPIC_ID")
    feishu_verified = False
    verification_error = ""

    if verify_runtime and feishu_configured and auth_client is not None:
        try:
            auth_client.get_tenant_access_token()
            feishu_verified = True
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            verification_error = str(exc)

    overall_status = "未安装"
    user_ready_summary = "当前还没有可用的 原力OS 前台壳。"
    if bundle_exists:
        overall_status = "已安装"
        user_ready_summary = "原力OS 前台壳已经装好，可以直接拿来接任务、续上下文和看状态。"
    if bundle_exists and feishu_configured:
        overall_status = "需要我补后台配置"
        user_ready_summary = "协作连接已补到一半，但还没完成运行验真。"
    if bundle_exists and feishu_verified:
        overall_status = "可直接用"
        user_ready_summary = "核心前台路径和飞书协作连接都已验真，可以直接使用。"

    return {
        "bundle_id": metadata.get("bundle_id", "ai-da-guan-jia-openclaw"),
        "install_source": resolve_bundle_source(),
        "overall_status": overall_status,
        "user_ready_summary": user_ready_summary,
        "components": [
            {
                "id": "bundle",
                "label": "原力OS 前台壳",
                "required": True,
                "status": "present" if bundle_exists else "missing",
                "details": "装好后即可在移动端接任务、续上下文、看状态、准备收口。",
            },
            {
                "id": "feishu_bot",
                "label": "飞书协作连接",
                "required": False,
                "status": "verified" if feishu_verified else ("configured" if feishu_configured else "missing"),
                "details": "只有想把前台对话接到飞书协作面时，才需要我补后台配置。",
            },
            {
                "id": "get_biji_api",
                "label": "Get笔记连接",
                "required": False,
                "status": "configured" if get_biji_configured else "missing",
                "details": "只有想让它直接走 Get笔记 读路径时，才需要我补后台配置。",
            },
        ],
        "verification_error": verification_error,
        "readiness_states": load_distribution_credentials().get("readiness_states", []),
    }


@dataclass
class BridgeConfig:
    app_id: str
    app_secret: str
    verification_token: str = ""
    signing_secret: str = ""
    base_url: str = "https://open.feishu.cn"
    execution_mode: str = "route_only"
    route_persist: bool = True
    send_cards: bool = False
    instance_tag: str = ""
    request_timeout_seconds: int = 15
    max_request_age_seconds: int = 60 * 10

    @classmethod
    def from_env(cls) -> "BridgeConfig":
        app_id = os.getenv("FEISHU_APP_ID", "").strip()
        app_secret = os.getenv("FEISHU_APP_SECRET", "").strip()
        if not app_id or not app_secret:
            raise ValueError("FEISHU_APP_ID and FEISHU_APP_SECRET are required.")
        return cls(
            app_id=app_id,
            app_secret=app_secret,
            verification_token=os.getenv("FEISHU_EVENT_VERIFICATION_TOKEN", "").strip(),
            signing_secret=os.getenv("FEISHU_EVENT_SIGNING_SECRET", "").strip(),
            base_url=os.getenv("FEISHU_BASE_URL", "https://open.feishu.cn").rstrip("/"),
            execution_mode=os.getenv("AI_DA_GUAN_JIA_FEISHU_EXECUTION_MODE", "route_only").strip() or "route_only",
            route_persist=os.getenv("AI_DA_GUAN_JIA_FEISHU_ROUTE_PERSIST", "true").lower() != "false",
            send_cards=os.getenv("AI_DA_GUAN_JIA_FEISHU_SEND_CARDS", "false").lower() == "true",
            instance_tag=os.getenv("AI_DA_GUAN_JIA_FEISHU_INSTANCE_TAG", "").strip(),
            request_timeout_seconds=int(os.getenv("FEISHU_REQUEST_TIMEOUT_SECONDS", "15")),
            max_request_age_seconds=int(os.getenv("FEISHU_EVENT_MAX_AGE_SECONDS", str(60 * 10))),
        )

    @property
    def allows_p0_execution(self) -> bool:
        return self.execution_mode in {"p0_assist", "p1_assist"}

    @property
    def allows_p1_execution(self) -> bool:
        return self.execution_mode == "p1_assist"


class FeishuAuthClient:
    def __init__(self, config: BridgeConfig):
        self.config = config
        self._token: str | None = None
        self._expires_at: float = 0.0

    def get_tenant_access_token(self) -> str:
        now = time.time()
        if self._token and now < self._expires_at:
            return self._token

        url = f"{self.config.base_url}/open-apis/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self.config.app_id,
            "app_secret": self.config.app_secret,
        }
        response = self._request_json(url, payload, authorized=False, method="POST")
        if response.get("code") != 0:
            raise RuntimeError(f"Failed to get tenant_access_token: {response}")
        token = str(response["tenant_access_token"])
        expire = int(response.get("expire", 0) or 0)
        self._token = token
        self._expires_at = now + max(expire - 60, 60)
        return token

    def post_openapi(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.config.base_url}{path}"
        return self._request_json(url, payload, authorized=True, method="POST")

    def patch_openapi(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.config.base_url}{path}"
        return self._request_json(url, payload, authorized=True, method="PATCH")

    def _request_json(self, url: str, payload: dict[str, Any], *, authorized: bool, method: str) -> dict[str, Any]:
        data = json_dumps(payload)
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": USER_AGENT,
        }
        if authorized:
            headers["Authorization"] = f"Bearer {self.get_tenant_access_token()}"
        request = urllib_request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib_request.urlopen(request, timeout=self.config.request_timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib_error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Feishu API error {exc.code}: {detail}") from exc


class FeishuMessenger:
    def __init__(self, auth_client: FeishuAuthClient):
        self.auth_client = auth_client

    def send_text_to_chat(self, chat_id: str, text: str) -> dict[str, Any]:
        payload = {
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        }
        return self.auth_client.post_openapi("/open-apis/im/v1/messages?receive_id_type=chat_id", payload)

    def send_card_to_chat(self, chat_id: str, card: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "receive_id": chat_id,
            "msg_type": "interactive",
            "content": json.dumps(card, ensure_ascii=False),
        }
        return self.auth_client.post_openapi("/open-apis/im/v1/messages?receive_id_type=chat_id", payload)

    def update_card(self, message_id: str, card: dict[str, Any]) -> dict[str, Any]:
        return self.auth_client.patch_openapi(
            f"/open-apis/im/v1/messages/{message_id}",
            {"content": json.dumps(card, ensure_ascii=False)},
        )


class FeishuEventVerifier:
    def __init__(self, config: BridgeConfig):
        self.config = config

    def verify(self, payload: dict[str, Any], headers: dict[str, str], raw_body: bytes) -> None:
        self._verify_timestamp(headers)
        self._verify_token(payload)
        self._verify_signature(headers, raw_body)

    def _verify_timestamp(self, headers: dict[str, str]) -> None:
        timestamp = headers.get("x-lark-request-timestamp", "").strip()
        if not timestamp:
            return
        try:
            request_ts = int(timestamp)
        except ValueError as exc:
            raise PermissionError("Invalid x-lark-request-timestamp header.") from exc
        if abs(int(time.time()) - request_ts) > self.config.max_request_age_seconds:
            raise PermissionError("Feishu event request is outside the allowed age window.")

    def _verify_token(self, payload: dict[str, Any]) -> None:
        expected = self.config.verification_token
        if not expected:
            return
        actual = str(payload.get("token", "")).strip()
        if actual and actual == expected:
            return
        header = payload.get("header")
        if isinstance(header, dict) and str(header.get("token", "")).strip() == expected:
            return
        raise PermissionError("Feishu event verification token mismatch.")

    def _verify_signature(self, headers: dict[str, str], raw_body: bytes) -> None:
        secret = self.config.signing_secret
        if not secret:
            return
        timestamp = headers.get("x-lark-request-timestamp", "").strip()
        nonce = headers.get("x-lark-request-nonce", "").strip()
        actual = headers.get("x-lark-signature", "").strip()
        if not timestamp or not actual:
            raise PermissionError("Missing Feishu signature headers.")
        base = b"".join([timestamp.encode("utf-8"), nonce.encode("utf-8"), raw_body])
        expected = hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, actual):
            raise PermissionError("Feishu event signature mismatch.")


class IdempotencyStore:
    def __init__(self, ttl_seconds: int = 3600, path: Path | None = None):
        self.ttl_seconds = ttl_seconds
        self.path = Path(path or IDEMPOTENCY_STORE_PATH)
        self._events: dict[str, dict[str, Any]] = {}
        self._loaded = False

    def seen(self, event_id: str) -> bool:
        self._ensure_loaded()
        self._prune()
        return event_id in self._events

    def mark(self, event_id: str, metadata: dict[str, Any] | None = None) -> None:
        self._ensure_loaded()
        self._prune()
        now_ts = time.time()
        details = metadata.copy() if isinstance(metadata, dict) else {}
        seen_at = str(details.get("seen_at", "")).strip() or iso_now()
        heartbeat_at = str(details.get("heartbeat_at", "")).strip() or seen_at
        self._events[event_id] = {
            "timestamp": now_ts,
            "seen_at": seen_at,
            "heartbeat_at": heartbeat_at,
            "owner": str(details.get("owner", "")).strip(),
            "event_source": str(details.get("event_source", "")).strip(),
            "chat_id": str(details.get("chat_id", "")).strip(),
            "message_id": str(details.get("message_id", "")).strip(),
        }
        self._save()

    def recent_events(self, limit: int = 5) -> list[dict[str, Any]]:
        self._ensure_loaded()
        self._prune()
        ordered = sorted(
            self._events.items(),
            key=lambda item: float(item[1].get("timestamp", 0.0)),
            reverse=True,
        )
        return [
            {"event_id": event_id, **details}
            for event_id, details in ordered[: max(limit, 0)]
        ]

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self.path.exists():
            return
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        events = payload.get("events", payload) if isinstance(payload, dict) else {}
        if not isinstance(events, dict):
            return
        normalized: dict[str, dict[str, Any]] = {}
        for event_id, value in events.items():
            key = str(event_id)
            if isinstance(value, dict):
                timestamp = float(value.get("timestamp", 0.0) or 0.0)
                normalized[key] = {
                    "timestamp": timestamp,
                    "seen_at": str(value.get("seen_at", "")).strip(),
                    "heartbeat_at": str(value.get("heartbeat_at", "")).strip() or str(value.get("seen_at", "")).strip(),
                    "owner": str(value.get("owner", "")).strip(),
                    "event_source": str(value.get("event_source", "")).strip(),
                    "chat_id": str(value.get("chat_id", "")).strip(),
                    "message_id": str(value.get("message_id", "")).strip(),
                }
                continue
            normalized[key] = {
                "timestamp": float(value),
                "seen_at": "",
                "heartbeat_at": "",
                "owner": "",
                "event_source": "",
                "chat_id": "",
                "message_id": "",
            }
        self._events = normalized
        self._prune()

    def _prune(self) -> None:
        threshold = time.time() - self.ttl_seconds
        expired = [event_id for event_id, value in self._events.items() if float(value.get("timestamp", 0.0)) < threshold]
        for event_id in expired:
            self._events.pop(event_id, None)
        if expired:
            self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"events": self._events}
        temp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self.path)


class AiDaGuanJiaBackend:
    def __init__(self, *, persist_route: bool = True, capture_root: Path | None = None):
        self.module = load_ai_da_guan_jia_module()
        self.persist_route = persist_route
        default_capture_root = Path(getattr(self.module, "RUNS_ROOT", FRONTDESK_CAPTURE_ROOT))
        self.capture_root = Path(capture_root or default_capture_root)
        self._finance_adapter: FinanceAdapter | None = None

    @property
    def finance_adapter(self) -> FinanceAdapter:
        if self._finance_adapter is None:
            self._finance_adapter = FinanceAdapter(FINANCE_DEMO_DATA_PATH)
        return self._finance_adapter

    def list_frontdesk_capabilities(self) -> dict[str, Any]:
        metadata = load_distribution_metadata()
        return {
            "bundle_id": metadata.get("bundle_id", "ai-da-guan-jia-openclaw"),
            "display_name": metadata.get("display_name", "原力OS"),
            "short_description": metadata.get("short_description", ""),
            "wake_words": metadata.get("wake_words", WAKE_WORDS),
            "invocation_examples": metadata.get("invocation_examples", []),
            "frontdesk_scenes": metadata.get("frontdesk_scenes", []),
            "tool_contracts": metadata.get("tool_contracts", []),
            "credential_guides": metadata.get("credential_guides", []),
            "when_to_call": metadata.get("when_to_call", []),
            "when_not_to_call": metadata.get("when_not_to_call", []),
            "readiness_copy": metadata.get("readiness_copy", {}),
            "reply_contract": metadata.get("reply_contract", []),
        }

    def route_task(self, input_text: str, user_context: dict[str, Any] | None = None) -> dict[str, Any]:
        prompt = input_text.strip()
        if not prompt:
            raise ValueError("input_text cannot be empty")
        module = self.module
        skills = module.discover_skills()
        signals = module.detect_signals(prompt)
        mentioned = module.explicit_mentions(prompt, [item["name"] for item in skills])
        governance = module.load_governance_signals()
        ranked = [module.score_candidate(prompt, skill, signals, mentioned, governance) for skill in skills]
        ranked.sort(key=lambda item: item["total_score"], reverse=True)
        selected, omitted = module.choose_skills(prompt, ranked, signals, mentioned)
        get_biji_plan = module.plan_get_biji_actions(prompt) if signals["get_biji"] else {}
        feishu_km_plan = module.plan_feishu_km_actions(prompt, signals) if signals["feishu_km"] else {}
        situation_map = module.build_situation_map(prompt, selected, signals)
        situation_map["治理提权判断"] = (
            "Governance-weighted routing is active; routing credit only adjusts near-tie candidates."
            if governance["status"] != "missing"
            else "Governance-weighted routing is unavailable; fallback to rule-only routing."
        )
        created_at = module.iso_now()
        run_id = module.allocate_run_id(created_at)
        run_dir = module.run_dir_for(run_id, created_at)
        route_payload = {
            "run_id": run_id,
            "created_at": created_at,
            "task_text": prompt,
            "routing_order": module.ROUTING_ORDER,
            "signals": signals,
            "governance_signal_status": governance["status"],
            "credit_influenced_selection": module.credit_influenced_selection(ranked, selected),
            "skills_considered": [item["name"] for item in ranked],
            "candidate_rankings": ranked[:10],
            "selected_skills": selected,
            "proposal_authority_summary": module.selected_proposal_authority_summary(ranked, selected),
            "omitted_due_to_selection_ceiling": omitted,
            "selection_ceiling": module.selection_ceiling(signals),
            "human_boundary": module.determine_human_boundary(signals),
            "verification_targets": module.verification_targets(signals, get_biji_plan),
            "situation_map": situation_map,
            "user_context": user_context or {},
            "bridge_surface": "feishu_bot",
        }
        route_payload.update(get_biji_plan)
        route_payload.update(feishu_km_plan)
        route_payload = self._enrich_route_payload_for_frontdesk(route_payload)
        if self.persist_route:
            module.write_json(run_dir / "route.json", route_payload)
            (run_dir / "situation-map.md").write_text(
                module.render_situation_map(situation_map, prompt),
                encoding="utf-8",
            )
        route_payload["run_dir"] = str(run_dir)
        return route_payload

    def get_run_status(self, run_id: str) -> dict[str, Any]:
        normalized = run_id.strip()
        if not normalized:
            raise ValueError("run_id is required")
        candidate_roots: list[Path] = []
        module_root = Path(getattr(self.module, "ARTIFACTS_ROOT", PROJECT_ROOT / "work" / "ai-da-guan-jia" / "artifacts" / "ai-da-guan-jia"))
        candidate_roots.append(module_root)
        external_skill_root = Path.home() / ".codex" / "skills" / "ai-da-guan-jia" / "artifacts" / "ai-da-guan-jia"
        if external_skill_root not in candidate_roots:
            candidate_roots.append(external_skill_root)
        for artifacts_root in candidate_roots:
            runs_root = artifacts_root / "runs"
            if not runs_root.exists():
                continue
            for date_dir in sorted(runs_root.glob("*"), reverse=True):
                run_dir = date_dir / normalized
                if not run_dir.exists():
                    continue
                route = self._load_optional_json(run_dir / "route.json")
                worklog = self._load_optional_json(run_dir / "worklog.json")
                evolution = self._load_optional_json(run_dir / "evolution.json")
                selected_skills = route.get("selected_skills", [])
                return {
                    "status": "found",
                    "run_id": normalized,
                    "run_dir": str(run_dir),
                    "task_text": str(route.get("task_text", "")).strip(),
                    "selected_skills": selected_skills,
                    "verification_targets": route.get("verification_targets", []),
                    "close_status": str(worklog.get("status") or evolution.get("status") or "route_only"),
                    "has_worklog": bool(worklog),
                    "has_evolution": bool(evolution),
                    "human_boundary": str(route.get("human_boundary", "")).strip(),
                    "next_step": (self._next_steps_from_route(route) or [str(route.get("next_action", "")).strip()])[0],
                    "recommended_actions": route.get("recommended_actions", []),
                }
        return {"status": "missing", "run_id": normalized}

    @staticmethod
    def _load_optional_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _summarize_hits(hits: list[dict[str, Any]]) -> str:
        if not hits:
            return ""
        snippets: list[str] = []
        for hit in hits[:3]:
            title = str(hit.get("title") or hit.get("name") or "").strip()
            content = shorten(str(hit.get("content") or hit.get("summary") or "").strip(), limit=48)
            snippet = title or content
            if title and content:
                snippet = f"{title}: {content}"
            if snippet:
                snippets.append(snippet)
        return "；".join(snippets)

    @staticmethod
    def _next_steps_from_route(route: dict[str, Any]) -> list[str]:
        next_steps: list[str] = []
        for item in route.get("recommended_actions", [])[:3]:
            if isinstance(item, dict):
                command = str(item.get("cli_command", "")).strip()
                if command:
                    next_steps.append(command)
        return next_steps

    @staticmethod
    def _user_visible_human_boundary(boundary: str) -> str:
        value = str(boundary or "").strip()
        if not value or value.lower() == "none":
            return ""
        if DEFAULT_AUTONOMY_BOUNDARY_HINT in value.lower():
            return ""
        normalized = normalize_text(value)
        if any(keyword in normalized for keyword in ["审批", "批准", "授权", "发布", "删除", "付款", "拍板", "取舍"]):
            return "这一步涉及明确的人类边界，等你拍板后我再继续。"
        return "这一步已经碰到人类边界，需要你确认后我再继续。"

    @staticmethod
    def _default_frontdesk_route_summary(task_text: str) -> str:
        cleaned = str(task_text or "").strip()
        if not cleaned:
            return "我理解成一个待推进任务，先帮你定清目标、路径和第一步。"
        return f"我理解成你要推进这件事：{shorten(cleaned, limit=72)}。先帮你定清目标、路径和第一步。"

    @staticmethod
    def _normalize_frontdesk_recommended_actions(
        route_payload: dict[str, Any],
        actions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        normalized_actions: list[dict[str, Any]] = []
        for index, item in enumerate(actions, start=1):
            if not isinstance(item, dict):
                continue
            intent = str(item.get("human_next_step") or item.get("intent") or item.get("reason") or "").strip()
            if not intent:
                intent = "我先按这条路径帮你继续往下压。"
            user_reply = str(item.get("user_reply") or "").strip() or TASK_COPILOT_REPLY_OPTIONS
            normalized_actions.append(
                {
                    **item,
                    "step_index": int(item.get("step_index", index) or index),
                    "human_next_step": intent,
                    "user_reply": user_reply,
                }
            )
        if normalized_actions:
            return normalized_actions
        return [
            {
                "step_index": 1,
                "action": str(route_payload.get("primary_action") or "frontdesk.coplan"),
                "intent": "先把目标压成可推进任务，再决定第一步。",
                "human_next_step": "我先帮你把目标、路径和第一步压清，再判断是不是要切到更深的执行链。",
                "user_reply": TASK_COPILOT_REPLY_OPTIONS,
            }
        ]

    def _enrich_route_payload_for_frontdesk(self, route_payload: dict[str, Any]) -> dict[str, Any]:
        payload = dict(route_payload)
        human_summary = str(payload.get("human_route_summary") or "").strip()
        if not human_summary:
            human_summary = self._default_frontdesk_route_summary(str(payload.get("task_text", "")).strip())
        actions = self._normalize_frontdesk_recommended_actions(
            payload,
            payload.get("recommended_actions") if isinstance(payload.get("recommended_actions"), list) else [],
        )
        payload["human_route_summary"] = human_summary
        payload["recommended_actions"] = actions
        payload["primary_action"] = str(payload.get("primary_action") or actions[0].get("action") or "frontdesk.coplan")
        payload["next_action"] = str(payload.get("next_action") or actions[0].get("human_next_step") or "").strip()
        return payload

    @staticmethod
    def _capture_query_text(text: str) -> str:
        return strip_light_knowledge_prefix(str(text or "").strip()).strip()

    @staticmethod
    def _capture_search_score(query: str, content: str) -> int:
        query_norm = normalize_text(query)
        content_norm = normalize_text(content)
        if not query_norm or not content_norm:
            return 0
        if query_norm in content_norm:
            return 1000 + len(query_norm)
        terms = [term for term in query_norm.split(" ") if term]
        if not terms:
            return 0
        return sum(1 for term in terms if term in content_norm)

    def _resolve_capture_run(self, created_at: str, session: FrontdeskSessionState | None) -> tuple[str, Path, bool]:
        active_run_id = ""
        if session is not None:
            active_run_id = str(session.active_run_id or session.run_id or "").strip()
        if active_run_id:
            run_status = self.get_run_status(active_run_id)
            if run_status.get("status") == "found":
                run_dir = Path(str(run_status.get("run_dir", "")).strip())
                if run_dir:
                    return active_run_id, run_dir, False
        run_id = self.module.allocate_run_id(created_at)
        run_dir = Path(self.capture_root) / created_at[:10] / run_id
        return run_id, run_dir, True

    def _recent_capture_records(self, limit: int = 50) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []

        for path in sorted(Path(self.capture_root).glob(f"*/*/{CANONICAL_CAPTURE_DIRNAME}/*.json"), reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            record = dict(payload)
            record["artifact_path"] = str(path)
            records.append(record)
            if len(records) >= limit:
                break

        if len(records) < limit:
            for path in sorted(FRONTDESK_CAPTURE_ROOT.glob("*/*/capture.json"), reverse=True):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if not isinstance(payload, dict):
                    continue
                record = dict(payload)
                record.setdefault("run_id", "")
                record.setdefault("session_id", "")
                record.setdefault("sync_status", "legacy_local_only")
                record["artifact_path"] = str(path)
                records.append(record)
                if len(records) >= limit:
                    break

        records.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return records[:limit]

    def _lookup_local_capture(self, input_text: str) -> dict[str, Any] | None:
        query = self._capture_query_text(input_text)
        if not query:
            return None

        ranked: list[tuple[int, dict[str, Any]]] = []
        for record in self._recent_capture_records(limit=80):
            searchable = " ".join(
                [
                    str(record.get("content", "")).strip(),
                    str(record.get("summary", "")).strip(),
                    str(record.get("capture_id", "")).strip(),
                ]
            ).strip()
            score = self._capture_search_score(query, searchable)
            if score <= 0:
                continue
            ranked.append((score, record))
        if not ranked:
            return None

        ranked.sort(key=lambda item: (item[0], str(item[1].get("created_at", ""))), reverse=True)
        hits = [item[1] for item in ranked[:3]]
        top = hits[0]
        hit_lines = [
            f"{str(item.get('created_at', '')).strip() or 'unknown'}｜{shorten(str(item.get('content', '')).strip(), limit=56)}"
            for item in hits
        ]
        route = {
            "task_text": query,
            "run_id": str(top.get("run_id", "")).strip(),
            "human_boundary": "本地 canonical 只读查询，不替你写第三方知识库。",
            "situation_map": {"当前最大失真": "把本地轻记录误判成已经同步到外部知识库。"},
        }
        return {
            "status": "completed",
            "execution_mode": "canonical_local",
            "route": route,
            "source_label": "本地 canonical / 原力OS 轻记录",
            "summary": f"命中 {len(hits)} 条本地记录：{'；'.join(hit_lines)}",
            "missing": "已命中本地 canonical；尚未同步到外部知识库。",
            "produced_evidence": True,
            "verification_evidence": [str(item.get("artifact_path", "")).strip() for item in hits if str(item.get("artifact_path", "")).strip()],
            "open_questions": ["如需外部知识库答案，再明确指定飞书知识库或 Get笔记。"],
            "effective_patterns": ["先记进 canonical，再搜刚记的内容，移动端连续性会更稳定。"],
            "wasted_patterns": [],
            "evolution_candidates": ["把轻记录命中结果继续接到更完整的 canonical 回查视图。"],
        }

    @staticmethod
    def _load_canonical_entities(name: str) -> list[dict[str, Any]]:
        path = PROJECT_ROOT / "canonical" / "entities" / f"{name}.json"
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []

    @staticmethod
    def _task_lane(task: dict[str, Any]) -> str:
        status = str(task.get("status", "")).strip()
        human_boundary = str(task.get("human_boundary_state", "")).strip()
        if status == "blocked_needs_user" or human_boundary in WAITING_HUMAN_STATES:
            return "waiting_for_user"
        if status in BLOCKED_TASK_STATUSES:
            return "blocked"
        if status in ACTIVE_TASK_STATUSES:
            return "active"
        return "other"

    def _canonical_task_items(self) -> list[dict[str, Any]]:
        tasks = self._load_canonical_entities("tasks")
        threads = {
            str(item.get("thread_id") or item.get("id") or "").strip(): item
            for item in self._load_canonical_entities("threads")
        }
        items: list[dict[str, Any]] = []
        for task in tasks:
            thread_id = str(task.get("thread_id", "")).strip()
            thread = threads.get(thread_id, {})
            lane = self._task_lane(task)
            status = str(task.get("status", "")).strip() or "unknown"
            if status in {"completed", "merged", "deferred", "archived"}:
                continue
            next_action = str(task.get("next_action", "")).strip()
            if not next_action:
                open_questions = thread.get("open_questions") if isinstance(thread.get("open_questions"), list) else []
                next_action = str(open_questions[0]).strip() if open_questions else ""
            run_id = str(task.get("intake_run_id", "")).strip() or str(thread.get("source_run_id", "")).strip()
            items.append(
                {
                    "task_id": str(task.get("task_id") or task.get("id") or "").strip(),
                    "thread_id": thread_id,
                    "thread_title": str(thread.get("title", "")).strip(),
                    "title": str(task.get("title") or thread.get("title") or task.get("task_id") or "").strip(),
                    "status": status,
                    "priority": str(task.get("priority", "")).strip() or "P9",
                    "lane": lane,
                    "next_action": next_action,
                    "human_boundary_state": str(task.get("human_boundary_state", "")).strip() or "not_needed",
                    "verification_state": str(task.get("verification_state", "")).strip() or "unknown",
                    "run_id": run_id,
                    "updated_at": str(task.get("updated_at") or task.get("last_updated_at") or thread.get("updated_at") or "").strip(),
                }
            )
        priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4, "P5": 5, "P6": 6, "P7": 7, "P8": 8, "P9": 9}
        lane_order = {"waiting_for_user": 0, "blocked": 1, "active": 2, "other": 3}
        items.sort(
            key=lambda item: (
                lane_order.get(item["lane"], 9),
                priority_order.get(item["priority"], 9),
                item["updated_at"],
            ),
            reverse=False,
        )
        return items

    def my_tasks(self, *, limit: int = 5) -> dict[str, Any]:
        items = self._canonical_task_items()
        waiting = [item for item in items if item["lane"] == "waiting_for_user"]
        blocked = [item for item in items if item["lane"] == "blocked"]
        active = [item for item in items if item["lane"] == "active"]
        top = (waiting + blocked + active + [item for item in items if item["lane"] == "other"])[:limit]
        if not top:
            return {
                "status": "empty",
                "summary": "当前 canonical 里还没有可展示的活跃任务。",
                "next_step": "先从飞书里给我一个任务，我来起第一条 run。",
                "tasks": [],
                "counts": {"waiting_for_user": 0, "blocked": 0, "active": 0},
            }
        summary = f"活跃 {len(active)} / 阻塞 {len(blocked)} / 待你拍板 {len(waiting)}"
        next_step = next((item["next_action"] for item in top if item["next_action"]), "先看排在最前的那条任务。")
        return {
            "status": "ok",
            "summary": summary,
            "next_step": next_step,
            "tasks": top,
            "counts": {"waiting_for_user": len(waiting), "blocked": len(blocked), "active": len(active)},
        }

    def today_focus(self) -> dict[str, Any]:
        task_summary = self.my_tasks(limit=5)
        tasks = task_summary.get("tasks", [])
        if not tasks:
            return {
                "status": "empty",
                "summary": "今天没有抓到需要优先看的 canonical 活跃任务。",
                "next_step": "先给我一个今天要推进的目标。",
                "focus_items": [],
            }
        focus_items = tasks[:3]
        summary = "；".join(
            [
                f"{item['title']}（{item['status']}）"
                for item in focus_items
            ]
        )
        next_step = next((item["next_action"] for item in focus_items if item["next_action"]), task_summary.get("next_step", "先处理排在最前的那条。"))
        return {
            "status": "ok",
            "summary": summary,
            "next_step": next_step,
            "focus_items": focus_items,
            "counts": task_summary.get("counts", {}),
        }

    def project_heartbeat(self) -> dict[str, Any]:
        current_root = Path(
            getattr(
                self.module,
                "PROJECT_HEARTBEAT_CURRENT_ROOT",
                PROJECT_ROOT / "work" / "ai-da-guan-jia" / "artifacts" / "ai-da-guan-jia" / "heartbeat" / "current",
            )
        )
        latest_round = self._load_optional_json(current_root / "latest-round.json")
        if not latest_round:
            return {
                "status": "missing",
                "summary": "小猫 还没有产出任何小时推进回合。",
                "next_step": "先在后端跑一次 project-heartbeat，我再告诉你它现在在推什么。",
                "top_action": {},
                "top_human_boundary": {},
                "recent_actions": [],
                "current_max_distortion": "还没有 heartbeat 证据，不能假装它已经在主动治理。",
                "verification_status": "missing_heartbeat",
                "run_id": "",
            }
        action_queue_payload = self._load_optional_json(current_root / "action-queue.json")
        boundary_payload = self._load_optional_json(current_root / "human-boundary-queue.json")
        nudge_log = self._load_optional_json(current_root / "nudge-log.json")
        top_action = latest_round.get("top_action") if isinstance(latest_round.get("top_action"), dict) else {}
        top_boundary = latest_round.get("top_human_boundary") if isinstance(latest_round.get("top_human_boundary"), dict) else {}
        recent_actions = action_queue_payload.get("actions") if isinstance(action_queue_payload, dict) else []
        if not isinstance(recent_actions, list):
            recent_actions = []
        boundary_items = boundary_payload.get("items") if isinstance(boundary_payload, dict) else []
        if not isinstance(boundary_items, list):
            boundary_items = []
        nudge_entries = nudge_log.get("entries") if isinstance(nudge_log, dict) else []
        if not isinstance(nudge_entries, list):
            nudge_entries = []
        summary = str(latest_round.get("total_judgment") or "").strip() or "小猫 已完成一轮项目巡检。"
        next_step = str(top_action.get("next_step") or top_action.get("summary") or "继续盯住当前 top action。").strip()
        return {
            "status": str(latest_round.get("status") or "ok"),
            "summary": summary,
            "next_step": next_step,
            "top_action": top_action,
            "top_human_boundary": top_boundary or (boundary_items[0] if boundary_items else {}),
            "recent_actions": recent_actions[:3],
            "recent_nudges": nudge_entries[-3:],
            "current_max_distortion": str(latest_round.get("current_max_distortion") or "").strip(),
            "verification_status": "heartbeat_round_read",
            "run_id": str(latest_round.get("round_key") or "").strip(),
            "artifact_root": str(current_root),
        }

    def resume_context(self, session: FrontdeskSessionState) -> dict[str, Any]:
        active_run_id = session.active_run_id or session.run_id
        if active_run_id:
            run_status = self.get_run_status(active_run_id)
            if run_status.get("status") == "found":
                return {
                    "status": "found",
                    "summary": str(run_status.get("task_text") or session.last_user_goal or "已恢复最近任务。"),
                    "next_step": str(run_status.get("next_step") or session.task_text or "继续按当前技能链推进。"),
                    "run_id": active_run_id,
                    "verification_status": str(session.last_verification_status or run_status.get("close_status", "route_only")),
                    "human_boundary": str(session.pending_human_boundary or run_status.get("human_boundary", "")),
                    "selected_skills": run_status.get("selected_skills", []),
                }
        if session.last_user_goal:
            return {
                "status": "session_only",
                "summary": session.last_user_goal,
                "next_step": session.task_text or "把上次目标再发一句，我继续接。",
                "run_id": active_run_id,
                "verification_status": session.last_verification_status or "missing_run",
                "human_boundary": session.pending_human_boundary,
                "selected_skills": [],
            }
        return {
            "status": "missing",
            "summary": "当前还没有可恢复的最近上下文。",
            "next_step": "直接说“帮我接个任务”或把上次那件事再发一遍。",
            "run_id": "",
            "verification_status": "missing_context",
            "human_boundary": "",
            "selected_skills": [],
        }

    def handoff_to_pc(self, session: FrontdeskSessionState) -> dict[str, Any]:
        resume = self.resume_context(session)
        if resume["status"] == "missing":
            return {
                "status": "missing",
                "summary": "当前没有现成 run 可交接到 PC。",
                "next_step": "先在飞书里起单，我再给你 run id 和 PC 续接点。",
                "run_id": "",
                "verification_status": "missing_context",
                "human_boundary": "",
            }
        run_id = str(resume.get("run_id", "")).strip()
        next_step = str(resume.get("next_step", "")).strip()
        if run_id:
            next_step = f"回到 PC 后继续 run {run_id}；{next_step}".strip("；")
        return {
            "status": "ready",
            "summary": f"这件事适合切回 PC 深工：{resume.get('summary', '')}",
            "next_step": next_step or "回到 PC 后继续当前技能链。",
            "run_id": run_id,
            "verification_status": str(resume.get("verification_status", "")),
            "human_boundary": str(resume.get("human_boundary", "")),
        }

    def _invoke_module_callable(self, func: Any, args: argparse.Namespace, run_dir: Path, run_id: str) -> dict[str, Any]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = int(func(args, run_dir, run_id))
        return {
            "exit_code": exit_code,
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
        }

    def _invoke_module_command(self, func: Any, args: argparse.Namespace) -> dict[str, Any]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = int(func(args))
        return {
            "exit_code": exit_code,
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
        }

    def judge_task(self, input_text: str, user_context: dict[str, Any] | None = None) -> dict[str, Any]:
        route = self.route_task(input_text, user_context=user_context)
        situation = route.get("situation_map", {})
        return {
            "status": "judged",
            "execution_mode": "route_only",
            "route": route,
            "judgments": {
                "自治判断": str(situation.get("自治判断", "")),
                "全局最优判断": str(situation.get("全局最优判断", "")),
                "当前最大失真": str(situation.get("当前最大失真", "")),
                "能力复用判断": str(situation.get("能力复用判断", "")),
            },
        }

    def suggest_human_decision(self, context: str, user_context: dict[str, Any] | None = None) -> dict[str, Any]:
        result = self.judge_task(context, user_context=user_context)
        route = result["route"]
        situation = route.get("situation_map", {})
        return {
            "status": "suggested",
            "route": route,
            "recommended": f"由你拍板，AI 负责比较与草案。建议路径：{', '.join(route.get('selected_skills', [])) or 'none'}",
            "not_recommended": "让 AI 直接处理发布、删除、授权、付款或价值取舍类不可逆动作。",
            "why_human_now": str(route.get("human_boundary") or situation.get("自治判断") or "这类动作属于明确的人类边界。"),
        }

    def knowledge_lookup(
        self,
        input_text: str,
        user_context: dict[str, Any] | None = None,
        *,
        allow_execute: bool = False,
    ) -> dict[str, Any]:
        local_capture = self._lookup_local_capture(input_text)
        if local_capture is not None:
            return local_capture
        route = self.route_task(input_text, user_context=user_context)
        signals = route.get("signals", {})
        if not any([signals.get("get_biji"), signals.get("feishu_km"), signals.get("knowledge_first")]) and looks_like_lightweight_knowledge_query(input_text):
            route["signals"] = dict(signals)
            route["signals"]["get_biji"] = True
            route.update(self.module.plan_get_biji_actions(input_text))
            return self._handle_get_biji_lookup(route, allow_execute=allow_execute)
        if signals.get("get_biji"):
            return self._handle_get_biji_lookup(route, allow_execute=allow_execute)
        if signals.get("feishu_km") or signals.get("knowledge_first"):
            return self._handle_feishu_km_lookup(route, allow_execute=allow_execute)
        return {
            "status": "planned",
            "execution_mode": "route_only",
            "route": route,
            "source_label": "待判定知识源",
            "summary": shorten(route.get("human_route_summary") or "当前问题更像普通任务，先给出知识源选择建议。"),
            "missing": "还缺明确知识源；可指定飞书知识库、Get笔记、逐字稿或历史笔记。",
            "produced_evidence": False,
            "verification_evidence": [],
            "open_questions": ["你希望先问飞书知识库，还是先查 Get笔记？"],
            "effective_patterns": [],
            "wasted_patterns": [],
            "evolution_candidates": ["把常见知识源查询做成更稳定的前端入口。"],
        }

    def note_capture(self, input_text: str, user_context: dict[str, Any] | None = None) -> dict[str, Any]:
        raw_text = str(input_text or "").strip()
        capture_text = strip_note_capture_prefix(raw_text).strip() or raw_text
        created_at = iso_now()
        timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
        capture_id = f"frontdesk-capture-{timestamp}"
        session = user_context.get("__session__") if isinstance(user_context, dict) else None
        session = session if isinstance(session, FrontdeskSessionState) else None
        run_id, run_dir, is_new_run = self._resolve_capture_run(created_at, session)
        capture_dir = run_dir / CANONICAL_CAPTURE_DIRNAME
        capture_dir.mkdir(parents=True, exist_ok=True)
        session_id = str(session.session_id if session is not None else build_session_id(user_context)).strip()
        parent_run_id = str(session.active_run_id or session.run_id or "").strip() if session is not None else ""
        payload = {
            "capture_id": capture_id,
            "created_at": created_at,
            "source": "yuanli_os_frontdesk",
            "surface": "feishu_bot",
            "kind": "note_capture",
            "content": capture_text,
            "run_id": run_id,
            "parent_run_id": parent_run_id,
            "session_id": session_id,
            "sync_status": "canonical_local_only",
        }
        artifact_path = capture_dir / f"{capture_id}.json"
        self.module.write_json(artifact_path, payload)
        summary_path = capture_dir / f"{capture_id}.md"
        summary_path.write_text(
            "\n".join(
                [
                    "# 原力OS 轻记录",
                    "",
                    f"- capture_id: `{capture_id}`",
                    f"- run_id: `{run_id}`",
                    f"- session_id: `{session_id or 'none'}`",
                    f"- created_at: `{created_at}`",
                    "",
                    capture_text,
                    "",
                ]
            ),
            encoding="utf-8",
        )
        route_path = run_dir / "route.json"
        if is_new_run and not route_path.exists():
            self.module.write_json(
                route_path,
                {
                    "run_id": run_id,
                    "created_at": created_at,
                    "task_text": capture_text,
                    "selected_skills": ["ai-da-guan-jia", "yuanli_os_frontdesk"],
                    "human_boundary": "轻记录只落本地 canonical，不替你直接写第三方笔记。",
                    "verification_targets": [str(artifact_path)],
                    "bridge_surface": "feishu_bot",
                    "note_capture": True,
                },
            )
        next_step = "如果你要继续查，就发：原力原力 搜一下 ...；如果要推进成任务，就直接说帮我接个任务。"
        return {
            "status": "captured",
            "capture_id": capture_id,
            "run_id": run_id,
            "summary": shorten(capture_text, limit=120),
            "next_step": next_step,
            "verification_status": "captured_canonical",
            "artifact_path": str(artifact_path),
            "summary_path": str(summary_path),
            "canonical_run_dir": str(run_dir),
            "canonical_ref": f"{run_id}::{capture_id}",
            "sync_status": "canonical_local_only",
            "content": capture_text,
        }

    def _finance_run_dir(self, prefix: str) -> tuple[str, str, Path]:
        created_at = iso_now()
        timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
        run_id = f"{prefix}-{timestamp}"
        run_dir = Path(self.capture_root) / created_at[:10] / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_id, created_at, run_dir

    @staticmethod
    def _write_plain_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def finance_news_search(self, input_text: str, *, limit: int = 5, days: int = 1) -> dict[str, Any]:
        result = self.finance_adapter.search_news(input_text, limit=limit, days=days)
        run_id, created_at, run_dir = self._finance_run_dir("finance-news")
        artifact_path = run_dir / "finance-news.json"
        payload = {
            "run_id": run_id,
            "created_at": created_at,
            "query": input_text,
            "tool": "finance_news_search",
            **result,
        }
        self._write_plain_json(artifact_path, payload)
        return {
            **result,
            "run_id": run_id,
            "created_at": created_at,
            "artifact_path": str(artifact_path),
            "verification_evidence": [str(artifact_path)],
            "produced_evidence": bool(result.get("facts")),
            "open_questions": ([] if result.get("status") == "ok" else [str(result.get("missing", "")).strip()]),
            "effective_patterns": ["金融资讯结果必须带来源和发布时间。"] if result.get("status") == "ok" else [],
            "wasted_patterns": ([] if result.get("status") == "ok" else ["把泛搜索结果误当成实时金融资讯。"]),
            "evolution_candidates": ["继续补新闻去重、关键词提炼和 provider 切换策略。"],
            "human_boundary": "默认不输出结论性荐股判断。",
        }

    def finance_data_query(self, input_text: str) -> dict[str, Any]:
        result = self.finance_adapter.query_data(input_text)
        run_id, created_at, run_dir = self._finance_run_dir("finance-data")
        artifact_path = run_dir / "finance-data.json"
        payload = {
            "run_id": run_id,
            "created_at": created_at,
            "query": input_text,
            "tool": "finance_data_query",
            **result,
        }
        self._write_plain_json(artifact_path, payload)
        return {
            **result,
            "run_id": run_id,
            "created_at": created_at,
            "artifact_path": str(artifact_path),
            "verification_evidence": [str(artifact_path)],
            "produced_evidence": bool(result.get("facts")),
            "open_questions": ([] if result.get("status") == "ok" else [str(result.get("missing", "")).strip()]),
            "effective_patterns": ["所有金融数据都带 `source + as_of`，避免把旧数据说成实时。"] if result.get("status") == "ok" else [],
            "wasted_patterns": ([] if result.get("status") == "ok" else ["上游失败时返回伪实时数据。"]),
            "evolution_candidates": ["继续补更多证券类型和指标映射。"],
            "human_boundary": "这是事实数据查询，不自动给投资建议。",
        }

    def stock_screen(self, input_text: str, *, limit: int = 10) -> dict[str, Any]:
        result = self.finance_adapter.screen_stocks(input_text, limit=limit)
        run_id, created_at, run_dir = self._finance_run_dir("stock-screen")
        artifact_path = run_dir / "stock-screen.json"
        payload = {
            "run_id": run_id,
            "created_at": created_at,
            "query": input_text,
            "tool": "stock_screen",
            **result,
        }
        self._write_plain_json(artifact_path, payload)
        return {
            **result,
            "run_id": run_id,
            "created_at": created_at,
            "artifact_path": str(artifact_path),
            "verification_evidence": [str(artifact_path)],
            "produced_evidence": bool(result.get("results")),
            "open_questions": ([] if result.get("status") == "ok" else [str(result.get("missing", "")).strip()]),
            "effective_patterns": ["回显命中的显式规则，避免黑盒式选股结果。"] if result.get("status") == "ok" else [],
            "wasted_patterns": ([] if result.get("status") == "ok" else ["规则不完整却假装已经筛完市场。"]),
            "evolution_candidates": ["继续补更稳定的指标 universe 与排序规则。"],
            "human_boundary": "这是规则筛选工具，不是投顾或自动交易系统。",
        }

    def _handle_get_biji_lookup(self, route: dict[str, Any], *, allow_execute: bool) -> dict[str, Any]:
        action = str(route.get("primary_action") or "").strip()
        recommended_actions = route.get("recommended_actions") or []
        first_action = recommended_actions[0] if recommended_actions else {}
        inputs = first_action.get("inputs") or {}
        run_id = str(route.get("run_id", "")).strip()
        run_dir = Path(route["run_dir"])
        preview_missing = "当前运行模式只给出路径建议，未直接调用 Get笔记。"
        if action not in {"get_biji.ask", "get_biji.recall"}:
            preview_missing = "这类 Get笔记 动作仍属于较重执行链路，当前前端只提供建议路径。"
        if not allow_execute or action not in {"get_biji.ask", "get_biji.recall"}:
            return {
                "status": "planned",
                "execution_mode": "route_only",
                "route": route,
                "source_label": f"Get笔记 / {action or 'planned_lookup'}",
                "summary": shorten(route.get("human_route_summary") or "建议先按 Get笔记 路径查询。"),
                "missing": preview_missing,
                "produced_evidence": False,
                "verification_evidence": [],
                "open_questions": [preview_missing],
                "effective_patterns": [],
                "wasted_patterns": [],
                "evolution_candidates": ["把高频 Get笔记 查询稳定成可前端直接调用的读路径。"],
            }

        if action == "get_biji.ask":
            args = argparse.Namespace(
                question=inputs.get("question", route["task_text"]),
                topic_id=inputs.get("topic_id", ""),
                knowledge_base_id=inputs.get("knowledge_base_id", ""),
                user=inputs.get("user", "ai-da-guan-jia"),
                run_id=run_id,
            )
            command_result = self._invoke_module_callable(self.module.execute_get_biji_api_ask, args, run_dir, run_id)
        else:
            args = argparse.Namespace(
                query=inputs.get("query", route["task_text"]),
                topic_id=inputs.get("topic_id", ""),
                knowledge_base_id=inputs.get("knowledge_base_id", ""),
                top_k=inputs.get("top_k", 5),
                run_id=run_id,
            )
            command_result = self._invoke_module_callable(self.module.execute_get_biji_api_recall, args, run_dir, run_id)

        record = self._load_optional_json(run_dir / "get-biji-record.json")
        summary = shorten(str(record.get("answer") or self._summarize_hits(record.get("hits", [])) or route.get("human_route_summary") or "未拿到稳定答案。"))
        verification_note = str(record.get("verification_note") or "").strip()
        success = bool(record.get("success")) and command_result["exit_code"] == 0
        evidence = [
            f"record: {run_dir / 'get-biji-record.json'}",
            f"response: {run_dir / 'get-biji-response.json'}",
        ]
        metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        transcript_path = str(metadata.get("transcript_txt") or "").strip()
        if transcript_path:
            evidence.append(f"transcript: {transcript_path}")
        return {
            "status": "completed" if success else "blocked",
            "execution_mode": "p0_assist",
            "route": route,
            "record": record,
            "source_label": f"{record.get('source', 'get_biji_api')} / {record.get('operation', action)}",
            "summary": summary,
            "missing": verification_note or "需要继续核对原始命中内容。",
            "produced_evidence": success and bool(record.get("answer") or record.get("hits") or transcript_path),
            "verification_evidence": evidence,
            "open_questions": ([] if success else [verification_note or "Get笔记 查询未产出稳定证据。"]),
            "effective_patterns": ["前端能直接走 Get笔记 读路径时，查询回路更短。"] if success else [],
            "wasted_patterns": ([] if success else ["把较重的知识查询当成一定会即时返回。"]),
            "evolution_candidates": ["补稳定的 Get笔记 查询状态提示与错误分层。"],
        }

    def _handle_feishu_km_lookup(self, route: dict[str, Any], *, allow_execute: bool) -> dict[str, Any]:
        run_id = str(route.get("run_id", "")).strip()
        run_dir = Path(route["run_dir"])
        preview_missing = "当前默认只给出 ask.feishu / Aily 的提问路径，不自动伪造答案。"
        if not allow_execute:
            return {
                "status": "planned",
                "execution_mode": "route_only",
                "route": route,
                "source_label": "ask.feishu / Aily（计划路径）",
                "summary": shorten(route.get("human_route_summary") or "建议先问飞书知识库，并保留原始问答。"),
                "missing": preview_missing,
                "produced_evidence": False,
                "verification_evidence": [],
                "open_questions": [preview_missing],
                "effective_patterns": [],
                "wasted_patterns": [],
                "evolution_candidates": ["把飞书知识问答的 manual_web 与 official_api 路径区分清楚。"],
            }

        args = argparse.Namespace(
            question=route["task_text"],
            source_url=getattr(self.module, "FEISHU_KM_DEFAULT_SOURCE_URL", ""),
            run_id=run_id,
            feishu_km_command="prepare-manual",
        )
        command_result = self._invoke_module_callable(self.module.execute_feishu_km_prepare_manual, args, run_dir, run_id)
        request_payload = self._load_optional_json(run_dir / "feishu-km-request.json")
        question_file = run_dir / "feishu-km-question.md"
        evidence = [
            f"request: {run_dir / 'feishu-km-request.json'}",
            f"question_file: {question_file}",
        ]
        if command_result["exit_code"] != 0:
            return {
                "status": "blocked",
                "execution_mode": "p0_assist",
                "route": route,
                "source_label": "ask.feishu / manual_web",
                "summary": "飞书知识问答提问包生成失败。",
                "missing": shorten(command_result["stderr"] or command_result["stdout"] or "需要检查 feishu-km 运行前提。"),
                "produced_evidence": False,
                "verification_evidence": evidence,
                "open_questions": ["需要先确认 ask.feishu / Aily 的提问路径是否可用。"],
                "effective_patterns": [],
                "wasted_patterns": ["没有先分清 manual_web 与 official_api 的边界。"],
                "evolution_candidates": ["补飞书知识问答 readiness 提示。"],
            }
        return {
            "status": "prepared",
            "execution_mode": "p0_assist",
            "route": route,
            "request": request_payload,
            "source_label": "ask.feishu / manual_web",
            "summary": "已生成提问包；下一步是在 ask.feishu 提问并保留原始回答。",
            "missing": "还缺 raw answer。只有记录原始回答后，才适合继续综合与规划。",
            "produced_evidence": False,
            "verification_evidence": evidence,
            "open_questions": ["请把 ask.feishu 的原始回答复制回来，再进入综合。"],
            "effective_patterns": ["先保留原始问答，再做总结，可以降低二手总结失真。"],
            "wasted_patterns": [],
            "evolution_candidates": ["把 feishu-km manual_web 录回答步骤也接进前端。"],
        }

    def assess_close_loop(
        self,
        last_session: FrontdeskSessionState,
        *,
        allow_execute: bool = False,
    ) -> dict[str, Any]:
        verification_status = str(last_session.last_verification_status or "").strip()
        evidence_paths = [str(item).strip() for item in last_session.verification_evidence if str(item).strip()]
        if not last_session.task_text:
            return {
                "status": "missing_context",
                "summary": "当前没有可收口的最近任务。",
                "verification_status": "missing_context",
                "missing": "先给任务、做一次知识查询，或让 AI 先形成一个 run。",
                "next_iterate": "先完成一次有证据的任务回合，再谈闭环。",
                "run_id": "",
            }

        if not evidence_paths:
            return {
                "status": "not_ready",
                "summary": f"当前还没有 canonical 证据支撑真正闭环：{last_session.task_text}",
                "verification_status": "not_ready",
                "missing": "还缺可复核 canonical artifact；不能把“会回话”误判成“任务完成”。",
                "next_iterate": "先补知识查询结果、任务产物或人工确认的完成证据，再执行 close-task。",
                "run_id": last_session.run_id,
            }

        if verification_status in NON_CLOSURE_VERIFICATION_STATUSES:
            missing = "已有本地证据，但还不是可闭环的完成证据。"
            if verification_status == "captured_canonical":
                missing = "已经记进 canonical，但这只是轻记录，不等于任务完成。"
            return {
                "status": "not_ready",
                "summary": f"这件事已有记录，但还不适合闭环：{last_session.task_text}",
                "verification_status": "not_ready",
                "missing": missing,
                "next_iterate": "先把这条记录继续查清、推进成任务产物，或补人工确认，再谈 close-task。",
                "run_id": last_session.run_id,
            }

        if not allow_execute:
            return {
                "status": "ready_for_close",
                "summary": f"这件事已具备进入 close-task 的基本证据：{last_session.task_text}",
                "verification_status": "ready_for_close",
                "missing": "当前前端还未替你正式执行 closure apply。",
                "next_iterate": "切到 p0_assist 或在终端执行 close-task，生成正式 canonical closure。",
                "run_id": last_session.run_id,
            }

        created_at = self.module.iso_now()
        run_id = self.module.allocate_run_id(created_at)
        args = argparse.Namespace(
            task=last_session.task_text,
            goal="Close the frontdesk task with verification, reusable patterns, and recursive improvement.",
            verification_status="partially_verified" if last_session.open_questions else "completed",
            evidence=last_session.verification_evidence or ["Feishu frontdesk interaction produced local evidence."],
            open_question=last_session.open_questions,
            effective_pattern=last_session.effective_patterns or ["飞书前端把任务入口和治理后端分开了。"],
            wasted_pattern=last_session.wasted_patterns or ["如果没有正式 closure，容易把可用性误判成完成。"],
            evolution_candidate=last_session.evolution_candidates or ["补 persistent idempotency 和更稳定的前端协议。"],
            human_boundary=last_session.human_boundary or "Only escalate to the human for publish/delete/auth/payment/value decisions.",
            max_distortion=last_session.max_distortion or "把前端可用误判成任务闭环完成。",
            run_id=run_id,
            created_at=created_at,
            link=None,
            primary_field=None,
            bridge_script=None,
            repo=None,
        )
        command_result = self._invoke_module_command(self.module.command_close_task, args)
        run_dir = Path(self.module.run_dir_for(run_id, created_at))
        evolution = self._load_optional_json(run_dir / "evolution.json")
        worklog = self._load_optional_json(run_dir / "worklog.json")
        success = command_result["exit_code"] == 0
        return {
            "status": "closed" if success else "blocked",
            "summary": str(worklog.get("完成情况") or worklog.get("工作状态") or "已尝试执行 closure。"),
            "verification_status": str(evolution.get("verification_result", {}).get("status", "blocked")),
            "missing": shorten(command_result["stderr"] or "如仍有开放问题，以 evolution.json 为准。"),
            "next_iterate": shorten("；".join(evolution.get("evolution_candidates", [])) or "继续按 next iterate 推进。"),
            "run_id": run_id,
            "worklog": worklog,
            "evolution": evolution,
        }

    def execute_task(self, input_text: str, user_context: dict[str, Any] | None = None) -> dict[str, Any]:
        route = self.route_task(input_text, user_context=user_context)
        next_steps = self._next_steps_from_route(route)
        return {
            "status": "planned",
            "execution_mode": "route_only",
            "route": route,
            "summary": {
                "selected_skills": route.get("selected_skills", []),
                "verification_targets": route.get("verification_targets", []),
                "human_boundary": route.get("human_boundary", ""),
                "next_steps": next_steps,
            },
        }

    def render_feishu_response(self, result: dict[str, Any]) -> dict[str, Any]:
        route = result["route"]
        selected = route.get("selected_skills", [])
        verification_targets = route.get("verification_targets", [])
        next_steps = result.get("summary", {}).get("next_steps", [])
        lines = [
            f"原力OS 已接单：{route['task_text']}",
            f"路由技能：{', '.join(selected) if selected else 'none'}",
            f"验真目标：{'; '.join(verification_targets[:3]) if verification_targets else 'none'}",
            f"本地 run：{route['run_id']}",
        ]
        if next_steps:
            lines.append(f"下一步：{next_steps[0]}")
        return {
            "text": "\n".join(lines),
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {"title": {"tag": "plain_text", "content": "原力OS 路由结果"}},
                "elements": [
                    {"tag": "markdown", "content": f"**任务**\n{route['task_text']}"},
                    {"tag": "markdown", "content": f"**技能链**\n{', '.join(selected) if selected else 'none'}"},
                    {"tag": "markdown", "content": f"**Run ID**\n{route['run_id']}"},
                ],
            },
        }


class FeishuClawBridgeService:
    def __init__(
        self,
        config: BridgeConfig,
        auth_client: FeishuAuthClient | None = None,
        messenger: FeishuMessenger | None = None,
        backend: AiDaGuanJiaBackend | None = None,
        verifier: FeishuEventVerifier | None = None,
        idempotency_store: IdempotencyStore | None = None,
        session_store: FrontdeskSessionStore | None = None,
    ):
        self.config = config
        self.auth_client = auth_client or FeishuAuthClient(config)
        self.messenger = messenger or FeishuMessenger(self.auth_client)
        self.backend = backend or AiDaGuanJiaBackend(persist_route=config.route_persist)
        self.verifier = verifier or FeishuEventVerifier(config)
        self.idempotency_store = idempotency_store or IdempotencyStore()
        self.session_store = session_store or FrontdeskSessionStore()
        self.chat_sessions: dict[str, FrontdeskSessionState] = {}

    def auth_check(self) -> dict[str, Any]:
        token = self.auth_client.get_tenant_access_token()
        return {"ok": True, "tenant_access_token_prefix": token[:12]}

    def bundle_status(self, *, verify_runtime: bool = False) -> dict[str, Any]:
        return inspect_installation_state(auth_client=self.auth_client, verify_runtime=verify_runtime)

    def bundle_metadata(self, *, verify_runtime: bool = False) -> dict[str, Any]:
        capabilities = self.backend.list_frontdesk_capabilities()
        return {
            **capabilities,
            "install_prompt": render_install_prompt(),
            "install_source": resolve_bundle_source(),
            "install_prompt_template": str(DISTRIBUTION_INSTALL_PROMPT_TEMPLATE),
            "bundle_root": str(DISTRIBUTION_ROOT),
            "frontend_guide": str(FRONTEND_GUIDE_PATH),
            "installation_state": self.bundle_status(verify_runtime=verify_runtime),
        }

    def _runtime_owner(self) -> str:
        instance_tag = str(self.config.instance_tag or "").strip()
        if instance_tag:
            return instance_tag
        return f"official::{self.config.app_id}"

    def runtime_diagnostics(self, *, chat_id: str = "", session_id: str = "", limit: int = 5) -> dict[str, Any]:
        sessions = self.session_store.all_sessions()
        sessions.sort(key=lambda item: str(item.updated_at or ""), reverse=True)
        target: FrontdeskSessionState | None = None
        for state in sessions:
            if session_id and state.session_id == session_id:
                target = state
                break
            if chat_id and state.chat_id == chat_id:
                target = state
                break
        if target is None and sessions:
            target = sessions[0]
        return {
            "official_owner": self._runtime_owner(),
            "instance_tag": str(self.config.instance_tag or "").strip(),
            "execution_mode": self.config.execution_mode,
            "send_cards": bool(self.config.send_cards),
            "target_session": target.to_dict() if target is not None else {},
            "recent_sessions": [state.to_dict() for state in sessions[: max(limit, 0)]],
            "recent_events": self.idempotency_store.recent_events(limit=max(limit, 0)),
        }

    def _detect_signals(self, text: str) -> dict[str, bool]:
        module = getattr(self.backend, "module", None)
        if module is not None and hasattr(module, "detect_signals"):
            return module.detect_signals(text)
        return {
            "get_biji": text_has_any(normalize_text(text), KNOWLEDGE_KEYWORDS),
            "feishu_km": "飞书知识库" in text or "ask.feishu" in text,
            "knowledge_first": text_has_any(normalize_text(text), KNOWLEDGE_KEYWORDS),
            "hard_boundary": text_has_any(normalize_text(text), APPROVAL_KEYWORDS),
        }

    def _session_from_context(self, user_context: dict[str, Any] | None = None) -> FrontdeskSessionState:
        context = user_context or {}
        session_id = build_session_id(context)
        chat_id = str(context.get("chat_id", "")).strip()
        cached = self.chat_sessions.get(session_id) or (self.chat_sessions.get(chat_id) if chat_id else None)
        if cached is not None:
            state = FrontdeskSessionState.from_dict(cached.to_dict())
        else:
            state = self.session_store.get(session_id) or FrontdeskSessionState()
        state.session_id = state.session_id or session_id
        state.chat_id = state.chat_id or chat_id
        state.tenant_key = state.tenant_key or str(context.get("tenant_key", "")).strip()
        state.user_open_id = state.user_open_id or str(context.get("open_id") or context.get("user_open_id") or "").strip()
        return state

    def _cache_session(self, state: FrontdeskSessionState) -> None:
        if state.session_id:
            self.chat_sessions[state.session_id] = FrontdeskSessionState.from_dict(state.to_dict())
        if state.chat_id:
            self.chat_sessions[state.chat_id] = FrontdeskSessionState.from_dict(state.to_dict())

    @staticmethod
    def _default_requested_state(scene: str) -> str:
        mapping = {
            "task_intake": "follow_up_requested",
            "resume_context": "resume_requested",
            "project_heartbeat": "follow_up_requested",
            "approval": "waiting_for_user",
            "close_loop": "close_check_requested",
            "handoff_to_pc": "follow_up_requested",
            "note_capture": "follow_up_requested",
        }
        return mapping.get(scene, "")

    @staticmethod
    def _list_field(session_update: dict[str, Any], key: str, current: list[str]) -> list[str]:
        if key not in session_update:
            return current
        return [str(item) for item in session_update.get(key, [])]

    def _update_session(self, user_context: dict[str, Any] | None, reply: FrontdeskReply) -> None:
        session_update = reply.metadata.get("session_update")
        if reply.scene == "home" and not isinstance(session_update, dict):
            return
        update = session_update if isinstance(session_update, dict) else {}
        current = self._session_from_context(user_context)
        context = user_context or {}
        task_text = str(update.get("task_text", "")).strip() or current.task_text
        run_id = str(update.get("run_id", "")).strip() or reply.run_id or current.run_id
        human_boundary = str(update.get("human_boundary", "")).strip() or reply.human_boundary or current.human_boundary
        verification_status = str(update.get("verification_status", "")).strip() or reply.verification_status or current.last_verification_status
        runtime_owner = str(update.get("runtime_owner", "")).strip() or self._runtime_owner()
        owner_heartbeat_at = str(update.get("owner_heartbeat_at", "")).strip() or iso_now()
        last_event_source = str(update.get("last_event_source", "")).strip() or str(context.get("event_source") or context.get("surface") or current.last_event_source).strip()
        last_event_id = str(update.get("last_event_id", "")).strip() or str(context.get("event_id") or current.last_event_id).strip()
        last_user_message_id = str(update.get("last_user_message_id", "")).strip() or str(context.get("message_id") or current.last_user_message_id).strip()
        merged = FrontdeskSessionState(
            session_id=current.session_id,
            chat_id=current.chat_id,
            tenant_key=current.tenant_key,
            user_open_id=current.user_open_id,
            scene=reply.scene,
            last_scene=reply.scene,
            task_text=task_text,
            last_user_goal=str(update.get("last_user_goal", "")).strip() or task_text or current.last_user_goal,
            run_id=run_id,
            active_run_id=str(update.get("active_run_id", "")).strip() or run_id or current.active_run_id,
            active_thread_id=str(update.get("active_thread_id", "")).strip() or current.active_thread_id,
            active_task_ids=self._list_field(update, "active_task_ids", current.active_task_ids),
            requested_frontdesk_state=str(update.get("requested_frontdesk_state", "")).strip() or self._default_requested_state(reply.scene) or current.requested_frontdesk_state,
            last_card_message_id=current.last_card_message_id,
            produced_evidence=bool(update.get("produced_evidence", current.produced_evidence)),
            verification_evidence=self._list_field(update, "verification_evidence", current.verification_evidence),
            open_questions=self._list_field(update, "open_questions", current.open_questions),
            effective_patterns=self._list_field(update, "effective_patterns", current.effective_patterns),
            wasted_patterns=self._list_field(update, "wasted_patterns", current.wasted_patterns),
            evolution_candidates=self._list_field(update, "evolution_candidates", current.evolution_candidates),
            human_boundary=human_boundary,
            pending_human_boundary=str(update.get("pending_human_boundary", "")).strip() or human_boundary or current.pending_human_boundary,
            max_distortion=str(update.get("max_distortion", "")).strip() or current.max_distortion,
            last_verification_status=verification_status,
            runtime_owner=runtime_owner,
            owner_heartbeat_at=owner_heartbeat_at,
            last_event_source=last_event_source,
            last_event_id=last_event_id,
            last_user_message_id=last_user_message_id,
            updated_at=iso_now(),
        )
        reply.session_id = reply.session_id or merged.session_id
        reply.metadata["session_state"] = merged.to_dict()
        self.session_store.upsert(merged)
        self._cache_session(merged)

    def _remember_card_message(self, user_context: dict[str, Any] | None, message_id: str) -> None:
        normalized = str(message_id).strip()
        if not normalized:
            return
        session = self._session_from_context(user_context)
        session.last_card_message_id = normalized
        session.owner_heartbeat_at = iso_now()
        session.updated_at = iso_now()
        self.session_store.upsert(session)
        self._cache_session(session)

    def _decorate_reply_for_delivery(self, reply: FrontdeskReply) -> FrontdeskReply:
        instance_tag = str(self.config.instance_tag or "").strip()
        if not instance_tag:
            return reply
        footer = list(reply.footer)
        signature = f"bridge: {instance_tag}"
        if signature in footer:
            return reply
        return replace(reply, footer=footer + [signature])

    def _send_card_response(self, user_context: dict[str, Any], reply: FrontdeskReply) -> None:
        chat_id = str(user_context.get("chat_id", "")).strip()
        if not chat_id or not self.config.send_cards:
            return
        session = self._session_from_context(user_context)
        response: dict[str, Any]
        if session.last_card_message_id:
            try:
                response = self.messenger.update_card(session.last_card_message_id, reply.as_card())
            except Exception:
                response = self.messenger.send_card_to_chat(chat_id, reply.as_card())
        else:
            response = self.messenger.send_card_to_chat(chat_id, reply.as_card())
        message_id = str(((response.get("data") or {}).get("message_id", ""))).strip()
        if message_id:
            self._remember_card_message(user_context, message_id)

    @staticmethod
    def _session_from_payload(payload: dict[str, Any] | None) -> FrontdeskSessionState:
        return FrontdeskSessionState.from_dict(payload)

    @staticmethod
    def _format_task_items(tasks: list[dict[str, Any]]) -> str:
        if not tasks:
            return "当前没有抓到可展示的任务。"
        return "\n".join(
            [
                f"- {item['title']}｜{item['status']}｜下一步：{item.get('next_action') or '待补'}"
                for item in tasks
            ]
        )

    @staticmethod
    def _format_finance_facts(facts: list[dict[str, Any]]) -> str:
        if not facts:
            return "当前没有稳定事实字段。"
        lines: list[str] = []
        for item in facts[:8]:
            label = str(item.get("label") or item.get("title") or "").strip()
            value = item.get("value")
            if value is None:
                value = str(item.get("summary", "")).strip()
            unit = str(item.get("unit", "")).strip()
            if isinstance(value, float):
                value_text = f"{value:.2f}"
            else:
                value_text = str(value).strip()
            source = str(item.get("source", "")).strip()
            published_at = str(item.get("published_at", "")).strip()
            if label and value_text:
                line = f"- {label}：{value_text}{unit}"
            else:
                line = f"- {shorten(str(item.get('title', '')).strip(), limit=48)}"
            if source or published_at:
                line += f"（{source or 'source unknown'} {published_at}）".rstrip()
            lines.append(line)
        return "\n".join(lines)

    @staticmethod
    def _format_screen_results(items: list[dict[str, Any]]) -> str:
        if not items:
            return "当前没有命中的股票。"
        lines: list[str] = []
        for row in items[:8]:
            matched_rules = ", ".join([str(item).strip() for item in row.get("matched_rules", []) if str(item).strip()]) or "规则命中"
            metrics: list[str] = []
            for label, key, unit in (
                ("PE", "pe", ""),
                ("PB", "pb", ""),
                ("20日涨幅", "pct_change_20d", "%"),
                ("营收同比", "revenue_yoy", "%"),
            ):
                value = row.get(key)
                if value is None:
                    continue
                metrics.append(f"{label}={value}{unit}")
            lines.append(
                f"- {row.get('name', '')}（{row.get('ts_code', '')}）｜{matched_rules}"
                + (f"｜{' / '.join(metrics)}" if metrics else "")
            )
        return "\n".join(lines)

    def _home_reply(self, session_id: str) -> FrontdeskReply:
        p0_entries = [entry for entry in HOME_ENTRIES if entry["wave"] == "P0"]
        return FrontdeskReply(
            scene="home",
            title="原力OS · 移动前台首页",
            sections=[
                ("怎么唤醒我", "- 可直接说自然语言\n- 也可以用唤醒词：原力原力\n- 只发“原力原力”时，我会把可用入口再列给你"),
                ("什么时候叫我", "\n".join([f"- {entry['name']}：{entry['prompt']}" for entry in p0_entries])),
                ("什么时候别叫我", "- 要深度研究，直接叫 Deep Research\n- 要浏览网页或操作页面，直接叫 Browser Agent\n- 要出图、搜图、改图，直接叫图片类 Skill"),
                ("连续陪伴节奏", "- 先在飞书里起单\n- 我帮你续上下文、看今天、看任务\n- 重执行切回 AI大管家 后端或 PC 深工"),
                ("协作边界", "我是连续陪伴型聊天前台，不是执行层万能代理。发布、授权、付款、删除仍由你拍板。"),
            ],
            session_id=session_id,
            summary="移动端前台已就位，可以直接接任务、续上下文、看今日重点和任务状态。",
            next_step="直接说：继续昨天那个 / 我现在有哪些任务 / 帮我接个任务；也可以说：原力原力 今天最该看什么。",
            human_boundary="发布、授权、付款、删除仍由你拍板。",
            verification_status="home",
            footer=[f"execution mode: {self.config.execution_mode}"],
        )

    def _task_intake_reply(self, content: str, user_context: dict[str, Any], session: FrontdeskSessionState) -> FrontdeskReply:
        result = self.backend.execute_task(content, user_context=user_context)
        route = result["route"]
        recommended_actions = route.get("recommended_actions") if isinstance(route.get("recommended_actions"), list) else []
        first_action = recommended_actions[0] if recommended_actions else {}
        human_summary = str(route.get("human_route_summary") or route.get("task_text") or "我理解成一个待推进任务。").strip()
        next_step = str(first_action.get("human_next_step") or route.get("next_action") or "我先帮你把目标、路径和第一步压清。").strip()
        reply_options = str(first_action.get("user_reply") or TASK_COPILOT_REPLY_OPTIONS).strip()
        visible_boundary = self.backend._user_visible_human_boundary(str(route.get("human_boundary", "")))
        sections = [
            ("我理解你要做什么", human_summary),
            ("我建议先怎么推进", next_step),
            ("你现在可以怎么回我", visible_boundary or reply_options),
        ]
        return FrontdeskReply(
            scene="task_intake",
            title="原力OS · 任务副驾驶",
            sections=sections,
            run_id=route["run_id"],
            session_id=session.session_id,
            summary=human_summary,
            next_step=next_step,
            human_boundary=visible_boundary,
            verification_status="route_planned",
            metadata={
                "session_update": {
                    "task_text": route["task_text"],
                    "last_user_goal": route["task_text"],
                    "run_id": route["run_id"],
                    "active_run_id": route["run_id"],
                    "produced_evidence": False,
                    "verification_evidence": [],
                    "open_questions": [],
                    "effective_patterns": [],
                    "wasted_patterns": [],
                    "evolution_candidates": ["把高频前端任务入口进一步固化成稳定协议。"],
                    "human_boundary": visible_boundary,
                    "verification_status": "route_planned",
                    "requested_frontdesk_state": "follow_up_requested",
                    "max_distortion": route.get("situation_map", {}).get("当前最大失真", ""),
                }
            },
            footer=build_footer(route["run_id"]),
        )

    def _resume_context_reply(self, session: FrontdeskSessionState) -> FrontdeskReply:
        result = self.backend.resume_context(session)
        status = str(result.get("status", "ok"))
        run_id = str(result.get("run_id", "")).strip()
        if status == "found":
            summary = str(result.get("summary", "当前没有最近上下文。"))
            next_step = str(result.get("next_step", "请重新给我任务。"))
        elif status == "session_only":
            summary = f"我记得你上次在说：{str(result.get('summary', '')).strip() or '最近那件事'}"
            next_step = "我记得目标，但没有稳定 run 证据。把那件事再发一句，我继续接。"
        else:
            summary = "当前还没有可恢复的最近上下文。"
            next_step = "我手里还没有稳定的最近上下文，请把那件事再发一遍。"
        return FrontdeskReply(
            scene="resume_context",
            title="原力OS · 继续上次",
            sections=[
                ("上次在推进什么", summary),
                ("现在卡在哪 / 下一步是什么", next_step),
                ("run id", run_id or "none"),
            ],
            run_id=run_id,
            session_id=session.session_id,
            status=status,
            summary=summary,
            next_step=next_step,
            human_boundary=self.backend._user_visible_human_boundary(str(result.get("human_boundary", ""))),
            verification_status=str(result.get("verification_status", "")),
            metadata={
                "session_update": {
                    "task_text": session.task_text,
                    "last_user_goal": str(result.get("summary", "")).strip() or session.last_user_goal,
                    "run_id": run_id or session.run_id,
                    "active_run_id": run_id or session.active_run_id,
                    "verification_status": str(result.get("verification_status", "")),
                    "requested_frontdesk_state": "resume_requested",
                    "human_boundary": self.backend._user_visible_human_boundary(str(result.get("human_boundary", ""))),
                }
            },
            footer=build_footer(run_id),
        )

    def _my_tasks_reply(self, session: FrontdeskSessionState) -> FrontdeskReply:
        result = self.backend.my_tasks()
        counts = result.get("counts", {})
        return FrontdeskReply(
            scene="my_tasks",
            title="原力OS · 我的任务",
            sections=[
                ("任务总览", str(result.get("summary", "当前没有可展示的任务。"))),
                ("优先列表", self._format_task_items(result.get("tasks", []))),
                ("下一步", str(result.get("next_step", "先发一条新任务。"))),
            ],
            session_id=session.session_id,
            status=str(result.get("status", "ok")),
            summary=str(result.get("summary", "")),
            next_step=str(result.get("next_step", "")),
            human_boundary="任务总表只读展示，重执行仍回后端。",
            verification_status="canonical_tasks_read",
            metadata={
                "session_update": {
                    "verification_status": "canonical_tasks_read",
                    "requested_frontdesk_state": "follow_up_requested",
                    "active_task_ids": [str(item.get("task_id", "")).strip() for item in result.get("tasks", []) if str(item.get("task_id", "")).strip()],
                }
            },
            footer=[f"活跃 {counts.get('active', 0)} / 阻塞 {counts.get('blocked', 0)} / 待你拍板 {counts.get('waiting_for_user', 0)}"],
        )

    def _judgment_reply(self, content: str, user_context: dict[str, Any], session: FrontdeskSessionState) -> FrontdeskReply:
        result = self.backend.judge_task(content, user_context=user_context)
        route = result["route"]
        judgments = result["judgments"]
        next_step = f"如果你认同，就按 {', '.join(route.get('selected_skills', [])) or '当前技能链'} 往下推。"
        return FrontdeskReply(
            scene="judgment",
            title="原力OS · 做判断",
            sections=[
                ("自治判断", judgments.get("自治判断", "")),
                ("全局最优判断", judgments.get("全局最优判断", "")),
                ("当前最大失真", judgments.get("当前最大失真", "")),
            ],
            run_id=route["run_id"],
            session_id=session.session_id,
            summary=str(judgments.get("全局最优判断", "") or judgments.get("自治判断", "")),
            next_step=next_step,
            human_boundary=route.get("human_boundary", ""),
            verification_status="judged_not_executed",
            metadata={
                "session_update": {
                    "task_text": route["task_text"],
                    "last_user_goal": route["task_text"],
                    "run_id": route["run_id"],
                    "active_run_id": route["run_id"],
                    "produced_evidence": False,
                    "verification_evidence": [],
                    "open_questions": [],
                    "effective_patterns": [],
                    "wasted_patterns": [],
                    "evolution_candidates": ["把高频判断题沉淀成更稳定的治理问句模板。"],
                    "human_boundary": route.get("human_boundary", ""),
                    "verification_status": "judged_not_executed",
                    "max_distortion": judgments.get("当前最大失真", ""),
                }
            },
            footer=build_footer(route["run_id"], [f"建议技能链: {', '.join(route.get('selected_skills', [])) or 'none'}"]),
        )

    def _note_capture_reply(self, content: str, user_context: dict[str, Any], session: FrontdeskSessionState) -> FrontdeskReply:
        capture_context = dict(user_context)
        capture_context["__session__"] = session
        result = self.backend.note_capture(content, user_context=capture_context)
        capture_id = str(result.get("capture_id", "")).strip()
        artifact_path = str(result.get("artifact_path", "")).strip()
        summary_path = str(result.get("summary_path", "")).strip()
        run_id = str(result.get("run_id", "")).strip()
        sync_status = str(result.get("sync_status", "")).strip()
        footer = [f"capture id: {capture_id}"] if capture_id else []
        if sync_status:
            footer.append("状态：已记入本地 canonical，未同步到外部知识库。")
        return FrontdeskReply(
            scene="note_capture",
            title="原力OS · 轻记录",
            sections=[
                ("记录摘要", str(result.get("summary", "已记录。"))),
                ("下一步", str(result.get("next_step", "继续搜一下，或把它推进成任务。"))),
            ],
            run_id=run_id,
            session_id=session.session_id,
            status=str(result.get("status", "captured")),
            summary=str(result.get("summary", "")),
            next_step=str(result.get("next_step", "")),
            human_boundary="轻记录只落本地 canonical，不替你直接写第三方笔记。",
            verification_status=str(result.get("verification_status", "captured_canonical")),
            metadata={
                "capture_id": capture_id,
                "artifact_path": artifact_path,
                "summary_path": summary_path,
                "canonical_run_dir": str(result.get("canonical_run_dir", "")).strip(),
                "canonical_ref": str(result.get("canonical_ref", "")).strip(),
                "session_update": {
                    "task_text": session.task_text or str(result.get("content", "")).strip(),
                    "last_user_goal": str(result.get("content", "")).strip() or str(result.get("summary", "")).strip() or session.last_user_goal,
                    "run_id": run_id or session.run_id,
                    "active_run_id": run_id or session.active_run_id or session.run_id,
                    "produced_evidence": True,
                    "verification_evidence": [path for path in [artifact_path, summary_path] if path],
                    "open_questions": ["当前只有轻记录，尚未形成可闭环的完成证据。"],
                    "verification_status": str(result.get("verification_status", "captured_canonical")),
                    "requested_frontdesk_state": "follow_up_requested",
                    "effective_patterns": ["把高频碎片先记进本地 canonical，再决定是否升级成任务或知识查询。"],
                    "evolution_candidates": ["让轻记录命中本地 canonical 后，继续串到更稳定的回查路径。"],
                    "human_boundary": "轻记录只落本地 canonical，不替你直接写第三方笔记。",
                },
            },
            footer=footer,
        )

    def _knowledge_reply(self, content: str, user_context: dict[str, Any], session: FrontdeskSessionState) -> FrontdeskReply:
        result = self.backend.knowledge_lookup(content, user_context=user_context, allow_execute=self.config.allows_p0_execution)
        route = result.get("route", {})
        run_id = str(route.get("run_id") or "")
        verification_status = "evidence_ready" if result.get("produced_evidence", False) else str(result.get("status", "planned"))
        next_step = str(result.get("missing", "继续补原始答案或证据。"))
        return FrontdeskReply(
            scene="knowledge_lookup",
            title="原力OS · 查资料",
            sections=[
                ("我会先查什么来源", str(result.get("source_label", "待判定知识源"))),
                ("我准备给你什么结果", str(result.get("summary", "尚未形成稳定摘要。"))),
                ("现在还缺什么", str(result.get("missing", "none"))),
            ],
            run_id=run_id,
            session_id=session.session_id,
            status=str(result.get("status", "ok")),
            summary=str(result.get("summary", "")),
            next_step=next_step,
            human_boundary=self.backend._user_visible_human_boundary(str(route.get("human_boundary", ""))),
            verification_status=verification_status,
            metadata={
                "session_update": {
                    "task_text": str(route.get("task_text", content)).strip(),
                    "last_user_goal": str(route.get("task_text", content)).strip(),
                    "run_id": run_id,
                    "active_run_id": run_id,
                    "produced_evidence": bool(result.get("produced_evidence", False)),
                    "verification_evidence": result.get("verification_evidence", []),
                    "open_questions": result.get("open_questions", []),
                    "effective_patterns": result.get("effective_patterns", []),
                    "wasted_patterns": result.get("wasted_patterns", []),
                    "evolution_candidates": result.get("evolution_candidates", []),
                    "human_boundary": self.backend._user_visible_human_boundary(str(route.get("human_boundary", ""))),
                    "verification_status": verification_status,
                    "max_distortion": str(route.get("situation_map", {}).get("当前最大失真", "")),
                }
            },
            footer=build_footer(run_id, [f"execution mode: {result.get('execution_mode', 'route_only')}"]),
        )

    def _finance_news_reply(self, content: str, session: FrontdeskSessionState) -> FrontdeskReply:
        result = self.backend.finance_news_search(content)
        return FrontdeskReply(
            scene="finance_news_search",
            title="原力OS · 金融资讯搜索",
            sections=[
                ("事实资讯", self._format_finance_facts(result.get("facts", []))),
                ("我能推到哪一步", str(result.get("inference", "只输出事实与来源，不自动荐股。"))),
                ("现在还缺什么", str(result.get("missing", "")) or "当前结果已经带来源与时间。"),
            ],
            run_id=str(result.get("run_id", "")),
            session_id=session.session_id,
            status=str(result.get("status", "ok")),
            summary=str(result.get("summary", "")),
            next_step="如果你要继续看某个标的的数据，就直接说：查下 xxx 的 PE / PB / 收盘价。",
            human_boundary=str(result.get("human_boundary", "默认不输出结论性荐股判断。")),
            verification_status=str(result.get("verification_status", "")),
            metadata={
                "artifact_path": str(result.get("artifact_path", "")).strip(),
                "session_update": {
                    "task_text": content,
                    "last_user_goal": content,
                    "run_id": str(result.get("run_id", "")).strip(),
                    "active_run_id": str(result.get("run_id", "")).strip(),
                    "produced_evidence": bool(result.get("produced_evidence", False)),
                    "verification_evidence": result.get("verification_evidence", []),
                    "open_questions": result.get("open_questions", []),
                    "effective_patterns": result.get("effective_patterns", []),
                    "wasted_patterns": result.get("wasted_patterns", []),
                    "evolution_candidates": result.get("evolution_candidates", []),
                    "human_boundary": str(result.get("human_boundary", "")),
                    "verification_status": str(result.get("verification_status", "")),
                }
            },
            footer=build_footer(str(result.get("run_id", "")), [f"source: {result.get('source_label', '')}", f"as_of: {result.get('as_of', '')}"]),
        )

    def _finance_data_reply(self, content: str, session: FrontdeskSessionState) -> FrontdeskReply:
        result = self.backend.finance_data_query(content)
        security = result.get("security", {}) if isinstance(result.get("security"), dict) else {}
        security_line = f"{security.get('name', '')}（{security.get('ts_code', '')}）".strip("（）")
        return FrontdeskReply(
            scene="finance_data_query",
            title="原力OS · 金融数据查询",
            sections=[
                ("对象", security_line or "当前还没识别到证券对象。"),
                ("事实数据", self._format_finance_facts(result.get("facts", []))),
                ("现在还缺什么", str(result.get("missing", "")) or "关键字段已返回，并带截至时间。"),
            ],
            run_id=str(result.get("run_id", "")),
            session_id=session.session_id,
            status=str(result.get("status", "ok")),
            summary=str(result.get("summary", "")),
            next_step="如果你要按规则筛选，就直接说：按 PE < 20、营收同比 > 15% 选股。",
            human_boundary=str(result.get("human_boundary", "这是事实数据查询，不自动给投资建议。")),
            verification_status=str(result.get("verification_status", "")),
            metadata={
                "artifact_path": str(result.get("artifact_path", "")).strip(),
                "session_update": {
                    "task_text": content,
                    "last_user_goal": content,
                    "run_id": str(result.get("run_id", "")).strip(),
                    "active_run_id": str(result.get("run_id", "")).strip(),
                    "produced_evidence": bool(result.get("produced_evidence", False)),
                    "verification_evidence": result.get("verification_evidence", []),
                    "open_questions": result.get("open_questions", []),
                    "effective_patterns": result.get("effective_patterns", []),
                    "wasted_patterns": result.get("wasted_patterns", []),
                    "evolution_candidates": result.get("evolution_candidates", []),
                    "human_boundary": str(result.get("human_boundary", "")),
                    "verification_status": str(result.get("verification_status", "")),
                }
            },
            footer=build_footer(str(result.get("run_id", "")), [f"source: {result.get('source_label', '')}", f"as_of: {result.get('as_of', '')}"]),
        )

    def _stock_screen_reply(self, content: str, session: FrontdeskSessionState) -> FrontdeskReply:
        result = self.backend.stock_screen(content)
        sort_fields = ", ".join([str(item) for item in result.get("sort_fields", []) if str(item).strip()]) or "无"
        return FrontdeskReply(
            scene="stock_screen",
            title="原力OS · 智能选股",
            sections=[
                ("命中的规则", "\n".join([f"- {item}" for item in result.get("rules", [])]) or "当前没有解析到规则。"),
                ("筛选结果", self._format_screen_results(result.get("results", []))),
                ("排序字段与边界", f"排序字段：{sort_fields}\n这是显式规则筛选，不代表投资建议。"),
            ],
            run_id=str(result.get("run_id", "")),
            session_id=session.session_id,
            status=str(result.get("status", "ok")),
            summary=str(result.get("summary", "")),
            next_step=str(result.get("missing", "")) or "如果你要缩小范围，可以继续加行业或估值条件。",
            human_boundary=str(result.get("human_boundary", "这是规则筛选工具，不是投顾或自动交易系统。")),
            verification_status=str(result.get("verification_status", "")),
            metadata={
                "artifact_path": str(result.get("artifact_path", "")).strip(),
                "session_update": {
                    "task_text": content,
                    "last_user_goal": content,
                    "run_id": str(result.get("run_id", "")).strip(),
                    "active_run_id": str(result.get("run_id", "")).strip(),
                    "produced_evidence": bool(result.get("produced_evidence", False)),
                    "verification_evidence": result.get("verification_evidence", []),
                    "open_questions": result.get("open_questions", []),
                    "effective_patterns": result.get("effective_patterns", []),
                    "wasted_patterns": result.get("wasted_patterns", []),
                    "evolution_candidates": result.get("evolution_candidates", []),
                    "human_boundary": str(result.get("human_boundary", "")),
                    "verification_status": str(result.get("verification_status", "")),
                }
            },
            footer=build_footer(str(result.get("run_id", "")), [f"source: {result.get('source_label', '')}", f"as_of: {result.get('as_of', '')}"]),
        )

    def _close_loop_reply(self, session: FrontdeskSessionState) -> FrontdeskReply:
        result = self.backend.assess_close_loop(session, allow_execute=self.config.allows_p0_execution)
        run_id = str(result.get("run_id", "")).strip()
        return FrontdeskReply(
            scene="close_loop",
            title="原力OS · 收口",
            sections=[
                ("完成情况", str(result.get("summary", "尚未进入闭环。"))),
                ("验真状态", str(result.get("verification_status", "unknown"))),
                ("next iterate", str(result.get("next_iterate", "继续补证据并保持边界清晰。"))),
            ],
            run_id=run_id,
            session_id=session.session_id,
            status=str(result.get("status", "ok")),
            summary=str(result.get("summary", "")),
            next_step=str(result.get("next_iterate", "")),
            human_boundary=session.pending_human_boundary or session.human_boundary,
            verification_status=str(result.get("verification_status", "unknown")),
            metadata={
                "session_update": {
                    "task_text": session.task_text,
                    "last_user_goal": session.last_user_goal or session.task_text,
                    "run_id": run_id or session.run_id,
                    "active_run_id": run_id or session.active_run_id or session.run_id,
                    "verification_status": str(result.get("verification_status", "unknown")),
                    "requested_frontdesk_state": "close_check_requested",
                    "human_boundary": session.pending_human_boundary or session.human_boundary,
                }
            },
            footer=build_footer(run_id, [str(result.get("missing", ""))]),
        )

    def _handoff_to_pc_reply(self, session: FrontdeskSessionState) -> FrontdeskReply:
        result = self.backend.handoff_to_pc(session)
        run_id = str(result.get("run_id", "")).strip()
        return FrontdeskReply(
            scene="handoff_to_pc",
            title="原力OS · 交给 PC 深工",
            sections=[
                ("为什么切回 PC", str(result.get("summary", "这件事适合在 PC 端继续。"))),
                ("接力点", str(result.get("next_step", "回到 PC 后继续当前任务。"))),
                ("run id", run_id or "none"),
            ],
            run_id=run_id,
            session_id=session.session_id,
            status=str(result.get("status", "ok")),
            summary=str(result.get("summary", "")),
            next_step=str(result.get("next_step", "")),
            human_boundary=str(result.get("human_boundary", "")),
            verification_status=str(result.get("verification_status", "")),
            metadata={
                "session_update": {
                    "task_text": session.task_text,
                    "last_user_goal": session.last_user_goal or session.task_text,
                    "run_id": run_id or session.run_id,
                    "active_run_id": run_id or session.active_run_id or session.run_id,
                    "verification_status": str(result.get("verification_status", "")),
                    "requested_frontdesk_state": "follow_up_requested",
                    "human_boundary": str(result.get("human_boundary", "")),
                }
            },
            footer=build_footer(run_id),
        )

    def _approval_reply(self, content: str, user_context: dict[str, Any], session: FrontdeskSessionState) -> FrontdeskReply:
        result = self.backend.judge_task(content, user_context=user_context)
        route = result["route"]
        situation = route.get("situation_map", {})
        summary = f"由你拍板，AI 负责比较与草案。当前建议路径：{', '.join(route.get('selected_skills', [])) or 'none'}"
        return FrontdeskReply(
            scene="approval",
            title="原力OS · 审批边界",
            sections=[
                ("推荐方案", summary),
                ("不推荐方案", "让 AI 直接处理发布、删除、授权、付款或价值取舍类不可逆动作。"),
                ("为什么现在该由人决定", str(route.get("human_boundary") or situation.get("自治判断") or "这类动作属于明确的人类边界。")),
            ],
            run_id=route["run_id"],
            session_id=session.session_id,
            summary=summary,
            next_step="这一步请你拍板，我继续给比较稿和草案。",
            human_boundary=str(route.get("human_boundary") or situation.get("自治判断") or ""),
            verification_status="human_boundary",
            metadata={
                "session_update": {
                    "task_text": route["task_text"],
                    "last_user_goal": route["task_text"],
                    "run_id": route["run_id"],
                    "active_run_id": route["run_id"],
                    "produced_evidence": False,
                    "verification_evidence": [],
                    "open_questions": [],
                    "effective_patterns": [],
                    "wasted_patterns": [],
                    "evolution_candidates": ["把审批题和判断题的前端协议分得更清楚。"],
                    "human_boundary": route.get("human_boundary", ""),
                    "pending_human_boundary": route.get("human_boundary", ""),
                    "verification_status": "human_boundary",
                    "requested_frontdesk_state": "waiting_for_user",
                    "max_distortion": situation.get("当前最大失真", ""),
                }
            },
            footer=build_footer(route["run_id"]),
        )

    def _today_focus_reply(self, session: FrontdeskSessionState) -> FrontdeskReply:
        result = self.backend.today_focus()
        focus_items = result.get("focus_items", [])
        counts = result.get("counts", {})
        return FrontdeskReply(
            scene="today_focus",
            title="原力OS · 今天最该看什么",
            sections=[
                ("今日总览", str(result.get("summary", "当前没有抓到要优先看的内容。"))),
                ("先看什么", self._format_task_items(focus_items)),
                ("下一步", str(result.get("next_step", "先确认今天最重要的那条目标。"))),
            ],
            session_id=session.session_id,
            status=str(result.get("status", "ok")),
            summary=str(result.get("summary", "")),
            next_step=str(result.get("next_step", "")),
            human_boundary="今天重点来自 canonical 任务与线程，只读展示。",
            verification_status="canonical_focus_read",
            metadata={
                "session_update": {
                    "verification_status": "canonical_focus_read",
                    "requested_frontdesk_state": "follow_up_requested",
                    "active_task_ids": [str(item.get("task_id", "")).strip() for item in focus_items if str(item.get("task_id", "")).strip()],
                }
            },
            footer=[f"活跃 {counts.get('active', 0)} / 阻塞 {counts.get('blocked', 0)} / 待你拍板 {counts.get('waiting_for_user', 0)}"],
        )

    def _project_heartbeat_reply(self, session: FrontdeskSessionState) -> FrontdeskReply:
        result = self.backend.project_heartbeat()
        top_action = result.get("top_action") if isinstance(result.get("top_action"), dict) else {}
        top_boundary = result.get("top_human_boundary") if isinstance(result.get("top_human_boundary"), dict) else {}
        recent_actions = result.get("recent_actions") if isinstance(result.get("recent_actions"), list) else []
        action_lines = [f"- [{item.get('kind', 'watch')}] {item.get('summary', '')}" for item in recent_actions[:3] if isinstance(item, dict)]
        if not action_lines:
            action_lines = ["- 当前没有新增催办，小猫 保持静默巡检。"]
        boundary_summary = str(top_boundary.get("title") or "当前没有需要你立刻拍板的事项。")
        if str(top_boundary.get("reason") or "").strip():
            boundary_summary = f"{boundary_summary}｜{top_boundary.get('reason')}"
        return FrontdeskReply(
            scene="project_heartbeat",
            title="原力OS · 小猫项目推进",
            sections=[
                ("本小时总判断", str(result.get("summary", "小猫 还没开始巡检。"))),
                ("最该推进的 1 件事", str(top_action.get("summary") or result.get("next_step") or "当前没有 top action。")),
                ("最该你拍板的 1 件事", boundary_summary),
                ("本小时已自动催办 / 已记录的动作", "\n".join(action_lines)),
                ("当前最大失真", str(result.get("current_max_distortion", "暂无"))),
            ],
            run_id=str(result.get("run_id", "")),
            session_id=session.session_id,
            status=str(result.get("status", "ok")),
            summary=str(result.get("summary", "")),
            next_step=str(result.get("next_step", "")),
            human_boundary=boundary_summary if top_boundary else "当前没有额外的人类边界升级。",
            verification_status=str(result.get("verification_status", "heartbeat_round_read")),
            metadata={
                "artifact_root": str(result.get("artifact_root", "")),
                "session_update": {
                    "verification_status": str(result.get("verification_status", "heartbeat_round_read")),
                    "requested_frontdesk_state": "follow_up_requested",
                    "human_boundary": boundary_summary if top_boundary else session.human_boundary,
                },
            },
            footer=build_footer(str(result.get("run_id", ""))),
        )

    def _dispatch_scene_reply(
        self,
        scene: str,
        content: str,
        user_context: dict[str, Any],
        session: FrontdeskSessionState,
    ) -> FrontdeskReply:
        if scene == "home":
            return self._home_reply(session.session_id)
        if scene == "judgment":
            return self._judgment_reply(content, user_context, session)
        if scene == "note_capture":
            return self._note_capture_reply(content, user_context, session)
        if scene == "knowledge_lookup":
            return self._knowledge_reply(content, user_context, session)
        if scene == "finance_news_search":
            return self._finance_news_reply(content, session)
        if scene == "finance_data_query":
            return self._finance_data_reply(content, session)
        if scene == "stock_screen":
            return self._stock_screen_reply(content, session)
        if scene == "close_loop":
            return self._close_loop_reply(session)
        if scene == "approval":
            return self._approval_reply(content, user_context, session)
        if scene == "today_focus":
            return self._today_focus_reply(session)
        if scene == "project_heartbeat":
            return self._project_heartbeat_reply(session)
        if scene == "my_tasks":
            return self._my_tasks_reply(session)
        if scene == "resume_context":
            return self._resume_context_reply(session)
        if scene == "handoff_to_pc":
            return self._handoff_to_pc_reply(session)
        return self._task_intake_reply(content, user_context, session)

    def _detect_frontdesk_bundle_requests(self, content: str) -> list[tuple[str, str, bool]]:
        normalized_lines = [normalize_frontdesk_line(line) for line in str(content or "").splitlines()]
        lines = [(line, wake_used) for line, wake_used in normalized_lines if line]
        if len(lines) < 2:
            return []

        requests: list[tuple[str, str, bool]] = []
        seen: set[str] = set()
        for line, wake_used in lines:
            scene = classify_frontdesk_scene(line, self._detect_signals(line), wake_used=wake_used)
            if scene not in BUNDLABLE_FRONTDESK_SCENES or scene in seen:
                continue
            requests.append((scene, line, wake_used))
            seen.add(scene)
        if len(requests) < 2:
            return []
        return requests

    @staticmethod
    def _bundle_section_content(reply: FrontdeskReply) -> str:
        parts: list[str] = []
        if reply.summary:
            parts.append(reply.summary)
        elif reply.sections:
            parts.append(reply.sections[0][1])
        if reply.next_step:
            parts.append(f"下一步：{reply.next_step}")
        if not parts and reply.run_id:
            parts.append(f"run id：{reply.run_id}")
        if not parts and reply.verification_status:
            parts.append(f"状态：{reply.verification_status}")
        return "\n".join(parts).strip()

    def _bundle_reply(
        self,
        requests: list[tuple[str, str, bool]],
        content: str,
        user_context: dict[str, Any],
        session: FrontdeskSessionState,
    ) -> FrontdeskReply:
        sub_replies = [self._dispatch_scene_reply(scene, line, user_context, session) for scene, line, _wake_used in requests]
        sections = [
            (f"{index}. {reply.title.replace('AI大管家 · ', '').replace('原力OS · ', '')}", self._bundle_section_content(reply))
            for index, reply in enumerate(sub_replies, start=1)
        ]
        active_task_ids: list[str] = []
        run_id = ""
        human_boundary = ""
        produced_evidence = False
        verification_evidence: list[str] = []
        open_questions: list[str] = []
        effective_patterns: list[str] = []
        wasted_patterns: list[str] = []
        evolution_candidates: list[str] = []
        for reply in sub_replies:
            update = reply.metadata.get("session_update")
            if isinstance(update, dict):
                active_task_ids.extend([str(item).strip() for item in update.get("active_task_ids", []) if str(item).strip()])
                verification_evidence.extend([str(item).strip() for item in update.get("verification_evidence", []) if str(item).strip()])
                open_questions.extend([str(item).strip() for item in update.get("open_questions", []) if str(item).strip()])
                effective_patterns.extend([str(item).strip() for item in update.get("effective_patterns", []) if str(item).strip()])
                wasted_patterns.extend([str(item).strip() for item in update.get("wasted_patterns", []) if str(item).strip()])
                evolution_candidates.extend([str(item).strip() for item in update.get("evolution_candidates", []) if str(item).strip()])
                produced_evidence = produced_evidence or bool(update.get("produced_evidence", False))
            run_id = run_id or reply.run_id
            human_boundary = human_boundary or reply.human_boundary
        dedup_task_ids = list(dict.fromkeys(active_task_ids))
        dedup_verification_evidence = list(dict.fromkeys(verification_evidence))
        next_step = "如果你要继续，就单独发其中一条，我按那条往下深推。"
        return FrontdeskReply(
            scene="frontdesk_bundle",
            title="原力OS · 多条前台请求",
            sections=sections,
            run_id=run_id,
            session_id=session.session_id,
            status="ok",
            summary=f"已一次处理 {len(sub_replies)} 条前台请求。",
            next_step=next_step,
            human_boundary=human_boundary,
            verification_status="bundle_processed",
            metadata={
                "session_update": {
                    "task_text": session.task_text,
                    "last_user_goal": content.strip(),
                    "run_id": run_id or session.run_id,
                    "active_run_id": run_id or session.active_run_id or session.run_id,
                    "active_task_ids": dedup_task_ids or session.active_task_ids,
                    "produced_evidence": produced_evidence or session.produced_evidence,
                    "verification_evidence": dedup_verification_evidence or session.verification_evidence,
                    "open_questions": list(dict.fromkeys(open_questions)) or session.open_questions,
                    "effective_patterns": list(dict.fromkeys(effective_patterns)) or session.effective_patterns,
                    "wasted_patterns": list(dict.fromkeys(wasted_patterns)) or session.wasted_patterns,
                    "evolution_candidates": list(dict.fromkeys(evolution_candidates)) or session.evolution_candidates,
                    "verification_status": "bundle_processed",
                    "requested_frontdesk_state": "follow_up_requested",
                    "human_boundary": human_boundary or session.human_boundary,
                }
            },
            footer=["提示：一次发多条前台指令时，我会按顺序给你压缩回答。"],
        )

    def reply_to_frontdesk(self, content: str, user_context: dict[str, Any] | None = None) -> FrontdeskReply:
        context = user_context or {}
        session = self._session_from_context(context)
        bundle_requests = self._detect_frontdesk_bundle_requests(content)
        if bundle_requests:
            reply = self._bundle_reply(bundle_requests, content, context, session)
        else:
            normalized_content, wake_used = normalize_frontdesk_line(content)
            scene = classify_frontdesk_scene(normalized_content, self._detect_signals(normalized_content), wake_used=wake_used)
            reply = self._dispatch_scene_reply(scene, normalized_content, context, session)
        reply.session_id = reply.session_id or session.session_id
        self._update_session(context, reply)
        return reply

    def handle_event(self, payload: dict[str, Any], headers: dict[str, str], raw_body: bytes) -> tuple[int, dict[str, Any]]:
        if payload.get("type") == "url_verification":
            return HTTPStatus.OK, {"challenge": payload.get("challenge", "")}

        self.verifier.verify(payload, headers, raw_body)
        header = payload.get("header") or {}
        event_type = header.get("event_type") or payload.get("type") or ""
        event_id = header.get("event_id") or ""

        if event_id and self.idempotency_store.seen(event_id):
            return HTTPStatus.OK, {"code": 0, "msg": "duplicate event ignored"}

        if event_type != "im.message.receive_v1":
            return HTTPStatus.OK, {"code": 0, "msg": f"ignored unsupported event_type={event_type}"}

        event = payload.get("event") or {}
        message = event.get("message") or {}
        sender = event.get("sender") or {}
        chat_id = str(message.get("chat_id", "")).strip()
        if not chat_id:
            return HTTPStatus.BAD_REQUEST, {"code": 400, "msg": "missing chat_id"}

        content = self._extract_text(message)
        if not content:
            self.messenger.send_text_to_chat(chat_id, "当前只支持文本消息，请直接发送任务描述。")
            return HTTPStatus.OK, {"code": 0, "msg": "non-text message handled"}

        user_context = {
            "chat_id": chat_id,
            "message_id": message.get("message_id", ""),
            "open_id": ((sender.get("sender_id") or {}).get("open_id", "")),
            "tenant_key": header.get("tenant_key", ""),
            "event_source": event_type,
            "event_id": event_id,
        }
        if event_id:
            self.idempotency_store.mark(
                event_id,
                {
                    "owner": self._runtime_owner(),
                    "heartbeat_at": iso_now(),
                    "event_source": event_type,
                    "chat_id": chat_id,
                    "message_id": str(message.get("message_id", "")).strip(),
                },
            )
        reply = self.reply_to_frontdesk(content, user_context=user_context)
        delivered_reply = self._decorate_reply_for_delivery(reply)
        self.messenger.send_text_to_chat(chat_id, delivered_reply.as_text())
        self._send_card_response(user_context, delivered_reply)
        return HTTPStatus.OK, {
            "code": 0,
            "msg": "ok",
            "scene": reply.scene,
            "run_id": reply.run_id,
            "session_id": reply.session_id,
            "status": reply.status,
        }

    @staticmethod
    def _extract_text(message: dict[str, Any]) -> str:
        message_type = str(message.get("message_type", "")).strip()
        raw_content = message.get("content", "{}")
        if isinstance(raw_content, (dict, list)):
            content = raw_content
        else:
            try:
                content = json.loads(raw_content or "{}")
            except (TypeError, json.JSONDecodeError):
                return ""

        if message_type == "text":
            return str((content or {}).get("text", "")).strip()
        if message_type == "post":
            return FeishuClawBridgeService._extract_post_text(content)
        return FeishuClawBridgeService._extract_nested_text(content)

    @staticmethod
    def _extract_post_text(content: dict[str, Any]) -> str:
        language_blocks: list[dict[str, Any]] = []
        if isinstance(content, dict):
            if isinstance(content.get("zh_cn"), dict):
                language_blocks.append(content.get("zh_cn") or {})
            language_blocks.extend(
                value for key, value in content.items() if key != "zh_cn" and isinstance(value, dict)
            )

        lines: list[str] = []
        for block in language_blocks:
            rows = block.get("content") or []
            if not isinstance(rows, list):
                continue
            for row in rows:
                row_text = FeishuClawBridgeService._extract_nested_text(row)
                if row_text:
                    lines.append(row_text)
        return "\n".join([line for line in lines if line]).strip()

    @staticmethod
    def _extract_nested_text(value: Any) -> str:
        parts: list[str] = []

        def walk(node: Any) -> None:
            if isinstance(node, str):
                text = node.strip()
                if text:
                    parts.append(text)
                return
            if isinstance(node, list):
                for item in node:
                    walk(item)
                return
            if not isinstance(node, dict):
                return

            tag = str(node.get("tag", "")).strip()
            if tag == "text":
                text = str(node.get("text", "")).strip()
                if text:
                    parts.append(text)
                return
            if tag == "a":
                text = str(node.get("text", "")).strip() or str(node.get("href", "")).strip()
                if text:
                    parts.append(text)
                return
            if tag == "at":
                text = str(node.get("user_name", "")).strip() or str(node.get("text", "")).strip()
                if text:
                    parts.append(text)
                return
            if "text" in node and isinstance(node.get("text"), str):
                text = str(node.get("text", "")).strip()
                if text:
                    parts.append(text)
            for item in node.values():
                if isinstance(item, (dict, list)):
                    walk(item)

        walk(value)
        return "\n".join(parts).strip()


class BridgeHTTPRequestHandler(BaseHTTPRequestHandler):
    server_version = "AiDaGuanJiaFeishuBridge/0.1"

    @property
    def bridge(self) -> FeishuClawBridgeService:
        return self.server.bridge_service  # type: ignore[attr-defined]

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib_parse.urlsplit(self.path)
        path = parsed.path
        query = urllib_parse.parse_qs(parsed.query)

        if path == "/healthz":
            self._write_json(HTTPStatus.OK, {"ok": True, "service": "feishu_claw_bridge"})
            return

        if path == "/bundle/install-prompt":
            self._write_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "install_prompt": render_install_prompt(),
                    "install_source": resolve_bundle_source(),
                },
            )
            return

        if path == "/bundle/metadata":
            verify_runtime = query.get("verify_runtime", ["false"])[0].lower() == "true"
            self._write_json(HTTPStatus.OK, {"ok": True, "result": self.bridge.bundle_metadata(verify_runtime=verify_runtime)})
            return

        if path == "/tools/list_frontdesk_capabilities":
            verify_runtime = query.get("verify_runtime", ["false"])[0].lower() == "true"
            self._write_json(HTTPStatus.OK, {"ok": True, "result": self.bridge.bundle_metadata(verify_runtime=verify_runtime)})
            return

        if path == "/tools/get_run_status":
            run_id = str(query.get("run_id", [""])[0]).strip()
            if not run_id:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "run_id is required"})
                return
            self._write_json(HTTPStatus.OK, {"ok": True, "result": self.bridge.backend.get_run_status(run_id)})
            return

        if path == "/tools/runtime_diagnostics":
            limit = int(str(query.get("limit", ["5"])[0]).strip() or "5")
            chat_id = str(query.get("chat_id", [""])[0]).strip()
            session_id = str(query.get("session_id", [""])[0]).strip()
            self._write_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "result": self.bridge.runtime_diagnostics(chat_id=chat_id, session_id=session_id, limit=limit),
                },
            )
            return

        if path != "/healthz":
            self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
            return

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length)
        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid json body"})
            return

        if self.path == "/feishu/events":
            try:
                status, response = self.bridge.handle_event(payload, self._normalized_headers(), raw_body)
            except PermissionError as exc:
                self._write_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": str(exc)})
                return
            except Exception as exc:  # pragma: no cover
                self._write_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
                return
            self._write_json(status, response)
            return

        if self.path == "/tools/route_task":
            input_text = str(payload.get("input_text", "")).strip()
            if not input_text:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "input_text is required"})
                return
            result = self.bridge.backend.route_task(input_text, user_context=payload.get("user_context"))
            self._write_json(HTTPStatus.OK, {"ok": True, "result": result})
            return

        if self.path == "/tools/frontdesk_reply":
            input_text = str(payload.get("input_text", "")).strip()
            if not input_text:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "input_text is required"})
                return
            reply = self.bridge.reply_to_frontdesk(input_text, user_context=payload.get("user_context") or {})
            self._write_json(HTTPStatus.OK, {"ok": True, "result": reply.to_dict()})
            return

        if self.path == "/tools/ask_knowledge":
            input_text = str(payload.get("input_text", "")).strip()
            if not input_text:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "input_text is required"})
                return
            result = self.bridge.backend.knowledge_lookup(
                input_text,
                user_context=payload.get("user_context"),
                allow_execute=bool(payload.get("allow_execute", False)),
            )
            self._write_json(HTTPStatus.OK, {"ok": True, "result": result})
            return

        if self.path == "/tools/finance_news_search":
            input_text = str(payload.get("input_text", "")).strip()
            if not input_text:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "input_text is required"})
                return
            result = self.bridge.backend.finance_news_search(
                input_text,
                limit=int(str(payload.get("limit", 5)).strip() or "5"),
                days=int(str(payload.get("days", 1)).strip() or "1"),
            )
            self._write_json(HTTPStatus.OK, {"ok": True, "result": result})
            return

        if self.path == "/tools/finance_data_query":
            input_text = str(payload.get("input_text", "")).strip()
            if not input_text:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "input_text is required"})
                return
            result = self.bridge.backend.finance_data_query(input_text)
            self._write_json(HTTPStatus.OK, {"ok": True, "result": result})
            return

        if self.path == "/tools/stock_screen":
            input_text = str(payload.get("input_text", "")).strip()
            if not input_text:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "input_text is required"})
                return
            result = self.bridge.backend.stock_screen(
                input_text,
                limit=int(str(payload.get("limit", 10)).strip() or "10"),
            )
            self._write_json(HTTPStatus.OK, {"ok": True, "result": result})
            return

        if self.path == "/tools/close_task":
            session_state = payload.get("session_state")
            if session_state:
                state = self.bridge._session_from_payload(session_state)
            else:
                user_context = payload.get("user_context") if isinstance(payload.get("user_context"), dict) else {}
                if not user_context and payload.get("chat_id"):
                    user_context = {"chat_id": str(payload.get("chat_id", "")).strip()}
                state = self.bridge._session_from_context(user_context)
            result = self.bridge.backend.assess_close_loop(state, allow_execute=bool(payload.get("allow_execute", False)))
            self._write_json(HTTPStatus.OK, {"ok": True, "result": result})
            return

        if self.path == "/tools/get_run_status":
            run_id = str(payload.get("run_id", "")).strip()
            if not run_id:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "run_id is required"})
                return
            self._write_json(HTTPStatus.OK, {"ok": True, "result": self.bridge.backend.get_run_status(run_id)})
            return

        if self.path == "/tools/list_frontdesk_capabilities":
            verify_runtime = bool(payload.get("verify_runtime", False))
            self._write_json(HTTPStatus.OK, {"ok": True, "result": self.bridge.bundle_metadata(verify_runtime=verify_runtime)})
            return

        if self.path == "/tools/runtime_diagnostics":
            limit = int(str(payload.get("limit", 5)).strip() or "5")
            result = self.bridge.runtime_diagnostics(
                chat_id=str(payload.get("chat_id", "")).strip(),
                session_id=str(payload.get("session_id", "")).strip(),
                limit=limit,
            )
            self._write_json(HTTPStatus.OK, {"ok": True, "result": result})
            return

        if self.path == "/tools/suggest_human_decision":
            context = str(payload.get("context", "") or payload.get("input_text", "")).strip()
            if not context:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "context is required"})
                return
            result = self.bridge.backend.suggest_human_decision(context, user_context=payload.get("user_context"))
            self._write_json(HTTPStatus.OK, {"ok": True, "result": result})
            return

        self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _normalized_headers(self) -> dict[str, str]:
        return {key.lower(): value for key, value in self.headers.items()}

    def _write_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json_dumps(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(args: argparse.Namespace) -> int:
    config = BridgeConfig.from_env()
    service = FeishuClawBridgeService(config)
    server = ThreadingHTTPServer((args.host, args.port), BridgeHTTPRequestHandler)
    server.bridge_service = service  # type: ignore[attr-defined]
    print(f"listening: http://{args.host}:{args.port}")
    print("healthz: /healthz")
    print("events: /feishu/events")
    print("frontdesk_reply: /tools/frontdesk_reply")
    print("bundle_metadata: /bundle/metadata")
    print("install_prompt: /bundle/install-prompt")
    print(f"execution_mode: {config.execution_mode}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def auth_check(args: argparse.Namespace) -> int:
    del args
    config = BridgeConfig.from_env()
    service = FeishuClawBridgeService(config)
    result = service.auth_check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def route_task_command(args: argparse.Namespace) -> int:
    backend = AiDaGuanJiaBackend(persist_route=True)
    result = backend.route_task(args.input_text, user_context={"surface": "cli"})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def install_prompt_command(args: argparse.Namespace) -> int:
    del args
    print(render_install_prompt())
    return 0


def bundle_metadata_command(args: argparse.Namespace) -> int:
    config = BridgeConfig(
        app_id=os.getenv("FEISHU_APP_ID", "preview-app"),
        app_secret=os.getenv("FEISHU_APP_SECRET", "preview-secret"),
    )
    service = FeishuClawBridgeService(config, auth_client=FeishuAuthClient(config))
    result = service.bundle_metadata(verify_runtime=args.verify_runtime)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def bundle_status_command(args: argparse.Namespace) -> int:
    config = BridgeConfig(
        app_id=os.getenv("FEISHU_APP_ID", "preview-app"),
        app_secret=os.getenv("FEISHU_APP_SECRET", "preview-secret"),
    )
    service = FeishuClawBridgeService(config, auth_client=FeishuAuthClient(config))
    result = service.bundle_status(verify_runtime=args.verify_runtime)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def run_status_command(args: argparse.Namespace) -> int:
    backend = AiDaGuanJiaBackend(persist_route=False)
    result = backend.get_run_status(args.run_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def runtime_diagnostics_command(args: argparse.Namespace) -> int:
    config = BridgeConfig(
        app_id=os.getenv("FEISHU_APP_ID", "preview-app"),
        app_secret=os.getenv("FEISHU_APP_SECRET", "preview-secret"),
        execution_mode=os.getenv("AI_DA_GUAN_JIA_FEISHU_EXECUTION_MODE", "route_only"),
        send_cards=os.getenv("AI_DA_GUAN_JIA_FEISHU_SEND_CARDS", "false").lower() == "true",
        instance_tag=os.getenv("AI_DA_GUAN_JIA_FEISHU_INSTANCE_TAG", "").strip(),
    )
    service = FeishuClawBridgeService(config, auth_client=FeishuAuthClient(config))
    result = service.runtime_diagnostics(chat_id=args.chat_id, session_id=args.session_id, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def reply_preview_command(args: argparse.Namespace) -> int:
    config = BridgeConfig(
        app_id="preview-app",
        app_secret="preview-secret",
        execution_mode=args.execution_mode,
        send_cards=True,
    )
    service = FeishuClawBridgeService(config, auth_client=None, messenger=None)
    reply = service.reply_to_frontdesk(args.input_text, user_context={"chat_id": "cli-preview", "surface": "cli"})
    print(json.dumps(reply.to_dict(), ensure_ascii=False, indent=2))
    return 0


def finance_news_command(args: argparse.Namespace) -> int:
    backend = AiDaGuanJiaBackend(persist_route=False)
    result = backend.finance_news_search(args.input_text, limit=args.limit, days=args.days)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def finance_data_command(args: argparse.Namespace) -> int:
    backend = AiDaGuanJiaBackend(persist_route=False)
    result = backend.finance_data_query(args.input_text)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def stock_screen_command(args: argparse.Namespace) -> int:
    backend = AiDaGuanJiaBackend(persist_route=False)
    result = backend.stock_screen(args.input_text, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def serve_longconn(args: argparse.Namespace) -> int:
    del args
    if lark is None:
        raise RuntimeError("Missing optional dependency `lark-oapi`. Install it before starting long connection mode.")

    config = BridgeConfig.from_env()
    service = FeishuClawBridgeService(config)

    print("transport: long_connection")
    print("surface: 原力OS")
    print(f"app_id: {config.app_id}")
    print(f"execution_mode: {config.execution_mode}")
    if config.instance_tag:
        print(f"instance_tag: {config.instance_tag}")
    print("event: im.message.receive_v1")
    print("status: connecting")

    def on_receive(data: Any) -> None:
        payload = coerce_longconn_event_payload(data, default_event_type="im.message.receive_v1")
        raw_body = json_dumps(payload)
        status, result = service.handle_event(payload, {}, raw_body)
        event = payload.get("event") or {}
        message = event.get("message") or {}
        text_preview = ""
        try:
            if str(message.get("message_type", "")).strip() == "text":
                text_preview = str(json.loads(message.get("content", "{}")).get("text", "")).strip()
        except json.JSONDecodeError:
            text_preview = ""
        summary = {
            "transport": "long_connection",
            "status_code": int(status),
            "event_type": ((payload.get("header") or {}).get("event_type", "")),
            "event_id": ((payload.get("header") or {}).get("event_id", "")),
            "chat_id": str(message.get("chat_id", "")).strip(),
            "message_type": str(message.get("message_type", "")).strip(),
            "text_preview": text_preview,
            "scene": result.get("scene", ""),
            "run_id": result.get("run_id", ""),
            "session_id": result.get("session_id", ""),
            "result_status": result.get("status", ""),
            "msg": result.get("msg", ""),
        }
        print(json.dumps(summary, ensure_ascii=False))

    def on_ignored(event_type: str):
        def handler(data: Any) -> None:
            payload = coerce_longconn_event_payload(data, default_event_type=event_type)
            summary = {
                "transport": "long_connection",
                "event_type": event_type,
                "event_id": ((payload.get("header") or {}).get("event_id", "")),
                "status": "ignored",
            }
            print(json.dumps(summary, ensure_ascii=False))

        return handler

    builder = lark.EventDispatcherHandler.builder("", "", lark.LogLevel.INFO)
    builder.register_p2_im_message_receive_v1(on_receive)
    builder.register_p2_im_message_reaction_created_v1(on_ignored("im.message.reaction.created_v1"))
    builder.register_p2_im_message_reaction_deleted_v1(on_ignored("im.message.reaction.deleted_v1"))
    client = lark.ws.Client(
        config.app_id,
        config.app_secret,
        log_level=lark.LogLevel.INFO,
        event_handler=builder.build(),
    )
    client.start()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Feishu Claw bridge for AI大管家.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve", help="Start the webhook server.")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8787)
    serve_parser.set_defaults(func=serve)

    longconn_parser = subparsers.add_parser("serve-longconn", help="Start the Feishu long connection client.")
    longconn_parser.set_defaults(func=serve_longconn)

    auth_parser = subparsers.add_parser("auth-check", help="Validate tenant_access_token retrieval.")
    auth_parser.set_defaults(func=auth_check)

    route_parser = subparsers.add_parser("route-task", help="Run the local AI大管家 router and persist route artifacts.")
    route_parser.add_argument("--input-text", required=True)
    route_parser.set_defaults(func=route_task_command)

    install_parser = subparsers.add_parser("install-prompt", help="Render the OpenClaw install prompt for AI大管家.")
    install_parser.set_defaults(func=install_prompt_command)

    metadata_parser = subparsers.add_parser("bundle-metadata", help="Show install bundle metadata and capability contracts.")
    metadata_parser.add_argument("--verify-runtime", action="store_true")
    metadata_parser.set_defaults(func=bundle_metadata_command)

    status_parser = subparsers.add_parser("bundle-status", help="Show install/configuration/verification status.")
    status_parser.add_argument("--verify-runtime", action="store_true")
    status_parser.set_defaults(func=bundle_status_command)

    run_status_parser = subparsers.add_parser("run-status", help="Read a persisted AI大管家 run bundle by run id.")
    run_status_parser.add_argument("--run-id", required=True)
    run_status_parser.set_defaults(func=run_status_command)

    runtime_parser = subparsers.add_parser("runtime-diagnostics", help="Inspect runtime owner, recent sessions, and recent event ownership.")
    runtime_parser.add_argument("--chat-id", default="")
    runtime_parser.add_argument("--session-id", default="")
    runtime_parser.add_argument("--limit", type=int, default=5)
    runtime_parser.set_defaults(func=runtime_diagnostics_command)

    reply_parser = subparsers.add_parser("reply-preview", help="Preview the structured frontdesk reply for one message.")
    reply_parser.add_argument("--input-text", required=True)
    reply_parser.add_argument("--execution-mode", default="route_only", choices=["route_only", "p0_assist", "p1_assist"])
    reply_parser.set_defaults(func=reply_preview_command)

    finance_news_parser = subparsers.add_parser("finance-news", help="Search finance news with source + timestamp boundaries.")
    finance_news_parser.add_argument("--input-text", required=True)
    finance_news_parser.add_argument("--limit", type=int, default=5)
    finance_news_parser.add_argument("--days", type=int, default=1)
    finance_news_parser.set_defaults(func=finance_news_command)

    finance_data_parser = subparsers.add_parser("finance-data", help="Query market/fundamental data for a stock, index, fund, or sector.")
    finance_data_parser.add_argument("--input-text", required=True)
    finance_data_parser.set_defaults(func=finance_data_command)

    stock_screen_parser = subparsers.add_parser("stock-screen", help="Run explainable rule-based stock screening.")
    stock_screen_parser.add_argument("--input-text", required=True)
    stock_screen_parser.add_argument("--limit", type=int, default=10)
    stock_screen_parser.set_defaults(func=stock_screen_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
