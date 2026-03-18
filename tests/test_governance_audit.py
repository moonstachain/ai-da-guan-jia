from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "governance_audit.py"
MODULE_SPEC = importlib.util.spec_from_file_location("governance_audit", SCRIPT_PATH)
assert MODULE_SPEC and MODULE_SPEC.loader
spec = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(spec)


class GovernanceAuditTest(unittest.TestCase):
    def test_count_naming_traps_counts_rows(self) -> None:
        sample = """## ⚠️ 命名陷阱（防止 Claude/Codex 误判）
| 错误假设 | 实际情况 |
|---------|---------|
| A | B |
| C | D |

---
"""
        self.assertEqual(spec.count_naming_traps(sample), 2)

    def test_summarize_execution_engine_health_reads_recent_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            run_one = runs_root / "2026-03-16" / "adagj-001"
            run_two = runs_root / "2026-03-15" / "adagj-002"
            run_one.mkdir(parents=True, exist_ok=True)
            run_two.mkdir(parents=True, exist_ok=True)
            (run_one / "evolution.json").write_text(
                json.dumps(
                    {
                        "created_at": "2026-03-16T09:00:00+00:00",
                        "verification_result": {"status": "completed"},
                        "feishu_sync_status": "synced_applied",
                        "github_sync_status": "github_closure_synced_applied",
                        "effective_patterns": ["Pattern A", "Pattern A"],
                        "wasted_patterns": ["Waste A"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (run_two / "evolution.json").write_text(
                json.dumps(
                    {
                        "created_at": "2026-03-15T08:00:00+00:00",
                        "verification_result": {"status": "partial"},
                        "feishu_sync_status": "apply_blocked_missing_credentials",
                        "github_sync_status": "github_closure_preview_ready",
                        "effective_patterns": ["Pattern B"],
                        "wasted_patterns": ["Waste A", "Waste B"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(spec, "ensure_runtime_feishu_env", return_value={"missing_keys": ["FEISHU_APP_ID"], "source": "missing"}):
                summary = spec.summarize_execution_engine_health(
                    runs_root,
                    now=datetime(2026, 3, 17, tzinfo=timezone.utc),
                )

        self.assertEqual(summary["recent_runs_7d"], 2)
        self.assertEqual(summary["verification_status_distribution"]["completed"], 1)
        self.assertEqual(summary["verification_status_distribution"]["partial"], 1)
        self.assertEqual(summary["feishu_sync_status_distribution"]["synced_applied"], 1)
        self.assertEqual(summary["verified_rate"], 0.5)
        self.assertEqual(summary["feishu_apply_success_rate"], 0.5)
        self.assertEqual(summary["github_apply_success_rate"], 0.5)
        self.assertEqual(summary["top_effective_patterns"][0]["pattern"], "Pattern A")
        self.assertEqual(summary["top_wasted_patterns"][0]["pattern"], "Waste A")
        self.assertTrue(summary["inferred_notes"])

    def test_summarize_execution_engine_health_is_safe_when_no_runs_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            with patch.object(spec, "ensure_runtime_feishu_env", return_value={"missing_keys": [], "source": "process_env"}):
                summary = spec.summarize_execution_engine_health(
                    runs_root,
                    now=datetime(2026, 3, 17, tzinfo=timezone.utc),
                )

        self.assertEqual(summary["recent_runs_7d"], 0)
        self.assertEqual(summary["verified_rate"], 0.0)
        self.assertEqual(summary["feishu_apply_success_rate"], 0.0)
        self.assertEqual(summary["github_apply_success_rate"], 0.0)
        self.assertEqual(summary["top_effective_patterns"], [])
        self.assertEqual(summary["top_wasted_patterns"], [])


if __name__ == "__main__":
    unittest.main()
