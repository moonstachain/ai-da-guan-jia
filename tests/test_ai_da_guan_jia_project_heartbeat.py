from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime
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


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class ProjectHeartbeatTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPT_ROOT))
        cls.module = load_module("test_ai_da_guan_jia_project_heartbeat", SCRIPT_ROOT / "ai_da_guan_jia.py")

    def patch_paths(self, root: Path):
        artifacts_root = root / "artifacts"
        strategy_root = artifacts_root / "strategy"
        strategy_current = strategy_root / "current"
        heartbeat_root = artifacts_root / "heartbeat"
        frontdesk_state_root = root / "derived" / "feishu" / "frontdesk-state"
        return patch.multiple(
            self.module,
            PROJECT_ROOT=root,
            CODEX_HOME=root / ".codex",
            ARTIFACTS_ROOT=artifacts_root,
            RUNS_ROOT=artifacts_root / "runs",
            STRATEGY_ROOT=strategy_root,
            STRATEGY_CURRENT_ROOT=strategy_current,
            PROPOSAL_QUEUE_PATH=strategy_current / "proposal-queue.json",
            PROJECT_HEARTBEAT_ROOT=heartbeat_root,
            PROJECT_HEARTBEAT_CURRENT_ROOT=heartbeat_root / "current",
            PROJECT_HEARTBEAT_ROUNDS_ROOT=heartbeat_root / "rounds",
            REPO_AUTOMATIONS_ROOT=root / "automations",
            FRONTDESK_STATE_ROOT=frontdesk_state_root,
            FRONTDESK_SESSIONS_PATH=frontdesk_state_root / "sessions.json",
            PROJECT_HEARTBEAT_NOTIFY_CHAT_ID="",
        )

    @staticmethod
    def heartbeat_args(**overrides):
        payload = {
            "project_id": "",
            "notify_feishu": False,
            "force_notify_feishu": False,
            "active_hours": "08:00-23:00",
            "quiet_hours": "00:00-08:00",
            "source": "manual",
        }
        payload.update(overrides)
        return argparse.Namespace(**payload)

    def write_strategy_minimum(self, root: Path) -> None:
        write_json(root / "artifacts" / "strategy" / "current" / "canonical-thread-registry.json", [])
        write_json(root / "artifacts" / "strategy" / "current" / "active-threads.json", [])

    def write_canonical_minimum(self, root: Path, *, tasks=None, threads=None, relations=None) -> None:
        write_json(root / "canonical" / "entities" / "tasks.json", tasks or [])
        write_json(root / "canonical" / "entities" / "threads.json", threads or [])
        write_json(root / "canonical" / "relations" / "relations.json", relations or [])

    def test_project_heartbeat_writes_silent_round_when_no_active_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            self.write_canonical_minimum(root)
            self.write_strategy_minimum(root)

            with self.patch_paths(root):
                with patch.object(self.module, "now_local", return_value=datetime.fromisoformat("2026-03-14T09:00:00+08:00")):
                    result = self.module.command_project_heartbeat(self.heartbeat_args())

            self.assertEqual(result, 0)
            latest_round = json.loads((root / "artifacts" / "heartbeat" / "current" / "latest-round.json").read_text(encoding="utf-8"))
            action_queue = json.loads((root / "artifacts" / "heartbeat" / "current" / "action-queue.json").read_text(encoding="utf-8"))
            self.assertEqual(latest_round["status"], "silent")
            self.assertEqual(latest_round["project_count"], 0)
            self.assertFalse(latest_round["should_notify"])
            self.assertEqual(action_queue["actions"], [])

    def test_project_heartbeat_turns_frontdesk_capture_into_intake_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            self.write_canonical_minimum(root)
            self.write_strategy_minimum(root)
            run_dir = root / "artifacts" / "runs" / "2026-03-14" / "adagj-note-capture"
            write_json(
                run_dir / "route.json",
                {
                    "run_id": "adagj-note-capture",
                    "created_at": "2026-03-14T08:55:00+08:00",
                    "task_text": "明天要确认 Minutes 凭证",
                    "note_capture": True,
                },
            )
            write_json(
                run_dir / "frontdesk-captures" / "frontdesk-capture-001.json",
                {
                    "capture_id": "frontdesk-capture-001",
                    "run_id": "adagj-note-capture",
                    "created_at": "2026-03-14T08:55:00+08:00",
                    "content": "明天要确认 Minutes 凭证",
                    "sync_status": "canonical_local_only",
                },
            )

            with self.patch_paths(root):
                with patch.object(self.module, "now_local", return_value=datetime.fromisoformat("2026-03-14T09:00:00+08:00")):
                    result = self.module.command_project_heartbeat(self.heartbeat_args())

            self.assertEqual(result, 0)
            registry = json.loads((root / "artifacts" / "heartbeat" / "current" / "project-registry.json").read_text(encoding="utf-8"))
            action_queue = json.loads((root / "artifacts" / "heartbeat" / "current" / "action-queue.json").read_text(encoding="utf-8"))
            self.assertEqual(registry["projects"][0]["kind"], "capture_proposal")
            self.assertEqual(action_queue["actions"][0]["kind"], "intake_proposal")

    def test_project_heartbeat_marks_stall_after_three_unchanged_rounds(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            self.write_canonical_minimum(
                root,
                tasks=[
                    {
                        "task_id": "task-stall",
                        "thread_id": "thread-stall",
                        "title": "transport 边界恢复",
                        "status": "active",
                        "priority": "P1",
                        "verification_state": "unknown",
                        "next_action": "继续确认 gh / GitHub auth",
                        "updated_at": "2026-03-14T01:00:00+08:00",
                    }
                ],
                threads=[
                    {
                        "thread_id": "thread-stall",
                        "title": "原力OS-信息聚合主线",
                        "updated_at": "2026-03-14T01:00:00+08:00",
                    }
                ],
            )
            self.write_strategy_minimum(root)

            with self.patch_paths(root):
                for hour in ["2026-03-14T09:00:00+08:00", "2026-03-14T10:00:00+08:00", "2026-03-14T11:00:00+08:00"]:
                    with patch.object(self.module, "now_local", return_value=datetime.fromisoformat(hour)):
                        result = self.module.command_project_heartbeat(self.heartbeat_args())
                        self.assertEqual(result, 0)

            scorecard = json.loads((root / "artifacts" / "heartbeat" / "current" / "scorecard.json").read_text(encoding="utf-8"))
            row = scorecard["rows"][0]
            self.assertEqual(row["project_id"], "task-stall")
            self.assertEqual(row["unchanged_rounds"], 3)
            self.assertTrue(row["stall_risk"])
            self.assertGreaterEqual(row["stall_risk_score"], 80.0)

    def test_project_heartbeat_escalates_blocked_system_and_forces_notify_even_in_quiet_hours(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            self.write_canonical_minimum(
                root,
                tasks=[
                    {
                        "task_id": "task-blocked-system",
                        "thread_id": "thread-blocked-system",
                        "title": "恢复 GitHub transport",
                        "status": "blocked_system",
                        "priority": "P1",
                        "verification_state": "unknown",
                        "blocker_reason": "GitHub auth 丢失，当前无法继续。",
                        "updated_at": "2026-03-14T01:00:00+08:00",
                    }
                ],
                threads=[
                    {
                        "thread_id": "thread-blocked-system",
                        "title": "原力OS-信息聚合主线",
                        "updated_at": "2026-03-14T01:00:00+08:00",
                    }
                ],
            )
            self.write_strategy_minimum(root)

            with self.patch_paths(root):
                with patch.object(self.module, "now_local", return_value=datetime.fromisoformat("2026-03-14T02:00:00+08:00")):
                    result = self.module.command_project_heartbeat(
                        self.heartbeat_args(active_hours="", quiet_hours="00:00-08:00")
                    )

            self.assertEqual(result, 0)
            latest_round = json.loads((root / "artifacts" / "heartbeat" / "current" / "latest-round.json").read_text(encoding="utf-8"))
            boundary_queue = json.loads((root / "artifacts" / "heartbeat" / "current" / "human-boundary-queue.json").read_text(encoding="utf-8"))
            self.assertTrue(latest_round["should_notify"])
            self.assertEqual(latest_round["notify_reason"], "new_blocked_system")
            self.assertEqual(latest_round["notify_status"], "queued_local_only")
            self.assertEqual(boundary_queue["items"][0]["status"], "blocked_system")

    def test_project_heartbeat_force_notify_bypasses_noise_guard_for_manual_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            self.write_canonical_minimum(
                root,
                tasks=[
                    {
                        "task_id": "task-monitor",
                        "thread_id": "thread-monitor",
                        "title": "Minutes 凭证推进",
                        "status": "active",
                        "priority": "P1",
                        "verification_state": "needs_follow_up",
                        "next_action": "继续观察是否需要补凭证",
                        "updated_at": "2026-03-14T03:50:00+08:00",
                    }
                ],
                threads=[
                    {
                        "thread_id": "thread-monitor",
                        "title": "Minutes 主线",
                        "updated_at": "2026-03-14T03:50:00+08:00",
                    }
                ],
            )
            self.write_strategy_minimum(root)

            with self.patch_paths(root), patch.object(self.module, "PROJECT_HEARTBEAT_NOTIFY_CHAT_ID", "oc_live"), patch.object(
                self.module,
                "send_project_heartbeat_to_feishu_chat",
                return_value={"status": "sent_text", "message_id": "om_live"},
            ) as mock_send:
                with patch.object(self.module, "now_local", return_value=datetime.fromisoformat("2026-03-14T04:10:00+08:00")):
                    result = self.module.command_project_heartbeat(
                        self.heartbeat_args(
                            notify_feishu=True,
                            force_notify_feishu=True,
                            active_hours="00:00-24:00",
                            quiet_hours="08:00-08:01",
                        )
                    )

            self.assertEqual(result, 0)
            latest_round = json.loads((root / "artifacts" / "heartbeat" / "current" / "latest-round.json").read_text(encoding="utf-8"))
            self.assertTrue(latest_round["should_notify"])
            self.assertEqual(latest_round["notify_reason"], "manual_override")
            self.assertEqual(latest_round["notify_status"], "sent_text")
            self.assertEqual(latest_round["notify_chat_id"], "oc_live")
            self.assertEqual(latest_round["delivery_result"]["message_id"], "om_live")
            mock_send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
