#!/usr/bin/env python3
"""Run Template Fit checks for renderer_spec against template profile.

This validator focuses on fit constraints only:
- visual contract capacity (layout budgets)
- source footer presence
- hard text-fit limits
- feature support (chart/table/matrix)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from json_utils import load_json_file
from validation_common import display_units, estimate_lines, layout_rules_for


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = ROOT / "templates" / "template_profile.json"
FALLBACK_REPORT = {"template_profile": "templates/template_profile.json"}


def _load_json(path: Path | str) -> dict[str, Any]:
    data = load_json_file(Path(path))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a JSON object")
    return data


def _slide_variants(profile: dict[str, Any]) -> dict[tuple[int, str], dict[str, Any]]:
    variants = {}
    for item in profile.get("slide_variants", []):
        if not isinstance(item, dict):
            continue
        try:
            slide_no = int(item.get("slide_no"))
            page_type = str(item.get("page_type") or "")
        except Exception:
            continue
        variants[(slide_no, page_type)] = item
    return variants


def _is_blank(value: Any) -> bool:
    return not bool(str(value or "").strip())


def _has_payload(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, dict):
        return bool(value)
    if isinstance(value, list):
        return bool(value)
    return bool(str(value).strip())


def _render_layouts_by_slide(profile: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    raw = profile.get("layout", {}).get("render_layouts", {})
    if not isinstance(raw, dict):
        return {}
    slides = raw.get("slides", raw)
    if not isinstance(slides, dict):
        return {}
    return slides


def _text_fit_rules(profile: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    text_fit = profile.get("layout", {}).get("text_fit_rules", {})
    fields = text_fit.get("fields", {})
    aliases = text_fit.get("renderer_field_aliases", {})
    if not isinstance(fields, dict):
        fields = {}
    if not isinstance(aliases, dict):
        aliases = {}
    return fields, aliases


def _append(target: list[str], message: str) -> None:
    target.append(message)


def _check_source_footer(
    slide: dict[str, Any],
    variant: dict[str, Any],
    warnings: list[str],
    blocking: list[str],
) -> None:
    source_footer_required = bool(variant.get("source_footer_required"))
    if not source_footer_required:
        return
    if _is_blank(slide.get("source_note")):
        _append(blocking, f"slide {slide.get('slide_no')}: source footer required by template variant but source_note is empty")
        return
    note = str(slide.get("source_note") or "")
    if note.strip().startswith("来源：") and len(note.strip()) <= 3:
        _append(warnings, f"slide {slide.get('slide_no')}: source footer is present but appears empty")


def _check_text_capacity(
    slide: dict[str, Any],
    layout_budget: dict[str, Any],
    warnings: list[str],
    blocking: list[str],
) -> None:
    slide_no = int(slide.get("slide_no") or 0)
    page_type = str(slide.get("selected_page_type") or "")
    rules = layout_rules_for(slide_no, page_type, layout_budget)
    if not isinstance(rules, dict):
        return

    body_copy = slide.get("body_copy") or {}
    if not isinstance(body_copy, dict):
        return

    global_rules = layout_budget.get("global", {})
    global_body = global_rules.get("body_copy", {})
    default_limit = float(global_body.get("max_bullet_units_default", 88))
    field_limits = rules.get("body_fields_max_units", {})
    table_limit = float(rules.get("table", {}).get("max_cell_units", global_rules.get("table", {}).get("max_cell_units", 22)))

    for field_name, value in body_copy.items():
        if not isinstance(value, str):
            continue
        field_limit = float(field_limits.get(field_name, default_limit))
        actual = display_units(value)
        if actual > field_limit:
            msg = (
                f"slide {slide_no}: '{field_name}' is {actual:.1f} layout units, "
                f"template budget is {field_limit:.1f}; edit Generation output or reduce copy"
            )
            _append(blocking, msg)

        if field_name.startswith("table_") and "|" in value:
            for idx, cell in enumerate(value.split("|"), start=1):
                cell_units = display_units(cell)
                if cell_units > table_limit:
                    _append(warnings, f"slide {slide_no}: table field '{field_name}' cell {idx} is {cell_units:.1f} units; >{table_limit:.1f} may wrap")


def _check_text_fit(
    slide: dict[str, Any],
    text_fit_fields: dict[str, Any],
    aliases: dict[str, str],
    warnings: list[str],
    blocking: list[str],
) -> None:
    slide_no = int(slide.get("slide_no") or 0)
    page_type = str(slide.get("selected_page_type") or "")
    fields = {
        "headline": slide.get("headline", ""),
        "main_message": slide.get("main_message", ""),
    }

    for field, value in fields.items():
        if not isinstance(value, str) or not value.strip():
            continue
        alias = aliases.get(field, field)
        rule = text_fit_fields.get(f"{slide_no}:{page_type}:{alias}")
        if not isinstance(rule, dict):
            continue
        max_line_units = float(rule.get("max_line_units") or 0)
        if max_line_units <= 0:
            continue
        target_lines = int(rule.get("target_lines") or 0)
        max_lines = int(rule.get("max_lines") or 0)
        actual_lines = estimate_lines(value, max_line_units)
        placeholder = rule.get("placeholder", "")
        if target_lines and actual_lines > target_lines:
            msg = (
                f"slide {slide_no}: '{field}' exceeds target density for {placeholder}; "
                f"estimated {actual_lines} line(s), target is {target_lines}"
            )
            _append(warnings, msg)
        if max_lines and actual_lines > max_lines:
            msg = (
                f"slide {slide_no}: '{field}' exceeds template max lines for {placeholder}; "
                f"estimated {actual_lines} line(s), max is {max_lines}"
            )
            _append(blocking, msg)


def _check_payload_support(
    slide: dict[str, Any],
    variant: dict[str, Any],
    warnings: list[str],
    blocking: list[str],
) -> None:
    supports = variant.get("supports") if isinstance(variant.get("supports"), dict) else {}
    slide_no = slide.get("slide_no")
    page_type = str(slide.get("selected_page_type") or "")
    if _has_payload(slide.get("chart_data")) and not bool(supports.get("chart", False)):
        _append(blocking, f"slide {slide_no}: chart data exists for '{page_type}' but template variant reports no chart support")
    if _has_payload(slide.get("compare_table_data")) and not bool(supports.get("table", False)):
        _append(blocking, f"slide {slide_no}: compare_table_data exists for '{page_type}' but template variant reports no table support")
    if _has_payload(slide.get("matrix_data")) and not bool(supports.get("matrix", False)):
        _append(warnings, f"slide {slide_no}: matrix payload exists for '{page_type}' but matrix support flag is false")

    required_fields = variant.get("required_body_fields") if isinstance(variant.get("required_body_fields"), list) else []
    body_copy = slide.get("body_copy") or {}
    if isinstance(body_copy, dict):
        missing = [name for name in required_fields if _is_blank(body_copy.get(name))]
        if missing:
            _append(blocking, f"slide {slide_no}: required body fields missing: {', '.join(missing)}")


def _check_render_layout_presence(
    slide: dict[str, Any],
    layout_slides: dict[str, dict[str, dict[str, Any]]],
    variant: dict[str, Any],
    warnings: list[str],
    blocking: list[str],
) -> None:
    slide_no = int(slide.get("slide_no") or 0)
    page_type = str(slide.get("selected_page_type") or "")
    variant_layout = str(variant.get("render_layout") or "")
    variant_missing = page_type not in layout_slides.get(str(slide_no), {})
    if variant_missing:
        if _has_payload(slide.get("chart_data")) or _has_payload(slide.get("compare_table_data")):
            _append(blocking, f"slide {slide_no}: render layout for '{page_type}' not found in template profile")
        else:
            _append(warnings, f"slide {slide_no}: render_layout '{variant_layout}' not found in template profile")


def _check_visual_style(
    profile: dict[str, Any],
    warnings: list[str],
) -> None:
    colors = profile.get("visual_style", {}).get("colors", {})
    typography = profile.get("visual_style", {}).get("typography", {})
    if not isinstance(colors, dict) or not isinstance(typography, dict):
        _append(warnings, "template_profile missing visual_style; fit checks cannot validate color/font constraints")
        return
    fallback_colors = {
        "brand_primary": "#0D57AA",
        "accent_red": "#C03C28",
        "grid_gray": "#D9D9D9",
        "text_gray": "#555555",
    }
    for key, fallback in fallback_colors.items():
        value = str(colors.get(key) or "")
        if value == fallback or not value:
            _append(warnings, f"template_profile uses fallback color for {key}: {value}")
    for key in ("body", "table_header", "table_body"):
        value = str(typography.get(key) or "").strip()
        if not value:
            _append(warnings, f"template_profile missing typography field {key}")


def _run_fit(renderer_spec: dict[str, Any], profile: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    warnings: list[str] = []
    blocking: list[str] = []

    slides = renderer_spec.get("slides")
    if not isinstance(slides, list):
        raise ValueError("renderer_spec.slides must be a list")

    layout_budget = profile.get("layout", {}).get("layout_budget", {})
    if not isinstance(layout_budget, dict):
        layout_budget = {}
    text_fit_fields, aliases = _text_fit_rules(profile)
    variants = _slide_variants(profile)
    layout_slides = _render_layouts_by_slide(profile)

    _check_visual_style(profile, warnings)

    for slide in slides:
        if not isinstance(slide, dict):
            continue
        slide_no = int(slide.get("slide_no") or 0)
        page_type = str(slide.get("selected_page_type") or "")
        variant = variants.get((slide_no, page_type))
        if not variant:
            blocking.append(f"slide {slide_no}: template profile missing variant '{page_type}'")
            continue
        if not isinstance(variant, dict):
            blocking.append(f"slide {slide_no}: invalid variant payload for '{page_type}'")
            continue
        _check_source_footer(slide, variant, warnings, blocking)
        _check_text_capacity(slide, layout_budget, warnings, blocking)
        _check_text_fit(slide, text_fit_fields, aliases, warnings, blocking)
        _check_payload_support(slide, variant, warnings, blocking)
        _check_render_layout_presence(slide, layout_slides, variant, warnings, blocking)

    is_valid = not blocking
    return is_valid, warnings, blocking


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--renderer-spec", required=True)
    parser.add_argument("--template-profile", default=str(DEFAULT_PROFILE))
    parser.add_argument("--output", default=str(ROOT / "artifacts" / "template_fit_validation.json"))
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as blocking issues (strict build mode)."
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        renderer_spec = _load_json(Path(args.renderer_spec))
        profile = _load_json(Path(args.template_profile))
        warnings = []
        blocking = []
        is_valid, fit_warnings, fit_blocking = _run_fit(renderer_spec, profile)
        warnings.extend(fit_warnings)
        blocking.extend(fit_blocking)
        if args.strict and warnings:
            blocking.extend(warnings)
            warnings = []
        result = {
            "schema_version": "template_fit_v1",
            "is_valid": is_valid,
            "analysis_source": "template_fit.py",
            "renderer_spec": str(Path(args.renderer_spec)),
            "template_profile": str(Path(args.template_profile)),
            "error_count": len(blocking),
            "warning_count": len(warnings),
            "errors": blocking,
            "warnings": warnings,
            "blocking_issues": blocking,
            "fit_checks": {
                "checked_slides": len(renderer_spec.get("slides") or []),
                "strict_mode": args.strict,
            },
        }
    except Exception as exc:
        result = {
            "schema_version": "template_fit_v1",
            "is_valid": False,
            "analysis_source": "template_fit.py",
            "error_count": 1,
            "warning_count": 0,
            "errors": [f"{type(exc).__name__}: {exc}"],
            "warnings": [FALLBACK_REPORT["template_profile"]],
            "blocking_issues": [f"{type(exc).__name__}: {exc}"],
        }

    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["is_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
