from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
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


class CloneOpsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPT_ROOT))
        cls.module = load_module("test_ai_da_guan_jia_clone_ops", SCRIPT_PATH)

    def patch_runtime_paths(self, temp_root: Path):
        artifacts_root = temp_root / "artifacts"
        clones_root = artifacts_root / "clones"
        clones_current = clones_root / "current"
        strategy_root = artifacts_root / "strategy"
        strategy_current = strategy_root / "current"
        return patch.multiple(
            self.module,
            ARTIFACTS_ROOT=artifacts_root,
            RUNS_ROOT=temp_root / "runs",
            CLONES_ROOT=clones_root,
            CLONES_CURRENT_ROOT=clones_current,
            CLONE_REGISTRY_PATH=clones_current / "clone-registry.json",
            ROLE_TEMPLATE_REGISTRY_PATH=clones_current / "role-template-registry.json",
            CLONE_ORG_REGISTRY_PATH=clones_current / "org-registry.json",
            CLONE_TRAINING_STATE_PATH=clones_current / "clone-training-state.json",
            CLONE_SCORECARD_PATH=clones_current / "clone-scorecard.json",
            CLONE_AUTONOMY_TIER_PATH=clones_current / "clone-autonomy-tier.json",
            CLONE_PROMOTION_QUEUE_PATH=clones_current / "promotion-queue.json",
            CLONE_BUDGET_ALLOCATION_PATH=clones_current / "budget-allocation.json",
            CLONE_TASK_RUNS_PATH=clones_current / "task-runs.json",
            CLONE_TRAINING_CYCLES_PATH=clones_current / "training-cycles.json",
            CLONE_CAPABILITY_PROPOSALS_PATH=clones_current / "capability-proposals.json",
            CLONE_ALERTS_DECISIONS_PATH=clones_current / "alerts-decisions.json",
            CLONE_PORTFOLIO_REPORT_PATH=clones_current / "portfolio-daily-report.json",
            CLONE_PORTFOLIO_REPORT_MD_PATH=clones_current / "portfolio-daily-report.md",
            CLONE_FEISHU_SYNC_BUNDLE_PATH=clones_current / "feishu-sync-bundle.json",
            CLONE_SYNC_RESULT_PATH=clones_current / "sync-result.json",
            STRATEGY_ROOT=strategy_root,
            STRATEGY_CURRENT_ROOT=strategy_current,
        )

    def register_clone(self, parser, args_list: list[str]) -> int:
        args = parser.parse_args(args_list)
        with patch.object(self.module, "current_shared_core_version", return_value="test-core"):
            return args.func(args)

    def test_register_clone_uses_role_template_defaults_and_org_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_runtime_paths(root):
                parser = self.module.build_parser()
                returncode = self.register_clone(
                    parser,
                    [
                        "register-clone",
                        "--clone-id",
                        "clone-finance-1",
                        "--customer-id",
                        "self-fleet",
                        "--display-name",
                        "财务助理",
                        "--role-template-id",
                        "finance",
                        "--actor-type",
                        "employee",
                    ],
                )

                registry_rows = json.loads(self.module.CLONE_REGISTRY_PATH.read_text(encoding="utf-8"))

        self.assertEqual(returncode, 0)
        self.assertEqual(len(registry_rows), 1)
        row = registry_rows[0]
        self.assertEqual(row["org_id"], "yuanli-hq")
        self.assertEqual(row["tenant_id"], "yuanli-hq")
        self.assertEqual(row["actor_type"], "employee")
        self.assertEqual(row["role_template_id"], "finance")
        self.assertEqual(row["visibility_policy"], "hq_internal_full")
        self.assertEqual(row["service_tier"], "internal_core")
        self.assertEqual(row["memory_namespace"], "clone/yuanli-hq/clone-finance-1")
        self.assertEqual(row["report_owner"], "liming")
        self.assertIn("财务", row["goal_model"])

    def test_refresh_clone_factory_state_supports_portfolios_and_governance_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_runtime_paths(root):
                parser = self.module.build_parser()
                self.register_clone(
                    parser,
                    [
                        "register-clone",
                        "--clone-id",
                        "clone-finance-1",
                        "--customer-id",
                        "self-fleet",
                        "--display-name",
                        "财务助理",
                        "--role-template-id",
                        "finance",
                        "--actor-type",
                        "employee",
                    ],
                )
                self.register_clone(
                    parser,
                    [
                        "register-clone",
                        "--clone-id",
                        "clone-acme-ops",
                        "--customer-id",
                        "acme",
                        "--display-name",
                        "Acme Operator",
                        "--goal-model",
                        "提高客户成功率",
                        "--memory-namespace",
                        "clone/acme/clone-acme-ops",
                        "--report-owner",
                        "hay",
                        "--actor-type",
                        "client_operator",
                    ],
                )

                records = [
                    {
                        "run_id": "adagj-internal-001",
                        "created_at": "2026-03-15T10:00:00+08:00",
                        "run_kind": "clone_training",
                        "clone_id": "clone-finance-1",
                        "customer_id": "self-fleet",
                        "training_cycle_id": "cycle-finance",
                        "target_capability": "对账闭环",
                        "goal_model": "提升财务准确率",
                        "skills_selected": ["ai-da-guan-jia", "agency-support-finance-tracker"],
                        "verification_result": {"status": "completed", "evidence": ["ledger"], "open_questions": []},
                        "score_before": 35,
                        "score_after": 68,
                        "promotion_recommendation": "watch",
                        "budget_weight": 0.4,
                        "max_distortion": "",
                        "evolution_candidates": ["Promote finance reconciliation template"],
                    },
                    {
                        "run_id": "adagj-client-001",
                        "created_at": "2026-03-15T11:00:00+08:00",
                        "run_kind": "clone_training",
                        "clone_id": "clone-acme-ops",
                        "customer_id": "acme",
                        "training_cycle_id": "cycle-acme",
                        "target_capability": "客户交付闭环",
                        "goal_model": "提高客户成功率",
                        "skills_selected": ["ai-da-guan-jia"],
                        "verification_result": {
                            "status": "partial",
                            "evidence": ["report"],
                            "open_questions": ["客户确认审批链"],
                        },
                        "score_before": 28,
                        "score_after": 44,
                        "promotion_recommendation": "watch",
                        "budget_weight": 0.2,
                        "max_distortion": "把审批提醒误判成已收口。",
                        "evolution_candidates": ["Keep client approval checklist tenant-local"],
                    },
                ]
                with patch.object(self.module, "iter_clone_training_records", return_value=records):
                    internal = self.module.refresh_clone_factory_state(report_date="2026-03-15", portfolio="internal", persist=True)
                    client = self.module.refresh_clone_factory_state(report_date="2026-03-15", portfolio="client", persist=False)

                bundle = self.module.write_clone_review_materials(internal)
                persisted_orgs = json.loads(self.module.CLONE_ORG_REGISTRY_PATH.read_text(encoding="utf-8"))

        self.assertEqual(internal["portfolio"], "internal")
        self.assertEqual([row["clone_id"] for row in internal["scorecard"]], ["clone-finance-1"])
        self.assertEqual(client["portfolio"], "client")
        self.assertEqual([row["clone_id"] for row in client["scorecard"]], ["clone-acme-ops"])
        self.assertEqual(len(persisted_orgs), 1)
        self.assertEqual(persisted_orgs[0]["org_id"], "yuanli-hq")
        self.assertIn("能力提案表", bundle["tables"])
        self.assertIn("风险与决策表", bundle["tables"])
        self.assertIn("AI实例注册表", bundle["tables"])
        self.assertEqual(len(bundle["tables"]["AI实例注册表"]), 1)
        self.assertEqual(bundle["tables"]["能力提案表"][0]["Clone ID"], "clone-finance-1")

    def test_sync_feishu_surface_clone_governance_routes_to_bundle_sync(self) -> None:
        parser = self.module.build_parser()
        args = parser.parse_args(
            [
                "sync-feishu",
                "--surface",
                "clone_governance",
                "--portfolio",
                "internal",
                "--report-date",
                "2026-03-15",
                "--dry-run",
            ]
        )

        with patch.object(self.module, "run_clone_governance_feishu_sync", return_value=(0, "dry_run_preview_ready")) as sync:
            output = io.StringIO()
            with redirect_stdout(output):
                returncode = self.module.command_sync_feishu(args)

        self.assertEqual(returncode, 0)
        sync.assert_called_once_with(
            report_date="2026-03-15",
            portfolio="internal",
            apply=False,
            link_override=None,
            bridge_script_override=None,
        )
        self.assertIn("dry_run_preview_ready", output.getvalue())

    def test_review_clones_internal_persists_local_internal_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_runtime_paths(root):
                parser = self.module.build_parser()
                self.register_clone(
                    parser,
                    [
                        "register-clone",
                        "--clone-id",
                        "ops-mvp-001",
                        "--customer-id",
                        "yuanli-hq",
                        "--display-name",
                        "中台管理试点同事",
                        "--role-template-id",
                        "ops-management",
                        "--actor-type",
                        "employee",
                    ],
                )
                args = parser.parse_args(
                    [
                        "review-clones",
                        "--portfolio",
                        "internal",
                        "--date",
                        "2026-03-15",
                    ]
                )

                output = io.StringIO()
                with patch.object(self.module, "iter_clone_training_records", return_value=[]):
                    with redirect_stdout(output):
                        returncode = args.func(args)

                report = json.loads(self.module.CLONE_PORTFOLIO_REPORT_PATH.read_text(encoding="utf-8"))
                org_rows = json.loads(self.module.CLONE_ORG_REGISTRY_PATH.read_text(encoding="utf-8"))
                score_rows = json.loads(self.module.CLONE_SCORECARD_PATH.read_text(encoding="utf-8"))
                bundle_exists = self.module.CLONE_FEISHU_SYNC_BUNDLE_PATH.exists()
                command_output = output.getvalue()

        self.assertEqual(returncode, 0)
        self.assertEqual(report["portfolio"], "internal")
        self.assertEqual(len(org_rows), 1)
        self.assertEqual(org_rows[0]["org_id"], "yuanli-hq")
        self.assertEqual(len(score_rows), 1)
        self.assertEqual(score_rows[0]["clone_id"], "ops-mvp-001")
        self.assertTrue(bundle_exists)
        self.assertIn("portfolio: internal", command_output)


if __name__ == "__main__":
    unittest.main()
