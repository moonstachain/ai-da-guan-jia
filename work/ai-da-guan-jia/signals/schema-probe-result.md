# TS-SYNC-02 Schema Probe Result
# 自动生成，勿手动编辑
# canonical: /Users/liming/Documents/codex-ai-gua-jia-01/work/ai-da-guan-jia/signals/schema-probe-result.md
# generated_at: 2026-03-18T15:07:58+08:00
# account_id: feishu-claw
# base_token: PVDgbdWYFaDLBiss0hlcM5WRnQc
# table_id: tblB9JQ4cROTBUnr
# table_name: 战略任务追踪表
# field_count: 14
# sample_count: 5

## 字段清单
| field_name | field_id | type | primary |
|---|---|---|---|
| task_id | fldhNh6ZUT | 1 | yes |
| project_id | fldODIZdUD | 1 |  |
| project_name | fldPJZBF86 | 1 |  |
| project_status | fldq5DNRag | 3 |  |
| task_name | fldUnvHk8X | 1 |  |
| task_status | fld98wYwqK | 3 |  |
| priority | fldxqoKE99 | 3 |  |
| owner | fldwvedS8y | 3 |  |
| start_date | fldoegbjZQ | 5 |  |
| completion_date | fldaIeoqRJ | 5 |  |
| blockers | fldDMXnK7j | 1 |  |
| evidence_ref | fldKatNLJ0 | 1 |  |
| dependencies | fldfPhE0Mf | 1 |  |
| notes | fldojYWj80 | 1 |  |

## 前 5 条记录样本
### Record 1
```json
{
  "fields": {
    "completion_date": 1773567000000,
    "evidence_ref": "data/skill_inventory.json",
    "notes": "已形成可复用的治理对象底册。",
    "owner": "Claude",
    "priority": "P0",
    "project_id": "R18",
    "project_name": "R18 三向量扩展 + 驾驶舱 2.0 + 康波智库",
    "project_status": "进行中",
    "start_date": 1773537600000,
    "task_id": "TS-GH-01",
    "task_name": "GitHub 盘点（5 仓 309 项分类）",
    "task_status": "已完成"
  },
  "id": "recvebaPyhvUwQ",
  "record_id": "recvebaPyhvUwQ"
}
```

### Record 2
```json
{
  "fields": {
    "completion_date": 1773624000000,
    "dependencies": "TS-GH-01",
    "evidence_ref": "yuanli-os-claude/CLAUDE-INIT.md",
    "notes": "模板化完成后，后续任务可以沿统一结构推进。",
    "owner": "Claude",
    "priority": "P0",
    "project_id": "R18",
    "project_name": "R18 三向量扩展 + 驾驶舱 2.0 + 康波智库",
    "project_status": "进行中",
    "start_date": 1773540600000,
    "task_id": "TS-V2-01",
    "task_name": "INIT 模板化",
    "task_status": "已完成"
  },
  "id": "recvebaQ9vAxZk",
  "record_id": "recvebaQ9vAxZk"
}
```

### Record 3
```json
{
  "fields": {
    "blockers": "等待黑色卫星机恢复可达，需人类完成授权侧动作。",
    "evidence_ref": "artifacts/ai-da-guan-jia/runs/2026-03-18/r18-v1-01/blocker-note.md",
    "notes": "阻塞项需要单独暴露，避免被“进度看起来还行”掩盖。",
    "owner": "人类",
    "priority": "P1",
    "project_id": "R18",
    "project_name": "R18 三向量扩展 + 驾驶舱 2.0 + 康波智库",
    "project_status": "进行中",
    "start_date": 1773796800000,
    "task_id": "TS-V1-01",
    "task_name": "卫星机治理对齐",
    "task_status": "阻塞"
  },
  "id": "recvebaQJLYX7W",
  "record_id": "recvebaQJLYX7W"
}
```

### Record 4
```json
{
  "fields": {
    "completion_date": 1773711000000,
    "dependencies": "TS-V2-01",
    "evidence_ref": "work/ai-da-guan-jia/references/feishu-task-log-base-schema.json",
    "notes": "完成多维表结构重构。",
    "owner": "Codex",
    "priority": "P0",
    "project_id": "R18",
    "project_name": "R18 三向量扩展 + 驾驶舱 2.0 + 康波智库",
    "project_status": "进行中",
    "start_date": 1773625200000,
    "task_id": "TS-DASH-01",
    "task_name": "飞书表改造（4 旧表 + 3 新表）",
    "task_status": "已完成"
  },
  "id": "recvebaRgHB4UD",
  "record_id": "recvebaRgHB4UD"
}
```

### Record 5
```json
{
  "fields": {
    "completion_date": 1773728400000,
    "dependencies": "TS-DASH-01",
    "evidence_ref": "derived/reports/cockpit-build.json",
    "notes": "核心指标已补齐，驾驶舱可稳定读到 canonical 数据。",
    "owner": "Codex",
    "priority": "P0",
    "project_id": "R18",
    "project_name": "R18 三向量扩展 + 驾驶舱 2.0 + 康波智库",
    "project_status": "进行中",
    "start_date": 1773649200000,
    "task_id": "TS-DASH-02",
    "task_name": "驾驶舱 2.0 数据补齐（26/40 canonical）",
    "task_status": "已完成"
  },
  "id": "recvebaRNAgkez",
  "record_id": "recvebaRNAgkez"
}
```

## 映射建议
| target_column | suggested_field | match_mode | rationale |
|---|---|---|---|
| task_id | task_id | exact | live field name matches the target or a known alias |
| task_name | task_name | exact | live field name matches the target or a known alias |
| task_status | task_status | exact | live field name matches the target or a known alias |
| priority | priority | exact | live field name matches the target or a known alias |
| owner | owner | exact | live field name matches the target or a known alias |
| created_time | record.created_time (system field) | system | created_time is usually a record system field rather than a normal Bitable field |

## 结论
PROBE OK: live schema reachable and field inventory captured.
