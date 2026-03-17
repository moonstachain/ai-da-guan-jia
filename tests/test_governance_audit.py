from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "governance_audit.py"
MODULE_SPEC = importlib.util.spec_from_file_location("governance_audit", SCRIPT_PATH)
assert MODULE_SPEC and MODULE_SPEC.loader
spec = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(spec)


def test_count_naming_traps_counts_rows() -> None:
    sample = """## ⚠️ 命名陷阱（防止 Claude/Codex 误判）
| 错误假设 | 实际情况 |
|---------|---------|
| A | B |
| C | D |

---
"""
    assert spec.count_naming_traps(sample) == 2
