from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path("/Users/liming/Documents/codex-ai-gua-jia-01")
SCRIPT_PATH = PROJECT_ROOT / "work" / "ai-da-guan-jia" / "scripts" / "window_governance_cleanup_bundle.py"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class WindowGovernanceCleanupBundleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module("test_window_governance_cleanup_bundle", SCRIPT_PATH)

    def test_classifiers_match_expected_cleanup_decisions(self) -> None:
        legacy_row = {
            "recommended_action": "裁决",
            "trusted_evidence_count": 0,
            "sole_blocker": "still blocked",
        }
        legacy_history_row = {
            "recommended_action": "收口",
            "observed_state": "suspected_silent_lost",
            "trusted_evidence_count": 0,
        }
        successor_row = {
            "recommended_action": "继续",
            "trusted_evidence_count": 5,
        }
        observability_row = {
            "recommended_action": "收口",
            "observed_state": "suspected_silent_lost",
            "age_minutes": 150.0,
        }

        self.assertEqual(
            self.module.legacy_classification(legacy_row, successor_row),
            "superseded_by_black_satellite_pmo_beta",
        )
        self.assertEqual(
            self.module.legacy_classification(legacy_history_row, successor_row),
            "archived_history_line",
        )
        self.assertEqual(
            self.module.observability_recommendation(observability_row),
            "downgrade_to_history",
        )

    def test_write_outputs_creates_both_cleanup_packages(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            summary_path = root / "summary.json"
            govern_path = root / "govern.json"
            contract_path = root / "contract.json"
            protocol_path = root / "protocol.md"
            duty_bundle_path = root / "duty-bundle.json"
            output_dir = root / "run"

            summary_path.write_text(
                json.dumps(
                    {
                        "windows": [
                            {
                                "window_id": "black-satellite",
                                "role": "黑色卫星支线",
                                "current_phase": "old",
                                "last_action": "legacy",
                                "current_status": "blocked",
                                "sole_blocker": "preview blocked",
                                "observed_state": "stuck",
                                "trusted_evidence_count": 0,
                                "trusted_evidence": [],
                                "evidence_state": [{"path": "/private/tmp/legacy.png"}],
                                "updated_at": "2026-03-16T00:00:00+08:00",
                                "age_minutes": 100.0,
                                "current_heartbeat_path": "/tmp/legacy.json",
                            },
                            {
                                "window_id": "black-satellite-pmo-beta",
                                "role": "半自动远程控制面 + 窗口治理值班官 v1",
                                "current_phase": "formal",
                                "last_action": "duty",
                                "current_status": "running",
                                "sole_blocker": "",
                                "observed_state": "progressing",
                                "trusted_evidence_count": 5,
                                "trusted_evidence": [{"path": "work/output/bundle.json"}],
                                "evidence_state": [{"path": "work/output/bundle.json"}],
                                "updated_at": "2026-03-16T00:01:00+08:00",
                                "age_minutes": 1.0,
                                "current_heartbeat_path": "/tmp/pmo.json",
                            },
                            {
                                "window_id": "window-observability-heartbeat",
                                "role": "普通支线",
                                "current_phase": "protocol",
                                "last_action": "done",
                                "current_status": "running",
                                "sole_blocker": "",
                                "observed_state": "suspected_silent_lost",
                                "trusted_evidence_count": 1,
                                "trusted_evidence": [{"path": "docs/protocol.md"}],
                                "evidence_state": [{"path": "docs/protocol.md"}],
                                "updated_at": "2026-03-15T22:07:06+08:00",
                                "age_minutes": 140.0,
                                "current_heartbeat_path": "/tmp/obs.json",
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
                        "decisions": [
                            {
                                "window_id": "black-satellite",
                                "decision": "裁决",
                                "observed_state": "stuck",
                                "reason": "blocked",
                                "next_action": "rule",
                                "sole_blocker": "preview blocked",
                                "human_boundary": False,
                                "auto_dispatch_allowed": True,
                            },
                            {
                                "window_id": "black-satellite-pmo-beta",
                                "decision": "继续",
                                "observed_state": "progressing",
                                "reason": "fresh",
                                "next_action": "continue",
                                "sole_blocker": "",
                                "human_boundary": False,
                                "auto_dispatch_allowed": True,
                            },
                            {
                                "window_id": "window-observability-heartbeat",
                                "decision": "收口",
                                "observed_state": "suspected_silent_lost",
                                "reason": "silent lost",
                                "next_action": "close",
                                "sole_blocker": "",
                                "human_boundary": False,
                                "auto_dispatch_allowed": True,
                            },
                        ]
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            contract_path.write_text('{"schema_version":"x"}\n', encoding="utf-8")
            protocol_path.write_text("# protocol\n", encoding="utf-8")
            duty_bundle_path.write_text('{"schema_version":"bundle"}\n', encoding="utf-8")

            original_current_root = self.module.HEARTBEAT_CURRENT_ROOT
            fake_current_root = root / "current-heartbeats"
            fake_current_root.mkdir()
            (fake_current_root / "legacy.json").write_text(
                json.dumps({"window_id": "black-satellite"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (fake_current_root / "pmo.json").write_text(
                json.dumps({"window_id": "black-satellite-pmo-beta"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (fake_current_root / "obs.json").write_text(
                json.dumps({"window_id": "window-observability-heartbeat"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            self.module.HEARTBEAT_CURRENT_ROOT = fake_current_root
            try:
                context = self.module.CleanupContext(
                    run_id="cleanup-test",
                    created_at="2026-03-16T00:10:00+08:00",
                    output_dir=output_dir,
                    summary_json=summary_path,
                    governance_json=govern_path,
                    contract_json=contract_path,
                    protocol_md=protocol_path,
                    duty_bundle_json=duty_bundle_path,
                )
                result = self.module.write_outputs(context)
            finally:
                self.module.HEARTBEAT_CURRENT_ROOT = original_current_root

            self.assertTrue((output_dir / "task-a-legacy-black-satellite" / "legacy-black-satellite-judgement.json").exists())
            self.assertTrue((output_dir / "task-b-window-observability-heartbeat" / "window-observability-cleanup.json").exists())
            self.assertEqual(result["legacy_package"]["recommended_label"], "superseded_by_black_satellite_pmo_beta")
            self.assertEqual(result["observability_package"]["recommended_action"], "downgrade_to_history")
            self.assertEqual(result["legacy_verify"]["status"], "completed")
            self.assertEqual(result["observability_verify"]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
