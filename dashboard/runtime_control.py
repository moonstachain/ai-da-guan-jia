from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from mcp_server_feishu.feishu_client import FeishuClient


TEXT_FIELD = 1
NUMBER_FIELD = 2
SINGLE_SELECT_FIELD = 3


@dataclass(frozen=True)
class FieldSpec:
    name: str
    field_type: int
    property: dict[str, Any] | None = None


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class RuntimeControlPlane:
    """
    Maintain a singleton runtime-control record inside Feishu Bitable.
    """

    APP_TOKEN = "PVDgbdWYFaDLBiss0hlcM5WRnQc"
    TABLE_NAME = "L0_运行态总控"
    PRIMARY_FIELD_NAME = "active_round"
    FIELD_SPECS = (
        FieldSpec("active_round", TEXT_FIELD),
        FieldSpec("frontstage_focus", TEXT_FIELD),
        FieldSpec(
            "runtime_state",
            SINGLE_SELECT_FIELD,
            {
                "options": [
                    {"name": "healthy", "color": 0},
                    {"name": "degraded", "color": 1},
                    {"name": "blocked", "color": 2},
                ]
            },
        ),
        FieldSpec(
            "risk_level",
            SINGLE_SELECT_FIELD,
            {
                "options": [
                    {"name": "low", "color": 0},
                    {"name": "medium", "color": 1},
                    {"name": "high", "color": 2},
                    {"name": "critical", "color": 3},
                ]
            },
        ),
        FieldSpec("total_tests_passed", NUMBER_FIELD),
        FieldSpec("total_commits", NUMBER_FIELD),
        FieldSpec("pending_human_actions", NUMBER_FIELD),
        FieldSpec("system_blockers", NUMBER_FIELD),
        FieldSpec("last_evolution_round", TEXT_FIELD),
        FieldSpec(
            "last_evolution_status",
            SINGLE_SELECT_FIELD,
            {
                "options": [
                    {"name": "completed", "color": 0},
                    {"name": "blocked_needs_user", "color": 1},
                    {"name": "failed_partial", "color": 2},
                ]
            },
        ),
        FieldSpec("last_refresh", TEXT_FIELD),
    )

    def __init__(
        self,
        client: FeishuClient | None = None,
        *,
        app_token: str | None = None,
        table_name: str | None = None,
    ) -> None:
        self.client = client or FeishuClient()
        self.app_token = app_token or self.APP_TOKEN
        self.table_name = table_name or self.TABLE_NAME

    def ensure_table(self) -> str:
        tables_payload = self.client.list_bitable_tables(self.app_token)
        if "error" in tables_payload:
            raise RuntimeError(str(tables_payload["error"]))

        table_id = ""
        for table in tables_payload.get("tables", []):
            if str(table.get("name", "")).strip() == self.table_name:
                table_id = str(table.get("table_id", "")).strip()
                break

        if not table_id:
            table = self._api(
                "POST",
                f"/bitable/v1/apps/{self.app_token}/tables",
                {"table": {"name": self.table_name}},
            )
            data = table.get("data", {}) or {}
            created = data.get("table", data) or {}
            table_id = str(created.get("table_id", "")).strip()
            if not table_id:
                raise RuntimeError("failed to create runtime control table")

        self._ensure_fields(table_id)
        return table_id

    def upsert(self, fields: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
        table_id = self.ensure_table()
        current = self._list_records(table_id)
        payload = dict(fields)
        payload["last_refresh"] = _iso_now()
        action = "updated" if current else "created"
        record_id = self._record_id(current[0]) if current else ""

        if dry_run:
            return {
                "action": action,
                "record_id": record_id,
                "table_id": table_id,
                "fields": payload,
            }

        if current:
            updated = self._api(
                "PUT",
                f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/records/{record_id}",
                {"fields": payload},
            )
            data = updated.get("data", {}) or {}
            record = data.get("record", data) or {}
            record_id = self._record_id(record) or record_id
        else:
            created = self._api(
                "POST",
                f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/records",
                {"fields": payload},
            )
            data = created.get("data", {}) or {}
            record = data.get("record", data) or {}
            record_id = self._record_id(record)

        return {"record_id": record_id, "action": action, "table_id": table_id}

    def get_current(self) -> dict[str, Any] | None:
        table_id = self.ensure_table()
        records = self._list_records(table_id)
        if not records:
            return None
        return dict(records[0].get("fields", {}) or {})

    def _ensure_fields(self, table_id: str) -> None:
        fields = self._list_fields(table_id)
        primary_field = next((field for field in fields if field.get("is_primary")), None)
        if primary_field is None and fields:
            primary_field = fields[0]

        if primary_field is not None:
            current_name = str(primary_field.get("field_name", "")).strip()
            if current_name != self.PRIMARY_FIELD_NAME:
                self._api(
                    "PUT",
                    f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/fields/{primary_field['field_id']}",
                    {"field_name": self.PRIMARY_FIELD_NAME, "type": TEXT_FIELD},
                )
                fields = self._list_fields(table_id)

        field_names = {
            str(field.get("field_name", "")).strip(): field for field in fields if field.get("field_name")
        }
        for spec in self.FIELD_SPECS[1:]:
            if spec.name in field_names:
                continue
            payload: dict[str, Any] = {"field_name": spec.name, "type": spec.field_type}
            if spec.property is not None:
                payload["property"] = spec.property
            self._api(
                "POST",
                f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/fields",
                payload,
            )

    def _list_fields(self, table_id: str) -> list[dict[str, Any]]:
        payload = self._api(
            "GET",
            f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/fields",
            query={"page_size": 500},
        )
        return list((payload.get("data", {}) or {}).get("items", []) or [])

    def _list_records(self, table_id: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        page_token = ""
        while True:
            query = {"page_size": 500}
            if page_token:
                query["page_token"] = page_token
            payload = self._api(
                "GET",
                f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/records",
                query=query,
            )
            data = payload.get("data", {}) or {}
            records.extend(list(data.get("items", []) or []))
            if not data.get("has_more"):
                break
            page_token = str(data.get("page_token", "")).strip()
            if not page_token:
                break
        return records

    def _api(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        query: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        request_path = path
        if query:
            request_path = f"{request_path}?{urlencode(query)}"
        payload = self.client._request(method, request_path, body)
        if "error" in payload:
            raise RuntimeError(str(payload["error"]))
        code = payload.get("code", 0)
        if code not in (0, "0", None):
            message = payload.get("msg") or payload.get("error") or f"feishu api error: {code}"
            raise RuntimeError(str(message))
        return payload

    @staticmethod
    def _record_id(record: dict[str, Any]) -> str:
        return str(record.get("record_id") or record.get("id") or "").strip()
