# moonstachain/claude-code 深度整合报告 v1

## 一句话结论

`moonstachain/claude-code` 应该被当作 `Python-first` 的 porting workspace 与能力索引来吸收，而不是被整仓当成一个要直接并入的 runtime。

最值得深整合的，是它的控制面、路由面、任务/记忆面和桥接面。

## 证据摘要

- `src/main.py` 暴露了 `summary`、`manifest`、`parity-audit`、`commands`、`tools`、`route`、`show-command`、`show-tool` 这些面向观察与路由的入口。
- `src/runtime.py` 只是基于命中词的路由器，适合作为 benchmark，不适合作为最终治理策略引擎。
- `src/port_manifest.py` 和 `src/query_engine.py` 更像观察层和报表层。
- `src/tasks.py`、`src/context.py`、`src/cost_tracker.py` 提供了任务、上下文和预算的轻量骨架。
- `src/parity_audit.py` 提供了一个可验证的 parity gate，适合作为质量门样本。
- `tests/test_porting_workspace.py` 已经在验证 summary、parity、commands、tools 和 route 这些基础面。
- README 明确把仓库定位成 Python-first porting workspace，并且承认当前还不是完整的 runtime 等价实现。

## 深整合分层

### 1. 直接吸收

这些层与 AI大管家的治理内核最接近，应该优先纳入：

- `skills / routing / review`
- `task / session / memory / evolution`
- `parity / review / security / cost` 质量门

对应到 AI大管家，就是：

- `review-skills`
- `evaluate-external-skill`
- `skill-trainer-recursive`
- `ai-metacognitive-core`
- `project-heartbeat`
- `window-heartbeat`
- `close-task`
- `strategy-governor`

### 2. Benchmark then port

这些层值得吸收，但要先保留为 benchmark，再决定是否转成 canonical 结构：

- `agents / worktree / remote / mcp / plugin`
- `review / security / cost / parity`
- `command surface` 与 `tool surface` 的统一索引

对应到 AI大管家，就是：

- `agency-agents-orchestrator`
- `self-evolution-max`
- `opencli-platform-bridge`
- `feishu-bitable-bridge`
- `feishu-km`
- `review-governance`

### 3. 保持外部

下面这些层先不要并入治理核心：

- `components`
- `utils`
- `screens`
- 任何 UI/runtime-heavy 细节

原因很简单：

- 它们会把整合问题拖成重建 runtime
- 它们不直接提升治理、验真和闭环
- 它们更适合作为后续的参考实现，而不是第一批吸收对象

## 推荐顺序

1. 先把 `skills / routing / review` 接到 AI大管家的外部技能评估与训练链路。
2. 再补 `task / session / memory / evolution`，把任务、心跳、预算和 canonical log 统一起来。
3. 再接 `agents / worktree / remote / mcp / plugin`，把多窗口、多代理和桥接同步做成控制面。
4. 最后把 `review / security / cost / parity` 固化为回归门。
5. `components / utils / screens` 保持在最末端，等前四层稳定后再谈。

## 回归门

要把这个仓库真正纳入 AI大管家 的深整合样本，至少要满足下面几条：

- `evaluate-external-skill` 的结果稳定落在 `portable_reference`
- `runtime_target` 使用 `multi_harness`
- 回归测试覆盖 `summary` / `route` / `parity` 的关键行为
- `claude-code-my-workflow-bridge.md` 保持为唯一桥接入口

## 实施结论

这次实现不应该追求“整套搬进来”，而应该追求：

- 把这个 repo 变成 AI大管家的外部 benchmark 样本
- 把它的路由、任务、验证和桥接层变成可复用结构
- 把 UI/runtime-heavy 的部分留在后面

换句话说：

`先吸收方法层，再吸收控制层，最后才考虑展示层。`
