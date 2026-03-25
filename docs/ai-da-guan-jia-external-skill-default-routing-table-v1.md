# AI大管家 外部 Skill 默认路由表 v1

这是一份日常版速查表。  
更长的分析版见 [AI大管家 外部 Skill 吸收矩阵 v1](/Users/liming/Documents/codex-ai-gua-jia-01/docs/ai-da-guan-jia-external-skill-absorption-matrix-v1.md)。

## 1. 先看这三条

1. 只要是在问“这个外部 skill 值不值得接、能不能用、怎么用”，先走 `evaluate-external-skill`。
2. 只要评估结果是 `directly_usable`，才考虑 `install_now`。
3. 只要评估结果是 `portable_reference` 或 `intel_only`，默认都不要直接收编进 skill core。

## 2. 默认分流表

| 触发场景 | 默认路由 | 代表项 | 默认动作 | 不要做什么 |
| --- | --- | --- | --- | --- |
| 外部 skill / GitHub repo 评估 | `evaluate-external-skill` | 任意外部候选 | 先产评估卡，再决定去向 | 不要跳过评估直接安装 |
| 官方文档 / 陌生库 / 版本差异 | `guide-benchmark-learning` + `Context7` | `Context7` | 先 docs-first，再判断是否接入 | 不要把 README 热度当验真 |
| PRD -> 任务拆解 -> 进度推进 | `task-spec`，必要时再看 `Task Master AI` | `Task Master AI` | 先用现有任务规格，再 benchmark 规划桥 | 不要让两个规划桥并行抢 canonical |
| 调试 / 根因分析 / 盲修风险 | `ai-metacognitive-core` + `Systematic Debugging` | `Systematic Debugging` | 先 root cause，再修复 | 不要先编码后找证据 |
| 上下文压缩 / token 控制 | `Context Optimization` | `Context Optimization` | 先缩上下文，再做决策 | 不要在上下文爆炸时继续扩 scope |
| 代码库搜索 / 记忆 / 定位 | `File Search` + `Codebase Memory MCP` | `File Search`、`Codebase Memory MCP` | 先定位，再进入改动 | 不要靠记忆猜文件位置 |
| 抓取 / 搜索 / 研究信号 | 只作情报，不进主线 | `Tavily`、`GPT Researcher`、`AutoResearch` | 只保留研究信号 | 不要把包装感当闭环证据 |
| 文档 / 表格 / 幻灯片 | 内部文档工作流 | `pdf`、`doc`、`slides`、`spreadsheet` | 直接走文档执行器 | 不要先引入外部 runtime |
| 设计 / 品牌 / 视觉产出 | `agency-design` | `Frontend Design`、`Brand Guidelines`、`Theme Factory`、`Canvas Design` | 设计先验收，再产出 | 不要把风格灵感当成规范 |
| 自动化 / Agent runtime / 编排引擎 | 保持外部底座 | `LangGraph`、`Dify`、`CrewAI`、`n8n`、`Ollama`、`Open WebUI`、`Firecrawl`、`DSPy`、`Spec Kit` | 只接工具层 | 不要把 runtime 误抬成 skill core |
| 知识库 / Notion / 飞书知识问答 | 先知识后整理 | `knowledge-orchestrator`、`notion-*`、`feishu-km` | 先原始答复，再做整理 | 不要让镜像反客为主 |
| Feishu 写回 | 先本地 canonical log | `feishu-bitable-bridge` | 本地真相先定，再同步 | 不要先同步后补真相 |

## 3. 外部 skill 桶怎么处理

### 3.1 `directly_usable`

典型代表：

- `Context7`
- `Task Master AI`

默认动作：

- 先进入本地安装验证
- 只在通过验真后再考虑进入日常路由

### 3.2 `portable_reference`

典型代表：

- `Context Optimization`
- `Systematic Debugging`
- `Firecrawl`
- `Codebase Memory MCP`

默认动作：

- 先 benchmark
- 只吸收产品化壳层、工作流拆分、验真机制
- 不直接整包收编

### 3.3 `intel_only`

典型代表：

- `Tavily`
- `GPT Researcher`
- `AutoResearch`

默认动作：

- 只做信号观察
- 不进入接入队列
- 只在确实需要时拿来做对照研究

## 4. 日常优先级

每天真正按这个顺序想就够了：

1. 先判断是不是外部 skill intake。
2. 如果是，先跑 `evaluate-external-skill`。
3. 如果是 docs / method learning，再跑 `guide-benchmark-learning`。
4. 如果是任务拆解，再跑 `task-spec`，`Task Master AI` 只做对照桥。
5. 如果是调试 / 代码定位 / 上下文控制，优先 `Systematic Debugging`、`File Search`、`Context Optimization`。
6. 如果是研究 / 搜索，只把 `Tavily`、`GPT Researcher`、`AutoResearch` 当情报。
7. 如果是 runtime / framework，引擎只留工具层，不进 core。

## 5. 不要再犯的三种误判

1. `包装完整` 误判成 `可直接收编`。
2. `运行时兼容` 误判成 `治理边界兼容`。
3. `很像一个好工具` 误判成 `可以立刻进入 skill core`。

## 6. 一句话记忆

`先评估，再分桶；可安装的不等于可收编；可参考的不等于可接入；看起来像底座的，大多就该留在底座。`

