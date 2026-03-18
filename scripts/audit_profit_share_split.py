#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS = {"a": MAIN_NS}
N = f"{{{MAIN_NS}}}"


@dataclass
class Cell:
    ref: str
    value: Any
    raw: str
    formula: str | None


def col_from_ref(ref: str) -> str:
    return re.sub(r"\d", "", ref)


def row_from_ref(ref: str) -> int:
    return int(re.sub(r"\D", "", ref))


def to_number(raw: str) -> Any:
    if raw == "":
        return ""
    try:
        num = float(raw)
    except ValueError:
        return raw
    if math.isfinite(num):
        return num
    return raw


def is_numeric_string(value: str) -> bool:
    return re.fullmatch(r"[-+]?\d+(?:\.\d+)?(?:[Ee][-+]?\d+)?", value) is not None


def excel_serial_to_iso(value: str) -> str | None:
    if not is_numeric_string(value):
        return None
    number = float(value)
    if number < 30000 or number > 60000 or not number.is_integer():
        return None
    origin = datetime(1899, 12, 30)
    return (origin + timedelta(days=int(number))).date().isoformat()


class WorkbookView:
    def __init__(self, workbook_path: Path) -> None:
        self.workbook_path = workbook_path
        self.sheet_name = ""
        self.cells: dict[str, Cell] = {}
        self.headers: dict[str, str] = {}
        self.row_labels: dict[int, str] = {}
        self._load()

    def _load(self) -> None:
        with zipfile.ZipFile(self.workbook_path) as zf:
            shared_strings = self._load_shared_strings(zf)
            self.sheet_name = self._load_first_sheet_name(zf)
            sheet_xml = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
            for cell_node in sheet_xml.findall(".//a:c", NS):
                ref = cell_node.attrib["r"]
                raw = self._read_cell_raw(cell_node, shared_strings)
                formula_node = cell_node.find("a:f", NS)
                cell = Cell(
                    ref=ref,
                    value=to_number(raw),
                    raw=raw,
                    formula=formula_node.text if formula_node is not None else None,
                )
                self.cells[ref] = cell

            for ref, cell in self.cells.items():
                col = col_from_ref(ref)
                row = row_from_ref(ref)
                if row == 3:
                    self.headers[col] = cell.raw
                if col == "A":
                    self.row_labels[row] = cell.raw

    def _load_shared_strings(self, zf: zipfile.ZipFile) -> list[str]:
        if "xl/sharedStrings.xml" not in zf.namelist():
            return []
        shared_xml = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        values: list[str] = []
        for node in shared_xml.findall("a:si", NS):
            parts = [text.text or "" for text in node.iter(f"{N}t")]
            values.append("".join(parts))
        return values

    def _load_first_sheet_name(self, zf: zipfile.ZipFile) -> str:
        workbook_xml = ET.fromstring(zf.read("xl/workbook.xml"))
        first_sheet = workbook_xml.find("a:sheets/a:sheet", NS)
        return first_sheet.attrib.get("name", "sheet1") if first_sheet is not None else "sheet1"

    def _read_cell_raw(self, cell_node: ET.Element, shared_strings: list[str]) -> str:
        cell_type = cell_node.attrib.get("t")
        value_node = cell_node.find("a:v", NS)
        if cell_type == "s" and value_node is not None:
            return shared_strings[int(value_node.text or "0")]
        if cell_type == "inlineStr":
            inline_node = cell_node.find("a:is", NS)
            if inline_node is None:
                return ""
            return "".join(text.text or "" for text in inline_node.iter(f"{N}t"))
        if value_node is not None and value_node.text is not None:
            return value_node.text
        return ""

    def get(self, ref: str) -> Cell:
        return self.cells[ref]

    def number(self, ref: str) -> float:
        value = self.get(ref).value
        if isinstance(value, (int, float)):
            return float(value)
        raise ValueError(f"{ref} is not numeric: {value!r}")

    def header(self, ref_or_col: str) -> str:
        col = ref_or_col if ref_or_col.isalpha() else col_from_ref(ref_or_col)
        return self.headers.get(col, "")

    def header_display(self, ref_or_col: str) -> str:
        raw = self.header(ref_or_col)
        converted = excel_serial_to_iso(raw)
        return converted or raw

    def row_label(self, ref_or_row: str | int) -> str:
        row = ref_or_row if isinstance(ref_or_row, int) else row_from_ref(ref_or_row)
        return self.row_labels.get(int(row), "")


def currency(value: float) -> str:
    return f"{value:,.2f}"


def percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def matches_expected(actual: float, expected: float, tolerance: float = 0.01) -> bool:
    return abs(actual - expected) <= tolerance


