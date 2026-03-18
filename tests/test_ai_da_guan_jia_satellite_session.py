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


class SatelliteSessionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPT_ROOT))
        cls.module = load_module("test_ai_da_guan_jia_satellite_session", SCRIPT_PATH)

    def make_args(self, **overrides):
        base = {
            "task": "Use black satellite to push the current project mainline forward.",
            "resume_session": "",
            "alias": "黑色",
            "run_mode": "visible",
            "lane_count": 3,
            "selected_lanes": "",
            "lane_launch_mode": "parallel",
            "main_command": "",
            "support_command": "",
            "verify_command": "",
            "lane_timeout": 300,
            "run_id": "adagj-satellite-session",
            "created_at": "2026-03-15T10:00:00+08:00",
        }
        base.update(overrides)
        return types.SimpleNamespace(**base)

    def make_lane_args(self, **overrides):
        base = {
            "session_run_id": "adagj-satellite-session",
            "lane": "verify",
            "task": "Run the remote verify lane for the current project.",
            "run_mode": "visible",
            "lane_command": "python3 scripts/yuanli_governance.py validate",
            "lane_timeout": 120,
            "run_id": "adagj-satellite-session-verify",
            "created_at": "2026-03-15T10:00:00+08:00",
        }
        base.update(overrides)
        return types.SimpleNamespace(**base)

    def fake_resolution(self, alias: str):
        self.assertEqual(alias, "黑色")
        return {
            "requested_alias": alias,
            "resolved_satellite_id": "satellite-black",
            "resolved_clone_id": "clone-satellite-black",
            "resolved_source_id": "satellite-02",
            "dispatch_mode": "remote_ssh_exec",
            "status": "connected",
        }

    def fake_source_row(self, source_id: str):
        if source_id != "satellite-02":
            return {}
        return {
            "source_id": source_id,
            "status": "connected",
            "hostname": "satellite-02",
        }

    def fake_remote_info(self, source_id: str):
        if source_id != "satellite-02":
            return {}
        return {
            "source_id": source_id,
            "host": "192.168.31.86",
            "user": "hay2045",
            "workspace_root": "/Users/hay2045/Documents/codex-ai-gua-jia-01",
            "artifact_dir": "/tmp/satellite-02",
            "probe": {"status": "ready", "client_mode": "vscode-agent"},
            "inventory": {"status": "completed"},
            "verify": {"status": "verify_complete"},
        }

    def sample_export_payload(self, lane: str) -> dict[str, object]:
        files = []
        for name, payload in [
            ("route.json", {"run_kind": "satellite_session_lane", "lane": lane}),
            ("lane-manifest.json", {"lane": lane}),
            ("lane-result.json", {"lane": lane, "status": "completed"}),
            ("lane-summary.md", f"# {lane}\n"),
            ("command-result.json", {"lane": lane, "returncode": 0}),
            ("codex-exec-result.json", {"lane": lane, "returncode": 0}),
            ("worklog.json", {"lane": lane, "status": "completed"}),
            ("worklog.md", f"# {lane} worklog\n"),
        ]:
            content = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
            files.append({"relative_path": name, "content": content})
        return {
            "status": "completed",
            "files": files,
            "missing_files": [],
        }

    def test_parser_registers_satellite_session_and_hidden_lane(self) -> None:
        parser = self.module.build_parser()

        parsed = parser.parse_args(["satellite-session", "--task", "push closure"])
        self.assertEqual(parsed.func.__name__, "command_satellite_session")
        self.assertEqual(parsed.alias, "黑色")
        self.assertEqual(parsed.run_mode, "visible")
        self.assertEqual(parsed.lane_count, 3)
        self.assertEqual(parsed.lane_launch_mode, "parallel")

        resumed = parser.parse_args(["satellite-session", "--resume-session", "adagj-sat"])
        self.assertEqual(resumed.func.__name__, "command_satellite_session")
        self.assertEqual(resumed.resume_session, "adagj-sat")

        hidden = parser.parse_args(
            [
                "satellite-session-lane",
                "--session-run-id",
                "adagj-sat",
                "--lane",
                "verify",
                "--task",
                "verify",
            ]
        )
        self.assertEqual(hidden.func.__name__, "command_satellite_session_lane")
        self.assertEqual(hidden.lane, "verify")

    def test_tool_glue_remote_host_metadata_prefers_probe_user_and_remaps_workspace_root(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            remote_hosts_root = Path(tempdir) / "remote-hosts"
            host_dir = remote_hosts_root / "satellite-02"
            host_dir.mkdir(parents=True, exist_ok=True)
            (host_dir / "onboarding-result.json").write_text(
                json.dumps(
                    {
                        "source_id": "satellite-02",
                        "host": "192.168.31.86",
                        "user": "hay2045",
                        "workspace_root": "/Users/hay2045/Documents/codex-ai-gua-jia-01",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (host_dir / "probe.json").write_text(
                json.dumps(
                    {
                        "status": "ready",
                        "host": "192.168.31.86",
                        "user": "liming",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (host_dir / "verify.json").write_text(
                json.dumps(
                    {
                        "status": "verify_complete",
                        "host": "192.168.31.86",
                        "user": "hay2045",
                        "workspace_root": "/Users/hay2045/Documents/codex-ai-gua-jia-01",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            with patch.multiple(
                self.module,
                REMOTE_HOSTS_V2_ROOT=remote_hosts_root,
                REMOTE_HOSTS_ROOT=Path(tempdir) / "legacy-remote-hosts",
            ):
                payload = self.module.tool_glue_remote_host_metadata("satellite-02")

        self.assertEqual(payload["user"], "liming")
        self.assertEqual(payload["resolved_user_source"], "probe")
        self.assertEqual(payload["original_user"], "hay2045")
        self.assertEqual(
            payload["workspace_root"],
            "/Users/liming/Documents/codex-ai-gua-jia-01",
        )
        self.assertEqual(
            payload["original_workspace_root"],
            "/Users/hay2045/Documents/codex-ai-gua-jia-01",
        )
        self.assertEqual(payload["user_source_mismatch"]["resolved_user"], "liming")

    def test_satellite_session_codex_exec_uses_isolated_worker_codex_home(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            fake_codex_home = Path(tempdir) / ".codex"
            fake_codex_home.mkdir(parents=True, exist_ok=True)
            (fake_codex_home / "auth.json").write_text(
                json.dumps(
                    {
                        "auth_mode": "apikey",
                        "OPENAI_API_KEY": "sk-or-v1-test-key",
                        "tokens": {"access_token": "a", "refresh_token": "b"},
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            captured = {}

            def fake_run(command, **kwargs):
                captured["command"] = command
                captured["env"] = kwargs.get("env", {})
                output_path = Path(command[command.index("--output-last-message") + 1])
                output_path.write_text(
                    json.dumps(
                        {
                            "status": "completed",
                            "did_what": "Used isolated worker home.",
                            "evidence_ref": [],
                            "blocking_reason": "",
                            "next_action": "",
                            "changed_files": [],
                            "commands_run": [],
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

                class Completed:
                    returncode = 0
                    stdout = ""
                    stderr = ""

                return Completed()

            with patch.dict("os.environ", {"CODEX_HOME": str(fake_codex_home)}, clear=False):
                with patch.object(self.module, "tool_glue_resolve_codex_bin", return_value=Path("/Applications/Codex.app/Contents/MacOS/codex")):
                    with patch.object(self.module.subprocess, "run", side_effect=fake_run):
                        payload = self.module.satellite_session_run_codex_exec_json(
                            "reply with ok",
                            self.module.satellite_session_codex_schema(),
                            cwd=PROJECT_ROOT,
                            timeout=30,
                        )

        self.assertEqual(payload["returncode"], 0)
        self.assertEqual(payload["json"]["status"], "completed")
        self.assertEqual(payload["default_codex_home"], str(fake_codex_home.resolve()))
        self.assertEqual(payload["copied_codex_home_files"], ["auth.json"])
        self.assertEqual(payload["auth_sanitization"]["applied"], True)
        self.assertEqual(payload["auth_sanitization"]["new_auth_mode"], "chatgpt")
        self.assertEqual(payload["auth_sanitization"]["removed_openai_api_key"], True)
        self.assertNotEqual(captured["env"]["CODEX_HOME"], str(fake_codex_home.resolve()))
        self.assertTrue(captured["env"]["CODEX_HOME"].endswith("codex-home"))

    def test_satellite_session_prepare_codex_home_reuses_local_profile_for_gui_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            fake_codex_home = Path(tempdir) / ".codex"
            fake_codex_home.mkdir(parents=True, exist_ok=True)
            worker_codex_home = Path(tempdir) / "worker-home"

            payload = self.module.satellite_session_prepare_codex_home(
                execution_surface="gui_terminal",
                default_codex_home=fake_codex_home,
                worker_codex_home=worker_codex_home,
            )

        self.assertEqual(payload["effective_codex_home"], str(fake_codex_home.resolve()))
        self.assertEqual(payload["copied_codex_home_files"], [])
        self.assertEqual(payload["auth_sanitization"]["applied"], False)
        self.assertEqual(payload["auth_sanitization"]["reason"], "reuse_local_gui_profile")

    def test_satellite_session_gui_terminal_accepts_valid_json_without_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            fake_codex_home = Path(tempdir) / ".codex"
            fake_codex_home.mkdir(parents=True, exist_ok=True)

            def fake_run(command, **kwargs):
                run_script_path = Path(json.loads(command[2].split(" to do script ", 1)[1]))
                output_path = run_script_path.parent / "result.json"
                output_path.write_text(
                    json.dumps(
                        {
                            "status": "completed",
                            "did_what": "Probe completed.",
                            "evidence_ref": ["."],
                            "blocking_reason": "",
                            "next_action": "ready",
                            "changed_files": [],
                            "commands_run": ["pwd"],
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

                class Completed:
                    returncode = 0
                    stdout = ""
                    stderr = ""

                return Completed()

            with patch.dict("os.environ", {"CODEX_HOME": str(fake_codex_home)}, clear=False):
                with patch.object(self.module, "tool_glue_resolve_codex_bin", return_value=Path("/Applications/Codex.app/Contents/Resources/codex")):
                    with patch.object(self.module.subprocess, "run", side_effect=fake_run):
                        with patch.object(self.module.time, "sleep", return_value=None):
                            payload = self.module.satellite_session_run_codex_exec_json(
                                "reply with a readiness note",
                                self.module.satellite_session_codex_schema(),
                                cwd=PROJECT_ROOT,
                                timeout=0,
                                execution_surface="gui_terminal",
                            )

        self.assertEqual(payload["returncode"], 0)
        self.assertEqual(payload["json"]["status"], "completed")

    def test_hidden_satellite_session_lane_passes_gui_terminal_surface_to_codex_exec(self) -> None:
        args = self.make_lane_args(lane="main", codex_execution_surface="gui_terminal", lane_command="")
        captured = {}

        def fake_exec(prompt, schema, *, cwd=None, sandbox="workspace-write", timeout=0, execution_surface="headless"):
            captured["execution_surface"] = execution_surface
            return {
                "returncode": 0,
                "stdout": "",
                "stderr": "",
                "json": {
                    "status": "completed",
                    "did_what": "Used gui terminal.",
                    "evidence_ref": [],
                    "blocking_reason": "",
                    "next_action": "",
                    "changed_files": [],
                    "commands_run": [],
                },
            }

        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            with patch.multiple(self.module, RUNS_ROOT=runs_root):
                with patch.object(self.module, "satellite_session_run_codex_exec_json", side_effect=fake_exec):
                    exit_code = self.module.command_satellite_session_lane(args)

        self.assertEqual(exit_code, 0)
        self.assertEqual(captured["execution_surface"], "gui_terminal")

    def test_satellite_session_dispatches_three_lanes_and_restores_remote_bundles(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            called_lanes: list[str] = []

            def fake_remote(remote_info, argv, *, timeout=900, input_text=None):
                self.assertEqual(remote_info["host"], "192.168.31.86")
                self.assertEqual(argv[0], "satellite-session-lane")
                lane = argv[argv.index("--lane") + 1]
                called_lanes.append(lane)
                if lane in {"main", "support"}:
                    self.assertIn("--codex-execution-surface", argv)
                    self.assertEqual(argv[argv.index("--codex-execution-surface") + 1], "gui_terminal")
                else:
                    self.assertNotIn("--codex-execution-surface", argv)
                return {
                    "returncode": 0,
                    "stdout": json.dumps(
                        {
                            "lane": lane,
                            "status": "completed",
                            "did_what": f"{lane} lane completed",
                            "evidence_ref": [f"{lane}-evidence.md"],
                            "blocking_reason": "",
                            "next_action": "",
                            "changed_files": [f"{lane}.txt"] if lane != "verify" else [],
                            "commands_run": [],
                            "remote_run_dir": f"/remote/{lane}",
                        },
                        ensure_ascii=False,
                    ),
                    "stderr": "",
                    "command": argv,
                }

            def fake_export(remote_info, *, run_id, created_at, include_files):
                lane = run_id.rsplit("-", 1)[-1]
                self.assertEqual(created_at, "2026-03-15T10:00:00+08:00")
                self.assertEqual(include_files, self.module.SATELLITE_SESSION_EXPORT_FILES)
                return self.sample_export_payload(lane)

            args = self.make_args()
            with patch.multiple(self.module, RUNS_ROOT=runs_root):
                with patch.object(self.module, "resolve_satellite_assignment", side_effect=self.fake_resolution):
                    with patch.object(self.module, "tool_glue_connected_source_row", side_effect=self.fake_source_row):
                        with patch.object(self.module, "tool_glue_remote_host_metadata", side_effect=self.fake_remote_info):
                            with patch.object(self.module, "tool_glue_run_remote_ai_da_guan_jia", side_effect=fake_remote):
                                with patch.object(self.module, "tool_glue_export_remote_run_files", side_effect=fake_export):
                                    exit_code = self.module.command_satellite_session(args)

            self.assertEqual(exit_code, 0)
            self.assertEqual(sorted(called_lanes), ["main", "support", "verify"])
            run_dir = runs_root / "2026-03-15" / args.run_id
            for relative_path in [
                "route.json",
                "worklog.json",
                "satellite-session-plan.json",
                "satellite-session-preflight.json",
                "lane-main.json",
                "lane-support.json",
                "lane-verify.json",
                "exported-remote-bundles.json",
                "satellite-session-recap.json",
                "satellite-session-recap.md",
            ]:
                self.assertTrue((run_dir / relative_path).exists(), relative_path)
            self.assertTrue((run_dir / "remote-lanes" / "main" / "lane-result.json").exists())
            recap = json.loads((run_dir / "satellite-session-recap.json").read_text(encoding="utf-8"))
            self.assertEqual(recap["overall_status"], "completed")
            self.assertEqual(len(recap["lanes"]), 3)

    def test_satellite_session_supports_selected_lanes_in_staggered_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            called_lanes: list[str] = []

            def fake_remote(remote_info, argv, *, timeout=900, input_text=None):
                lane = argv[argv.index("--lane") + 1]
                called_lanes.append(lane)
                return {
                    "returncode": 0,
                    "stdout": json.dumps(
                        {
                            "lane": lane,
                            "status": "completed",
                            "did_what": f"{lane} lane completed",
                            "evidence_ref": [f"{lane}-evidence.md"],
                            "blocking_reason": "",
                            "next_action": "",
                            "changed_files": [],
                            "commands_run": [],
                            "remote_run_dir": f"/remote/{lane}",
                        },
                        ensure_ascii=False,
                    ),
                    "stderr": "",
                    "command": argv,
                }

            def fake_export(remote_info, *, run_id, created_at, include_files):
                lane = run_id.rsplit("-", 1)[-1]
                return self.sample_export_payload(lane)

            args = self.make_args(
                run_id="adagj-satellite-session-staggered",
                selected_lanes="support,main",
                lane_launch_mode="staggered",
            )
            with patch.multiple(self.module, RUNS_ROOT=runs_root):
                with patch.object(self.module, "resolve_satellite_assignment", side_effect=self.fake_resolution):
                    with patch.object(self.module, "tool_glue_connected_source_row", side_effect=self.fake_source_row):
                        with patch.object(self.module, "tool_glue_remote_host_metadata", side_effect=self.fake_remote_info):
                            with patch.object(self.module, "tool_glue_run_remote_ai_da_guan_jia", side_effect=fake_remote):
                                with patch.object(self.module, "tool_glue_export_remote_run_files", side_effect=fake_export):
                                    exit_code = self.module.command_satellite_session(args)

            self.assertEqual(exit_code, 0)
            self.assertEqual(called_lanes, ["main", "support"])
            recap = json.loads(
                (runs_root / "2026-03-15" / args.run_id / "satellite-session-recap.json").read_text(encoding="utf-8")
            )
            self.assertEqual([item["lane"] for item in recap["lanes"]], ["main", "support"])
            self.assertEqual(recap["overall_status"], "completed")

    def test_satellite_session_auto_serializes_parallel_gui_codex_lanes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            called_lanes: list[str] = []

            def fake_remote(remote_info, argv, *, timeout=900, input_text=None):
                lane = argv[argv.index("--lane") + 1]
                called_lanes.append(lane)
                return {
                    "returncode": 0,
                    "stdout": json.dumps(
                        {
                            "lane": lane,
                            "status": "completed",
                            "did_what": f"{lane} lane completed",
                            "evidence_ref": [f"{lane}-evidence.md"],
                            "blocking_reason": "",
                            "next_action": "",
                            "changed_files": [],
                            "commands_run": [],
                            "remote_run_dir": f"/remote/{lane}",
                        },
                        ensure_ascii=False,
                    ),
                    "stderr": "",
                    "command": argv,
                }

            def fake_export(remote_info, *, run_id, created_at, include_files):
                lane = run_id.rsplit("-", 1)[-1]
                return self.sample_export_payload(lane)

            args = self.make_args(run_id="adagj-satellite-session-auto-staggered")
            with patch.multiple(self.module, RUNS_ROOT=runs_root):
                with patch.object(self.module, "resolve_satellite_assignment", side_effect=self.fake_resolution):
                    with patch.object(self.module, "tool_glue_connected_source_row", side_effect=self.fake_source_row):
                        with patch.object(self.module, "tool_glue_remote_host_metadata", side_effect=self.fake_remote_info):
                            with patch.object(self.module, "tool_glue_run_remote_ai_da_guan_jia", side_effect=fake_remote):
                                with patch.object(self.module, "tool_glue_export_remote_run_files", side_effect=fake_export):
                                    exit_code = self.module.command_satellite_session(args)

            self.assertEqual(exit_code, 0)
            self.assertEqual(called_lanes, ["main", "support", "verify"])
            plan = json.loads(
                (runs_root / "2026-03-15" / args.run_id / "satellite-session-plan.json").read_text(encoding="utf-8")
            )
            self.assertEqual(plan["lane_launch_mode"], "staggered")

    def test_current_project_readiness_probe_forces_staggered_launch(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            called_lanes: list[str] = []

            def fake_remote(remote_info, argv, *, timeout=900, input_text=None):
                lane = argv[argv.index("--lane") + 1]
                called_lanes.append(lane)
                return {
                    "returncode": 0,
                    "stdout": json.dumps(
                        {
                            "lane": lane,
                            "status": "completed",
                            "did_what": f"{lane} lane completed",
                            "evidence_ref": [f"{lane}-evidence.md"],
                            "blocking_reason": "",
                            "next_action": "",
                            "changed_files": [],
                            "commands_run": [],
                            "remote_run_dir": f"/remote/{lane}",
                        },
                        ensure_ascii=False,
                    ),
                    "stderr": "",
                    "command": argv,
                }

            def fake_export(remote_info, *, run_id, created_at, include_files):
                lane = run_id.rsplit("-", 1)[-1]
                return self.sample_export_payload(lane)

            args = self.make_args(
                run_id="adagj-satellite-session-current-project-readiness-v6-test",
                task="Current-project readiness probe v6 for AI大管家 black satellite.",
                lane_launch_mode="parallel",
            )
            with patch.multiple(self.module, RUNS_ROOT=runs_root):
                with patch.object(self.module, "resolve_satellite_assignment", side_effect=self.fake_resolution):
                    with patch.object(self.module, "tool_glue_connected_source_row", side_effect=self.fake_source_row):
                        with patch.object(self.module, "tool_glue_remote_host_metadata", side_effect=self.fake_remote_info):
                            with patch.object(self.module, "tool_glue_run_remote_ai_da_guan_jia", side_effect=fake_remote):
                                with patch.object(self.module, "tool_glue_export_remote_run_files", side_effect=fake_export):
                                    exit_code = self.module.command_satellite_session(args)

            self.assertEqual(exit_code, 0)
            self.assertEqual(called_lanes, ["main", "support", "verify"])
            plan = json.loads(
                (runs_root / "2026-03-15" / args.run_id / "satellite-session-plan.json").read_text(encoding="utf-8")
            )
            recap = json.loads(
                (runs_root / "2026-03-15" / args.run_id / "satellite-session-recap.json").read_text(encoding="utf-8")
            )
            self.assertEqual(plan["lane_launch_mode"], "staggered")
            self.assertEqual([item["lane"] for item in recap["lanes"]], ["main", "support", "verify"])
            self.assertEqual(recap["overall_status"], "completed")

    def test_resume_session_only_reruns_incomplete_lane(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            run_dir = runs_root / "2026-03-15" / "adagj-satellite-session-resume"
            run_dir.mkdir(parents=True, exist_ok=True)
            route_payload = self.module.satellite_session_route_payload(
                run_id="adagj-satellite-session-resume",
                created_at="2026-03-15T10:00:00+08:00",
                task_text="Resume satellite session",
                requested_alias="黑色",
                resolution=self.fake_resolution("黑色"),
                lane_specs=self.module.satellite_session_build_lane_specs(
                    task_text="Resume satellite session",
                    main_command="",
                    support_command="",
                    verify_command="",
                ),
                run_mode="visible",
                lane_count=3,
                lane_launch_mode="parallel",
            )
            plan_payload = {
                "run_id": "adagj-satellite-session-resume",
                "created_at": "2026-03-15T10:00:00+08:00",
                "requested_alias": "黑色",
                "resolved_source_id": "satellite-02",
                "lane_launch_mode": "parallel",
                "selected_lanes": ["main", "support", "verify"],
                "lanes": route_payload["satellite_session"]["lanes"],
            }
            (run_dir / "route.json").write_text(json.dumps(route_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            (run_dir / "satellite-session-plan.json").write_text(
                json.dumps(plan_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            for lane, status in [("main", "completed"), ("support", "blocked_system"), ("verify", "completed")]:
                (run_dir / f"lane-{lane}.json").write_text(
                    json.dumps({"lane": lane, "status": status}, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )

            called_lanes: list[str] = []

            def fake_remote(remote_info, argv, *, timeout=900, input_text=None):
                lane = argv[argv.index("--lane") + 1]
                called_lanes.append(lane)
                return {
                    "returncode": 0,
                    "stdout": json.dumps(
                        {
                            "lane": lane,
                            "status": "completed",
                            "did_what": f"{lane} resumed",
                            "evidence_ref": [f"{lane}.md"],
                            "blocking_reason": "",
                            "next_action": "",
                            "changed_files": [],
                            "commands_run": [],
                            "remote_run_dir": f"/remote/{lane}",
                        },
                        ensure_ascii=False,
                    ),
                    "stderr": "",
                    "command": argv,
                }

            def fake_export(remote_info, *, run_id, created_at, include_files):
                lane = run_id.rsplit("-", 1)[-1]
                return self.sample_export_payload(lane)

            args = self.make_args(task=None, resume_session="adagj-satellite-session-resume", run_id=None, created_at=None)
            with patch.multiple(self.module, RUNS_ROOT=runs_root):
                with patch.object(self.module, "resolve_satellite_assignment", side_effect=self.fake_resolution):
                    with patch.object(self.module, "tool_glue_connected_source_row", side_effect=self.fake_source_row):
                        with patch.object(self.module, "tool_glue_remote_host_metadata", side_effect=self.fake_remote_info):
                            with patch.object(self.module, "tool_glue_run_remote_ai_da_guan_jia", side_effect=fake_remote):
                                with patch.object(self.module, "tool_glue_export_remote_run_files", side_effect=fake_export):
                                    exit_code = self.module.command_satellite_session(args)

            self.assertEqual(exit_code, 0)
            self.assertEqual(called_lanes, ["support"])
            recap = json.loads((run_dir / "satellite-session-recap.json").read_text(encoding="utf-8"))
            self.assertEqual(recap["overall_status"], "completed")

    def test_hidden_satellite_session_lane_writes_remote_lane_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            args = self.make_lane_args()

            def fake_run(command, *, cwd=None, timeout=20, input_text=None):
                self.assertEqual(command[0:2], ["/bin/zsh", "-lc"])
                self.assertIn("python3 scripts/yuanli_governance.py validate", command[2])
                return {
                    "command": command,
                    "returncode": 0,
                    "stdout": "validation passed\n",
                    "stderr": "",
                    "timed_out": False,
                }

            with patch.multiple(self.module, RUNS_ROOT=runs_root):
                with patch.object(self.module, "run_command_capture", side_effect=fake_run):
                    exit_code = self.module.command_satellite_session_lane(args)

            self.assertEqual(exit_code, 0)
            run_dir = runs_root / "2026-03-15" / args.run_id
            for relative_path in [
                "route.json",
                "lane-manifest.json",
                "command-result.json",
                "lane-result.json",
                "lane-summary.md",
                "worklog.json",
                "worklog.md",
            ]:
                self.assertTrue((run_dir / relative_path).exists(), relative_path)
            lane_result = json.loads((run_dir / "lane-result.json").read_text(encoding="utf-8"))
            self.assertEqual(lane_result["status"], "completed")
            self.assertEqual(lane_result["remote_run_dir"], str(run_dir.resolve()))

    def test_hidden_satellite_session_lane_uses_codex_exec_for_main_lane(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            args = self.make_lane_args(
                lane="main",
                lane_command="",
                run_id="adagj-satellite-session-main",
            )

            with patch.multiple(self.module, RUNS_ROOT=runs_root):
                with patch.object(
                    self.module,
                    "satellite_session_run_codex_exec_json",
                    return_value={
                        "returncode": 0,
                        "stdout": "",
                        "stderr": "",
                        "json": {
                            "status": "completed",
                            "did_what": "Main lane advanced the task.",
                            "evidence_ref": ["notes/main.md"],
                            "blocking_reason": "",
                            "next_action": "",
                            "changed_files": ["work/ai-da-guan-jia/scripts/ai_da_guan_jia.py"],
                            "commands_run": ["rg -n satellite-session work/ai-da-guan-jia/scripts/ai_da_guan_jia.py"],
                        },
                    },
                ):
                    exit_code = self.module.command_satellite_session_lane(args)

            self.assertEqual(exit_code, 0)
            run_dir = runs_root / "2026-03-15" / args.run_id
            self.assertTrue((run_dir / "codex-exec-result.json").exists())
            lane_result = json.loads((run_dir / "lane-result.json").read_text(encoding="utf-8"))
            self.assertEqual(lane_result["status"], "completed")
            self.assertIn("work/ai-da-guan-jia/scripts/ai_da_guan_jia.py", lane_result["changed_files"])

    def test_hidden_satellite_session_lane_marks_codex_auth_failure_as_blocked_needs_user(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            args = self.make_lane_args(
                lane="main",
                lane_command="",
                run_id="adagj-satellite-session-main-auth",
            )

            with patch.multiple(self.module, RUNS_ROOT=runs_root):
                with patch.object(
                    self.module,
                    "satellite_session_run_codex_exec_json",
                    return_value={
                        "returncode": 1,
                        "stdout": "provider: openai\n",
                        "stderr": "401 Unauthorized: Missing bearer or basic authentication in header",
                        "json": None,
                    },
                ):
                    exit_code = self.module.command_satellite_session_lane(args)

            self.assertEqual(exit_code, 0)
            run_dir = runs_root / "2026-03-15" / args.run_id
            lane_result = json.loads((run_dir / "lane-result.json").read_text(encoding="utf-8"))
            self.assertEqual(lane_result["status"], "blocked_needs_user")
            self.assertEqual(lane_result["blocking_reason"], "remote_codex_local_auth_required")
            self.assertIn("local Codex login", lane_result["next_action"])

    def test_hidden_satellite_session_lane_marks_usage_limit_as_blocked_needs_user(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            args = self.make_lane_args(
                lane="main",
                lane_command="",
                run_id="adagj-satellite-session-main-quota",
            )

            with patch.multiple(self.module, RUNS_ROOT=runs_root):
                with patch.object(
                    self.module,
                    "satellite_session_run_codex_exec_json",
                    return_value={
                        "returncode": 124,
                        "stdout": "",
                        "stderr": "ERROR: You've hit your usage limit. Upgrade to Pro or visit https://chatgpt.com/codex/settings/usage.",
                        "json": None,
                    },
                ):
                    exit_code = self.module.command_satellite_session_lane(args)

            self.assertEqual(exit_code, 0)
            run_dir = runs_root / "2026-03-15" / args.run_id
            lane_result = json.loads((run_dir / "lane-result.json").read_text(encoding="utf-8"))
            self.assertEqual(lane_result["status"], "blocked_needs_user")
            self.assertEqual(lane_result["blocking_reason"], "remote_codex_local_quota_or_api_profile_required")

    def test_readiness_probe_prompt_discourages_repo_edits(self) -> None:
        prompt = self.module.satellite_session_lane_prompt(
            lane="main",
            task_text="Clean GUI single-lane probe on the black satellite. Return one truthful structured readiness note only.",
            session_run_id="adagj-probe",
            run_mode="visible",
            lane_command="",
        )

        self.assertIn("This is a readiness probe, not an implementation round.", prompt)
        self.assertIn("Do not write patches, plans, or diff text.", prompt)

    def test_current_project_readiness_probe_prompt_pins_fixed_validation_set(self) -> None:
        prompt = self.module.satellite_session_lane_prompt(
            lane="main",
            task_text="Current-project readiness probe v4 for AI大管家 black satellite.",
            session_run_id="adagj-probe-v4",
            run_mode="visible",
            lane_command="",
        )

        self.assertIn("python3 -m unittest tests.test_ai_da_guan_jia_satellite_session", prompt)
        self.assertIn("python3 -m unittest tests.test_ai_da_guan_jia_autoclaw_framework", prompt)
        self.assertIn("python3 scripts/yuanli_governance.py validate", prompt)
        self.assertIn("Do not cite or run broader readiness validation", prompt)

    def test_current_project_readiness_probe_verify_lane_uses_fixed_validation_bundle(self) -> None:
        specs = self.module.satellite_session_build_lane_specs(
            task_text="Current-project readiness probe v4 for AI大管家 black satellite.",
            main_command="",
            support_command="",
            verify_command="",
        )

        verify_spec = next(item for item in specs if item["lane"] == "verify")
        self.assertEqual(
            verify_spec["lane_command"],
            "python3 -m unittest tests.test_ai_da_guan_jia_satellite_session && "
            "python3 -m unittest tests.test_ai_da_guan_jia_autoclaw_framework && "
            "python3 scripts/yuanli_governance.py validate",
        )

    def test_hidden_satellite_session_lane_marks_missing_structured_note_as_blocked_system(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            args = self.make_lane_args(
                lane="main",
                lane_command="",
                run_id="adagj-satellite-session-main-missing-note",
            )

            with patch.multiple(self.module, RUNS_ROOT=runs_root):
                with patch.object(
                    self.module,
                    "satellite_session_run_codex_exec_json",
                    return_value={
                        "returncode": 124,
                        "stdout": "",
                        "stderr": "Warning: no last agent message; wrote empty content to result.json",
                        "json": None,
                    },
                ):
                    exit_code = self.module.command_satellite_session_lane(args)

            self.assertEqual(exit_code, 1)
            run_dir = runs_root / "2026-03-15" / args.run_id
            lane_result = json.loads((run_dir / "lane-result.json").read_text(encoding="utf-8"))
            self.assertEqual(lane_result["status"], "blocked_system")
            self.assertEqual(lane_result["blocking_reason"], "remote_codex_structured_note_missing")

    def test_hidden_satellite_session_lane_keeps_non_auth_codex_failure_as_blocked_system(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            args = self.make_lane_args(
                lane="main",
                lane_command="",
                run_id="adagj-satellite-session-main-system",
            )

            with patch.multiple(self.module, RUNS_ROOT=runs_root):
                with patch.object(
                    self.module,
                    "satellite_session_run_codex_exec_json",
                    return_value={
                        "returncode": 1,
                        "stdout": "",
                        "stderr": "RuntimeError: unexpected filesystem failure",
                        "json": None,
                    },
                ):
                    exit_code = self.module.command_satellite_session_lane(args)

            self.assertEqual(exit_code, 1)
            run_dir = runs_root / "2026-03-15" / args.run_id
            lane_result = json.loads((run_dir / "lane-result.json").read_text(encoding="utf-8"))
            self.assertEqual(lane_result["status"], "blocked_system")
            self.assertIn("unexpected filesystem failure", lane_result["blocking_reason"])


if __name__ == "__main__":
    unittest.main()
