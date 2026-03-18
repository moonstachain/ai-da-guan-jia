"""原力OS白皮书与协同治理 Feishu 总控 base 同步入口。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from .contracts import PROJECT_ROOT
from .core import (
    build_inventory,
    ensure_inventory,
    iso_now,
    load_source_scope,
    now_local,
    read_json,
    stable_id,
    write_json,
    write_text,
)


CODEX_HOME = Path(os.getenv("CODEX_HOME", str(Path.home() / ".codex"))).expanduser().resolve()
AGENTS_HOME = Path.home() / ".agents"
DEFAULT_FEISHU_DOC_SCRIPT = AGENTS_HOME / "skills" / "feishu-doc-1.2.7" / "index.js"
DEFAULT_FEISHU_BITABLE_BRIDGE_SCRIPT = CODEX_HOME / "skills" / "feishu-bitable-bridge" / "scripts" / "feishu_bitable_bridge.py"
DEFAULT_HUB_TRANSPORT_STATUS_PATH = CODEX_HOME / "skills" / "ai-da-guan-jia" / "artifacts" / "ai-da-guan-jia" / "hub" / "current" / "transport-status.json"
DEFAULT_HUB_SOURCE_STATUS_PATH = CODEX_HOME / "skills" / "ai-da-guan-jia" / "artifacts" / "ai-da-guan-jia" / "hub" / "current" / "source-status.json"

CONTROL_BASE_CURRENT_ROOT = PROJECT_ROOT / "output" / "ai-da-guan-jia" / "control-base" / "current"
WHITEPAPER_ROOT = CONTROL_BASE_CURRENT_ROOT / "whitepaper"
PAYLOADS_ROOT = CONTROL_BASE_CURRENT_ROOT / "payloads"
SYNC_STATE_PATH = CONTROL_BASE_CURRENT_ROOT / "docs-sync-state.json"
STRATEGY_CURRENT_ROOT = PROJECT_ROOT / "work" / "ai-da-guan-jia" / "artifacts" / "ai-da-guan-jia" / "strategy" / "current"

FEISHU_ENV_VARS = ("FEISHU_APP_ID", "FEISHU_APP_SECRET")
FEISHU_OPENAPI_BASE = "https://open.feishu.cn"
CONTROL_LEVEL_VALUES = ("direct", "control", "execute")
PRIORITY_BAND_VALUES = ("P0", "P1", "P2", "P3")


def _field(
    name: str,
    english_name: str,
    canonical_path: str,
    *,
    field_type: str = "text",
    description: str = "",
    machine_written: bool = True,
    human_editable: bool = False,
) -> dict[str, Any]:
    return {
        "name": name,
        "english_name": english_name,
        "canonical_path": canonical_path,
        "type": field_type,
        "description": description,
        "machine_written": machine_written,
        "human_editable": human_editable,
    }


CONTROL_BASE_TABLE_SPECS: list[dict[str, Any]] = [
    {
        "table_id": "control_objects",
        "table_name": "总控对象主表",
        "description": "跨线程、任务、能力、来源与治理轨迹的总控入口。",
        "primary": _field("对象Key", "object_key", "derived.control_objects[].object_key", description="对象唯一键。"),
        "views": ["全部", "前台主线", "待你处理", "系统阻塞", "已完成", "后台队列"],
        "fields": [
            _field("对象类型", "object_type", "derived.control_objects[].object_type", description="对象所属家族。"),
            _field("对象标题", "object_title", "derived.control_objects[].object_title", description="对象的人类可读标题。"),
            _field("治理层级", "governance_level", "derived.control_objects[].governance_level", description="L1 运营对象层或 L2 治理轨迹层。"),
            _field("运营分段", "operations_segment", "derived.control_objects[].operations_segment", description="frontstage/background/wait_human 等运营分段。"),
            _field("对象状态", "object_status", "derived.control_objects[].object_status", description="当前对象状态。"),
            _field("目标ID", "goal_id", "derived.control_objects[].goal_id", description="关联目标。"),
            _field("空间ID", "space_id", "derived.control_objects[].space_id", description="关联实例空间。"),
            _field("模块ID", "module_id", "derived.control_objects[].module_id", description="关联模块。"),
            _field("component_domain", "component_domain", "derived.control_objects[].component_domain", description="CBM 组件域或当前对象所属组件。"),
            _field("control_level", "control_level", "derived.control_objects[].control_level", description="CBM 纵线 direct/control/execute。"),
            _field("priority_band", "priority_band", "derived.control_objects[].priority_band", description="统一优先级带。"),
            _field("线程ID", "thread_id", "derived.control_objects[].thread_id", description="关联线程。"),
            _field("父对象ID", "parent_object_id", "derived.control_objects[].parent_object_id", description="父级任务或父级对象。"),
            _field("负责人模式", "owner_mode", "derived.control_objects[].owner_mode", description="人类、AI 或混合治理方式。"),
            _field("human_boundary_state", "human_boundary_state", "derived.control_objects[].human_boundary_state", description="当前是否卡在人类边界。"),
            _field("当前摘要", "current_summary", "derived.control_objects[].current_summary", description="当前阶段最关键的一句话摘要。"),
            _field("阻塞原因", "blocker_reason", "derived.control_objects[].blocker_reason", description="当前阻塞或风险。"),
            _field("需要人类输入", "required_human_input", "derived.control_objects[].required_human_input", description="必须由你补的输入。"),
            _field("下一步动作", "next_action", "derived.control_objects[].next_action", description="当前最小下一步。"),
            _field("证据入口", "evidence_entry", "derived.control_objects[].evidence_entry", description="主证据或主工件入口。"),
            _field("evidence_strength", "evidence_strength", "derived.control_objects[].evidence_strength", description="证据强度或覆盖度判断。"),
            _field("来源文件", "source_file", "derived.control_objects[].source_file", description="事实源或回写源。"),
            _field("置信度", "confidence", "derived.control_objects[].confidence", field_type="number", description="记录可信度。"),
            _field("最近更新时间", "updated_at", "derived.control_objects[].updated_at", description="最近更新时间。"),
        ],
    },
    {
        "table_id": "threads",
        "table_name": "线程总表",
        "description": "原力OS 当前所有线程的运行状态总表。",
        "primary": _field("Thread ID", "thread_id", "threads[].thread_id", description="线程唯一主键。"),
        "views": ["全部"],
        "fields": [
            _field("标题", "title", "threads[].title", description="线程标题。"),
            _field("主题", "theme", "threads[].theme", description="主题或主题簇。"),
            _field("策略ID", "strategy_id", "threads[].strategy_id", description="关联策略。"),
            _field("实验ID", "experiment_id", "threads[].experiment_id", description="关联实验。"),
            _field("工作流ID", "workflow_id", "threads[].workflow_id", description="关联工作流。"),
            _field("目标ID", "goal_id", "threads[].goal_id", description="关联目标。"),
            _field("空间ID", "space_id", "threads[].space_id", description="所属空间。"),
            _field("模块ID", "module_id", "threads[].module_id", description="所属模块。"),
            _field("component_domain", "component_domain", "threads[].component_domain", description="线程映射到的 CBM 组件域。"),
            _field("control_level", "control_level", "threads[].control_level", description="线程所在 control 纵线。"),
            _field("priority_band", "priority_band", "threads[].priority_band", description="线程优先级带。"),
            _field("状态", "status", "threads[].status", description="当前线程状态。"),
            _field("运营分段", "operations_segment", "derived.threads[].operations_segment", description="frontstage/background/wait_human 等运营分段。"),
            _field("last_activity_at", "last_activity_at", "derived.threads[].last_activity_at", field_type="date", description="最近一次治理动作时间。"),
            _field("last_activity_type", "last_activity_type", "derived.threads[].last_activity_type", description="最近动作类型，通常为 decision 或 writeback。"),
            _field("last_activity_summary", "last_activity_summary", "derived.threads[].last_activity_summary", description="最近动作的一句话摘要。"),
            _field("frontstage_focus_object", "frontstage_focus_object", "derived.threads[].frontstage_focus_object", description="当前前台真正推进的对象。"),
            _field("来源Run ID", "source_run_id", "threads[].source_run_id", description="来源运行编号。"),
            _field("进入方式", "entry_mode", "threads[].entry_mode", description="线程进入方式。"),
            _field("父任务ID", "parent_task_id", "threads[].parent_task_id", description="父任务。"),
            _field("managed_by", "managed_by", "threads[].managed_by", description="线程由谁管理。"),
            _field("编排状态", "orchestration_state", "threads[].orchestration_state", description="编排状态。"),
            _field("闭环状态", "closure_state", "threads[].closure_state", description="闭环状态。"),
            _field("闭环Run ID", "closure_run_id", "threads[].closure_run_id", description="闭环运行编号。"),
            _field("阻塞原因", "blocker_reason", "threads[].blocker_reason", description="线程阻塞原因。"),
            _field("需要人类输入", "required_human_input", "threads[].required_human_input", description="线程所需人类输入。"),
            _field("开放问题", "open_questions", "threads[].open_questions", description="仍待回答的问题。"),
            _field("晨检标记", "morning_review_flag", "threads[].morning_review_flag", description="是否进入晨检。"),
            _field("下次复查日", "next_review_date", "threads[].next_review_date", field_type="date", description="下次复查日期。"),
            _field("来源文件", "source_ref", "threads[].source_ref", description="来源文件或工件。"),
            _field("evidence_strength", "evidence_strength", "threads[].evidence_strength", description="线程证据强度。"),
            _field("置信度", "confidence", "threads[].confidence", field_type="number", description="记录可信度。"),
            _field("更新时间", "updated_at", "threads[].updated_at", description="更新时间。"),
        ],
    },
    {
        "table_id": "tasks",
        "table_name": "任务总表",
        "description": "原力OS 当前任务与执行单总表。",
        "primary": _field("Task ID", "task_id", "tasks[].task_id", description="任务唯一主键。"),
        "views": ["全部"],
        "fields": [
            _field("标题", "title", "tasks[].title", description="任务标题。"),
            _field("Thread ID", "thread_id", "tasks[].thread_id", description="关联线程。"),
            _field("目标ID", "goal_id", "tasks[].goal_id", description="关联目标。"),
            _field("空间ID", "space_id", "tasks[].space_id", description="所属空间。"),
            _field("目标主体ID", "target_subject_id", "tasks[].target_subject_id", description="目标主体。"),
            _field("目标模块ID", "target_module_id", "tasks[].target_module_id", description="目标模块。"),
            _field("模块编码", "module_code", "tasks[].module_code", description="模块短编码。"),
            _field("component_domain", "component_domain", "tasks[].component_domain", description="任务映射到的 CBM 组件域。"),
            _field("control_level", "control_level", "tasks[].control_level", description="任务所在 control 纵线。"),
            _field("priority_band", "priority_band", "tasks[].priority_band", description="统一优先级带。"),
            _field("模块Owner主体ID", "owner_subject_id", "tasks[].owner_subject_id", description="模块 Owner 主体。"),
            _field("模块AI主体ID", "ai_subject_id", "tasks[].ai_subject_id", description="模块 AI copilot 主体。"),
            _field("业务副手主体ID", "deputy_subject_id", "tasks[].deputy_subject_id", description="业务副手主体。"),
            _field("状态", "status", "tasks[].status", description="当前状态。"),
            _field("运营分段", "operations_segment", "derived.tasks[].operations_segment", description="frontstage/background/wait_human 等运营分段。"),
            _field("优先级", "priority", "tasks[].priority", description="优先级。"),
            _field("owner_mode", "owner_mode", "tasks[].owner_mode", description="负责人模式。"),
            _field("任务类型", "task_kind", "tasks[].task_kind", description="parent 或 execution。"),
            _field("父任务ID", "parent_task_id", "tasks[].parent_task_id", description="父任务。"),
            _field("依赖任务IDs", "depends_on_task_ids", "tasks[].depends_on_task_ids", description="依赖任务列表。"),
            _field("managed_by", "managed_by", "tasks[].managed_by", description="任务由谁管理。"),
            _field("intake_run_id", "intake_run_id", "tasks[].intake_run_id", description="intake 运行编号。"),
            _field("delegation_mode", "delegation_mode", "tasks[].delegation_mode", description="分派模式。"),
            _field("人类边界状态", "human_boundary_state", "tasks[].human_boundary_state", description="人类边界状态。"),
            _field("已选技能", "selected_skills", "tasks[].selected_skills", description="推荐或已选技能。"),
            _field("验真状态", "verification_state", "tasks[].verification_state", description="验真状态。"),
            _field("验真目标", "verification_target", "tasks[].verification_target", description="验真目标。"),
            _field("打断条件", "interrupt_only_if", "tasks[].interrupt_only_if", description="何时才打断你。"),
            _field("证据入口", "evidence_ref", "tasks[].evidence_ref", description="主证据入口。"),
            _field("执行模式", "execution_mode", "tasks[].execution_mode", description="repo_builtin/skill_cli/handoff_only。"),
            _field("runner_state", "runner_state", "tasks[].runner_state", description="执行器状态。"),
            _field("执行工件", "run_artifact_ref", "tasks[].run_artifact_ref", description="执行工件目录。"),
            _field("结果摘要", "result_summary", "tasks[].result_summary", description="结果摘要。"),
            _field("证据列表", "evidence_refs", "tasks[].evidence_refs", description="证据列表。"),
            _field("evidence_strength", "evidence_strength", "tasks[].evidence_strength", description="任务证据强度。"),
            _field("progress_truth_label", "progress_truth_label", "derived.tasks[].progress_truth_label", description="真推进/表面推进/真实阻塞/陈旧未验真的四档标签。"),
            _field("kpi_gap", "kpi_gap", "tasks[].kpi_gap", description="任务对应的 KPI 或能力缺口。"),
            _field("闭环状态", "closure_state", "tasks[].closure_state", description="闭环状态。"),
            _field("闭环Run ID", "closure_run_id", "tasks[].closure_run_id", description="闭环运行编号。"),
            _field("阻塞原因", "blocker_reason", "tasks[].blocker_reason", description="阻塞原因。"),
            _field("需要人类输入", "required_human_input", "tasks[].required_human_input", description="需要你补的输入。"),
            _field("下一步", "next_action", "tasks[].next_action", description="当前最小下一步。"),
            _field("来源文件", "source_ref", "tasks[].source_ref", description="来源文件。"),
            _field("置信度", "confidence", "tasks[].confidence", field_type="number", description="记录可信度。"),
            _field("最后更新时间", "last_updated_at", "tasks[].last_updated_at", description="任务最后更新时间。"),
            _field("更新时间", "updated_at", "tasks[].updated_at", description="更新时间。"),
        ],
    },
    {
        "table_id": "strategic_linkage",
        "table_name": "战略链路表",
        "description": "把 goal/theme/strategy/experiment/workflow 正式桥接到组件域和 control 纵线。",
        "primary": _field("战略链路Key", "strategic_linkage_key", "derived.strategic_linkage[].strategic_linkage_key", description="战略链路唯一键。"),
        "views": ["全部"],
        "fields": [
            _field("goal_id", "goal_id", "derived.strategic_linkage[].goal_id", description="治理目标 ID。"),
            _field("goal_title", "goal_title", "derived.strategic_linkage[].goal_title", description="治理目标标题。"),
            _field("theme_id", "theme_id", "derived.strategic_linkage[].theme_id", description="主题 ID。"),
            _field("theme_title", "theme_title", "derived.strategic_linkage[].theme_title", description="主题标题。"),
            _field("strategy_id", "strategy_id", "derived.strategic_linkage[].strategy_id", description="策略 ID。"),
            _field("strategy_title", "strategy_title", "derived.strategic_linkage[].strategy_title", description="策略标题。"),
            _field("experiment_id", "experiment_id", "derived.strategic_linkage[].experiment_id", description="实验 ID。"),
            _field("experiment_title", "experiment_title", "derived.strategic_linkage[].experiment_title", description="实验标题。"),
            _field("workflow_id", "workflow_id", "derived.strategic_linkage[].workflow_id", description="工作流 ID。"),
            _field("workflow_title", "workflow_title", "derived.strategic_linkage[].workflow_title", description="工作流标题。"),
            _field("component_domain", "component_domain", "derived.strategic_linkage[].component_domain", description="链路映射到的组件域。"),
            _field("control_level_scope", "control_level_scope", "derived.strategic_linkage[].control_level_scope", description="这条链路覆盖的 control 纵线。"),
            _field("status", "status", "derived.strategic_linkage[].status", description="链路状态或验证状态。"),
            _field("current_gap", "current_gap", "derived.strategic_linkage[].current_gap", description="当前最大 gap。"),
            _field("next_action", "next_action", "derived.strategic_linkage[].next_action", description="当前最小下一步。"),
            _field("evidence_ref", "evidence_ref", "derived.strategic_linkage[].evidence_ref", description="主证据入口。"),
            _field("source_ref", "source_ref", "derived.strategic_linkage[].source_ref", description="来源工件。"),
            _field("updated_at", "updated_at", "derived.strategic_linkage[].updated_at", description="更新时间。"),
        ],
    },
    {
        "table_id": "cbm_component_responsibility",
        "table_name": "CBM组件责任表",
        "description": "组件域、owner、copilot 与战略归属的责任桥表。",
        "primary": _field("组件责任Key", "component_responsibility_key", "derived.cbm_component_responsibility[].component_responsibility_key", description="组件责任唯一键。"),
        "views": ["全部"],
        "fields": [
            _field("component_domain", "component_domain", "derived.cbm_component_responsibility[].component_domain", description="组件域。"),
            _field("control_level_scope", "control_level_scope", "derived.cbm_component_responsibility[].control_level_scope", description="组件覆盖的 control 纵线范围。"),
            _field("human_owner", "human_owner", "derived.cbm_component_responsibility[].human_owner", description="人类 owner。"),
            _field("ai_copilot", "ai_copilot", "derived.cbm_component_responsibility[].ai_copilot", description="AI copilot。"),
            _field("goal_id", "goal_id", "derived.cbm_component_responsibility[].goal_id", description="绑定目标。"),
            _field("theme_id", "theme_id", "derived.cbm_component_responsibility[].theme_id", description="绑定主题。"),
            _field("strategy_id", "strategy_id", "derived.cbm_component_responsibility[].strategy_id", description="绑定策略。"),
            _field("workflow_id", "workflow_id", "derived.cbm_component_responsibility[].workflow_id", description="绑定工作流。"),
            _field("owner_gap", "owner_gap", "derived.cbm_component_responsibility[].owner_gap", description="human_owner/ai_copilot 缺位标签。"),
            _field("owner_mode", "owner_mode", "derived.cbm_component_responsibility[].owner_mode", description="当前 owner 模式。"),
            _field("status", "status", "derived.cbm_component_responsibility[].status", description="状态。"),
            _field("evidence_ref", "evidence_ref", "derived.cbm_component_responsibility[].evidence_ref", description="主证据入口。"),
            _field("updated_at", "updated_at", "derived.cbm_component_responsibility[].updated_at", description="更新时间。"),
        ],
    },
    {
        "table_id": "cbm_component_heatmap",
        "table_name": "CBM组件热图表",
        "description": "组件域 x control 纵线 x gap x priority 的派生热图。",
        "primary": _field("热图Key", "component_heatmap_key", "derived.cbm_component_heatmap[].component_heatmap_key", description="组件热图唯一键。"),
        "views": ["全部"],
        "fields": [
            _field("component_domain", "component_domain", "derived.cbm_component_heatmap[].component_domain", description="组件域。"),
            _field("control_level", "control_level", "derived.cbm_component_heatmap[].control_level", description="control 纵线。"),
            _field("kpi_hint", "kpi_hint", "derived.cbm_component_heatmap[].kpi_hint", description="组件 KPI 提示。"),
            _field("current_gap", "current_gap", "derived.cbm_component_heatmap[].current_gap", description="分级 gap 前缀加缺口说明。"),
            _field("priority_band", "priority_band", "derived.cbm_component_heatmap[].priority_band", description="优先级带。"),
            _field("next_action", "next_action", "derived.cbm_component_heatmap[].next_action", description="当前最小下一步。"),
            _field("owner_mode", "owner_mode", "derived.cbm_component_heatmap[].owner_mode", description="owner 模式。"),
            _field("evidence_strength", "evidence_strength", "derived.cbm_component_heatmap[].evidence_strength", description="证据强度。"),
            _field("latest_decision_id", "latest_decision_id", "derived.cbm_component_heatmap[].latest_decision_id", description="最近决策 ID。"),
            _field("latest_writeback_id", "latest_writeback_id", "derived.cbm_component_heatmap[].latest_writeback_id", description="最近写回 ID。"),
            _field("status", "status", "derived.cbm_component_heatmap[].status", description="热图状态。"),
            _field("evidence_ref", "evidence_ref", "derived.cbm_component_heatmap[].evidence_ref", description="主证据入口。"),
            _field("updated_at", "updated_at", "derived.cbm_component_heatmap[].updated_at", description="更新时间。"),
        ],
    },
    {
        "table_id": "skills_capabilities",
        "table_name": "技能与能力表",
        "description": "原力OS 当前可调用技能与能力约束。",
        "primary": _field("能力Key", "capability_key", "derived.skills_capabilities[].capability_key", description="技能或能力唯一键。"),
        "views": ["全部"],
        "fields": [
            _field("记录类型", "record_type", "derived.skills_capabilities[].record_type", description="skill 或 capability。"),
            _field("对象ID", "object_id", "derived.skills_capabilities[].object_id", description="对应 skill_id 或 capability_id。"),
            _field("名称", "name", "derived.skills_capabilities[].name", description="技能短名。"),
            _field("标题", "title", "derived.skills_capabilities[].title", description="标题。"),
            _field("cluster_or_actor", "cluster_or_actor", "derived.skills_capabilities[].cluster_or_actor", description="技能簇或 actor_type。"),
            _field("role", "role", "derived.skills_capabilities[].role", description="角色。"),
            _field("verification_strength", "verification_strength", "derived.skills_capabilities[].verification_strength", field_type="number", description="验真强度。"),
            _field("cost_efficiency", "cost_efficiency", "derived.skills_capabilities[].cost_efficiency", field_type="number", description="成本效率。"),
            _field("auth_reuse", "auth_reuse", "derived.skills_capabilities[].auth_reuse", field_type="number", description="登录态复用度。"),
            _field("complexity_penalty", "complexity_penalty", "derived.skills_capabilities[].complexity_penalty", field_type="number", description="复杂度惩罚。"),
            _field("routing_credit", "routing_credit", "derived.skills_capabilities[].routing_credit", field_type="number", description="路由信用。"),
            _field("allowed_action_ids", "allowed_action_ids", "derived.skills_capabilities[].allowed_action_ids", description="允许动作列表。"),
            _field("bound_policy_ids", "bound_policy_ids", "derived.skills_capabilities[].bound_policy_ids", description="绑定策略。"),
            _field("requires_human_approval", "requires_human_approval", "derived.skills_capabilities[].requires_human_approval", description="是否需要人类审批。"),
            _field("approval_latency", "approval_latency", "derived.skills_capabilities[].approval_latency", description="审批延迟代理值。"),
            _field("approval_block_count", "approval_block_count", "derived.skills_capabilities[].approval_block_count", field_type="number", description="审批阻塞次数代理值。"),
            _field("friction_score", "friction_score", "derived.skills_capabilities[].friction_score", field_type="number", description="授权摩擦综合分。"),
            _field("状态", "status", "derived.skills_capabilities[].status", description="状态。"),
            _field("来源文件", "source_ref", "derived.skills_capabilities[].source_ref", description="来源文件。"),
            _field("置信度", "confidence", "derived.skills_capabilities[].confidence", field_type="number", description="可信度。"),
            _field("更新时间", "updated_at", "derived.skills_capabilities[].updated_at", description="更新时间。"),
        ],
    },
    {
        "table_id": "source_feeds",
        "table_name": "数据源同步表",
        "description": "原力OS 数据源、transport 与三端状态总表。",
        "primary": _field("Source Feed ID", "source_feed_id", "source_feeds[].source_feed_id", description="来源唯一主键。"),
        "views": ["全部"],
        "fields": [
            _field("标题", "title", "source_feeds[].title", description="来源标题。"),
            _field("来源家族", "source_family", "source_feeds[].source_family", description="来源家族。"),
            _field("注册组", "registry_group", "source_feeds[].registry_group", description="注册分组。"),
            _field("根路径", "root_path", "source_feeds[].root_path", description="来源根路径。"),
            _field("来源设备", "origin_device", "source_feeds[].origin_device", description="来源设备。"),
            _field("所有者账号ID", "owner_account_id", "source_feeds[].owner_account_id", description="所有者账号。"),
            _field("状态", "status", "source_feeds[].status", description="来源状态。"),
            _field("已识别文件数", "recognized_file_count", "source_feeds[].recognized_file_count", field_type="number", description="识别文件数。"),
            _field("未分类文件数", "unclassified_file_count", "source_feeds[].unclassified_file_count", field_type="number", description="未分类文件数。"),
            _field("最近扫描时间", "last_scanned_at", "source_feeds[].last_scanned_at", field_type="date", description="最近扫描时间。"),
            _field("transport_repo", "transport_repo", "derived.source_feeds[].transport_repo", description="当前 transport repo。"),
            _field("remote_reachable", "remote_reachable", "derived.source_feeds[].remote_reachable", description="远端是否可达。"),
            _field("github_backend", "github_backend", "derived.source_feeds[].github_backend", description="GitHub backend。"),
            _field("connected_sources_snapshot", "connected_sources_snapshot", "derived.source_feeds[].connected_sources_snapshot", description="当前已接入来源快照。"),
            _field("missing_sources_snapshot", "missing_sources_snapshot", "derived.source_feeds[].missing_sources_snapshot", description="当前缺失来源快照。"),
            _field("health_bucket", "health_bucket", "derived.source_feeds[].health_bucket", description="healthy/degraded/broken/unknown 健康桶。"),
            _field("来源文件", "source_ref", "source_feeds[].source_ref", description="来源文件。"),
            _field("置信度", "confidence", "source_feeds[].confidence", field_type="number", description="可信度。"),
            _field("更新时间", "updated_at", "source_feeds[].updated_at", description="更新时间。"),
        ],
    },
    {
        "table_id": "review_runs",
        "table_name": "Review批次表",
        "description": "原力OS review 批次与拍板上下文。",
        "primary": _field("Review ID", "review_id", "review_runs[].review_id", description="review 唯一主键。"),
        "views": ["全部"],
        "fields": [
            _field("评审日期", "review_date", "review_runs[].review_date", field_type="date", description="评审日期。"),
            _field("范围", "scope", "review_runs[].scope", description="评审范围。"),
            _field("摘要", "summary", "review_runs[].summary", description="摘要。"),
            _field("top_risks", "top_risks", "review_runs[].top_risks", description="主要风险。"),
            _field("candidate_actions", "candidate_actions", "review_runs[].candidate_actions", description="候选动作。"),
            _field("human_decision", "human_decision", "review_runs[].human_decision", description="人类拍板。"),
            _field("sync_state", "sync_state", "review_runs[].sync_state", description="同步状态。"),
            _field("来源文件", "source_ref", "review_runs[].source_ref", description="来源文件。"),
            _field("置信度", "confidence", "review_runs[].confidence", field_type="number", description="可信度。"),
            _field("更新时间", "updated_at", "review_runs[].updated_at", description="更新时间。"),
        ],
    },
    {
        "table_id": "decision_records",
        "table_name": "决策记录表",
        "description": "原力OS 关键决策与理由追踪表。",
        "primary": _field("Decision ID", "decision_id", "decision_records[].decision_id", description="决策唯一主键。"),
        "views": ["全部"],
        "fields": [
            _field("标题", "title", "decision_records[].title", description="决策标题。"),
            _field("decision_type", "decision_type", "decision_records[].decision_type", description="决策类型。"),
            _field("decision_state", "decision_state", "decision_records[].decision_state", description="决策状态。"),
            _field("target_entity_ids", "target_entity_ids", "decision_records[].target_entity_ids", description="目标实体列表。"),
            _field("decision_summary", "decision_summary", "decision_records[].decision_summary", description="决策摘要。"),
            _field("rationale", "rationale", "decision_records[].rationale", description="决策依据。"),
            _field("evidence_refs", "evidence_refs", "decision_records[].evidence_refs", description="证据引用。"),
            _field("decided_by", "decided_by", "decision_records[].decided_by", description="决策人。"),
            _field("decision_time", "decision_time", "decision_records[].decision_time", field_type="date", description="决策时间。"),
            _field("writeback_event_ids", "writeback_event_ids", "decision_records[].writeback_event_ids", description="关联写回事件。"),
            _field("来源文件", "source_ref", "decision_records[].source_ref", description="来源文件。"),
            _field("置信度", "confidence", "decision_records[].confidence", field_type="number", description="可信度。"),
            _field("更新时间", "updated_at", "decision_records[].updated_at", description="更新时间。"),
        ],
    },
    {
        "table_id": "governance_events",
        "table_name": "治理动作与写回表",
        "description": "动作 contract 与写回事件统一视图。",
        "primary": _field("治理事件Key", "governance_event_key", "derived.governance_events[].governance_event_key", description="动作或写回事件唯一键。"),
        "views": ["全部"],
        "fields": [
            _field("记录类型", "record_type", "derived.governance_events[].record_type", description="review/decision/action/writeback。"),
            _field("对象ID", "object_id", "derived.governance_events[].object_id", description="动作或写回对象 ID。"),
            _field("标题", "title", "derived.governance_events[].title", description="标题。"),
            _field("scenario_or_trigger", "scenario_or_trigger", "derived.governance_events[].scenario_or_trigger", description="场景或触发器。"),
            _field("状态", "status", "derived.governance_events[].status", description="状态。"),
            _field("target_entity_type_or_refs", "target_entity_type_or_refs", "derived.governance_events[].target_entity_type_or_refs", description="目标类型或目标引用。"),
            _field("allowed_actor_types_or_changed_fields", "allowed_actor_types_or_changed_fields", "derived.governance_events[].allowed_actor_types_or_changed_fields", description="允许 actor 或变更字段。"),
            _field("required_policy_ids", "required_policy_ids", "derived.governance_events[].required_policy_ids", description="所需策略。"),
            _field("input_contract", "input_contract", "derived.governance_events[].input_contract", description="输入 contract。"),
            _field("output_contract", "output_contract", "derived.governance_events[].output_contract", description="输出 contract。"),
            _field("writeback_targets_or_decision_id", "writeback_targets_or_decision_id", "derived.governance_events[].writeback_targets_or_decision_id", description="写回目标或决策 ID。"),
            _field("requires_human_approval", "requires_human_approval", "derived.governance_events[].requires_human_approval", description="是否需要人工审批。"),
            _field("verification_state", "verification_state", "derived.governance_events[].verification_state", description="验证状态。"),
            _field("evidence_refs", "evidence_refs", "derived.governance_events[].evidence_refs", description="证据引用。"),
            _field("triggered_by", "triggered_by", "derived.governance_events[].triggered_by", description="触发者。"),
            _field("event_time", "event_time", "derived.governance_events[].event_time", field_type="date", description="事件时间。"),
            _field("来源文件", "source_ref", "derived.governance_events[].source_ref", description="来源文件。"),
            _field("置信度", "confidence", "derived.governance_events[].confidence", field_type="number", description="可信度。"),
            _field("更新时间", "updated_at", "derived.governance_events[].updated_at", description="更新时间。"),
        ],
    },
    {
        "table_id": "field_dictionary",
        "table_name": "字段字典与术语表",
        "description": "白皮书概念与多维表字段的桥接字典。",
        "primary": _field("字段Key", "field_key", "derived.field_dictionary[].field_key", description="字段唯一键。"),
        "views": ["全部"],
        "fields": [
            _field("对象家族", "object_family", "derived.field_dictionary[].object_family", description="所属对象家族。"),
            _field("中文字段名", "cn_field_name", "derived.field_dictionary[].cn_field_name", description="中文字段名。"),
            _field("英文字段名", "en_field_name", "derived.field_dictionary[].en_field_name", description="英文字段名。"),
            _field("对应canonical路径", "canonical_path", "derived.field_dictionary[].canonical_path", description="canonical 路径。"),
            _field("字段层级", "field_level", "derived.field_dictionary[].field_level", description="L0/L1/L2。"),
            _field("字段用途", "field_usage", "derived.field_dictionary[].field_usage", description="字段用途。"),
            _field("机器写入", "machine_written", "derived.field_dictionary[].machine_written", description="是否机器写入。"),
            _field("人类可编辑", "human_editable", "derived.field_dictionary[].human_editable", description="是否建议人类编辑。"),
            _field("示例值", "example_value", "derived.field_dictionary[].example_value", description="示例值。"),
            _field("说明", "description", "derived.field_dictionary[].description", description="字段说明。"),
            _field("来源文档", "source_document", "derived.field_dictionary[].source_document", description="来源文档。"),
            _field("更新时间", "updated_at", "derived.field_dictionary[].updated_at", description="更新时间。"),
        ],
    },
]


DOCUMENT_DEFINITIONS = [
    {"key": "overview", "title": "原力OS总览"},
    {"key": "whitepaper", "title": "原力OS白皮书 v1"},
    {"key": "manual", "title": "原力OS使用说明书 v1"},
    {"key": "field_dictionary", "title": "原力OS对象与字段字典 v1"},
    {"key": "operations_navigation", "title": "协同治理运营导航 v1"},
]


def _scope_script(scope: dict[str, Any], key: str, default: Path) -> Path:
    value = str(scope.get(key, "")).strip()
    return Path(value).expanduser().resolve() if value else default.expanduser().resolve()


def _compose_table_link(base_link: str, table_id: str, view_id: str = "") -> str:
    parsed = urlparse(base_link)
    params = parse_qs(parsed.query)
    params["table"] = [table_id]
    if view_id:
        params["view"] = [view_id]
    encoded = urlencode({key: values[0] for key, values in params.items() if values})
    return urlunparse(parsed._replace(query=encoded))


def _base_app_token_from_link(link: str) -> str:
    parts = [part for part in urlparse(link).path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "base":
        return parts[1]
    return ""


def _resolve_bitable_app_token(link: str, *, token: str) -> str:
    app_token = _base_app_token_from_link(link)
    if app_token:
        return app_token
    wiki_token = _wiki_token_from_link(link)
    if not wiki_token:
        return ""
    node_response = _feishu_api(
        f"/open-apis/wiki/v2/spaces/get_node?token={wiki_token}",
        token=token,
    )
    node = node_response.get("data", {}).get("node", {}) or {}
    if str(node.get("obj_type", "")).strip() != "bitable":
        return ""
    return str(node.get("obj_token", "")).strip()


def _named_items(items: list[dict[str, Any]], *keys: str) -> dict[str, dict[str, Any]]:
    named: dict[str, dict[str, Any]] = {}
    for item in items:
        for key in keys:
            value = str(item.get(key, "")).strip()
            if value:
                named[value] = item
                break
    return named


def _bitable_field_type_id(field_type: str) -> int:
    normalized = str(field_type or "").strip().lower()
    if normalized == "number":
        return 2
    if normalized == "date":
        return 5
    return 1


def _bitable_paged_items(path: str, *, token: str, item_key: str = "items") -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page_token = ""
    while True:
        separator = "&" if "?" in path else "?"
        request_path = f"{path}{separator}page_size=500"
        if page_token:
            request_path = f"{request_path}&page_token={page_token}"
        response = _feishu_api(request_path, token=token)
        data = response.get("data", {}) or {}
        items.extend(data.get(item_key, []) or [])
        if not data.get("has_more"):
            break
        page_token = str(data.get("page_token", "")).strip()
        if not page_token:
            break
    return items


def _bitable_list_tables(app_token: str, *, token: str) -> list[dict[str, Any]]:
    return _bitable_paged_items(f"/open-apis/bitable/v1/apps/{app_token}/tables", token=token)


def _bitable_create_table(app_token: str, table_name: str, *, token: str) -> dict[str, Any]:
    response = _feishu_api(
        f"/open-apis/bitable/v1/apps/{app_token}/tables",
        token=token,
        method="POST",
        payload={"table": {"name": table_name}},
    )
    return response.get("data", {}).get("table", {}) or response.get("data", {}) or {}


def _bitable_list_fields(app_token: str, table_id: str, *, token: str) -> list[dict[str, Any]]:
    return _bitable_paged_items(
        f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
        token=token,
    )


def _bitable_create_field(
    app_token: str,
    table_id: str,
    field_name: str,
    *,
    token: str,
    field_type: int = 1,
) -> dict[str, Any]:
    response = _feishu_api(
        f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
        token=token,
        method="POST",
        payload={"field_name": field_name, "type": field_type},
    )
    return response.get("data", {}).get("field", {}) or response.get("data", {}) or {}


def _bitable_update_field(
    app_token: str,
    table_id: str,
    field_id: str,
    *,
    token: str,
    field_name: str,
    field_type: int = 1,
) -> dict[str, Any]:
    response = _feishu_api(
        f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{field_id}",
        token=token,
        method="PUT",
        payload={"field_name": field_name, "type": field_type},
    )
    return response.get("data", {}).get("field", {}) or response.get("data", {}) or {}


def _bitable_list_views(app_token: str, table_id: str, *, token: str) -> list[dict[str, Any]]:
    return _bitable_paged_items(
        f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/views",
        token=token,
    )


def _bitable_create_view(
    app_token: str,
    table_id: str,
    view_name: str,
    *,
    token: str,
    view_type: str = "grid",
) -> dict[str, Any]:
    response = _feishu_api(
        f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/views",
        token=token,
        method="POST",
        payload={"view_name": view_name, "view_type": view_type},
    )
    return response.get("data", {}).get("view", {}) or response.get("data", {}) or {}


def _bitable_update_view(
    app_token: str,
    table_id: str,
    view_id: str,
    *,
    token: str,
    view_name: str,
) -> dict[str, Any]:
    response = _feishu_api(
        f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/views/{view_id}",
        token=token,
        method="PATCH",
        payload={"view_name": view_name},
    )
    return response.get("data", {}).get("view", {}) or response.get("data", {}) or {}


def _bitable_list_records(app_token: str, table_id: str, *, token: str) -> list[dict[str, Any]]:
    return _bitable_paged_items(
        f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records",
        token=token,
    )


def _bitable_batch_create_records(app_token: str, table_id: str, rows: list[dict[str, Any]], *, token: str) -> dict[str, Any]:
    response = _feishu_api(
        f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
        token=token,
        method="POST",
        payload={"records": [{"fields": row} for row in rows]},
    )
    return response.get("data", {}) or {}


def _bitable_batch_update_records(
    app_token: str,
    table_id: str,
    rows: list[dict[str, Any]],
    *,
    token: str,
) -> dict[str, Any]:
    response = _feishu_api(
        f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_update",
        token=token,
        method="POST",
        payload={"records": rows},
    )
    return response.get("data", {}) or {}


def _record_compare_key(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _chunk_rows(rows: list[dict[str, Any]], size: int = 500) -> list[list[dict[str, Any]]]:
    return [rows[index : index + size] for index in range(0, len(rows), size)]


def _apply_record_batches(
    app_token: str,
    table_id: str,
    rows: list[dict[str, Any]],
    *,
    token: str,
    primary_field: str,
    mode: str,
) -> None:
    if not rows:
        return
    handler = _bitable_batch_create_records if mode == "create" else _bitable_batch_update_records
    for batch in _chunk_rows(rows):
        try:
            handler(app_token, table_id, batch, token=token)
            continue
        except RuntimeError as exc:
            if len(batch) == 1:
                key = _record_compare_key(batch[0].get(primary_field))
                raise RuntimeError(f"{mode} record failed for {primary_field}={key}: {exc}") from exc
        for row in batch:
            try:
                handler(app_token, table_id, [row], token=token)
            except RuntimeError as exc:
                key = _record_compare_key(row.get(primary_field))
                raise RuntimeError(f"{mode} record failed for {primary_field}={key}: {exc}") from exc


def _sync_base_via_base_link(
    link: str,
    *,
    payloads: dict[str, list[dict[str, Any]]],
    token: str | None = None,
    app_token: str | None = None,
) -> dict[str, Any]:
    token = token or _feishu_tenant_access_token()
    app_token = app_token or _resolve_bitable_app_token(link, token=token)
    if not app_token:
        raise RuntimeError(f"Link does not contain a Feishu base app token: {link}")

    existing_tables = _bitable_list_tables(app_token, token=token)
    tables_by_name = _named_items(existing_tables, "name", "table_name")
    schema_preview_tables: list[dict[str, Any]] = []
    schema_apply_tables: list[dict[str, Any]] = []
    table_results: list[dict[str, Any]] = []

    for spec in CONTROL_BASE_TABLE_SPECS:
        desired_fields = [spec["primary"], *spec["fields"]]
        field_types = {field["name"]: str(field.get("type", "text")).strip().lower() for field in desired_fields}
        desired_view_names = [str(name).strip() for name in spec.get("views", []) if str(name).strip()]
        table_name = spec["table_name"]
        primary_name = spec["primary"]["name"]
        table = tables_by_name.get(table_name)
        table_created = False
        renamed_primary_field = False
        renamed_default_view = False
        created_fields: list[str] = []
        created_views: list[str] = []

        if table is None:
            try:
                table = _bitable_create_table(app_token, table_name, token=token)
            except RuntimeError:
                existing_tables = _bitable_list_tables(app_token, token=token)
                tables_by_name = _named_items(existing_tables, "name", "table_name")
                table = tables_by_name.get(table_name)
                if table is None:
                    raise
            table_created = True
            tables_by_name[table_name] = table

        table_id = str(table.get("table_id", "")).strip()
        if not table_id:
            raise RuntimeError(f"Failed to resolve table_id for table: {table_name}")

        fields = _bitable_list_fields(app_token, table_id, token=token)
        fields_by_name = _named_items(fields, "field_name", "name")
        if primary_name not in fields_by_name and fields:
            default_field = fields[0]
            default_name = str(default_field.get("field_name") or default_field.get("name") or "").strip()
            if table_created and len(fields) == 1 and default_name != primary_name:
                _bitable_update_field(
                    app_token,
                    table_id,
                    str(default_field.get("field_id", "")).strip(),
                    token=token,
                    field_name=primary_name,
                    field_type=int(default_field.get("type") or 1),
                )
                renamed_primary_field = True
                fields = _bitable_list_fields(app_token, table_id, token=token)
                fields_by_name = _named_items(fields, "field_name", "name")

        for field in desired_fields:
            field_name = field["name"]
            if field_name in fields_by_name:
                continue
            fields = _bitable_list_fields(app_token, table_id, token=token)
            fields_by_name = _named_items(fields, "field_name", "name")
            if field_name in fields_by_name:
                continue
            try:
                _bitable_create_field(
                    app_token,
                    table_id,
                    field_name,
                    token=token,
                    field_type=_bitable_field_type_id(field.get("type", "text")),
                )
                created_fields.append(field_name)
            except RuntimeError:
                fields = _bitable_list_fields(app_token, table_id, token=token)
                fields_by_name = _named_items(fields, "field_name", "name")
                if field_name not in fields_by_name:
                    raise
                continue
            fields = _bitable_list_fields(app_token, table_id, token=token)
            fields_by_name = _named_items(fields, "field_name", "name")

        views = _bitable_list_views(app_token, table_id, token=token)
        views_by_name = _named_items(views, "view_name", "name")
        if desired_view_names and views:
            default_view = views[0]
            default_view_name = str(default_view.get("view_name") or default_view.get("name") or "").strip()
            if table_created and default_view_name != desired_view_names[0] and desired_view_names[0] not in views_by_name:
                _bitable_update_view(
                    app_token,
                    table_id,
                    str(default_view.get("view_id", "")).strip(),
                    token=token,
                    view_name=desired_view_names[0],
                )
                renamed_default_view = True
                views = _bitable_list_views(app_token, table_id, token=token)
                views_by_name = _named_items(views, "view_name", "name")

        for view_name in desired_view_names:
            if view_name in views_by_name:
                continue
            views = _bitable_list_views(app_token, table_id, token=token)
            views_by_name = _named_items(views, "view_name", "name")
            if view_name in views_by_name:
                continue
            try:
                _bitable_create_view(app_token, table_id, view_name, token=token)
                created_views.append(view_name)
            except RuntimeError:
                views = _bitable_list_views(app_token, table_id, token=token)
                views_by_name = _named_items(views, "view_name", "name")
                if view_name not in views_by_name:
                    raise
                continue
            views = _bitable_list_views(app_token, table_id, token=token)
            views_by_name = _named_items(views, "view_name", "name")

        default_view_id = str((views[0] if views else {}).get("view_id", "")).strip()
        table_link = _compose_table_link(link, table_id, default_view_id)
        existing_records = _bitable_list_records(app_token, table_id, token=token)
        existing_by_key = {}
        for record in existing_records:
            key = _record_compare_key((record.get("fields") or {}).get(primary_name))
            if key:
                existing_by_key[key] = str(record.get("record_id", "")).strip()

        create_rows: list[dict[str, Any]] = []
        update_rows: list[dict[str, Any]] = []
        for row in payloads[spec["table_id"]]:
            fields_payload = {}
            for key, value in row.items():
                if not key:
                    continue
                field_type = field_types.get(key, "text")
                if field_type in {"date", "number"} and value in {"", None}:
                    continue
                fields_payload[key] = value
            key = _record_compare_key(fields_payload.get(primary_name))
            if not key:
                continue
            record_id = existing_by_key.get(key, "")
            if record_id:
                update_rows.append({"record_id": record_id, "fields": fields_payload})
            else:
                create_rows.append(fields_payload)

        _apply_record_batches(
            app_token,
            table_id,
            create_rows,
            token=token,
            primary_field=primary_name,
            mode="create",
        )
        _apply_record_batches(
            app_token,
            table_id,
            update_rows,
            token=token,
            primary_field=primary_name,
            mode="update",
        )

        preview = {
            "summary": {
                "creates": len(create_rows),
                "updates": len(update_rows),
                "unchanged": 0,
                "errors": 0,
                "can_apply": True,
            }
        }
        schema_preview_tables.append(
            {
                "mode": "dry-run",
                "base": {"obj_token": app_token, "title": "app-owned-base"},
                "table_name": table_name,
                "table_id": table_id,
                "primary_field": primary_name,
                "status": "applied",
                "table_created": table_created,
                "renamed_primary_field": renamed_primary_field,
                "renamed_default_view": renamed_default_view,
                "created_fields": created_fields,
                "created_views": created_views,
                "preview": preview,
                "table_link": table_link,
            }
        )
        schema_apply_tables.append(
            {
                "table_name": table_name,
                "table_id": table_id,
                "table_created": table_created,
                "renamed_primary_field": renamed_primary_field,
                "renamed_default_view": renamed_default_view,
                "created_fields": created_fields,
                "created_views": created_views,
                "table_link": table_link,
                "views": views,
            }
        )
        table_results.append(
            {
                "table_id": spec["table_id"],
                "table_name": table_name,
                "table_link": table_link,
                "payload_count": len(payloads[spec["table_id"]]),
                "preview": preview,
                "apply": {
                    "status": "applied",
                    "create_batches": len(_chunk_rows(create_rows)),
                    "update_batches": len(_chunk_rows(update_rows)),
                },
            }
        )

    return {
        "status": "completed",
        "script": "native_openapi_base_link",
        "schema_preview": {"mode": "native_base_link", "tables": schema_preview_tables},
        "schema_apply": {"mode": "native_base_link", "tables": schema_apply_tables},
        "tables": table_results,
    }


def _node_binary() -> str:
    for candidate in [
        os.getenv("NODE_BINARY", "").strip(),
        shutil.which("node") or "",
        shutil.which("/Users/hay2045/.local/bin/node") or "",
    ]:
        if candidate:
            return candidate
    raise RuntimeError("Node.js is required for feishu-doc integration but no node binary was found.")


def _command_for_script(script_path: Path) -> list[str]:
    suffix = script_path.suffix.lower()
    if suffix == ".py":
        return ["python3", str(script_path)]
    if suffix in {".js", ".cjs", ".mjs"}:
        return [_node_binary(), str(script_path)]
    return [str(script_path)]


def _run_command(command: list[str], *, env: dict[str, str] | None = None) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env or os.environ.copy(),
    )
    payload: Any = None
    stdout = completed.stdout.strip()
    if stdout:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = None
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "json": payload,
    }


def _json_request(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    encoded = None
    final_headers = {"Content-Type": "application/json; charset=utf-8"}
    if headers:
        final_headers.update(headers)
    if payload is not None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib_request.Request(url, data=encoded, headers=final_headers, method=method)
    try:
        with urllib_request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except urllib_error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {body}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"Network error for {url}: {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON response from {url}: {raw[:500]}") from exc


def _feishu_tenant_access_token() -> str:
    app_id = os.getenv("FEISHU_APP_ID", "").strip()
    app_secret = os.getenv("FEISHU_APP_SECRET", "").strip()
    response = _json_request(
        f"{FEISHU_OPENAPI_BASE}/open-apis/auth/v3/tenant_access_token/internal",
        method="POST",
        payload={"app_id": app_id, "app_secret": app_secret},
    )
    token = str(response.get("tenant_access_token", "")).strip()
    if response.get("code") not in {0, None} or not token:
        raise RuntimeError(f"Failed to obtain tenant_access_token: {json.dumps(response, ensure_ascii=False)}")
    return token


def _feishu_api(
    path: str,
    *,
    token: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = _json_request(
        f"{FEISHU_OPENAPI_BASE}{path}",
        method=method,
        payload=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    if response.get("code") not in {0, None}:
        raise RuntimeError(f"Feishu API error for {path}: {json.dumps(response, ensure_ascii=False)}")
    return response


def _doc_url_from_link(link: str, document_id: str) -> str:
    host = urlparse(link).netloc or "feishu.cn"
    return f"https://{host}/docx/{document_id}"


def _wiki_token_from_link(link: str) -> str:
    parts = [part for part in urlparse(link).path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "wiki":
        return parts[1]
    return ""


def _wiki_link_from_node_token(link: str, node_token: str) -> str:
    parsed = urlparse(link)
    return urlunparse(parsed._replace(path=f"/wiki/{node_token}", query="from=from_copylink"))


def _is_test_feishu_stub_env() -> bool:
    return bool(os.getenv("TEST_FEISHU_DOC_ROOT", "").strip()) and bool(os.getenv("TEST_FEISHU_BRIDGE_ROOT", "").strip())


def _resolve_control_links(link: str) -> dict[str, Any]:
    docs_link = link
    base_link = link
    resolution = {"mode": "direct", "docs_link": docs_link, "base_link": base_link, "docs_title": "", "base_title": ""}
    if _is_test_feishu_stub_env():
        resolution["mode"] = "test_stub"
        resolution["base_title"] = "协同治理"
        return resolution
    wiki_token = _wiki_token_from_link(link)
    if not wiki_token:
        return resolution

    token = _feishu_tenant_access_token()
    node_response = _feishu_api(
        f"/open-apis/wiki/v2/spaces/get_node?token={wiki_token}",
        token=token,
    )
    node = node_response.get("data", {}).get("node", {}) or {}
    docs_title = str(node.get("title", "")).strip()
    resolution["docs_title"] = docs_title
    if str(node.get("obj_type", "")).strip() == "bitable":
        resolution["base_title"] = docs_title
        return resolution

    parent_node_token = str(node.get("parent_node_token", "")).strip()
    space_id = str(node.get("space_id", "")).strip()
    if not parent_node_token or not space_id:
        resolution["mode"] = "docs_only"
        return resolution

    siblings_response = _feishu_api(
        f"/open-apis/wiki/v2/spaces/{space_id}/nodes?page_size=50&parent_node_token={parent_node_token}",
        token=token,
    )
    siblings = siblings_response.get("data", {}).get("items", []) or []
    preferred = next(
        (
            item
            for item in siblings
            if str(item.get("obj_type", "")).strip() == "bitable"
            and str(item.get("title", "")).strip() == "协同治理"
        ),
        None,
    )
    if preferred is None:
        preferred = next((item for item in siblings if str(item.get("obj_type", "")).strip() == "bitable"), None)
    if preferred is None:
        resolution["mode"] = "docs_only"
        return resolution

    base_link = _wiki_link_from_node_token(link, str(preferred.get("node_token", "")).strip())
    resolution["mode"] = "doc_plus_sibling_bitable"
    resolution["base_link"] = base_link
    resolution["base_title"] = str(preferred.get("title", "")).strip()
    return resolution


def _markdown_to_feishu_blocks(markdown: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        block_type = 2
        prop = "text"
        content = stripped
        if stripped.startswith("### "):
            block_type = 5
            prop = "heading3"
            content = stripped[4:]
        elif stripped.startswith("## "):
            block_type = 4
            prop = "heading2"
            content = stripped[3:]
        elif stripped.startswith("# "):
            block_type = 3
            prop = "heading1"
            content = stripped[2:]
        elif stripped.startswith("- "):
            block_type = 12
            prop = "bullet"
            content = stripped[2:]
        elif stripped[:3].isdigit() and stripped[1:3] == ". ":
            block_type = 13
            prop = "ordered"
            content = stripped[3:]
        elif stripped[:2].isdigit() and stripped[2:4] == ". ":
            block_type = 13
            prop = "ordered"
            content = stripped[4:]
        elif stripped.startswith("> "):
            block_type = 15
            prop = "quote"
            content = stripped[2:]
        blocks.append(
            {
                "block_type": block_type,
                prop: {
                    "elements": [
                        {
                            "text_run": {
                                "content": content,
                                "text_element_style": {},
                            }
                        }
                    ]
                },
            }
        )
    return blocks


def _feishu_create_doc(title: str, *, token: str, link: str) -> dict[str, str]:
    response = _feishu_api(
        "/open-apis/docx/v1/documents",
        token=token,
        method="POST",
        payload={"title": title},
    )
    document = response.get("data", {}).get("document", {})
    document_id = str(document.get("document_id", "")).strip()
    if not document_id:
        raise RuntimeError(f"Feishu doc create did not return document_id: {json.dumps(response, ensure_ascii=False)}")
    return {
        "document_id": document_id,
        "url": _doc_url_from_link(link, document_id),
        "title": str(document.get("title", "")).strip() or title,
    }


def _feishu_clear_doc(document_id: str, *, token: str) -> None:
    children = _feishu_api(
        f"/open-apis/docx/v1/documents/{document_id}/blocks/{document_id}/children?page_size=500",
        token=token,
    )
    items = children.get("data", {}).get("items", []) or []
    if not items:
        return
    _feishu_api(
        f"/open-apis/docx/v1/documents/{document_id}/blocks/{document_id}/children/batch_delete",
        token=token,
        method="DELETE",
        payload={"start_index": 0, "end_index": len(items)},
    )


def _feishu_append_doc(document_id: str, content: str, *, token: str) -> None:
    blocks = _markdown_to_feishu_blocks(content)
    if not blocks:
        return
    for start in range(0, len(blocks), 50):
        _feishu_api(
            f"/open-apis/docx/v1/documents/{document_id}/blocks/{document_id}/children",
            token=token,
            method="POST",
            payload={"children": blocks[start : start + 50], "index": -1},
        )


def _sync_documents_native(
    link: str,
    *,
    markdowns: dict[str, str],
    state_documents: dict[str, Any],
    existing_results: dict[str, Any] | None = None,
) -> dict[str, Any]:
    token = _feishu_tenant_access_token()
    results: dict[str, Any] = existing_results or {"status": "completed", "documents": {}, "script": "native_openapi_fallback"}
    ordered = [item for item in DOCUMENT_DEFINITIONS if item["key"] != "overview"] + [next(item for item in DOCUMENT_DEFINITIONS if item["key"] == "overview")]

    for definition in ordered:
        key = definition["key"]
        title = definition["title"]
        entry = state_documents.get(key, {}) if isinstance(state_documents.get(key, {}), dict) else {}
        document_id = str(entry.get("document_id", "")).strip()
        url = str(entry.get("url", "")).strip()
        if not document_id:
            created = _feishu_create_doc(title, token=token, link=link)
            document_id = created["document_id"]
            url = created["url"]

        content = markdowns[key]
        if key == "overview":
            overview_lines: list[str] = []
            for line in content.splitlines():
                if "待写入后回填 URL" not in line:
                    overview_lines.append(line)
                    continue
                if "白皮书" in line:
                    replacement = results["documents"]["whitepaper"]["url"]
                elif "使用说明书" in line:
                    replacement = results["documents"]["manual"]["url"]
                elif "字段字典" in line:
                    replacement = results["documents"]["field_dictionary"]["url"]
                else:
                    replacement = results["documents"]["operations_navigation"]["url"]
                overview_lines.append(line.replace("待写入后回填 URL", replacement))
            content = "\n".join(overview_lines)

        chunks = _chunk_markdown(content)
        _feishu_clear_doc(document_id, token=token)
        for chunk in chunks:
            _feishu_append_doc(document_id, chunk, token=token)

        state_documents[key] = {"document_id": document_id, "url": url, "title": title, "updated_at": iso_now()}
        results["documents"][key] = {"title": title, "document_id": document_id, "url": url, "chunk_count": len(chunks)}

    write_json(SYNC_STATE_PATH, {"documents": state_documents, "updated_at": iso_now(), "link": link})
    results["status"] = "completed"
    results["writer"] = "native_openapi_fallback"
    return results


def _chunk_markdown(markdown: str, *, max_chars: int = 1400) -> list[str]:
    blocks = [block.strip() for block in markdown.split("\n\n") if block.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for block in blocks:
        addition = len(block) + (2 if current else 0)
        if current and current_len + addition > max_chars:
            chunks.append("\n\n".join(current))
            current = [block]
            current_len = len(block)
            continue
        current.append(block)
        current_len += addition
    if current:
        chunks.append("\n\n".join(current))
    return chunks or ["# Empty\n"]


def _bool_text(value: Any) -> str:
    return "是" if bool(value) else "否"


def _text_list(value: Any) -> str:
    if isinstance(value, list):
        return " | ".join(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def _to_date_value(value: Any) -> int | str:
    if value in {"", None}:
        return ""
    if isinstance(value, (int, float)):
        integer = int(value)
        return integer // 1000 if abs(integer) >= 10**12 else integer
    normalized = str(value).strip()
    if not normalized:
        return ""
    if normalized.isdigit():
        integer = int(normalized)
        return integer // 1000 if abs(integer) >= 10**12 else integer
    try:
        if len(normalized) == 10:
            dt = datetime.strptime(normalized, "%Y-%m-%d")
        else:
            dt = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except ValueError:
        return normalized


def _transport_status(scope: dict[str, Any]) -> dict[str, Any]:
    transport_path = Path(
        str(scope.get("hub_transport_status_path") or DEFAULT_HUB_TRANSPORT_STATUS_PATH)
    ).expanduser().resolve()
    source_path = Path(
        str(scope.get("hub_source_status_path") or DEFAULT_HUB_SOURCE_STATUS_PATH)
    ).expanduser().resolve()
    transport = read_json(transport_path, default={}) if transport_path.exists() else {}
    source = read_json(source_path, default={}) if source_path.exists() else {}
    missing_sources = source.get("missing_sources")
    if isinstance(missing_sources, list):
        missing_snapshot = " | ".join(str(item) for item in missing_sources) if missing_sources else "none"
    else:
        missing_snapshot = str(missing_sources or "unknown")
    connected_sources = source.get("connected_sources")
    if isinstance(connected_sources, list):
        connected_snapshot = " | ".join(str(item) for item in connected_sources)
    else:
        connected_snapshot = str(connected_sources or "")
    return {
        "transport_repo": str(transport.get("transport_repo") or transport.get("remote_url") or ""),
        "remote_reachable": _bool_text(transport.get("remote_reachable") is True),
        "github_backend": str(transport.get("backend") or transport.get("github_backend") or ""),
        "connected_sources_snapshot": connected_snapshot,
        "missing_sources_snapshot": missing_snapshot,
    }


def _derive_segment(status: str, *, required_human_input: str = "", blocker_reason: str = "", priority: str = "") -> str:
    lowered = status.strip().lower()
    if lowered in {"completed", "feedback_pending", "feedback_recorded", "verified", "archived", "merged"}:
        return "completed"
    if "blocked_system" in lowered:
        return "blocked_system"
    if "blocked_needs_user" in lowered or "human_manual_pending" in lowered or required_human_input.strip():
        return "wait_human"
    if "defer" in lowered:
        return "deferred"
    if blocker_reason.strip():
        return "background"
    if priority.strip().upper() == "P1" or lowered in {"active", "in_progress", "running"}:
        return "frontstage"
    return "background"


def _field_value(row: dict[str, Any], name: str, *, default: Any = "") -> Any:
    return row.get(name, default)


def _normalize_for_field(value: Any, field_type: str) -> Any:
    if field_type == "number":
        if value in {"", None}:
            return ""
        try:
            return float(value)
        except (TypeError, ValueError):
            return ""
    if field_type == "date":
        return _to_date_value(value)
    if isinstance(value, (list, dict)):
        return _text_list(value)
    return "" if value is None else value


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _join_non_empty(values: list[Any], *, sep: str = " | ") -> str:
    return sep.join(part for part in (_clean_text(value) for value in values) if part)


def _coerce_control_level(value: Any) -> str:
    normalized = _clean_text(value).lower()
    return normalized if normalized in CONTROL_LEVEL_VALUES else ""


def _coerce_priority_band(value: Any) -> str:
    normalized = _clean_text(value).upper()
    return normalized if normalized in PRIORITY_BAND_VALUES else ""


def _priority_rank(value: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(value, 99)


def _highest_priority_band(values: list[Any]) -> str:
    normalized = [_coerce_priority_band(value) for value in values]
    normalized = [value for value in normalized if value]
    if not normalized:
        return ""
    return sorted(normalized, key=_priority_rank)[0]


def _strategy_artifact(name: str, *, default: Any) -> Any:
    return read_json(STRATEGY_CURRENT_ROOT / f"{name}.json", default=default)


def _module_lookup(context: dict[str, Any], *, module_id: str = "", module_code: str = "") -> dict[str, Any]:
    if module_id and module_id in context["modules_by_id"]:
        return context["modules_by_id"][module_id]
    if module_code and module_code in context["modules_by_code"]:
        return context["modules_by_code"][module_code]
    return {}


def _pick_cbm_row(candidates: list[dict[str, Any]], *, title: str = "") -> dict[str, Any]:
    if not candidates:
        return {}
    if len(candidates) == 1:
        return candidates[0]
    lowered = title.lower()
    preferred = ""
    if "ontology" in lowered or "对象" in title or "mirror" in lowered or "写回" in title or "资产" in title:
        preferred = "control"
    elif any(token in title for token in ["销售", "成交", "交付", "财务", "公域", "私域"]):
        preferred = "execute"
    elif any(token in title for token in ["治理", "主图", "复制", "协同", "蓝图"]):
        preferred = "direct"
    if preferred:
        for candidate in candidates:
            if _coerce_control_level(candidate.get("control_level")) == preferred:
                return candidate
    for candidate in candidates:
        if _clean_text(candidate.get("strategy_id")) or _clean_text(candidate.get("experiment_id")):
            return candidate
    return candidates[0]


def _cbm_row_for_entity(
    context: dict[str, Any],
    *,
    entity_id: str = "",
    title: str = "",
    strategy_id: str = "",
    experiment_id: str = "",
    theme_id: str = "",
    module_id: str = "",
    module_code: str = "",
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []

    def add(rows: list[dict[str, Any]]) -> None:
        for row in rows:
            if row not in candidates:
                candidates.append(row)

    if entity_id and entity_id in context["cbm_by_entity"]:
        return context["cbm_by_entity"][entity_id]
    if title:
        add(context["cbm_by_title"].get(title, []))
    if strategy_id:
        add(context["cbm_by_strategy"].get(strategy_id, []))
    if experiment_id:
        add(context["cbm_by_experiment"].get(experiment_id, []))
    if theme_id:
        add(context["cbm_by_theme"].get(theme_id, []))
    if module_id:
        add(context["cbm_by_module"].get(module_id, []))
    module = _module_lookup(context, module_id=module_id, module_code=module_code)
    if module:
        add(context["cbm_by_module"].get(_clean_text(module.get("module_id")), []))
        if _clean_text(module.get("module_code")) == "governance":
            add(context["cbm_by_theme"].get("theme-governance", []))
    return _pick_cbm_row(candidates, title=title)


def _infer_control_level(
    item: dict[str, Any],
    context: dict[str, Any],
    *,
    entity_id_key: str,
    module_id_key: str,
    module_code_key: str,
    title_key: str,
    theme_key: str,
    strategy_key: str,
    experiment_key: str,
) -> str:
    explicit = _coerce_control_level(item.get("control_level"))
    if explicit:
        return explicit
    title = _clean_text(item.get(title_key))
    cbm_row = _cbm_row_for_entity(
        context,
        entity_id=_clean_text(item.get(entity_id_key)),
        title=title,
        strategy_id=_clean_text(item.get(strategy_key)),
        experiment_id=_clean_text(item.get(experiment_key)),
        theme_id=_clean_text(item.get(theme_key)),
        module_id=_clean_text(item.get(module_id_key)),
        module_code=_clean_text(item.get(module_code_key)),
    )
    mapped = _coerce_control_level(cbm_row.get("control_level"))
    if mapped:
        return mapped
    lowered = title.lower()
    module = _module_lookup(
        context,
        module_id=_clean_text(item.get(module_id_key)),
        module_code=_clean_text(item.get(module_code_key)),
    )
    module_code = _clean_text(module.get("module_code") or item.get(module_code_key))
    theme_id = _clean_text(item.get(theme_key))
    if theme_id == "theme-business" or module_code in {"public", "private", "sales", "delivery", "finance"}:
        return "execute"
    if "ontology" in lowered or "对象" in title or "mirror" in lowered or "sync" in lowered or "资产" in title or "写回" in title:
        return "control"
    if theme_id in {"theme-governance", "theme-human-ai-coevolution"} or module_code == "governance":
        return "direct"
    return ""


def _infer_component_domain(
    item: dict[str, Any],
    context: dict[str, Any],
    *,
    entity_id_key: str,
    module_id_key: str,
    module_code_key: str,
    title_key: str,
    theme_key: str,
    strategy_key: str,
    experiment_key: str,
) -> str:
    explicit = _clean_text(item.get("component_domain"))
    if explicit:
        return explicit
    title = _clean_text(item.get(title_key))
    cbm_row = _cbm_row_for_entity(
        context,
        entity_id=_clean_text(item.get(entity_id_key)),
        title=title,
        strategy_id=_clean_text(item.get(strategy_key)),
        experiment_id=_clean_text(item.get(experiment_key)),
        theme_id=_clean_text(item.get(theme_key)),
        module_id=_clean_text(item.get(module_id_key)),
        module_code=_clean_text(item.get(module_code_key)),
    )
    mapped = _clean_text(cbm_row.get("component_domain"))
    if mapped:
        return mapped
    lowered = title.lower()
    if "ontology" in lowered or "对象" in title:
        return "运行对象层"
    if "客户" in title or "协同" in title or "复制" in title:
        return "人机协同复制"
    if "知识" in title or "资产" in title:
        return "知识资产同步"
    if "销售" in title or "成交" in title:
        return "销售成交"
    module = _module_lookup(
        context,
        module_id=_clean_text(item.get(module_id_key)),
        module_code=_clean_text(item.get(module_code_key)),
    )
    return _clean_text(module.get("title"))


def _infer_evidence_strength(item: dict[str, Any], cbm_row: dict[str, Any]) -> str:
    explicit = _clean_text(item.get("evidence_strength"))
    if explicit:
        return explicit
    coverage = _clean_text(cbm_row.get("coverage_status"))
    if coverage == "absorbed":
        return "strong"
    if coverage == "partial":
        return "medium"
    try:
        confidence = float(item.get("confidence", 0) or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    if confidence >= 0.94:
        return "strong"
    if confidence >= 0.85:
        return "medium"
    return "low"


def _derive_runtime_context(inventory: dict[str, Any]) -> dict[str, Any]:
    goals = {str(item.get("id", "")).strip(): item for item in _strategy_artifact("strategic-goals", default=[])}
    themes = {str(item.get("id", "")).strip(): item for item in _strategy_artifact("theme-registry", default=[])}
    strategies = {
        str(item.get("strategy_id", "")).strip(): item
        for item in _strategy_artifact("strategy-registry", default=[])
    }
    experiments = {
        str(item.get("experiment_id", "")).strip(): item
        for item in _strategy_artifact("experiment-registry", default=[])
    }
    workflows = {
        str(item.get("workflow_id", item.get("id", ""))).strip(): item
        for item in _strategy_artifact("workflow-registry", default=[])
        if str(item.get("workflow_id", item.get("id", ""))).strip()
    }
    initiatives = _strategy_artifact("initiative-registry", default=[])
    canonical_threads = _strategy_artifact("canonical-thread-registry", default=[])
    sales_execute_plan = _strategy_artifact("execute-sales-v1", default={})
    sales_execute_plan_summary = _sales_execute_plan_summary(
        {"sales_execute_plan": sales_execute_plan if isinstance(sales_execute_plan, dict) else {}}
    )
    cbm_payload = _strategy_artifact("cbm-mapping-view", default={"rows": []})
    cbm_rows = list(cbm_payload.get("rows", []))
    modules = inventory.get("operating_modules", [])
    threads = inventory.get("threads", [])
    tasks = inventory.get("tasks", [])
    modules_by_id = {str(item.get("module_id", "")).strip(): item for item in modules}
    modules_by_code = {str(item.get("module_code", "")).strip(): item for item in modules}
    subjects_by_id = {str(item.get("subject_id", "")).strip(): item for item in inventory.get("subjects", [])}
    threads_by_id = {str(item.get("thread_id", "")).strip(): item for item in threads}
    tasks_by_id = {str(item.get("task_id", "")).strip(): item for item in tasks}
    tasks_by_thread: dict[str, list[dict[str, Any]]] = {}
    for item in tasks:
        thread_id = str(item.get("thread_id", "")).strip()
        if thread_id:
            tasks_by_thread.setdefault(thread_id, []).append(item)
    decisions_by_id = {str(item.get("decision_id", "")).strip(): item for item in inventory.get("decision_records", [])}
    writebacks_by_id = {str(item.get("writeback_id", "")).strip(): item for item in inventory.get("writeback_events", [])}

    cbm_by_entity: dict[str, dict[str, Any]] = {}
    cbm_by_title: dict[str, list[dict[str, Any]]] = {}
    cbm_by_strategy: dict[str, list[dict[str, Any]]] = {}
    cbm_by_experiment: dict[str, list[dict[str, Any]]] = {}
    cbm_by_theme: dict[str, list[dict[str, Any]]] = {}
    cbm_by_module: dict[str, list[dict[str, Any]]] = {}
    for row in cbm_rows:
        strategy_id = _clean_text(row.get("strategy_id"))
        experiment_id = _clean_text(row.get("experiment_id"))
        theme_id = _clean_text(row.get("theme_id"))
        if strategy_id:
            cbm_by_strategy.setdefault(strategy_id, []).append(row)
        if experiment_id:
            cbm_by_experiment.setdefault(experiment_id, []).append(row)
        if theme_id:
            cbm_by_theme.setdefault(theme_id, []).append(row)
        for ref in row.get("entity_refs", []):
            entity_id = _clean_text(ref.get("entity_id"))
            if entity_id and entity_id not in cbm_by_entity:
                cbm_by_entity[entity_id] = row
            title = _clean_text(ref.get("title"))
            if title:
                cbm_by_title.setdefault(title, []).append(row)
            if _clean_text(ref.get("entity_type")) == "operating_module" and entity_id:
                cbm_by_module.setdefault(entity_id, []).append(row)

    return {
        "goals": goals,
        "themes": themes,
        "strategies": strategies,
        "experiments": experiments,
        "workflows": workflows,
        "initiatives": initiatives,
        "canonical_threads": canonical_threads,
        "sales_execute_plan": sales_execute_plan if isinstance(sales_execute_plan, dict) else {},
        "cbm_rows": cbm_rows,
        "cbm_payload": cbm_payload,
        "cbm_by_entity": cbm_by_entity,
        "cbm_by_title": cbm_by_title,
        "cbm_by_strategy": cbm_by_strategy,
        "cbm_by_experiment": cbm_by_experiment,
        "cbm_by_theme": cbm_by_theme,
        "cbm_by_module": cbm_by_module,
        "modules_by_id": modules_by_id,
        "modules_by_code": modules_by_code,
        "subjects_by_id": subjects_by_id,
        "threads_by_id": threads_by_id,
        "tasks_by_id": tasks_by_id,
        "tasks_by_thread": tasks_by_thread,
        "decisions_by_id": decisions_by_id,
        "writebacks_by_id": writebacks_by_id,
        "sales_execute_live": _sales_execute_live_summary(
            inventory,
            plan=sales_execute_plan_summary,
            subjects_by_id=subjects_by_id,
        ),
    }


def _sales_execute_plan_summary(context: dict[str, Any]) -> dict[str, str]:
    plan = context.get("sales_execute_plan", {})
    if not isinstance(plan, dict) or not plan:
        return {}
    kpi_heatmap = plan.get("kpi_heatmap", {})
    evidence_refs = plan.get("evidence_refs", [])
    if not isinstance(kpi_heatmap, dict):
        kpi_heatmap = {}
    if not isinstance(evidence_refs, list):
        evidence_refs = []
    return {
        "goal_id": _clean_text(plan.get("goal_id")),
        "theme_id": _clean_text(plan.get("theme_id")),
        "strategy_id": _clean_text(plan.get("strategy_id")),
        "experiment_id": _clean_text(plan.get("experiment_id")),
        "workflow_id": _clean_text(plan.get("workflow_id")),
        "component_domain": _clean_text(plan.get("component_domain")),
        "control_level": _coerce_control_level(plan.get("control_level")),
        "status": _clean_text(plan.get("status")) or "in_progress",
        "owner_mode": _clean_text(plan.get("owner_mode")),
        "current_gap": _join_non_empty(list(kpi_heatmap.get("current_gap", []))),
        "next_action": _clean_text(kpi_heatmap.get("next_action")) or _clean_text(plan.get("summary")),
        "priority_band": _coerce_priority_band(kpi_heatmap.get("priority_band")),
        "kpi_hint": _join_non_empty([item.get("title") for item in kpi_heatmap.get("kpis", [])]),
        "evidence_strength": _clean_text(kpi_heatmap.get("evidence_strength")),
        "evidence_ref": _clean_text(evidence_refs[0] if evidence_refs else "") or _clean_text(plan.get("source_ref")),
        "source_ref": _clean_text(plan.get("source_ref")),
        "updated_at": _clean_text(plan.get("updated_at")) or iso_now(),
    }


def _parse_runtime_date(value: Any) -> datetime | None:
    normalized = _clean_text(value)
    if not normalized:
        return None
    try:
        if len(normalized) == 10:
            return datetime.strptime(normalized, "%Y-%m-%d")
        return datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return None


def _runtime_sort_value(value: Any) -> float:
    parsed = _parse_runtime_date(value)
    if not parsed:
        return float("-inf")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=now_local().tzinfo)
    return parsed.timestamp()


def _is_recent_runtime_activity(value: Any, *, days: int = 14) -> bool:
    sort_value = _runtime_sort_value(value)
    if sort_value == float("-inf"):
        return False
    return (now_local().timestamp() - sort_value) <= days * 86400


def _runtime_entity_title(context: dict[str, Any], entity_id: Any) -> str:
    normalized = _clean_text(entity_id)
    if not normalized:
        return ""
    task = context.get("tasks_by_id", {}).get(normalized, {})
    if task:
        return _clean_text(task.get("title")) or normalized
    thread = context.get("threads_by_id", {}).get(normalized, {})
    if thread:
        return _clean_text(thread.get("title")) or normalized
    return normalized


def _governance_activities_for_entities(context: dict[str, Any], entity_ids: list[str]) -> list[dict[str, str]]:
    targets = {value for value in (_clean_text(item) for item in entity_ids) if value}
    if not targets:
        return []

    activities: list[dict[str, str]] = []
    seen_writebacks: set[str] = set()
    for item in context["decisions_by_id"].values():
        decision_id = _clean_text(item.get("decision_id"))
        raw_targets = item.get("target_entity_ids", [])
        if not isinstance(raw_targets, list):
            raw_targets = [raw_targets]
        decision_targets = {_clean_text(target) for target in raw_targets if _clean_text(target)}
        if decision_id not in targets and not targets.intersection(decision_targets):
            continue
        focus_object = next(
            (
                _runtime_entity_title(context, target)
                for target in decision_targets
                if _runtime_entity_title(context, target)
            ),
            "",
        ) or _clean_text(item.get("title"))
        activities.append(
            {
                "event_type": "decision",
                "event_time": _clean_text(item.get("decision_time")) or _clean_text(item.get("updated_at")),
                "summary": _clean_text(item.get("title")) or _clean_text(item.get("decision_summary")),
                "focus_object": focus_object,
            }
        )
        raw_writeback_ids = item.get("writeback_event_ids", [])
        if not isinstance(raw_writeback_ids, list):
            raw_writeback_ids = [raw_writeback_ids]
        linked_writebacks = {_clean_text(ref) for ref in raw_writeback_ids if _clean_text(ref)}
        for writeback in context["writebacks_by_id"].values():
            writeback_id = _clean_text(writeback.get("writeback_id"))
            if not writeback_id or writeback_id in seen_writebacks:
                continue
            if writeback_id not in linked_writebacks and _clean_text(writeback.get("decision_id")) != decision_id:
                continue
            seen_writebacks.add(writeback_id)
            activities.append(
                {
                    "event_type": "writeback",
                    "event_time": _clean_text(writeback.get("writeback_time")) or _clean_text(writeback.get("updated_at")),
                    "summary": _clean_text(writeback.get("action_id")) or writeback_id,
                    "focus_object": focus_object or _clean_text(writeback.get("action_id")),
                }
            )
    return activities


def _latest_governance_activity(context: dict[str, Any], entity_ids: list[str]) -> dict[str, str]:
    activities = _governance_activities_for_entities(context, entity_ids)
    if not activities:
        return {}
    return sorted(activities, key=lambda item: _runtime_sort_value(item.get("event_time")))[-1]


def _derive_progress_truth_label(item: dict[str, Any]) -> str:
    status = _clean_text(item.get("status")).lower()
    verification_state = _clean_text(item.get("verification_state")).lower()
    evidence_ref = _clean_text(item.get("evidence_ref"))
    run_artifact_ref = _clean_text(item.get("run_artifact_ref"))
    raw_evidence_refs = item.get("evidence_refs", [])
    if not isinstance(raw_evidence_refs, list):
        raw_evidence_refs = [raw_evidence_refs]
    has_evidence = bool(
        evidence_ref
        or run_artifact_ref
        or any(_clean_text(ref) for ref in raw_evidence_refs)
    )
    blocker_reason = _clean_text(item.get("blocker_reason"))
    updated_at = _clean_text(item.get("last_updated_at")) or _clean_text(item.get("updated_at"))
    verified = verification_state in {"verified", "verified_or_closed"} or status in {"completed", "verified", "archived"}

    if "blocked" in status and (blocker_reason or has_evidence):
        return "real_blocked"
    if status == "handoff_only_closed" or verification_state == "handoff_prepared":
        return "appearance_only"
    if has_evidence and verified:
        return "real_progress"
    if not _is_recent_runtime_activity(updated_at) and not verified:
        return "stale_unverified"
    if has_evidence or status in {"active", "in_progress", "running", "completed", "verified"}:
        return "appearance_only"
    return "stale_unverified"


def _derive_owner_gap(human_owner: str, ai_copilot: str) -> str:
    if not human_owner and not ai_copilot:
        return "O3_dual_missing"
    if not human_owner:
        return "O2_human_owner_missing"
    if not ai_copilot:
        return "O2_ai_copilot_missing"
    return ""


def _normalize_ranked_gap(current_gap: str, *, has_runtime_row: bool, evidence_strength: str = "", status: str = "") -> str:
    gap = _clean_text(current_gap)
    if not gap:
        return ""
    for prefix in ("G3_runtime_missing | ", "G2_partial_binding | ", "G1_quality_gap | "):
        if gap.startswith(prefix):
            return gap
    normalized_status = _clean_text(status)
    normalized_strength = _clean_text(evidence_strength)
    if not has_runtime_row:
        prefix = "G3_runtime_missing"
    elif (
        "最小 execute 证据链已形成" in gap
        or "字段质量" in gap
        or normalized_status in {"absorbed", "validated"}
        or normalized_strength == "strong"
    ):
        prefix = "G1_quality_gap"
    else:
        prefix = "G2_partial_binding"
    return f"{prefix} | {gap}"


def _derive_source_health_bucket(*, remote_reachable: str, missing_sources_snapshot: str, connected_sources_snapshot: str, source_ref: str) -> str:
    if remote_reachable == "否" or not source_ref:
        return "broken"
    if remote_reachable == "是" and missing_sources_snapshot in {"", "none"} and connected_sources_snapshot:
        return "healthy"
    if remote_reachable == "是":
        return "degraded"
    return "unknown"


def _coerce_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _derive_capability_friction(*, requires_human_approval: str, verification_strength: Any, routing_credit: Any) -> tuple[str, int, float]:
    if requires_human_approval != "是":
        return "", 0, 0.0
    block_count = 1
    friction_score = round(_coerce_float(verification_strength) + _coerce_float(routing_credit), 2)
    return "", block_count, friction_score


def _normalize_runtime_close_state(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    normalized = text.lower().replace("-", "_").replace(" ", "")
    if normalized in {"won", "closed_won", "closedwon", "dealwon", "wonclosed"} or text in {
        "成交",
        "赢单",
        "已成交",
        "成交成功",
        "关闭赢单",
    }:
        return "closed_won"
    if normalized in {"lost", "closed_lost", "closedlost", "deallost", "lostclosed"} or text in {
        "丢单",
        "失单",
        "未成交",
        "失败",
        "成交失败",
        "关闭失单",
        "关闭失败",
    }:
        return "closed_lost"
    return ""


def _runtime_order_close_state(order: dict[str, Any]) -> str:
    explicit = _normalize_runtime_close_state(order.get("close_state"))
    if explicit:
        return explicit
    if _clean_text(order.get("lost_at")) and (
        _clean_text(order.get("loss_reason")) or _clean_text(order.get("loss_evidence_ref"))
    ):
        return "closed_lost"
    return "closed_won"


def _runtime_is_lost_contract_row(order: dict[str, Any]) -> bool:
    if _normalize_runtime_close_state(order.get("close_state")) == "closed_lost":
        return True
    return any(_clean_text(order.get(field)) for field in ("lost_at", "loss_reason", "loss_evidence_ref"))


def _runtime_is_complete_lost_row(order: dict[str, Any]) -> bool:
    return (
        _runtime_order_close_state(order) == "closed_lost"
        and bool(_clean_text(order.get("lost_at")))
        and bool(_clean_text(order.get("loss_reason")) or _clean_text(order.get("loss_evidence_ref")))
    )


def _sales_execute_live_summary(
    inventory: dict[str, Any],
    *,
    plan: dict[str, str],
    subjects_by_id: dict[str, dict[str, Any]],
) -> dict[str, str]:
    sales_orders = [
        item
        for item in inventory.get("orders", [])
        if _clean_text(item.get("module_code")) in {"", "sales"}
    ]
    sales_close_writebacks = [
        item
        for item in inventory.get("writeback_events", [])
        if _clean_text(item.get("action_id")) == "deal-close"
    ]
    sales_won_writebacks = [
        item
        for item in sales_close_writebacks
        if _clean_text(item.get("writeback_type")) == "deal_closed_won"
    ]
    sales_lost_writebacks = [
        item
        for item in sales_close_writebacks
        if _clean_text(item.get("writeback_type")) == "deal_closed_lost"
    ]
    sales_quote_writebacks = [
        item
        for item in inventory.get("writeback_events", [])
        if _clean_text(item.get("action_id")) == "proposal-quote"
    ]
    sales_handoff_writebacks = [
        item
        for item in inventory.get("writeback_events", [])
        if _clean_text(item.get("action_id")) == "post-close-handoff"
    ]
    if not sales_orders and not sales_close_writebacks and not sales_quote_writebacks and not sales_handoff_writebacks:
        return {}

    sales_module = next(
        (
            item
            for item in inventory.get("operating_modules", [])
            if _clean_text(item.get("module_code")) == "sales" or _clean_text(item.get("title")) == "销售成交"
        ),
        {},
    )
    owner_mode = _owner_mode_from_people(
        _lookup_registry_title(subjects_by_id.get(_clean_text(sales_module.get("owner_subject_id")), {})),
        _lookup_registry_title(subjects_by_id.get(_clean_text(sales_module.get("ai_subject_id")), {})),
    ) or plan.get("owner_mode", "")
    qualified_opportunities = {
        _clean_text(item.get("opportunity_id"))
        for item in sales_orders
        if _clean_text(item.get("opportunity_id"))
    }
    opportunity_anchor_gap_count = sum(
        1 for item in sales_orders if not _clean_text(item.get("opportunity_id"))
    )
    quote_rows = [
        item
        for item in sales_orders
        if _clean_text(item.get("quote_id")) or _clean_text(item.get("quote_sent_at"))
    ]
    timing_rows = [
        item
        for item in sales_orders
        if _clean_text(item.get("quote_sent_at"))
    ]
    won_rows = [item for item in sales_orders if _runtime_order_close_state(item) == "closed_won"]
    lost_rows = [item for item in sales_orders if _runtime_is_lost_contract_row(item)]
    lost_completed_rows = [item for item in sales_orders if _runtime_is_complete_lost_row(item)]
    handoff_rows = [
        item
        for item in sales_orders
        if any(
            _clean_text(item.get(field))
            for field in ("delivery_owner", "finance_owner", "handoff_packet_ref", "handoff_completed_at")
        )
    ]
    handoff_completed_rows = [
        item
        for item in sales_orders
        if _clean_text(item.get("handoff_completed_at"))
        and any(_clean_text(item.get(field)) for field in ("delivery_owner", "finance_owner", "handoff_packet_ref"))
    ]
    base_owner_gap_count = sum(
        1
        for item in sales_orders
        if not _clean_text(item.get("lead_owner")) or not _clean_text(item.get("primary_conversion_owner"))
    )
    handoff_owner_gap_count = sum(
        1
        for item in handoff_rows
        if not _clean_text(item.get("delivery_owner")) or not _clean_text(item.get("finance_owner"))
    )
    owner_gap_count = base_owner_gap_count + handoff_owner_gap_count
    cycle_days: list[int] = []
    for item in sales_orders:
        quote_dt = _parse_runtime_date(item.get("quote_sent_at"))
        close_dt = _parse_runtime_date(item.get("order_date"))
        if quote_dt and close_dt and close_dt >= quote_dt:
            cycle_days.append((close_dt - quote_dt).days)
    latest_writeback = {}
    if sales_close_writebacks:
        latest_writeback = max(
            sales_close_writebacks,
            key=lambda item: _clean_text(item.get("updated_at")) or _clean_text(item.get("writeback_time")),
        )
    latest_quote_writeback = {}
    if sales_quote_writebacks:
        latest_quote_writeback = max(
            sales_quote_writebacks,
            key=lambda item: _clean_text(item.get("updated_at")) or _clean_text(item.get("writeback_time")),
        )
    latest_handoff_writeback = {}
    if sales_handoff_writebacks:
        latest_handoff_writeback = max(
            sales_handoff_writebacks,
            key=lambda item: _clean_text(item.get("updated_at")) or _clean_text(item.get("writeback_time")),
        )
    latest_activity_writeback = {}
    all_sales_activity = [*sales_close_writebacks, *sales_quote_writebacks, *sales_handoff_writebacks]
    if all_sales_activity:
        latest_activity_writeback = max(
            all_sales_activity,
            key=lambda item: _clean_text(item.get("updated_at")) or _clean_text(item.get("writeback_time")),
        )

    quote_source_detected = bool(quote_rows)
    quote_timing_ready = bool(sales_quote_writebacks) and bool(timing_rows)
    handoff_ready = bool(sales_handoff_writebacks) and bool(handoff_completed_rows)
    lost_ready = bool(sales_lost_writebacks) and bool(lost_completed_rows)
    current_gap_parts = ["lead_count 仍不可观测"]
    if not quote_source_detected:
        current_gap_parts.append("缺 quote source contract，quote_throughput / deal_cycle_delay 仍不可观测")
    elif not quote_timing_ready:
        current_gap_parts.append("quote source 已接入，但缺阶段时间戳或 source-backed quote writeback，deal_cycle_delay 仍不可观测")
    elif handoff_ready and lost_ready:
        current_gap_parts.append("最小 execute 证据链已形成，剩余缺口在 handoff owner 覆盖与 owner/opportunity 字段质量")
    elif handoff_ready:
        current_gap_parts.append("lost 仍缺证据，handoff 已进入真实证据链")
    elif lost_ready:
        current_gap_parts.append("handoff 仍缺证据，lost 已进入真实证据链")
    else:
        current_gap_parts.append("lost 与 handoff 仍缺证据，quote/timing 已进入真实证据链")
    if owner_gap_count or opportunity_anchor_gap_count:
        current_gap_parts.append(
            _join_non_empty(
                [
                    f"字段质量仍有缺口：owner_gap={owner_gap_count}" if owner_gap_count else "",
                    (
                        f"handoff_owner_gap={handoff_owner_gap_count}"
                        if handoff_owner_gap_count
                        else ""
                    ),
                    (
                        f"opportunity_anchor_gap={opportunity_anchor_gap_count}"
                        if opportunity_anchor_gap_count
                        else ""
                    ),
                ],
                sep=" / ",
            )
        )
    if not qualified_opportunities:
        current_gap_parts.append("qualified_opportunities 仍缺少真实 opportunity_id 锚点")
    if not quote_timing_ready:
        next_action = (
            "先接 quote_sent 源字段，再补 handoff。"
            if not quote_source_detected
            else "先补阶段时间戳，再补 handoff。"
        )
    elif handoff_ready and lost_ready:
        next_action = "补 handoff owner 覆盖，并校准 owner/opportunity 字段质量。"
    elif handoff_ready:
        next_action = "补 lost，并继续补 handoff owner 覆盖。"
    elif lost_ready:
        next_action = "补 handoff，并继续补 owner/opportunity 字段质量。"
    else:
        next_action = "补 handoff，再补 lost。"

    won_count = len(sales_won_writebacks) or len(won_rows)
    lost_count_hint = (
        str(len(sales_lost_writebacks))
        if sales_lost_writebacks
        else (str(len(lost_completed_rows)) if lost_completed_rows else "不可观测")
    )

    summary = dict(plan)
    summary.update(
        {
            "status": "in_progress",
            "owner_mode": owner_mode,
            "current_gap": _join_non_empty(current_gap_parts),
            "next_action": _join_non_empty(
                [
                    next_action,
                    "并补齐缺失 owner/opportunity 的成交订单字段。"
                    if owner_gap_count or opportunity_anchor_gap_count
                    else "",
                ]
            ),
            "priority_band": "P1",
            "kpi_hint": _join_non_empty(
                [
                    f"qualified_opportunities={len(qualified_opportunities)}",
                    (
                        f"quote_throughput={len(sales_quote_writebacks)}"
                        if sales_quote_writebacks
                        else "quote_throughput=不可观测"
                    ),
                    (
                        f"deal_cycle_delay=avg:{sum(cycle_days) / len(cycle_days):.1f}d"
                        if cycle_days
                        else "deal_cycle_delay=不可观测"
                    ),
                    (
                        f"handoff_completed={len(sales_handoff_writebacks)}"
                        if sales_handoff_writebacks
                        else "handoff_completed=不可观测"
                    ),
                    f"win_loss_count=won:{won_count}, lost:{lost_count_hint}",
                    f"owner_gap={owner_gap_count}",
                    (
                        f"quote_source_detected={len(quote_rows)}"
                        if quote_rows
                        else "quote_source_detected=0"
                    ),
                    (
                        f"lost_source_detected={len(lost_rows)}"
                        if lost_rows
                        else "lost_source_detected=0"
                    ),
                    (
                        f"handoff_source_detected={len(handoff_rows)}"
                        if handoff_rows
                        else "handoff_source_detected=0"
                    ),
                ]
            ),
            "evidence_strength": "strong" if sales_close_writebacks else "medium",
            "evidence_ref": (
                _clean_text(latest_handoff_writeback.get("source_ref"))
                or _clean_text(latest_quote_writeback.get("source_ref"))
                or _clean_text(latest_activity_writeback.get("source_ref"))
                or _clean_text(latest_writeback.get("source_ref"))
                or plan.get("evidence_ref", "")
            ),
            "source_ref": (
                _clean_text(latest_handoff_writeback.get("source_ref"))
                or _clean_text(latest_quote_writeback.get("source_ref"))
                or _clean_text(latest_activity_writeback.get("source_ref"))
                or _clean_text(latest_writeback.get("source_ref"))
                or plan.get("source_ref", "")
            ),
            "updated_at": (
                _clean_text(latest_handoff_writeback.get("updated_at"))
                or _clean_text(latest_handoff_writeback.get("writeback_time"))
                or _clean_text(latest_quote_writeback.get("updated_at"))
                or _clean_text(latest_quote_writeback.get("writeback_time"))
                or _clean_text(latest_activity_writeback.get("updated_at"))
                or _clean_text(latest_activity_writeback.get("writeback_time"))
                or _clean_text(latest_writeback.get("updated_at"))
                or _clean_text(latest_writeback.get("writeback_time"))
                or plan.get("updated_at", "")
                or iso_now()
            ),
            "latest_decision_id": _clean_text(latest_activity_writeback.get("decision_id")) or _clean_text(latest_writeback.get("decision_id")),
            "latest_writeback_id": _clean_text(latest_activity_writeback.get("writeback_id")) or _clean_text(latest_writeback.get("writeback_id")),
        }
    )
    if not summary.get("component_domain"):
        summary["component_domain"] = "销售成交"
    if not summary.get("control_level"):
        summary["control_level"] = "execute"
    return summary


def _lookup_registry_title(record: dict[str, Any]) -> str:
    for key in ("title", "name", "theme"):
        value = _clean_text(record.get(key))
        if value:
            return value
    return ""


def _matched_initiative(context: dict[str, Any], *, strategy_id: str = "", theme_id: str = "", goal_id: str = "") -> dict[str, Any]:
    for item in context["initiatives"]:
        if strategy_id and _clean_text(item.get("strategy_id")) == strategy_id:
            return item
    for item in context["initiatives"]:
        if goal_id and theme_id and _clean_text(item.get("goal_id")) == goal_id and _clean_text(item.get("theme_id")) == theme_id:
            return item
    return {}


def _owner_mode_from_people(human_owner: str, ai_copilot: str) -> str:
    if human_owner and ai_copilot:
        return "hybrid"
    if human_owner:
        return "human"
    if ai_copilot:
        return "ai"
    return "missing"


def _latest_decision_for_entities(context: dict[str, Any], entity_ids: list[str]) -> dict[str, Any]:
    targets = {value for value in (_clean_text(item) for item in entity_ids) if value}
    if not targets:
        return {}
    matches = []
    for item in context["decisions_by_id"].values():
        if _clean_text(item.get("decision_id")) in targets:
            matches.append(item)
            continue
        item_targets = {value for value in (_clean_text(target) for target in item.get("target_entity_ids", [])) if value}
        if targets.intersection(item_targets):
            matches.append(item)
    if not matches:
        return {}
    return sorted(matches, key=lambda item: _clean_text(item.get("decision_time")))[-1]


def _latest_writeback_for_ids(context: dict[str, Any], writeback_ids: list[str]) -> dict[str, Any]:
    matches = [
        context["writebacks_by_id"][writeback_id]
        for writeback_id in (_clean_text(item) for item in writeback_ids)
        if writeback_id and writeback_id in context["writebacks_by_id"]
    ]
    if not matches:
        return {}
    return sorted(matches, key=lambda item: _clean_text(item.get("writeback_time")))[-1]


def _build_threads_rows(inventory: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in inventory.get("threads", []):
        cbm_row = _cbm_row_for_entity(
            context,
            entity_id=_clean_text(item.get("thread_id")),
            title=_clean_text(item.get("title")),
            strategy_id=_clean_text(item.get("strategy_id")),
            experiment_id=_clean_text(item.get("experiment_id")),
            theme_id=_clean_text(item.get("theme")),
            module_id=_clean_text(item.get("module_id")),
        )
        priority_band = _coerce_priority_band(item.get("priority_band")) or _coerce_priority_band(item.get("priority"))
        related_task_ids = [
            _clean_text(task.get("task_id"))
            for task in context.get("tasks_by_thread", {}).get(_clean_text(item.get("thread_id")), [])
            if _clean_text(task.get("task_id"))
        ]
        latest_activity = _latest_governance_activity(
            context,
            [_clean_text(item.get("thread_id")), *related_task_ids],
        )
        rows.append(
            {
                "Thread ID": item.get("thread_id", ""),
                "标题": item.get("title", ""),
                "主题": item.get("theme", ""),
                "策略ID": item.get("strategy_id", ""),
                "实验ID": item.get("experiment_id", ""),
                "工作流ID": item.get("workflow_id", ""),
                "目标ID": item.get("goal_id", ""),
                "空间ID": item.get("space_id", ""),
                "模块ID": item.get("module_id", ""),
                "component_domain": _infer_component_domain(
                    item,
                    context,
                    entity_id_key="thread_id",
                    module_id_key="module_id",
                    module_code_key="module_code",
                    title_key="title",
                    theme_key="theme",
                    strategy_key="strategy_id",
                    experiment_key="experiment_id",
                ),
                "control_level": _infer_control_level(
                    item,
                    context,
                    entity_id_key="thread_id",
                    module_id_key="module_id",
                    module_code_key="module_code",
                    title_key="title",
                    theme_key="theme",
                    strategy_key="strategy_id",
                    experiment_key="experiment_id",
                ),
                "priority_band": priority_band,
                "状态": item.get("status", ""),
                "运营分段": _derive_segment(
                    item.get("status", ""),
                    required_human_input=item.get("required_human_input", ""),
                    blocker_reason=item.get("blocker_reason", ""),
                    priority=priority_band,
                ),
                "last_activity_at": latest_activity.get("event_time") or item.get("updated_at", ""),
                "last_activity_type": latest_activity.get("event_type") or "thread_update",
                "last_activity_summary": latest_activity.get("summary") or item.get("title", ""),
                "frontstage_focus_object": latest_activity.get("focus_object") or item.get("title", ""),
                "来源Run ID": item.get("source_run_id", ""),
                "进入方式": item.get("entry_mode", ""),
                "父任务ID": item.get("parent_task_id", ""),
                "managed_by": item.get("managed_by", ""),
                "编排状态": item.get("orchestration_state", ""),
                "闭环状态": item.get("closure_state", ""),
                "闭环Run ID": item.get("closure_run_id", ""),
                "阻塞原因": item.get("blocker_reason", ""),
                "需要人类输入": item.get("required_human_input", ""),
                "开放问题": _text_list(item.get("open_questions", [])),
                "晨检标记": _bool_text(item.get("morning_review_flag")),
                "下次复查日": item.get("next_review_date", ""),
                "来源文件": item.get("source_ref", ""),
                "evidence_strength": _infer_evidence_strength(item, cbm_row),
                "置信度": item.get("confidence", ""),
                "更新时间": item.get("updated_at", ""),
            }
        )
    return rows


def _build_tasks_rows(inventory: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in inventory.get("tasks", []):
        cbm_row = _cbm_row_for_entity(
            context,
            entity_id=_clean_text(item.get("task_id")),
            title=_clean_text(item.get("title")),
            strategy_id=_clean_text(item.get("strategy_id")),
            experiment_id=_clean_text(item.get("experiment_id")),
            theme_id=_clean_text(item.get("theme")),
            module_id=_clean_text(item.get("target_module_id")),
            module_code=_clean_text(item.get("module_code")),
        )
        priority_band = _coerce_priority_band(item.get("priority_band")) or _coerce_priority_band(item.get("priority"))
        rows.append(
            {
                "Task ID": item.get("task_id", ""),
                "标题": item.get("title", ""),
                "Thread ID": item.get("thread_id", ""),
                "目标ID": item.get("goal_id", ""),
                "空间ID": item.get("space_id", ""),
                "目标主体ID": item.get("target_subject_id", ""),
                "目标模块ID": item.get("target_module_id", ""),
                "模块编码": item.get("module_code", ""),
                "component_domain": _infer_component_domain(
                    item,
                    context,
                    entity_id_key="task_id",
                    module_id_key="target_module_id",
                    module_code_key="module_code",
                    title_key="title",
                    theme_key="theme",
                    strategy_key="strategy_id",
                    experiment_key="experiment_id",
                ),
                "control_level": _infer_control_level(
                    item,
                    context,
                    entity_id_key="task_id",
                    module_id_key="target_module_id",
                    module_code_key="module_code",
                    title_key="title",
                    theme_key="theme",
                    strategy_key="strategy_id",
                    experiment_key="experiment_id",
                ),
                "priority_band": priority_band,
                "模块Owner主体ID": item.get("owner_subject_id", ""),
                "模块AI主体ID": item.get("ai_subject_id", ""),
                "业务副手主体ID": item.get("deputy_subject_id", ""),
                "状态": item.get("status", ""),
                "运营分段": _derive_segment(
                    item.get("status", ""),
                    required_human_input=item.get("required_human_input", ""),
                    blocker_reason=item.get("blocker_reason", ""),
                    priority=priority_band or item.get("priority", ""),
                ),
                "优先级": item.get("priority", ""),
                "owner_mode": item.get("owner_mode", ""),
                "任务类型": item.get("task_kind", ""),
                "父任务ID": item.get("parent_task_id", ""),
                "依赖任务IDs": _text_list(item.get("depends_on_task_ids", [])),
                "managed_by": item.get("managed_by", ""),
                "intake_run_id": item.get("intake_run_id", ""),
                "delegation_mode": item.get("delegation_mode", ""),
                "人类边界状态": item.get("human_boundary_state", ""),
                "已选技能": _text_list(item.get("selected_skills", [])),
                "验真状态": item.get("verification_state", ""),
                "验真目标": _text_list(item.get("verification_target", [])),
                "打断条件": item.get("interrupt_only_if", ""),
                "证据入口": item.get("evidence_ref", ""),
                "执行模式": item.get("execution_mode", ""),
                "runner_state": item.get("runner_state", ""),
                "执行工件": item.get("run_artifact_ref", ""),
                "结果摘要": item.get("result_summary", ""),
                "证据列表": _text_list(item.get("evidence_refs", [])),
                "evidence_strength": _infer_evidence_strength(item, cbm_row),
                "progress_truth_label": _derive_progress_truth_label(item),
                "kpi_gap": _clean_text(item.get("kpi_gap")) or _join_non_empty(list(cbm_row.get("gap_notes", []))),
                "闭环状态": item.get("closure_state", ""),
                "闭环Run ID": item.get("closure_run_id", ""),
                "阻塞原因": item.get("blocker_reason", ""),
                "需要人类输入": item.get("required_human_input", ""),
                "下一步": item.get("next_action", ""),
                "来源文件": item.get("source_ref", ""),
                "置信度": item.get("confidence", ""),
                "最后更新时间": item.get("last_updated_at", ""),
                "更新时间": item.get("updated_at", ""),
            }
        )
    return rows


def _build_strategic_linkage_rows(context: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    covered_keys: set[tuple[str, str, str, str, str, str, str]] = set()
    cbm_source_ref = str(STRATEGY_CURRENT_ROOT / "cbm-mapping-view.json")
    canonical_source_ref = str(STRATEGY_CURRENT_ROOT / "canonical-thread-registry.json")

    for item in context["cbm_rows"]:
        goal_id = _clean_text(item.get("goal_id"))
        theme_id = _clean_text(item.get("theme_id"))
        strategy_id = _clean_text(item.get("strategy_id"))
        experiment_id = _clean_text(item.get("experiment_id"))
        workflow_id = _clean_text(item.get("workflow_id"))
        component_domain = _clean_text(item.get("component_domain"))
        control_level = _coerce_control_level(item.get("control_level"))
        covered_keys.add((goal_id, theme_id, strategy_id, experiment_id, workflow_id, component_domain, control_level))
        strategy = context["strategies"].get(strategy_id, {})
        experiment = context["experiments"].get(experiment_id, {})
        workflow = context["workflows"].get(workflow_id, {})
        rows.append(
            {
                "战略链路Key": stable_id("strategic-link", goal_id, theme_id, strategy_id, experiment_id, workflow_id, component_domain, control_level),
                "goal_id": goal_id,
                "goal_title": _lookup_registry_title(context["goals"].get(goal_id, {})),
                "theme_id": theme_id,
                "theme_title": _lookup_registry_title(context["themes"].get(theme_id, {})),
                "strategy_id": strategy_id,
                "strategy_title": _lookup_registry_title(strategy),
                "experiment_id": experiment_id,
                "experiment_title": _lookup_registry_title(experiment),
                "workflow_id": workflow_id,
                "workflow_title": _lookup_registry_title(workflow),
                "component_domain": component_domain,
                "control_level_scope": control_level,
                "status": _clean_text(experiment.get("verdict")) or _clean_text(strategy.get("validation_state")) or _clean_text(item.get("coverage_status")) or "mapped",
                "current_gap": _join_non_empty(list(item.get("gap_notes", []))),
                "next_action": _clean_text(experiment.get("next_action")) or _join_non_empty([ref.get("title") for ref in item.get("action_refs", [])]),
                "evidence_ref": _clean_text((item.get("evidence_refs") or [""])[0]) or _clean_text(experiment.get("evidence_ref")) or _clean_text(strategy.get("last_evidence_ref")),
                "source_ref": cbm_source_ref,
                "updated_at": _clean_text(experiment.get("updated_at")) or _clean_text(strategy.get("updated_at")) or iso_now(),
            }
        )

    sales_execute = context.get("sales_execute_live") or _sales_execute_plan_summary(context)
    if sales_execute:
        dedupe_key = (
            sales_execute["goal_id"],
            sales_execute["theme_id"],
            sales_execute["strategy_id"],
            sales_execute["experiment_id"],
            sales_execute["workflow_id"],
            sales_execute["component_domain"],
            sales_execute["control_level"],
        )
        strategy = context["strategies"].get(sales_execute["strategy_id"], {})
        experiment = context["experiments"].get(sales_execute["experiment_id"], {})
        workflow = context["workflows"].get(sales_execute["workflow_id"], {})
        sales_row = {
            "战略链路Key": stable_id(
                "strategic-link",
                sales_execute["goal_id"],
                sales_execute["theme_id"],
                sales_execute["strategy_id"],
                sales_execute["experiment_id"],
                sales_execute["workflow_id"],
                sales_execute["component_domain"],
                sales_execute["control_level"],
            ),
            "goal_id": sales_execute["goal_id"],
            "goal_title": _lookup_registry_title(context["goals"].get(sales_execute["goal_id"], {})),
            "theme_id": sales_execute["theme_id"],
            "theme_title": _lookup_registry_title(context["themes"].get(sales_execute["theme_id"], {})),
            "strategy_id": sales_execute["strategy_id"],
            "strategy_title": _lookup_registry_title(strategy),
            "experiment_id": sales_execute["experiment_id"],
            "experiment_title": _lookup_registry_title(experiment),
            "workflow_id": sales_execute["workflow_id"],
            "workflow_title": _lookup_registry_title(workflow),
            "component_domain": sales_execute["component_domain"],
            "control_level_scope": sales_execute["control_level"],
            "status": sales_execute["status"],
            "current_gap": sales_execute["current_gap"],
            "next_action": sales_execute["next_action"],
            "evidence_ref": sales_execute["evidence_ref"],
            "source_ref": sales_execute["source_ref"],
            "updated_at": sales_execute["updated_at"],
        }
        if dedupe_key in covered_keys:
            for row in rows:
                existing_key = (
                    _clean_text(row.get("goal_id")),
                    _clean_text(row.get("theme_id")),
                    _clean_text(row.get("strategy_id")),
                    _clean_text(row.get("experiment_id")),
                    _clean_text(row.get("workflow_id")),
                    _clean_text(row.get("component_domain")),
                    _coerce_control_level(row.get("control_level_scope")),
                )
                if existing_key != dedupe_key:
                    continue
                for field in ("status", "current_gap", "next_action", "evidence_ref", "source_ref", "updated_at"):
                    if _clean_text(sales_row.get(field)):
                        row[field] = sales_row[field]
                break
        else:
            covered_keys.add(dedupe_key)
            rows.append(sales_row)

    for item in context["canonical_threads"]:
        goal_id = _clean_text(item.get("goal_id"))
        theme_id = _clean_text(item.get("theme_id"))
        strategy_id = _clean_text(item.get("strategy_slot"))
        experiment_id = _clean_text(item.get("experiment_slot"))
        initiative = _matched_initiative(context, strategy_id=strategy_id, theme_id=theme_id, goal_id=goal_id)
        workflow_id = _clean_text(initiative.get("workflow_id"))
        pseudo = {
            "entity_id": "",
            "title": _clean_text(item.get("canonical_thread")),
            "theme_id": theme_id,
            "strategy_id": strategy_id,
            "experiment_id": experiment_id,
            "module_id": "",
            "module_code": "",
        }
        component_domain = _infer_component_domain(
            pseudo,
            context,
            entity_id_key="entity_id",
            module_id_key="module_id",
            module_code_key="module_code",
            title_key="title",
            theme_key="theme_id",
            strategy_key="strategy_id",
            experiment_key="experiment_id",
        )
        control_level = _infer_control_level(
            pseudo,
            context,
            entity_id_key="entity_id",
            module_id_key="module_id",
            module_code_key="module_code",
            title_key="title",
            theme_key="theme_id",
            strategy_key="strategy_id",
            experiment_key="experiment_id",
        )
        dedupe_key = (goal_id, theme_id, strategy_id, experiment_id, workflow_id, component_domain, control_level)
        if dedupe_key in covered_keys:
            continue
        strategy = context["strategies"].get(strategy_id, {})
        experiment = context["experiments"].get(experiment_id, {})
        workflow = context["workflows"].get(workflow_id, {})
        rows.append(
            {
                "战略链路Key": stable_id("strategic-link", goal_id, theme_id, strategy_id, experiment_id, workflow_id, item.get("canonical_thread", "")),
                "goal_id": goal_id,
                "goal_title": _lookup_registry_title(context["goals"].get(goal_id, {})),
                "theme_id": theme_id,
                "theme_title": _lookup_registry_title(context["themes"].get(theme_id, {})),
                "strategy_id": strategy_id,
                "strategy_title": _lookup_registry_title(strategy),
                "experiment_id": experiment_id,
                "experiment_title": _lookup_registry_title(experiment),
                "workflow_id": workflow_id,
                "workflow_title": _lookup_registry_title(workflow),
                "component_domain": component_domain,
                "control_level_scope": control_level,
                "status": _clean_text(experiment.get("verdict")) or _clean_text(strategy.get("validation_state")) or _clean_text(item.get("disposition")) or "proposal_first",
                "current_gap": _clean_text(item.get("next_blocker")),
                "next_action": _clean_text(item.get("next_experiment")),
                "evidence_ref": canonical_source_ref,
                "source_ref": canonical_source_ref,
                "updated_at": _clean_text(experiment.get("updated_at")) or _clean_text(strategy.get("updated_at")) or iso_now(),
            }
        )
    return rows


def _build_cbm_component_responsibility_rows(inventory: dict[str, Any], context: dict[str, Any], strategic_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    strategic_by_component: dict[str, list[dict[str, Any]]] = {}
    for item in strategic_rows:
        component_domain = _clean_text(item.get("component_domain"))
        if component_domain:
            strategic_by_component.setdefault(component_domain, []).append(item)

    for module in inventory.get("operating_modules", []):
        module_id = _clean_text(module.get("module_id"))
        module_code = _clean_text(module.get("module_code"))
        component_domain = _clean_text(module.get("title"))
        related_cbm = list(context["cbm_by_module"].get(module_id, []))
        if module_code == "governance":
            for candidate in context["cbm_by_theme"].get("theme-governance", []):
                if candidate not in related_cbm:
                    related_cbm.append(candidate)
        related_links: list[dict[str, Any]] = list(strategic_by_component.get(component_domain, []))
        for candidate in related_cbm:
            candidate_domain = _clean_text(candidate.get("component_domain"))
            for linkage in strategic_by_component.get(candidate_domain, []):
                if linkage not in related_links:
                    related_links.append(linkage)
        if module_code == "governance" and not related_links:
            related_links = [item for item in strategic_rows if _clean_text(item.get("theme_id")) == "theme-governance"]

        human_owner = _lookup_registry_title(context["subjects_by_id"].get(_clean_text(module.get("owner_subject_id")), {}))
        ai_copilot = _lookup_registry_title(context["subjects_by_id"].get(_clean_text(module.get("ai_subject_id")), {}))
        owner_mode = _owner_mode_from_people(human_owner, ai_copilot)
        control_scope = _join_non_empty(
            sorted(
                {
                    _clean_text(item.get("control_level_scope") or item.get("control_level"))
                    for item in related_links
                    if _clean_text(item.get("control_level_scope") or item.get("control_level"))
                }
            ),
            sep=", ",
        )
        primary_link = related_links[0] if related_links else {}
        owner_gap = _derive_owner_gap(human_owner, ai_copilot)
        rows.append(
            {
                "组件责任Key": stable_id("component-responsibility", module_id, component_domain),
                "component_domain": component_domain,
                "control_level_scope": control_scope,
                "human_owner": human_owner,
                "ai_copilot": ai_copilot,
                "goal_id": _clean_text(primary_link.get("goal_id")),
                "theme_id": _clean_text(primary_link.get("theme_id")),
                "strategy_id": _clean_text(primary_link.get("strategy_id")),
                "workflow_id": _clean_text(primary_link.get("workflow_id")),
                "owner_gap": owner_gap,
                "owner_mode": owner_mode,
                "status": "active_with_gap" if owner_gap and _clean_text(module.get("status")) == "active" else _clean_text(module.get("status")),
                "evidence_ref": _clean_text(primary_link.get("evidence_ref")) or _clean_text(module.get("source_ref")),
                "updated_at": _clean_text(module.get("updated_at")) or iso_now(),
            }
        )
    return rows


def _build_cbm_component_heatmap_rows(
    inventory: dict[str, Any],
    context: dict[str, Any],
    thread_rows: list[dict[str, Any]],
    task_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    task_lookup = {item.get("Task ID", ""): item for item in task_rows}
    thread_lookup = {item.get("Thread ID", ""): item for item in thread_rows}
    represented_components: set[str] = set()
    sales_execute = context.get("sales_execute_live") or _sales_execute_plan_summary(context)

    for item in context["cbm_rows"]:
        entity_ids = [_clean_text(ref.get("entity_id")) for ref in item.get("entity_refs", [])]
        related_priorities = []
        related_owner_modes = []
        related_next_actions = []
        for entity_id in entity_ids:
            if entity_id in task_lookup:
                related_priorities.append(task_lookup[entity_id].get("priority_band", ""))
                related_owner_modes.append(task_lookup[entity_id].get("owner_mode", ""))
                related_next_actions.append(task_lookup[entity_id].get("下一步", ""))
            if entity_id in thread_lookup:
                related_priorities.append(thread_lookup[entity_id].get("priority_band", ""))
                related_next_actions.append(thread_lookup[entity_id].get("下次复查日", ""))
        decision = _latest_decision_for_entities(context, entity_ids)
        action_writebacks = []
        for action in item.get("action_refs", []):
            action_writebacks.extend(action.get("writeback_event_ids", []))
        latest_writeback = _latest_writeback_for_ids(
            context,
            action_writebacks or list(decision.get("writeback_event_ids", [])),
        )
        component_domain = _clean_text(item.get("component_domain"))
        represented_components.add(component_domain)
        module_fallback = next(
            (module for module in inventory.get("operating_modules", []) if _clean_text(module.get("title")) == component_domain),
            {},
        )
        fallback_owner_mode = _owner_mode_from_people(
            _lookup_registry_title(context["subjects_by_id"].get(_clean_text(module_fallback.get("owner_subject_id")), {})),
            _lookup_registry_title(context["subjects_by_id"].get(_clean_text(module_fallback.get("ai_subject_id")), {})),
        )
        current_gap = _normalize_ranked_gap(
            _join_non_empty(list(item.get("gap_notes", []))),
            has_runtime_row=True,
            status=_clean_text(item.get("coverage_status")),
        )
        priority_band = _highest_priority_band(related_priorities)
        if not priority_band:
            priority_band = "P1" if current_gap or related_next_actions else ("P1" if _clean_text(item.get("coverage_status")) == "partial" else "P2")
        row = {
            "热图Key": stable_id("component-heatmap", component_domain, _clean_text(item.get("control_level"))),
            "component_domain": component_domain,
            "control_level": _coerce_control_level(item.get("control_level")),
            "kpi_hint": _join_non_empty(list(item.get("kpi_refs", []))),
            "current_gap": current_gap,
            "priority_band": priority_band,
            "next_action": _join_non_empty(
                [ref.get("title") for ref in item.get("action_refs", [])],
                sep=" / ",
            ) or _join_non_empty(related_next_actions, sep=" / ") or _clean_text(context["experiments"].get(_clean_text(item.get("experiment_id")), {}).get("next_action")) or current_gap,
            "owner_mode": _join_non_empty(related_owner_modes, sep=", ") or _clean_text((item.get("entity_refs") or [{}])[0].get("owner_mode")) or fallback_owner_mode,
            "evidence_strength": "strong" if _clean_text(item.get("coverage_status")) == "absorbed" else "medium",
            "latest_decision_id": _clean_text(decision.get("decision_id")) or next((entity_id for entity_id in entity_ids if entity_id.startswith("decision-")), ""),
            "latest_writeback_id": _clean_text(latest_writeback.get("writeback_id")) or _clean_text(action_writebacks[0] if action_writebacks else ""),
            "status": _clean_text(item.get("coverage_status")) or "mapped",
            "evidence_ref": _clean_text((item.get("evidence_refs") or [""])[0]),
            "updated_at": _clean_text(latest_writeback.get("updated_at")) or _clean_text(decision.get("updated_at")) or iso_now(),
        }
        if (
            sales_execute
            and component_domain == sales_execute["component_domain"]
            and row["control_level"] == sales_execute["control_level"]
        ):
            row["kpi_hint"] = sales_execute["kpi_hint"] or row["kpi_hint"]
            row["current_gap"] = _normalize_ranked_gap(
                sales_execute["current_gap"] or row["current_gap"],
                has_runtime_row=True,
                evidence_strength=sales_execute.get("evidence_strength", ""),
                status=sales_execute.get("status", ""),
            )
            row["priority_band"] = sales_execute["priority_band"] or row["priority_band"]
            row["next_action"] = sales_execute["next_action"] or row["next_action"]
            row["owner_mode"] = sales_execute["owner_mode"] or row["owner_mode"]
            row["evidence_strength"] = sales_execute["evidence_strength"] or row["evidence_strength"]
            row["status"] = sales_execute["status"] or row["status"]
            row["evidence_ref"] = sales_execute["evidence_ref"] or row["evidence_ref"]
            row["updated_at"] = sales_execute["updated_at"] or row["updated_at"]
            if _clean_text(sales_execute.get("latest_decision_id")):
                row["latest_decision_id"] = sales_execute["latest_decision_id"]
            if _clean_text(sales_execute.get("latest_writeback_id")):
                row["latest_writeback_id"] = sales_execute["latest_writeback_id"]
            elif not _clean_text(latest_writeback.get("writeback_id")):
                row["latest_writeback_id"] = ""
        rows.append(row)

    for module in inventory.get("operating_modules", []):
        component_domain = _clean_text(module.get("title"))
        if component_domain in represented_components:
            continue
        human_owner = _lookup_registry_title(context["subjects_by_id"].get(_clean_text(module.get("owner_subject_id")), {}))
        ai_copilot = _lookup_registry_title(context["subjects_by_id"].get(_clean_text(module.get("ai_subject_id")), {}))
        rows.append(
            {
                "热图Key": stable_id("component-heatmap", component_domain, "gap"),
                "component_domain": component_domain,
                "control_level": "",
                "kpi_hint": _clean_text(module.get("kpi_hint")),
                    "current_gap": _normalize_ranked_gap(
                        "尚未建立 component_domain x control_level x KPI 热图的一等运行视图。",
                        has_runtime_row=False,
                    ),
                "priority_band": "P2" if _clean_text(module.get("status")) == "active" else "",
                "next_action": "先把组件责任、priority_band 和 action/writeback 绑到同一组件视图。",
                "owner_mode": _owner_mode_from_people(human_owner, ai_copilot),
                "evidence_strength": "low",
                "latest_decision_id": "",
                "latest_writeback_id": "",
                "status": "gap",
                "evidence_ref": _clean_text(module.get("source_ref")),
                "updated_at": _clean_text(module.get("updated_at")) or iso_now(),
            }
        )
    return rows


def _build_skills_capabilities_rows(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in inventory.get("skills", []):
        approval_latency, approval_block_count, friction_score = _derive_capability_friction(
            requires_human_approval="否",
            verification_strength=item.get("verification_strength", ""),
            routing_credit=item.get("routing_credit", ""),
        )
        rows.append(
            {
                "能力Key": f"skill:{item.get('skill_id', '')}",
                "记录类型": "skill",
                "对象ID": item.get("skill_id", ""),
                "名称": item.get("name", ""),
                "标题": item.get("title", ""),
                "cluster_or_actor": item.get("cluster", ""),
                "role": item.get("role", ""),
                "verification_strength": item.get("verification_strength", ""),
                "cost_efficiency": item.get("cost_efficiency", ""),
                "auth_reuse": item.get("auth_reuse", ""),
                "complexity_penalty": item.get("complexity_penalty", ""),
                "routing_credit": item.get("routing_credit", ""),
                "allowed_action_ids": "",
                "bound_policy_ids": "",
                "requires_human_approval": "",
                "approval_latency": approval_latency,
                "approval_block_count": approval_block_count,
                "friction_score": friction_score,
                "状态": item.get("status", ""),
                "来源文件": item.get("source_ref", ""),
                "置信度": item.get("confidence", ""),
                "更新时间": item.get("updated_at", ""),
            }
        )
    for item in inventory.get("agent_capabilities", []):
        requires_human_approval = _bool_text(item.get("requires_human_approval"))
        approval_latency, approval_block_count, friction_score = _derive_capability_friction(
            requires_human_approval=requires_human_approval,
            verification_strength=item.get("verification_strength", ""),
            routing_credit=item.get("routing_credit", ""),
        )
        rows.append(
            {
                "能力Key": f"capability:{item.get('capability_id', '')}",
                "记录类型": "capability",
                "对象ID": item.get("capability_id", ""),
                "名称": item.get("capability_id", ""),
                "标题": item.get("title", ""),
                "cluster_or_actor": item.get("actor_type", ""),
                "role": "",
                "verification_strength": "",
                "cost_efficiency": "",
                "auth_reuse": "",
                "complexity_penalty": "",
                "routing_credit": "",
                "allowed_action_ids": _text_list(item.get("allowed_action_ids", [])),
                "bound_policy_ids": _text_list(item.get("bound_policy_ids", [])),
                "requires_human_approval": requires_human_approval,
                "approval_latency": approval_latency,
                "approval_block_count": approval_block_count,
                "friction_score": friction_score,
                "状态": item.get("status", ""),
                "来源文件": item.get("source_ref", ""),
                "置信度": item.get("confidence", ""),
                "更新时间": item.get("updated_at", ""),
            }
        )
    return rows


def _build_source_rows(inventory: dict[str, Any], scope: dict[str, Any]) -> list[dict[str, Any]]:
    transport = _transport_status(scope)
    rows: list[dict[str, Any]] = []
    for item in inventory.get("source_feeds", []):
        health_bucket = _derive_source_health_bucket(
            remote_reachable=transport["remote_reachable"],
            missing_sources_snapshot=transport["missing_sources_snapshot"],
            connected_sources_snapshot=transport["connected_sources_snapshot"],
            source_ref=_clean_text(item.get("source_ref")),
        )
        rows.append(
            {
                "Source Feed ID": item.get("source_feed_id", ""),
                "标题": item.get("title", ""),
                "来源家族": item.get("source_family", ""),
                "注册组": item.get("registry_group", ""),
                "根路径": item.get("root_path", ""),
                "来源设备": item.get("origin_device", ""),
                "所有者账号ID": item.get("owner_account_id", ""),
                "状态": item.get("status", ""),
                "已识别文件数": item.get("recognized_file_count", ""),
                "未分类文件数": item.get("unclassified_file_count", ""),
                "最近扫描时间": item.get("last_scanned_at", ""),
                "transport_repo": transport["transport_repo"],
                "remote_reachable": transport["remote_reachable"],
                "github_backend": transport["github_backend"],
                "connected_sources_snapshot": transport["connected_sources_snapshot"],
                "missing_sources_snapshot": transport["missing_sources_snapshot"],
                "health_bucket": health_bucket,
                "来源文件": item.get("source_ref", ""),
                "置信度": item.get("confidence", ""),
                "更新时间": item.get("updated_at", ""),
            }
        )
    return rows


def _build_review_rows(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in inventory.get("review_runs", []):
        rows.append(
            {
                "Review ID": item.get("review_id", ""),
                "评审日期": item.get("review_date", ""),
                "范围": item.get("scope", ""),
                "摘要": item.get("summary", ""),
                "top_risks": _text_list(item.get("top_risks", [])),
                "candidate_actions": _text_list(item.get("candidate_actions", [])),
                "human_decision": item.get("human_decision", ""),
                "sync_state": item.get("sync_state", ""),
                "来源文件": item.get("source_ref", ""),
                "置信度": item.get("confidence", ""),
                "更新时间": item.get("updated_at", ""),
            }
        )
    return rows


def _build_decision_rows(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in inventory.get("decision_records", []):
        rows.append(
            {
                "Decision ID": item.get("decision_id", ""),
                "标题": item.get("title", ""),
                "decision_type": item.get("decision_type", ""),
                "decision_state": item.get("decision_state", ""),
                "target_entity_ids": _text_list(item.get("target_entity_ids", [])),
                "decision_summary": item.get("decision_summary", ""),
                "rationale": item.get("rationale", ""),
                "evidence_refs": _text_list(item.get("evidence_refs", [])),
                "decided_by": item.get("decided_by", ""),
                "decision_time": item.get("decision_time", ""),
                "writeback_event_ids": _text_list(item.get("writeback_event_ids", [])),
                "来源文件": item.get("source_ref", ""),
                "置信度": item.get("confidence", ""),
                "更新时间": item.get("updated_at", ""),
            }
        )
    return rows


def _build_governance_event_rows(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in inventory.get("review_runs", []):
        rows.append(
            {
                "治理事件Key": f"review:{item.get('review_id', '')}",
                "记录类型": "review",
                "对象ID": item.get("review_id", ""),
                "标题": item.get("scope", "") or item.get("review_id", ""),
                "scenario_or_trigger": item.get("summary", ""),
                "状态": item.get("sync_state", ""),
                "target_entity_type_or_refs": item.get("scope", ""),
                "allowed_actor_types_or_changed_fields": _text_list(item.get("candidate_actions", [])),
                "required_policy_ids": "",
                "input_contract": "",
                "output_contract": "",
                "writeback_targets_or_decision_id": item.get("human_decision", ""),
                "requires_human_approval": _bool_text(bool(_clean_text(item.get("human_decision")))),
                "verification_state": item.get("sync_state", ""),
                "evidence_refs": item.get("source_ref", ""),
                "triggered_by": "review",
                "event_time": item.get("review_date", "") or item.get("updated_at", ""),
                "来源文件": item.get("source_ref", ""),
                "置信度": item.get("confidence", ""),
                "更新时间": item.get("updated_at", ""),
            }
        )
    for item in inventory.get("decision_records", []):
        rows.append(
            {
                "治理事件Key": f"decision:{item.get('decision_id', '')}",
                "记录类型": "decision",
                "对象ID": item.get("decision_id", ""),
                "标题": item.get("title", ""),
                "scenario_or_trigger": item.get("decision_type", ""),
                "状态": item.get("decision_state", ""),
                "target_entity_type_or_refs": _text_list(item.get("target_entity_ids", [])),
                "allowed_actor_types_or_changed_fields": item.get("rationale", ""),
                "required_policy_ids": "",
                "input_contract": "",
                "output_contract": item.get("decision_summary", ""),
                "writeback_targets_or_decision_id": _text_list(item.get("writeback_event_ids", [])),
                "requires_human_approval": _bool_text(_clean_text(item.get("decided_by")) == "human_owner"),
                "verification_state": item.get("decision_state", ""),
                "evidence_refs": _text_list(item.get("evidence_refs", [])),
                "triggered_by": item.get("decided_by", ""),
                "event_time": item.get("decision_time", "") or item.get("updated_at", ""),
                "来源文件": item.get("source_ref", ""),
                "置信度": item.get("confidence", ""),
                "更新时间": item.get("updated_at", ""),
            }
        )
    for item in inventory.get("actions", []):
        rows.append(
            {
                "治理事件Key": f"action:{item.get('action_id', '')}",
                "记录类型": "action",
                "对象ID": item.get("action_id", ""),
                "标题": item.get("title", ""),
                "scenario_or_trigger": item.get("scenario", ""),
                "状态": item.get("status", ""),
                "target_entity_type_or_refs": item.get("target_entity_type", ""),
                "allowed_actor_types_or_changed_fields": _text_list(item.get("allowed_actor_types", [])),
                "required_policy_ids": _text_list(item.get("required_policy_ids", [])),
                "input_contract": _text_list(item.get("input_contract", {})),
                "output_contract": _text_list(item.get("output_contract", {})),
                "writeback_targets_or_decision_id": _text_list(item.get("writeback_targets", [])),
                "requires_human_approval": _bool_text(item.get("requires_human_approval")),
                "verification_state": "",
                "evidence_refs": item.get("source_ref", ""),
                "triggered_by": "",
                "event_time": item.get("updated_at", ""),
                "来源文件": item.get("source_ref", ""),
                "置信度": item.get("confidence", ""),
                "更新时间": item.get("updated_at", ""),
            }
        )
    for item in inventory.get("writeback_events", []):
        rows.append(
            {
                "治理事件Key": f"writeback:{item.get('writeback_id', '')}",
                "记录类型": "writeback",
                "对象ID": item.get("writeback_id", ""),
                "标题": item.get("action_id", ""),
                "scenario_or_trigger": item.get("action_id", ""),
                "状态": item.get("verification_state", ""),
                "target_entity_type_or_refs": _text_list(item.get("target_refs", [])),
                "allowed_actor_types_or_changed_fields": _text_list(item.get("changed_fields", [])),
                "required_policy_ids": "",
                "input_contract": "",
                "output_contract": "",
                "writeback_targets_or_decision_id": item.get("decision_id", ""),
                "requires_human_approval": "",
                "verification_state": item.get("verification_state", ""),
                "evidence_refs": _text_list(item.get("evidence_refs", [])),
                "triggered_by": item.get("triggered_by", ""),
                "event_time": item.get("writeback_time", "") or item.get("updated_at", ""),
                "来源文件": item.get("source_ref", ""),
                "置信度": item.get("confidence", ""),
                "更新时间": item.get("updated_at", ""),
            }
        )
    return rows


def _derive_control_summary(rows_by_table: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in rows_by_table["threads"]:
        rows.append(
            {
                "对象Key": f"thread:{item['Thread ID']}",
                "对象类型": "thread",
                "对象标题": item["标题"],
                "治理层级": "L1 运营对象层",
                "运营分段": _derive_segment(item["状态"], required_human_input=item["需要人类输入"]),
                "对象状态": item["状态"],
                "目标ID": item["目标ID"],
                "空间ID": item["空间ID"],
                "模块ID": item["模块ID"],
                "component_domain": item.get("component_domain", ""),
                "control_level": item.get("control_level", ""),
                "priority_band": item.get("priority_band", ""),
                "线程ID": item["Thread ID"],
                "父对象ID": item["父任务ID"],
                "负责人模式": item["managed_by"] or "hybrid",
                "human_boundary_state": "needs_user" if item["需要人类输入"] else "",
                "当前摘要": item.get("last_activity_summary", "") or item["开放问题"] or item["主题"],
                "阻塞原因": item["阻塞原因"],
                "需要人类输入": item["需要人类输入"],
                "下一步动作": item.get("frontstage_focus_object", "") or item["下次复查日"],
                "证据入口": item["来源文件"],
                "evidence_strength": item.get("evidence_strength", ""),
                "来源文件": item["来源文件"],
                "置信度": item["置信度"],
                "最近更新时间": item["更新时间"],
            }
        )
    for item in rows_by_table["tasks"]:
        rows.append(
            {
                "对象Key": f"task:{item['Task ID']}",
                "对象类型": "task",
                "对象标题": item["标题"],
                "治理层级": "L1 运营对象层",
                "运营分段": _derive_segment(item["状态"], required_human_input=item["需要人类输入"], priority=item["优先级"]),
                "对象状态": item["状态"],
                "目标ID": item["目标ID"],
                "空间ID": item["空间ID"],
                "模块ID": item["目标模块ID"],
                "component_domain": item.get("component_domain", ""),
                "control_level": item.get("control_level", ""),
                "priority_band": item.get("priority_band", ""),
                "线程ID": item["Thread ID"],
                "父对象ID": item["父任务ID"],
                "负责人模式": item["owner_mode"],
                "human_boundary_state": item["人类边界状态"],
                "当前摘要": item["结果摘要"] or item["验真目标"],
                "阻塞原因": item["阻塞原因"],
                "需要人类输入": item["需要人类输入"],
                "下一步动作": item["下一步"],
                "证据入口": item["证据入口"],
                "evidence_strength": item.get("evidence_strength", ""),
                "来源文件": item["来源文件"],
                "置信度": item["置信度"],
                "最近更新时间": item["更新时间"],
            }
        )
    for item in rows_by_table["skills_capabilities"]:
        object_type = item["记录类型"]
        rows.append(
            {
                "对象Key": f"{object_type}:{item['对象ID']}",
                "对象类型": object_type,
                "对象标题": item["标题"] or item["名称"],
                "治理层级": "L1 运营对象层",
                "运营分段": "background" if item["状态"] == "active" else _derive_segment(item["状态"]),
                "对象状态": item["状态"],
                "目标ID": "",
                "空间ID": "",
                "模块ID": "",
                "component_domain": "",
                "control_level": "",
                "priority_band": "",
                "线程ID": "",
                "父对象ID": "",
                "负责人模式": item["cluster_or_actor"],
                "human_boundary_state": "",
                "当前摘要": item["role"] or item["allowed_action_ids"],
                "阻塞原因": "",
                "需要人类输入": "",
                "下一步动作": "",
                "证据入口": item["来源文件"],
                "evidence_strength": "",
                "来源文件": item["来源文件"],
                "置信度": item["置信度"],
                "最近更新时间": item["更新时间"],
            }
        )
    for item in rows_by_table["source_feeds"]:
        rows.append(
            {
                "对象Key": f"source_feed:{item['Source Feed ID']}",
                "对象类型": "source_feed",
                "对象标题": item["标题"],
                "治理层级": "L1 运营对象层",
                "运营分段": "completed" if item["missing_sources_snapshot"] == "none" else "background",
                "对象状态": item["状态"],
                "目标ID": "",
                "空间ID": "",
                "模块ID": "",
                "component_domain": "",
                "control_level": "",
                "priority_band": "",
                "线程ID": "",
                "父对象ID": "",
                "负责人模式": item["来源设备"],
                "human_boundary_state": "",
                "当前摘要": f"health={item.get('health_bucket', '')} / repo={item['transport_repo']} / backend={item['github_backend']}",
                "阻塞原因": "" if item.get("health_bucket") == "healthy" else item["missing_sources_snapshot"],
                "需要人类输入": "",
                "下一步动作": "继续 emit / aggregate / audit",
                "证据入口": item["来源文件"],
                "evidence_strength": "",
                "来源文件": item["来源文件"],
                "置信度": item["置信度"],
                "最近更新时间": item["更新时间"],
            }
        )
    for item in rows_by_table["review_runs"]:
        rows.append(
            {
                "对象Key": f"review_run:{item['Review ID']}",
                "对象类型": "review_run",
                "对象标题": item["范围"],
                "治理层级": "L2 治理轨迹层",
                "运营分段": "background",
                "对象状态": item["sync_state"],
                "目标ID": "",
                "空间ID": "",
                "模块ID": "",
                "component_domain": "",
                "control_level": "",
                "priority_band": "",
                "线程ID": "",
                "父对象ID": "",
                "负责人模式": "governance",
                "human_boundary_state": "",
                "当前摘要": item["摘要"],
                "阻塞原因": item["top_risks"],
                "需要人类输入": item["human_decision"],
                "下一步动作": item["candidate_actions"],
                "证据入口": item["来源文件"],
                "evidence_strength": "",
                "来源文件": item["来源文件"],
                "置信度": item["置信度"],
                "最近更新时间": item["更新时间"],
            }
        )
    for item in rows_by_table["decision_records"]:
        rows.append(
            {
                "对象Key": f"decision_record:{item['Decision ID']}",
                "对象类型": "decision_record",
                "对象标题": item["标题"],
                "治理层级": "L2 治理轨迹层",
                "运营分段": "completed" if item["decision_state"] == "approved" else "background",
                "对象状态": item["decision_state"],
                "目标ID": "",
                "空间ID": "",
                "模块ID": "",
                "component_domain": "",
                "control_level": "",
                "priority_band": "",
                "线程ID": "",
                "父对象ID": "",
                "负责人模式": item["decided_by"],
                "human_boundary_state": "",
                "当前摘要": item["decision_summary"],
                "阻塞原因": "",
                "需要人类输入": "",
                "下一步动作": item["writeback_event_ids"],
                "证据入口": item["evidence_refs"],
                "evidence_strength": "",
                "来源文件": item["来源文件"],
                "置信度": item["置信度"],
                "最近更新时间": item["更新时间"],
            }
        )
    for item in rows_by_table["governance_events"]:
        rows.append(
            {
                "对象Key": f"{item['记录类型']}:{item['对象ID']}",
                "对象类型": item["记录类型"],
                "对象标题": item["标题"],
                "治理层级": "L2 治理轨迹层",
                "运营分段": "completed" if item["状态"] in {"completed", "active"} else _derive_segment(item["状态"]),
                "对象状态": item["状态"],
                "目标ID": "",
                "空间ID": "",
                "模块ID": "",
                "component_domain": "",
                "control_level": "",
                "priority_band": "",
                "线程ID": "",
                "父对象ID": "",
                "负责人模式": item["triggered_by"] or item["记录类型"],
                "human_boundary_state": "",
                "当前摘要": item["scenario_or_trigger"] or item["target_entity_type_or_refs"],
                "阻塞原因": "",
                "需要人类输入": "",
                "下一步动作": item["writeback_targets_or_decision_id"],
                "证据入口": item["evidence_refs"] or item["来源文件"],
                "evidence_strength": "",
                "来源文件": item["来源文件"],
                "置信度": item["置信度"],
                "最近更新时间": item["更新时间"],
            }
        )
    for item in rows_by_table.get("strategic_linkage", []):
        rows.append(
            {
                "对象Key": f"strategic_linkage:{item['战略链路Key']}",
                "对象类型": "strategic_linkage",
                "对象标题": item["strategy_title"] or item["theme_title"] or item["goal_title"] or item["component_domain"],
                "治理层级": "L1 运营对象层",
                "运营分段": "frontstage" if item["status"] in {"validated", "absorbed"} else "background",
                "对象状态": item["status"],
                "目标ID": item["goal_id"],
                "空间ID": "",
                "模块ID": "",
                "component_domain": item["component_domain"],
                "control_level": item["control_level_scope"],
                "priority_band": "",
                "线程ID": "",
                "父对象ID": "",
                "负责人模式": "strategy_governor",
                "human_boundary_state": "",
                "当前摘要": item["current_gap"] or item["theme_title"],
                "阻塞原因": item["current_gap"],
                "需要人类输入": "",
                "下一步动作": item["next_action"],
                "证据入口": item["evidence_ref"],
                "evidence_strength": "strong" if item["status"] in {"validated", "absorbed"} else "medium",
                "来源文件": item["source_ref"],
                "置信度": 0.94,
                "最近更新时间": item["updated_at"],
            }
        )
    for item in rows_by_table.get("cbm_component_responsibility", []):
        rows.append(
            {
                "对象Key": f"cbm_component_responsibility:{item['组件责任Key']}",
                "对象类型": "cbm_component_responsibility",
                "对象标题": item["component_domain"],
                "治理层级": "L1 运营对象层",
                "运营分段": "wait_human" if "human_owner_missing" in item["owner_gap"] else "background",
                "对象状态": item["status"],
                "目标ID": item["goal_id"],
                "空间ID": "",
                "模块ID": "",
                "component_domain": item["component_domain"],
                "control_level": item["control_level_scope"],
                "priority_band": "",
                "线程ID": "",
                "父对象ID": "",
                "负责人模式": item["owner_mode"],
                "human_boundary_state": "needs_user" if "human_owner_missing" in item["owner_gap"] else "",
                "当前摘要": item["owner_gap"],
                "阻塞原因": item["owner_gap"],
                "需要人类输入": "补齐组件 owner 或 copilot" if item["owner_gap"] else "",
                "下一步动作": item["strategy_id"] or item["workflow_id"],
                "证据入口": item["evidence_ref"],
                "evidence_strength": "medium",
                "来源文件": item["evidence_ref"],
                "置信度": 0.92,
                "最近更新时间": item["updated_at"],
            }
        )
    for item in rows_by_table.get("cbm_component_heatmap", []):
        rows.append(
            {
                "对象Key": f"cbm_component_heatmap:{item['热图Key']}",
                "对象类型": "cbm_component_heatmap",
                "对象标题": item["component_domain"],
                "治理层级": "L1 运营对象层",
                "运营分段": "frontstage" if item["priority_band"] in {"P0", "P1"} else "background",
                "对象状态": item["status"],
                "目标ID": "",
                "空间ID": "",
                "模块ID": "",
                "component_domain": item["component_domain"],
                "control_level": item["control_level"],
                "priority_band": item["priority_band"],
                "线程ID": "",
                "父对象ID": "",
                "负责人模式": item["owner_mode"],
                "human_boundary_state": "",
                "当前摘要": item["kpi_hint"],
                "阻塞原因": item["current_gap"],
                "需要人类输入": "",
                "下一步动作": item["next_action"],
                "证据入口": item["evidence_ref"],
                "evidence_strength": item["evidence_strength"],
                "来源文件": item["evidence_ref"],
                "置信度": 0.92,
                "最近更新时间": item["updated_at"],
            }
        )
    return rows


def _field_dictionary_rows(payloads: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    example_lookup: dict[tuple[str, str], Any] = {}
    for spec in CONTROL_BASE_TABLE_SPECS:
        rows = payloads.get(spec["table_id"], [])
        if rows:
            first = rows[0]
            example_lookup[(spec["table_id"], spec["primary"]["name"])] = first.get(spec["primary"]["name"], "")
            for field in spec["fields"]:
                example_lookup[(spec["table_id"], field["name"])] = first.get(field["name"], "")
    records: list[dict[str, Any]] = []
    for spec in CONTROL_BASE_TABLE_SPECS:
        table_family = spec["table_id"]
        primary = spec["primary"]
        for field in [primary] + spec["fields"]:
            records.append(
                {
                    "字段Key": f"{table_family}:{field['english_name']}",
                    "对象家族": table_family,
                    "中文字段名": field["name"],
                    "英文字段名": field["english_name"],
                    "对应canonical路径": field["canonical_path"],
                    "字段层级": "L0 总控驾驶舱层" if table_family == "control_objects" else ("L2 治理轨迹层" if table_family in {"review_runs", "decision_records", "governance_events"} else "L1 运营对象层"),
                    "字段用途": spec["description"],
                    "机器写入": _bool_text(field["machine_written"]),
                    "人类可编辑": _bool_text(field["human_editable"]),
                    "示例值": _text_list(example_lookup.get((table_family, field["name"]), "")),
                    "说明": field["description"],
                    "来源文档": "原力OS对象与字段字典 v1",
                    "更新时间": iso_now(),
                }
            )
    return records


def _payloads_from_inventory(inventory: dict[str, Any], scope: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    runtime_context = _derive_runtime_context(inventory)
    rows_by_table = {
        "threads": _build_threads_rows(inventory, runtime_context),
        "tasks": _build_tasks_rows(inventory, runtime_context),
        "strategic_linkage": _build_strategic_linkage_rows(runtime_context),
        "skills_capabilities": _build_skills_capabilities_rows(inventory),
        "source_feeds": _build_source_rows(inventory, scope),
        "review_runs": _build_review_rows(inventory),
        "decision_records": _build_decision_rows(inventory),
        "governance_events": _build_governance_event_rows(inventory),
    }
    rows_by_table["cbm_component_responsibility"] = _build_cbm_component_responsibility_rows(
        inventory,
        runtime_context,
        rows_by_table["strategic_linkage"],
    )
    rows_by_table["cbm_component_heatmap"] = _build_cbm_component_heatmap_rows(
        inventory,
        runtime_context,
        rows_by_table["threads"],
        rows_by_table["tasks"],
    )
    rows_by_table["control_objects"] = _derive_control_summary(rows_by_table)
    rows_by_table["field_dictionary"] = _field_dictionary_rows(rows_by_table)
    return rows_by_table


def _schema_manifest() -> dict[str, Any]:
    tables: list[dict[str, Any]] = []
    for spec in CONTROL_BASE_TABLE_SPECS:
        tables.append(
            {
                "table_name": spec["table_name"],
                "primary_field": spec["primary"]["name"],
                "fields": [
                    {"name": field["name"], "type": field["type"]}
                    for field in spec["fields"]
                ],
                "views": spec["views"],
            }
        )
    return {"tables": tables}


def _render_table_navigation(spec: dict[str, Any]) -> list[str]:
    lines = [
        f"## {spec['table_name']}",
        "",
        f"- 角色：{spec['description']}",
        f"- 主键：{spec['primary']['name']}",
        f"- 默认视图：{' / '.join(spec['views'])}",
        "",
        "### 字段",
    ]
    for field in [spec["primary"]] + spec["fields"]:
        lines.append(f"- {field['name']} :: {field['description']}")
    return lines


def _document_markdown(inventory: dict[str, Any], link: str) -> dict[str, str]:
    sources = [
        "collaboration-charter",
        "meta-constitution",
        "operational ontology v0",
        "policy boundary v0",
    ]
    table_names = [spec["table_name"] for spec in CONTROL_BASE_TABLE_SPECS]
    whitepaper = "\n".join(
        [
            "# 原力OS白皮书 v1",
            "",
            f"- 生成时间：{iso_now()}",
            "- 外显名称：原力OS",
            "- 内部治理引擎：AI大管家",
            "",
            "## 为什么是原力OS",
            "",
            "原力OS 是把 AI大管家 这套治理能力外显成一套人类可理解、可运营、可交接的操作系统语言。",
            "它不是又一个聊天助手，而是一套把目标、边界、执行、验真、闭环和进化组织在一起的治理系统。",
            "",
            "## AI大管家 与 原力OS 的关系",
            "",
            "- 原力OS：对人类展示的系统外壳、概念语言和运营界面。",
            "- AI大管家：原力OS 背后的治理引擎，负责路由、约束、验真、闭环和进化。",
            "- 人类：共同治理者，不负责替系统拆每一步，而负责目标、边界和不可替代判断。",
            "",
            "## 宪章与初始条件",
            "",
            "- 初始目的：递归进化。",
            "- 基本方法：最小负熵优先。",
            "- 工具定位：工具的工具。",
            "- 执行 DNA：递归、统帅、克制、闭环进化。",
            "- 协作单位：一次递归进化回合，而不是一次随手问答。",
            "",
            "## 三层结构",
            "",
            "### 目的层",
            "",
            "- 解释这件事为什么值得做，系统要把你带向哪里。",
            "- 对应白皮书里的愿景、长期目标和治理观。",
            "",
            "### 方法层",
            "",
            "- 规定如何做最小充分路由、少打扰推进、边界清晰中断。",
            "- 对应协作协议、任务分层、终态定义和验真标准。",
            "",
            "### 工具层",
            "",
            "- 由线程、任务、技能、能力、数据源、review、决策、动作、写回组成。",
            "- 这些对象会在协同治理 base 中被结构化呈现。",
            "",
            "## 运行层对象系统",
            "",
            f"- 当前纳管线程：{len(inventory.get('threads', []))}",
            f"- 当前纳管任务：{len(inventory.get('tasks', []))}",
            f"- 当前纳管技能：{len(inventory.get('skills', []))}",
            f"- 当前纳管能力：{len(inventory.get('agent_capabilities', []))}",
            f"- 当前纳管数据源：{len(inventory.get('source_feeds', []))}",
            f"- 当前 review 批次：{len(inventory.get('review_runs', []))}",
            f"- 当前决策记录：{len(inventory.get('decision_records', []))}",
            f"- 当前动作与写回：{len(inventory.get('actions', [])) + len(inventory.get('writeback_events', []))}",
            "",
            "这些对象共同回答三件事：现在有什么、谁能做什么、做完之后如何留下证据并继续进化。",
            "",
            "## 策略边界与人类边界",
            "",
            "- AI 默认可以 read/propose；只有明确 capability 绑定后才 execute。",
            "- human_owner 拥有 read/propose/execute/approve 全权限。",
            "- 默认只在 登录、授权、付款、不可逆发布/删除、不可替代主观判断 时打断你。",
            "- 高风险动作必须能追到 evidence_refs、DecisionRecord 和 WritebackEvent。",
            "",
            "## 闭环与进化机制",
            "",
            "- 原力OS 不以动作完成为结束，而以路径清晰、结果验真、证据落地、下一轮可复用为结束。",
            "- 终态最少区分：completed / blocked_needs_user / blocked_system / failed_partial。",
            "- 每轮有意义的任务都要沉淀 effective_patterns、wasted_patterns、next_iterate。",
            "",
            "## 本版概念来源",
            "",
            *[f"- {item}" for item in sources],
        ]
    )
    manual = "\n".join(
        [
            "# 原力OS使用说明书 v1",
            "",
            "## 你是谁 / 它是谁",
            "",
            "- 你是共同治理者，负责目标、边界和不可替代判断。",
            "- 原力OS 是对人类展示的治理操作系统。",
            "- AI大管家 是原力OS 的内部治理引擎。",
            "",
            "## 如何提任务",
            "",
            "你优先给目标、成功标准、约束和不可替代主观边界，不需要先替系统拆步骤。",
            "如果你有很多想法，可以先连续讲；系统默认先接住，再整理，再推进。",
            "",
            "## 连续想法输入模式",
            "",
            "- 你可以直接说：你先收着听。",
            "- 系统先短回应接住，不抢节奏。",
            "- 你说“我讲完了”后，再进入结构化整理和推进。",
            "",
            "## 什么情况下会打断你",
            "",
            "- 登录",
            "- 授权",
            "- 付款",
            "- 不可逆发布",
            "- 不可逆删除",
            "- 不可替代主观判断",
            "",
            "## 终态如何定义",
            "",
            "- completed：本地或当前边界内已经真闭环。",
            "- blocked_needs_user：只差你补一个明确输入。",
            "- blocked_system：方向没问题，但被系统级运行时或基础设施挡住。",
            "- failed_partial：保留了证据和恢复入口，但当前执行没有跑通。",
            "",
            "## 日常 emit / aggregate / audit 怎么看",
            "",
            "- 先看协同治理 base 的总控对象主表。",
            "- 再看线程总表、任务总表和数据源同步表。",
            "- 如果你要知道今天该看什么，优先看“待你处理”和“系统阻塞”视图。",
            "",
            f"## 运营容器\n\n- 协同治理 Base：{link}",
        ]
    )
    operations_navigation = "\n".join(
        [
            "# 协同治理运营导航 v1",
            "",
            f"- 目标 Base：{link}",
            f"- 表总数：{len(CONTROL_BASE_TABLE_SPECS)}",
            "",
            "## 先看什么",
            "",
            "1. 总控对象主表：看整体前台、阻塞和待你处理。",
            "2. 线程总表：看每条主线现在做到哪一步。",
            "3. 任务总表：看执行单、边界和下一步。",
            "4. 数据源同步表：看 transport 和三端状态。",
            "5. 决策记录表 / 治理动作与写回表：看为什么这么做、做完写回到哪。",
            "",
            "## 表结构总览",
            "",
            *[f"- {name}" for name in table_names],
            "",
            *sum((_render_table_navigation(spec) + [""] for spec in CONTROL_BASE_TABLE_SPECS), []),
        ]
    )
    field_dictionary = "\n".join(
        [
            "# 原力OS对象与字段字典 v1",
            "",
            "这份字典是白皮书概念层与协同治理多维表之间的桥。",
            "同一个字段会同时说明：它服务什么对象、来自哪个 canonical 路径、默认由谁写、你是否应该手改。",
            "",
            *sum(
                (
                    [
                        f"## {spec['table_name']}",
                        "",
                        f"- 表角色：{spec['description']}",
                        f"- 主键：{spec['primary']['name']} -> {spec['primary']['canonical_path']}",
                        "",
                        "### 字段说明",
                    ]
                    + [
                        f"- {field['name']} :: {field['canonical_path']} :: 机器写入={_bool_text(field['machine_written'])} :: 人类可编辑={_bool_text(field['human_editable'])} :: {field['description']}"
                        for field in spec["fields"]
                    ]
                    + [""]
                    for spec in CONTROL_BASE_TABLE_SPECS
                ),
                [],
            ),
        ]
    )
    overview = "\n".join(
        [
            "# 原力OS总览",
            "",
            "原力OS 是 AI大管家 的人类外显层。你可以把它理解成：一套把任务、线程、技能、来源、决策和写回组织在一起的人机协同治理系统。",
            "",
            f"- 当前目标 Base：{link}",
            f"- 当前线程数：{len(inventory.get('threads', []))}",
            f"- 当前任务数：{len(inventory.get('tasks', []))}",
            f"- 当前技能数：{len(inventory.get('skills', []))}",
            f"- 当前来源数：{len(inventory.get('source_feeds', []))}",
            "",
            "## 文档导航",
            "",
            "- 原力OS白皮书 v1：待写入后回填 URL",
            "- 原力OS使用说明书 v1：待写入后回填 URL",
            "- 原力OS对象与字段字典 v1：待写入后回填 URL",
            "- 协同治理运营导航 v1：待写入后回填 URL",
            "",
            "## 数据运营入口",
            "",
            f"- 协同治理 Base：{link}",
            "- 核心运营入口：总控对象主表 -> 前台主线 / 待你处理 / 系统阻塞 / 已完成 / 后台队列",
            "",
            "## 当前版本边界",
            "",
            "- 外显名称统一为原力OS。",
            "- 内部脚本、环境变量和运行引擎仍沿用 AI大管家 命名。",
            "- 文档层级通过根索引页导航表达，不依赖 Wiki 子节点自动创建。",
        ]
    )
    return {
        "overview": overview,
        "whitepaper": whitepaper,
        "manual": manual,
        "field_dictionary": field_dictionary,
        "operations_navigation": operations_navigation,
    }


def _write_local_bundle(markdowns: dict[str, str], payloads: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    WHITEPAPER_ROOT.mkdir(parents=True, exist_ok=True)
    PAYLOADS_ROOT.mkdir(parents=True, exist_ok=True)
    local_docs: list[dict[str, Any]] = []
    for definition in DOCUMENT_DEFINITIONS:
        key = definition["key"]
        content = markdowns[key]
        doc_path = WHITEPAPER_ROOT / f"{key}.md"
        chunks = _chunk_markdown(content)
        chunks_path = WHITEPAPER_ROOT / f"{key}.chunks.json"
        write_text(doc_path, content)
        write_json(chunks_path, {"key": key, "title": definition["title"], "chunks": chunks})
        local_docs.append(
            {
                "key": key,
                "title": definition["title"],
                "markdown_path": str(doc_path),
                "chunks_path": str(chunks_path),
                "chunk_count": len(chunks),
            }
        )
    manifest = _schema_manifest()
    schema_path = CONTROL_BASE_CURRENT_ROOT / "schema-manifest.json"
    write_json(schema_path, manifest)
    for spec in CONTROL_BASE_TABLE_SPECS:
        payload_path = PAYLOADS_ROOT / f"{spec['table_id']}.json"
        write_json(payload_path, payloads[spec["table_id"]])
    write_text(CONTROL_BASE_CURRENT_ROOT / "field-dictionary.md", markdowns["field_dictionary"])
    return {
        "documents": local_docs,
        "schema_manifest_path": str(schema_path),
        "payload_dir": str(PAYLOADS_ROOT),
        "field_dictionary_markdown_path": str(CONTROL_BASE_CURRENT_ROOT / "field-dictionary.md"),
    }


def _normalize_payload_rows(payloads: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    normalized: dict[str, list[dict[str, Any]]] = {}
    for spec in CONTROL_BASE_TABLE_SPECS:
        rows: list[dict[str, Any]] = []
        field_types = {spec["primary"]["name"]: spec["primary"]["type"]}
        field_types.update({field["name"]: field["type"] for field in spec["fields"]})
        for item in payloads[spec["table_id"]]:
            row: dict[str, Any] = {}
            for field_name, field_type in field_types.items():
                row[field_name] = _normalize_for_field(_field_value(item, field_name), field_type)
            rows.append(row)
        normalized[spec["table_id"]] = rows
    return normalized


def _render_summary(
    *,
    status: str,
    link: str,
    inventory: dict[str, Any],
    docs_status: str,
    base_status: str,
    payloads: dict[str, list[dict[str, Any]]],
    blocker: str = "",
) -> str:
    lines = [
        "# 原力OS白皮书 + 协同治理 Base 同步摘要",
        "",
        f"- 生成时间：{iso_now()}",
        f"- 目标链接：{link}",
        f"- 总状态：{status}",
        f"- docs phase：{docs_status}",
        f"- base phase：{base_status}",
        "",
        "## 当前纳管规模",
        "",
        f"- threads={len(inventory.get('threads', []))}",
        f"- tasks={len(inventory.get('tasks', []))}",
        f"- skills={len(inventory.get('skills', []))}",
        f"- capabilities={len(inventory.get('agent_capabilities', []))}",
        f"- source_feeds={len(inventory.get('source_feeds', []))}",
        f"- reviews={len(inventory.get('review_runs', []))}",
        f"- decisions={len(inventory.get('decision_records', []))}",
        f"- governance_events={len(inventory.get('actions', [])) + len(inventory.get('writeback_events', []))}",
        "",
        "## Payload 记录数",
        "",
    ]
    for spec in CONTROL_BASE_TABLE_SPECS:
        lines.append(f"- {spec['table_name']}：{len(payloads.get(spec['table_id'], []))}")
    lines.extend(
        [
            "",
            "## 说明",
            "",
            "- 旧的 `文本` 表保留为 legacy_text_staging，不在本轮 schema manifest 中覆盖。",
            "- 文档层级通过 `原力OS总览` 根索引页导航表达。",
        ]
    )
    if blocker:
        lines.extend(["", "## 阻塞", "", f"- {blocker}"])
    return "\n".join(lines)


def _sync_documents(
    scope: dict[str, Any],
    *,
    link: str,
    markdowns: dict[str, str],
) -> dict[str, Any]:
    script = _scope_script(scope, "feishu_doc_script", DEFAULT_FEISHU_DOC_SCRIPT)
    state = read_json(SYNC_STATE_PATH, default={"documents": {}})
    state_documents = state.get("documents", {}) if isinstance(state.get("documents", {}), dict) else {}
    if not all(os.getenv(key, "").strip() for key in FEISHU_ENV_VARS):
        return {
            "status": "blocked_missing_credentials",
            "blocker": "Missing FEISHU_APP_ID or FEISHU_APP_SECRET; local whitepaper and payloads were generated but apply stopped before Feishu writes.",
            "script": str(script),
        }
    if not script.exists():
        return _sync_documents_native(link, markdowns=markdowns, state_documents=state_documents)
    results: dict[str, Any] = {"status": "completed", "documents": {}, "script": str(script)}

    # Create or reuse non-overview docs first, then rewrite overview with final URLs.
    ordered = [item for item in DOCUMENT_DEFINITIONS if item["key"] != "overview"] + [next(item for item in DOCUMENT_DEFINITIONS if item["key"] == "overview")]

    for definition in ordered:
        key = definition["key"]
        title = definition["title"]
        entry = state_documents.get(key, {}) if isinstance(state_documents.get(key, {}), dict) else {}
        token = str(entry.get("document_id", "")).strip()
        url = str(entry.get("url", "")).strip()
        if not token:
            created = _run_command(_command_for_script(script) + ["--action", "create", "--title", title])
            if created["returncode"] != 0 or not isinstance(created["json"], dict):
                return _sync_documents_native(
                    link,
                    markdowns=markdowns,
                    state_documents=state_documents,
                    existing_results={"status": "completed", "documents": dict(results["documents"]), "script": str(script)},
                )
            token = str(created["json"].get("document_id", "") or created["json"].get("doc_token", "")).strip()
            url = str(created["json"].get("url", "")).strip()
        content = markdowns[key]
        if key == "overview":
            overview_lines = []
            for line in content.splitlines():
                if "待写入后回填 URL" not in line:
                    overview_lines.append(line)
                    continue
                if "白皮书" in line:
                    replacement = results["documents"]["whitepaper"]["url"]
                elif "使用说明书" in line:
                    replacement = results["documents"]["manual"]["url"]
                elif "字段字典" in line:
                    replacement = results["documents"]["field_dictionary"]["url"]
                else:
                    replacement = results["documents"]["operations_navigation"]["url"]
                overview_lines.append(line.replace("待写入后回填 URL", replacement))
            content = "\n".join(overview_lines)
        chunks = _chunk_markdown(content)
        write_first = _run_command(_command_for_script(script) + ["--action", "write", "--token", token, "--content", chunks[0]])
        if write_first["returncode"] != 0:
            return _sync_documents_native(
                link,
                markdowns=markdowns,
                state_documents=state_documents,
                existing_results={"status": "completed", "documents": dict(results["documents"]), "script": str(script)},
            )
        for chunk in chunks[1:]:
            appended = _run_command(_command_for_script(script) + ["--action", "append", "--token", token, "--content", chunk])
            if appended["returncode"] != 0:
                return _sync_documents_native(
                    link,
                    markdowns=markdowns,
                    state_documents=state_documents,
                    existing_results={"status": "completed", "documents": dict(results["documents"]), "script": str(script)},
                )
        state_documents[key] = {"document_id": token, "url": url, "title": title, "updated_at": iso_now()}
        results["documents"][key] = {"title": title, "document_id": token, "url": url, "chunk_count": len(chunks)}

    write_json(SYNC_STATE_PATH, {"documents": state_documents, "updated_at": iso_now(), "link": link})
    return results


def _sync_base(
    scope: dict[str, Any],
    *,
    link: str,
    schema_manifest_path: Path,
    payloads: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    if not all(os.getenv(key, "").strip() for key in FEISHU_ENV_VARS):
        return {
            "status": "blocked_missing_credentials",
            "blocker": "Missing FEISHU_APP_ID or FEISHU_APP_SECRET; local schema and payloads were generated but apply stopped before Feishu base sync.",
            "script": "native_openapi_base_link",
        }
    if not _is_test_feishu_stub_env():
        try:
            token = _feishu_tenant_access_token()
            app_token = _resolve_bitable_app_token(link, token=token)
        except RuntimeError as exc:
            return {
                "status": "failed_partial",
                "blocker": str(exc),
                "script": "native_openapi_base_link",
            }
        if app_token:
            try:
                return _sync_base_via_base_link(
                    link,
                    payloads=payloads,
                    token=token,
                    app_token=app_token,
                )
            except RuntimeError as exc:
                return {
                    "status": "failed_partial",
                    "blocker": str(exc),
                    "script": "native_openapi_base_link",
                }

    script = _scope_script(scope, "feishu_bitable_bridge_script", DEFAULT_FEISHU_BITABLE_BRIDGE_SCRIPT)
    if not script.exists():
        return {
            "status": "blocked_missing_tool",
            "blocker": f"feishu-bitable-bridge script not found: {script}",
            "script": str(script),
        }
    schema_preview = _run_command(
        _command_for_script(script)
        + ["sync-base-schema", "--link", link, "--manifest", str(schema_manifest_path), "--dry-run"]
    )
    if schema_preview["returncode"] != 0 or not isinstance(schema_preview["json"], dict):
        return {
            "status": "failed_partial",
            "blocker": schema_preview["stderr"].strip() or schema_preview["stdout"].strip() or "sync-base-schema dry-run failed",
            "script": str(script),
            "schema_preview": schema_preview,
        }
    schema_apply = _run_command(
        _command_for_script(script)
        + ["sync-base-schema", "--link", link, "--manifest", str(schema_manifest_path), "--apply"]
    )
    if schema_apply["returncode"] != 0 or not isinstance(schema_apply["json"], dict):
        return {
            "status": "failed_partial",
            "blocker": schema_apply["stderr"].strip() or schema_apply["stdout"].strip() or "sync-base-schema apply failed",
            "script": str(script),
            "schema_preview": schema_preview["json"],
            "schema_apply": schema_apply,
        }

    table_results = []
    apply_tables = schema_apply["json"].get("tables", [])
    for spec in CONTROL_BASE_TABLE_SPECS:
        table_result = next((item for item in apply_tables if item.get("table_name") == spec["table_name"]), None)
        if not table_result:
            return {
                "status": "failed_partial",
                "blocker": f"Schema apply result missing table: {spec['table_name']}",
                "script": str(script),
                "schema_preview": schema_preview["json"],
                "schema_apply": schema_apply["json"],
                "tables": table_results,
            }
        payload_path = PAYLOADS_ROOT / f"{spec['table_id']}.json"
        table_link = str(table_result.get("table_link") or "").strip() or _compose_table_link(link, str(table_result.get("table_id", "")))
        preview = _run_command(
            _command_for_script(script)
            + [
                "upsert-records",
                "--link",
                table_link,
                "--payload-file",
                str(payload_path),
                "--primary-field",
                spec["primary"]["name"],
                "--dry-run",
            ]
        )
        preview_json = preview["json"] if isinstance(preview["json"], dict) else {}
        if preview["returncode"] != 0 or not preview_json.get("summary", {}).get("can_apply", False):
            return {
                "status": "failed_partial",
                "blocker": preview["stderr"].strip() or preview["stdout"].strip() or f"upsert preview failed for {spec['table_name']}",
                "script": str(script),
                "schema_preview": schema_preview["json"],
                "schema_apply": schema_apply["json"],
                "tables": table_results + [{"table_name": spec["table_name"], "preview": preview_json}],
            }
        applied = _run_command(
            _command_for_script(script)
            + [
                "upsert-records",
                "--link",
                table_link,
                "--payload-file",
                str(payload_path),
                "--primary-field",
                spec["primary"]["name"],
                "--apply",
            ]
        )
        if applied["returncode"] != 0 or not isinstance(applied["json"], dict):
            return {
                "status": "failed_partial",
                "blocker": applied["stderr"].strip() or applied["stdout"].strip() or f"upsert apply failed for {spec['table_name']}",
                "script": str(script),
                "schema_preview": schema_preview["json"],
                "schema_apply": schema_apply["json"],
                "tables": table_results + [{"table_name": spec["table_name"], "preview": preview_json, "apply": applied}],
            }
        table_results.append(
            {
                "table_id": spec["table_id"],
                "table_name": spec["table_name"],
                "table_link": table_link,
                "payload_count": len(payloads[spec["table_id"]]),
                "preview": preview_json,
                "apply": applied["json"],
            }
        )
    return {
        "status": "completed",
        "script": str(script),
        "schema_preview": schema_preview["json"],
        "schema_apply": schema_apply["json"],
        "tables": table_results,
    }


def sync_yuanli_os_control_impl(
    link: str,
    *,
    scope_path: Path | None = None,
    dry_run: bool = False,
    apply: bool = False,
) -> dict[str, Any]:
    if dry_run == apply:
        raise RuntimeError("Use exactly one of --dry-run or --apply.")
    scope = load_source_scope(scope_path)
    inventory = build_inventory(scope_path)
    inventory = ensure_inventory(scope_path)
    payload_rows = _payloads_from_inventory(inventory, scope)
    payloads = _normalize_payload_rows(payload_rows)
    markdowns = _document_markdown(inventory, link)
    local_bundle = _write_local_bundle(markdowns, payloads)

    docs_result: dict[str, Any] = {
        "status": "preview_ready",
        "documents": local_bundle["documents"],
        "script": str(_scope_script(scope, "feishu_doc_script", DEFAULT_FEISHU_DOC_SCRIPT)),
    }
    base_result: dict[str, Any] = {
        "status": "preview_ready",
        "schema_manifest_path": local_bundle["schema_manifest_path"],
        "payload_dir": local_bundle["payload_dir"],
        "script": str(_scope_script(scope, "feishu_bitable_bridge_script", DEFAULT_FEISHU_BITABLE_BRIDGE_SCRIPT)),
        "tables": [
            {
                "table_id": spec["table_id"],
                "table_name": spec["table_name"],
                "payload_count": len(payloads[spec["table_id"]]),
                "views": spec["views"],
            }
            for spec in CONTROL_BASE_TABLE_SPECS
        ],
    }
    blocker = ""
    status = "preview_ready"
    link_resolution = {
        "mode": "preview_unresolved",
        "docs_link": link,
        "base_link": link,
        "docs_title": "",
        "base_title": "",
    }
    if apply:
        docs_result = _sync_documents(scope, link=link, markdowns=markdowns)
        if docs_result["status"] != "completed":
            blocker = str(docs_result.get("blocker", "")).strip()
            base_result["status"] = "blocked_docs_phase"
            status = docs_result["status"]
        else:
            link_resolution = _resolve_control_links(link)
            base_result = _sync_base(
                scope,
                link=str(link_resolution.get("base_link", link)),
                schema_manifest_path=Path(local_bundle["schema_manifest_path"]),
                payloads=payloads,
            )
            if base_result["status"] != "completed":
                blocker = str(base_result.get("blocker", "")).strip()
                status = base_result["status"]
            else:
                status = "completed"

    summary = _render_summary(
        status=status,
        link=link,
        inventory=inventory,
        docs_status=docs_result["status"],
        base_status=base_result["status"],
        payloads=payloads,
        blocker=blocker,
    )
    summary_path = CONTROL_BASE_CURRENT_ROOT / "sync-summary.md"
    result_path = CONTROL_BASE_CURRENT_ROOT / "sync-result.json"
    write_text(summary_path, summary)
    result = {
        "generated_at": iso_now(),
        "link": link,
        "mode": "dry-run" if dry_run else "apply",
        "status": status,
        "docs_link": str(link_resolution.get("docs_link", link)),
        "base_link": str(link_resolution.get("base_link", link)),
        "link_resolution": link_resolution,
        "artifact_root": str(CONTROL_BASE_CURRENT_ROOT),
        "whitepaper_root": str(WHITEPAPER_ROOT),
        "schema_manifest_path": local_bundle["schema_manifest_path"],
        "payload_dir": local_bundle["payload_dir"],
        "field_dictionary_markdown_path": local_bundle["field_dictionary_markdown_path"],
        "docs": docs_result,
        "base": base_result,
        "inventory_counts": inventory.get("counts", {}),
        "legacy_table_policy": "legacy_text_staging preserved and untouched",
        "blocker": blocker,
        "summary_path": str(summary_path),
    }
    write_json(result_path, result)
    return result
