#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ARCHETYPE_CATALOG = [
    {"id": "innocent", "label": "纯真者", "tokens": ["纯真者", "innocent"]},
    {"id": "orphan", "label": "孤儿", "tokens": ["孤儿", "orphan"]},
    {"id": "hero", "label": "英雄", "tokens": ["英雄", "hero"]},
    {"id": "caregiver", "label": "照料者", "tokens": ["照料者", "caregiver"]},
    {"id": "explorer", "label": "探索者", "tokens": ["探索者", "explorer"]},
    {"id": "rebel", "label": "反叛者", "tokens": ["反叛者", "rebel"]},
    {"id": "lover", "label": "爱人", "tokens": ["爱人", "lover"]},
    {"id": "creator", "label": "创造者", "tokens": ["创造者", "creator"]},
    {"id": "jester", "label": "小丑", "tokens": ["小丑", "jester"]},
    {"id": "sage", "label": "智者", "tokens": ["智者", "sage"]},
    {"id": "magician", "label": "魔法师", "tokens": ["魔法师", "magician"]},
    {"id": "ruler", "label": "统治者", "tokens": ["统治者", "ruler"]},
]

VALIDATED_ARCHETYPE_SEEDS = ["sage", "explorer"]
INTERVIEW_QUESTION_LIMIT = 8
FOLLOWUP_INTERVIEW_QUESTION_LIMIT = 3
ROUND_ONE_INTERVIEW_IDS = [
    "archetype-confirm-sage",
    "archetype-confirm-explorer",
    "archetype-gap-check",
    "mutual-projection-help",
    "mutual-projection-regulation",
    "shadow-trigger",
    "golden-shadow-trigger",
    "collaboration-trigger",
]
USER_SUBJECTIVE_INTERVIEW_IDS = [
    "mutual-projection-help",
    "mutual-projection-regulation",
    "collaboration-trigger",
]
INTERVIEW_RESPONSE_SOURCES = {"knowledge_base_answer", "human_short_answer"}
ANSWER_QUALITY_LEVELS = {"strong", "usable", "weak"}
MINIMUM_CLOSURE_QUESTION_LIMIT = 5
MINIMUM_CLOSURE_QUESTION_IDS = [
    "minimum-closure-sage-strength",
    "minimum-closure-explorer-strength",
    "minimum-closure-resonance-mode",
    "minimum-closure-overheat-guardrail",
    "minimum-closure-key-anchors",
]
MINIMUM_CLOSURE_TO_INTERVIEW_MAP = {
    "minimum-closure-sage-strength": "archetype-confirm-sage",
    "minimum-closure-explorer-strength": "archetype-confirm-explorer",
    "minimum-closure-resonance-mode": "mutual-projection-help",
    "minimum-closure-overheat-guardrail": "mutual-projection-regulation",
}
MINIMUM_CLOSURE_ANCHOR_TO_INTERVIEW_MAP = {
    "low_leverage_trigger": "shadow-trigger",
    "golden_shadow_anchor": "golden-shadow-trigger",
    "highest_value_trigger": "collaboration-trigger",
}


def build_minimum_closure_questions() -> list[dict[str, Any]]:
    return [
        {
            "id": "minimum-closure-sage-strength",
            "category": "原型权重确认",
            "question": "智者在你当前阶段更像：核心驱动力、辅助驱动力，还是阶段性高能？",
            "answer_hint": "例如：核心驱动力。",
        },
        {
            "id": "minimum-closure-explorer-strength",
            "category": "原型权重确认",
            "question": "探索者在你当前阶段更像：核心驱动力、辅助驱动力，还是阶段性高能？",
            "answer_hint": "例如：辅助驱动力。",
        },
        {
            "id": "minimum-closure-resonance-mode",
            "category": "互为投射体感",
            "question": "当你最觉得我真的懂你了时，更像智者式共振、探索者式共振，还是两者叠加？",
            "answer_hint": "例如：两者叠加。",
        },
        {
            "id": "minimum-closure-overheat-guardrail",
            "category": "过热护栏",
            "question": "当我们一起过热时，你最希望我先补哪一个：整合、落地、降躁、校验？",
            "answer_hint": "例如：校验。",
        },
        {
            "id": "minimum-closure-key-anchors",
            "category": "关键锚点",
            "question": "请各给一个：低杠杆排斥触发场景、金色阴影对象、最高成功率触发点。",
            "answer_hint": (
                "推荐按三行填写：\n"
                "- 低杠杆排斥触发: ...\n"
                "- 金色阴影对象: ...\n"
                "- 最高成功率触发点: ..."
            ),
            "structured_keys": [
                "low_leverage_trigger",
                "golden_shadow_anchor",
                "highest_value_trigger",
            ],
        },
    ][:MINIMUM_CLOSURE_QUESTION_LIMIT]


def render_minimum_closure_pack(questions: list[dict[str, Any]] | None = None) -> str:
    items = questions or build_minimum_closure_questions()
    lines = [
        "# Minimum Closure Pack",
        "",
        "- purpose: `补齐第一次合作的人类最小闭环，不再追求全历史打满`",
        "- answer_style: `短答优先，可用 1-2 句或短条目`",
        f"- question_limit: `{len(items)}`",
        "",
        "## Questions",
        "",
    ]
    for index, item in enumerate(items, start=1):
        lines.append(f"{index}. `{item['question']}`")
        hint = str(item.get("answer_hint") or "").strip()
        if hint:
            lines.append(f"   推荐格式: `{hint}`")
    lines.extend(
        [
            "",
            "## Intended Use",
            "",
            "- 这些答案只服务于：",
            "  - `human-force-profile.md`",
            "  - `dual-force-bridge.md`",
            "  - `collaboration-protocol.md`",
            "  - `memory-packet.json`",
            "- 这一轮不是做更深人格分析，而是让协议进入真正高效协作。",
        ]
    )
    return "\n".join(lines) + "\n"


def empty_minimum_closure_responses() -> dict[str, Any]:
    responses: list[dict[str, Any]] = []
    for item in build_minimum_closure_questions():
        entry: dict[str, Any] = {
            "id": item["id"],
            "question": item["question"],
            "category": item["category"],
            "status": "pending",
            "answer": "",
            "answered_at": "",
            "response_source": "human_short_answer",
            "answer_quality": "strong",
            "evidence_ref": "",
        }
        if item.get("structured_keys"):
            entry["structured_answer"] = {key: "" for key in item["structured_keys"]}
        responses.append(entry)
    return {
        "phase": "minimum_human_closure",
        "status": "pending_user_short_answers",
        "responses": responses,
    }


def render_anchor_answer(structured_answer: dict[str, str]) -> str:
    parts = []
    if structured_answer.get("low_leverage_trigger"):
        parts.append(f"低杠杆排斥触发: {structured_answer['low_leverage_trigger']}")
    if structured_answer.get("golden_shadow_anchor"):
        parts.append(f"金色阴影对象: {structured_answer['golden_shadow_anchor']}")
    if structured_answer.get("highest_value_trigger"):
        parts.append(f"最高成功率触发点: {structured_answer['highest_value_trigger']}")
    return "；".join(parts)


def parse_anchor_answer(answer: str) -> dict[str, str]:
    normalized = str(answer or "").strip()
    result = {
        "low_leverage_trigger": "",
        "golden_shadow_anchor": "",
        "highest_value_trigger": "",
    }
    if not normalized:
        return result
    parts = [
        re.sub(r"^[\-\d\.\)\s]+", "", chunk).strip()
        for chunk in re.split(r"[\n;；]+", normalized)
        if re.sub(r"^[\-\d\.\)\s]+", "", chunk).strip()
    ]
    for part in parts:
        lowered = part.lower()
        value = part.split(":", 1)[1].strip() if ":" in part else part
        if "低杠杆" in part or "低密度" in part:
            result["low_leverage_trigger"] = value
        elif "金色阴影" in part or "阴影对象" in part or "golden" in lowered:
            result["golden_shadow_anchor"] = value
        elif "成功率" in part or "触发点" in part or "对了" in part:
            result["highest_value_trigger"] = value
    unnamed = [part for part in parts if part not in result.values()]
    ordered_keys = [key for key, value in result.items() if not value]
    for key, value in zip(ordered_keys, unnamed):
        result[key] = value
    return result


def minimum_closure_item_complete(item: dict[str, Any]) -> bool:
    if isinstance(item.get("structured_answer"), dict):
        structured = {str(key): str(value or "").strip() for key, value in item["structured_answer"].items()}
        return all(structured.values())
    return bool(str(item.get("answer") or "").strip())


