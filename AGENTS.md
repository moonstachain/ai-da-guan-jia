# AGENTS

## Post-Task Rules

- Run `./post-task-sync.sh` after a task finishes and before closing the repo handoff.
- Keep commits small and module-oriented; auto-commit only when `git status --porcelain` is non-empty.
- If push fails, record the exact error and mark the run `sync_pending` for follow-up.
