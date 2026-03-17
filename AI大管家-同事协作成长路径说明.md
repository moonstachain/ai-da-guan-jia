# AI大管家-同事协作成长路径说明

## 0. 一句话判断

截至 `2026-03-15`，`AI大管家` 已经不只是能帮你启动 `1 位中台管理同事` 的第一周 MVP，还可以按 `激活 -> 协作 -> 半自治操盘 -> 方法进化 -> 组织复制` 的完整路径来运营。

这个路径的目标不是“同事开始用 AI”，而是形成 3 层递归闭环：

- `同事越干越顺`
- `你越看越省心`
- `AI大管家 越跑越会治理这类岗位`

## 1. 默认协作结构

这一版固定采用：

- `1 个共享 AI大管家 治理核`
- `1 个 internal employee clone`
- `1 条 internal portfolio 总账`
- `1 个总部总控舱`

使用入口分两层：

1. 第一阶段：同事先通过本地脚本和固定口令完成激活。
2. 第二阶段：飞书 / 原力OS 作为自然语言前台。

GitHub 只负责代码分发和镜像治理，不是同事每天工作的入口。

## 2. 你今天怎么启动

### 最小启动

```bash
bash scripts/internal_collaboration_playbook.sh bootstrap ops-mvp-001 "中台管理试点同事"
```

### 看当前在哪个阶段

```bash
bash scripts/internal_collaboration_playbook.sh status ops-mvp-001
```

### 看完整阶段图

```bash
bash scripts/internal_collaboration_playbook.sh phase-map
```

### 看创始人巡检面

```bash
bash scripts/internal_collaboration_playbook.sh founder-loop
```

## 3. Phase 0：激活与边界定型

### 目标

让同事从“装好了工具”变成“拥有一个属于自己的岗位实例”。

### 同事要做什么

- 知道自己只用 `1` 个主岗位模板
- 知道固定前台话术或等价本地入口
- 不把 GitHub、脚本细节、飞书底表当成工作入口

### 你要做什么

- 注册 `1` 个 internal `ops-management` clone
- 确认 `review-clones --portfolio internal` 可见
- 确认 `sync-feishu --surface clone_governance --portfolio internal --dry-run` 可见

### AI大管家 要做什么

- 写入 `clone_id / memory_namespace / scorecard / training history`
- 初始化内部治理账本
- 产出总部摘要视图

### 阶段成果

- 同事已经拥有独立实例，不再是共用你的个人会话
- 你能在总部总控舱看到这位同事
- 边界已经固定：审批、付款、发布、删除、法务确认仍归人

### 验收标准

- bootstrap 成功
- `internal portfolio` 可见
- `clone governance` dry-run 可见
- 同事知道固定 5 句前台话术或等价本地入口

## 4. Phase 1：学会和 AI大管家 协作

### 目标

让同事把 `AI大管家` 当岗位副驾，而不是问答机器人。

### 协作协议

- 早上：给今天重点
- 白天：看任务、续上下文、补信息、处理边界
- 晚上：触发收口

### 同事的协作要求

- 只说目标、上下文、边界
- 不自己先拆一长串碎步骤
- 不同时让 AI 扮演多个岗位

### AI大管家 的沉淀重点

- 任务风格
- 常见阻塞类型
- 高频边界动作
- 推荐 skill chain

### 阶段成果

- “公寓 / 交付 / 管理 / 流量” 等日常事项开始变成清晰任务链
- 每条任务被压成 `下一步 / blocker / evidence / closure_state`

### 验收标准

- 连续 `5` 个工作日，每天至少 `1` 条真实任务走完整闭环
- 至少 `80%` 任务进入明确 `closure_state`
- 至少 `2` 次正确落到 `blocked_needs_user`

## 5. Phase 2：岗位半自治操盘

### 目标

让这位同事在自己的主岗位里形成真实减负。

### AI大管家 默认承担

- 任务 intake 与压缩
- 优先级排序
- blocker 显性化
- evidence 归档
- closure 判断
- 每日 clone review 建议

### 同事仍保留

- 业务判断权
- 登录 / 授权 / 发布 / 删除 / 付款 / 审批边界
- 关键上下文补充

