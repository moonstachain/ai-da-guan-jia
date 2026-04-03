#!/usr/bin/env python3
"""Skill Lazy Loader — On-demand skill loading inspired by Claude Code's ToolSearch pattern.

Instead of injecting all 71+ SKILL.md files into context (~50K tokens),
this module builds a lightweight index and loads skill details only when needed.

Usage:
    python3 skill_loader.py index          # Build/refresh the skill index
    python3 skill_loader.py search "飞书"   # Search skills by keyword
    python3 skill_loader.py load <name>     # Load full SKILL.md for a specific skill
    python3 skill_loader.py stats           # Show index statistics
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

SKILLS_ROOT = Path(os.getenv("CODEX_HOME", str(Path.home() / ".codex"))).resolve() / "skills"
INDEX_PATH = SKILLS_ROOT / ".skill-index.json"

# Chinese → English mapping (shared with governance_engine.py)
CN_EN_MAP: dict[str, list[str]] = {
    "飞书": ["feishu", "lark"], "多维表": ["bitable"], "同步": ["sync"],
    "进化": ["evolution"], "桥接": ["bridge"], "技能": ["skill"],
    "治理": ["governance"], "知识": ["knowledge"], "内容": ["content"],
    "设计": ["design"], "测试": ["testing"], "项目": ["project"],
    "营销": ["marketing"], "工程": ["engineering"], "支持": ["support"],
    "部署": ["deploy"], "截图": ["screenshot"], "自动化": ["automator"],
    "仪表盘": ["dashboard"], "克隆": ["clone"], "评估": ["eval", "review"],
    "消息": ["message", "im"], "文档": ["docs", "document"],
    "日历": ["calendar"], "审批": ["approval"],
}


@dataclass(frozen=True)
class SkillIndexEntry:
    """Lightweight skill metadata — always in memory (~100 bytes per skill)."""
    name: str
    layer: str
    description: str  # First line of SKILL.md description
    keywords: tuple[str, ...]  # Extracted from name + description
    has_scripts: bool
    has_references: bool
    path: str  # Absolute path to skill directory

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "layer": self.layer,
            "description": self.description,
            "keywords": list(self.keywords),
            "has_scripts": self.has_scripts,
            "has_references": self.has_references,
            "path": self.path,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SkillIndexEntry:
        return cls(
            name=d["name"],
            layer=d["layer"],
            description=d["description"],
            keywords=tuple(d.get("keywords", [])),
            has_scripts=d.get("has_scripts", False),
            has_references=d.get("has_references", False),
            path=d["path"],
        )


def _classify_layer(name: str) -> str:
    if name.startswith(("ai-", "skill-", "self-", "jiyao-")) or "knowledge" in name:
        return "meta"
    if name.startswith("agency-"):
        return "agency"
    if name.startswith(("feishu-", "github-", "notion-", "gh-")):
        return "platform"
    return "workflow"


def _extract_description(skill_md_path: Path) -> str:
    """Extract the description from SKILL.md frontmatter or first paragraph."""
    try:
        text = skill_md_path.read_text(encoding="utf-8")[:1000]
        # Try YAML frontmatter
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                for line in parts[1].strip().split("\n"):
                    if line.strip().startswith("description:"):
                        desc = line.split(":", 1)[1].strip().strip('"').strip("'")
                        return desc[:200]
        # Fallback: first non-empty, non-heading line
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith(("#", "---", "name:", "description:")):
                return stripped[:200]
    except Exception:
        pass
    return ""


def _extract_keywords(name: str, description: str) -> tuple[str, ...]:
    """Extract searchable keywords from name and description."""
    tokens = set()
    # From name
    for token in name.replace("-", " ").split():
        if len(token) > 1:
            tokens.add(token.lower())
    # From description (key words only)
    for token in description.lower().replace(",", " ").replace(".", " ").split():
        if len(token) > 2 and token.isascii():
            tokens.add(token)
    return tuple(sorted(tokens))


def build_index() -> list[SkillIndexEntry]:
    """Scan SKILLS_ROOT and build a lightweight index."""
    entries: list[SkillIndexEntry] = []
    if not SKILLS_ROOT.exists():
        return entries

    for skill_dir in sorted(SKILLS_ROOT.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        name = skill_dir.name
        description = _extract_description(skill_md)
        entry = SkillIndexEntry(
            name=name,
            layer=_classify_layer(name),
            description=description,
            keywords=_extract_keywords(name, description),
            has_scripts=(skill_dir / "scripts").exists(),
            has_references=(skill_dir / "references").exists(),
            path=str(skill_dir),
        )
        entries.append(entry)

    # Persist index
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(
        json.dumps(
            {"built_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "count": len(entries),
             "entries": [e.to_dict() for e in entries]},
            ensure_ascii=False, indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    return entries


@lru_cache(maxsize=1)
def load_index() -> tuple[SkillIndexEntry, ...]:
    """Load the skill index from cache, or build if stale/missing."""
    if INDEX_PATH.exists():
        try:
            data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
            return tuple(SkillIndexEntry.from_dict(e) for e in data["entries"])
        except Exception:
            pass
    return tuple(build_index())


def search_skills(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search the skill index by keyword with Chinese expansion."""
    index = load_index()
    text = query.lower()
    tokens = set(text.replace("/", " ").replace("-", " ").split())

    # Expand Chinese to English
    for cn, en_list in CN_EN_MAP.items():
        if cn in text:
            tokens.update(en_list)

    scored: list[tuple[float, SkillIndexEntry]] = []
    for entry in index:
        score = 0.0
        # Name token match
        name_tokens = set(entry.name.replace("-", " ").split())
        name_overlap = tokens & name_tokens
        score += len(name_overlap) * 2.0

        # Keyword match
        kw_overlap = tokens & set(entry.keywords)
        score += len(kw_overlap) * 1.0

        # Description substring match
        desc_lower = entry.description.lower()
        for t in tokens:
            if t in desc_lower:
                score += 0.5

        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {"name": e.name, "score": round(s, 1), "layer": e.layer,
         "description": e.description[:100], "has_scripts": e.has_scripts}
        for s, e in scored[:limit]
    ]


