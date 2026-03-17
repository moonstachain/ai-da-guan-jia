#!/usr/bin/env python3
"""Dual-source story-canon refresh workflow for AI大管家."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import flomo_zsxq_workflow as flomo_helpers
import zsxq_flomo_sync_workflow as zsxq_helpers


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
ARTIFACTS_ROOT = SKILL_DIR / "artifacts" / "ai-da-guan-jia"
STORY_CANON_ROOT = ARTIFACTS_ROOT / "story-canon"
STORY_CANON_RUNS_ROOT = STORY_CANON_ROOT / "runs"
STORY_CANON_CURRENT_ROOT = STORY_CANON_ROOT / "current"
STORY_CANON_LATEST_REFRESH_PATH = STORY_CANON_CURRENT_ROOT / "latest-refresh.json"
STORY_CANON_LAST_REAUTH_PATH = STORY_CANON_CURRENT_ROOT / "last-reauth.json"
STORY_SOURCE_BUNDLE_PATH = SKILL_DIR / "story-source-bundle.json"
STORY_ARC_PLAN_PATH = SKILL_DIR / "story-arc-plan.md"
CHARACTER_CONTRACT_PATH = SKILL_DIR / "character-contract.md"
DEFAULT_FLOMO_TAG = flomo_helpers.DEFAULT_TAG
DEFAULT_ZSXQ_GROUP_URL = flomo_helpers.DEFAULT_ZSXQ_GROUP_URL
DEFAULT_ZSXQ_COLUMN = "原力养虾炼丹"
DEFAULT_PUBLISH_COLUMN = flomo_helpers.DEFAULT_COLUMN_NAME
DEFAULT_FLOMO_LIMIT = flomo_helpers.DEFAULT_BACKFILL_LIMIT
MAX_EPISODE_SEEDS = 12

CONCRETE_TASK_KEYWORDS = [
    "今天",
    "第一次",
    "开始",
    "发布",
    "修复",
    "走通",
    "验证",
    "上线",
    "同步",
    "登录",
    "授权",
    "卡住",
    "完成",
    "闭环",
    "故事",
    "空降",
    "高管",
    "二号位",
    "问题",
]
CONFLICT_KEYWORDS = [
    "难题",
    "问题",
    "卡住",
    "失败",
    "误判",
    "冲突",
    "边界",
    "失真",
    "风险",
    "阻塞",
    "拐点",
]
GROWTH_KEYWORDS = [
    "一起",
    "伙伴",
    "搭档",
    "开始",
    "终于",
    "后来",
    "现在",
    "慢慢",
    "学会",
    "发现",
    "变化",
    "进化",
]
HEAVY_KEYWORDS = [
    "系统",
    "方法论",
    "治理",
    "框架",
    "原则",
    "宪章",
    "战略",
    "模型",
    "总盘",
    "母题",
    "操作系统",
    "架构",
    "ontology",
    "cbm",
]
AUTH_HINTS = ["auth", "login", "oauth", "授权", "登录", "扫码", "请先登录", "auth required"]

ensure_dir = flomo_helpers.ensure_dir
iso_now = flomo_helpers.iso_now
write_json = flomo_helpers.write_json
load_optional_json = flomo_helpers.load_optional_json
normalize_list = flomo_helpers.normalize_list
truncate = flomo_helpers.truncate
parse_datetime = flomo_helpers.parse_datetime
canonical_timestamp = flomo_helpers.canonical_timestamp


def story_source_refresh_run_id(created_at: str) -> str:
    stamp = (parse_datetime(created_at) or datetime.now().astimezone()).strftime("%Y%m%d-%H%M%S-%f")
    return f"story-source-refresh-{stamp}"


def run_dir_for(run_id: str, created_at: str) -> Path:
    dt = parse_datetime(created_at) or datetime.now().astimezone()
    return ensure_dir(STORY_CANON_RUNS_ROOT / dt.strftime("%Y-%m-%d") / run_id)


def normalize_prompt(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def looks_like_auth_blocker(status: str, reason: str) -> bool:
    lowered_status = normalize_prompt(status)
    lowered_reason = normalize_prompt(reason)
    return "blocked_needs_user" in lowered_status or any(hint in lowered_reason for hint in AUTH_HINTS)


def derive_flomo_title(note: dict[str, Any]) -> str:
    content = str(note.get("content") or "").strip()
    if content:
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            cleaned = re.sub(r"(?<!\w)#[^\s#]+", "", line).strip(" -:：")
            if cleaned:
                return truncate(cleaned, 48)
    return flomo_helpers.clean_note_title(note)


def split_zsxq_body(title: str, body_text: str) -> str:
    body = str(body_text or "").strip()
    if not body:
        return ""
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if lines and normalize_prompt(lines[0]) == normalize_prompt(title):
        lines = lines[1:]
    return "\n".join(lines).strip()


def keyword_hits(text: str, keywords: list[str]) -> int:
    lowered = normalize_prompt(text)
    return sum(1 for keyword in keywords if keyword.lower() in lowered or keyword in text)


def classify_story_weight(title: str, body: str, source_type: str) -> tuple[str, int, list[str]]:
    combined = f"{title}\n{body}".strip()
    task_hits = keyword_hits(combined, CONCRETE_TASK_KEYWORDS)
    conflict_hits = keyword_hits(combined, CONFLICT_KEYWORDS)
    growth_hits = keyword_hits(combined, GROWTH_KEYWORDS)
    heavy_hits = keyword_hits(combined, HEAVY_KEYWORDS)
    length_flag = len(combined) >= 900 or len([line for line in combined.splitlines() if line.strip()]) >= 14
    score = task_hits * 3 + conflict_hits * 2 + growth_hits - heavy_hits
    reasons: list[str] = []
    if task_hits:
        reasons.append("contains_concrete_task_turn")
    if conflict_hits:
        reasons.append("contains_conflict_or_friction")
    if growth_hits:
        reasons.append("contains_growth_signal")
    if heavy_hits:
        reasons.append("contains_heavy_system_language")
    if length_flag:
        reasons.append("long_form_or_dense")
    if source_type == "flomo" and task_hits:
        score += 1
        reasons.append("flomo_observer_bonus")
    if task_hits >= 1 and (conflict_hits >= 1 or growth_hits >= 1) and not (heavy_hits >= 2 and not conflict_hits):
        return "episode_candidate", score, reasons
    if heavy_hits >= 2 or length_flag:
        return "reference_heavy", score, reasons or ["heavy_by_default"]
    return "supporting_reference", score, reasons or ["background_reference"]


def flomo_story_entry(note: dict[str, Any]) -> dict[str, Any]:
    title = derive_flomo_title(note)
    body = str(note.get("content") or "").strip()
    weight_class, story_score, reasons = classify_story_weight(title, body, "flomo")
    return {
        "source_type": "flomo",
        "source_id": str(note.get("memo_id") or ""),
        "title": title,
        "body_text": body,
        "source_url": str(note.get("source_url") or ""),
        "deep_link": str(note.get("deep_link") or ""),
        "timestamp": canonical_timestamp(str(note.get("updated_at") or "")),
        "tags": normalize_list(note.get("tags")),
        "has_image": bool(note.get("has_image")),
        "attachment_urls": normalize_list(note.get("attachment_urls")),
        "image_urls": normalize_list(note.get("image_urls")),
        "weight_class": weight_class,
        "story_score": story_score,
        "classification_reasons": reasons,
    }


def zsxq_story_entry(entry: dict[str, Any]) -> dict[str, Any]:
    title = str(entry.get("title") or "").strip() or str(entry.get("entry_id") or "未命名条目")
    body = split_zsxq_body(title, str(entry.get("body_text") or ""))
    weight_class, story_score, reasons = classify_story_weight(title, body, "zsxq_column")
    return {
        "source_type": "zsxq_column",
        "source_id": str(entry.get("entry_id") or ""),
        "title": title,
        "body_text": body,
        "source_url": str(entry.get("post_url") or ""),
        "timestamp": canonical_timestamp(str(entry.get("published_at") or "")),
        "tags": [],
        "has_image": False,
        "attachment_urls": [],
        "image_urls": [],
        "weight_class": weight_class,
        "story_score": story_score,
        "classification_reasons": reasons,
    }


def sort_story_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(item: dict[str, Any]) -> tuple[int, str, str]:
        parsed = parse_datetime(str(item.get("timestamp") or ""))
        stamp = parsed.isoformat() if parsed else str(item.get("timestamp") or "")
        return (-int(item.get("story_score") or 0), stamp, str(item.get("title") or ""))

    return sorted(entries, key=sort_key)


def summarize_source_payload(name: str, payload: dict[str, Any], *, item_key: str) -> dict[str, Any]:
    items = payload.get(item_key, [])
    return {
        "name": name,
        "status": str(payload.get("status") or ""),
        "blocked_reason": str(payload.get("blocked_reason") or ""),
        "item_count": len(items if isinstance(items, list) else []),
    }


def build_arc_update_suggestions(
    episode_candidates: list[dict[str, Any]],
    supporting_reference: list[dict[str, Any]],
    reference_heavy: list[dict[str, Any]],
) -> list[str]:
    suggestions: list[str] = []
    if any(item.get("source_type") == "zsxq_column" for item in episode_candidates):
        suggestions.append("用 `原力养虾炼丹` 里的现实管理/组织情境，补强连续剧的“外部世界试炼”。")
    if any(item.get("source_type") == "flomo" for item in episode_candidates):
        suggestions.append("保留 Flomo `#星球精选` 的第一人称现场感，让剧情继续从小刺猬当下的判断切入。")
    if reference_heavy:
        suggestions.append("把重理论条目降到背景参考层，只让它们解释世界规则，不直接顶替单集任务剧情。")
    if supporting_reference and not reference_heavy:
        suggestions.append("把 supporting references 用来补白人物关系和判断依据，不要让它们抢走单集主线。")
    if episode_candidates:
        top_titles = " / ".join(str(item.get("title") or "") for item in episode_candidates[:3])
        suggestions.append(f"下一轮优先从这些故事种子起草：{top_titles}")
    else:
        suggestions.append("当前双源里还没有足够强的任务型条目，先补 auth 和更完整的正文后再刷新故事种子。")
    return suggestions


def build_reauth_bundle(
    *,
    run_id: str,
    created_at: str,
    session: str | None,
    headless: bool,
    flomo_payload: dict[str, Any],
    zsxq_scan: dict[str, Any],
) -> dict[str, Any]:
    base_command = [
        "python3",
        str((SCRIPT_DIR / "ai_da_guan_jia.py").resolve()),
        "story-source-refresh",
    ]
    if session:
        base_command.extend(["--session", session])
    if headless:
        base_command.append("--headless")
    return {
        "run_id": run_id,
        "created_at": created_at,
        "status": "blocked_needs_user",
        "message": "至少有一侧素材源需要重新授权。请在同一个人工窗口里同时完成 Flomo 和知识星球的重授权，再重新刷新故事素材。",
        "flomo_tag": DEFAULT_FLOMO_TAG,
        "group_url": DEFAULT_ZSXQ_GROUP_URL,
        "zsxq_column": DEFAULT_ZSXQ_COLUMN,
        "actions": [
            {
                "system": "flomo",
                "action": "mcp_login",
                "command": "codex mcp login flomo",
                "description": "重新授权 Flomo MCP，让 `#星球精选` 能被读取。",
            },
            {
                "system": "zsxq",
                "action": "browser_login",
                "url": DEFAULT_ZSXQ_GROUP_URL,
                "description": f"打开知识星球 group 页面，确认栏目 `{DEFAULT_ZSXQ_COLUMN}` 所在页面的登录态和授权有效。",
            },
        ],
        "resume_command": " ".join(base_command),
        "sources": {
            "flomo": summarize_source_payload("flomo", flomo_payload, item_key="notes"),
            "zsxq": summarize_source_payload("zsxq", zsxq_scan, item_key="entries"),
        },
    }


def render_reauth_markdown(bundle: dict[str, Any]) -> str:
    actions = bundle.get("actions", [])
    lines = [
        "# Story Source Reauth",
        "",
        f"- `run_id`: `{bundle.get('run_id', '')}`",
        f"- `status`: `{bundle.get('status', '')}`",
        "",
        str(bundle.get("message") or "").strip(),
        "",
        "## 同时完成这两步",
        "",
    ]
    for index, action in enumerate(actions, start=1):
        lines.append(f"{index}. `{action.get('system', '')}`: {action.get('description', '')}")
        if action.get("command"):
            lines.append(f"   命令：`{action.get('command', '')}`")
        if action.get("url"):
            lines.append(f"   页面：`{action.get('url', '')}`")
    lines.extend(
        [
            "",
            "## 完成后重跑",
            "",
            f"- `{bundle.get('resume_command', '')}`",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_blocked_refresh(status: str, blocked_reason: str, sources: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Story Source Refresh",
            "",
            f"- `status`: `{status}`",
            f"- `publish_column`: `{DEFAULT_PUBLISH_COLUMN}`",
            f"- `flomo_tag`: `{DEFAULT_FLOMO_TAG}`",
            f"- `zsxq_column`: `{DEFAULT_ZSXQ_COLUMN}`",
            "",
            "## Blocked reason",
            "",
            blocked_reason or "Unknown blocker",
            "",
            "## Source status",
            "",
            f"- Flomo: `{sources['flomo']['status']}` / {sources['flomo']['blocked_reason'] or 'ready'}",
            f"- ZSXQ: `{sources['zsxq']['status']}` / {sources['zsxq']['blocked_reason'] or 'ready'}",
            "",
        ]
    )


def render_story_source_refresh(summary: dict[str, Any], seeds: dict[str, Any]) -> str:
    lines = [
        "# Story Source Refresh",
        "",
        f"- `run_id`: `{summary.get('run_id', '')}`",
        f"- `status`: `{summary.get('status', '')}`",
        f"- `publish_column`: `{summary.get('publish_column', '')}`",
        f"- `flomo_tag`: `{summary.get('flomo_tag', '')}`",
        f"- `zsxq_column`: `{summary.get('zsxq_column', '')}`",
        "",
        "## Source summary",
        "",
        f"- Flomo notes: {summary['sources']['flomo']['item_count']}",
        f"- ZSXQ entries: {summary['sources']['zsxq']['item_count']}",
        "",
        "## Corpus weights",
        "",
        f"- `episode_candidate`: {seeds['counts']['episode_candidate']}",
        f"- `supporting_reference`: {seeds['counts']['supporting_reference']}",
        f"- `reference_heavy`: {seeds['counts']['reference_heavy']}",
        "",
    ]
    if seeds.get("episode_candidates"):
        lines.extend(["## Episode candidates", ""])
        for item in seeds["episode_candidates"][:MAX_EPISODE_SEEDS]:
            lines.append(
                f"- [{item.get('source_type', '')}] {item.get('title', '')} | score={item.get('story_score', 0)} | {', '.join(item.get('classification_reasons', []))}"
            )
        lines.append("")
    if seeds.get("reference_heavy"):
        lines.extend(["## Heavy references", ""])
        for item in seeds["reference_heavy"][:6]:
            lines.append(f"- [{item.get('source_type', '')}] {item.get('title', '')}")
        lines.append("")
    if seeds.get("arc_update_suggestions"):
        lines.extend(["## 建议如何更新长线", ""])
        for suggestion in seeds["arc_update_suggestions"]:
            lines.append(f"- {suggestion}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_story_source_bundle(
    *,
    run_id: str,
    created_at: str,
    status: str,
    flomo_payload: dict[str, Any],
    zsxq_scan: dict[str, Any],
    counts: dict[str, int] | None,
) -> None:
    bundle = load_optional_json(STORY_SOURCE_BUNDLE_PATH)
    if not bundle:
        bundle = {
            "column_name": DEFAULT_PUBLISH_COLUMN,
            "human_role": flomo_helpers.DEFAULT_HUMAN_ROLE,
            "ai_role": flomo_helpers.DEFAULT_AI_ROLE,
            "persona_visibility": flomo_helpers.DEFAULT_PERSONA_VISIBILITY,
            "story_model": flomo_helpers.DEFAULT_STORY_MODEL,
        }
    bundle["column_name"] = DEFAULT_PUBLISH_COLUMN
    bundle["publish_column"] = DEFAULT_PUBLISH_COLUMN
    bundle["story_arc_plan_path"] = str(STORY_ARC_PLAN_PATH.resolve())
    bundle["character_contract_path"] = str(CHARACTER_CONTRACT_PATH.resolve())
    bundle["dual_source_refresh"] = {
        "run_id": run_id,
        "created_at": created_at,
        "status": status,
        "flomo_tag": DEFAULT_FLOMO_TAG,
        "zsxq_column": DEFAULT_ZSXQ_COLUMN,
        "group_url": DEFAULT_ZSXQ_GROUP_URL,
        "sources": {
            "flomo": summarize_source_payload("flomo", flomo_payload, item_key="notes"),
            "zsxq": summarize_source_payload("zsxq", zsxq_scan, item_key="entries"),
        },
        "counts": counts or {},
        "source_mode": "parallel_read_only",
    }
    bundle["reading_weight_policy"] = {
        "episode_candidate": "具体任务、具体难题、协作转折、误判修正、第一次成功",
        "supporting_reference": "能解释剧情节点，但不是单集主线",
        "reference_heavy": "理论密度高、系统密度高、抽象长文，保留但降权",
    }
    write_json(STORY_SOURCE_BUNDLE_PATH, bundle)


def command_story_source_refresh(args: Any) -> int:
    created_at = iso_now()
    run_id = str(getattr(args, "run_id", "") or story_source_refresh_run_id(created_at))
    session = str(getattr(args, "session", "") or "").strip() or None
    headless = bool(getattr(args, "headless", False))

    ensure_dir(STORY_CANON_CURRENT_ROOT)
    run_dir = run_dir_for(run_id, created_at)
    flomo_dir = ensure_dir(run_dir / "sources" / "flomo")
    zsxq_dir = ensure_dir(run_dir / "sources" / "zsxq")

    with ThreadPoolExecutor(max_workers=2) as executor:
        flomo_future = executor.submit(
            flomo_helpers.read_flomo_candidates,
            DEFAULT_FLOMO_TAG,
            {},
            DEFAULT_FLOMO_LIMIT,
        )
        zsxq_future = executor.submit(
            zsxq_helpers.scan_zsxq_column,
            group_url=DEFAULT_ZSXQ_GROUP_URL,
            column_name=DEFAULT_ZSXQ_COLUMN,
            run_id=run_id,
            run_dir=zsxq_dir,
            limit=0,
            headless=headless,
            session=session,
        )
        flomo_payload = dict(flomo_future.result())
        zsxq_scan = dict(zsxq_future.result())

    write_json(flomo_dir / "flomo-read.json", flomo_payload)
    write_json(zsxq_dir / "zsxq-scan.json", zsxq_scan)

    sources = {
        "flomo": summarize_source_payload("flomo", flomo_payload, item_key="notes"),
        "zsxq": summarize_source_payload("zsxq", zsxq_scan, item_key="entries"),
    }
    needs_auth = looks_like_auth_blocker(str(flomo_payload.get("status") or ""), str(flomo_payload.get("blocked_reason") or "")) or looks_like_auth_blocker(
        str(zsxq_scan.get("status") or ""),
        str(zsxq_scan.get("blocked_reason") or ""),
    )
    if needs_auth:
        bundle = build_reauth_bundle(
            run_id=run_id,
            created_at=created_at,
            session=session,
            headless=headless,
            flomo_payload=flomo_payload,
            zsxq_scan=zsxq_scan,
        )
        write_json(run_dir / "reauth-bundle.json", bundle)
        (run_dir / "reauth.md").write_text(render_reauth_markdown(bundle), encoding="utf-8")
        (run_dir / "story-source-refresh.md").write_text(
            render_blocked_refresh("blocked_needs_user", str(bundle.get("message") or ""), sources),
            encoding="utf-8",
        )
        write_story_source_bundle(
            run_id=run_id,
            created_at=created_at,
            status="blocked_needs_user",
            flomo_payload=flomo_payload,
            zsxq_scan=zsxq_scan,
            counts=None,
        )
        latest = {
            "run_id": run_id,
            "created_at": created_at,
            "status": "blocked_needs_user",
            "run_dir": str(run_dir.resolve()),
            "reauth_bundle_path": str((run_dir / "reauth-bundle.json").resolve()),
        }
        write_json(STORY_CANON_LATEST_REFRESH_PATH, latest)
        write_json(STORY_CANON_LAST_REAUTH_PATH, latest)
        print(f"run_id: {run_id}")
        print("status: blocked_needs_user")
        print(f"reauth_bundle_path: {run_dir / 'reauth-bundle.json'}")
        return 1

    if str(flomo_payload.get("status") or "") != "ready" or str(zsxq_scan.get("status") or "") != "ready":
        blocked_reason = " | ".join(
            reason
            for reason in [
                str(flomo_payload.get("blocked_reason") or "").strip(),
                str(zsxq_scan.get("blocked_reason") or "").strip(),
            ]
            if reason
        ) or "Dual-source refresh failed."
        (run_dir / "story-source-refresh.md").write_text(
            render_blocked_refresh("blocked_system", blocked_reason, sources),
            encoding="utf-8",
        )
        write_story_source_bundle(
            run_id=run_id,
            created_at=created_at,
            status="blocked_system",
            flomo_payload=flomo_payload,
            zsxq_scan=zsxq_scan,
            counts=None,
        )
        latest = {
            "run_id": run_id,
            "created_at": created_at,
            "status": "blocked_system",
            "run_dir": str(run_dir.resolve()),
            "blocked_reason": blocked_reason,
        }
        write_json(STORY_CANON_LATEST_REFRESH_PATH, latest)
        print(f"run_id: {run_id}")
        print("status: blocked_system")
        print(f"blocked_reason: {blocked_reason}")
        return 2

    flomo_entries = [flomo_story_entry(note) for note in flomo_payload.get("notes", []) if isinstance(note, dict)]
    zsxq_entries = [zsxq_story_entry(entry) for entry in zsxq_scan.get("entries", []) if isinstance(entry, dict)]
    corpus_entries = sort_story_entries([*flomo_entries, *zsxq_entries])

    episode_candidates = [item for item in corpus_entries if item.get("weight_class") == "episode_candidate"]
    supporting_reference = [item for item in corpus_entries if item.get("weight_class") == "supporting_reference"]
    reference_heavy = [item for item in corpus_entries if item.get("weight_class") == "reference_heavy"]
    arc_update_suggestions = build_arc_update_suggestions(episode_candidates, supporting_reference, reference_heavy)
    counts = {
        "episode_candidate": len(episode_candidates),
        "supporting_reference": len(supporting_reference),
        "reference_heavy": len(reference_heavy),
    }

    corpus = {
        "run_id": run_id,
        "created_at": created_at,
        "status": "ready",
        "publish_column": DEFAULT_PUBLISH_COLUMN,
        "flomo_tag": DEFAULT_FLOMO_TAG,
        "zsxq_column": DEFAULT_ZSXQ_COLUMN,
        "group_url": DEFAULT_ZSXQ_GROUP_URL,
        "sources": sources,
        "counts": counts,
        "entries": corpus_entries,
    }
    seeds = {
        "run_id": run_id,
        "created_at": created_at,
        "status": "ready",
        "counts": counts,
        "episode_candidates": episode_candidates[:MAX_EPISODE_SEEDS],
        "supporting_reference": supporting_reference[:MAX_EPISODE_SEEDS],
        "reference_heavy": reference_heavy[:MAX_EPISODE_SEEDS],
        "arc_update_suggestions": arc_update_suggestions,
    }
    write_json(run_dir / "dual-source-corpus.json", corpus)
    write_json(run_dir / "episode-seeds.json", seeds)
    (run_dir / "story-source-refresh.md").write_text(render_story_source_refresh(corpus, seeds), encoding="utf-8")
    write_story_source_bundle(
        run_id=run_id,
        created_at=created_at,
        status="ready",
        flomo_payload=flomo_payload,
        zsxq_scan=zsxq_scan,
        counts=counts,
    )
    latest = {
        "run_id": run_id,
        "created_at": created_at,
        "status": "ready",
        "run_dir": str(run_dir.resolve()),
        "corpus_path": str((run_dir / "dual-source-corpus.json").resolve()),
        "episode_seeds_path": str((run_dir / "episode-seeds.json").resolve()),
    }
    write_json(STORY_CANON_LATEST_REFRESH_PATH, latest)
    print(f"run_id: {run_id}")
    print("status: ready")
    print(f"corpus_path: {run_dir / 'dual-source-corpus.json'}")
    print(f"episode_seeds_path: {run_dir / 'episode-seeds.json'}")
    return 0
