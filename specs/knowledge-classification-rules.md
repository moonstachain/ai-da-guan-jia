# Knowledge Classification Rules

## Scope

This rule set defines the first-pass classification contract for `knowledge_items`.
It is intentionally narrow and only covers the current Yuanli shared knowledge source rollout.

## Governance Layers

- `治理层`
  - Top-level maps, operating systems, root pages, and space-level governance overviews.
  - Typical signals: `OS`, `总图`, `总览`, `根目录`, `治理`.
- `规则层`
  - Explicit rules, protocols, SOPs, contracts, naming policies, rubrics.
  - Typical signals: `规则`, `协议`, `SOP`, `模板`, `命名`, `章程`.
- `线程层`
  - Active logs, diaries, recursive journals, running investigations, thread workspaces.
  - Typical signals: `日志`, `递归`, `线索`, `观察`, `复盘进行中`.
- `资产层`
  - Reusable inventories, skill maps, templates, capability registries, stable reference assets.
  - Typical signals: `盘点`, `资产`, `能力`, `技能`, `清单`, `模板库`.
- `交付层`
  - Published outputs, delivered reports, finalized decks, summaries prepared for external or downstream use.
  - Typical signals: `交付`, `报告`, `结案`, `发布版`, `成品`.

## Sync Tiers

- `core`
  - Must appear in the human-facing shared interface.
  - Includes root governance pages, stable rules, key capability inventories, and confirmed top-level maps.
- `candidate`
  - Keep in canonical and review periodically before mirroring.
  - Default for logs, active threads, exploratory materials, and incomplete but potentially useful workspaces.
- `ignore`
  - Do not mirror by default.
  - Use for duplicates, stale scratch pages, or low-value fragments.

## Default Decisions For 【原力龙虾】

- `【原力龙虾】` -> `治理层` + `core`
- `原力OS` -> `治理层` + `core`
- `SOUL-递归日志-*` -> `线程层` + `candidate`
- `驯兽日志` -> `线程层` + `candidate`
- `技能盘点` -> `资产层` + `core`

## Evidence Rule

- Browser-visible title or navigation evidence is enough to create a first-pass `knowledge_item`.
- Full text extraction is required before upgrading exploratory items into high-confidence rules or delivery objects.
