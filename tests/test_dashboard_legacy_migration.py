from __future__ import annotations

import unittest
from pathlib import Path

from dashboard import legacy_migration


class FakeMigrationAPI:
    def __init__(self) -> None:
        self.target_app_token = "app_target"
        self.tables: dict[str, dict[str, object]] = {
            "总控概览": {"table_id": legacy_migration.TARGET_TABLE_IDS["总控概览"], "name": "总控概览"},
            "组件热图": {"table_id": legacy_migration.TARGET_TABLE_IDS["组件热图"], "name": "组件热图"},
            "战略链路": {"table_id": legacy_migration.TARGET_TABLE_IDS["战略链路"], "name": "战略链路"},
            "组件责任": {"table_id": legacy_migration.TARGET_TABLE_IDS["组件责任"], "name": "组件责任"},
            "进化轨迹": {"table_id": legacy_migration.TARGET_TABLE_IDS["进化轨迹"], "name": "进化轨迹"},
        }
        self.fields = {
            legacy_migration.TARGET_TABLE_IDS["总控概览"]: [{"field_id": "fld_1", "field_name": "last_refresh", "type": 5}],
            legacy_migration.TARGET_TABLE_IDS["组件热图"]: [{"field_id": "fld_h_domain", "field_name": "component_domain", "type": 3}],
            legacy_migration.TARGET_TABLE_IDS["战略链路"]: [{"field_id": "fld_s_domain", "field_name": "component_domain", "type": 3}],
            legacy_migration.TARGET_TABLE_IDS["组件责任"]: [{"field_id": "fld_r_domain", "field_name": "component_domain", "type": 3}],
            legacy_migration.TARGET_TABLE_IDS["进化轨迹"]: [{"field_id": "fld_e_domain", "field_name": "component_domain", "type": 3}],
        }
        self.records = {
            legacy_migration.TARGET_TABLE_IDS["总控概览"]: [{"record_id": "rec_seed_1", "fields": {"runtime_state": "healthy"}}],
            legacy_migration.TARGET_TABLE_IDS["组件热图"]: [{"record_id": "rec_seed_2", "fields": {"component_domain": "governance"}}],
            legacy_migration.TARGET_TABLE_IDS["战略链路"]: [{"record_id": "rec_seed_3", "fields": {"goal_id": "g1"}}],
            legacy_migration.TARGET_TABLE_IDS["组件责任"]: [{"record_id": "rec_seed_4", "fields": {"component_domain": "sales"}}],
            legacy_migration.TARGET_TABLE_IDS["进化轨迹"]: [{"record_id": "rec_seed_5", "fields": {"round_id": "R1"}}],
        }
        self.created_tables: list[tuple[str, list[dict[str, object]]]] = []
        self.updated_fields: list[tuple[str, str, dict[str, object]]] = []
        self.deleted_records: list[tuple[str, str]] = []
        self.batch_created: list[tuple[str, list[dict[str, object]]]] = []

    def resolve_app_token(self, link: str) -> str:
        if link == legacy_migration.TARGET_LINK:
            return self.target_app_token
        if link == legacy_migration.LEGACY_MASTER_LINK:
            return "app_legacy_master"
        if link == legacy_migration.LEGACY_LOG_LINK:
            return "app_legacy_log"
        return "app_unknown"

    def list_records(self, app_token: str, table_id: str) -> list[dict[str, object]]:
        if app_token == "app_legacy_master":
            if table_id == legacy_migration.LEGACY_MASTER_TABLE_ID:
                return [
                    {"record_id": "rec_1", "fields": {"对象类型": "strategic_linkage", "对象Key": "strategic_linkage:strategic-link-abc123", "对象标题": "治理运行骨架收口", "component_domain": "治理运行骨架", "control_level": "direct", "对象状态": "validated", "当前摘要": "gap", "下一步动作": "next", "证据入口": "proof"}},
                    {"record_id": "rec_2", "fields": {"对象类型": "cbm_component_heatmap", "component_domain": "销售成交", "control_level": "execute", "priority_band": "P1", "evidence_strength": "medium", "当前摘要": "KPI", "下一步动作": "补 catalog", "对象状态": "gap", "负责人模式": "hybrid", "最近更新时间": "2026-03-14T01:57:57+08:00"}},
                    {"record_id": "rec_3", "fields": {"对象类型": "cbm_component_responsibility", "component_domain": "治理控制", "control_level": "control, direct", "对象状态": "active", "负责人模式": "hybrid", "目标ID": "G1", "证据入口": "proof"}},
                ]
            if table_id == legacy_migration.LEGACY_DECISION_TABLE_ID:
                return [
                    {"record_id": "rec_d", "fields": {"Decision ID": "decision-1", "decision_type": "review_action_resolution", "decision_state": "pending_approval", "decision_summary": "处理外部高价值线索", "rationale": "值得纳入 adoption queue", "evidence_refs": "proof", "decision_time": 1773189380}},
                ]
        if app_token == "app_legacy_log":
            return [
                {"record_id": "rec_l", "fields": {"日志ID": "adagj-001", "时间": "2026-03-10T04:56:44+08:00", "工作状态": "已完成", "调用技能": "feishu-bitable-bridge, self-evolution-max", "gained": "真实记录", "wasted": "", "next_iterate": "继续", "验真状态": "completed"}},
            ]
        return list(self.records.get(table_id, []))

    def list_tables(self, app_token: str) -> list[dict[str, object]]:
        return list(self.tables.values())

    def list_fields(self, app_token: str, table_id: str) -> list[dict[str, object]]:
        return list(self.fields.get(table_id, []))

    def create_table(self, app_token: str, table_name: str, fields: list[dict[str, object]]) -> dict[str, object]:
        table_id = "tbl_decision"
        self.tables[table_name] = {"table_id": table_id, "name": table_name}
        self.fields[table_id] = [
            {"field_id": f"fld_{index}", "field_name": field["field_name"], "type": field["type"]}
            for index, field in enumerate(fields, start=1)
        ]
        self.records[table_id] = []
        self.created_tables.append((table_name, fields))
        return {"table_id": table_id, "name": table_name}

    def batch_create_records(self, app_token: str, table_id: str, rows: list[dict[str, object]]) -> dict[str, object]:
        for index, row in enumerate(rows, start=len(self.records.get(table_id, [])) + 1):
            self.records.setdefault(table_id, []).append({"record_id": f"rec_{table_id}_{index}", "fields": dict(row)})
        self.batch_created.append((table_id, rows))
        return {"records": rows}

    def _request(self, path: str, *, method: str = "GET", payload: dict[str, object] | None = None) -> dict[str, object]:
        if method == "DELETE":
            record_id = path.split("/")[-1]
            table_id = path.split("/")[-3]
            self.records[table_id] = [item for item in self.records.get(table_id, []) if item.get("record_id") != record_id]
            self.deleted_records.append((table_id, record_id))
            return {"code": 0, "data": {}}
        if method == "PUT":
            table_id = path.split("/")[-3]
            field_id = path.split("/")[-1]
            self.updated_fields.append((table_id, field_id, payload or {}))
            return {"code": 0, "data": {}}
        raise AssertionError(f"unexpected request: {method} {path}")


