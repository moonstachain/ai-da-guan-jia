# AI大管家全合作史双语进化路线图 v1

## 1. 导言

这不是一份普通项目复盘，而是一份 `AI大管家` 从“会执行的 AI 协作者”逐步长成“会路由、会验真、会闭环、会进化的治理内核”的成长史。

这份文档有两个固定目标：

- 把 `AI大管家` 的真实技术进化路径写清楚，不靠印象，不把 GitHub 当成事实本体。
- 把同一条技术进化路径翻译成一套人能直接理解的协作语言，解释你到底在和一个怎样变化中的系统合作。

这份文档只服务两个对象：

- 你本人，作为长期共同治理者，回看“我们是怎么走到这里的”。
- 未来协作者，快速理解 `AI大管家` 不是功能堆，而是一套逐步器官化的治理系统。

先把两个总边界写死：

- `本地 canonical 是事实源。`
- `GitHub 是协作镜像层，开始稳定可追溯于 2026-03-13。`

## 2. 证据方法

### 2.1 证据分层

本路线图按 4 层证据模型写作，优先级从高到低固定如下：

| 层级 | 名称 | 说明 | 本文用途 |
| --- | --- | --- | --- |
| `L1` | 本地 canonical | `/Users/liming/.codex/skills/ai-da-guan-jia/artifacts/ai-da-guan-jia/runs/*`、`strategy/current/*`、`soul/*` | 用于确定最早起点、真实运行方式、活的战略对象 |
| `L2` | 本地代码/文档 | 当前仓库 `docs/*`、`scripts/*`、git commit 历史 | 用于确定阶段转向、对象模型、底盘器官化 |
| `L3` | GitHub 镜像 | `moonstachain/ai-task-ops` issue 记录 | 用于确定协作镜像何时制度化、何时可公开追溯 |
| `L4` | 解释性推断 | 只在证据不足时使用 | 用于连接断层，但必须标注 `高可信推断` 或 `待补证` |

### 2.2 方法纪律

本文严格遵守 5 条写作纪律：

1. 先取证，再下结论。
2. 不把任务数量等同于能力成熟度。
3. 不把飞书、多维表、妙搭、GitHub 页面等镜像面误当系统本体。
4. 不把“已经提出”误写成“已经做到”。
5. 所有关键断点都用绝对日期表示，不用“前几天”“后来”这种模糊时间。

### 2.3 当前可确认的两个时间边界

- 当前最早可验证起点：`2026-03-09`
  - 证据来自最早的本地 `route.json` 与 `situation-map.md`。
- GitHub 镜像开始稳定可见：`2026-03-13`
  - 证据来自 `moonstachain/ai-task-ops` issue 列表中最早成批出现的 `ai-da-guan-jia-task` 镜像记录。

换句话说，这条全合作史必须分成两段：

- `GitHub 前史`：系统已经在本地 canonical 层开始长出治理纪律，但还没有稳定的 GitHub 外显痕迹。
- `GitHub 可追溯期`：系统开始把任务、镜像、治理、归档外显到 GitHub，便于跨人和跨机器追溯。

## 3. 双语言词典

### 3.1 固定术语对照

| 机器语言 | 人力语言 |
| --- | --- |
| `route` | 先判断这件事该不该做、怎么做、用什么最省失真 |
| `verify` | 不是命令跑完，而是真的成立 |
| `closure` | 做完后要有正式收口，不能停在“差不多” |
| `evolution` | 这次经验会沉淀成下一次能力 |
| `mirror` | 同步到 GitHub/飞书的是协作表层，不是事实本体 |
| `proposal autonomy` | 会提案，但不越权替你拍板 |
| `canonical` | 真相源、本体层、本地正式记录 |
| `strategy/current` | 系统当前正在活着运转的战略真相，而不是静态 PPT |
| `goal / initiative / thread / scorecard` | 从“做一件事”升级成“按目标、项目、线程、评分治理整个系统” |

### 3.2 两套语言的使用边界

- `机器语言轨`
  - 写对象、机制、接口、证据、约束、边界。
- `人力语言轨`
  - 写用户感受、协作变化、能力升级、为什么更值得信任。

如果只写机器语言，这会变成工程档案；如果只写人力语言，这会变成回忆录。  
`AI大管家` 的真实路线必须两条同时成立。

## 4. 阶段总览

