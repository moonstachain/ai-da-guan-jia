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


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class StrategyGovernorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPT_ROOT))
        cls.module = load_module("test_ai_da_guan_jia_strategy_governor", SCRIPT_ROOT / "ai_da_guan_jia.py")

    def patch_strategy_paths(self, temp_root: Path):
        strategy_root = temp_root / "strategy"
        current = strategy_root / "current"
        return patch.multiple(
            self.module,
            STRATEGY_ROOT=strategy_root,
            STRATEGY_CURRENT_ROOT=current,
            PROPOSAL_QUEUE_PATH=current / "proposal-queue.json",
            GOVERNANCE_CURRENT_ROOT=temp_root / "governance" / "current",
        )

    def fake_clone_bundle(self) -> dict:
        return {
            "promotion_queue": [],
            "scorecard": [
                {
                    "clone_id": "clone-beta-builder",
                    "promotion_recommendation": "watch",
                    "routing_priority": 94.8,
                    "autonomy_cap": "guarded-autonomy",
                }
            ],
            "lab_registry_count": 0,
            "include_lab": False,
            "portfolio_report": {"feishu_mirror_state": "local_only"},
            "budget_allocation": {},
            "registry": [],
        }

    def test_review_clones_parser_wires_include_lab_and_sync_fields(self) -> None:
        parser = self.module.build_parser()
        args = parser.parse_args(
            [
                "review-clones",
                "--date",
                "2026-03-12",
                "--include-lab",
                "--sync-feishu",
                "--link",
                "https://example.com/base",
                "--bridge-script",
                "/tmp/fake-bridge.py",
            ]
        )
        bundle = self.fake_clone_bundle()
        bundle["lab_registry_count"] = 1

        with patch.object(self.module, "refresh_clone_factory_state", return_value=bundle) as refresh:
            with patch.object(self.module, "write_clone_review_materials", return_value={"bundle": "ok"}):
                with patch.object(self.module, "sync_clone_review_to_feishu", return_value=(0, "synced")) as sync:
                    output = io.StringIO()
                    with redirect_stdout(output):
                        returncode = self.module.command_review_clones(args)

        self.assertEqual(returncode, 0)
        refresh.assert_called_once_with(report_date="2026-03-12", include_lab=True, portfolio="all", persist=False)
        sync.assert_called_once()
        text = output.getvalue()
        self.assertIn("portfolio: all", text)
        self.assertIn("include_lab: True", text)
        self.assertIn("feishu_mirror_state: synced", text)

    def test_write_strategy_operating_system_writes_dual_axis_registries(self) -> None:
        inventory = [
            {"name": "ai-da-guan-jia", "cluster": "AI大管家治理簇", "resource_score": 2, "boundary": ""},
            {"name": "routing-playbook", "cluster": "AI大管家治理簇", "resource_score": 2, "boundary": ""},
            {"name": "skill-trainer-recursive", "cluster": "技能生产簇", "resource_score": 2, "boundary": ""},
        ]
        recent_runs = [
            {
                "run_id": "adagj-coevo-001",
                "task_text": "做人机协同 MVP 快证",
                "skills_selected": ["ai-da-guan-jia"],
                "verification_result": {"status": "completed", "open_questions": [], "evidence": ["note"]},
                "result_status": "completed",
            }
        ]
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_strategy_paths(root):
                with patch.object(self.module, "refresh_clone_factory_state", return_value=self.fake_clone_bundle()):
                    with patch.object(self.module, "load_clone_factory_state", return_value={"registry": []}):
                        with patch.object(self.module, "latest_hub_summary", return_value={}):
                            with patch.object(self.module, "latest_hub_recommendations", return_value={}):
                                bundle = self.module.write_strategy_operating_system(
                                    goals=self.module.default_strategic_goals(),
                                    inventory=inventory,
                                    recent_runs=recent_runs,
                                )

            current = root / "strategy" / "current"
            theme_registry = json.loads((current / "theme-registry.json").read_text(encoding="utf-8"))
            strategy_registry = json.loads((current / "strategy-registry.json").read_text(encoding="utf-8"))
            experiment_registry = json.loads((current / "experiment-registry.json").read_text(encoding="utf-8"))
            workflow_registry = json.loads((current / "workflow-registry.json").read_text(encoding="utf-8"))
            canonical_threads = json.loads((current / "canonical-thread-registry.json").read_text(encoding="utf-8"))
            thread_proposals = json.loads((current / "thread-proposal.json").read_text(encoding="utf-8"))
            active_threads = json.loads((current / "active-threads.json").read_text(encoding="utf-8"))
            cbm_mapping = json.loads((current / "cbm-mapping-view.json").read_text(encoding="utf-8"))
            cbm_markdown = (current / "cbm-mapping-view.md").read_text(encoding="utf-8")
            dashboard = (current / "governance-dashboard.md").read_text(encoding="utf-8")

            self.assertEqual(len(theme_registry), 3)
            self.assertTrue(
                any(item["id"] == "theme-human-ai-coevolution" and item["status"] == "active" for item in theme_registry)
            )
            self.assertEqual(len(strategy_registry), 8)
            self.assertTrue(any(item["strategy_id"] == "strategy-human-ai-success-efficiency" for item in strategy_registry))
            self.assertTrue(any(item["strategy_id"] == "strategy-governance-mainline-closure" for item in strategy_registry))
            self.assertEqual(len(experiment_registry), 6)
            self.assertEqual(workflow_registry, [])
            self.assertEqual(
                len([item for item in canonical_threads if item["disposition"] == "frontstage_now"]),
                3,
            )
            self.assertTrue(any(item["canonical_thread"] == "原力OS-治理体系研究" for item in canonical_threads))
            self.assertTrue(any(item["id"] == "TP-HA-001" and item["theme_id"] == "theme-human-ai-coevolution" for item in thread_proposals))
            self.assertTrue(any(item["theme"] == "theme-human-ai-coevolution" for item in active_threads))
            self.assertEqual(bundle["strategy_map"]["production_axis"]["counts"]["themes"], 3)
            self.assertEqual(
                bundle["strategy_map"]["production_axis"]["canonical_thread_program"]["frontstage_focus_theme_id"],
                "theme-governance",
            )
            self.assertIn("## Theme Registry", dashboard)
            self.assertIn("## Canonical Thread Program", dashboard)
            self.assertIn("## Frontstage Threads", dashboard)
            self.assertIn("## Strategy Registry", dashboard)
            self.assertIn("## Experiment Registry", dashboard)
            self.assertIn("## Workflow Registry", dashboard)
            self.assertIn("## Production Metrics", dashboard)
            self.assertIn("theme-human-ai-coevolution", dashboard)
            self.assertIn("Frontstage Focus Override: theme-governance", dashboard)
            self.assertEqual(cbm_mapping["meta"]["artifact_role"], "cbm_mapping_view")
            self.assertEqual(len(cbm_mapping["rows"]), 3)
            self.assertEqual(
                [item["control_level"] for item in cbm_mapping["rows"]],
                ["direct", "control", "execute"],
            )
            self.assertEqual(cbm_mapping["summary"]["rows_with_action_refs"], 2)
            self.assertEqual(cbm_mapping["rows"][2]["coverage_status"], "partial")
            self.assertIn("## Rows", cbm_markdown)
            self.assertIn("治理运行骨架", cbm_markdown)

    def test_workflow_registry_only_keeps_validated_strategies(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            current = root / "strategy" / "current"
            current.mkdir(parents=True, exist_ok=True)
            (current / "workflow-registry.json").write_text(
                json.dumps(
                    [
                        {
                            "workflow_id": "workflow-pass",
                            "title": "Validated workflow",
                            "strategy_id": "strategy-pass",
                            "trigger": "manual",
                            "inputs": ["prompt"],
                            "verification_rule": "check evidence",
                            "human_boundary": "approval",
                            "reuse_signal": "reused",
                            "cost_class": "low",
                        },
                        {
                            "workflow_id": "workflow-proposed",
                            "title": "Should be filtered",
                            "strategy_id": "strategy-proposed",
                            "trigger": "manual",
                            "inputs": ["prompt"],
                            "verification_rule": "check evidence",
                            "human_boundary": "approval",
                            "reuse_signal": "new",
                            "cost_class": "low",
                        },
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            with self.patch_strategy_paths(root):
                rows = self.module.build_workflow_registry(
                    [
                        {"strategy_id": "strategy-pass", "validation_state": "passed"},
                        {"strategy_id": "strategy-proposed", "validation_state": "proposed"},
                    ]
                )

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["workflow_id"], "workflow-pass")

    def test_build_review_payload_uses_current_strategy_map_signature(self) -> None:
        inventory = [
            {
                "name": "ai-da-guan-jia",
                "directory_name": "ai-da-guan-jia",
                "description": "Top-level governance router",
                "layer": "governance",
                "resource_score": 2,
                "cluster": "AI大管家治理簇",
            }
        ]
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_strategy_paths(root):
                with patch.object(self.module, "REVIEWS_ROOT", root / "reviews"):
                    payload = self.module.build_review_payload(
                        inventory,
                        created_at="2026-03-14T02:05:00+08:00",
                        run_id="adagj-review-signature-fix",
                    )

        self.assertEqual(payload["skills_total"], 1)
        self.assertEqual(payload["status"], "awaiting_human_choice")
        self.assertIn("strategy_stage_theme", payload)
        self.assertIn("strategy_highest_goal", payload)

    def test_infer_strategy_axis_refs_maps_governance_mainlines(self) -> None:
        refs = self.module.infer_strategy_axis_refs("推进原力OS-治理体系研究并跑一次 scaffold 消费闭环")
        self.assertEqual(refs["theme_id"], "theme-governance")
        self.assertEqual(refs["strategy_id"], "strategy-governance-operating-core-closure")
        self.assertEqual(refs["experiment_id"], "experiment-governance-operating-core-closure-001")

        refs = self.module.infer_strategy_axis_refs("继续原力OS-分形设计，先做联邦对象治理模型完整验证")
        self.assertEqual(refs["strategy_id"], "strategy-governance-operational-ontology-closure")
        self.assertEqual(refs["experiment_id"], "experiment-governance-operational-ontology-closure-001")

        refs = self.module.infer_strategy_axis_refs("原力OS-信息聚合-三端一网先补 transport 再 emit")
        self.assertEqual(refs["strategy_id"], "strategy-governance-transport-unblock")
        self.assertEqual(refs["experiment_id"], "experiment-governance-transport-unblock-001")

    def test_record_evolution_local_only_keeps_mirror_state_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run_dir = root / "runs" / "2026-03-12" / "adagj-local-record"
            run_dir.mkdir(parents=True, exist_ok=True)
            input_path = root / "evolution-input.json"
            input_path.write_text(
                json.dumps(
                    {
                        "run_id": "adagj-local-record",
                        "created_at": "2026-03-12T15:30:00+08:00",
                        "task_text": "本地记录一次治理试点",
                        "skills_selected": ["ai-da-guan-jia"],
                        "theme_id": "theme-governance",
                        "strategy_id": "strategy-governance-operating-core-closure",
                        "experiment_id": "experiment-governance-operating-core-closure-001",
                        "experiment_verdict": "passed",
                        "verification_result": {"status": "completed", "evidence": ["local proof"], "open_questions": []},
                        "effective_patterns": ["真实试点先于镜像"],
                        "wasted_patterns": [],
                        "evolution_candidates": ["把本地闭环保持为默认路径"],
                        "feishu_sync_status": "payload_only_local",
                        "github_sync_status": "pending_intake",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            args = self.module.argparse.Namespace(input=str(input_path))
            saved: dict[str, object] = {}

            def fake_save(run_dir_arg, evolution, route_payload):
                saved["run_dir"] = run_dir_arg
                saved["evolution"] = dict(evolution)
                saved["route_payload"] = dict(route_payload)

            with patch.object(self.module, "run_dir_for", return_value=run_dir):
                with patch.object(self.module, "save_evolution_bundle", side_effect=fake_save):
                    with patch.object(self.module, "sync_strategy_axis_from_evolution", return_value={"theme_id": "theme-governance", "strategy_id": "strategy-governance-operating-core-closure", "experiment_id": "experiment-governance-operating-core-closure-001", "experiment_verdict": "passed"}):
                        with patch.object(self.module, "prepare_github_materials", return_value={}):
                            with redirect_stdout(io.StringIO()):
                                returncode = self.module.command_record_evolution(args)

            self.assertEqual(returncode, 0)
            evolution = saved["evolution"]
            self.assertEqual(evolution["feishu_mirror_state"], "local_only")
            self.assertEqual(evolution["github_mirror_state"], "local_only")

    def test_latest_sync_results_override_stale_mirror_state_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run_dir = root / "runs" / "2026-03-13" / "adagj-sync-refresh"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "feishu-sync-result.json").write_text(
                json.dumps({"status": "synced_applied", "stdout": "{\"base\":{\"obj_token\":\"tok\"}}"}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (run_dir / "github-sync-result.json").write_text(
                json.dumps({"status": "github_closure_synced_applied"}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            refreshed = self.module.ensure_evolution_mirror_states(
                {
                    "feishu_sync_status": "synced_applied",
                    "feishu_mirror_state": "blocked_auth",
                    "github_sync_status": "github_closure_synced_applied",
                    "github_mirror_state": "apply_failed",
                },
                run_dir,
            )

            self.assertEqual(refreshed["feishu_mirror_state"], "mirrored")
            self.assertEqual(refreshed["github_mirror_state"], "mirrored")

    def test_sync_strategy_axis_from_evolution_promotes_strategy_and_updates_mother(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run_dir = root / "runs" / "2026-03-12" / "adagj-real-round-001"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "evolution.json").write_text("{}", encoding="utf-8")
            with self.patch_strategy_paths(root):
                with patch.object(self.module, "refresh_clone_factory_state", return_value=self.fake_clone_bundle()):
                    with patch.object(self.module, "load_clone_factory_state", return_value={"registry": []}):
                        with patch.object(self.module, "latest_hub_summary", return_value={}):
                            with patch.object(self.module, "latest_hub_recommendations", return_value={}):
                                self.module.write_strategy_operating_system(
                                    goals=self.module.default_strategic_goals(),
                                    inventory=[{"name": "ai-da-guan-jia", "cluster": "AI大管家治理簇", "resource_score": 2, "boundary": ""}],
                                    recent_runs=[],
                                )
                                summary = self.module.sync_strategy_axis_from_evolution(
                                    {
                                        "run_id": "adagj-real-round-001",
                                        "created_at": "2026-03-12T13:00:00+08:00",
                                        "task_text": "做人机协同 MVP 快证",
                                        "skills_selected": ["ai-da-guan-jia"],
                                        "theme_id": "theme-human-ai-coevolution",
                                        "strategy_id": "strategy-human-ai-mvp-fast-validation",
                                        "experiment_id": "experiment-human-ai-mvp-fast-validation-001",
                                        "workflow_id": "",
                                        "experiment_verdict": "passed",
                                        "verification_result": {
                                            "status": "completed",
                                            "evidence": ["local proof"],
                                            "open_questions": [],
                                        },
                                        "effective_patterns": ["最小链路先验证再扩张"],
                                        "wasted_patterns": ["过早想 workflow 化"],
                                        "evolution_candidates": ["把 verdict 回灌母策略"],
                                    },
                                    run_dir,
                                )

            current = root / "strategy" / "current"
            strategy_registry = json.loads((current / "strategy-registry.json").read_text(encoding="utf-8"))
            experiment_registry = json.loads((current / "experiment-registry.json").read_text(encoding="utf-8"))
            target_strategy = next(
                item for item in strategy_registry if item["strategy_id"] == "strategy-human-ai-mvp-fast-validation"
            )
            mother_strategy = next(
                item for item in strategy_registry if item["strategy_id"] == "strategy-human-ai-success-efficiency"
            )
            target_experiment = next(
                item
                for item in experiment_registry
                if item["experiment_id"] == "experiment-human-ai-mvp-fast-validation-001"
            )

            self.assertEqual(summary["experiment_verdict"], "passed")
            self.assertTrue(summary["strategy_updated"])
            self.assertTrue(summary["mother_strategy_updated"])
            self.assertEqual(target_experiment["verdict"], "passed")
            self.assertEqual(target_strategy["validation_state"], "validated")
            self.assertEqual(target_strategy["last_experiment_id"], "experiment-human-ai-mvp-fast-validation-001")
            self.assertEqual(mother_strategy["last_child_strategy_id"], "strategy-human-ai-mvp-fast-validation")
            self.assertIn("gained=最小链路先验证再扩张", mother_strategy["last_reflection_summary"])

    def test_governance_wave_one_marks_transport_boundary_and_promotes_mother(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_strategy_paths(root):
                with patch.object(self.module, "refresh_clone_factory_state", return_value=self.fake_clone_bundle()):
                    with patch.object(self.module, "load_clone_factory_state", return_value={"registry": []}):
                        with patch.object(self.module, "latest_hub_summary", return_value={}):
                            with patch.object(self.module, "latest_hub_recommendations", return_value={}):
                                self.module.write_strategy_operating_system(
                                    goals=self.module.default_strategic_goals(),
                                    inventory=[{"name": "ai-da-guan-jia", "cluster": "AI大管家治理簇", "resource_score": 2, "boundary": ""}],
                                    recent_runs=[],
                                )
                                for run_name, strategy_id, experiment_id, verdict, verification_status in [
                                    (
                                        "adagj-governance-wave1-core",
                                        "strategy-governance-operating-core-closure",
                                        "experiment-governance-operating-core-closure-001",
                                        "passed",
                                        "completed",
                                    ),
                                    (
                                        "adagj-governance-wave1-ontology",
                                        "strategy-governance-operational-ontology-closure",
                                        "experiment-governance-operational-ontology-closure-001",
                                        "passed",
                                        "completed",
                                    ),
                                    (
                                        "adagj-governance-wave1-transport",
                                        "strategy-governance-transport-unblock",
                                        "experiment-governance-transport-unblock-001",
                                        "blocked_needs_user",
                                        "blocked_needs_user",
                                    ),
                                ]:
                                    run_dir = root / "runs" / "2026-03-12" / run_name
                                    run_dir.mkdir(parents=True, exist_ok=True)
                                    (run_dir / "evolution.json").write_text("{}", encoding="utf-8")
                                    summary = self.module.sync_strategy_axis_from_evolution(
                                        {
                                            "run_id": run_name,
                                            "created_at": "2026-03-12T16:30:00+08:00",
                                            "task_text": "推进原力OS主线收口",
                                            "skills_selected": ["ai-da-guan-jia"],
                                            "theme_id": "theme-governance",
                                            "strategy_id": strategy_id,
                                            "experiment_id": experiment_id,
                                            "workflow_id": "",
                                            "experiment_verdict": verdict,
                                            "verification_result": {
                                                "status": verification_status,
                                                "evidence": ["local proof"],
                                                "open_questions": [],
                                            },
                                            "effective_patterns": ["先把终态写清楚"],
                                            "wasted_patterns": ["没有"],
                                            "evolution_candidates": ["进入下一波"],
                                        },
                                        run_dir,
                                    )

            current = root / "strategy" / "current"
            strategy_registry = json.loads((current / "strategy-registry.json").read_text(encoding="utf-8"))
            experiment_registry = json.loads((current / "experiment-registry.json").read_text(encoding="utf-8"))
            dashboard = (current / "governance-dashboard.md").read_text(encoding="utf-8")
            transport_strategy = next(
                item for item in strategy_registry if item["strategy_id"] == "strategy-governance-transport-unblock"
            )
            mother_strategy = next(
                item for item in strategy_registry if item["strategy_id"] == "strategy-governance-mainline-closure"
            )
            transport_experiment = next(
                item
                for item in experiment_registry
                if item["experiment_id"] == "experiment-governance-transport-unblock-001"
            )

            self.assertEqual(summary["experiment_verdict"], "blocked_needs_user")
            self.assertEqual(transport_experiment["verdict"], "blocked_needs_user")
            self.assertEqual(transport_experiment["latest_verification_status"], "blocked_needs_user")
            self.assertEqual(transport_strategy["validation_state"], "blocked_needs_user")
            self.assertEqual(mother_strategy["validation_state"], "validated")
            self.assertEqual(mother_strategy["last_child_strategy_id"], "strategy-governance-transport-unblock")
            self.assertEqual(mother_strategy["last_child_verdict"], "blocked_needs_user")
            self.assertIn("- Wave 1 Complete: True", dashboard)
            self.assertIn("Recommended Next Focus: 原力茶馆-小石头的大世界 [theme-business]", dashboard)


if __name__ == "__main__":
    unittest.main()
