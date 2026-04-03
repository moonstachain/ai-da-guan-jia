#!/usr/bin/env python3
"""Governance Engine — 3-layer judgment pipeline, run state machine, and adversarial verification.

Architecture optimization for AI大管家, inspired by Claude Code's:
- 3-layer security model (speculative classifier → hooks → permissions)
- query.ts state machine with guard conditions and rollback
- Verification Agent adversarial pattern
- Frozen dataclass immutability pattern

Usage:
    python3 governance_engine.py pipeline --prompt "..."
    python3 governance_engine.py state --run-id <id> --action advance
    python3 governance_engine.py verify --run-id <id> [--adversarial]
    python3 governance_engine.py harness --prompt "..."
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Resolve paths relative to ai_da_guan_jia.py's layout
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
ARTIFACTS_ROOT = SKILL_DIR / "artifacts" / "ai-da-guan-jia"
RUNS_ROOT = ARTIFACTS_ROOT / "runs"
SKILLS_ROOT = Path(os.getenv("CODEX_HOME", str(Path.home() / ".codex"))).resolve() / "skills"


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now().astimezone()
    return datetime.fromisoformat(value)


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


# ═══════════════════════════════════════════════════════════════════════════
# MODULE 1: Three-Layer Judgment Pipeline
# ═══════════════════════════════════════════════════════════════════════════
#
# Layer 1 (Fast ~10ms):  自治判断 + 能力复用判断  → 80% 日常任务直接放行
# Layer 2 (Hooks ~50ms): 全局最优判断 + 最大失真判断 → 仅 Layer1 未决时触发
# Layer 3 (Deep ~200ms): 验真判断 + 进化判断 → 仅高影响/不可逆任务触发
#
# Each layer can return a Decision: PASS, ESCALATE, BLOCK
# PASS   = proceed without further layers
# ESCALATE = run next layer
# BLOCK  = require human intervention

class Decision(Enum):
    PASS = "pass"
    ESCALATE = "escalate"
    BLOCK = "block"


@dataclass(frozen=True)
class JudgmentResult:
    """Immutable result from a single judgment."""
    name: str
    decision: Decision
    reason: str
    detail: str = ""


@dataclass(frozen=True)
class LayerResult:
    """Immutable result from a pipeline layer."""
    layer: int
    judgments: tuple[JudgmentResult, ...]
    decision: Decision
    elapsed_ms: float


@dataclass(frozen=True)
class PipelineResult:
    """Full pipeline execution result."""
    layers_executed: int
    final_decision: Decision
    results: tuple[LayerResult, ...]
    short_circuited: bool
    total_elapsed_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "layers_executed": self.layers_executed,
            "final_decision": self.final_decision.value,
            "short_circuited": self.short_circuited,
            "total_elapsed_ms": round(self.total_elapsed_ms, 1),
            "layers": [
                {
                    "layer": lr.layer,
                    "decision": lr.decision.value,
                    "elapsed_ms": round(lr.elapsed_ms, 1),
                    "judgments": [
                        {"name": j.name, "decision": j.decision.value, "reason": j.reason}
                        for j in lr.judgments
                    ],
                }
                for lr in self.results
            ],
        }


# --- Signal Detection (lightweight, reuses ai_da_guan_jia.detect_signals pattern) ---

HARD_BOUNDARY_KEYWORDS = frozenset([
    "登录", "授权", "付款", "发布", "删除", "不可逆", "权限",
    "login", "authorize", "payment", "publish", "delete", "irreversible",
])

IRREVERSIBLE_KEYWORDS = frozenset([
    "发布", "上线", "删除", "部署", "推送", "force push", "drop", "deploy",
    "publish", "delete", "migrate", "production",
])


def _quick_signals(prompt: str) -> dict[str, Any]:
    """Ultra-fast signal detection for Layer 1. No I/O."""
    text = prompt.lower()
    return {
        "has_hard_boundary": any(kw in text for kw in HARD_BOUNDARY_KEYWORDS),
        "is_irreversible": any(kw in text for kw in IRREVERSIBLE_KEYWORDS),
        "mentions_feishu": "飞书" in text or "feishu" in text or "lark" in text,
        "mentions_skill": "skill" in text or "技能" in text,
        "is_query_only": any(
            text.startswith(prefix) for prefix in ["查", "看", "读", "搜", "检索", "show", "list", "get", "search"]
        ),
        "word_count": len(text.split()),
    }


# --- Layer 1: Fast Gate ---

def _layer1_autonomy(prompt: str, signals: dict[str, Any]) -> JudgmentResult:
    """自治判断: Can we proceed without human interruption?"""
    if signals["has_hard_boundary"]:
        return JudgmentResult(
            name="自治判断",
            decision=Decision.BLOCK,
            reason="Task involves login, authorization, payment, or irreversible action.",
        )
    if signals["is_irreversible"]:
        return JudgmentResult(
            name="自治判断",
            decision=Decision.ESCALATE,
            reason="Task may involve irreversible operations; escalate for deeper review.",
        )
    return JudgmentResult(
        name="自治判断",
        decision=Decision.PASS,
        reason="No hard boundary detected; autonomous execution is safe.",
    )


def _layer1_reuse(prompt: str, signals: dict[str, Any]) -> JudgmentResult:
    """能力复用判断: Can we reuse existing skills?"""
    # Quick check: if SKILLS_ROOT has matching skills, PASS
    if not SKILLS_ROOT.exists():
        return JudgmentResult(
            name="能力复用判断",
            decision=Decision.ESCALATE,
            reason="Skills root not found; cannot verify reuse.",
        )
    text = prompt.lower()
    skill_dirs = [d.name for d in SKILLS_ROOT.iterdir() if d.is_dir() and (d / "SKILL.md").exists()]
    matches = [name for name in skill_dirs if name.replace("-", " ") in text or name in text]
    if matches:
        return JudgmentResult(
            name="能力复用判断",
            decision=Decision.PASS,
            reason=f"Matched existing skills: {', '.join(matches[:3])}",
            detail=json.dumps(matches[:5]),
        )
    # Even without exact match, if it's a simple query, pass
    if signals["is_query_only"]:
        return JudgmentResult(
            name="能力复用判断",
            decision=Decision.PASS,
            reason="Simple query task; no special skill needed.",
        )
    return JudgmentResult(
        name="能力复用判断",
        decision=Decision.ESCALATE,
        reason="No direct skill match found; escalate for full routing.",
    )


def _run_layer1(prompt: str, signals: dict[str, Any]) -> LayerResult:
    t0 = time.monotonic()
    autonomy = _layer1_autonomy(prompt, signals)
    reuse = _layer1_reuse(prompt, signals)
    judgments = (autonomy, reuse)

    if any(j.decision == Decision.BLOCK for j in judgments):
        decision = Decision.BLOCK
    elif all(j.decision == Decision.PASS for j in judgments):
        decision = Decision.PASS
    else:
        decision = Decision.ESCALATE

    return LayerResult(layer=1, judgments=judgments, decision=decision, elapsed_ms=(time.monotonic() - t0) * 1000)


# --- Layer 2: Governance Hooks ---

def _layer2_global_optimum(prompt: str, signals: dict[str, Any], north_stars: list[str]) -> JudgmentResult:
    """全局最优判断: Is this the most important thing to do right now?"""
    if not north_stars:
        return JudgmentResult(
            name="全局最优判断",
            decision=Decision.PASS,
            reason="No north stars configured; cannot evaluate global priority.",
        )
    text = prompt.lower()
    aligned = [ns for ns in north_stars if any(word in text for word in ns.lower().split())]
    if aligned:
        return JudgmentResult(
            name="全局最优判断",
            decision=Decision.PASS,
            reason=f"Aligned with north star: {aligned[0][:60]}",
        )
    return JudgmentResult(
        name="全局最优判断",
        decision=Decision.ESCALATE,
        reason="Task not clearly aligned with any current north star; needs human prioritization.",
    )


def _layer2_max_distortion(prompt: str, signals: dict[str, Any]) -> JudgmentResult:
    """最大失真判断: What's the biggest risk of pseudo-completion?"""
    # Known anti-patterns from the codebase
    anti_patterns = [
        (signals.get("mentions_feishu", False), "把飞书镜像误当成 canonical source"),
        (signals.get("is_irreversible", False), "执行不可逆操作前未确认验收标准"),
        ("口号" in prompt or "看起来完成" in prompt, "把规划语言写成已落地事实"),
    ]
    triggered = [(pat, msg) for pat, msg in anti_patterns if pat]
    if triggered:
        return JudgmentResult(
            name="最大失真判断",
            decision=Decision.ESCALATE,
            reason=triggered[0][1],
            detail=json.dumps([msg for _, msg in triggered]),
        )
    return JudgmentResult(
        name="最大失真判断",
        decision=Decision.PASS,
        reason="No known distortion pattern detected.",
    )


