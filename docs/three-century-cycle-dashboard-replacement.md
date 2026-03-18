# Three Century Cycle Dashboard Replacement

This document turns the current Feishu/Aily-generated `300年康波周期分析仪表盘` into a self-hosted web dashboard specification and a constrained OSS selection.

## Current State

- The Aily conversation URL is now accessible with the persisted browser profile after manual Feishu login on March 11, 2026.
- The repository already generates Feishu dashboard blueprint artifacts, but stops at source-view and checklist generation. It does not provide a self-hosted dashboard frontend yet.
- The screenshot shows a stable shape worth preserving:
  - title and metadata header
  - four KPI cards
  - filter controls
  - dark themed timeline view with colored event dots

## Verified Aily Sample

The latest successful sample is stored at:

- [result.json](/Users/hay2045/Documents/codex-ai-gua-jia-01/output/aily-session-sampler/2026-03-11T14-37-15-398Z/result.json)
- [result.md](/Users/hay2045/Documents/codex-ai-gua-jia-01/output/aily-session-sampler/2026-03-11T14-37-15-398Z/result.md)
- [page.png](/Users/hay2045/Documents/codex-ai-gua-jia-01/output/aily-session-sampler/2026-03-11T14-37-15-398Z/page.png)

Verified from the sampled conversation:

- Original user intent: use the 300-year Kondratieff-cycle data table to help entrepreneur users interpret current geopolitical and macro events through a long-cycle lens.
- Confirmed KPI targets: `306 years`, `79 events`, `10 cycle stages`, `4 country lines`.
- Confirmed interaction targets: zoomable timeline scatter, range slider, multi-select dropdown filters, hover/click detail interaction.
- Confirmed generated project artifacts mentioned by Aily: `dashboard_data.json` and `dashboard_preview.html`.
- Confirmed upstream source link exposed in the conversation:
  - [300年康波周期地图 副本](https://h52xu4gwob.feishu.cn/wiki/Kd6FwZvHOiE2D3kSy33c2oQZnad?from=from_copylink)
- Confirmed limitation from the upstream wiki sample:
  - the wiki shell is accessible, but it does not expose the final dashboard URL or exported files directly in visible markup
  - latest wiki sample artifacts: [result.json](/Users/hay2045/Documents/codex-ai-gua-jia-01/output/wiki-session-sampler/2026-03-11T14-39-02-378Z/result.json) and [page.png](/Users/hay2045/Documents/codex-ai-gua-jia-01/output/wiki-session-sampler/2026-03-11T14-39-02-378Z/page.png)

## Aily Sampling Workflow

Use the local sampler after manual Feishu login:

```bash
node scripts/aily_session_sampler.js \
  --url 'https://aily.feishu.cn/chat/conversation_4jpjnkp3m5psm' \
  --headed \
  --wait-for-auth
```

Artifacts land under `output/aily-session-sampler/<timestamp>/`:

- `result.json`
- `result.md`
- `page.png`

The sampler extracts:

- final page URL
- title
- page text preview
- Bitable/dashboard/doc links visible in the page
- screenshot evidence

## Target Product Shape

The self-hosted dashboard should preserve the current information hierarchy without depending on Feishu widget binding.

### Layout

- Hero header with title, subtitle, refresh date, record count, and identifier badge.
- Four KPI cards for year span, event count, cycle stage count, and theme count.
- Filter bar with year range, event category, region, and cycle stage.
- Main timeline visualization as the center of gravity.
- Event detail panel and supporting event table below or beside the chart depending on viewport.

### Data Contract

The minimal data model is defined in [three-century-cycle-dashboard-spec.json](/Users/hay2045/Documents/codex-ai-gua-jia-01/specs/self-hosted/three-century-cycle-dashboard-spec.json).

Core entities:

- `cycle_event`
- `cycle_stage`
- `event_category`
- `region`

Mandatory event fields:

- `id`
- `title`
- `event_year`
- `cycle_stage_id`
- `event_category_id`
- `region_id`
- `summary`
- `source_refs`

## Recommended Stack

### Primary

- [Apache ECharts](https://github.com/apache/echarts)
  - Best fit for the current screenshot because it handles dense scatter/time-series views, custom tooltips, legends, theming, and responsive redraw well.
  - The repo is active and broadly adopted; the GitHub repository shows a latest release on July 30, 2025 and a large installed base.
- [TanStack Table](https://github.com/TanStack/table)
  - Headless table layer that keeps layout and style fully under our control.
  - Good fit for synchronized chart-table selection and URL-driven filter state.

### Optional Add-Ons

- [react-grid-layout](https://github.com/react-grid-layout/react-grid-layout)
  - Add only if we later want end-user card rearrangement or saved dashboard layouts.
  - Not required for the first implementation because the current screenshot uses a fixed layout.
- [vis-timeline](https://github.com/visjs/vis-timeline)
  - Keep as a deferred fallback for editable ranges, grouped bands, or interval-heavy timelines.
  - Do not introduce it in v1 because the current target can be covered by a single ECharts-based rendering stack.

## Selection Rationale

Choose a single primary visualization stack first:

- ECharts covers the screenshot's KPI + filter + dark analytical timeline use case with less composition overhead.
- TanStack Table complements ECharts without forcing a prebuilt visual style.
- `react-grid-layout` is layout infrastructure, not a charting solution.
- `vis-timeline` is strong for editable range timelines, but adds a second rendering model we do not need yet.

## Constraints

- Do not treat Feishu Bitable or dashboard cards as the final presentation layer.
- Do not assume Aily exposes a stable public API for `generate dashboard from prompt`.
- Treat Aily as a reference workflow and evidence source until proven otherwise.

## Implementation Sequence

1. Complete Feishu login and sample the Aily conversation.
2. Extract the original prompt and generated link targets.
3. Normalize the event schema into local JSON.
4. Build the v1 self-hosted page with React + ECharts + TanStack Table.
5. Add `react-grid-layout` only if fixed layout becomes a bottleneck.

## Sources

- [Apache ECharts GitHub](https://github.com/apache/echarts)
- [TanStack Table GitHub](https://github.com/TanStack/table)
- [TanStack Table Docs](https://tanstack.com/table/docs)
- [react-grid-layout GitHub](https://github.com/react-grid-layout/react-grid-layout)
- [vis-timeline GitHub](https://github.com/visjs/vis-timeline)
- [Feishu Aily Knowledge Ask Docs](https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/aily-v1/app-knowledge/ask)
