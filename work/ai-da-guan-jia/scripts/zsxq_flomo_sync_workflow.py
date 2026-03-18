#!/usr/bin/env python3
"""ZSXQ column -> flomo sync workflow for AI大管家."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

import flomo_zsxq_workflow as flomo_helpers


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
ARTIFACTS_ROOT = SKILL_DIR / "artifacts" / "ai-da-guan-jia"
ZSXQ_FLOMO_ROOT = ARTIFACTS_ROOT / "zsxq-flomo"
ZSXQ_FLOMO_RUNS_ROOT = ZSXQ_FLOMO_ROOT / "runs"
ZSXQ_FLOMO_CURRENT_ROOT = ZSXQ_FLOMO_ROOT / "current"
ZSXQ_FLOMO_CHECKPOINT_PATH = ZSXQ_FLOMO_CURRENT_ROOT / "checkpoint.json"
ZSXQ_FLOMO_ENTRY_LEDGER_PATH = ZSXQ_FLOMO_CURRENT_ROOT / "entry-ledger.json"
ZSXQ_FLOMO_LATEST_SCAN_PATH = ZSXQ_FLOMO_CURRENT_ROOT / "latest-scan.json"
ZSXQ_FLOMO_IMPORT_PREVIEW_PATH = ZSXQ_FLOMO_CURRENT_ROOT / "import-preview.json"
ZSXQ_FLOMO_WRITE_RESULT_PATH = ZSXQ_FLOMO_CURRENT_ROOT / "write-result.json"
DEFAULT_TAG = "#星球精选"
DEFAULT_SOURCE_TAG = "#原力养龙虾"
DEFAULT_EXISTING_MEMO_LIMIT = 200
DEFAULT_CHROME_USER_DATA_DIR = Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


ensure_dir = flomo_helpers.ensure_dir
iso_now = flomo_helpers.iso_now
write_json = flomo_helpers.write_json
read_json = flomo_helpers.read_json
load_optional_json = flomo_helpers.load_optional_json
normalize_list = flomo_helpers.normalize_list
stable_hash = flomo_helpers.stable_hash
truncate = flomo_helpers.truncate
parse_datetime = flomo_helpers.parse_datetime
canonical_timestamp = flomo_helpers.canonical_timestamp
read_mcp_config = flomo_helpers.read_mcp_config
flomo_setup_hint = flomo_helpers.flomo_setup_hint
run_codex_exec_json = flomo_helpers.run_codex_exec_json
run_codex_exec_last_message = flomo_helpers.run_codex_exec_last_message
FLOMO_MCP_SERVER_NAME = flomo_helpers.FLOMO_MCP_SERVER_NAME


def normalize_prompt(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def normalize_slug_part(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", normalize_prompt(value))
    normalized = normalized.strip("-")
    return normalized or "unknown"


def strip_html_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", str(value or ""))


def module_available(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def login_like_content(html_text: str) -> bool:
    lowered = normalize_prompt(strip_html_tags(html_text))
    return any(
        keyword in lowered
        for keyword in ["login", "sign in", "登录", "扫码", "继续使用", "请先登录", "手机号登录", "微信登录"]
    )


def preview_gate_like_content(html_text: str) -> bool:
    lowered = normalize_prompt(strip_html_tags(html_text))
    gate_markers = [
        "加入星球后可查看全部",
        "精选主题预览",
        "本期低至",
        "付费须知",
    ]
    return "加入星球" in lowered and any(marker in lowered for marker in gate_markers)


def normalize_tag(tag: str) -> str:
    text = str(tag or "").strip()
    if not text:
        return ""
    return text if text.startswith("#") else f"#{text}"


def normalized_tags(value: Any) -> list[str]:
    return [tag for tag in [normalize_tag(item) for item in normalize_list(value)] if tag]


def memo_has_tag(memo: dict[str, Any], tag: str) -> bool:
    normalized = normalize_tag(tag)
    if not normalized:
        return False
    if normalized in normalized_tags(memo.get("tags")):
        return True
    return normalized in str(memo.get("content") or "")


def safe_body_text(page: Any) -> str:
    try:
        return str(page.locator("body").inner_text(timeout=10000) or "")
    except Exception:
        return ""


def zsxq_run_id(created_at: str) -> str:
    stamp = (parse_datetime(created_at) or flomo_helpers.now_local()).strftime("%Y%m%d-%H%M%S-%f")
    return f"zsxq-flomo-{stamp}"


def run_dir_for(run_id: str, created_at: str) -> Path:
    dt = parse_datetime(created_at) or flomo_helpers.now_local()
    return ensure_dir(ZSXQ_FLOMO_RUNS_ROOT / dt.strftime("%Y-%m-%d") / run_id)


def zsxq_profile_candidates(session: str | None) -> list[Path]:
    candidates: list[Path] = []
    env_path = str(os.getenv("AI_DA_GUAN_JIA_ZSXQ_PROFILE_DIR", "")).strip()
    if env_path:
        candidates.append(Path(env_path).expanduser().resolve())
    if session:
        session_dir = SKILL_DIR / "state" / "zsxq-browser" / normalize_slug_part(session)
        if session_dir.exists():
            candidates.append(session_dir.resolve())
    if DEFAULT_CHROME_USER_DATA_DIR.exists():
        candidates.append(DEFAULT_CHROME_USER_DATA_DIR.resolve())
    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def profile_needs_shadow_copy(profile_dir: Path) -> bool:
    if profile_dir == DEFAULT_CHROME_USER_DATA_DIR:
        return True
    return any((profile_dir / name).exists() for name in ["SingletonLock", "SingletonSocket", "SingletonCookie"])


def prepare_browser_launch_dir(profile_dir: Path) -> tuple[Path, Path | None]:
    if not profile_needs_shadow_copy(profile_dir):
        return profile_dir, None
    cleanup_root = Path(tempfile.mkdtemp(prefix="adagj-zsxq-profile-"))
    launch_dir = cleanup_root / profile_dir.name
    shutil.copytree(
        profile_dir,
        launch_dir,
        symlinks=True,
        ignore=shutil.ignore_patterns("SingletonLock", "SingletonSocket", "SingletonCookie", "RunningChromeVersion"),
    )
    return launch_dir, cleanup_root


def launch_browser_context(playwright: Any, profile_dir: Path, *, headless: bool) -> Any:
    kwargs: dict[str, Any] = {
        "user_data_dir": str(profile_dir),
        "headless": headless,
        "viewport": {"width": 1440, "height": 960},
    }
    chrome_binary = Path(CHROME_PATH)
    if chrome_binary.exists():
        kwargs["executable_path"] = str(chrome_binary)
    return playwright.chromium.launch_persistent_context(**kwargs)


def extract_group_id(group_url: str) -> str:
    match = re.search(r"/group/([^/?#]+)", str(group_url or ""))
    return str(match.group(1) if match else "").strip()


def extract_timestamp(text: str) -> str:
    source = str(text or "")
    patterns = [
        r"(20\d{2}[/-]\d{1,2}[/-]\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?)",
        r"(20\d{2}[/-]\d{1,2}[/-]\d{1,2})",
        r"(20\d{2}年\d{1,2}月\d{1,2}日(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, source)
        if not match:
            continue
        candidate = match.group(1).replace("年", "-").replace("月", "-").replace("日", "")
        return canonical_timestamp(candidate)
    return ""


def first_nonempty(*values: str) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def looks_like_entry_href(href: str, group_id: str) -> bool:
    target = str(href or "").strip()
    if not target or "zsxq.com" not in target:
        return False
    if any(snippet in target for snippet in ["support.zsxq.com", "doc.zsxq.com", "about:blank", "javascript:"]):
        return False
    if any(snippet in target for snippet in ["topic_detail", "/topic/", "/post/", "/posts/", "/article/", "/column/"]):
        return True
    if group_id and f"/group/{group_id}" in target and ("topic" in target or "detail" in target or "post" in target):
        return True
    return False


def extract_candidate_links(page: Any, group_url: str, column_name: str) -> list[dict[str, Any]]:
    raw = page.evaluate(
        """
        () => Array.from(document.querySelectorAll('a[href]'))
          .map((node, index) => {
            const href = node.href || node.getAttribute('href') || '';
            const title =
              (node.innerText || node.textContent || node.getAttribute('title') || '').replace(/\\s+/g, ' ').trim();
            const container = node.closest('article, li, section, div') || node.parentElement || node;
            const contextText = (container?.innerText || '').replace(/\\s+/g, ' ').trim();
            return { href, title, context_text: contextText, index };
          })
          .filter(Boolean)
        """
    )
    group_id = extract_group_id(group_url)
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    for item in raw or []:
        href = str(item.get("href") or "").strip()
        if not href or href in seen or not looks_like_entry_href(href, group_id):
            continue
        title = first_nonempty(str(item.get("title") or ""), str(item.get("context_text") or "")[:80])
        context_text = str(item.get("context_text") or "").strip()
        normalized_context = normalize_prompt(context_text)
        if normalize_prompt(title) == normalize_prompt(column_name):
            continue
        if len(context_text) < 24 and column_name.lower() not in normalized_context:
            continue
        seen.add(href)
        items.append(
            {
                "detail_url": href,
                "title": truncate(title, 80),
                "context_text": context_text,
                "published_at": extract_timestamp(context_text),
                "ordinal": int(item.get("index") or len(items)),
            }
        )
    return items


def try_open_column(page: Any, column_name: str) -> bool:
    selectors = [
        f"a:has-text('{column_name}')",
        f"button:has-text('{column_name}')",
        f"[role='tab']:has-text('{column_name}')",
        f"text={column_name}",
    ]
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() and locator.is_visible():
                locator.click()
                page.wait_for_timeout(1500)
                return True
        except Exception:
            continue
    return False


def detail_text_blocks(page: Any) -> list[str]:
    blocks = page.evaluate(
        """
        () => {
          const selectors = ['main article', 'article', '[role="main"]', 'main', '.topic-detail', '.post-detail'];
          const nodes = [];
          for (const selector of selectors) {
            for (const node of document.querySelectorAll(selector)) {
              if (!nodes.includes(node)) nodes.push(node);
            }
          }
          if (!nodes.length) nodes.push(document.body);
          return nodes
            .map((node) => (node?.innerText || '').replace(/\\n{3,}/g, '\\n\\n').trim())
            .filter((text) => text && text.length >= 40)
            .sort((a, b) => b.length - a.length)
            .slice(0, 5);
        }
        """
    )
    return [str(item).strip() for item in blocks or [] if str(item).strip()]


def clean_detail_body(text: str, title: str, column_name: str) -> str:
    body = str(text or "").strip()
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    filtered: list[str] = []
    seen: set[str] = set()
    skip_prefixes = [normalize_prompt(title), normalize_prompt(column_name), "知识星球", "zsxq"]
    for line in lines:
        lowered = normalize_prompt(line)
        if lowered in seen:
            continue
        seen.add(lowered)
        if any(lowered == prefix for prefix in skip_prefixes if prefix):
            continue
        if lowered in {"首页", "消息", "我的", "圈子", "星球"}:
            continue
        filtered.append(line)
    return "\n".join(filtered).strip()


def extract_entry_id(detail_url: str, body_text: str, title: str, published_at: str) -> str:
    patterns = [
        r"topic_detail/([^/?#]+)",
        r"/topic/([^/?#]+)",
        r"/post/([^/?#]+)",
        r"/posts/([^/?#]+)",
        r"/article/([^/?#]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, str(detail_url or ""))
        if match:
            return str(match.group(1)).strip()
    return stable_hash(title, published_at, body_text)


def scroll_for_more(page: Any) -> None:
    page.evaluate("window.scrollBy(0, Math.max(window.innerHeight, 900));")
    page.wait_for_timeout(1200)


def hydrate_entry(context: Any, candidate: dict[str, Any], column_name: str) -> dict[str, Any]:
    page = context.new_page()
    try:
        page.goto(candidate["detail_url"], wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1200)
        body_text = safe_body_text(page)
        if login_like_content(body_text):
            return {
                "status": "blocked_needs_user",
                "blocked_reason": "知识星球浏览器会话需要重新登录。",
                "entry": {},
            }
        if preview_gate_like_content(body_text):
            return {
                "status": "blocked_needs_user",
                "blocked_reason": "当前知识星球页面只返回公开预览，需用已加入或星主账号登录后才能读取全文。",
                "entry": {},
            }
        blocks = detail_text_blocks(page)
        selected = first_nonempty(*(clean_detail_body(block, candidate["title"], column_name) for block in blocks), body_text)
        title = candidate["title"]
        try:
            heading = str(page.locator("h1").first.inner_text(timeout=1500) or "").strip()
            if heading:
                title = heading
        except Exception:
            pass
        published_at = extract_timestamp(selected) or candidate.get("published_at", "")
        detail_url = str(page.url or candidate["detail_url"]).strip()
        entry_id = extract_entry_id(detail_url, selected, title, published_at)
        entry = {
            "entry_id": entry_id,
            "title": truncate(title or f"原力养龙虾 {entry_id}", 120),
            "published_at": published_at,
            "post_url": detail_url,
            "body_text": selected.strip(),
            "content_hash": stable_hash(title, selected),
            "source_key": detail_url or entry_id,
            "ordinal": int(candidate.get("ordinal") or 0),
        }
        return {"status": "ready", "blocked_reason": "", "entry": entry}
    except Exception as exc:
        return {
            "status": "blocked_system",
            "blocked_reason": f"知识星球详情提取失败: {exc}",
            "entry": {},
        }
    finally:
        page.close()


def sort_entries_oldest_first(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(item: dict[str, Any]) -> tuple[int, str, int]:
        parsed = parse_datetime(str(item.get("published_at") or ""))
        if parsed is not None:
            return (0, parsed.isoformat(), int(item.get("ordinal") or 0))
        return (1, "", -int(item.get("ordinal") or 0))

    return sorted(entries, key=sort_key)


def render_scan_markdown(scan: dict[str, Any]) -> str:
    lines = [
        "# ZSXQ Column Scan",
        "",
        f"- `run_id`: `{scan.get('run_id', '')}`",
        f"- `status`: `{scan.get('status', '')}`",
        f"- `group_url`: `{scan.get('group_url', '')}`",
        f"- `column_name`: `{scan.get('column_name', '')}`",
        f"- `entry_count`: {len(scan.get('entries', []))}",
        f"- `screenshot_path`: `{scan.get('screenshot_path', '') or 'none'}`",
        "",
    ]
    blocked_reason = str(scan.get("blocked_reason") or "").strip()
    if blocked_reason:
        lines.extend(["## Blocked reason", "", blocked_reason, ""])
    if scan.get("entries"):
        lines.extend(["## Entries", ""])
        for item in scan["entries"]:
            lines.append(
                f"- `{item.get('published_at', '') or 'unknown'}` {item.get('title', '')} -> `{item.get('post_url', '') or item.get('source_key', '')}`"
            )
        lines.append("")
    return "\n".join(lines)


def scan_zsxq_column(
    *,
    group_url: str,
    column_name: str,
    run_id: str,
    run_dir: Path,
    limit: int,
    headless: bool,
    session: str | None,
) -> dict[str, Any]:
    if not module_available("playwright"):
        return {
            "run_id": run_id,
            "status": "blocked_system",
            "blocked_reason": "python module playwright is not installed",
            "group_url": group_url,
            "column_name": column_name,
            "entries": [],
            "screenshot_path": "",
            "attempts": [],
            "session": session or "",
        }
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover
        return {
            "run_id": run_id,
            "status": "blocked_system",
            "blocked_reason": f"failed to import playwright: {exc}",
            "group_url": group_url,
            "column_name": column_name,
            "entries": [],
            "screenshot_path": "",
            "attempts": [],
            "session": session or "",
        }

    profile_candidates = zsxq_profile_candidates(session)
    if not profile_candidates:
        return {
            "run_id": run_id,
            "status": "blocked_system",
            "blocked_reason": "No ZSXQ browser profile candidates were found.",
            "group_url": group_url,
            "column_name": column_name,
            "entries": [],
            "screenshot_path": "",
            "attempts": [],
            "session": session or "",
        }

    screenshot_path = run_dir / f"zsxq-column-{normalize_slug_part(column_name)}.png"
    attempts: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        for profile_dir in profile_candidates:
            cleanup_root: Path | None = None
            try:
                launch_dir, cleanup_root = prepare_browser_launch_dir(profile_dir)
                context = launch_browser_context(playwright, launch_dir, headless=headless)
            except Exception as exc:
                attempts.append(
                    {
                        "profile_dir": str(profile_dir),
                        "status": "blocked_system",
                        "blocked_reason": f"failed to launch browser context: {exc}",
                    }
                )
                if cleanup_root and cleanup_root.exists():
                    shutil.rmtree(cleanup_root, ignore_errors=True)
                continue

            try:
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(group_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(1500)
                body_text = safe_body_text(page)
                if login_like_content(body_text):
                    attempts.append(
                        {
                            "profile_dir": str(profile_dir),
                            "status": "blocked_needs_user",
                            "blocked_reason": "知识星球浏览器会话需要重新登录。",
                        }
                    )
                    continue
                if preview_gate_like_content(body_text):
                    attempts.append(
                        {
                            "profile_dir": str(profile_dir),
                            "status": "blocked_needs_user",
                            "blocked_reason": "当前知识星球页面只返回公开预览，需用已加入或星主账号登录后才能读取全文。",
                        }
                    )
                    continue
                if not try_open_column(page, column_name):
                    attempts.append(
                        {
                            "profile_dir": str(profile_dir),
                            "status": "blocked_system",
                            "blocked_reason": f"未找到栏目“{column_name}”的可点击入口。",
                        }
                    )
                    continue

                seen_links: set[str] = set()
                candidates: list[dict[str, Any]] = []
                stagnant_rounds = 0
                scroll_rounds = 0
                while scroll_rounds < 25:
                    fresh = extract_candidate_links(page, group_url, column_name)
                    new_count = 0
                    for item in fresh:
                        key = str(item.get("detail_url") or "")
                        if not key or key in seen_links:
                            continue
                        seen_links.add(key)
                        item["ordinal"] = len(candidates)
                        candidates.append(item)
                        new_count += 1
                    if limit > 0 and len(candidates) >= limit:
                        break
                    if new_count == 0:
                        stagnant_rounds += 1
                    else:
                        stagnant_rounds = 0
                    if stagnant_rounds >= 3:
                        break
                    scroll_for_more(page)
                    scroll_rounds += 1

                page.screenshot(path=str(screenshot_path), full_page=True)

                if not candidates:
                    attempts.append(
                        {
                            "profile_dir": str(profile_dir),
                            "status": "blocked_system",
                            "blocked_reason": f"打开栏目“{column_name}”后没有发现可抽取的条目链接。",
                        }
                    )
                    continue

                hydrated: list[dict[str, Any]] = []
                first_blocked: dict[str, Any] | None = None
                for candidate in candidates:
                    detail = hydrate_entry(context, candidate, column_name)
                    if detail["status"] != "ready":
                        first_blocked = first_blocked or detail
                        continue
                    entry = detail["entry"]
                    if not str(entry.get("body_text") or "").strip():
                        continue
                    hydrated.append(entry)
                    if limit > 0 and len(hydrated) >= limit:
                        break

                if not hydrated:
                    status = first_blocked["status"] if first_blocked else "blocked_system"
                    blocked_reason = first_blocked["blocked_reason"] if first_blocked else "未能提取任何栏目正文。"
                    attempts.append(
                        {
                            "profile_dir": str(profile_dir),
                            "status": status,
                            "blocked_reason": blocked_reason,
                        }
                    )
                    continue

                entries = sort_entries_oldest_first(hydrated)
                if limit > 0:
                    entries = entries[:limit]
                return {
                    "run_id": run_id,
                    "status": "ready",
                    "blocked_reason": "",
                    "group_url": group_url,
                    "column_name": column_name,
                    "entries": entries,
                    "screenshot_path": str(screenshot_path.resolve()),
                    "attempts": attempts,
                    "session": session or "",
                }
            finally:
                context.close()
                if cleanup_root and cleanup_root.exists():
                    shutil.rmtree(cleanup_root, ignore_errors=True)

    final_status = "blocked_system"
    blocked_reason = "知识星球栏目抓取失败。"
    if attempts:
        if any(item.get("status") == "blocked_needs_user" for item in attempts):
            final_status = "blocked_needs_user"
        blocked_reason = str(attempts[-1].get("blocked_reason") or blocked_reason)
    return {
        "run_id": run_id,
        "status": final_status,
        "blocked_reason": blocked_reason,
        "group_url": group_url,
        "column_name": column_name,
        "entries": [],
        "screenshot_path": str(screenshot_path.resolve()) if screenshot_path.exists() else "",
        "attempts": attempts,
        "session": session or "",
    }


def flomo_tag_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "status": {"type": "string", "enum": ["ready", "blocked_needs_user", "blocked_system"]},
            "blocked_reason": {"type": "string"},
            "memos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "string"},
                        "content": {"type": "string"},
                        "updated_at": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["id", "content", "updated_at", "tags"],
                },
            },
        },
        "required": ["status", "blocked_reason", "memos"],
    }


def build_flomo_tag_prompt(tag: str, limit: int) -> str:
    clean_tag = normalize_tag(tag).lstrip("#")
    return f"""
