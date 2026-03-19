from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zipfile import ZipFile

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.feishu_deploy import FeishuBitableAPI
from scripts.create_kangbo_signal_tables import DEFAULT_ACCOUNT_ID, load_feishu_credentials

APP_TOKEN = "IqZhbMJJxaq8D4sHOvkciaWFnid"
L0_TABLE_ID = "tblwzxos2mtbBo4G"
L5_TABLE_ID = "tblGERh218ui9oyC"
DEFAULT_PATCH_ZIP = Path.home() / "Downloads" / "TS-KB-07-PATCH.zip"
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "ai-da-guan-jia" / "runs"


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def load_client(account_id: str) -> FeishuBitableAPI:
    creds = load_feishu_credentials(account_id)
    os.environ["FEISHU_APP_ID"] = creds["app_id"]
    os.environ["FEISHU_APP_SECRET"] = creds["app_secret"]
    return FeishuBitableAPI(creds["app_id"], creds["app_secret"])


def load_patch_rows(patch_zip: Path) -> list[dict[str, Any]]:
    if not patch_zip.exists():
        raise RuntimeError(f"patch zip not found: {patch_zip}")
    with ZipFile(patch_zip) as zf:
        return json.loads(zf.read("l0_seed_patch.json"))


def batch(items: list[dict[str, Any]], size: int = 500) -> list[list[dict[str, Any]]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def record_dimension(record: dict[str, Any]) -> str:
    return str((record.get("fields") or {}).get("dimension") or "").strip()


def record_id(record: dict[str, Any]) -> str:
    return str(record.get("record_id") or "").strip()


def field_names(api: FeishuBitableAPI, table_id: str) -> set[str]:
    names: set[str] = set()
    for item in api.list_fields(APP_TOKEN, table_id):
        name = str(item.get("field_name") or item.get("name") or "").strip()
        if name:
            names.add(name)
    return names


def verify_patch_row_coverage(rows: list[dict[str, Any]], table_fields: set[str]) -> None:
    patch_fields = {
        key
        for row in rows
        for key in row.keys()
        if key and key != "dimension"
    }
    missing_fields = sorted(patch_fields - table_fields)
    if missing_fields:
        raise RuntimeError(f"target table is missing fields required by the patch: {', '.join(missing_fields)}")


def apply_l0_patch(api: FeishuBitableAPI, rows: list[dict[str, Any]], *, apply: bool) -> dict[str, Any]:
    existing_records = api.list_records(APP_TOKEN, L0_TABLE_ID)
    existing_by_dimension = {record_dimension(record): record for record in existing_records if record_dimension(record)}
    table_fields = field_names(api, L0_TABLE_ID)
    verify_patch_row_coverage(rows, table_fields)

    updates: list[dict[str, Any]] = []
    missing_dimensions: list[str] = []
    for row in rows:
        dimension = str(row.get("dimension") or "").strip()
        if not dimension:
            continue
        existing = existing_by_dimension.get(dimension)
        if not existing or not record_id(existing):
            missing_dimensions.append(dimension)
            continue
        fields = {
            key: value
            for key, value in row.items()
            if key != "dimension" and key in table_fields and value not in {None, ""}
        }
        updates.append({"record_id": record_id(existing), "fields": fields})

    if missing_dimensions:
        raise RuntimeError(f"missing L0 rows for dimensions: {', '.join(missing_dimensions)}")

    updated = 0
    if apply:
        for chunk in batch(updates):
            api._request(
                f"/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{L0_TABLE_ID}/records/batch_update",
                method="POST",
                payload={"records": chunk},
            )
            updated += len(chunk)

    refreshed = api.list_records(APP_TOKEN, L0_TABLE_ID)
    refreshed_by_dimension = {
        record_dimension(record): record
        for record in refreshed
        if record_dimension(record)
    }
    required_fields = ["fyp_11", "fyp_12", "fyp_13", "fyp_14", "fyp_15"]
    nonempty_dimensions = [
        dimension
        for dimension, record in refreshed_by_dimension.items()
        if dimension in {row["dimension"] for row in rows}
        and all(str((record.get("fields") or {}).get(field) or "").strip() for field in required_fields)
    ]

    return {
        "table_id": L0_TABLE_ID,
        "existing_records": len(existing_records),
        "matched_dimensions": len(updates),
        "updated_records": updated,
        "verified_records": len(refreshed),
        "nonempty_dimensions": sorted(nonempty_dimensions),
        "all_dimensions_present": len(nonempty_dimensions) == len(rows),
    }


def verify_l5_table(api: FeishuBitableAPI) -> dict[str, Any]:
    records = api.list_records(APP_TOKEN, L5_TABLE_ID)
    return {
        "table_id": L5_TABLE_ID,
        "record_count": len(records),
        "non_empty": len(records) > 0,
    }


def run(*, patch_zip: Path, apply: bool, account_id: str, output_dir: Path | None = None) -> dict[str, Any]:
    api = load_client(account_id)
    rows = load_patch_rows(patch_zip)
    artifact_dir = output_dir or ARTIFACT_ROOT / datetime.now().strftime("%Y-%m-%d") / f"adagj-{now_stamp()}-ts-kb-07-seed-patch"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "status": "applied" if apply else "dry-run",
        "patch_zip": str(patch_zip),
        "app_token": APP_TOKEN,
        "patch_rows": len(rows),
        "l0": apply_l0_patch(api, rows, apply=apply),
        "l5": verify_l5_table(api),
    }
    (artifact_dir / "ts-kb-07-seed-patch-result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"artifact_dir": str(artifact_dir), **result}


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply the TS-KB-07 Kangbo seed patch to Feishu.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Read and verify the patch without writing to Feishu.")
    mode.add_argument("--apply", action="store_true", help="Write the patch rows to Feishu.")
    parser.add_argument("--patch-zip", default=str(DEFAULT_PATCH_ZIP), help="Path to TS-KB-07-PATCH.zip")
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    parser.add_argument("--output-dir", default="")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve() if args.output_dir else None
    result = run(
        patch_zip=Path(args.patch_zip).expanduser().resolve(),
        apply=bool(args.apply),
        account_id=args.account_id,
        output_dir=output_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