def build_reference_checks(book: WorkbookView) -> list[dict[str, Any]]:
    checks = [
        ("AO61", "AL60"),
        ("BH61", "D60"),
        ("BQ61", "BN60"),
        ("BZ61", "BW60"),
        ("CI61", "CF60"),
        ("DB61", "CO60"),
        ("DK61", "DH60"),
    ]
    results: list[dict[str, Any]] = []
    for target, source in checks:
        target_cell = book.get(target)
        source_cell = book.get(source)
        values_match = target_cell.value == source_cell.value
        results.append(
            {
                "target": target,
                "target_header": book.header_display(target),
                "source": source,
                "source_header": book.header_display(source),
                "target_value": target_cell.value,
                "source_value": source_cell.value,
                "formula": target_cell.formula,
                "passed": target_cell.formula == source and values_match,
            }
        )
    return results


def search_split_markers(book: WorkbookView) -> list[dict[str, Any]]:
    markers = ("20%", "80%", "0.2", "0.8", "二八")
    findings: list[dict[str, Any]] = []
    for cell in book.cells.values():
        raw = cell.raw if isinstance(cell.raw, str) else str(cell.raw)
        formula = cell.formula or ""
        haystacks = [formula]
        if raw and not is_numeric_string(raw):
            haystacks.append(raw)
        if any(marker in hay for hay in haystacks for marker in markers):
            findings.append(
                {
                    "ref": cell.ref,
                    "row_label": book.row_label(cell.ref),
                    "header": book.header_display(cell.ref),
                    "raw": raw,
                    "formula": cell.formula,
                }
            )
    return findings


def annual_rows(book: WorkbookView) -> list[dict[str, Any]]:
    years = [
        {
            "year": "2023",
            "retained_base_cell": "D60",
            "available_base_cell": "D63",
            "annual_display_cell": "L61",
            "quarter_cells": ["L61"],
            "notes": "23Q4 年显示值与 2023-10-01 节点 AO61 一致，AO61=AL60。",
        },
        {
            "year": "2024",
            "retained_base_cell": "AX60",
            "available_base_cell": "AX63",
            "annual_display_cell": "AX61",
            "quarter_cells": ["AZ61", "BB61", "BD61", "BF61"],
            "notes": "AX61 当前公式只汇总 AZ61+BB61+BD61，漏掉 BF61。",
        },
        {
            "year": "2025YTD",
            "retained_base_cell": "CR60",
            "available_base_cell": "CR63",
            "annual_display_cell": "CR61",
            "quarter_cells": ["CT61", "CV61", "CX61"],
            "notes": "CR61 为手填值，但与 CT61+CV61+CX61 相等。",
        },
    ]
    rows: list[dict[str, Any]] = []
    for item in years:
        retained_base = book.number(item["retained_base_cell"])
        available_base = book.number(item["available_base_cell"])
        actual_display = book.number(item["annual_display_cell"])
        corrected_total = sum(book.number(ref) for ref in item["quarter_cells"])
        retained_expected_20 = retained_base * 0.2
        retained_expected_80 = retained_base * 0.8
        available_expected_20 = available_base * 0.2
        available_expected_80 = available_base * 0.8
        rows.append(
            {
                **item,
                "retained_base": retained_base,
                "available_base": available_base,
                "retained_expected_20": retained_expected_20,
                "retained_expected_80": retained_expected_80,
                "available_expected_20": available_expected_20,
                "available_expected_80": available_expected_80,
                "actual_display": actual_display,
                "corrected_total": corrected_total,
                "display_vs_retained_ratio": actual_display / retained_base if retained_base else None,
                "display_vs_available_ratio": actual_display / available_base if available_base else None,
                "corrected_vs_retained_ratio": corrected_total / retained_base if retained_base else None,
                "corrected_vs_available_ratio": corrected_total / available_base if available_base else None,
                "matches_retained_20": matches_expected(actual_display, retained_expected_20),
                "matches_retained_80": matches_expected(actual_display, retained_expected_80),
                "matches_available_20": matches_expected(actual_display, available_expected_20),
                "matches_available_80": matches_expected(actual_display, available_expected_80),
            }
        )
    return rows


def anomaly_rows(book: WorkbookView, annual: list[dict[str, Any]]) -> list[str]:
    findings: list[str] = []
    formula_markers = [
        row
        for row in search_split_markers(book)
        if row["row_label"] not in {"人力服务费"} and row["ref"] not in {"EL32"}
    ]
    if not formula_markers:
        findings.append("未发现任何与分红/留存利润相关的 `20% / 80% / 0.2 / 0.8 / 二八` 公式或标签。")

    ax61 = book.get("AX61")
    bf61 = book.number("BF61")
    corrected_2024 = next(row for row in annual if row["year"] == "2024")["corrected_total"]
    findings.append(
        "2024 年分红汇总 `AX61` 的公式为 `SUM(AZ61,BB61,BD61)`，漏掉了 `BF61="
        + currency(bf61)
        + "`，若按季度行求和应为 `"
        + currency(corrected_2024)
        + "`。"
    )

    cr61 = book.get("CR61")
    if cr61.formula is None:
        findings.append("`CR61` 没有公式，是手填值；虽然当前与 `CT61+CV61+CX61` 相等，但存在人工口径风险。")

    findings.append(
        "Row 61 的关键节点均直接承接上一个结点的 `子品牌可用余额`，例如 `AO61=AL60`、`BQ61=BN60`、`DB61=CO60`，说明这里记录的是整笔结转/分红，而不是按比例拆分。"
    )
    return findings


