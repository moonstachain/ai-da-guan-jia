# Autonomy Proposal Contract

## Goal

把 `AI大管家` 的提案能力从“解释路由结果”升级为“输出带证据、带边界、可待批的 propose-only bundle”。

Phase 2 的最小目标不是自动执行，而是稳定产出：

- `hidden_state_hypothesis`
- `evidence_bundle`
- `thread_proposal`
- `initiative_decomposition`
- `skill_recruitment_suggestion`
- 明确的 `proposal_readiness`

Phase 4 的目标是在不突破边界的前提下，把 proposal 从 thread-centered 扩成组织级对象层，新增：

- `workflow_hardening_suggestion`
- `clone_training_recommendation`
- `proposal_object_map`

## Default Boundary

`建议 + 待批`

Allowed without human approval:

- generate initiative proposals
- generate thread proposals
- generate skill gap reports
- generate recruitment candidates
- persist local canonical proposal artifacts

Not allowed without human approval:

- open high-impact external threads
- publish externally
- mutate unrelated skills
- spend privileged resources implicitly
- execute strategy, initiative, or workflow changes beyond the propose-only layer

## Public Contract

### Inputs

- `user_prompt`
- `kb_answer`
- `strategic_goals`
- `initiative_registry`
- `prior_runs`
- `routing_credit`
- `auth_state`

### Middle Layer

- `hidden_state_hypothesis`
- `proposal_candidates`
- `reuse_vs_new_judgment`
- `evidence_bundle`
- `boundary_assessment`

### Outputs

- `thread_proposal`
- `initiative_decomposition`
- `skill_recruitment_suggestion`
- `workflow_hardening_suggestion`
- `clone_training_recommendation`
- `proposal_object_map`
- `blocked_reason`

### Gates

- `honesty_gate`
- `verification_gate`
- `boundary_gate`
- `human_approval`

## Hidden State Hypothesis Template

```json
{
  "primary_goal": "把当前任务压成一个低失真的 propose-only 结果",
  "goal_confidence": "high|medium|low",
  "target_goal_id": "G2",
  "target_initiative_id": "I-AUTO-001",
  "user_preference_signals": [
    "prefer_low_interruption",
    "prefer_reuse_before_new_build"
  ],
  "execution_boundary": "建议 + 待批",
  "risk_level": "low|medium|high",
  "why_now": "为什么当前最该提这个 proposal，而不是先执行别的动作",
  "misread_risk": "当前最大失真是什么"
}
```

要求：

- 只写当前 run 真正能支持的判断
- 不把推断伪装成事实
- 不把“用户说了什么”直接等同于“用户真正要什么”

## Evidence Bundle Template

```json
{
  "facts": [
    "prompt 明确提到了某个目标、initiative、边界或约束",
    "当前可复用 skill / auth / strategy object 已存在"
  ],
  "inferences": [
    "这次更适合 propose-only 而不是 direct execution",
    "最优挂载目标是哪个 goal / initiative"
  ],
  "gaps": [
    "还缺什么信息才适合进入下一阶段"
  ],
  "verification_targets": [
    "什么证据可以证明 proposal 是完整而不是漂亮"
  ],
  "source_paths": [
    "相关 contract / strategy / run artifact 路径"
  ],
  "approval_triggers": [
    "哪些动作一旦越过就必须等人批"
  ]
}
```

要求：

- `facts` 只能写当前 run 能直接证明的内容
- `inferences` 必须可追溯到 `facts`
- `gaps` 不能为空数组时，不能把 proposal 状态说成 fully verified

## Proposal Readiness

### `verified`

- proposal bundle 已完整
- `facts / inferences / verification_targets` 明确
- 当前结果仍停留在 propose-only 层
- 下一步不需要额外人类输入才能把 proposal 记账或排队

### `waiting_human`

- proposal bundle 本身已完整
- 但下一步会跨越高影响边界，必须等待人类批准
- 常见场景：
  - thread / initiative 真正升级或切换优先级
  - 外部发布
  - 登录、授权、付费、删除

### `blocked`

- 证据不足、环境缺失、权限受阻，proposal 还不完整
- 必须给出 `blocked_reason`
- 不允许把 `blocked` 伪装成“差一点完成”

## Proposal Quality Bar

Every proposal must include:

- strategic goal binding
- initiative binding or explicit no-initiative reason
- expected gain
- resource cost
- verification condition
- required skills
- explicit human approval requirement
- fact vs inference split
- boundary note
- `why_this_object`
- `why_now`
- `reuse_before_new_reason`
- `not_execute_now_reason`

## Minimum Route Output

Phase 2 之后，`route.json` 至少新增这些字段：

- `goal_id`
- `initiative_id`
- `theme_id`
- `strategy_id`
- `hidden_state_hypothesis`
- `evidence_bundle`
- `boundary_assessment`
- `proposal_candidates`
- `thread_proposal`
- `initiative_decomposition`
- `skill_recruitment_suggestion`
- `workflow_hardening_suggestion`
- `clone_training_recommendation`
- `proposal_object_map`
- `proposal_readiness`
- `blocked_reason`

## Phase 4 Object Layer

Phase 4 要求 proposal 不再只围绕 thread，而是至少能稳定覆盖 3 类组织对象：

- `skill_recruitment_suggestion`
- `workflow_hardening_suggestion`
- `clone_training_recommendation`

并通过一个总览字段 `proposal_object_map` 把单次 run 里的对象层关系落出来：

```json
{
  "thread_proposals": [],
  "initiative_decomposition": [],
  "skill_recruitment_suggestions": [],
  "workflow_hardening_suggestions": [],
  "clone_training_recommendations": [],
  "counts": {
    "thread_proposals": 1,
    "initiative_decomposition": 3,
    "skill_recruitment_suggestions": 2,
    "workflow_hardening_suggestions": 1,
    "clone_training_recommendations": 1,
    "total_objects": 5
  }
}
```

每个 proposal 对象都必须回答 4 个问题：

- 为什么是这个对象
- 为什么是现在
- 为什么复用而不是新建
- 为什么当前仍不能直接执行

要求：

- `proposal_object_map` 只汇总当前 run 已真实产出的对象
- `waiting_human` 仍然是合法收口，不代表失败
- Phase 4 完成不等于进入自动执行；边界仍是 `建议 + 待批`

## Phase 3 Governance Linkage

Phase 3 不改变 propose-only 边界，但要求 proposal 结果能被治理系统读取并影响：

- `agent-scorecard.json`
- `routing-credit.json`
- `autonomy-tier.json`

最小治理信号：

- `proposal_support_count`
- `proposal_support_rate`
- `proposal_quality`
- `proposal_target_binding_rate`
- `proposal_boundary_discipline`
- `proposal_governance_score`

要求：

- proposal quality 只能来自真实 `route.json`，不能凭口头总结补写
- `waiting_human` 不算失败；它表示边界纪律成立
- 没有 proposal 证据时，不得伪装成已接入治理
- proposal 信号可以加分，也可以卡住更高 autonomy tier，但不能直接越权执行

## Non-goals

- 不把 proposal output 直接接到静默执行
- 不用单次成功替代长期治理判断
- 不用生成数量冒充 proposal 质量
