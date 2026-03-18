from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from yuanli_governance import yuanli_os_control as control


class YuanliOsControlNativeSyncTest(unittest.TestCase):
    def test_human_manual_pending_maps_to_wait_human_segment(self) -> None:
        self.assertEqual(control._derive_segment("human_manual_pending"), "wait_human")

    def test_date_fields_use_feishu_date_type_and_unix_seconds(self) -> None:
        self.assertEqual(control._bitable_field_type_id("date"), 5)
        self.assertEqual(control._to_date_value("2026-03-11"), 1773158400)
        self.assertEqual(control._to_date_value(1773244800000), 1773244800)

    def test_resolve_bitable_app_token_from_wiki_link(self) -> None:
        with patch.object(
            control,
            "_feishu_api",
            return_value={
                "code": 0,
                "data": {
                    "node": {
                        "obj_type": "bitable",
                        "obj_token": "app_wiki_123",
                    }
                },
            },
        ) as mocked_api:
            app_token = control._resolve_bitable_app_token(
                "https://h52xu4gwob.feishu.cn/wiki/C4kWwmXI8i6E6rkQ7i8cVlsyn1e?from=from_copylink",
                token="tenant-token",
            )

        self.assertEqual(app_token, "app_wiki_123")
        mocked_api.assert_called_once()

    def test_sync_base_prefers_native_path_when_app_token_resolves(self) -> None:
        with (
            patch.dict("os.environ", {"FEISHU_APP_ID": "cli_test", "FEISHU_APP_SECRET": "secret"}, clear=False),
            patch.object(control, "_is_test_feishu_stub_env", return_value=False),
            patch.object(control, "_feishu_tenant_access_token", return_value="tenant-token"),
            patch.object(control, "_resolve_bitable_app_token", return_value="app_token_123"),
            patch.object(
                control,
                "_sync_base_via_base_link",
                return_value={
                    "status": "completed",
                    "script": "native_openapi_base_link",
                    "schema_preview": {"mode": "native_base_link", "tables": []},
                    "schema_apply": {"mode": "native_base_link", "tables": []},
                    "tables": [],
                },
            ) as mocked_native,
        ):
            result = control._sync_base(
                {},
                link="https://h52xu4gwob.feishu.cn/wiki/C4kWwmXI8i6E6rkQ7i8cVlsyn1e?from=from_copylink",
                schema_manifest_path=Path("/tmp/schema-manifest.json"),
                payloads={},
            )

        self.assertEqual(result["status"], "completed")
        mocked_native.assert_called_once_with(
            "https://h52xu4gwob.feishu.cn/wiki/C4kWwmXI8i6E6rkQ7i8cVlsyn1e?from=from_copylink",
            payloads={},
            token="tenant-token",
            app_token="app_token_123",
        )

    def test_sync_base_via_base_link_tolerates_duplicate_field_name(self) -> None:
        spec = {
            "table_id": "field_dictionary",
            "table_name": "字段字典与术语表",
            "primary": {"name": "术语Key", "type": "text"},
            "fields": [{"name": "字段用途", "type": "text"}],
            "views": ["全部"],
        }
        payloads = {"field_dictionary": [{"术语Key": "term-001", "字段用途": "治理字段"}]}

        tables: dict[str, dict[str, str]] = {}
        fields_by_table: dict[str, list[dict[str, object]]] = {}
        views_by_table: dict[str, list[dict[str, object]]] = {}
        records_by_table: dict[str, list[dict[str, object]]] = {}
        duplicate_once = {"字段用途": True}

        def list_tables(app_token: str, *, token: str) -> list[dict[str, object]]:
            return [{"table_id": table_id, "name": meta["name"]} for table_id, meta in tables.items()]

        def create_table(app_token: str, table_name: str, *, token: str) -> dict[str, object]:
            table_id = "tbl_field_dict"
            tables[table_id] = {"name": table_name}
            fields_by_table[table_id] = [{"field_id": "fld_default", "field_name": "默认列", "type": 1}]
            views_by_table[table_id] = [{"view_id": "vew_default", "view_name": "默认视图"}]
            records_by_table[table_id] = []
            return {"table_id": table_id, "name": table_name}

        def list_fields(app_token: str, table_id: str, *, token: str) -> list[dict[str, object]]:
            return [dict(item) for item in fields_by_table[table_id]]

        def update_field(app_token: str, table_id: str, field_id: str, *, token: str, field_name: str, field_type: int) -> dict[str, object]:
            for field in fields_by_table[table_id]:
                if field["field_id"] == field_id:
                    field["field_name"] = field_name
                    field["type"] = field_type
                    return dict(field)
            raise AssertionError(f"unknown field id: {field_id}")

        def create_field(app_token: str, table_id: str, field_name: str, *, token: str, field_type: int) -> dict[str, object]:
            if duplicate_once.get(field_name):
                duplicate_once[field_name] = False
                fields_by_table[table_id].append({"field_id": "fld_usage", "field_name": field_name, "type": field_type})
                raise RuntimeError('Feishu API error for /fields: {"code": 1254014, "msg": "FieldNameDuplicated"}')
            field = {"field_id": f"fld_{len(fields_by_table[table_id]) + 1}", "field_name": field_name, "type": field_type}
            fields_by_table[table_id].append(field)
            return field

        def list_views(app_token: str, table_id: str, *, token: str) -> list[dict[str, object]]:
            return [dict(item) for item in views_by_table[table_id]]

        def update_view(app_token: str, table_id: str, view_id: str, *, token: str, view_name: str) -> dict[str, object]:
            for view in views_by_table[table_id]:
                if view["view_id"] == view_id:
                    view["view_name"] = view_name
                    return dict(view)
            raise AssertionError(f"unknown view id: {view_id}")

        def create_view(app_token: str, table_id: str, view_name: str, *, token: str) -> dict[str, object]:
            view = {"view_id": f"vew_{len(views_by_table[table_id]) + 1}", "view_name": view_name}
            views_by_table[table_id].append(view)
            return view

        def list_records(app_token: str, table_id: str, *, token: str) -> list[dict[str, object]]:
            return [dict(item) for item in records_by_table[table_id]]

        def batch_create_records(app_token: str, table_id: str, rows: list[dict[str, object]], *, token: str) -> dict[str, object]:
            for index, row in enumerate(rows, start=1):
                records_by_table[table_id].append({"record_id": f"rec_{index}", "fields": dict(row)})
            return {"records": rows}

        def batch_update_records(app_token: str, table_id: str, rows: list[dict[str, object]], *, token: str) -> dict[str, object]:
            return {"records": rows}

        with (
            patch.object(control, "CONTROL_BASE_TABLE_SPECS", [spec]),
            patch.object(control, "_bitable_list_tables", side_effect=list_tables),
            patch.object(control, "_bitable_create_table", side_effect=create_table),
            patch.object(control, "_bitable_list_fields", side_effect=list_fields),
            patch.object(control, "_bitable_update_field", side_effect=update_field),
            patch.object(control, "_bitable_create_field", side_effect=create_field),
            patch.object(control, "_bitable_list_views", side_effect=list_views),
            patch.object(control, "_bitable_update_view", side_effect=update_view),
            patch.object(control, "_bitable_create_view", side_effect=create_view),
            patch.object(control, "_bitable_list_records", side_effect=list_records),
            patch.object(control, "_bitable_batch_create_records", side_effect=batch_create_records),
            patch.object(control, "_bitable_batch_update_records", side_effect=batch_update_records),
        ):
            result = control._sync_base_via_base_link(
                "https://h52xu4gwob.feishu.cn/base/app_test?from=from_copylink",
                payloads=payloads,
                token="tenant-token",
                app_token="app_test",
            )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(records_by_table["tbl_field_dict"][0]["fields"]["术语Key"], "term-001")
        self.assertEqual(
            {field["field_name"] for field in fields_by_table["tbl_field_dict"]},
            {"术语Key", "字段用途"},
        )

    def test_sync_base_via_base_link_omits_empty_date_field_values(self) -> None:
        spec = {
            "table_id": "threads",
            "table_name": "线程总表",
            "primary": {"name": "Thread ID", "type": "text"},
            "fields": [{"name": "下次复查日", "type": "date"}],
            "views": ["全部"],
        }
        payloads = {"threads": [{"Thread ID": "thread-empty-date", "下次复查日": ""}]}

        created_rows: list[dict[str, object]] = []

        with (
            patch.object(control, "CONTROL_BASE_TABLE_SPECS", [spec]),
            patch.object(control, "_bitable_list_tables", return_value=[{"table_id": "tbl_threads", "name": "线程总表"}]),
            patch.object(
                control,
                "_bitable_list_fields",
                return_value=[
                    {"field_id": "fld_thread_id", "field_name": "Thread ID", "type": 1},
                    {"field_id": "fld_next_review", "field_name": "下次复查日", "type": 5},
                ],
            ),
            patch.object(control, "_bitable_list_views", return_value=[{"view_id": "vew_all", "view_name": "全部"}]),
            patch.object(control, "_bitable_list_records", return_value=[]),
            patch.object(
                control,
                "_bitable_batch_create_records",
                side_effect=lambda app_token, table_id, rows, *, token: created_rows.extend(rows) or {"records": rows},
            ),
            patch.object(control, "_bitable_batch_update_records", return_value={"records": []}),
        ):
            result = control._sync_base_via_base_link(
                "https://h52xu4gwob.feishu.cn/base/app_test?from=from_copylink",
                payloads=payloads,
                token="tenant-token",
                app_token="app_test",
            )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(created_rows, [{"Thread ID": "thread-empty-date"}])

    def test_strategic_linkage_rows_include_sales_execute_plan(self) -> None:
        context = {
            "goals": {"G1": {"id": "G1", "title": "治理操作系统化"}},
            "themes": {"theme-business": {"id": "theme-business", "theme": "业务执行"}},
            "strategies": {"strategy-business-sales-execute-v1": {"strategy_id": "strategy-business-sales-execute-v1", "title": "Sales Execute 做实"}},
            "experiments": {"experiment-business-sales-execute-v1-001": {"experiment_id": "experiment-business-sales-execute-v1-001", "title": "Sales Execute v1"}},
            "workflows": {"workflow-business-sales-execute-v1": {"workflow_id": "workflow-business-sales-execute-v1", "title": "Sales Workflow v1"}},
            "initiatives": [],
            "canonical_threads": [],
            "cbm_rows": [],
            "sales_execute_plan": {
                "goal_id": "G1",
                "theme_id": "theme-business",
                "strategy_id": "strategy-business-sales-execute-v1",
                "experiment_id": "experiment-business-sales-execute-v1-001",
                "workflow_id": "workflow-business-sales-execute-v1",
                "component_domain": "销售成交",
                "control_level": "execute",
                "status": "in_progress",
                "owner_mode": "hybrid",
                "kpi_heatmap": {
                    "priority_band": "P1",
                    "current_gap": ["真实 business writeback 仍未发生"],
                    "next_action": "先把 sales action catalog 和 execute writeback schema 固化，再接 live KPI source。",
                    "evidence_strength": "medium",
                    "kpis": [{"title": "线索数"}],
                },
                "evidence_refs": ["generated://sales-execute"],
                "source_ref": "/tmp/execute-sales-v1.json",
                "updated_at": "2026-03-14T09:18:00+08:00",
            },
        }

        rows = control._build_strategic_linkage_rows(context)

        sales_row = next(
            item for item in rows if item["strategy_id"] == "strategy-business-sales-execute-v1"
        )
        self.assertEqual(sales_row["component_domain"], "销售成交")
        self.assertEqual(sales_row["control_level_scope"], "execute")
        self.assertEqual(sales_row["status"], "in_progress")
        self.assertEqual(sales_row["next_action"], "先把 sales action catalog 和 execute writeback schema 固化，再接 live KPI source。")

    def test_component_heatmap_rows_enrich_sales_execute_from_plan(self) -> None:
        inventory = {
            "operating_modules": [
                {
                    "module_id": "module-sales",
                    "module_code": "sales",
                    "title": "销售成交",
                    "status": "active",
                    "owner_subject_id": "subject-collab-owner",
                    "ai_subject_id": "subject-agent-sales",
                }
            ]
        }
        context = {
            "cbm_rows": [
                {
                    "component_domain": "销售成交",
                    "control_level": "execute",
                    "goal_id": "G1",
                    "theme_id": "theme-business",
                    "strategy_id": "",
                    "experiment_id": "",
                    "workflow_id": "",
                    "entity_refs": [
                        {
                            "entity_type": "operating_module",
                            "entity_id": "module-sales",
                            "title": "销售成交",
                            "status": "active",
                        }
                    ],
                    "action_refs": [],
                    "kpi_refs": ["商机推进、报价、成交额"],
                    "evidence_refs": ["generated://module/sales"],
                    "coverage_status": "partial",
                    "gap_notes": ["热图 / 投资优先级还没有与 module-sales 形成一等字段绑定。"],
                }
            ],
            "experiments": {},
            "subjects_by_id": {
                "subject-collab-owner": {"title": "共同治理者"},
                "subject-agent-sales": {"title": "Sales Copilot"},
            },
            "decisions_by_id": {},
            "writebacks_by_id": {},
            "sales_execute_plan": {
                "goal_id": "G1",
                "theme_id": "theme-business",
                "strategy_id": "strategy-business-sales-execute-v1",
                "experiment_id": "experiment-business-sales-execute-v1-001",
                "workflow_id": "workflow-business-sales-execute-v1",
                "component_domain": "销售成交",
                "control_level": "execute",
                "status": "in_progress",
                "owner_mode": "hybrid",
                "kpi_heatmap": {
                    "priority_band": "P1",
                    "current_gap": ["真实 business writeback 仍未发生，当前只有 schema-first scaffold。"],
                    "next_action": "先把 sales action catalog 和 execute writeback schema 固化，再接 live KPI source。",
                    "evidence_strength": "medium",
                    "kpis": [{"title": "线索数"}, {"title": "报价吞吐"}],
                },
                "evidence_refs": ["/tmp/execute-sales-v1.json"],
                "source_ref": "/tmp/execute-sales-v1.json",
                "updated_at": "2026-03-14T09:18:00+08:00",
            },
        }

        rows = control._build_cbm_component_heatmap_rows(inventory, context, [], [])

        sales_row = next(
            item
            for item in rows
            if item["component_domain"] == "销售成交" and item["control_level"] == "execute"
        )
        self.assertEqual(sales_row["priority_band"], "P1")
        self.assertIn("sales action catalog", sales_row["next_action"])
        self.assertEqual(sales_row["status"], "in_progress")
        self.assertEqual(sales_row["latest_writeback_id"], "")
        self.assertEqual(sales_row["owner_mode"], "hybrid")

    def test_derive_runtime_context_and_heatmap_upgrade_sales_execute_from_live_orders(self) -> None:
        inventory = {
            "operating_modules": [
                {
                    "module_id": "module-sales",
                    "module_code": "sales",
                    "title": "销售成交",
                    "status": "active",
                    "owner_subject_id": "subject-collab-owner",
                    "ai_subject_id": "subject-agent-sales",
                }
            ],
            "subjects": [
                {"subject_id": "subject-collab-owner", "title": "共同治理者"},
                {"subject_id": "subject-agent-sales", "title": "Sales Copilot"},
            ],
            "orders": [
                {
                    "order_id": "ord-001",
                    "module_code": "sales",
                    "opportunity_id": "opp-001",
                    "lead_owner": "施子超",
                    "primary_conversion_owner": "施子超",
                },
                {
                    "order_id": "ord-002",
                    "module_code": "sales",
                    "opportunity_id": "",
                    "lead_owner": "",
                    "primary_conversion_owner": "",
                },
            ],
            "decision_records": [
                {
                    "decision_id": "decision-ord-002-won",
                    "title": "确认订单 ord-002 已形成赢单证据",
                }
            ],
            "writeback_events": [
                {
                    "writeback_id": "writeback-ord-002-won",
                    "action_id": "deal-close",
                    "decision_id": "decision-ord-002-won",
                    "source_ref": "/tmp/business-ingestion.json",
                    "updated_at": "2026-03-14T09:40:00+08:00",
                }
            ],
        }

        def fake_artifact(name: str, *, default: object) -> object:
            if name == "execute-sales-v1":
                return {
                    "goal_id": "G1",
                    "theme_id": "theme-business",
                    "strategy_id": "strategy-business-sales-execute-v1",
                    "experiment_id": "experiment-business-sales-execute-v1-001",
                    "workflow_id": "workflow-business-sales-execute-v1",
                    "component_domain": "销售成交",
                    "control_level": "execute",
                    "status": "in_progress",
                    "owner_mode": "hybrid",
                    "kpi_heatmap": {
                        "priority_band": "P1",
                        "current_gap": ["真实 business writeback 仍未发生"],
                        "next_action": "先把 sales action catalog 和 execute writeback schema 固化，再接 live KPI source。",
                        "evidence_strength": "medium",
                        "kpis": [{"title": "线索数"}],
                    },
                    "evidence_refs": ["/tmp/execute-sales-v1.json"],
                    "source_ref": "/tmp/execute-sales-v1.json",
                    "updated_at": "2026-03-14T09:18:00+08:00",
                }
            return default

        with patch.object(control, "_strategy_artifact", side_effect=fake_artifact):
            context = control._derive_runtime_context(inventory)

        self.assertEqual(context["sales_execute_live"]["latest_writeback_id"], "writeback-ord-002-won")
        self.assertIn("缺 quote source contract", context["sales_execute_live"]["current_gap"])
        self.assertIn("owner_gap=1", context["sales_execute_live"]["current_gap"])
        self.assertIn("opportunity_anchor_gap=1", context["sales_execute_live"]["current_gap"])
        self.assertIn("先接 quote_sent 源字段", context["sales_execute_live"]["next_action"])

        context["cbm_rows"] = [
            {
                "component_domain": "销售成交",
                "control_level": "execute",
                "goal_id": "G1",
                "theme_id": "theme-business",
                "strategy_id": "strategy-business-sales-execute-v1",
                "experiment_id": "experiment-business-sales-execute-v1-001",
                "workflow_id": "workflow-business-sales-execute-v1",
                "entity_refs": [{"entity_type": "operating_module", "entity_id": "module-sales", "title": "销售成交"}],
                "action_refs": [],
                "kpi_refs": ["商机推进、报价、成交额"],
                "evidence_refs": ["generated://module/sales"],
                "coverage_status": "partial",
                "gap_notes": ["热图 / 投资优先级还没有与 module-sales 形成一等字段绑定。"],
            }
        ]
        rows = control._build_cbm_component_heatmap_rows(inventory, context, [], [])
        sales_row = next(
            item
            for item in rows
            if item["component_domain"] == "销售成交" and item["control_level"] == "execute"
        )

        self.assertEqual(sales_row["latest_writeback_id"], "writeback-ord-002-won")
        self.assertEqual(sales_row["latest_decision_id"], "decision-ord-002-won")
        self.assertEqual(sales_row["priority_band"], "P1")
        self.assertIn("先接 quote_sent 源字段", sales_row["next_action"])
        self.assertIn("handoff", sales_row["next_action"])
        self.assertIn("qualified_opportunities=1", sales_row["kpi_hint"])
        self.assertIn("缺 quote source contract", sales_row["current_gap"])

    def test_derive_runtime_context_and_heatmap_marks_quote_ready_when_source_backed(self) -> None:
        inventory = {
            "operating_modules": [
                {
                    "module_id": "module-sales",
                    "module_code": "sales",
                    "title": "销售成交",
                    "status": "active",
                    "owner_subject_id": "subject-collab-owner",
                    "ai_subject_id": "subject-agent-sales",
                }
            ],
            "subjects": [
                {"subject_id": "subject-collab-owner", "title": "共同治理者"},
                {"subject_id": "subject-agent-sales", "title": "Sales Copilot"},
            ],
            "orders": [
                {
                    "order_id": "ord-quote-001",
                    "module_code": "sales",
                    "order_date": "2024-03-05",
                    "opportunity_id": "opp-quote-001",
                    "lead_owner": "施子超",
                    "primary_conversion_owner": "施子超",
                    "quote_id": "qt-001",
                    "quote_sent_at": "2024-03-03",
                }
            ],
            "decision_records": [
                {
                    "decision_id": "decision-quote-001",
                    "title": "确认订单 ord-quote-001 已形成真实报价证据",
                },
                {
                    "decision_id": "decision-close-001",
                    "title": "确认订单 ord-quote-001 已形成赢单证据",
                },
            ],
            "writeback_events": [
                {
                    "writeback_id": "writeback-quote-001",
                    "action_id": "proposal-quote",
                    "decision_id": "decision-quote-001",
                    "source_ref": "/tmp/business-ingestion.json",
                    "updated_at": "2026-03-14T09:20:00+08:00",
                },
                {
                    "writeback_id": "writeback-close-001",
                    "action_id": "deal-close",
                    "decision_id": "decision-close-001",
                    "source_ref": "/tmp/business-ingestion.json",
                    "updated_at": "2026-03-14T09:40:00+08:00",
                },
            ],
        }

        def fake_artifact(name: str, *, default: object) -> object:
            if name == "execute-sales-v1":
                return {
                    "goal_id": "G1",
                    "theme_id": "theme-business",
                    "strategy_id": "strategy-business-sales-execute-v1",
                    "experiment_id": "experiment-business-sales-execute-v1-001",
                    "workflow_id": "workflow-business-sales-execute-v1",
                    "component_domain": "销售成交",
                    "control_level": "execute",
                    "status": "in_progress",
                    "owner_mode": "hybrid",
                    "kpi_heatmap": {
                        "priority_band": "P1",
                        "current_gap": ["quote source readiness 尚未完成"],
                        "next_action": "先把 quote source contract 接起来，再补 handoff。",
                        "evidence_strength": "medium",
                        "kpis": [{"title": "报价吞吐"}],
                    },
                    "evidence_refs": ["/tmp/execute-sales-v1.json"],
                    "source_ref": "/tmp/execute-sales-v1.json",
                    "updated_at": "2026-03-14T09:18:00+08:00",
                }
            return default

        with patch.object(control, "_strategy_artifact", side_effect=fake_artifact):
            context = control._derive_runtime_context(inventory)

        self.assertIn("lost 与 handoff 仍缺证据", context["sales_execute_live"]["current_gap"])
        self.assertIn("quote_throughput=1", context["sales_execute_live"]["kpi_hint"])
        self.assertIn("deal_cycle_delay=avg:2.0d", context["sales_execute_live"]["kpi_hint"])
        self.assertIn("补 handoff，再补 lost", context["sales_execute_live"]["next_action"])

        context["cbm_rows"] = [
            {
                "component_domain": "销售成交",
                "control_level": "execute",
                "goal_id": "G1",
                "theme_id": "theme-business",
                "strategy_id": "strategy-business-sales-execute-v1",
                "experiment_id": "experiment-business-sales-execute-v1-001",
                "workflow_id": "workflow-business-sales-execute-v1",
                "entity_refs": [{"entity_type": "operating_module", "entity_id": "module-sales", "title": "销售成交"}],
                "action_refs": [],
                "kpi_refs": ["报价、成交额、交接"],
                "evidence_refs": ["generated://module/sales"],
                "coverage_status": "partial",
                "gap_notes": ["quote/timing ready but handoff still missing."],
            }
        ]
        rows = control._build_cbm_component_heatmap_rows(inventory, context, [], [])
        sales_row = next(
            item
            for item in rows
            if item["component_domain"] == "销售成交" and item["control_level"] == "execute"
        )

        self.assertIn("lost 与 handoff 仍缺证据", sales_row["current_gap"])
        self.assertIn("quote_throughput=1", sales_row["kpi_hint"])
        self.assertIn("deal_cycle_delay=avg:2.0d", sales_row["kpi_hint"])
        self.assertIn("补 handoff，再补 lost", sales_row["next_action"])

    def test_derive_runtime_context_and_heatmap_marks_handoff_ready_when_source_backed(self) -> None:
        inventory = {
            "operating_modules": [
                {
                    "module_id": "module-sales",
                    "module_code": "sales",
                    "title": "销售成交",
                    "status": "active",
                    "owner_subject_id": "subject-collab-owner",
                    "ai_subject_id": "subject-agent-sales",
                }
            ],
            "subjects": [
                {"subject_id": "subject-collab-owner", "title": "共同治理者"},
                {"subject_id": "subject-agent-sales", "title": "Sales Copilot"},
            ],
            "orders": [
                {
                    "order_id": "ord-handoff-001",
                    "module_code": "sales",
                    "order_date": "2024-03-05",
                    "opportunity_id": "opp-handoff-001",
                    "lead_owner": "施子超",
                    "primary_conversion_owner": "施子超",
                    "quote_id": "qt-001",
                    "quote_sent_at": "2024-03-03",
                    "delivery_owner": "交付小赵",
                    "handoff_packet_ref": "https://example.com/handoff/pkg-001",
                    "handoff_completed_at": "2024-03-06T10:00:00+08:00",
                }
            ],
            "decision_records": [
                {
                    "decision_id": "decision-quote-001",
                    "title": "确认订单 ord-handoff-001 已形成真实报价证据",
                },
                {
                    "decision_id": "decision-close-001",
                    "title": "确认订单 ord-handoff-001 已形成赢单证据",
                },
                {
                    "decision_id": "decision-handoff-001",
                    "title": "确认订单 ord-handoff-001 已形成真实交接完成证据",
                },
            ],
            "writeback_events": [
                {
                    "writeback_id": "writeback-quote-001",
                    "action_id": "proposal-quote",
                    "decision_id": "decision-quote-001",
                    "source_ref": "/tmp/business-ingestion.json",
                    "updated_at": "2026-03-14T09:20:00+08:00",
                },
                {
                    "writeback_id": "writeback-close-001",
                    "action_id": "deal-close",
                    "decision_id": "decision-close-001",
                    "source_ref": "/tmp/business-ingestion.json",
                    "updated_at": "2026-03-14T09:40:00+08:00",
                },
                {
                    "writeback_id": "writeback-handoff-001",
                    "action_id": "post-close-handoff",
                    "decision_id": "decision-handoff-001",
                    "source_ref": "/tmp/business-ingestion.json",
                    "updated_at": "2026-03-14T10:00:00+08:00",
                },
            ],
        }

        def fake_artifact(name: str, *, default: object) -> object:
            if name == "execute-sales-v1":
                return {
                    "goal_id": "G1",
                    "theme_id": "theme-business",
                    "strategy_id": "strategy-business-sales-execute-v1",
                    "experiment_id": "experiment-business-sales-execute-v1-001",
                    "workflow_id": "workflow-business-sales-execute-v1",
                    "component_domain": "销售成交",
                    "control_level": "execute",
                    "status": "in_progress",
                    "owner_mode": "hybrid",
                    "kpi_heatmap": {
                        "priority_band": "P1",
                        "current_gap": ["quote/timing ready，下一跳是 handoff。"],
                        "next_action": "补 handoff，再补 lost。",
                        "evidence_strength": "medium",
                        "kpis": [{"title": "报价吞吐"}],
                    },
                    "evidence_refs": ["/tmp/execute-sales-v1.json"],
                    "source_ref": "/tmp/execute-sales-v1.json",
                    "updated_at": "2026-03-14T09:18:00+08:00",
                }
            return default

        with patch.object(control, "_strategy_artifact", side_effect=fake_artifact):
            context = control._derive_runtime_context(inventory)

        self.assertEqual(context["sales_execute_live"]["latest_writeback_id"], "writeback-handoff-001")
        self.assertEqual(context["sales_execute_live"]["latest_decision_id"], "decision-handoff-001")
        self.assertIn("lost 仍缺证据，handoff 已进入真实证据链", context["sales_execute_live"]["current_gap"])
        self.assertIn("handoff_completed=1", context["sales_execute_live"]["kpi_hint"])
        self.assertIn("handoff_source_detected=1", context["sales_execute_live"]["kpi_hint"])
        self.assertIn("补 lost，并继续补 handoff owner 覆盖", context["sales_execute_live"]["next_action"])

        context["cbm_rows"] = [
            {
                "component_domain": "销售成交",
                "control_level": "execute",
                "goal_id": "G1",
                "theme_id": "theme-business",
                "strategy_id": "strategy-business-sales-execute-v1",
                "experiment_id": "experiment-business-sales-execute-v1-001",
                "workflow_id": "workflow-business-sales-execute-v1",
                "entity_refs": [{"entity_type": "operating_module", "entity_id": "module-sales", "title": "销售成交"}],
                "action_refs": [],
                "kpi_refs": ["报价、成交额、交接"],
                "evidence_refs": ["generated://module/sales"],
                "coverage_status": "partial",
                "gap_notes": ["quote/timing ready and handoff connected."],
            }
        ]
        rows = control._build_cbm_component_heatmap_rows(inventory, context, [], [])
        sales_row = next(
            item
            for item in rows
            if item["component_domain"] == "销售成交" and item["control_level"] == "execute"
        )

        self.assertEqual(sales_row["latest_writeback_id"], "writeback-handoff-001")
        self.assertEqual(sales_row["latest_decision_id"], "decision-handoff-001")
        self.assertIn("lost 仍缺证据，handoff 已进入真实证据链", sales_row["current_gap"])
        self.assertIn("handoff_completed=1", sales_row["kpi_hint"])
        self.assertIn("补 lost，并继续补 handoff owner 覆盖", sales_row["next_action"])

    def test_derive_runtime_context_and_heatmap_marks_minimum_execute_chain_ready_when_lost_connected(self) -> None:
        inventory = {
            "operating_modules": [
                {
                    "module_id": "module-sales",
                    "module_code": "sales",
                    "title": "销售成交",
                    "status": "active",
                    "owner_subject_id": "subject-collab-owner",
                    "ai_subject_id": "subject-agent-sales",
                }
            ],
            "subjects": [
                {"subject_id": "subject-collab-owner", "title": "共同治理者"},
                {"subject_id": "subject-agent-sales", "title": "Sales Copilot"},
            ],
            "orders": [
                {
                    "order_id": "ord-handoff-001",
                    "module_code": "sales",
                    "order_date": "2024-03-05",
                    "opportunity_id": "opp-handoff-001",
                    "lead_owner": "施子超",
                    "primary_conversion_owner": "施子超",
                    "quote_id": "qt-001",
                    "quote_sent_at": "2024-03-03",
                    "delivery_owner": "交付小赵",
                    "finance_owner": "财务小周",
                    "handoff_packet_ref": "https://example.com/handoff/pkg-001",
                    "handoff_completed_at": "2024-03-06T10:00:00+08:00",
                },
                {
                    "order_id": "ord-lost-001",
                    "module_code": "sales",
                    "opportunity_id": "opp-lost-001",
                    "lead_owner": "施子超",
                    "primary_conversion_owner": "施子超",
                    "quote_id": "qt-lost-001",
                    "quote_sent_at": "2024-03-04",
                    "close_state": "closed_lost",
                    "lost_at": "2024-03-07T15:30:00+08:00",
                    "loss_reason": "预算延后",
                    "loss_evidence_ref": "https://example.com/lost/evidence-001",
                },
            ],
            "decision_records": [
                {
                    "decision_id": "decision-quote-001",
                    "title": "确认订单 ord-handoff-001 已形成真实报价证据",
                },
                {
                    "decision_id": "decision-close-won-001",
                    "title": "确认订单 ord-handoff-001 已形成赢单证据",
                },
                {
                    "decision_id": "decision-handoff-001",
                    "title": "确认订单 ord-handoff-001 已形成真实交接完成证据",
                },
                {
                    "decision_id": "decision-close-lost-001",
                    "title": "确认订单 ord-lost-001 已形成真实丢单证据",
                },
            ],
            "writeback_events": [
                {
                    "writeback_id": "writeback-quote-001",
                    "action_id": "proposal-quote",
                    "decision_id": "decision-quote-001",
                    "source_ref": "/tmp/business-ingestion.json",
                    "updated_at": "2026-03-14T09:20:00+08:00",
                },
                {
                    "writeback_id": "writeback-close-won-001",
                    "action_id": "deal-close",
                    "writeback_type": "deal_closed_won",
                    "decision_id": "decision-close-won-001",
                    "source_ref": "/tmp/business-ingestion.json",
                    "updated_at": "2026-03-14T09:40:00+08:00",
                },
                {
                    "writeback_id": "writeback-handoff-001",
                    "action_id": "post-close-handoff",
                    "decision_id": "decision-handoff-001",
                    "source_ref": "/tmp/business-ingestion.json",
                    "updated_at": "2026-03-14T10:00:00+08:00",
                },
                {
                    "writeback_id": "writeback-close-lost-001",
                    "action_id": "deal-close",
                    "writeback_type": "deal_closed_lost",
                    "decision_id": "decision-close-lost-001",
                    "source_ref": "/tmp/business-ingestion.json",
                    "updated_at": "2026-03-14T10:30:00+08:00",
                },
            ],
        }

        def fake_artifact(name: str, *, default: object) -> object:
            if name == "execute-sales-v1":
                return {
                    "goal_id": "G1",
                    "theme_id": "theme-business",
                    "strategy_id": "strategy-business-sales-execute-v1",
                    "experiment_id": "experiment-business-sales-execute-v1-001",
                    "workflow_id": "workflow-business-sales-execute-v1",
                    "component_domain": "销售成交",
                    "control_level": "execute",
                    "status": "in_progress",
                    "owner_mode": "hybrid",
                    "kpi_heatmap": {
                        "priority_band": "P1",
                        "current_gap": ["lost 与 handoff 仍缺证据"],
                        "next_action": "补 handoff，再补 lost。",
                        "evidence_strength": "medium",
                        "kpis": [{"title": "赢单与丢单"}],
                    },
                    "evidence_refs": ["/tmp/execute-sales-v1.json"],
                    "source_ref": "/tmp/execute-sales-v1.json",
                    "updated_at": "2026-03-14T09:18:00+08:00",
                }
            return default

        with patch.object(control, "_strategy_artifact", side_effect=fake_artifact):
            context = control._derive_runtime_context(inventory)

        self.assertEqual(context["sales_execute_live"]["latest_writeback_id"], "writeback-close-lost-001")
        self.assertEqual(context["sales_execute_live"]["latest_decision_id"], "decision-close-lost-001")
        self.assertIn("最小 execute 证据链已形成", context["sales_execute_live"]["current_gap"])
        self.assertIn("win_loss_count=won:1, lost:1", context["sales_execute_live"]["kpi_hint"])
        self.assertIn("lost_source_detected=1", context["sales_execute_live"]["kpi_hint"])
        self.assertIn("补 handoff owner 覆盖，并校准 owner/opportunity 字段质量", context["sales_execute_live"]["next_action"])

        context["cbm_rows"] = [
            {
                "component_domain": "销售成交",
                "control_level": "execute",
                "goal_id": "G1",
                "theme_id": "theme-business",
                "strategy_id": "strategy-business-sales-execute-v1",
                "experiment_id": "experiment-business-sales-execute-v1-001",
                "workflow_id": "workflow-business-sales-execute-v1",
                "entity_refs": [{"entity_type": "operating_module", "entity_id": "module-sales", "title": "销售成交"}],
                "action_refs": [],
                "kpi_refs": ["报价、成交额、交接、丢单"],
                "evidence_refs": ["generated://module/sales"],
                "coverage_status": "partial",
                "gap_notes": ["minimum execute chain connected."],
            }
        ]
        rows = control._build_cbm_component_heatmap_rows(inventory, context, [], [])
        sales_row = next(
            item
            for item in rows
            if item["component_domain"] == "销售成交" and item["control_level"] == "execute"
        )

        self.assertEqual(sales_row["latest_writeback_id"], "writeback-close-lost-001")
        self.assertEqual(sales_row["latest_decision_id"], "decision-close-lost-001")
        self.assertIn("最小 execute 证据链已形成", sales_row["current_gap"])
        self.assertIn("win_loss_count=won:1, lost:1", sales_row["kpi_hint"])
        self.assertIn("补 handoff owner 覆盖，并校准 owner/opportunity 字段质量", sales_row["next_action"])

    def test_threads_rows_include_latest_governance_activity_fields(self) -> None:
        inventory = {
            "threads": [
                {
                    "thread_id": "thread-main",
                    "title": "主会场线程",
                    "theme": "G1",
                    "goal_id": "G1",
                    "space_id": "space-main",
                    "module_id": "module-governance",
                    "status": "active",
                    "updated_at": "2026-03-14T09:00:00+08:00",
                    "source_ref": "/tmp/threads.json",
                }
            ],
            "tasks": [
                {
                    "task_id": "task-main",
                    "thread_id": "thread-main",
                    "title": "推进治理主线",
                    "goal_id": "G1",
                    "space_id": "space-main",
                    "target_module_id": "module-governance",
                    "status": "active",
                    "priority": "P1",
                    "updated_at": "2026-03-14T09:05:00+08:00",
                    "last_updated_at": "2026-03-14T09:05:00+08:00",
                    "source_ref": "/tmp/tasks.json",
                }
            ],
            "decision_records": [
                {
                    "decision_id": "decision-main",
                    "title": "确认推进治理主线",
                    "target_entity_ids": ["task-main"],
                    "decision_time": "2026-03-14T10:00:00+08:00",
                    "writeback_event_ids": ["writeback-main"],
                    "updated_at": "2026-03-14T10:00:00+08:00",
                }
            ],
            "writeback_events": [
                {
                    "writeback_id": "writeback-main",
                    "action_id": "publish-governance-report",
                    "decision_id": "decision-main",
                    "writeback_time": "2026-03-14T10:30:00+08:00",
                    "updated_at": "2026-03-14T10:30:00+08:00",
                }
            ],
            "operating_modules": [{"module_id": "module-governance", "module_code": "governance", "title": "治理控制", "status": "active"}],
            "subjects": [],
        }

        with patch.object(control, "_strategy_artifact", side_effect=lambda name, *, default: default):
            context = control._derive_runtime_context(inventory)

        rows = control._build_threads_rows(inventory, context)
        thread_row = rows[0]

        self.assertEqual(thread_row["last_activity_type"], "writeback")
        self.assertEqual(thread_row["last_activity_at"], "2026-03-14T10:30:00+08:00")
        self.assertEqual(thread_row["last_activity_summary"], "publish-governance-report")
        self.assertEqual(thread_row["frontstage_focus_object"], "推进治理主线")

    def test_tasks_rows_assign_progress_truth_labels(self) -> None:
        inventory = {
            "tasks": [
                {
                    "task_id": "task-real-progress",
                    "title": "真实推进任务",
                    "goal_id": "G1",
                    "space_id": "space-main",
                    "target_module_id": "module-governance",
                    "status": "completed",
                    "priority": "P1",
                    "verification_state": "verified",
                    "evidence_ref": "/tmp/evidence.md",
                    "updated_at": "2026-03-14T10:00:00+08:00",
                    "last_updated_at": "2026-03-14T10:00:00+08:00",
                },
                {
                    "task_id": "task-appearance-only",
                    "title": "表面推进任务",
                    "goal_id": "G1",
                    "space_id": "space-main",
                    "target_module_id": "module-governance",
                    "status": "handoff_only_closed",
                    "priority": "P1",
                    "verification_state": "handoff_prepared",
                    "updated_at": "2026-03-14T10:00:00+08:00",
                    "last_updated_at": "2026-03-14T10:00:00+08:00",
                },
                {
                    "task_id": "task-real-blocked",
                    "title": "真实阻塞任务",
                    "goal_id": "G1",
                    "space_id": "space-main",
                    "target_module_id": "module-governance",
                    "status": "blocked_system",
                    "priority": "P1",
                    "blocker_reason": "missing token",
                    "evidence_ref": "/tmp/blocker.md",
                    "updated_at": "2026-03-14T10:00:00+08:00",
                    "last_updated_at": "2026-03-14T10:00:00+08:00",
                },
                {
                    "task_id": "task-stale",
                    "title": "陈旧未验真任务",
                    "goal_id": "G1",
                    "space_id": "space-main",
                    "target_module_id": "module-governance",
                    "status": "queued",
                    "priority": "P2",
                    "verification_state": "needs_follow_up",
                    "updated_at": "2026-02-01T10:00:00+08:00",
                    "last_updated_at": "2026-02-01T10:00:00+08:00",
                },
            ],
            "operating_modules": [{"module_id": "module-governance", "module_code": "governance", "title": "治理控制", "status": "active"}],
            "subjects": [],
        }

        with patch.object(control, "_strategy_artifact", side_effect=lambda name, *, default: default):
            context = control._derive_runtime_context(inventory)

        rows = control._build_tasks_rows(inventory, context)
        labels = {row["Task ID"]: row["progress_truth_label"] for row in rows}

        self.assertEqual(labels["task-real-progress"], "real_progress")
        self.assertEqual(labels["task-appearance-only"], "appearance_only")
        self.assertEqual(labels["task-real-blocked"], "real_blocked")
        self.assertEqual(labels["task-stale"], "stale_unverified")

    def test_governance_event_rows_include_review_decision_and_writeback_records(self) -> None:
        inventory = {
            "review_runs": [
                {
                    "review_id": "review-001",
                    "review_date": "2026-03-14",
                    "scope": "AI大管家日常 review",
                    "summary": "review summary",
                    "candidate_actions": ["action-a"],
                    "human_decision": "",
                    "sync_state": "completed",
                    "source_ref": "/tmp/review.json",
                    "confidence": 0.9,
                    "updated_at": "2026-03-14T09:00:00+08:00",
                }
            ],
            "decision_records": [
                {
                    "decision_id": "decision-001",
                    "title": "批准主线推进",
                    "decision_type": "priority_shift",
                    "decision_state": "approved",
                    "target_entity_ids": ["thread-main"],
                    "decision_summary": "summary",
                    "rationale": "why",
                    "evidence_refs": ["/tmp/evidence.json"],
                    "decided_by": "human_owner",
                    "decision_time": "2026-03-14T10:00:00+08:00",
                    "writeback_event_ids": ["writeback-001"],
                    "source_ref": "/tmp/decision.json",
                    "confidence": 0.94,
                    "updated_at": "2026-03-14T10:00:00+08:00",
                }
            ],
            "writeback_events": [
                {
                    "writeback_id": "writeback-001",
                    "action_id": "publish-governance-report",
                    "decision_id": "decision-001",
                    "target_refs": ["/tmp/out.md"],
                    "changed_fields": ["summary"],
                    "evidence_refs": ["/tmp/evidence.json"],
                    "triggered_by": "automation",
                    "verification_state": "completed",
                    "source_ref": "/tmp/writeback.json",
                    "confidence": 0.9,
                    "updated_at": "2026-03-14T10:30:00+08:00",
                }
            ],
        }

        rows = control._build_governance_event_rows(inventory)
        by_type = {row["记录类型"]: row for row in rows}

        self.assertTrue({"review", "decision", "writeback"}.issubset(by_type))
        self.assertEqual(by_type["review"]["治理事件Key"], "review:review-001")
        self.assertEqual(by_type["decision"]["标题"], "批准主线推进")
        self.assertEqual(by_type["decision"]["event_time"], "2026-03-14T10:00:00+08:00")
        self.assertEqual(by_type["writeback"]["event_time"], "2026-03-14T10:30:00+08:00")
        self.assertEqual(by_type["writeback"]["writeback_targets_or_decision_id"], "decision-001")


if __name__ == "__main__":
    unittest.main()
