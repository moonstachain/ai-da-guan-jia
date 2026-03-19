# Task Spec Template V18

> 适用场景：`三阶段执行计划` 类任务，尤其是“建表 → 历史数据灌入 → 分析层灌入”的飞书 Base / Bitable 工作。
> 目标：把 Task Spec 写成可直接执行、可验真、可回写、可复用的版本，而不是描述性备忘录。

## 使用说明

- 先把所有 `{{PLACEHOLDER}}` 替换成当前任务的真实值。
- `confirmed / assumed / superseded` 三态必须分开写，不要混写。
- 如果任务最终要回写飞书战略任务追踪表，最后一步必须保留原文块，不要改写语义。
- 若有外部镜像、dashboard 或 wiki，只能作为 `mirror surface`，不能替代 canonical object。

## 标准骨架

# Codex Task Spec: {{TASK_TITLE}}

> **Round**: {{ROUND_ID}}
> **Task ID**: {{TASK_ID}}
> **Project ID**: {{PROJECT_ID}}
> **Priority**: {{PRIORITY}}

## 1. 任务目标

- **本轮要改变什么**：{{OBJECTIVE_CHANGE}}
- **为什么现在做**：{{WHY_THIS_ROUND}}
- **完成后应该成立什么**：{{POST_STATE}}

## 2. 当前状态

### Confirmed

- {{CONFIRMED_STATE_1}}
- {{CONFIRMED_STATE_2}}

### Assumed

- {{ASSUMPTION_1}}
- {{ASSUMPTION_2}}

### Known Drift / Risk

- {{KNOWN_DRIFT_1}}
- {{KNOWN_DRIFT_2}}

## 3. 对象边界

- **Object family**: {{OBJECT_FAMILY}}
- **Canonical object**: {{CANONICAL_OBJECT}}
- **Mirror surface**: {{MIRROR_SURFACE}}
- **Target location**: {{TARGET_LOCATION}}

## 4. 依赖与输入

- **前置依赖**: {{PREREQUISITES}}
- **输入文件 / 数据源**: {{INPUT_SOURCES}}
- **需要固定的坐标**: {{FIXED_COORDINATES}}
- **需要复用的现有产物**: {{REUSE_ARTIFACTS}}

## 5. 三阶段执行计划

### Phase 1：建表

**目标**
- 创建 Base / 表 / 字段 / 公式 / 单选项 / registry

**执行要点**
- {{PHASE1_STEPS}}

**产出**
- `table_registry.json`
- {{PHASE1_ARTIFACTS}}

**验收**
- {{PHASE1_ACCEPTANCE}}

**失败兜底**
- {{PHASE1_FALLBACK}}

### Phase 2：录入层 + 业务层数据灌入

**目标**
- 从历史源文件抽取并写入 T01-T06 或同级业务表

**执行要点**
- {{PHASE2_STEPS}}

**产出**
- {{PHASE2_ARTIFACTS}}

**验收**
- {{PHASE2_ACCEPTANCE}}

**失败兜底**
- {{PHASE2_FALLBACK}}

### Phase 3：分析层数据灌入

**目标**
- 将 JSON / 结构化 payload 写入 T07-T10 或同级分析表

**执行要点**
- {{PHASE3_STEPS}}

**产出**
- {{PHASE3_ARTIFACTS}}

**验收**
- {{PHASE3_ACCEPTANCE}}

**失败兜底**
- {{PHASE3_FALLBACK}}

## 6. 不在范围

- {{NOT_IN_SCOPE_1}}
- {{NOT_IN_SCOPE_2}}
- {{NOT_IN_SCOPE_3}}

## 7. 验收标准

- {{ACCEPTANCE_1}}
- {{ACCEPTANCE_2}}
- {{ACCEPTANCE_3}}
- {{ACCEPTANCE_4}}

## 8. 验证方法

- **本地验证**: {{LOCAL_VERIFICATION}}
- **API / 回读验证**: {{API_VERIFICATION}}
- **镜像回读验证**: {{MIRROR_VERIFICATION}}
- **异常验证**: {{ERROR_VERIFICATION}}

## 9. 人类边界

- **是否需要人类**: {{HUMAN_REQUIRED}}
- **人类要去哪里**: {{HUMAN_LOCATION}}
- **要点什么 / 确认什么**: {{HUMAN_ACTION}}
- **为什么必须人类做这一步**: {{HUMAN_REASON}}
- **回传什么证据**: {{HUMAN_EVIDENCE}}

## 10. 失败回退

- 如果主路径失败，优先：{{PRIMARY_FALLBACK_RULE}}
- 如果镜像失败，优先：{{MIRROR_FALLBACK_RULE}}
- 如果关键坐标不明确，优先：{{GROUNDING_FALLBACK_RULE}}
- 如果需要人工介入，只问一个最小问题，不扩 scope

## 11. 交付物

- {{DELIVERABLE_1}}
- {{DELIVERABLE_2}}
- {{DELIVERABLE_3}}

## 12. 最终回传

- 需要回传的 evidence: {{EVIDENCE_REQUIRED}}
- 需要写入的本地 artifact: {{LOCAL_ARTIFACTS_REQUIRED}}
- 需要同步的镜像: {{MIRROR_SYNC_REQUIRED}}
- 需要更新的 evolution / worklog: {{EVOLUTION_EXPECTATION}}

## 13. V18 强制闭环

每个 Task Spec 最后一步固定加这一段：

```md
> **最后一步：同步飞书战略任务追踪表**
> - 表: `PVDgbdWYFaDLBiss0hlcM5WRnQc / tblB9JQ4cROTBUnr`
> - 如果task_id不在表中 → batch_create
> - 如果已在表中 → batch_update（更新status和completion_date）
> - 必填: task_id, project_id, task_name, task_status, priority
```

## 14. 填写示例（三阶段 Base 类任务）

下面这组字段是最常见的三阶段 Base 任务填法，适合直接复制后替换：

- `{{OBJECT_FAMILY}}` = `Strategic state / Feishu Bitable base`
- `{{CANONICAL_OBJECT}}` = `本地 Task Spec + table_registry.json + seed payload`
- `{{MIRROR_SURFACE}}` = `飞书 Base / Wiki / 战略任务追踪表`
- `{{TARGET_LOCATION}}` = `{{WIKI_NODE}} / {{APP_TOKEN}}`
- `{{PHASE1_STEPS}}` = `建 Base，创建 12 张表，补字段类型 / 公式 / 单选项，写出 table_registry.json`
- `{{PHASE2_STEPS}}` = `从历史 Excel 提取并写入 T01-T06`
- `{{PHASE3_STEPS}}` = `将分析层 JSON 写入 T07-T10`
- `{{PHASE1_ACCEPTANCE}}` = `registry 生成且可回读，表数 / 字段数 / table_id 全部匹配`
- `{{PHASE2_ACCEPTANCE}}` = `T01-T06 记录数与 dry-run / apply 结果一致，missing key = 0`
- `{{PHASE3_ACCEPTANCE}}` = `T07-T10 全部 seed 成功，payload 与表字段一致`
- `{{LOCAL_VERIFICATION}}` = `py_compile + dry-run + apply + count check`
- `{{API_VERIFICATION}}` = `list_records / readback / upsert result`
- `{{MIRROR_VERIFICATION}}` = `飞书任务追踪表与本地 report 一致`

