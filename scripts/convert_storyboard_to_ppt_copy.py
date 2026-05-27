#!/usr/bin/env python3
"""
Deterministic converter: industry_storyboard.json → industry_section_ppt_copy.json.

For standard storyboard runs, the expected contract is:
  - slide.body_copy already uses ppt_copy-compatible field names
  - selected_page_type is final
  - chart_data / source_note / headline / main_message are final

This script therefore handles the full deterministic conversion for standard
workflows:
  - section_meta → meta block
  - slide_no, selected_page_type → slide_no, selected_page_type
  - headline → slide_title
  - main_message → main_takeaway
  - body_copy → content (pass-through)
  - source_note → source_footer
  - chart_data.title (preferred) or visual_direction → chart_title
  - template_binding → rules block

If a storyboard was written in a looser legacy style and body_copy does not
match ppt_copy field names, run the LLM finalize step after this conversion.

Usage:
  python scripts/convert_storyboard_to_ppt_copy.py \
    --storyboard industry_storyboard.json \
    --output industry_section_ppt_copy.json
"""

import argparse
import copy
import json
import sys
from pathlib import Path

from json_utils import load_json_file


SLIDE_KEY_MAP = {
    "industry_overview": "industry_overview",
    "market_size_segmentation": "market_size_segmentation",
    "growth_drivers": "key_industry_drivers",
    "value_chain_profit_pool": "value_chain_profit_pool",
    "barriers_value_drivers": "key_barriers_value_drivers",
    "competitive_landscape": "competitive_landscape",
    "industry_trends_future_evolution": "industry_trends_future_evolution",
    "key_takeaways_for_target": "key_takeaways_for_target",
}

# Page types that render quantitative charts. All others get chart_title cleared.
CHART_PAGE_TYPES = {"chart_page", "chart_plus_mini_table_page"}

EXPECTED_CONTENT_FIELDS = {
    1: {
        "summary_page": ["bullet_1", "bullet_2", "bullet_3"],
    },
    2: {
        "chart_page": ["bullet_1", "bullet_2", "bullet_3"],
        "chart_plus_mini_table_page": [
            "bullet_1",
            "bullet_2",
            "table_header_1",
            "table_header_2",
            "table_row_1",
            "table_row_2",
            "table_row_3",
        ],
    },
    3: {
        "driver_card_page": ["card_1", "card_2", "card_3", "card_4"],
    },
    4: {
        "value_chain_page": [
            "top_left",
            "top_center",
            "top_right",
            "bottom_left",
            "bottom_center",
            "bottom_right",
        ],
    },
    5: {
        "moat_page": ["card_1", "card_2", "card_3"],
    },
    6: {
        "compare_table_page": [
            "table_header",
            "table_row_1",
            "table_row_2",
            "table_row_3",
            "table_row_4",
            "table_row_5",
            "table_row_6",
            "right_top",
            "right_mid",
            "right_bottom",
        ],
        "matrix_page": [
            "left_panel",
            "matrix_title",
            "matrix_label_x",
            "matrix_label_y",
            "right_top",
            "right_mid",
            "right_bottom",
        ],
    },
    7: {
        "trend_page": ["card_1", "card_2", "card_3"],
        "timeline_page": ["stage_1", "stage_2", "stage_3", "stage_4", "timeline_note"],
    },
    8: {
        "summary_page": ["left_panel", "right_top", "right_mid", "right_bottom"],
    },
}


def load_json(path: Path) -> dict:
    return load_json_file(path)


