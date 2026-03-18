from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path("/Users/liming/Documents/codex-ai-gua-jia-01")
SCRIPT_ROOT = PROJECT_ROOT / "work" / "ai-da-guan-jia" / "scripts"
SCRIPT_PATH = SCRIPT_ROOT / "ai_da_guan_jia.py"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class OvernightAutopilotTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPT_ROOT))
        cls.module = load_module("test_ai_da_guan_jia_overnight_autopilot", SCRIPT_PATH)

    def make_args(self, **overrides):
        base = {
            "task": "[$ai-da-guan-jia] 夜间自动驾驶推进知识整理和发布准备",
            "prompt": None,
            "executor_source_id": "satellite-03",
            "question_mode": "zero_interrupt",
            "blocked_policy": "park_and_continue",
            "publish_mode": "draft_only",
            "preauth_manifest": None,
            "sleep_policy": None,
            "resume_run_id": "",
            "run_id": "adagj-overnight",
            "created_at": "2026-03-14T23:40:00+08:00",
        }
        base.update(overrides)
        return types.SimpleNamespace(**base)

    def make_resume_args(self, **overrides):
        base = {
            "run_id": "adagj-resume",
            "preauth_manifest": None,
        }
        base.update(overrides)
        return types.SimpleNamespace(**base)

    def fake_route_builder(self, recommended_actions, *, task_text="夜间自动驾驶测试任务"):
        def _builder(
            *,
            run_id,
            created_at,
            run_dir,
            executor_source_id,
            question_mode,
            blocked_policy,
            publish_mode,
            resume_run_id="",
            **_,
        ):
            route_payload = {
                "run_id": run_id,
                "created_at": created_at,
                "task_text": task_text,
                "selected_skills": ["ai-da-guan-jia"],
                "skills_considered": ["ai-da-guan-jia", "jiyao-youyao-haiyao-zaiyao"],
                "recommended_actions": recommended_actions,
                "signals": {"browser": True},
                "verification_targets": ["route.json", "morning-brief.md"],
                "human_boundary": "Only interrupt for login, authorization, payment, or irreversible publish/delete.",
                "governance_signal_status": "missing",
                "credit_influenced_selection": False,
                "proposal_authority_summary": {},
                "autopilot_mode": {
                    "executor_source_id": executor_source_id,
                    "question_mode": question_mode,
                    "blocked_policy": blocked_policy,
                    "publish_mode": publish_mode,
                    "resume_run_id": resume_run_id,
                },
            }
            (run_dir / "route.json").write_text(
                json.dumps(route_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (run_dir / "situation-map.md").write_text("# Situation Map\n\n- zero interrupt\n", encoding="utf-8")
            (run_dir / "github-task.json").write_text(
                json.dumps({"run_id": run_id, "phase": "intake"}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            return route_payload

        return _builder

    def fake_feishu_sync(self, run_id, *, apply=False, **_):
        if apply:
            return 0, "apply_completed"
        return 0, "dry_run_preview_ready"

    def fake_github_sync(self, run_id, *, phase, apply=False):
        return 0, f"github_{phase}_{'apply' if apply else 'dry_run'}_ready"

    def fake_source_row(self, source_id: str):
        if source_id != "satellite-03":
            return {}
        return {"source_id": source_id, "status": "connected", "hostname": "satellite-03"}

    def fake_remote_info(self, source_id: str):
        if source_id != "satellite-03":
            return {}
        return {
            "source_id": source_id,
            "host": "192.168.31.83",
            "workspace_root": "/Users/liming/Documents/codex-ai-gua-jia-01",
            "verify": {"status": "verify_complete"},
        }

    def test_parser_registers_overnight_autopilot_and_resume_defaults(self) -> None:
        parser = self.module.build_parser()

        overnight = parser.parse_args(["overnight-autopilot", "--task", "night run"])
        self.assertEqual(overnight.func.__name__, "command_overnight_autopilot")
        self.assertEqual(overnight.executor_source_id, "satellite-03")
        self.assertEqual(overnight.question_mode, "zero_interrupt")
        self.assertEqual(overnight.blocked_policy, "park_and_continue")
        self.assertEqual(overnight.publish_mode, "draft_only")

        resume = parser.parse_args(["autopilot-resume", "--run-id", "adagj-run"])
        self.assertEqual(resume.func.__name__, "command_autopilot_resume")
        self.assertEqual(resume.run_id, "adagj-run")
        self.assertIsNone(resume.preauth_manifest)

    def test_overnight_autopilot_writes_closure_bundle_and_gates_publish_without_preauth(self) -> None:
        publish_command = (
            f"python3 {SCRIPT_PATH} tool-glue-zsxq-publish "
            "--feishu-url https://example.test/docx/1 "
            "--group-url https://wx.zsxq.com/group/15554854424522 "
            "--send-stages claudy --final-send"
        )
        recommended_actions = [
            {
                "action": "Publish CLAUDY article to Yuanli Planet",
                "cli_command": publish_command,
                "stage_name": "claudy",
                "inputs": {"stage": "claudy"},
            }
        ]
        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            args = self.make_args(run_id="adagj-overnight-gated")
            executed_argv: list[list[str]] = []

            def fake_execute(argv, *, timeout=900):
                executed_argv.append(list(argv))
                return {"returncode": 0, "stdout": "status: completed\n", "stderr": ""}

            with patch.multiple(
                self.module,
                RUNS_ROOT=runs_root,
            ):
                with patch.object(self.module, "tool_glue_connected_source_row", side_effect=self.fake_source_row):
                    with patch.object(self.module, "tool_glue_remote_host_metadata", side_effect=self.fake_remote_info):
                        with patch.object(
                            self.module,
                            "autopilot_build_route_bundle",
                            side_effect=self.fake_route_builder(recommended_actions),
                        ):
                            with patch.object(self.module, "autopilot_execute_child_command", side_effect=fake_execute):
                                with patch.object(self.module, "run_feishu_sync", side_effect=self.fake_feishu_sync):
                                    with patch.object(self.module, "sync_github_run", side_effect=self.fake_github_sync):
                                        with patch.object(self.module, "append_daily_soul_log", return_value=Path(tempdir) / "soul-log.md"):
                                            exit_code = self.module.command_overnight_autopilot(args)

            self.assertEqual(exit_code, 0)
            run_dir = runs_root / "2026-03-14" / "adagj-overnight-gated"
            for relative_path in [
                "approval-bundle.json",
                "autopilot-plan.json",
                "blocked-queue.json",
                "resume-actions.json",
                "route.json",
                "evolution.json",
                "worklog.json",
                "morning-brief.md",
                "node-ledger.json",
                "closure-sync.json",
                "feishu-payload.json",
                "github-payload.json",
                "gate-decisions.json",
            ]:
                self.assertTrue((run_dir / relative_path).exists(), relative_path)

            gate_payload = json.loads((run_dir / "gate-decisions.json").read_text(encoding="utf-8"))
            self.assertEqual(len(gate_payload["items"]), 1)
            self.assertTrue(gate_payload["items"][0]["gated"])
            self.assertEqual(gate_payload["items"][0]["reason"], "gated_to_draft")
            self.assertNotIn("--final-send", gate_payload["items"][0]["adjusted_argv"])
            self.assertEqual(len(executed_argv), 1)
            self.assertNotIn("--final-send", executed_argv[0])
            blocked_payload = json.loads((run_dir / "blocked-queue.json").read_text(encoding="utf-8"))
            self.assertEqual(blocked_payload["items"], [])
            brief = (run_dir / "morning-brief.md").read_text(encoding="utf-8")
            self.assertIn("Overall Status: `completed`", brief)

    def test_overnight_autopilot_parks_blocked_main_and_continues_side_lane(self) -> None:
        recommended_actions = [
            {
                "action": "Publish packet requires manual stage input",
                "cli_command": f"python3 {SCRIPT_PATH} tool-glue-zsxq-publish --feishu-url <fill>",
                "inputs": {"feishu_url": "<fill>"},
            },
            {
                "action": "Prepare closure mirror",
                "cli_command": f"python3 {SCRIPT_PATH} sync-github --phase closure --dry-run --run-id adagj-overnight-queue",
            },
        ]
        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            args = self.make_args(run_id="adagj-overnight-queue")

            def fake_execute(argv, *, timeout=900):
                return {"returncode": 0, "stdout": "status: completed\n", "stderr": ""}

            with patch.multiple(self.module, RUNS_ROOT=runs_root):
                with patch.object(self.module, "tool_glue_connected_source_row", side_effect=self.fake_source_row):
                    with patch.object(self.module, "tool_glue_remote_host_metadata", side_effect=self.fake_remote_info):
                        with patch.object(
                            self.module,
                            "autopilot_build_route_bundle",
                            side_effect=self.fake_route_builder(recommended_actions),
                        ):
                            with patch.object(self.module, "autopilot_execute_child_command", side_effect=fake_execute):
                                with patch.object(self.module, "run_feishu_sync", side_effect=self.fake_feishu_sync):
                                    with patch.object(self.module, "sync_github_run", side_effect=self.fake_github_sync):
                                        with patch.object(self.module, "append_daily_soul_log", return_value=Path(tempdir) / "soul-log.md"):
                                            exit_code = self.module.command_overnight_autopilot(args)

            self.assertEqual(exit_code, 0)
            run_dir = runs_root / "2026-03-14" / "adagj-overnight-queue"
            blocked_payload = json.loads((run_dir / "blocked-queue.json").read_text(encoding="utf-8"))
            resume_payload = json.loads((run_dir / "resume-actions.json").read_text(encoding="utf-8"))
            side_results = json.loads((run_dir / "side-action-results.json").read_text(encoding="utf-8"))
            main_results = json.loads((run_dir / "main-action-results.json").read_text(encoding="utf-8"))
            self.assertEqual(blocked_payload["items"][0]["status"], "blocked_needs_user")
            self.assertEqual(blocked_payload["items"][0]["blocking_reason"], "placeholder_input_required")
            self.assertEqual(len(resume_payload["items"]), 1)
            self.assertEqual(main_results["results"][0]["status"], "blocked_needs_user")
            self.assertEqual(side_results["results"][0]["status"], "completed")
            self.assertEqual(side_results["results"][0]["action"], "Prepare closure mirror")
            brief = (run_dir / "morning-brief.md").read_text(encoding="utf-8")
            self.assertIn("placeholder_input_required", brief)

    def test_overnight_autopilot_allows_final_send_when_scoped_preauthorized(self) -> None:
        publish_command = (
            f"python3 {SCRIPT_PATH} tool-glue-zsxq-publish "
            "--feishu-url https://example.test/docx/1 "
            "--group-url https://wx.zsxq.com/group/15554854424522 "
            "--send-stages claudy --final-send"
        )
        recommended_actions = [
            {
                "action": "Publish CLAUDY article to Yuanli Planet",
                "cli_command": publish_command,
                "stage_name": "claudy",
                "inputs": {"stage": "claudy"},
            }
        ]
        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            preauth_path = Path(tempdir) / "preauth.json"
            preauth_path.write_text(
                json.dumps(
                    {
                        "publish_grants": [
                            {
                                "command": "tool-glue-zsxq-publish",
                                "stage": "claudy",
                                "group_url": "https://wx.zsxq.com/group/15554854424522",
                                "allow": True,
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            args = self.make_args(
                run_id="adagj-overnight-preauth",
                publish_mode="send_if_preauthorized",
                preauth_manifest=str(preauth_path),
            )
            executed_argv: list[list[str]] = []

            def fake_execute(argv, *, timeout=900):
                executed_argv.append(list(argv))
                return {"returncode": 0, "stdout": "status: completed\n", "stderr": ""}

            with patch.multiple(self.module, RUNS_ROOT=runs_root):
                with patch.object(self.module, "tool_glue_connected_source_row", side_effect=self.fake_source_row):
                    with patch.object(self.module, "tool_glue_remote_host_metadata", side_effect=self.fake_remote_info):
                        with patch.object(
                            self.module,
                            "autopilot_build_route_bundle",
                            side_effect=self.fake_route_builder(recommended_actions),
                        ):
                            with patch.object(self.module, "autopilot_execute_child_command", side_effect=fake_execute):
                                with patch.object(self.module, "run_feishu_sync", side_effect=self.fake_feishu_sync):
                                    with patch.object(self.module, "sync_github_run", side_effect=self.fake_github_sync):
                                        with patch.object(self.module, "append_daily_soul_log", return_value=Path(tempdir) / "soul-log.md"):
                                            exit_code = self.module.command_overnight_autopilot(args)

            self.assertEqual(exit_code, 0)
            run_dir = runs_root / "2026-03-14" / "adagj-overnight-preauth"
            gate_payload = json.loads((run_dir / "gate-decisions.json").read_text(encoding="utf-8"))
            self.assertTrue(gate_payload["items"][0]["authorized"])
            self.assertFalse(gate_payload["items"][0]["gated"])
            self.assertIn("--final-send", gate_payload["items"][0]["adjusted_argv"])
            self.assertIn("--final-send", executed_argv[0])
            approval_bundle = json.loads((run_dir / "approval-bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(approval_bundle["publish_grant_count"], 1)

    def test_autopilot_resume_consumes_existing_queue_without_rerouting(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            run_dir = runs_root / "2026-03-14" / "adagj-resume"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "route.json").write_text(
                json.dumps(
                    {
                        "run_id": "adagj-resume",
                        "created_at": "2026-03-14T23:50:00+08:00",
                        "task_text": "恢复夜间自动驾驶执行",
                        "autopilot_mode": {
                            "executor_source_id": "satellite-03",
                            "publish_mode": "draft_only",
                            "blocked_policy": "park_and_continue",
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (run_dir / "preauth-manifest.json").write_text("{}\n", encoding="utf-8")
            (run_dir / "blocked-queue.json").write_text(
                json.dumps(
                    {"items": [{"action": "wait_login", "status": "blocked_needs_user", "blocking_reason": "login_expired"}]},
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (run_dir / "resume-actions.json").write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "action": "Resume GitHub closure mirror",
                                "cli_command": f"python3 {SCRIPT_PATH} sync-github --phase closure --dry-run --run-id adagj-resume",
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (run_dir / "node-ledger.json").write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "node_id": "node_1",
                                "node_index": 1,
                                "title": "睡前预授权包",
                                "status": "completed",
                                "summary": "seed",
                                "evidence_refs": [],
                                "blockers": [],
                                "updated_at": "2026-03-14T23:50:00+08:00",
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            def fake_execute(argv, *, timeout=900):
                return {"returncode": 0, "stdout": "status: completed\n", "stderr": ""}

            with patch.multiple(self.module, RUNS_ROOT=runs_root):
                with patch.object(self.module, "autopilot_execute_child_command", side_effect=fake_execute):
                    with patch.object(self.module, "run_feishu_sync", side_effect=self.fake_feishu_sync):
                        with patch.object(self.module, "sync_github_run", side_effect=self.fake_github_sync):
                            with patch.object(self.module, "append_daily_soul_log", return_value=Path(tempdir) / "soul-log.md"):
                                exit_code = self.module.command_autopilot_resume(self.make_resume_args())

            self.assertEqual(exit_code, 0)
            updated_resume = json.loads((run_dir / "resume-actions.json").read_text(encoding="utf-8"))
            self.assertEqual(updated_resume["items"], [])
            resume_results = json.loads((run_dir / "resume-action-results.json").read_text(encoding="utf-8"))
            self.assertEqual(resume_results["results"][0]["status"], "completed")
            node_ledger = json.loads((run_dir / "node-ledger.json").read_text(encoding="utf-8"))
            self.assertEqual(node_ledger["items"][-1]["title"], "续跑执行队列")
            self.assertTrue((run_dir / "morning-brief.md").exists())


if __name__ == "__main__":
    unittest.main()
