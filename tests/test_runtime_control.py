from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from dashboard import runtime_control
from dashboard.runtime_control import RuntimeControlPlane


class FakeFeishuClient:
    def __init__(self, tables: list[dict[str, Any]] | None = None):
        self.available = True
        self.tables = list(tables or [])
        self.fields_by_table: dict[str, list[dict[str, Any]]] = {}
        self.records_by_table: dict[str, list[dict[str, Any]]] = {}
        self.calls: list[tuple[str, str, Any]] = []
        self._table_counter = 1
        self._field_counter = 1
        self._record_counter = 1

    def list_bitable_tables(self, app_token: str) -> dict[str, Any]:
        self.calls.append(("LIST_TABLES", app_token, None))
        return {
            "tables": [
                {"table_id": table["table_id"], "name": table["name"]}
                for table in self.tables
            ]
        }

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        self.calls.append((method, path, body))
        route, _, query = path.partition("?")
        parts = [part for part in route.split("/") if part]
        table_id = parts[5] if len(parts) > 5 else ""

        if method == "POST" and route.endswith("/tables"):
            created_table_id = f"tbl_{self._table_counter}"
            self._table_counter += 1
            self.tables.append({"table_id": created_table_id, "name": body["table"]["name"]})
            self.fields_by_table[created_table_id] = [
                {
                    "field_id": "fld_default",
                    "field_name": "默认列",
                    "is_primary": True,
                    "type": 1,
                }
            ]
            self.records_by_table.setdefault(created_table_id, [])
            return {"code": 0, "data": {"table": {"table_id": created_table_id, "name": body["table"]["name"]}}}

        if method == "GET" and route.endswith("/fields"):
            return {"code": 0, "data": {"items": self.fields_by_table.get(table_id, [])}}

        if method == "POST" and route.endswith("/fields"):
            created_field_id = f"fld_{self._field_counter}"
            self._field_counter += 1
            field = {
                "field_id": created_field_id,
                "field_name": body["field_name"],
                "type": body["type"],
                "is_primary": False,
                "property": body.get("property"),
            }
            self.fields_by_table.setdefault(table_id, []).append(field)
            return {"code": 0, "data": {"field": field}}

        if method == "PUT" and "/fields/" in route:
            field_id = parts[7]
            for field in self.fields_by_table.get(table_id, []):
                if field["field_id"] == field_id:
                    field["field_name"] = body["field_name"]
                    field["type"] = body.get("type", field["type"])
                    return {"code": 0, "data": {"field": field}}
            raise AssertionError(f"unknown field id: {field_id}")

        if method == "GET" and route.endswith("/records"):
            return {
                "code": 0,
                "data": {
                    "items": self.records_by_table.get(table_id, []),
                    "has_more": False,
                    "page_token": "",
                },
            }

        if method == "POST" and route.endswith("/records"):
            record_id = f"rec_{self._record_counter}"
            self._record_counter += 1
            record = {"record_id": record_id, "fields": dict(body["fields"])}
            self.records_by_table.setdefault(table_id, []).append(record)
            return {"code": 0, "data": {"record": record}}

        if method == "PUT" and "/records/" in route:
            record_id = parts[7]
            for record in self.records_by_table.get(table_id, []):
                if record["record_id"] == record_id:
                    record["fields"].update(dict(body["fields"]))
                    return {"code": 0, "data": {"record": record}}
            raise AssertionError(f"unknown record id: {record_id}")

        raise AssertionError(f"unexpected request: {method} {path} query={query}")


def _runtime_table_fields() -> list[dict[str, Any]]:
    specs = list(RuntimeControlPlane.FIELD_SPECS)
    fields = []
    for index, spec in enumerate(specs):
        fields.append(
            {
                "field_id": f"fld_{index + 1}",
                "field_name": spec.name,
                "type": spec.field_type,
                "is_primary": index == 0,
                "property": spec.property,
            }
        )
    return fields


def test_ensure_table_returns_existing_table_id_without_recreating() -> None:
    client = FakeFeishuClient([{"table_id": "tbl_existing", "name": RuntimeControlPlane.TABLE_NAME}])
    client.fields_by_table["tbl_existing"] = _runtime_table_fields()
    control_plane = RuntimeControlPlane(client=client)

    table_id = control_plane.ensure_table()

    assert table_id == "tbl_existing"
    assert not any(method == "POST" and path.endswith("/tables") for method, path, _ in client.calls)


def test_ensure_table_creates_missing_table() -> None:
    client = FakeFeishuClient()
    control_plane = RuntimeControlPlane(client=client)

    table_id = control_plane.ensure_table()

    assert table_id == "tbl_1"
    assert any(method == "POST" and path.endswith("/tables") for method, path, _ in client.calls)
    field_names = {field["field_name"] for field in client.fields_by_table[table_id]}
    expected = {spec.name for spec in RuntimeControlPlane.FIELD_SPECS}
    assert expected.issubset(field_names)


