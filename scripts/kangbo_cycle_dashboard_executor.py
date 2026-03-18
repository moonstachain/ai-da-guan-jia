from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp_server_feishu.feishu_client import FeishuClient
from scripts.create_kangbo_signal_tables import DEFAULT_ACCOUNT_ID, load_feishu_credentials
from scripts.r12_kangbo_signal_spec import NEW_BASE_LINK, TARGET_APP_TOKEN


OUTPUT_ROOT = PROJECT_ROOT / "artifacts" / "kangbo-cycle-cockpit"
AUTOMATOR_ROOT = Path.home() / ".codex" / "skills" / "feishu-dashboard-automator"
SYNC_VIEWS_SCRIPT = AUTOMATOR_ROOT / "scripts" / "sync_source_views.py"
EXPORT_SPEC_SCRIPT = AUTOMATOR_ROOT / "scripts" / "export_dashboard_spec.py"
BUILD_MVP_SCRIPT = AUTOMATOR_ROOT / "scripts" / "build_dashboard_mvp.py"

TABLE_REGISTRY = [
    {"table_name": "时间事件主表", "table_id": "tbl6ZOMIgyMXsied"},
    {"table_name": "康波阶段表", "table_id": "tbl57waor719IPFV"},
    {"table_name": "国家地区主线表", "table_id": "tbl5wBn89taolLd4"},
    {"table_name": "主题图层表", "table_id": "tbl4L1A3EcCQhgZo"},
    {"table_name": "L1_康波事件信号", "table_id": "tbl6QgzUgcXq4HO5"},
    {"table_name": "L1_历史镜像", "table_id": "tblYgEiXi94IeZGs"},
    {"table_name": "L2_资产信号映射", "table_id": "tblX03ZmKferJF65"},
]


def ensure_output_root() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)


def set_feishu_env(account_id: str) -> None:
    creds = load_feishu_credentials(account_id)
    os.environ["FEISHU_APP_ID"] = creds["app_id"]
    os.environ["FEISHU_APP_SECRET"] = creds["app_secret"]


def field_type_name(type_id: Any) -> str:
    mapping = {
        1: "text",
        2: "number",
        3: "single_select",
        4: "multi_select",
        5: "date",
        7: "checkbox",
        11: "person",
        13: "phone",
        15: "url",
        17: "link",
        18: "lookup",
        19: "formula",
        20: "created_time",
        21: "modified_time",
    }
    try:
        return mapping[int(type_id)]
    except Exception:
        return str(type_id)


def collect_table_schema(client: FeishuClient, table_name: str, table_id: str) -> dict[str, Any]:
    fields_payload = client._request("GET", f"/bitable/v1/apps/{TARGET_APP_TOKEN}/tables/{table_id}/fields")
    if fields_payload.get("error"):
        raise RuntimeError(f"list fields failed for {table_name}: {fields_payload}")
    field_items = (fields_payload.get("data") or fields_payload).get("items") or []

    views_payload = client._request("GET", f"/bitable/v1/apps/{TARGET_APP_TOKEN}/tables/{table_id}/views")
    if views_payload.get("error"):
        raise RuntimeError(f"list views failed for {table_name}: {views_payload}")
    view_items = (views_payload.get("data") or views_payload).get("items") or []

    records_payload = client.read_bitable_records(TARGET_APP_TOKEN, table_id, page_size=500)
    if records_payload.get("error"):
        raise RuntimeError(f"read records failed for {table_name}: {records_payload}")
    records = records_payload.get("records") or []

    fields = []
    config_fields = {}
    for item in field_items:
        field_name = item.get("field_name") or item.get("name") or ""
        field_id = item.get("field_id") or ""
        type_name = field_type_name(item.get("type"))
        options_map = {}
        for option in ((item.get("property") or {}).get("options") or []):
            label = str(option.get("name") or "").strip()
            option_id = str(option.get("id") or "").strip()
            if label and option_id:
                options_map[label] = option_id
        config_entry = {
            "field_id": field_id,
            "type": type_name,
        }
        if options_map:
            config_entry["options"] = options_map
        config_fields[field_name] = config_entry
        fields.append(
            {
                "field_name": field_name,
                "field_id": field_id,
                "type": type_name,
                "raw_type": item.get("type"),
                "options": options_map,
            }
        )

    return {
        "table_name": table_name,
        "table_id": table_id,
        "record_count": len(records),
        "field_count": len(fields),
        "fields": fields,
        "views": [
            {
                "view_name": view.get("view_name") or view.get("name") or "",
                "view_id": view.get("view_id") or "",
                "view_type": view.get("view_type") or "",
            }
            for view in view_items
        ],
        "config_table": {
            "table_id": table_id,
            "fields": config_fields,
        },
        "sample_record": (records[0] or {}).get("fields") if records else {},
    }


