# 07. 原力OS 90 天借鉴落地路线

## 目标

90 天内不追求做出 “Palantir for Yuanli”，而是做出一个最小但成闭环的 `governance operational layer`。

## Phase 1: 定义期（Day 1-15）

目标：把概念层定死，避免后面边做边改名。

- 固化双 ontology 架构
- 确定 12 个最小公共类型
- 列出第一批 `Entity`、`Action`、`Policy`
- 为 `EvidenceAtom` 和 `DecisionRecord` 写最小契约

验收：

- 有一份 `operational ontology v0 spec`
- 有一份 `action catalog v0`
- 有一份 `policy boundary note`

## Phase 2: 单场景闭环（Day 16-35）

目标：只选一个高价值场景，把对象、动作、回写做通。

推荐首场景：

- `技能治理`
  - 因为已有 canonical source、CLI、report、review 资产

实施：

- 把 `Skill`、`ReviewRun`、`DecisionRecord` 对象化
- 把 `review-skill`、`resolve-action`、`publish-governance-report` 建成 action
- 把结果回写到 canonical 和 derived reports

验收：

- 一个 agent 或自动流程可以在 policy 下完成“读 -> 判 -> 建议 -> 回写”

## Phase 3: 第二场景扩张（Day 36-60）

目标：验证这不是单点拼装，而是可复用操作层。

推荐第二场景：

- `线程推进治理`

实施：

- 把 `Thread`、`Task`、`Asset` 纳入同一 operational layer
- 建立 `promote-thread`、`split-task`、`archive-thread` action
- 把晨会材料与决策记录连接起来

验收：

- 两个场景共享同一套对象、动作、权限骨架

## Phase 4: Agent Capability Layer（Day 61-75）

目标：把 agent 从“会说”推进到“受控能干”。

实施：

- 定义 `AgentCapability`
- 明确哪些 action 可由 agent 直接执行，哪些必须审批
- 给每次执行补 `WritebackEvent` 和 `DecisionRecord`

验收：

- 至少 1 个 agent capability 被正式接入 operational ontology

## Phase 5: Bootcamp 化与复盘（Day 76-90）

目标：把这套试点方法沉淀成你自己的 bootcamp。

实施：

- 总结第一轮对象建模模板
- 总结 action catalog 模板
- 总结 review / decision / writeback 模板
- 沉淀成一套“原力OS bootcamp”文档

验收：

- 新场景可以用 bootcamp 模板在 1-2 周内拉起试点

## 关键设计原则

- 先场景，后扩展
- 先动作闭环，后大而全模型
- 先 policy 和 audit，后 agent 自治
- 先 evidence grounding，后自由推理

## 失败信号

- ontology 名词越来越多，但 action 仍然稀少
- agent 做了很多建议，但不能稳定回写
- 决策仍然只存在于聊天和 Markdown，不能查询
- 每个场景都在自造对象和字段

## 成功信号

- 至少两个场景共用同一套核心对象与动作骨架
- `DecisionRecord` 和 `WritebackEvent` 成为真实一等对象
- agent capability 不再依赖 prompt 口头约束
- 原力OS 的讨论从“我们有什么概念”升级成“我们能可靠改变什么”

## 讨论题

1. 90 天里你最想优先打通哪个场景？
2. 你是否接受“先做 1-2 个硬闭环，不追求全局覆盖”？
3. 谁会是原力OS 的第一个 bootcamp 参与角色：你自己、AI 大管家，还是具体垂直 skill？
