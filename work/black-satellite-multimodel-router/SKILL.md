---
name: black-satellite-multimodel-router
description: Use when the user wants one black-satellite terminal entry that auto-routes a task across GPT-5.4, Claude, Gemini, and Kimi, switches the remote provider, and returns both the answer and routing metadata.
---

# black-satellite-multimodel-router

Use this skill when the job is to run one task through the black satellite's multimodel router instead of manually choosing a model.

## What It Does

- Accepts one natural-language task plus optional image/search/citation flags.
- Routes the task to one of `gpt54`, `claude4`, `gemini25`, or `kimi`.
- Switches the black satellite provider remotely.
- Executes the task through `codex exec`.
- Returns both the human-readable answer and routing metadata.

## When To Use

- The user says they want the black satellite or black WeChat machine to choose the best model automatically.
- The user is unsure whether to use GPT-5.4, Claude, Gemini, or Kimi.
- The task mixes code, writing, Chinese workflow planning, or image understanding.

## Do Not Use

- When the user explicitly wants a different satellite.
- When the task needs a direct Grok, Perplexity, or DeepSeek live adapter. Those are v2 slots, not part of this MVP.
- When the user only wants a conceptual comparison and not a real remote run.

## Command

```bash
python3 /Users/liming/Documents/codex-ai-gua-jia-01/work/ai-da-guan-jia/scripts/ai_da_guan_jia.py satellite-multimodel-router --satellite 黑色 --task "..."
```

Optional flags:

- `--image /abs/path`
- `--need-search`
- `--need-citations`
- `--force-model gpt54|claude4|gemini25|kimi`
- `--dry-run`
- `--json`

## Routing Rules

- Image or multimodal intent: `gemini25`
- Code, math, logic, structured solving: `gpt54`
- Long-form rewrite, style-heavy writing: `claude4`
- Chinese workflow decomposition or Chinese agent-style work: `kimi`
- Explicit live search or citations: `gpt54` with search enabled

## Human Boundary

There is one intentional human boundary in v1:

- If Gemini hits the one-time workspace trust prompt on the black satellite, stop and return the fixed human action contract instead of guessing.

## Output Contract

Expect two layers:

- `response_text`: the user-facing answer
- routing metadata: `selected_model`, `reason`, `search_enabled`, `fallback_used`, `blocked_needs_user`
