# 原力全体系治理总览

- 生成时间: 2026-03-14T21:48:39+08:00
- 联邦实例数: 5
- 主体数: 12
- 终端数: 5
- 账号数: 7
- 来源数: 2
- 模块覆盖: 6/6
- 业务副手覆盖: 3/3
- 资产数: 147
- 订单数: 1016
- 现金流数: 0
- 任务数: 42
- 线程数: 33
- 技能数: 112
- 动作数: 9
- 决策数: 1027
- 写回事件数: 1024
- 晨会/Review 数: 1

## 联邦实例
- 原理OS联邦总图 [federation_root] :: root
- 0号实例-你本人 [personal_instance] :: personal
- 内部协作实例 [internal_instance] :: internal
- 客户复制实例 [client_instance] :: client
- 下游复制实例 [downstream_instance] :: downstream

## 模块责任覆盖
- 公域获客 :: human=hay2045 :: ai=公域增长 Agent :: deputy=业务增长 Deputy
- 私域转化 :: human=hay2045 :: ai=私域转化 Agent :: deputy=业务增长 Deputy
- 销售成交 :: human=内部协作责任人 :: ai=销售 Agent :: deputy=业务增长 Deputy
- 产品交付 :: human=内部协作责任人 :: ai=交付 Agent :: deputy=缺失
- 财务经营 :: human=内部协作责任人 :: ai=财务 Agent :: deputy=缺失
- 治理控制 :: human=hay2045 :: ai=治理 Agent :: deputy=缺失

## 当前活跃线程
- Scheduled governed transcript review (propose_only) using default Feishu Minutes + Get笔记 sources for Transcript 9am automation. [G1]
- 把 agency-engineering-rapid-prototyper 从 persona 加厚成可验证 workflow 样板，并补齐 AI大管家 路由命中。 [G1]
- 把 agency-engineering-frontend-developer 从 persona 加厚成页面实现包 workflow 样板，并补齐 AI大管家 路由边界。 [G1]
- 落地 AI龙虾训练营 v1 交付包 [G1]
- 实现腾讯会议分享页探测器、治理入库和 CLI 入口 [G1]

## 当前 Active Operational Thread
- 当前没有识别到 operational ontology 主线程。

## 当前 Action Catalog
- review-skill :: skill :: approval=no
- resolve-action :: review_run :: approval=yes
- publish-governance-report :: asset :: approval=yes
- lead-capture :: sales_lead :: approval=no
- opportunity-qualify :: sales_opportunity :: approval=no
- proposal-quote :: sales_quote :: approval=yes
- deal-commit :: sales_deal :: approval=no
- deal-close :: sales_deal :: approval=yes
- post-close-handoff :: sales_handoff :: approval=no

## 当前 Pending Decisions
- 处理外部高价值线索 :: review_action_resolution :: pending_approval
- 加厚高频 agency 技能 :: review_action_resolution :: pending_approval
- 处理重复和边界冲突 :: review_action_resolution :: pending_approval

## 最近 Writeback Events
- writeback-48bd23f614 :: publish-governance-report :: completed
- writeback-9fd8746851 :: deal-close :: completed
- writeback-af8caf4afb :: deal-close :: completed
- writeback-58fa955eae :: deal-close :: completed
- writeback-388a97dd80 :: deal-close :: completed

## 当前待跟进任务
- 建立原力OS主线收口计划的总控母任务：按三波推进执行。Wave 1 前台推进治理体系研究、分形设计主线、信息聚合主线；Wave 2 收尾原力茶馆-小石头的大世… :: 按 program-control.json 的四面板和三波顺序推进；当前只保留 Wave 1 三条主线在前台。
- 建立原力OS主线收口计划的总控母任务：按三波推进执行。Wave 1 前台推进治理体系研究、分形设计主线、信息聚合主线 :: 等待下游技能或人工接手；当前本地闭环可继续。
- Wave 2 收尾原力茶馆-小石头的大世界、康波大地图、他山之玉、原力OS-技能市场、原力OS-skill成熟度治理 :: 等待下游技能或人工接手；当前本地闭环可继续。
- Wave 3 把DNA宪章、本体论/方法论、CEO述职、激励设计、使用说明书、多维表-仪表盘、多维表+飞书编程、github等线程合并降噪，并将moltbook社区同步设为后台等待边界、原力星球-CBM设为收窄后再开。最终每条子线必须落到 completed / blocked_needs_user / blocked_system / failed_partial / merged / deferred 之一 :: Wave 3 已完成终态判定；merge / wait_human / defer 队列已固化。
- 恢复原力OS-信息聚合主线的 transport 边界：补齐 gh、GitHub auth、GITHUB_TOKEN、moonstachain/ai-task… :: 保持 ai-task-ops 的日常 emit / aggregate / audit 节奏；后续再把 shadow bootstrap 替换成真实独立外部端。

## 技能簇分布
- AI大管家治理簇: 7
- agency簇: 12
- 垂直workflow簇: 12
- 平台簇: 12
- 技能生产簇: 3
- 未分组: 66

## 来源覆盖
- order_facts::business-finance :: family=order_facts :: recognized=3 :: unclassified=0
- governance_artifact::IntelligencePlatform :: family=governance_artifact :: recognized=3042 :: unclassified=0
