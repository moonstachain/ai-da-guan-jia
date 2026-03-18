# AI大管家 Medallion 提案自治路线图 v1

这份路线图只回答一件事：

把大奖章 / IBM 方法论挂到 `G2 / I-AUTO-001 提案自治引擎` 以后，接下来分 4 期怎样稳步做成，而不误滑向“全自动执行”。

## 当前定位

- 当前 initiative：`I-AUTO-001 提案自治引擎`
- 当前主张：先做到 `高质量提案自治`，不是全自动执行
- 本轮新增母约束：
  - 提案 = 隐状态推断
  - 提案 = 证据组织
  - 提案 = 边界内自治
  - 提案 = 可反哺治理记忆

## 非目标

- 本路线图不要求第一期改 runtime 代码
- 不要求第一期建立新 initiative
- 不要求第一期把提案直接接到自动执行

## Phase 1：方法层定标

### 目标

把大奖章 / IBM 方法论压成 `proposal autonomy contract`，让 `I-AUTO-001` 有可执行的上位语义，而不是只停在“会提建议”。

### 关键产物

- `Medallion proposal autonomy blueprint`
- `proposal autonomy public contract`
- `TP-002` 升级后的 canonical thread proposal
- `initiative-brief.json` 切换到 `I-AUTO-001`

### 验收标准

- 文档里明确写出：
  - 5 个方法轴
  - 六判断映射
  - 6 层架构图
  - `吸收 / 改写 / 拒绝` 矩阵
- canonical 战略对象已经体现：
  - `TP-002` 不再是抽象提案
  - 新 active thread 已挂到 `G2 / I-AUTO-001`

### 依赖

- 现有 `G2`
- 现有 `I-AUTO-001`
- Feishu 主材料与 IBM / ACL / CMU 主来源

## Phase 2：提案回路 MVP

### 目标

形成第一条最小可验证提案回路：

`signal -> hidden-state hypothesis -> proposal -> evidence gate -> 待批`

### 关键产物

- proposal intake schema 的文档化版本
- `hidden_state_hypothesis` 模板
- `evidence_bundle` 模板
- 一次真实 task 的 propose-only 演示样本
- `waiting_human` / `blocked` / `verified` 的判定口径

### 验收标准

- 至少一条真实任务可以输出：
  - `thread proposal`
  - `initiative decomposition`
  - `blocked reason`
- 结果里能分清：
  - 哪些是可证事实
  - 哪些是策略推断
  - 哪些必须等待人类批准

### 依赖

- `I-AUTO-001`
- `route / review / evolution` 现有闭环
- `feishu-reader`、`guide-benchmark-learning`、`ai-da-guan-jia`

### 主要风险

- 误把生成 proposal 数量当成质量
- 误把“看起来合理”当成 evidence complete

## Phase 3：治理联动

### 目标

把 proposal 结果正式接入治理层，而不是把提案留在单次会话里。

### 关键产物

- proposal 结果到 `routing credit` 的映射规则
- proposal 结果到 `autonomy tier` 的映射规则
- proposal 结果到 `object / chain scorecard` 的映射规则
- 至少一条“提案质量影响治理结果”的真实规则

### 验收标准

- proposal 质量可以影响至少一项实际治理判断：
  - 路由优先级
  - 提权候选
  - 进化权候选
- `G2` 开始与 `G3` 发生真实联动，而不是平行文档

### 依赖

- `I-AUTO-001`
- `I-INC-001`
- 现有 `routing credit / autonomy tier / scorecard` 工件

### 主要风险

- 提案评分过于主观
- 激励联动过早，导致系统鼓励“会说的 proposal”而不是“真有证据的 proposal”

## Phase 4：组织扩张

### 目标

把提案自治从单条线程的建议器，升级成围绕组织目标稳定提出结构性建议的中层器官。

### 关键产物

- `thread proposal` 扩展到：
  - `initiative decomposition`
  - `skill recruitment suggestion`
  - `clone training recommendation`
- clone / 招募 / workflow hardening 的提案模板
- `G1 / G2 / G3` 的跨目标 proposal map

### 验收标准

- 至少出现 3 类不同提案：
  - 线程提案
  - 技能招募提案
  - clone / workflow 提案
- 新提案可以清楚回答：
  - 为什么是这个对象
  - 为什么现在提
  - 为什么复用而不是新建
  - 为什么还不能执行

### 依赖

- `I-AUTO-001`
- `I-CLONE-001`
- `I-GOV-001`
- `skill-trainer-recursive` 或未来正式中层器官

### 主要风险

- 组织扩张过快，导致 proposal 泛滥
- 没有强 evidence gate，提案系统变成“战略噪声生产器”

## 与 G1 / G2 / G3 的映射

| Phase | 主要挂载目标 | 次级联动目标 |
| --- | --- | --- |
| Phase 1 | `G2 / I-AUTO-001` | `G1` |
| Phase 2 | `G2 / I-AUTO-001` | `G1` |
| Phase 3 | `G2 / I-AUTO-001` | `G3 / I-INC-001` |
| Phase 4 | `G2 / I-AUTO-001` | `G1 / I-GOV-001`, `G2 / I-CLONE-001`, `G3 / I-INC-001` |

## 最近两轮可执行抓手

### Round A

- 完成蓝图与 canonical 战略对象升级
- 明确 `TP-002` 已获批准
- 固定 `proposal autonomy contract`

### Round B

- 选一个真实任务做 propose-only 演示
- 把 `hidden_state_hypothesis` 与 `evidence_bundle` 走通
- 验证是否真的能稳定产出 `待批提案` 而不是泛建议

## 完成定义

这条路线第一阶段真正算站稳，不是“写了漂亮文档”，而是下面 3 件事同时成立：

1. `I-AUTO-001` 已经有清楚的方法论母板。
2. proposal output 已经和 evidence gate 绑定。
3. 系统仍然维持 `建议 + 待批` 边界，没有偷渡成静默执行。
