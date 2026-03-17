# Role Template Contract

## Purpose

Define the canonical role-template registry for internal operators and future client operating roles.

Role templates let multiple clones stay `同源同构` while still having role-specific goal models, skill chains, boundaries, and scorecards.

## Canonical Location

`artifacts/ai-da-guan-jia/clones/current/role-template-registry.json`

## Required Fields

- `role_template_id`
- `display_name`
- `goal_model`
- `recommended_skill_chain`
- `prohibited_boundaries`
- `scorecard_metrics`
- `default_actor_type`
- `default_visibility_policy`
- `default_service_tier`

## Default V1 Templates

- `ops-management`
- `finance`
- `hr-legal`
- `growth-conversion`
- `backend-delivery`
- `product`

## Rules

- Templates are shared-core governance assets, not per-tenant copies.
- A clone may omit `role_template_id`, but employee-facing V1 operators should prefer a registered template.
- `recommended_skill_chain` is a default, not a hard routing override; `AI大管家` still chooses the smallest sufficient chain per run.
- `prohibited_boundaries` must name actions that still require explicit human approval.
- `scorecard_metrics` must stay human-readable and stable enough for Feishu and dashboard views.