def save_json(data: dict, path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def convert_meta(storyboard: dict) -> dict:
    """Convert section_meta → ppt_copy meta block."""
    meta = storyboard.get("section_meta", {})
    return {
        "target_company": meta.get("target_name", ""),
        "transaction_type": "",
        "industry": meta.get("industry", ""),
        "subsector": "",
        "geography": meta.get("geography", ""),
        "language": "English" if meta.get("language") == "en" else "Chinese",
    }


def convert_slide(storyboard_slide: dict) -> dict:
    """Convert a single storyboard slide → ppt_copy slide."""
    slide_role = storyboard_slide.get("slide_role", "")
    slide_key = SLIDE_KEY_MAP.get(slide_role, slide_role)
    page_type = storyboard_slide.get("selected_page_type", "")

    # Validate page type consistency with template_binding
    # (caller should pass template_binding for cross-validation)

    # Auto-resolve chart_title:
    # - Has chart_data with title → use it (metric cards, bar charts, etc.)
    # - Chart page type without chart_data → fallback to visual_direction
    # - Non-chart page type without chart_data → clear (visual_direction is execution notes)
    chart_data = storyboard_slide.get("chart_data") or {}
    if chart_data.get("title"):
        chart_title = chart_data["title"]
    elif page_type in CHART_PAGE_TYPES:
        chart_title = storyboard_slide.get("visual_direction", "")
    else:
        chart_title = ""

    ppt_slide = {
        "slide_no": storyboard_slide.get("slide_no", 0),
        "slide_key": slide_key,
        "selected_page_type": page_type,
        "slide_title": storyboard_slide.get("headline", ""),
        "main_takeaway": storyboard_slide.get("main_message", ""),
        "content": storyboard_slide.get("body_copy", {}),
        "chart_title": chart_title,
        "source_footer": storyboard_slide.get("source_note", ""),
        "speaker_note": "",
    }

    return ppt_slide


def convert_rules(template_binding: dict) -> dict:
    """Convert template_binding → ppt_copy rules block."""
    return {
        "active_slide_keys_only": True,
        "controlled_layout_variants": {
            "market_size_segmentation": ["chart_page", "chart_plus_mini_table_page"],
            "competitive_landscape": ["compare_table_page", "matrix_page"],
            "industry_trends_future_evolution": ["trend_page", "timeline_page"],
        },
        "slide_02_table_fields_only_active_for_chart_plus_mini_table_page": True,
        "inactive_variant_fields_may_remain_blank": True,
        "selected_page_type_required_for_variant_slides": True,
        "title_should_be_conclusion_led": True,
        "takeaway_one_sentence_only": True,
        "content_fields_should_follow_ppt_copy_mapping": True,
        "content_fields_should_match_ppt_mapping_roles": True,
        "source_footer_required": True,
    }


def validate_variant_consistency(slides: list, template_binding: dict) -> tuple[list[str], dict[int, str]]:
    """Check slide-level page types against template_binding without mutating input."""
    warnings = []
    normalized_page_types = {}
    variant_map = {
        2: ("slide_2_variant", ["chart_page", "chart_plus_mini_table_page"]),
        6: ("slide_6_variant", ["compare_table_page", "matrix_page"]),
        7: ("slide_7_variant", ["trend_page", "timeline_page"]),
    }

    for slide in slides:
        slide_no = slide.get("slide_no", 0)
        if slide_no in variant_map:
            binding_key, valid_types = variant_map[slide_no]
            expected = template_binding.get(binding_key, "")
            actual = slide.get("selected_page_type", "")
            if expected and expected not in valid_types:
                raise ValueError(
                    f"Slide {slide_no}: template_binding.{binding_key}='{expected}' is invalid. "
                    f"Allowed values: {', '.join(valid_types)}."
                )
            if expected and actual and expected != actual:
                warnings.append(
                    f"Slide {slide_no}: selected_page_type '{actual}' does not match "
                    f"template_binding.{binding_key} '{expected}'. Using template_binding value."
                )
                normalized_page_types[slide_no] = expected
    return warnings, normalized_page_types


def validate_content_fields(slides: list) -> list[str]:
    """Check that storyboard body_copy contains active fields for the selected layout."""
    warnings = []
    for slide in slides:
        slide_no = slide.get("slide_no", 0)
        page_type = slide.get("selected_page_type", "")
        body_copy = slide.get("body_copy") or {}
        expected_by_type = EXPECTED_CONTENT_FIELDS.get(slide_no, {})
        expected_fields = expected_by_type.get(page_type)
        if expected_fields is None:
            warnings.append(
                f"Slide {slide_no}: no expected content-field contract for page type '{page_type}'."
            )
            continue

        missing_fields = [field for field in expected_fields if field not in body_copy]
        empty_fields = [
            field
            for field in expected_fields
            if field in body_copy and str(body_copy.get(field, "")).strip() == ""
        ]
        extra_fields = sorted(set(body_copy.keys()) - set(expected_fields))

        if missing_fields:
            warnings.append(
                f"Slide {slide_no} ({page_type}): missing active body_copy fields: "
                f"{', '.join(missing_fields)}."
            )
        if empty_fields:
            warnings.append(
                f"Slide {slide_no} ({page_type}): empty active body_copy fields: "
                f"{', '.join(empty_fields)}."
            )
        if extra_fields:
            warnings.append(
                f"Slide {slide_no} ({page_type}): extra body_copy fields ignored by active layout: "
                f"{', '.join(extra_fields)}."
            )
    return warnings


def build_ppt_copy(storyboard: dict) -> dict:
    template_binding = storyboard.get("template_binding", {})
    storyboard_slides = storyboard.get("slides", [])

    warnings, normalized_page_types = validate_variant_consistency(storyboard_slides, template_binding)
    normalized_slides = copy.deepcopy(storyboard_slides)
    for slide in normalized_slides:
        slide_no = int(slide.get("slide_no", 0) or 0)
        if slide_no in normalized_page_types:
            slide["selected_page_type"] = normalized_page_types[slide_no]
    warnings.extend(validate_content_fields(normalized_slides))

    ppt_copy = {
        "meta": convert_meta(storyboard),
        "ppt_copy_slides": [convert_slide(s) for s in normalized_slides],
        "rules": convert_rules(template_binding),
    }

    return {"ppt_copy": ppt_copy, "warnings": warnings}


def convert(storyboard_path: Path, output_path: Path) -> dict:
    """Main conversion: storyboard → ppt_copy."""
    storyboard = load_json(storyboard_path)
    result = build_ppt_copy(storyboard)
    save_json(result["ppt_copy"], output_path)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Convert industry_storyboard.json to industry_section_ppt_copy.json (structural bootstrap)."
    )
    parser.add_argument(
        "--storyboard",
        default="industry_storyboard.json",
        help="Path to industry_storyboard.json.",
    )
    parser.add_argument(
        "--output",
        default="industry_section_ppt_copy.json",
        help="Path to write the ppt_copy JSON.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate variant consistency, do not write output.",
    )
    parser.add_argument(
        "--strict-content",
        action="store_true",
        help="Fail when selected layouts are missing active body_copy fields.",
    )
    args = parser.parse_args()

    storyboard_path = Path(args.storyboard)
    if not storyboard_path.exists():
        print(f"ERROR: storyboard file not found: {storyboard_path}", file=sys.stderr)
        sys.exit(1)

    storyboard = load_json(storyboard_path)
    result = build_ppt_copy(storyboard)

    if result["warnings"]:
        print("WARNINGS:")
        for w in result["warnings"]:
            print(f"  - {w}")
        strict_failures = [
            w
            for w in result["warnings"]
            if (
                "missing active body_copy fields" in w
                or "empty active body_copy fields" in w
                or "no expected content-field contract" in w
            )
        ]
        if args.strict_content and strict_failures:
            print("ERROR: strict content validation failed.", file=sys.stderr)
            sys.exit(1)

    if not args.validate_only:
        save_json(result["ppt_copy"], Path(args.output))
        print(f"ppt_copy written to: {args.output}")
        print(
            "NOTE: body_copy → content is passed through directly. "
            "If your storyboard uses non-canonical body_copy keys, run the finalize LLM step."
        )


if __name__ == "__main__":
    main()
