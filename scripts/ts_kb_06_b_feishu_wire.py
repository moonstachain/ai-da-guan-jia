from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.feishu_deploy import FeishuBitableAPI, normalize_record, schema_field_to_feishu_field
from scripts.create_kangbo_signal_tables import DEFAULT_ACCOUNT_ID, load_feishu_credentials

FEISHU_BASE_LINK = "https://h52xu4gwob.feishu.cn/base/IqZhbMJJxaq8D4sHOvkciaWFnid"
WEALTH_JS_PATH = REPO_ROOT / "work" / "MiroFish" / "frontend" / "src" / "data" / "wealthPhilosophy.js"

TEXT_FIELD = 1
NUMBER_FIELD = 2
SINGLE_SELECT_FIELD = 3
MULTI_SELECT_FIELD = 4
CHECKBOX_FIELD = 7

ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "ai-da-guan-jia" / "runs"


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def load_feishu_client(account_id: str) -> FeishuBitableAPI:
    creds = load_feishu_credentials(account_id)
    os.environ["FEISHU_APP_ID"] = creds["app_id"]
    os.environ["FEISHU_APP_SECRET"] = creds["app_secret"]
    return FeishuBitableAPI(creds["app_id"], creds["app_secret"])


def load_js_payload() -> dict[str, Any]:
    script = f"""
const mod = await import({json.dumps(WEALTH_JS_PATH.as_uri())});
const payload = {{
  propositions: mod.wealthPhilosophySeed.propositions,
  assets: mod.wealthPhilosophySeed.assets,
  strategies: mod.wealthPhilosophySeed.strategies,
  quantPanoramaNodes: mod.quantPanoramaNodes,
}};
console.log(JSON.stringify(payload));
"""
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "failed to load JS payload")
    return json.loads(completed.stdout)


def field_options(*names: str) -> dict[str, Any]:
    return {"options": [{"name": name} for name in names if str(name).strip()]}


def table_schema_specs() -> list[dict[str, Any]]:
    return [
        {
            "table_name": "L4_财富三观_核心命题表",
            "primary_field": "proposition_id",
            "fields": [
                {"name": "proposition_id", "type": "text"},
                {"name": "san_guan", "type": "single_select", "options": ["古今之变", "东西之变", "虚实之变"]},
                {"name": "model_name", "type": "text"},
                {"name": "layer", "type": "number"},
                {"name": "title", "type": "text"},
                {"name": "thesis", "type": "text"},
                {"name": "evidence_chain", "type": "text"},
                {"name": "golden_quote", "type": "text"},
                {"name": "related_event_ids", "type": "text"},
                {"name": "related_principle_ids", "type": "text"},
                {"name": "related_asset_ids", "type": "text"},
                {"name": "display_order", "type": "number"},
            ],
        },
        {
            "table_name": "L4_资产审美_标的库",
            "primary_field": "asset_aesthetic_id",
            "fields": [
                {"name": "asset_aesthetic_id", "type": "text"},
                {"name": "asset_name", "type": "text"},
                {"name": "asset_form", "type": "single_select", "options": ["实体资产", "线上资产", "链上资产", "智能资产"]},
                {"name": "san_guan_link", "type": "multi_select", "options": ["古今之变", "东西之变", "虚实之变"]},
                {"name": "scarcity_score", "type": "number"},
                {"name": "productivity_score", "type": "number"},
                {"name": "consensus_score", "type": "number"},
                {"name": "tax_logic", "type": "text"},
                {"name": "representative_ticker", "type": "text"},
                {"name": "narrative", "type": "text"},
                {"name": "risk_level", "type": "single_select", "options": ["低", "中", "高", "极高"]},
            ],
        },
        {
            "table_name": "L4_配置策略表",
            "primary_field": "strategy_id",
            "fields": [
                {"name": "strategy_id", "type": "text"},
                {"name": "strategy_name", "type": "text"},
                {"name": "san_guan_basis", "type": "multi_select", "options": ["古今之变", "东西之变", "虚实之变"]},
                {"name": "target_persona", "type": "text"},
                {"name": "asset_threshold", "type": "text"},
                {"name": "allocation_pct", "type": "text"},
                {"name": "holding_period", "type": "text"},
                {"name": "risk_profile", "type": "single_select", "options": ["保守", "稳健", "进取"]},
                {"name": "yuanli_match", "type": "text"},
                {"name": "action_guide", "type": "text"},
            ],
        },
        {
            "table_name": "L4_智能资产_量化全景",
            "primary_field": "node_id",
            "fields": [
                {"name": "node_id", "type": "text"},
                {"name": "parent_id", "type": "text"},
                {"name": "layer", "type": "number"},
                {"name": "node_name", "type": "text"},
                {"name": "node_name_en", "type": "text"},
                {"name": "strategy_family", "type": "text"},
                {"name": "decision_mode", "type": "single_select", "options": ["量化", "主观", "量化 + 主观", "综合"]},
                {"name": "classification_axis", "type": "text"},
                {"name": "description", "type": "text"},
                {"name": "risk_return_profile", "type": "text"},
                {"name": "expected_annual_return", "type": "text"},
                {"name": "expected_excess_return", "type": "text"},
                {"name": "expected_max_drawdown", "type": "text"},
                {"name": "market_condition_fit", "type": "multi_select", "options": ["牛市", "熊市", "震荡市", "结构市", "全市场"]},
                {"name": "liquidity_requirement", "type": "text"},
                {"name": "min_investment", "type": "text"},
                {"name": "ai_dependency", "type": "number"},
                {"name": "industry_avg_return_2025", "type": "text"},
                {"name": "industry_aum", "type": "text"},
                {"name": "key_players", "type": "text"},
                {"name": "analogy", "type": "text"},
                {"name": "color_code", "type": "text"},
                {"name": "display_order", "type": "number"},
                {"name": "is_highlighted", "type": "checkbox"},
            ],
        },
    ]


