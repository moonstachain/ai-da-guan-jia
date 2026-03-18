from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "black_satellite_asset_inventory.py"


def load_module():
    spec = importlib.util.spec_from_file_location("black_satellite_asset_inventory", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class BlackSatelliteAssetInventoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_categorize_skill_assigns_expected_buckets(self):
        self.assertEqual(self.module.categorize_skill("ai-da-guan-jia"), "治理与路由")
        self.assertEqual(self.module.categorize_skill("feishu-bitable-bridge"), "飞书与知识中台")
        self.assertEqual(self.module.categorize_skill("playwright"), "浏览器与执行面")
        self.assertEqual(self.module.categorize_skill("agency-engineering"), "工程与 Agency")
        self.assertEqual(self.module.categorize_skill("yuanli-core"), "内容与原力体系")
        self.assertEqual(
            self.module.categorize_skill("black-satellite-multimodel-router"),
            "黑色卫星特化",
        )

    def test_build_skill_inventory_marks_legacy_agency_members_as_not_recommended(self):
        payload = self.module.build_skill_inventory(
            [
                "agency-engineering",
                "agency-engineering-frontend-developer",
                "black-satellite-multimodel-router",
            ]
        )
        rows = {item["name"]: item for item in payload["skills"]}
        self.assertEqual(rows["agency-engineering"]["readiness"], "可立即复用")
        self.assertEqual(rows["agency-engineering-frontend-developer"]["readiness"], "暂不建议复用")
        self.assertEqual(rows["black-satellite-multimodel-router"]["reuse_value"], "高")

    def test_build_reuse_shortlist_surfaces_memory_gap(self):
        machine_profile = {
            "resolved_source_id": "satellite-02",
            "binding_status": "connected",
            "machine": {"os_version": "15.7.5"},
            "codex_home": {
                "model": "gpt-5.4",
                "skills_count": 127,
                "automations_count": 11,
                "mcp_servers": ["context7", "github", "flomo", "playwright"],
            },
            "repo_count": 8,
        }
        skill_inventory = {
            "skills": [
                {
                    "name": "ai-da-guan-jia",
                    "category": "治理与路由",
                    "readiness": "可立即复用",
                    "best_use_case": "x",
                },
                {
                    "name": "black-satellite-multimodel-router",
                    "category": "黑色卫星特化",
                    "readiness": "可立即复用",
                    "best_use_case": "x",
                },
                {
                    "name": "knowledge-orchestrator",
                    "category": "治理与路由",
                    "readiness": "可立即复用",
                    "best_use_case": "x",
                },
                {
                    "name": "feishu-bitable-bridge",
                    "category": "飞书与知识中台",
                    "readiness": "可条件复用",
                    "best_use_case": "x",
                },
                {
                    "name": "opencli-platform-bridge",
                    "category": "浏览器与执行面",
                    "readiness": "可条件复用",
                    "best_use_case": "x",
                },
            ]
        }
        core_assets = {
            "assets": [
                {
                    "name": "black_satellite_cli_selfcheck.sh",
                    "asset_type": "script_entrypoint",
                    "status": "present",
                    "how_to_reuse": "x",
                },
                {
                    "name": "black_satellite_human_action.sh",
                    "asset_type": "script_entrypoint",
                    "status": "present",
                    "how_to_reuse": "x",
                },
                {
                    "name": "ai_da_guan_jia.py",
                    "asset_type": "workflow_entrypoint",
                    "status": "present",
                    "how_to_reuse": "x",
                },
            ]
        }
        output = self.module.build_reuse_shortlist(machine_profile, skill_inventory, core_assets)
        self.assertIn("Agency 重复入口仍然偏多", output)
        self.assertIn("~/.codex/memory.md", output)
