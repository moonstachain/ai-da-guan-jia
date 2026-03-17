# Source of Truth Contract

## Purpose

Define source-of-truth ownership by object family for `AI大管家`.

This contract answers one question:

`for each object family, which layer decides truth, which layers mirror it, and which surfaces only display it?`

This contract does not redefine the five-layer model.
It applies the layer model from [memory-layer-contract.md](memory-layer-contract.md) to concrete object families.

When this contract conflicts with an outer mirror or display value, the contract-assigned canonical layer wins unless verified evidence proves the canonical object is stale or wrong.

## First Principle

Source of truth is assigned by object family, not by visibility.

That means:

- the most visible value is not automatically the true value
- the most recent mirror text is not automatically the authoritative value
- the most shareable surface is not automatically the source of truth

Use this order:

1. identify the object family
2. identify the canonical layer
3. identify the canonical object
4. identify mirror layers and human-facing surfaces
5. resolve discrepancies without letting mirrors reverse-promote themselves into truth

## Object Classification Rule

Every governed object must be classified into one object family before sync, review, or dashboard interpretation.

Each object family must declare:

- `what the object is`
- `canonical layer`
- `canonical object`
- `mirror layers`
- `human-facing surface`
- `conflict rule`
- `rewrite rule`
- `notes / examples`

If an object does not clearly fit one family, do not improvise a sync rule.
Classify it first, then sync it.

## Object Families

### 1. Task Run / Evolution Log

`what the object is`

The canonical record of one meaningful run, including routing, evidence, closure, and self-evaluation.

`canonical layer`

`Layer 1 Local Canonical`

`canonical object`

The local run directory under:

- `artifacts/ai-da-guan-jia/runs/YYYY-MM-DD/<run-id>/`

including at minimum:

- `route.json`
- `evolution.json`
- `worklog.json`
- local markdown closure artifacts

`mirror layers`

- `Layer 3 GitHub Collaboration Mirror`
- `Layer 4 Human-facing Frontstage Mirror`

`human-facing surface`

- GitHub issue and closure comment
- Feishu work log row

`conflict rule`

If GitHub issue state, closure text, or Feishu work log conflicts with local run files, the local run files win.

`rewrite rule`

Fix the mirror from the local run.
Do not rewrite the local run just because a mirror was edited or displayed differently.

`notes / examples`

Examples include `github-payload.json`, GitHub closure comments, `feishu-payload.json`, and Feishu work log rows keyed by the same run identity.

### 2. Strategic State

`what the object is`

The current strategic operating-system state for goals, initiatives, active threads, registries, and governance policy outputs.

`canonical layer`

`Layer 1 Local Canonical`

`canonical object`

`artifacts/ai-da-guan-jia/strategy/current/`

including the strategic registries and governance dashboard artifacts defined by the strategic governor contract.

`mirror layers`

- `Layer 3 GitHub Collaboration Mirror`
- `Layer 4 Human-facing Frontstage Mirror`

`human-facing surface`

- roadmap summaries
- strategic docs
- frontstage governance boards

`conflict rule`

If a dashboard or doc summary disagrees with the local strategy registry, the local strategic state wins.

`rewrite rule`

Frontstage summaries may be regenerated from local strategy state.
Do not let a dashboard override mutate the strategic registry by itself.

`notes / examples`

`frontstage focus override` is a display concern; it does not become the canonical strategy registry state unless explicitly written back through the local strategic layer.

### 3. Clone Registry / Tenant State

`what the object is`

The canonical configuration and portfolio state for clone instances, org boundaries, tenant visibility, training cycles, and promotion proposals.

`canonical layer`

`Layer 1 Local Canonical`

`canonical object`

`artifacts/ai-da-guan-jia/clones/current/`

including:

- `clone-registry.json`
- `org-registry.json`
- `clone-training-state.json`
- `promotion-queue.json`
- related clone portfolio ledgers

`mirror layers`

- `Layer 4 Human-facing Frontstage Mirror`
- optional `Layer 3` summaries when needed

`human-facing surface`

- clone portfolio tables
- tenant management views
- human-facing clone management cockpit

`conflict rule`

If a frontstage clone table disagrees with the local clone registry, the local clone registry wins.

