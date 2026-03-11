#!/usr/bin/env python3
"""Export a versionable mirror of local Codex skills."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime
from pathlib import Path


VOLATILE_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".venv",
    "venv",
    "node_modules",
    "artifacts",
    "state",
    "output",
    "tmp",
}
VOLATILE_FILE_SUFFIXES = {".pyc", ".pyo"}


def expand_path(value: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(value))).resolve()


def ignore_volatile(_root: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        if name in VOLATILE_DIR_NAMES:
            ignored.add(name)
            continue
        if Path(name).suffix in VOLATILE_FILE_SUFFIXES:
            ignored.add(name)
    return ignored


def export_skills(source: Path, destination: Path, clean: bool) -> dict[str, object]:
    if clean and destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)

    exported: list[dict[str, object]] = []
    for skill_dir in sorted(source.iterdir()):
        if not skill_dir.is_dir():
            continue
        if not (skill_dir / "SKILL.md").exists():
            continue
        target = destination / skill_dir.name
        shutil.copytree(skill_dir, target, dirs_exist_ok=True, ignore=ignore_volatile)
        exported.append(
            {
                "name": skill_dir.name,
                "source": str(skill_dir),
                "destination": str(target),
            }
        )

    manifest = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "source": str(source),
        "destination": str(destination),
        "count": len(exported),
        "excluded_dirs": sorted(VOLATILE_DIR_NAMES),
        "skills": exported,
    }
    (destination / "skills-mirror-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default="$HOME/.codex/skills",
        help="Source Codex skills directory.",
    )
    parser.add_argument(
        "--destination",
        required=True,
        help="Destination directory for the mirror export.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete the destination before exporting.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = expand_path(args.source)
    destination = expand_path(args.destination)
    manifest = export_skills(source, destination, clean=args.clean)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
