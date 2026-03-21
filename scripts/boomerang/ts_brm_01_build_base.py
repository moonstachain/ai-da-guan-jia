from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.feishu_deploy import FeishuBitableAPI
from scripts.create_kangbo_signal_tables import DEFAULT_ACCOUNT_ID, load_feishu_credentials

from scripts.boomerang.boomerang_schema import INFERENCE_NOTES, TABLE_SPECS
from scripts.boomerang.boomerang_sync import task_tracker_rows_for_brm, write_task_tracker

ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "boomerang"


FIELD_TYPE_MAP: dict[str, int] = {
    "text": 1,
    "number": 2,
    "single_select": 3,
    "multi_select": 4,
    "datetime": 5,
    "checkbox": 7,
    "user": 11,
    "phone": 13,
    "url": 15,
    "formula": 17,
    "multiline_text": 18,
    "auto_number": 20,
    "progress": 22,
}


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_api(account_id: str) -> FeishuBitableAPI:
    creds = load_feishu_credentials(account_id)
    os.environ["FEISHU_APP_ID"] = creds["app_id"]
    os.environ["FEISHU_APP_SECRET"] = creds["app_secret"]
    return FeishuBitableAPI(creds["app_id"], creds["app_secret"])


def api_request(api: FeishuBitableAPI, path: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return api._request(path, method=method, payload=payload)


def resolve_wiki_node(api: FeishuBitableAPI, wiki_token: str) -> dict[str, Any]:
    payload = api_request(api, f"/open-apis/wiki/v2/spaces/get_node?token={wiki_token}")
    node = (payload.get("data") or {}).get("node") or {}
    return {
        "obj_type": str(node.get("obj_type") or "").strip(),
        "obj_token": str(node.get("obj_token") or "").strip(),
        "space_id": str(node.get("space_id") or "").strip(),
        "node_token": str(node.get("node_token") or "").strip(),
        "parent_node_token": str(node.get("parent_node_token") or "").strip(),
        "title": str(node.get("title") or "").strip(),
    }


def create_base(
    api: FeishuBitableAPI,
    *,
    base_name: str,
    folder_token: str,
) -> str:
    payload = api_request(
        api,
        "/open-apis/bitable/v1/apps",
        method="POST",
        payload={"name": base_name, "folder_token": folder_token},
    )
    data = payload.get("data") or {}
    app = data.get("app") or data
    app_token = str(app.get("app_token") or "").strip()
    if not app_token:
        raise RuntimeError(f"Failed to create base {base_name}: {json.dumps(payload, ensure_ascii=False)}")
    return app_token


def resolve_app_token(
    api: FeishuBitableAPI,
    *,
    wiki_token: str,
    base_name: str,
    apply: bool,
    folder_token_override: str | None = None,
    app_token_override: str | None = None,
) -> tuple[str, dict[str, Any]]:
    if app_token_override:
        return app_token_override, {"resolved_from": "override"}

    node = resolve_wiki_node(api, wiki_token)
    obj_type = node.get("obj_type")
    obj_token = node.get("obj_token")
    if obj_type == "bitable" and obj_token:
        return obj_token, {"resolved_from": "wiki_node", "node": node}

    if not apply:
        return f"dryrun::{base_name}", {"resolved_from": "dry_run", "node": node}

    folder_token = folder_token_override or node.get("node_token") or wiki_token
    app_token = create_base(api, base_name=base_name, folder_token=str(folder_token))
    return app_token, {"resolved_from": "created_base", "node": node, "folder_token": folder_token}


def feishu_field_payload(field: dict[str, Any]) -> dict[str, Any]:
    field_type = str(field.get("type") or "").strip().lower()
    if field_type not in FIELD_TYPE_MAP:
        raise ValueError(f"Unsupported field type: {field_type}")
    payload: dict[str, Any] = {"field_name": str(field["name"]), "type": FIELD_TYPE_MAP[field_type]}
    property_payload: dict[str, Any] = {}
    if field_type in {"single_select", "multi_select"}:
        options = [{"name": str(option)} for option in field.get("options", []) if str(option).strip()]
        property_payload["options"] = options
    if field_type == "number":
        formatter = (field.get("property") or {}).get("formatter")
        if formatter:
            property_payload["formatter"] = formatter
    if field_type == "datetime":
        formatter = (field.get("property") or {}).get("date_formatter")
        if formatter:
            property_payload["date_formatter"] = formatter
        if "auto_fill" in (field.get("property") or {}):
            property_payload["auto_fill"] = bool((field.get("property") or {}).get("auto_fill"))
    if field_type == "formula":
        expression = (field.get("property") or {}).get("formula_expression")
        if expression:
            property_payload["formula_expression"] = expression
    if property_payload:
        payload["property"] = property_payload
    return payload


def list_tables(api: FeishuBitableAPI, app_token: str) -> dict[str, dict[str, Any]]:
    tables = api.list_tables(app_token)
    return {str(item.get("name") or "").strip(): item for item in tables}


def list_fields(api: FeishuBitableAPI, app_token: str, table_id: str) -> dict[str, dict[str, Any]]:
    fields = api.list_fields(app_token, table_id)
    return {str(item.get("field_name") or "").strip(): item for item in fields}


def rename_primary_field(
    api: FeishuBitableAPI,
    app_token: str,
    table_id: str,
    desired_name: str,
    *,
    apply: bool,
    log_lines: list[str],
) -> None:
    fields = api.list_fields(app_token, table_id)
    primary = next((field for field in fields if field.get("is_primary")), None)
    if not primary:
        return
    current_name = str(primary.get("field_name") or "").strip()
    if current_name == desired_name:
        return
    if not apply:
        log_lines.append(f"- primary rename planned: {table_id} {current_name} -> {desired_name}")
        return
    current_type = int(primary.get("type") or 1)
    payload: dict[str, Any] = {"field_name": desired_name, "type": current_type}
    current_property = primary.get("property") or {}
    if current_type == FIELD_TYPE_MAP["datetime"]:
        date_formatter = str(current_property.get("date_formatter") or "").strip()
        if date_formatter:
            payload["property"] = {
                "date_formatter": date_formatter,
                "auto_fill": bool(current_property.get("auto_fill", False)),
            }
    api_request(
        api,
        f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{primary['field_id']}",
        method="PUT",
        payload=payload,
    )


def update_select_options(
    api: FeishuBitableAPI,
    app_token: str,
    table_id: str,
    field_id: str,
    *,
    field_name: str,
    options: list[str],
    field_type: int,
) -> None:
    payload = {"field_name": field_name, "type": field_type, "property": {"options": [{"name": opt} for opt in options]}}
    try:
        api_request(
            api,
            f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{field_id}",
            method="PUT",
            payload=payload,
        )
    except RuntimeError as exc:
        message = str(exc)
        if "DataNotChange" in message or '"code": 1254606' in message:
            return
        raise


def ensure_table_fields(
    api: FeishuBitableAPI,
    app_token: str,
    table_id: str,
    table_spec: dict[str, Any],
    *,
    apply: bool,
    log_lines: list[str],
) -> dict[str, Any]:
    if not apply:
        return {"created": 0, "skipped": len(table_spec["fields"]), "updated_options": 0}

    rename_primary_field(api, app_token, table_id, str(table_spec["fields"][0]["name"]), apply=apply, log_lines=log_lines)
    existing_fields = list_fields(api, app_token, table_id)
    created = 0
    skipped = 0
    updated_options = 0

    for field in table_spec["fields"]:
        field_name = str(field["name"]).strip()
        existing = existing_fields.get(field_name)
        if existing:
            field_type = int(existing.get("type") or 0)
            if field.get("type") in {"single_select", "multi_select"}:
                existing_options = {str(opt.get("name") or "").strip() for opt in (existing.get("property") or {}).get("options", [])}
                desired_options = [str(opt).strip() for opt in field.get("options", []) if str(opt).strip()]
                missing = [opt for opt in desired_options if opt not in existing_options]
                if missing:
                    update_select_options(
                        api,
                        app_token,
                        table_id,
                        str(existing.get("field_id") or ""),
                        field_name=field_name,
                        options=desired_options,
                        field_type=field_type,
                    )
                    updated_options += 1
            skipped += 1
            continue
        try:
            payload = feishu_field_payload(field)
            api_request(
                api,
                f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
                method="POST",
                payload=payload,
            )
            created += 1
        except Exception as exc:  # pragma: no cover - network dependent
            if field.get("type") in {"formula", "multiline_text"}:
                fallback = {"name": field_name, "type": "text"}
                payload = feishu_field_payload(fallback)
                api_request(
                    api,
                    f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
                    method="POST",
                    payload=payload,
                )
                log_lines.append(f"- fallback: {table_spec['table_name']}::{field_name} -> text ({exc})")
                created += 1
            else:
                raise

    return {"created": created, "skipped": skipped, "updated_options": updated_options}


def main() -> int:
    parser = argparse.ArgumentParser(description="TS-BRM-01: build Boomerang Bitable base and tables")
    parser.add_argument("--wiki-token", default="W9ksww7QuiV969k8Hqtcro1Fn7c")
    parser.add_argument("--base-name", default="回旋镖局_战略驾驶舱")
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    parser.add_argument("--app-token")
    parser.add_argument("--folder-token")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--registry-path", default=str(ARTIFACT_ROOT / "table_registry.json"))
    parser.add_argument("--log-path", default=str(ARTIFACT_ROOT / "runs" / datetime.now().strftime("%Y-%m-%d") / "ts-brm-01-log.md"))
    args = parser.parse_args()

    apply = bool(args.apply) and not bool(args.dry_run)
    ensure_dir(Path(args.registry_path).parent)
    ensure_dir(Path(args.log_path).parent)

    api = load_api(args.account_id)
    app_token, resolve_meta = resolve_app_token(
        api,
        wiki_token=str(args.wiki_token),
        base_name=str(args.base_name),
        apply=apply,
        folder_token_override=args.folder_token,
        app_token_override=args.app_token,
    )

    tables_before = {}
    if apply and not app_token.startswith("dryrun::"):
        tables_before = list_tables(api, app_token)

    log_lines: list[str] = []
    log_lines.append(f"# TS-BRM-01 建表日志")
    log_lines.append(f"- timestamp: {datetime.now().isoformat(timespec='seconds')}")
    log_lines.append(f"- apply: {apply}")
    log_lines.append(f"- app_token: {app_token}")
    log_lines.append(f"- resolve_meta: {json.dumps(resolve_meta, ensure_ascii=False)}")
    log_lines.append("")

    registry_tables: dict[str, Any] = {}

    for spec in TABLE_SPECS:
        table_name = spec["table_name"]
        field_count = len(spec["fields"])
        table_id = ""
        status = "planned"
        created = False

        if apply and not app_token.startswith("dryrun::"):
            existing = tables_before.get(table_name) or list_tables(api, app_token).get(table_name)
            if existing:
                table_id = str(existing.get("table_id") or "").strip()
            else:
                payload = api_request(
                    api,
                    f"/open-apis/bitable/v1/apps/{app_token}/tables",
                    method="POST",
                    payload={"table": {"name": table_name}},
                )
                data = payload.get("data") or {}
                table = data.get("table") or data
                table_id = str(table.get("table_id") or "").strip()
                created = True

        if not table_id:
            table_id = f"dryrun::{spec['table_key']}"

        field_result = ensure_table_fields(api, app_token, table_id, spec, apply=apply, log_lines=log_lines)
        status = "verified" if apply else "planned"
        registry_tables[table_name] = {
            "table_id": table_id,
            "table_key": spec["table_key"],
            "layer": spec.get("layer"),
            "primary_field": spec.get("primary_field"),
            "field_count": field_count,
            "field_created": field_result.get("created"),
            "field_skipped": field_result.get("skipped"),
            "field_option_updates": field_result.get("updated_options"),
            "status": status,
            "created": created,
        }

    registry = {
        "app_token": app_token,
        "base_name": args.base_name,
        "tables": registry_tables,
        "schema_notes": INFERENCE_NOTES,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "created_by": "codex",
        "apply": apply,
    }

    Path(args.registry_path).write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(args.log_path).write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    if apply:
        completion_date_ms = int(datetime.now().timestamp() * 1000)
        tracker_rows = task_tracker_rows_for_brm(
            task_status_by_id={
                "TS-BRM-01": "已完成",
                "TS-BRM-02": "待启动",
                "TS-BRM-03": "待启动",
            },
            completion_date_by_id={
                "TS-BRM-01": completion_date_ms,
                "TS-BRM-02": "",
                "TS-BRM-03": "",
            },
            evidence_ref_by_id={
                "TS-BRM-01": str(Path(args.registry_path)),
                "TS-BRM-02": "",
                "TS-BRM-03": "",
            },
            notes_by_id={
                "TS-BRM-01": f"registry={args.registry_path}; log={args.log_path}",
                "TS-BRM-02": "",
                "TS-BRM-03": "",
            },
        )
        write_task_tracker(api, tracker_rows, apply=True)

    print(json.dumps(registry, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
