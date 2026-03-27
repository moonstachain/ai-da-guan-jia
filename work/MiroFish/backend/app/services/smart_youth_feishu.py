from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from .strategic_tasks_feishu import FeishuBitableAPI, StrategicTaskFeishuError, load_feishu_credentials


REPO_ROOT = Path(__file__).resolve().parents[5]
BACKEND_ROOT = Path(__file__).resolve().parents[2]
CAPABILITY_DIR = BACKEND_ROOT / "capabilities"
REGISTRY_PATH = REPO_ROOT / "artifacts" / "smart-youth" / "smart-youth-table-registry.json"
SHANGHAI_TZ = timezone(timedelta(hours=8))

FIELD_TYPE_NAMES: dict[int, str] = {
    1: "text",
    2: "number",
    3: "single_select",
    4: "multi_select",
    5: "datetime",
    7: "checkbox",
    15: "url",
}


class SmartYouthFeishuError(RuntimeError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SmartYouthFeishuError(f"missing smart-youth artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_registry() -> dict[str, Any]:
    return _load_json(REGISTRY_PATH)


@lru_cache(maxsize=8)
def load_capability(capability_id: str) -> dict[str, Any]:
    capability_path = CAPABILITY_DIR / f"{capability_id}.json"
    return _load_json(capability_path)


@lru_cache(maxsize=1)
def load_client() -> FeishuBitableAPI:
    creds = load_feishu_credentials()
    return FeishuBitableAPI(creds["app_id"], creds["app_secret"])


def list_capabilities() -> list[dict[str, Any]]:
    registry = load_registry()
    registry_tables = registry.get("tables") or {}
    capabilities: list[dict[str, Any]] = []
    for capability_path in sorted(CAPABILITY_DIR.glob("smart_youth_*.json")):
        capability = json.loads(capability_path.read_text(encoding="utf-8"))
        table_key = str(capability.get("tableKey") or "").strip()
        table_name = str(capability.get("tableName") or "").strip()
        registry_entry = registry_tables.get(table_name) or {}
        capabilities.append(
            {
                "id": str(capability.get("id") or capability_path.stem),
                "name": str(capability.get("name") or ""),
                "description": str(capability.get("description") or ""),
                "table_key": table_key,
                "table_name": table_name,
                "table_id": str(registry_entry.get("table_id") or capability.get("formValue", {}).get("tableID") or ""),
                "field_count": len((capability.get("formValue") or {}).get("fields") or []),
                "search_hint": str((capability.get("actions") or [{}])[0].get("description") or ""),
            }
        )
    return capabilities


def _field_type(field: dict[str, Any]) -> str:
    try:
        type_id = int(field.get("type") or 0)
    except (TypeError, ValueError):
        type_id = 0
    return FIELD_TYPE_NAMES.get(type_id, "text")


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        for key in ("name", "text", "value", "label", "display_text"):
            candidate = value.get(key)
            if candidate is not None and candidate != "":
                return _normalize_text(candidate)
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        parts = [_normalize_text(item) for item in value]
        return "、".join([part for part in parts if part])
    return str(value).strip()


def _normalize_datetime(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, dict):
        for key in ("value", "timestamp", "text", "date"):
            candidate = value.get(key)
            if candidate is not None and candidate != "":
                return _normalize_datetime(candidate)
        return ""
    if isinstance(value, list):
        return _normalize_datetime(value[0]) if value else ""
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if abs(timestamp) < 10**11:
            timestamp *= 1000
        return datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).astimezone(SHANGHAI_TZ).isoformat()
    text = str(value).strip()
    if not text:
        return ""
    if text.isdigit():
        timestamp = int(text)
        if abs(timestamp) < 10**11:
            timestamp *= 1000
        return datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).astimezone(SHANGHAI_TZ).isoformat()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(SHANGHAI_TZ).isoformat()
    except ValueError:
        return text


