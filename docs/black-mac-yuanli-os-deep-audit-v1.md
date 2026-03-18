# 黑色笔记本 原力OS 深盘审计与吸收报告 v1

## Summary

这次盘点确认了三件大事：

1. 当前就是你说的“黑色笔记本”。
   - 主机：`limingdeMacBook-Pro.local`
   - 用户：`liming`
   - 工作区：`/Users/liming/Documents/codex-ai-gua-jia-01`
2. `AI大管家` 在这台机器上已经是明确的 `1号位治理引擎`，但它当前的真实 `execute` 权限并没有无限扩张，而是被 capability 和 human approval 明确收住了。
3. `原力OS` 在黑色笔记本上的真实定位不是“独立的二号业务 Agent”，而是 `人类外显层 + 治理语言 + 控制台对象系统`。真正能长成 `COO / CGO / 业务增长副手` 的种子，当前更像是 `公域 / 私域 / 销售` 三个业务 copilot 模块的组合，而不是 `原力OS` 本体。

一句话结论：

`值得大幅借鉴，但不该把原力OS直接误升为单体二号位；更合理的吸收方式，是保持 AI大管家 为 1 号位治理引擎，保持 原力OS 为人类外显层，再从 public/private/sales 模块群里提纯出 business deputy。`

## 六个治理判断

- `自治判断`：黑色笔记本上大部分 Codex、AI大管家、原力OS、GitHub、Chrome、Feishu Reader、Get笔记 资产已可直接实盘；本轮没有被真正的 macOS 权限墙拦在关键路径上。
- `全局最优判断`：先以黑色笔记本本地 `canonical/entities`、`.codex`、skills state、browser profile 为真相源，比先看 GitHub 镜像或口头记忆更稳。
- `能力复用判断`：现成可复用的骨架已经很强，包括 `ai-da-guan-jia`、`yuanli_governance`、`canonical` 对象模型、`os-yuanli benchmark audit`，不需要发明第二套审计体系。
- `验真判断`：权限、角色、外部接线至少要满足 “本地配置 / canonical contracts / 实际状态落位” 三类证据中的两类，才算真落位。
- `进化判断`：后续吸收应该按 `立即吸收 / 条件吸收 / 不要吸收` 三层推进，而不是一口气把原力OS提升成二号位。
- `当前最大失真`：把“原力OS 这个外壳和对象系统已经很完整”误判成“二号业务生命体已经完整成型”。

## 1. 黑色笔记本当前真相源

### 1.1 机器与 Codex 根资产

当前机器上的 `Codex` 不是空壳，而是重度使用中的主环境。

- `.codex` 根目录存在且活跃
- skills 目录存在，共 `110` 个本地 skill 目录
- automations 目录存在，共 `10` 个 automation
- `state_5.sqlite` 存在，约 `551 MB`
- `logs_1.sqlite` 存在，约 `60 MB`
- `session_index.jsonl`、`models_cache.json`、`sessions/`、`archived_sessions/`、`shell_snapshots/` 均存在
- `.codex/config.toml` 已配置：
  - `context7` MCP
  - `github` MCP
  - `chrome-devtools` MCP 已声明但当前 `enabled = false`
- `.codex/auth.json` 已存在，键层面可见：
  - `OPENAI_API_KEY`
  - `auth_mode`
  - `last_refresh`
  - `tokens`

这说明黑色笔记本上的 Codex 已经具备：

- 主模型接线
- MCP 接线
- 长期会话状态
- 自动化与技能系统

### 1.2 Workspace 与 canonical 真相源

工作区 `codex-ai-gua-jia-01` 内，`canonical` 已经是明确的结构化真相源，而不是零散文档堆。

已落位的 canonical 实体包含：

- `accounts.json`
- `actions.json`
- `agent_capabilities.json`
- `assets.json`
- `cashflows.json`
- `decision_records.json`
- `endpoints.json`
- `ingestion_runs.json`
- `knowledge_items.json`
- `knowledge_sources.json`
- `operating_modules.json`
- `orders.json`
- `review_runs.json`
- `skills.json`
- `source_feeds.json`
- `spaces.json`
- `subjects.json`
- `tasks.json`
- `threads.json`
- `writeback_events.json`
- `relations.json`

