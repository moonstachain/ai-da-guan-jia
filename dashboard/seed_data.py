"""Generate dashboard seed data for Feishu Miaoda."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_SEED_DIR = PACKAGE_DIR / "seed"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_control_overview(timestamp: str) -> list[dict[str, object]]:
    return [
        {
            "runtime_state": "healthy",
            "frontstage_focus": "R6 人类协作仪表盘",
            "active_round": "R6",
            "risk_level": "low",
            "pending_human_actions": 1,
            "system_blockers": 0,
            "last_evolution_round": "R5",
            "last_evolution_status": "completed",
            "total_tests_passed": 100,
            "total_commits": 5,
            "last_refresh": timestamp,
        }
    ]


def build_component_heatmap(timestamp: str) -> list[dict[str, object]]:
    rows = [
        ("governance", "direct", "mature", "medium", "—", "方向校准稳定", "liming", "AI大管家", False, "strong", "继续维持治理节奏"),
        ("governance", "control", "mature", "low", "—", "治理闭环稳定", "liming", "AI大管家", False, "strong", "保持 round 节奏"),
        ("governance", "execute", "mature", "low", "—", "执行链可验证", "liming", "AI大管家", False, "strong", "扩展执行覆盖面"),
        ("sales", "direct", "has_skeleton", "high", "strategy 链路待补全", "销售目标未完全挂接", "liming", "AI大管家", False, "moderate", "补齐 sales 战略链路"),
        ("sales", "control", "front_half", "high", "writeback + KPI 待补", "KPI 看板未落地", "liming", "AI大管家", False, "moderate", "补 KPI 与 writeback"),
        ("sales", "execute", "weak", "critical", "action catalog 待建", "执行动作缺标准件", "liming", "AI大管家", True, "weak", "建立 sales action catalog"),
        ("delivery", "direct", "not_started", "medium", "roadmap 待建", "交付路线图缺失", "liming", "AI大管家", True, "none", "定义 delivery roadmap"),
        ("delivery", "control", "not_started", "medium", "权限与边界待建", "交付治理边界未定义", "liming", "AI大管家", True, "none", "设计 delivery 权限边界"),
        ("delivery", "execute", "not_started", "high", "workflow 待建", "交付流程未编排", "liming", "AI大管家", True, "none", "搭交付 workflow"),
        ("clone", "direct", "not_started", "low", "设计态", "分身战略仍在设计", "liming", "AI大管家", True, "none", "明确 clone 目标"),
        ("clone", "control", "not_started", "low", "设计态", "分身治理规则待定", "liming", "AI大管家", True, "none", "定义 clone 治理规则"),
        ("clone", "execute", "not_started", "low", "设计态", "分身执行能力待定", "liming", "AI大管家", True, "none", "规划 clone 执行链"),
    ]
    return [
        {
            "component_domain": domain,
            "control_level": level,
            "maturity": maturity,
            "kpi_hint": kpi_hint,
            "current_gap": gap,
            "priority_band": priority,
            "human_owner": human_owner,
            "ai_copilot": ai_copilot,
            "owner_gap": owner_gap,
            "evidence_strength": evidence_strength,
            "next_action": next_action,
            "last_updated": timestamp,
        }
        for domain, level, maturity, priority, gap, kpi_hint, human_owner, ai_copilot, owner_gap, evidence_strength, next_action in rows
    ]


def build_strategy_linkage() -> list[dict[str, object]]:
    return [
        {
            "goal_id": "goal-governance-001",
            "goal_name": "构建 AI大管家 治理操作系统",
            "theme": "治理底座",
            "strategy": "通过 R1-R6 逐轮把类型、路由、MCP、飞书、闭环和仪表盘补齐",
            "component_domain": "governance",
            "control_level_scope": ["direct", "control", "execute"],
            "status": "active",
            "current_gap": "需要把治理状态进一步映射到人类可视化界面",
            "next_action": "推进 R6b 妙搭页面绑定",
            "evidence_ref": "R1-R5 commits + pytest outputs",
        },
        {
            "goal_id": "goal-sales-001",
            "goal_name": "补齐 sales 组件链路",
            "theme": "业务扩展",
            "strategy": "从 strategy linkage、KPI、action catalog 三段补全销售组件",
            "component_domain": "sales",
            "control_level_scope": ["direct", "control", "execute"],
            "status": "planned",
            "current_gap": "战略链路和执行 catalog 仍缺位",
            "next_action": "优先建设 sales execute 标准动作",
            "evidence_ref": "dashboard.component_heatmap.sales",
        },
    ]


def build_component_responsibility() -> list[dict[str, object]]:
    rows = [
        ("governance", "direct", "liming", "AI大管家", "goal-governance-001", "治理底座", "方向与节奏", False, "staffed", "R1-R5"),
        ("governance", "control", "liming", "AI大管家", "goal-governance-001", "治理底座", "规则与闭环", False, "staffed", "R1-R5"),
        ("governance", "execute", "liming", "AI大管家", "goal-governance-001", "治理底座", "执行与验真", False, "staffed", "R1-R5"),
        ("sales", "direct", "liming", "AI大管家", "goal-sales-001", "业务扩展", "销售战略", False, "staffed", "R6a"),
        ("sales", "control", "liming", "AI大管家", "goal-sales-001", "业务扩展", "销售指标", False, "staffed", "R6a"),
        ("sales", "execute", "", "AI大管家", "goal-sales-001", "业务扩展", "销售动作", True, "partial", "R6a"),
        ("delivery", "direct", "", "AI大管家", "", "待定", "交付路线", True, "partial", "R6a"),
        ("delivery", "control", "", "AI大管家", "", "待定", "交付边界", True, "partial", "R6a"),
        ("delivery", "execute", "", "AI大管家", "", "待定", "交付流程", True, "partial", "R6a"),
        ("clone", "direct", "", "AI大管家", "", "待定", "分身战略", True, "partial", "R6a"),
        ("clone", "control", "", "AI大管家", "", "待定", "分身治理", True, "partial", "R6a"),
        ("clone", "execute", "", "AI大管家", "", "待定", "分身执行", True, "partial", "R6a"),
    ]
    return [
        {
            "component_domain": domain,
            "control_level": level,
            "human_owner": human_owner,
            "ai_copilot": ai_copilot,
            "goal_ref": goal_ref,
            "theme_ref": theme_ref,
            "strategy_ref": strategy_ref,
            "owner_gap": owner_gap,
            "status": status,
            "evidence_ref": evidence_ref,
        }
        for domain, level, human_owner, ai_copilot, goal_ref, theme_ref, strategy_ref, owner_gap, status, evidence_ref in rows
    ]


def build_evolution_tracker() -> list[dict[str, object]]:
    rounds = [
        ("R1", "2026-03-16T00:00:00+00:00", "completed", "governance", "control", "10 个核心类型可执行", "", "R2 做技能路由", "验真力", 16, "00dda81", True),
        ("R2", "2026-03-16T00:30:00+00:00", "completed", "governance", "control", "skill manifest + router", "", "R3 做 MCP server", "路由力", 23, "15a3a04", True),
        ("R3", "2026-03-16T01:00:00+00:00", "completed", "governance", "control", "5 个 MCP tool 暴露", "", "R4 接飞书只读 MCP", "连接力", 15, "0eecb10", True),
        ("R4", "2026-03-16T01:30:00+00:00", "completed", "governance", "control", "飞书只读 MCP 就位", "", "R5 做 evidence pipeline", "感知力", 14, "d399ee9", True),
        ("R5", "2026-03-16T02:00:00+00:00", "completed", "governance", "control", "evidence pipeline 自动化", "", "R6 做人类协作仪表盘", "闭环力", 32, "e4ed607", True),
    ]
    return [
        {
            "round_id": round_id,
            "timestamp": timestamp,
            "status": status,
            "component_domain": component_domain,
            "control_level": control_level,
            "gained": gained,
            "wasted": wasted,
            "next_iterate": next_iterate,
            "capability_delta": capability_delta,
            "tests_passed": tests_passed,
            "commit_hash": commit_hash,
            "distortion_resolved": distortion_resolved,
        }
        for (
            round_id,
            timestamp,
            status,
            component_domain,
            control_level,
            gained,
            wasted,
            next_iterate,
            capability_delta,
            tests_passed,
            commit_hash,
            distortion_resolved,
        ) in rounds
    ]


def build_seed_payloads(timestamp: str | None = None) -> dict[str, list[dict[str, object]]]:
    current_time = timestamp or _now_iso()
    return {
        "control_overview.json": build_control_overview(current_time),
        "component_heatmap.json": build_component_heatmap(current_time),
        "strategy_linkage.json": build_strategy_linkage(),
        "component_responsibility.json": build_component_responsibility(),
        "evolution_tracker.json": build_evolution_tracker(),
    }


def generate_seed_data(output_dir: str | os.PathLike[str] | None = None) -> list[Path]:
    target_dir = Path(output_dir) if output_dir else DEFAULT_SEED_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    written_files: list[Path] = []
    for filename, payload in build_seed_payloads().items():
        destination = target_dir / filename
        destination.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        written_files.append(destination)
    return written_files


def main() -> None:
    output_dir = os.environ.get("YOS_DASHBOARD_SEED_DIR")
    written_files = generate_seed_data(output_dir)
    print("Generated dashboard seed data:")
    for path in written_files:
        print(path)


if __name__ == "__main__":
    main()
