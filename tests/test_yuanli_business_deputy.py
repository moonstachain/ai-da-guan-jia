from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class YuanliBusinessDeputyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(PROJECT_ROOT))
        cls.core = importlib.import_module("yuanli_governance.core")
        cls.contracts = importlib.import_module("yuanli_governance.contracts")

    def test_runtime_binding_maps_business_module_to_deputy(self) -> None:
        binding = self.core.runtime_binding_for_module(module_code="sales")

        self.assertEqual(binding["module_id"], "module-sales")
        self.assertEqual(binding["owner_subject_id"], "subject-collab-owner")
        self.assertEqual(binding["ai_subject_id"], "subject-agent-sales")
        self.assertEqual(binding["deputy_subject_id"], self.contracts.BUSINESS_DEPUTY_SUBJECT_ID)

    def test_initialize_task_runtime_fields_backfills_business_runtime_binding(self) -> None:
        task = self.core.initialize_task_runtime_fields(
            {
                "task_id": "task-test-sales",
                "title": "销售报价推进",
                "target_module_id": "module-sales",
                "selected_skills": ["knowledge-orchestrator"],
            }
        )

        self.assertEqual(task["module_code"], "sales")
        self.assertEqual(task["owner_subject_id"], "subject-collab-owner")
        self.assertEqual(task["ai_subject_id"], "subject-agent-sales")
        self.assertEqual(task["deputy_subject_id"], self.contracts.BUSINESS_DEPUTY_SUBJECT_ID)

    def test_build_federation_entities_adds_business_deputy_and_module_relations(self) -> None:
        _, subjects, _, _, modules, relations = self.core.build_federation_entities(
            scope={"ontology_path": str(PROJECT_ROOT / "canonical" / "ontology" / "ontology.db")},
            skills=[
                {"skill_id": "knowledge-orchestrator"},
                {"skill_id": "yuanli-core"},
                {"skill_id": "feishu-bitable-bridge"},
            ],
            assets=[],
        )

        subject_ids = {item["subject_id"] for item in subjects}
        self.assertIn(self.contracts.BUSINESS_DEPUTY_SUBJECT_ID, subject_ids)

        deputy_module_relations = {
            relation["to_id"]
            for relation in relations
            if relation["relation_type"] == "ai_deputy_oversees_module"
            and relation["from_id"] == self.contracts.BUSINESS_DEPUTY_SUBJECT_ID
        }
        self.assertEqual(
            deputy_module_relations,
            {f"module-{code}" for code in self.contracts.BUSINESS_MODULE_CODES},
        )

        module_index = {item["module_id"]: item for item in modules}
        self.assertEqual(
            module_index["module-public"]["deputy_subject_id"],
            self.contracts.BUSINESS_DEPUTY_SUBJECT_ID,
        )
        self.assertEqual(module_index["module-delivery"]["deputy_subject_id"], "")


if __name__ == "__main__":
    unittest.main()
