# 飞书 Claw Bridge

这个桥接层把飞书机器人当成 `AI大管家` 的前端入口，不接管飞书自己的 Claw 内核。

## 当前能力

- `GET /bundle/install-prompt`
  - 输出一键复制安装提示词
- `GET /bundle/metadata`
  - 输出安装包元数据、最小 tool contract、readiness 状态
- `POST /feishu/events`
  - 处理 `url_verification`
  - 处理 `im.message.receive_v1`
  - 校验时间窗
  - 校验 verification token
  - 可选校验签名 secret
- `GET /healthz`
- `POST /tools/route_task`
  - 本地调用 `AI大管家` 路由逻辑
  - 持久化 `route.json` 与 `situation-map.md`
- `GET|POST /tools/list_frontdesk_capabilities`
  - 返回前台场景、tool contract、安装状态
- `GET|POST /tools/get_run_status`
  - 读取本地 run bundle 状态
- `POST /tools/ask_knowledge`
  - 走最小知识查询接口
- `POST /tools/close_task`
  - 按当前会话状态评估收口 readiness
- `POST /tools/suggest_human_decision`
  - 输出推荐方案、反例、为什么要你拍板
- `POST /tools/frontdesk_reply`
  - 走飞书前端场景协议
  - 返回结构化文本与卡片 payload

## 环境变量

```bash
export FEISHU_APP_ID="cli_xxx"
export FEISHU_APP_SECRET="rotated_secret"
export FEISHU_EVENT_VERIFICATION_TOKEN="token_from_event_subscription"
export FEISHU_EVENT_SIGNING_SECRET=""
export AI_DA_GUAN_JIA_FEISHU_EXECUTION_MODE="route_only"
export AI_DA_GUAN_JIA_FEISHU_ROUTE_PERSIST="true"
export AI_DA_GUAN_JIA_FEISHU_SEND_CARDS="false"
```

说明：

- `FEISHU_APP_SECRET` 应使用已旋转的新密钥。
- `FEISHU_EVENT_SIGNING_SECRET` 当前是可选项；配置后桥接层会要求 `x-lark-signature`、`x-lark-request-timestamp`、`x-lark-request-nonce`。
- `AI_DA_GUAN_JIA_FEISHU_EXECUTION_MODE`
  - `route_only`：只做前端协议和路由
  - `p0_assist`：允许低风险 P0 场景执行
  - `p1_assist`：为后续 P1 场景预留

## 启动

```bash
python3 scripts/feishu_claw_bridge.py auth-check
python3 scripts/feishu_claw_bridge.py install-prompt
python3 scripts/feishu_claw_bridge.py bundle-metadata
python3 scripts/feishu_claw_bridge.py bundle-status
python3 scripts/feishu_claw_bridge.py serve --host 0.0.0.0 --port 8787
python3 scripts/feishu_claw_bridge.py reply-preview --input-text "帮我研究飞书 claw 接入"
```

安装包说明见 [docs/ai-da-guan-jia-openclaw-package.md](/Users/hay2045/Documents/codex-ai-gua-jia-01/docs/ai-da-guan-jia-openclaw-package.md)。

## 飞书侧配置

建议先按自建应用机器人模式接：

1. 在开放平台为机器人配置事件订阅地址：`POST /feishu/events`
2. 订阅 `im.message.receive_v1`
3. 配置 verification token
4. 如果租户侧开启签名 secret，再同步到 `FEISHU_EVENT_SIGNING_SECRET`

## 返回行为

收到文本消息后，桥接层会：

1. 生成本地路由工件
2. 用 `AI大管家` 选出 skill 链
3. 回发一条文本摘要
4. 可选再回发一张卡片

文本摘要默认包含：

- 原任务
- 路由技能
- 验真目标
- 本地 run id

现在还额外支持一层安装/配置分离：

- `已安装但未配置`
- `已配置但未验真`
- `已验真可用`

前端协作场景见 [docs/feishu-frontdesk-scenarios.md](/Users/hay2045/Documents/codex-ai-gua-jia-01/docs/feishu-frontdesk-scenarios.md)。

## 当前边界

- 非文本消息先返回“当前只支持文本消息”
- 事件去重只做进程内内存级去重，重启后会丢失
- 不把飞书消息当 canonical memory
- MCP 桥接未实现，这一版只落机器人事件桥接
- P1 场景当前只做预告，不默认自动执行
