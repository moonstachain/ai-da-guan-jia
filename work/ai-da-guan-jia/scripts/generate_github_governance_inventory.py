#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path("/Users/liming/Documents/codex-ai-gua-jia-01")
REPORTS_DIR = WORKSPACE_ROOT / "work/ai-da-guan-jia/artifacts/reports"
REFERENCES_DIR = WORKSPACE_ROOT / "work/ai-da-guan-jia/references"


@dataclass(frozen=True)
class RepoTarget:
    name: str
    role: str
    active_path: Path
    declared_remote_url: str
    dependency_basis: str
    dependencies: list[str]
    notes: str
    metadata_path: Path | None = None


TARGETS: list[RepoTarget] = [
    RepoTarget(
        name="yuanli-os-claude",
        role="策略启动记忆、Task Spec、策略分发",
        active_path=WORKSPACE_ROOT / "yuanli-os-claude",
        metadata_path=WORKSPACE_ROOT / "mac-max-backup-2026/yuanli-os-claude 3",
        declared_remote_url="git@github.com:moonstachain/yuanli-os-claude.git",
        dependency_basis="Observed from backup clone remote and repo map in yuanli-os-claude/CLAUDE-INIT.md.",
        dependencies=["os-yuanli", "ai-da-guan-jia"],
        notes="Active path is an embedded workspace directory; the verified Git remote exists only in a backup clone on this machine.",
    ),
    RepoTarget(
        name="ai-da-guan-jia",
        role="治理内核、canonical local execution",
        active_path=WORKSPACE_ROOT / "work/ai-da-guan-jia",
        metadata_path=None,
        declared_remote_url="git@github.com:moonstachain/ai-da-guan-jia.git",
        dependency_basis="Declared in bootstrap-new-mac.sh and the repository map embedded in CLAUDE-INIT.md.",
        dependencies=["os-yuanli", "yuanli-os-claude", "yuanli-os-skills-pack"],
        notes="No standalone clone was found on this machine; the active materials live inside the workspace monorepo and installed skill surfaces.",
    ),
    RepoTarget(
        name="yuanli-os-skills-pack",
        role="共享 Skill 分发层",
        active_path=WORKSPACE_ROOT / "tmp/external-repos/yuanli-os-skills-pack",
        metadata_path=WORKSPACE_ROOT / "tmp/external-repos/yuanli-os-skills-pack",
        declared_remote_url="git@github.com:moonstachain/yuanli-os-skills-pack.git",
        dependency_basis="Verified from local git remote plus manifest references to moonstachain/ai-da-guan-jia and moonstachain/os-yuanli.",
        dependencies=["os-yuanli", "ai-da-guan-jia"],
        notes="This is the cleanest independently cloned repo in the current workspace.",
    ),
    RepoTarget(
        name="os-yuanli",
        role="上位总纲 root skill",
        active_path=WORKSPACE_ROOT / "tmp/external-repos/os-yuanli",
        metadata_path=None,
        declared_remote_url="git@github.com:moonstachain/os-yuanli.git",
        dependency_basis="Declared in CLAUDE-INIT.md and reinforced by tmp/external-repos/os-yuanli/README.md.",
        dependencies=[],
        notes="The local path exists as a published-copy directory inside the workspace repo, but not as an independent git clone.",
    ),
    RepoTarget(
        name="yuanli-os-ops",
        role="运营协作层",
        active_path=WORKSPACE_ROOT / "tmp/external-repos/yuanli-os-ops",
        metadata_path=WORKSPACE_ROOT / "tmp/external-repos/yuanli-os-ops",
        declared_remote_url="git@github.com:moonstachain/yuanli-os-ops.git",
        dependency_basis="Verified from local git remote plus bootstrap manifests listing os-yuanli, ai-da-guan-jia, and yuanli-os-skills-pack.",
        dependencies=["os-yuanli", "ai-da-guan-jia", "yuanli-os-skills-pack"],
        notes="This repo has a verified standalone clone, but its bootstrap contracts show it still depends on the other governance repos.",
    ),
]


