# Routing Policy

## Ranking Order

Score candidates in this fixed order:

1. `任务适配度`
2. `验真能力`
3. `成本/算力`
4. `已有认证/登录态复用`
5. `新增复杂度`

Do not let a cheaper path outrank a clearly better-fit path. Do not let a familiar path outrank a more verifiable path.

## Hard Routing Rules

- If the prompt is about skill inventory review, capability mapping, duplicate detection, system-wide skill evaluation, or a daily skill review, route `AI大管家` native `review-skills` flow first.
- If the prompt is about one external skill, one GitHub skill repo, or “这个 skill 能不能用 / 怎么用 / 值不值得接”, route `AI大管家` native `evaluate-external-skill` flow first.
- If the prompt is about learning an unfamiliar API, platform, tool, workflow, or method and explicitly mentions manuals, official docs, guides, tutorials, best practices, or benchmark comparison, route `guide-benchmark-learning` first.
- If that unfamiliar-domain prompt is specifically about OpenAI products or APIs, route `openai-docs` after `guide-benchmark-learning`.
- If the prompt is about `OpenClaw`, `小红书`, `博主`, `爆款`, `共进化`, or this content niche, route `openclaw-xhs-coevolution-lab` first.
- If the prompt asks to train a skill or design a skill-training method, route `skill-trainer-recursive` first.
- If the prompt asks to create or update a skill, route `skill-creator` first.
- If the prompt says to ask the knowledge base first, route `knowledge-orchestrator` first.
- If the prompt is about capturing, researching, or documenting into Notion, route the relevant `notion-*` skill only after any requested knowledge-base-first judgment is complete.
- If the prompt specifically asks to query `ask.feishu`, `Aily`, `飞书知识库`, or `飞书知识问答`, route `feishu-km` before `knowledge-orchestrator`, preserve raw Q&A artifacts first, and only then synthesize or plan.
- If the prompt is about `OpenCLI`, `website as CLI`, or supported social/community platform reads and light actions, route `opencli-platform-bridge` before `playwright`.
- For live OpenCLI execution, explicitly bind `PLAYWRIGHT_MCP_EXTENSION_TOKEN` from the current env or a trusted local config source such as `~/.codex/config.toml` or `~/.zshrc`; do not assume an interactive shell already sourced the token.
- If the prompt requires Feishu table writes, keep Feishu last in the chain:
  1. create local canonical record
  2. generate `feishu-payload.json`
  3. run dry-run preview
  4. apply sync
  5. run evolution gate and write back validated rules if hit
- If the prompt emphasizes autonomy, minimal interruption, or cheapest reliable path, prefer `jiyao-youyao-haiyao` as the execution layer.
- If the prompt emphasizes distortion, meta-judgment, or false completion risk, prefer `ai-metacognitive-core` as the judgment layer.
- If the prompt is iterative by nature, prefer `self-evolution-max`.
- If the prompt needs staged multi-agent execution, prefer `agency-agents-orchestrator`.

## Overlap Boundaries

- `jiyao-youyao-haiyao` is the default when the work is a single closure pass with low interruption and strong autonomy. `jiyao-youyao-haiyao-zaiyao` is the default when the work is clearly multi-stage, has repeated verification loops, or shows at least two of these signals: multiple execution surfaces, mixed work types, meaningful human multi-window leverage, or expected runtime above 20-30 minutes.
- `knowledge-orchestrator` owns KB-first judgment. `notion-*` owns capture, research, and documentation into Notion. When both are relevant, do the KB-first step first; do not let Notion preempt the knowledge-base judgment.
- `figma` owns design context discovery, asset loading, and node inspection. `figma-implement-design` owns 1:1 production implementation from an existing Figma source. Do not route generic UI ideation to either unless there is an actual Figma source.
- `youquant-backtest-automation` is the canonical route for natural-language strategy-to-backtest work. `youquant-backtest` is a legacy alias and should only be used when an existing flow already references that name.
- Feishu mirror rule: create and freeze the local canonical log first, then generate `feishu-payload.json`, then run dry-run preview, then apply sync. Do not let a mirror become the source of truth.

## Selection Ceiling

- Default downstream limit: 3 skills.
- Exceeding 3 is a failure by default. Only do it when omission would clearly break the task.
- If more than 3 candidates are relevant, keep the strongest domain fit first and explain the omitted candidates in `route.json`.

## Proof Rule

Every route must carry a verification target, not just a chosen skill name. Examples:

- skill creation: `SKILL.md`, `agents/openai.yaml`, resource files, validator pass
- skill training: `intent-canvas.json`, `first_principles.md`, `benchmark-map.json`, `candidate-skill-spec.md`, `eval-report.json`
- skill inventory review: correct top-level skill count, explicit exclusion of `artifacts/**`, structured review summary, and exactly 3 candidate evolution actions
- external skill evaluation: `source_url`, `runtime_target`, `category`, `can_use_now`, `best_use_mode`, explicit risks, and a recommendation about direct install versus benchmark/migration
- manual-first learning: `source-map.json`, `benchmark-grid.md`, `learning-handbook.md`, `execution-readiness.md`, and an explicit source-of-truth vs reference-guide split
- OpenClaw Xiaohongshu strategy: account plan, topic plan, note blueprint, evidence requirements, and viral logic
- knowledge-first planning: raw KB answers saved before synthesis
- Feishu knowledge Q&A: `feishu-km-request.json`, `feishu-km-response.json`, `feishu-km-record.json`, explicit `knowledge_source_type=feishu_aily_km`, and a manual-web versus official-api split
- Feishu mirror: canonical local log plus preview output before apply
- Recursive closure: use `close-task` to force recap, sync, and evolution writeback checks
