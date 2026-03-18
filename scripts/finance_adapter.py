#!/usr/bin/env python3
"""Shared finance adapter for OpenClaw-facing financial skills.

The adapter intentionally separates:
- provider-specific data collection
- query / rule parsing
- normalized result envelopes for frontend skills

V1 supports:
- finance news search
- market / fundamental data lookup
- explainable rule-based stock screening

When `TUSHARE_TOKEN` is present the adapter uses Tushare as the primary
provider. It always keeps the bundled demo dataset as a fallback so the
tooling stays testable and previewable without live credentials.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request


USER_AGENT = "ai-da-guan-jia-finance-adapter/0.1"
DEFAULT_TIMEOUT_SECONDS = 15
CACHE_TTL_SECONDS = 60 * 15

TUSHARE_API_URL = "http://api.tushare.pro"
TUSHARE_MAINLAND_INDEX_MARKETS = ("MS", "CSI", "SSE", "SZSE", "CICC", "SW", "OTH")

FINANCE_STOPWORDS = {
    "今天",
    "今日",
    "现在",
    "最近",
    "请",
    "帮我",
    "查询",
    "查下",
    "查一下",
    "搜一下",
    "看看",
    "告诉我",
    "有什么",
    "有哪些",
    "消息",
    "资讯",
    "新闻",
    "数据",
    "行情",
    "财务",
    "估值",
    "选股",
    "筛股",
    "筛选",
    "规则",
    "按照",
    "给我",
    "一下",
    "的",
}


class FinanceAdapterError(RuntimeError):
    """Base finance adapter error."""


class UpstreamUnavailableError(FinanceAdapterError):
    """Raised when the live data provider is unavailable."""


class UnsupportedRuleError(FinanceAdapterError):
    """Raised when the screener rule set cannot be executed."""


@dataclass
class SecurityMatch:
    kind: str
    symbol: str
    ts_code: str
    name: str
    aliases: list[str]
    metadata: dict[str, Any]


@dataclass
class ScreenRule:
    field: str
    operator: str
    value: Any
    raw: str
    label: str


def normalize_text(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def shorten(text: str, limit: int = 120) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def _shanghai_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def iso_now() -> str:
    return _shanghai_now().isoformat(timespec="seconds")


def _dedupe_strings(values: list[str]) -> list[str]:
    return list(dict.fromkeys([str(item).strip() for item in values if str(item).strip()]))


def _safe_float(value: Any) -> float | None:
    if value in ("", None, "None", "null"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    number = _safe_float(value)
    if number is None:
        return None
    return int(number)


def _contains_any(text: str, candidates: list[str]) -> bool:
    normalized = normalize_text(text)
    return any(normalize_text(candidate) in normalized for candidate in candidates)


def _guess_topic_tokens(query: str) -> list[str]:
    cleaned = str(query or "")
    cleaned = re.sub(r"[，。、“”‘’：:；;,.!?！？()（）/\\]", " ", cleaned)
    cleaned = cleaned.replace("板块", " ").replace("行业", " ").replace("指数", " ").replace("基金", " ")
    tokens = [token.strip() for token in cleaned.split() if token.strip()]
    filtered = [token for token in tokens if token not in FINANCE_STOPWORDS and len(token) >= 2]
    return _dedupe_strings(filtered)


class FinanceProvider:
    """Provider protocol."""

    provider_id = "base"
    provider_label = "unknown"

    def search_news(self, query: str, *, limit: int = 5, days: int = 1) -> dict[str, Any]:
        raise NotImplementedError

    def resolve_security(self, query: str) -> SecurityMatch | None:
        raise NotImplementedError

    def query_security(self, match: SecurityMatch, *, metrics: list[str] | None = None) -> dict[str, Any]:
        raise NotImplementedError

    def build_screen_universe(self) -> dict[str, Any]:
        raise NotImplementedError


class DemoFinanceProvider(FinanceProvider):
    provider_id = "demo"
    provider_label = "bundled_demo_dataset"

    def __init__(self, dataset_path: Path):
        self.dataset_path = Path(dataset_path)
        payload = json.loads(self.dataset_path.read_text(encoding="utf-8"))
        self.payload = payload if isinstance(payload, dict) else {}
        self.metadata = self.payload.get("metadata", {}) if isinstance(self.payload.get("metadata"), dict) else {}
        self.news_items = self.payload.get("news", []) if isinstance(self.payload.get("news"), list) else []
        self.securities = self.payload.get("securities", []) if isinstance(self.payload.get("securities"), list) else []
        self.screen_rows = self.payload.get("screen_universe", []) if isinstance(self.payload.get("screen_universe"), list) else []
        self._security_index: list[SecurityMatch] = []
        for row in self.securities:
            if not isinstance(row, dict):
                continue
            aliases = _dedupe_strings(
                [
                    str(row.get("name", "")),
                    str(row.get("symbol", "")),
                    str(row.get("ts_code", "")),
                    *[str(item) for item in row.get("aliases", []) if isinstance(item, str)],
                ]
            )
            self._security_index.append(
                SecurityMatch(
                    kind=str(row.get("kind", "")).strip() or "stock",
                    symbol=str(row.get("symbol", "")).strip() or str(row.get("ts_code", "")).strip(),
                    ts_code=str(row.get("ts_code", "")).strip() or str(row.get("symbol", "")).strip(),
                    name=str(row.get("name", "")).strip() or str(row.get("symbol", "")).strip(),
                    aliases=aliases,
                    metadata=row,
                )
            )

    def search_news(self, query: str, *, limit: int = 5, days: int = 1) -> dict[str, Any]:
        tokens = _guess_topic_tokens(query)
        now_dt = datetime.fromisoformat(str(self.metadata.get("as_of", iso_now())))
        cutoff = now_dt - timedelta(days=max(days, 1))
        matches: list[dict[str, Any]] = []
        for item in self.news_items:
            if not isinstance(item, dict):
                continue
            published_at = str(item.get("published_at", "")).strip()
            try:
                published_dt = datetime.fromisoformat(published_at)
            except ValueError:
                published_dt = now_dt
            if published_dt < cutoff:
                continue
            haystack = normalize_text(" ".join([str(item.get("title", "")), str(item.get("summary", "")), str(item.get("content", ""))]))
            if tokens and not all(token.lower() in haystack for token in tokens):
                continue
            matches.append(
                {
                    "title": str(item.get("title", "")).strip(),
                    "summary": str(item.get("summary", "")).strip() or shorten(str(item.get("content", "")).strip(), limit=90),
                    "source": str(item.get("source", "demo")).strip() or "demo",
                    "published_at": published_at,
                    "source_label": f"{self.provider_label}:{str(item.get('source', 'demo')).strip() or 'demo'}",
                    "evidence_type": "news",
                }
            )
        matches.sort(key=lambda row: str(row.get("published_at", "")), reverse=True)
        return {
            "provider": self.provider_id,
            "source_label": self.provider_label,
            "as_of": str(self.metadata.get("as_of", iso_now())),
            "items": matches[: max(limit, 1)],
        }

    def resolve_security(self, query: str) -> SecurityMatch | None:
        normalized = normalize_text(query)
        if not normalized:
            return None
        best: SecurityMatch | None = None
        best_score = -1
        for match in self._security_index:
            score = 0
            for alias in match.aliases:
                alias_norm = normalize_text(alias)
                if not alias_norm:
                    continue
                if normalized == alias_norm:
                    score = max(score, 200)
                elif alias_norm in normalized or normalized in alias_norm:
                    score = max(score, 120 + len(alias_norm))
            if match.kind == "sector" and ("板块" in query or "行业" in query):
                score += 10
            if score > best_score:
                best = match
                best_score = score
        return best if best_score > 0 else None

    def query_security(self, match: SecurityMatch, *, metrics: list[str] | None = None) -> dict[str, Any]:
        del metrics
        row = dict(match.metadata)
        return {
            "provider": self.provider_id,
            "source_label": self.provider_label,
            "as_of": str(self.metadata.get("as_of", iso_now())),
            "security": {
                "kind": match.kind,
                "name": match.name,
                "symbol": match.symbol,
                "ts_code": match.ts_code,
            },
            "quote": row.get("quote", {}) if isinstance(row.get("quote"), dict) else {},
            "fundamentals": row.get("fundamentals", {}) if isinstance(row.get("fundamentals"), dict) else {},
        }

    def build_screen_universe(self) -> dict[str, Any]:
        return {
            "provider": self.provider_id,
            "source_label": self.provider_label,
            "as_of": str(self.metadata.get("as_of", iso_now())),
            "rows": [dict(item) for item in self.screen_rows if isinstance(item, dict)],
        }


class TushareFinanceProvider(FinanceProvider):
    provider_id = "tushare"
    provider_label = "tushare_pro"

    def __init__(self, token: str, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS):
        self.token = str(token or "").strip()
        self.timeout_seconds = timeout_seconds
        self._last_request_at = 0.0
        self._basics_cache: dict[str, list[dict[str, Any]]] = {}
        if not self.token:
            raise ValueError("TUSHARE_TOKEN is required for the Tushare provider.")

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request_at
        min_interval = 0.35
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)

    def _post(self, api_name: str, params: dict[str, Any] | None = None, fields: str = "") -> list[dict[str, Any]]:
        self._throttle()
        payload = {
            "api_name": api_name,
            "token": self.token,
            "params": params or {},
            "fields": fields,
        }
        request = urllib_request.Request(
            TUSHARE_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        try:
            with urllib_request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib_error.URLError as exc:  # pragma: no cover - network dependent
            raise UpstreamUnavailableError(f"Tushare request failed: {exc}") from exc
        finally:
            self._last_request_at = time.time()
        if int(raw.get("code", -1)) != 0:
            raise UpstreamUnavailableError(f"Tushare returned code={raw.get('code')}: {raw.get('msg')}")
        data = raw.get("data") or {}
        fields_list = data.get("fields") or []
        items = data.get("items") or []
        return [dict(zip(fields_list, row)) for row in items if isinstance(row, list)]

    def _load_stock_basic(self) -> list[dict[str, Any]]:
        cached = self._basics_cache.get("stock_basic")
        if cached is not None:
            return cached
        rows = self._post(
            "stock_basic",
            {"list_status": "L"},
            "ts_code,symbol,name,area,industry,market,list_date,exchange,act_name",
        )
        self._basics_cache["stock_basic"] = rows
        return rows

    def _load_index_basic(self) -> list[dict[str, Any]]:
        cached = self._basics_cache.get("index_basic")
        if cached is not None:
            return cached
        rows: list[dict[str, Any]] = []
        for market in TUSHARE_MAINLAND_INDEX_MARKETS:
            try:
                rows.extend(
                    self._post(
                        "index_basic",
                        {"market": market},
                        "ts_code,name,fullname,market,publisher,category,list_date",
                    )
                )
            except UpstreamUnavailableError:
                continue
        self._basics_cache["index_basic"] = rows
        return rows

    def _load_fund_basic(self) -> list[dict[str, Any]]:
        cached = self._basics_cache.get("fund_basic")
        if cached is not None:
            return cached
        rows = self._post(
            "fund_basic",
            {"market": "E", "status": "L"},
            "ts_code,name,management,custodian,fund_type,found_date,benchmark,invest_type",
        )
        self._basics_cache["fund_basic"] = rows
        return rows

    def _latest_trade_date(self) -> str:
        end = _shanghai_now().strftime("%Y%m%d")
        start = (_shanghai_now() - timedelta(days=14)).strftime("%Y%m%d")
        rows = self._post("trade_cal", {"exchange": "SSE", "start_date": start, "end_date": end}, "cal_date,is_open")
        open_days = [str(row.get("cal_date", "")).strip() for row in rows if str(row.get("is_open", "")) == "1"]
        if not open_days:
            raise UpstreamUnavailableError("Unable to determine latest trade date from Tushare.")
        return sorted(open_days)[-1]

    def _major_news_sources(self) -> list[str]:
        return ["新浪财经", "同花顺", "华尔街见闻", "金十数据", "财联社"]

    def search_news(self, query: str, *, limit: int = 5, days: int = 1) -> dict[str, Any]:
        tokens = _guess_topic_tokens(query)
        if not tokens:
            tokens = [normalize_text(query)]
        end = _shanghai_now()
        start = end - timedelta(days=max(days, 1))
        matches: list[dict[str, Any]] = []
        for source in self._major_news_sources():
            try:
                rows = self._post(
                    "major_news",
                    {
                        "src": source,
                        "start_date": start.strftime("%Y-%m-%d %H:%M:%S"),
                        "end_date": end.strftime("%Y-%m-%d %H:%M:%S"),
                    },
                    "title,content,pub_time,src",
                )
            except UpstreamUnavailableError:
                continue
            for row in rows:
                haystack = normalize_text(" ".join([str(row.get("title", "")), str(row.get("content", ""))]))
                if tokens and not all(token.lower() in haystack for token in tokens):
                    continue
                matches.append(
                    {
                        "title": str(row.get("title", "")).strip(),
                        "summary": shorten(str(row.get("content", "")).strip(), limit=96),
                        "source": str(row.get("src", source)).strip() or source,
                        "published_at": str(row.get("pub_time", "")).strip(),
                        "source_label": f"{self.provider_label}:major_news",
                        "evidence_type": "news",
                    }
                )
        dedup: dict[tuple[str, str], dict[str, Any]] = {}
        for item in matches:
            key = (str(item.get("title", "")).strip(), str(item.get("published_at", "")).strip())
            dedup.setdefault(key, item)
        ordered = sorted(dedup.values(), key=lambda row: str(row.get("published_at", "")), reverse=True)
        return {
            "provider": self.provider_id,
            "source_label": f"{self.provider_label}:major_news",
            "as_of": iso_now(),
            "items": ordered[: max(limit, 1)],
        }

    def resolve_security(self, query: str) -> SecurityMatch | None:
        normalized = normalize_text(query)
        if not normalized:
            return None

        explicit_code = re.search(r"\b\d{6}\.(?:sz|sh|bj|of)\b", normalized, re.IGNORECASE)
        if explicit_code:
            code = explicit_code.group(0).upper()
            for dataset_name, dataset, kind in (
                ("stock_basic", self._load_stock_basic(), "stock"),
                ("index_basic", self._load_index_basic(), "index"),
                ("fund_basic", self._load_fund_basic(), "fund"),
            ):
                for row in dataset:
                    if str(row.get("ts_code", "")).strip().upper() != code:
                        continue
                    return SecurityMatch(
                        kind=kind,
                        symbol=str(row.get("symbol", "")).strip() or code.split(".")[0],
                        ts_code=code,
                        name=str(row.get("name", "")).strip() or code,
                        aliases=_dedupe_strings([code, str(row.get("name", "")), str(row.get("symbol", ""))]),
                        metadata={"dataset": dataset_name, **row},
                    )

        candidates: list[tuple[int, SecurityMatch]] = []
        for dataset_name, dataset, kind in (
            ("stock_basic", self._load_stock_basic(), "stock"),
            ("index_basic", self._load_index_basic(), "index"),
            ("fund_basic", self._load_fund_basic(), "fund"),
        ):
            for row in dataset:
                aliases = _dedupe_strings(
                    [
                        str(row.get("name", "")),
                        str(row.get("ts_code", "")),
                        str(row.get("symbol", "")),
                        str(row.get("fullname", "")),
                    ]
                )
                score = 0
                for alias in aliases:
                    alias_norm = normalize_text(alias)
                    if not alias_norm:
                        continue
                    if normalized == alias_norm:
                        score = max(score, 300)
                    elif alias_norm in normalized or normalized in alias_norm:
                        score = max(score, 150 + len(alias_norm))
                if score <= 0:
                    continue
                candidates.append(
                    (
                        score,
                        SecurityMatch(
                            kind=kind,
                            symbol=str(row.get("symbol", "")).strip() or str(row.get("ts_code", "")).split(".")[0],
                            ts_code=str(row.get("ts_code", "")).strip(),
                            name=str(row.get("name", "")).strip() or str(row.get("fullname", "")).strip(),
                            aliases=aliases,
                            metadata={"dataset": dataset_name, **row},
                        ),
                    )
                )
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    def query_security(self, match: SecurityMatch, *, metrics: list[str] | None = None) -> dict[str, Any]:
        del metrics
        trade_date = self._latest_trade_date()
        quote: dict[str, Any] = {}
        fundamentals: dict[str, Any] = {}

        if match.kind == "stock":
            daily_rows = self._post(
                "daily",
                {"ts_code": match.ts_code, "trade_date": trade_date},
                "ts_code,trade_date,open,high,low,close,pre_close,pct_chg,vol,amount",
            )
            if daily_rows:
                row = daily_rows[0]
                quote = {
                    "open": _safe_float(row.get("open")),
                    "high": _safe_float(row.get("high")),
                    "low": _safe_float(row.get("low")),
                    "close": _safe_float(row.get("close")),
                    "pct_change": _safe_float(row.get("pct_chg")),
                    "volume": _safe_float(row.get("vol")),
                    "amount": _safe_float(row.get("amount")),
                    "trade_date": str(row.get("trade_date", trade_date)).strip(),
                }
            basic_rows = self._post(
                "daily_basic",
                {"ts_code": match.ts_code, "trade_date": trade_date},
                "ts_code,trade_date,close,turnover_rate,pe,pb,total_mv,circ_mv",
            )
            if basic_rows:
                row = basic_rows[0]
                fundamentals.update(
                    {
                        "pe": _safe_float(row.get("pe")),
                        "pb": _safe_float(row.get("pb")),
                        "turnover_rate": _safe_float(row.get("turnover_rate")),
                        "total_mv": _safe_float(row.get("total_mv")),
                        "circ_mv": _safe_float(row.get("circ_mv")),
                        "trade_date": str(row.get("trade_date", trade_date)).strip(),
                    }
                )
            indicator_rows = self._post(
                "fina_indicator",
                {"ts_code": match.ts_code, "limit": 1},
                "ts_code,end_date,ann_date,roe,roa,grossprofit_margin,q_sales_yoy,eps,bps",
            )
            if indicator_rows:
                row = indicator_rows[0]
                fundamentals.update(
                    {
                        "report_end_date": str(row.get("end_date", "")).strip(),
                        "ann_date": str(row.get("ann_date", "")).strip(),
                        "roe": _safe_float(row.get("roe")),
                        "roa": _safe_float(row.get("roa")),
                        "grossprofit_margin": _safe_float(row.get("grossprofit_margin")),
                        "revenue_yoy": _safe_float(row.get("q_sales_yoy")),
                        "eps": _safe_float(row.get("eps")),
                        "bps": _safe_float(row.get("bps")),
                    }
                )
        elif match.kind == "index":
            rows = self._post(
                "index_daily",
                {"ts_code": match.ts_code, "trade_date": trade_date},
                "ts_code,trade_date,open,high,low,close,pre_close,pct_chg,vol,amount",
            )
            if rows:
                row = rows[0]
                quote = {
                    "open": _safe_float(row.get("open")),
                    "high": _safe_float(row.get("high")),
                    "low": _safe_float(row.get("low")),
                    "close": _safe_float(row.get("close")),
                    "pct_change": _safe_float(row.get("pct_chg")),
                    "volume": _safe_float(row.get("vol")),
                    "amount": _safe_float(row.get("amount")),
                    "trade_date": str(row.get("trade_date", trade_date)).strip(),
                }
        elif match.kind == "fund":
            rows = self._post(
                "fund_nav",
                {"ts_code": match.ts_code, "limit": 1},
                "ts_code,end_date,unit_nav,accum_nav,adj_nav",
            )
            if rows:
                row = rows[0]
                quote = {
                    "unit_nav": _safe_float(row.get("unit_nav")),
                    "accum_nav": _safe_float(row.get("accum_nav")),
                    "adj_nav": _safe_float(row.get("adj_nav")),
                    "trade_date": str(row.get("end_date", trade_date)).strip(),
                }
        else:
            raise UpstreamUnavailableError(f"Unsupported Tushare security kind: {match.kind}")

        return {
            "provider": self.provider_id,
            "source_label": self.provider_label,
            "as_of": iso_now(),
            "security": {
                "kind": match.kind,
                "name": match.name,
                "symbol": match.symbol,
                "ts_code": match.ts_code,
            },
            "quote": quote,
            "fundamentals": fundamentals,
        }

    def build_screen_universe(self) -> dict[str, Any]:
        trade_date = self._latest_trade_date()
        stock_basic = {str(row.get("ts_code", "")).strip(): row for row in self._load_stock_basic()}
        daily_basic_rows = self._post(
            "daily_basic",
            {"trade_date": trade_date},
            "ts_code,trade_date,close,turnover_rate,pe,pb,total_mv,circ_mv",
        )
        rows: list[dict[str, Any]] = []
        for row in daily_basic_rows:
            ts_code = str(row.get("ts_code", "")).strip()
            basic = stock_basic.get(ts_code, {})
            rows.append(
                {
                    "ts_code": ts_code,
                    "name": str(basic.get("name", "")).strip() or ts_code,
                    "industry": str(basic.get("industry", "")).strip(),
                    "trade_date": str(row.get("trade_date", trade_date)).strip(),
                    "close": _safe_float(row.get("close")),
                    "pe": _safe_float(row.get("pe")),
                    "pb": _safe_float(row.get("pb")),
                    "turnover_rate": _safe_float(row.get("turnover_rate")),
                    "market_cap": _safe_float(row.get("total_mv")),
                    "circulating_market_cap": _safe_float(row.get("circ_mv")),
                    "revenue_yoy": None,
                    "pct_change_20d": None,
                }
            )
        return {
            "provider": self.provider_id,
            "source_label": f"{self.provider_label}:daily_basic",
            "as_of": iso_now(),
            "rows": rows,
        }


class FinanceAdapter:
    def __init__(self, demo_dataset_path: Path):
        self.demo_provider = DemoFinanceProvider(demo_dataset_path)
        token = str(os.getenv("TUSHARE_TOKEN", "")).strip()
        self.live_provider = TushareFinanceProvider(token) if token else None
        self.default_provider = str(os.getenv("AI_DA_GUAN_JIA_FINANCE_PROVIDER", "auto")).strip().lower() or "auto"
        self._cache: dict[str, tuple[float, Any]] = {}

    def _cache_key(self, prefix: str, *parts: Any) -> str:
        return "|".join([prefix, *[str(part) for part in parts]])

    def _cache_get(self, key: str) -> Any | None:
        cached = self._cache.get(key)
        if cached is None:
            return None
        expires_at, payload = cached
        if time.time() >= expires_at:
            self._cache.pop(key, None)
            return None
        return payload

    def _cache_set(self, key: str, payload: Any, *, ttl_seconds: int = CACHE_TTL_SECONDS) -> Any:
        self._cache[key] = (time.time() + ttl_seconds, payload)
        return payload

    def _iter_providers(self) -> list[FinanceProvider]:
        if self.default_provider == "demo":
            return [self.demo_provider]
        if self.default_provider == "tushare" and self.live_provider is not None:
            return [self.live_provider, self.demo_provider]
        if self.live_provider is not None:
            return [self.live_provider, self.demo_provider]
        return [self.demo_provider]

    def _normalize_news_result(self, query: str, payload: dict[str, Any], *, requested_days: int, limit: int) -> dict[str, Any]:
        items = payload.get("items", []) if isinstance(payload.get("items"), list) else []
        facts = items[: max(limit, 1)]
        if not facts:
            return {
                "status": "not_found",
                "query": query,
                "source_label": str(payload.get("source_label", "")),
                "facts": [],
                "inference": "没有命中足够近期且和关键词直接相关的金融资讯。",
                "summary": f"未找到足够近期的金融资讯：{query}",
                "missing": f"已按最近 {requested_days} 天搜索；建议换更明确的标的、板块或主题关键词。",
                "verification_status": "not_found",
                "as_of": str(payload.get("as_of", iso_now())),
            }
        fact_summary = "；".join(
            [
                f"{str(item.get('published_at', '')).strip()}｜{str(item.get('source', '')).strip()}｜{shorten(str(item.get('title', '')).strip(), limit=42)}"
                for item in facts
            ]
        )
        return {
            "status": "ok",
            "query": query,
            "source_label": str(payload.get("source_label", "")),
            "facts": facts,
            "inference": f"按关键词筛出 {len(facts)} 条近期资讯，未自动推导投资结论。",
            "summary": f"找到 {len(facts)} 条金融资讯：{fact_summary}",
            "missing": "",
            "verification_status": "facts_with_sources",
            "as_of": str(payload.get("as_of", iso_now())),
        }

    def search_news(self, query: str, *, limit: int = 5, days: int = 1) -> dict[str, Any]:
        cache_key = self._cache_key("news", normalize_text(query), limit, days, self.default_provider, bool(self.live_provider))
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        last_error = ""
        for provider in self._iter_providers():
            try:
                payload = provider.search_news(query, limit=limit, days=days)
            except UpstreamUnavailableError as exc:
                last_error = str(exc)
                continue
            result = self._normalize_news_result(query, payload, requested_days=days, limit=limit)
            return self._cache_set(cache_key, result)
        return self._cache_set(
            cache_key,
            {
                "status": "upstream_unavailable",
                "query": query,
                "source_label": "unavailable",
                "facts": [],
                "inference": "新闻上游暂时不可用。",
                "summary": f"金融资讯暂时不可用：{query}",
                "missing": last_error or "请检查 Tushare token、网络连通性或改用 demo 数据进行预览。",
                "verification_status": "upstream_unavailable",
                "as_of": iso_now(),
            },
        )

    def resolve_security(self, query: str) -> SecurityMatch | None:
        cache_key = self._cache_key("resolve", normalize_text(query))
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        for provider in self._iter_providers():
            try:
                match = provider.resolve_security(query)
            except UpstreamUnavailableError:
                continue
            if match is not None:
                return self._cache_set(cache_key, match)
        return None

    def _extract_requested_metrics(self, query: str) -> list[str]:
        normalized = normalize_text(query)
        metric_map = {
            "pe": ["pe", "市盈率"],
            "pb": ["pb", "市净率"],
            "market_cap": ["市值", "总市值", "market cap"],
            "turnover_rate": ["换手率", "turnover"],
            "revenue_yoy": ["营收同比", "收入同比", "sales yoy"],
            "roe": ["roe", "净资产收益率"],
            "pct_change": ["涨跌幅", "涨幅", "pct chg"],
            "close": ["收盘价", "close", "价格", "行情"],
            "unit_nav": ["净值", "nav"],
        }
        requested: list[str] = []
        for metric, aliases in metric_map.items():
            if any(alias.lower() in normalized for alias in aliases):
                requested.append(metric)
        return requested

    def query_data(self, query: str) -> dict[str, Any]:
        match = self.resolve_security(query)
        if match is None:
            return {
                "status": "not_found",
                "query": query,
                "source_label": "resolver",
                "security": {},
                "facts": [],
                "inference": "没有在当前 provider 中解析到证券对象。",
                "summary": f"未识别到证券对象：{query}",
                "missing": "请提供更明确的证券代码、简称或指数/基金名称。",
                "verification_status": "not_found",
                "as_of": iso_now(),
            }

        metrics = self._extract_requested_metrics(query)
        cache_key = self._cache_key("data", match.kind, match.ts_code, ",".join(sorted(metrics)), self.default_provider, bool(self.live_provider))
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        last_error = ""
        for provider in self._iter_providers():
            try:
                payload = provider.query_security(match, metrics=metrics)
            except UpstreamUnavailableError as exc:
                last_error = str(exc)
                continue
            quote = payload.get("quote", {}) if isinstance(payload.get("quote"), dict) else {}
            fundamentals = payload.get("fundamentals", {}) if isinstance(payload.get("fundamentals"), dict) else {}
            facts: list[dict[str, Any]] = []
            for label, value, unit, fact_type in (
                ("收盘价", quote.get("close"), "", "quote"),
                ("涨跌幅", quote.get("pct_change"), "%", "quote"),
                ("市盈率", fundamentals.get("pe"), "", "fundamental"),
                ("市净率", fundamentals.get("pb"), "", "fundamental"),
                ("营收同比", fundamentals.get("revenue_yoy"), "%", "fundamental"),
                ("ROE", fundamentals.get("roe"), "%", "fundamental"),
                ("基金单位净值", quote.get("unit_nav"), "", "quote"),
                ("基金累计净值", quote.get("accum_nav"), "", "quote"),
            ):
                if value is None:
                    continue
                facts.append({"label": label, "value": value, "unit": unit, "fact_type": fact_type})
            trade_date = str(quote.get("trade_date") or fundamentals.get("trade_date") or fundamentals.get("report_end_date") or payload.get("as_of", iso_now()))
            security = payload.get("security", {}) if isinstance(payload.get("security"), dict) else {}
            result = {
                "status": "ok",
                "query": query,
                "source_label": str(payload.get("source_label", "")),
                "security": security,
                "facts": facts,
                "quote": quote,
                "fundamentals": fundamentals,
                "inference": "只返回事实数据与显式字段，不自动给出投资建议。",
                "summary": f"{security.get('name', match.name)}（{security.get('ts_code', match.ts_code)}）数据已准备好，截至 {trade_date}。",
                "missing": "" if facts else "当前只解析到了证券对象，还没有取到稳定字段。",
                "verification_status": "facts_with_sources" if facts else "partial",
                "as_of": str(payload.get("as_of", iso_now())),
            }
            return self._cache_set(cache_key, result)

        return self._cache_set(
            cache_key,
            {
                "status": "upstream_unavailable",
                "query": query,
                "source_label": "unavailable",
                "security": {
                    "kind": match.kind,
                    "name": match.name,
                    "ts_code": match.ts_code,
                    "symbol": match.symbol,
                },
                "facts": [],
                "inference": "金融数据上游暂时不可用。",
                "summary": f"金融数据暂时不可用：{match.name}",
                "missing": last_error or "请检查 Tushare token、网络或切换到 demo provider。",
                "verification_status": "upstream_unavailable",
                "as_of": iso_now(),
            },
        )

    def parse_screen_rules(self, query: str) -> tuple[list[ScreenRule], list[str]]:
        text = str(query or "")
        rules: list[ScreenRule] = []
        unsupported: list[str] = []
        patterns = [
            (
                r"(?:pe|市盈率)\s*(<=|>=|=|<|>)\s*(\d+(?:\.\d+)?)",
                lambda op, value, raw: ScreenRule("pe", op, float(value), raw, f"PE {op} {value}"),
            ),
            (
                r"(?:pb|市净率)\s*(<=|>=|=|<|>)\s*(\d+(?:\.\d+)?)",
                lambda op, value, raw: ScreenRule("pb", op, float(value), raw, f"PB {op} {value}"),
            ),
            (
                r"(?:近|最近)?\s*20\s*日(?:涨幅|涨跌幅|涨跌)\s*(<=|>=|=|<|>)\s*(\d+(?:\.\d+)?)%?",
                lambda op, value, raw: ScreenRule("pct_change_20d", op, float(value), raw, f"近20日涨幅 {op} {value}%"),
            ),
            (
                r"(?:营收同比|收入同比|sales yoy)\s*(<=|>=|=|<|>)\s*(\d+(?:\.\d+)?)%?",
                lambda op, value, raw: ScreenRule("revenue_yoy", op, float(value), raw, f"营收同比 {op} {value}%"),
            ),
            (
                r"(?:所属行业|行业)\s*(?:=|是|为)\s*([^\s，。,；;]+)",
                lambda _op, value, raw: ScreenRule("industry", "=", value.strip(), raw, f"所属行业 = {value.strip()}"),
            ),
        ]
        consumed: list[str] = []
        for pattern, factory in patterns:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                raw = match.group(0)
                consumed.append(raw)
                groups = match.groups()
                if len(groups) == 2:
                    rule = factory(groups[0], groups[1], raw)
                else:
                    rule = factory("", groups[0], raw)
                rules.append(rule)
        if "选股" in text or "筛股" in text or "筛选" in text:
            stripped = text
            for piece in consumed:
                stripped = stripped.replace(piece, " ")
            stripped = stripped.replace("选股", " ").replace("筛股", " ").replace("筛选", " ").replace("股票", " ")
            leftovers = [token for token in _guess_topic_tokens(stripped) if token not in {"规则"}]
            if leftovers:
                unsupported.extend(leftovers)
        return rules, unsupported

    @staticmethod
    def _compare(left: Any, operator: str, right: Any) -> bool:
        if left is None:
            return False
        if operator == "<":
            return left < right
        if operator == "<=":
            return left <= right
        if operator == ">":
            return left > right
        if operator == ">=":
            return left >= right
        return left == right

    def screen_stocks(self, query: str, *, limit: int = 10) -> dict[str, Any]:
        rules, unsupported = self.parse_screen_rules(query)
        if unsupported:
            return {
                "status": "invalid_rule",
                "query": query,
                "rules": [rule.label for rule in rules],
                "rejected_rules": unsupported,
                "results": [],
                "source_label": "rule_parser",
                "summary": "规则里包含当前 V1 还不支持自动执行的条件。",
                "missing": f"未支持的条件片段：{', '.join(unsupported)}",
                "verification_status": "invalid_rule",
                "as_of": iso_now(),
            }
        if not rules:
            return {
                "status": "invalid_rule",
                "query": query,
                "rules": [],
                "rejected_rules": [],
                "results": [],
                "source_label": "rule_parser",
                "summary": "没有解析到可执行的显式选股规则。",
                "missing": "请使用显式条件，例如 `PE < 20`、`营收同比 > 15%`、`所属行业 = 半导体`。",
                "verification_status": "invalid_rule",
                "as_of": iso_now(),
            }

        cache_key = self._cache_key("screen", normalize_text(query), limit, self.default_provider, bool(self.live_provider))
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        last_error = ""
        for provider in self._iter_providers():
            try:
                universe = provider.build_screen_universe()
            except UpstreamUnavailableError as exc:
                last_error = str(exc)
                continue
            rows = universe.get("rows", []) if isinstance(universe.get("rows"), list) else []
            matched_rows: list[dict[str, Any]] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                matched = True
                matched_rule_labels: list[str] = []
                for rule in rules:
                    field_value = row.get(rule.field)
                    if rule.field == "industry":
                        if normalize_text(str(field_value or "")) != normalize_text(str(rule.value)):
                            matched = False
                            break
                    elif not self._compare(_safe_float(field_value), rule.operator, float(rule.value)):
                        matched = False
                        break
                    matched_rule_labels.append(rule.label)
                if matched:
                    matched_rows.append(
                        {
                            "ts_code": str(row.get("ts_code", "")).strip(),
                            "name": str(row.get("name", "")).strip(),
                            "industry": str(row.get("industry", "")).strip(),
                            "trade_date": str(row.get("trade_date", "")).strip(),
                            "close": _safe_float(row.get("close")),
                            "pe": _safe_float(row.get("pe")),
                            "pb": _safe_float(row.get("pb")),
                            "pct_change_20d": _safe_float(row.get("pct_change_20d")),
                            "revenue_yoy": _safe_float(row.get("revenue_yoy")),
                            "market_cap": _safe_float(row.get("market_cap")),
                            "matched_rules": matched_rule_labels,
                        }
                    )
            sort_fields = ["pct_change_20d", "revenue_yoy", "market_cap", "close"]
            matched_rows.sort(
                key=lambda row: tuple((row.get(field) if row.get(field) is not None else float("-inf")) for field in sort_fields),
                reverse=True,
            )
            top = matched_rows[: max(limit, 1)]
            result = {
                "status": "ok" if top else "not_found",
                "query": query,
                "rules": [rule.label for rule in rules],
                "rejected_rules": [],
                "results": top,
                "sort_fields": sort_fields,
                "source_label": str(universe.get("source_label", "")),
                "summary": f"命中 {len(top)} 只股票；结果只反映显式规则，不代表投资建议。" if top else "没有股票命中当前显式规则。",
                "missing": "" if top else "建议放宽阈值或增加行业限定后重试。",
                "verification_status": "screen_results" if top else "not_found",
                "as_of": str(universe.get("as_of", iso_now())),
            }
            return self._cache_set(cache_key, result)

        return self._cache_set(
            cache_key,
            {
                "status": "upstream_unavailable",
                "query": query,
                "rules": [rule.label for rule in rules],
                "rejected_rules": [],
                "results": [],
                "sort_fields": [],
                "source_label": "unavailable",
                "summary": "智能选股上游暂时不可用。",
                "missing": last_error or "请检查 Tushare token 或先用 demo 数据预览规则链路。",
                "verification_status": "upstream_unavailable",
                "as_of": iso_now(),
            },
        )
