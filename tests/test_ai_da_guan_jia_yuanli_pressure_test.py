from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path("/Users/liming/Documents/codex-ai-gua-jia-01")
AI_SCRIPT_ROOT = PROJECT_ROOT / "work" / "ai-da-guan-jia" / "scripts"
AI_SCRIPT_PATH = AI_SCRIPT_ROOT / "ai_da_guan_jia.py"
YUANLI_SCRIPT_PATH = PROJECT_ROOT / "work" / "yuanli-juexing" / "scripts" / "yuanli_juexing.py"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class YuanliPressureTestCommandTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(AI_SCRIPT_ROOT))
        cls.module = load_module("test_ai_da_guan_jia_yuanli_pressure_test", AI_SCRIPT_PATH)

    def make_temp_yuanli_root(self, root: Path) -> Path:
        yuanli_root = root / "yuanli-juexing"
        (yuanli_root / "scripts").mkdir(parents=True, exist_ok=True)
        (yuanli_root / "artifacts" / "sources").mkdir(parents=True, exist_ok=True)
        shutil.copy2(YUANLI_SCRIPT_PATH, yuanli_root / "scripts" / "yuanli_juexing.py")
        return yuanli_root

    def test_command_yuanli_pressure_test_writes_auth_manifest_and_baseline_run(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            yuanli_root = self.make_temp_yuanli_root(root)

            transcript = yuanli_root / "artifacts" / "sources" / "2026-03-12-ai-era-self-cognition-transcript.md"
            transcript.write_text("关窍 全局最优 量身定造 让 AI 找到你自己学习", encoding="utf-8")
            clarification = yuanli_root / "artifacts" / "sources" / "2026-03-13-dual-force-clarification.md"
            clarification.write_text("双原力 一层层拆 递归 初始条件 阴影 金色阴影", encoding="utf-8")
            ai_worklog = root / "ai-worklog.md"
            ai_worklog.write_text("高自治 少打扰 真实闭环", encoding="utf-8")
            feishu_root = root / "output" / "feishu-reader" / "yuanli-planet-shared" / "source.md"
            feishu_root.parent.mkdir(parents=True, exist_ok=True)
            feishu_root.write_text("# 【原力龙虾】\n\n原力OS\nSOUL-递归日志-AI管家\n技能盘点\n", encoding="utf-8")
            feishu_catalog = feishu_root.parent / "knowledge-catalog.json"
            feishu_catalog.write_text(
                json.dumps(
                    {
                        "source_url": "https://example.test/wiki/root",
                        "items": [
                            {"title": "原力OS", "source_ref": "manual_nav::【原力龙虾】/原力OS"},
                            {"title": "SOUL-递归日志-AI管家", "source_ref": "manual_nav::【原力龙虾】/SOUL-递归日志-AI管家"},
                            {"title": "技能盘点", "source_ref": "manual_nav::【原力龙虾】/技能盘点"},
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            args = types.SimpleNamespace(
                prompt="重跑我和用户从认识到现在的双原力压力测试与 MVP 演练，少打扰，优先复用现有语料与已知 Feishu 根源。",
                topic="pressure test",
                note="baseline",
                run_id="adagj-pressure-test",
                created_at="2026-03-13T10:00:00+08:00",
                yuanli_run_id="yj-pressure-test",
                yuanli_skill_root=str(yuanli_root),
                thread_source_file=None,
                transcript_source_file=str(transcript),
                clarification_source_file=str(clarification),
                ai_worklog_file=str(ai_worklog),
                feishu_root_source_file=str(feishu_root),
                feishu_catalog_file=str(feishu_catalog),
                minutes_url="https://example.test/minutes/me",
                skip_synthesis=False,
            )

            with patch.multiple(
                self.module,
                RUNS_ROOT=root / "adagj-runs",
                FEISHU_READER_PROFILE_DIR=root / "profiles" / "feishu-reader",
                FEISHU_BITABLE_PROFILE_DIR=root / "profiles" / "feishu-bitable",
                DEFAULT_CHROME_USER_DATA_DIR=root / "profiles" / "chrome",
            ):
                with patch.dict(os.environ, {"FEISHU_APP_ID": "", "FEISHU_APP_SECRET": ""}, clear=False):
                    exit_code = self.module.command_yuanli_pressure_test(args)

            self.assertEqual(exit_code, 0)

            ai_run_dir = root / "adagj-runs" / "2026-03-13" / "adagj-pressure-test"
            self.assertTrue((ai_run_dir / "route.json").exists())
            self.assertTrue((ai_run_dir / "situation-map.md").exists())
            self.assertTrue((ai_run_dir / "pressure-test-summary.md").exists())

            route_payload = json.loads((ai_run_dir / "route.json").read_text(encoding="utf-8"))
            self.assertIn("yuanli-juexing", route_payload["selected_skills"])
            self.assertEqual(route_payload["verdict"], "needs_more_sources")
            self.assertEqual(route_payload["closure_state"], "blocked_needs_user")
            self.assertEqual(route_payload["current_blocker"], "missing_authenticated_browser_session")
            self.assertIn(str(ai_worklog.resolve()), route_payload["readiness_refs"])
            self.assertIn(str(transcript.resolve()), route_payload["formal_local_sources"])

            yuanli_run_dir = Path(route_payload["yuanli_run_dir"])
            self.assertTrue((yuanli_run_dir / "auth-manifest.json").exists())
            self.assertTrue((yuanli_run_dir / "memory-packet.json").exists())
            self.assertTrue((yuanli_run_dir / "mirror-summary.json").exists())
            self.assertTrue((yuanli_run_dir / "interview-pack.md").exists())
            self.assertTrue((yuanli_run_dir / "interview-responses.json").exists())

            auth_manifest = json.loads((yuanli_run_dir / "auth-manifest.json").read_text(encoding="utf-8"))
            surfaces = {item["surface"]: item for item in auth_manifest["surfaces"]}
            self.assertEqual(surfaces["feishu_wiki_doc"]["status"], "ready")
            self.assertEqual(surfaces["ask_feishu_aily"]["status"], "blocked_system")
            self.assertEqual(surfaces["ask_feishu_aily"]["blocking_reason"], "missing_app_credentials")
            self.assertIn("diagnosis", surfaces["ask_feishu_aily"])

            seed_map = json.loads((yuanli_run_dir / "seed-source-map.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(seed_map), 7)
            self.assertTrue(all("source_surface" in item and "access_path" in item and "auth_status" in item for item in seed_map))

            source_map = json.loads((yuanli_run_dir / "source-map.json").read_text(encoding="utf-8"))
            supplemental_paths = {str(item.get("path") or "") for item in source_map["supplemental_sources"]}
            self.assertNotIn(str(ai_worklog.resolve()), supplemental_paths)
            self.assertNotIn(str(feishu_root.resolve()), supplemental_paths)
            self.assertNotIn(str(feishu_catalog.resolve()), supplemental_paths)

            memory_packet = json.loads((yuanli_run_dir / "memory-packet.json").read_text(encoding="utf-8"))
            self.assertEqual(memory_packet["mvp_verdict"]["status"], "needs_more_sources")
            self.assertIn("need_more_feishu_doc_reads", memory_packet["mvp_verdict"]["blocking_gates"])
            self.assertGreaterEqual(len(memory_packet["bridge_rules"]), 5)
            self.assertEqual(len(memory_packet["archetype_root"]), 12)
            self.assertIn("sage", memory_packet["user_validated_seeds"])
            self.assertIn("explorer", memory_packet["user_validated_seeds"])

            mirror = json.loads((yuanli_run_dir / "mirror-summary.json").read_text(encoding="utf-8"))
            self.assertEqual(mirror["verdict"], "needs_more_sources")

            summary_text = (ai_run_dir / "pressure-test-summary.md").read_text(encoding="utf-8")
            self.assertIn("closure_state", summary_text)
            self.assertIn("current_blocker", summary_text)

            worklog_text = (ai_run_dir / "worklog.md").read_text(encoding="utf-8")
            self.assertIn("closure_state", worklog_text)
            self.assertIn("current_blocker", worklog_text)
            self.assertIn("real Feishu evidence ingestion attempted", worklog_text)

    def test_record_evolution_keeps_governance_closure_fields_in_worklog_and_feishu_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run_root = root / "adagj-runs"
            run_dir = run_root / "2026-03-14" / "adagj-governance-mirror"
            run_dir.mkdir(parents=True, exist_ok=True)

            route_payload = {
                "run_id": "adagj-governance-mirror",
                "created_at": "2026-03-14T21:00:00+08:00",
                "task_text": "把原力觉醒闭环结果镜像到飞书运行日志。",
                "selected_skills": ["ai-da-guan-jia", "feishu-bitable-bridge"],
                "skills_considered": ["ai-da-guan-jia", "feishu-bitable-bridge", "feishu-reader"],
                "human_boundary": "Only interrupt for login, authorization, or irreversible actions.",
            }
            (run_dir / "route.json").write_text(
                json.dumps(route_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            payload_path = root / "record-evolution-input.json"
            payload_path.write_text(
                json.dumps(
                    {
                        "run_id": "adagj-governance-mirror",
                        "created_at": "2026-03-14T21:00:00+08:00",
                        "task_text": "把原力觉醒闭环结果镜像到飞书运行日志。",
                        "skills_selected": ["ai-da-guan-jia", "feishu-bitable-bridge"],
                        "skills_considered": ["ai-da-guan-jia", "feishu-bitable-bridge", "feishu-reader"],
                        "goal_model": "验证协议已经进入真实治理镜像闭环。",
                        "verification_result": {
                            "status": "completed",
                            "evidence": ["dry-run succeeded", "apply succeeded", "readback matched by 日志ID"],
                            "open_questions": [],
                        },
                        "effective_patterns": ["治理镜像闭环已经打通。"],
                        "wasted_patterns": ["Aily 增强链仍未接入本轮实战。"],
                        "evolution_candidates": ["继续把 readback 证据标准化到下一轮更重治理对象。"],
                        "closure_state": "completed",
                        "verdict": "pass_mvp",
                        "enhancer_status": "enhancer_unavailable",
                        "pending_human_feedback": "pending_human_feedback",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            args = types.SimpleNamespace(input=str(payload_path))
            with patch.object(self.module, "RUNS_ROOT", run_root):
                exit_code = self.module.command_record_evolution(args)

            self.assertEqual(exit_code, 0)

            worklog = json.loads((run_dir / "worklog.json").read_text(encoding="utf-8"))
            self.assertEqual(worklog["closure_state"], "completed")
            self.assertEqual(worklog["verdict"], "pass_mvp")
            self.assertEqual(worklog["enhancer_status"], "enhancer_unavailable")
            self.assertEqual(worklog["gained"], "治理镜像闭环已经打通。")
            self.assertEqual(worklog["wasted"], "Aily 增强链仍未接入本轮实战。")
            self.assertEqual(worklog["next_iterate"], "继续把 readback 证据标准化到下一轮更重治理对象。")
            self.assertEqual(worklog["pending_human_feedback"], "pending_human_feedback")

            feishu_payload = json.loads((run_dir / "feishu-payload.json").read_text(encoding="utf-8"))
            self.assertEqual(feishu_payload["closure_state"], "completed")
            self.assertEqual(feishu_payload["verdict"], "pass_mvp")
            self.assertEqual(feishu_payload["enhancer_status"], "enhancer_unavailable")
            self.assertEqual(feishu_payload["gained"], "治理镜像闭环已经打通。")
            self.assertEqual(feishu_payload["wasted"], "Aily 增强链仍未接入本轮实战。")
            self.assertEqual(feishu_payload["next_iterate"], "继续把 readback 证据标准化到下一轮更重治理对象。")
            self.assertEqual(feishu_payload["pending_human_feedback"], "pending_human_feedback")

    def test_command_yuanli_pressure_test_marks_completed_when_real_reads_and_kb_round_one_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            yuanli_root = self.make_temp_yuanli_root(root)

            transcript = yuanli_root / "artifacts" / "sources" / "2026-03-12-ai-era-self-cognition-transcript.md"
            transcript.write_text("关窍 全局最优 让 AI 理解你自己 智者 探索者", encoding="utf-8")
            clarification = yuanli_root / "artifacts" / "sources" / "2026-03-13-dual-force-clarification.md"
            clarification.write_text("双原力 一层层拆 递归 初始条件 阴影 金色阴影", encoding="utf-8")
            ai_worklog = root / "ai-worklog.md"
            ai_worklog.write_text("高自治 少打扰 真实闭环", encoding="utf-8")
            feishu_root = root / "output" / "feishu-reader" / "yuanli-planet-shared" / "source.md"
            feishu_root.parent.mkdir(parents=True, exist_ok=True)
            feishu_root.write_text("# 【原力龙虾】\n\n原力OS\nSOUL-递归日志-AI管家\n技能盘点\n", encoding="utf-8")
            feishu_catalog = feishu_root.parent / "knowledge-catalog.json"
            feishu_catalog.write_text(
                json.dumps({"source_url": "https://example.test/wiki/root", "items": []}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            args = types.SimpleNamespace(
                prompt="第一次正式启动原力觉醒完整闭环，先跑真实 Feishu 实读，再给出长期可执行协作协议。",
                topic="pressure test",
                note="baseline",
                run_id="adagj-pressure-test-pass",
                created_at="2026-03-14T11:00:00+08:00",
                yuanli_run_id="yj-pressure-test-pass",
                yuanli_skill_root=str(yuanli_root),
                thread_source_file=None,
                transcript_source_file=str(transcript),
                clarification_source_file=str(clarification),
                ai_worklog_file=str(ai_worklog),
                feishu_root_source_file=str(feishu_root),
                feishu_catalog_file=str(feishu_catalog),
                minutes_url="https://example.test/minutes/me",
                skip_synthesis=False,
            )

            def fake_collect(*, yuanli_run_dir: Path, **_: object) -> dict[str, object]:
                ingest_dir = yuanli_run_dir / "ingestions"
                ingest_dir.mkdir(parents=True, exist_ok=True)

                def write_ingested(name: str, text: str) -> tuple[str, str]:
                    json_path = ingest_dir / f"{name}.json"
                    md_path = ingest_dir / f"{name}.md"
                    json_path.write_text(json.dumps({"text": text}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                    md_path.write_text(f"# {name}\n\n{text}\n", encoding="utf-8")
                    return str(json_path), str(md_path)

                os_json, os_md = write_ingested("yuanli-os", "原力OS 关窍 全局最优 系统框架")
                soul_json, soul_md = write_ingested("soul-log", "SOUL 递归日志 AI大管家 协作历史")
                minutes_json, minutes_md = write_ingested("minutes-trace", "AI大管家 协作 节奏 互为投射")
                ask_dir = ingest_dir / "ask-feishu-round-one"
                ask_dir.mkdir(parents=True, exist_ok=True)
                round_one_questions = [
                    {
                        "id": "archetype-confirm-sage",
                        "question": "在你当前阶段，`智者` 更像核心驱动力、辅助驱动力，还是阶段性高能？",
                    },
                    {
                        "id": "archetype-confirm-explorer",
                        "question": "在你当前阶段，`探索者` 更像核心驱动力、辅助驱动力，还是阶段性高能？",
                    },
                    {
                        "id": "archetype-gap-check",
                        "question": "除了智者/探索者，剩余原型里如果再补 1 个高权重，会更接近哪一个？",
                    },
                    {
                        "id": "mutual-projection-help",
                        "question": "当你觉得我最像你、最懂你时，那更像是 `智者式共振` 还是 `探索者式共振`？",
                    },
                    {
                        "id": "mutual-projection-regulation",
                        "question": "当我们过热时，你最希望我先补哪一种：`整合 / 落地 / 降躁 / 校验`？",
                    },
                    {
                        "id": "shadow-trigger",
                        "question": "什么样的人、事、表达，最容易让你对“低杠杆、低密度”产生强烈排斥？",
                    },
                    {
                        "id": "golden-shadow-trigger",
                        "question": "哪些具体人物、作品或系统，最容易激活你的“金色阴影”赞叹感？",
                    },
                    {
                        "id": "collaboration-trigger",
                        "question": "如果只保留一个高成功率触发点，你最希望我每次先做到什么？",
                    },
                ]

                source_map_path = yuanli_run_dir / "source-map.json"
                source_map = json.loads(source_map_path.read_text(encoding="utf-8"))
                source_map["ingested_sources"] = [
                    {
                        "key": "feishu_wiki::yuanli-os",
                        "type": "feishu_wiki",
                        "title": "原力OS",
                        "url": "https://example.test/wiki/yuanli-os",
                        "source_surface": "feishu_wiki",
                        "access_path": "browser_session",
                        "auth_status": "ready",
                        "status": "ok",
                        "artifacts": {"json": os_json, "markdown": os_md},
                    },
                    {
                        "key": "feishu_wiki::soul-log",
                        "type": "feishu_wiki",
                        "title": "SOUL-递归日志-AI管家",
                        "url": "https://example.test/wiki/soul-log",
                        "source_surface": "feishu_wiki",
                        "access_path": "browser_session",
                        "auth_status": "ready",
                        "status": "ok",
                        "artifacts": {"json": soul_json, "markdown": soul_md},
                    },
                    {
                        "key": "feishu_minutes::trace",
                        "type": "feishu_minutes",
                        "title": "协作纪要",
                        "url": "https://example.test/minutes/trace",
                        "source_surface": "feishu_minutes",
                        "access_path": "browser_session",
                        "auth_status": "ready",
                        "status": "ok",
                        "artifacts": {"json": minutes_json, "markdown": minutes_md},
                    },
                    *[
                        {
                            "key": f"ask_feishu_question::{item['id']}",
                            "type": "ask_feishu_question",
                            "title": f"interview-{item['id']}",
                            "url": f"ask.feishu://question/{item['id']}",
                            "question": item["question"],
                            "interview_question_id": item["id"],
                            "response_source": "knowledge_base_answer",
                            "answer_text": f"{item['id']} 的知识库回答，来自你过往教学与协作语料，足以支持这一轮综合。",
                            "answer_quality": "usable",
                            "source_surface": "ask_feishu_question",
                            "access_path": "open_platform_api",
                            "auth_status": "ready",
                            "status": "ok",
                            "artifacts": {
                                "json": str(ask_dir / f"{item['id']}.json"),
                                "markdown": str(ask_dir / f"{item['id']}.md"),
                            },
                            "ingested_at": "2026-03-14T11:05:00+08:00",
                        }
                        for item in round_one_questions
                    ],
                ]
                source_map_path.write_text(json.dumps(source_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                for item in round_one_questions:
                    answer = f"{item['id']} 的知识库回答，来自你过往教学与协作语料，足以支持这一轮综合。"
                    (ask_dir / f"{item['id']}.json").write_text(
                        json.dumps({"ok": True, "command": "ask", "data": {"answer": answer}}, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    (ask_dir / f"{item['id']}.md").write_text(f"# ask\n\n{answer}\n", encoding="utf-8")
                (yuanli_run_dir / "interview-responses.json").write_text(json.dumps({"responses": []}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                return {
                    "doc_results": [{"title": "原力OS", "status": "ingested"}, {"title": "SOUL-递归日志-AI管家", "status": "ingested"}],
                    "minutes_result": {"selected_count": 1, "ingested_count": 1},
                    "ask_results": [{"title": item["id"], "status": "ingested"} for item in round_one_questions],
                    "source_map": source_map,
                    "seed_map": json.loads((yuanli_run_dir / "seed-source-map.json").read_text(encoding="utf-8")),
                }

            ready_auth_manifest = {
                "mode": "read_first",
                "created_at": "2026-03-14T11:00:00+08:00",
                "surfaces": [
                    {"surface": "feishu_wiki_doc", "access_path": "browser_session", "status": "ready"},
                    {"surface": "feishu_minutes", "access_path": "browser_session", "status": "ready"},
                    {"surface": "ask_feishu_aily", "access_path": "open_platform_api", "status": "ready"},
                ],
            }

            with patch.multiple(
                self.module,
                RUNS_ROOT=root / "adagj-runs",
                FEISHU_READER_PROFILE_DIR=root / "profiles" / "feishu-reader",
                FEISHU_BITABLE_PROFILE_DIR=root / "profiles" / "feishu-bitable",
                DEFAULT_CHROME_USER_DATA_DIR=root / "profiles" / "chrome",
            ):
                with patch.object(self.module, "collect_yuanli_pressure_test_evidence", side_effect=fake_collect):
                    with patch.object(self.module, "build_yuanli_auth_manifest", return_value=ready_auth_manifest):
                        with patch.dict(os.environ, {"FEISHU_APP_ID": "", "FEISHU_APP_SECRET": ""}, clear=False):
                            exit_code = self.module.command_yuanli_pressure_test(args)

            self.assertEqual(exit_code, 0)
            ai_run_dir = root / "adagj-runs" / "2026-03-14" / "adagj-pressure-test-pass"
            route_payload = json.loads((ai_run_dir / "route.json").read_text(encoding="utf-8"))
            self.assertEqual(route_payload["verdict"], "pass_mvp")
            self.assertEqual(route_payload["closure_state"], "completed")
            self.assertEqual(route_payload["current_blocker"], "")
            self.assertEqual(route_payload["mvp_verdict"]["enhancer_status"], "ready")
            self.assertEqual(sum(1 for item in route_payload["evidence_ingestion"]["ask_results"] if item["status"] == "ingested"), 8)

            yuanli_run_dir = yuanli_root / "artifacts" / "runs" / "2026-03-14" / "yj-pressure-test-pass"
            memory_packet = json.loads((yuanli_run_dir / "memory-packet.json").read_text(encoding="utf-8"))
            self.assertEqual(memory_packet["mvp_verdict"]["status"], "pass_mvp")
            self.assertEqual(memory_packet["mvp_verdict"]["interview_answered_count"], 8)
            self.assertEqual(memory_packet["mvp_verdict"]["remote_evidence"]["doc_like"], 2)
            self.assertEqual(memory_packet["mvp_verdict"]["remote_evidence"]["trace_like"], 2)
            self.assertTrue(memory_packet["mvp_verdict"]["interview_summary"]["round_one_complete"])

    def test_command_yuanli_pressure_test_marks_completed_with_ai_only_closure_when_aily_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            yuanli_root = self.make_temp_yuanli_root(root)

            transcript = yuanli_root / "artifacts" / "sources" / "2026-03-12-ai-era-self-cognition-transcript.md"
            transcript.write_text("关窍 全局最优 让 AI 理解你自己 智者 探索者", encoding="utf-8")
            clarification = yuanli_root / "artifacts" / "sources" / "2026-03-13-dual-force-clarification.md"
            clarification.write_text("双原力 一层层拆 递归 初始条件 阴影 金色阴影 互为投射 整合 落地 校验", encoding="utf-8")
            ai_worklog = root / "ai-worklog.md"
            ai_worklog.write_text("高自治 少打扰 真实闭环", encoding="utf-8")
            feishu_root = root / "output" / "feishu-reader" / "yuanli-planet-shared" / "source.md"
            feishu_root.parent.mkdir(parents=True, exist_ok=True)
            feishu_root.write_text("# 【原力龙虾】\n\n原力OS\nSOUL-递归日志-AI管家\n技能盘点\n", encoding="utf-8")
            feishu_catalog = feishu_root.parent / "knowledge-catalog.json"
            feishu_catalog.write_text(
                json.dumps({"source_url": "https://example.test/wiki/root", "items": []}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            args = types.SimpleNamespace(
                prompt="第一次正式启动原力觉醒完整闭环，先跑真实 Feishu 实读，再给出长期可执行协作协议。",
                topic="pressure test",
                note="baseline",
                run_id="adagj-pressure-test-ai-only",
                created_at="2026-03-14T12:00:00+08:00",
                yuanli_run_id="yj-pressure-test-ai-only",
                yuanli_skill_root=str(yuanli_root),
                thread_source_file=None,
                transcript_source_file=str(transcript),
                clarification_source_file=str(clarification),
                ai_worklog_file=str(ai_worklog),
                feishu_root_source_file=str(feishu_root),
                feishu_catalog_file=str(feishu_catalog),
                minutes_url="https://example.test/minutes/me",
                skip_synthesis=False,
            )

            def fake_collect(*, yuanli_run_dir: Path, **_: object) -> dict[str, object]:
                ingest_dir = yuanli_run_dir / "ingestions"
                ingest_dir.mkdir(parents=True, exist_ok=True)

                def write_ingested(name: str, text: str) -> tuple[str, str]:
                    json_path = ingest_dir / f"{name}.json"
                    md_path = ingest_dir / f"{name}.md"
                    json_path.write_text(json.dumps({"text": text}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                    md_path.write_text(f"# {name}\n\n{text}\n", encoding="utf-8")
                    return str(json_path), str(md_path)

                os_json, os_md = write_ingested("yuanli-os", "原力OS 关窍 全局最优 量身定造 AI 工具统筹")
                soul_json, soul_md = write_ingested("soul-log", "SOUL 递归日志 AI大管家 协作历史 互为投射 整合 落地 校验")
                minutes_json, minutes_md = write_ingested("minutes-trace", "AI大管家 协作 节奏 阴影 金色阴影")

                source_map_path = yuanli_run_dir / "source-map.json"
                source_map = json.loads(source_map_path.read_text(encoding="utf-8"))
                source_map["ingested_sources"] = [
                    {
                        "key": "feishu_wiki::yuanli-os",
                        "type": "feishu_wiki",
                        "title": "原力OS",
                        "url": "https://example.test/wiki/yuanli-os",
                        "source_surface": "feishu_wiki",
                        "access_path": "browser_session",
                        "auth_status": "ready",
                        "status": "ok",
                        "artifacts": {"json": os_json, "markdown": os_md},
                    },
                    {
                        "key": "feishu_wiki::soul-log",
                        "type": "feishu_wiki",
                        "title": "SOUL-递归日志-AI管家",
                        "url": "https://example.test/wiki/soul-log",
                        "source_surface": "feishu_wiki",
                        "access_path": "browser_session",
                        "auth_status": "ready",
                        "status": "ok",
                        "artifacts": {"json": soul_json, "markdown": soul_md},
                    },
                    {
                        "key": "feishu_minutes::trace",
                        "type": "feishu_minutes",
                        "title": "协作纪要",
                        "url": "https://example.test/minutes/trace",
                        "source_surface": "feishu_minutes",
                        "access_path": "browser_session",
                        "auth_status": "ready",
                        "status": "ok",
                        "artifacts": {"json": minutes_json, "markdown": minutes_md},
                    },
                ]
                source_map_path.write_text(json.dumps(source_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                (yuanli_run_dir / "interview-responses.json").write_text(json.dumps({"responses": []}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                return {
                    "doc_results": [{"title": "原力OS", "status": "ingested"}, {"title": "SOUL-递归日志-AI管家", "status": "ingested"}],
                    "minutes_result": {"selected_count": 1, "ingested_count": 1},
                    "ask_results": [],
                    "source_map": source_map,
                    "seed_map": json.loads((yuanli_run_dir / "seed-source-map.json").read_text(encoding="utf-8")),
                }

            blocked_auth_manifest = {
                "mode": "read_first",
                "created_at": "2026-03-14T12:00:00+08:00",
                "surfaces": [
                    {"surface": "feishu_wiki_doc", "access_path": "browser_session", "status": "ready"},
                    {"surface": "feishu_minutes", "access_path": "browser_session", "status": "ready"},
                    {"surface": "ask_feishu_aily", "access_path": "open_platform_api", "status": "blocked_system", "blocking_reason": "probe_failed"},
                ],
            }

            with patch.multiple(
                self.module,
                RUNS_ROOT=root / "adagj-runs",
                FEISHU_READER_PROFILE_DIR=root / "profiles" / "feishu-reader",
                FEISHU_BITABLE_PROFILE_DIR=root / "profiles" / "feishu-bitable",
                DEFAULT_CHROME_USER_DATA_DIR=root / "profiles" / "chrome",
            ):
                with patch.object(self.module, "collect_yuanli_pressure_test_evidence", side_effect=fake_collect):
                    with patch.object(self.module, "build_yuanli_auth_manifest", return_value=blocked_auth_manifest):
                        with patch.dict(os.environ, {"FEISHU_APP_ID": "", "FEISHU_APP_SECRET": ""}, clear=False):
                            exit_code = self.module.command_yuanli_pressure_test(args)

            self.assertEqual(exit_code, 0)
            ai_run_dir = root / "adagj-runs" / "2026-03-14" / "adagj-pressure-test-ai-only"
            route_payload = json.loads((ai_run_dir / "route.json").read_text(encoding="utf-8"))
            self.assertEqual(route_payload["verdict"], "pass_mvp")
            self.assertEqual(route_payload["closure_state"], "completed")
            self.assertEqual(route_payload["current_blocker"], "")
            self.assertEqual(route_payload["mvp_verdict"]["enhancer_status"], "enhancer_unavailable")

            yuanli_run_dir = yuanli_root / "artifacts" / "runs" / "2026-03-14" / "yj-pressure-test-ai-only"
            memory_packet = json.loads((yuanli_run_dir / "memory-packet.json").read_text(encoding="utf-8"))
            self.assertEqual(memory_packet["mvp_verdict"]["status"], "pass_mvp")
            self.assertEqual(memory_packet["mvp_verdict"]["interview_answered_count"], 0)
            self.assertTrue(memory_packet["mvp_verdict"]["ai_only_closure_ready"])

    def test_collect_yuanli_pressure_test_evidence_batches_eight_kb_questions_when_aily_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            yuanli_root = self.make_temp_yuanli_root(root)
            yuanli_run_dir = yuanli_root / "artifacts" / "runs" / "2026-03-14" / "yj-collect-kb"
            yuanli_run_dir.mkdir(parents=True, exist_ok=True)
            (yuanli_run_dir / "source-map.json").write_text(
                json.dumps({"seed_sources": [], "supplemental_sources": [], "ingested_sources": []}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (yuanli_run_dir / "seed-source-map.json").write_text("[]\n", encoding="utf-8")

            asked: list[dict[str, str]] = []
            question_bank = [
                {"id": "archetype-confirm-sage", "question": "Q1"},
                {"id": "archetype-confirm-explorer", "question": "Q2"},
                {"id": "archetype-gap-check", "question": "Q3"},
                {"id": "mutual-projection-help", "question": "Q4"},
                {"id": "mutual-projection-regulation", "question": "Q5"},
                {"id": "shadow-trigger", "question": "Q6"},
                {"id": "golden-shadow-trigger", "question": "Q7"},
                {"id": "collaboration-trigger", "question": "Q8"},
            ]

            def fake_run(command: list[str], cwd: Path | None = None, timeout: int | None = None) -> dict[str, object]:
                del cwd, timeout
                if "synthesize-dual-force" in command:
                    (yuanli_run_dir / "interview-responses.json").write_text(
                        json.dumps(
                            {
                                "responses": [
                                    {
                                        "id": item["id"],
                                        "question": item["question"],
                                        "status": "pending",
                                    }
                                    for item in question_bank
                                ]
                            },
                            ensure_ascii=False,
                            indent=2,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                return {"returncode": 0, "stdout": "", "stderr": ""}

            def fake_ingest_ask(**kwargs: object) -> dict[str, object]:
                asked.append(
                    {
                        "question": str(kwargs["question"]),
                        "interview_question_id": str(kwargs["interview_question_id"]),
                        "response_source": str(kwargs["response_source"]),
                        "artifact_subdir": str(kwargs["artifact_subdir"]),
                    }
                )
                return {"ok": True, "stderr": "", "stdout": "", "returncode": 0}

            with patch.object(self.module, "run_command_capture", side_effect=fake_run):
                with patch.object(self.module, "invoke_yuanli_ingest_ask_feishu", side_effect=fake_ingest_ask):
                    result = self.module.collect_yuanli_pressure_test_evidence(
                        yuanli_script=yuanli_root / "scripts" / "yuanli_juexing.py",
                        yuanli_root=yuanli_root,
                        yuanli_run_dir=yuanli_run_dir,
                        ai_run_dir=root / "adagj-run",
                        created_at="2026-03-14T11:00:00+08:00",
                        catalog_payload={},
                        auth_manifest={
                            "surfaces": [
                                {"surface": "ask_feishu_aily", "status": "ready"},
                            ]
                        },
                        minutes_url="https://example.test/minutes/me",
                    )

            self.assertEqual(len(asked), 8)
            self.assertTrue(all(item["response_source"] == "knowledge_base_answer" for item in asked))
            self.assertTrue(all(item["artifact_subdir"] == "ask-feishu-round-one" for item in asked))
            self.assertEqual(sum(1 for item in result["ask_results"] if item["status"] == "ingested"), 8)

    def test_build_aily_auth_surface_reports_missing_scopes(self) -> None:
        ok_auth = {
            "command": ["python3", "feishu_km.py", "auth-check"],
            "returncode": 0,
            "stdout": json.dumps({"ok": True, "command": "auth-check"}, ensure_ascii=False),
            "stderr": "",
            "timed_out": False,
        }
        blocked_ask = {
            "command": ["python3", "feishu_km.py", "ask"],
            "returncode": 1,
            "stdout": json.dumps(
                {
                    "ok": False,
                    "command": "ask",
                    "error": {
                        "code": 99991672,
                        "missing_scopes": ["aily:knowledge:ask"],
                    },
                },
                ensure_ascii=False,
            ),
            "stderr": "",
            "timed_out": False,
        }

        with tempfile.TemporaryDirectory() as tempdir:
            fake_script = Path(tempdir) / "feishu_km.py"
            fake_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            with patch.object(self.module, "FEISHU_KM_SCRIPT", fake_script):
                with patch.object(self.module, "feishu_km_credentials_present", return_value=True):
                    with patch.object(self.module, "run_command_capture", side_effect=[ok_auth, blocked_ask, blocked_ask, blocked_ask]):
                        surface = self.module.build_aily_auth_surface("2026-03-13T16:50:00+08:00")

        self.assertEqual(surface["status"], "blocked_scope")
        self.assertIn("aily:knowledge:ask", surface["required_scopes_or_session"])
        self.assertEqual(surface["blocking_reason"], "missing_required_scopes")
        self.assertEqual(surface["human_action_required"], ["grant_required_scopes"])
        self.assertEqual(surface["diagnosis"]["state"], "confirmed")
        self.assertIn("Open Platform", surface["diagnosis"]["current_best_hypothesis"])

    def test_build_aily_auth_surface_reports_wrong_object_layer(self) -> None:
        ok_auth = {
            "command": ["python3", "feishu_km.py", "auth-check"],
            "returncode": 0,
            "stdout": json.dumps({"ok": True, "command": "auth-check"}, ensure_ascii=False),
            "stderr": "",
            "timed_out": False,
        }
        blocked_channel = {
            "command": ["python3", "feishu_km.py", "ask"],
            "returncode": 1,
            "stdout": json.dumps(
                {
                    "ok": False,
                    "command": "ask",
                    "error": {
                        "code": 2320008,
                        "msg": "未找到应用凭证对应的应用信息，请确认当前 Aily 应用是否已发布至飞书机器人渠道",
                    },
                },
                ensure_ascii=False,
            ),
            "stderr": "",
            "timed_out": False,
        }

        with tempfile.TemporaryDirectory() as tempdir:
            fake_script = Path(tempdir) / "feishu_km.py"
            fake_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            with patch.object(self.module, "FEISHU_KM_SCRIPT", fake_script):
                with patch.object(self.module, "feishu_km_credentials_present", return_value=True):
                    with patch.object(self.module, "run_command_capture", side_effect=[ok_auth, blocked_channel, blocked_channel, blocked_channel]):
                        with patch.dict(os.environ, {"FEISHU_APP_ID": "cli_a92aeb1ceff9dcc7", "FEISHU_APP_SECRET": "secret"}, clear=False):
                            surface = self.module.build_aily_auth_surface("2026-03-13T17:20:00+08:00")

        self.assertEqual(surface["status"], "blocked_system")
        self.assertEqual(surface["blocking_reason"], "wrong_aily_app_object_layer")
        self.assertEqual(surface["human_action_required"], [])
        self.assertEqual(surface["diagnosis"]["state"], "confirmed")
        self.assertIn("spring_*", surface["diagnosis"]["resource_id"])
        self.assertTrue(surface["diagnosis"]["superseded_reasons"])

    def test_derive_pressure_test_closure_state_returns_failed_partial_for_wrong_object_layer(self) -> None:
        auth_manifest = {
            "surfaces": [
                {
                    "surface": "ask_feishu_aily",
                    "status": "blocked_system",
                    "blocking_reason": "wrong_aily_app_object_layer",
                    "diagnosis": {"superseded_reasons": ["old guess superseded"]},
                }
            ]
        }
        closure_state = self.module.derive_pressure_test_closure_state(auth_manifest, {"status": "needs_more_sources"})
        drift = self.module.pressure_test_diagnosis_drift(auth_manifest)

        self.assertEqual(closure_state, "failed_partial")
        self.assertEqual(drift[0]["surface"], "ask_feishu_aily")

    def test_derive_pressure_test_closure_state_returns_blocked_needs_user_for_user_micro_interview(self) -> None:
        closure_state = self.module.derive_pressure_test_closure_state(
            {"surfaces": [{"surface": "feishu_wiki_doc", "status": "ready"}, {"surface": "feishu_minutes", "status": "ready"}]},
            {"status": "needs_more_sources", "blocking_gates": ["need_user_micro_interview"]},
        )
        self.assertEqual(closure_state, "blocked_needs_user")

    def test_pressure_test_current_blocker_prioritizes_main_feishu_gaps_before_enhancer(self) -> None:
        auth_manifest = {
            "surfaces": [
                {"surface": "feishu_wiki_doc", "status": "ready", "blocking_reason": ""},
                {"surface": "feishu_minutes", "status": "ready", "blocking_reason": ""},
                {"surface": "ask_feishu_aily", "status": "blocked_system", "blocking_reason": "wrong_aily_app_object_layer"},
            ]
        }
        mvp_verdict = {
            "status": "needs_more_sources",
            "blocking_gates": [
                "need_more_feishu_doc_reads",
                "need_more_collaboration_trace",
                "need_kb_round_one_interview",
            ],
        }

        blocker = self.module.pressure_test_current_blocker(auth_manifest, mvp_verdict)
        self.assertEqual(blocker, "need_more_feishu_doc_reads")

    def test_invoke_yuanli_ingest_feishu_doc_prefers_dedicated_profile_and_only_falls_back_on_auth(self) -> None:
        calls: list[list[str]] = []

        def fake_run(command: list[str], cwd: Path, timeout: int) -> dict[str, object]:
            calls.append(command)
            if len(calls) == 1:
                return {
                    "returncode": 2,
                    "stdout": "stored: /tmp/mock.json\nstatus: auth_required\n",
                    "stderr": "",
                }
            return {
                "returncode": 0,
                "stdout": "stored: /tmp/mock.json\nstatus: ok\n",
                "stderr": "",
            }

        with patch.object(self.module, "run_command_capture", side_effect=fake_run):
            payload = self.module.invoke_yuanli_ingest_feishu_doc(
                yuanli_script=Path("/tmp/yuanli_juexing.py"),
                yuanli_root=Path("/tmp"),
                yuanli_run_dir=Path("/tmp/yuanli-run"),
                url="https://example.test/wiki/demo",
                title="原力OS",
                priority="high",
                reason="系统框架",
            )

        self.assertEqual(len(calls), 2)
        self.assertNotIn("--reuse-chrome-profile", calls[0])
        self.assertIn("--reuse-chrome-profile", calls[1])
        self.assertTrue(payload["ok"])
        self.assertIn("previous_attempt", payload)


if __name__ == "__main__":
    unittest.main()
