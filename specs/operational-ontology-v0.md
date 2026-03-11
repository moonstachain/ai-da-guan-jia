# 原力OS Operational Ontology v0

## 目的

把现有原力治理项目从“知识治理和状态展示”推进到“受控动作闭环的治理操作层”。

本规范只定义 `operational ontology`，不替代现有 `epistemic ontology`。

## 边界

### `epistemic ontology`

负责：

- 母题
- topic mapping
- source layering
- knowledge object model
- 认识论边界

回答的是“这是什么知识、属于哪一层、哪些解释不能混”。

### `operational ontology`

负责：

- 治理对象
- 对象状态
- 可执行动作
- 权限与策略
- agent 可调用能力
- 写回与审计

回答的是“当前有什么对象、谁能做什么、做完如何回写和追责”。

## 最小公共类型

### 1. `EvidenceAtom`

最小证据单元。必须能追溯到文件、记录、事件或生成工件。

最小字段：

- `id`
- `title`
- `source_ref`
- `source_kind`
- `captured_at`
- `confidence`
- `supports_entity_ids`
- `supports_decision_ids`

### 2. `Entity`

运行层对象的统一抽象。v0 不单独落库，而是映射现有实体表。

v0 覆盖对象：

- `Task`
- `Thread`
- `Asset`
- `ReviewRun`
- `Skill`

最小字段：

- `id`
- `entity_type`
- `title`
- `status`
- `owner_mode`
- `source_ref`
- `updated_at`

### 3. `Relation`

对象之间的显式关系。

复用现有 [canonical/schema/relations.schema.json](/Users/hay2045/Documents/codex-ai-gua-jia-01/canonical/schema/relations.schema.json) 的基本结构，不另起协议。

### 4. `State`

对象在运行期所处的阶段。v0 沿用各实体现有 `status` 字段，不单独建表。

要求：

- 状态必须可枚举
- 状态必须可被 action 改变
- 状态变化必须可回写

### 5. `Action`

受控执行单元。不是任意脚本，不是 prompt 中的临时动词。

v0 首批动作：

- `review-skill`
- `resolve-action`
- `publish-governance-report`

最小字段：

- `action_id`
- `title`
- `target_entity_type`
- `allowed_actor_types`
- `required_policy_ids`
- `input_contract`
- `output_contract`
- `writeback_targets`

### 6. `Policy`

动作执行约束。定义风险边界、审批要求和写回范围。

v0 首批策略：

- `policy-read-governance`
- `policy-propose-skill-review`
- `policy-resolve-review-action`
- `policy-publish-derived-report`

### 7. `Permission`

actor 对 policy 或 action 的允许级别。

v0 级别：

- `read`
- `propose`
- `execute`
- `approve`

### 8. `DecisionRecord`

把关键判断从 Markdown 注释升级为对象。

适用场景：

- 为什么发起某个 skill review
- 为什么采纳或拒绝某个 action candidate
- 为什么发布某个治理结果

最小字段：

- `decision_id`
- `title`
- `decision_type`
- `target_entity_ids`
- `decision_summary`
- `rationale`
- `evidence_refs`
- `decided_by`
- `decision_time`
- `writeback_event_ids`

### 9. `TaskThread`

对现有 `Task + Thread` 的运行层联合视角，不新增落库表。

目的：

- 让任务推进和线程推进共享 action 设计语言
- 避免任务、线程、review 三套逻辑各说各话

### 10. `AgentCapability`

agent 被允许调用的治理能力，不等于 agent 自己的自由意图。

v0 首批 capability：

- `capability-skill-review-proposal`
- `capability-review-resolution-draft`
- `capability-report-publication`

最小字段：

- `capability_id`
- `title`
- `actor_type`
- `allowed_action_ids`
- `bound_policy_ids`
- `requires_human_approval`

### 11. `WritebackEvent`

每次动作执行后的回写记录。

最小字段：

- `writeback_id`
- `action_id`
- `target_refs`
- `changed_fields`
- `evidence_refs`
- `triggered_by`
- `writeback_time`
- `verification_state`

## 三条桥接接口

### `EvidenceAtom -> Entity / DecisionRecord`

原始证据支撑对象状态和决策结论。

v0 约束：

- 没有 `source_ref` 的材料不能成为正式 `EvidenceAtom`
- 没有 `EvidenceAtom` 的 `DecisionRecord` 只能是草稿

### `Action / WritebackEvent -> EvidenceAtom`

执行结果必须反向沉淀为证据。

v0 约束：

- 所有执行类 action 都必须产出新的 `EvidenceAtom` 或引用已有证据

### `AgentCapability -> Policy / Permission`

agent 能做什么由 capability 和 policy 决定，不由 prompt 口头约束。

v0 约束：

- agent 默认无 `approve`
- 高风险动作默认 `requires_human_approval = true`

## 与现有 canonical 的映射

### 直接复用

- `Task` -> [canonical/schema/tasks.schema.json](/Users/hay2045/Documents/codex-ai-gua-jia-01/canonical/schema/tasks.schema.json)
- `Thread` -> [canonical/schema/threads.schema.json](/Users/hay2045/Documents/codex-ai-gua-jia-01/canonical/schema/threads.schema.json)
- `Asset` -> [canonical/schema/assets.schema.json](/Users/hay2045/Documents/codex-ai-gua-jia-01/canonical/schema/assets.schema.json)
- `Skill` -> [canonical/schema/skills.schema.json](/Users/hay2045/Documents/codex-ai-gua-jia-01/canonical/schema/skills.schema.json)
- `ReviewRun` -> [canonical/schema/review_runs.schema.json](/Users/hay2045/Documents/codex-ai-gua-jia-01/canonical/schema/review_runs.schema.json)
- `Relation` -> [canonical/schema/relations.schema.json](/Users/hay2045/Documents/codex-ai-gua-jia-01/canonical/schema/relations.schema.json)

### 新增对象契约

v0 只新增规范，不直接新增 runtime 代码：

- `DecisionRecord`
- `Action`
- `AgentCapability`
- `WritebackEvent`

## 首个试点场景

固定为 `技能治理`。

对象：

- `Skill`
- `ReviewRun`
- `DecisionRecord`

动作：

- `review-skill`
- `resolve-action`
- `publish-governance-report`

写回目标：

- canonical entities
- derived governance report

## 非目标

- 不做多 agent 编排
- 不做客户复制实例
- 不做 UI 扩展
- 不把 `epistemic ontology` 和 `operational ontology` 合并
