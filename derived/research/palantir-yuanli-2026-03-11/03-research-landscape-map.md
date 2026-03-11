# 03. 外部研究地图

## 研究脉络 1: Enterprise Ontology

### 核心问题

企业世界中有哪些稳定对象、角色、关系和边界，能够被不同系统共享理解。

### 代表来源

- [Palantir Ontology Overview](https://www.palantir.com/docs/foundry/ontology/overview/)
- [Why create an Ontology?](https://www.palantir.com/docs/foundry/ontology/why-ontology)
- [W3C ORG Ontology](https://www.w3.org/TR/vocab-org/)

### 与 Palantir 的相似处

- 都强调对象和关系比裸表结构更接近真实业务世界。
- 都强调语义稳定性对跨系统协作有价值。

### Palantir 多出来的东西

- 对象不是只供描述，还供应用、动作、权限和 AI 调用。
- ontology 是“工作界面”，不是“抽象字典”。

### 对原力OS的启发

- `原力 epistemic ontology` 用来定义知识和边界。
- `原力 operational ontology` 用来定义任务、线程、资产、决策和动作。
- 两者都叫 ontology，但职责必须分开。

## 研究脉络 2: Knowledge Graph / OBDA

### 核心问题

如何让异构数据通过语义层被稳定查询、联结、解释，并为 AI 提供 grounding。

### 代表来源

- [KG, LLM and LMM Survey](https://arxiv.org/abs/2403.03111)
- [LLM and KG: Opportunities and Challenges](https://arxiv.org/abs/2308.06374)

### 与 Palantir 的相似处

- 都强调符号结构和关系信息在复杂推理中的作用。
- 都认为语义层能提升可解释性和可控性。

### Palantir 多出来的东西

- 不止问答和查询，还包含行动入口和业务写回。
- 权限和政策不是外部拼接，而是靠近对象层。

### 对原力OS的启发

- `EvidenceAtom` 应该是最小 grounding 单位。
- 先把 evidence、entity、decision 关系打通，再接 LLM/agent。

## 研究脉络 3: Digital Twin / Cognitive Twin

### 核心问题

如何把真实世界建成持续更新、可反馈、可模拟、可决策的数字镜像。

### 代表来源

- [Digital Twin Review](https://www.mdpi.com/1099-4300/23/2/204)
- [A Cognitive Digital Twin for Intelligent Decision-Making](https://link.springer.com/article/10.1007/s12559-022-10037-4)
- [Azure Digital Twins Overview](https://learn.microsoft.com/en-us/azure/digital-twins/overview)

### 与 Palantir 的相似处

- 都强调模型和现实之间持续同步。
- 都强调反馈回路，而不是静态快照。

### Palantir 多出来的东西

- twin 的对象是企业运营世界，不只是设备或物理系统。
- 决策、协作、权限、agent 都能挂进这个 twin。

### 对原力OS的启发

- 原力OS 不该只做“知识 twin”，而要做“治理与执行 twin”。
- `TaskThread`、`DecisionRecord`、`WritebackEvent` 都可以看成治理 twin 的基本对象。

## 研究脉络 4: Decision Intelligence

### 核心问题

如何让决策过程被结构化、支持、追踪、复盘，并持续改进。

### 代表来源

- [Gartner 2022 D&A Trends](https://www.gartner.com/en/newsroom/press-releases/2022-03-14-gartner-identifies-top-trends-in-data-and-analytics-for-2022)
- [A Cognitive Digital Twin for Intelligent Decision-Making](https://link.springer.com/article/10.1007/s12559-022-10037-4)

### 与 Palantir 的相似处

- 都在试图把 BI 推向决策支持。
- 都强调从描述型分析走向行动导向。

### Palantir 多出来的东西

- 把 `decision capture -> action -> writeback -> audit` 做成操作闭环。
- 决策不是“报告结尾一句建议”，而是对象层里的可追踪事件。

### 对原力OS的启发

- 原力OS 应把 `DecisionRecord` 做成可查询、可关联、可回写对象。
- 晨会、review、线程推进，都应该沉淀为可复盘的决策资产。

## 研究脉络 5: Agentic Enterprise Systems

### 核心问题

agent 如何在企业环境里真正产生价值，而不是只做聊天或 demo。

### 代表来源

- [AIP Features](https://www.palantir.com/docs/foundry/aip/aip-features)
- [Why Agents Are the Next Frontier of Generative AI](https://www.mckinsey.com/capabilities/mckinsey-digital/our-insights/why-agents-are-the-next-frontier-of-generative-ai)

### 与 Palantir 的相似处

- 都强调 agent 需要访问工具和业务系统。
- 都强调 workflow integration 比单轮对话更关键。

### Palantir 多出来的东西

- agent 的 grounding、policy、tooling、audit 和业务对象共用同一底座。
- 不是“给模型更多插件”，而是“让 agent 住进受控的对象世界”。

### 对原力OS的启发

- `AgentCapability` 必须是显式建模对象。
- 不应让 agent 直接操作底层文件或外部系统；应通过 action 层进行。

## 总评

Palantir 并不是从零发明了 enterprise ontology、knowledge graph、digital twin、decision intelligence 和 enterprise agents。它真正稀缺的，是把这些脉络以产品和交付方法高度耦合地工程化，并让它们围绕真实业务对象形成闭环。

## 讨论题

1. 原力OS 最该吸收的是哪一条脉络，为什么？
2. 你更想先建立 evidence grounding，还是先建立 action/writeback？
3. 你接受把原力OS 看成“治理 twin”吗？
4. 如果只借 agentic 那层，不补对象和权限，会不会变成空壳？
