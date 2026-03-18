# Output Contract

Every meaningful `原力觉醒` run should emit these canonical files.

## Standard Run Files

### `input.json`

Purpose:

- preserve run topic, note, and local source files
- give the run a stable identity

Required keys:

- `run_id`
- `topic`
- `created_at`
- `note`
- `source_files`

### `source-map.json`

Purpose:

- keep the normalized source frontier for the run

Recommended top-level keys:

- `seed_sources`
- `supplemental_sources`
- `ingested_sources`

`seed_sources` entries should carry at least:

- `type`
- `title`
- `url`
- `priority`
- `reason`

Allowed `type` values:

- `feishu_doc`
- `feishu_wiki`
- `ask_feishu_question`

### `source-digest.md`

Purpose:

- compress all source material into a scan-friendly digest

Recommended sections:

- `## Source Overview`
- `## Core Claims`
- `## Jung-Relevant Signals`
- `## Collaboration Relevance`

### `ai-force-model.md`

Purpose:

- define the machine-side force model

Required sections:

- `## 机器侧分层结构`
- `## 初始条件与递归原则`
- `## 全局最优判断法`
- `## 人类友好协作约束`
- `## 失真警戒项`

### `human-force-profile.md`

Purpose:

- define the user-side force model

Required sections:

- `## 荣格12原型根目录`
- `## 显性自述与长期主题`
- `## 行为偏好与兴趣特征`
- `## 决策风格与合作触发点`
- `## 互为投射线索`
- `## 阴影`
- `## 金色阴影`
- `## 阴影整合任务`
- `## 自信/自在的来源与破坏因子`

### `dual-force-bridge.md`

Purpose:

- connect the AI force and human force into one operating agreement

Required sections:

- `## 已高度匹配`
- `## 互为投射与共振`
- `## 张力与误读风险`
- `## Bridge Rules`
- `## Codex 接下来怎么变`

### `collaboration-protocol.md`

Purpose:

- turn the bridge into explicit behavior change

Recommended sections:

- `## How Codex Should Show Up`
- `## What To Stop Doing`
- `## Preferred Rhythm`
- `## Mutual Projection Guardrails`
- `## When Resonance Helps`
- `## When Resonance Distorts`
- `## Proof Requirements`

### `memory-packet.json`

Purpose:

- provide a compact importable summary for future tasks

Required top-level keys:

- `profile_version`
- `updated_at`
- `ai_force`
- `human_force`
- `bridge_rules`
- `collaboration_preferences`
- `current_phase`
- `minimum_human_closure`
- `archetype_root`
- `mutual_projection_map`
- `interview_deltas`
- `user_validated_seeds`
- `shadow_map`
- `golden_shadow_map`
- `integration_tasks`
- `confidence_conditions`
- `open_questions`
- `source_refs`

### `worklog.md`

Purpose:

- make closure quality visible

Recommended sections:

- `## Run`
- `## Verification`
- `## Gained`
- `## Wasted`
- `## Next Iterate`

## Helper Files

### `seed-source-map.json`

Purpose:

- editable intake queue for Feishu seeds

### `user-corrections.json`

Purpose:

- preserve user overrides or corrections

Suggested item keys:

- `field`
- `label`
- `correction`
- `reason`
- `recorded_at`

### `mirror-summary.json`

Purpose:

- optional governance-safe summary packet

Required keys:

- `run_id`
- `summary`
- `gained`
- `wasted`
- `next_iterate`
- `selected_rules`

Privacy rule:

- never include long raw excerpts, full ask.feishu answers, or uncompressed psychological inference.

### `interview-pack.md`

Purpose:

- hold the post-baseline short interview batch

Rules:

- first batch should contain at most 8 short-answer questions
- ask only after the baseline synthesis has exposed high-value gaps

### `interview-responses.json`

Purpose:

- preserve structured user answers to the interview pack

### `minimum-closure-pack.md`

Purpose:

- hold the fixed 5-question first-collaboration minimum closure pack

Rules:

- keep this pack stable once the active canonical has been frozen
- use it to collect only the irreducible subjective signals needed to move from MVP to stable collaboration

### `minimum-closure-responses.json`

Purpose:

- preserve the 5 short answers that finish the first-collaboration minimum human closure

Rules:

- status should be `pending_user_short_answers` until all 5 answers are collected
- once complete, status should become `collected`
- the anchor question should preserve structured fields for:
  - `low_leverage_trigger`
  - `golden_shadow_anchor`
  - `highest_value_trigger`

Suggested shape:

- `responses[]`
  - `id`
  - `category`
  - `question`
  - `answer`
  - `status`
  - `answered_at`
