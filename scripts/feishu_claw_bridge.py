#!/usr/bin/env python3
"""Feishu bot bridge for AI大管家.

This bridge treats Feishu as the frontend surface and reuses the local
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
import sys
import time
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request


PROJECT_ROOT = Path(__file__).resolve().parent.parent
AI_DA_GUAN_JIA_SCRIPT = PROJECT_ROOT / "work" / "ai-da-guan-jia" / "scripts" / "ai_da_guan_jia.py"
DISTRIBUTION_ROOT = PROJECT_ROOT / "distribution" / "ai-da-guan-jia-openclaw"
DISTRIBUTION_CAPABILITIES_PATH = DISTRIBUTION_ROOT / "capabilities.json"
DISTRIBUTION_CREDENTIALS_PATH = DISTRIBUTION_ROOT / "credentials.example.json"
DISTRIBUTION_INSTALL_PROMPT_TEMPLATE = DISTRIBUTION_ROOT / "install-prompt.template.txt"
FRONTEND_GUIDE_PATH = PROJECT_ROOT / "docs" / "ai-da-guan-jia-openclaw-package.md"
USER_AGENT = "ai-da-guan-jia-feishu-bridge/0.1"
HOME_ENTRIES = [
    {"name": "给我接个任务", "scene": "task_intake", "wave": "P0", "prompt": "帮我研究飞书 claw 接入"},
    {"name": "帮我查资料", "scene": "knowledge_lookup", "wave": "P0", "prompt": "帮我查飞书知识库里关于客户分层的结论"},
    {"name": "帮我做判断", "scene": "judgment", "wave": "P0", "prompt": "这件事该不该做"},
    {"name": "帮我收个口", "scene": "close_loop", "wave": "P0", "prompt": "把这事闭环"},
    {"name": "今天最该看什么", "scene": "today_focus", "wave": "P1", "prompt": "今天最该看什么"},
]
HOME_KEYWORDS = ["首页", "菜单", "帮助", "help", "能做什么", "可以做什么", "入口", "home", "start"]
TODAY_FOCUS_KEYWORDS = ["今天最该看什么", "今天该看什么", "今日重点", "daily focus", "morning review", "治理巡检"]
CLOSE_LOOP_KEYWORDS = ["闭环", "收口", "收尾", "结案", "复盘", "close task", "close it"]
APPROVAL_KEYWORDS = ["审批", "批准", "批不批", "要不要发", "要不要发布", "要不要删", "要不要授权", "要不要付款", "你建议我选哪个", "该选哪个"]
KNOWLEDGE_KEYWORDS = ["查资料", "查飞书知识库", "ask.feishu", "aily", "get笔记", "得到笔记", "逐字稿", "召回", "找那条笔记", "知识库"]
JUDGMENT_KEYWORDS = ["该不该", "先做哪条", "优先级", "值不值得", "怎么判断", "怎么取舍", "风险", "判断一下"]
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
    status: str = "ok"
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
            "status": self.status,
            "metadata": self.metadata,
        }


@dataclass
class FrontdeskSessionState:
    scene: str = ""
    task_text: str = ""
    run_id: str = ""
    produced_evidence: bool = False
    verification_evidence: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    effective_patterns: list[str] = field(default_factory=list)
    wasted_patterns: list[str] = field(default_factory=list)
    evolution_candidates: list[str] = field(default_factory=list)
    human_boundary: str = ""
    max_distortion: str = ""


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


def classify_frontdesk_scene(text: str, signals: dict[str, bool]) -> str:
    normalized = normalize_text(text)
    if not normalized or text_has_any(normalized, HOME_KEYWORDS):
        return "home"
    if text_has_any(normalized, TODAY_FOCUS_KEYWORDS):
        return "today_focus"
    if text_has_any(normalized, CLOSE_LOOP_KEYWORDS):
        return "close_loop"
    if signals.get("hard_boundary") or text_has_any(normalized, APPROVAL_KEYWORDS):
        return "approval"
    if signals.get("get_biji") or signals.get("feishu_km") or signals.get("knowledge_first") or text_has_any(normalized, KNOWLEDGE_KEYWORDS):
        return "knowledge_lookup"
    if text_has_any(normalized, JUDGMENT_KEYWORDS):
        return "judgment"
    return "task_intake"


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


def load_distribution_metadata() -> dict[str, Any]:
    if DISTRIBUTION_CAPABILITIES_PATH.exists():
        return json.loads(DISTRIBUTION_CAPABILITIES_PATH.read_text(encoding="utf-8"))
    return {
        "bundle_id": "ai-da-guan-jia-openclaw",
        "display_name": "AI大管家",
        "short_description": "接任务、做判断、查知识、收口闭环的治理前台能力包",
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

    overall_status = "not_installed"
    if bundle_exists:
        overall_status = "已安装但未配置"
    if bundle_exists and feishu_configured:
        overall_status = "已配置但未验真"
    if bundle_exists and feishu_verified:
        overall_status = "已验真可用"

    return {
        "bundle_id": metadata.get("bundle_id", "ai-da-guan-jia-openclaw"),
        "install_source": resolve_bundle_source(),
        "overall_status": overall_status,
        "components": [
            {
                "id": "bundle",
                "label": "安装包",
                "required": True,
                "status": "present" if bundle_exists else "missing",
                "details": str(DISTRIBUTION_ROOT),
            },
            {
                "id": "feishu_bot",
                "label": "飞书机器人凭证",
                "required": True,
                "status": "verified" if feishu_verified else ("configured" if feishu_configured else "missing"),
                "details": "FEISHU_APP_ID / FEISHU_APP_SECRET",
            },
            {
                "id": "get_biji_api",
                "label": "Get笔记 API",
                "required": False,
                "status": "configured" if get_biji_configured else "missing",
                "details": "GET_BIJI_API_KEY / GET_BIJI_TOPIC_ID",
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
    def __init__(self, ttl_seconds: int = 3600):
        self.ttl_seconds = ttl_seconds
        self._events: dict[str, float] = {}

    def seen(self, event_id: str) -> bool:
        self._prune()
        return event_id in self._events

    def mark(self, event_id: str) -> None:
        self._prune()
        self._events[event_id] = time.time()

    def _prune(self) -> None:
        threshold = time.time() - self.ttl_seconds
        expired = [event_id for event_id, ts in self._events.items() if ts < threshold]
        for event_id in expired:
            self._events.pop(event_id, None)


class AiDaGuanJiaBackend:
    def __init__(self, *, persist_route: bool = True):
        self.module = load_ai_da_guan_jia_module()
        self.persist_route = persist_route

    def list_frontdesk_capabilities(self) -> dict[str, Any]:
        metadata = load_distribution_metadata()
        return {
            "bundle_id": metadata.get("bundle_id", "ai-da-guan-jia-openclaw"),
            "display_name": metadata.get("display_name", "AI大管家"),
            "short_description": metadata.get("short_description", ""),
            "frontdesk_scenes": metadata.get("frontdesk_scenes", []),
            "tool_contracts": metadata.get("tool_contracts", []),
            "credential_guides": metadata.get("credential_guides", []),
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
        route = self.route_task(input_text, user_context=user_context)
        signals = route.get("signals", {})
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
        if not last_session.task_text:
            return {
                "status": "missing_context",
                "summary": "当前没有可收口的最近任务。",
                "verification_status": "missing_context",
                "missing": "先给任务、做一次知识查询，或让 AI 先形成一个 run。",
                "next_iterate": "先完成一次有证据的任务回合，再谈闭环。",
                "run_id": "",
            }

        if not last_session.produced_evidence:
            return {
                "status": "not_ready",
                "summary": f"当前只有前端交互，没有足够证据支撑真正闭环：{last_session.task_text}",
                "verification_status": "not_ready",
                "missing": "还缺可复核证据；不能把“会回话”误判成“任务完成”。",
                "next_iterate": "先补知识查询结果、任务产物或人工确认的完成证据，再执行 close-task。",
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
            f"AI大管家已接单：{route['task_text']}",
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
                "header": {"title": {"tag": "plain_text", "content": "AI大管家 路由结果"}},
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
    ):
        self.config = config
        self.auth_client = auth_client or FeishuAuthClient(config)
        self.messenger = messenger or FeishuMessenger(self.auth_client)
        self.backend = backend or AiDaGuanJiaBackend(persist_route=config.route_persist)
        self.verifier = verifier or FeishuEventVerifier(config)
        self.idempotency_store = idempotency_store or IdempotencyStore()
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

    def _update_session(self, chat_id: str, reply: FrontdeskReply) -> None:
        session_update = reply.metadata.get("session_update")
        if not isinstance(session_update, dict):
            return
        self.chat_sessions[chat_id] = FrontdeskSessionState(
            scene=reply.scene,
            task_text=str(session_update.get("task_text", "")).strip(),
            run_id=str(session_update.get("run_id", "")).strip(),
            produced_evidence=bool(session_update.get("produced_evidence", False)),
            verification_evidence=[str(item) for item in session_update.get("verification_evidence", [])],
            open_questions=[str(item) for item in session_update.get("open_questions", [])],
            effective_patterns=[str(item) for item in session_update.get("effective_patterns", [])],
            wasted_patterns=[str(item) for item in session_update.get("wasted_patterns", [])],
            evolution_candidates=[str(item) for item in session_update.get("evolution_candidates", [])],
            human_boundary=str(session_update.get("human_boundary", "")).strip(),
            max_distortion=str(session_update.get("max_distortion", "")).strip(),
        )

    @staticmethod
    def _session_from_payload(payload: dict[str, Any] | None) -> FrontdeskSessionState:
        data = payload or {}
        return FrontdeskSessionState(
            scene=str(data.get("scene", "")).strip(),
            task_text=str(data.get("task_text", "")).strip(),
            run_id=str(data.get("run_id", "")).strip(),
            produced_evidence=bool(data.get("produced_evidence", False)),
            verification_evidence=[str(item) for item in data.get("verification_evidence", [])],
            open_questions=[str(item) for item in data.get("open_questions", [])],
            effective_patterns=[str(item) for item in data.get("effective_patterns", [])],
            wasted_patterns=[str(item) for item in data.get("wasted_patterns", [])],
            evolution_candidates=[str(item) for item in data.get("evolution_candidates", [])],
            human_boundary=str(data.get("human_boundary", "")).strip(),
            max_distortion=str(data.get("max_distortion", "")).strip(),
        )

    def _home_reply(self) -> FrontdeskReply:
        p0_entries = [entry for entry in HOME_ENTRIES if entry["wave"] == "P0"]
        p1_entries = [entry for entry in HOME_ENTRIES if entry["wave"] == "P1"]
        return FrontdeskReply(
            scene="home",
            title="AI大管家 · 飞书前端首页",
            sections=[
                ("P0 现在可用", "\n".join([f"- {entry['name']}：{entry['prompt']}" for entry in p0_entries])),
                ("P1 下一波", "\n".join([f"- {entry['name']}：{entry['prompt']}" for entry in p1_entries])),
                ("协作边界", "飞书龙虾只做协作前端；AI大管家负责路由、验真、闭环。默认不是全自动代理。"),
            ],
            footer=[f"execution mode: {self.config.execution_mode}"],
        )

    def _task_intake_reply(self, content: str, user_context: dict[str, Any]) -> FrontdeskReply:
        result = self.backend.execute_task(content, user_context=user_context)
        route = result["route"]
        sections = [
            ("任务理解", route["task_text"]),
            ("技能链", ", ".join(route.get("selected_skills", [])) or "none"),
            ("验真目标", "；".join(route.get("verification_targets", [])[:3]) or "none"),
            ("run id", route["run_id"]),
        ]
        next_steps = result.get("summary", {}).get("next_steps", [])
        return FrontdeskReply(
            scene="task_intake",
            title="AI大管家 · 给任务",
            sections=sections,
            run_id=route["run_id"],
            metadata={
                "session_update": {
                    "task_text": route["task_text"],
                    "run_id": route["run_id"],
                    "produced_evidence": False,
                    "verification_evidence": [],
                    "open_questions": [],
                    "effective_patterns": [],
                    "wasted_patterns": [],
                    "evolution_candidates": ["把高频前端任务入口进一步固化成稳定协议。"],
                    "human_boundary": route.get("human_boundary", ""),
                    "max_distortion": route.get("situation_map", {}).get("当前最大失真", ""),
                }
            },
            footer=build_footer(route["run_id"], [f"next: {next_steps[0]}" if next_steps else ""]),
        )

    def _judgment_reply(self, content: str, user_context: dict[str, Any]) -> FrontdeskReply:
        result = self.backend.judge_task(content, user_context=user_context)
        route = result["route"]
        judgments = result["judgments"]
        return FrontdeskReply(
            scene="judgment",
            title="AI大管家 · 做判断",
            sections=[
                ("自治判断", judgments.get("自治判断", "")),
                ("全局最优判断", judgments.get("全局最优判断", "")),
                ("当前最大失真", judgments.get("当前最大失真", "")),
            ],
            run_id=route["run_id"],
            metadata={
                "session_update": {
                    "task_text": route["task_text"],
                    "run_id": route["run_id"],
                    "produced_evidence": False,
                    "verification_evidence": [],
                    "open_questions": [],
                    "effective_patterns": [],
                    "wasted_patterns": [],
                    "evolution_candidates": ["把高频判断题沉淀成更稳定的治理问句模板。"],
                    "human_boundary": route.get("human_boundary", ""),
                    "max_distortion": judgments.get("当前最大失真", ""),
                }
            },
            footer=build_footer(route["run_id"], [f"建议技能链: {', '.join(route.get('selected_skills', [])) or 'none'}"]),
        )

    def _knowledge_reply(self, content: str, user_context: dict[str, Any]) -> FrontdeskReply:
        result = self.backend.knowledge_lookup(content, user_context=user_context, allow_execute=self.config.allows_p0_execution)
        route = result.get("route", {})
        run_id = str(route.get("run_id") or "")
        return FrontdeskReply(
            scene="knowledge_lookup",
            title="AI大管家 · 查资料",
            sections=[
                ("原始来源", str(result.get("source_label", "待判定知识源"))),
                ("摘要结论", str(result.get("summary", "尚未形成稳定摘要。"))),
                ("还缺什么", str(result.get("missing", "none"))),
            ],
            run_id=run_id,
            status=str(result.get("status", "ok")),
            metadata={
                "session_update": {
                    "task_text": str(route.get("task_text", content)).strip(),
                    "run_id": run_id,
                    "produced_evidence": bool(result.get("produced_evidence", False)),
                    "verification_evidence": result.get("verification_evidence", []),
                    "open_questions": result.get("open_questions", []),
                    "effective_patterns": result.get("effective_patterns", []),
                    "wasted_patterns": result.get("wasted_patterns", []),
                    "evolution_candidates": result.get("evolution_candidates", []),
                    "human_boundary": str(route.get("human_boundary", "")),
                    "max_distortion": str(route.get("situation_map", {}).get("当前最大失真", "")),
                }
            },
            footer=build_footer(run_id, [f"execution mode: {result.get('execution_mode', 'route_only')}"]),
        )

    def _close_loop_reply(self, chat_id: str) -> FrontdeskReply:
        state = self.chat_sessions.get(chat_id, FrontdeskSessionState())
        result = self.backend.assess_close_loop(state, allow_execute=self.config.allows_p0_execution)
        run_id = str(result.get("run_id", "")).strip()
        return FrontdeskReply(
            scene="close_loop",
            title="AI大管家 · 收口",
            sections=[
                ("完成情况", str(result.get("summary", "尚未进入闭环。"))),
                ("验真状态", str(result.get("verification_status", "unknown"))),
                ("next iterate", str(result.get("next_iterate", "继续补证据并保持边界清晰。"))),
            ],
            run_id=run_id,
            status=str(result.get("status", "ok")),
            footer=build_footer(run_id, [str(result.get("missing", ""))]),
        )

    def _approval_reply(self, content: str, user_context: dict[str, Any]) -> FrontdeskReply:
        result = self.backend.judge_task(content, user_context=user_context)
        route = result["route"]
        situation = route.get("situation_map", {})
        return FrontdeskReply(
            scene="approval",
            title="AI大管家 · 审批边界",
            sections=[
                ("推荐方案", f"由你拍板，AI 负责比较与草案。当前建议路径：{', '.join(route.get('selected_skills', [])) or 'none'}"),
                ("不推荐方案", "让 AI 直接处理发布、删除、授权、付款或价值取舍类不可逆动作。"),
                ("为什么现在该由人决定", str(route.get("human_boundary") or situation.get("自治判断") or "这类动作属于明确的人类边界。")),
            ],
            run_id=route["run_id"],
            metadata={
                "session_update": {
                    "task_text": route["task_text"],
                    "run_id": route["run_id"],
                    "produced_evidence": False,
                    "verification_evidence": [],
                    "open_questions": [],
                    "effective_patterns": [],
                    "wasted_patterns": [],
                    "evolution_candidates": ["把审批题和判断题的前端协议分得更清楚。"],
                    "human_boundary": route.get("human_boundary", ""),
                    "max_distortion": situation.get("当前最大失真", ""),
                }
            },
            footer=build_footer(route["run_id"]),
        )

    def _today_focus_reply(self) -> FrontdeskReply:
        return FrontdeskReply(
            scene="today_focus",
            title="AI大管家 · 今天最该看什么",
            sections=[
                ("当前状态", "这是第二波能力；当前先维持建议模式，不默认自动跑。"),
                ("建议动作", "review-skills --daily；review-governance --daily；strategy-governor"),
                ("为什么还没默认开启", "战略层资产尚未稳定落盘，先避免把建议层误当执行层。"),
            ],
            footer=[f"execution mode: {self.config.execution_mode}"],
        )

    def reply_to_frontdesk(self, content: str, user_context: dict[str, Any] | None = None) -> FrontdeskReply:
        context = user_context or {}
        scene = classify_frontdesk_scene(content, self._detect_signals(content))
        if scene == "home":
            return self._home_reply()
        if scene == "judgment":
            return self._judgment_reply(content, context)
        if scene == "knowledge_lookup":
            return self._knowledge_reply(content, context)
        if scene == "close_loop":
            return self._close_loop_reply(str(context.get("chat_id", "")))
        if scene == "approval":
            return self._approval_reply(content, context)
        if scene == "today_focus":
            return self._today_focus_reply()
        return self._task_intake_reply(content, context)

    def handle_event(self, payload: dict[str, Any], headers: dict[str, str], raw_body: bytes) -> tuple[int, dict[str, Any]]:
        if payload.get("type") == "url_verification":
            return HTTPStatus.OK, {"challenge": payload.get("challenge", "")}

        self.verifier.verify(payload, headers, raw_body)
        header = payload.get("header") or {}
        event_type = header.get("event_type") or payload.get("type") or ""
        event_id = header.get("event_id") or ""

        if event_id and self.idempotency_store.seen(event_id):
            return HTTPStatus.OK, {"code": 0, "msg": "duplicate event ignored"}
        if event_id:
            self.idempotency_store.mark(event_id)

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
        }
        reply = self.reply_to_frontdesk(content, user_context=user_context)
        self._update_session(chat_id, reply)
        self.messenger.send_text_to_chat(chat_id, reply.as_text())
        if self.config.send_cards:
            self.messenger.send_card_to_chat(chat_id, reply.as_card())
        return HTTPStatus.OK, {
            "code": 0,
            "msg": "ok",
            "scene": reply.scene,
            "run_id": reply.run_id,
            "status": reply.status,
        }

    @staticmethod
    def _extract_text(message: dict[str, Any]) -> str:
        if message.get("message_type") != "text":
            return ""
        try:
            content = json.loads(message.get("content", "{}"))
        except json.JSONDecodeError:
            return ""
        return str(content.get("text", "")).strip()


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

        if self.path == "/tools/close_task":
            session_state = payload.get("session_state")
            if session_state:
                state = self.bridge._session_from_payload(session_state)
            else:
                chat_id = str(payload.get("chat_id", "")).strip()
                state = self.bridge.chat_sessions.get(chat_id, FrontdeskSessionState())
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Feishu Claw bridge for AI大管家.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve", help="Start the webhook server.")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8787)
    serve_parser.set_defaults(func=serve)

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

    reply_parser = subparsers.add_parser("reply-preview", help="Preview the structured frontdesk reply for one message.")
    reply_parser.add_argument("--input-text", required=True)
    reply_parser.add_argument("--execution-mode", default="route_only", choices=["route_only", "p0_assist", "p1_assist"])
    reply_parser.set_defaults(func=reply_preview_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
