#!/usr/bin/env python3
"""Validate industry_storyboard.json before deterministic PPT execution."""

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Optional

from convert_storyboard_to_ppt_copy import EXPECTED_CONTENT_FIELDS
from json_utils import load_json_file


DEFAULT_LAYOUT_BUDGET_PATH = Path(__file__).resolve().parents[1] / "templates" / "layout_budget.json"


FIXED_PAGE_TYPES = {
    1: "summary_page",
    3: "driver_card_page",
    4: "value_chain_page",
    5: "moat_page",
    8: "summary_page",
}

VARIANT_PAGE_TYPES = {
    2: ("slide_2_variant", {"chart_page", "chart_plus_mini_table_page"}),
    6: ("slide_6_variant", {"compare_table_page", "matrix_page"}),
    7: ("slide_7_variant", {"trend_page", "timeline_page"}),
}

REQUIRED_TOP_LEVEL = {
    "section_meta",
    "storyline_strategy",
    "slides",
    "template_binding",
    "qc_self_check",
}

REQUIRED_SLIDE_FIELDS = {
    "slide_no",
    "slide_role",
    "selected_page_type",
    "decision_rationale",
    "headline",
    "main_message",
    "body_copy",
    "target_link",
    "source_note",
}

REQUIRED_STRATEGY_FIELDS = {
    "one_sentence_thesis",
    "transaction_relevance",
    "primary_investor_questions",
    "key_messages",
}

REQUIRED_QC_FIELDS = {
    "generic_industry_report_risk",
    "target_linkage_check",
    "source_support_check",
    "page_repetition_check",
    "template_fit_check",
}

CHART_TYPES_REQUIRING_SERIES = {
    "bar",
    "column",
    "clustered_bar",
    "clustered_column",
    "stacked_bar",
    "stacked_column",
    "line",
    "line_chart",
}
SUPPORTED_CHART_TYPES = CHART_TYPES_REQUIRING_SERIES | {"metric_cards", "none", "no_chart", "text"}
DEFAULT_TERMINAL_PUNCTUATION = "。．.，,、；;：:！!？?"


def load_json(path: Path) -> dict:
    return load_json_file(path)


def is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def add_missing(errors: list[str], prefix: str, obj: dict, required: set[str]) -> None:
    missing = sorted(required - set(obj.keys()))
    if missing:
        errors.append(f"{prefix}: missing required fields: {', '.join(missing)}")


def display_units(text: str) -> float:
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


def check_main_message_terminal_punctuation(
    slide_no: int,
    text: str,
    layout_budget: Optional[dict],
    errors: list[str],
) -> None:
    global_rules = (layout_budget or {}).get("global", {})
    main_message_rules = global_rules.get("main_message", {})
    if not main_message_rules.get("forbid_terminal_punctuation", True):
        return
    terminal_punctuation = main_message_rules.get("terminal_punctuation", DEFAULT_TERMINAL_PUNCTUATION)
    stripped = str(text or "").strip()
    if stripped and stripped[-1] in terminal_punctuation:
        errors.append(f"slide {slide_no}: main_message/subtitle must not end with punctuation")


def check_layout_budget(
    slide_no: int,
    page_type: str,
    body_copy: dict,
    layout_budget: Optional[dict],
    errors: list[str],
    warnings: list[str],
) -> None:
    if not layout_budget:
        return
    global_rules = layout_budget.get("global", {})
    page_rules = layout_budget.get("page_type_budgets", {}).get(page_type, {})
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


def estimate_lines(text: str, max_line_units: float) -> int:
    if not text or max_line_units <= 0:
        return 0
    return sum(max(1, math.ceil(display_units(segment) / max_line_units)) for segment in re.split(r"\r?\n", text))