def _normalize_url(value: Any) -> dict[str, str] | str:
    if value is None or value == "":
        return ""
    if isinstance(value, dict):
        link = _normalize_text(value.get("link") or value.get("url") or value.get("href"))
        text = _normalize_text(value.get("text") or value.get("title") or value.get("name") or link)
        if not link:
            return ""
        return {"link": link, "text": text or link}
    text = _normalize_text(value)
    if not text:
        return ""
    return {"link": text, "text": text}


def _normalize_value(field: dict[str, Any], value: Any) -> Any:
    field_type = _field_type(field)
    if field_type == "datetime":
        return _normalize_datetime(value)
    if field_type == "number":
        if isinstance(value, (int, float)):
            return value
        text = _normalize_text(value).replace(",", "")
        if not text:
            return ""
        try:
            return int(text)
        except ValueError:
            try:
                return float(text)
            except ValueError:
                return text
    if field_type == "single_select":
        text = _normalize_text(value)
        return text
    if field_type == "multi_select":
        if value is None or value == "":
            return []
        if isinstance(value, list):
            tokens = [_normalize_text(item) for item in value if _normalize_text(item)]
            return tokens
        return [_normalize_text(item) for item in _normalize_text(value).split("、") if _normalize_text(item)]
    if field_type == "checkbox":
        if isinstance(value, bool):
            return value
        text = _normalize_text(value).lower()
        if text in {"true", "1", "yes", "y"}:
            return True
        if text in {"false", "0", "no", "n"}:
            return False
        return bool(text)
    if field_type == "url":
        return _normalize_url(value)
    return _normalize_text(value)


def _normalize_record(raw_record: dict[str, Any], field_defs: list[dict[str, Any]]) -> dict[str, Any]:
    fields = raw_record.get("fields") or raw_record
    if not isinstance(fields, dict):
        fields = {}
    normalized: dict[str, Any] = {}
    for field in field_defs:
        field_name = str(field.get("name") or "").strip()
        if not field_name or field_name not in fields:
            continue
        normalized_value = _normalize_value(field, fields[field_name])
        if normalized_value is None or normalized_value == "" or normalized_value == []:
            continue
        normalized[field_name] = normalized_value
    record_id = _normalize_text(raw_record.get("record_id") or raw_record.get("id") or "")
    if record_id:
        normalized["record_id"] = record_id
    return normalized


