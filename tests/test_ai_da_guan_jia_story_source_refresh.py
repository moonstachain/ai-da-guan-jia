from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
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


class StorySourceRefreshWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPT_ROOT))
        cls.workflow = load_module("test_story_source_refresh_workflow", SCRIPT_ROOT / "story_source_refresh_workflow.py")
        cls.ai_da_guan_jia = load_module("test_ai_da_guan_jia_story_source_refresh", SCRIPT_ROOT / "ai_da_guan_jia.py")

    def make_args(self, **overrides):
        base = {
            "run_id": "story-source-refresh-test",
            "session": "story-refresh",
            "headless": True,
        }
        base.update(overrides)
        return type("Args", (), base)()

    def patch_paths(self, temp_root: Path):
        current = temp_root / "current"
        return patch.multiple(
            self.workflow,
            ARTIFACTS_ROOT=temp_root,
            STORY_CANON_ROOT=temp_root,
            STORY_CANON_RUNS_ROOT=temp_root / "runs",
            STORY_CANON_CURRENT_ROOT=current,
            STORY_CANON_LATEST_REFRESH_PATH=current / "latest-refresh.json",
            STORY_CANON_LAST_REAUTH_PATH=current / "last-reauth.json",
            STORY_SOURCE_BUNDLE_PATH=temp_root / "story-source-bundle.json",
            STORY_ARC_PLAN_PATH=temp_root / "story-arc-plan.md",
            CHARACTER_CONTRACT_PATH=temp_root / "character-contract.md",
        )

    def sample_flomo_ready(self):
        return {
            "status": "ready",
            "blocked_reason": "",
            "notes": [
                {
                    "memo_id": "memo-001",
                    "content": "#星球精选\n第一次把一条内容真的发出去\n\n今天我和 AI 一起把这件事走通了，中间虽然卡住，但最后还是完成了闭环。",
                    "updated_at": "2026-03-15T10:00:00+08:00",
                    "tags": ["#星球精选"],
                    "source_url": "https://v.flomoapp.com/mine/?memo_id=memo-001",
                    "deep_link": "flomo://memo/memo-001",
                    "has_image": False,
                    "attachment_urls": [],
                    "image_urls": [],
                },
                {
                    "memo_id": "memo-002",
                    "content": "#星球精选\n系统治理方法论总盘\n\n这是一个很重的系统治理方法论框架，涉及原则、架构、总盘、方法论和操作系统式的抽象收束。",
                    "updated_at": "2026-03-15T11:00:00+08:00",
                    "tags": ["#星球精选"],
                    "source_url": "https://v.flomoapp.com/mine/?memo_id=memo-002",
                    "deep_link": "flomo://memo/memo-002",
                    "has_image": False,
                    "attachment_urls": [],
                    "image_urls": [],
                },
            ],
        }

    def sample_zsxq_ready(self):
        return {
            "run_id": "story-source-refresh-test",
            "status": "ready",
            "blocked_reason": "",
            "group_url": "https://wx.zsxq.com/group/15554854424522",
            "column_name": "原力养虾炼丹",
            "entries": [
                {
                    "entry_id": "topic-001",
                    "title": "外企高管空降之后，两个伙伴怎么一起看懂局势",
                    "published_at": "2026-03-15T12:00:00+08:00",
                    "post_url": "https://wx.zsxq.com/dweb2/index/topic_detail/topic-001",
                    "body_text": "外企高管空降之后，两个伙伴怎么一起看懂局势\n\n这次难题不是概念，而是真实组织冲突。我们一起拆解判断，先看现场，再看误判。",
                    "content_hash": "hash-topic-001",
                    "source_key": "https://wx.zsxq.com/dweb2/index/topic_detail/topic-001",
                    "ordinal": 0,
                },
                {
                    "entry_id": "topic-002",
                    "title": "治理框架和方法论为什么要分层",
                    "published_at": "2026-03-15T13:00:00+08:00",
                    "post_url": "https://wx.zsxq.com/dweb2/index/topic_detail/topic-002",
                    "body_text": "治理框架和方法论为什么要分层\n\n这是偏重的系统解释，主要在讲治理框架、方法论、原则和架构应该如何分层。",
                    "content_hash": "hash-topic-002",
                    "source_key": "https://wx.zsxq.com/dweb2/index/topic_detail/topic-002",
                    "ordinal": 1,
                },
            ],
            "screenshot_path": "/tmp/zsxq-column.png",
            "attempts": [],
            "session": "story-refresh",
        }

    def test_parser_registers_story_source_refresh(self) -> None:
        parser = self.ai_da_guan_jia.build_parser()
        parsed = parser.parse_args(["story-source-refresh"])
        self.assertEqual(parsed.func.__name__, "command_story_source_refresh")
        self.assertTrue(parsed.headless is False)

    def test_auth_required_from_flomo_writes_dual_reauth_bundle(self) -> None:
        flomo_blocked = {"status": "blocked_system", "blocked_reason": "Auth required", "notes": []}
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_paths(root):
                with patch.object(self.workflow, "iso_now", return_value="2026-03-15T18:00:00+08:00"):
                    with patch.object(self.workflow.flomo_helpers, "read_flomo_candidates", return_value=flomo_blocked):
                        with patch.object(self.workflow.zsxq_helpers, "scan_zsxq_column", return_value=self.sample_zsxq_ready()):
                            exit_code = self.workflow.command_story_source_refresh(self.make_args())

            self.assertEqual(exit_code, 1)
            run_dir = root / "runs" / "2026-03-15" / "story-source-refresh-test"
            bundle = json.loads((run_dir / "reauth-bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(bundle["status"], "blocked_needs_user")
            self.assertEqual([item["system"] for item in bundle["actions"]], ["flomo", "zsxq"])
            latest = json.loads((root / "current" / "latest-refresh.json").read_text(encoding="utf-8"))
            self.assertEqual(latest["status"], "blocked_needs_user")

    def test_zsxq_login_blocked_also_writes_dual_reauth_bundle(self) -> None:
        zsxq_blocked = {
            "run_id": "story-source-refresh-test",
            "status": "blocked_needs_user",
            "blocked_reason": "知识星球浏览器会话需要重新登录。",
            "group_url": "https://wx.zsxq.com/group/15554854424522",
            "column_name": "原力养虾炼丹",
            "entries": [],
            "screenshot_path": "",
            "attempts": [],
            "session": "story-refresh",
        }
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_paths(root):
                with patch.object(self.workflow, "iso_now", return_value="2026-03-15T18:00:00+08:00"):
                    with patch.object(self.workflow.flomo_helpers, "read_flomo_candidates", return_value=self.sample_flomo_ready()):
                        with patch.object(self.workflow.zsxq_helpers, "scan_zsxq_column", return_value=zsxq_blocked):
                            exit_code = self.workflow.command_story_source_refresh(self.make_args())

            self.assertEqual(exit_code, 1)
            run_dir = root / "runs" / "2026-03-15" / "story-source-refresh-test"
            bundle = json.loads((run_dir / "reauth-bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(bundle["sources"]["zsxq"]["status"], "blocked_needs_user")
            self.assertEqual(bundle["sources"]["flomo"]["status"], "ready")

    def test_ready_refresh_generates_read_only_story_canon_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_paths(root):
                with patch.object(self.workflow, "iso_now", return_value="2026-03-15T18:00:00+08:00"):
                    with patch.object(self.workflow.flomo_helpers, "read_flomo_candidates", return_value=self.sample_flomo_ready()):
                        with patch.object(self.workflow.zsxq_helpers, "scan_zsxq_column", return_value=self.sample_zsxq_ready()):
                            with patch.object(self.workflow.zsxq_helpers, "write_flomo_memo") as write_mock:
                                exit_code = self.workflow.command_story_source_refresh(self.make_args())

            self.assertEqual(exit_code, 0)
            write_mock.assert_not_called()
            run_dir = root / "runs" / "2026-03-15" / "story-source-refresh-test"
            corpus = json.loads((run_dir / "dual-source-corpus.json").read_text(encoding="utf-8"))
            seeds = json.loads((run_dir / "episode-seeds.json").read_text(encoding="utf-8"))
            bundle = json.loads((root / "story-source-bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(corpus["status"], "ready")
            self.assertEqual(bundle["dual_source_refresh"]["status"], "ready")
            self.assertGreaterEqual(corpus["counts"]["episode_candidate"], 2)
            self.assertGreaterEqual(corpus["counts"]["reference_heavy"], 1)
            self.assertTrue(seeds["episode_candidates"])
            self.assertEqual(seeds["episode_candidates"][0]["weight_class"], "episode_candidate")
            heavy_titles = [item["title"] for item in seeds["reference_heavy"]]
            self.assertIn("系统治理方法论总盘", heavy_titles)
            self.assertTrue((run_dir / "story-source-refresh.md").exists())


if __name__ == "__main__":
    unittest.main()
