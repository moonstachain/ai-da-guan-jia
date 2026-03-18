# AI大管家-内部同事版第一闭环MVP启用说明

## 0. 一句话判断

截至 `2026-03-15`，内部同事版第一闭环 MVP 已经可以按 `1 位中台管理同事 + 5 个工作日 + 飞书前台 + AI大管家后端` 的方式启动。

如果你现在不只想跑第一周，而是要把这位同事一路带到 `半自治操盘 -> 方法进化 -> 组织复制`，继续看：

- [AI大管家-同事协作成长路径说明.md](./AI大管家-同事协作成长路径说明.md)
- `bash scripts/internal_collaboration_playbook.sh overview`

这一版只验证一件事：

- `是否明显减少你亲自盯人、追问、催办的次数`

这一版明确不验证：

- 多岗位同时上线
- 客户租户
- 妙搭新壳
- 财务/法务高风险自动闭环
- 新 workflow 引擎

## 1. 你今天就怎么开始

### 最小启动命令

```bash
bash scripts/internal_ops_mvp.sh bootstrap ops-mvp-001 "中台管理试点同事"
```

这条命令会做 3 件事：

1. 用 `ops-management` 模板注册 1 个内部 clone。
2. 立即跑一次 `review-clones --portfolio internal`。
3. 立即生成一次 `sync-feishu --surface clone_governance --portfolio internal --dry-run` 本地预演。

### 中午巡检

```bash
bash scripts/internal_ops_mvp.sh midday
```

### 晚上收口

```bash
bash scripts/internal_ops_mvp.sh evening
```

### 看当前状态

```bash
bash scripts/internal_ops_mvp.sh status
```

### 看完整话术和周节奏

```bash
bash scripts/internal_ops_mvp.sh checklist
```

## 2. 固定前台话术

同事第一周只需要记住这 5 句：

1. `今天最该看什么`
2. `帮我接个任务：...`
3. `我现在有哪些任务`
4. `继续昨天那个`
5. `把这事闭环`

使用规则也固定：

- 早上先说 `今天最该看什么`
- 如果目标不清，再说 `帮我接个任务：...`
- 白天只说 `我现在有哪些任务 / 继续昨天那个 / 原力原力 记一下 ...`
- 晚上固定说 `把这事闭环`
- 前台同时最多 `3` 条活跃任务

## 3. 第一个闭环是什么

闭环名称固定为 `日常推进闭环`。

每条任务必须落到这 4 种状态之一：

- `completed`
- `blocked_needs_user`
- `blocked_system`
- `failed_partial`

第一周不接受模糊的“还在推进中但没有 blocker、没有 evidence、没有收口判断”。

## 4. 你和同事分别做什么

同事只做：

- 说今天重点
- 补业务上下文
- 处理必须人工决定的边界
- 晚上触发收口

你只做：

- 中午看一次 `waiting_human / blocked_* / 风险与决策表`
- 晚上看一次收口与风险
- 对高影响动作拍板
- 给一句最短反馈

AI大管家负责：

- route
- 任务压缩
- blocker 显性化
- evidence 归档
- closure 判断
- 每日 clone review

## 5. 第一周节奏

### Day 0

- 注册 clone
- 打开同事飞书入口
- 打开 `internal portfolio`
- 打开 `clone governance` 内部视图
- 确认对方只按固定话术使用

### Day 1-2

- 只验证 `早上定重点 -> 白天跟进 -> 晚上收口`
- 不改模板结构
- 只记真实 friction

### Day 3

只允许调一次 `ops-management` 模板，而且只调这 4 项：

- 目标模型
- 推荐 skill chain
- 禁止越权边界
- 评分指标

### Day 4-5

- 连续稳定跑
- 不再加功能
- 不扩第二位同事
- 不接客户

## 6. 直接可用的 CLI

如果你不想走包装脚本，也可以直接用这 4 条主命令：

```bash
python3 scripts/ai_da_guan_jia.py register-clone --clone-id ops-mvp-001 --customer-id yuanli-hq --display-name "中台管理试点同事" --org-id yuanli-hq --tenant-id yuanli-hq --actor-type employee --role-template-id ops-management --visibility-policy hq_internal_full --service-tier internal_core --report-owner liming
python3 scripts/ai_da_guan_jia.py review-clones --portfolio internal
python3 scripts/ai_da_guan_jia.py sync-feishu --surface clone_governance --portfolio internal --dry-run
python3 scripts/ai_da_guan_jia.py train-clone --clone-id ops-mvp-001 --target-capability "日常推进闭环"
```

这一轮实现里，`review-clones --portfolio internal` 已经会本地持久化内部账本，不再只是临时预览。

## 7. 你真正要看的东西

第一周只看这几个判断点：

- 谁在推进
- 谁卡住了
- 哪件事在等你拍板
- evidence 是否清楚
- blocker 是否真实
- 你手工催办和追问有没有下降

不要把这些误当成功：

- 看板亮了
- 话术顺了
- 同事觉得“挺好玩”

你要的成功只有一个：

- `你明显更少亲自盯人`

## 8. 第一周验收标准

- 连续 `5` 个工作日，每天至少 `1` 条真实任务走完整闭环
- 至少 `80%` 的任务在当天或次日早上前进入明确 closure state
- 至少 `2` 次任务被正确拦在 `blocked_needs_user`
- 你的手工催办/追问次数相对当前基线下降 `30%` 以上
- 第一周不新增第二位同事、不接客户、不扩财务法务
