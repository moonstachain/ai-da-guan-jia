from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path("/Users/hay2045/Documents/codex-ai-gua-jia-01")
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

    def send_text_to_chat(self, chat_id: str, text: str) -> dict[str, object]:
        self.text_messages.append((chat_id, text))
        return {"code": 0}

    def send_card_to_chat(self, chat_id: str, card: dict[str, object]) -> dict[str, object]:
        self.card_messages.append((chat_id, card))
        return {"code": 0}


class FakeFrontdeskBackend:
    def __init__(self, *, signals=None, task_result=None, judgment_result=None, knowledge_result=None, close_result=None):
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

    def assess_close_loop(self, last_session, allow_execute=False):
        result = dict(self._close_result)
        if allow_execute:
            result["status"] = "closed"
        return result

    def list_frontdesk_capabilities(self):
        return {
            "bundle_id": "ai-da-guan-jia-openclaw",
            "display_name": "AI大管家",
            "short_description": "治理前台能力包",
            "frontdesk_scenes": [{"scene": "task_intake", "label": "给任务"}],
            "tool_contracts": [{"name": "route_task"}],
            "credential_guides": [{"id": "feishu_bot"}],
        }

    def get_run_status(self, run_id):
        return {"status": "found", "run_id": run_id, "task_text": "测试任务", "selected_skills": ["ai-da-guan-jia"]}

    def suggest_human_decision(self, context, user_context=None):
        return {
            "status": "suggested",
            "route": {"run_id": "adagj-approve", "selected_skills": ["ai-da-guan-jia"]},
            "recommended": "由你拍板，AI 负责比较与草案。",
            "not_recommended": "不要让 AI 直接做不可逆动作。",
            "why_human_now": "这是人类边界。",
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

    def test_handle_event_routes_text_message_and_sends_text_reply(self) -> None:
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
        self.assertIn("AI大管家 · 给任务", messenger.text_messages[0][1])

    def test_handle_event_ignores_duplicate_event(self) -> None:
        config = self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x")
        messenger = FakeMessenger()
        service = self.module.FeishuClawBridgeService(
            config,
            messenger=messenger,
            backend=FakeFrontdeskBackend(),
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

    def test_home_reply_lists_frontdesk_entrypoints(self) -> None:
        service = self.module.FeishuClawBridgeService(
            self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
            messenger=FakeMessenger(),
            backend=FakeFrontdeskBackend(),
        )
        reply = service.reply_to_frontdesk("首页", user_context={"chat_id": "oc_1"})
        self.assertEqual(reply.scene, "home")
        self.assertIn("给我接个任务", reply.as_text())
        self.assertIn("今天最该看什么", reply.as_text())

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
        self.assertIn("原始来源", reply.as_text())
        self.assertIn("ask.feishu / Aily", reply.as_text())
        self.assertIn("还缺什么", reply.as_text())

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

    def test_bundle_metadata_includes_install_prompt_and_status(self) -> None:
        service = self.module.FeishuClawBridgeService(
            self.module.BridgeConfig(app_id="cli_x", app_secret="sec_x"),
            messenger=FakeMessenger(),
            backend=FakeFrontdeskBackend(),
        )
        metadata = service.bundle_metadata()
        self.assertEqual(metadata["bundle_id"], "ai-da-guan-jia-openclaw")
        self.assertIn("请安装 AI大管家 技能", metadata["install_prompt"])
        self.assertIn("installation_state", metadata)
        self.assertIn("overall_status", metadata["installation_state"])

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


if __name__ == "__main__":
    unittest.main()
