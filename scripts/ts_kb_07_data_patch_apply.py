from __future__ import annotations

import argparse
import json
import os
import sys
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zipfile import ZipFile

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.feishu_deploy import FeishuBitableAPI
from scripts.create_kangbo_signal_tables import DEFAULT_ACCOUNT_ID, load_feishu_credentials

APP_TOKEN = "IqZhbMJJxaq8D4sHOvkciaWFnid"
L0_TABLE_ID = "tblwzxos2mtbBo4G"
L5_POLICY_TABLE_ID = "tblGERh218ui9oyC"
L5_MATRIX_TABLE_ID = "tbljcZoJhpBurxXL"
DEFAULT_PATCH_ZIP = Path.home() / "Downloads" / "TS-KB-07-DATA-PATCH.zip"
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "ai-da-guan-jia" / "runs"


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def load_client(account_id: str) -> FeishuBitableAPI:
    creds = load_feishu_credentials(account_id)
    os.environ["FEISHU_APP_ID"] = creds["app_id"]
    os.environ["FEISHU_APP_SECRET"] = creds["app_secret"]
    return FeishuBitableAPI(creds["app_id"], creds["app_secret"])


def load_patch_json(patch_zip: Path, member: str) -> list[dict[str, Any]]:
    if not patch_zip.exists():
        raise RuntimeError(f"patch zip not found: {patch_zip}")
    with ZipFile(patch_zip) as zf:
        return json.loads(zf.read(member))


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def field_names(api: FeishuBitableAPI, table_id: str) -> set[str]:
    names: set[str] = set()
    for item in api.list_fields(APP_TOKEN, table_id):
        name = str(item.get("field_name") or item.get("name") or "").strip()
        if name:
            names.add(name)
    return names