这说明原力OS在黑色笔记本上，已经不是“只有概念文件”，而是已经具备：

- 对象层
- 关系层
- schema 层
- snapshot 层
- derived report 层

### 1.3 外部接线与状态落位

#### GitHub

- `gh auth status` 已确认登录到 `moonstachain`
- 当前 scope 至少包括：
  - `repo`
  - `read:org`
  - `gist`
- `.config/gh/hosts.yml` 存在
- 这意味着 GitHub 在黑色笔记本上不是“理论可用”，而是 `真实已登录`

#### Chrome / 浏览器态

- 系统级 Chrome 用户数据目录存在：`~/Library/Application Support/Google/Chrome`
- skill 级 profile 已落位：
  - `feishu-reader/state/browser-profile/feishu-reader`
  - `get-biji-transcript/state/browser-profile/get-biji`

这说明浏览器型 skill 在这台机器上的真实策略是：

- `Web-first`
- `profile reuse`
- `skill-specific persistent session`

而不是桌面客户端优先。

#### Feishu

实盘状态是 `浏览器态较强，桌面态证据弱`。

- canonical 中 `Feishu 主账号` 已存在，状态标为 `active / healthy`
- `feishu-reader` 专属 profile 已存在
- 但桌面客户端路径：
  - `~/Library/Application Support/feishu`
  - `~/Library/Application Support/LarkShell`
  当前都不存在

所以黑色笔记本上的 Feishu 更像：

- `Web / browser session first`
- 不是 `desktop app first`

#### Get笔记

Get笔记在黑色笔记本上的接线比 Feishu 更扎实。

- `get-biji` skill 专属浏览器 profile 已存在
- `ai-da-guan-jia/state/get-biji.env` 已存在
- 只看键名，已绑定：
  - `GET_BIJI_API_KEY`
  - `GET_BIJI_TOPIC_ID`
  - `GET_BIJI_BASE_URL`
  - `GET_BIJI_TIMEOUT_SECONDS`

这说明 Get笔记同时具备：

- `API 路`
- `Browser 路`

#### OpenClaw

- `~/.openclaw-autoclaw` 当前不存在

所以在黑色笔记本上，OpenClaw 当前不是活动底座，而是 `缺席态 / 未落位态`。

### 1.4 macOS 权限墙真实情况

本轮大范围探测时，确实撞到了 Apple 受保护目录的 `Operation not permitted`，包括：

- Mail
- Messages
- Safari
- Photos
- Cookies
- 诸多 `Library/Group Containers`

但这些都不在本轮核心审计范围内。

所以更准确的判断是：

- `系统深盘存在 TCC 墙`
- `当前 Codex / AI大管家 / 原力OS 审计主线没有被它卡死`

也就是说，本轮没有形成“必须立刻让你去点授权”的真阻塞。

## 2. AI大管家 1号位权限账本

## 2.1 文档宣称的 1号位职责

从 `SKILL.md` 和协作文档看，AI大管家的宣称职责非常明确：

- 顶层治理者
- 本地 skill 系统总路由
- 最小充分 skill 组合选择器
- canonical log 优先
- Feishu / GitHub 只做 mirror
- 少打扰推进
- 真验真、真闭环、真进化

这套话语已经明显是 `1号位`，不是普通执行 skill。

## 2.2 黑色笔记本上真实落位的 1号位能力

黑色笔记本上的本地脚本与 canonical 数据进一步验证了这件事。

### 脚本侧

`ai_da_guan_jia.py` 的核心 profile 把它定义成：

- `Govern the local skill system`
- `route to the smallest sufficient combination`
- `close the loop with review and evolution artifacts`

同时它在 profile 层的强度是：

- `verification_strength = 5`
- `cost_efficiency = 4`
- `auth_reuse = 2`
- `complexity_penalty = 1`

### canonical 侧

`canonical/entities/skills.json` 中：

