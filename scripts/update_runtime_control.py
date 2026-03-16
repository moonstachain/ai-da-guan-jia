from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.runtime_control import RuntimeControlPlane


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--round", required=True)
    parser.add_argument("--focus", required=True)
    parser.add_argument("--tests", type=int, required=True)
    parser.add_argument("--commits", type=int, required=True)
    parser.add_argument("--status", default="completed")
    parser.add_argument("--risk", default="low")
    parser.add_argument("--pending", type=int, default=0)
    parser.add_argument("--blockers", type=int, default=0)
    parser.add_argument("--state", default="healthy")
    parser.add_argument("--app-token", default=RuntimeControlPlane.APP_TOKEN)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    control_plane = RuntimeControlPlane(app_token=args.app_token)
    control_plane.ensure_table()
    result = control_plane.upsert(
        {
            "active_round": args.round,
            "frontstage_focus": args.focus,
            "runtime_state": args.state,
            "risk_level": args.risk,
            "total_tests_passed": args.tests,
            "total_commits": args.commits,
            "pending_human_actions": args.pending,
            "system_blockers": args.blockers,
            "last_evolution_round": args.round,
            "last_evolution_status": args.status,
        },
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

