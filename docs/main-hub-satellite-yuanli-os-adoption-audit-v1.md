# 主机主策略与卫星原力OS吸收审计报告 v1

## 1. 一句话结论

这轮实盘之后，结论可以先定死：

- `main-hub` 继续是唯一 `canonical source`，不做双主。
- `AI大管家` 继续是唯一顶层治理入口，负责总路由、正式闭环、验真和镜像边界。
- `原力OS` 在主机上的真实身份是 `人类外显层 + 治理语言 + 控制台/对象系统`，不是独立二号总控。
- `卫星黑色`、`卫星白色`、`卫星old` 都按卫星处理，只承担采集、执行、登录复用、局部推进，不承担正式闭环。
- 外部分装资产里，最值得吸收的是 `方法核 + 器官化 skill + bridge discipline`；最不该做的是让它们抢 `AI大管家` 的 root 身份。

如果把这份报告压成一句人话，就是：

`你以后继续只跟我工作；我内部会把 AI大管家 当总控，把 原力OS 当人类前台，把 卫星 当前哨，把外部分装 skill 当可插拔器官或 benchmark。`

## 2. 命名与拓扑归一

### 2.1 固定命名

从这轮开始，协作层命名统一成下面这一组：

- `main-hub`
  - 当前主机
  - 唯一正式真相源
  - 唯一正式 closure / evolution / mirror 出口
- `卫星黑色`
  - `satellite execution role`
  - 偏执行、采集、浏览器操作、局部推进
- `卫星白色`
  - `satellite mirror role`
  - 偏镜像、迁移、复用既有大管家资产
- `卫星old`
  - `satellite legacy source role`
  - 偏旧机器、历史资产、登录态或旧流程遗产

### 2.2 和现有治理框架的映射

现有主机-卫星治理文档已经把结构写得很明确：

- `main-hub` 负责真相源、正式主线、治理闭环、策略层和总控。
- 卫星机默认只做 `采集 + 执行`。
- 卫星 thread 是临时前哨，不是长期 canonical 主线。
- 只有 `main-hub` 做正式 closure、evolution、sync。

这说明你现在给三台机器取的人类名，本质上是在给既有治理框架补一层更顺手的协作语言，而不是重设计架构。

### 2.3 当前需要保留的一个边界

当前 `hub-audit-summary` 已经看到：

- `main-hub`
- `satellite-01`
- `satellite-02`

但这份工件也明确提醒了一件事：

`三端来源已接入，不等于三台独立机器已经被完全验真；当前仍可能带有 shadow bootstrap 成分。`

所以这轮报告先固定 `人类别名 -> 治理角色`，不强行固定：

- 不直接默认 `卫星黑色 = satellite-01`
- 不直接默认 `卫星白色 = satellite-02`

目前唯一相对明确的，是旧机器 playbook 已经把“老笔记本”按 `satellite-01` 来设计过。所以：

- `卫星old` 可以安全理解为 `legacy source / old notebook`
- `卫星黑色`、`卫星白色` 的具体 source-id 绑定，后续由主机 onboarding 记录再冻结

这一步不影响你日常协作，因为你只需要说“这是主线”还是“这是卫星执行”。

## 3. 主机当前真实主策略

这部分只采信 `AI大管家 strategy/current` 的 live 工件，不采信口头印象。

### 3.1 三条长期主策略

当前主机上的正式战略目标就是这三条：

- `G1 治理操作系统化`
- `G2 受控自治与提案推进`
- `G3 AI 组织激励系统`

治理仪表盘里对应的最高目标也写得很直白：

`让 AI大管家 从任务路由器进化成战略提案者 + 组织编排者 + 治理审计者。`

### 3.2 这三条策略分别意味着什么

#### `G1 治理操作系统化`

这不是“多写几个 skill”，而是把整套系统升级成可治理的 operating system。  
它的真实含义是：

- 要有统一治理视图
- 要有 strategy/current 这种活工件
- 要有 hub / satellite / canonical / closure 的正式边界
- 要把技能集合变成结构化系统，而不是技能杂货铺

这是主机最值得直接吸收的方法之一。