| 阶段 | 时间 | 核心判断 | 代表性变化 |
| --- | --- | --- | --- |
| `阶段 1 前史起点期` | `2026-03-09` | 本地 canonical 先于外部镜像成立 | 六判断、situation map、canonical 优先级出现 |
| `阶段 2 闭环原型期` | `2026-03-09` | 路由、飞书、复盘开始被放入同一闭环语义 | 从“做任务”转向“带进化收口做任务” |
| `阶段 3 高密度器官生长期` | `2026-03-10 ~ 2026-03-11` | 系统不是在加功能，而是在长器官 | route / sync / close-task / strategy/current 同时成形 |
| `阶段 4 镜像制度化期` | `2026-03-13` 起 | GitHub 成为协作镜像而不是随手归档 | 任务命名、分类、issue 镜像、归档边界稳定 |
| `阶段 5 战略分层期` | `2026-03-14 ~ 2026-03-15` | 从线程治理升级成目标治理 | `G1 / G2 / G3`、`I-*`、提案自治路线图、成熟版路线图形成 |
| `阶段 6 受控自治加厚期` | `2026-03-15 ~ 2026-03-16` | 受控自治开始从概念变对象模型 | `I-AUTO-001` 收官、clone/激励/卫星分层、底盘提交显性化 |

## 5. 分阶段详解

本文每个里程碑都用同一数据模型：

- `阶段名`
- `绝对日期`
- `证据等级`
- `触发任务/问题`
- `新增器官/机制`
- `旧能力的升级点`
- `机器语言描述`
- `人力语言翻译`
- `这轮真正解决了什么`
- `这轮还没解决什么`
- `对应证据索引`

### 阶段 1：前史起点期

#### 里程碑 1.1

- `阶段名`：最早 canonical 起点出现
- `绝对日期`：`2026-03-09`
- `证据等级`：`L1`
- `触发任务/问题`：做完后要同步飞书，但必须先保留本地 canonical
- `新增器官/机制`：`route.json` + `situation-map.md`
- `旧能力的升级点`：从“直接执行”升级成“先路由再执行”
- `机器语言描述`：
  最早 run 已经明确包含 `routing_order`、signals、候选 skill 排序和 `Situation Map` 六判断。这说明 `AI大管家` 的起点不是普通提示词模板，而是一个最小治理入口。
- `人力语言翻译`：
  从一开始，你遇到的就不再只是“帮你干活”的助手，而是一个会先判断如何少打扰你、如何复用已有能力、如何验真的系统雏形。
- `这轮真正解决了什么`：
  把“先保留本地真相，再考虑飞书同步”的优先级定死。
- `这轮还没解决什么`：
  还没有 GitHub 可追溯镜像，也没有完整战略对象层。
- `对应证据索引`：`E01` `E02`

#### 里程碑 1.2

- `阶段名`：最大失真被明确命名
- `绝对日期`：`2026-03-09`
- `证据等级`：`L1`
- `触发任务/问题`：复盘要不要直接以飞书为准
- `新增器官/机制`：`当前最大失真` 字段
- `旧能力的升级点`：从“会同步”升级成“会区分本体和镜像”
- `机器语言描述`：
  最早 `situation-map.md` 已把 `把飞书镜像误当成 canonical source` 记为当前最大失真。这个字段后来成为整个系统反复强调的根纪律。
- `人力语言翻译`：
  这意味着系统不是在帮你多开一个面板，而是在提醒你：页面好看、同步成功，不等于事情真的成立。
- `这轮真正解决了什么`：
  立下了“镜像面不是本体”的宪法。
- `这轮还没解决什么`：
  这种纪律当时还是局部 run 级规则，还没有升级成跨阶段制度。
- `对应证据索引`：`E02` `E03`

### 阶段 2：闭环原型期

#### 里程碑 2.1

- `阶段名`：复盘和进化被塞进同一条闭环
- `绝对日期`：`2026-03-09`
- `证据等级`：`L1`
- `触发任务/问题`：做完后不仅要同步，还要留下复盘
- `新增器官/机制`：`effective patterns / wasted patterns / evolution candidates` 的前置语义
- `旧能力的升级点`：从“任务完成”升级成“任务完成 + 能力沉淀”
- `机器语言描述`：
  最早 route 信号里已经出现 `evolution=true`，并把 `self-evolution-max` 与 `feishu-bitable-bridge` 一起纳入候选。这是 `route -> verify -> evolve` 链条的早期原型。
