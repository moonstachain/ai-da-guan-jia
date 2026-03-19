# Governance Dashboard

- Stage Theme: 从强执行体升级为受控自治的 AI 治理系统
- Highest Goal: 让 AI大管家 从任务路由器进化成战略提案者 + 组织编排者 + 治理审计者。
- Theme Policy: proposal_first
- First Active Theme: theme-human-ai-coevolution
- Frontstage Focus Override: theme-governance (registry active stays theme-human-ai-coevolution)
- Wave 1 Complete: False
- Recommended Next Focus:  [] :: 
- I-AUTO-001 Status: Phase 4 in progress

## Strategic Goals

- G1: 治理操作系统化 :: 从技能集合升级为可治理的 AI operating system
- G2: 受控自治与提案推进 :: 先做到高质量提案自治，而不是全自动执行
- G3: AI 组织激励系统 :: 奖励治理质量、低失真和可复用贡献

## Production Axis

- Stages: theme -> strategy -> experiment -> workflow
- Counts: themes=3 strategies=8 experiments=6 workflows=0
- Method Priority: 低失真 > 验真闭环 > 速度 > 自动化率
- Frontstage Cap: 3 workflow_generation_enabled=False
- Benchmark Thread: 原力OS：宰相制度的萌芽

## Theme Registry

- theme-governance :: governed_seed :: proposal=queued :: owner=proposal_first :: 治理
- theme-business :: governed_seed :: proposal=queued :: owner=proposal_first :: 业务
- theme-human-ai-coevolution :: active :: proposal=approved :: owner=co_governed_proposal_first :: 人机协同创新

## Strategy Registry

- strategy-governance-mainline-closure [theme-governance] :: validated :: mother=none :: 治理主线收口
- strategy-governance-operating-core-closure [theme-governance] :: proposed :: mother=strategy-governance-mainline-closure :: 治理运行骨架收口
- strategy-governance-operational-ontology-closure [theme-governance] :: proposed :: mother=strategy-governance-mainline-closure :: operational ontology 收口
- strategy-governance-transport-unblock [theme-governance] :: proposed :: mother=strategy-governance-mainline-closure :: transport 打通
- strategy-human-ai-success-efficiency [theme-human-ai-coevolution] :: validated :: mother=none :: 最大成功率与效率的人机协同
- strategy-human-ai-low-interruption-convergence [theme-human-ai-coevolution] :: proposed :: mother=strategy-human-ai-success-efficiency :: 连续表达低打断收束
- strategy-human-ai-mvp-fast-validation [theme-human-ai-coevolution] :: proposed :: mother=strategy-human-ai-success-efficiency :: 最小可控MVP快证
- strategy-human-ai-consensus-before-automation [theme-human-ai-coevolution] :: proposed :: mother=strategy-human-ai-success-efficiency :: 上层共识先于自动化固化

## Experiment Registry

- experiment-governance-operating-core-closure-001 [strategy-governance-operating-core-closure] :: verdict=pending_real_round :: scope=围绕治理体系研究只跑 1 次真实 scaffold 消费回合，结果只能是 completed 或明确 blocked。
- experiment-governance-operational-ontology-closure-001 [strategy-governance-operational-ontology-closure] :: verdict=pending_real_round :: scope=只做接线修复、完整验证、噪音隔离 3 件事，不开新抽象线程。
- experiment-governance-transport-unblock-001 [strategy-governance-mainline-closure] :: verdict=passed :: scope=先补 auth / remote 边界，再跑 1 次真实 emit；缺权限就直接转 blocked_needs_user。
- experiment-human-ai-low-interruption-round-001 [strategy-human-ai-low-interruption-convergence] :: verdict=pending_real_round :: scope=选择 1 次真实连续表达会话，只验证接话节奏、收束质量和最小必要追问。
- experiment-human-ai-mvp-fast-validation-001 [strategy-human-ai-mvp-fast-validation] :: verdict=pending_real_round :: scope=围绕 1 个真实主题只跑最小链路，验证 idea -> strategy -> experiment -> verdict 是否顺畅闭环。
- experiment-human-ai-consensus-before-automation-001 [strategy-human-ai-consensus-before-automation] :: verdict=pending_real_round :: scope=选择 1 条拟自动化链路，先只做共识和策略验证，不落地自动执行。

