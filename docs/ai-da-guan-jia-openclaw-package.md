# AI大管家 OpenClaw 安装包

这个安装包把 `AI大管家` 收敛成一个适合 OpenClaw 和飞书小龙虾前端使用的能力壳。

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
  - 飞书固定 5 类 P0 场景
  - 缺配置提示
  - readiness 状态分层

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

- `已安装但未配置`
  - bundle 已存在，但缺核心凭证
- `已配置但未验真`
  - 核心凭证已存在，但尚未做 runtime smoke test
- `已验真可用`
  - 已完成 runtime 验真；当前 bridge 会在 `--verify-runtime` 时尝试做飞书鉴权检查

## 飞书前端入口

飞书小龙虾前台只承接场景，不承接内部系统复杂度：

- 给任务
- 做判断
- 查资料
- 收口
- 审批

详细前端场景见 [docs/feishu-frontdesk-scenarios.md](/Users/hay2045/Documents/codex-ai-gua-jia-01/docs/feishu-frontdesk-scenarios.md)。
