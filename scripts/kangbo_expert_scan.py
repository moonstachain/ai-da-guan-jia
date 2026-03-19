from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.sync_governance_dashboard_base import api, list_records
from scripts.sync_r11_v2_skill_inventory_feishu import bootstrap_client
from scripts.ts_kb_03_kangbo_expert_ops import TARGET_APP_TOKEN, to_link_object


L2_TABLE_ID = "tbl82HhewJxuU8hV"
L3_TABLE_ID = "tblcAxYlxfEHbPHv"
DEFAULT_ACCOUNT_ID = "feishu-claw"
DEFAULT_SLEEP_SECONDS = 2.0
USER_AGENT = "Mozilla/5.0 (compatible; KangboExpertScan/1.0)"


@dataclass(frozen=True)
class ExpertSource:
    expert_id: str
    name: str
    tier: str
    source_type: str
    source_url: str


@dataclass(frozen=True)
class CandidateInsight:
    expert_id: str
    title: str
    summary: str
    source_url: str
    source_type: str
    insight_date: str
    article_url: str
    article_title: str
    article_summary: str
    created_by: str = "Codex"
    kangbo_phase: str = "KB10"
    sentiment: str = "中性"
    quality_score: int = 3
    asset_class_impact: tuple[str, ...] = ("其他",)
    event_ref: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "insight_id": make_insight_id(self.expert_id, self.title, self.insight_date),
            "expert_id": self.expert_id,
            "insight_date": to_ms(self.insight_date),
            "title": self.title,
            "summary": self.summary,
            "source_url": to_link_object(self.source_url),
            "source_type": self.source_type,
            "event_ref": self.event_ref,
            "kangbo_phase": self.kangbo_phase,
            "asset_class_impact": list(self.asset_class_impact),
            "sentiment": self.sentiment,
            "quality_score": self.quality_score,
            "created_by": self.created_by,
        }


def to_ms(date_text: str) -> int:
    dt = datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def now_local_stamp() -> str:
    return datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")


def current_date_text() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d")


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Kangbo expert network scan.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--expert-id", action="append", default=[], help="Filter by expert_id. Can be passed multiple times.")
    parser.add_argument("--tier", choices=["T0", "T1", "T2"], action="append", default=[], help="Filter by tier. Can be passed multiple times.")
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    parser.add_argument("--sleep-seconds", type=float, default=DEFAULT_SLEEP_SECONDS)
    parser.add_argument("--run-root", default=str(REPO_ROOT / "artifacts" / "ai-da-guan-jia" / "runs"))
    return parser.parse_args(argv)


def bootstrap_feishu(account_id: str):
    return bootstrap_client(account_id)


def extract_link_object(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("link") or value.get("text") or "").strip()
    return str(value or "").strip()


def fetch_html(url: str, *, timeout: int = 20) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(800_000).decode("utf-8", errors="ignore")
            return {
                "ok": True,
                "url": url,
                "final_url": getattr(response, "url", url),
                "status": getattr(response, "status", 200),
                "content_type": response.headers.get("Content-Type", ""),
                "html": body,
            }
    except HTTPError as exc:
        return {
            "ok": False,
            "url": url,
            "final_url": url,
            "status": exc.code,
            "content_type": "",
            "error": f"HTTP {exc.code}",
            "html": "",
        }
    except URLError as exc:
        message = str(exc.reason)
        if "CERTIFICATE_VERIFY_FAILED" in message or "certificate has expired" in message or "Hostname mismatch" in message:
            try:
                context = ssl._create_unverified_context()
                with urlopen(request, timeout=timeout, context=context) as response:
                    body = response.read(800_000).decode("utf-8", errors="ignore")
                    return {
                        "ok": True,
                        "url": url,
                        "final_url": getattr(response, "url", url),
                        "status": getattr(response, "status", 200),
                        "content_type": response.headers.get("Content-Type", ""),
                        "html": body,
                        "ssl_relaxed": True,
                    }
            except Exception as retry_exc:  # pragma: no cover - defensive fallback
                message = f"{message}; retry_failed={retry_exc}"
        return {
            "ok": False,
            "url": url,
            "final_url": url,
            "status": 599,
            "content_type": "",
            "error": message,
            "html": "",
        }


def find_meta(html: str, key: str) -> str:
    patterns = [
        rf'<meta[^>]+property=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']+)["\']',
        rf'<meta[^>]+name=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']+)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return clean_text(match.group(1))
    return ""


