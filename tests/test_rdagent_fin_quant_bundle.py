from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ROOT = PROJECT_ROOT / "distribution" / "rd-agent-fin-quant"


class RDAgentFinQuantBundleTest(unittest.TestCase):
    def test_expected_bundle_files_exist(self) -> None:
        expected = [
            BUNDLE_ROOT / "README.md",
            BUNDLE_ROOT / "rdagent.env.example",
            BUNDLE_ROOT / "remote" / "bootstrap_rd_agent_fin_quant.sh",
            BUNDLE_ROOT / "remote" / "verify_rd_agent_fin_quant.sh",
            PROJECT_ROOT / "scripts" / "deploy_rdagent_fin_quant_remote.sh",
            PROJECT_ROOT / "scripts" / "verify_rdagent_fin_quant_remote.sh",
            PROJECT_ROOT / "scripts" / "deploy_black_satellite_rdagent.sh",
        ]
        for path in expected:
            self.assertTrue(path.exists(), f"missing bundle file: {path}")

    def test_env_template_pins_fin_quant_with_docker(self) -> None:
        text = (BUNDLE_ROOT / "rdagent.env.example").read_text(encoding="utf-8")
        self.assertIn("RDAGENT_SETTINGS_MODULE=rdagent.app.qlib_rd_loop_conf", text)
        self.assertIn("SCEN=fin_quant", text)
        self.assertIn("MODEL_COSTEER_ENV_TYPE=docker", text)
        self.assertIn("OPENAI_API_KEY=", text)

    def test_bundle_readme_calls_out_remote_linux_path(self) -> None:
        text = (BUNDLE_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Ubuntu 22.04/24.04", text)
        self.assertIn("Apple Silicon", text)
        self.assertIn("research-only", text)
        self.assertIn('RD_AGENT_HOST=your-ubuntu-host-or-ip', text)
        self.assertIn("--workspace-root '$HOME/rd-agent-fin-quant-poc'", text)
        self.assertIn("deploy_black_satellite_rdagent.sh", text)
        self.assertIn("qlib.cli.data", text)
        self.assertIn("qlib_bin.tar.gz", text)
        self.assertNotIn("--host <ubuntu-host>", text)

    def test_bootstrap_script_supports_modern_qlib_data_fallbacks(self) -> None:
        text = (BUNDLE_ROOT / "remote" / "bootstrap_rd_agent_fin_quant.sh").read_text(encoding="utf-8")
        self.assertIn("python -m qlib.cli.data qlib_data", text)
        self.assertIn("python -m qlib.run.get_data qlib_data", text)
        self.assertIn("QLIB_CN_COMMUNITY_DATA_URL", text)
        self.assertIn("downloaded_community", text)

    def test_shell_scripts_parse(self) -> None:
        bash = shutil.which("bash")
        zsh = shutil.which("zsh")
        self.assertIsNotNone(bash)
        self.assertIsNotNone(zsh)

        bash_scripts = [
            BUNDLE_ROOT / "remote" / "bootstrap_rd_agent_fin_quant.sh",
            BUNDLE_ROOT / "remote" / "verify_rd_agent_fin_quant.sh",
        ]
        zsh_scripts = [
            PROJECT_ROOT / "scripts" / "deploy_rdagent_fin_quant_remote.sh",
            PROJECT_ROOT / "scripts" / "verify_rdagent_fin_quant_remote.sh",
            PROJECT_ROOT / "scripts" / "deploy_black_satellite_rdagent.sh",
        ]

        for path in bash_scripts:
            subprocess.run([bash, "-n", str(path)], check=True)
        for path in zsh_scripts:
            subprocess.run([zsh, "-n", str(path)], check=True)
