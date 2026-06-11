#!/usr/bin/env python3
"""Validate content quality of renderer_spec.json against the research pack and quality rules.

Density and generic-copy findings are advisory by default. Source-quality findings are blocking by
default because weak or generic attributions can make unsupported facts look diligence-grade.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

from json_utils import load_json_file
from metric_scope_utils import SCOPE_FIELDS, normalize_scope_value
from qc_repair_targets import normalize_repair_issue
from validation_common import (
    approx_units_to_chars,
    check_main_message_terminal_punctuation,
    display_units,
    estimate_lines,
    unique_preserve_order,
    is_blank,
    layout_budget_findings,
)


DEFAULT_LAYOUT_BUDGET_PATH = Path(__file__).resolve().parents[1] / "templates" / "layout_budget.json"
DEFAULT_DRILLDOWN_ROLE_LIBRARY_PATH = Path(__file__).resolve().parents[1] / "templates" / "drilldown_role_library.json"
# ── Helpers ──────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    return load_json_file(path)


def load_text(path: Path) -> str:
    with path.open("r", encoding="utf-8") as f:
        return f.read()


def load_drilldown_role_ids(path: Path = DEFAULT_DRILLDOWN_ROLE_LIBRARY_PATH) -> set[str]:
    try:
        data = load_json(path)
    except FileNotFoundError:
        return set()
    roles = data.get("roles", [])
    if not isinstance(roles, list):
        return set()
    return {
        str(role.get("role_id") or "").strip()
        for role in roles
        if isinstance(role, dict) and str(role.get("role_id") or "").strip()
    }


def normalize(s: str) -> str:
    """Lowercase and strip for phrase matching."""
    return s.strip().lower()

def check_layout_budget(
    body_copy: dict,
    slide_no: int,
    page_type: str,
    layout_budget: dict,
    warnings: list[str],
    blocking_issues: list[str],
) -> None:
    budget_errors, budget_warnings = layout_budget_findings(body_copy, slide_no, page_type, layout_budget)
    for message in budget_errors:
        warnings.append(message)
        blocking_issues.append(message)
    warnings.extend(budget_warnings)


# ── Density checks ───────────────────────────────────────────────

def check_field_density(
    field_name: str,
    field_value: str,
    rules: dict,
    slide_no: int,
    warnings: list[str],
) -> None:
    """Check if a body_copy field is shorter than the configured minimum."""
    min_chars = rules.get("min_chars_by_field_type", {})

    # Map common field name patterns to rule keys
    if any(kw in field_name.lower() for kw in ("title", "headline")):
        key = "title"
    elif any(kw in field_name.lower() for kw in ("takeaway", "main_message")):
        key = "main_takeaway"
    elif any(kw in field_name.lower() for kw in ("bullet", "point")):
        key = "bullet"
    elif any(kw in field_name.lower() for kw in ("card",)):
        key = "card"
    elif any(kw in field_name.lower() for kw in ("panel",)):
        key = "panel"
    elif any(kw in field_name.lower() for kw in ("table_row",)):
        key = "table_row"
    elif any(kw in field_name.lower() for kw in ("timeline", "stage")):
        key = "timeline_stage"
    elif any(kw in field_name.lower() for kw in ("source", "footer", "attribution")):
        key = "source_footer"
    else:
        return  # Unknown field type, skip density check

    threshold = min_chars.get(key)
    if threshold and len(field_value.strip()) < threshold:
        warnings.append(
            f"slide {slide_no}: '{field_name}' is {len(field_value.strip())} chars "
            f"(min recommended: {threshold} chars)"
        )


def check_text_fit(
    text: str,
    renderer_field: str,
    slide_no: int,
    page_type: str,
    text_fit_rules: dict,
    warnings: list[str],
    blocking_issues: list[str],
) -> None:
    aliases = text_fit_rules.get("renderer_field_aliases", {})
    field_name = aliases.get(renderer_field, renderer_field)
    rule = text_fit_rules.get("fields", {}).get(f"{slide_no}:{page_type}:{field_name}")
    if not rule:
        return
    max_line_units = float(rule.get("max_line_units") or 0)
    actual_lines = estimate_lines(text, max_line_units)
    target_lines = int(rule.get("target_lines") or 0)
    max_lines = int(rule.get("max_lines") or 0)
    placeholder = rule.get("placeholder", "")
    if target_lines and actual_lines > target_lines:
        overage = max(0.0, display_units(text) - (target_lines * max_line_units))
        warnings.append(
            f"slide {slide_no}: '{renderer_field}' estimated at {actual_lines} line(s) "
            f"for {placeholder}; target is {target_lines} line(s); "
            f"reduce by ~{approx_units_to_chars(overage)} CJK char(s) to hit target"
        )
    if max_lines and actual_lines > max_lines:
        overage = max(0.0, display_units(text) - (max_lines * max_line_units))
        message = (
            f"slide {slide_no}: '{renderer_field}' estimated at {actual_lines} line(s) "
            f"for {placeholder}; max allowed is {max_lines} line(s); "
            f"reduce by ~{approx_units_to_chars(overage)} CJK char(s) or simplify the slide"
        )
        warnings.append(message)
        if rule.get("block_if_exceeds_max_lines", True):
            blocking_issues.append(message)


# ── Generic phrase checks ────────────────────────────────────────

def check_generic_phrases(
    text: str,
    generic_phrases: list[str],
    slide_no: int,
    field_name: str,
    warnings: list[str],
    phrase_category: str,
) -> None:
    """Check if text contains generic/banned phrases."""
    text_lower = normalize(text)
    for phrase in generic_phrases:
        if normalize(phrase) in text_lower:
            warnings.append(
                f"slide {slide_no}: {phrase_category} '{phrase}' found in '{field_name}'"
            )
            break  # One warning per field is enough


INLINE_SOURCE_RE = re.compile(
    r"[\(（][^()（）\n]*(?:EV-\d+|Source|source|来源|报告|年报|公告|research|Research|"
    r"[\u4e00-\u9fff]{2,}(?:协会|情报|咨询|研究院|药监局|年报|公告|数据|智库|证券|交易所|统计局)[^()（）\n]*\d{4})"
    r"[^()（）\n]*[\)）]"
)
EV_ID_RE = re.compile(r"\bEV-\d{3}\b")
METRIC_RE = re.compile(
    r"(?P<value>(?:(?:¥|RMB|USD)\s*\d+(?:\.\d+)?\s*(?:亿|万|bn|mn|billion|million)?)|"
    r"(?:\d+(?:\.\d+)?\s*(?:%|％|亿|万|bn|mn|billion|million)))",
    flags=re.IGNORECASE,
)
ARGUMENT_MECHANISM_RE = re.compile(
    r"driv|support|imply|because|therefore|target|margin|share|penetration|"
    r"驱动|支撑|意味着|因此|标的|利润|份额|渗透|增长|提升|降低|带来|"
    r"受益|压力|壁垒|集中|分散|渠道|价格带|复购|转化|估值|并购|买方",
    flags=re.IGNORECASE,
)


def check_inline_source_references(
    text: str,
    slide_no: int,
    field_name: str,
    warnings: list[str],
) -> None:
    if INLINE_SOURCE_RE.search(text):
        warnings.append(
            f"slide {slide_no}: inline source reference found in '{field_name}'; "
            "move source IDs/names to source_note/source_footer"
        )


def metric_signatures(text: str) -> list[str]:
    signatures: list[str] = []
    for match in METRIC_RE.finditer(text):
        value = re.sub(r"\s+", "", match.group("value"))
        if value:
            signatures.append(value)
    return signatures


def collect_slide_text_fields(slide: dict) -> list[tuple[str, str]]:
    """Collect (field_name, text_value) pairs from headline, main_message, pitch_relevance, and body_copy."""
    fields: list[tuple[str, str]] = []
    for field_name in ("headline", "main_message", "pitch_relevance"):
        value = slide.get(field_name)
        if isinstance(value, str):
            fields.append((field_name, value))
    body_copy = slide.get("body_copy", {})
    if isinstance(body_copy, dict):
        fields.extend((f"body_copy.{key}", value) for key, value in body_copy.items() if isinstance(value, str))
    return fields


def collect_slide_metric_signatures(slide: dict) -> set[str]:
    fields: list[str] = [value for _, value in collect_slide_text_fields(slide)]
    chart_data = slide.get("chart_data", {})
    if isinstance(chart_data, dict):
        fields.append(str(chart_data.get("title") or ""))
        fields.append(str(chart_data.get("notes") or ""))
        source_rows = chart_data.get("source_rows", [])
        if isinstance(source_rows, list):
            for row in source_rows:
                if isinstance(row, dict):
                    fields.extend(str(row.get(key) or "") for key in ("label", "value", "period", "note"))
    return set(metric_signatures(" ".join(fields)))


def check_body_length(
    text: str,
    slide_no: int,
    field_name: str,
    warnings: list[str],
    blocking_issues: Optional[list[str]] = None,
    max_units: float = 95.0,
) -> None:
    if display_units(text) > max_units:
        message = (
            f"slide {slide_no}: '{field_name}' is paragraph-like; review scanability, "
            "but do not delete evidence, mechanism, or implication depth solely to shorten body copy"
        )
        warnings.append(message)


def check_argument_density(
    slide: dict,
    rules: dict,
    warnings: list[str],
) -> None:
    """Check that PPT body fields carry actual arguments, not only topic labels."""
    checks = rules.get("required_renderer_checks", {})
    if not checks.get("argument_fields_should_include_mechanism_or_data", True):
        return

    slide_no = slide.get("slide_no")
    body_copy = slide.get("body_copy", {})
    if not isinstance(body_copy, dict):
        return

    argument_fields = []
    for field_name, value in body_copy.items():
        lowered = field_name.lower()
        if lowered.startswith(("table_", "matrix_label", "matrix_title")):
            continue
        if not isinstance(value, str) or not value.strip():
            continue
        argument_fields.append((field_name, value))

    if not argument_fields:
        return

    strong_fields = []
    for field_name, value in argument_fields:
        # Accept evidence IDs, numeric metrics, or mechanism / implication language.
        # Do not require colon/arrow punctuation; that made normal Chinese bullets
        # look weaker than they are and created noisy density warnings.
        if EV_ID_RE.search(value) or METRIC_RE.search(value) or ARGUMENT_MECHANISM_RE.search(value):
            strong_fields.append(field_name)
    min_fields = int(checks.get("argument_complexity_warning_threshold", 3))
    if len(strong_fields) < min(min_fields, len(argument_fields)):
        warnings.append(
            f"slide {slide_no}: only {len(strong_fields)} body_copy field(s) read as evidence-backed arguments; "
            f"consider simplifying secondary claims or using deck_blueprint proof points with label + judgment + data/mechanism/pitch relevance."
        )


def check_claim_strength_language(
    slide: dict,
    overclaim_phrases: list[str],
    warnings: list[str],
    blocking_issues: list[str],
) -> None:
    """Block absolute language that is incompatible with pitch materials."""
    slide_no = slide.get("slide_no")
    fields = collect_slide_text_fields(slide)

    findings: list[str] = []
    for field_name, value in fields:
        text_lower = normalize(value)
        for phrase in overclaim_phrases:
            if normalize(phrase) and normalize(phrase) in text_lower:
                findings.append(f"'{phrase}' in {field_name}")
                break
    if findings:
        shown = "; ".join(findings[:3])
        suffix = "" if len(findings) <= 3 else f"; plus {len(findings) - 3} more"
        message = (
            f"slide {slide_no}: hard-banned absolute language found: {shown}{suffix}. "
            "Use evidence-scoped wording instead of guaranteed, absolute, or impossible-to-disprove claims."
        )
        warnings.append(message)
        blocking_issues.append(message)


def check_cautious_language(
    slide: dict,
    cautious_phrases: list[str],
    advisory_warnings: list[str],
) -> None:
    """Flag contextual caution terms without making every pitch phrase a hard gate."""
    if not cautious_phrases:
        return
    slide_no = slide.get("slide_no")
    fields = collect_slide_text_fields(slide)

    findings: list[str] = []
    for field_name, value in fields:
        text_lower = normalize(value)
        for phrase in cautious_phrases:
            if normalize(phrase) and normalize(phrase) in text_lower:
                findings.append(f"'{phrase}' in {field_name}")
                break
    if findings:
        message = (
            f"slide {slide_no}: contextual caution phrasing found; confirm claim_strength/evidence support it: "
            + "; ".join(findings[:3])
        )
        advisory_warnings.append(message)


def _slide_policy_values(slide: dict) -> tuple[str, str]:
    return (
        str(slide.get("target_context_type") or "").strip(),
        str(slide.get("claim_strength") or "").strip(),
    )


def check_target_advocacy_language(
    slide: dict,
    target_advocacy_phrases: list[str],
    warnings: list[str],
    blocking_issues: list[str],
    advisory_warnings: list[str],
) -> None:
    """Block target-advocacy headlines where target context is not central and evidence-scoped."""
    if not target_advocacy_phrases:
        return
    slide_no = slide.get("slide_no")
    target_context_type, claim_strength = _slide_policy_values(slide)
    allowed_central_headline = slide_no == 8 and (
        not target_context_type or target_context_type in {"central", "selective"}
    )
    fields = collect_slide_text_fields(slide)

    blocking_findings: list[str] = []
    advisory_findings: list[str] = []
    for field_name, value in fields:
        text_lower = normalize(value)
        matched_phrase = ""
        for phrase in target_advocacy_phrases:
            if normalize(phrase) and normalize(phrase) in text_lower:
                matched_phrase = phrase
                break
        if not matched_phrase:
            continue
        if field_name in {"headline", "main_message"}:
            if not allowed_central_headline or claim_strength in {"management_claim", "hypothesis", "open_question", ""}:
                blocking_findings.append(f"'{matched_phrase}' in {field_name}")
            else:
                advisory_findings.append(f"'{matched_phrase}' in {field_name}")
        else:
            advisory_findings.append(f"'{matched_phrase}' in {field_name}")

    if blocking_findings:
        message = (
            f"slide {slide_no}: target-advocacy language appears in headline/main_message "
            f"while target_context_type='{target_context_type or 'missing'}', claim_strength='{claim_strength or 'missing'}': "
            + "; ".join(blocking_findings[:3])
            + ". Keep industry-page titles sector-first; reserve central target advocacy for evidence-scoped Slide 8."
        )
        warnings.append(message)
        blocking_issues.append(message)
    if advisory_findings:
        advisory_warnings.append(
            f"slide {slide_no}: target-context wording should remain evidence-scoped: "
            + "; ".join(advisory_findings[:3])
        )


def check_slide_specific_quality(
    slide: dict,
    rules: dict,
    warnings: list[str],
    blocking_issues: list[str],
) -> None:
    """Check slide-specific semantic constraints that are too contextual for schema validation."""
    slide_no = slide.get("slide_no")
    slide_rules = rules.get("slide_specific_quality_rules", {})
    if not isinstance(slide_rules, dict):
        return
    rule = slide_rules.get(str(slide_no))
    if not isinstance(rule, dict):
        return

    headline = str(slide.get("headline") or "")
    fields_to_check = [
        ("headline", str(slide.get("headline") or ""), rule.get("forbidden_headline_patterns", [])),
        ("main_message", str(slide.get("main_message") or ""), rule.get("forbidden_main_message_patterns", [])),
    ]
    main_message = fields_to_check[1][1]

    for checked_field, checked_text, patterns in fields_to_check:
        for pattern in patterns:
            if not isinstance(pattern, str) or not pattern.strip():
                continue
            try:
                matched = re.search(pattern, checked_text, flags=re.IGNORECASE)
            except re.error as exc:
                warnings.append(f"slide {slide_no}: invalid slide-specific {checked_field} regex {pattern!r}: {exc}")
                continue
            if matched:
                description = str(rule.get("description") or "slide-specific semantic rule")
                message = (
                    f"slide {slide_no}: {checked_field} appears to violate slide-specific role ({description}; "
                    f"matched {pattern!r}). Keep the slide's primary subject aligned with its page role and target context secondary."
                )
                warnings.append(message)
                blocking_issues.append(message)
                break

    body_copy = slide.get("body_copy", {})
    body_text = ""
    if isinstance(body_copy, dict):
        body_text = "\n".join(str(value) for value in body_copy.values() if isinstance(value, str))

    focus_terms = [str(term).strip() for term in rule.get("preferred_focus_terms", []) if str(term).strip()]
    if focus_terms:
        combined = f"{headline}\n{main_message}\n{body_text}".lower()
        if not any(term.lower() in combined for term in focus_terms):
            description = str(rule.get("description") or "slide-specific semantic rule")
            warnings.append(
                f"slide {slide_no}: headline/main_message/body_copy do not clearly signal the expected slide role ({description}); "
                "make the slide's primary analytical subject explicit and keep target context secondary where required"
            )

    body_focus_terms = [str(term).strip() for term in rule.get("preferred_body_focus_terms", []) if str(term).strip()]
    if body_focus_terms and body_text:
        body_lower = body_text.lower()
        if not any(term.lower() in body_lower for term in body_focus_terms):
            message = str(rule.get("preferred_body_focus_message") or
                          "body_copy should contain industry-level focus terms for this slide role")
            warnings.append(f"slide {slide_no}: {message}")

    required_body_terms = [str(term).strip() for term in rule.get("required_body_terms", []) if str(term).strip()]
    if required_body_terms:
        combined_body = f"{main_message}\n{body_text}".lower()
        if not any(term.lower() in combined_body for term in required_body_terms):
            message = str(rule.get("required_body_message") or "required slide-specific body term missing")
            warnings.append(f"slide {slide_no}: {message}")


def validate_slide_1_2_pair(
    slides: list[dict],
    warnings: list[str],
    blocking_issues: list[str],
    valid_drilldown_roles: Optional[set[str]] = None,
) -> None:
    """Validate that Slide 1 is an overview and Slide 2 is a distinct drill-down."""
    slide_1 = None
    slide_2 = None
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        no = slide.get("slide_no")
        if no == 1:
            slide_1 = slide
        elif no == 2:
            slide_2 = slide

    if not slide_1 or not slide_2:
        return

    def slide_strategy_fields(slide: dict) -> dict:
        return {
            key: slide.get(key)
            for key in (
            "page_role",
            "drilldown_role",
            "drill_down_from_slide",
            "new_information_added",
            "primary_metric_ids",
            "intentional_overlap_metric_ids",
            )
            if key in slide
        }

    contract_1 = slide_strategy_fields(slide_1)
    contract_2 = slide_strategy_fields(slide_2)

    if not isinstance(contract_1, dict) or not isinstance(contract_2, dict):
        return

    # 1. Role check
    drilldown_role = str(contract_2.get("drilldown_role") or "").strip()
    page_role = str(contract_2.get("page_role") or "").strip()
    role_2 = drilldown_role or page_role
    if not role_2:
        message = (
            "slide 2: page_role / drilldown_role is required. Slide 2 must select one drill-down role "
            "from templates/drilldown_role_library.json (e.g., market_segmentation, channel_structure, "
            "customer_structure). Do not hard-code as channel or segment."
        )
        warnings.append(message)
    elif valid_drilldown_roles and role_2 not in valid_drilldown_roles:
        message = (
            f"slide 2: drilldown_role/page_role '{role_2}' is not in templates/drilldown_role_library.json. "
            f"Allowed roles: {', '.join(sorted(valid_drilldown_roles))}."
        )
        warnings.append(message)
    elif not drilldown_role:
        warnings.append(
            "slide 2: drilldown_role should be set explicitly even when page_role is present; "
            "use one role_id from templates/drilldown_role_library.json."
        )

    # 2. drill_down_from_slide check
    drill_from = contract_2.get("drill_down_from_slide")
    if drill_from != 1:
        message = "slide 2: drill_down_from_slide must be 1 (drills down from industry overview)"
        warnings.append(message)

    # 3. new_information_added check
    new_info = contract_2.get("new_information_added", [])
    if not isinstance(new_info, list) or len(new_info) < 1:
        message = (
            "slide 2: new_information_added is required. Slide 2 must add at least one category "
            "of new structural insight beyond what Slide 1 covers."
        )
        warnings.append(message)

    # 4. Primary metric overlap check
    metrics_1 = set(str(m).strip() for m in contract_1.get("primary_metric_ids", []) if str(m).strip())
    metrics_2 = set(str(m).strip() for m in contract_2.get("primary_metric_ids", []) if str(m).strip())
    intentional_overlap = set(str(m).strip() for m in contract_2.get("intentional_overlap_metric_ids", []))

    if metrics_1 and metrics_2:
        overlap_set = (metrics_1 & metrics_2) - intentional_overlap
        denom = min(len(metrics_1), len(metrics_2))
        if denom > 0:
            overlap_ratio = len(overlap_set) / denom
            if overlap_ratio >= 0.75:
                message = (
                    f"slide 1/2: primary metric overlap is {overlap_ratio:.0%} (≥75% threshold). "
                    f"Overlapping MET-IDs: {sorted(overlap_set)[:5]}. "
                    f"Slide 2 must introduce substantially new quantitative backbone."
                )
                warnings.append(message)
            elif overlap_ratio >= 0.40:
                warnings.append(
                    f"slide 1/2: primary metric overlap is {overlap_ratio:.0%} (≥40% threshold). "
                    f"Consider whether Slide 2 adds enough new quantitative insight."
                )


def check_source_note_notes_discipline(
    slide: dict,
    warnings: list[str],
) -> None:
    """Flag likely scope/calculation notes hidden inside source_note."""
    slide_no = slide.get("slide_no")
    source_note = str(slide.get("source_note") or "")
    if not source_note:
        return
    lowered = source_note.lower()
    note_terms = (
        "assumption",
        "calculation",
        "formula",
        "scope",
        "definition",
        "口径",
        "假设",
        "测算",
        "计算",
        "不包含",
        "剔除",
    )
    if any(term in lowered for term in note_terms) and "source" not in lowered and "sources" not in lowered and "来源" not in source_note:
        warnings.append(
            f"slide {slide_no}: source_note appears to contain scope/calculation notes without clear source attribution; "
            "separate sources from notes where possible"
        )


# ── Source note specificity ──────────────────────────────────────

def check_source_note_specificity(
    source_note: str,
    generic_source_phrases: list[str],
    slide_no: int,
    warnings: list[str],
) -> None:
    """Check if source_note is too generic."""
    text_lower = normalize(source_note)
    for phrase in generic_source_phrases:
        if normalize(phrase) in text_lower:
            warnings.append(
                f"slide {slide_no}: source_note contains generic source phrase '{phrase}'"
            )
            return

    # Heuristic: a specific source note should be at least 20 chars
    # and contain a recognizable source name, URL, or research pack section reference
    if len(source_note.strip()) < 15:
        warnings.append(
            f"slide {slide_no}: source_note too short ({len(source_note.strip())} chars); "
            "reference a specific research pack section, source name, or URL"
        )


DEFAULT_CONTENT_REPAIR_PROFILE = {
    "category": "content_quality",
    "owner_stage": "deck_blueprint",
    "repair_target": "deck_blueprint.json",
    "repair_target_layer": "generation",
    "repair_target_artifact": "deck_blueprint.json",
    "recommended_action": (
        "Fix the upstream page argument, evidence, or blueprint copy; "
        "do not patch compiled renderer or PPT artifacts."
    ),
    "forbidden_action": "Do not patch renderer_spec.json, replacement_dict.json, or PPT files unless a deterministic compiler/script bug is confirmed.",
    "repair_fields": [
        "slides[].headline",
        "slides[].main_message",
        "slides[].body_blocks",
        "slides[].source_note",
    ],
    "fallback_repair_targets": [
        "industry_research_pack.md",
        "industry_issue_analysis.json",
    ],
    "do_not_edit": [
        "renderer_spec.json",
        "replacement_dict.json",
        "*.pptx",
    ],
    "rerun_steps": [
        "scripts/validate_deck_blueprint.py",
        "scripts/compile_deck_blueprint.py",
        "scripts/validate_content_quality.py",
    ],
    "repair_hint": "Fix the upstream page argument, evidence, or blueprint copy; do not patch compiled renderer or PPT artifacts.",
}


CONTENT_REPAIR_PROFILES: dict[str, dict[str, Any]] = {
    "CHART_METRIC_BINDING": {
        "category": "metric_claims",
        "owner_stage": "deck_blueprint",
        "repair_target": "deck_blueprint.json",
        "repair_fields": [
            "slides[].chart_data",
            "slides[].visual_design.visual_metric_ids",
            "slides[].visible_metric_claims",
            "slides[].body_blocks[].metric_ids",
        ],
        "fallback_repair_targets": [
            "industry_research_pack.md",
            "industry_issue_analysis.json",
        ],
        "do_not_edit": [
            "renderer_spec.json",
            "replacement_dict.json",
            "*.pptx",
        ],
        "rerun_steps": [
            "scripts/validate_deck_blueprint.py",
            "scripts/compile_deck_blueprint.py",
            "scripts/validate_chart_metric_binding.py",
            "scripts/validate_content_quality.py",
        ],
        "repair_hint": "Fix chart_data, visual metric IDs, and source_rows in deck_blueprint; if the metric is genuinely missing, return to the research pack / issue analysis.",
    },
    "VISIBLE_CLAIM_BINDING": {
        "category": "metric_claims",
        "owner_stage": "deck_blueprint",
        "repair_target": "deck_blueprint.json",
        "repair_fields": [
            "slides[].visible_metric_claims",
            "slides[].headline",
            "slides[].main_message",
            "slides[].body_blocks[].copy",
            "slides[].body_blocks[].metric_ids",
        ],
        "fallback_repair_targets": [
            "industry_research_pack.md",
        ],
        "do_not_edit": [
            "renderer_spec.json",
            "replacement_dict.json",
            "*.pptx",
        ],
        "rerun_steps": [
            "scripts/repair_visible_metric_claims.py",
            "scripts/compile_deck_blueprint.py",
            "scripts/validate_chart_metric_binding.py",
            "scripts/validate_content_quality.py",
        ],
        "repair_hint": "Bind each visible number to existing MET-IDs in deck_blueprint; if no MET-ID exists, add or correct the metric in the research pack before reusing it.",
    },
    "WEAK_OR_GENERIC_SOURCE": {
        "category": "source_traceability",
        "owner_stage": "deck_blueprint",
        "repair_target": "deck_blueprint.json",
        "repair_fields": [
            "slides[].source_note",
            "slides[].evidence_ids",
            "slides[].body_blocks[].evidence_ids",
        ],
        "fallback_repair_targets": [
            "industry_research_pack.md",
            "artifacts/source_reviews.json",
            "artifacts/source_archive/source_archive_index.json",
        ],
        "do_not_edit": [
            "renderer_spec.json",
            "replacement_dict.json",
            "*.pptx",
        ],
        "rerun_steps": [
            "scripts/validate_deck_blueprint.py",
            "scripts/compile_deck_blueprint.py",
            "scripts/validate_content_quality.py",
        ],
        "repair_hint": "Replace generic source notes with specific EV IDs and source locators; if the EV/source is missing or not auditable, repair the research pack, source reviews, or source archive first.",
    },
    "EVIDENCE_LINKAGE": {
        "category": "source_traceability",
        "owner_stage": "deck_blueprint_or_research_pack",
        "repair_target": "deck_blueprint.json",
        "repair_fields": [
            "slides[].source_note",
            "slides[].evidence_ids",
            "slides[].body_blocks[].evidence_ids",
            "industry_research_pack.md Evidence Ledger",
        ],
        "fallback_repair_targets": [
            "industry_research_pack.md",
            "industry_issue_analysis.json",
            "artifacts/source_reviews.json",
            "artifacts/source_archive/source_archive_index.json",
        ],
        "do_not_edit": [
            "renderer_spec.json",
            "replacement_dict.json",
            "*.pptx",
        ],
        "rerun_steps": [
            "scripts/validate_research_pack.py",
            "scripts/validate_issue_analysis.py",
            "scripts/compile_deck_blueprint.py",
            "scripts/validate_content_quality.py",
        ],
        "repair_hint": "Make slide evidence IDs, source reviews, source archive, and the research pack Evidence Ledger consistent; downgrade or caveat claims when evidence remains thin.",
    },
    "TRANSACTION_EVIDENCE_TOO_THIN": {
        "category": "transaction_evidence",
        "owner_stage": "deck_blueprint_or_research_pack",
        "repair_target": "deck_blueprint.json",
        "repair_fields": [
            "slides[].headline",
            "slides[].main_message",
            "slides[].body_blocks",
            "slides[].caveats",
            "slides[].open_questions",
        ],
        "fallback_repair_targets": [
            "industry_research_pack.md",
            "industry_issue_analysis.json",
        ],
        "do_not_edit": [
            "renderer_spec.json",
            "replacement_dict.json",
            "*.pptx",
        ],
        "rerun_steps": [
            "scripts/validate_research_pack.py",
            "scripts/validate_issue_analysis.py",
            "scripts/compile_deck_blueprint.py",
            "scripts/validate_content_quality.py",
        ],
        "repair_hint": "Use at least two distinct transaction-case EVs for a transaction trend, or downgrade the page to a caveated observation / diligence question.",
    },
    "LAYOUT_FIT_RISK": {
        "category": "layout_density",
        "owner_stage": "deck_blueprint",
        "repair_target": "deck_blueprint.json",
        "repair_fields": [
            "slides[].headline",
            "slides[].main_message",
        ],
        "fallback_repair_targets": [],
        "do_not_edit": [
            "renderer_spec.json",
            "replacement_dict.json",
            "*.pptx",
        ],
        "rerun_steps": [
            "scripts/validate_deck_blueprint.py",
            "scripts/compile_deck_blueprint.py",
            "scripts/validate_content_quality.py",
        ],
        "repair_hint": "Fix hard title/subtitle fit issues in headline/main_message. Body-copy length findings are advisory scanability prompts; do not delete evidence, mechanism, or implication depth solely to shorten body text.",
    },
    "TARGET_ADVOCACY_OR_OVERCLAIM": {
        "category": "claim_strength",
        "owner_stage": "deck_blueprint",
        "repair_target": "deck_blueprint.json",
        "repair_fields": [
            "slides[].headline",
            "slides[].main_message",
            "slides[].body_blocks[].copy",
            "slides[].pitch_relevance",
            "slides[].caveats",
            "slides[].open_questions",
        ],
        "fallback_repair_targets": [
            "industry_issue_analysis.json",
        ],
        "do_not_edit": [
            "renderer_spec.json",
            "replacement_dict.json",
            "*.pptx",
        ],
        "rerun_steps": [
            "scripts/validate_deck_blueprint.py",
            "scripts/compile_deck_blueprint.py",
            "scripts/validate_content_quality.py",
        ],
        "repair_hint": "Reframe as sector understanding, pitch relevance, or open diligence question unless the evidence supports a stronger claim.",
    },
    "PAGE_STORY_OR_ROLE": {
        "category": "page_semantics",
        "owner_stage": "deck_blueprint",
        "repair_target": "deck_blueprint.json",
        "repair_fields": [
            "slides[].investor_question",
            "slides[].page_thesis",
            "slides[].headline",
            "slides[].main_message",
            "slides[].body_blocks",
            "slides[].selected_page_type",
        ],
        "fallback_repair_targets": [
            "industry_issue_analysis.json",
        ],
        "do_not_edit": [
            "renderer_spec.json",
            "replacement_dict.json",
            "*.pptx",
        ],
        "rerun_steps": [
            "scripts/validate_deck_blueprint.py",
            "scripts/compile_deck_blueprint.py",
            "scripts/validate_content_quality.py",
        ],
        "repair_hint": "Repair the page thesis and body-block roles in deck_blueprint so the slide answers one investor question without repeating other slides.",
    },
    "GENERIC_COPY": {
        "category": "copy_quality",
        "owner_stage": "deck_blueprint",
        "repair_target": "deck_blueprint.json",
        "repair_fields": [
            "slides[].headline",
            "slides[].main_message",
            "slides[].body_blocks[].copy",
        ],
        "fallback_repair_targets": [
            "industry_issue_analysis.json",
        ],
        "do_not_edit": [
            "renderer_spec.json",
            "replacement_dict.json",
            "*.pptx",
        ],
        "rerun_steps": [
            "scripts/validate_deck_blueprint.py",
            "scripts/compile_deck_blueprint.py",
            "scripts/validate_content_quality.py",
        ],
        "repair_hint": "Rewrite generic PPT copy in deck_blueprint into specific banker page language tied to EV/MET evidence.",
    },
}


def classify_content_root_causes(messages: list[str]) -> list[dict[str, Any]]:
    """Group blocking findings into repairable root-cause classes."""
    buckets = [
        (
            "CHART_METRIC_BINDING",
            ("chart_data compares", "chart series", "chart_data.source_rows", "percentage/share-like", "value", "data period"),
        ),
        (
            "VISIBLE_CLAIM_BINDING",
            ("visible_metric_claims", "material visible quantitative claim"),
        ),
        (
            "WEAK_OR_GENERIC_SOURCE",
            ("weak source marker", "generic source phrase", "source_note"),
        ),
        (
            "EVIDENCE_LINKAGE",
            ("evidence id", "ev-id", "not found in research pack", "no evidence id", "central supported_inference uses one ev-id"),
        ),
        (
            "TRANSACTION_EVIDENCE_TOO_THIN",
            ("transaction/consolidation", "transaction_case", "交易", "整合"),
        ),
        (
            "LAYOUT_FIT_RISK",
            ("layout", "line(s)", "reduce by", "budget", "chars", "visual area", "template-profile", "footer"),
        ),
        (
            "TARGET_ADVOCACY_OR_OVERCLAIM",
            ("target advocacy", "overclaim", "hard banned", "sell-side", "absolute"),
        ),
        (
            "PAGE_STORY_OR_ROLE",
            ("slide 1/2", "drilldown", "distinct", "overlap", "duplicate", "repeated", "not enough new information", "page role"),
        ),
        (
            "GENERIC_COPY",
            ("generic copy phrase", "too generic", "boilerplate", "research note style"),
        ),
        (
            "CONTENT_SOURCE_NOTE",
            ("source_note", "evidence", "source note"),
        ),
        (
            "CONTENT_EVIDENCE_LINKAGE",
            ("evidence id", "ev-id", "central supported_inference", "no evidence", "outside material claim", "open question"),
        ),
    ]
    grouped: dict[str, dict[str, Any]] = {}
    for message in messages:
        lowered = message.lower()
        code = "OTHER_CONTENT_QUALITY"
        for candidate_code, needles in buckets:
            if any(needle.lower() in lowered for needle in needles):
                code = candidate_code
                break
        profile = {
            **DEFAULT_CONTENT_REPAIR_PROFILE,
            **CONTENT_REPAIR_PROFILES.get(code, {}),
        }
        repair_issue_defaults = normalize_repair_issue(
            profile,
            default_layer="generation",
            default_artifact="deck_blueprint.json",
            default_recommended_action=profile.get("repair_hint", ""),
        ) or {
            "issue_type": code,
            "severity": "error",
            "repair_target_layer": "generation",
            "repair_target_artifact": profile.get("repair_target", "deck_blueprint.json"),
            "recommended_action": profile.get("repair_hint", ""),
            "forbidden_action": "; ".join(str(item) for item in profile.get("do_not_edit", []) or []),
        }
        entry = grouped.setdefault(
            code,
            {
                "severity": repair_issue_defaults.get("severity", "error"),
                "code": code,
                "category": profile["category"],
                "owner_stage": profile["owner_stage"],
                "repair_target_layer": repair_issue_defaults["repair_target_layer"],
                "repair_target": profile["repair_target"],
                "repair_target_artifact": repair_issue_defaults["repair_target_artifact"],
                "repair_fields": profile["repair_fields"],
                "fallback_repair_targets": profile["fallback_repair_targets"],
                "do_not_edit": profile["do_not_edit"],
                "rerun_steps": profile["rerun_steps"],
                "message_count": 0,
                "examples": [],
                "repair_hint": profile["repair_hint"],
                "recommended_action": repair_issue_defaults["recommended_action"],
                "forbidden_action": repair_issue_defaults["forbidden_action"],
            },
        )
        entry["message_count"] += 1
        if len(entry["examples"]) < 5:
            entry["examples"].append(message)
    return list(grouped.values())


def build_content_repair_plan(root_causes: list[dict[str, Any]]) -> dict[str, Any]:
    """Create an LLM-friendly repair map from classified content findings."""
    if not root_causes:
        return {
            "status": "no_content_quality_repairs_required",
            "instruction": "Content-quality validation has no blocking issues.",
            "primary_repair_targets": [],
            "fallback_repair_targets": [],
            "do_not_edit": [],
            "rerun_steps": [],
            "repair_issues": [],
            "targets": [],
        }

    primary_targets = unique_preserve_order(
        str(item.get("repair_target") or "") for item in root_causes if item.get("repair_target")
    )
    fallback_targets = unique_preserve_order(
        str(target)
        for item in root_causes
        for target in item.get("fallback_repair_targets", []) or []
        if target
    )
    do_not_edit = unique_preserve_order(
        str(target)
        for item in root_causes
        for target in item.get("do_not_edit", []) or []
        if target
    )
    rerun_steps = unique_preserve_order(
        str(step)
        for item in root_causes
        for step in item.get("rerun_steps", []) or []
        if step
    )

    targets: list[dict[str, Any]] = []
    for target in primary_targets:
        related = [item for item in root_causes if item.get("repair_target") == target]
        targets.append(
            {
                "repair_target": target,
                "root_cause_codes": [item.get("code") for item in related],
                "categories": unique_preserve_order(str(item.get("category")) for item in related if item.get("category")),
                "repair_fields": unique_preserve_order(
                    str(field)
                    for item in related
                    for field in item.get("repair_fields", []) or []
                    if field
                ),
                "example_count": sum(int(item.get("message_count") or 0) for item in related),
                "repair_hints": unique_preserve_order(str(item.get("repair_hint")) for item in related if item.get("repair_hint")),
            }
        )

    repair_issues = []
    for root_cause in root_causes:
        issue = normalize_repair_issue(
            {
                **root_cause,
                "issue_type": root_cause.get("code", "content_quality"),
                "repair_target_artifact": root_cause.get("repair_target_artifact") or root_cause.get("repair_target", ""),
                "recommended_action": root_cause.get("recommended_action", root_cause.get("repair_hint", "")),
                "forbidden_action": root_cause.get("forbidden_action", ""),
            },
            default_layer=root_cause.get("repair_target_layer") or str(root_cause.get("owner_stage") or "generation"),
            default_artifact=str(root_cause.get("repair_target") or root_cause.get("repair_target_artifact") or ""),
            default_recommended_action=root_cause.get("repair_hint", ""),
        )
        if issue:
            issue["examples"] = unique_preserve_order(root_cause.get("examples", []))
            repair_issues.append(issue)

    deduped_repair_issues: list[dict[str, Any]] = []
    seen_issue_keys: set[str] = set()
    for item in repair_issues:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key in seen_issue_keys:
            continue
        seen_issue_keys.add(key)
        deduped_repair_issues.append(item)
    repair_issues = deduped_repair_issues
    return {
        "status": "repair_required",
        "instruction": (
            "Fix the listed repair_target artifacts first, then rerun the compiled validators. "
            "Do not patch renderer_spec.json, replacement_dict.json, or PPT files unless a deterministic compiler/script bug is confirmed."
        ),
        "primary_repair_targets": primary_targets,
        "fallback_repair_targets": fallback_targets,
        "do_not_edit": do_not_edit,
        "rerun_steps": rerun_steps,
        "targets": targets,
        "repair_issues": repair_issues,
    }


def has_explicit_slide1_data_limitation(slide: dict, chart_data: dict) -> bool:
    """Return true when Slide 1 clearly explains why no safe primary chart exists."""
    fields = [
        slide.get("main_message"),
        slide.get("pitch_relevance"),
        slide.get("source_note"),
        chart_data.get("title"),
        chart_data.get("subtitle"),
        chart_data.get("limitation_note"),
        chart_data.get("scope_note"),
        chart_data.get("basis_note"),
    ]
    body_copy = slide.get("body_copy") or {}
    if isinstance(body_copy, dict):
        fields.extend(str(value) for value in body_copy.values())
    text = " ".join(str(value or "") for value in fields).lower()
    limitation_markers = [
        "data limitation",
        "limitation",
        "no reliable comparable",
        "not comparable",
        "proxy",
        "benchmark",
        "caveat",
        "scope",
        "口径",
        "不可比",
        "数据不足",
        "公开数据",
        "数据缺口",
        "替代指标",
        "代理指标",
        "基准",
        "限制",
        "谨慎",
    ]
    return any(marker in text for marker in limitation_markers)


# ── Chart data checks ────────────────────────────────────────────

def check_chart_data(
    slide: dict,
    rules: dict,
    warnings: list[str],
    blocking_issues: list[str],
    layout_budget: Optional[dict] = None,
    memo_text: str = "",
) -> None:
    """Check chart_data completeness for quantitative slides."""
    slide_no = slide.get("slide_no")
    page_type = slide.get("selected_page_type", "")
    chart_data = slide.get("chart_data")

    if slide_no == 1:
        if page_type == "summary_page":
            message = (
                "slide 1: formal delivery requires industry_overview_dynamic_page. "
                "summary_page is not a valid formal Slide 1 choice."
            )
            warnings.append(message)
            blocking_issues.append(message)
        if not chart_data or not isinstance(chart_data, dict):
            message = (
                "slide 1: visual area needs chart_data with chart_type "
                "('bar', 'stacked_bar', 'clustered_column', or 'line')"
            )
            warnings.append(message)
            blocking_issues.append(message)
            return
        chart_type = str(chart_data.get("chart_type") or "").lower()
        if chart_type in {"none", "no_chart", "text"}:
            if has_explicit_slide1_data_limitation(slide, chart_data):
                warnings.append(
                    f"slide 1: chart_type '{chart_type}' is accepted only because the renderer spec explicitly "
                    "labels the data limitation; prefer a reliable comparable chart when one is available."
                )
            else:
                message = (
                    f"slide 1: chart_type '{chart_type}' needs an explicit data limitation. "
                    "Prefer a reliable comparable chart; if none exists, state the scope/data limitation "
                    "rather than forcing weak proxy evidence."
                )
                warnings.append(message)
                blocking_issues.append(message)
            return
        if chart_type in {"bar", "column", "clustered_bar", "clustered_column", "stacked_bar", "stacked_column", "line", "line_chart"}:
            if not chart_data.get("categories") or not chart_data.get("series"):
                message = f"slide 1: chart_type '{chart_type}' requires categories and series"
                warnings.append(message)
                blocking_issues.append(message)
            if not chart_data.get("source_rows"):
                message = f"slide 1: chart_type '{chart_type}' requires source_rows"
                warnings.append(message)
                blocking_issues.append(message)
            secondary_module = chart_data.get("secondary_module") or {}
            if page_type == "industry_overview_dynamic_page":
                if not isinstance(secondary_module, dict):
                    secondary_module = {}
                secondary_type = str(secondary_module.get("module_type") or "").strip().lower()
                secondary_rows = secondary_module.get("rows") or []
                if secondary_type and secondary_type not in {"none", "no_module", "disabled"} and (
                    not isinstance(secondary_rows, list) or not [row for row in secondary_rows if isinstance(row, dict)]
                ):
                    message = (
                        "slide 1: chart_data.secondary_module is requested but rows are empty; "
                        "either provide true secondary_module.rows or omit/disable the module. "
                        "Do not reuse primary chart source_rows as metric-card fallback."
                    )
                    warnings.append(message)
                    blocking_issues.append(message)
            if page_type == "industry_overview_dynamic_page":
                body_copy = slide.get("body_copy") or {}
                key_messages = [body_copy.get("bullet_1"), body_copy.get("bullet_2"), body_copy.get("bullet_3")]
                if len([item for item in key_messages if str(item or "").strip()]) < 3:
                    message = (
                        "slide 1: industry_overview_dynamic_page should preserve three left-side key message bullets"
                    )
                    warnings.append(message)
                    blocking_issues.append(message)
            check_chart_metric_binding(slide, memo_text, warnings, blocking_issues)
            return
        if chart_type in {"metric_cards", "metric_card", "metrics", ""}:
            message = (
                "slide 1: metric_cards are not allowed as the primary formal overview visual. "
                "Use a real bar/stacked_bar/clustered_column/line chart and keep metric cards only as non-primary support."
            )
            warnings.append(message)
            blocking_issues.append(message)
            rows = chart_data.get("source_rows") or []
            min_rows = 3
            if layout_budget:
                min_rows = int(
                    layout_budget.get("slide_budgets", {})
                    .get("1:summary_page", {})
                    .get("slide_1_visual", {})
                    .get("min_metric_cards", min_rows)
                )
            if len(rows) < min_rows:
                message = f"slide 1: metric_cards visual requires at least {min_rows} source_rows"
                warnings.append(message)
                blocking_issues.append(message)
            unit = str(chart_data.get("unit") or "")
            has_mixed_unit = "/" in unit or " and " in unit.lower() or "mixed" in unit.lower()
            if has_mixed_unit:
                missing_row_units = []
                for idx, row in enumerate(rows[:max(min_rows, 1)], start=1):
                    if not isinstance(row, dict):
                        continue
                    value_text = str(row.get("value") or "")
                    row_unit = str(row.get("unit") or row.get("value_unit") or "")
                    if not row_unit and not any(token in value_text for token in ("%", "亿", "万", "元", "RMB", "USD", "$")):
                        missing_row_units.append(str(idx))
                if missing_row_units:
                    message = (
                        "slide 1: metric_cards uses mixed chart_data.unit; each source_row needs row-level "
                        f"unit/value_unit or a value string with units (missing rows: {', '.join(missing_row_units)})"
                    )
                    warnings.append(message)
                    blocking_issues.append(message)
            check_chart_metric_binding(slide, memo_text, warnings, blocking_issues)
            return
        message = f"slide 1: unsupported chart_type '{chart_type}' for deterministic visual rendering"
        warnings.append(message)
        blocking_issues.append(message)
        return

    # Quantitative page types should have chart_data
    quantitative_types = {"chart_page", "chart_plus_mini_table_page"}
    if page_type in quantitative_types and not chart_data:
        warnings.append(
            f"slide {slide_no}: quantitative page type '{page_type}' has no chart_data"
        )
        return

    if not chart_data or not isinstance(chart_data, dict):
        return

    if rules.get("required_renderer_checks", {}).get("chart_data_source_rows_for_quant_slides", True):
        if page_type in quantitative_types and not chart_data.get("source_rows"):
            warnings.append(
                f"slide {slide_no}: chart_data has no source_rows - "
                "quantitative slides should trace chart data back to sources"
            )

    check_chart_metric_binding(slide, memo_text, warnings, blocking_issues)


def parse_markdown_section_table(
    memo_text: str,
    section_pattern: str,
    header_sentinel: str,
    key_pattern: str = "",
    key_column: int = 0,
) -> dict[str, dict[str, str]]:
    """Generic parser for pipe-delimited Markdown tables under a ## section heading.

    Args:
        memo_text: Full markdown text to parse.
        section_pattern: Regex pattern to match the section header (e.g. "Metric Reconciliation").
        header_sentinel: First cell value that identifies the header row (e.g. "Metric Group").
        key_pattern: Regex pattern to match the key column value (e.g. r"^MET-\\d{3}$"). If empty, all data rows are included.
        key_column: Column index to match against key_pattern and use as the dict key.

    Returns:
        Dict keyed by the key column value, with each value being a dict of column-header -> cell-value.
    """
    result: dict[str, dict[str, str]] = {}
    if not memo_text:
        return result
    in_section = False
    header: list[str] = []
    for line in memo_text.splitlines():
        if re.match(rf"^##\s+{section_pattern}\b", line, flags=re.IGNORECASE):
            in_section = True
            continue
        if in_section and re.match(r"^##\s+", line):
            break
        if not in_section or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if not cells:
            continue
        if cells[0] == header_sentinel:
            header = cells
            continue
        if all(set(c) <= {"-", ":"} for c in cells):
            continue
        key = cells[key_column] if len(cells) > key_column else ""
        if key_pattern and not re.match(key_pattern, key):
            continue
        if key:
            result[key] = {header[i] if i < len(header) else f"col_{i}": cell for i, cell in enumerate(cells)}
    return result


def parse_metric_reconciliation(memo_text: str) -> dict[str, dict[str, str]]:
    """Parse research pack Metric Reconciliation rows into a MET-ID keyed map."""
    return parse_markdown_section_table(
        memo_text,
        section_pattern="Metric Reconciliation",
        header_sentinel="Metric Group",
        key_pattern=r"^MET-\d{3}$",
        key_column=1,
    )


def parse_evidence_ledger(memo_text: str) -> dict[str, dict[str, str]]:
    """Parse research pack Evidence Ledger rows into an EV-ID keyed map."""
    return parse_markdown_section_table(
        memo_text,
        section_pattern="Evidence Ledger",
        header_sentinel="Evidence ID",
        key_pattern=r"^EV-\d{3}$",
        key_column=0,
    )


def collect_chart_source_rows(chart_data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = chart_data.get("source_rows") or []
    collected = rows if isinstance(rows, list) else []
    return [row for row in collected if isinstance(row, dict)]


def collect_secondary_source_rows(chart_data: dict[str, Any]) -> list[dict[str, Any]]:
    secondary = chart_data.get("secondary_module") or {}
    rows = secondary.get("rows") if isinstance(secondary, dict) else []
    return [row for row in (rows or []) if isinstance(row, dict)]


def chart_datapoint_count(chart_data: dict[str, Any]) -> int:
    categories = chart_data.get("categories") or []
    series = chart_data.get("series") or []
    if not isinstance(categories, list) or not isinstance(series, list):
        return 0
    datapoint_count = 0
    for chart_series in series:
        if isinstance(chart_series, dict) and isinstance(chart_series.get("values"), list):
            datapoint_count += len(chart_series.get("values") or [])
    return datapoint_count


def chart_expected_datapoints(chart_data: dict[str, Any]) -> list[dict[str, Any]]:
    categories = chart_data.get("categories") or []
    series = chart_data.get("series") or []
    if not isinstance(categories, list) or not isinstance(series, list):
        return []
    expected: list[dict[str, Any]] = []
    for chart_series in series:
        if not isinstance(chart_series, dict) or not isinstance(chart_series.get("values"), list):
            continue
        series_name = str(chart_series.get("name") or chart_series.get("series_name") or "").strip()
        for idx, value in enumerate(chart_series.get("values") or []):
            category = categories[idx] if idx < len(categories) else ""
            expected.append(
                {
                    "series_name": series_name,
                    "category": category,
                    "value": value,
                }
            )
    return expected


def _parse_chart_number(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _is_percent_metric(row: dict[str, str]) -> bool:
    searchable = " ".join(
        str(row.get(field, ""))
        for field in ("Metric Type", "Metric Name", "Unit")
    ).lower()
    return any(token in searchable for token in ("%", "share", "rate", "ratio", "penetration", "占比", "份额", "比例", "渗透率"))


def _is_percent_source_row(row: dict[str, Any], chart_data: dict[str, Any]) -> bool:
    searchable = " ".join(
        str(value or "")
        for value in (
            row.get("label"),
            row.get("unit"),
            row.get("value_unit"),
            row.get("note"),
            chart_data.get("unit"),
        )
    ).lower()
    return "%" in searchable or any(token in searchable for token in ("share", "占比", "份额", "比例", "渗透率"))


def _row_period(row: dict[str, Any]) -> str:
    return str(row.get("period") or row.get("data_period") or row.get("year") or "").strip()


def _row_category(row: dict[str, Any]) -> str:
    return str(row.get("category") or row.get("x") or row.get("period") or row.get("data_period") or row.get("year") or "").strip()


def _row_series_name(row: dict[str, Any]) -> str:
    return str(row.get("series_name") or row.get("series") or row.get("metric_series") or "").strip()


def _normalized_scope(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().lower())


def _looks_like_time_label(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    return bool(
        re.search(r"\b20\d{2}(?:[EeA]?|E|A)?\b", text)
        or re.search(r"\b20\d{2}\s*[-~至]\s*20\d{2}", text)
        or re.search(r"\bQ[1-4]\b|季度|月", text, flags=re.IGNORECASE)
    )


def _is_time_series_chart(chart_data: dict[str, Any]) -> bool:
    categories = chart_data.get("categories") or []
    if not isinstance(categories, list) or len(categories) < 2:
        return False
    period_like = sum(1 for category in categories if _looks_like_time_label(category))
    return period_like >= max(2, len(categories) // 2)


def _normalized_for_compare(value: float, is_percent: bool) -> list[float]:
    if not is_percent:
        return [value]
    candidates = [value]
    if value <= 1:
        candidates.append(value * 100.0)
    else:
        candidates.append(value / 100.0)
    return candidates


def check_chart_metric_binding(
    slide: dict,
    memo_text: str,
    warnings: list[str],
    blocking_issues: list[str],
) -> None:
    """Require chart datapoints to bind to comparable research pack MET-IDs."""
    chart_data = slide.get("chart_data")
    if not memo_text or not isinstance(chart_data, dict):
        return

    slide_no = slide.get("slide_no")
    chart_type = str(chart_data.get("chart_type") or "").lower()
    if chart_type in {"", "none", "no_chart", "text"}:
        return

    primary_rows = collect_chart_source_rows(chart_data)
    secondary_rows = collect_secondary_source_rows(chart_data)
    if not primary_rows and not secondary_rows:
        return

    series = chart_data.get("series") or []
    categories = chart_data.get("categories") or []
    is_time_series = _is_time_series_chart(chart_data)
    if isinstance(series, list) and isinstance(categories, list) and categories:
        datapoint_count = chart_datapoint_count(chart_data)
        if datapoint_count and len(primary_rows) < datapoint_count:
            message = (
                f"slide {slide_no}: chart_data has {datapoint_count} chart datapoint(s) but only "
                f"{len(primary_rows)} primary source_rows; bind every primary chart datapoint to a specific MET-ID"
            )
            warnings.append(message)
            blocking_issues.append(message)

    metrics = parse_metric_reconciliation(memo_text)
    chart_met_ids: list[str] = []
    expected_datapoints = chart_expected_datapoints(chart_data)

    def validate_row(
        row: dict[str, Any],
        idx: int,
        row_label: str,
        context: dict[str, Any],
        expected: Optional[dict[str, Any]] = None,
        collect_for_chart: bool = False,
    ) -> None:
        metric_id = str(row.get("metric_id") or "").strip()
        value = row.get("value")
        numeric_value = isinstance(value, (int, float)) or bool(re.search(r"\d", str(value or "")))
        if numeric_value and not metric_id:
            message = (
                f"slide {slide_no}: {row_label}[{idx}] has quantitative value "
                "but no metric_id; bind every chart datapoint to research pack Metric Reconciliation"
            )
            warnings.append(message)
            blocking_issues.append(message)
            return
        if metric_id:
            if metric_id not in metrics:
                message = f"slide {slide_no}: {row_label}[{idx}] references unknown {metric_id}"
                warnings.append(message)
                blocking_issues.append(message)
                return
            if collect_for_chart:
                chart_met_ids.append(metric_id)
            metric_row = metrics[metric_id]
            source_value = _parse_chart_number(value)
            metric_value = _parse_chart_number(metric_row.get("Value", ""))
            source_period = _row_period(row)
            metric_period = str(metric_row.get("Data Period") or "").strip()
            if source_period and metric_period and _normalized_scope(source_period) not in _normalized_scope(metric_period):
                message = (
                    f"slide {slide_no}: {row_label}[{idx}] period '{source_period}' does not match "
                    f"{metric_id} Data Period '{metric_period}'"
                )
                warnings.append(message)
                blocking_issues.append(message)
            if expected:
                expected_series = str(expected.get("series_name") or "").strip()
                row_series = _row_series_name(row)
                if expected_series and row_series and _normalized_scope(row_series) != _normalized_scope(expected_series):
                    message = (
                        f"slide {slide_no}: {row_label}[{idx}] series_name '{row_series}' does not align "
                        f"with chart series '{expected_series}'"
                    )
                    warnings.append(message)
                    blocking_issues.append(message)
                row_category = _row_category(row)
                expected_category = str(expected.get("category") or "").strip()
                if row_category and expected_category and _normalized_scope(row_category) not in _normalized_scope(expected_category):
                    message = (
                        f"slide {slide_no}: {row_label}[{idx}] category/period '{row_category}' does not align "
                        f"with chart category '{expected_category}'"
                    )
                    warnings.append(message)
                    blocking_issues.append(message)
            if is_time_series and source_period:
                category_text = _normalized_scope(expected.get("category")) if expected else ""
                if category_text and _normalized_scope(source_period) not in category_text:
                    message = (
                        f"slide {slide_no}: {row_label}[{idx}] period '{source_period}' does not align "
                        f"with x-axis category '{expected.get('category')}'"
                    )
                    warnings.append(message)
                    blocking_issues.append(message)
            if _is_percent_source_row(row, context) and not _is_percent_metric(metric_row):
                message = (
                    f"slide {slide_no}: {row_label}[{idx}] is percentage/share-like but "
                    f"binds to {metric_id} ({metric_row.get('Metric Type', '')} / {metric_row.get('Unit', '')})"
                )
                warnings.append(message)
                blocking_issues.append(message)
            if source_value is not None and metric_value is not None:
                source_candidates = _normalized_for_compare(source_value, _is_percent_source_row(row, context))
                metric_candidates = _normalized_for_compare(metric_value, _is_percent_metric(metric_row))
                if not any(
                    abs(source - metric) <= max(0.05, abs(metric) * 0.02)
                    for source in source_candidates
                    for metric in metric_candidates
                ):
                    message = (
                        f"slide {slide_no}: {row_label}[{idx}] value {value} does not match "
                        f"{metric_id} value {metric_row.get('Value', '')}; do not reuse unrelated MET-IDs"
                    )
                    warnings.append(message)
                    blocking_issues.append(message)

    def expected_for_row(row: dict[str, Any], idx: int) -> Optional[dict[str, Any]]:
        row_series = _normalized_scope(_row_series_name(row))
        row_category = _normalized_scope(_row_category(row))
        if row_series or row_category:
            for expected in expected_datapoints:
                expected_series = _normalized_scope(expected.get("series_name"))
                expected_category = _normalized_scope(expected.get("category"))
                series_matches = not row_series or not expected_series or row_series == expected_series
                category_matches = not row_category or not expected_category or row_category in expected_category
                if series_matches and category_matches:
                    return expected
        return expected_datapoints[idx - 1] if idx - 1 < len(expected_datapoints) else None

    for idx, row in enumerate(primary_rows, start=1):
        expected = expected_for_row(row, idx)
        validate_row(row, idx, "chart_data.source_rows", chart_data, expected, collect_for_chart=True)

    secondary_context = chart_data.get("secondary_module") if isinstance(chart_data.get("secondary_module"), dict) else chart_data
    for idx, row in enumerate(secondary_rows, start=1):
        validate_row(row, idx, "chart_data.secondary_module.rows", secondary_context, None, collect_for_chart=False)

    if len(chart_met_ids) != len(set(chart_met_ids)) and chart_datapoint_count(chart_data) > len(set(chart_met_ids)):
        message = (
            f"slide {slide_no}: chart_data reuses MET-IDs across multiple datapoints. "
            "Each distinct chart datapoint should bind to its own MET-ID unless the same value is intentionally repeated as context."
        )
        warnings.append(message)
        blocking_issues.append(message)

    unique_ids = list(dict.fromkeys(chart_met_ids))
    if len(unique_ids) < 2:
        return

    rows_by_id = [metrics[met_id] for met_id in unique_ids if met_id in metrics]
    blocking_statuses = {"conflicting", "not_comparable", "unresolved"}
    for met_id, metric_row in zip(unique_ids, rows_by_id):
        status = metric_row.get("Conflict Status", "").strip().lower()
        if status in blocking_statuses:
            message = f"slide {slide_no}: chart_data uses {met_id} with Conflict Status '{status}'"
            warnings.append(message)
            blocking_issues.append(message)

    comparable_fields = ["Metric Type", "Geography", "Unit"]
    if chart_type not in {"line", "line_chart"} and not is_time_series:
        comparable_fields.append("Data Period")
    for field in comparable_fields:
        values = {
            (metric_row.get(field) or "").strip().lower()
            for metric_row in rows_by_id
            if (metric_row.get(field) or "").strip()
        }
        if len(values) > 1:
            detail = ", ".join(
                f"{met_id}={metrics[met_id].get(field, '')}"
                for met_id in unique_ids
                if met_id in metrics
            )
            message = (
                f"slide {slide_no}: chart_data compares MET-IDs with mixed {field}: {detail}. "
                "Use separate visuals, normalize the metric, or explain a comparable basis before charting."
            )
            warnings.append(message)
            blocking_issues.append(message)


# ── Training data check ──────────────────────────────────────────

def check_training_data_usage(
    slide: dict,
    memo_text: str,
    rules: dict,
    warnings: list[str],
) -> None:
    """Flag potential training-data usage when no research pack evidence found."""
    if not rules.get("required_renderer_checks", {}).get("no_training_data_unless_degraded_mode", True):
        return

    slide_no = slide.get("slide_no")
    source_note = slide.get("source_note", "")
    data_gaps = slide.get("data_gaps", [])

    # If source_note mentions training_data or the slide has data_gaps about unverifiable claims,
    # and we're not in degraded mode, warn
    if "training_data" in normalize(source_note):
        warnings.append(
            f"slide {slide_no}: source_note references training_data — "
            "fact may not be diligence-grade"
        )

    for gap in (data_gaps or []):
        if isinstance(gap, str) and "training_data" in normalize(gap):
            warnings.append(
                f"slide {slide_no}: data_gaps flags training_data — "
                "consider upgrading source before final PPT"
            )


# ── Source quality checks ────────────────────────────────────────

def check_weak_source_markers(
    text: str,
    markers: list[str],
    slide_no: int,
    field_name: str,
    warnings: list[str],
) -> None:
    text_lower = normalize(text)
    for marker in markers:
        if normalize(marker) in text_lower:
            warnings.append(
                f"slide {slide_no}: weak source marker '{marker}' found in {field_name}; "
                "do not use weak or unresolved sources as core support"
            )
            return


def check_memo_source_quality(
    memo_text: str,
    weak_markers: list[str],
    warnings: list[str],
) -> None:
    if not memo_text:
        return
    source_line_re = re.compile(
        r"(^\|\s*EV-|source|来源|材料|资料|http|www\.|\.com|\.cn|\.org|"
        r"Source Name|Online Research Sources|Source Materials)",
        flags=re.IGNORECASE,
    )
    for line_no, line in enumerate(memo_text.splitlines(), start=1):
        if not source_line_re.search(line):
            continue
        line_lower = normalize(line)
        for marker in weak_markers:
            if normalize(marker) in line_lower:
                warnings.append(
                    f"research pack line {line_no}: weak source marker '{marker}' appears in source/evidence text"
                )
                break


# ── Evidence-per-slide check ─────────────────────────────────────

def check_metric_ids_against_memo(slides: list[dict], memo_text: str) -> list[str]:
    """Check that renderer spec metric_ids exist in research pack and are not conflicting."""
    if not memo_text:
        return []
    issues: list[str] = []

    # Parse Metric Reconciliation from research pack using shared parser
    metrics = parse_metric_reconciliation(memo_text)
    met_status: dict[str, str] = {}
    for met_id, row in metrics.items():
        # Find conflict and resolution columns by header name
        conflict = ""
        resolution = ""
        for col_name, cell_value in row.items():
            col_lower = col_name.strip().lower()
            if "conflict" in col_lower and "status" in col_lower:
                conflict = cell_value.strip().lower()
            elif "resolution" in col_lower:
                resolution = cell_value.strip()
        met_status[met_id] = conflict
        if resolution:
            met_status[f"{met_id}_resolution"] = resolution

    all_met_ids = set(met_status.keys()) - {k for k in met_status if k.endswith("_resolution")}

    for slide in slides:
        if not isinstance(slide, dict):
            continue
        slide_no = slide.get("slide_no", "")
        visible_claims = slide.get("visible_metric_claims", [])
        if not isinstance(visible_claims, list):
            visible_claims = []
        metric_ids: list[str] = []
        for claim in visible_claims:
            if isinstance(claim, dict) and isinstance(claim.get("metric_ids"), list):
                metric_ids.extend(str(item).strip() for item in claim.get("metric_ids", []) if str(item).strip())
        for met_id in metric_ids:
            met_id = str(met_id).strip()
            if not met_id.startswith("MET-"):
                continue
            if met_id not in all_met_ids:
                issues.append(
                    f"slide {slide_no}: metric_ids references {met_id} which does not exist in research pack Metric Reconciliation"
                )
                continue
            status = met_status.get(met_id, "")
            if status in {"conflicting", "not_comparable"}:
                issues.append(
                    f"slide {slide_no}: metric_ids references {met_id} with conflict status '{status}'; "
                    f"conflicting/unresolved metrics must not be used in chart data or slide headlines"
                )
            elif status == "unresolved":
                issues.append(
                    f"slide {slide_no}: metric_ids references unresolved {met_id}; "
                    f"resolve before using in quantitative claims"
                )

    # Also check chart_data values against research pack if both present
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        slide_no = slide.get("slide_no", "")
        chart_data = slide.get("chart_data", {})
        if not isinstance(chart_data, dict):
            continue
        chart_ids = re.findall(r"MET-\d{3}", str(chart_data))
        for met_id in chart_ids:
            if met_id not in all_met_ids:
                issues.append(
                    f"slide {slide_no}: chart_data references {met_id} not in research pack Metric Reconciliation"
                )
            else:
                status = met_status.get(met_id, "")
                if status in {"conflicting", "not_comparable"}:
                    issues.append(
                        f"slide {slide_no}: chart_data references {met_id} with status '{status}'"
                    )

    return issues


QUANT_CLAIM_RE = re.compile(
    r"(?:\d+(?:\.\d+)?\s*(?:%|％|亿元|亿|万|万美元|亿美元|元|CAGR)|"
    r"CAGR|CR[34510]|Top\s*\d+|第[一二三四五六七八九十\d]+|行业第一|排名)",
    re.IGNORECASE,
)

MATERIAL_NUMERIC_MARKERS_RE = re.compile(
    r"(market|size|growth|cagr|share|margin|profit|revenue|gmv|valuation|multiple|ranking|rank|top|cr\d|"
    r"penetration|conversion|scale|peer|comparison|compare|leader|leading|premium|discount|"
    r"规模|增速|增长|份额|市占|毛利|净利|利润|营收|收入|gmv|估值|倍数|排名|榜|top|cr\d|"
    r"渗透|集中度|龙头|领先|高增长|高毛利|稀缺|低渗透|整合|交易|尽调|对比|同比|复合)",
    re.IGNORECASE,
)


def is_material_numeric_claim_location(loc: str, text: str) -> bool:
    """Return whether a visible number materially supports the slide claim."""
    if loc in {"headline", "main_message"}:
        return True
    if loc.startswith("chart_data.secondary_module") or loc.startswith("compare_table_data.rows"):
        return True
    if loc == "chart_data.title":
        return bool(MATERIAL_NUMERIC_MARKERS_RE.search(text))
    if loc.startswith("body_copy."):
        field = loc.split(".", 1)[1].lower()
        if any(marker in field for marker in ("metric", "kpi", "table", "row", "card", "panel")):
            return True
        return bool(MATERIAL_NUMERIC_MARKERS_RE.search(text))
    if loc == "pitch_relevance":
        return bool(MATERIAL_NUMERIC_MARKERS_RE.search(text))
    return False


def visible_text_fields(slide: dict) -> list[tuple[str, str]]:
    fields = [
        ("headline", str(slide.get("headline") or "")),
        ("main_message", str(slide.get("main_message") or "")),
        ("pitch_relevance", str(slide.get("pitch_relevance") or "")),
    ]
    body = slide.get("body_copy") or {}
    if isinstance(body, dict):
        for key, value in body.items():
            if isinstance(value, str):
                fields.append((f"body_copy.{key}", value))
    chart_data = slide.get("chart_data") or {}
    if isinstance(chart_data, dict):
        fields.append(("chart_data.title", str(chart_data.get("title") or "")))
        secondary = chart_data.get("secondary_module") or {}
        if isinstance(secondary, dict):
            for idx, row in enumerate(secondary.get("rows") or [], start=1):
                if isinstance(row, dict):
                    fields.append((f"chart_data.secondary_module.rows[{idx}]", " ".join(str(row.get(k) or "") for k in ("label", "value", "unit", "note"))))
    compare_table = slide.get("compare_table_data") or {}
    if isinstance(compare_table, dict):
        for idx, row in enumerate(compare_table.get("rows") or [], start=1):
            if not isinstance(row, dict):
                continue
            cells = [str(row.get("label") or "")]
            cells.extend(str(cell or "") for cell in row.get("cells") or [])
            fields.append((f"compare_table_data.rows[{idx}]", " ".join(cells)))
    return [(loc, text) for loc, text in fields if text.strip()]


def check_visible_metric_claims(slide: dict, memo_text: str, blocking_issues: list[str], warnings: list[str]) -> None:
    if not memo_text:
        return
    slide_no = slide.get("slide_no")
    metrics = parse_metric_reconciliation(memo_text)
    claims = slide.get("visible_metric_claims")
    all_quant_locations = [(loc, text) for loc, text in visible_text_fields(slide) if QUANT_CLAIM_RE.search(text)]
    quant_locations = [
        (loc, text)
        for loc, text in all_quant_locations
        if is_material_numeric_claim_location(loc, text)
    ]
    incidental_locations = [loc for loc, _ in all_quant_locations if loc not in {item[0] for item in quant_locations}]
    if len(quant_locations) > 6:
        warnings.append(
            f"slide {slide_no}: {len(quant_locations)} material numeric claim location(s) detected; "
            "consider simplifying the slide or moving secondary numeric context to source_note."
        )
    if incidental_locations:
        warnings.append(
            f"slide {slide_no}: visible numeric context found outside material claim locations "
            f"({', '.join(incidental_locations[:4])}); remove, move to source_note, or bind if it supports the conclusion."
        )
    if quant_locations and not isinstance(claims, list):
        blocking_issues.append(
            f"slide {slide_no}: material visible quantitative claim(s) require visible_metric_claims bindings: "
            + ", ".join(loc for loc, _ in quant_locations[:6])
        )
        return

    claim_locations = {str(claim.get("location") or ""): claim for claim in claims or [] if isinstance(claim, dict)}
    for loc, text in quant_locations:
        claim = claim_locations.get(loc)
        if not claim:
            # Allow chart datapoint rows to be covered by direct row metric_id.
            if loc.startswith("chart_data.") and re.search(r"MET-\d{3}", str(slide.get("chart_data", {}))):
                continue
            blocking_issues.append(
                f"slide {slide_no}: material visible quantitative claim at {loc!r} is not covered by visible_metric_claims"
            )
            continue
        metric_ids = [str(m).strip() for m in claim.get("metric_ids", []) if str(m).strip()]
        if not metric_ids:
            blocking_issues.append(f"slide {slide_no}: visible_metric_claims[{loc}] has no metric_ids")
            continue
        for met_id in metric_ids:
            if met_id not in metrics:
                blocking_issues.append(f"slide {slide_no}: visible_metric_claims[{loc}] references unknown {met_id}")
                continue
            status = str(metrics[met_id].get("Conflict Status") or "").strip().lower()
            if status in {"conflicting", "not_comparable", "unresolved"}:
                blocking_issues.append(
                    f"slide {slide_no}: visible_metric_claims[{loc}] uses {met_id} with Conflict Status '{status}'"
                )
        if claim.get("usage_type") == "calculated_display" and not str(claim.get("calculation_note") or "").strip():
            blocking_issues.append(f"slide {slide_no}: calculated visible metric claim at {loc!r} needs calculation_note")
        if claim.get("usage_type") == "ranking":
            ranking_basis = str(
                claim.get("basis_note")
                or claim.get("calculation_note")
                or claim.get("display_text")
                or ""
            )
            if not re.search(r"(basis|scope|period|platform|source|population|口径|按|期间|平台|来源|样本|排名|榜单)", ranking_basis, re.I):
                blocking_issues.append(
                    f"slide {slide_no}: ranking visible metric claim at {loc!r} needs ranking basis; "
                    "add visible_metric_claims[].basis_note with period, platform/source, and ranked population"
                )


def check_slide_scope_compatibility(slide: dict, memo_text: str, blocking_issues: list[str], warnings: list[str]) -> None:
    if not memo_text:
        return
    chart_data = slide.get("chart_data")
    if not isinstance(chart_data, dict):
        return
    metrics = parse_metric_reconciliation(memo_text)
    slide_no = slide.get("slide_no")
    chart_type = str(chart_data.get("chart_type") or "").lower()
    primary_rows = [row for row in chart_data.get("source_rows") or [] if isinstance(row, dict)]
    series_groups: dict[str, list[str]] = {}
    for row in primary_rows:
        met_id = str(row.get("metric_id") or "").strip()
        if met_id in metrics:
            series_groups.setdefault(str(row.get("series_name") or "primary"), []).append(met_id)
    for series_name, met_ids in series_groups.items():
        unique_ids = list(dict.fromkeys(met_ids))
        if len(unique_ids) < 2:
            continue
        core_fields = ["Metric Type", "Channel Scope", "Geography", "Unit"]
        for field in core_fields:
            values = {
                normalize_scope_value(metrics[met_id].get(field, ""))
                for met_id in unique_ids
                if metrics[met_id].get(field)
            }
            if len(values) > 1:
                detail = ", ".join(
                    f"{met_id}={metrics[met_id].get(field, '')}"
                    for met_id in unique_ids
                    if met_id in metrics
                )
                blocking_issues.append(
                    f"slide {slide_no}: chart series '{series_name}' mixes incompatible {field} values ({detail}). "
                    "Use separate visuals, normalize to a comparable basis, or revise chart_data.source_rows."
                )
        # Market Definition can intentionally differ when the chart axis is a
        # category / segment / channel comparison. Do not block on this field;
        # require the chart to disclose the comparison axis instead.
        if chart_type not in {"line", "line_chart"} and not _is_time_series_chart(chart_data):
            periods = {normalize_scope_value(metrics[met_id].get("Data Period", "")) for met_id in unique_ids if metrics[met_id].get("Data Period")}
            if len(periods) > 1:
                blocking_issues.append(
                    f"slide {slide_no}: chart series '{series_name}' mixes Data Period values without time-series framing"
                )
        market_defs = {
            normalize_scope_value(metrics[met_id].get("Market Definition", ""))
            for met_id in unique_ids
            if metrics[met_id].get("Market Definition")
        }
        has_axis_note = str(
            chart_data.get("comparison_axis")
            or chart_data.get("scope_note")
            or chart_data.get("notes")
            or chart_data.get("basis_note")
            or ""
        ).strip()
        if len(market_defs) > 1 and not has_axis_note:
            warnings.append(
                f"slide {slide_no}: chart series '{series_name}' compares different Market Definition values; "
                "add chart_data.comparison_axis or scope_note to state that the axis is category/segment/channel comparison."
            )

    scope_groups = set()
    for row in primary_rows:
        if row.get("scope_group"):
            scope_groups.add(str(row.get("scope_group")))
        met_id = str(row.get("metric_id") or "").strip()
        if met_id in metrics:
            scope_groups.add("|".join(normalize_scope_value(metrics[met_id].get(field, "")) for field in SCOPE_FIELDS[:4]))
    secondary = chart_data.get("secondary_module") or {}
    if isinstance(secondary, dict):
        for row in secondary.get("rows") or []:
            if isinstance(row, dict) and row.get("scope_group"):
                scope_groups.add(str(row.get("scope_group")))
    if slide_no == 2 and len(scope_groups) >= 3 and not str(chart_data.get("scope_note") or chart_data.get("notes") or "").strip():
        blocking_issues.append(
            "slide 2: uses 3+ metric scope groups without chart_data.scope_note/notes; split primary axis and auxiliary context"
        )


def _concept_tokens(text: str) -> set[str]:
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "", text.lower())
    tokens: set[str] = set()
    for n in (2, 3, 4):
        tokens.update(text[i : i + n] for i in range(0, max(0, len(text) - n + 1)))
    stop = {"行业", "市场", "公司", "中国", "发展", "趋势", "驱动", "结构", "企业", "价值"}
    return {token for token in tokens if token and token not in stop}


def check_cross_slide_distinctness(slides: list[dict], rules: dict, blocking_issues: list[str], warnings: list[str]) -> None:
    by_no = {slide.get("slide_no"): slide for slide in slides if isinstance(slide, dict)}
    default_rules = [
        {"slides": [3, 7], "max_semantic_overlap": 0.45, "blocking": True, "reason": "drivers must not repeat future trends"},
        {"slides": [4, 5], "max_semantic_overlap": 0.45, "blocking": True, "reason": "profit pools must not repeat barriers"},
        {"slides": [1, 8], "max_semantic_overlap": 0.55, "blocking": False, "reason": "summary may recap but must add transaction implications and DD questions"},
    ]
    distinct_rules = rules.get("cross_slide_distinctness_rules") or default_rules
    for rule in distinct_rules:
        pair = rule.get("slides") or []
        if len(pair) != 2 or pair[0] not in by_no or pair[1] not in by_no:
            continue
        slide_a, slide_b = by_no[pair[0]], by_no[pair[1]]
        text_a = " ".join(text for _, text in visible_text_fields(slide_a))
        text_b = " ".join(text for _, text in visible_text_fields(slide_b))
        tokens_a = _concept_tokens(text_a)
        tokens_b = _concept_tokens(text_b)
        if not tokens_a or not tokens_b:
            continue
        overlap = len(tokens_a & tokens_b) / max(1, min(len(tokens_a), len(tokens_b)))
        max_overlap = float(rule.get("max_semantic_overlap", 0.5))
        if overlap > max_overlap:
            repeated = sorted(tokens_a & tokens_b, key=len, reverse=True)[:8]
            message = (
                f"slide {pair[0]} / slide {pair[1]} semantic overlap {overlap:.0%} exceeds {max_overlap:.0%}; "
                f"{rule.get('reason', 'slides must be distinct')}. Repeated concepts: {', '.join(repeated)}"
            )
            warnings.append(message)


def check_transaction_trend_claim_support(slide: dict, memo_text: str, blocking_issues: list[str]) -> None:
    text = " ".join(text for _, text in visible_text_fields(slide))
    if not re.search(r"(产业|行业).{0,8}整合.{0,6}加速|(交易|出售|控股权).{0,8}窗口.{0,6}(打开|确立|清晰)|验证.{0,20}(趋势|逻辑|窗口)", text):
        return
    ledger = parse_evidence_ledger(memo_text)
    ev_ids = set(re.findall(r"EV-\d{3}", str(slide.get("source_note") or "")))
    ev_ids.update(str(item).strip() for item in slide.get("evidence_ids", []) or [] if str(item).strip())
    transaction_evidence = []
    for ev_id in ev_ids:
        row = ledger.get(ev_id, {})
        searchable = " ".join(str(row.get(field, "")) for field in ("Evidence Category", "Source Type", "Claim / Metric", "Claim Scope")).lower()
        if "transaction_case" in searchable or "交易" in searchable or "并购" in searchable or "收购" in searchable:
            transaction_evidence.append(ev_id)
    if len(set(transaction_evidence)) < 2:
        blocking_issues.append(
            f"slide {slide.get('slide_no')}: transaction/consolidation trend claim is supported by only "
            f"{len(set(transaction_evidence))} transaction_case EV-ID(s); use at least 2 distinct cases or downgrade wording to a recent observation sample"
        )


def check_slide6_industry_balance(slides: list[dict], memo_text: str) -> list[str]:
    """Require Slide 6 competitive landscape to remain industry/peer-first."""
    if not memo_text:
        return []
    # Use shared Evidence Ledger parser
    ledger = parse_evidence_ledger(memo_text)
    ev_scope: dict[str, str] = {
        ev_id: str(row.get("Claim Scope") or "").strip().lower()
        for ev_id, row in ledger.items()
    }

    issues: list[str] = []
    for slide in slides:
        if not isinstance(slide, dict) or slide.get("slide_no") != 6:
            continue
        ev_ids: set[str] = set()
        source_note = str(slide.get("source_note") or "")
        ev_ids.update(EV_ID_RE.findall(source_note))
        ev_ids.update(str(item).strip() for item in slide.get("evidence_ids", []) or [] if str(item).strip())
        industry_count = sum(1 for ev_id in ev_ids if "industry-level" in ev_scope.get(ev_id, ""))
        target_count = sum(1 for ev_id in ev_ids if "target-level" in ev_scope.get(ev_id, ""))
        if target_count and target_count >= industry_count:
            issues.append(
                f"slide 6: target-level evidence count ({target_count}) must be lower than industry-level evidence count ({industry_count}); "
                "competitive landscape pages must be market-structure / peer-positioning first"
            )
    return issues


def check_evidence_linkage(
    slide: dict,
    memo_text: str,
    min_evidence: int,
    warnings: list[str],
) -> None:
    """Check that material slide conclusions have traceable evidence.

    `min_evidence` is an advisory materiality threshold, not a hard quota. A
    single high-quality source can support a narrow hard fact, while directional
    or comparative claims should triangulate or carry caveats.
    """
    slide_no = slide.get("slide_no")
    source_note = slide.get("source_note", "")
    body_copy = slide.get("body_copy", {})
    evidence_tokens = set(EV_ID_RE.findall(source_note or ""))
    for item in slide.get("evidence_ids", []) or []:
        if isinstance(item, str) and EV_ID_RE.fullmatch(item.strip()):
            evidence_tokens.add(item.strip())

    claim_strength = str(slide.get("claim_strength") or "").strip()
    slide_text = " ".join(
        str(value or "")
        for value in (
            slide.get("headline"),
            slide.get("main_message"),
            slide.get("pitch_relevance"),
            source_note,
            body_copy if isinstance(body_copy, str) else " ".join(str(v or "") for v in body_copy.values()) if isinstance(body_copy, dict) else "",
        )
    ).lower()
    has_caveat = bool(
        re.search(
            r"(caveat|directional|preliminary|limitation|open question|diligence|validate|validation|"
            r"需|待|验证|尽调|初步|方向性|口径|限制|假设|问题)",
            slide_text,
        )
    )

    if len(evidence_tokens) == 0 and claim_strength not in {"hypothesis", "open_question"}:
        warnings.append(
            f"slide {slide_no}: no Evidence ID found in source_note or renderer spec evidence_ids; "
            "material slide conclusions should be traceable to EV IDs."
        )
    elif len(evidence_tokens) == 1 and claim_strength in {"supported_inference", "directional_inference", "management_claim"}:
        warnings.append(
            f"slide {slide_no}: central {claim_strength} uses one EV-ID. This may be sufficient for a narrow source-backed fact, "
            "but directional, comparative, or transaction-relevant conclusions should triangulate or carry caveats."
        )
    elif len(evidence_tokens) < min_evidence and not has_caveat:
        warnings.append(
            f"slide {slide_no}: references {len(evidence_tokens)} EV-ID(s). If the slide carries multiple material claims, "
            "simplify secondary claims, add evidence, or include caveats."
        )

    if evidence_tokens and memo_text:
        missing = sorted(token for token in evidence_tokens if token not in memo_text)
        if missing:
            warnings.append(
                f"slide {slide_no}: Evidence ID(s) not found in research pack: {', '.join(missing)}"
            )


# ── Main validation ──────────────────────────────────────────────

def validate(
    renderer_spec_path: Path,
    memo_path: Optional[Path],
    rules_path: Path,
    block_source_warnings: bool = True,
    text_fit_rules_path: Optional[Path] = None,
    layout_budget_path: Optional[Path] = DEFAULT_LAYOUT_BUDGET_PATH,
) -> dict:
    errors: list[str] = []
    density_warnings: list[str] = []
    source_warnings: list[str] = []
    chart_data_warnings: list[str] = []
    generic_copy_warnings: list[str] = []
    evidence_warnings: list[str] = []
    layout_warnings: list[str] = []
    layout_blocking_issues: list[str] = []
    claim_strength_warnings: list[str] = []
    claim_strength_blocking_issues: list[str] = []
    consistency_warnings: list[str] = []

    # Load inputs
    try:
        renderer_spec = load_json(renderer_spec_path)
    except (ValueError, json.JSONDecodeError) as exc:
        return {
            "is_valid": False,
            "renderer_spec": str(renderer_spec_path),
            "errors": [f"invalid JSON: {exc}"],
            "density_warnings": [],
            "source_warnings": [],
            "chart_data_warnings": [],
            "generic_copy_warnings": [],
            "evidence_warnings": [],
            "claim_strength_warnings": [],
            "tone_advisory_warnings": [],
            "consistency_warnings": [],
        }

    try:
        rules = load_json(rules_path)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return {
            "is_valid": False,
            "renderer_spec": str(renderer_spec_path),
            "rules": str(rules_path),
            "errors": [f"cannot load rules: {exc}"],
            "density_warnings": [],
            "source_warnings": [],
            "chart_data_warnings": [],
            "generic_copy_warnings": [],
            "evidence_warnings": [],
            "claim_strength_warnings": [],
            "consistency_warnings": [],
        }

    text_fit_rules = {}
    if text_fit_rules_path is None:
        candidate = rules_path.parent / "text_fit_rules.json"
        if candidate.exists():
            text_fit_rules_path = candidate
    if text_fit_rules_path:
        try:
            text_fit_rules = load_json(text_fit_rules_path)
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"cannot load text fit rules: {exc}")
    layout_budget = {}
    if layout_budget_path and layout_budget_path.exists():
        try:
            layout_budget = load_json(layout_budget_path)
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"cannot load layout budget: {exc}")
    valid_drilldown_roles = load_drilldown_role_ids()

    memo_text = ""
    if memo_path:
        try:
            memo_text = load_text(memo_path)
        except FileNotFoundError:
            errors.append(f"research pack file not found: {memo_path}")

    generic_source = rules.get("generic_source_phrases", [])
    generic_copy = rules.get("generic_copy_phrases", [])
    overclaim_phrases = rules.get("hard_banned_phrases", rules.get("overclaim_phrases", []))
    cautious_phrases = rules.get("contextual_caution_phrases", rules.get("cautious_language_phrases", []))
    target_advocacy_phrases = rules.get("target_advocacy_phrases", [])
    weak_source_markers = rules.get("weak_source_markers", [])
    min_evidence = rules.get("required_renderer_checks", {}).get("evidence_complexity_warning_threshold", 2)

    slides = renderer_spec.get("slides", [])
    if not isinstance(slides, list):
        errors.append("slides must be an array")
        slides = []

    metric_locations: dict[str, list[int]] = {}
    tone_advisory_warnings: list[str] = []

    for slide in slides:
        if not isinstance(slide, dict):
            continue
        slide_no = slide.get("slide_no")
        page_type = slide.get("selected_page_type", "")

        # 1. Headline density
        headline = slide.get("headline", "")
        if headline:
            check_field_density("headline", headline, rules, slide_no, density_warnings)
            if text_fit_rules:
                check_text_fit(
                    headline,
                    "headline",
                    slide_no,
                    page_type,
                    text_fit_rules,
                    layout_warnings,
                    layout_blocking_issues,
                )

        # 2. Main message density
        main_message = slide.get("main_message", "")
        if main_message:
            check_field_density("main_message", main_message, rules, slide_no, density_warnings)
            if layout_budget:
                punctuation_warning = check_main_message_terminal_punctuation(
                    main_message,
                    slide_no,
                    layout_budget,
                )
                if punctuation_warning:
                    layout_warnings.append(punctuation_warning)
                    layout_blocking_issues.append(punctuation_warning)
            if text_fit_rules:
                check_text_fit(
                    main_message,
                    "main_message",
                    slide_no,
                    page_type,
                    text_fit_rules,
                    layout_warnings,
                    layout_blocking_issues,
                )

        # 3. Body copy density + generic phrases
        body_copy = slide.get("body_copy", {})
        if isinstance(body_copy, dict):
            if layout_budget:
                check_layout_budget(
                    body_copy,
                    slide_no,
                    page_type,
                    layout_budget,
                    layout_warnings,
                    layout_blocking_issues,
                )
            for field_name, field_value in body_copy.items():
                if isinstance(field_value, str) and field_value.strip():
                    check_field_density(field_name, field_value, rules, slide_no, density_warnings)
                    if not field_name.lower().startswith(("table_", "matrix_")):
                        check_body_length(field_value, slide_no, field_name, density_warnings)
                    check_inline_source_references(field_value, slide_no, field_name, source_warnings)
                    check_generic_phrases(
                        field_value, generic_copy, slide_no, field_name,
                        generic_copy_warnings, "generic copy phrase",
                    )
            check_argument_density(slide, rules, evidence_warnings)

        # 4. Source note specificity
        source_note = slide.get("source_note", "")
        if source_note:
            check_source_note_specificity(source_note, generic_source, slide_no, source_warnings)
            check_generic_phrases(
                source_note, generic_source, slide_no, "source_note",
                source_warnings, "generic source phrase",
            )
            check_weak_source_markers(
                source_note,
                weak_source_markers,
                slide_no,
                "source_note",
                source_warnings,
            )
            if rules.get("required_renderer_checks", {}).get("sources_notes_discipline", True):
                check_source_note_notes_discipline(slide, source_warnings)

        # 5. Chart data completeness
        check_chart_data(slide, rules, chart_data_warnings, layout_blocking_issues, layout_budget, memo_text)
        check_slide_scope_compatibility(slide, memo_text, layout_blocking_issues, chart_data_warnings)
        check_visible_metric_claims(slide, memo_text, layout_blocking_issues, evidence_warnings)

        # 6. Claim strength and overclaim language
        check_claim_strength_language(slide, overclaim_phrases, claim_strength_warnings, claim_strength_blocking_issues)
        check_cautious_language(slide, cautious_phrases, tone_advisory_warnings)
        check_target_advocacy_language(
            slide,
            target_advocacy_phrases,
            claim_strength_warnings,
            claim_strength_blocking_issues,
            tone_advisory_warnings,
        )

        # 7. Slide-specific semantic constraints
        check_slide_specific_quality(slide, rules, generic_copy_warnings, claim_strength_blocking_issues)

        # 8. Training data usage
        if memo_text:
            check_training_data_usage(slide, memo_text, rules, source_warnings)

        # 9. Evidence linkage
        if memo_text:
            check_evidence_linkage(slide, memo_text, min_evidence, evidence_warnings)
            check_transaction_trend_claim_support(slide, memo_text, claim_strength_blocking_issues)

        if rules.get("required_renderer_checks", {}).get("cross_slide_metric_consistency_check", True):
            for signature in collect_slide_metric_signatures(slide):
                metric_locations.setdefault(signature, []).append(slide_no)

    if memo_text:
        check_memo_source_quality(memo_text, weak_source_markers, source_warnings)

    # Slide 1/2 pair validation: overview → drill-down
    validate_slide_1_2_pair(slides, generic_copy_warnings, claim_strength_blocking_issues, valid_drilldown_roles)
    check_cross_slide_distinctness(slides, rules, claim_strength_blocking_issues, generic_copy_warnings)

    # Check renderer spec metric_ids against research pack Metric Reconciliation
    metric_id_issues = check_metric_ids_against_memo(slides, memo_text)
    evidence_warnings.extend(metric_id_issues)

    slide6_balance_issues = check_slide6_industry_balance(slides, memo_text)
    generic_copy_warnings.extend(slide6_balance_issues)

    if metric_locations:
        repeated_metrics = {
            metric: sorted(set(locations))
            for metric, locations in metric_locations.items()
            if len(set(locations)) >= 3
        }
        for metric, locations in list(repeated_metrics.items())[:8]:
            consistency_warnings.append(
                f"cross-slide metric consistency: '{metric}' appears on slides {locations}; "
                "verify same value/unit/scope/period and label any intentional definition differences"
            )

    blocking_issues = []
    if block_source_warnings:
        blocking_issues.extend(source_warnings)
    blocking_issues.extend(layout_blocking_issues)
    blocking_issues.extend(claim_strength_blocking_issues)
    blocking_issues.extend(metric_id_issues)
    blocking_issues.extend(slide6_balance_issues)
    blocking_issues = unique_preserve_order(blocking_issues)

    layout_warnings = unique_preserve_order(
        [warning for warning in layout_warnings if warning not in set(blocking_issues)]
    )
    source_warnings = unique_preserve_order(source_warnings)
    density_warnings = unique_preserve_order(density_warnings)
    chart_data_warnings = unique_preserve_order(chart_data_warnings)
    generic_copy_warnings = unique_preserve_order(generic_copy_warnings)
    evidence_warnings = unique_preserve_order(evidence_warnings)
    claim_strength_warnings = unique_preserve_order(
        [warning for warning in claim_strength_warnings if warning not in set(blocking_issues)]
    )
    tone_advisory_warnings = unique_preserve_order(tone_advisory_warnings)
    consistency_warnings = unique_preserve_order(consistency_warnings)

    all_warnings = unique_preserve_order(
        density_warnings
        + source_warnings
        + chart_data_warnings
        + generic_copy_warnings
        + evidence_warnings
        + layout_warnings
        + claim_strength_warnings
        + consistency_warnings
        + blocking_issues
    )

    if blocking_issues:
        errors.append(
            "content quality gate failed: resolve blocking source/layout issues before PPT delivery"
        )
    root_causes = classify_content_root_causes(blocking_issues)
    repair_plan = build_content_repair_plan(root_causes)

    return {
        "is_valid": len(errors) == 0,
        "renderer_spec": str(renderer_spec_path),
        "research_pack": str(memo_path) if memo_path else "",
        "rules": str(rules_path),
        "text_fit_rules": str(text_fit_rules_path) if text_fit_rules_path else "",
        "layout_budget": str(layout_budget_path) if layout_budget_path else "",
        "error_count": len(errors),
        "warning_count": len(all_warnings),
        "errors": errors,
        "root_cause_count": len(root_causes),
        "root_causes": root_causes,
        "repair_plan": repair_plan,
        "repair_issues": repair_plan.get("repair_issues", []),
        "blocking_issue_count": len(blocking_issues),
        "blocking_issues": blocking_issues,
        "density_warnings": density_warnings,
        "source_warnings": source_warnings,
        "chart_data_warnings": chart_data_warnings,
        "generic_copy_warnings": generic_copy_warnings,
        "evidence_warnings": evidence_warnings,
        "metric_id_warnings": unique_preserve_order(metric_id_issues),
        "layout_warnings": layout_warnings,
        "claim_strength_warnings": claim_strength_warnings,
        "tone_advisory_warnings": tone_advisory_warnings,
        "consistency_warnings": consistency_warnings,
    }


# ── CLI ──────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate content quality of renderer_spec.json against the research pack."
    )
    parser.add_argument(
        "--renderer-spec",
        dest="renderer_spec",
        required=True,
        help="Path to renderer_spec.json."
    )
    parser.add_argument(
        "--research-pack",
        dest="research_pack",
        help="Path to industry_research_pack.md for evidence-linkage checks."
    )
    parser.add_argument(
        "--rules", required=True,
        help="Path to templates/content_quality_rules.json."
    )
    parser.add_argument(
        "--text-fit-rules",
        help="Optional path to templates/text_fit_rules.json. Defaults to sibling file next to --rules when present."
    )
    parser.add_argument(
        "--layout-budget",
        default=str(DEFAULT_LAYOUT_BUDGET_PATH),
        help="Optional path to templates/layout_budget.json."
    )
    parser.add_argument(
        "--output",
        help="Optional path to write validation report JSON."
    )
    parser.add_argument(
        "--quality-gate", action="store_true",
        help="Treat warnings as errors (fail on any warning)."
    )
    parser.add_argument(
        "--warnings-as-errors", action="store_true",
        help="Alias for --quality-gate."
    )
    parser.add_argument(
        "--allow-source-warnings", action="store_true",
        help="Do not fail on source_warnings. Use only for explicitly degraded/debug drafts.",
    )
    args = parser.parse_args()
    result = validate(
        renderer_spec_path=Path(args.renderer_spec),
        memo_path=Path(args.research_pack) if args.research_pack else None,
        rules_path=Path(args.rules),
        block_source_warnings=not args.allow_source_warnings,
        text_fit_rules_path=Path(args.text_fit_rules) if args.text_fit_rules else None,
        layout_budget_path=Path(args.layout_budget) if args.layout_budget else None,
    )

    gate = args.quality_gate or args.warnings_as_errors
    if gate and result["warning_count"] > 0:
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
