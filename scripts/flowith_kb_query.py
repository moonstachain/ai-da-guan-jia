#!/usr/bin/env python3
"""Minimal Flowith Knowledge Base query probe.

Usage:
  FLOWITH_API_TOKEN=... FLOWITH_KB_ID=... python3 scripts/flowith_kb_query.py \
    --query "Summarize my notes about identity"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request


DEFAULT_ENDPOINT = "https://api.flowith.io/v1/knowledge_base/query"
DEFAULT_TIMEOUT = 45
DEFAULT_USER_AGENT = "Codex-Flowith-Probe/1.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query a Flowith knowledge base with the official knowledge retrieval API.",
    )
    parser.add_argument("--token", default=os.getenv("FLOWITH_API_TOKEN", ""), help="Flowith API token.")
    parser.add_argument("--kb-id", default=os.getenv("FLOWITH_KB_ID", ""), help="Flowith knowledge base id.")
    parser.add_argument("--query", required=True, help="Query text sent to Flowith.")
    parser.add_argument(
        "--mode",
        choices=["fast", "deep"],
        default=os.getenv("FLOWITH_QUERY_MODE", "fast"),
        help="Retrieval mode. Defaults to fast.",
    )
    parser.add_argument(
        "--endpoint",
        default=os.getenv("FLOWITH_API_ENDPOINT", DEFAULT_ENDPOINT),
        help="Override the Flowith API endpoint.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(os.getenv("FLOWITH_API_TIMEOUT", str(DEFAULT_TIMEOUT))),
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--out",
        help="Optional JSON output file path.",
    )
    return parser


def make_request(*, endpoint: str, token: str, kb_id: str, query: str, mode: str, timeout: int) -> dict[str, Any]:
    payload = {
        "kb_id": kb_id,
        "query": query,
        "mode": mode,
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib_request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
        },
    )

    try:
        with urllib_request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            content_type = response.headers.get("Content-Type", "")
            parsed: Any
            if "application/json" in content_type.lower():
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = {"raw": raw}
            else:
                parsed = {"raw": raw}
            return {
                "ok": True,
                "status": response.status,
                "endpoint": endpoint,
                "payload": payload,
                "response": parsed,
            }
    except urllib_error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        parsed: Any
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return {
            "ok": False,
            "status": exc.code,
            "endpoint": endpoint,
            "payload": payload,
            "response": parsed,
        }


def validate_args(args: argparse.Namespace) -> None:
    if not args.token:
        raise SystemExit("Missing API token. Set FLOWITH_API_TOKEN or pass --token.")
    if not args.kb_id:
        raise SystemExit("Missing knowledge base id. Set FLOWITH_KB_ID or pass --kb-id.")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    validate_args(args)
    result = make_request(
        endpoint=args.endpoint,
        token=args.token,
        kb_id=args.kb_id,
        query=args.query,
        mode=args.mode,
        timeout=args.timeout,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        output_path = Path(args.out).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
