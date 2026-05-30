#!/usr/bin/env python3
"""Validate industry_storyboard.json before deterministic PPT execution."""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional, Union

from convert_storyboard_to_ppt_copy import EXPECTED_CONTENT_FIELDS
from json_utils import load_json_file
from validation_common import (
    check_main_message_terminal_punctuation,
    estimate_lines,
    is_blank,
    layout_budget_findings,
    split_table_cells,
)


DEFAULT_LAYOUT_BUDGET_PATH = Path(__file__).resolve().parents[1] / "templates" / "layout_budget.json"


FIXED_PAGE_TYPES = {
    1: "summary_page",
    4: "value_chain_page",
    5: "moat_page",
    8: "summary_page",
}

VARIANT_PAGE_TYPES = {
    2: ("slide_2_variant", {"chart_page", "chart_plus_mini_table_page"}),
    3: ("slide_3_variant", {"driver_card_page", "driver_card_5_page", "driver_card_6_page"}),
    6: ("slide_6_variant", {"compare_table_page", "matrix_page"}),
    7: (
        "slide_7_variant",
        {"trend_page", "timeline_page", "trend_4_card_page", "trend_5_card_page", "trend_6_card_page"},
    ),
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
    "slide_story_contract",
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
RELEVANCE_LEVELS = {"sector_credibility", "transaction_relevance", "target_implication", "mixed"}
TARGET_LINK_TYPES = {"light", "selective", "central"}
CLAIM_STRENGTHS = {"hard_fact", "supported_inference", "management_claim", "hypothesis"}

EXPECTED_ROLES = {
    1: "industry_overview",
    2: "market_size_segmentation",
    3: "key_industry_drivers",
    4: "value_chain_profit_pool",
    5: "key_barriers_value_drivers",
    6: "competitive_landscape",
    7: "industry_trends_future_evolution",
    8: "key_takeaways_for_target",
}

# Slides 1-7 are industry structure pages; target should not be the central claim.
# Slide 8 is the conclusion page where central target linkage is appropriate.
ALLOWED_TARGET_LINK_TYPES_PER_SLIDE = {
    1: {"light", "selective"},
    2: {"light", "selective"},
    3: {"light", "selective"},
    4: {"light", "selective"},
    5: {"light", "selective"},
    6: {"light", "selective"},
    7: {"light", "selective"},
    8: {"selective", "central"},
}


def load_json(path: Path) -> dict:
    return load_json_file(path)


def add_missing(errors: list[str], prefix: str, obj: dict, required: set[str]) -> None:
    missing = sorted(required - set(obj.keys()))
    if missing:
        errors.append(f"{prefix}: missing required fields: {', '.join(missing)}")

def check_layout_budget(
    slide_no: int,
    page_type: str,
    body_copy: dict,
    layout_budget: Optional[dict],
    errors: list[str],
    warnings: list[str],
) -> None:
    budget_errors, budget_warnings = layout_budget_findings(body_copy, slide_no, page_type, layout_budget)
    errors.extend(budget_errors)
    warnings.extend(budget_warnings)


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
            slide_1_visual = layout_budget.get("slide_budgets", {}).get("1:summary_page", {}).get("slide_1_visual", {})
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


def check_storyline_contract(
    slide: dict,
    errors: list[str],
    warnings: list[str],
) -> None:
    """Validate slide_story_contract: structure, forbidden_topics enforcement, title consistency."""
    slide_no = slide.get("slide_no")
    contract = slide.get("slide_story_contract")
    if not isinstance(contract, dict):
        errors.append(f"slide {slide_no}: slide_story_contract is required and must be an object")
        return

    # 1. Check required contract fields
    for field in (
        "question",
        "answer",
        "primary_relevance_level",
        "target_link_type",
        "claim_strength",
        "evidence_ids",
        "forbidden_topics",
        "visual_role",
    ):
        if field not in contract:
            errors.append(f"slide {slide_no}: slide_story_contract.{field} is required")

    relevance_level = contract.get("primary_relevance_level")
    if relevance_level and relevance_level not in RELEVANCE_LEVELS:
        errors.append(
            f"slide {slide_no}: slide_story_contract.primary_relevance_level must be one of "
            f"{sorted(RELEVANCE_LEVELS)}, found {relevance_level!r}"
        )
    target_link_type = contract.get("target_link_type")
    if target_link_type and target_link_type not in TARGET_LINK_TYPES:
        errors.append(
            f"slide {slide_no}: slide_story_contract.target_link_type must be one of "
            f"{sorted(TARGET_LINK_TYPES)}, found {target_link_type!r}"
        )
    if target_link_type and slide_no in ALLOWED_TARGET_LINK_TYPES_PER_SLIDE:
        allowed = ALLOWED_TARGET_LINK_TYPES_PER_SLIDE[slide_no]
        if target_link_type not in allowed:
            errors.append(
                f"slide {slide_no}: target_link_type '{target_link_type}' is not allowed for this slide role; "
                f"allowed: {sorted(allowed)}. Industry structure slides (1-7) cannot use 'central'."
            )
    claim_strength = contract.get("claim_strength")
    if claim_strength and claim_strength not in CLAIM_STRENGTHS:
        errors.append(
            f"slide {slide_no}: slide_story_contract.claim_strength must be one of "
            f"{sorted(CLAIM_STRENGTHS)}, found {claim_strength!r}"
        )

    question = contract.get("question", "")
    if isinstance(question, str) and question.count("?") > 1:
        warnings.append(
            f"slide {slide_no}: slide_story_contract.question contains multiple '?'; "
            f"each slide should answer exactly one question"
        )

    evidence_ids = contract.get("evidence_ids", [])
    if isinstance(evidence_ids, list) and len(set(str(item) for item in evidence_ids if item)) < 2:
        errors.append(f"slide {slide_no}: slide_story_contract.evidence_ids must have at least 2 distinct items")

    # 2. Forbidden_topics enforcement — check if body_copy contains forbidden content
    forbidden = contract.get("forbidden_topics", [])
    body_copy = slide.get("body_copy", {})
    if isinstance(forbidden, list) and isinstance(body_copy, dict):
        body_text = " ".join(str(v) for v in body_copy.values() if isinstance(v, str)).lower()
        for topic in forbidden:
            if isinstance(topic, str) and topic.lower() in body_text:
                warnings.append(
                    f"slide {slide_no}: body_copy contains forbidden topic '{topic}' "
                    f"from slide_story_contract; this violates MECE boundaries"
                )

    # 3. Title number consistency — check if headline/main_message promises N items
    #    but body_copy has fewer items
    headline = str(slide.get("headline", ""))
    main_message = str(slide.get("main_message", ""))
    # Detect explicit enumeration promises only. Do not match data such as "¥500亿" or "3-year CAGR".
    en_nums = {"three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}
    number_pattern = re.compile(
        r"(?:"
        r"([一二三四五六七八九十])\s*大\s*(?:核心|关键|主要|增长|结构性|行业|未来|交易|投资)?\s*(?:趋势|驱动|因素|逻辑|看点|变化|启示|机会|壁垒)|"
        r"(\d+)\s*(?:个|大)\s*(?:核心|关键|主要|增长|结构性|行业|未来|交易|投资)?\s*(?:趋势|驱动|因素|逻辑|看点|变化|启示|机会|壁垒)|"
        r"(three|four|five|six|seven)\s+(?:key|major|critical)?\s*(?:drivers|trends|factors|themes|takeaways|implications|barriers)"
        r")",
        re.IGNORECASE,
    )
    for text_field, text_value in [("headline", headline), ("main_message", main_message)]:
        match = number_pattern.search(text_value)
        if match:
            # Extract promised count
            if match.group(1):
                cn_nums = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
                promised = cn_nums.get(match.group(1), 0)
            else:
                try:
                    promised = int(match.group(2)) if match.group(2) else en_nums.get(match.group(3).lower(), 0)
                except (TypeError, ValueError):
                    promised = 0

            if promised > 0:
                # Count body_copy items that look like content slots (card_*, bullet_*, stage_*, table_row_*)
                content_fields = [
                    k for k in (body_copy.keys() if isinstance(body_copy, dict) else [])
                    if any(k.startswith(prefix) for prefix in ("card_", "bullet_", "stage_", "point_", "table_row_"))
                ]
                # For trend_page/timeline_page, count non-empty content fields
                filled_count = sum(
                    1 for k in content_fields
                    if isinstance(body_copy.get(k), str) and body_copy.get(k, "").strip()
                )
                if filled_count > 0 and promised > filled_count:
                    warnings.append(
                        f"slide {slide_no}: {text_field} promises {promised} items "
                        f"but body_copy has only {filled_count} filled content slots; "
                        f"title must not over-promise what the page can carry"
                    )

    # 4. target_link_type vs target_link consistency
    #    If target_link_type is "light", the target_link should not use promotional language
    #    that implies the target is the central subject.
    target_link_type = contract.get("target_link_type")
    target_link = str(slide.get("target_link") or "")
    if target_link_type == "light" and target_link:
        promotional_markers = [
            "护城河", "显著优势", "领先", "最强", "最优", "核心竞争力",
            "moat", "dominant", "best-in-class", "superior", "competitive advantage",
        ]
        target_link_lower = target_link.lower()
        found = [m for m in promotional_markers if m in target_link_lower]
        if found:
            warnings.append(
                f"slide {slide_no}: target_link_type is 'light' but target_link contains "
                f"promotional language ({', '.join(found[:3])}); "
                f"use contextual or evidence-based framing for light target linkage"
            )


def check_compare_table_structure(
    slide: dict,
    warnings: list[str],
) -> None:
    """Check that compare_table rows are structurally consistent with the header."""
    slide_no = slide.get("slide_no")
    page_type = slide.get("selected_page_type", "")
    if page_type != "compare_table_page":
        return

    body_copy = slide.get("body_copy", {})
    if not isinstance(body_copy, dict):
        return

    header = body_copy.get("table_header", "")
    header_cells = split_table_cells(header) if isinstance(header, str) else []
    expected_columns = len(header_cells)
    if expected_columns < 2:
        return

    rows: list[tuple[str, list[str]]] = []
    for key in sorted(body_copy.keys()):
        if key.startswith("table_row_") and isinstance(body_copy.get(key), str) and body_copy[key].strip():
            rows.append((key, split_table_cells(body_copy[key])))

    if len(rows) < 2:
        return

    inconsistent = [
        f"{key}({len(cells)}/{expected_columns})"
        for key, cells in rows
        if len(cells) != expected_columns or any(not str(cell).strip() for cell in cells)
    ]
    if inconsistent:
        warnings.append(
            f"slide {slide_no}: compare_table rows must match the table_header structure; "
            f"inconsistent rows: {', '.join(inconsistent[:4])}. "
            f"Move summary conclusions or CRx commentary to the right-side insight panel instead of partial table rows."
        )


def check_storyline_coverage(
    slides: list[dict],
    errors: list[str],
    warnings: list[str],
) -> None:
    """Check storyline coverage: role completeness, contract validation, structural checks."""
    # 1. Role completeness and mapping
    seen_roles: dict[str, int] = {}
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        slide_no = slide.get("slide_no")
        role = slide.get("slide_role", "")
        seen_roles[role] = slide_no

        expected_role = EXPECTED_ROLES.get(slide_no)
        if expected_role and role != expected_role:
            errors.append(
                f"slide {slide_no}: slide_role must be '{expected_role}', found '{role}'"
            )

    missing_roles = set(EXPECTED_ROLES.values()) - set(seen_roles.keys())
    if missing_roles:
        errors.append(f"missing slide roles: {', '.join(sorted(missing_roles))}")

    sector_count = 0
    transaction_count = 0
    target_count = 0
    target_central_count = 0
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        contract = slide.get("slide_story_contract", {})
        if not isinstance(contract, dict):
            continue
        level = contract.get("primary_relevance_level")
        target_link_type = contract.get("target_link_type")
        if level in {"sector_credibility", "mixed"}:
            sector_count += 1
        if level in {"transaction_relevance", "mixed"}:
            transaction_count += 1
        if level in {"target_implication", "mixed"} or target_link_type in {"selective", "central"}:
            target_count += 1
        if target_link_type == "central":
            target_central_count += 1

    if sector_count < 3:
        errors.append(
            f"pre-mandate relevance coverage: only {sector_count} slide(s) build sector credibility; expected at least 3"
        )
    if transaction_count < 2:
        errors.append(
            f"pre-mandate relevance coverage: only {transaction_count} slide(s) explain transaction relevance; expected at least 2"
        )
    if target_count < 2:
        errors.append(
            f"pre-mandate relevance coverage: only {target_count} slide(s) include target implication; expected at least 2"
        )
    if target_central_count > 4:
        errors.append(
            f"pre-mandate relevance balance: {target_central_count} slide(s) are target-central; no more than 4 should make the target the central claim"
        )

    # 2. Per-slide structural checks
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        check_storyline_contract(slide, errors, warnings)
        check_compare_table_structure(slide, warnings)


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
        punctuation_error = check_main_message_terminal_punctuation(
            str(slide.get("main_message") or ""),
            slide_no,
            layout_budget,
        )
        if punctuation_error:
            errors.append(punctuation_error)
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
                    errors.append(f"slide {slide_no}: extra body_copy fields ignored by active layout: {', '.join(extra)}")
                check_layout_budget(slide_no, page_type, body_copy, layout_budget, errors, warnings)

        validate_chart_data(slide, errors, warnings, layout_budget)

    expected_numbers = list(range(1, 9))
    if sorted(seen) != expected_numbers:
        errors.append(f"slides must be numbered 1-8 exactly; found {seen}")

    # Storyline coverage: role completeness, role-slide mapping, MECE overlap
    check_storyline_coverage(slides, errors, warnings)

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


def _schema_type_matches(value, expected_type: Union[str, list[str]]) -> bool:
    if isinstance(expected_type, list):
        return any(_schema_type_matches(value, item) for item in expected_type)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    return True


def validate_schema_subset(value, schema: dict, path: str, errors: list[str]) -> None:
    """Validate the JSON Schema subset used by templates/storyboard_schema.json."""
    if "$ref" in schema:
        errors.append(f"{path}: $ref is not supported by this lightweight schema validator")
        return

    all_of = schema.get("allOf")
    if isinstance(all_of, list):
        for idx, option in enumerate(all_of):
            if isinstance(option, dict):
                validate_schema_subset(value, option, f"{path}.allOf[{idx}]", errors)

    any_of = schema.get("anyOf")
    if isinstance(any_of, list):
        match_count = 0
        for option in any_of:
            option_errors: list[str] = []
            if isinstance(option, dict):
                validate_schema_subset(value, option, path, option_errors)
                if not option_errors:
                    match_count += 1
        if match_count < 1:
            errors.append(f"{path}: value does not match any allowed schema option")
        return

    not_schema = schema.get("not")
    if isinstance(not_schema, dict):
        option_errors: list[str] = []
        validate_schema_subset(value, not_schema, path, option_errors)
        if not option_errors:
            errors.append(f"{path}: value matches schema forbidden by 'not'")
            return

    one_of = schema.get("oneOf")
    if isinstance(one_of, list):
        match_count = 0
        for option in one_of:
            option_errors: list[str] = []
            if isinstance(option, dict):
                validate_schema_subset(value, option, path, option_errors)
                if not option_errors:
                    match_count += 1
        if match_count != 1:
            errors.append(f"{path}: value does not match exactly one allowed schema option")
        return

    expected_type = schema.get("type")
    if expected_type and not _schema_type_matches(value, expected_type):
        errors.append(f"{path}: expected {expected_type}, found {type(value).__name__}")
        return

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value {value!r} is not one of {schema['enum']}")
        return

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}.{key}: missing required field")
        properties = schema.get("properties", {})
        for key, child_schema in properties.items():
            if key in value and isinstance(child_schema, dict):
                validate_schema_subset(value[key], child_schema, f"{path}.{key}", errors)
        pattern_properties = schema.get("patternProperties", {})
        matched_by_pattern: set[str] = set()
        if isinstance(pattern_properties, dict):
            for pattern, child_schema in pattern_properties.items():
                try:
                    compiled = re.compile(pattern)
                except re.error as exc:
                    errors.append(f"{path}: invalid patternProperties regex {pattern!r}: {exc}")
                    continue
                for key in value:
                    if key in properties:
                        continue
                    if compiled.search(str(key)):
                        matched_by_pattern.add(key)
                        if isinstance(child_schema, dict):
                            validate_schema_subset(value[key], child_schema, f"{path}.{key}", errors)

        additional_properties = schema.get("additionalProperties")
        if additional_properties is False:
            allowed_keys = set(properties)
            for key in value:
                if key not in allowed_keys and key not in matched_by_pattern:
                    errors.append(f"{path}.{key}: additional property is not allowed")
        elif isinstance(additional_properties, dict):
            allowed_keys = set(properties) | matched_by_pattern
            for key in value:
                if key not in allowed_keys:
                    validate_schema_subset(value[key], additional_properties, f"{path}.{key}", errors)

    if isinstance(value, list):
        min_items = schema.get("minItems")
        max_items = schema.get("maxItems")
        if isinstance(min_items, int) and len(value) < min_items:
            errors.append(f"{path}: expected at least {min_items} items, found {len(value)}")
        if isinstance(max_items, int) and len(value) > max_items:
            errors.append(f"{path}: expected at most {max_items} items, found {len(value)}")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for idx, item in enumerate(value):
                validate_schema_subset(item, item_schema, f"{path}[{idx}]", errors)

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if isinstance(minimum, (int, float)) and value < minimum:
            errors.append(f"{path}: value {value} is below minimum {minimum}")
        if isinstance(maximum, (int, float)) and value > maximum:
            errors.append(f"{path}: value {value} is above maximum {maximum}")


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

    if schema_path:
        if not schema_path.exists():
            errors.append(f"schema file not found: {schema_path}")
        else:
            try:
                schema = load_json(schema_path)
                validate_schema_subset(storyboard, schema, "storyboard", errors)
            except Exception as exc:
                errors.append(f"cannot validate schema {schema_path}: {exc}")

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
