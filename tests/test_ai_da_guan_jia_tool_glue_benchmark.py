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


class ToolGlueBenchmarkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPT_ROOT))
        cls.module = load_module("test_ai_da_guan_jia_tool_glue", SCRIPT_PATH)

    def test_build_tool_glue_prompt_uses_fixed_prefixes(self) -> None:
        transcript = "这是逐字稿正文。"
        doubao_prompt = self.module.build_tool_glue_prompt(transcript, mode="doubao")
        polish_prompt = self.module.build_tool_glue_prompt(transcript, mode="polish")
        claudy_prompt = self.module.build_tool_glue_prompt(transcript, mode="claudy")

        self.assertTrue(doubao_prompt.startswith(self.module.TOOL_GLUE_DOUBAO_PROMPT_PREFIX))
        self.assertTrue(polish_prompt.startswith(self.module.TOOL_GLUE_WECHAT_POLISH_PROMPT_PREFIX))
        self.assertTrue(claudy_prompt.startswith(self.module.TOOL_GLUE_CLAUDY_PROMPT_PREFIX))
        self.assertIn(transcript, doubao_prompt)
        self.assertIn(transcript, polish_prompt)
        self.assertIn(transcript, claudy_prompt)

    def test_tool_glue_required_files_include_raw_transcript_exports(self) -> None:
        required_files = self.module.tool_glue_required_files("wechat_skill_local")
        self.assertIn("transcript-source.raw.json", required_files)
        self.assertIn("transcript-source.raw.md", required_files)

    def test_tool_glue_playwright_session_name_stays_short(self) -> None:
        session = self.module.tool_glue_playwright_session_name(
            "adagj-20260314-164139-000000",
            "zsxq-polish-stage-with-a-very-long-name",
        )
        self.assertLessEqual(len(session), 10)
        self.assertTrue(session.startswith("tg"))

    def test_tool_glue_run_page_script_wraps_async_iife(self) -> None:
        with patch.object(self.module, "run_playwright_cli", return_value={"returncode": 0}) as mocked:
            self.module.tool_glue_run_page_script("const x = 1;\nawait page.waitForTimeout(10);", session="tg12345678", cwd=PROJECT_ROOT)
        args = mocked.call_args.args[0]
        self.assertEqual(args[0], "run-code")
        self.assertIn("(async () => {", args[1])
        self.assertIn("await page.waitForTimeout(10);", args[1])
        self.assertTrue(args[1].strip().endswith("})()"))

    def test_tool_glue_pick_browser_tab_prefers_claudy_then_claude(self) -> None:
        tabs = [
            {"title": "Claude", "url": "https://claude.example/chat"},
            {"title": "CLAUDY CHAT", "url": "https://claudy.example/chat"},
            {"title": "Something Else", "url": "https://example.test"},
        ]
        selected = self.module.tool_glue_pick_browser_tab(tabs, "CLAUDY")
        fallback = self.module.tool_glue_pick_browser_tab([tabs[0], tabs[2]], "CLAUDY")

        self.assertIsNotNone(selected)
        self.assertEqual(selected["title"], "CLAUDY CHAT")
        self.assertIsNotNone(fallback)
        self.assertEqual(fallback["title"], "Claude")

    def test_tool_glue_select_all_decision_tracks_retry_window(self) -> None:
        first = self.module.tool_glue_select_all_decision("这里需要 全部选择 才能继续", 0)
        last = self.module.tool_glue_select_all_decision("这里需要 全部选择 才能继续", 2)
        none = self.module.tool_glue_select_all_decision("普通正文，没有额外选择", 0)

        self.assertTrue(first["needed"])
        self.assertTrue(first["retry_after_action"])
        self.assertFalse(last["retry_after_action"])
        self.assertEqual(none["action"], "none")

    def test_tool_glue_scorecard_and_verdict_degrade_when_outputs_are_missing(self) -> None:
        feishu = self.module.tool_glue_stage_record(
            name="feishu",
            status="completed",
            success=True,
            output_text="逐字稿" * 200,
        )
        doubao = self.module.tool_glue_stage_record(
            name="doubao",
            status="failed_partial",
            success=False,
            input_chars=1000,
            output_text="",
            blocking_reason="output_not_ready",
        )
        final_stage = self.module.tool_glue_stage_record(
            name="polish",
            status="failed_partial",
            success=False,
            input_chars=1000,
            output_text="",
            blocking_reason="output_not_ready",
        )
        baseline = self.module.tool_glue_stage_record(
            name="baseline_direct_polish",
            status="failed_partial",
            success=False,
            input_chars=1000,
            output_text="",
            blocking_reason="output_not_ready",
        )
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            artifact_paths = [root / name for name in self.module.tool_glue_required_files("wechat_skill_local")[:3]]
            for path in artifact_paths:
                path.write_text("ok\n", encoding="utf-8")
            scorecard = self.module.tool_glue_scorecard_from_stages(
                feishu_stage=feishu,
                doubao_stage=doubao,
                final_stage=final_stage,
                baseline_stage=baseline,
                final_stage_name="polish",
                baseline_stage_name="baseline_direct_polish",
                artifact_paths=artifact_paths,
            )
            verdict = self.module.tool_glue_verdict_from_scorecard(scorecard)

        self.assertLess(scorecard["chain_scores"]["联合效率"]["score"], 70)
        self.assertEqual(verdict["verdict"], "not_worth_gluing")
        self.assertEqual(verdict["closure_state"], "failed_partial")

    def test_run_tool_glue_wechat_polish_stage_uses_workspace_claude_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            temp_root = Path(tempdir)
            skill_path = temp_root / "wechat-skill.md"
            skill_path.write_text("skill-body\n", encoding="utf-8")
            claude_path = temp_root / "CLAUDE.md"
            claude_path.write_text("style-body\n", encoding="utf-8")
            exec_payload = {
                "returncode": 0,
                "json": {
                    "status": "completed",
                    "title": "润色定稿",
                    "article_markdown": "润色长文\n" * 800,
                    "alternate_titles": ["标题一", "标题二"],
                    "summary": "总结",
                    "notes": "说明",
                },
            }
            with patch.object(self.module, "TOOL_GLUE_WECHAT_SKILL_PATH", skill_path):
                with patch.object(self.module, "tool_glue_resolve_codex_bin", return_value=Path("/tmp/codex")):
                    with patch.object(self.module, "tool_glue_find_workspace_claude_md", return_value=claude_path):
                        with patch.object(self.module, "tool_glue_run_codex_exec_json", return_value=exec_payload):
                            stage = self.module.run_tool_glue_wechat_polish_stage(
                                stage_name="polish",
                                prompt_text="请润色这篇文章",
                            )

        self.assertEqual(stage["status"], "completed")
        self.assertTrue(stage["success"])
        self.assertEqual(stage["claude_style_source"], "workspace_claude_md")
        self.assertEqual(stage["title"], "润色定稿")

    def test_run_tool_glue_wechat_polish_stage_falls_back_when_claude_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            skill_path = Path(tempdir) / "wechat-skill.md"
            skill_path.write_text("skill-body\n", encoding="utf-8")
            exec_payload = {
                "returncode": 0,
                "json": {
                    "status": "completed",
                    "title": "润色定稿",
                    "article_markdown": "润色长文\n" * 800,
                    "alternate_titles": [],
                    "summary": "",
                    "notes": "",
                },
            }
            with patch.object(self.module, "TOOL_GLUE_WECHAT_SKILL_PATH", skill_path):
                with patch.object(self.module, "tool_glue_resolve_codex_bin", return_value=Path("/tmp/codex")):
                    with patch.object(self.module, "tool_glue_find_workspace_claude_md", return_value=None):
                        with patch.object(self.module, "tool_glue_run_codex_exec_json", return_value=exec_payload):
                            stage = self.module.run_tool_glue_wechat_polish_stage(
                                stage_name="polish",
                                prompt_text="请润色这篇文章",
                            )

        self.assertEqual(stage["status"], "completed")
        self.assertEqual(stage["claude_style_source"], "skill_default")

    def test_run_tool_glue_wechat_polish_stage_handles_schema_parse_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            skill_path = Path(tempdir) / "wechat-skill.md"
            skill_path.write_text("skill-body\n", encoding="utf-8")
            with patch.object(self.module, "TOOL_GLUE_WECHAT_SKILL_PATH", skill_path):
                with patch.object(self.module, "tool_glue_resolve_codex_bin", return_value=Path("/tmp/codex")):
                    with patch.object(self.module, "tool_glue_find_workspace_claude_md", return_value=None):
                        with patch.object(self.module, "tool_glue_run_codex_exec_json", return_value={"returncode": 0, "stdout": "", "stderr": ""}):
                            stage = self.module.run_tool_glue_wechat_polish_stage(
                                stage_name="polish",
                                prompt_text="请润色这篇文章",
                            )

        self.assertEqual(stage["status"], "failed_partial")
        self.assertEqual(stage["blocking_reason"], "wechat_polish_parse_failed")

    def test_run_tool_glue_wechat_polish_stage_rejects_short_output(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            skill_path = Path(tempdir) / "wechat-skill.md"
            skill_path.write_text("skill-body\n", encoding="utf-8")
            exec_payload = {
                "returncode": 0,
                "json": {
                    "status": "completed",
                    "title": "太短了",
                    "article_markdown": "短文",
                    "alternate_titles": [],
                    "summary": "",
                    "notes": "",
                },
            }
            with patch.object(self.module, "TOOL_GLUE_WECHAT_SKILL_PATH", skill_path):
                with patch.object(self.module, "tool_glue_resolve_codex_bin", return_value=Path("/tmp/codex")):
                    with patch.object(self.module, "tool_glue_find_workspace_claude_md", return_value=None):
                        with patch.object(self.module, "tool_glue_run_codex_exec_json", return_value=exec_payload):
                            stage = self.module.run_tool_glue_wechat_polish_stage(
                                stage_name="polish",
                                prompt_text="请润色这篇文章",
                            )

        self.assertEqual(stage["status"], "failed_partial")
        self.assertEqual(stage["blocking_reason"], "wechat_polish_output_too_short")

    def test_run_feishu_reader_extract_handles_auth_required_and_empty_text(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir)
            auth_stdout = json.dumps({"status": "auth_required", "text": "", "title": "需要登录"}, ensure_ascii=False)
            empty_stdout = json.dumps({"status": "ok", "text": "", "title": "空文档"}, ensure_ascii=False)
            ok_stdout = json.dumps({"status": "ok", "text": "逐字稿内容" * 120, "title": "正常文档"}, ensure_ascii=False)

            with patch.object(self.module, "tool_glue_runtime_ready", return_value={"node_available": True, "feishu_reader_script_exists": True, "npx_available": True, "playwright_wrapper_exists": True}):
                with patch.object(self.module, "run_shell_command_capture", return_value={"returncode": 2, "stdout": auth_stdout, "stderr": "", "timed_out": False}):
                    auth_stage = self.module.run_feishu_reader_extract(feishu_url="https://example.test/docx/1", run_dir=run_dir)
                with patch.object(self.module, "run_shell_command_capture", return_value={"returncode": 0, "stdout": empty_stdout, "stderr": "", "timed_out": False}):
                    empty_stage = self.module.run_feishu_reader_extract(feishu_url="https://example.test/docx/2", run_dir=run_dir)
                with patch.object(self.module, "run_shell_command_capture", return_value={"returncode": 0, "stdout": ok_stdout, "stderr": "", "timed_out": False}):
                    ok_stage = self.module.run_feishu_reader_extract(feishu_url="https://example.test/docx/3", run_dir=run_dir)

        self.assertEqual(auth_stage["status"], "blocked_needs_user")
        self.assertEqual(empty_stage["status"], "blocked_needs_user")
        self.assertTrue(ok_stage["success"])
        self.assertEqual(ok_stage["status"], "completed")

    def test_run_feishu_reader_extract_recovers_false_auth_when_document_text_is_present(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir)
            recovered_stdout = json.dumps(
                {
                    "status": "auth_required",
                    "title": "北京奥德修斯教育科技有限公司",
                    "canonical_url": "https://h52xu4gwob.feishu.cn/docx/VZ2IdYDxZoeBoIxpbdscdHU9nSb",
                    "text": "原力觉醒：AI时代信息处理与自我认知讨论\n" + ("逐字稿内容" * 120),
                    "notes": {"profile_dir": "/tmp/feishu-reader"},
                },
                ensure_ascii=False,
            )

            with patch.object(self.module, "tool_glue_runtime_ready", return_value={"node_available": True, "feishu_reader_script_exists": True, "npx_available": True, "playwright_wrapper_exists": True}):
                with patch.object(self.module, "run_shell_command_capture", return_value={"returncode": 2, "stdout": recovered_stdout, "stderr": "", "timed_out": False}):
                    stage = self.module.run_feishu_reader_extract(feishu_url="https://h52xu4gwob.feishu.cn/docx/VZ2IdYDxZoeBoIxpbdscdHU9nSb", run_dir=run_dir)

        self.assertEqual(stage["status"], "completed")
        self.assertTrue(stage["success"])
        self.assertEqual(stage["extract_payload"]["status"], "ok")
        self.assertTrue(stage["extract_payload"]["notes"]["status_recovered_by_tool_glue"])

    def test_run_feishu_reader_extract_uses_headed_dedicated_profile_on_auth(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir)
            first_stdout = json.dumps({"status": "auth_required", "text": "", "title": "需要登录"}, ensure_ascii=False)
            headed_stdout = json.dumps({"status": "ok", "text": "逐字稿内容" * 120, "title": "正常文档"}, ensure_ascii=False)
            calls: list[list[str]] = []

            def fake_shell(command, *, cwd=None, timeout=20, input_text=None):
                calls.append(command)
                stdout = first_stdout if len(calls) == 1 else headed_stdout
                return {"returncode": 2 if len(calls) == 1 else 0, "stdout": stdout, "stderr": "", "timed_out": False}

            with patch.object(self.module, "tool_glue_runtime_ready", return_value={"node_available": True, "feishu_reader_script_exists": True, "npx_available": True, "playwright_wrapper_exists": True}):
                with patch.object(self.module, "run_shell_command_capture", side_effect=fake_shell):
                    stage = self.module.run_feishu_reader_extract(feishu_url="https://example.test/docx/retry", run_dir=run_dir)

        self.assertEqual(len(calls), 2)
        self.assertNotIn("--reuse-chrome-profile", calls[0])
        self.assertIn("--headed", calls[1])
        self.assertNotIn("--reuse-chrome-profile", calls[1])
        self.assertEqual(stage["status"], "completed")
        self.assertTrue(stage["success"])
        self.assertTrue(stage["visibility"]["actual_visible"])
        self.assertEqual(stage["fallback_attempts"][0]["strategy"], "dedicated_profile_headed_login")

    def test_run_feishu_reader_extract_retries_with_chrome_profile_after_headed_login_still_needs_auth(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir)
            auth_stdout = json.dumps({"status": "auth_required", "text": "", "title": "需要登录"}, ensure_ascii=False)
            fallback_stdout = json.dumps({"status": "ok", "text": "逐字稿内容" * 120, "title": "正常文档"}, ensure_ascii=False)
            calls: list[list[str]] = []

            def fake_shell(command, *, cwd=None, timeout=20, input_text=None):
                calls.append(command)
                if len(calls) <= 2:
                    return {"returncode": 2, "stdout": auth_stdout, "stderr": "", "timed_out": False}
                return {"returncode": 0, "stdout": fallback_stdout, "stderr": "", "timed_out": False}

            with patch.object(self.module, "tool_glue_runtime_ready", return_value={"node_available": True, "feishu_reader_script_exists": True, "npx_available": True, "playwright_wrapper_exists": True}):
                with patch.object(self.module, "run_shell_command_capture", side_effect=fake_shell):
                    stage = self.module.run_feishu_reader_extract(feishu_url="https://example.test/docx/retry", run_dir=run_dir)

        self.assertEqual(len(calls), 3)
        self.assertNotIn("--reuse-chrome-profile", calls[0])
        self.assertIn("--headed", calls[1])
        self.assertIn("--reuse-chrome-profile", calls[2])
        self.assertEqual(stage["status"], "completed")
        self.assertTrue(stage["success"])

    def test_run_feishu_reader_extract_uses_profile_snapshot_when_live_chrome_is_locked(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir)
            first_stdout = json.dumps({"status": "auth_required", "text": "", "title": "需要登录"}, ensure_ascii=False)
            snapshot_stdout = json.dumps({"status": "ok", "text": "逐字稿内容" * 120, "title": "正常文档"}, ensure_ascii=False)
            calls: list[list[str]] = []

            def fake_shell(command, *, cwd=None, timeout=20, input_text=None):
                calls.append(command)
                if len(calls) == 1:
                    return {"returncode": 2, "stdout": first_stdout, "stderr": "", "timed_out": False}
                if len(calls) == 2:
                    return {"returncode": 2, "stdout": first_stdout, "stderr": "", "timed_out": False}
                if len(calls) == 3:
                    return {
                        "returncode": 1,
                        "stdout": "",
                        "stderr": "Failed to create a ProcessSingleton for your profile directory.",
                        "timed_out": False,
                    }
                return {"returncode": 0, "stdout": snapshot_stdout, "stderr": "", "timed_out": False}

            with patch.object(self.module, "tool_glue_runtime_ready", return_value={"node_available": True, "feishu_reader_script_exists": True, "npx_available": True, "playwright_wrapper_exists": True}):
                with patch.object(self.module, "run_shell_command_capture", side_effect=fake_shell):
                    with patch.object(
                        self.module,
                        "tool_glue_create_chrome_profile_snapshot",
                        return_value={"ok": True, "status": "completed", "snapshot_dir": str(run_dir / "playwright" / "snapshot")},
                    ):
                        stage = self.module.run_feishu_reader_extract(feishu_url="https://example.test/docx/retry", run_dir=run_dir)

        self.assertEqual(len(calls), 4)
        self.assertNotIn("--reuse-chrome-profile", calls[0])
        self.assertIn("--headed", calls[1])
        self.assertIn("--reuse-chrome-profile", calls[2])
        self.assertIn("--reuse-chrome-profile", calls[3])
        self.assertIn("--profile-dir", calls[3])
        self.assertEqual(stage["status"], "completed")
        self.assertTrue(stage["success"])
        self.assertEqual(stage["fallback_attempts"][-1]["strategy"], "chrome_profile_snapshot_extract")

    def test_run_feishu_reader_extract_uses_live_chrome_tab_after_snapshot_still_needs_auth(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir)
            first_stdout = json.dumps({"status": "auth_required", "text": "", "title": "需要登录"}, ensure_ascii=False)
            snapshot_auth_stdout = json.dumps({"status": "auth_required", "text": "扫码登录", "title": "需要登录"}, ensure_ascii=False)
            calls: list[list[str]] = []

            def fake_shell(command, *, cwd=None, timeout=20, input_text=None):
                calls.append(command)
                if len(calls) == 1:
                    return {"returncode": 2, "stdout": first_stdout, "stderr": "", "timed_out": False}
                if len(calls) == 2:
                    return {"returncode": 2, "stdout": first_stdout, "stderr": "", "timed_out": False}
                if len(calls) == 3:
                    return {
                        "returncode": 1,
                        "stdout": "",
                        "stderr": "Failed to create a ProcessSingleton for your profile directory.",
                        "timed_out": False,
                    }
                return {"returncode": 2, "stdout": snapshot_auth_stdout, "stderr": "", "timed_out": False}

            live_payload = {
                "status": "ok",
                "title": "飞书妙计主题",
                "canonical_url": "https://example.test/docx/live",
                "text": "逐字稿内容" * 120,
                "auth_mode_used": "live_chrome_tab",
            }
            with patch.object(self.module, "tool_glue_runtime_ready", return_value={"node_available": True, "feishu_reader_script_exists": True, "npx_available": True, "playwright_wrapper_exists": True}):
                with patch.object(self.module, "run_shell_command_capture", side_effect=fake_shell):
                    with patch.object(
                        self.module,
                        "tool_glue_create_chrome_profile_snapshot",
                        return_value={"ok": True, "status": "completed", "snapshot_dir": str(run_dir / "playwright" / "snapshot")},
                    ):
                        with patch.object(
                            self.module,
                            "tool_glue_extract_feishu_from_live_chrome",
                            return_value={"ok": True, "command_result": {"returncode": 0}, "payload": live_payload},
                        ):
                            stage = self.module.run_feishu_reader_extract(feishu_url="https://example.test/docx/retry", run_dir=run_dir)

        self.assertEqual(len(calls), 4)
        self.assertEqual(stage["status"], "completed")
        self.assertTrue(stage["success"])
        self.assertEqual(stage["extract_payload"]["auth_mode_used"], "live_chrome_tab")
        self.assertEqual(stage["fallback_attempts"][-1]["strategy"], "live_chrome_tab_extract")

    def test_command_tool_glue_benchmark_writes_success_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            args = types.SimpleNamespace(
                feishu_url="https://example.test/docx/ok",
                polish_mode="wechat_skill_local",
                claudy_match="CLAUDY",
                doubao_url="https://example.test/doubao",
                claudy_url="",
                run_id="adagj-tool-glue-success",
                created_at="2026-03-14T21:00:00+08:00",
            )

            feishu = self.module.tool_glue_stage_record(
                name="feishu",
                status="completed",
                success=True,
                output_text="逐字稿内容" * 300,
                target_url=args.feishu_url,
            )
            doubao = self.module.tool_glue_stage_record(
                name="doubao",
                status="completed",
                success=True,
                input_chars=5000,
                output_text="豆包文章" * 1200,
                target_url=args.doubao_url,
                prompt_text=self.module.build_tool_glue_prompt(feishu["output_text"], mode="doubao"),
            )
            polish = self.module.tool_glue_stage_record(
                name="polish",
                status="completed",
                success=True,
                input_chars=12000,
                output_text="公众号定稿" * 1300,
                target_url="local_codex_exec::wechat-article-writer",
                prompt_text=self.module.build_tool_glue_prompt(doubao["output_text"], mode="polish"),
            )
            baseline = self.module.tool_glue_stage_record(
                name="baseline_direct_polish",
                status="completed",
                success=True,
                input_chars=4000,
                output_text="直接基线稿" * 900,
                target_url="local_codex_exec::wechat-article-writer",
                prompt_text=self.module.build_tool_glue_prompt(feishu["output_text"], mode="polish"),
            )

            def fake_browser_stage(**kwargs):
                stage_name = kwargs["stage_name"]
                if stage_name == "doubao":
                    return doubao
                raise AssertionError(f"unexpected stage: {stage_name}")

            with patch.multiple(self.module, RUNS_ROOT=runs_root):
                with patch.object(self.module, "run_feishu_reader_extract", return_value=feishu):
                    with patch.object(self.module, "run_tool_glue_browser_stage", side_effect=fake_browser_stage):
                        with patch.object(self.module, "run_tool_glue_wechat_polish_stage", side_effect=[polish, baseline]):
                            exit_code = self.module.command_tool_glue_benchmark(args)

            self.assertEqual(exit_code, 0)
            run_dir = runs_root / "2026-03-14" / args.run_id
            for name in self.module.tool_glue_required_files("wechat_skill_local"):
                self.assertTrue((run_dir / name).exists(), name)

            route_payload = json.loads((run_dir / "route.json").read_text(encoding="utf-8"))
            self.assertEqual(route_payload["closure_state"], "completed")
            self.assertEqual(route_payload["mvp_verdict"], "keep_and_harden")
            self.assertEqual(route_payload["polish_mode"], "wechat_skill_local")
            self.assertEqual(route_payload["resolved_claudy_url"], "")
            self.assertEqual(route_payload["remote_visibility_defaults"]["priority"], "stability_first")
            self.assertIn("why_not_visible", route_payload)

            verdict = json.loads((run_dir / "mvp-verdict.json").read_text(encoding="utf-8"))
            self.assertEqual(verdict["verdict"], "keep_and_harden")
            scorecard = json.loads((run_dir / "glue-scorecard.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(scorecard["composite_score"], 75)
            self.assertIn("polish", scorecard["stages"])
            worklog = (run_dir / "worklog.md").read_text(encoding="utf-8")
            self.assertIn("Execution Visibility", worklog)
            self.assertIn("why_not_visible", worklog)

    def test_command_tool_glue_benchmark_writes_blocked_bundle_when_feishu_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            args = types.SimpleNamespace(
                feishu_url="https://example.test/docx/blocked",
                polish_mode="wechat_skill_local",
                claudy_match="CLAUDY",
                doubao_url="https://example.test/doubao",
                claudy_url="",
                run_id="adagj-tool-glue-blocked",
                created_at="2026-03-14T22:00:00+08:00",
            )
            feishu = self.module.tool_glue_stage_record(
                name="feishu",
                status="blocked_needs_user",
                success=False,
                blocking_reason="auth_required",
                target_url=args.feishu_url,
            )

            with patch.multiple(self.module, RUNS_ROOT=runs_root):
                with patch.object(self.module, "run_feishu_reader_extract", return_value=feishu):
                    with patch.object(self.module, "run_tool_glue_browser_stage") as browser_stage:
                        with patch.object(self.module, "run_tool_glue_wechat_polish_stage") as polish_stage:
                            exit_code = self.module.command_tool_glue_benchmark(args)

            self.assertEqual(exit_code, 0)
            browser_stage.assert_not_called()
            polish_stage.assert_not_called()
            run_dir = runs_root / "2026-03-14" / args.run_id
            for name in self.module.tool_glue_required_files("wechat_skill_local"):
                self.assertTrue((run_dir / name).exists(), name)

            verdict = json.loads((run_dir / "mvp-verdict.json").read_text(encoding="utf-8"))
            self.assertEqual(verdict["closure_state"], "blocked_needs_user")
            polish_markdown = (run_dir / "polish-article.md").read_text(encoding="utf-8")
            self.assertIn("No content captured", polish_markdown)
            raw_json = json.loads((run_dir / "transcript-source.raw.json").read_text(encoding="utf-8"))
            self.assertEqual(raw_json["status"], "blocked_needs_user")
            doubao_request = json.loads((run_dir / "doubao-request.json").read_text(encoding="utf-8"))
            self.assertEqual(doubao_request["status"], "blocked_needs_user")
            polish_request = json.loads((run_dir / "polish-request.json").read_text(encoding="utf-8"))
            self.assertEqual(polish_request["status"], "blocked_needs_user")


if __name__ == "__main__":
    unittest.main()
