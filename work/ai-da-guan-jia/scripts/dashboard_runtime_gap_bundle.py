from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[3]
ARTIFACTS_ROOT = PROJECT_ROOT / "work" / "ai-da-guan-jia" / "artifacts" / "ai-da-guan-jia"
RUNS_ROOT = ARTIFACTS_ROOT / "runs"

DEFAULT_BASE_CONFIG = PROJECT_ROOT / "specs" / "feishu" / "ibm-cbm-governance-dashboard-current-base-config.json"
DEFAULT_SOURCE_VIEWS = PROJECT_ROOT / "specs" / "feishu" / "ibm-cbm-governance-dashboard-v1-blueprint" / "source-views-spec.json"
DEFAULT_BINDING_RUN = PROJECT_ROOT / "output" / "feishu-dashboard-automator" / "cbm-governance" / "miaoda-r2-binding-run.json"
DEFAULT_POSTCHECK = PROJECT_ROOT / "output" / "feishu-dashboard-automator" / "cbm-governance" / "miaoda-r2-postcheck.json"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "output" / "feishu-dashboard-automator" / "cbm-governance"
FOCUS_CARD_IDS = ("diagnosis-03", "action-04")

FIELD_ALIAS_HINTS = {
    "title": "标题",
    "name": "名称",
    "status": "状态",
    "source_family": "来源家族",
}


@dataclass
class BundleContext:
    run_id: str
    created_at: str
    output_dir: Path
    base_config_path: Path
    source_views_path: Path
    binding_run_path: Path
    postcheck_path: Path
    runtime_output_root: Path


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict[str, Any] | list[Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value.strip().lower())


def find_card_spec(base_config: dict[str, Any], card_id: str) -> dict[str, Any]:
    for group_specs in base_config.get("card_specs", {}).values():
        if not isinstance(group_specs, list):
            continue
        for item in group_specs:
            if isinstance(item, dict) and str(item.get("card_id") or "") == card_id:
                return item
    raise KeyError(f"Missing card_spec for {card_id}")


def find_source_view(source_views: list[dict[str, Any]], card_id: str) -> dict[str, Any]:
    for item in source_views:
        if str(item.get("card_id") or "") == card_id:
            return item
    raise KeyError(f"Missing source_view for {card_id}")


def find_binding_step(binding_run: dict[str, Any], card_id: str) -> dict[str, Any]:
    for item in binding_run.get("steps", []):
        if str(item.get("card_id") or "") == card_id:
            return item
    raise KeyError(f"Missing binding step for {card_id}")


def find_postcheck_card(postcheck: dict[str, Any], card_id: str) -> dict[str, Any]:
    for item in postcheck.get("cards", []):
        if str(item.get("card_id") or "") == card_id:
            return item
    raise KeyError(f"Missing postcheck card for {card_id}")


def field_mapping_report(display_fields: list[str], schema_fields: dict[str, Any]) -> dict[str, Any]:
    exact_fields: list[str] = []
    alias_fields: list[dict[str, str]] = []
    unresolved_fields: list[str] = []
    schema_names = list(schema_fields.keys())
    normalized_schema = {normalize_token(name): name for name in schema_names}
    for field in display_fields:
        if field in schema_fields:
            exact_fields.append(field)
            continue
        normalized = normalize_token(field)
        alias_target = normalized_schema.get(normalized)
        if not alias_target and field in FIELD_ALIAS_HINTS:
            alias_target = FIELD_ALIAS_HINTS[field]
        if alias_target and alias_target in schema_fields:
            alias_fields.append({"logical_field": field, "schema_field": alias_target})
        else:
            unresolved_fields.append(field)
    has_pending_fields = any(str(meta.get("field_id") or "").startswith("pending__") for meta in schema_fields.values() if isinstance(meta, dict))
    return {
        "exact_fields": exact_fields,
        "alias_fields": alias_fields,
        "unresolved_fields": unresolved_fields,
        "has_pending_fields": has_pending_fields,
    }