Use the flomo MCP server only. Do not use shell commands or web browsing.

Task:
- Read recent memos under tag `{clean_tag}`.
- Prefer the tag memos resource first. Fall back to memo search only if needed.
- Return at most {limit} memos.
- Return only `id`, `content`, `updated_at`, and `tags`.
- If the MCP tool is not authenticated or needs user authorization, return `status = "blocked_needs_user"`.
- If the MCP tool fails for another reason, return `status = "blocked_system"`.
- If the tag exists but has no memos, return `status = "ready"` and `memos = []`.
""".strip()


def build_flomo_tag_fallback_prompt(tag: str, limit: int) -> str:
    clean_tag = normalize_tag(tag).lstrip("#")
    return f"""
Use the flomo MCP server only. Do not use shell commands or web browsing.

Task:
- Read recent memos under tag `{clean_tag}`.
- Return at most {limit} memos.
- Return only `id`, `content`, `updated_at`, and `tags`.
- If authentication is missing, return `status = "blocked_needs_user"`.
- If the server fails for another reason, return `status = "blocked_system"`.

Return one compact JSON object only:
{{
  "status": "ready|blocked_needs_user|blocked_system",
  "blocked_reason": "",
  "memos": [
    {{
      "id": "...",
      "content": "...",
      "updated_at": "...",
      "tags": ["..."]
    }}
  ]
}}
""".strip()


def normalize_flomo_tag_payload(
    payload: dict[str, Any],
    *,
    mcp_state: dict[str, Any],
    exec_result: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "status": "blocked_system",
            "blocked_reason": "flomo MCP result was not a JSON object.",
            "memos": [],
            "mcp_state": mcp_state,
            "exec_result": exec_result,
        }
    normalized_memos: list[dict[str, Any]] = []
    for item in payload.get("memos", []):
        if not isinstance(item, dict):
            continue
        normalized_memos.append(
            {
                "id": str(item.get("id") or "").strip(),
                "content": str(item.get("content") or "").strip(),
                "updated_at": canonical_timestamp(str(item.get("updated_at") or "").strip()),
                "tags": normalized_tags(item.get("tags")),
            }
        )
    payload["memos"] = [memo for memo in normalized_memos if memo["id"] and memo["content"]]
    payload["mcp_state"] = mcp_state
    payload["exec_result"] = exec_result
    payload["setup_hint"] = flomo_setup_hint()
    return payload


def read_flomo_tag_memos(tag: str, limit: int = DEFAULT_EXISTING_MEMO_LIMIT) -> dict[str, Any]:
    mcp_state = read_mcp_config(FLOMO_MCP_SERVER_NAME)
    if not mcp_state.get("configured"):
        return {
            "status": "blocked_needs_user",
            "blocked_reason": "flomo MCP server is not configured in Codex.",
            "memos": [],
            "mcp_state": mcp_state,
            "setup_hint": flomo_setup_hint(),
        }
    if not mcp_state.get("enabled", False):
        return {
            "status": "blocked_needs_user",
            "blocked_reason": "flomo MCP server exists but is disabled.",
            "memos": [],
            "mcp_state": mcp_state,
            "setup_hint": flomo_setup_hint(),
        }
    result = run_codex_exec_json(build_flomo_tag_prompt(tag, limit), flomo_tag_schema())
    if int(result.get("returncode", 1)) != 0:
        fallback = run_codex_exec_last_message(build_flomo_tag_fallback_prompt(tag, limit))
        if int(fallback.get("returncode", 1)) == 0 and isinstance(fallback.get("json"), dict):
            return normalize_flomo_tag_payload(
                dict(fallback["json"]),
                mcp_state=mcp_state,
                exec_result={
                    "mode": "last_message_fallback",
                    "returncode": fallback.get("returncode", 0),
                    "stdout": fallback.get("stdout", ""),
                    "stderr": fallback.get("stderr", ""),
                },
            )
        reason = str(
            fallback.get("stderr")
            or fallback.get("stdout")
            or fallback.get("json_error")
            or result.get("stderr")
            or result.get("stdout")
            or "codex exec failed"
        ).strip()
        status = "blocked_needs_user" if "oauth" in reason.lower() or "login" in reason.lower() else "blocked_system"
        return {
            "status": status,
            "blocked_reason": reason,
            "memos": [],
            "mcp_state": mcp_state,
            "setup_hint": flomo_setup_hint(),
        }
    return normalize_flomo_tag_payload(
        dict(result.get("json", {})),
        mcp_state=mcp_state,
        exec_result={
            "mode": "output_schema",
            "returncode": result.get("returncode", 0),
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
        },
    )


def flomo_write_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "status": {"type": "string", "enum": ["created", "updated", "blocked_needs_user", "blocked_system"]},
            "blocked_reason": {"type": "string"},
            "memo_id": {"type": "string"},
        },
        "required": ["status", "blocked_reason", "memo_id"],
    }


def build_flomo_write_prompt(content: str, *, memo_id: str = "") -> str:
    action = "update the existing memo" if memo_id else "create a new memo"
    memo_hint = f"- Target memo id: `{memo_id}`." if memo_id else "- There is no existing memo id. Create a new memo."
    return f"""
