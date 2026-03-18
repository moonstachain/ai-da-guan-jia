from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path("/Users/liming/Documents/codex-ai-gua-jia-01")
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


class SatelliteMultimodelRouterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPT_ROOT))
        cls.module = load_module("test_ai_da_guan_jia_satellite_multimodel_router", SCRIPT_PATH)

    def make_args(self, **overrides):
        base = {
            "satellite": "黑色",
            "task": "请把这个中文任务拆成可执行步骤",
            "image": [],
            "need_search": False,
            "need_citations": False,
            "force_model": "",
            "dry_run": False,
            "json": True,
            "timeout": 300,
            "run_id": "adagj-multimodel-router",
            "created_at": "2026-03-16T10:00:00+08:00",
        }
        base.update(overrides)
        return types.SimpleNamespace(**base)

    def fake_resolution(self, alias: str):
        self.assertEqual(alias, "黑色")
        return {
            "requested_alias": alias,
            "resolved_satellite_id": "satellite-black",
            "resolved_clone_id": "clone-satellite-black",
            "resolved_source_id": "satellite-02",
            "dispatch_mode": "remote_ssh_exec",
            "status": "connected",
        }

    def fake_remote_info(self, source_id: str):
        self.assertEqual(source_id, "satellite-02")
        return {
            "source_id": source_id,
            "host": "192.168.31.86",
            "user": "liming",
            "workspace_root": "/Users/liming/Documents/codex-ai-gua-jia-01",
        }

    def test_parser_registers_satellite_multimodel_router(self) -> None:
        parser = self.module.build_parser()
        parsed = parser.parse_args(["satellite-multimodel-router", "--task", "solve this"])
        self.assertEqual(parsed.func.__name__, "command_satellite_multimodel_router")
        self.assertEqual(parsed.satellite, "黑色")
        self.assertEqual(parsed.timeout, self.module.SATELLITE_SESSION_DEFAULT_TIMEOUT)
        self.assertFalse(parsed.dry_run)

    def test_route_task_covers_eight_static_cases(self) -> None:
        cases = [
            ("修复这个 Python bug 并给出 patch 思路", {}, "gpt54"),
            ("请证明这个数学题并给出结构化推导", {}, "gpt54"),
            ("把这篇长文改写成更统一的文风", {}, "claude4"),
            ("请把这个中文工作流拆成 5 个 Agent 步骤", {}, "kimi"),
            ("分析这张截图里的异常状态", {"image_path": "/tmp/demo.png"}, "gemini25"),
            ("帮我做一个多模态图片理解总结", {}, "gemini25"),
            ("帮我实时搜索今天的 X 讨论并给引用", {"need_search": True, "need_citations": True}, "gpt54"),
            ("Plain English task with no strong specialist markers.", {}, "gpt54"),
        ]
        for task_text, extra, expected in cases:
            route = self.module.satellite_multimodel_route_task(
                task_text=task_text,
                image_path=extra.get("image_path", ""),
                need_search=bool(extra.get("need_search", False)),
                need_citations=bool(extra.get("need_citations", False)),
                force_model="",
            )
            self.assertEqual(route["model_id"], expected, msg=task_text)

    def test_force_model_overrides_auto_route(self) -> None:
        route = self.module.satellite_multimodel_route_task(
            task_text="修复这段 Python 代码并解释逻辑",
            image_path="",
            need_search=False,
            need_citations=False,
            force_model="kimi",
        )
        self.assertEqual(route["model_id"], "kimi")
        self.assertEqual(route["route_family"], "forced")

    def test_dry_run_only_writes_route_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            args = self.make_args(dry_run=True)
            with patch.multiple(self.module, RUNS_ROOT=runs_root):
                with patch.object(self.module, "resolve_satellite_assignment", side_effect=self.fake_resolution):
                    with patch.object(self.module, "tool_glue_remote_host_metadata", side_effect=self.fake_remote_info):
                        with patch.object(self.module, "satellite_multimodel_activate_provider") as activate_mock:
                            exit_code = self.module.command_satellite_multimodel_router(args)

            self.assertEqual(exit_code, 0)
            activate_mock.assert_not_called()
            run_dir = runs_root / "2026-03-16" / args.run_id
            result = json.loads((run_dir / "router-result.json").read_text(encoding="utf-8"))
            self.assertTrue(result["dry_run"])
            self.assertIn("selected_model", result)

    def test_gemini_trust_block_returns_fixed_human_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            local_root = Path(tempdir) / "workspace"
            local_root.mkdir(parents=True, exist_ok=True)
            image_path = local_root / "sample.png"
            image_path.write_bytes(b"fake-image")
            args = self.make_args(task="分析这张图片", image=[str(image_path)])
            with patch.multiple(self.module, RUNS_ROOT=runs_root, PROJECT_ROOT=local_root):
                with patch.object(self.module, "resolve_satellite_assignment", side_effect=self.fake_resolution):
                    with patch.object(self.module, "tool_glue_remote_host_metadata", side_effect=self.fake_remote_info):
                        with patch.object(
                            self.module,
                            "satellite_multimodel_probe_gemini_trust",
                            return_value={
                                "returncode": 124,
                                "stdout": "Do you trust the files in this folder?\n1. Trust folder\n2. Trust parent folder\n3. Don't trust\n",
                                "stderr": "",
                            },
                        ):
                            exit_code = self.module.command_satellite_multimodel_router(args)

            self.assertEqual(exit_code, 0)
            run_dir = runs_root / "2026-03-16" / args.run_id
            result = json.loads((run_dir / "router-result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "blocked_needs_user")
            self.assertEqual(result["blocking_reason"], "remote_gemini_workspace_trust_required")
            self.assertIn("Trust folder", result["human_action_contract"]["click_what"])

    def test_provider_switch_failure_uses_one_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            args = self.make_args(task="把这篇长文重写成统一风格")
            with patch.multiple(self.module, RUNS_ROOT=runs_root):
                with patch.object(self.module, "resolve_satellite_assignment", side_effect=self.fake_resolution):
                    with patch.object(self.module, "tool_glue_remote_host_metadata", side_effect=self.fake_remote_info):
                        with patch.object(
                            self.module,
                            "satellite_multimodel_activate_provider",
                            side_effect=[
                                {"returncode": 1, "stdout": "", "stderr": "provider missing"},
                                {"returncode": 0, "stdout": "activated_provider=or-gpt54", "stderr": ""},
                            ],
                        ):
                            with patch.object(
                                self.module,
                                "satellite_multimodel_run_remote_codex_exec_json",
                                return_value={
                                    "returncode": 0,
                                    "stdout": "",
                                    "stderr": "",
                                    "json": {
                                        "status": "completed",
                                        "response_text": "done",
                                        "sources": [],
                                        "blocking_reason": "",
                                        "next_action": "",
                                    },
                                },
                            ):
                                exit_code = self.module.command_satellite_multimodel_router(args)

            self.assertEqual(exit_code, 0)
            run_dir = runs_root / "2026-03-16" / args.run_id
            result = json.loads((run_dir / "router-result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["requested_model"], "claude4")
            self.assertEqual(result["selected_model"], "gpt54")
            self.assertTrue(result["fallback_used"])

    def test_provider_switch_failure_after_fallback_blocks_system(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            runs_root = Path(tempdir) / "runs"
            args = self.make_args(task="把这篇长文重写成统一风格")
            with patch.multiple(self.module, RUNS_ROOT=runs_root):
                with patch.object(self.module, "resolve_satellite_assignment", side_effect=self.fake_resolution):
                    with patch.object(self.module, "tool_glue_remote_host_metadata", side_effect=self.fake_remote_info):
                        with patch.object(
                            self.module,
                            "satellite_multimodel_activate_provider",
                            side_effect=[
                                {"returncode": 1, "stdout": "", "stderr": "provider missing"},
                                {"returncode": 1, "stdout": "", "stderr": "fallback missing"},
                            ],
                        ):
                            exit_code = self.module.command_satellite_multimodel_router(args)

            self.assertEqual(exit_code, 1)
            run_dir = runs_root / "2026-03-16" / args.run_id
            result = json.loads((run_dir / "router-result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "blocked_system")
            self.assertIn("provider_switch_failed", result["blocking_reason"])


if __name__ == "__main__":
    unittest.main()