def run(
    args: list[str],
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        check=check,
        text=True,
        capture_output=True,
    )


def git_root(path: Path) -> Path | None:
    result = run(["git", "-C", str(path), "rev-parse", "--show-toplevel"], check=False)
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def git_status_entries(root: Path, pathspec: str | None = None) -> list[dict[str, str]]:
    args = ["git", "-C", str(root), "status", "--porcelain", "-z"]
    if pathspec:
        args.extend(["--", pathspec])
    result = run(args, check=True)
    payload = result.stdout
    chunks = payload.split("\0")
    entries: list[dict[str, str]] = []
    i = 0
    while i < len(chunks):
        chunk = chunks[i]
        if not chunk:
            i += 1
            continue
        status = chunk[:2]
        path = chunk[3:]
        original_path = ""
        if status and status[0] in {"R", "C"}:
            i += 1
            if i < len(chunks):
                original_path = path
                path = chunks[i]
        entries.append({"status": status, "path": path, "original_path": original_path})
        i += 1
    return entries


def count_status_entries(root: Path, pathspec: str | None = None) -> int:
    return len(git_status_entries(root, pathspec))


def top_level_entries(path: Path) -> list[str]:
    if not path.exists():
        return []
    return sorted(item.name for item in path.iterdir())


def has_readme(path: Path) -> bool:
    return any((path / name).exists() for name in ("README.md", "README.MD", "readme.md"))


def git_metadata(path: Path) -> dict[str, Any]:
    if not (path / ".git").exists() and git_root(path) != path:
        return {
            "is_git_repo": False,
            "git_root": None,
            "remote_urls": [],
            "default_branch": None,
            "total_commits": None,
            "last_commit": None,
            "branches": [],
            "tags": [],
        }

    remote_lines = run(["git", "-C", str(path), "remote", "-v"], check=False).stdout.strip().splitlines()
    remote_urls: dict[str, str] = {}
    for line in remote_lines:
        parts = line.split()
        if len(parts) >= 3 and parts[2] == "(fetch)":
            remote_urls[parts[0]] = parts[1]
    current_branch = run(["git", "-C", str(path), "branch", "--show-current"], check=False).stdout.strip() or None
    commit_count_raw = run(["git", "-C", str(path), "rev-list", "--count", "HEAD"], check=False).stdout.strip()
    last_commit_raw = run(
        [
            "git",
            "-C",
            str(path),
            "log",
            "-1",
            "--date=iso",
            "--pretty=format:%H|%ad|%an|%s",
        ],
        check=False,
    ).stdout.strip()
    branches = [
        line
        for line in run(
            ["git", "-C", str(path), "for-each-ref", "refs/heads", "refs/remotes", "--format=%(refname:short)"],
            check=False,
        ).stdout.splitlines()
        if line
    ]
    tags = [line for line in run(["git", "-C", str(path), "tag", "--sort=refname"], check=False).stdout.splitlines() if line]
    last_commit = None
    if last_commit_raw:
        commit_hash, committed_at, author, subject = (last_commit_raw.split("|", 3) + ["", "", "", ""])[:4]
        last_commit = {
            "hash": commit_hash,
            "committed_at": committed_at,
            "author": author,
            "subject": subject,
        }
    return {
        "is_git_repo": True,
        "git_root": str(path),
        "remote_urls": [{"name": key, "url": value} for key, value in remote_urls.items()],
        "default_branch": current_branch,
        "total_commits": int(commit_count_raw) if commit_count_raw.isdigit() else None,
        "last_commit": last_commit,
        "branches": branches,
        "tags": tags,
    }