def _run_layer2(prompt: str, signals: dict[str, Any]) -> LayerResult:
    t0 = time.monotonic()
    north_stars = _load_north_stars()
    global_opt = _layer2_global_optimum(prompt, signals, north_stars)
    distortion = _layer2_max_distortion(prompt, signals)
    judgments = (global_opt, distortion)

    if any(j.decision == Decision.BLOCK for j in judgments):
        decision = Decision.BLOCK
    elif all(j.decision == Decision.PASS for j in judgments):
        decision = Decision.PASS
    else:
        decision = Decision.ESCALATE

    return LayerResult(layer=2, judgments=judgments, decision=decision, elapsed_ms=(time.monotonic() - t0) * 1000)


def _load_north_stars() -> list[str]:
    """Load current north stars from strategy artifacts."""
    path = ARTIFACTS_ROOT / "strategy" / "current" / "north-stars.json"
    if path.exists():
        try:
            data = read_json(path)
            if isinstance(data, list):
                return [str(item) for item in data]
        except Exception:
            pass
    return []


# --- Layer 3: Deep Review ---

def _layer3_verification(prompt: str, signals: dict[str, Any]) -> JudgmentResult:
    """验真判断: What evidence proves the result is real, not pseudo-complete?"""
    if signals["is_irreversible"]:
        return JudgmentResult(
            name="验真判断",
            decision=Decision.BLOCK,
            reason="Irreversible task requires explicit verification criteria before execution.",
        )
    return JudgmentResult(
        name="验真判断",
        decision=Decision.PASS,
        reason="Standard verification: artifact check + goal check.",
    )