def inspect_schema(account_id: str, output_path: Path | None) -> dict[str, Any]:
    set_feishu_env(account_id)
    client = FeishuClient()
    if not client.available:
        raise RuntimeError("Feishu credentials are unavailable after loading local account config")

    tables = [collect_table_schema(client, item["table_name"], item["table_id"]) for item in TABLE_REGISTRY]
    payload = {
        "base_url": NEW_BASE_LINK,
        "app_token": TARGET_APP_TOKEN,
        "generated_from": "scripts/kangbo_cycle_dashboard_executor.py",
        "tables": tables,
        "config_tables": {item["table_name"]: item["config_table"] for item in tables},
    }
    ensure_output_root()
    final_path = output_path or OUTPUT_ROOT / "live-schema.json"
    final_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"output_path": str(final_path), "table_count": len(tables)}


def run_automator(script_path: Path, args: list[str], account_id: str) -> dict[str, Any]:
    if not script_path.exists():
        raise RuntimeError(f"Automator script missing: {script_path}")
    creds = load_feishu_credentials(account_id)
    env = dict(os.environ)
    env["FEISHU_APP_ID"] = creds["app_id"]
    env["FEISHU_APP_SECRET"] = creds["app_secret"]
    completed = subprocess.run(
        [sys.executable, str(script_path), *args],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    payload_text = completed.stdout.strip() or completed.stderr.strip()
    if completed.returncode != 0:
        raise RuntimeError(payload_text or f"{script_path.name} failed with exit code {completed.returncode}")
    return json.loads(payload_text)


def sync_source_views(config_path: Path, account_id: str, apply_changes: bool) -> dict[str, Any]:
    args = ["--config", str(config_path), "--apply" if apply_changes else "--dry-run"]
    result = run_automator(SYNC_VIEWS_SCRIPT, args, account_id)
    ensure_output_root()
    output_path = OUTPUT_ROOT / ("source-views-apply.json" if apply_changes else "source-views-dry-run.json")
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"output_path": str(output_path), "view_count": len(result.get("views") or [])}


def export_dashboard_spec(config_path: Path, views_path: Path, account_id: str) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    views_result = json.loads(views_path.read_text(encoding="utf-8"))
    ensure_output_root()
    json_path = OUTPUT_ROOT / "dashboard-card-spec.json"
    markdown_path = OUTPUT_ROOT / "dashboard-card-checklist.md"
    payload = {
        "generated_from": "scripts/kangbo_cycle_dashboard_executor.py",
        "base_name": config["base_name"],
        "base_url": config["base_url"],
        "views": views_result["views"],
        "cards": config["card_specs"],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_dashboard_checklist(config, views_result), encoding="utf-8")
    return {"json_path": str(json_path), "markdown_path": str(markdown_path)}


