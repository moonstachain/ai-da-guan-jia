# AutoClaw / 飞书前端协作场景

> 当前面向真实日常协作的上位说明书，统一见 [docs/yuanli-os-ai-da-guan-jia-collaboration-whitepaper-v2.md](/Users/liming/Documents/codex-ai-gua-jia-01/docs/yuanli-os-ai-da-guan-jia-collaboration-whitepaper-v2.md)。  
> 如果想要一份更偏“每天直接照着用”的前后端协同手册，优先看 [docs/yuanli-os-xiaomao-ai-da-guan-jia-practical-guide-v1.md](/Users/liming/Documents/codex-ai-gua-jia-01/docs/yuanli-os-xiaomao-ai-da-guan-jia-practical-guide-v1.md)。  
> 本文档保留为前台场景与操作示例清单。

默认产品表面改为 AutoClaw 自用版；飞书只保留为可选协作前端。`AI大管家` 负责路由、验真、闭环，不抢执行层工作。

## 使用顺序

1. 先装
   - `python3 scripts/feishu_claw_bridge.py install-prompt`
2. 先用
   - 在 AutoClaw 或飞书里按连续陪伴型话术触发
   - 也可以用唤醒词 `原力原力` 开头
3. 有需要再配
   - 如要接飞书协作面，再补飞书后台连接
   - 如要直连 Get笔记，再补 Get笔记 后台连接
4. 再看状态
   - `python3 scripts/feishu_claw_bridge.py bundle-status`
   - `python3 scripts/feishu_claw_bridge.py bundle-metadata`

## 当前优先级

### P0

- `原力原力`
  - 返回：`首页 / 可用入口 / 下一步`
- `继续昨天那个`
  - 返回：`run id / 上次在推进什么 / 下一步`
- `我现在有哪些任务`
  - 返回：`任务总览 / 优先列表 / 下一步`
- `今天最该看什么`
  - 返回：`今日总览 / 先看什么 / 下一步`
- `小猫现在在推什么 / 项目现在卡哪了 / 这一小时你催了谁`
  - 返回：`本小时总判断 / 最该推进的 1 件事 / 最该你拍板的 1 件事 / 当前最大失真`
  - 只读显示最近一轮 `project-heartbeat` 工件，不在前台直接改 canonical task
  - `P猫现在在推什么` 继续兼容命中，但主叫法改成 `小猫`
- `给我接个任务`
  - 返回：`任务理解 / 技能链 / 下一步 / 人类边界 / run id`
- `帮我做判断`
  - 返回：`自治判断 / 全局最优判断 / 当前最大失真 / 下一步`
- `原力原力 记一下 xxx`
  - 返回：`记录摘要 / 下一步 / capture id`
  - 默认只落本地 canonical，不直接写 Get笔记
- `帮我查资料`
  - 返回：`原始来源 / 摘要结论 / 还缺什么 / verification status`
  - 默认先做知识源选择，不冒充已经查到答案
  - `原力原力 搜一下 xxx / 查一下 xxx / 问一下 xxx` 也会走这里
- `帮我收个口`
  - 返回：`完成情况 / 验真状态 / next iterate / run id`
- `这件事交给 PC 继续`
  - 返回：`为什么切回 PC / 接力点 / run id`

### 边缘升级

- `审批 / 要不要发 / 你建议我选哪个`
  - 返回：`推荐方案 / 不推荐方案 / 为什么现在该由人决定`
  - 保留为边界升级路径，不作为默认首页入口

## 执行模式

- `route_only`
  - 默认模式
  - 只做场景识别、路由、结构化回复、上下文续接、任务只读展示
  - `原力原力 记一下` 只做本地轻记录
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
python3 scripts/feishu_claw_bridge.py reply-preview --input-text "帮我把这件事理清并排个推进顺序"
python3 scripts/feishu_claw_bridge.py reply-preview --input-text "原力原力"
python3 scripts/feishu_claw_bridge.py reply-preview --input-text "继续昨天那个"
python3 scripts/feishu_claw_bridge.py reply-preview --input-text "原力原力 今天最该看什么"
python3 work/ai-da-guan-jia/scripts/ai_da_guan_jia.py project-heartbeat --source manual
python3 scripts/feishu_claw_bridge.py reply-preview --input-text "小猫现在在推什么"
python3 scripts/feishu_claw_bridge.py reply-preview --input-text "我现在有哪些任务"
python3 scripts/feishu_claw_bridge.py reply-preview --input-text "原力原力 记一下 明天要确认 Minutes 凭证"
python3 scripts/feishu_claw_bridge.py reply-preview --input-text "今天最该看什么"
python3 scripts/feishu_claw_bridge.py reply-preview --input-text "这件事该不该做"
python3 scripts/feishu_claw_bridge.py reply-preview --input-text "原力原力 搜一下 客户分层"
python3 scripts/feishu_claw_bridge.py reply-preview --input-text "我该先问飞书知识库、Get笔记，还是直接做 Deep Research" --execution-mode p0_assist
python3 scripts/feishu_claw_bridge.py reply-preview --input-text "把这事闭环"
```

## 设计边界

- 不把前台总控包装成“全自动代理”
- 不把聊天成功误判成任务闭环完成
- 不把飞书消息当 canonical memory
- 不和 Deep Research、Browser Agent、图片类 Skill 抢执行层工作
- 不在前期开放多人复杂协同和长事务自治

整体对比与四方分工见 [docs/autoclaw-feishu-governance-framework.md](/Users/hay2045/Documents/codex-ai-gua-jia-01/docs/autoclaw-feishu-governance-framework.md)。
