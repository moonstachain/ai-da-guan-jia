# 原力OS核心三件套边界定义

| 仓库 | 定位 | 包含 | 不包含 |
|------|------|------|--------|
| os-yuanli | 公开根协议 | DNA、架构决策、分层定义、公开API契约 | 运行时代码、数据、Skill定义 |
| yuanli-os-ops | 私有运行层 | pipeline脚本、日常ops、部署配置 | Skill定义、策略记忆、公开协议 |
| yuanli-os-skills-pack | 技能分发包 | 可复用Skill.md + scripts + references | 运行态数据、治理状态、ops配置 |

Status: accepted (2026-03-21)
