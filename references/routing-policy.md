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

- If the prompt asks to create or update a skill, route `skill-creator` first.
- If the prompt says to ask the knowledge base first, route `knowledge-orchestrator` first.
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

## Selection Ceiling

- Default downstream limit: 3 skills.
- Exceeding 3 is a failure by default. Only do it when omission would clearly break the task.
- If more than 3 candidates are relevant, keep the strongest domain fit first and explain the omitted candidates in `route.json`.

## Proof Rule

Every route must carry a verification target, not just a chosen skill name. Examples:

- skill creation: `SKILL.md`, `agents/openai.yaml`, resource files, validator pass
- knowledge-first planning: raw KB answers saved before synthesis
- Feishu mirror: canonical local log plus preview output before apply
- Recursive closure: use `close-task` to force recap, sync, and evolution writeback checks
