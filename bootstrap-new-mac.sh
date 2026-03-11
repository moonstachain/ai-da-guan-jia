#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-${SCRIPT_DIR}}"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
SKILLS_MIRROR_ROOT="${SKILLS_MIRROR_ROOT:-$HOME/Documents/skills-mirror}"
SECRET_BUNDLE_ROOT="${SECRET_BUNDLE_ROOT:-$HOME/Documents/codex-secret-bundle}"
CLONE_VERSIONED_ASSETS="${CLONE_VERSIONED_ASSETS:-0}"
AI_DA_GUAN_JIA_REPO_URL="${AI_DA_GUAN_JIA_REPO_URL:-git@github.com:moonstachain/ai-da-guan-jia.git}"
SKILL_TRAINER_REPO_URL="${SKILL_TRAINER_REPO_URL:-git@github.com:moonstachain/skill-trainer-recursive.git}"

log() {
  printf '[bootstrap] %s\n' "$1"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'missing command: %s\n' "$1" >&2
    exit 1
  fi
}

brew_install_if_missing() {
  local formula="$1"
  if ! brew list --formula "$formula" >/dev/null 2>&1; then
    log "installing $formula via Homebrew"
    brew install "$formula"
  else
    log "Homebrew formula already present: $formula"
  fi
}

sync_dir() {
  local src="$1"
  local dst="$2"
  mkdir -p "$dst"
  rsync -a "$src"/ "$dst"/
}

restore_skills_from_mirror() {
  local mirror_root="$1"
  local codex_skills_root="$2"
  [[ -d "$mirror_root" ]] || return 0

  mkdir -p "$codex_skills_root"
  for skill_dir in "$mirror_root"/*; do
    [[ -d "$skill_dir" ]] || continue
    [[ -f "$skill_dir/SKILL.md" ]] || continue
    local skill_name
    skill_name="$(basename "$skill_dir")"
    local target="$codex_skills_root/$skill_name"
    if [[ -d "$target/.git" ]]; then
      log "skip base mirror sync for git-managed skill: $skill_name"
      continue
    fi
    log "syncing mirrored skill: $skill_name"
    mkdir -p "$target"
    rsync -a --exclude '.git/' "$skill_dir"/ "$target"/
  done
}

restore_raw_skills() {
  local raw_root="$1"
  local codex_skills_root="$2"
  [[ -d "$raw_root" ]] || return 0

  mkdir -p "$codex_skills_root"
  for skill_dir in "$raw_root"/*; do
    [[ -d "$skill_dir" ]] || continue
    local skill_name
    skill_name="$(basename "$skill_dir")"
    local target="$codex_skills_root/$skill_name"
    if [[ -d "$target/.git" ]]; then
      log "overlaying runtime state for git-managed skill: $skill_name"
      if [[ -d "$skill_dir/artifacts" ]]; then
        sync_dir "$skill_dir/artifacts" "$target/artifacts"
      fi
      if [[ -d "$skill_dir/state" ]]; then
        sync_dir "$skill_dir/state" "$target/state"
      fi
      continue
    fi
    log "restoring raw skill tree: $skill_name"
    mkdir -p "$target"
    rsync -a --exclude '.git/' "$skill_dir"/ "$target"/
  done
}

clone_versioned_asset_if_missing() {
  local repo_url="$1"
  local target="$2"
  if [[ "$CLONE_VERSIONED_ASSETS" != "1" ]]; then
    return 0
  fi
  if [[ -d "$target/.git" ]]; then
    log "git repo already present: $target"
    return 0
  fi
  mkdir -p "$(dirname "$target")"
  log "cloning $repo_url -> $target"
  git clone "$repo_url" "$target"
}

main() {
  require_command git
  require_command rsync
  require_command python3

  if ! command -v brew >/dev/null 2>&1; then
    printf 'Homebrew is required. Install it first: https://brew.sh/\n' >&2
    exit 1
  fi

  brew_install_if_missing git
  brew_install_if_missing python@3.11
  brew_install_if_missing node@20

  mkdir -p "$CODEX_HOME/skills" "$CODEX_HOME/automations" "$WORKSPACE_ROOT"

  clone_versioned_asset_if_missing "$AI_DA_GUAN_JIA_REPO_URL" "$CODEX_HOME/skills/ai-da-guan-jia"
  clone_versioned_asset_if_missing "$SKILL_TRAINER_REPO_URL" "$CODEX_HOME/skills/skill-trainer-recursive"

  restore_skills_from_mirror "$SKILLS_MIRROR_ROOT" "$CODEX_HOME/skills"

  if [[ -d "$SECRET_BUNDLE_ROOT/secret/codex" ]]; then
    log "restoring secret codex assets"
    if [[ -f "$SECRET_BUNDLE_ROOT/secret/codex/auth.json" ]]; then
      mkdir -p "$CODEX_HOME"
      cp "$SECRET_BUNDLE_ROOT/secret/codex/auth.json" "$CODEX_HOME/auth.json"
    fi
    if [[ -f "$SECRET_BUNDLE_ROOT/secret/codex/config.toml" ]]; then
      cp "$SECRET_BUNDLE_ROOT/secret/codex/config.toml" "$CODEX_HOME/config.toml"
    fi
    if [[ -d "$SECRET_BUNDLE_ROOT/secret/codex/automations" ]]; then
      sync_dir "$SECRET_BUNDLE_ROOT/secret/codex/automations" "$CODEX_HOME/automations"
    fi
    restore_raw_skills "$SECRET_BUNDLE_ROOT/secret/codex/skills-raw" "$CODEX_HOME/skills"
  fi

  if [[ -d "$SECRET_BUNDLE_ROOT/secret/workspace/output" ]]; then
    log "restoring workspace output"
    sync_dir "$SECRET_BUNDLE_ROOT/secret/workspace/output" "$WORKSPACE_ROOT/output"
  fi
  if [[ -d "$SECRET_BUNDLE_ROOT/secret/workspace/artifacts" ]]; then
    log "restoring workspace artifacts"
    sync_dir "$SECRET_BUNDLE_ROOT/secret/workspace/artifacts" "$WORKSPACE_ROOT/artifacts"
  fi

  if [[ -f "$WORKSPACE_ROOT/scripts/bootstrap_codex_mcp.sh" ]]; then
    log "running Codex MCP bootstrap check"
    "$WORKSPACE_ROOT/scripts/bootstrap_codex_mcp.sh"
  fi

  log "bootstrap finished"
  log "next steps:"
  log "1. Install or open Codex.app and sign in again."
  log "2. Recreate GitHub SSH key or PAT on the new Mac."
  log "3. Re-login Feishu and Get笔记."
  log "4. Run ./verify-restore.sh from $WORKSPACE_ROOT."
}

main "$@"
