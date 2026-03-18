from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path("/Users/liming/Documents/codex-ai-gua-jia-01")
SCRIPT_PATH = PROJECT_ROOT / "work" / "ai-da-guan-jia" / "scripts" / "window_duty_officer_bundle.py"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class WindowDutyOfficerBundleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module("test_window_duty_officer_bundle", SCRIPT_PATH)

    def test_build_bundle_picks_top_priority_and_top_frozen(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            summary_path = root / "summary.json"
            govern_path = root / "govern.json"
            contract_path = root / "contract.json"
            protocol_path = root / "protocol.md"
            output_dir = root / "run"

            summary_path.write_text(
                json.dumps(
                    {
                        "window_count": 3,
                        "windows": [
                            {
                                "window_id": "blocked-zero-proof",
                                "role": "黑色卫星支线",
                                "current_phase": "old blocker",
                                "current_status": "blocked",
                                "trusted_evidence_count": 0,
                                "trusted_evidence": [],
                                "current_heartbeat_path": "/tmp/blocked.json",
                                "updated_at": "2026-03-16T00:00:00+08:00",
                                "age_minutes": 80.0,
                            },
                            {
                                "window_id": "wait-window",
                                "role": "运营主线",
                                "current_phase": "waiting external",
                                "current_status": "waiting_external",
                                "trusted_evidence_count": 2,
                                "trusted_evidence": [{"path": "output/wait-proof.md"}],
                                "current_heartbeat_path": "/tmp/wait.json",
                                "updated_at": "2026-03-16T00:01:00+08:00",
                                "age_minutes": 15.0,
                            },
                            {
                                "window_id": "continue-window",
                                "role": "半自动远程控制面",
                                "current_phase": "ready",
                                "current_status": "waiting_review",
                                "trusted_evidence_count": 3,
                                "trusted_evidence": [{"path": "output/continue-proof.json"}],
                                "current_heartbeat_path": "/tmp/continue.json",
                                "updated_at": "2026-03-16T00:02:00+08:00",
                                "age_minutes": 5.0,
                            },
                        ],
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
                                "window_id": "blocked-zero-proof",
                                "decision": "裁决",
                                "observed_state": "stuck",
                                "reason": "窗口已自报 blocked/error/failed。",
                                "next_action": "裁决它",
                                "sole_blocker": "still blocked",
                                "human_boundary": False,
                                "auto_dispatch_allowed": True,
                            },
                            {
                                "window_id": "wait-window",
                                "decision": "等待",
                                "observed_state": "waiting_external",
                                "reason": "等待外部条件。",
                                "next_action": "继续等待",
                                "sole_blocker": "external wait",
                                "human_boundary": False,
                                "auto_dispatch_allowed": False,
                            },
                            {
                                "window_id": "continue-window",
                                "decision": "继续",
                                "observed_state": "waiting_external",
                                "reason": "外部等待已不明显。",
                                "next_action": "恢复执行",
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

            context = self.module.BundleContext(
                run_id="duty-officer-test",
                created_at="2026-03-16T00:10:00+08:00",
                output_dir=output_dir,
                summary_json=summary_path,
                governance_json=govern_path,
                contract_json=contract_path,
                protocol_md=protocol_path,
                trial_run_dir=None,
            )
            bundle = self.module.build_bundle(context)

        self.assertEqual(bundle["top_priority_window"]["window_id"], "blocked-zero-proof")
        self.assertEqual(bundle["top_frozen_window"]["window_id"], "wait-window")
        self.assertEqual(bundle["global_max_distortion"]["window_id"], "blocked-zero-proof")

    def test_write_bundle_creates_outputs_and_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            summary_path = root / "summary.json"
            govern_path = root / "govern.json"
            contract_path = root / "contract.json"
            protocol_path = root / "protocol.md"
            output_dir = root / "run"

            summary_path.write_text(
                json.dumps(
                    {
                        "window_count": 1,
                        "windows": [
                            {
                                "window_id": "ops",
                                "role": "运营主线",
                                "current_phase": "waiting",
                                "current_status": "waiting_external",
                                "trusted_evidence_count": 1,
                                "trusted_evidence": [{"path": "output/proof.md"}],
                                "current_heartbeat_path": "/tmp/ops.json",
                                "updated_at": "2026-03-16T00:00:00+08:00",
                                "age_minutes": 10.0,
                            }
                        ],
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
                                "window_id": "ops",
                                "decision": "等待",
                                "observed_state": "waiting_external",
                                "reason": "等待外部条件。",
                                "next_action": "继续等待",
                                "sole_blocker": "external wait",
                                "human_boundary": False,
                                "auto_dispatch_allowed": False,
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            contract_path.write_text('{"schema_version":"x"}\n', encoding="utf-8")
            protocol_path.write_text("# protocol\n", encoding="utf-8")

            context = self.module.BundleContext(
                run_id="duty-officer-write-test",
                created_at="2026-03-16T00:10:00+08:00",
                output_dir=output_dir,
                summary_json=summary_path,
                governance_json=govern_path,
                contract_json=contract_path,
                protocol_md=protocol_path,
                trial_run_dir=None,
            )
            result = self.module.write_bundle(context)

            self.assertTrue((output_dir / "duty-officer-bundle.json").exists())
            self.assertTrue((output_dir / "duty-officer-manifest.json").exists())
            self.assertTrue((output_dir / "support" / "quickstart.md").exists())
            self.assertTrue((output_dir / "verify" / "verification-report.json").exists())
            self.assertEqual(result["verification_report"]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
