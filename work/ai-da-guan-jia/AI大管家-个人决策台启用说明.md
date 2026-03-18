# AI大管家-个人决策台启用说明

## 0. 一句话判断

截至 `2026-03-15`，`AI大管家` 已经可以作为你的 `个人决策台` 日用。

当前可用层级是：

- `提案`
- `分诊`
- `验真`
- `治理中控`

当前不可假装已经具备的层级是：

- 静默自动执行高影响动作
- 无需批准的外部发布
- 无需授权的系统跃迁

换句话说，它今天就能替你做大部分判断、整理、路由和闭环，但不会越过 `建议 + 待批` 的边界。

## 1. 你今天就可以怎么开始

最小启用方式只需要 3 个入口：

### 早上：给今天的 north star

```bash
bash scripts/personal_decision_cockpit.sh morning "今天最重要的是把 X 推进到 Y，帮我判断先做什么、哪些该延后、需要调用哪些 skill、哪些地方必须等我批准。"
```

### 白天：只看高影响待批

```bash
bash scripts/personal_decision_cockpit.sh status
```

你主要看：

- 当前 top proposal 是什么
- 哪些对象处于 `waiting_human`
- 哪些动作明确需要你的批准

### 晚上：做一次 recap 和治理刷新

```bash
bash scripts/personal_decision_cockpit.sh evening
```

如果你要补一句人类反馈：

```bash
bash scripts/personal_decision_cockpit.sh feedback <run-id> 通过 "方向对，继续压缩打扰和失真" liming
```

## 2. 每天 10 分钟的推荐节奏

### 早上 3 分钟

- 只说今天最重要的 `1-3` 个目标
- 不要先手工拆子任务
- 不要先替系统选工具

推荐提法：

```text
今天的 north star：
1. X
2. Y
3. Z

要求：
- 优先复用现有 skill、脚本和登录态
- 除登录、授权、付费、不可逆发布/删除外，尽量少打扰我
- 先给我 thread / skill / workflow proposal，再进入执行
```

### 白天 4 分钟

你只做三件事：

- 批准高影响动作
- 否决明显失真的 proposal
- 在必要时补 1 句主观判断

推荐反馈语：

- `通过，继续`
- `不通过，这里方向错了`
- `先别执行，等我确认`
- `这个对象不对，换一个更复用的路径`

### 晚上 3 分钟

- 看 1 次治理 recap
- 判断今天有没有明显误路由
- 给 1 句人类反馈

## 3. 你要做什么

你最重要的角色不是执行者，而是：

- `目标给定者`
- `边界裁决者`
- `最终验收人`

你每天需要做的事：

- 给当天 north star
- 批准高影响动作
- 提供不可替代的主观判断
- 给一句最短反馈
- 保持认证和权限链路可用

你不需要再做的事：

- 手工拆大部分子任务
- 手工决定 skill 组合
- 手工整理大部分过程证据
- 手工做治理记账和复盘

## 4. 你该怎么看输出

一轮个人决策台最重要的不是“做了很多”，而是输出这几个东西：

- `situation-map.md`
- `route.json`
- `strategic-proposal.md`
- `governance-dashboard.md`

你真正要看的判断点是：

- 目标有没有挂对
- proposal 有没有区分 `facts / inferences / approval_triggers`
- 哪些动作被拦在 `waiting_human`
- 是否真的减少了你自己做分诊和证据整理的负担

## 5. 第一周验收标准

启用第一周，先不要追求“自动做更多”，只看这几件事：

- 每天至少 1 条真实任务走完整 `route -> proposal -> recap`
- 至少 1 条高影响动作被正确拦在 `waiting_human`
- 你每天介入时间大致控制在 `10 分钟`
- 你明显感到“不必再亲自做任务分诊和证据整理”

进入稳用阶段的标准：

- 连续 `5-7` 天没有明显误路由
- proposal 的失真率下降
- daily review 对你是省力，而不是增负担

## 6. 当前边界

这套启用方式默认坚持：

- `建议 + 待批`
- 先本地 canonical，后外部镜像
- 先路由和验真，后执行

所以：

- 它可以帮你判断、排序、建议、验真、沉淀
- 它不应该替你默默完成高影响外部动作

## 7. 推荐命令

如果你只想记最少的命令，就记这 5 个：

```bash
bash scripts/personal_decision_cockpit.sh morning "..."
bash scripts/personal_decision_cockpit.sh status
bash scripts/personal_decision_cockpit.sh review
bash scripts/personal_decision_cockpit.sh evening
bash scripts/personal_decision_cockpit.sh feedback <run-id> <label> <comment> [by]
```

它们只是把现有公开接口压成更好用的人类入口，不新增治理边界，不新增隐藏能力。

## 8. 后面怎么升级

等个人决策台跑顺以后，下一条自然主线不是“马上全自动”，而是：

- 把 `workflow-hardening / skill-deduper / skill-inventory-review` 补厚
- 把高频任务压成更稳定的 workflow 样板
- 让 daily review 和 strategy current 更像操作台

再往后，才适合扩到：

- clone 训练工厂
- 更强自动执行链
- 更深的外部系统联动
