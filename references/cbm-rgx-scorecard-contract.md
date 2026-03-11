# CBM-RGX Method

## Purpose

- 服务未来 90 天优先级，而不是做静态框架展示。
- 在不另起炉灶的前提下，把现有 `CBM v2`、`component-register`、`skill-review-rubric`、`agent-scorecard` 统一到一张分。

## RGX 定义

- `R = Result`：结果兑现度
- `G = Governance`：治理强度
- `X = eXvolution`：递归进化能力

## 评分对象

1. `业务层`
- 3 个原力主题 x 3 条业务链路
- 共 9 个业务格子

2. `治理层`
- 端到端任务智能闭环
- Skill / AI 人才治理体系
- 治理节律与证据体系

3. `基础设施层`
- 对当前原力主战场中的关键共享组件逐个评分

## 分值与证据

- 评分区间：`0-5`
- 证据等级：`A/B/C`
- `A`：真实业务数据或外部系统已验证记录
- `B`：有 run / artifact / 工作台证据，但经营数据不完整
- `C`：只有结构定义或局部原型

## 权重

- 业务格子：`R 50% / G 25% / X 25%`
- 治理体系：`R 20% / G 50% / X 30%`
- 基础设施：`R 20% / G 40% / X 40%`

## R 口径

- 是否有清晰战略结果
- 是否有真实动作与产出
- 是否有经营数据或业务代理指标

## G 口径

- 边界是否清楚
- 上下游接口是否稳定
- 验真和闭环是否存在
- 人类中断条件是否明确

## X 口径

- 是否主动引入 benchmark / 外部信息源
- 卡点是否回收到 rule / playbook / asset
- 是否有复盘写回
- 是否减少重复劳动和系统熵

## Existing Inputs Reused

- `component-register.json` 提供对象边界、maturity、inputs/outputs、entropy 结构
- `skill-review-rubric.md` 提供治理类定性判断口径
- `agent-scorecard.json` 提供技能治理侧真实评分底盘
- `governance-dashboard.md` 提供当前治理主目标和运行状态

## Scoring Discipline

- 缺经营数据时，只降证据等级，不伪造经营判断
- 保留 `L0-L3 maturity`，但只作为结构成熟度，不替代 RGX 评分
- 所有高分都必须带 evidence refs
- 先做样板价值流，再扩全矩阵