def test_upsert_creates_record_for_empty_table() -> None:
    client = FakeFeishuClient([{"table_id": "tbl_existing", "name": RuntimeControlPlane.TABLE_NAME}])
    client.fields_by_table["tbl_existing"] = _runtime_table_fields()
    control_plane = RuntimeControlPlane(client=client)

    result = control_plane.upsert({"active_round": "R10", "frontstage_focus": "runtime sync"})

    assert result["action"] == "created"
    assert client.records_by_table["tbl_existing"][0]["fields"]["active_round"] == "R10"


def test_upsert_updates_first_existing_record() -> None:
    client = FakeFeishuClient([{"table_id": "tbl_existing", "name": RuntimeControlPlane.TABLE_NAME}])
    client.fields_by_table["tbl_existing"] = _runtime_table_fields()
    client.records_by_table["tbl_existing"] = [
        {"record_id": "rec_1", "fields": {"active_round": "R9", "frontstage_focus": "old"}}
    ]
    control_plane = RuntimeControlPlane(client=client)

    result = control_plane.upsert({"active_round": "R10", "frontstage_focus": "new"})

    assert result["action"] == "updated"
    assert client.records_by_table["tbl_existing"][0]["fields"]["active_round"] == "R10"


def test_upsert_adds_last_refresh_field() -> None:
    client = FakeFeishuClient([{"table_id": "tbl_existing", "name": RuntimeControlPlane.TABLE_NAME}])
    client.fields_by_table["tbl_existing"] = _runtime_table_fields()
    control_plane = RuntimeControlPlane(client=client)

    original = runtime_control._iso_now
    runtime_control._iso_now = lambda: "2026-03-16T18:00:00Z"
    try:
        control_plane.upsert({"active_round": "R10"})
    finally:
        runtime_control._iso_now = original

    assert client.records_by_table["tbl_existing"][0]["fields"]["last_refresh"] == "2026-03-16T18:00:00Z"


def test_get_current_returns_fields_dict() -> None:
    client = FakeFeishuClient([{"table_id": "tbl_existing", "name": RuntimeControlPlane.TABLE_NAME}])
    client.fields_by_table["tbl_existing"] = _runtime_table_fields()
    client.records_by_table["tbl_existing"] = [
        {"record_id": "rec_1", "fields": {"active_round": "R10", "frontstage_focus": "focus"}}
    ]
    control_plane = RuntimeControlPlane(client=client)

    current = control_plane.get_current()

    assert current == {"active_round": "R10", "frontstage_focus": "focus"}


def test_get_current_returns_none_when_empty() -> None:
    client = FakeFeishuClient([{"table_id": "tbl_existing", "name": RuntimeControlPlane.TABLE_NAME}])
    client.fields_by_table["tbl_existing"] = _runtime_table_fields()
    control_plane = RuntimeControlPlane(client=client)

    assert control_plane.get_current() is None


def test_upsert_dry_run_does_not_write_record() -> None:
    client = FakeFeishuClient([{"table_id": "tbl_existing", "name": RuntimeControlPlane.TABLE_NAME}])
    client.fields_by_table["tbl_existing"] = _runtime_table_fields()
    control_plane = RuntimeControlPlane(client=client)

    result = control_plane.upsert({"active_round": "R10"}, dry_run=True)

    assert result["action"] == "created"
    assert client.records_by_table.get("tbl_existing", []) == []


def test_cli_executes_with_mock_runtime_control_plane(monkeypatch, capsys) -> None:
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "update_runtime_control.py"
    spec = importlib.util.spec_from_file_location("update_runtime_control", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)

    class FakeRuntimeControlPlane:
        APP_TOKEN = RuntimeControlPlane.APP_TOKEN
        last_instance: FakeRuntimeControlPlane | None = None

        def __init__(self, app_token: str):
            self.app_token = app_token
            self.ensure_called = False
            self.upsert_payload: dict[str, Any] | None = None
            self.dry_run = False
            FakeRuntimeControlPlane.last_instance = self

        def ensure_table(self) -> str:
            self.ensure_called = True
            return "tbl_runtime"

        def upsert(self, fields: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
            self.upsert_payload = dict(fields)
            self.dry_run = dry_run
            return {"record_id": "rec_1", "action": "updated", "table_id": "tbl_runtime"}

    monkeypatch.setattr(module, "RuntimeControlPlane", FakeRuntimeControlPlane)

    exit_code = module.main(
        [
            "--round",
            "R10",
            "--focus",
            "R10 OpenClaw Skill包 + 妙搭经营驾驶舱",
            "--tests",
            "150",
            "--commits",
            "11",
            "--status",
            "completed",
        ]
    )
    output = capsys.readouterr().out.strip()

    assert exit_code == 0
    assert json.loads(output)["action"] == "updated"
    assert FakeRuntimeControlPlane.last_instance is not None
    assert FakeRuntimeControlPlane.last_instance.ensure_called is True
    assert FakeRuntimeControlPlane.last_instance.upsert_payload == {
        "active_round": "R10",
        "frontstage_focus": "R10 OpenClaw Skill包 + 妙搭经营驾驶舱",
        "runtime_state": "healthy",
        "risk_level": "low",
        "total_tests_passed": 150,
        "total_commits": 11,
        "pending_human_actions": 0,
        "system_blockers": 0,
        "last_evolution_round": "R10",
        "last_evolution_status": "completed",
    }
