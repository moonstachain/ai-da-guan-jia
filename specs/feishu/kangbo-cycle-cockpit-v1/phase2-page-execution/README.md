# 康波周期总控舱 Phase 2 页面执行包

这个目录是给“单独新建出来的页面执行窗口”准备的。

它只负责：

- 妙搭 / 飞书 dashboard 页面创建
- 卡片创建与绑定
- 页面视觉编排
- post-check 证据回传

它不负责：

- 再做数据建模
- 再改 source view
- 再解释 dashboard 信息架构
- 再修改 Feishu 表结构

## 入口文件

- `operator-handoff.md`
- `execution-contract.json`
- `evidence-checklist.md`

## 已准备好的前置物

- live base schema: [live-schema.json](/Users/liming/Documents/codex-ai-gua-jia-01/artifacts/kangbo-cycle-cockpit/live-schema.json)
- live source views: [source-views-apply.json](/Users/liming/Documents/codex-ai-gua-jia-01/artifacts/kangbo-cycle-cockpit/source-views-apply.json)
- card checklist: [dashboard-card-checklist.md](/Users/liming/Documents/codex-ai-gua-jia-01/artifacts/kangbo-cycle-cockpit/dashboard-card-checklist.md)
- 实施说明: [miaoda-implementation.md](/Users/liming/Documents/codex-ai-gua-jia-01/specs/feishu/kangbo-cycle-cockpit-v1/miaoda-implementation.md)

## 推荐新窗口开场语

把 [operator-handoff.md](/Users/liming/Documents/codex-ai-gua-jia-01/specs/feishu/kangbo-cycle-cockpit-v1/phase2-page-execution/operator-handoff.md) 整段贴进新窗口，然后直接执行。
