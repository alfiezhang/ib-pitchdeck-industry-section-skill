#!/usr/bin/env python3
"""Run Template Fit checks for renderer_spec against template profile.

This validator focuses on fit constraints only:
- visual contract capacity (layout budgets)
- source footer presence
- hard text-fit limits
- feature support (chart/table/matrix)
"""

from __future__ import annotations

# Runtime scripts can be run directly. Shared helpers remain in runtime
# `scripts/`; production tools live under role scripts; validators live under QC.
import sys as _ib_sys
from pathlib import Path as _IbPath
_IB_ROLE_SCRIPT_DIR = _IbPath(__file__).resolve().parent
_IB_RUNTIME_ROOT = next(
    _p for _p in _IbPath(__file__).resolve().parents
    if (_p / 'configs').is_dir() and (_p / 'scripts').is_dir()
)
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts" / "_lib"
_IB_ROLE_SCRIPT_DIRS = sorted(_p for _p in (_IB_RUNTIME_ROOT / 'scripts').iterdir() if _p.is_dir())
_IB_QC_VALIDATOR_DIRS = sorted((_IB_RUNTIME_ROOT / 'scripts' / 'qc' / 'validators').glob('*'))
_IB_IMPORT_PATHS = [str(_IB_ROLE_SCRIPT_DIR)]
for _ib_dir in [*_IB_ROLE_SCRIPT_DIRS, *_IB_QC_VALIDATOR_DIRS]:
    _ib_text = str(_ib_dir)
    if _ib_text not in _IB_IMPORT_PATHS:
        _IB_IMPORT_PATHS.append(_ib_text)
_IB_IMPORT_PATHS.append(str(_IB_SHARED_SCRIPT_DIR))
for _ib_path in list(_IB_IMPORT_PATHS):
    if _ib_path in _ib_sys.path:
        _ib_sys.path.remove(_ib_path)
for _ib_path in reversed(_IB_IMPORT_PATHS):
    _ib_sys.path.insert(0, _ib_path)

import argparse
import json
from pathlib import Path
from typing import Any

from json_utils import load_json_file
from template_contract_utils import active_body_fields
from validation_common import display_units, estimate_lines, layout_rules_for


ROOT = _IB_RUNTIME_ROOT
DEFAULT_PROFILE = ROOT / "configs" / "template_profile.json"
FALLBACK_REPORT = {"template_profile": "configs/template_profile.json"}


def _load_json(path: Path | str) -> dict[str, Any]:
    data = load_json_file(Path(path))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a JSON object")
    return data


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


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


def _variant_for_slide(profile: dict[str, Any], slide_no: int, page_type: str) -> dict[str, Any]:
    return _slide_variants(profile).get((slide_no, page_type), {})


def _capacity_conflict(slide_no: int, field_path: str, message: str, recommendation: str) -> dict[str, Any]:
    return {
        "conflict_type": "template_capacity_conflict",
        "slide_no": slide_no,
        "field_path": field_path,
        "message": message,
        "repair_owner": "generation",
        "repair_action": recommendation,
        "downstream_blocked": True,
    }


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
    required_fields = active_body_fields(required_fields, page_type, slide)
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
    variant_missing = page_type not in layout_slides.get(str(slide_no), {})
    needs_render_layout = (
        _has_payload(slide.get("chart_data"))
        or _has_payload(slide.get("compare_table_data"))
        or _has_payload(slide.get("matrix_data"))
    )
    if variant_missing and needs_render_layout:
        _append(blocking, f"slide {slide_no}: render layout for '{page_type}' not found in template profile; PPT rendering will produce broken output")
    elif variant_missing:
        _append(warnings, f"slide {slide_no}: render layout for '{page_type}' not found in template profile; token-only/text rendering will be used")


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


def _inventory_by_slide(profile: dict[str, Any]) -> dict[int, dict[str, Any]]:
    inventory = profile.get("template_inventory") if isinstance(profile.get("template_inventory"), dict) else {}
    return {
        int(item.get("slide_no")): item
        for item in inventory.get("slides", [])
        if isinstance(item, dict) and str(item.get("slide_no", "")).isdigit()
    }


