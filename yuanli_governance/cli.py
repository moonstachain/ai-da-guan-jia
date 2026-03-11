"""CLI entrypoint for the Yuanli governance system."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import (
    build_cockpit,
    build_dashboard_blueprint,
    build_inventory,
    generate_morning_review,
    ingest_business,
    ingest_content,
    inventory_sources,
    mirror_feishu,
    probe_tencent_meeting_link,
    run_daily,
    transcribe_tencent_meeting_file,
    validate_sensitivity,
    validate_knowledge_source,
    validate_entities,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Yuanli governance system v1")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser("inventory", help="Scan local sources and rebuild canonical entities.")
    inventory.add_argument("--source-config", help="Override source scope JSON path.")

    source_inventory = subparsers.add_parser("inventory-sources", help="Scan grouped source roots and summarize registered feeds.")
    source_inventory.add_argument("--source-config", help="Override source scope JSON path.")

    ingest_business_parser = subparsers.add_parser("ingest-business", help="Build business and finance facts from local sources.")
    ingest_business_parser.add_argument("--source-config", help="Override source scope JSON path.")

    ingest_content_parser = subparsers.add_parser("ingest-content", help="Build content and knowledge asset indexes from local sources.")
    ingest_content_parser.add_argument("--source-config", help="Override source scope JSON path.")

    dashboard = subparsers.add_parser("build-dashboard", help="Generate Feishu dashboard blueprint bundle.")
    dashboard.add_argument("--source-config", help="Unused placeholder for CLI symmetry.")

    cockpit = subparsers.add_parser("build-cockpit", help="Build the dashboard blueprint and Feishu cockpit payload.")
    cockpit.add_argument("--source-config", help="Override source scope JSON path.")

    morning = subparsers.add_parser("morning-review", help="Generate the 09:00 special review bundle.")
    morning.add_argument("--source-config", help="Override source scope JSON path.")

    feishu = subparsers.add_parser("mirror-feishu", help="Generate or validate Feishu mirror payloads.")
    mode = feishu.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Validate local payload only.")
    mode.add_argument("--apply", action="store_true", help="Attempt apply after a successful dry-run.")

    validate = subparsers.add_parser("validate", help="Run local structural validation.")
    validate.add_argument("--source-config", help="Override source scope JSON path.")

    sensitivity = subparsers.add_parser("validate-sensitivity", help="Validate that Feishu payload exports are masked.")
    sensitivity.add_argument("--source-config", help="Override source scope JSON path.")

    knowledge = subparsers.add_parser(
        "validate-knowledge-source",
        help="Validate a Feishu knowledge source and register it in local canonical records.",
    )
    knowledge.add_argument("--url", required=True, help="Feishu wiki/doc/base URL to validate.")
    knowledge.add_argument("--headed", action="store_true", help="Open a headed browser for login-gated validation.")
    knowledge.add_argument("--output-slug", default="yuanli-planet-shared", help="Artifact subdirectory label.")
    knowledge.add_argument("--manual-confirmed", action="store_true", help="Write a validated result from manual browser confirmation.")
    knowledge.add_argument("--manual-title", help="Manual validation title override.")
    knowledge.add_argument("--manual-note", help="Manual validation evidence note.")
    knowledge.add_argument("--source-config", help="Override source scope JSON path.")

    tencent = subparsers.add_parser(
        "probe-tencent-meeting-link",
        help="Probe a Tencent Meeting cloud-record share link and register it as a governance source.",
    )
    tencent.add_argument("--link", required=True, help="Tencent Meeting crm/cw share link.")
    tencent.add_argument("--output-slug", help="Artifact subdirectory label.")
    tencent.add_argument("--timeout-seconds", type=float, default=20.0, help="HTTP fetch timeout in seconds.")
    tencent.add_argument("--source-config", help="Override source scope JSON path.")

    tencent_transcribe = subparsers.add_parser(
        "transcribe-tencent-meeting-file",
        help="Register an exported Tencent Meeting media file and transcribe it into a reusable transcript artifact.",
    )
    tencent_transcribe.add_argument("--file", required=True, help="Local exported MP4/audio path.")
    source_selector = tencent_transcribe.add_mutually_exclusive_group(required=True)
    source_selector.add_argument("--source-id", help="Existing Tencent Meeting source_id.")
    source_selector.add_argument("--link", help="Tencent Meeting crm/cw share link.")
    tencent_transcribe.add_argument("--timeout-seconds", type=int, default=1800, help="Get笔记 transcription timeout in seconds.")
    tencent_transcribe.add_argument("--source-config", help="Override source scope JSON path.")

    daily = subparsers.add_parser("run-daily", help="Run inventory, dashboard, dry-run mirror, and morning review.")
    daily.add_argument("--source-config", help="Override source scope JSON path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    source_config = Path(args.source_config).expanduser().resolve() if getattr(args, "source_config", None) else None

    if args.command == "inventory":
        result = build_inventory(source_config)
    elif args.command == "inventory-sources":
        result = inventory_sources(source_config)
    elif args.command == "ingest-business":
        result = ingest_business(source_config)
    elif args.command == "ingest-content":
        result = ingest_content(source_config)
    elif args.command == "build-dashboard":
        result = build_dashboard_blueprint()
    elif args.command == "build-cockpit":
        result = build_cockpit(source_config)
    elif args.command == "morning-review":
        result = generate_morning_review(source_config)
    elif args.command == "mirror-feishu":
        result = mirror_feishu(dry_run=args.dry_run, apply=args.apply)
    elif args.command == "validate":
        result = validate_entities(source_config)
    elif args.command == "validate-sensitivity":
        result = validate_sensitivity(source_config)
    elif args.command == "validate-knowledge-source":
        result = validate_knowledge_source(
            args.url,
            scope_path=source_config,
            headed=args.headed,
            output_slug=args.output_slug,
            manual_confirmed=args.manual_confirmed,
            manual_title=str(args.manual_title or ""),
            manual_note=str(args.manual_note or ""),
        )
    elif args.command == "probe-tencent-meeting-link":
        result = probe_tencent_meeting_link(
            args.link,
            scope_path=source_config,
            output_slug=args.output_slug,
            timeout_seconds=args.timeout_seconds,
        )
    elif args.command == "transcribe-tencent-meeting-file":
        result = transcribe_tencent_meeting_file(
            file_path=args.file,
            source_id=str(args.source_id or ""),
            link=str(args.link or ""),
            scope_path=source_config,
            timeout_seconds=args.timeout_seconds,
        )
    elif args.command == "run-daily":
        result = run_daily(source_config)
    else:
        parser.error(f"Unknown command: {args.command}")
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