def check_text_fit(
    slide_no: int,
    page_type: str,
    storyboard_field: str,
    text: str,
    text_fit_rules: dict,
    errors: list[str],
    warnings: list[str],
) -> None:
    aliases = text_fit_rules.get("storyboard_field_aliases", {})
    field_name = aliases.get(storyboard_field, storyboard_field)
    rule = text_fit_rules.get("fields", {}).get(f"{slide_no}:{page_type}:{field_name}")
    if not rule:
        return
    actual_lines = estimate_lines(text, float(rule.get("max_line_units") or 0))
    target_lines = int(rule.get("target_lines") or 0)
    max_lines = int(rule.get("max_lines") or 0)
    placeholder = rule.get("placeholder", "")
    if target_lines and actual_lines > target_lines:
        warnings.append(
            f"slide {slide_no}: {storyboard_field} estimated at {actual_lines} line(s) for {placeholder}; "
            f"target is {target_lines}"
        )
    if max_lines and actual_lines > max_lines:
        errors.append(
            f"slide {slide_no}: {storyboard_field} estimated at {actual_lines} line(s) for {placeholder}; "
            f"max allowed is {max_lines}"
        )


def validate_top_level(storyboard: dict, errors: list[str], warnings: list[str]) -> None:
    add_missing(errors, "storyboard", storyboard, REQUIRED_TOP_LEVEL)

    section_meta = storyboard.get("section_meta", {})
    if not isinstance(section_meta, dict):
        errors.append("section_meta must be an object")
    else:
        for key in ["target_name", "industry", "language", "output_mode", "source_memo"]:
            if is_blank(section_meta.get(key)):
                errors.append(f"section_meta.{key} is required and must not be blank")

    strategy = storyboard.get("storyline_strategy", {})
    if not isinstance(strategy, dict):
        errors.append("storyline_strategy must be an object")
    else:
        add_missing(errors, "storyline_strategy", strategy, REQUIRED_STRATEGY_FIELDS)
        if len(strategy.get("primary_investor_questions", [])) < 3:
            warnings.append("storyline_strategy.primary_investor_questions should contain at least 3 items")
        if len(strategy.get("key_messages", [])) < 5:
            warnings.append("storyline_strategy.key_messages should contain at least 5 items")

    qc = storyboard.get("qc_self_check", {})
    if not isinstance(qc, dict):
        errors.append("qc_self_check must be an object")
    else:
        add_missing(errors, "qc_self_check", qc, REQUIRED_QC_FIELDS)


def validate_chart_data(slide: dict, errors: list[str], warnings: list[str], layout_budget: Optional[dict] = None) -> None:
    slide_no = slide.get("slide_no")
    page_type = slide.get("selected_page_type")
    chart_data = slide.get("chart_data")
    if chart_data is None:
        if page_type in {"chart_page", "chart_plus_mini_table_page"} or slide_no == 1:
            errors.append(f"slide {slide_no}: page type {page_type} requires executable chart_data")
        return
    if not isinstance(chart_data, dict):
        errors.append(f"slide {slide_no}: chart_data must be an object when present")
        return

    chart_type = str(chart_data.get("chart_type") or "").lower()
    if not chart_type:
        errors.append(f"slide {slide_no}: chart_data.chart_type is required")
        return
    if chart_type not in SUPPORTED_CHART_TYPES:
        errors.append(
            f"slide {slide_no}: unsupported chart_data.chart_type '{chart_data.get('chart_type')}'. "
            f"Allowed: {', '.join(sorted(SUPPORTED_CHART_TYPES))}"
        )
    if chart_type in {"none", "no_chart", "text"}:
        if page_type in {"chart_page", "chart_plus_mini_table_page"}:
            errors.append(f"slide {slide_no}: quantitative page type cannot use chart_type={chart_type}")
        return

    series = chart_data.get("series", [])
    categories = chart_data.get("categories", [])
    if chart_type in CHART_TYPES_REQUIRING_SERIES:
        if not isinstance(categories, list) or not categories:
            errors.append(f"slide {slide_no}: chart_data.categories is required for chart_type={chart_type}")
        if not isinstance(series, list) or not series:
            errors.append(f"slide {slide_no}: chart_data.series is required for chart_type={chart_type}")
        if is_blank(chart_data.get("unit")):
            errors.append(f"slide {slide_no}: chart_data.unit is required for chart_type={chart_type}")
    if isinstance(series, list) and isinstance(categories, list) and series and categories:
        expected_len = len(categories)
        for item in series:
            if not isinstance(item, dict):
                errors.append(f"slide {slide_no}: each chart_data.series item must be an object")
                continue
            values = item.get("values", []) if isinstance(item, dict) else []
            if len(values) != expected_len:
                errors.append(
                    f"slide {slide_no}: chart_data series '{item.get('name', '')}' has "
                    f"{len(values)} values but {expected_len} categories"
                )
            if any(not isinstance(value, (int, float)) for value in values):
                errors.append(f"slide {slide_no}: chart_data series '{item.get('name', '')}' contains non-numeric values")
    if chart_type == "metric_cards":
        source_rows = chart_data.get("source_rows")
        min_rows = 3 if slide_no == 1 else 2
        if slide_no == 1 and layout_budget:
            slide_1_visual = (
                layout_budget.get("page_type_budgets", {})
                .get("summary_page", {})
                .get("slide_1_visual", {})
            )
            min_rows = int(slide_1_visual.get("min_metric_cards", min_rows))
            max_rows = int(slide_1_visual.get("max_metric_cards", min_rows))
            if isinstance(source_rows, list) and len(source_rows) > max_rows:
                warnings.append(f"slide {slide_no}: metric_cards will render only the first {max_rows} source_rows")
        if not isinstance(source_rows, list) or len(source_rows) < min_rows:
            errors.append(f"slide {slide_no}: metric_cards requires at least {min_rows} source_rows")
        elif any(not isinstance(row, dict) or is_blank(row.get("label")) or is_blank(row.get("value")) for row in source_rows):
            errors.append(f"slide {slide_no}: metric_cards source_rows require nonblank label and value")
    if not chart_data.get("source_rows"):
        errors.append(f"slide {slide_no}: chart_data.source_rows is required")


