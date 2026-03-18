from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "work" / "ai-da-guan-jia" / "scripts" / "internal_collaboration_playbook.sh"


class InternalCollaborationPlaybookScriptTest(unittest.TestCase):
    def test_script_parses_with_bash_n(self) -> None:
        completed = subprocess.run(
            ["bash", "-n", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_phase_map_prints_full_lifecycle(self) -> None:
        completed = subprocess.run(
            ["bash", str(SCRIPT_PATH), "phase-map"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Phase 0", completed.stdout)
        self.assertIn("Phase 4", completed.stdout)
        self.assertIn("半自治操盘", completed.stdout)
        self.assertIn("shared_core", completed.stdout)

    def test_status_infers_phase_three_from_capability_proposals(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            clone_root = Path(tempdir)
            self._write_json(
                clone_root / "clone-registry.json",
                [
                    {
                        "clone_id": "ops-mvp-001",
                        "display_name": "中台管理试点同事",
                        "actor_type": "employee",
                        "role_template_id": "ops-management",
                        "portfolio_scope": "internal",
                    }
                ],
            )
            self._write_json(
                clone_root / "clone-scorecard.json",
                [
                    {
                        "clone_id": "ops-mvp-001",
                        "training_runs": 6,
                        "routing_priority": 71.5,
                        "autonomy_cap": "guarded",
                        "promotion_recommendation": "watch",
                    }
                ],
            )
            self._write_json(
                clone_root / "task-runs.json",
                [
                    {"clone_id": "ops-mvp-001", "task_run_key": "run-1"},
                    {"clone_id": "ops-mvp-001", "task_run_key": "run-2"},
                ],
            )
            self._write_json(
                clone_root / "training-cycles.json",
                [
                    {"clone_id": "ops-mvp-001", "training_cycle_key": "cycle-1"},
                ],
            )
            self._write_json(
                clone_root / "capability-proposals.json",
                [
                    {
                        "clone_id": "ops-mvp-001",
                        "proposal_title": "Promote ops escalation checklist",
                    }
                ],
            )
            self._write_json(
                clone_root / "alerts-decisions.json",
                [
                    {
                        "clone_id": "ops-mvp-001",
                        "status": "open",
                        "approval_required": True,
                        "title": "审批链仍需 founder 拍板",
                    }
                ],
            )
            self._write_json(
                clone_root / "portfolio-daily-report.json",
                {
                    "portfolio": "internal",
                    "sections": {
                        "当前最大失真与主要风险": [
                            {
                                "clone_id": "ops-mvp-001",
                                "summary": "中台管理试点同事 :: 审批提醒可能被误判成已收口",
                            }
                        ],
                        "明日训练建议": [
                            {
                                "clone_id": "ops-mvp-001",
                                "summary": "中台管理试点同事 :: continue one focused training cycle on 日常推进闭环",
                            }
                        ],
                        "候选晋升 / 降权 / 休眠": [
                            {
                                "clone_id": "ops-mvp-001",
                                "summary": "中台管理试点同事 :: watch :: priority=71.5 :: status=pending_approval",
                            }
                        ],
                    },
                },
            )

            env = dict(os.environ)
            env["AI_DA_GUAN_JIA_CLONE_CURRENT_ROOT"] = str(clone_root)
            completed = subprocess.run(
                ["bash", str(SCRIPT_PATH), "status", "ops-mvp-001"],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("current_phase: Phase 3", completed.stdout)
        self.assertIn("clone_id: ops-mvp-001", completed.stdout)
        self.assertIn("capability_proposal_count: 1", completed.stdout)
        self.assertIn("approval_required_alert_count: 1", completed.stdout)
        self.assertIn("latest_proposal: Promote ops escalation checklist", completed.stdout)

    @staticmethod
    def _write_json(path: Path, payload: object) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
