"""Core pipeline for the Yuanli governance system."""

from __future__ import annotations

import importlib.util
import csv
import html as html_lib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
from hashlib import sha1
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from .contracts import (
    AGENT_SKILL_HINTS,
    CLUSTER_DEFAULTS,
    DASHBOARD_QUESTIONS,
    DEFAULT_ACCOUNT_SPECS,
    DEFAULT_AGENT_SPECS,
    DEFAULT_ENDPOINT_SPECS,
    DEFAULT_SUBJECT_SPECS,
    ENTITY_FILES,
    FEDERATION_SPACE_SPECS,
    FEISHU_TABLE_SPECS,
    FIXED_RELATION_TYPES,
    LOCAL_TIMEZONE,
    MORNING_REVIEW_SECTIONS,
    OPERATING_MODULE_SPECS,
    PROJECT_ROOT,
)

try:
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None


TIMEZONE = ZoneInfo(LOCAL_TIMEZONE)
CANONICAL_ROOT = PROJECT_ROOT / "canonical"
DERIVED_ROOT = PROJECT_ROOT / "derived"
SPECS_ROOT = PROJECT_ROOT / "specs"
CODEX_HOME = Path(os.getenv("CODEX_HOME", str(Path.home() / ".codex"))).expanduser().resolve()
DEFAULT_FEISHU_INGEST_ROOT = PROJECT_ROOT / "output" / "feishu-reader"
DEFAULT_TENCENT_MEETING_INGEST_ROOT = PROJECT_ROOT / "output" / "tencent-meeting"
KNOWLEDGE_SOURCE_ALLOWED_STATUSES = {
    "validated",
    "auth_required",
    "access_denied",
    "not_found",
    "empty_extraction",
    "blocked_runtime_missing",
}
KNOWLEDGE_ITEM_ALLOWED_LAYERS = {
    "治理层",
    "规则层",
    "线程层",
    "资产层",
    "交付层",
}
KNOWLEDGE_ITEM_ALLOWED_SYNC_TIERS = {"core", "candidate", "ignore"}
KNOWLEDGE_ITEM_ALLOWED_STATUSES = {"active", "pending_review", "archived"}
TENCENT_MEETING_CAPTURE_ALLOWED_STATUSES = {"accessible", "gated", "expired", "failed"}
TENCENT_MEETING_TRANSCRIPT_ALLOWED_STATUSES = {"present", "empty", "unknown"}
TENCENT_MEETING_NATIVE_TRANSCRIPT_CAPABILITY_ALLOWED_STATUSES = {"supported", "unsupported", "unknown"}
TENCENT_MEETING_NATIVE_TRANSCRIPT_ENABLED_ALLOWED_STATUSES = {"enabled", "disabled", "unknown"}
TENCENT_MEETING_SHARE_PAGE_TRANSCRIPT_VISIBLE_ALLOWED_STATUSES = {"visible", "hidden", "gated", "unknown"}
TENCENT_MEETING_TRANSCRIPT_ACCESS_PATH_ALLOWED_STATUSES = {"share_page", "login_probe", "open_api", "external_transcribe"}
OPERATIONAL_CAPABILITY_DEFAULTS = [
    {
        "capability_id": "capability-skill-review-proposal",
        "title": "技能治理评审提案",
        "actor_type": "ai_agent",
        "allowed_action_ids": ["review-skill"],
        "bound_policy_ids": ["policy-read-governance", "policy-propose-skill-review"],
        "requires_human_approval": False,
    },
    {
        "capability_id": "capability-review-resolution-draft",
        "title": "技能治理决议草拟",
        "actor_type": "ai_agent",
        "allowed_action_ids": ["resolve-action"],
        "bound_policy_ids": ["policy-read-governance", "policy-resolve-review-action"],
        "requires_human_approval": True,
    },
    {
        "capability_id": "capability-report-publication",
        "title": "治理报告发布执行",
        "actor_type": "automation",
        "allowed_action_ids": ["publish-governance-report"],
        "bound_policy_ids": ["policy-read-governance", "policy-publish-derived-report"],
        "requires_human_approval": True,
    },
]


def now_local() -> datetime:
    return datetime.now(TIMEZONE)


def iso_now() -> str:
    return now_local().isoformat(timespec="seconds")


def read_json(path: Path, *, default: Any = None) -> Any:
    if not path.exists():
        return deepcopy(default)
    return json.loads(path.read_text(encoding="utf-8"))


def load_toml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if tomllib is not None:
        return tomllib.loads(text)
    return parse_basic_toml(text)


def parse_basic_toml(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith('"') and value.endswith('"'):
            result[key] = value[1:-1]
        elif value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if not inner:
                result[key] = []
            else:
                result[key] = [item.strip().strip('"') for item in inner.split(",")]
        elif value.isdigit():
            result[key] = int(value)
        else:
            result[key] = value.strip('"')
    return result


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "-", lowered)
    lowered = re.sub(r"-{2,}", "-", lowered)
    return lowered.strip("-") or "item"


