from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import types
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


def write_skill(root: Path, name: str, description: str) -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                f"name: {name}",
                f"description: {description}",
                "---",
                "",
                f"# {name}",
            ]
        ),
        encoding="utf-8",
    )


class CollaborationClosureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPT_ROOT))
        cls.module = load_module("test_ai_da_guan_jia_collaboration_closure", SCRIPT_PATH)

    def seed_skills(self, root: Path) -> None:
        write_skill(root, "agency-engineering", "全栈工程能力中枢，帮我写后端 API。")
        write_skill(root, "agency-engineering-backend-architect", "旧版后端成员 skill。")
        write_skill(root, "agency-testing", "测试与质量保障。")
        write_skill(root, "ai-da-guan-jia", "治理内核。")

    def make_minimal_evolution(self, run_id: str, created_at: str, task_text: str) -> dict[str, object]:
        return {
            "run_id": run_id,
            "created_at": created_at,
            "task_text": task_text,
            "goal_model": "close the task",
            "autonomy_judgment": "高",
            "global_optimum_judgment": "先本地闭环",
            "reuse_judgment": "复用现有链路",
            "verification_judgment": "需要真实证据",
            "evolution_judgment": "沉淀下一轮",
            "max_distortion": "把局部成功当闭环",
            "skills_considered": ["agency-engineering"],
            "skills_selected": ["agency-engineering"],
            "human_boundary": "登录和授权仍归人类。",
            "verification_result": {
                "status": "completed",
                "evidence": ["Local bundle written."],
                "open_questions": [],
            },
            "effective_patterns": ["Canonical-first closure."],
            "wasted_patterns": [],
            "evolution_candidates": ["Promote the verified pattern."],
            "feishu_sync_status": "payload_only_local",
            "moltbook_sync_status": "not_configured",
            "evolution_judgment_detail": {},
            "evolution_writeback_applied": False,
            "evolution_writeback_commit": "",
            "github_task_key": "",
            "github_issue_url": "",
            "github_project_url": "",
            "github_repo": "moonstachain/ai-da-guan-jia",
            "github_sync_status": "pending_intake",
            "github_classification": {},
            "github_archive_status": "not_archived",
            "github_closure_comment_url": "",
            "governance_signal_status": "missing",
            "credit_influenced_selection": False,
            "proposal_authority_summary": {},
        }

    def test_prepare_routing_candidates_suppresses_legacy_member(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            skills_root = root / "skills"
            self.seed_skills(skills_root)
            with patch.object(self.module, "SKILLS_ROOT", skills_root):
                routing = self.module.prepare_routing_candidates("帮我写后端 API")

        effective = [item["name"] for item in routing["effective_skills"]]
        suppressed = routing["legacy_members_suppressed"]
        self.assertIn("agency-engineering", effective)
        self.assertNotIn("agency-engineering-backend-architect", effective)
        self.assertEqual(suppressed[0]["legacy_skill"], "agency-engineering-backend-architect")
        self.assertEqual(suppressed[0]["super_skill"], "agency-engineering")

    def test_prepare_routing_candidates_keeps_explicit_legacy_member(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            skills_root = root / "skills"
            self.seed_skills(skills_root)
            with patch.object(self.module, "SKILLS_ROOT", skills_root):
                routing = self.module.prepare_routing_candidates("请用 agency-engineering-backend-architect 帮我写 API")

        effective = [item["name"] for item in routing["effective_skills"]]
        self.assertIn("agency-engineering-backend-architect", effective)
        self.assertEqual(routing["legacy_members_suppressed"], [])

    def test_run_feishu_sync_loads_private_env_into_child_process(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run_id = "adagj-20260317-000001"
            created_at = "2026-03-17T10:00:00+08:00"
            run_dir = root / "runs" / "2026-03-17" / run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            bridge_script = root / "bridge.py"
            bridge_script.write_text("print('bridge')\n", encoding="utf-8")
            (root / ".env").write_text(
                "\n".join(
                    [
                        "FEISHU_APP_ID=test-app",
                        "FEISHU_APP_SECRET=test-secret",
                        "AI_DA_GUAN_JIA_FEISHU_LINK=https://example.com/base",
                        f"AI_DA_GUAN_JIA_FEISHU_BRIDGE_SCRIPT={bridge_script}",
                    ]
                ),
                encoding="utf-8",
            )
            evolution = self.make_minimal_evolution(run_id, created_at, "同步飞书")
            (run_dir / "evolution.json").write_text(json.dumps(evolution, ensure_ascii=False), encoding="utf-8")
            captured: dict[str, object] = {}

            def fake_run(command, capture_output, text, check, env):
                captured["command"] = command
                captured["env"] = env
                return types.SimpleNamespace(returncode=0, stdout="ok", stderr="")

            with patch.multiple(
                self.module,
                RUNS_ROOT=root / "runs",
                CODEX_HOME=root,
            ):
                with patch.object(self.module.subprocess, "run", side_effect=fake_run):
                    with patch.dict(os.environ, {}, clear=False):
                        os.environ.pop("FEISHU_APP_ID", None)
                        os.environ.pop("FEISHU_APP_SECRET", None)
                        returncode, status = self.module.run_feishu_sync(
                            run_id,
                            apply=True,
                            link_override=None,
                            primary_field_override=None,
                            bridge_script_override=None,
                            print_status=False,
                        )

        self.assertEqual(returncode, 0)
        self.assertEqual(status, "synced_applied")
        self.assertEqual(captured["env"]["FEISHU_APP_ID"], "test-app")
        self.assertEqual(captured["env"]["FEISHU_APP_SECRET"], "test-secret")

    def test_run_feishu_sync_marks_missing_credentials_as_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run_id = "adagj-20260317-000002"
            created_at = "2026-03-17T10:00:00+08:00"
            run_dir = root / "runs" / "2026-03-17" / run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            bridge_script = root / "bridge.py"
            bridge_script.write_text("print('bridge')\n", encoding="utf-8")
            (root / ".env").write_text(
                "\n".join(
                    [
                        "AI_DA_GUAN_JIA_FEISHU_LINK=https://example.com/base",
                        f"AI_DA_GUAN_JIA_FEISHU_BRIDGE_SCRIPT={bridge_script}",
                    ]
                ),
                encoding="utf-8",
            )
            evolution = self.make_minimal_evolution(run_id, created_at, "同步飞书")
            (run_dir / "evolution.json").write_text(json.dumps(evolution, ensure_ascii=False), encoding="utf-8")
            with patch.multiple(
                self.module,
                RUNS_ROOT=root / "runs",
                CODEX_HOME=root,
            ):
                with patch.dict(os.environ, {}, clear=False):
                    os.environ.pop("FEISHU_APP_ID", None)
                    os.environ.pop("FEISHU_APP_SECRET", None)
                    returncode, status = self.module.run_feishu_sync(
                        run_id,
                        apply=True,
                        link_override=None,
                        primary_field_override=None,
                        bridge_script_override=None,
                        print_status=False,
                    )
                    result = json.loads((run_dir / "feishu-sync-result.json").read_text(encoding="utf-8"))

        self.assertEqual(returncode, 1)
        self.assertEqual(status, "apply_blocked_missing_credentials")
        self.assertEqual(result["status"], "apply_blocked_missing_credentials")
        self.assertIn("FEISHU_APP_ID", result["missing_keys"])
        self.assertIn("FEISHU_APP_SECRET", result["missing_keys"])

    def test_command_close_task_writes_claude_handoff_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            skills_root = root / "skills"
            self.seed_skills(skills_root)
            parser = self.module.build_parser()
            args = parser.parse_args(
                [
                    "close-task",
                    "--task",
                    "帮我写一个后端 API 并完成闭环",
                    "--created-at",
                    "2026-03-17T11:00:00+08:00",
                    "--run-id",
                    "adagj-20260317-000003",
                    "--verification-status",
                    "completed",
                    "--evidence",
                    "API contract saved.",
                    "--open-question",
                    "Need one more production smoke test.",
                ]
            )

            def fake_prepare_github_materials(run_dir, phase):
                return {
                    "github_task": {
                        "classification": {"task_key": "ADAGJ-1"},
                        "skip_github_management": False,
                    }
                }

            def fake_run_feishu(run_id, *, apply, **kwargs):
                status = "synced_applied" if apply else "dry_run_preview_ready"
                result = {"status": status, "mode": "apply" if apply else "dry-run"}
                run_dir = self.module.find_run_dir(run_id)
                (run_dir / "feishu-sync-result.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
                self.module.update_evolution_sync_status(run_dir, status, result)
                return 0, status

            def fake_sync_github(run_id, *, phase, apply, repo_override=None):
                status = "github_closure_synced_applied" if apply else "github_closure_preview_ready"
                run_dir = self.module.find_run_dir(run_id)
                evolution = json.loads((run_dir / "evolution.json").read_text(encoding="utf-8"))
                evolution["github_sync_status"] = status
                evolution["github_issue_url"] = "https://github.com/moonstachain/ai-da-guan-jia/issues/1"
                self.module.refresh_run_documents(run_dir, evolution)
                (run_dir / "github-sync-result.json").write_text(
                    json.dumps({"status": status, "phase": phase}, ensure_ascii=False),
                    encoding="utf-8",
                )
                return 0, status

            def fake_moltbook(run_id, prepare, url_override=None, mode_override=None):
                run_dir = self.module.find_run_dir(run_id)
                evolution = json.loads((run_dir / "evolution.json").read_text(encoding="utf-8"))
                evolution["moltbook_sync_status"] = "ready_for_review"
                self.module.refresh_run_documents(run_dir, evolution)
                return 0, "ready_for_review"

            with patch.multiple(
                self.module,
                RUNS_ROOT=root / "runs",
                CODEX_HOME=root,
                SKILLS_ROOT=skills_root,
            ):
                with patch.object(self.module, "append_daily_soul_log", return_value=None):
                    with patch.object(self.module, "prepare_github_materials", side_effect=fake_prepare_github_materials):
                        with patch.object(self.module, "sync_strategy_axis_from_evolution", return_value={"theme_id": "", "strategy_id": "", "experiment_id": "", "workflow_id": "", "experiment_verdict": "pending_real_round"}):
                            with patch.object(self.module, "run_feishu_sync", side_effect=fake_run_feishu):
                                with patch.object(self.module, "sync_github_run", side_effect=fake_sync_github):
                                    with patch.object(self.module, "run_moltbook_sync", side_effect=fake_moltbook):
                                        with patch.object(self.module, "evaluate_evolution_judgment", return_value={"hit": False}):
                                            returncode = args.func(args)
                run_dir = root / "runs" / "2026-03-17" / "adagj-20260317-000003"
                handoff = json.loads((run_dir / "claude_handoff.json").read_text(encoding="utf-8"))
                worklog = json.loads((run_dir / "worklog.json").read_text(encoding="utf-8"))

        self.assertEqual(returncode, 0)
        self.assertEqual(handoff["run_id"], "adagj-20260317-000003")
        self.assertEqual(handoff["feishu_sync_status"], "synced_applied")
        self.assertEqual(handoff["github_sync_status"], "github_closure_synced_applied")
        self.assertEqual(handoff["github_issue_url"], "https://github.com/moonstachain/ai-da-guan-jia/issues/1")
        self.assertTrue(handoff["recommended_next_action"])
        self.assertTrue(Path(worklog["claude_handoff_json_path"]).name == "claude_handoff.json")


if __name__ == "__main__":
    unittest.main()
