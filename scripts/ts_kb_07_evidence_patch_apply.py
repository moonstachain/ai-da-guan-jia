from __future__ import annotations

import argparse
import json
import os
import re
import sys
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib import error, request
from zipfile import ZipFile

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.feishu_deploy import FeishuBitableAPI
from scripts.create_kangbo_signal_tables import DEFAULT_ACCOUNT_ID, load_feishu_credentials

APP_TOKEN = "IqZhbMJJxaq8D4sHOvkciaWFnid"
L5_POLICY_TABLE_ID = "tblGERh218ui9oyC"
DEFAULT_PATCH_ZIP = Path.home() / "Downloads" / "TS-KB-07-EVIDENCE.zip"
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "ai-da-guan-jia" / "runs"

URL_FIELD = 15
TEXT_FIELD = 1


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


def batch(items: list[dict[str, Any]], size: int = 500) -> list[list[dict[str, Any]]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def field_name(item: dict[str, Any]) -> str:
    return str(item.get("field_name") or item.get("name") or "").strip()


def field_map(api: FeishuBitableAPI, table_id: str) -> dict[str, dict[str, Any]]:
    return {field_name(item): item for item in api.list_fields(APP_TOKEN, table_id) if field_name(item)}


def record_key(record: dict[str, Any], key_field: str) -> str:
    return str((record.get("fields") or {}).get(key_field) or "").strip()


def record_id(record: dict[str, Any]) -> str:
    return str(record.get("record_id") or "").strip()


def to_link_object(value: Any) -> dict[str, str] | None:
    if isinstance(value, dict):
        link = str(value.get("link") or value.get("text") or "").strip()
        text = str(value.get("text") or link).strip()
        if not link:
            return None
        return {"link": link, "text": text or link}
    text = str(value or "").strip()
    if not text:
        return None
    return {"link": text, "text": text}


def normalize_patch_value(field_name: str, value: Any) -> Any:
    if field_name in {"source_url", "source_doc_url"}:
        return to_link_object(value)
    if is_blank(value):
        return None
    return value


def count_field_nonempty(records: list[dict[str, Any]], field_name: str) -> int:
    return sum(0 if is_blank((record.get("fields") or {}).get(field_name)) else 1 for record in records)


def field_counts(records: list[dict[str, Any]], field_names: tuple[str, ...]) -> dict[str, int]:
    return {name: count_field_nonempty(records, name) for name in field_names}


def field_fill_rates(records: list[dict[str, Any]], field_names: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    total = len(records)
    result: dict[str, dict[str, Any]] = {}
    for name in field_names:
        filled = count_field_nonempty(records, name)
        result[name] = {"filled": filled, "total": total, "rate": round((filled / total * 100) if total else 0.0, 2)}
    return result


def overall_coverage(records: list[dict[str, Any]], field_names: tuple[str, ...]) -> dict[str, Any]:
    total_cells = len(records) * len(field_names)
    filled_cells = sum(count_field_nonempty(records, name) for name in field_names)
    return {
        "filled_cells": filled_cells,
        "total_cells": total_cells,
        "rate": round((filled_cells / total_cells * 100) if total_cells else 0.0, 2),
    }


def merge_patch_rows(
    rows: list[dict[str, Any]],
    key_field: str,
    write_fields: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get(key_field) or "").strip()
        if not key:
            raise RuntimeError(f"missing patch key field: {key_field}")
        fields = merged.setdefault(key, {})
        for field_name in write_fields:
            if field_name not in row:
                continue
            value = normalize_patch_value(field_name, row.get(field_name))
            if value is None:
                continue
            if field_name in fields and fields[field_name] != value:
                raise RuntimeError(
                    f"conflicting values for {key_field}={key}, field={field_name}: {fields[field_name]!r} vs {value!r}"
                )
            fields[field_name] = value
    return merged


def index_records(records: list[dict[str, Any]], key_field: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        key = record_key(record, key_field)
        if not key:
            continue
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
        current_fields = current.get("fields") or {}
        effective_fields = {
            field_name: value for field_name, value in patch_fields.items() if current_fields.get(field_name) != value
        }
        if not effective_fields:
            continue
        updates.append({"record_id": record_id(current), "fields": effective_fields})
        simulated = simulated_index[key]
        simulated_fields = simulated.setdefault("fields", {})
        simulated_fields.update(effective_fields)
        simulated_record = simulated_records_index[key]
        simulated_record_fields = simulated_record.setdefault("fields", {})
        simulated_record_fields.update(effective_fields)

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


def apply_record_patch(
    api: FeishuBitableAPI,
    *,
    table_id: str,
    patch_rows: list[dict[str, Any]],
    key_field: str,
    write_fields: tuple[str, ...],
    apply: bool,
) -> dict[str, Any]:
    current_records = api.list_records(APP_TOKEN, table_id)
    merged_rows = merge_patch_rows(patch_rows, key_field, write_fields)
    updates, simulated_records, simulated_index, missing_keys = build_update_payloads(
        current_records,
        merged_rows,
        key_field=key_field,
    )
    if missing_keys:
        raise RuntimeError(f"missing live rows for keys: {', '.join(missing_keys)}")

    before_counts = field_counts(current_records, write_fields)
    before_fill_rates = field_fill_rates(current_records, write_fields)
    before_coverage = overall_coverage(current_records, write_fields)

    updated_records = 0
    if apply:
        for chunk in batch(updates):
            if not chunk:
                continue
            api._request(
                f"/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{table_id}/records/batch_update",
                method="POST",
                payload={"records": chunk},
            )
            updated_records += len(chunk)

    actual_records = api.list_records(APP_TOKEN, table_id) if apply else simulated_records
    mismatches = compare_expected_actual(
        simulated_index if apply else simulated_index,
        actual_records,
        key_field=key_field,
        write_fields=write_fields,
    ) if apply else []

    after_counts = field_counts(actual_records, write_fields)
    after_fill_rates = field_fill_rates(actual_records, write_fields)
    after_coverage = overall_coverage(actual_records, write_fields)

    return {
        "key_field": key_field,
        "write_fields": list(write_fields),
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


def ensure_fields(
    api: FeishuBitableAPI,
    *,
    table_id: str,
    apply: bool,
) -> dict[str, Any]:
    expected_fields = [
        {"field_name": "source_doc_url", "type": URL_FIELD},
        {"field_name": "source_excerpt", "type": TEXT_FIELD},
        {"field_name": "evidence_note", "type": TEXT_FIELD},
    ]
    current = field_map(api, table_id)
    created_fields: list[dict[str, Any]] = []
    existing_fields: list[dict[str, Any]] = []
    planned_fields: list[dict[str, Any]] = []

    for spec in expected_fields:
        name = spec["field_name"]
        existing = current.get(name)
        if existing:
            actual_type = int(existing.get("type") or 0)
            if actual_type != spec["type"]:
                raise RuntimeError(f"field type mismatch for {name}: expected {spec['type']}, got {actual_type}")
            existing_fields.append(
                {
                    "field_name": name,
                    "field_id": str(existing.get("field_id") or "").strip(),
                    "type": actual_type,
                }
            )
            continue
        if not apply:
            planned_fields.append({"field_name": name, "type": spec["type"]})
            continue
        response = api._request(
            f"/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{table_id}/fields",
            method="POST",
            payload={"field_name": name, "type": spec["type"]},
        )
        field = (response.get("data") or {}).get("field") or (response.get("data") or {})
        created_fields.append(
            {
                "field_name": str(field.get("field_name") or name).strip(),
                "field_id": str(field.get("field_id") or "").strip(),
                "type": int(field.get("type") or spec["type"]),
            }
        )

    refreshed = field_map(api, table_id) if apply else current
    missing_after_create = [spec["field_name"] for spec in expected_fields if spec["field_name"] not in refreshed and apply]
    if missing_after_create:
        raise RuntimeError(f"failed to create fields: {', '.join(missing_after_create)}")

    field_ids: dict[str, str] = {}
    for spec in expected_fields:
        item = refreshed.get(spec["field_name"])
        if item:
            field_ids[spec["field_name"]] = str(item.get("field_id") or "").strip()

    return {
        "expected_fields": expected_fields,
        "existing_fields": existing_fields,
        "created_fields": created_fields,
        "planned_fields": planned_fields,
        "field_ids": field_ids,
        "mode": "applied" if apply else "dry-run",
    }


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if tag in {"p", "div", "br", "li", "tr", "section", "article", "header", "footer", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag in {"p", "div", "br", "li", "tr", "section", "article", "header", "footer", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = unescape(data)
        if text:
            self.parts.append(text)

    def text(self) -> str:
        return "".join(self.parts)


def fetch_url_text(url: str, timeout: int = 30) -> str:
    req = request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Codex TS-KB-07 evidence patch)",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    with request.urlopen(req, timeout=timeout) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
    for encoding in (charset, "utf-8", "gb18030", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def extract_visible_text(html: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(html)
    text = parser.text()
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_for_search(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def find_excerpt(doc_text: str, wording: str, window: int = 100) -> str | None:
    haystack = normalize_for_search(doc_text)
    needle = normalize_for_search(wording)
    if not haystack or not needle:
        return None
    index = haystack.find(needle)
    if index < 0:
        return None
    start = max(0, index - window)
    end = min(len(haystack), index + len(needle) + window)
    return haystack[start:end]


def build_excerpt_updates(
    records: list[dict[str, Any]],
    *,
    doc_cache: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    updates: list[dict[str, Any]] = []
    stats = {
        "candidate_records": 0,
        "matched_records": 0,
        "missing_doc_urls": [],
        "unmatched_signals": [],
        "doc_urls": sorted(doc_cache),
    }
    for record in records:
        fields = record.get("fields") or {}
        original_wording = str(fields.get("original_wording") or "").strip()
        if not original_wording:
            continue
        stats["candidate_records"] += 1
        current_excerpt = fields.get("source_excerpt")
        if not is_blank(current_excerpt):
            continue
        doc_url = ""
        source_doc = fields.get("source_doc_url")
        source_url = fields.get("source_url")
        if isinstance(source_doc, dict):
            doc_url = str(source_doc.get("link") or source_doc.get("text") or "").strip()
        elif isinstance(source_doc, str):
            doc_url = source_doc.strip()
        if not doc_url and isinstance(source_url, dict):
            doc_url = str(source_url.get("link") or source_url.get("text") or "").strip()
        elif not doc_url and isinstance(source_url, str):
            doc_url = source_url.strip()
        if not doc_url:
            stats["missing_doc_urls"].append(record_key(record, "signal_id"))
            continue
        doc_text = doc_cache.get(doc_url)
        if not doc_text:
            stats["missing_doc_urls"].append(doc_url)
            continue
        excerpt = find_excerpt(doc_text, original_wording)
        if not excerpt:
            stats["unmatched_signals"].append(
                {"signal_id": record_key(record, "signal_id"), "doc_url": doc_url, "original_wording": original_wording}
            )
            continue
        stats["matched_records"] += 1
        updates.append({"record_id": record_id(record), "fields": {"source_excerpt": excerpt}})
    return updates, stats


def apply_excerpt_patch(api: FeishuBitableAPI, *, table_id: str, apply: bool) -> dict[str, Any]:
    current_records = api.list_records(APP_TOKEN, table_id)
    doc_urls: list[str] = []
    for record in current_records:
        fields = record.get("fields") or {}
        for field_name in ("source_doc_url", "source_url"):
            value = fields.get(field_name)
            if isinstance(value, dict):
                url = str(value.get("link") or value.get("text") or "").strip()
            else:
                url = str(value or "").strip()
            if url and url not in doc_urls:
                doc_urls.append(url)

    doc_cache: dict[str, str] = {}
    warnings: list[str] = []
    for url in doc_urls:
        try:
            html = fetch_url_text(url)
            doc_cache[url] = extract_visible_text(html)
        except (error.URLError, TimeoutError, RuntimeError, ValueError, OSError) as exc:
            warnings.append(f"failed to fetch {url}: {exc}")

    updates, stats = build_excerpt_updates(current_records, doc_cache=doc_cache)
    before_counts = field_counts(current_records, ("source_excerpt",))
    before_fill_rates = field_fill_rates(current_records, ("source_excerpt",))
    before_coverage = overall_coverage(current_records, ("source_excerpt",))

    updated_records = 0
    if apply:
        for chunk in batch(updates):
            if not chunk:
                continue
            api._request(
                f"/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{table_id}/records/batch_update",
                method="POST",
                payload={"records": chunk},
            )
            updated_records += len(chunk)

    actual_records = api.list_records(APP_TOKEN, table_id) if apply else current_records
    after_counts = field_counts(actual_records, ("source_excerpt",))
    after_fill_rates = field_fill_rates(actual_records, ("source_excerpt",))
    after_coverage = overall_coverage(actual_records, ("source_excerpt",))

    return {
        "mode": "applied" if apply else "dry-run",
        "doc_url_count": len(doc_urls),
        "cached_doc_count": len(doc_cache),
        "warnings": warnings,
        "excerpt_stats": stats,
        "updated_records": updated_records,
        "before_counts": before_counts,
        "after_counts": after_counts,
        "before_fill_rates": before_fill_rates,
        "after_fill_rates": after_fill_rates,
        "before_coverage": before_coverage,
        "after_coverage": after_coverage,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(*, patch_zip: Path, apply: bool, account_id: str, output_dir: Path | None = None, skip_excerpt: bool = False) -> dict[str, Any]:
    api = load_client(account_id)
    artifact_dir = output_dir or ARTIFACT_ROOT / datetime.now().strftime("%Y-%m-%d") / f"adagj-{now_stamp()}-ts-kb-07-evidence-patch"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    source_url_patch = load_patch_json(patch_zip, "l5_source_url_patch.json")
    evidence_note_patch = load_patch_json(patch_zip, "l5_evidence_note_patch.json")

    phase1 = ensure_fields(api, table_id=L5_POLICY_TABLE_ID, apply=apply)
    phase2 = apply_record_patch(
        api,
        table_id=L5_POLICY_TABLE_ID,
        patch_rows=source_url_patch,
        key_field="signal_id",
        write_fields=("source_url", "source_doc_url"),
        apply=apply,
    )
    phase3 = apply_record_patch(
        api,
        table_id=L5_POLICY_TABLE_ID,
        patch_rows=evidence_note_patch,
        key_field="signal_id",
        write_fields=("evidence_note",),
        apply=apply,
    )
    phase4: dict[str, Any] | None = None
    if apply and not skip_excerpt:
        try:
            phase4 = apply_excerpt_patch(api, table_id=L5_POLICY_TABLE_ID, apply=True)
        except Exception as exc:  # noqa: BLE001 - best-effort optional phase
            phase4 = {"mode": "failed", "warning": str(exc)}
    elif skip_excerpt:
        phase4 = {"mode": "skipped"}
    else:
        phase4 = {"mode": "dry-run-skipped"}

    summary = {
        "status": "applied" if apply else "dry-run",
        "patch_zip": str(patch_zip),
        "app_token": APP_TOKEN,
        "table_id": L5_POLICY_TABLE_ID,
        "artifact_dir": str(artifact_dir),
        "phase1": phase1,
        "phase2": phase2,
        "phase3": phase3,
        "phase4": phase4,
    }
    write_json(artifact_dir / "ts-kb-07-evidence-patch-result.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply the TS-KB-07 evidence patch to Feishu.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Simulate the patch without writing to Feishu.")
    mode.add_argument("--apply", action="store_true", help="Write the patch to Feishu.")
    parser.add_argument("--patch-zip", default=str(DEFAULT_PATCH_ZIP), help="Path to TS-KB-07-EVIDENCE.zip")
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--skip-excerpts", action="store_true", help="Skip the optional source_excerpt crawl phase.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve() if args.output_dir else None
    result = run(
        patch_zip=Path(args.patch_zip).expanduser().resolve(),
        apply=bool(args.apply),
        account_id=args.account_id,
        output_dir=output_dir,
        skip_excerpt=bool(args.skip_excerpts),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