def _layer3_evolution(prompt: str, signals: dict[str, Any]) -> JudgmentResult:
    """进化判断: What does this action contribute to the next iteration?"""
    evolution_keywords = ["进化", "复盘", "沉淀", "evolution", "review", "retrospect", "pattern"]
    text = prompt.lower()
    if any(kw in text for kw in evolution_keywords):
        return JudgmentResult(
            name="进化判断",
            decision=Decision.PASS,
            reason="Task explicitly targets evolution/review; high evolution value.",
        )
    return JudgmentResult(
        name="进化判断",
        decision=Decision.PASS,
        reason="Standard evolution: record effective/wasted patterns after closure.",
    )


def _run_layer3(prompt: str, signals: dict[str, Any]) -> LayerResult:
    t0 = time.monotonic()
    verification = _layer3_verification(prompt, signals)
    evolution = _layer3_evolution(prompt, signals)
    judgments = (verification, evolution)

    if any(j.decision == Decision.BLOCK for j in judgments):
        decision = Decision.BLOCK
    elif all(j.decision == Decision.PASS for j in judgments):
        decision = Decision.PASS
    else:
        decision = Decision.ESCALATE

    return LayerResult(layer=3, judgments=judgments, decision=decision, elapsed_ms=(time.monotonic() - t0) * 1000)


# --- Pipeline Orchestrator ---

