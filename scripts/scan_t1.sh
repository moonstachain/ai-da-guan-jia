#!/usr/bin/env bash
set -euo pipefail

# Manual trigger for TS-KB-03 scan hook V1.
# Cron placeholder (enable in V2 only):
# 0 8 * * 1 /path/to/scan_t1.sh --dry-run

cat <<'EOF'
TS-KB-03 scan_t1.sh
- V1 先保留为人工触发入口
- 建议由大管家后续扩展到刘煜辉/洪灏/秦小明/AQR/GMO/Man/Citadel 的分层扫描
- 本轮核心验真由 scan_t0.sh 承担
EOF
