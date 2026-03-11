# 01. Palantir 入门讲透版

## 一句话先讲明白

Palantir 不是“一个很会做情报的软件公司”这么简单。它真正厉害的地方，是把企业里分散的数据、流程、角色、决策、动作和 AI 都压进一个统一的操作层里，让人和机器可以在同一套对象世界里看、想、干、回写、审计。

## Palantir 到底在卖什么

按公开材料看，Palantir 主要卖的是一套企业运行平台，而不是一个单点工具：

- `Gotham`：偏政府、国防、情报与任务协同。
- `Foundry`：偏企业运营、数据治理、应用开发和决策执行。
- `Apollo`：偏持续部署、交付和跨环境运营。
- `AIP`：把大模型、工具、agent 能力接到已有的 ontology、policy 和应用层上。

来源：
[Platform Overview](https://www.palantir.com/docs/foundry/platform-overview/overview/),
[Architecture Center Overview](https://www.palantir.com/docs/foundry/architecture-center/overview/),
[AIP Features](https://www.palantir.com/docs/foundry/aip/aip-features)

## `Ontology` 到底是什么

这里的 `Ontology` 不是哲学里那个“世界究竟由什么构成”的本体论。

Palantir 的 `Ontology` 更像：

- 企业世界的对象模型
- 业务语义层
- 数字孪生/操作层
- 应用和 AI 的 grounding layer

它关心的是：

- 企业里有哪些关键对象，例如客户、工单、资产、供应节点、任务、人员、事件
- 这些对象之间是什么关系
- 这些对象处于什么状态
- 针对这些对象允许做什么动作
- 谁能做，做完如何回写和审计

所以 Palantir 的 `Ontology` 不是停在“理解世界”，而是直接进入“操作世界”。

来源：
[Ontology Overview](https://www.palantir.com/docs/foundry/ontology/overview/),
[Why create an Ontology?](https://www.palantir.com/docs/foundry/ontology/why-ontology)

## 为什么这套东西会显得很牛

### 1. 它把“看见”升级成“干预”

很多企业系统只能做到报表、图表、监控、搜索、问答。Palantir 的目标是继续往下走，直接把行动能力挂在对象层上，让分析、协同、决策、执行、回写形成闭环。

### 2. 它把 AI 绑在真实业务世界上

很多 AI 项目失败，不是模型不聪明，而是模型没有稳定、可控、带权限的世界模型。Palantir 的做法，是让 AIP 站在 ontology 之上去调用函数、访问对象、遵守策略，而不是直接裸连数据库和文档堆。

### 3. 它把“部署能力”也产品化了

很多公司能做 demo，但做不好跨环境部署、版本控制、合规上线、持续运营。`Apollo` 和架构中心那条线，说明 Palantir 把 delivery 和 operations 也做成了体系。

### 4. 它把交付方法论标准化了

从公开投资者材料看，`AIP bootcamps` 是它极强的一张牌。它不是先卖一个大而全的多年蓝图，而是用密集共创把真实场景快速拉进平台，让用户在短时间里看到“这玩意真能改世界”。

来源：
[Q3 2023 Business Update](https://investors.palantir.com/files/Palantir%20Q3%202023%20Business%20Update.pdf)

## 这和“知识图谱”有什么区别

Palantir 当然借用了知识图谱、语义层、数据建模的思想，但它不是传统意义上的知识图谱产品。

传统知识图谱更偏：

- 表达知识
- 统一实体
- 关系推理
- 查询与解释

Palantir 更偏：

- 表达企业对象
- 管理对象状态
- 绑定动作和工具
- 绑定权限和治理
- 让人和 agent 在这个对象世界里协作

所以它更接近“operational knowledge graph”甚至“enterprise operating system”。

## 为什么业界会反复提它的 `Ontology`

因为很多企业数字化项目卡在这里：

- 底层数据太碎
- 上层 AI 太飘
- 报表和实际动作脱节
- 每个部门说的不是同一个对象
- 系统之间不能稳定回写

`Ontology` 正好卡在中间，像一个语义和操作的总线。它既能往下接数据，又能往上接应用、AI 和人。

## 你该怎么理解“Palantir 为什么涨得凶”

只从方法论角度，不做投资建议：

- 市场越来越相信企业 AI 不是“多一个聊天框”，而是“把模型接进真实业务闭环”。
- Palantir 刚好长期建设的是这个闭环底座。
- `AIP` 不是从零开始，而是叠在已有 ontology、应用、权限、部署、行业交付之上，所以被市场视为放大器。

## 对原力OS 最重要的一句翻译

如果用你的语境翻译，Palantir 最值得学的不是“做一个大 ontology”，而是：

> 先定义一个能被人、系统、agent 共用的对象世界；再让动作、权限、回写和审计都依附在这个对象世界上。

## 讨论题

1. 原力OS 当前更像“知识治理系统”，还是已经有一部分“操作系统”雏形？
2. 你最想让 agent 改变的真实世界对象是什么：任务、线程、资产、决策，还是别的？
3. 如果没有动作与回写，原力OS 会不会只变成更高级的知识库？
4. 你更接受先做小而硬的 operational layer，还是先扩完整 ontology 名词体系？
