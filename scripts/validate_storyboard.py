#!/usr/bin/env python3
"""Validate industry_storyboard.json before deterministic PPT execution."""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from convert_storyboard_to_ppt_copy import EXPECTED_CONTENT_FIELDS


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


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


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


def validate_chart_data(slide: dict, errors: list[str], warnings: list[str]) -> None:
    slide_no = slide.get("slide_no")
    chart_data = slide.get("chart_data")
    if chart_data is None:
        if slide.get("selected_page_type") in {"chart_page", "chart_plus_mini_table_page"}:
            warnings.append(f"slide {slide_no}: quantitative page type has no chart_data")
        return
    if not isinstance(chart_data, dict):
        errors.append(f"slide {slide_no}: chart_data must be an object when present")
        return

    series = chart_data.get("series", [])
    categories = chart_data.get("categories", [])
    if series and categories:
        expected_len = len(categories)
        for item in series:
            values = item.get("values", []) if isinstance(item, dict) else []
            if len(values) != expected_len:
                errors.append(
                    f"slide {slide_no}: chart_data series '{item.get('name', '')}' has "
                    f"{len(values)} values but {expected_len} categories"
                )
    if not chart_data.get("source_rows"):
        warnings.append(f"slide {slide_no}: chart_data has no source_rows")


def validate_slides(storyboard: dict, errors: list[str], warnings: list[str]) -> None:
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

        validate_chart_data(slide, errors, warnings)

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


def validate(storyboard_path: Path, schema_path: Optional[Path] = None) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        storyboard = load_json(storyboard_path)
    except json.JSONDecodeError as exc:
        return {
            "is_valid": False,
            "storyboard": str(storyboard_path),
            "errors": [f"invalid JSON: {exc}"],
            "warnings": [],
        }

    if schema_path and not schema_path.exists():
        errors.append(f"schema file not found: {schema_path}")

    validate_top_level(storyboard, errors, warnings)
    validate_slides(storyboard, errors, warnings)

    return {
        "is_valid": not errors,
        "storyboard": str(storyboard_path),
        "schema": str(schema_path) if schema_path else "",
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate industry_storyboard.json contract.")
    parser.add_argument("--storyboard", required=True, help="Path to industry_storyboard.json.")
    parser.add_argument("--schema", default="", help="Optional path to templates/storyboard_schema.json.")
    parser.add_argument("--output", default="", help="Optional path to write validation report JSON.")
    parser.add_argument("--warnings-as-errors", action="store_true", help="Fail when warnings are present.")
    args = parser.parse_args()

    schema_path = Path(args.schema) if args.schema else None
    result = validate(Path(args.storyboard), schema_path)
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
