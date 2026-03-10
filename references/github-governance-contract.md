# GitHub Governance Contract

Use GitHub as the collaboration and archive mirror for every meaningful AI大管家 task.

## Canonical Rule

- Local run artifacts remain canonical.
- GitHub mirrors the task for search, triage, status management, and historical traceability.
- Do not block a task just because GitHub auth or central repo config is missing.

## Governance Topology

- One organization-level `.github` repository for shared issue and PR defaults.
- One central ops repository, default name `ai-task-ops`, for task issues.
- One Project v2 for lifecycle visibility across all meaningful tasks.

## Required Management Surfaces

- Issue title format: `[type/domain] slug | 中文标题`
- Labels: `type:*`, `domain:*`, `state:*`, `artifact:*`
- Project fields:
  - `Status`
  - `Task Key`
  - `Type`
  - `Domain`
  - `Verification`
  - `Target Repo`
  - `Run ID`
  - `Archived At`

## Lifecycle

1. `route` writes the intake artifacts and attempts GitHub intake sync.
2. `close-task` writes the closure payload and attempts GitHub closure sync.
3. Re-runs must reuse the same `github_task_key`.
4. If sync is blocked, keep local payloads and record the blocked reason.
