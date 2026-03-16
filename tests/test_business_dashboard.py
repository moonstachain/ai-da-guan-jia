from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dashboard import business_migration


class FakeBusinessAPI:
    def __init__(self) -> None:
        self.source_app = "app_source"
        self.target_app = "app_target"
        self.source_tables = {
            "客户机会主表": {"table_id": "tbl_opp", "name": "客户机会主表"},
            "订单事实表": {"table_id": "tbl_order", "name": "订单事实表"},
            "跟进与证据表": {"table_id": "tbl_evd", "name": "跟进与证据表"},
            "交付项目表": {"table_id": "tbl_del", "name": "交付项目表"},
            "学员/客户档案表": {"table_id": "tbl_cus", "name": "学员/客户档案表"},
            "私域运营事实表": {"table_id": "tbl_private", "name": "私域运营事实表"},
        }
        self.source_fields = {
            "tbl_opp": [
                {"field_name": "机会ID", "type": 1},
                {"field_name": "客户名称", "type": 1},
                {"field_name": "主转化归属", "type": 1},
                {"field_name": "当前状态", "type": 1},
                {"field_name": "预估成交金额", "type": 2},
            ],
            "tbl_order": [
                {"field_name": "订单ID", "type": 1},
                {"field_name": "订单日期", "type": 5},
                {"field_name": "支付金额", "type": 2},
                {"field_name": "客户名称", "type": 1},
                {"field_name": "订单来源", "type": 1},
                {"field_name": "服务线", "type": 1},
                {"field_name": "主转化归属", "type": 1},
            ],
            "tbl_evd": [
                {"field_name": "记录ID", "type": 1},
                {"field_name": "记录时间", "type": 5},
                {"field_name": "记录人", "type": 1},
            ],
            "tbl_del": [
                {"field_name": "交付ID", "type": 1},
                {"field_name": "服务线", "type": 1},
                {"field_name": "交付负责人", "type": 1},
                {"field_name": "开始时间", "type": 5},
                {"field_name": "结束时间", "type": 5},
                {"field_name": "来源订单", "type": 1},
                {"field_name": "当前交付阶段", "type": 1},
                {"field_name": "当前风险", "type": 1},
            ],
            "tbl_cus": [
                {"field_name": "客户ID", "type": 1},
                {"field_name": "客户名称", "type": 1},
                {"field_name": "是否邀请复训", "type": 3, "property": {"options": [{"name": "是"}, {"name": "否"}]}},
            ],
            "tbl_private": [
                {"field_name": "记录ID", "type": 1},
                {"field_name": "日期", "type": 5},
                {"field_name": "新增加私", "type": 2},
                {"field_name": "当日私域流水", "type": 2},
            ],
        }
        self.source_records = {
            "tbl_opp": [
                {"record_id": "rec_opp_1", "fields": {"机会ID": "opp-1", "客户名称": "A客户", "主转化归属": "施子超", "当前状态": "跟进中", "预估成交金额": 12000}},
                {"record_id": "rec_opp_2", "fields": {"机会ID": "opp-2", "客户名称": "B客户", "主转化归属": "田彤", "当前状态": "已成交", "预估成交金额": 6000}},
            ],
            "tbl_order": [
                {"record_id": "rec_ord_1", "fields": {"订单ID": "ord-1", "订单日期": 1736899200, "支付金额": 12980, "客户名称": "A客户", "订单来源": "1V1", "服务线": "私董会", "主转化归属": "施子超"}},
                {"record_id": "rec_ord_2", "fields": {"订单ID": "ord-2", "订单日期": 1737331200, "支付金额": 2999, "客户名称": "B客户", "订单来源": "短视频", "服务线": "AI社区", "主转化归属": "田彤"}},
                {"record_id": "rec_ord_3", "fields": {"订单ID": "ord-3", "订单日期": 1740787200, "支付金额": 9980, "客户名称": "A客户", "订单来源": "1V1", "服务线": "北京线下实战课", "主转化归属": "施子超"}},
            ],
            "tbl_evd": [
                {"record_id": "rec_evd_1", "fields": {"记录ID": "evd-1", "记录时间": 1740787200, "记录人": "施子超"}},
                {"record_id": "rec_evd_2", "fields": {"记录ID": "evd-2", "记录时间": 1740787200, "记录人": "施子超"}},
            ],
            "tbl_del": [
                {"record_id": "rec_del_1", "fields": {"交付ID": "del-1", "服务线": "私董会", "交付负责人": "施子超", "开始时间": 1740787200, "结束时间": 1741392000, "来源订单": "ord-1", "当前交付阶段": "已完成", "当前风险": ""}},
                {"record_id": "rec_del_2", "fields": {"交付ID": "del-2", "服务线": "北京线下实战课", "交付负责人": "施子超", "开始时间": 1740787200, "结束时间": "", "来源订单": "ord-3", "当前交付阶段": "进行中", "当前风险": "排期紧张"}},
            ],
            "tbl_cus": [
                {"record_id": "rec_cus_1", "fields": {"客户ID": "cus-1", "客户名称": "A客户", "是否邀请复训": "是"}},
                {"record_id": "rec_cus_2", "fields": {"客户ID": "cus-2", "客户名称": "B客户", "是否邀请复训": "否"}},
            ],
            "tbl_private": [
                {"record_id": "rec_pri_1", "fields": {"记录ID": "pri-1", "日期": 1740787200, "新增加私": 12, "当日私域流水": 2999}},
                {"record_id": "rec_pri_2", "fields": {"记录ID": "pri-2", "日期": 1740873600, "新增加私": 8, "当日私域流水": 0}},
            ],
        }
        self.target_tables: dict[str, dict[str, object]] = {}
        self.target_fields: dict[str, list[dict[str, object]]] = {}
        self.target_records: dict[str, list[dict[str, object]]] = {}

    def resolve_app_token(self, link: str) -> str:
        if "source" in link:
            return self.source_app
        return self.target_app

    def list_tables(self, app_token: str) -> list[dict[str, object]]:
        if app_token == self.source_app:
            return list(self.source_tables.values())
        return list(self.target_tables.values())

    def list_fields(self, app_token: str, table_id: str) -> list[dict[str, object]]:
        if app_token == self.source_app:
            return list(self.source_fields[table_id])
        return list(self.target_fields.get(table_id, []))

    def list_records(self, app_token: str, table_id: str) -> list[dict[str, object]]:
        if app_token == self.source_app:
            return list(self.source_records[table_id])
        return list(self.target_records.get(table_id, []))

    def create_table(self, app_token: str, table_name: str, fields: list[dict[str, object]]) -> dict[str, object]:
        table_id = f"tbl_target_{len(self.target_tables) + 1}"
        table = {"table_id": table_id, "name": table_name}
        self.target_tables[table_name] = table
        self.target_fields[table_id] = [
            {"field_name": field["field_name"], "type": field["type"]}
            for field in fields
        ]
        self.target_records[table_id] = []
        return table

    def create_field(self, app_token: str, table_id: str, payload: dict[str, object]) -> dict[str, object]:
        self.target_fields.setdefault(table_id, []).append({"field_name": payload["field_name"], "type": payload["type"]})
        return payload

    def batch_create_records(self, app_token: str, table_id: str, rows: list[dict[str, object]]) -> dict[str, object]:
        for idx, row in enumerate(rows, start=len(self.target_records.get(table_id, [])) + 1):
            self.target_records.setdefault(table_id, []).append({"record_id": f"rec_{idx}", "fields": dict(row)})
        return {"records": rows}

    def delete_record(self, app_token: str, table_id: str, record_id: str) -> None:
        self.target_records[table_id] = [row for row in self.target_records.get(table_id, []) if row["record_id"] != record_id]