def extract_title(html: str) -> str:
    for key in ("og:title", "twitter:title"):
        value = find_meta(html, key)
        if value:
            return value
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return clean_text(match.group(1))
    return ""


def extract_description(html: str) -> str:
    for key in ("og:description", "twitter:description", "description"):
        value = find_meta(html, key)
        if value:
            return value
    return ""


def extract_date(html: str) -> str:
    patterns = [
        r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})",
        r"(20\d{2})\s*[-/]\s*(\d{1,2})\s*[-/]\s*(\d{1,2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            year, month, day = match.groups()
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    return current_date_text()


def extract_paragraph_summary(html: str) -> str:
    paragraphs = [clean_text(item) for item in re.findall(r"<p[^>]*>(.*?)</p>", html, flags=re.IGNORECASE | re.DOTALL)]
    paragraphs = [item for item in paragraphs if len(item) >= 20]
    if not paragraphs:
        return ""
    summary = " ".join(paragraphs[:2]).strip()
    return summary[:220]


def same_domain(base_url: str, other_url: str) -> bool:
    return urlparse(base_url).netloc.lower() == urlparse(other_url).netloc.lower()


def score_link(base_url: str, href: str, text: str) -> int:
    score = 0
    href_l = href.lower()
    text_l = text.lower()
    for token, points in [
        ("article", 6),
        ("news", 6),
        ("insights", 6),
        ("research", 6),
        ("detail", 5),
        ("video", 5),
        ("post", 4),
        ("info", 4),
        ("content", 4),
    ]:
        if token in href_l or token in text_l:
            score += points
    if len(text) >= 12:
        score += min(len(text) // 20, 3)
    if href_l.startswith("javascript:") or href_l.startswith("mailto:") or href_l.startswith("#"):
        score -= 50
    if any(token in href_l for token in ["login", "register", "share", "tag", "category", "search", "signup"]):
        score -= 12
    if href.rstrip("/") == base_url.rstrip("/"):
        score -= 20
    if not same_domain(base_url, href):
        score -= 2
    return score


def extract_links(url: str, html: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    pattern = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', flags=re.IGNORECASE | re.DOTALL)
    for match in pattern.finditer(html):
        href = unescape(match.group(1).strip())
        text = clean_text(match.group(2))
        if not href or href.startswith("javascript:") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        abs_url = urljoin(url, href)
        links.append({"url": abs_url, "text": text, "score": str(score_link(url, abs_url, text))})
    links.sort(key=lambda item: int(item["score"]), reverse=True)
    unique: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in links:
        if item["url"] in seen:
            continue
        seen.add(item["url"])
        unique.append(item)
    return unique


def normalize_source_type(source_type: str, url: str) -> str:
    value = source_type.strip()
    if "研报" in value:
        return "研报"
    if "视频" in value:
        return "视频"
    if "演讲" in value:
        return "演讲"
    if "书籍" in value:
        return "书籍"
    if "社交" in value:
        return "社交媒体"
    if "官网" in value or value == "公开" or value.startswith("公开"):
        return "官网文章"
    domain = urlparse(url).netloc.lower()
    if "bilibili" in domain:
        return "视频"
    if any(token in domain for token in ["xueqiu", "weixin", "weixinyidu"]):
        return "社交媒体"
    return "官网文章"


def summarize_source_type(source_type: str) -> str:
    mapping = {
        "研报": "research",
        "公开研报+白皮书": "research",
        "公开文章+书籍": "article",
        "公开观点+媒体": "media",
        "公开+研报": "research",
        "公开+付费": "research",
        "公开": "public",
        "视频": "video",
        "演讲": "talk",
        "书籍": "book",
        "社交媒体": "social",
    }
    return mapping.get(source_type, "public")


def make_insight_id(expert_id: str, title: str, insight_date: str) -> str:
    digest = hashlib.sha1(f"{expert_id}|{title}|{insight_date}".encode("utf-8")).hexdigest()[:8].upper()
    code = expert_id.split("-")[-1]
    return f"SCAN-{code}-{digest}"


def l2_index(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in records:
        fields = row.get("fields") or {}
        expert_id = str(fields.get("expert_id") or "").strip()
        if expert_id:
            result[expert_id] = row
    return result


def l3_index(records: list[dict[str, Any]]) -> set[tuple[str, str]]:
    result: set[tuple[str, str]] = set()
    for row in records:
        fields = row.get("fields") or {}
        expert_id = str(fields.get("expert_id") or "").strip()
        title = str(fields.get("title") or "").strip()
        if expert_id and title:
            result.add((expert_id, title))
    return result


def load_experts(client: Any) -> list[ExpertSource]:
    rows = list_records(client, TARGET_APP_TOKEN, L2_TABLE_ID)
    result: list[ExpertSource] = []
    for row in rows:
        fields = row.get("fields") or {}
        source_url = extract_link_object(fields.get("source_url"))
        if not source_url:
            continue
        result.append(
            ExpertSource(
                expert_id=str(fields.get("expert_id") or "").strip(),
                name=str(fields.get("name") or "").strip(),
                tier=str(fields.get("tier") or "").strip(),
                source_type=str(fields.get("source_type") or "").strip(),
                source_url=source_url,
            )
        )
    return result


def should_scan(expert: ExpertSource, args: argparse.Namespace) -> bool:
    if args.expert_id and expert.expert_id not in set(args.expert_id):
        return False
    if args.tier and expert.tier not in set(args.tier):
        return False
    return True


def make_summary_text(article_title: str, article_summary: str, source_type: str) -> str:
    source_class = summarize_source_type(source_type)
    if article_summary:
        return article_summary[:180]
    if article_title:
        return f"{source_class} source: {article_title}"
    return f"{source_class} source"


def fetch_candidates_for_expert(expert: ExpertSource) -> dict[str, Any]:
    source_fetch = fetch_html(expert.source_url)
    if not source_fetch["ok"]:
        return {
            "expert": expert,
            "status": "failed",
            "source_fetch": source_fetch,
            "candidates": [],
            "warnings": [f"{expert.expert_id} fetch failed: {source_fetch.get('error', 'unknown error')}"],
        }

    html = source_fetch["html"]
    base_title = extract_title(html)
    base_desc = extract_description(html) or extract_paragraph_summary(html)
    base_date = extract_date(html)

    candidates: list[CandidateInsight] = []
    seen_titles: set[str] = set()

    def add_candidate(article_url: str, article_title: str, article_summary: str, insight_date: str) -> None:
        normalized_title = article_title.strip()
        if not normalized_title:
            return
        key = normalized_title.lower()
        if key in seen_titles:
            return
        seen_titles.add(key)
        candidates.append(
            CandidateInsight(
                expert_id=expert.expert_id,
                title=normalized_title,
                summary=make_summary_text(normalized_title, article_summary, expert.source_type),
                source_url=article_url,
                source_type=normalize_source_type(expert.source_type, article_url),
                insight_date=insight_date,
                article_url=article_url,
                article_title=normalized_title,
                article_summary=article_summary,
                quality_score=4 if expert.source_type in {"研报", "公开研报+白皮书"} else 3,
                asset_class_impact=("其他",),
            )
        )

    link_items = extract_links(source_fetch["final_url"], html)
    link_items = [item for item in link_items if same_domain(source_fetch["final_url"], item["url"])]
    link_items = [item for item in link_items if int(item["score"]) >= 3][:5]

    if link_items:
        for item in link_items[:3]:
            linked = fetch_html(item["url"])
            if linked["ok"]:
                title = extract_title(linked["html"]) or item["text"] or base_title
                summary = extract_description(linked["html"]) or extract_paragraph_summary(linked["html"]) or base_desc
                add_candidate(linked["final_url"], title, summary, extract_date(linked["html"]))
            else:
                if item["text"]:
                    add_candidate(item["url"], item["text"], base_desc, base_date)
    else:
        fallback_title = base_title or expert.name or expert.expert_id
        add_candidate(source_fetch["final_url"], fallback_title, base_desc, base_date)

    if not candidates:
        fallback_title = base_title or expert.name or expert.expert_id
        add_candidate(source_fetch["final_url"], fallback_title, base_desc, base_date)

    return {
        "expert": expert,
        "status": "ok",
        "source_fetch": source_fetch,
        "candidates": candidates,
        "warnings": [],
    }


def update_l2_tracking(client: Any, expert_row: dict[str, Any], delta: int, *, apply: bool) -> dict[str, Any]:
    fields = expert_row.get("fields") or {}
    current_count = int(fields.get("insight_count") or 0)
    payload = {
        "last_tracked": int(datetime.now(timezone.utc).timestamp() * 1000),
        "insight_count": current_count + delta,
    }
    if not apply:
        return {
            "record_id": expert_row.get("record_id"),
            "fields": payload,
            "action": "dry-run",
        }
    api(
        client,
        "PUT",
        f"/bitable/v1/apps/{TARGET_APP_TOKEN}/tables/{L2_TABLE_ID}/records/{expert_row['record_id']}",
        {"fields": payload},
    )
    return {
        "record_id": expert_row.get("record_id"),
        "fields": payload,
        "action": "update",
    }


def upsert_l3_record(client: Any, record: dict[str, Any], *, apply: bool) -> dict[str, Any]:
    if not apply:
        return {"action": "dry-run", "fields": record}
    response = api(
        client,
        "POST",
        f"/bitable/v1/apps/{TARGET_APP_TOKEN}/tables/{L3_TABLE_ID}/records",
        {"fields": record},
    )
    payload = (response.get("data") or {}).get("record") or {}
    return {"action": "create", "record_id": payload.get("record_id"), "fields": record}


def run_scan(args: argparse.Namespace) -> dict[str, Any]:
    client = bootstrap_feishu(args.account_id)
    l2_rows = list_records(client, TARGET_APP_TOKEN, L2_TABLE_ID)
    l3_rows = list_records(client, TARGET_APP_TOKEN, L3_TABLE_ID)
    l2_map = l2_index(l2_rows)
    existing_titles = l3_index(l3_rows)

    experts = [expert for expert in load_experts(client) if should_scan(expert, args)]
    run_date = datetime.now().astimezone().strftime("%Y-%m-%d")
    run_id = f"adagj-{now_local_stamp()}-ts-kb-04-scan"
    run_dir = Path(args.run_root) / run_date / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    scan_results: list[dict[str, Any]] = []
    fallback: dict[str, Any] = {"success": [], "failed": []}
    l2_actions: list[dict[str, Any]] = []
    l3_actions: list[dict[str, Any]] = []
    warnings: list[str] = []
    parsed_sources = 0
    new_candidates = 0

    for index, expert in enumerate(experts):
        result = fetch_candidates_for_expert(expert)
        scan_results.append(
            {
                "expert_id": expert.expert_id,
                "name": expert.name,
                "tier": expert.tier,
                "source_url": expert.source_url,
                "status": result["status"],
                "source_fetch": {k: v for k, v in (result["source_fetch"] or {}).items() if k != "html"},
                "candidates": [
                    {
                        "title": candidate.title,
                        "summary": candidate.summary,
                        "source_url": candidate.source_url,
                        "source_type": candidate.source_type,
                        "insight_date": candidate.insight_date,
                    }
                    for candidate in result["candidates"]
                ],
            }
        )
        if result["status"] != "ok":
            fallback["failed"].append({"expert_id": expert.expert_id, "error": result["warnings"][0] if result["warnings"] else "unknown"})
            warnings.extend(result["warnings"])
            time.sleep(args.sleep_seconds)
            continue

        parsed_sources += 1
        fallback["success"].append({"expert_id": expert.expert_id, "candidates": len(result["candidates"])})

        expert_new_count = 0
        for candidate in result["candidates"]:
            if (candidate.expert_id, candidate.title) in existing_titles:
                continue
            record = candidate.to_record()
            existing_titles.add((candidate.expert_id, candidate.title))
            expert_new_count += 1
            new_candidates += 1
            l3_actions.append(
                {
                    "expert_id": candidate.expert_id,
                    "title": candidate.title,
                    "action": "create" if args.apply else "dry-run",
                    "record": record,
                }
            )
            if args.apply:
                upsert_l3_record(client, record, apply=True)

        expert_row = l2_map.get(expert.expert_id)
        if expert_row:
            l2_actions.append(update_l2_tracking(client, expert_row, expert_new_count, apply=args.apply))
        else:
            warnings.append(f"{expert.expert_id} not found in live L2 table")
        time.sleep(max(args.sleep_seconds, 0.0))

    summary = {
        "mode": "apply" if args.apply else "dry-run",
        "run_id": run_id,
        "run_dir": str(run_dir),
        "account_id": args.account_id,
        "filters": {"expert_id": args.expert_id, "tier": args.tier},
        "expert_count": len(experts),
        "parsed_sources": parsed_sources,
        "new_candidates": new_candidates,
        "l2_total": len(l2_rows),
        "l3_total": len(l3_rows),
    }
    result = {
        "summary": summary,
        "scan_results": scan_results,
        "l2_actions": l2_actions,
        "l3_actions": l3_actions,
        "warnings": warnings,
        "fallback": fallback,
    }

    artifact_path = run_dir / "scan-result.json"
    fallback_path = run_dir / "fallback.json"
    artifact_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    fallback_path.write_text(json.dumps(fallback, ensure_ascii=False, indent=2), encoding="utf-8")
    result["artifact_path"] = str(artifact_path)
    result["fallback_path"] = str(fallback_path)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_scan(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
