from __future__ import annotations

from scripts import r12_v2_hotspot_analysis as spec


def test_hotspot_field_contract_has_20_fields() -> None:
    assert len(spec.HOTSPOT_FIELD_SPECS) == 20
    assert spec.HOTSPOT_FIELD_SPECS[0]["field_name"] == "analysis_id"
    assert spec.HOTSPOT_FIELD_SPECS[-1]["field_name"] == "investment_implication"


def test_hotspot_seed_record_links_to_existing_event() -> None:
    assert spec.HOTSPOT_RECORD["analysis_id"] == "HDA-202603-001"
    assert spec.HOTSPOT_RECORD["source_event_id"] == "KBS-202602-001"
    assert spec.HOTSPOT_RECORD["adversary_time_preference"] == "对手"
    assert spec.HOTSPOT_RECORD["escalation_probability"] == 75