def load_skill(name: str) -> dict[str, Any]:
    """Load the full SKILL.md content for a specific skill (on-demand)."""
    index = load_index()
    for entry in index:
        if entry.name == name:
            skill_md = Path(entry.path) / "SKILL.md"
            if skill_md.exists():
                content = skill_md.read_text(encoding="utf-8")
                return {
                    "name": name,
                    "path": entry.path,
                    "layer": entry.layer,
                    "content": content,
                    "content_length": len(content),
                    "has_scripts": entry.has_scripts,
                    "has_references": entry.has_references,
                }
            return {"error": f"SKILL.md not found at {skill_md}"}
    return {"error": f"Skill '{name}' not in index"}


def index_stats() -> dict[str, Any]:
    """Return index statistics."""
    index = load_index()
    layers = {}
    for entry in index:
        layers[entry.layer] = layers.get(entry.layer, 0) + 1
    full_init_tokens = sum(
        len(Path(e.path, "SKILL.md").read_text(encoding="utf-8")) // 4
        for e in index
        if Path(e.path, "SKILL.md").exists()
    )
    index_tokens = sum(len(e.description) for e in index) // 4
    return {
        "total_skills": len(index),
        "by_layer": layers,
        "estimated_full_load_tokens": full_init_tokens,
        "estimated_index_only_tokens": index_tokens,
        "savings_ratio": round(1 - index_tokens / max(full_init_tokens, 1), 2),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="skill_loader", description="Skill lazy loader with on-demand loading.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("index", help="Build/refresh the skill index.")

    s = sub.add_parser("search", help="Search skills by keyword.")
    s.add_argument("query", help="Search query.")
    s.add_argument("--limit", type=int, default=10)

    l = sub.add_parser("load", help="Load full SKILL.md for a skill.")
    l.add_argument("name", help="Skill name.")

    sub.add_parser("stats", help="Show index statistics.")

    args = parser.parse_args(argv)

    if args.command == "index":
        entries = build_index()
        print(f"Indexed {len(entries)} skills → {INDEX_PATH}")
        return 0

    if args.command == "search":
        results = search_skills(args.query, limit=args.limit)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    if args.command == "load":
        result = load_skill(args.name)
        if "error" in result:
            print(result["error"], file=sys.stderr)
            return 1
        # Print metadata + content
        print(f"# {result['name']} ({result['layer']})")
        print(f"# path: {result['path']}")
        print(f"# content_length: {result['content_length']}")
        print(f"# has_scripts: {result['has_scripts']}, has_references: {result['has_references']}")
        print("---")
        print(result["content"])
        return 0

    if args.command == "stats":
        stats = index_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