- `人力语言翻译`：
  从这时开始，你不是在和一个“一次性打工 AI”合作，而是在喂养一个会记账、会总结、会下次更像样的系统。
- `这轮真正解决了什么`：
  让“复盘”不再是事后感想，而是进入执行链路。
- `这轮还没解决什么`：
  当时还没有统一的 `close-task`、GitHub payload、strategy/current 级别的器官。
- `对应证据索引`：`E01` `E04`

#### 里程碑 2.2

- `阶段名`：六判断成为固定开工前仪表盘
- `绝对日期`：`2026-03-09`
- `证据等级`：`L1 + L2`
- `触发任务/问题`：如何在少打扰人的前提下保持真实闭环
- `新增器官/机制`：`自治判断 / 全局最优判断 / 能力复用判断 / 验真判断 / 进化判断 / 当前最大失真`
- `旧能力的升级点`：从“经验性判断”升级成“固定治理框架”
- `机器语言描述`：
  六判断最早在 run 级工件中出现，后续被上升为 `AI大管家协作手册` 与 `SKILL.md` 的固定语义入口。
- `人力语言翻译`：
  你看到的不是某次灵光一现，而是系统把“做之前先想什么”沉淀成了可复用的合作协议。
- `这轮真正解决了什么`：
  让协作风格开始稳定，而不是每轮重新发明方法。
- `这轮还没解决什么`：
  还没长出目标层、initiative 层、卫星层。
- `对应证据索引`：`E02` `E05`

### 阶段 3：高密度器官生长期

#### 里程碑 3.1

- `阶段名`：run 密度爆发，治理核开始器官化
- `绝对日期`：`2026-03-10 ~ 2026-03-11`
- `证据等级`：`L1`
- `触发任务/问题`：大量真实任务需要被统一路由、统一镜像、统一收口
- `新增器官/机制`：大规模 `runs/*`、`github-task.json`、`github-payload.json`、`github-sync-result.json`
- `旧能力的升级点`：从单 run 成功升级成批量闭环能力
- `机器语言描述`：
  本地 run 统计显示 `2026-03-10` 有 `82` 个非 test run，`2026-03-11` 有 `83` 个非 test run。真正的变化不是“任务变多”，而是同一套闭环工件开始被规模化复用。
- `人力语言翻译`：
  这时系统不再像一个偶尔有灵感的搭子，而像一台开始有稳定工作节拍的治理机器。
- `这轮真正解决了什么`：
  证明了闭环不是个别案例，而是可批量复用的工作方式。
- `这轮还没解决什么`：
  高密度不等于高成熟，当时很多器官还是“长出来了”，还没完全稳。
- `对应证据索引`：`E06` `E07`

#### 里程碑 3.2

- `阶段名`：GitHub mirror 机制在本地先长成
- `绝对日期`：`2026-03-10 ~ 2026-03-11`
- `证据等级`：`L1`
- `触发任务/问题`：要把任务分类命名归档同步纳入统一治理
- `新增器官/机制`：`github_repo`、`dot_github_repo`、`github_project_owner` 等字段进入 run 工件
- `旧能力的升级点`：从手工归档升级成镜像协议化
- `机器语言描述`：
  尽管 GitHub issue 侧稳定痕迹在 `2026-03-13` 才清晰可见，但本地 run 在 `2026-03-10 ~ 2026-03-11` 已生成结构化 GitHub payload，说明镜像协议先在 canonical 层成形，再向外发布。
- `人力语言翻译`：
  也就是说，系统先把“怎么同步 GitHub”想明白了，才开始真正对外稳定显示，不是反过来边发边想。
- `这轮真正解决了什么`：
  把 GitHub 从“你去记一下”变成一条制度化镜像链。
- `这轮还没解决什么`：
  对外可见性和对外稳定性当时仍然弱于本地层。
- `对应证据索引`：`E07` `E08`

#### 里程碑 3.3

- `阶段名`：从任务流升级成活的战略层
- `绝对日期`：`2026-03-11`
- `证据等级`：`L1 + L2`
- `触发任务/问题`：系统不能只会做 task，还要会解释当前总控方向
- `新增器官/机制`：`strategy/current/*` 活工件体系
- `旧能力的升级点`：从 run 级进化升级成 goal/initiative/thread 级进化
- `机器语言描述`：
  `strategy/current` 已包含 `strategic-goals.json`、`initiative-registry.json`、`governance-dashboard.md`、`routing-credit.json`、`autonomy-tier.json` 等活对象。这里是 `AI大管家` 从 task governor 变成 strategy governor 的分水岭。
