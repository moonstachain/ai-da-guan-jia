#!/usr/bin/env python3
from __future__ import annotations

import argparse
import email
from email.header import decode_header, make_header
import imaplib
import json
import logging
import re
import sys
import time
from email.message import Message
from pathlib import Path
from typing import Any


SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt"}
LOGGER = logging.getLogger("email_collector")


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w.\-]+", "_", name.strip(), flags=re.UNICODE)
    return cleaned.strip("._") or "resume"


def decode_message_part(value: bytes | str | None, charset: str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    for candidate in [charset, "utf-8", "gb18030", "latin-1"]:
        if not candidate:
            continue
        try:
            return value.decode(candidate)
        except Exception:
            continue
    return value.decode("utf-8", errors="ignore")


def extract_text_body(message: Message) -> str:
    parts: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            disposition = str(part.get_content_disposition() or "").lower()
            if disposition == "attachment":
                continue
            if part.get_content_type() != "text/plain":
                continue
            payload = part.get_payload(decode=True)
            parts.append(decode_message_part(payload, part.get_content_charset()))
    else:
        payload = message.get_payload(decode=True)
        parts.append(decode_message_part(payload, message.get_content_charset()))
    return "\n".join(chunk.strip() for chunk in parts if chunk and chunk.strip()).strip()


def save_payload(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8")


def collect_from_message(message: Message, *, output_dir: Path, prefix: str) -> list[str]:
    saved: list[str] = []
    for index, part in enumerate(message.walk(), start=1):
        disposition = str(part.get_content_disposition() or "").lower()
        filename = part.get_filename()
        suffix = Path(filename or "").suffix.lower()
        if disposition == "attachment" and suffix in SUPPORTED_SUFFIXES:
            payload = part.get_payload(decode=True) or b""
            target = output_dir / f"{prefix}-{index}-{sanitize_filename(filename or f'attachment{suffix}')}"
            save_payload(target, payload)
            saved.append(str(target.resolve()))
    if saved:
        return saved
    body = extract_text_body(message)
    if body:
        target = output_dir / f"{prefix}-email-body.txt"
        save_payload(target, body)
        return [str(target.resolve())]
    return []


def fetch_once(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    mailbox: str,
    output_dir: Path,
    search_criterion: str,
    dry_run: bool,
    mark_seen: bool,
    use_ssl: bool,
) -> list[dict[str, Any]]:
    client_cls = imaplib.IMAP4_SSL if use_ssl else imaplib.IMAP4
    with client_cls(host, port) as client:
        client.login(username, password)
        client.select(mailbox)
        _, search_data = client.search(None, search_criterion)
        ids = [item for item in (search_data[0] or b"").split() if item]
        results: list[dict[str, Any]] = []
        for raw_id in ids:
            _, payload = client.fetch(raw_id, "(RFC822)")
            if not payload or not payload[0]:
                continue
            message = email.message_from_bytes(payload[0][1])
            subject = str(make_header(decode_header(message.get("Subject", ""))))
            prefix = sanitize_filename(f"{raw_id.decode()}-{subject}")[:120]
            if dry_run:
                saved = ["dry-run"]
            else:
                saved = collect_from_message(message, output_dir=output_dir, prefix=prefix)
            if mark_seen and not dry_run:
                client.store(raw_id, "+FLAGS", "\\Seen")
            results.append(
                {
                    "message_id": raw_id.decode(),
                    "subject": subject,
                    "saved_files": saved,
                    "from": message.get("From", ""),
                }
            )
        return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect resume attachments from IMAP and save them into the watcher inbox.")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=993)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--mailbox", default="INBOX")
    parser.add_argument("--output-dir", type=Path, default=Path("/Users/liming/Documents/codex-ai-gua-jia-01/tmp/proj-talent-03/inbox"))
    parser.add_argument("--search-criterion", default='(UNSEEN)')
    parser.add_argument("--mark-seen", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Actually download files")
    parser.add_argument("--loop", action="store_true", help="Poll forever")
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--plain-imap", action="store_true", help="Use IMAP without SSL")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO), format="%(asctime)s %(levelname)s %(message)s")

    while True:
        results = fetch_once(
            host=args.host,
            port=args.port,
            username=args.username,
            password=args.password,
            mailbox=args.mailbox,
            output_dir=args.output_dir,
            search_criterion=args.search_criterion,
            dry_run=not args.apply,
            mark_seen=args.mark_seen,
            use_ssl=not args.plain_imap,
        )
        sys.stdout.write(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
        if not args.loop:
            break
        time.sleep(args.interval_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
