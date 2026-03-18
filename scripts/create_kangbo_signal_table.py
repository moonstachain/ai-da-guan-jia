from __future__ import annotations

import json
import sys
from pathlib import Path

from mcp_server_feishu.feishu_client import FeishuClient

try:
    from scripts.r12_kangbo_signal_spec import (
        ARTIFACT_ROOT,
        FIELDS,
        TABLE_ID_FILE,
        TABLE_NAME,
        TARGET_APP_TOKEN,
        write_manifest_json,
        write_seed_csv,
        write_seed_json,
        save_table_id,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution path
    from r12_kangbo_signal_spec import (
        ARTIFACT_ROOT,
        FIELDS,
        TABLE_ID_FILE,
        TABLE_NAME,
        TARGET_APP_TOKEN,
        write_manifest_json,
        write_seed_csv,
        write_seed_json,
        save_table_id,
    )


def main() -> int:
    artifact_root = ARTIFACT_ROOT
    write_manifest_json(artifact_root / "kangbo_signal_schema_manifest.json")
    write_seed_json(artifact_root / "kangbo_signal_seed_rows.json")
    write_seed_csv(artifact_root / "kangbo_signal_seed_rows.csv")

    client = FeishuClient()
    if not client.available:
        print(
            json.dumps(
                {
                    "status": "blocked_missing_credentials",
                    "message": "FEISHU_APP_ID / FEISHU_APP_SECRET 缺失，已生成 schema/seed 工件；可改走浏览器自动化或补环境变量后重试。",
                    "target_app_token": TARGET_APP_TOKEN,
                    "table_name": TABLE_NAME,
                    "table_id_file": str(TABLE_ID_FILE),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    created = client._request(
        "POST",
        f"/bitable/v1/apps/{TARGET_APP_TOKEN}/tables",
        {"table": {"name": TABLE_NAME}},
    )
    if int(created.get("code", -1) or -1) != 0:
        print(json.dumps(created, ensure_ascii=False, indent=2))
        return 1

    table = created.get("data", created).get("table", {})
    table_id = str(table.get("table_id") or "").strip()
    if not table_id:
        print(json.dumps(created, ensure_ascii=False, indent=2))
        return 1

    fields_created: list[str] = []
    fields_failed: list[dict[str, object]] = []
    for field in FIELDS:
        payload = {
            "field_name": field["field_name"],
            "type": field["type"],
            **({"property": field["property"]} if "property" in field else {}),
        }
        result = client._request(
            "POST",
            f"/bitable/v1/apps/{TARGET_APP_TOKEN}/tables/{table_id}/fields",
            payload,
        )
        if int(result.get("code", -1) or -1) == 0:
            fields_created.append(field["field_name"])
        else:
            fields_failed.append({"field_name": field["field_name"], "result": result})

    save_table_id(table_id)
    output = {
        "status": "ok" if not fields_failed else "partial",
        "table_id": table_id,
        "table_name": TABLE_NAME,
        "fields_created": fields_created,
        "fields_failed": fields_failed,
        "target_app_token": TARGET_APP_TOKEN,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if not fields_failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
