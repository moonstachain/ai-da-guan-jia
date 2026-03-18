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


class AutoClawSkillAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPT_ROOT))
        cls.ai_da_guan_jia = load_module("test_ai_da_guan_jia_autoclaw", SCRIPT_ROOT / "ai_da_guan_jia.py")

    def test_normalize_family_key_keeps_non_version_suffix(self) -> None:
        self.assertEqual(self.ai_da_guan_jia.normalize_autoclaw_family_key("skill-creator-0.1.0"), "skill-creator")
        self.assertEqual(self.ai_da_guan_jia.normalize_autoclaw_family_key("frontend-design-3-0.1.0"), "frontend-design-3")
        self.assertEqual(self.ai_da_guan_jia.normalize_autoclaw_family_key("feishu-perm"), "feishu-perm")

    def test_build_autoclaw_skill_audit_detects_mirrors_and_recommendations(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            temp_root = Path(tempdir)
            app_root = temp_root / "AutoClaw.app" / "Contents" / "Resources"
            packaged_root = app_root / "skills"
            gateway_root = app_root / "gateway" / "openclaw" / "skills"
            feishu_root = app_root / "gateway" / "openclaw" / "extensions" / "feishu" / "skills"
            extra_1 = temp_root / "extra-1"
            extra_2 = temp_root / "extra-2"

            write_skill(
                packaged_root,
                "1password-1.0.1",
                'name: 1password\ndescription: password helper\nmetadata:\n  {"openclaw":{"requires":{"bins":["op"]}}}',
            )
            write_skill(packaged_root, "feishu-doc-1.2.7", "name: feishu-doc\ndescription: Feishu document read and write")
            write_skill(gateway_root, "1password", "name: 1password\ndescription: gateway 1password")
            write_skill(gateway_root, "session-logs", "name: session-logs\ndescription: session memory and reflection")
            write_skill(feishu_root, "feishu-doc", "name: feishu-doc\ndescription: Feishu document extension")
            write_skill(feishu_root, "feishu-drive", "name: feishu-drive\ndescription: Feishu drive extension")
            write_skill(
                extra_1,
                "1password-1.0.1",
                'name: 1password\ndescription: password helper\nmetadata:\n  {"openclaw":{"requires":{"bins":["op"]}}}',
            )
            write_skill(extra_1, "find-skills", "name: find-skills\ndescription: skill discovery and routing")
            write_skill(
                extra_2,
                "1password-1.0.1",
                'name: 1password\ndescription: password helper\nmetadata:\n  {"openclaw":{"requires":{"bins":["op"]}}}',
            )
            write_skill(extra_2, "find-skills", "name: find-skills\ndescription: skill discovery and routing")

            config_path = temp_root / "openclaw.json"
            config_path.write_text(
                json.dumps(
                    {
                        "skills": {
                            "load": {
                                "extraDirs": [
                                    str(extra_1),
                                    str(extra_2),
                                ]
                            }
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            sessions_path = temp_root / "sessions.json"
            sessions_path.write_text(
                json.dumps(
                    {
                        "agent:main:preset_1": {
                            "updatedAt": 100,
                            "skillsSnapshot": {
                                "skills": [{"name": "1password"}, {"name": "feishu-drive"}],
                                "resolvedSkills": [
                                    {
                                        "name": "1password",
                                        "filePath": str(extra_1 / "1password-1.0.1" / "SKILL.md"),
                                        "baseDir": str(extra_1 / "1password-1.0.1"),
                                        "source": "agents-skills-personal",
                                    },
                                    {
                                        "name": "feishu-drive",
                                        "filePath": str(feishu_root / "feishu-drive" / "SKILL.md"),
                                        "baseDir": str(feishu_root / "feishu-drive"),
                                        "source": "openclaw-extra",
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

            audit = self.ai_da_guan_jia.build_autoclaw_skill_audit(
                config_path=config_path,
                session_index_path=sessions_path,
                app_resources_root=app_root,
            )
            self.assertEqual(audit["summary"]["source_entries_total"], 10)
            self.assertEqual(audit["summary"]["exact_unique_total"], 7)
            self.assertEqual(audit["summary"]["family_unique_total"], 5)
            self.assertEqual(audit["summary"]["mirror_duplicate_exact_total"], 2)
            self.assertEqual(audit["runtime_snapshot"]["resolved_count"], 2)

            profile_map = {item["family_key"]: item for item in audit["family_profiles"]}
            self.assertEqual(profile_map["1password"]["recommendation"], "条件启用")
            self.assertEqual(profile_map["session-logs"]["recommendation"], "默认禁用")
            self.assertEqual(profile_map["feishu-drive"]["recommendation"], "条件启用")
            self.assertIn(profile_map["1password"]["dependency_bucket"], {"缺 bin", "无依赖可直接用"})

    def test_command_audit_autoclaw_skills_writes_report_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            temp_root = Path(tempdir)
            app_root = temp_root / "AutoClaw.app" / "Contents" / "Resources"
            write_skill(app_root / "skills", "autoglm-websearch", "name: autoglm-websearch\ndescription: web search")
            config_path = temp_root / "openclaw.json"
            config_path.write_text(json.dumps({"skills": {"load": {"extraDirs": []}}}, ensure_ascii=False), encoding="utf-8")
            sessions_path = temp_root / "sessions.json"
            sessions_path.write_text(
                json.dumps(
                    {
                        "agent:main:preset_1": {
                            "updatedAt": 100,
                            "skillsSnapshot": {
                                "skills": [{"name": "autoglm-websearch"}],
                                "resolvedSkills": [
                                    {
                                        "name": "autoglm-websearch",
                                        "filePath": str(app_root / "skills" / "autoglm-websearch" / "SKILL.md"),
                                        "baseDir": str(app_root / "skills" / "autoglm-websearch"),
                                        "source": "agents-skills-personal",
                                    }
                                ],
                            },
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            output_dir = temp_root / "output"
            args = self.ai_da_guan_jia.argparse.Namespace(
                config=str(config_path),
                sessions=str(sessions_path),
                app_resources=str(app_root),
                output_dir=str(output_dir),
            )
            exit_code = self.ai_da_guan_jia.command_audit_autoclaw_skills(args)
            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "audit.json").exists())
            self.assertTrue((output_dir / "family-profiles.json").exists())
            self.assertTrue((output_dir / "report.md").exists())
            report_text = (output_dir / "report.md").read_text(encoding="utf-8")
            self.assertIn("AutoClaw Skill 治理审计报告", report_text)
            self.assertIn("autoglm-websearch", report_text)


if __name__ == "__main__":
    unittest.main()
