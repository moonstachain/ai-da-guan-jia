# 把原力OS 从治理总控舱升级成总控舱加组件驾驶舱，让共同治理者同时看见控制态、组件失衡、责任缺口、优先级和行动队列。仪表盘

## Summary
- Goal: 把原力OS 从治理总控舱升级成总控舱加组件驾驶舱，让共同治理者同时看见控制态、组件失衡、责任缺口、优先级和行动队列。
- Audience: 共同治理者, AI大管家, 治理运营者, 第一次接触原力OS的人类协作者
- Time grain: day

## Official Boundary
- OpenAPI-capable: bitable app metadata, tables, fields, records, views, dashboard list, dashboard copy
- Manual or template-driven: dashboard card creation, widget binding, canvas layout placement

## Overview Layer
- 当前系统处于什么控制态？
  - Type: table
  - Source view: `view-dq-overview-01`
- 当前真正处于前台推进的主线有哪些？
  - Type: bar_chart
  - Source view: `view-dq-overview-02`
- 当前有多少事项必须由你介入？
  - Type: bar_chart
  - Source view: `view-dq-overview-03`
- 当前有多少系统级阻塞正在挡路？
  - Type: bar_chart
  - Source view: `view-dq-overview-04`
- 哪些组件当前优先级最高？
  - Type: bar_chart
  - Source view: `view-dq-component-01`
- 哪些组件在 direct、control、execute 上最失衡？
  - Type: table
  - Source view: `view-dq-component-02`
- 哪些组件的人类 Owner 或 AI Copilot 仍然缺位？
  - Type: table
  - Source view: `view-dq-component-03`
- 哪些组件 gap 最大、最值得优先补？
  - Type: table
  - Source view: `view-dq-component-04`

## Diagnosis Layer
- 当前主会场到底在推什么？
  - Type: table
  - Source view: `view-dq-diagnosis-01`
- 哪些任务是真推进，哪些只是看起来在推进？
  - Type: table
  - Source view: `view-dq-diagnosis-02`
- 数据源与证据链当前健康吗？
  - Type: bar_chart
  - Source view: `view-dq-diagnosis-03`
- 最近系统做了哪些 review、decision 和 writeback？
  - Type: line_chart
  - Source view: `view-dq-diagnosis-04`

## Action Layer
- 哪些事项必须由你立即处理？
  - Type: table
  - Source view: `view-dq-action-01`
- 哪些系统阻塞不能再假推进，必须单独处理？
  - Type: table
  - Source view: `view-dq-action-02`
- 如果现在开始推进，优先动作是什么？
  - Type: table
  - Source view: `view-dq-action-03`
- 哪些能力价值高，但审批或授权摩擦仍然很大？
  - Type: table
  - Source view: `view-dq-action-04`

## Source Views

- overview-当前系统处于什么控制态 (总控对象主表)
  - Filters: time grain = day
  - Display fields: 对象状态
- overview-当前真正处于前台推进的主线有哪些 (线程总表)
  - Filters: time grain = day; status in [active, frontstage_now]
  - Display fields: 运营分段, title, goal_id, component_domain, control_level, status, required_human_input, blocker_reason
- overview-当前有多少事项必须由你介入 (总控对象主表)
  - Filters: time grain = day; 需要人类输入 != 空
  - Display fields: human_boundary_state, 对象标题, component_domain, control_level, 需要人类输入, 阻塞原因, 下一步动作, evidence_ref
- overview-当前有多少系统级阻塞正在挡路 (总控对象主表)
  - Filters: time grain = day; 对象状态 = blocked_system
  - Display fields: 对象状态, 对象标题, component_domain, control_level, 阻塞原因, 下一步动作, evidence_ref
- overview-哪些组件当前优先级最高 (CBM组件热图表)
  - Filters: time grain = day; priority_band in [P0, P1] AND next_action != 空
  - Display fields: component_domain, priority_band, control_level, current_gap, next_action, latest_decision_id, latest_writeback_id
- overview-哪些组件在-direct-control-execute-上最失衡 (CBM组件热图表)
  - Filters: time grain = day; current_gap != 空
  - Display fields: component_domain, control_level, current_gap, priority_band, next_action, latest_decision_id
- overview-哪些组件的人类-owner-或-ai-copilot-仍然缺位 (CBM组件责任表)
  - Filters: time grain = day; owner_gap != none
  - Display fields: component_domain, owner_gap, control_level_scope, human_owner, ai_copilot, goal_id, strategy_id, evidence_ref
- overview-哪些组件-gap-最大-最值得优先补 (CBM组件热图表)
  - Filters: time grain = day; priority_band in [P0, P1]
  - Display fields: component_domain, priority_band, evidence_strength, control_level, kpi_hint, current_gap, next_action
- diagnosis-当前主会场到底在推什么 (线程总表)
  - Filters: time grain = day; status in [active, frontstage_now]
  - Display fields: component_domain, title, goal_id, control_level, status, required_human_input, blocker_reason
- diagnosis-哪些任务是真推进-哪些只是看起来在推进 (任务总表)
  - Filters: time grain = day; task_status in [waiting, blocked_needs_user, blocked_system]
  - Display fields: task_status, priority_band, title, thread_id, component_domain, control_level, next_action, evidence_ref
- diagnosis-数据源与证据链当前健康吗 (数据源同步表)
  - Filters: time grain = day; status != healthy OR missing_sources_snapshot != none
  - Display fields: status, title, source_family, remote_reachable, missing_sources_snapshot, connected_sources_snapshot
- diagnosis-最近系统做了哪些-review-decision-和-writeback (治理动作与写回表)
  - Filters: time grain = day; event_time within last 14 days
  - Display fields: review_date, title, record_type, status, verification_state, evidence_refs, event_time
- action-哪些事项必须由你立即处理 (总控对象主表)
  - Filters: 需要人类输入 != 空
  - Display fields: 对象标题, component_domain, control_level, 需要人类输入, 阻塞原因, 下一步动作, evidence_ref
- action-哪些系统阻塞不能再假推进-必须单独处理 (总控对象主表)
  - Filters: 对象状态 = blocked_system
  - Display fields: 对象标题, component_domain, control_level, 阻塞原因, 下一步动作, evidence_ref
- action-如果现在开始推进-优先动作是什么 (CBM组件热图表)
  - Filters: priority_band in [P0, P1] AND next_action != 空
  - Display fields: component_domain, priority_band, control_level, current_gap, next_action, latest_decision_id, latest_writeback_id
- action-哪些能力价值高-但审批或授权摩擦仍然很大 (技能与能力表)
  - Filters: requires_human_approval = true
  - Display fields: cluster_or_actor, name, routing_credit, verification_strength, requires_human_approval, status

## Manual Binding Notes

- Bind cards manually in the dashboard UI.
- Keep source views as the stable integration contract.
