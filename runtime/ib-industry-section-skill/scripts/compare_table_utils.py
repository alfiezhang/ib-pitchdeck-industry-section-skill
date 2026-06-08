#!/usr/bin/env python3
"""Shared helpers for Slide 6 canonical compare-table payloads."""

from __future__ import annotations

import re
from typing import Any


def split_table_cells(text: str) -> list[str]:
    """Split display-only table text while preserving blank cells."""
    if "｜" in text:
        return [part.strip() for part in text.split("｜")]
    if "|" in text:
        stripped = text.strip().strip("|")
        return [part.strip() for part in stripped.split("|")]
    return [text.strip()] if text.strip() else []


def normalize_compare_table_payload(slide_data: dict[str, Any]) -> tuple[list[str], list[list[str]]]:
    """Return headers and full rows from canonical compare_table_data.

    `compare_table_data` is the renderer-spec source of truth. Do not infer
    a formal compare table from separator-delimited body text.
    """
    compare_table = slide_data.get("compare_table_data")
    if isinstance(compare_table, dict):
        headers = [str(item).strip() for item in compare_table.get("headers") or []]
        rows: list[list[str]] = []
        for row in compare_table.get("rows") or []:
            if not isinstance(row, dict):
                continue
            label = str(row.get("label") or "").strip()
            cells = [str(item).strip() for item in row.get("cells") or []]
            rows.append([label] + cells)
        return headers, rows

    return [], []


def compare_table_summary_row_issues(rows: list[list[str]]) -> list[str]:
    summary_terms = ("市场结构", "竞争维度", "标的定位", "行业判断", "CR4", "CR5", "CR10", "集中度")
    company_markers = (
        "公司", "企业", "玩家", "集团", "股份", "有限", "控股",
        "co.", "ltd", "inc", "corp", "corporation", "group",
    )
    issues = []
    for idx, cells in enumerate(rows, start=1):
        first_cell = cells[0] if cells else ""
        row_text = " ".join(cells)
        first_cell_lower = first_cell.lower()
        looks_like_company = any(marker in first_cell_lower for marker in company_markers)
        if any(term in row_text for term in summary_terms) and not looks_like_company:
            issues.append(f"row {idx}")
    return issues