def classify_path(status: str, path: str) -> tuple[str, str]:
    normalized = path.replace("\\", "/")
    should_gitignore_prefixes = (
        ".playwright-cli/",
        ".pytest_cache/",
        ".venv",
    )
    pending_human_prefixes = (
        "dashboard/",
        "data/",
        "input/",
        "mac-max-backup-2026/",
    )
    should_commit_prefixes = (
        "automations/",
        "canonical/",
        "derived/",
        "distribution/",
        "docs/",
        "ontology/",
        "scripts/",
        "specs/",
        "tests/",
        "work/",
        "yuanli-os-claude/",
        "yuanli_governance/",
    )
    if normalized.startswith(should_gitignore_prefixes):
        return "should_gitignore", "Local environment cache or virtualenv artifact."
    if normalized.startswith('", '):
        return "should_delete", "Looks like an accidental shell heredoc artifact with a broken filename."
    if normalized in {".DS_Store"}:
        return "should_gitignore", "Machine-specific Finder metadata should not remain tracked."
    if normalized.startswith(pending_human_prefixes):
        return "pending_human", "Large imported or backup material needs a human keep-or-externalize decision."
    if normalized.startswith(should_commit_prefixes):
        return "should_commit", "Repository source or governance artifact that likely belongs in version control."
    if normalized.endswith(".command") or normalized.endswith(".py") or normalized.endswith(".md") or normalized.endswith(".json"):
        return "should_commit", "Source or documentation file that looks intentional."
    if status == "??":
        return "pending_human", "Untracked path without a strong pattern match."
    return "should_commit", "Tracked modification with no ignore/delete signal."


def triage_workspace() -> dict[str, Any]:
    entries = git_status_entries(WORKSPACE_ROOT)
    grouped: dict[str, list[dict[str, str]]] = {
        "should_commit": [],
        "should_gitignore": [],
        "should_delete": [],
        "pending_human": [],
    }
    for entry in entries:
        bucket, reason = classify_path(entry["status"], entry["path"])
        grouped[bucket].append(
            {
                "status": entry["status"],
                "path": entry["path"],
                "reason": reason,
            }
        )
    return {
        "workspace_git_root": str(WORKSPACE_ROOT),
        "total_entries": len(entries),
        "grouped": grouped,
    }


def active_path_mode(target: RepoTarget, active_root: Path | None) -> str:
    if target.metadata_path and target.metadata_path == target.active_path and active_root == target.active_path:
        return "standalone_git_clone"
    if target.metadata_path and target.metadata_path != target.active_path:
        return "embedded_active_path_with_backup_clone"
    if active_root == WORKSPACE_ROOT:
        return "embedded_directory_in_workspace_repo"
    if target.active_path.exists():
        return "local_directory_without_git_clone"
    return "missing_local_path"


