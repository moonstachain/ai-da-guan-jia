# Codex Task Spec: R1 — Operational Ontology 运行时基座

> **Round**: R1
> **六判断检查点**: codex-specs/R1-governance-checkpoint.json
> **目标仓库**: moonstachain/ai-da-guan-jia

---

## 六判断摘要

- **自治判断**: AI 可自治，不涉及授权/付款/发布/删除
- **全局最优判断**: 先把 operational ontology 的对象类型从 markdown 变成可执行的 Python 数据类，这是所有后续能力（路由、验真、写回、热图）的地基
- **能力复用判断**: 直接复用已有的 operational-ontology-v0.md 定义，不重新发明
- **验真判断**: pytest 通过 + 能创建、序列化、验证所有核心类型实例
- **进化判断**: 系统从"只有 markdown 定义"进化到"有可执行的类型系统"
- **最大失真**: 当前最大风险是只有文档没有代码——对象定义停在描述层，动作/权限/写回链无法被程序调用

## 定位

- **component_domain**: governance
- **control_level**: control
- **evolution_stage**: stage2_align_data
- **涉及的 ontology 对象**: Entity, Action, Policy, Permission, EvidenceAtom, DecisionRecord, AgentCapability, WritebackEvent

---

## 目标

把 operational-ontology-v0.md 中定义的 10 个核心类型，实现为可导入、可实例化、可序列化、可验证的 Python 数据类。这是"对象→动作→权限→写回→审计"硬链的代码基座。

---

## 要创建的文件

```
ai-da-guan-jia/
├── ontology/
│   ├── __init__.py
│   ├── types.py              # 10 个核心数据类
│   ├── validators.py         # 类型验证 + 闭环规则检查
│   └── serializers.py        # JSON 序列化/反序列化
├── tests/
│   ├── test_ontology_types.py
│   └── test_ontology_validators.py
└── schemas/
    └── operational-ontology-types.schema.json  # 从 yuanli-os-claude 同步
```

---

## 实现规格

### ontology/types.py

用 Python dataclasses 实现以下 10 个类型，每个类型必须严格对齐 operational-ontology-types.schema.json 中的字段定义：

1. **Entity** — entity_id, entity_type (枚举: task/thread/asset/skill/datasource/goal/theme/strategy/experiment/workflow), status, component_domain (枚举: governance/sales/delivery/clone), control_level (枚举: direct/control/execute), owner_mode (枚举: human/ai/shared), canonical_path

2. **Action** — action_id, action_type, target_entity_id, requires_permission (bool), policy_ref, human_boundary (bool)

3. **Policy** — policy_id, scope, rule, enforcement (枚举: hard_block/soft_warn/audit_only)

4. **Permission** — permission_id, agent_id, action_types (list), boundary (枚举: autonomous/needs_approval/forbidden)

5. **EvidenceAtom** — evidence_id, source_type (枚举: explicit_statement/behavior_trace/repeated_pattern/inference/system_output/screenshot), content, confidence (枚举: confirmed/provisional/superseded), source_ref

6. **DecisionRecord** — decision_id, decision_type, rationale, evidence_refs (list), alternatives_considered (list)

7. **AgentCapability** — agent_id, capabilities (list), limitations (list), success_rate_hint

8. **WritebackEvent** — writeback_id, target_entity_id, action_id, timestamp, result (枚举: success/partial/failed/rolled_back), evidence_ref, canonical_path

9. **Relation** — relation_id, source_entity_id, target_entity_id, relation_type

10. **State** — state_id, entity_id, state_value, timestamp, trigger_action_id

每个枚举用 Python Enum 实现。每个类型实现 `to_dict()` 和 `from_dict(cls, data)` 方法。

### ontology/validators.py

实现以下验证函数：

- `validate_entity(entity: Entity) -> list[str]`: 检查必填字段和枚举值
- `validate_action_permission(action: Action, permissions: list[Permission]) -> bool`: 检查动作是否有对应权限
- `check_closure_readiness(path_routed: bool, result_verified: bool, evolution_recorded: bool, next_captured: bool) -> bool`: 四条全 True 才返回 True
- `validate_writeback_chain(action: Action, writeback: WritebackEvent, evidence: EvidenceAtom) -> list[str]`: 检查"动作→写回→证据"链是否完整

### ontology/serializers.py

- `to_json(obj) -> str`: 把任何 ontology 对象序列化为 JSON
- `from_json(json_str: str, target_type: type) -> object`: 反序列化
- `validate_against_schema(obj, schema_path: str) -> list[str]`: 用 jsonschema 库验证

---

## 测试要求

### test_ontology_types.py

- 每个类型至少 1 个 happy-path 创建测试
- Entity 的 component_domain 和 control_level 枚举值覆盖测试
- to_dict() 和 from_dict() 往返测试（序列化后反序列化应等于原对象）

### test_ontology_validators.py

- validate_entity 对非法枚举值返回错误
- validate_action_permission 对无权限的 Action 返回 False
- check_closure_readiness 对任一条件为 False 返回 False
- validate_writeback_chain 对缺少 evidence 的链返回错误

---

## 验收标准

1. `pytest tests/ -v` 全部通过
2. 10 个核心类型均可从 Python 代码中 import 并实例化
3. 类型定义与 operational-ontology-types.schema.json 中的字段完全对齐
4. validators.py 中的闭环规则检查能正确执行
5. 不依赖任何外部服务，纯本地可运行

---

## 不做什么

- 不做 MCP Server（R2 再做）
- 不做 Feishu 同步（后续 round）
- 不做 CLI 入口改造（后续 round）
- 不做 router agent（R3 再做）
- 不修改 references/ 目录中的任何治理合同

---

## 人类边界

- 无——本轮全部是本地代码工作，不涉及不可逆动作

---

## 需要回传的证据

1. PR 链接
2. pytest 输出截图或日志
3. `from ontology.types import Entity; e = Entity(...)` 的成功执行截图

---

## 预期进化产出

- **gained**: 系统从"对象定义在 markdown 里"进化到"对象可被程序创建、验证和序列化"
- **capability_delta**: 验真力——现在可以用代码检查闭环条件是否满足，而不是靠人看文档判断