### 你能实时看见

- 谁在推进
- 谁卡住了
- 哪件事在等你拍板
- 哪些风险被挡在 `waiting_human / blocked_*`

### 阶段成果

- 多线程事务不再靠脑内记忆推进
- 默认前台最多 `3` 条活跃任务
- 你不需要再靠高频追问维持推进感

### 验收标准

- 你的手工催办 / 追问次数下降 `30%+`
- 同事对当天工作形成 `重点清楚 / 阻塞清楚 / 收口清楚` 的稳定节奏

## 6. Phase 3：从会用到会进化

### 目标

让同事不只是更快完成工作，而是开始为组织贡献岗位方法。

### AI大管家 必须抓的 5 类材料

1. 高频任务模式：哪些类型任务反复出现
2. 有效 skill chain：哪些组合最稳、最省打扰
3. 失真模式：哪些误判、假闭环、假推进反复出现
4. 边界模式：哪些事应该稳稳拦给人
5. 岗位方法论候选：哪些做法值得晋升为模板

### 本地 canonical 必须持续落地

- `task_runs`
- `training_cycles`
- `scorecards`
- `capability_proposals`
- `alerts_decisions`

### 晋升机制

`同事实例内发现改进 -> 进入 capability_proposals -> 总部复核 -> 晋升共享核心 / 保持岗位局部 / 驳回`

### 阶段成果

- 同事开始产出“岗位方法”，不是只有岗位执行
- `AI大管家` 开始学会如何治理 `ops-management`

## 7. Phase 4：组织复制与共享治理

### 目标

把成熟路径复制到财务、人力法务、增长转化、交付、产品等岗位。

### 固定复制规则

- 共享同一个治理核
- 每人一个独立 clone
- 每人一个主岗位模板
- 总部仍看一个主库
- 不复制 repo
- 不复制 skill 仓库

### 你在总部总控舱要看的 4 个维度

- 各岗位 clone 的评分变化
- 哪个岗位在产生高价值方法
- 哪个岗位长期失真高，需要降权或重训
- 哪些能力能提炼成共享组织资产

### 阶段成果

- 你看到的不再是很多零散 AI 助手
- 而是一组可比较、可训练、可晋升的岗位实例

## 8. 你、同事、AI大管家的长期分工

### 同事

- 提供目标、上下文、业务判断、边界动作
- 在自己的岗位里持续产生真实工作样本

### 你

- 做共同治理者
- 看摘要和风险
- 决定自治边界、能力晋升、模板升级

### AI大管家

- 负责路由、验真、收口、评分、训练、提案
- 把“任务完成”转成“组织能力进化”

## 9. 创始人摘要优先监控法

你默认不看全量细节，只先看摘要。

每天只保留两次固定介入：

- 中午：看 `waiting_human / blocked_* / 风险与决策表`
- 晚上：看收口状态、evidence、blocker 和第二天训练建议

你需要先回答 3 个问题：

- 现在谁在推进
- 谁卡住了
- 哪件事在等我拍板

只有摘要异常时，才下钻到：

- `task_runs`
- `capability_proposals`
- `alerts_decisions`
- `portfolio-daily-report`

## 10. 最完美状态

### 同事侧

- 每个人都有一个岗位副驾
- 日常工作被压成清晰推进和可验证收口
- 不再靠碎聊天和脑内记忆维持执行

### 你这侧

- 默认看摘要
- 异常时下钻
- 不再靠亲自盯人维持推进

### AI大管家 这侧

- 不断吸收真实岗位经验
- 反哺 `role_template / skill_chain / boundary_rule / scorecard_metric / governance_rule`

## 11. 和现有 MVP 的关系

`内部同事版第一闭环 MVP` 不是另一套体系。

它就是完整成长路径的：

- `Phase 0`
- `Phase 1`

如果你只想先跑第一周，直接看：

- [AI大管家-内部同事版第一闭环MVP启用说明.md](./AI大管家-内部同事版第一闭环MVP启用说明.md)

如果你要按完整路径运营这位同事，就用：

- `bash scripts/internal_collaboration_playbook.sh overview`
- `bash scripts/internal_collaboration_playbook.sh status <clone-id>`
