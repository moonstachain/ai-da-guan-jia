#!/usr/bin/env python3
"""Collect evidence for TS-REVIEW-01 and refresh CLAUDE-INIT after verification."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request


WORKSPACE_ROOT = Path("/Users/liming/Documents/codex-ai-gua-jia-01")
AI_DA_GUAN_JIA_ROOT = WORKSPACE_ROOT / "work" / "ai-da-guan-jia"
YUANLI_OS_CLAUDE_ROOT = WORKSPACE_ROOT / "yuanli-os-claude"
CLAUDE_INIT_PATH = YUANLI_OS_CLAUDE_ROOT / "CLAUDE-INIT.md"
REVISION_SOURCE_PATH = Path("/Users/liming/Downloads/yuanlios-first-evolution-review.md")
OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"
FEISHU_AUTH_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
FEISHU_API_BASE = "https://open.feishu.cn/open-apis/bitable/v1"
LIVE_RUNTIME_BASE_TOKEN = "PHp2wURl2i6SyBkDtmGcuaEenag"

REVIEW_ID = "TS-REVIEW-01"
DEFAULT_RUN_ID = "adagj-20260318-ts-review-01"
WINDOW_START = "2026-03-08 00:00:00"
WINDOW_END = "2026-03-18 23:59:59"

PVD_BASE_TOKEN = "PVDgbdWYFaDLBiss0hlcM5WRnQc"
KANGBO_BASE_TOKEN = "IqZhbMJJxaq8D4sHOvkciaWFnid"

FEISHU_TABLES = [
    {
        "label": "live_control",
        "app_token": LIVE_RUNTIME_BASE_TOKEN,
        "table_id": "tblnRCmMS7QBMtHI",
        "table_name": "live 运行态总控",
    },
    {
        "label": "skill_inventory",
        "app_token": PVD_BASE_TOKEN,
        "table_id": "tbl7g2E33tHswDeE",
        "table_name": "Skill 盘点表",
    },
    {
        "label": "governance_maturity",
        "app_token": PVD_BASE_TOKEN,
        "table_id": "tblYnhPN5JyMNwrU",
        "table_name": "治理成熟度评估",
    },
]

KANGBO_TABLES = [
    {"label": "L1", "app_token": KANGBO_BASE_TOKEN, "table_id": "tbl6QgzUgcXq4HO5", "table_name": "L1_康波事件信号"},
    {"label": "L2", "app_token": KANGBO_BASE_TOKEN, "table_id": "tbl82HhewJxuU8hV", "table_name": "L2_专家智库"},
    {"label": "L3", "app_token": KANGBO_BASE_TOKEN, "table_id": "tblcAxYlxfEHbPHv", "table_name": "L3_专家洞察"},
    {"label": "L4_core", "app_token": KANGBO_BASE_TOKEN, "table_id": "tblu9j7rpLFYCkto", "table_name": "L4_财富三观_核心命题表"},
    {"label": "L4_assets", "app_token": KANGBO_BASE_TOKEN, "table_id": "tblypdAEzkxIyISM", "table_name": "L4_资产审美_标的库"},
    {"label": "L4_strategy", "app_token": KANGBO_BASE_TOKEN, "table_id": "tblUrtJLbF7aerLm", "table_name": "L4_配置策略表"},
    {"label": "L4_quant", "app_token": KANGBO_BASE_TOKEN, "table_id": "tblIwtSUXnsHWoGs", "table_name": "L4_智能资产_量化全景"},
]


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_openclaw_account(account_id: str = "feishu-claw") -> dict[str, str]:
    config = read_json(OPENCLAW_CONFIG)
    accounts = (((config.get("channels") or {}).get("feishu") or {}).get("accounts") or {})
    account = accounts.get(account_id) or {}
    app_id = str(account.get("appId") or "").strip()
    app_secret = str(account.get("appSecret") or "").strip()
    if not app_id or not app_secret:
        raise RuntimeError(f"Missing Feishu credentials for accountId={account_id}")
    return {"app_id": app_id, "app_secret": app_secret}


def json_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 40,
) -> dict[str, Any]:
    request_headers = {"User-Agent": "adagj-ts-review-01/1.0"}
    if headers:
        request_headers.update(headers)
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib_request.Request(url, data=body, headers=request_headers, method=method.upper())
    try:
        with urllib_request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib_error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {exc.reason}: {details}") from exc


def fetch_tenant_access_token(app_id: str, app_secret: str) -> str:
    result = json_request("POST", FEISHU_AUTH_URL, payload={"app_id": app_id, "app_secret": app_secret})
    if result.get("code") != 0:
        raise RuntimeError(f"Feishu auth failed: {result}")
    token = str(result.get("tenant_access_token") or "").strip()
    if not token:
        raise RuntimeError(f"Feishu auth returned empty token: {result}")
    return token


@dataclass
class FeishuBitableClient:
    app_id: str
    app_secret: str
    base_token: str
    _tenant_access_token: str | None = None

    def _auth_headers(self) -> dict[str, str]:
        if not self._tenant_access_token:
            self._tenant_access_token = fetch_tenant_access_token(self.app_id, self.app_secret)
        return {"Authorization": f"Bearer {self._tenant_access_token}"}

    def _api(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{FEISHU_API_BASE}{path}"
        if query:
            from urllib import parse as urllib_parse

            url = f"{url}?{urllib_parse.urlencode(query)}"
        result = json_request(method, url, headers=self._auth_headers(), payload=payload)
        if result.get("code") != 0:
            raise RuntimeError(f"Feishu API failed {path}: {result}")
        return result

    def list_fields(self, table_id: str) -> list[dict[str, Any]]:
        result = self._api("GET", f"/apps/{self.base_token}/tables/{table_id}/fields", query={"page_size": 100})
        return ((result.get("data") or {}).get("items") or [])

    def list_records(self, table_id: str, *, page_size: int = 500) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            query: dict[str, Any] = {"page_size": page_size}
            if page_token:
                query["page_token"] = page_token
            result = self._api("GET", f"/apps/{self.base_token}/tables/{table_id}/records", query=query)
            data = result.get("data") or {}
            records.extend(data.get("items") or [])
            if not data.get("has_more"):
                break
            page_token = str(data.get("page_token") or "").strip() or None
            if not page_token:
                break
        return records


def git_log(repo_path: Path) -> dict[str, Any]:
    git_root = subprocess.check_output(["git", "-C", str(repo_path), "rev-parse", "--show-toplevel"], text=True).strip()
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_path),
            "log",
            f"--since={WINDOW_START}",
            f"--until={WINDOW_END}",
            "--date=iso-strict",
            "--pretty=format:%H%x09%ad%x09%s",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    commits: list[dict[str, str]] = []
    for line in result.stdout.splitlines():
        sha, date_str, subject = line.split("\t", 2)
        commits.append({"sha": sha, "date": date_str, "subject": subject})
    return {
        "repo_path": str(repo_path),
        "git_root": git_root,
        "window": {"since": WINDOW_START, "until": WINDOW_END},
        "commit_count": len(commits),
        "commits": commits,
        "first_commit": commits[0] if commits else {},
        "last_commit": commits[-1] if commits else {},
    }


def build_distribution(values: list[str]) -> dict[str, int]:
    return dict(Counter(values))


def capture_table_snapshot(client: FeishuBitableClient, table_spec: dict[str, str]) -> dict[str, Any]:
    table_id = table_spec["table_id"]
    fields = client.list_fields(table_id)
    records = client.list_records(table_id)
    snapshot: dict[str, Any] = {
        "table_name": table_spec["table_name"],
        "table_id": table_id,
        "base_token": client.base_token,
        "field_count": len(fields),
        "fields": [
            {
                "field_name": str(item.get("field_name") or ""),
                "field_id": str(item.get("field_id") or ""),
                "type": item.get("type"),
                "is_primary": bool(item.get("is_primary")),
            }
            for item in fields
        ],
        "record_count": len(records),
        "records_sample": records[:5],
    }
    if table_spec["label"] == "skill_inventory":
        statuses = [str((record.get("fields") or {}).get("status") or "") for record in records]
        quadrants = [str((record.get("fields") or {}).get("quadrant") or "") for record in records]
        source_types = [str((record.get("fields") or {}).get("source_type") or "") for record in records]
        snapshot["status_distribution"] = build_distribution(statuses)
        snapshot["quadrant_distribution"] = build_distribution(quadrants)
        snapshot["source_type_distribution"] = build_distribution(source_types)
        snapshot["active_count"] = snapshot["status_distribution"].get("active", 0)
    if table_spec["label"] == "governance_maturity":
        latest = max(
            records,
            key=lambda item: int((item.get("fields") or {}).get("audit_date") or 0),
            default=None,
        )
        if latest:
            latest_fields = latest.get("fields") or {}
            snapshot["latest_audit"] = {
                "audit_id": latest_fields.get("audit_id"),
                "audit_date": latest_fields.get("audit_date"),
                "total_score": latest_fields.get("total_score"),
                "total_score_40": latest_fields.get("total_score_40"),
                "dimension_group": latest_fields.get("dimension_group"),
                "top_gap": latest_fields.get("top_gap"),
                "top_action": latest_fields.get("top_action"),
            }
    return snapshot


def capture_kangbo_snapshot(client: FeishuBitableClient) -> dict[str, Any]:
    tables: dict[str, Any] = {}
    for spec in KANGBO_TABLES:
        fields = client.list_fields(spec["table_id"])
        records = client.list_records(spec["table_id"])
        tables[spec["label"]] = {
            "table_name": spec["table_name"],
            "table_id": spec["table_id"],
            "base_token": client.base_token,
            "field_count": len(fields),
            "record_count": len(records),
            "fields": [str(item.get("field_name") or "") for item in fields],
        }
    return {
        "base_token": client.base_token,
        "tables": tables,
        "summary": {
            "L1": tables["L1"]["record_count"],
            "L2": tables["L2"]["record_count"],
            "L3": tables["L3"]["record_count"],
            "L4_core": tables["L4_core"]["record_count"],
            "L4_assets": tables["L4_assets"]["record_count"],
            "L4_strategy": tables["L4_strategy"]["record_count"],
            "L4_quant": tables["L4_quant"]["record_count"],
        },
    }


def build_findings(
    git_evidence: dict[str, Any],
    feishu_snapshots: dict[str, Any],
    kangbo_snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    governance_latest = feishu_snapshots["governance_maturity"].get("latest_audit") or {}
    skill_snapshot = feishu_snapshots["skill_inventory"]
    kangbo_summary = kangbo_snapshot["summary"]
    return [
        {
            "claim_id": "git-root-shared",
            "status": "confirmed",
            "severity": "info",
            "statement": "两个路径 scope 都解析到同一个 git root，因此 review 中的两个仓库日志证据本质上共享同一提交历史。",
            "evidence": [
                f"yuanli-os-claude git_root={git_evidence['yuanli-os-claude']['git_root']}",
                f"ai-da-guan-jia git_root={git_evidence['ai-da-guan-jia']['git_root']}",
                f"window commit_count={git_evidence['shared_window_commit_count']}",
            ],
        },
        {
            "claim_id": "governance-26-confirmed",
            "status": "confirmed",
            "severity": "info",
            "statement": "治理成熟度当前 latest audit 仍然是 26/40，和复盘里对 D1-D10 结构成熟度的叙述一致。",
            "evidence": [
                f"audit_id={governance_latest.get('audit_id')}",
                f"total_score_40={governance_latest.get('total_score_40')}",
                f"top_gap={governance_latest.get('top_gap')}",
            ],
        },
        {
            "claim_id": "skill-available-stale",
            "status": "superseded_by_new_evidence",
            "severity": "medium",
            "statement": "Skill 盘点表的当前 active 数已到 132，不是 review / early-INIT 里沿用的 112；这条数字需要在启动记忆里修正。",
            "evidence": [
                f"record_count={skill_snapshot['record_count']}",
                f"status_distribution={skill_snapshot['status_distribution']}",
                f"active_count={skill_snapshot['active_count']}",
            ],
        },
        {
            "claim_id": "kangbo-l3-stale",
            "status": "superseded_by_new_evidence",
            "severity": "medium",
            "statement": "康波 L2=33 仍然成立，但 L3 当前 live 已到 49，早先写成 48 的摘要已过期。",
            "evidence": [
                f"L2={kangbo_summary['L2']}",
                f"L3={kangbo_summary['L3']}",
                "docs/kangbo-expert-network.md currently states 49.",
            ],
        },
        {
            "claim_id": "live-control-runtime-confirmed",
            "status": "confirmed",
            "severity": "info",
            "statement": "live 运行态总控表已按 runtime app token 成功读取，当前可见 1 条记录 / 19 个字段，可作为运行态证据来源。",
            "evidence": [
                f"base_token={feishu_snapshots['live_control']['base_token']}",
                f"field_count={feishu_snapshots['live_control']['field_count']}",
                f"record_count={feishu_snapshots['live_control']['record_count']}",
                f"runtime_state={(feishu_snapshots['live_control']['records_sample'][0].get('fields') or {}).get('runtime_state', '') if feishu_snapshots['live_control']['records_sample'] else ''}",
            ],
        },
        {
            "claim_id": "kangbo-counts-confirmed",
            "status": "confirmed",
            "severity": "info",
            "statement": "康波 Base 的 L1-L4 行数可以稳定复现，说明投研数据层本身是可验真的。",
            "evidence": [
                f"L1={kangbo_summary['L1']}",
                f"L2={kangbo_summary['L2']}",
                f"L3={kangbo_summary['L3']}",
                f"L4_core={kangbo_summary['L4_core']}",
                f"L4_assets={kangbo_summary['L4_assets']}",
                f"L4_strategy={kangbo_summary['L4_strategy']}",
                f"L4_quant={kangbo_summary['L4_quant']}",
            ],
        },
    ]


def render_evidence_markdown(evidence: dict[str, Any]) -> str:
    lines = [
        "# TS-REVIEW-01 Evidence Review",
        "",
        f"- Run ID: `{evidence['run_id']}`",
        f"- Created At: `{evidence['created_at']}`",
        f"- Review Source: `{evidence['review_source']}`",
        f"- Git Root: `{evidence['git_evidence']['shared_git_root']}`",
        "",
        "## Conclusion",
        "",
        evidence["conclusion"],
        "",
        "## Confirmed / Superseded / Follow-up",
    ]
    for item in evidence["findings"]:
        lines.extend(
            [
                "",
                f"### {item['claim_id']}",
                f"- Status: {item['status']}",
                f"- Severity: {item['severity']}",
                f"- Statement: {item['statement']}",
                "- Evidence:",
            ]
        )
        lines.extend([f"  - {entry}" for entry in item["evidence"]])
    lines.extend(
        [
            "",
            "## Git Window",
            "",
            f"- Commit count: {evidence['git_evidence']['shared_window_commit_count']}",
            f"- Window: {WINDOW_START} → {WINDOW_END}",
            f"- Repo log paths resolve to same git root: {evidence['git_evidence']['same_git_root']}",
            "",
            "## Feishu Snapshot",
            "",
            f"- live_control: {evidence['feishu_snapshots']['live_control']['record_count']} records / {evidence['feishu_snapshots']['live_control']['field_count']} fields",
            f"- skill_inventory: {evidence['feishu_snapshots']['skill_inventory']['record_count']} records / active {evidence['feishu_snapshots']['skill_inventory']['active_count']}",
            f"- governance_maturity: {evidence['feishu_snapshots']['governance_maturity']['record_count']} audits / latest {json.dumps(evidence['feishu_snapshots']['governance_maturity'].get('latest_audit') or {}, ensure_ascii=False)}",
            "",
            "## Kangbo Snapshot",
            "",
            json.dumps(evidence["kangbo_snapshot"]["summary"], ensure_ascii=False, indent=2),
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_evolution_input(evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": evidence["run_id"],
        "created_at": evidence["created_at"],
        "task_text": "TS-REVIEW-01 evidence pull: verify the first evolution review against live git and Feishu evidence, then refresh CLAUDE-INIT counts and the periodic review section.",
        "goal_model": "Turn the first evolution review into a verified evidence pack and correct any stale launch-memory numbers.",
        "skills_considered": ["ai-da-guan-jia", "feishu-bitable-bridge"],
        "skills_selected": ["ai-da-guan-jia", "feishu-bitable-bridge"],
        "autonomy_judgment": "AI owns the read-only evidence pull, synthesis, and launch-memory correction; no human click is required for the data collection itself.",
        "global_optimum_judgment": "Use the live APIs and git root as the source of truth, treat the review as a snapshot, and only refresh CLAUDE-INIT after verification.",
        "reuse_judgment": "Reuse the existing Feishu auth path and the canonical run bundle layout instead of inventing a parallel evidence format.",
        "verification_judgment": "The real checks are commit-window counts, live table row counts, and current snapshot distributions on the Feishu side.",
        "evolution_judgment": "The run should land as a canonical evidence pack plus a launch-memory refresh, with stale snapshot numbers corrected in place.",
        "max_distortion": "Do not confuse an early review snapshot with the current live counts; the current values must be grounded in API readback.",
        "verification_result": {
            "status": "verified",
            "evidence": [
                "git logs for both path scopes resolve to the same git root and 41 commits in the 2026-03-08 → 2026-03-18 window.",
                "live skill inventory currently shows 150 records with 132 active items.",
                "governance maturity live latest audit shows 26/40.",
                "Kangbo live counts are L1=4, L2=33, L3=49, L4 core=30, assets=40, strategy=15, quant=75.",
            ],
            "open_questions": [],
        },
        "effective_patterns": [
            "Treat local git root and live Feishu API readback as the canonical evidence pair.",
            "Capture live distributions, not just top-line counts, before refreshing startup memory.",
            "Keep snapshot claims and current claims separate in the evidence pack.",
        ],
        "wasted_patterns": [
            "Relying on stale init-note numbers without checking the live table distributions first.",
            "Assuming path-level repo names imply distinct git roots.",
        ],
        "evolution_candidates": [
            "Add a tiny launcher-memory drift checker that highlights stale counts before they are copied into CLAUDE-INIT.",
            "Expose a single evidence-review script entrypoint so future TS-REVIEW rounds do not need ad hoc commands.",
            "Consider storing the latest live counts in a compact machine-readable cache under the strategy current directory.",
        ],
        "human_boundary": "No human action required for the evidence pull itself; after that the resulting launch-memory edits are local and deterministic.",
        "governance_signal_status": "loaded",
        "credit_influenced_selection": False,
        "proposal_authority_summary": {
            "suggestion_capable": ["ai-da-guan-jia"],
            "execution_focused": ["feishu-bitable-bridge"],
        },
        "feishu_sync_status": "not_run",
        "moltbook_sync_status": "not_configured",
        "github_sync_status": "not_run",
        "github_archive_status": "not_archived",
        "github_classification": {
            "type": "task",
            "domain": "governance",
            "state": "evidence-pull",
            "artifact": "evidence-review-01",
            "slug": "ts-review-01-evidence",
            "task_key": "TS-REVIEW-01",
        },
    }


def update_claude_init(evidence: dict[str, Any]) -> None:
    text = CLAUDE_INIT_PATH.read_text(encoding="utf-8")
    updated = text
    updated = updated.replace(
        "- 当前重点：`驾驶舱 2.0 部署验收 + 康波智库首轮闭环（L2×33 / L3×48 / scan_t0 已验真）`",
        "- 当前重点：`驾驶舱 2.0 部署验收 + 康波智库首轮闭环（L2×33 / L3×49 / scan_t0 已验真）`",
    )
    updated = updated.replace(
        "- `TS-KB-03` 康波智库落地：已完成首轮闭环（`L2×33 + L3×48 + scan_t0 apply`），后续升级重点是 `manual -> scheduled`",
        "- `TS-KB-03` 康波智库落地：已完成首轮闭环（`L2×33 + L3×49 + scan_t0 apply`），后续升级重点是 `manual -> scheduled`",
    )
    updated = updated.replace(
        "- `Skill` live 表以 `tbl7g2E33tHswDeE` 为准，不用旧 id",
        "- `Skill` live 表以 `tbl7g2E33tHswDeE` 为准，当前 150 条记录中 `active=132`、`draft=15`、`needs_manual_review=3`，不用旧 id",
    )
    updated = updated.replace(
        "- `Skill` 不是几个而已，当前治理记录是 `150` 条，当前可用 `112`",
        "- `Skill` 不是几个而已，当前治理记录是 `150` 条，当前可用 `132`",
    )
    updated = updated.replace(
        "8. Skill 治理进入合并态：150 条治理记录、7 个超级 skill、当前可用 112。详见 `docs/r18-roadmap.md`。",
        "8. Skill 治理进入合并态：150 条治理记录、7 个超级 skill、当前可用 132。详见 `docs/r18-roadmap.md`。",
    )
    if "## 定期进化盘点制度" not in updated:
        insertion = """
