#!/bin/bash

set -euo pipefail

usage() {
    echo "用法: cat new.md | ./scripts/update_init.sh"
    echo "  或: ./scripts/update_init.sh /path/to/new.md"
}

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="$REPO_ROOT/CLAUDE-INIT.md"

if [ $# -ge 1 ]; then
    if [ ! -f "$1" ]; then
        echo "错误：找不到输入文件: $1" >&2
        exit 1
    fi
    NEW_CONTENT="$(cat "$1")"
elif [ ! -t 0 ]; then
    NEW_CONTENT="$(cat)"
else
    usage
    exit 1
fi

if [ -z "$NEW_CONTENT" ]; then
    echo "错误：新内容为空，不执行更新" >&2
    exit 1
fi

printf '%s\n' "$NEW_CONTENT" > "$TARGET"

cd "$REPO_ROOT"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "错误：当前目录不是 git 仓库: $REPO_ROOT" >&2
    exit 1
fi

git add CLAUDE-INIT.md

if git diff --cached --quiet -- CLAUDE-INIT.md; then
    echo "ℹ️ CLAUDE-INIT.md 内容无变化，未创建 commit"
    exit 0
fi

git commit -m "chore: update CLAUDE-INIT.md (auto)"

if git push origin main; then
    echo "✅ CLAUDE-INIT.md 已更新并推送到 GitHub"
else
    echo "⚠️ git push 失败，请检查远端状态后重试" >&2
    exit 1
fi
