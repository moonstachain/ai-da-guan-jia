#!/usr/bin/env bash
set -euo pipefail

EVENT_CATEGORY="${1:-}"
if [[ -z "${EVENT_CATEGORY}" ]]; then
  echo "usage: scan_t2_event.sh <event_category>" >&2
  exit 1
fi

# Manual trigger for TS-KB-03 scan hook V1.
# Cron placeholder (enable in V2 only after L1 event hook is stabilized):
# # 0 8 * * * /path/to/scan_t2_event.sh 战争/地缘

cat <<EOF
TS-KB-03 scan_t2_event.sh
- event_category: ${EVENT_CATEGORY}
- V1 保留事件驱动入口，后续按 L1 新增事件自动映射 T2 板块专家
- 本轮未自动抓取 T2 外部来源，避免在低质量输入下污染 L3
EOF