def run_pipeline(prompt: str) -> PipelineResult:
    """Execute the 3-layer judgment pipeline with short-circuit logic."""
    t0 = time.monotonic()
    signals = _quick_signals(prompt)
    results: list[LayerResult] = []

    # Layer 1: Fast gate
    l1 = _run_layer1(prompt, signals)
    results.append(l1)
    if l1.decision == Decision.PASS:
        return PipelineResult(
            layers_executed=1,
            final_decision=Decision.PASS,
            results=tuple(results),
            short_circuited=True,
            total_elapsed_ms=(time.monotonic() - t0) * 1000,
        )
    if l1.decision == Decision.BLOCK:
        return PipelineResult(
            layers_executed=1,
            final_decision=Decision.BLOCK,
            results=tuple(results),
            short_circuited=True,
            total_elapsed_ms=(time.monotonic() - t0) * 1000,
        )

    # Layer 2: Governance hooks
    l2 = _run_layer2(prompt, signals)
    results.append(l2)
    if l2.decision == Decision.PASS:
        return PipelineResult(
            layers_executed=2,
            final_decision=Decision.PASS,
            results=tuple(results),
            short_circuited=True,
            total_elapsed_ms=(time.monotonic() - t0) * 1000,
        )
    if l2.decision == Decision.BLOCK:
        return PipelineResult(
            layers_executed=2,
            final_decision=Decision.BLOCK,
            results=tuple(results),
            short_circuited=True,
            total_elapsed_ms=(time.monotonic() - t0) * 1000,
        )

    # Layer 3: Deep review
    l3 = _run_layer3(prompt, signals)
    results.append(l3)

    return PipelineResult(
        layers_executed=3,
        final_decision=l3.decision,
        results=tuple(results),
        short_circuited=False,
        total_elapsed_ms=(time.monotonic() - t0) * 1000,
    )


# ═══════════════════════════════════════════════════════════════════════════
# MODULE 2: Run State Machine
# ═══════════════════════════════════════════════════════════════════════════
#
# States: routed → executing → evidence_collected → verifying → verified →
#         evolving → synced → closed
# Special: blocked (from any state, returns to routed after human unblock)
#
# Inspired by Claude Code's query.ts state machine pattern.

class RunState(Enum):
    ROUTED = "routed"
    EXECUTING = "executing"
    EVIDENCE_COLLECTED = "evidence_collected"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    EVOLVING = "evolving"
    SYNCED = "synced"
    CLOSED = "closed"
    BLOCKED = "blocked"


# Transition table: from_state -> list of (to_state, guard_name)
TRANSITIONS: dict[RunState, list[tuple[RunState, str]]] = {
    RunState.ROUTED: [
        (RunState.EXECUTING, "has_skill_combo"),
        (RunState.BLOCKED, "missing_requirement"),
    ],
    RunState.EXECUTING: [
        (RunState.EVIDENCE_COLLECTED, "execution_complete"),
        (RunState.BLOCKED, "execution_failed"),
    ],
    RunState.EVIDENCE_COLLECTED: [
        (RunState.VERIFYING, "evidence_file_exists"),
    ],
    RunState.VERIFYING: [
        (RunState.VERIFIED, "all_evidence_confirmed"),
        (RunState.BLOCKED, "evidence_refuted"),
    ],
    RunState.VERIFIED: [
        (RunState.EVOLVING, "evolution_record_written"),
    ],
    RunState.EVOLVING: [
        (RunState.SYNCED, "sync_complete"),
    ],
    RunState.SYNCED: [
        (RunState.CLOSED, "always"),
    ],
    RunState.BLOCKED: [
        (RunState.ROUTED, "human_unblocked"),
    ],
    RunState.CLOSED: [],
}


@dataclass
class RunStateRecord:
    """Mutable state record for a single run."""
    run_id: str
    current_state: RunState
    history: list[dict[str, str]]
    created_at: str
    updated_at: str
    blocked_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "current_state": self.current_state.value,
            "history": self.history,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "blocked_reason": self.blocked_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunStateRecord:
        return cls(
            run_id=data["run_id"],
            current_state=RunState(data["current_state"]),
            history=data.get("history", []),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            blocked_reason=data.get("blocked_reason", ""),
        )


def _state_file(run_dir: Path) -> Path:
    return run_dir / "state.json"


