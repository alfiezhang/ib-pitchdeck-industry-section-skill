#!/usr/bin/env python3
"""
Internal token-source adapter for renderer_spec.json.

For standard renderer runs, the expected contract is:
  - slide.body_copy already uses token-compatible field names
  - selected_page_type is final
  - chart_data / source_note / headline / main_message are final

This script handles the deterministic conversion into the token source consumed
by the fixed-template replacement dictionary:
  - section_meta → meta block
  - slide_no, selected_page_type → slide_no, selected_page_type
  - headline → slide_title
  - main_message → main_takeaway
  - body_copy → content (pass-through)
  - source_note → source_footer
  - chart_data.title (preferred) or visual_direction → chart_title
  - template_binding → rules block

Do not call this script as a workflow step. The formal pipeline derives the
replacement dictionary directly from `renderer_spec.json`.
"""

import copy
import json
from pathlib import Path

from compare_table_utils import normalize_compare_table_payload
from json_utils import load_json_file
from slide_registry import controlled_layout_variants, load_slide_registry, variant_page_types


SLIDE_REGISTRY = load_slide_registry()


def _clean_source_footer(source_note: str) -> str:
    """Strip leading 'Sources:'/'Sources：' prefix since the PPT template already has a static 'Sources' label."""
    if not source_note:
        return source_note
    import re
    cleaned = re.sub(
        r"^(?:Sources\s*[:：]?\s*)+",
        "",
        source_note,
        flags=re.IGNORECASE,
    ).strip()
    return cleaned if cleaned else source_note


SLIDE_KEY_MAP = {
    "industry_overview": "industry_overview",
    "market_size_segmentation": "market_size_segmentation",
    "growth_drivers": "key_industry_drivers",
    "value_chain_profit_pool": "value_chain_profit_pool",
    "barriers_value_drivers": "key_barriers_value_drivers",
    "competitive_landscape": "competitive_landscape",
    "industry_trends_future_evolution": "industry_trends_future_evolution",
    "transaction_implications": "transaction_implications",
}

# Page types that render quantitative charts. All others get chart_title cleared.
CHART_PAGE_TYPES = {"industry_overview_dynamic_page", "chart_page", "chart_plus_mini_table_page"}

EXPECTED_CONTENT_FIELDS = {
    1: {
        "industry_overview_dynamic_page": ["bullet_1", "bullet_2", "bullet_3"],
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
        "driver_card_5_page": ["card_1", "card_2", "card_3", "card_4", "card_5"],
        "driver_card_6_page": ["card_1", "card_2", "card_3", "card_4", "card_5", "card_6"],
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
        "trend_4_card_page": ["card_1", "card_2", "card_3", "card_4"],
        "trend_5_card_page": ["card_1", "card_2", "card_3", "card_4", "card_5"],
        "trend_6_card_page": ["card_1", "card_2", "card_3", "card_4", "card_5", "card_6"],
    },
    8: {
        "summary_page": ["left_panel", "right_top", "right_mid", "right_bottom"],
    },
}


def load_json(path: Path) -> dict:
    return load_json_file(path)


def convert_meta(renderer_spec: dict) -> dict:
    """Convert section_meta into the token-source meta block."""
    meta = renderer_spec.get("section_meta", {})
    return {
        "target_company": meta.get("target_name", ""),
        "transaction_type": "",
        "industry": meta.get("industry", ""),
        "subsector": "",
        "geography": meta.get("geography", ""),
        "language": "English" if meta.get("language") == "en" else "Chinese",
    }


