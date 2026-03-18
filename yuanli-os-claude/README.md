# 原力OS-Claude

> Claude 策略大脑 × Codex 执行引擎 × 人类共同治理者

这个仓库是原力OS生态系统的**战略中枢**。它不执行代码，不部署服务，它只做一件事：

**把治理思想变成可执行的工程规格，然后通过 Codex 落地到各个仓库。**

## 一句话定义

```
yuanli-os-claude = 原力OS 的策略层 canonical + Claude↔Codex 的桥接协议
```

## 它在整个生态里的位置

```
原力OS 生态系统
├── os-yuanli/                 # 上位总纲：治理OS 三原则 + 工作OS 三层 + 3×3 矩阵
├── ai-da-guan-jia/            # 治理内核：六判断 + 路由 + 闭环 + 进化
├── yuanli-os-claude/          # 👈 你在这里：策略层 + Codex 桥接
├── yuanli-os-ops/             # 运营层：飞书前台 + 小猫推进器 + runtime
├── yuanli-os-skills-pack/     # 技能层：domain skill 集合
└── github-feishu-sync/        # 工具层：GitHub↔飞书同步
```

## 为什么需要这个仓库

在原力OS生态里，ai-da-guan-jia 定义了"怎么治理"，os-yuanli 定义了"什么是治理"。
但有一个问题一直没被正式解决：

**谁来把治理决策翻译成工程任务，并且保证翻译过程本身也是可审计、可进化的？**

答案是这个仓库。它负责：

1. **存储 Claude 的战略输出**：每一轮策略思考的 canonical 版本
2. **生成 Codex Task Spec**：让 Codex 可以在其他仓库里精确执行
3. **回收执行证据**：Codex 完成后的 PR、测试结果、进化记录
4. **维护跨轮进化链**：gained / wasted / next iterate 真正变成参数更新

## 核心工作流

```
┌─────────────┐     task spec      ┌─────────────┐
│   Claude     │ ──────────────────→│   Codex      │
│ (策略大脑)    │                    │ (执行引擎)    │
│              │←──────────────────│              │
└──────┬───────┘    evidence        └──────┬───────┘
       │                                   │
       │ designs                           │ executes on
       ↓                                   ↓
 yuanli-os-claude/              target repos:
 ├── strategy/                  ├── ai-da-guan-jia/
 ├── codex-specs/               ├── yuanli-os-ops/
 └── evolution-log/             └── yuanli-os-skills-pack/
       ↑                                   │
       │          reviews + bridges         │
       └────────── 人类 (共同治理者) ─────────┘
```

## 仓库结构

```
yuanli-os-claude/
├── README.md                          # 本文件
├── STRATEGY.md                        # Claude 对原力OS的完整战略理解
├── specs/                             # Claude↔Codex 协议与执行规范
│   └── parallel-execution-protocol.md
├── strategy/                          # 每轮战略产物
│   ├── R1-canonical-mcp.md
│   ├── R2-skill-schema.md
│   └── ...
├── schemas/                           # 可执行的治理 schema
│   ├── governance-checkpoint.schema.json
│   ├── skill-manifest.schema.json
│   ├── codex-task-spec.schema.json
│   └── evolution-log.schema.json
├── codex-specs/                       # 给 Codex 的 Task Spec（可直接粘贴）
│   ├── R1-canonical-mcp-server.md
│   └── ...
├── references/                        # 从其他仓库同步的治理合同
│   └── ecosystem-map.md
├── evolution-log/                     # 每轮 gained/wasted/next
│   └── .gitkeep
└── scripts/                           # 辅助脚本
    ├── update_init.sh
    └── validate-schemas.py
```

## 怎么用

### 开始新一轮

在 Claude 里说：
> "开始 Round N，请输出完整的 Codex Task Spec"

Claude 会：
1. 跑六判断
2. 输出架构设计
3. 生成一份符合 `codex-task-spec.schema.json` 的 Task Spec
4. Task Spec 存入 `codex-specs/`

### 执行

你把 Task Spec 粘贴到 Codex，指定目标仓库执行。

### 回流

Codex 完成后，你把执行结果（PR 链接 + 任何报错）带回 Claude。
Claude 做验真，输出 `evolution-log/RN-evidence.json`。

## 关键 Schema

### governance-checkpoint.schema.json

每轮任务必须先过的六判断 gate：

```json
{
  "autonomy": "AI 可自治 / 需人工边界",
  "global_optimum": "当前路径是否全局最优",
  "capability_reuse": "是否优先复用已有能力",
  "verification": "什么证据才算完成",
  "evolution": "这轮结束后沉淀什么",
  "max_distortion": "当前最大失真点"
}
```

### codex-task-spec.schema.json

给 Codex 的标准任务格式：

```json
{
  "round_id": "R1",
  "objective": "一句话目标",
  "target_repo": "moonstachain/ai-da-guan-jia",
  "files_to_create": ["path/to/file.py"],
  "implementation_spec": "详细实现要求",
  "test_requirements": "测试用例要求",
  "acceptance_criteria": "可验证的完成标准",
  "not_in_scope": "明确不做什么",
  "human_boundary": "哪些动作需要人类批准",
  "evidence_required": "需要回传什么证据"
}
```

## 与其他仓库的关系

| 仓库 | 关系 | 数据流方向 |
|------|------|-----------|
| os-yuanli | 读取总纲作为策略输入 | os-yuanli → claude |
| ai-da-guan-jia | 读取治理合同 + 输出工程任务 | 双向 |
| yuanli-os-ops | 通过 Codex Task Spec 下发执行 | claude → ops |
| yuanli-os-skills-pack | 通过 Codex Task Spec 下发执行 | claude → skills |
| github-feishu-sync | 镜像同步（不直接交互） | 间接 |

## 如果只记住三句话

1. **Claude 出策略，Codex 执行，你是桥接器和最终审批者。**
2. **Task Spec 是唯一合同，每轮只有一份，不含糊。**
3. **没有证据回流的执行不算闭环。**
