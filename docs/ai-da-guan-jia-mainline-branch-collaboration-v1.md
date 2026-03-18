# AI大管家人机协作升级协议 v1

> 这是 `AI大管家` 在复杂任务中的默认编排协议。  
> 它不替代 [docs/ai-da-guan-jia-collaboration-v1.md](/Users/liming/Documents/codex-ai-gua-jia-01/docs/ai-da-guan-jia-collaboration-v1.md) 的通用协作基线，也不替代 [docs/ai-da-guan-jia-host-satellite-collaboration-v2.md](/Users/liming/Documents/codex-ai-gua-jia-01/docs/ai-da-guan-jia-host-satellite-collaboration-v2.md) 的多机边界。

## Summary

从 `2026-03-15` 开始，`AI大管家` 的默认人机协作不再只按“任务复杂不复杂”来拆，而是先判断这一步在：

- `信息维` 上对 AI 是否友好
- `能量维` 上对人类是否便宜

这套协议只做四件事：

- 让 `AI` 尽量负责 `高信息、低能量` 的工作
- 让 `人类` 尽早接手 `低信息、高能量` 的动作
- 在 `高信息、高能量` 场景里，再进入 `主线 + 支线 + 人类执行面`
- 在不值得烧 token 的地方，明确止损，而不是让我继续硬磨

默认模式固定为两种：

- `节能模式`
  - 目标是省 token
  - 优先单主线
  - 一旦遇到 `低信息 / 高能量` 动作，立刻切人类
- `并行模式`
  - 目标是提速
  - 使用 `1 主线 + 2~3 支线`
  - 你负责开窗、点击、截图回传
  - 我负责总控、分析、裁决与收口

## 信息维 × 能量维矩阵

以后默认先按这张二维矩阵路由：

- `高信息 / 低能量`
  - `AI大管家` 直接做
  - 典型任务：分析、路由、结构设计、字段契约、验证、收口
- `低信息 / 高能量`
  - 尽早切给人类
  - 典型任务：点击按钮、授权、切窗口、肉眼定位页面元素、刷新页面、补一张截图
- `高信息 / 高能量`
  - 进入 `主线 + 支线 + 人类执行面`
  - `AI` 负责分析和裁决，`人类` 负责执行面
- `低信息 / 低能量`
  - 不急着做
  - 优先挂起、合并，或顺手并入别的动作

## 什么时候进入并行模式

满足任意 `2` 条，就默认由 `AI大管家` 主动建议从 `节能模式` 升到 `并行模式`：

- 任务同时涉及多个执行面
  - 例如 repo、本地工具、飞书/妙搭、黑色卫星机、浏览器、截图
- 任务同时包含不同性质的工作
  - 例如主实现、上游数据契约分析、验证/截图、远端 readiness
- 主线里已经出现明显可并行的子问题
  - 例如 `Diagnosis / Overview / Health + Action` 这种天然可拆块
- 人类点击能显著降低摩擦
  - 例如多窗口开子线程、妙搭/飞书手动刷新、截图回传
- 预计单窗口推进超过 `20-30` 分钟，且中间会多次切上下文

## 默认拓扑

复杂度分级固定为：

- `轻度复杂`
  - `1 主线 + 2 支线`
- `中度复杂`
  - `1 主线 + 3 支线`
- `重度复杂`
  - `1 主线 + 3 支线 + 1 卫星机支线`

从 `2026-03-15` 开始，面向日常治理的默认窗口拓扑进一步固定为：

- `总控台`
  - 固定为当前窗口
  - 只负责裁决、统筹、路线、验真口径和最终收口
  - 不重新掉回实现位，不替代 `运营主线` 接日常推进
- `运营主线`
  - 固定为单独新开窗口
  - 负责承接当天主任务、主线推进、状态整理和对支线的消费
  - 不抢 `总控台` 的裁决权，不擅自改总口径
- `支线窗口`
  - 继续保持单目标合同
  - 只处理一个清晰子目标
  - 不改主线状态，不扩 scope
- `卫星机支线`
  - 仍然只做 `support / verify / read-only / 可逆` 任务
  - 不升格成新的总控台或新的运营主线
  - 不接管妙搭页面最终修复或 preview / source view 最终人工绑定

默认角色分工固定为：

- `总控台`
  - 管总体路线、优先级、stop condition、验真口径和最终收口
  - 不下沉到细碎执行
- `运营主线`
  - 管当天主线任务承接、执行编排、素材吸收和状态回传
  - 是 `总控台` 与各支线之间的第一消费面
- `支线窗口`
  - 每条只承接一个清晰子目标
  - 不抢 `总控台` 裁决权
  - 不擅自宣布 `completed`
- `人类`
  - 负责开 `运营主线` 与支线窗口
  - 承接必要点击
  - 把支线截图或结果回传 `运营主线 / 总控台`
- `卫星机`
  - 只做 `support / verify / read-only / 可逆` 任务
  - 在完全稳定前，不作为主线唯一 gating item

