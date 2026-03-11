# AI大管家 OpenClaw Bundle

## What it is
AI大管家 OpenClaw Bundle packages the local governance layer into a frontend-facing skill bundle for OpenClaw and Feishu.

## What users get
- A stable install prompt for OpenClaw or Feishu frontend assistants.
- A minimal tool contract for task intake, judgment, knowledge lookup, and closure.
- A credential checklist that separates install success from runtime readiness.

## Frontdesk scenes
- `给任务`: return `任务理解 / 技能链 / 验真目标 / run id`
- `做判断`: return `自治判断 / 全局最优判断 / 当前最大失真`
- `查资料`: return `原始来源 / 摘要结论 / 还缺什么`
- `收口`: return `完成情况 / 验真状态 / next iterate`
- `审批`: return `推荐方案 / 不推荐方案 / 为什么现在该由人决定`

## Runtime adapter
The runtime adapter is the local bridge script:

```bash
python3 scripts/feishu_claw_bridge.py bundle-metadata
python3 scripts/feishu_claw_bridge.py install-prompt
python3 scripts/feishu_claw_bridge.py reply-preview --input-text "帮我接个任务"
```

## Readiness model
- `已安装但未配置`
- `已配置但未验真`
- `已验真可用`

The bundle never treats a successful install as proof that Feishu, Get笔记, or knowledge APIs are already working.
