from __future__ import annotations

import argparse
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


class WindowHeartbeatTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPT_ROOT))
        cls.module = load_module("test_ai_da_guan_jia_window_heartbeat", SCRIPT_PATH)

    def patch_paths(self, root: Path):
        resolved_root = root.resolve()
        artifacts_root = resolved_root / "artifacts"
        heartbeat_root = artifacts_root / "heartbeat"
        window_heartbeat_root = heartbeat_root / "windows"
        return patch.multiple(
            self.module,
            PROJECT_ROOT=resolved_root,
            ARTIFACTS_ROOT=artifacts_root,
            RUNS_ROOT=artifacts_root / "runs",
            PROJECT_HEARTBEAT_ROOT=heartbeat_root,
            WINDOW_HEARTBEAT_ROOT=window_heartbeat_root,
            WINDOW_HEARTBEAT_CURRENT_ROOT=window_heartbeat_root / "current",
            WINDOW_HEARTBEAT_ROUNDS_ROOT=window_heartbeat_root / "rounds",
        )

    def make_write_args(self, **overrides):
        payload = {
            "window_id": "ops-mainline",
            "role": "运营主线",
            "current_phase": "M3 复验等待",
            "last_action": "完成 Phase 2 live evidence 并等待页面执行面重发",
            "current_status": "waiting_external",
            "evidence": ["work/ai-da-guan-jia/artifacts/ai-da-guan-jia/runs/2026-03-15/example/result.json"],
            "sole_blocker": "none",
        }
        payload.update(overrides)
        return argparse.Namespace(**payload)

    def make_govern_args(self, **overrides):
        payload = {
            "window_id": "",
            "stall_minutes": 45,
            "silent_lost_minutes": 120,
        }
        payload.update(overrides)
        return argparse.Namespace(**payload)

    def test_parser_registers_window_heartbeat_govern(self) -> None:
        parser = self.module.build_parser()
        parsed = parser.parse_args(["window-heartbeat", "govern"])
        self.assertEqual(parsed.func.__name__, "command_window_heartbeat_govern")

    def test_window_heartbeat_govern_writes_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            evidence_path = root / "work" / "ai-da-guan-jia" / "artifacts" / "ai-da-guan-jia" / "runs" / "2026-03-15" / "example" / "result.json"
            evidence_path.parent.mkdir(parents=True, exist_ok=True)
            evidence_path.write_text('{"status":"ok"}\n', encoding="utf-8")

            with self.patch_paths(root):
                with patch.object(self.module, "iso_now", return_value="2026-03-15T13:00:00+08:00"):
                    self.module.command_window_heartbeat_write(
                        self.make_write_args(
                            window_id="ops-mainline",
                            current_status="running",
                            evidence=[str(evidence_path)],
                            sole_blocker="none",
                        )
                    )
                with patch.object(self.module, "iso_now", return_value="2026-03-15T13:05:00+08:00"):
                    self.module.command_window_heartbeat_write(
                        self.make_write_args(
                            window_id="black-satellite",
                            role="黑色卫星支线",
                            current_phase="surface alignment",
                            current_status="blocked",
                            last_action="确认 preview 仍落在旧静态 JSON cockpit",
                            evidence=[str(evidence_path)],
                            sole_blocker="目标 preview 仍是旧静态 JSON 页面，不是真实 dashboard 画布",
                        )
                    )
                with patch.object(self.module, "iso_now", return_value="2026-03-15T13:30:00+08:00"):
                    result = self.module.command_window_heartbeat_govern(self.make_govern_args())

            self.assertEqual(result, 0)
            governance_path = root / "artifacts" / "heartbeat" / "windows" / "current" / "governance-summary.json"
            payload = json.loads(governance_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["decision_counts"]["继续"], 1)
            self.assertEqual(payload["decision_counts"]["裁决"], 1)
            decisions = {item["window_id"]: item for item in payload["decisions"]}
            self.assertTrue(decisions["ops-mainline"]["auto_dispatch_allowed"])
            self.assertEqual(decisions["ops-mainline"]["decision"], "继续")
            self.assertTrue(decisions["black-satellite"]["auto_dispatch_allowed"])
            self.assertEqual(decisions["black-satellite"]["decision"], "裁决")

    def test_window_heartbeat_govern_respects_human_boundary_and_silent_lost(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_paths(root):
                with patch.object(self.module, "iso_now", return_value="2026-03-15T12:40:00+08:00"):
                    self.module.command_window_heartbeat_write(
                        self.make_write_args(
                            window_id="ops-mainline",
                            current_status="waiting_user",
                            sole_blocker="等待人类登录并完成发布确认",
                        )
                    )
                with patch.object(self.module, "iso_now", return_value="2026-03-15T10:00:00+08:00"):
                    self.module.command_window_heartbeat_write(
                        self.make_write_args(
                            window_id="silent-branch",
                            role="普通支线",
                            current_phase="waiting report",
                            current_status="running",
                            last_action="写完上一轮产物后未再更新",
                            evidence=[],
                            sole_blocker="none",
                        )
                    )
                with patch.object(self.module, "iso_now", return_value="2026-03-15T13:30:00+08:00"):
                    result = self.module.command_window_heartbeat_govern(
                        self.make_govern_args(silent_lost_minutes=120)
                    )

            self.assertEqual(result, 0)
            governance_path = root / "artifacts" / "heartbeat" / "windows" / "current" / "governance-summary.json"
            payload = json.loads(governance_path.read_text(encoding="utf-8"))
            decisions = {item["window_id"]: item for item in payload["decisions"]}
            self.assertEqual(decisions["ops-mainline"]["decision"], "等待")
            self.assertFalse(decisions["ops-mainline"]["auto_dispatch_allowed"])
            self.assertTrue(decisions["ops-mainline"]["human_boundary"])
            self.assertEqual(decisions["silent-branch"]["decision"], "收口")
            self.assertTrue(decisions["silent-branch"]["auto_dispatch_allowed"])

    def test_window_heartbeat_govern_ignores_historical_login_text_when_current_blocker_is_technical(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            evidence_path = root / "output" / "example" / "lane-result.json"
            evidence_path.parent.mkdir(parents=True, exist_ok=True)
            evidence_path.write_text('{"status":"ok"}\n', encoding="utf-8")

            with self.patch_paths(root):
                with patch.object(self.module, "iso_now", return_value="2026-03-15T13:05:00+08:00"):
                    self.module.command_window_heartbeat_write(
                        self.make_write_args(
                            window_id="black-satellite",
                            role="黑色卫星支线",
                            current_phase="PMO beta dispatch",
                            current_status="blocked",
                            last_action="已完成登录、授权和切模型校验，现在只剩技术对齐",
                            evidence=[str(evidence_path)],
                            sole_blocker="当前缺口是 repo-local 证据回写协议未收敛，仍需总控做技术裁决",
                        )
                    )
                with patch.object(self.module, "iso_now", return_value="2026-03-15T13:30:00+08:00"):
                    result = self.module.command_window_heartbeat_govern(self.make_govern_args())

            self.assertEqual(result, 0)
            governance_path = root / "artifacts" / "heartbeat" / "windows" / "current" / "governance-summary.json"
            payload = json.loads(governance_path.read_text(encoding="utf-8"))
            decisions = {item["window_id"]: item for item in payload["decisions"]}
            self.assertEqual(decisions["black-satellite"]["decision"], "裁决")
            self.assertFalse(decisions["black-satellite"]["human_boundary"])

    def test_window_heartbeat_summary_and_governance_absorb_cleanup_annotations(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            evidence_path = root / "output" / "example" / "lane-result.json"
            evidence_path.parent.mkdir(parents=True, exist_ok=True)
            evidence_path.write_text('{"status":"ok"}\n', encoding="utf-8")

            cleanup_root = (
                root
                / "artifacts"
                / "runs"
                / "2026-03-16"
                / "adagj-black-satellite-governance-cleanup-01"
            )
            task_a_dir = cleanup_root / "task-a-legacy-black-satellite"
            task_b_dir = cleanup_root / "task-b-window-observability-heartbeat"
            task_a_dir.mkdir(parents=True, exist_ok=True)
            task_b_dir.mkdir(parents=True, exist_ok=True)
            legacy_json = task_a_dir / "legacy-black-satellite-judgement.json"
            observability_json = task_b_dir / "window-observability-cleanup.json"
            legacy_json.write_text(
                json.dumps(
                    {
                        "recommended_label": "archived_history_line",
                        "legacy_window": {"window_id": "black-satellite"},
                        "recommended_control_tower_action": {"why": "旧 black-satellite 已被历史化处理。"},
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            observability_json.write_text(
                json.dumps(
                    {
                        "recommended_action": "downgrade_to_history",
                        "window": {"window_id": "window-observability-heartbeat"},
                        "recommended_control_tower_action": {"why": "陈旧观测对象应降为历史。"},
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (cleanup_root / "run-manifest.json").write_text(
                json.dumps(
                    {
                        "package_a": {"evidence_paths": [str(legacy_json)]},
                        "package_b": {"evidence_paths": [str(observability_json)]},
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            with self.patch_paths(root):
                with patch.object(self.module, "iso_now", return_value="2026-03-15T10:00:00+08:00"):
                    self.module.command_window_heartbeat_write(
                        self.make_write_args(
                            window_id="black-satellite",
                            role="黑色卫星支线",
                            current_phase="AI Phase 2 / surface alignment",
                            current_status="blocked",
                            last_action="旧专项线已停止推进",
                            evidence=[str(evidence_path)],
                            sole_blocker="技术专项已结束",
                        )
                    )
                with patch.object(self.module, "iso_now", return_value="2026-03-15T09:30:00+08:00"):
                    self.module.command_window_heartbeat_write(
                        self.make_write_args(
                            window_id="window-observability-heartbeat",
                            role="普通支线",
                            current_phase="协议落地",
                            current_status="running",
                            last_action="早期观测协议验证",
                            evidence=[str(evidence_path)],
                            sole_blocker="none",
                        )
                    )
                with patch.object(self.module, "iso_now", return_value="2026-03-15T13:30:00+08:00"):
                    self.module.command_window_heartbeat_inspect(self.make_govern_args())
                    self.module.command_window_heartbeat_govern(self.make_govern_args())

            summary_path = root / "artifacts" / "heartbeat" / "windows" / "current" / "summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary_windows = {item["window_id"]: item for item in summary["windows"]}
            self.assertEqual(summary_windows["black-satellite"]["accepted_cleanup_label"], "archived_history_line")
            self.assertEqual(summary_windows["black-satellite"]["display_state"], "archived_history_line")
            self.assertEqual(
                summary_windows["window-observability-heartbeat"]["accepted_cleanup_label"],
                "downgrade_to_history",
            )

            governance_path = root / "artifacts" / "heartbeat" / "windows" / "current" / "governance-summary.json"
            governance = json.loads(governance_path.read_text(encoding="utf-8"))
            governance_windows = {item["window_id"]: item for item in governance["windows"]}
            decisions = {item["window_id"]: item for item in governance["decisions"]}
            self.assertEqual(governance_windows["black-satellite"]["recommended_action"], decisions["black-satellite"]["decision"])
            self.assertEqual(decisions["black-satellite"]["recommended_action"], decisions["black-satellite"]["decision"])
            self.assertEqual(
                decisions["window-observability-heartbeat"]["accepted_cleanup_label"],
                "downgrade_to_history",
            )


if __name__ == "__main__":
    unittest.main()