- `ai-da-guan-jia`
  - cluster：`AI大管家治理簇`
  - role：`Govern`
  - routing_credit：`77.8`
  - status：`active`

`canonical/relations/relations.json` 中：

- `ai-da-guan-jia -> subject-agent-governance`
  - relation：`skill_enables_agent`

这说明黑色笔记本上，AI大管家不只是“文档写自己是总控”，而是已经在对象系统里被当作：

- 治理引擎
- 治理 Agent 的主 enablement skill

## 2.3 真实权限边界

这是本轮最关键的发现之一：

`AI大管家 已经是 1号位，但它当前真实 execute 权限是受限的，不是无限制总执行者。`

当前 `agent_capabilities.json` 只确认了 3 个明确 capability：

1. `技能治理评审提案`
   - action：`review-skill`
   - `requires_human_approval = false`
2. `技能治理决议草拟`
   - action：`resolve-action`
   - `requires_human_approval = true`
3. `治理报告发布执行`
   - action：`publish-governance-report`
   - `requires_human_approval = true`

对应 `actions.json` 也明确了 writeback target 和 policy boundary。

这意味着：

- AI大管家 当前已经有 `read / propose`
- 有部分 `execute`
- 但 `execute` 主要聚焦在 `治理 review / 决议草拟 / 治理报告发布`
- 高风险动作仍被 `human approval` 收住

## 2.4 文档宣称 vs 黑色笔记本真实落位

### 一致的部分

- 顶层治理身份：一致
- local canonical 优先：一致
- 少打扰和 human boundary：一致
- 只在登录/授权/付款/不可逆动作时打断：一致
- Feishu/GitHub 是 mirror 不是真源：一致

### 不一致或仍未完全展开的部分

- 文档层看起来像“AI大管家几乎能统领全场”
- 真实 capability 层则显示：
  - 它的 `governance execute` 很清楚
  - 但它还没有被正式授予 “通吃所有业务模块” 的统一执行权限

这不是缺点，反而是成熟度信号：

`它已经是一号位，但不是乱提权的一号位。`

## 2.5 当前 1号位的真实风险

最大的风险不是权力太大，而是：

`治理语义已经很强，但 canonical 对 skill 世界的映射还不够全。`

实盘发现：

- `.codex/skills` 本地实际有 `110` 个 skill
- canonical `skills.json` 当前只镜像了 `3` 个：
  - `ai-da-guan-jia`
  - `knowledge-orchestrator`
  - `yuanli-core`

这意味着：

- 黑色笔记本上真实技能宇宙很大
- 但 canonical 里只进入了“核心少数”
- 所以 AI大管家 的治理骨架很强
- 但对整个 skill 生态的结构化表达，还没有完全收口

这会直接影响你后面要做的 `2号位 / 业务副手` 正式编制化。

## 3. 原力OS 与 2号位关系判断

## 3.1 原力OS 当前真实定位

黑色笔记本上的 `yuanli_os_control.py`、白皮书、使用说明书、字段字典已经把原力OS定位写得非常直白：

- 原力OS：`对人类展示的系统外壳、概念语言和运营界面`
- AI大管家：`原力OS 背后的治理引擎`
- 人类：`共同治理者`

并且白皮书还明确写了：

- AI 默认 `read/propose`
- 只有 capability 绑定后才 `execute`
- `human_owner` 拥有 `read/propose/execute/approve` 全权限

所以：

`原力OS 当前更像壳层与语义层，不像已经独立封装好的单体二号业务 Agent。`

## 3.2 黑色笔记本上真正的“副手胚胎”在哪

canonical `subjects.json` 已经定义了 6 个 AI copilot：

- `subject-agent-public`：公域增长 Agent
- `subject-agent-private`：私域转化 Agent
- `subject-agent-sales`：销售 Agent
- `subject-agent-delivery`：交付 Agent
- `subject-agent-finance`：财务 Agent
- `subject-agent-governance`：治理 Agent

同时 `operating_modules.json` 也一一对上：

- `module-public`
- `module-private`
- `module-sales`
- `module-delivery`
- `module-finance`
- `module-governance`

关系层也已经把这些 copilot 与模块绑上了：

