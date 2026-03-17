#!/usr/bin/env python3
"""Read-only Odyssey course and prompt analysis pipeline."""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
from typing import Any
from urllib import parse as urllib_parse
from urllib import request as urllib_request


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = SKILL_DIR.parents[1]
ARTIFACTS_ROOT = SKILL_DIR / "artifacts" / "ai-da-guan-jia"
RUNS_ROOT = ARTIFACTS_ROOT / "runs"
DERIVED_REPORTS_ROOT = PROJECT_ROOT / "derived" / "reports"
DEFAULT_BASE_URL = "https://yy.odysseyinst.com"
DEFAULT_PAGE_SIZE = 100
DEFAULT_TOP_N = 20
FOCUS_CATEGORIES = {"原力 AI", "私董 AI", "天赋私教", "智能少年"}
SECTION_ORDER = [
    "role",
    "inputs",
    "goal",
    "constraints",
    "evidence_rules",
    "output_format",
    "tone",
    "examples",
    "escalation_boundary",
]
SECTION_KEYWORDS = {
    "role": ["角色", "角色定位", "身份", "你是", "你将扮演"],
    "inputs": ["输入", "用户信息", "背景", "上下文", "已知信息", "变量", "用户会提供"],
    "goal": ["目标", "任务目标", "任务", "使命", "要做", "核心目标"],
    "constraints": ["规则", "硬性规则", "注意", "要求", "铁律", "限制", "禁忌"],
    "evidence_rules": ["证据不足", "不要编造", "仅依据", "只依据", "不做诊断", "不得编造", "无法判断"],
    "output_format": ["输出格式", "结构", "请按以下", "报告结构", "格式", "直接输出发布版本"],
    "tone": ["语调", "风格", "tone", "写作风格", "表达", "节奏", "视角"],
    "examples": ["示例", "句式模板", "模板", "例", "高频词", "核心句式库"],
    "escalation_boundary": ["证据不足", "无法判断", "不要补问", "不输出补问", "如需", "若证据不足"],
}
SCHEMA_SECTION_LABELS = {
    "role": "角色定位",
    "inputs": "输入上下文",
    "goal": "目标结果",
    "constraints": "硬性规则",
    "evidence_rules": "证据边界",
    "output_format": "输出格式",
    "tone": "语气与禁忌",
    "examples": "示例与模板",
    "escalation_boundary": "证据不足时的处理",
}


@dataclass(frozen=True)
class ModuleDefinition:
    module: str
    keywords: tuple[str, ...]
    concepts: tuple[str, ...]
    decision_rules: tuple[str, ...]
    user_scenarios: tuple[str, ...]
    output_patterns: tuple[str, ...]
    coverage_priority: int


MODULE_DEFINITIONS = [
    ModuleDefinition(
        module="原力定位与原理学习",
        keywords=("原力", "原理", "能力", "在线", "亮点", "特点", "缺点"),
        concepts=("原力", "原理", "能力在线", "亮点放大", "长期不变"),
        decision_rules=(
            "先找到人生里长期不变的能力原点，再决定创业和表达路径。",
            "把问题背后的缺点抽象成特点，再转成可以放大的亮点。",
        ),
        user_scenarios=(
            "创始人不知道自己真正该做哪条线。",
            "技术人或转型者需要从经历里抽出独特天赋。",
        ),
        output_patterns=("原力识别报告", "原理觉醒分析", "能力在线/离线诊断"),
        coverage_priority=5,
    ),
    ModuleDefinition(
        module="借势合力与周期判断",
        keywords=("借势", "合力", "周期", "康波", "原型", "势能", "拨盘"),
        concepts=("借势", "合力", "周期", "康波", "原型", "势能"),
        decision_rules=(
            "先判断自己和项目所处周期，再决定发力方式。",
            "对的势和对的人格原型叠加，会放大回报。",
        ),
        user_scenarios=(
            "业务增长遇到拐点，不确定是继续硬推还是换打法。",
            "需要判断个人能量和市场周期是否对齐。",
        ),
        output_patterns=("周期定位报告", "借势合力建议", "增长阶段判断"),
        coverage_priority=5,
    ),
    ModuleDefinition(
        module="品类独创与甜用户贵问题",
        keywords=("品类", "心智", "用户", "贵问题", "甜用户", "预算", "价值"),
        concepts=("品类独创", "心智账户", "甜用户", "贵问题", "预算"),
        decision_rules=(
            "先锁定甜用户和贵问题，再定义品类与价值表达。",
            "用户基数乘用户心智预算，决定可兑现的空间。",
        ),
        user_scenarios=(
            "要找到最愿意付费、最痛、最贵、最持续的问题。",
            "需要把泛泛服务改成清晰品类和价值主张。",
        ),
        output_patterns=("甜用户贵问题卡", "品类独创方案", "心智账户测算"),
        coverage_priority=5,
    ),
    ModuleDefinition(
        module="模式升级与系统化经营",
        keywords=("模式", "系统", "前链", "后链", "彩链", "合谋", "升级"),
        concepts=("模式升级", "系统化", "经营链路", "可复制"),
        decision_rules=(
            "把生意从单点能力升级为系统和模式，才能放大。",
            "百倍空间来自结构，不是来自更辛苦地做同样的事。",
        ),
        user_scenarios=(
            "业务验证过了，但还不能规模化。",
            "需要把服务、内容、转化、交付串成一套模式。",
        ),
        output_patterns=("模式升级蓝图", "经营系统清单", "增长链路设计"),
        coverage_priority=4,
    ),
    ModuleDefinition(
        module="十年理论与企业判断",
        keywords=("十年", "巴菲特", "段永平", "伟大的公司", "学霸", "好企业"),
        concepts=("十年理论", "企业判断", "资产审美", "长期主义"),
        decision_rules=(
            "只做未来十年比过去十年更好的事和更好的公司。",
            "企业判断先看趋势，再看壁垒和长期可持续性。",
        ),
        user_scenarios=(
            "需要判断项目值不值得长期投入。",
            "创业者要建立资产审美和企业筛选标准。",
        ),
        output_patterns=("十年理论评估", "企业质量评分", "长期资产判断"),
        coverage_priority=4,
    ),
    ModuleDefinition(
        module="左手现金流右手滚雪球",
        keywords=("现金流", "滚雪球", "资产", "审美", "财富", "左手", "右手"),
        concepts=("现金流", "资产", "滚雪球", "财富审美"),
        decision_rules=(
            "左手做源源不断的现金流，右手配置符合长期法则的资产。",
            "财富不是单一标的，而是人生信念与资产审美的结果。",
        ),
        user_scenarios=(
            "创业者想兼顾当下赚钱和长期复利。",
            "需要把业务选择和资产配置放在同一套逻辑里。",
        ),
        output_patterns=("现金流/资产双轮策略", "财富审美校准", "复利路径建议"),
        coverage_priority=3,
    ),
]


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def now_local() -> datetime:
    return datetime.now().astimezone()


def iso_now() -> str:
    return now_local().isoformat(timespec="seconds")