def _slot_assignments(slide: dict[str, Any], variant: dict[str, Any], inventory_slide: dict[str, Any]) -> list[dict[str, Any]]:
    assignments: list[dict[str, Any]] = []
    slide_no = int(slide.get("slide_no") or 0)
    page_type = str(slide.get("selected_page_type") or "")
    body_copy = slide.get("body_copy") if isinstance(slide.get("body_copy"), dict) else {}
    field_roles = variant.get("field_roles") if isinstance(variant.get("field_roles"), dict) else {}
    for field_name in sorted(body_copy):
        assignments.append(
            {
                "slide_no": slide_no,
                "page_type": page_type,
                "content_field": f"body_copy.{field_name}",
                "template_role": field_roles.get(field_name, field_name),
                "slot_type": "text",
                "placement": "body",
            }
        )
    if _has_payload(slide.get("chart_data")):
        assignments.append(
            {
                "slide_no": slide_no,
                "page_type": page_type,
                "content_field": "chart_data",
                "template_role": "chart",
                "slot_type": "chart",
                "placement": "visual",
            }
        )
    if _has_payload(slide.get("compare_table_data")):
        assignments.append(
            {
                "slide_no": slide_no,
                "page_type": page_type,
                "content_field": "compare_table_data",
                "template_role": "table",
                "slot_type": "table",
                "placement": "visual",
            }
        )
    if _has_payload(slide.get("source_note")):
        assignments.append(
            {
                "slide_no": slide_no,
                "page_type": page_type,
                "content_field": "source_note",
                "template_role": "source_footer",
                "slot_type": "source_footer",
                "placement": "footer",
            }
        )
    if inventory_slide:
        for assignment in assignments:
            assignment["template_slide_inventory"] = {
                "slot_count": inventory_slide.get("shape_count", 0),
                "information_density": inventory_slide.get("information_density", "unknown"),
            }
    return assignments


