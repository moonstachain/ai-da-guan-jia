# 原力GEO Phase 1 妙搭实施说明

## 1. 当前状态

- 这次实现的是 `原力GEO Phase 1` 的规格包，不是最终 live Feishu 绑定。
- 目前仓库里已经有 GEO 的蓝图、source view 规范、卡片清单和实施说明。
- 真实的 Feishu Base、source view、dashboard 卡绑定还需要后续按该规格落地。

## 2. 页面结构

首页固定为 `原力GEO 试点总控舱`，承担：

- Hero 控制态头部
- 试点导览层
- 4 张 overview 卡
- 3 张 diagnosis 卡
- 3 张 action 卡
- 试点收口与后续扩展入口

## 3. 页面执行边界

- 先做 `YSE` 单点试点，不在 Phase 1 同时铺开另外 4 条产品线。
- 回旋镖局相关材料只作为案例和证据输入，不独立起 GEO 项目。
- `T01-T06` 是唯一的数据底座，妙搭只读，不存真相。
- 所有卡片都必须能回到单一 source view，不做混合卡。

## 4. 推荐实施顺序

1. 先创建 `T01-T06` 并把 `YSE` 试点数据落表。
2. 再补 `T01_蒸馏词库` 和 `T02_品牌知识库` 的首批数据。
3. 再生成 `T03-T05` 的内容、发布和监测记录。
4. 再搭建 `T06_运营快照` 做总览和周度复盘。
5. 最后手动绑定 10 张 dashboard 卡，先验真，再谈自动化。

## 5. 关键验收

- 至少 1 个目标问法在至少 1 个 AI 平台上出现原力 / YSE 品牌信息。
- 10 篇试验文全部有审阅与发布记录。
- 每条蒸馏词都能追到内容、发布和监测记录。
- 周度复盘能明确说出哪些词在进、哪些平台在涨、哪些内容类型有效。

## 6. 需要人工守住的点

- 人类审核首批内容质量。
- 人类确认首轮发布平台与节奏。
- 人类确认是否把回旋镖局证据包继续沉淀成 YSE 资产。

## 7. 交付物位置

- [dashboard-blueprint.md](/Users/liming/Documents/codex-ai-gua-jia-01/specs/feishu/or-force-os-geo-v1/dashboard-blueprint.md)
- [dashboard-blueprint.json](/Users/liming/Documents/codex-ai-gua-jia-01/specs/feishu/or-force-os-geo-v1/dashboard-blueprint.json)
- [source-views-spec.json](/Users/liming/Documents/codex-ai-gua-jia-01/specs/feishu/or-force-os-geo-v1/source-views-spec.json)
- [dashboard-card-checklist.md](/Users/liming/Documents/codex-ai-gua-jia-01/specs/feishu/or-force-os-geo-v1/dashboard-card-checklist.md)

## 8. 后续扩展

- Phase 2 才把同一套 schema 复制到另外 4 条产品线。
- Phase 3 才在人工循环稳定后做 geo-publish、geo-monitor 和 skill pack 封装。