def validate_slides(
    storyboard: dict,
    errors: list[str],
    warnings: list[str],
    text_fit_rules: Optional[dict] = None,
    layout_budget: Optional[dict] = None,
) -> None:
    slides = storyboard.get("slides", [])
    if not isinstance(slides, list):
        errors.append("slides must be an array")
        return
    if len(slides) != 8:
        errors.append(f"slides must contain exactly 8 items; found {len(slides)}")

    seen = []
    slide_by_no = {}
    for slide in slides:
        if not isinstance(slide, dict):
            errors.append("each slide must be an object")
            continue
        slide_no = slide.get("slide_no")
        seen.append(slide_no)
        slide_by_no[slide_no] = slide

        add_missing(errors, f"slide {slide_no}", slide, REQUIRED_SLIDE_FIELDS)
        for key in ["headline", "main_message", "decision_rationale", "target_link", "source_note"]:
            if is_blank(slide.get(key)):
                errors.append(f"slide {slide_no}: {key} is required and must not be blank")

        page_type = slide.get("selected_page_type")
        if text_fit_rules and page_type:
            check_text_fit(slide_no, page_type, "headline", str(slide.get("headline") or ""), text_fit_rules, errors, warnings)
            check_text_fit(slide_no, page_type, "main_message", str(slide.get("main_message") or ""), text_fit_rules, errors, warnings)
        check_main_message_terminal_punctuation(slide_no, str(slide.get("main_message") or ""), layout_budget, errors)
        if slide_no in FIXED_PAGE_TYPES and page_type != FIXED_PAGE_TYPES[slide_no]:
            errors.append(
                f"slide {slide_no}: selected_page_type must be {FIXED_PAGE_TYPES[slide_no]}, found {page_type}"
            )
        if slide_no in VARIANT_PAGE_TYPES:
            _, valid_types = VARIANT_PAGE_TYPES[slide_no]
            if page_type not in valid_types:
                errors.append(
                    f"slide {slide_no}: selected_page_type must be one of {sorted(valid_types)}, found {page_type}"
                )

        body_copy = slide.get("body_copy")
        if not isinstance(body_copy, dict):
            errors.append(f"slide {slide_no}: body_copy must be an object")
        else:
            expected_fields = EXPECTED_CONTENT_FIELDS.get(slide_no, {}).get(page_type)
            if not expected_fields:
                errors.append(f"slide {slide_no}: no active body_copy contract for page type {page_type}")
            else:
                missing = [field for field in expected_fields if field not in body_copy]
                blank = [field for field in expected_fields if is_blank(body_copy.get(field))]
                extra = sorted(set(body_copy.keys()) - set(expected_fields))
                if missing:
                    errors.append(f"slide {slide_no}: missing active body_copy fields: {', '.join(missing)}")
                if blank:
                    errors.append(f"slide {slide_no}: blank active body_copy fields: {', '.join(blank)}")
                if extra:
                    warnings.append(f"slide {slide_no}: extra body_copy fields ignored by active layout: {', '.join(extra)}")
                check_layout_budget(slide_no, page_type, body_copy, layout_budget, errors, warnings)

        validate_chart_data(slide, errors, warnings, layout_budget)

    expected_numbers = list(range(1, 9))
    if sorted(seen) != expected_numbers:
        errors.append(f"slides must be numbered 1-8 exactly; found {seen}")

    validate_template_binding(storyboard.get("template_binding", {}), slide_by_no, errors, warnings)


