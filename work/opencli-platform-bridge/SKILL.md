---
name: opencli-platform-bridge
description: Use when the user wants to read, search, trace, or lightly operate websites like Bilibili, Zhihu, Xiaohongshu, X/Twitter, Reddit, GitHub, YouTube, Weibo, HackerNews, V2EX, Xueqiu, or other supported sites through OpenCLI or compatible website-as-CLI tools. Prefer this skill before browser automation for supported platform workflows, especially when the goal is timeline inspection, content search, feed extraction, profile lookup, relationship lookup, or guarded write operations with explicit confirmation.
---

# OpenCLI Platform Bridge

## Overview

Use this skill as the `CLI-first platform action bridge` for social, community, content, and public-web workflows.

- It turns supported websites into structured terminal commands through `jackwener/opencli` and compatible platform CLIs.
- It should be preferred before Playwright when the target action is already covered by a stable CLI command.
- It is optimized for `read / search / inspect / export / light guarded write`, not blind UI exploration.

## When To Use

Trigger this skill when the user wants to:

- inspect `X / Twitter` timelines, followers, following, bookmarks, threads, or search results
- read or search `Reddit`, `Bilibili`, `Zhihu`, `Xiaohongshu`, `Weibo`, `YouTube`, `HackerNews`, `V2EX`, `Xueqiu`, `BBC`, `Reuters`, `Yahoo Finance`, `GitHub`, or other OpenCLI-supported sites
- export structured results as `json`, `yaml`, `md`, `csv`, or tables for downstream synthesis
- do guarded light write operations like `like`, `follow`, `bookmark`, `reply`, `post`, or similar actions only after preview and explicit confirmation
- explore whether a website can be converted into a reusable CLI surface through OpenCLI's `explore / synthesize / generate / cascade` workflow

Do not use this skill when:

- the site is unsupported and the job requires exploratory clicking or DOM debugging
- the user needs a full browser walkthrough, visual debugging, screenshots, or element-level manipulation
- the task is deep GitHub engineering collaboration rather than simple GitHub content search
- the task requires high-risk bulk writes without a human approval checkpoint

## Routing Rule

Prefer this skill over browser automation when all 3 are true:

1. the target site is supported by OpenCLI or a compatible CLI
2. the desired operation is known and reproducible as a command
3. a structured output format is useful for verification or downstream reasoning

Fallback to `playwright` when:

- the site is unsupported
- OpenCLI command discovery fails
- authentication needs visual repair
- the task depends on page state that cannot be reliably expressed as a CLI action
- the user explicitly asks for browser automation or screenshots

## Runtime Rule

For live OpenCLI calls, bind `PLAYWRIGHT_MCP_EXTENSION_TOKEN` explicitly before invoking `opencli`.

- First prefer the current process environment.
- If missing, fall back to `~/.codex/config.toml`.
- If still missing, fall back to `~/.zshrc`.
- Do not rely on an interactive shell having already sourced startup files.

## Safety Model

Use these 3 safety classes:

### 1. Read Ops

- safe by default
- examples: timeline, search, hot list, feed, topic, user profile, saved list, market quote
- default output format should be `json` or `yaml` when downstream reasoning matters

### 2. Light Write Ops

- require explicit preview plus confirmation
- examples: like, bookmark, follow, save, upvote, subscribe
- log the target object and action before execution

### 3. Heavy or Irreversible Write Ops

- require human confirmation every time
- examples: post, reply, delete, bulk follow, bulk comment, add-to-cart
- if the platform risk or output risk is unclear, stop and keep the action at `proposal_only`

## Deployment Workflow

### 1. Check prerequisites

```bash
node --version
npm --version
command -v opencli || true
python3 scripts/doctor.py
```

### 2. Install OpenCLI if missing

```bash
npm install -g @jackwener/opencli
opencli --version
opencli doctor
```

### 3. Finish browser/session setup

- Keep Chrome open.
- Log into the target websites in Chrome first.
- Install the Playwright MCP Bridge extension if OpenCLI asks for it.
- Run `opencli setup` if token/config wiring is missing.

### 4. Verify command registry

```bash
opencli list -f yaml
python3 scripts/opencli_bridge.py list --format json
```

## Commands

```bash
python3 scripts/doctor.py
python3 scripts/opencli_bridge.py list --format yaml
python3 scripts/opencli_bridge.py probe --site twitter
python3 scripts/opencli_bridge.py probe --site reddit
python3 scripts/opencli_bridge.py run -- twitter timeline --limit 20 -f json
python3 scripts/opencli_bridge.py run -- reddit search --query "llm agents" -f json
python3 scripts/opencli_bridge.py run --confirm-write -- twitter like --tweet-id 1234567890
```

