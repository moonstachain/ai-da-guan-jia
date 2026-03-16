from __future__ import annotations

import unittest
from pathlib import Path

from dashboard import feishu_deploy


class FakeFeishuAPI:
    def __init__(self) -> None:
        self.app_token = "app_test_123"
        self.table_counter = 0
        self.tables: dict[str, dict[str, object]] = {}
        self.fields: dict[str, list[dict[str, object]]] = {}
        self.records: dict[str, list[dict[str, object]]] = {}

    def resolve_app_token(self, link: str) -> str:
        return self.app_token

    def list_tables(self, app_token: str) -> list[dict[str, object]]:
        return list(self.tables.values())

    def create_table(self, app_token: str, table_name: str, fields: list[dict[str, object]]) -> dict[str, object]:
        self.table_counter += 1
        table_id = f"tbl_{self.table_counter}"
        table = {"table_id": table_id, "name": table_name}
        self.tables[table_name] = table
        self.fields[table_id] = [{"field_name": field["field_name"], "type": field["type"]} for field in fields]
        self.records[table_id] = []
        return table

    def list_fields(self, app_token: str, table_id: str) -> list[dict[str, object]]:
        return self.fields[table_id]

    def list_records(self, app_token: str, table_id: str) -> list[dict[str, object]]:
        return self.records[table_id]

    def batch_create_records(self, app_token: str, table_id: str, rows: list[dict[str, object]]) -> dict[str, object]:
        for index, row in enumerate(rows, start=len(self.records[table_id]) + 1):
            self.records[table_id].append({"record_id": f"rec_{index}", "fields": dict(row)})
        return {"records": rows}


class DashboardFeishuDeployTest(unittest.TestCase):
    def test_feishu_field_type_mapping(self) -> None:
        self.assertEqual(feishu_deploy.feishu_field_type("text"), 1)
        self.assertEqual(feishu_deploy.feishu_field_type("number"), 2)
        self.assertEqual(feishu_deploy.feishu_field_type("single_select"), 3)
        self.assertEqual(feishu_deploy.feishu_field_type("multi_select"), 4)
        self.assertEqual(feishu_deploy.feishu_field_type("datetime"), 5)
        self.assertEqual(feishu_deploy.feishu_field_type("checkbox"), 7)

    def test_schema_field_to_feishu_field_includes_select_options(self) -> None:
        payload = feishu_deploy.schema_field_to_feishu_field(
            {"name": "status", "type": "single_select", "options": ["planned", "completed"]}
        )
        self.assertEqual(payload["field_name"], "status")
        self.assertEqual(payload["type"], 3)
        self.assertEqual(payload["property"]["options"][0]["name"], "planned")

    def test_normalize_record_converts_mixed_types(self) -> None:
        schema = {
            "fields": [
                {"name": "when", "type": "datetime"},
                {"name": "tags", "type": "multi_select"},
                {"name": "done", "type": "checkbox"},
                {"name": "count", "type": "number"},
            ]
        }
        normalized = feishu_deploy.normalize_record(
            schema,
            {
                "when": "2026-03-16T02:00:00+00:00",
                "tags": ["direct", "control"],
                "done": 1,
                "count": "12",
            },
        )
        self.assertEqual(normalized["when"], 1773626400)
        self.assertEqual(normalized["tags"], ["direct", "control"])
        self.assertIs(normalized["done"], True)
        self.assertEqual(normalized["count"], 12)

    def test_load_dashboard_tables_reads_five_tables(self) -> None:
        tables = feishu_deploy.load_dashboard_tables()
        self.assertEqual(len(tables), 5)
        self.assertEqual({table.table_name for table in tables}, set(feishu_deploy.TABLE_FILE_MAP))

    def test_deployer_creates_missing_tables_and_seeds_records(self) -> None:
        api = FakeFeishuAPI()
        deployer = feishu_deploy.DashboardFeishuDeployer(api, artifact_dir=Path("/tmp/dashboard-feishu-deploy-tests"))
        result = deployer.deploy("https://h52xu4gwob.feishu.cn/wiki/example", apply_changes=True)

        self.assertEqual(len(result["tables"]), 5)
        control = next(item for item in result["tables"] if item["table_name"] == "总控概览")
        heatmap = next(item for item in result["tables"] if item["table_name"] == "组件热图")
        evolution = next(item for item in result["tables"] if item["table_name"] == "进化轨迹")
        self.assertEqual(control["verified_records"], 1)
        self.assertEqual(heatmap["verified_records"], 12)
        self.assertEqual(evolution["verified_records"], 5)

    def test_deployer_skips_tables_with_expected_existing_count(self) -> None:
        api = FakeFeishuAPI()
        deployer = feishu_deploy.DashboardFeishuDeployer(api, artifact_dir=Path("/tmp/dashboard-feishu-deploy-tests"))
        first = deployer.deploy("https://h52xu4gwob.feishu.cn/wiki/example", apply_changes=True)
        second = deployer.deploy("https://h52xu4gwob.feishu.cn/wiki/example", apply_changes=True)

        self.assertEqual(len(first["tables"]), 5)
        self.assertTrue(all(item["status"] == "already_seeded" for item in second["tables"]))

    def test_deployer_rejects_unexpected_existing_record_count(self) -> None:
        api = FakeFeishuAPI()
        deployer = feishu_deploy.DashboardFeishuDeployer(api, artifact_dir=Path("/tmp/dashboard-feishu-deploy-tests"))
        deployer.deploy("https://h52xu4gwob.feishu.cn/wiki/example", apply_changes=True)
        table = api.tables["总控概览"]
        api.records[str(table["table_id"])].append({"record_id": "rec_extra", "fields": {"runtime_state": "healthy"}})

        with self.assertRaises(RuntimeError):
            deployer.deploy("https://h52xu4gwob.feishu.cn/wiki/example", apply_changes=True)

    def test_dry_run_reports_planned_creation(self) -> None:
        api = FakeFeishuAPI()
        deployer = feishu_deploy.DashboardFeishuDeployer(api, artifact_dir=Path("/tmp/dashboard-feishu-deploy-tests"))
        result = deployer.deploy("https://h52xu4gwob.feishu.cn/wiki/example", apply_changes=False)
        self.assertTrue(all(item["status"] == "planned_create" for item in result["tables"]))


if __name__ == "__main__":
    unittest.main()
