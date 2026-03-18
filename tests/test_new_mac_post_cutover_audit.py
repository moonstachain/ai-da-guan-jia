import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path("/Users/liming/Documents/codex-ai-gua-jia-01/scripts/run_new_mac_post_cutover_audit.py")
SPEC = importlib.util.spec_from_file_location("new_mac_post_cutover_audit", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class NewMacPostCutoverAuditTests(unittest.TestCase):
    def test_grade_from_score(self) -> None:
        self.assertEqual(MODULE.grade_from_score(9.2), "A")
        self.assertEqual(MODULE.grade_from_score(8.2), "B+")
        self.assertEqual(MODULE.grade_from_score(5.1), "C")

    def test_classify_transition_for_bool(self) -> None:
        spec = {"kind": "bool"}
        self.assertEqual(MODULE.classify_transition(spec, True, False)[0], "新机缺失")
        self.assertEqual(MODULE.classify_transition(spec, True, True)[0], "已完成迁移")
        self.assertEqual(MODULE.classify_transition(spec, False, True)[0], "已完成迁移")

    def test_classify_transition_for_count(self) -> None:
        spec = {"kind": "count"}
        self.assertEqual(MODULE.classify_transition(spec, 10, 8)[0], "新机降级")
        self.assertEqual(MODULE.classify_transition(spec, 10, 10)[0], "已完成迁移")
        self.assertEqual(MODULE.classify_transition(spec, 10, 0)[0], "新机缺失")

    def test_build_diff_matrix_marks_intentional_rows(self) -> None:
        local = {
            "repos": {"project_root": {"present": True}, "ai_da_guan_jia": {"present": True}, "os_yuanli": {"present": True}, "yuanli_os_ops": {"present": True}, "yuanli_os_skills_pack": {"present": True}},
            "codex": {"skill_count": 120, "automation_count": 10, "required_skills": {"ai-da-guan-jia": True}},
            "credentials": {"github_auth": {"valid": False}, "github_hosts": {"present": True}, "openclaw": {"present": True}},
            "profiles": {"feishu_reader": True, "get_biji": True},
            "workflow": {"content_smoke": True, "audit_sync": True},
            "source_compare": {"expected_live": True, "live_ok": False},
        }
        source = {
            "repos": {"project_root": {"present": True}, "ai_da_guan_jia": {"present": True}, "os_yuanli": {"present": True}, "yuanli_os_ops": {"present": True}, "yuanli_os_skills_pack": {"present": True}},
            "codex": {"skill_count": 110, "automation_count": 10, "required_skills": {"ai-da-guan-jia": True}},
            "credentials": {"github_auth": {"valid": True}, "github_hosts": {"present": True}, "openclaw": {"present": False}},
            "profiles": {"feishu_reader": True, "get_biji": True},
            "workflow": {"content_smoke": True, "audit_sync": True},
            "source_compare": {"expected_live": True, "live_ok": False},
        }
        rows = MODULE.build_diff_matrix(local, source)
        statuses = {row["item_id"]: row["status"] for row in rows}
        self.assertEqual(statuses["gh_auth_valid"], "新机缺失")
        intentional = [row for row in rows if row["status"] == "故意不迁移"]
        self.assertGreaterEqual(len(intentional), 1)


if __name__ == "__main__":
    unittest.main()
