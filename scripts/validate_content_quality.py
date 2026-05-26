#!/usr/bin/env python3
"""Validate content quality of industry_storyboard.json against the research memo and quality rules.

Density and generic-copy findings are advisory by default. Source-quality findings are blocking by
default because weak or generic attributions can make unsupported facts look diligence-grade.
"""

import argparse
import json
import re
import sys
import math
from pathlib import Path
from typing import Optional

from json_utils import load_json_file


# ── Helpers ──────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    return load_json_file(path)


def load_text(path: Path) -> str:
    with path.open("r", encoding="utf-8") as f:
        return f.read()


def is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def normalize(s: str) -> str:
    """Lowercase and strip for phrase matching."""
    return s.strip().lower()


def display_units(text: str) -> float:
    """Approximate rendered line width in CJK-character units."""
    clean = re.sub(r"\[\[/?(?:b|hl)\]\]", "", text or "")
    units = 0.0
    for ch in clean:
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
    lines = 0
    for segment in re.split(r"\r?\n", text):
        units = display_units(segment)
        lines += max(1, math.ceil(units / max_line_units))
    return lines


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
    r"[\(（][^()（）\n]*(?:EV-\d+|Source|source|来源|报告|年报|公告|research|Research)[^()（）\n]*[\)）]"
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


def check_body_length(
    text: str,
    slide_no: int,
    field_name: str,
    warnings: list[str],
    max_units: float = 95.0,
) -> None:
    if display_units(text) > max_units:
        warnings.append(
            f"slide {slide_no}: '{field_name}' is paragraph-like; split/compress into shorter bullet text"
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


# ── Chart data checks ────────────────────────────────────────────

def check_chart_data(
    slide: dict,
    rules: dict,
    warnings: list[str],
    blocking_warnings: list[str],
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
            if len(rows) < 2:
                message = "slide 1: metric_cards visual requires at least two source_rows"
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
    target_link = slide.get("target_link", "")

    # Count distinct evidence mentions across source_note + body fields
    evidence_count = 0

    # Check source_note for references
    # Look for patterns like "Memo Section X", "Source 1", URLs, specific names
    if source_note and len(source_note.strip()) > 15:
        evidence_count += 1

    # Check body_copy fields for inline source references
    if isinstance(body_copy, dict):
        for val in body_copy.values():
            if isinstance(val, str) and len(val.strip()) > 15:
                # Heuristic: field that reads like "evidence + data" counts
                if re.search(r'\d+', val) and re.search(r'[%％亿万亿]|RMB|USD|CAGR|bn|mn', val):
                    evidence_count += 1

    if evidence_count < min_evidence:
        warnings.append(
            f"slide {slide_no}: only ~{evidence_count} evidence-carrying field(s) — "
            f"recommend at least {min_evidence} per slide"
        )


# ── Main validation ──────────────────────────────────────────────

def validate(
    storyboard_path: Path,
    memo_path: Optional[Path],
    rules_path: Path,
    block_source_warnings: bool = True,
    text_fit_rules_path: Optional[Path] = None,
) -> dict:
    errors: list[str] = []
    density_warnings: list[str] = []
    source_warnings: list[str] = []
    chart_data_warnings: list[str] = []
    generic_copy_warnings: list[str] = []
    evidence_warnings: list[str] = []
    layout_warnings: list[str] = []
    layout_blocking_warnings: list[str] = []

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

    memo_text = ""
    if memo_path:
        try:
            memo_text = load_text(memo_path)
        except FileNotFoundError:
            errors.append(f"memo file not found: {memo_path}")

    generic_source = rules.get("generic_source_phrases", [])
    generic_copy = rules.get("generic_copy_phrases", [])
    weak_source_markers = rules.get("weak_source_markers", [])
    min_evidence = rules.get("required_storyboard_checks", {}).get("min_evidence_per_slide", 2)

    slides = storyboard.get("slides", [])
    if not isinstance(slides, list):
        errors.append("slides must be an array")
        slides = []

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

        # 5. Chart data completeness
        check_chart_data(slide, rules, chart_data_warnings, layout_blocking_warnings)

        # 6. Training data usage
        if memo_text:
            check_training_data_usage(slide, memo_text, rules, source_warnings)

        # 7. Evidence linkage
        if memo_text:
            check_evidence_linkage(slide, memo_text, min_evidence, evidence_warnings)

    if memo_text:
        check_memo_source_quality(memo_text, weak_source_markers, source_warnings)

    all_warnings = (
        density_warnings
        + source_warnings
        + chart_data_warnings
        + generic_copy_warnings
        + evidence_warnings
        + layout_warnings
    )

    blocking_warnings = []
    if block_source_warnings:
        blocking_warnings.extend(source_warnings)
    blocking_warnings.extend(layout_blocking_warnings)
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