`rewrite rule`

Regenerate or re-upsert the mirror from local clone ledgers.
Do not rewrite clone configuration, memory namespace, or promotion state from a dashboard row.

`notes / examples`

Fields like `memory_namespace`, `role_template_id`, `visibility_policy`, and `manager_clone_id` are registry facts, not frontstage hints.

### 4. Governance Review

`what the object is`

The scored governance audit over governed objects, including honesty, maturity, evidence, and action candidates.

`canonical layer`

`Layer 1 Local Canonical`

`canonical object`

The local governance review artifacts, including:

- `review.json`
- governance object ledgers
- skills, workflows, agents, and components governance files

`mirror layers`

- `Layer 4 Human-facing Frontstage Mirror`

`human-facing surface`

- Feishu `治理信用总账`
- governance dashboard and assessment tables

`conflict rule`

If Feishu scores, action states, or dashboard views diverge from local governance ledgers, local governance ledgers win.

`rewrite rule`

Update the Feishu mirror from local governance artifacts after verification.
Do not treat a Feishu score or displayed status as self-authorizing evidence.

`notes / examples`

Human resolution of `A / B / C` actions may trigger a new local review state and then a new mirror sync; the human click itself is not the canonical ledger.

### 5. Machine-side Institutional Memory

`what the object is`

Durable rules, contracts, startup guidance, indexes, and machine-side memory summaries.

`canonical layer`

`Layer 2 Machine-side Institutional Memory`

`canonical object`

- `work/ai-da-guan-jia/SKILL.md`
- `work/ai-da-guan-jia/references/*.md`
- `~/.codex/memory.md`

`mirror layers`

- `Layer 3 GitHub Collaboration Mirror`
- `Layer 4 Human-facing Frontstage Mirror` when selectively surfaced

`human-facing surface`

- human-readable governance docs
- startup memory entrypoints
- shared institutional references

`conflict rule`

If this layer conflicts with Layer 1 runtime facts, Layer 1 wins on runtime truth.
If a mirror copy of this layer diverges from the local institutional version, the local institutional version wins unless explicitly promoted through governance.

`rewrite rule`

Institutional memory may summarize or point to canonical runtime facts, but must not replace them.
Mirror copies of contracts or memory indexes are rewritten from the local institutional layer, not the other way around.

`notes / examples`

`~/.codex/memory.md` is an index and recovery guide, not the raw history database.

### 6. Shared Startup Memory

`what the object is`

The shared startup memory surface used to bootstrap new strategic conversations across environments.

`canonical layer`

`Layer 2 Machine-side Institutional Memory` for source authority, with a `Layer 3` distribution object

`canonical object`

The source authority comes from the agreed local governance memory and contracts.
The primary distribution object is `CLAUDE-INIT.md`.

`mirror layers`

- `Layer 4 Human-facing Frontstage Mirror`
- conversation retellings in `Layer 5`

`human-facing surface`

- GitHub page for `CLAUDE-INIT.md`
- shared startup entrypoints
- Feishu wiki summaries of startup memory

`conflict rule`

`CLAUDE-INIT.md` is not the full-system source of truth for runtime facts.
If it conflicts with Layer 1 run facts, Layer 1 wins.
If it conflicts with local institutional memory for startup guidance, the local governance source wins until a deliberate distribution update is made.

`rewrite rule`

Update `CLAUDE-INIT.md` from agreed local governance memory.
Do not let its public visibility upgrade it into the canonical task log, runtime ledger, or full strategic registry.

`notes / examples`

This family is a special case:

- `CLAUDE-INIT.md` is not a generic mirror page
- it is a `shared startup memory distribution object`
- it has distribution authority for `what a new shared conversation should load first`
- it does not have override authority over Layer 1 runtime truth

### 7. GitHub Execution Mirrors

`what the object is`

GitHub-side execution, closure, archive, and coordination artifacts.

`canonical layer`

No GitHub object is canonical by itself.
Its source authority is inherited from the corresponding Layer 1 or Layer 2 object family.

`canonical object`

The upstream local object that the GitHub artifact mirrors.

`mirror layers`

- `Layer 3 GitHub Collaboration Mirror`

