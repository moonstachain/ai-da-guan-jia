# Palantir + 外部研究学习手册

## 目标能力

理解 Palantir 为什么强，并把其中可复用的结构迁移到原力OS，而不是只学几个名词。

## 先说结论

Palantir 真正强的不是单独的 `Ontology`，而是把下面几层做成了一个闭环系统：

1. 异构数据接入和治理
2. 业务对象和关系的语义层
3. 基于对象层的动作与函数
4. 权限、策略、审计与写回
5. AI/agent 在受控边界里的调用
6. 极短时间内把业务人员拉进场景的 bootcamp 交付法

这使它更像一个“企业世界的操作系统”，而不是一个 BI、一个知识图谱、一个 LLM 平台，或一个数字孪生平台。

## Source-Of-Truth Rules

- `Palantir 是什么`：以官方 Foundry/AIP/Apollo/Investor materials 为准。
- `相关学术脉络是什么`：以标准、综述、同行评审为准。
- `Palantir 是否原创`：默认不做“发明者”叙事，只评估其工程组合与交付优势。
- `原力OS 如何借鉴`：一律标成 `原力OS设计建议`。

## What Can Be Asserted Safely

### 官方明示

- Palantir 把数据资产映射为 ontology objects、links、actions、applications。
- AIP 不是脱离数据和权限的聊天层，而是建立在 ontology、policy 和 tool access 之上。
- AIP bootcamps 被官方当作 time-to-value 的关键交付方式。

### 跨来源共识

- 企业级 AI 如果没有稳定语义层，很难持续 grounding。
- 决策系统如果没有 writeback 和 audit，只会停留在“看见”而不是“改变”。
- agent 要想进企业核心流程，必须绑定 policy、role、action，而不是直接拿底层数据库写权限。

### 原力OS设计建议

- 原力现有 ontology 应保持 epistemic 角色，不应被强行拉去承载 operational execution。
- 应新增 `operational ontology` 作为对象、状态、动作、权限、审计和 agent capability 的统一层。
- `EvidenceAtom` 应作为两套 ontology 的桥梁，而不是让知识对象和业务对象直接混写。

## What Must Stay Inferred

- Palantir 内部到底如何组织交付团队、模板库、行业模型，外部只能有限推断。
- AIP agent 的内部 orchestration 细节不是公开文档重点。
- Palantir 的 moat 很大一部分来自组织与销售执行，不只是技术结构。

## Risks

- 容易把 `ontology` 这个词误听成哲学本体论，导致讨论偏玄。
- 容易把 Palantir 当作“情报神话公司”，忽略其长期的平台化建设。
- 容易只借语义层，不借动作、策略、回写，最终做成“更高级的知识库”。

## Safe Handoff Condition

当且仅当下面三件事被接受，才适合进入原力OS 实现规划：

1. 接受“双 ontology”架构。
2. 接受 `DecisionRecord`、`WritebackEvent`、`AgentCapability` 进入最小公共类型集合。
3. 接受原力OS 的最小可行目标不是“全功能 Palantir”，而是“带受控动作闭环的治理操作层”。
