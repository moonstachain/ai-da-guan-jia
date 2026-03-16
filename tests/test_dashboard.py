from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "dashboard" / "schemas"
VALID_FIELD_TYPES = {"text", "number", "single_select", "multi_select", "checkbox", "datetime"}


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_schema_files_parse() -> None:
    schema_files = sorted(SCHEMA_DIR.glob("*.json"))
    assert len(schema_files) == 5
    for path in schema_files:
        data = _load_json(path)
        assert {"table_name", "layer", "purpose", "fields"} <= data.keys()


def test_schema_fields_are_well_formed() -> None:
    for path in SCHEMA_DIR.glob("*.json"):
        data = _load_json(path)
        for field in data["fields"]:
            assert {"name", "type"} <= field.keys()
            assert field["type"] in VALID_FIELD_TYPES


def test_single_select_fields_declare_options() -> None:
    for path in SCHEMA_DIR.glob("*.json"):
        data = _load_json(path)
        for field in data["fields"]:
            if field["type"] == "single_select":
                assert field.get("options")


def test_dashboard_spec_has_five_blocks() -> None:
    spec = _load_json(REPO_ROOT / "dashboard" / "dashboard_spec.json")
    assert len(spec["blocks"]) == 5


def test_dashboard_blocks_have_required_keys() -> None:
    spec = _load_json(REPO_ROOT / "dashboard" / "dashboard_spec.json")
    for block in spec["blocks"]:
        assert {"id", "title", "purpose"} <= block.keys()


def test_seed_data_module_executes_successfully(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["YOS_DASHBOARD_SEED_DIR"] = str(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "dashboard.seed_data"],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Generated dashboard seed data:" in result.stdout


def test_seed_data_writes_all_expected_files(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["YOS_DASHBOARD_SEED_DIR"] = str(tmp_path)
    subprocess.run(
        [sys.executable, "-m", "dashboard.seed_data"],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert sorted(path.name for path in tmp_path.glob("*.json")) == [
        "component_heatmap.json",
        "component_responsibility.json",
        "control_overview.json",
        "evolution_tracker.json",
        "strategy_linkage.json",
    ]


def test_control_overview_contains_single_record(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["YOS_DASHBOARD_SEED_DIR"] = str(tmp_path)
    subprocess.run([sys.executable, "-m", "dashboard.seed_data"], cwd=REPO_ROOT, env=env, check=True)
    payload = _load_json(tmp_path / "control_overview.json")
    assert len(payload) == 1


def test_component_heatmap_contains_twelve_records(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["YOS_DASHBOARD_SEED_DIR"] = str(tmp_path)
    subprocess.run([sys.executable, "-m", "dashboard.seed_data"], cwd=REPO_ROOT, env=env, check=True)
    payload = _load_json(tmp_path / "component_heatmap.json")
    assert len(payload) == 12


def test_evolution_tracker_contains_five_records(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["YOS_DASHBOARD_SEED_DIR"] = str(tmp_path)
    subprocess.run([sys.executable, "-m", "dashboard.seed_data"], cwd=REPO_ROOT, env=env, check=True)
    payload = _load_json(tmp_path / "evolution_tracker.json")
    assert len(payload) == 5


def test_strategy_linkage_contains_seeded_records(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["YOS_DASHBOARD_SEED_DIR"] = str(tmp_path)
    subprocess.run([sys.executable, "-m", "dashboard.seed_data"], cwd=REPO_ROOT, env=env, check=True)
    payload = _load_json(tmp_path / "strategy_linkage.json")
    assert len(payload) >= 1


def test_component_responsibility_contains_twelve_records(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["YOS_DASHBOARD_SEED_DIR"] = str(tmp_path)
    subprocess.run([sys.executable, "-m", "dashboard.seed_data"], cwd=REPO_ROOT, env=env, check=True)
    payload = _load_json(tmp_path / "component_responsibility.json")
    assert len(payload) == 12


def test_evolution_round_ids_are_unique(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["YOS_DASHBOARD_SEED_DIR"] = str(tmp_path)
    subprocess.run([sys.executable, "-m", "dashboard.seed_data"], cwd=REPO_ROOT, env=env, check=True)
    payload = _load_json(tmp_path / "evolution_tracker.json")
    round_ids = [row["round_id"] for row in payload]
    assert len(round_ids) == len(set(round_ids))


def test_heatmap_covers_all_domain_level_combinations(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["YOS_DASHBOARD_SEED_DIR"] = str(tmp_path)
    subprocess.run([sys.executable, "-m", "dashboard.seed_data"], cwd=REPO_ROOT, env=env, check=True)
    payload = _load_json(tmp_path / "component_heatmap.json")
    combos = {(row["component_domain"], row["control_level"]) for row in payload}
    expected = {
        ("governance", "direct"),
        ("governance", "control"),
        ("governance", "execute"),
        ("sales", "direct"),
        ("sales", "control"),
        ("sales", "execute"),
        ("delivery", "direct"),
        ("delivery", "control"),
        ("delivery", "execute"),
        ("clone", "direct"),
        ("clone", "control"),
        ("clone", "execute"),
    }
    assert combos == expected


def test_heatmap_domains_match_schema_options(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["YOS_DASHBOARD_SEED_DIR"] = str(tmp_path)
    subprocess.run([sys.executable, "-m", "dashboard.seed_data"], cwd=REPO_ROOT, env=env, check=True)
    payload = _load_json(tmp_path / "component_heatmap.json")
    schema = _load_json(SCHEMA_DIR / "component_heatmap.json")
    allowed_domains = next(field["options"] for field in schema["fields"] if field["name"] == "component_domain")
    assert all(row["component_domain"] in allowed_domains for row in payload)


def test_evolution_statuses_match_schema_options(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["YOS_DASHBOARD_SEED_DIR"] = str(tmp_path)
    subprocess.run([sys.executable, "-m", "dashboard.seed_data"], cwd=REPO_ROOT, env=env, check=True)
    payload = _load_json(tmp_path / "evolution_tracker.json")
    schema = _load_json(SCHEMA_DIR / "evolution_tracker.json")
    allowed_statuses = next(field["options"] for field in schema["fields"] if field["name"] == "status")
    assert all(row["status"] in allowed_statuses for row in payload)