## Workflow Registry

- none

## Canonical Thread Program

- Canonical Threads: 30
- Dispositions: frontstage=3 background=11 waiting_human=1 deferred=1 candidate_pool=14
- Wave Order: wave_0_remap -> wave_1_frontstage -> wave_2_closure_only -> wave_3_cleanup

## Frontstage Threads

- 原力OS-治理体系研究 [theme-governance] :: strategy=strategy-governance-operating-core-closure experiment=experiment-governance-operating-core-closure-001 :: next=跑 1 次真实 scaffold 消费闭环，结果只能是 completed 或明确 blocked。
- 原力OS-分形设计主线 [theme-governance] :: strategy=strategy-governance-operational-ontology-closure experiment=experiment-governance-operational-ontology-closure-001 :: next=只做接线修复、完整验证、噪音隔离 3 件事。
- 原力OS-信息聚合主线 [theme-governance] :: strategy=strategy-governance-transport-unblock experiment=experiment-governance-transport-unblock-001 :: next=先补 auth / remote 边界，再跑 1 次真实 emit。

## Background Merge Queue

- 原力OS-三层治理-主题层 [theme-governance] :: strategy=strategy-governance-mainline-closure :: blocker=已形成上层原则，但不应继续单独占前台。
- 原力OS-DNA完善讨论 [theme-governance] :: strategy=strategy-governance-mainline-closure :: blocker=宪章成文但未进入运行时接口层。
- 战略思考 [theme-governance] :: strategy=strategy-governance-mainline-closure :: blocker=它是总控判断，不是独立结果项目。
- 原力OS-使用说明书 [theme-governance] :: strategy=strategy-governance-mainline-closure :: blocker=内容已完成，但入口可发现性不足。
- 原力OS-三大主线的PM [theme-governance] :: strategy=strategy-governance-mainline-closure :: blocker=属于治理 PM 叠层，不应和主线收口并行抢前台。
- 原力OS-OSA项目管理 [theme-governance] :: strategy=strategy-governance-mainline-closure :: blocker=contract 已成，但真实试点还没跑。
- 原力OS-激励设计 [theme-governance] :: strategy=strategy-governance-mainline-closure :: blocker=评分校准和真实遥测未完成。
- github [theme-governance] :: strategy=strategy-governance-transport-unblock :: blocker=automation 已设，但硬验真不足。
- 多维表+飞书编程 [theme-governance] :: strategy=strategy-governance-transport-unblock :: blocker=它是清仓复盘，不是继续常驻推进的主线。
- 多维表-仪表盘 [theme-governance] :: strategy=strategy-governance-transport-unblock :: blocker=模板已成，但真实业务结果层未接管。
- 原力OS-本体论研究 [theme-governance] :: strategy=strategy-governance-operational-ontology-closure :: blocker=主线已成文，但未被动作化。

## Waiting Human Boundary

- 原力OS-CEO述职 [theme-governance] :: next=目标 base / dashboard 入口补齐后再回填第一版主会场。 :: blocker=缺目标 Feishu base / dashboard 入口。

## Deferred After Narrowing

- 原力星球-CBM [theme-business] :: next=继续前必须压窄到 5-8 个私教服务案例或只接视频号入口。 :: blocker=主线过宽，未收束到单一结果面。

## Candidate Pool