def _find_run_dir(run_id: str) -> Path:
    """Find a run directory by scanning date directories."""
    for date_dir in sorted(RUNS_ROOT.glob("*"), reverse=True):
        candidate = date_dir / run_id
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(f"run_id not found: {run_id}")


def load_state(run_id: str) -> RunStateRecord:
    """Load state for a run, inferring from artifacts if no state.json exists."""
    run_dir = _find_run_dir(run_id)
    sf = _state_file(run_dir)
    if sf.exists():
        return RunStateRecord.from_dict(read_json(sf))

    # Infer state from existing artifacts (backward compatibility)
    now = iso_now()
    if (run_dir / "close-task.json").exists():
        state = RunState.CLOSED
    elif (run_dir / "feishu-payload.json").exists():
        state = RunState.SYNCED
    elif (run_dir / "evolution.json").exists():
        state = RunState.EVOLVING
    elif (run_dir / "verification-report.json").exists():
        state = RunState.VERIFIED
    elif (run_dir / "route.json").exists():
        state = RunState.ROUTED
    else:
        state = RunState.ROUTED

    record = RunStateRecord(
        run_id=run_id,
        current_state=state,
        history=[{"state": state.value, "at": now, "via": "inferred"}],
        created_at=now,
        updated_at=now,
    )
    write_json(sf, record.to_dict())
    return record


def _check_guard(run_dir: Path, guard: str) -> bool:
    """Evaluate a guard condition against the run directory."""
    guards = {
        "has_skill_combo": lambda: (run_dir / "route.json").exists(),
        "execution_complete": lambda: True,  # Caller asserts this
        "execution_failed": lambda: False,
        "evidence_file_exists": lambda: any(run_dir.glob("evidence*.json")),
        "all_evidence_confirmed": lambda: _all_evidence_confirmed(run_dir),
        "evidence_refuted": lambda: _any_evidence_refuted(run_dir),
        "evolution_record_written": lambda: (run_dir / "evolution.json").exists(),
        "sync_complete": lambda: (run_dir / "feishu-payload.json").exists() or (run_dir / "sync-status.json").exists(),
        "always": lambda: True,
        "human_unblocked": lambda: True,  # Caller asserts this
        "missing_requirement": lambda: False,
    }
    checker = guards.get(guard)
    if checker is None:
        return False
    return checker()


def _all_evidence_confirmed(run_dir: Path) -> bool:
    vr = run_dir / "verification-report.json"
    if not vr.exists():
        return False
    try:
        report = read_json(vr)
        items = report.get("items", [])
        return bool(items) and all(item.get("status") == "confirmed" for item in items)
    except Exception:
        return False


def _any_evidence_refuted(run_dir: Path) -> bool:
    vr = run_dir / "verification-report.json"
    if not vr.exists():
        return False
    try:
        report = read_json(vr)
        return any(item.get("status") == "refuted" for item in report.get("items", []))
    except Exception:
        return False


def advance_state(run_id: str, target: RunState | None = None, reason: str = "") -> RunStateRecord:
    """Advance a run to the next valid state, or to a specific target state."""
    record = load_state(run_id)
    run_dir = _find_run_dir(run_id)
    current = record.current_state

    if current == RunState.CLOSED:
        return record  # Terminal state

    valid_transitions = TRANSITIONS.get(current, [])
    if target:
        # Validate requested transition
        for next_state, guard in valid_transitions:
            if next_state == target and _check_guard(run_dir, guard):
                return _apply_transition(record, run_dir, target, reason or guard)
        raise ValueError(
            f"Cannot transition {current.value} → {target.value}. "
            f"Valid: {[(s.value, g) for s, g in valid_transitions]}"
        )

    # Auto-advance: try each valid transition in order
    for next_state, guard in valid_transitions:
        if next_state != RunState.BLOCKED and _check_guard(run_dir, guard):
            return _apply_transition(record, run_dir, next_state, reason or guard)

    return record  # No valid transition available


def _apply_transition(record: RunStateRecord, run_dir: Path, target: RunState, reason: str) -> RunStateRecord:
    now = iso_now()
    record.history.append({
        "from": record.current_state.value,
        "to": target.value,
        "at": now,
        "reason": reason,
    })
    record.current_state = target
    record.updated_at = now
    if target == RunState.BLOCKED:
        record.blocked_reason = reason
    else:
        record.blocked_reason = ""
    write_json(_state_file(run_dir), record.to_dict())
    return record


