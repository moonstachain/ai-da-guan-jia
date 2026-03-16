from __future__ import annotations

from scripts import r12_kangbo_signal_spec as spec


def test_schema_manifest_contains_three_tables() -> None:
    manifest = spec.schema_manifest()

    assert len(manifest["tables"]) == 3


def test_event_signal_table_primary_field_is_event_id() -> None:
    table = spec.table_spec_by_key("event_signals")

    assert table["primary_field"] == "event_id"


def test_historical_mirror_table_primary_field_is_mirror_id() -> None:
    table = spec.table_spec_by_key("historical_mirrors")

    assert table["primary_field"] == "mirror_id"


def test_asset_signal_table_primary_field_is_signal_id() -> None:
    table = spec.table_spec_by_key("asset_signals")

    assert table["primary_field"] == "signal_id"


def test_event_signal_seed_has_one_record() -> None:
    assert len(spec.seed_rows("event_signals")) == 1


def test_historical_mirror_seed_has_three_records() -> None:
    assert len(spec.seed_rows("historical_mirrors")) == 3


def test_asset_signal_seed_has_seven_records() -> None:
    assert len(spec.seed_rows("asset_signals")) == 7


def test_historical_mirror_rows_all_reference_demo_event() -> None:
    rows = spec.seed_rows("historical_mirrors")

    assert {row["source_event_id"] for row in rows} == {"KBS-202602-001"}


def test_asset_signal_rows_all_reference_demo_event() -> None:
    rows = spec.seed_rows("asset_signals")

    assert {row["source_event_id"] for row in rows} == {"KBS-202602-001"}


def test_event_signal_severity_is_five() -> None:
    row = spec.seed_rows("event_signals")[0]

    assert row["severity"] == 5


def test_historical_mirror_similarity_scores_match_spec() -> None:
    rows = spec.seed_rows("historical_mirrors")

    assert [row["similarity_score"] for row in rows] == [9, 8, 7]


def test_asset_signal_directions_cover_expected_set() -> None:
    rows = spec.seed_rows("asset_signals")

    assert {row["direction"] for row in rows} == {"强多", "多", "中性", "强空", "空"}


def test_historical_mirror_kangbo_event_ids_match_spec() -> None:
    rows = spec.seed_rows("historical_mirrors")

    assert [row["kangbo_event_id"] for row in rows] == ["KBE-055", "KBE-033", "KBE-053"]


def test_source_url_field_uses_url_type() -> None:
    table = spec.table_spec_by_key("event_signals")
    field = next(item for item in table["fields"] if item["name"] == "source_url")

    assert field["type"] == spec.URL_FIELD


def test_date_fields_use_date_type() -> None:
    event_table = spec.table_spec_by_key("event_signals")
    asset_table = spec.table_spec_by_key("asset_signals")

    event_date = next(item for item in event_table["fields"] if item["name"] == "event_date")
    valid_until = next(item for item in asset_table["fields"] if item["name"] == "valid_until")

    assert event_date["type"] == spec.DATE_FIELD
    assert valid_until["type"] == spec.DATE_FIELD
