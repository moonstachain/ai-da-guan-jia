from __future__ import annotations

import json
import sys
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcp_server_feishu.feishu_client import FeishuClient


GOVERNANCE_WIKI_TOKEN = "Zge0wIkDDiGPsskJlLFcuT9Pnac"
LIVE_RUNTIME_APP_TOKEN = "PHp2wURl2i6SyBkDtmGcuaEenag"
LIVE_RUNTIME_TABLE_ID = "tblnRCmMS7QBMtHI"
OLD_GOVERNANCE_APP_TOKEN = "XkzJb6QDtaL21wshfUXcsn5knyg"
OLD_GOVERNANCE_RUNTIME_TABLE_ID = "tblkKkauA35yJOrH"
ARTIFACT_DIR = REPO_ROOT / "artifacts"
LATEST_AUDIT_PATH = ARTIFACT_DIR / "governance_audit.json"
CLAUDE_INIT_PATH = REPO_ROOT / "yuanli-os-claude" / "CLAUDE-INIT.md"
PRIVATE_RUNTIME_ENV_PATH = Path.home() / ".codex" / ".env"


def api(client: FeishuClient, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = client._request(method, path, body)
    if payload.get("error"):
        raise RuntimeError(str(payload["error"]))
    code = payload.get("code", 0)
    if code not in (0, "0", None):
        raise RuntimeError(json.dumps(payload, ensure_ascii=False))
    return payload


def paged_items(client: FeishuClient, path: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page_token = ""
    while True:
        query = {"page_size": 500}
        if page_token:
            query["page_token"] = page_token
        payload = api(client, "GET", f"{path}?{urlencode(query)}")
        data = payload.get("data", {}) or {}
        items.extend(list(data.get("items", []) or []))
        if not data.get("has_more"):
            break
        page_token = str(data.get("page_token", "")).strip()
        if not page_token:
            break
    return items


def discover_governance_app_token(client: FeishuClient) -> str:
    payload = api(client, "GET", f"/wiki/v2/spaces/get_node?token={GOVERNANCE_WIKI_TOKEN}")
    node = (payload.get("data", {}) or {}).get("node", {}) or {}
    obj_type = str(node.get("obj_type", "")).strip()
    if obj_type != "bitable":
        raise RuntimeError(f"expected bitable wiki node, got {obj_type or 'unknown'}")
    app_token = str(node.get("obj_token", "")).strip()
    if not app_token:
        raise RuntimeError("governance wiki node missing obj_token")
    return app_token


def list_tables(client: FeishuClient, app_token: str) -> list[dict[str, Any]]:
    return paged_items(client, f"/bitable/v1/apps/{app_token}/tables")


def list_records(client: FeishuClient, app_token: str, table_id: str) -> list[dict[str, Any]]:
    return paged_items(client, f"/bitable/v1/apps/{app_token}/tables/{table_id}/records")


def resolve_table_ids(client: FeishuClient, app_token: str) -> dict[str, str]:
    table_map: dict[str, str] = {}
    for table in list_tables(client, app_token):
        name = str(table.get("name", "")).strip()
        table_id = str(table.get("table_id", "")).strip()
        if name and table_id:
            table_map[name] = table_id
    return table_map


def safe_read(
    audit: dict[str, Any],
    client: FeishuClient,
    app_token: str,
    table_id: str | None,
    label: str,
) -> list[dict[str, Any]]:
    if not table_id:
        audit["errors"].append(f"{label}: missing table_id")
        return []
    try:
        return list_records(client, app_token, table_id)
    except Exception as exc:
        audit["errors"].append(f"{label}: {exc}")
        return []


def count_naming_traps(markdown_text: str) -> int:
    marker = "## ⚠️ 命名陷阱（防止 Claude/Codex 误判）"
    if marker not in markdown_text:
        return 0
    section = markdown_text.split(marker, 1)[1]
    if "\n---" in section:
        section = section.split("\n---", 1)[0]
    lines = [line for line in section.splitlines() if line.startswith("| ") and not line.startswith("| 错误假设")]
    return len(lines)


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    return text in {"true", "1", "yes", "y", "是"}


def parse_simple_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def ensure_runtime_feishu_env() -> dict[str, Any]:
    required = ("FEISHU_APP_ID", "FEISHU_APP_SECRET")
    env_file_values = parse_simple_env_file(PRIVATE_RUNTIME_ENV_PATH)
    loaded: list[str] = []
    existing: list[str] = []
    missing: list[str] = []
    for key in required:
        current = str(os.getenv(key, "")).strip()
        if current:
            existing.append(key)
            continue
        fallback = str(env_file_values.get(key, "")).strip()
        if fallback:
            os.environ[key] = fallback
            loaded.append(key)
        else:
            missing.append(key)
    return {
        "source": "process_env"
        if existing and not loaded
        else "process_env+private_env"
        if existing and loaded
        else "private_env"
        if loaded
        else "missing",
        "env_file_path": str(PRIVATE_RUNTIME_ENV_PATH),
        "env_file_exists": PRIVATE_RUNTIME_ENV_PATH.exists(),
        "env_file_hit": bool(loaded),
        "loaded_from_file": loaded,
        "existing_in_process": existing,
        "missing_keys": missing,
    }


def resolve_ai_da_guan_jia_runs_root() -> Path:
    candidates = [
        Path.home() / ".codex" / "skills" / "ai-da-guan-jia" / "artifacts" / "ai-da-guan-jia" / "runs",
        REPO_ROOT / "work" / "ai-da-guan-jia" / "artifacts" / "ai-da-guan-jia" / "runs",
        REPO_ROOT / "artifacts" / "ai-da-guan-jia" / "runs",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[1]


def safe_rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 2) if denominator else 0.0


def top_counter_rows(counter: Counter[str], *, limit: int = 5) -> list[dict[str, Any]]:
    return [{"pattern": key, "count": count} for key, count in counter.most_common(limit)]


def summarize_execution_engine_health(
    runs_root: Path,
    *,
    now: datetime | None = None,
    window_days: int = 7,
) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    threshold = current - timedelta(days=window_days)
    verification_counter: Counter[str] = Counter()
    feishu_counter: Counter[str] = Counter()
    github_counter: Counter[str] = Counter()
    effective_counter: Counter[str] = Counter()
    wasted_counter: Counter[str] = Counter()
    recent_runs = 0
    verified_count = 0
    feishu_apply_successes = 0
    github_apply_successes = 0
    credential_env = ensure_runtime_feishu_env()

    for evolution_path in sorted(runs_root.glob("*/*/evolution.json")):
        try:
            payload = json.loads(evolution_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        created_at = str(payload.get("created_at") or "")
        if not created_at:
            continue
        try:
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except Exception:
            continue
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created.astimezone(timezone.utc) < threshold:
            continue
        recent_runs += 1
        verification_status = str((payload.get("verification_result") or {}).get("status") or "unknown").strip() or "unknown"
        feishu_status = str(payload.get("feishu_sync_status") or "unknown").strip() or "unknown"
        github_status = str(payload.get("github_sync_status") or "unknown").strip() or "unknown"
        verification_counter[verification_status] += 1
        feishu_counter[feishu_status] += 1
        github_counter[github_status] += 1
        if verification_status.lower() in {"passed", "success", "done", "complete", "completed"}:
            verified_count += 1
        if feishu_status == "synced_applied":
            feishu_apply_successes += 1
        if github_status.endswith("_synced_applied") or github_status == "github_synced_applied":
            github_apply_successes += 1
        for item in payload.get("effective_patterns", []) or []:
            text = str(item).strip()
            if text:
                effective_counter[text] += 1
        for item in payload.get("wasted_patterns", []) or []:
            text = str(item).strip()
            if text:
                wasted_counter[text] += 1

    inferred_notes: list[str] = []
    if credential_env["missing_keys"] and feishu_counter.get("apply_blocked_missing_credentials", 0):
        inferred_notes.append("Current runtime still lacks Feishu credentials; recent Feishu apply failures may be driven by auth gaps.")

    return {
        "runs_root": str(runs_root),
        "window_days": window_days,
        "recent_runs_7d": recent_runs,
        "verification_status_distribution": dict(verification_counter),
        "feishu_sync_status_distribution": dict(feishu_counter),
        "github_sync_status_distribution": dict(github_counter),
        "verified_rate": safe_rate(verified_count, recent_runs),
        "feishu_apply_success_rate": safe_rate(feishu_apply_successes, recent_runs),
        "github_apply_success_rate": safe_rate(github_apply_successes, recent_runs),
        "top_effective_patterns": top_counter_rows(effective_counter),
        "top_wasted_patterns": top_counter_rows(wasted_counter),
        "confirmed_from_local_runs": {
            "status": "confirmed",
            "source": "local evolution.json artifacts",
        },
        "runtime_credential_context": credential_env,
        "inferred_notes": inferred_notes,
    }


def build_audit() -> dict[str, Any]:
    ensure_runtime_feishu_env()
    client = FeishuClient()
    if not client.available:
        raise SystemExit("FEISHU_APP_ID / FEISHU_APP_SECRET are required")

    now = datetime.now(timezone.utc)
    governance_app_token = discover_governance_app_token(client)
    governance_tables = resolve_table_ids(client, governance_app_token)

    audit: dict[str, Any] = {
        "audit_id": f"GOV-AUDIT-{now.strftime('%Y%m%d')}",
        "timestamp": now.isoformat(),
        "governance_app_token": governance_app_token,
        "dimensions": {},
        "errors": [],
        "table_refs": {
            "governance_tables": governance_tables,
            "live_runtime": {"app_token": LIVE_RUNTIME_APP_TOKEN, "table_id": LIVE_RUNTIME_TABLE_ID},
            "old_governance_runtime": {"app_token": OLD_GOVERNANCE_APP_TOKEN, "table_id": OLD_GOVERNANCE_RUNTIME_TABLE_ID},
        },
    }

    print("=" * 60)
    print(f"原力OS 治理成熟度全域盘点 — {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    print("\n[D1] 记忆与演化...")
    d1: dict[str, Any] = {}
    evo_records = safe_read(audit, client, governance_app_token, governance_tables.get("进化轨迹"), "D1-进化轨迹")
    chronicle_records = safe_read(
        audit, client, governance_app_token, governance_tables.get("原力OS进化编年史"), "D1-编年史"
    )
    ctrl_records = safe_read(audit, client, LIVE_RUNTIME_APP_TOKEN, LIVE_RUNTIME_TABLE_ID, "D1-总控")
    d1["evolution_total"] = len(evo_records)
    d1["evolution_completed"] = sum(1 for row in evo_records if str((row.get("fields") or {}).get("status", "")).strip() == "completed")
    d1["evolution_blocked"] = sum(1 for row in evo_records if "blocked" in str((row.get("fields") or {}).get("status", "")).lower())
    d1["evolution_failed"] = sum(1 for row in evo_records if "failed" in str((row.get("fields") or {}).get("status", "")).lower())
    gained_count = sum(
        1 for row in evo_records if boolish((row.get("fields") or {}).get("distortion_resolved") or (row.get("fields") or {}).get("gained"))
    )
    d1["gained_rate"] = round(gained_count / max(len(evo_records), 1), 2)
    d1["chronicle_milestones"] = len(chronicle_records)
    if ctrl_records:
        ctrl = ctrl_records[0].get("fields", {}) or {}
        d1["active_round"] = ctrl.get("active_round", "unknown")
        d1["total_tests"] = ctrl.get("total_tests_passed", 0)
        d1["total_commits"] = ctrl.get("total_commits", 0)
    else:
        d1["active_round"] = "unknown"
        d1["total_tests"] = 0
        d1["total_commits"] = 0
    print(
        f"  进化轨迹: {d1['evolution_total']} 条 (completed={d1['evolution_completed']}, gained_rate={d1['gained_rate']})"
    )
    print(f"  编年史: {d1['chronicle_milestones']} 条")
    print(f"  总控: round={d1['active_round']}, tests={d1['total_tests']}, commits={d1['total_commits']}")
    audit["dimensions"]["D1_记忆与演化"] = d1

    print("\n[D2] 验真与证据...")
    d2: dict[str, Any] = {
        "total_tests": d1["total_tests"],
        "total_commits": d1["total_commits"],
        "closure_completed_rate": round(d1["evolution_completed"] / max(d1["evolution_total"], 1), 2),
        "closure_blocked_rate": round(d1["evolution_blocked"] / max(d1["evolution_total"], 1), 2),
    }
    print(f"  tests={d2['total_tests']}, commits={d2['total_commits']}")
    print(
        f"  closure_completed_rate={d2['closure_completed_rate']}, blocked_rate={d2['closure_blocked_rate']}"
    )
    audit["dimensions"]["D2_验真与证据"] = d2

    print("\n[D3] 能力知晓与路由...")
    d3: dict[str, Any] = {}
    skill_records = safe_read(audit, client, governance_app_token, governance_tables.get("Skill盘点表"), "D3-Skill盘点")
    d3["skill_total"] = len(skill_records)
    quadrant_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    desc_qualified = 0
    for row in skill_records:
        fields = row.get("fields", {}) or {}
        quadrant = str(fields.get("quadrant", "unknown"))
        quadrant_counts[quadrant] = quadrant_counts.get(quadrant, 0) + 1
        category = str(fields.get("category", "unknown"))
        category_counts[category] = category_counts.get(category, 0) + 1
        status = str(fields.get("status", "unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1
        source_type = str(fields.get("source_type", "unknown"))
        source_counts[source_type] = source_counts.get(source_type, 0) + 1
        recommendation = str(fields.get("action_recommendation", ""))
        if len(recommendation) > 20 and "Use when the user explicitly" not in recommendation:
            desc_qualified += 1
    d3["quadrant_distribution"] = quadrant_counts
    d3["category_distribution"] = category_counts
    d3["status_distribution"] = status_counts
    d3["source_distribution"] = source_counts
    d3["description_qualified_rate"] = round(desc_qualified / max(d3["skill_total"], 1), 2)
    d3["core_count"] = quadrant_counts.get("核心", 0)
    d3["retire_count"] = quadrant_counts.get("淘汰", 0)
    d3["merge_count"] = quadrant_counts.get("合并", 0) + quadrant_counts.get("已合并", 0)
    d3["other_category_count"] = category_counts.get("其他", 0)
    d3["other_category_rate"] = round(d3["other_category_count"] / max(d3["skill_total"], 1), 2)
    print(
        f"  skills={d3['skill_total']}, core={d3['core_count']}, 合并={d3['merge_count']}, 淘汰={d3['retire_count']}"
    )
    print(
        f"  description合格率={d3['description_qualified_rate']}, '其他'类别占比={d3['other_category_rate']}"
    )
    audit["dimensions"]["D3_能力知晓与路由"] = d3

    print("\n[D4] 自治与边界...")
    d4: dict[str, Any] = {}
    dec_records = safe_read(audit, client, governance_app_token, governance_tables.get("决策记录"), "D4-决策记录")
    d4["decision_total"] = len(dec_records)
    d4["decision_approved"] = sum(
        1 for row in dec_records if str((row.get("fields") or {}).get("status", "")).strip() == "approved"
    )
    d4["decision_pending"] = sum(
        1 for row in dec_records if "pending" in str((row.get("fields") or {}).get("status", "")).lower()
    )
    if ctrl_records:
        ctrl = ctrl_records[0].get("fields", {}) or {}
        d4["pending_human_actions"] = ctrl.get("pending_human_actions", "N/A")
        d4["system_blockers"] = ctrl.get("system_blockers", "N/A")
        d4["runtime_state"] = ctrl.get("runtime_state", "unknown")
        d4["risk_level"] = ctrl.get("risk_level", "unknown")
    else:
        d4["pending_human_actions"] = "N/A"
        d4["system_blockers"] = "N/A"
        d4["runtime_state"] = "unknown"
        d4["risk_level"] = "unknown"
    print(
        f"  决策记录: {d4['decision_total']} 条 (approved={d4['decision_approved']}, pending={d4['decision_pending']})"
    )
    print(
        f"  pending_human={d4['pending_human_actions']}, blockers={d4['system_blockers']}, state={d4['runtime_state']}"
    )
    audit["dimensions"]["D4_自治与边界"] = d4

    print("\n[D5] 数据一致性...")
    d5: dict[str, Any] = {}
    old_ctrl = safe_read(
        audit, client, OLD_GOVERNANCE_APP_TOKEN, OLD_GOVERNANCE_RUNTIME_TABLE_ID, "D5-旧总控"
    )
    old_round = (old_ctrl[0].get("fields", {}) or {}).get("active_round", "N/A") if old_ctrl else "N/A"
    live_round = d1.get("active_round", "N/A")
    claude_init_text = CLAUDE_INIT_PATH.read_text(encoding="utf-8") if CLAUDE_INIT_PATH.exists() else ""
    d5["base_count"] = 3
    d5["active_bases"] = 2
    d5["deprecated_bases"] = 1
    d5["old_base_round"] = old_round
    d5["live_base_round"] = live_round
    d5["bases_consistent"] = old_round == live_round
    d5["naming_traps_count"] = count_naming_traps(claude_init_text)
    print(f"  旧Base: {old_round}, 新Base: {live_round}, 一致={d5['bases_consistent']}")
    print(f"  命名陷阱: {d5['naming_traps_count']} 条")
    audit["dimensions"]["D5_数据一致性"] = d5

    print("\n[D6] 业务覆盖度...")
    d6: dict[str, Any] = {}
    hm_records = safe_read(audit, client, governance_app_token, governance_tables.get("组件热图"), "D6-组件热图")
    d6["component_total"] = len(hm_records)
    maturity_counts: dict[str, int] = {}
    evidence_counts: dict[str, int] = {}
    has_execute = 0
    for row in hm_records:
        fields = row.get("fields", {}) or {}
        maturity = str(fields.get("maturity", "unknown"))
        maturity_counts[maturity] = maturity_counts.get(maturity, 0) + 1
        evidence = str(fields.get("evidence_strength", "unknown"))
        evidence_counts[evidence] = evidence_counts.get(evidence, 0) + 1
        if str(fields.get("control_level", "")).strip() == "execute":
            has_execute += 1
    d6["maturity_distribution"] = maturity_counts
    d6["evidence_distribution"] = evidence_counts
    d6["mature_count"] = maturity_counts.get("mature", 0)
    d6["weak_count"] = maturity_counts.get("weak", 0)
    d6["execute_coverage"] = has_execute
    resp_records = safe_read(audit, client, governance_app_token, governance_tables.get("组件责任"), "D6-组件责任")
    d6["responsibility_total"] = len(resp_records)
    d6["owner_gap_total"] = sum(1 for row in resp_records if boolish((row.get("fields") or {}).get("owner_gap")))
    d6["staffed_count"] = sum(
        1 for row in resp_records if str((row.get("fields") or {}).get("status", "")).strip() == "staffed"
    )
    print(f"  组件: {d6['component_total']}个, mature={d6['mature_count']}, weak={d6['weak_count']}")
    print(f"  execute层覆盖: {d6['execute_coverage']}个")
    print(f"  人力缺口: {d6['owner_gap_total']}/{d6['responsibility_total']}")
    audit["dimensions"]["D6_业务覆盖度"] = d6

    print("\n[D7] 生态与复制...")
    d7: dict[str, Any] = {}
    d7["source_distribution"] = d3["source_distribution"]
    d7["github_count"] = d3["source_distribution"].get("github", 0)
    d7["github_rate"] = round(d7["github_count"] / max(d3["skill_total"], 1), 2)
    d7["local_count"] = d3["source_distribution"].get("local_codex", 0)
    d7["mcp_count"] = d3["source_distribution"].get("mcp_tool", 0)
    d7["clawhub_published"] = False
    print(
        f"  source分布: github={d7['github_count']}, local={d7['local_count']}, mcp={d7['mcp_count']}"
    )
    print(f"  github占比: {d7['github_rate']}")
    audit["dimensions"]["D7_生态与复制"] = d7

    print("\n[D8] 执行引擎健康度...")
    runs_root = resolve_ai_da_guan_jia_runs_root()
    d8 = summarize_execution_engine_health(runs_root)
    print(f"  recent_runs_7d={d8['recent_runs_7d']}, verified_rate={d8['verified_rate']}")
    print(
        f"  feishu_apply_success_rate={d8['feishu_apply_success_rate']}, github_apply_success_rate={d8['github_apply_success_rate']}"
    )
    audit["dimensions"]["D8_执行引擎健康度"] = d8

    return audit


def main() -> int:
    audit = build_audit()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    date_path = ARTIFACT_DIR / f"governance_audit_{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"
    payload = json.dumps(audit, ensure_ascii=False, indent=2) + "\n"
    date_path.write_text(payload, encoding="utf-8")
    LATEST_AUDIT_PATH.write_text(payload, encoding="utf-8")

    print("\n" + "=" * 60)
    print(f"✅ 审计完成: {date_path}")
    print(f"✅ 最新副本: {LATEST_AUDIT_PATH}")
    print(f"   错误数: {len(audit['errors'])}")
    for error in audit["errors"]:
        print(f"   ⚠️ {error}")
    print("=" * 60)
    print("\n📋 SUMMARY（粘贴给 Claude 即可分析）:")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
