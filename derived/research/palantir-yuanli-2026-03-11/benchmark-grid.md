# Palantir Benchmark Grid

## Target Capability

把 Palantir 的方法论拆成可比较的部件，再判断哪些是已有学术/行业脉络的工程化整合，哪些是它自己的组合优势。

## Comparison Grid

| 脉络 | 核心问题 | 代表来源 | 与 Palantir 的重合 | Palantir 多出来的东西 | 对原力OS的启发 |
| --- | --- | --- | --- | --- | --- |
| `enterprise ontology` | 企业世界里到底有哪些对象、角色、关系、边界 | [Ontology Overview](https://www.palantir.com/docs/foundry/ontology/overview/), [Why create an Ontology?](https://www.palantir.com/docs/foundry/ontology/why-ontology), [W3C ORG Ontology](https://www.w3.org/TR/vocab-org/) | 都强调对象、关系、可解释结构 | Palantir 把对象层直接变成应用、权限、动作和运营入口 | 原力要分离 `认知 ontology` 与 `operational ontology`，不要只停留在知识分类 |
| `knowledge graph / OBDA` | 如何让异构数据带语义、可查询、可追溯 | [KG+LLM Survey](https://arxiv.org/abs/2403.03111), [LLM and KG](https://arxiv.org/abs/2308.06374) | 都强调语义层比裸数据更适合作为 AI grounding | Palantir 不只做查询与推理，还把行动和写回纳入对象层 | 原力可把 `EvidenceAtom` 设计成 grounding 单位，再映射到业务对象 |
| `digital twin / cognitive twin` | 如何把真实世界映射成可更新、可反馈的数字镜像 | [Digital Twin Review](https://www.mdpi.com/1099-4300/23/2/204), [Cognitive Digital Twin](https://link.springer.com/article/10.1007/s12559-022-10037-4), [Azure Digital Twins](https://learn.microsoft.com/en-us/azure/digital-twins/overview) | 都强调模型、实时数据、反馈 | Palantir 的 twin 更偏企业运营、决策与协作，不局限工业设备 | 原力 operational ontology 应该是“组织/任务/决策 twin”，不是“知识库镜像” |
| `decision intelligence` | 如何让决策被结构化、追踪、复盘、优化 | [Gartner 2022 D&A Trends](https://www.gartner.com/en/newsroom/press-releases/2022-03-14-gartner-identifies-top-trends-in-data-and-analytics-for-2022), [A Cognitive Digital Twin](https://link.springer.com/article/10.1007/s12559-022-10037-4) | 都强调从报表走向决策支持 | Palantir 把 decision capture、权限、行动执行和 writeback 串成闭环 | 原力要把 `DecisionRecord` 变成一等对象，而不是会后纪要副产物 |
| `agentic enterprise systems` | agent 如何在企业环境中安全调用能力、执行任务、接受约束 | [AIP Features](https://www.palantir.com/docs/foundry/aip/aip-features), [McKinsey agents](https://www.mckinsey.com/capabilities/mckinsey-digital/our-insights/why-agents-are-the-next-frontier-of-generative-ai) | 都强调 agent 不该脱离工具和权限体系 | Palantir 把 agent 直接绑到 ontology、policy、action 和 audit 上 | 原力要先把 `AgentCapability -> Policy -> Action` 走通，再谈多 agent 自治 |

## Source-Of-Truth Rules

- 关于 Palantir 的产品能力，只认官方文档与投资者材料。
- 关于共性理论，只认标准、综述、同行评审和一线研究机构公开材料。
- 关于“原力OS 应该怎么做”，全部视为设计建议，不伪装成外部共识。

## Risks

- Palantir 的很多优势来自组合和交付法，不是单篇论文能证明。
- 行业文章常常高估 agent 成熟度，必须和 Palantir 的治理闭环拆开看。
- 学术界对 enterprise ontology 的定义更宽，和 Palantir 的 operational layer 不是完全一一对应。

## Recommended Next Skill Chain

`guide-benchmark-learning -> yuanli-ontology-manager -> implementation planning`
