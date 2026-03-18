# 老笔记本 Satellite Onboarding Playbook

这份 playbook 把“另一台旧机器也在跑 Codex”的场景固定成一条可验证、可长期维护的纳管链。  
默认目标不是切主，而是把老笔记本接成 `satellite-01`，由当前主机 `main-hub` 统一盘点、验真和管理。

这条链现在同时支持两类客户端栈：

- `codex-app`：远端直接安装 `Codex.app`
- `vscode-agent`：远端主要在 `Visual Studio Code` 里跑 Codex/Claude Code 一类代理工作流

也就是说，`Codex.app` 不再是所有 satellite 的唯一形态。

## 什么时候用这份文档

用这份文档：

- 当前主机已经稳定
- 另一台机器也装了 Codex，想继续纳入统一治理
- 目标是 `第二台机器可控 + 可盘点 + 可接入 hub`

不要用这份文档：

- 你要把另一台机器升级成默认主控  
  这时继续用 [new-mac-cutover-playbook.md](/Users/hay2045/Documents/codex-ai-gua-jia-01/docs/new-mac-cutover-playbook.md)

## 默认角色

- 当前主机：`main-hub`
- 老笔记本：`satellite-01`
- 控制方式：`SSH + Screen Sharing`
- 网络假设：同一局域网
- 目标状态：尽量恢复到“和主机接近的一样能用”，但不把 sidebar 呈现 100% 一致当成硬验收

## Day-0 人类动作

在老笔记本上先完成：

1. 打开 `Remote Login`
2. 打开 `Screen Sharing`
3. 把主机的 SSH 公钥加到老笔记本
4. 如缺环境，再补：
   - `Homebrew`
   - `Python 3.11+`
   - `Node 20+`
5. 如老笔记本还没有目标工作区，先准备：
   - `~/Documents/codex-ai-gua-jia-01`

当前唯一必须由人手完成的边界仍然是：

- 打开系统共享服务
- 首次把主机公钥写进远端 `~/.ssh/authorized_keys`
- 首次登录那些只能人工扫码/确认的浏览器或桌面应用

如果机器只是能 SSH 登录，但没开 Screen Sharing，不算完整可管状态。

## 标准顺序

标准顺序固定为：

1. `probe`
2. `inventory`
3. `verify`
4. `onboard`

对应命令：

```bash
scripts/probe_remote_codex_host.sh --host <host> --user <user> --source-id satellite-01
scripts/remote_inventory_codex_host.sh --host <host> --user <user> --workspace-root /Users/<user>/Documents/codex-ai-gua-jia-01 --source-id satellite-01
scripts/remote_verify_codex_host.sh --host <host> --user <user> --workspace-root /Users/<user>/Documents/codex-ai-gua-jia-01 --source-id satellite-01
scripts/onboard_satellite_host.sh --host <host> --user <user> --workspace-root /Users/<user>/Documents/codex-ai-gua-jia-01 --source-id satellite-01
```

如果这台机器是像 `old` 那样主要在 VSCode 里跑，而不是标准 `Codex.app` 桌面栈，建议显式带上：

```bash
scripts/probe_remote_codex_host.sh --host <host> --user <user> --source-id satellite-01 --client-mode vscode-agent
scripts/remote_inventory_codex_host.sh --host <host> --user <user> --workspace-root /Users/<user>/Documents/codex-ai-gua-jia-01 --source-id satellite-01 --client-mode vscode-agent
scripts/remote_verify_codex_host.sh --host <host> --user <user> --workspace-root /Users/<user>/Documents/codex-ai-gua-jia-01 --source-id satellite-01 --client-mode vscode-agent
scripts/onboard_satellite_host.sh --host <host> --user <user> --workspace-root /Users/<user>/Documents/codex-ai-gua-jia-01 --source-id satellite-01 --client-mode vscode-agent
```

在 `vscode-agent` 模式下：

- `verify` 会把 `Codex.app` 和 `Codex MCP` 检查自动降成 `skip`
- 重点验真转到 `SSH / toolchain / workspace / ai-da-guan-jia script / intake bundle / hub aggregate`
- 如果你想强行检查独立 `Codex.app`，再显式传 `--verify-codex-app-mode strict` 或 `--verify-mcp-mode strict`

## “尽量一模一样”的定义

这里的“尽量一模一样”固定指：

- 工作区可以打开
- skills 可以正常盘点和调用
- `state_5.sqlite / sessions / archived_sessions` 这类状态层存在
- GitHub / Feishu / Get笔记 等授权尽量复用
- 浏览器型 skill 至少能判断“已可进站”还是“只差重新登录”

这里**不承诺**：

- sidebar 命名完全和主机一模一样
- thread 排序、置顶、展开状态 100% 自动还原

如果内容层已在，但 sidebar 呈现不同，这算“展示层差异”，不算纳管失败。

## 成功标准

一台旧机器要算正式纳入 `satellite-01`，至少满足：

- `probe` 返回 `ready`
- `inventory` 返回 `inventory_complete`
- `verify-restore.sh` 通过，或只留下已知的 `warn` 级差异
- 远端 `emit-intake-bundle --source-id satellite-01 --mode full` 成功
- 主机侧 `aggregate-hub` 和 `audit-maturity` 成功
- `source-topology/source-status` 已能看到 `satellite-01`

## 失败时的处理

如果 `probe / inventory / verify` 任一失败：

- 不进入正式 satellite 接入
- 这台机器保持 `blocked_needs_user`
- 优先修：
  - 共享服务
  - Python / Node / Codex 环境
  - workspace
  - `~/.codex`
  - GitHub / Feishu / Get笔记 登录态

## 工件位置

所有本地纳管工件默认写到：

```text
output/ai-da-guan-jia/remote-hosts/<source-id-or-host>/
```

固定会有：

- `probe.json`
- `inventory.json`
- `inventory-summary.md`
- `verify.json`
- `verify.log`
- `emit-bundle.log`
- `aggregate.log`
- `audit.log`
- `onboarding-result.json`

这些工件就是后续复盘、继续接管、或判断要不要补授权的真相源。

## 纳管后的协作语义

一台机器被正式接成 `satellite-*` 后，默认不等于“第二主机”。

纳管后的长期规则固定为：

- `main-hub`
  - 继续是唯一 canonical source
  - 负责正式主线、策略层、闭环和治理写回
- `satellite-*`
  - 默认承担采集、浏览器执行、登录复用、局部推进
  - thread 语义默认是 `临时前哨`
  - 重要任务的真正收口仍回 `main-hub`

完整工作方式见 [docs/ai-da-guan-jia-host-satellite-collaboration-v1.md](/Users/hay2045/Documents/codex-ai-gua-jia-01/docs/ai-da-guan-jia-host-satellite-collaboration-v1.md)。