## 09:00 合并晨会协议

从 `2026-03-15` 开始，每天 `09:00` 的固定晨会不再只是 `skill review`，而是 `总控台 / 运营主线 / 支线` 共用的 `合并晨会`。

这轮晨会同时完成三件事：

- `总控台定盘`
  - 给出当天唯一总方向、优先级和 stop condition
- `支线编排建议`
  - 给出是否要开支线、开什么支线、哪些不值得开
- `人机协作优化提案`
  - 指出哪些动作继续由 AI 承担，哪些动作应更早切给人类

晨会固定输出必须包含且只包含这 `5` 段：

1. `总控台今日定盘`
2. `运营主线今日合同`
3. `支线编排建议`
4. `人机协作优化提案`
5. `评审吸收结果与唯一待裁决项`

这 `5` 段的含义固定为：

- `总控台今日定盘`
  - 只写今日主目标、优先级、stop condition、什么不做
- `运营主线今日合同`
  - 只写 `运营主线` 今日承接的单一主合同、交付口径、与总控台的回报节奏
- `支线编排建议`
  - 只写建议开的支线、各自单目标、是否需要卫星机支持
- `人机协作优化提案`
  - 只写对窗口协作、点击边界、切人时机的优化建议
- `评审吸收结果与唯一待裁决项`
  - 只写本轮吸收了哪些 `daily review / governance review` 信号，以及还剩哪一个最小裁决问题

## 合并晨会与既有评审的关系

`09:00 合并晨会` 不是新增一个平行入口，而是对既有评审入口的上层吸收。

- `daily review`
  - 继续承担 `skills / inventory / candidate actions` 的系统盘点
  - 但其结论不再直接作为最终晨会输出
  - 必须先被 `合并晨会` 吸收到 `总控台今日定盘` 或 `支线编排建议`
- `governance review`
  - 继续承担 `治理健康度 / 真实性 / maturity / 失真` 判断
  - 但其结论不再单独形成第二套晨会话语
  - 必须先被 `合并晨会` 吸收到 `人机协作优化提案` 或 `唯一待裁决项`
- `09:00 合并晨会`
  - 是唯一面向人类和当天执行面的正式入口
  - 它消费 `daily review` 与 `governance review`，但不与它们并列竞争注意力

## 提前求助与止损切换阈值

以后遇到页面解析、按钮识别、跨窗口操作，只要满足任意 `1` 条，就不再硬耗，而应切到人类执行面：

- 同一页面连续 `2` 次定位失败
- 预计还要继续烧 `8-10` 分钟以上
- 需要你点一下就能把信息压缩 `10` 倍以上
- 任务已经从“分析”退化成“盲试 UI”

这条规则的目标不是更快求助，而是更早识别：

- `人类易做 / AI难做`
- `继续试仍然不值 token`
- `当前瓶颈不在理解，而在能量执行面`

## 支线任务合同

`AI大管家` 给每条支线的默认输出模板固定为：

1. `本轮结论`
2. `涉及对象`
3. `最小改动方案`
4. `验收方式`
5. `唯一 blocker`

每条支线默认同时带这 `4` 个边界：

- `只做本子目标`
- `不改主线状态`
- `不擅自扩 scope`
- `遇到需要裁决的问题，只上报一个最小问题`

支线回主线时，默认只回这 `4` 件事：

- `本轮做了什么`
- `哪些结果已真实成立`
- `哪些对象仍等待外部条件`
- `需要主线裁决的唯一问题`

主线回支线时，默认只回这 `3` 件事：

- `是否认可当前局部结果`
- `是否允许继续下一批`
- `是否触发状态升级`

## 人类协作请求格式

以后当我需要你帮忙，不再说模糊的话，而是固定说清这 `4` 件事：

- `去哪里`
- `点什么`
- `为什么这一步该由你做`
- `做完回传什么`

标准格式固定为：

`请在 <页面/窗口> 执行 <动作>，这一步属于 <低信息高能量 / 高信息高能量里的执行面>，由你做比我继续解析更省；完成后请回传 <截图/文字结果/状态信号>。`

## 当前项目默认落点

下面这部分只描述当前 `phase-1` 最小闭环实验的默认编排，不是 `AI大管家` 的长期本体语言。

其中 `R2 / R3` 仅是本轮实验代号，长期系统定义见：

- [ai-da-guan-jia-top-level-blueprint-v1.md](/Users/liming/Documents/codex-ai-gua-jia-01/docs/ai-da-guan-jia-top-level-blueprint-v1.md)
- [ai-da-guan-jia-phase-1-minimum-closure-v1.md](/Users/liming/Documents/codex-ai-gua-jia-01/docs/ai-da-guan-jia-phase-1-minimum-closure-v1.md)

对当前 `phase-1` 最小闭环项目，默认编排如下：

- `主线窗口`
  - `G1` 最小闭环
  - `R2 / R3` 总控
  - 黑色卫星机支线优先级裁决
