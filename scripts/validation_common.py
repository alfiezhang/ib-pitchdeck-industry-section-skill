#!/usr/bin/env python3
"""Shared validation helpers for storyboard/content-quality checks."""

import math
import re
from typing import Optional


DEFAULT_TERMINAL_PUNCTUATION = "。．.，,、；;：:！!？?"


def is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def display_units(text: str) -> float:
    """Approximate rendered line width in CJK-character units."""
    units = 0.0
    for ch in re.sub(r"\[\[/?(?:b|hl)\]\]", "", text or ""):
        code = ord(ch)
        if ch in "\n\r":
            continue
        if ch.isspace():
            units += 0.3
        elif ch in ",.;:!?()[]{}<>/\\|-_+=~'\"":
            units += 0.35
        elif code < 128:
            units += 0.55
        elif 0xFF61 <= code <= 0xFF9F:
            units += 0.55
        else:
            units += 1.0
    return units


def estimate_lines(text: str, max_line_units: float) -> int:
    if not text or max_line_units <= 0:
        return 0
    return sum(
        max(1, math.ceil(display_units(segment) / max_line_units))
        for segment in re.split(r"\r?\n", text)
    )


def split_table_cells(text: str) -> list[str]:
    value = str(text or "").strip()
    if not value:
        return []
    if "｜" in value:
        return [part.strip() for part in value.split("｜")]
    if "|" in value:
        return [part.strip() for part in value.split("|")]
    if " / " in value:
        return [part.strip() for part in value.split(" / ")]
    return [value]


def layout_rules_for(slide_no: int, page_type: str, layout_budget: Optional[dict]) -> dict:
    if not layout_budget:
        return {}
    slide_key = f"{slide_no}:{page_type}"
    slide_rules = layout_budget.get("slide_budgets", {}).get(slide_key)
    if isinstance(slide_rules, dict):
        return slide_rules
    page_rules = layout_budget.get("page_type_budgets", {}).get(page_type)
    return page_rules if isinstance(page_rules, dict) else {}


def check_main_message_terminal_punctuation(
    text: str,
    slide_no: int,
    layout_budget: Optional[dict],
) -> Optional[str]:
    global_rules = (layout_budget or {}).get("global", {})
    main_message_rules = global_rules.get("main_message", {})
    if not main_message_rules.get("forbid_terminal_punctuation", True):
        return None
    terminal_punctuation = main_message_rules.get("terminal_punctuation", DEFAULT_TERMINAL_PUNCTUATION)
    stripped = str(text or "").strip()
    if stripped and stripped[-1] in terminal_punctuation:
        return f"slide {slide_no}: main_message/subtitle must not end with punctuation"
    return None


def layout_budget_findings(
    body_copy: dict,
    slide_no: int,
    page_type: str,
    layout_budget: Optional[dict],
) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for page/slide layout budget checks."""
    if not layout_budget:
        return [], []

    errors: list[str] = []
    warnings: list[str] = []
    global_rules = layout_budget.get("global", {})
    page_rules = layout_rules_for(slide_no, page_type, layout_budget)
    field_limits = page_rules.get("body_fields_max_units", {})
    default_limit = float(global_rules.get("body_copy", {}).get("max_bullet_units_default", 88))
    table_cell_limit = float(
        page_rules.get("table", {}).get(
            "max_cell_units",
            global_rules.get("table", {}).get("max_cell_units", 22),
        )
    )
    max_newlines = int(global_rules.get("body_copy", {}).get("max_newlines_per_field", 1))

    for field_name, value in body_copy.items():
        if not isinstance(value, str):
            continue
        text = value.strip()
        if not text:
            continue
        if text.count("\n") > max_newlines:
            errors.append(f"slide {slide_no}: {field_name} contains too many line breaks for a PPT body field")
        limit = float(field_limits.get(field_name, default_limit))
        units = display_units(text)
        if units > limit:
            errors.append(
                f"slide {slide_no}: {field_name} is {units:.1f} layout units; "
                f"max for {page_type} is {limit:.1f}"
            )
        if field_name.lower().startswith("table_") and "row" in field_name.lower():
            cells = split_table_cells(text)
            if len(cells) <= 1:
                warnings.append(f"slide {slide_no}: {field_name} should use table cell separator '｜'")
            for idx, cell in enumerate(cells, start=1):
                cell_units = display_units(cell)
                if cell_units > table_cell_limit:
                    errors.append(
                        f"slide {slide_no}: {field_name} cell {idx} is {cell_units:.1f} layout units; "
                        f"max table cell budget is {table_cell_limit:.1f}"
                    )

    return errors, warnings
