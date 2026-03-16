from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from ontology.types import (
    Action,
    ComponentDomain,
    Confidence,
    ControlLevel,
    DecisionRecord,
    Entity,
    EvidenceAtom,
    WritebackEvent,
)
from ontology.validators import check_closure_readiness, validate_writeback_chain


@dataclass
class TaskRun:
    """一次完整的任务运行记录"""

    run_id: str
    round_id: str
    objective: str
    component_domain: ComponentDomain
    control_level: ControlLevel
    target_entity: Entity
    actions_taken: list[Action] = field(default_factory=list)
    evidence_collected: list[EvidenceAtom] = field(default_factory=list)
    writebacks: list[WritebackEvent] = field(default_factory=list)
    decisions: list[DecisionRecord] = field(default_factory=list)
    routing_rationale: str = ""
    human_boundary_log: list[str] = field(default_factory=list)


class EvidencePipeline:
    """
    闭环自动化管道。

    职责：
    1. 收集一次 TaskRun 中的所有证据
    2. 检查四条闭环规则
    3. 生成结构化 evolution log
    4. 写入 canonical artifacts
    """

    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = Path(artifacts_dir)

    def collect_evidence(self, run: TaskRun) -> dict[str, Any]:
        evidence_types: dict[str, int] = {}
        confidence_distribution: dict[str, int] = {}
        writeback_results: dict[str, int] = {}

        for evidence in run.evidence_collected:
            evidence_types[evidence.source_type.value] = evidence_types.get(evidence.source_type.value, 0) + 1
            confidence_distribution[evidence.confidence.value] = (
                confidence_distribution.get(evidence.confidence.value, 0) + 1
            )

        for writeback in run.writebacks:
            writeback_results[writeback.result.value] = writeback_results.get(writeback.result.value, 0) + 1

        return {
            "run_id": run.run_id,
            "evidence_count": len(run.evidence_collected),
            "evidence_types": evidence_types,
            "confidence_distribution": confidence_distribution,
            "writeback_count": len(run.writebacks),
            "writeback_results": writeback_results,
            "decision_count": len(run.decisions),
            "actions_count": len(run.actions_taken),
            "human_boundary_events": list(run.human_boundary_log),
        }

    def check_closure(self, run: TaskRun) -> dict[str, Any]:
        path_routed = bool(run.routing_rationale.strip())
        result_verified = any(
            evidence.confidence == Confidence.CONFIRMED for evidence in run.evidence_collected
        )
        evolution_recorded = True
        next_captured = False
        is_ready = check_closure_readiness(
            path_routed=path_routed,
            result_verified=result_verified,
            evolution_recorded=evolution_recorded,
            next_captured=next_captured,
        )
        missing = [
            name
            for name, value in [
                ("path_routed", path_routed),
                ("result_verified", result_verified),
                ("evolution_recorded", evolution_recorded),
                ("next_captured", next_captured),
            ]
            if not value
        ]
        return {
            "path_routed": path_routed,
            "result_verified": result_verified,
            "evolution_recorded": evolution_recorded,
            "next_captured": next_captured,
            "is_ready": is_ready,
            "missing": missing,
        }

    def validate_chains(self, run: TaskRun) -> list[str]:
        errors: list[str] = []
        actions_by_id = {action.action_id: action for action in run.actions_taken}
        evidence_by_id = {evidence.evidence_id: evidence for evidence in run.evidence_collected}

        for writeback in run.writebacks:
            action = actions_by_id.get(writeback.action_id)
            evidence = evidence_by_id.get(writeback.evidence_ref)
            if action is None:
                errors.append(f"missing action for writeback {writeback.writeback_id}: {writeback.action_id}")
                continue
            if evidence is None:
                errors.append(
                    f"missing evidence for writeback {writeback.writeback_id}: {writeback.evidence_ref}"
                )
                continue
            errors.extend(validate_writeback_chain(action, writeback, evidence))

        return errors

    def generate_evolution_log(
        self,
        run: TaskRun,
        gained: list[str],
        wasted: list[str],
        next_iterate: list[str],
        capability_delta: str,
        previous_distortion_resolved: bool = False,
        new_distortion: str = "",
    ) -> dict[str, Any]:
        if not gained:
            raise ValueError("gained 至少要有一条")
        if not next_iterate:
            raise ValueError("next_iterate 至少要有一条")

        closure_check = self.check_closure(run)
        closure_check["next_captured"] = True
        closure_check["is_ready"] = check_closure_readiness(
            path_routed=closure_check["path_routed"],
            result_verified=closure_check["result_verified"],
            evolution_recorded=closure_check["evolution_recorded"],
            next_captured=True,
        )
        closure_check["missing"] = [
            name
            for name, value in [
                ("path_routed", closure_check["path_routed"]),
                ("result_verified", closure_check["result_verified"]),
                ("evolution_recorded", closure_check["evolution_recorded"]),
                ("next_captured", closure_check["next_captured"]),
            ]
            if not value
        ]

        chain_errors = self.validate_chains(run)
        unresolved_human_boundary = [item for item in run.human_boundary_log if item.strip()]
        if unresolved_human_boundary:
            status = "blocked_needs_user"
        elif chain_errors:
            status = "failed_partial"
        elif closure_check["is_ready"]:
            status = "completed"
        else:
            status = "blocked_system"

        evolution_log = {
            "_run_id": run.run_id,
            "round_id": run.round_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "context": {
                "component_domain": run.component_domain.value,
                "control_level": run.control_level.value,
                "evolution_stage": "evidence_pipeline",
            },
            "closure_check": closure_check,
            "execution_evidence": {
                "files_created": [],
                "files_modified": [],
                "evidence_atoms": [evidence.evidence_id for evidence in run.evidence_collected],
            },
            "gained": list(gained),
            "wasted": list(wasted),
            "next_iterate": list(next_iterate),
            "capability_delta": capability_delta,
            "distortion_status": {
                "previous_distortion_resolved": previous_distortion_resolved,
                "new_distortion_identified": new_distortion,
            },
        }
        return evolution_log

    def save_evolution_log(self, evolution_log: dict[str, Any]) -> str:
        run_id = evolution_log.get("_run_id")
        if not run_id:
            raise ValueError("evolution_log 缺少 _run_id，无法生成保存路径")

        output_dir = self.artifacts_dir / "evolution-log"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{evolution_log['round_id']}-{run_id}.json"
        output_path.write_text(
            json.dumps(
                {key: value for key, value in evolution_log.items() if not key.startswith("_")},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return output_path.as_posix()

    def run_full_pipeline(
        self,
        run: TaskRun,
        gained: list[str],
        wasted: list[str],
        next_iterate: list[str],
        capability_delta: str,
        previous_distortion_resolved: bool = False,
        new_distortion: str = "",
    ) -> dict[str, Any]:
        evidence_summary = self.collect_evidence(run)
        chain_errors = self.validate_chains(run)
        evolution_log = self.generate_evolution_log(
            run=run,
            gained=gained,
            wasted=wasted,
            next_iterate=next_iterate,
            capability_delta=capability_delta,
            previous_distortion_resolved=previous_distortion_resolved,
            new_distortion=new_distortion,
        )
        saved_path = self.save_evolution_log(evolution_log)
        evolution_log["execution_evidence"]["files_created"] = [saved_path]

        closure_status = dict(evolution_log["closure_check"])
        return {
            "evolution_log": {key: value for key, value in evolution_log.items() if not key.startswith("_")},
            "saved_path": saved_path,
            "closure_status": closure_status,
            "chain_errors": chain_errors,
            "evidence_summary": evidence_summary,
        }


def close_task(
    run: TaskRun,
    gained: list[str],
    wasted: list[str],
    next_iterate: list[str],
    capability_delta: str,
    artifacts_dir: str = "artifacts",
    **kwargs: Any,
) -> dict[str, Any]:
    """
    顶层便捷入口。创建 EvidencePipeline 并执行 run_full_pipeline。
    """
    pipeline = EvidencePipeline(artifacts_dir)
    return pipeline.run_full_pipeline(
        run=run,
        gained=gained,
        wasted=wasted,
        next_iterate=next_iterate,
        capability_delta=capability_delta,
        **kwargs,
    )
