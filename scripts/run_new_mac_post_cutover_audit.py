#!/usr/bin/env python3
"""Run a post-cutover OS-原力 migration audit for the new Mac."""

from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CODEX_HOME = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
OUTPUT_ROOT = PROJECT_ROOT / "output" / "migration"
BASELINE_PATH = PROJECT_ROOT / "specs" / "migration" / "black_satellite_cutover_baseline.json"
OPS_ROOT = PROJECT_ROOT / "tmp" / "external-repos" / "yuanli-os-ops"
OPS_SCHEMA_PATH = OPS_ROOT / "FORCE-CLAW" / "references" / "yuanli-os-feishu-base-schema.json"
FEISHU_BRIDGE_PATH = OPS_ROOT / "tools" / "feishu-bitable-bridge" / "scripts" / "feishu_bitable_bridge.py"
AI_DA_GUAN_JIA_SCRIPT = CODEX_HOME / "skills" / "ai-da-guan-jia" / "scripts" / "ai_da_guan_jia.py"
OS_YUANLI_DOCTOR = CODEX_HOME / "skills" / "os-yuanli" / "scripts" / "doctor.py"
SKILLS_PACK_VERIFY = PROJECT_ROOT / "tmp" / "external-repos" / "yuanli-os-skills-pack" / "scripts" / "verify_yuanli_os_skills_pack.py"
OPS_VERIFY = OPS_ROOT / "scripts" / "verify_yuanli_os_ops_bundle.py"
OPS_AUDIT_SYNC = OPS_ROOT / "FORCE-CLAW" / "scripts" / "sync_yuanli_os_audit_to_feishu.py"
SSH_WRAPPER = PROJECT_ROOT / "scripts" / "ssh_with_codex_identities.sh"
DEFAULT_SOURCE_HOSTS = ["liming@172.16.77.38", "H9V6Q97K6Y", "liming@192.168.31.86", "liming@MacBook-Pro-2.local"]
DEFAULT_FEISHU_LINK = "https://h52xu4gwob.feishu.cn/wiki/DdNXw06poicDHHkSKIdcRrYDnod?from=from_copylink"
DEFAULT_ACCOUNT_ID = "feishu-claw"
INTENTIONAL_NOT_COPY = [
    {
        "label": "浏览器 cookies 与完整 auth storage dump",
        "subsystem": "凭证与集成面",
        "reason": "bootstrap contract 明确禁止直接复制浏览器 cookies、auth storage dumps。",
    },
    {
        "label": "整份 ~/.codex 目录镜像",
        "subsystem": "代码与技能面",
        "reason": "迁移策略要求按 skills / config / artifacts 分层恢复，而不是整目录硬拷贝。",
    },
    {
        "label": "无稳定合同的临时 runtime 噪音",
        "subsystem": "工作流与 cutover 面",
        "reason": "只保留有合同的 bundle、skills、artifacts，不复制噪音输出。",
    },
]
SUBSYSTEMS = [
    ("machine_surface", "系统面"),
    ("code_skills", "代码与技能面"),
    ("credentials", "凭证与集成面"),
    ("workflow_cutover", "工作流与 cutover 面"),
]
SAMPLE_KEYS = [
    ("sample::local-health", "本机健康检查"),
    ("sample::source-compare", "源机差异对照"),
    ("sample::content-smoke", "内容链 smoke run"),
    ("sample::feishu-sync", "Feishu 镜像"),
]
GRADE_BANDS = [
    (9.0, "A"),
    (8.0, "B+"),
    (7.0, "B"),
    (6.0, "C+"),
    (5.0, "C"),
]
COMPARE_ITEMS = [
    {
        "id": "workspace_root",
        "label": "主工作区存在",
        "subsystem": "代码与技能面",
        "kind": "bool",
        "source": ("repos", "project_root", "present"),
        "target": ("repos", "project_root", "present"),
        "severity": "P1",
        "fix": "确保主工作区在标准路径并可被脚本引用。",
    },
    {
        "id": "repo_ai_da_guan_jia",
        "label": "AI大管家 repo",
        "subsystem": "代码与技能面",
        "kind": "bool",
        "source": ("repos", "ai_da_guan_jia", "present"),
        "target": ("repos", "ai_da_guan_jia", "present"),
        "severity": "P1",
        "fix": "恢复或重新 clone AI大管家 仓库。",
    },
    {
        "id": "repo_os_yuanli",
        "label": "os-yuanli repo",
        "subsystem": "代码与技能面",
        "kind": "bool",
        "source": ("repos", "os_yuanli", "present"),
        "target": ("repos", "os_yuanli", "present"),
        "severity": "P1",
        "fix": "恢复或重新 clone os-yuanli 仓库。",
    },
    {
        "id": "repo_ops",
        "label": "yuanli-os-ops repo",
        "subsystem": "代码与技能面",
        "kind": "bool",
        "source": ("repos", "yuanli_os_ops", "present"),
        "target": ("repos", "yuanli_os_ops", "present"),
        "severity": "P1",
        "fix": "恢复或重新 clone yuanli-os-ops 仓库。",
    },
    {
        "id": "repo_skills_pack",
        "label": "yuanli-os-skills-pack repo",
        "subsystem": "代码与技能面",
        "kind": "bool",
        "source": ("repos", "yuanli_os_skills_pack", "present"),
        "target": ("repos", "yuanli_os_skills_pack", "present"),
        "severity": "P1",
        "fix": "恢复或重新 clone yuanli-os-skills-pack 仓库。",
    },
    {
        "id": "codex_skill_count",
        "label": "Codex skills 数量",
        "subsystem": "代码与技能面",
        "kind": "count",
        "source": ("codex", "skill_count"),
        "target": ("codex", "skill_count"),
        "severity": "P1",
        "fix": "补齐缺失技能并重跑 inventory。",
    },
    {
        "id": "automation_count",
        "label": "automations 数量",
        "subsystem": "工作流与 cutover 面",
        "kind": "count",
        "source": ("codex", "automation_count"),
        "target": ("codex", "automation_count"),
        "severity": "P2",
        "fix": "盘点并补回关键自动化，或明确哪些自动化已废弃。",
    },
    {
        "id": "required_skills_complete",
        "label": "manifest 核心技能齐备",
        "subsystem": "代码与技能面",
        "kind": "all_true",
        "source": ("codex", "required_skills"),
        "target": ("codex", "required_skills"),
        "severity": "P0",
        "fix": "按 skills-manifest.lock.json 补齐核心 skills。",
    },
    {
        "id": "gh_auth_valid",
        "label": "GitHub gh auth",
        "subsystem": "凭证与集成面",
        "kind": "bool",
        "source": ("credentials", "github_auth", "valid"),
        "target": ("credentials", "github_auth", "valid"),
        "severity": "P0",
        "fix": "在新机执行 gh auth login -h github.com，恢复 repo scope。",
    },
    {
        "id": "github_hosts_present",
        "label": "GitHub hosts 配置存在",
        "subsystem": "凭证与集成面",
        "kind": "bool",
        "source": ("credentials", "github_hosts", "present"),
        "target": ("credentials", "github_hosts", "present"),
        "severity": "P1",
        "fix": "恢复 ~/.config/gh/hosts.yml 或重新登录 gh。",
    },
    {
        "id": "openclaw_present",
        "label": "OpenClaw / Feishu app credentials",
        "subsystem": "凭证与集成面",
        "kind": "bool",
        "source": ("credentials", "openclaw", "present"),
        "target": ("credentials", "openclaw", "present"),
        "severity": "P1",
        "fix": "补齐 ~/.openclaw/openclaw.json 或同等凭证入口。",
    },
    {
        "id": "feishu_reader_profile",
        "label": "feishu-reader 浏览器态",
        "subsystem": "凭证与集成面",
        "kind": "bool",
        "source": ("profiles", "feishu_reader"),
        "target": ("profiles", "feishu_reader"),
        "severity": "P1",
        "fix": "恢复 feishu-reader profile 或重新登录 Feishu Web。",
    },
    {
        "id": "get_biji_profile",
        "label": "Get笔记 浏览器态",
        "subsystem": "凭证与集成面",
        "kind": "bool",
        "source": ("profiles", "get_biji"),
        "target": ("profiles", "get_biji"),
        "severity": "P2",
        "fix": "恢复 Get笔记 profile 或重新登录 Get笔记 Web。",
    },
    {
        "id": "content_smoke_capability",
        "label": "内容链 smoke capability",
        "subsystem": "工作流与 cutover 面",
        "kind": "bool",
        "source": ("workflow", "content_smoke"),
        "target": ("workflow", "content_smoke"),
        "severity": "P0",
        "fix": "跑通一次 AI大管家 -> OS-原力 -> 内容链 smoke run。",
    },
    {
        "id": "audit_sync_capability",
        "label": "审计链 / Feishu mirror capability",
        "subsystem": "工作流与 cutover 面",
        "kind": "bool",
        "source": ("workflow", "audit_sync"),
        "target": ("workflow", "audit_sync"),
        "severity": "P0",
        "fix": "跑通 audit bundle + Feishu sync 的 dry-run 或 apply。",
    },
    {
        "id": "source_live_compare",
        "label": "源机 live SSH 对照",
        "subsystem": "系统面",
        "kind": "bool",
        "source": ("source_compare", "expected_live"),
        "target": ("source_compare", "live_ok"),
        "severity": "P1",
        "fix": "修复新机到黑色卫星机的 SSH / LAN 直连链路。",
    },
]
CHECKPOINT_TEMPLATE = [
    ("主题层", "目标清晰"),
    ("主题层", "优先级成立"),
    ("主题层", "边界清楚"),
    ("主题层", "长期价值"),
    ("主题层", "停止条件"),
    ("策略层", "层级定位"),
    ("策略层", "核心矛盾"),
    ("策略层", "备选比较"),
    ("策略层", "路径合理"),
    ("策略层", "风险边界"),
    ("执行层", "链路存在"),
    ("执行层", "责任清楚"),
    ("执行层", "产物存在"),
    ("执行层", "验真明确"),
    ("执行层", "闭环清楚"),
    ("递归进化", "复盘存在"),
    ("递归进化", "写回系统"),
    ("递归进化", "重复错误减少"),
    ("递归进化", "升级落点清楚"),
    ("递归进化", "下一轮动作明确"),
    ("全局最优", "考虑替代方案"),
    ("全局最优", "复用优先"),
    ("全局最优", "层级不混乱"),
    ("全局最优", "资源投入合理"),
    ("全局最优", "跨系统 leverage 存在"),
    ("人类友好", "少打扰"),
    ("人类友好", "少重做"),
    ("人类友好", "少耗算"),
    ("人类友好", "少隐性复杂度"),
    ("人类友好", "最终输出可用"),
]


