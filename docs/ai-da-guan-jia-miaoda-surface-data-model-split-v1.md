# AI大管家 妙搭外显与数据模型分工协议 v1

这份协议只解决一个问题：

- 当 `dashboard runtime data model` 与 `妙搭页面外显 / preview / source view / binding` 同时出现时，谁负责哪一层。

它不替代顶层蓝图，不替代运营主线协议，也不替代黑色卫星 PMO Beta 协议。

## Summary

当前状态不是“全都没解决”，而是分成两层：

- `模型/治理层`
  - 顶层共识已基本解决
  - dashboard runtime data model 仍有未落稳部分
- `妙搭页面外显层`
  - 仍未解决
  - 当前 blocker 仍是页面侧 preview / source view / binding 纠偏

因此责任划分固定为：

- `黑色线`
  - 负责模型缺口澄清、support、verify、证据整理
- `人类页面执行面`
  - 负责妙搭页面上的真实 republish / binding / preview 纠偏
- `运营主线`
  - 只在页面执行面回传后，做最终复验与诚实收口

## 当前验真结论

当前 repo-local 证据仍显示妙搭页面外显未解决：

- [miaoda-r2-postcheck.json](/Users/liming/Documents/codex-ai-gua-jia-01/output/feishu-dashboard-automator/cbm-governance/miaoda-r2-postcheck.json)
  - `verification_state = failed_partial`
  - `diagnosis-03` 当前仍是 `binding_unproven`
  - `action-04` 当前仍是 `没绑`
  - 多数卡片仍是 `pending_surface_specific_binding`
- [operations-mainline-132e1d64aef95a7d.json](/Users/liming/Documents/codex-ai-gua-jia-01/work/ai-da-guan-jia/artifacts/ai-da-guan-jia/heartbeat/windows/current/operations-mainline-132e1d64aef95a7d.json)
  - 当前仍是 `waiting_external`
  - 唯一 blocker 仍是页面侧未把正确版本发到当前 preview

## 固定分工

### 黑色线负责

- 把 dashboard runtime data model 哪些已清楚、哪些未清楚写成最小 gap 包
- 对 `expected source view / expected card binding / expected evidence chain` 做 repo-local 对照
- 页面执行面完成动作后，做 support / verify
- 继续产出 repo-local 证据，不碰页面最终纠偏

### 黑色线不负责

- 妙搭页面最终修复
- preview 纠偏
- source view 最终人工绑定
- 页面执行面 republish

### 人类页面执行面负责

- 进入妙搭页面
- 检查当前 preview
- 真正 republish 正确版本
- 确认 `diagnosis-03 / action-04` 的页面对象是否已对齐

### 运营主线负责

- 保持冻结
- 等待页面执行面回传：
  - `已重发当前 app，可复验`
- 收到信号后立即复跑：
  - `bind-cards`
  - `post-check`
- 只检查：
  - `diagnosis-03`
  - `action-04`

## 页面执行窗口规则

推荐答案固定为：

- `需要页面执行窗口`
- `但只为页面执行面单开，不为数据模型分析单开`

具体规则：

- 如果当前已经有可用的页面执行窗口，就继续用那个
- 如果没有，就新开一个专门的“妙搭页面执行面”窗口
- 这个窗口只做页面动作，不做人肉数据模型分析

## 黑色线 Prompt

```text
你现在承接的是 `dashboard runtime data model gap + repo-local verify` 子目标，不是妙搭页面执行面。

固定边界：
- 不承担妙搭页面最终修复
- 不承担 preview 纠偏
- 不承担 source view 最终人工绑定
- 不接管页面执行面职责

你当前只做：
1. 把 dashboard runtime data model 哪些已清楚、哪些未清楚压成最小 gap 包
2. 对 `expected source view / expected card binding / expected evidence chain` 做 repo-local 对照
3. 为页面执行面动作完成后的复验，准备 support / verify 证据

输出仍只用：
1. 本轮结论
2. 涉及对象
3. 最小改动方案
4. 验收方式
5. 唯一 blocker
```

## 页面执行面 Prompt

```text
你现在是 `妙搭页面执行面`，不是黑色线，不是运营主线，不做人肉数据模型分析。

请只做页面侧最终纠偏：
1. 去哪里
- `https://miaoda.feishu.cn/app/app_4jpv228nf1phd`

2. 点什么 / 改什么
- 检查当前 preview
- 把正确版本真正 republish 到当前 preview
- 确认 `diagnosis-03` 与 `action-04` 对应的是目标页面对象，而不是语义相近卡或旧 preview

3. 为什么这一步该由你做
- 当前 blocker 在页面执行面，不在黑色线，不在运营主线
- 这是典型 `低信息 / 高能量` 或 `高信息 / 高能量里的执行面`

4. 做完回传什么
- `已重发当前 app，可复验`
```

## 成功判断

以下 3 条成立，说明分工正确：

1. 黑色线能给出一份最小 `dashboard runtime data model gap` 说明，但不碰页面最终纠偏
2. 人类页面执行面能把正确版本真正发到当前 preview
3. 运营主线在信号到达后完成最终复验

## 失败判断

任一条成立都说明分工错了：

1. 黑色线开始像页面执行面一样承担妙搭最终修复
2. 人类被拉去做人肉数据模型分析
3. 运营主线在没有页面信号时重新开始空转
4. 把“蓝图共识”继续当成“页面外显完成”
