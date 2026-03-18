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


class ToolGlueZsxqPublishTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPT_ROOT))
        cls.module = load_module("test_ai_da_guan_jia_tool_glue_zsxq_publish", SCRIPT_PATH)

    def make_args(self, **overrides):
        base = {
            "feishu_url": "https://example.test/docx/transcript",
            "executor_source_id": "satellite-03",
            "group_url": "https://wx.zsxq.com/group/15554854424522",
            "polish_mode": "wechat_skill_local",
            "claudy_match": "CLAUDY",
            "publish_stages": "doubao,polish",
            "send_stages": "polish",
            "doubao_url": "https://example.test/doubao",
            "claudy_url": "",
            "run_id": "adagj-tool-glue-zsxq",
            "created_at": "2026-03-14T23:00:00+08:00",
            "session": None,
            "headless": False,
            "apply": False,
            "final_send": False,
        }
        base.update(overrides)
        return types.SimpleNamespace(**base)

    def sample_bundle(self, *, feishu_title: str = "飞书妙计主题") -> dict[str, object]:
        feishu_stage = self.module.tool_glue_stage_record(
            name="feishu",
            status="completed",
            success=True,
            output_text=("逐字稿正文\n" * 240).strip(),
            target_url="https://example.test/docx/transcript",
            extra={"title": feishu_title},
        )
        doubao_stage = self.module.tool_glue_stage_record(
            name="doubao",
            status="completed",
            success=True,
            output_text=("豆包长文\n" * 1600).strip(),
            target_url="https://example.test/doubao",
        )
        polish_stage = self.module.tool_glue_stage_record(
            name="polish",
            status="completed",
            success=True,
            output_text=("公众号定稿\n" * 1700).strip(),
            target_url="local_codex_exec::wechat-article-writer",
        )
        baseline_stage = self.module.tool_glue_stage_record(
            name="baseline_direct_polish",
            status="completed",
            success=True,
            output_text=("基线长文\n" * 1200).strip(),
            target_url="local_codex_exec::wechat-article-writer",
        )
        return {
            "route": {"run_id": "adagj-tool-glue-zsxq", "polish_mode": "wechat_skill_local", "resolved_claudy_url": ""},
            "scorecard": {
                "stages": {
                    "feishu": feishu_stage,
                    "doubao": doubao_stage,
                    "polish": polish_stage,
                    "baseline_direct_polish": baseline_stage,
                },
                "stage_order": ["feishu", "doubao", "polish", "baseline_direct_polish"],
                "final_stage_name": "polish",
                "baseline_stage_name": "baseline_direct_polish",
            },
            "verdict": {"closure_state": "completed", "verdict": "keep_and_harden"},
            "feishu_stage": feishu_stage,
            "stages": {
                "feishu": feishu_stage,
                "doubao": doubao_stage,
                "polish": polish_stage,
                "baseline_direct_polish": baseline_stage,
            },
        }

    def test_parser_registers_tool_glue_zsxq_publish_defaults(self) -> None:
        parser = self.module.build_parser()
        parsed = parser.parse_args(["tool-glue-zsxq-publish", "--feishu-url", "https://example.test/docx/1"])
        self.assertEqual(parsed.func.__name__, "command_tool_glue_zsxq_publish")
        self.assertEqual(parsed.executor_source_id, "satellite-03")
        self.assertEqual(parsed.group_url, "https://wx.zsxq.com/group/15554854424522")
        self.assertEqual(parsed.polish_mode, "wechat_skill_local")
        self.assertEqual(parsed.publish_stages, "doubao,polish")
        self.assertEqual(parsed.send_stages, "polish")
        self.assertFalse(parsed.final_send)

    def test_dispatch_helper_uses_true_remote_executor_and_restores_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            temp_root = Path(tempdir)
            current_root = temp_root / "current"
            current_root.mkdir(parents=True, exist_ok=True)
            (current_root / "source-status.json").write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "source_id": "satellite-03",
                                "status": "connected",
                                "hostname": "MacBookPro",
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            remote_root = temp_root / "remote-hosts-v2" / "satellite-03"
            remote_root.mkdir(parents=True, exist_ok=True)
            (remote_root / "onboarding-result.json").write_text(
                json.dumps(
                    {
                        "source_id": "satellite-03",
                        "host": "192.168.31.83",
                        "user": "liming",
                        "workspace_root": "/Users/liming/Documents/codex-ai-gua-jia-01",
                        "client_mode": "vscode-agent",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            def fake_remote(remote_info, argv, *, timeout=900, input_text=None):
                if argv[0] == "tool-glue-benchmark":
                    self.assertEqual(remote_info["host"], "192.168.31.83")
                    return {"returncode": 0, "stdout": "run_id: dispatch-connected\n", "stderr": "", "command": argv}
                self.assertEqual(argv[0], "tool-glue-export-run")
                export_payload = {
                    "status": "completed",
                    "files": [
                        {
                            "relative_path": "mvp-verdict.json",
                            "content": json.dumps({"closure_state": "completed"}, ensure_ascii=False, indent=2) + "\n",
                        },
                        {
                            "relative_path": "route.json",
                            "content": json.dumps({"resolved_claudy_url": "https://claudy.example/chat"}, ensure_ascii=False, indent=2) + "\n",
                        },
                    ],
                    "missing_files": [],
                }
                return {"returncode": 0, "stdout": json.dumps(export_payload, ensure_ascii=False), "stderr": "", "command": argv}

            with patch.multiple(
                self.module,
                RUNS_ROOT=temp_root / "runs",
                HUB_CURRENT_ROOT=current_root,
                REMOTE_HOSTS_V2_ROOT=temp_root / "remote-hosts-v2",
                REMOTE_HOSTS_ROOT=temp_root / "remote-hosts",
            ):
                with patch.object(self.module, "tool_glue_run_remote_ai_da_guan_jia", side_effect=fake_remote):
                    connected = self.module.tool_glue_dispatch_benchmark_to_executor(
                        run_id="dispatch-connected",
                        created_at="2026-03-14T23:10:00+08:00",
                        feishu_url="https://example.test/docx/dispatch",
                        executor_source_id="satellite-03",
                        doubao_url="https://example.test/doubao",
                        polish_mode="wechat_skill_local",
                        claudy_match="CLAUDY",
                        claudy_url="",
                    )
                    blocked = self.module.tool_glue_dispatch_benchmark_to_executor(
                        run_id="dispatch-blocked",
                        created_at="2026-03-14T23:11:00+08:00",
                        feishu_url="https://example.test/docx/blocked",
                        executor_source_id="satellite-09",
                        doubao_url="https://example.test/doubao",
                        polish_mode="wechat_skill_local",
                        claudy_match="CLAUDY",
                        claudy_url="",
                    )

        self.assertEqual(connected["status"], "completed")
        self.assertEqual(connected["dispatch_method"], "remote_ssh_exec")
        self.assertEqual(connected["remote_info"]["host"], "192.168.31.83")
        self.assertIn("mvp-verdict.json", connected["restored_files"])
        self.assertEqual(connected["visibility"]["preferred_visible"], True)
        self.assertIn("why_not_visible", connected["visibility"])
        self.assertTrue(connected["why_not_visible"])
        self.assertEqual(blocked["status"], "blocked_system")
        self.assertEqual(blocked["blocking_reason"], "executor_source_not_connected")

    def test_recent_run_claudy_url_beats_tab_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            prior_run = runs_root / "2026-03-14" / "adagj-prior"
            prior_run.mkdir(parents=True, exist_ok=True)
            (prior_run / "route.json").write_text(
                json.dumps(
                    {
                        "workflow_id": "workflow:tool-glue-zsxq-publish-v2",
                        "resolved_claudy_url": "https://claudy.example/from-recent-run",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            current_run = runs_root / "2026-03-15" / "adagj-current"
            current_run.mkdir(parents=True, exist_ok=True)
            with patch.multiple(self.module, RUNS_ROOT=runs_root):
                with patch.object(self.module, "list_google_chrome_tabs", return_value=[{"title": "CLAUDY", "url": "https://claudy.example/from-tab"}]):
                    url, matched_tab, strategy = self.module.tool_glue_resolved_claudy_target(
                        current_run,
                        explicit_url="",
                        claudy_match="CLAUDY",
                    )
        self.assertEqual(url, "https://claudy.example/from-recent-run")
        self.assertEqual(matched_tab, {})
        self.assertEqual(strategy, "recent_successful_run")

    def test_command_tool_glue_zsxq_publish_writes_preview_bundle_and_send_stages(self) -> None:
        bundle = self.sample_bundle()
        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            args = self.make_args(run_id="tool-glue-zsxq-preview")
            with patch.multiple(self.module, RUNS_ROOT=runs_root):
                with patch.object(
                    self.module,
                    "tool_glue_dispatch_benchmark_to_executor",
                    return_value={"status": "completed", "executor_source_id": "satellite-03", "dispatch_method": "remote_ssh_exec"},
                ):
                    with patch.object(self.module, "tool_glue_load_benchmark_bundle", return_value=bundle):
                        with patch.object(
                            self.module,
                            "tool_glue_write_publish_closure",
                            return_value={
                                "feishu": {"apply": {"status": "not_attempted"}},
                                "github": {"closure_dry_run": {"status": "github_closure_preview_ready"}},
                            },
                        ):
                            exit_code = self.module.command_tool_glue_zsxq_publish(args)
            self.assertEqual(exit_code, 0)
            run_dir = runs_root / "2026-03-14" / args.run_id
            self.assertTrue((run_dir / "publish-batch.json").exists())
            self.assertTrue((run_dir / "publish-preview.md").exists())
            self.assertTrue((run_dir / "zsxq-doubao-packet.json").exists())
            self.assertTrue((run_dir / "zsxq-polish-packet.json").exists())
            self.assertFalse((run_dir / "zsxq-baseline-claudy-packet.json").exists())

            batch = json.loads((run_dir / "publish-batch.json").read_text(encoding="utf-8"))
            self.assertEqual(batch["closure_state"], "completed")
            self.assertEqual(batch["send_stages"], ["polish"])
            self.assertFalse(batch["final_send"])
            self.assertEqual(len(batch["entries"]), 2)
            self.assertEqual(batch["counts"]["ready"], 2)
            self.assertEqual(batch["counts"]["draft_ready"], 1)
            self.assertEqual(batch["counts"]["manual_confirmation_required"], 1)
            self.assertEqual(batch["base_title"], "飞书妙计主题")

            route = json.loads((run_dir / "route.json").read_text(encoding="utf-8"))
            self.assertEqual(route["closure_state"], "completed")
            self.assertEqual(route["publish_stages"], ["doubao", "polish"])
            self.assertEqual(route["send_stages"], ["polish"])
            self.assertEqual(route["polish_mode"], "wechat_skill_local")
            self.assertEqual(route["remote_visibility_defaults"]["priority"], "stability_first")
            self.assertIn("remote_execution_visibility", route)

            doubao_result = json.loads((run_dir / "zsxq-doubao-result.json").read_text(encoding="utf-8"))
            polish_result = json.loads((run_dir / "zsxq-polish-result.json").read_text(encoding="utf-8"))
            self.assertEqual(doubao_result["status"], "draft_ready")
            self.assertFalse(doubao_result["send_selected"])
            self.assertEqual(polish_result["status"], "manual_confirmation_required")
            self.assertTrue(polish_result["send_selected"])

    def test_command_tool_glue_zsxq_publish_apply_only_sends_selected_stage(self) -> None:
        bundle = self.sample_bundle()
        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            args = self.make_args(
                run_id="tool-glue-zsxq-apply",
                apply=True,
                final_send=True,
                send_stages="doubao,polish",
            )
            publish_calls: list[dict[str, object]] = []

            def fake_remote_publish(*, packet, executor_source_id, session, headless, final_send):
                publish_calls.append(
                    {
                        "stage_name": packet["stage_name"],
                        "executor_source_id": executor_source_id,
                        "session": session,
                        "headless": headless,
                        "final_send": final_send,
                    }
                )
                return {
                    "run_id": packet["run_id"],
                    "stage_name": packet["stage_name"],
                    "status": "published",
                    "message": "remote final send verified",
                    "screenshots": [f"/tmp/{packet['stage_name']}.png"],
                    "snapshots": [f"/tmp/{packet['stage_name']}.txt"],
                }

            with patch.multiple(self.module, RUNS_ROOT=runs_root):
                with patch.object(
                    self.module,
                    "tool_glue_dispatch_benchmark_to_executor",
                    return_value={"status": "completed", "executor_source_id": "satellite-03", "dispatch_method": "remote_ssh_exec"},
                ):
                        with patch.object(self.module, "tool_glue_load_benchmark_bundle", return_value=bundle):
                            with patch.object(self.module, "tool_glue_dispatch_publish_stage_to_executor", side_effect=fake_remote_publish):
                                with patch.object(
                                    self.module,
                                    "tool_glue_write_publish_closure",
                                    return_value={
                                        "feishu": {"apply": {"status": "synced_applied"}},
                                        "github": {"closure_dry_run": {"status": "github_closure_preview_ready"}},
                                    },
                                ):
                                    exit_code = self.module.command_tool_glue_zsxq_publish(args)
            self.assertEqual(exit_code, 0)
            self.assertEqual(len(publish_calls), 2)
            self.assertEqual({call["stage_name"] for call in publish_calls}, {"doubao", "polish"})
            self.assertTrue(all(bool(call["final_send"]) for call in publish_calls))

            run_dir = runs_root / "2026-03-14" / args.run_id
            batch = json.loads((run_dir / "publish-batch.json").read_text(encoding="utf-8"))
            self.assertEqual(batch["counts"]["published"], 2)
            self.assertEqual(batch["counts"]["draft_ready"], 0)

            doubao_result = json.loads((run_dir / "zsxq-doubao-result.json").read_text(encoding="utf-8"))
            polish_result = json.loads((run_dir / "zsxq-polish-result.json").read_text(encoding="utf-8"))
            self.assertEqual(doubao_result["status"], "published")
            self.assertEqual(polish_result["status"], "published")
            self.assertTrue(doubao_result["final_send_requested"])
            self.assertTrue(polish_result["final_send_requested"])

    def test_local_publish_send_without_confirmation_evidence_becomes_failed_partial(self) -> None:
        packet = {
            "run_id": "adagj-publish-final",
            "group_url": "https://wx.zsxq.com/group/15554854424522",
            "stage_name": "polish",
            "title": "公众号润色定稿｜飞书妙计主题",
            "body_markdown": "正文",
            "tag_suggestions": ["原力星球", "公众号润色定稿"],
            "artifact_dir": tempfile.gettempdir(),
        }
        click_results = [
            {"clicked": True, "matched_text": "发帖", "command": {"step": "compose"}, "payload": {"clicked": True}},
            {"clicked": True, "matched_text": "发布", "command": {"step": "publish"}, "payload": {"clicked": True}},
        ]
        evidence_results = [
            {"screenshot": "/tmp/pre.png", "snapshot": "/tmp/pre.txt"},
            {"screenshot": "/tmp/post.png", "snapshot": "/tmp/post.txt"},
        ]
        with patch.object(self.module, "tool_glue_runtime_ready", return_value={"npx_available": True, "playwright_wrapper_exists": True}):
            with patch.object(self.module, "run_playwright_cli", return_value={"returncode": 0, "stdout": "", "stderr": ""}):
                with patch.object(self.module, "tool_glue_wait", return_value={"returncode": 0, "stdout": "", "stderr": ""}):
                    with patch.object(
                        self.module,
                        "tool_glue_probe_page",
                        return_value={"command": {"returncode": 0}, "payload": {"text": "原力星球页面", "title": "原力星球", "url": packet["group_url"]}},
                    ):
                        with patch.object(self.module, "tool_glue_click_any_text", side_effect=click_results):
                            with patch.object(
                                self.module,
                                "tool_glue_fill_zsxq_publish_form",
                                return_value={"command": {"returncode": 0}, "payload": {"title_filled": True, "body_filled": True}},
                            ):
                                with patch.object(self.module, "tool_glue_capture_page_evidence", side_effect=evidence_results):
                                    with patch.object(
                                        self.module,
                                        "tool_glue_collect_publish_confirmation",
                                        return_value={"success": False, "payload": {"url": packet["group_url"]}, "command": {"returncode": 0}},
                                    ):
                                        result = self.module.tool_glue_run_local_zsxq_publish_web(
                                            packet,
                                            execute=True,
                                            headed=True,
                                            session="zsxq-final",
                                            final_send=True,
                                        )
        self.assertEqual(result["status"], "failed_partial")
        self.assertEqual(result["blocking_reason"], "post_submit_confirmation_missing")
        self.assertEqual(result["screenshots"], ["/tmp/pre.png", "/tmp/post.png"])
        self.assertTrue(result["visibility"]["actual_visible"])
        self.assertEqual(result["visibility"]["evidence_paths"], ["/tmp/pre.png", "/tmp/post.png", "/tmp/pre.txt", "/tmp/post.txt"])

    def test_local_publish_blocks_when_target_column_cannot_be_selected(self) -> None:
        packet = {
            "run_id": "adagj-publish-column",
            "group_url": "https://wx.zsxq.com/group/15554854424522",
            "stage_name": "polish",
            "title": "栏目测试",
            "body_markdown": "正文",
            "tag_suggestions": ["原力星球"],
            "target_column_name": "原力小刺猬",
            "artifact_dir": tempfile.gettempdir(),
        }
        with patch.object(self.module, "tool_glue_runtime_ready", return_value={"npx_available": True, "playwright_wrapper_exists": True}):
            with patch.object(self.module, "run_playwright_cli", return_value={"returncode": 0, "stdout": "", "stderr": ""}):
                with patch.object(self.module, "tool_glue_wait", return_value={"returncode": 0, "stdout": "", "stderr": ""}):
                    with patch.object(
                        self.module,
                        "tool_glue_probe_page",
                        return_value={"command": {"returncode": 0}, "payload": {"text": "原力星球页面", "title": "原力星球", "url": packet["group_url"]}},
                    ):
                        with patch.object(
                            self.module,
                            "tool_glue_click_any_text",
                            return_value={"clicked": True, "matched_text": "发帖", "command": {"step": "compose"}, "payload": {"clicked": True}},
                        ):
                            with patch.object(
                                self.module,
                                "tool_glue_fill_zsxq_publish_form",
                                return_value={
                                    "command": {"returncode": 0},
                                    "payload": {"column_selected": False, "title_filled": True, "body_filled": True},
                                },
                            ):
                                result = self.module.tool_glue_run_local_zsxq_publish_web(
                                    packet,
                                    execute=True,
                                    headed=True,
                                    session="zsxq-column",
                                    final_send=False,
                                )
        self.assertEqual(result["status"], "blocked_needs_user")
        self.assertEqual(result["blocking_reason"], "missing_ui::target_column")

    def test_command_tool_glue_zsxq_publish_surfaces_blocked_executor(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            args = self.make_args(run_id="tool-glue-zsxq-blocked")
            with patch.multiple(self.module, RUNS_ROOT=runs_root):
                with patch.object(
                    self.module,
                    "tool_glue_dispatch_benchmark_to_executor",
                    return_value={
                        "status": "blocked_system",
                        "executor_source_id": "satellite-03",
                        "blocking_reason": "executor_source_not_connected",
                    },
                ):
                    with patch.object(
                        self.module,
                        "tool_glue_write_publish_closure",
                        return_value={
                            "feishu": {"apply": {"status": "payload_only_missing_link"}},
                                "github": {"closure_dry_run": {"status": "github_closure_preview_ready"}},
                        },
                    ):
                        exit_code = self.module.command_tool_glue_zsxq_publish(args)
            self.assertEqual(exit_code, 1)
            run_dir = runs_root / "2026-03-14" / args.run_id
            batch = json.loads((run_dir / "publish-batch.json").read_text(encoding="utf-8"))
            self.assertEqual(batch["closure_state"], "blocked_system")
            self.assertEqual(batch["entries"], [])
            route = json.loads((run_dir / "route.json").read_text(encoding="utf-8"))
            self.assertEqual(route["closure_state"], "blocked_system")


if __name__ == "__main__":
    unittest.main()
