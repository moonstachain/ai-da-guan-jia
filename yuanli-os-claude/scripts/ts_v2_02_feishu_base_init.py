#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

CLAUDE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcp_server_feishu.feishu_client import FeishuClient


TEMPLATE_PATH = CLAUDE_ROOT / "CLAUDE-INIT-TEMPLATE.md"
DEFAULT_OUTPUT_DIR = CLAUDE_ROOT / "output" / "ts-v2-02"
PLACEHOLDER_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")

TEXT_FIELD = 1
NUMBER_FIELD = 2
SINGLE_SELECT_FIELD = 3
DATE_FIELD = 5

SKILL_FIELD_NAMES = [
    "skill_id",
    "skill_name",
    "source_repo",
    "file_path",
    "source_type",
    "description",
    "trigger_keywords",
    "dependencies",
    "last_updated",
    "status",
    "category",
    "quadrant",
    "action_recommendation",
]

EVOLUTION_FIELD_SPECS = [
    {"field_name": "milestone_id", "type": TEXT_FIELD, "is_primary": True},
    {
        "field_name": "version",
        "type": SINGLE_SELECT_FIELD,
        "property": {"options": [{"name": "1.0"}, {"name": "2.0"}]},
    },
    {"field_name": "phase", "type": TEXT_FIELD},
    {"field_name": "date", "type": DATE_FIELD, "property": {"date_formatter": "yyyy-MM-dd", "auto_fill": False}},
    {"field_name": "milestone_name", "type": TEXT_FIELD},
    {"field_name": "organ_gained", "type": TEXT_FIELD},
    {"field_name": "capability_before", "type": TEXT_FIELD},
    {"field_name": "capability_after", "type": TEXT_FIELD},
    {"field_name": "machine_description", "type": TEXT_FIELD},
    {"field_name": "human_translation", "type": TEXT_FIELD},
    {"field_name": "what_solved", "type": TEXT_FIELD},
    {"field_name": "what_unsolved", "type": TEXT_FIELD},
    {
        "field_name": "evidence_level",
        "type": SINGLE_SELECT_FIELD,
        "property": {"options": [{"name": "L1"}, {"name": "L2"}, {"name": "L3"}, {"name": "L4"}]},
    },
    {"field_name": "evidence_refs", "type": TEXT_FIELD},
    {"field_name": "commit_hash", "type": TEXT_FIELD},
    {"field_name": "tests_passed", "type": NUMBER_FIELD},
]