#### `G2 受控自治与提案推进`

主机当前不是追求“全自动执行”，而是明确选择：

`先做到高质量提案自治，再考虑更深自动执行。`

这条策略非常重要，因为它决定了主机的方法论不是“为了自动而自动”，而是：

- 先判断值不值得做
- 先给出可验真的 route
- 需要人拍板的地方就显式留给人
- 真正收口之后再谈提权

这条是我后续最应该继承的上位协作原则。

#### `G3 AI 组织激励系统`

主机已经把“做成事”升级成“怎样的做成事值得被奖励”。  
当前方向是：

- 奖励治理质量
- 奖励低失真
- 奖励可复用贡献
- 用 routing credit / 验真 / reuse 信号影响未来选择

这不是装饰层，而是 AI 团队化之后必须有的组织机制。

### 3.3 当前活跃线程与历史归档线程

当前 live 工件里，活跃线程集中在：

- 逐字稿治理与日常 review
- 高频工程类 skill hardening
- 原力OS主线治理收口
- AI 训练营/交付包类执行主线

归档线程很多，说明主机已经不是“想法堆”，而是有明确 archive discipline 的系统。

这意味着主机的方法值得吸收的不是某个具体任务，而是这三件事：

- `长期主策略` 和 `当前活跃线程` 分开管理
- 做完的任务会归档，不无限占据当前面板
- 当前优先级由战略目标驱动，而不是由最新一句话驱动

### 3.4 这台主机最值得我直接吸收的方法

我给出四条明确结论：

#### `立即吸收`

- `strategy/current` 作为活真相源，而不是把战略放在静态文档里
- `main-hub + satellite` 的单主多前哨结构
- `proposal-first` 的受控自治逻辑
- `验真 + credit + archive` 三件套联动

#### `条件吸收`

- 更深的 routing credit 提权机制
- 更重的自动推进能力

原因不是方法不对，而是这些能力必须建立在足够多真实闭环数据上，不能先想象后赋权。

#### `不要吸收成误解`

- 不要把“当前已有 `main-hub/satellite-01/satellite-02`”直接理解成“真实三端独立运行已经完全成熟”
- 不要把“有很多活跃资产”理解成“应该增加第二个顶层总控”

## 4. 主机里的 `原力OS` 到底是什么

这部分结论已经很稳，不是推测。

### 4.1 代码和文档的直接定义

`yuanli_os_control.py` 里已经把关系写明了：

- `原力OS 是把 AI大管家 这套治理能力外显成一套人类可理解、可运营、可交接的操作系统语言。`
- `原力OS：对人类展示的系统外壳、概念语言和运营界面。`
- `AI大管家：原力OS 背后的治理引擎，负责路由、约束、验真、闭环和进化。`

Feishu front shell 相关脚本里也能看到一致的表达：

- `原力OS 前台壳已经装好`
- `原力OS · 移动前台首页`
- `原力OS · 继续上次`
- `原力OS · 我的任务`
- `原力OS · 交给 PC 深工`

所以它不是抽象设想，而是已经落成前台壳的系统。

### 4.2 我对它的最终角色判断

`原力OS` 当前更像：

- 人类外显层
- 治理语言
- 控制台/白皮书/说明书/字典组成的对象系统

它当前不像：

- 独立二号业务总控
- 和 `AI大管家` 并列的第二个 root 入口

### 4.3 哪些值得我吸收

#### `立即吸收`

- `白皮书 + 使用说明书 + 字典` 这种人类可交接的外显化三件套
- 把治理能力翻译成人能理解的话语系统
- 把前台首页、继续上次、任务入口这类壳层做成稳定入口

这些东西的价值不是替代治理引擎，而是降低你和系统协作的认知负担。

#### `条件吸收`

- 更系统化的 console surface
- 面向飞书/移动端的持续前台化

这部分不是不能做，而是要继续服从：

- `AI大管家` 负责治理
- `原力OS` 负责展示

### 4.4 哪些不能和 `AI大管家` 重叠

这几层不能重叠，否则就是双总控：

- 顶层 route
- 正式 closure
- canonical truth ownership
- Feishu / GitHub sync policy
- 最终验真权