def convert_slide(renderer_slide: dict) -> dict:
    """Convert a renderer spec slide into a token-source slide."""
    slide_role = renderer_slide.get("slide_role", "")
    slide_key = SLIDE_KEY_MAP.get(slide_role, slide_role)
    page_type = renderer_slide.get("selected_page_type", "")

    # Validate page type consistency with template_binding
    # (caller should pass template_binding for cross-validation)

    # Auto-resolve chart_title:
    # - Has chart_data with title → use it (metric cards, bar charts, etc.)
    # - Chart page type without chart_data → fallback to visual_direction
    # - Non-chart page type without chart_data → clear (visual_direction is execution notes)
    chart_data = renderer_slide.get("chart_data") or {}
    if chart_data.get("title"):
        chart_title = chart_data["title"]
    elif page_type in CHART_PAGE_TYPES:
        chart_title = renderer_slide.get("visual_direction", "")
    else:
        chart_title = ""

    content = copy.deepcopy(renderer_slide.get("body_copy", {}) or {})
    if page_type == "compare_table_page":
        headers, rows = normalize_compare_table_payload(renderer_slide)
        if headers:
            content["table_header"] = "｜".join(headers)
        for idx, row_cells in enumerate(rows[:6], start=1):
            content[f"table_row_{idx}"] = "｜".join(row_cells)

    ppt_slide = {
        "slide_no": renderer_slide.get("slide_no", 0),
        "slide_key": slide_key,
        "selected_page_type": page_type,
        "slide_title": renderer_slide.get("headline", ""),
        "main_takeaway": renderer_slide.get("main_message", ""),
        "content": content,
        "chart_title": chart_title,
        "source_footer": _clean_source_footer(renderer_slide.get("source_note", "")),
        "speaker_note": "",
    }

    return ppt_slide


def convert_rules(template_binding: dict) -> dict:
    """Convert template_binding into token-source execution rules."""
    return {
        "active_slide_keys_only": True,
        "controlled_layout_variants": controlled_layout_variants(SLIDE_REGISTRY),
        "slide_02_table_fields_only_active_for_chart_plus_mini_table_page": True,
        "inactive_variant_fields_may_remain_blank": True,
        "selected_page_type_required_for_variant_slides": True,
        "title_should_be_conclusion_led": True,
        "takeaway_one_sentence_only": True,
        "content_fields_should_follow_slide_registry": True,
        "content_fields_should_match_ppt_mapping_roles": True,
        "source_footer_required": True,
    }


def validate_variant_consistency(slides: list, template_binding: dict) -> tuple[list[str], dict[int, str]]:
    """Check slide-level page types against template_binding without mutating input."""
    warnings = []
    normalized_page_types = {}
    variant_map = {
        slide_no: (binding_key, sorted(valid_types))
        for slide_no, (binding_key, valid_types) in variant_page_types(SLIDE_REGISTRY).items()
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
    """Check that token-source content contains active fields for the selected layout."""
    warnings = []
    for slide in slides:
        slide_no = slide.get("slide_no", 0)
        page_type = slide.get("selected_page_type", "")
        body_copy = slide.get("content") or slide.get("body_copy") or {}
        expected_by_type = EXPECTED_CONTENT_FIELDS.get(slide_no, {})
        expected_fields = expected_by_type.get(page_type)
        if expected_fields is None:
            warnings.append(
                f"Slide {slide_no}: no expected content-field contract for page type '{page_type}'."
            )
            continue
        if slide_no == 6 and page_type == "compare_table_page":
            populated_rows = [
                field
                for field in [f"table_row_{idx}" for idx in range(1, 7)]
                if str(body_copy.get(field, "")).strip()
            ]
            if len(populated_rows) >= 3:
                missing_row_fields = [
                    field
                    for field in [f"table_row_{idx}" for idx in range(1, 7)]
                    if field not in populated_rows
                ]
                expected_fields = [
                    field
                    for field in expected_fields
                    if field not in missing_row_fields
                ]

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


def build_token_source(renderer_spec: dict) -> dict:
    template_binding = renderer_spec.get("template_binding", {})
    renderer_slides = renderer_spec.get("slides", [])

    warnings, normalized_page_types = validate_variant_consistency(renderer_slides, template_binding)
    normalized_slides = copy.deepcopy(renderer_slides)
    for slide in normalized_slides:
        slide_no = int(slide.get("slide_no", 0) or 0)
        if slide_no in normalized_page_types:
            slide["selected_page_type"] = normalized_page_types[slide_no]
    converted_slides = [convert_slide(s) for s in normalized_slides]
    warnings.extend(validate_content_fields(converted_slides))

    token_source = {
        "meta": convert_meta(renderer_spec),
        "slides": converted_slides,
        "rules": convert_rules(template_binding),
    }

    return {"token_source": token_source, "warnings": warnings}
