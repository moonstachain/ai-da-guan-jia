# Internal Collaboration Lifecycle Contract

## Purpose

Define the canonical lifecycle for one internal colleague clone from `activation` to `org-wide replication`.

This contract sits above the week-one MVP.
The MVP remains the first validated slice of the larger lifecycle.

## Scope

- Start with `1` internal colleague only
- Default role template: `ops-management`
- Default actor type: `employee`
- Default portfolio: `internal`
- Default org and tenant: `yuanli-hq`
- Default operating mode: `half-autonomous cockpit`

## Control Surfaces

- `岗位工作台`
  - the colleague sees tasks, next steps, evidence, blockers, and close-out prompts
- `总部总控舱`
  - the founder sees summary, blockers, boundary items, proposals, and score shifts
- `clone governance` internal view
  - mirrors governance tables into Feishu without replacing local canonical artifacts

## Canonical Inputs

- `register-clone`
- `train-clone`
- `review-clones --portfolio internal`
- `sync-feishu --surface clone_governance --portfolio internal`

## Canonical Local Objects

- `role-template-registry.json`
- `clone-registry.json`
- `task-runs.json`
- `training-cycles.json`
- `capability-proposals.json`
- `clone-scorecard.json`
- `alerts-decisions.json`
- `portfolio-daily-report.json`
- `portfolio-daily-report.md`

## Phase Gates

### Phase 0: Activation

Required outcomes:

- one internal `ops-management` clone exists
- the colleague has a unique `clone_id`
- the founder can see the clone in `internal portfolio`
- `clone governance` dry-run is ready

Required proof:

- `clone-registry.json`
- `clone-training-state.json`
- `portfolio-daily-report.json`
- `sync-result.json`

### Phase 1: Collaboration Habit

Required outcomes:

- the colleague uses the fixed morning / daytime / evening rhythm
- real tasks produce `closure_state + evidence + blocker`
- the system stops accepting vague “still in progress” states

Required proof:

- at least `1` real task per workday for `5` days
- at least `80%` of tasks enter explicit closure states
- at least `2` tasks land in `blocked_needs_user`

### Phase 2: Half-Autonomous Operation

Required outcomes:

- AI大管家 owns intake, compression, blocker surfacing, evidence capture, closure suggestion, and daily review
- the colleague retains business judgment and human-only boundary actions
- the founder sees fewer manual follow-ups

Required proof:

- stable `task-runs`
- stable `clone-scorecard`
- `waiting_human / blocked_*` visible in summaries
- founder follow-up frequency down by `30%+`

### Phase 3: Capability Evolution

Required outcomes:

- new methods from the colleague become explicit proposals
- the system can separate local wins from promotable shared capabilities

Required proof:

- `capability-proposals.json` contains real proposals
- proposals keep `fact vs inference` separation
- each proposal has a suggested HQ decision

### Phase 4: Shared Governance Replication

Required outcomes:

- a second internal role can onboard without copying repos or skills
- the founder compares clones from one HQ cockpit
- shared-core promotion decisions affect templates rather than one-off chats

Required proof:

- more than one internal employee clone exists
- more than one internal role template is active
- governance tables remain under one HQ bundle

## Required Monitoring Signals

The founder summary view must answer:

- who is moving
- who is blocked
- what is waiting for human approval
- which clone is improving or drifting

The founder should default to summary-first monitoring:

- noon: `waiting_human / blocked_* / 风险与决策表`
- evening: `closure_state + evidence + blocker + next training suggestion`

## Required Evolution Material Categories

Every colleague lifecycle must preserve these categories:

1. recurring task patterns
2. effective skill chains
3. distortion patterns
4. boundary patterns
5. role-method candidates

These categories must be recoverable from:

- `task-runs.json`
- `training-cycles.json`
- `capability-proposals.json`
- `clone-scorecard.json`
- `alerts-decisions.json`

## Promotion Loop

The fixed promotion path is:

`instance-local improvement -> capability_proposals -> HQ review -> promote_shared_core / keep_tenant_local / reject`

No proposal may bypass `capability-proposals.json`.

## Non-Goals

- do not treat dashboard brightness as proof of progress
- do not use GitHub as the colleague's daily work entrance
- do not copy the shared AI大管家 core per colleague
- do not grant autonomous approval, payment, publish, delete, or legal confirmation