def collect_inventory() -> dict[str, Any]:
    observed_git_roots = []
    for candidate in [
        WORKSPACE_ROOT,
        WORKSPACE_ROOT / "tmp/external-repos/yuanli-os-ops",
        WORKSPACE_ROOT / "tmp/external-repos/yuanli-os-skills-pack",
        WORKSPACE_ROOT / "mac-max-backup-2026/yuanli-os-claude 3",
    ]:
        root = git_root(candidate)
        if root and str(root) not in observed_git_roots:
            observed_git_roots.append(str(root))

    repos = []
    for target in TARGETS:
        active_root = git_root(target.active_path)
        metadata_path = target.metadata_path if target.metadata_path and target.metadata_path.exists() else None
        metadata = git_metadata(metadata_path) if metadata_path else {
            "is_git_repo": False,
            "git_root": None,
            "remote_urls": [],
            "default_branch": None,
            "total_commits": None,
            "last_commit": None,
            "branches": [],
            "tags": [],
        }
        if metadata["is_git_repo"]:
            uncommitted_count = count_status_entries(Path(metadata["git_root"]))
            metadata_source = "verified_local_git_clone"
        elif active_root == WORKSPACE_ROOT:
            rel = str(target.active_path.relative_to(WORKSPACE_ROOT))
            uncommitted_count = count_status_entries(WORKSPACE_ROOT, rel)
            metadata_source = "workspace_path_projection"
        else:
            uncommitted_count = None
            metadata_source = "declared_only"

        repos.append(
            {
                "name": target.name,
                "url": metadata["remote_urls"][0]["url"] if metadata["remote_urls"] else target.declared_remote_url,
                "url_status": "verified_remote" if metadata["remote_urls"] else "declared_from_local_docs",
                "role": target.role,
                "default_branch": metadata["default_branch"],
                "total_commits": metadata["total_commits"],
                "last_commit": metadata["last_commit"],
                "uncommitted_count": uncommitted_count,
                "branches": metadata["branches"],
                "tags": metadata["tags"],
                "top_level_dirs": top_level_entries(target.active_path),
                "has_readme": has_readme(target.active_path),
                "dependencies": target.dependencies,
                "dependency_basis": target.dependency_basis,
                "active_path": str(target.active_path),
                "metadata_source_path": str(metadata_path) if metadata_path else None,
                "metadata_source": metadata_source,
                "path_mode": active_path_mode(target, active_root),
                "active_path_git_root": str(active_root) if active_root else None,
                "notes": target.notes,
            }
        )

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "machine_scope": str(WORKSPACE_ROOT),
        "inventory_basis": [
            "Filesystem probe of current workspace and nearby backup/external-repo directories.",
            "Git metadata taken only from verified local clones.",
            "Declared repo URLs filled from local docs when no clone was present on this machine.",
        ],
        "observed_git_roots": observed_git_roots,
        "logical_repo_count": len(TARGETS),
        "verified_independent_clone_count": sum(1 for repo in repos if repo["path_mode"] == "standalone_git_clone"),
        "repos": repos,
        "workspace_repo": {
            "git_root": str(WORKSPACE_ROOT),
            "default_branch": run(["git", "-C", str(WORKSPACE_ROOT), "branch", "--show-current"], check=False).stdout.strip() or None,
            "uncommitted_count": count_status_entries(WORKSPACE_ROOT),
            "remote_urls": [],
            "notes": "The active workspace itself is a git repo, but it currently has no configured remote.",
        },
        "fact_inference_split": {
            "confirmed": [
                "Only yuanli-os-ops and yuanli-os-skills-pack are verified as independent active clones under the current workspace.",
                "A separate backup clone exists for yuanli-os-claude at mac-max-backup-2026/yuanli-os-claude 3.",
                "The active workspace repo is dirty and currently has no configured git remote.",
            ],
            "inferred": [
                "ai-da-guan-jia and os-yuanli are intended GitHub repos, but this machine currently exposes them as embedded/published-copy directories rather than standalone clones.",
                "Cross-repo dependencies are governance/operating dependencies documented in local manifests, not strict code-import dependencies.",
            ],
        },
    }


def render_triage_markdown(triage: dict[str, Any]) -> str:
    grouped = triage["grouped"]
    lines = [
        "# Uncommitted Files Triage",
        "",
        f"- Generated at: `{datetime.now().astimezone().isoformat()}`",
        f"- Workspace git root: `{triage['workspace_git_root']}`",
        f"- Total uncommitted entries: `{triage['total_entries']}`",
        "",
        "## Summary",
        "",
    ]
    for key in ("should_commit", "should_gitignore", "should_delete", "pending_human"):
        lines.append(f"- `{key}`: {len(grouped[key])}")
    lines.extend(
        [
            "",
            "## Heuristic Notes",
            "",
            "- `should_commit`: source, docs, specs, scripts, governance artifacts, and tracked edits that look intentional.",
            "- `should_gitignore`: local caches, virtualenvs, or machine-only metadata.",
            "- `should_delete`: obvious accidental shell artifacts only; anything ambiguous is pushed to `pending_human` instead.",
            "- `pending_human`: imported datasets, backups, or untracked paths whose keep/delete policy cannot be inferred safely.",
            "",
        ]
    )
    for key, title in (
        ("should_commit", "Should Commit"),
        ("should_gitignore", "Should Gitignore"),
        ("should_delete", "Should Delete"),
        ("pending_human", "Pending Human"),
    ):
        lines.extend([f"## {title}", ""])
        entries = grouped[key]
        if not entries:
            lines.append("- None")
            lines.append("")
            continue
        for entry in entries:
            safe_path = entry["path"].replace("\n", "\\n")
            lines.append(f"- `{entry['status']}` `{safe_path}`: {entry['reason']}")
        lines.append("")
    return "\n".join(lines)