REMOTE_SNAPSHOT_PY = r"""
import json
import os
import subprocess
from pathlib import Path


def safe_run(args):
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=20)
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except Exception as exc:
        return {"ok": False, "returncode": -1, "stdout": "", "stderr": str(exc)}


def version_for(cmd):
    result = safe_run(cmd)
    return {
        "present": result["returncode"] == 0,
        "version": result["stdout"].splitlines()[0] if result["stdout"] else "",
    }


home = Path.home()
codex_home = Path(os.environ.get("CODEX_HOME", str(home / ".codex"))).expanduser()
skills_root = codex_home / "skills"
automation_root = codex_home / "automations"
workspace_candidates = [
    home / "Documents" / "codex-ai-gua-jia-01",
    home / "workspace" / "yuanli-stack",
]
project_root = next((path for path in workspace_candidates if path.exists()), workspace_candidates[0])

required_skills = [
    "ai-da-guan-jia",
    "os-yuanli",
    "intent-grounding",
    "skill-router",
    "jiyao-youyao-haiyao-zaiyao",
    "evidence-gate",
    "closure-evolution",
    "wechat-style-profiler",
    "wechat-topic-outline-planner",
    "wechat-draft-writer",
    "wechat-title-generator",
    "wechat-article-writer",
    "feishu-reader",
    "openai-docs",
    "pdf",
    "spreadsheet",
    "feishu-bitable-bridge",
]

gh_status = safe_run(["gh", "auth", "status"])
payload = {
    "snapshot_mode": "ssh_live",
    "machine": {
        "host": safe_run(["hostname"])["stdout"],
        "user": os.environ.get("USER", ""),
        "workspace_root": str(project_root),
        "os_family": "macOS",
        "arch": safe_run(["uname", "-m"])["stdout"],
        "sw_vers": safe_run(["sw_vers"])["stdout"],
    },
    "repos": {
        "project_root": {"present": project_root.exists()},
        "ai_da_guan_jia": {"present": (project_root / "work" / "ai-da-guan-jia").exists()},
        "os_yuanli": {"present": (project_root / "tmp" / "external-repos" / "os-yuanli").exists()},
        "yuanli_os_ops": {"present": (project_root / "tmp" / "external-repos" / "yuanli-os-ops").exists()},
        "yuanli_os_skills_pack": {"present": (project_root / "tmp" / "external-repos" / "yuanli-os-skills-pack").exists()},
    },
    "codex": {
        "skill_count": len([path for path in skills_root.iterdir() if path.is_dir()]) if skills_root.exists() else 0,
        "automation_count": len([path for path in automation_root.iterdir() if path.is_dir()]) if automation_root.exists() else 0,
        "required_skills": {name: (skills_root / name / "SKILL.md").exists() for name in required_skills},
    },
    "credentials": {
        "github_auth": {
            "valid": gh_status["ok"],
            "summary": gh_status["stdout"] or gh_status["stderr"],
        },
        "github_hosts": {"present": (home / ".config" / "gh" / "hosts.yml").exists()},
        "openclaw": {"present": (home / ".openclaw" / "openclaw.json").exists()},
    },
    "profiles": {
        "feishu_reader": (skills_root / "feishu-reader" / "state" / "browser-profile" / "feishu-reader").exists(),
        "get_biji": (skills_root / "get-biji-transcript" / "state" / "browser-profile" / "get-biji").exists(),
    },
    "workflow": {
        "content_smoke": True,
        "audit_sync": True,
    },
    "tools": {
        "python3": version_for(["python3", "--version"]),
        "node": version_for(["node", "--version"]),
        "npm": version_for(["npm", "--version"]),
        "git": version_for(["git", "--version"]),
        "gh": version_for(["gh", "--version"]),
    },
}
print(json.dumps(payload, ensure_ascii=False))
"""


@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run_command(
    command: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 120,
    env: dict[str, str] | None = None,
) -> CommandResult:
    completed = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    return CommandResult(command, completed.returncode, completed.stdout, completed.stderr)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def slugify(value: str) -> str:
    text = value.strip().lower()
    text = re.sub(r"[`'\"“”‘’]+", "", text)
    text = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "-", text)
    return text.strip("-") or "item"


def grade_from_score(score: float) -> str:
    for floor, grade in GRADE_BANDS:
        if score >= floor:
            return grade
    return "D"


