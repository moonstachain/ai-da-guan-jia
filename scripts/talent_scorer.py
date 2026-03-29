#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_WEIGHTS = {
    "smart": 25,
    "tough": 25,
    "reliable": 30,
    "spark": 20,
}

DIMENSION_LABELS = {
    "smart": "聪明",
    "tough": "皮实",
    "reliable": "靠谱",
    "spark": "灵气",
}

KEYWORDS = {
    "smart": [
        "strategy",
        "system",
        "framework",
        "analy",
        "拆解",
        "系统",
        "策略",
        "框架",
        "结构化",
        "抽象",
        "学习",
        "洞察",
        "数据",
        "增长",
        "优化",
        "automation",
    ],
    "tough": [
        "pressure",
        "crisis",
        "ownership",
        "resilien",
        "fail",
        "challenge",
        "困难",
        "压力",
        "韧性",
        "复盘",
        "扛",
        "恢复",
        "挑战",
        "挫折",
        "负责",
    ],
    "reliable": [
        "delivery",
        "delivered",
        "closed",
        "sla",
        "launch",
        "execute",
        "交付",
        "闭环",
        "兑现",
        "落地",
        "准时",
        "结果",
        "负责到底",
        "推进",
        "完成",
    ],
    "spark": [
        "creative",
        "curious",
        "cross",
        "insight",
        "taste",
        "原创",
        "好奇",
        "跨界",
        "美感",
        "审美",
        "洞见",
        "独立观点",
        "灵感",
        "研究",
        "长期主义",
    ],
}


def read_text_arg(text: str | None, file_path: str | None, *, label: str) -> str:
    if text:
        return text.strip()
    if file_path:
        return Path(file_path).read_text(encoding="utf-8").strip()
    raise SystemExit(f"missing {label}: provide --{label.replace('_', '-').lower()}-text or --{label.replace('_', '-').lower()}-file")


def load_json_arg(raw: str | None, file_path: str | None, *, label: str) -> Any:
    if raw:
        return json.loads(raw)
    if file_path:
        return json.loads(Path(file_path).read_text(encoding="utf-8"))
    raise SystemExit(f"missing {label}: provide --{label.replace('_', '-').lower()}-json or --{label.replace('_', '-').lower()}-file")


def split_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[。！？.!?;；])\s+|\n+", cleaned)
    return [part.strip() for part in parts if part.strip()]


def dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def find_evidence(text: str, dimension: str, *, limit: int = 3) -> list[str]:
    keywords = KEYWORDS[dimension]
    matches: list[str] = []
    for sentence in split_sentences(text):
        lower = sentence.lower()
        if any(keyword.lower() in lower for keyword in keywords):
            matches.append(sentence)
        if len(matches) >= limit:
            break
    if not matches and text.strip():
        matches = split_sentences(text)[:1]
    return matches


def count_dimension_hits(text: str, dimension: str) -> tuple[int, int]:
    lower = text.lower()
    unique = 0
    total = 0
    for keyword in KEYWORDS[dimension]:
        hits = lower.count(keyword.lower())
        if hits:
            unique += 1
            total += hits
    return unique, total


def level_from_text(text: str, dimension: str) -> int:
    unique, total = count_dimension_hits(text, dimension)
    sentences = split_sentences(text)
    richness = unique * 2 + min(total, 4) + min(len(sentences), 4)
    if not text.strip():
        return 1
    if richness >= 12:
        return 5
    if richness >= 9:
        return 4
    if richness >= 6:
        return 3
    if richness >= 3:
        return 2
    return 1


def clamp(value: int, lower: int, upper: int) -> int:
    return max(lower, min(upper, value))


def weighted_score(level: int, weight: int) -> int:
    return int(round(weight * (level / 5)))


def overall_grade(score: int, levels: dict[str, int]) -> str:
    if score >= 90 and min(levels.values()) >= 4:
        return "S"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B"
    if score >= 60:
        return "C"
    return "D"


def level_to_anchor(level: int) -> str:
    return {
        1: "无证据",
        2: "偏弱",
        3: "中等",
        4: "较强",
        5: "卓越",
    }[level]


