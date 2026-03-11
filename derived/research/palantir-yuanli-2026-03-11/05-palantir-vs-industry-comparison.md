# 05. Palantir 与业界相邻范式对比

## 对比矩阵

| 维度 | Palantir | 相邻研究/业界常见做法 | 判断 |
| --- | --- | --- | --- |
| 对象模型 | 把业务对象做成平台核心运行时 | 往往停在 schema、KG、twin model 或数据产品 | Palantir 更偏 operational object model |
| 语义层/本体层 | 语义层直接服务应用、动作、AI | 很多方案只服务查询、解释、集成 | Palantir 的语义层更靠近执行 |
| 动作与写回 | `Action` 与对象上下文绑定，重视 writeback | 常见平台只能分析或建议，不能稳定回写 | 这是 Palantir 最关键的差异点之一 |
| 权限与治理 | policy、security、audit 深度内嵌 | 常见方案在外围补 IAM 或审批流 | Palantir 更像“治理先行” |
| agent 可调用性 | AI 在 ontology + tool + policy 之上运行 | 多数 agent 框架先有 agent，再补企业约束 | Palantir 更适合高风险场景 |
| 部署/运营 | Apollo/architecture 是产品能力的一部分 | 很多方案把交付当项目，把运营当后勤 | Palantir 更像平台公司而不是咨询项目 |
| 交付方法 | bootcamp 强调短周期共创和实战 | 常见做法是长前期规划或小 demo 试点 | Palantir 更擅长 time-to-value |
| time-to-value | 强调快速把真实流程拉进闭环 | 常见 AI 项目卡在 PoC 到生产之间 | Palantir 的方法论非常重“落地速度” |

## 这说明了什么

### 1. Palantir 的独到之处不是“有 ontology”

很多研究和平台都有 ontology、graph、twin、semantic layer。Palantir 的独到之处在于把它们编织成受控的执行层。

### 2. Palantir 不是纯技术胜利

它同时赢在：

- 建模方式
- 权限治理
- 部署运营
- 行业交付法
- 销售与组织推进

### 3. 原力OS 不需要复制它的全部重量

原力OS 最该借的是结构，不是规模：

- 一致的对象世界
- 动作与回写闭环
- 明确的 agent 权限边界
- 快速验证价值的 bootcamp 方法

## 直接借 / 改造后借 / 不借

### 直接借

- 对象世界优先于聊天界面
- 动作和 writeback 是核心能力
- 决策记录是一等对象
- agent 必须受 policy 和 action 层约束

### 改造后借

- ontology 命名和对象划分
- bootcamp 交付节奏
- 应用层和操作视图设计
- twin 思维对治理系统的映射

### 不借

- 复制其重型平台外形
- 把所有对象都做成巨型统一模型再开工
- 用市场神话代替本地可验证闭环

## 讨论题

1. 你更认可“Palantir 是工程化整合者”还是“Palantir 有根本性方法创新者”？
2. 原力OS 当前最应该模仿的是它的对象层，还是 bootcamp 交付法？
3. 哪一条如果不借，原力OS 最容易走偏？
