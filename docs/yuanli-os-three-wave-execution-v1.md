# 原力 OS 全量推进执行计划 v1

## Summary

这轮已经从“总盘建议”进入“正式执行登记”。

- `canonical_program`: `原力OS主线收口计划`
- `program_mode`: `three_wave_execution`
- `run_id`: `yuanli-os-mainline-closure-v1`
- `thread_id`: `thread-yuanli-os-mainline-closure-v1`
- `parent_task_id`: `task-yuanli-os-mainline-closure-v1`
- `benchmark_thread`: `原力OS：宰相制度的萌芽`

母任务已经写入 repo-local intake ledger。执行总图的人工可读说明在：

- `output/ai-da-guan-jia/intake/yuanli-os-mainline-closure-v1/program-summary.md`
- `output/ai-da-guan-jia/intake/yuanli-os-mainline-closure-v1/program-control.json`

这里的默认执行原则固定为：

- 前台只保留 3 条主线
- 其余线程按 `merge / background / wait_human / defer` 处理
- 所有线程最终必须落到 `completed / blocked_needs_user / blocked_system / failed_partial / merged / deferred`

## Operational Override

这次 `task-intake` 通过现有 `AI大管家 route` 成功登记了母任务，但 route 对长计划提示词的 skill 选择更偏 `manual-first learning`。因此本轮执行以 `program-control.json` 作为运行时总控来源，而不是把 route 里自动挑出的 skill 链直接当作真实执行 owner。

含义很简单：

- `route.json / osa-card.json / delegation-plan.json` 保留为正式 intake 证据
- `program-control.json` 负责表达这次三波推进的真实执行分工、四个面板和终态合同

## Four Panels

### `frontstage_now`

当前前台只保留：

1. `原力OS-治理体系研究`
2. `原力OS-分形设计主线`
3. `原力OS-信息聚合主线`

这三条都要求：

- `window_mode = visible_stage_feedback`
- 不允许继续停在“快完成”
- 每条必须形成清晰终态

### `background_merge_queue`

这一批不再单开主会场，而是并入主线降噪：

- `原力OS-DNA宪章主线` -> 治理核心
- `原力OS-本体论/方法论主线` -> `operational ontology v0`
- `原力OS-CEO述职主线` -> OSA cockpit
- `原力OS-激励设计` -> 治理评分线
- `原力OS-使用说明书` -> 治理文档入口
- `战略思考` -> 治理核心
- `飞书知识库` -> 小石头能力线
- `多维表-仪表盘` -> dashboard execution
- `多维表+飞书编程` -> cleanup program
- `github` -> transport ops

这些线程的目标终态不是“继续开一个窗口”，而是 `merged`。

### `waiting_human_boundary`

默认列入等待真实人类边界的线程：

- `原力茶馆-小石头的大世界`
- `moltbook社区同步`
- `原力OS-CEO述职主线`

如果对应边界未补齐，不假推进，直接保持 `blocked_needs_user`。

### `deferred_after_narrowing`

当前固定只有：

- `原力星球-CBM`

继续条件固定为先收窄范围，只允许：

- `5-8` 个私教服务案例
- 或只接 `视频号` 入口

未压窄前，默认终态 `deferred`。

## Wave Contract

### Wave 1

目标：把三条主线从“有骨架”推进到“有终态”。

- `原力OS-治理体系研究`
  - 退出条件：至少一条真实 scaffold 消费试点闭环，或明确 scaffold 自身 blocker
- `原力OS-分形设计主线`
  - 退出条件：clone/human feedback 验证链跑通，或 `doctor.py` 噪音被隔离成非阻塞历史缺陷
- `原力OS-信息聚合主线`
  - 退出条件：至少一轮真实跨端 emit 成功，或清晰升级为 transport/auth 人类边界

### Wave 2

目标：只做收尾，不扩抽象。

顺序固定为：

1. `原力茶馆-小石头的大世界`
2. `康波大地图`
3. `他山之玉`
4. `原力OS-技能市场`
5. `原力OS-skill成熟度治理`

### Wave 3

目标：合并、降噪、收窄。

- 合并同源窗口
- 后台保留边界型线程
- 强制收窄 `原力星球-CBM`

## Validation

这轮计划的验真标准已经固定：

- Wave 1 结束后，前三条主线必须有明确终态
- Wave 2 每条必须表现为“收尾动作”，而不是重新发散
- Wave 3 结束后，不再让同源线程分别占多个前台窗口
- 每一波都要补一页 recap：
  - `gained`
  - `wasted`
  - `next iterate`
  - `new blockers`
