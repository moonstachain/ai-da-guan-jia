# AI大管家 OpenClaw 安装包

> 如果你想先理解“原力OS 前台”和“AI大管家 后端”到底怎么分工，请先看 [docs/yuanli-os-ai-da-guan-jia-collaboration-whitepaper-v2.md](/Users/liming/Documents/codex-ai-gua-jia-01/docs/yuanli-os-ai-da-guan-jia-collaboration-whitepaper-v2.md)。

这个安装包把 `AI大管家` 收敛成一个适合飞书移动端长期共处的 `原力OS` 前台 Skill。

第一原则：它不是执行层万能代理，而是前台分流器。

## 对外暴露

- 安装层
  - 本地 bundle 路径
  - 一键复制安装提示词
- 能力层
  - `route_task`
  - `ask_knowledge`
  - `close_task`
  - `get_run_status`
  - `list_frontdesk_capabilities`
  - `suggest_human_decision`
- 使用层
  - 连续陪伴型前台场景
  - 什么时候该叫它 / 什么时候别叫它
  - readiness 状态分层

## AutoClaw-first 定位

- 该叫它的时候
  - 任务还糊，需要先压成清晰推进链
  - 你想续接上一个 run，确认现在卡在哪
  - 你想看今天最该看什么、我有哪些任务、哪些在等你拍板
  - 你要做取舍，需要边界判断
  - 你不知道该先问哪个知识源
  - 你想判断这件事能不能收口
- 不该叫它的时候
  - 已经明确要做深度研究，直接用 `Deep Research`
  - 已经明确要浏览网页或操作页面，直接用 `Browser Agent`
  - 已经明确要出图、搜图、改图，直接用图片类 Skill

## 生成安装提示词

```bash
python3 scripts/feishu_claw_bridge.py install-prompt
python3 scripts/feishu_claw_bridge.py bundle-metadata
python3 scripts/feishu_claw_bridge.py bundle-status
```

默认 `技能地址` 使用当前仓库的本地 bundle 路径；如果后续发布到稳定 URL，只需要设置：

```bash
export AI_DA_GUAN_JIA_OPENCLAW_SOURCE="https://your-stable-bundle-url"
```

## readiness 分层

- `已安装`
  - Skill 壳已经装好，可以开始本地接任务和做判断
- `可直接用`
  - 核心路径已经验真，可直接日常使用
- `需要我补后台配置`
  - 要接飞书协作面或外部知识源时，再补后台连接

## 默认前台入口

原力OS v1 在飞书里优先承接这些高频场景：

- 原力原力
- 首页
- 继续昨天那个
- 我现在有哪些任务
- 今天最该看什么
- 给任务
- 做判断
- 记一下
- 查资料
- 收口
- 这件事交给 PC 继续

`审批` 仍保留为边缘升级路径，不作为默认首页入口。

## 唤醒词

- 唤醒词是 `原力原力`
- 直接说自然语言也照常可用，不做强制迁移
- 推荐示例：
  - `原力原力 今天最该看什么`
  - `原力原力 我现在有哪些任务`
  - `原力原力 继续昨天那个`
  - `原力原力 记一下 明天要确认 Minutes 凭证`
  - `原力原力 搜一下 客户分层`

## 统一回复协议

每次前台回复都返回：

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

## 冲突治理与验真

- 冲突矩阵见 [docs/autoclaw-skill-conflict-matrix.md](/Users/hay2045/Documents/codex-ai-gua-jia-01/docs/autoclaw-skill-conflict-matrix.md)
- 自用验真清单见 [docs/autoclaw-self-validation.md](/Users/hay2045/Documents/codex-ai-gua-jia-01/docs/autoclaw-self-validation.md)
- 长期前端治理框架见 [docs/autoclaw-feishu-governance-framework.md](/Users/hay2045/Documents/codex-ai-gua-jia-01/docs/autoclaw-feishu-governance-framework.md)

详细前端场景见 [docs/feishu-frontdesk-scenarios.md](/Users/hay2045/Documents/codex-ai-gua-jia-01/docs/feishu-frontdesk-scenarios.md)。
