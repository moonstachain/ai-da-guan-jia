# AI大管家 成熟进化版 8轮路线图 v1

`R1 / R2 / R3` 在本文中只表示当前 phase-1 实验代号，不是长期系统本体语言。长期边界见 [ai-da-guan-jia-top-level-blueprint-v1.md](/Users/liming/Documents/codex-ai-gua-jia-01/docs/ai-da-guan-jia-top-level-blueprint-v1.md)。

这份路线图回答的是一个很具体的问题：

从当前状态出发，如果按“像刚才那样的一轮强回合”持续推进，到 `成熟进化版` 大概还要多少轮，以及每一轮到底要完成什么。

## 当前判断

- `2026-03-14` 更新：
  - `R1` 已完成
  - `R2` 已转为 `human_manual_pending` 的人工妙搭子分支
  - 官方主线已切到 `R3 Sales Execute`

- 当前完成度：约 `30%`
- 已完成等价回合：约 `3 轮`
- 从现在到成熟进化版：
  - 乐观：`7 轮`
  - 基线：`8 轮`
  - 保守：`10 轮`
- 从项目最初起点到成熟进化版：
  - 基线总量约 `11 轮`

## 为什么不是更少

因为现在真正已经长稳的，主要还是：

- 治理认知层
- 本地运行底盘
- Feishu cockpit 的 blueprint 和 source-view 预演

而真正还没长全的，是 3 个最难的部分：

- live Feishu 底盘真正通电
- execute 三条主线做实
- clone / 激励 / 稳定递归系统长成

所以现在不能把“蓝图清楚”和“系统成熟”混为一谈。

## 六个治理判断

- `自治判断`
  大部分回合都可以由 AI大管家 自治推进，真正的人类边界仍然主要集中在 Feishu 权限、少数不可替代拍板和最终边界授权。
- `全局最优判断`
  先做 live 底盘和 execute，再做 clone 和激励，不能反过来。
- `能力复用判断`
  继续复用 `AI大管家 + strategy-governor + feishu-bitable-bridge + feishu-dashboard-automator`。
- `验真判断`
  每一轮都必须留下 live 证据或强本地证据，不能只停在概念或文档。
- `进化判断`
  `成熟进化版` 的标志不是功能越来越多，而是 `G1 / G2 / G3` 都至少有一个真实闭环。
- `当前最大失真`
  当前最容易高估的是治理层成熟度，最欠账的是 execute、clone、激励。

## 8 个标准回合

## 回合 1：打通 Live 底盘

- 目标：
  把当前 `协同治理` base 的 schema 管理边界交给 app，完成 live rollout。
- 关键交付：
  - `战略链路表`
  - `CBM组件责任表`
  - `CBM组件热图表`
  - 关键旧表新增 `component_domain / control_level / priority_band`
  - 16 个 source views 真正 apply
- 验收标准：
  - 不再出现 `91403`
  - live base 可创建表、字段、视图
  - config 中不再出现 `pending__...`
- 风险：
  - 如果当前 base 无法授权，就切换到 app-owned base 迁移

## 回合 2：做成可用的组件驾驶舱

- 目标：
  把现在的 source views 升成真正可用的 cockpit。
- 关键交付：
  - dashboard Phase 2 卡片绑定完成
  - cockpit 能稳定回答 4 个问题：
    - 哪些组件最重要
    - 哪些组件失衡
    - 哪些组件 owner / copilot 缺位
    - 哪些组件 gap 最大
- 验收标准：
  - 陌生协作者首次打开也知道先看哪里
  - 不再依赖 source-view checklist 才能读懂
- 对应目标：
  - `G1`

## 回合 3：Sales Execute 做实

- 目标：
  把当前唯一已经露头的 execute 主线做成第一条完整业务闭环。
- 关键交付：
  - `sales action catalog`
  - `execute writeback`
  - `sales KPI heatmap`
  - sales workflow v1
- 验收标准：
  - `goal -> component_domain -> control_level=execute -> action -> evidence -> KPI` 贯通
  - `module-sales` 不再只是解释层语义
- 对应目标：
  - `G1`

## 回合 4：Delivery Execute 做实

- 目标：
  把交付从治理语义变成运行对象。
- 关键交付：
  - delivery action catalog
  - delivery writeback
  - delivery KPI heatmap
  - 交付组件热图视图
- 验收标准：
  - cockpit 中能看到 delivery 优先级和 gap
  - 决策与交付动作之间有明确证据链
- 对应目标：
  - `G1`

## 回合 5：Finance Execute 做实

- 目标：
  让经营闭环进入 cockpit，不再只是任务感知。
- 关键交付：
  - finance action catalog
  - finance writeback
  - finance KPI heatmap
  - 至少一条经营主线进入治理总控
- 验收标准：
  - `sales / delivery / finance` 三件套成立
  - 至少一个经营判断能直接改变组件优先级
- 对应目标：
  - `G1`

## 回合 6：Clone 工厂做成第一版

- 目标：
  把 `AI管家克隆体训练工厂` 从概念做成机制。
- 对应 initiative：
  - `I-CLONE-001`
- 关键交付：
  - clone register
  - clone train round
  - clone review
  - clone scorecard / budget / promotion queue
- 验收标准：
  - clone 至少完成一整轮 `register -> train -> review`
  - clone 结果能进入治理总控
- 对应目标：
  - `G2`

## 回合 7：激励与自治等级接上

- 目标：
  把 `AI组织激励系统` 做成真实治理器官。
- 对应 initiative：
  - `I-INC-001`
- 关键交付：
  - routing credit
  - autonomy tier
  - incentive scorecard
  - 至少一条影响实际路由或写回权的规则
- 验收标准：
  - scorecard 不再只是展示，而是能影响一次真实治理决策
- 对应目标：
  - `G3`

## 回合 8：稳定化与递归节奏固化

- 目标：
  把前面长出来的器官固化成稳定的周/月递归系统。
- 重点补齐：
  - `workflow-hardening`
  - `skill-deduper`
  - `skill-inventory-review`
  - 日 / 周 / 月治理节奏
- 验收标准：
  - 不靠临时推动，也能稳定产出：
    - 治理视图
    - 组件热图
    - 提案推进
    - clone 评估
    - 激励更新
  - AI大管家 开始呈现“自己会长”的状态

## 成熟进化版的最终完成定义

真正算完成，不是“所有事情都完美了”，而是下面 3 件事同时成立：

- `G1` 已经有 live 闭环：
  - 治理底盘 + 组件驾驶舱 + execute 三条主线
- `G2` 已经有 live 闭环：
  - clone / 提案自治 / review
- `G3` 已经有 live 闭环：
  - 激励 / 自治等级 / 路由信用

再加上一条系统级标准：

- 日 / 周 / 月治理节奏已经稳定，不再靠临时推动维持

## 你现在只要记住的 5 句话

1. 我们现在不是没方向，而是已经进入“中后盘”。  
2. 从现在到成熟进化版，按强回合算，基线还要 `8 轮`。  
3. 最先要打穿的仍然是 live 底盘，不是继续加概念。  
4. 真正拉开差距的，是 execute、clone、激励这三块。  
5. 成熟版的标志不是更复杂，而是 `G1 / G2 / G3` 都开始自己运转。  