def stable_id(prefix: str, *parts: str) -> str:
    basis = "||".join(part for part in parts if part)
    digest = sha1(basis.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{digest}"


def normalize_external_url(raw_url: str) -> str:
    parsed = urlsplit(raw_url.strip())
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def canonicalize_knowledge_source_url(raw_url: str) -> str:
    normalized = normalize_external_url(raw_url)
    parsed = urlsplit(normalized)
    host = parsed.netloc.lower()
    if "feishu.cn" in host or "larksuite.com" in host:
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    return normalized


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def source_scope_file(scope_path: Path | None = None) -> Path:
    return (scope_path or (SPECS_ROOT / "source-scope.json")).expanduser().resolve()


def coerce_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def ensure_scope_defaults(scope: dict[str, Any]) -> dict[str, Any]:
    payload = dict(scope)
    payload.setdefault("sync_hub_root", str(PROJECT_ROOT / "sync-hub"))
    payload["sync_hub_roots"] = unique_strings(
        coerce_string_list(payload.get("sync_hub_roots")) + coerce_string_list(payload.get("sync_hub_root"))
    )
    payload["business_finance_roots"] = unique_strings(
        coerce_string_list(payload.get("business_finance_roots"))
    )
    payload["content_knowledge_roots"] = unique_strings(
        coerce_string_list(payload.get("content_knowledge_roots"))
    )
    payload["governance_roots"] = unique_strings(
        coerce_string_list(payload.get("governance_roots"))
    )
    legacy_governance = [
        "skills_root",
        "automations_root",
        "strategy_root",
        "reviews_root",
        "review_state_path",
        "strategic_goals_path",
        "active_threads_path",
        "governance_dashboard_path",
        "routing_credit_path",
        "org_taxonomy_path",
        "ontology_path",
        "daily_review_automation_path",
        "latest_review_path",
        "latest_skill_scout_path",
        "feishu_ingest_root",
        "tencent_meeting_ingest_root",
    ]
    payload["governance_roots"] = unique_strings(
        payload["governance_roots"] + [str(payload.get(key, "")).strip() for key in legacy_governance if str(payload.get(key, "")).strip()]
    )
    source_links = payload.get("source_feishu_links", [])
    if not isinstance(source_links, list):
        source_links = [str(source_links)]
    payload["source_feishu_links"] = unique_strings([normalize_external_url(str(item)) for item in source_links if str(item).strip()])
    tencent_links = payload.get("source_tencent_meeting_links", [])
    if not isinstance(tencent_links, list):
        tencent_links = [str(tencent_links)]
    payload["source_tencent_meeting_links"] = unique_strings(
        [
            normalize_tencent_meeting_share_url(str(item))[0]
            for item in tencent_links
            if str(item).strip()
        ]
    )
    payload.setdefault("source_registry_version", "v1")
    payload.setdefault("source_registry_groups", ["sync_hub_roots", "business_finance_roots", "content_knowledge_roots", "governance_roots"])
    payload.setdefault("feishu_ingest_root", str(DEFAULT_FEISHU_INGEST_ROOT))
    payload.setdefault("tencent_meeting_ingest_root", str(DEFAULT_TENCENT_MEETING_INGEST_ROOT))
    return payload


def load_source_scope(path: Path | None = None) -> dict[str, Any]:
    scope_path = source_scope_file(path)
    scope = read_json(scope_path)
    if scope.get("reviews_root"):
        review_files = sorted(Path(scope["reviews_root"]).glob("**/review.json"))
        if review_files:
            scope["latest_review_path"] = str(review_files[-1])
    if scope.get("skill_scout_root"):
        scout_files = sorted(Path(scope["skill_scout_root"]).glob("**/briefing.json"))
        if scout_files:
            scope["latest_skill_scout_path"] = str(scout_files[-1])
    return ensure_scope_defaults(scope)


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if not match:
        return {}
    result: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def parse_org_taxonomy(path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    if not path.exists():
        return mapping
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^- ([^:]+): (.+)$", line.strip())
        if not match:
            continue
        cluster = match.group(1).strip()
        skills = [item.strip() for item in match.group(2).split("|")]
        for skill in skills:
            if skill:
                mapping[skill] = cluster
    return mapping


def load_core_profiles(script_path: Path) -> dict[str, dict[str, Any]]:
    if not script_path.exists():
        return {}
    spec = importlib.util.spec_from_file_location("ai_da_guan_jia_router", script_path)
    if spec is None or spec.loader is None:
        return {}
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        return {}
    profiles = getattr(module, "CORE_PROFILES", {})
    result: dict[str, dict[str, Any]] = {}
    for key, profile in profiles.items():
        payload = asdict(profile)
        result[key] = payload
    return result


def load_routing_credit(path: Path) -> dict[str, float]:
    mapping: dict[str, float] = {}
    for item in read_json(path, default=[]):
        skill = str(item.get("skill", "")).strip()
        if skill:
            mapping[skill] = float(item.get("routing_credit", 0))
    return mapping


def load_goal_priority(path: Path) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for item in read_json(path, default=[]):
        goal_id = str(item.get("id", "")).strip()
        if goal_id:
            mapping[goal_id] = int(item.get("priority", 99))
    return mapping


def priority_label(priority: int | None) -> str:
    if priority == 1:
        return "P1"
    if priority == 2:
        return "P2"
    if priority == 3:
        return "P3"
    return "P4"


def skill_defaults_for_cluster(cluster: str) -> dict[str, int]:
    return deepcopy(CLUSTER_DEFAULTS.get(cluster, CLUSTER_DEFAULTS["未分组"]))


def list_skill_dirs(skills_root: Path) -> list[Path]:
    if not skills_root.exists():
        return []
    return sorted({manifest.parent for manifest in skills_root.glob("**/SKILL.md")})


def build_relation(
    from_type: str,
    from_id: str,
    relation_type: str,
    to_type: str,
    to_id: str,
    evidence_ref: str,
) -> dict[str, Any]:
    relation_id = stable_id("rel", from_id, to_id, relation_type)
    return {
        "id": relation_id,
        "relation_id": relation_id,
        "from_type": from_type,
        "from_id": from_id,
        "relation_type": relation_type,
        "to_type": to_type,
        "to_id": to_id,
        "evidence_ref": evidence_ref,
        "updated_at": iso_now(),
    }


def with_runtime_fields(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for item in items:
        payload = dict(item)
        payload["updated_at"] = iso_now()
        enriched.append(payload)
    return enriched


def find_asset_id(assets: list[dict[str, Any]], *patterns: str) -> str:
    lowered_patterns = [pattern.lower() for pattern in patterns if pattern]
    for asset in assets:
        haystack = " ".join(
            [
                str(asset.get("title", "")),
                str(asset.get("source_path", "")),
                str(asset.get("source_ref", "")),
                str(asset.get("asset_type", "")),
            ]
        ).lower()
        if all(pattern in haystack for pattern in lowered_patterns):
            return str(asset["asset_id"])
    return ""


def path_matches_tokens(path: Path, tokens: list[str]) -> bool:
    haystack = str(path).lower()
    return any(token in haystack for token in tokens)


def infer_registry_group(path: Path, scope: dict[str, Any]) -> str:
    normalized = str(path)
    for group in ["sync_hub_roots", "business_finance_roots", "content_knowledge_roots", "governance_roots"]:
        for root in scope.get(group, []):
            if normalized.startswith(str(Path(root).expanduser())):
                return group
    return "governance_roots"


def infer_origin_device(path: Path, scope: dict[str, Any]) -> str:
    normalized = str(path)
    sync_hubs = [str(Path(root).expanduser()) for root in scope.get("sync_hub_roots", [])]
    for root in sync_hubs:
        if normalized.startswith(root):
            relative = Path(normalized).relative_to(Path(root))
            parts = relative.parts
            if parts:
                return parts[0]
    if normalized.startswith(str(Path.home())):
        return "current-mac"
    if normalized.startswith("/Volumes/"):
        volume = Path(normalized).parts[2] if len(Path(normalized).parts) > 2 else "mounted-volume"
        return f"volume-{slugify(volume)}"
    return "external-source"


def file_checksum(path: Path) -> str:
    stat = path.stat()
    digest = sha1()
    digest.update(str(stat.st_size).encode("utf-8"))
    if stat.st_size <= 1024 * 1024:
        digest.update(path.read_bytes())
    else:
        with path.open("rb") as handle:
            digest.update(handle.read(512 * 1024))
    return digest.hexdigest()


def iter_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    if root.is_file():
        return [root]
    result: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part.startswith(".") for part in path.parts if part not in {".", ".."}):
            continue
        if "__pycache__" in path.parts:
            continue
        result.append(path)
    return sorted(result)


def classify_source_file(path: Path, scope: dict[str, Any]) -> dict[str, str]:
    suffix = path.suffix.lower()
    name = path.name.lower()
    registry_group = infer_registry_group(path, scope)
    if path_matches_tokens(path, ["order-facts", "订单", "orders", "consulting-first-batch-orders"]):
        return {
            "source_family": "order_facts",
            "content_class": "business_fact",
            "module_code": "sales",
            "owner_account_id": "",
            "registry_group": registry_group,
            "parse_status": "ready" if suffix in {".json", ".csv", ".tsv"} else "needs_export",
        }
    if path_matches_tokens(path, ["cashflow", "ledger", "流水", "收支", "对账"]):
        return {
            "source_family": "cashflow_ledger",
            "content_class": "finance_fact",
            "module_code": "finance",
            "owner_account_id": "",
            "registry_group": registry_group,
            "parse_status": "ready" if suffix in {".json", ".csv", ".tsv"} else "needs_export",
        }
    if path_matches_tokens(path, ["wechat", "公众号"]):
        return {
            "source_family": "wechat_content",
            "content_class": "article_asset" if suffix in {".md", ".txt", ".json"} else "content_artifact",
            "module_code": "public",
            "owner_account_id": "account-wechat",
            "registry_group": registry_group,
            "parse_status": "ready" if suffix in {".json", ".md", ".txt"} else "indexed_only",
        }
    if path_matches_tokens(path, ["xiaohongshu", "小红书"]):
        return {
            "source_family": "xiaohongshu_content",
            "content_class": "social_asset",
            "module_code": "public",
            "owner_account_id": "account-xiaohongshu",
            "registry_group": registry_group,
            "parse_status": "indexed_only",
        }
    if path_matches_tokens(path, ["douyin", "抖音"]):
        return {
            "source_family": "douyin_content",
            "content_class": "social_asset",
            "module_code": "public",
            "owner_account_id": "account-douyin",
            "registry_group": registry_group,
            "parse_status": "indexed_only",
        }
    if path_matches_tokens(path, ["视频号", "video-channel", "video_channel"]):
        return {
            "source_family": "video_channel_content",
            "content_class": "social_asset",
            "module_code": "public",
            "owner_account_id": "account-video-channel",
            "registry_group": registry_group,
            "parse_status": "indexed_only",
        }
    if suffix in {".pdf", ".ppt", ".pptx", ".doc", ".docx"} and path_matches_tokens(path, ["课程", "研习", "直播资料", "混沌课程", "课", "training"]):
        return {
            "source_family": "course_material",
            "content_class": "course_material",
            "module_code": "delivery",
            "owner_account_id": "",
            "registry_group": registry_group,
            "parse_status": "indexed_only",
        }
    if suffix in {".md", ".pdf", ".txt", ".doc", ".docx"} and registry_group == "content_knowledge_roots":
        return {
            "source_family": "knowledge_document",
            "content_class": "knowledge_document",
            "module_code": "delivery",
            "owner_account_id": "",
            "registry_group": registry_group,
            "parse_status": "indexed_only",
        }
    if suffix == ".json" and registry_group == "sync_hub_roots":
        return {
            "source_family": "sync_manifest",
            "content_class": "sync_manifest",
            "module_code": "governance",
            "owner_account_id": "",
            "registry_group": registry_group,
            "parse_status": "ready",
        }
    if registry_group == "governance_roots" or name in {"skill.md", "automation.toml"}:
        return {
            "source_family": "governance_artifact",
            "content_class": "governance_artifact",
            "module_code": "governance",
            "owner_account_id": "",
            "registry_group": registry_group,
            "parse_status": "indexed_only",
        }
    return {
        "source_family": "unclassified",
        "content_class": "unclassified",
        "module_code": "governance",
        "owner_account_id": "",
        "registry_group": registry_group,
        "parse_status": "unclassified",
    }


def sensitivity_level_for_path(path: Path, family: str) -> str:
    if family in {"order_facts", "cashflow_ledger"}:
        return "restricted"
    if family in {"wechat_content", "xiaohongshu_content", "douyin_content", "video_channel_content"}:
        return "internal"
    if path.suffix.lower() in {".db", ".xlsx", ".csv", ".tsv"}:
        return "internal"
    return "low"


def build_file_asset(path: Path, classification: dict[str, str], scope: dict[str, Any]) -> dict[str, Any]:
    checksum = file_checksum(path)
    return {
        "id": stable_id("asset", str(path)),
        "asset_id": stable_id("asset", str(path)),
        "title": path.stem,
        "asset_type": "source_file",
        "domain": classification["registry_group"],
        "source_path": str(path),
        "source_kind": "file",
        "source_ref": str(path),
        "content_class": classification["content_class"],
        "source_family": classification["source_family"],
        "module_code": classification["module_code"],
        "owner_account_id": classification["owner_account_id"],
        "origin_device": infer_origin_device(path, scope),
        "sensitivity_level": sensitivity_level_for_path(path, classification["source_family"]),
        "checksum": checksum,
        "parse_status": classification["parse_status"],
        "status": "active",
        "owner_mode": "hybrid",
        "confidence": 0.88 if classification["source_family"] != "unclassified" else 0.6,
        "last_seen_at": iso_now(),
        "updated_at": iso_now(),
    }


def read_tabular_records(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = read_json(path, default=[])
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for value in payload.values():
                if isinstance(value, list) and all(isinstance(item, dict) for item in value):
                    return value
        return []
    if suffix in {".csv", ".tsv"}:
        delimiter = "," if suffix == ".csv" else "\t"
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle, delimiter=delimiter)]
    return []


def first_non_empty(record: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = str(record.get(key, "")).strip()
        if value:
            return value
    return ""


def coerce_float(value: Any) -> float:
    text = str(value).strip().replace(",", "")
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def map_order_record(record: dict[str, Any], *, path: Path, source_feed_id: str, classification: dict[str, str]) -> dict[str, Any]:
    order_date = first_non_empty(record, ["订单日期", "日期", "报名日期", "支付日期"])
    order_id = first_non_empty(record, ["订单ID", "订单号"])
    customer_name = first_non_empty(record, ["客户名称", "姓名", "客户", "昵称"])
    amount = coerce_float(first_non_empty(record, ["支付金额", "金额", "实付金额"]))
    if not order_id:
        order_id = stable_id("ord", str(path), order_date, customer_name, f"{amount:.2f}")
    return {
        "id": order_id,
        "order_id": order_id,
        "order_date": order_date,
        "payment_amount": amount,
        "payment_platform": first_non_empty(record, ["支付平台", "平台"]),
        "order_source": first_non_empty(record, ["订单来源", "来源"]),
        "customer_name": customer_name,
        "customer_phone": first_non_empty(record, ["手机号", "支付手机号", "手机"]),
        "service_line": first_non_empty(record, ["服务线"]),
        "lead_owner": first_non_empty(record, ["流量归属"]),
        "primary_conversion_owner": first_non_empty(record, ["主转化归属"]),
        "secondary_conversion_owner": first_non_empty(record, ["次转化归属"]),
        "opportunity_id": first_non_empty(record, ["关联机会"]),
        "note": first_non_empty(record, ["成单备注"]),
        "card_note": first_non_empty(record, ["名片备注"]),
        "source_feed_id": source_feed_id,
        "source_path": str(path),
        "source_family": classification["source_family"],
        "module_code": classification["module_code"],
        "sensitivity_level": "restricted",
        "parse_status": "parsed",
        "source_ref": str(path),
        "confidence": 0.9,
        "updated_at": iso_now(),
    }


def map_cashflow_record(record: dict[str, Any], *, path: Path, source_feed_id: str, classification: dict[str, str]) -> dict[str, Any]:
    transaction_date = first_non_empty(record, ["发生日期", "交易日期", "日期"])
    amount = coerce_float(first_non_empty(record, ["金额", "收入金额", "支出金额", "支付金额"]))
    direction = first_non_empty(record, ["方向", "收支方向"])
    if not direction:
        direction = "inflow" if amount >= 0 else "outflow"
    transaction_id = first_non_empty(record, ["流水ID", "交易流水号", "单号"])
    if not transaction_id:
        transaction_id = stable_id("cf", str(path), transaction_date, first_non_empty(record, ["对手方", "摘要"]), f"{amount:.2f}")
    return {
        "id": transaction_id,
        "cashflow_id": transaction_id,
        "transaction_date": transaction_date,
        "amount": amount,
        "direction": direction,
        "account_name": first_non_empty(record, ["账户", "账户名称", "付款账户"]),
        "counterparty": first_non_empty(record, ["对手方", "交易对方"]),
        "summary": first_non_empty(record, ["摘要", "备注", "说明"]),
        "source_feed_id": source_feed_id,
        "source_path": str(path),
        "source_family": classification["source_family"],
        "module_code": classification["module_code"],
        "sensitivity_level": "restricted",
        "parse_status": "parsed",
        "source_ref": str(path),
        "confidence": 0.9,
        "updated_at": iso_now(),
    }


def scan_source_registry(scope: dict[str, Any]) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for group in scope.get("source_registry_groups", []):
        for root_value in scope.get(group, []):
            root = Path(root_value).expanduser()
            for path in iter_files(root):
                normalized = str(path.resolve())
                if normalized in seen_paths:
                    continue
                seen_paths.add(normalized)
                classification = classify_source_file(path, scope)
                files.append(
                    {
                        "path": path.resolve(),
                        "classification": classification,
                    }
                )
    feed_groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in files:
        classification = item["classification"]
        key = (classification["registry_group"], classification["source_family"])
        feed_groups.setdefault(key, []).append(item)

    source_feeds: list[dict[str, Any]] = []
    for (registry_group, source_family), items in sorted(feed_groups.items()):
        sample_path = items[0]["path"]
        feed_id = stable_id("feed", registry_group, source_family, str(sample_path.parent))
        owner_account_id = next((it["classification"]["owner_account_id"] for it in items if it["classification"]["owner_account_id"]), "")
        unclassified_count = sum(1 for it in items if it["classification"]["source_family"] == "unclassified")
        source_feeds.append(
            {
                "id": feed_id,
                "source_feed_id": feed_id,
                "title": f"{source_family}::{sample_path.parent.name}",
                "source_family": source_family,
                "registry_group": registry_group,
                "root_path": str(sample_path.parent),
                "origin_device": infer_origin_device(sample_path, scope),
                "owner_account_id": owner_account_id,
                "status": "active" if source_family != "unclassified" else "needs_classification",
                "recognized_file_count": sum(1 for it in items if it["classification"]["source_family"] != "unclassified"),
                "unclassified_file_count": unclassified_count,
                "last_scanned_at": iso_now(),
                "source_ref": str(sample_path.parent),
                "confidence": 0.88 if source_family != "unclassified" else 0.6,
                "updated_at": iso_now(),
            }
        )
    return {"files": files, "source_feeds": source_feeds}


def feed_id_for_file(path: Path, source_feeds: list[dict[str, Any]], classification: dict[str, str]) -> str:
    for feed in source_feeds:
        if feed["source_family"] != classification["source_family"]:
            continue
        if str(path).startswith(str(feed["root_path"])):
            return str(feed["source_feed_id"])
    return stable_id("feed", classification["registry_group"], classification["source_family"], str(path.parent))


def build_ingested_entities(scope: dict[str, Any]) -> dict[str, Any]:
    registry = scan_source_registry(scope)
    source_feeds = registry["source_feeds"]
    files = registry["files"]
    assets: list[dict[str, Any]] = []
    orders: list[dict[str, Any]] = []
    cashflows: list[dict[str, Any]] = []
    unclassified_paths: list[str] = []

    for item in files:
        path = item["path"]
        classification = item["classification"]
        if classification["source_family"] == "governance_artifact":
            continue
        assets.append(build_file_asset(path, classification, scope))
        if classification["source_family"] == "unclassified":
            unclassified_paths.append(str(path))
        feed_id = feed_id_for_file(path, source_feeds, classification)
        if classification["source_family"] == "order_facts":
            for record in read_tabular_records(path):
                orders.append(map_order_record(record, path=path, source_feed_id=feed_id, classification=classification))
        elif classification["source_family"] == "cashflow_ledger":
            for record in read_tabular_records(path):
                cashflows.append(map_cashflow_record(record, path=path, source_feed_id=feed_id, classification=classification))

    orders = dedupe_by_key(orders, "order_id")
    cashflows = dedupe_by_key(cashflows, "cashflow_id")
    ingestion_run_id = f"ingest-{now_local().strftime('%Y%m%d-%H%M%S')}"
    ingestion_runs = [
        {
            "id": ingestion_run_id,
            "ingestion_run_id": ingestion_run_id,
            "run_type": "full_inventory",
            "status": "completed",
            "scanned_file_count": len(files),
            "recognized_file_count": sum(1 for item in files if item["classification"]["source_family"] != "unclassified"),
            "source_feed_count": len(source_feeds),
            "order_count": len(orders),
            "cashflow_count": len(cashflows),
            "content_asset_count": sum(
                1 for item in assets if item.get("content_class") in {"course_material", "knowledge_document", "article_asset", "social_asset", "content_artifact"}
            ),
            "unclassified_file_count": len(unclassified_paths),
            "unclassified_paths": unclassified_paths[:50],
            "sensitivity_check_status": "pending",
            "source_ref": "registry://full_inventory",
            "confidence": 0.9,
            "updated_at": iso_now(),
        }
    ]
    return {
        "source_feeds": source_feeds,
        "ingestion_runs": ingestion_runs,
        "assets": assets,
        "orders": orders,
        "cashflows": cashflows,
    }


def reconcile_accounts_with_source_feeds(accounts: list[dict[str, Any]], source_feeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    observed_accounts = {
        str(feed.get("owner_account_id", ""))
        for feed in source_feeds
        if str(feed.get("owner_account_id", "")).strip() and int(feed.get("recognized_file_count", 0)) > 0
    }
    updated: list[dict[str, Any]] = []
    for account in accounts:
        payload = dict(account)
        if payload["account_id"] in observed_accounts:
            payload["health_status"] = "inventory_observed"
            if payload.get("status") == "planned":
                payload["status"] = "active"
        updated.append(payload)
    return updated

def infer_space_id(title: str) -> str:
    lowered = title.lower()
    if "下游" in title or "客户的客户" in title or "downstream" in lowered:
        return "space-downstream-template"
    if "客户" in title or "client" in lowered:
        return "space-client-template"
    if "同事" in title or "合伙" in title or "内部" in title or "公司" in title:
        return "space-internal-team"
    return "space-personal-zero"


def infer_module_code(title: str, selected_skills: list[str]) -> str:
    lowered = title.lower()
    skill_blob = " ".join(skill.lower() for skill in selected_skills)
    if any(token in title for token in ["财务", "回款", "利润"]) or "finance" in lowered:
        return "finance"
    if any(token in title for token in ["交付", "课程", "服务", "履约"]) or "delivery" in lowered:
        return "delivery"
    if any(token in title for token in ["销售", "成交", "报价", "商机"]) or "sales" in lowered:
        return "sales"
    if any(token in title for token in ["私域", "转化", "社群"]) or "private" in lowered:
        return "private"
    if any(token in title for token in ["公域", "内容", "视频号", "小红书", "抖音", "b站"]) or any(
        token in skill_blob for token in ["openclaw", "xiaohongshu", "yuanli-xiaoshitou"]
    ):
        return "public"
    return "governance"


def module_id_from_code(module_code: str) -> str:
    return f"module-{module_code}"


def subject_id_for_module_owner(module_code: str) -> str:
    if module_code in {"sales", "delivery", "finance"}:
        return "subject-collab-owner"
    return "subject-hay2045"


def build_skill_entities(
    scope: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    skills_root = Path(scope["skills_root"])
    taxonomy = parse_org_taxonomy(Path(scope["org_taxonomy_path"]))
    core_profiles = load_core_profiles(Path(scope["ai_da_guan_jia_script"]))
    routing_credit = load_routing_credit(Path(scope["routing_credit_path"]))
    entities: list[dict[str, Any]] = []
    assets: list[dict[str, Any]] = []
    for skill_dir in list_skill_dirs(skills_root):
        manifest = skill_dir / "SKILL.md"
        frontmatter = parse_frontmatter(manifest)
        name = frontmatter.get("name") or skill_dir.name
        cluster = taxonomy.get(name, "未分组")
        defaults = skill_defaults_for_cluster(cluster)
        profile = core_profiles.get(name, {})
        description = frontmatter.get("description", "")
        status = "active"
        skill_id = name
        entities.append(
            {
                "id": skill_id,
                "skill_id": skill_id,
                "name": name,
                "title": name,
                "cluster": cluster,
                "role": profile.get("role") or description,
                "verification_strength": int(profile.get("verification_strength", defaults["verification_strength"])),
                "cost_efficiency": int(profile.get("cost_efficiency", defaults["cost_efficiency"])),
                "auth_reuse": int(profile.get("auth_reuse", defaults["auth_reuse"])),
                "complexity_penalty": int(profile.get("complexity_penalty", defaults["complexity_penalty"])),
                "routing_credit": round(routing_credit.get(name, 0.0), 1),
                "status": status,
                "source_ref": str(manifest),
                "confidence": 0.95,
                "updated_at": iso_now(),
            }
        )
        assets.append(
            {
                "id": stable_id("asset", str(manifest)),
                "asset_id": stable_id("asset", str(manifest)),
                "title": name,
                "asset_type": "skill_manifest",
                "domain": cluster,
                "source_path": str(manifest),
                "source_kind": "skill",
                "source_ref": str(manifest),
                "status": status,
                "owner_mode": "ai",
                "confidence": 0.95,
                "last_seen_at": iso_now(),
                "updated_at": iso_now(),
            }
        )
    return entities, assets


def build_automation_assets(scope: dict[str, str]) -> list[dict[str, Any]]:
    automations_root = Path(scope["automations_root"])
    assets: list[dict[str, Any]] = []
    if not automations_root.exists():
        return assets
    for automation_dir in sorted(path for path in automations_root.iterdir() if path.is_dir()):
        toml_path = automation_dir / "automation.toml"
        if not toml_path.exists():
            continue
        data = load_toml(toml_path)
        asset_id = stable_id("asset", str(toml_path))
        assets.append(
            {
                "id": asset_id,
                "asset_id": asset_id,
                "title": data.get("name") or automation_dir.name,
                "asset_type": "automation_manifest",
                "domain": "automation",
                "source_path": str(toml_path),
                "source_kind": "automation",
                "source_ref": str(toml_path),
                "status": str(data.get("status", "ACTIVE")).lower(),
                "owner_mode": "ai",
                "confidence": 0.95,
                "last_seen_at": iso_now(),
                "updated_at": iso_now(),
            }
        )
    return assets


def build_strategy_assets(scope: dict[str, str]) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    strategy_paths = [
        Path(scope["strategic_goals_path"]),
        Path(scope["active_threads_path"]),
        Path(scope["governance_dashboard_path"]),
        Path(scope["routing_credit_path"]),
        Path(scope["org_taxonomy_path"]),
        Path(scope["review_state_path"]),
        Path(scope["latest_review_path"]),
        Path(scope["ontology_path"]),
        SPECS_ROOT / "operational-ontology-v0.md",
        SPECS_ROOT / "action-catalog-v0.json",
        SPECS_ROOT / "policy-boundary-v0.md",
        SPECS_ROOT / "operational-ontology-implementation-plan-v0.md",
    ]
    for path in strategy_paths:
        if not path.exists():
            continue
        asset_type = "ontology_db" if path.suffix == ".db" else "strategy_artifact"
        domain = "ontology" if path.suffix == ".db" else "governance"
        asset_id = stable_id("asset", str(path))
        assets.append(
            {
                "id": asset_id,
                "asset_id": asset_id,
                "title": path.name,
                "asset_type": asset_type,
                "domain": domain,
                "source_path": str(path),
                "source_kind": "file",
                "source_ref": str(path),
                "status": "active",
                "owner_mode": "ai",
                "confidence": 0.98,
                "last_seen_at": iso_now(),
                "updated_at": iso_now(),
            }
        )
    return assets


def operational_action_catalog_path() -> Path:
    return SPECS_ROOT / "action-catalog-v0.json"


def operational_policy_boundary_path() -> Path:
    return SPECS_ROOT / "policy-boundary-v0.md"


def operational_ontology_spec_path() -> Path:
    return SPECS_ROOT / "operational-ontology-v0.md"


def operational_impl_plan_path() -> Path:
    return SPECS_ROOT / "operational-ontology-implementation-plan-v0.md"


def read_action_catalog() -> dict[str, Any]:
    return read_json(operational_action_catalog_path(), default={})


def build_operational_actions() -> list[dict[str, Any]]:
    catalog = read_action_catalog()
    scenario = str(catalog.get("scenario", "skill_governance")).strip() or "skill_governance"
    actions: list[dict[str, Any]] = []
    for raw in catalog.get("actions", []):
        action_id = str(raw.get("action_id", "")).strip()
        if not action_id:
            continue
        actions.append(
            {
                "id": action_id,
                "action_id": action_id,
                "title": str(raw.get("title", action_id)).strip(),
                "scenario": scenario,
                "status": "active",
                "target_entity_type": str(raw.get("target_entity_type", "")).strip(),
                "allowed_actor_types": coerce_string_list(raw.get("allowed_actor_types")),
                "required_policy_ids": coerce_string_list(raw.get("required_policy_ids")),
                "input_contract": raw.get("input_contract", {}),
                "output_contract": raw.get("output_contract", {}),
                "writeback_targets": coerce_string_list(raw.get("writeback_targets")),
                "requires_human_approval": bool(raw.get("requires_human_approval")),
                "source_ref": str(operational_action_catalog_path()),
                "confidence": 0.96,
                "updated_at": iso_now(),
            }
        )
    return actions


def build_operational_agent_capabilities() -> list[dict[str, Any]]:
    capabilities: list[dict[str, Any]] = []
    for raw in OPERATIONAL_CAPABILITY_DEFAULTS:
        capability_id = str(raw["capability_id"])
        capabilities.append(
            {
                "id": capability_id,
                "capability_id": capability_id,
                "title": str(raw["title"]),
                "status": "active",
                "actor_type": str(raw["actor_type"]),
                "allowed_action_ids": coerce_string_list(raw.get("allowed_action_ids")),
                "bound_policy_ids": coerce_string_list(raw.get("bound_policy_ids")),
                "requires_human_approval": bool(raw.get("requires_human_approval")),
                "source_ref": str(operational_policy_boundary_path()),
                "confidence": 0.95,
                "updated_at": iso_now(),
            }
        )
    return capabilities


def build_federation_entities(
    scope: dict[str, str],
    skills: list[dict[str, Any]],
    assets: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    spaces = with_runtime_fields(FEDERATION_SPACE_SPECS)
    subjects = with_runtime_fields(DEFAULT_SUBJECT_SPECS + DEFAULT_AGENT_SPECS)
    endpoints = with_runtime_fields(DEFAULT_ENDPOINT_SPECS)
    accounts = with_runtime_fields(DEFAULT_ACCOUNT_SPECS)
    modules = with_runtime_fields(OPERATING_MODULE_SPECS)

    relations: list[dict[str, Any]] = []
    for space in spaces:
        parent_space_id = str(space.get("parent_space_id", "")).strip()
        if parent_space_id:
            relations.append(
                build_relation(
                    "space",
                    parent_space_id,
                    "space_parent_of_space",
                    "space",
                    str(space["space_id"]),
                    str(space["source_ref"]),
                )
            )
    for subject in subjects:
        relations.append(
            build_relation(
                "space",
                str(subject["space_id"]),
                "space_contains_subject",
                "subject",
                str(subject["subject_id"]),
                str(subject["source_ref"]),
            )
        )
    for module in modules:
        relations.append(
            build_relation(
                "space",
                str(module["space_id"]),
                "space_contains_module",
                "operating_module",
                str(module["module_id"]),
                str(module["source_ref"]),
            )
        )
        relations.append(
            build_relation(
                "subject",
                str(module["owner_subject_id"]),
                "subject_responsible_for_module",
                "operating_module",
                str(module["module_id"]),
                str(module["source_ref"]),
            )
        )
        relations.append(
            build_relation(
                "subject",
                str(module["ai_subject_id"]),
                "ai_agent_copilots_module",
                "operating_module",
                str(module["module_id"]),
                str(module["source_ref"]),
            )
        )
    for endpoint in endpoints:
        relations.append(
            build_relation(
                "subject",
                str(endpoint["owner_subject_id"]),
                "subject_owns_endpoint",
                "endpoint",
                str(endpoint["endpoint_id"]),
                str(endpoint["source_ref"]),
            )
        )
    for account in accounts:
        relations.append(
            build_relation(
                "subject",
                str(account["owner_subject_id"]),
                "subject_controls_account",
                "account",
                str(account["account_id"]),
                str(account["source_ref"]),
            )
        )
        relations.append(
            build_relation(
                "endpoint",
                str(account["endpoint_id"]),
                "endpoint_hosts_account",
                "account",
                str(account["account_id"]),
                str(account["source_ref"]),
            )
        )

    skill_ids = {str(item["skill_id"]) for item in skills}
    for agent_id, hints in AGENT_SKILL_HINTS.items():
        for skill_id in hints:
            if skill_id not in skill_ids:
                continue
            relations.append(
                build_relation(
                    "skill",
                    skill_id,
                    "skill_enables_agent",
                    "subject",
                    agent_id,
                    f"generated://skill-enables-agent/{skill_id}",
                )
            )

    governance_asset_id = find_asset_id(assets, "governance-dashboard")
    ontology_asset_id = find_asset_id(assets, "ontology.db")
    review_asset_id = find_asset_id(assets, "daily-skill-co-review")
    if governance_asset_id:
        relations.append(
            build_relation(
                "asset",
                governance_asset_id,
                "asset_supports_account",
                "account",
                "account-github",
                "generated://asset-supports-account/github",
            )
        )
        relations.append(
            build_relation(
                "asset",
                governance_asset_id,
                "asset_supports_account",
                "account",
                "account-feishu",
                "generated://asset-supports-account/feishu",
            )
        )
        relations.append(
            build_relation(
                "asset",
                governance_asset_id,
                "asset_supports_module",
                "operating_module",
                "module-governance",
                "generated://asset-supports-module/governance-dashboard",
            )
        )
    if ontology_asset_id:
        relations.append(
            build_relation(
                "asset",
                ontology_asset_id,
                "asset_supports_module",
                "operating_module",
                "module-governance",
                scope["ontology_path"],
            )
        )
        relations.append(
            build_relation(
                "asset",
                ontology_asset_id,
                "asset_supports_module",
                "operating_module",
                "module-public",
                scope["ontology_path"],
            )
        )
    if review_asset_id:
        relations.append(
            build_relation(
                "asset",
                review_asset_id,
                "asset_supports_module",
                "operating_module",
                "module-governance",
                "generated://asset-supports-module/daily-review",
            )
        )

    return spaces, subjects, endpoints, accounts, modules, relations


def ontology_asset_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"tables": [], "path": str(path), "status": "missing"}
    try:
        with sqlite3.connect(str(path)) as connection:
            cursor = connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
    except sqlite3.Error:
        tables = []
    return {"tables": tables, "path": str(path), "status": "available"}


def build_task_thread_entities(
    scope: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    active_threads_path = Path(scope["active_threads_path"])
    goal_priority = load_goal_priority(Path(scope["strategic_goals_path"]))
    thread_source_ref = str(active_threads_path)
    tasks: list[dict[str, Any]] = []
    threads: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    source_asset_id = stable_id("asset", thread_source_ref)
    for item in read_json(active_threads_path, default=[]):
        run_id = str(item.get("run_id", "")).strip()
        if not run_id:
            continue
        title = str(item.get("task_text", run_id)).strip()
        goal_id = str(item.get("goal_id", "")).strip()
        status = str(item.get("status", "active")).strip() or "active"
        selected_skills = [str(skill).strip() for skill in item.get("selected_skills", []) if str(skill).strip()]
        open_questions = [str(question).strip() for question in item.get("open_questions", []) if str(question).strip()]
        task_id = f"task-{run_id}"
        thread_id = f"thread-{run_id}"
        next_action = open_questions[0] if open_questions else ""
        priority = priority_label(goal_priority.get(goal_id))
        space_id = infer_space_id(title)
        module_code = infer_module_code(title, selected_skills)
        module_id = module_id_from_code(module_code)
        subject_id = subject_id_for_module_owner(module_code)
        tasks.append(
            {
                "id": task_id,
                "task_id": task_id,
                "title": title,
                "goal_id": goal_id,
                "space_id": space_id,
                "target_subject_id": subject_id,
                "target_module_id": module_id,
                "status": status,
                "priority": priority,
                "owner_mode": "ai",
                "selected_skills": selected_skills,
                "verification_state": "needs_follow_up" if open_questions else "verified_or_closed",
                "evidence_ref": f"{thread_source_ref}#{run_id}",
                "next_action": next_action,
                "source_ref": thread_source_ref,
                "confidence": 0.92,
                "last_updated_at": iso_now(),
                "updated_at": iso_now(),
            }
        )
        threads.append(
            {
                "id": thread_id,
                "thread_id": thread_id,
                "title": title,
                "theme": goal_id or "unclassified",
                "goal_id": goal_id,
                "space_id": space_id,
                "module_id": module_id,
                "status": status,
                "source_run_id": run_id,
                "open_questions": open_questions,
                "morning_review_flag": status == "active",
                "next_review_date": now_local().date().isoformat() if status == "active" else "",
                "source_ref": thread_source_ref,
                "confidence": 0.92,
                "updated_at": iso_now(),
            }
        )
        relations.append(
            {
                "id": stable_id("rel", task_id, thread_id, "task_belongs_to_thread"),
                "relation_id": stable_id("rel", task_id, thread_id, "task_belongs_to_thread"),
                "from_type": "task",
                "from_id": task_id,
                "relation_type": "task_belongs_to_thread",
                "to_type": "thread",
                "to_id": thread_id,
                "evidence_ref": f"{thread_source_ref}#{run_id}",
                "updated_at": iso_now(),
            }
        )
        relations.append(
            {
                "id": stable_id("rel", source_asset_id, task_id, "asset_supports_task"),
                "relation_id": stable_id("rel", source_asset_id, task_id, "asset_supports_task"),
                "from_type": "asset",
                "from_id": source_asset_id,
                "relation_type": "asset_supports_task",
                "to_type": "task",
                "to_id": task_id,
                "evidence_ref": thread_source_ref,
                "updated_at": iso_now(),
            }
        )
        relations.append(
            {
                "id": stable_id("rel", source_asset_id, thread_id, "asset_supports_thread"),
                "relation_id": stable_id("rel", source_asset_id, thread_id, "asset_supports_thread"),
                "from_type": "asset",
                "from_id": source_asset_id,
                "relation_type": "asset_supports_thread",
                "to_type": "thread",
                "to_id": thread_id,
                "evidence_ref": thread_source_ref,
                "updated_at": iso_now(),
            }
        )
        relations.append(
            build_relation(
                "task",
                task_id,
                "task_targets_subject",
                "subject",
                subject_id,
                f"{thread_source_ref}#{run_id}",
            )
        )
        relations.append(
            build_relation(
                "task",
                task_id,
                "task_targets_module",
                "operating_module",
                module_id,
                f"{thread_source_ref}#{run_id}",
            )
        )
        relations.append(
            build_relation(
                "thread",
                thread_id,
                "thread_tracks_space",
                "space",
                space_id,
                f"{thread_source_ref}#{run_id}",
            )
        )
        for skill in selected_skills:
            relations.append(build_relation("skill", skill, "skill_supports_task", "task", task_id, f"{thread_source_ref}#{run_id}"))
            relations.append(
                build_relation("skill", skill, "skill_supports_thread", "thread", thread_id, f"{thread_source_ref}#{run_id}")
            )
        if "原力" in title or "yuanli" in title.lower():
            ontology_asset_id = stable_id("asset", scope["ontology_path"])
            relations.append(
                build_relation("asset", ontology_asset_id, "asset_supports_thread", "thread", thread_id, scope["ontology_path"])
            )
            relations.append(
                build_relation("asset", ontology_asset_id, "asset_supports_module", "operating_module", module_id, scope["ontology_path"])
            )
    return tasks, threads, relations


def load_latest_review(scope: dict[str, str]) -> dict[str, Any]:
    return read_json(Path(scope["latest_review_path"]), default={})


def load_latest_skill_scout(scope: dict[str, str]) -> dict[str, Any]:
    path = str(scope.get("latest_skill_scout_path", "")).strip()
    if not path:
        return {}
    return read_json(Path(path), default={})


def build_review_entities(scope: dict[str, str]) -> list[dict[str, Any]]:
    latest_review = load_latest_review(scope)
    if not latest_review:
        return []
    return [
        {
            "id": latest_review.get("run_id", stable_id("review", "latest")),
            "review_id": latest_review.get("run_id", stable_id("review", "latest")),
            "review_date": str(latest_review.get("created_at", ""))[:10],
            "scope": "AI大管家日常 review",
            "summary": f"skills_total={latest_review.get('skills_total', 0)} / status={latest_review.get('status', 'unknown')}",
            "top_risks": [cluster.get("name", "") for cluster in latest_review.get("weak_clusters", [])[:3]],
            "candidate_actions": [item.get("title", "") for item in latest_review.get("candidate_actions", [])[:3]],
            "human_decision": "",
            "sync_state": latest_review.get("feishu_sync_status", "unknown"),
            "source_ref": scope["latest_review_path"],
            "confidence": 0.9,
            "updated_at": iso_now(),
        }
    ]


def build_operational_decision_records(
    scope: dict[str, str],
    threads: list[dict[str, Any]],
    review_runs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    active_threads_path = str(scope["active_threads_path"])
    for thread in threads:
        title = str(thread.get("title", "")).strip()
        if "operational ontology" not in title.lower():
            continue
        decision_id = stable_id("decision", str(thread["thread_id"]), "promote")
        records.append(
            {
                "id": decision_id,
                "decision_id": decision_id,
                "title": f"将 {title} 设为 G1 当前一号实现线程",
                "decision_type": "strategic_thread_priority",
                "decision_state": "approved",
                "target_entity_ids": [str(thread["thread_id"]), str(thread.get("goal_id", ""))],
                "decision_summary": "Operational ontology v0 is the current G1 implementation priority.",
                "rationale": "Move from Palantir research into schema, action, policy, writeback, and audit implementation.",
                "evidence_refs": [active_threads_path],
                "decided_by": "human_owner",
                "decision_time": str(thread.get("updated_at") or iso_now()),
                "writeback_event_ids": [stable_id("writeback", str(thread["thread_id"]), "governance-overview")],
                "source_ref": active_threads_path,
                "confidence": 0.94,
                "updated_at": iso_now(),
            }
        )

    latest_review = load_latest_review(scope)
    review_id = str(latest_review.get("run_id", "")).strip()
    review_time = str(latest_review.get("created_at", "")).strip() or iso_now()
    for candidate in latest_review.get("candidate_actions", [])[:3]:
        candidate_id = str(candidate.get("id", "")).strip()
        title = str(candidate.get("title", "")).strip()
        if not candidate_id or not title:
            continue
        decision_id = stable_id("decision", review_id or "latest-review", candidate_id)
        records.append(
            {
                "id": decision_id,
                "decision_id": decision_id,
                "title": title,
                "decision_type": "review_action_resolution",
                "decision_state": "pending_approval",
                "target_entity_ids": [review_id] if review_id else [],
                "decision_summary": title,
                "rationale": str(candidate.get("problem", "")).strip() or str(candidate.get("recommended_next_step", "")).strip(),
                "evidence_refs": [str(scope["latest_review_path"])] if review_runs else [],
                "decided_by": "",
                "decision_time": review_time,
                "writeback_event_ids": [],
                "source_ref": str(scope["latest_review_path"]),
                "confidence": 0.88,
                "updated_at": iso_now(),
            }
        )
    return records


def build_operational_writeback_events(
    scope: dict[str, str],
    decision_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    approved_decision = next(
        (item for item in decision_records if str(item.get("decision_state", "")).strip() == "approved"),
        None,
    )
    report_path = DERIVED_ROOT / "reports" / "governance-overview.md"
    report_json_path = DERIVED_ROOT / "reports" / "governance-overview.json"
    snapshot_path = CANONICAL_ROOT / "snapshots" / "latest.json"
    writeback_id = (
        coerce_string_list(approved_decision.get("writeback_event_ids"))[0]
        if approved_decision and coerce_string_list(approved_decision.get("writeback_event_ids"))
        else stable_id("writeback", "governance-overview", str(report_path))
    )
    return [
        {
            "id": writeback_id,
            "writeback_id": writeback_id,
            "action_id": "publish-governance-report",
            "decision_id": str(approved_decision.get("decision_id", "")) if approved_decision else "",
            "target_refs": [str(report_path), str(report_json_path), str(snapshot_path)],
            "changed_fields": ["governance_overview", "inventory_snapshot", "summary_counts"],
            "evidence_refs": [str(scope["active_threads_path"]), str(operational_action_catalog_path())],
            "triggered_by": "automation",
            "writeback_time": iso_now(),
            "verification_state": "completed" if approved_decision else "blocked_missing_decision",
            "source_ref": str(report_path),
            "confidence": 0.9,
            "updated_at": iso_now(),
        }
    ]


def dedupe_by_key(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    ordered: list[dict[str, Any]] = []
    for item in items:
        value = str(item.get(key, "")).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(item)
    return ordered


def infer_source_system(knowledge_source: dict[str, Any]) -> str:
    page_type = str(knowledge_source.get("page_type", "")).strip()
    url = str(knowledge_source.get("url", "")).strip()
    if page_type == "wiki" or "feishu.cn" in url or "larksuite.com" in url:
        return "feishu"
    if page_type == "tencent_meeting_share" or "meeting.tencent.com" in url:
        return "tencent_meeting"
    return "external"


def seed_knowledge_items(knowledge_sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for source in knowledge_sources:
        source_ref = str(source.get("canonical_url") or source.get("url") or "").strip()
        source_id = str(source.get("source_id") or source.get("id") or "").strip()
        title = str(source.get("title") or "Untitled knowledge source").strip()
        artifact_dir = str(source.get("artifact_dir") or "").strip()
        validation_status = str(source.get("validation_status") or "").strip()
        item_status = "active" if validation_status == "validated" else "pending_review"
        sync_tier = "core" if validation_status == "validated" else "candidate"
        summary = (
            f"Knowledge source seed for {title}. "
            f"Validation status: {validation_status or 'unknown'}."
        )
        items.append(
            {
                "id": stable_id("kitem", source_id or source_ref or title),
                "knowledge_id": stable_id("kitem", source_id or source_ref or title),
                "title": title,
                "governance_layer": "治理层",
                "material_type": "knowledge_source_root",
                "source_system": infer_source_system(source),
                "source_ref": source_ref,
                "source_id": source_id,
                "canonical_path": str(Path(artifact_dir) / "source.md") if artifact_dir else "",
                "summary": summary,
                "importance": "high" if sync_tier == "core" else "medium",
                "sync_tier": sync_tier,
                "status": item_status,
                "updated_at": str(source.get("updated_at") or iso_now()),
            }
        )
    return dedupe_by_key(items, "knowledge_id")


def read_manual_knowledge_catalogs(scope: dict[str, Any], knowledge_sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ingest_root = Path(scope.get("feishu_ingest_root", str(DEFAULT_FEISHU_INGEST_ROOT))).expanduser().resolve()
    if not ingest_root.exists():
        return []
    registered_source_ids = {
        str(item.get("source_id", "")).strip()
        for item in knowledge_sources
        if str(item.get("source_id", "")).strip()
    }
    items: list[dict[str, Any]] = []
    for path in sorted(ingest_root.glob("**/knowledge-catalog.json")):
        payload = read_json(path, default={})
        catalog_items = payload.get("items", payload if isinstance(payload, list) else [])
        if not isinstance(catalog_items, list):
            continue
        source_id = str(payload.get("source_id", "")).strip()
        if source_id and source_id not in registered_source_ids:
            continue
        source_title = str(payload.get("source_title", "")).strip()
        source_url = str(payload.get("source_url", "")).strip()
        default_canonical_path = str(path.parent / "source.md")
        for raw_item in catalog_items:
            if not isinstance(raw_item, dict):
                continue
            title = str(raw_item.get("title", "")).strip()
            if not title:
                continue
            source_ref = str(raw_item.get("source_ref", "")).strip() or f"manual_nav::{source_title or path.parent.name}/{title}"
            items.append(
                {
                    "id": str(raw_item.get("knowledge_id", "")).strip()
                    or stable_id("kitem", source_id or source_url or source_ref, title),
                    "knowledge_id": str(raw_item.get("knowledge_id", "")).strip()
                    or stable_id("kitem", source_id or source_url or source_ref, title),
                    "title": title,
                    "governance_layer": str(raw_item.get("governance_layer", "")).strip() or "资产层",
                    "material_type": str(raw_item.get("material_type", "")).strip() or "knowledge_entry",
                    "source_system": str(raw_item.get("source_system", "")).strip() or "feishu",
                    "source_ref": source_ref,
                    "source_id": str(raw_item.get("source_id", "")).strip() or source_id,
                    "canonical_path": str(raw_item.get("canonical_path", "")).strip() or default_canonical_path,
                    "summary": str(raw_item.get("summary", "")).strip() or f"Catalog item extracted from {source_title or path.parent.name}.",
                    "importance": str(raw_item.get("importance", "")).strip() or "medium",
                    "sync_tier": str(raw_item.get("sync_tier", "")).strip() or "candidate",
                    "status": str(raw_item.get("status", "")).strip() or "pending_review",
                    "updated_at": str(raw_item.get("updated_at", "")).strip() or iso_now(),
                }
            )
    return dedupe_by_key(items, "knowledge_id")


def build_inventory(scope_path: Path | None = None) -> dict[str, Any]:
    scope = load_source_scope(scope_path)
    knowledge_sources = read_knowledge_sources()
    skills, skill_assets = build_skill_entities(scope)
    automation_assets = build_automation_assets(scope)
    strategy_assets = build_strategy_assets(scope)
    ingested = build_ingested_entities(scope)
    assets = dedupe_by_key(skill_assets + automation_assets + strategy_assets + ingested["assets"], "asset_id")
    spaces, subjects, endpoints, accounts, operating_modules, federation_relations = build_federation_entities(
        scope, skills, assets
    )
    accounts = reconcile_accounts_with_source_feeds(accounts, ingested["source_feeds"])
    tasks, threads, relations = build_task_thread_entities(scope)
    review_runs = build_review_entities(scope)
    actions = build_operational_actions()
    agent_capabilities = build_operational_agent_capabilities()
    decision_records = build_operational_decision_records(scope, threads, review_runs)
    writeback_events = build_operational_writeback_events(scope, decision_records)
    knowledge_items = seed_knowledge_items(knowledge_sources) + read_manual_knowledge_catalogs(scope, knowledge_sources)

    spaces = dedupe_by_key(spaces, "space_id")
    subjects = dedupe_by_key(subjects, "subject_id")
    endpoints = dedupe_by_key(endpoints, "endpoint_id")
    accounts = dedupe_by_key(accounts, "account_id")
    operating_modules = dedupe_by_key(operating_modules, "module_id")
    source_feeds = dedupe_by_key(ingested["source_feeds"], "source_feed_id")
    ingestion_runs = dedupe_by_key(ingested["ingestion_runs"], "ingestion_run_id")
    orders = dedupe_by_key(ingested["orders"], "order_id")
    cashflows = dedupe_by_key(ingested["cashflows"], "cashflow_id")
    skills = dedupe_by_key(skills, "skill_id")
    tasks = dedupe_by_key(tasks, "task_id")
    threads = dedupe_by_key(threads, "thread_id")
    review_runs = dedupe_by_key(review_runs, "review_id")
    actions = dedupe_by_key(actions, "action_id")
    agent_capabilities = dedupe_by_key(agent_capabilities, "capability_id")
    decision_records = dedupe_by_key(decision_records, "decision_id")
    writeback_events = dedupe_by_key(writeback_events, "writeback_id")
    knowledge_items = dedupe_by_key(knowledge_items, "knowledge_id")
    relations = dedupe_by_key(federation_relations + relations, "relation_id")

    inventory = {
        "generated_at": iso_now(),
        "source_scope": scope,
        "ontology_summary": ontology_asset_summary(Path(scope["ontology_path"])),
        "counts": {
            "spaces": len(spaces),
            "subjects": len(subjects),
            "endpoints": len(endpoints),
            "accounts": len(accounts),
            "operating_modules": len(operating_modules),
            "source_feeds": len(source_feeds),
            "ingestion_runs": len(ingestion_runs),
            "assets": len(assets),
            "orders": len(orders),
            "cashflows": len(cashflows),
            "tasks": len(tasks),
            "threads": len(threads),
            "skills": len(skills),
            "actions": len(actions),
            "agent_capabilities": len(agent_capabilities),
            "decision_records": len(decision_records),
            "writeback_events": len(writeback_events),
            "knowledge_items": len(knowledge_items),
            "review_runs": len(review_runs),
            "relations": len(relations),
        },
        "spaces": spaces,
        "subjects": subjects,
        "endpoints": endpoints,
        "accounts": accounts,
        "operating_modules": operating_modules,
        "source_feeds": source_feeds,
        "ingestion_runs": ingestion_runs,
        "assets": assets,
        "orders": orders,
        "cashflows": cashflows,
        "tasks": tasks,
        "threads": threads,
        "skills": skills,
        "actions": actions,
        "agent_capabilities": agent_capabilities,
        "decision_records": decision_records,
        "writeback_events": writeback_events,
        "knowledge_items": knowledge_items,
        "review_runs": review_runs,
        "relations": relations,
    }
    persist_inventory(inventory)
    return inventory


def persist_inventory(inventory: dict[str, Any]) -> None:
    write_json(ENTITY_FILES["spaces"], inventory["spaces"])
    write_json(ENTITY_FILES["subjects"], inventory["subjects"])
    write_json(ENTITY_FILES["endpoints"], inventory["endpoints"])
    write_json(ENTITY_FILES["accounts"], inventory["accounts"])
    write_json(ENTITY_FILES["operating_modules"], inventory["operating_modules"])
    write_json(ENTITY_FILES["source_feeds"], inventory["source_feeds"])
    write_json(ENTITY_FILES["ingestion_runs"], inventory["ingestion_runs"])
    write_json(ENTITY_FILES["assets"], inventory["assets"])
    write_json(ENTITY_FILES["orders"], inventory["orders"])
    write_json(ENTITY_FILES["cashflows"], inventory["cashflows"])
    write_json(ENTITY_FILES["tasks"], inventory["tasks"])
    write_json(ENTITY_FILES["threads"], inventory["threads"])
    write_json(ENTITY_FILES["skills"], inventory["skills"])
    write_json(ENTITY_FILES["actions"], inventory["actions"])
    write_json(ENTITY_FILES["agent_capabilities"], inventory["agent_capabilities"])
    write_json(ENTITY_FILES["decision_records"], inventory["decision_records"])
    write_json(ENTITY_FILES["writeback_events"], inventory["writeback_events"])
    write_json(ENTITY_FILES["knowledge_items"], inventory["knowledge_items"])
    write_json(ENTITY_FILES["review_runs"], inventory["review_runs"])
    write_json(ENTITY_FILES["relations"], inventory["relations"])

    snapshot_dir = CANONICAL_ROOT / "snapshots" / now_local().date().isoformat()
    snapshot_path = snapshot_dir / "inventory-snapshot.json"
    write_json(snapshot_path, inventory)
    write_json(CANONICAL_ROOT / "snapshots" / "latest.json", inventory)
    write_json(DERIVED_ROOT / "reports" / "inventory-snapshot.json", inventory)
    write_text(DERIVED_ROOT / "reports" / "governance-overview.md", render_governance_overview(inventory))
    write_json(DERIVED_ROOT / "reports" / "governance-overview.json", build_governance_summary(inventory))


def inventory_sources(scope_path: Path | None = None) -> dict[str, Any]:
    scope = load_source_scope(scope_path)
    ingested = build_ingested_entities(scope)
    payload = {
        "generated_at": iso_now(),
        "source_scope": scope,
        "source_feeds": ingested["source_feeds"],
        "ingestion_runs": ingested["ingestion_runs"],
        "counts": {
            "source_feeds": len(ingested["source_feeds"]),
            "ingestion_runs": len(ingested["ingestion_runs"]),
            "orders": len(ingested["orders"]),
            "cashflows": len(ingested["cashflows"]),
            "assets": len(ingested["assets"]),
        },
    }
    write_json(DERIVED_ROOT / "reports" / "source-inventory.json", payload)
    return payload


def ingest_business(scope_path: Path | None = None) -> dict[str, Any]:
    scope = load_source_scope(scope_path)
    ingested = build_ingested_entities(scope)
    payload = {
        "generated_at": iso_now(),
        "orders": ingested["orders"],
        "cashflows": ingested["cashflows"],
        "counts": {
            "orders": len(ingested["orders"]),
            "cashflows": len(ingested["cashflows"]),
        },
    }
    write_json(DERIVED_ROOT / "reports" / "business-ingestion.json", payload)
    return payload


def ingest_content(scope_path: Path | None = None) -> dict[str, Any]:
    scope = load_source_scope(scope_path)
    ingested = build_ingested_entities(scope)
    content_assets = [
        item
        for item in ingested["assets"]
        if item.get("content_class") in {"course_material", "knowledge_document", "article_asset", "social_asset", "content_artifact"}
    ]
    payload = {
        "generated_at": iso_now(),
        "content_assets": content_assets,
        "counts": {
            "content_assets": len(content_assets),
        },
    }
    write_json(DERIVED_ROOT / "reports" / "content-ingestion.json", payload)
    return payload


def resolve_node_binary() -> Path | None:
    env_value = os.getenv("YUANLI_NODE_BIN", "").strip()
    if env_value:
        explicit = Path(env_value).expanduser()
        if explicit.exists() and os.access(explicit, os.X_OK):
            return explicit
        return None
    candidate_paths: list[Path] = []
    which_value = shutil.which("node")
    if which_value:
        candidate_paths.append(Path(which_value))
    candidate_paths.append(Path.home() / ".local" / "bin" / "node")
    for base in [Path.home() / ".local" / "lib", Path.home() / ".local"]:
        if not base.exists():
            continue
        candidate_paths.extend(sorted(base.glob("node-v*/bin/node"), reverse=True))
    seen: set[str] = set()
    for candidate in candidate_paths:
        resolved = str(candidate.expanduser())
        if resolved in seen:
            continue
        seen.add(resolved)
        path = Path(resolved)
        if path.exists() and os.access(path, os.X_OK):
            return path
    return None


def resolve_feishu_reader_script() -> Path:
    override = os.getenv("YUANLI_FEISHU_READER_SCRIPT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (CODEX_HOME / "skills" / "feishu-reader" / "scripts" / "extract_feishu.js").resolve()


def materialize_feishu_reader_runtime(script_path: Path) -> Path:
    runtime_dir = DEFAULT_FEISHU_INGEST_ROOT / "runtime"
    runtime_script = runtime_dir / "extract_feishu.js"
    write_text(runtime_script, script_path.read_text(encoding="utf-8"))
    return runtime_script


def map_extraction_status(status: str) -> str:
    normalized = str(status or "").strip()
    if normalized == "ok":
        return "validated"
    if normalized in KNOWLEDGE_SOURCE_ALLOWED_STATUSES:
        return normalized
    return "empty_extraction"


def read_knowledge_sources() -> list[dict[str, Any]]:
    return read_json(ENTITY_FILES["knowledge_sources"], default=[])


def upsert_knowledge_source(
    *,
    scope_path: Path | None,
    normalized_url: str,
    entry: dict[str, Any],
    scope_key: str = "source_feishu_links",
) -> None:
    entities = read_knowledge_sources()
    updated_entities = [
        item
        for item in entities
        if normalize_external_url(str(item.get("url", ""))) != normalized_url
    ]
    updated_entities.append(entry)
    updated_entities.sort(key=lambda item: str(item.get("source_id", "")))
    write_json(ENTITY_FILES["knowledge_sources"], updated_entities)

    active_scope_path = source_scope_file(scope_path)
    scope = load_source_scope(scope_path)
    scope[scope_key] = unique_strings(
        list(scope.get(scope_key, [])) + [normalized_url]
    )
    write_json(active_scope_path, scope)


def resolve_get_biji_transcript_script() -> Path:
    override = os.getenv("YUANLI_GET_BIJI_TRANSCRIPT_SCRIPT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (CODEX_HOME / "skills" / "get-biji-transcript" / "scripts" / "get_biji_transcript.py").resolve()


def build_runtime_blocked_result(
    *,
    url: str,
    artifact_dir: Path,
    notes: str,
) -> dict[str, Any]:
    validated_at = iso_now()
    source_id = stable_id("ksrc", url)
    entry = {
        "id": source_id,
        "source_id": source_id,
        "title": "Yuanli planet shared knowledge source",
        "url": url,
        "page_type": "wiki",
        "source_role": "shared_kb_candidate",
        "validation_status": "blocked_runtime_missing",
        "auth_mode_used": "",
        "artifact_dir": str(artifact_dir),
        "notes": notes,
        "last_validated_at": validated_at,
        "updated_at": validated_at,
    }
    return {
        "ok": False,
        "validation_status": "blocked_runtime_missing",
        "source_id": source_id,
        "normalized_url": url,
        "artifact_dir": str(artifact_dir),
        "knowledge_source": entry,
    }


def build_manual_validation_result(
    *,
    normalized_url: str,
    artifact_dir: Path,
    title: str,
    note: str,
) -> dict[str, Any]:
    validated_at = iso_now()
    source_id = stable_id("ksrc", normalized_url)
    canonical_url = canonicalize_knowledge_source_url(normalized_url)
    entry = {
        "id": source_id,
        "source_id": source_id,
        "title": title,
        "url": normalized_url,
        "canonical_url": canonical_url,
        "page_type": "wiki",
        "source_role": "shared_kb_candidate",
        "validation_status": "validated",
        "auth_mode_used": "manual_browser_confirmation",
        "artifact_dir": str(artifact_dir),
        "notes": note,
        "last_validated_at": validated_at,
        "updated_at": validated_at,
    }
    return {
        "ok": True,
        "validation_status": "validated",
        "source_id": source_id,
        "normalized_url": normalized_url,
        "artifact_dir": str(artifact_dir),
        "command": ["manual_browser_validation"],
        "returncode": 0,
        "stdout": "validated via manual browser confirmation",
        "stderr": "",
        "artifact_json": str(artifact_dir / "source.json"),
        "artifact_markdown": str(artifact_dir / "source.md"),
        "knowledge_source": entry,
    }


def write_manual_validation_artifacts(
    *,
    artifact_dir: Path,
    title: str,
    canonical_url: str,
    note: str,
) -> None:
    source_json = {
        "page_type": "wiki",
        "title": title,
        "canonical_url": canonical_url,
        "metadata": {
            "document_title": title,
            "workspace_title": "飞书云文档",
        },
        "toc": [],
        "text": title,
        "visible_links": [{"text": title, "href": canonical_url}],
        "auth_mode_used": "manual_browser_confirmation",
        "screenshot_path": "",
        "status": "ok",
        "artifacts": {
            "json": str(artifact_dir / "source.json"),
            "markdown": str(artifact_dir / "source.md"),
            "screenshot": "",
        },
        "notes": {
            "validation_method": "manual_browser_confirmation",
            "evidence": note,
        },
    }
    source_md = "\n".join(
        [
            f"# {title}",
            "",
            f"- Canonical URL: {canonical_url}",
            "- Page Type: wiki",
            "- Auth Mode: manual_browser_confirmation",
            "- Validation: validated",
            "",
            "## Notes",
            "",
            f"- {note}",
        ]
    )
    write_json(artifact_dir / "source.json", source_json)
    write_text(artifact_dir / "source.md", source_md)


def extract_tencent_meeting_short_link(url: str) -> str:
    parsed = urlsplit(normalize_external_url(url))
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2 and parts[0] in {"crm", "cw"}:
        return parts[1]
    if parsed.query:
        match = re.search(r"(?:^|[?&])short_link=([^&]+)", f"?{parsed.query}")
        if match:
            return match.group(1)
    return ""


def normalize_tencent_meeting_share_url(url: str) -> tuple[str, str]:
    normalized = normalize_external_url(url)
    parsed = urlsplit(normalized)
    short_link = extract_tencent_meeting_short_link(normalized)
    if short_link and parsed.path.startswith(("/crm/", "/cw/")):
        return urlunsplit((parsed.scheme, parsed.netloc, f"/cw/{short_link}", "", "")), short_link
    return normalized, short_link


def fetch_http_document(url: str, *, timeout_seconds: float = 20.0) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "yuanli-governance/1.0"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
            text = body.decode(charset, errors="replace")
            return {
                "ok": True,
                "status_code": getattr(response, "status", 200),
                "final_url": normalize_external_url(response.geturl()),
                "headers": dict(response.headers.items()),
                "body": text,
                "error": "",
            }
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return {
            "ok": False,
            "status_code": exc.code,
            "final_url": normalize_external_url(exc.geturl()),
            "headers": dict(exc.headers.items()),
                "body": body,
                "error": str(exc),
            }
    except URLError as exc:
        curl_command = [
            "curl",
            "-L",
            "-sS",
            "-w",
            "\n__STATUS__:%{http_code}\n__EFFECTIVE_URL__:%{url_effective}\n",
            url,
        ]
        completed = subprocess.run(curl_command, capture_output=True, text=True, check=False)
        if completed.returncode == 0:
            match = re.search(
                r"\n__STATUS__:(\d+)\n__EFFECTIVE_URL__:(.+)\n?\Z",
                completed.stdout,
                flags=re.DOTALL,
            )
            if match:
                body = completed.stdout[: match.start()]
                return {
                    "ok": True,
                    "status_code": int(match.group(1)),
                    "final_url": normalize_external_url(match.group(2).strip()),
                    "headers": {},
                    "body": body,
                    "error": "",
                }
        return {
            "ok": False,
            "status_code": 0,
            "final_url": normalize_external_url(url),
            "headers": {},
            "body": "",
            "error": completed.stderr.strip() or str(exc),
        }


def first_match(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.DOTALL)
        if match:
            return html_lib.unescape(match.group(1).strip())
    return ""


def first_json_string_value(text: str, *keys: str) -> str:
    patterns: list[str] = []
    for key in keys:
        escaped = re.escape(key)
        patterns.extend(
            [
                rf'"{escaped}":"([^"]+)"',
                rf'\\"{escaped}\\":\\"([^"\\]+)\\"',
            ]
        )
    return first_match(text, patterns)


def first_json_int_string_value(text: str, *keys: str) -> str:
    patterns: list[str] = []
    for key in keys:
        escaped = re.escape(key)
        patterns.extend(
            [
                rf'"{escaped}":"([0-9]+)"',
                rf'\\"{escaped}\\":\\"([0-9]+)\\"',
            ]
        )
    return first_match(text, patterns)


def first_json_numeric_value(text: str, *keys: str) -> str:
    for key in keys:
        escaped = re.escape(key)
        for pattern in [
            rf'"{escaped}":"([0-9]+)"',
            rf'"{escaped}":([0-9]+)',
            rf'\\"{escaped}\\":\\"([0-9]+)\\"',
            rf'\\"{escaped}\\":([0-9]+)',
        ]:
            match = re.search(pattern, text, flags=re.DOTALL)
            if match:
                return match.group(1).strip()
    return ""


def extract_tencent_meeting_ssr_snippet(html: str) -> str:
    share_start = html.find('id="share-ssr-container"')
    if share_start < 0:
        return html
    tag_start = html.rfind("<", 0, share_start)
    if tag_start >= 0:
        return html[tag_start:]
    return html[share_start:]


def extract_tencent_meeting_visible_text(html: str) -> str:
    snippet = extract_tencent_meeting_ssr_snippet(html)
    snippet = re.sub(r"<script\b[^>]*>.*?</script>", " ", snippet, flags=re.DOTALL | re.IGNORECASE)
    snippet = re.sub(r"<style\b[^>]*>.*?</style>", " ", snippet, flags=re.DOTALL | re.IGNORECASE)
    snippet = snippet.replace("<!-- -->", "")
    snippet = re.sub(r"<[^>]+>", " ", snippet)
    snippet = html_lib.unescape(snippet)
    snippet = re.sub(r"\s+", " ", snippet)
    return snippet.strip()


def strip_tencent_meeting_boilerplate(text: str, *, title: str, created_at_raw: str) -> str:
    cleaned = text
    boilerplate = [
        title,
        created_at_raw,
        "返回",
        "更多",
        "转写",
        "纪要",
        "章节",
        "发言人",
        "话题",
        "创建时间",
        "创建者",
        "暂无文本内容",
        "摘要和待办",
    ]
    for token in boilerplate:
        if token:
            cleaned = cleaned.replace(token, " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def is_meaningful_tencent_meeting_text(text: str) -> bool:
    candidate = re.sub(r"\s+", " ", text).strip()
    if not candidate:
        return False
    if any(token in candidate for token in ['id="', "style=", "font-family:", "background-color:"]):
        return False
    cjk_or_word_units = re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9]{2,}", candidate)
    return len(cjk_or_word_units) >= 10


def infer_tencent_meeting_validation_status(capture_status: str) -> str:
    if capture_status == "accessible":
        return "validated"
    if capture_status == "gated":
        return "auth_required"
    if capture_status == "expired":
        return "not_found"
    return "empty_extraction"


def can_use_as_primary_material(record: dict[str, Any]) -> bool:
    if str(record.get("capture_status", "")).strip() != "accessible":
        return False
    return any(
        str(record.get(field, "")).strip()
        for field in ("title", "record_created_at", "meeting_code", "meeting_id")
    )


def render_tencent_meeting_assessment(capture: dict[str, Any], *, input_url: str) -> str:
    metadata_lines = [
        f"- 输入链接: {input_url}",
        f"- 归一化链接: {capture['canonical_url']}",
        f"- 短链 ID: {capture['source_id'] or 'unknown'}",
        f"- 标题: {capture['title'] or 'unknown'}",
        f"- 创建时间: {capture['record_created_at'] or 'unknown'}",
        f"- 会议码: {capture['meeting_code'] or 'unknown'}",
        f"- 会议 ID: {capture['meeting_id'] or 'unknown'}",
        f"- 录制时长(ms): {capture['recording_duration_ms'] or 'unknown'}",
        f"- 录制大小(bytes): {capture['recording_size_bytes'] or 'unknown'}",
    ]
    status_lines = [
        f"- 页面可访问: {'yes' if capture['page_accessible'] else 'no'}",
        f"- 验证状态: {capture['validation_status']}",
        f"- 采集状态: {capture['capture_status']}",
        f"- 转写状态: {capture['transcript_status']}",
        f"- 腾讯会议原生逐字稿能力: {capture.get('native_transcript_capability', 'unknown')}",
        f"- 当前录制原生转写状态: {capture.get('native_transcript_enabled', 'unknown')}",
        f"- 当前分享页逐字稿可见性: {capture.get('share_page_transcript_visible', 'unknown')}",
        f"- 当前优先文本获取路径: {capture.get('transcript_access_path', 'unknown')}",
        f"- 纪要可见: {'yes' if capture['minutes_present'] else 'no'}",
        f"- 媒体直链可见: {'yes' if capture['media_url_present'] else 'no'}",
        f"- 是否可作为主材料: {'yes' if capture['can_use_as_primary_material'] else 'no'}",
        f"- 建议补采动作: {capture['fallback_action']}",
    ]
    transcript_provider = str(capture.get("external_transcribe_provider", "")).strip()
    transcript_txt_ref = str(capture.get("transcript_txt_ref", "")).strip()
    transcript_json_ref = str(capture.get("transcript_json_ref", "")).strip()
    transcript_note_id = str(capture.get("transcript_note_id", "")).strip()
    exported_media_path = str(capture.get("exported_media_path", "")).strip()
    if transcript_provider:
        status_lines.append(f"- 外部转写提供方: {transcript_provider}")
    if transcript_note_id:
        status_lines.append(f"- 转写笔记 ID: {transcript_note_id}")
    if exported_media_path:
        status_lines.append(f"- 导出媒体路径: {exported_media_path}")
    if transcript_txt_ref:
        status_lines.append(f"- 逐字稿 TXT: {transcript_txt_ref}")
    if transcript_json_ref:
        status_lines.append(f"- 逐字稿 JSON: {transcript_json_ref}")
    notes = [
        "页面能访问",
        "页面有录制元数据",
        "页面有可用逐字稿/纪要",
    ]
    lines = [
        "# 腾讯会议来源接入评估",
        "",
        "## 元数据",
        *metadata_lines,
        "",
        "## 状态判定",
        *status_lines,
        "",
        "## 关键结论",
        f"- 必须分别判断：{ ' / '.join(notes) }。",
        "- 腾讯会议产品本身支持原生逐字稿/纪要，匿名分享页拿不到正文不等于产品没有这个能力。",
        f"- 当前页面文本摘要：{capture['text_excerpt'] or 'none'}",
        "",
        "## 下一步",
    ]
    if capture["fallback_action"] == "permission_probe":
        lines.append("- 当前更像权限可见性问题，先用更强登录态或主持人授权重新探测原生逐字稿。")
    elif capture["fallback_action"] == "browser_probe":
        lines.append("- 先用浏览器登录态复探，确认是否有登录后可见文本或更多元数据。")
    elif capture["fallback_action"] == "export_media":
        lines.append("- 当前原生逐字稿未启用或当前路径拿不到原生文本，建议从腾讯会议导出 MP4/音频后再进入外部转写链路。")
    elif capture["fallback_action"] == "external_transcribe":
        lines.append("- 当前应走外部转写路径；若能直接拿到媒体直链，可跳过导出文件。")
    elif capture["can_use_as_primary_material"]:
        lines.append("- 当前页面已经满足主材料准入，无需补采。")
    else:
        lines.append("- 当前探测没有拿到足够证据，不应据此认定分享页失效；优先在网络可达或浏览器态环境中重试。")
    return "\n".join(lines)


def render_tencent_meeting_source_markdown(capture: dict[str, Any]) -> str:
    lines = [
        f"# {capture.get('title') or 'Tencent Meeting share'}",
        "",
        f"- Canonical URL: {capture.get('canonical_url', '')}",
        f"- Page Type: tencent_meeting_share",
        f"- Source ID: {capture.get('source_id', '')}",
        f"- Validation: {capture.get('validation_status', '')}",
        f"- Capture Status: {capture.get('capture_status', '')}",
        f"- Transcript Status: {capture.get('transcript_status', '')}",
        f"- Native Transcript Capability: {capture.get('native_transcript_capability', '')}",
        f"- Native Transcript Enabled: {capture.get('native_transcript_enabled', '')}",
        f"- Share Page Transcript Visible: {capture.get('share_page_transcript_visible', '')}",
        f"- Transcript Access Path: {capture.get('transcript_access_path', '')}",
        f"- Created At: {capture.get('record_created_at', '') or 'unknown'}",
        f"- Meeting Code: {capture.get('meeting_code', '') or 'unknown'}",
        f"- Meeting ID: {capture.get('meeting_id', '') or 'unknown'}",
        f"- Recording Duration(ms): {capture.get('recording_duration_ms', 0)}",
        f"- Recording Size(bytes): {capture.get('recording_size_bytes', 0)}",
        "",
        "## Assessment",
        "",
        f"- Fallback Action: {capture.get('fallback_action', '')}",
        f"- Can Use As Primary Material: {'yes' if capture.get('can_use_as_primary_material') else 'no'}",
    ]
    transcript_txt_ref = str(capture.get("transcript_txt_ref", "")).strip()
    transcript_json_ref = str(capture.get("transcript_json_ref", "")).strip()
    exported_media_path = str(capture.get("exported_media_path", "")).strip()
    if transcript_txt_ref or transcript_json_ref or exported_media_path:
        lines.extend(["", "## Transcript Chain", ""])
        if exported_media_path:
            lines.append(f"- Exported Media: {exported_media_path}")
        if transcript_txt_ref:
            lines.append(f"- Transcript TXT: {transcript_txt_ref}")
        if transcript_json_ref:
            lines.append(f"- Transcript JSON: {transcript_json_ref}")
        if str(capture.get("transcript_note_id", "")).strip():
            lines.append(f"- Get笔记 Note ID: {capture.get('transcript_note_id')}")
    return "\n".join(lines)


def write_tencent_meeting_source_artifacts(artifact_dir: Path, capture: dict[str, Any]) -> dict[str, str]:
    source_json = {
        "page_type": "tencent_meeting_share",
        "title": capture.get("title", ""),
        "canonical_url": capture.get("canonical_url", ""),
        "metadata": {
            "source_id": capture.get("source_id", ""),
            "record_created_at": capture.get("record_created_at", ""),
            "meeting_code": capture.get("meeting_code", ""),
            "meeting_id": capture.get("meeting_id", ""),
            "recording_duration_ms": capture.get("recording_duration_ms", 0),
            "recording_size_bytes": capture.get("recording_size_bytes", 0),
            "thumbnail_url": capture.get("thumbnail_url", ""),
        },
        "status": {
            "validation_status": capture.get("validation_status", ""),
            "capture_status": capture.get("capture_status", ""),
            "transcript_status": capture.get("transcript_status", ""),
            "native_transcript_capability": capture.get("native_transcript_capability", ""),
            "native_transcript_enabled": capture.get("native_transcript_enabled", ""),
            "share_page_transcript_visible": capture.get("share_page_transcript_visible", ""),
            "transcript_access_path": capture.get("transcript_access_path", ""),
            "fallback_action": capture.get("fallback_action", ""),
        },
        "transcript": {
            "provider": capture.get("external_transcribe_provider", ""),
            "txt_ref": capture.get("transcript_txt_ref", ""),
            "json_ref": capture.get("transcript_json_ref", ""),
            "result_ref": capture.get("transcribe_result_ref", ""),
            "note_id": capture.get("transcript_note_id", ""),
            "note_url": capture.get("transcript_note_url", ""),
            "sentence_count": capture.get("transcript_sentence_count", 0),
        },
        "exported_media": {
            "path": capture.get("exported_media_path", ""),
            "size_bytes": capture.get("exported_media_size_bytes", 0),
        },
        "artifacts": {
            "source_json": str(artifact_dir / "source.json"),
            "source_markdown": str(artifact_dir / "source.md"),
            "assessment_markdown": str(artifact_dir / "tencent-meeting-assessment.md"),
            "normalized_capture": str(artifact_dir / "tencent-meeting-normalized.json"),
        },
    }
    source_json_path = artifact_dir / "source.json"
    source_md_path = artifact_dir / "source.md"
    write_json(source_json_path, source_json)
    write_text(source_md_path, render_tencent_meeting_source_markdown(capture))
    return {
        "source_json": str(source_json_path),
        "source_markdown": str(source_md_path),
    }


def load_tencent_meeting_source_record(*, source_id: str = "", link: str = "") -> dict[str, Any] | None:
    normalized_url = normalize_tencent_meeting_share_url(link)[0] if link else ""
    for item in read_knowledge_sources():
        if str(item.get("page_type", "")).strip() != "tencent_meeting_share":
            continue
        if source_id and str(item.get("source_id", "")).strip() == source_id.strip():
            return item
        if normalized_url and normalize_external_url(str(item.get("url", ""))) == normalized_url:
            return item
    return None


def latest_file_for_pattern(directory: Path, pattern: str) -> Path | None:
    matches = sorted(directory.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def probe_tencent_meeting_link(
    link: str,
    *,
    scope_path: Path | None = None,
    output_slug: str | None = None,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    original_input_url = normalize_external_url(link)
    canonical_url, short_link = normalize_tencent_meeting_share_url(original_input_url)
    scope = load_source_scope(scope_path)
    slug = output_slug or slugify(short_link or canonical_url)
    artifact_dir = Path(scope.get("tencent_meeting_ingest_root", str(DEFAULT_TENCENT_MEETING_INGEST_ROOT))).expanduser().resolve() / slug
    artifact_dir.mkdir(parents=True, exist_ok=True)

    raw_json_path = artifact_dir / "tencent-meeting-raw.json"
    normalized_json_path = artifact_dir / "tencent-meeting-normalized.json"
    assessment_md_path = artifact_dir / "tencent-meeting-assessment.md"
    original_html_path = artifact_dir / "original.html"
    canonical_html_path = artifact_dir / "canonical.html"
    validation_result_path = artifact_dir / "validation-result.json"

    original_fetch = fetch_http_document(original_input_url, timeout_seconds=timeout_seconds)
    js_redirect_url = first_match(
        original_fetch.get("body", ""),
        [
            r'window\.location\.replace\("([^"]+)"\)',
            r'"redirectUrl":"([^"]+)"',
        ],
    )
    if js_redirect_url:
        canonical_url, inferred_short_link = normalize_tencent_meeting_share_url(js_redirect_url)
        short_link = short_link or inferred_short_link

    final_fetch = original_fetch
    if canonical_url != original_input_url:
        final_fetch = fetch_http_document(canonical_url, timeout_seconds=timeout_seconds)

    original_html_path.write_text(original_fetch.get("body", ""), encoding="utf-8")
    canonical_html_path.write_text(final_fetch.get("body", ""), encoding="utf-8")

    html_body = final_fetch.get("body", "")
    created_at_raw = first_match(
        html_body,
        [r"创建时间(?:<!-- -->)?：(?:<!-- -->)?([0-9]{4}[/-][0-9]{2}[/-][0-9]{2} [0-9]{2}:[0-9]{2})"],
    )
    title = first_match(
        html_body,
        [
            r'font-weight:600">([^<]+)</span>',
            r'class="record-detail-title_recordTitle__[^"]*">([^<]+)</',
            r"<title>([^<]+)</title>",
        ],
    )
    meeting_code = first_json_string_value(html_body, "meeting_code")
    meeting_id = first_json_string_value(html_body, "meeting_id")
    recording_duration = first_json_int_string_value(html_body, "total_recording_duration", "recording_duration", "duration")
    recording_size = first_json_int_string_value(html_body, "total_recording_size", "recording_size", "size")
    start_time_ms = first_json_int_string_value(html_body, "recording_start_time", "start_time")
    minutes_status_raw = first_json_numeric_value(html_body, "minutes_status")
    minutes_exportable_raw = first_json_numeric_value(html_body, "minutes_exportable")
    thumbnail_url = first_match(
        html_body,
        [
            r'"cover_url":"([^"]+)"',
            r'\\"cover_url\\":\\"([^"\\]+)\\"',
            r"background-image:url\((https?://[^)]+)\)",
            r'"shortcut_url":"([^"]+)"',
        ],
    )
    visible_text = extract_tencent_meeting_visible_text(html_body)
    non_boilerplate_text = strip_tencent_meeting_boilerplate(visible_text, title=title, created_at_raw=created_at_raw)
    meaningful_text_present = is_meaningful_tencent_meeting_text(non_boilerplate_text)
    has_empty_text_marker = "暂无文本内容" in html_body or "in-conversion-empty" in html_body
    tab_labels = [label for label in ["转写", "纪要", "章节", "发言人", "话题"] if label in html_body or label in visible_text]
    has_content_tabs = bool(tab_labels)
    transcript_status = "unknown"
    if has_empty_text_marker:
        transcript_status = "empty"
    elif meaningful_text_present:
        transcript_status = "present"
    elif final_fetch.get("status_code", 0) == 200 and (title or meeting_code or meeting_id):
        transcript_status = "empty"
    media_url = first_match(
        html_body,
        [
            r'(https?://[^"\')\s]+\.m3u8[^"\')\s]*)',
            r'(https?://[^"\')\s]+\.mp4[^"\')\s]*)',
            r'"(?:video_url|media_url|play_url)":"([^"]+)"',
        ],
    )
    invalid_markers = [
        "您来到了一个还没有人开会的星球",
        "页面不存在",
        "链接已失效",
        "分享已关闭",
    ]
    gated_markers = ["登录后查看", "扫码登录", "无权访问", "访问受限", "需要登录"]
    disabled_markers = [
        "未开启转写",
        "暂未开启转写",
        "转写已关闭",
        "未开启纪要",
        "暂未开启纪要",
        "纪要已关闭",
        "主持人未开启文字转写",
        "主持人未开启纪要",
    ]
    share_invalid_or_expired = final_fetch.get("status_code", 0) >= 400 or any(marker in html_body for marker in invalid_markers)
    auth_required = (not share_invalid_or_expired) and any(marker in html_body for marker in gated_markers)
    page_accessible = final_fetch.get("status_code", 0) == 200 and not share_invalid_or_expired
    if auth_required:
        capture_status = "gated"
    elif share_invalid_or_expired:
        capture_status = "expired"
    elif page_accessible:
        capture_status = "accessible"
    else:
        capture_status = "failed"
    media_url_present = bool(media_url)
    transcript_present = transcript_status == "present"
    minutes_status_enabled = minutes_status_raw.isdigit() and int(minutes_status_raw) > 0
    minutes_exportable_enabled = minutes_exportable_raw.isdigit() and int(minutes_exportable_raw) > 0
    minutes_present = ("纪要" in tab_labels) or ("摘要和待办" in html_body) or minutes_status_enabled or minutes_exportable_enabled
    native_transcript_capability = "supported"
    if any(marker in html_body for marker in disabled_markers):
        native_transcript_enabled = "disabled"
    elif transcript_present or has_empty_text_marker or has_content_tabs or minutes_status_enabled or minutes_exportable_enabled:
        native_transcript_enabled = "enabled"
    else:
        native_transcript_enabled = "unknown"
    if capture_status == "gated":
        share_page_transcript_visible = "gated"
    elif transcript_present:
        share_page_transcript_visible = "visible"
    elif page_accessible and (native_transcript_enabled in {"enabled", "disabled"} or transcript_status == "empty"):
        share_page_transcript_visible = "hidden"
    else:
        share_page_transcript_visible = "unknown"
    if share_page_transcript_visible == "visible":
        transcript_access_path = "share_page"
        fallback_action = "none"
    elif share_page_transcript_visible == "gated":
        transcript_access_path = "login_probe"
        fallback_action = "permission_probe"
    elif native_transcript_enabled == "enabled" and share_page_transcript_visible == "hidden":
        transcript_access_path = "login_probe"
        fallback_action = "browser_probe"
    elif media_url_present:
        transcript_access_path = "external_transcribe"
        fallback_action = "external_transcribe"
    elif native_transcript_enabled == "disabled":
        transcript_access_path = "external_transcribe"
        fallback_action = "export_media"
    elif capture_status == "failed" or transcript_status == "unknown":
        transcript_access_path = "login_probe"
        fallback_action = "browser_probe"
    elif page_accessible:
        transcript_access_path = "external_transcribe"
        fallback_action = "export_media"
    else:
        transcript_access_path = "login_probe"
        fallback_action = "none"
    validation_status = infer_tencent_meeting_validation_status(capture_status)
    record_created_at = ""
    if created_at_raw:
        parsed_created_at = datetime.strptime(created_at_raw, "%Y/%m/%d %H:%M")
        record_created_at = parsed_created_at.replace(tzinfo=TIMEZONE).isoformat(timespec="seconds")
    elif start_time_ms.isdigit():
        record_created_at = datetime.fromtimestamp(int(start_time_ms) / 1000, tz=TIMEZONE).isoformat(timespec="seconds")

    raw_capture = {
        "input_url": original_input_url,
        "canonical_url": canonical_url,
        "short_link": short_link,
        "redirect_chain": unique_strings(
            [
                original_input_url,
                original_fetch.get("final_url", ""),
                js_redirect_url,
                canonical_url,
                final_fetch.get("final_url", ""),
            ]
        ),
        "js_redirect_url": js_redirect_url,
        "original_fetch": {
            "ok": original_fetch.get("ok", False),
            "status_code": original_fetch.get("status_code", 0),
            "final_url": original_fetch.get("final_url", ""),
            "error": original_fetch.get("error", ""),
            "headers": original_fetch.get("headers", {}),
            "html_path": str(original_html_path),
        },
        "canonical_fetch": {
            "ok": final_fetch.get("ok", False),
            "status_code": final_fetch.get("status_code", 0),
            "final_url": final_fetch.get("final_url", ""),
            "error": final_fetch.get("error", ""),
            "headers": final_fetch.get("headers", {}),
            "html_path": str(canonical_html_path),
        },
        "key_ssr_fragments": {
            "title_fragment": title,
            "created_at_fragment": created_at_raw,
            "start_time_ms_fragment": start_time_ms,
            "tab_labels_present": has_content_tabs,
            "empty_text_marker": has_empty_text_marker,
            "minutes_status": minutes_status_raw,
            "minutes_exportable": minutes_exportable_raw,
            "native_transcript_enabled": native_transcript_enabled,
            "share_page_transcript_visible": share_page_transcript_visible,
        },
    }

    normalized_capture = {
        "source_url": canonical_url,
        "original_input_url": original_input_url,
        "source_platform": "tencent_meeting",
        "source_kind": "tencent_meeting_share",
        "source_id": short_link or stable_id("tmshare", canonical_url),
        "title": title or f"Tencent Meeting share {short_link or 'unknown'}",
        "canonical_url": canonical_url,
        "record_created_at": record_created_at,
        "meeting_code": meeting_code,
        "meeting_id": meeting_id,
        "recording_duration_ms": int(recording_duration) if recording_duration.isdigit() else 0,
        "recording_size_bytes": int(recording_size) if recording_size.isdigit() else 0,
        "thumbnail_url": thumbnail_url,
        "page_accessible": page_accessible,
        "transcript_present": transcript_present,
        "minutes_present": minutes_present,
        "media_url_present": media_url_present,
        "auth_required": auth_required,
        "share_invalid_or_expired": share_invalid_or_expired,
        "transcript_status": transcript_status,
        "native_transcript_capability": native_transcript_capability,
        "native_transcript_enabled": native_transcript_enabled,
        "share_page_transcript_visible": share_page_transcript_visible,
        "transcript_access_path": transcript_access_path,
        "capture_status": capture_status,
        "fallback_action": fallback_action,
        "validation_status": validation_status,
        "tab_labels": tab_labels,
        "text_excerpt": non_boilerplate_text[:240],
        "media_url": media_url,
    }
    normalized_capture["can_use_as_primary_material"] = can_use_as_primary_material(normalized_capture)

    write_json(raw_json_path, raw_capture)
    write_json(normalized_json_path, normalized_capture)
    write_text(assessment_md_path, render_tencent_meeting_assessment(normalized_capture, input_url=original_input_url))
    source_artifacts = write_tencent_meeting_source_artifacts(artifact_dir, normalized_capture)

    notes = (
        f"capture_status={capture_status}; transcript_status={transcript_status}; "
        f"native_transcript_enabled={native_transcript_enabled}; "
        f"share_page_transcript_visible={share_page_transcript_visible}; "
        f"fallback_action={fallback_action}; title={normalized_capture['title']}"
    )
    validated_at = iso_now()
    entry = {
        "id": stable_id("ksrc", canonical_url),
        "source_id": normalized_capture["source_id"],
        "title": normalized_capture["title"],
        "url": canonical_url,
        "canonical_url": canonical_url,
        "page_type": "tencent_meeting_share",
        "source_role": "meeting_record_material",
        "validation_status": validation_status,
        "auth_mode_used": "anonymous_http" if page_accessible and not auth_required else "",
        "artifact_dir": str(artifact_dir),
        "notes": notes,
        "last_validated_at": validated_at,
        "updated_at": validated_at,
        "source_platform": "tencent_meeting",
        "source_kind": "tencent_meeting_share",
        "record_created_at": record_created_at,
        "meeting_code": meeting_code,
        "meeting_id": meeting_id,
        "recording_duration_ms": normalized_capture["recording_duration_ms"],
        "recording_size_bytes": normalized_capture["recording_size_bytes"],
        "thumbnail_url": thumbnail_url,
        "page_accessible": page_accessible,
        "transcript_status": transcript_status,
        "native_transcript_capability": native_transcript_capability,
        "native_transcript_enabled": native_transcript_enabled,
        "share_page_transcript_visible": share_page_transcript_visible,
        "transcript_access_path": transcript_access_path,
        "capture_status": capture_status,
        "fallback_action": fallback_action,
        "media_url_present": media_url_present,
        "transcript_present": transcript_present,
        "minutes_present": minutes_present,
        "auth_required": auth_required,
        "share_invalid_or_expired": share_invalid_or_expired,
        "can_use_as_primary_material": normalized_capture["can_use_as_primary_material"],
        "normalized_capture_ref": str(normalized_json_path),
        "raw_capture_ref": str(raw_json_path),
        "assessment_ref": str(assessment_md_path),
        "source_json_ref": source_artifacts["source_json"],
        "source_markdown_ref": source_artifacts["source_markdown"],
    }
    result = {
        "ok": page_accessible,
        "validation_status": validation_status,
        "source_id": normalized_capture["source_id"],
        "normalized_url": canonical_url,
        "artifact_dir": str(artifact_dir),
        "raw_capture": raw_capture,
        "normalized_capture": normalized_capture,
        "artifacts": {
            "raw_json": str(raw_json_path),
            "normalized_json": str(normalized_json_path),
            "assessment_markdown": str(assessment_md_path),
            "source_json": source_artifacts["source_json"],
            "source_markdown": source_artifacts["source_markdown"],
            "original_html": str(original_html_path),
            "canonical_html": str(canonical_html_path),
        },
        "knowledge_source": entry,
    }
    write_json(validation_result_path, result)
    upsert_knowledge_source(
        scope_path=scope_path,
        normalized_url=canonical_url,
        entry=entry,
        scope_key="source_tencent_meeting_links",
    )
    return result


def transcribe_tencent_meeting_file(
    *,
    file_path: str,
    source_id: str = "",
    link: str = "",
    scope_path: Path | None = None,
    timeout_seconds: int = 1800,
) -> dict[str, Any]:
    source = load_tencent_meeting_source_record(source_id=source_id, link=link)
    if not source:
        lookup = source_id or normalize_tencent_meeting_share_url(link)[0] or file_path
        return {
            "ok": False,
            "error": f"tencent_meeting_source_not_found:{lookup}",
        }

    media_path = Path(file_path).expanduser().resolve()
    if not media_path.exists():
        return {
            "ok": False,
            "error": f"media_file_missing:{media_path}",
            "source_id": str(source.get("source_id", "")).strip(),
        }

    script_path = resolve_get_biji_transcript_script()
    if not script_path.exists():
        return {
            "ok": False,
            "error": f"get_biji_transcript_script_missing:{script_path}",
            "source_id": str(source.get("source_id", "")).strip(),
        }

    artifact_dir = Path(str(source.get("artifact_dir", "")).strip()).expanduser().resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    transcribe_dir = artifact_dir / "external-transcribe"
    transcribe_dir.mkdir(parents=True, exist_ok=True)
    media_record_path = artifact_dir / "exported-media.json"

    media_record = {
        "source_id": str(source.get("source_id", "")).strip(),
        "canonical_url": str(source.get("canonical_url") or source.get("url") or "").strip(),
        "input_file": str(media_path),
        "file_name": media_path.name,
        "size_bytes": media_path.stat().st_size,
        "registered_at": iso_now(),
    }
    write_json(media_record_path, media_record)

    command = [
        sys.executable,
        str(script_path),
        "transcribe-file",
        "--file",
        str(media_path),
        "--output-dir",
        str(transcribe_dir),
        "--timeout-seconds",
        str(timeout_seconds),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)

    result_json_path = latest_file_for_pattern(transcribe_dir, "transcribe-file-result-*.json")
    transcript_json_path = latest_file_for_pattern(transcribe_dir, "transcript-*.json")
    transcript_txt_path = latest_file_for_pattern(transcribe_dir, "transcript-*.txt")

    if completed.returncode != 0 or not (result_json_path and transcript_json_path and transcript_txt_path):
        failed_result = {
            "ok": False,
            "source_id": str(source.get("source_id", "")).strip(),
            "artifact_dir": str(artifact_dir),
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "transcribe_artifact_dir": str(transcribe_dir),
            "exported_media_record": str(media_record_path),
        }
        write_json(artifact_dir / "external-transcribe-result.json", failed_result)
        return failed_result

    transcribe_result = read_json(result_json_path, default={})
    transcript_payload = read_json(transcript_json_path, default={})
    sentence_count = int(transcript_payload.get("sentence_count", 0) or 0)

    normalized_capture_ref = str(source.get("normalized_capture_ref", "")).strip()
    normalized_json_path = Path(normalized_capture_ref).expanduser().resolve() if normalized_capture_ref else artifact_dir / "tencent-meeting-normalized.json"
    normalized_capture = read_json(normalized_json_path, default={}) if normalized_capture_ref else {}
    if not normalized_capture:
        normalized_capture = {
            "source_url": str(source.get("url", "")).strip(),
            "canonical_url": str(source.get("canonical_url", "")).strip(),
            "source_platform": "tencent_meeting",
            "source_kind": "tencent_meeting_share",
            "source_id": str(source.get("source_id", "")).strip(),
            "title": str(source.get("title", "")).strip(),
            "record_created_at": str(source.get("record_created_at", "")).strip(),
            "meeting_code": str(source.get("meeting_code", "")).strip(),
            "meeting_id": str(source.get("meeting_id", "")).strip(),
            "recording_duration_ms": int(source.get("recording_duration_ms", 0) or 0),
            "recording_size_bytes": int(source.get("recording_size_bytes", 0) or 0),
            "thumbnail_url": str(source.get("thumbnail_url", "")).strip(),
            "page_accessible": bool(source.get("page_accessible", False)),
            "minutes_present": bool(source.get("minutes_present", False)),
            "media_url_present": bool(source.get("media_url_present", False)),
            "auth_required": bool(source.get("auth_required", False)),
            "share_invalid_or_expired": bool(source.get("share_invalid_or_expired", False)),
            "native_transcript_capability": str(source.get("native_transcript_capability", "supported")).strip() or "supported",
            "native_transcript_enabled": str(source.get("native_transcript_enabled", "unknown")).strip() or "unknown",
            "share_page_transcript_visible": str(source.get("share_page_transcript_visible", "unknown")).strip() or "unknown",
            "transcript_access_path": str(source.get("transcript_access_path", "external_transcribe")).strip() or "external_transcribe",
            "capture_status": str(source.get("capture_status", "")).strip(),
            "validation_status": str(source.get("validation_status", "")).strip(),
        }

    updated_at = iso_now()
    normalized_capture.update(
        {
            "transcript_present": True,
            "transcript_status": "present",
            "transcript_access_path": "external_transcribe",
            "fallback_action": "none",
            "validation_status": "validated",
            "external_transcribe_provider": "get_biji_transcript",
            "transcribe_result_ref": str(result_json_path),
            "transcript_json_ref": str(transcript_json_path),
            "transcript_txt_ref": str(transcript_txt_path),
            "transcript_note_id": str(transcribe_result.get("note_id", "")).strip(),
            "transcript_note_url": str(transcribe_result.get("note_url", "")).strip(),
            "transcript_sentence_count": sentence_count,
            "transcript_generated_at": updated_at,
            "exported_media_path": str(media_path),
            "exported_media_size_bytes": media_path.stat().st_size,
            "exported_media_record_ref": str(media_record_path),
            "text_excerpt": Path(transcript_txt_path).read_text(encoding="utf-8")[:240].strip(),
        }
    )
    normalized_capture["can_use_as_primary_material"] = can_use_as_primary_material(normalized_capture)

    notes = (
        f"capture_status={normalized_capture.get('capture_status', '')}; transcript_status=present; "
        f"native_transcript_enabled={normalized_capture.get('native_transcript_enabled', '')}; "
        f"share_page_transcript_visible={normalized_capture.get('share_page_transcript_visible', '')}; "
        f"fallback_action=none; title={normalized_capture.get('title', '')}; "
        f"transcript_provider=get_biji_transcript"
    )
    updated_entry = {
        **source,
        "validation_status": "validated",
        "notes": notes,
        "updated_at": updated_at,
        "last_validated_at": updated_at,
        "transcript_status": "present",
        "transcript_present": True,
        "transcript_access_path": "external_transcribe",
        "fallback_action": "none",
        "normalized_capture_ref": str(normalized_json_path),
        "assessment_ref": str(artifact_dir / "tencent-meeting-assessment.md"),
        "transcribe_result_ref": str(result_json_path),
        "transcript_json_ref": str(transcript_json_path),
        "transcript_txt_ref": str(transcript_txt_path),
        "transcript_note_id": str(transcribe_result.get("note_id", "")).strip(),
        "transcript_note_url": str(transcribe_result.get("note_url", "")).strip(),
        "transcript_sentence_count": sentence_count,
        "external_transcribe_provider": "get_biji_transcript",
        "transcript_generated_at": updated_at,
        "exported_media_path": str(media_path),
        "exported_media_size_bytes": media_path.stat().st_size,
        "exported_media_record_ref": str(media_record_path),
    }

    write_json(normalized_json_path, normalized_capture)
    write_text(
        artifact_dir / "tencent-meeting-assessment.md",
        render_tencent_meeting_assessment(
            normalized_capture,
            input_url=str(normalized_capture.get("original_input_url") or normalized_capture.get("canonical_url") or ""),
        ),
    )
    source_artifacts = write_tencent_meeting_source_artifacts(artifact_dir, normalized_capture)
    updated_entry["source_json_ref"] = source_artifacts["source_json"]
    updated_entry["source_markdown_ref"] = source_artifacts["source_markdown"]

    result = {
        "ok": True,
        "source_id": str(source.get("source_id", "")).strip(),
        "artifact_dir": str(artifact_dir),
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "normalized_capture": normalized_capture,
        "knowledge_source": updated_entry,
        "artifacts": {
            "transcribe_result_json": str(result_json_path),
            "transcript_json": str(transcript_json_path),
            "transcript_txt": str(transcript_txt_path),
            "exported_media_record": str(media_record_path),
            "source_json": source_artifacts["source_json"],
            "source_markdown": source_artifacts["source_markdown"],
            "assessment_markdown": str(artifact_dir / "tencent-meeting-assessment.md"),
            "normalized_json": str(normalized_json_path),
        },
    }
    write_json(artifact_dir / "external-transcribe-result.json", result)
    write_json(artifact_dir / "validation-result.json", result)
    upsert_knowledge_source(
        scope_path=scope_path,
        normalized_url=normalize_external_url(str(updated_entry.get("url", "")).strip()),
        entry=updated_entry,
        scope_key="source_tencent_meeting_links",
    )
    return result


def validate_knowledge_source(
    url: str,
    *,
    scope_path: Path | None = None,
    headed: bool = False,
    output_slug: str = "yuanli-planet-shared",
    manual_confirmed: bool = False,
    manual_title: str = "",
    manual_note: str = "",
) -> dict[str, Any]:
    normalized_url = normalize_external_url(url)
    scope = load_source_scope(scope_path)
    artifact_dir = Path(scope.get("feishu_ingest_root", str(DEFAULT_FEISHU_INGEST_ROOT))).expanduser().resolve() / output_slug
    artifact_dir.mkdir(parents=True, exist_ok=True)
    result_json_path = artifact_dir / "source.json"
    result_markdown_path = artifact_dir / "source.md"
    validation_result_path = artifact_dir / "validation-result.json"

    if manual_confirmed:
        title = manual_title.strip() or "Yuanli planet shared knowledge source"
        note = manual_note.strip() or "Validated by manual browser confirmation."
        result = build_manual_validation_result(
            normalized_url=normalized_url,
            artifact_dir=artifact_dir,
            title=title,
            note=note,
        )
        write_manual_validation_artifacts(
            artifact_dir=artifact_dir,
            title=title,
            canonical_url=result["knowledge_source"]["canonical_url"],
            note=note,
        )
        write_json(validation_result_path, result)
        upsert_knowledge_source(scope_path=scope_path, normalized_url=normalized_url, entry=result["knowledge_source"])
        return result

    reader_script = resolve_feishu_reader_script()
    node_binary = resolve_node_binary()

    if node_binary is None:
        result = build_runtime_blocked_result(
            url=normalized_url,
            artifact_dir=artifact_dir,
            notes="node runtime not found; checked PATH and ~/.local node installs.",
        )
        write_json(validation_result_path, result)
        upsert_knowledge_source(scope_path=scope_path, normalized_url=normalized_url, entry=result["knowledge_source"])
        return result

    if not reader_script.exists():
        result = build_runtime_blocked_result(
            url=normalized_url,
            artifact_dir=artifact_dir,
            notes=f"feishu-reader script not found: {reader_script}",
        )
        write_json(validation_result_path, result)
        upsert_knowledge_source(scope_path=scope_path, normalized_url=normalized_url, entry=result["knowledge_source"])
        return result

    runtime_script = materialize_feishu_reader_runtime(reader_script)

    command = [
        str(node_binary),
        str(runtime_script),
        "--url",
        normalized_url,
        "--output-dir",
        str(artifact_dir),
        "--json-out",
        str(result_json_path),
        "--md-out",
        str(result_markdown_path),
    ]
    if headed:
        command.append("--headed")

    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    extraction = read_json(result_json_path, default={}) if result_json_path.exists() else {}

    if extraction:
        validation_status = map_extraction_status(str(extraction.get("status", "")))
        title = str(extraction.get("title") or extraction.get("metadata", {}).get("og_title") or "Yuanli planet shared knowledge source")
        auth_mode_used = str(extraction.get("auth_mode_used", ""))
        notes = str(extraction.get("status", "unknown"))
        canonical_url = str(extraction.get("canonical_url", ""))
    else:
        stderr = completed.stderr.strip()
        validation_status = "blocked_runtime_missing" if (
            "Could not import playwright" in stderr
            or "Cannot find package 'playwright'" in stderr
            or "playwright" in stderr.lower()
        ) else "empty_extraction"
        title = "Yuanli planet shared knowledge source"
        auth_mode_used = ""
        notes = stderr or completed.stdout.strip() or "feishu-reader did not produce a JSON artifact."
        canonical_url = ""

    validated_at = iso_now()
    source_id = stable_id("ksrc", normalized_url)
    entry = {
        "id": source_id,
        "source_id": source_id,
        "title": title,
        "url": normalized_url,
        "canonical_url": canonical_url,
        "page_type": str(extraction.get("page_type", "wiki") or "wiki"),
        "source_role": "shared_kb_candidate",
        "validation_status": validation_status,
        "auth_mode_used": auth_mode_used,
        "artifact_dir": str(artifact_dir),
        "notes": notes,
        "last_validated_at": validated_at,
        "updated_at": validated_at,
    }
    result = {
        "ok": validation_status == "validated",
        "validation_status": validation_status,
        "source_id": source_id,
        "normalized_url": normalized_url,
        "artifact_dir": str(artifact_dir),
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "artifact_json": str(result_json_path) if result_json_path.exists() else "",
        "artifact_markdown": str(result_markdown_path) if result_markdown_path.exists() else "",
        "knowledge_source": entry,
    }
    write_json(validation_result_path, result)
    upsert_knowledge_source(scope_path=scope_path, normalized_url=normalized_url, entry=entry)
    return result


def build_governance_summary(inventory: dict[str, Any]) -> dict[str, Any]:
    skills_by_cluster = Counter(item["cluster"] for item in inventory["skills"])
    active_threads = [item for item in inventory["threads"] if item["status"] == "active"]
    blocked_tasks = [item for item in inventory["tasks"] if item["verification_state"] != "verified_or_closed"]
    active_operational_threads = [
        item for item in active_threads if "operational ontology" in str(item.get("title", "")).lower()
    ]
    pending_decisions = [
        item for item in inventory.get("decision_records", [])
        if str(item.get("decision_state", "")).strip() not in {"approved", "rejected", "archived"}
    ]
    recent_writebacks = sorted(
        inventory.get("writeback_events", []),
        key=lambda item: str(item.get("writeback_time", "")),
        reverse=True,
    )[:5]
    subject_index = {item["subject_id"]: item for item in inventory["subjects"]}
    human_owned_modules = {
        item["to_id"]
        for item in inventory["relations"]
        if item["relation_type"] == "subject_responsible_for_module"
        and subject_index.get(item["from_id"], {}).get("subject_type") == "human"
    }
    ai_staffed_modules = {
        item["to_id"]
        for item in inventory["relations"]
        if item["relation_type"] == "ai_agent_copilots_module"
        and subject_index.get(item["from_id"], {}).get("subject_type") == "ai_agent"
    }
    controlled_accounts = {
        item["to_id"] for item in inventory["relations"] if item["relation_type"] == "subject_controls_account"
    }
    client_spaces = [
        item for item in inventory["spaces"] if item.get("federation_role") in {"client", "downstream"}
    ]
    fully_staffed_modules = human_owned_modules & ai_staffed_modules
    return {
        "generated_at": inventory["generated_at"],
        "counts": inventory["counts"],
        "skills_by_cluster": dict(skills_by_cluster),
        "space_count": len(inventory["spaces"]),
        "subject_count": len(inventory["subjects"]),
        "endpoint_count": len(inventory["endpoints"]),
        "account_count": len(inventory["accounts"]),
        "source_feed_count": len(inventory.get("source_feeds", [])),
        "ingestion_run_count": len(inventory.get("ingestion_runs", [])),
        "order_count": len(inventory.get("orders", [])),
        "cashflow_count": len(inventory.get("cashflows", [])),
        "module_coverage": {
            "total": len(inventory["operating_modules"]),
            "human_owned": len(human_owned_modules),
            "ai_copilot_ready": len(ai_staffed_modules),
            "fully_staffed": len(fully_staffed_modules),
        },
        "active_thread_count": len(active_threads),
        "blocked_task_count": len(blocked_tasks),
        "controlled_account_count": len(controlled_accounts),
        "client_space_count": len(client_spaces),
        "top_active_threads": [item["title"] for item in active_threads[:5]],
        "top_active_operational_threads": [item["title"] for item in active_operational_threads[:5]],
        "action_catalog": [item["action_id"] for item in inventory.get("actions", [])],
        "action_count": len(inventory.get("actions", [])),
        "pending_decision_count": len(pending_decisions),
        "top_pending_decisions": [item["title"] for item in pending_decisions[:5]],
        "recent_writeback_count": len(inventory.get("writeback_events", [])),
        "recent_writebacks": [
            {
                "writeback_id": item["writeback_id"],
                "action_id": item["action_id"],
                "verification_state": item["verification_state"],
            }
            for item in recent_writebacks
        ],
        "top_blocked_tasks": [item["title"] for item in blocked_tasks[:5]],
    }


def render_governance_overview(inventory: dict[str, Any]) -> str:
    summary = build_governance_summary(inventory)
    active_threads = [item for item in inventory["threads"] if item["status"] == "active"][:5]
    blocked_tasks = [item for item in inventory["tasks"] if item["verification_state"] != "verified_or_closed"][:5]
    active_operational_threads = [
        item for item in inventory["threads"] if item["status"] == "active" and "operational ontology" in str(item.get("title", "")).lower()
    ][:5]
    pending_decisions = [
        item
        for item in inventory.get("decision_records", [])
        if str(item.get("decision_state", "")).strip() not in {"approved", "rejected", "archived"}
    ][:5]
    recent_writebacks = sorted(
        inventory.get("writeback_events", []),
        key=lambda item: str(item.get("writeback_time", "")),
        reverse=True,
    )[:5]
    modules = inventory["operating_modules"][:6]
    module_owner_map = {
        item["to_id"]: item["from_id"]
        for item in inventory["relations"]
        if item["relation_type"] == "subject_responsible_for_module"
    }
    module_agent_map = {
        item["to_id"]: item["from_id"]
        for item in inventory["relations"]
        if item["relation_type"] == "ai_agent_copilots_module"
    }
    subject_titles = {item["subject_id"]: item["title"] for item in inventory["subjects"]}
    lines = [
        "# 原力全体系治理总览",
        "",
        f"- 生成时间: {inventory['generated_at']}",
        f"- 联邦实例数: {summary['space_count']}",
        f"- 主体数: {summary['subject_count']}",
        f"- 终端数: {summary['endpoint_count']}",
        f"- 账号数: {summary['account_count']}",
        f"- 来源数: {summary['source_feed_count']}",
        f"- 模块覆盖: {summary['module_coverage']['fully_staffed']}/{summary['module_coverage']['total']}",
        f"- 资产数: {inventory['counts']['assets']}",
        f"- 订单数: {summary['order_count']}",
        f"- 现金流数: {summary['cashflow_count']}",
        f"- 任务数: {inventory['counts']['tasks']}",
        f"- 线程数: {inventory['counts']['threads']}",
        f"- 技能数: {inventory['counts']['skills']}",
        f"- 动作数: {inventory['counts'].get('actions', 0)}",
        f"- 决策数: {inventory['counts'].get('decision_records', 0)}",
        f"- 写回事件数: {inventory['counts'].get('writeback_events', 0)}",
        f"- 晨会/Review 数: {inventory['counts']['review_runs']}",
        "",
        "## 联邦实例",
    ]
    lines.extend(
        f"- {item['title']} [{item['space_type']}] :: {item.get('federation_role', 'unknown')}"
        for item in inventory["spaces"]
    )
    lines.extend(["", "## 模块责任覆盖"])
    for module in modules:
        lines.append(
            f"- {module['title']} :: human={subject_titles.get(module_owner_map.get(module['module_id'], ''), '缺失')} :: ai={subject_titles.get(module_agent_map.get(module['module_id'], ''), '缺失')}"
        )
    lines.extend(["", "## 当前活跃线程"])
    if active_threads:
        lines.extend(f"- {item['title']} [{item['goal_id'] or '无目标'}]" for item in active_threads)
    else:
        lines.append("- 当前没有活跃线程。")
    lines.extend(["", "## 当前 Active Operational Thread"])
    if active_operational_threads:
        lines.extend(f"- {item['title']} [{item['goal_id'] or '无目标'}]" for item in active_operational_threads)
    else:
        lines.append("- 当前没有识别到 operational ontology 主线程。")
    lines.extend(["", "## 当前 Action Catalog"])
    if inventory.get("actions"):
        lines.extend(
            f"- {item['action_id']} :: {item['target_entity_type']} :: approval={'yes' if item.get('requires_human_approval') else 'no'}"
            for item in inventory["actions"]
        )
    else:
        lines.append("- 当前没有初始化 action catalog。")
    lines.extend(["", "## 当前 Pending Decisions"])
    if pending_decisions:
        lines.extend(
            f"- {item['title']} :: {item['decision_type']} :: {item['decision_state']}"
            for item in pending_decisions
        )
    else:
        lines.append("- 当前没有待审批决策。")
    lines.extend(["", "## 最近 Writeback Events"])
    if recent_writebacks:
        lines.extend(
            f"- {item['writeback_id']} :: {item['action_id']} :: {item['verification_state']}"
            for item in recent_writebacks
        )
    else:
        lines.append("- 当前没有写回记录。")
    lines.extend(["", "## 当前待跟进任务"])
    if blocked_tasks:
        lines.extend(f"- {item['title']} :: {item['next_action'] or '待补下一步'}" for item in blocked_tasks)
    else:
        lines.append("- 当前没有待跟进任务。")
    lines.extend(["", "## 技能簇分布"])
    for cluster, count in sorted(summary["skills_by_cluster"].items()):
        lines.append(f"- {cluster}: {count}")
    lines.extend(["", "## 来源覆盖"])
    for item in inventory.get("source_feeds", [])[:8]:
        lines.append(
            f"- {item['title']} :: family={item['source_family']} :: recognized={item['recognized_file_count']} :: unclassified={item['unclassified_file_count']}"
        )
    return "\n".join(lines)


def ensure_inventory(scope_path: Path | None = None) -> dict[str, Any]:
    latest = read_json(CANONICAL_ROOT / "snapshots" / "latest.json", default=None)
    required_keys = {"spaces", "subjects", "endpoints", "accounts", "operating_modules"}
    if latest and required_keys.issubset(latest.keys()):
        return latest
    return build_inventory(scope_path)


def default_candidate_actions(inventory: dict[str, Any]) -> list[dict[str, str]]:
    active_threads = [item for item in inventory["threads"] if item["status"] == "active"]
    blocked_tasks = [item for item in inventory["tasks"] if item["verification_state"] != "verified_or_closed"]
    weak_cluster = min(
        Counter(item["cluster"] for item in inventory["skills"]).items(),
        key=lambda pair: pair[1],
        default=("未分组", 0),
    )[0]
    return [
        {
            "id": "A",
            "title": "先处理最高优先级活跃线程",
            "problem": active_threads[0]["title"] if active_threads else "当前没有被识别的活跃线程",
            "recommended_next_step": active_threads[0]["next_review_date"] if active_threads else "补建专题线程",
        },
        {
            "id": "B",
            "title": "先清理待跟进任务的证据缺口",
            "problem": blocked_tasks[0]["title"] if blocked_tasks else "当前没有待跟进任务",
            "recommended_next_step": blocked_tasks[0]["next_action"] if blocked_tasks else "检查验真链路",
        },
        {
            "id": "C",
            "title": "先补治理能力薄弱簇",
            "problem": weak_cluster,
            "recommended_next_step": "补强薄弱簇的输出契约或边界说明",
        },
    ]


def generate_morning_review(scope_path: Path | None = None) -> dict[str, Any]:
    scope = load_source_scope(scope_path)
    inventory = ensure_inventory(scope_path)
    latest_review = load_latest_review(scope)
    latest_skill_scout = load_latest_skill_scout(scope)
    candidate_actions = latest_review.get("candidate_actions") or default_candidate_actions(inventory)
    candidate_actions = candidate_actions[:3]
    active_threads = [item for item in inventory["threads"] if item["status"] == "active"]
    blocked_tasks = [item for item in inventory["tasks"] if item["verification_state"] != "verified_or_closed"]
    structure_changes = [
        "canonical counts: "
        f"spaces={inventory['counts']['spaces']}, subjects={inventory['counts']['subjects']}, endpoints={inventory['counts']['endpoints']}, "
        f"accounts={inventory['counts']['accounts']}, modules={inventory['counts']['operating_modules']}, source_feeds={inventory['counts'].get('source_feeds', 0)}, "
        f"assets={inventory['counts']['assets']}, orders={inventory['counts'].get('orders', 0)}, cashflows={inventory['counts'].get('cashflows', 0)}, "
        f"tasks={inventory['counts']['tasks']}, threads={inventory['counts']['threads']}, skills={inventory['counts']['skills']}",
        f"active threads={len(active_threads)}, pending follow-up tasks={len(blocked_tasks)}, client spaces={len([item for item in inventory['spaces'] if item.get('federation_role') in {'client', 'downstream'}])}",
        f"ontology tables={len(inventory['ontology_summary'].get('tables', []))}",
    ]
    top_risks = []
    if active_threads:
        top_risks.append(f"最高优先级活跃线程仍待推进: {active_threads[0]['title']}")
    if blocked_tasks:
        top_risks.append(f"存在待补证据/待拍板任务: {blocked_tasks[0]['title']}")
    if latest_review.get("missing_middle_layer_capabilities"):
        top_risks.append(
            "治理中层缺口: " + " / ".join(latest_review["missing_middle_layer_capabilities"][:3])
        )
    if not top_risks:
        top_risks.append("当前没有显著结构性风险。")
    scout_summary = latest_skill_scout.get("summary") if isinstance(latest_skill_scout.get("summary"), dict) else {}
    shortlist_titles = scout_summary.get("shortlist_titles") if isinstance(scout_summary.get("shortlist_titles"), list) else []
    blockers = latest_skill_scout.get("env_blockers") if isinstance(latest_skill_scout.get("env_blockers"), list) else []
    external_signal_summary = [
        "今日 shortlist: " + (" / ".join(str(item) for item in shortlist_titles[:3]) if shortlist_titles else "none"),
        f"observation only={int(scout_summary.get('observation_only_count', 0))}, adoption queue={int(latest_skill_scout.get('adoption_queue_count', scout_summary.get('adoption_queue_count', 0) or 0))}",
        "env blockers=" + (" / ".join(str(item) for item in blockers) if blockers else "none"),
    ]

    recommended_action = candidate_actions[0]["id"] if candidate_actions else "A"
    review_id = f"yrgs-review-{now_local().strftime('%Y%m%d-%H%M%S')}"
    morning_review = {
        "review_id": review_id,
        "generated_at": iso_now(),
        "scope": "原力全体系治理系统专项晨会",
        "structure_changes": structure_changes,
        "external_signal_summary": external_signal_summary,
        "top_risks": top_risks,
        "candidate_actions": candidate_actions,
        "seed_watch_items": latest_skill_scout.get("seed_watch_items", []) if isinstance(latest_skill_scout.get("seed_watch_items"), list) else [],
        "adoption_queue_count": int(latest_skill_scout.get("adoption_queue_count", scout_summary.get("adoption_queue_count", 0) or 0)),
        "env_blockers": blockers,
        "waiting_choice": f"请只拍板一个动作：{recommended_action}",
        "recommended_action": recommended_action,
    }
    write_json(DERIVED_ROOT / "morning-review" / "morning-review-input.json", inventory)
    write_json(DERIVED_ROOT / "morning-review" / "morning-review.json", morning_review)
    write_text(DERIVED_ROOT / "morning-review" / "morning-review.md", render_morning_review(morning_review))
    merge_review_run(morning_review)
    return morning_review


def merge_review_run(morning_review: dict[str, Any]) -> None:
    review_runs = read_json(ENTITY_FILES["review_runs"], default=[])
    review_runs = [item for item in review_runs if item.get("review_id") != morning_review["review_id"]]
    review_runs.append(
        {
            "id": morning_review["review_id"],
            "review_id": morning_review["review_id"],
            "review_date": morning_review["generated_at"][:10],
            "scope": morning_review["scope"],
            "summary": " | ".join([*morning_review["structure_changes"][:1], *morning_review.get("external_signal_summary", [])[:1]]),
            "top_risks": morning_review["top_risks"],
            "candidate_actions": [item["title"] for item in morning_review["candidate_actions"]],
            "human_decision": "",
            "sync_state": "local_generated",
            "source_ref": str(DERIVED_ROOT / "morning-review" / "morning-review.json"),
            "confidence": 0.93,
            "updated_at": iso_now(),
        }
    )
    review_runs = sorted(review_runs, key=lambda item: item.get("review_id", ""))
    write_json(ENTITY_FILES["review_runs"], review_runs)


def render_morning_review(morning_review: dict[str, Any]) -> str:
    lines = [f"# {morning_review['scope']}", ""]
    lines.extend(["## 今日结构变化"])
    lines.extend(f"- {item}" for item in morning_review["structure_changes"])
    lines.extend(["", "## 外部线索摘要"])
    lines.extend(f"- {item}" for item in morning_review.get("external_signal_summary", []))
    lines.extend(["", "## 当前最值得关注的问题"])
    lines.extend(f"- {item}" for item in morning_review["top_risks"])
    lines.extend(["", "## 3 个候选进化动作"])
    for item in morning_review["candidate_actions"]:
        lines.append(f"- {item['id']}. {item['title']} :: {item.get('problem', '')} :: {item.get('recommended_next_step', '')}")
    lines.extend(["", "## 当前等待你做的选择", f"- {morning_review['waiting_choice']}"])
    return "\n".join(lines)


def build_dashboard_spec() -> dict[str, Any]:
    table_specs = {item["table_id"]: item for item in FEISHU_TABLE_SPECS}
    return {
        "goal": "原力全体系治理系统总览",
        "audience": ["治理负责人", "人类协作者"],
        "decision_questions": [
            {
                "id": "dq-001",
                "layer": "federation",
                "question": DASHBOARD_QUESTIONS[0],
                "metric_ids": ["space_count", "subject_count"],
                "dimension_ids": ["space_role", "subject_type"],
                "chart_preference": "table",
            },
            {
                "id": "dq-002",
                "layer": "federation",
                "question": DASHBOARD_QUESTIONS[1],
                "metric_ids": ["account_count"],
                "dimension_ids": ["account_platform", "account_status"],
                "action_target_ids": ["account_risk_queue"],
                "chart_preference": "bar_chart",
            },
            {
                "id": "dq-003",
                "layer": "federation",
                "question": DASHBOARD_QUESTIONS[2],
                "metric_ids": ["module_count"],
                "dimension_ids": ["module_status"],
                "action_target_ids": ["module_owner_gap_queue"],
                "chart_preference": "table",
            },
            {
                "id": "dq-004",
                "layer": "federation",
                "question": DASHBOARD_QUESTIONS[3],
                "metric_ids": ["ai_agent_count", "skill_count"],
                "dimension_ids": ["subject_type", "skill_cluster"],
                "action_target_ids": ["agent_skill_queue"],
                "chart_preference": "bar_chart",
            },
            {
                "id": "dq-005",
                "layer": "operations",
                "question": DASHBOARD_QUESTIONS[4],
                "metric_ids": ["active_thread_count"],
                "dimension_ids": ["thread_goal"],
                "chart_preference": "table",
            },
            {
                "id": "dq-006",
                "layer": "operations",
                "question": DASHBOARD_QUESTIONS[5],
                "metric_ids": ["task_count"],
                "dimension_ids": ["task_status"],
                "action_target_ids": ["pending_task_queue"],
                "chart_preference": "bar_chart",
            },
            {
                "id": "dq-007",
                "layer": "operations",
                "question": DASHBOARD_QUESTIONS[6],
                "metric_ids": ["skill_count"],
                "dimension_ids": ["skill_cluster"],
                "action_target_ids": ["skill_gap_queue"],
                "chart_preference": "bar_chart",
            },
            {
                "id": "dq-008",
                "layer": "operations",
                "question": DASHBOARD_QUESTIONS[7],
                "metric_ids": ["client_space_count"],
                "dimension_ids": ["space_role"],
                "action_target_ids": ["client_rollout_queue"],
                "chart_preference": "table",
            },
            {
                "id": "dq-009",
                "layer": "action",
                "question": DASHBOARD_QUESTIONS[8],
                "metric_ids": ["review_count"],
                "dimension_ids": ["review_date"],
                "chart_preference": "line_chart",
            },
            {
                "id": "dq-010",
                "layer": "action",
                "question": "今天早上 9 点要过什么，三种动作候选是什么？",
                "action_target_ids": ["today_review_queue"],
                "chart_preference": "table",
            },
        ],
        "tables": [
            {"id": table_id, "name": spec["table_name"], "grain": table_id.rstrip("s"), "fields": spec["fields"]}
            for table_id, spec in table_specs.items()
        ],
        "metrics": [
            {"id": "space_count", "name": "联邦实例数", "table_id": "spaces", "aggregation": "count"},
            {"id": "subject_count", "name": "主体数", "table_id": "subjects", "aggregation": "count"},
            {"id": "ai_agent_count", "name": "AI Agent 数", "table_id": "subjects", "aggregation": "count"},
            {"id": "account_count", "name": "账号数", "table_id": "accounts", "aggregation": "count"},
            {"id": "module_count", "name": "模块数", "table_id": "operating_modules", "aggregation": "count"},
            {"id": "asset_count", "name": "资产数", "table_id": "assets", "aggregation": "count"},
            {"id": "task_count", "name": "任务数", "table_id": "tasks", "aggregation": "count"},
            {"id": "active_thread_count", "name": "活跃线程数", "table_id": "threads", "aggregation": "count"},
            {"id": "skill_count", "name": "技能数", "table_id": "skills", "aggregation": "count"},
            {"id": "client_space_count", "name": "客户实例数", "table_id": "spaces", "aggregation": "count"},
            {"id": "review_count", "name": "专项晨会数", "table_id": "review_runs", "aggregation": "count"},
        ],
        "dimensions": [
            {"id": "space_role", "name": "联邦角色", "table_id": "spaces", "field": "联邦角色", "type": "single_select"},
            {"id": "subject_type", "name": "主体类型", "table_id": "subjects", "field": "主体类型", "type": "single_select"},
            {"id": "account_platform", "name": "平台", "table_id": "accounts", "field": "平台", "type": "single_select"},
            {"id": "account_status", "name": "账号状态", "table_id": "accounts", "field": "健康状态", "type": "single_select"},
            {"id": "module_status", "name": "模块状态", "table_id": "operating_modules", "field": "状态", "type": "single_select"},
            {"id": "thread_goal", "name": "目标ID", "table_id": "threads", "field": "目标ID", "type": "single_select"},
            {"id": "task_status", "name": "任务状态", "table_id": "tasks", "field": "状态", "type": "single_select"},
            {"id": "skill_cluster", "name": "技能簇", "table_id": "skills", "field": "簇", "type": "single_select"},
            {"id": "review_date", "name": "复盘日期", "table_id": "review_runs", "field": "复盘日期", "type": "date"},
        ],
        "time_grain": "day",
        "action_targets": [
            {
                "id": "account_risk_queue",
                "name": "账号失管队列",
                "table_id": "accounts",
                "record_filter": "健康状态 != healthy",
                "display_fields": ["标题", "平台", "拥有主体", "宿主终端", "健康状态"],
            },
            {
                "id": "module_owner_gap_queue",
                "name": "模块责任缺口队列",
                "table_id": "operating_modules",
                "record_filter": "人类Owner is empty OR AI Copilot is empty",
                "display_fields": ["标题", "模块编码", "人类Owner", "AI Copilot", "KPI提示"],
            },
            {
                "id": "agent_skill_queue",
                "name": "AI编制挂接队列",
                "table_id": "subjects",
                "record_filter": "主体类型 = ai_agent",
                "display_fields": ["标题", "主体类型", "负责模块", "自治层级", "所属实例"],
            },
            {
                "id": "pending_task_queue",
                "name": "待跟进任务队列",
                "table_id": "tasks",
                "record_filter": "状态 != archived",
                "display_fields": ["标题", "优先级", "验真状态", "下一步动作"],
            },
            {
                "id": "skill_gap_queue",
                "name": "技能缺口队列",
                "table_id": "skills",
                "record_filter": "复杂度惩罚 >= 2",
                "display_fields": ["技能名", "簇", "验真强度", "复杂度惩罚"],
            },
            {
                "id": "client_rollout_queue",
                "name": "客户复制进度队列",
                "table_id": "spaces",
                "record_filter": "联邦角色 in (client, downstream)",
                "display_fields": ["标题", "实例类型", "联邦角色", "状态", "说明"],
            },
            {
                "id": "today_review_queue",
                "name": "今日晨会队列",
                "table_id": "review_runs",
                "record_filter": "复盘日期 = today",
                "display_fields": ["摘要", "主要风险", "候选动作", "待你拍板"],
            },
        ],
    }


def build_dashboard_blueprint() -> dict[str, Any]:
    spec = build_dashboard_spec()
    cards = []
    source_views = []
    checklist = []
    for index, question in enumerate(spec["decision_questions"], start=1):
        source_view_id = f"view-{question['id']}"
        cards.append(
            {
                "card_id": f"card-{index:02d}",
                "question_id": question["id"],
                "question": question["question"],
                "layer": question["layer"],
                "source_view_id": source_view_id,
                "chart_type": question.get("chart_preference") or "table",
                "metric_ids": question.get("metric_ids", []),
                "dimension_ids": question.get("dimension_ids", []),
                "action_target_ids": question.get("action_target_ids", []),
            }
        )
        source_views.append(
            {
                "view_id": source_view_id,
                "table_id": infer_table_for_question(question),
                "question_id": question["id"],
                "layer": question["layer"],
                "filter_hint": build_filter_hint(question),
            }
        )
        checklist.append(
            {
                "card_id": f"card-{index:02d}",
                "question": question["question"],
                "source_view_id": source_view_id,
                "manual_step": "在 Feishu dashboard 中手动绑定该 source view，并确认卡片只回答一个管理问题。",
            }
        )
    blueprint = {
        "generated_at": iso_now(),
        "goal": spec["goal"],
        "audience": spec["audience"],
        "layers": {
            "联邦层": ["实例边界", "主体编制", "终端账号", "模块责任"],
            "运营层": ["活跃线程", "任务堵点", "技能缺口", "客户复制"],
            "晨会层": ["战略进化", "今日 agenda", "待你拍板项"],
        },
        "cards": cards,
        "automation_boundary": {
            "supported": ["bitable tables", "views", "records", "dashboard source specs"],
            "manual": ["dashboard card creation", "widget binding", "layout placement"],
        },
    }
    write_json(SPECS_ROOT / "feishu" / "dashboard-input.json", spec)
    write_json(SPECS_ROOT / "feishu" / "dashboard-blueprint.json", blueprint)
    write_text(SPECS_ROOT / "feishu" / "dashboard-blueprint.md", render_dashboard_blueprint(blueprint))
    write_json(SPECS_ROOT / "feishu" / "source-views-spec.json", {"views": source_views})
    write_text(SPECS_ROOT / "feishu" / "dashboard-card-checklist.md", render_dashboard_checklist(checklist))
    return blueprint


def build_cockpit(scope_path: Path | None = None) -> dict[str, Any]:
    if scope_path is not None:
        build_inventory(scope_path)
    blueprint = build_dashboard_blueprint()
    payload = build_feishu_payload()
    result = {
        "generated_at": iso_now(),
        "dashboard_cards": len(blueprint["cards"]),
        "table_count": len(payload["tables"]),
        "questions": [
            "现在一共纳管了哪些来源，哪些还没进来",
            "订单和现金流各自覆盖到什么时间范围",
            "哪些内容资产已被纳管但未分类",
            "哪些平台/账号只有占位，没有真实数据",
            "哪些来源需要你授权、导出或命名澄清",
        ],
    }
    write_json(DERIVED_ROOT / "reports" / "cockpit-build.json", result)
    return result


def infer_table_for_question(question: dict[str, Any]) -> str:
    metric_ids = question.get("metric_ids", [])
    action_targets = question.get("action_target_ids", [])
    if action_targets:
        if action_targets[0] == "today_review_queue":
            return "review_runs"
        if action_targets[0] == "account_risk_queue":
            return "accounts"
        if action_targets[0] == "module_owner_gap_queue":
            return "operating_modules"
        if action_targets[0] == "agent_skill_queue":
            return "subjects"
        if action_targets[0] == "skill_gap_queue":
            return "skills"
        if action_targets[0] == "client_rollout_queue":
            return "spaces"
        return "tasks"
    if "space_count" in metric_ids or "client_space_count" in metric_ids:
        return "spaces"
    if "subject_count" in metric_ids or "ai_agent_count" in metric_ids:
        return "subjects"
    if "account_count" in metric_ids:
        return "accounts"
    if "module_count" in metric_ids:
        return "operating_modules"
    if "skill_count" in metric_ids:
        return "skills"
    if "asset_count" in metric_ids:
        return "assets"
    if "review_count" in metric_ids:
        return "review_runs"
    if "active_thread_count" in metric_ids:
        return "threads"
    return "tasks"


def build_filter_hint(question: dict[str, Any]) -> str:
    if question["layer"] == "federation":
        return "默认展示联邦总图的当前实例和责任覆盖"
    if question["layer"] in {"overview"}:
        return "默认展示最近快照的聚合指标"
    if question["layer"] in {"diagnosis", "operations"}:
        return "默认筛出 active / pending / needs follow-up"
    return "默认筛出今日待处理或待拍板记录"


def render_dashboard_blueprint(blueprint: dict[str, Any]) -> str:
    lines = [
        f"# {blueprint['goal']}",
        "",
        f"- 生成时间: {blueprint['generated_at']}",
        f"- 面向对象: {'、'.join(blueprint['audience'])}",
        "",
        "## 卡片列表",
    ]
    for card in blueprint["cards"]:
        lines.append(
            f"- {card['card_id']} [{card['layer']}] {card['question']} -> {card['source_view_id']} ({card['chart_type']})"
        )
    lines.extend(["", "## 卡片分层"])
    for layer, items in blueprint["layers"].items():
        lines.append(f"- {layer}: {'、'.join(items)}")
    return "\n".join(lines)


def render_dashboard_checklist(checklist: list[dict[str, str]]) -> str:
    lines = ["# Dashboard Card Checklist", ""]
    for item in checklist:
        lines.append(f"- {item['card_id']} :: {item['question']} :: {item['source_view_id']} :: {item['manual_step']}")
    return "\n".join(lines)


def mask_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) >= 11:
        return f"{digits[:3]}****{digits[-4:]}"
    return value


def mask_freeform_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value
    text = re.sub(r"(1[3-9]\d)\d{4}(\d{4})", r"\1****\2", text)
    text = re.sub(r"(\d{4})\d{8,11}(\d{4})", r"\1****\2", text)
    return text


def sanitize_order_for_feishu(order: dict[str, Any]) -> dict[str, Any]:
    payload = dict(order)
    payload["customer_phone"] = mask_phone(str(payload.get("customer_phone", "")))
    for key in ["customer_name", "note", "card_note"]:
        payload[key] = mask_freeform_value(payload.get(key, ""))
    return payload


def sanitize_cashflow_for_feishu(cashflow: dict[str, Any]) -> dict[str, Any]:
    payload = dict(cashflow)
    for key in ["account_name", "counterparty", "summary"]:
        payload[key] = mask_freeform_value(payload.get(key, ""))
    return payload


def validate_sensitivity_payload(payload: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    for table_name, rows in payload.get("tables", {}).items():
        for index, row in enumerate(rows):
            for key, value in row.items():
                if not isinstance(value, str):
                    continue
                if re.search(r"1[3-9]\d{9}", value):
                    issues.append(f"{table_name}[{index}].{key}:raw_phone")
                if re.search(r"\d{12,19}", value):
                    issues.append(f"{table_name}[{index}].{key}:raw_long_number")
    result = {
        "generated_at": iso_now(),
        "ok": not issues,
        "checks": [
            {
                "name": "no_raw_phone_or_long_id_in_feishu_payload",
                "ok": not issues,
                "details": issues[:50],
            }
        ],
    }
    write_json(DERIVED_ROOT / "reports" / "sensitivity-report.json", result)
    return result


def build_feishu_payload() -> dict[str, Any]:
    inventory = ensure_inventory()
    content_assets = [
        item
        for item in inventory["assets"]
        if item.get("content_class") in {"course_material", "knowledge_document", "article_asset", "social_asset", "content_artifact"}
    ]
    payload = {
        "generated_at": iso_now(),
        "tables": {
            "联邦实例表": inventory["spaces"],
            "主体总表": inventory["subjects"],
            "终端表": inventory["endpoints"],
            "终端账号表": inventory["accounts"],
            "CBM模块责任表": inventory["operating_modules"],
            "来源总表": inventory.get("source_feeds", []),
            "采集运行表": inventory.get("ingestion_runs", []),
            "资产总表": inventory["assets"],
            "订单事实表": [sanitize_order_for_feishu(item) for item in inventory.get("orders", [])],
            "现金流事实表": [sanitize_cashflow_for_feishu(item) for item in inventory.get("cashflows", [])],
            "内容资产表": content_assets,
            "任务总表": inventory["tasks"],
            "线程总表": inventory["threads"],
            "技能能力表": inventory["skills"],
            "专项晨会记录表": inventory["review_runs"],
        },
        "schema": FEISHU_TABLE_SPECS,
        "mode": "mirror_only",
    }
    write_json(DERIVED_ROOT / "feishu" / "feishu-payload.json", payload)
    return payload


def mirror_feishu(*, dry_run: bool = False, apply: bool = False) -> dict[str, Any]:
    if dry_run == apply:
        raise RuntimeError("Use exactly one of --dry-run or --apply.")
    payload = build_feishu_payload()
    result_path = DERIVED_ROOT / "feishu" / ("sync-result.dry-run.json" if dry_run else "sync-result.apply.json")
    if dry_run:
        sensitivity = validate_sensitivity_payload(payload)
        result = {
            "generated_at": iso_now(),
            "status": "validated" if sensitivity["ok"] else "blocked_sensitive_payload",
            "table_counts": {table: len(records) for table, records in payload["tables"].items()},
            "sensitivity_ok": sensitivity["ok"],
            "message": "Local canonical payload validated. No remote Feishu base configured in v1.",
        }
        write_json(result_path, result)
        return result

    dry_run_result = read_json(DERIVED_ROOT / "feishu" / "sync-result.dry-run.json", default={})
    if dry_run_result.get("status") != "validated":
        raise RuntimeError("Feishu apply is blocked until a successful dry-run exists.")
    result = {
        "generated_at": iso_now(),
        "status": "blocked_no_base_configured",
        "message": "Remote Feishu apply is intentionally blocked in v1 because no live base binding is configured.",
    }
    write_json(result_path, result)
    return result


def validate_entities(scope_path: Path | None = None) -> dict[str, Any]:
    results: dict[str, Any] = {"generated_at": iso_now(), "checks": []}
    entities = {name: read_json(path, default=[]) for name, path in ENTITY_FILES.items()}
    scope = load_source_scope(scope_path)
    entity_index = {
        "space": {item["space_id"] for item in entities["spaces"]},
        "subject": {item["subject_id"] for item in entities["subjects"]},
        "endpoint": {item["endpoint_id"] for item in entities["endpoints"]},
        "account": {item["account_id"] for item in entities["accounts"]},
        "operating_module": {item["module_id"] for item in entities["operating_modules"]},
        "source_feed": {item["source_feed_id"] for item in entities["source_feeds"]},
        "ingestion_run": {item["ingestion_run_id"] for item in entities["ingestion_runs"]},
        "asset": {item["asset_id"] for item in entities["assets"]},
        "order": {item["order_id"] for item in entities["orders"]},
        "cashflow": {item["cashflow_id"] for item in entities["cashflows"]},
        "task": {item["task_id"] for item in entities["tasks"]},
        "thread": {item["thread_id"] for item in entities["threads"]},
        "skill": {item["skill_id"] for item in entities["skills"]},
        "action": {item["action_id"] for item in entities["actions"]},
        "agent_capability": {item["capability_id"] for item in entities["agent_capabilities"]},
        "decision_record": {item["decision_id"] for item in entities["decision_records"]},
        "writeback_event": {item["writeback_id"] for item in entities["writeback_events"]},
        "knowledge_item": {item["knowledge_id"] for item in entities["knowledge_items"]},
        "review_run": {item["review_id"] for item in entities["review_runs"]},
    }
    knowledge_source_urls = [
        normalize_external_url(str(item.get("url", "")))
        for item in entities["knowledge_sources"]
        if str(item.get("url", "")).strip()
    ]
    configured_source_urls = [
        normalize_external_url(str(item))
        for item in scope.get("source_feishu_links", [])
        if str(item).strip()
    ]
    configured_tencent_meeting_urls = [
        normalize_tencent_meeting_share_url(str(item))[0]
        for item in scope.get("source_tencent_meeting_links", [])
        if str(item).strip()
    ]
    tencent_sources_by_url = {
        normalize_external_url(str(item.get("url", ""))): item
        for item in entities["knowledge_sources"]
        if str(item.get("page_type", "")).strip() == "tencent_meeting_share" and str(item.get("url", "")).strip()
    }
    subject_types = {item["subject_id"]: item.get("subject_type", "") for item in entities["subjects"]}

    orphan_relations = []
    for relation in entities["relations"]:
        from_ok = reference_exists(relation["from_type"], relation["from_id"], entity_index)
        to_ok = reference_exists(relation["to_type"], relation["to_id"], entity_index)
        if not (from_ok and to_ok):
            orphan_relations.append(relation["relation_id"])
    results["checks"].append({"name": "no_orphan_relations", "ok": not orphan_relations, "details": orphan_relations})
    results["checks"].append(
        {
            "name": "relation_types_valid",
            "ok": all(item["relation_type"] in FIXED_RELATION_TYPES for item in entities["relations"]),
            "details": [],
        }
    )
    results["checks"].append(
        {
            "name": "daily_review_automation_preserved",
            "ok": Path(load_source_scope(scope_path)["daily_review_automation_path"]).exists(),
            "details": [],
        }
    )
    results["checks"].append(
        {
            "name": "dashboard_blueprint_present",
            "ok": (SPECS_ROOT / "feishu" / "dashboard-blueprint.json").exists(),
            "details": [],
        }
    )
    results["checks"].append(
        {
            "name": "operational_spec_files_present",
            "ok": all(
                path.exists()
                for path in [
                    operational_ontology_spec_path(),
                    operational_action_catalog_path(),
                    operational_policy_boundary_path(),
                    operational_impl_plan_path(),
                ]
            ),
            "details": [
                str(path)
                for path in [
                    operational_ontology_spec_path(),
                    operational_action_catalog_path(),
                    operational_policy_boundary_path(),
                    operational_impl_plan_path(),
                ]
                if not path.exists()
            ],
        }
    )
    results["checks"].append(
        {
            "name": "actions_bootstrapped",
            "ok": len(entities["actions"]) >= 3,
            "details": [str(item.get("action_id", "")) for item in entities["actions"]],
        }
    )
    results["checks"].append(
        {
            "name": "agent_capabilities_bootstrapped",
            "ok": len(entities["agent_capabilities"]) >= 3,
            "details": [str(item.get("capability_id", "")) for item in entities["agent_capabilities"]],
        }
    )
    results["checks"].append(
        {
            "name": "writebacks_reference_existing_actions",
            "ok": all(
                str(item.get("action_id", "")).strip() in entity_index["action"]
                for item in entities["writeback_events"]
            ),
            "details": [
                str(item.get("writeback_id", ""))
                for item in entities["writeback_events"]
                if str(item.get("action_id", "")).strip() not in entity_index["action"]
            ],
        }
    )
    results["checks"].append(
        {
            "name": "approved_writebacks_have_decision",
            "ok": all(
                str(item.get("verification_state", "")).strip() != "completed"
                or str(item.get("decision_id", "")).strip() in entity_index["decision_record"]
                for item in entities["writeback_events"]
            ),
            "details": [
                str(item.get("writeback_id", ""))
                for item in entities["writeback_events"]
                if str(item.get("verification_state", "")).strip() == "completed"
                and str(item.get("decision_id", "")).strip() not in entity_index["decision_record"]
            ],
        }
    )
    results["checks"].append(
        {
            "name": "source_registry_groups_present",
            "ok": all(scope.get(group) for group in ["sync_hub_roots", "business_finance_roots", "content_knowledge_roots", "governance_roots"]),
            "details": [
                group for group in ["sync_hub_roots", "business_finance_roots", "content_knowledge_roots", "governance_roots"] if not scope.get(group)
            ],
        }
    )
    results["checks"].append(
        {
            "name": "source_feeds_unique",
            "ok": len(entity_index["source_feed"]) == len(entities["source_feeds"]),
            "details": [
                str(item.get("source_feed_id", ""))
                for item in entities["source_feeds"]
                if list(entity_index["source_feed"]).count(str(item.get("source_feed_id", ""))) > 1
            ],
        }
    )
    results["checks"].append(
        {
            "name": "orders_unique",
            "ok": len(entity_index["order"]) == len(entities["orders"]),
            "details": [],
        }
    )
    results["checks"].append(
        {
            "name": "cashflows_unique",
            "ok": len(entity_index["cashflow"]) == len(entities["cashflows"]),
            "details": [],
        }
    )
    results["checks"].append(
        {
            "name": "knowledge_source_statuses_valid",
            "ok": all(
                str(item.get("validation_status", "")).strip() in KNOWLEDGE_SOURCE_ALLOWED_STATUSES
                for item in entities["knowledge_sources"]
            ),
            "details": [
                str(item.get("source_id", ""))
                for item in entities["knowledge_sources"]
                if str(item.get("validation_status", "")).strip() not in KNOWLEDGE_SOURCE_ALLOWED_STATUSES
            ],
        }
    )
    results["checks"].append(
        {
            "name": "configured_knowledge_sources_registered",
            "ok": set(configured_source_urls).issubset(set(knowledge_source_urls)),
            "details": sorted(set(configured_source_urls) - set(knowledge_source_urls)),
        }
    )
    results["checks"].append(
        {
            "name": "configured_tencent_meeting_sources_registered",
            "ok": set(configured_tencent_meeting_urls).issubset(set(knowledge_source_urls)),
            "details": sorted(set(configured_tencent_meeting_urls) - set(knowledge_source_urls)),
        }
    )
    results["checks"].append(
        {
            "name": "configured_tencent_meeting_samples_verified",
            "ok": all(
                (
                    str(tencent_sources_by_url[url].get("capture_status", "")).strip() != "failed"
                    and str(tencent_sources_by_url[url].get("transcript_status", "")).strip() != "unknown"
                    and str(tencent_sources_by_url[url].get("native_transcript_capability", "")).strip() != "unknown"
                    and str(tencent_sources_by_url[url].get("native_transcript_enabled", "")).strip() != "unknown"
                    and str(tencent_sources_by_url[url].get("share_page_transcript_visible", "")).strip() != "unknown"
                )
                for url in configured_tencent_meeting_urls
                if url in tencent_sources_by_url
            ),
            "details": [
                url
                for url in configured_tencent_meeting_urls
                if url in tencent_sources_by_url
                and (
                    str(tencent_sources_by_url[url].get("capture_status", "")).strip() == "failed"
                    or str(tencent_sources_by_url[url].get("transcript_status", "")).strip() == "unknown"
                    or str(tencent_sources_by_url[url].get("native_transcript_capability", "")).strip() == "unknown"
                    or str(tencent_sources_by_url[url].get("native_transcript_enabled", "")).strip() == "unknown"
                    or str(tencent_sources_by_url[url].get("share_page_transcript_visible", "")).strip() == "unknown"
                )
            ],
        }
    )
    results["checks"].append(
        {
            "name": "knowledge_source_urls_unique",
            "ok": len(knowledge_source_urls) == len(set(knowledge_source_urls)),
            "details": sorted(
                {
                    url
                    for url in knowledge_source_urls
                    if knowledge_source_urls.count(url) > 1
                }
            ),
        }
    )
    results["checks"].append(
        {
            "name": "knowledge_item_layers_valid",
            "ok": all(
                str(item.get("governance_layer", "")).strip() in KNOWLEDGE_ITEM_ALLOWED_LAYERS
                for item in entities["knowledge_items"]
            ),
            "details": [
                str(item.get("knowledge_id", ""))
                for item in entities["knowledge_items"]
                if str(item.get("governance_layer", "")).strip() not in KNOWLEDGE_ITEM_ALLOWED_LAYERS
            ],
        }
    )
    results["checks"].append(
        {
            "name": "knowledge_item_sync_tiers_valid",
            "ok": all(
                str(item.get("sync_tier", "")).strip() in KNOWLEDGE_ITEM_ALLOWED_SYNC_TIERS
                for item in entities["knowledge_items"]
            ),
            "details": [
                str(item.get("knowledge_id", ""))
                for item in entities["knowledge_items"]
                if str(item.get("sync_tier", "")).strip() not in KNOWLEDGE_ITEM_ALLOWED_SYNC_TIERS
            ],
        }
    )
    results["checks"].append(
        {
            "name": "knowledge_item_statuses_valid",
            "ok": all(
                str(item.get("status", "")).strip() in KNOWLEDGE_ITEM_ALLOWED_STATUSES
                for item in entities["knowledge_items"]
            ),
            "details": [
                str(item.get("knowledge_id", ""))
                for item in entities["knowledge_items"]
                if str(item.get("status", "")).strip() not in KNOWLEDGE_ITEM_ALLOWED_STATUSES
            ],
        }
    )
    results["checks"].append(
        {
            "name": "knowledge_items_reference_known_sources",
            "ok": all(
                not str(item.get("source_id", "")).strip()
                or str(item.get("source_id", "")).strip()
                in {
                    str(source.get("source_id", "")).strip()
                    for source in entities["knowledge_sources"]
                }
                for item in entities["knowledge_items"]
            ),
            "details": [
                str(item.get("knowledge_id", ""))
                for item in entities["knowledge_items"]
                if str(item.get("source_id", "")).strip()
                and str(item.get("source_id", "")).strip()
                not in {
                    str(source.get("source_id", "")).strip()
                    for source in entities["knowledge_sources"]
                }
            ],
        }
    )
    results["checks"].append(
        {
            "name": "tencent_meeting_capture_statuses_valid",
            "ok": all(
                str(item.get("capture_status", "")).strip() in TENCENT_MEETING_CAPTURE_ALLOWED_STATUSES
                for item in entities["knowledge_sources"]
                if str(item.get("page_type", "")).strip() == "tencent_meeting_share"
            ),
            "details": [
                str(item.get("source_id", ""))
                for item in entities["knowledge_sources"]
                if str(item.get("page_type", "")).strip() == "tencent_meeting_share"
                and str(item.get("capture_status", "")).strip() not in TENCENT_MEETING_CAPTURE_ALLOWED_STATUSES
            ],
        }
    )
    results["checks"].append(
        {
            "name": "tencent_meeting_transcript_statuses_valid",
            "ok": all(
                str(item.get("transcript_status", "")).strip() in TENCENT_MEETING_TRANSCRIPT_ALLOWED_STATUSES
                for item in entities["knowledge_sources"]
                if str(item.get("page_type", "")).strip() == "tencent_meeting_share"
            ),
            "details": [
                str(item.get("source_id", ""))
                for item in entities["knowledge_sources"]
                if str(item.get("page_type", "")).strip() == "tencent_meeting_share"
                and str(item.get("transcript_status", "")).strip() not in TENCENT_MEETING_TRANSCRIPT_ALLOWED_STATUSES
            ],
        }
    )
    results["checks"].append(
        {
            "name": "tencent_meeting_native_transcript_capabilities_valid",
            "ok": all(
                str(item.get("native_transcript_capability", "")).strip()
                in TENCENT_MEETING_NATIVE_TRANSCRIPT_CAPABILITY_ALLOWED_STATUSES
                for item in entities["knowledge_sources"]
                if str(item.get("page_type", "")).strip() == "tencent_meeting_share"
            ),
            "details": [
                str(item.get("source_id", ""))
                for item in entities["knowledge_sources"]
                if str(item.get("page_type", "")).strip() == "tencent_meeting_share"
                and str(item.get("native_transcript_capability", "")).strip()
                not in TENCENT_MEETING_NATIVE_TRANSCRIPT_CAPABILITY_ALLOWED_STATUSES
            ],
        }
    )
    results["checks"].append(
        {
            "name": "tencent_meeting_native_transcript_enabled_valid",
            "ok": all(
                str(item.get("native_transcript_enabled", "")).strip()
                in TENCENT_MEETING_NATIVE_TRANSCRIPT_ENABLED_ALLOWED_STATUSES
                for item in entities["knowledge_sources"]
                if str(item.get("page_type", "")).strip() == "tencent_meeting_share"
            ),
            "details": [
                str(item.get("source_id", ""))
                for item in entities["knowledge_sources"]
                if str(item.get("page_type", "")).strip() == "tencent_meeting_share"
                and str(item.get("native_transcript_enabled", "")).strip()
                not in TENCENT_MEETING_NATIVE_TRANSCRIPT_ENABLED_ALLOWED_STATUSES
            ],
        }
    )
    results["checks"].append(
        {
            "name": "tencent_meeting_share_page_transcript_visible_valid",
            "ok": all(
                str(item.get("share_page_transcript_visible", "")).strip()
                in TENCENT_MEETING_SHARE_PAGE_TRANSCRIPT_VISIBLE_ALLOWED_STATUSES
                for item in entities["knowledge_sources"]
                if str(item.get("page_type", "")).strip() == "tencent_meeting_share"
            ),
            "details": [
                str(item.get("source_id", ""))
                for item in entities["knowledge_sources"]
                if str(item.get("page_type", "")).strip() == "tencent_meeting_share"
                and str(item.get("share_page_transcript_visible", "")).strip()
                not in TENCENT_MEETING_SHARE_PAGE_TRANSCRIPT_VISIBLE_ALLOWED_STATUSES
            ],
        }
    )
    results["checks"].append(
        {
            "name": "tencent_meeting_transcript_access_paths_valid",
            "ok": all(
                str(item.get("transcript_access_path", "")).strip()
                in TENCENT_MEETING_TRANSCRIPT_ACCESS_PATH_ALLOWED_STATUSES
                for item in entities["knowledge_sources"]
                if str(item.get("page_type", "")).strip() == "tencent_meeting_share"
            ),
            "details": [
                str(item.get("source_id", ""))
                for item in entities["knowledge_sources"]
                if str(item.get("page_type", "")).strip() == "tencent_meeting_share"
                and str(item.get("transcript_access_path", "")).strip()
                not in TENCENT_MEETING_TRANSCRIPT_ACCESS_PATH_ALLOWED_STATUSES
            ],
        }
    )
    controlled_accounts = {
        relation["to_id"]
        for relation in entities["relations"]
        if relation["relation_type"] == "subject_controls_account"
    }
    owned_endpoints = {
        relation["to_id"]
        for relation in entities["relations"]
        if relation["relation_type"] == "subject_owns_endpoint"
    }
    task_target_subjects = {
        relation["from_id"]
        for relation in entities["relations"]
        if relation["relation_type"] == "task_targets_subject"
    }
    task_target_modules = {
        relation["from_id"]
        for relation in entities["relations"]
        if relation["relation_type"] == "task_targets_module"
    }
    tracked_threads = {
        relation["from_id"]
        for relation in entities["relations"]
        if relation["relation_type"] == "thread_tracks_space"
    }
    human_owned_modules = {
        relation["to_id"]
        for relation in entities["relations"]
        if relation["relation_type"] == "subject_responsible_for_module"
        and subject_types.get(relation["from_id"]) == "human"
    }
    ai_copilot_modules = {
        relation["to_id"]
        for relation in entities["relations"]
        if relation["relation_type"] == "ai_agent_copilots_module"
        and subject_types.get(relation["from_id"]) == "ai_agent"
    }
    results["checks"].append(
        {
            "name": "accounts_have_subject_owner",
            "ok": controlled_accounts == entity_index["account"],
            "details": sorted(entity_index["account"] - controlled_accounts),
        }
    )
    results["checks"].append(
        {
            "name": "endpoints_have_subject_owner",
            "ok": owned_endpoints == entity_index["endpoint"],
            "details": sorted(entity_index["endpoint"] - owned_endpoints),
        }
    )
    results["checks"].append(
        {
            "name": "modules_have_human_owner",
            "ok": human_owned_modules == entity_index["operating_module"],
            "details": sorted(entity_index["operating_module"] - human_owned_modules),
        }
    )
    results["checks"].append(
        {
            "name": "modules_have_ai_copilot",
            "ok": ai_copilot_modules == entity_index["operating_module"],
            "details": sorted(entity_index["operating_module"] - ai_copilot_modules),
        }
    )
    results["checks"].append(
        {
            "name": "tasks_are_attached_to_subject_and_module",
            "ok": task_target_subjects == entity_index["task"] and task_target_modules == entity_index["task"],
            "details": sorted((entity_index["task"] - task_target_subjects) | (entity_index["task"] - task_target_modules)),
        }
    )
    results["checks"].append(
        {
            "name": "threads_track_space",
            "ok": tracked_threads == entity_index["thread"],
            "details": sorted(entity_index["thread"] - tracked_threads),
        }
    )
    sensitivity = validate_sensitivity_payload(build_feishu_payload())
    results["checks"].append(
        {
            "name": "feishu_payload_masked",
            "ok": sensitivity["ok"],
            "details": sensitivity["checks"][0]["details"],
        }
    )
    results["ok"] = all(check["ok"] for check in results["checks"])
    write_json(DERIVED_ROOT / "reports" / "validation-report.json", results)
    return results


def validate_sensitivity(scope_path: Path | None = None) -> dict[str, Any]:
    if scope_path is not None:
        build_inventory(scope_path)
    payload = build_feishu_payload()
    return validate_sensitivity_payload(payload)


def reference_exists(
    entity_type: str,
    entity_id: str,
    entity_index: dict[str, set[str]],
) -> bool:
    return entity_id in entity_index.get(entity_type, set())


def run_daily(scope_path: Path | None = None) -> dict[str, Any]:
    inventory = build_inventory(scope_path)
    cockpit = build_cockpit()
    dry_run_result = mirror_feishu(dry_run=True)
    morning_review = generate_morning_review(scope_path)
    validation = validate_entities(scope_path)
    result = {
        "generated_at": iso_now(),
        "inventory_counts": inventory["counts"],
        "dashboard_cards": cockpit["dashboard_cards"],
        "dry_run_status": dry_run_result["status"],
        "morning_review_id": morning_review["review_id"],
        "validation_ok": validation["ok"],
    }
    write_json(DERIVED_ROOT / "reports" / "run-daily-result.json", result)
    return result