def expected_evidence_chain(card_id: str, runtime_output_root: Path) -> dict[str, str]:
    return {
        "canvas_evidence_path": str((runtime_output_root / f"{card_id}-canvas.png").resolve()),
        "binding_evidence_path": str((runtime_output_root / f"{card_id}-binding.png").resolve()),
        "binding_run_json": str((runtime_output_root / "miaoda-r2-binding-run.json").resolve()),
        "postcheck_json": str((runtime_output_root / "miaoda-r2-postcheck.json").resolve()),
    }


def reverify_rules(card_id: str, expected_view_name: str) -> list[str]:
    rules = [
        f"`selected_source_view` 或 live source-view 文本需要等于 `{expected_view_name}`。",
        "`binding_evidence_kind` 需要进入 `binding_panel` 或 `card_shell_metadata`，不能只停在 `page_source_static_json`。",
        "`binding_evidence_path` 与 `canvas_evidence_path` 都必须存在于 repo-local 路径。",
        "`source_evidence` 不能再是 `plan_only_not_observed_in_ui`。",
    ]
    if card_id == "diagnosis-03":
        rules.append("`binding_truth` 至少要从 `binding_unproven` 提升到能判断 exact/wrong-source-view 的 live 证据态。")
    if card_id == "action-04":
        rules.append("`binding_truth` 应由执行器在 live 证据下落到四分类之一：`没绑 / 绑了但没数据 / 绑错 source view / 已正确绑定`。")
    return rules


def build_card_gap_bundle(
    *,
    card_id: str,
    base_config: dict[str, Any],
    source_views: list[dict[str, Any]],
    binding_run: dict[str, Any],
    postcheck: dict[str, Any],
    runtime_output_root: Path,
) -> dict[str, Any]:
    card_spec = find_card_spec(base_config, card_id)
    source_view = find_source_view(source_views, card_id)
    binding_step = find_binding_step(binding_run, card_id)
    postcheck_card = find_postcheck_card(postcheck, card_id)
    table_name = str(card_spec.get("table") or source_view.get("table_name") or "")
    table_schema = base_config.get("tables", {}).get(table_name, {})
    schema_fields = table_schema.get("fields", {}) if isinstance(table_schema, dict) else {}
    display_fields = [str(item) for item in source_view.get("display_fields", [])]
    field_report = field_mapping_report(display_fields, schema_fields)
    expected_view_name = str(source_view.get("view_name") or card_spec.get("view") or "")
    evidence_chain = expected_evidence_chain(card_id, runtime_output_root)

    clear_now = [
        "card_id / title / component_type / expected table / expected source view 已 repo-local 对齐。",
        "focused table 使用真实 field_id，不依赖 `pending__` 占位字段。",
        "canvas/binding 截图和 binding-run/post-check JSON 已存在于 repo-local。",
    ]
    not_clear_now = []
    if binding_step.get("selected_source_view") in (None, ""):
        not_clear_now.append("运行时 `selected_source_view` 仍为空，说明 live binding 面未被稳定抓到。")
    if str(postcheck_card.get("source_evidence") or "") == "plan_only_not_observed_in_ui":
        not_clear_now.append("post-check 仍把 source evidence 记为 `plan_only_not_observed_in_ui`。")
    if str(binding_step.get("binding_evidence_kind") or "") == "page_source_static_json":
        not_clear_now.append("当前 binding 证据仍是 `page_source_static_json`，不是 live binding panel/shell metadata。")
    if str(binding_step.get("title_match_mode") or "") == "semantic":
        not_clear_now.append("当前只拿到语义级标题匹配，不是 exact title/source-view proof。")
    if field_report["alias_fields"]:
        not_clear_now.append("source-view display_fields 与 base schema label 之间仍缺显式 alias contract。")

    return {
        "card_id": card_id,
        "expected_contract": {
            "title": str(card_spec.get("name") or ""),
            "component_type": str(card_spec.get("type") or ""),
            "table_name": table_name,
            "table_id": str(table_schema.get("table_id") or ""),
            "view_name": expected_view_name,
            "source_view_id": str(source_view.get("id") or ""),
            "question_id": str(source_view.get("question_id") or ""),
            "metrics": source_view.get("metrics", []),
            "dimensions": source_view.get("dimensions", []),
            "filters": source_view.get("filters", []),
            "display_fields": display_fields,
            "action_target_ids": source_view.get("action_target_ids", []),
            "purpose": str(card_spec.get("purpose") or ""),
        },
        "schema_field_status": {
            "schema_fields": list(schema_fields.keys()),
            **field_report,
        },
        "runtime_observation": {
            "binding_run_status": str(binding_step.get("status") or ""),
            "selected_source_view": binding_step.get("selected_source_view"),
            "title_match_mode": str(binding_step.get("title_match_mode") or ""),
            "matched_title": str(binding_step.get("matched_title") or ""),
            "binding_evidence_kind": str(binding_step.get("binding_evidence_kind") or ""),
            "binding_truth": str(binding_step.get("binding_truth") or ""),
            "binding_excerpt": str(binding_step.get("binding_excerpt") or ""),
            "postcheck_source_evidence": str(postcheck_card.get("source_evidence") or ""),
            "postcheck_binding_truth": str(postcheck_card.get("binding_truth") or ""),
            "postcheck_binding_evidence_kind": str(postcheck_card.get("binding_evidence_kind") or ""),
        },
        "clear_now": clear_now,
        "not_clear_now": not_clear_now,
        "expected_evidence_chain": evidence_chain,
        "reverify_rules": reverify_rules(card_id, expected_view_name),
    }