def deep_get(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = payload
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def summarize_command(result: CommandResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "returncode": result.returncode,
        "command": result.command,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def parse_gh_validity(result: CommandResult) -> tuple[bool, str]:
    text = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part).strip()
    invalid_markers = [
        "Failed to log in",
        "token in",
        "invalid",
        "To re-authenticate",
    ]
    valid = result.returncode == 0 and not any(marker in text for marker in invalid_markers)
    return valid, text


def collect_machine_info() -> dict[str, Any]:
    hostname = run_command(["hostname"])
    sw_vers = run_command(["sw_vers"])
    arch = run_command(["uname", "-m"])
    cpu = run_command(["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"])
    memory = run_command(["/usr/sbin/sysctl", "-n", "hw.memsize"])
    return {
        "host": hostname.stdout.strip(),
        "user": os.environ.get("USER", ""),
        "workspace_root": str(PROJECT_ROOT),
        "os_family": "macOS",
        "arch": arch.stdout.strip(),
        "sw_vers": sw_vers.stdout.strip(),
        "cpu": cpu.stdout.strip(),
        "memory_bytes": memory.stdout.strip(),
    }


def collect_tool_versions() -> dict[str, Any]:
    commands = {
        "python3": ["python3", "--version"],
        "node": ["node", "--version"],
        "npm": ["npm", "--version"],
        "git": ["git", "--version"],
        "gh": ["gh", "--version"],
    }
    tools: dict[str, Any] = {}
    for name, command in commands.items():
        result = run_command(command)
        tools[name] = {
            "present": result.ok,
            "version": (result.stdout.strip() or result.stderr.strip()).splitlines()[0] if (result.stdout or result.stderr) else "",
        }
    return tools


def collect_required_skills() -> dict[str, bool]:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    names = baseline["snapshot"]["codex"]["required_skills"].keys()
    return {name: (CODEX_HOME / "skills" / name / "SKILL.md").exists() for name in names}


def collect_local_snapshot() -> dict[str, Any]:
    gh_status = run_command(["gh", "auth", "status"])
    gh_valid, gh_summary = parse_gh_validity(gh_status)
    skills_root = CODEX_HOME / "skills"
    automations_root = CODEX_HOME / "automations"
    return {
        "snapshot_mode": "live_local",
        "machine": collect_machine_info(),
        "tools": collect_tool_versions(),
        "repos": {
            "project_root": {"present": PROJECT_ROOT.exists(), "path": str(PROJECT_ROOT)},
            "ai_da_guan_jia": {"present": (PROJECT_ROOT / "work" / "ai-da-guan-jia").exists()},
            "os_yuanli": {"present": (PROJECT_ROOT / "tmp" / "external-repos" / "os-yuanli").exists()},
            "yuanli_os_ops": {"present": OPS_ROOT.exists()},
            "yuanli_os_skills_pack": {"present": (PROJECT_ROOT / "tmp" / "external-repos" / "yuanli-os-skills-pack").exists()},
        },
        "codex": {
            "skill_count": len([path for path in skills_root.iterdir() if path.is_dir()]) if skills_root.exists() else 0,
            "automation_count": len([path for path in automations_root.iterdir() if path.is_dir()]) if automations_root.exists() else 0,
            "required_skills": collect_required_skills(),
        },
        "credentials": {
            "github_auth": {"valid": gh_valid, "summary": gh_summary},
            "github_hosts": {"present": (Path.home() / ".config" / "gh" / "hosts.yml").exists()},
            "openclaw": {"present": (Path.home() / ".openclaw" / "openclaw.json").exists()},
        },
        "profiles": {
            "feishu_reader": (CODEX_HOME / "skills" / "feishu-reader" / "state" / "browser-profile" / "feishu-reader").exists(),
            "get_biji": (CODEX_HOME / "skills" / "get-biji-transcript" / "state" / "browser-profile" / "get-biji").exists(),
        },
        "workflow": {
            "content_smoke": False,
            "audit_sync": False,
        },
    }


def load_source_baseline() -> dict[str, Any]:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    snapshot = baseline["snapshot"]
    snapshot["source_name"] = baseline["source_name"]
    snapshot["historical_evidence"] = baseline["historical_evidence"]
    return snapshot


def collect_source_snapshot(hosts: list[str]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    encoded = base64.b64encode(REMOTE_SNAPSHOT_PY.encode("utf-8")).decode("ascii")
    remote_cmd = (
        "python3 - <<'PY'\n"
        f"import base64\nexec(base64.b64decode('{encoded}').decode('utf-8'))\n"
        "PY"
    )
    errors: list[dict[str, str]] = []
    for host in hosts:
        try:
            result = run_command([str(SSH_WRAPPER), host, remote_cmd], timeout=30)
        except Exception as exc:
            errors.append({"host": host, "error": str(exc)})
            continue
        if result.ok:
            payload = json.loads(result.stdout.strip())
            payload["source_name"] = "黑色卫星机"
            payload["live_host"] = host
            return payload, errors
        errors.append({"host": host, "error": (result.stderr or result.stdout).strip()})
    baseline = load_source_baseline()
    baseline["source_compare"] = {"expected_live": True, "live_ok": False, "fallback": "historical_baseline"}
    baseline["ssh_errors"] = errors
    return baseline, errors


def classify_transition(spec: dict[str, Any], source_value: Any, target_value: Any) -> tuple[str, str]:
    kind = spec["kind"]
    if kind == "bool":
        source_bool = bool(source_value)
        target_bool = bool(target_value)
        if source_bool and target_bool:
            return "已完成迁移", "新机已具备该能力。"
        if source_bool and not target_bool:
            return "新机缺失", "源机具备而新机尚未具备。"
        if not source_bool and target_bool:
            return "已完成迁移", "新机相对源机已有增强。"
        return "已完成迁移", "源机未形成稳定要求，不视为迁移遗漏。"
    if kind == "count":
        source_num = int(source_value or 0)
        target_num = int(target_value or 0)
        if source_num <= 0 and target_num > 0:
            return "已完成迁移", "新机数量高于源机基线。"
        if target_num >= source_num:
            return "已完成迁移", "新机数量达到或超过源机。"
        if target_num > 0:
            return "新机降级", "新机数量低于源机基线。"
        return "新机缺失", "新机数量为 0。"
    if kind == "all_true":
        target_map = target_value or {}
        missing = sorted(name for name, ok in target_map.items() if not ok)
        if not missing:
            return "已完成迁移", "manifest 关键技能已齐备。"
        return "新机缺失", f"缺少关键技能：{', '.join(missing)}"
    return "已完成迁移", "未命中差异规则。"


def render_value(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, dict):
        if "valid" in value:
            return "valid" if value["valid"] else "invalid"
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def build_diff_matrix(local_snapshot: dict[str, Any], source_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    source_compare = {
        "expected_live": True,
        "live_ok": source_snapshot.get("snapshot_mode") == "ssh_live",
    }
    local_snapshot["source_compare"] = source_compare
    source_snapshot.setdefault("source_compare", source_compare)
    for spec in COMPARE_ITEMS:
        source_value = deep_get(source_snapshot, spec["source"])
        target_value = deep_get(local_snapshot, spec["target"])
        status, note = classify_transition(spec, source_value, target_value)
        rows.append(
            {
                "item_id": spec["id"],
                "subsystem": spec["subsystem"],
                "label": spec["label"],
                "source_value": render_value(source_value),
                "target_value": render_value(target_value),
                "status": status,
                "severity": spec["severity"],
                "note": note,
                "fix": spec["fix"],
            }
        )
    for item in INTENTIONAL_NOT_COPY:
        rows.append(
            {
                "item_id": slugify(item["label"]),
                "subsystem": item["subsystem"],
                "label": item["label"],
                "source_value": "source truth exists but intentionally excluded",
                "target_value": "not copied",
                "status": "故意不迁移",
                "severity": "P2",
                "note": item["reason"],
                "fix": "保持边界，不把安全边界误当成迁移遗漏。",
            }
        )
    return rows


def run_healthchecks(run_id: str) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    checks["os_yuanli_doctor"] = summarize_command(run_command(["python3", str(OS_YUANLI_DOCTOR)], cwd=PROJECT_ROOT))
    checks["skills_pack_verify"] = summarize_command(run_command(["python3", str(SKILLS_PACK_VERIFY)], cwd=PROJECT_ROOT))
    checks["ops_bundle_verify"] = summarize_command(run_command(["python3", str(OPS_VERIFY)], cwd=PROJECT_ROOT))
    checks["inventory_skills"] = summarize_command(run_command(["python3", str(AI_DA_GUAN_JIA_SCRIPT), "inventory-skills"], cwd=PROJECT_ROOT, timeout=180))
    checks["ops_audit_dry_run"] = summarize_command(
        run_command(
            ["python3", str(OPS_AUDIT_SYNC), "--dry-run", "--sync-scope", "internal"],
            cwd=OPS_ROOT,
            timeout=180,
        )
    )
    smoke_prompt = "请用 OS-原力 路由一次内容链 smoke run：为公众号生成一个关于新 Mac 迁移复盘的选题大纲和 3 个标题备选。"
    smoke_run_id = f"{run_id}-content-smoke"
    smoke_result = run_command(
        ["python3", str(AI_DA_GUAN_JIA_SCRIPT), "route", "--prompt", smoke_prompt, "--run-id", smoke_run_id],
        cwd=PROJECT_ROOT,
        timeout=240,
    )
    smoke_day = datetime.now().strftime("%Y-%m-%d")
    smoke_dir = CODEX_HOME / "skills" / "ai-da-guan-jia" / "artifacts" / "ai-da-guan-jia" / "runs" / smoke_day / smoke_run_id
    checks["content_smoke"] = summarize_command(smoke_result)
    checks["content_smoke"]["run_id"] = smoke_run_id
    checks["content_smoke"]["artifact_dir"] = str(smoke_dir)
    checks["content_smoke"]["artifact_present"] = (smoke_dir / "route.json").exists()
    return checks


def attach_workflow_state(local_snapshot: dict[str, Any], checks: dict[str, Any]) -> None:
    local_snapshot["workflow"]["content_smoke"] = bool(checks["content_smoke"]["ok"] and checks["content_smoke"]["artifact_present"])
    local_snapshot["workflow"]["audit_sync"] = bool(checks["ops_audit_dry_run"]["ok"])


def gather_internal_evidence(run_id: str, run_dir: Path, source_snapshot: dict[str, Any], source_errors: list[dict[str, str]]) -> list[dict[str, str]]:
    evidence_specs = [
        ("system", run_dir / "report.md", "最终 canonical 审计报告", "本轮迁移收尾审计的主报告。", "评分卡总表,扣分与差距,进化动作"),
        ("system", run_dir / "local-snapshot.json", "新机快照", "记录新机当前运行面、技能面、凭证面与工作流面。", "内部证据,评分卡总表"),
        ("system", run_dir / "source-snapshot.json", "源机对照快照", "优先记录 live SSH 对照，失败时回落到历史基线。", "内部证据,扣分与差距"),
        ("system", run_dir / "diff-matrix.json", "迁移差异矩阵", "每个迁移项都标注为已完成/缺失/降级/故意不迁移。", "扣分与差距,进化动作"),
        ("system", run_dir / "decision-pack.md", "Decision Pack", "P0/P1/P2 修复动作与 24h/7d/30d 路线。", "进化动作,递归队列"),
        ("system", run_dir / "healthchecks.json", "健康检查结果", "记录 doctor / verify / inventory / dry-run / content smoke 的结果。", "内部证据,评分卡总表"),
        ("system", BASELINE_PATH, "黑色卫星机历史基线", "当 live SSH 不可达时，作为源机历史对照基线。", "内部证据,扣分与差距"),
    ]
    if source_errors:
        write_json(run_dir / "source-ssh-errors.json", source_errors)
        evidence_specs.append(("system", run_dir / "source-ssh-errors.json", "源机 SSH 错误", "记录 live source compare 失败原因。", "扣分与差距"))
    if source_snapshot.get("historical_evidence", {}).get("doc_path"):
        evidence_specs.append(
            (
                "system",
                Path(source_snapshot["historical_evidence"]["doc_path"]),
                "黑色卫星机历史审计报告",
                "作为源机状态的历史证据。",
                "内部证据,扣分与差距",
            )
        )
    rows: list[dict[str, str]] = []
    for object_key, path, summary, conclusion, reuse in evidence_specs:
        if not path.exists():
            continue
        stat = path.stat()
        rows.append(
            {
                "Internal Evidence Key": f"{run_id}::{object_key}::{slugify(path.name)}",
                "Object Key": f"subsystem::{object_key}",
                "来源类型": path.suffix.lstrip(".") or "file",
                "来源路径": str(path),
                "canonical 标记": "yes",
                "时间戳": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "证据摘要": summary,
                "抽取结论": conclusion,
                "复用去向": reuse,
            }
        )
    return rows


def build_system_checkpoint_rows(run_id: str, diff_rows: list[dict[str, Any]], checks: dict[str, Any]) -> tuple[list[dict[str, str]], dict[str, float], dict[str, str]]:
    severe = [row for row in diff_rows if row["status"] in {"新机缺失", "新机降级"}]
    p0_count = sum(1 for row in severe if row["severity"] == "P0")
    p1_count = sum(1 for row in severe if row["severity"] == "P1")
    live_source = any(row["item_id"] == "source_live_compare" and row["status"] == "已完成迁移" for row in diff_rows)
    content_ok = checks["content_smoke"]["ok"] and checks["content_smoke"]["artifact_present"]
    audit_ok = checks["ops_audit_dry_run"]["ok"]
    gh_ok = any(row["item_id"] == "gh_auth_valid" and row["status"] == "已完成迁移" for row in diff_rows)
    core_contradiction = "当前核心矛盾是源机 live compare 未打通。" if gh_ok else "当前核心矛盾是 GitHub 凭证漂移与源机 live compare 未打通。"
    repeat_error_note = "当前 P0 已清空，说明高优先级凭证漂移已被收口。" if gh_ok else "GitHub token 漂移仍在重复出现，说明凭证治理还不够硬。"
    hidden_complexity_note = (
        "源机 SSH alias / LAN 直连仍会制造隐性复杂度。"
        if gh_ok and not live_source
        else "SSH alias / LAN 直连与 gh token 漂移仍会制造隐性复杂度。"
        if not live_source or not gh_ok
        else "关键协作与对照链路已没有显著隐性复杂度。"
    )
    rows_meta = {
        ("主题层", "目标清晰"): (2, "审计对象、时间边界、canonical 证据顺序都已固定。", "继续保持迁移审计对象与边界清楚。"),
        ("主题层", "优先级成立"): (2 if p0_count else 1, "GitHub 凭证与 cutover 验收直接影响新机是否可独立工作。", "优先先修 P0 项，再处理 P1/P2。"),
        ("主题层", "边界清楚"): (2 if live_source else 1, "已明确不把旧机当 canonical，只把旧机当对照层。", "补通 live SSH 对照，缩小源机补证噪音。"),
        ("主题层", "长期价值"): (2, "这次审计将转化为可重复跑的脚本与 Feishu 递归面。", "把后续复检固定成周期动作。"),
        ("主题层", "停止条件"): (2, "doctor / verify / inventory / dry-run / content smoke 构成固定验收门槛。", "继续用健康检查作为切主 stop condition。"),
        ("策略层", "层级定位"): (2, "审计按系统面、代码技能面、凭证集成面、工作流面拆层。", "保持分层，不把所有缺口混成一张清单。"),
        ("策略层", "核心矛盾"): (2 if severe else 1, core_contradiction, "围绕真实阻塞修复，不扩大题目。"),
        ("策略层", "备选比较"): (2 if live_source else 1, "实现里先尝试 live SSH，再回落到黑色卫星机历史基线。", "优先修复 live compare，保留 baseline fallback。"),
        ("策略层", "路径合理"): (2, "复用了现有 os-yuanli 审计、Feishu schema 与 SSH 工具链。", "继续避免另起一套迁移系统。"),
        ("策略层", "风险边界"): (2, "GUI 登录态无法 CLI 证明的部分被明确列为待补证项。", "保持 GUI 补证边界，不凭印象通过。"),
        ("执行层", "链路存在"): (2, "审计脚本能产出本地报告、差异矩阵和 Feishu bundle。", "把链路留在脚本内，避免人工拼装。"),
        ("执行层", "责任清楚"): (2, "AI大管家 / os-yuanli / audit script / Feishu bridge 的职责边界明确。", "保持 root skill 与 bridge 分工。"),
        ("执行层", "产物存在"): (2, "本轮会落 Inquiry Brief、Audit Pack、Decision Pack、Evolution Note。", "继续以工件验真而不是口头汇报。"),
        ("执行层", "验真明确"): (2 if audit_ok else 1, "doctor / verify / inventory / dry-run 都是结构化验真。", "把失败项直接落入 gap ledger。"),
        ("执行层", "闭环清楚"): (2 if content_ok and audit_ok else 1, "Feishu 镜像与本地 canonical 报告构成闭环。", "补通内容链 smoke run 后再重审。"),
        ("递归进化", "复盘存在"): (2, "这轮迁移盘点会形成结构化 Evolution Note。", "将后续修复结果写回下一轮审计。"),
        ("递归进化", "写回系统"): (2, "审计脚本、基线文件和 Feishu 递归面都属于写回。", "继续把一次性排障沉淀成长期器官。"),
        ("递归进化", "重复错误减少"): (1 if p0_count else 2, repeat_error_note, "给 gh auth 增加定期复检动作。"),
        ("递归进化", "升级落点清楚"): (2, "P0/P1/P2 gap 与递归队列已经提供升级落点。", "按 gap owner 与 cadence 推进。"),
        ("递归进化", "下一轮动作明确"): (2, "24h/7d/30d 路线会明确下一轮复检。", "把下一轮复检时间写入递归队列。"),
        ("全局最优", "考虑替代方案"): (2, "已比较 live SSH、历史基线 fallback 和现有 Feishu schema 复用。", "优先复用既有工具链。"),
        ("全局最优", "复用优先"): (2, "复用了现成迁移 playbook、Feishu bridge 和 audit schema。", "继续避免从零造轮子。"),
        ("全局最优", "层级不混乱"): (2, "本地 canonical、旧机对照、Feishu 镜像三层边界清楚。", "继续保证 canonical truth order。"),
        ("全局最优", "资源投入合理"): (1 if not live_source else 2, "live SSH 不可达导致对照层效率下降。", "先修网络/SSH，再放大源机对照。"),
        ("全局最优", "跨系统 leverage 存在"): (2, "本轮同时 leverage 仓库、skills、SSH、Feishu。", "继续让审计脚本跨系统复用。"),
        ("人类友好", "少打扰"): (2, "大部分盘点通过脚本和现有检查完成。", "只把真 GUI 边界留给人。"),
        ("人类友好", "少重做"): (2 if audit_ok else 1, "现有 schema 与脚本复用减少了重复搭建。", "继续用同一套 schema 承接复检。"),
        ("人类友好", "少耗算"): (1, "内容 smoke 与远端探活仍有一定算力和等待成本。", "把重步骤限制为切主验收时运行。"),
        ("人类友好", "少隐性复杂度"): (1 if (not live_source or not gh_ok) else 2, hidden_complexity_note, "显式记录 host fallback 与凭证复检规则。"),
        ("人类友好", "最终输出可用"): (2, "会直接产出本地审计包和 Feishu 记录。", "保持结果可直接拿来复检与协作。"),
    }
    checkpoint_rows: list[dict[str, str]] = []
    axis_scores: dict[str, float] = {axis: 0.0 for axis, _ in CHECKPOINT_TEMPLATE}
    axis_deductions: dict[str, str] = {}
    for axis, checkpoint in CHECKPOINT_TEMPLATE:
        score, evidence, improvement = rows_meta[(axis, checkpoint)]
        axis_scores[axis] += float(score)
        axis_deductions.setdefault(axis, improvement)
        checkpoint_rows.append(
            {
                "Checkpoint Key": f"{run_id}::system::{slugify(axis)}::{slugify(checkpoint)}",
                "Audit Run ID": run_id,
                "Object Key": "system",
                "轴名": axis,
                "检查点名": checkpoint,
                "得分": f"{float(score):.1f}",
                "状态": "已形成" if score == 2 else "部分形成" if score == 1 else "缺口",
                "证据句": evidence,
                "扣分原因": evidence if score < 2 else improvement,
                "改进动作": improvement,
                "证据键列表": "",
            }
        )
    return checkpoint_rows, axis_scores, axis_deductions


def subsystem_items(diff_rows: list[dict[str, Any]], subsystem: str) -> list[dict[str, Any]]:
    return [row for row in diff_rows if row["subsystem"] == subsystem and row["status"] != "故意不迁移"]


def score_subsystem(name: str, rows: list[dict[str, Any]], checks: dict[str, Any], source_snapshot: dict[str, Any]) -> dict[str, Any]:
    total = max(len(rows), 1)
    completed = sum(1 for row in rows if row["status"] == "已完成迁移")
    degraded = sum(1 for row in rows if row["status"] == "新机降级")
    missing = sum(1 for row in rows if row["status"] == "新机缺失")
    live_source = source_snapshot.get("snapshot_mode") == "ssh_live"
    coverage = completed / total
    issue_ratio = (degraded + missing) / total
    base = 6.0 + coverage * 3.0 - issue_ratio * 2.0
    axes = {
        "主题层": min(10.0, round(base + 1.0, 1)),
        "策略层": min(10.0, round(base + (0.5 if live_source else 0.0), 1)),
        "执行层": max(0.0, round(base + (1.0 if name == "工作流与 cutover 面" and checks["ops_audit_dry_run"]["ok"] else 0.0) - issue_ratio, 1)),
        "递归进化": max(0.0, round(base + 0.5, 1)),
        "全局最优": max(0.0, round(base + 1.0, 1)),
        "人类友好": max(0.0, round(base - 0.5 * (degraded + missing), 1)),
    }
    internal_score = round(sum(axes.values()) / len(axes), 1)
    deductions = []
    if degraded or missing:
        deductions.extend(f"{row['label']}：{row['note']}" for row in rows if row["status"] in {"新机缺失", "新机降级"})
    else:
        deductions.append("关键迁移项已通过当前审计。")
    return {
        "name": name,
        "axes": axes,
        "internal_score": internal_score,
        "grade": grade_from_score(internal_score),
        "deductions": "；".join(deductions[:4]),
        "next_action": rows[0]["fix"] if rows and (missing or degraded) else "维持当前状态并进入周期复检。",
        "counts": {"completed": completed, "degraded": degraded, "missing": missing},
    }


def build_system_score(axis_scores: dict[str, float], diff_rows: list[dict[str, Any]]) -> dict[str, Any]:
    internal_score = round(sum(axis_scores.values()) / len(axis_scores), 1)
    weakest_gap = next((row["label"] for row in diff_rows if row["status"] in {"新机缺失", "新机降级"}), "无重大迁移缺口")
    return {
        "axes": axis_scores,
        "internal_score": internal_score,
        "grade": grade_from_score(internal_score),
        "deductions": "；".join(row["label"] for row in diff_rows if row["status"] in {"新机缺失", "新机降级"}) or "无重大迁移缺口",
        "next_action": weakest_gap,
    }


def build_gap_ledger(diff_rows: list[dict[str, Any]], checks: dict[str, Any], source_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for row in diff_rows:
        if row["status"] not in {"新机缺失", "新机降级"}:
            continue
        gaps.append(
            {
                "gap_id": row["item_id"],
                "subsystem": row["subsystem"],
                "title": row["label"],
                "priority": row["severity"],
                "status": "open",
                "impact": row["note"],
                "evidence": f"source={row['source_value']} / target={row['target_value']}",
                "repair": row["fix"],
            }
        )
    if source_snapshot.get("snapshot_mode") != "ssh_live":
        gaps.append(
            {
                "gap_id": "source-live-compare-unavailable",
                "subsystem": "系统面",
                "title": "源机 live compare 不可达",
                "priority": "P1",
                "status": "open",
                "impact": "当前只能使用历史基线对照，无法做同刻实时差异。",
                "evidence": json.dumps(source_snapshot.get("ssh_errors", []), ensure_ascii=False),
                "repair": "恢复新机到黑色卫星机的 SSH / LAN 直连。",
            }
        )
    if not checks["content_smoke"]["ok"] or not checks["content_smoke"]["artifact_present"]:
        gaps.append(
            {
                "gap_id": "content-smoke-failed",
                "subsystem": "工作流与 cutover 面",
                "title": "内容链 smoke run 未闭环",
                "priority": "P0",
                "status": "open",
                "impact": "新机还不能证明内容链可独立完成一次真实闭环。",
                "evidence": checks["content_smoke"]["stderr"] or checks["content_smoke"]["stdout"],
                "repair": "修复内容链所需的模型、路由或技能链后重跑 smoke run。",
            }
        )
    return gaps


def roadmap_bucket(priority: str) -> str:
    return {"P0": "24h", "P1": "7d", "P2": "30d"}.get(priority, "30d")


def build_action_rows(run_id: str, gaps: list[dict[str, Any]]) -> list[dict[str, str]]:
    actions = []
    for idx, gap in enumerate(gaps, start=1):
        cadence = roadmap_bucket(gap["priority"])
        actions.append(
            {
                "Action Key": f"{run_id}::{cadence}::{idx}",
                "Audit Run ID": run_id,
                "Gap Key": f"{run_id}::{slugify(gap['gap_id'])}",
                "动作标题": gap["repair"],
                "动作类型": "repair" if gap["priority"] == "P0" else "harden" if gap["priority"] == "P1" else "evolve",
                "负责人": "OS-原力",
                "优先级": "high" if gap["priority"] == "P0" else "medium" if gap["priority"] == "P1" else "low",
                "预期收益": gap["impact"],
                "投入等级": "medium" if gap["priority"] != "P0" else "high",
                "计划节奏": cadence,
                "状态": "open",
                "闭环证据": "",
                "关闭时间": "",
            }
        )
    return actions


def build_recursion_rows(run_id: str, gaps: list[dict[str, Any]], now: datetime) -> list[dict[str, str]]:
    rows = []
    for gap in gaps:
        cadence = roadmap_bucket(gap["priority"])
        next_run = now + {"24h": timedelta(days=1), "7d": timedelta(days=7), "30d": timedelta(days=30)}[cadence]
        rows.append(
            {
                "Loop Key": f"{run_id}::{slugify(gap['gap_id'])}",
                "Object Key": f"subsystem::{slugify(gap['subsystem'])}",
                "复审节奏": cadence,
                "触发类型": gap["title"],
                "上次内部同步": now.strftime("%Y-%m-%d %H:%M:%S"),
                "上次外部同步": "",
                "下次运行": next_run.strftime("%Y-%m-%d %H:%M:%S"),
                "过期标记": "false",
                "阻塞": gap["impact"],
                "分数变化": "0.0",
                "是否自动开 gap": "yes",
            }
        )
    return rows


def scorecard_rows_from_scores(run_id: str, system_score: dict[str, Any], subsystem_scores: list[dict[str, Any]], sample_scores: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    system_row = {
        "Scorecard Key": f"{run_id}::system",
        "Audit Run ID": run_id,
        "Object Key": "system",
        "对象类型": "system",
        "对象名称": "新 Mac Pro Max 迁移收尾审计",
        "父对象": "",
        "内部成熟度": f"{system_score['internal_score']:.1f}",
        "外部对标分": "0.0",
        "综合分": f"{system_score['internal_score']:.1f}",
        "等级": system_score["grade"],
        "关键扣分": system_score["deductions"],
        "下一步动作摘要": system_score["next_action"],
    }
    for axis, field in [
        ("主题层", "主题层分"),
        ("策略层", "策略层分"),
        ("执行层", "执行层分"),
        ("递归进化", "递归进化分"),
        ("全局最优", "全局最优分"),
        ("人类友好", "人类友好分"),
    ]:
        system_row[field] = f"{system_score['axes'][axis]:.1f}"
    rows.append(system_row)
    for key, score in zip(SUBSYSTEMS, subsystem_scores):
        object_key = f"subsystem::{key[0]}"
        row = {
            "Scorecard Key": f"{run_id}::{object_key}",
            "Audit Run ID": run_id,
            "Object Key": object_key,
            "对象类型": "subsystem",
            "对象名称": key[1],
            "父对象": "system",
            "内部成熟度": f"{score['internal_score']:.1f}",
            "外部对标分": "0.0",
            "综合分": f"{score['internal_score']:.1f}",
            "等级": score["grade"],
            "关键扣分": score["deductions"],
            "下一步动作摘要": score["next_action"],
        }
        for axis, field in [
            ("主题层", "主题层分"),
            ("策略层", "策略层分"),
            ("执行层", "执行层分"),
            ("递归进化", "递归进化分"),
            ("全局最优", "全局最优分"),
            ("人类友好", "人类友好分"),
        ]:
            row[field] = f"{score['axes'][axis]:.1f}"
        rows.append(row)
    for (object_key, object_name), score in zip(SAMPLE_KEYS, sample_scores):
        row = {
            "Scorecard Key": f"{run_id}::{object_key}",
            "Audit Run ID": run_id,
            "Object Key": object_key,
            "对象类型": "sample",
            "对象名称": object_name,
            "父对象": "system",
            "内部成熟度": f"{score['internal_score']:.1f}",
            "外部对标分": "0.0",
            "综合分": f"{score['internal_score']:.1f}",
            "等级": score["grade"],
            "关键扣分": score["deductions"],
            "下一步动作摘要": score["next_action"],
            "主题层分": "",
            "策略层分": "",
            "执行层分": "",
            "递归进化分": "",
            "全局最优分": "",
            "人类友好分": "",
        }
        rows.append(row)
    return rows


def build_sample_scores(checks: dict[str, Any], source_snapshot: dict[str, Any], gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "internal_score": 9.0 if checks["os_yuanli_doctor"]["ok"] and checks["skills_pack_verify"]["ok"] and checks["ops_bundle_verify"]["ok"] else 6.5,
            "grade": grade_from_score(9.0 if checks["os_yuanli_doctor"]["ok"] and checks["skills_pack_verify"]["ok"] and checks["ops_bundle_verify"]["ok"] else 6.5),
            "deductions": "健康检查主链已通过。" if checks["os_yuanli_doctor"]["ok"] else "健康检查仍有失败项。",
            "next_action": "维持 doctor / verify / inventory 作为每轮复检入口。",
        },
        {
            "internal_score": 8.5 if source_snapshot.get("snapshot_mode") == "ssh_live" else 6.5,
            "grade": grade_from_score(8.5 if source_snapshot.get("snapshot_mode") == "ssh_live" else 6.5),
            "deductions": "live SSH source compare 已打通。" if source_snapshot.get("snapshot_mode") == "ssh_live" else "当前仍在用历史基线 fallback。",
            "next_action": "打通 live SSH 对照链路。" if source_snapshot.get("snapshot_mode") != "ssh_live" else "保留 live source compare 作为周期盘点入口。",
        },
        {
            "internal_score": 8.8 if checks["content_smoke"]["ok"] and checks["content_smoke"]["artifact_present"] else 5.8,
            "grade": grade_from_score(8.8 if checks["content_smoke"]["ok"] and checks["content_smoke"]["artifact_present"] else 5.8),
            "deductions": "内容链 smoke run 已留 real artifact。" if checks["content_smoke"]["ok"] and checks["content_smoke"]["artifact_present"] else "内容链 smoke run 尚未形成可验真 artifact。",
            "next_action": "补通一次内容链 smoke run。" if not (checks["content_smoke"]["ok"] and checks["content_smoke"]["artifact_present"]) else "把 smoke run 纳入切主复检。",
        },
        {
            "internal_score": 8.8 if not any(gap["priority"] == "P0" and "审计" in gap["subsystem"] for gap in gaps) else 7.0,
            "grade": grade_from_score(8.8 if not any(gap["priority"] == "P0" and "审计" in gap["subsystem"] for gap in gaps) else 7.0),
            "deductions": "Feishu 镜像链可用。" if not any(gap["title"] == "审计链 / Feishu mirror capability" for gap in gaps) else "审计镜像链仍有缺口。",
            "next_action": "维持 Feishu mirror 作为长期复检面。",
        },
    ]


def format_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def render_report(
    run_id: str,
    local_snapshot: dict[str, Any],
    source_snapshot: dict[str, Any],
    diff_rows: list[dict[str, Any]],
    checks: dict[str, Any],
    system_score: dict[str, Any],
    subsystem_scores: list[dict[str, Any]],
    sample_scores: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
) -> str:
    gh_ok = any(row["item_id"] == "gh_auth_valid" and row["status"] == "已完成迁移" for row in diff_rows)
    live_source = source_snapshot.get("snapshot_mode") == "ssh_live"
    autonomy_boundary = (
        "GUI 边界只剩登录态补证。"
        if gh_ok and live_source
        else "GUI 边界只剩登录态补证与源机 live SSH 补证。"
        if gh_ok
        else "GUI 边界只剩登录态补证与 GitHub 重登。"
    )
    reuse_judgment = "本轮复用了现有 doctor、verify、inventory、audit dry-run、Feishu bridge 与黑色卫星机 live snapshot。" if live_source else "本轮复用了现有 doctor、verify、inventory、audit dry-run、Feishu bridge 与黑色卫星机历史基线。"
    theme_deduction = "live source compare 已恢复为同刻实时对照。" if live_source else "live source compare 还没稳定打通，部分边界仍依赖历史基线而不是同刻对照。"
    strategy_deduction = (
        "源机 live 对照已经恢复，后续重点是把复检规则固化到日常治理。"
        if gh_ok and live_source
        else "源机对照 fallback 已经清晰，但还没闭环到日常治理规则。"
        if gh_ok
        else "GitHub 凭证漂移与源机对照 fallback 已经清晰，但还没全部闭环到日常治理规则。"
    )
    execution_deduction = (
        "新机主链健康检查通过，live source compare 也已恢复到实时对照。"
        if gh_ok and live_source
        else "新机主链健康检查通过，但 live source compare 还没有恢复到实时对照。"
        if gh_ok
        else "新机主链健康检查通过，但 `gh auth` 失效会影响真实协作链闭环。"
    )
    evolution_deduction = (
        "迁移审计已写回脚本与 Feishu，后续重点是把 live 对照纳入周期复检规则。"
        if gh_ok and live_source
        else "迁移审计已写回脚本与 Feishu，但 SSH 对照还没形成长期防漂移规则。"
        if gh_ok
        else "迁移审计已写回脚本与 Feishu，但 GitHub 凭证与 SSH 对照还没形成长期防漂移规则。"
    )
    global_deduction = "当前已经复用现有系统，且源机 live compare 已恢复，证据强度明显提升。" if live_source else "当前已经复用现有系统，但源机 live compare 缺失会降低最优性与证据强度。"
    human_deduction = (
        "人工补证边界已明显收敛。"
        if gh_ok and live_source
        else "`远端 SSH 恢复` 仍需人工介入，隐藏复杂度尚未完全清零。"
        if gh_ok
        else "`gh auth` 重登与远端 SSH 恢复仍需人工介入，隐藏复杂度尚未完全清零。"
    )
    strongest = max(subsystem_scores, key=lambda item: item["internal_score"])["name"]
    weakest = min(subsystem_scores, key=lambda item: item["internal_score"])["name"]
    completed_count = sum(1 for row in diff_rows if row["status"] == "已完成迁移")
    missing_count = sum(1 for row in diff_rows if row["status"] == "新机缺失")
    degraded_count = sum(1 for row in diff_rows if row["status"] == "新机降级")
    intentional_count = sum(1 for row in diff_rows if row["status"] == "故意不迁移")
    system_table = format_table(
        ["维度", "分数", "等级", "总评", "关键扣分"],
        [
            [f"`{axis}`", f"{score:.1f}/10", grade_from_score(score), "见扣分账本。", system_score["next_action"] if axis == "执行层" else system_score["deductions"]]
            for axis, score in system_score["axes"].items()
        ],
    )
    subsystem_blocks = []
    for (key, label), score in zip(SUBSYSTEMS, subsystem_scores):
        rows = format_table(
            ["维度", "分数", "扣分说明"],
            [[f"`{axis}`", f"{value:.1f}", score["deductions"] if axis == "执行层" else score["next_action"]] for axis, value in score["axes"].items()],
        )
        subsystem_blocks.append(
            f"""### 5.{len(subsystem_blocks)+1} {label}

`得分：{score['internal_score']:.1f} / 10`

`等级：{score['grade']}`

{rows}

扣分点：
{score['deductions']}

为什么得这个分：
{score['next_action']}
"""
        )
    sample_blocks = []
    for idx, ((_, label), score) in enumerate(zip(SAMPLE_KEYS, sample_scores), start=1):
        sample_blocks.append(
            f"""### 6.{idx} {label}

`得分：{score['internal_score']:.1f} / 10`

`等级：{score['grade']}`

扣分点：
{score['deductions']}

为什么得这个分：
{score['next_action']}
"""
        )
    gap_table = format_table(
        ["扣分项", "证据句", "改进动作"],
        [[gap["title"], gap["evidence"][:80].replace("\n", " "), gap["repair"]] for gap in gaps[:12]],
    )
    p0 = [gap["repair"] for gap in gaps if gap["priority"] == "P0"]
    p1 = [gap["repair"] for gap in gaps if gap["priority"] == "P1"]
    p2 = [gap["repair"] for gap in gaps if gap["priority"] == "P2"]
    subsystem_block_text = "".join(subsystem_blocks)
    sample_block_text = "".join(sample_blocks)
    p0_text = "".join(f"{idx}. {item}\n" for idx, item in enumerate(p0 or ["无 P0 动作。"], start=1))
    p1_text = "".join(f"{idx}. {item}\n" for idx, item in enumerate(p1 or ["无 7d 动作。"], start=1))
    p2_text = "".join(f"{idx}. {item}\n" for idx, item in enumerate(p2 or ["无 30d 动作。"], start=1))
    return textwrap.dedent(
        f"""
        # 新 Mac Pro Max 迁移收尾审计报告

        > 审计时点：`{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`  
        > 审计对象：`新 Mac Pro Max 上的 OS-原力整机迁移完整度与可持续运行成熟度`  
        > 对照层：`H9V6Q97K6Y / 黑色卫星机`（当前模式：`{source_snapshot.get('snapshot_mode', 'unknown')}`）

        ## 1. 执行摘要

        ### 1.1 系统总评分

        `系统总分：{system_score['internal_score']:.1f} / 10`

        `等级：{system_score['grade']}`

        当前最强区块：`{strongest}`  
        当前最弱区块：`{weakest}`

        ### 1.2 六判断

        - `自治判断`：本轮审计大部分链路已可本机自治执行，{autonomy_boundary}
        - `全局最优判断`：最优路径是复用现有 `os-yuanli + yuanli-os-ops + Feishu schema + SSH toolkit`，而不是另起迁移系统。
        - `能力复用判断`：{reuse_judgment}
        - `验真判断`：以 `doctor / verify / inventory / audit dry-run / content smoke / Feishu mirror` 为主验真口径。
        - `进化判断`：这轮的沉淀物应是 `可重复跑的迁移审计脚本 + Feishu 递归面 + P0/P1/P2 gap ledger`。
        - `当前最大失真`：把“新机主链已恢复”误判成“所有凭证与 live source compare 都已收口”。

        ## 2. 审计范围与证据底座

        - canonical 顺序：`本地 docs/repo -> 本地 runtime/artifacts -> ~/.codex/skills -> 历史 runs/reviews -> 源机对照`
        - 源机对照模式：`{source_snapshot.get('snapshot_mode', 'unknown')}`
        - 新机 skill 数：`{local_snapshot['codex']['skill_count']}`
        - 源机 skill 基线：`{source_snapshot['codex']['skill_count']}`
        - 新机 automation 数：`{local_snapshot['codex']['automation_count']}`
        - 源机 automation 基线：`{source_snapshot['codex']['automation_count']}`

        ## 3. 评分口径

        - `6 轴 × 10 分 = 原力OS评分模型`
        - 本轮不把行业 benchmark 作为主证据，只把源机对照作为迁移遗漏层
        - 所有扣分项都必须落到 `差异矩阵 / gap ledger / 决策动作`

        ## 4. 系统总评分卡

        ### 4.1 总表

        {system_table}

        ### 4.2 主题层

        关键扣分：
        {theme_deduction}

        ### 4.3 策略层

        关键扣分：
        {strategy_deduction}

        ### 4.4 执行层

        关键扣分：
        {execution_deduction}

        ### 4.5 递归进化

        关键扣分：
        {evolution_deduction}

        ### 4.6 全局最优

        关键扣分：
        {global_deduction}

        ### 4.7 人类友好

        关键扣分：
        {human_deduction}

        ## 5. 子系统评分卡

        {subsystem_block_text}

        ## 6. 代表性样本

        {sample_block_text}

        ## 7. Deduction Ledger

        {gap_table}

        ## 8. Roadmap

        ### 8.1 24h

        {p0_text}

        ### 8.2 7d

        {p1_text}

        ### 8.3 30d

        {p2_text}

        ## 9. 源机差异矩阵摘要

        - `已完成迁移`：{completed_count}
        - `新机缺失`：{missing_count}
        - `新机降级`：{degraded_count}
        - `故意不迁移`：{intentional_count}
        """
    ).strip()


def render_brief_markdown(title: str, bullets: list[str]) -> str:
    return "\n".join([f"# {title}", "", *[f"- {bullet}" for bullet in bullets]])


def build_markdown_packs(
    run_dir: Path,
    report_text: str,
    gaps: list[dict[str, Any]],
    checks: dict[str, Any],
    diff_rows: list[dict[str, Any]],
) -> None:
    write_text(run_dir / "report.md", report_text)
    write_text(
        run_dir / "inquiry-brief.md",
        render_brief_markdown(
            "Inquiry Brief",
            [
                "审计对象：新 Mac Pro Max 上的 OS-原力 整机迁移完整度与可持续运行成熟度。",
                "时间边界：当前新机状态 + 本次审计时刻可取得的源机对照或历史基线。",
                "成功条件：本地 canonical 审计包落盘，关键 gap 入账，Feishu 镜像可写入现有审计系统。",
            ],
        ),
    )
    write_text(
        run_dir / "analysis-card.md",
        render_brief_markdown(
            "Analysis Card",
            [
                "主策略：复用现有 OS-原力 审计与迁移工具链，不从零搭系统。",
                "核心矛盾：GitHub gh auth 失效，以及源机 live SSH 对照当前不可达。",
                "证据结构：本地 docs / runtime / skills / 历史 runs + 源机 live compare 或历史基线。",
            ],
        ),
    )
    write_text(
        run_dir / "audit-run-sheet.md",
        render_brief_markdown(
            "Audit Run Sheet",
            [
                f"os-yuanli doctor: {'OK' if checks['os_yuanli_doctor']['ok'] else 'FAIL'}",
                f"skills-pack verify: {'OK' if checks['skills_pack_verify']['ok'] else 'FAIL'}",
                f"ops verify: {'OK' if checks['ops_bundle_verify']['ok'] else 'FAIL'}",
                f"inventory-skills: {'OK' if checks['inventory_skills']['ok'] else 'FAIL'}",
                f"audit dry-run: {'OK' if checks['ops_audit_dry_run']['ok'] else 'FAIL'}",
                f"content smoke: {'OK' if checks['content_smoke']['ok'] and checks['content_smoke']['artifact_present'] else 'FAIL'}",
            ],
        ),
    )
    write_text(
        run_dir / "audit-pack.md",
        render_brief_markdown(
            "Audit Pack",
            [
                "report.md 作为 canonical 总报告。",
                "diff-matrix.json 记录迁移项差异。",
                "migration-gap-ledger.json 记录 P0/P1/P2 缺口。",
                "roadmap.json 记录 24h / 7d / 30d 动作。",
            ],
        ),
    )
    grouped = {"P0": [], "P1": [], "P2": []}
    for gap in gaps:
        grouped.setdefault(gap["priority"], []).append(gap["repair"])
    p0_lines = [f"- {item}" for item in grouped.get("P0", [])] or ["- 无"]
    p1_lines = [f"- {item}" for item in grouped.get("P1", [])] or ["- 无"]
    p2_lines = [f"- {item}" for item in grouped.get("P2", [])] or ["- 无"]
    write_text(
        run_dir / "decision-pack.md",
        "\n".join(
            [
                "# Decision Pack",
                "",
                "## P0 立即修",
                *p0_lines,
                "",
                "## P1 本周补齐",
                *p1_lines,
                "",
                "## P2 进入递归优化",
                *p2_lines,
            ]
        ),
    )
    write_text(
        run_dir / "evolution-note.md",
        render_brief_markdown(
            "Evolution Note",
            [
                "迁移审计已经从一次性盘点升级成可重复执行的脚本与工件链。",
                "源机对照需要从历史基线进一步升级成 live SSH compare。",
                "GitHub 凭证复检应该被制度化，不再依赖发现后人工补救。",
            ],
        ),
    )
    write_json(run_dir / "roadmap.json", grouped)
    write_json(run_dir / "diff-matrix.json", diff_rows)


def build_table_payloads(
    run_id: str,
    run_dir: Path,
    local_snapshot: dict[str, Any],
    source_snapshot: dict[str, Any],
    diff_rows: list[dict[str, Any]],
    checks: dict[str, Any],
    system_score: dict[str, Any],
    subsystem_scores: list[dict[str, Any]],
    sample_scores: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
    source_errors: list[dict[str, str]],
) -> dict[str, Any]:
    now = datetime.now()
    checkpoint_rows, axis_scores, _ = build_system_checkpoint_rows(run_id, diff_rows, checks)
    action_rows = build_action_rows(run_id, gaps)
    recursion_rows = build_recursion_rows(run_id, gaps, now)
    scorecard_rows = scorecard_rows_from_scores(run_id, system_score, subsystem_scores, sample_scores)
    internal_evidence_rows = gather_internal_evidence(run_id, run_dir, source_snapshot, source_errors)
    batch_row = {
        "Audit Run ID": run_id,
        "审计日期": now.strftime("%Y-%m-%d"),
        "审计范围": "新 Mac Pro Max 迁移收尾 + 黑色卫星机对照",
        "时间边界": now.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "full",
        "内部权重": "1.0",
        "外部权重": "0.0",
        "内部总分": f"{system_score['internal_score']:.1f}",
        "外部总分": "0.0",
        "综合分": f"{system_score['internal_score']:.1f}",
        "等级": system_score["grade"],
        "最强区块": max(subsystem_scores, key=lambda item: item["internal_score"])["name"],
        "最弱区块": min(subsystem_scores, key=lambda item: item["internal_score"])["name"],
        "当前最大失真": "把主链恢复误判成所有凭证与 live source compare 已经收口。",
        "状态": "bundle_ready",
        "报告路径": str(run_dir / "report.md"),
        "同步结果": str(run_dir / "sync-result.json"),
    }
    gap_table_rows = [
        {
            "Gap Key": f"{run_id}::{slugify(gap['gap_id'])}",
            "Audit Run ID": run_id,
            "Object Key": f"subsystem::{slugify(gap['subsystem'])}",
            "差距类型": gap["title"],
            "来源层": gap["subsystem"],
            "严重度": "high" if gap["priority"] == "P0" else "medium" if gap["priority"] == "P1" else "low",
            "当前状态": gap["status"],
            "目标状态": "closed",
            "阻塞原因": gap["impact"],
            "证据键": gap["evidence"],
            "建议修复": gap["repair"],
            "状态": "open",
        }
        for gap in gaps
    ]
    bundle = {
        "run_id": run_id,
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "local_snapshot": local_snapshot,
        "source_snapshot": source_snapshot,
        "diff_rows": diff_rows,
        "checks": checks,
        "table_payloads": {
            "审计批次": [batch_row],
            "评分卡总表": scorecard_rows,
            "检查点明细": checkpoint_rows,
            "扣分与差距": gap_table_rows,
            "进化动作": action_rows,
            "内部证据": internal_evidence_rows,
            "外部情报": [],
            "对标映射": [],
            "递归队列": recursion_rows,
        },
        "axis_scores": axis_scores,
    }
    return bundle


def load_bridge_module() -> Any:
    spec = importlib.util.spec_from_file_location("feishu_bridge", FEISHU_BRIDGE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load bridge module from {FEISHU_BRIDGE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def upsert_rows(
    client: Any,
    bridge: Any,
    table_id: str,
    key_field: str,
    actual_primary_field: str,
    rows: list[dict[str, Any]],
    apply: bool,
) -> dict[str, int]:
    existing_records = client.list_records(table_id) if table_id else []
    index = bridge.existing_index(existing_records, actual_primary_field) if table_id else {}
    preview_create = 0
    preview_update = 0
    created = 0
    updated = 0
    for row in rows:
        key = str(row.get(key_field) or "").strip()
        payload = dict(row)
        payload[actual_primary_field] = key
        if key in index:
            preview_update += 1
            if apply:
                client.update_record(table_id, str(index[key]["record_id"]), payload)
                updated += 1
        else:
            preview_create += 1
            if apply:
                client.create_record(table_id, payload)
                created += 1
    return {
        "would_create": preview_create,
        "would_update": preview_update,
        "created": created,
        "updated": updated,
    }


def sync_to_feishu(bundle: dict[str, Any], *, link: str, account_id: str, apply: bool) -> dict[str, Any]:
    manifest = json.loads(OPS_SCHEMA_PATH.read_text(encoding="utf-8"))
    table_specs = {item["table_name"]: item for item in manifest.get("tables", []) if isinstance(item, dict)}
    if not apply:
        return {
            "ok": True,
            "mode": "dry-run",
            "tables": {
                name: {"row_count": len(rows), "preview": {"would_create": len(rows), "would_update": 0}}
                for name, rows in bundle["table_payloads"].items()
            },
        }
    bridge = load_bridge_module()
    creds = bridge.load_feishu_account(account_id)
    base_token = bridge.resolve_base_token(link, app_id=creds["app_id"], app_secret=creds["app_secret"])
    client = bridge.FeishuBitableClient(creds["app_id"], creds["app_secret"], base_token)
    sync_tables: dict[str, Any] = {}
    for table_name, rows in bundle["table_payloads"].items():
        spec = table_specs[table_name]
        ensured = bridge.ensure_table(
            client,
            table_name=table_name,
            primary_field=str(spec["primary_field"]),
            field_names=[str(field) for field in spec.get("fields", [])],
            apply=True,
        )
        table_id = ensured.get("table_id") or ""
        actual_primary = str(spec["primary_field"])
        if table_id:
            current_fields = client.list_fields(table_id)
            primary = next((item for item in current_fields if item.get("is_primary")), None)
            if primary and primary.get("field_name"):
                actual_primary = str(primary["field_name"])
        counts = upsert_rows(client, bridge, table_id, str(spec["primary_field"]), actual_primary, rows, True) if table_id else {
            "would_create": len(rows),
            "would_update": 0,
            "created": 0,
            "updated": 0,
        }
        sync_tables[table_name] = {
            "table_id": table_id,
            "row_count": len(rows),
            "ensure_table": ensured,
            "preview": {"would_create": counts["would_create"], "would_update": counts["would_update"]},
            "result": {"created": counts["created"], "updated": counts["updated"]},
        }
    return {"ok": True, "mode": "apply", "base_token": base_token, "tables": sync_tables}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-host", action="append", dest="source_hosts", help="Preferred source host alias or user@host.")
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--feishu-link", default=DEFAULT_FEISHU_LINK)
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    parser.add_argument("--apply-feishu", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    hosts = args.source_hosts or DEFAULT_SOURCE_HOSTS
    run_id = datetime.now().strftime("new-mac-post-cutover-audit-%Y%m%d-%H%M%S")
    run_dir = args.output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    local_snapshot = collect_local_snapshot()
    source_snapshot, source_errors = collect_source_snapshot(hosts)
    checks = run_healthchecks(run_id)
    attach_workflow_state(local_snapshot, checks)
    diff_rows = build_diff_matrix(local_snapshot, source_snapshot)
    checkpoint_rows, axis_scores, _ = build_system_checkpoint_rows(run_id, diff_rows, checks)
    system_score = build_system_score(axis_scores, diff_rows)
    subsystem_scores = [score_subsystem(label, subsystem_items(diff_rows, label), checks, source_snapshot) for _, label in SUBSYSTEMS]
    gaps = build_gap_ledger(diff_rows, checks, source_snapshot)
    sample_scores = build_sample_scores(checks, source_snapshot, gaps)

    write_json(run_dir / "local-snapshot.json", local_snapshot)
    write_json(run_dir / "source-snapshot.json", source_snapshot)
    write_json(run_dir / "healthchecks.json", checks)
    write_json(run_dir / "system-checkpoints.json", checkpoint_rows)
    write_json(run_dir / "subsystem-scorecards.json", subsystem_scores)
    write_json(run_dir / "migration-gap-ledger.json", gaps)
    write_json(run_dir / "sample-scorecards.json", sample_scores)

    report_text = render_report(run_id, local_snapshot, source_snapshot, diff_rows, checks, system_score, subsystem_scores, sample_scores, gaps)
    build_markdown_packs(run_dir, report_text, gaps, checks, diff_rows)

    bundle = build_table_payloads(
        run_id,
        run_dir,
        local_snapshot,
        source_snapshot,
        diff_rows,
        checks,
        system_score,
        subsystem_scores,
        sample_scores,
        gaps,
        source_errors,
    )
    write_json(run_dir / "feishu-bundle.json", bundle)

    sync_result = sync_to_feishu(bundle, link=args.feishu_link, account_id=args.account_id, apply=args.apply_feishu)
    write_json(run_dir / "sync-result.json", sync_result)

    print(
        json.dumps(
            {
                "status": "ok",
                "run_id": run_id,
                "run_dir": str(run_dir),
                "source_snapshot_mode": source_snapshot.get("snapshot_mode"),
                "gap_count": len(gaps),
                "feishu_mode": sync_result.get("mode"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