- 原力茶馆-小石头的大世界 [theme-business] :: next=作为 Wave 2 最近候选，先重生成干净 publish packet。 :: blocker=只差一次人工确认与真实发布。
- 康波大地图 [theme-business] :: next=Wave 2 只收首页旧图和跨表卡。 :: blocker=dashboard 页面本身未最终收口。
- 他山之玉 [theme-business] :: next=Wave 2 先出正式长文，再补 facts-to-yuanli。 :: blocker=样板已成，但制度化未收口。
- 原力OS-技能市场 [theme-governance] :: next=Wave 2 收拢成 09:00 真实消费入口。 :: blocker=自动化入口和晨会消费路径分叉。
- 原力OS-skill成熟度治理 [theme-governance] :: next=Wave 2 在 transport 边界清楚后收口 maturity baseline。 :: blocker=transport / satellite / Feishu link 仍缺。
- moltbook社区同步 [theme-business] :: next=保留观察位，只有渠道仍高优先时再补 owner login / API。 :: blocker=owner login / X claim / API key 仍缺人工边界。
- 智普龙虾的评估 [theme-human-ai-coevolution] :: next=只保留为人机协同评估候选，不进入本轮治理前台。 :: blocker=尚未与当前治理主线建立直接结果关系。
- 外部SKILL评估体系 [theme-human-ai-coevolution] :: next=保留到 coevolution candidate_pool，后续再决定是否进入外部 skill 治理线。 :: blocker=当前更适合作为评估方法候选，而非治理主线负载。
- 龙虾教练的教练 [theme-human-ai-coevolution] :: next=保留为人机协同样板候选，不抢治理主题前台。 :: blocker=和当前治理主线没有直接收口关系。
- 龙虾教练的提示词工程 [theme-human-ai-coevolution] :: next=保留为协同方法候选，等待后续样板化再进入策略层。 :: blocker=当前不是治理前台要解决的终态问题。
- $ai-da-guan-jia 我想用这个skill [theme-human-ai-coevolution] :: next=保留为 coevolution 方法样板，不进入本轮前台。 :: blocker=它更像方法自反材料，不是治理主线负载。
- B站视频的信息萃取 [theme-business] :: next=保留为业务 candidate，不进本轮治理前台。 :: blocker=尚未被压成单一业务结果面。
- 要招董秘啦 [theme-business] :: next=保留为业务 candidate，等治理主线收口后再上桌。 :: blocker=当前优先级低于治理主线收口。
- 原力OS：宰相制度的萌芽 [theme-human-ai-coevolution] :: next=仅作为 benchmark thread，不进入本轮工作负载。 :: blocker=none :: benchmark_only

## Out Of Program

- 马上要搬家啦

## Wave Plan

- wave_0_remap :: 完成 canonical remap，确保截图主线有唯一 owner。
- wave_1_frontstage :: 串行推进 治理体系研究 -> 分形设计 -> 信息聚合。
- wave_2_closure_only :: 只做近成品收尾，不扩抽象。
- wave_3_cleanup :: 做 merge / background / defer 清仓。

## Active Initiatives

- I-GOV-001 [G1] 治理主线收口 :: active :: gap=low :: theme=theme-governance / strategy=strategy-governance-mainline-closure / experiment=none / workflow=none
- I-AUTO-001 [G2] 提案自治引擎 :: active :: gap=high :: theme=theme-human-ai-coevolution / strategy=strategy-human-ai-success-efficiency / experiment=none / workflow=none
- I-INC-001 [G3] AI 激励评分体系 :: active :: gap=high :: theme=theme-governance / strategy=none / experiment=none / workflow=none
- I-CLONE-001 [G2] AI管家克隆体训练工厂 :: active :: gap=high :: theme=theme-human-ai-coevolution / strategy=strategy-human-ai-success-efficiency / experiment=none / workflow=none

## Active Threads

