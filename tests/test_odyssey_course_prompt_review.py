from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "work" / "ai-da-guan-jia" / "scripts" / "odyssey_course_prompt_review.py"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class OdysseyCoursePromptReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module("test_odyssey_course_prompt_review", SCRIPT_PATH)

    def test_classify_model_type_and_editable_source(self) -> None:
        flowith = {"isFlowith": 1, "flowithId": "wf_1"}
        gpts = {"isGPTs": 1, "gizmoID": "g-123"}
        fixed = {"isFixedModel": 1, "appModel": "gemini-3-pro-preview"}
        normal = {"isFlowith": 0, "isGPTs": 0, "isFixedModel": 0}

        self.assertEqual(self.module.classify_model_type(flowith), "flowith")
        self.assertEqual(self.module.classify_editable_source(flowith), "flowith")
        self.assertEqual(self.module.classify_model_type(gpts), "gpts")
        self.assertEqual(self.module.classify_editable_source(gpts), "external_gpts")
        self.assertEqual(self.module.classify_model_type(fixed), "fixed")
        self.assertEqual(self.module.classify_editable_source(fixed), "local_preset")
        self.assertEqual(self.module.classify_model_type(normal), "normal")
        self.assertEqual(self.module.classify_editable_source(normal), "local_preset")

    def test_extract_prompt_sections_prefers_structured_headings(self) -> None:
        prompt = """
# 角色定位
你是一名原力创业顾问。

# 输入
用户会提供业务规模、角色、当前挑战。

# 任务目标
输出一份周期判断报告。

# 硬性规则
不要编造；证据不足要明确写出。

# 输出格式
1. 周期定位
2. 风险提示

# 语调
专业但不端着。
        """

        sections = self.module.extract_prompt_sections(prompt)
        self.assertIn("原力创业顾问", sections["role"])
        self.assertIn("业务规模", sections["inputs"])
        self.assertIn("周期判断报告", sections["goal"])
        self.assertIn("不要编造", sections["constraints"])
        self.assertIn("证据不足", sections["evidence_rules"])
        self.assertIn("周期定位", sections["output_format"])
        self.assertIn("专业但不端着", sections["tone"])

    def test_build_top_optimizations_attaches_dual_evidence(self) -> None:
        modules = [
            {
                "module": "原力定位与原理学习",
                "concepts": ["原力", "原理"],
                "decision_rules": [],
                "user_scenarios": [],
                "output_patterns": [],
                "coverage_priority": 5,
                "matched_sessions": ["DAY1-AM"],
                "evidence_refs": [{"source": "DAY1-AM", "snippet": "把真正那个领域给抽象出来。"}],
            }
        ]
        app = {
            "id": 1,
            "name": "原力分析",
            "category": "原力 AI",
            "order": 5000,
            "status": 1,
            "editable_source": "local_preset",
            "prompt_length": 120,
            "preset_text": "你是一名顾问。\n输出报告。",
            "prompt_sections": {
                "role": "你是一名顾问。",
                "inputs": "",
                "goal": "输出报告。",
                "constraints": "",
                "evidence_rules": "",
                "output_format": "",
                "tone": "",
                "examples": "",
                "escalation_boundary": "",
            },
            "matched_modules": [{"module": "原力定位与原理学习", "score": 0.6, "matched_terms": ["原力"]}],
            "primary_module": "原力定位与原理学习",
            "scores": {"clarity": 0.4, "executability": 0.4, "course_alignment": 0.7, "overall": 0.5},
        }

        items = self.module.build_top_optimizations([app], modules, top_n=1)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["issue_title"], "补证据边界")
        self.assertEqual(items[0]["course_evidence"]["source"], "DAY1-AM")
        self.assertIn("未检出", items[0]["current_prompt_evidence"]["observed"])


if __name__ == "__main__":
    unittest.main()
