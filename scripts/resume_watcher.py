#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path("/Users/liming/Documents/codex-ai-gua-jia-01")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.feishu_writer import ingest_candidate
from scripts.resume_parser import SUPPORTED_SUFFIXES, parse_resume


LOCAL_TZ = timezone(timedelta(hours=8))
LOGGER = logging.getLogger("resume_watcher")


def now_stamp() -> str:
    return datetime.now(LOCAL_TZ).strftime("%Y%m%d-%H%M%S")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_fallback_score(resume_payload: dict[str, Any], *, reason: str) -> dict[str, Any]:
    text = str(resume_payload.get("plain_text") or "")
    char_count = len(text)
    heuristic = min(100, max(35, char_count // 80))
    if heuristic >= 85:
        grade = "A"
    elif heuristic >= 70:
        grade = "B"
    elif heuristic >= 55:
        grade = "C"
    else:
        grade = "D"
    return {
        "overall_score": heuristic,
        "grade": grade,
        "recommendation_summary": f"Fallback local heuristic score generated because {reason}.",
        "recommended_interview_questions": [],
        "fallback": True,
        "fallback_reason": reason,
    }


def scorer_command_template(explicit_command: str) -> str:
    if explicit_command.strip():
        return explicit_command.strip()
    default_path = REPO_ROOT / "scripts" / "talent_scorer.py"
    if default_path.exists():
        return "python3 scripts/talent_scorer.py --resume-json {resume_json} --output {score_json}"
    return ""


def run_scorer(
    *,
    resume_json_path: Path,
    score_json_path: Path,
    explicit_command: str,
    dry_run: bool,
) -> dict[str, Any]:
    template = scorer_command_template(explicit_command)
    if not template:
        return build_fallback_score(load_json(resume_json_path), reason="talent_scorer.py is missing")
    command = template.format(
        resume_json=str(resume_json_path),
        score_json=str(score_json_path),
    )
    LOGGER.info("Running scorer command: %s", command)
    completed = subprocess.run(
        command,
        shell=True,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        LOGGER.warning("Scorer command failed, falling back to heuristic score: %s", completed.stderr.strip() or completed.stdout.strip())
        payload = build_fallback_score(
            load_json(resume_json_path),
            reason=f"scorer_failed:{completed.returncode}",
        )
        save_json(score_json_path, payload)
        return payload
    if score_json_path.exists():
        return load_json(score_json_path)
    stdout = completed.stdout.strip()
    if stdout:
        payload = json.loads(stdout)
        save_json(score_json_path, payload)
        return payload
    payload = build_fallback_score(load_json(resume_json_path), reason="scorer_returned_no_output")
    save_json(score_json_path, payload)
    return payload


def supported_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES and not path.name.startswith(".")


def process_resume_file(
    path: Path,
    *,
    parsed_dir: Path,
    score_dir: Path,
    archive_dir: Path,
    error_dir: Path,
    target_project: str,
    target_role: str,
    source_channel: str,
    tag: str,
    scorer_version: str,
    notify_grades: set[str],
    notify_webhook: str,
    notify_chat_id: str,
    scorer_command: str,
    dry_run: bool,
) -> dict[str, Any]:
    stem = f"{path.stem}-{now_stamp()}"
    parsed_json = parsed_dir / f"{stem}.json"
    score_json = score_dir / f"{stem}.json"
    try:
        resume_payload = parse_resume(path)
        save_json(parsed_json, resume_payload)
        score_payload = run_scorer(
            resume_json_path=parsed_json,
            score_json_path=score_json,
            explicit_command=scorer_command,
            dry_run=dry_run,
        )
        result = ingest_candidate(
            resume_payload,
            score_payload,
            target_project=target_project,
            target_role=target_role,
            source_channel=source_channel,
            tag=tag,
            scorer_version=scorer_version,
            notify_grades=notify_grades,
            webhook_url=notify_webhook,
            chat_id=notify_chat_id,
            dry_run=dry_run,
        )
        result["source_file"] = str(path.resolve())
        if not dry_run:
            archive_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(archive_dir / path.name))
        return result
    except Exception as exc:
        error_dir.mkdir(parents=True, exist_ok=True)
        target = error_dir / path.name
        if path.exists() and not dry_run:
            shutil.move(str(path), str(target))
        return {
            "status": "failed",
            "source_file": str(path.resolve()),
            "error": str(exc),
            "error_file": str(target.resolve()) if target.exists() else "",
        }


def drain_inbox(
    inbox_dir: Path,
    *,
    parsed_dir: Path,
    score_dir: Path,
    archive_dir: Path,
    error_dir: Path,
    target_project: str,
    target_role: str,
    source_channel: str,
    tag: str,
    scorer_version: str,
    notify_grades: set[str],
    notify_webhook: str,
    notify_chat_id: str,
    scorer_command: str,
    dry_run: bool,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    inbox_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(inbox_dir.iterdir()):
        if not supported_file(path):
            continue
        LOGGER.info("Processing resume file %s", path)
        results.append(
            process_resume_file(
                path,
                parsed_dir=parsed_dir,
                score_dir=score_dir,
                archive_dir=archive_dir,
                error_dir=error_dir,
                target_project=target_project,
                target_role=target_role,
                source_channel=source_channel,
                tag=tag,
                scorer_version=scorer_version,
                notify_grades=notify_grades,
                notify_webhook=notify_webhook,
                notify_chat_id=notify_chat_id,
                scorer_command=scorer_command,
                dry_run=dry_run,
            )
        )
    return results


def watch_with_watchdog(inbox_dir: Path, callback: Any, interval_seconds: float) -> None:
    from watchdog.events import FileSystemEventHandler  # type: ignore
    from watchdog.observers import Observer  # type: ignore

    class Handler(FileSystemEventHandler):
        def on_created(self, event: Any) -> None:
            if not event.is_directory:
                callback()

    observer = Observer()
    observer.schedule(Handler(), str(inbox_dir), recursive=False)
    observer.start()
    LOGGER.info("watchdog observer started for %s", inbox_dir)
    try:
        while True:
            time.sleep(interval_seconds)
    finally:
        observer.stop()
        observer.join()


def main() -> int:
    parser = argparse.ArgumentParser(description="Watch a folder and auto-process PDF/DOCX/TXT resumes.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--inbox-dir", type=Path, default=REPO_ROOT / "tmp" / "proj-talent-03" / "inbox")
    common.add_argument("--parsed-dir", type=Path, default=REPO_ROOT / "tmp" / "proj-talent-03" / "parsed")
    common.add_argument("--score-dir", type=Path, default=REPO_ROOT / "tmp" / "proj-talent-03" / "scores")
    common.add_argument("--archive-dir", type=Path, default=REPO_ROOT / "tmp" / "proj-talent-03" / "archive")
    common.add_argument("--error-dir", type=Path, default=REPO_ROOT / "tmp" / "proj-talent-03" / "error")
    common.add_argument("--target-project", default="八万四千")
    common.add_argument("--target-role", default="私域运营负责人")
    common.add_argument("--source-channel", default="自动采集")
    common.add_argument("--tag", default="社招")
    common.add_argument("--scorer-version", default="v1-local")
    common.add_argument("--notify-grades", default="S,A,B")
    common.add_argument("--notify-webhook", default="")
    common.add_argument("--notify-chat-id", default="")
    common.add_argument("--scorer-command", default="", help="Override scorer shell command with {resume_json} and {score_json} placeholders")
    common.add_argument("--apply", action="store_true", help="Actually call scorer and Feishu writes")
    common.add_argument("--log-level", default="INFO")

    process_parser = subparsers.add_parser("process", parents=[common], help="Process all currently queued resumes once")
    process_parser.set_defaults(loop=False)

    watch_parser = subparsers.add_parser("watch", parents=[common], help="Continuously watch inbox dir")
    watch_parser.add_argument("--interval-seconds", type=float, default=5.0)
    watch_parser.set_defaults(loop=True)

    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO), format="%(asctime)s %(levelname)s %(message)s")
    notify_grades = {item.strip().upper() for item in args.notify_grades.split(",") if item.strip()}

    def callback() -> list[dict[str, Any]]:
        return drain_inbox(
            args.inbox_dir,
            parsed_dir=args.parsed_dir,
            score_dir=args.score_dir,
            archive_dir=args.archive_dir,
            error_dir=args.error_dir,
            target_project=args.target_project,
            target_role=args.target_role,
            source_channel=args.source_channel,
            tag=args.tag,
            scorer_version=args.scorer_version,
            notify_grades=notify_grades,
            notify_webhook=args.notify_webhook.strip(),
            notify_chat_id=args.notify_chat_id.strip(),
            scorer_command=args.scorer_command,
            dry_run=not args.apply,
        )

    if not args.loop:
        results = callback()
        sys.stdout.write(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
        return 0

    args.inbox_dir.mkdir(parents=True, exist_ok=True)
    try:
        import watchdog  # type: ignore  # noqa: F401

        callback()
        watch_with_watchdog(args.inbox_dir, callback, args.interval_seconds)
    except ModuleNotFoundError:
        LOGGER.info("watchdog not installed; falling back to polling every %.1f seconds", args.interval_seconds)
        while True:
            results = callback()
            if results:
                LOGGER.info("Processed %s file(s)", len(results))
            time.sleep(args.interval_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