def build_bundle(context: BundleContext) -> dict[str, Any]:
    base_config = load_json(context.base_config_path)
    source_views = load_json(context.source_views_path)
    binding_run = load_json(context.binding_run_path)
    postcheck = load_json(context.postcheck_path)
    if not isinstance(base_config, dict) or not isinstance(source_views, list) or not isinstance(binding_run, dict) or not isinstance(postcheck, dict):
        raise ValueError("Unexpected JSON structure for runtime gap bundle inputs.")

    cards = [
        build_card_gap_bundle(
            card_id=card_id,
            base_config=base_config,
            source_views=source_views,
            binding_run=binding_run,
            postcheck=postcheck,
            runtime_output_root=context.runtime_output_root,
        )
        for card_id in FOCUS_CARD_IDS
    ]
    global_clear = [
        "focus cards 的 expected table/view/component contract 已固定在 repo-local spec。",
        "focus cards 所依赖表字段都已是稳定 field_id，当前 gap 不是 schema apply 权限问题。",
        "页面执行面复验所需的 canvas/binding 证据路径和 JSON carrier 已存在。",
    ]
    global_gaps = [
        {
            "gap_id": "runtime_source_view_observability",
            "status": "open",
            "why": "运行时仍拿不到 live `selected_source_view`，只能看到 `page_source_static_json` 或语义标题。",
            "applies_to": list(FOCUS_CARD_IDS),
        },
        {
            "gap_id": "display_field_alias_contract",
            "status": "open",
            "why": "source-view spec 的逻辑字段别名和 base schema 的真实 label 之间还缺显式映射，影响 repo-local verify 的确定性。",
            "applies_to": list(FOCUS_CARD_IDS),
        },
    ]
    return {
        "schema_version": "dashboard-runtime-gap-bundle-v1",
        "run_id": context.run_id,
        "created_at": context.created_at,
        "goal": "压缩 diagnosis-03 / action-04 的 dashboard runtime data model clear/gap 状态，为页面执行面动作后的 support/verify 复验准备 repo-local 对照。",
        "source_artifacts": {
            "base_config_json": str(context.base_config_path.resolve()),
            "source_views_json": str(context.source_views_path.resolve()),
            "binding_run_json": str(context.binding_run_path.resolve()),
            "postcheck_json": str(context.postcheck_path.resolve()),
        },
        "focus_card_ids": list(FOCUS_CARD_IDS),
        "clear_now": global_clear,
        "runtime_model_gaps": global_gaps,
        "cards": cards,
        "support_verify_packet": {
            "when_to_use": "页面执行面完成新一轮 bind-cards / post-check 后，support/verify 直接对照这份 gap bundle 做 repo-local 复验。",
            "first_checks": [
                "先看 card.expected_contract.view_name 与 post-check/source-view 是否 exact 对齐。",
                "再看 binding_evidence_kind 是否摆脱 `page_source_static_json`。",
                "最后看 binding_truth/source_evidence 是否从 partial 提升到 live 可判定态。",
            ],
        },
    }


