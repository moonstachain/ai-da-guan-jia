# 原力OS Operational Ontology v0 实施拆解

## 目标

把 Palantir 研究包正式转译成下一轮可工程实现的最小增量，不再停留在概念讨论。

## 当前可直接复用

### 现有对象与 schema

- `Task`: 已有 `title / goal_id / status / owner_mode / selected_skills / evidence_ref / next_action`
- `Thread`: 已有 `title / goal_id / status / source_run_id / open_questions`
- `Asset`: 已有 `title / asset_type / source_path / source_kind / status`
- `Skill`: 已有 `name / cluster / role / routing_credit`
- `ReviewRun`: 已有 `summary / top_risks / candidate_actions / human_decision`
- `Relation`: 已有通用 from/to/relation_type 结构

### 现有运行层基础

- 已有 canonical entities 和 schema
- 已有 derived governance report
- 已有 `AI大管家` 战略目标和 active thread 机制

## 需要新增的对象契约

### `DecisionRecord`

建议新增文件：

- `canonical/schema/decision_records.schema.json`
- `canonical/entities/decision_records.json`

最小用途：

- 记录 skill review 结果为何被采纳或拒绝

### `Action`

建议新增文件：

- `canonical/schema/actions.schema.json`
- `canonical/entities/actions.json`

最小用途：

- 固化 `review-skill / resolve-action / publish-governance-report`

### `AgentCapability`

建议新增文件：

- `canonical/schema/agent_capabilities.schema.json`
- `canonical/entities/agent_capabilities.json`

最小用途：

- 把 agent 权限从 prompt 约束转成结构化能力绑定

### `WritebackEvent`

建议新增文件：

- `canonical/schema/writeback_events.schema.json`
- `canonical/entities/writeback_events.json`

最小用途：

- 记录每次 report 发布或状态更新的回写痕迹

## 下一轮代码改造顺序

### Phase 1: Schema and canonical entities

- 新增 4 份 schema
- 新增 4 份空实体文件
- 把 `action-catalog-v0.json` 中的动作初始化进 `actions.json`

### Phase 2: Inventory and report pipeline

- 在 inventory/build pipeline 中把 `DecisionRecord / Action / AgentCapability / WritebackEvent` 纳入 snapshot
- 在 derived report 中展示：
  - 当前可执行动作
  - 当前待审批决策
  - 最近写回记录

### Phase 3: Skill governance runtime

- 让 `review-skill` 产出 `ReviewRun`
- 让 `resolve-action` 产出 `DecisionRecord`
- 让 `publish-governance-report` 产出 `WritebackEvent`

## 首个试点的数据流

1. 读取 `Skill` 与既有 `ReviewRun`
2. 生成或更新 `review-skill`
3. 形成候选动作
4. 通过 `resolve-action` 生成 `DecisionRecord`
5. 通过 `publish-governance-report` 写回 derived report
6. 同步记录 `WritebackEvent`

## 验收条件

- 新对象只做增量，不破坏现有 `tasks / threads / assets / review_runs`
- skill governance 场景可以明确回答：
  - 当前有哪些动作可执行
  - 谁可以执行
  - 哪些动作仍需审批
  - 最近一次写回改了什么

## 当前不做

- 不直接改 `AI大管家` 脚本逻辑
- 不做 Feishu 镜像扩写
- 不做多 agent orchestration
