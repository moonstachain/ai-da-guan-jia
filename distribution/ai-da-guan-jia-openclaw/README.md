# AI大管家 OpenClaw Bundle

## What it is
原力OS OpenClaw Bundle packages the local governance layer into a Feishu-ready mobile frontend companion.

## What users get
- A continuous companion frontend that handles task intake, resume, daily focus, my tasks, judgment, knowledge-source choice, and closure readiness.
- A minimal tool contract that keeps AI大管家, Deep Research, Browser Agent, and image skills as downstream executors.
- A user-facing readiness model that separates "installed" from "ready" and "needs backend wiring".

## Frontdesk scenes
- `首页`
- `给任务`
- `继续上次`
- `我的任务`
- `今日重点`
- `做判断`
- `查资料`
- `收口`
- `交给 PC`
- `审批边界`

The bundle returns one unified reply contract for every scene:

- `scene`
- `status`
- `run_id`
- `session_id`
- `summary`
- `next_step`
- `human_boundary`
- `verification_status`
- `text`
- `card`

## Runtime adapter
The runtime adapter is the local bridge script:

```bash
python3 scripts/feishu_claw_bridge.py bundle-metadata
python3 scripts/feishu_claw_bridge.py install-prompt
python3 scripts/feishu_claw_bridge.py reply-preview --input-text "帮我接个任务"
```

## Readiness model
- `已安装`
- `可直接用`
- `需要我补后台配置`

The bundle never treats a successful install as proof that Feishu, Get笔记, or external knowledge connectors are already working.