def render_governance_spec(inventory: dict[str, Any], triage: dict[str, Any]) -> str:
    repo_rows = []
    for repo in inventory["repos"]:
        repo_rows.append(
            "| {name} | {mode} | {branch} | {tags} | {dirty} |".format(
                name=repo["name"],
                mode=repo["path_mode"],
                branch=repo["default_branch"] or "n/a",
                tags=len(repo["tags"]),
                dirty=repo["uncommitted_count"] if repo["uncommitted_count"] is not None else "n/a",
            )
        )
    return "\n".join(
        [
            "# GitHub Governance Spec",
            "",
            f"- Generated at: `{inventory['generated_at']}`",
            "- Canonical owner: `work/ai-da-guan-jia/references/github-governance-spec.md`",
            "- Scope: logical governance over `yuanli-os-claude / ai-da-guan-jia / yuanli-os-skills-pack / os-yuanli / yuanli-os-ops`.",
            "",
            "## Reality Check",
            "",
            "- This machine currently verifies only `yuanli-os-ops` and `yuanli-os-skills-pack` as active standalone clones.",
            "- `yuanli-os-claude` has a verified backup clone, but the active working directory is embedded inside the workspace repo.",
            "- `ai-da-guan-jia` and `os-yuanli` are present locally as workspace/skill copies, not as independent active clones.",
            f"- The active workspace root currently has `{inventory['workspace_repo']['uncommitted_count']}` uncommitted entries and no configured git remote.",
            "",
            "## Inventory Snapshot",
            "",
            "| Repo | Local Mode | Default Branch | Tag Count | Uncommitted |",
            "| --- | --- | --- | --- | --- |",
            *repo_rows,
            "",
            "## Naming Standard",
            "",
            "- Repository names stay English lowercase kebab-case only.",
            "- Use Chinese only for README headings, issue titles, and human-facing summaries.",
            "- Keep task keys in `tsk-YYYYMMDD-type-domain-slug-hash8` format.",
            "- Use `codex/<goal>` for agent-created branches; do not commit long-lived work directly onto ad hoc branch names.",
            "",
            "## Branch Strategy",
            "",
            "- Protect `main` on every GitHub repo once each logical repo has an active standalone clone.",
            "- Create short-lived implementation branches under `codex/`, `feat/`, `fix/`, or `docs/` depending on purpose.",
            "- Merge through PRs for shared repos; local-only repos should still keep branch names consistent with the same prefixes.",
            "- Disallow direct tagging or release creation from dirty working trees.",
            "",
            "## Versioning Policy",
            "",
            "- Use semantic version tags: `vMAJOR.MINOR.PATCH`.",
            "- Use milestone tags only as annotated checkpoints, for example `v2.0-baseline` after repo cleanup and branch protection are complete.",
            "- Do not mint tags on repos without a clean working tree and a verified remote.",
            "- Publish GitHub Releases only from semver tags; treat baseline tags as governance checkpoints, not product releases.",
            "",
            "## Recommended .gitignore Template",
            "",
            "```gitignore",
            "# macOS",
            ".DS_Store",
            "",
            "# Python",
            "__pycache__/",
            "*.pyc",
            ".pytest_cache/",
            ".venv*/",
            "",
            "# Node",
            "node_modules/",
            "",
            "# Browser automation",
            ".playwright-cli/",
            "",
            "# Local data / backups",
            "mac-max-backup-2026/",
            "dashboard/",
            "data/",
            "input/",
            "```",
            "",
            "## Repository Dependency DAG",
            "",
            "```mermaid",
            "graph TD",
            '  A["os-yuanli"] --> B["yuanli-os-claude"]',
            '  A["os-yuanli"] --> C["ai-da-guan-jia"]',
            '  A["os-yuanli"] --> D["yuanli-os-skills-pack"]',
            '  D["yuanli-os-skills-pack"] --> C["ai-da-guan-jia"]',
            '  B["yuanli-os-claude"] --> C["ai-da-guan-jia"]',
            '  C["ai-da-guan-jia"] --> E["yuanli-os-ops"]',
            '  D["yuanli-os-skills-pack"] --> E["yuanli-os-ops"]',
            "```",
            "",
            "Dependency meaning: operating and governance dependency inferred from local manifests, bootstrap contracts, and the repo map in `CLAUDE-INIT.md`, not necessarily direct code imports.",
            "",
            "## Current Governance Findings",
            "",
            "- No verified tags were found on the independently cloned repos.",
            "- Remote configuration is healthy only on `yuanli-os-ops`, `yuanli-os-skills-pack`, and the backup clone of `yuanli-os-claude`.",
            "- The current monorepo shape hides repo boundaries, which makes dirty counts and branch policy harder to reason about.",
            f"- Uncommitted triage summary: commit `{len(triage['grouped']['should_commit'])}`, gitignore `{len(triage['grouped']['should_gitignore'])}`, delete `{len(triage['grouped']['should_delete'])}`, pending human `{len(triage['grouped']['pending_human'])}`.",
            "",
            "## Next Actions",
            "",
            "- Clone or restore active standalone copies for `ai-da-guan-jia`, `os-yuanli`, and `yuanli-os-claude` so repo governance can be enforced per repo instead of per embedded directory.",
            "- Clean the current workspace until `main` is either intentionally dirty with a scoped branch or returned to a known baseline.",
            "- Add the shared `.gitignore` baseline before enabling branch protection.",
            "- After cleanup, create annotated `v2.0-baseline` tags on the repos that have verified remotes and clean trees.",
            "",
        ]
    )