- `subject-agent-public -> module-public`
- `subject-agent-private -> module-private`
- `subject-agent-sales -> module-sales`
- `subject-agent-delivery -> module-delivery`
- `subject-agent-finance -> module-finance`
- `subject-agent-governance -> module-governance`

这说明黑色笔记本上真正长出“二号位胚胎”的，不是 `原力OS` 本体，而是：

`业务模块层的 copilot 群。`

## 3.3 现有技能映射说明了什么

`contracts.py` 已经给出了一版模块到 skill 的 hint：

- 治理 Agent：
  - `ai-da-guan-jia`
  - `knowledge-orchestrator`
- 公域增长 Agent：
  - `yuanli-core`
  - `yuanli-xiaoshitou`
  - `openclaw-xhs-coevolution-lab`
- 私域转化 Agent：
  - `knowledge-orchestrator`
  - `feishu-bitable-bridge`
- 销售 Agent：
  - `knowledge-orchestrator`
  - `agency-data-consolidation-agent`
- 交付 Agent：
  - `yuanli-core`
  - `yuanli-zsxq-coevolution-assistant`
- 财务 Agent：
  - `agency-support-finance-tracker`

这里最有价值的地方是：

- 它已经把“业务副手”拆成了模块群，而不是一个模糊 super-agent
- 这非常适合你后面要做的 `COO / CGO` 吸收工作

## 3.4 为什么原力OS不该被直接升格为二号位

原因有四个：

1. 它的白皮书定位是外显层，不是单体业务执行体。
2. AI大管家已经占了顶层治理引擎位，如果再把原力OS单独提升成二号总入口，会形成双总控。
3. 现在真正可执行的业务种子，已经以 `public/private/sales/delivery/finance` 的模块形式存在。
4. 任务层还没有真正把这些模块绑实。

这里还有一个非常关键的实盘信号：

