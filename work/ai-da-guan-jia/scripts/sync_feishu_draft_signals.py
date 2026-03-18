#!/usr/bin/env python3
"""Probe Feishu draft-signal schema for AI大管家."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request


ROOT = Path(__file__).resolve().parents[1]
SIGNALS_DIR = ROOT / "signals"
PROBE_RESULT_PATH = SIGNALS_DIR / "schema-probe-result.md"
DEFAULT_ACCOUNT_ID = "feishu-claw"
DEFAULT_BASE_TOKEN = "PVDgbdWYFaDLBiss0hlcM5WRnQc"
DEFAULT_TABLE_ID = "tblB9JQ4cROTBUnr"
DEFAULT_TABLE_NAME = "战略任务追踪表"
OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"
FEISHU_AUTH_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
FEISHU_API_BASE = "https://open.feishu.cn/open-apis/bitable/v1"


class FeishuAuthError(RuntimeError):
    pass


class FeishuAPIError(RuntimeError):
    pass


def json_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    request_headers = {"User-Agent": "ai-da-guan-jia-draft-signal-probe/1.0"}
    if headers:
        request_headers.update(headers)
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib_request.Request(url, data=body, headers=request_headers, method=method.upper())
    try:
        with urllib_request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib_error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {exc.reason}: {details}") from exc


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_feishu_account(account_id: str) -> dict[str, str]:
    config = read_json(OPENCLAW_CONFIG)
    accounts = (((config.get("channels") or {}).get("feishu") or {}).get("accounts") or {})
    account = accounts.get(account_id) or {}
    app_id = str(account.get("appId") or "").strip()
    app_secret = str(account.get("appSecret") or "").strip()
    if not app_id or not app_secret:
        raise FeishuAuthError(f"Missing Feishu account credentials for accountId={account_id}")
    return {"app_id": app_id, "app_secret": app_secret}


def fetch_tenant_access_token(app_id: str, app_secret: str) -> str:
    try:
        result = json_request(
            "POST",
            FEISHU_AUTH_URL,
            payload={"app_id": app_id, "app_secret": app_secret},
        )
    except Exception as exc:  # network or transport failures still surface as auth setup issues here
        raise FeishuAuthError(f"Feishu auth request failed: {exc}") from exc
    if result.get("code") != 0:
        raise FeishuAuthError(f"Feishu auth failed: {result}")
    token = str((result.get("tenant_access_token") or "")).strip()
    if not token:
        raise FeishuAuthError(f"Feishu auth returned empty token: {result}")
    return token


def resolve_base_token() -> str:
    for env_name in (
        "FEISHU_BITABLE_BRIDGE_BASE_TOKEN",
        "AI_DA_GUAN_JIA_FEISHU_BASE_TOKEN",
    ):
        value = str(os.getenv(env_name) or "").strip()
        if value:
            return value
    return DEFAULT_BASE_TOKEN


@dataclass
class FeishuBitableClient:
    app_id: str
    app_secret: str
    base_token: str
    _tenant_access_token: str | None = None

    def _auth_headers(self) -> dict[str, str]:
        if not self._tenant_access_token:
            try:
                self._tenant_access_token = fetch_tenant_access_token(self.app_id, self.app_secret)
            except FeishuAuthError:
                raise
            except Exception as exc:
                raise FeishuAuthError(f"Feishu auth setup failed: {exc}") from exc
        return {"Authorization": f"Bearer {self._tenant_access_token}"}

    def _api(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{FEISHU_API_BASE}{path}"
        if query:
            url = f"{url}?{urllib_parse.urlencode(query)}"
        result = json_request(method, url, headers=self._auth_headers(), payload=payload)
        if result.get("code") != 0:
            raise FeishuAPIError(f"Feishu API failed {path}: {result}")
        return result

    def list_fields(self, table_id: str) -> list[dict[str, Any]]:
        result = self._api("GET", f"/apps/{self.base_token}/tables/{table_id}/fields", query={"page_size": 100})
        return ((result.get("data") or {}).get("items") or [])

    def list_records(
        self,
        table_id: str,
        *,
        page_size: int = 500,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            query: dict[str, Any] = {"page_size": page_size}
            if page_token:
                query["page_token"] = page_token
            result = self._api("GET", f"/apps/{self.base_token}/tables/{table_id}/records", query=query)
            data = result.get("data") or {}
            records.extend(data.get("items") or [])
            if limit is not None and len(records) >= limit:
                return records[:limit]
            if not data.get("has_more"):
                break
            page_token = str(data.get("page_token") or "").strip() or None
            if not page_token:
                break
        return records if limit is None else records[:limit]


def type_label(field_item: dict[str, Any]) -> str:
    field_type = field_item.get("type")
    if isinstance(field_type, int):
        return str(field_type)
    if field_type is None:
        return ""
    return str(field_type)


def normalize_text(text: str) -> str:
    return "".join(ch.lower() for ch in text if ch.isalnum())


def best_field_match(target: str, fields: list[dict[str, Any]]) -> tuple[str, str]:
    aliases: dict[str, list[str]] = {
        "task_id": ["task_id", "编号", "id", "taskid"],
        "task_name": ["task_name", "任务标题", "标题", "name", "taskname"],
        "task_status": ["task_status", "状态", "status", "taskstatus"],
        "priority": ["priority", "优先级", "prio"],
        "owner": ["owner", "负责人", "owner_name"],
        "created_time": ["created_time", "创建时间", "create_time", "createdtime"],
    }
    target_key = normalize_text(target)
    live_names = [str(item.get("field_name") or "") for item in fields]
    for candidate in aliases.get(target, [target]):
        for live_name in live_names:
            if normalize_text(candidate) == normalize_text(live_name):
                return live_name, "exact"
    for live_name in live_names:
        live_key = normalize_text(live_name)
        if target_key and (target_key in live_key or live_key in target_key):
            return live_name, "substring"
    if target == "created_time":
        return "record.created_time (system field)", "system"
    return "UNCONFIRMED", "needs-confirmation"


def build_mapping_suggestions(fields: list[dict[str, Any]]) -> list[dict[str, str]]:
    suggestions: list[dict[str, str]] = []
    for target in ["task_id", "task_name", "task_status", "priority", "owner", "created_time"]:
        candidate, method = best_field_match(target, fields)
        rationale = {
            "exact": "live field name matches the target or a known alias",
            "substring": "live field name is a close textual match",
            "system": "created_time is usually a record system field rather than a normal Bitable field",
            "needs-confirmation": "no clear live field match; confirm during A-1 mapping review",
        }[method]
        suggestions.append(
            {
                "target_column": target,
                "suggested_field": candidate,
                "match_mode": method,
                "rationale": rationale,
            }
        )
    return suggestions


def markdown_table(rows: list[list[str]], headers: list[str]) -> str:
    def esc(value: str) -> str:
        return value.replace("|", r"\|")

    out = ["| " + " | ".join(esc(h) for h in headers) + " |"]
    out.append("|" + "|".join(["---"] * len(headers)) + "|")
    for row in rows:
        out.append("| " + " | ".join(esc(cell) for cell in row) + " |")
    return "\n".join(out)


def format_created_time(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 10_000_000_000:
            ts /= 1000.0
        return datetime.fromtimestamp(ts).astimezone().date().isoformat()
    text = str(value).strip()
    if not text:
        return ""
    if text.isdigit():
        ts = float(text)
        if ts > 10_000_000_000:
            ts /= 1000.0
        return datetime.fromtimestamp(ts).astimezone().date().isoformat()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone().date().isoformat()
    except ValueError:
        return text


def split_markdown_row(line: str) -> list[str]:
    return [cell.replace(r"\|", "|").strip() for cell in line.strip().strip("|").split("|")]


def parse_existing_pending_rows(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    header = "| 编号 | 标题 | 状态 | 优先级 | 负责人 | 创建时间 |"
    rows: dict[str, dict[str, str]] = {}
    in_table = False
    for line in lines:
        if line.strip() == header:
            in_table = True
            continue
        if not in_table:
            continue
        stripped = line.strip()
        if not stripped.startswith("|"):
            if rows:
                break
            continue
        cells = split_markdown_row(line)
        if len(cells) != 6:
            continue
        if all(re.fullmatch(r"-+", cell.replace(" ", "")) for cell in cells):
            continue
        task_id = cells[0]
        if not task_id:
            continue
        rows[task_id] = {
            "task_id": cells[0],
            "title": cells[1],
            "status": cells[2],
            "priority": cells[3],
            "owner": cells[4],
            "created_time": cells[5],
        }
    return rows


def build_pending_rows(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    required_fields = ["task_id", "task_name", "task_status", "priority", "owner"]
    rows: list[dict[str, str]] = []
    for record in records:
        fields = record.get("fields") or {}
        missing = [name for name in required_fields if name not in fields]
        if missing:
            raise ValueError(f"field mapping error - expected {missing[0]} not found")
        task_status = str(fields.get("task_status") or "").strip()
        if task_status not in {"草案待审", "已审批待执行"}:
            continue
        task_id = str(fields.get("task_id") or "").strip()
        if not task_id:
            raise ValueError("field mapping error - expected task_id not found")
        rows.append(
            {
                "task_id": task_id,
                "title": str(fields.get("task_name") or "").strip(),
                "status": task_status,
                "priority": str(fields.get("priority") or "").strip(),
                "owner": str(fields.get("owner") or "").strip(),
                "created_time": format_created_time(
                    fields.get("start_date")
                    or record.get("created_time")
                    or record.get("createdTime")
                    or record.get("create_time")
                ),
            }
        )
    rows.sort(key=lambda item: item["task_id"])
    return rows


def render_pending_markdown(rows: list[dict[str, str]], *, total: int, new: int, changed: int, removed: int) -> str:
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    lines = [
        "# 待处理任务信号",
        "# 自动生成，勿手动编辑",
        f"# canonical: {SIGNALS_DIR / 'pending-tasks.md'}",
        f"# 最后扫描：{now}",
        f"# 扫描结果：成功 | total={total} | new={new} | changed={changed} | removed={removed}",
        "",
        "| 编号 | 标题 | 状态 | 优先级 | 负责人 | 创建时间 |",
        "|------|------|------|--------|--------|----------|",
    ]
    for row in rows:
        lines.append(
            f"| {row['task_id']} | {row['title']} | {row['status']} | {row['priority']} | {row['owner']} | {row['created_time']} |"
        )
    if not rows:
        lines.extend(["", "# 无待处理任务"])
    return "\n".join(lines).rstrip() + "\n"


def prepend_failure_note(path: Path, reason: str) -> None:
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    note = f"# LAST_SCAN_FAILED: {now} {reason}".rstrip()
    if path.exists():
        current = path.read_text(encoding="utf-8")
        path.write_text(note + "\n" + current.lstrip("\n"), encoding="utf-8")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(note + "\n", encoding="utf-8")


def render_probe_markdown(
    *,
    account_id: str,
    base_token: str,
    table_id: str,
    table_name: str,
    fields: list[dict[str, Any]],
    records: list[dict[str, Any]],
) -> str:
    now = datetime.now().astimezone()
    field_rows = [
        [
            str(item.get("field_name") or ""),
            str(item.get("field_id") or ""),
            type_label(item),
            "yes" if item.get("is_primary") else "",
        ]
        for item in fields
    ]
    suggestion_rows = [
        [item["target_column"], item["suggested_field"], item["match_mode"], item["rationale"]]
        for item in build_mapping_suggestions(fields)
    ]
    lines: list[str] = [
        "# TS-SYNC-02 Schema Probe Result",
        "# 自动生成，勿手动编辑",
        f"# canonical: {PROBE_RESULT_PATH}",
        f"# generated_at: {now.isoformat(timespec='seconds')}",
        f"# account_id: {account_id}",
        f"# base_token: {base_token}",
        f"# table_id: {table_id}",
        f"# table_name: {table_name}",
        f"# field_count: {len(fields)}",
        f"# sample_count: {len(records)}",
        "",
        "## 字段清单",
        markdown_table(field_rows, ["field_name", "field_id", "type", "primary"]),
        "",
        "## 前 5 条记录样本",
    ]
    if not records:
        lines.extend(["WARNING: table has 0 records", ""])
    for idx, record in enumerate(records[:5], start=1):
        lines.extend(
            [
                f"### Record {idx}",
                "```json",
                json.dumps(record, ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## 映射建议",
            markdown_table(suggestion_rows, ["target_column", "suggested_field", "match_mode", "rationale"]),
            "",
            "## 结论",
        ]
    )
    if fields:
        lines.append("PROBE OK: live schema reachable and field inventory captured.")
    else:
        lines.append("PROBE OK: schema endpoint reachable, but no fields were returned.")
    return "\n".join(lines).rstrip() + "\n"


def run_sync() -> int:
    account_id = str(os.getenv("FEISHU_BITABLE_BRIDGE_ACCOUNT_ID") or DEFAULT_ACCOUNT_ID)
    table_id = str(os.getenv("AI_DA_GUAN_JIA_FEISHU_TABLE_ID") or DEFAULT_TABLE_ID)
    pending_path = SIGNALS_DIR / "pending-tasks.md"
    try:
        creds = load_feishu_account(account_id)
        client = FeishuBitableClient(creds["app_id"], creds["app_secret"], resolve_base_token())
        all_records = client.list_records(table_id)
        filtered_rows = build_pending_rows(all_records)
        old_rows = parse_existing_pending_rows(pending_path)
        new_count = 0
        changed_count = 0
        remaining_old_rows = dict(old_rows)
        for row in filtered_rows:
            previous = remaining_old_rows.pop(row["task_id"], None)
            if previous is None:
                new_count += 1
            elif previous != row:
                changed_count += 1
        removed_count = len(remaining_old_rows)
        SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
        content = render_pending_markdown(
            filtered_rows,
            total=len(filtered_rows),
            new=new_count,
            changed=changed_count,
            removed=removed_count,
        )
        pending_path.write_text(content, encoding="utf-8")
        print(
            f"SYNC OK: total={len(filtered_rows)}, new={new_count}, changed={changed_count}, removed={removed_count}"
        )
        return 0
    except FeishuAuthError as exc:
        prepend_failure_note(pending_path, f"auth error - {exc}")
        print(f"SYNC FAILED: auth error - {exc}")
        return 2
    except ValueError as exc:
        prepend_failure_note(pending_path, str(exc))
        print(f"SYNC FAILED: {exc}")
        return 4
    except (urllib_error.URLError, TimeoutError, FeishuAPIError, RuntimeError) as exc:
        prepend_failure_note(pending_path, str(exc))
        print(f"SYNC FAILED: {exc}")
        return 1


def run_probe_only() -> int:
    account_id = str(os.getenv("FEISHU_BITABLE_BRIDGE_ACCOUNT_ID") or DEFAULT_ACCOUNT_ID)
    table_id = str(os.getenv("AI_DA_GUAN_JIA_FEISHU_TABLE_ID") or DEFAULT_TABLE_ID)
    table_name = str(os.getenv("AI_DA_GUAN_JIA_FEISHU_TABLE_NAME") or DEFAULT_TABLE_NAME)
    try:
        creds = load_feishu_account(account_id)
        client = FeishuBitableClient(creds["app_id"], creds["app_secret"], resolve_base_token())
        fields = client.list_fields(table_id)
        records = client.list_records(table_id, limit=5)
        SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
        content = render_probe_markdown(
            account_id=account_id,
            base_token=client.base_token,
            table_id=table_id,
            table_name=table_name,
            fields=fields,
            records=records,
        )
        PROBE_RESULT_PATH.write_text(content, encoding="utf-8")
        print(f"PROBE OK: schema-probe-result.md written, {len(fields)} fields found")
        return 0
    except FeishuAuthError as exc:
        print(f"PROBE FAILED: auth error - {exc}")
        return 2
    except (urllib_error.URLError, TimeoutError, FeishuAPIError, RuntimeError, ValueError) as exc:
        print(f"PROBE FAILED: {exc}")
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe the Feishu draft-signal schema.")
    parser.add_argument("--probe-only", action="store_true", help="Read schema and sample records only.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.probe_only:
        return run_sync()
    return run_probe_only()


if __name__ == "__main__":
    raise SystemExit(main())
