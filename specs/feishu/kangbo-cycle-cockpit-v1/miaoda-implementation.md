# 妙搭《康波周期总控舱》实施说明 v1

## 1. 当前已完成

- 已基于 live base `IqZhbMJJxaq8D4sHOvkciaWFnid` 生成专用 blueprint bundle。
- 已真实同步 13 个 source view 到飞书多维表。
- 已导出一份可直接给页面执行面使用的 card checklist。

本轮 live 数据底座确认如下：

- `时间事件主表`: 79 条
- `康波阶段表`: 10 条
- `国家地区主线表`: 10 条
- `主题图层表`: 10 条
- `L1_康波事件信号`: 1 条
- `L1_历史镜像`: 3 条
- `L2_资产信号映射`: 7 条

## 2. 页面结构

首页固定为 `康波周期总控舱`，承担：

- Hero 控制态头部
- 3 张 onboarding 导览卡
- 4 张 KPI 总览卡
- 诊断层
- 行动层
- 深入页入口

四个深入页固定为：

- `300年事件库`
- `阶段解剖页`
- `当前局势页`
- `企业家应对页`

## 3. 已创建的 Source Views

- `view-hero-current-signal` -> `L1_康波事件信号` / `vewQrDdoDc`
- `view-kpi-event-distribution` -> `时间事件主表` / `vewn40Pzoj`
- `view-kpi-phase-distribution` -> `时间事件主表` / `vewV46xFkP`
- `view-kpi-asset-basket` -> `L2_资产信号映射` / `vewzXaB8hG`
- `view-diagnosis-current-event` -> `L1_康波事件信号` / `vewPb9YtRj`
- `view-diagnosis-historical-mirror` -> `L1_历史镜像` / `vew0GLEXLp`
- `view-diagnosis-phase-context` -> `国家地区主线表` / `vewINHEegC`
- `view-action-asset-basket` -> `L2_资产信号映射` / `vewG5jG2uk`
- `view-action-entrepreneur-translation` -> `L2_资产信号映射` / `vewsShCpCC`
- `view-library-events-timeline` -> `时间事件主表` / `vew8sdVy5w`
- `view-library-phase-profile` -> `康波阶段表` / `vewAyBGUVy`
- `view-library-theme-layer` -> `主题图层表` / `vewj1ldvka`
- `view-library-region-mainline` -> `国家地区主线表` / `vewgXWNtaN`

## 4. 手工绑卡边界

OpenAPI 已完成的是 `table / field / view` 层，不包含妙搭或飞书 dashboard 的精细卡片创建。因此页面执行面仍需手工完成：

- Hero 主视觉
- 3 张 onboarding 文本卡
- 深入页入口卡
- 历史镜像抽屉
- 资产方向解释抽屉
- 首屏视觉编排与响应式微调

建议页面执行顺序：

1. 先做首页 Hero、onboarding 和 KPI。
2. 再绑首页 5 张核心数据卡。
3. 再做 4 个深入页。
4. 最后补抽屉、hover 和视觉打磨。

## 5. 当前已确认的数据缺口

`康波阶段表` 当前不是标准字段头结构，而是导入时把第一行数据写成了字段名。结果是：

- `view-library-phase-profile` 已创建成功
- 但它更适合作为“原始证据表”展示
- 不适合作为高精度筛选和分阶段切换的数据源

因此当前建议：

- 首页 `阶段主线卡` 默认从 `国家地区主线表` 切入
- `主题图层表` 承担阶段解剖页的解释层
- `康波阶段表` 保留为原始档案，后续如要做精细切换，先结构化重建

## 6. 页面语气与视觉约束

- 文案顺序固定为：一句结论、一句为什么、一句这对你意味着什么
- 视觉走 `ink/slate` 深色分析舱，不走赛博大屏
- 强调色固定为 `cyan-blue / amber / rose-red`
- 资产卡只给篮子方向、理由、风险提示，不给 ticker 和仓位
- 企业家应对页必须翻译成现金流、杠杆、供应链、扩张节奏语言

## 7. 交付物位置

- `dashboard-input.json`
- `dashboard-blueprint.json`
- `dashboard-blueprint.md`
- `source-views-spec.json`
- `dashboard-card-checklist.md`
- `dashboard-config.yaml`
- `artifacts/kangbo-cycle-cockpit/live-schema.json`
- `artifacts/kangbo-cycle-cockpit/source-views-apply.json`
- `artifacts/kangbo-cycle-cockpit/dashboard-card-checklist.md`