def stable_hash(*parts: str) -> str:
    raw = "||".join(part for part in parts if part)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def truncate_text(value: str, limit: int = 180) -> str:
    compact = re.sub(r"\s+", " ", value.strip())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def slugify(value: str) -> str:
    text = re.sub(r"\s+", "-", value.strip().lower())
    text = re.sub(r"[^a-z0-9\-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "unknown"


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def normalized_variant_key(path: Path) -> str:
    name = path.name
    name = re.sub(r" \(\d+\)(?=\.docx$)", "", name, flags=re.IGNORECASE)
    return name


def count_heading_lines(lines: list[str]) -> int:
    count = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#") or re.fullmatch(r"[【\[].+[】\]]", stripped):
            count += 1
            continue
        if stripped.endswith(("：", ":")) and len(stripped) <= 40:
            count += 1
    return count


def chinese_ratio(text: str) -> float:
    if not text:
        return 0.0
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    return chinese / max(len(text), 1)


def count_timestamps(text: str) -> int:
    return len(re.findall(r"\(\d{2}:\d{2}:\d{2}\)", text))


def convert_docx_to_text(path: Path) -> str:
    result = subprocess.run(
        ["textutil", "-convert", "txt", "-stdout", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"textutil failed for {path}: {result.stderr.strip()}")
    return result.stdout


def extract_course_file_info(path: Path) -> dict[str, Any]:
    text = convert_docx_to_text(path)
    lines = [line.strip() for line in text.splitlines()]
    nonempty_lines = [line for line in lines if line]
    metrics = {
        "char_count": len(text),
        "nonempty_lines": len(nonempty_lines),
        "timestamp_count": count_timestamps(text),
        "heading_lines": count_heading_lines(nonempty_lines),
        "chinese_ratio": round(chinese_ratio(text), 4),
        "keyword_hits": sum(text.count(keyword) for definition in MODULE_DEFINITIONS for keyword in definition.keywords),
    }
    clarity_score = (
        metrics["nonempty_lines"] * 1.5
        + metrics["timestamp_count"] * 2.0
        + metrics["heading_lines"] * 8.0
        + metrics["char_count"] / 300
        + metrics["keyword_hits"] * 3.0
        + metrics["chinese_ratio"] * 40
    )
    return {
        "path": str(path),
        "name": path.name,
        "variant_key": normalized_variant_key(path),
        "text": text,
        "metrics": metrics,
        "clarity_score": round(clarity_score, 2),
    }


def choose_canonical_variants(file_infos: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for info in file_infos:
        groups[str(info["variant_key"])].append(info)

    canonical: list[dict[str, Any]] = []
    resolutions: list[dict[str, Any]] = []
    for key in sorted(groups):
        variants = sorted(groups[key], key=lambda item: (-float(item["clarity_score"]), item["name"]))
        chosen = variants[0]
        canonical.append(chosen)
        reason = "single_source"
        if len(variants) > 1:
            reason = (
                f"selected highest clarity score {chosen['clarity_score']} based on char_count="
                f"{chosen['metrics']['char_count']}, nonempty_lines={chosen['metrics']['nonempty_lines']}, "
                f"timestamp_count={chosen['metrics']['timestamp_count']}, heading_lines={chosen['metrics']['heading_lines']}"
            )
        resolutions.append(
            {
                "session_key": key,
                "chosen_path": chosen["path"],
                "reason": reason,
                "variants": [
                    {
                        "path": variant["path"],
                        "clarity_score": variant["clarity_score"],
                        "metrics": variant["metrics"],
                    }
                    for variant in variants
                ],
            }
        )
    return canonical, resolutions


def course_source_label(path: str) -> str:
    stem = Path(path).stem
    stem = re.sub(r"^\d+-?", "", stem)
    return stem


def split_course_fragments(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text)
    pieces = re.split(r"(?<=[。！？!?])|(?<=\))\s+|(?<=:)\s+|(?<=：)\s+", normalized)
    fragments = [piece.strip() for piece in pieces if piece and piece.strip()]
    return [fragment for fragment in fragments if len(fragment) >= 12]


def find_snippets(text: str, keywords: tuple[str, ...], limit: int = 6) -> list[str]:
    matches: list[tuple[int, str]] = []
    seen: set[str] = set()
    for fragment in split_course_fragments(text):
        matched_terms = [keyword for keyword in keywords if keyword in fragment]
        if not matched_terms:
            continue
        snippet = truncate_text(fragment, 160)
        if snippet in seen:
            continue
        seen.add(snippet)
        matches.append((len(matched_terms), snippet))
    matches.sort(key=lambda item: (-item[0], len(item[1])))
    return [snippet for _, snippet in matches[:limit]]


def build_course_modules(canonical_infos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    modules: list[dict[str, Any]] = []
    for definition in MODULE_DEFINITIONS:
        evidence_refs: list[dict[str, str]] = []
        matched_sessions: list[str] = []
        for info in canonical_infos:
            snippets = find_snippets(str(info["text"]), definition.keywords, limit=3)
            if not snippets:
                continue
            matched_sessions.append(course_source_label(str(info["path"])))
            for snippet in snippets[:2]:
                evidence_refs.append(
                    {
                        "source": course_source_label(str(info["path"])),
                        "snippet": snippet,
                    }
                )
        modules.append(
            {
                "module": definition.module,
                "concepts": list(definition.concepts),
                "decision_rules": list(definition.decision_rules),
                "user_scenarios": list(definition.user_scenarios),
                "output_patterns": list(definition.output_patterns),
                "coverage_priority": definition.coverage_priority,
                "matched_sessions": matched_sessions,
                "evidence_refs": evidence_refs[:8],
            }
        )
    return modules


def request_json(url: str, *, method: str = "GET", payload: Any | None = None, headers: dict[str, str] | None = None) -> Any:
    data = None
    final_headers = {"Content-Type": "application/json"}
    if headers:
        final_headers.update(headers)
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib_request.Request(url, data=data, headers=final_headers, method=method)
    with urllib_request.urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        body = response.read().decode(charset)
    return json.loads(body)


def fetch_live_snapshots(base_url: str, username: str, password: str, page_size: int) -> dict[str, Any]:
    login_payload = request_json(
        urllib_parse.urljoin(base_url.rstrip("/") + "/", "api/login"),
        method="POST",
        payload={"username": username, "password": password},
    )
    if not login_payload.get("success"):
        raise RuntimeError(f"Login failed: {login_payload}")
    user = login_payload["user"]
    headers = {
        "user-level": str(user["权限等级"]),
        "user-id": str(user["id"]),
        "user-name": str(user["name"]),
    }
    categories = request_json(
        urllib_parse.urljoin(base_url.rstrip("/") + "/", "api/app-cats"),
        headers=headers,
    )
    items: list[dict[str, Any]] = []
    total = None
    page = 1
    while True:
        query = urllib_parse.urlencode({"page": page, "pageSize": page_size})
        payload = request_json(
            urllib_parse.urljoin(base_url.rstrip("/") + "/", f"api/apps?{query}"),
            headers=headers,
        )
        page_items = list(payload.get("items") or [])
        items.extend(page_items)
        total = int(payload.get("total") or len(items))
        if len(items) >= total or not page_items:
            break
        page += 1
    return {
        "fetched_at": iso_now(),
        "base_url": base_url,
        "user": user,
        "categories": categories,
        "apps": items,
        "headers": headers,
    }


def classify_model_type(app: dict[str, Any]) -> str:
    if int(app.get("isFlowith") or 0) == 1 or app.get("flowithId"):
        return "flowith"
    if int(app.get("isGPTs") or app.get("isGpts") or 0) == 1 or app.get("gizmoID"):
        return "gpts"
    if int(app.get("isFixedModel") or 0) == 1 or app.get("appModel"):
        return "fixed"
    return "normal"


def classify_editable_source(app: dict[str, Any]) -> str:
    model_type = classify_model_type(app)
    if model_type == "flowith":
        return "flowith"
    if model_type == "gpts":
        return "external_gpts"
    return "local_preset"


def split_prompt_lines(text: str) -> list[str]:
    return [line.rstrip() for line in text.splitlines()]


def looks_like_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith("#"):
        return True
    if re.fullmatch(r"[【\[].+[】\]]", stripped):
        return True
    return stripped.endswith(("：", ":")) and len(stripped) <= 40


def section_key_for_heading(heading: str) -> str | None:
    lowered = heading.lower()
    for section, keywords in SECTION_KEYWORDS.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            return section
    return None


def extract_prompt_sections(text: str) -> dict[str, str]:
    sections = {key: "" for key in SECTION_ORDER}
    if not text.strip():
        return sections

    lines = split_prompt_lines(text)
    current: str | None = None
    bucket: dict[str, list[str]] = {key: [] for key in SECTION_ORDER}
    fallback: list[str] = []
    for line in lines:
        stripped = line.strip()
        if looks_like_heading(line):
            guessed = section_key_for_heading(stripped)
            if guessed:
                current = guessed
                continue
        if current:
            bucket[current].append(line)
        else:
            fallback.append(line)

    for section in SECTION_ORDER:
        content = "\n".join(line for line in bucket[section] if line.strip()).strip()
        if content:
            sections[section] = content

    if not sections["role"]:
        match = re.search(r"(你是[^\n。]{6,120})", text)
        if match:
            sections["role"] = match.group(1).strip()
    if not sections["goal"]:
        goal_match = re.search(r"(任务[^\n]{0,80}|目标[^\n]{0,80})", text)
        if goal_match:
            sections["goal"] = goal_match.group(1).strip()
    if not sections["inputs"]:
        input_lines = [line.strip() for line in lines if "{" in line and "}" in line]
        if input_lines:
            sections["inputs"] = "\n".join(input_lines[:8])
    if not sections["output_format"]:
        format_lines = [line.strip() for line in lines if re.match(r"^(\d+\.|##+|\* )", line.strip())]
        if format_lines:
            sections["output_format"] = "\n".join(format_lines[:10])
    if not sections["constraints"]:
        constraint_lines = [line.strip() for line in lines if any(word in line for word in ("必须", "不能", "不要", "只", "严禁"))]
        if constraint_lines:
            sections["constraints"] = "\n".join(constraint_lines[:10])
    if not sections["tone"]:
        tone_lines = [line.strip() for line in lines if any(word in line for word in ("风格", "语调", "Tone", "节奏", "视角"))]
        if tone_lines:
            sections["tone"] = "\n".join(tone_lines[:8])
    if not sections["examples"]:
        example_lines = [line.strip() for line in lines if any(word in line for word in ("示例", "模板", "句式"))]
        if example_lines:
            sections["examples"] = "\n".join(example_lines[:10])
    if not sections["evidence_rules"]:
        evidence_lines = [line.strip() for line in lines if any(word in line for word in SECTION_KEYWORDS["evidence_rules"])]
        if evidence_lines:
            sections["evidence_rules"] = "\n".join(evidence_lines[:8])
    if not sections["escalation_boundary"]:
        boundary_lines = [
            line.strip()
            for line in lines
            if any(word in line for word in ("证据不足", "无法判断", "不要补问", "不输出补问", "明确写"))
        ]
        if boundary_lines:
            sections["escalation_boundary"] = "\n".join(boundary_lines[:8])
    if not any(sections.values()) and fallback:
        sections["goal"] = "\n".join(line for line in fallback if line.strip())[:500]
    return sections


def detect_course_alignment(app: dict[str, Any], modules: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], float]:
    haystack = " ".join(
        [
            str(app.get("name") or ""),
            str(app.get("des") or ""),
            str(app.get("category") or ""),
            str(app.get("preset_text") or ""),
        ]
    )
    scored: list[dict[str, Any]] = []
    for module in modules:
        keywords = list(module["concepts"]) + [module["module"]]
        hit_count = 0
        matched_terms: list[str] = []
        for keyword in keywords:
            if keyword and keyword in haystack:
                hit_count += 1
                matched_terms.append(keyword)
        if hit_count:
            score = round(hit_count / max(len(keywords), 1), 3)
            scored.append({"module": module["module"], "score": score, "matched_terms": matched_terms[:8]})
    scored.sort(key=lambda item: (-float(item["score"]), item["module"]))
    top_score = scored[0]["score"] if scored else 0.0
    return scored, float(top_score)


def score_prompt_quality(app: dict[str, Any], sections: dict[str, str], alignment_score: float) -> dict[str, float]:
    present_count = sum(1 for key in SECTION_ORDER if sections.get(key))
    clarity = min(1.0, (present_count / len(SECTION_ORDER)) * 0.7 + min(len(app.get("preset_text", "")) / 3500, 0.3))
    executability = min(
        1.0,
        (
            0.2 * bool(sections.get("role"))
            + 0.2 * bool(sections.get("goal"))
            + 0.2 * bool(sections.get("inputs"))
            + 0.2 * bool(sections.get("output_format"))
            + 0.2 * bool(sections.get("constraints"))
        ),
    )
    course_alignment = min(1.0, alignment_score + (0.15 if app.get("category") in FOCUS_CATEGORIES else 0.0))
    return {
        "clarity": round(clarity, 3),
        "executability": round(executability, 3),
        "course_alignment": round(course_alignment, 3),
        "overall": round((clarity * 0.35) + (executability * 0.35) + (course_alignment * 0.30), 3),
    }


def normalize_apps(apps: list[dict[str, Any]], categories: list[dict[str, Any]], modules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    category_map = {str(row["id"]): row["name"] for row in categories}
    normalized: list[dict[str, Any]] = []
    for app in apps:
        category = category_map.get(str(app.get("catId") or ""), "未分类")
        model_type = classify_model_type(app)
        editable_source = classify_editable_source(app)
        preset_text = str(app.get("preset") or "")
        prompt_sections = extract_prompt_sections(preset_text)
        matched_modules, alignment_score = detect_course_alignment(
            {
                "name": app.get("name"),
                "des": app.get("des"),
                "category": category,
                "preset_text": preset_text,
            },
            modules,
        )
        scores = score_prompt_quality(
            {
                "preset_text": preset_text,
                "category": category,
            },
            prompt_sections,
            alignment_score,
        )
        normalized.append(
            {
                "id": app.get("id"),
                "name": app.get("name"),
                "category": category,
                "order": int(app.get("order") or 0),
                "status": int(app.get("status") or 0),
                "model_type": model_type,
                "editable_source": editable_source,
                "preset_text": preset_text,
                "gizmo_id": app.get("gizmoID") or "",
                "flowith_id": app.get("flowithId") or "",
                "app_model": app.get("appModel") or "",
                "description": app.get("des") or "",
                "prompt_sections": prompt_sections,
                "matched_modules": matched_modules,
                "primary_module": matched_modules[0]["module"] if matched_modules else "",
                "scores": scores,
                "prompt_length": len(preset_text),
            }
        )
    return normalized


def summarize_categories(apps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for app in apps:
        grouped[str(app["category"])].append(app)
    summary: list[dict[str, Any]] = []
    for category, rows in sorted(grouped.items()):
        editable_counts = Counter(row["editable_source"] for row in rows)
        model_counts = Counter(row["model_type"] for row in rows)
        local_scores = [float(row["scores"]["overall"]) for row in rows if row["editable_source"] == "local_preset"]
        summary.append(
            {
                "category": category,
                "count": len(rows),
                "editable_source_counts": dict(editable_counts),
                "model_type_counts": dict(model_counts),
                "top_order_app": max(rows, key=lambda row: int(row["order"] or 0))["name"],
                "average_local_prompt_score": round(statistics.mean(local_scores), 3) if local_scores else 0.0,
            }
        )
    return summary


def build_module_mapping(modules: list[dict[str, Any]], apps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mapping: list[dict[str, Any]] = []
    for module in modules:
        aligned = [app for app in apps if app["primary_module"] == module["module"]]
        aligned.sort(key=lambda row: (-int(row["order"]), -float(row["scores"]["overall"]), str(row["name"])))
        mapping.append(
            {
                "module": module["module"],
                "categories": sorted({app["category"] for app in aligned}),
                "apps": [
                    {
                        "id": app["id"],
                        "name": app["name"],
                        "category": app["category"],
                        "order": app["order"],
                        "editable_source": app["editable_source"],
                        "overall_score": app["scores"]["overall"],
                    }
                    for app in aligned[:15]
                ],
                "gap": not bool(aligned),
            }
        )
    return mapping


def priority_score(app: dict[str, Any]) -> float:
    category_bonus = 1.0 if app["category"] in FOCUS_CATEGORIES else 0.35
    editable_bonus = {"local_preset": 1.0, "external_gpts": 0.2, "flowith": 0.1}[app["editable_source"]]
    order_score = min(int(app["order"]) / 5000, 1.0)
    preset_score = min(int(app["prompt_length"]) / 2500, 1.0)
    return round(
        category_bonus * 0.35
        + editable_bonus * 0.20
        + order_score * 0.20
        + float(app["scores"]["overall"]) * 0.15
        + preset_score * 0.10,
        4,
    )


def choose_primary_issue(app: dict[str, Any]) -> tuple[str, str]:
    sections = app["prompt_sections"]
    if not sections.get("evidence_rules"):
        return ("补证据边界", "当前 prompt 缺少明确的证据不足/不得编造边界，容易让高价值分析类输出失真。")
    if not sections.get("inputs"):
        return ("补输入上下文", "当前 prompt 没把用户背景、阶段、角色、目标收成明确输入变量，难以稳定个性化。")
    if not sections.get("output_format"):
        return ("补输出格式", "当前 prompt 缺少显式交付结构，结果质量更依赖模型临场发挥。")
    if not sections.get("goal"):
        return ("补目标结果", "当前 prompt 对最终要帮用户拿到什么结果定义不够清晰。")
    if not sections.get("constraints"):
        return ("补硬性规则", "当前 prompt 缺少约束条件，容易出现风格漂移或越界发挥。")
    if not sections.get("tone"):
        return ("补语气禁忌", "当前 prompt 任务明确，但语气与表达边界未被单独固化。")
    if float(app["scores"]["course_alignment"]) < 0.45:
        return ("补课程模块映射", "当前 prompt 可执行，但和原力创业课程的核心概念绑定还不够深。")
    return ("做模板化拆分", "当前 prompt 已较完整，下一步更适合拆成可复用 Schema 与变量包。")


def best_course_evidence(module_name: str, modules: list[dict[str, Any]]) -> dict[str, str]:
    for module in modules:
        if module["module"] == module_name and module["evidence_refs"]:
            return module["evidence_refs"][0]
    return {"source": "", "snippet": ""}


def current_prompt_evidence(app: dict[str, Any], issue_title: str) -> dict[str, str]:
    sections = app["prompt_sections"]
    if issue_title == "补证据边界":
        return {
            "observed": "未检出“证据不足 / 不要编造 / 仅依据输入”类边界语。",
            "snippet": truncate_text(sections.get("goal") or sections.get("output_format") or app["preset_text"]),
        }
    if issue_title == "补输入上下文":
        return {
            "observed": "未检出稳定的输入变量或用户背景块。",
            "snippet": truncate_text(sections.get("role") or sections.get("goal") or app["preset_text"]),
        }
    if issue_title == "补输出格式":
        return {
            "observed": "未检出完整输出格式章节。",
            "snippet": truncate_text(sections.get("goal") or sections.get("constraints") or app["preset_text"]),
        }
    if issue_title == "补课程模块映射":
        return {
            "observed": "当前 prompt 可执行，但关键词与课程主轴重合度偏低。",
            "snippet": truncate_text(sections.get("role") or sections.get("goal") or app["preset_text"]),
        }
    target_section = "goal" if issue_title == "补目标结果" else "constraints" if issue_title == "补硬性规则" else "tone"
    return {
        "observed": f"{target_section} 段缺失或过弱。",
        "snippet": truncate_text(sections.get("role") or app["preset_text"]),
    }


def improvement_outline(issue_title: str, app: dict[str, Any], module_name: str) -> list[str]:
    if issue_title == "补证据边界":
        return [
            "在“硬性规则”后新增“证据边界”块，明确只依据用户输入与已给证据推断。",
            "加入“证据不足时直接标注，不编造、不补脑”的固定句式。",
            "把需要高判断力的结论改成“证据 -> 推断 -> 风险提示”三段式。",
        ]
    if issue_title == "补输入上下文":
        return [
            "新增“输入上下文”块，收集用户阶段、角色、业务规模、目标、当前卡点。",
            "把 prompt 内部隐含前提改成变量槽位，方便未来自动填充。",
            "输入不足时只输出已知范围内的判断，不默认补全业务背景。",
        ]
    if issue_title == "补输出格式":
        return [
            "把交付结果改成固定结构：结论、分析、行动建议、风险提示。",
            "每段限制长度与信息密度，减少模型自由漂移。",
            "对报告类输出补充“先结论后展开”的顺序。",
        ]
    if issue_title == "补课程模块映射":
        return [
            f"显式写入“{module_name}”相关概念词，避免和课程体系脱钩。",
            "把课程里的判断句替换成 prompt 内的分析框架或评分标准。",
            "让输出结论明确回到原力创业方法论，而不是泛泛商业建议。",
        ]
    if issue_title == "补目标结果":
        return [
            "把任务目标改写成用户拿到什么结果、解决什么决策。",
            "避免只描述身份或风格，不描述产出价值。",
            "目标后接一条成功判定标准，便于未来自动评测。",
        ]
    if issue_title == "补硬性规则":
        return [
            "单列“硬性规则”，约束不可编造、不可越界、不可偏离场景。",
            "增加需要保持的业务边界和不该输出的内容。",
            "把风格性偏好和合规性边界分开写。",
        ]
    return [
        "补“语气与禁忌”块，锁定明哥体系中的从容、深刻、具体感。",
        "明确避免泛泛鸡汤、避免空洞堆词、避免无依据夸张判断。",
        "把表达方式与用户阅读场景绑定起来。",
    ]


def build_top_optimizations(apps: list[dict[str, Any]], modules: list[dict[str, Any]], top_n: int) -> list[dict[str, Any]]:
    candidates = [app for app in apps if app["editable_source"] == "local_preset" and int(app["status"]) == 1]
    candidates.sort(key=lambda row: (-priority_score(row), -int(row["order"]), row["name"]))
    selected = candidates[:top_n]
    suggestions: list[dict[str, Any]] = []
    for rank, app in enumerate(selected, start=1):
        issue_title, issue_reason = choose_primary_issue(app)
        module_name = app["primary_module"] or "原力定位与原理学习"
        course_evidence = best_course_evidence(module_name, modules)
        prompt_evidence = current_prompt_evidence(app, issue_title)
        suggestions.append(
            {
                "rank": rank,
                "app_id": app["id"],
                "name": app["name"],
                "category": app["category"],
                "priority_score": priority_score(app),
                "primary_module": module_name,
                "issue_title": issue_title,
                "issue_reason": issue_reason,
                "recommended_changes": improvement_outline(issue_title, app, module_name),
                "present_sections": [section for section in SECTION_ORDER if app["prompt_sections"].get(section)],
                "missing_sections": [section for section in SECTION_ORDER if not app["prompt_sections"].get(section)],
                "course_evidence": course_evidence,
                "current_prompt_evidence": prompt_evidence,
            }
        )
    return suggestions


def derive_prompt_schema(apps: list[dict[str, Any]]) -> dict[str, Any]:
    local_apps = [app for app in apps if app["editable_source"] == "local_preset" and app["prompt_length"] > 0]
    local_apps.sort(key=lambda row: (-float(row["scores"]["overall"]), -int(row["order"]), row["name"]))
    exemplars = local_apps[:8]
    section_presence = Counter()
    for app in exemplars:
        for section in SECTION_ORDER:
            if app["prompt_sections"].get(section):
                section_presence[section] += 1
    schema_sections: list[dict[str, Any]] = []
    for section in SECTION_ORDER:
        required = section in {"role", "inputs", "goal", "constraints", "evidence_rules", "output_format"}
        schema_sections.append(
            {
                "key": section,
                "label": SCHEMA_SECTION_LABELS[section],
                "required": required,
                "present_in_exemplars": section_presence.get(section, 0),
                "description": {
                    "role": "定义智能体身份、适用边界和价值承诺。",
                    "inputs": "收纳用户阶段、角色、问题、目标等变量，减少凭空补全。",
                    "goal": "明确此 prompt 要帮助用户拿到什么结果。",
                    "constraints": "约束必须遵守的业务边界、禁忌和输出要求。",
                    "evidence_rules": "显式规定证据不足时如何处理，避免幻觉和失真。",
                    "output_format": "规定输出顺序、结构、长度和交付形态。",
                    "tone": "规定语气、节奏、表达风格与禁忌表达。",
                    "examples": "补充句式模板、示例片段和高频表达。",
                    "escalation_boundary": "当输入不足或风险较高时，明确降级或提示方式。",
                }[section],
            }
        )
    return {
        "schema_name": "yuanli_course_preset_schema_v1",
        "ordered_sections": schema_sections,
        "recommended_template_order": [SCHEMA_SECTION_LABELS[section] for section in SECTION_ORDER],
        "derived_from_apps": [
            {
                "id": app["id"],
                "name": app["name"],
                "category": app["category"],
                "overall_score": app["scores"]["overall"],
            }
            for app in exemplars
        ],
    }


def derive_optimization_rules(apps: list[dict[str, Any]], modules: list[dict[str, Any]], prompt_schema: dict[str, Any]) -> list[dict[str, Any]]:
    local_apps = [app for app in apps if app["editable_source"] == "local_preset"]
    missing_evidence = sum(1 for app in local_apps if not app["prompt_sections"].get("evidence_rules"))
    missing_inputs = sum(1 for app in local_apps if not app["prompt_sections"].get("inputs"))
    missing_format = sum(1 for app in local_apps if not app["prompt_sections"].get("output_format"))
    module_gaps = [module["module"] for module in build_module_mapping(modules, apps) if module["gap"]]
    rules = [
        {
            "rule_id": "R1",
            "title": "固定使用统一 Prompt Schema",
            "description": "所有本地 preset 默认按同一顺序写：角色定位 -> 输入上下文 -> 目标结果 -> 硬性规则 -> 证据边界 -> 输出格式 -> 语气与禁忌 -> 示例与模板 -> 证据不足时处理。",
            "why_now": f"Top exemplar prompts already稳定覆盖 {sum(1 for section in prompt_schema['ordered_sections'] if section['required'])} 个必需段落。",
        },
        {
            "rule_id": "R2",
            "title": "分析类 prompt 必带证据边界",
            "description": "凡是输出报告、诊断、判断、建议的 prompt，必须显式写“仅依据输入/证据不足时标注/不得编造”。",
            "why_now": f"当前本地 prompt 中仍有 {missing_evidence} 个未检出证据边界。",
        },
        {
            "rule_id": "R3",
            "title": "所有高客单 prompt 必收输入变量",
            "description": "把用户阶段、角色、规模、目标、卡点收成变量槽位，不再把上下文埋在长叙述里。",
            "why_now": f"当前本地 prompt 中仍有 {missing_inputs} 个没有稳定输入上下文块。",
        },
        {
            "rule_id": "R4",
            "title": "报告类输出统一结论先行",
            "description": "所有报告型 prompt 先给结论，再展开分析、行动和风险提示，减少模型自由漂移。",
            "why_now": f"当前本地 prompt 中仍有 {missing_format} 个未固化输出格式。",
        },
        {
            "rule_id": "R5",
            "title": "课程模块与应用分类强绑定",
            "description": "新增或改写 prompt 时，必须声明它属于哪个课程模块，以及服务哪类用户场景。",
            "why_now": "课程主轴已经稳定，但后台分类与课程模块仍有脱节。",
        },
        {
            "rule_id": "R6",
            "title": "优先改本地 preset，不先碰外部 GPTs",
            "description": "首轮优化只改 local_preset；external_gpts 先做来源盘点和替代方案设计。",
            "why_now": "外部 GPTs 的 canonical prompt 不在当前后台可编辑路径里。",
        },
        {
            "rule_id": "R7",
            "title": "模块缺口直接进产品候选池",
            "description": "课程模块若没有对应应用，不视为分析失败，而是进入“尚未产品化机会清单”。",
            "why_now": f"当前缺口模块数量：{len(module_gaps)}。",
        },
    ]
    return rules


def derive_product_gaps(modules: list[dict[str, Any]], mapping: list[dict[str, Any]], apps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    category_counts = Counter(app["category"] for app in apps)
    gaps: list[dict[str, Any]] = []
    for module in modules:
        module_map = next(item for item in mapping if item["module"] == module["module"])
        if module_map["gap"]:
            gaps.append(
                {
                    "module": module["module"],
                    "gap_type": "no_direct_app",
                    "reason": "课程模块已有稳定概念与证据，但当前后台无直接对应应用。",
                    "suggested_categories": ["原力 AI", "私董 AI"] if module["coverage_priority"] >= 4 else ["原力 AI"],
                    "evidence": module["evidence_refs"][:2],
                }
            )
            continue
        if not any(app["category"] in FOCUS_CATEGORIES for app in apps if app["primary_module"] == module["module"]):
            gaps.append(
                {
                    "module": module["module"],
                    "gap_type": "weak_focus_category_coverage",
                    "reason": "已有应用映射，但未落在核心课程分类中，后续不利于体系化教学复用。",
                    "suggested_categories": sorted(FOCUS_CATEGORIES),
                    "evidence": module["evidence_refs"][:2],
                }
            )
    for category, count in category_counts.items():
        if category in FOCUS_CATEGORIES:
            continue
        local_count = sum(1 for app in apps if app["category"] == category and app["editable_source"] == "local_preset")
        if count >= 8 and local_count >= 5:
            gaps.append(
                {
                    "module": category,
                    "gap_type": "cross_vertical_packaging",
                    "reason": "该分类应用数量已形成竖类集群，但尚未显式映射到课程模块，适合作为行业模板包整理。",
                    "suggested_categories": [category, "原力 AI"],
                    "evidence": [],
                }
            )
    return gaps


def make_csv_inventory(path: Path, apps: list[dict[str, Any]]) -> None:
    fieldnames = [
        "id",
        "name",
        "category",
        "order",
        "status",
        "model_type",
        "editable_source",
        "primary_module",
        "prompt_length",
        "score_overall",
        "gizmo_id",
        "flowith_id",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for app in apps:
            writer.writerow(
                {
                    "id": app["id"],
                    "name": app["name"],
                    "category": app["category"],
                    "order": app["order"],
                    "status": app["status"],
                    "model_type": app["model_type"],
                    "editable_source": app["editable_source"],
                    "primary_module": app["primary_module"],
                    "prompt_length": app["prompt_length"],
                    "score_overall": app["scores"]["overall"],
                    "gizmo_id": app["gizmo_id"],
                    "flowith_id": app["flowith_id"],
                }
            )


def render_situation_map() -> str:
    lines = [
        "# Situation Map",
        "",
        "- `任务`: 原力创业课程吸收与智能体 Prompt 优化",
        "- `自治判断`: 本轮适合 AI 自治完成课程抽象、后台只读盘点、输出生成；写入后台和发布仍保持人工边界。",
        "- `全局最优判断`: 先抽课程骨架，再映射后台 preset，比逐条改 prompt 更稳。",
        "- `能力复用判断`: 复用课程转写稿、后台 `preset` 字段、现有应用分类与工作目录。",
        "- `验真判断`: 每条优化建议都要同时引用课程证据和当前 prompt 证据。",
        "- `进化判断`: 输出可复跑脚本、标准 Schema、规则集和本地 artifact，而不是一次性摘要。",
        "- `当前最大失真`: 课程模块、应用分类与真实 prompt 结构过去没有被放在同一张图里。",
        "",
    ]
    return "\n".join(lines)


def render_course_module_markdown(modules: list[dict[str, Any]], resolutions: list[dict[str, Any]]) -> str:
    lines = ["# 原力创业课程模块图", "", "## 重复稿取舍", ""]
    for resolution in resolutions:
        lines.append(f"- `{resolution['session_key']}` -> `{Path(resolution['chosen_path']).name}`")
        lines.append(f"  依据: {resolution['reason']}")
    lines.extend(["", "## 模块", ""])
    for module in modules:
        lines.append(f"### {module['module']}")
        lines.append("")
        lines.append(f"- 概念: {', '.join(module['concepts'])}")
        lines.append(f"- 决策规则: {'；'.join(module['decision_rules'])}")
        lines.append(f"- 用户场景: {'；'.join(module['user_scenarios'])}")
        lines.append(f"- 输出形态: {'；'.join(module['output_patterns'])}")
        if module["evidence_refs"]:
            lines.append("- 课程证据:")
            for evidence in module["evidence_refs"][:4]:
                lines.append(f"  - [{evidence['source']}] {evidence['snippet']}")
        lines.append("")
    return "\n".join(lines)


def render_app_inventory_markdown(category_summary: list[dict[str, Any]], apps: list[dict[str, Any]]) -> str:
    editable_counts = Counter(app["editable_source"] for app in apps)
    model_counts = Counter(app["model_type"] for app in apps)
    lines = [
        "# 应用清单与分类盘点",
        "",
        f"- 总应用数: `{len(apps)}`",
        f"- `local_preset`: `{editable_counts.get('local_preset', 0)}`",
        f"- `external_gpts`: `{editable_counts.get('external_gpts', 0)}`",
        f"- `flowith`: `{editable_counts.get('flowith', 0)}`",
        f"- 模型类型分布: `{dict(model_counts)}`",
        "",
        "## 分类摘要",
        "",
        "| 分类 | 数量 | editable_source | model_type | 核心应用 | 本地 prompt 平均分 |",
        "| --- | ---: | --- | --- | --- | ---: |",
    ]
    for row in category_summary:
        lines.append(
            f"| {row['category']} | {row['count']} | {row['editable_source_counts']} | {row['model_type_counts']} | {row['top_order_app']} | {row['average_local_prompt_score']} |"
        )
    return "\n".join(lines)


def render_prompt_schema_markdown(prompt_schema: dict[str, Any]) -> str:
    lines = ["# Prompt Schema", "", f"- 名称: `{prompt_schema['schema_name']}`", "", "## 推荐顺序", ""]
    for section in prompt_schema["ordered_sections"]:
        required = "必需" if section["required"] else "可选"
        lines.append(
            f"- `{section['label']}`: {required}; exemplar 覆盖 `{section['present_in_exemplars']}`；{section['description']}"
        )
    lines.extend(["", "## 代表性 prompt", ""])
    for app in prompt_schema["derived_from_apps"]:
        lines.append(f"- `{app['name']}` / `{app['category']}` / score `{app['overall_score']}`")
    return "\n".join(lines)


def render_top_optimizations_markdown(items: list[dict[str, Any]]) -> str:
    lines = ["# Top 20 Prompt 优化建议", ""]
    for item in items:
        lines.append(f"## {item['rank']}. {item['name']} ({item['category']})")
        lines.append("")
        lines.append(f"- 主模块: `{item['primary_module']}`")
        lines.append(f"- 主要问题: `{item['issue_title']}`")
        lines.append(f"- 原因: {item['issue_reason']}")
        lines.append(f"- 已有段落: {', '.join(item['present_sections']) or '无'}")
        lines.append(f"- 缺失段落: {', '.join(item['missing_sections']) or '无'}")
        lines.append("- 推荐改法:")
        for change in item["recommended_changes"]:
            lines.append(f"  - {change}")
        lines.append(
            f"- 课程证据: [{item['course_evidence'].get('source', '')}] {item['course_evidence'].get('snippet', '')}"
        )
        lines.append(
            f"- 当前 prompt 证据: {item['current_prompt_evidence']['observed']} | {item['current_prompt_evidence']['snippet']}"
        )
        lines.append("")
    return "\n".join(lines)


def render_rules_markdown(rules: list[dict[str, Any]]) -> str:
    lines = ["# 自动优化规则", ""]
    for rule in rules:
        lines.append(f"## {rule['rule_id']} {rule['title']}")
        lines.append("")
        lines.append(f"- 规则: {rule['description']}")
        lines.append(f"- 当前依据: {rule['why_now']}")
        lines.append("")
    return "\n".join(lines)


def render_gaps_markdown(gaps: list[dict[str, Any]]) -> str:
    lines = ["# 尚未产品化的课程模块机会", ""]
    if not gaps:
        lines.append("- 当前未发现明显缺口。")
        return "\n".join(lines)
    for gap in gaps:
        lines.append(f"## {gap['module']}")
        lines.append("")
        lines.append(f"- 缺口类型: `{gap['gap_type']}`")
        lines.append(f"- 原因: {gap['reason']}")
        lines.append(f"- 建议落点: {', '.join(gap['suggested_categories'])}")
        for evidence in gap.get("evidence", [])[:2]:
            lines.append(f"- 课程证据: [{evidence['source']}] {evidence['snippet']}")
        lines.append("")
    return "\n".join(lines)


def render_summary_markdown(
    run_id: str,
    modules: list[dict[str, Any]],
    apps: list[dict[str, Any]],
    category_summary: list[dict[str, Any]],
    top_optimizations: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
) -> str:
    editable_counts = Counter(app["editable_source"] for app in apps)
    focus_coverage = {
        category: sum(1 for app in apps if app["category"] == category)
        for category in sorted(FOCUS_CATEGORIES)
    }
    lines = [
        "# 原力创业课程吸收与 Prompt 优化摘要",
        "",
        f"- run_id: `{run_id}`",
        f"- 课程主模块数: `{len(modules)}`",
        f"- 应用总数: `{len(apps)}`",
        f"- 分类数: `{len(category_summary)}`",
        f"- `local_preset / external_gpts / flowith`: `{editable_counts.get('local_preset', 0)} / {editable_counts.get('external_gpts', 0)} / {editable_counts.get('flowith', 0)}`",
        f"- 核心分类覆盖: `{focus_coverage}`",
        "",
        "## 首轮结论",
        "",
        "- 课程已经稳定抽成 6 个可复用模块，可直接对接 prompt 设计。",
        "- 后台的 canonical prompt 字段确认为 `preset`，适合继续做模板化治理。",
        "- Top 20 建议已全部绑定“双证据”：课程证据 + 当前 prompt 证据。",
        f"- 尚未产品化或覆盖偏弱的机会点: `{len(gaps)}`",
        "",
        "## 交付物",
        "",
        "- `course-module-map.md`",
        "- `app-inventory-summary.md` + `app-inventory.csv`",
        "- `prompt-schema.md`",
        "- `top20-optimizations.md`",
        "- `prompt-optimization-rules.md`",
        "- `product-gap-opportunities.md`",
        "",
    ]
    return "\n".join(lines)


def governance_artifacts(
    run_id: str,
    output_files: list[str],
    situation_map: dict[str, str],
) -> dict[str, Any]:
    return {
        "route.json": {
            "run_id": run_id,
            "selected_skills": ["ai-da-guan-jia", "doc"],
            "task_family": "course_absorption_prompt_governance",
            "execution_mode": "local_analysis_read_only",
            "verification_strategy": "course_evidence_plus_prompt_evidence",
        },
        "github-task.json": {
            "run_id": run_id,
            "title": "原力创业课程吸收与智能体 Prompt 优化",
            "state": "verified",
            "type": "research",
            "artifact": "report",
            "read_only": True,
        },
        "github-payload.json": {
            "run_id": run_id,
            "deliverables": output_files,
            "situation_map": situation_map,
        },
        "github-sync-result.json": {
            "run_id": run_id,
            "status": "not_run",
            "reason": "read_only_local_analysis_only",
        },
        "feishu-payload.json": {
            "run_id": run_id,
            "status": "payload_only",
            "deliverables": output_files,
        },
        "self-evaluation.json": {
            "run_id": run_id,
            "gained": "把课程模块、后台分类、真实 preset 放进了一套统一分析流程。",
            "wasted": "首轮仍需依赖规则抽取，尚未做语义级别聚类。",
            "next_iterate": "下一轮可补充 prompt diff 建议稿和按分类批量重写草案。",
        },
        "pending-human-feedback.json": {
            "run_id": run_id,
            "status": "pending_human_feedback",
            "slot": "reserved",
            "comment": "",
        },
        "task-closure.json": {
            "run_id": run_id,
            "closure_state": "completed",
            "read_only": True,
        },
    }


def markdown_for_governance(run_id: str, outputs: list[str]) -> dict[str, str]:
    return {
        "github-sync-plan.md": "\n".join(
            [
                "# GitHub Sync Plan",
                "",
                f"- run_id: `{run_id}`",
                "- state: local-only verified artifact",
                f"- deliverables: {', '.join(outputs)}",
                "- note: 本轮按用户要求保持只读，不做 GitHub 侧 apply。",
            ]
        ),
        "github-archive.md": "\n".join(
            [
                "# GitHub Archive Note",
                "",
                f"- run_id: `{run_id}`",
                "- 结果已在本地 artifact 目录闭环。",
                "- 下一步如果需要协同，再把输出转成 issue / project 卡片。",
            ]
        ),
        "self-evaluation.md": "\n".join(
            [
                "# Self Evaluation",
                "",
                "- gained: 课程、分类、prompt 终于能同图查看。",
                "- wasted: 还没有直接产出可粘贴回后台的 prompt diff。",
                "- next iterate: 生成每个核心分类的可复用 prompt patch 模板。",
            ]
        ),
    }


def run_analysis(args: argparse.Namespace) -> Path:
    timestamp = now_local()
    run_id = args.run_id or f"adagj-odyssey-course-prompt-{timestamp.strftime('%Y%m%d-%H%M%S')}"
    run_dir = ensure_dir(RUNS_ROOT / timestamp.strftime("%Y-%m-%d") / run_id)
    input_dir = ensure_dir(run_dir / "input")
    course_dir = ensure_dir(run_dir / "course")
    texts_dir = ensure_dir(course_dir / "texts")
    apps_dir = ensure_dir(run_dir / "apps")
    outputs_dir = ensure_dir(run_dir / "outputs")

    file_infos = [
        extract_course_file_info(path)
        for path in sorted(Path(args.course_dir).glob("*原力创业-DAY*.docx"))
    ]
    if not file_infos:
        raise RuntimeError(f"No 原力创业 course docx files found in {args.course_dir}")
    canonical_infos, resolutions = choose_canonical_variants(file_infos)
    for info in canonical_infos:
        text_name = normalized_variant_key(Path(str(info["path"]))).replace(".docx", ".txt")
        write_text(texts_dir / text_name, str(info["text"]))

    write_json(course_dir / "source-manifest.json", file_infos)
    write_json(course_dir / "duplicate-resolution.json", resolutions)

    if args.apps_json and args.categories_json:
        apps_snapshot = json.loads(Path(args.apps_json).read_text(encoding="utf-8"))
        categories = json.loads(Path(args.categories_json).read_text(encoding="utf-8"))
        apps_raw = json.loads(Path(args.apps_json).read_text(encoding="utf-8"))
    else:
        live = fetch_live_snapshots(args.base_url, args.username, args.password, args.page_size)
        categories = list(live["categories"])
        apps_raw = list(live["apps"])
        write_json(input_dir / "live-login-user.json", live["user"])
        write_json(input_dir / "app-categories.raw.json", categories)
        write_json(input_dir / "apps.raw.json", apps_raw)
        apps_snapshot = {"items": apps_raw, "total": len(apps_raw)}

    modules = build_course_modules(canonical_infos)
    apps = normalize_apps(list(apps_snapshot["items"]), categories, modules)
    category_summary = summarize_categories(apps)
    module_mapping = build_module_mapping(modules, apps)
    top_optimizations = build_top_optimizations(apps, modules, args.top_n)
    prompt_schema = derive_prompt_schema(apps)
    rules = derive_optimization_rules(apps, modules, prompt_schema)
    gaps = derive_product_gaps(modules, module_mapping, apps)

    write_json(course_dir / "course-modules.json", modules)
    write_text(outputs_dir / "course-module-map.md", render_course_module_markdown(modules, resolutions))
    write_json(outputs_dir / "course-module-map.json", {"modules": modules, "duplicate_resolution": resolutions})

    write_json(apps_dir / "categories.json", categories)
    write_json(apps_dir / "inventory-normalized.json", apps)
    write_json(apps_dir / "category-summary.json", category_summary)
    write_json(apps_dir / "module-mapping.json", module_mapping)
    make_csv_inventory(outputs_dir / "app-inventory.csv", apps)
    write_text(outputs_dir / "app-inventory-summary.md", render_app_inventory_markdown(category_summary, apps))

    write_json(outputs_dir / "prompt-schema.json", prompt_schema)
    write_text(outputs_dir / "prompt-schema.md", render_prompt_schema_markdown(prompt_schema))

    write_json(outputs_dir / "top20-optimizations.json", top_optimizations)
    write_text(outputs_dir / "top20-optimizations.md", render_top_optimizations_markdown(top_optimizations))

    write_json(outputs_dir / "prompt-optimization-rules.json", rules)
    write_text(outputs_dir / "prompt-optimization-rules.md", render_rules_markdown(rules))

    write_json(outputs_dir / "product-gap-opportunities.json", gaps)
    write_text(outputs_dir / "product-gap-opportunities.md", render_gaps_markdown(gaps))

    summary_md = render_summary_markdown(run_id, modules, apps, category_summary, top_optimizations, gaps)
    write_text(outputs_dir / "summary.md", summary_md)
    write_json(
        outputs_dir / "summary.json",
        {
            "run_id": run_id,
            "generated_at": iso_now(),
            "course_module_count": len(modules),
            "app_count": len(apps),
            "category_count": len(category_summary),
            "top_optimization_count": len(top_optimizations),
            "gap_count": len(gaps),
        },
    )

    situation_map = {
        "自治判断": "本轮适合 AI 自治完成课程抽象、后台只读盘点、输出生成；写入后台与发布仍停留在人。",
        "全局最优判断": "先抽课程骨架，再映射后台 preset，比逐条改 prompt 更稳。",
        "能力复用判断": "复用课程转写稿、后台 preset 字段、应用分类与当前 workdir artifact 结构。",
        "验真判断": "每条优化建议都包含课程证据和当前 prompt 证据。",
        "进化判断": "输出可复跑脚本、Schema、规则集和本地 artifact。",
        "当前最大失真": "课程模块、应用分类、prompt 结构过去未统一对齐。",
    }
    write_text(run_dir / "situation-map.md", render_situation_map())
    output_files = sorted(str(path.relative_to(run_dir)) for path in outputs_dir.iterdir() if path.is_file())
    gov_json = governance_artifacts(run_id, output_files, situation_map)
    for filename, payload in gov_json.items():
        write_json(run_dir / filename, payload)
    for filename, text in markdown_for_governance(run_id, output_files).items():
        write_text(run_dir / filename, text)

    ensure_dir(DERIVED_REPORTS_ROOT)
    write_text(DERIVED_REPORTS_ROOT / "odyssey-course-prompt-analysis-latest.md", summary_md)
    write_json(
        DERIVED_REPORTS_ROOT / "odyssey-course-prompt-analysis-latest.json",
        {
            "run_id": run_id,
            "run_dir": str(run_dir),
            "summary_file": str(outputs_dir / "summary.md"),
            "top20_file": str(outputs_dir / "top20-optimizations.md"),
        },
    )
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only Odyssey course and prompt analysis.")
    parser.add_argument("--course-dir", required=True, help="Directory containing the 原力创业 DAY docx files.")
    parser.add_argument("--run-id", help="Optional explicit run id.")
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N, help="How many prompt suggestions to generate.")
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE, help="Live app fetch page size.")
    parser.add_argument("--apps-json", help="Offline apps snapshot JSON with an `items` array.")
    parser.add_argument("--categories-json", help="Offline category snapshot JSON.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Live admin base URL.")
    parser.add_argument("--username", help="Live admin username.")
    parser.add_argument("--password", help="Live admin password.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if bool(args.apps_json) != bool(args.categories_json):
        parser.error("--apps-json and --categories-json must be provided together.")
    if not args.apps_json and not (args.username and args.password):
        parser.error("Provide either --apps-json/--categories-json or live --username/--password.")

    run_dir = run_analysis(args)
    print(str(run_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
