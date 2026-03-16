from __future__ import annotations

import csv
import importlib.util
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "build_r11_v2_skill_inventory.py"


def load_module():
    spec = importlib.util.spec_from_file_location("build_r11_v2_skill_inventory", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_source_record_extracts_frontmatter_and_sections():
    module = load_module()
    text = """---
name: demo-skill
description: Demo description for inventory
---
# Inputs
- one
- two

# Expected Outputs
- JSON

Use when the user wants demo automation.
"""
    record = module.build_source_record(
        text=text,
        source_repo="demo-repo",
        file_path="skills/demo-skill/SKILL.md",
        source_type="github",
        last_updated="2026-03-16T00:00:00Z",
        file_size_bytes=len(text),
    )
    assert record.skill_id == "demo-skill"
    assert record.skill_name == "demo-skill"
    assert record.description == "Demo description for inventory"
    assert "one" in record.input_params
    assert "JSON" in record.output_format
    assert record.status == "active"


def test_dedupe_and_merge_prefers_github_and_merges_sources():
    module = load_module()
    github_record = module.SourceRecord(
        skill_id="demo-skill",
        skill_name="demo-skill",
        source_repo="demo-repo",
        file_path="skills/demo-skill/SKILL.md",
        source_type="github",
        description="GitHub source",
        trigger_keywords=["demo"],
        input_params="a",
        output_format="b",
        dependencies=["playwright"],
        last_updated="2026-03-16T00:00:00Z",
        file_size_bytes=10,
        status="active",
        category="工具",
    )
    local_record = module.SourceRecord(
        skill_id="demo-skill",
        skill_name="demo-skill",
        source_repo="local-codex",
        file_path="/Users/test/.codex/skills/demo-skill/SKILL.md",
        source_type="local_codex",
        description="Local source",
        trigger_keywords=["automation"],
        input_params="c",
        output_format="d",
        dependencies=["linear"],
        last_updated="2026-03-15T00:00:00Z",
        file_size_bytes=20,
        status="active",
        category="治理",
    )
    merged = module.dedupe_and_merge([local_record, github_record])
    assert len(merged) == 1
    item = merged[0]
    assert item["source_type"] == "github"
    assert sorted(item["source_types"]) == ["github", "local_codex"]
    assert sorted(item["dependencies"]) == ["linear", "playwright"]


def test_parse_tool_definitions_reads_server_file():
    module = load_module()
    tools = module.parse_tool_definitions(PROJECT_ROOT / "mcp_server" / "server.py")
    tool_names = {tool["name"] for tool in tools}
    assert "route_task" in tool_names
    assert "list_skills" in tool_names


def test_write_csv_outputs_expected_columns():
    module = load_module()
    rows = [
        {
            "skill_id": "demo-skill",
            "skill_name": "demo-skill",
            "source_repo": "demo-repo",
            "file_path": "skills/demo-skill/SKILL.md",
            "source_type": "github",
            "description": "Demo",
            "trigger_keywords": ["alpha", "beta"],
            "dependencies": ["linear"],
            "last_updated": "2026-03-16T00:00:00Z",
            "status": "active",
            "category": "工具",
        }
    ]
    with tempfile.TemporaryDirectory() as tmp_dir:
        csv_path = Path(tmp_dir) / "skill_inventory.csv"
        module.write_csv(rows, csv_path)
        with csv_path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            output = list(reader)
    assert output[0]["skill_id"] == "demo-skill"
    assert output[0]["trigger_keywords"] == "alpha | beta"
    assert output[0]["action_recommendation"] == ""
