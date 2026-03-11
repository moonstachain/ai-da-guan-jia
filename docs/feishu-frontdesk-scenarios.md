# 飞书前端协作场景

飞书龙虾只做协作前端，`AI大管家` 负责路由、验真、闭环。

## 使用顺序

1. 先装
   - `python3 scripts/feishu_claw_bridge.py install-prompt`
2. 再配
   - 先补 `FEISHU_APP_ID / FEISHU_APP_SECRET`
   - 如需 Get笔记，再补 `GET_BIJI_API_KEY / GET_BIJI_TOPIC_ID`
3. 再用
   - 在飞书里按固定 5 类话术触发
4. 再看状态
   - `python3 scripts/feishu_claw_bridge.py bundle-status`
   - `python3 scripts/feishu_claw_bridge.py bundle-metadata`

## 当前优先级

### P0

- `给我接个任务`
  - 返回：`任务理解 / 技能链 / 验真目标 / run id`
- `帮我做判断`
  - 返回：`自治判断 / 全局最优判断 / 当前最大失真`
- `帮我查资料`
  - 返回：`原始来源 / 摘要结论 / 还缺什么`
- `帮我收个口`
  - 返回：`完成情况 / 验真状态 / next iterate`
- `审批 / 要不要发 / 你建议我选哪个`
  - 返回：`推荐方案 / 不推荐方案 / 为什么现在该由人决定`

### P1

- `今天最该看什么`
  - 当前只做预告，不默认自动执行 `review-skills` / `review-governance` / `strategy-governor`

## 执行模式

- `route_only`
  - 默认模式
  - 只做场景识别、路由、结构化回复
  - 不直接执行知识查询或 closure apply
- `p0_assist`
  - 开放 P0 里的低风险读路径
  - 允许直接跑 `Get笔记 ask/recall`
  - 允许生成 `ask.feishu` 手动提问包
  - 只有存在足够证据时，才允许尝试 closure
- `p1_assist`
  - 预留给后续 P1 能力

## 本地预览

```bash
python3 scripts/feishu_claw_bridge.py install-prompt
python3 scripts/feishu_claw_bridge.py bundle-status
python3 scripts/feishu_claw_bridge.py reply-preview --input-text "帮我研究飞书 claw 接入"
python3 scripts/feishu_claw_bridge.py reply-preview --input-text "这件事该不该做"
python3 scripts/feishu_claw_bridge.py reply-preview --input-text "帮我查飞书知识库里关于客户分层的结论" --execution-mode p0_assist
python3 scripts/feishu_claw_bridge.py reply-preview --input-text "把这事闭环"
```

## 设计边界

- 不把飞书前端包装成“全自动代理”
- 不把聊天成功误判成任务闭环完成
- 不把飞书消息当 canonical memory
- 不在前期开放多人复杂协同和长事务自治