- Total tracked threads: 7
- Archived: 3
- Active: 4
- adagj-20260319-092742-ts-kb-07 [G1] theme=theme-governance strategy=strategy-governance-mainline-closure experiment=none workflow=none canonical=none disposition=none :: TS-KB-07 十五五政策信号层飞书建表 + 妙搭前端
- adagj-20260318-tsyl02-apply6 [G1] theme=theme-governance strategy=strategy-governance-mainline-closure experiment=experiment-governance-transport-unblock-001 workflow=none canonical=github disposition=background_merge_queue :: TS-YL-02 final closure: sync T0 rating fields from the 256-row T9S diagnostic score table, mirror the run to Feishu, and mirror the run to GitHub.
- adagj-20260318-retro-10d [G1] theme=theme-human-ai-coevolution strategy=strategy-human-ai-success-efficiency experiment=none workflow=none canonical=none disposition=none :: 10天协同系统首次大盘点，并建立 23:00 递归复盘机制
- adagj-20260318-gh6-closure [G1] theme=theme-governance strategy=strategy-governance-mainline-closure experiment=none workflow=none canonical=none disposition=none :: TS-GH-03 和 TS-DASH-04 联合验收通过，正式结项
- adagj-20260318-194000-000000 [G1] theme=theme-governance strategy=strategy-governance-mainline-closure experiment=none workflow=none canonical=none disposition=none :: 阅读、评估并执行 t0-t12-t15 relation-aware schema manifest，补建 T0/T12-T15 并回填 table_id
- adagj-20260318-172718-000000 [G1] theme=theme-human-ai-coevolution strategy=strategy-human-ai-success-efficiency experiment=none workflow=none canonical=none disposition=none :: 读取并执行 TS-YL-01：基于原力创业-6张新表种子数据包.xlsx，为康波 Base 准备 T6-T11 六张新表的本地 canonical、schema/seed 映射与后续 Feishu 落地计划，尽量少打扰人类
- adagj-20260318-131707-000000 [G1] theme=theme-human-ai-coevolution strategy=strategy-human-ai-success-efficiency experiment=none workflow=none canonical=none disposition=none :: 执行 TS-KB-06：在 MiroFish Vue 前端新增财富三观认知层落地页面、路由与本地数据适配，并同步准备飞书三张表 schema 和 seed 方案；优先复用现有战略任务页风格，尽量少打扰人类。

## Production Metrics

- Theme Layer: proposal_acceptance=1/3 active_theme_focus=2/4
- Strategy Layer: idea_to_verdict_cycle_time_hours=9.02 mother_strategy_reuse=6
- Execution Layer: verified_closure_rate=0.71 human_interruption_count=0 workflow_reuse_rate=0.0

## Current Gaps

- Missing middle layers: workflow-hardening | skill-deduper | skill-inventory-review
- Under-hardened high-use skills: feishu-bitable-bridge

## Proposal Queue

- TP-001 [thread] theme-governance :: goal=G1 theme=theme-governance strategy=none experiment=none :: action=建立统一治理视图与战略 review :: status=pending_approval
- TP-002 [thread] strategy-human-ai-success-efficiency :: goal=G2 theme=theme-human-ai-coevolution strategy=strategy-human-ai-success-efficiency experiment=none :: action=用大奖章/IBM 方法论加厚提案自治引擎 :: status=pending_approval
- TP-003 [thread] theme-governance :: goal=G3 theme=theme-governance strategy=none experiment=none :: action=建立 agent scorecard 与提权机制 :: status=pending_approval
- TP-HA-001 [thread] experiment-human-ai-mvp-fast-validation-001 :: goal=G2 theme=theme-human-ai-coevolution strategy=strategy-human-ai-mvp-fast-validation experiment=experiment-human-ai-mvp-fast-validation-001 :: action=在 theme-human-ai-coevolution 下运行一次人机协同 MVP 快证回合 :: status=pending_approval

## Top Routing Credit

- collab-sync: closure=1.0 verify=10.0 reuse=1 distortion=2.0
- evolution-log: closure=1.0 verify=10.0 reuse=1 distortion=2.0
- ai-da-guan-jia: closure=1.0 verify=6.24 reuse=4 distortion=0.5 proposal=0.97 support=1
- agency-engineering-frontend-developer: closure=1.0 verify=4.0 reuse=1 distortion=0.0
- spreadsheet: closure=1.0 verify=4.0 reuse=1 distortion=0.0
- feishu-bitable-bridge: closure=0.5 verify=5.99 reuse=2 distortion=0.0 proposal=0.97 support=1
- jiyao-youyao-haiyao: closure=0.5 verify=4.49 reuse=2 distortion=0.5 proposal=0.97 support=1
- yuanli-knowledge: closure=0.0 verify=5.49 reuse=1 distortion=0.0 proposal=0.97 support=1
- agency-agentic-identity-trust: closure=0.0 verify=0.0 reuse=0 distortion=0.0
- agency-agents-orchestrator: closure=0.0 verify=0.0 reuse=0 distortion=0.0