### 4.5 `business deputy` 应该从哪里长出来

这轮仍然维持之前深盘审计的结论：

`业务 COO / CGO 副手，不该从 原力OS 本体里直接硬拔，而应该从 public / private / sales 模块群里提纯。`

也就是说：

- `原力OS` 继续做人类前台
- `AI大管家` 继续做治理总控
- `business deputy` 作为业务中层能力，从已有业务模块里成长出来

这是更稳的组织结构。

## 5. 外部分装资产四对象审计

这里不把四个对象混成一个词，每个都单独落结论。

### 5.1 `moonstachain/yuanli-os-skills-pack`

#### 它真实是什么

live tree 已经证实，这不是一个 root system，而是一个 `分层分组的技能分装仓`，目前至少包含：

- `content-growth/skills/*`
- `method-organs/skills/*`
- `workflow-bridges/feishu-bitable-bridge`
- `manifest/skills-manifest.lock.json`
- `scripts/install_skills_pack.py`
- `scripts/verify_yuanli_os_skills_pack.py`

它更像：

- 方法器官包
- 内容增长 skill 包
- workflow bridge 包
- 安装/校验分发层

#### 它和 `AI大管家 / 原力OS` 重叠在哪一层

- 和 `AI大管家` 的重叠主要在：器官层、bridge 层、局部 skill 层
- 和 `原力OS` 的重叠主要在：方法语言与器官设计

它不直接重叠顶层治理入口，这一点反而是优点。

#### 最佳接管方式

- `规则吸收`
- `本地镜像`
- `隔离试运行`

不要整包直接并入当前 root stack。

#### 最终结论

`条件吸收`

原因：

- 值得吸收的东西很多，尤其是 `method-organs`
- 但它是“技能分装仓”，不是现在就该整体 install 成主入口的东西
- 需要按需挑器官、逐个验真，再落回本地主机的 canonical 治理里

#### 我建议优先吸收的部分

- `intent-grounding`
- `skill-router`
- `evidence-gate`
- `closure-evolution`
- `jiyao-youyao-haiyao-zaiyao`

这些最像主机当前系统缺的“可独立器官化”部件。

#### 我建议谨慎处理的部分

- `workflow-bridges/feishu-bitable-bridge`

因为主机本地已经有成熟版 `feishu-bitable-bridge`，这里更适合拿来做 benchmark，不适合盲装第二份同名桥。

### 5.2 `moonstachain/yuanli-os-ops`

#### 它真实是什么

live metadata 已证实：

- 仓库是 private
- 描述是：`Private operating-layer bundle for rebuilding OS-原力 across notebooks`

live 顶层 contents 目前已验证到：

- `bootstrap`
- `output`
- `scripts`
- `tools`
- `FORCE-CLAW`

所以它更像：

- notebook 间重建/迁移/启动的 operating layer
- ops / bootstrap / toolchain bundle

#### 它和 `AI大管家 / 原力OS` 重叠在哪一层

- 和 `AI大管家` 的重叠在：多机部署、bootstrap、运维层
- 和 `原力OS` 的重叠在：跨机器重建壳层或运行面

它不该直接进当前活跃 root stack，因为这会和 `main-hub` 的正式治理面打架。

#### 最佳接管方式

- `隔离试运行`
- `不进入当前活跃 root stack`

#### 最终结论

`仅作 benchmark`

原因：

- 目前 live inspection 只核到了 repo metadata 和顶层 contents
- 还没有完成递归树和 README 级别的深验真
- 它很像 notebook rebuild / bootstrap bundle，不该在当前主机上直接抢运行层入口

#### 现阶段最适合怎么用

- 当跨笔记本迁移/重建时，用它校验操作层缺口
- 当你要新增卫星或重装卫星时，把它当 `ops benchmark`
- 不要把它装成 `AI大管家` 之上的新根入口

### 5.3 `os-yuanli` 根 protocol benchmark

#### 它真实是什么

本地 benchmark mirror 已经很明确：

- 它自称 `standalone root skill`
- 走 `治理OS × 工作OS`
- 先过 `六判断`
- 再过 `主题层 / 策略层 / 执行层`
- 做完必须 `验真 + Evolution Note`

