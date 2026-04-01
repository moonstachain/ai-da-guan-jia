from __future__ import annotations

import argparse
import io
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = PROJECT_ROOT / "work" / "ai-da-guan-jia" / "scripts"
SCRIPT_PATH = SCRIPT_ROOT / "ai_da_guan_jia.py"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class MemoryPatchWriterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPT_ROOT))
        cls.module = load_module("test_ai_da_guan_jia_memory_patch", SCRIPT_PATH)

    def make_args(self, **overrides):
        base = {
            "input": "-",
            "memory_path": None,
        }
        base.update(overrides)
        return argparse.Namespace(**base)

    def patch_home(self, root: Path):
        return patch.object(self.module, "CODEX_HOME", root / ".codex")

    def make_payload(self, **overrides):
        payload = {
            "run_id": "adagj-memory-distill-test",
            "created_at": "2026-04-01T04:30:00+08:00",
            "title": "04:30 记忆蒸馏",
            "summary_lines": ["稳定摘要一"],
            "stable_rules": ["memory-patch 只写 durable 内容。"],
            "restore_order": ["当前线程", "~/.codex/memory.md"],
            "boundary_updates": ["Feishu / GitHub 继续只作为 mirror。"],
            "source_refs": ["runs/2026-04-01/adagj-memory-distill"],
            "open_questions": ["embedding 层是否要补。"],
        }
        payload.update(overrides)
        return payload

    def test_parser_registers_memory_patch(self) -> None:
        parser = self.module.build_parser()
        parsed = parser.parse_args(["memory-patch", "--input", "-"])
        self.assertEqual(parsed.func.__name__, "command_memory_patch")
        self.assertIsNone(parsed.memory_path)

    def test_memory_patch_writes_and_replaces_stable_block(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            memory_path = root / ".codex" / "memory.md"
            memory_path.parent.mkdir(parents=True, exist_ok=True)
            memory_path.write_text("# AI大管家 Memory\n\n旧内容。\n", encoding="utf-8")

            with self.patch_home(root):
                with patch.object(sys, "stdin", io.StringIO(json.dumps(self.make_payload()))):
                    exit_code = self.module.command_memory_patch(self.make_args())

            self.assertEqual(exit_code, 0)
            first_text = memory_path.read_text(encoding="utf-8")
            self.assertIn(self.module.MEMORY_PATCH_SECTION_TITLE, first_text)
            self.assertEqual(first_text.count(self.module.MEMORY_PATCH_START_MARKER), 1)
            self.assertEqual(first_text.count(self.module.MEMORY_PATCH_END_MARKER), 1)
            self.assertIn("稳定摘要一", first_text)
            self.assertIn("memory-patch 只写 durable 内容。", first_text)

            updated_payload = self.make_payload(
                summary_lines=["稳定摘要二"],
                stable_rules=["memory-patch 只写 durable 内容。", "摘要只收录稳定结论。"],
            )
            with self.patch_home(root):
                with patch.object(sys, "stdin", io.StringIO(json.dumps(updated_payload))):
                    exit_code = self.module.command_memory_patch(self.make_args())

            self.assertEqual(exit_code, 0)
            second_text = memory_path.read_text(encoding="utf-8")
            self.assertNotIn("稳定摘要一", second_text)
            self.assertIn("稳定摘要二", second_text)
            self.assertEqual(second_text.count(self.module.MEMORY_PATCH_START_MARKER), 1)
            self.assertEqual(second_text.count(self.module.MEMORY_PATCH_END_MARKER), 1)

    def test_memory_patch_noop_leaves_memory_file_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            memory_path = root / ".codex" / "memory.md"
            memory_path.parent.mkdir(parents=True, exist_ok=True)
            before = "# AI大管家 Memory\n\n保留这段原文。\n"
            memory_path.write_text(before, encoding="utf-8")

            noop_payload = self.make_payload(no_op=True)
            with self.patch_home(root):
                with patch.object(sys, "stdin", io.StringIO(json.dumps(noop_payload))):
                    exit_code = self.module.command_memory_patch(self.make_args())

            self.assertEqual(exit_code, 0)
            after = memory_path.read_text(encoding="utf-8")
            self.assertEqual(after, before)
            self.assertNotIn(self.module.MEMORY_PATCH_START_MARKER, after)


if __name__ == "__main__":
    unittest.main()