- `支线 A`
  - `Diagnosis` 上游契约
  - 真推进判定
  - 活动 / review / decision / writeback 数据面
- `支线 B`
  - `Overview` 组件失衡
  - `owner / copilot` 缺位
  - `gap` 排序与价值优先级
- `支线 C`
  - `Health + Action`
  - refresh packet
  - 验收准备
- `卫星机支线`
  - repo-local support
  - validator
  - 只读辅助
- `人类窗口`
  - 妙搭刷新
  - 飞书点击
  - 截图回传
  - 必要的多窗口协助
  - 页面执行面 republish / preview 纠偏

## 验收信号

这套协议只有满足下面这些信号，才算真的比单窗口混做更好：

- 主线窗口只谈路线、裁决、收口，不重新掉进细碎执行
- 每条支线都只有一个清晰目标，没有 scope 蔓延
- 人类知道每个窗口在做什么，也知道下一步该回哪张截图
- 每条支线都能被主线判定为 `继续 / 切换 / 冻结 / 合并`
- 相比单窗口混做，复杂任务的上下文切换更少，等待复制粘贴的阻力更低

## 窗口 Heartbeat 最小协议

从 `2026-03-15` 开始，`总控台 / 运营主线 / 支线 / 卫星机支线` 可以把最小进度外显到 repo-local heartbeat，而不是继续依赖人类做人工消息总线。

唯一 canonical 落点固定为：

- `work/ai-da-guan-jia/artifacts/ai-da-guan-jia/heartbeat/windows/current/<slug>-<hash>.json`
- `work/ai-da-guan-jia/artifacts/ai-da-guan-jia/heartbeat/windows/rounds/<slug>-<hash>/<timestamp>.json`

每条 heartbeat 至少包含：

- `window_id`
- `role`
- `current_phase`
- `last_action`
- `current_status`
- `latest_evidence_paths`
- `sole_blocker`
- `updated_at`

总控台消费时的信任边界固定为：

- `window_id / role / current_phase / last_action / current_status / sole_blocker / updated_at`
  - 视为窗口自报，只读消费
- `latest_evidence_paths`
  - 只视为证据指针
  - 只有当路径真实存在于 repo-local / local-canonical 产物面时，才算可信证据

总控台默认判定规则固定为：

- `正在推进`
  - heartbeat 新鲜，且窗口处于 `running / in_progress`
- `等待外部条件`
  - `current_status` 为 `waiting_external / waiting_user`，或 `sole_blocker` 明确存在
- `卡住`
  - `current_status=blocked`，或 heartbeat 超过停滞阈值未更新
- `疑似静默失联`
  - heartbeat 超过失联阈值未更新

最小命令固定为：

```bash
python3 work/ai-da-guan-jia/scripts/ai_da_guan_jia.py window-heartbeat write \
  --window-id ops-mainline \
  --role 运营主线 \
  --current-phase "主线推进" \
  --last-action "完成当轮状态整理并写出 run artifact" \
  --current-status running \
  --evidence work/ai-da-guan-jia/artifacts/ai-da-guan-jia/runs/2026-03-15/example-run/result.json \
  --sole-blocker none

python3 work/ai-da-guan-jia/scripts/ai_da_guan_jia.py window-heartbeat inspect
python3 work/ai-da-guan-jia/scripts/ai_da_guan_jia.py window-heartbeat govern
```

## 日内巡检与条件式自动发号施令

从 `2026-03-15` 开始，`总控台` 的日内默认顺序固定为：

1. 先跑 `window-heartbeat inspect`
2. 再看可信 `latest_evidence_paths`
3. 再决定窗口属于：
   - `继续`
   - `等待`
   - `裁决`
   - `收口`
4. 只有证据不足时，才升级成人类补充

条件式自动发号施令只允许发生在下面几类：

- `继续`
  - heartbeat 新鲜
  - 有可信 evidence
  - 当前子目标边界清晰
- `等待 -> 继续`
  - 原窗口处于 `waiting_external`
  - 但唯一 blocker 已消失，且不属于人类边界
- `裁决`
  - 当前窗口处于 `stuck`
  - blocker 属于总控可裁决的技术/范围问题
- `收口`
  - 当前窗口处于 `suspected_silent_lost`
  - 总控需要先要求窗口回报当前状态或正式收口

总控禁止自动越过下面这些边界：

- 登录、授权、支付
- 不可逆发布、删除
- 需要人类主观判断的设计/业务取舍
- 同时改动多窗口目标和总体优先级
- 证据不足时的状态升级
- 自动新开窗口

总控自动裁决命令固定为：

```bash
python3 work/ai-da-guan-jia/scripts/ai_da_guan_jia.py window-heartbeat govern
```

## Defaults

- 默认人类可以稳定支持 `3` 个支线窗口
- 默认简单任务先走 `节能模式`
- 默认复杂任务先判断是否切到 `并行模式`
- 默认页面型、点击型、授权型任务提高人类介入优先级
- 默认当前窗口是主线窗口，除非人类明确要求切换
