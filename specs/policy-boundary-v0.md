# 原力OS Policy Boundary v0

## 目的

给 `skill governance` 首个试点场景定义最小权限边界，确保 agent 可以提案和执行低风险动作，但不能越权改写治理真相。

## Actor Types

### `human_owner`

- 你本人或被明确授权的人
- 允许 `read / propose / execute / approve`

### `ai_agent`

- 治理 Agent 或经批准接入的下游 Agent
- 默认只允许 `read / propose`
- 只有显式 capability 绑定后，才可 `execute`

### `automation`

- 定时任务或脚本执行器
- 默认只允许 `read / execute`
- 不允许自主 `approve`

## Policy Set

### `policy-read-governance`

- 允许读取 canonical entities、derived reports、review data
- 不允许直接改写 source of truth

### `policy-propose-skill-review`

- 允许 agent 或 automation 生成 skill review 候选
- 输出必须带 `evidence_refs`
- 不允许在此阶段直接变更 skill 状态

### `policy-resolve-review-action`

- 允许把候选动作转换成正式决策或推进任务
- 必须产出 `DecisionRecord`
- agent 只能生成 resolution draft
- 最终 resolution 默认需要 `human_owner` 批准

### `policy-publish-derived-report`

- 允许把经过决策确认的内容写入 derived report
- 任何影响 canonical 状态的 publish 都必须同时记录 `WritebackEvent`

## Capability Binding

### `capability-skill-review-proposal`

- actor: `ai_agent`
- allowed actions:
  - `review-skill`
- approval:
  - 不需要人工审批即可生成候选 review

### `capability-review-resolution-draft`

- actor: `ai_agent`
- allowed actions:
  - `resolve-action`
- approval:
  - 只能输出草稿，不能最终批准

### `capability-report-publication`

- actor: `automation`
- allowed actions:
  - `publish-governance-report`
- approval:
  - 若引用的 `DecisionRecord` 已批准，可执行
  - 若没有批准的 `DecisionRecord`，必须阻断

## Hard Gates

- 没有 `EvidenceAtom` 或等价 `evidence_ref` 的动作不能升级为正式决策
- 没有 `DecisionRecord` 的状态变更不能写入 canonical truth
- agent 默认无 `approve`
- 高风险动作默认需人工确认：
  - 修改战略线程状态
  - 改写任务优先级
  - 发布影响外部镜像的正式结论

## v0 Non-Goals

- 不覆盖客户实例、财务经营、销售成交等高复杂模块
- 不引入复杂 RBAC 系统
- 不处理跨组织信任和联邦权限
