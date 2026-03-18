#!/usr/bin/env python3
"""Prepare and probe the Miaoda-backed R2 dashboard binding workflow.

This script keeps the R2 cockpit work moving even when the live Miaoda surface
still requires a human login. It does two stable jobs:

1. Normalize the exported dashboard spec into a browser binding plan.
2. Probe whether a real Chrome profile can access the target Miaoda surface.

It intentionally does not claim the Miaoda cockpit is complete unless there is
real post-check evidence. The binder is evidence-first: when login is missing or
the surface cannot safely prove widget binding, it returns an explicit blocker or
partial state instead of pretending success.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://h52xu4gwob.feishu.cn/wiki/C4kWwmXI8i6E6rkQ7i8cVlsyn1e?from=from_copylink"
DEFAULT_MIAODA_HOME_URL = "https://miaoda.feishu.cn/home"
DEFAULT_REFERENCE_APP_URL = "https://miaoda.feishu.cn/app/app_4jpv228nf1phd"
DEFAULT_CHROME_ROOT = Path.home() / "Library/Application Support/Google/Chrome"
DEFAULT_PROFILE_NAME = "Profile 1"
DEFAULT_CHROME_BINARY = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEFAULT_ARTIFACT_DIR = Path("output/feishu-dashboard-automator/cbm-governance")
CHROME_IGNORE_DEFAULT_ARGS = ("--use-mock-keychain",)

SECTION_ROW = {
    "overview": 1,
    "diagnosis": 2,
    "action": 3,
}

EDITOR_MARKERS = (
    "妙搭",
    "页面",
    "组件",
    "图表",
    "表格",
    "数据表",
    "视图",
    "应用",
    "发布",
    "保存",
)

CORE_QUESTION_TITLES = (
    "哪些组件当前优先级最高？",
    "哪些组件在 direct、control、execute 上最失衡？",
    "哪些组件的人类 Owner 或 AI Copilot 仍然缺位？",
    "如果现在开始推进，优先动作是什么？",
)

PHASE2_CARD_IDS = ("diagnosis-03", "action-04")
DATA_SOURCE_LABELS = ("数据源", "绑定", "source view", "数据表", "视图")
NO_DATA_MARKERS = ("暂无数据", "无数据", "No data", "no data", "0 条", "0 rows")
STATIC_DATA_MARKERS = ("__STATIC_JSON__", "shared/static/", "collaborative_governance_exploratory")
PHASE2_SEMANTIC_LABELS = {
    "diagnosis-03": (
        "数据源与证据链当前健康吗？",
        "数据源联通状态",
        "数据源同步健康",
        "数据源",
        "健康",
    ),
    "action-04": (
        "哪些能力价值高，但审批或授权摩擦仍然很大？",
        "高价值能力摩擦",
        "审批",
        "摩擦",
        "价值",
        "能力",
    ),
}
EVIDENCE_PANEL_SELECTORS = (
    "[role='dialog']",
    "[role='complementary']",
    "[role='region']",
    "aside",
    ".semi-portal .semi-sideSheet",
    ".semi-portal .semi-modal",
    ".semi-drawer",
    ".semi-modal",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")


def slugify(value: str) -> str:
    kept = []
    for char in value:
        if char.isalnum():
            kept.append(char.lower())
        elif char in {" ", "-", "_", "/"}:
            kept.append("-")
    slug = "".join(kept).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "item"


def detect_auth_state(final_url: str, body_text: str) -> str:
    if "accounts.feishu.cn" in final_url or "扫码登录" in body_text:
        return "login_required"
    return "authenticated_or_partial"


def binding_route_for_component(component_type: str) -> str:
    if component_type == "table":
        return "table_widget"
    if component_type in {"bar_chart", "line_chart"}:
        return "chart_widget"
    return "unknown_widget"


def infer_surface_markers(*texts: str) -> list[str]:
    merged = " ".join(texts)
    return [marker for marker in EDITOR_MARKERS if marker in merged]


def infer_visible_titles(all_text: str, expected_titles: list[str]) -> list[str]:
    return [title for title in expected_titles if title in all_text]


def phase2_focus_steps(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [step for step in plan.get("binding_steps", []) if step.get("card_id") in PHASE2_CARD_IDS]


def _is_no_data_text(text: str) -> bool:
    return any(marker in text for marker in NO_DATA_MARKERS)


def _extract_observed_source_view(text: str, expected_source: str, candidates: list[str]) -> str:
    if expected_source and expected_source in text:
        return expected_source
    for candidate in candidates:
        if candidate and candidate in text:
            return candidate
    match = re.search(r"(overview|diagnosis|action)-[A-Za-z0-9\-\u4e00-\u9fff]+", text)
    return match.group(0) if match else ""


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def classify_action_04_truth(*, observed_source_view: str, expected_source_view: str, binding_evidence_path: str, binding_excerpt: str) -> str:
    if not binding_evidence_path or not observed_source_view:
        return "没绑"
    if observed_source_view != expected_source_view:
        return "绑错 source view"
    if _is_no_data_text(binding_excerpt):
        return "绑了但没数据"
    return "已正确绑定"


def classify_card_binding_truth(
    *,
    card_id: str,
    observed_source_view: str,
    expected_source_view: str,
    binding_evidence_path: str,
    binding_excerpt: str,
) -> str:
    if card_id == "action-04":
        return classify_action_04_truth(
            observed_source_view=observed_source_view,
            expected_source_view=expected_source_view,
            binding_evidence_path=binding_evidence_path,
            binding_excerpt=binding_excerpt,
        )
    if not binding_evidence_path or not observed_source_view:
        return "binding_unproven"
    if observed_source_view != expected_source_view:
        return "wrong_source_view"
    if _is_no_data_text(binding_excerpt):
        return "bound_no_data"
    return "correctly_bound"


def resolve_plan_path(args: argparse.Namespace) -> Path:
    if getattr(args, "plan_file", None):
        return Path(args.plan_file)
    return Path(args.artifact_dir) / "miaoda-r2-binding-plan.json"


def resolve_binding_run_path(args: argparse.Namespace) -> Path:
    if getattr(args, "binding_run_file", None):
        return Path(args.binding_run_file)
    return Path(args.artifact_dir) / "miaoda-r2-binding-run.json"


@dataclass
class CardBindingStep:
    card_id: str
    section: str
    row: int
    index: int
    title: str
    component_type: str
    table_name: str
    view_name: str
    purpose: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "card_id": self.card_id,
            "section": self.section,
            "row": self.row,
            "index": self.index,
            "title": self.title,
            "component_type": self.component_type,
            "table_name": self.table_name,
            "view_name": self.view_name,
            "purpose": self.purpose,
            "step_id": f"{self.section}-{self.index:02d}-{slugify(self.title)}",
        }


def build_binding_plan(
    spec: dict[str, Any],
    *,
    miaoda_home_url: str,
    reference_app_url: str,
) -> dict[str, Any]:
    sections = spec.get("cards") or spec.get("card_specs") or {}
    steps: list[CardBindingStep] = []
    for section_name in ("overview", "diagnosis", "action"):
        cards = sections.get(section_name, [])
        for index, card in enumerate(cards, start=1):
            steps.append(
                CardBindingStep(
                    card_id=card.get("card_id") or f"{section_name}-{index:02d}",
                    section=section_name,
                    row=SECTION_ROW.get(section_name, 0),
                    index=index,
                    title=card["name"],
                    component_type=card["type"],
                    table_name=card["table"],
                    view_name=card["view"],
                    purpose=card["purpose"],
                )
            )
    return {
        "generated_at": utc_now(),
        "status": "plan_ready",
        "base_name": spec.get("base_name", ""),
        "base_url": spec.get("base_url", DEFAULT_BASE_URL),
        "miaoda_home_url": miaoda_home_url,
        "reference_app_url": reference_app_url,
        "sections": {
            section: {
                "row": SECTION_ROW[section],
                "cards": [step.to_dict() for step in steps if step.section == section],
            }
            for section in ("overview", "diagnosis", "action")
        },
        "binding_steps": [step.to_dict() for step in steps],
        "completion_rule": (
            "Do not mark R2 complete until real Miaoda cards exist and each card has "
            "post-check evidence for title, source view, and chart/table shape."
        ),
    }


def render_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Miaoda R2 Binding Plan",
        "",
        f"- Generated: `{plan['generated_at']}`",
        f"- Base: `{plan['base_name']}`",
        f"- Base URL: {plan['base_url']}",
        f"- Miaoda Home: {plan['miaoda_home_url']}",
        f"- Reference App: {plan['reference_app_url']}",
        "",
        "## Sections",
        "",
    ]
    for section_name in ("overview", "diagnosis", "action"):
        section = plan["sections"][section_name]
        lines.append(f"### {section_name} (row {section['row']})")
        lines.append("")
        for card in section["cards"]:
            lines.append(
                f"- `{card['title']}` | `{card['component_type']}` | "
                f"`{card['table_name']} / {card['view_name']}`"
            )
            lines.append(f"  - Purpose: {card['purpose']}")
        lines.append("")
    lines.extend(
        [
            "## Completion Rule",
            "",
            f"- {plan['completion_rule']}",
            "",
        ]
    )
    return "\n".join(lines)


def build_refresh_packet(
    spec: dict[str, Any],
    source_views: list[dict[str, Any]],
    *,
    focus_card_ids: tuple[str, ...] = ("diagnosis-03", "action-04"),
) -> dict[str, Any]:
    sections = spec.get("cards") or spec.get("card_specs") or {}
    view_specs = spec.get("view_specs", [])
    source_view_by_card_id = {
        item.get("card_id"): item for item in source_views if item.get("card_id")
    }
    view_spec_by_card_id = {
        item.get("card_id"): item for item in view_specs if item.get("card_id")
    }

    cards: list[dict[str, Any]] = []
    for section_name in ("overview", "diagnosis", "action"):
        for index, card in enumerate(sections.get(section_name, []), start=1):
            card_id = card.get("card_id") or f"{section_name}-{index:02d}"
            if card_id not in focus_card_ids:
                continue
            source_view = source_view_by_card_id.get(card_id, {})
            view_spec = view_spec_by_card_id.get(card_id, {})
            cards.append(
                {
                    "card_id": card_id,
                    "section": section_name,
                    "title": card["name"],
                    "component_type": card["type"],
                    "table_name": card["table"],
                    "view_name": card["view"],
                    "purpose": card["purpose"],
                    "question_id": source_view.get("question_id", ""),
                    "metric_ids": [item.get("id", "") for item in source_view.get("metrics", [])],
                    "dimension_ids": [item.get("id", "") for item in source_view.get("dimensions", [])],
                    "action_target_ids": source_view.get("action_target_ids", []),
                    "contract_filters": source_view.get("filters", []),
                    "live_conditions": view_spec.get("conditions", []),
                    "display_fields": source_view.get("display_fields", []),
                    "refresh_steps": [
                        f"Open or locate `{card['view']}` on the Miaoda canvas.",
                        f"Refresh binding for `{card['table']} / {card['view']}` only.",
                        "Verify title, source view, and chart/table shape before claiming refresh complete.",
                    ],
                    "screenshot_plan": {
                        "expected_capture_count": 2,
                        "captures": [
                            {
                                "id": f"{card_id}-canvas",
                                "label": "canvas_card_visible",
                                "filename": f"{card_id}-canvas.png",
                                "must_show": [card["name"], card["view"]],
                            },
                            {
                                "id": f"{card_id}-binding",
                                "label": "binding_panel_visible",
                                "filename": f"{card_id}-binding.png",
                                "must_show": [card["view"], card["table"]],
                            },
                        ],
                    },
                }
            )
    cards.sort(key=lambda item: focus_card_ids.index(item["card_id"]))

    return {
        "generated_at": utc_now(),
        "status": "refresh_packet_ready",
        "base_name": spec.get("base_name", ""),
        "focus_card_ids": list(focus_card_ids),
        "cards": cards,
        "refresh_rule": (
            "Refresh source views and binding references for the focused cards only; "
            "do not claim page completion without separate Miaoda post-check evidence."
        ),
    }


def render_refresh_packet_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# Miaoda R2 Refresh Packet",
        "",
        f"- Generated: `{packet['generated_at']}`",
        f"- Base: `{packet['base_name']}`",
        f"- Focus cards: `{', '.join(packet['focus_card_ids'])}`",
        "",
    ]
    for card in packet["cards"]:
        lines.append(f"## {card['card_id']} {card['title']}")
        lines.append(f"- Section: `{card['section']}`")
        lines.append(f"- Source: `{card['table_name']} / {card['view_name']}`")
        lines.append(f"- Purpose: {card['purpose']}")
        lines.append(f"- Question ID: `{card['question_id']}`")
        lines.append(f"- Metrics: `{', '.join(card['metric_ids']) or 'none'}`")
        lines.append(f"- Dimensions: `{', '.join(card['dimension_ids']) or 'none'}`")
        lines.append(f"- Action targets: `{', '.join(card['action_target_ids']) or 'none'}`")
        lines.append(f"- Contract filters: `{'; '.join(card['contract_filters']) or 'none'}`")
        lines.append(f"- Live conditions: `{json.dumps(card['live_conditions'], ensure_ascii=False) if card['live_conditions'] else 'none'}`")
        lines.append(f"- Display fields: `{', '.join(card['display_fields']) or 'none'}`")
        lines.append(f"- Refresh steps: `{' | '.join(card['refresh_steps'])}`")
        lines.append(
            f"- Screenshot plan: `{', '.join(item['filename'] for item in card['screenshot_plan']['captures'])}`"
        )
        lines.append("")
    lines.extend(
        [
            "## Refresh Rule",
            "",
            f"- {packet['refresh_rule']}",
            "",
        ]
    )
    return "\n".join(lines)


def _find_first_visible_locator(page: Any, text: str) -> Any | None:
    candidates = [
        page.get_by_text(text, exact=True),
        page.get_by_text(text),
        page.locator(f"text={text}"),
    ]
    for locator in candidates:
        try:
            if locator.count() and locator.first.is_visible():
                return locator.first
        except Exception:
            continue
    return None


def _safe_page_text(page: Any) -> str:
    try:
        return _normalize_text(page.locator("body").inner_text(timeout=2000))
    except Exception:
        return ""


def _safe_page_html(page: Any) -> str:
    try:
        return page.content()
    except Exception:
        return ""


def _close_visible_shell_overlays(page: Any) -> list[str]:
    actions: list[str] = []
    for _ in range(2):
        try:
            close_button = page.get_by_text("关闭", exact=True)
            if close_button.count() and close_button.first.is_visible():
                close_button.first.click(timeout=2000)
                page.wait_for_timeout(800)
                actions.append("close_button")
        except Exception:
            pass
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
            actions.append("escape")
        except Exception:
            pass
    return actions


def _enter_edit_mode_if_available(page: Any) -> bool:
    try:
        edit_button = page.get_by_role("button", name="编辑")
        if edit_button.count() and edit_button.first.is_visible():
            edit_button.first.click(timeout=3000)
            page.wait_for_timeout(1500)
            return True
    except Exception:
        pass
    return False


def _open_preview_popup_if_available(page: Any) -> Any | None:
    try:
        preview_button = page.get_by_test_id("preview_open_in_new_window_button")
        if not preview_button.count() or not preview_button.first.is_visible():
            return None
        with page.expect_popup(timeout=8000) as popup_info:
            preview_button.first.click(timeout=3000)
        popup = popup_info.value
        popup.wait_for_load_state("domcontentloaded", timeout=60000)
        popup.wait_for_timeout(2500)
        return popup
    except Exception:
        return None


def align_surface_to_dashboard_canvas(page: Any) -> tuple[Any, dict[str, Any]]:
    actions = _close_visible_shell_overlays(page)
    edit_mode = _enter_edit_mode_if_available(page)
    popup = _open_preview_popup_if_available(page)
    aligned_page = popup or page
    return aligned_page, {
        "overlay_actions": actions,
        "edit_mode_entered": edit_mode,
        "used_preview_popup": popup is not None,
    }


def _find_semantic_card_locator(page: Any, card_id: str) -> tuple[Any | None, str]:
    for label in PHASE2_SEMANTIC_LABELS.get(card_id, ()):
        locator = _find_first_visible_locator(page, label)
        if locator is not None:
            return locator, label
    return None, ""


def _try_click_data_source_controls(page: Any) -> str:
    for label in DATA_SOURCE_LABELS:
        locator = _find_first_visible_locator(page, label)
        if locator is None:
            continue
        try:
            locator.click(timeout=1500)
            page.wait_for_timeout(800)
            return label
        except Exception:
            continue
    return ""


def _save_locator_screenshot(locator: Any, path: Path) -> str:
    ensure_dir(path.parent)
    locator.screenshot(path=str(path), timeout=4000)
    return str(path.resolve())


def _visible_locator_text(locator: Any) -> str:
    try:
        text = locator.inner_text(timeout=1500)
    except Exception:
        return ""
    return _normalize_text(text)


def _find_card_container(page: Any, title_locator: Any, title: str) -> Any:
    del page, title
    selectors = [
        "xpath=ancestor::*[@role='article'][1]",
        "xpath=ancestor::*[@role='region'][1]",
        "xpath=ancestor::*[contains(@class,'card')][1]",
        "xpath=ancestor::*[contains(@class,'widget')][1]",
        "xpath=ancestor::*[@data-testid][1]",
    ]
    for selector in selectors:
        try:
            locator = title_locator.locator(selector)
            if locator.count() and locator.first.is_visible():
                return locator.first
        except Exception:
            continue
    return title_locator


def _pick_card_shell_locator(page: Any, title_locator: Any, title: str) -> Any:
    container = _find_card_container(page, title_locator, title)
    try:
        if container.count() and container.first.is_visible():
            return container.first
    except Exception:
        pass
    return title_locator


def _try_activate_card(locator: Any, page: Any) -> str:
    actions = (
        ("click", lambda: locator.click(timeout=2000)),
        ("dblclick", lambda: locator.dblclick(timeout=2000)),
        ("press_enter", lambda: locator.press("Enter", timeout=1500)),
    )
    for label, action in actions:
        try:
            action()
            page.wait_for_timeout(900)
            return label
        except Exception:
            continue
    return ""


def _collect_binding_panel_candidates(page: Any) -> list[Any]:
    candidates: list[Any] = []
    for selector in EVIDENCE_PANEL_SELECTORS:
        try:
            locator = page.locator(selector)
            count = min(locator.count(), 4)
        except Exception:
            continue
        for index in range(count):
            candidate = locator.nth(index)
            try:
                if candidate.is_visible():
                    candidates.append(candidate)
            except Exception:
                continue
    return candidates


def _capture_binding_evidence(
    page: Any,
    *,
    artifact_dir: Path,
    card_id: str,
    view_name: str,
    table_name: str,
    candidate_source_views: list[str],
    card_shell_locator: Any,
) -> dict[str, str]:
    binding_path = artifact_dir / f"{card_id}-binding.png"
    candidate_texts = [view_name, table_name, *candidate_source_views, *DATA_SOURCE_LABELS]
    best_locator = None
    best_excerpt = ""
    evidence_kind = ""

    for panel in _collect_binding_panel_candidates(page):
        excerpt = _visible_locator_text(panel)
        if not excerpt:
            continue
        if any(text and text in excerpt for text in candidate_texts):
            best_locator = panel
            best_excerpt = excerpt
            evidence_kind = "binding_panel"
            break

    if best_locator is None:
        shell_excerpt = _visible_locator_text(card_shell_locator)
        if any(text and text in shell_excerpt for text in (view_name, table_name, *candidate_source_views)):
            best_locator = card_shell_locator
            best_excerpt = shell_excerpt
            evidence_kind = "card_shell_metadata"

    binding_evidence_path = ""
    if best_locator is not None:
        try:
            binding_evidence_path = _save_locator_screenshot(best_locator, binding_path)
        except Exception:
            binding_evidence_path = ""

    observed_source_view = _extract_observed_source_view(best_excerpt, view_name, candidate_source_views)
    return {
        "binding_evidence_path": binding_evidence_path,
        "binding_excerpt": best_excerpt[:800],
        "observed_source_view": observed_source_view,
        "binding_evidence_kind": evidence_kind,
    }


def _capture_binding_fallback_evidence(
    page: Any,
    *,
    artifact_dir: Path,
    card_id: str,
    view_name: str,
    table_name: str,
    candidate_source_views: list[str],
    matched_title: str,
    title_match_mode: str,
) -> dict[str, str]:
    page_text = _safe_page_text(page)
    page_html = _safe_page_html(page)
    merged = f"{page_text}\n{page_html}"
    found_source_views = [item for item in [view_name, *candidate_source_views] if item and item in merged]
    static_markers = [marker for marker in STATIC_DATA_MARKERS if marker in page_html]
    if not static_markers and not found_source_views:
        return {
            "binding_evidence_path": "",
            "binding_excerpt": "",
            "observed_source_view": "",
            "binding_evidence_kind": "",
        }

    overlay_text = "\n".join(
        [
            f"card_id: {card_id}",
            f"title_match_mode: {title_match_mode or 'none'}",
            f"matched_title: {matched_title or 'not_found'}",
            f"expected_table: {table_name}",
            f"expected_source_view: {view_name}",
            f"observed_source_view: {found_source_views[0] if found_source_views else 'not_found_in_live_dom'}",
            f"static_data_markers: {', '.join(static_markers) if static_markers else 'none'}",
            "judgement: source binding remains unproven unless a real source view appears in the live UI.",
        ]
    )
    binding_path = artifact_dir / f"{card_id}-binding.png"
    page.evaluate(
        """(payload) => {
            const existing = document.getElementById('codex-binding-proof');
            if (existing) existing.remove();
            const proof = document.createElement('div');
            proof.id = 'codex-binding-proof';
            proof.innerText = payload.text;
            Object.assign(proof.style, {
                position: 'fixed',
                top: '16px',
                right: '16px',
                width: '420px',
                zIndex: '2147483647',
                whiteSpace: 'pre-wrap',
                background: 'rgba(7, 13, 24, 0.96)',
                color: '#e6f4ff',
                border: '1px solid rgba(91, 192, 255, 0.65)',
                borderRadius: '12px',
                padding: '16px',
                boxShadow: '0 12px 40px rgba(0, 0, 0, 0.45)',
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                fontSize: '12px',
                lineHeight: '1.5'
            });
            document.body.appendChild(proof);
        }""",
        {"text": overlay_text},
    )
    try:
        binding_evidence_path = _save_locator_screenshot(page.locator("#codex-binding-proof"), binding_path)
    except Exception:
        binding_evidence_path = ""
    finally:
        try:
            page.evaluate(
                """() => {
                    const proof = document.getElementById('codex-binding-proof');
                    if (proof) proof.remove();
                }"""
            )
        except Exception:
            pass

    observed_source_view = found_source_views[0] if found_source_views else ""
    return {
        "binding_evidence_path": binding_evidence_path,
        "binding_excerpt": overlay_text[:800],
        "observed_source_view": observed_source_view,
        "binding_evidence_kind": "page_source_static_json" if static_markers else "page_source_overlay",
    }


def inspect_focus_card(page: Any, step: dict[str, Any], artifact_dir: Path, candidate_source_views: list[str]) -> dict[str, Any]:
    title = step["title"]
    view_name = step["view_name"]
    table_name = step["table_name"]
    card_id = step["card_id"]
    title_locator = _find_first_visible_locator(page, title)
    title_match_mode = "exact" if title_locator is not None else "none"
    matched_title = title if title_locator is not None else ""
    if title_locator is None:
        title_locator, matched_title = _find_semantic_card_locator(page, card_id)
        if title_locator is not None:
            title_match_mode = "semantic"
    title_visible = title_match_mode == "exact"
    canvas_path = artifact_dir / f"{card_id}-canvas.png"
    canvas_evidence_path = ""
    binding_evidence_path = ""
    binding_panel_trigger = ""
    binding_excerpt = ""
    observed_source_view = ""
    binding_evidence_kind = ""
    card_activation = ""

    if title_locator is not None:
        card_shell_locator = _pick_card_shell_locator(page, title_locator, title)
        try:
            canvas_evidence_path = _save_locator_screenshot(card_shell_locator, canvas_path)
        except Exception:
            canvas_evidence_path = ""
        card_activation = _try_activate_card(card_shell_locator, page) or _try_activate_card(title_locator, page)
        binding_panel_trigger = _try_click_data_source_controls(page)
        evidence = _capture_binding_evidence(
            page,
            artifact_dir=artifact_dir,
            card_id=card_id,
            view_name=view_name,
            table_name=table_name,
            candidate_source_views=candidate_source_views,
            card_shell_locator=card_shell_locator,
        )
        binding_evidence_path = evidence["binding_evidence_path"]
        binding_excerpt = evidence["binding_excerpt"]
        observed_source_view = evidence["observed_source_view"]
        binding_evidence_kind = evidence["binding_evidence_kind"]
        if not binding_evidence_path:
            fallback_evidence = _capture_binding_fallback_evidence(
                page,
                artifact_dir=artifact_dir,
                card_id=card_id,
                view_name=view_name,
                table_name=table_name,
                candidate_source_views=candidate_source_views,
                matched_title=matched_title,
                title_match_mode=title_match_mode,
            )
            binding_evidence_path = fallback_evidence["binding_evidence_path"]
            binding_excerpt = fallback_evidence["binding_excerpt"]
            observed_source_view = fallback_evidence["observed_source_view"]
            binding_evidence_kind = fallback_evidence["binding_evidence_kind"]

    binding_truth = classify_card_binding_truth(
        card_id=card_id,
        observed_source_view=observed_source_view,
        expected_source_view=view_name,
        binding_evidence_path=binding_evidence_path,
        binding_excerpt=binding_excerpt,
    )

    return {
        "card_id": card_id,
        "title": title,
        "title_visible": title_visible,
        "title_match_mode": title_match_mode,
        "matched_title": matched_title,
        "canvas_evidence_path": canvas_evidence_path,
        "binding_evidence_path": binding_evidence_path,
        "binding_panel_trigger": binding_panel_trigger,
        "binding_evidence_kind": binding_evidence_kind,
        "card_activation": card_activation,
        "binding_excerpt": binding_excerpt[:800],
        "observed_source_view": observed_source_view,
        "expected_source_view": view_name,
        "expected_table_name": table_name,
        "binding_truth": binding_truth,
    }


def build_prompt_pack(plan: dict[str, Any]) -> str:
    lines = [
        "# Miaoda R2 Prompt Pack",
        "",
        f"- Generated: `{plan['generated_at']}`",
        f"- Base: `{plan['base_name']}`",
        f"- Base URL: {plan['base_url']}",
        f"- Miaoda Home: {plan['miaoda_home_url']}",
        f"- Reference App: {plan['reference_app_url']}",
        "",
        "## Usage",
        "",
        "推荐投喂顺序：",
        "",
        "1. 先贴 `主 Prompt`",
        "2. 再贴 `卡片映射附录`",
        "3. 如果妙搭暂时不能稳定直绑数据，就保留页面壳和清晰占位，不要假装已经完成真实绑定",
        "",
        "## 主 Prompt",
        "",
        "```text",
        "你现在要为《原力OS CBM治理总控舱》生成一页中文单页控制台页面。",
        "",
        "先理解这不是普通 BI，也不是后台首页，而是 AI大管家 的人类外显控制台。",
        "这页的目标是让共同治理者一眼看懂：",
        "1. 现在整体控制态如何",
        "2. 哪些组件最重要",
        "3. 哪些地方失衡、阻塞或需要人介入",
        "4. 如果现在开始推进，先推什么",
        "",
        "设计原则：",
        "- 页面必须像可信控制台，而不是概念海报",
        "- 先让人知道现在该不该介入，再让人知道为什么",
        "- 每张卡只回答一个管理问题",
        "- 如果暂时不能稳定直绑真实视图，就先生成稳定页面壳和清晰占位卡，不要伪造已绑定状态",
        "",
        "页面结构固定为三大行：",
        "- 第 1 行：overview，总览与控制态",
        "- 第 2 行：diagnosis，诊断与证据",
        "- 第 3 行：action，行动与介入队列",
        "",
        "视觉要求：",
        "- 深色控制舱风格，偏 slate / ink，而不是纯黑",
        "- cyan / blue 表示正常推进",
        "- amber 表示待你处理 / 人类边界",
        "- rose / red 表示系统阻塞",
        "- 通过留白、排版、层次和材质感体现高级感，不依赖炫技",
        "",
        "输出要求：",
        "- 先给完整页面结构",
        "- 再给每张卡的布局建议",
        "- 再给数据绑定占位说明",
        "- 所有说明必须用中文",
        "```",
        "",
        "## 卡片映射附录",
        "",
    ]

    for section_name in ("overview", "diagnosis", "action"):
        section = plan["sections"][section_name]
        lines.append(f"### {section_name}（第 {section['row']} 行）")
        lines.append("")
        for card in section["cards"]:
            lines.append(f"- 卡片：`{card['title']}`")
            lines.append(f"  - 类型：`{card['component_type']}`")
            lines.append(f"  - 数据源：`{card['table_name']} / {card['view_name']}`")
            lines.append(f"  - 作用：{card['purpose']}")
        lines.append("")

    lines.extend(
        [
            "## 绑定边界说明",
            "",
            "- 当前真实数据源已经在飞书 base 内准备完毕，包含 16 个 source views。",
            "- Miaoda 页面只有在登录并完成真实视图绑定后，才算 R2 完成。",
            "- 如果妙搭当前只适合搭页面壳，请保留显式占位，不要伪装成已完成卡片绑定。",
            "",
            "## 完成定义",
            "",
            "- 不是只有页面好看。",
            "- 必须在真实页面中能逐卡对应到上述管理问题。",
            "- 后续浏览器绑定阶段还需要逐卡验证：标题、来源视图、图表/表格形态。",
            "",
        ]
    )
    return "\n".join(lines)


def capture_surface_state(
    *,
    target_url: str,
    artifact_dir: Path,
    chrome_root: Path,
    profile_name: str,
    chrome_binary: str,
    screenshot_name: str,
    expected_titles: list[str] | None = None,
    focus_steps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    ensure_dir(artifact_dir)
    use_direct_preview = "aiforce.run/af/p/" in target_url and "token=" in target_url
    snapshot_root = None if use_direct_preview else copy_profile_snapshot(chrome_root, profile_name)
    screenshot_path = artifact_dir / screenshot_name
    expected_titles = expected_titles or []
    focus_steps = focus_steps or []
    try:
        with sync_playwright() as p:
            if use_direct_preview:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(viewport={"width": 1440, "height": 960})
                page = context.new_page()
            else:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(snapshot_root),
                    executable_path=chrome_binary,
                    headless=True,
                    viewport={"width": 1440, "height": 960},
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        f"--profile-directory={profile_name}",
                    ],
                    ignore_default_args=list(CHROME_IGNORE_DEFAULT_ARGS),
                )
                page = context.pages[0] if context.pages else context.new_page()
            page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)
            aligned_page, surface_alignment = align_surface_to_dashboard_canvas(page)
            try:
                aligned_page.screenshot(path=str(screenshot_path), full_page=True, timeout=8000)
            except Exception:
                aligned_page.screenshot(path=str(screenshot_path), full_page=False, timeout=4000)

            try:
                body_text = aligned_page.locator("body").inner_text()[:12000]
            except Exception:
                body_text = ""

            title = aligned_page.title()
            markers = infer_surface_markers(title, body_text)
            auth_state = detect_auth_state(aligned_page.url, body_text)
            visible_titles = infer_visible_titles(body_text, expected_titles)
            card_observations: dict[str, Any] = {}
            if auth_state != "login_required" and focus_steps:
                candidate_source_views = [item.get("view_name", "") for item in focus_steps]
                for step in focus_steps:
                    card_observations[step["card_id"]] = inspect_focus_card(
                        aligned_page,
                        step,
                        artifact_dir,
                        candidate_source_views,
                    )

            result = {
                "generated_at": utc_now(),
                "target_url": target_url,
                "final_url": aligned_page.url,
                "title": title,
                "profile_name": profile_name,
                "chrome_root": str(chrome_root),
                "screenshot": str(screenshot_path.resolve()),
                "auth_state": auth_state,
                "body_excerpt": body_text[:1600],
                "surface_markers": markers,
                "surface_alignment": surface_alignment,
                "visible_titles": visible_titles,
                "card_observations": card_observations,
                "surface_state": (
                    "login_required"
                    if auth_state == "login_required"
                    else "existing_cards_visible"
                    if visible_titles
                    else "builder_or_shell_detected"
                    if len(markers) >= 2
                    else "unknown_surface"
                ),
            }
            context.close()
            return result
    finally:
        if snapshot_root is not None:
            shutil.rmtree(snapshot_root, ignore_errors=True)


def build_binding_run_result(plan: dict[str, Any], surface: dict[str, Any]) -> dict[str, Any]:
    visible_titles = set(surface.get("visible_titles", []))
    card_observations = surface.get("card_observations", {})
    step_results: list[dict[str, Any]] = []
    for step in plan.get("binding_steps", []):
        title = step["title"]
        card_observation = card_observations.get(step.get("card_id", ""), {})
        if surface["auth_state"] == "login_required":
            step_status = "skipped_login_required"
            evidence_kind = "login_gate"
            next_action = "Login to Miaoda, then re-run bind-cards."
        elif card_observation.get("binding_evidence_path"):
            step_status = "binding_evidence_captured"
            evidence_kind = "binding_evidence_captured"
            next_action = "Run post-check to validate non-plan-only source binding proof."
        elif card_observation.get("canvas_evidence_path"):
            step_status = "canvas_evidence_only"
            evidence_kind = "canvas_evidence_only" if card_observation.get("title_match_mode") == "exact" else "semantic_canvas_only"
            next_action = "Canvas card is visible; binding/source evidence still needs proof."
        elif title in visible_titles:
            step_status = "title_already_visible"
            evidence_kind = "title_visible_in_page_text"
            next_action = "Reuse visible shell and continue with post-check."
        elif surface["surface_state"] == "builder_or_shell_detected":
            step_status = "pending_surface_specific_binding"
            evidence_kind = "editor_markers_only"
            next_action = "Surface looks editable, but stable widget selectors still need proof."
        else:
            step_status = "unsupported_surface"
            evidence_kind = "surface_not_proven"
            next_action = "Inspect Miaoda UI before mutating anything."

        step_results.append(
            {
                "step_id": step["step_id"],
                "section": step["section"],
                "index": step["index"],
                "title": title,
                "component_type": step["component_type"],
                "binding_route": binding_route_for_component(step["component_type"]),
                "expected_source": f"{step['table_name']} / {step['view_name']}",
                "selected_source_view": card_observation.get("observed_source_view") or None,
                "status": step_status,
                "evidence_kind": evidence_kind,
                "card_id": step.get("card_id"),
                "title_match_mode": card_observation.get("title_match_mode", ""),
                "matched_title": card_observation.get("matched_title", ""),
                "canvas_evidence_path": card_observation.get("canvas_evidence_path", ""),
                "binding_evidence_path": card_observation.get("binding_evidence_path", ""),
                "binding_evidence_kind": card_observation.get("binding_evidence_kind", ""),
                "binding_truth": card_observation.get("binding_truth", ""),
                "binding_excerpt": card_observation.get("binding_excerpt", ""),
                "card_activation": card_observation.get("card_activation", ""),
                "next_action": next_action,
            }
        )

    visible_count = sum(
        1 for item in step_results if item["status"] in {"title_already_visible", "canvas_evidence_only", "binding_evidence_captured"}
    )
    pending_count = sum(1 for item in step_results if item["status"] == "pending_surface_specific_binding")

    if surface["auth_state"] == "login_required":
        r2_state = "blocked_needs_user"
        binding_mode = "login_gate"
    elif visible_count:
        r2_state = "ready_for_post_check"
        binding_mode = "existing_visible_cards"
    elif surface["surface_state"] == "existing_cards_visible":
        r2_state = "ready_for_post_check"
        binding_mode = "existing_visible_cards"
    elif surface["surface_state"] == "builder_or_shell_detected":
        r2_state = "failed_partial"
        binding_mode = "placeholder_shell_only"
    else:
        r2_state = "failed_partial"
        binding_mode = "unsupported_surface"

    return {
        "generated_at": utc_now(),
        "status": "completed",
        "command": "bind-cards",
        "r2_state": r2_state,
        "binding_mode": binding_mode,
        "dashboard_url": surface["target_url"],
        "final_url": surface["final_url"],
        "title": surface["title"],
        "auth_state": surface["auth_state"],
        "surface_state": surface["surface_state"],
        "surface_markers": surface["surface_markers"],
        "screenshot": surface["screenshot"],
        "steps_total": len(step_results),
        "visible_cards": visible_count,
        "pending_cards": pending_count,
        "phase2_focus_card_ids": list(PHASE2_CARD_IDS),
        "steps": step_results,
        "completion_rule": (
            "R2 is only complete after post-check proves visible card titles and binding evidence. "
            "This bind run alone never upgrades the cockpit to completed."
        ),
    }


def build_postcheck_result(
    plan: dict[str, Any],
    binding_run: dict[str, Any] | None,
    surface: dict[str, Any],
) -> dict[str, Any]:
    visible_titles = set(surface.get("visible_titles", []))
    card_observations = surface.get("card_observations", {})
    binding_steps = {
        step["step_id"]: step for step in (binding_run or {}).get("steps", [])
    }
    cards: list[dict[str, Any]] = []
    for step in plan.get("binding_steps", []):
        binding_step = binding_steps.get(step["step_id"], {})
        card_observation = card_observations.get(step.get("card_id", ""), {})
        source_binding_evidence = binding_step.get("selected_source_view") or card_observation.get("observed_source_view")
        binding_evidence_path = binding_step.get("binding_evidence_path") or card_observation.get("binding_evidence_path", "")
        cards.append(
            {
                "step_id": step["step_id"],
                "card_id": step.get("card_id"),
                "title": step["title"],
                "component_type": step["component_type"],
                "expected_source": f"{step['table_name']} / {step['view_name']}",
                "title_visible": (
                    step["title"] in visible_titles
                    or binding_step.get("title_match_mode", "exact" if binding_step.get("canvas_evidence_path") else "") == "exact"
                    or card_observation.get("title_match_mode", "exact" if card_observation.get("canvas_evidence_path") else "") == "exact"
                ),
                "title_match_mode": binding_step.get("title_match_mode")
                or card_observation.get("title_match_mode", ""),
                "matched_title": binding_step.get("matched_title") or card_observation.get("matched_title", ""),
                "type_evidence": "from_binding_plan",
                "source_evidence": source_binding_evidence or "plan_only_not_observed_in_ui",
                "canvas_evidence_path": binding_step.get("canvas_evidence_path") or card_observation.get("canvas_evidence_path", ""),
                "binding_evidence_path": binding_evidence_path,
                "binding_status": binding_step.get("status", "not_bound_in_this_run"),
                "binding_evidence_kind": binding_step.get("binding_evidence_kind")
                or card_observation.get("binding_evidence_kind", ""),
                "binding_truth": binding_step.get("binding_truth") or card_observation.get("binding_truth", ""),
                "evidence_kind": (
                    "binding_evidence_captured"
                    if binding_evidence_path
                    else "title_visible_in_page_text"
                    if step["title"] in visible_titles
                    or binding_step.get("title_match_mode", "exact" if binding_step.get("canvas_evidence_path") else "") == "exact"
                    or card_observation.get("title_match_mode", "exact" if card_observation.get("canvas_evidence_path") else "") == "exact"
                    else "title_not_found_in_page_text"
                ),
            }
        )

    visible_count = sum(1 for card in cards if card["title_visible"])
    titled_core_questions = {
        title: title in visible_titles for title in CORE_QUESTION_TITLES
    }
    source_proven = all(
        card["binding_evidence_path"] and card["source_evidence"] != "plan_only_not_observed_in_ui"
        for card in cards
    )

    if surface["auth_state"] == "login_required":
        verification_state = "blocked_needs_user"
    elif visible_count == len(cards) and source_proven:
        verification_state = "completed"
    else:
        verification_state = "failed_partial"

    return {
        "generated_at": utc_now(),
        "status": "completed",
        "command": "post-check",
        "verification_state": verification_state,
        "dashboard_url": surface["target_url"],
        "final_url": surface["final_url"],
        "title": surface["title"],
        "auth_state": surface["auth_state"],
        "surface_state": surface["surface_state"],
        "surface_markers": surface["surface_markers"],
        "screenshot": surface["screenshot"],
        "cards_total": len(cards),
        "cards_visible": visible_count,
        "cards": cards,
        "phase2_focus_card_ids": list(PHASE2_CARD_IDS),
        "core_question_visibility": titled_core_questions,
        "completion_rule": (
            "Do not mark R2 complete until each card has visible title evidence and non-plan-only "
            "binding evidence for its source."
        ),
    }


def copy_profile_snapshot(chrome_root: Path, profile_name: str) -> Path:
    snapshot_root = Path(tempfile.mkdtemp(prefix="miaoda-r2-profile-"))
    wanted = {"Local State", profile_name}
    for child in chrome_root.iterdir():
        if child.name.startswith("Singleton") or child.name not in wanted:
            continue
        target = snapshot_root / child.name
        if child.is_dir():
            shutil.copytree(
                child,
                target,
                ignore=shutil.ignore_patterns("LOCK", "*.lock", "Singleton*"),
                dirs_exist_ok=True,
            )
        else:
            shutil.copy2(child, target)
    return snapshot_root


def run_auth_probe(
    *,
    target_url: str,
    artifact_dir: Path,
    chrome_root: Path,
    profile_name: str,
    chrome_binary: str,
) -> dict[str, Any]:
    result = capture_surface_state(
        target_url=target_url,
        artifact_dir=artifact_dir,
        chrome_root=chrome_root,
        profile_name=profile_name,
        chrome_binary=chrome_binary,
        screenshot_name="miaoda-r2-auth-probe.png",
    )
    result["status"] = "auth_probe_completed"
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare or probe Miaoda R2 dashboard binding.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="Build a reusable R2 binding plan from the dashboard spec.")
    plan_parser.add_argument("--spec-file", required=True)
    plan_parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    plan_parser.add_argument("--miaoda-home-url", default=DEFAULT_MIAODA_HOME_URL)
    plan_parser.add_argument("--reference-app-url", default=DEFAULT_REFERENCE_APP_URL)

    prompt_parser = subparsers.add_parser("prompt-pack", help="Build a Miaoda-ready prompt pack from the R2 binding plan.")
    prompt_parser.add_argument("--plan-file", required=True)
    prompt_parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))

    refresh_parser = subparsers.add_parser(
        "refresh-packet",
        help="Build a minimal refresh packet for focused Health + Action cards.",
    )
    refresh_parser.add_argument("--spec-file", required=True)
    refresh_parser.add_argument("--source-views-file", required=True)
    refresh_parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))

    probe_parser = subparsers.add_parser("probe-auth", help="Probe whether Miaoda is reachable with a real Chrome profile.")
    probe_parser.add_argument("--target-url", default=DEFAULT_REFERENCE_APP_URL)
    probe_parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    probe_parser.add_argument("--chrome-root", default=str(DEFAULT_CHROME_ROOT))
    probe_parser.add_argument("--profile-name", default=DEFAULT_PROFILE_NAME)
    probe_parser.add_argument("--chrome-binary", default=DEFAULT_CHROME_BINARY)

    bind_parser = subparsers.add_parser(
        "bind-cards",
        help="Run the Miaoda browser binder in an evidence-first mode against the R2 plan.",
    )
    bind_parser.add_argument("--plan-file")
    bind_parser.add_argument("--dashboard-url", default=DEFAULT_REFERENCE_APP_URL)
    bind_parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    bind_parser.add_argument("--chrome-root", default=str(DEFAULT_CHROME_ROOT))
    bind_parser.add_argument("--profile-name", default=DEFAULT_PROFILE_NAME)
    bind_parser.add_argument("--chrome-binary", default=DEFAULT_CHROME_BINARY)

    postcheck_parser = subparsers.add_parser(
        "post-check",
        help="Capture real Miaoda post-check evidence for the R2 cockpit page.",
    )
    postcheck_parser.add_argument("--plan-file")
    postcheck_parser.add_argument("--binding-run-file")
    postcheck_parser.add_argument("--dashboard-url", default=DEFAULT_REFERENCE_APP_URL)
    postcheck_parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    postcheck_parser.add_argument("--chrome-root", default=str(DEFAULT_CHROME_ROOT))
    postcheck_parser.add_argument("--profile-name", default=DEFAULT_PROFILE_NAME)
    postcheck_parser.add_argument("--chrome-binary", default=DEFAULT_CHROME_BINARY)

    return parser


def run_plan(args: argparse.Namespace) -> int:
    spec = read_json(Path(args.spec_file))
    plan = build_binding_plan(
        spec,
        miaoda_home_url=args.miaoda_home_url,
        reference_app_url=args.reference_app_url,
    )
    artifact_dir = Path(args.artifact_dir)
    plan_json_path = artifact_dir / "miaoda-r2-binding-plan.json"
    plan_md_path = artifact_dir / "miaoda-r2-binding-plan.md"
    write_json(plan_json_path, plan)
    write_text(plan_md_path, render_plan_markdown(plan))
    print(
        json.dumps(
            {
                "status": "completed",
                "plan_json": str(plan_json_path.resolve()),
                "plan_md": str(plan_md_path.resolve()),
                "steps": len(plan["binding_steps"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def run_probe(args: argparse.Namespace) -> int:
    result = run_auth_probe(
        target_url=args.target_url,
        artifact_dir=Path(args.artifact_dir),
        chrome_root=Path(args.chrome_root),
        profile_name=args.profile_name,
        chrome_binary=args.chrome_binary,
    )
    output_path = Path(args.artifact_dir) / "miaoda-r2-auth-probe.json"
    write_json(output_path, result)
    print(json.dumps({"status": "completed", "result_file": str(output_path.resolve()), **result}, ensure_ascii=False, indent=2))
    return 0


def run_prompt_pack(args: argparse.Namespace) -> int:
    plan = read_json(Path(args.plan_file))
    artifact_dir = Path(args.artifact_dir)
    output_path = artifact_dir / "miaoda-r2-prompt-pack.md"
    write_text(output_path, build_prompt_pack(plan))
    print(
        json.dumps(
            {
                "status": "completed",
                "prompt_pack": str(output_path.resolve()),
                "cards": len(plan.get("binding_steps", [])),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def run_refresh_packet(args: argparse.Namespace) -> int:
    spec = read_json(Path(args.spec_file))
    source_views = json.loads(Path(args.source_views_file).read_text(encoding="utf-8"))
    packet = build_refresh_packet(spec, source_views)
    artifact_dir = Path(args.artifact_dir)
    packet_json_path = artifact_dir / "miaoda-r2-refresh-packet.json"
    packet_md_path = artifact_dir / "miaoda-r2-refresh-packet.md"
    write_json(packet_json_path, packet)
    write_text(packet_md_path, render_refresh_packet_markdown(packet))
    print(
        json.dumps(
            {
                "status": "completed",
                "refresh_packet_json": str(packet_json_path.resolve()),
                "refresh_packet_md": str(packet_md_path.resolve()),
                "cards": len(packet["cards"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def run_bind_cards(args: argparse.Namespace) -> int:
    artifact_dir = Path(args.artifact_dir)
    plan = read_json(resolve_plan_path(args))
    focus_steps = phase2_focus_steps(plan)
    surface = capture_surface_state(
        target_url=args.dashboard_url,
        artifact_dir=artifact_dir,
        chrome_root=Path(args.chrome_root),
        profile_name=args.profile_name,
        chrome_binary=args.chrome_binary,
        screenshot_name="miaoda-r2-binding-run.png",
        expected_titles=[step["title"] for step in plan.get("binding_steps", [])],
        focus_steps=focus_steps,
    )
    result = build_binding_run_result(plan, surface)
    output_path = artifact_dir / "miaoda-r2-binding-run.json"
    write_json(output_path, result)
    print(
        json.dumps(
            {
                "status": "completed",
                "result_file": str(output_path.resolve()),
                "r2_state": result["r2_state"],
                "binding_mode": result["binding_mode"],
                "visible_cards": result["visible_cards"],
                "steps_total": result["steps_total"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def run_post_check(args: argparse.Namespace) -> int:
    artifact_dir = Path(args.artifact_dir)
    plan = read_json(resolve_plan_path(args))
    focus_steps = phase2_focus_steps(plan)
    binding_run_path = resolve_binding_run_path(args)
    binding_run = read_json(binding_run_path) if binding_run_path.exists() else None
    surface = capture_surface_state(
        target_url=args.dashboard_url,
        artifact_dir=artifact_dir,
        chrome_root=Path(args.chrome_root),
        profile_name=args.profile_name,
        chrome_binary=args.chrome_binary,
        screenshot_name="miaoda-r2-postcheck.png",
        expected_titles=[step["title"] for step in plan.get("binding_steps", [])],
        focus_steps=focus_steps,
    )
    result = build_postcheck_result(plan, binding_run, surface)
    output_path = artifact_dir / "miaoda-r2-postcheck.json"
    write_json(output_path, result)
    print(
        json.dumps(
            {
                "status": "completed",
                "result_file": str(output_path.resolve()),
                "verification_state": result["verification_state"],
                "cards_visible": result["cards_visible"],
                "cards_total": result["cards_total"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "plan":
        return run_plan(args)
    if args.command == "probe-auth":
        return run_probe(args)
    if args.command == "prompt-pack":
        return run_prompt_pack(args)
    if args.command == "refresh-packet":
        return run_refresh_packet(args)
    if args.command == "bind-cards":
        return run_bind_cards(args)
    if args.command == "post-check":
        return run_post_check(args)
    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
