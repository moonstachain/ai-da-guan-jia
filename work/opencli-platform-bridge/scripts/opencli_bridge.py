#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys

from opencli_runtime import runtime_env


WRITE_VERBS = {
    "post",
    "reply",
    "delete",
    "like",
    "follow",
    "unfollow",
    "bookmark",
    "unbookmark",
    "comment",
    "upvote",
    "save",
    "subscribe",
    "add-to-cart",
}


def require_opencli() -> str:
    path = shutil.which("opencli")
    if not path:
        raise SystemExit(
            "opencli is not installed. Run `npm install -g @jackwener/opencli` first."
        )
    return path


def run_opencli(args: list[str]) -> int:
    opencli = require_opencli()
    env, _source = runtime_env()
    completed = subprocess.run([opencli, *args], check=False, env=env)
    return completed.returncode


def capture_opencli(args: list[str]) -> subprocess.CompletedProcess[str]:
    opencli = require_opencli()
    env, _source = runtime_env()
    return subprocess.run(
        [opencli, *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def render_items(items: list[dict], fmt: str) -> int:
    if fmt == "json":
        json.dump(items, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0
    if fmt == "yaml":
        for item in items:
            sys.stdout.write("-\n")
            for key, value in item.items():
                sys.stdout.write(f"  {key}: {json.dumps(value, ensure_ascii=False)}\n")
        return 0
    if fmt == "md":
        if not items:
            return 0
        keys = list(items[0].keys())
        sys.stdout.write("| " + " | ".join(keys) + " |\n")
        sys.stdout.write("| " + " | ".join(["---"] * len(keys)) + " |\n")
        for item in items:
            row = [str(item.get(key, "")) for key in keys]
            sys.stdout.write("| " + " | ".join(row) + " |\n")
        return 0
    if fmt == "csv":
        if not items:
            return 0
        keys = list(items[0].keys())
        sys.stdout.write(",".join(keys) + "\n")
        for item in items:
            row = [json.dumps(item.get(key, ""), ensure_ascii=False) for key in keys]
            sys.stdout.write(",".join(row) + "\n")
        return 0
    for item in items:
        sys.stdout.write(json.dumps(item, ensure_ascii=False) + "\n")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    cli_args = ["list", "-f", args.format]
    return run_opencli(cli_args)


def cmd_probe(args: argparse.Namespace) -> int:
    completed = capture_opencli(["list", "-f", "json"])
    if completed.returncode != 0:
        sys.stderr.write(completed.stderr)
        return completed.returncode
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError:
        sys.stderr.write("Failed to parse `opencli list -f json` output.\n")
        return 1
    if not isinstance(parsed, list):
        sys.stderr.write("Unexpected registry format from opencli.\n")
        return 1
    site = args.site.lower()
    filtered = []
    for item in parsed:
        haystack = json.dumps(item, ensure_ascii=False).lower()
        if site in haystack:
            filtered.append(item)
    return render_items(filtered, args.format)


def cmd_run(args: argparse.Namespace) -> int:
    if not args.cli_args:
        raise SystemExit("No opencli arguments were provided.")
    cli_args = args.cli_args[1:] if args.cli_args and args.cli_args[0] == "--" else args.cli_args
    if not cli_args:
        raise SystemExit("No opencli arguments were provided.")
    verb = cli_args[1] if len(cli_args) > 1 else ""
    if verb in WRITE_VERBS and not args.confirm_write:
        raise SystemExit(
            f"Refusing write verb `{verb}` without --confirm-write. "
            "Preview the action and confirm explicitly."
        )
    return run_opencli(cli_args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Guarded wrapper around opencli.")
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list", help="List opencli registry entries.")
    list_parser.add_argument(
        "--format",
        default="yaml",
        choices=["table", "json", "yaml", "md", "csv"],
    )
    list_parser.set_defaults(func=cmd_list)

    probe_parser = sub.add_parser("probe", help="Show registry output for a site.")
    probe_parser.add_argument("--site", required=True)
    probe_parser.add_argument(
        "--format",
        default="yaml",
        choices=["table", "json", "yaml", "md", "csv"],
    )
    probe_parser.set_defaults(func=cmd_probe)

    run_parser = sub.add_parser("run", help="Run an opencli command with write guards.")
    run_parser.add_argument(
        "--confirm-write",
        action="store_true",
        help="Allow a guarded write verb such as post/like/follow/delete.",
    )
    run_parser.add_argument("cli_args", nargs=argparse.REMAINDER)
    run_parser.set_defaults(func=cmd_run)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