Use the flomo MCP server only. Do not use shell commands or web browsing.

Task:
- {action} with the exact content between START CONTENT and END CONTENT.
- Use `format = "markdown"`.
{memo_hint}
- If authentication is missing, return `status = "blocked_needs_user"`.
- If the server fails for another reason, return `status = "blocked_system"`.
- Otherwise return `status = "created"` or `status = "updated"` and the memo id.

START CONTENT
{content}
END CONTENT
""".strip()


def build_flomo_write_fallback_prompt(content: str, *, memo_id: str = "") -> str:
    action = "update the memo" if memo_id else "create the memo"
    memo_hint = f"using memo id `{memo_id}`" if memo_id else "as a new memo"
    return f"""
Use the flomo MCP server only. Do not use shell commands or web browsing.

Task:
- {action} {memo_hint} with the exact content below.
- Use markdown format.
- Return one compact JSON object only.

START CONTENT
{content}
END CONTENT

{{
  "status": "created|updated|blocked_needs_user|blocked_system",
  "blocked_reason": "",
  "memo_id": "..."
}}
""".strip()


def write_flomo_memo(content: str, *, memo_id: str = "") -> dict[str, Any]:
    mcp_state = read_mcp_config(FLOMO_MCP_SERVER_NAME)
    if not mcp_state.get("configured"):
        return {
            "status": "blocked_needs_user",
            "blocked_reason": "flomo MCP server is not configured in Codex.",
            "memo_id": memo_id,
            "mcp_state": mcp_state,
            "setup_hint": flomo_setup_hint(),
        }
    if not mcp_state.get("enabled", False):
        return {
            "status": "blocked_needs_user",
            "blocked_reason": "flomo MCP server exists but is disabled.",
            "memo_id": memo_id,
            "mcp_state": mcp_state,
            "setup_hint": flomo_setup_hint(),
        }
    result = run_codex_exec_json(build_flomo_write_prompt(content, memo_id=memo_id), flomo_write_schema())
    if int(result.get("returncode", 1)) != 0:
        fallback = run_codex_exec_last_message(build_flomo_write_fallback_prompt(content, memo_id=memo_id))
        if int(fallback.get("returncode", 1)) == 0 and isinstance(fallback.get("json"), dict):
            payload = dict(fallback["json"])
            payload["setup_hint"] = flomo_setup_hint()
            payload["mcp_state"] = mcp_state
            return payload
        reason = str(
            fallback.get("stderr")
            or fallback.get("stdout")
            or fallback.get("json_error")
            or result.get("stderr")
            or result.get("stdout")
            or "codex exec failed"
        ).strip()
        status = "blocked_needs_user" if "oauth" in reason.lower() or "login" in reason.lower() else "blocked_system"
        return {
            "status": status,
            "blocked_reason": reason,
            "memo_id": memo_id,
            "mcp_state": mcp_state,
            "setup_hint": flomo_setup_hint(),
        }
    payload = dict(result.get("json", {}))
    payload["setup_hint"] = flomo_setup_hint()
    payload["mcp_state"] = mcp_state
    return payload


def extract_source_url_from_content(content: str) -> str:
    match = re.search(r"原文[:：]\s*(https?://\S+)", str(content or ""))
    return str(match.group(1) if match else "").strip()


def strip_tags_and_source(content: str) -> str:
    lines = []
    for line in str(content or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("原文：") or stripped.startswith("原文:"):
            continue
        lines.append(stripped)
    return "\n".join(lines).strip()


def split_memo_title_body(content: str) -> tuple[str, str]:
    cleaned = strip_tags_and_source(content)
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if not lines:
        return "", ""
    title = lines[0]
    body = "\n".join(lines[1:]).strip()
    if not body:
        body = title
    return title, body


def summarize_text_signature(title: str, body: str) -> dict[str, str]:
    normalized_body = re.sub(r"\s+", " ", str(body or "").strip())
    normalized_title = re.sub(r"\s+", " ", str(title or "").strip())
    prefix = normalized_body[:160]
    return {
        "normalized_title": normalize_prompt(normalized_title),
        "normalized_body_prefix": normalize_prompt(prefix),
        "signature": stable_hash(normalized_title, prefix),
    }


def annotate_existing_memos(memos: list[dict[str, Any]], source_tag: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for memo in memos:
        content = str(memo.get("content") or "")
        title, body = split_memo_title_body(content)
        signature = summarize_text_signature(title, body)
        rows.append(
            {
                **memo,
                "source_url": extract_source_url_from_content(content),
                "managed": bool(extract_source_url_from_content(content) and memo_has_tag(memo, source_tag)),
                "body_without_tags": body,
                "content_hash": stable_hash(title, body),
                **signature,
            }
        )
    return rows


def build_existing_memo_indexes(memos: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_source_url: dict[str, dict[str, Any]] = {}
    by_signature: dict[str, dict[str, Any]] = {}
    for memo in memos:
        source_url = str(memo.get("source_url") or "").strip()
        if source_url and source_url not in by_source_url:
            by_source_url[source_url] = memo
        signature = str(memo.get("signature") or "").strip()
        if signature and signature not in by_signature:
            by_signature[signature] = memo
    return {"by_source_url": by_source_url, "by_signature": by_signature}


def load_entry_ledger() -> dict[str, Any]:
    payload = load_optional_json(ZSXQ_FLOMO_ENTRY_LEDGER_PATH)
    if not isinstance(payload.get("entries"), list):
        payload["entries"] = []
    return payload


def ledger_by_source_key(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for item in ledger.get("entries", []):
        if not isinstance(item, dict):
            continue
        source_key = str(item.get("source_key") or "").strip()
        if source_key:
            rows[source_key] = item
    return rows


def save_entry_ledger(ledger: dict[str, Any]) -> None:
    ledger["updated_at"] = iso_now()
    ledger["entries"] = sorted(
        [item for item in ledger.get("entries", []) if isinstance(item, dict)],
        key=lambda item: (str(item.get("published_at") or ""), str(item.get("title") or "")),
    )
    write_json(ZSXQ_FLOMO_ENTRY_LEDGER_PATH, ledger)


def build_source_key(entry: dict[str, Any]) -> str:
    return str(entry.get("post_url") or entry.get("entry_id") or stable_hash(entry.get("title", ""), entry.get("body_text", ""))).strip()


def build_flomo_content(entry: dict[str, Any], tag: str, source_tag: str) -> str:
    title = str(entry.get("title") or "").strip()
    body = str(entry.get("body_text") or "").strip()
    post_url = str(entry.get("post_url") or "").strip()
    parts: list[str] = []
    if title:
        parts.append(title)
    if body:
        if not title or normalize_prompt(body.splitlines()[0]) != normalize_prompt(title):
            parts.extend(["", body])
        elif len(body.splitlines()) > 1:
            parts.extend(["", "\n".join(body.splitlines()[1:]).strip()])
    if post_url:
        parts.extend(["", f"原文：{post_url}"])
    parts.extend(["", f"{normalize_tag(tag)} {normalize_tag(source_tag)}"])
    return "\n".join(part for part in parts if part is not None).strip() + "\n"


def resolve_target_memo(
    entry: dict[str, Any],
    ledger_entry: dict[str, Any] | None,
    existing_indexes: dict[str, dict[str, Any]],
    existing_memos: list[dict[str, Any]],
) -> tuple[str, str, dict[str, Any] | None, dict[str, Any] | None]:
    post_url = str(entry.get("post_url") or "").strip()
    signature = str(entry.get("signature") or "").strip()
    if ledger_entry:
        memo_id = str(ledger_entry.get("flomo_memo_id") or "").strip()
        if memo_id:
            return memo_id, "ledger", None, None
    if post_url and post_url in existing_indexes["by_source_url"]:
        target = existing_indexes["by_source_url"][post_url]
        if target.get("managed"):
            return str(target.get("id") or "").strip(), "existing_source_url", None, target
    if signature and signature in existing_indexes["by_signature"]:
        conflict = existing_indexes["by_signature"][signature]
        if conflict.get("managed"):
            return str(conflict.get("id") or "").strip(), "existing_signature", None, conflict
        return "", "needs_review_signature", conflict, None
    for memo in existing_memos:
        if memo.get("managed"):
            continue
        if str(memo.get("normalized_title") or "") and memo.get("normalized_title") == entry.get("normalized_title"):
            if str(memo.get("normalized_body_prefix") or "") == entry.get("normalized_body_prefix"):
                return "", "needs_review_manual", memo, None
    return "", "new", None, None


def build_import_plan(
    entries: list[dict[str, Any]],
    ledger: dict[str, Any],
    existing_memos: list[dict[str, Any]],
    *,
    tag: str,
    source_tag: str,
) -> dict[str, Any]:
    annotated = annotate_existing_memos(existing_memos, source_tag)
    indexes = build_existing_memo_indexes(annotated)
    ledger_index = ledger_by_source_key(ledger)
    actions: list[dict[str, Any]] = []
    counts = {"create": 0, "update": 0, "skip": 0, "needs_review": 0}

    for source_entry in sort_entries_oldest_first(entries):
        entry = dict(source_entry)
        entry["source_key"] = build_source_key(entry)
        entry["signature"] = summarize_text_signature(entry.get("title", ""), entry.get("body_text", "")).get("signature", "")
        entry["normalized_title"] = summarize_text_signature(entry.get("title", ""), entry.get("body_text", "")).get("normalized_title", "")
        entry["normalized_body_prefix"] = summarize_text_signature(entry.get("title", ""), entry.get("body_text", "")).get("normalized_body_prefix", "")
        entry["flomo_content"] = build_flomo_content(entry, tag, source_tag)
        ledger_entry = ledger_index.get(entry["source_key"])
        memo_id, target_source, conflict, target_memo = resolve_target_memo(entry, ledger_entry, indexes, annotated)
        previous_hash = str(ledger_entry.get("content_hash") or "") if ledger_entry else ""
        action = "create"
        reason = "New ZSXQ column entry is not present in the local ledger or managed flomo memos."
        if conflict is not None:
            action = "needs_review"
            reason = "A similar #星球精选 memo exists without a stable origin marker, so this entry needs manual review."
        elif memo_id:
            managed_hash = str(target_memo.get("content_hash") or "") if target_memo else ""
            if (previous_hash and previous_hash == entry["content_hash"]) or (not previous_hash and managed_hash == entry["content_hash"]):
                action = "skip"
                reason = "Local ledger already tracks the same content hash."
            else:
                action = "update"
                reason = f"Managed flomo memo found via {target_source}; content hash changed."
        counts[action] += 1
        actions.append(
            {
                "action": action,
                "reason": reason,
                "target_memo_id": memo_id,
                "conflict_memo_id": str(conflict.get("id") or "").strip() if conflict else "",
                "source_key": entry["source_key"],
                "entry_id": str(entry.get("entry_id") or ""),
                "title": str(entry.get("title") or ""),
                "published_at": str(entry.get("published_at") or ""),
                "post_url": str(entry.get("post_url") or ""),
                "content_hash": str(entry.get("content_hash") or ""),
                "flomo_content": entry["flomo_content"],
            }
        )
    return {"actions": actions, "counts": counts}


def render_import_preview(preview: dict[str, Any]) -> str:
    counts = preview.get("counts", {})
    lines = [
        "# ZSXQ -> flomo Import Preview",
        "",
        f"- `run_id`: `{preview.get('run_id', '')}`",
        f"- `apply`: `{preview.get('apply', False)}`",
        f"- `tag`: `{preview.get('tag', '')}`",
        f"- `source_tag`: `{preview.get('source_tag', '')}`",
        f"- `entries`: {preview.get('entry_count', 0)}",
        f"- `create`: {counts.get('create', 0)}",
        f"- `update`: {counts.get('update', 0)}",
        f"- `skip`: {counts.get('skip', 0)}",
        f"- `needs_review`: {counts.get('needs_review', 0)}",
        "",
    ]
    if preview.get("actions"):
        lines.extend(["## Actions", ""])
        for item in preview["actions"]:
            title = truncate(str(item.get("title") or item.get("source_key") or ""), 48)
            lines.append(f"- `{item.get('action', '')}` {title} -> {item.get('reason', '')}")
        lines.append("")
    return "\n".join(lines)


def apply_import_plan(actions: list[dict[str, Any]], *, apply: bool) -> dict[str, Any]:
    writes: list[dict[str, Any]] = []
    created = 0
    updated = 0
    skipped = 0
    needs_review = 0
    status = "preview_ready"
    blocked_reason = ""

    for item in actions:
        action = str(item.get("action") or "")
        if action == "skip":
            skipped += 1
            writes.append({**item, "write_status": "skipped", "memo_id": str(item.get("target_memo_id") or "")})
            continue
        if action == "needs_review":
            needs_review += 1
            writes.append({**item, "write_status": "needs_review", "memo_id": str(item.get("conflict_memo_id") or "")})
            continue
        if not apply:
            writes.append({**item, "write_status": "planned", "memo_id": str(item.get("target_memo_id") or "")})
            continue
        result = write_flomo_memo(str(item.get("flomo_content") or ""), memo_id=str(item.get("target_memo_id") or ""))
        write_status = str(result.get("status") or "")
        memo_id = str(result.get("memo_id") or item.get("target_memo_id") or "").strip()
        writes.append({**item, "write_status": write_status, "memo_id": memo_id, "write_result": result})
        if write_status == "created":
            created += 1
        elif write_status == "updated":
            updated += 1
        elif write_status == "blocked_needs_user":
            status = "blocked_needs_user"
            blocked_reason = str(result.get("blocked_reason") or "").strip()
        else:
            status = "blocked_system"
            blocked_reason = str(result.get("blocked_reason") or "").strip()
    if apply and status == "preview_ready":
        status = "applied"
    return {
        "status": status,
        "blocked_reason": blocked_reason,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "needs_review": needs_review,
        "writes": writes,
    }


def update_ledger_after_writes(
    ledger: dict[str, Any],
    writes: list[dict[str, Any]],
    *,
    run_id: str,
    run_dir: Path,
) -> dict[str, Any]:
    ledger_index = ledger_by_source_key(ledger)
    for item in writes:
        status = str(item.get("write_status") or "")
        if status not in {"created", "updated", "skipped"}:
            continue
        source_key = str(item.get("source_key") or "")
        entry = ledger_index.get(source_key) or {"source_key": source_key, "run_ids": []}
        entry["entry_id"] = str(item.get("entry_id") or "")
        entry["title"] = str(item.get("title") or "")
        entry["published_at"] = str(item.get("published_at") or "")
        entry["post_url"] = str(item.get("post_url") or "")
        entry["content_hash"] = str(item.get("content_hash") or "")
        entry["flomo_memo_id"] = str(item.get("memo_id") or entry.get("flomo_memo_id") or "")
        entry["latest_run_id"] = run_id
        entry["latest_run_dir"] = str(run_dir.resolve())
        entry["last_write_status"] = status
        entry["run_ids"] = normalize_list([*normalize_list(entry.get("run_ids")), run_id])
        ledger_index[source_key] = entry
    ledger["entries"] = list(ledger_index.values())
    return ledger


def status_exit_code(status: str) -> int:
    if status == "blocked_needs_user":
        return 1
    if status == "blocked_system":
        return 2
    return 0


def command_zsxq_flomo_sync(args: argparse.Namespace) -> int:
    created_at = iso_now()
    run_id = str(getattr(args, "run_id", "") or zsxq_run_id(created_at))
    group_url = str(getattr(args, "group_url", "") or "").strip()
    column_name = str(getattr(args, "column_name", "") or "").strip()
    tag = normalize_tag(str(getattr(args, "tag", DEFAULT_TAG) or DEFAULT_TAG))
    source_tag = normalize_tag(str(getattr(args, "source_tag", DEFAULT_SOURCE_TAG) or DEFAULT_SOURCE_TAG))
    limit = int(getattr(args, "limit", 0) or 0)
    session = str(getattr(args, "session", "") or "").strip() or None
    headless = bool(getattr(args, "headless", False))
    apply = bool(getattr(args, "apply", False))

    if not group_url:
        raise ValueError("--group-url is required")
    if not column_name:
        raise ValueError("--column-name is required")

    ensure_dir(ZSXQ_FLOMO_CURRENT_ROOT)
    run_dir = run_dir_for(run_id, created_at)
    ledger = load_entry_ledger()
    save_entry_ledger(ledger)
    scan = scan_zsxq_column(
        group_url=group_url,
        column_name=column_name,
        run_id=run_id,
        run_dir=run_dir,
        limit=limit,
        headless=headless,
        session=session,
    )
    write_json(run_dir / "zsxq-scan.json", scan)
    (run_dir / "zsxq-scan.md").write_text(render_scan_markdown(scan) + "\n", encoding="utf-8")
    write_json(ZSXQ_FLOMO_LATEST_SCAN_PATH, scan)

    checkpoint = {
        "updated_at": iso_now(),
        "run_id": run_id,
        "group_url": group_url,
        "column_name": column_name,
        "tag": tag,
        "source_tag": source_tag,
        "last_status": str(scan.get("status") or ""),
        "last_blocked_reason": str(scan.get("blocked_reason") or ""),
        "last_source_published_at": max(
            [str(item.get("published_at") or "") for item in scan.get("entries", []) if str(item.get("published_at") or "").strip()],
            default="",
        ),
        "entry_count": len(scan.get("entries", [])),
        "apply": apply,
    }
    write_json(ZSXQ_FLOMO_CHECKPOINT_PATH, checkpoint)

    if scan.get("status") != "ready":
        preview = {
            "run_id": run_id,
            "status": str(scan.get("status") or "blocked_system"),
            "blocked_reason": str(scan.get("blocked_reason") or ""),
            "apply": apply,
            "tag": tag,
            "source_tag": source_tag,
            "entry_count": len(scan.get("entries", [])),
            "counts": {"create": 0, "update": 0, "skip": 0, "needs_review": 0},
            "actions": [],
        }
        write_json(run_dir / "import-preview.json", preview)
        write_json(ZSXQ_FLOMO_IMPORT_PREVIEW_PATH, preview)
        result = {
            "run_id": run_id,
            "status": str(scan.get("status") or "blocked_system"),
            "blocked_reason": str(scan.get("blocked_reason") or ""),
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "needs_review": 0,
            "writes": [],
        }
        write_json(run_dir / "write-result.json", result)
        write_json(ZSXQ_FLOMO_WRITE_RESULT_PATH, result)
        print(f"run_id: {run_id}")
        print(f"status: {result['status']}")
        print(f"blocked_reason: {result['blocked_reason']}")
        return status_exit_code(result["status"])

    existing = read_flomo_tag_memos(tag, limit=max(DEFAULT_EXISTING_MEMO_LIMIT, len(scan.get("entries", [])) * 4 or DEFAULT_EXISTING_MEMO_LIMIT))
    write_json(run_dir / "flomo-existing.json", existing)
    if existing.get("status") != "ready":
        preview = {
            "run_id": run_id,
            "status": str(existing.get("status") or "blocked_system"),
            "blocked_reason": str(existing.get("blocked_reason") or ""),
            "apply": apply,
            "tag": tag,
            "source_tag": source_tag,
            "entry_count": len(scan.get("entries", [])),
            "counts": {"create": 0, "update": 0, "skip": 0, "needs_review": 0},
            "actions": [],
        }
        write_json(run_dir / "import-preview.json", preview)
        write_json(ZSXQ_FLOMO_IMPORT_PREVIEW_PATH, preview)
        result = {
            "run_id": run_id,
            "status": str(existing.get("status") or "blocked_system"),
            "blocked_reason": str(existing.get("blocked_reason") or ""),
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "needs_review": 0,
            "writes": [],
        }
        write_json(run_dir / "write-result.json", result)
        write_json(ZSXQ_FLOMO_WRITE_RESULT_PATH, result)
        print(f"run_id: {run_id}")
        print(f"status: {result['status']}")
        print(f"blocked_reason: {result['blocked_reason']}")
        return status_exit_code(result["status"])

    plan = build_import_plan(scan.get("entries", []), ledger, existing.get("memos", []), tag=tag, source_tag=source_tag)
    preview = {
        "run_id": run_id,
        "status": "ready",
        "blocked_reason": "",
        "apply": apply,
        "tag": tag,
        "source_tag": source_tag,
        "entry_count": len(scan.get("entries", [])),
        **plan,
    }
    write_json(run_dir / "import-preview.json", preview)
    (run_dir / "import-preview.md").write_text(render_import_preview(preview) + "\n", encoding="utf-8")
    write_json(ZSXQ_FLOMO_IMPORT_PREVIEW_PATH, preview)

    write_result = apply_import_plan(plan["actions"], apply=apply)
    if apply and write_result["status"] in {"applied", "preview_ready"}:
        ledger = update_ledger_after_writes(ledger, write_result["writes"], run_id=run_id, run_dir=run_dir)
        save_entry_ledger(ledger)
    else:
        save_entry_ledger(ledger)

    result = {
        "run_id": run_id,
        "status": write_result["status"],
        "blocked_reason": write_result["blocked_reason"],
        "apply": apply,
        "created": write_result["created"],
        "updated": write_result["updated"],
        "skipped": write_result["skipped"],
        "needs_review": write_result["needs_review"],
        "writes": write_result["writes"],
    }
    write_json(run_dir / "write-result.json", result)
    write_json(ZSXQ_FLOMO_WRITE_RESULT_PATH, result)

    checkpoint["last_status"] = result["status"]
    checkpoint["last_blocked_reason"] = result["blocked_reason"]
    checkpoint["created"] = result["created"]
    checkpoint["updated"] = result["updated"]
    checkpoint["skipped"] = result["skipped"]
    checkpoint["needs_review"] = result["needs_review"]
    write_json(ZSXQ_FLOMO_CHECKPOINT_PATH, checkpoint)

    print(f"run_id: {run_id}")
    print(f"status: {result['status']}")
    print(f"entry_count: {preview['entry_count']}")
    print(f"create: {preview['counts']['create']}")
    print(f"update: {preview['counts']['update']}")
    print(f"skip: {preview['counts']['skip']}")
    print(f"needs_review: {preview['counts']['needs_review']}")
    print(f"checkpoint_path: {ZSXQ_FLOMO_CHECKPOINT_PATH}")
    print(f"ledger_path: {ZSXQ_FLOMO_ENTRY_LEDGER_PATH}")
    print(f"preview_path: {ZSXQ_FLOMO_IMPORT_PREVIEW_PATH}")
    print(f"write_result_path: {ZSXQ_FLOMO_WRITE_RESULT_PATH}")
    return status_exit_code(result["status"])