def validate_template_binding(
    template_binding: dict,
    slide_by_no: dict[int, dict],
    errors: list[str],
    warnings: list[str],
) -> None:
    if not isinstance(template_binding, dict):
        errors.append("template_binding must be an object")
        return

    inactive = set(template_binding.get("inactive_variants_to_remove", []))
    expected_inactive = set()
    for slide_no, (binding_key, valid_types) in VARIANT_PAGE_TYPES.items():
        bound_value = template_binding.get(binding_key)
        slide_value = slide_by_no.get(slide_no, {}).get("selected_page_type")
        if bound_value not in valid_types:
            errors.append(f"template_binding.{binding_key} must be one of {sorted(valid_types)}, found {bound_value}")
            continue
        if slide_value and bound_value != slide_value:
            errors.append(
                f"slide {slide_no}: selected_page_type {slide_value} does not match template_binding.{binding_key} {bound_value}"
            )
        expected_inactive.update(valid_types - {bound_value})

    if inactive != expected_inactive:
        errors.append(
            "template_binding.inactive_variants_to_remove must equal the unselected variants; "
            f"expected {sorted(expected_inactive)}, found {sorted(inactive)}"
        )


def validate(
    storyboard_path: Path,
    schema_path: Optional[Path] = None,
    text_fit_rules_path: Optional[Path] = None,
    layout_budget_path: Optional[Path] = DEFAULT_LAYOUT_BUDGET_PATH,
) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        storyboard = load_json(storyboard_path)
    except ValueError as exc:
        return {
            "is_valid": False,
            "storyboard": str(storyboard_path),
            "errors": [str(exc)],
            "warnings": [],
        }

    if schema_path and not schema_path.exists():
        errors.append(f"schema file not found: {schema_path}")

    text_fit_rules = None
    if text_fit_rules_path:
        try:
            text_fit_rules = load_json(text_fit_rules_path)
        except Exception as exc:
            errors.append(f"cannot load text fit rules: {exc}")
    layout_budget = None
    if layout_budget_path and layout_budget_path.exists():
        try:
            layout_budget = load_json(layout_budget_path)
        except Exception as exc:
            errors.append(f"cannot load layout budget: {exc}")

    validate_top_level(storyboard, errors, warnings)
    validate_slides(storyboard, errors, warnings, text_fit_rules, layout_budget)

    return {
        "is_valid": not errors,
        "storyboard": str(storyboard_path),
        "schema": str(schema_path) if schema_path else "",
        "text_fit_rules": str(text_fit_rules_path) if text_fit_rules_path else "",
        "layout_budget": str(layout_budget_path) if layout_budget_path else "",
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate industry_storyboard.json contract.")
    parser.add_argument("--storyboard", required=True, help="Path to industry_storyboard.json.")
    parser.add_argument("--schema", default="", help="Optional path to templates/storyboard_schema.json.")
    parser.add_argument("--text-fit-rules", default="", help="Optional path to templates/text_fit_rules.json.")
    parser.add_argument("--layout-budget", default=str(DEFAULT_LAYOUT_BUDGET_PATH), help="Optional path to templates/layout_budget.json.")
    parser.add_argument("--output", default="", help="Optional path to write validation report JSON.")
    parser.add_argument("--warnings-as-errors", action="store_true", help="Fail when warnings are present.")
    args = parser.parse_args()

    schema_path = Path(args.schema) if args.schema else None
    text_fit_rules_path = Path(args.text_fit_rules) if args.text_fit_rules else None
    layout_budget_path = Path(args.layout_budget) if args.layout_budget else None
    result = validate(Path(args.storyboard), schema_path, text_fit_rules_path, layout_budget_path)
    if args.warnings_as_errors and result["warnings"]:
        result["is_valid"] = False

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["is_valid"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
