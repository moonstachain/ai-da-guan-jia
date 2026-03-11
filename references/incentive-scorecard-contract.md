# Incentive Scorecard Contract

## Priority

Optimize for governance quality, not raw throughput.

## Primary Target

Score the `execution_chain` first, then allocate credit to `agent / skill / workflow / component`.

Do not let strong local behavior hide weak full-chain behavior.

## Score Layers

### 1. `route_score`

Used before execution for routing priority, budget assignment, and autonomy limits.

Hard gates:

- `honesty_gate`
- `verification_gate`
- `boundary_gate`

Weighted dimensions:

- `task_fit`
- `verification_capability`
- `predicted_token_efficiency`
- `predicted_time_efficiency`
- `auth_reuse`
- `chain_simplicity`

### 2. `closure_score`

Used after execution for reward, demotion, budget review, and writeback trust.

Hard gates:

- `closure_quality >= pass`
- `verification_strength >= pass`
- `pseudo_completion = false`

Weighted dimensions:

- `closure_quality`
- `verification_strength`
- `token_efficiency`
- `time_efficiency`
- `interruption_cost`
- `reuse_contribution`
- `handoff_coherence`
- `strategic_alignment`

## Primary Metrics

- `closure_quality`
- `verification_strength`
- `token_efficiency`
- `time_efficiency`
- `reuse_contribution`
- `distortion_rate`
- `handoff_coherence`
- `strategic_alignment`
- `human_interruption_cost`

## Budget Discipline

Use tiered task budgets instead of one global hard cap.

Default tiers:

- `micro`
- `standard`
- `deep`
- `expedition`

Each tier must define:

- `soft_token_cap`
- `hard_token_cap`
- `soft_time_cap`
- `hard_time_cap`

## Incentive Levers

- `调用权`: routing priority
- `自治权`: proposal autonomy tier
- `资源权`: context and model budget preference
- `进化权`: writeback and governance trust

## Rules

- Do not reward task count alone.
- Do not reward token spend alone.
- Do not reward low token or fast completion when truth gates failed.
- Penalize pseudo-completion more than slow completion.
- Penalize repeated interruption when the task did not require a human boundary.
- Penalize chain inflation when multi-agent stacking does not improve closure.
- High-cost runs may still keep positive credit if they prove materially stronger closure.
