"""Migrate legacy Feishu bitable data into the dashboard tables."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .feishu_deploy import FeishuBitableAPI, required_credentials, schema_field_to_feishu_field


PACKAGE_DIR = Path(__file__).resolve().parent
ARTIFACT_DIR = PACKAGE_DIR.parent / "artifacts" / "dashboard-legacy-migration"
DOMAIN_MAPPING_PATH = PACKAGE_DIR / "domain_mapping.json"
SEED_EVOLUTION_PATH = PACKAGE_DIR / "seed" / "evolution_tracker.json"

LEGACY_MASTER_LINK = "https://h52xu4gwob.feishu.cn/wiki/C4kWwmXI8i6E6rkQ7i8cVlsyn1e"
LEGACY_LOG_LINK = "https://h52xu4gwob.feishu.cn/wiki/FwG2wbljSiQrtPkTt8RcLAbxnvd"
TARGET_LINK = "https://h52xu4gwob.feishu.cn/wiki/S29wwMHSxixwU6kG7oOc4WPznWh"

LEGACY_MASTER_TABLE_ID = "tblkS2QRSoe0On63"
LEGACY_DECISION_TABLE_ID = "tblCh3QnPMde2MNM"
LEGACY_RUN_LOG_TABLE_ID = "tblDR8XbK5fxun4x"

TARGET_TABLE_IDS = {
    "总控概览": "tblkKkauA35yJOrH",
    "组件热图": "tblBZfqAcFJzjOmd",
    "战略链路": "tblDfGetDlvYZ7iN",
    "组件责任": "tblHjuh31vwrcqG2",
    "进化轨迹": "tbl68xR3EBKy6hG5",
}

DECISION_TABLE_NAME = "决策记录"
DECISION_TABLE_FIELDS = [
    {"name": "decision_id", "type": "text"},
    {"name": "decision_type", "type": "text"},
    {"name": "summary", "type": "text"},
    {"name": "status", "type": "single_select", "options": ["approved", "pending_approval", "rejected"]},
    {"name": "rationale", "type": "text"},
    {"name": "evidence_refs", "type": "text"},
    {"name": "component_domain", "type": "single_select", "options": []},
    {"name": "control_level", "type": "single_select", "options": ["direct", "control", "execute"]},
    {"name": "created_at", "type": "datetime"},
]

STRATEGIC_STATUS_MAP = {
    "validated": "active",
    "proposed": "planned",
    "candidate_pool": "planned",
    "pending_real_round": "planned",
    "partial": "active",
    "deferred_after_narrowing": "paused",
}

HEATMAP_MATURITY_MAP = {
    "absorbed": "mature",
    "partial": "has_skeleton",
    "gap": "weak",
    "active": "has_skeleton",
    "active_with_gap": "weak",
}

RESPONSIBILITY_STATUS_MAP = {
    "active": "staffed",
    "active_with_gap": "partial",
}

EVOLUTION_STATUS_MAP = {
    "已完成": "completed",
    "待验证": "blocked_needs_user",
    "部分完成": "failed_partial",
}

PRIORITY_MAP = {
    "P1": "critical",
    "P2": "high",
}


@dataclass(frozen=True)
class LegacySnapshot:
    strategic_rows: list[dict[str, Any]]
    heatmap_rows: list[dict[str, Any]]
    responsibility_rows: list[dict[str, Any]]
    decision_rows: list[dict[str, Any]]
    run_log_rows: list[dict[str, Any]]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_domain_mapping() -> list[dict[str, Any]]:
    payload = _load_json(DOMAIN_MAPPING_PATH)
    return list(payload.get("domain_mapping") or [])


def domain_options() -> list[str]:
    return [str(item["legacy_domain"]) for item in load_domain_mapping()]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _extract_hash_id(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    tail = text.split(":")[-1]
    return tail.split("-")[-1]


def _split_levels(value: Any) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    return [part.strip() for part in re.split(r"[,/|]", text) if part.strip()]


def _first_nonempty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _owner_roles(owner_mode: Any) -> tuple[str, str]:
    normalized = str(owner_mode or "").strip().lower()
    if normalized == "human_owner":
        return "liming", ""
    if normalized in {"ai", "strategy_governor", "proposal_first"}:
        return "", "AI大管家"
    if normalized == "hybrid":
        return "liming", "AI大管家"
    return "", ""


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


def _parse_numeric(text: Any) -> int | str:
    raw = str(text or "").strip()
    match = re.search(r"\b(\d+)\b", raw)
    return int(match.group(1)) if match else ""


def _legacy_type_rows(rows: list[dict[str, Any]], object_type: str) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for row in rows:
        fields = row.get("fields") or {}
        if str(fields.get("对象类型") or "").strip() == object_type:
            filtered.append(fields)
    return filtered


def read_legacy_snapshot(api: FeishuBitableAPI) -> LegacySnapshot:
    master_app_token = api.resolve_app_token(LEGACY_MASTER_LINK)
    master_rows = api.list_records(master_app_token, LEGACY_MASTER_TABLE_ID)
    decision_rows = [item.get("fields") or {} for item in api.list_records(master_app_token, LEGACY_DECISION_TABLE_ID)]

    log_app_token = api.resolve_app_token(LEGACY_LOG_LINK)
    run_log_rows = [item.get("fields") or {} for item in api.list_records(log_app_token, LEGACY_RUN_LOG_TABLE_ID)]

    return LegacySnapshot(
        strategic_rows=_legacy_type_rows(master_rows, "strategic_linkage"),
        heatmap_rows=_legacy_type_rows(master_rows, "cbm_component_heatmap"),
        responsibility_rows=_legacy_type_rows(master_rows, "cbm_component_responsibility"),
        decision_rows=decision_rows,
        run_log_rows=run_log_rows,
    )


def transform_strategic_linkage(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in rows:
        records.append(
            {
                "goal_id": _extract_hash_id(row.get("对象Key")),
                "goal_name": _first_nonempty(row.get("对象标题")),
                "theme": "",
                "strategy": "",
                "component_domain": _first_nonempty(row.get("component_domain")),
                "control_level_scope": _split_levels(row.get("control_level")),
                "status": STRATEGIC_STATUS_MAP.get(str(row.get("对象状态") or "").strip(), "planned"),
                "current_gap": _first_nonempty(row.get("当前摘要"), row.get("阻塞原因")),
                "next_action": _first_nonempty(row.get("下一步动作"), row.get("当前摘要")),
                "evidence_ref": _first_nonempty(row.get("证据入口"), row.get("来源文件")),
            }
        )
    return records


def transform_component_heatmap(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in rows:
        human_owner, ai_copilot = _owner_roles(row.get("负责人模式"))
        records.append(
            {
                "component_domain": _first_nonempty(row.get("component_domain")),
                "control_level": _first_nonempty(*_split_levels(row.get("control_level"))),
                "maturity": HEATMAP_MATURITY_MAP.get(str(row.get("对象状态") or "").strip(), "weak"),
                "kpi_hint": _first_nonempty(row.get("当前摘要")),
                "current_gap": _first_nonempty(row.get("阻塞原因"), row.get("当前摘要")),
                "priority_band": PRIORITY_MAP.get(str(row.get("priority_band") or "").strip(), "medium"),
                "human_owner": human_owner,
                "ai_copilot": ai_copilot,
                "owner_gap": "gap" in str(row.get("对象状态") or "").strip() or bool(str(row.get("需要人类输入") or "").strip()),
                "evidence_strength": _first_nonempty(row.get("evidence_strength"), "weak"),
                "next_action": _first_nonempty(row.get("下一步动作"), row.get("当前摘要")),
                "last_updated": _to_datetime_value(row.get("最近更新时间")),
            }
        )
    return records


def transform_component_responsibility(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in rows:
        human_owner, ai_copilot = _owner_roles(row.get("负责人模式"))
        status = RESPONSIBILITY_STATUS_MAP.get(str(row.get("对象状态") or "").strip(), "partial")
        records.append(
            {
                "component_domain": _first_nonempty(row.get("component_domain")),
                "control_level": _first_nonempty(*_split_levels(row.get("control_level"))),
                "human_owner": human_owner,
                "ai_copilot": ai_copilot,
                "goal_ref": _first_nonempty(row.get("目标ID")),
                "theme_ref": "",
                "strategy_ref": "",
                "owner_gap": status != "staffed" or bool(str(row.get("需要人类输入") or "").strip()),
                "status": status,
                "evidence_ref": _first_nonempty(row.get("证据入口"), row.get("来源文件")),
            }
        )
    return records


def transform_decision_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in rows:
        records.append(
            {
                "decision_id": _first_nonempty(row.get("Decision ID"), _extract_hash_id(row.get("对象Key"))),
                "decision_type": _first_nonempty(row.get("decision_type"), "legacy_decision_record"),
                "summary": _first_nonempty(row.get("decision_summary"), row.get("当前摘要"), row.get("标题"), row.get("对象标题")),
                "status": _first_nonempty(row.get("decision_state"), row.get("对象状态")),
                "rationale": _first_nonempty(row.get("rationale"), row.get("当前摘要")),
                "evidence_refs": _first_nonempty(row.get("evidence_refs"), row.get("证据入口"), row.get("来源文件")),
                "component_domain": "",
                "control_level": "",
                "created_at": _to_datetime_value(_first_nonempty(row.get("decision_time"), row.get("最近更新时间"), row.get("更新时间"))),
            }
        )
    return records


def transform_run_logs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in rows:
        first_skill = ""
        skill_text = str(row.get("调用技能") or "").strip()
        if skill_text:
            first_skill = re.split(r"[,，]", skill_text)[0].strip()
        records.append(
            {
                "round_id": _first_nonempty(row.get("日志ID")),
                "timestamp": _to_datetime_value(_first_nonempty(row.get("时间"), row.get("记录日期"))),
                "status": EVOLUTION_STATUS_MAP.get(str(row.get("工作状态") or "").strip(), "blocked_needs_user"),
                "component_domain": "",
                "control_level": "",
                "gained": _first_nonempty(row.get("gained")),
                "wasted": _first_nonempty(row.get("wasted")),
                "next_iterate": _first_nonempty(row.get("next_iterate")),
                "capability_delta": first_skill,
                "tests_passed": _parse_numeric(row.get("验真状态")),
                "commit_hash": "",
                "distortion_resolved": str(row.get("工作状态") or "").strip() == "已完成",
            }
        )
    return records


def load_r1_to_r5_records() -> list[dict[str, Any]]:
    rows = _load_json(SEED_EVOLUTION_PATH)
    records: list[dict[str, Any]] = []
    for row in rows:
        copied = dict(row)
        copied["component_domain"] = "治理运行骨架"
        copied["control_level"] = _first_nonempty(row.get("control_level"), "control")
        copied["timestamp"] = _to_datetime_value(row.get("timestamp"))
        copied["distortion_resolved"] = bool(row.get("distortion_resolved"))
        records.append(copied)
    return records


def merge_evolution_records(run_log_rows: list[dict[str, Any]], r1_to_r5_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    combined = transform_run_logs(run_log_rows) + list(r1_to_r5_rows)
    combined.sort(key=lambda item: (str(item.get("timestamp") or ""), str(item.get("round_id") or "")))
    return combined


def build_control_overview(pending_human_actions: int) -> list[dict[str, Any]]:
    return [
        {
            "runtime_state": "healthy",
            "frontstage_focus": "R7 数据迁移 + R6c 妙搭界面",
            "active_round": "R7",
            "risk_level": "low",
            "pending_human_actions": pending_human_actions,
            "system_blockers": 0,
            "last_evolution_round": "R6b",
            "last_evolution_status": "completed",
            "total_tests_passed": 140,
            "total_commits": 7,
            "last_refresh": _to_datetime_value(_now_iso()),
        }
    ]


class DashboardLegacyMigrator:
    def __init__(self, api: FeishuBitableAPI, *, artifact_dir: Path = ARTIFACT_DIR) -> None:
        self.api = api
        self.artifact_dir = artifact_dir
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

    def _field_map(self, app_token: str, table_id: str) -> dict[str, dict[str, Any]]:
        fields = self.api.list_fields(app_token, table_id)
        return {str(field.get("field_name") or field.get("name") or ""): field for field in fields}

    def _update_field(self, app_token: str, table_id: str, field_id: str, field_name: str, field_type: int, property_payload: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {"field_name": field_name, "type": field_type}
        if property_payload is not None:
            payload["property"] = property_payload
        self.api._request(
            f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{field_id}",
            method="PUT",
            payload=payload,
        )

    def _delete_record(self, app_token: str, table_id: str, record_id: str) -> None:
        self.api._request(
            f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
            method="DELETE",
        )

    def _clear_table(self, app_token: str, table_id: str) -> int:
        records = self.api.list_records(app_token, table_id)
        for record in records:
            self._delete_record(app_token, table_id, str(record.get("record_id") or ""))
        return len(records)

    def _ensure_component_domain_options(self, app_token: str, table_id: str) -> None:
        fields = self._field_map(app_token, table_id)
        field = fields.get("component_domain")
        if not field:
            return
        self._update_field(
            app_token,
            table_id,
            str(field.get("field_id") or ""),
            "component_domain",
            int(field.get("type") or 3),
            {"options": [{"name": option} for option in domain_options()]},
        )

    def _ensure_decision_table(self, app_token: str, *, apply_changes: bool) -> str:
        for table in self.api.list_tables(app_token):
            if str(table.get("name") or table.get("table_name") or "") == DECISION_TABLE_NAME:
                return str(table.get("table_id") or "")
        if not apply_changes:
            return ""
        fields = []
        for field in DECISION_TABLE_FIELDS:
            payload = dict(schema_field_to_feishu_field(field))
            if field["name"] == "component_domain":
                payload["property"] = {"options": [{"name": option} for option in domain_options()]}
            fields.append(payload)
        created = self.api.create_table(app_token, DECISION_TABLE_NAME, fields)
        return str(created.get("table_id") or "")

    def _write_rows(self, app_token: str, table_id: str, rows: list[dict[str, Any]]) -> None:
        cleaned_rows = []
        for row in rows:
            cleaned = {}
            for key, value in row.items():
                if value == "" or value == [] or value is None:
                    continue
                cleaned[key] = value
            cleaned_rows.append(cleaned)
        for start in range(0, len(cleaned_rows), 500):
            batch = cleaned_rows[start : start + 500]
            if batch:
                self.api.batch_create_records(app_token, table_id, batch)

    def migrate(self, *, apply_changes: bool) -> dict[str, Any]:
        snapshot = read_legacy_snapshot(self.api)
        pending_human_actions = sum(1 for row in snapshot.decision_rows if str(row.get("decision_state") or "").strip() == "pending_approval")
        strategic_rows = transform_strategic_linkage(snapshot.strategic_rows)
        heatmap_rows = transform_component_heatmap(snapshot.heatmap_rows)
        responsibility_rows = transform_component_responsibility(snapshot.responsibility_rows)
        decision_rows = transform_decision_records(snapshot.decision_rows)
        evolution_rows = merge_evolution_records(snapshot.run_log_rows, load_r1_to_r5_records())
        control_overview_rows = build_control_overview(pending_human_actions)

        payloads = {
            "总控概览": control_overview_rows,
            "组件热图": heatmap_rows,
            "战略链路": strategic_rows,
            "组件责任": responsibility_rows,
            "进化轨迹": evolution_rows,
        }
        plan = {
            "总控概览": len(control_overview_rows),
            "组件热图": len(heatmap_rows),
            "战略链路": len(strategic_rows),
            "组件责任": len(responsibility_rows),
            "进化轨迹": len(evolution_rows),
            DECISION_TABLE_NAME: len(decision_rows),
        }

        target_app_token = self.api.resolve_app_token(TARGET_LINK)
        decision_table_id = self._ensure_decision_table(target_app_token, apply_changes=apply_changes)

        if not apply_changes:
            result = {
                "mode": "dry-run",
                "target_app_token": target_app_token,
                "plan": plan,
                "decision_table_id": decision_table_id or "(will_create_on_apply)",
                "domain_mapping": load_domain_mapping(),
            }
        else:
            cleared_counts: dict[str, int] = {}
            for table_name, table_id in TARGET_TABLE_IDS.items():
                cleared_counts[table_name] = self._clear_table(target_app_token, table_id)
            cleared_counts[DECISION_TABLE_NAME] = self._clear_table(target_app_token, decision_table_id)

            for table_name in ["组件热图", "战略链路", "组件责任", "进化轨迹"]:
                self._ensure_component_domain_options(target_app_token, TARGET_TABLE_IDS[table_name])
            self._ensure_component_domain_options(target_app_token, decision_table_id)

            for table_name, rows in payloads.items():
                self._write_rows(target_app_token, TARGET_TABLE_IDS[table_name], rows)
            self._write_rows(target_app_token, decision_table_id, decision_rows)

            readback = {}
            for table_name, table_id in TARGET_TABLE_IDS.items():
                readback[table_name] = len(self.api.list_records(target_app_token, table_id))
            readback[DECISION_TABLE_NAME] = len(self.api.list_records(target_app_token, decision_table_id))

            result = {
                "mode": "apply",
                "target_app_token": target_app_token,
                "cleared_counts": cleared_counts,
                "readback": readback,
                "plan": plan,
                "decision_table_id": decision_table_id,
                "domain_mapping": load_domain_mapping(),
            }

        artifact_path = self.artifact_dir / f"dashboard-legacy-migration-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        artifact_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result["artifact_path"] = str(artifact_path)
        return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate legacy Feishu dashboard data.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    app_id, app_secret = required_credentials()
    api = FeishuBitableAPI(app_id, app_secret)
    migrator = DashboardLegacyMigrator(api)
    result = migrator.migrate(apply_changes=bool(args.apply or not args.dry_run))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
