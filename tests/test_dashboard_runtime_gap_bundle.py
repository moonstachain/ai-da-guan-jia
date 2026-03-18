from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path("/Users/liming/Documents/codex-ai-gua-jia-01")
SCRIPT_PATH = PROJECT_ROOT / "work" / "ai-da-guan-jia" / "scripts" / "dashboard_runtime_gap_bundle.py"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class DashboardRuntimeGapBundleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module("test_dashboard_runtime_gap_bundle", SCRIPT_PATH)

    def test_field_mapping_report_detects_alias_fields(self) -> None:
        report = self.module.field_mapping_report(
            ["status", "title", "remote_reachable"],
            {
                "状态": {"field_id": "fld_status"},
                "标题": {"field_id": "fld_title"},
                "remote_reachable": {"field_id": "fld_remote"},
            },
        )
        self.assertEqual(report["exact_fields"], ["remote_reachable"])
        self.assertEqual(
            report["alias_fields"],
            [
                {"logical_field": "status", "schema_field": "状态"},
                {"logical_field": "title", "schema_field": "标题"},
            ],
        )
        self.assertFalse(report["unresolved_fields"])

    def test_write_bundle_creates_gap_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            base_config = root / "base.json"
            source_views = root / "views.json"
            binding_run = root / "binding-run.json"
            postcheck = root / "postcheck.json"
            runtime_root = root / "runtime"
            output_dir = root / "out"
            runtime_root.mkdir()

            for filename in [
                "diagnosis-03-canvas.png",
                "diagnosis-03-binding.png",
                "action-04-canvas.png",
                "action-04-binding.png",
                "miaoda-r2-binding-run.json",
                "miaoda-r2-postcheck.json",
            ]:
                (runtime_root / filename).write_text("x", encoding="utf-8")

            base_config.write_text(
                json.dumps(
                    {
                        "tables": {
                            "数据源同步表": {
                                "table_id": "tbl_source",
                                "fields": {
                                    "标题": {"field_id": "fld_title"},
                                    "状态": {"field_id": "fld_status"},
                                    "来源家族": {"field_id": "fld_family"},
                                    "remote_reachable": {"field_id": "fld_remote"},
                                    "missing_sources_snapshot": {"field_id": "fld_missing"},
                                    "connected_sources_snapshot": {"field_id": "fld_connected"},
                                },
                            },
                            "技能与能力表": {
                                "table_id": "tbl_skill",
                                "fields": {
                                    "cluster_or_actor": {"field_id": "fld_cluster"},
                                    "名称": {"field_id": "fld_name"},
                                    "routing_credit": {"field_id": "fld_credit"},
                                    "verification_strength": {"field_id": "fld_ver"},
                                    "requires_human_approval": {"field_id": "fld_approval"},
                                    "状态": {"field_id": "fld_status"},
                                },
                            },
                        },
                        "card_specs": {
                            "diagnosis": [
                                {
                                    "card_id": "diagnosis-03",
                                    "name": "数据源与证据链当前健康吗？",
                                    "type": "bar_chart",
                                    "table": "数据源同步表",
                                    "view": "diagnosis-数据源与证据链当前健康吗",
                                    "purpose": "健康分布",
                                }
                            ],
                            "action": [
                                {
                                    "card_id": "action-04",
                                    "name": "哪些能力价值高，但审批或授权摩擦仍然很大？",
                                    "type": "table",
                                    "table": "技能与能力表",
                                    "view": "action-哪些能力价值高-但审批或授权摩擦仍然很大",
                                    "purpose": "摩擦队列",
                                }
                            ],
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            source_views.write_text(
                json.dumps(
                    [
                        {
                            "card_id": "diagnosis-03",
                            "id": "view-dq-diagnosis-03",
                            "view_name": "diagnosis-数据源与证据链当前健康吗",
                            "table_name": "数据源同步表",
                            "question_id": "dq-diagnosis-03",
                            "metrics": [{"id": "m1"}],
                            "dimensions": [{"id": "d1"}],
                            "filters": ["time grain = day"],
                            "display_fields": ["status", "title", "source_family", "remote_reachable"],
                            "action_target_ids": ["source_evidence_queue"],
                        },
                        {
                            "card_id": "action-04",
                            "id": "view-dq-action-04",
                            "view_name": "action-哪些能力价值高-但审批或授权摩擦仍然很大",
                            "table_name": "技能与能力表",
                            "question_id": "dq-action-04",
                            "metrics": [{"id": "m2"}],
                            "dimensions": [{"id": "d2"}],
                            "filters": ["requires_human_approval = 是"],
                            "display_fields": ["cluster_or_actor", "name", "routing_credit", "verification_strength", "requires_human_approval", "status"],
                            "action_target_ids": ["approval_friction_queue"],
                        },
                    ],
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            binding_run.write_text(
                json.dumps(
                    {
                        "steps": [
                            {
                                "card_id": "diagnosis-03",
                                "status": "binding_evidence_captured",
                                "selected_source_view": None,
                                "title_match_mode": "semantic",
                                "matched_title": "数据源联通状态",
                                "binding_evidence_kind": "page_source_static_json",
                                "binding_truth": "binding_unproven",
                                "binding_excerpt": "observed_source_view: not_found_in_live_dom",
                            },
                            {
                                "card_id": "action-04",
                                "status": "binding_evidence_captured",
                                "selected_source_view": None,
                                "title_match_mode": "semantic",
                                "matched_title": "高价值能力摩擦",
                                "binding_evidence_kind": "page_source_static_json",
                                "binding_truth": "没绑",
                                "binding_excerpt": "observed_source_view: not_found_in_live_dom",
                            },
                        ]
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            postcheck.write_text(
                json.dumps(
                    {
                        "cards": [
                            {
                                "card_id": "diagnosis-03",
                                "source_evidence": "plan_only_not_observed_in_ui",
                                "binding_truth": "binding_unproven",
                                "binding_evidence_kind": "page_source_static_json",
                            },
                            {
                                "card_id": "action-04",
                                "source_evidence": "plan_only_not_observed_in_ui",
                                "binding_truth": "没绑",
                                "binding_evidence_kind": "page_source_static_json",
                            },
                        ]
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            context = self.module.BundleContext(
                run_id="runtime-gap-test",
                created_at="2026-03-16T10:00:00+08:00",
                output_dir=output_dir,
                base_config_path=base_config,
                source_views_path=source_views,
                binding_run_path=binding_run,
                postcheck_path=postcheck,
                runtime_output_root=runtime_root,
            )
            result = self.module.write_bundle(context)

            self.assertTrue((output_dir / "dashboard-runtime-gap-bundle.json").exists())
            self.assertTrue((output_dir / "support" / "runtime-reverify-checklist.md").exists())
            self.assertTrue((output_dir / "verify" / "verification-report.json").exists())
            self.assertEqual(result["verification"]["status"], "completed")
            bundle = result["bundle"]
            first_card = bundle["cards"][0]
            self.assertEqual(first_card["schema_field_status"]["alias_fields"][0]["schema_field"], "状态")


if __name__ == "__main__":
    unittest.main()
