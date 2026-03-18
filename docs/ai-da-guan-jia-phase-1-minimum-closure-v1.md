# AI大管家 Phase-1 最小闭环实验定义 v1

这份文档只描述当前 `phase-1` 证明工程，不定义长期本体语言。

如果要理解 `AI大管家` 的长期系统边界，请先看：

- [ai-da-guan-jia-top-level-blueprint-v1.md](/Users/liming/Documents/codex-ai-gua-jia-01/docs/ai-da-guan-jia-top-level-blueprint-v1.md)

## Summary

当前阶段判断固定为：`phase-1.5`

含义是：

- 治理底盘已成立
- 多机协作底盘已初步成立
- 黑色卫星加速器官已成立
- 但最小业务闭环还未最终收掉

这份实验的目标，不是证明整个 AI大管家 已成熟落地，而是证明：

- 这套系统已经不是纸上蓝图
- 它可以穿过至少一条真实业务主线
- 它的 canonical / mirror / human boundary / satellite boundary 是可运行的

## 系统级最小闭环定义

`最小闭环完成` 固定定义为以下 3 条同时成立：

1. 至少 1 条真实业务主线贯穿：
   - `goal -> action -> evidence -> writeback -> derived view -> mirror`
2. 前台证据面被人工验真，而不是只存在 prompt pack 或结构描述
3. 状态口径恢复诚实，不混写：
   - `completed`
   - `in_progress`
   - `human_manual_pending`

## 当前 phase-1 实验实例

当前实验继续使用下面这些对象来证明系统级最小闭环：

- `lost`
- `cockpit`
- `KPI / heatmap / writeback / mirror`

这些对象是本轮实验实例，不是长期本体字段。

## 当前实验状态解释

为了描述本轮实验的推进状态，可以继续使用阶段别名：

- `R1 = completed`
- `R2 = human_manual_pending`
- `R3 = in_progress`

但固定说明为：

- `R1 / R2 / R3` 只是当前 phase-1 的实验代号
- 它们不是长期对象模型
- 后续实验可以替换，不进入顶层宪法语言

## 当前实验验收

### 最小闭环验收

- 你本人跨机器使用时，治理逻辑不散，镜像不替代 canonical
- 至少 1 条业务主线能贯穿：
  - `goal -> action -> evidence -> writeback -> KPI -> mirror`
- `R2` cockpit 能被截图验真，而不是只存在 prompt pack
- `R3` 不再只有 `won + quote + handoff`，还要补上真实 `lost`

### 口径验收

- Feishu、GitHub、local canonical 三处状态一致
- 不再出现“项目仍在推进，但 registry 已写成 validated”这种治理失真

## 近期主轴

当前 phase-1 的近期主轴固定为：

1. 用当前实验证明 `最小闭环`
2. 用黑色卫星迅猛清掉系统残留噪音和历史线
3. 在业务闭环成立后，再进入团队 / clone 结构化扩展

## 当前硬 blocker

当前 phase-1 最硬的 blocker 不是顶层蓝图，而是妙搭页面外显仍未收掉。

当前 repo-local 证据显示：

- `diagnosis-03` 仍是 `binding_unproven`
- `action-04` 仍是 `没绑`
- 多数卡片仍停在 `pending_surface_specific_binding`

证据见：

- [miaoda-r2-postcheck.json](/Users/liming/Documents/codex-ai-gua-jia-01/output/feishu-dashboard-automator/cbm-governance/miaoda-r2-postcheck.json)
- [operations-mainline-132e1d64aef95a7d.json](/Users/liming/Documents/codex-ai-gua-jia-01/work/ai-da-guan-jia/artifacts/ai-da-guan-jia/heartbeat/windows/current/operations-mainline-132e1d64aef95a7d.json)

## 黑色卫星在 phase-1 的角色

黑色卫星在本轮实验中固定作为 `部署层加速器官` 使用。

它负责：

- 系统清障
- 治理降噪
- support / verify
- repo-local evidence 补强

它不负责：

- phase-1 最终业务真相
- 主线替代
- 总控闭环
- 妙搭页面最终修复
- preview 纠偏
- source view 最终人工绑定

## 妙搭分工

当 phase-1 同时涉及 `dashboard runtime data model` 与 `妙搭页面外显` 时，固定分工如下：

- `黑色卫星`
  - 负责模型缺口澄清、support、verify、repo-local 对照
- `人类页面执行面`
  - 负责妙搭页面上的真实 republish / binding / preview 纠偏
- `运营主线`
  - 只在页面执行面回传后，做最终复验与诚实收口

具体协议见：

- [ai-da-guan-jia-miaoda-surface-data-model-split-v1.md](/Users/liming/Documents/codex-ai-gua-jia-01/docs/ai-da-guan-jia-miaoda-surface-data-model-split-v1.md)