def block_run(run_id: str, reason: str) -> RunStateRecord:
    """Block a run with a reason."""
    record = load_state(run_id)
    run_dir = _find_run_dir(run_id)
    return _apply_transition(record, run_dir, RunState.BLOCKED, reason)


# ═══════════════════════════════════════════════════════════════════════════
# MODULE 3: Adversarial Verification
# ═══════════════════════════════════════════════════════════════════════════
#
# Inspired by Claude Code's Verification Agent pattern:
# - Don't re-run the same checks; ASSUME the result is wrong and try to disprove it
# - Use independent tool paths for verification
# - Output a structured verification report

@dataclass(frozen=True)
class VerificationItem:
    claim: str
    method: str
    status: str  # "confirmed" | "refuted" | "uncertain"
    evidence: str


def verify_run(run_id: str, adversarial: bool = False) -> dict[str, Any]:
    """Verify a run's evidence bundle. If adversarial, assume claims are false."""
    run_dir = _find_run_dir(run_id)
    items: list[dict[str, str]] = []

    # Check 1: route.json exists and has selected skills
    route_path = run_dir / "route.json"
    if route_path.exists():
        route = read_json(route_path)
        selected = route.get("selected_skills", [])
        items.append({
            "claim": "Task was consciously routed",
            "method": "Check route.json for selected_skills",
            "status": "confirmed" if selected else "refuted",
            "evidence": f"selected_skills: {selected}" if selected else "No skills selected in route.json",
        })
    else:
        items.append({
            "claim": "Task was consciously routed",
            "method": "Check route.json exists",
            "status": "refuted",
            "evidence": "route.json not found",
        })

    # Check 2: evolution.json exists and has patterns
    evo_path = run_dir / "evolution.json"
    if evo_path.exists():
        evo = read_json(evo_path)
        effective = evo.get("effective_patterns", [])
        wasted = evo.get("wasted_patterns", [])
        candidates = evo.get("evolution_candidates", [])
        has_substance = bool(effective or wasted or candidates)
        if adversarial:
            # Adversarial: check if patterns are generic boilerplate
            generic_phrases = ["canonical", "closure", "standard", "default", "promote"]
            is_boilerplate = all(
                any(gp in str(p).lower() for gp in generic_phrases)
                for p in (effective + wasted + candidates)
                if p
            )
            status = "uncertain" if is_boilerplate else ("confirmed" if has_substance else "refuted")
            evidence = "Patterns appear to be boilerplate" if is_boilerplate else f"effective: {len(effective)}, wasted: {len(wasted)}, candidates: {len(candidates)}"
        else:
            status = "confirmed" if has_substance else "refuted"
            evidence = f"effective: {len(effective)}, wasted: {len(wasted)}, candidates: {len(candidates)}"
        items.append({
            "claim": "Evolution record has substantive patterns",
            "method": "Check evolution.json for non-empty patterns",
            "status": status,
            "evidence": evidence,
        })
    else:
        items.append({
            "claim": "Evolution record exists",
            "method": "Check evolution.json exists",
            "status": "refuted",
            "evidence": "evolution.json not found",
        })

    # Check 3: Feishu sync status
    feishu_payload_path = run_dir / "feishu-payload.json"
    if feishu_payload_path.exists():
        if adversarial:
            # Adversarial: verify the payload has actual record data, not just metadata
            try:
                payload = read_json(feishu_payload_path)
                records = payload.get("records", [])
                has_fields = all(bool(r.get("fields")) for r in records) if records else False
                items.append({
                    "claim": "Feishu payload contains real record data",
                    "method": "Inspect feishu-payload.json records and fields",
                    "status": "confirmed" if has_fields else "uncertain",
                    "evidence": f"{len(records)} records, fields_present: {has_fields}",
                })
            except Exception as e:
                items.append({
                    "claim": "Feishu payload is valid JSON",
                    "method": "Parse feishu-payload.json",
                    "status": "refuted",
                    "evidence": str(e),
                })
        else:
            items.append({
                "claim": "Feishu sync payload exists",
                "method": "Check feishu-payload.json exists",
                "status": "confirmed",
                "evidence": str(feishu_payload_path),
            })
    else:
        items.append({
            "claim": "Feishu sync payload exists",
            "method": "Check feishu-payload.json exists",
            "status": "uncertain",
            "evidence": "feishu-payload.json not found (may not be required for this task)",
        })

    # Check 4: Adversarial — cross-check run_id consistency
    if adversarial:
        run_ids_found = set()
        for json_file in run_dir.glob("*.json"):
            if json_file.name == "state.json":
                continue
            try:
                data = read_json(json_file)
                if isinstance(data, dict) and "run_id" in data:
                    run_ids_found.add(data["run_id"])
            except Exception:
                pass
        consistent = len(run_ids_found) <= 1 and (not run_ids_found or run_id in run_ids_found)
        items.append({
            "claim": "All artifacts reference the same run_id",
            "method": "Cross-check run_id across all JSON files",
            "status": "confirmed" if consistent else "refuted",
            "evidence": f"run_ids found: {run_ids_found}" if not consistent else "All consistent",
        })

    # Compute overall verdict
    statuses = [item["status"] for item in items]
    if all(s == "confirmed" for s in statuses):
        verdict = "verified"
    elif any(s == "refuted" for s in statuses):
        verdict = "failed"
    else:
        verdict = "inconclusive"

    report = {
        "run_id": run_id,
        "adversarial": adversarial,
        "verified_at": iso_now(),
        "verdict": verdict,
        "items": items,
        "summary": f"{sum(1 for s in statuses if s == 'confirmed')}/{len(statuses)} confirmed, "
                   f"{sum(1 for s in statuses if s == 'refuted')}/{len(statuses)} refuted, "
                   f"{sum(1 for s in statuses if s == 'uncertain')}/{len(statuses)} uncertain",
    }
    write_json(run_dir / "verification-report.json", report)
    return report


