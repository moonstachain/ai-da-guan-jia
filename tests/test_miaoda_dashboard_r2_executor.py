from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.miaoda_dashboard_r2_executor import (
    build_binding_plan,
    build_binding_run_result,
    build_postcheck_result,
    build_prompt_pack,
    build_refresh_packet,
    classify_action_04_truth,
    detect_auth_state,
    run_bind_cards,
    run_plan,
    run_post_check,
    run_prompt_pack,
    run_refresh_packet,
)


class MiaodaDashboardR2ExecutorTest(unittest.TestCase):
    def make_plan(self) -> dict:
        return {
            "generated_at": "2026-03-14T03:00:00+08:00",
            "base_name": "Test Base",
            "base_url": "https://example.com/base",
            "miaoda_home_url": "https://miaoda.feishu.cn/home",
            "reference_app_url": "https://miaoda.feishu.cn/app/app_demo",
            "sections": {
                "overview": {
                    "row": 1,
                    "cards": [
                        {
                            "card_id": "diagnosis-03",
                            "section": "overview",
                            "row": 1,
                            "index": 1,
                            "title": "当前系统处于什么控制态？",
                            "component_type": "table",
                            "table_name": "总控对象主表",
                            "view_name": "overview-当前系统处于什么控制态",
                            "purpose": "回答当前运行态分布。",
                            "step_id": "overview-01-当前系统处于什么控制态",
                        }
                    ],
                },
                "diagnosis": {"row": 2, "cards": []},
                "action": {
                    "row": 3,
                    "cards": [
                        {
                            "card_id": "action-04",
                            "section": "action",
                            "row": 3,
                            "index": 1,
                            "title": "如果现在开始推进，优先动作是什么？",
                            "component_type": "table",
                            "table_name": "CBM组件热图表",
                            "view_name": "action-如果现在开始推进-优先动作是什么",
                            "purpose": "回答优先动作队列。",
                            "step_id": "action-01-如果现在开始推进优先动作是什么",
                        }
                    ],
                },
            },
            "binding_steps": [
                {
                    "card_id": "diagnosis-03",
                    "section": "overview",
                    "row": 1,
                    "index": 1,
                    "title": "当前系统处于什么控制态？",
                    "component_type": "table",
                    "table_name": "总控对象主表",
                    "view_name": "overview-当前系统处于什么控制态",
                    "purpose": "回答当前运行态分布。",
                    "step_id": "overview-01-当前系统处于什么控制态",
                },
                {
                    "card_id": "action-04",
                    "section": "action",
                    "row": 3,
                    "index": 1,
                    "title": "如果现在开始推进，优先动作是什么？",
                    "component_type": "table",
                    "table_name": "CBM组件热图表",
                    "view_name": "action-如果现在开始推进-优先动作是什么",
                    "purpose": "回答优先动作队列。",
                    "step_id": "action-01-如果现在开始推进优先动作是什么",
                },
            ],
        }

    def test_build_binding_plan_preserves_section_order(self) -> None:
        spec = {
            "base_name": "Test Base",
            "base_url": "https://example.com/base",
            "card_specs": {
                "overview": [
                    {
                        "card_id": "overview-01",
                        "name": "当前系统处于什么控制态？",
                        "type": "table",
                        "table": "总控对象主表",
                        "view": "overview-当前系统处于什么控制态",
                        "purpose": "回答当前运行态分布。",
                    }
                ],
                "diagnosis": [
                    {
                        "card_id": "diagnosis-01",
                        "name": "当前主会场到底在推什么？",
                        "type": "table",
                        "table": "线程总表",
                        "view": "diagnosis-当前主会场到底在推什么",
                        "purpose": "回答当前主会场推进对象。",
                    }
                ],
                "action": [
                    {
                        "card_id": "action-01",
                        "name": "如果现在开始推进，优先动作是什么？",
                        "type": "table",
                        "table": "CBM组件热图表",
                        "view": "action-如果现在开始推进-优先动作是什么",
                        "purpose": "回答优先动作队列。",
                    }
                ],
            },
        }

        plan = build_binding_plan(
            spec,
            miaoda_home_url="https://miaoda.feishu.cn/home",
            reference_app_url="https://miaoda.feishu.cn/app/app_demo",
        )

        self.assertEqual(plan["sections"]["overview"]["row"], 1)
        self.assertEqual(plan["sections"]["diagnosis"]["row"], 2)
        self.assertEqual(plan["sections"]["action"]["row"], 3)
        self.assertEqual(len(plan["binding_steps"]), 3)
        self.assertEqual(plan["binding_steps"][0]["card_id"], "overview-01")
        self.assertEqual(plan["binding_steps"][0]["title"], "当前系统处于什么控制态？")
        self.assertEqual(plan["binding_steps"][2]["table_name"], "CBM组件热图表")

    def test_run_plan_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "spec.json"
            artifact_dir = root / "artifacts"
            spec_path.write_text(
                json.dumps(
                    {
                        "base_name": "Test Base",
                        "base_url": "https://example.com/base",
                        "cards": {"overview": [], "diagnosis": [], "action": []},
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            args = SimpleNamespace(
                spec_file=str(spec_path),
                artifact_dir=str(artifact_dir),
                miaoda_home_url="https://miaoda.feishu.cn/home",
                reference_app_url="https://miaoda.feishu.cn/app/app_demo",
            )

            exit_code = run_plan(args)
            self.assertEqual(exit_code, 0)
            self.assertTrue((artifact_dir / "miaoda-r2-binding-plan.json").exists())
            self.assertTrue((artifact_dir / "miaoda-r2-binding-plan.md").exists())

    def test_prompt_pack_contains_card_mapping(self) -> None:
        plan = self.make_plan()
        text = build_prompt_pack(plan)
        self.assertIn("Miaoda R2 Prompt Pack", text)
        self.assertIn("当前系统处于什么控制态？", text)
        self.assertIn("总控对象主表 / overview-当前系统处于什么控制态", text)

    def test_run_prompt_pack_writes_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path = root / "plan.json"
            artifact_dir = root / "artifacts"
            plan_path.write_text(
                json.dumps(
                    {
                        "generated_at": "2026-03-14T03:00:00+08:00",
                        "base_name": "Test Base",
                        "base_url": "https://example.com/base",
                        "miaoda_home_url": "https://miaoda.feishu.cn/home",
                        "reference_app_url": "https://miaoda.feishu.cn/app/app_demo",
                        "sections": {
                            "overview": {"row": 1, "cards": []},
                            "diagnosis": {"row": 2, "cards": []},
                            "action": {"row": 3, "cards": []},
                        },
                        "binding_steps": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            args = SimpleNamespace(plan_file=str(plan_path), artifact_dir=str(artifact_dir))
            exit_code = run_prompt_pack(args)
            self.assertEqual(exit_code, 0)
            self.assertTrue((artifact_dir / "miaoda-r2-prompt-pack.md").exists())

    def test_build_refresh_packet_focuses_on_m3_cards(self) -> None:
        spec = {
            "base_name": "Test Base",
            "card_specs": {
                "diagnosis": [
                    {
                        "card_id": "diagnosis-03",
                        "name": "数据源与证据链当前健康吗？",
                        "type": "bar_chart",
                        "table": "数据源同步表",
                        "view": "diagnosis-数据源与证据链当前健康吗",
                        "purpose": "回答健康分布。",
                    }
                ],
                "action": [
                    {
                        "card_id": "action-04",
                        "name": "哪些能力价值高，但审批或授权摩擦仍然很大？",
                        "type": "table",
                        "table": "技能与能力表",
                        "view": "action-哪些能力价值高-但审批或授权摩擦仍然很大",
                        "purpose": "回答审批摩擦。",
                    }
                ],
            },
            "view_specs": [
                {"card_id": "diagnosis-03", "view_name": "diagnosis-数据源与证据链当前健康吗"},
                {
                    "card_id": "action-04",
                    "view_name": "action-哪些能力价值高-但审批或授权摩擦仍然很大",
                    "conditions": [{"field": "requires_human_approval", "operator": "is", "values": ["是"]}],
                },
            ],
        }
        source_views = [
            {
                "card_id": "diagnosis-03",
                "question_id": "dq-diagnosis-03",
                "metrics": [{"id": "source_health_issue_count"}],
                "dimensions": [{"id": "source_health_state"}],
                "action_target_ids": ["source_evidence_queue"],
                "filters": ["time grain = day"],
                "display_fields": ["status", "title"],
            },
            {
                "card_id": "action-04",
                "question_id": "dq-action-04",
                "metrics": [{"id": "approval_friction_count"}],
                "dimensions": [{"id": "capability_cluster"}],
                "action_target_ids": ["approval_friction_queue"],
                "filters": ["requires_human_approval = 是"],
                "display_fields": ["name", "routing_credit", "verification_strength"],
            },
        ]

        packet = build_refresh_packet(spec, source_views)

        self.assertEqual(packet["focus_card_ids"], ["diagnosis-03", "action-04"])
        self.assertEqual(packet["cards"][0]["card_id"], "diagnosis-03")
        self.assertEqual(packet["cards"][0]["contract_filters"], ["time grain = day"])
        self.assertEqual(packet["cards"][0]["screenshot_plan"]["captures"][0]["filename"], "diagnosis-03-canvas.png")
        self.assertEqual(packet["cards"][1]["card_id"], "action-04")
        self.assertEqual(packet["cards"][1]["contract_filters"], ["requires_human_approval = 是"])
        self.assertEqual(packet["cards"][1]["action_target_ids"], ["approval_friction_queue"])
        self.assertEqual(packet["cards"][1]["screenshot_plan"]["captures"][1]["filename"], "action-04-binding.png")

    def test_run_refresh_packet_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "spec.json"
            source_views_path = root / "source-views.json"
            artifact_dir = root / "artifacts"
            spec_path.write_text(
                json.dumps(
                    {
                        "base_name": "Test Base",
                        "card_specs": {
                            "diagnosis": [
                                {
                                    "card_id": "diagnosis-03",
                                    "name": "数据源与证据链当前健康吗？",
                                    "type": "bar_chart",
                                    "table": "数据源同步表",
                                    "view": "diagnosis-数据源与证据链当前健康吗",
                                    "purpose": "回答健康分布。",
                                }
                            ],
                            "action": [
                                {
                                    "card_id": "action-04",
                                    "name": "哪些能力价值高，但审批或授权摩擦仍然很大？",
                                    "type": "table",
                                    "table": "技能与能力表",
                                    "view": "action-哪些能力价值高-但审批或授权摩擦仍然很大",
                                    "purpose": "回答审批摩擦。",
                                }
                            ],
                        },
                        "view_specs": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            source_views_path.write_text(
                json.dumps(
                    [
                        {"card_id": "diagnosis-03", "question_id": "dq-diagnosis-03", "metrics": [], "dimensions": [], "action_target_ids": [], "filters": ["time grain = day"], "display_fields": []},
                        {"card_id": "action-04", "question_id": "dq-action-04", "metrics": [], "dimensions": [], "action_target_ids": ["approval_friction_queue"], "filters": ["requires_human_approval = 是"], "display_fields": []},
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            args = SimpleNamespace(spec_file=str(spec_path), source_views_file=str(source_views_path), artifact_dir=str(artifact_dir))

            exit_code = run_refresh_packet(args)

            self.assertEqual(exit_code, 0)
            self.assertTrue((artifact_dir / "miaoda-r2-refresh-packet.json").exists())
            self.assertTrue((artifact_dir / "miaoda-r2-refresh-packet.md").exists())

    def test_detect_auth_state_flags_login(self) -> None:
        self.assertEqual(
            detect_auth_state("https://accounts.feishu.cn/accounts/page/login", "扫码登录"),
            "login_required",
        )
        self.assertEqual(
            detect_auth_state("https://miaoda.feishu.cn/app/demo", "妙搭页面"),
            "authenticated_or_partial",
        )

    def test_classify_action_04_truth_distinguishes_binding_states(self) -> None:
        self.assertEqual(
            classify_action_04_truth(
                observed_source_view="",
                expected_source_view="action-哪些能力价值高-但审批或授权摩擦仍然很大",
                binding_evidence_path="",
                binding_excerpt="",
            ),
            "没绑",
        )
        self.assertEqual(
            classify_action_04_truth(
                observed_source_view="action-别的视图",
                expected_source_view="action-哪些能力价值高-但审批或授权摩擦仍然很大",
                binding_evidence_path="/tmp/action-04-binding.png",
                binding_excerpt="action-别的视图",
            ),
            "绑错 source view",
        )
        self.assertEqual(
            classify_action_04_truth(
                observed_source_view="action-哪些能力价值高-但审批或授权摩擦仍然很大",
                expected_source_view="action-哪些能力价值高-但审批或授权摩擦仍然很大",
                binding_evidence_path="/tmp/action-04-binding.png",
                binding_excerpt="暂无数据",
            ),
            "绑了但没数据",
        )
        self.assertEqual(
            classify_action_04_truth(
                observed_source_view="action-哪些能力价值高-但审批或授权摩擦仍然很大",
                expected_source_view="action-哪些能力价值高-但审批或授权摩擦仍然很大",
                binding_evidence_path="/tmp/action-04-binding.png",
                binding_excerpt="routing_credit verification_strength",
            ),
            "已正确绑定",
        )

    def test_build_binding_run_result_stays_honest_when_only_shell_detected(self) -> None:
        plan = self.make_plan()
        surface = {
            "target_url": "https://miaoda.feishu.cn/app/demo",
            "final_url": "https://miaoda.feishu.cn/app/demo",
            "title": "妙搭 Demo",
            "auth_state": "authenticated_or_partial",
            "surface_state": "builder_or_shell_detected",
            "surface_markers": ["妙搭", "页面", "组件"],
            "visible_titles": [],
            "screenshot": "/tmp/bind.png",
        }
        result = build_binding_run_result(plan, surface)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["r2_state"], "failed_partial")
        self.assertEqual(result["binding_mode"], "placeholder_shell_only")
        self.assertEqual(result["steps"][0]["status"], "pending_surface_specific_binding")

    def test_build_binding_run_result_captures_phase2_evidence_and_action04_classification(self) -> None:
        plan = self.make_plan()
        surface = {
            "target_url": "https://miaoda.feishu.cn/app/demo",
            "final_url": "https://miaoda.feishu.cn/app/demo",
            "title": "妙搭 Demo",
            "auth_state": "authenticated_or_partial",
            "surface_state": "existing_cards_visible",
            "surface_markers": ["妙搭", "页面"],
            "visible_titles": [],
            "screenshot": "/tmp/bind.png",
            "card_observations": {
                "diagnosis-03": {
                    "canvas_evidence_path": "/tmp/diagnosis-03-canvas.png",
                    "binding_evidence_path": "/tmp/diagnosis-03-binding.png",
                    "observed_source_view": "overview-当前系统处于什么控制态",
                    "binding_truth": "wrong_source_view",
                    "binding_excerpt": "overview-当前系统处于什么控制态",
                },
                "action-04": {
                    "canvas_evidence_path": "/tmp/action-04-canvas.png",
                    "binding_evidence_path": "/tmp/action-04-binding.png",
                    "observed_source_view": "action-哪些能力价值高-但审批或授权摩擦仍然很大",
                    "binding_truth": "绑了但没数据",
                    "binding_excerpt": "暂无数据",
                },
            },
        }

        result = build_binding_run_result(plan, surface)

        self.assertEqual(result["steps"][0]["status"], "binding_evidence_captured")
        self.assertEqual(result["steps"][0]["binding_truth"], "wrong_source_view")
        self.assertEqual(result["steps"][0]["binding_evidence_kind"], "")
        self.assertEqual(result["steps"][1]["status"], "binding_evidence_captured")
        self.assertEqual(result["steps"][1]["binding_truth"], "绑了但没数据")
        self.assertEqual(result["steps"][1]["selected_source_view"], "action-哪些能力价值高-但审批或授权摩擦仍然很大")
        self.assertEqual(result["binding_mode"], "existing_visible_cards")
        self.assertEqual(result["r2_state"], "ready_for_post_check")

    def test_build_postcheck_requires_more_than_plan_only_evidence(self) -> None:
        plan = self.make_plan()
        binding_run = {
            "steps": [
                {
                    "step_id": "overview-01-当前系统处于什么控制态",
                    "status": "title_already_visible",
                    "selected_source_view": None,
                },
                {
                    "step_id": "action-01-如果现在开始推进优先动作是什么",
                    "status": "pending_surface_specific_binding",
                    "selected_source_view": None,
                },
            ]
        }
        surface = {
            "target_url": "https://miaoda.feishu.cn/app/demo",
            "final_url": "https://miaoda.feishu.cn/app/demo",
            "title": "妙搭 Demo",
            "auth_state": "authenticated_or_partial",
            "surface_state": "existing_cards_visible",
            "surface_markers": ["妙搭", "页面"],
            "visible_titles": ["当前系统处于什么控制态？"],
            "screenshot": "/tmp/postcheck.png",
        }
        result = build_postcheck_result(plan, binding_run, surface)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["verification_state"], "failed_partial")
        self.assertEqual(result["cards_visible"], 1)
        self.assertEqual(result["cards"][0]["source_evidence"], "plan_only_not_observed_in_ui")

    def test_build_postcheck_uses_non_plan_only_binding_evidence_for_phase2_cards(self) -> None:
        plan = self.make_plan()
        binding_run = {
            "steps": [
                {
                    "step_id": "overview-01-当前系统处于什么控制态",
                    "card_id": "diagnosis-03",
                    "status": "binding_evidence_captured",
                    "selected_source_view": "diagnosis-数据源与证据链当前健康吗",
                    "canvas_evidence_path": "/tmp/diagnosis-03-canvas.png",
                    "binding_evidence_path": "/tmp/diagnosis-03-binding.png",
                    "binding_truth": "correctly_bound",
                },
                {
                    "step_id": "action-01-如果现在开始推进优先动作是什么",
                    "card_id": "action-04",
                    "status": "binding_evidence_captured",
                    "selected_source_view": "action-哪些能力价值高-但审批或授权摩擦仍然很大",
                    "canvas_evidence_path": "/tmp/action-04-canvas.png",
                    "binding_evidence_path": "/tmp/action-04-binding.png",
                    "binding_truth": "已正确绑定",
                },
            ]
        }
        surface = {
            "target_url": "https://miaoda.feishu.cn/app/demo",
            "final_url": "https://miaoda.feishu.cn/app/demo",
            "title": "妙搭 Demo",
            "auth_state": "authenticated_or_partial",
            "surface_state": "existing_cards_visible",
            "surface_markers": ["妙搭", "页面"],
            "visible_titles": [],
            "screenshot": "/tmp/postcheck.png",
            "card_observations": {},
        }

        result = build_postcheck_result(plan, binding_run, surface)

        self.assertEqual(result["verification_state"], "completed")
        self.assertEqual(result["cards"][0]["source_evidence"], "diagnosis-数据源与证据链当前健康吗")
        self.assertEqual(result["cards"][0]["binding_evidence_path"], "/tmp/diagnosis-03-binding.png")
        self.assertEqual(result["cards"][1]["binding_truth"], "已正确绑定")

    def test_build_postcheck_accepts_equivalent_binding_evidence_from_card_shell_metadata(self) -> None:
        plan = self.make_plan()
        surface = {
            "target_url": "https://miaoda.feishu.cn/app/demo",
            "final_url": "https://miaoda.feishu.cn/app/demo",
            "title": "妙搭 Demo",
            "auth_state": "authenticated_or_partial",
            "surface_state": "existing_cards_visible",
            "surface_markers": ["妙搭", "页面"],
            "visible_titles": [],
            "screenshot": "/tmp/postcheck.png",
            "card_observations": {
                "diagnosis-03": {
                    "canvas_evidence_path": "/tmp/diagnosis-03-canvas.png",
                    "binding_evidence_path": "/tmp/diagnosis-03-binding.png",
                    "binding_evidence_kind": "card_shell_metadata",
                    "observed_source_view": "overview-当前系统处于什么控制态",
                    "binding_truth": "wrong_source_view",
                },
                "action-04": {
                    "canvas_evidence_path": "/tmp/action-04-canvas.png",
                    "binding_evidence_path": "/tmp/action-04-binding.png",
                    "binding_evidence_kind": "card_shell_metadata",
                    "observed_source_view": "action-哪些能力价值高-但审批或授权摩擦仍然很大",
                    "binding_truth": "已正确绑定",
                },
            },
        }

        result = build_postcheck_result(plan, None, surface)

        self.assertEqual(result["verification_state"], "completed")
        self.assertEqual(result["cards"][0]["binding_evidence_kind"], "card_shell_metadata")
        self.assertEqual(result["cards"][1]["binding_truth"], "已正确绑定")

    def test_build_postcheck_keeps_semantic_canvas_and_static_binding_overlay_as_partial(self) -> None:
        plan = self.make_plan()
        surface = {
            "target_url": "https://miaoda.feishu.cn/app/demo",
            "final_url": "https://miaoda.feishu.cn/app/demo",
            "title": "妙搭 Demo",
            "auth_state": "authenticated_or_partial",
            "surface_state": "existing_cards_visible",
            "surface_markers": ["妙搭", "页面"],
            "visible_titles": [],
            "screenshot": "/tmp/postcheck.png",
            "card_observations": {
                "diagnosis-03": {
                    "canvas_evidence_path": "/tmp/diagnosis-03-canvas.png",
                    "title_match_mode": "semantic",
                    "matched_title": "数据源联通状态",
                    "binding_evidence_path": "/tmp/diagnosis-03-binding.png",
                    "binding_evidence_kind": "page_source_static_json",
                    "observed_source_view": "",
                    "binding_truth": "binding_unproven",
                },
                "action-04": {
                    "canvas_evidence_path": "/tmp/action-04-canvas.png",
                    "title_match_mode": "semantic",
                    "matched_title": "高价值能力摩擦",
                    "binding_evidence_path": "/tmp/action-04-binding.png",
                    "binding_evidence_kind": "page_source_static_json",
                    "observed_source_view": "",
                    "binding_truth": "没绑",
                },
            },
        }

        result = build_postcheck_result(plan, None, surface)

        self.assertEqual(result["verification_state"], "failed_partial")
        self.assertFalse(result["cards"][0]["title_visible"])
        self.assertEqual(result["cards"][0]["source_evidence"], "plan_only_not_observed_in_ui")
        self.assertEqual(result["cards"][1]["binding_truth"], "没绑")

    def test_run_bind_cards_writes_blocked_result_file(self) -> None:
        plan = self.make_plan()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_dir = root / "artifacts"
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

            args = SimpleNamespace(
                plan_file=str(plan_path),
                dashboard_url="https://miaoda.feishu.cn/app/app_demo",
                artifact_dir=str(artifact_dir),
                chrome_root="/tmp/chrome",
                profile_name="Profile 1",
                chrome_binary="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            )

            with patch("scripts.miaoda_dashboard_r2_executor.capture_surface_state") as mock_capture:
                mock_capture.return_value = {
                    "target_url": args.dashboard_url,
                    "final_url": "https://accounts.feishu.cn/accounts/page/login",
                    "title": "登录",
                    "auth_state": "login_required",
                    "surface_state": "login_required",
                    "surface_markers": [],
                    "visible_titles": [],
                    "screenshot": "/tmp/bind.png",
                }
                exit_code = run_bind_cards(args)

            self.assertEqual(exit_code, 0)
            result = json.loads((artifact_dir / "miaoda-r2-binding-run.json").read_text(encoding="utf-8"))
            self.assertEqual(result["r2_state"], "blocked_needs_user")
            self.assertEqual(result["steps"][0]["status"], "skipped_login_required")

    def test_run_post_check_writes_json(self) -> None:
        plan = self.make_plan()
        binding_run = {
            "steps": [
                {
                    "step_id": "overview-01-当前系统处于什么控制态",
                    "status": "title_already_visible",
                    "selected_source_view": None,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_dir = root / "artifacts"
            plan_path = root / "plan.json"
            binding_run_path = root / "binding-run.json"
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            binding_run_path.write_text(json.dumps(binding_run, ensure_ascii=False, indent=2), encoding="utf-8")

            args = SimpleNamespace(
                plan_file=str(plan_path),
                binding_run_file=str(binding_run_path),
                dashboard_url="https://miaoda.feishu.cn/app/app_demo",
                artifact_dir=str(artifact_dir),
                chrome_root="/tmp/chrome",
                profile_name="Profile 1",
                chrome_binary="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            )

            with patch("scripts.miaoda_dashboard_r2_executor.capture_surface_state") as mock_capture:
                mock_capture.return_value = {
                    "target_url": args.dashboard_url,
                    "final_url": args.dashboard_url,
                    "title": "妙搭 Demo",
                    "auth_state": "authenticated_or_partial",
                    "surface_state": "existing_cards_visible",
                    "surface_markers": ["妙搭", "页面"],
                    "visible_titles": ["当前系统处于什么控制态？"],
                    "screenshot": "/tmp/postcheck.png",
                }
                exit_code = run_post_check(args)

            self.assertEqual(exit_code, 0)
            result = json.loads((artifact_dir / "miaoda-r2-postcheck.json").read_text(encoding="utf-8"))
            self.assertEqual(result["verification_state"], "failed_partial")
            self.assertEqual(result["cards_visible"], 1)


if __name__ == "__main__":
    unittest.main()
