# Skill Review Rubric

Use this rubric whenever `AI大管家` reviews the local skill system.

Keep the wording stable across daily reviews.

## Fixed Criteria

- `顺手度`: whether the skill reduces interruptions, context switching, and time-to-closure.
- `闭环度`: whether the skill has clear inputs, workflow, verification, and outputs.
- `复用度`: whether the skill can be combined predictably with other skills.
- `证据度`: whether the skill carries scripts, references, or an explicit proof path.
- `边界清晰度`: whether the skill is easy to distinguish from adjacent skills.
- `进化潜力`: whether the skill should be thickened, merged, or replaced.

## Review Discipline

- Review only top-level installed skills under `$CODEX_HOME/skills/*/SKILL.md`.
- Exclude `artifacts/**/SKILL.md` and `.system/*/SKILL.md` from the daily review count.
- Separate direct usage evidence from structure-based inference.
- End every review with exactly 3 candidate evolution actions.
- Ensure the 3 actions cover different types whenever possible:
  - `路由修正`
  - `workflow hardening`
  - `去重/合并`
  - `新建中层 skill`