# ═══════════════════════════════════════════════════════════════════════════
# MODULE 4: Skill Harness (Recommendation Engine)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SkillMatch:
    name: str
    score: float
    matched_keywords: tuple[str, ...]
    layer: str


# Chinese → English skill keyword mapping for cross-language matching
_CN_EN_MAP: dict[str, list[str]] = {
    "飞书": ["feishu", "lark"],
    "多维表": ["bitable"],
    "同步": ["sync"],
    "进化": ["evolution"],
    "桥接": ["bridge"],
    "技能": ["skill"],
    "治理": ["governance"],
    "知识": ["knowledge"],
    "内容": ["content"],
    "设计": ["design"],
    "测试": ["testing"],
    "项目": ["project"],
    "营销": ["marketing"],
    "工程": ["engineering"],
    "支持": ["support"],
    "部署": ["deploy", "cloudflare"],
    "截图": ["screenshot"],
    "自动化": ["automator"],
    "仪表盘": ["dashboard"],
    "克隆": ["clone"],
    "评估": ["eval", "review"],
}


def harness_recommend(prompt: str, limit: int = 3) -> dict[str, Any]:
    """Recommend skill combination for a task prompt."""
    if not SKILLS_ROOT.exists():
        return {"error": "Skills root not found", "recommended_combo": []}

    text = prompt.lower()
    tokens = set(text.replace("/", " ").replace("-", " ").split())

    # Expand Chinese tokens to English equivalents
    extra_tokens: set[str] = set()
    for cn, en_list in _CN_EN_MAP.items():
        if cn in text:
            extra_tokens.update(en_list)
    tokens |= extra_tokens

    matches: list[SkillMatch] = []
    for skill_dir in SKILLS_ROOT.iterdir():
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        name = skill_dir.name
        name_tokens = set(name.replace("-", " ").split())

        # Score by token overlap in name
        overlap = tokens & name_tokens
        score = len(overlap)

        # Bonus: check SKILL.md description for keyword match
        try:
            content = skill_md.read_text(encoding="utf-8")[:500].lower()
            content_matches = sum(1 for t in tokens if t in content and len(t) > 2)
            score += content_matches * 0.5
        except Exception:
            pass

        if score > 0:
            layer = _classify_skill_layer(name)
            matches.append(SkillMatch(name=name, score=score, matched_keywords=tuple(overlap), layer=layer))

    matches.sort(key=lambda m: m.score, reverse=True)
    selected = matches[:limit]

    return {
        "prompt": prompt[:200],
        "recommended_combo": [
            {"skill": m.name, "score": round(m.score, 2), "layer": m.layer, "keywords": list(m.matched_keywords)}
            for m in selected
        ],
        "alternatives": [
            {"skill": m.name, "score": round(m.score, 2)}
            for m in matches[limit:limit + 5]
        ],
        "total_candidates_scored": len(matches),
        "human_decision_needed": len(selected) == 0,
    }