def build_resume_result(resume_text: str, job_description: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    weights = dict(DEFAULT_WEIGHTS)
    if config and isinstance(config.get("weights"), dict):
        for key in weights:
            value = config["weights"].get(key)
            if isinstance(value, int) and value > 0:
                weights[key] = value

    analysis_text = "\n".join([resume_text.strip(), job_description.strip()]).strip()
    levels = {dimension: level_from_text(analysis_text, dimension) for dimension in weights}
    scores = {dimension: weighted_score(levels[dimension], weights[dimension]) for dimension in weights}
    overall = sum(scores.values())
    grade = overall_grade(overall, levels)

    evidence = {dimension: find_evidence(analysis_text, dimension) for dimension in weights}
    strengths = [
        f"{DIMENSION_LABELS[dimension]}表现{level_to_anchor(levels[dimension])}，有较明确证据支撑。"
        for dimension in sorted(levels, key=levels.get, reverse=True)[:2]
    ]
    weaknesses = [
        f"{DIMENSION_LABELS[dimension]}证据偏少，建议在面试中追问具体案例。"
        for dimension in sorted(levels, key=levels.get)[:2]
    ]
    risk_flags = [
        f"{DIMENSION_LABELS[dimension]}证据不足"
        for dimension, level in levels.items()
        if level <= 2
    ]
    recommended_questions = [
        f"请结合一个真实项目，具体说明你如何体现{DIMENSION_LABELS[dimension]}。"
        for dimension, level in sorted(levels.items(), key=lambda item: item[1])
        if level <= 3
    ][:4]

    return {
        "smart_score": scores["smart"],
        "tough_score": scores["tough"],
        "reliable_score": scores["reliable"],
        "spark_score": scores["spark"],
        "overall_score": overall,
        "grade": grade,
        "smart_evidence": " | ".join(evidence["smart"]),
        "tough_evidence": " | ".join(evidence["tough"]),
        "reliable_evidence": " | ".join(evidence["reliable"]),
        "spark_evidence": " | ".join(evidence["spark"]),
        "strengths": strengths,
        "weaknesses": weaknesses,
        "risk_flags": risk_flags,
        "recommended_interview_questions": recommended_questions,
        "recommendation_summary": (
            f"候选人当前综合评分 {overall}/100，等级 {grade}。"
            f" 优先确认 {DIMENSION_LABELS[min(levels, key=levels.get)]} 维度的真实案例，再决定是否推进。"
        ),
    }


def baseline_level(score: int, weight: int) -> int:
    if weight <= 0:
        return 1
    return clamp(int(round((score / weight) * 5)), 1, 5)


def delta_symbol(current_score: int, baseline_score: int, *, tolerance: int = 2) -> str:
    if current_score >= baseline_score + tolerance:
        return "↑"
    if current_score <= baseline_score - tolerance:
        return "↓"
    return "→"


def build_interview_result(
    transcript_text: str,
    resume_result: dict[str, Any],
    interview_round: str,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    weights = dict(DEFAULT_WEIGHTS)
    if config and isinstance(config.get("weights"), dict):
        for key in weights:
            value = config["weights"].get(key)
            if isinstance(value, int) and value > 0:
                weights[key] = value

    levels = {dimension: level_from_text(transcript_text, dimension) for dimension in weights}
    scores = {dimension: weighted_score(levels[dimension], weights[dimension]) for dimension in weights}
    baseline_scores = {
        "smart": int(resume_result.get("smart_score", 0) or 0),
        "tough": int(resume_result.get("tough_score", 0) or 0),
        "reliable": int(resume_result.get("reliable_score", 0) or 0),
        "spark": int(resume_result.get("spark_score", 0) or 0),
    }
    key_observations = dedupe_keep_order([
        sentence for dimension in weights for sentence in find_evidence(transcript_text, dimension, limit=1)
    ])[:4]
    concerns = [
        f"{DIMENSION_LABELS[dimension]}在{interview_round}中仍缺少可验证案例。"
        for dimension, level in levels.items()
        if level <= 2
    ]
    total = sum(scores.values())
    if total >= 85 and not concerns:
        verdict = "强烈推荐"
    elif total >= 65:
        verdict = "推荐"
    elif total >= 50:
        verdict = "中性"
    else:
        verdict = "不推荐"

    weak_dimensions = [dimension for dimension, level in sorted(levels.items(), key=lambda item: item[1])[:2]]
    next_focus = [f"继续验证{DIMENSION_LABELS[dimension]}：要求候选人给出更完整的情境-动作-结果。" for dimension in weak_dimensions]

    return {
        "smart_score_iv": scores["smart"],
        "tough_score_iv": scores["tough"],
        "reliable_score_iv": scores["reliable"],
        "spark_score_iv": scores["spark"],
        "interview_total": total,
        "smart_delta": delta_symbol(scores["smart"], baseline_scores["smart"]),
        "tough_delta": delta_symbol(scores["tough"], baseline_scores["tough"]),
        "reliable_delta": delta_symbol(scores["reliable"], baseline_scores["reliable"]),
        "spark_delta": delta_symbol(scores["spark"], baseline_scores["spark"]),
        "key_observations": key_observations or ["逐字稿里缺少足够长的结构化回答，需要补追问。"],
        "concerns": concerns,
        "verdict": verdict,
        "verdict_reasoning": (
            f"{interview_round}总分 {total}/100。"
            f" 与简历阶段相比，最明显变化是"
            f" {DIMENSION_LABELS[max(scores, key=lambda item: scores[item] - baseline_scores[item])]}。"
        ),
        "next_round_focus_areas": next_focus,
    }


def normalize_history(history: Any) -> list[dict[str, Any]]:
    if isinstance(history, list):
        items = history
    elif isinstance(history, dict):
        items = history.get("history") or history.get("stages") or []
    else:
        items = []
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "stage": str(item.get("stage") or item.get("name") or "").strip() or f"stage-{len(normalized) + 1}",
                "smart_score": int(item.get("smart_score") or item.get("smart_score_iv") or item.get("smart_score_trial") or 0),
                "tough_score": int(item.get("tough_score") or item.get("tough_score_iv") or item.get("tough_score_trial") or 0),
                "reliable_score": int(item.get("reliable_score") or item.get("reliable_score_iv") or item.get("reliable_score_trial") or 0),
                "spark_score": int(item.get("spark_score") or item.get("spark_score_iv") or item.get("spark_score_trial") or 0),
            }
        )
    return normalized


