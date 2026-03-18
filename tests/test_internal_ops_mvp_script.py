from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "work" / "ai-da-guan-jia" / "scripts" / "internal_ops_mvp.sh"


class InternalOpsMVPScriptTest(unittest.TestCase):
    def test_script_parses_with_bash_n(self) -> None:
        completed = subprocess.run(
            ["bash", "-n", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_checklist_prints_fixed_phrases_and_core_commands(self) -> None:
        completed = subprocess.run(
            ["bash", str(SCRIPT_PATH), "checklist"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("今天最该看什么", completed.stdout)
        self.assertIn("帮我接个任务", completed.stdout)
        self.assertIn("把这事闭环", completed.stdout)
        self.assertIn("review-clones --portfolio internal", completed.stdout)
        self.assertIn("sync-feishu --surface clone_governance --portfolio internal --dry-run", completed.stdout)


if __name__ == "__main__":
    unittest.main()
