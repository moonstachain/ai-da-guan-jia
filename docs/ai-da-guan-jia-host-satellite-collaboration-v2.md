# AI大管家主机-卫星协同工作框架 v2

## Summary

- 当前固定模型是 `1 main-hub + 3 satellites`。
- `main-hub` 继续是唯一 canonical source。
- `大管家卫星白色` 允许在完成 onboarding 后承担 `副总控 / 故障切换控制面`，但不升格为第二主机。
- 三个用户可直呼的卫星名称固定为：
  - `大管家卫星O`
  - `大管家卫星白色`
  - `大管家卫星黑色`
- 默认派工规则固定为：
  - 指名哪个卫星，就直派到那个卫星绑定的 `source_id`
  - 未指名时，默认走 `大管家卫星O`

## 固定绑定

- `大管家卫星O -> satellite-03`
- `大管家卫星白色 -> satellite-01`
- `大管家卫星黑色 -> satellite-02`
- `old` 只保留为 `大管家卫星O` 的兼容旧别名

## 协作边界

- 卫星负责：
  - 远程执行
  - 浏览器 / 登录态任务
  - 证据采集
  - 局部验证
- `大管家卫星白色` 额外负责：
  - 黑色 / old 的日常调度
  - heartbeat 汇总
  - repo-local evidence intake
  - `reclaim_to_main_hub`
  - `main-hub` 暂时不可用时的 `proposal / pending_judgement` 级故障切换
- 主机负责：
  - 正式 route
  - aggregate / audit
  - close-task
  - evolution
  - Feishu / GitHub mirror

## 状态推进

- `大管家卫星O` 复用现有 `satellite-03`，不重做 onboarding。
- `大管家卫星白色` 和 `大管家卫星黑色` 在拿到以下工件前都只能是 `pending_onboarding`：
  - `probe.json`
  - `inventory.json`
  - `verify.json`
  - `onboarding-result.json`
- 只有工件齐全后，`satellite-01 / satellite-02` 才允许进入 canonical expected sources。
- 对 `大管家卫星白色` 来说，进入 expected sources 之后也只代表：
  - 可以承担 `deputy-control-plane`
  - 不代表可以替代 `main-hub`

## 白色副总控边界

- `大管家卫星白色`
  - 允许：
    - satellite reachability probe
    - task dispatch to `大管家卫星黑色` / `大管家卫星O`
    - heartbeat aggregation
    - local evidence intake
    - reclaim packet generation back to `main-hub`
    - degraded-mode coordination
  - 禁止：
    - canonical truth promotion
    - `close-task`
    - `record-evolution`
    - `sync-feishu --apply`
    - `sync-github --apply`
    - 重写长期策略或记忆母本

## 黑色与 O 的固定角色

- `大管家卫星黑色`
  - 默认承担：
    - governance
    - support
    - verify
    - repo-local evidence
- `大管家卫星O`
  - 默认承担：
    - legacy execution
    - browser / login reuse
    - 历史环境与特定执行面

## 对话语义

- `大管家卫星O：<任务>` = 默认远程执行到 `satellite-03`
- `大管家卫星白色：<任务>` = 远程执行到 `satellite-01`
- `大管家卫星黑色：<任务>` = 远程执行到 `satellite-02`
- `AI大管家：<任务>` = 默认远程执行到 `大管家卫星O`

## 历史快照

- `docs/black-white-old-host-satellite-mvp-v1.md` 保留为旧阶段快照，不再作为当前默认派工语义。
