#!/usr/bin/env python3
"""Static and entrypoint checks for ai-da-guan-jia."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKILL_MD = ROOT / "SKILL.md"
MAIN_SCRIPT = ROOT / "scripts" / "ai_da_guan_jia.py"
REQUIRED_FILES = [
    ROOT / ".gitignore",
    ROOT / "agents" / "openai.yaml",
    ROOT / "references" / "meta-constitution.md",
    ROOT / "references" / "core-roster.md",
    ROOT / "references" / "skill-review-rubric.md",
    ROOT / "references" / "daily-review-contract.md",
    ROOT / "references" / "routing-policy.md",
    ROOT / "references" / "evolution-log-schema.md",
    ROOT / "references" / "feishu-sync-contract.md",
    ROOT / "references" / "github-governance-contract.md",
    ROOT / "references" / "github-sync-contract.md",
    ROOT / "references" / "github-taxonomy.md",
    ROOT / "references" / "github-naming-policy.md",
    ROOT / "references" / "github-project-schema.md",
    ROOT / "references" / "feishu-review-base-schema.json",
    ROOT / "references" / "feishu-review-sync-contract.md",
    ROOT / "references" / "validated-evolution-rules.md",
    ROOT / "assets" / "github-governance" / ".github" / "ISSUE_TEMPLATE" / "task-intake.yml",
    ROOT / "assets" / "github-governance" / ".github" / "PULL_REQUEST_TEMPLATE.md",
    MAIN_SCRIPT,
    ROOT / "scripts" / "doctor.py",
]
ROSTER_NAMES = [
    "ai-metacognitive-core",
    "jiyao-youyao-haiyao",
    "jiyao-youyao-haiyao-zaiyao",
    "skill-creator",
    "skill-trainer-recursive",
    "guide-benchmark-learning",
    "openclaw-xhs-coevolution-lab",
    "knowledge-orchestrator",
    "self-evolution-max",
    "agency-agents-orchestrator",
    "feishu-bitable-bridge",
]
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def check_exists(path: Path, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"missing: {path}")


def resolve_link(source: Path, target: str) -> Path | None:
    if target.startswith("http://") or target.startswith("https://") or target.startswith("#"):
        return None
    if target.startswith("/"):
        return Path(target)
    return (source.parent / target).resolve()


def check_markdown_links(path: Path, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    for target in MARKDOWN_LINK_RE.findall(text):
        resolved = resolve_link(path, target)
        if resolved is None:
            continue
        if not resolved.exists():
            errors.append(f"broken link in {path}: {target} -> {resolved}")


def check_skill_md(errors: list[str]) -> None:
    if not SKILL_MD.exists():
        return
    text = SKILL_MD.read_text(encoding="utf-8")
    if "name: ai-da-guan-jia" not in text:
        errors.append("SKILL.md frontmatter missing correct name")
    if "structured evolution log" not in text:
        errors.append("SKILL.md description does not mention the evolution log contract")


def check_openai_yaml(errors: list[str]) -> None:
    path = ROOT / "agents" / "openai.yaml"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if 'display_name: "AI大管家"' not in text:
        errors.append("agents/openai.yaml missing display_name")
    if "allow_implicit_invocation: false" not in text:
        errors.append("agents/openai.yaml must disable implicit invocation")
    if "$ai-da-guan-jia" not in text:
        errors.append("agents/openai.yaml default_prompt must mention $ai-da-guan-jia")


def check_roster(errors: list[str]) -> None:
    path = ROOT / "references" / "core-roster.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    for name in ROSTER_NAMES:
        if name not in text:
            errors.append(f"core-roster.md missing {name}")


def check_entrypoints(errors: list[str]) -> None:
    for command in (
        ["python3", str(MAIN_SCRIPT), "--help"],
        ["python3", str(MAIN_SCRIPT), "inventory-skills", "--help"],
        ["python3", str(MAIN_SCRIPT), "review-skills", "--help"],
        ["python3", str(MAIN_SCRIPT), "route", "--help"],
        ["python3", str(MAIN_SCRIPT), "record-evolution", "--help"],
        ["python3", str(MAIN_SCRIPT), "sync-feishu", "--help"],
        ["python3", str(MAIN_SCRIPT), "sync-github", "--help"],
        ["python3", str(MAIN_SCRIPT), "close-task", "--help"],
    ):
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            errors.append(f"entrypoint failed: {' '.join(command)}")


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    check_exists(ROOT, errors)
    check_exists(SKILL_MD, errors)
    for path in REQUIRED_FILES:
        check_exists(path, errors)

    check_skill_md(errors)
    check_openai_yaml(errors)
    check_roster(errors)

    for path in [SKILL_MD, *REQUIRED_FILES]:
        if path.suffix == ".md" and path.exists():
            check_markdown_links(path, errors)

    if MAIN_SCRIPT.exists():
        check_entrypoints(errors)

    if "AI_DA_GUAN_JIA_FEISHU_LINK" not in os.environ and "AI_DA_GUAN_JIA_REVIEW_FEISHU_LINK" not in os.environ:
        warnings.append("No Feishu link env var is configured; built-in defaults will be used.")
    if "AI_DA_GUAN_JIA_GITHUB_OPS_REPO" not in os.environ:
        warnings.append("AI_DA_GUAN_JIA_GITHUB_OPS_REPO is not configured; GitHub sync will stay local-only or blocked.")

    if errors:
        print("FAILED")
        for item in errors:
            print(f"- {item}")
        if warnings:
            print("WARNINGS")
            for item in warnings:
                print(f"- {item}")
        return 1

    print("OK")
    print(f"root: {ROOT}")
    print(f"required files: {len(REQUIRED_FILES) + 1}")
    if warnings:
        print("WARNINGS")
        for item in warnings:
            print(f"- {item}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
