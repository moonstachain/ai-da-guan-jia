"""Deploy dashboard schemas and seed data to Feishu Bitable."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import parse, request


PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parent
SCHEMA_DIR = PACKAGE_DIR / "schemas"
SEED_DIR = PACKAGE_DIR / "seed"
ARTIFACT_DIR = REPO_ROOT / "artifacts" / "dashboard-feishu-deploy"
FEISHU_OPENAPI_BASE = "https://open.feishu.cn"

FIELD_TYPE_MAP = {
    "text": 1,
    "number": 2,
    "single_select": 3,
    "multi_select": 4,
    "datetime": 5,
    "checkbox": 7,
}

TABLE_FILE_MAP = {
    "总控概览": ("control_overview.json", "control_overview.json"),
    "组件热图": ("component_heatmap.json", "component_heatmap.json"),
    "战略链路": ("strategy_linkage.json", "strategy_linkage.json"),
    "组件责任": ("component_responsibility.json", "component_responsibility.json"),
    "进化轨迹": ("evolution_tracker.json", "evolution_tracker.json"),
}


@dataclass(frozen=True)
class DashboardTable:
    table_name: str
    schema_path: Path
    seed_path: Path
    schema: dict[str, Any]
    records: list[dict[str, Any]]


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_dashboard_tables(
    schema_dir: Path = SCHEMA_DIR,
    seed_dir: Path = SEED_DIR,
) -> list[DashboardTable]:
    tables: list[DashboardTable] = []
    for table_name, (schema_file, seed_file) in TABLE_FILE_MAP.items():
        schema_path = schema_dir / schema_file
        seed_path = seed_dir / seed_file
        schema = _load_json(schema_path)
        records = _load_json(seed_path)
        tables.append(
            DashboardTable(
                table_name=table_name,
                schema_path=schema_path,
                seed_path=seed_path,
                schema=schema,
                records=records,
            )
        )
    return tables


def feishu_field_type(field_type: str) -> int:
    normalized = str(field_type or "").strip().lower()
    if normalized not in FIELD_TYPE_MAP:
        raise ValueError(f"Unsupported field type: {field_type}")
    return FIELD_TYPE_MAP[normalized]


def _select_property(field: dict[str, Any]) -> dict[str, Any] | None:
    field_type = str(field.get("type") or "").strip().lower()
    if field_type not in {"single_select", "multi_select"}:
        return None
    options = field.get("options") or []
    return {"options": [{"name": str(option)} for option in options if str(option).strip()]}


def schema_field_to_feishu_field(field: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "field_name": str(field["name"]),
        "type": feishu_field_type(str(field["type"])),
    }
    property_payload = _select_property(field)
    if property_payload:
        payload["property"] = property_payload
    return payload


def _to_datetime_value(value: Any) -> int | str:
    if value in {"", None}:
        return ""
    if isinstance(value, (int, float)):
        integer = int(value)
        return integer // 1000 if abs(integer) >= 10**12 else integer
    text = str(value).strip()
    if not text:
        return ""
    if text.isdigit():
        integer = int(text)
        return integer // 1000 if abs(integer) >= 10**12 else integer
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return int(parsed.timestamp())
    except ValueError:
        return text


def _to_number_value(value: Any) -> int | float | str:
    if value in {"", None}:
        return ""
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    if not text:
        return ""
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return text


def normalize_record_value(field: dict[str, Any], value: Any) -> Any:
    field_type = str(field.get("type") or "").strip().lower()
    if field_type == "datetime":
        return _to_datetime_value(value)
    if field_type == "number":
        return _to_number_value(value)
    if field_type == "checkbox":
        return bool(value)
    if field_type == "multi_select":
        if value == "" or value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        return [str(value)]
    if value in {None, ""}:
        return ""
    return str(value)


def normalize_record(schema: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    fields_by_name = {field["name"]: field for field in schema.get("fields", [])}
    normalized: dict[str, Any] = {}
    for key, value in record.items():
        field = fields_by_name.get(key)
        if not field:
            continue
        normalized_value = normalize_record_value(field, value)
        if normalized_value == "" or normalized_value == []:
            continue
        normalized[key] = normalized_value
    return normalized


def required_credentials() -> tuple[str, str]:
    app_id = str(os.getenv("FEISHU_APP_ID") or "").strip()
    app_secret = str(os.getenv("FEISHU_APP_SECRET") or "").strip()
    if not app_id or not app_secret:
        raise RuntimeError("Missing FEISHU_APP_ID or FEISHU_APP_SECRET in the environment.")
    return app_id, app_secret


class FeishuBitableAPI:
    def __init__(self, app_id: str, app_secret: str, *, base_url: str = FEISHU_OPENAPI_BASE) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = base_url.rstrip("/")
        self._tenant_access_token: str | None = None

    def _request(self, path: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        body = None
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if path != "/open-apis/auth/v3/tenant_access_token/internal":
            headers["Authorization"] = f"Bearer {self.tenant_access_token()}"
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(url, data=body, headers=headers, method=method)
        with request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
        if data.get("code") not in {0, None}:
            raise RuntimeError(f"Feishu API error for {path}: {json.dumps(data, ensure_ascii=False)}")
        return data

    def tenant_access_token(self) -> str:
        if self._tenant_access_token:
            return self._tenant_access_token
        payload = self._request(
            "/open-apis/auth/v3/tenant_access_token/internal",
            method="POST",
            payload={"app_id": self.app_id, "app_secret": self.app_secret},
        )
        token = str(payload.get("tenant_access_token") or "").strip()
        if not token:
            raise RuntimeError("Failed to obtain tenant_access_token.")
        self._tenant_access_token = token
        return token

    def resolve_app_token(self, link: str) -> str:
        parsed = parse.urlparse(link)
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] == "base":
            return parts[1]
        if len(parts) < 2 or parts[0] != "wiki":
            raise RuntimeError(f"Unsupported Feishu link: {link}")
        wiki_token = parts[1]
        response = self._request(f"/open-apis/wiki/v2/spaces/get_node?token={parse.quote(wiki_token)}")
        node = (response.get("data") or {}).get("node") or {}
        app_token = str(node.get("obj_token") or "").strip()
        if not app_token:
            raise RuntimeError(f"Unable to resolve app_token from wiki link: {link}")
        return app_token

    def list_tables(self, app_token: str) -> list[dict[str, Any]]:
        response = self._request(f"/open-apis/bitable/v1/apps/{app_token}/tables?page_size=500")
        return (response.get("data") or {}).get("items") or []

    def create_table(self, app_token: str, table_name: str, fields: list[dict[str, Any]]) -> dict[str, Any]:
        response = self._request(
            f"/open-apis/bitable/v1/apps/{app_token}/tables",
            method="POST",
            payload={"table": {"name": table_name, "fields": fields}},
        )
        return (response.get("data") or {}).get("table") or (response.get("data") or {})

    def list_fields(self, app_token: str, table_id: str) -> list[dict[str, Any]]:
        response = self._request(f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields?page_size=500")
        return (response.get("data") or {}).get("items") or []

    def list_records(self, app_token: str, table_id: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page_token = ""
        while True:
            path = f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records?page_size=500"
            if page_token:
                path += f"&page_token={parse.quote(page_token)}"
            response = self._request(path)
            data = response.get("data") or {}
            items.extend(data.get("items") or [])
            if not data.get("has_more"):
                return items
            page_token = str(data.get("page_token") or "").strip()
            if not page_token:
                return items

    def batch_create_records(self, app_token: str, table_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        response = self._request(
            f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
            method="POST",
            payload={"records": [{"fields": row} for row in rows]},
        )
        return response.get("data") or {}


class DashboardFeishuDeployer:
    def __init__(self, api: FeishuBitableAPI, *, artifact_dir: Path = ARTIFACT_DIR) -> None:
        self.api = api
        self.artifact_dir = artifact_dir
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

    def deploy(self, link: str, *, apply_changes: bool) -> dict[str, Any]:
        app_token = self.api.resolve_app_token(link)
        tables = load_dashboard_tables()
        existing_tables = {
            str(item.get("name") or item.get("table_name") or ""): item
            for item in self.api.list_tables(app_token)
        }
        results: list[dict[str, Any]] = []
        for table in tables:
            feishu_fields = [schema_field_to_feishu_field(field) for field in table.schema["fields"]]
            existing = existing_tables.get(table.table_name)
            if existing is None:
                if not apply_changes:
                    results.append(
                        {
                            "table_name": table.table_name,
                            "status": "planned_create",
                            "expected_records": len(table.records),
                            "fields": feishu_fields,
                        }
                    )
                    continue
                created = self.api.create_table(app_token, table.table_name, feishu_fields)
                table_id = str(created.get("table_id") or "")
            else:
                table_id = str(existing.get("table_id") or "")

            fields = self.api.list_fields(app_token, table_id)
            field_types = {
                str(field.get("field_name") or field.get("name") or ""): int(field.get("type") or 0)
                for field in fields
            }
            expected_types = {field["field_name"]: field["type"] for field in feishu_fields}
            for field_name, expected_type in expected_types.items():
                actual_type = field_types.get(field_name)
                if actual_type != expected_type:
                    raise RuntimeError(
                        f"Field type mismatch in {table.table_name}.{field_name}: expected {expected_type}, got {actual_type}"
                    )

            existing_records = self.api.list_records(app_token, table_id)
            expected_count = len(table.records)
            action = "noop"
            inserted = 0
            if not apply_changes:
                action = "planned_seed" if not existing_records else "planned_verify_only"
            elif not existing_records:
                rows = [normalize_record(table.schema, row) for row in table.records]
                for start in range(0, len(rows), 500):
                    batch = rows[start : start + 500]
                    if batch:
                        self.api.batch_create_records(app_token, table_id, batch)
                        inserted += len(batch)
                action = "seeded"
            elif len(existing_records) == expected_count:
                action = "already_seeded"
            else:
                raise RuntimeError(
                    f"Table {table.table_name} already has {len(existing_records)} records; expected 0 or {expected_count}."
                )

            verified_records = self.api.list_records(app_token, table_id)
            results.append(
                {
                    "table_name": table.table_name,
                    "table_id": table_id,
                    "status": action,
                    "expected_records": expected_count,
                    "verified_records": len(verified_records),
                    "inserted_records": inserted,
                }
            )

        payload = {
            "link": link,
            "app_token": app_token,
            "mode": "apply" if apply_changes else "dry-run",
            "tables": results,
        }
        artifact_path = self.artifact_dir / f"dashboard-feishu-deploy-{_now_stamp()}.json"
        artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        payload["artifact_path"] = str(artifact_path)
        return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deploy dashboard seed data to Feishu Bitable.")
    parser.add_argument("--link", required=True, help="Feishu wiki/base link for the target bitable.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    app_id, app_secret = required_credentials()
    api = FeishuBitableAPI(app_id, app_secret)
    deployer = DashboardFeishuDeployer(api)
    result = deployer.deploy(args.link, apply_changes=bool(args.apply or not args.dry_run))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
