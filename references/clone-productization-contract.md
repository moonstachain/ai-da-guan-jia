# Clone Productization Contract

## Purpose

Define how `AI大管家` becomes a product line that can be reused by colleagues, strategic partners, and clients without copying the shared core.

This contract is the bridge between:

- the shared governance core in `AI大管家`
- the onboarding / operating manual in `原力龙虾`
- the canonical clone registry / training / review contracts already in `references/`

## Product Thesis

The product is not a generic chat assistant.
The product is a `shared core + Clone Kit + configured instance` system.

- `shared core`
  - one canonical `AI大管家` governance kernel
  - one route / evolution / worklog closure path
  - one source-of-truth contract
  - one review and proposal discipline
- `Clone Kit`
  - reusable templates, prompts, roles, and playbooks
  - activation / onboarding copy
  - instance registry and mirror contracts
  - visibility and boundary presets
- `configured instance`
  - a tenant- or role-specific clone created from the kit
  - isolated by `memory_namespace`
  - differentiated by `role_template_id`, `visibility_policy`, `service_tier`, and manager boundary

## Product Ladder

The rollout order is fixed:

1. `internal colleague clone`
2. `strategic partner clone`
3. `client clone`

The later two stages reuse the same shared core and only change instance configuration, visibility, and human-approval boundaries.

### Stage 1: Internal Colleague Clone

- Goal: prove the clone can reduce manual follow-up and produce stable closure discipline.
- Default template: `ops-management`
- Default loop: `5-day activation + daily morning / daytime / evening rhythm`
- Default visibility: `hq_internal_full`
- Default operating boundary: `half-autonomous cockpit`

### Stage 2: Strategic Partner Clone

- Goal: let a trusted external collaborator use the same core without seeing other tenants.
- Default posture: controlled pilot, summary-first visibility, proposal-only promotion.
- Required additions: partner-specific `tenant_id`, partner-specific `visibility_policy`, explicit boundary notes.

### Stage 3: Client Clone

- Goal: deliver the shared core as a tenant-isolated operating product.
- Default posture: tenant-operated summary, HQ cross-org risk visibility, stricter approval boundaries.
- Required additions: stronger isolation, tighter writeback rules, client-facing review cadence.

## Clone Kit Contents

The minimal kit must include these reusable assets:

- `clone-registry.json`
- `org-registry.json`
- `role-template-registry.json`
- `clone-training-state.json`
- `clone-scorecard.json`
- `clone-autonomy-tier.json`
- `promotion-queue.json`
- `capability-proposals.json`
- `alerts-decisions.json`
- `portfolio-daily-report.json`
- `portfolio-daily-report.md`
- `CLONE-INIT.md` template
- `internal_ops_mvp.sh`
- `internal_collaboration_playbook.sh`
- `clone-review` / `sync-feishu` mirror contracts

The kit also depends on the existing canonical substrate:

- `references/clone-registry-contract.md`
- `references/clone-training-contract.md`
- `references/clone-review-contract.md`
- `references/role-template-contract.md`
- `references/tenant-visibility-contract.md`
- `references/source-of-truth-contract.md`

## Non-Negotiable Rules

- Do not create one repo per clone in v1.
- Do not copy local skill folders into per-clone folders.
- Do not treat a frontstage mirror as the canonical object.
- Do not auto-promote, auto-hibernate, or auto-change budgets without a proposal.
- Do not grant autonomous approval, payment, publish, delete, or legal confirmation.
- Do not let `clone_mode` overload tenancy, maturity, and product stage at the same time.
- Do not let `memory_namespace` leak across tenants.

## Instance Configuration Model

Every clone instance must be expressible with the same small set of fields:

- `clone_id`
- `customer_id`
- `org_id`
- `tenant_id`
- `display_name`
- `status`
- `actor_type`
- `role_template_id`
- `visibility_policy`
- `service_tier`
- `manager_clone_id`
- `goal_model`
- `shared_core_version`
- `memory_namespace`
- `report_owner`

These fields define the product shell.
They are not a dashboard hint and they are not optional styling.

## Rollout Gates

### Gate 1: Internal Colleague Ready

- one internal `ops-management` clone exists
- the 5-day loop can run without re-explaining the workflow each time
- `clone governance` dry-run is ready
- the founder can see who is moving, blocked, or waiting for approval

### Gate 2: Partner Pilot Ready

- the internal clone loop is stable
- the shared core does not depend on per-instance hacks
- tenant isolation rules are explicit
- proposal-only boundaries are working

### Gate 3: Client Pilot Ready

- partner pilot has been proven
- the visibility model is stable enough for tenant isolation
- client-facing review and approval points are explicit
- shared-core changes still flow through `capability-proposals.json`

## Operating Principle

The productization target is:

`one shared core -> many configured clones -> one governance vocabulary`

If a proposed change requires a different core for every tenant, it is not a clone product.
It is a collection of one-off deployments.

## Assumptions

- V1 is managed delivery / semi-self-service, not fully open SaaS.
- Internal colleague clone is the first validated slice.
- Strategic partner and client slices come only after the internal slice is stable.
- The operational truth for each instance stays local even when mirrors are published.
