# 02. Palantir 方法论全栈拆解

## 判断标签说明

- `官方明示`：可直接由官方文档或投资者材料支持
- `跨来源共识`：学术/行业研究和官方材料一致指向
- `原力OS设计建议`：基于前两者做的迁移判断

## 1. 数据接入与治理

- `官方明示`：Palantir 平台把异构数据接进统一平台，保留 lineage、security 和 transformation。
- `跨来源共识`：企业 AI 的第一难点从来不是模型，而是数据世界不统一。
- `原力OS设计建议`：原力OS 的输入不应只是聊天记录，还要把任务、技能、线程、晨会 review 当作结构化资产。

## 2. `Ontology` 作为对象世界

- `官方明示`：Ontology 把数据资产映射成业务对象、关系和操作入口。
- `跨来源共识`：enterprise ontology、knowledge graph、digital twin 都说明“对象层”是语义稳定性的关键。
- `原力OS设计建议`：保留现有 epistemic ontology，新增 operational ontology。

## 3. Action / Function / Workflow

- `官方明示`：Palantir 把 action 和 function 直接挂在 object context 上。
- `跨来源共识`：没有 action binding 的语义层，通常只服务分析，不服务改变。
- `原力OS设计建议`：每个关键对象类型都要能声明可执行动作和可触发函数，而不是把操作逻辑散落到脚本里。

## 4. 应用层和场景层

- `官方明示`：Foundry 支持在 ontology 之上构建运营应用。
- `跨来源共识`：真正落地的系统必须面向场景和角色，不是只面向数据工程师。
- `原力OS设计建议`：原力OS 的 UI/automation/CLI 都要被看成 operational views，而不是平行散件。

## 5. AI / Agent 层

- `官方明示`：AIP 的 agent、tooling、semantic layer、policy enforcement 是一体设计。
- `跨来源共识`：企业 agent 只有在 grounding、tool access、policy 和 audit 都存在时才可控。
- `原力OS设计建议`：先建 `AgentCapability -> Policy -> Action`，再谈多 agent。

## 6. 权限、治理、审计

- `官方明示`：Palantir 强调 security model、role-aware access、审计和 policy。
- `跨来源共识`：这类系统一旦碰到真实执行和 AI，权限与可追责性就变成底层能力，不是附加项。
- `原力OS设计建议`：至少给每个 action 和 writeback 绑定 actor、policy、审批边界和 evidence。

## 7. 部署与运营

- `官方明示`：Architecture Center 和 Apollo 说明部署、版本、环境管理是平台的一部分。
- `跨来源共识`：企业平台如果不能稳定部署和运营，就会沦为咨询项目或 demo。
- `原力OS设计建议`：后续实现时，把 local canonical、Feishu mirror、automation runtime 视作多环境治理问题。

## 8. 交付方法

- `官方明示`：AIP bootcamp 被官方用作快速形成业务价值的机制。
- `跨来源共识`：time-to-value 在 enterprise AI 里比“功能列表更长”更重要。
- `原力OS设计建议`：原力OS 应采用 `small hard use case -> shared objects -> action loop -> review` 的 bootcamp 式推进。

## 为什么这是一套体系而不是散件

Palantir 的壁垒不在某个单点，而在组合顺序：

1. 先接数据
2. 再对象化
3. 再绑定动作
4. 再给应用和人用
5. 再把 AI/agent 接进来
6. 全程受权限、审计和部署体系约束

这套顺序避免了两个常见失败：

- 先上 AI，后来发现没有稳定对象世界
- 先做数据平台，后来发现没有动作闭环

## 讨论题

1. 原力OS 当前最缺的是对象层、动作层，还是权限层？
2. 你是否接受 `DecisionRecord` 也变成一等对象，而不是只在 Markdown 里留痕？
3. 如果只做 ontology 而不做 action binding，会不会重演“认知很清楚，系统改不动”的老问题？
4. 原力OS 是否需要自己的小型 bootcamp 交付法？