class BusinessDashboardTest(unittest.TestCase):
    def test_flatten_cell_joins_link_texts(self) -> None:
        value = [{"text": "ord-1"}, {"text": "ord-2"}]
        self.assertEqual(business_migration.flatten_cell(value), "ord-1 | ord-2")

    def test_fetch_source_bundle_normalizes_source_tables(self) -> None:
        api = FakeBusinessAPI()
        bundles, rows_by_table = business_migration.fetch_source_bundle(api, "source-link")
        self.assertEqual(len(bundles), 6)
        self.assertIn("订单事实表", rows_by_table)
        self.assertEqual(rows_by_table["订单事实表"][0]["支付金额"], 12980)

    def test_build_dashboard_records_derives_expected_rows(self) -> None:
        api = FakeBusinessAPI()
        _, rows_by_table = business_migration.fetch_source_bundle(api, "source-link")
        bundles = business_migration.build_dashboard_records(rows_by_table)
        l0 = next(bundle for bundle in bundles if bundle.table_name == "L0_经营总览")
        customer = next(bundle for bundle in bundles if bundle.table_name == "L2_客户价值分析")
        self.assertEqual(l0.records[0]["year_target"], 10000000)
        self.assertEqual(customer.records[0]["customer_tier"], "成长客户")

    def test_write_schema_files_outputs_source_and_dashboard_json(self) -> None:
        api = FakeBusinessAPI()
        source_bundles, rows_by_table = business_migration.fetch_source_bundle(api, "source-link")
        dashboard_bundles = business_migration.build_dashboard_records(rows_by_table)
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = business_migration.write_schema_files(source_bundles, dashboard_bundles, schema_dir=Path(tmp_dir))
            self.assertEqual(len(paths), len(source_bundles) + len(dashboard_bundles))
            self.assertTrue((Path(tmp_dir) / "customer_opportunities.json").exists())
            self.assertTrue((Path(tmp_dir) / "l0_overview.json").exists())

    def test_migrator_creates_and_seeds_target_tables(self) -> None:
        api = FakeBusinessAPI()
        with tempfile.TemporaryDirectory() as tmp_dir:
            migrator = business_migration.BusinessDashboardMigrator(api, artifact_dir=Path(tmp_dir))
            result = migrator.migrate("source-link", "target-link", apply_changes=True)
        self.assertEqual(result["source_table_count"], 6)
        self.assertEqual(result["dashboard_table_count"], 5)
        l0 = next(item for item in result["tables"] if item["table_name"] == "L0_经营总览")
        orders = next(item for item in result["tables"] if item["table_name"] == "订单事实表")
        self.assertEqual(l0["verified_records"], 1)
        self.assertEqual(orders["verified_records"], 3)

    def test_migrator_dry_run_reports_planned_seed(self) -> None:
        api = FakeBusinessAPI()
        with tempfile.TemporaryDirectory() as tmp_dir:
            migrator = business_migration.BusinessDashboardMigrator(api, artifact_dir=Path(tmp_dir))
            result = migrator.migrate("source-link", "target-link", apply_changes=False)
        self.assertTrue(all(item["status"].startswith("planned") for item in result["tables"]))


if __name__ == "__main__":
    unittest.main()
