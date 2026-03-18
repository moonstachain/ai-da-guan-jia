from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path("/Users/liming/Documents/codex-ai-gua-jia-01")
SCRIPT_PATH = PROJECT_ROOT / "work" / "ai-da-guan-jia" / "scripts" / "black_satellite_mission_status_bundle.py"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class BlackSatelliteMissionStatusBundleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module("test_black_satellite_mission_status_bundle", SCRIPT_PATH)

    def test_build_bundle_captures_completion_and_external_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            summary_path = root / "summary.json"
            govern_path = root / "govern.json"
            contract_path = root / "contract.json"
            protocol_path = root / "protocol.md"
            split_protocol_path = root / "split.md"
            duty_bundle_path = root / "duty.json"
            cleanup_manifest_path = root / "cleanup.json"
            runtime_gap_path = root / "runtime-gap.json"
            heartbeat_path = root / "black-satellite-pmo-beta-test.json"

            heartbeat_path.write_text(
                json.dumps(
                    {
                        "window_id": "black-satellite-pmo-beta",
                        "role": "半自动远程控制面 + 窗口治理值班官 v1",
                        "current_phase": "formal_duty_active / runtime-gap-ready",
                        "last_action": "产出 runtime gap bundle",
                        "current_status": "waiting_external",
                        "latest_evidence_paths": ["run/runtime-gap.json"],
                        "sole_blocker": "waiting live evidence",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            summary_path.write_text(
                json.dumps(
                    {
                        "windows": [
                            {
                                "window_id": "black-satellite",
                                "role": "黑色卫星支线",
                                "display_state": "archived_history_line",
                                "accepted_cleanup_label": "archived_history_line",
                                "sole_blocker": "",
                            },
                            {
                                "window_id": "black-satellite-pmo-beta",
                                "role": "半自动远程控制面 + 窗口治理值班官 v1",
                                "display_state": "",
                                "accepted_cleanup_label": "",
                                "sole_blocker": "waiting live evidence",
                            },
                            {
                                "window_id": "operations-mainline",
                                "role": "运营主线",
                                "display_state": "",
                                "accepted_cleanup_label": "",
                                "sole_blocker": "wait external",
                            },
                            {
                                "window_id": "window-observability-heartbeat",
                                "role": "普通支线",
                                "display_state": "downgrade_to_history",
                                "accepted_cleanup_label": "downgrade_to_history",
                                "sole_blocker": "",
                            },
                        ]
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            govern_path.write_text(
                json.dumps(
                    {
                        "windows": [
                            {
                                "window_id": "black-satellite",
                                "recommended_action": "收口",
                                "observed_state": "suspected_silent_lost",
                                "governance_reason": "历史化",
                            },
                            {
                                "window_id": "black-satellite-pmo-beta",
                                "recommended_action": "继续",
                                "observed_state": "progressing",
                                "governance_reason": "继续当前子目标",
                            },
                            {
                                "window_id": "operations-mainline",
                                "recommended_action": "等待",
                                "observed_state": "waiting_external",
                                "governance_reason": "等待外部条件",
                            },
                            {
                                "window_id": "window-observability-heartbeat",
                                "recommended_action": "收口",
                                "observed_state": "suspected_silent_lost",
                                "governance_reason": "收口历史化",
                            },
                        ]
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            contract_path.write_text(
                json.dumps(
                    {
                        "role_boundary": {
                            "can_do": ["remote_execution"],
                            "cannot_do": ["miaoda_page_final_repair"],
                            "retained_by_main_hub": ["closure"],
                            "retained_by_human": ["login"],
                        },
                        "miaoda_split_rule": {
                            "black_satellite_should_do": ["repo_local_verify"],
                            "retained_by_human_execution_surface": ["republish_correct_version"],
                            "retained_by_operations_mainline": ["honest_final_reverify"],
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            protocol_path.write_text("# protocol\n", encoding="utf-8")
            split_protocol_path.write_text("# split\n", encoding="utf-8")
            duty_bundle_path.write_text(
                json.dumps(
                    {
                        "top_priority_window": {"window_id": "operations-mainline", "recommended_action": "等待"},
                        "top_frozen_window": {"window_id": "operations-mainline", "recommended_action": "等待"},
                        "global_max_distortion": {"window_id": "black-satellite", "summary": "legacy drift"},
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            cleanup_manifest_path.write_text(
                json.dumps(
                    {
                        "package_a": {"recommended_label": "archived_history_line"},
                        "package_b": {"recommended_action": "downgrade_to_history"},
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            runtime_gap_path.write_text(
                json.dumps(
                    {
                        "focus_card_ids": ["diagnosis-03", "action-04"],
                        "runtime_model_gaps": [
                            {"gap_id": "runtime_source_view_observability", "status": "open"},
                            {"gap_id": "display_field_alias_contract", "status": "open"},
                        ],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            context = self.module.MissionContext(
                run_id="mission-status-test",
                created_at="2026-03-16T12:00:00+08:00",
                output_dir=root / "run",
                summary_json=summary_path,
                governance_json=govern_path,
                contract_json=contract_path,
                protocol_md=protocol_path,
                split_protocol_md=split_protocol_path,
                duty_bundle_json=duty_bundle_path,
                cleanup_manifest_json=cleanup_manifest_path,
                runtime_gap_bundle_json=runtime_gap_path,
                heartbeat_json=heartbeat_path,
            )
            bundle = self.module.build_bundle(context)

        self.assertEqual(bundle["completion_assessment"]["black_satellite_owned_completion_percent"], 85)
        self.assertEqual(
            bundle["remaining_work"]["next_reverify_checks"][0]["check_id"],
            "selected_source_view_exact_match",
        )
        self.assertIn(
            "live source-view / binding evidence",
            bundle["remaining_work"]["current_biggest_unfinished"],
        )
        self.assertEqual(
            bundle["current_state"]["governance_windows"][1]["recommended_action"],
            "继续",
        )

    def test_write_bundle_creates_outputs_and_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            summary_path = root / "summary.json"
            govern_path = root / "govern.json"
            contract_path = root / "contract.json"
            protocol_path = root / "protocol.md"
            split_protocol_path = root / "split.md"
            duty_bundle_path = root / "duty.json"
            cleanup_manifest_path = root / "cleanup.json"
            runtime_gap_path = root / "runtime-gap.json"
            heartbeat_path = root / "black-satellite-pmo-beta-test.json"
            output_dir = root / "run"

            heartbeat_path.write_text(
                json.dumps(
                    {
                        "window_id": "black-satellite-pmo-beta",
                        "role": "半自动远程控制面 + 窗口治理值班官 v1",
                        "current_phase": "formal_duty_active / mission-ready",
                        "last_action": "产出 mission bundle",
                        "current_status": "waiting_external",
                        "latest_evidence_paths": ["run/mission.json"],
                        "sole_blocker": "",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            summary_path.write_text(
                json.dumps(
                    {
                        "windows": [
                            {"window_id": "black-satellite", "accepted_cleanup_label": "archived_history_line"},
                            {"window_id": "window-observability-heartbeat", "accepted_cleanup_label": "downgrade_to_history"},
                        ]
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            govern_path.write_text(
                json.dumps(
                    {
                        "windows": [
                            {"window_id": "black-satellite", "recommended_action": "收口", "observed_state": "suspected_silent_lost"},
                            {"window_id": "black-satellite-pmo-beta", "recommended_action": "继续", "observed_state": "progressing"},
                            {"window_id": "operations-mainline", "recommended_action": "等待", "observed_state": "waiting_external"},
                            {"window_id": "window-observability-heartbeat", "recommended_action": "收口", "observed_state": "suspected_silent_lost"},
                        ]
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            contract_path.write_text(
                json.dumps(
                    {
                        "role_boundary": {
                            "can_do": ["remote_execution"],
                            "cannot_do": ["miaoda_page_final_repair"],
                            "retained_by_main_hub": ["closure"],
                            "retained_by_human": ["login"],
                        },
                        "miaoda_split_rule": {
                            "black_satellite_should_do": ["repo_local_verify"],
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            protocol_path.write_text("# protocol\n", encoding="utf-8")
            split_protocol_path.write_text("# split\n", encoding="utf-8")
            duty_bundle_path.write_text(
                json.dumps(
                    {
                        "top_priority_window": {"window_id": "operations-mainline"},
                        "top_frozen_window": {"window_id": "operations-mainline"},
                        "global_max_distortion": {"window_id": "black-satellite"},
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            cleanup_manifest_path.write_text(
                json.dumps(
                    {
                        "package_a": {"recommended_label": "archived_history_line"},
                        "package_b": {"recommended_action": "downgrade_to_history"},
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            runtime_gap_path.write_text(
                json.dumps(
                    {
                        "focus_card_ids": ["diagnosis-03", "action-04"],
                        "runtime_model_gaps": [
                            {"gap_id": "runtime_source_view_observability", "status": "open"},
                            {"gap_id": "display_field_alias_contract", "status": "open"},
                        ],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            context = self.module.MissionContext(
                run_id="mission-status-write-test",
                created_at="2026-03-16T12:00:00+08:00",
                output_dir=output_dir,
                summary_json=summary_path,
                governance_json=govern_path,
                contract_json=contract_path,
                protocol_md=protocol_path,
                split_protocol_md=split_protocol_path,
                duty_bundle_json=duty_bundle_path,
                cleanup_manifest_json=cleanup_manifest_path,
                runtime_gap_bundle_json=runtime_gap_path,
                heartbeat_json=heartbeat_path,
            )
            result = self.module.write_bundle(context)

            self.assertTrue((output_dir / "black-satellite-mission-status-bundle.json").exists())
            self.assertTrue((output_dir / "black-satellite-mission-status-bundle.md").exists())
            self.assertTrue((output_dir / "support" / "quickstart.md").exists())
            self.assertTrue((output_dir / "verify" / "verification-report.json").exists())
            self.assertEqual(result["verification"]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
