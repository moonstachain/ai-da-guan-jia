from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path("/Users/hay2045/Documents/codex-ai-gua-jia-01")
SCRIPT_ROOT = PROJECT_ROOT / "work" / "ai-da-guan-jia" / "scripts"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class GetBijiDualTrackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPT_ROOT))
        cls.connector = load_module("test_get_biji_connector", SCRIPT_ROOT / "get_biji_connector.py")
        cls.ai_da_guan_jia = load_module("test_ai_da_guan_jia", SCRIPT_ROOT / "ai_da_guan_jia.py")

    def test_connector_ask_normalizes_answer_and_hits(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            response_path = Path(tempdir) / "response.json"
            with patch.dict(
                os.environ,
                {
                    "GET_BIJI_API_KEY": "test-key",
                    "GET_BIJI_TOPIC_ID": "topic-123",
                    "GET_BIJI_BASE_URL": "https://api.example.com/v1",
                },
                clear=False,
            ):
                with patch.object(
                    self.connector,
                    "_request_json",
                    return_value={
                        "answer": "这是答案",
                        "records": [
                            {
                                "title": "笔记一",
                                "content": "片段一",
                                "source": "doc-1",
                                "score": 0.91,
                            }
                        ],
                    },
                ):
                    result = self.connector.ask(question="帮我总结", raw_response_path=response_path)
                    self.assertTrue(result.success)
                    self.assertEqual(result.answer, "这是答案")
                    self.assertEqual(result.topic_id, "topic-123")
                    self.assertEqual(len(result.hits), 1)
                    self.assertEqual(result.hits[0]["title"], "笔记一")
                    self.assertTrue(response_path.exists())

    def test_connector_recall_keeps_empty_hits_successful(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            response_path = Path(tempdir) / "response.json"
            with patch.dict(
                os.environ,
                {
                    "GET_BIJI_API_KEY": "test-key",
                    "GET_BIJI_TOPIC_ID": "topic-456",
                },
                clear=False,
            ):
                with patch.object(self.connector, "_request_json", return_value={"records": []}):
                    result = self.connector.recall(query="查找这条笔记", raw_response_path=response_path, top_k=3)
                    self.assertTrue(result.success)
                    self.assertEqual(result.topic_id, "topic-456")
                    self.assertEqual(result.hits, [])
                    self.assertIn("no hits", result.verification_note)
                    self.assertTrue(response_path.exists())

    def test_connector_reads_state_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            env_path = Path(tempdir) / "get-biji.env"
            env_path.write_text(
                "\n".join(
                    [
                        "GET_BIJI_API_KEY=file-key",
                        "GET_BIJI_TOPIC_ID=file-topic",
                        "GET_BIJI_BASE_URL=https://open-api.example.com/getnote/openapi",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                with patch.object(self.connector, "STATE_ENV_PATH", env_path):
                    config = self.connector.GetBijiConfig.from_env()
                    self.assertEqual(config.api_key, "file-key")
                    self.assertEqual(config.topic_id, "file-topic")
                    self.assertEqual(config.base_url, "https://open-api.example.com/getnote/openapi")

    def test_plan_get_biji_actions_prefers_ask_for_natural_language_lookup(self) -> None:
        plan = self.ai_da_guan_jia.plan_get_biji_actions("帮我查上周那条客户分层笔记")
        self.assertEqual(plan["recommended_entrypoint"], "get_biji")
        self.assertEqual(plan["primary_action"], "get_biji.ask")
        self.assertEqual(plan["recommended_actions"][0]["inputs"]["question"], "帮我查上周那条客户分层笔记")

    def test_plan_get_biji_actions_prefers_recall_for_keyword_retrieval(self) -> None:
        plan = self.ai_da_guan_jia.plan_get_biji_actions("帮我找回客户分层")
        self.assertEqual(plan["primary_action"], "get_biji.recall")
        self.assertEqual(plan["recommended_actions"][0]["inputs"]["top_k"], 5)

    def test_plan_get_biji_actions_detects_ingest_link(self) -> None:
        plan = self.ai_da_guan_jia.plan_get_biji_actions("把这个 B站链接记到 Get笔记")
        self.assertEqual(plan["primary_action"], "get_biji.ingest_link")
        self.assertEqual(plan["recommended_actions"][0]["inputs"]["mode"], "submit-link")
        self.assertIn("<external-link>", plan["recommended_actions"][0]["cli_command"])

    def test_plan_get_biji_actions_detects_fetch_original(self) -> None:
        plan = self.ai_da_guan_jia.plan_get_biji_actions("帮我拿 note 1903496783305829808 的原始逐字稿")
        self.assertEqual(plan["primary_action"], "get_biji.fetch_original")
        self.assertEqual(plan["recommended_actions"][0]["inputs"]["note_id"], "1903496783305829808")

    def test_plan_get_biji_actions_builds_mixed_step_chain(self) -> None:
        plan = self.ai_da_guan_jia.plan_get_biji_actions("把这个视频记到 Get笔记里，然后给我逐字稿，后面我还要继续问它")
        self.assertEqual(plan["primary_action"], "get_biji.ingest_link")
        self.assertGreaterEqual(len(plan["recommended_actions"]), 2)
        self.assertEqual(plan["recommended_actions"][0]["inputs"]["mode"], "transcribe-link")
        self.assertEqual(plan["recommended_actions"][1]["action"], "get_biji.ask")

    def test_get_biji_signal_prefers_transcript_skill(self) -> None:
        signals = self.ai_da_guan_jia.detect_signals("帮我用 Get笔记 导入链接并找逐字稿")
        ranked = [
            {"name": "get-biji-transcript", "task_fit_score": 5},
            {"name": "ai-da-guan-jia", "task_fit_score": 2},
            {"name": "knowledge-orchestrator", "task_fit_score": 1},
        ]
        selected, omitted = self.ai_da_guan_jia.choose_skills("帮我用 Get笔记 导入链接并找逐字稿", ranked, signals, [])
        self.assertTrue(signals["get_biji"])
        self.assertIn("get-biji-transcript", selected)
        self.assertEqual(omitted, [])

    def test_feishu_km_signal_prefers_feishu_km_before_knowledge_orchestrator(self) -> None:
        signals = self.ai_da_guan_jia.detect_signals("先问飞书知识库，再帮我规划下一步")
        ranked = [
            {"name": "knowledge-orchestrator", "task_fit_score": 4},
            {"name": "feishu-km", "task_fit_score": 5},
            {"name": "ai-da-guan-jia", "task_fit_score": 2},
        ]
        selected, omitted = self.ai_da_guan_jia.choose_skills("先问飞书知识库，再帮我规划下一步", ranked, signals, [])
        self.assertTrue(signals["feishu_km"])
        self.assertTrue(signals["knowledge_first"])
        self.assertEqual(selected[:2], ["feishu-km", "knowledge-orchestrator"])
        self.assertEqual(omitted, [])

    def test_ingest_link_reuses_local_index(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            temp_root = Path(tempdir)
            run_dir = temp_root / "runs" / "adagj-test"
            run_dir.mkdir(parents=True, exist_ok=True)
            index_path = temp_root / "link-index.json"
            transcript_script = temp_root / "get_biji_transcript.py"
            transcript_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            index_payload = {
                "https://example.com/video": {
                    "note_id": "1903496783305829808",
                    "topic_id": "topic-xyz",
                    "success": True,
                    "note_title": "Existing note",
                    "transcript_txt": "/tmp/transcript.txt",
                }
            }
            index_path.write_text(json.dumps(index_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            args = self.ai_da_guan_jia.argparse.Namespace(
                link="https://example.com/video",
                mode="transcribe-link",
                topic_id="",
                timeout_seconds=120,
            )
            with patch.object(self.ai_da_guan_jia, "GET_BIJI_LINK_INDEX_PATH", index_path):
                with patch.object(self.ai_da_guan_jia, "GET_BIJI_CURRENT_ROOT", temp_root):
                    with patch.object(self.ai_da_guan_jia, "GET_BIJI_TRANSCRIPT_SCRIPT", transcript_script):
                        exit_code = self.ai_da_guan_jia.execute_get_biji_ingest_link(args, run_dir, "adagj-test")
                        record = json.loads((run_dir / "get-biji-record.json").read_text(encoding="utf-8"))
                        self.assertEqual(exit_code, 0)
                        self.assertTrue(record["success"])
                        self.assertTrue(record["metadata"]["deduped"])
                        self.assertEqual(record["metadata"]["note_id"], "1903496783305829808")

    def test_command_route_writes_get_biji_action_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "runs" / "adagj-route-test"
            run_dir.mkdir(parents=True, exist_ok=True)
            fake_skills = [
                {
                    "name": "get-biji-transcript",
                    "description": "Get笔记 transcript",
                    "path": "/tmp/get-biji-transcript",
                    "is_core": True,
                },
                {
                    "name": "ai-da-guan-jia",
                    "description": "Router",
                    "path": "/tmp/ai-da-guan-jia",
                    "is_core": True,
                },
            ]
            fake_materials = {
                "github_task": {
                    "classification": {"task_key": "tsk-route-test"},
                    "skip_github_management": True,
                }
            }
            args = self.ai_da_guan_jia.argparse.Namespace(
                prompt="把这个视频记到 Get笔记里，然后给我逐字稿，后面我还要继续问它",
                run_id=None,
            )
            stdout = io.StringIO()
            with patch.object(self.ai_da_guan_jia, "discover_skills", return_value=fake_skills):
                with patch.object(self.ai_da_guan_jia, "load_governance_signals", return_value={"status": "missing"}):
                    with patch.object(self.ai_da_guan_jia, "allocate_run_id", return_value="adagj-route-test"):
                        with patch.object(self.ai_da_guan_jia, "run_dir_for", return_value=run_dir):
                            with patch.object(self.ai_da_guan_jia, "prepare_github_materials", return_value=fake_materials):
                                with patch.object(self.ai_da_guan_jia, "sync_github_run", return_value=(0, "skipped")):
                                    with contextlib.redirect_stdout(stdout):
                                        exit_code = self.ai_da_guan_jia.command_route(args)
            route_payload = json.loads((run_dir / "route.json").read_text(encoding="utf-8"))
            rendered = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertEqual(route_payload["recommended_entrypoint"], "get_biji")
            self.assertEqual(route_payload["primary_action"], "get_biji.ingest_link")
            self.assertIn("recommended_actions", route_payload)
            self.assertIn("get-biji-transcript", route_payload["selected_skills"])
            self.assertIn("primary_action: get_biji.ingest_link", rendered)
            self.assertIn("next_command_1:", rendered)

    def test_command_route_maps_plain_note_lookup_to_get_biji(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "runs" / "adagj-route-ask"
            run_dir.mkdir(parents=True, exist_ok=True)
            fake_skills = [
                {
                    "name": "get-biji-transcript",
                    "description": "Get笔记 transcript",
                    "path": "/tmp/get-biji-transcript",
                    "is_core": True,
                }
            ]
            fake_materials = {
                "github_task": {
                    "classification": {"task_key": "tsk-route-ask"},
                    "skip_github_management": True,
                }
            }
            args = self.ai_da_guan_jia.argparse.Namespace(prompt="帮我查上周那条客户分层笔记", run_id=None)
            with patch.object(self.ai_da_guan_jia, "discover_skills", return_value=fake_skills):
                with patch.object(self.ai_da_guan_jia, "load_governance_signals", return_value={"status": "missing"}):
                    with patch.object(self.ai_da_guan_jia, "allocate_run_id", return_value="adagj-route-ask"):
                        with patch.object(self.ai_da_guan_jia, "run_dir_for", return_value=run_dir):
                            with patch.object(self.ai_da_guan_jia, "prepare_github_materials", return_value=fake_materials):
                                with patch.object(self.ai_da_guan_jia, "sync_github_run", return_value=(0, "skipped")):
                                    exit_code = self.ai_da_guan_jia.command_route(args)
            route_payload = json.loads((run_dir / "route.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(route_payload["recommended_entrypoint"], "get_biji")
            self.assertEqual(route_payload["primary_action"], "get_biji.ask")
            self.assertIn("get-biji-transcript", route_payload["selected_skills"])

    def test_command_route_keeps_non_get_biji_prompts_without_get_biji_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "runs" / "adagj-route-non-biji"
            run_dir.mkdir(parents=True, exist_ok=True)
            fake_skills = [
                {
                    "name": "skill-creator",
                    "description": "Skill creator",
                    "path": "/tmp/skill-creator",
                    "is_core": True,
                }
            ]
            fake_materials = {
                "github_task": {
                    "classification": {"task_key": "tsk-route-non-biji"},
                    "skip_github_management": True,
                }
            }
            args = self.ai_da_guan_jia.argparse.Namespace(prompt="帮我做一个新 skill", run_id=None)
            with patch.object(self.ai_da_guan_jia, "discover_skills", return_value=fake_skills):
                with patch.object(self.ai_da_guan_jia, "load_governance_signals", return_value={"status": "missing"}):
                    with patch.object(self.ai_da_guan_jia, "allocate_run_id", return_value="adagj-route-non-biji"):
                        with patch.object(self.ai_da_guan_jia, "run_dir_for", return_value=run_dir):
                            with patch.object(self.ai_da_guan_jia, "prepare_github_materials", return_value=fake_materials):
                                with patch.object(self.ai_da_guan_jia, "sync_github_run", return_value=(0, "skipped")):
                                    exit_code = self.ai_da_guan_jia.command_route(args)
            route_payload = json.loads((run_dir / "route.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertNotIn("recommended_entrypoint", route_payload)

    def test_command_route_maps_feishu_knowledge_prompt_to_feishu_km_manual_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "runs" / "adagj-route-feishu-km"
            run_dir.mkdir(parents=True, exist_ok=True)
            fake_skills = [
                {
                    "name": "feishu-km",
                    "description": "Feishu knowledge ask",
                    "path": "/tmp/feishu-km",
                    "is_core": True,
                },
                {
                    "name": "knowledge-orchestrator",
                    "description": "Knowledge synth",
                    "path": "/tmp/knowledge-orchestrator",
                    "is_core": True,
                },
            ]
            fake_materials = {
                "github_task": {
                    "classification": {"task_key": "tsk-route-feishu-km"},
                    "skip_github_management": True,
                }
            }
            args = self.ai_da_guan_jia.argparse.Namespace(prompt="先问飞书知识库，再帮我规划下一步", run_id=None)
            with patch.dict(os.environ, {}, clear=True):
                with patch.object(self.ai_da_guan_jia, "discover_skills", return_value=fake_skills):
                    with patch.object(self.ai_da_guan_jia, "load_governance_signals", return_value={"status": "missing"}):
                        with patch.object(self.ai_da_guan_jia, "allocate_run_id", return_value="adagj-route-feishu-km"):
                            with patch.object(self.ai_da_guan_jia, "run_dir_for", return_value=run_dir):
                                with patch.object(self.ai_da_guan_jia, "prepare_github_materials", return_value=fake_materials):
                                    with patch.object(self.ai_da_guan_jia, "sync_github_run", return_value=(0, "skipped")):
                                        exit_code = self.ai_da_guan_jia.command_route(args)
            route_payload = json.loads((run_dir / "route.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(route_payload["recommended_entrypoint"], "feishu_km")
            self.assertEqual(route_payload["primary_action"], "feishu_km.prepare_manual")
            self.assertEqual(route_payload["knowledge_source_type"], "feishu_aily_km")
            self.assertEqual(route_payload["selected_skills"][:2], ["feishu-km", "knowledge-orchestrator"])
            self.assertIn("feishu-km-request.json", " ".join(route_payload["verification_targets"]))

    def test_feishu_km_prepare_and_record_manual_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "runs" / "adagj-feishu-km"
            run_dir.mkdir(parents=True, exist_ok=True)
            prepare_args = self.ai_da_guan_jia.argparse.Namespace(
                question="帮我查这周关于客户分层的关键结论",
                source_url=self.ai_da_guan_jia.FEISHU_KM_DEFAULT_SOURCE_URL,
                run_id="adagj-feishu-km",
            )
            exit_code = self.ai_da_guan_jia.execute_feishu_km_prepare_manual(prepare_args, run_dir, "adagj-feishu-km")
            self.assertEqual(exit_code, 0)
            record_args = self.ai_da_guan_jia.argparse.Namespace(
                answer_text="原始回答：本周客户分层重点是先区分高意向复购人群。",
                answer_file=None,
                run_id="adagj-feishu-km",
                question="",
                source_url=self.ai_da_guan_jia.FEISHU_KM_DEFAULT_SOURCE_URL,
                followup=["这条判断的证据来源是什么？"],
                confidence_note="直接来自 ask.feishu 复制回答，尚未核对原始出处。",
            )
            exit_code = self.ai_da_guan_jia.execute_feishu_km_record_manual(record_args, run_dir, "adagj-feishu-km")
            record_payload = json.loads((run_dir / "feishu-km-record.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(record_payload["knowledge_source_type"], "feishu_aily_km")
            self.assertEqual(record_payload["source"], "ask.feishu")
            self.assertEqual(record_payload["question"], "帮我查这周关于客户分层的关键结论")
            self.assertIn("高意向复购人群", record_payload["raw_answer"])
            self.assertEqual(record_payload["followup_candidates"], ["这条判断的证据来源是什么？"])

    def test_feishu_km_api_readiness_reports_missing_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "runs" / "adagj-feishu-km-readiness"
            run_dir.mkdir(parents=True, exist_ok=True)
            script_path = Path(tempdir) / "feishu_km.py"
            script_path.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            args = self.ai_da_guan_jia.argparse.Namespace(script=str(script_path), run_id="adagj-feishu-km-readiness")
            with patch.dict(os.environ, {}, clear=True):
                exit_code = self.ai_da_guan_jia.execute_feishu_km_api_readiness(args, run_dir, "adagj-feishu-km-readiness")
            readiness_payload = json.loads((run_dir / "feishu-km-api-readiness.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 1)
            self.assertTrue(readiness_payload["script_exists"])
            self.assertFalse(readiness_payload["ready_for_live_api"])
            self.assertFalse(readiness_payload["app_id_present"])
            self.assertFalse(readiness_payload["app_secret_present"])


if __name__ == "__main__":
    unittest.main()
