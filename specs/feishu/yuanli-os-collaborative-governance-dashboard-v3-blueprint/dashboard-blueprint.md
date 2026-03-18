# 为原力OS生成一个单页协同治理控制台，让陌生人先理解系统身份与协同方式，再帮助人类判断当前控制态、阻塞边界、证据线索和下一步动作。仪表盘

## Summary
- Goal: 为原力OS生成一个单页协同治理控制台，让陌生人先理解系统身份与协同方式，再帮助人类判断当前控制态、阻塞边界、证据线索和下一步动作。
- Audience: hay, 原力OS 人类协作者, 第一次接触原力OS的人类运营者
- Time grain: day

## Official Boundary
- OpenAPI-capable: bitable app metadata, tables, fields, records, views, dashboard list, dashboard copy
- Manual or template-driven: dashboard card creation, widget binding, canvas layout placement

## Overview Layer
- 当前真正处于前台推进的主线有几条？
  - Type: bar_chart
  - Source view: `view-dq-kpi-01`
- 当前有多少事项只差我输入？
  - Type: bar_chart
  - Source view: `view-dq-kpi-02`
- 当前有多少系统级阻塞正在挡路？
  - Type: bar_chart
  - Source view: `view-dq-kpi-03`
- 数据源联通和 transport 当前是否健康？
  - Type: bar_chart
  - Source view: `view-dq-kpi-04`

## Diagnosis Layer
- 当前主会场到底在推什么，哪些是真推进，哪些只是等待？
  - Type: breakdown_table
  - Source view: `view-dq-card-01`
- 任务整体推进态分布如何，堵点集中在哪？
  - Type: breakdown_table
  - Source view: `view-dq-card-02`
- 数据源同步、transport 和 source 覆盖现在健康吗？
  - Type: breakdown_table
  - Source view: `view-dq-card-03`
- 最近系统做了哪些 review、decision 和 writeback？
  - Type: breakdown_table
  - Source view: `view-dq-card-04`

## Action Layer
- 现在哪些事项必须由我介入？
  - Type: detail_table
  - Source view: `view-dq-action-01`
- 哪些系统阻塞需要单独处理，而不是继续假推进？
  - Type: detail_table
  - Source view: `view-dq-action-02`
- 如果现在开始推进，优先动作是什么？
  - Type: detail_table
  - Source view: `view-dq-action-03`
- 哪些能力价值高，但审批或授权摩擦大？
  - Type: detail_table
  - Source view: `view-dq-action-04`

## Source Views

- overview-当前真正处于前台推进的主线有几条 (总控对象主表)
  - Filters: time grain = day
  - Display fields: 运营分段
- overview-当前有多少事项只差我输入 (总控对象主表)
  - Filters: time grain = day; 需要人类输入 != 空
  - Display fields: 人类边界状态, 对象标题, 需要人类输入, 阻塞原因, 下一步动作, 证据入口
- overview-当前有多少系统级阻塞正在挡路 (总控对象主表)
  - Filters: time grain = day; 对象状态 = blocked_system
  - Display fields: 对象状态, 对象标题, 阻塞原因, 证据入口, 下一步动作
- overview-数据源联通和-transport-当前是否健康 (数据源同步表)
  - Filters: time grain = day; missing_sources_snapshot != none OR remote_reachable != true
  - Display fields: 来源家族, 标题, 状态, remote_reachable, missing_sources_snapshot, github_backend
- diagnosis-当前主会场到底在推什么-哪些是真推进-哪些只是等待 (总控对象主表)
  - Filters: time grain = day; 运营分段 = frontstage
  - Display fields: 对象状态, 负责人模式, 对象标题, 当前摘要, 下一步动作, 证据入口
- diagnosis-任务整体推进态分布如何-堵点集中在哪 (任务总表)
  - Filters: time grain = day; 下一步动作 != 空
  - Display fields: 状态, 对象标题, 对象状态, 负责人模式, 下一步动作, 证据入口
- diagnosis-数据源同步-transport-和-source-覆盖现在健康吗 (数据源同步表)
  - Filters: time grain = day; missing_sources_snapshot != none OR remote_reachable != true
  - Display fields: remote_reachable, 标题, 状态, missing_sources_snapshot, github_backend
- diagnosis-最近系统做了哪些-review-decision-和-writeback (治理动作与写回表)
  - Filters: time grain = day; event_time within last 14 days
  - Display fields: event_time, 标题, 状态, verification_state, evidence_refs
- action-现在哪些事项必须由我介入 (总控对象主表)
  - Filters: 需要人类输入 != 空
  - Display fields: 对象标题, 需要人类输入, 阻塞原因, 下一步动作, 证据入口
- action-哪些系统阻塞需要单独处理-而不是继续假推进 (总控对象主表)
  - Filters: 对象状态 = blocked_system
  - Display fields: 对象标题, 阻塞原因, 证据入口, 下一步动作
- action-如果现在开始推进-优先动作是什么 (总控对象主表)
  - Filters: 下一步动作 != 空
  - Display fields: 对象标题, 对象状态, 负责人模式, 下一步动作, 证据入口
- action-哪些能力价值高-但审批或授权摩擦大 (技能与能力表)
  - Filters: requires_human_approval = true
  - Display fields: requires_human_approval, 名称, routing_credit, verification_strength

## Manual Binding Notes

- Bind cards manually in the dashboard UI.
- Keep source views as the stable integration contract.
