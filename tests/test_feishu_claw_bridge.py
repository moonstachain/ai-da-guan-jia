from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "feishu_claw_bridge.py"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload: dict[str, object]):
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeMessenger:
    def __init__(self):
        self.text_messages: list[tuple[str, str]] = []
        self.card_messages: list[tuple[str, dict[str, object]]] = []
        self.updated_cards: list[tuple[str, dict[str, object]]] = []

    def send_text_to_chat(self, chat_id: str, text: str) -> dict[str, object]:
        self.text_messages.append((chat_id, text))
        return {"code": 0}

    def send_card_to_chat(self, chat_id: str, card: dict[str, object]) -> dict[str, object]:
        self.card_messages.append((chat_id, card))
        return {"code": 0, "data": {"message_id": f"card_{len(self.card_messages)}"}}

    def update_card(self, message_id: str, card: dict[str, object]) -> dict[str, object]:
        self.updated_cards.append((message_id, card))
        return {"code": 0, "data": {"message_id": message_id}}


class FakeFrontdeskBackend:
    def __init__(self, *, signals=None, task_result=None, judgment_result=None, knowledge_result=None, close_result=None, heartbeat_result=None):
        default_signals = {
            "get_biji": False,
            "feishu_km": False,
            "knowledge_first": False,
            "hard_boundary": False,
        }
        default_signals.update(signals or {})
        self.module = types.SimpleNamespace(detect_signals=lambda text: default_signals)
        self._task_result = task_result or {
            "status": "planned",
            "route": {
                "task_text": "默认任务",
                "selected_skills": ["ai-da-guan-jia"],
                "verification_targets": ["route.json"],
                "run_id": "adagj-default-task",
                "human_boundary": "none",
                "situation_map": {"当前最大失真": "默认失真"},
            },
            "summary": {"next_steps": ["python3 ... route"]},
        }
        self._judgment_result = judgment_result or {
            "route": {
                "task_text": "默认判断",
                "selected_skills": ["ai-da-guan-jia"],
                "run_id": "adagj-default-judge",
                "human_boundary": "需要人拍板",
                "situation_map": {"当前最大失真": "默认失真"},
            },
            "judgments": {
                "自治判断": "默认自治判断",
                "全局最优判断": "默认全局最优判断",
                "当前最大失真": "默认失真",
            },
        }
        self._knowledge_result = knowledge_result or {
            "status": "planned",
            "execution_mode": "route_only",
            "route": {"task_text": "默认查资料", "run_id": "adagj-default-knowledge", "human_boundary": "", "situation_map": {"当前最大失真": "查资料失真"}},
            "source_label": "Get笔记 / planned_lookup",
            "summary": "默认资料摘要",
            "missing": "默认还缺什么",
            "produced_evidence": False,
            "verification_evidence": [],
            "open_questions": ["默认开放问题"],
            "effective_patterns": [],
            "wasted_patterns": [],
            "evolution_candidates": ["默认演化建议"],
        }
        self._close_result = close_result or {
            "status": "not_ready",
            "summary": "默认还不能闭环",
            "verification_status": "not_ready",
            "missing": "还缺证据",
            "next_iterate": "先补证据",
            "run_id": "adagj-default-close",
        }
        self._heartbeat_result = heartbeat_result or {
            "status": "ok",
            "summary": "本轮继续盯住最需要推进的一条主线，只在值得打扰时打扰。",
            "next_step": "优先处理 transport 边界的恢复动作。",
            "top_action": {
                "project_id": "task-top",
                "title": "transport 边界恢复",
                "kind": "stall_nudge",
                "summary": "催办连续停滞的《transport 边界恢复》。",
                "next_step": "先确认 gh / GitHub auth 是否恢复。",
            },
            "top_human_boundary": {
                "project_id": "task-human",
                "title": "确认 Minutes 凭证",
                "status": "blocked_needs_user",
                "reason": "只差你确认凭证是否可用于下一轮抓取。",
            },
            "recent_actions": [
                {"kind": "stall_nudge", "summary": "催办连续停滞的《transport 边界恢复》。"},
                {"kind": "human_boundary", "summary": "把《确认 Minutes 凭证》推回共同治理者拍板。"},
            ],
            "recent_nudges": [],
            "current_max_distortion": "任务已经停滞，但表面上看起来还在流动。",
            "verification_status": "heartbeat_round_read",
            "run_id": "2026-03-14T09",
            "artifact_root": "/tmp/project-heartbeat",
        }

    @staticmethod
    def _user_visible_human_boundary(boundary):
        value = str(boundary or "").strip()
        if not value or value.lower() in {"none", ""} or "default to high autonomy" in value.lower():
            return ""
        return value
        self._note_capture_result = {
            "status": "captured",
            "capture_id": "frontdesk-capture-test",
            "run_id": "adagj-note-capture",
            "summary": "默认轻记录摘要",
            "next_step": "继续搜一下，或推进成任务。",
            "verification_status": "captured_canonical",
            "artifact_path": "/tmp/frontdesk-capture-test/capture.json",
            "summary_path": "/tmp/frontdesk-capture-test/summary.md",
            "canonical_run_dir": "/tmp/frontdesk-capture-test",
            "canonical_ref": "adagj-note-capture::frontdesk-capture-test",
            "sync_status": "canonical_local_only",
            "content": "默认轻记录内容",
        }

    def execute_task(self, input_text, user_context=None):
        result = dict(self._task_result)
        result["route"] = dict(result["route"])
        result["route"]["task_text"] = input_text
        return result

    def judge_task(self, input_text, user_context=None):
        result = dict(self._judgment_result)
        result["route"] = dict(result["route"])
        result["route"]["task_text"] = input_text
        return result

    def knowledge_lookup(self, input_text, user_context=None, allow_execute=False):
        result = dict(self._knowledge_result)
        result["route"] = dict(result.get("route", {}))
        result["route"]["task_text"] = input_text
        result["execution_mode"] = "p0_assist" if allow_execute else result.get("execution_mode", "route_only")
        return result

    def note_capture(self, input_text, user_context=None):
        result = dict(self._note_capture_result)
        result["summary"] = input_text or result["summary"]
        result["content"] = input_text or result["content"]
        return result

    def project_heartbeat(self):
        return dict(self._heartbeat_result)

    def assess_close_loop(self, last_session, allow_execute=False):
        result = dict(self._close_result)
        if allow_execute:
            result["status"] = "closed"
        return result

    def list_frontdesk_capabilities(self):
        return {
            "bundle_id": "ai-da-guan-jia-openclaw",
            "display_name": "原力OS",
            "short_description": "治理前台能力包",
            "wake_words": ["原力原力"],
            "invocation_examples": ["原力原力 今天最该看什么", "小猫现在在推什么"],
            "frontdesk_scenes": [{"scene": "task_intake", "label": "给任务"}, {"scene": "resume_context", "label": "继续上次"}, {"scene": "note_capture", "label": "轻记录"}, {"scene": "project_heartbeat", "label": "小猫推进"}],
            "tool_contracts": [{"name": "route_task"}],
            "credential_guides": [{"id": "feishu_bot"}],
            "when_to_call": ["任务还模糊，需要先压成清晰技能链"],
            "readiness_copy": {"已安装": "Skill 壳已经装好。"},
            "reply_contract": ["scene", "status", "run_id", "session_id", "summary", "next_step", "human_boundary", "verification_status", "text", "card"],
        }

    def get_run_status(self, run_id):
        return {"status": "found", "run_id": run_id, "task_text": "测试任务", "selected_skills": ["ai-da-guan-jia"], "next_step": "继续推进", "close_status": "route_only", "human_boundary": "none"}

    def suggest_human_decision(self, context, user_context=None):
        return {
            "status": "suggested",
            "route": {"run_id": "adagj-approve", "selected_skills": ["ai-da-guan-jia"]},
            "recommended": "由你拍板，AI 负责比较与草案。",
            "not_recommended": "不要让 AI 直接做不可逆动作。",
            "why_human_now": "这是人类边界。",
        }

    def today_focus(self):
        return {
            "status": "ok",
            "summary": "任务 A（active）；任务 B（blocked_needs_user）",
            "next_step": "先处理任务 A",
            "focus_items": [
                {"task_id": "task-a", "title": "任务 A", "status": "active", "next_action": "先处理任务 A"},
                {"task_id": "task-b", "title": "任务 B", "status": "blocked_needs_user", "next_action": "等你拍板"},
            ],
            "counts": {"active": 1, "blocked": 0, "waiting_for_user": 1},
        }

    def my_tasks(self, limit=5):
        return {
            "status": "ok",
            "summary": "活跃 1 / 阻塞 1 / 待你拍板 1",
            "next_step": "先处理任务 A",
            "tasks": [
                {"task_id": "task-a", "title": "任务 A", "status": "active", "next_action": "先处理任务 A"},
                {"task_id": "task-b", "title": "任务 B", "status": "blocked_needs_user", "next_action": "等你拍板"},
            ][:limit],
            "counts": {"active": 1, "blocked": 0, "waiting_for_user": 1},
        }

    def resume_context(self, session):
        if session.active_run_id or session.run_id:
            run_id = session.active_run_id or session.run_id
            return {
                "status": "found",
                "summary": session.last_user_goal or session.task_text or "继续上次任务",
                "next_step": "继续推进",
                "run_id": run_id,
                "verification_status": session.last_verification_status or "route_only",
                "human_boundary": session.pending_human_boundary or session.human_boundary,
                "selected_skills": ["ai-da-guan-jia"],
            }
        return {
            "status": "missing",
            "summary": "当前还没有可恢复的最近上下文。",
            "next_step": "请重新起单。",
            "run_id": "",
            "verification_status": "missing_context",
            "human_boundary": "",
            "selected_skills": [],
        }

    def handoff_to_pc(self, session):
        return {
            "status": "ready",
            "summary": session.last_user_goal or session.task_text or "这件事适合切回 PC 深工",
            "next_step": f"回到 PC 后继续 run {session.active_run_id or session.run_id}".strip(),
            "run_id": session.active_run_id or session.run_id,
            "verification_status": session.last_verification_status or "route_only",
            "human_boundary": session.pending_human_boundary or session.human_boundary,
        }


class FeishuClawBridgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module("test_feishu_claw_bridge", SCRIPT_PATH)

    def test_auth_client_caches_tenant_token(self) -> None:
        config = self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x")
        client = self.module.FeishuAuthClient(config)
        calls: list[str] = []

        def fake_urlopen(request, timeout=0):
            calls.append(request.full_url)
            return FakeResponse({"code": 0, "tenant_access_token": "tenant_token_123", "expire": 7200})

        with patch.object(self.module.urllib_request, "urlopen", side_effect=fake_urlopen):
            token_a = client.get_tenant_access_token()
            token_b = client.get_tenant_access_token()

        self.assertEqual(token_a, "tenant_token_123")
        self.assertEqual(token_b, "tenant_token_123")
        self.assertEqual(len(calls), 1)

    def test_verifier_accepts_matching_verification_token(self) -> None:
        config = self.module.BridgeConfig(
            app_id="cli_x",
            app_secret="sec_x",
            verification_token="verify-me",
        )
        verifier = self.module.FeishuEventVerifier(config)
        verifier.verify({"token": "verify-me"}, {}, b"{}")

    def test_verifier_rejects_mismatched_verification_token(self) -> None:
        config = self.module.BridgeConfig(
            app_id="cli_x",
            app_secret="sec_x",
            verification_token="verify-me",
        )
        verifier = self.module.FeishuEventVerifier(config)
        with self.assertRaises(PermissionError):
            verifier.verify({"token": "wrong"}, {}, b"{}")

    def test_backend_route_task_persists_route_bundle(self) -> None:
        fake_module = types.SimpleNamespace()
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "runs" / "adagj-feishu-test"
            run_dir.mkdir(parents=True, exist_ok=True)
            fake_module.ROUTING_ORDER = ["task_fit_score"]
            fake_module.discover_skills = lambda: [{"name": "ai-da-guan-jia"}]
            fake_module.detect_signals = lambda prompt: {"feishu": False, "get_biji": False, "feishu_km": False}
            fake_module.explicit_mentions = lambda prompt, names: []
            fake_module.load_governance_signals = lambda: {"status": "missing"}
            fake_module.score_candidate = lambda prompt, skill, signals, mentioned, governance: {
                "name": skill["name"],
                "total_score": 10,
            }
            fake_module.choose_skills = lambda prompt, ranked, signals, mentioned: (["ai-da-guan-jia"], [])
            fake_module.plan_get_biji_actions = lambda prompt: {}
            fake_module.plan_feishu_km_actions = lambda prompt, signals: {}
            fake_module.build_situation_map = lambda prompt, selected, signals: {"自治判断": "high"}
            fake_module.iso_now = lambda: "2026-03-11T15:00:00+08:00"
            fake_module.allocate_run_id = lambda created_at: "adagj-feishu-test"
            fake_module.run_dir_for = lambda run_id, created_at: run_dir
            fake_module.credit_influenced_selection = lambda ranked, selected: False
            fake_module.selected_proposal_authority_summary = lambda ranked, selected: {}
            fake_module.selection_ceiling = lambda signals: 3
            fake_module.determine_human_boundary = lambda signals: "none"
            fake_module.verification_targets = lambda signals, plan: ["route.json"]
            fake_module.render_situation_map = lambda situation_map, prompt: "# Situation"
            fake_module.write_json = lambda path, payload: path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            backend = self.module.AiDaGuanJiaBackend.__new__(self.module.AiDaGuanJiaBackend)
            backend.module = fake_module
            backend.persist_route = True
            result = backend.route_task("帮我规划飞书接入", user_context={"surface": "test"})

            self.assertEqual(result["run_id"], "adagj-feishu-test")
            self.assertTrue((run_dir / "route.json").exists())
            self.assertTrue((run_dir / "situation-map.md").exists())
            self.assertIn("human_route_summary", result)
            self.assertIn("recommended_actions", result)
            self.assertIn("next_action", result)

    def test_handle_event_routes_text_message_and_sends_text_reply(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            config = self.module.BridgeConfig(
                app_id="cli_x",
                app_secret="sec_x",
                verification_token="verify-me",
            )
            messenger = FakeMessenger()
            backend = FakeFrontdeskBackend(
                task_result={
                    "status": "planned",
                    "route": {
                        "task_text": "占位任务",
                        "selected_skills": ["ai-da-guan-jia", "feishu-open-platform"],
                        "verification_targets": ["route.json"],
                        "run_id": "adagj-bridge-test",
                        "human_boundary": "none",
                        "situation_map": {"当前最大失真": "默认失真"},
                    },
                    "summary": {"next_steps": ["python3 work/ai-da-guan-jia/scripts/ai_da_guan_jia.py route --prompt ..."]},
                }
            )
            service = self.module.FeishuClawBridgeService(
                config,
                messenger=messenger,
                backend=backend,
                idempotency_store=self.module.IdempotencyStore(path=Path(tempdir) / "idempotency.json"),
                session_store=self.module.FrontdeskSessionStore(Path(tempdir) / "sessions.json"),
            )
            payload = {
                "token": "verify-me",
                "header": {
                    "event_type": "im.message.receive_v1",
                    "event_id": "evt_123",
                },
                "event": {
                    "sender": {"sender_id": {"open_id": "ou_123"}},
                    "message": {
                        "chat_id": "oc_123",
                        "message_id": "om_123",
                        "message_type": "text",
                        "content": json.dumps({"text": "帮我研究飞书 claw"}, ensure_ascii=False),
                    },
                },
            }

            status, response = service.handle_event(payload, {}, json.dumps(payload).encode("utf-8"))
            self.assertEqual(status, 200)
            self.assertEqual(response["run_id"], "adagj-bridge-test")
            self.assertEqual(response["scene"], "task_intake")
            self.assertEqual(messenger.text_messages[0][0], "oc_123")
            self.assertIn("原力OS · 任务副驾驶", messenger.text_messages[0][1])

    def test_handle_event_ignores_duplicate_event(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            config = self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x")
            messenger = FakeMessenger()
            service = self.module.FeishuClawBridgeService(
                config,
                messenger=messenger,
                backend=FakeFrontdeskBackend(),
                idempotency_store=self.module.IdempotencyStore(path=Path(tempdir) / "idempotency.json"),
                session_store=self.module.FrontdeskSessionStore(Path(tempdir) / "sessions.json"),
            )
            payload = {
                "header": {"event_type": "im.message.receive_v1", "event_id": "evt_dup"},
                "event": {"message": {"chat_id": "oc_123", "message_type": "text", "content": "{\"text\":\"x\"}"}, "sender": {}},
            }
            first = service.handle_event(payload, {}, b"{}")
            second = service.handle_event(payload, {}, b"{}")
            self.assertEqual(first[0], 200)
            self.assertEqual(second[1]["msg"], "duplicate event ignored")
            self.assertEqual(len(messenger.text_messages), 1)

    def test_classify_frontdesk_scene_prefers_home_and_approval(self) -> None:
        home = self.module.classify_frontdesk_scene("首页", {"hard_boundary": False})
        approval = self.module.classify_frontdesk_scene("这条消息要不要发", {"hard_boundary": True})
        self.assertEqual(home, "home")
        self.assertEqual(approval, "approval")

    def test_classify_frontdesk_scene_detects_resume_tasks_and_pc_handoff(self) -> None:
        resume = self.module.classify_frontdesk_scene("继续昨天那个", {"hard_boundary": False})
        my_tasks = self.module.classify_frontdesk_scene("我现在有哪些任务", {"hard_boundary": False})
        handoff = self.module.classify_frontdesk_scene("这件事交给 PC 继续", {"hard_boundary": False})
        self.assertEqual(resume, "resume_context")
        self.assertEqual(my_tasks, "my_tasks")
        self.assertEqual(handoff, "handoff_to_pc")

    def test_classify_frontdesk_scene_detects_semantic_resume_queries(self) -> None:
        resume = self.module.classify_frontdesk_scene("原力原力，你是能看到我上一个那个任务吗", {"hard_boundary": False})
        remembered = self.module.classify_frontdesk_scene("你还记得我上次那个任务吗", {"hard_boundary": False})
        self.assertEqual(resume, "resume_context")
        self.assertEqual(remembered, "resume_context")

    def test_classify_frontdesk_scene_detects_project_heartbeat_queries(self) -> None:
        scene = self.module.classify_frontdesk_scene("小猫现在在推什么", {"hard_boundary": False})
        compatible = self.module.classify_frontdesk_scene("P猫现在在推什么", {"hard_boundary": False})
        blocker = self.module.classify_frontdesk_scene("项目现在卡哪了", {"hard_boundary": False})
        self.assertEqual(scene, "project_heartbeat")
        self.assertEqual(compatible, "project_heartbeat")
        self.assertEqual(blocker, "project_heartbeat")

    def test_strip_wake_prefix_only_matches_at_message_start(self) -> None:
        stripped, wake_used = self.module.strip_wake_prefix("原力原力 今天最该看什么")
        untouched, untouched_wake = self.module.strip_wake_prefix("帮我研究原力原力OS接入")

        self.assertTrue(wake_used)
        self.assertEqual(stripped, "今天最该看什么")
        self.assertFalse(untouched_wake)
        self.assertEqual(untouched, "帮我研究原力原力OS接入")

    def test_home_reply_lists_frontdesk_entrypoints(self) -> None:
        service = self.module.FeishuClawBridgeService(
            self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
            messenger=FakeMessenger(),
            backend=FakeFrontdeskBackend(),
        )
        reply = service.reply_to_frontdesk("首页", user_context={"chat_id": "oc_1"})
        self.assertEqual(reply.scene, "home")
        self.assertIn("给我接个任务", reply.as_text())
        self.assertIn("继续昨天那个", reply.as_text())
        self.assertIn("原力原力", reply.as_text())
        self.assertIn("什么时候别叫我", reply.as_text())
        self.assertIn("Deep Research", reply.as_text())

    def test_wake_word_only_returns_home(self) -> None:
        service = self.module.FeishuClawBridgeService(
            self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
            messenger=FakeMessenger(),
            backend=FakeFrontdeskBackend(),
        )
        reply = service.reply_to_frontdesk("原力原力", user_context={"chat_id": "oc_1"})
        self.assertEqual(reply.scene, "home")

    def test_wake_prefixed_today_focus_routes_normally(self) -> None:
        service = self.module.FeishuClawBridgeService(
            self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
            messenger=FakeMessenger(),
            backend=FakeFrontdeskBackend(),
        )
        reply = service.reply_to_frontdesk("原力原力 今天最该看什么", user_context={"chat_id": "oc_1"})
        self.assertEqual(reply.scene, "today_focus")
        self.assertIn("任务 A", reply.as_text())

    def test_wake_prefixed_note_capture_uses_light_record_scene(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            backend = self.module.AiDaGuanJiaBackend(persist_route=False, capture_root=Path(tempdir))
            service = self.module.FeishuClawBridgeService(
                self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
                messenger=FakeMessenger(),
                backend=backend,
            )

            reply = service.reply_to_frontdesk(
                "原力原力 记一下 明天要确认 Minutes 凭证",
                user_context={"chat_id": "oc_1", "open_id": "ou_1", "tenant_key": "tenant_1"},
            )

            self.assertEqual(reply.scene, "note_capture")
            self.assertEqual(reply.status, "captured")
            artifact_path = Path(reply.metadata["artifact_path"])
            self.assertTrue(artifact_path.exists())
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["content"], "明天要确认 Minutes 凭证")
            self.assertEqual(payload["sync_status"], "canonical_local_only")
            self.assertTrue(Path(reply.metadata["canonical_run_dir"]).exists())
            self.assertTrue(reply.run_id.startswith("adagj-"))

    def test_wake_prefixed_search_routes_to_knowledge_lookup(self) -> None:
        service = self.module.FeishuClawBridgeService(
            self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
            messenger=FakeMessenger(),
            backend=FakeFrontdeskBackend(),
        )
        reply = service.reply_to_frontdesk("原力原力 搜一下 客户分层", user_context={"chat_id": "oc_1"})
        self.assertEqual(reply.scene, "knowledge_lookup")

    def test_colloquial_search_routes_to_knowledge_lookup_without_wake_word(self) -> None:
        service = self.module.FeishuClawBridgeService(
            self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
            messenger=FakeMessenger(),
            backend=FakeFrontdeskBackend(),
        )
        reply = service.reply_to_frontdesk("诶，你搜一下那个小红书，就是最新的关于那个 Openclaw 的那个热点新闻，你给我来10条", user_context={"chat_id": "oc_1"})
        self.assertEqual(reply.scene, "knowledge_lookup")
        self.assertIn("我会先查什么来源", reply.as_text())
        self.assertNotIn("原力OS · 给任务", reply.as_text())

    def test_note_capture_is_searchable_from_local_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            backend = self.module.AiDaGuanJiaBackend(persist_route=False, capture_root=Path(tempdir))
            service = self.module.FeishuClawBridgeService(
                self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
                messenger=FakeMessenger(),
                backend=backend,
            )

            service.reply_to_frontdesk(
                "原力原力 记一下 明天要确认 Minutes 凭证",
                user_context={"chat_id": "oc_1", "open_id": "ou_1", "tenant_key": "tenant_1"},
            )
            reply = service.reply_to_frontdesk(
                "原力原力 搜一下 Minutes 凭证",
                user_context={"chat_id": "oc_1", "open_id": "ou_1", "tenant_key": "tenant_1"},
            )

            self.assertEqual(reply.scene, "knowledge_lookup")
            self.assertIn("本地 canonical", reply.as_text())
            self.assertIn("未同步到外部知识库", reply.as_text())
            self.assertEqual(reply.verification_status, "evidence_ready")

    def test_knowledge_reply_keeps_source_boundary(self) -> None:
        backend = FakeFrontdeskBackend(
            signals={"knowledge_first": True},
            knowledge_result={
                "status": "planned",
                "execution_mode": "route_only",
                "route": {"task_text": "帮我查飞书知识库", "run_id": "adagj-knowledge", "human_boundary": "", "situation_map": {"当前最大失真": "二手总结失真"}},
                "source_label": "ask.feishu / Aily（计划路径）",
                "summary": "建议先问飞书知识库，并保留原始问答。",
                "missing": "当前默认只给出路径建议，未自动伪造答案。",
                "produced_evidence": False,
                "verification_evidence": [],
                "open_questions": ["还缺原始回答"],
                "effective_patterns": [],
                "wasted_patterns": [],
                "evolution_candidates": ["把 manual_web 与 official_api 路径分清楚。"],
            },
        )
        service = self.module.FeishuClawBridgeService(
            self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
            messenger=FakeMessenger(),
            backend=backend,
        )
        reply = service.reply_to_frontdesk("帮我查飞书知识库里关于客户分层的结论", user_context={"chat_id": "oc_1"})
        self.assertEqual(reply.scene, "knowledge_lookup")
        self.assertIn("我会先查什么来源", reply.as_text())
        self.assertIn("ask.feishu / Aily", reply.as_text())
        self.assertIn("现在还缺什么", reply.as_text())
        self.assertEqual(reply.verification_status, "planned")

    def test_task_intake_reply_uses_copilot_card_and_hides_internal_fields(self) -> None:
        backend = FakeFrontdeskBackend(
            task_result={
                "status": "planned",
                "route": {
                    "task_text": "帮我把这件事理清并排个推进顺序",
                    "selected_skills": ["jiyao-youyao-haiyao", "openclaw-xhs-coevolution-lab"],
                    "verification_targets": ["route.json"],
                    "run_id": "adagj-copilot",
                    "human_boundary": "Default to high autonomy. Do not interrupt the user unless a truly human-only boundary appears.",
                    "human_route_summary": "我理解成你要先把这件事压成可推进任务，再定第一步。",
                    "recommended_actions": [
                        {
                            "step_index": 1,
                            "action": "frontdesk.coplan",
                            "human_next_step": "我先帮你把目标、路径和第一步压清，再决定是否要切深工。",
                            "user_reply": "如果我理解对了，你可以回：继续推进；如果要改目标，就把新目标再说一句。",
                        }
                    ],
                    "situation_map": {"当前最大失真": "默认失真"},
                },
                "summary": {"next_steps": ["python3 ... route"]},
            }
        )
        service = self.module.FeishuClawBridgeService(
            self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
            messenger=FakeMessenger(),
            backend=backend,
        )

        reply = service.reply_to_frontdesk("帮我把这件事理清并排个推进顺序", user_context={"chat_id": "oc_1"})

        self.assertEqual(reply.title, "原力OS · 任务副驾驶")
        self.assertIn("我理解你要做什么", reply.as_text())
        self.assertIn("我建议先怎么推进", reply.as_text())
        self.assertIn("你现在可以怎么回我", reply.as_text())
        self.assertNotIn("按技能链推进下一步", reply.as_text())
        self.assertNotIn("jiyao-youyao-haiyao", reply.as_text())
        self.assertNotIn("Default to high autonomy", reply.as_text())

    def test_close_loop_reply_surfaces_readiness(self) -> None:
        service = self.module.FeishuClawBridgeService(
            self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
            messenger=FakeMessenger(),
            backend=FakeFrontdeskBackend(
                close_result={
                    "status": "ready_for_close",
                    "summary": "这件事已具备进入 close-task 的基本证据。",
                    "verification_status": "ready_for_close",
                    "missing": "当前前端还未替你正式执行 closure apply。",
                    "next_iterate": "切到 p0_assist 或在终端执行 close-task。",
                    "run_id": "adagj-close-preview",
                }
            ),
        )
        service.chat_sessions["oc_1"] = self.module.FrontdeskSessionState(
            scene="knowledge_lookup",
            task_text="帮我查客户分层笔记",
            run_id="adagj-knowledge",
            produced_evidence=True,
            verification_evidence=["record: /tmp/get-biji-record.json"],
        )
        reply = service.reply_to_frontdesk("把这事闭环", user_context={"chat_id": "oc_1"})
        self.assertEqual(reply.scene, "close_loop")
        self.assertIn("ready_for_close", reply.as_text())
        self.assertIn("next iterate", reply.as_text())

    def test_close_loop_after_note_capture_stays_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            backend = self.module.AiDaGuanJiaBackend(persist_route=False, capture_root=Path(tempdir))
            service = self.module.FeishuClawBridgeService(
                self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
                messenger=FakeMessenger(),
                backend=backend,
            )

            service.reply_to_frontdesk(
                "原力原力 记一下 明天要确认 Minutes 凭证",
                user_context={"chat_id": "oc_1", "open_id": "ou_1", "tenant_key": "tenant_1"},
            )
            reply = service.reply_to_frontdesk(
                "把这事闭环",
                user_context={"chat_id": "oc_1", "open_id": "ou_1", "tenant_key": "tenant_1"},
            )

            self.assertEqual(reply.scene, "close_loop")
            self.assertIn("不适合闭环", reply.as_text())
            self.assertIn("轻记录", reply.as_text())

    def test_reply_contract_contains_session_and_next_step_fields(self) -> None:
        service = self.module.FeishuClawBridgeService(
            self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
            messenger=FakeMessenger(),
            backend=FakeFrontdeskBackend(),
        )
        reply = service.reply_to_frontdesk(
            "帮我研究飞书 claw",
            user_context={"chat_id": "oc_1", "open_id": "ou_1", "tenant_key": "tenant_1"},
        )
        payload = reply.to_dict()
        self.assertEqual(payload["scene"], "task_intake")
        self.assertEqual(payload["run_id"], "adagj-default-task")
        self.assertTrue(payload["session_id"].startswith("tenant_1::ou_1::oc_1"))
        self.assertIn("summary", payload)
        self.assertIn("next_step", payload)
        self.assertIn("human_boundary", payload)
        self.assertIn("verification_status", payload)

    def test_resume_context_recovers_persisted_session_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            session_path = Path(tempdir) / "sessions.json"
            service = self.module.FeishuClawBridgeService(
                self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
                messenger=FakeMessenger(),
                backend=FakeFrontdeskBackend(),
                session_store=self.module.FrontdeskSessionStore(session_path),
            )
            service.reply_to_frontdesk(
                "帮我研究飞书 claw",
                user_context={"chat_id": "oc_1", "open_id": "ou_1", "tenant_key": "tenant_1"},
            )

            restarted = self.module.FeishuClawBridgeService(
                self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
                messenger=FakeMessenger(),
                backend=FakeFrontdeskBackend(),
                session_store=self.module.FrontdeskSessionStore(session_path),
            )
            reply = restarted.reply_to_frontdesk(
                "继续昨天那个",
                user_context={"chat_id": "oc_1", "open_id": "ou_1", "tenant_key": "tenant_1"},
            )
            self.assertEqual(reply.scene, "resume_context")
            self.assertEqual(reply.run_id, "adagj-default-task")
            self.assertIn("继续推进", reply.as_text())

    def test_semantic_resume_without_history_stays_resume_context(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            service = self.module.FeishuClawBridgeService(
                self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
                messenger=FakeMessenger(),
                backend=FakeFrontdeskBackend(),
                session_store=self.module.FrontdeskSessionStore(Path(tempdir) / "sessions.json"),
            )

            reply = service.reply_to_frontdesk(
                "原力原力，你是能看到我上一个那个任务吗",
                user_context={"chat_id": "oc_1", "open_id": "ou_1", "tenant_key": "tenant_1"},
            )

            self.assertEqual(reply.scene, "resume_context")
            self.assertIn("最近上下文", reply.as_text())
            self.assertNotEqual(reply.scene, "task_intake")

    def test_idempotency_store_persists_duplicate_events_across_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            idempotency_path = Path(tempdir) / "idempotency.json"
            payload = {
                "header": {"event_type": "im.message.receive_v1", "event_id": "evt_dup_restart"},
                "event": {
                    "message": {"chat_id": "oc_123", "message_type": "text", "content": "{\"text\":\"x\"}"},
                    "sender": {"sender_id": {"open_id": "ou_123"}},
                },
            }
            first = self.module.FeishuClawBridgeService(
                self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
                messenger=FakeMessenger(),
                backend=FakeFrontdeskBackend(),
                idempotency_store=self.module.IdempotencyStore(path=idempotency_path),
            )
            first.handle_event(payload, {}, b"{}")

            second = self.module.FeishuClawBridgeService(
                self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
                messenger=FakeMessenger(),
                backend=FakeFrontdeskBackend(),
                idempotency_store=self.module.IdempotencyStore(path=idempotency_path),
            )
            status, response = second.handle_event(payload, {}, b"{}")
            self.assertEqual(status, 200)
            self.assertEqual(response["msg"], "duplicate event ignored")

    def test_my_tasks_and_today_focus_reply_read_canonical_summary(self) -> None:
        service = self.module.FeishuClawBridgeService(
            self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
            messenger=FakeMessenger(),
            backend=FakeFrontdeskBackend(),
        )
        my_tasks = service.reply_to_frontdesk("我现在有哪些任务", user_context={"chat_id": "oc_1"})
        today = service.reply_to_frontdesk("今天最该看什么", user_context={"chat_id": "oc_1"})
        self.assertEqual(my_tasks.scene, "my_tasks")
        self.assertIn("活跃 1 / 阻塞 0 / 待你拍板 1", my_tasks.as_text())
        self.assertEqual(today.scene, "today_focus")
        self.assertIn("任务 A", today.as_text())

    def test_project_heartbeat_reply_surfaces_top_action_and_human_boundary(self) -> None:
        service = self.module.FeishuClawBridgeService(
            self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
            messenger=FakeMessenger(),
            backend=FakeFrontdeskBackend(),
        )
        reply = service.reply_to_frontdesk("小猫现在在推什么", user_context={"chat_id": "oc_1"})
        self.assertEqual(reply.scene, "project_heartbeat")
        self.assertIn("transport 边界恢复", reply.as_text())
        self.assertIn("确认 Minutes 凭证", reply.as_text())
        self.assertEqual(reply.title, "原力OS · 小猫项目推进")

    def test_project_heartbeat_reply_handles_colloquial_wake_phrase(self) -> None:
        service = self.module.FeishuClawBridgeService(
            self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
            messenger=FakeMessenger(),
            backend=FakeFrontdeskBackend(),
        )
        reply = service.reply_to_frontdesk("诶，原力原力，那个呢小猫现在在推什么？", user_context={"chat_id": "oc_1"})
        self.assertEqual(reply.scene, "project_heartbeat")
        self.assertEqual(reply.title, "原力OS · 小猫项目推进")
        self.assertIn("本小时总判断", reply.as_text())

    def test_handoff_to_pc_reply_uses_active_run(self) -> None:
        service = self.module.FeishuClawBridgeService(
            self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
            messenger=FakeMessenger(),
            backend=FakeFrontdeskBackend(),
        )
        session_id = self.module.build_session_id({"chat_id": "oc_1", "open_id": "ou_1", "tenant_key": "tenant_1"})
        state = self.module.FrontdeskSessionState(
            session_id=session_id,
            chat_id="oc_1",
            tenant_key="tenant_1",
            user_open_id="ou_1",
            task_text="帮我研究飞书 claw",
            last_user_goal="帮我研究飞书 claw",
            run_id="adagj-default-task",
            active_run_id="adagj-default-task",
            last_verification_status="route_only",
        )
        service.chat_sessions[session_id] = state
        reply = service.reply_to_frontdesk("这件事交给 PC 继续", user_context={"chat_id": "oc_1", "open_id": "ou_1", "tenant_key": "tenant_1"})
        self.assertEqual(reply.scene, "handoff_to_pc")
        self.assertIn("adagj-default-task", reply.as_text())

    def test_bundle_metadata_includes_install_prompt_and_status(self) -> None:
        service = self.module.FeishuClawBridgeService(
            self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
            messenger=FakeMessenger(),
            backend=FakeFrontdeskBackend(),
        )
        metadata = service.bundle_metadata()
        self.assertEqual(metadata["bundle_id"], "ai-da-guan-jia-openclaw")
        self.assertIn("请安装 原力OS 技能", metadata["install_prompt"])
        self.assertEqual(metadata["wake_words"], ["原力原力"])
        self.assertIn("installation_state", metadata)
        self.assertIn("overall_status", metadata["installation_state"])
        self.assertIn("when_to_call", metadata)
        self.assertIn("readiness_copy", metadata)

    def test_runtime_diagnostics_reports_owner_and_recent_event(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            config = self.module.BridgeConfig(
                app_id="cli_x",
                app_secret="sec_x",
                instance_tag="local-owner",
            )
            service = self.module.FeishuClawBridgeService(
                config,
                messenger=FakeMessenger(),
                backend=FakeFrontdeskBackend(),
                idempotency_store=self.module.IdempotencyStore(path=Path(tempdir) / "idempotency.json"),
                session_store=self.module.FrontdeskSessionStore(Path(tempdir) / "sessions.json"),
            )
            payload = {
                "header": {"event_type": "im.message.receive_v1", "event_id": "evt_diag", "tenant_key": "tenant_1"},
                "event": {
                    "sender": {"sender_id": {"open_id": "ou_1"}},
                    "message": {
                        "chat_id": "oc_1",
                        "message_id": "om_1",
                        "message_type": "text",
                        "content": json.dumps({"text": "继续昨天那个"}, ensure_ascii=False),
                    },
                },
            }

            service.handle_event(payload, {}, json.dumps(payload).encode("utf-8"))
            diagnostics = service.runtime_diagnostics(chat_id="oc_1", limit=3)

            self.assertEqual(diagnostics["official_owner"], "local-owner")
            self.assertEqual(diagnostics["target_session"]["runtime_owner"], "local-owner")
            self.assertEqual(diagnostics["target_session"]["last_event_id"], "evt_diag")
            self.assertEqual(diagnostics["recent_events"][0]["owner"], "local-owner")

    def test_frontdesk_visible_titles_use_yuanli_os_brand(self) -> None:
        service = self.module.FeishuClawBridgeService(
            self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
            messenger=FakeMessenger(),
            backend=FakeFrontdeskBackend(),
        )

        replies = [
            service.reply_to_frontdesk("帮我研究飞书 claw", user_context={"chat_id": "oc_1"}),
            service.reply_to_frontdesk("这件事该不该做", user_context={"chat_id": "oc_1"}),
            service.reply_to_frontdesk("原力原力 搜一下 客户分层", user_context={"chat_id": "oc_1"}),
            service.reply_to_frontdesk("把这事闭环", user_context={"chat_id": "oc_1"}),
            service.reply_to_frontdesk("这条消息要不要发", user_context={"chat_id": "oc_1"}),
            service.reply_to_frontdesk("今天最该看什么", user_context={"chat_id": "oc_1"}),
            service.reply_to_frontdesk("小猫现在在推什么", user_context={"chat_id": "oc_1"}),
        ]

        for reply in replies:
            self.assertTrue(reply.title.startswith("原力OS · "), msg=reply.title)

    def test_backend_get_run_status_reads_route_bundle(self) -> None:
        fake_module = types.SimpleNamespace()
        with tempfile.TemporaryDirectory() as tempdir:
            artifacts_root = Path(tempdir) / "artifacts"
            run_dir = artifacts_root / "runs" / "2026-03-11" / "adagj-run-status"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "route.json").write_text(
                json.dumps(
                    {
                        "run_id": "adagj-run-status",
                        "task_text": "测试 run 状态",
                        "selected_skills": ["ai-da-guan-jia", "feishu-open-platform"],
                        "verification_targets": ["route.json"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            fake_module.ARTIFACTS_ROOT = artifacts_root
            backend = self.module.AiDaGuanJiaBackend.__new__(self.module.AiDaGuanJiaBackend)
            backend.module = fake_module
            backend.persist_route = False
            result = backend.get_run_status("adagj-run-status")
            self.assertEqual(result["status"], "found")
            self.assertEqual(result["task_text"], "测试 run 状态")
            self.assertIn("feishu-open-platform", result["selected_skills"])

    def test_suggest_human_decision_endpoint_uses_minimal_contract(self) -> None:
        service = self.module.FeishuClawBridgeService(
            self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
            messenger=FakeMessenger(),
            backend=FakeFrontdeskBackend(),
        )
        result = service.backend.suggest_human_decision("这条消息要不要发")
        self.assertEqual(result["status"], "suggested")
        self.assertIn("由你拍板", result["recommended"])
        self.assertIn("人类边界", result["why_human_now"])

    def test_coerce_longconn_event_payload_converts_sdk_object(self) -> None:
        sender_id = types.SimpleNamespace(open_id="ou_test")
        sender = types.SimpleNamespace(sender_id=sender_id, tenant_key="tenant_test")
        message = types.SimpleNamespace(
            message_id="om_test",
            chat_id="oc_test",
            message_type="text",
            content="{\"text\":\"继续昨天那个\"}",
        )
        header = types.SimpleNamespace(event_type="im.message.receive_v1", event_id="evt_test", tenant_key="tenant_test")
        event = types.SimpleNamespace(header=header, event=types.SimpleNamespace(sender=sender, message=message), schema="2.0")

        payload = self.module.coerce_longconn_event_payload(event)

        self.assertEqual(payload["header"]["event_type"], "im.message.receive_v1")
        self.assertEqual(payload["header"]["event_id"], "evt_test")
        self.assertEqual(payload["event"]["sender"]["sender_id"]["open_id"], "ou_test")
        self.assertEqual(payload["event"]["message"]["chat_id"], "oc_test")

    def test_coerce_longconn_event_payload_uses_explicit_default_event_type(self) -> None:
        event = types.SimpleNamespace(header=types.SimpleNamespace(event_id="evt_reaction"), event=types.SimpleNamespace(), schema="2.0")

        payload = self.module.coerce_longconn_event_payload(
            event,
            default_event_type="im.message.reaction.deleted_v1",
        )

        self.assertEqual(payload["header"]["event_type"], "im.message.reaction.deleted_v1")

    def test_extract_text_supports_post_messages(self) -> None:
        message = {
            "message_type": "post",
            "content": json.dumps(
                {
                    "zh_cn": {
                        "title": "",
                        "content": [
                            [{"tag": "text", "text": "1. 继续昨天那个"}],
                            [{"tag": "text", "text": "2. 我现在有哪些任务"}],
                        ],
                    }
                },
                ensure_ascii=False,
            ),
        }

        result = self.module.FeishuClawBridgeService._extract_text(message)

        self.assertIn("继续昨天那个", result)
        self.assertIn("我现在有哪些任务", result)

    def test_multiline_frontdesk_bundle_returns_combined_reply(self) -> None:
        service = self.module.FeishuClawBridgeService(
            self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
            messenger=FakeMessenger(),
            backend=FakeFrontdeskBackend(),
        )

        reply = service.reply_to_frontdesk(
            "我现在有哪些任务\n今天最该看什么\n把这事闭环",
            user_context={"chat_id": "oc_bundle", "open_id": "ou_bundle", "tenant_key": "tenant_bundle"},
        )

        self.assertEqual(reply.scene, "frontdesk_bundle")
        self.assertIn("我的任务", reply.as_text())
        self.assertIn("今天最该看什么", reply.as_text())
        self.assertIn("收口", reply.as_text())
        self.assertIn("一次处理 3 条前台请求", reply.summary)

    def test_multiline_frontdesk_bundle_supports_wake_prefixed_lines(self) -> None:
        service = self.module.FeishuClawBridgeService(
            self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
            messenger=FakeMessenger(),
            backend=FakeFrontdeskBackend(),
        )

        reply = service.reply_to_frontdesk(
            "原力原力 我现在有哪些任务\n今天最该看什么",
            user_context={"chat_id": "oc_bundle", "open_id": "ou_bundle", "tenant_key": "tenant_bundle"},
        )

        self.assertEqual(reply.scene, "frontdesk_bundle")
        self.assertIn("我的任务", reply.as_text())
        self.assertIn("今天最该看什么", reply.as_text())

    def test_handle_event_appends_instance_tag_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            config = self.module.BridgeConfig(
                app_id="cli_x",
                app_secret="sec_x",
                instance_tag="local-debug",
            )
            messenger = FakeMessenger()
            service = self.module.FeishuClawBridgeService(
                config,
                messenger=messenger,
                backend=FakeFrontdeskBackend(),
                idempotency_store=self.module.IdempotencyStore(path=Path(tempdir) / "idempotency.json"),
                session_store=self.module.FrontdeskSessionStore(Path(tempdir) / "sessions.json"),
            )
            payload = {
                "header": {"event_type": "im.message.receive_v1", "event_id": "evt_sig"},
                "event": {
                    "sender": {"sender_id": {"open_id": "ou_123"}},
                    "message": {
                        "chat_id": "oc_123",
                        "message_id": "om_123",
                        "message_type": "text",
                        "content": json.dumps({"text": "继续昨天那个"}, ensure_ascii=False),
                    },
                },
            }

            status, response = service.handle_event(payload, {}, json.dumps(payload).encode("utf-8"))

            self.assertEqual(status, 200)
            self.assertEqual(response["scene"], "resume_context")
            self.assertIn("bridge: local-debug", messenger.text_messages[0][1])


if __name__ == "__main__":
    unittest.main()