`human-facing surface`

- GitHub issues
- GitHub Projects
- GitHub payload and archive views

`conflict rule`

GitHub state is valid for collaboration and triage, not for adjudicating whether a task fact is true.
If GitHub issue state conflicts with local closure state, local closure state wins.

`rewrite rule`

Repair GitHub from the local source object or regenerate payloads.
Do not rewrite local canonical truth because a GitHub issue was edited, mislabeled, or moved.

`notes / examples`

Issue status, labels, and comments are collaboration signals.
They are not the canonical task ledger.

### 8. Feishu Frontstage Mirrors

`what the object is`

Feishu-side readable mirrors and cockpit surfaces for humans.

`canonical layer`

No Feishu object is canonical by itself.
Its source authority is inherited from the corresponding Layer 1 or Layer 2 object family.

`canonical object`

The upstream local object that the Feishu row, page, or dashboard mirrors.

`mirror layers`

- `Layer 4 Human-facing Frontstage Mirror`

`human-facing surface`

- bitable rows
- wiki pages
- Miaoda dashboards
- review tables
- cockpit cards

`conflict rule`

Displayed Feishu values do not become truth just because they are the most visible human surface.
If a Feishu mirror diverges from the assigned source object, the source object wins.

`rewrite rule`

Correct the Feishu mirror from the validated upstream source.
Only begin a canonical rewrite investigation if Feishu exposes verifiable new evidence that the local source is stale or wrong.

`notes / examples`

This family contains a second special case:

- a Feishu dashboard card value is not the object itself
- it is a `frontstage display`
- its source-of-truth must be found by first identifying the object family it is displaying
- never infer truth by starting from the card value alone

### 9. Conversation Conclusions / Thread Working Memory

`what the object is`

Thread-local judgments, summaries, plans, interpretations, and interim decisions formed during the current conversation.

`canonical layer`

`Layer 5 Conversation Working Memory` by default

`canonical object`

The current thread context and its transient conclusions

`mirror layers`

None by default

`human-facing surface`

- the current conversation

`conflict rule`

Thread confidence is not sufficient to become durable truth.
If the thread says one thing and a classified canonical object says another, the classified canonical object wins until explicit canonicalization occurs.

`rewrite rule`

Promote only after explicit canonicalization into Layer 1 or Layer 2.
Otherwise keep it as temporary working memory.

`notes / examples`

A good thread conclusion may later become:

- a local run artifact
- a validated rule
- a memory index entry

Until that happens, it remains temporary.

## Conflict Handling

Use one fixed discrepancy process for all object families:

1. identify the object family
2. locate the assigned canonical layer
3. locate the assigned canonical object
4. classify the outer-layer value as one of:
   - `stale_mirror`
   - `filtered_summary`
   - `frontstage_only_display`
   - `true_correction_signal`
5. if it is only a mirror discrepancy, repair the mirror and do not rewrite canonical
6. only start a canonical rewrite investigation if the outer layer carries verifiable evidence that the canonical object is stale or wrong

Hard prohibitions:

- `more visible` does not mean `more true`
- `more recent` does not mean `more authoritative`
- `more shareable` does not mean `source of truth`

## Sync Consequences

This contract imposes the following downstream requirements:

- `~/.codex/memory.md` must store indexes, stable state summaries, and restore order only; it must not duplicate raw run history
- `task-spec-quality-contract.md` must require specs to name at least:
  - object family
  - canonical object
  - mirror surface
- the `CLAUDE-INIT` four-layer split blueprint must use this contract to assign content destinations instead of deciding them ad hoc
- GitHub and Feishu sync flows must declare which upstream object family they mirror
- dashboard interpretation must begin from object family classification, not from card visibility

## Acceptance

This contract is working as intended when:

- future work can answer `who decides truth for this object?` without a thread-level debate
- no one can treat GitHub or Feishu as canonical merely because they are easier to read
- `CLAUDE-INIT.md` is no longer mistaken for a runtime ledger
- a dashboard discrepancy can be resolved by first locating the object family and source object
- `~/.codex/memory.md` can be written as a stable entrypoint instead of a raw history dump
- later specs can point to one object-family truth contract instead of improvising source ownership each time
