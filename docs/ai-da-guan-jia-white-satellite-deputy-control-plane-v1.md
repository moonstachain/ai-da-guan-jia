# 白色卫星副总控 / 故障切换协议 v1

> 这份协议只定义 `白色卫星 = 副总控 / 故障切换控制面` 的最小可信边界。  
> 它不改变 [docs/ai-da-guan-jia-host-satellite-collaboration-v2.md](/Users/liming/Documents/codex-ai-gua-jia-01/docs/ai-da-guan-jia-host-satellite-collaboration-v2.md) 里 `main-hub` 唯一 canonical source 的根规则。

## 1. 角色定位

- `白色卫星` 不是新的 `main-hub`，也不是第二记忆母本。
- 它是 `deputy-control-plane`：
  - 常驻观察
  - 卫星调度
  - 心跳汇总
  - 局部证据 intake
  - main-hub 暂时不可用时的故障切换协调
- 它的目标不是替代总控，而是让系统在 `main-hub` 忙碌、离线或跨网不稳定时仍能维持秩序。

## 2. 角色边界

### 白色卫星能做什么

- 探测 `黑色卫星` 与 `大管家卫星O / old` 的连通性
- 把任务派给 `黑色卫星` 或 `大管家卫星O / old`
- 汇总 heartbeat、局部验证结果和 repo-local 证据
- 生成 `reclaim_to_main_hub` 包，把结果送回主机正式裁决
- 在 `main-hub` 暂时不可用时，维持 `proposal / pending_judgement` 级治理不断线

### 白色卫星不能做什么

- 不能升格为新的 canonical source
- 不能执行 `close-task`
- 不能执行 `record-evolution`
- 不能执行 `sync-feishu --apply`
- 不能执行 `sync-github --apply`
- 不能重写长期策略、记忆母本或正式线程状态
- 不能对 `黑色卫星` 和 `大管家卫星O / old` 发出与 `main-hub` 冲突的根指令

### 仍保留给 main-hub

- 正式 route
- 全局优先级
- final truth judgement
- closure / evolution
- Feishu / GitHub mirror
- 长期记忆与战略母本

## 3. 四层同步

### 能力层

- 同步：
  - skill inventory
  - 路由规则
  - 卫星协议
  - 黑色线 / 主线协作文档
- 目标：
  - 让白色使用和当前总控一致的判断语言

### 运行层

- 同步：
  - `strategy/current`
  - 活跃线程摘要
  - 当前 blockers
  - 卫星绑定
- 目标：
  - 让白色知道当前系统在推进什么

### 记忆层

- 只同步 `read-mostly memory snapshot`
- 允许读取：
  - 近期决策
  - 当前任务摘要
  - 关键边界
  - 卫星现状
- 不允许形成可自由改写的第二记忆母本

### 凭据层

- 只同步白色履职所需的：
  - SSH
  - remote dispatch
  - read-only verify
- 不默认复制：
  - publish
  - mirror apply
  - closure

## 4. 两种工作模式

### `normal_deputy_mode`

- `main-hub` 在线
- 白色只做：
  - 常驻观察
  - 代派工
  - 代收证据
  - 代协调
- 一切正式裁决仍回 `main-hub`

### `failover_mode`

- `main-hub` 暂时不可用
- 白色可以继续：
  - 观察黑色与 old
  - 收集证据
  - 产出 pending decisions
- 但只允许输出：
  - `proposal`
  - `pending_judgement`
  - `reclaim_to_main_hub`

## 5. Onboarding / Promotion 条件

白色要作为副总控使用，必须已经具备：

- `probe.json`
- `inventory.json`
- `verify.json`
- `onboarding-result.json`

并满足：

- 能访问工作区与必要脚本
- 能解析 `白色 / 黑色 / O / old` 绑定
- 能探测 `satellite-02` 与 `satellite-03`
- 能生成 repo-local dispatch / reclaim / heartbeat 产物
- 不能越权执行 canonical closure

## 6. 黑色与 OLD 的固定分工

- `黑色卫星`
  - 优先承接：
    - governance
    - support
    - verify
    - gap clarification
    - repo-local bundle
- `大管家卫星O / old`
  - 优先承接：
    - browser
    - login reuse
    - legacy execution
    - historical environment tasks
- `白色卫星`
  - 只负责：
    - 选谁来干
    - 收谁的证据
    - 何时回收到 `main-hub`

## 7. Canonical Files

- 协议文档：
  - [ai-da-guan-jia-white-satellite-deputy-control-plane-v1.md](/Users/liming/Documents/codex-ai-gua-jia-01/docs/ai-da-guan-jia-white-satellite-deputy-control-plane-v1.md)
- machine-readable contract：
  - [white-satellite-deputy-control-plane-contract.json](/Users/liming/Documents/codex-ai-gua-jia-01/work/ai-da-guan-jia/artifacts/ai-da-guan-jia/satellites/current/white-satellite-deputy-control-plane-contract.json)
