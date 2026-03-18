from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path("/Users/liming/Documents/codex-ai-gua-jia-01")
SCRIPT_PATH = PROJECT_ROOT / "work" / "yuanli-juexing" / "scripts" / "yuanli_juexing.py"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class YuanliJuexingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module("test_yuanli_juexing_module", SCRIPT_PATH)

    def make_temp_skill_root(self) -> Path:
        temp_root = Path(tempfile.mkdtemp())
        (temp_root / "artifacts" / "sources").mkdir(parents=True, exist_ok=True)
        shutil.copy2(SCRIPT_PATH, temp_root / "scripts.py")
        return temp_root

    def test_init_run_creates_dual_force_scaffold(self) -> None:
        temp_root = self.make_temp_skill_root()
        source_path = temp_root / "artifacts" / "sources" / "transcript.md"
        source_path.write_text("关窍 全局最优 让 AI 理解你自己", encoding="utf-8")

        args = types.SimpleNamespace(
            topic="demo",
            note="note",
            run_id="yj-test-init",
            source_file=[str(source_path)],
        )
        with patch.object(self.module, "skill_root", return_value=temp_root):
            exit_code = self.module.init_run(args)

        self.assertEqual(exit_code, 0)
        run_dir = temp_root / "artifacts" / "runs" / self.module.now_local().strftime("%Y-%m-%d") / "yj-test-init"
        expected = {
            "input.json",
            "source-map.json",
            "source-digest.md",
            "ai-force-model.md",
            "human-force-profile.md",
            "dual-force-bridge.md",
            "collaboration-protocol.md",
            "memory-packet.json",
            "worklog.md",
            "seed-source-map.json",
            "user-corrections.json",
            "auth-manifest.json",
            "interview-pack.md",
            "interview-responses.json",
            "minimum-closure-pack.md",
            "minimum-closure-responses.json",
        }
        self.assertTrue(run_dir.exists())
        self.assertTrue(expected.issubset({path.name for path in run_dir.iterdir()}))

    def test_infer_auth_status_treats_auth_required_with_substantive_visible_content_as_ready(self) -> None:
        payload = {
            "status": "auth_required",
            "title": "原力OS-数据模型",
            "text": "原力OS-数据模型 数据表 工作流 总控对象主表 线程总表 任务总表 战略链路表 CBM组件责任表 CBM组件热图表 技能与能力表 数据源同步表 Review批次表 决策记录表 治理动作与写回表 字段字典与术语表 新建 导入 Excel 数据表 收集表 仪表盘 工作流 文档 文件夹 连接器中心 应用 表格 新建视图 AI 帮我搭建 评论 " * 2,
            "metadata": {"top_lines": ["飞书云文档", "原力OS-数据模型", "SOUL-递归日志-AI管家", "技能盘点"]},
        }

        self.assertEqual(self.module.infer_auth_status(payload), "ready")

    def test_synthesize_and_prepare_mirror(self) -> None:
        temp_root = self.make_temp_skill_root()
        source_path = temp_root / "artifacts" / "sources" / "clarification.md"
        source_path.write_text(
            "关窍 全局最优 量身定造 让 AI 找到你自己学习 阴影 金色阴影 一层层拆 递归 初始条件 智者 探索者 互为投射 采访",
            encoding="utf-8",
        )
        run_dir = temp_root / "artifacts" / "runs" / "2026-03-13" / "yj-test-synthesis"
        run_dir.mkdir(parents=True, exist_ok=True)

        input_payload = {
            "run_id": "yj-test-synthesis",
            "topic": "demo",
            "created_at": "2026-03-13T16:00:00+08:00",
            "note": "demo",
            "source_files": [str(source_path)],
        }
        source_map = {
            "seed_sources": [],
            "supplemental_sources": [{"type": "local_file", "title": "clarification", "path": str(source_path), "status": "available"}],
            "ingested_sources": [],
        }
        (run_dir / "input.json").write_text(json.dumps(input_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (run_dir / "source-map.json").write_text(json.dumps(source_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (run_dir / "seed-source-map.json").write_text("[]\n", encoding="utf-8")
        (run_dir / "auth-manifest.json").write_text(
            json.dumps(
                {
                    "mode": "read_first",
                    "created_at": "2026-03-13T16:00:00+08:00",
                    "surfaces": [
                        {"surface": "feishu_wiki_doc", "access_path": "browser_session", "status": "ready"},
                        {"surface": "ask_feishu_aily", "access_path": "open_platform_api", "status": "blocked_system"},
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (run_dir / "user-corrections.json").write_text(
            json.dumps(
                [
                    {
                        "field": "human_force.decision_style",
                        "label": "用户修正",
                        "correction": "不要把我写成单纯人格分析对象",
                        "reason": "这是双原力协同，不是单边画像",
                        "recorded_at": "2026-03-13T16:10:00+08:00",
                    }
                ],
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (run_dir / "worklog.md").write_text("# Worklog\n", encoding="utf-8")

        synth_args = types.SimpleNamespace(run_dir=str(run_dir))
        mirror_args = types.SimpleNamespace(run_dir=str(run_dir))
        with patch.object(self.module, "skill_root", return_value=temp_root):
            synth_exit = self.module.synthesize_dual_force(synth_args)
            mirror_exit = self.module.prepare_governance_mirror(mirror_args)

        self.assertEqual(synth_exit, 0)
        self.assertEqual(mirror_exit, 0)

        memory_packet = json.loads((run_dir / "memory-packet.json").read_text(encoding="utf-8"))
        self.assertIn("ai_force", memory_packet)
        self.assertIn("human_force", memory_packet)
        self.assertIn("archetype_root", memory_packet)
        self.assertEqual(len(memory_packet["archetype_root"]), 12)
        self.assertTrue(all(item["key"] == item["id"] for item in memory_packet["archetype_root"]))
        self.assertIn("mutual_projection_map", memory_packet)
        self.assertIn("interview_deltas", memory_packet)
        self.assertIn("user_validated_seeds", memory_packet)
        self.assertEqual(memory_packet["current_phase"], "source_enrichment_pending")
        self.assertTrue(memory_packet["bridge_rules"])
        self.assertTrue(memory_packet["confidence_conditions"]["user_corrections_applied"])
        self.assertIn("mvp_verdict", memory_packet)
        self.assertEqual(memory_packet["mvp_verdict"]["status"], "needs_more_sources")
        self.assertIn("sage", memory_packet["user_validated_seeds"])
        self.assertIn("explorer", memory_packet["user_validated_seeds"])

        human_force_md = (run_dir / "human-force-profile.md").read_text(encoding="utf-8")
        self.assertIn("荣格12原型根目录", human_force_md)
        self.assertIn("互为投射线索", human_force_md)

        bridge_md = (run_dir / "dual-force-bridge.md").read_text(encoding="utf-8")
        self.assertIn("互为投射与共振", bridge_md)

        protocol_md = (run_dir / "collaboration-protocol.md").read_text(encoding="utf-8")
        self.assertIn("Mutual Projection Guardrails", protocol_md)
        self.assertIn("When Resonance Helps", protocol_md)
        self.assertIn("When Resonance Distorts", protocol_md)

        interview_pack = (run_dir / "interview-pack.md").read_text(encoding="utf-8")
        self.assertIn("question_limit", interview_pack)
        self.assertLessEqual(interview_pack.count(". ["), 8)

        interview_responses = json.loads((run_dir / "interview-responses.json").read_text(encoding="utf-8"))
        self.assertEqual(len(interview_responses["responses"]), 8)
        self.assertTrue(all(item["status"] in {"pending", "answered"} for item in interview_responses["responses"]))

        mirror = json.loads((run_dir / "mirror-summary.json").read_text(encoding="utf-8"))
        self.assertEqual(mirror["run_id"], "yj-test-synthesis")
        self.assertTrue(mirror["selected_rules"])
        self.assertEqual(mirror["verdict"], "needs_more_sources")
        self.assertNotIn("关窍 全局最优", json.dumps(mirror, ensure_ascii=False))

    def test_synthesize_passes_mvp_when_real_reads_and_round_one_human_answers_exist(self) -> None:
        temp_root = self.make_temp_skill_root()
        source_path = temp_root / "artifacts" / "sources" / "clarification.md"
        source_path.write_text(
            "关窍 全局最优 量身定造 让 AI 找到你自己学习 阴影 金色阴影 一层层拆 递归 初始条件 智者 探索者 互为投射",
            encoding="utf-8",
        )
        run_dir = temp_root / "artifacts" / "runs" / "2026-03-14" / "yj-test-pass-mvp"
        run_dir.mkdir(parents=True, exist_ok=True)
        ingest_dir = run_dir / "ingestions"
        ingest_dir.mkdir(parents=True, exist_ok=True)

        def write_ingested(name: str, text: str) -> tuple[str, str]:
            json_path = ingest_dir / f"{name}.json"
            md_path = ingest_dir / f"{name}.md"
            json_path.write_text(json.dumps({"text": text}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            md_path.write_text(f"# {name}\n\n{text}\n", encoding="utf-8")
            return str(json_path), str(md_path)

        os_json, os_md = write_ingested("yuanli-os", "原力OS 关窍 全局最优 长期系统框架")
        soul_json, soul_md = write_ingested("soul-log", "SOUL 递归日志 AI大管家 协作历史 长期迭代")
        minutes_json, minutes_md = write_ingested("minutes-trace", "AI大管家 协作 节奏 误读点 互为投射")

        input_payload = {
            "run_id": "yj-test-pass-mvp",
            "topic": "demo",
            "created_at": "2026-03-14T10:00:00+08:00",
            "note": "demo",
            "source_files": [str(source_path)],
        }
        source_map = {
            "seed_sources": [],
            "supplemental_sources": [{"type": "local_file", "title": "clarification", "path": str(source_path), "status": "available"}],
            "ingested_sources": [
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
            ],
        }
        (run_dir / "input.json").write_text(json.dumps(input_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (run_dir / "source-map.json").write_text(json.dumps(source_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (run_dir / "seed-source-map.json").write_text("[]\n", encoding="utf-8")
        (run_dir / "auth-manifest.json").write_text(
            json.dumps(
                {
                    "mode": "read_first",
                    "created_at": "2026-03-14T10:00:00+08:00",
                    "surfaces": [
                        {"surface": "feishu_wiki_doc", "access_path": "browser_session", "status": "ready"},
                        {"surface": "feishu_minutes", "access_path": "browser_session", "status": "ready"},
                        {"surface": "ask_feishu_aily", "access_path": "open_platform_api", "status": "blocked_system"},
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (run_dir / "user-corrections.json").write_text("[]\n", encoding="utf-8")
        (run_dir / "worklog.md").write_text("# Worklog\n", encoding="utf-8")
        (run_dir / "interview-responses.json").write_text(
            json.dumps(
                {
                    "responses": [
                        {"id": "archetype-confirm-sage", "answer": "核心驱动力", "status": "answered", "answered_at": "2026-03-14T10:05:00+08:00"},
                        {"id": "archetype-confirm-explorer", "answer": "辅助驱动力", "status": "answered", "answered_at": "2026-03-14T10:05:00+08:00"},
                        {"id": "archetype-gap-check", "answer": "创造者", "status": "answered", "answered_at": "2026-03-14T10:05:00+08:00"},
                        {"id": "mutual-projection-help", "answer": "智者式共振", "status": "answered", "answered_at": "2026-03-14T10:05:00+08:00"},
                        {"id": "mutual-projection-regulation", "answer": "校验", "status": "answered", "answered_at": "2026-03-14T10:05:00+08:00"},
                        {"id": "shadow-trigger", "answer": "低密度表达", "status": "answered", "answered_at": "2026-03-14T10:05:00+08:00"},
                        {"id": "golden-shadow-trigger", "answer": "高密度系统作品", "status": "answered", "answered_at": "2026-03-14T10:05:00+08:00"},
                        {"id": "collaboration-trigger", "answer": "先抓关窍", "status": "answered", "answered_at": "2026-03-14T10:05:00+08:00"},
                    ]
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        synth_args = types.SimpleNamespace(run_dir=str(run_dir))
        with patch.object(self.module, "skill_root", return_value=temp_root):
            synth_exit = self.module.synthesize_dual_force(synth_args)

        self.assertEqual(synth_exit, 0)
        memory_packet = json.loads((run_dir / "memory-packet.json").read_text(encoding="utf-8"))
        self.assertEqual(memory_packet["mvp_verdict"]["status"], "pass_mvp")
        self.assertEqual(memory_packet["mvp_verdict"]["enhancer_status"], "enhancer_unavailable")
        self.assertEqual(memory_packet["current_phase"], "ready_for_real_task_validation")
        self.assertEqual(memory_packet["mvp_verdict"]["remote_evidence"]["doc_like"], 2)
        self.assertEqual(memory_packet["mvp_verdict"]["remote_evidence"]["trace_like"], 2)
        self.assertEqual(memory_packet["mvp_verdict"]["interview_answered_count"], 8)
        self.assertTrue(memory_packet["mvp_verdict"]["interview_summary"]["round_one_complete"])

        interview_pack = (run_dir / "interview-pack.md").read_text(encoding="utf-8")
        self.assertIn("round: `1`", interview_pack)
        self.assertIn("status: `completed_no_followup_needed`", interview_pack)
        self.assertLessEqual(interview_pack.count(". ["), 8)

    def test_synthesize_counts_knowledge_base_round_one_as_completed_interview(self) -> None:
        temp_root = self.make_temp_skill_root()
        source_path = temp_root / "artifacts" / "sources" / "clarification.md"
        source_path.write_text(
            "关窍 全局最优 量身定造 让 AI 找到你自己学习 阴影 金色阴影 一层层拆 递归 初始条件 智者 探索者 互为投射",
            encoding="utf-8",
        )
        run_dir = temp_root / "artifacts" / "runs" / "2026-03-14" / "yj-test-kb-round-one"
        run_dir.mkdir(parents=True, exist_ok=True)
        ingest_dir = run_dir / "ingestions"
        ingest_dir.mkdir(parents=True, exist_ok=True)

        def write_ingested(name: str, text: str) -> tuple[str, str]:
            json_path = ingest_dir / f"{name}.json"
            md_path = ingest_dir / f"{name}.md"
            json_path.write_text(json.dumps({"text": text}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            md_path.write_text(f"# {name}\n\n{text}\n", encoding="utf-8")
            return str(json_path), str(md_path)

        os_json, os_md = write_ingested("yuanli-os", "原力OS 关窍 全局最优 长期系统框架")
        soul_json, soul_md = write_ingested("soul-log", "SOUL 递归日志 AI大管家 协作历史 长期迭代")
        minutes_json, minutes_md = write_ingested("minutes-trace", "AI大管家 协作 节奏 误读点 互为投射")

        ask_dir = ingest_dir / "ask-feishu-round-one"
        ask_dir.mkdir(parents=True, exist_ok=True)
        round_one_questions = self.module.build_round_one_interview_questions({"archetype_root": []})
        ask_entries = []
        for item in round_one_questions:
            answer = f"{item['id']} 的知识库回答，来自你过往教学和协作材料，已经足够支持这一轮综合判断。"
            json_path = ask_dir / f"{item['id']}.json"
            md_path = ask_dir / f"{item['id']}.md"
            payload = {"ok": True, "command": "ask", "data": {"answer": answer}}
            json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            md_path.write_text(f"# ask\n\n{answer}\n", encoding="utf-8")
            ask_entries.append(
                {
                    "key": f"ask_feishu_question::{item['id']}",
                    "type": "ask_feishu_question",
                    "title": f"interview-{item['id']}",
                    "url": f"ask.feishu://question/{item['id']}",
                    "question": item["question"],
                    "interview_question_id": item["id"],
                    "response_source": "knowledge_base_answer",
                    "answer_text": answer,
                    "answer_quality": "usable",
                    "source_surface": "ask_feishu_question",
                    "access_path": "open_platform_api",
                    "auth_status": "ready",
                    "status": "ok",
                    "artifacts": {"json": str(json_path), "markdown": str(md_path)},
                    "ingested_at": "2026-03-14T10:05:00+08:00",
                }
            )

        input_payload = {
            "run_id": "yj-test-kb-round-one",
            "topic": "demo",
            "created_at": "2026-03-14T10:00:00+08:00",
            "note": "demo",
            "source_files": [str(source_path)],
        }
        source_map = {
            "seed_sources": [],
            "supplemental_sources": [{"type": "local_file", "title": "clarification", "path": str(source_path), "status": "available"}],
            "ingested_sources": [
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
                *ask_entries,
            ],
        }
        (run_dir / "input.json").write_text(json.dumps(input_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (run_dir / "source-map.json").write_text(json.dumps(source_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (run_dir / "seed-source-map.json").write_text("[]\n", encoding="utf-8")
        (run_dir / "auth-manifest.json").write_text(
            json.dumps(
                {
                    "mode": "read_first",
                    "created_at": "2026-03-14T10:00:00+08:00",
                    "surfaces": [
                        {"surface": "feishu_wiki_doc", "access_path": "browser_session", "status": "ready"},
                        {"surface": "feishu_minutes", "access_path": "browser_session", "status": "ready"},
                        {"surface": "ask_feishu_aily", "access_path": "open_platform_api", "status": "ready"},
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (run_dir / "user-corrections.json").write_text("[]\n", encoding="utf-8")
        (run_dir / "worklog.md").write_text("# Worklog\n", encoding="utf-8")
        (run_dir / "interview-responses.json").write_text(json.dumps({"responses": []}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        synth_args = types.SimpleNamespace(run_dir=str(run_dir))
        with patch.object(self.module, "skill_root", return_value=temp_root):
            synth_exit = self.module.synthesize_dual_force(synth_args)

        self.assertEqual(synth_exit, 0)
        memory_packet = json.loads((run_dir / "memory-packet.json").read_text(encoding="utf-8"))
        self.assertEqual(memory_packet["mvp_verdict"]["status"], "pass_mvp")
        self.assertEqual(memory_packet["mvp_verdict"]["interview_answered_count"], 8)
        self.assertEqual(memory_packet["mvp_verdict"]["enhancer_status"], "ready")
        self.assertEqual(memory_packet["current_phase"], "ready_for_real_task_validation")
        self.assertTrue(memory_packet["mvp_verdict"]["interview_summary"]["round_one_complete"])
        self.assertEqual(memory_packet["confidence_conditions"]["knowledge_base_mediated_count"], 8)

        responses = json.loads((run_dir / "interview-responses.json").read_text(encoding="utf-8"))["responses"]
        self.assertEqual({item["response_source"] for item in responses}, {"knowledge_base_answer"})
        self.assertTrue(all(item["answer_quality"] in {"usable", "strong"} for item in responses))

        source_digest = (run_dir / "source-digest.md").read_text(encoding="utf-8")
        self.assertIn("Knowledge-Base Mediated Evidence", source_digest)
        self.assertIn("archetype-confirm-sage", source_digest)

        human_force_md = (run_dir / "human-force-profile.md").read_text(encoding="utf-8")
        self.assertIn("Knowledge-Base Mediated Evidence", human_force_md)
        self.assertIn("archetype-confirm-sage", human_force_md)

    def test_synthesize_passes_mvp_with_ai_only_real_feishu_closure(self) -> None:
        temp_root = self.make_temp_skill_root()
        source_path = temp_root / "artifacts" / "sources" / "clarification.md"
        source_path.write_text(
            "关窍 全局最优 量身定造 让 AI 找到你自己学习 阴影 金色阴影 一层层拆 递归 初始条件 智者 探索者 互为投射 整合 落地 校验",
            encoding="utf-8",
        )
        run_dir = temp_root / "artifacts" / "runs" / "2026-03-14" / "yj-test-ai-only-closure"
        run_dir.mkdir(parents=True, exist_ok=True)
        ingest_dir = run_dir / "ingestions"
        ingest_dir.mkdir(parents=True, exist_ok=True)

        def write_ingested(name: str, text: str) -> tuple[str, str]:
            json_path = ingest_dir / f"{name}.json"
            md_path = ingest_dir / f"{name}.md"
            json_path.write_text(json.dumps({"text": text}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            md_path.write_text(f"# {name}\n\n{text}\n", encoding="utf-8")
            return str(json_path), str(md_path)

        os_json, os_md = write_ingested("yuanli-os", "原力OS 关窍 全局最优 量身定造 AI 工具统筹")
        soul_json, soul_md = write_ingested("soul-log", "SOUL 递归日志 AI大管家 协作历史 互为投射 整合 落地 校验")
        minutes_json, minutes_md = write_ingested("minutes-trace", "AI大管家 协作 节奏 误读点 金色阴影 阴影")

        input_payload = {
            "run_id": "yj-test-ai-only-closure",
            "topic": "demo",
            "created_at": "2026-03-14T10:00:00+08:00",
            "note": "demo",
            "source_files": [str(source_path)],
        }
        source_map = {
            "seed_sources": [],
            "supplemental_sources": [{"type": "local_file", "title": "clarification", "path": str(source_path), "status": "available"}],
            "ingested_sources": [
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
            ],
        }
        (run_dir / "input.json").write_text(json.dumps(input_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (run_dir / "source-map.json").write_text(json.dumps(source_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (run_dir / "seed-source-map.json").write_text("[]\n", encoding="utf-8")
        (run_dir / "auth-manifest.json").write_text(
            json.dumps(
                {
                    "mode": "read_first",
                    "created_at": "2026-03-14T10:00:00+08:00",
                    "surfaces": [
                        {"surface": "feishu_wiki_doc", "access_path": "browser_session", "status": "ready"},
                        {"surface": "feishu_minutes", "access_path": "browser_session", "status": "ready"},
                        {"surface": "ask_feishu_aily", "access_path": "open_platform_api", "status": "blocked_system"},
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (run_dir / "user-corrections.json").write_text("[]\n", encoding="utf-8")
        (run_dir / "worklog.md").write_text("# Worklog\n", encoding="utf-8")
        (run_dir / "interview-responses.json").write_text(json.dumps({"responses": []}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        synth_args = types.SimpleNamespace(run_dir=str(run_dir))
        with patch.object(self.module, "skill_root", return_value=temp_root):
            synth_exit = self.module.synthesize_dual_force(synth_args)

        self.assertEqual(synth_exit, 0)
        memory_packet = json.loads((run_dir / "memory-packet.json").read_text(encoding="utf-8"))
        self.assertEqual(memory_packet["mvp_verdict"]["status"], "pass_mvp")
        self.assertEqual(memory_packet["mvp_verdict"]["enhancer_status"], "enhancer_unavailable")
        self.assertEqual(memory_packet["current_phase"], "minimum_human_closure_pending")
        self.assertEqual(memory_packet["mvp_verdict"]["interview_answered_count"], 0)
        self.assertTrue(memory_packet["mvp_verdict"]["ai_only_closure_ready"])

        interview_pack = (run_dir / "interview-pack.md").read_text(encoding="utf-8")
        self.assertIn("status: `ai_only_closure_ready`", interview_pack)
        self.assertEqual(interview_pack.count(". ["), 0)

    def test_synthesize_promotes_user_micro_interview_when_kb_answers_leave_subjective_gaps(self) -> None:
        temp_root = self.make_temp_skill_root()
        source_path = temp_root / "artifacts" / "sources" / "clarification.md"
        source_path.write_text(
            "关窍 全局最优 量身定造 让 AI 找到你自己学习 阴影 金色阴影 一层层拆 递归 初始条件 智者 探索者 互为投射",
            encoding="utf-8",
        )
        run_dir = temp_root / "artifacts" / "runs" / "2026-03-14" / "yj-test-kb-followup"
        run_dir.mkdir(parents=True, exist_ok=True)
        ingest_dir = run_dir / "ingestions"
        ingest_dir.mkdir(parents=True, exist_ok=True)

        def write_ingested(name: str, text: str) -> tuple[str, str]:
            json_path = ingest_dir / f"{name}.json"
            md_path = ingest_dir / f"{name}.md"
            json_path.write_text(json.dumps({"text": text}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            md_path.write_text(f"# {name}\n\n{text}\n", encoding="utf-8")
            return str(json_path), str(md_path)

        os_json, os_md = write_ingested("yuanli-os", "原力OS 关窍 全局最优 长期系统框架")
        soul_json, soul_md = write_ingested("soul-log", "SOUL 递归日志 AI大管家 协作历史 长期迭代")
        minutes_json, minutes_md = write_ingested("minutes-trace", "AI大管家 协作 节奏 误读点 互为投射")

        ask_dir = ingest_dir / "ask-feishu-round-one"
        ask_dir.mkdir(parents=True, exist_ok=True)
        weak_ids = {"mutual-projection-help", "mutual-projection-regulation", "collaboration-trigger"}
        ask_entries = []
        for item in self.module.build_round_one_interview_questions({"archetype_root": []}):
            if item["id"] in weak_ids:
                answer = "校验"
                quality = "weak"
            else:
                answer = f"{item['id']} 的知识库回答，来自你过往教学和协作材料，已经足够支持这一轮综合判断。"
                quality = "usable"
            json_path = ask_dir / f"{item['id']}.json"
            md_path = ask_dir / f"{item['id']}.md"
            payload = {"ok": True, "command": "ask", "data": {"answer": answer}}
            json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            md_path.write_text(f"# ask\n\n{answer}\n", encoding="utf-8")
            ask_entries.append(
                {
                    "key": f"ask_feishu_question::{item['id']}",
                    "type": "ask_feishu_question",
                    "title": f"interview-{item['id']}",
                    "url": f"ask.feishu://question/{item['id']}",
                    "question": item["question"],
                    "interview_question_id": item["id"],
                    "response_source": "knowledge_base_answer",
                    "answer_text": answer,
                    "answer_quality": quality,
                    "source_surface": "ask_feishu_question",
                    "access_path": "open_platform_api",
                    "auth_status": "ready",
                    "status": "ok",
                    "artifacts": {"json": str(json_path), "markdown": str(md_path)},
                    "ingested_at": "2026-03-14T10:05:00+08:00",
                }
            )

        input_payload = {
            "run_id": "yj-test-kb-followup",
            "topic": "demo",
            "created_at": "2026-03-14T10:00:00+08:00",
            "note": "demo",
            "source_files": [str(source_path)],
        }
        source_map = {
            "seed_sources": [],
            "supplemental_sources": [{"type": "local_file", "title": "clarification", "path": str(source_path), "status": "available"}],
            "ingested_sources": [
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
                *ask_entries,
            ],
        }
        (run_dir / "input.json").write_text(json.dumps(input_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (run_dir / "source-map.json").write_text(json.dumps(source_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (run_dir / "seed-source-map.json").write_text("[]\n", encoding="utf-8")
        (run_dir / "auth-manifest.json").write_text(
            json.dumps(
                {
                    "mode": "read_first",
                    "created_at": "2026-03-14T10:00:00+08:00",
                    "surfaces": [
                        {"surface": "feishu_wiki_doc", "access_path": "browser_session", "status": "ready"},
                        {"surface": "feishu_minutes", "access_path": "browser_session", "status": "ready"},
                        {"surface": "ask_feishu_aily", "access_path": "open_platform_api", "status": "ready"},
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (run_dir / "user-corrections.json").write_text("[]\n", encoding="utf-8")
        (run_dir / "worklog.md").write_text("# Worklog\n", encoding="utf-8")
        (run_dir / "interview-responses.json").write_text(json.dumps({"responses": []}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        synth_args = types.SimpleNamespace(run_dir=str(run_dir))
        with patch.object(self.module, "skill_root", return_value=temp_root):
            synth_exit = self.module.synthesize_dual_force(synth_args)

        self.assertEqual(synth_exit, 0)
        memory_packet = json.loads((run_dir / "memory-packet.json").read_text(encoding="utf-8"))
        self.assertEqual(memory_packet["mvp_verdict"]["status"], "needs_more_sources")
        self.assertIn("need_user_micro_interview", memory_packet["mvp_verdict"]["blocking_gates"])

        interview_pack = (run_dir / "interview-pack.md").read_text(encoding="utf-8")
        self.assertIn("status: `user_micro_active`", interview_pack)
        self.assertLessEqual(interview_pack.count(". ["), 3)

    def test_prepare_and_record_minimum_closure(self) -> None:
        temp_root = self.make_temp_skill_root()
        run_dir = temp_root / "artifacts" / "runs" / "2026-03-14" / "yj-test-minimum-closure"
        run_dir.mkdir(parents=True, exist_ok=True)

        with patch.object(self.module, "skill_root", return_value=temp_root):
            prepare_exit = self.module.prepare_minimum_closure(types.SimpleNamespace(run_dir=str(run_dir)))
        self.assertEqual(prepare_exit, 0)

        pack_text = (run_dir / "minimum-closure-pack.md").read_text(encoding="utf-8")
        self.assertIn("question_limit: `5`", pack_text)
        responses_payload = json.loads((run_dir / "minimum-closure-responses.json").read_text(encoding="utf-8"))
        self.assertEqual(responses_payload["status"], "pending_user_short_answers")
        self.assertEqual(len(responses_payload["responses"]), 5)

        answers_file = temp_root / "answers.json"
        answers_file.write_text(
            json.dumps(
                {
                    "minimum-closure-sage-strength": "核心驱动力",
                    "minimum-closure-explorer-strength": "辅助驱动力",
                    "minimum-closure-resonance-mode": "两者叠加",
                    "minimum-closure-overheat-guardrail": "校验",
                    "minimum-closure-key-anchors": {
                        "low_leverage_trigger": "被拉去做低密度、低杠杆的重复解释时。",
                        "golden_shadow_anchor": "真正能统帅复杂性又保持洞察穿透力的人。",
                        "highest_value_trigger": "先抓住真正的关窍，再展开路径。",
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        with patch.object(self.module, "skill_root", return_value=temp_root):
            record_exit = self.module.record_minimum_closure(
                types.SimpleNamespace(run_dir=str(run_dir), answers_file=str(answers_file))
            )
        self.assertEqual(record_exit, 0)

        recorded = json.loads((run_dir / "minimum-closure-responses.json").read_text(encoding="utf-8"))
        self.assertEqual(recorded["status"], "collected")
        anchor_item = next(item for item in recorded["responses"] if item["id"] == "minimum-closure-key-anchors")
        self.assertEqual(anchor_item["structured_answer"]["highest_value_trigger"], "先抓住真正的关窍，再展开路径。")

    def test_synthesize_uses_minimum_closure_to_reach_real_task_validation_phase(self) -> None:
        temp_root = self.make_temp_skill_root()
        source_path = temp_root / "artifacts" / "sources" / "clarification.md"
        source_path.write_text(
            "关窍 全局最优 量身定造 让 AI 找到你自己学习 阴影 金色阴影 一层层拆 递归 初始条件 智者 探索者 互为投射",
            encoding="utf-8",
        )
        run_dir = temp_root / "artifacts" / "runs" / "2026-03-14" / "yj-test-minimum-closure-phase"
        run_dir.mkdir(parents=True, exist_ok=True)
        ingest_dir = run_dir / "ingestions"
        ingest_dir.mkdir(parents=True, exist_ok=True)

        def write_ingested(name: str, text: str) -> tuple[str, str]:
            json_path = ingest_dir / f"{name}.json"
            md_path = ingest_dir / f"{name}.md"
            json_path.write_text(json.dumps({"text": text}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            md_path.write_text(f"# {name}\n\n{text}\n", encoding="utf-8")
            return str(json_path), str(md_path)

        os_json, os_md = write_ingested("yuanli-os", "原力OS 关窍 全局最优 长期系统框架")
        soul_json, soul_md = write_ingested("soul-log", "SOUL 递归日志 AI大管家 协作历史 长期迭代")
        minutes_json, minutes_md = write_ingested("minutes-trace", "AI大管家 协作 节奏 误读点 互为投射")

        input_payload = {
            "run_id": "yj-test-minimum-closure-phase",
            "topic": "demo",
            "created_at": "2026-03-14T10:00:00+08:00",
            "note": "demo",
            "source_files": [str(source_path)],
        }
        source_map = {
            "seed_sources": [],
            "supplemental_sources": [{"type": "local_file", "title": "clarification", "path": str(source_path), "status": "available"}],
            "ingested_sources": [
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
            ],
        }
        (run_dir / "input.json").write_text(json.dumps(input_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (run_dir / "source-map.json").write_text(json.dumps(source_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (run_dir / "seed-source-map.json").write_text("[]\n", encoding="utf-8")
        (run_dir / "auth-manifest.json").write_text(
            json.dumps(
                {
                    "mode": "read_first",
                    "created_at": "2026-03-14T10:00:00+08:00",
                    "surfaces": [
                        {"surface": "feishu_wiki_doc", "access_path": "browser_session", "status": "ready"},
                        {"surface": "feishu_minutes", "access_path": "browser_session", "status": "ready"},
                        {"surface": "ask_feishu_aily", "access_path": "open_platform_api", "status": "blocked_system"},
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (run_dir / "user-corrections.json").write_text("[]\n", encoding="utf-8")
        (run_dir / "worklog.md").write_text("# Worklog\n", encoding="utf-8")
        (run_dir / "interview-responses.json").write_text(json.dumps({"responses": []}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (run_dir / "minimum-closure-responses.json").write_text(
            json.dumps(
                {
                    "phase": "minimum_human_closure",
                    "status": "collected",
                    "responses": [
                        {"id": "minimum-closure-sage-strength", "question": "q1", "category": "原型权重确认", "status": "answered", "answer": "核心驱动力"},
                        {"id": "minimum-closure-explorer-strength", "question": "q2", "category": "原型权重确认", "status": "answered", "answer": "辅助驱动力"},
                        {"id": "minimum-closure-resonance-mode", "question": "q3", "category": "互为投射体感", "status": "answered", "answer": "两者叠加"},
                        {"id": "minimum-closure-overheat-guardrail", "question": "q4", "category": "过热护栏", "status": "answered", "answer": "校验"},
                        {
                            "id": "minimum-closure-key-anchors",
                            "question": "q5",
                            "category": "关键锚点",
                            "status": "answered",
                            "answer": "低杠杆排斥触发: 被迫做低杠杆解释；金色阴影对象: 能统帅复杂性的人；最高成功率触发点: 先抓真正关窍。",
                            "structured_answer": {
                                "low_leverage_trigger": "被迫做低杠杆解释",
                                "golden_shadow_anchor": "能统帅复杂性的人",
                                "highest_value_trigger": "先抓真正关窍",
                            },
                        },
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        synth_args = types.SimpleNamespace(run_dir=str(run_dir))
        with patch.object(self.module, "skill_root", return_value=temp_root):
            synth_exit = self.module.synthesize_dual_force(synth_args)

        self.assertEqual(synth_exit, 0)
        memory_packet = json.loads((run_dir / "memory-packet.json").read_text(encoding="utf-8"))
        self.assertEqual(memory_packet["mvp_verdict"]["status"], "pass_mvp")
        self.assertEqual(memory_packet["current_phase"], "ready_for_real_task_validation")
        self.assertTrue(memory_packet["minimum_human_closure"]["complete"])
        self.assertEqual(memory_packet["minimum_human_closure"]["overheat_guardrail"], "校验")

        human_force_md = (run_dir / "human-force-profile.md").read_text(encoding="utf-8")
        self.assertIn("第一次合作最小闭环", human_force_md)
        self.assertIn("最高成功率触发点", human_force_md)

        protocol_md = (run_dir / "collaboration-protocol.md").read_text(encoding="utf-8")
        self.assertIn("先抓真正关窍", protocol_md)
        self.assertIn("校验", protocol_md)


if __name__ == "__main__":
    unittest.main()