MATURITY_FIELD_NAMES = [
    "对象类型",
    "对象名称",
    "证据等级",
    "结构层级",
    "诚实度",
    "成熟度",
    "治理分",
    "档位",
    "路由影响",
    "自治上限",
    "写回信任",
    "Carry-over 动作",
    "最近评估时间",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TS-V2-02: render one INIT instance and prepare/apply the Feishu base init plan.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Render files and write the init plan without calling Feishu APIs.")
    mode.add_argument("--apply", action="store_true", help="Render files and ensure the configured Feishu tables exist.")
    parser.add_argument("--config", required=True, help="Instance config JSON containing template values.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory for rendered files and plan.")
    return parser.parse_args(argv)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def api(
    client: FeishuClient,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    *,
    query: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request_path = path
    if query:
        request_path = f"{path}?{urlencode(query)}"
    payload = client._request(method, request_path, body)
    if payload.get("error"):
        raise RuntimeError(str(payload["error"]))
    code = payload.get("code", 0)
    if code not in (0, "0", None):
        raise RuntimeError(str(payload.get("msg") or payload.get("error") or f"Feishu API error {code}"))
    return payload


def list_tables(client: FeishuClient, app_token: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page_token = ""
    while True:
        query: dict[str, Any] = {"page_size": 200}
        if page_token:
            query["page_token"] = page_token
        payload = api(client, "GET", f"/bitable/v1/apps/{app_token}/tables", query=query)
        data = payload.get("data", {}) or {}
        items.extend(list(data.get("items", []) or []))
        if not data.get("has_more"):
            break
        page_token = str(data.get("page_token") or "").strip()
        if not page_token:
            break
    return items


def list_fields(client: FeishuClient, app_token: str, table_id: str) -> list[dict[str, Any]]:
    payload = api(client, "GET", f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields", query={"page_size": 500})
    return list(((payload.get("data") or {}).get("items") or []))


def table_id_by_name(client: FeishuClient, app_token: str, table_name: str) -> str:
    for table in list_tables(client, app_token):
        if str(table.get("name") or "").strip() == table_name:
            return str(table.get("table_id") or "").strip()
    return ""


def field_name(field: dict[str, Any]) -> str:
    return str(field.get("field_name") or field.get("name") or "").strip()


def sanitize_property(field_type: int, property_value: Any) -> dict[str, Any] | None:
    if not isinstance(property_value, dict) or not property_value:
        return None
    if field_type == SINGLE_SELECT_FIELD:
        options = []
        for option in property_value.get("options", []) or []:
            if not isinstance(option, dict):
                continue
            name = str(option.get("name") or "").strip()
            if not name:
                continue
            cleaned = {"name": name}
            if option.get("color") is not None:
                cleaned["color"] = option["color"]
            options.append(cleaned)
        return {"options": options} if options else None
    return dict(property_value)


def template_placeholders(template_text: str) -> list[str]:
    return sorted(set(PLACEHOLDER_RE.findall(template_text)))


def require_placeholder_values(config: dict[str, Any], template_text: str) -> dict[str, str]:
    values = dict(config.get("placeholders") or {})
    expected = template_placeholders(template_text)
    missing = [name for name in expected if str(values.get(name) or "").strip() == ""]
    if missing:
        raise RuntimeError(f"missing placeholder values: {', '.join(missing)}")
    return {name: str(values[name]) for name in expected}


def render_template(template_text: str, values: dict[str, str]) -> str:
    rendered = template_text
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    return rendered


def ensure_generic_table(
    client: FeishuClient,
    app_token: str,
    table_name: str,
    field_specs: list[dict[str, Any]],
) -> str:
    table_id = table_id_by_name(client, app_token, table_name)
    if not table_id:
        created = api(client, "POST", f"/bitable/v1/apps/{app_token}/tables", {"table": {"name": table_name}})
        table = (created.get("data", {}) or {}).get("table", {}) or {}
        table_id = str(table.get("table_id") or "").strip() or table_id_by_name(client, app_token, table_name)
    if not table_id:
        raise RuntimeError(f"failed to create or resolve table {table_name}")

    current_fields = {field_name(item): item for item in list_fields(client, app_token, table_id)}
    primary_spec = next((item for item in field_specs if item.get("is_primary")), field_specs[0])
    current_primary = next((field for field in current_fields.values() if field.get("is_primary")), None)
    if current_primary is not None and field_name(current_primary) != primary_spec["field_name"]:
        body: dict[str, Any] = {"field_name": primary_spec["field_name"], "type": primary_spec["type"]}
        prop = sanitize_property(primary_spec["type"], primary_spec.get("property"))
        if prop:
            body["property"] = prop
        api(client, "PUT", f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{current_primary['field_id']}", body)
        current_fields = {field_name(item): item for item in list_fields(client, app_token, table_id)}

    for spec in field_specs[1:]:
        name = spec["field_name"]
        if name in current_fields:
            continue
        body = {"field_name": name, "type": spec["type"]}
        prop = sanitize_property(spec["type"], spec.get("property"))
        if prop:
            body["property"] = prop
        api(client, "POST", f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields", body)
    return table_id


def bootstrap_client() -> FeishuClient:
    client = FeishuClient()
    if not client.available:
        raise RuntimeError("FEISHU_APP_ID / FEISHU_APP_SECRET are required for --apply")
    return client


def build_table_specs(config: dict[str, Any]) -> list[dict[str, Any]]:
    values = config["placeholders"]
    names = dict(config.get("table_names") or {})
    return [
        {
            "surface": "live_control",
            "app_token_key": "FEISHU_APP_TOKEN_LIVE",
            "table_id_key": "FEISHU_TABLE_ID_LIVE_CONTROL",
            "table_name": str(names.get("live_control") or "L0_运行态总控"),
            "managed_by_runtime_control": True,
        },
        {
            "surface": "skill_inventory",
            "app_token_key": "FEISHU_APP_TOKEN_SKILL",
            "table_id_key": "FEISHU_TABLE_ID_SKILL",
            "table_name": str(names.get("skill_inventory") or "Skill全景盘点表"),
            "field_specs": [{"field_name": "skill_id", "type": TEXT_FIELD, "is_primary": True}]
            + [{"field_name": item, "type": TEXT_FIELD} for item in SKILL_FIELD_NAMES[1:]],
        },
        {
            "surface": "evolution_chronicle",
            "app_token_key": "FEISHU_APP_TOKEN_GOVERNANCE",
            "table_id_key": "FEISHU_TABLE_ID_EVOLUTION",
            "table_name": str(names.get("evolution_chronicle") or "原力OS进化编年史"),
            "field_specs": EVOLUTION_FIELD_SPECS,
        },
        {
            "surface": "governance_maturity",
            "app_token_key": "FEISHU_APP_TOKEN_GOVERNANCE",
            "table_id_key": "FEISHU_TABLE_ID_MATURITY",
            "table_name": str(names.get("governance_maturity") or "治理成熟度评估"),
            "field_specs": [{"field_name": "Object ID", "type": TEXT_FIELD, "is_primary": True}]
            + [{"field_name": item, "type": TEXT_FIELD} for item in MATURITY_FIELD_NAMES],
        },
        {
            "surface": "legacy_control",
            "app_token_key": "FEISHU_APP_TOKEN_LEGACY",
            "table_id_key": "FEISHU_TABLE_ID_LEGACY_CONTROL",
            "table_name": str(names.get("legacy_control") or "旧治理总控表"),
            "managed_read_only": True,
            "note": "Legacy surface remains read-only; the init script only records the configured token and table id.",
        },
    ]


def apply_table_specs(client: FeishuClient, values: dict[str, str], table_specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    applied: list[dict[str, Any]] = []
    for spec in table_specs:
        app_token = str(values[spec["app_token_key"]]).strip()
        entry = {
            "surface": spec["surface"],
            "app_token": app_token,
            "table_name": spec["table_name"],
            "table_id_key": spec["table_id_key"],
        }
        if spec.get("managed_read_only"):
            entry["table_id"] = str(values[spec["table_id_key"]]).strip()
            entry["status"] = "recorded_read_only"
            applied.append(entry)
            continue
        if spec.get("managed_by_runtime_control"):
            from dashboard.runtime_control import RuntimeControlPlane

            table_id = RuntimeControlPlane(client=client, app_token=app_token, table_name=spec["table_name"]).ensure_table()
        else:
            table_id = ensure_generic_table(client, app_token, spec["table_name"], spec["field_specs"])
        values[spec["table_id_key"]] = table_id
        entry["table_id"] = table_id
        entry["status"] = "ensured"
        applied.append(entry)
    return applied


def dry_run_table_specs(values: dict[str, str], table_specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for spec in table_specs:
        results.append(
            {
                "surface": spec["surface"],
                "app_token": str(values[spec["app_token_key"]]).strip(),
                "table_name": spec["table_name"],
                "table_id_key": spec["table_id_key"],
                "planned_table_id": str(values[spec["table_id_key"]]).strip(),
                "status": "planned_read_only" if spec.get("managed_read_only") else "planned_ensure",
            }
        )
    return results


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    mode = "apply" if args.apply else "dry_run"
    config_path = Path(args.config).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    config = load_json(config_path)
    template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
    values = require_placeholder_values(config, template_text)
    table_specs = build_table_specs({"placeholders": values, "table_names": config.get("table_names") or {}})

    if args.apply:
        client = bootstrap_client()
        table_results = apply_table_specs(client, values, table_specs)
    else:
        table_results = dry_run_table_specs(values, table_specs)

    rendered = render_template(template_text, values)
    instance_name = str(config.get("instance_name") or "instance").strip()
    rendered_path = output_dir / f"{instance_name}-CLAUDE-INIT.md"
    rendered_path.write_text(rendered + "\n", encoding="utf-8")

    plan = {
        "task_id": "TS-V2-02",
        "mode": mode,
        "instance_name": instance_name,
        "config_path": str(config_path),
        "template_path": str(TEMPLATE_PATH.resolve()),
        "rendered_init_path": str(rendered_path),
        "placeholder_count": len(values),
        "table_results": table_results,
        "notes": [
            "Rendered INIT uses the template placeholders after config validation.",
            "Only --apply touches Feishu; dry-run writes a local init plan only.",
            "Legacy control surface remains read-only and is recorded, not mutated.",
        ],
    }
    plan_path = output_dir / "feishu-base-init-plan.json"
    write_json(plan_path, plan)

    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
