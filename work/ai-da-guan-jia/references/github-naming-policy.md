# GitHub Naming Policy

## Core Rule

Use English machine names and Chinese human display text together, not interchangeably.

## Repo Naming

- Repositories use lowercase kebab-case English only.
- Chinese belongs in README headings, descriptions, or issue titles.
- Use repo topics for repository-level classification.

## Task Naming

- Stable task key:
  - `tsk-YYYYMMDD-<type>-<domain>-<slug>-<hash8>`
- Issue title:
  - `[type/domain] slug | 中文标题`

## Slug Rules

- Prefer ASCII kebab-case from stable keywords.
- If the prompt does not yield useful ASCII terms, fall back to a deterministic task slug.
- Never use raw Chinese text as the slug.