def build_rows(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    rows = {
        "L4_财富三观_核心命题表": payload["propositions"],
        "L4_资产审美_标的库": payload["assets"],
        "L4_配置策略表": payload["strategies"],
        "L4_智能资产_量化全景": payload["quantPanoramaNodes"],
    }
    return rows


def table_lookup(client: FeishuBitableAPI, app_token: str) -> dict[str, dict[str, Any]]:
    return {str(table.get("name") or "").strip(): table for table in client.list_tables(app_token)}


def field_lookup(client: FeishuBitableAPI, app_token: str, table_id: str) -> dict[str, dict[str, Any]]:
    fields = client.list_fields(app_token, table_id)
    return {str(field.get("field_name") or "").strip(): field for field in fields}


def sanitize_property(field_type: int, options: list[str] | None = None) -> dict[str, Any] | None:
    if field_type not in {SINGLE_SELECT_FIELD, MULTI_SELECT_FIELD}:
        return None
    if not options:
        return None
    return field_options(*options)


def field_payload(spec: dict[str, Any]) -> dict[str, Any]:
    field_type = {
        "text": TEXT_FIELD,
        "number": NUMBER_FIELD,
        "single_select": SINGLE_SELECT_FIELD,
        "multi_select": MULTI_SELECT_FIELD,
        "checkbox": CHECKBOX_FIELD,
    }[spec["type"]]
    payload = {"field_name": spec["name"], "type": field_type}
    prop = sanitize_property(field_type, spec.get("options"))
    if prop:
        payload["property"] = prop
    return payload


def ensure_field_options(client: FeishuBitableAPI, app_token: str, table_id: str, spec: dict[str, Any], *, apply_changes: bool) -> list[str]:
    if spec["type"] not in {"single_select", "multi_select"}:
        return []
    current = field_lookup(client, app_token, table_id).get(spec["name"])
    if current is None:
        return []
    current_options = [str(option.get("name") or "").strip() for option in ((current.get("property") or {}).get("options") or [])]
    wanted = [str(name).strip() for name in spec.get("options") or [] if str(name).strip()]
    missing = [name for name in wanted if name not in current_options]
    if not missing:
        return []
    if not apply_changes:
        return missing
    merged_options = [{"name": name} for name in current_options if name]
    for name in missing:
        merged_options.append({"name": name})
    client._request(
        "PUT",
        f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{current['field_id']}",
        payload={"field_name": spec["name"], "type": field_payload(spec)["type"], "property": {"options": merged_options}},
    )
    return missing


def ensure_table(client: FeishuBitableAPI, app_token: str, spec: dict[str, Any], *, apply_changes: bool) -> dict[str, Any]:
    desired_fields = [field_payload(field) for field in spec["fields"]]
    tables = table_lookup(client, app_token)
    existing = tables.get(spec["table_name"])
    created = False
    if existing is None:
        if not apply_changes:
            return {
                "table_name": spec["table_name"],
                "table_id": "",
                "created": False,
                "status": "planned_create",
                "missing_fields": [field["name"] for field in spec["fields"]],
            }
        created_payload = client.create_table(app_token, spec["table_name"], desired_fields)
        table_id = str(created_payload.get("table_id") or "").strip()
        if not table_id:
            raise RuntimeError(f"failed to create table {spec['table_name']}")
        created = True
    else:
        table_id = str(existing.get("table_id") or "").strip()
        if not table_id:
            raise RuntimeError(f"table {spec['table_name']} has no table_id")

    existing_fields = field_lookup(client, app_token, table_id) if apply_changes or created else {}
    created_fields: list[str] = []
    option_updates: dict[str, list[str]] = {}
    for field_spec in spec["fields"]:
        current = existing_fields.get(field_spec["name"])
        if current is None:
            created_fields.append(field_spec["name"])
            if apply_changes and not created:
                client._request(
                    "POST",
                    f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
                    payload=field_payload(field_spec),
                )
            continue
        if int(current.get("type") or 0) != field_payload(field_spec)["type"]:
            raise RuntimeError(
                f"Field type mismatch for {spec['table_name']}.{field_spec['name']}: "
                f"expected {field_payload(field_spec)['type']}, got {current.get('type')}"
            )
        missing_options = ensure_field_options(client, app_token, table_id, field_spec, apply_changes=apply_changes)
        if missing_options:
            option_updates[field_spec["name"]] = missing_options

    return {
        "table_name": spec["table_name"],
        "table_id": table_id,
        "created": created,
        "status": "created" if created else "existing",
        "created_fields": created_fields,
        "option_updates": option_updates,
        "expected_fields": len(spec["fields"]),
    }


def chunked(items: list[dict[str, Any]], size: int = 500) -> list[list[dict[str, Any]]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def seed_table(
    client: FeishuBitableAPI,
    app_token: str,
    table_id: str,
    schema: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    apply_changes: bool,
) -> dict[str, Any]:
    normalized_rows = [normalize_record(schema, row) for row in rows]
    if not table_id:
        return {
            "expected_records": len(normalized_rows),
            "existing_records": 0,
            "verified_records": 0,
            "created_records": 0,
            "status": "planned_seed",
        }

    existing_records = client.list_records(app_token, table_id)
    existing_count = len(existing_records)
    expected_count = len(normalized_rows)
    if existing_count not in {0, expected_count}:
        raise RuntimeError(
            f"Table {schema.get('table_name') or table_id} already has {existing_count} records; "
            f"expected 0 or {expected_count}."
        )

    created = 0
    if apply_changes and existing_count == 0:
        for batch in chunked(normalized_rows, 500):
            client.batch_create_records(app_token, table_id, batch)
            created += len(batch)

    verified_count = len(client.list_records(app_token, table_id))
    return {
        "expected_records": expected_count,
        "existing_records": existing_count,
        "verified_records": verified_count,
        "created_records": created,
        "status": "seeded" if created else ("already_seeded" if verified_count == expected_count else "planned_seed"),
    }


def run(*, apply_changes: bool, account_id: str) -> dict[str, Any]:
    payload = load_js_payload()
    client = load_feishu_client(account_id)
    app_token = client.resolve_app_token(FEISHU_BASE_LINK)

    table_specs = table_schema_specs()
    rows_by_table = build_rows(payload)

    tables_result: list[dict[str, Any]] = []
    table_ids: dict[str, str] = {}
    record_counts: dict[str, int] = {}

    for spec in table_specs:
        table_result = ensure_table(client, app_token, spec, apply_changes=apply_changes)
        table_ids[spec["table_name"]] = table_result["table_id"]
        tables_result.append(table_result)

    for spec in table_specs:
        table_id = table_ids[spec["table_name"]]
        seed_result = seed_table(
            client,
            app_token,
            table_id,
            {"table_name": spec["table_name"], "fields": spec["fields"]},
            rows_by_table[spec["table_name"]],
            apply_changes=apply_changes,
        )
        record_counts[spec["table_name"]] = seed_result["verified_records"]
        tables_result = [
            {**item, **seed_result} if item["table_name"] == spec["table_name"] else item
            for item in tables_result
        ]

    artifact_dir = ARTIFACT_ROOT / datetime.now().strftime("%Y-%m-%d") / f"adagj-{now_stamp()}-ts-kb-06-b"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "status": "applied" if apply_changes else "preview_ready",
        "app_token": app_token,
        "base_link": FEISHU_BASE_LINK,
        "tables": tables_result,
        "table_ids": table_ids,
        "record_counts": record_counts,
        "seed_counts": {
            "propositions": len(rows_by_table["L4_财富三观_核心命题表"]),
            "assets": len(rows_by_table["L4_资产审美_标的库"]),
            "strategies": len(rows_by_table["L4_配置策略表"]),
            "quant_panorama": len(rows_by_table["L4_智能资产_量化全景"]),
        },
    }
    (artifact_dir / "feishu-wire-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Wire TS-KB-06-B to live Feishu Bitable tables.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    args = parser.parse_args()

    result = run(apply_changes=bool(args.apply), account_id=args.account_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
