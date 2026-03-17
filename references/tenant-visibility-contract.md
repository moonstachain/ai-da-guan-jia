# Tenant Visibility Contract

## Purpose

Define the visibility boundary for `总部总控舱 / 岗位工作台 / 客户运营台`.

The visibility layer exists to preserve tenant isolation while still allowing the HQ governor to see cross-org risk and proposal signals.

## Canonical Fields

These fields live on `clone-registry.json` and derived mirror rows:

- `org_id`
- `tenant_id`
- `actor_type`
- `visibility_policy`
- `manager_clone_id`

## V1 Policies

- `hq_internal_full`
  - Internal operators can be seen in detail by the HQ governor.
- `hq_cross_org_summary`
  - Reserved for founder/HQ summary views across internal and client tenants.
- `tenant_operated_summary`
  - Default for operated client clones; HQ sees details, client-facing surfaces should default to summary and approval points.
- `tenant_isolated_summary`
  - Reserved for stronger future customer isolation.

## Rules

- Default V1 stance is `分层可见`, not `总部全明细` for every customer-facing surface.
- Client A must never see Client B run detail, capability proposals, or scorecard detail.
- HQ may see cross-org summary, risk, and promotion queues across all tenants.
- Detailed customer operation views should be limited to the serving tenant and the HQ governor.
- `visibility_policy` is a governance contract, not just a UI hint; mirror bundles must carry it through.