def main() -> int:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    REFERENCES_DIR.mkdir(parents=True, exist_ok=True)
    report_date = datetime.now().strftime("%Y%m%d")

    inventory = collect_inventory()
    triage = triage_workspace()
    inventory["workspace_triage_summary"] = {
        key: len(value) for key, value in triage["grouped"].items()
    }

    dated_inventory_path = REPORTS_DIR / f"github-inventory-{report_date}.json"
    latest_inventory_path = REPORTS_DIR / "github-inventory.json"
    triage_path = REPORTS_DIR / "uncommitted-files-triage.md"
    handoff_path = REPORTS_DIR / "handoff.json"
    governance_spec_path = REFERENCES_DIR / "github-governance-spec.md"

    dated_inventory_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    latest_inventory_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    triage_path.write_text(render_triage_markdown(triage) + "\n", encoding="utf-8")
    governance_spec_path.write_text(render_governance_spec(inventory, triage) + "\n", encoding="utf-8")
    handoff = {
        "generated_at": inventory["generated_at"],
        "task": "TS-GH-01 GitHub治理盘点与规范化",
        "gained": [
            "Verified which logical repos have real standalone clones on this machine.",
            "Separated declared GitHub topology from current local filesystem reality.",
            "Produced a machine-readable inventory, governance spec, and uncommitted-file triage.",
        ],
        "wasted": [
            "Initial route output over-indexed on proposal flow instead of direct execution and had to be overridden by local evidence.",
            "The workspace monorepo shape makes per-repo dirty-state inspection noisier than necessary.",
        ],
        "next_iterate": [
            "Restore standalone clones for ai-da-guan-jia, os-yuanli, and yuanli-os-claude.",
            "Apply the shared .gitignore baseline and reduce pending-human backup/data paths.",
            "Only after cleanup, approve branch protection and baseline tags.",
        ],
        "outputs": {
            "inventory_dated": str(dated_inventory_path),
            "inventory_latest": str(latest_inventory_path),
            "triage": str(triage_path),
            "governance_spec": str(governance_spec_path),
        },
    }
    handoff_path.write_text(json.dumps(handoff, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"inventory_dated={dated_inventory_path}")
    print(f"inventory_latest={latest_inventory_path}")
    print(f"triage={triage_path}")
    print(f"governance_spec={governance_spec_path}")
    print(f"handoff={handoff_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