def _build_fit_plan(renderer_spec: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    layout_budget = profile.get("layout", {}).get("layout_budget", {})
    if not isinstance(layout_budget, dict):
        layout_budget = {}
    variants = _slide_variants(profile)
    inventory = _inventory_by_slide(profile)
    fields, aliases = _text_fit_rules(profile)
    assignments: list[dict[str, Any]] = []
    recommendations: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    for slide in as_list(renderer_spec.get("slides")):
        if not isinstance(slide, dict):
            continue
        slide_no = int(slide.get("slide_no") or 0)
        page_type = str(slide.get("selected_page_type") or "")
        variant = variants.get((slide_no, page_type), {})
        inventory_slide = inventory.get(slide_no, {})
        if not variant:
            conflicts.append(
                _capacity_conflict(
                    slide_no,
                    "selected_page_type",
                    f"template profile has no variant for page type '{page_type}'",
                    "Choose a registered page type or regenerate template_profile from the selected template.",
                )
            )
            continue
        assignments.extend(_slot_assignments(slide, variant, inventory_slide))

        body_copy = slide.get("body_copy") if isinstance(slide.get("body_copy"), dict) else {}
        rules = layout_rules_for(slide_no, page_type, layout_budget)
        field_limits = rules.get("body_fields_max_units", {}) if isinstance(rules, dict) else {}
        default_limit = float(layout_budget.get("global", {}).get("body_copy", {}).get("max_bullet_units_default", 88))
        for field_name, value in body_copy.items():
            if not isinstance(value, str):
                continue
            limit = float(field_limits.get(field_name, default_limit))
            actual = display_units(value)
            if actual > limit:
                over_by = round(actual - limit, 1)
                msg = f"body_copy.{field_name} exceeds template capacity by {over_by:.1f} layout units"
                conflicts.append(
                    _capacity_conflict(
                        slide_no,
                        f"body_copy.{field_name}",
                        msg,
                        "Return to Generation and compress/restructure this field; do not silently truncate.",
                    )
                )
                recommendations.append(
                    {
                        "slide_no": slide_no,
                        "field_path": f"body_copy.{field_name}",
                        "recommendation_type": "copy_compression",
                        "current_units": actual,
                        "max_units": limit,
                        "message": f"Compress or split copy before rendering; over budget by {over_by:.1f} units.",
                    }
                )

        supports = variant.get("supports") if isinstance(variant.get("supports"), dict) else {}
        if _has_payload(slide.get("chart_data")) and not supports.get("chart"):
            conflicts.append(
                _capacity_conflict(
                    slide_no,
                    "chart_data",
                    "renderer_spec contains chart_data but selected template variant has no chart slot",
                    "Choose a chart-capable page type or revise visual plan in Generation.",
                )
            )
        if _has_payload(slide.get("compare_table_data")) and not supports.get("table"):
            conflicts.append(
                _capacity_conflict(
                    slide_no,
                    "compare_table_data",
                    "renderer_spec contains compare_table_data but selected template variant has no table slot",
                    "Choose a table-capable page type or revise visual plan in Generation.",
                )
            )

        for field, value in {"headline": slide.get("headline", ""), "main_message": slide.get("main_message", "")}.items():
            alias = aliases.get(field, field)
            rule = fields.get(f"{slide_no}:{page_type}:{alias}")
            if not isinstance(rule, dict) or not isinstance(value, str) or not value.strip():
                continue
            max_line_units = float(rule.get("max_line_units") or 0)
            max_lines = int(rule.get("max_lines") or 0)
            if max_line_units and max_lines:
                actual_lines = estimate_lines(value, max_line_units)
                if actual_lines > max_lines:
                    conflicts.append(
                        _capacity_conflict(
                            slide_no,
                            field,
                            f"{field} estimates to {actual_lines} lines but template allows {max_lines}",
                            "Return to Generation and compress the headline/message before rendering.",
                        )
                    )

    return {
        "schema_version": "template_fit_plan_v1",
        "analysis_source": "template_fit.py",
        "template_profile": str(profile.get("output_path") or profile.get("template_file") or ""),
        "page_assignments": assignments,
        "copy_compression_recommendations": recommendations,
        "capacity_conflicts": conflicts,
        "template_capacity_conflict": bool(conflicts),
        "fit_decision": "template_capacity_conflict" if conflicts else "template_ready",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--renderer-spec", required=True)
    parser.add_argument("--template-profile", default=str(DEFAULT_PROFILE))
    parser.add_argument("--output", default=str(ROOT / "artifacts" / "template_fit_validation.json"))
    parser.add_argument("--fit-plan-output", help="Optional path for artifacts/template_fit_plan.json")
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
        fit_plan = _build_fit_plan(renderer_spec, profile)
        warnings.extend(fit_warnings)
        blocking.extend(fit_blocking)
        for conflict in fit_plan.get("capacity_conflicts") or []:
            message = str(conflict.get("message") or "")
            if message and message not in blocking:
                blocking.append(message)
        if args.strict and warnings:
            blocking.extend(warnings)
            warnings = []
        # Recompute is_valid after strict promotion so blocking issues are reflected
        is_valid = not blocking
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
            "capacity_conflicts": fit_plan.get("capacity_conflicts", []),
            "template_capacity_conflict": bool(fit_plan.get("template_capacity_conflict")),
            "template_fit_plan": args.fit_plan_output or "",
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
            "capacity_conflicts": [],
            "template_capacity_conflict": False,
        }
        fit_plan = {
            "schema_version": "template_fit_plan_v1",
            "analysis_source": "template_fit.py",
            "fit_decision": "template_fit_error",
            "page_assignments": [],
            "copy_compression_recommendations": [],
            "capacity_conflicts": [],
            "errors": result["errors"],
        }

    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.fit_plan_output:
        fit_plan_path = Path(args.fit_plan_output)
        fit_plan_path.parent.mkdir(parents=True, exist_ok=True)
        fit_plan_path.write_text(json.dumps(fit_plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["is_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
