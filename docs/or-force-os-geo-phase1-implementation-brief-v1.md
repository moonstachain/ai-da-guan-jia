# 原力 GEO Phase 1 实施简报

这份简报把这次 `原力GEO` 落地，收束成一套可直接继续推进的 repo 级实现包。

## 这次已经落好的东西

- 新增了一个独立的 GEO spec bundle：`specs/feishu/or-force-os-geo-v1/`
- 把 Phase 1 的目标收束到 `YSE` 单点试点
- 把回旋镖局材料明确定位为证据包和案例包，而不是独立 GEO 项目
- 把页面结构固定为 overview / diagnosis / action 三层

## 这次实现的对象

- Canonical object: 仓库内的 GEO 规格文件与实施说明
- Mirror surface: 未来的 Feishu Base / Miaoda dashboard
- Target location: `specs/feishu/or-force-os-geo-v1/`

## 已补的规范文件

- [dashboard-blueprint.md](/Users/liming/Documents/codex-ai-gua-jia-01/specs/feishu/or-force-os-geo-v1/dashboard-blueprint.md)
- [dashboard-blueprint.json](/Users/liming/Documents/codex-ai-gua-jia-01/specs/feishu/or-force-os-geo-v1/dashboard-blueprint.json)
- [source-views-spec.json](/Users/liming/Documents/codex-ai-gua-jia-01/specs/feishu/or-force-os-geo-v1/source-views-spec.json)
- [dashboard-card-checklist.md](/Users/liming/Documents/codex-ai-gua-jia-01/specs/feishu/or-force-os-geo-v1/dashboard-card-checklist.md)
- [miaoda-implementation.md](/Users/liming/Documents/codex-ai-gua-jia-01/specs/feishu/or-force-os-geo-v1/miaoda-implementation.md)

## Phase 1 约束

- 先做 `YSE`，不铺开另外 4 条产品线
- 先做人工或半自动闭环，不急着做 `geo-publish` 和 `geo-monitor`
- 先把 10 张卡和 6 张表的语义定稳，再谈 live 写入

## 验收口径

- 能从 source view 直接回答每张卡的管理问题
- 能把内容、发布、收录和回写追到同一条链路
- 能把回旋镖局案例沉淀成可复用的 YSE 证据资产
- 能为后续 `PROJ-GEO-02` 的 live 执行提供稳定输入