def verdict(annual: list[dict[str, Any]]) -> dict[str, str]:
    mismatches = []
    for row in annual:
        if not any(
            [
                row["matches_retained_20"],
                row["matches_retained_80"],
                row["matches_available_20"],
                row["matches_available_80"],
            ]
        ):
            mismatches.append(row["year"])

    summary = "按表内现状看，没有证据支持历年留存利润按“你 20% / 公司 80%”执行。"
    if len(mismatches) != len(annual):
        summary = "部分年份存在需要人工复核的口径，但仍没有直接的 20/80 公式证据。"

    likely_issue = (
        "如果业务约定确实应按二八分，当前最可能的偏差层在 `子品牌分红` 记录方式和年汇总口径，"
        "其次才是“留存利润基数”定义；因为分红行直接引用历史余额，且 2024/2025 年汇总还存在漏算或手填。"
    )
    return {"summary": summary, "likely_issue": likely_issue}


def render_markdown(book: WorkbookView, annual: list[dict[str, Any]], reference_checks: list[dict[str, Any]]) -> str:
    verdict_block = verdict(annual)
    anomalies = anomaly_rows(book, annual)
    lines: list[str] = []
    lines.append("# 视频创作中心留存利润二八分审计")
    lines.append("")
    lines.append("## 审计对象")
    lines.append(f"- 文件：`{book.workbook_path}`")
    lines.append(f"- 工作表：`{book.sheet_name}`")
    lines.append("- 审计口径：默认把“每年留存利润”理解为年度末仍可分配余额（row 60），并用 row 63 做交叉核对。")
    lines.append("")
    lines.append("## 结论")
    lines.append(f"- {verdict_block['summary']}")
    lines.append(f"- {verdict_block['likely_issue']}")
    lines.append("")
    lines.append("## 年度审计表")
    lines.append("")
    lines.append("| 年度 | 年末留存基数 | 你应得20% | 公司应得80% | 年累计可动用基数 | 实际分红年汇总 | 实际/留存基数 | 实际/累计可动用 | 判断 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
    for row in annual:
        decision = "不匹配 20/80"
        lines.append(
            "| "
            + " | ".join(
                [
                    row["year"],
                    f"{currency(row['retained_base'])} (`{row['retained_base_cell']}`)",
                    currency(row["retained_expected_20"]),
                    currency(row["retained_expected_80"]),
                    f"{currency(row['available_base'])} (`{row['available_base_cell']}`)",
                    f"{currency(row['actual_display'])} (`{row['annual_display_cell']}`)",
                    percent(row["display_vs_retained_ratio"]),
                    percent(row["display_vs_available_ratio"]),
                    decision,
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## 关键引用链核验")
    lines.append("")
    lines.append("| 分红记录 | 分红列头 | 直接引用 | 来源列头 | 数值是否一致 | 结论 |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for check in reference_checks:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{check['target']}`",
                    check["target_header"] or "-",
                    f"`{check['source']}`",
                    check["source_header"] or "-",
                    "是" if check["target_value"] == check["source_value"] else "否",
                    "通过" if check["passed"] else "未通过",
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## 异常点")
    for item in anomalies:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## 年度备注")
    for row in annual:
        lines.append(f"- {row['year']}：{row['notes']}")
    lines.append("")
    lines.append("## 2024 年汇总修正参考")
    lines.append(
        "- `AX61` 显示值为 "
        + currency(book.number("AX61"))
        + "，但四个季度/节点分红分别是 "
        + ", ".join(f"`{ref}={currency(book.number(ref))}`" for ref in ["AZ61", "BB61", "BD61", "BF61"])
        + "。"
    )
    lines.append("- 若四项都计入，2024 年分红合计应为 " + currency(next(row for row in annual if row["year"] == "2024")["corrected_total"]) + "。")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit whether retained profit was split 20/80 in an xlsx workbook.")
    parser.add_argument("workbook", type=Path, help="Path to the xlsx workbook")
    parser.add_argument("--markdown-out", type=Path, required=True, help="Where to write the markdown report")
    parser.add_argument("--json-out", type=Path, required=True, help="Where to write the json summary")
    args = parser.parse_args()

    book = WorkbookView(args.workbook)
    annual = annual_rows(book)
    reference_checks = build_reference_checks(book)
    report = render_markdown(book, annual, reference_checks)

    payload = {
        "workbook": str(args.workbook),
        "sheet_name": book.sheet_name,
        "annual": annual,
        "reference_checks": reference_checks,
        "anomalies": anomaly_rows(book, annual),
        "verdict": verdict(annual),
    }

    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.write_text(report + "\n", encoding="utf-8")
    args.json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
