# Core Roster

## Control Plane Spine

### ai-metacognitive-core

- Role: expose distortion risk, truth condition, collaboration boundary, and evolution judgment before action.
- Strengths: catches pseudo-completion, pseudo-understanding, and boundary confusion.
- Weaknesses: does not execute domain work by itself.
- Boundary: use as the supervisory judgment layer above the rest of the chain.

### intent-grounding

- Role: turn a vague request into a bounded intent, success criteria, and a routeable task frame before downstream selection.
- Strengths: reduces ambiguity before routing starts, makes hidden assumptions explicit.
- Weaknesses: does not choose the final tool chain by itself.
- Boundary: use before routing whenever the prompt is underspecified or likely to split into multiple interpretations.

### skill-router

- Role: select the smallest sufficient downstream combination and keep the mainline stable.
- Strengths: stable route choice, overlap resolution, and combination discipline.
- Weaknesses: depends on clean intent and good boundary input.
- Boundary: use as the primary chooser once the task frame is grounded.

### evidence-gate

- Role: require proof-bearing evidence before completion, mirror sync, or truth promotion is accepted.
- Strengths: blocks pseudo-closure, keeps results tied to verifiable artifacts.
- Weaknesses: cannot invent evidence or replace execution.
- Boundary: use as the completion gate, not as a brainstorming helper.

### closure-evolution

- Role: decide whether a completed run should be captured as a validated rule, policy, or reusable pattern.
- Strengths: turns single runs into reusable governance assets.
- Weaknesses: should not pre-empt task execution.
- Boundary: use after the result is real and the evidence gate has passed.

## jiyao-youyao-haiyao

- Role: enforce minimal interruption, dual verification, and the cheapest reliable single-pass execution.
- Strengths: strong autonomy, cost ladder discipline, low-noise escalation.
- Weaknesses: not a domain planner or knowledge specialist.
- Boundary: use when the main risk is waste, interruption, or weak proof, and the work is still a single closure pass.

## jiyao-youyao-haiyao-zaiyao

- Role: stronger meta-execution variant for complex multi-step work with short post-task reflection and repeated verification.
- Strengths: good for larger workflows that still need tight convergence.
- Weaknesses: can be heavier than necessary for small tasks.
- Boundary: use when the task is clearly complex, multi-stage, or requires multiple proof cycles to converge.

## skill-creator

- Role: create or update local Codex skills with the correct skeleton, metadata, validation, and progressive disclosure.
- Strengths: reliable structure, reusable resources, validation workflow.
- Weaknesses: not a meta-judgment system on its own.
- Boundary: route here first for any request to build or modify a skill.

## skill-trainer-recursive

- Role: train a new skill method through strategic intent discovery, first-principles decomposition, benchmark alignment, and recursive MVP evaluation.
- Strengths: turns vague skill ideas into a methodical training loop with explicit artifacts and release gates.
- Weaknesses: heavier than direct scaffolding when the user only needs a fast one-off skill file.
- Boundary: route here before raw scaffolding when the user wants to train a skill or design a skill-training method.

## guide-benchmark-learning

- Role: learn unfamiliar capabilities by reading manuals, official docs, benchmark guides, and similar cases before execution.
- Strengths: source hierarchy discipline, execution-readiness judgment, reusable learning handbook output.
- Weaknesses: does not execute domain work and can be unnecessary when the domain is already locally mature.
- Boundary: route here when the task is unfamiliar enough that learning should happen before execution or before training a new skill.

## openclaw-xhs-coevolution-lab

- Role: turn real OpenClaw experiments into Xiaohongshu viral-note blueprints and a co-evolution content system.
- Strengths: strong on account positioning, topic hooks, evidence requirements, and note-structure design for this niche.
- Weaknesses: does not publish content and should not replace real experimentation.
- Boundary: use when the job is OpenClaw + 小红书 + 共进化 + 爆款内容 strategy, not generic social posting.

## knowledge-orchestrator

- Role: ask the knowledge base first, then synthesize and plan from the answers.
- Strengths: preserves raw Q and A before synthesis, good for knowledge-first strategy work.
- Weaknesses: depends on the knowledge system and does not replace execution proof.
- Boundary: route here first when the user explicitly wants the knowledge base queried before judgment.

## self-evolution-max

- Role: run multi-round plan-execute-evaluate-iterate loops with versioned state.
- Strengths: strong for iterative strategy, MVP loops, and feedback-driven progress.
- Weaknesses: heavier than a single-pass task router.
- Boundary: route here when the job is explicitly iterative rather than one-shot.

## agency-agents-orchestrator

- Role: coordinate multi-agent or multi-role delivery pipelines with QA loops.
- Strengths: good for broader implementation pipelines and staged handoffs.
- Weaknesses: can overshoot when the user only needs one focused skill.
- Boundary: route here when the user wants agent orchestration, QA loops, or pipeline control.

## feishu-bitable-bridge

- Role: inspect or safely upsert Feishu bitable records with a preview-first workflow.
- Strengths: schema awareness, dry-run preview, safe application.
- Weaknesses: external-system dependent, not canonical memory.
- Boundary: use only after the local evolution record and Feishu payload already exist.

## routing-playbook

- Role: serve as a mid-layer routing handbook that maps recurring task families to the smallest sufficient skill combinations.
- Strengths: stable task-to-skill mapping, boundary clarification, reusable combination rationale.
- Weaknesses: does not execute work and should not replace the top-level governor.
- Boundary: use when AI大管家 needs a repeatable combination guide for high-frequency task families.

## Absorbed Missing Organs

`ai-metacognitive-core` references several immune organs that are not installed locally as standalone skills.
The control-plane spine above now makes the main chain explicit; keep this list only as a reminder of residual absorbed lineage:

- `human-ai-collab-loop`

In `AI大管家` v1, absorb the residual responsibilities into the routing policy, verification rules, and evolution log instead of adding hard dependencies.