def _classify_skill_layer(name: str) -> str:
    if name.startswith(("ai-", "skill-", "self-")) or "knowledge" in name:
        return "元治理层"
    if name.startswith("agency-"):
        return "专家角色层"
    if name.startswith(("feishu-", "github-", "notion-")):
        return "平台集成层"
    return "垂直工作流层"


# ═══════════════════════════════════════════════════════════════════════════
# CLI Interface
# ═══════════════════════════════════════════════════════════════════════════

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="governance_engine",
        description="AI大管家 Governance Engine: 3-layer pipeline, state machine, adversarial verification.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # pipeline
    pipe = sub.add_parser("pipeline", help="Run the 3-layer judgment pipeline.")
    pipe.add_argument("--prompt", required=True, help="Task prompt to evaluate.")
    pipe.add_argument("--json", action="store_true", help="Output as JSON.")

    # state
    st = sub.add_parser("state", help="Manage run state machine.")
    st.add_argument("--run-id", required=True, help="Run ID.")
    st.add_argument("--action", choices=["show", "advance", "block"], default="show")
    st.add_argument("--target", help="Target state for advance.")
    st.add_argument("--reason", default="", help="Reason for block.")

    # verify
    ver = sub.add_parser("verify", help="Verify a run's evidence bundle.")
    ver.add_argument("--run-id", required=True, help="Run ID.")
    ver.add_argument("--adversarial", action="store_true", help="Use adversarial verification mode.")

    # harness
    har = sub.add_parser("harness", help="Recommend skill combination for a task.")
    har.add_argument("--prompt", required=True, help="Task prompt.")
    har.add_argument("--limit", type=int, default=3, help="Max skills to recommend.")

    args = parser.parse_args(argv)

    if args.command == "pipeline":
        result = run_pipeline(args.prompt)
        if args.json:
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(f"layers_executed: {result.layers_executed}")
            print(f"final_decision: {result.final_decision.value}")
            print(f"short_circuited: {result.short_circuited}")
            print(f"total_elapsed_ms: {result.total_elapsed_ms:.1f}")
            for lr in result.results:
                print(f"\n--- Layer {lr.layer} ({lr.elapsed_ms:.1f}ms) → {lr.decision.value} ---")
                for j in lr.judgments:
                    print(f"  {j.name}: {j.decision.value} — {j.reason}")
        return 0

    if args.command == "state":
        if args.action == "show":
            record = load_state(args.run_id)
            print(json.dumps(record.to_dict(), ensure_ascii=False, indent=2))
        elif args.action == "advance":
            target = RunState(args.target) if args.target else None
            record = advance_state(args.run_id, target=target, reason=args.reason)
            print(f"state: {record.current_state.value}")
            print(json.dumps(record.to_dict(), ensure_ascii=False, indent=2))
        elif args.action == "block":
            record = block_run(args.run_id, reason=args.reason or "Blocked by human")
            print(f"state: {record.current_state.value}")
        return 0

    if args.command == "verify":
        report = verify_run(args.run_id, adversarial=args.adversarial)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["verdict"] == "verified" else 1

    if args.command == "harness":
        result = harness_recommend(args.prompt, limit=args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
