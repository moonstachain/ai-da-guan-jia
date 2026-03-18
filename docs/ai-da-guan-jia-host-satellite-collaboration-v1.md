# AI大管家主机-卫星协同工作框架 v1

## Current MVP Freeze

当前执行中的黑白 old MVP 冻结为：

- `black -> main-hub`
- `old -> satellite-03`
- `white -> pending satellite`

本轮 canonical expected sources 只认：

- `main-hub`
- `satellite-03`

浏览器/登录型真任务链优先顺序固定为：

- `Feishu`
- `Get笔记`
- `其他浏览器任务`

补充说明见 [black-white-old-host-satellite-mvp-v1.md](/Users/liming/Documents/codex-ai-gua-jia-01/docs/black-white-old-host-satellite-mvp-v1.md)。

## Summary

这套框架把多机协同固定成：

- `main-hub` 负责真相源、正式主线、治理闭环、策略层和总控
- `satellite-*` 负责采集、浏览器执行、登录复用、局部推进
- 重要任务默认从主机开始
- 任务真正收口一律回主机

默认原则不是“每台机器都一样重”，而是：

- `主机优先`
- `卫星机 = 采集 + 执行`
- `任务闭环回主机`
- `卫星 thread = 临时前哨，不是长期 canonical 主线`

## Role Model

### `main-hub`

- 默认主机，唯一 canonical source
- 承担：
  - 正式 intake
  - 主线 thread
  - 任务拆解
  - `route`
  - `strategy-governor`
  - `close-task`
  - GitHub / Feishu 治理闭环

### `satellite-*`

- 默认卫星机，不升级成隐式双主
- 承担：
  - 临时采集
  - 浏览器 / 登录态执行
  - 局部验证
  - 素材抓取
  - 移动场景下的短任务推进
- 可以做事，但不承担最终 canonical 闭环

## Thread Semantics

### 主机上的 thread

- 视为正式 thread
- 可以长期保留、持续演化、进入主线治理

### 卫星机上的 thread

- 视为 `临时前哨 thread`
- 默认只承载：
  - 现场采集
  - 局部执行
  - 临时判断
  - 登录 / 浏览器型步骤
- 不默认当长期主线
- 价值升级后，再回收到 `main-hub` 成正式 thread

## Working Pattern

### 重要任务

1. 默认从 `main-hub` 开始
2. 如中途需要浏览器、登录态、现场机器或移动处理，再把一个子段交给 `satellite-*`
3. `satellite-*` 完成后，把结果回送给 `main-hub`
4. 只有 `main-hub` 做正式 closure、evolution、sync

### 交互式远端任务默认可见

- 所有交互式远端任务，默认优先给人类提供 `前台可见执行面`
- 尤其是远端 `Codex / VSCode` 型任务，默认要求输入输出能在远端屏幕摊平可见
- 浏览器型远端任务默认优先用可见窗口，而不是黑箱后台执行
- 如果某次必须从前台可见降级到后台执行，系统必须显式写出 `why_not_visible`
- 降级后台后，仍必须补 `截图 / 快照 / 窗口状态` 这类可见证据，不能只给一句“已经跑过了”

### 可见性与稳定性的默认权衡

- 默认价值排序固定为：
  - `稳定优先`
  - `可见协作第二`
- 也就是说，可见性是默认要求，但不是压倒稳定性的硬约束
- 当前台可见明显降低成功率、可恢复性或登录态复用稳定性时，允许自动切到后台
- 一旦自动降级，系统要同时做到：
  - 说明为什么降级
  - 留下可见证据
  - 给出可恢复的继续路径

### 临时任务

- 可直接在卫星机上开始
- 默认只做成：
  - `素材`
  - `证据`
  - `局部结果`
  - `待主机收口的 execution fragment`
- 不在卫星机上做长期策略发散和正式闭环

## Human Protocol

你不需要记复杂命令，只需要在对话里带上机器语境：

- `我现在在主机，开正式主线`
- `我现在在 satellite-01，上来先采集`
- `我现在在卫星机，只做执行，不做闭环`
- `把这条从卫星机回收到主机`
- `今天帮我做一次主机汇总`

默认解释规则：

- 你说“在主机”
  - 我按正式主线模式工作
- 你说“在卫星机”
  - 我按前哨模式工作
- 你没说
  - 我默认你要走 `main-hub` 正式模式

## AI大管家默认动作

### 在 `main-hub`

- 默认按完整六判断 + `route` + `task-orchestrate` + closure 走
- 把这里当成正式治理面

### 在 `satellite-*`

- 默认少发散、少重规划
- 优先做：
  - 登录 / 授权
  - 浏览器任务
  - 采集
  - 局部执行
  - 简短验证
- 需要正式收口时，默认建议回主机

## Daily Rhythm

### 日常深度工作

- 在 `main-hub`

### 移动场景 / 临时机器 / 外出处理

- 在 `satellite-*`

### 每天正式收口

- 默认回 `main-hub`

### 跨机器切换

- 不要求每切一次机都强制大同步
- 默认在“任务闭环”时回主机统一写回

## Multi-Machine Governance

新增卫星机默认流程固定为：

1. `probe`
2. `inventory`
3. `verify`
4. `onboard`
5. `auth sync pass`

命名固定：

- 主机：`main-hub`
- 卫星：`satellite-01`、`satellite-02`、`satellite-03` ...

默认不再接受：

- 隐式双主
- 未命名“临时第二主机”
- 每台机器各自发展长期真相源

## Auth And Login Strategy

默认优先统一三层：

- `GitHub CLI / git protocol`
- `Feishu` 浏览器 profile
- `Get笔记` 浏览器 profile

策略固定为：

- 能复制复用的本地 profile，优先复用
- 真正需要网页登录时，再打断你
- 站点登录不是全时要求，只在触发对应 skill 时补

## What To Remember

以后只坚持这 4 条：

1. 重要任务默认在主机开
2. 在卫星机上，只把自己当成“前哨站”
3. 真正收口一律回主机
4. 不把 sidebar 是否完全一样，当成协同成功标准

## Acceptance

这套框架算跑通，至少满足：

- 你能在 `main-hub` 上继续做正式主线工作
- 你能在任一 `satellite-*` 上完成采集、登录、浏览器执行、临时推进
- 卫星机产生的高价值结果，能被明确“回收”进主机
- `main-hub` 继续是唯一 canonical source
- 新增卫星机时，不需要重新发明流程，只复用 `probe -> inventory -> verify -> onboard`
- 你在日常协作里不需要自己判断“这台机器算主机还是卫星”，只要告诉我“我现在在哪类机器”

## Assumptions And Defaults

- 当前默认架构长期保持：
  - `main-hub + 多 satellite`
- 默认 `主机优先`，不是 `就近哪台都一样`
- 默认卫星机承担 `采集 + 执行`，不承担正式闭环
- 默认 `任务闭环回主机`
- 默认卫星 thread 是 `临时前哨`
- 默认 sidebar 呈现差异属于显示层问题，不作为协同是否成功的主判据
- 默认后续如果继续加机器，直接沿这套框架扩，不再重新设计一套新协议