但它的 `integration-boundaries` 也同时明确说了：

- `AI大管家` 拥有 inventory、top-level route、local canonical closure、Feishu/GitHub sync policy
- `os-yuanli` 拥有方法内核、任务族适配、theme / strategy / execution gates

#### 它和 `AI大管家 / 原力OS` 重叠在哪一层

- 和 `AI大管家` 重叠的是 root-level 话语和方法总控语义
- 和 `原力OS` 重叠的是治理语言和方法表达

但它自己已经把关键 ownership 让给了 `AI大管家`，这反而说明它最好的位置不是抢位，而是做内核 benchmark。

#### 最佳接管方式

- `规则吸收`
- `本地镜像`
- `不进入当前活跃 root stack`

#### 最终结论

`仅作 benchmark`

这条结论和现有 `AI大管家` 外部 skill 评估结果一致：

- `category = intel_only`
- `can_use_now = no`
- `best_use_mode = research_only`

也就是说，它现在最适合：

- 做 `COO 方法内核 benchmark`
- 做 `治理OS × 工作OS` 的压缩宪法来源
- 做任务族 artifact pack 设计参考

不适合：

- 直接替代 `AI大管家`
- 直接升级成当前系统主入口

### 5.4 `os-yuanli` 器官型 skill bundle

#### 它真实是什么

从 `os-yuanli` mirror 和 `yuanli-os-skills-pack` live tree 合起来看，器官层已经相当明确：

- `intent-grounding`
- `skill-router`
- `evidence-gate`
- `closure-evolution`
- `jiyao-youyao-haiyao-zaiyao`

这些都不是外壳，而是能被系统编排的治理器官。

#### 它和 `AI大管家 / 原力OS` 重叠在哪一层

- 和 `AI大管家` 重叠在：局部 route、验真、进化、意图压缩
- 和 `原力OS` 重叠在：方法语言和治理节奏

这类重叠是可控的，因为它们不是总入口，而是中间器官。

#### 最佳接管方式

- `规则吸收`
- `本地镜像`
- `隔离试运行`

#### 最终结论

`条件吸收`

原因：

- 这些器官最有机会变成主机的左膀右臂
- 但要先完成接口对齐、命名去重、验真闭环
- 当前还不适合一口气全量激活

#### 吸收顺序建议

优先级从高到低：

1. `intent-grounding`
2. `skill-router`
3. `evidence-gate`
4. `closure-evolution`
5. `jiyao-youyao-haiyao-zaiyao` 的反思模板部分

这样做能先把主机最缺的中层能力补上，再考虑更完整的 protocol 化。

## 6. 吸收梯度总表

### 6.1 四对象最终分层

- `yuanli-os-skills-pack`
  - 结论：`条件吸收`
  - 主接法：`规则吸收 + 本地镜像 + 逐个隔离试运行`
- `yuanli-os-ops`
  - 结论：`仅作 benchmark`
  - 主接法：`ops benchmark + 不进入当前活跃 root stack`
- `os-yuanli` 根 protocol benchmark
  - 结论：`仅作 benchmark`
  - 主接法：`方法宪法参考 + 本地镜像，不抢 root`
- `os-yuanli` 器官型 skill bundle
  - 结论：`条件吸收`
  - 主接法：`器官化落地 + 本地命名对齐 + 隔离试运行`

### 6.2 这轮最值得立刻拿过来的东西

如果只讲“这周就值得拿过来消化”的内容，我会优先拿这五类：

- `六判断先行`
- `主题层 / 策略层 / 执行层` 的 gate discipline
- `intent-grounding`
- `evidence-gate`
- `closure-evolution`

这五类能直接增强当前主机，而不会制造双总控。

## 7. 以后你只跟我工作时，我内部怎么调用这些能力

这章只讲人类协作接口，不讲机器内部细节。

### 7.1 你对外只需要记住四种说法

以后你只需要说下面这几种话，我内部会自己分流：

- `这是主线`
- `这是卫星执行`
- `这是原力OS话语`
- `这是业务副手问题`

### 7.2 我内部的默认分流

