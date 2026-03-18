# 并行执行协议：Claude × 桌面 Codex × 黑色卫星机

> 本文件定义三端协作的标准流程。
> 存放位置：yuanli-os-claude/specs/parallel-execution-protocol.md

---

## 三端角色定义

| 端 | 身份 | 职责 | 运行时间 |
|---|------|------|---------|
| Claude | 策略中枢 | 六判断、Task Spec 生成、验真、evolution log | 人类在线时 |
| 桌面 Codex | 调度台 + 轻任务执行 | 审批分发、轻量任务直接执行、窗口管理 | 人类在线时 |
| 黑色卫星机 Codex | 执行工厂 | 重任务、长任务、多窗口并行执行 | 7×24 |

## 人类在三端中的角色

- **审批 Task Spec**：Claude 生成后，人类确认再分发
- **观察窗口**：黑色卫星机的 Codex 窗口保持人类可视
- **带回结果**：把 GitHub 上的 commit hash / pytest 输出带回 Claude
- **不需要做**：中间技术判断、代码审查细节、每一步确认

---

## 标准工作流

### 单任务流程（串行）

```
Claude 出 Task Spec
    ↓
人类审批
    ↓
粘贴到桌面 Codex → 桌面 Codex 直接执行（轻任务）
    或
粘贴到桌面 Codex → 桌面 Codex 分发到黑色卫星机（重任务）
    ↓
执行完成 → commit + push to GitHub
    ↓
人类把 commit hash + pytest 输出带回 Claude
    ↓
Claude 验真 + evolution log + 更新 CLAUDE-INIT.md
```

### 并行任务流程（多窗口）

```
Claude 一次性输出多份 Task Spec（标注可并行）
    ↓
人类审批全部
    ↓
桌面 Codex 分发到黑色卫星机：
    窗口 1 → Task Spec A（如 R7 数据迁移）
    窗口 2 → Task Spec B（如 R8 Proxy）
    窗口 3 → Task Spec C（如 R9 xxx）
    ↓
各窗口独立执行，各自 commit + push
    ↓
全部完成后，人类把所有 commit hash 带回 Claude
    ↓
Claude 逐个验真，批量写 evolution log
```

---

## 任务分类规则

### 轻任务（桌面 Codex 直接执行）

- 单文件修改
- 文档更新
- 配置变更
- < 5 分钟可完成

### 重任务（分发到黑色卫星机）

- 多文件创建
- 需要 pytest 跑完整套测试
- 涉及飞书 API 调用
- 涉及数据迁移或批量写入
- 预估 > 10 分钟

### 可并行的判断标准

两个 Task Spec 可以并行，当且仅当：

1. **文件不重叠**：各自创建/修改的文件没有交集
2. **目录不重叠**：各自工作的目录独立
3. **不存在数据依赖**：B 不需要 A 的产出作为输入
4. **不存在 import 依赖**：B 不需要 import A 新建的模块

Claude 在输出 Task Spec 时会显式标注：

```
并行标记：可与 R8 并行执行（文件无重叠，无数据依赖）
```

或：

```
串行标记：必须在 R7 完成后执行（依赖 R7 写入的飞书数据）
```

---

## Task Spec 并行输出格式

当 Claude 判断有多个任务可以并行时，输出格式为：

```markdown
# 本轮并行任务包

## 并行可行性分析
- Task A 和 Task B 文件不重叠 ✅
- Task A 和 Task B 无数据依赖 ✅
- Task A 和 Task C 有串行依赖 ❌（C 需要 A 的产出）

## 执行计划
- 窗口 1：Task A（R7 数据迁移）
- 窗口 2：Task B（R8 Proxy）
- 等待 A 完成后 → 窗口 3：Task C

## Task Spec A
[完整 Task Spec]

## Task Spec B
[完整 Task Spec]

## Task Spec C（等待 A 完成）
[完整 Task Spec]
```

---

## GitHub 分支策略

### 默认模式（当前）

所有任务直接 push 到 main。适合当前阶段（单人+AI协作，快速迭代）。

### 并行安全模式（推荐升级）

当多窗口并行执行时，为避免 push 冲突：

```
窗口 1 → 创建 branch: feat/r7-data-migration → push → PR → merge to main
窗口 2 → 创建 branch: feat/r8-feishu-proxy → push → PR → merge to main
```

各窗口在独立 branch 上工作，完成后创建 PR。PR 合并可以由人类手动做，也可以在 pytest 通过后自动合并。

Claude 验真时检查的是 main 上的最终合并状态。

---

## 黑色卫星机的环境要求

### 已有
- Codex CLI / API 连接
- Python 3.11+
- Git + GitHub 推送权限
- 飞书环境变量（FEISHU_APP_ID / FEISHU_APP_SECRET）

### 需要确保
- ai-da-guan-jia 仓库已 clone 且 main 分支最新
- pytest 可运行
- 网络可访问 GitHub 和飞书 API

### 建议新增
- PROXY_TOKEN 环境变量（R8 完成后）
- tmux 或 screen（多窗口管理，SSH 断开不中断）

---

## 监控与可见性

### 人类可视要求

黑色卫星机的每个 Codex 窗口必须保持人类可观察。方式：

1. **桌面 Codex 窗口**：直接在桌面端看到每个窗口的实时输出
2. **SSH + tmux**：如果远程操作，用 tmux 分屏保持可视
3. **GitHub Commit 流**：每个窗口完成后的 commit 在 GitHub 上可追溯

### Claude 可视要求

Claude 通过以下方式获得可见性：

1. **GitHub commit history**：人类带回 commit hash
2. **pytest 输出**：人类带回测试结果
3. **Feishu Proxy（R8 后）**：Claude 直接 web_fetch 验证飞书数据

---

## 异常处理

### 窗口执行失败

```
如果某个窗口的 Task 失败：
1. 不影响其他窗口继续执行
2. 失败的窗口保留现场（不清理中间产物）
3. 人类把错误信息带回 Claude
4. Claude 判断：修复后重试 / 调整 Task Spec / 跳过留到下一轮
```

### Push 冲突

```
如果两个窗口同时 push 到 main 产生冲突：
1. 后 push 的窗口 pull --rebase 后重试
2. 如果自动 rebase 失败，人类介入手动解决
3. 或者直接用分支模式避免此问题
```

### 黑色卫星机离线

```
如果黑色卫星机断网或断电：
1. 已 push 的结果不受影响（GitHub 上已有）
2. 未 push 的结果在本地，重新上线后继续
3. Claude 只验真 GitHub 上的结果，不验真未 push 的本地状态
```

---

## 与 CLAUDE-INIT.md 的关系

每轮验真后，Claude 更新 CLAUDE-INIT.md 时需要记录：

```
执行方式：串行 / 并行（窗口 1: R7, 窗口 2: R8）
执行端：桌面 Codex / 黑色卫星机
```

这样任何新 Claude 会话都能知道上一轮是怎么执行的。
