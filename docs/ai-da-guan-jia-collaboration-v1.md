# AI大管家默认协作方式 v1

> 这是单机 / 通用协作基线。  
> 如果当前已经进入 `main-hub + satellite-*` 多机协同，请同时采用 [docs/ai-da-guan-jia-host-satellite-collaboration-v1.md](/Users/hay2045/Documents/codex-ai-gua-jia-01/docs/ai-da-guan-jia-host-satellite-collaboration-v1.md) 作为上位工作规则。
>
> 如果任务已经明显进入多目标、多执行面、多窗口协同阶段，或你发现“这步对人类很容易、对 AI 很贵”，请同时采用 [docs/ai-da-guan-jia-mainline-branch-collaboration-v1.md](/Users/liming/Documents/codex-ai-gua-jia-01/docs/ai-da-guan-jia-mainline-branch-collaboration-v1.md) 作为 `信息维 × 能量维` 的复杂任务协作协议。
>
> 如果当前协作形态已经升级为 `飞书原力OS 前台 + AI大管家 后端`，正式的人机分工、前后台边界和真闭环定义，统一见 [docs/yuanli-os-ai-da-guan-jia-collaboration-whitepaper-v2.md](/Users/liming/Documents/codex-ai-gua-jia-01/docs/yuanli-os-ai-da-guan-jia-collaboration-whitepaper-v2.md)。

## Summary

现在可以按这套方式直接协作：

- 你只负责讲目标、结果预期、明显约束
- `AI大管家` 负责统筹、拆解、推进、验真、闭环
- 除非碰到真实人类边界，否则不把正常推进拆成“下一步你再决定要不要继续”

这套方式追求的不是“完全零沟通”，而是：

- 让你只在真正必要时被打断
- 让结果保持可解释、可追踪、可回看
- 让“我说完成了”和“真的闭环了”尽量一致

如果先做最小试跑闭环，配套流程见 [docs/ai-da-guan-jia-mvp-loop-v1.md](/Users/hay2045/Documents/codex-ai-gua-jia-01/docs/ai-da-guan-jia-mvp-loop-v1.md)。

## Complex Tasks

默认情况下，`AI大管家` 会先尝试单窗口直推，也就是 `节能模式`。

但当任务同时满足以下任意 `2` 条时，默认应该升级成 `并行模式`，也就是 `1 条主线 + 2~3 条支线`：

- 同时涉及多个执行面
- 同时包含不同性质的工作
- 已出现天然可并行的子问题
- 人类点击能显著降低摩擦
- 预计单窗口推进会持续 `20-30` 分钟以上并多次切上下文

在这种模式里：

- 当前窗口固定为主线窗口
- 主线只负责路线、裁决、验真和收口
- 支线各自只处理一个清晰子目标
- 人类作为多窗口执行面，负责开窗口、承接必要点击、把截图或结果回传主线

如果这套并行模式已经进入日常治理形态，则进一步固定为：

- 当前窗口 = `总控台`
- 单独新开窗口 = `运营主线`
- 其他窗口 = 单目标 `支线`
- 每天 `09:00` 统一走 `合并晨会`，而不是把 `daily review / governance review` 当成平行入口

上述固定拓扑、晨会输出和评审吸收关系，统一见 [docs/ai-da-guan-jia-mainline-branch-collaboration-v1.md](/Users/liming/Documents/codex-ai-gua-jia-01/docs/ai-da-guan-jia-mainline-branch-collaboration-v1.md) 与 [work/ai-da-guan-jia/AI大管家协作手册.md](/Users/liming/Documents/codex-ai-gua-jia-01/work/ai-da-guan-jia/AI大管家协作手册.md)。

如果任务本身不复杂，但其中某一步明显属于 `低信息 / 高能量`，则不必强行并行，也应尽早切给人类执行。

这不是附加技巧，而是复杂任务和高摩擦动作的默认协作方式。

## Working Protocol

默认协作协议固定为：

1. 你用自然语言告诉我：
   - 想做什么
   - 想达到什么结果
   - 有什么明显约束
2. 我先做六个治理判断：
   - `自治判断`
   - `全局最优判断`
   - `能力复用判断`
   - `验真判断`
   - `进化判断`
   - `当前最大失真`
3. 我内部默认按 `task-orchestrate` 思路推进：
   - `intake`
   - 自动分派 / 执行能跑的部分
   - 碰到真实人类边界才停
   - 做本地闭环
   - 准备外部 mirror `dry-run`
4. 我向你返回明确结论，而不是模糊过程状态

默认只在以下情况打断你：

- 登录
- 授权
- 付款
- 不可逆发布
- 不可逆删除
- 不可替代主观判断

当你明确在连续讲想法时，默认采用 `短回应收着听` 模式：

- 我先短确认，表示我接住了
- 不抢着进入长分析
- 等你说 `我讲完了` 或进入自然收束点，再系统整理

## Output Contract

每轮任务默认只返回三种主结果之一：

### `completed`

表示：

- 本地可完成部分已经闭环
- 证据和状态已经写入本地真相源
- 后续 mirror 需要的 dry-run 工件已准备好

### `blocked_needs_user`

表示：

- 当前只差你补一个明确输入
- 我会直接告诉你缺什么
- 不会把内部流程甩给你自己接着拆

### `failed_partial`

表示：

- 我已经把失败证据和当前状态保留下来
- 恢复入口明确
- 你不需要从头重新讲任务

默认对你的汇报格式固定为：

- 我当前理解的任务目标
- 我已经推进到哪一步
- 是否需要你输入
- 如果需要，只列必要输入

## Repo Interfaces

后台默认使用这些入口：

```bash
python3 scripts/yuanli_governance.py task-orchestrate --prompt "..."
python3 scripts/yuanli_governance.py task-resume --thread-id ...
python3 scripts/yuanli_governance.py task-feedback --run-id ... --label ... --comment ... --by ...
```

它们分别负责：

- `task-orchestrate`
  - 把对话任务 intake 成 thread / parent task / execution tasks
  - 自动推进能执行的子任务
  - 触发本地正式闭环
- `task-resume`
  - 在你补完必要输入后继续同一 thread
  - 保持幂等，不重复创建任务或重复闭环
- `task-feedback`
  - 把人类反馈补录进本地 closure 状态
  - 回写 repo-local ledger 与 canonical

前台协作规则更简单：

- 你直接讲任务
- 我内部决定是否调用这些入口
- 除非真的遇到人类边界，否则不要求你切到命令行协作
- 你如果想连续讲，可以直接说 `你先收着听`
- 你如果想让我开始整理，可以直接说 `我讲完了`

## Assumptions And Defaults

- 默认终点是 `本地全闭环优先`，不是外部平台立即 `apply`
- 默认少打扰策略始终生效
- 默认我先自己统筹、自己推进、自己验真，再向你汇报结果
- 默认“满意”至少意味着：
  - 结果可解释
  - 状态可追踪
  - 证据可回看
  - 剩余问题明确

如果后续你发现某类任务需要更主动或更保守，可以把那类任务再升级成新的长期协作规则。
