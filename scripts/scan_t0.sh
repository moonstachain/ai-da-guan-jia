#!/usr/bin/env bash
set -euo pipefail

# Manual trigger for TS-KB-03 scan hook V1.
# Cron placeholder (enable in V2 only):
# 0 8 * * * /path/to/scan_t0.sh --apply

MODE="${1:-"--dry-run"}"
exec python3 "$(dirname "$0")/kangbo_scan_t0.py" "${MODE}"
