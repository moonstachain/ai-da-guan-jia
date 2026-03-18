# Memory Layer Contract

## Purpose

Define the fixed memory-layer model for `AI大管家` so that:

- canonical state is not confused with mirrors
- collaboration surfaces do not reverse-promote themselves into truth
- `memory.md`, `CLAUDE-INIT.md`, GitHub mirrors, and Feishu mirrors each keep one stable role

This contract sits above any one task, dashboard, or sync workflow.

## First Principle

The memory system is not ordered as `向上更真`.
It is ordered as:

- `向内更真`
- `向外更协作`

That means:

- the closer a layer is to local canonical artifacts, the closer it is to source of truth
- the farther a layer is toward GitHub, Feishu, or live conversation, the more it becomes a collaboration, mirror, or temporary working surface

No outer layer may claim canonical authority only because it is more visible.

## Fixed Layers

### Layer 1: Local Canonical

This is the default source-of-truth layer.

Typical objects:

- `artifacts/ai-da-guan-jia/runs/YYYY-MM-DD/<run-id>/...`
- `work/ai-da-guan-jia/artifacts/ai-da-guan-jia/...`
- local evolution records
- local strategy state
- local clone and governance state

Role:

- preserve the real execution trace
- preserve the canonical record of what truly happened
- provide the base evidence for any later sync

Allowed writers:

- local scripts
- validated local writeback flows
- human or AI edits only when they are acting on canonical local state directly

Freshness profile:

- highest truth priority
- may be less readable than outer layers
- must still outrank them when conflicts appear

### Layer 2: Machine-side Institutional Memory

This is the machine-readable and human-readable rule/index layer.

Typical objects:

- `work/ai-da-guan-jia/SKILL.md`
- `work/ai-da-guan-jia/references/*.md`
- `~/.codex/memory.md`
- stable local markdown indexes

Role:

- store durable rules, contracts, boundaries, and startup guidance
- compress local canonical reality into reusable institutional memory
- help future runs restore context without replaying raw artifacts

Allowed writers:

- human
- AI大管家
- validated auto-writeback limited to the approved surface

Freshness profile:

- durable but not raw
- should summarize or point to canonical objects, not replace them

### Layer 3: GitHub Collaboration Mirror

This is the asynchronous collaboration and distribution layer.

Typical objects:

- `yuanli-os-claude/CLAUDE-INIT.md`
- docs in shared repos
- GitHub issues
- GitHub Project items
- GitHub sync payloads and archive surfaces

Role:

- distribute shared strategic memory
- support async collaboration and archive
- expose reusable public or team-facing governance assets

Allowed writers:

- human
- AI workflows that sync from validated local state

Freshness profile:

- collaborative and shareable
- not canonical for runtime truth
- may be intentionally compressed, delayed, or filtered

### Layer 4: Human-facing Frontstage Mirror

This is the human collaboration and cockpit layer.

Typical objects:

- Feishu bitable mirrors
- Feishu wiki pages
- Miaoda dashboards
- human-facing work logs and review views

Role:

- make system state readable and operable for humans
- provide frontstage visibility and coordination
- support cockpit, management, and review workflows

Allowed writers:

- human
- API sync flows that already have a canonical local source

Freshness profile:

- highly visible
- often operationally important
- never gains truth priority merely because it is on screen

### Layer 5: Conversation Working Memory

This is the temporary thread-level memory layer.

Typical objects:

- current conversation
- current Claude/Codex thread context
- transient plans, assumptions, and interpretations

Role:

- hold the current working set
- support reasoning and short-horizon execution
- bridge a request into a real canonical or institutional record

Allowed writers:

- human
- Claude
- AI大管家

Freshness profile:

- highest immediacy
- shortest half-life
- must not silently become long-term memory

## Canonical Direction

Truth priority flows inward, not outward.

Priority order:

1. Layer 1 `Local Canonical`
2. Layer 2 `Machine-side Institutional Memory`
3. Layer 3 `GitHub Collaboration Mirror`
4. Layer 4 `Human-facing Frontstage Mirror`
5. Layer 5 `Conversation Working Memory`

Interpretation rule:

- Layer 2 may explain Layer 1
- Layer 3 and Layer 4 may mirror Layer 1 and Layer 2
- Layer 5 may propose or summarize
- none of Layers 3-5 may overrule Layer 1 merely by visibility or recency

## Sync Direction

Default allowed directions:

- `Layer 1 -> Layer 2`
- `Layer 1 -> Layer 3`
- `Layer 1 -> Layer 4`
- `Layer 5 -> Layer 1` only after explicit canonicalization
- `Layer 5 -> Layer 2` only after validation and durable relevance
- `Layer 2 -> Layer 3`
- `Layer 2 -> Layer 4` when the object is meant to be displayed or coordinated

Default prohibited reverse writes:

- `Layer 4 -> Layer 1` without explicit verification against local canonical evidence
- `Layer 3 -> Layer 1` just because GitHub has newer text
- `Layer 5 -> Layer 1` just because the current thread sounds confident
- `Layer 4 -> Layer 2` when the source is only a cockpit display
- `Layer 3 -> Layer 2` when the source is only a mirror-side rewrite

Special rule:

- a mirror discrepancy may trigger a local investigation
- it may not directly rewrite canonical local state unless the investigation proves the canonical layer is stale or wrong

## Promotion Rules

An object may be promoted from an outer layer to an inner durable layer only when all of the following are true:

1. the object is not merely thread-local commentary
2. it has durable value beyond the current run
3. it has either direct evidence or a clear pointer to evidence
4. its destination layer is explicit
5. its role is clear: `rule`, `index`, `summary`, `mirror`, or `canonical record`

Promotion examples:

- a repeated execution lesson can become a validated rule in `references/`
- a stable startup recovery summary can become `~/.codex/memory.md`
- a task closure recap can become a GitHub issue update or Feishu mirror after local logging exists

Non-promotion examples:

- speculative diagnosis from a thread
- a dashboard value with no local proof
- an unverified table coordinate copied from a message
- a one-off planning sentence with no lasting governance value

## Read Order

Default restore order for meaningful work:

1. current request and current thread constraints
2. relevant local canonical artifacts if the task is stateful
3. relevant institutional memory such as `references/*.md` and `~/.codex/memory.md`
4. GitHub mirrors if shared context is needed
5. Feishu mirrors if human-facing operational context is needed

This order may be narrowed by task, but outer layers should not be read first by default when local truth is needed.

## Freshness and Conflict

When two layers disagree:

1. identify the object type
2. identify the contract-assigned source-of-truth layer
3. verify whether the outer-layer value is a stale mirror, filtered summary, or true correction signal
4. only rewrite inward after verification

Conflict rule:

- `more recent` does not automatically mean `more true`
- `more visible` does not automatically mean `more authoritative`
- `more shareable` does not automatically mean `more canonical`

## Required Consequences

This contract imposes the following design consequences:

- `~/.codex/memory.md` must be an index and recovery layer, not a replacement for Layer 1
- `CLAUDE-INIT.md` must remain a shared startup memory surface, not a full runtime ledger
- GitHub issues and Projects must be treated as execution mirrors, not the canonical task log
- Feishu dashboards must be treated as frontstage displays that depend on validated upstream sync
- conversation conclusions must be explicitly canonicalized before they become long-term memory

## Acceptance

This contract is working as intended when:

- future documents stop mixing `canonical`, `mirror`, and `frontstage`
- `memory.md` can be built without pretending to be the raw history database
- later contracts can point to one fixed memory-layer model instead of redefining it
- no one can reasonably claim that GitHub or Feishu became source of truth merely because it was easier to read