def batch(items: list[dict[str, Any]], size: int = 500) -> list[list[dict[str, Any]]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def record_key(record: dict[str, Any], key_field: str) -> str:
    return str((record.get("fields") or {}).get(key_field) or "").strip()


def record_id(record: dict[str, Any]) -> str:
    return str(record.get("record_id") or "").strip()


def to_link_object(url: Any) -> dict[str, str] | None:
    value = str(url or "").strip()
    if not value:
        return None
    return {"link": value, "text": value}


def normalize_value(field_name: str, value: Any) -> Any:
    if field_name == "source_url":
        return to_link_object(value)
    if is_blank(value):
        return None
    return value


@dataclass(frozen=True)
class PatchSpec:
    name: str
    member: str
    table_id: str
    key_field: str
    write_fields: tuple[str, ...]


PATCH_SPECS: tuple[PatchSpec, ...] = (
    PatchSpec(
        name="P0 矩阵补数据",
        member="l5_matrix_patch_final.json",
        table_id=L5_MATRIX_TABLE_ID,
        key_field="indicator",
        write_fields=("y2021", "y2022", "y2023", "y2024", "y2025", "y2026", "trend", "investment_signal"),
    ),
    PatchSpec(
        name="P1 补source_url",
        member="l5_url_patch.json",
        table_id=L5_POLICY_TABLE_ID,
        key_field="signal_id",
        write_fields=("source_url",),
    ),
    PatchSpec(
        name="P1 补yoy_change",
        member="l5_yoy_patch.json",
        table_id=L5_POLICY_TABLE_ID,
        key_field="signal_id",
        write_fields=("yoy_change",),
    ),
    PatchSpec(
        name="P2 L0小补丁",
        member="l0_small_patch.json",
        table_id=L0_TABLE_ID,
        key_field="dimension",
        write_fields=("investment_implication", "kangbo_cross"),
    ),
)


def merge_patch_rows(rows: list[dict[str, Any]], key_field: str, write_fields: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get(key_field) or "").strip()
        if not key:
            raise RuntimeError(f"missing patch key field: {key_field}")
        fields = merged.setdefault(key, {})
        for field_name in write_fields:
            if field_name not in row:
                continue
            value = normalize_value(field_name, row.get(field_name))
            if value is None:
                continue
            if field_name in fields and fields[field_name] != value:
                raise RuntimeError(
                    f"conflicting values for {key_field}={key}, field={field_name}: {fields[field_name]!r} vs {value!r}"
                )
            fields[field_name] = value
    return merged


def count_field_nonempty(records: list[dict[str, Any]], field_name: str) -> int:
    return sum(0 if is_blank((record.get("fields") or {}).get(field_name)) else 1 for record in records)


def field_counts(records: list[dict[str, Any]], field_names: tuple[str, ...]) -> dict[str, int]:
    return {field_name: count_field_nonempty(records, field_name) for field_name in field_names}


def field_fill_rates(records: list[dict[str, Any]], field_names: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    total = len(records)
    result: dict[str, dict[str, Any]] = {}
    for field_name in field_names:
        count = count_field_nonempty(records, field_name)
        result[field_name] = {
            "filled": count,
            "total": total,
            "rate": round((count / total * 100) if total else 0.0, 2),
        }
    return result


def overall_coverage(records: list[dict[str, Any]], field_names: tuple[str, ...]) -> dict[str, Any]:
    total_cells = len(records) * len(field_names)
    filled_cells = sum(count_field_nonempty(records, field_name) for field_name in field_names)
    return {
        "filled_cells": filled_cells,
        "total_cells": total_cells,
        "rate": round((filled_cells / total_cells * 100) if total_cells else 0.0, 2),
    }


def index_records(records: list[dict[str, Any]], key_field: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        key = record_key(record, key_field)
        if key:
            if key in indexed:
                raise RuntimeError(f"duplicate live record key for {key_field}={key}")
            indexed[key] = record
    return indexed


def build_update_payloads(
    current_records: list[dict[str, Any]],
    merged_patch_rows: dict[str, dict[str, Any]],
    *,
    key_field: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]], list[str]]:
    current_index = index_records(current_records, key_field)
    updates: list[dict[str, Any]] = []
    simulated_index = {record_key(record, key_field): deepcopy(record) for record in current_records if record_key(record, key_field)}
    simulated_records = deepcopy(current_records)
    simulated_records_index = index_records(simulated_records, key_field)
    missing_keys: list[str] = []

    for key, patch_fields in merged_patch_rows.items():
        current = current_index.get(key)
        if not current or not record_id(current):
            missing_keys.append(key)
            continue
        updates.append({"record_id": record_id(current), "fields": patch_fields})
        simulated = simulated_index[key]
        simulated_fields = simulated.setdefault("fields", {})
        simulated_fields.update(patch_fields)
        simulated_record = simulated_records_index[key]
        simulated_record_fields = simulated_record.setdefault("fields", {})
        simulated_record_fields.update(patch_fields)

    return updates, simulated_records, simulated_index, missing_keys


def compare_expected_actual(
    expected_index: dict[str, dict[str, Any]],
    actual_records: list[dict[str, Any]],
    *,
    key_field: str,
    write_fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    actual_index = index_records(actual_records, key_field)
    mismatches: list[dict[str, Any]] = []
    for key, expected_record in expected_index.items():
        actual_record = actual_index.get(key)
        if not actual_record:
            mismatches.append({"key": key, "error": "missing_record"})
            continue
        expected_fields = expected_record.get("fields") or {}
        actual_fields = actual_record.get("fields") or {}
        for field_name in write_fields:
            if actual_fields.get(field_name) != expected_fields.get(field_name):
                mismatches.append(
                    {
                        "key": key,
                        "field": field_name,
                        "expected": expected_fields.get(field_name),
                        "actual": actual_fields.get(field_name),
                    }
                )
    return mismatches


def apply_patch(
    api: FeishuBitableAPI,
    spec: PatchSpec,
    patch_rows: list[dict[str, Any]],
    *,
    apply: bool,
) -> dict[str, Any]:
    current_records = api.list_records(APP_TOKEN, spec.table_id)
    table_fields = field_names(api, spec.table_id)
    missing_table_fields = [field for field in spec.write_fields if field not in table_fields]
    if missing_table_fields:
        raise RuntimeError(
            f"{spec.name} target table missing fields: {', '.join(missing_table_fields)}"
        )

    merged_rows = merge_patch_rows(patch_rows, spec.key_field, spec.write_fields)
    updates, simulated_records, simulated_index, missing_keys = build_update_payloads(
        current_records,
        merged_rows,
        key_field=spec.key_field,
    )
    if missing_keys:
        raise RuntimeError(f"{spec.name} missing live rows for keys: {', '.join(missing_keys)}")

    before_counts = field_counts(current_records, spec.write_fields)
    before_fill_rates = field_fill_rates(current_records, spec.write_fields)
    before_coverage = overall_coverage(current_records, spec.write_fields)

    updated_records = 0
    if apply:
        for chunk in batch(updates):
            api._request(
                f"/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{spec.table_id}/records/batch_update",
                method="POST",
                payload={"records": chunk},
            )
            updated_records += len(chunk)

    actual_records = api.list_records(APP_TOKEN, spec.table_id) if apply else simulated_records
    if apply:
        mismatches = compare_expected_actual(
            simulated_index,
            actual_records,
            key_field=spec.key_field,
            write_fields=spec.write_fields,
        )
    else:
        mismatches = []

    after_counts = field_counts(actual_records, spec.write_fields)
    after_fill_rates = field_fill_rates(actual_records, spec.write_fields)
    after_coverage = overall_coverage(actual_records, spec.write_fields)

    return {
        "patch_name": spec.name,
        "member": spec.member,
        "table_id": spec.table_id,
        "key_field": spec.key_field,
        "write_fields": list(spec.write_fields),
        "patch_rows": len(patch_rows),
        "matched_keys": len(merged_rows),
        "updated_records": updated_records,
        "mode": "applied" if apply else "dry-run",
        "before_counts": before_counts,
        "after_counts": after_counts,
        "before_fill_rates": before_fill_rates,
        "after_fill_rates": after_fill_rates,
        "before_coverage": before_coverage,
        "after_coverage": after_coverage,
        "mismatches": mismatches,
    }


def run(*, patch_zip: Path, apply: bool, account_id: str, output_dir: Path | None = None) -> dict[str, Any]:
    api = load_client(account_id)
    artifact_dir = output_dir or ARTIFACT_ROOT / datetime.now().strftime("%Y-%m-%d") / f"adagj-{now_stamp()}-ts-kb-07-data-patch"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    patch_bundle = {spec.member: load_patch_json(patch_zip, spec.member) for spec in PATCH_SPECS}
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for spec in PATCH_SPECS:
        try:
            result = apply_patch(api, spec, patch_bundle[spec.member], apply=apply)
            result["status"] = "ok"
            results.append(result)
        except Exception as exc:
            failure = {
                "patch_name": spec.name,
                "member": spec.member,
                "table_id": spec.table_id,
                "status": "failed",
                "error": str(exc),
            }
            failures.append(failure)
            results.append(failure)

    summary = {
        "status": "applied" if apply and not failures else "dry-run" if not apply and not failures else "partial_failure",
        "patch_zip": str(patch_zip),
        "app_token": APP_TOKEN,
        "patches": results,
        "failures": failures,
    }
    (artifact_dir / "ts-kb-07-data-patch-result.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if failures:
        (artifact_dir / "fallback.json").write_text(
            json.dumps({"patch_zip": str(patch_zip), "failures": failures}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return {"artifact_dir": str(artifact_dir), **summary}


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply the TS-KB-07 data patch to Feishu.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Read the patch and simulate verification without writing.")
    mode.add_argument("--apply", action="store_true", help="Write the patch updates to Feishu.")
    parser.add_argument("--patch-zip", default=str(DEFAULT_PATCH_ZIP), help="Path to TS-KB-07-DATA-PATCH.zip")
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
