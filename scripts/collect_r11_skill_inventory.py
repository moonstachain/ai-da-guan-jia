#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "r11-skill-panorama"
RAW_PATH = OUT_DIR / "skill_inventory_raw.json"
SUMMARY_PATH = OUT_DIR / "scan_summary.json"
OWNER = "moonstachain"


def run_json(cmd: list[str]) -> object:
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return json.loads(proc.stdout)


def list_repos() -> list[dict]:
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


def get_skill_paths(repo_full_name: str, branch: str) -> list[str]:
    tree = run_json(
        [
            "gh",
            "api",
            f"repos/{repo_full_name}/git/trees/{branch}?recursive=1",
        ]
    )
    return sorted(
        item["path"]
        for item in tree.get("tree", [])
        if item.get("path", "").endswith("SKILL.md")
    )


def skill_id_from_path(repo_name: str, path: str) -> str:
    parts = Path(path).parts
    return parts[-2] if len(parts) >= 2 else repo_name


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    repos = list_repos()
    inventory: list[dict] = []
    skipped_repos: list[dict] = []
    scanned_repos = 0

    for repo in repos:
        repo_full_name = repo["nameWithOwner"]
        repo_name = repo["name"]
        branch = (repo.get("defaultBranchRef") or {}).get("name") or ""
        if not branch:
            skipped_repos.append(
                {
                    "repo": repo_full_name,
                    "reason": "missing_default_branch",
                }
            )
            continue

        scanned_repos += 1
        try:
            skill_paths = get_skill_paths(repo_full_name, branch)
        except subprocess.CalledProcessError as exc:
            skipped_repos.append(
                {
                    "repo": repo_full_name,
                    "reason": "tree_api_failed",
                    "stderr": (exc.stderr or "").strip(),
                }
            )
            continue

        for path in skill_paths:
            inventory.append(
                {
                    "skill_id": skill_id_from_path(repo_name, path),
                    "repo": repo_name,
                    "path": path,
                    "source": "github",
                    "last_updated": repo["updatedAt"],
                    "trigger_count_30d": 0,
                    "trigger_count_30d_evidence": "no_openclaw_log_source_on_this_machine",
                    "trigger_count_30d_note": (
                        "Task spec path /home/gem/workspace/agent/logs is absent on this machine; "
                        "local codex-tui.log is empty, so counts remain 0 pending external log verification."
                    ),
                    "quadrant": None,
                    "action": None,
                }
            )

    inventory.sort(key=lambda item: (item["repo"], item["path"]))
    RAW_PATH.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n")

    repo_counter = Counter(item["repo"] for item in inventory)
    summary = {
        "owner": OWNER,
        "repos_seen": len(repos),
        "repos_scanned": scanned_repos,
        "repos_skipped": skipped_repos,
        "skill_entries": len(inventory),
        "repos_with_skills": sum(1 for count in repo_counter.values() if count > 0),
        "top_skill_repos": repo_counter.most_common(20),
        "log_evidence": {
            "openclaw_log_dir": "/home/gem/workspace/agent/logs",
            "openclaw_log_dir_exists": False,
            "local_codex_tui_log": "/Users/liming/.codex/log/codex-tui.log",
            "local_codex_tui_log_size_bytes": 0,
            "status": "trigger counts require external verification",
        },
        "outputs": {
            "raw_inventory": str(RAW_PATH),
        },
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
