# AI大管家 技能层清单

## 23 个 Core Skills（inventory core）

### 治理/元层
1. `ai-da-guan-jia` — 治理中枢
2. `ai-metacognitive-core` — 元认知核心
3. `jiyao-youyao-haiyao` — 递进式需求提炼
4. `jiyao-youyao-haiyao-zaiyao` — 递进式需求提炼（扩展版）
5. `skill-creator` — 技能创建器
6. `skill-trainer-recursive` — 递归技能训练
7. `guide-benchmark-learning` — 基准学习引导
8. `knowledge-orchestrator` — 知识编排器
9. `self-evolution-max` — 自我进化最大化
10. `openai-docs` — OpenAI 文档技能
11. `openclaw-xhs-coevolution-lab` — 共进化实验室

### 运行/连接层
12. `agency-agents-orchestrator` — 多Agent编排
13. `agency-design` — 设计Agency（含7个成员skill）
14. `agency-engineering` — 工程Agency（含6个成员）
15. `agency-engineering-rapid-prototyper` — 快速原型
16. `agency-marketing` — 营销Agency（含8个成员）
17. `agency-project-mgmt` — 项目管理Agency（含5个成员）
18. `agency-support` — 支持Agency（含6个成员）
19. `agency-testing` — 测试Agency（含7个成员）

### AI大管家 主壳/数据连接
20. `feishu-bitable-bridge` — 飞书多维表桥接
21. `feishu-km` — 飞书知识管理
22. `get-biji-transcript` — 笔记转写获取
23. `yuanli-knowledge` — 原力知识库（含3个成员）

## 7 个 Umbrella/Merged Groups

这 7 个 umbrella skill 下面吸收了 42 个 legacy member skills：
- agency-design → 7 个成员
- agency-engineering → 6 个成员
- agency-marketing → 8 个成员
- agency-project-mgmt → 5 个成员
- agency-support → 6 个成员
- agency-testing → 7 个成员
- yuanli-knowledge → 3 个成员

routing 上优先使用 umbrella 入口。

## 24 个 Adjacent Helper Skills

### 路由/评审/任务规格
- routing-playbook, skill-audit, skill-pattern-publisher, task-spec, collab-sync, evolution-log

### Feishu/Web/Platform
- feishu-reader, feishu-open-platform, feishu-dashboard-automator, github-feishu-sync, opencli-platform-bridge, playwright, playwright-interactive

### Yuanli/知识/内容
- yuanli-core, yuanli-ontology-manager, yuanli-status, yuanli-xiaoshitou, yuanli-zsxq-coevolution-assistant

### 业务/GitHub/其他
- business-structure-designer, github-skill-naming-audit, github-usage-expert, ai-da-guan-jia-prompt

## Contract-backed Capabilities（非独立skill）

- `strategy-governor`：contract-backed capability，主载体在 references/strategic-governor-contract.md
- `skill-router`：吸收式能力
- `evidence-gate`
- `closure-evolution`
- `intent-grounding`
- `human-ai-collab-loop`

## 平台级依赖

新环境先验证可用：skill-creator, skill-installer