- `人力语言翻译`：
  你合作的不再是一个“任务处理器”，而是一个开始知道自己当前总目标、活跃项目、评分机制和优先级的系统。
- `这轮真正解决了什么`：
  让“现在最重要的是什么”有了活的系统答案，而不是每次重新判断。
- `这轮还没解决什么`：
  激励和 clone 当时还在骨架态，远未成熟。
- `对应证据索引`：`E09` `E10`

### 阶段 4：镜像制度化期

#### 里程碑 4.1

- `阶段名`：GitHub 成为稳定可追溯镜像
- `绝对日期`：`2026-03-13`
- `证据等级`：`L3`
- `触发任务/问题`：需要跨任务、跨窗口、跨时间公开追溯 AI大管家 的工作
- `新增器官/机制`：`moonstachain/ai-task-ops` issue mirror
- `旧能力的升级点`：从“本地准备好镜像”升级成“外部稳定可见”
- `机器语言描述`：
  GitHub issue 列表显示 `2026-03-13` 已有成批 `AI大管家 Task Mirror` 相关 issue，如 `#1`、`#2` 等。这是 GitHub 从协议存在变成协作现实的起点。
- `人力语言翻译`：
  从这一天起，AI大管家 不只是“你知道它做过什么”，而是“别人也能按统一格式看懂它做过什么”。
- `这轮真正解决了什么`：
  建立了跨会话、跨机器、跨协作者的镜像记账层。
- `这轮还没解决什么`：
  镜像仍然不是本体，不能因为 issue 写得好就误判系统已经成熟。
- `对应证据索引`：`E11` `E12`

#### 里程碑 4.2

- `阶段名`：命名、分类、归档不再是随手习惯
- `绝对日期`：`2026-03-13 ~ 2026-03-14`
- `证据等级`：`L2 + L3`
- `触发任务/问题`：任务太多，如果不规范命名和归档，就会重新退化成杂乱线程池
- `新增器官/机制`：`[type/domain] title` 的 issue 标题规范、归档状态、GitHub sync 边界
- `旧能力的升级点`：从“能同步”升级成“同步什么、如何归档、怎么分类都被制度化”
- `机器语言描述`：
  GitHub issue 标题已稳定使用 `[implement/ops]`、`[review/skill-system]`、`[sync/github]` 等结构，同时本地已有专门的 `github-taxonomy`、`github-naming-policy`、`github-sync-contract` 作为制度层。
- `人力语言翻译`：
  这表示系统不再只是把东西丢到 GitHub，而是在建立“以后谁看都能懂”的公共秩序。
- `这轮真正解决了什么`：
  把对外协作语言标准化。
- `这轮还没解决什么`：
  公共秩序建立了，不代表内部所有能力都已经成熟。
- `对应证据索引`：`E12` `E13`

### 阶段 5：战略分层期

#### 里程碑 5.1

- `阶段名`：`G1 / G2 / G3` 成形
- `绝对日期`：`2026-03-14 ~ 2026-03-15`
- `证据等级`：`L1 + L2`
- `触发任务/问题`：系统不能永远靠“当前任务”，必须回答长期往哪里长
- `新增器官/机制`：`strategic-goals.json`
- `旧能力的升级点`：从“有很多主线”升级成“有 3 个长期总目标”
- `机器语言描述`：
  当前活目标明确为：
  `G1 治理操作系统化`、
  `G2 受控自治与提案推进`、
  `G3 AI 组织激励系统`。
  这标志着 AI大管家 从任务汇流器升级成了战略分层系统。
- `人力语言翻译`：
  你面对的不再只是一个擅长把事做完的系统，而是一个开始知道自己为什么要这样长、先长什么、后长什么的系统。
- `这轮真正解决了什么`：
  把系统长期方向压成统一战略语言。
- `这轮还没解决什么`：
  `G2 / G3` 虽然成形，但仍有大量 gap 未被填平。
- `对应证据索引`：`E09` `E14`

#### 里程碑 5.2

