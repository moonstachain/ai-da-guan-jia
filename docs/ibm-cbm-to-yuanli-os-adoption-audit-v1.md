# IBM CBM 到 AI大管家 / 原力OS 吸收审计 v1

## 一句话结论

IBM CBM 已经被 `AI大管家 / 原力OS` 明显吸收，但方式不是“原词照搬”，而是被改写成：

- `goal_id + theme -> strategy -> experiment -> workflow` 的双轴系统
- `Entity / Action / Policy / Capability / Writeback` 的运行对象层
- `main-hub + satellite-*` 的单主多前哨协同拓扑

当前更准确的判断是：

`已经吸收了 60%-75% 的结构价值，但还没把 CBM 的 component x control x KPI heatmap 变成完整运行时视图。`

## IBM CBM 原始骨架

从 [CBM PDF](/Users/liming/Downloads/CBM%20for%20%E6%88%98%E7%95%A5%E6%96%B0%E5%85%B4%E4%BA%A7%E4%B8%9A%E5%88%9B%E6%96%B0%E4%B8%AD%E5%BF%83.pdf) 可抽出 4 个核心骨架：

1. 横线是 `component domain`
   - 如园区战略、营销、基础设施、支持服务、增值服务、孵化、生态协同、职能管理
2. 纵线是 `Direct / Control / Execute`
   - 不是按部门分，而是按治理层级分
3. 每个组件都要有 `KPI / 热图 / 差距 / 投资优先级`
4. 最终要形成 `路线图`
   - 不只讲架构，而是导向项目排序、ROI 与落地路径

## 当前系统里的对应物

### 1. 横线已被改写成多层组件视图

- `goal_id` 对应治理优先级
- `theme -> strategy -> experiment -> workflow` 对应生产主轴
- `module-public / private / sales / delivery / finance / governance` 对应更接近 CBM 的组件域
- `Task / Thread / DecisionRecord / WritebackEvent` 对应运行对象

这意味着今天的“横线”不是单一一排业务组件，而是：

`治理目标轴 + 生产主轴 + operating modules + runtime entities`

### 2. 纵线已被改写成治理控制链

- `direct`
  - 更接近 `strategy-governor / canonical-thread-program / initiative registry`
- `control`
  - 更接近 `operational ontology / policy / permission / decision record / writeback`
- `execute`
  - 更接近 `module-sales / module-delivery / 客户复制 / 业务线程`

所以今天系统里并不是没有 `Direct / Control / Execute`，而是它们还主要作为解释层语义存在。

### 3. KPI 思想已经进入 operating modules

当前 `derived/reports/inventory-snapshot.json` 已有：

- `module-sales` -> `商机推进、报价、成交额`
- `module-delivery` -> `交付节奏、里程碑、满意度`
- `module-finance` -> `回款、利润、现金流`
- `module-governance` -> `闭环率、失真率、复制进度`

这说明 CBM 的 `组件 + KPI hint` 已经被显式引入。

### 4. 生态协同被改写成主机-卫星结构

IBM CBM 里有生态协同、合作伙伴和职能协调层。

在当前系统里，这部分更像：

- `main-hub` 负责 canonical source、正式闭环与策略层
- `satellite-*` 负责采集、执行、登录复用与局部推进

这不是传统组织图，但它承担了非常相似的组织协调角色。

## 当前最关键的 3 条映射样板

运行时样板已经落到：

- `治理运行骨架`
  - `direct`
- `operational ontology 收口`
  - `control`
- `销售成交 / 内部销售协同节奏`
  - `execute`

对应的机器可读工件：

- [specs/cbm-mapping-view.schema.json](/Users/liming/Documents/codex-ai-gua-jia-01/specs/cbm-mapping-view.schema.json)
- `strategy/current/cbm-mapping-view.json`
- `strategy/current/cbm-mapping-view.md`

## 还没有真正吸收完的部分

### 1. `control_level` 还不是一等运行时字段

当前 `direct / control / execute` 主要存在于解释层和附录视图里，还不是各对象统一携带的 schema 枚举。

### 2. 业务执行面落后于治理面

治理面已经有：

- `action catalog`
- `decision records`
- `writeback events`

但业务组件还没有同等级的：

- business action catalog
- component-level writeback
- heatmap-bound priority field

### 3. 热图 / 投资优先级还没正式对象化

今天已经有 `kpi_hint`、gap、next blocker，但还没有把：

- `component_domain x control_level x gap x priority`

固化成一等总图。

## 建议的下一步

1. 把 `control_level = direct | control | execute` 升成正式枚举字段
2. 给 `module-sales / module-delivery / module-finance / module-governance` 补 component-level action / writeback
3. 把 `kpi_hint + gap + next_action` 升成真正的 component heatmap
4. 保持边界不变
   - CBM 只做 `映射层 / 解释层 / 视图层`
   - 不替代 `AI大管家` 的 root 治理身份
