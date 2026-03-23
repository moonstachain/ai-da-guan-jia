#!/usr/bin/env bash
set -euo pipefail

REPO_OWNER="moonstachain"
MAIN_REPO="ai-da-guan-jia"
SKILLS_REPO="skills-mirror"

WORKDIR="${WORKDIR:-$HOME/Documents}"
ROOT_DIR="${ROOT_DIR:-$WORKDIR/$MAIN_REPO}"
SKILLS_DIR="${SKILLS_DIR:-$WORKDIR/skills-mirror}"

say() {
  printf "%s\n" "$*"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    say "Missing required command: $1"
    exit 1
  fi
}

require_cmd git
require_cmd python3

say "== One-click restore =="

if [ ! -d "$ROOT_DIR/.git" ]; then
  say "Cloning main repo into $ROOT_DIR"
  git clone "git@github.com:${REPO_OWNER}/${MAIN_REPO}.git" "$ROOT_DIR"
else
  say "Main repo already exists. Pulling latest."
  (cd "$ROOT_DIR" && git pull --ff-only)
fi

if [ ! -d "$SKILLS_DIR/.git" ]; then
  say "Cloning skills mirror into $SKILLS_DIR"
  git clone "git@github.com:${REPO_OWNER}/${SKILLS_REPO}.git" "$SKILLS_DIR"
else
  say "Skills mirror already exists. Pulling latest."
  (cd "$SKILLS_DIR" && git pull --ff-only)
fi

export SKILLS_MIRROR_ROOT="$SKILLS_DIR"

if [ -x "$ROOT_DIR/bootstrap-new-mac.sh" ]; then
  say "Running bootstrap-new-mac.sh"
  (cd "$ROOT_DIR" && ./bootstrap-new-mac.sh)
else
  say "bootstrap-new-mac.sh not found or not executable. Skipping."
fi

say "Restore complete. Next steps:"
say "1) Open Codex.app and log in"
say "2) Ensure Feishu / Get笔记 logins are valid"
say "3) (Optional) Run: python3 $ROOT_DIR/scripts/doctor.py"
