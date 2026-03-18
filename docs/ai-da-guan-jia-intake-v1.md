# AI大管家入口 v1

> 这份文档描述的是早期 `task-intake / task-update` 阶段能力。
> 当前默认协作方式已经升级到 `task-orchestrate / task-resume / task-feedback`。
> 新的默认协作规则见 [docs/ai-da-guan-jia-collaboration-v1.md](/Users/hay2045/Documents/codex-ai-gua-jia-01/docs/ai-da-guan-jia-collaboration-v1.md)。
> 如果当前已经采用 `原力OS 飞书前台 + AI大管家 后端` 的形态，正式的人机协同白皮书见 [docs/yuanli-os-ai-da-guan-jia-collaboration-whitepaper-v2.md](/Users/liming/Documents/codex-ai-gua-jia-01/docs/yuanli-os-ai-da-guan-jia-collaboration-whitepaper-v2.md)。

## 当前状态

这版入口已经满足以下协作目标：

- 先和共同治理者把任务聊清楚
- 再由 `AI大管家` 路由与拆解
- 在 `codex-ai-gua-jia-01` 内创建 `1 个母任务 + 多个子执行单`
- 默认少打扰，只在真正的人类边界出现时才升级

这版的完成标准是：

- 能稳定 intake
- 能落地本地任务来源层
- 能生成可验证的分派包
- 能把任务状态继续回写到 canonical

这版的完成标准不是：

- 自动把子执行单继续交给下游 skill/agent 去执行
- 自动补齐 `AI大管家` 的 evolution / Feishu / GitHub / human-feedback 闭环

## 现在能做什么

### 1. 对话转任务

用 `task-intake` 把一段协作需求转成：

- `thread`
- `parent task`
- `execution tasks`
- `route.json`
- `situation-map.md`
- `osa-card.json`
- `intake-summary.md`
- `delegation-plan.json`

命令：

```bash
python3 scripts/yuanli_governance.py task-intake --prompt "先聊清楚，再拆成几件事，在 repo 里建任务，原则上少打扰我"
```

预览模式：

```bash
python3 scripts/yuanli_governance.py task-intake --prompt "先聊清楚，再拆成几件事，在 repo 里建任务，原则上少打扰我" --dry-run
```

### 2. 本地来源层防覆盖

repo-local intake 的真相源固定写到：

- `output/ai-da-guan-jia/intake/tasks.local.json`
- `output/ai-da-guan-jia/intake/threads.local.json`
- `output/ai-da-guan-jia/intake/<run_id>/`

`inventory` 会合并：

- 外部 `active-threads.json`
- 本地 `tasks.local.json`
- 本地 `threads.local.json`

因此本地 intake 任务不会被外部 `active-threads.json` 覆盖。

### 3. 子执行单状态推进

用 `task-update` 推进单个 execution task：

```bash
python3 scripts/yuanli_governance.py task-update --task-id task-<run_id>-01 --status in_progress --next-action "开始执行并补充证据。"
```

回写效果：

- 更新 repo-local task ledger
- 重新生成 canonical `tasks/threads`
- 让后续 `inventory` / `review` / `morning-review` 看到最新状态

## 当前边界

这版的“安排人”停在 `任务分派层`。

也就是：

- `AI大管家` 负责判断、拆解、分派、标边界
- execution task 内会写推荐 `skill chain`
- 但不会自动触发下游 skill/agent 执行

默认少打扰边界固定为：

- 登录
- 授权
- 付款
- 不可逆发布
- 不可逆删除
- 不可替代主观判断

只有这些情况才应升级为 `needs_user`。

## 后续两阶段

如果要把入口从“任务分派”升级到“自动执行 + 正式闭环”，还差两段：

### 阶段 2：自动下游执行层

目标：

- 把 `delegation-plan.json` 从推荐 skill 链升级成可执行 runner
- 区分哪些 skill 只产出 handoff，哪些 skill 可以直接执行
- 把 execution result 回写到 task ledger

完成标志：

- 子执行单可被程序化触发
- 成功 / 失败 / 阻塞会结构化回写
- 不需要手工复制 skill 名再二次分派

### 阶段 3：AI大管家正式闭环层

目标：

- 每轮任务自动补本地 evolution record
- 为完成态任务准备 `Feishu / GitHub` dry-run mirror 工件
- 预留并记录 `record-human-feedback` 槽位

完成标志：

- “代码实现完成”和“AI大管家治理闭环完成”不再分离
- 每轮任务都能补全 gain / waste / next iterate
- mirror 仍保持本地 canonical 优先

## 验证现状

当前仓库里，这版能力已经由 pipeline 测试覆盖：

- `task-intake --dry-run` 只预览，不写 repo-local 真相源
- 正常 `task-intake` 会写 packet、ledger、canonical
- 同一 `run_id` 重跑具备幂等性
- `depends_on_task_ids` 会保留
- `task-update` 会回写 ledger 与 canonical

本轮能力的最低验证命令：

```bash
python3 -m unittest tests.test_pipeline
```

## 结论

如果当前目标是：

- 先聊清楚
- 再拆任务
- 在 `codex-ai-gua-jia-01` 里建任务
- 原则上少打扰

那么这版已经实现。

如果目标升级为：

- 自动把子任务继续交给下游 skill/agent 执行
- 并自动完成 `AI大管家` 正式闭环

那么还需要继续做阶段 2 和阶段 3。
