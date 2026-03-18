# 把 300 年康波关键事件、当前冲击研判、历史镜像和大类资产篮子方向压缩成一个适合企业家学员与创业者的总控舱，并通过深入页承接结构化细节。仪表盘

## Summary
- Goal: 把 300 年康波关键事件、当前冲击研判、历史镜像和大类资产篮子方向压缩成一个适合企业家学员与创业者的总控舱，并通过深入页承接结构化细节。
- Audience: 企业家学员, 创业者, 投研型内容策划者, 妙搭页面执行面
- Time grain: custom

## Official Boundary
- OpenAPI-capable: bitable app metadata, tables, fields, records, views, dashboard list, dashboard copy
- Manual or template-driven: dashboard card creation, widget binding, canvas layout placement

## Overview Layer
- 当前重点落在哪个康波阶段，风险温度处于什么水平？
  - Type: table
  - Source view: `view-dq-overview-01`
- 79 条历史事件里，哪几类冲击最常见？
  - Type: bar_chart
  - Source view: `view-dq-overview-02`
- 历史事件主要分布在哪些康波阶段？
  - Type: bar_chart
  - Source view: `view-dq-overview-03`
- 当前资产篮子方向整体偏向什么姿态？
  - Type: table
  - Source view: `view-dq-overview-04`

## Diagnosis Layer
- 当前关键事件到底发生了什么，为什么重要？
  - Type: table
  - Source view: `view-dq-diagnosis-01`
- 哪三个历史镜像最像当下，它们像在哪里又差在哪里？
  - Type: table
  - Source view: `view-dq-diagnosis-02`
- 当前事件应挂回哪条阶段主线，背后的技术、制度和国家重心是什么？
  - Type: table
  - Source view: `view-dq-diagnosis-03`
- 从国家地区和影响方向看，历史事件库的重心在哪里？
  - Type: table
  - Source view: `view-dq-diagnosis-04`

## Action Layer
- 资产篮子应该怎么按大类展示成结论、理由和风险提示？
  - Type: table
  - Source view: `view-dq-action-01`
- 如果把资产语言翻译成企业语言，企业家下一步该做什么？
  - Type: table
  - Source view: `view-dq-action-02`
- 接下来最该盯住哪些风险观察点和验证指标？
  - Type: table
  - Source view: `view-dq-action-03`
- 当用户想继续深挖时，应该从哪个深入页进入？
  - Type: table
  - Source view: `view-dq-action-04`

## Source Views

- overview-当前重点落在哪个康波阶段-风险温度处于什么水平 (L1_康波事件信号)
  - Filters: 最新事件，仅展示 event_name/event_summary/scenario_shift/source_article
  - Display fields: kangbo_phase, event_category, event_name, event_date, severity, event_summary, scenario_shift, source_article
- overview-79-条历史事件里-哪几类冲击最常见 (时间事件主表)
  - Display fields: 事件类别
- overview-历史事件主要分布在哪些康波阶段 (时间事件主表)
  - Display fields: 康波阶段
- overview-当前资产篮子方向整体偏向什么姿态 (L2_资产信号映射)
  - Filters: 按 asset_class 分组展示方向与风险提示
  - Display fields: direction, asset_class, asset_name, position_action, stop_rule, confidence
- diagnosis-当前关键事件到底发生了什么-为什么重要 (L1_康波事件信号)
  - Filters: 最新事件，仅展示 event_name/event_summary/scenario_shift/source_article
  - Display fields: kangbo_phase, event_category, event_name, event_date, severity, event_summary, scenario_shift, source_article
- diagnosis-哪三个历史镜像最像当下-它们像在哪里又差在哪里 (L1_历史镜像)
  - Filters: 按 similarity_score 降序，保留 top 3
  - Display fields: kangbo_event_name, analogy_type, kangbo_event_id, similarity_score, analogy_reasoning, key_difference, historical_asset_impact
- diagnosis-当前事件应挂回哪条阶段主线-背后的技术-制度和国家重心是什么 (康波阶段表)
  - Filters: 默认挂到当前事件所属 phase
  - Display fields: 阶段编码, 康波阶段, 阶段名称, 阶段定义, 技术主线, 制度背景, 典型事件
- diagnosis-从国家地区和影响方向看-历史事件库的重心在哪里 (时间事件主表)
  - Display fields: 国家|地区, 影响方向, 可信度
- action-资产篮子应该怎么按大类展示成结论-理由和风险提示 (L2_资产信号映射)
  - Filters: 按 asset_class 分组展示方向与风险提示
  - Display fields: asset_class, direction, confidence, asset_name, position_action, stop_rule
- action-如果把资产语言翻译成企业语言-企业家下一步该做什么 (L2_资产信号映射)
  - Filters: 将资产语言映射为现金流、防御配置、扩张节奏、供应链动作
  - Display fields: asset_class, direction, asset_name, position_action, stop_rule
- action-接下来最该盯住哪些风险观察点和验证指标 (L1_康波事件信号)
  - Filters: 结合 scenario_shift 和 impact_direction 提炼监控项
  - Display fields: event_category, asset_class, event_name, impact_direction, causal_chain, scenario_shift
- action-当用户想继续深挖时-应该从哪个深入页进入 (时间事件主表)
  - Filters: 人工固定成四个二级页面入口
  - Display fields: 事件名称, 事件类别, 康波阶段, 国家|地区

## Manual Binding Notes

- Bind cards manually in the dashboard UI.
- Keep source views as the stable integration contract.