def render_bundle_markdown(bundle: dict[str, Any]) -> str:
    lines = [
        "# Dashboard Runtime Gap Bundle",
        "",
        f"- run_id: `{bundle.get('run_id', '')}`",
        f"- created_at: `{bundle.get('created_at', '')}`",
        f"- focus_card_ids: `{', '.join(bundle.get('focus_card_ids', []))}`",
        "",
        "## Clear Now",
        "",
    ]
    lines.extend(f"- {item}" for item in bundle.get("clear_now", []))
    lines.extend(["", "## Runtime Model Gaps", ""])
    for item in bundle.get("runtime_model_gaps", []):
        lines.append(f"- `{item.get('gap_id', '')}` | status=`{item.get('status', '')}` | applies_to=`{', '.join(item.get('applies_to', []))}`")
        lines.append(f"  - why: {item.get('why', '')}")
    lines.extend(["", "## Cards", ""])
    for card in bundle.get("cards", []):
        expected = card.get("expected_contract", {})
        runtime = card.get("runtime_observation", {})
        schema = card.get("schema_field_status", {})
        lines.append(
            f"- `{card.get('card_id', '')}` | type=`{expected.get('component_type', '')}` | table=`{expected.get('table_name', '')}` | view=`{expected.get('view_name', '')}`"
        )
        lines.append(f"  - runtime: selected_source_view=`{runtime.get('selected_source_view', '')}` | binding_evidence_kind=`{runtime.get('binding_evidence_kind', '')}` | binding_truth=`{runtime.get('binding_truth', '')}`")
        lines.append(f"  - alias_fields: `{json.dumps(schema.get('alias_fields', []), ensure_ascii=False)}`")
        for item in card.get("not_clear_now", []):
            lines.append(f"  - gap: {item}")
    return "\n".join(lines) + "\n"


def render_support_checklist(bundle: dict[str, Any]) -> str:
    lines = [
        "# Dashboard Runtime Reverify Checklist",
        "",
        "- 适用时机：页面执行面完成新的 `bind-cards -> post-check` 之后。",
        "- 先看这 3 件事：",
        "  - `selected_source_view` 是否等于 expected view_name",
        "  - `binding_evidence_kind` 是否脱离 `page_source_static_json`",
        "  - `source_evidence / binding_truth` 是否从 partial 提升",
        "",
    ]
    for card in bundle.get("cards", []):
        lines.append(f"## {card.get('card_id', '')}")
        lines.append("")
        for rule in card.get("reverify_rules", []):
            lines.append(f"- {rule}")
        chain = card.get("expected_evidence_chain", {})
        lines.append(f"- canvas evidence: `{chain.get('canvas_evidence_path', '')}`")
        lines.append(f"- binding evidence: `{chain.get('binding_evidence_path', '')}`")
        lines.append("")
    return "\n".join(lines)


def verify_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    source_artifacts = bundle.get("source_artifacts", {})
    for key, path_text in source_artifacts.items():
        path = Path(path_text)
        checks.append({"name": f"exists:{key}", "ok": path.exists(), "detail": str(path.resolve())})
    for card in bundle.get("cards", []):
        expected = card.get("expected_contract", {})
        runtime = card.get("runtime_observation", {})
        chain = card.get("expected_evidence_chain", {})
        checks.append(
            {
                "name": f"contract:view_alignment:{card.get('card_id', '')}",
                "ok": bool(expected.get("view_name")) and bool(expected.get("source_view_id")) and bool(expected.get("table_id")),
                "detail": f"{expected.get('table_name', '')} / {expected.get('view_name', '')}",
            }
        )
        checks.append(
            {
                "name": f"evidence:repo_local:{card.get('card_id', '')}",
                "ok": all(Path(path_text).exists() for path_text in chain.values()),
                "detail": json.dumps(chain, ensure_ascii=False, sort_keys=True),
            }
        )
        checks.append(
            {
                "name": f"gap:runtime_selected_source_view_missing:{card.get('card_id', '')}",
                "ok": runtime.get("selected_source_view") in (None, ""),
                "detail": str(runtime.get("selected_source_view")),
            }
        )
        schema = card.get("schema_field_status", {})
        checks.append(
            {
                "name": f"schema:no_pending_fields:{card.get('card_id', '')}",
                "ok": not schema.get("has_pending_fields"),
                "detail": json.dumps(schema.get("schema_fields", []), ensure_ascii=False),
            }
        )
    status = "completed" if all(item.get("ok") for item in checks) else "failed_partial"
    return {
        "schema_version": "dashboard-runtime-gap-verify-v1",
        "status": status,
        "checks": checks,
    }


