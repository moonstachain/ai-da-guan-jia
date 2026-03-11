from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path("/Users/hay2045/Documents/codex-ai-gua-jia-01")


class MigrationToolkitTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.codex_root = self.root / ".codex"
        self.skills_root = self.codex_root / "skills"
        self.workspace_root = self.root / "workspace"
        self.mirror_destination = self.root / "skills-mirror"
        self.bundle_output = self.root / "bundle-output"
        self._build_fixture()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _build_fixture(self) -> None:
        skill_dir = self.skills_root / "alpha-skill"
        (skill_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        (skill_dir / "scripts").mkdir(parents=True, exist_ok=True)
        (skill_dir / ".git").mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text("# alpha\n", encoding="utf-8")
        (skill_dir / "scripts" / "run.py").write_text("print('ok')\n", encoding="utf-8")
        (skill_dir / "artifacts" / "state.json").write_text("{}", encoding="utf-8")

        system_skill_dir = self.skills_root / ".system" / "skill-creator"
        system_skill_dir.mkdir(parents=True, exist_ok=True)
        (system_skill_dir / "SKILL.md").write_text("# nested\n", encoding="utf-8")

        self.codex_root.mkdir(parents=True, exist_ok=True)
        (self.codex_root / "auth.json").write_text('{"token": "abc"}\n', encoding="utf-8")
        (self.codex_root / "config.toml").write_text('model = "gpt-5.4"\n', encoding="utf-8")
        (self.codex_root / "automations" / "daily").mkdir(parents=True, exist_ok=True)
        (self.codex_root / "automations" / "daily" / "automation.toml").write_text("version = 1\n", encoding="utf-8")

        self.workspace_root.mkdir(parents=True, exist_ok=True)
        (self.workspace_root / "output" / "playwright").mkdir(parents=True, exist_ok=True)
        (self.workspace_root / "output" / "playwright" / "trace.txt").write_text("trace\n", encoding="utf-8")
        (self.workspace_root / "artifacts" / "logs").mkdir(parents=True, exist_ok=True)
        (self.workspace_root / "artifacts" / "logs" / "task.md").write_text("log\n", encoding="utf-8")

        manifest = {
            "secret_assets": [
                {
                    "id": "auth",
                    "source": "$HOME/.codex/auth.json",
                    "bundle_path": "secret/codex/auth.json",
                    "restore_target": "$HOME/.codex/auth.json",
                    "required": True,
                },
                {
                    "id": "skills",
                    "source": "$HOME/.codex/skills",
                    "bundle_path": "secret/codex/skills-raw",
                    "restore_target": "$HOME/.codex/skills",
                    "required": True,
                },
                {
                    "id": "workspace-output",
                    "source": "$WORKSPACE_ROOT/output",
                    "bundle_path": "secret/workspace/output",
                    "restore_target": "$WORKSPACE_ROOT/output",
                    "required": False,
                },
            ],
            "optional_history_assets": [
                {
                    "id": "history-db",
                    "source": "$HOME/.codex/state_5.sqlite",
                    "bundle_path": "history/codex/state_5.sqlite",
                    "restore_target": "$HOME/.codex/state_5.sqlite",
                }
            ],
        }
        (self.workspace_root / "migration-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_export_skills_mirror_excludes_runtime_state(self) -> None:
        result = subprocess.run(
            [
                "python3",
                str(PROJECT_ROOT / "scripts" / "export_skills_mirror.py"),
                "--source",
                str(self.skills_root),
                "--destination",
                str(self.mirror_destination),
                "--clean",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["count"], 2)
        self.assertTrue((self.mirror_destination / "alpha-skill" / "SKILL.md").exists())
        self.assertTrue((self.mirror_destination / "alpha-skill" / "scripts" / "run.py").exists())
        self.assertTrue((self.mirror_destination / ".system" / "skill-creator" / "SKILL.md").exists())
        self.assertFalse((self.mirror_destination / "alpha-skill" / "artifacts").exists())
        self.assertFalse((self.mirror_destination / "alpha-skill" / ".git").exists())

    def test_build_restore_bundle_stages_secret_assets(self) -> None:
        env = os.environ.copy()
        env["HOME"] = str(self.root)
        env["WORKSPACE_ROOT"] = str(self.workspace_root)
        result = subprocess.run(
            [
                "python3",
                str(PROJECT_ROOT / "scripts" / "build_restore_bundle.py"),
                "--manifest",
                str(self.workspace_root / "migration-manifest.json"),
                "--output-dir",
                str(self.bundle_output),
            ],
            capture_output=True,
            text=True,
            check=True,
            cwd=self.workspace_root,
            env=env,
        )

        payload = json.loads(result.stdout)
        staging_root = Path(payload["staging_root"])
        archive_path = Path(payload["archive_path"])

        self.assertTrue(staging_root.exists())
        self.assertTrue(archive_path.exists())
        self.assertTrue((staging_root / "secret" / "codex" / "auth.json").exists())
        self.assertTrue((staging_root / "secret" / "codex" / "skills-raw" / "alpha-skill" / "artifacts").exists())
        self.assertTrue((staging_root / "secret" / "workspace" / "output" / "playwright" / "trace.txt").exists())
        self.assertFalse((staging_root / "history").exists())


if __name__ == "__main__":
    unittest.main()
