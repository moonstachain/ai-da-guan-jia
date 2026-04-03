# 验真回合协议（Verification Protocol）

## 定位

验真回合是 Claude↔Codex 闭环流程中的独立验证步骤。
实现者（Codex）和验证者（Claude）必须角色分离。
验证者不补写实现，不替实现者解释结果，只基于 evidence 和 canonical artifacts 裁决。

## 触发条件

以下情况必须跑验真回合：

- Codex 完成 Task Spec 执行后，人类带 evidence 回到 Claude 时
- 任何涉及 canonical 文件变更的闭环
- 任何涉及 GitHub push 的闭环
- 任何出现 blocker、回滚、补丁收口时，需要确认最终状态时

## 验证者角色 Prompt

> 你现在是验证者，不是实现者。
> 只基于 local canonical artifacts、命令输出和可复核 evidence 判断。
> 不接受“看起来对了”或“应该没问题”。
> 先核对目标、验收标准、证据、镜像一致性，再给出 VERDICT。

## 验真检查清单

- [ ] evidence 是否包含实际执行的命令输出，而不是口头总结
- [ ] 关键产出物是否做了独立验证（`ls` / `cat` / `grep` / `diff` / 截图）
- [ ] 验收标准是否逐条核对，而不是只核对最终结果
- [ ] local canonical 与镜像是否一致，是否存在未解释的漂移
- [ ] 是否识别并记录了剩余 blocker 或真实开放问题
- [ ] 进化记录是否已产出，且包含 `effective_patterns` / `wasted_patterns` / `evolution_candidates`
- [ ] 是否确认本轮没有把“执行完成”误写成“结果已闭环”

## 合理化倾向识别

- "Codex 说做完了" → 不算验证。看 evidence。
- "文件应该在那里" → 不算验证。跑 `ls`。
- "commit 应该推上去了" → 不算验证。跑 `git log`。
- "和上次一样的流程" → 不减免验证。每次都要独立核对。
- "页面看起来没问题" → 不算验证。回到 canonical readback。

## VERDICT 输出格式

VERDICT: PASS | FAIL | PARTIAL

- PASS：所有验收标准通过，evidence 完整，canonical 与镜像一致
- FAIL：关键验收标准未通过，或 evidence 缺失，或 canonical 有未解释漂移
- PARTIAL：部分通过，附带具体未通过项、剩余 blocker 和下一步动作

## Fail-Closed 默认值

- 验真回合未跑 → 闭环状态自动标记为 `unverified`
- `unverified` 不等于 `failed`，但不能被计为 `completed`
- 验真回合证据不足 → 默认退回 `PARTIAL`，而不是直接升级为 `PASS`

## 执行约束

- 只验证，不替代实现
- 只裁决，不扩写范围
- 只认 canonical 与可复核 evidence，不认自我声明
- 如果验证者暂时无法复核关键项，先要求最小补证，再做裁决