class DashboardLegacyMigrationTest(unittest.TestCase):
    def test_transform_strategic_linkage_maps_status_and_levels(self) -> None:
        rows = [
            {
                "对象Key": "strategic_linkage:strategic-link-c96abeccdc",
                "对象标题": "治理运行骨架收口",
                "component_domain": "治理运行骨架",
                "control_level": "direct, control",
                "对象状态": "validated",
                "当前摘要": "still gap",
                "下一步动作": "close it",
                "证据入口": "proof",
            }
        ]
        transformed = legacy_migration.transform_strategic_linkage(rows)
        self.assertEqual(transformed[0]["goal_id"], "c96abeccdc")
        self.assertEqual(transformed[0]["status"], "active")
        self.assertEqual(transformed[0]["control_level_scope"], ["direct", "control"])

    def test_transform_heatmap_uses_real_status_mapping(self) -> None:
        row = {
            "component_domain": "销售成交",
            "control_level": "execute",
            "priority_band": "P1",
            "evidence_strength": "medium",
            "当前摘要": "KPI",
            "下一步动作": "补 catalog",
            "对象状态": "gap",
            "负责人模式": "hybrid",
            "最近更新时间": "2026-03-14T01:57:57+08:00",
        }
        transformed = legacy_migration.transform_component_heatmap([row])[0]
        self.assertEqual(transformed["maturity"], "weak")
        self.assertEqual(transformed["priority_band"], "critical")
        self.assertEqual(transformed["human_owner"], "liming")

    def test_transform_responsibility_parses_owner_mode(self) -> None:
        row = {
            "component_domain": "治理控制",
            "control_level": "control, direct",
            "对象状态": "active",
            "负责人模式": "hybrid",
            "目标ID": "G1",
            "证据入口": "proof",
        }
        transformed = legacy_migration.transform_component_responsibility([row])[0]
        self.assertEqual(transformed["control_level"], "control")
        self.assertEqual(transformed["status"], "staffed")
        self.assertFalse(transformed["owner_gap"])

    def test_transform_decision_records_preserves_richer_fields(self) -> None:
        row = {
            "Decision ID": "decision-abaf712e9f",
            "decision_type": "strategic_thread_priority",
            "decision_state": "approved",
            "decision_summary": "Operational ontology v0 is the current G1 implementation priority.",
            "rationale": "Move from research into implementation.",
            "evidence_refs": "proof",
            "decision_time": 1773424677,
        }
        transformed = legacy_migration.transform_decision_records([row])[0]
        self.assertEqual(transformed["decision_id"], "decision-abaf712e9f")
        self.assertEqual(transformed["status"], "approved")
        self.assertEqual(transformed["created_at"], 1773424677)

    def test_merge_evolution_records_keeps_r1_to_r5(self) -> None:
        merged = legacy_migration.merge_evolution_records(
            [{"日志ID": "adagj-001", "时间": "2026-03-10T04:56:44+08:00", "工作状态": "已完成", "调用技能": "feishu-bitable-bridge"}],
            [{"round_id": "R1", "timestamp": 1773626400, "status": "completed", "component_domain": "治理运行骨架", "control_level": "control", "gained": "x", "wasted": "", "next_iterate": "y", "capability_delta": "z", "tests_passed": 16, "commit_hash": "abc", "distortion_resolved": True}],
        )
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[-1]["round_id"], "R1")

    def test_migrator_apply_clears_seed_and_writes_real_data(self) -> None:
        api = FakeMigrationAPI()
        migrator = legacy_migration.DashboardLegacyMigrator(api, artifact_dir=Path("/tmp/dashboard-legacy-migration-tests"))
        result = migrator.migrate(apply_changes=True)

        self.assertEqual(result["readback"]["战略链路"], 1)
        self.assertEqual(result["readback"]["组件热图"], 1)
        self.assertEqual(result["readback"]["组件责任"], 1)
        self.assertEqual(result["readback"]["进化轨迹"], 6)
        self.assertEqual(result["readback"]["总控概览"], 1)
        self.assertEqual(result["readback"]["决策记录"], 1)
        self.assertTrue(api.created_tables)
        self.assertGreater(sum(result["cleared_counts"].values()), 0)
        self.assertTrue(api.updated_fields)


if __name__ == "__main__":
    unittest.main()
