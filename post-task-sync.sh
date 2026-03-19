#!/usr/bin/env bash
set -euo pipefail

branch="$(git rev-parse --abbrev-ref HEAD)"
python3 scripts/post_task_verify.py --full-audit

if [[ -z "$(git status --porcelain)" ]]; then
  echo "clean: no post-task commit needed"
  exit 0
fi

stamp="$(date +%Y-%m-%d)"
git add -A
git commit -m "chore(sync): post-task auto-commit ${stamp}"
git push origin "${branch}"
