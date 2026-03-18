from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = PROJECT_ROOT / "work" / "ai-da-guan-jia" / "scripts"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class ExternalSkillEvalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPT_ROOT))
        cls.ai_da_guan_jia = load_module("test_ai_da_guan_jia_external_skill_eval", SCRIPT_ROOT / "ai_da_guan_jia.py")

    @staticmethod
    def http_404(url: str, *, body: str = "404") -> dict[str, object]:
        return {"url": url, "status": "http_error", "http_status": 404, "body": body, "sample": body}

    def test_evaluate_external_skill_repo_classifies_wechat_skills_as_portable_reference(self) -> None:
        readme_text = """
        # WeChat Writing Skills

        这是一套帮你写公众号的 Skill，可以直接装到 OpenClaw 里用。

        1. wechat-topic-outline-planner 从粗略的想法推进到大纲阶段。
        2. wechat-draft-writer 大纲确认后，按你的文风 DNA 写初稿。
        3. wechat-title-generator 根据正文生成 8 个标题。
        4. wechat-style-profiler 从你的 3-10 篇历史文章里提炼文风 DNA。

        装好之后，先做一次初始化，准备 3-10 篇历史文章。
        """
        skill_payloads = [
            {
                "name": "wechat-style-profiler",
                "description": "Extract style DNA from 3-10 historical articles.",
                "source_url": "https://raw.githubusercontent.com/gainubi/wechat-skills/main/wechat-style-profiler/SKILL.md",
                "status": "fetched",
            },
            {
                "name": "wechat-draft-writer",
                "description": "Write a draft after the outline is confirmed.",
                "source_url": "https://raw.githubusercontent.com/gainubi/wechat-skills/main/wechat-draft-writer/SKILL.md",
                "status": "fetched",
            },
        ]
        with patch.object(self.ai_da_guan_jia, "fetch_text_source", side_effect=lambda url, **_: self.http_404(url)):
            card = self.ai_da_guan_jia.evaluate_external_skill_repo(
                source_url="https://github.com/gainubi/wechat-skills",
                readme_text=readme_text,
                skill_payloads=skill_payloads,
            )
        self.assertEqual(card["runtime_target"], "openclaw")
        self.assertEqual(card["category"], "portable_reference")
        self.assertEqual(card["can_use_now"], "conditional")
        self.assertEqual(card["best_use_mode"], "benchmark_then_port")
        self.assertEqual(card["key_modules_priority"][:2], ["wechat-style-profiler", "wechat-topic-outline-planner"])
        self.assertIn("runtime_mismatch", card["risk_tags"])
        self.assertIn("private_material_dependency", card["risk_tags"])
        self.assertIn("unverifiable_output", card["risk_tags"])
        self.assertEqual(len(card["evaluation_lenses"]), 5)
        self.assertEqual(card["evaluation_lenses"][0]["title"], "产品化壳层")
        self.assertIn("benchmark_then_port", card["best_use_mode"])

    def test_evaluate_external_skill_repo_builds_five_lens_portable_reference_for_everything_claude_code(self) -> None:
        readme_text = """
        # Everything Claude Code

        Works across Claude Code, Codex, Cursor, and OpenCode.
        Install with /plugin install, ship commands, hooks, rules, and skills,
        and keep quality gates plus continuous learning in the loop.
        """
        package_json = json.dumps(
            {
                "name": "ecc-universal",
                "files": [
                    "agents/",
                    "commands/",
                    "hooks/",
                    "rules/",
                    "skills/",
                    "AGENTS.md",
                    ".claude-plugin/plugin.json",
                ],
                "scripts": {
                    "test": "node tests/run-all.js",
                    "coverage": "c8 node tests/run-all.js",
                },
            },
            ensure_ascii=False,
        )
        hooks_json = json.dumps(
            {
                "hooks": {
                    "PreToolUse": [],
                    "PostToolUse": [],
                    "Stop": [],
                }
            },
            ensure_ascii=False,
        )
        rules_readme = """
        # Rules

        common/ + language-specific rules, installed manually beside the plugin.
        """

        def fake_fetch(url: str, **_: object) -> dict[str, object]:
            if url.endswith("/README.md"):
                return {"url": url, "status": "fetched", "http_status": 200, "body": readme_text, "sample": "Everything Claude Code"}
            if url.endswith("/README.zh-CN.md"):
                return {"url": url, "status": "fetched", "http_status": 200, "body": "# ECC 中文说明", "sample": "ECC 中文说明"}
            if url.endswith("/package.json"):
                return {"url": url, "status": "fetched", "http_status": 200, "body": package_json, "sample": "ecc-universal"}
            if url.endswith("/hooks/hooks.json"):
                return {"url": url, "status": "fetched", "http_status": 200, "body": hooks_json, "sample": "PreToolUse"}
            if url.endswith("/rules/README.md"):
                return {"url": url, "status": "fetched", "http_status": 200, "body": rules_readme, "sample": "Rules"}
            if url.endswith("/rules/example-rules.md"):
                return self.http_404(url)
            return self.http_404(url)

        with patch.object(self.ai_da_guan_jia, "fetch_text_source", side_effect=fake_fetch):
            card = self.ai_da_guan_jia.evaluate_external_skill_repo(
                source_url="https://github.com/affaan-m/everything-claude-code",
                readme_text=readme_text,
            )

        self.assertEqual(card["runtime_target"], "multi_harness")
        self.assertEqual(card["category"], "portable_reference")
        self.assertEqual(card["best_use_mode"], "benchmark_then_port")
        self.assertIn("runtime_mismatch", card["risk_tags"])
        self.assertNotIn("packaging_only_signal", card["risk_tags"])
        self.assertEqual([lens["lens_id"] for lens in card["evaluation_lenses"]], [
            "productization_shell",
            "workflow_decomposition",
            "verification_mechanism",
            "cross_runtime_adaptation",
            "continuous_learning",
        ])
        self.assertIn("package_manifest", card["evaluation_lenses"][0]["direct_borrow"]["evidence_refs"])
        self.assertIn("scripts/references/artifacts", " ".join(card["evaluation_lenses"][0]["direct_borrow"]["local_gap"]))
        self.assertIn("rules_example", card["evidence"]["missing_source_ids"])
        self.assertEqual(card["review_questions"]["runtime_compatible"]["answer"], "conditional")

    def test_command_evaluate_external_skill_writes_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            temp_root = Path(tempdir)
            readme_path = temp_root / "README.md"
            readme_path.write_text(
                """
                # WeChat Writing Skills

                这是一套帮你写公众号的 Skill，可以直接装到 OpenClaw 里用。

                1. wechat-topic-outline-planner
                2. wechat-draft-writer
                3. wechat-title-generator
                4. wechat-style-profiler

                初始化需要 3-10 篇历史文章。
                """,
                encoding="utf-8",
            )
            style_dir = temp_root / "wechat-style-profiler"
            style_dir.mkdir(parents=True, exist_ok=True)
            style_skill_path = style_dir / "SKILL.md"
            style_skill_path.write_text(
                """---
name: wechat-style-profiler
description: "Extract the author's style DNA from prior articles."
---

# wechat-style-profiler
""",
                encoding="utf-8",
            )
            draft_dir = temp_root / "wechat-draft-writer"
            draft_dir.mkdir(parents=True, exist_ok=True)
            draft_skill_path = draft_dir / "SKILL.md"
            draft_skill_path.write_text(
                """---
name: wechat-draft-writer
description: "Write the first draft after the outline is approved."
---

# wechat-draft-writer
""",
                encoding="utf-8",
            )

            output_root = temp_root / "artifacts"
            current_root = output_root / "current"
            args = self.ai_da_guan_jia.argparse.Namespace(
                source_url="https://github.com/gainubi/wechat-skills",
                title="wechat-skills",
                runtime_target="openclaw",
                readme_file=str(readme_path),
                skill_file=[str(style_skill_path), str(draft_skill_path)],
                run_id="adagj-external-skill-test",
            )
            with patch.object(self.ai_da_guan_jia, "EXTERNAL_SKILL_EVAL_ROOT", output_root):
                with patch.object(self.ai_da_guan_jia, "EXTERNAL_SKILL_EVAL_CURRENT_ROOT", current_root):
                    with patch.object(
                        self.ai_da_guan_jia,
                        "fetch_text_source",
                        side_effect=lambda url, **_: self.http_404(url),
                    ):
                        exit_code = self.ai_da_guan_jia.command_evaluate_external_skill(args)

            self.assertEqual(exit_code, 0)
            run_dir = output_root / self.ai_da_guan_jia.now_local().strftime("%Y-%m-%d") / "adagj-external-skill-test"
            self.assertTrue((run_dir / "evaluation-card.json").exists())
            self.assertTrue((run_dir / "evaluation-card.md").exists())
            self.assertTrue((run_dir / "decision-memo.md").exists())
            self.assertTrue((run_dir / "source-evidence.json").exists())
            self.assertTrue((current_root / "latest-evaluation.json").exists())

            card = json.loads((run_dir / "evaluation-card.json").read_text(encoding="utf-8"))
            self.assertEqual(card["category"], "portable_reference")
            self.assertEqual(card["runtime_target"], "openclaw")
            self.assertEqual(card["can_use_now"], "conditional")
            self.assertIn("risk_tags", card)
            markdown = (run_dir / "evaluation-card.md").read_text(encoding="utf-8")
            self.assertIn("外部 Skill 完整评估卡", markdown)
            self.assertIn("benchmark_then_port", markdown)
            self.assertIn("五镜头", markdown)

    def test_fetch_first_available_text_returns_serializable_attempts(self) -> None:
        with patch.object(
            self.ai_da_guan_jia,
            "fetch_text_source",
            side_effect=[
                {"url": "https://example.com/README.md", "status": "http_error", "http_status": 404, "body": "", "sample": "404"},
                {"url": "https://example.com/README.md?alt=1", "status": "fetched", "http_status": 200, "body": "# ok", "sample": "# ok"},
            ],
        ):
            result = self.ai_da_guan_jia.fetch_first_available_text(
                ["https://example.com/README.md", "https://example.com/README.md?alt=1"]
            )

        self.assertEqual(result["status"], "fetched")
        self.assertEqual(len(result["attempts"]), 2)
        self.assertNotIn("attempts", result["attempts"][1])
        json.dumps(result, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
