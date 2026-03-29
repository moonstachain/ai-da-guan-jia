# 原力GEO Phase 1 试点总控舱

## Summary

- Goal: 把原力GEO系统先落成一个以 `YSE` 为单点试点的控制舱，让团队能看见蒸馏词、品牌知识库、内容生成、发布、收录和回写的完整闭环。
- Audience: 原力OS 共同治理者, YSE 试点执行者, Miaoda 页面执行面, Feishu 表结构维护者
- Time grain: day
- Trial scope: `YSE`

## Official Boundary

- OpenAPI-capable: bitable app metadata, tables, fields, records, views, dashboard list, dashboard copy
- Manual or template-driven: dashboard card creation, widget binding, canvas layout placement, content review queue handling
- Canonical truth: local repository plus future Feishu source views, not the dashboard surface

## Phase 1 Design

### 试点原则

- 只做 `YSE` 单点试点，不在 Phase 1 同时铺开另外 4 条产品线。
- 回旋镖局相关材料只作为证据包和案例包，先吸收进 `YSE` 品牌知识库，不单独起一个 GEO 项目。
- 先证明闭环跑通，再进入自动化与多产品线复制。

### Phase 1 成功标准

- 至少 1 个目标问法在至少 1 个 AI 平台上出现原力 / YSE 品牌信息。
- 10 篇试验文全部有审阅与发布记录。
- Feishu Base 无孤儿记录，蒸馏词、内容、发布和监测能彼此追溯。
- 周度复盘能明确说出哪些词在进、哪些平台在涨、哪些内容类型有效。

## Overview Layer

- 当前 YSE 试点健康吗？
  - Type: table
  - Source view: `view-overview-health`
- 当前最该盯的焦点蒸馏词是什么？
  - Type: table
  - Source view: `view-overview-focus`
- 当前阻塞与风险是什么？
  - Type: table
  - Source view: `view-overview-risk`
- 本周新增了哪些可验证进展？
  - Type: table
  - Source view: `view-overview-evolution`

## Diagnosis Layer

- YSE 蒸馏词库准备到什么程度？
  - Type: breakdown_table
  - Source view: `view-diagnosis-distill`
- 品牌知识库是否能支撑内容生成？
  - Type: breakdown_table
  - Source view: `view-diagnosis-knowledge`
- 发布与内容管线当前卡在哪里？
  - Type: breakdown_table
  - Source view: `view-diagnosis-pipeline`

## Action Layer

- 哪些事项需要人类审核？
  - Type: detail_table
  - Source view: `view-action-human-review`
- 哪些事项需要发布或补发？
  - Type: detail_table
  - Source view: `view-action-publish-queue`
- 哪些事项需要回写证据或调整蒸馏词？
  - Type: detail_table
  - Source view: `view-action-evidence-refresh`

## Seed Materials

- `原力GEO系统_全链路搭建路线图_V1.docx`
- `回旋镖局_战略诊断报告_V1 (1).docx`
- `供给侧瓶颈深度分析.docx`
- `回旋镖局_商业模式创新与进化路线图_V1 (1).docx`
- `全球标杆对标分析：七维度战略框架.docx`
- `这份报告的核心逻辑.docx`

## Source Views

- `view-overview-health` -> `T06_运营快照`
  - Filters: `Phase 1 only`, `recent window = last 14 days`
  - Display fields: `日期`, `总蒸馏词`, `已收录数`, `收录率`, `各平台分布`
- `view-overview-focus` -> `T01_蒸馏词库`
  - Filters: `所属产品线 = YSE`, `优先级 = P0 OR 当前收录状态 != 已收录`
  - Display fields: `ID`, `主关键词`, `拓展问题`, `优先级`, `当前收录状态`, `已收录平台`
- `view-overview-risk` -> `T05_收录监测`
  - Filters: `是否收录 = 否 OR 排名为空`
  - Display fields: `蒸馏词ID`, `AI平台`, `查询时间`, `是否收录`, `排名`, `竞品`
- `view-overview-evolution` -> `T06_运营快照`
  - Filters: `recent window = last 4 weeks`
  - Display fields: `日期`, `总蒸馏词`, `已收录数`, `收录率`, `各平台分布`
- `view-diagnosis-distill` -> `T01_蒸馏词库`
  - Filters: `所属产品线 = YSE`
  - Display fields: `ID`, `主关键词`, `拓展问题`, `所属产品线`, `优先级`, `当前收录状态`, `已收录平台`
- `view-diagnosis-knowledge` -> `T02_品牌知识库`
  - Filters: `产品线 = YSE`
  - Display fields: `产品线`, `品牌描述`, `差异化卖点`, `数据案例`, `关键词`
- `view-diagnosis-pipeline` -> `T03_内容库`
  - Filters: `Phase 1 only`
  - Display fields: `内容ID`, `标题`, `蒸馏词ID`, `内容类型`, `创建时间`, `正文`
- `view-action-human-review` -> `T04_发布记录`
  - Filters: `状态 = 待审核 OR 状态 = 需重写`
  - Display fields: `内容ID`, `发布平台`, `状态`, `发布时间`, `文章URL`
- `view-action-publish-queue` -> `T04_发布记录`
  - Filters: `状态 = 待发布`
  - Display fields: `内容ID`, `发布平台`, `状态`, `发布时间`, `文章URL`
- `view-action-evidence-refresh` -> `T05_收录监测`
  - Filters: `是否收录 = 否 OR 排名为空`
  - Display fields: `蒸馏词ID`, `AI平台`, `查询时间`, `是否收录`, `排名`, `竞品`

## Manual Binding Notes

- Bind cards manually in the dashboard UI.
- Keep source views as the stable integration contract.
- Do not treat the dashboard as canonical truth.
- The first build should stay on `YSE` until Phase 1 success criteria are met.