def build_probation_result(
    history: Any,
    accomplishments_text: str,
    problems_text: str,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    weights = dict(DEFAULT_WEIGHTS)
    if config and isinstance(config.get("weights"), dict):
        for key in weights:
            value = config["weights"].get(key)
            if isinstance(value, int) and value > 0:
                weights[key] = value

    normalized_history = normalize_history(history)
    latest = normalized_history[-1] if normalized_history else {
        "stage": "S1",
        "smart_score": 0,
        "tough_score": 0,
        "reliable_score": 0,
        "spark_score": 0,
    }

    achievement_levels = {dimension: level_from_text(accomplishments_text, dimension) for dimension in weights}
    problem_levels = {dimension: level_from_text(problems_text, dimension) for dimension in weights}
    baseline_levels = {
        "smart": baseline_level(latest["smart_score"], weights["smart"]),
        "tough": baseline_level(latest["tough_score"], weights["tough"]),
        "reliable": baseline_level(latest["reliable_score"], weights["reliable"]),
        "spark": baseline_level(latest["spark_score"], weights["spark"]),
    }

    final_levels: dict[str, int] = {}
    for dimension in weights:
        adjustment = 0
        if achievement_levels[dimension] >= 4:
            adjustment += 1
        if problem_levels[dimension] >= 4:
            adjustment -= 1
        final_levels[dimension] = clamp(baseline_levels[dimension] + adjustment, 1, 5)

    current_scores = {dimension: weighted_score(final_levels[dimension], weights[dimension]) for dimension in weights}
    evolution_curve = {
        "smart": [{"stage": item["stage"], "score": item["smart_score"]} for item in normalized_history] + [{"stage": "current", "score": current_scores["smart"]}],
        "tough": [{"stage": item["stage"], "score": item["tough_score"]} for item in normalized_history] + [{"stage": "current", "score": current_scores["tough"]}],
        "reliable": [{"stage": item["stage"], "score": item["reliable_score"]} for item in normalized_history] + [{"stage": "current", "score": current_scores["reliable"]}],
        "spark": [{"stage": item["stage"], "score": item["spark_score"]} for item in normalized_history] + [{"stage": "current", "score": current_scores["spark"]}],
    }
    total = sum(current_scores.values())
    concern_areas = [
        f"{DIMENSION_LABELS[dimension]}需要更多真实工作产出支撑。"
        for dimension, level in final_levels.items()
        if level <= 2
    ]
    growth_areas = [
        f"{DIMENSION_LABELS[dimension]}出现正向进化趋势。"
        for dimension, level in final_levels.items()
        if level >= baseline_levels[dimension] and level >= 4
    ]
    if total >= 85 and current_scores["reliable"] >= 24 and not concern_areas:
        verdict = "转正"
    elif total >= 70:
        verdict = "继续"
    elif total >= 55:
        verdict = "延长"
    else:
        verdict = "终止"

    return {
        "smart_score_trial": current_scores["smart"],
        "tough_score_trial": current_scores["tough"],
        "reliable_score_trial": current_scores["reliable"],
        "spark_score_trial": current_scores["spark"],
        "evolution_curve": evolution_curve,
        "growth_areas": growth_areas,
        "concern_areas": concern_areas,
        "verdict": verdict,
        "verdict_reasoning": (
            f"当前试用期总分 {total}/100。"
            f" 其中靠谱维度 {current_scores['reliable']}/{weights['reliable']}，"
            f" 结合成果与问题描述给出 {verdict} 判断。"
        ),
        "development_suggestions": [
            f"为{DIMENSION_LABELS[dimension]}建立 30 天可验证动作和复盘指标。"
            for dimension, level in sorted(final_levels.items(), key=lambda item: item[1])[:2]
        ],
    }


def ensure_fields(payload: dict[str, Any], required: list[str]) -> None:
    missing = [field for field in required if field not in payload]
    if missing:
        raise ValueError(f"missing output fields: {', '.join(missing)}")


def render_output(payload: dict[str, Any], *, output_path: str | None, pretty: bool) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None)
    if output_path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    print(text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic four-dimension scorer for PROJ-TALENT flows.")
    parser.add_argument(
        "--resume-json",
        dest="compat_resume_json",
        help="Compatibility mode: path to a parsed resume JSON file.",
    )
    parser.add_argument(
        "--job-description-text",
        dest="compat_job_description_text",
        help="Compatibility mode: raw role description text.",
    )
    parser.add_argument(
        "--job-description-file",
        dest="compat_job_description_file",
        help="Compatibility mode: path to a role description file.",
    )
    parser.add_argument(
        "--config-file",
        dest="compat_config_file",
        help="Compatibility mode: path to a JSON config file.",
    )
    parser.add_argument(
        "--output",
        dest="compat_output",
        help="Compatibility mode: output JSON path.",
    )
    parser.add_argument(
        "--pretty",
        dest="compat_pretty",
        action="store_true",
        help="Compatibility mode: pretty-print JSON output.",
    )
    subparsers = parser.add_subparsers(dest="command")

    resume = subparsers.add_parser("resume", help="Score a resume against the four-dimension model.")
    resume.add_argument("--resume-text")
    resume.add_argument("--resume-file")
    resume.add_argument("--job-description-text")
    resume.add_argument("--job-description-file")
    resume.add_argument("--config-file")
    resume.add_argument("--output")
    resume.add_argument("--pretty", action="store_true")

    interview = subparsers.add_parser("interview", help="Analyze an interview transcript against resume-stage scoring.")
    interview.add_argument("--transcript-text")
    interview.add_argument("--transcript-file")
    interview.add_argument("--resume-score-json")
    interview.add_argument("--resume-score-file")
    interview.add_argument("--round", default="一面")
    interview.add_argument("--config-file")
    interview.add_argument("--output")
    interview.add_argument("--pretty", action="store_true")

    probation = subparsers.add_parser("probation", help="Evaluate probation-stage growth from historical scores.")
    probation.add_argument("--history-json")
    probation.add_argument("--history-file")
    probation.add_argument("--accomplishments-text")
    probation.add_argument("--accomplishments-file")
    probation.add_argument("--problems-text")
    probation.add_argument("--problems-file")
    probation.add_argument("--config-file")
    probation.add_argument("--output")
    probation.add_argument("--pretty", action="store_true")

    return parser


def load_config(config_file: str | None) -> dict[str, Any] | None:
    if not config_file:
        return None
    return json.loads(Path(config_file).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command is None:
        if not args.compat_resume_json:
            build_parser().print_help()
            return 0
        config = load_config(args.compat_config_file)
        resume_payload = load_json_arg(None, args.compat_resume_json, label="resume")
        resume_text = str(
            resume_payload.get("plain_text")
            or resume_payload.get("resume_text")
            or resume_payload.get("text")
            or json.dumps(resume_payload, ensure_ascii=False)
        )
        if args.compat_job_description_text or args.compat_job_description_file:
            job_description = read_text_arg(
                args.compat_job_description_text,
                args.compat_job_description_file,
                label="job_description",
            )
        else:
            job_description = ""
        payload = build_resume_result(resume_text, job_description, config)
        ensure_fields(
            payload,
            [
                "smart_score",
                "tough_score",
                "reliable_score",
                "spark_score",
                "overall_score",
                "grade",
                "smart_evidence",
                "tough_evidence",
                "reliable_evidence",
                "spark_evidence",
                "strengths",
                "weaknesses",
                "risk_flags",
                "recommended_interview_questions",
                "recommendation_summary",
            ],
        )
        render_output(payload, output_path=args.compat_output, pretty=args.compat_pretty)
        return 0

    config = load_config(getattr(args, "config_file", None))

    if args.command == "resume":
        payload = build_resume_result(
            read_text_arg(args.resume_text, args.resume_file, label="resume"),
            read_text_arg(args.job_description_text, args.job_description_file, label="job_description"),
            config,
        )
        ensure_fields(
            payload,
            [
                "smart_score",
                "tough_score",
                "reliable_score",
                "spark_score",
                "overall_score",
                "grade",
                "smart_evidence",
                "tough_evidence",
                "reliable_evidence",
                "spark_evidence",
                "strengths",
                "weaknesses",
                "risk_flags",
                "recommended_interview_questions",
                "recommendation_summary",
            ],
        )
        render_output(payload, output_path=args.output, pretty=args.pretty)
        return 0

    if args.command == "interview":
        payload = build_interview_result(
            read_text_arg(args.transcript_text, args.transcript_file, label="transcript"),
            load_json_arg(args.resume_score_json, args.resume_score_file, label="resume_score"),
            args.round,
            config,
        )
        ensure_fields(
            payload,
            [
                "smart_score_iv",
                "tough_score_iv",
                "reliable_score_iv",
                "spark_score_iv",
                "interview_total",
                "smart_delta",
                "tough_delta",
                "reliable_delta",
                "spark_delta",
                "key_observations",
                "concerns",
                "verdict",
                "verdict_reasoning",
                "next_round_focus_areas",
            ],
        )
        render_output(payload, output_path=args.output, pretty=args.pretty)
        return 0

    payload = build_probation_result(
        load_json_arg(args.history_json, args.history_file, label="history"),
        read_text_arg(args.accomplishments_text, args.accomplishments_file, label="accomplishments"),
        read_text_arg(args.problems_text, args.problems_file, label="problems"),
        config,
    )
    ensure_fields(
        payload,
        [
            "smart_score_trial",
            "tough_score_trial",
            "reliable_score_trial",
            "spark_score_trial",
            "evolution_curve",
            "growth_areas",
            "concern_areas",
            "verdict",
            "verdict_reasoning",
            "development_suggestions",
        ],
    )
    render_output(payload, output_path=args.output, pretty=args.pretty)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
