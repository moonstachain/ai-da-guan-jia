# OSA 接口字段映射 v1

本附录定义 OSA 如何映射到现有治理接口。

v1 先固定字段与语义，不要求本轮直接改运行时脚本。

## 1. route / situation-map

`route` 是 OSA 的入口载体，必须承载以下内容：

| OSA 段落 | route 应承载的字段 |
| --- | --- |
| 六个治理判断 | `autonomy_judgment` `global_optimum_judgment` `capability_reuse_judgment` `verification_judgment` `evolution_judgment` `current_max_distortion` |
| 原目标对齐 | `origin_goal_alignment` |
| 战略目标对齐 | `strategic_goal_alignment` |
| 任务目标定义 | `task_goal_definition` |
| 失真边界 | `distortion_boundary` |
| 路径决策 | `path_decision` |
| 验真目标 | `verification_target` |
| 推荐能力链 | `recommended_skill_chain` |
| 管控节点 | `control_gates` |

### route 默认输出要求

- 必须能看出三层目标不是断裂的
- 必须能看出为什么选当前 skill 链
- 必须带验真目标
- 若 skill 数量超过 3，必须附带解释

## 2. strategy-governor

`strategy-governor` 是 OSA 的纵向对齐层，负责把任务挂回上层目标。

| OSA 段落 | strategy-governor 应承载的字段 |
| --- | --- |
| 原目标对齐 | `origin_goal` `recursive_value` |
| 战略目标对齐 | `goal_id` `strategic_goal` |
| 任务目标定义 | `task_id` `task_title` `thread_id` |
| 全局最优判断 | `global_optimum_judgment` |
| 自治判断 | `autonomy_judgment` |
| 进化判断 | `evolution_judgment` |

### strategy-governor 默认输出要求

- 能看出 `原目标 -> 战略目标 -> 线程/任务` 的链路
- 能看出这是一次局部执行，还是一次值得升级为 initiative 的线程
- 能看出自治层级是否需要保持 `建议 + 待批`

## 3. review / close-task

`review` 与 `close-task` 是 OSA 的收尾层，负责判断“是否真闭环”。

| OSA 段落 | review / close-task 应承载的字段 |
| --- | --- |
| 验真目标 | `verification_target` `evidence` |
| 结果是否达成 | `result_status` |
| gain | `gain` |
| waste | `waste` |
| next iterate | `next_iterate` |
| rule candidate | `rule_candidate` |
| 当前最大失真 | `current_max_distortion` |

### review 默认输出要求

- 不允许只有“做完了”，必须有证据状态
- 不允许只写 gain，不写 waste
- 不允许 next iterate 为空但仍声称完成递归闭环

## 4. 推荐 OSA Card 结构

OSA Card 的标准机器结构固定为：

1. `task_context`
2. `governance_judgments`
3. `objective`
4. `strategy`
5. `action`
6. `closure_gate`
7. `interface_projection`

对应 schema 见 `specs/osa/osa-card.schema.json`。

## 5. 固定实现边界

- v1 只固定结构、字段语义、样例和验证
- v1 不要求立即改现有 route / review / strategy-governor 脚本
- 后续若进入脚本改造，应优先保持字段名与本附录一致