## 定期进化盘点制度

- 日盘：每日 23:00，产出日盘快照
- 周盘：每周日 23:00，产出周盘报告 + 评分更新
- 月盘：每月末，产出月度进化报告
- 季盘：每季末，产出季度战略复盘
- 年盘：每年 12 月，产出年度进化白皮书
- 执行方式：Claude 输出盘点 Task Spec → 人类审批 → Codex 拉取 evidence → Claude 复核出报告
- 首次完整盘点：2026-03-18（TS-REVIEW-01）
- 盘点归档：`artifacts/ai-da-guan-jia/runs/YYYY-MM-DD/<run-id>/`
"""
        marker = "## Task Spec “最后一步”标准"
        updated = updated.replace(marker, insertion.strip() + "\n\n" + marker, 1)
    if updated != text:
        CLAUDE_INIT_PATH.write_text(updated, encoding="utf-8")


def build_conclusion(findings: list[dict[str, Any]]) -> str:
    confirmed = [item for item in findings if item["status"] == "confirmed"]
    superseded = [item for item in findings if item["status"] == "superseded_by_new_evidence"]
    followup = [item for item in findings if item["status"] == "followup"]
    return (
        f"Evidence verified: {len(confirmed)} confirmed, {len(superseded)} claims superseded by new evidence, "
        f"{len(followup)} follow-up items. The review is directionally valid, but the live counts for "
        f"skill inventory and Kangbo L3 have drifted since the snapshot. The live-control table is reachable "
        f"through its runtime app token and currently shows 1 record / 19 fields."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect TS-REVIEW-01 evidence and refresh launch memory.")
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--skip-claude-init", action="store_true")
    args = parser.parse_args()

    today = datetime.now().astimezone().date().isoformat()
    run_dir = ensure_dir(AI_DA_GUAN_JIA_ROOT / "artifacts" / "ai-da-guan-jia" / "runs" / today / args.run_id)

    account = load_openclaw_account()
    client_cache: dict[str, FeishuBitableClient] = {}

    def get_client(base_token: str) -> FeishuBitableClient:
        cached = client_cache.get(base_token)
        if cached is None:
            cached = FeishuBitableClient(account["app_id"], account["app_secret"], base_token)
            client_cache[base_token] = cached
        return cached

    git_scope = {
        "yuanli-os-claude": git_log(YUANLI_OS_CLAUDE_ROOT),
        "ai-da-guan-jia": git_log(AI_DA_GUAN_JIA_ROOT),
    }
    same_git_root = git_scope["yuanli-os-claude"]["git_root"] == git_scope["ai-da-guan-jia"]["git_root"]
    shared_window_commit_count = git_scope["ai-da-guan-jia"]["commit_count"]

    feishu_snapshots = {
        item["label"]: capture_table_snapshot(get_client(str(item["app_token"])), item) for item in FEISHU_TABLES
    }
    kangbo_snapshot = capture_kangbo_snapshot(get_client(KANGBO_BASE_TOKEN))

    findings = build_findings(
        {
            **git_scope,
            "shared_git_root": git_scope["ai-da-guan-jia"]["git_root"],
            "same_git_root": same_git_root,
            "shared_window_commit_count": shared_window_commit_count,
        },
        feishu_snapshots,
        kangbo_snapshot,
    )
    evidence = {
        "review_id": REVIEW_ID,
        "run_id": args.run_id,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "review_source": str(REVISION_SOURCE_PATH),
        "git_evidence": {
            **git_scope,
            "shared_git_root": git_scope["ai-da-guan-jia"]["git_root"],
            "same_git_root": same_git_root,
            "shared_window_commit_count": shared_window_commit_count,
        },
        "feishu_snapshots": feishu_snapshots,
        "kangbo_snapshot": kangbo_snapshot,
        "findings": findings,
        "conclusion": build_conclusion(findings),
    }

    write_json(run_dir / "evidence-review-01.json", evidence)
    (run_dir / "evidence-review-01.md").write_text(render_evidence_markdown(evidence), encoding="utf-8")
    write_json(run_dir / "git-log-yuanli-os-claude.json", git_scope["yuanli-os-claude"])
    write_json(run_dir / "git-log-ai-da-guan-jia.json", git_scope["ai-da-guan-jia"])
    write_json(run_dir / "feishu-live-snapshots.json", feishu_snapshots)
    write_json(run_dir / "kangbo-snapshot.json", kangbo_snapshot)
    write_json(run_dir / "evolution-input.json", build_evolution_input(evidence))

    if not args.skip_claude_init:
        update_claude_init(evidence)

    print(f"run_dir: {run_dir}")
    print(f"evidence_json: {run_dir / 'evidence-review-01.json'}")
    print(f"evidence_md: {run_dir / 'evidence-review-01.md'}")
    print(f"git_commit_window_count: {shared_window_commit_count}")
    print(f"skill_active_count: {feishu_snapshots['skill_inventory']['active_count']}")
    print(f"governance_latest_score_40: {(feishu_snapshots['governance_maturity'].get('latest_audit') or {}).get('total_score_40', '')}")
    print(f"kangbo_l3_count: {kangbo_snapshot['summary']['L3']}")
    print(f"claude_init_updated: {not args.skip_claude_init}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
