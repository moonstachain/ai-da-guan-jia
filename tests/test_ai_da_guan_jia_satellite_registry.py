from __future__ import annotations

import importlib.util
import json
import subprocess
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


class SatelliteRegistryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPT_ROOT))
        cls.module = load_module("test_ai_da_guan_jia_satellite_registry", SCRIPT_PATH)

    def patch_runtime_paths(self, temp_root: Path):
        artifacts_root = temp_root / "artifacts"
        clones_root = artifacts_root / "clones"
        clones_current = clones_root / "current"
        satellites_root = artifacts_root / "satellites"
        satellites_current = satellites_root / "current"
        hub_root = artifacts_root / "hub"
        hub_current = hub_root / "current"
        strategy_root = artifacts_root / "strategy"
        strategy_current = strategy_root / "current"
        return patch.multiple(
            self.module,
            ARTIFACTS_ROOT=artifacts_root,
            CLONES_ROOT=clones_root,
            CLONES_CURRENT_ROOT=clones_current,
            CLONE_REGISTRY_PATH=clones_current / "clone-registry.json",
            ROLE_TEMPLATE_REGISTRY_PATH=clones_current / "role-template-registry.json",
            CLONE_ORG_REGISTRY_PATH=clones_current / "org-registry.json",
            CLONE_TRAINING_STATE_PATH=clones_current / "clone-training-state.json",
            CLONE_SCORECARD_PATH=clones_current / "clone-scorecard.json",
            CLONE_AUTONOMY_TIER_PATH=clones_current / "clone-autonomy-tier.json",
            CLONE_PROMOTION_QUEUE_PATH=clones_current / "promotion-queue.json",
            CLONE_BUDGET_ALLOCATION_PATH=clones_current / "budget-allocation.json",
            CLONE_TASK_RUNS_PATH=clones_current / "task-runs.json",
            CLONE_TRAINING_CYCLES_PATH=clones_current / "training-cycles.json",
            CLONE_CAPABILITY_PROPOSALS_PATH=clones_current / "capability-proposals.json",
            CLONE_ALERTS_DECISIONS_PATH=clones_current / "alerts-decisions.json",
            CLONE_PORTFOLIO_REPORT_PATH=clones_current / "portfolio-daily-report.json",
            CLONE_PORTFOLIO_REPORT_MD_PATH=clones_current / "portfolio-daily-report.md",
            CLONE_FEISHU_SYNC_BUNDLE_PATH=clones_current / "feishu-sync-bundle.json",
            CLONE_SYNC_RESULT_PATH=clones_current / "sync-result.json",
            SATELLITES_ROOT=satellites_root,
            SATELLITES_CURRENT_ROOT=satellites_current,
            SATELLITE_REGISTRY_PATH=satellites_current / "satellite-registry.json",
            SATELLITE_RECLAIM_ROOT=satellites_root / "reclaim-packets",
            SATELLITE_RDAGENT_ROOT=satellites_root / "rd-agent-fin-quant",
            SATELLITE_RDAGENT_CURRENT_ROOT=satellites_root / "rd-agent-fin-quant" / "current",
            SATELLITE_RDAGENT_RUNTIME_BINDINGS_PATH=satellites_root / "rd-agent-fin-quant" / "current" / "runtime-bindings.json",
            SATELLITE_RDAGENT_CONTRACTS_ROOT=satellites_root / "rd-agent-fin-quant" / "contracts",
            SATELLITE_RDAGENT_DEPLOYMENTS_ROOT=satellites_root / "rd-agent-fin-quant" / "deployments",
            HUB_ROOT=hub_root,
            HUB_CURRENT_ROOT=hub_current,
            HUB_OUTBOX_ROOT=hub_root / "outbox",
            HUB_REPOS_ROOT=hub_root / "repos",
            HUB_MVP_CONTRACT_PATH=hub_root / "host-satellite-mvp.json",
            STRATEGY_ROOT=strategy_root,
            STRATEGY_CURRENT_ROOT=strategy_current,
            YUANLI_ACTIVE_CANONICAL_PATH=strategy_current / "yuanli-active-canonical.json",
            REMOTE_HOSTS_ROOT=temp_root / "remote-hosts",
            REMOTE_HOSTS_V2_ROOT=temp_root / "remote-hosts-v2",
        )

    def seed_connected_o(self, temp_root: Path) -> None:
        hub_current = temp_root / "artifacts" / "hub" / "current"
        hub_current.mkdir(parents=True, exist_ok=True)
        (hub_current / "source-status.json").write_text(
            json.dumps(
                {
                    "rows": [
                        {"source_id": "main-hub", "status": "connected", "hostname": "HubMac"},
                        {"source_id": "satellite-03", "status": "connected", "hostname": "OldMac"},
                    ]
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        strategy_current = temp_root / "artifacts" / "strategy" / "current"
        strategy_current.mkdir(parents=True, exist_ok=True)
        (strategy_current / "yuanli-active-canonical.json").write_text(
            json.dumps(
                {
                    "status": "real_task_validation_active",
                    "current_phase": "ready_for_real_task_validation",
                    "active_canonical": {
                        "ai_run_id": "adagj-20260314-yuanli-final-closure-v4",
                        "yuanli_run_id": "yj-20260314-yuanli-final-closure-v4",
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        remote_root = temp_root / "remote-hosts-v2" / "satellite-03"
        remote_root.mkdir(parents=True, exist_ok=True)
        (remote_root / "onboarding-result.json").write_text(
            json.dumps(
                {
                    "source_id": "satellite-03",
                    "host": "192.168.31.83",
                    "user": "liming",
                    "workspace_root": "/Users/liming/Documents/codex-ai-gua-jia-01",
                    "final_status": "completed",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def seed_historical_black_profile(self, temp_root: Path, *, platform: str = "darwin", arch: str = "arm64") -> None:
        profile_root = temp_root / "artifacts" / "hub" / "outbox" / "sources" / "satellite-02" / "latest"
        profile_root.mkdir(parents=True, exist_ok=True)
        (profile_root / "machine-profile.json").write_text(
            json.dumps(
                {
                    "source_id": "satellite-02",
                    "hostname": "BlackMac.local",
                    "user": "liming",
                    "platform": platform,
                    "arch": arch,
                    "python": "3.12.4",
                    "generated_at": "2026-03-14T16:54:44+08:00",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def seed_connected_black(self, temp_root: Path, *, os_name: str = "Darwin", arch: str = "arm64", docker_present: bool = False) -> None:
        hub_current = temp_root / "artifacts" / "hub" / "current"
        payload = json.loads((hub_current / "source-status.json").read_text(encoding="utf-8"))
        rows = payload["rows"] + [{"source_id": "satellite-02", "status": "connected", "hostname": "BlackMac.local"}]
        payload["rows"] = rows
        (hub_current / "source-status.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        remote_root = temp_root / "remote-hosts-v2" / "satellite-02"
        remote_root.mkdir(parents=True, exist_ok=True)
        (remote_root / "onboarding-result.json").write_text(
            json.dumps(
                {
                    "source_id": "satellite-02",
                    "host": "black.local",
                    "user": "liming",
                    "workspace_root": "/Users/liming/Documents/codex-ai-gua-jia-01",
                    "final_status": "completed",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (remote_root / "probe.json").write_text(
            json.dumps(
                {
                    "status": "ready",
                    "source_id": "satellite-02",
                    "client_mode": "vscode-agent",
                    "host_reachable": True,
                    "ssh_reachable": True,
                    "os_name": os_name,
                    "arch": arch,
                    "docker_present": docker_present,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def register_default_fleet(self) -> None:
        with patch.object(self.module, "current_shared_core_version", return_value="test-core"):
            with patch.object(self.module, "resolve_github_ops_repo", return_value="moonstachain/ai-task-ops"):
                with patch.object(self.module, "detect_github_backend", return_value={"backend": "", "reason": "missing auth"}):
                    with patch.object(
                        self.module.subprocess,
                        "run",
                        return_value=subprocess.CompletedProcess(args=["git"], returncode=1, stdout="", stderr="offline"),
                    ):
                        self.module.register_default_satellite_fleet()

    def test_register_satellite_bootstraps_default_fleet_and_linked_clones(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_runtime_paths(root):
                self.seed_connected_o(root)
                parser = self.module.build_parser()
                args = parser.parse_args(["register-satellite"])
                with patch.object(self.module, "current_shared_core_version", return_value="test-core"):
                    with patch.object(self.module, "resolve_github_ops_repo", return_value="moonstachain/ai-task-ops"):
                        with patch.object(self.module, "detect_github_backend", return_value={"backend": "", "reason": "missing auth"}):
                            with patch.object(
                                self.module.subprocess,
                                "run",
                                return_value=subprocess.CompletedProcess(args=["git"], returncode=1, stdout="", stderr="offline"),
                            ):
                                returncode = args.func(args)

                satellite_rows = json.loads(self.module.SATELLITE_REGISTRY_PATH.read_text(encoding="utf-8"))
                clone_rows = json.loads(self.module.CLONE_REGISTRY_PATH.read_text(encoding="utf-8"))
                source_topology = json.loads((self.module.HUB_ROOT / "source-topology.json").read_text(encoding="utf-8"))

        self.assertEqual(returncode, 0)
        self.assertEqual([row["satellite_id"] for row in satellite_rows], ["satellite-black", "satellite-o", "satellite-white"])
        satellite_map = {row["satellite_id"]: row for row in satellite_rows}
        self.assertEqual(satellite_map["satellite-o"]["source_id"], "satellite-03")
        self.assertEqual(satellite_map["satellite-o"]["status"], "connected")
        self.assertTrue(satellite_map["satellite-o"]["default_when_unspecified"])
        self.assertEqual(satellite_map["satellite-o"]["role_kind"], "legacy_execution_satellite")
        self.assertEqual(satellite_map["satellite-white"]["status"], "pending_onboarding")
        self.assertEqual(satellite_map["satellite-white"]["role_kind"], "deputy_control_plane")
        self.assertEqual(satellite_map["satellite-white"]["authority_mode"], "proposal_and_reclaim_only")
        self.assertEqual(satellite_map["satellite-white"]["management_scope"], ["satellite-02", "satellite-03"])
        self.assertEqual(satellite_map["satellite-black"]["status"], "pending_onboarding")
        self.assertEqual(satellite_map["satellite-black"]["role_kind"], "governance_support_satellite")
        self.assertEqual(len(clone_rows), 3)
        self.assertTrue(all(row["customer_id"] == "self-fleet" for row in clone_rows))
        self.assertTrue(all(row["clone_mode"] == "lab" for row in clone_rows))
        self.assertEqual(source_topology["expected_sources"], ["main-hub", "satellite-03"])
        self.assertEqual(
            source_topology["pending_satellite_aliases"],
            ["大管家卫星白色", "大管家卫星黑色"],
        )

    def test_resolve_satellite_supports_named_aliases_and_default_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_runtime_paths(root):
                self.seed_connected_o(root)
                with patch.object(self.module, "current_shared_core_version", return_value="test-core"):
                    with patch.object(self.module, "resolve_github_ops_repo", return_value="moonstachain/ai-task-ops"):
                        with patch.object(self.module, "detect_github_backend", return_value={"backend": "", "reason": "missing auth"}):
                            with patch.object(
                                self.module.subprocess,
                                "run",
                                return_value=subprocess.CompletedProcess(args=["git"], returncode=1, stdout="", stderr="offline"),
                            ):
                                self.module.register_default_satellite_fleet()
                default_target = self.module.resolve_satellite_assignment("")
                o_target = self.module.resolve_satellite_assignment("大管家卫星O")
                white_target = self.module.resolve_satellite_assignment("白色")
                black_target = self.module.resolve_satellite_assignment("black")

        self.assertEqual(default_target["resolved_satellite_id"], "satellite-o")
        self.assertTrue(default_target["is_default_fallback"])
        self.assertEqual(o_target["resolved_source_id"], "satellite-03")
        self.assertEqual(white_target["resolved_source_id"], "satellite-01")
        self.assertEqual(white_target["status"], "pending_onboarding")
        self.assertEqual(black_target["resolved_source_id"], "satellite-02")
        self.assertFalse(black_target["is_default_fallback"])

    def test_resolve_expected_sources_only_promotes_satellites_with_onboarding_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_runtime_paths(root):
                self.seed_connected_o(root)
                white_remote = root / "remote-hosts-v2" / "satellite-01"
                white_remote.mkdir(parents=True, exist_ok=True)
                (white_remote / "onboarding-result.json").write_text(
                    json.dumps(
                        {
                            "source_id": "satellite-01",
                            "host": "192.168.31.90",
                            "user": "liming",
                            "workspace_root": "/Users/liming/Documents/codex-ai-gua-jia-01",
                            "final_status": "completed",
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                with patch.object(self.module, "current_shared_core_version", return_value="test-core"):
                    with patch.object(self.module, "resolve_github_ops_repo", return_value="moonstachain/ai-task-ops"):
                        with patch.object(self.module, "detect_github_backend", return_value={"backend": "", "reason": "missing auth"}):
                            with patch.object(
                                self.module.subprocess,
                                "run",
                                return_value=subprocess.CompletedProcess(args=["git"], returncode=1, stdout="", stderr="offline"),
                            ):
                                self.module.register_default_satellite_fleet()
                expected_sources = self.module.resolve_expected_sources()
                source_status = self.module.build_source_status(
                    {
                        "main-hub": {"machine_profile": {"hostname": "HubMac"}},
                        "satellite-03": {"machine_profile": {"hostname": "OldMac"}},
                    }
                )

        self.assertEqual(expected_sources, ["main-hub", "satellite-03", "satellite-01"])
        self.assertEqual(source_status["expected_sources"], ["main-hub", "satellite-03", "satellite-01"])
        self.assertEqual(source_status["missing_sources"], ["satellite-01"])

    def test_build_host_satellite_contract_uses_new_three_satellite_dispatch_model(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_runtime_paths(root):
                self.seed_connected_o(root)
                with patch.object(self.module, "current_shared_core_version", return_value="test-core"):
                    with patch.object(self.module, "resolve_github_ops_repo", return_value="moonstachain/ai-task-ops"):
                        with patch.object(self.module, "detect_github_backend", return_value={"backend": "", "reason": "missing auth"}):
                            with patch.object(
                                self.module.subprocess,
                                "run",
                                return_value=subprocess.CompletedProcess(args=["git"], returncode=1, stdout="", stderr="offline"),
                            ):
                                self.module.register_default_satellite_fleet()
                contract = self.module.build_host_satellite_mvp_contract("moonstachain/ai-task-ops", ["main-hub", "satellite-03"])

        self.assertEqual(contract["contract_id"], "one-hub-three-satellite-dispatch-v1")
        self.assertEqual(contract["machine_aliases"]["o"], "satellite-03")
        self.assertEqual(contract["dispatch_contract"]["default_when_unspecified"], "satellite-o")
        self.assertEqual(contract["dispatch_contract"]["deputy_control_plane"], "satellite-01")
        self.assertIn("docs/black-white-old-host-satellite-mvp-v1.md", contract["canonical_topology"]["historical_snapshot_refs"])
        self.assertEqual(
            contract["canonical_topology"]["pending_satellite_aliases"],
            ["大管家卫星白色", "大管家卫星黑色"],
        )

    def test_export_satellite_protocol_bundle_writes_registry_and_reclaim_template(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_runtime_paths(root):
                self.seed_connected_o(root)
                self.register_default_fleet()
                output_dir = root / "exports"

                payload = self.module.export_satellite_protocol_bundle(output_dir, requested_alias="大管家卫星O")

                registry_payload = json.loads((output_dir / "satellite-registry-protocol.json").read_text(encoding="utf-8"))
                reclaim_payload = json.loads((output_dir / "satellite-reclaim-packet.template.json").read_text(encoding="utf-8"))

        self.assertEqual(Path(payload["registry_json_path"]).name, "satellite-registry-protocol.json")
        self.assertEqual(registry_payload["bundle_id"], "satellite-registry-protocol-v1")
        self.assertEqual(registry_payload["default_dispatch"]["satellite_id"], "satellite-o")
        white_row = next(row for row in registry_payload["satellites"] if row["satellite_id"] == "satellite-white")
        self.assertEqual(white_row["role_kind"], "deputy_control_plane")
        self.assertEqual(white_row["authority_mode"], "proposal_and_reclaim_only")
        self.assertEqual(registry_payload["active_canonical"]["current_phase"], "ready_for_real_task_validation")
        self.assertEqual(reclaim_payload["requested_alias"], "大管家卫星O")
        self.assertEqual(reclaim_payload["resolved_satellite_id"], "satellite-o")
        self.assertEqual(reclaim_payload["next_main_hub_action"], "not_yet_collected")

    def test_prepare_satellite_reclaim_writes_formal_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_runtime_paths(root):
                self.seed_connected_o(root)
                self.register_default_fleet()
                output_dir = root / "reclaim"
                parser = self.module.build_parser()
                args = parser.parse_args(
                    [
                        "prepare-satellite-reclaim",
                        "--alias",
                        "O",
                        "--task",
                        "在卫星侧完成一轮浏览器执行并把证据交回主机",
                        "--leverage-point",
                        "先让卫星承担浏览器与登录复用，再由主机正式收口",
                        "--did-what",
                        "完成浏览器执行、证据采集和本地验证",
                        "--evidence-ref",
                        "/tmp/evidence-1.json",
                        "--remaining-gap",
                        "主机仍需 aggregate 与 close-task",
                        "--mainline-decision",
                        "promote_main_line_candidate",
                        "--next-main-hub-action",
                        "把卫星证据并入主机 canonical run 并正式 close-task",
                        "--output-dir",
                        str(output_dir),
                    ]
                )

                returncode = args.func(args)
                rows = sorted(output_dir.glob("*.json"))
                self.assertEqual(len(rows), 1)
                packet = json.loads(rows[0].read_text(encoding="utf-8"))

        self.assertEqual(returncode, 0)
        self.assertEqual(packet["resolved_satellite_id"], "satellite-o")
        self.assertEqual(packet["resolved_source_id"], "satellite-03")
        self.assertEqual(packet["mainline_decision"], "promote_main_line_candidate")
        self.assertEqual(packet["completion_state"], "completed")
        self.assertEqual(packet["active_canonical"]["ai_run_id"], "adagj-20260314-yuanli-final-closure-v4")
        self.assertIn("aggregate", packet["proof_boundaries"]["main_hub_scope"])

    def test_inspect_rdagent_fin_quant_prefers_reclaim_before_runtime_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_runtime_paths(root):
                self.seed_connected_o(root)
                self.seed_historical_black_profile(root, platform="darwin", arch="arm64")
                self.register_default_fleet()

                contract = self.module.build_rdagent_fin_quant_control_plane_contract("黑色")

        self.assertEqual(contract["control_plane"]["resolved_source_id"], "satellite-02")
        self.assertFalse(contract["runtime_classification"]["qualifies_direct_runtime"])
        self.assertEqual(contract["runtime_classification"]["os_name"], "darwin")
        self.assertEqual(contract["next_action"]["action_id"], "reclaim_black_satellite")
        self.assertEqual(contract["next_action"]["status"], "blocked_needs_user")

    def test_bind_rdagent_runtime_persists_black_runtime_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_runtime_paths(root):
                self.seed_connected_o(root)
                self.seed_connected_black(root, os_name="Darwin", arch="arm64", docker_present=False)
                self.register_default_fleet()
                parser = self.module.build_parser()
                args = parser.parse_args(
                    [
                        "bind-rdagent-runtime",
                        "--alias",
                        "黑色",
                        "--runtime-host",
                        "10.0.0.8",
                        "--runtime-user",
                        "ubuntu",
                    ]
                )

                returncode = args.func(args)
                rows = json.loads(self.module.SATELLITE_RDAGENT_RUNTIME_BINDINGS_PATH.read_text(encoding="utf-8"))
                contract = self.module.build_rdagent_fin_quant_control_plane_contract("黑色")

        self.assertEqual(returncode, 0)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["control_plane_source_id"], "satellite-02")
        self.assertEqual(rows[0]["runtime_host"], "10.0.0.8")
        self.assertEqual(contract["runtime_binding"]["runtime_host"], "10.0.0.8")
        self.assertEqual(contract["next_action"]["action_id"], "deploy_via_bound_runtime")
        self.assertEqual(contract["next_action"]["status"], "ready")

    def test_deploy_rdagent_fin_quant_uses_bound_runtime_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.patch_runtime_paths(root):
                self.seed_connected_o(root)
                self.seed_connected_black(root, os_name="Darwin", arch="arm64", docker_present=False)
                self.register_default_fleet()
                binding = self.module.build_satellite_rdagent_runtime_binding(
                    requested_alias="黑色",
                    runtime_host="10.0.0.8",
                    runtime_user="ubuntu",
                    runtime_port=22,
                    runtime_workspace_root="$HOME/rd-agent-fin-quant-poc",
                    runtime_conda_home="$HOME/miniforge3",
                    runtime_env_name="rdagent",
                    runtime_data_root="$HOME/.qlib/qlib_data/cn_data",
                    os_name="linux",
                    arch="x86_64",
                )
                self.module.ensure_satellite_rdagent_current_files()
                self.module.write_json(self.module.SATELLITE_RDAGENT_RUNTIME_BINDINGS_PATH, [binding])
                parser = self.module.build_parser()
                args = parser.parse_args(
                    [
                        "deploy-rdagent-fin-quant",
                        "--alias",
                        "黑色",
                        "--skip-verify",
                    ]
                )
                with patch.object(
                    self.module,
                    "run_shell_command_capture",
                    return_value={"command": [], "returncode": 0, "stdout": "ok", "stderr": "", "timed_out": False},
                ) as run_shell:
                    returncode = args.func(args)

        self.assertEqual(returncode, 0)
        self.assertEqual(run_shell.call_count, 1)
        invoked_command = run_shell.call_args.args[0]
        self.assertEqual(invoked_command[0], str(self.module.RDAGENT_FIN_QUANT_DEPLOY_SCRIPT))
        self.assertIn("10.0.0.8", invoked_command)


if __name__ == "__main__":
    unittest.main()
