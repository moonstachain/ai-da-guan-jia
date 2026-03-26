# Or Force OS GitHub Design v1

这份文档定义 GitHub 在原力OS 体系里的职责边界：它是协同层和证据层，不是真相层。

## 定位

GitHub 负责：

- 任务协作
- 变更记录
- PR 审核
- 证据镜像
- 发布追踪

GitHub 不负责：

- canonical truth
- runtime state
- Feishu 卡片绑定
- 业务系统的最终裁决

## GitHub 侧的四类对象

### 1. Issue

- 用于任务分发和协作入口
- 每个 issue 只描述一个清晰的工作目标
- 关联 Feishu / 本地证据 / PR

### 2. Project

- 用于阶段推进面板
- 建议列固定为：
  - `backlog`
  - `ready`
  - `in_progress`
  - `blocked`
  - `review`
  - `done`

### 3. PR / Commit

- 用于代码、协议、模板、脚本变更
- 每次变更都要能回链到一条任务或一个提案
- 不允许只有“看起来做了”的描述

### 4. Artifact mirror

- 用于保存验证结果、run summary、截图、同步状态
- 建议文件类型：
  - `verification_result.json`
  - `run_summary.md`
  - `sync_result.json`
  - `screen_capture.png`

## 标签体系

建议固定标签：

- `type:design`
- `type:clone`
- `type:governance`
- `type:dashboard`
- `type:feishu-sync`
- `status:blocker`
- `status:ready`
- `status:verified`

## 分支建议

- 分支前缀：`codex/`
- 分支命名建议：`codex/<domain>-<short-slug>`
- 每个分支只承载一个明确子目标

## GitHub 与 Feishu 的关系

- GitHub 记录变更链
- Feishu 记录结构化治理事实
- 本地 canonical 记录最终真相
- 任一镜像都不能反向升级为本体

## 推荐工作流

1. 先在本地 canonical 完成改动或设计
2. 再生成 GitHub 变更摘要
3. 再回写 Feishu 结构化数据
4. 最后把 evidence mirror 贴到 issue / PR

## 这次设计的 GitHub 目标

- 让任务、证据、提案、review 都有可追踪位置
- 让 clone 的能力晋升可以通过 issue / PR 链路进入共享核心
- 让每次完成都能回到同一条治理闭环

