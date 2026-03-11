# 原力全体系治理总览

- 生成时间: 2026-03-11T19:39:02+08:00
- 联邦实例数: 5
- 主体数: 11
- 终端数: 5
- 账号数: 7
- 来源数: 7
- 模块覆盖: 6/6
- 资产数: 25
- 订单数: 2
- 现金流数: 1
- 任务数: 5
- 线程数: 5
- 技能数: 3
- 动作数: 3
- 决策数: 4
- 写回事件数: 1
- 晨会/Review 数: 1

## 联邦实例
- 原理OS联邦总图 [federation_root] :: root
- 0号实例-你本人 [personal_instance] :: personal
- 内部协作实例 [internal_instance] :: internal
- 客户复制实例 [client_instance] :: client
- 下游复制实例 [downstream_instance] :: downstream

## 模块责任覆盖
- 公域获客 :: human=hay2045 :: ai=公域增长 Agent
- 私域转化 :: human=hay2045 :: ai=私域转化 Agent
- 销售成交 :: human=内部协作责任人 :: ai=销售 Agent
- 产品交付 :: human=内部协作责任人 :: ai=交付 Agent
- 财务经营 :: human=内部协作责任人 :: ai=财务 Agent
- 治理控制 :: human=hay2045 :: ai=治理 Agent

## 当前活跃线程
- 完成原力治理主图 [G1]
- 内部销售协同节奏梳理 [G1]
- Palantir -> 原力OS operational ontology v0 [G1]
- 给客户复制原力治理模板 [G2]

## 当前 Active Operational Thread
- Palantir -> 原力OS operational ontology v0 [G1]

## 当前 Action Catalog
- review-skill :: skill :: approval=no
- resolve-action :: review_run :: approval=yes
- publish-governance-report :: asset :: approval=yes

## 当前 Pending Decisions
- 先补 workflow hardening :: review_action_resolution :: pending_approval
- 先清理 overlap :: review_action_resolution :: pending_approval
- 先优化 review 路由 :: review_action_resolution :: pending_approval

## 最近 Writeback Events
- writeback-a1f9d00591 :: publish-governance-report :: completed

## 当前待跟进任务
- 完成原力治理主图 :: 先确认 v1 母题范围
- 内部销售协同节奏梳理 :: 先确认内部 owner 分工
- Palantir -> 原力OS operational ontology v0 :: 先补 canonical -> derived 镜像链
- 给客户复制原力治理模板 :: 先确认客户要复制到哪一层

## 技能簇分布
- AI大管家治理簇: 1
- 垂直workflow簇: 2

## 来源覆盖
- cashflow_ledger::business :: family=cashflow_ledger :: recognized=1 :: unclassified=0
- order_facts::business :: family=order_facts :: recognized=2 :: unclassified=0
- course_material::courses :: family=course_material :: recognized=1 :: unclassified=0
- unclassified::content :: family=unclassified :: recognized=0 :: unclassified=1
- wechat_content::content :: family=wechat_content :: recognized=2 :: unclassified=0
- governance_artifact::ai-da-guan-jia :: family=governance_artifact :: recognized=13 :: unclassified=0
- order_facts::2026-03-11 :: family=order_facts :: recognized=1 :: unclassified=0