def render_dashboard_checklist(config: dict[str, Any], views_result: dict[str, Any]) -> str:
    view_lookup = {(item["table_name"], item["view_name"]): item for item in views_result["views"]}
    lines = [
        "# 康波周期总控舱 Dashboard Card Checklist",
        "",
        f"- Base: `{config['base_name']}`",
        f"- Base URL: {config['base_url']}",
        "- Phase 1 source views are already prepared via OpenAPI.",
        "- Hero 文本卡、onboarding 导览卡、深入页入口卡仍需在妙搭/飞书页面手工创建。",
        "- `康波阶段表` 当前是原始导入列头形态，适合保留证据，不适合做高精度筛选。",
        "",
    ]
    for group in config["dashboard_groups"]:
        group_name = group["name"]
        lines.append(f"## {group_name}")
        lines.append("")
        lines.append("### Source Views")
        lines.append("")
        seen: set[tuple[str, str]] = set()
        for card in config["card_specs"][group_name]:
            key = (card["table"], card["view"])
            if key in seen:
                continue
            seen.add(key)
            bound = view_lookup[key]
            lines.append(f"- `{card['table']} / {card['view']}`: {bound['view_url']}")
        lines.append("")
        lines.append("### Cards")
        lines.append("")
        for card in config["card_specs"][group_name]:
            bound = view_lookup[(card["table"], card["view"])]
            lines.append(f"- `{card['name']}`")
            lines.append(f"  - 类型：{card['type']}")
            lines.append(f"  - 数据源：`{card['table']} / {card['view']}`")
            lines.append(f"  - 入口：{bound['view_url']}")
            if "dimension" in card:
                lines.append(f"  - 维度：`{card['dimension']}`")
            if "metric" in card:
                metric = card["metric"]
                if isinstance(metric, list):
                    metric = " / ".join(metric)
                lines.append(f"  - 指标：`{metric}`")
            if "fields" in card:
                lines.append(f"  - 展示字段：`{'`、`'.join(card['fields'])}`")
            lines.append(f"  - 作用：{card['purpose']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_dashboard_mvp(config_path: Path, account_id: str, apply_changes: bool) -> dict[str, Any]:
    args = ["--config", str(config_path), "--apply" if apply_changes else "--dry-run"]
    result = run_automator(BUILD_MVP_SCRIPT, args, account_id)
    return result


def render_config_stub(schema_path: Path, output_path: Path) -> dict[str, Any]:
    payload = json.loads(schema_path.read_text(encoding="utf-8"))
    config = {
        "base_name": "康波周期总控舱",
        "base_url": NEW_BASE_LINK,
        "app_token": TARGET_APP_TOKEN,
        "tables": payload["config_tables"],
    }
    output_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return {"output_path": str(output_path), "table_count": len(config["tables"])}


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute Kangbo cockpit dashboard setup helpers.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_cmd = subparsers.add_parser("inspect-schema")
    inspect_cmd.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    inspect_cmd.add_argument("--output-path")

    stub_cmd = subparsers.add_parser("render-config-stub")
    stub_cmd.add_argument("--schema-path", required=True)
    stub_cmd.add_argument("--output-path", required=True)

    sync_cmd = subparsers.add_parser("sync-source-views")
    sync_cmd.add_argument("--config", required=True)
    sync_cmd.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    sync_cmd.add_argument("--apply", action="store_true")

    export_cmd = subparsers.add_parser("export-dashboard-spec")
    export_cmd.add_argument("--config", required=True)
    export_cmd.add_argument("--views-path", required=True)
    export_cmd.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)

    mvp_cmd = subparsers.add_parser("build-mvp")
    mvp_cmd.add_argument("--config", required=True)
    mvp_cmd.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    mvp_cmd.add_argument("--apply", action="store_true")

    args = parser.parse_args()

    if args.command == "inspect-schema":
        result = inspect_schema(args.account_id, Path(args.output_path).expanduser().resolve() if args.output_path else None)
    elif args.command == "render-config-stub":
        result = render_config_stub(
            Path(args.schema_path).expanduser().resolve(),
            Path(args.output_path).expanduser().resolve(),
        )
    elif args.command == "sync-source-views":
        result = sync_source_views(Path(args.config).expanduser().resolve(), args.account_id, args.apply)
    elif args.command == "export-dashboard-spec":
        result = export_dashboard_spec(
            Path(args.config).expanduser().resolve(),
            Path(args.views_path).expanduser().resolve(),
            args.account_id,
        )
    elif args.command == "build-mvp":
        result = build_dashboard_mvp(Path(args.config).expanduser().resolve(), args.account_id, args.apply)
    else:
        raise RuntimeError(f"Unsupported command: {args.command}")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
