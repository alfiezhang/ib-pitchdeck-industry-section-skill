#!/usr/bin/env python3
"""Validate content quality of industry_storyboard.json against the research memo and quality rules.

Density and generic-copy findings are advisory by default. Source-quality findings are blocking by
default because weak or generic attributions can make unsupported facts look diligence-grade.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

from json_utils import load_json_file
from validation_common import (
    check_main_message_terminal_punctuation,
    display_units,
    estimate_lines,
    is_blank,
    layout_budget_findings,
)


DEFAULT_LAYOUT_BUDGET_PATH = Path(__file__).resolve().parents[1] / "templates" / "layout_budget.json"
# ── Helpers ──────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    return load_json_file(path)


def load_text(path: Path) -> str:
    with path.open("r", encoding="utf-8") as f:
        return f.read()


def normalize(s: str) -> str:
    """Lowercase and strip for phrase matching."""
    return s.strip().lower()

def check_layout_budget(
    body_copy: dict,
    slide_no: int,
    page_type: str,
    layout_budget: dict,
    warnings: list[str],
    blocking_warnings: list[str],
) -> None:
    budget_errors, budget_warnings = layout_budget_findings(body_copy, slide_no, page_type, layout_budget)
    for message in budget_errors:
        warnings.append(message)
        blocking_warnings.append(message)
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
    storyboard_field: str,
    slide_no: int,
    page_type: str,
    text_fit_rules: dict,
    warnings: list[str],
    blocking_warnings: list[str],
) -> None:
    aliases = text_fit_rules.get("storyboard_field_aliases", {})
    field_name = aliases.get(storyboard_field, storyboard_field)
    rule = text_fit_rules.get("fields", {}).get(f"{slide_no}:{page_type}:{field_name}")
    if not rule:
        return
    max_line_units = float(rule.get("max_line_units") or 0)
    actual_lines = estimate_lines(text, max_line_units)
    target_lines = int(rule.get("target_lines") or 0)
    max_lines = int(rule.get("max_lines") or 0)
    placeholder = rule.get("placeholder", "")
    if target_lines and actual_lines > target_lines:
        warnings.append(
            f"slide {slide_no}: '{storyboard_field}' estimated at {actual_lines} line(s) "
            f"for {placeholder}; target is {target_lines} line(s)"
        )
    if max_lines and actual_lines > max_lines:
        message = (
            f"slide {slide_no}: '{storyboard_field}' estimated at {actual_lines} line(s) "
            f"for {placeholder}; max allowed is {max_lines} line(s)"
        )
        warnings.append(message)
        if rule.get("block_if_exceeds_max_lines", True):
            blocking_warnings.append(message)


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


def collect_slide_metric_signatures(slide: dict) -> set[str]:
    fields: list[str] = []
    for field_name in ("headline", "main_message", "target_link"):
        value = slide.get(field_name)
        if isinstance(value, str):
            fields.append(value)
    body_copy = slide.get("body_copy", {})
    if isinstance(body_copy, dict):
        fields.extend(value for value in body_copy.values() if isinstance(value, str))
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
    blocking_warnings: Optional[list[str]] = None,
    max_units: float = 95.0,
) -> None:
    if display_units(text) > max_units:
        message = f"slide {slide_no}: '{field_name}' is paragraph-like; split/compress into shorter bullet text"
        warnings.append(message)
        if blocking_warnings is not None:
            blocking_warnings.append(message)


def check_argument_density(
    slide: dict,
    rules: dict,
    warnings: list[str],
) -> None:
    """Check that PPT body fields carry actual arguments, not only topic labels."""
    checks = rules.get("required_storyboard_checks", {})
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
    min_fields = int(checks.get("min_argument_fields_per_slide", 3))
    if len(strong_fields) < min(min_fields, len(argument_fields)):
        warnings.append(
            f"slide {slide_no}: only {len(strong_fields)} body_copy field(s) read as evidence-backed arguments; "
            f"expected at least {min(min_fields, len(argument_fields))}. Use memo Page Evidence Pack arguments with label + judgment + data/mechanism/target implication."
        )


def check_claim_strength_language(
    slide: dict,
    overclaim_phrases: list[str],
    warnings: list[str],
    blocking_warnings: list[str],
) -> None:
    """Check that non-hard-fact claims do not use absolute language."""
    slide_no = slide.get("slide_no")
    contract = slide.get("slide_story_contract", {})
    claim_strength = ""
    if isinstance(contract, dict):
        claim_strength = str(contract.get("claim_strength") or "").strip()
    if claim_strength == "hard_fact":
        return

    fields: list[tuple[str, str]] = []
    for field_name in ("headline", "main_message", "target_link"):
        value = slide.get(field_name)
        if isinstance(value, str):
            fields.append((field_name, value))
    body_copy = slide.get("body_copy", {})
    if isinstance(body_copy, dict):
        fields.extend((f"body_copy.{key}", value) for key, value in body_copy.items() if isinstance(value, str))

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
            f"slide {slide_no}: overclaim language found while claim_strength is "
            f"'{claim_strength or 'missing'}': {shown}{suffix}. "
            "Use cautious wording or upgrade evidence."
        )
        warnings.append(message)
        blocking_warnings.append(message)


def check_cautious_language(
    slide: dict,
    cautious_phrases: list[str],
    warnings: list[str],
    blocking_warnings: list[str],
) -> None:
    """Flag promotional language that should be softened in pitch materials. Blocking for pre-mandate context."""
    if not cautious_phrases:
        return
    slide_no = slide.get("slide_no")
    fields: list[tuple[str, str]] = []
    for field_name in ("headline", "main_message", "target_link"):
        value = slide.get(field_name)
        if isinstance(value, str):
            fields.append((field_name, value))
    body_copy = slide.get("body_copy", {})
    if isinstance(body_copy, dict):
        fields.extend((f"body_copy.{key}", value) for key, value in body_copy.items() if isinstance(value, str))

    findings: list[str] = []
    for field_name, value in fields:
        text_lower = normalize(value)
        for phrase in cautious_phrases:
            if normalize(phrase) and normalize(phrase) in text_lower:
                findings.append(f"'{phrase}' in {field_name}")
                break
    if findings:
        message = (
            f"slide {slide_no}: promotional / overconfident phrasing is not allowed in pitch materials: "
            + "; ".join(findings[:3])
        )
        warnings.append(message)
        blocking_warnings.append(message)


def check_slide_specific_quality(
    slide: dict,
    rules: dict,
    warnings: list[str],
    blocking_warnings: list[str],
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
                    f"matched {pattern!r}). Keep the slide's primary subject aligned with its page role and target linkage secondary."
                )
                warnings.append(message)
                blocking_warnings.append(message)
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
                "make the slide's primary analytical subject explicit and keep target linkage secondary where required"
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
    # and contain a recognizable source name, URL, or memo section reference
    if len(source_note.strip()) < 15:
        warnings.append(
            f"slide {slide_no}: source_note too short ({len(source_note.strip())} chars); "
            "reference a specific memo section, source name, or URL"
        )


def unique_preserve_order(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


# ── Chart data checks ────────────────────────────────────────────

def check_chart_data(
    slide: dict,
    rules: dict,
    warnings: list[str],
    blocking_warnings: list[str],
    layout_budget: Optional[dict] = None,
) -> None:
    """Check chart_data completeness for quantitative slides."""
    slide_no = slide.get("slide_no")
    page_type = slide.get("selected_page_type", "")
    chart_data = slide.get("chart_data")

    if slide_no == 1:
        if not chart_data or not isinstance(chart_data, dict):
            message = (
                "slide 1: summary_page visual area needs chart_data with chart_type "
                "('bar', 'stacked_bar', 'line', 'metric_cards', or 'none')"
            )
            warnings.append(message)
            blocking_warnings.append(message)
            return
        chart_type = str(chart_data.get("chart_type") or "").lower()
        if chart_type in {"none", "no_chart", "text"}:
            return
        if chart_type in {"bar", "column", "clustered_bar", "clustered_column", "stacked_bar", "stacked_column", "line", "line_chart"}:
            if not chart_data.get("categories") or not chart_data.get("series"):
                message = f"slide 1: chart_type '{chart_type}' requires categories and series"
                warnings.append(message)
                blocking_warnings.append(message)
            if not chart_data.get("source_rows"):
                message = f"slide 1: chart_type '{chart_type}' requires source_rows"
                warnings.append(message)
                blocking_warnings.append(message)
            return
        if chart_type in {"metric_cards", "metric_card", "metrics", ""}:
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
                blocking_warnings.append(message)
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
                    blocking_warnings.append(message)
            return
        message = f"slide 1: unsupported chart_type '{chart_type}' for deterministic visual rendering"
        warnings.append(message)
        blocking_warnings.append(message)
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

    if rules.get("required_storyboard_checks", {}).get("chart_data_source_rows_for_quant_slides", True):
        if page_type in quantitative_types and not chart_data.get("source_rows"):
            warnings.append(
                f"slide {slide_no}: chart_data has no source_rows - "
                "quantitative slides should trace chart data back to sources"
            )


# ── Training data check ──────────────────────────────────────────

def check_training_data_usage(
    slide: dict,
    memo_text: str,
    rules: dict,
    warnings: list[str],
) -> None:
    """Flag potential training-data usage when no memo evidence found."""
    if not rules.get("required_storyboard_checks", {}).get("no_training_data_unless_degraded_mode", True):
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
                    f"memo line {line_no}: weak source marker '{marker}' appears in source/evidence text"
                )
                break


# ── Evidence-per-slide check ─────────────────────────────────────

def check_evidence_linkage(
    slide: dict,
    memo_text: str,
    min_evidence: int,
    warnings: list[str],
) -> None:
    """Check that each slide references at least min_evidence sources or memo sections."""
    slide_no = slide.get("slide_no")
    source_note = slide.get("source_note", "")
    body_copy = slide.get("body_copy", {})
    contract = slide.get("slide_story_contract", {})
    evidence_tokens = set(EV_ID_RE.findall(source_note or ""))
    if isinstance(contract, dict):
        for item in contract.get("evidence_ids", []) or []:
            if isinstance(item, str) and EV_ID_RE.fullmatch(item.strip()):
                evidence_tokens.add(item.strip())

    if len(evidence_tokens) < min_evidence:
        warnings.append(
            f"slide {slide_no}: references only {len(evidence_tokens)} distinct Evidence ID(s); "
            f"expected at least {min_evidence}. Cite memo EV IDs in slide_story_contract.evidence_ids and source_note."
        )

    if evidence_tokens and memo_text:
        missing = sorted(token for token in evidence_tokens if token not in memo_text)
        if missing:
            warnings.append(
                f"slide {slide_no}: Evidence ID(s) not found in memo: {', '.join(missing)}"
            )


# ── Main validation ──────────────────────────────────────────────

def validate(
    storyboard_path: Path,
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
    layout_blocking_warnings: list[str] = []
    claim_strength_warnings: list[str] = []
    claim_strength_blocking_warnings: list[str] = []
    consistency_warnings: list[str] = []

    # Load inputs
    try:
        storyboard = load_json(storyboard_path)
    except (ValueError, json.JSONDecodeError) as exc:
        return {
            "is_valid": False,
            "storyboard": str(storyboard_path),
            "errors": [f"invalid JSON: {exc}"],
            "density_warnings": [],
            "source_warnings": [],
            "chart_data_warnings": [],
            "generic_copy_warnings": [],
            "evidence_warnings": [],
            "claim_strength_warnings": [],
            "consistency_warnings": [],
        }

    try:
        rules = load_json(rules_path)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return {
            "is_valid": False,
            "storyboard": str(storyboard_path),
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

    memo_text = ""
    if memo_path:
        try:
            memo_text = load_text(memo_path)
        except FileNotFoundError:
            errors.append(f"memo file not found: {memo_path}")

    generic_source = rules.get("generic_source_phrases", [])
    generic_copy = rules.get("generic_copy_phrases", [])
    overclaim_phrases = rules.get("overclaim_phrases", [])
    cautious_phrases = rules.get("cautious_language_phrases", [])
    weak_source_markers = rules.get("weak_source_markers", [])
    min_evidence = rules.get("required_storyboard_checks", {}).get("min_evidence_per_slide", 2)

    slides = storyboard.get("slides", [])
    if not isinstance(slides, list):
        errors.append("slides must be an array")
        slides = []

    metric_locations: dict[str, list[int]] = {}

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
                    layout_blocking_warnings,
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
                    layout_blocking_warnings.append(punctuation_warning)
            if text_fit_rules:
                check_text_fit(
                    main_message,
                    "main_message",
                    slide_no,
                    page_type,
                    text_fit_rules,
                    layout_warnings,
                    layout_blocking_warnings,
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
                    layout_blocking_warnings,
                )
            for field_name, field_value in body_copy.items():
                if isinstance(field_value, str) and field_value.strip():
                    check_field_density(field_name, field_value, rules, slide_no, density_warnings)
                    if not field_name.lower().startswith(("table_", "matrix_")):
                        check_body_length(field_value, slide_no, field_name, density_warnings, layout_blocking_warnings)
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
            if rules.get("required_storyboard_checks", {}).get("sources_notes_discipline", True):
                check_source_note_notes_discipline(slide, source_warnings)

        # 5. Chart data completeness
        check_chart_data(slide, rules, chart_data_warnings, layout_blocking_warnings, layout_budget)

        # 6. Claim strength and overclaim language
        check_claim_strength_language(slide, overclaim_phrases, claim_strength_warnings, claim_strength_blocking_warnings)
        check_cautious_language(slide, cautious_phrases, claim_strength_warnings, claim_strength_blocking_warnings)

        # 7. Slide-specific semantic constraints
        check_slide_specific_quality(slide, rules, generic_copy_warnings, claim_strength_blocking_warnings)

        # 8. Training data usage
        if memo_text:
            check_training_data_usage(slide, memo_text, rules, source_warnings)

        # 9. Evidence linkage
        if memo_text:
            check_evidence_linkage(slide, memo_text, min_evidence, evidence_warnings)

        if rules.get("required_storyboard_checks", {}).get("cross_slide_metric_consistency_check", True):
            for signature in collect_slide_metric_signatures(slide):
                metric_locations.setdefault(signature, []).append(slide_no)

    if memo_text:
        check_memo_source_quality(memo_text, weak_source_markers, source_warnings)

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

    blocking_warnings = []
    if block_source_warnings:
        blocking_warnings.extend(source_warnings)
    blocking_warnings.extend(layout_blocking_warnings)
    blocking_warnings.extend(claim_strength_blocking_warnings)
    blocking_warnings = unique_preserve_order(blocking_warnings)

    layout_warnings = unique_preserve_order(
        [warning for warning in layout_warnings if warning not in set(blocking_warnings)]
    )
    source_warnings = unique_preserve_order(source_warnings)
    density_warnings = unique_preserve_order(density_warnings)
    chart_data_warnings = unique_preserve_order(chart_data_warnings)
    generic_copy_warnings = unique_preserve_order(generic_copy_warnings)
    evidence_warnings = unique_preserve_order(evidence_warnings)
    claim_strength_warnings = unique_preserve_order(
        [warning for warning in claim_strength_warnings if warning not in set(blocking_warnings)]
    )
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
        + blocking_warnings
    )

    if blocking_warnings:
        errors.append(
            "content quality gate failed: resolve blocking source/layout warnings before PPT delivery"
        )

    return {
        "is_valid": len(errors) == 0,
        "storyboard": str(storyboard_path),
        "memo": str(memo_path) if memo_path else "",
        "rules": str(rules_path),
        "text_fit_rules": str(text_fit_rules_path) if text_fit_rules_path else "",
        "layout_budget": str(layout_budget_path) if layout_budget_path else "",
        "error_count": len(errors),
        "warning_count": len(all_warnings),
        "errors": errors,
        "blocking_warning_count": len(blocking_warnings),
        "blocking_warnings": blocking_warnings,
        "density_warnings": density_warnings,
        "source_warnings": source_warnings,
        "chart_data_warnings": chart_data_warnings,
        "generic_copy_warnings": generic_copy_warnings,
        "evidence_warnings": evidence_warnings,
        "layout_warnings": layout_warnings,
        "claim_strength_warnings": claim_strength_warnings,
        "consistency_warnings": consistency_warnings,
    }


# ── CLI ──────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate content quality of industry_storyboard.json against the research memo."
    )
    parser.add_argument(
        "--storyboard", required=True,
        help="Path to industry_storyboard.json."
    )
    parser.add_argument(
        "--memo",
        help="Path to industry_input_memo.md for evidence-linkage checks."
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
        storyboard_path=Path(args.storyboard),
        memo_path=Path(args.memo) if args.memo else None,
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
