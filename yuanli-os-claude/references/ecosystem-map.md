# 原力OS 生态系统地图

> 本文件记录所有仓库的定位、关系和数据流方向。
> 由 Claude 维护，人类审批后更新。

## 仓库清单

| 仓库 | 定位 | 对应原力OS层 | canonical 类型 |
|------|------|-------------|---------------|
| `os-yuanli` | 上位总纲 | 治理OS 定义层 | 理论 canonical |
| `ai-da-guan-jia` | 治理内核 | 治理OS 执行层 | 系统 canonical |
| `yuanli-os-claude` | 策略中枢 | 策略层 + 桥接层 | 策略 canonical |
| `yuanli-os-ops` | 运营层 | 工作OS 前台 + 推进 | 运营 canonical |
| `yuanli-os-skills-pack` | 技能集合 | 工作OS 执行层 | 技能 canonical |
| `github-feishu-sync` | 同步工具 | 镜像层 | 工具 canonical |

## 数据流

```
os-yuanli (总纲)
    ↓ 理论输入
ai-da-guan-jia (治理内核) ←→ yuanli-os-claude (策略中枢)
    ↓ 路由指令                    ↓ Task Spec
yuanli-os-ops (运营)          Codex 执行目标仓库
    ↓                              ↓
yuanli-os-skills-pack (技能)    PR + evidence
    ↓                              ↓
证据 → 回流 → yuanli-os-claude/evolution-log/
```

## 关键约束

1. **本地 canonical 优先**：所有仓库的本地版本是真相源，GitHub 是归档镜像
2. **单向 Task Spec**：Claude 只通过 Task Spec 向 Codex 下发任务，不直接修改目标仓库
3. **证据必须回流**：Codex 的执行结果必须被 Claude 验真后才算闭环
4. **人类是桥接器**：Claude↔Codex 之间的 Task Spec 传递由人类完成，确保不可逆动作的人类边界
