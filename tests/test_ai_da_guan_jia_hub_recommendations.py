from __future__ import annotations

import importlib.util
import os
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


class HubRecommendationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPT_ROOT))
        cls.ai_da_guan_jia = load_module(
            "test_ai_da_guan_jia_hub_recommendations",
            SCRIPT_ROOT / "ai_da_guan_jia.py",
        )

    def test_build_recommendations_flags_transport_blocker_when_remote_unreachable(self) -> None:
        recommendations = self.ai_da_guan_jia.build_recommendations(
            task_ledger=[],
            skill_ledger=[],
            source_bundles={"main-hub": {"machine_profile": {"hostname": "MacBookPro"}}},
            summary={
                "missing_sources": ["satellite-01", "satellite-02"],
                "transport": {"remote_reachable": False, "github_backend": ""},
            },
        )

        self.assertEqual(recommendations["next_steps"][0]["title"], "先打通 ai-task-ops 远端 transport")
        self.assertIn("远端不可达", recommendations["next_steps"][0]["why"])
        self.assertIn("satellite-01", recommendations["next_steps"][1]["why"])

    def test_build_recommendations_explains_shadow_bootstrap_when_sources_are_colocated(self) -> None:
        recommendations = self.ai_da_guan_jia.build_recommendations(
            task_ledger=[],
            skill_ledger=[],
            source_bundles={
                "main-hub": {"machine_profile": {"hostname": "MacBookPro"}},
                "satellite-01": {"machine_profile": {"hostname": "MacBookPro"}},
                "satellite-02": {"machine_profile": {"hostname": "MacBookPro"}},
            },
            summary={
                "missing_sources": [],
                "transport": {"remote_reachable": True, "github_backend": "git_ssh"},
            },
        )

        self.assertEqual(recommendations["next_steps"][0]["title"], "把 ai-task-ops 纳入日常 transport 节奏")
        self.assertIn("backend=git_ssh", recommendations["next_steps"][0]["why"])
        self.assertEqual(recommendations["next_steps"][1]["title"], "把 shadow bootstrap 与正式三端治理边界写清楚")
        self.assertIn("同机共址", recommendations["next_steps"][1]["why"])
        self.assertIn("main-hub/satellite-01/satellite-02", recommendations["next_steps"][1]["why"])

    def test_build_recommendations_prefers_browser_mvp_loop_for_main_hub_plus_satellite_03(self) -> None:
        recommendations = self.ai_da_guan_jia.build_recommendations(
            task_ledger=[],
            skill_ledger=[],
            source_bundles={
                "main-hub": {"machine_profile": {"hostname": "BlackMac"}},
                "satellite-03": {"machine_profile": {"hostname": "OldMac"}},
            },
            summary={
                "expected_sources": ["main-hub", "satellite-03"],
                "missing_sources": [],
                "pending_satellite_aliases": ["white"],
                "browser_task_priority": ["feishu", "get_biji", "other_browser"],
                "transport": {"remote_reachable": True, "github_backend": "gh"},
            },
        )

        self.assertEqual(recommendations["next_steps"][1]["title"], "先跑一条主机-卫星浏览器真任务链")
        self.assertIn("main-hub | satellite-03", recommendations["next_steps"][1]["why"])
        self.assertIn("feishu -> get_biji -> other_browser", recommendations["next_steps"][1]["why"])
        self.assertEqual(recommendations["deferred_next_steps"][0]["title"], "按 Phase 2 纳管待定卫星")
        self.assertIn("white", recommendations["deferred_next_steps"][0]["why"])

    def test_resolve_expected_sources_prefers_persisted_hub_state_over_legacy_default(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            current_root = root / "current"
            current_root.mkdir(parents=True, exist_ok=True)
            (current_root / "source-status.json").write_text(
                '{"expected_sources": ["main-hub", "satellite-03"]}\n',
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"AI_DA_GUAN_JIA_EXPECTED_SOURCES": ""}, clear=False):
                with patch.object(self.ai_da_guan_jia, "HUB_CURRENT_ROOT", current_root):
                    with patch.object(self.ai_da_guan_jia, "HUB_ROOT", root):
                        self.assertEqual(
                            self.ai_da_guan_jia.resolve_expected_sources(),
                            ["main-hub", "satellite-03"],
                        )

    def test_sync_github_run_allows_local_preview_when_auth_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir)
            github_payload = run_dir / "github-payload.json"
            github_payload.write_text("{}", encoding="utf-8")
            github_task = {
                "skip_github_management": False,
                "github_repo": "moonstachain/ai-task-ops",
                "github_project_url": "",
                "classification": {"task_key": "TASK-001"},
            }
            captured: dict[str, object] = {}

            def capture_update(_run_dir: Path, _github_task: dict[str, object], payload: dict[str, object]) -> None:
                captured["payload"] = payload

            with patch.object(self.ai_da_guan_jia, "find_run_dir", return_value=run_dir):
                with patch.object(self.ai_da_guan_jia, "prepare_github_materials", return_value={"github_task": github_task}):
                    with patch.object(self.ai_da_guan_jia, "detect_github_backend", return_value={"backend": "", "reason": "missing auth"}):
                        with patch.object(self.ai_da_guan_jia, "update_github_files_after_sync", side_effect=capture_update):
                            returncode, status = self.ai_da_guan_jia.sync_github_run(
                                "adagj-test",
                                phase="intake",
                                apply=False,
                            )

        self.assertEqual(returncode, 0)
        self.assertEqual(status, "github_intake_preview_ready")
        payload = captured["payload"]
        self.assertEqual(payload["status"], "github_intake_preview_ready")
        self.assertTrue(payload["local_preview_only"])
        self.assertEqual(payload["reason"], "missing auth")


if __name__ == "__main__":
    unittest.main()