- `阶段名`：initiative registry 成立
- `绝对日期`：`2026-03-15`
- `证据等级`：`L1 + L2`
- `触发任务/问题`：目标太大，必须压成可治理 initiative
- `新增器官/机制`：`I-GOV-001 / I-AUTO-001 / I-INC-001 / I-CLONE-001`
- `旧能力的升级点`：从 goal 级叙事升级成 goal -> initiative 的执行语义
- `机器语言描述`：
  `initiative-registry.json` 已明确 4 条 active initiatives，并为每条 initiative 绑定 goal、theme、strategy、gap level 和 required capabilities。
- `人力语言翻译`：
  这意味着系统不再只是“知道长期方向”，而是能把长期方向拆成可持续推进的项目层，不再靠脑内记忆维持。
- `这轮真正解决了什么`：
  把宏大目标压成可以排队、对齐、交接的中层对象。
- `这轮还没解决什么`：
  initiative 成立不等于器官成熟，尤其 `I-INC-001` 与 `I-CLONE-001` 仍是高 gap。
- `对应证据索引`：`E10` `E14`

#### 里程碑 5.3

- `阶段名`：成熟版路线图开始承认“不成熟”
- `绝对日期`：`2026-03-14`
- `证据等级`：`L2`
- `触发任务/问题`：系统需要一份不自我美化的成熟度判断
- `新增器官/机制`：`ai-da-guan-jia-mature-evolution-round-roadmap-v1.md`
- `旧能力的升级点`：从“描述现状”升级成“定义成熟标准与缺口”
- `机器语言描述`：
  这份路线图明确写出：当前最欠账的是 `execute、clone、激励`，不能把蓝图清楚误当系统成熟。
- `人力语言翻译`：
  这表明系统开始拥有一种很重要的品格：不被自己画出来的图骗到。
- `这轮真正解决了什么`：
  给未来的增长设了真实门槛，而不是自我吹大。
- `这轮还没解决什么`：
  文档能看清缺口，不等于缺口已经补上。
- `对应证据索引`：`E03` `E15`

### 阶段 6：受控自治加厚期

#### 里程碑 6.1

- `阶段名`：提案自治从概念走到对象层
- `绝对日期`：`2026-03-15`
- `证据等级`：`L1 + L2`
- `触发任务/问题`：AI大管家 不能永远只建议“开哪个线程”，需要对更高层对象提案
- `新增器官/机制`：`I-AUTO-001` Phase 1-4 完整闭环
- `旧能力的升级点`：从 thread-centered proposal 升级成 initiative / skill / workflow / clone proposal
- `机器语言描述`：
  `I-AUTO-001 Phase 4 收官文档` 已明确系统稳定输出：
  `thread_proposal`、
  `initiative_decomposition`、
  `skill_recruitment_suggestion`、
  `workflow_hardening_suggestion`、
  `clone_training_recommendation`、
  `proposal_object_map`。
- `人力语言翻译`：
  这意味着系统不再只会说“下一步干嘛”，而开始会说“该优先加厚哪个能力、固化哪个流程、训练哪个 clone”，但仍然守住 `建议 + 待批` 的边界。
- `这轮真正解决了什么`：
  把“受控自治”从话术变成对象模型。
- `这轮还没解决什么`：
  依然不是自动执行系统，边界仍然是 `proposal_first` 而非静默替你做决定。
- `对应证据索引`：`E16` `E17`

#### 里程碑 6.2

- `阶段名`：主机/卫星/前后台分层稳定
- `绝对日期`：`2026-03-15`
- `证据等级`：`L2`
- `触发任务/问题`：多机、多前台、多外部分装资产开始出现 root 身份争夺风险
- `新增器官/机制`：`main-hub` 单主、卫星前哨、人类前台与治理后脑的分工协议
- `旧能力的升级点`：从多资产并存升级成单主多前哨拓扑
- `机器语言描述`：
  `main-hub-satellite-yuanli-os-adoption-audit-v1.md` 把边界定死：
  `AI大管家` 是唯一顶层治理入口，
  `原力OS` 是人类外显层，
  `卫星` 只承担采集/执行/登录复用，不承担正式闭环。
- `人力语言翻译`：
  对你来说，这句人话就是：
  “你以后继续只跟我工作；内部怎么分卫星、前台、外部分装，是系统内部编排，不会让你被迫管理多套总控。”
- `这轮真正解决了什么`：
  阻止系统长成双主、三主甚至多 root 的混乱形态。
- `这轮还没解决什么`：
  卫星的长期稳定性和 fully verified onboarding 仍需后续验证。
