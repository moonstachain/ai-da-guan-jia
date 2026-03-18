from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


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


def write_skill(root: Path, name: str, frontmatter: str, body: str = "") -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    text = f"---\n{frontmatter}\n---\n\n{body}\n"
    (skill_dir / "SKILL.md").write_text(text, encoding="utf-8")
    return skill_dir / "SKILL.md"


class AutoClawFrameworkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPT_ROOT))
        cls.ai_da_guan_jia = load_module("test_ai_da_guan_jia_autoclaw_framework", SCRIPT_ROOT / "ai_da_guan_jia.py")

    def test_build_autoclaw_frontdesk_framework_has_expected_split(self) -> None:
        audit = {
            "summary": {
                "source_entries_total": 215,
                "exact_unique_total": 108,
                "family_unique_total": 101,
                "mirror_duplicate_exact_total": 53,
                "mirror_duplicate_hash_identical_total": 53,
            },
            "runtime_snapshot": {"resolved_count": 53},
        }
        profile = {
            "keep_families": [{"family_key": "autoglm-browser-agent"}, {"family_key": "github"}],
            "conditional_families": [{"family_key": "feishu-doc"}],
        }
        diagnosis = {
            "status": "blocked_binary_signature",
            "reason": "Browser agent is blocked by a Python shared-library signature or compatibility error.",
        }
        framework = self.ai_da_guan_jia.build_autoclaw_frontdesk_framework(
            audit=audit,
            profile=profile,
            diagnosis=diagnosis,
        )
        self.assertIn("全局最优判断", framework["judgments"])
        self.assertEqual(framework["comparison_rows"][0]["dimension"], "入口形态")
        role_map = {row["actor"]: row for row in framework["role_split"]}
        self.assertIn("个人前台总控壳", role_map["AutoClaw"]["positioning"])
        self.assertIn("协作和结果分发表面", role_map["飞书机器人"]["positioning"])
        self.assertIn("治理层和总控层", role_map["AI大管家"]["positioning"])
        self.assertIn("blocked_binary_signature", framework["current_machine_assessment"]["browser_status"])

    def test_command_frame_autoclaw_frontends_writes_framework_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            temp_root = Path(tempdir)
            app_root = temp_root / "AutoClaw.app" / "Contents" / "Resources"
            packaged_root = app_root / "skills"
            gateway_root = app_root / "gateway" / "openclaw" / "skills"
            runtime_root = temp_root / ".agents" / "skills"
            sessions_root = temp_root / "sessions"
            sessions_root.mkdir(parents=True, exist_ok=True)
            browser_skill_dir = runtime_root / "autoglm-browser-agent" / "dist"
            browser_skill_dir.mkdir(parents=True, exist_ok=True)
            (browser_skill_dir / "relay").write_text("", encoding="utf-8")
            (browser_skill_dir / "mcp_server").write_text("", encoding="utf-8")

            write_skill(packaged_root, "autoglm-websearch", "name: autoglm-websearch\ndescription: web search")
            write_skill(packaged_root, "feishu-doc-1.2.7", "name: feishu-doc\ndescription: Feishu document read and write")
            write_skill(gateway_root, "github", "name: github\ndescription: github operations")

            config_path = temp_root / "openclaw.json"
            config_path.write_text(json.dumps({"skills": {"load": {"extraDirs": []}}}, ensure_ascii=False), encoding="utf-8")
            sessions_path = sessions_root / "sessions.json"
            sessions_path.write_text(
                json.dumps(
                    {
                        "agent:main:preset_1": {
                            "updatedAt": 100,
                            "skillsSnapshot": {
                                "skills": [{"name": "autoglm-websearch"}, {"name": "github"}],
                                "resolvedSkills": [
                                    {
                                        "name": "autoglm-websearch",
                                        "filePath": str(packaged_root / "autoglm-websearch" / "SKILL.md"),
                                        "baseDir": str(packaged_root / "autoglm-websearch"),
                                        "source": "agents-skills-personal",
                                    },
                                    {
                                        "name": "github",
                                        "filePath": str(gateway_root / "github" / "SKILL.md"),
                                        "baseDir": str(gateway_root / "github"),
                                        "source": "openclaw-bundled",
                                    },
                                ],
                            },
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (sessions_root / "broken-browser.jsonl").write_text(
                '{"timestamp":"2026-03-12T01:00:00.000Z","message":{"content":[{"type":"text","text":"Failed to load Python shared library"}]}}\n',
                encoding="utf-8",
            )

            output_dir = temp_root / "output"
            args = self.ai_da_guan_jia.argparse.Namespace(
                config=str(config_path),
                sessions=str(sessions_path),
                app_resources=str(app_root),
                output_dir=str(output_dir),
                show_windows=False,
            )
            original_runtime_root = self.ai_da_guan_jia.AUTOCLAW_RUNTIME_SKILLS_ROOT
            try:
                self.ai_da_guan_jia.AUTOCLAW_RUNTIME_SKILLS_ROOT = runtime_root
                exit_code = self.ai_da_guan_jia.command_frame_autoclaw_frontends(args)
            finally:
                self.ai_da_guan_jia.AUTOCLAW_RUNTIME_SKILLS_ROOT = original_runtime_root

            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "framework.json").exists())
            self.assertTrue((output_dir / "comparison-table.json").exists())
            self.assertTrue((output_dir / "role-split.json").exists())
            self.assertTrue((output_dir / "report.md").exists())
            self.assertTrue((output_dir / "browser-agent-diagnosis.json").exists())
            self.assertTrue((output_dir / "closure-status.json").exists())
            report_text = (output_dir / "report.md").read_text(encoding="utf-8")
            self.assertIn("AutoClaw / 飞书机器人 / AI大管家 统筹框架", report_text)
            self.assertIn("四方分工", report_text)
            self.assertIn("前台使用原则", report_text)

    def test_update_visible_stage_writes_artifacts_without_gui(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir)
            result = self.ai_da_guan_jia.update_visible_stage(
                enabled=False,
                run_dir=run_dir,
                task_kind="autoclaw_frontdesk_framework",
                task_title="质朴龙虾评估",
                stage="start",
                status="running",
                last_action="开始执行",
                needs_user=False,
                summary="正在生成报告",
                evidence_ref="/tmp/report.md",
            )
            self.assertEqual(result["window_result"]["status"], "disabled")
            payload = json.loads((run_dir / "window-state.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["task_title"], "质朴龙虾评估")
            self.assertEqual(payload["stage"], "start")
            self.assertTrue((run_dir / "window-state.html").exists())

    def test_open_status_window_html_prefers_chrome_app_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            html_path = root / "window-state.html"
            html_path.write_text("<html><body>ok</body></html>", encoding="utf-8")
            chrome_binary = root / "Google Chrome"
            chrome_binary.write_text("", encoding="utf-8")

            with mock.patch.object(self.ai_da_guan_jia, "CHROME_STATUS_WINDOW_BINARY", chrome_binary):
                with mock.patch.object(self.ai_da_guan_jia.subprocess, "Popen") as popen_mock:
                    popen_mock.return_value.pid = 4242
                    result = self.ai_da_guan_jia.open_status_window_html(
                        html_path,
                        title="质朴龙虾评估",
                        slot="left",
                    )

            self.assertEqual(result["status"], "status_window_opened")
            self.assertEqual(result["mode"], "chrome_app_window")
            self.assertEqual(result["command"]["pid"], 4242)
            launch_command = result["command"]["command"]
            self.assertIn("--app=file://", " ".join(launch_command))
            self.assertIn("--window-position=80,110", launch_command)


if __name__ == "__main__":
    unittest.main()
