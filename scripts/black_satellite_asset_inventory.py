from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "artifacts" / "black-satellite-asset-inventory"
SSH_SCRIPT = PROJECT_ROOT / "scripts" / "ssh_with_codex_identities.sh"
AI_DA_GUAN_JIA_SCRIPT = PROJECT_ROOT / "work" / "ai-da-guan-jia" / "scripts" / "ai_da_guan_jia.py"

DEFAULT_HOST_CANDIDATES = [
    "liming@MacBook-Pro-2.local",
    "liming@172.16.77.38",
    "liming@192.168.31.86",
]

GOVERNANCE_SKILLS = {
    "ai-da-guan-jia",
    "ai-da-guan-jia-prompt",
    "ai-metacognitive-core",
    "closure-evolution",
    "evidence-gate",
    "guide-benchmark-learning",
    "intent-grounding",
    "jiyao-youyao-haiyao",
    "jiyao-youyao-haiyao-zaiyao",
    "knowledge-orchestrator",
    "openai-docs",
    "routing-playbook",
    "self-evolution-max",
    "skill-pattern-publisher",
    "skill-router",
    "skill-trainer-recursive",
    "strategy-skill-template",
}

BROWSER_SKILLS = {
    "atlas",
    "opencli-platform-bridge",
    "playwright",
    "playwright-interactive",
    "screenshot",
}

FEISHU_SKILLS = {
    "business-structure-designer",
    "design-feishu-bitable-dashboards",
    "feishu-bitable-bridge",
    "feishu-dashboard-automator",
    "feishu-km",
    "feishu-open-platform",
    "feishu-reader",
    "github-feishu-sync",
}

CONTENT_SKILLS = {
    "get-biji-transcript",
    "notion-knowledge-capture",
    "notion-meeting-intelligence",
    "notion-research-documentation",
    "notion-spec-to-implementation",
    "wechat-article-writer",
    "wechat-draft-writer",
    "wechat-style-profiler",
    "wechat-title-generator",
    "wechat-topic-outline-planner",
    "xiaoshitou-dashijie",
}

AGENCY_SUPER_SKILLS = {
    "agency-design",
    "agency-engineering",
    "agency-marketing",
    "agency-project-mgmt",
    "agency-support",
    "agency-testing",
    "yuanli-knowledge",
}

HIGH_VALUE_SKILLS = {
    "ai-da-guan-jia",
    "black-satellite-multimodel-router",
    "feishu-bitable-bridge",
    "feishu-dashboard-automator",
    "knowledge-orchestrator",
    "opencli-platform-bridge",
    "playwright",
}

EXTERNAL_DEPENDENCY_SKILLS = {
    "feishu-bitable-bridge",
    "feishu-dashboard-automator",
    "feishu-km",
    "feishu-open-platform",
    "feishu-reader",
    "figma",
    "figma-implement-design",
    "gh-address-comments",
    "gh-fix-ci",
    "github-feishu-sync",
    "github-usage-expert",
    "linear",
    "notion-knowledge-capture",
    "notion-meeting-intelligence",
    "notion-research-documentation",
    "notion-spec-to-implementation",
    "opencli-platform-bridge",
}


def run_local(command: list[str], *, input_text: str | None = None) -> str:
    completed = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed ({completed.returncode}): {' '.join(command)}\n{completed.stderr.strip()}"
        )
    return completed.stdout


def run_remote_script(target_host: str, script: str) -> str:
    return run_local([str(SSH_SCRIPT), target_host, "zsh", "-s"], input_text=script)


def parse_key_value_output(text: str) -> dict[str, str]:
    payload: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        payload[key.strip()] = value.strip()
    return payload


def resolve_satellite_binding() -> dict[str, str]:
    raw = run_local(
        [
            sys.executable,
            str(AI_DA_GUAN_JIA_SCRIPT),
            "resolve-satellite",
            "--alias",
            "黑色",
        ]
    )
    return parse_key_value_output(raw)


