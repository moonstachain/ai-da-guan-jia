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
SCRIPT_ROOT = PROJECT_ROOT / "work" / "ai-da-guan-jia" / "scripts"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def fake_zsxq_module(publish_result: dict[str, object] | None = None):
    publish_result = publish_result or {
        "status": "browser_opened_manual_confirmation_required",
        "message": "browser opened",
    }

    def plan_from_capture(capture):
        return {
            "run_id": capture["run_id"],
            "entry_type": "觉醒日志",
            "material_status": capture["material_sufficiency"]["status"],
            "themes": capture["themes"],
            "core_conclusion": capture["themes"][0],
            "tag_suggestions": ["觉醒日志", "原力星球"],
            "manual_confirmation_items": ["确认标题", "确认边界"],
            "risk_items": [],
            "open_questions": [],
        }

    def render_draft(plan, capture):
        return (
            "---\n"
            f"run_id: {plan['run_id']}\n"
            f"entry_type: {plan['entry_type']}\n"
            f"material_status: {plan['material_status']}\n"
            "title: 测试草稿\n"
            "tags:\n"
            "  - 觉醒日志\n"
            "---\n\n"
            "# 测试草稿\n\n"
            f"{capture['materials'][0]['preview']}\n"
        )

    def parse_simple_frontmatter(_text):
        return {"title": "测试草稿", "entry_type": "觉醒日志", "material_status": "ready", "tags": ["觉醒日志"]}

    def prepare_publish_packet(run_dir, draft_text, meta, plan):
        return {
            "run_id": plan["run_id"],
            "status": "ready_for_manual_publish",
            "post_type": "主题",
            "title": meta["title"],
            "body_markdown": draft_text,
            "tag_suggestions": plan["tag_suggestions"],
            "column_suggestions": [plan.get("target_column_name") or "觉醒日志"],
            "target_column_name": plan.get("target_column_name", ""),
            "manual_confirmation_items": plan["manual_confirmation_items"],
            "platform_url": "https://www.zsxq.com/",
            "artifact_dir": str(run_dir.resolve()),
        }

    def build_review(_run_dir, publish_result_payload, _feedback):
        return (
            f"# Review\n\n- Publish status: {publish_result_payload['status']}\n",
            {"run_id": publish_result_payload.get("run_id", ""), "next_diary": ["next"]},
        )

    def run_publish_web(_packet, execute, headed, session):
        result = dict(publish_result)
        result["attempted_execute"] = execute
        result["headed"] = headed
        result["session"] = session
        return result

    return types.SimpleNamespace(
        plan_from_capture=plan_from_capture,
        render_draft=render_draft,
        parse_simple_frontmatter=parse_simple_frontmatter,
        prepare_publish_packet=prepare_publish_packet,
        build_review=build_review,
        run_publish_web=run_publish_web,
    )


def fake_ai_da_guan_jia_module(publish_result: dict[str, object] | None = None):
    publish_result = publish_result or {
        "status": "manual_confirmation_required",
        "message": "publish page is ready",
    }

    def tool_glue_run_zsxq_publish_web(_packet, *, execute, headed, session, final_send=False):
        result = dict(publish_result)
        result["attempted_execute"] = execute
        result["headed"] = headed
        result["session"] = session
        result["final_send_requested"] = final_send
        return result

    return types.SimpleNamespace(tool_glue_run_zsxq_publish_web=tool_glue_run_zsxq_publish_web)


class FlomoZsxqWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPT_ROOT))
        cls.workflow = load_module("test_flomo_zsxq_workflow", SCRIPT_ROOT / "flomo_zsxq_workflow.py")
        cls.ai_da_guan_jia = load_module("test_ai_da_guan_jia_flomo_zsxq", SCRIPT_ROOT / "ai_da_guan_jia.py")

    def make_poll_args(self, **overrides):
        base = {
            "tag": "#星球精选",
            "limit": 20,
            "run_id": "flomo-poll-test",
            "created_at": "2026-03-13T10:00:00+08:00",
            "column_name": "原力小刺猬",
            "series_mode": "ai_da_guan_jia_observer",
            "image_source": "flomo_attachment",
            "image_policy": "required",
            "rollout_stage": "staged",
            "group_url": "https://wx.zsxq.com/group/15554854424522",
        }
        base.update(overrides)
        return types.SimpleNamespace(**base)

    def make_backfill_args(self, **overrides):
        base = {
            "tag": "#星球精选",
            "limit": 200,
            "run_id": "flomo-backfill-test",
            "created_at": "2026-03-13T10:00:00+08:00",
            "column_name": "原力小刺猬",
            "series_mode": "ai_da_guan_jia_observer",
            "image_source": "flomo_attachment",
            "image_policy": "required",
            "rollout_stage": "staged",
            "group_url": "https://wx.zsxq.com/group/15554854424522",
        }
        base.update(overrides)
        return types.SimpleNamespace(**base)

    def make_publish_args(self, **overrides):
        base = {
            "run_id": "flomo-zsxq-20260313-100000-000000-aaaaaaaa",
            "apply": False,
            "headless": False,
            "session": None,
            "final_send": False,
            "manual_approval": False,
            "column_name": "原力小刺猬",
            "series_mode": "ai_da_guan_jia_observer",
            "image_source": "flomo_attachment",
            "image_policy": "required",
            "rollout_stage": "staged",
            "group_url": "https://wx.zsxq.com/group/15554854424522",
        }
        base.update(overrides)
        return types.SimpleNamespace(**base)

    def sample_scene(self) -> dict[str, object]:
        return {
            "title": "【原力小刺猬】测试观察",
            "opening_scene": "我先看到的是一段真实工作现场。",
            "what_i_saw": "AI大管家开始把零散线索组织成更完整的行动。",
            "why_i_judged_it": "因为它不只是回答问题，而是在推进一个闭环。",
            "ai_change": "这说明 AI 正在从答题机走向任务协作者。",
            "reader_relevance": "普通人也可以从这里理解 AI 的真正价值不在聊天，而在工作流。",
            "facts": ["fact-1"],
            "observations": ["observation-1"],
            "inferences": ["inference-1"],
            "caveats": [],
            "question_hook": "你最想先让 AI 接管哪一步？",
        }

    def sample_image_manifest(self, *, status: str = "ready", blocked_reason: str = "") -> dict[str, object]:
        return {
            "status": status,
            "blocked_reason": blocked_reason,
            "ocr_status": "ready" if status == "ready" else "blocked_system",
            "ocr_text": "截图里出现了 AI大管家 的运行证据",
            "ocr_text_excerpt": "截图里出现了 AI大管家 的运行证据",
            "page_text_excerpt": "page text",
            "evidence_paths": ["/tmp/flomo-attachment-page.png", "/tmp/flomo-attachment-page.txt"],
            "image_count": 1 if status == "ready" else 0,
            "image_candidates": [{"src": "https://example.test/image.png", "alt": "运行截图"}],
        }

    def capture_image_evidence_stub(self, *, status: str = "ready", blocked_reason: str = ""):
        manifest = self.sample_image_manifest(status=status, blocked_reason=blocked_reason)

        def _capture(_note, *, run_dir, image_source, image_policy, session=None):
            (run_dir / "image-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return manifest

        return _capture

    def patch_paths(self, temp_root: Path):
        current = temp_root / "current"
        return patch.multiple(
            self.workflow,
            ARTIFACTS_ROOT=temp_root,
            FLOMO_ZSXQ_ROOT=temp_root,
            FLOMO_ZSXQ_RUNS_ROOT=temp_root / "runs",
            FLOMO_ZSXQ_CURRENT_ROOT=current,
            FLOMO_ZSXQ_CHECKPOINT_PATH=current / "checkpoint.json",
            FLOMO_ZSXQ_NOTE_LEDGER_PATH=current / "note-ledger.json",
            FLOMO_ZSXQ_POLL_RESULT_PATH=current / "latest-poll.json",
            FLOMO_ZSXQ_PUBLISH_QUEUE_PATH=current / "publish-queue.json",
            FLOMO_ZSXQ_ROLLOUT_STATE_PATH=current / "rollout-state.json",
            FLOMO_ZSXQ_BACKFILL_RESULT_PATH=current / "latest-backfill.json",
        )

    def test_parser_registers_flomo_commands(self) -> None:
        parser = self.ai_da_guan_jia.build_parser()
        parsed_poll = parser.parse_args(["flomo-zsxq-poll", "--tag", "#星球精选"])
        parsed_backfill = parser.parse_args(["flomo-zsxq-backfill", "--tag", "#星球精选"])
        parsed_publish = parser.parse_args(["flomo-zsxq-publish", "--run-id", "demo-run"])
        self.assertEqual(parsed_poll.func.__name__, "command_flomo_zsxq_poll")
        self.assertEqual(parsed_backfill.func.__name__, "command_flomo_zsxq_backfill")
        self.assertEqual(parsed_publish.func.__name__, "command_flomo_zsxq_publish")

    def test_poll_creates_candidate_bundle_for_tagged_note_only(self) -> None:
        fetched = {
            "status": "ready",
            "blocked_reason": "",
            "notes": [
                {
                    "memo_id": "memo-001",
                    "content": "#星球精选\n今天我把一条碎片想法整理成方法。",
                    "updated_at": "2026-03-13T09:30:00+08:00",
                    "tags": ["#星球精选", "#觉醒"],
                    "source_url": "https://v.flomoapp.com/mine/?memo_id=memo-001",
                    "deep_link": "flomo://memo/memo-001",
                    "has_image": True,
                },
                {
                    "memo_id": "memo-002",
                    "content": "这条没有标签，不应该入链。",
                    "updated_at": "2026-03-13T09:31:00+08:00",
                    "tags": ["#其他"],
                    "source_url": "",
                    "deep_link": "",
                },
            ],
        }
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_paths(root):
                with patch.object(self.workflow, "read_flomo_candidates", return_value=fetched):
                    with patch.object(self.workflow, "load_zsxq_assistant_module", return_value=fake_zsxq_module()):
                        with patch.object(self.workflow, "capture_image_evidence", side_effect=self.capture_image_evidence_stub()):
                            with patch.object(self.workflow, "generate_scene_reconstruction", return_value=self.sample_scene()):
                                exit_code = self.workflow.command_flomo_zsxq_poll(self.make_poll_args())

            self.assertEqual(exit_code, 0)
            ledger = json.loads((root / "current" / "note-ledger.json").read_text(encoding="utf-8"))
            self.assertEqual(len(ledger["notes"]), 1)
            run_id = ledger["notes"][0]["latest_run_id"]
            run_dir = root / "runs" / "2026-03-13" / run_id
            self.assertTrue((run_dir / "flomo-source.json").exists())
            self.assertTrue((run_dir / "source.md").exists())
            self.assertTrue((run_dir / "image-manifest.json").exists())
            self.assertTrue((run_dir / "scene-reconstruction.json").exists())
            self.assertTrue((run_dir / "entry-plan.json").exists())
            self.assertTrue((run_dir / "series-metadata.json").exists())
            self.assertTrue((run_dir / "serial-draft.md").exists())
            self.assertTrue((run_dir / "draft.md").exists())
            self.assertTrue((run_dir / "publish-packet.json").exists())
            self.assertTrue((run_dir / "publish-preview.md").exists())
            self.assertTrue((run_dir / "publish-result.json").exists())
            self.assertTrue((run_dir / "review.md").exists())
            self.assertTrue((run_dir / "checkpoint.json").exists())
            packet = json.loads((run_dir / "publish-packet.json").read_text(encoding="utf-8"))
            self.assertEqual(packet["target_column_name"], "原力小刺猬")
            self.assertEqual(packet["human_role"], "小刺猬")
            self.assertEqual(packet["ai_role"], "小精怪")
            series_metadata = json.loads((run_dir / "series-metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(series_metadata["story_model"], "hero_journey_dual_partner")

    def test_poll_dedupes_same_note_when_timestamp_is_unchanged(self) -> None:
        fetched = {
            "status": "ready",
            "blocked_reason": "",
            "notes": [
                {
                    "memo_id": "memo-001",
                    "content": "#星球精选\n同一条 flomo 记录。",
                    "updated_at": "2026-03-13T09:30:00+08:00",
                    "tags": ["#星球精选"],
                    "source_url": "",
                    "deep_link": "",
                    "has_image": True,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_paths(root):
                with patch.object(self.workflow, "read_flomo_candidates", return_value=fetched):
                    with patch.object(self.workflow, "load_zsxq_assistant_module", return_value=fake_zsxq_module()):
                        with patch.object(self.workflow, "capture_image_evidence", side_effect=self.capture_image_evidence_stub()):
                            with patch.object(self.workflow, "generate_scene_reconstruction", return_value=self.sample_scene()):
                                first_exit = self.workflow.command_flomo_zsxq_poll(self.make_poll_args(run_id="poll-1"))
                                second_exit = self.workflow.command_flomo_zsxq_poll(self.make_poll_args(run_id="poll-2"))

            self.assertEqual(first_exit, 0)
            self.assertEqual(second_exit, 0)
            ledger = json.loads((root / "current" / "note-ledger.json").read_text(encoding="utf-8"))
            self.assertEqual(len(ledger["notes"]), 1)
            self.assertEqual(len(ledger["notes"][0]["run_ids"]), 1)
            latest_poll = json.loads((root / "current" / "latest-poll.json").read_text(encoding="utf-8"))
            self.assertEqual(latest_poll["created_count"], 0)

    def test_publish_without_apply_stays_in_draft_ready(self) -> None:
        fetched = {
            "status": "ready",
            "blocked_reason": "",
            "notes": [
                {
                    "memo_id": "memo-001",
                    "content": "#星球精选\n今天记录一次真实变化。",
                    "updated_at": "2026-03-13T09:30:00+08:00",
                    "tags": ["#星球精选"],
                    "source_url": "",
                    "deep_link": "",
                    "has_image": True,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_paths(root):
                with patch.object(self.workflow, "read_flomo_candidates", return_value=fetched):
                    with patch.object(self.workflow, "load_zsxq_assistant_module", return_value=fake_zsxq_module()):
                        with patch.object(self.workflow, "capture_image_evidence", side_effect=self.capture_image_evidence_stub()):
                            with patch.object(self.workflow, "generate_scene_reconstruction", return_value=self.sample_scene()):
                                self.workflow.command_flomo_zsxq_poll(self.make_poll_args())
                                ledger = json.loads((root / "current" / "note-ledger.json").read_text(encoding="utf-8"))
                                run_id = ledger["notes"][0]["latest_run_id"]
                                exit_code = self.workflow.command_flomo_zsxq_publish(self.make_publish_args(run_id=run_id, apply=False))

            self.assertEqual(exit_code, 0)
            result = json.loads((root / "runs" / "2026-03-13" / run_id / "publish-result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["publish_state"], "draft_ready")
            self.assertEqual(result["final_human_confirmation"], "pending")

    def test_publish_apply_maps_auth_failure_to_blocked_needs_user(self) -> None:
        fetched = {
            "status": "ready",
            "blocked_reason": "",
            "notes": [
                {
                    "memo_id": "memo-001",
                    "content": "#星球精选\n今天记录一次真实变化。",
                    "updated_at": "2026-03-13T09:30:00+08:00",
                    "tags": ["#星球精选"],
                    "source_url": "",
                    "deep_link": "",
                    "has_image": True,
                }
            ],
        }
        blocked_publish = {"status": "blocked_needs_user", "message": "knowledge planet login required"}
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_paths(root):
                with patch.object(self.workflow, "read_flomo_candidates", return_value=fetched):
                    with patch.object(self.workflow, "load_zsxq_assistant_module", return_value=fake_zsxq_module(blocked_publish)):
                        with patch.object(self.workflow, "load_ai_da_guan_jia_module", return_value=fake_ai_da_guan_jia_module(blocked_publish)):
                            with patch.object(self.workflow, "capture_image_evidence", side_effect=self.capture_image_evidence_stub()):
                                with patch.object(self.workflow, "generate_scene_reconstruction", return_value=self.sample_scene()):
                                    self.workflow.command_flomo_zsxq_poll(self.make_poll_args())
                                    ledger = json.loads((root / "current" / "note-ledger.json").read_text(encoding="utf-8"))
                                    run_id = ledger["notes"][0]["latest_run_id"]
                                    exit_code = self.workflow.command_flomo_zsxq_publish(self.make_publish_args(run_id=run_id, apply=True))

            self.assertEqual(exit_code, 1)
            result = json.loads((root / "runs" / "2026-03-13" / run_id / "publish-result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["publish_state"], "blocked_needs_user")

    def test_publish_apply_generates_review_after_success(self) -> None:
        fetched = {
            "status": "ready",
            "blocked_reason": "",
            "notes": [
                {
                    "memo_id": "memo-001",
                    "content": "#星球精选\n今天记录一次真实变化。",
                    "updated_at": "2026-03-13T09:30:00+08:00",
                    "tags": ["#星球精选"],
                    "source_url": "",
                    "deep_link": "",
                    "has_image": True,
                }
            ],
        }
        published = {"status": "published", "message": "posted", "published_url": "https://example.test/post/1"}
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_paths(root):
                with patch.object(self.workflow, "read_flomo_candidates", return_value=fetched):
                    with patch.object(self.workflow, "load_zsxq_assistant_module", return_value=fake_zsxq_module(published)):
                        with patch.object(self.workflow, "load_ai_da_guan_jia_module", return_value=fake_ai_da_guan_jia_module(published)):
                            with patch.object(self.workflow, "capture_image_evidence", side_effect=self.capture_image_evidence_stub()):
                                with patch.object(self.workflow, "generate_scene_reconstruction", return_value=self.sample_scene()):
                                    self.workflow.command_flomo_zsxq_poll(self.make_poll_args())
                                    ledger = json.loads((root / "current" / "note-ledger.json").read_text(encoding="utf-8"))
                                    run_id = ledger["notes"][0]["latest_run_id"]
                                    exit_code = self.workflow.command_flomo_zsxq_publish(
                                        self.make_publish_args(run_id=run_id, apply=True, final_send=True, manual_approval=True)
                                    )

            self.assertEqual(exit_code, 0)
            result = json.loads((root / "runs" / "2026-03-13" / run_id / "publish-result.json").read_text(encoding="utf-8"))
            review_text = (root / "runs" / "2026-03-13" / run_id / "review.md").read_text(encoding="utf-8")
            self.assertEqual(result["publish_state"], "published")
            self.assertIn("published", review_text)

    def test_poll_blocks_when_required_image_evidence_is_missing(self) -> None:
        fetched = {
            "status": "ready",
            "blocked_reason": "",
            "notes": [
                {
                    "memo_id": "memo-001",
                    "content": "#星球精选\n这条没有成功拿到图片。",
                    "updated_at": "2026-03-13T09:30:00+08:00",
                    "tags": ["#星球精选"],
                    "source_url": "",
                    "deep_link": "",
                    "has_image": True,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_paths(root):
                with patch.object(self.workflow, "read_flomo_candidates", return_value=fetched):
                    with patch.object(self.workflow, "load_zsxq_assistant_module", return_value=fake_zsxq_module()):
                        with patch.object(
                            self.workflow,
                            "capture_image_evidence",
                            side_effect=self.capture_image_evidence_stub(status="blocked_system", blocked_reason="OCR failed"),
                        ):
                            exit_code = self.workflow.command_flomo_zsxq_poll(self.make_poll_args())

            self.assertEqual(exit_code, 0)
            ledger = json.loads((root / "current" / "note-ledger.json").read_text(encoding="utf-8"))
            run_id = ledger["notes"][0]["latest_run_id"]
            run_dir = root / "runs" / "2026-03-13" / run_id
            result = json.loads((run_dir / "publish-result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["publish_state"], "blocked_system")
            self.assertFalse((run_dir / "publish-packet.json").exists())

    def test_backfill_uses_same_pipeline_and_dedupes_existing_runs(self) -> None:
        fetched = {
            "status": "ready",
            "blocked_reason": "",
            "notes": [
                {
                    "memo_id": "memo-001",
                    "content": "#星球精选\n回填历史记录。",
                    "updated_at": "2026-03-11T09:30:00+08:00",
                    "tags": ["#星球精选"],
                    "source_url": "",
                    "deep_link": "",
                    "has_image": True,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_paths(root):
                with patch.object(self.workflow, "read_flomo_candidates", return_value=fetched):
                    with patch.object(self.workflow, "load_zsxq_assistant_module", return_value=fake_zsxq_module()):
                        with patch.object(self.workflow, "capture_image_evidence", side_effect=self.capture_image_evidence_stub()):
                            with patch.object(self.workflow, "generate_scene_reconstruction", return_value=self.sample_scene()):
                                first_exit = self.workflow.command_flomo_zsxq_backfill(self.make_backfill_args(run_id="backfill-1"))
                                second_exit = self.workflow.command_flomo_zsxq_backfill(self.make_backfill_args(run_id="backfill-2"))

            self.assertEqual(first_exit, 0)
            self.assertEqual(second_exit, 0)
            latest = json.loads((root / "current" / "latest-backfill.json").read_text(encoding="utf-8"))
            self.assertEqual(latest["created_count"], 0)

    def test_publish_final_send_stays_locked_until_rollout_is_unlocked(self) -> None:
        fetched = {
            "status": "ready",
            "blocked_reason": "",
            "notes": [
                {
                    "memo_id": "memo-001",
                    "content": "#星球精选\n今天记录一次真实变化。",
                    "updated_at": "2026-03-13T09:30:00+08:00",
                    "tags": ["#星球精选"],
                    "source_url": "",
                    "deep_link": "",
                    "has_image": True,
                }
            ],
        }
        publish_result = {"status": "manual_confirmation_required", "message": "prepared"}
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_paths(root):
                with patch.object(self.workflow, "read_flomo_candidates", return_value=fetched):
                    with patch.object(self.workflow, "load_zsxq_assistant_module", return_value=fake_zsxq_module()):
                        with patch.object(self.workflow, "load_ai_da_guan_jia_module", return_value=fake_ai_da_guan_jia_module(publish_result)):
                            with patch.object(self.workflow, "capture_image_evidence", side_effect=self.capture_image_evidence_stub()):
                                with patch.object(self.workflow, "generate_scene_reconstruction", return_value=self.sample_scene()):
                                    self.workflow.command_flomo_zsxq_poll(self.make_poll_args())
                                    ledger = json.loads((root / "current" / "note-ledger.json").read_text(encoding="utf-8"))
                                    run_id = ledger["notes"][0]["latest_run_id"]
                                    exit_code = self.workflow.command_flomo_zsxq_publish(
                                        self.make_publish_args(run_id=run_id, apply=True, final_send=True)
                                    )

            self.assertEqual(exit_code, 0)
            result = json.loads((root / "runs" / "2026-03-13" / run_id / "publish-result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["publish_state"], "manual_confirmation_required")
            self.assertTrue(result["rollout_locked"])

    def test_poll_reports_blocked_needs_user_when_flomo_mcp_is_missing(self) -> None:
        blocked = {
            "status": "blocked_needs_user",
            "blocked_reason": "flomo MCP server is not configured in Codex.",
            "notes": [],
            "setup_hint": {"commands": ["codex mcp add flomo --url https://flomoapp.com/mcp"]},
        }
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_paths(root):
                with patch.object(self.workflow, "read_flomo_candidates", return_value=blocked):
                    exit_code = self.workflow.command_flomo_zsxq_poll(self.make_poll_args())

            self.assertEqual(exit_code, 1)
            latest = json.loads((root / "current" / "latest-poll.json").read_text(encoding="utf-8"))
            self.assertEqual(latest["status"], "blocked_needs_user")

    def test_read_flomo_candidates_falls_back_to_last_message_when_output_schema_times_out(self) -> None:
        mcp_state = {"configured": True, "enabled": True, "payload": {"name": "flomo"}}
        fallback_payload = {
            "status": "ready",
            "blocked_reason": "",
            "notes": [
                {
                    "memo_id": "memo-001",
                    "content": "#星球精选\n这是一条可以入链的 flomo 记录。",
                    "updated_at": "2026-03-13T09:30:00+08:00",
                    "tags": ["星球精选"],
                }
            ],
        }
        with patch.object(self.workflow, "read_mcp_config", return_value=mcp_state):
            with patch.object(
                self.workflow,
                "run_codex_exec_json",
                return_value={"returncode": 124, "stdout": "", "stderr": "Codex exec timed out after 180 seconds."},
            ):
                with patch.object(
                    self.workflow,
                    "run_codex_exec_last_message",
                    return_value={
                        "returncode": 0,
                        "stdout": "",
                        "stderr": "",
                        "json": fallback_payload,
                    },
                ):
                    result = self.workflow.read_flomo_candidates("#星球精选", {}, 5)

        self.assertEqual(result["status"], "ready")
        self.assertEqual(len(result["notes"]), 1)
        self.assertEqual(result["notes"][0]["memo_id"], "memo-001")
        self.assertEqual(result["exec_result"]["mode"], "last_message_fallback")

    def test_flomo_poll_schema_requires_all_declared_note_fields(self) -> None:
        schema = self.workflow.flomo_poll_schema()
        note_schema = schema["properties"]["notes"]["items"]
        self.assertEqual(sorted(note_schema["required"]), sorted(note_schema["properties"].keys()))


if __name__ == "__main__":
    unittest.main()
