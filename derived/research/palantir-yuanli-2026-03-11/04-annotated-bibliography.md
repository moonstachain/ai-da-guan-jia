# 04. 带评语的参考文献与报告清单

## 评分口径

- `可信度`：High / Medium-High / Medium
- `相关度`：对 Palantir 解释和原力OS 迁移的直接帮助程度

## Source List

### 1. Palantir, *Platform Overview*

- 来源类型：官方文档
- 年份：持续更新
- 可信度：High
- 贡献点：定义 Foundry 的平台边界和主要构件
- 局限：偏平台总览，细节不如专题文档
- 相关度：高
- 链接：[Platform Overview](https://www.palantir.com/docs/foundry/platform-overview/overview/)

### 2. Palantir, *Ontology Overview*

- 来源类型：官方文档
- 年份：持续更新
- 可信度：High
- 贡献点：最直接解释 objects、links、actions、applications
- 局限：不会展开全部内部实现
- 相关度：极高
- 链接：[Ontology Overview](https://www.palantir.com/docs/foundry/ontology/overview/)

### 3. Palantir, *Why create an Ontology?*

- 来源类型：官方文档
- 年份：持续更新
- 可信度：High
- 贡献点：解释为什么 ontology 对业务用户有价值
- 局限：偏产品叙述，不讨论学术定义争议
- 相关度：极高
- 链接：[Why create an Ontology?](https://www.palantir.com/docs/foundry/ontology/why-ontology)

### 4. Palantir, *AIP Features*

- 来源类型：官方文档
- 年份：持续更新
- 可信度：High
- 贡献点：说明 AIP 如何把 AI 能力绑到语义层、policy 和 action 上
- 局限：不覆盖全部 agent 运行时细节
- 相关度：极高
- 链接：[AIP Features](https://www.palantir.com/docs/foundry/aip/aip-features)

### 5. Palantir, *Architecture Center Overview*

- 来源类型：官方文档
- 年份：持续更新
- 可信度：High
- 贡献点：解释架构、部署和运营是平台能力的一部分
- 局限：对业务方法论解释较少
- 相关度：高
- 链接：[Architecture Center Overview](https://www.palantir.com/docs/foundry/architecture-center/overview/)

### 6. Palantir, *Q3 2023 Business Update*

- 来源类型：投资者材料
- 年份：2023
- 可信度：High
- 贡献点：提供 AIP bootcamp 和 time-to-value 叙事
- 局限：面向投资者，有宣传倾向
- 相关度：高
- 链接：[Q3 2023 Business Update](https://investors.palantir.com/files/Palantir%20Q3%202023%20Business%20Update.pdf)

### 7. Palantir, *Reports 2024 / Events*

- 来源类型：投资者门户
- 年份：2024-2026
- 可信度：High
- 贡献点：确认公开报告节奏和最新披露入口
- 局限：不是单一分析文档
- 相关度：中高
- 链接：[Reports 2024](https://investors.palantir.com/reports-2024.html), [Events](https://investors.palantir.com/events.html)

### 8. W3C, *ORG Ontology*

- 来源类型：标准
- 年份：2014
- 可信度：High
- 贡献点：提供组织实体、角色、成员关系的标准化表达
- 局限：偏静态组织结构，不涉及动作闭环
- 相关度：中高
- 链接：[ORG Ontology](https://www.w3.org/TR/vocab-org/)

### 9. Pan et al., *Knowledge Graphs, Large Language Models and Large Multimodal Models: A Survey*

- 来源类型：学术综述
- 年份：2024
- 可信度：Medium-High
- 贡献点：系统总结 KG 与 LLM 的互补关系
- 局限：综述很多，工程落地深度有限
- 相关度：高
- 链接：[arXiv:2403.03111](https://arxiv.org/abs/2403.03111)

### 10. Zhang et al., *Large Language Models and Knowledge Graphs: Opportunities and Challenges*

- 来源类型：学术综述
- 年份：2023
- 可信度：Medium-High
- 贡献点：说明语义结构对 LLM grounding 和 reasoning 的价值
- 局限：不直接回答企业治理和动作执行问题
- 相关度：高
- 链接：[arXiv:2308.06374](https://arxiv.org/abs/2308.06374)

### 11. Jones et al., *Digital Twin: State-of-the-Art Future Challenge and Research Directions*

- 来源类型：同行评审综述
- 年份：2021
- 可信度：High
- 贡献点：总结 digital twin 的定义、组成和研究方向
- 局限：偏广义 twin，不专门针对 enterprise operations
- 相关度：高
- 链接：[Entropy 2021](https://www.mdpi.com/1099-4300/23/2/204)

### 12. Kaczmarczyk et al., *A Cognitive Digital Twin for Intelligent Decision-Making*

- 来源类型：同行评审论文
- 年份：2022
- 可信度：High
- 贡献点：把 twin 推向 intelligent decision support
- 局限：与 Palantir 相比，产品化和治理视角较弱
- 相关度：高
- 链接：[Cognitive Computation](https://link.springer.com/article/10.1007/s12559-022-10037-4)

### 13. Gartner, *Top Trends in Data and Analytics for 2022*

- 来源类型：行业研究公开声明
- 年份：2022
- 可信度：Medium-High
- 贡献点：公开提出 `decision intelligence` 作为重要趋势
- 局限：公开页面比正式研究报告更简略
- 相关度：中高
- 链接：[Gartner press release](https://www.gartner.com/en/newsroom/press-releases/2022-03-14-gartner-identifies-top-trends-in-data-and-analytics-for-2022)

### 14. McKinsey, *Why Agents Are the Next Frontier of Generative AI*

- 来源类型：行业研究文章
- 年份：2025
- 可信度：Medium-High
- 贡献点：总结 enterprise agent 从 chatbot 走向 workflow actor 的逻辑
- 局限：不是严格同行评审
- 相关度：高
- 链接：[McKinsey article](https://www.mckinsey.com/capabilities/mckinsey-digital/our-insights/why-agents-are-the-next-frontier-of-generative-ai)

### 15. Microsoft, *Azure Digital Twins Overview*

- 来源类型：平台文档
- 年份：持续更新
- 可信度：Medium-High
- 贡献点：展示主流工业平台如何实现 twin model、graph 和 live environment
- 局限：主要是平台说明，不是中立研究
- 相关度：中高
- 链接：[Azure Digital Twins Overview](https://learn.microsoft.com/en-us/azure/digital-twins/overview)

### 16. W3C, *OWL 2 Web Ontology Language Document Overview*

- 来源类型：标准
- 年份：2012
- 可信度：High
- 贡献点：提供 formal ontology language 的标准背景
- 局限：更偏知识表示，不涉及企业动作闭环
- 相关度：中
- 链接：[OWL 2 Overview](https://www.w3.org/TR/owl2-overview/)

### 17. W3C, *RDF 1.1 Concepts and Abstract Syntax*

- 来源类型：标准
- 年份：2014
- 可信度：High
- 贡献点：提供图数据模型的基础表达框架
- 局限：只提供表达基础，不回答业务执行问题
- 相关度：中
- 链接：[RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/)

### 18. W3C, *Shapes Constraint Language (SHACL)*

- 来源类型：标准
- 年份：2017
- 可信度：High
- 贡献点：提供图约束和验证机制的标准化视角
- 局限：不能替代企业级权限和动作治理
- 相关度：中
- 链接：[SHACL](https://www.w3.org/TR/shacl/)

### 19. W3C, *SPARQL 1.1 Overview*

- 来源类型：标准
- 年份：2013
- 可信度：High
- 贡献点：提供语义查询层的标准化背景
- 局限：查询强不等于 operational execution 强
- 相关度：中
- 链接：[SPARQL 1.1 Overview](https://www.w3.org/TR/sparql11-overview/)

## 综合评估

- 如果问题是“Palantir 的 ontology 还是不是传统 ontology”，最关键来源是 2、3、8。
- 如果问题是“Palantir 是否只是知识图谱换壳”，最关键来源是 2、9、10。
- 如果问题是“为什么它更像 operating system”，最关键来源是 2、4、5、6、11、12、14。

## 讨论题

1. 这些来源里，哪几篇最值得变成原力OS 的长期参考文献？
2. 你更信“标准/论文”的框架，还是更信 Palantir 的产品化组合经验？
3. 原力OS 未来要不要也维护自己的 annotated bibliography？
