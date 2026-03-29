#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from zipfile import ZipFile
from xml.etree import ElementTree


LOCAL_TZ = timezone(timedelta(hours=8))
SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt"}


def now_iso() -> str:
    return datetime.now(LOCAL_TZ).isoformat()


def clean_text(value: str) -> str:
    text = value.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_text_file(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_bytes().decode("utf-8", errors="ignore")


def read_pdf(path: Path) -> tuple[str, str]:
    try:
        import pdfplumber  # type: ignore

        pages: list[str] = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
        text = clean_text("\n\n".join(pages))
        if text:
            return text, "pdfplumber"
    except Exception:
        pass

    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(path))
        text = clean_text("\n\n".join(page.extract_text() or "" for page in reader.pages))
        if text:
            return text, "pypdf"
    except Exception:
        pass

    if shutil_which("pdftotext"):
        try:
            completed = subprocess.run(
                ["pdftotext", str(path), "-"],
                check=False,
                capture_output=True,
                text=True,
            )
            text = clean_text(completed.stdout)
            if completed.returncode == 0 and text:
                return text, "pdftotext"
        except Exception:
            pass

    raise RuntimeError("Unable to extract text from PDF. Install pdfplumber, pypdf, or pdftotext.")


def read_docx(path: Path) -> tuple[str, str]:
    try:
        from docx import Document  # type: ignore

        doc = Document(str(path))
        text = clean_text("\n".join(para.text for para in doc.paragraphs if para.text.strip()))
        if text:
            return text, "python-docx"
    except Exception:
        pass

    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    try:
        with ZipFile(path) as archive:
            xml = archive.read("word/document.xml")
        root = ElementTree.fromstring(xml)
        parts: list[str] = []
        for para in root.findall(".//w:p", namespace):
            texts = [node.text or "" for node in para.findall(".//w:t", namespace)]
            merged = "".join(texts).strip()
            if merged:
                parts.append(merged)
        text = clean_text("\n".join(parts))
        if text:
            return text, "ooxml-fallback"
    except Exception as exc:  # pragma: no cover - fallback only
        raise RuntimeError(f"Unable to extract text from DOCX: {exc}") from exc

    raise RuntimeError("Unable to extract text from DOCX.")


def shutil_which(command: str) -> str | None:
    from shutil import which

    return which(command)


def infer_candidate_name(path: Path, text: str) -> str:
    stem = re.sub(r"[_-]+", " ", path.stem).strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines:
        first = lines[0]
        if 1 <= len(first) <= 30 and not re.search(r"[@:：/\\]", first):
            return first
    return stem


def extract_contacts(text: str) -> dict[str, list[str]]:
    emails = sorted(set(re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, flags=re.I)))
    phones = sorted(
        set(
            re.findall(
                r"(?:(?:\+?86[- ]?)?1[3-9]\d{9})|(?:\+?\d[\d -]{7,}\d)",
                text,
            )
        )
    )
    urls = sorted(set(re.findall(r"https?://[^\s)>]+", text)))
    return {"emails": emails, "phones": phones, "urls": urls}


def build_sections(text: str) -> dict[str, str]:
    lines = [line.strip() for line in text.splitlines()]
    buckets = {
        "education": [],
        "experience": [],
        "projects": [],
        "skills": [],
        "other": [],
    }
    current = "other"
    for line in lines:
        lower = line.lower()
        if any(token in line for token in ["教育", "学历", "毕业", "学校"]) or "education" in lower:
            current = "education"
        elif any(token in line for token in ["经历", "工作", "实习"]) or "experience" in lower:
            current = "experience"
        elif any(token in line for token in ["项目", "作品"]) or "project" in lower:
            current = "projects"
        elif any(token in line for token in ["技能", "能力", "工具"]) or "skill" in lower:
            current = "skills"
        buckets[current].append(line)
    return {key: clean_text("\n".join(value)) for key, value in buckets.items() if clean_text("\n".join(value))}


def build_summary(path: Path, text: str, extractor: str) -> dict[str, Any]:
    contacts = extract_contacts(text)
    sections = build_sections(text)
    candidate_name = infer_candidate_name(path, text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    snippet = "\n".join(lines[:12]).strip()
    return {
        "source_path": str(path.resolve()),
        "source_name": path.name,
        "suffix": path.suffix.lower(),
        "sha256": sha256_file(path),
        "parsed_at": now_iso(),
        "extractor": extractor,
        "candidate_name": candidate_name,
        "contacts": contacts,
        "sections": sections,
        "line_count": len(lines),
        "char_count": len(text),
        "summary_excerpt": snippet,
        "plain_text": text,
    }


def parse_resume(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"Unsupported resume suffix: {suffix}")
    if suffix == ".txt":
        text = clean_text(read_text_file(path))
        extractor = "text"
    elif suffix == ".pdf":
        text, extractor = read_pdf(path)
    else:
        text, extractor = read_docx(path)
    if not text:
        raise RuntimeError(f"No text extracted from {path}")
    return build_summary(path, text, extractor)


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse PDF/DOCX/TXT resumes into structured JSON.")
    parser.add_argument("source", type=Path, help="Resume file path (.pdf/.docx/.txt)")
    parser.add_argument("--output", type=Path, help="Optional output JSON path")
    parser.add_argument("--compact", action="store_true", help="Emit compact JSON")
    args = parser.parse_args()

    payload = parse_resume(args.source)
    text = json.dumps(payload, ensure_ascii=False, indent=None if args.compact else 2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
