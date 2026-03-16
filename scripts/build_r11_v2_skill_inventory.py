#!/usr/bin/env python3
from __future__ import annotations

import ast
import base64
import csv
import json
import os
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ARTIFACT_DIR = ROOT / "artifacts" / "r11-v2-skill-inventory"
R11_CACHE_PATH = ROOT / "artifacts" / "r11-skill-panorama" / "skill_inventory_raw.json"
OWNER = "moonstachain"
WIKI_ARTIFACTS = [
    ROOT / "output" / "feishu-reader" / "r11-skill-wiki.json",
    ROOT / "output" / "feishu-reader" / "r11-business-base.json",
]
LOCAL_CODEX_ROOT = Path.home() / ".codex" / "skills"
LOCAL_OPENCLAW_ROOTS = [
    Path("/home/gem/workspace/agent/workspace/skills"),
    Path.home() / ".openclaw" / "skills",
    Path.home() / ".maxclaw" / "skills",
    Path.home() / ".agents" / "skills",
]
PROJECT_SCAN_ROOTS = [
    ROOT / "work" / "ai-da-guan-jia",
    ROOT / "scripts",
    ROOT / "mcp_server",
    ROOT / "mcp_server_feishu",
    ROOT / "proxy",
]
PROJECT_SKIP_PARTS = {
    ".git",
    "node_modules",
    "output",
    "artifacts",
    "tmp",
    "__pycache__",
    ".pytest_cache",
    ".playwright-cli",
    ".venv",
    ".venv-feishu-dashboard",
}
SKILL_FILE_PATTERNS = (
    "SKILL.md",
    "*.skill",
    "*.skill.md",
    "skill*.md",
)
SOURCE_PRIORITY = {
    "github": 0,
    "local_codex": 1,
    "current_project": 2,
    "local_openclaw": 3,
    "mcp_tool": 4,
    "feishu_wiki": 5,
    "feishu_bitable": 6,
}
KEYWORD_PATTERN = re.compile(r"[A-Za-z0-9_\u4e00-\u9fff.+#/-]{2,}")
SKILL_MENTION_PATTERN = re.compile(r"`([A-Za-z0-9_.:/-]+)`")