#### 你说 `这是主线`

我会走：

- `AI大管家`
- `main-hub`
- 正式 canonical 记账
- 正式 closure / evolution / mirror 边界

#### 你说 `这是卫星执行`

我会走：

- `卫星黑色` 或 `卫星白色` 或 `卫星old` 的前哨角色
- 采集、浏览器操作、局部推进
- 做完后回收到 `main-hub`

#### 你说 `这是原力OS话语`

我会做的是：

- 用 `原力OS` 的前台语言和对象系统跟你对齐
- 让输出更像“操作系统界面”和“可交接说明”

但内部治理总控仍由 `AI大管家` 承担。

#### 你说 `这是业务副手问题`

我会优先走：

- `public`
- `private`
- `sales`

三模块群提纯出来的 `business deputy` 路由。

必要时，我会再借：

- `os-yuanli` 的方法核
- `yuanli-os-skills-pack` 的器官 skill

但这些都在内部消化，不要求你切换入口。

### 7.3 哪些层对你可见，哪些层我内部消化

#### 对你可见

- 当前这是主线还是卫星任务
- 当前下一步是什么
- 哪些地方需要你拍板
- 当前是不是已经真闭环

#### 我内部消化

- 选哪个器官 skill
- 是否调用外部分装资产
- 是否把某个外部仓只当 benchmark
- 是否从卫星回收进主机
- 是否触发验真或进化写回

这就是你以后“继续只和我工作”时，最省力的协作方式。

## 8. 风险与不要做的事

### 8.1 当前明确不要做的事

- 不要把 `原力OS` 直接升格为独立二号总控
- 不要把 `yuanli-os-skills-pack` 整包直接装成主入口
- 不要让 `yuanli-os-ops` 抢当前主机的运行层根身份
- 不要把卫星机上的局部推进误判成正式闭环

### 8.2 当前仍保留的 live-inspection 缺口

- `yuanli-os-ops` 目前只做了 repo metadata 和顶层 contents 级 live 核验，未完成更深递归树核验
- `卫星黑色`、`卫星白色` 和 `satellite-01/02` 的精确绑定还没被主机 onboarding 元数据正式冻结
- hub audit 已接入三端，但仍需继续区分真实独立三机与 shadow bootstrap

这些缺口不会推翻本轮结论，但值得在后续纳管时补齐。

## 9. 最终角色建议

最后把结构再压缩成一句正式建议：

- `AI大管家`：唯一顶层治理入口
- `原力OS`：人类外显层
- `卫星黑色 / 卫星白色 / 卫星old`：卫星前哨
- `business deputy`：从 `public / private / sales` 模块群提纯
- `外部分装资产`：被我吸收、编排、按需调用的下层能力，不直接要求你切换入口

所以这轮最核心的判断不是“要不要接管这些资产”，而是：

`要接，但要按层接；要吸收，但不抢根；要复用，但不制造双主和双总控。`

## 10. 验真依据

本报告主要基于以下实证层：

- `AI大管家 strategy/current`
  - `strategic-goals.json`
  - `governance-dashboard.md`
  - `active-threads.json`
  - `hub-audit-summary.json`
- 主机本地 `原力OS`
  - `yuanli_governance/yuanli_os_control.py`
  - `scripts/feishu_claw_bridge.py`
- 既有本地审计文档
  - `docs/black-mac-yuanli-os-deep-audit-v1.md`
  - `docs/ai-da-guan-jia-host-satellite-collaboration-v1.md`
  - `docs/remote-satellite-onboarding-playbook.md`
  - `docs/os-yuanli-benchmark-audit-v1.md`
- `os-yuanli` benchmark mirror
  - `tmp/external-repos/os-yuanli/SKILL.md`
  - `tmp/external-repos/os-yuanli/references/integration-boundaries.md`
- GitHub live metadata / tree
  - `moonstachain/yuanli-os-skills-pack`
  - `moonstachain/yuanli-os-ops`

这意味着本轮不是纯口头报告，而是：

`本地主机 live 工件 + 本地 benchmark mirror + GitHub live metadata` 三层交叉之后给出的 adoption 审计结论。