- `对应证据索引`：`E18` `E10`

#### 里程碑 6.3

- `阶段名`：底盘器官开始在代码仓里显性化
- `绝对日期`：`2026-03-16`
- `证据等级`：`L2`
- `触发任务/问题`：治理语言要进一步落到底层类型、路由器、MCP、Feishu read-only、proxy 等实际底盘
- `新增器官/机制`：`R1 / R2 / R3 / R4 / R8` 提交链
- `旧能力的升级点`：从文档和工件为主，升级成底盘代码显性化
- `机器语言描述`：
  git 历史显示在 `2026-03-16` 出现一组连续提交：
  `d0b55bc feat: implement operational ontology runtime types (R1)`、
  `5354670 feat: add skill manifest and router module (R2)`、
  `8f872cc feat: add canonical MCP server with 5 tools (R3)`、
  `9f8371a feat: add Feishu read-only MCP server (R4)`、
  `0b0e5cb feat: add Feishu HTTP proxy for Claude web_fetch access (R8)`。
- `人力语言翻译`：
  这说明 AI大管家 的一些关键能力，已经不再只存在于“会不会说、会不会写方案”，而开始被压成可复用的底盘器官。
- `这轮真正解决了什么`：
  把治理语义进一步落向代码运行时。
- `这轮还没解决什么`：
  这些器官的存在本身不等于系统已经成熟；成熟仍要看真实闭环和长期稳态。
- `对应证据索引`：`E19` `E20`

## 6. 总进化逻辑

把整条历史压缩成一句话：

`AI大管家` 不是从弱助手线性升级成强助手，而是从“能执行”不断进化成“会治理执行、会治理镜像、会治理证据、会治理自己未来如何继续长”的系统。

这条进化里，至少有 3 次真进化：

1. `真进化一：canonical-first`
   - 真相源先于镜像成立。
   - 代表变化：`2026-03-09` 就已明确“先本地 canonical，再飞书同步”。
2. `真进化二：strategy/current`
   - 系统开始有活的战略对象，而不是只有一堆任务。
   - 代表变化：`G1 / G2 / G3`、initiative registry、governance dashboard 成形。
3. `真进化三：proposal object model`
   - 受控自治不再是说法，而是对象层提案机制。
   - 代表变化：`I-AUTO-001` 从蓝图走到 Phase 4 收官。

同时，这条历史里至少有 3 次关键自我纠偏：

1. `纠偏一：不要把飞书镜像误当 canonical`
2. `纠偏二：不要把 GitHub issue 密度误当成熟度`
3. `纠偏三：不要把提案自治误写成自动执行`

如果再压成一句更接近人话的总结：

`AI大管家` 最重要的进化，不是越来越会做事，而是越来越知道什么才算真的做成、什么该先问你、什么应该沉淀成下一轮能力。

## 7. 未完成的未来段

这份历史不能只写成就，否则会把系统再次写歪。

截至当前阶段，至少还有 4 个器官没有真正长稳：

### 7.1 execute 仍然是最容易被高估的部分

尽管治理语言、战略语言、镜像语言都已很强，但 `execute` 的真实业务闭环仍然比文档层成熟度低。这也是成熟路线图反复提醒的最大欠账之一。

### 7.2 clone 还是“对象模型已成，稳态运营未成”

`I-CLONE-001` 已经作为 initiative 成立，clone contracts 也已写出，但当前更接近“可治理设计完成”，还不是“真实 clone 网络长期稳定运行”。

### 7.3 incentive 仍是高价值、高风险、未完全制度化的器官

`G3 / I-INC-001` 已有 `routing-credit`、`autonomy-tier`、`scorecard` 的雏形，但激励系统最怕奖励会说的 proposal，而不是奖励真闭环与低失真。

### 7.4 稳态递归还没有完全替代强推式推进

系统已经开始呈现“自己会长”的特征，但还没有完全进入“不靠强推也能稳定周/月递归”的状态。  
这意味着未来最重要的不是再加概念，而是把高频闭环真正养成稳态节律。

## 8. 证据索引附录

### L1 本地 canonical

