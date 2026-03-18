from __future__ import annotations

import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OSA_METHOD_DOC = PROJECT_ROOT / "docs" / "osa-methodology-v1.md"
OSA_MAPPING_DOC = PROJECT_ROOT / "docs" / "osa-interface-mapping-v1.md"
OSA_SCHEMA = PROJECT_ROOT / "specs" / "osa" / "osa-card.schema.json"
OSA_SAMPLE = PROJECT_ROOT / "specs" / "osa" / "examples" / "task-adagj-001-osa.json"
GOVERNANCE_MAP_DOC = PROJECT_ROOT / "derived" / "reports" / "governance-map-v1.md"
GOVERNANCE_MAP_JSON = PROJECT_ROOT / "derived" / "reports" / "governance-map-v1.json"
README = PROJECT_ROOT / "README.md"


def validate_shape(schema: dict, data: object, path: str = "$", defs: dict | None = None) -> list[str]:
    errors: list[str] = []
    schema_type = schema.get("type")
    defs = defs or schema.get("$defs", {})

    if schema_type == "object":
        if not isinstance(data, dict):
            return [f"{path} expected object"]
        required = schema.get("required", [])
        for key in required:
            if key not in data:
                errors.append(f"{path}.{key} missing")
        properties = schema.get("properties", {})
        for key, value in data.items():
            if key not in properties:
                continue
            prop_schema = properties[key]
            if "$ref" in prop_schema:
                ref_name = prop_schema["$ref"].split("/")[-1]
                prop_schema = defs[ref_name]
            errors.extend(validate_shape(prop_schema, value, f"{path}.{key}", defs))
        return errors

    if schema_type == "array":
        if not isinstance(data, list):
            return [f"{path} expected array"]
        item_schema = schema.get("items", {})
        for index, item in enumerate(data):
            errors.extend(validate_shape(item_schema, item, f"{path}[{index}]", defs))
        return errors

    scalar_types = {
        "string": str,
        "number": (int, float),
        "boolean": bool,
    }
    if schema_type in scalar_types and not isinstance(data, scalar_types[schema_type]):
        return [f"{path} expected {schema_type}"]
    return errors


def iter_nodes(node: dict) -> list[dict]:
    nodes = [node]
    for child in node.get("children", []):
        nodes.extend(iter_nodes(child))
    return nodes


class OsaMethodologyTest(unittest.TestCase):
    def test_docs_and_schema_are_present(self) -> None:
        for path in [OSA_METHOD_DOC, OSA_MAPPING_DOC, OSA_SCHEMA, OSA_SAMPLE, GOVERNANCE_MAP_DOC, GOVERNANCE_MAP_JSON]:
            self.assertTrue(path.exists(), f"missing required OSA artifact: {path}")

    def test_readme_references_osa_artifacts(self) -> None:
        readme = README.read_text(encoding="utf-8")
        self.assertIn("docs/osa-methodology-v1.md", readme)
        self.assertIn("docs/osa-interface-mapping-v1.md", readme)
        self.assertIn("specs/osa/osa-card.schema.json", readme)

    def test_methodology_doc_captures_core_sections(self) -> None:
        content = OSA_METHOD_DOC.read_text(encoding="utf-8")
        for keyword in [
            "六个治理判断",
            "O / Objective",
            "S / Strategy",
            "A / Action",
            "Closure Gate",
            "任务适配度 > 验真能力 > 成本/算力 > 登录态复用 > 新增复杂度",
        ]:
            self.assertIn(keyword, content)

    def test_mapping_doc_covers_all_governance_interfaces(self) -> None:
        content = OSA_MAPPING_DOC.read_text(encoding="utf-8")
        for keyword in ["route / situation-map", "strategy-governor", "review / close-task", "recommended_skill_chain"]:
            self.assertIn(keyword, content)

    def test_sample_matches_declared_shape(self) -> None:
        schema = json.loads(OSA_SCHEMA.read_text(encoding="utf-8"))
        sample = json.loads(OSA_SAMPLE.read_text(encoding="utf-8"))
        errors = validate_shape(schema, sample)
        self.assertEqual(errors, [], "\n".join(errors))
        self.assertEqual(sample["task_context"]["task_id"], "task-adagj-001")
        self.assertEqual(sample["interface_projection"]["strategy_governor"]["thread_id"], "thread-adagj-001")
        self.assertGreaterEqual(len(sample["action"]["capability_orchestration"]), 3)
        self.assertIn("endpoint / account / asset", sample["objective"]["task_goal_definition"]["deliverable"])
        self.assertIn("主图回指 JSON", sample["strategy"]["verification_target"]["evidence_required"])

    def test_governance_map_artifacts_cover_backbone_and_anchor_nodes(self) -> None:
        content = GOVERNANCE_MAP_DOC.read_text(encoding="utf-8")
        for keyword in [
            "space-personal-zero",
            "subject-hay2045",
            "module-governance",
            "thread-adagj-001",
            "endpoint-local-workstation",
            "account-github",
            "asset-db2ee9207e",
        ]:
            self.assertIn(keyword, content)

        payload = json.loads(GOVERNANCE_MAP_JSON.read_text(encoding="utf-8"))
        nodes = {node["node_id"]: node for node in iter_nodes(payload["root"])}
        for required in [
            "space-personal-zero",
            "subject-hay2045",
            "module-governance",
            "task-yuanli-os-mainline-closure-v1",
            "thread-yuanli-os-mainline-closure-v1",
            "task-adagj-001",
            "thread-adagj-001",
            "endpoint-local-workstation",
            "account-github",
            "asset-db2ee9207e",
        ]:
            self.assertIn(required, nodes)

        self.assertEqual(nodes["module-governance"]["node_type"], "operating_module")
        self.assertIn("account-github", nodes["asset-db2ee9207e"]["backlink_ids"])
        self.assertIn("module-governance", nodes["asset-db2ee9207e"]["backlink_ids"])
        self.assertIn("derived/morning-review/morning-review-input.json#thread-adagj-001", nodes["thread-adagj-001"]["source_ref"])


if __name__ == "__main__":
    unittest.main()
