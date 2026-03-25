# Context7 与 Task Master AI 可用验证清单 v1

这份清单只回答一个问题：**现在能不能真用**。

结论先写死：

- `Context7`：已可直接使用
- `Task Master AI`：已可直接使用，但当前机器必须切到 `Node 22` 路径

## 1. Context7

### 当前状态

- `~/.codex/config.toml` 里已经启用 `context7`
- `python3 scripts/check_codex_mcp.py` 返回 `ready`
- 当前检查结果显示 `context7: ok -> https://mcp.context7.com/mcp`

### 验证命令

```bash
python3 scripts/check_codex_mcp.py
```

### 使用方式

- 先按 `guide-benchmark-learning` 走 docs-first
- 需要最新官方文档时，优先用 `Context7`
- 不要把 README 热度当成可用性证明

## 2. Task Master AI

### 当前状态

- 官方仓库是 [eyaltoledano/claude-task-master](https://github.com/eyaltoledano/claude-task-master)
- 本机已经安装 `node@22`
- `npx -y task-master-ai --help` 在 `Node 22` 路径下返回 `0`
- 这说明它不是“只能看不能跑”，而是已经到了可用状态

### 运行前提

当前系统默认 `node` 仍然是 `v20.20.1`，所以要用下面这个路径先切到 `Node 22`：

```bash
export PATH="/opt/homebrew/opt/node@22/bin:$PATH"
```

如果只想临时跑一次，也可以直接在命令前加 `PATH=...`。

### 验证命令

```bash
python3 scripts/check_task_master_ai.py
```

### 已验证输出特征

- `node` 版本为 `v22.22.1`
- `task-master-ai --help` 返回 `0`
- 启动日志里能看到 MCP server 启动和核心工具注册

### 使用边界

- 它适合作为 `PRD -> 任务 -> 执行` 的规划桥
- 它还不是默认 canonical planning bridge
- 路由上仍然要先过 `task-spec`
- 如果要做 canonical 比对，先和 `self-evolution-max` 做 benchmark

## 3. 日常判断

以后看到这两个名字，直接按下面走：

| 名称 | 现在怎么判 | 现在怎么用 |
| --- | --- | --- |
| `Context7` | 已 ready | 直接拿来查官方文档和版本差异 |
| `Task Master AI` | 已 ready，但依赖 Node 22 PATH | 先切 Node 22，再作为规划桥使用 |

## 4. 一句话记忆

`Context7 现在就能查文档；Task Master AI 现在就能跑，但要先把 Node 切到 22。`