- `E01` [最早 route.json](/Users/liming/.codex/skills/ai-da-guan-jia/artifacts/ai-da-guan-jia/runs/2026-03-09/adagj-20260309-004645/route.json)
- `E02` [最早 situation-map.md](/Users/liming/.codex/skills/ai-da-guan-jia/artifacts/ai-da-guan-jia/runs/2026-03-09/adagj-20260309-004645/situation-map.md)
- `E06` [runs 目录总览](/Users/liming/.codex/skills/ai-da-guan-jia/artifacts/ai-da-guan-jia/runs)
- `E07` [2026-03-10 样本 run：github-task.json](/Users/liming/.codex/skills/ai-da-guan-jia/artifacts/ai-da-guan-jia/runs/2026-03-10/adagj-20260310-113328-000000/github-task.json)
- `E08` [2026-03-10 样本 run：github-sync-result.json](/Users/liming/.codex/skills/ai-da-guan-jia/artifacts/ai-da-guan-jia/runs/2026-03-10/adagj-20260310-113328-000000/github-sync-result.json)
- `E09` [strategic-goals.json](/Users/liming/.codex/skills/ai-da-guan-jia/artifacts/ai-da-guan-jia/strategy/current/strategic-goals.json)
- `E10` [governance-dashboard.md](/Users/liming/.codex/skills/ai-da-guan-jia/artifacts/ai-da-guan-jia/strategy/current/governance-dashboard.md)
- `E14` [initiative-registry.json](/Users/liming/.codex/skills/ai-da-guan-jia/artifacts/ai-da-guan-jia/strategy/current/initiative-registry.json)
- `E16` [I-AUTO-001 soul 样本，2026-03-15](/Users/liming/.codex/skills/ai-da-guan-jia/artifacts/ai-da-guan-jia/soul/2026-03-15.md)

### L2 本地代码/文档

- `E03` [AI大管家成熟进化版 8 轮路线图](/Users/liming/Documents/codex-ai-gua-jia-01/docs/ai-da-guan-jia-mature-evolution-round-roadmap-v1.md)
- `E04` [AI大管家协作手册](/Users/liming/.codex/skills/ai-da-guan-jia/AI大管家协作手册.md)
- `E05` [AI大管家 SKILL 定义](/Users/liming/.codex/skills/ai-da-guan-jia/SKILL.md)
- `E13` [GitHub sync contract](/Users/liming/.codex/skills/ai-da-guan-jia/references/github-sync-contract.md)
- `E15` [AI大管家顶层蓝图](/Users/liming/Documents/codex-ai-gua-jia-01/docs/ai-da-guan-jia-top-level-blueprint-v1.md)
- `E17` [I-AUTO-001 Phase 4 收官文档](/Users/liming/Documents/codex-ai-gua-jia-01/docs/ai-da-guan-jia-i-auto-001-phase4-closeout-v1.md)
- `E18` [主机主策略与卫星原力OS吸收审计报告](/Users/liming/Documents/codex-ai-gua-jia-01/docs/main-hub-satellite-yuanli-os-adoption-audit-v1.md)
- `E19` [git 历史：R1/R2/R3/R4/R8 提交链说明](/Users/liming/Documents/codex-ai-gua-jia-01/docs/ai-da-guan-jia-full-history-bilingual-evolution-roadmap-v1.md#阶段-6受控自治加厚期)
- `E20` [AI大管家 Medallion 提案自治路线图](/Users/liming/Documents/codex-ai-gua-jia-01/docs/ai-da-guan-jia-medallion-proposal-autonomy-roadmap-v1.md)

### L3 GitHub 镜像

- `E11` [moonstachain/ai-task-ops issue #1](https://github.com/moonstachain/ai-task-ops/issues/1)
- `E12` [moonstachain/ai-task-ops issue #2](https://github.com/moonstachain/ai-task-ops/issues/2)

### L4 解释性推断

- `P01`
  `高可信推断`：`2026-03-10 ~ 2026-03-11` 是 GitHub 镜像机制在本地 canonical 层先长成、再于 `2026-03-13` 外显稳定的过渡期。
- `P02`
  `高可信推断`：当前全合作史里，真正的主进化逻辑不是“更强执行”，而是“更强治理 + 更强边界 + 更强可追溯性”。

## 9. 后续补档建议

后续如果发现 `2026-03-09` 之前还有更早材料，不需要推翻本文结构，只需新增一个小节：

- `前史补档期`

然后把新增证据插入 `阶段 1` 之前即可。

这也是本文刻意采用“阶段 + 证据索引”结构，而不是纯散文叙事的原因：  
它不是一次性纪念文，而是未来还会继续更新的 `AI大管家` 正式成长档案。
