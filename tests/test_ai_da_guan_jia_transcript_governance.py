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


class TranscriptGovernanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPT_ROOT))
        cls.module = load_module("test_ai_da_guan_jia_transcript_governance", SCRIPT_ROOT / "ai_da_guan_jia.py")

    def make_args(self, **overrides):
        base = {
            "mode": "backfill",
            "window_days": 3,
            "feishu_minutes_url": "https://example.test/feishu/minutes/me",
            "get_biji_subject_url": "https://example.test/biji/subject/DEFAULT",
            "chat_id": "oc_test",
            "proposal_mode": "propose_only",
            "send_feishu_card": True,
            "run_id": "adagj-transcript-governance-test",
            "created_at": "2026-03-12T09:00:00+08:00",
            "show_windows": False,
        }
        base.update(overrides)
        return types.SimpleNamespace(**base)

    def patch_artifact_paths(self, temp_root: Path):
        current = temp_root / "current"
        return patch.multiple(
            self.module,
            RUNS_ROOT=temp_root / "runs",
            SOUL_ROOT=temp_root / "soul",
            TRANSCRIPT_GOVERNANCE_ROOT=temp_root / "transcript-governance",
            TRANSCRIPT_GOVERNANCE_CURRENT_ROOT=current,
            TRANSCRIPT_RECORD_LEDGER_PATH=current / "record-ledger.json",
            TRANSCRIPT_SOURCE_INDEX_PATH=current / "source-index.json",
            TRANSCRIPT_DEDUPE_INDEX_PATH=current / "dedupe-index.json",
            TRANSCRIPT_PROPOSAL_QUEUE_PATH=current / "proposal-queue.json",
            TRANSCRIPT_SOURCE_CURSORS_PATH=current / "source-cursors.json",
        )

    def test_govern_transcripts_backfill_dedupes_dual_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            transcript_path = root / "biji-transcript.txt"
            transcript_path.write_text(
                "今天决定先做客户分层。帮我整理一个推进清单并在下午跟进。",
                encoding="utf-8",
            )

            def fake_fetch(url: str, *args, **kwargs):
                if url == "https://example.test/feishu/minutes/me":
                    return {
                        "ok": True,
                        "status_code": 200,
                        "final_url": url,
                        "headers": {},
                        "body": '<a href="/minutes/abc123">客户分层周会</a><div>2026/03/11 09:00</div>',
                        "error": "",
                    }
                if url == "https://example.test/minutes/abc123":
                    return {
                        "ok": True,
                        "status_code": 200,
                        "final_url": url,
                        "headers": {},
                        "body": """
                        <html><head><title>客户分层周会</title></head>
                        <body>
                        <div>2026/03/11 09:00</div>
                        <p>今天决定先做客户分层。帮我整理一个推进清单并在下午跟进。</p>
                        <p>后续需要再做一次调研分析。</p>
                        </body></html>
                        """,
                        "error": "",
                    }
                if url == "https://example.test/biji/subject/DEFAULT":
                    return {
                        "ok": True,
                        "status_code": 200,
                        "final_url": url,
                        "headers": {},
                        "body": '<a href="/note/1903496783305829808">客户分层周会</a><div>2026/03/11 09:00</div>',
                        "error": "",
                    }
                return {"ok": False, "status_code": 404, "final_url": url, "headers": {}, "body": "", "error": "not_found"}

            with self.patch_artifact_paths(root), patch.object(self.module, "append_daily_soul_log", lambda evolution: None):
                with patch.object(self.module, "prepare_github_materials", return_value={}):
                    with patch.object(self.module, "run_feishu_sync", return_value=(0, "dry_run_preview_ready")):
                        with patch.object(self.module, "sync_github_run", return_value=(0, "github_closure_preview_ready")):
                            with patch.object(self.module, "send_digest_to_feishu_chat", return_value={"status": "sent_card"}):
                                with patch.object(self.module, "fetch_text_document", side_effect=fake_fetch):
                                    with patch.object(
                                        self.module,
                                        "fetch_get_biji_original_transcript",
                                        return_value={
                                            "success": True,
                                            "verification_status": "transcript_ready",
                                            "verification_note": "ok",
                                            "transcript_path": str(transcript_path),
                                            "note_title": "客户分层周会",
                                        },
                                    ):
                                        exit_code = self.module.command_govern_transcripts(self.make_args())

            self.assertEqual(exit_code, 0)
            run_dir = root / "runs" / "2026-03-12" / "adagj-transcript-governance-test"
            canonical_records = json.loads((run_dir / "canonical-records.json").read_text(encoding="utf-8"))
            task_proposals = json.loads((run_dir / "task-proposals.json").read_text(encoding="utf-8"))
            self.assertEqual(len(canonical_records), 1)
            self.assertEqual(canonical_records[0]["source_coverage"], "dual_source")
            self.assertTrue(canonical_records[0]["transcript_path"])
            self.assertGreaterEqual(len(task_proposals), 1)

    def test_late_transcript_arrival_updates_existing_record(self) -> None:
        existing = {
            "record_id": "transcript::abc",
            "source_type": "feishu_minutes",
            "source_url": "https://example.test/minutes/abc123",
            "source_item_id": "abc123",
            "captured_at": "2026-03-11T09:00:00+08:00",
            "title": "客户分层周会",
            "dedupe_key": "abc",
            "transcript_path": "",
            "verification_status": "metadata_only",
            "verification_note": "metadata only",
            "source_coverage": "feishu_minutes_only",
            "transcript_hash": "",
            "normalized_title": "客户分层周会",
            "source_refs": [
                {
                    "source_type": "feishu_minutes",
                    "source_url": "https://example.test/minutes/abc123",
                    "source_item_id": "abc123",
                    "captured_at": "2026-03-11T09:00:00+08:00",
                    "verification_status": "metadata_only",
                    "verification_note": "metadata only",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tempdir:
            transcript_path = Path(tempdir) / "late.txt"
            transcript_path.write_text("帮我继续推进客户分层项目。", encoding="utf-8")
            source_record = self.module.make_source_record(
                source_type="get_biji",
                source_url="https://example.test/note/1903496783305829808",
                source_item_id="1903496783305829808",
                captured_at="2026-03-11T09:05:00+08:00",
                title="客户分层周会",
                transcript_path=str(transcript_path),
                verification_status="transcript_ready",
                verification_note="late transcript",
            )
            state = {
                "records": [existing],
                "source_index": {"feishu_minutes::abc123": "transcript::abc"},
                "dedupe_index": {"abc": "transcript::abc"},
                "proposal_queue": [],
                "source_cursors": {},
            }
            updated = self.module.update_transcript_governance_state(
                state=state,
                source_records=[source_record],
                source_cursors={"get_biji": "2026-03-11T09:05:00+08:00"},
            )
            self.assertEqual(len(updated["records"]), 1)
            self.assertEqual(updated["records"][0]["record_id"], "transcript::abc")
            self.assertEqual(updated["records"][0]["source_coverage"], "dual_source")
            self.assertTrue(updated["records"][0]["transcript_path"].endswith("late.txt"))

    def test_heartbeat_digest_when_no_new_records(self) -> None:
        digest = self.module.build_review_digest(
            mode="scheduled",
            run_id="adagj-heartbeat",
            records=[],
            changed_records=[],
            intent_ledger=[],
            task_proposals=[],
            source_artifacts={},
        )
        markdown = self.module.render_review_digest_markdown(digest)
        self.assertEqual(digest["counts"]["new_or_updated_records"], 0)
        self.assertIn("0 条新增或更新逐字稿", markdown)
        self.assertTrue(digest["next_check_time"])

    def test_send_failure_is_recorded_but_command_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)

            def fake_fetch(url: str, *args, **kwargs):
                return {"ok": True, "status_code": 200, "final_url": url, "headers": {}, "body": "", "error": ""}

            with self.patch_artifact_paths(root), patch.object(self.module, "append_daily_soul_log", lambda evolution: None):
                with patch.object(self.module, "prepare_github_materials", return_value={}):
                    with patch.object(self.module, "run_feishu_sync", return_value=(0, "payload_only_missing_link")):
                        with patch.object(self.module, "sync_github_run", return_value=(0, "github_blocked_missing_repo")):
                            with patch.object(self.module, "send_digest_to_feishu_chat", return_value={"status": "send_failed", "error": "boom"}):
                                with patch.object(self.module, "fetch_text_document", side_effect=fake_fetch):
                                    exit_code = self.module.command_govern_transcripts(self.make_args(send_feishu_card=False))

            self.assertEqual(exit_code, 0)
            run_dir = root / "runs" / "2026-03-12" / "adagj-transcript-governance-test"
            delivery = json.loads((run_dir / "delivery-result.json").read_text(encoding="utf-8"))
            digest = json.loads((run_dir / "review-digest.json").read_text(encoding="utf-8"))
            self.assertEqual(delivery["status"], "send_failed")
            self.assertEqual(digest["counts"]["new_or_updated_records"], 0)
            closure = json.loads((run_dir / "closure-status.json").read_text(encoding="utf-8"))
            self.assertEqual(closure["status"], "partial")

    def test_locked_browser_profile_uses_shadow_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            profile_dir = root / "Chrome"
            (profile_dir / "Default").mkdir(parents=True)
            (profile_dir / "Default" / "Cookies").write_text("cookie-cache", encoding="utf-8")
            (profile_dir / "SingletonLock").write_text("locked", encoding="utf-8")

            with patch.object(self.module, "DEFAULT_CHROME_USER_DATA_DIR", profile_dir):
                launch_dir, cleanup_root = self.module.prepare_transcript_browser_launch_dir(
                    profile_dir,
                    source_type="feishu_minutes",
                )

            try:
                self.assertNotEqual(launch_dir, profile_dir)
                self.assertTrue((launch_dir / "Default" / "Cookies").exists())
                self.assertFalse((launch_dir / "SingletonLock").exists())
                self.assertIsNotNone(cleanup_root)
                self.assertTrue(cleanup_root.exists())
            finally:
                if cleanup_root is not None:
                    shutil.rmtree(cleanup_root, ignore_errors=True)

    def test_browser_minutes_entries_skips_navigation_links(self) -> None:
        class FakePage:
            def evaluate(self, script):
                return [
                    {"href": "https://h52xu4gwob.feishu.cn/minutes/home", "title": "首页", "context_text": ""},
                    {"href": "https://h52xu4gwob.feishu.cn/minutes/shared", "title": "共享", "context_text": ""},
                    {
                        "href": "https://h52xu4gwob.feishu.cn/minutes/obcnlun9e14l7r498rr111b7",
                        "title": "董事会沟通",
                        "context_text": "2026/03/12 09:00",
                    },
                ]

        entries = self.module.browser_minutes_entries(FakePage())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "董事会沟通")

    def test_show_windows_updates_stage_and_blocked_state(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            stage_calls = []

            def fake_fetch(url: str, *args, **kwargs):
                if url == "https://example.test/feishu/minutes/me":
                    return {
                        "ok": True,
                        "status_code": 200,
                        "final_url": url,
                        "headers": {},
                        "body": '<a href="/minutes/abc123">董事会记录</a><div>2026/03/11 09:00</div>',
                        "error": "",
                    }
                if url == "https://example.test/minutes/abc123":
                    return {"ok": False, "status_code": 401, "final_url": url, "headers": {}, "body": "请先登录", "error": "http_401"}
                return {"ok": True, "status_code": 200, "final_url": url, "headers": {}, "body": "", "error": ""}

            with self.patch_artifact_paths(root), patch.object(self.module, "append_daily_soul_log", lambda evolution: None):
                with patch.object(self.module, "prepare_github_materials", return_value={}):
                    with patch.object(self.module, "run_feishu_sync", return_value=(0, "payload_only_missing_link")):
                        with patch.object(self.module, "sync_github_run", return_value=(0, "github_blocked_missing_repo")):
                            with patch.object(self.module, "send_digest_to_feishu_chat", return_value={"status": "send_failed", "error": "boom"}):
                                with patch.object(self.module, "fetch_text_document", side_effect=fake_fetch):
                                    with patch.object(
                                        self.module,
                                        "fetch_browser_document",
                                        return_value={
                                            "ok": False,
                                            "status_code": 401,
                                            "final_url": "https://example.test/minutes/abc123",
                                            "headers": {},
                                            "body": "请先登录",
                                            "error": "",
                                            "diagnosis": "auth_gate",
                                        },
                                    ):
                                        with patch.object(self.module, "update_visible_stage", side_effect=lambda **kwargs: stage_calls.append(kwargs) or {}):
                                            exit_code = self.module.command_govern_transcripts(self.make_args(show_windows=True, send_feishu_card=False))

            self.assertEqual(exit_code, 0)
            self.assertGreaterEqual(len(stage_calls), 3)
            self.assertEqual(stage_calls[0]["stage"], "start")
            self.assertEqual(stage_calls[-1]["status"], "blocked_needs_user")


if __name__ == "__main__":
    unittest.main()