@dataclass
class SourceRecord:
    skill_id: str
    skill_name: str
    source_repo: str
    file_path: str
    source_type: str
    description: str
    trigger_keywords: list[str]
    input_params: str
    output_format: str
    dependencies: list[str]
    last_updated: str
    file_size_bytes: int
    status: str
    category: str
    source_note: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "source_repo": self.source_repo,
            "file_path": self.file_path,
            "source_type": self.source_type,
            "description": self.description,
            "trigger_keywords": self.trigger_keywords,
            "input_params": self.input_params,
            "output_format": self.output_format,
            "dependencies": self.dependencies,
            "last_updated": self.last_updated,
            "file_size_bytes": self.file_size_bytes,
            "status": self.status,
            "category": self.category,
            "source_note": self.source_note,
        }


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def run_text(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return proc.stdout


def run_json(cmd: list[str]) -> Any:
    return json.loads(run_text(cmd))


def short_text(value: str, limit: int = 50) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def slugify(value: str) -> str:
    slug = value.strip().lower().replace("_", "-").replace(" ", "-")
    slug = re.sub(r"[^a-z0-9\u4e00-\u9fff.-]+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or "unknown-skill"


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        return {}, text
    lines = text.splitlines()
    frontmatter: dict[str, str] = {}
    index = 1
    while index < len(lines):
        line = lines[index]
        if line.strip() == "---":
            body = "\n".join(lines[index + 1 :])
            return frontmatter, body
        if ":" in line:
            key, value = line.split(":", 1)
            frontmatter[key.strip()] = value.strip().strip("\"'")
        index += 1
    return {}, text


def markdown_sections(text: str) -> dict[str, list[str]]:
    current = ""
    sections: dict[str, list[str]] = defaultdict(list)
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("#"):
            current = re.sub(r"^#+\s*", "", line).strip().lower()
            continue
        sections[current].append(line)
    return sections


def extract_trigger_keywords(description: str, body: str) -> list[str]:
    phrases: list[str] = []
    candidate_lines = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if lowered.startswith(("use when", "trigger", "when to use", "当用户", "适用", "用于", "触发")):
            candidate_lines.append(stripped)
    candidate_lines.insert(0, description)
    for line in candidate_lines:
        for token in re.split(r"[，。；;、|/]", line):
            cleaned = re.sub(r"^[\-\*\d.\s`]+", "", token).strip()
            if 2 <= len(cleaned) <= 30:
                phrases.append(cleaned)
    result: list[str] = []
    seen: set[str] = set()
    for item in phrases:
        if item not in seen:
            seen.add(item)
            result.append(item)
        if len(result) >= 8:
            break
    return result


def extract_inputs_and_outputs(body: str) -> tuple[str, str]:
    sections = markdown_sections(body)
    input_keys = ["inputs", "input", "适用输入", "输入", "when to use"]
    output_keys = ["expected outputs", "output", "输出", "预期输出", "output contract", "expected outputs "]
    input_text = ""
    output_text = ""
    for key in input_keys:
        if key in sections:
            input_text = short_text(" ".join(line.strip() for line in sections[key] if line.strip()), limit=120)
            break
    for key in output_keys:
        if key in sections:
            output_text = short_text(" ".join(line.strip() for line in sections[key] if line.strip()), limit=120)
            break
    return input_text, output_text


def extract_dependencies(body: str) -> list[str]:
    candidates: list[str] = []
    for match in SKILL_MENTION_PATTERN.findall(body):
        token = match.strip()
        if token.endswith(".py") or "/" in token or token.startswith("--"):
            continue
        if len(token) > 40:
            continue
        candidates.append(token)
    result: list[str] = []
    seen: set[str] = set()
    for token in candidates:
        normalized = token.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
        if len(result) >= 12:
            break
    return result


def infer_category(skill_id: str, description: str, source_type: str) -> str:
    blob = f"{skill_id} {description}".lower()
    if source_type == "mcp_tool":
        return "工具"
    if any(token in blob for token in ["governance", "yuanli", "ontology", "evolution", "route", "router", "skill", "claude", "ai-da-guan-jia", "runtime", "governor"]):
        return "治理"
    if any(token in blob for token in ["business", "sales", "customer", "delivery", "feishu-dashboard", "dashboard", "bitable", "finance tracker", "运营", "经营", "客户"]):
        return "经营"
    if any(token in blob for token in ["quant", "backtest", "factor", "research", "market", "paper", "invest", "投研", "财经", "odyssey course"]):
        return "投研"
    if any(token in blob for token in ["teaching", "course", "教研", "training", "trainer", "meeting-intelligence"]):
        return "教学"
    if any(token in blob for token in ["wechat", "content", "title", "style", "xhs", "instagram", "tiktok", "twitter", "story", "writer", "公众号", "内容"]):
        return "内容"
    if any(token in blob for token in ["playwright", "figma", "github", "gh-", "cloudflare", "doc", "pdf", "speech", "spreadsheet", "screenshot", "linear", "atlas", "tool", "api"]):
        return "工具"
    return "其他"


def infer_status(path: str, body: str, source_type: str) -> str:
    blob = f"{path} {body}".lower()
    if source_type in {"feishu_wiki", "feishu_bitable"}:
        return "needs_manual_review"
    if "deprecated" in blob or "废弃" in blob:
        return "deprecated"
    if "draft" in blob or "草稿" in blob:
        return "draft"
    if "skill" in blob or "tool_definitions" in blob:
        return "active"
    return "unknown"


def build_source_record(
    *,
    text: str,
    source_repo: str,
    file_path: str,
    source_type: str,
    last_updated: str,
    file_size_bytes: int,
    source_note: str = "",
) -> SourceRecord:
    frontmatter, body = parse_frontmatter(text)
    raw_name = frontmatter.get("name") or Path(file_path).parent.name or Path(file_path).stem
    skill_id = slugify(raw_name)
    description = short_text(
        frontmatter.get("description")
        or next((line.strip() for line in body.splitlines() if line.strip()), "")
        or raw_name,
        limit=50,
    )
    input_params, output_format = extract_inputs_and_outputs(body)
    return SourceRecord(
        skill_id=skill_id,
        skill_name=raw_name.strip(),
        source_repo=source_repo,
        file_path=file_path,
        source_type=source_type,
        description=description,
        trigger_keywords=extract_trigger_keywords(description, body),
        input_params=input_params,
        output_format=output_format,
        dependencies=extract_dependencies(body),
        last_updated=last_updated,
        file_size_bytes=file_size_bytes,
        status=infer_status(file_path, body, source_type),
        category=infer_category(skill_id, description, source_type),
        source_note=source_note,
    )


def github_repos() -> list[dict[str, Any]]:
    return run_json(
        [
            "gh",
            "repo",
            "list",
            OWNER,
            "--limit",
            "200",
            "--json",
            "name,nameWithOwner,updatedAt,defaultBranchRef",
        ]
    )


def github_tree(repo_full_name: str, branch: str) -> list[dict[str, Any]]:
    payload = run_json(["gh", "api", f"repos/{repo_full_name}/git/trees/{branch}?recursive=1"])
    return list(payload.get("tree", []))


def is_skill_like_path(path: str) -> bool:
    name = Path(path).name.lower()
    return (
        name == "skill.md"
        or name.endswith(".skill")
        or name.endswith(".skill.md")
        or (name.startswith("skill") and name.endswith(".md"))
    )


def github_file_content(repo_full_name: str, path: str) -> str:
    encoded_path = quote(path, safe="/")
    payload = run_json(["gh", "api", f"repos/{repo_full_name}/contents/{encoded_path}"])
    content = str(payload.get("content", "")).replace("\n", "")
    return base64.b64decode(content).decode("utf-8", errors="ignore")


def collect_github_sources(scan_notes: list[str]) -> list[SourceRecord]:
    records: list[SourceRecord] = []
    local_index = local_skill_text_index()
    if R11_CACHE_PATH.exists():
        cached_rows = json.loads(R11_CACHE_PATH.read_text(encoding="utf-8"))
        scan_notes.append(f"github cache hit: {R11_CACHE_PATH}")
        local_hits = 0
        for item in cached_rows:
            repo_name = str(item.get("repo") or "")
            repo_full_name = f"{OWNER}/{repo_name}" if repo_name else ""
            path = str(item.get("path") or "")
            updated_at = str(item.get("last_updated") or "")
            cached_skill_id = slugify(str(item.get("skill_id") or Path(path).parent.name))
            if not repo_full_name or not path:
                continue
            if cached_skill_id in local_index:
                text, file_size = local_index[cached_skill_id]
                local_hits += 1
                note = "content hydrated from local codex mirror"
            else:
                try:
                    text = github_file_content(repo_full_name, path)
                except subprocess.CalledProcessError as exc:
                    scan_notes.append(f"github file failed: {repo_full_name}/{path}: {(exc.stderr or '').strip()}")
                    continue
                file_size = len(text.encode("utf-8"))
                note = ""
            records.append(
                build_source_record(
                    text=text,
                    source_repo=repo_name,
                    file_path=path,
                    source_type="github",
                    last_updated=updated_at,
                    file_size_bytes=file_size,
                    source_note=note,
                )
            )
        scan_notes.append(f"github local mirror hits: {local_hits}/{len(cached_rows)}")
        return records

    repos = github_repos()
    for repo in repos:
        repo_name = str(repo.get("name") or "")
        repo_full_name = str(repo.get("nameWithOwner") or "")
        updated_at = str(repo.get("updatedAt") or "")
        branch = str((repo.get("defaultBranchRef") or {}).get("name") or "")
        if not branch:
            scan_notes.append(f"github skip: {repo_full_name} missing default branch")
            continue
        try:
            tree = github_tree(repo_full_name, branch)
        except subprocess.CalledProcessError as exc:
            scan_notes.append(f"github tree failed: {repo_full_name}: {(exc.stderr or '').strip()}")
            continue
        for item in tree:
            path = str(item.get("path") or "")
            if not is_skill_like_path(path):
                continue
            try:
                text = github_file_content(repo_full_name, path)
            except subprocess.CalledProcessError as exc:
                scan_notes.append(f"github file failed: {repo_full_name}/{path}: {(exc.stderr or '').strip()}")
                continue
            records.append(
                build_source_record(
                    text=text,
                    source_repo=repo_name,
                    file_path=path,
                    source_type="github",
                    last_updated=updated_at,
                    file_size_bytes=len(text.encode("utf-8")),
                )
            )
    return records


def iter_local_skill_files(root: Path, *, recursive: bool = False) -> list[Path]:
    if not root.exists():
        return []
    if recursive:
        return sorted(
            path
            for path in root.rglob("*")
            if path.is_file() and is_skill_like_path(path.name)
        )
    files = list(root.glob("*/SKILL.md"))
    files.extend(root.glob(".system/*/SKILL.md"))
    return sorted(path for path in files if path.is_file())


def collect_local_skill_sources(
    root: Path,
    source_type: str,
    source_repo: str,
    *,
    recursive: bool = False,
) -> list[SourceRecord]:
    records: list[SourceRecord] = []
    for path in iter_local_skill_files(root, recursive=recursive):
        text = path.read_text(encoding="utf-8", errors="ignore")
        stat = path.stat()
        records.append(
            build_source_record(
                text=text,
                source_repo=source_repo,
                file_path=str(path),
                source_type=source_type,
                last_updated=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                file_size_bytes=stat.st_size,
            )
        )
    return records


def local_skill_text_index() -> dict[str, tuple[str, int]]:
    index: dict[str, tuple[str, int]] = {}
    for path in iter_local_skill_files(LOCAL_CODEX_ROOT):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        index[slugify(path.parent.name)] = (text, path.stat().st_size)
    return index


def project_skill_files() -> list[Path]:
    files: list[Path] = []
    for scan_root in PROJECT_SCAN_ROOTS:
        if not scan_root.exists():
            continue
        if scan_root.is_file():
            if is_skill_like_path(scan_root.name):
                files.append(scan_root)
            continue
        for current_root, dirnames, filenames in os.walk(scan_root):
            dirnames[:] = [name for name in dirnames if name not in PROJECT_SKIP_PARTS]
            for filename in filenames:
                if is_skill_like_path(filename):
                    files.append(Path(current_root) / filename)
    skill_manifest = ROOT / "skill-manifest.json"
    if skill_manifest.exists():
        files.append(skill_manifest)
    return sorted(set(path.resolve() for path in files))


def collect_current_project_sources() -> list[SourceRecord]:
    records: list[SourceRecord] = []
    for path in project_skill_files():
        stat = path.stat()
        if path.name == "skill-manifest.json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            text = json.dumps(payload, ensure_ascii=False)
            record = SourceRecord(
                skill_id="skill-manifest",
                skill_name="skill-manifest",
                source_repo="ai-da-guan-jia",
                file_path=str(path),
                source_type="current_project",
                description="当前项目的机器可读 skill 注册表",
                trigger_keywords=["skill manifest", "注册表", "路由"],
                input_params="tier/component_domain/control_level 等查询参数",
                output_format="JSON 清单",
                dependencies=[],
                last_updated=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                file_size_bytes=stat.st_size,
                status="active",
                category="治理",
            )
            records.append(record)
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        records.append(
            build_source_record(
                text=text,
                source_repo="ai-da-guan-jia",
                file_path=str(path),
                source_type="current_project",
                last_updated=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                file_size_bytes=stat.st_size,
            )
        )
    return records


def parse_tool_definitions(path: Path) -> list[dict[str, Any]]:
    module = ast.parse(path.read_text(encoding="utf-8"))
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "TOOL_DEFINITIONS":
                    return ast.literal_eval(node.value)
    return []


def collect_mcp_tools() -> list[SourceRecord]:
    specs = [
        ("ai-da-guan-jia-mcp", ROOT / "mcp_server" / "server.py"),
        ("ai-da-guan-jia-feishu-mcp", ROOT / "mcp_server_feishu" / "server.py"),
    ]
    records: list[SourceRecord] = []
    for source_repo, path in specs:
        for tool in parse_tool_definitions(path):
            name = str(tool.get("name") or "").strip()
            if not name:
                continue
            description = short_text(str(tool.get("description") or name), limit=50)
            input_schema = tool.get("inputSchema") or {}
            properties = sorted((input_schema.get("properties") or {}).keys())
            required = sorted(input_schema.get("required") or [])
            records.append(
                SourceRecord(
                    skill_id=f"mcp-{slugify(name)}",
                    skill_name=name,
                    source_repo=source_repo,
                    file_path=str(path),
                    source_type="mcp_tool",
                    description=description,
                    trigger_keywords=[name, description],
                    input_params=", ".join(required or properties),
                    output_format="MCP structuredContent JSON",
                    dependencies=[path.parent.name],
                    last_updated=datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    file_size_bytes=path.stat().st_size,
                    status="active",
                    category="工具",
                )
            )
    return records


def load_feishu_artifact(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def collect_feishu_entries(scan_notes: list[str]) -> tuple[list[SourceRecord], list[dict[str, Any]]]:
    wiki_records: list[SourceRecord] = []
    base_scan_notes: list[dict[str, Any]] = []
    for path in WIKI_ARTIFACTS:
        payload = load_feishu_artifact(path)
        if payload is None:
            scan_notes.append(f"missing Feishu artifact: {path}")
            continue
        title = str(payload.get("title") or path.stem)
        canonical_url = str(payload.get("canonical_url") or "")
        text_blob = "\n".join(
            [
                str(payload.get("text") or ""),
                " ".join(item.get("text", "") for item in payload.get("buttons", []) if isinstance(item, dict)),
            ]
        )
        related_lines = []
        for raw_line in text_blob.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if any(token in line.lower() for token in ["skill", "技能", "能力", "工具", "智能体"]):
                related_lines.append(line)
        deduped_lines: list[str] = []
        seen: set[str] = set()
        for line in related_lines:
            if line not in seen:
                seen.add(line)
                deduped_lines.append(line)
        if deduped_lines:
            for line in deduped_lines:
                wiki_records.append(
                    SourceRecord(
                        skill_id=f"wiki-{slugify(line)}",
                        skill_name=line,
                        source_repo="feishu-wiki",
                        file_path=canonical_url or str(path),
                        source_type="feishu_wiki",
                        description=short_text(f"飞书知识库可见条目：{line}", limit=50),
                        trigger_keywords=[line],
                        input_params="需人工打开对应飞书页面继续核验",
                        output_format="知识库页面/目录条目",
                        dependencies=[],
                        last_updated=iso_now(),
                        file_size_bytes=len(json.dumps(payload, ensure_ascii=False).encode("utf-8")),
                        status="needs_manual_review",
                        category="治理",
                        source_note=f"visible under {title}",
                    )
                )
        table_candidates = []
        after_data_table = False
        for raw_line in text_blob.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line == "数据表":
                after_data_table = True
                continue
            if after_data_table and line in {"收集表", "仪表盘", "工作流", "文档", "文件夹", "连接器中心", "应用", "表格", "新建视图", "评论"}:
                after_data_table = False
            if after_data_table:
                table_candidates.append(line)
        skill_tables = [
            name for name in table_candidates if any(token in name.lower() for token in ["skill", "技能", "能力", "工具", "智能体"])
        ]
        base_scan_notes.append(
            {
                "title": title,
                "canonical_url": canonical_url,
                "visible_table_candidates": table_candidates,
                "skill_related_tables": skill_tables,
            }
        )
    return wiki_records, base_scan_notes


def dedupe_and_merge(records: list[SourceRecord]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for record in records:
        bucket = merged.get(record.skill_id)
        source_entry = record.to_json()
        if bucket is None:
            merged[record.skill_id] = {
                **source_entry,
                "all_sources": [source_entry],
                "source_types": [record.source_type],
                "source_repos": [record.source_repo],
                "quadrant": "",
                "action_recommendation": "",
            }
            continue
        bucket["all_sources"].append(source_entry)
        if record.source_type not in bucket["source_types"]:
            bucket["source_types"].append(record.source_type)
        if record.source_repo not in bucket["source_repos"]:
            bucket["source_repos"].append(record.source_repo)
        bucket["trigger_keywords"] = sorted(set(bucket["trigger_keywords"]) | set(record.trigger_keywords))
        bucket["dependencies"] = sorted(set(bucket["dependencies"]) | set(record.dependencies))
        if SOURCE_PRIORITY.get(record.source_type, 99) < SOURCE_PRIORITY.get(bucket["source_type"], 99):
            for key in [
                "skill_name",
                "source_repo",
                "file_path",
                "source_type",
                "description",
                "input_params",
                "output_format",
                "last_updated",
                "file_size_bytes",
                "status",
                "category",
                "source_note",
            ]:
                bucket[key] = source_entry[key]
    return sorted(merged.values(), key=lambda item: item["skill_id"])


def by_source(skills: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for skill in skills:
        for source_type in skill.get("source_types", []):
            counts[source_type] += 1
    return dict(sorted(counts.items()))


def by_category(skills: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(item.get("category") or "其他") for item in skills)
    return dict(sorted(counts.items()))


def by_status(skills: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(item.get("status") or "unknown") for item in skills)
    return dict(sorted(counts.items()))


def write_csv(skills: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "skill_id",
                "skill_name",
                "source_repo",
                "file_path",
                "source_type",
                "description",
                "trigger_keywords",
                "dependencies",
                "last_updated",
                "status",
                "category",
                "quadrant",
                "action_recommendation",
            ],
        )
        writer.writeheader()
        for item in skills:
            writer.writerow(
                {
                    "skill_id": item["skill_id"],
                    "skill_name": item["skill_name"],
                    "source_repo": item["source_repo"],
                    "file_path": item["file_path"],
                    "source_type": item["source_type"],
                    "description": item["description"],
                    "trigger_keywords": " | ".join(item.get("trigger_keywords", [])),
                    "dependencies": " | ".join(item.get("dependencies", [])),
                    "last_updated": item["last_updated"],
                    "status": item["status"],
                    "category": item["category"],
                    "quadrant": "",
                    "action_recommendation": "",
                }
            )


def print_summary(payload: dict[str, Any]) -> None:
    print("=== 原力OS全量Skill盘点摘要 ===")
    print(f"扫描时间：{payload['scan_timestamp']}")
    print("扫描位置：GitHub owner repos + 本地Codex/OpenClaw + 飞书知识库/可见base + MCP工具 + 当前项目")
    print(f"总计发现：{payload['total_skills']} 个 skill")
    print()
    print("按来源分布：")
    for key, value in payload["by_source"].items():
        print(f"  {key}：{value}")
    print()
    print("按类别分布：")
    for key, value in payload["by_category"].items():
        print(f"  {key}：{value}")
    print()
    print("按状态分布：")
    for key, value in payload["by_status"].items():
        print(f"  {key}：{value}")
    print()
    print("文件输出：")
    print(f"  {DATA_DIR / 'skill_inventory.json'}")
    print(f"  {DATA_DIR / 'skill_inventory.csv'}")


def main() -> int:
    ensure_dirs()
    scan_notes: list[str] = []
    records: list[SourceRecord] = []

    try:
        records.extend(collect_github_sources(scan_notes))
    except subprocess.CalledProcessError as exc:
        scan_notes.append(f"github owner scan failed: {(exc.stderr or '').strip()}")

    if LOCAL_CODEX_ROOT.exists():
        records.extend(collect_local_skill_sources(LOCAL_CODEX_ROOT, "local_codex", "local-codex"))
    else:
        scan_notes.append(f"local codex root missing: {LOCAL_CODEX_ROOT}")

    for root in LOCAL_OPENCLAW_ROOTS:
        if root.exists():
            records.extend(
                collect_local_skill_sources(
                    root,
                    "local_openclaw",
                    root.name,
                    recursive=True,
                )
            )
        else:
            scan_notes.append(f"local openclaw root missing: {root}")

    records.extend(collect_current_project_sources())
    records.extend(collect_mcp_tools())
    wiki_records, base_scan_notes = collect_feishu_entries(scan_notes)
    records.extend(wiki_records)

    merged = dedupe_and_merge(records)
    payload = {
        "scan_timestamp": iso_now(),
        "total_skills": len(merged),
        "by_source": by_source(merged),
        "by_category": by_category(merged),
        "by_status": by_status(merged),
        "skills": merged,
        "scan_notes": scan_notes,
        "feishu_base_scan": base_scan_notes,
    }

    json_path = DATA_DIR / "skill_inventory.json"
    csv_path = DATA_DIR / "skill_inventory.csv"
    summary_path = ARTIFACT_DIR / "skill_inventory_summary.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(merged, csv_path)
    summary_path.write_text(
        json.dumps(
            {
                "scan_timestamp": payload["scan_timestamp"],
                "total_skills": payload["total_skills"],
                "by_source": payload["by_source"],
                "by_category": payload["by_category"],
                "by_status": payload["by_status"],
                "scan_notes_count": len(scan_notes),
                "feishu_base_scan": base_scan_notes,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print_summary(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