def write_bundle(context: BundleContext) -> dict[str, Any]:
    ensure_dir(context.output_dir)
    ensure_dir(context.output_dir / "support")
    ensure_dir(context.output_dir / "verify")
    bundle = build_bundle(context)
    bundle_json_path = context.output_dir / "dashboard-runtime-gap-bundle.json"
    bundle_md_path = context.output_dir / "dashboard-runtime-gap-bundle.md"
    checklist_path = context.output_dir / "support" / "runtime-reverify-checklist.md"
    verify_path = context.output_dir / "verify" / "verification-report.json"
    manifest_path = context.output_dir / "run-manifest.json"

    write_json(bundle_json_path, bundle)
    bundle_md_path.write_text(render_bundle_markdown(bundle), encoding="utf-8")
    checklist_path.write_text(render_support_checklist(bundle), encoding="utf-8")
    verification = verify_bundle(bundle)
    write_json(verify_path, verification)
    write_json(
        manifest_path,
        {
            "schema_version": "dashboard-runtime-gap-manifest-v1",
            "run_id": context.run_id,
            "created_at": context.created_at,
            "bundle_json": str(bundle_json_path.resolve()),
            "bundle_md": str(bundle_md_path.resolve()),
            "support_checklist": str(checklist_path.resolve()),
            "verify_report": str(verify_path.resolve()),
        },
    )
    return {
        "bundle": bundle,
        "verification": verification,
        "bundle_json_path": bundle_json_path,
        "bundle_md_path": bundle_md_path,
        "checklist_path": checklist_path,
        "verify_path": verify_path,
        "manifest_path": manifest_path,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate repo-local dashboard runtime gap bundle for support/verify.")
    parser.add_argument("--run-id", default="adagj-dashboard-runtime-gap-bundle-01", help="Stable run id.")
    parser.add_argument("--created-at", default="", help="Optional ISO datetime override.")
    parser.add_argument("--base-config", default=str(DEFAULT_BASE_CONFIG), help="Dashboard base config path.")
    parser.add_argument("--source-views", default=str(DEFAULT_SOURCE_VIEWS), help="Source views spec path.")
    parser.add_argument("--binding-run", default=str(DEFAULT_BINDING_RUN), help="Binding run json path.")
    parser.add_argument("--postcheck", default=str(DEFAULT_POSTCHECK), help="Post-check json path.")
    parser.add_argument("--runtime-output-root", default=str(DEFAULT_OUTPUT_ROOT), help="Runtime output root.")
    parser.add_argument("--output-dir", default="", help="Optional output dir override.")
    return parser


def resolve_context(args: argparse.Namespace) -> BundleContext:
    created_at = str(args.created_at or iso_now())
    created_dt = datetime.fromisoformat(created_at)
    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if str(args.output_dir or "").strip()
        else RUNS_ROOT / created_dt.strftime("%Y-%m-%d") / str(args.run_id or "adagj-dashboard-runtime-gap-bundle-01")
    )
    return BundleContext(
        run_id=str(args.run_id or "adagj-dashboard-runtime-gap-bundle-01"),
        created_at=created_at,
        output_dir=output_dir,
        base_config_path=Path(str(args.base_config)).expanduser().resolve(),
        source_views_path=Path(str(args.source_views)).expanduser().resolve(),
        binding_run_path=Path(str(args.binding_run)).expanduser().resolve(),
        postcheck_path=Path(str(args.postcheck)).expanduser().resolve(),
        runtime_output_root=Path(str(args.runtime_output_root)).expanduser().resolve(),
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    context = resolve_context(args)
    result = write_bundle(context)
    print(
        json.dumps(
            {
                "run_id": context.run_id,
                "output_dir": str(context.output_dir.resolve()),
                "verification_status": result["verification"]["status"],
                "bundle_json": str(result["bundle_json_path"].resolve()),
                "verify_report": str(result["verify_path"].resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
