# Clone Registry Contract

## Purpose

Define the canonical object model for AI管家 clone instances.

Clones are configured instances over the shared `AI大管家` core.
They are not copied skill folders, copied repos, or copied workflow trees.

## Canonical Location

Write current clone-factory state under:

`artifacts/ai-da-guan-jia/clones/current/`

## Required Files

- `clone-registry.json`
- `role-template-registry.json`
- `org-registry.json`
- `clone-training-state.json`
- `clone-scorecard.json`
- `clone-autonomy-tier.json`
- `promotion-queue.json`
- `budget-allocation.json`
- `task-runs.json`
- `training-cycles.json`
- `capability-proposals.json`
- `alerts-decisions.json`
- `portfolio-daily-report.json`
- `portfolio-daily-report.md`

## clone-registry.json Required Fields

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
- `created_at`
- `updated_at`

## Rules

- Reuse one shared `AI大管家` codebase and governance core.
- Keep `clone_mode=lab|client` for backward compatibility, but treat it as a legacy compatibility field rather than the full org model.
- Separate `org_id / tenant_id / actor_type / role_template_id` from `clone_mode`; do not overload one field to represent both tenancy and maturity.
- Isolate customer memory by `memory_namespace`.
- Default internal operators to the shared HQ org and default client operators to tenant-local ids.
- Do not copy local skills into per-customer clone folders.
- Do not create one repo per clone in v1.
- Promotion, budget changes, and hibernation remain proposal-only in v1.
- New capability evolution must flow through `capability-proposals.json` before promotion into the shared core.
