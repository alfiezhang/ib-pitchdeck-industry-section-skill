#!/usr/bin/env python3
"""Validate replacement_dict.json against current renderer_spec and slide semantics."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from generate_replacement_dict import build_replacement_dict
from json_utils import load_json_file
from renderer_token_source import build_token_source


DRAFT_MARKERS = (
    "DRAFT_REWRITE_REQUIRED",
    "TODO_REPLACE",
    "TODO:",
    "PLACEHOLDER",
)

AUDIT_TABLE_TERMS = {"point", "evidence", "metric", "ev", "met"}


def _normalize(text: Any) -> str:
    raw = str(text or "").strip().lower()
    raw = re.sub(r"^[•\-–—]+\s*", "", raw)
    raw = re.sub(r"sources?[:：]?", "", raw)
    raw = re.sub(r"ev-\d{3}|met-\d{3}", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"[\s\W_]+", "", raw, flags=re.UNICODE)
    return raw


def _token_slide_no(placeholder: str) -> int | None:
    match = re.search(r"slide_(\d{2})", placeholder)
    if not match:
        return None
    return int(match.group(1))


def _active_text_tokens(replacements: dict[str, Any]) -> dict[int, dict[str, str]]:
    by_slide: dict[int, dict[str, str]] = defaultdict(dict)
    for placeholder, value in replacements.items():
        slide_no = _token_slide_no(str(placeholder))
        if not slide_no:
            continue
        text = str(value or "").strip()
        if not text:
            continue
        lowered = placeholder.lower()
        if "source_footer" in lowered or "chart_title" in lowered:
            continue
        by_slide[slide_no][str(placeholder)] = text
    return dict(by_slide)


def _placeholder_role(placeholder: str) -> str:
    lowered = placeholder.lower()
    if "title" in lowered and "chart_title" not in lowered:
        return "title"
    if "takeaway" in lowered:
        return "takeaway"
    if any(token in lowered for token in ("bullet", "card", "panel", "row", "top", "bottom", "stage")):
        return "body"
    return "other"


def _char_jaccard(a: str, b: str) -> float:
    left = _similarity_features(a)
    right = _similarity_features(b)
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _similarity_features(text: Any) -> set[str]:
    raw = str(text or "").strip().lower()
    ascii_tokens = {
        token
        for token in re.findall(r"[a-z0-9]{3,}", raw)
        if token not in {"the", "and", "for", "with", "from", "that", "this", "into"}
    }
    cjk_chars = re.findall(r"[\u4e00-\u9fff]", raw)
    cjk_bigrams = {
        "".join(cjk_chars[idx : idx + 2])
        for idx in range(len(cjk_chars) - 1)
    }
    numeric_tokens = set(re.findall(r"\d+(?:\.\d+)?%?", raw))
    return ascii_tokens | cjk_bigrams | numeric_tokens


def _contains_draft_marker(value: Any) -> bool:
    text = str(value or "")
    return any(marker.lower() in text.lower() for marker in DRAFT_MARKERS)


def _load_expected(renderer_spec: dict[str, Any], ppt_mapping: dict[str, Any], renderer_spec_path: Path, ppt_mapping_path: Path) -> dict[str, Any]:
    token_result = build_token_source(renderer_spec)
    warnings = token_result.get("warnings") or []
    blocking = [
        warning for warning in warnings
        if "missing active body_copy fields" in warning
        or "empty active body_copy fields" in warning
        or "extra body_copy fields ignored" in warning
    ]
    if blocking:
        raise ValueError("renderer_spec cannot be converted into token source: " + "; ".join(blocking))
    return build_replacement_dict(
        token_result["token_source"],
        ppt_mapping,
        keep_unmapped_empty=False,
        renderer_spec_path=renderer_spec_path,
        ppt_mapping_path=ppt_mapping_path,
    )


def _chart_order_errors(renderer_spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for slide in renderer_spec.get("slides") or []:
        if not isinstance(slide, dict):
            continue
        slide_no = slide.get("slide_no")
        chart_data = slide.get("chart_data")
        if not isinstance(chart_data, dict):
            continue
        categories = [str(item) for item in chart_data.get("categories") or []]
        years = []
        for category in categories:
            match = re.search(r"(20\d{2})", category)
            if match:
                years.append(int(match.group(1)))
        if len(years) >= 3 and years != sorted(years) and years != sorted(years, reverse=True):
            errors.append(
                f"slide {slide_no}: chart categories look like a time series but are not ordered: {', '.join(categories)}"
            )
        if len(categories) >= 3 and len(set(categories)) == 1:
            errors.append(f"slide {slide_no}: chart categories are all identical: {categories[0]}")
    return errors


def validate(
    replacement_dict: dict[str, Any],
    renderer_spec: dict[str, Any],
    ppt_mapping: dict[str, Any],
    *,
    renderer_spec_path: Path,
    ppt_mapping_path: Path,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    expected = _load_expected(renderer_spec, ppt_mapping, renderer_spec_path, ppt_mapping_path)
    mismatches = []
    for key, expected_value in expected.items():
        actual = replacement_dict.get(key)
        if str(actual or "") != str(expected_value or ""):
            mismatches.append((key, actual, expected_value))
    extra_keys = sorted(set(replacement_dict) - set(expected))
    if mismatches:
        sample = "; ".join(
            f"{key}: actual={str(actual)[:40]!r}, expected={str(expected_value)[:40]!r}"
            for key, actual, expected_value in mismatches[:8]
        )
        errors.append(
            f"replacement_dict does not match current renderer_spec for {len(mismatches)} token(s); "
            f"rerun generate_replacement_dict.py. Examples: {sample}"
        )
    if extra_keys:
        warnings.append(f"replacement_dict contains {len(extra_keys)} inactive/extra token(s)")

    for key, value in replacement_dict.items():
        if _contains_draft_marker(value):
            errors.append(f"{key}: replacement value still contains draft/TODO marker")
        normalized = _normalize(value)
        if normalized in AUDIT_TABLE_TERMS:
            errors.append(f"{key}: replacement value looks like audit/scaffold label rather than client-facing copy")

    by_slide = _active_text_tokens(replacement_dict)
    for slide_no, values in sorted(by_slide.items()):
        role_values: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for placeholder, text in values.items():
            role_values[_placeholder_role(placeholder)].append((placeholder, text))

        title_values = role_values.get("title", [])
        takeaway_values = role_values.get("takeaway", [])
        if title_values and takeaway_values:
            title = title_values[0][1]
            takeaway = takeaway_values[0][1]
            if _normalize(title) == _normalize(takeaway) or _char_jaccard(title, takeaway) >= 0.92:
                errors.append(f"slide {slide_no}: title and takeaway are too similar; title must be a conclusion and takeaway must add the page logic")

        body_values = role_values.get("body", [])
        normalized_to_tokens: dict[str, list[str]] = defaultdict(list)
        for placeholder, text in body_values:
            norm = _normalize(text)
            if len(norm) >= 8:
                normalized_to_tokens[norm].append(placeholder)
        for norm, placeholders in normalized_to_tokens.items():
            if len(placeholders) >= 2:
                errors.append(
                    f"slide {slide_no}: duplicate body copy across active placeholders: {', '.join(placeholders)}"
                )

        for idx, (left_key, left_text) in enumerate(body_values):
            for right_key, right_text in body_values[idx + 1 :]:
                if len(_normalize(left_text)) < 12 or len(_normalize(right_text)) < 12:
                    continue
                if _char_jaccard(left_text, right_text) >= 0.9:
                    errors.append(
                        f"slide {slide_no}: body placeholders are near-duplicates ({left_key}, {right_key})"
                    )
                    break

        if len(body_values) >= 3:
            distinct = {_normalize(text) for _, text in body_values if len(_normalize(text)) >= 8}
            if len(distinct) < max(2, len(body_values) // 2):
                errors.append(f"slide {slide_no}: active body placeholders do not contain enough distinct page arguments")

    errors.extend(_chart_order_errors(renderer_spec))
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replacement-dict", required=True)
    parser.add_argument("--renderer-spec", required=True)
    parser.add_argument("--ppt-mapping", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    try:
        replacement_path = Path(args.replacement_dict)
        renderer_spec_path = Path(args.renderer_spec)
        ppt_mapping_path = Path(args.ppt_mapping)
        errors, warnings = validate(
            load_json_file(replacement_path),
            load_json_file(renderer_spec_path),
            load_json_file(ppt_mapping_path),
            renderer_spec_path=renderer_spec_path,
            ppt_mapping_path=ppt_mapping_path,
        )
    except Exception as exc:
        errors, warnings = [str(exc)], []

    result = {
        "is_valid": not errors,
        "replacement_dict": args.replacement_dict,
        "renderer_spec": args.renderer_spec,
        "ppt_mapping": args.ppt_mapping,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
