from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class IbmCbmGovernanceM2ContractTest(unittest.TestCase):
    def test_overview_m2_cards_have_stable_card_ids_in_current_base_config(self) -> None:
        config = json.loads(
            (ROOT / "specs/feishu/ibm-cbm-governance-dashboard-current-base-config.json").read_text(
                encoding="utf-8"
            )
        )
        overview_cards = {item["card_id"]: item for item in config["card_specs"]["overview"] if "card_id" in item}

        self.assertEqual(
            {
                "overview-06": "哪些组件在 direct、control、execute 上最失衡？",
                "overview-07": "哪些组件的人类 Owner 或 AI Copilot 仍然缺位？",
                "overview-08": "哪些组件 gap 最大、最值得优先补？",
            },
            {card_id: overview_cards[card_id]["name"] for card_id in ("overview-06", "overview-07", "overview-08")},
        )

    def test_overview_m2_source_views_and_checklist_share_same_card_ids(self) -> None:
        blueprint = json.loads(
            (ROOT / "specs/feishu/ibm-cbm-governance-dashboard-v1-blueprint/dashboard-blueprint.json").read_text(
                encoding="utf-8"
            )
        )
        source_view_by_card = {
            item["card_id"]: item["question"]
            for item in blueprint["source_views"]
            if item.get("card_id") in {"overview-06", "overview-07", "overview-08"}
        }
        checklist_by_card = {
            item["card_id"]: item["card_title"]
            for item in blueprint["card_checklist"]
            if item.get("card_id") in {"overview-06", "overview-07", "overview-08"}
        }

        self.assertEqual(source_view_by_card["overview-06"], "哪些组件在 direct、control、execute 上最失衡？")
        self.assertEqual(source_view_by_card["overview-07"], "哪些组件的人类 Owner 或 AI Copilot 仍然缺位？")
        self.assertEqual(source_view_by_card["overview-08"], "哪些组件 gap 最大、最值得优先补？")
        self.assertEqual(checklist_by_card["overview-06"], source_view_by_card["overview-06"])
        self.assertEqual(checklist_by_card["overview-07"], source_view_by_card["overview-07"])
        self.assertEqual(checklist_by_card["overview-08"], source_view_by_card["overview-08"])

    def test_m3_cards_have_stable_card_ids_and_aligned_filters(self) -> None:
        config = json.loads(
            (ROOT / "specs/feishu/ibm-cbm-governance-dashboard-current-base-config.json").read_text(
                encoding="utf-8"
            )
        )
        blueprint = json.loads(
            (ROOT / "specs/feishu/ibm-cbm-governance-dashboard-v1-blueprint/dashboard-blueprint.json").read_text(
                encoding="utf-8"
            )
        )

        diagnosis_card = next(
            item for item in config["card_specs"]["diagnosis"] if item.get("card_id") == "diagnosis-03"
        )
        action_card = next(
            item for item in config["card_specs"]["action"] if item.get("card_id") == "action-04"
        )
        diagnosis_source_view = next(
            item for item in blueprint["source_views"] if item.get("card_id") == "diagnosis-03"
        )
        action_source_view = next(
            item for item in blueprint["source_views"] if item.get("card_id") == "action-04"
        )

        self.assertEqual(diagnosis_card["name"], "数据源与证据链当前健康吗？")
        self.assertEqual(action_card["name"], "哪些能力价值高，但审批或授权摩擦仍然很大？")
        self.assertEqual(diagnosis_source_view["filters"], ["time grain = day"])
        self.assertEqual(action_source_view["filters"], ["requires_human_approval = 是"])


if __name__ == "__main__":
    unittest.main()
