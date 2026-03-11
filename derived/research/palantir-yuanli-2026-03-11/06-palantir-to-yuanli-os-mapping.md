# 06. Palantir 到原力OS 的映射方案

## 核心判断

Palantir 的 `Ontology` 和原力现有 ontology 有关系，但不是同一种东西。

- 原力现有 ontology 更像 `epistemic ontology`
- Palantir 的 ontology 更像 `operational ontology`

这两个层次不应混成一个大词。

## 双 ontology 架构

## A. `原力 epistemic ontology`

职责：

- 母题分类
- topic mapping
- knowledge object model
- source layering
- boundary rules
- anti-collapse epistemic discipline

这层主要回答：

- 这是什么类型的知识对象
- 这条材料属于哪一层认识论
- 它与哪些母题相关
- 哪些解释不该被强行合并

对应你现有资料中的稳定锚点：

- `Knowledge Object Model`
- `Topic Mapping`
- `Epistemic Layers`

## B. `原力 operational ontology`

职责：

- 把真实治理世界建成对象层
- 统一任务、线程、资产、决策、动作、权限和 writeback
- 作为 agent 可调用的受控运行时

这层主要回答：

- 当前有哪些治理对象
- 它们是什么状态
- 可以执行什么动作
- 谁能执行
- 执行后写回到哪里
- 如何审计和复盘

## 最小公共类型集合

- `EvidenceAtom`
- `Entity`
- `Relation`
- `State`
- `Action`
- `Function`
- `Policy`
- `Permission`
- `DecisionRecord`
- `TaskThread`
- `AgentCapability`
- `WritebackEvent`

## 三条桥接接口

### 1. `EvidenceAtom -> Entity / DecisionRecord`

把原始证据原子转成治理对象和决策对象的支撑材料。

### 2. `Action / WritebackEvent -> EvidenceAtom`

任何执行结果都应回写成新证据，而不是只改变状态不留来源。

### 3. `AgentCapability -> Policy / Permission`

agent 能做什么，不由 prompt 临时决定，而由 capability 和 policy 决定。

## 三个原力OS 场景样例

## 场景 1: 技能治理

- `Entity`：Skill
- `Action`：review-skill, validate-skill, route-task
- `DecisionRecord`：保留为什么升级/合并/淘汰某个 skill
- `WritebackEvent`：回写到 canonical snapshot 和 governance report
- `AgentCapability`：允许指定 agent 只做 inventory 与 review，不直接改写技能本体

## 场景 2: 线程推进

- `Entity`：Thread, Task, Asset
- `Action`：promote-thread, split-task, archive-thread
- `DecisionRecord`：为什么一个线程被升为重点，或被降级
- `WritebackEvent`：更新 canonical relations 和 derived reports
- `AgentCapability`：仅允许 agent 在审批边界内推进，不允许无痕删除

## 场景 3: 晨会与复盘治理

- `Entity`：ReviewRun, DecisionRecord, FollowUpTask
- `Action`：generate-review, resolve-action, mirror-feishu
- `DecisionRecord`：记录某个 review action 被采纳或放弃的理由
- `WritebackEvent`：回写到晨会材料、Feishu payload 和任务状态
- `AgentCapability`：允许 agent 生成候选动作，但最终高风险动作仍需人确认

## 外部研究对双 ontology 的支持

### 支持 `epistemic ontology`

- W3C ORG 的结构化表达思想
- KG/LLM 研究对 grounding 与可解释性的强调

### 支持 `operational ontology`

- Palantir ontology 文档
- digital twin / cognitive twin 对“对象 + 状态 + 回路”的强调
- decision intelligence 对“决策资产化”的强调
- enterprise agents 对“tool + policy + workflow”的强调

### 支持桥接层

- KG/LLM 研究说明 `EvidenceAtom` 的 grounding 价值
- cognitive twin 和 decision intelligence 说明执行结果应回到知识/决策层

## 直接借 / 改造后借 / 不借

### 直接借

- 对象世界优先
- 动作与 writeback 一体化
- agent capability 显式建模
- 决策记录对象化

### 改造后借

- Palantir 的 ontology 命名方式
- bootcamp 式落地方法
- 应用视图与角色视图

### 不借

- 把 epistemic ontology 直接等同于 business object model
- 先做超大模型，再补 policy 和 audit
- 在没有 action catalog 的情况下谈 agent 自治

## 讨论题

1. 双 ontology 架构你是否接受？
2. 这 12 个最小公共类型里，你觉得哪个最值得先做？
3. 原力OS 第一批 action 应该围绕技能治理、线程治理，还是晨会治理？
4. 哪个场景最适合作为你的 `AIP bootcamp` 式试点？
