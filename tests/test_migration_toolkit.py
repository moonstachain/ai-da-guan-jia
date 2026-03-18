from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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

    def test_build_restore_bundle_includes_history_assets_when_requested(self) -> None:
        history_file = self.codex_root / "state_5.sqlite"
        history_file.write_text("sqlite-placeholder\n", encoding="utf-8")

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
                "--include-history",
            ],
            capture_output=True,
            text=True,
            check=True,
            cwd=self.workspace_root,
            env=env,
        )

        payload = json.loads(result.stdout)
        staging_root = Path(payload["staging_root"])
        self.assertTrue((staging_root / "history" / "codex" / "state_5.sqlite").exists())

    def test_build_restore_bundle_excludes_its_own_output_dir_from_workspace_output_asset(self) -> None:
        env = os.environ.copy()
        env["HOME"] = str(self.root)
        env["WORKSPACE_ROOT"] = str(self.workspace_root)
        recursive_output_dir = self.workspace_root / "output" / "migration"

        result = subprocess.run(
            [
                "python3",
                str(PROJECT_ROOT / "scripts" / "build_restore_bundle.py"),
                "--manifest",
                str(self.workspace_root / "migration-manifest.json"),
                "--output-dir",
                str(recursive_output_dir),
            ],
            capture_output=True,
            text=True,
            check=True,
            cwd=self.workspace_root,
            env=env,
        )

        payload = json.loads(result.stdout)
        staging_root = Path(payload["staging_root"])
        restored_output = staging_root / "secret" / "workspace" / "output"

        self.assertTrue(restored_output.exists())
        self.assertFalse((restored_output / "migration").exists())
        self.assertTrue((restored_output / "playwright" / "trace.txt").exists())

    def _write_ssh_stub(self, body: str) -> Path:
        stub = self.root / "ssh-stub.sh"
        stub.write_text(body, encoding="utf-8")
        stub.chmod(0o755)
        return stub

    def _write_remote_ai_script(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            """#!/usr/bin/env python3
import sys

if __name__ == "__main__":
    if "inventory-skills" in sys.argv:
        print("count: 54")
    else:
        print("ok")
""",
            encoding="utf-8",
        )

    def test_probe_new_mac_remote_reports_missing_codex_app(self) -> None:
        ssh_stub = self._write_ssh_stub(
            """#!/bin/zsh
set -euo pipefail
cmd="${*: -1}"
if [[ "$cmd" == "printf connected" ]]; then
  printf 'connected'
  exit 0
fi
cat <<'EOF'
HAS_GIT=1
HAS_PYTHON3=1
PYTHON_VERSION=3.11.9
PYTHON_OK=1
HAS_NODE=1
NODE_VERSION=20.12.0
NODE_OK=1
HAS_CODEX_APP=0
EOF
"""
        )

        result = subprocess.run(
            [
                str(PROJECT_ROOT / "scripts" / "probe_new_mac_remote.sh"),
                "--host",
                "mac-studio.local",
                "--json",
            ],
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "SSH_BIN": str(ssh_stub)},
        )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "missing_codex_app")
        self.assertTrue(payload["host_reachable"])
        self.assertTrue(payload["ssh_reachable"])
        self.assertFalse(payload["codex_app_present"])

    def test_probe_new_mac_remote_bootstraps_homebrew_shellenv(self) -> None:
        log_path = self.root / "probe-ssh-log.txt"
        ssh_stub = self._write_ssh_stub(
            f"""#!/bin/zsh
set -euo pipefail
cmd="${{*: -1}}"
printf '%s\\n---\\n' "$cmd" >> {log_path}
if [[ "$cmd" == "printf connected" ]]; then
  printf 'connected'
  exit 0
fi
cat <<'EOF'
HAS_GIT=1
HAS_PYTHON3=1
PYTHON_VERSION=3.11.15
PYTHON_OK=1
HAS_NODE=1
NODE_VERSION=20.20.1
NODE_OK=1
HAS_CODEX_APP=1
EOF
"""
        )

        result = subprocess.run(
            [
                str(PROJECT_ROOT / "scripts" / "probe_new_mac_remote.sh"),
                "--host",
                "m5.local",
                "--json",
            ],
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "SSH_BIN": str(ssh_stub)},
        )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ready")
        ssh_invocation = log_path.read_text(encoding="utf-8")
        self.assertIn("/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin", ssh_invocation)
        self.assertIn("shellenv", ssh_invocation)
        self.assertIn("$PY311_PREFIX/libexec/bin", ssh_invocation)
        self.assertIn("$NODE20_PREFIX/bin", ssh_invocation)

    def test_remote_verify_new_mac_runs_verify_script_over_ssh(self) -> None:
        log_path = self.root / "ssh-log.txt"
        ssh_stub = self._write_ssh_stub(
            f"""#!/bin/zsh
set -euo pipefail
printf '%s\\n' "$*" > {log_path}
printf '[verify] restore verification passed\\n'
"""
        )

        result = subprocess.run(
            [
                str(PROJECT_ROOT / "scripts" / "remote_verify_new_mac.sh"),
                "--host",
                "m5.local",
                "--workspace-root",
                "/Users/tester/Documents/codex-ai-gua-jia-01",
                "--browser-smoke-command",
                "python3 smoke.py",
            ],
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "SSH_BIN": str(ssh_stub)},
        )

        self.assertIn("[remote-verify] remote verify passed", result.stdout)
        ssh_invocation = log_path.read_text(encoding="utf-8")
        self.assertIn("verify-restore.sh", ssh_invocation)
        self.assertIn("BROWSER_SKILL_SMOKE_CMD", ssh_invocation)

    def test_verify_restore_uses_workspace_ai_script_when_skill_install_is_missing(self) -> None:
        workspace_ai_script = self.workspace_root / "work" / "ai-da-guan-jia" / "scripts" / "ai_da_guan_jia.py"
        self._write_remote_ai_script(workspace_ai_script)
        check_mcp_script = self.workspace_root / "scripts" / "check_codex_mcp.py"
        check_mcp_script.parent.mkdir(parents=True, exist_ok=True)
        check_mcp_script.write_text("print('mcp-ok')\n", encoding="utf-8")
        bin_dir = self.root / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        brew_stub = bin_dir / "brew"
        brew_stub.write_text(
            f"""#!/bin/sh
if [ "${{1:-}}" = "shellenv" ]; then
  printf 'export PATH=\"{Path(sys.executable).parent}:$PATH\"\\n'
  exit 0
fi
exit 1
""",
            encoding="utf-8",
        )
        brew_stub.chmod(0o755)

        env = os.environ.copy()
        env["HOME"] = str(self.root)
        env["CODEX_HOME"] = str(self.codex_root)
        env["WORKSPACE_ROOT"] = str(self.workspace_root)
        env["CHECK_CODEX_MCP_SCRIPT_PATH"] = str(check_mcp_script)
        env["VERIFY_CODEX_APP_MODE"] = "skip"
        env["VERIFY_MCP_MODE"] = "skip"
        env["VERIFY_UNIT_TEST_MODE"] = "skip"
        env["EXPECTED_SKILLS_MIN"] = "20"
        env["PATH"] = f"{bin_dir}:{env['PATH']}"

        result = subprocess.run(
            [str(PROJECT_ROOT / "verify-restore.sh")],
            capture_output=True,
            text=True,
            cwd=self.workspace_root,
            check=True,
            env=env,
        )

        self.assertIn("inventory-skills completed", result.stdout)
        self.assertIn("browser skill smoke skipped", result.stdout)
        self.assertIn("restore verification passed", result.stdout)

    def test_remote_inventory_codex_host_reports_browser_mvp_readiness(self) -> None:
        workspace_ai_script = self.workspace_root / "work" / "ai-da-guan-jia" / "scripts" / "ai_da_guan_jia.py"
        skill_ai_script = self.skills_root / "ai-da-guan-jia" / "scripts" / "ai_da_guan_jia.py"
        self._write_remote_ai_script(workspace_ai_script)
        self._write_remote_ai_script(skill_ai_script)

        feishu_profile = self.skills_root / "feishu-reader" / "state" / "browser-profile" / "feishu-reader"
        feishu_profile.mkdir(parents=True, exist_ok=True)
        (feishu_profile / "Cookies").write_text("cookie", encoding="utf-8")
        get_biji_env = self.skills_root / "ai-da-guan-jia" / "state" / "get-biji.env"
        get_biji_env.parent.mkdir(parents=True, exist_ok=True)
        get_biji_env.write_text("GET_BIJI_API_KEY=test\n", encoding="utf-8")
        chrome_profile = self.root / "Library" / "Application Support" / "Google" / "Chrome"
        chrome_profile.mkdir(parents=True, exist_ok=True)
        (chrome_profile / "Local State").write_text("{}", encoding="utf-8")

        output_root = self.root / "remote-output"
        ssh_stub = self._write_ssh_stub(
            f"""#!/bin/zsh
set -euo pipefail
cmd="${{*: -1}}"
HOME="{self.root}" /bin/zsh -lc "$cmd"
"""
        )

        result = subprocess.run(
            [
                str(PROJECT_ROOT / "scripts" / "remote_inventory_codex_host.sh"),
                "--host",
                "old.local",
                "--workspace-root",
                str(self.workspace_root),
                "--source-id",
                "satellite-03",
                "--output-root",
                str(output_root),
            ],
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "SSH_BIN": str(ssh_stub)},
        )

        self.assertIn("status: inventory_complete", result.stdout)
        inventory_path = output_root / "satellite-03" / "inventory.json"
        summary_path = output_root / "satellite-03" / "inventory-summary.md"
        payload = json.loads(inventory_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["browser"]["ready_surfaces"], ["feishu", "get_biji", "other_browser"])
        self.assertEqual(payload["mvp_execution"]["status"], "ready")
        self.assertEqual(payload["mvp_execution"]["next_ready_surface"], "feishu")
        summary = summary_path.read_text(encoding="utf-8")
        self.assertIn("Browser MVP Status: `ready`", summary)
        self.assertIn("Feishu Session: `ready`", summary)
        self.assertIn("Get笔记 Session: `ready`", summary)


if __name__ == "__main__":
    unittest.main()
