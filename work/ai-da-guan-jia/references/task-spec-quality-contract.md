# Task Spec Quality Contract

## Purpose

Define the minimum quality standard for any `Task Spec` that Claude or another upstream planner hands to `AI大管家` / Codex for execution.

This contract exists to prevent three recurring distortions:

- treating planning language as if it were already a grounded execution spec
- treating mirror coordinates as if they were canonical objects
- asking the executor to make upstream object, boundary, or acceptance decisions on the fly

This contract is not a style guide.
It is an execution-readiness contract.

## First Principle

A high-quality Task Spec must be:

- `decision-complete`
- `object-grounded`
- `boundary-explicit`
- `verification-bearing`

If the implementer still has to decide:

- what object is being changed
- where the source of truth lives
- what counts as success
- what is out of scope
- what to do when the main path fails

then the spec is incomplete.

## Required Position in the Governance Stack

Every Task Spec must inherit the already-fixed governance order:

1. `memory-layer-contract.md`
2. `source-of-truth-contract.md`
3. this `task-spec-quality-contract.md`

That means every valid spec must respect:

- local canonical before mirror interpretation
- object family before sync destination
- explicit human boundary before execution

## Minimum Required Fields

Every execution-grade Task Spec must include the following fields or their exact semantic equivalents.

### 1. Goal and Objective

The spec must state:

- what is being changed
- why this round exists
- what outcome should be true after completion

Bad example:

- `做一下这个`

Good example:

- `把 X 对象从当前状态推进到 Y 状态，并把结果写回到 Z 目标面`

### 2. Current State

The spec must state the relevant current reality, not just the desired future.

It must distinguish:

- `confirmed current state`
- `assumptions`
- `known drift / risk`

If the current state is not verified, the spec must say so explicitly instead of pretending it is settled.

### 3. Object Family

The spec must identify the object family for the main object being changed.

Examples:

- `Task Run / Evolution Log`
- `Strategic State`
- `Clone Registry / Tenant State`
- `Governance Review`
- `Machine-side Institutional Memory`
- `Shared Startup Memory`
- `GitHub Execution Mirrors`
- `Feishu Frontstage Mirrors`

If a spec cannot name the object family, it is not ready.

### 4. Canonical Object

The spec must name the actual canonical object being changed or read.

Examples:

- a local artifact directory
- a local contract file
- a local registry file
- a specific canonical base file or schema

This field must not be replaced by a dashboard link or a mirror URL unless the task itself is about the mirror object family.

### 5. Mirror Surface

If the task touches GitHub, Feishu, dashboard, wiki, or another mirror/frontstage, the spec must name that mirror surface explicitly.

Examples:

- GitHub issue / Project item
- Feishu bitable row
- Miaoda dashboard card
- `CLAUDE-INIT.md` as shared startup memory distribution object

If there is no mirror surface, the spec should say so.

### 6. Target Location

The spec must name:

- target repo
- target file(s)
- target table(s) or target object(s), when relevant

Coordinates must be concrete enough that the implementer does not have to hunt for them.

### 7. In-Scope Changes

The spec must say exactly what should change.

This should be behavior-level, not vague intent.

Examples:

- create one contract
- update one table binding
- add one schema field
- rewrite one startup-memory section

### 8. Not-in-Scope

The spec must explicitly say what must not be changed in this round.

This prevents silent scope expansion and keeps closure auditable.

### 9. Acceptance Criteria

The spec must define success in observable terms.

At minimum it must answer:

- what files or objects should exist after completion
- what state should be true after completion
- what should be verifiable by readback, test, screenshot, API response, or local evidence

`看起来差不多对` is not an acceptance criterion.

### 10. Verification Method

The spec must define how truth will be checked.

Possible methods include:

- local file existence
- readback from canonical object
- test command
- schema validation
- API response
- mirror re-read after local write

If no verification method exists, the spec is planning-only, not execution-grade.

### 11. Human Boundary

The spec must say whether the human is needed.

If yes, it must say:

- where the human goes
- what the human clicks or confirms
- why that step belongs to the human
- what evidence the human must return

If no, it must say the round is AI-owned.

### 12. Failure Fallback

The spec must say what to do when the primary path fails.

Examples:

- keep payload locally and mark payload-only
- stop before irreversible publish
- repair mirror from canonical instead of rewriting canonical
- ask for one exact human action when authorization is missing

Without fallback, the executor is forced to invent closure logic mid-run.

### 13. Final Step / Closure Requirement

The spec must state the required close-out behavior.

At minimum this means:

- what evidence to return
- whether local memory or mirrors must be updated
- whether a handoff / payload / summary is required

If the task has no explicit final step, it is prone to pseudo-closure.

## Spec Classes

Not all Task Specs are the same.
This contract fixes three classes.

### A. Planning Spec

Used when the task is to analyze, blueprint, compare, or design rather than mutate the system.

Must include:

- decision target
- current ambiguity
- evaluation criteria
- expected output artifact

Must not pretend execution has already been approved or grounded.

### B. Execution Spec

Used when the task changes canonical files, schemas, contracts, scripts, or other concrete objects.

Must include all minimum required fields, especially:

- object family
- canonical object
- mirror surface
- acceptance criteria
- verification method
- failure fallback

### C. Mirror / Sync Spec

Used when the task updates GitHub, Feishu, dashboards, wikis, or other mirror/frontstage surfaces.

Must additionally include:

- upstream canonical object
- sync direction
- whether the mirror is stale or the canonical source is changing
- readback method after sync

A mirror spec is invalid if it does not name the upstream source object.

## Input Quality Rules

The upstream author must distinguish three states:

- `confirmed`
- `assumed`
- `superseded`

The spec must not mix them.

Specific rules:

- verified coordinates may be written as facts
- unverified coordinates must be written as assumptions or risks
- superseded objects must be marked as old rather than silently reused
- dashboard display text must never be used as the only proof of current state
- GitHub or Feishu links must not stand in for canonical object identity unless the task is explicitly about those mirror objects

## Required Object Grounding

Every execution-grade or mirror-grade spec must name at least:

- `object family`
- `canonical object`
- `mirror surface`

If any of these is missing, one of two things must happen:

- downgrade the artifact to a planning spec
- or fill the missing grounding before execution starts

## Recommended Alignment with Existing Schema

When the downstream target is `yuanli-os-claude` style Codex Task Spec, the spec should align with the existing schema fields where relevant, including:

- `round_id`
- `governance_checkpoint_ref`
- `context`
- `objective`
- `target_repo`
- `implementation_spec`
- `test_requirements`
- `acceptance_criteria`
- `not_in_scope`
- `human_boundary`
- `evidence_required`
- `evolution_expectation`

This contract does not require every spec to be serialized as that JSON schema.
It does require the same information density.

## Common Failure Modes

The following patterns make a spec low quality:

### 1. Coordinate Drift

- using old table ids
- using old repos or paths
- naming a mirror surface as if it were the live object

### 2. Mirror-as-Canonical Confusion

- treating GitHub issue state as task truth
- treating Feishu dashboard values as source-of-truth
- treating `CLAUDE-INIT.md` as a runtime ledger

### 3. Planning-as-Fact

- writing future architecture as if it already exists
- writing intended target values as if they have already been verified
- collapsing `should be` into `is`

### 4. Missing Acceptance

- saying `做一下`
- saying `同步一下`
- saying `修一下`
- without observable acceptance criteria

### 5. Blurry Human Boundary

- saying `你去点一下`
- asking the implementer to decide whether authorization is needed
- mixing AI-owned analysis with human-only irreversible actions

### 6. Mixed Planning and Execution

- half blueprint, half mutation order
- no clear statement whether the round is planning-only or execution-grade

### 7. Missing Closure

- no explicit final step
- no evidence return requirement
- no mirror or memory update instruction when one is required

## Conflict Handling

If a spec conflicts with `source-of-truth-contract.md`, the source-of-truth contract wins.

If a spec conflicts with `memory-layer-contract.md`, the memory-layer contract wins.

If a spec cannot be executed without inventing object identity, source ownership, or acceptance logic on the fly, the executor must downgrade it to:

- `planning-needed`
- `grounding-missing`
- or `mirror-source-unclear`

instead of pretending it was ready.

## Downstream Consequences

This contract imposes the following requirements on future work:

- Claude should self-check Task Specs against this contract before handing them off
- AI大管家 may reject or reclassify a spec that lacks object grounding
- mirror-sync tasks must always name their upstream canonical object
- future templates should explicitly expose:
  - object family
  - canonical object
  - mirror surface
  - acceptance criteria
  - human boundary
  - fallback

## Acceptance

This contract is working as intended when:

- a human or AI can tell whether a spec is planning, execution, or mirror-sync without guessing
- a spec can be rejected for missing object grounding before execution begins
- later specs stop confusing dashboard values, GitHub states, and canonical local objects
- later specs stop forcing the implementer to decide success criteria mid-run
- Claude can use this contract as a self-check before producing downstream execution specs
