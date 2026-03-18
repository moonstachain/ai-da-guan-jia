from __future__ import annotations

from scripts import r17_three_super_events as spec


def test_payload_counts_match_task_spec() -> None:
    assert len(spec.EVENT_SIGNAL_RECORDS) == 3
    assert len(spec.HOTSPOT_RECORDS) == 3
    assert len(spec.MIRROR_RECORDS) == 6
    assert len(spec.SIGNAL_RECORDS) == 9


def test_primary_ids_cover_all_three_super_events() -> None:
    event_ids = {row["event_id"] for row in spec.EVENT_SIGNAL_RECORDS}
    analysis_ids = {row["analysis_id"] for row in spec.HOTSPOT_RECORDS}
    mirror_sources = {row["source_event_id"] for row in spec.MIRROR_RECORDS}
    signal_sources = {row["source_event_id"] for row in spec.SIGNAL_RECORDS}

    assert event_ids == {"KBS-202202-001", "KBS-202211-001", "KBS-202501-001"}
    assert analysis_ids == {"HDA-202202-001", "HDA-202211-001", "HDA-202501-001"}
    assert mirror_sources == event_ids
    assert signal_sources == event_ids


def test_required_option_patches_cover_new_single_select_values() -> None:
    assert "秩序崩塌" in spec.EVENT_SIGNAL_OPTION_PATCHES["narrative_type"]
    assert "范式转移" in spec.EVENT_SIGNAL_OPTION_PATCHES["impact_direction"]
    assert "通用技术革命起点" in spec.MIRROR_OPTION_PATCHES["analogy_type"]


def test_l1_backlink_fields_match_hotspot_link_contract() -> None:
    names = [field["field_name"] for field in spec.L1_BACKLINK_FIELDS]
    assert names == ["deep_analysis_id", "escalation_probability", "duration_estimate"]
