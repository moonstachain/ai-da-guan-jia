# Tool Glue Benchmark Contract

Use this contract when `AI大管家` runs the fixed v0 experiment:

`Feishu docx transcript -> 豆包 deep research -> CLAUDY CHAT web rewrite`

## Purpose

Turn one subjective “这套软件粘合起来好不好用” impression into a repeatable, proof-bearing benchmark run.

## Command Surface

The v0 benchmark entrypoint is:

```bash
python3 scripts/ai_da_guan_jia.py tool-glue-benchmark --feishu-url "<docx-url>" --claudy-match "CLAUDY"
```

## Required Outputs

Every run must write:

- `route.json`
- `situation-map.md`
- `transcript-source.json`
- `transcript-source.md`
- `doubao-request.json`
- `doubao-article.md`
- `claudy-request.json`
- `claudy-article.md`
- `baseline-direct-claudy.md`
- `glue-scorecard.json`
- `glue-scorecard.md`
- `mvp-verdict.json`
- `mvp-verdict.md`
- `worklog.md`

Blocked runs must still write every file above. Downstream article files may contain explicit blocker notes instead of generated content.

## Fixed Stage Rules

### 1. Feishu

- Input: one `docx` Feishu URL
- Method: use `feishu-reader`
- Success condition:
  - extraction status is `ok`
  - extracted text is non-empty
- Failure handling:
  - auth gate or empty text => `blocked_needs_user`
  - missing tool/runtime => `blocked_system`

### 2. 豆包

- Entry requirement: Feishu transcript stage succeeded
- Fixed prompt prefix:
  - `请帮我基于以下主题，写一篇1万字的深入研究公众号文章`
- If the page requests a follow-up bulk choice, prefer `全部选择`

### 3. CLAUDY CHAT

- Entry requirement: the main chain prefers 豆包 article as input
- Fixed prompt prefix:
  - `请帮我基于以下主题，写一篇1万字的深入研究公众号文章，以下是我的初稿`
- Default target discovery:
  - try a browser tab whose title or URL contains `CLAUDY`
  - if none, fall back to `Claude`
  - if still none, close as `blocked_needs_user`

### 4. Baseline Branch

- Always prepare the direct baseline when Feishu transcript exists:
  - `transcript -> CLAUDY`
- Purpose:
  - compare direct handoff vs `豆包 -> CLAUDY`

## Fixed Per-Stage Metrics

Every stage record must contain:

- `success`
- `elapsed_sec`
- `input_chars`
- `output_chars`
- `retry_count`
- `user_interruptions`

Useful optional fields:

- `status`
- `blocking_reason`
- `target_url`
- `matched_tab`
- `artifacts`

## Fixed Chain Metrics

`glue-scorecard.json` must include:

- `联合效率`
- `交接损耗`
- `闭环度`
- `证据度`
- `自动化可达度`
- `是否值得固化`

Each metric may carry both a numeric score and a short judgment.

## Closure States

Use explicit closure states only:

- `completed`
- `blocked_needs_user`
- `blocked_system`
- `failed_partial`

## Verdict Enum

The experiment verdict must be one of:

- `keep_and_harden`
- `use_conditionally`
- `not_worth_gluing`

## Promotion Rule

- v0 writes an `experiment` result only.
- v0 must not write into `workflow-registry.json`.
- Only a later round with `verdict = keep_and_harden` may propose workflow hardening.
