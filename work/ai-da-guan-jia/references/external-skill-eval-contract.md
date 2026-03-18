# External Skill Eval Contract

Use this contract when `AI大管家` evaluates one external skill, one GitHub skill repo, or one foreign runtime skill family.

## Goal

Turn ad hoc “这个 skill 能不能用” questions into one repeatable, proof-bearing evaluation card.

## Minimum Output

Every evaluation must produce:

- `evaluation-card.json`
- `evaluation-card.md`
- `decision-memo.md`
- `source-evidence.json`
- `feishu-payload.json`
- `sync-result.json`

## Required Fields

- `skill_name`
- `source_url`
- `runtime_target`
- `category`
- `can_use_now`
- `best_use_mode`
- `reuse_value`
- `risks`
- `risk_tags`
- `recommended_next_action`
- `review_questions`
- `evaluation_lenses`
- `absorption_backlog`

## Fixed Risk Tags

- `runtime_mismatch`
  - Native runtime or packaging shape does not cleanly match the current Codex governor system.
- `private_material_dependency`
  - The workflow depends on private human material such as historical articles, style DNA, or non-public seed data.
- `unverifiable_output`
  - The repo does not provide strong enough installation/self-check/test evidence for a direct closure claim.
- `packaging_only_signal`
  - The repo looks well packaged, but proof of real verification or long-term reuse is still too weak.

## Five Lenses

Every evaluation card must include these five lenses in order:

1. `产品化壳层`
2. `工作流拆分`
3. `验真机制`
4. `跨 runtime 适配`
5. `持续学习/自进化`

Every lens must contain three explicit judgments:

- `直接借鉴`
- `条件迁移`
- `明确不借`

Each judgment must point to:

- at least one first-party repo evidence reference when available
- at least one local current-system gap or boundary
- explicit migration conditions when the judgment is `条件迁移`

## Fixed Categories

- `directly_usable`
  - Current environment and runtime are compatible enough to proceed to installation verification.
- `portable_reference`
  - The workflow is valuable, but the runtime or contract does not match the current local system.
- `intel_only`
  - Keep as external signal only; do not queue for adoption.

## Fixed Use Modes

- `install_now`
- `benchmark_then_port`
- `research_only`

## Fixed `can_use_now`

- `yes`
- `conditional`
- `no`

## Review Questions

Always answer these four first:

1. Is the runtime compatible with the current system?
2. Does the input depend on private human material?
3. Is the output verifiable?
4. Can this become a reusable long-term asset?

## Judgment Discipline

- Separate “can install in its native runtime” from “can be installed into current Codex”.
- Prefer first-party repo docs and raw skill files over reposted summaries.
- Do not classify an OpenClaw-only skill as `directly_usable` in Codex just because the repo is public.
- If evidence is partial, keep the recommendation conservative and say so explicitly.
- If a named source file is missing or 404, record the source gap explicitly instead of filling it with inference.
- Do not let high star count, cross-runtime marketing, or packaging polish overwrite runtime mismatch and local-gap evidence.
