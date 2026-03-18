from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


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


class AutoClawSelfUseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPT_ROOT))
        cls.ai_da_guan_jia = load_module("test_ai_da_guan_jia_autoclaw_self_use", SCRIPT_ROOT / "ai_da_guan_jia.py")

    def test_prepare_autoclaw_self_use_writes_patch_tracker_and_diagnosis(self) -> None:
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

            write_skill(packaged_root, "autoglm-deepresearch", "name: autoglm-deepresearch\ndescription: deep research")
            write_skill(packaged_root, "feishu-doc-1.2.7", "name: feishu-doc\ndescription: Feishu document read and write")
            write_skill(packaged_root, "skill-creator-0.1.0", "name: skill-creator\ndescription: skill creation")
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
                                "skills": [{"name": "autoglm-deepresearch"}, {"name": "github"}],
                                "resolvedSkills": [
                                    {
                                        "name": "autoglm-deepresearch",
                                        "filePath": str(packaged_root / "autoglm-deepresearch" / "SKILL.md"),
                                        "baseDir": str(packaged_root / "autoglm-deepresearch"),
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
                start_date="2026-03-12",
                apply_config=False,
            )
            original_runtime_root = self.ai_da_guan_jia.AUTOCLAW_RUNTIME_SKILLS_ROOT
            try:
                self.ai_da_guan_jia.AUTOCLAW_RUNTIME_SKILLS_ROOT = runtime_root
                exit_code = self.ai_da_guan_jia.command_prepare_autoclaw_self_use(args)
            finally:
                self.ai_da_guan_jia.AUTOCLAW_RUNTIME_SKILLS_ROOT = original_runtime_root

            self.assertEqual(exit_code, 0)
            profile = json.loads((output_dir / "profile.json").read_text(encoding="utf-8"))
            patch = json.loads((output_dir / "skills-config.patch.json").read_text(encoding="utf-8"))
            diagnosis = json.loads((output_dir / "browser-agent-diagnosis.json").read_text(encoding="utf-8"))
            tracker = json.loads((output_dir / "tracker.json").read_text(encoding="utf-8"))
            self.assertTrue((output_dir / "report.md").exists())
            self.assertEqual(patch["skills"]["entries"]["autoglm-deepresearch"]["enabled"], True)
            self.assertEqual(patch["skills"]["entries"]["feishu-doc"]["enabled"], False)
            self.assertEqual(patch["skills"]["entries"]["skill-creator"]["enabled"], False)
            self.assertEqual(diagnosis["status"], "blocked_binary_signature")
            self.assertEqual(len(tracker["days"]), 7)
            self.assertEqual(profile["mode"], "strong_convergence")

    def test_prepare_autoclaw_self_use_can_apply_config_patch(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            temp_root = Path(tempdir)
            app_root = temp_root / "AutoClaw.app" / "Contents" / "Resources"
            packaged_root = app_root / "skills"
            write_skill(packaged_root, "autoglm-websearch", "name: autoglm-websearch\ndescription: web search")
            config_path = temp_root / "openclaw.json"
            config_path.write_text(json.dumps({"skills": {"load": {"extraDirs": []}}}, ensure_ascii=False, indent=2), encoding="utf-8")
            sessions_root = temp_root / "sessions"
            sessions_root.mkdir(parents=True, exist_ok=True)
            sessions_path = sessions_root / "sessions.json"
            sessions_path.write_text(
                json.dumps(
                    {
                        "agent:main:preset_1": {
                            "updatedAt": 1,
                            "skillsSnapshot": {
                                "skills": [{"name": "autoglm-websearch"}],
                                "resolvedSkills": [
                                    {
                                        "name": "autoglm-websearch",
                                        "filePath": str(packaged_root / "autoglm-websearch" / "SKILL.md"),
                                        "baseDir": str(packaged_root / "autoglm-websearch"),
                                        "source": "agents-skills-personal",
                                    }
                                ],
                            },
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            output_dir = temp_root / "output"
            args = self.ai_da_guan_jia.argparse.Namespace(
                config=str(config_path),
                sessions=str(sessions_path),
                app_resources=str(app_root),
                output_dir=str(output_dir),
                start_date="2026-03-12",
                apply_config=True,
            )
            exit_code = self.ai_da_guan_jia.command_prepare_autoclaw_self_use(args)
            self.assertEqual(exit_code, 0)
            updated = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(updated["skills"]["entries"]["autoglm-websearch"]["enabled"], True)
            apply_result = json.loads((output_dir / "apply-result.json").read_text(encoding="utf-8"))
            self.assertTrue(Path(apply_result["backup_path"]).exists())

    def test_record_and_review_autoclaw_self_use_tracker(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            temp_root = Path(tempdir)
            tracker_path = temp_root / "tracker.json"
            tracker = self.ai_da_guan_jia.build_autoclaw_self_use_tracker("2026-03-12")
            self.ai_da_guan_jia.write_json(tracker_path, tracker)

            record_1 = self.ai_da_guan_jia.argparse.Namespace(
                tracker=str(tracker_path),
                day=1,
                date=None,
                active_calls=3,
                misfires=1,
                missed_calls=1,
                skill_conflicts=3,
                chain_outcome="same",
                scenario=["给我接个任务"],
                notes="day1",
            )
            record_5 = self.ai_da_guan_jia.argparse.Namespace(
                tracker=str(tracker_path),
                day=5,
                date=None,
                active_calls=4,
                misfires=1,
                missed_calls=0,
                skill_conflicts=1,
                chain_outcome="shorter",
                scenario=["帮我查资料"],
                notes="day5",
            )
            record_6 = self.ai_da_guan_jia.argparse.Namespace(
                tracker=str(tracker_path),
                day=6,
                date=None,
                active_calls=4,
                misfires=1,
                missed_calls=0,
                skill_conflicts=1,
                chain_outcome="shorter",
                scenario=["把这事闭环"],
                notes="day6",
            )
            record_7 = self.ai_da_guan_jia.argparse.Namespace(
                tracker=str(tracker_path),
                day=7,
                date=None,
                active_calls=5,
                misfires=1,
                missed_calls=0,
                skill_conflicts=0,
                chain_outcome="shorter",
                scenario=["这件事该不该做"],
                notes="day7",
            )
            self.ai_da_guan_jia.command_record_autoclaw_self_use_day(record_1)
            self.ai_da_guan_jia.command_record_autoclaw_self_use_day(record_5)
            self.ai_da_guan_jia.command_record_autoclaw_self_use_day(record_6)
            self.ai_da_guan_jia.command_record_autoclaw_self_use_day(record_7)

            review_args = self.ai_da_guan_jia.argparse.Namespace(tracker=str(tracker_path))
            exit_code = self.ai_da_guan_jia.command_review_autoclaw_self_use(review_args)
            review = json.loads((temp_root / "review.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertTrue(review["passed"])
            self.assertEqual(review["shorter_days"], 3)


if __name__ == "__main__":
    unittest.main()