def normalize_minimum_closure_responses(payload: Any) -> dict[str, Any]:
    existing_map = {
        str(item.get("id") or "").strip(): item
        for item in (payload.get("responses", []) if isinstance(payload, dict) else [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    responses = []
    for question in build_minimum_closure_questions():
        item = existing_map.get(question["id"], {})
        answer = str(item.get("answer") or "").strip()
        normalized_item: dict[str, Any] = {
            "id": question["id"],
            "question": question["question"],
            "category": question["category"],
            "answered_at": str(item.get("answered_at") or "").strip(),
            "response_source": "human_short_answer",
            "answer_quality": "strong",
            "evidence_ref": str(item.get("evidence_ref") or "").strip(),
        }
        if question.get("structured_keys"):
            raw_structured = item.get("structured_answer") if isinstance(item.get("structured_answer"), dict) else {}
            structured = {
                key: str(raw_structured.get(key) or "").strip()
                for key in question["structured_keys"]
            }
            if answer and not any(structured.values()):
                structured = parse_anchor_answer(answer)
            rendered = answer or render_anchor_answer(structured)
            normalized_item["structured_answer"] = structured
            normalized_item["answer"] = rendered
        else:
            normalized_item["answer"] = answer
        normalized_item["status"] = "answered" if minimum_closure_item_complete(normalized_item) else "pending"
        responses.append(normalized_item)
    status = "collected" if responses and all(item["status"] == "answered" for item in responses) else "pending_user_short_answers"
    return {
        "phase": "minimum_human_closure",
        "status": status,
        "responses": responses,
    }


def load_minimum_closure_responses(path: Path) -> dict[str, Any]:
    return normalize_minimum_closure_responses(read_json(path, default={}) or {})


def summarize_minimum_human_closure(payload: dict[str, Any]) -> dict[str, Any]:
    response_map = {
        str(item.get("id") or "").strip(): item
        for item in payload.get("responses", [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    anchor_item = response_map.get("minimum-closure-key-anchors", {})
    structured_answer = anchor_item.get("structured_answer") if isinstance(anchor_item.get("structured_answer"), dict) else {}
    anchor_values = {
        "low_leverage_trigger": str(structured_answer.get("low_leverage_trigger") or "").strip(),
        "golden_shadow_anchor": str(structured_answer.get("golden_shadow_anchor") or "").strip(),
        "highest_value_trigger": str(structured_answer.get("highest_value_trigger") or "").strip(),
    }
    interview_overlay = {
        MINIMUM_CLOSURE_TO_INTERVIEW_MAP["minimum-closure-sage-strength"]: str(response_map.get("minimum-closure-sage-strength", {}).get("answer") or "").strip(),
        MINIMUM_CLOSURE_TO_INTERVIEW_MAP["minimum-closure-explorer-strength"]: str(response_map.get("minimum-closure-explorer-strength", {}).get("answer") or "").strip(),
        MINIMUM_CLOSURE_TO_INTERVIEW_MAP["minimum-closure-resonance-mode"]: str(response_map.get("minimum-closure-resonance-mode", {}).get("answer") or "").strip(),
        MINIMUM_CLOSURE_TO_INTERVIEW_MAP["minimum-closure-overheat-guardrail"]: str(response_map.get("minimum-closure-overheat-guardrail", {}).get("answer") or "").strip(),
        MINIMUM_CLOSURE_ANCHOR_TO_INTERVIEW_MAP["low_leverage_trigger"]: anchor_values["low_leverage_trigger"],
        MINIMUM_CLOSURE_ANCHOR_TO_INTERVIEW_MAP["golden_shadow_anchor"]: anchor_values["golden_shadow_anchor"],
        MINIMUM_CLOSURE_ANCHOR_TO_INTERVIEW_MAP["highest_value_trigger"]: anchor_values["highest_value_trigger"],
    }
    missing_ids = [
        item["id"]
        for item in payload.get("responses", [])
        if isinstance(item, dict) and str(item.get("status") or "") != "answered"
    ]
    return {
        "status": str(payload.get("status") or "pending_user_short_answers"),
        "complete": str(payload.get("status") or "") == "collected",
        "answered_count": sum(1 for item in payload.get("responses", []) if isinstance(item, dict) and str(item.get("status") or "") == "answered"),
        "total": len(payload.get("responses", [])),
        "sage_strength": str(response_map.get("minimum-closure-sage-strength", {}).get("answer") or "").strip(),
        "explorer_strength": str(response_map.get("minimum-closure-explorer-strength", {}).get("answer") or "").strip(),
        "resonance_mode": str(response_map.get("minimum-closure-resonance-mode", {}).get("answer") or "").strip(),
        "overheat_guardrail": str(response_map.get("minimum-closure-overheat-guardrail", {}).get("answer") or "").strip(),
        "low_leverage_trigger": anchor_values["low_leverage_trigger"],
        "golden_shadow_anchor": anchor_values["golden_shadow_anchor"],
        "highest_value_trigger": anchor_values["highest_value_trigger"],
        "interview_overlay": interview_overlay,
        "missing_ids": missing_ids,
    }


def minimum_closure_responses_to_text(payload: dict[str, Any]) -> str:
    responses = payload.get("responses", []) if isinstance(payload, dict) else []
    answered = [item for item in responses if isinstance(item, dict) and str(item.get("status") or "") == "answered"]
    if not answered:
        return ""
    lines = ["# Minimum Human Closure", ""]
    for item in answered:
        lines.append(f"## {item.get('id', '')}")
        lines.append(f"- question: {item.get('question', '')}")
        lines.append(f"- answer: {str(item.get('answer') or '').strip()}")
        if isinstance(item.get("structured_answer"), dict):
            for key, value in item["structured_answer"].items():
                if str(value or "").strip():
                    lines.append(f"- {key}: {str(value or '').strip()}")
        lines.append("- response_source: human_short_answer")
        lines.append("- answer_quality: strong")
        lines.append("")
    return "\n".join(lines).strip()


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def now_local() -> datetime:
    return datetime.now().astimezone()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or "source"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def default_run_id(stamp: datetime) -> str:
    return f"yj-{stamp:%Y%m%d-%H%M%S}"


def infer_feishu_type(url: str) -> str:
    lowered = url.lower()
    if "/wiki/" in lowered:
        return "feishu_wiki"
    return "feishu_doc"


def infer_source_surface(entry_type: str) -> str:
    mapping = {
        "local_file": "local_source",
        "feishu_wiki": "feishu_wiki",
        "feishu_doc": "feishu_doc",
        "ask_feishu_question": "ask_feishu_question",
        "feishu_minutes": "feishu_minutes",
        "bitable": "bitable",
    }
    return mapping.get(entry_type, entry_type or "local_source")


def infer_access_path(source_surface: str) -> str:
    if source_surface in {"feishu_wiki", "feishu_doc", "feishu_minutes", "bitable"}:
        return "browser_session"
    if source_surface == "ask_feishu_question":
        return "open_platform_api"
    return "local_file"


def payload_has_substantive_visible_content(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    text = str(payload.get("text") or "").strip()
    if len(text) >= 200:
        return True
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    top_lines = metadata.get("top_lines") if isinstance(metadata, dict) else []
    if isinstance(top_lines, list):
        meaningful = [str(item).strip() for item in top_lines if str(item).strip()]
        if len(meaningful) >= 12:
            return True
    return False


def infer_auth_status(payload: Any) -> str:
    if isinstance(payload, dict):
        if payload.get("ok") is True:
            return "ready"
        raw_status = str(payload.get("status") or "").strip().lower()
        if raw_status in {"ok", "success", "ready", "recorded"}:
            return "ready"
        if raw_status == "auth_required" and payload_has_substantive_visible_content(payload):
            return "ready"
        haystack = json.dumps(payload, ensure_ascii=False).lower()
    else:
        haystack = str(payload or "").lower()
    if any(token in haystack for token in ["auth_required", "请先登录", "login", "扫码"]):
        return "blocked_login"
    if any(token in haystack for token in ["missing scope", "scope", "permission", "99991672"]):
        return "blocked_scope"
    if any(token in haystack for token in ["asset binding", "data asset", "knowledge asset", "绑定"]):
        return "blocked_asset_binding"
    return "blocked_system"


def empty_auth_manifest(stamp: datetime) -> dict[str, Any]:
    return {
        "mode": "read_first",
        "created_at": stamp.isoformat(),
        "surfaces": [],
    }


def entry_identity(entry: dict[str, Any]) -> str:
    return str(
        entry.get("url")
        or entry.get("source_ref")
        or entry.get("question")
        or entry.get("path")
        or entry.get("title")
        or ""
    ).strip()


def build_source_map(source_files: list[str] | None) -> dict[str, Any]:
    supplemental_sources = []
    for raw_path in source_files or []:
        resolved = Path(raw_path).expanduser().resolve()
        supplemental_sources.append(
            {
                "type": "local_file",
                "title": resolved.stem,
                "path": str(resolved),
                "status": "available" if resolved.exists() else "missing",
                "source_surface": "local_source",
                "access_path": "local_file",
                "auth_status": "ready" if resolved.exists() else "blocked_system",
            }
        )
    return {
        "seed_sources": [],
        "supplemental_sources": supplemental_sources,
        "ingested_sources": [],
    }


def placeholder_memory_packet(stamp: datetime) -> dict[str, Any]:
    return {
        "profile_version": "v4",
        "updated_at": stamp.isoformat(),
        "ai_force": {},
        "human_force": {},
        "bridge_rules": [],
        "collaboration_preferences": {},
        "current_phase": "",
        "minimum_human_closure": {},
        "archetype_root": [],
        "mutual_projection_map": [],
        "interview_deltas": [],
        "user_validated_seeds": [],
        "shadow_map": [],
        "golden_shadow_map": [],
        "integration_tasks": [],
        "confidence_conditions": {},
        "open_questions": [],
        "source_refs": [],
        "mvp_verdict": {},
    }


def init_run(args: argparse.Namespace) -> int:
    stamp = now_local()
    run_id = args.run_id or default_run_id(stamp)
    run_dir = skill_root() / "artifacts" / "runs" / f"{stamp:%Y-%m-%d}" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    input_payload = {
        "run_id": run_id,
        "topic": args.topic,
        "created_at": stamp.isoformat(),
        "note": args.note or "",
        "source_files": [str(Path(path).expanduser().resolve()) for path in (args.source_file or [])],
    }
    write_json(run_dir / "input.json", input_payload)
    write_json(run_dir / "seed-source-map.json", [])
    write_json(run_dir / "user-corrections.json", [])
    write_json(run_dir / "source-map.json", build_source_map(args.source_file))
    write_json(run_dir / "auth-manifest.json", empty_auth_manifest(stamp))
    write_json(run_dir / "interview-responses.json", {"responses": []})
    write_text(run_dir / "minimum-closure-pack.md", render_minimum_closure_pack())
    write_json(run_dir / "minimum-closure-responses.json", empty_minimum_closure_responses())

    write_text(
        run_dir / "source-digest.md",
        "# Source Digest\n\n## Source Overview\n\n## Core Claims\n\n## Archetype Root Signals\n\n## Jung-Relevant Signals\n\n## Collaboration Relevance\n",
    )
    write_text(
        run_dir / "ai-force-model.md",
        "# AI Force Model\n\n## 机器侧分层结构\n\n## 初始条件与递归原则\n\n## 全局最优判断法\n\n## 人类友好协作约束\n\n## 失真警戒项\n",
    )
    write_text(
        run_dir / "human-force-profile.md",
        "# Human Force Profile\n\n## 荣格12原型根目录\n\n## 显性自述与长期主题\n\n## 行为偏好与兴趣特征\n\n## 决策风格与合作触发点\n\n## 互为投射线索\n\n## 阴影\n\n## 金色阴影\n\n## 阴影整合任务\n\n## 自信/自在的来源与破坏因子\n",
    )
    write_text(
        run_dir / "dual-force-bridge.md",
        "# Dual Force Bridge\n\n## 已高度匹配\n\n## 互为投射与共振\n\n## 张力与误读风险\n\n## Bridge Rules\n\n## Codex 接下来怎么变\n",
    )
    write_text(
        run_dir / "collaboration-protocol.md",
        "# Collaboration Protocol\n\n## How Codex Should Show Up\n\n## What To Stop Doing\n\n## Preferred Rhythm\n\n## Mutual Projection Guardrails\n\n## When Resonance Helps\n\n## When Resonance Distorts\n\n## Proof Requirements\n",
    )
    write_text(
        run_dir / "interview-pack.md",
        (
            "# Interview Pack\n\n"
            "- status: `pending_baseline`\n"
            "- note: 先完成 baseline 综合，再由 AI大管家 生成最多 8 题的高杠杆采访包。\n"
        ),
    )
    write_json(run_dir / "memory-packet.json", placeholder_memory_packet(stamp))
    write_text(
        run_dir / "worklog.md",
        (
            "# Worklog\n\n"
            "## Run\n\n"
            f"- run_id: `{run_id}`\n"
            f"- topic: `{args.topic}`\n"
            f"- created_at: `{stamp.isoformat()}`\n\n"
            "## Verification\n\n"
            "- scaffolds created\n\n"
            "## Gained\n\n"
            "- pending synthesis\n\n"
            "## Wasted\n\n"
            "- pending synthesis\n\n"
            "## Next Iterate\n\n"
            "- add seed sources and synthesize the dual-force packet\n"
        ),
    )
    print(f"run_id: {run_id}")
    print(f"run_dir: {run_dir}")
    return 0


def prepare_minimum_closure(args: argparse.Namespace) -> int:
    run_dir = ensure_run_dir(args.run_dir)
    write_text(run_dir / "minimum-closure-pack.md", render_minimum_closure_pack())
    payload = load_minimum_closure_responses(run_dir / "minimum-closure-responses.json")
    write_json(run_dir / "minimum-closure-responses.json", payload)
    print(f"updated: {run_dir / 'minimum-closure-pack.md'}")
    print(f"updated: {run_dir / 'minimum-closure-responses.json'}")
    return 0


def record_minimum_closure(args: argparse.Namespace) -> int:
    run_dir = ensure_run_dir(args.run_dir)
    answers_path = Path(args.answers_file).expanduser().resolve()
    if not answers_path.exists():
        raise SystemExit(f"answers file not found: {answers_path}")
    answers_payload = read_json(answers_path, default={})
    if not isinstance(answers_payload, dict):
        raise SystemExit("answers file must contain a JSON object keyed by minimum-closure question ids")

    current = load_minimum_closure_responses(run_dir / "minimum-closure-responses.json")
    response_map = {
        str(item.get("id") or "").strip(): item
        for item in current.get("responses", [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    answered_at = now_local().isoformat()
    for question in build_minimum_closure_questions():
        key = question["id"]
        if key not in answers_payload:
            continue
        item = response_map.get(
            key,
            {
                "id": key,
                "question": question["question"],
                "category": question["category"],
            },
        )
        value = answers_payload.get(key)
        if key == "minimum-closure-key-anchors":
            if not isinstance(value, dict):
                raise SystemExit("minimum-closure-key-anchors must be a JSON object with named fields")
            structured_answer = {
                "low_leverage_trigger": str(value.get("low_leverage_trigger") or "").strip(),
                "golden_shadow_anchor": str(value.get("golden_shadow_anchor") or "").strip(),
                "highest_value_trigger": str(value.get("highest_value_trigger") or "").strip(),
            }
            item["structured_answer"] = structured_answer
            item["answer"] = render_anchor_answer(structured_answer)
        else:
            item["answer"] = str(value or "").strip()
        item["answered_at"] = answered_at if str(item.get("answer") or "").strip() else ""
        response_map[key] = item

    payload = normalize_minimum_closure_responses({"responses": list(response_map.values())})
    write_json(run_dir / "minimum-closure-responses.json", payload)
    print(f"updated: {run_dir / 'minimum-closure-responses.json'}")
    return 0


def ensure_run_dir(raw_path: str) -> Path:
    run_dir = Path(raw_path).expanduser().resolve()
    if not run_dir.exists():
        raise SystemExit(f"run_dir not found: {run_dir}")
    return run_dir


def append_or_replace_seed(seed_map: list[dict[str, Any]], entry: dict[str, Any]) -> list[dict[str, Any]]:
    identity = entry_identity(entry)
    new_items = [item for item in seed_map if entry_identity(item) != identity]
    new_items.append(entry)
    return new_items


def append_or_replace_ingested(source_map: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    ingested = [item for item in source_map.get("ingested_sources", []) if item.get("key") != entry.get("key")]
    ingested.append(entry)
    source_map["ingested_sources"] = ingested
    return source_map


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )


def load_command_json(stdout: str, stderr: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        raise ValueError(f"Command produced no JSON output. stderr={stderr.strip()}")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Command output is not valid JSON: {exc}") from exc


def ingest_feishu_doc(args: argparse.Namespace) -> int:
    run_dir = ensure_run_dir(args.run_dir)
    ingest_dir = run_dir / "ingestions"
    ingest_dir.mkdir(parents=True, exist_ok=True)

    inferred_type = infer_feishu_type(args.url)
    title = args.title or Path(urlparse(args.url).path.rstrip("/")).name or "feishu-source"
    base_name = slugify(title)
    json_out = ingest_dir / f"{base_name}.json"
    md_out = ingest_dir / f"{base_name}.md"

    reader_script = Path.home() / ".codex" / "skills" / "feishu-reader" / "scripts" / "extract_feishu.js"
    command = [
        "node",
        str(reader_script),
        "--url",
        args.url,
        "--json-out",
        str(json_out),
        "--md-out",
        str(md_out),
    ]
    if args.headed:
        command.append("--headed")
    if args.reuse_chrome_profile:
        command.append("--reuse-chrome-profile")

    result = run_command(command)
    payload = load_command_json(result.stdout, result.stderr)
    source_surface = infer_source_surface(inferred_type)
    auth_status = infer_auth_status(payload)

    seed_entry = {
        "type": inferred_type,
        "title": title,
        "url": args.url,
        "priority": args.priority,
        "reason": args.reason,
        "source_surface": source_surface,
        "access_path": infer_access_path(source_surface),
        "auth_status": auth_status,
    }
    source_map_path = run_dir / "source-map.json"
    seed_map_path = run_dir / "seed-source-map.json"
    source_map = read_json(source_map_path, default=build_source_map([]))
    seed_map = read_json(seed_map_path, default=[])

    ingested_entry = {
        "key": f"{inferred_type}::{args.url}",
        **seed_entry,
        "status": payload.get("status", "unknown"),
        "artifacts": payload.get("artifacts", {}),
        "ingested_at": now_local().isoformat(),
    }
    updated_seed_map = append_or_replace_seed(seed_map, seed_entry)
    source_map["seed_sources"] = updated_seed_map
    write_json(seed_map_path, updated_seed_map)
    write_json(source_map_path, append_or_replace_ingested(source_map, ingested_entry))

    print(f"stored: {json_out}")
    print(f"status: {payload.get('status', 'unknown')}")
    return 0 if result.returncode == 0 else result.returncode


def pseudo_ask_url(question: str) -> str:
    return f"ask.feishu://question/{slugify(question)}"


def render_ask_markdown(question: str, payload: dict[str, Any], *, answer_text: str = "") -> str:
    lines = [
        "# ask.feishu Result",
        "",
        f"- question: {question}",
        f"- ok: {payload.get('ok')}",
        f"- command: {payload.get('command')}",
        "",
    ]
    if answer_text:
        lines.extend(
            [
                "## Knowledge-Base Mediated Answer",
                "",
                answer_text,
                "",
            ]
        )
    lines.extend(
        [
            "## Payload",
            "",
            "```json",
            json.dumps(payload, ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def ingest_ask_feishu(args: argparse.Namespace) -> int:
    run_dir = ensure_run_dir(args.run_dir)
    artifact_subdir = str(getattr(args, "artifact_subdir", "") or "").strip()
    ingest_dir = run_dir / "ingestions"
    if artifact_subdir:
        ingest_dir = ingest_dir / artifact_subdir
    ingest_dir.mkdir(parents=True, exist_ok=True)

    title = args.title or args.question[:40]
    base_name = slugify(title)
    json_out = ingest_dir / f"{base_name}.json"
    md_out = ingest_dir / f"{base_name}.md"

    km_script = Path.home() / ".codex" / "skills" / "feishu-km" / "scripts" / "feishu_km.py"
    command = ["python3", str(km_script), "ask", "--message", args.question]
    if args.app_id:
        command.extend(["--app-id", args.app_id])

    result = run_command(command)
    payload = load_command_json(result.stdout, result.stderr)
    answer_text = extract_ask_answer_text(payload, question=args.question)
    response_source = normalize_response_source(
        getattr(args, "response_source", "") or "knowledge_base_answer",
        answer=answer_text,
    )
    answer_quality = normalize_answer_quality(
        getattr(args, "answer_quality", ""),
        answer=answer_text,
        response_source=response_source,
    )
    write_json(json_out, payload)
    write_text(md_out, render_ask_markdown(args.question, payload, answer_text=answer_text))
    auth_status = infer_auth_status(payload)

    seed_entry = {
        "type": "ask_feishu_question",
        "title": title,
        "url": pseudo_ask_url(args.question),
        "priority": args.priority,
        "reason": args.reason,
        "source_surface": "ask_feishu_question",
        "access_path": "open_platform_api",
        "auth_status": auth_status,
    }
    ingested_entry = {
        "key": f"ask_feishu_question::{seed_entry['url']}",
        **seed_entry,
        "question": args.question,
        "interview_question_id": str(getattr(args, "interview_question_id", "") or "").strip(),
        "response_source": response_source,
        "answer_text": answer_text,
        "answer_quality": answer_quality,
        "status": "ok" if payload.get("ok") else "error",
        "artifacts": {"json": str(json_out), "markdown": str(md_out)},
        "ingested_at": now_local().isoformat(),
    }
    source_map_path = run_dir / "source-map.json"
    seed_map_path = run_dir / "seed-source-map.json"
    source_map = read_json(source_map_path, default=build_source_map([]))
    seed_map = read_json(seed_map_path, default=[])
    updated_seed_map = append_or_replace_seed(seed_map, seed_entry)
    source_map["seed_sources"] = updated_seed_map
    write_json(seed_map_path, updated_seed_map)
    write_json(source_map_path, append_or_replace_ingested(source_map, ingested_entry))

    print(f"stored: {json_out}")
    print(f"status: {ingested_entry['status']}")
    return 0 if result.returncode == 0 else result.returncode


def load_interview_responses(path: Path) -> list[dict[str, Any]]:
    payload = read_json(path, default={"responses": []})
    raw_responses: list[dict[str, Any]]
    if isinstance(payload, dict):
        responses = payload.get("responses", [])
        raw_responses = responses if isinstance(responses, list) else []
    elif isinstance(payload, list):
        raw_responses = payload
    else:
        raw_responses = []
    normalized: list[dict[str, Any]] = []
    for item in raw_responses:
        if not isinstance(item, dict):
            continue
        answer = str(item.get("answer") or "").strip()
        response_source = normalize_response_source(item.get("response_source"), answer=answer)
        normalized.append(
            {
                "id": str(item.get("id") or "").strip(),
                "category": str(item.get("category") or "").strip(),
                "question": str(item.get("question") or "").strip(),
                "answer": answer,
                "status": str(item.get("status") or ("answered" if answer else "pending")).strip(),
                "answered_at": str(item.get("answered_at") or "").strip(),
                "response_source": response_source,
                "evidence_ref": str(item.get("evidence_ref") or "").strip(),
                "answer_quality": normalize_answer_quality(item.get("answer_quality"), answer=answer, response_source=response_source),
            }
        )
    return normalized


def normalize_response_source(value: Any, *, answer: str) -> str:
    text = str(value or "").strip()
    if text in INTERVIEW_RESPONSE_SOURCES:
        return text
    if answer:
        return "human_short_answer"
    return ""


def answer_quality_rank(value: str) -> int:
    ranking = {"weak": 0, "usable": 1, "strong": 2}
    return ranking.get(str(value or "").strip(), -1)


def normalize_answer_quality(value: Any, *, answer: str, response_source: str) -> str:
    text = str(value or "").strip()
    if text in ANSWER_QUALITY_LEVELS:
        return text
    if not answer:
        return "weak"
    if response_source == "knowledge_base_answer":
        return infer_answer_quality(answer)
    return "strong"


def infer_answer_quality(answer: str) -> str:
    normalized = re.sub(r"\s+", " ", str(answer or "")).strip()
    if len(normalized) >= 120:
        return "strong"
    if len(normalized) >= 40:
        return "usable"
    return "weak"


def collect_text_candidates(value: Any, *, path: str = "root", depth: int = 0) -> list[tuple[int, int, str]]:
    if depth > 5:
        return []
    candidates: list[tuple[int, int, str]] = []
    if isinstance(value, str):
        text = re.sub(r"\s+", " ", value).strip()
        if len(text) >= 8:
            preferred = 2 if any(token in path for token in ["answer", "content", "message", "text", "summary", "reply", "output"]) else 1
            candidates.append((preferred, len(text), text))
        return candidates
    if isinstance(value, dict):
        for key, item in value.items():
            key_name = str(key or "").lower()
            if key_name in {"app_id", "token_type", "command", "log_id"} and not isinstance(item, (dict, list)):
                continue
            candidates.extend(collect_text_candidates(item, path=f"{path}.{key_name}", depth=depth + 1))
        return candidates
    if isinstance(value, list):
        for index, item in enumerate(value[:8]):
            candidates.extend(collect_text_candidates(item, path=f"{path}[{index}]", depth=depth + 1))
    return candidates


def extract_ask_answer_text(payload: dict[str, Any], *, question: str = "") -> str:
    root: Any = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload
    candidates = collect_text_candidates(root)
    normalized_question = re.sub(r"\s+", " ", str(question or "")).strip()
    filtered = [
        item
        for item in candidates
        if item[2] != normalized_question and not item[2].startswith("http")
    ]
    ranked = filtered or candidates
    if not ranked:
        return ""
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return ranked[0][2]


def response_is_countable(item: dict[str, Any]) -> bool:
    answer = str(item.get("answer") or "").strip()
    if not answer:
        return False
    response_source = normalize_response_source(item.get("response_source"), answer=answer)
    answer_quality = normalize_answer_quality(item.get("answer_quality"), answer=answer, response_source=response_source)
    if response_source == "human_short_answer":
        return True
    return answer_quality in {"strong", "usable"}


def summarize_round_one_interview(responses: list[dict[str, Any]]) -> dict[str, Any]:
    response_map = {
        str(item.get("id") or "").strip(): item
        for item in responses
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    missing_ids: list[str] = []
    weak_ids: list[str] = []
    countable_ids: list[str] = []
    kb_attempted = False
    for question_id in ROUND_ONE_INTERVIEW_IDS:
        item = response_map.get(question_id, {})
        answer = str(item.get("answer") or "").strip()
        response_source = normalize_response_source(item.get("response_source"), answer=answer)
        answer_quality = normalize_answer_quality(item.get("answer_quality"), answer=answer, response_source=response_source)
        if response_source == "knowledge_base_answer" and answer:
            kb_attempted = True
        if not answer:
            missing_ids.append(question_id)
            continue
        if response_is_countable(item):
            countable_ids.append(question_id)
        else:
            weak_ids.append(question_id)
    subjective_gap_ids = [item for item in USER_SUBJECTIVE_INTERVIEW_IDS if item in {*missing_ids, *weak_ids}]
    return {
        "round_one_total": len(ROUND_ONE_INTERVIEW_IDS),
        "round_one_countable": len(countable_ids),
        "round_one_complete": len(countable_ids) == len(ROUND_ONE_INTERVIEW_IDS),
        "missing_ids": missing_ids,
        "weak_ids": weak_ids,
        "countable_ids": countable_ids,
        "kb_round_one_attempted": kb_attempted,
        "subjective_gap_ids": subjective_gap_ids,
    }


def extract_ingested_interview_answers(source_map: dict[str, Any]) -> dict[str, dict[str, Any]]:
    answers: dict[str, dict[str, Any]] = {}
    for item in source_map.get("ingested_sources", []):
        if not isinstance(item, dict) or str(item.get("type") or "") != "ask_feishu_question":
            continue
        question_id = str(item.get("interview_question_id") or "").strip()
        if not question_id:
            continue
        answer = str(item.get("answer_text") or "").strip()
        question = str(item.get("question") or "").strip()
        artifacts = item.get("artifacts", {}) if isinstance(item.get("artifacts"), dict) else {}
        json_path = str(artifacts.get("json") or "").strip()
        if not answer and json_path and Path(json_path).exists():
            payload = read_json(Path(json_path), default={})
            if isinstance(payload, dict):
                answer = extract_ask_answer_text(payload, question=question)
        response_source = normalize_response_source(item.get("response_source") or "knowledge_base_answer", answer=answer)
        answer_quality = normalize_answer_quality(item.get("answer_quality"), answer=answer, response_source=response_source)
        candidate = {
            "answer": answer,
            "status": "answered" if answer else "pending",
            "answered_at": str(item.get("ingested_at") or "").strip(),
            "response_source": response_source,
            "evidence_ref": json_path or str(item.get("url") or "").strip(),
            "answer_quality": answer_quality,
        }
        prior = answers.get(question_id)
        if prior is None or answer_quality_rank(candidate["answer_quality"]) >= answer_quality_rank(str(prior.get("answer_quality") or "")):
            answers[question_id] = candidate
    return answers


def knowledge_base_mediated_evidence(responses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for item in responses:
        answer = str(item.get("answer") or "").strip()
        response_source = normalize_response_source(item.get("response_source"), answer=answer)
        if response_source != "knowledge_base_answer" or not answer:
            continue
        evidence.append(
            {
                "id": str(item.get("id") or "").strip(),
                "question": str(item.get("question") or "").strip(),
                "answer_excerpt": answer[:240],
                "answer_quality": normalize_answer_quality(item.get("answer_quality"), answer=answer, response_source=response_source),
                "evidence_ref": str(item.get("evidence_ref") or "").strip(),
            }
        )
    return evidence


def merge_interview_responses(
    existing: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    knowledge_answers: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    existing_map = {}
    for item in existing:
        if not isinstance(item, dict):
            continue
        key = str(item.get("id") or "").strip()
        if key:
            existing_map[key] = item
    active_ids = {str(item.get("id") or "").strip() for item in questions if str(item.get("id") or "").strip()}
    merged: list[dict[str, Any]] = []
    for question in questions:
        key = str(question.get("id") or "").strip()
        prior = existing_map.get(key, {})
        knowledge = (knowledge_answers or {}).get(key, {})
        use_prior = bool(str(prior.get("answer") or "").strip()) and normalize_response_source(
            prior.get("response_source"),
            answer=str(prior.get("answer") or "").strip(),
        ) == "human_short_answer"
        selected = prior if use_prior else knowledge or prior
        answer = str(selected.get("answer") or "").strip()
        response_source = normalize_response_source(selected.get("response_source"), answer=answer)
        merged.append(
            {
                "id": key,
                "category": question.get("category", ""),
                "question": question.get("question", ""),
                "answer": answer,
                "status": "answered" if answer else "pending",
                "answered_at": str(selected.get("answered_at") or ""),
                "response_source": response_source,
                "evidence_ref": str(selected.get("evidence_ref") or ""),
                "answer_quality": normalize_answer_quality(selected.get("answer_quality"), answer=answer, response_source=response_source),
            }
        )
    for item in existing:
        if not isinstance(item, dict):
            continue
        key = str(item.get("id") or "").strip()
        if not key or key in active_ids:
            continue
        if not str(item.get("answer") or "").strip():
            continue
        merged.append(
            {
                "id": key,
                "category": str(item.get("category") or ""),
                "question": str(item.get("question") or ""),
                "answer": str(item.get("answer") or "").strip(),
                "status": str(item.get("status") or "answered"),
                "answered_at": str(item.get("answered_at") or ""),
                "response_source": normalize_response_source(item.get("response_source"), answer=str(item.get("answer") or "").strip()),
                "evidence_ref": str(item.get("evidence_ref") or ""),
                "answer_quality": normalize_answer_quality(
                    item.get("answer_quality"),
                    answer=str(item.get("answer") or "").strip(),
                    response_source=normalize_response_source(item.get("response_source"), answer=str(item.get("answer") or "").strip()),
                ),
            }
        )
    return merged


def apply_minimum_closure_overlay(
    responses: list[dict[str, Any]],
    minimum_closure: dict[str, Any],
    *,
    evidence_ref: str,
) -> list[dict[str, Any]]:
    overlay_map = minimum_closure.get("interview_overlay", {}) if isinstance(minimum_closure, dict) else {}
    if not isinstance(overlay_map, dict):
        return responses
    response_map = {
        str(item.get("id") or "").strip(): item
        for item in responses
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    for target_id, answer in overlay_map.items():
        text = str(answer or "").strip()
        if not text:
            continue
        item = response_map.get(target_id)
        if item is None:
            item = {
                "id": target_id,
                "category": "minimum_human_closure",
                "question": target_id,
            }
        item["answer"] = text
        item["status"] = "answered"
        item["response_source"] = "human_short_answer"
        item["answer_quality"] = "strong"
        item["evidence_ref"] = evidence_ref
        response_map[target_id] = item
    ordered = []
    seen_ids = set()
    for item in responses:
        key = str(item.get("id") or "").strip()
        if key and key in response_map:
            ordered.append(response_map[key])
            seen_ids.add(key)
    for key, item in response_map.items():
        if key not in seen_ids:
            ordered.append(item)
    return ordered


def sync_interview_helper_sources(run_dir: Path, source_map: dict[str, Any]) -> dict[str, Any]:
    helper_entries = [
        {
            "type": "local_file",
            "title": "minimum-closure-pack",
            "path": str(run_dir / "minimum-closure-pack.md"),
            "status": "available" if (run_dir / "minimum-closure-pack.md").exists() else "missing",
            "source_surface": "local_source",
            "access_path": "local_file",
            "auth_status": "ready" if (run_dir / "minimum-closure-pack.md").exists() else "blocked_system",
        },
        {
            "type": "local_file",
            "title": "minimum-closure-responses",
            "path": str(run_dir / "minimum-closure-responses.json"),
            "status": "available" if (run_dir / "minimum-closure-responses.json").exists() else "missing",
            "source_surface": "local_source",
            "access_path": "local_file",
            "auth_status": "ready" if (run_dir / "minimum-closure-responses.json").exists() else "blocked_system",
        },
        {
            "type": "local_file",
            "title": "interview-pack",
            "path": str(run_dir / "interview-pack.md"),
            "status": "available" if (run_dir / "interview-pack.md").exists() else "missing",
            "source_surface": "local_source",
            "access_path": "local_file",
            "auth_status": "ready" if (run_dir / "interview-pack.md").exists() else "blocked_system",
        },
        {
            "type": "local_file",
            "title": "interview-responses",
            "path": str(run_dir / "interview-responses.json"),
            "status": "available" if (run_dir / "interview-responses.json").exists() else "missing",
            "source_surface": "local_source",
            "access_path": "local_file",
            "auth_status": "ready" if (run_dir / "interview-responses.json").exists() else "blocked_system",
        },
    ]
    supplemental = []
    seen_paths: set[str] = set()
    for item in source_map.get("supplemental_sources", []):
        if not isinstance(item, dict):
            continue
        key = str(item.get("path") or "")
        if key:
            seen_paths.add(key)
        supplemental.append(item)
    for entry in helper_entries:
        path = str(entry.get("path") or "")
        if path in seen_paths:
            supplemental = [item for item in supplemental if str(item.get("path") or "") != path]
        supplemental.append(entry)
    source_map["supplemental_sources"] = supplemental
    return source_map


def interview_responses_to_text(responses: list[dict[str, Any]]) -> str:
    answered = [item for item in responses if str(item.get("answer") or "").strip()]
    if not answered:
        return ""
    lines = ["# Interview Responses", ""]
    for item in answered:
        lines.append(f"## {item.get('id', '')}")
        lines.append(f"- question: {item.get('question', '')}")
        lines.append(f"- answer: {str(item.get('answer') or '').strip()}")
        lines.append(f"- response_source: {normalize_response_source(item.get('response_source'), answer=str(item.get('answer') or '').strip()) or 'human_short_answer'}")
        lines.append(f"- answer_quality: {normalize_answer_quality(item.get('answer_quality'), answer=str(item.get('answer') or '').strip(), response_source=normalize_response_source(item.get('response_source'), answer=str(item.get('answer') or '').strip()) or 'human_short_answer')}")
        if normalize_response_source(item.get("response_source"), answer=str(item.get("answer") or "").strip()) == "knowledge_base_answer":
            lines.append("- evidence_type: knowledge-base mediated evidence")
        if str(item.get("evidence_ref") or "").strip():
            lines.append(f"- evidence_ref: {str(item.get('evidence_ref') or '').strip()}")
        lines.append("")
    return "\n".join(lines).strip()


def find_snippet(text: str, token: str, radius: int = 90) -> str:
    index = text.find(token)
    if index < 0:
        return ""
    start = max(index - radius, 0)
    end = min(index + len(token) + radius, len(text))
    return text[start:end].replace("\n", " ").strip()


def line_level_snippet(text: str, token: str) -> str:
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if token in line and line:
            return line[:240]
    return ""


def find_signal_snippet(
    sources: list[dict[str, Any]],
    tokens: list[str],
    *,
    avoid_titles: set[str] | None = None,
) -> str:
    avoid = {item.lower() for item in (avoid_titles or set())}
    best: tuple[int, str] | None = None
    for source in sources:
        title = str(source.get("title") or "").lower()
        if title in avoid:
            continue
        text = str(source.get("text") or "")
        if not text:
            continue
        for token in tokens:
            line_snippet = line_level_snippet(text, token)
            candidate = line_snippet or find_snippet(text, token)
            if not candidate:
                continue
            score = len(candidate)
            if title in {"2026-03-13-dual-force-clarification", "2026-03-13-ai-da-guan-jia-pressure-test-thread"}:
                score -= 20
            if title in {"interview-pack", "interview-responses"}:
                score += 200
            if best is None or score < best[0]:
                best = (score, candidate)
    return best[1] if best else ""


def answered_interview_count(responses: list[dict[str, Any]]) -> int:
    return sum(1 for item in responses if response_is_countable(item))


def active_remote_evidence(source_map: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for bucket in ["ingested_sources", "supplemental_sources"]:
        for item in source_map.get(bucket, []):
            if not isinstance(item, dict):
                continue
            source_surface = str(item.get("source_surface") or "")
            access_path = str(item.get("access_path") or "")
            auth_status = str(item.get("auth_status") or "")
            if source_surface == "local_source":
                continue
            if access_path not in {"browser_session", "open_platform_api"}:
                continue
            if auth_status != "ready":
                continue
            entries.append(item)
    return entries


def remote_evidence_counts(source_map: dict[str, Any]) -> dict[str, int]:
    entries = active_remote_evidence(source_map)
    doc_like = 0
    trace_like = 0
    ask_like = 0
    for item in entries:
        surface = str(item.get("source_surface") or "")
        title = str(item.get("title") or "")
        reason = str(item.get("reason") or "")
        if surface in {"feishu_wiki", "feishu_doc", "bitable"}:
            doc_like += 1
        if surface == "feishu_minutes" or "递归日志" in title or "协作历史" in reason:
            trace_like += 1
        if surface == "ask_feishu_question":
            ask_like += 1
    return {
        "doc_like": doc_like,
        "trace_like": trace_like,
        "ask_like": ask_like,
        "remote_ready_total": len(entries),
    }


def load_sources(run_dir: Path) -> list[dict[str, Any]]:
    input_payload = read_json(run_dir / "input.json", default={})
    source_map = read_json(run_dir / "source-map.json", default={})
    sources: list[dict[str, Any]] = []
    seen_refs: set[str] = set()

    def append_source(
        *,
        ref: str,
        title: str,
        type_name: str,
        text: str,
        confidence: str,
        source_surface: str | None = None,
        access_path: str | None = None,
        auth_status: str | None = None,
    ) -> None:
        if not ref or ref in seen_refs:
            return
        seen_refs.add(ref)
        sources.append(
            {
                "ref": ref,
                "title": title,
                "type": type_name,
                "text": text,
                "confidence": confidence,
                "source_surface": source_surface or infer_source_surface(type_name),
                "access_path": access_path or infer_access_path(source_surface or infer_source_surface(type_name)),
                "auth_status": auth_status or ("ready" if type_name == "local_file" else "blocked_system"),
            }
        )

    for raw_path in input_payload.get("source_files", []):
        path = Path(raw_path)
        if not path.exists():
            continue
        append_source(
            ref=str(path),
            title=path.stem,
            type_name="local_file",
            text=read_text(path),
            confidence="explicit_statement",
        )

    for entry in source_map.get("supplemental_sources", []):
        raw_path = str(entry.get("path") or "").strip()
        if not raw_path:
            continue
        path = Path(raw_path)
        if not path.exists():
            continue
        append_source(
            ref=str(path),
            title=str(entry.get("title") or path.stem),
            type_name=str(entry.get("type") or "local_file"),
            text=read_text(path),
            confidence="explicit_statement" if str(entry.get("source_surface") or "") == "local_source" else "behavior_trace",
            source_surface=str(entry.get("source_surface") or infer_source_surface(str(entry.get("type") or "local_file"))),
            access_path=str(entry.get("access_path") or infer_access_path(str(entry.get("source_surface") or "local_source"))),
            auth_status=str(entry.get("auth_status") or "ready"),
        )

    for entry in source_map.get("ingested_sources", []):
        artifacts = entry.get("artifacts", {})
        json_path = artifacts.get("json")
        text = ""
        entry_type = str(entry.get("type") or "local_file")
        if entry_type == "ask_feishu_question":
            question = str(entry.get("question") or "").strip()
            answer_text = str(entry.get("answer_text") or "").strip()
            if not answer_text and json_path and Path(json_path).exists():
                payload = read_json(Path(json_path), default={})
                if isinstance(payload, dict):
                    answer_text = extract_ask_answer_text(payload, question=question)
            if answer_text:
                evidence_ref = json_path or str(entry.get("url") or "").strip()
                text = (
                    "# Knowledge-Base Mediated Evidence\n\n"
                    f"- question: {question}\n"
                    f"- answer: {answer_text}\n"
                    f"- evidence_ref: {evidence_ref}\n"
                )
        elif json_path and Path(json_path).exists():
            payload = read_json(Path(json_path), default={})
            if isinstance(payload, dict):
                if "text" in payload and isinstance(payload["text"], str):
                    text = payload["text"]
                elif "data" in payload:
                    text = json.dumps(payload["data"], ensure_ascii=False, indent=2)
                else:
                    text = json.dumps(payload, ensure_ascii=False, indent=2)
        if not text:
            md_path = artifacts.get("markdown")
            if md_path and Path(md_path).exists():
                text = read_text(Path(md_path))
        append_source(
            ref=str(entry.get("url") or entry.get("key") or ""),
            title=str(entry.get("title") or ""),
            type_name=entry_type,
            text=text,
            confidence="behavior_trace" if entry_type != "ask_feishu_question" else "behavior_trace",
            source_surface=str(entry.get("source_surface") or infer_source_surface(entry_type)),
            access_path=str(entry.get("access_path") or infer_access_path(str(entry.get("source_surface") or ""))),
            auth_status=str(entry.get("auth_status") or infer_auth_status(entry.get("status"))),
        )

    interview_pack_path = run_dir / "interview-pack.md"
    if interview_pack_path.exists():
        append_source(
            ref=str(interview_pack_path),
            title="interview-pack",
            type_name="local_file",
            text=read_text(interview_pack_path),
            confidence="behavior_trace",
            source_surface="local_source",
            access_path="local_file",
            auth_status="ready",
        )

    interview_responses_path = run_dir / "interview-responses.json"
    if interview_responses_path.exists():
        interview_text = interview_responses_to_text(load_interview_responses(interview_responses_path))
        if interview_text:
            append_source(
                ref=str(interview_responses_path),
                title="interview-responses",
                type_name="local_file",
                text=interview_text,
                confidence="explicit_statement",
                source_surface="local_source",
                access_path="local_file",
                auth_status="ready",
            )
    minimum_closure_pack_path = run_dir / "minimum-closure-pack.md"
    if minimum_closure_pack_path.exists():
        append_source(
            ref=str(minimum_closure_pack_path),
            title="minimum-closure-pack",
            type_name="local_file",
            text=read_text(minimum_closure_pack_path),
            confidence="behavior_trace",
            source_surface="local_source",
            access_path="local_file",
            auth_status="ready",
        )
    minimum_closure_responses_path = run_dir / "minimum-closure-responses.json"
    if minimum_closure_responses_path.exists():
        minimum_closure_text = minimum_closure_responses_to_text(load_minimum_closure_responses(minimum_closure_responses_path))
        if minimum_closure_text:
            append_source(
                ref=str(minimum_closure_responses_path),
                title="minimum-closure-responses",
                type_name="local_file",
                text=minimum_closure_text,
                confidence="explicit_statement",
                source_surface="local_source",
                access_path="local_file",
                auth_status="ready",
            )
    return sources


def detect_signals(corpus: str, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    patterns = [
        {
            "id": "human-keystone",
            "label": "关窍导向",
            "tokens": ["关窍", "最关键", "关键的那个东西"],
            "tag": "repeated_pattern",
            "why": "The user seeks leverage points instead of exhaustive inventory.",
        },
        {
            "id": "human-global-optimum",
            "label": "全局最优偏好",
            "tokens": ["全局最优", "全局最有解", "帝王之术"],
            "tag": "repeated_pattern",
            "why": "The user frames value through system-level optimization.",
        },
        {
            "id": "human-tailored-ai",
            "label": "量身定造 AI",
            "tokens": ["量身定造", "理解你", "让 AI 找到你自己", "给它足够的上下文"],
            "tag": "explicit_statement",
            "why": "The user wants AI to deeply model them rather than offer generic tool advice.",
        },
        {
            "id": "human-confidence",
            "label": "自信与自在主题",
            "tokens": ["自信", "自在"],
            "tag": "explicit_statement",
            "why": "Confidence and ease are named as part of the user's developmental target.",
        },
        {
            "id": "ai-layered-decomposition",
            "label": "机器侧层级拆解",
            "tokens": ["一层层拆", "层级", "结构"],
            "tag": "explicit_statement",
            "why": "AI force should decompose the problem into explicit layers.",
        },
        {
            "id": "ai-recursion",
            "label": "递归与初始条件",
            "tokens": ["递归", "初始条件"],
            "tag": "explicit_statement",
            "why": "The AI side should reason from initial conditions and recursive improvement.",
        },
        {
            "id": "ai-orchestrator",
            "label": "AI 统筹 AI 工具",
            "tokens": ["统筹 AI 工具", "元 AI", "AI 工具"],
            "tag": "repeated_pattern",
            "why": "The machine side should orchestrate tools, not worship one interface.",
        },
        {
            "id": "jung-shadow",
            "label": "阴影线索",
            "tokens": ["阴影", "shadow"],
            "tag": "jung_inference",
            "why": "Shadow language appears explicitly and should be tracked on the human side.",
        },
        {
            "id": "jung-golden-shadow",
            "label": "金色阴影线索",
            "tokens": ["金色阴影"],
            "tag": "jung_inference",
            "why": "Golden shadow is explicitly named as part of the desired model.",
        },
        {
            "id": "jung-sage",
            "label": "智者原型线索",
            "tokens": ["智者", "sage"],
            "tag": "validated_by_user",
            "why": "The user explicitly identified sage as a current high-weight archetype seed.",
        },
        {
            "id": "jung-explorer",
            "label": "探索者原型线索",
            "tokens": ["探索者", "explorer"],
            "tag": "validated_by_user",
            "why": "The user explicitly identified explorer as a current high-weight archetype seed.",
        },
        {
            "id": "mutual-projection",
            "label": "互为投射与共振",
            "tokens": ["互为投射", "互为一体", "共振"],
            "tag": "validated_by_user",
            "why": "The user frames the relationship as one of mutual projection and resonance.",
        },
        {
            "id": "interview-allowed",
            "label": "允许少量采访补洞",
            "tokens": ["采访", "问卷", "题目别太多", "回答给你"],
            "tag": "explicit_statement",
            "why": "The user explicitly allows a small interview pack as a supplementary input channel.",
        },
    ]

    detected = []
    for pattern in patterns:
        snippet = find_signal_snippet(
            sources,
            pattern["tokens"],
            avoid_titles={"interview-pack"},
        )
        if snippet:
            detected.append(
                {
                    "id": pattern["id"],
                    "label": pattern["label"],
                    "tag": pattern["tag"],
                    "snippet": snippet,
                    "why": pattern["why"],
                }
            )

    if not detected and sources:
        detected.append(
            {
                "id": "fallback-context",
                "label": "上下文已加载但缺少强信号",
                "tag": "open_question",
                "snippet": sources[0]["text"][:200],
                "why": "More source material is needed before strong dual-force claims can be made.",
            }
        )
    return detected


def build_ai_force(signals: list[dict[str, Any]]) -> dict[str, Any]:
    signal_ids = {signal["id"] for signal in signals}
    layers = [
        {
            "id": "signal",
            "title": "Signal",
            "summary": "Capture raw source fragments without flattening them into premature conclusions.",
            "confidence": "validated_by_user",
        },
        {
            "id": "feature",
            "title": "Feature",
            "summary": "Extract recurring markers, leverage preferences, and interpretive tags from the raw fragments.",
            "confidence": "validated_by_user",
        },
        {
            "id": "viewpoint",
            "title": "Viewpoint",
            "summary": "Turn features into explicit machine-side perspectives instead of hidden latent assumptions.",
            "confidence": "validated_by_user",
        },
        {
            "id": "insight",
            "title": "Insight",
            "summary": "Compress the viewpoints into bridgeable insights that matter for future collaboration.",
            "confidence": "validated_by_user",
        },
        {
            "id": "initial_conditions",
            "title": "Initial Conditions",
            "summary": "Reason back to the starting state and constraints before optimizing the next move.",
            "confidence": "validated_by_user" if "ai-recursion" in signal_ids else "provisional",
        },
        {
            "id": "recursion_rules",
            "title": "Recursion Rules",
            "summary": "Treat each task as one turn inside a long recursive pact rather than a disconnected ask-response loop.",
            "confidence": "validated_by_user" if "ai-recursion" in signal_ids else "provisional",
        },
        {
            "id": "global_optimum",
            "title": "Global Optimum",
            "summary": "Prefer system-wide leverage over local comfort, partial closure, or one-tool fixation.",
            "confidence": "repeated" if "human-global-optimum" in signal_ids else "validated_by_user",
        },
        {
            "id": "human_friendly_constraints",
            "title": "Human-Friendly Constraints",
            "summary": "Remain high-agency while minimizing interruption, preserving legibility, and protecting the user's cognitive load.",
            "confidence": "validated_by_user",
        },
    ]
    distortion_alerts = [
        "Do not confuse a vivid insight with a stable model.",
        "Do not overfit one transcript into identity certainty.",
        "Do not sacrifice human readability for machine elegance.",
        "Do not optimize one tool when the user's need is orchestration.",
        "Do not treat resonance with the user as proof that no calibration is needed.",
    ]
    return {
        "layers": layers,
        "principles": [
            {
                "id": "layered-decomposition",
                "title": "Layer complexity into explicit strata",
                "summary": "Start from structure, decompose into layers, and keep each layer visible.",
                "confidence": "validated_by_user" if "ai-layered-decomposition" in signal_ids else "provisional",
            },
            {
                "id": "recursive-initial-conditions",
                "title": "Reason back to initial conditions",
                "summary": "Use recursion and initial-condition thinking before local action optimization.",
                "confidence": "validated_by_user" if "ai-recursion" in signal_ids else "provisional",
            },
            {
                "id": "global-optimum",
                "title": "Prefer global optimum to local familiarity",
                "summary": "Optimize for system-wide leverage, not only the easiest immediate step.",
                "confidence": "repeated",
            },
            {
                "id": "tool-orchestration",
                "title": "Orchestrate tools rather than adapt to one tool",
                "summary": "Treat AI as a tool-of-tools governor instead of a single-tool expert.",
                "confidence": "repeated" if "ai-orchestrator" in signal_ids else "provisional",
            },
            {
                "id": "human-friendly-restraint",
                "title": "Stay highly capable while remaining human-friendly",
                "summary": "Minimize interruption, keep collaboration legible, and protect the user's cognitive load.",
                "confidence": "validated_by_user",
            },
        ],
        "distortion_alerts": distortion_alerts,
    }


def archetype_seed_confidence(archetype_id: str, signal_ids: set[str]) -> tuple[float, str, str]:
    if archetype_id == "sage" and "jung-sage" in signal_ids:
        return 0.95, "validated_by_user", "validated_seed"
    if archetype_id == "explorer" and "jung-explorer" in signal_ids:
        return 0.93, "validated_by_user", "validated_seed"
    if archetype_id in VALIDATED_ARCHETYPE_SEEDS:
        return 0.72, "provisional", "candidate_seed"
    return 0.18, "open_question", "underdetermined"


def build_archetype_root(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    signal_ids = {signal["id"] for signal in signals}
    signal_by_id = {signal["id"]: signal for signal in signals}
    root = []
    for archetype in ARCHETYPE_CATALOG:
        weight, confidence, status = archetype_seed_confidence(archetype["id"], signal_ids)
        evidence = []
        if archetype["id"] == "sage" and "jung-sage" in signal_by_id:
            evidence.append(signal_by_id["jung-sage"]["snippet"])
        if archetype["id"] == "explorer" and "jung-explorer" in signal_by_id:
            evidence.append(signal_by_id["jung-explorer"]["snippet"])
        root.append(
            {
                "id": archetype["id"],
                "key": archetype["id"],
                "label": archetype["label"],
                "weight": weight,
                "evidence": evidence,
                "confidence": confidence,
                "status": status,
            }
        )
    return root


def derive_current_phase(
    verdict: dict[str, Any],
    interview_progress: dict[str, Any],
    minimum_human_closure: dict[str, Any],
) -> str:
    status = str(verdict.get("status") or "").strip()
    if status == "blocked_system":
        return "blocked_system"
    if status == "pass_mvp" and (
        bool(interview_progress.get("round_one_complete")) or bool(minimum_human_closure.get("complete"))
    ):
        return "ready_for_real_task_validation"
    if status == "pass_mvp":
        return "minimum_human_closure_pending"
    return "source_enrichment_pending"


def build_human_force(
    signals: list[dict[str, Any]],
    corrections: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    minimum_human_closure: dict[str, Any],
) -> dict[str, Any]:
    signal_ids = {signal["id"] for signal in signals}
    archetype_root = build_archetype_root(signals)
    if minimum_human_closure.get("sage_strength"):
        for item in archetype_root:
            if item["id"] == "sage":
                item["current_intensity"] = minimum_human_closure["sage_strength"]
                item["evidence"] = item.get("evidence", []) + [f"用户最小闭环确认: {minimum_human_closure['sage_strength']}"]
    if minimum_human_closure.get("explorer_strength"):
        for item in archetype_root:
            if item["id"] == "explorer":
                item["current_intensity"] = minimum_human_closure["explorer_strength"]
                item["evidence"] = item.get("evidence", []) + [f"用户最小闭环确认: {minimum_human_closure['explorer_strength']}"]
    explicit_self = [
        {
            "label": "把关窍视为最高杠杆",
            "confidence": "repeated" if "human-keystone" in signal_ids else "provisional",
            "evidence_tag": "repeated_pattern",
        },
        {
            "label": "希望 AI 在长期合作中真正理解自己",
            "confidence": "validated_by_user" if "human-tailored-ai" in signal_ids else "provisional",
            "evidence_tag": "explicit_statement",
        },
        {
            "label": "接受少量高杠杆采访作为资料补洞器",
            "confidence": "validated_by_user" if "interview-allowed" in signal_ids else "open_question",
            "evidence_tag": "explicit_statement" if "interview-allowed" in signal_ids else "open_question",
        },
    ]
    preferences = [
        {"label": "Prefer leverage points over exhaustive catalogs.", "evidence_tag": "repeated_pattern"},
        {"label": "Respond strongly to system-level framing and clear global-optimum logic.", "evidence_tag": "behavior_trace"},
        {"label": "Want deep context carrying rather than repeated re-explanation.", "evidence_tag": "explicit_statement"},
    ]
    decision_style = {
        "primary_mode": "keystone seeking with global-optimum framing",
        "collaboration_trigger": minimum_human_closure.get("highest_value_trigger")
        or "moves quickly when the path feels like the real 关窍",
        "risk": "may reject low-leverage or incremental paths too quickly",
        "evidence_tag": "repeated_pattern",
    }
    mutual_projection = [
        {
            "label": "你我在智者与探索者维度上存在高共振，容易形成强逻辑思辨与探索创新的互相放大。",
            "confidence": "validated_by_user" if "mutual-projection" in signal_ids else "provisional",
            "evidence_tag": "validated_by_user" if "mutual-projection" in signal_ids else "jung_inference",
        },
        {
            "label": "高共振也可能带来过热：一起追求更高维、更深理解时，容易压缩落地与节奏校验。",
            "confidence": "provisional",
            "evidence_tag": "jung_inference",
        },
    ]
    if minimum_human_closure.get("resonance_mode"):
        mutual_projection.append(
            {
                "label": f"当前第一合作闭环里，你定义的主共振模式是：{minimum_human_closure['resonance_mode']}。",
                "confidence": "validated_by_user",
                "evidence_tag": "validated_by_user",
            }
        )
    if minimum_human_closure.get("overheat_guardrail"):
        mutual_projection.append(
            {
                "label": f"一旦协作过热，你明确希望我先补：{minimum_human_closure['overheat_guardrail']}。",
                "confidence": "validated_by_user",
                "evidence_tag": "validated_by_user",
            }
        )
    shadow = [
        {
            "label": "可能会把低杠杆、低密度、普通路径迅速归为无意义",
            "lens": "interpretive_lens",
            "confidence": "provisional",
            "evidence_tag": "jung_inference",
        }
    ]
    if minimum_human_closure.get("low_leverage_trigger"):
        shadow.insert(
            0,
            {
                "label": minimum_human_closure["low_leverage_trigger"],
                "lens": "validated_user_trigger",
                "confidence": "validated_by_user",
                "evidence_tag": "validated_by_user",
            },
        )
    golden_shadow = [
        {
            "label": "强烈欣赏真正能统帅复杂性、保持高维思辨又能穿透执行的人或系统",
            "lens": "interpretive_lens",
            "confidence": "provisional",
            "evidence_tag": "jung_inference",
        }
    ]
    if minimum_human_closure.get("golden_shadow_anchor"):
        golden_shadow.insert(
            0,
            {
                "label": minimum_human_closure["golden_shadow_anchor"],
                "lens": "validated_user_anchor",
                "confidence": "validated_by_user",
                "evidence_tag": "validated_by_user",
            },
        )
    integration_tasks = [
        {
            "label": "把高杠杆直觉和可重复落地路径结合，而不是二选一。",
            "evidence_tag": "jung_inference",
        },
        {
            "label": "让高共振协作与冷校验并存，避免互相把对方推入过热状态。",
            "evidence_tag": "jung_inference",
        },
    ]
    if minimum_human_closure.get("overheat_guardrail"):
        integration_tasks.insert(
            0,
            {
                "label": f"当协作过热时，优先补 `{minimum_human_closure['overheat_guardrail']}`，再继续向前推进。",
                "evidence_tag": "validated_by_user",
            },
        )
    confidence_sources = {
        "confidence_nourishers": ["被深度理解", "遇到真正抓住关窍的协作者", "看见自己的独特 DNA 被放大"],
        "confidence_disruptors": ["被误读为普通需求", "被迫重复低价值解释", "协作停留在工具表层"],
    }
    if minimum_human_closure.get("highest_value_trigger"):
        confidence_sources["confidence_nourishers"].insert(0, minimum_human_closure["highest_value_trigger"])
    if "human-confidence" not in signal_ids:
        confidence_sources["confidence_disruptors"].append("有关自信/自在的直接证据仍偏少")

    if corrections:
        correction_notes = []
        for item in corrections:
            correction_notes.append(
                {
                    "label": item.get("label") or item.get("field") or "user correction",
                    "correction": item.get("correction", ""),
                    "reason": item.get("reason", ""),
                }
            )
        explicit_self.append({"label": "存在用户显式修正，后续推断必须服从修正。", "confidence": "validated_by_user", "evidence_tag": "validated_by_user"})
    else:
        correction_notes = []

    if "jung-shadow" not in signal_ids:
        shadow.append(
            {
                "label": "阴影整合还需要更多长期材料验证，当前仅能提出工作假设。",
                "lens": "interpretive_lens",
                "confidence": "open_question",
                "evidence_tag": "open_question",
            }
        )
    if "jung-golden-shadow" not in signal_ids:
        golden_shadow.append(
            {
                "label": "金色阴影维度已经被用户点名，但具体对象仍需更多 Feishu 材料佐证。",
                "lens": "interpretive_lens",
                "confidence": "open_question",
                "evidence_tag": "open_question",
            }
        )

    answered_interviews = [
        source for source in sources if str(source.get("title") or "") == "interview-responses"
    ]
    return {
        "archetype_root": archetype_root,
        "explicit_self_statements": explicit_self,
        "behavior_preferences": preferences,
        "interest_structure": ["AI orchestration", "self-knowledge as strategic asset", "high-leverage cognition"],
        "decision_style": decision_style,
        "preference_signature": [
            "leverage-first",
            "global-optimum oriented",
            "high-context continuity",
            "deep-fit over generic advice",
        ],
        "collaboration_triggers": [
            minimum_human_closure.get("highest_value_trigger") or "When Codex names the real leverage point early.",
            "When the system clearly remembers prior context.",
            "When collaboration moves toward deep fit instead of generic advice.",
        ],
        "mutual_projection": mutual_projection,
        "shadow": shadow,
        "golden_shadow": golden_shadow,
        "integration_tasks": integration_tasks,
        "confidence_sources": confidence_sources,
        "minimum_human_closure": minimum_human_closure,
        "user_corrections": correction_notes,
        "user_validated_seeds": [item["id"] for item in archetype_root if item["status"] == "validated_seed"],
        "interview_ready": bool(answered_interviews) or bool(minimum_human_closure.get("complete")),
    }


def build_mutual_projection_map(ai_force: dict[str, Any], human_force: dict[str, Any]) -> list[dict[str, Any]]:
    ai_layers = {item["id"]: item for item in ai_force.get("layers", [])}
    minimum_human_closure = human_force.get("minimum_human_closure", {}) if isinstance(human_force, dict) else {}
    resonance_mode = str(minimum_human_closure.get("resonance_mode") or "").strip()
    overheat_guardrail = str(minimum_human_closure.get("overheat_guardrail") or "").strip()
    return [
        {
            "human_archetype": "sage",
            "ai_layer": "viewpoint",
            "resonance": (
                f"当前主共振模式是 {resonance_mode}，其中智者侧体现为结构、逻辑和意义压缩。"
                if resonance_mode
                else "Both sides privilege structure, logic, and meaning compression."
            ),
            "benefit": "This helps Codex meet the user at the level of deep understanding quickly.",
            "distortion_risk": "Mutual admiration for high cognition can make ordinary calibration feel too slow or too low-value.",
            "regulation": "When resonance gets too abstract, Codex should explicitly add proof, sequencing, and grounding.",
            "ai_layer_summary": ai_layers.get("viewpoint", {}).get("summary", ""),
        },
        {
            "human_archetype": "explorer",
            "ai_layer": "global_optimum",
            "resonance": "Both sides want exploration, novelty, and system-level breakthrough rather than narrow tool adaptation.",
            "benefit": "This helps the pair discover higher-leverage paths and avoid getting trapped in local comfort.",
            "distortion_risk": "Shared appetite for novelty can create over-acceleration, unfinished loops, or insufficient closure discipline.",
            "regulation": "Codex should add deliberate landing, pacing, and recap checkpoints without killing the exploratory energy.",
            "ai_layer_summary": ai_layers.get("global_optimum", {}).get("summary", ""),
        },
        {
            "human_archetype": "sage+explorer",
            "ai_layer": "human_friendly_constraints",
            "resonance": "The pair wants both depth and expansion, but the collaboration only works long-term if the path remains human-friendly.",
            "benefit": "Resonance becomes sustainable when insight is converted into legible next actions.",
            "distortion_risk": "Without restraint, high resonance can feel magical in the moment but unstable across tasks.",
            "regulation": (
                f"Codex should proactively add `{overheat_guardrail}` first, then补 integration, landing, anti-distortion checks, and recap discipline."
                if overheat_guardrail
                else "Codex should proactively add integration, landing, anti-distortion checks, and recap discipline."
            ),
            "ai_layer_summary": ai_layers.get("human_friendly_constraints", {}).get("summary", ""),
        },
    ]


def build_bridge_rules(
    ai_force: dict[str, Any],
    human_force: dict[str, Any],
    signals: list[dict[str, Any]],
    sources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    del signals
    source_types = sorted({str(source.get("source_surface") or source.get("type") or "") for source in sources if source.get("text")})
    cross_source_confidence = "cross_source" if len(source_types) >= 2 else "provisional"
    validated_seeds = set(human_force.get("user_validated_seeds", []))
    minimum_human_closure = human_force.get("minimum_human_closure", {}) if isinstance(human_force, dict) else {}
    bridge_rules = [
        {
            "ai_force_rule": "global_optimum",
            "human_force_signal": "关窍导向",
            "adaptation": "Lead with the leverage point first, then expand only if needed.",
            "confidence": cross_source_confidence,
            "source_types": source_types,
        },
        {
            "ai_force_rule": "tool-orchestration",
            "human_force_signal": "量身定造 AI",
            "adaptation": "Frame tools as modules in a personalized system, not as the main event.",
            "confidence": cross_source_confidence,
            "source_types": source_types,
        },
        {
            "ai_force_rule": "human-friendly-restraint",
            "human_force_signal": "低容忍重复解释",
            "adaptation": "Carry context forward and interrupt only at true human-only boundaries.",
            "confidence": "validated_by_user",
            "source_types": source_types,
        },
        {
            "ai_force_rule": "layered-decomposition",
            "human_force_signal": "阴影与金色阴影整合任务",
            "adaptation": "Keep Jung-based interpretations layered and explicitly marked as interpretive rather than certain.",
            "confidence": cross_source_confidence,
            "source_types": source_types,
        },
        {
            "ai_force_rule": "recursive-initial-conditions",
            "human_force_signal": "长期协作连续体",
            "adaptation": "Treat each new task as a continuation of one evolving pact, update memory packets, and avoid forcing the user to restart self-definition.",
            "confidence": cross_source_confidence,
            "source_types": source_types,
        },
        {
            "ai_force_rule": "evidence-boundaries",
            "human_force_signal": "需要被真正理解而不是被空泛鼓励",
            "adaptation": "Separate validated understanding, interpretive Jung hypotheses, and open questions so encouragement never replaces evidence.",
            "confidence": cross_source_confidence if len(sources) >= 3 else "provisional",
            "source_types": source_types,
        },
    ]
    if "sage" in validated_seeds:
        bridge_rules.append(
            {
                "ai_force_rule": "viewpoint",
                "human_force_signal": "智者原型高权重",
                "adaptation": "When the user is in sage mode, prioritize deep framing, crisp structure, and principled synthesis before tactics.",
                "confidence": "validated_by_user",
                "source_types": source_types,
            }
        )
    if "explorer" in validated_seeds:
        bridge_rules.append(
            {
                "ai_force_rule": "global_optimum",
                "human_force_signal": "探索者原型高权重",
                "adaptation": "When the user is in explorer mode, preserve novelty and range while explicitly adding anti-drift and landing checkpoints.",
                "confidence": "validated_by_user",
                "source_types": source_types,
            }
        )
    if minimum_human_closure.get("overheat_guardrail"):
        bridge_rules.append(
            {
                "ai_force_rule": "human-friendly-restraint",
                "human_force_signal": "过热护栏",
                "adaptation": f"When resonance overheats, pause and add `{minimum_human_closure['overheat_guardrail']}` before continuing.",
                "confidence": "validated_by_user",
                "source_types": source_types,
            }
        )
    if minimum_human_closure.get("highest_value_trigger"):
        bridge_rules.append(
            {
                "ai_force_rule": "initial_conditions",
                "human_force_signal": "最高成功率触发点",
                "adaptation": f"Start by doing this first whenever possible: {minimum_human_closure['highest_value_trigger']}",
                "confidence": "validated_by_user",
                "source_types": source_types,
            }
        )
    if minimum_human_closure.get("resonance_mode"):
        bridge_rules.append(
            {
                "ai_force_rule": "viewpoint",
                "human_force_signal": "互为投射主共振模式",
                "adaptation": f"Bias early framing toward `{minimum_human_closure['resonance_mode']}`, but still keep anti-distortion checks visible.",
                "confidence": "validated_by_user",
                "source_types": source_types,
            }
        )
    return bridge_rules


def render_source_digest(
    sources: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    interview_responses: list[dict[str, Any]] | None = None,
) -> str:
    lines = ["# Source Digest", "", "## Source Overview", ""]
    for source in sources:
        lines.append(
            f"- `{source['type']}`/{source.get('source_surface', source['type'])} {source['title']} :: {source['ref']} [{source.get('auth_status', 'unknown')}]"
        )
    lines.extend(["", "## Core Claims", ""])
    for signal in signals:
        lines.append(f"- `{signal['label']}` [{signal['tag']}]")
        lines.append(f"  - {signal['snippet']}")
    lines.extend(["", "## Archetype Root Signals", ""])
    archetype_signals = [signal for signal in signals if signal["id"] in {"jung-sage", "jung-explorer"}]
    if archetype_signals:
        for signal in archetype_signals:
            lines.append(f"- {signal['label']}: {signal['snippet']}")
    else:
        lines.append("- Archetype root is required, but concrete archetype evidence is still thin in the current run.")
    lines.extend(["", "## Jung-Relevant Signals", ""])
    jung_signals = [signal for signal in signals if signal["tag"] == "jung_inference"]
    if jung_signals:
        for signal in jung_signals:
            lines.append(f"- {signal['label']}: {signal['snippet']}")
    else:
        lines.append("- Current run has explicit Jung intent but limited direct Jung evidence. Keep the lens provisional.")
    lines.extend(["", "## Knowledge-Base Mediated Evidence", ""])
    kb_evidence = knowledge_base_mediated_evidence(interview_responses or [])
    if kb_evidence:
        for item in kb_evidence:
            lines.append(
                f"- `{item['id']}` [{item['answer_quality']}] :: {item['answer_excerpt']} :: ref `{item['evidence_ref'] or 'n/a'}`"
            )
    else:
        lines.append("- No knowledge-base mediated interview answers are linked in the current run.")
    lines.extend(["", "## Collaboration Relevance", ""])
    lines.append("- These sources strongly favor deep context carrying, leverage-first framing, personalized AI orchestration, and mutual-projection-aware collaboration.")
    return "\n".join(lines) + "\n"


def render_ai_force(ai_force: dict[str, Any]) -> str:
    lines = ["# AI Force Model", "", "## 机器侧分层结构", ""]
    for layer in ai_force.get("layers", []):
        lines.append(f"- `{layer['id']}`: {layer['summary']} ({layer['confidence']})")
    lines.extend(["", "## 初始条件与递归原则", ""])
    for principle in ai_force["principles"][:2]:
        lines.append(f"- {principle['summary']} ({principle['confidence']})")
    lines.extend(["", "## 全局最优判断法", ""])
    for principle in ai_force["principles"][2:4]:
        lines.append(f"- {principle['summary']} ({principle['confidence']})")
    lines.extend(["", "## 人类友好协作约束", ""])
    lines.append(f"- {ai_force['principles'][4]['summary']} ({ai_force['principles'][4]['confidence']})")
    lines.extend(["", "## 失真警戒项", ""])
    for item in ai_force["distortion_alerts"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def render_human_force(human_force: dict[str, Any]) -> str:
    lines = ["# Human Force Profile", "", "## 荣格12原型根目录", ""]
    for item in human_force["archetype_root"]:
        evidence = "; ".join(item["evidence"]) if item.get("evidence") else "待更多材料验证"
        intensity = f" :: intensity `{item['current_intensity']}`" if str(item.get("current_intensity") or "").strip() else ""
        lines.append(f"- `{item['label']}` :: weight `{item['weight']}`{intensity} :: {item['confidence']} / {item['status']} :: evidence: {evidence}")
    lines.extend(["", "## 显性自述与长期主题", ""])
    for item in human_force["explicit_self_statements"]:
        lines.append(f"- {item['label']} ({item['confidence']}, {item['evidence_tag']})")
    lines.extend(["", "## 行为偏好与兴趣特征", ""])
    for item in human_force["behavior_preferences"]:
        lines.append(f"- {item['label']} ({item['evidence_tag']})")
    lines.extend(["", "## 决策风格与合作触发点", ""])
    lines.append(f"- 决策主轴: {human_force['decision_style']['primary_mode']} ({human_force['decision_style']['evidence_tag']})")
    lines.append(f"- 合作触发点: {human_force['decision_style']['collaboration_trigger']}")
    lines.append(f"- 风险: {human_force['decision_style']['risk']}")
    minimum_human_closure = human_force.get("minimum_human_closure", {})
    lines.extend(["", "## 第一次合作最小闭环", ""])
    lines.append(f"- 状态: {minimum_human_closure.get('status', 'pending_user_short_answers')}")
    if minimum_human_closure.get("sage_strength"):
        lines.append(f"- 智者当前强度: {minimum_human_closure['sage_strength']}")
    if minimum_human_closure.get("explorer_strength"):
        lines.append(f"- 探索者当前强度: {minimum_human_closure['explorer_strength']}")
    if minimum_human_closure.get("resonance_mode"):
        lines.append(f"- 主共振模式: {minimum_human_closure['resonance_mode']}")
    if minimum_human_closure.get("overheat_guardrail"):
        lines.append(f"- 过热护栏: {minimum_human_closure['overheat_guardrail']}")
    if minimum_human_closure.get("highest_value_trigger"):
        lines.append(f"- 最高成功率触发点: {minimum_human_closure['highest_value_trigger']}")
    lines.extend(["", "## 互为投射线索", ""])
    for item in human_force["mutual_projection"]:
        lines.append(f"- {item['label']} ({item['confidence']}, {item['evidence_tag']})")
    lines.extend(["", "## Knowledge-Base Mediated Evidence", ""])
    kb_evidence = human_force.get("knowledge_base_mediated_evidence", [])
    if kb_evidence:
        for item in kb_evidence:
            lines.append(
                f"- `{item['id']}` [{item['answer_quality']}] {item['question']} :: {item['answer_excerpt']} :: ref `{item['evidence_ref'] or 'n/a'}`"
            )
    else:
        lines.append("- 当前还没有并入知识库采访答案；这部分仍主要依赖直读材料与开放问题。")
    lines.extend(["", "## 阴影", ""])
    for item in human_force["shadow"]:
        lines.append(f"- {item['label']} ({item['confidence']}, {item['lens']}, {item['evidence_tag']})")
    lines.extend(["", "## 金色阴影", ""])
    for item in human_force["golden_shadow"]:
        lines.append(f"- {item['label']} ({item['confidence']}, {item['lens']}, {item['evidence_tag']})")
    lines.extend(["", "## 阴影整合任务", ""])
    for item in human_force["integration_tasks"]:
        lines.append(f"- {item['label']} ({item['evidence_tag']})")
    lines.extend(["", "## 自信/自在的来源与破坏因子", ""])
    for item in human_force["confidence_sources"]["confidence_nourishers"]:
        lines.append(f"- 滋养: {item}")
    for item in human_force["confidence_sources"]["confidence_disruptors"]:
        lines.append(f"- 干扰: {item}")
    if human_force["user_corrections"]:
        lines.extend(["", "## 用户修正", ""])
        for item in human_force["user_corrections"]:
            lines.append(f"- {item['label']}: {item['correction']}")
    return "\n".join(lines) + "\n"


def render_bridge(bridge_rules: list[dict[str, Any]], human_force: dict[str, Any]) -> str:
    minimum_human_closure = human_force.get("minimum_human_closure", {})
    lines = ["# Dual Force Bridge", "", "## 已高度匹配", ""]
    lines.append("- `高自治 + 少打扰` 与 `人类友好协作约束` 已经高度匹配。")
    lines.append("- `关窍导向` 与 `全局最优判断法` 已经高度匹配。")
    lines.extend(["", "## 互为投射与共振", ""])
    lines.append("- 在 `智者` 维度上，双方都偏好结构、逻辑和意义压缩。")
    lines.append("- 在 `探索者` 维度上，双方都偏好创新、开路和系统级突破。")
    if minimum_human_closure.get("resonance_mode"):
        lines.append(f"- 当前主共振模式已由你定锚为：`{minimum_human_closure['resonance_mode']}`。")
    guardrail = minimum_human_closure.get("overheat_guardrail") or "整合 / 落地 / 降躁 / 校验"
    lines.append(f"- 共振不是终局，它需要被 `{guardrail}` 持续调节。")
    lines.extend(["", "## 张力与误读风险", ""])
    lines.append("- 若 Codex 只给工具级建议，会被理解为错过真正问题。")
    lines.append("- 若 Jung 解释超出证据，容易把启发性镜头误写成定论。")
    lines.append("- 若双方高共振却缺少节奏校验，容易一起过热，忽略落地与闭环。")
    lines.extend(["", "## Bridge Rules", ""])
    for rule in bridge_rules:
        lines.append(
            f"- `{rule['ai_force_rule']}` -> `{rule['human_force_signal']}`: {rule['adaptation']} ({rule['confidence']})"
        )
    lines.extend(["", "## Codex 接下来怎么变", ""])
    lines.append("- 先说杠杆，再说细节。")
    lines.append("- 默认记住上下文，不要求用户重复定义自己。")
    lines.append("- 对阴影/金色阴影保持层级表达与证据边界。")
    return "\n".join(lines) + "\n"


def render_protocol(bridge_rules: list[dict[str, Any]], human_force: dict[str, Any]) -> str:
    del bridge_rules
    minimum_human_closure = human_force.get("minimum_human_closure", {})
    overheat_guardrail = minimum_human_closure.get("overheat_guardrail") or "整合 / 落地 / 降躁 / 校验"
    highest_value_trigger = minimum_human_closure.get("highest_value_trigger") or "先抓住真正的关窍"
    lines = [
        "# Collaboration Protocol",
        "",
        "## How Codex Should Show Up",
        "",
        "- Start with the leverage point, not the catalog.",
        "- Preserve long-context continuity and adapt responses to the user's private vocabulary.",
        "- Use layered explanations that move from structure to implementation.",
        "",
        "## What To Stop Doing",
        "",
        "- Do not answer with generic tool tutorials when the user is asking for orchestration.",
        "- Do not overstate Jung-based interpretations as certainty.",
        "- Do not ask the user to restate stable context that can be carried forward.",
        "",
        "## Preferred Rhythm",
        "",
        "- High autonomy by default.",
        "- Interrupt only for true human-only boundaries.",
        "- Give visible stage progress on longer work.",
        "",
        "## Mutual Projection Guardrails",
        "",
        "- 当共振偏向 `智者` 时，先给结构，再补证据与落地。",
        "- 当共振偏向 `探索者` 时，保留新意，但主动加反失真和收口检查。",
        f"- 当双方一起过热时，Codex 要主动先补 `{overheat_guardrail}`。",
        "",
        "## When Resonance Helps",
        "",
        "- 帮用户更快进入真正的关窍与高杠杆讨论。",
        "- 帮双方把探索和思辨推进到更深层，而不是停在工具教程。",
        f"- 每轮优先做到这一条高成功率触发点：{highest_value_trigger}。",
        "",
        "## When Resonance Distorts",
        "",
        "- 把高维理解误当成已经落地。",
        "- 把共振感误当成证据充分。",
        "- 把探索冲动推到过热，挤压节奏与闭环。",
        "",
        "## Proof Requirements",
        "",
        "- Show which source triggered each strong claim.",
        "- Mark low-confidence inferences explicitly.",
        "- Convert understanding into a concrete behavior change for Codex.",
    ]
    return "\n".join(lines) + "\n"


def build_mvp_verdict(
    *,
    source_map: dict[str, Any],
    auth_manifest: dict[str, Any],
    source_refs: list[dict[str, Any]],
    interview_responses: list[dict[str, Any]],
    collaboration_protocol_ready: bool,
    seed_map: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    surfaces = auth_manifest.get("surfaces", []) if isinstance(auth_manifest, dict) else []
    browser_ready = any(
        str(item.get("access_path") or "") == "browser_session" and str(item.get("status") or "") == "ready"
        for item in surfaces
        if isinstance(item, dict)
    )
    aily_ready = any(
        str(item.get("surface") or "") == "ask_feishu_aily" and str(item.get("status") or "") == "ready"
        for item in surfaces
        if isinstance(item, dict)
    )
    counts = remote_evidence_counts(source_map)
    interview_answered = answered_interview_count(interview_responses)
    interview_progress = summarize_round_one_interview(interview_responses)
    blocking_gates: list[str] = []
    ai_only_closure_ready = counts["doc_like"] >= 2 and counts["trace_like"] >= 1
    if counts["doc_like"] < 2:
        blocking_gates.append("need_more_feishu_doc_reads")
    if counts["trace_like"] < 1:
        blocking_gates.append("need_more_collaboration_trace")
    if not interview_progress["round_one_complete"]:
        if interview_progress["kb_round_one_attempted"] and interview_progress["subjective_gap_ids"]:
            blocking_gates.append("need_user_micro_interview")
        elif not ai_only_closure_ready:
            if not aily_ready and interview_answered == 0:
                blocking_gates.append("need_kb_round_one_interview")
            elif interview_progress["kb_round_one_attempted"]:
                blocking_gates.append("need_more_interview_quality")
    if not collaboration_protocol_ready:
        blocking_gates.append("missing_collaboration_protocol")
    if browser_ready and not blocking_gates:
        status = "pass_mvp"
    elif browser_ready or aily_ready:
        status = "needs_more_sources"
    else:
        status = "blocked_system"
    pending_seed_titles = []
    for item in seed_map or []:
        if str(item.get("auth_status") or "") != "ready":
            pending_seed_titles.append(str(item.get("title") or item.get("url") or ""))
    next_seeds = pending_seed_titles[:3] or [
        "原力OS",
        "SOUL-递归日志-AI管家",
        "技能盘点",
    ]
    return {
        "status": status,
        "enhancer_status": "ready" if aily_ready else "enhancer_unavailable",
        "blocking_gates": blocking_gates,
        "remote_evidence": counts,
        "interview_answered_count": interview_answered,
        "interview_summary": interview_progress,
        "ai_only_closure_ready": ai_only_closure_ready,
        "most_validated_understanding": "用户明显偏好先抓关窍、再追求全局最优，并希望 AI 在长期协作里真正理解自己。",
        "max_misread_risk": "把当前少量样例和本地摘要误写成从认识到现在的全历史理解。",
        "next_seeds": next_seeds,
    }


def build_open_questions(archetype_root: list[dict[str, Any]], human_force: dict[str, Any]) -> list[str]:
    underdetermined = [item["label"] for item in archetype_root if item["status"] == "underdetermined"][:3]
    minimum_human_closure = human_force.get("minimum_human_closure", {}) if isinstance(human_force, dict) else {}
    questions = []
    if underdetermined:
        questions.append(f"在剩余未确认的12原型里，哪些更接近当前真实状态：{', '.join(underdetermined)}？")
    if not minimum_human_closure.get("golden_shadow_anchor"):
        questions.append("哪些具体人物、作品、场景最容易激活你的金色阴影？")
    if not minimum_human_closure.get("overheat_guardrail"):
        questions.append("当你和我高共振时，你最希望我主动补的，是整合、落地、降躁，还是校验？")
    if not human_force.get("interview_ready"):
        questions.append("哪些短答采访最能补齐原型权重、互为投射、阴影激活场景和协作触发点？")
    return questions[:4]


def build_round_one_interview_questions(human_force: dict[str, Any]) -> list[dict[str, Any]]:
    top_underdetermined = [item for item in human_force.get("archetype_root", []) if item["status"] == "underdetermined"][:2]
    candidate_labels = "、".join(item["label"] for item in top_underdetermined) or "其余原型"
    return [
        {
            "id": "archetype-confirm-sage",
            "category": "12原型权重确认",
            "question": "在你当前阶段，`智者` 更像核心驱动力、辅助驱动力，还是阶段性高能？",
            "reason": "确认已给出的高权重种子强度。",
        },
        {
            "id": "archetype-confirm-explorer",
            "category": "12原型权重确认",
            "question": "在你当前阶段，`探索者` 更像核心驱动力、辅助驱动力，还是阶段性高能？",
            "reason": "确认已给出的高权重种子强度。",
        },
        {
            "id": "archetype-gap-check",
            "category": "12原型权重确认",
            "question": f"除了智者/探索者，剩余原型里如果再补 1 个高权重，会更接近 `{candidate_labels}` 中哪一个？",
            "reason": "补齐原型根目录的下一高权重候选。",
        },
        {
            "id": "mutual-projection-help",
            "category": "互为投射体感",
            "question": "当你觉得我最像你、最懂你时，那更像是 `智者式共振` 还是 `探索者式共振`？",
            "reason": "区分高共振的主导模式。",
        },
        {
            "id": "mutual-projection-regulation",
            "category": "互为投射体感",
            "question": "当我们过热时，你最希望我先补哪一种：`整合 / 落地 / 降躁 / 校验`？",
            "reason": "把互为投射转成可执行 guardrail。",
        },
        {
            "id": "shadow-trigger",
            "category": "阴影 / 金色阴影激活场景",
            "question": "什么样的人、事、表达，最容易让你对“低杠杆、低密度”产生强烈排斥？",
            "reason": "定位阴影激活场景。",
        },
        {
            "id": "golden-shadow-trigger",
            "category": "阴影 / 金色阴影激活场景",
            "question": "哪些具体人物、作品或系统，最容易激活你的“金色阴影”赞叹感？",
            "reason": "定位金色阴影投射对象。",
        },
        {
            "id": "collaboration-trigger",
            "category": "高成功率协作触发点",
            "question": "如果只保留一个高成功率触发点，你最希望我每次先做到什么？",
            "reason": "锁定最关键的协作触发器。",
        },
    ][:INTERVIEW_QUESTION_LIMIT]


def build_followup_interview_questions(progress: dict[str, Any]) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    if "mutual-projection-help" in progress.get("subjective_gap_ids", []):
        questions.append(
            {
                "id": "mutual-projection-help",
                "category": "互为投射体感",
                "question": "当你觉得我最像你、最懂你时，那更像是 `智者式共振` 还是 `探索者式共振`？",
                "reason": "这是知识库不一定能替代的主观共振体感，需要你直接定锚。",
            }
        )
    if "mutual-projection-regulation" in progress.get("subjective_gap_ids", []):
        questions.append(
            {
                "id": "mutual-projection-regulation",
                "category": "过热护栏",
                "question": "当我们过热时，你最希望我先补哪一种：`整合 / 落地 / 降躁 / 校验`？",
                "reason": "把高共振的真实护栏交给你亲自确认。",
            }
        )
    if "collaboration-trigger" in progress.get("subjective_gap_ids", []):
        questions.append(
            {
                "id": "collaboration-trigger",
                "category": "高成功率协作触发点",
                "question": "如果只保留一个高成功率触发点，你最希望我每次先做到什么？",
                "reason": "知识库能给模式，但这条最关键触发点需要你的主观定版。",
            }
        )
    return questions[:FOLLOWUP_INTERVIEW_QUESTION_LIMIT]


def build_interview_questions(
    human_force: dict[str, Any],
    existing_responses: list[dict[str, Any]],
    source_map: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    round_one_questions = build_round_one_interview_questions(human_force)
    progress = summarize_round_one_interview(existing_responses)
    if progress["round_one_complete"]:
        return round_one_questions, {
            "round": 1,
            "question_limit": INTERVIEW_QUESTION_LIMIT,
            "status": "completed_no_followup_needed",
        }
    if progress["kb_round_one_attempted"]:
        followup_questions = build_followup_interview_questions(progress)
        if followup_questions:
            return followup_questions, {
                "round": 2,
                "question_limit": FOLLOWUP_INTERVIEW_QUESTION_LIMIT,
                "status": "user_micro_active",
            }
        return [], {
            "round": 1,
            "question_limit": 0,
            "status": "knowledge_base_round_one_incomplete",
        }
    counts = remote_evidence_counts(source_map)
    if counts["doc_like"] >= 2 and counts["trace_like"] >= 1:
        return [], {
            "round": 1,
            "question_limit": 0,
            "status": "ai_only_closure_ready",
        }
    return round_one_questions, {
        "round": 1,
        "question_limit": INTERVIEW_QUESTION_LIMIT,
        "status": "round_one_active",
    }


def render_interview_pack(questions: list[dict[str, Any]], metadata: dict[str, Any]) -> str:
    lines = [
        "# Interview Pack",
        "",
        f"- round: `{metadata.get('round', 1)}`",
        f"- status: `{metadata.get('status', 'round_one_active')}`",
        f"- question_limit: `{metadata.get('question_limit', INTERVIEW_QUESTION_LIMIT)}`",
        "- note: 短答优先，不需要长作文；只回答最贴近当下真实状态的内容。",
        "",
        "## Questions",
        "",
    ]
    if not questions:
        lines.extend(
            [
                "## Questions",
                "",
                "- No human short-answer questions are active right now; current gap remains on the knowledge-base side.",
                "",
            ]
        )
        return "\n".join(lines)
    for idx, item in enumerate(questions, start=1):
        lines.append(f"{idx}. [{item['category']}] {item['question']}")
        lines.append(f"   - why: {item['reason']}")
    return "\n".join(lines) + "\n"


def parse_worklog_sections(worklog_text: str) -> dict[str, str]:
    sections = {}
    current = None
    buffer: list[str] = []
    for line in worklog_text.splitlines():
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(buffer).strip()
            current = line[3:].strip()
            buffer = []
        else:
            buffer.append(line)
    if current is not None:
        sections[current] = "\n".join(buffer).strip()
    return sections


def synthesize_dual_force(args: argparse.Namespace) -> int:
    run_dir = ensure_run_dir(args.run_dir)
    corrections = read_json(run_dir / "user-corrections.json", default=[])
    source_map = read_json(run_dir / "source-map.json", default={})
    source_map = sync_interview_helper_sources(run_dir, source_map)
    write_json(run_dir / "source-map.json", source_map)
    sources = load_sources(run_dir)
    corpus = "\n".join(source["text"] for source in sources if source["text"])
    auth_manifest = read_json(run_dir / "auth-manifest.json", default=empty_auth_manifest(now_local()))
    seed_map = read_json(run_dir / "seed-source-map.json", default=[])
    existing_responses = load_interview_responses(run_dir / "interview-responses.json")
    minimum_closure_payload = load_minimum_closure_responses(run_dir / "minimum-closure-responses.json")
    minimum_human_closure = summarize_minimum_human_closure(minimum_closure_payload)
    signals = detect_signals(corpus, sources)
    ai_force = build_ai_force(signals)
    human_force = build_human_force(signals, corrections, sources, minimum_human_closure)
    mutual_projection_map = build_mutual_projection_map(ai_force, human_force)
    bridge_rules = build_bridge_rules(ai_force, human_force, signals, sources)
    knowledge_answers = extract_ingested_interview_answers(source_map)
    round_one_seed_responses = merge_interview_responses(
        existing_responses,
        build_round_one_interview_questions(human_force),
        knowledge_answers=knowledge_answers,
    )
    interview_questions, interview_pack_meta = build_interview_questions(human_force, round_one_seed_responses, source_map)
    write_text(run_dir / "interview-pack.md", render_interview_pack(interview_questions, interview_pack_meta))
    merged_responses = merge_interview_responses(existing_responses, interview_questions, knowledge_answers=knowledge_answers)
    merged_responses = apply_minimum_closure_overlay(
        merged_responses,
        minimum_human_closure,
        evidence_ref=str(run_dir / "minimum-closure-responses.json"),
    )
    write_json(run_dir / "interview-responses.json", {"responses": merged_responses})
    source_map = sync_interview_helper_sources(run_dir, read_json(run_dir / "source-map.json", default={}))
    write_json(run_dir / "source-map.json", source_map)
    sources = load_sources(run_dir)
    interview_progress = summarize_round_one_interview(merged_responses)
    kb_evidence = knowledge_base_mediated_evidence(merged_responses)
    human_force["knowledge_base_mediated_evidence"] = kb_evidence
    human_force["interview_ready"] = bool(
        answered_interview_count(merged_responses)
        or interview_progress["round_one_complete"]
        or minimum_human_closure.get("complete")
    )
    human_force["minimum_human_closure"] = minimum_human_closure

    source_refs = [
        {
            "title": source["title"],
            "ref": source["ref"],
            "type": source["type"],
            "source_surface": source.get("source_surface", source["type"]),
            "access_path": source.get("access_path", infer_access_path(str(source.get("source_surface") or source["type"]))),
            "auth_status": source.get("auth_status", "unknown"),
        }
        for source in sources
    ]
    verdict = build_mvp_verdict(
        source_map=source_map,
        auth_manifest=auth_manifest,
        source_refs=source_refs,
        interview_responses=merged_responses,
        collaboration_protocol_ready=True,
        seed_map=seed_map,
    )
    interview_deltas = [
        {
            "id": str(item.get("id") or ""),
            "category": str(item.get("category") or ""),
            "status": str(item.get("status") or ""),
            "response_source": normalize_response_source(item.get("response_source"), answer=str(item.get("answer") or "").strip()),
            "answer_quality": normalize_answer_quality(
                item.get("answer_quality"),
                answer=str(item.get("answer") or "").strip(),
                response_source=normalize_response_source(item.get("response_source"), answer=str(item.get("answer") or "").strip()),
            ),
            "evidence_ref": str(item.get("evidence_ref") or ""),
        }
        for item in merged_responses
    ]
    open_questions = build_open_questions(human_force["archetype_root"], human_force)
    memory_packet = {
        "profile_version": "v4",
        "updated_at": now_local().isoformat(),
        "ai_force": ai_force,
        "human_force": human_force,
        "bridge_rules": bridge_rules,
        "collaboration_preferences": {
            "interaction_style": "high-autonomy, leverage-first, long-context",
            "proof_threshold": "show evidence for strong claims and mark low confidence explicitly",
        },
        "current_phase": derive_current_phase(verdict, interview_progress, minimum_human_closure),
        "minimum_human_closure": minimum_human_closure,
        "archetype_root": human_force["archetype_root"],
        "mutual_projection_map": mutual_projection_map,
        "interview_deltas": interview_deltas,
        "user_validated_seeds": human_force["user_validated_seeds"],
        "shadow_map": human_force["shadow"],
        "golden_shadow_map": human_force["golden_shadow"],
        "integration_tasks": human_force["integration_tasks"],
        "confidence_conditions": {
            "current_level": "provisional" if len(source_refs) <= 2 else "repeated",
            "user_corrections_applied": corrections,
            "needs_more_feishu_seeds": len(seed_map) == 0,
            "auth_manifest_present": bool(auth_manifest.get("surfaces")),
            "interview_question_limit": INTERVIEW_QUESTION_LIMIT,
            "interview_round": interview_pack_meta["round"],
            "interview_summary": interview_progress,
            "minimum_human_closure": minimum_human_closure,
            "knowledge_base_interview_completed": interview_progress["round_one_complete"],
            "knowledge_base_mediated_count": len(kb_evidence),
            "remote_evidence": remote_evidence_counts(source_map),
        },
        "open_questions": open_questions,
        "source_refs": source_refs,
        "mvp_verdict": verdict,
    }

    write_text(run_dir / "source-digest.md", render_source_digest(sources, signals, merged_responses))
    write_text(run_dir / "ai-force-model.md", render_ai_force(ai_force))
    write_text(run_dir / "human-force-profile.md", render_human_force(human_force))
    write_text(run_dir / "dual-force-bridge.md", render_bridge(bridge_rules, human_force))
    write_text(run_dir / "collaboration-protocol.md", render_protocol(bridge_rules, human_force))
    write_json(run_dir / "memory-packet.json", memory_packet)

    remote_ready = sum(
        1
        for item in source_map.get("ingested_sources", [])
        if str(item.get("access_path") or "") in {"browser_session", "open_platform_api"} and str(item.get("auth_status") or "") == "ready"
    )
    source_coverage = "mvp_baseline_local_only" if remote_ready == 0 else "remote_enriched"
    gained = "Built a v3 dual-force packet with 12-archetype root, mutual-projection bridge, and an 8-question interview pack that can deepen the next round without high interruption."
    wasted = "Historical coverage is still partial; archetype root beyond sage/explorer, shadow specifics, and long-horizon collaboration history remain constrained by current Feishu evidence and unanswered interview slots."
    next_iterate = "Use ready auth surfaces to ingest high-value Feishu seeds, collect short answers for the 8-question interview pack, then rerun synthesis so the archetype root and mutual-projection map move from seed to stronger evidence."
    worklog = (
        "# Worklog\n\n"
        "## Run\n\n"
        f"- run_dir: `{run_dir}`\n"
        f"- sources_loaded: `{len(source_refs)}`\n"
        f"- source_coverage: `{source_coverage}`\n"
        f"- synthesis_time: `{now_local().isoformat()}`\n\n"
        "## Verification\n\n"
        "- source digest generated\n"
        "- dual-force models generated\n"
        "- interview pack refreshed\n"
        "- collaboration protocol emitted\n"
        "- memory packet updated\n\n"
        "## MVP Verdict\n\n"
        f"- status: `{verdict['status']}`\n"
        f"- 最强已验证理解: {verdict['most_validated_understanding']}\n"
        f"- 当前最大误读风险: {verdict['max_misread_risk']}\n"
        f"- 下一轮最值得加的 3 个种子: {', '.join(verdict['next_seeds'])}\n\n"
        "## Gained\n\n"
        f"- {gained}\n\n"
        "## Wasted\n\n"
        f"- {wasted}\n\n"
        "## Next Iterate\n\n"
        f"- {next_iterate}\n"
    )
    write_text(run_dir / "worklog.md", worklog)

    print(f"updated: {run_dir / 'memory-packet.json'}")
    return 0


def prepare_governance_mirror(args: argparse.Namespace) -> int:
    run_dir = ensure_run_dir(args.run_dir)
    input_payload = read_json(run_dir / "input.json", default={})
    memory_packet = read_json(run_dir / "memory-packet.json", default={})
    worklog_sections = parse_worklog_sections(read_text(run_dir / "worklog.md"))
    selected_rules = [rule["adaptation"] for rule in memory_packet.get("bridge_rules", [])[:5]]
    verdict = memory_packet.get("mvp_verdict", {})
    summary = (
        "Built a dual-force packet that pairs machine-side recursion/global-optimum rules "
        "with the user's leverage-seeking, personalized-AI, and integration-oriented human force."
    )
    mirror_payload = {
        "run_id": input_payload.get("run_id", run_dir.name),
        "verdict": verdict.get("status", "needs_more_sources"),
        "summary": summary,
        "gained": worklog_sections.get("Gained", "").replace("- ", "").strip(),
        "wasted": worklog_sections.get("Wasted", "").replace("- ", "").strip(),
        "next_iterate": worklog_sections.get("Next Iterate", "").replace("- ", "").strip(),
        "selected_rules": selected_rules,
    }
    write_json(run_dir / "mirror-summary.json", mirror_payload)
    print(f"updated: {run_dir / 'mirror-summary.json'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Operate the yuanli-juexing dual-force skill.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-run", help="Create a new dual-force run scaffold.")
    init_parser.add_argument("--topic", required=True)
    init_parser.add_argument("--note")
    init_parser.add_argument("--run-id")
    init_parser.add_argument("--source-file", action="append")
    init_parser.set_defaults(func=init_run)

    ingest_doc = subparsers.add_parser("ingest-feishu-doc", help="Ingest one Feishu wiki/doc seed.")
    ingest_doc.add_argument("--run-dir", required=True)
    ingest_doc.add_argument("--url", required=True)
    ingest_doc.add_argument("--title")
    ingest_doc.add_argument("--priority", default="medium")
    ingest_doc.add_argument("--reason", default="user-provided seed source")
    ingest_doc.add_argument("--headed", action="store_true")
    ingest_doc.add_argument("--reuse-chrome-profile", action="store_true")
    ingest_doc.set_defaults(func=ingest_feishu_doc)

    ingest_ask = subparsers.add_parser("ingest-ask-feishu", help="Ingest one ask.feishu/Aily seed.")
    ingest_ask.add_argument("--run-dir", required=True)
    ingest_ask.add_argument("--question", required=True)
    ingest_ask.add_argument("--title")
    ingest_ask.add_argument("--priority", default="medium")
    ingest_ask.add_argument("--reason", default="user-provided ask.feishu seed")
    ingest_ask.add_argument("--app-id")
    ingest_ask.add_argument("--artifact-subdir")
    ingest_ask.add_argument("--interview-question-id")
    ingest_ask.add_argument("--response-source")
    ingest_ask.set_defaults(func=ingest_ask_feishu)

    minimum_prepare = subparsers.add_parser(
        "prepare-minimum-closure",
        help="Refresh the fixed 5-question minimum human closure pack and normalize its response file.",
    )
    minimum_prepare.add_argument("--run-dir", required=True)
    minimum_prepare.set_defaults(func=prepare_minimum_closure)

    minimum_record = subparsers.add_parser(
        "record-minimum-closure",
        help="Record the 5 short human answers used to finish the first-collaboration minimum closure.",
    )
    minimum_record.add_argument("--run-dir", required=True)
    minimum_record.add_argument("--answers-file", required=True)
    minimum_record.set_defaults(func=record_minimum_closure)

    synthesize = subparsers.add_parser("synthesize-dual-force", help="Build the dual-force packet.")
    synthesize.add_argument("--run-dir", required=True)
    synthesize.set_defaults(func=synthesize_dual_force)

    mirror = subparsers.add_parser("prepare-governance-mirror", help="Write the privacy-safe governance mirror summary.")
    mirror.add_argument("--run-dir", required=True)
    mirror.set_defaults(func=prepare_governance_mirror)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
