from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "r15_evolution_chronicle.py"
MODULE_SPEC = importlib.util.spec_from_file_location("r15_evolution_chronicle", SCRIPT_PATH)
assert MODULE_SPEC and MODULE_SPEC.loader
spec = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(spec)


def test_r15_dataset_contract() -> None:
    payload = json.loads(Path(spec.DATA_PATH).read_text(encoding="utf-8"))
    records = payload["records"]
    assert len(records) == 34
    assert sum(1 for row in records if row["version"] == "1.0") == 15
    assert sum(1 for row in records if row["version"] == "2.0") == 19


def test_r15_field_contract() -> None:
    assert len(spec.FIELD_SPECS) == 16
    assert spec.FIELD_SPECS[0]["field_name"] == "milestone_id"
    assert spec.FIELD_SPECS[-1]["field_name"] == "tests_passed"
