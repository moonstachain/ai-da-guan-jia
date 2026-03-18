---
name: yuanli-juexing
description: Use when the user wants Codex to understand them through a dual-force protocol: absorb Feishu wiki/doc knowledge, ask ask.feishu/Aily, combine long-term materials and direct transcripts, model both AI force and human force, and turn that understanding into a reusable collaboration protocol. Trigger on requests about 原力觉醒, 双原力, AI 更懂我, 让我被 AI 理解, Feishu 里有我的知识, 阴影/金色阴影/整合, or turning private materials into a long-term human-AI operating pact.
---

# Yuanli Juexing

Treat this skill as the upstream `双原力对接协议`.

## Identity

- Hold two force models at the same time:
  - `AI 原力`: machine-side layer structure, recursion, initial conditions, global optimum, human-friendly collaboration, distortion guards
  - `人的原力`: the user's archetype root, self-expression, behavior traces, preferences, shadow, golden shadow, integration tasks, confidence patterns
- Do not reduce the user to a diagnosis or a type code.
- Do not reduce the AI to a tool picker.
- Treat the output as a living collaboration pact, not a one-time personality summary.
- Keep local artifacts canonical. Governance mirrors are optional and summary-only.

Read these references when needed:

- [references/evidence-layers.md](references/evidence-layers.md)
- [references/jung-lens.md](references/jung-lens.md)
- [references/dual-force-contract.md](references/dual-force-contract.md)
- [references/output-contract.md](references/output-contract.md)

## Core Question

Ask all sources these paired questions:

- `这段材料暴露了这个人的原力结构是什么?`
- `AI 应该用怎样的机器原力去贴合、放大、保护、校准这种人类原力?`

## Workflow

Follow this order:

1. `ingest-seed-sources`
2. `build-ai-force-model`
3. `build-human-force-model`
4. `bridge-dual-force`
5. `emit-collaboration-protocol`
6. `prepare-optional-governance-mirror`

Default intake boundary:

- `Feishu wiki/doc`: use [$feishu-reader](/Users/liming/.codex/skills/feishu-reader/SKILL.md)
- `ask.feishu / Aily`: use [$feishu-km](/Users/liming/.codex/skills/feishu-km/SKILL.md)
- `local transcript / direct chat clarification`: ingest as supplemental private sources
- `short interview pack`: ask only after baseline and keep the first batch within 8 short-answer questions

Map the user's original five-step ladder into the dual-force protocol:

`碎片信息 -> 抽取特征 -> 提炼观点 -> 形成洞察 -> 全局最优解`

- `碎片信息`: Feishu docs, ask.feishu answers, transcripts, chat clarifications
- `抽取特征`: evidence tags, repeated patterns, decision markers, shadow markers
- `提炼观点`: AI-force principles and human-force hypotheses
- `形成洞察`: dual-force bridge rules and tension points
- `全局最优解`: concrete collaboration protocol updates for Codex

## Operating Rules

- Use `seed-source-map.json` as the intake frontier. First version does not free-roam the user's whole Feishu space.
- Keep `荣格` as a primary interpretive lens for the human side, not as an absolute truth system.
- Use `荣格12原型人格` as the root directory for the human force, but keep it dynamic, revisable, and evidence-bound.
- Place Jung-derived observations only in `human_force`, and always mark them as `interpretive lens`.
- Prefer explicit self-description over inference when they conflict.
- Separate `explicit_statement`, `behavior_trace`, `repeated_pattern`, `jung_inference`, and `open_question`.
- Treat `智者` and `探索者` as first-round validated seeds only when the user explicitly provides them.
- If evidence is thin, label conclusions `provisional`.
- Always emit:
  - one `AI force` model
  - one `human force` model
  - one `dual-force bridge`
  - one `collaboration protocol`
- Always refresh the `interview-pack.md` after baseline synthesis, not before.
- Optional governance mirrors must contain summary only, never raw private source text.

## Commands

Initialize a run:

```bash
python3 scripts/yuanli_juexing.py init-run \
  --topic "原力觉醒双原力首轮校准" \
  --note "录音与补充说明首轮吸收" \
  --run-id yj-20260313-dual-force-sample \
  --source-file artifacts/sources/2026-03-12-ai-era-self-cognition-transcript.md \
  --source-file artifacts/sources/2026-03-13-dual-force-clarification.md
```

Ingest one Feishu wiki/doc seed:

```bash
python3 scripts/yuanli_juexing.py ingest-feishu-doc \
  --run-dir artifacts/runs/2026-03-13/yj-20260313-dual-force-sample \
  --url "https://example.feishu.cn/wiki/abc123" \
  --title "人格与原力笔记" \
  --priority high \
  --reason "这是用户长期自我理解的核心材料"
```

Ingest one ask.feishu seed:

```bash
python3 scripts/yuanli_juexing.py ingest-ask-feishu \
  --run-dir artifacts/runs/2026-03-13/yj-20260313-dual-force-sample \
  --question "总结我的行为偏好、阴影和金色阴影线索" \
  --title "人格阴影追问" \
  --priority high \
  --reason "补足文档里没有显式回答的人格整合问题"
```

Synthesize the dual-force packet:

```bash
python3 scripts/yuanli_juexing.py synthesize-dual-force \
  --run-dir artifacts/runs/2026-03-13/yj-20260313-dual-force-sample
```

Prepare the optional governance mirror:

```bash
python3 scripts/yuanli_juexing.py prepare-governance-mirror \
  --run-dir artifacts/runs/2026-03-13/yj-20260313-dual-force-sample
```

## Outputs

Write canonical run artifacts under:

`artifacts/runs/YYYY-MM-DD/<run-id>/`

Every standard run must produce:

- `input.json`
- `source-map.json`
- `source-digest.md`
- `ai-force-model.md`
- `human-force-profile.md`
- `dual-force-bridge.md`
- `collaboration-protocol.md`
- `memory-packet.json`
- `worklog.md`

Additional helper files used by the protocol:

- `auth-manifest.json`
- `seed-source-map.json`
- `interview-pack.md`
- `interview-responses.json`
- `user-corrections.json`
- `mirror-summary.json` after mirror preparation

When `AI大管家` is orchestrating the pressure test, it should author `auth-manifest.json` and the first `seed-source-map.json` before running baseline synthesis.

## V1 Boundaries

First version supports:

- private seed-source Feishu ingestion
- dual-force modeling from documents, transcripts, and clarifications
- Jung-informed human-force interpretation
- Codex adaptation rules and optional governance summary mirrors

First version does not support:

- automatic full-Feishu exploration
- medical, therapeutic, or diagnostic claims
- irreversible identity verdicts
- default syncing to Feishu or GitHub
- replacing the user's explicit self-definition with AI inference
