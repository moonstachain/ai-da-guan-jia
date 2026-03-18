# 新窗口执行 Prompt

你现在承接的是 `康波周期总控舱 Phase 2 页面执行面`，不是数据建模窗口，不是黑色线 support 窗口。

你的唯一目标是：

- 在妙搭 / 飞书 dashboard 页面上，把已经存在的 source view 绑定成可用页面
- 完成首页 `康波周期总控舱` + 4 个深入页
- 为每张已完成卡片保留可复验的证据

固定边界：

- 不改多维表 schema
- 不重做 source view
- 不扩展产品方案
- 不把首页做成长百科
- 不给 ticker、仓位、交易指令

## 你要先读的文件

1. [miaoda-implementation.md](/Users/liming/Documents/codex-ai-gua-jia-01/specs/feishu/kangbo-cycle-cockpit-v1/miaoda-implementation.md)
2. [dashboard-card-checklist.md](/Users/liming/Documents/codex-ai-gua-jia-01/artifacts/kangbo-cycle-cockpit/dashboard-card-checklist.md)
3. [execution-contract.json](/Users/liming/Documents/codex-ai-gua-jia-01/specs/feishu/kangbo-cycle-cockpit-v1/phase2-page-execution/execution-contract.json)
4. [evidence-checklist.md](/Users/liming/Documents/codex-ai-gua-jia-01/specs/feishu/kangbo-cycle-cockpit-v1/phase2-page-execution/evidence-checklist.md)

## 执行顺序

1. 新建一个独立页面工程，只承载 `康波周期总控舱`。
2. 先做首页 Hero、onboarding、KPI 和 5 张核心数据卡。
3. 再做 `300年事件库`。
4. 再做 `阶段解剖页`。
5. 再做 `当前局势页`。
6. 最后做 `企业家应对页`。
7. 每做完一个页面，立刻做 post-check，不要等全部完成再统一检查。

## 首页必须完成的内容

- Hero 头部
- 3 张 onboarding 导览卡
- 4 张 KPI 总览卡
- `当前关键事件卡`
- `历史镜像卡`
- `阶段主线卡`
- `资产篮子方向`
- `企业经营动作`
- 深入页入口卡

## 视觉硬约束

- 深色分析舱，不用纯黑
- 主色只用 `cyan-blue / amber / rose-red`
- 不做赛博噪音，不做伪 Bloomberg 终端
- 所有卡片都要能被第一次来的企业家用户读懂

## 真实数据提醒

`康波阶段表` 当前是原始导入列头形态，所以：

- `阶段主线卡` 首页默认绑定 `国家地区主线表`
- `康波阶段表` 只在 `阶段解剖页` 作为原始档案展示
- 不要把 `康波阶段表` 当成精细筛选源

## 你做完后必须回传

只用下面 5 段：

1. 本轮完成了什么
2. 哪些页面已可复验
3. 哪些卡片仍未完成
4. 每页各给 1 条证据
5. 唯一 blocker

如果都完成，回传固定信号：

`康波周期总控舱 Phase 2 已完成，可复验`
