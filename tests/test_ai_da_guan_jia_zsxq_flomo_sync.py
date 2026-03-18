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


class ZsxqFlomoSyncWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPT_ROOT))
        cls.workflow = load_module("test_zsxq_flomo_sync_workflow", SCRIPT_ROOT / "zsxq_flomo_sync_workflow.py")
        cls.ai_da_guan_jia = load_module("test_ai_da_guan_jia_zsxq_flomo_sync", SCRIPT_ROOT / "ai_da_guan_jia.py")

    def make_args(self, **overrides):
        base = {
            "group_url": "https://wx.zsxq.com/group/15554854424522",
            "column_name": "原力养龙虾",
            "tag": "#星球精选",
            "source_tag": "#原力养龙虾",
            "limit": 0,
            "run_id": "zsxq-flomo-test",
            "session": None,
            "headless": True,
            "apply": False,
        }
        base.update(overrides)
        return types.SimpleNamespace(**base)

    def patch_paths(self, temp_root: Path):
        current = temp_root / "current"
        return patch.multiple(
            self.workflow,
            ARTIFACTS_ROOT=temp_root,
            ZSXQ_FLOMO_ROOT=temp_root,
            ZSXQ_FLOMO_RUNS_ROOT=temp_root / "runs",
            ZSXQ_FLOMO_CURRENT_ROOT=current,
            ZSXQ_FLOMO_CHECKPOINT_PATH=current / "checkpoint.json",
            ZSXQ_FLOMO_ENTRY_LEDGER_PATH=current / "entry-ledger.json",
            ZSXQ_FLOMO_LATEST_SCAN_PATH=current / "latest-scan.json",
            ZSXQ_FLOMO_IMPORT_PREVIEW_PATH=current / "import-preview.json",
            ZSXQ_FLOMO_WRITE_RESULT_PATH=current / "write-result.json",
        )

    def sample_entry(self, **overrides):
        base = {
            "entry_id": "topic-001",
            "title": "原力养龙虾第一篇",
            "published_at": "2026-03-01T10:00:00+08:00",
            "post_url": "https://wx.zsxq.com/dweb2/index/topic_detail/123456789",
            "body_text": "这是第一篇全文。\n有两段内容。",
            "content_hash": "hash-001",
            "source_key": "https://wx.zsxq.com/dweb2/index/topic_detail/123456789",
            "ordinal": 0,
        }
        base.update(overrides)
        return base

    def sample_scan(self, entries: list[dict[str, object]], **overrides):
        base = {
            "run_id": "zsxq-flomo-test",
            "status": "ready",
            "blocked_reason": "",
            "group_url": "https://wx.zsxq.com/group/15554854424522",
            "column_name": "原力养龙虾",
            "entries": entries,
            "screenshot_path": "/tmp/zsxq-column.png",
            "attempts": [],
            "session": "",
        }
        base.update(overrides)
        return base

    def sample_flomo_payload(self, memos: list[dict[str, object]], **overrides):
        base = {
            "status": "ready",
            "blocked_reason": "",
            "memos": memos,
        }
        base.update(overrides)
        return base

    def test_parser_registers_zsxq_flomo_sync(self) -> None:
        parser = self.ai_da_guan_jia.build_parser()
        parsed = parser.parse_args(
            [
                "zsxq-flomo-sync",
                "--group-url",
                "https://wx.zsxq.com/group/15554854424522",
                "--column-name",
                "原力养龙虾",
            ]
        )
        self.assertEqual(parsed.func.__name__, "command_zsxq_flomo_sync")
        self.assertEqual(parsed.tag, "#星球精选")
        self.assertEqual(parsed.source_tag, "#原力养龙虾")

    def test_dry_run_writes_preview_without_flomo_mutation(self) -> None:
        entry = self.sample_entry()
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_paths(root):
                with patch.object(self.workflow, "iso_now", return_value="2026-03-13T18:00:00+08:00"):
                    with patch.object(self.workflow, "scan_zsxq_column", return_value=self.sample_scan([entry])):
                        with patch.object(self.workflow, "read_flomo_tag_memos", return_value=self.sample_flomo_payload([])):
                            with patch.object(self.workflow, "write_flomo_memo") as write_mock:
                                exit_code = self.workflow.command_zsxq_flomo_sync(self.make_args())

            self.assertEqual(exit_code, 0)
            write_mock.assert_not_called()
            preview = json.loads((root / "current" / "import-preview.json").read_text(encoding="utf-8"))
            result = json.loads((root / "current" / "write-result.json").read_text(encoding="utf-8"))
            self.assertEqual(preview["counts"]["create"], 1)
            self.assertEqual(result["status"], "preview_ready")
            self.assertEqual(result["created"], 0)
            self.assertTrue((root / "runs" / "2026-03-13" / "zsxq-flomo-test" / "zsxq-scan.json").exists())

    def test_apply_creates_flomo_memo_and_updates_ledger(self) -> None:
        entry = self.sample_entry()
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_paths(root):
                with patch.object(self.workflow, "scan_zsxq_column", return_value=self.sample_scan([entry])):
                    with patch.object(self.workflow, "read_flomo_tag_memos", return_value=self.sample_flomo_payload([])):
                        with patch.object(
                            self.workflow,
                            "write_flomo_memo",
                            return_value={"status": "created", "blocked_reason": "", "memo_id": "memo-001"},
                        ):
                            exit_code = self.workflow.command_zsxq_flomo_sync(self.make_args(apply=True))

            self.assertEqual(exit_code, 0)
            ledger = json.loads((root / "current" / "entry-ledger.json").read_text(encoding="utf-8"))
            result = json.loads((root / "current" / "write-result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "applied")
            self.assertEqual(result["created"], 1)
            self.assertEqual(ledger["entries"][0]["flomo_memo_id"], "memo-001")
            self.assertEqual(ledger["entries"][0]["source_key"], entry["source_key"])

    def test_apply_is_idempotent_when_hash_is_unchanged(self) -> None:
        entry = self.sample_entry()
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            current = root / "current"
            current.mkdir(parents=True, exist_ok=True)
            (current / "entry-ledger.json").write_text(
                json.dumps(
                    {
                        "entries": [
                            {
                                "source_key": entry["source_key"],
                                "entry_id": entry["entry_id"],
                                "title": entry["title"],
                                "published_at": entry["published_at"],
                                "post_url": entry["post_url"],
                                "content_hash": entry["content_hash"],
                                "flomo_memo_id": "memo-001",
                                "run_ids": ["older-run"],
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            managed_memo = {
                "id": "memo-001",
                "content": "原力养龙虾第一篇\n\n这是第一篇全文。\n有两段内容。\n\n原文：https://wx.zsxq.com/dweb2/index/topic_detail/123456789\n\n#星球精选 #原力养龙虾",
                "updated_at": "2026-03-13T10:00:00+08:00",
                "tags": ["#星球精选", "#原力养龙虾"],
            }
            with self.patch_paths(root):
                with patch.object(self.workflow, "scan_zsxq_column", return_value=self.sample_scan([entry])):
                    with patch.object(self.workflow, "read_flomo_tag_memos", return_value=self.sample_flomo_payload([managed_memo])):
                        with patch.object(self.workflow, "write_flomo_memo") as write_mock:
                            exit_code = self.workflow.command_zsxq_flomo_sync(self.make_args(apply=True))

            self.assertEqual(exit_code, 0)
            write_mock.assert_not_called()
            result = json.loads((root / "current" / "write-result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "applied")
            self.assertEqual(result["skipped"], 1)

    def test_apply_updates_existing_managed_memo_when_hash_changes(self) -> None:
        old_entry = self.sample_entry()
        new_entry = self.sample_entry(body_text="这是新版全文。\n增加了第三段。", content_hash="hash-002")
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            current = root / "current"
            current.mkdir(parents=True, exist_ok=True)
            (current / "entry-ledger.json").write_text(
                json.dumps(
                    {
                        "entries": [
                            {
                                "source_key": old_entry["source_key"],
                                "entry_id": old_entry["entry_id"],
                                "title": old_entry["title"],
                                "published_at": old_entry["published_at"],
                                "post_url": old_entry["post_url"],
                                "content_hash": old_entry["content_hash"],
                                "flomo_memo_id": "memo-001",
                                "run_ids": ["older-run"],
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            with self.patch_paths(root):
                with patch.object(self.workflow, "scan_zsxq_column", return_value=self.sample_scan([new_entry])):
                    with patch.object(self.workflow, "read_flomo_tag_memos", return_value=self.sample_flomo_payload([])):
                        with patch.object(
                            self.workflow,
                            "write_flomo_memo",
                            return_value={"status": "updated", "blocked_reason": "", "memo_id": "memo-001"},
                        ) as write_mock:
                            exit_code = self.workflow.command_zsxq_flomo_sync(self.make_args(apply=True))

            self.assertEqual(exit_code, 0)
            write_mock.assert_called_once()
            result = json.loads((root / "current" / "write-result.json").read_text(encoding="utf-8"))
            ledger = json.loads((root / "current" / "entry-ledger.json").read_text(encoding="utf-8"))
            self.assertEqual(result["updated"], 1)
            self.assertEqual(ledger["entries"][0]["content_hash"], "hash-002")

    def test_apply_marks_manual_similarity_conflict_as_needs_review(self) -> None:
        entry = self.sample_entry()
        manual_memo = {
            "id": "memo-manual",
            "content": "#星球精选\n原力养龙虾第一篇\n\n这是第一篇全文。\n有两段内容。",
            "updated_at": "2026-03-13T10:00:00+08:00",
            "tags": ["#星球精选"],
        }
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_paths(root):
                with patch.object(self.workflow, "scan_zsxq_column", return_value=self.sample_scan([entry])):
                    with patch.object(self.workflow, "read_flomo_tag_memos", return_value=self.sample_flomo_payload([manual_memo])):
                        with patch.object(self.workflow, "write_flomo_memo") as write_mock:
                            exit_code = self.workflow.command_zsxq_flomo_sync(self.make_args(apply=True))

            self.assertEqual(exit_code, 0)
            write_mock.assert_not_called()
            result = json.loads((root / "current" / "write-result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["needs_review"], 1)
            self.assertEqual(result["writes"][0]["write_status"], "needs_review")

    def test_scan_blocked_needs_user_propagates_exit_code(self) -> None:
        blocked_scan = self.sample_scan([], status="blocked_needs_user", blocked_reason="知识星球浏览器会话需要重新登录。")
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_paths(root):
                with patch.object(self.workflow, "scan_zsxq_column", return_value=blocked_scan):
                    exit_code = self.workflow.command_zsxq_flomo_sync(self.make_args())

            self.assertEqual(exit_code, 1)
            result = json.loads((root / "current" / "write-result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "blocked_needs_user")

    def test_flomo_blocked_system_propagates_exit_code(self) -> None:
        entry = self.sample_entry()
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_paths(root):
                with patch.object(self.workflow, "scan_zsxq_column", return_value=self.sample_scan([entry])):
                    with patch.object(
                        self.workflow,
                        "read_flomo_tag_memos",
                        return_value=self.sample_flomo_payload([], status="blocked_system", blocked_reason="flomo MCP unavailable"),
                    ):
                        exit_code = self.workflow.command_zsxq_flomo_sync(self.make_args())

            self.assertEqual(exit_code, 2)
            result = json.loads((root / "current" / "write-result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "blocked_system")

    def test_preview_gate_like_content_detects_paid_preview_page(self) -> None:
        text = """
        原力养虾炼丹
        精选主题预览
        加入星球后可查看全部 51 主题
        本期低至 ¥1 /天
        付费须知
        """
        self.assertTrue(self.workflow.preview_gate_like_content(text))
        self.assertFalse(self.workflow.preview_gate_like_content("知识星球浏览器会话需要重新登录。"))