def resolve_target_host(override: str | None = None) -> str:
    candidates = [override] if override else []
    candidates.extend([item for item in DEFAULT_HOST_CANDIDATES if item != override])
    for target in candidates:
        if not target:
            continue
        completed = subprocess.run(
            [str(SSH_SCRIPT), "-o", "BatchMode=yes", "-o", "ConnectTimeout=4", target, "exit"],
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode == 0:
            return target
    raise RuntimeError(f"Unable to reach black satellite via: {', '.join(candidates)}")


def remote_collection_script() -> str:
    return r"""
set -euo pipefail
python3 - <<'PY'
from __future__ import annotations

import json
import os
import platform
import subprocess
from pathlib import Path

def run_shell(command: str) -> tuple[int, str, str]:
    completed = subprocess.run(
        ["zsh", "-lc", command],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode, (completed.stdout or "").strip(), (completed.stderr or "").strip()


def repo_roots(documents_root: Path) -> list[str]:
    markers = {".git", "package.json", "pyproject.toml", "AGENTS.md"}
    results: set[Path] = set()
    for root, dirs, files in os.walk(documents_root):
        current = Path(root)
        depth = len(current.relative_to(documents_root).parts)
        if depth > 3:
            dirs[:] = []
            continue
        dir_names = set(dirs)
        file_names = set(files)
        if ".git" in dir_names:
            results.add(current)
        if markers.intersection(file_names):
            results.add(current)
    return sorted(str(path) for path in results)


home = Path.home()
codex_home = home / ".codex"
skills_root = codex_home / "skills"
automations_root = codex_home / "automations"
config_path = codex_home / "config.toml"
documents_root = home / "Documents"
primary_repo = documents_root / "codex-ai-gua-jia-01"
fallback_repo = documents_root / "RAY-CODEX" / "codex-ai-gua-jia-01"
repo_root = primary_repo if primary_repo.exists() else fallback_repo

skills = []
if skills_root.exists():
    for path in skills_root.rglob("SKILL.md"):
        if len(path.relative_to(skills_root).parts) <= 2:
            skills.append(path.parent.name)
skills = sorted(set(skills))
automations = sorted(str(path.relative_to(automations_root)) for path in automations_root.glob("*/automation.toml"))
vscode_extensions_root = home / ".vscode" / "extensions"
vscode_extensions = sorted(path.name for path in vscode_extensions_root.iterdir()) if vscode_extensions_root.exists() else []

config_raw = config_path.read_text(encoding="utf-8") if config_path.exists() else ""

code_path_rc, code_path, _ = run_shell("command -v code || true")
codex_path_rc, codex_path, _ = run_shell("command -v codex || true")
_, code_version, _ = run_shell("code --version | sed -n '1,2p'") if code_path else (0, "", "")
_, codex_version, _ = run_shell("codex --version | sed -n '1p'") if codex_path else (0, "", "")
_, sw_version, _ = run_shell("sw_vers -productVersion")

repo_scripts_root = repo_root / "scripts"
workflow_scripts_root = repo_root / "work" / "ai-da-guan-jia" / "scripts"
repo_scripts = sorted(path.name for path in repo_scripts_root.iterdir() if path.is_file()) if repo_scripts_root.exists() else []
workflow_scripts = sorted(path.name for path in workflow_scripts_root.iterdir() if path.is_file()) if workflow_scripts_root.exists() else []

payload = {
    "machine": {
        "hostname": platform.node(),
        "user": os.environ.get("USER", ""),
        "os_version": sw_version or platform.platform(),
        "home": str(home),
        "documents_root": str(documents_root),
        "apps": {
            "vscode_app_present": (Path("/Applications/Visual Studio Code.app").exists()),
            "codex_app_present": (Path("/Applications/Codex.app").exists()),
        },
        "cli": {
            "code_path": code_path if code_path_rc == 0 or code_path else "",
            "code_version": code_version.splitlines(),
            "codex_path": codex_path if codex_path_rc == 0 or codex_path else "",
            "codex_version": codex_version,
        },
    },
    "codex_home": {
        "path": str(codex_home),
        "config_exists": config_path.exists(),
        "config_path": str(config_path),
        "config_raw": config_raw,
        "memory_md_present": (codex_home / "memory.md").exists(),
        "memories_dir_present": (codex_home / "memories").exists(),
        "archived_sessions_present": (codex_home / "archived_sessions").exists(),
        "logs_sqlite_present": (codex_home / "logs_1.sqlite").exists(),
        "state_sqlite_present": (codex_home / "state_5.sqlite").exists(),
        "worktrees_present": (codex_home / "worktrees").exists(),
    },
    "skills": skills,
    "automations": automations,
    "vscode_extensions": vscode_extensions,
    "repos": repo_roots(documents_root),
    "repo_root": str(repo_root),
    "repo_scripts": repo_scripts,
    "workflow_scripts": workflow_scripts,
}
print(json.dumps(payload, ensure_ascii=False))
PY
"""


def categorize_skill(skill_name: str) -> str:
    if skill_name == "black-satellite-multimodel-router" or skill_name.startswith("black-satellite"):
        return "黑色卫星特化"
    if skill_name in GOVERNANCE_SKILLS:
        return "治理与路由"
    if skill_name in FEISHU_SKILLS:
        return "飞书与知识中台"
    if skill_name in BROWSER_SKILLS:
        return "浏览器与执行面"
    if skill_name.startswith("agency-") or skill_name in {
        "chatgpt-apps",
        "cloudflare-deploy",
        "doc",
        "figma",
        "figma-implement-design",
        "gh-address-comments",
        "gh-fix-ci",
        "github-skill-naming-audit",
        "github-usage-expert",
        "linear",
        "openai-docs",
        "pdf",
        "slides",
        "speech",
        "spreadsheet",
        "youquant-backtest",
        "youquant-backtest-automation",
    }:
        return "工程与 Agency"
    if skill_name in CONTENT_SKILLS or skill_name.startswith("wechat-") or skill_name.startswith("yuanli-"):
        return "内容与原力体系"
    return "工程与 Agency"


def derive_reuse_value(skill_name: str) -> str:
    if skill_name in HIGH_VALUE_SKILLS or skill_name in AGENCY_SUPER_SKILLS:
        return "高"
    if skill_name.startswith("agency-") and skill_name not in AGENCY_SUPER_SKILLS:
        return "低"
    return "中"


def derive_readiness(skill_name: str) -> str:
    if skill_name == "black-satellite-multimodel-router":
        return "可立即复用"
    if skill_name.startswith("agency-") and skill_name not in AGENCY_SUPER_SKILLS:
        return "暂不建议复用"
    if skill_name in EXTERNAL_DEPENDENCY_SKILLS:
        return "可条件复用"
    return "可立即复用"


def redact_config(value: Any, key_path: str = "") -> Any:
    lowered = key_path.lower()
    if isinstance(value, dict):
        return {k: redact_config(v, f"{key_path}.{k}" if key_path else k) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_config(item, key_path) for item in value]
    if isinstance(value, str) and lowered.endswith("_env_var"):
        return value
    if isinstance(value, str) and any(token in lowered for token in ("token", "secret", "password", "api_key")):
        return "<redacted>"
    return value


def parse_config_payload(raw_text: str) -> dict[str, Any]:
    if not raw_text or tomllib is None:
        return {}
    return redact_config(tomllib.loads(raw_text))


def best_use_case(skill_name: str, category: str) -> str:
    explicit = {
        "ai-da-guan-jia": "做黑色卫星机上的技能路由、治理判断、卫星派工和闭环收口。",
        "black-satellite-multimodel-router": "在黑色卫星机上切换多模型执行链，并保留黑色卫星专用控制语义。",
        "knowledge-orchestrator": "先问知识库再生成执行方案，适合复杂决策和资料密集任务。",
        "feishu-bitable-bridge": "把本地结构化结果安全写回飞书多维表，并保留预览与验真。",
        "feishu-dashboard-automator": "把飞书 dashboard 的 source view 和卡片清单标准化，适合看板型项目。",
        "opencli-platform-bridge": "优先用平台 CLI 代替浏览器点点点，降低成本并提高可复验性。",
        "playwright": "需要真实浏览器自动化、登录后取证或 UI 调试时使用。",
        "business-structure-designer": "把业务需求收敛成主表、阶段表、映射表等稳定结构。",
    }
    if skill_name in explicit:
        return explicit[skill_name]
    by_category = {
        "治理与路由": "作为上层判断或协同协议的一部分使用，适合复杂任务分流和方法学治理。",
        "飞书与知识中台": "连接飞书知识与数据底座，适合表结构、知识问答和看板呈现。",
        "浏览器与执行面": "需要真实界面交互、浏览器证据或页面自动化时使用。",
        "工程与 Agency": "作为通用工程执行或专业角色补位，适合具体实现、排查和交付。",
        "内容与原力体系": "承接原力内容生产、资料吸收和知识转写工作流。",
        "黑色卫星特化": "用于黑色卫星机的专用路由和多模型调度。",
    }
    return by_category[category]


def build_skill_inventory(skills: list[str]) -> dict[str, Any]:
    rows = []
    for name in skills:
        category = categorize_skill(name)
        rows.append(
            {
                "name": name,
                "category": category,
                "reuse_value": derive_reuse_value(name),
                "readiness": derive_readiness(name),
                "best_use_case": best_use_case(name, category),
            }
        )
    by_category = Counter(row["category"] for row in rows)
    by_readiness = Counter(row["readiness"] for row in rows)
    return {
        "count": len(rows),
        "by_category": dict(sorted(by_category.items())),
        "by_readiness": dict(sorted(by_readiness.items())),
        "skills": rows,
    }


def asset_status_for_mcp(server_name: str, server_payload: dict[str, Any]) -> str:
    if server_payload.get("enabled") is False:
        return "可条件复用"
    if "bearer_token_env_var" in server_payload or "env" in server_payload:
        return "可条件复用"
    return "可立即复用"


def build_core_assets_register(remote_payload: dict[str, Any]) -> dict[str, Any]:
    assets: list[dict[str, Any]] = []

    config = remote_payload["codex_home"].get("config", {})
    for name, payload in sorted(config.get("mcp_servers", {}).items()):
        dependency = []
        if payload.get("command"):
            dependency.append(f"command:{payload['command']}")
        if payload.get("url"):
            dependency.append(f"url:{payload['url']}")
        if payload.get("bearer_token_env_var"):
            dependency.append(f"env:{payload['bearer_token_env_var']}")
        if payload.get("env"):
            dependency.extend(f"env:{key}" for key in sorted(payload["env"].keys()))
        status = asset_status_for_mcp(name, payload)
        risk = "requires auth/env wiring" if status == "可条件复用" else ""
        if payload.get("enabled") is False:
            risk = "currently disabled in config"
        assets.append(
            {
                "asset_type": "mcp_config",
                "name": name,
                "path": remote_payload["codex_home"]["config_path"],
                "status": status,
                "how_to_reuse": f"作为 Codex MCP `{name}` 接入，给黑色卫星机补上下游能力。",
                "dependency": dependency,
                "risk_or_gap": risk,
            }
        )

    for automation in remote_payload.get("automations", []):
        assets.append(
            {
                "asset_type": "automation",
                "name": Path(automation).parent.name,
                "path": str(Path(remote_payload["codex_home"]["path"]) / "automations" / automation),
                "status": "present",
                "how_to_reuse": "作为定时任务入口，复用已有节奏化巡检和同步动作。",
                "dependency": ["Codex automations scheduler"],
                "risk_or_gap": "needs review of exact prompt/status before production reuse",
            }
        )

    repo_root = remote_payload.get("repo_root", "")
    for script_name in remote_payload.get("repo_scripts", []):
        script_path = str(Path(repo_root) / "scripts" / script_name)
        risk = ""
        if "black_satellite" in script_name:
            risk = ""
        assets.append(
            {
                "asset_type": "script_entrypoint",
                "name": script_name,
                "path": script_path,
                "status": "present",
                "how_to_reuse": "直接作为黑色卫星机上的本地入口脚本调用。",
                "dependency": ["repo workspace", "local shell"],
                "risk_or_gap": risk,
            }
        )

    for script_name in remote_payload.get("workflow_scripts", []):
        assets.append(
            {
                "asset_type": "workflow_entrypoint",
                "name": script_name,
                "path": str(Path(repo_root) / "work" / "ai-da-guan-jia" / "scripts" / script_name),
                "status": "present",
                "how_to_reuse": "通过 AI大管家工作流入口复用已有治理或运营 bundle。",
                "dependency": ["repo workspace", "Python runtime"],
                "risk_or_gap": "",
            }
        )

    for repo_path in remote_payload.get("repos", []):
        status = "present"
        risk = ""
        if repo_path.endswith("visual studio code-claude code-v1.1"):
            risk = "looks like experiment repo; review ownership before reuse"
        assets.append(
            {
                "asset_type": "repo_root",
                "name": Path(repo_path).name,
                "path": repo_path,
                "status": status,
                "how_to_reuse": "作为黑色卫星机上的现成工作区或实验仓库复用。",
                "dependency": ["repo checkout"],
                "risk_or_gap": risk,
            }
        )

    for extension in remote_payload.get("vscode_extensions", []):
        risk = ""
        if extension == "extensions.json":
            continue
        if "claude-code" in extension:
            risk = "explicit Codex VSCode extension still not evidenced"
        assets.append(
            {
                "asset_type": "vscode_extension",
                "name": extension,
                "path": str(Path(remote_payload["machine"]["home"]) / ".vscode" / "extensions" / extension),
                "status": "present",
                "how_to_reuse": "通过 VSCode 扩展层复用现成对话或协作能力。",
                "dependency": ["VSCode desktop"],
                "risk_or_gap": risk,
            }
        )

    counts = Counter(asset["asset_type"] for asset in assets)
    return {
        "count": len(assets),
        "by_asset_type": dict(sorted(counts.items())),
        "assets": assets,
    }


def build_machine_profile(binding: dict[str, str], target_host: str, remote_payload: dict[str, Any]) -> dict[str, Any]:
    config = remote_payload["codex_home"].get("config", {})
    mcp_servers = config.get("mcp_servers", {})
    return {
        "generated_at": iso_timestamp(),
        "satellite_alias": "黑色卫星机",
        "resolved_satellite_id": binding.get("resolved_satellite_id", ""),
        "resolved_source_id": binding.get("resolved_source_id", ""),
        "resolved_clone_id": binding.get("resolved_clone_id", ""),
        "dispatch_mode": binding.get("dispatch_mode", ""),
        "binding_status": binding.get("status", ""),
        "target_host": target_host,
        "machine": remote_payload["machine"],
        "codex_home": {
            "path": remote_payload["codex_home"]["path"],
            "config_exists": remote_payload["codex_home"]["config_exists"],
            "memory_md_present": remote_payload["codex_home"]["memory_md_present"],
            "memories_dir_present": remote_payload["codex_home"]["memories_dir_present"],
            "archived_sessions_present": remote_payload["codex_home"]["archived_sessions_present"],
            "logs_sqlite_present": remote_payload["codex_home"]["logs_sqlite_present"],
            "state_sqlite_present": remote_payload["codex_home"]["state_sqlite_present"],
            "worktrees_present": remote_payload["codex_home"]["worktrees_present"],
            "model": config.get("model", ""),
            "model_reasoning_effort": config.get("model_reasoning_effort", ""),
            "mcp_servers": sorted(mcp_servers.keys()),
            "automations_count": len(remote_payload.get("automations", [])),
            "skills_count": len(remote_payload.get("skills", [])),
        },
        "repo_root": remote_payload.get("repo_root", ""),
        "repo_count": len(remote_payload.get("repos", [])),
        "vscode_extensions_count": len([item for item in remote_payload.get("vscode_extensions", []) if item != "extensions.json"]),
    }


def build_reuse_shortlist(
    machine_profile: dict[str, Any],
    skill_inventory: dict[str, Any],
    core_assets_register: dict[str, Any],
) -> str:
    skills_lookup = {item["name"]: item for item in skill_inventory["skills"]}
    asset_lookup: dict[str, dict[str, Any]] = {}
    for asset in core_assets_register["assets"]:
        asset_lookup[asset["name"]] = asset

    shortlist_skills = [
        "ai-da-guan-jia",
        "black-satellite-multimodel-router",
        "knowledge-orchestrator",
        "feishu-bitable-bridge",
        "opencli-platform-bridge",
    ]
    shortlist_assets = [
        "black_satellite_cli_selfcheck.sh",
        "black_satellite_human_action.sh",
        "ai_da_guan_jia.py",
    ]

    lines = [
        "# 黑色卫星机 Codex 复用短名单",
        "",
        "## 总览",
        "",
        f"- 机器绑定：`黑色卫星机 -> {machine_profile['resolved_source_id']}`，当前状态 `{machine_profile['binding_status']}`",
        f"- 运行底座：`macOS {machine_profile['machine']['os_version']}`，模型 `{machine_profile['codex_home']['model']}`",
        f"- 资产规模：`{machine_profile['codex_home']['skills_count']}` 个 skill，`{machine_profile['codex_home']['automations_count']}` 个 automation，`{machine_profile['repo_count']}` 个相关 repo 根",
        f"- MCP：`{', '.join(machine_profile['codex_home']['mcp_servers'])}`",
        "",
        "## 最值得复用的 5 个 Skill",
        "",
    ]
    for index, name in enumerate(shortlist_skills, start=1):
        row = skills_lookup[name]
        lines.append(
            f"{index}. `{name}`：{row['category']}，{row['readiness']}。{row['best_use_case']}"
        )

    lines.extend(
        [
            "",
            "## 最值得复用的 3 个脚本 / 工作流",
            "",
        ]
    )
    for index, name in enumerate(shortlist_assets, start=1):
        asset = asset_lookup[name]
        lines.append(
            f"{index}. `{name}`：{asset['asset_type']}，状态 `{asset['status']}`。{asset['how_to_reuse']}"
        )

    lines.extend(
        [
            "",
            "## 2 个最该补强的治理缺口",
            "",
            "1. `Agency 重复入口仍然偏多`：7 个 super skills 和大量 legacy member skills 并存，默认入口需要继续收敛，否则路由容易分散。",
            "2. `可读型长期记忆仍偏弱`：`~/.codex/memory.md` 缺失，当前长期状态更多沉在 sqlite / logs 里，不利于人类快速接管与审计。",
            "",
            "## 复用建议",
            "",
            "- 先把 `ai-da-guan-jia + black-satellite-multimodel-router + black_satellite_cli_selfcheck.sh` 作为黑色卫星机基础操作链。",
            "- 涉及飞书写入和看板时优先走 `feishu-bitable-bridge`，而不是直接 UI 手动改。",
            "- 涉及平台抓取或轻交互时先试 `opencli-platform-bridge`，只有 CLI 不够时再切 `playwright`。",
        ]
    )
    return "\n".join(lines) + "\n"


def iso_timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inventory reusable Codex assets on the black satellite machine.")
    parser.add_argument("--host", help="Optional explicit SSH target like liming@172.16.77.38.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="Artifact root directory.")
    parser.add_argument("--json", action="store_true", help="Print the run manifest as JSON.")
    args = parser.parse_args(argv)

    binding = resolve_satellite_binding()
    target_host = resolve_target_host(args.host)
    remote_payload = json.loads(run_remote_script(target_host, remote_collection_script()))
    remote_payload["codex_home"]["config"] = parse_config_payload(remote_payload["codex_home"].get("config_raw", ""))

    output_root = Path(args.output_root).resolve()
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    machine_profile = build_machine_profile(binding, target_host, remote_payload)
    skill_inventory = build_skill_inventory(remote_payload["skills"])
    core_assets_register = build_core_assets_register(remote_payload)
    reuse_shortlist = build_reuse_shortlist(machine_profile, skill_inventory, core_assets_register)

    write_json(run_dir / "machine-profile.json", machine_profile)
    write_json(
        run_dir / "skills-inventory.json",
        {
            "generated_at": iso_timestamp(),
            "source_id": machine_profile["resolved_source_id"],
            **skill_inventory,
        },
    )
    write_json(
        run_dir / "core-assets-register.json",
        {
            "generated_at": iso_timestamp(),
            "source_id": machine_profile["resolved_source_id"],
            **core_assets_register,
        },
    )
    (run_dir / "reuse-shortlist.md").write_text(reuse_shortlist, encoding="utf-8")
    write_json(
        run_dir / "summary.json",
        {
            "generated_at": iso_timestamp(),
            "run_id": run_id,
            "run_dir": str(run_dir),
            "machine_profile": str(run_dir / "machine-profile.json"),
            "skills_inventory": str(run_dir / "skills-inventory.json"),
            "core_assets_register": str(run_dir / "core-assets-register.json"),
            "reuse_shortlist": str(run_dir / "reuse-shortlist.md"),
            "skills_count": skill_inventory["count"],
            "asset_count": core_assets_register["count"],
        },
    )
    (output_root / "latest-run.txt").write_text(run_id + "\n", encoding="utf-8")

    manifest = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "skills_count": skill_inventory["count"],
        "asset_count": core_assets_register["count"],
    }
    if args.json:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    else:
        print(f"run_id: {run_id}")
        print(f"run_dir: {run_dir}")
        print(f"skills_count: {skill_inventory['count']}")
        print(f"asset_count: {core_assets_register['count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