`canonical/entities/tasks.json` 当前有 5 条任务，但它们的 module_code / owner_subject_id / ai_subject_id 都还是空的。`

这说明：

- 角色架构已经设计出来了
- 但任务调度还没有真正压到这些 business agent 身上

所以现在最合理的动作不是“把原力OS提成二号位”，而是：

`把 business deputy 从 public/private/sales 模块群里提纯出来，并把 tasks 正式绑定过去。`

## 3.5 COO / CGO 的更合理提纯路径

如果你想做的是 `业务、业绩、增长、销售、转化` 这条二号位，黑色笔记本上最合理的提纯方式是：

### `CGO kernel`

由下面三层组成：

- `subject-agent-public`
- `subject-agent-private`
- `subject-agent-sales`

它负责：

- 流量入口
- 线索转化
- 商机推进

### `COO extension`

在需要扩到经营闭环时，再挂上：

- `subject-agent-delivery`
- `subject-agent-finance`

它负责：

- 交付节奏
- 回款与利润

### 最终结构

- `AI大管家`：1号位治理引擎
- `原力OS`：人类外显层
- `business deputy / growth-ops deputy`：二号位业务副手

也就是说：

`二号位应该从业务模块群中提纯，而不是从原力OS外壳里直接硬拔。`

## 4. 外部接线与登录态复用表

| 项目 | 黑色笔记本真实状态 | 复用判断 | 风险 |
| --- | --- | --- | --- |
| Codex auth | `.codex/auth.json` 已存在，含 OpenAI auth 结构 | 可复用 | 不应在报告中回显密钥正文 |
| Codex config | `context7` / `github` MCP 已启用，`chrome-devtools` 已声明但关闭 | 可复用 | 浏览器 MCP 不是当前默认主路 |
| GitHub CLI | 已登录 `moonstachain`，scope 含 `repo/read:org/gist` | 强复用 | 仍需避免在产物中暴露 token 正文 |
| Chrome base profile | 系统级 Chrome profile 已存在 | 强复用 | profile 多，需避免误用错误 profile |
| Feishu Reader profile | skill 专属 profile 已存在 | 可复用 | 更像 web-first，不是桌面 app first |
| Get笔记 profile | skill 专属 profile 已存在 | 强复用 | 依赖浏览器稳定性与登录态延续 |
| Get笔记 env | API 配置键已存在 | 可复用 | 仍需对真实 API 成功率做单独验真 |
| Feishu desktop app | 桌面 app 路径缺失 | 不作为主复用面 | 当前不能按“桌面客户端落位”判断 |
| OpenClaw home | 缺失 | 不可复用 | 黑色笔记本当前没有 OpenClaw 主底座 |

## 4.1 自动化层的真实情况

`.codex/automations` 当前共有 `10` 个 automation，其中已经能看到重复影子：

- `Transcript 9am` 有两份
- `Transcript 1pm` 有两份
- `Transcript 7pm` 有两份
- `GitHub skill scout brief` 有两份

这不是系统性故障，但它是一个值得写进风险栏的治理信号：

`自动化已经在用，但自动化治理还没完全去重。`

## 5. 借鉴点与吸收方案

## 5.1 立即吸收

### 1. 业务模块拆分

黑色笔记本当前最值得直接借鉴的是：

- 公域
- 私域
- 销售
- 交付
- 财务
- 治理

这套六模块拆分已经比“一个大而全二号位”成熟得多。

建议：

- 保留这六模块结构
- 其中先把 `public/private/sales` 提纯成 business deputy 主体

### 2. Capability-gated 权限模型

当前 capability/action/policy 的组合非常值得直接吸收：

- 先给 `read/propose`
- 再按 capability 开 `execute`
- 高风险动作明确 `requires_human_approval`

这比“先造一个很厉害的二号位，再慢慢收权”要安全得多。

### 3. 原力OS 外显化做法

白皮书 / 使用说明书 / 对象与字段字典 这三件套，说明黑色笔记本上的原力OS已经形成：

- 对人类可解释
- 可交接
- 可运营

这非常值得保留。

真正要吸收的不是“原力OS 当二号位”，而是：

`用原力OS继续做人类前台与概念壳。`

### 4. Browser-first 集成方法

黑色笔记本上的 Feishu / Get笔记 都明显是：

- 浏览器态优先
- persistent profile 复用

这比强依赖桌面 app 更稳，也更适合 Codex skill 体系。

### 5. 审计与 benchmark 文档化

黑色笔记本上已有：

- `os-yuanli-benchmark-audit-v1`
- `yuanli-os-task-audit-v1`
- 协作与治理 memo

这说明“盘点 -> 判断 -> adoption ladder” 已经是一种成熟工作法，值得继续复用。

## 5.2 条件吸收

### 1. 正式建立 business deputy

建议不是立刻把原力OS提为二号位，而是新增一个明确 subject：

- `subject-agent-business-deputy`
  或
- `subject-agent-growth-ops`

它的上游来源：

- `subject-agent-public`
- `subject-agent-private`
- `subject-agent-sales`

它的扩展接口：

- delivery
- finance

### 2. 扩 canonical skill inventory

当前本地技能 `110` 个，但 canonical 只有 `3` 个 skill 镜像，明显过窄。

如果你真的要让二号位长期运作，至少要把业务副手相关的关键 skill 纳入 canonical：

- `yuanli-xiaoshitou`
- `openclaw-xhs-coevolution-lab`
- `feishu-bitable-bridge`
- `agency-data-consolidation-agent`
- `agency-support-finance-tracker`
- `yuanli-zsxq-coevolution-assistant`

### 3. 把 tasks 正式绑模块和 agent

这是当前最该补的动作之一。

没有这一步，二号位永远只是概念角色，不是真正运行角色。

至少要让任务开始写明：

- `module_code`
- `owner_subject_id`
- `ai_subject_id`

### 4. 对 Feishu / Get笔记 再做 runtime 验真

当前证据已经足够证明“它们在黑色笔记本上有落位”，
但如果要进一步承担业务副手链路，仍建议单独做一轮：

- 登录态有效性
- 页面可进入性
- 关键 skill smoke test

## 5.3 不要吸收

### 1. 不要把原力OS直接升成单体二号位

因为它本质还是：

- 壳层
- 语言层
- 控制台层

不是现成单体业务执行体。

### 2. 不要造双总控

不要让：

- `AI大管家`
- `原力OS`
- `二号业务副手`

三者都争“谁是总入口”。

正确结构应该是：

- AI大管家：总治理
- 原力OS：人类外显层
- business deputy：业务执行副手

### 3. 不要把 canonical 中的 planned 项误当 active runtime

黑色笔记本上有些 account / endpoint 在 canonical 里是 `planned` 或 `needs_inventory`。

它们可以说明方向，但不能当成“已经真实跑起来”。

### 4. 不要在 OpenClaw 缺席时，把它假定成现役底座

黑色笔记本上 `~/.openclaw-autoclaw` 缺失，这是硬事实。

所以任何涉及 OpenClaw 的业务副手设计，目前都只能算：

- 候选扩展
- 不是当前主底座

## 6. 风险与不要做的事

## 6.1 当前主要风险

### 风险 1：对象系统比任务系统更成熟

现在：

- space / subject / module / capability 很清楚
- 但 task 还没真正挂到这些结构上

这会让系统看起来已经很成熟，但运行层还没有完全吃到结构收益。

### 风险 2：canonical 技能镜像过窄

`110` 个本地 skill 对 `3` 个 canonical skill，是明显的不对称。

如果不补这一步，后面一谈“二号位调用谁”，很容易回到口头判断。

### 风险 3：自动化重复

重复 automation 说明节奏系统已经开始长出来，但去重和治理还没完全做好。

### 风险 4：Feishu 健康是“web-first 健康”，不是“desktop-first 健康”

这本身没问题，但如果后续有人默认它依赖桌面客户端，会产生误判。

## 6.2 现在不要做的事

1. 不要让原力OS直接承担二号位业务副手身份。
2. 不要让 AI大管家 和 二号位同时做 root router。
3. 不要在 tasks 还没绑定 module/agent 前，就宣布二号位已经成型。
4. 不要把 planned account/channel 当成现役业务通道。

## 7. 最终角色建议

### 最终建议一

`AI大管家 继续保持 1号位治理引擎。`

原因：

- 顶层路由已成立
- human boundary 已成立
- capability-gated execute 已成立
- canonical-first 闭环已成立

### 最终建议二

`原力OS 继续保持人类外显层。`

原因：

- 它已经有白皮书、使用说明书、字段字典、控制台语义
- 这正是壳层该做的事

### 最终建议三

`业务 COO / CGO 副手，不从原力OS本体里硬拔，而从 public/private/sales 模块群里提纯。`

推荐结构：

- `CGO kernel`
  - public
  - private
  - sales
- `COO extension`
  - delivery
  - finance

### 最终建议四

真正值得借鉴的，不是“把原力OS整体搬过来当 2号位”，而是借它的 4 个层次：

1. 人类外显层语言
2. 六模块业务拆分
3. capability/policy 权限模型
4. benchmark-audit 工作法

## 8. Stop Condition

在下面这些事实仍成立时，不应把原力OS直接定名为二号位：

1. 原力OS 的白皮书定位仍是外显层
2. AI大管家 仍是治理引擎
3. tasks 仍未正式绑定 module_code / ai_subject_id
4. business deputy 还没有作为独立 subject 正式编制化

## 9. 本轮验真

本轮使用了三类证据交叉验真：

- `本地配置`
  - `.codex/auth.json`
  - `.codex/config.toml`
  - `.config/gh`
  - browser profiles
  - `get-biji.env`
- `canonical contracts`
  - `subjects.json`
  - `operating_modules.json`
  - `agent_capabilities.json`
  - `actions.json`
  - `relations.json`
  - `contracts.py`
- `运行落位`
  - 当前主机 / 当前用户 / 当前工作区
  - active GitHub auth
  - active Chrome/profile roots
  - actual automation presence
  - actual OpenClaw absence

本轮因此可以认为：

- `AI大管家 = 治理引擎` 已被验证
- `原力OS = 外显层` 已被验证
- `业务副手 = 仍在模块 copilot 阶段，尚未正式提纯为单一 subject` 已被验证