def _coerce_query_value(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return ""
        if text.isdigit():
            try:
                return int(text)
            except ValueError:
                return text
        try:
            return float(text)
        except ValueError:
            return text
    return value


def _record_matches(record_value: Any, operator: str, expected: Any) -> bool:
    operator = operator.lower().strip()
    if operator in {"contains", "includes"}:
        if isinstance(record_value, list):
            return _normalize_text(expected) in {_normalize_text(item) for item in record_value}
        return _normalize_text(expected) in _normalize_text(record_value)
    if operator in {"in"}:
        values = expected if isinstance(expected, list) else [expected]
        normalized_values = {_normalize_text(item) for item in values}
        if isinstance(record_value, list):
            return bool({_normalize_text(item) for item in record_value} & normalized_values)
        return _normalize_text(record_value) in normalized_values
    if operator in {"gt", "gte", "lt", "lte"}:
        left = record_value
        right = _coerce_query_value(expected)
        if isinstance(left, str) and isinstance(right, str):
            left_value = left
            right_value = right
        else:
            try:
                left_value = float(left) if not isinstance(left, str) else float(left)
                right_value = float(right) if not isinstance(right, str) else float(right)
            except (TypeError, ValueError):
                left_value = _normalize_text(left)
                right_value = _normalize_text(right)
        if operator == "gt":
            return left_value > right_value
        if operator == "gte":
            return left_value >= right_value
        if operator == "lt":
            return left_value < right_value
        return left_value <= right_value
    if operator in {"not_equals", "ne"}:
        return _normalize_text(record_value) != _normalize_text(expected)
    return _normalize_text(record_value) == _normalize_text(expected)


def _apply_filter(records: list[dict[str, Any]], filter_spec: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not filter_spec:
        return records
    filters = filter_spec.get("filters")
    if isinstance(filters, list) and filters:
        logic = str(filter_spec.get("logic") or "all").lower().strip()
        compiled = [f for f in filters if isinstance(f, dict) and f.get("field")]
        if not compiled:
            return records

        def matches(record: dict[str, Any]) -> bool:
            outcomes: list[bool] = []
            for clause in compiled:
                field_name = str(clause.get("field") or "").strip()
                operator = str(clause.get("operator") or "equals").strip()
                expected = clause.get("value")
                outcomes.append(_record_matches(record.get(field_name), operator, expected))
            return any(outcomes) if logic == "any" else all(outcomes)

        return [record for record in records if matches(record)]

    field_name = str(filter_spec.get("field") or "").strip()
    if not field_name:
        return records
    operator = str(filter_spec.get("operator") or "equals").strip()
    expected = filter_spec.get("value")
    return [record for record in records if _record_matches(record.get(field_name), operator, expected)]


def _apply_sort(records: list[dict[str, Any]], sort_spec: Any) -> list[dict[str, Any]]:
    if not sort_spec:
        return records
    if isinstance(sort_spec, dict):
        sort_spec = [sort_spec]
    if not isinstance(sort_spec, list):
        return records

    ordered = list(records)
    for clause in reversed([item for item in sort_spec if isinstance(item, dict) and item.get("field")]):
        field_name = str(clause.get("field") or "").strip()
        order = str(clause.get("order") or "asc").lower().strip()
        reverse = order == "desc"

        def key(record: dict[str, Any]) -> Any:
            value = record.get(field_name)
            if isinstance(value, dict):
                return _normalize_text(value.get("text") or value.get("link") or value)
            if isinstance(value, list):
                return "、".join(_normalize_text(item) for item in value)
            return value

        ordered.sort(key=key, reverse=reverse)
    return ordered


def search_capability_records(capability_id: str, query: dict[str, Any] | None = None) -> dict[str, Any]:
    capability = load_capability(capability_id)
    form_value = capability.get("formValue") or {}
    field_defs = list(form_value.get("fields") or [])
    table_id = str(form_value.get("tableID") or "").strip()
    table_name = str(capability.get("tableName") or "").strip()
    if not table_id:
        raise SmartYouthFeishuError(f"capability {capability_id} is missing tableID")

    try:
        client = load_client()
        registry = load_registry()
        mirror_surface = capability.get("mirrorSurface") or {}
        base_id = str(mirror_surface.get("baseId") or registry.get("app_token") or "").strip()
        records = client.list_records(base_id, table_id)
    except (StrategicTaskFeishuError, Exception) as exc:
        raise SmartYouthFeishuError(str(exc)) from exc

    normalized = [_normalize_record(record, field_defs) for record in records]
    filter_spec = query.get("filter") if query else None
    normalized = _apply_filter(normalized, filter_spec)
    normalized = _apply_sort(normalized, (query or {}).get("sort"))

    limit = (query or {}).get("limit")
    try:
        limit_value = int(limit) if limit is not None and limit != "" else None
    except (TypeError, ValueError):
        limit_value = None
    if limit_value is not None and limit_value >= 0:
        normalized = normalized[:limit_value]

    return {
        "source": "feishu",
        "capability_id": capability_id,
        "capability_name": str(capability.get("name") or capability_id),
        "description": str(capability.get("description") or ""),
        "table_key": str(capability.get("tableKey") or ""),
        "table_name": table_name,
        "table_id": table_id,
        "record_count": len(normalized),
        "records": normalized,
        "query": query or {},
        "fetched_at": datetime.now(tz=SHANGHAI_TZ).isoformat(),
    }


def capabilities_meta() -> dict[str, Any]:
    registry = load_registry()
    capabilities = list_capabilities()
    return {
        "base_id": str(registry.get("app_token") or ""),
        "base_name": str(registry.get("base_name_after") or registry.get("base_name_before") or ""),
        "source_link": str(registry.get("source_link") or ""),
        "capabilities": capabilities,
    }
