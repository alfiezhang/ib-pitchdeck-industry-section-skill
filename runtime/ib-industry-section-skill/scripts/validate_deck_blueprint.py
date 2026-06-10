#!/usr/bin/env python3
"""Validate deck_blueprint.json before compiling it to PPT renderer inputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from deck_blueprint_utils import (
    FIXED_PAGE_ROLES,
    METRIC_VISUAL_CAPABILITIES,
    VALID_CLAIM_STRENGTHS,
    analysis_evidence_ids,
    analysis_index,
    analysis_metric_ids,
    as_list,
    metric_ids_from_visual,
    non_empty_text,
    normalize_deck_blueprint_for_page_plan,
    normalize_text,
    proof_points_from_blueprint_slide,
    selected_issue_analysis_ids,
    template_variants_by_slide,
    unique,
    visual_plan_from_blueprint_slide,
)
from json_utils import load_json_file
from upstream_validation import DECK_BLUEPRINT_UPSTREAM_VALIDATIONS, assert_formal_upstream_valid
from validation_common import display_units, layout_rules_for


BLOCKED_MARKERS = (
    "DRAFT_REWRITE_REQUIRED",
    "TODO_REPLACE",
    "TODO:",
    "PLACEHOLDER",
    "{{",
    "}}",
)
CONCLUSION_MARKERS = (
    "看",
    "来自",
    "聚焦",
    "考验",
    "应",
    "需",
    "支撑",
    "决定",
    "驱动",
    "改变",
    "重塑",
    "验证",
    "取决",
    "打开",
    "形成",
    "升级",
    "放大",
    "收敛",
    "凸显",
    "anchors",
    "anchored",
    "driven",
    "requires",
    "depends",
    "supports",
    "reshapes",
    "creates",
    "captures",
)

VALID_EVIDENCE_ROLES = {
    "thesis_anchor",
    "supporting_evidence",
    "context_setting",
    "caveat_only",
    "open_question",
}


def _append_repair_target(
    targets: list[dict[str, Any]],
    *,
    repair_fields: list[str],
    repair_hint: str,
    slide_no: int,
    error_text: str,
    active_fields: list[str] | None = None,
) -> None:
    target = {
        "slide_no": slide_no,
        "repair_target": "deck_blueprint.json",
        "repair_fields": repair_fields,
        "error_text": error_text,
        "repair_hint": repair_hint,
    }
    if active_fields is not None:
        target["active_fields"] = active_fields
    if not any(
        existing.get("slide_no") == slide_no
        and existing.get("repair_fields") == repair_fields
        for existing in targets
    ):
        targets.append(target)


def _build_error_repair_plan(errors: list[str], repair_targets: list[dict[str, Any]]) -> dict[str, Any]:
    if not errors and not repair_targets:
        return {
            "status": "no_error_repairs_required",
            "targets": [],
            "instruction": "No deck-blueprint hard failures were found for structured repair planning.",
        }
    if not repair_targets:
        return {
            "status": "repair_target_not_mapped",
            "targets": [],
            "instruction": (
                "Validation produced errors. Re-run with full context and map the blocking fields manually, "
                "usually in deck_blueprint.json at the listed error line.")
            ,
        }
    return {
        "status": "mandatory_repair_required",
        "targets": repair_targets,
        "instruction": (
            "Use the mapped repair targets first. After edits rerun scripts/validate_deck_blueprint.py, "
            "scripts/compile_deck_blueprint.py, and scripts/validate_renderer_spec.py."
        ),
    }


def _usage(analysis: dict[str, Any]) -> dict[str, Any]:
    usage = analysis.get("downstream_permission")
    return usage if isinstance(usage, dict) else {}


def _contains_marker(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_marker(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_marker(item) for item in value)
    if isinstance(value, str):
        return any(marker.lower() in value.lower() for marker in BLOCKED_MARKERS)
    return False


def _looks_like_conclusion_headline(headline: str) -> bool:
    normalized = normalize_text(headline)
    if any(token in headline for token in ("，", "：", "；", ",", ":", ";")):
        return True
    if any(ch.isdigit() for ch in headline):
        return True
    lowered = normalized.lower()
    return any(marker.lower() in lowered for marker in CONCLUSION_MARKERS)


def _body_blocks(slide: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in as_list(slide.get("body_blocks")) if isinstance(item, dict)]


def _variant_for_slide(template_registry: dict[str, Any], slide_no: int, page_type: str) -> dict[str, Any] | None:
    return template_variants_by_slide(template_registry).get(slide_no, {}).get(page_type)


def _required_body_fields_for_variant(variant: dict[str, Any] | None, page_type: str, slide: dict[str, Any]) -> list[str]:
    if not variant:
        return []
    fields = [str(item) for item in (variant.get("required_body_fields") or [])]
    if page_type == "compare_table_page" and (
        isinstance(slide.get("compare_table_data"), dict)
        or isinstance((slide.get("visual_design") or {}).get("compare_table_data"), dict)
    ):
        fields = [field for field in fields if not (field == "table_header" or field.startswith("table_row_"))]
    return fields


def _block_target_field(block: dict[str, Any]) -> str:
    for key in ("target_field", "template_field", "body_field", "field"):
        value = str(block.get(key) or "").strip()
        if value:
            return value
    return ""


def _active_fields_hint(slide_no: int, page_type: str, fields: list[str]) -> str:
    allowed = ", ".join(fields) if fields else "(none)"
    return (
        f"Allowed active body fields: {allowed}. "
        "Use one of these values, or remove target_field and let the compiler map by role. "
        f"Inspect with: python scripts/describe_slide_fields.py --slide-no {slide_no} --page-type {page_type}"
    )


def _registered_page_types_hint(slide_no: int, variants: dict[str, dict[str, Any]]) -> str:
    if not variants:
        return f"No registered page types found for slide {slide_no}."
    formal = sorted(page_type for page_type, variant in variants.items() if variant.get("formal_allowed") is True)
    all_types = sorted(variants)
    if formal:
        return f"Formal-allowed page types for slide {slide_no}: {', '.join(formal)}."
    return f"Registered page types for slide {slide_no}: {', '.join(all_types)}."


def _collect_selected_metric_ids(analyses_by_id: dict[str, dict[str, Any]], issue_ids: list[str]) -> set[str]:
    values: set[str] = set()
    for analysis_id in issue_ids:
        values.update(analysis_metric_ids(analyses_by_id.get(analysis_id) or {}))
    return values


def _collect_selected_evidence_ids(analyses_by_id: dict[str, dict[str, Any]], issue_ids: list[str]) -> set[str]:
    values: set[str] = set()
    for analysis_id in issue_ids:
        values.update(analysis_evidence_ids(analyses_by_id.get(analysis_id) or {}))
    return values


def _ids_permitted_by_source_analyses(
    analyses_by_id: dict[str, dict[str, Any]],
    *,
    ids: list[str],
    source_analysis_ids: list[str],
    id_kind: str,
    permission_field: str,
) -> set[str]:
    permitted: set[str] = set()
    for analysis_id in source_analysis_ids:
        analysis = analyses_by_id.get(analysis_id) or {}
        if _usage(analysis).get(permission_field) is not True:
            continue
        if id_kind == "metric":
            permitted.update(analysis_metric_ids(analysis))
        else:
            permitted.update(analysis_evidence_ids(analysis))
    return {item for item in ids if item in permitted}


def _check_text_quality(slide: dict[str, Any], prefix: str, errors: list[str], warnings: list[str]) -> None:
    headline = str(slide.get("headline") or "").strip()
    main_message = str(slide.get("main_message") or "").strip()
    thesis = str(slide.get("page_thesis") or slide.get("page_answer") or "").strip()
    if normalize_text(headline) and normalize_text(headline) == normalize_text(main_message):
        errors.append(f"{prefix}: headline and main_message must not be identical")
    if normalize_text(headline) and normalize_text(headline) == normalize_text(thesis):
        warnings.append(f"{prefix}: headline duplicates page_thesis; rewrite headline as client-facing page copy")
    if headline and len(normalize_text(headline)) < 10:
        warnings.append(f"{prefix}: headline looks too thin to carry an IB page argument")
    if headline and not _looks_like_conclusion_headline(headline):
        warnings.append(f"{prefix}: headline may be a label rather than a conclusion-led title")

    body_norms: dict[str, int] = {}
    for idx, block in enumerate(_body_blocks(slide), start=1):
        copy = str(block.get("copy") or block.get("point") or "").strip()
        norm = normalize_text(copy)
        if len(norm) >= 8:
            body_norms[norm] = body_norms.get(norm, 0) + 1
        if normalize_text(copy) and normalize_text(copy) in {normalize_text(headline), normalize_text(main_message)}:
            errors.append(f"{prefix}: body_blocks[{idx}] duplicates headline/main_message")
    if any(count >= 2 for count in body_norms.values()):
        errors.append(f"{prefix}: duplicate body block copy; each active field needs a distinct page role")


def build_warning_repair_plan(warnings: list[str]) -> dict[str, Any]:
    targets: list[dict[str, Any]] = []
    for warning in warnings:
        warning_text = str(warning)
        if "headline may be a label" in warning_text:
            targets.append(
                {
                    "warning": warning_text,
                    "repair_target": "deck_blueprint.json",
                    "repair_fields": ["slides[].headline", "slides[].page_thesis", "slides[].main_message"],
                    "repair_hint": (
                        "Rewrite the headline as a client-facing conclusion with implication, not a topic label. "
                        "Use the structure: judgment + quantified support or transaction relevance. "
                        "Example: replace 'Competitive Landscape' with 'Fragmented competition leaves room for specialist base-makeup brands if channel economics hold'."
                    ),
                }
            )
        elif "headline looks too thin" in warning_text:
            targets.append(
                {
                    "warning": warning_text,
                    "repair_target": "deck_blueprint.json",
                    "repair_fields": ["slides[].headline"],
                    "repair_hint": "Expand the headline enough to carry the page argument; do not use a short label or isolated metric.",
                }
            )
        elif "headline duplicates page_thesis" in warning_text:
            targets.append(
                {
                    "warning": warning_text,
                    "repair_target": "deck_blueprint.json",
                    "repair_fields": ["slides[].headline", "slides[].page_thesis"],
                    "repair_hint": "Keep page_thesis as the planning statement and rewrite headline as polished PPT copy.",
                }
            )
        elif "target_field" in warning_text or "active field" in warning_text:
            targets.append(
                {
                    "warning": warning_text,
                    "repair_target": "deck_blueprint.json",
                    "repair_fields": ["slides[].body_blocks[].target_field"],
                    "repair_hint": "Use only active fields listed in the validator message or describe_slide_fields.py for the selected page type.",
                }
            )
    if not targets:
        return {
            "status": "no_warning_repairs_required",
            "targets": [],
            "instruction": "No deck-blueprint warnings require structured repair.",
        }
    return {
        "status": "advisory_repair_recommended",
        "instruction": (
            "Warnings are not schema failures, but they often explain why a technically valid deck feels thin or mechanical. "
            "Repair the listed deck_blueprint fields before compiling when the warning affects client-facing page quality."
        ),
        "targets": targets,
        "rerun_steps": [
            "scripts/validate_deck_blueprint.py",
            "scripts/compile_deck_blueprint.py",
            "scripts/validate_renderer_spec.py",
            "scripts/validate_content_quality.py",
        ],
    }


def validate(
    deck_blueprint: dict[str, Any],
    issue_analysis: dict[str, Any],
    template_registry: dict[str, Any],
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    warnings: list[str] = []
    error_repair_targets: list[dict[str, Any]] = []
    if deck_blueprint.get("schema_version") != "deck_blueprint_v1":
        errors.append("schema_version must be deck_blueprint_v1")
    if not non_empty_text(deck_blueprint.get("deck_storyline")):
        errors.append("deck_storyline is required")
    if _contains_marker(deck_blueprint):
        errors.append("deck_blueprint contains draft/TODO/placeholder markers")

    analyses_by_id = analysis_index(issue_analysis)
    variants_by_slide = template_variants_by_slide(template_registry)
    slides = deck_blueprint.get("slides") if isinstance(deck_blueprint, dict) else None
    if not isinstance(slides, list):
        return errors + ["slides must be an array"], warnings, []
    if len(slides) != 8:
        errors.append(f"slides must contain exactly 8 entries; found {len(slides)}")

    seen: set[int] = set()
    for idx, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            errors.append(f"slides[{idx}] must be an object")
            continue
        slide_no = slide.get("slide_no")
        prefix = f"slide {slide_no or idx}"
        if not isinstance(slide_no, int):
            errors.append(f"{prefix}: slide_no must be integer")
            continue
        if slide_no in seen:
            errors.append(f"{prefix}: duplicate slide_no")
        seen.add(slide_no)
        expected_role = FIXED_PAGE_ROLES.get(slide_no)
        role = str(slide.get("fixed_page_role") or slide.get("page_role") or "").strip()
        if role != expected_role:
            errors.append(f"{prefix}: fixed_page_role must be '{expected_role}', found '{role}'")

        for field in (
            "investor_question",
            "page_thesis",
            "page_argument",
            "visual_intent",
            "evidence_role",
            "headline",
            "main_message",
            "selected_page_type",
        ):
            if not non_empty_text(slide.get(field)):
                errors.append(f"{prefix}: {field} is required")
                _append_repair_target(
                    error_repair_targets,
                    repair_fields=[f"slides[{slide_no}].{field}"],
                    repair_hint=f"Complete {field} so the page argument and evidence role are explicit and usable for generation.",
                    slide_no=int(slide_no),
                    error_text=f"{prefix}: {field} is required",
                )
        evidence_role = str(slide.get("evidence_role") or "").strip()
        if evidence_role and evidence_role not in VALID_EVIDENCE_ROLES:
            errors.append(f"{prefix}: evidence_role '{evidence_role}' is invalid. Use one of: {', '.join(sorted(VALID_EVIDENCE_ROLES))}")
            _append_repair_target(
                error_repair_targets,
                repair_fields=[f"slides[{slide_no}].evidence_role"],
                repair_hint="Set evidence_role to one of: thesis_anchor, supporting_evidence, context_setting, caveat_only, open_question.",
                slide_no=int(slide_no),
                error_text=f"{prefix}: evidence_role '{evidence_role}' is invalid",
            )

        claim_strength = str(slide.get("claim_strength") or "").strip()
        if claim_strength not in VALID_CLAIM_STRENGTHS:
            errors.append(f"{prefix}: claim_strength must be one of {sorted(VALID_CLAIM_STRENGTHS)}")

        if (
            non_empty_text(slide.get("evidence_role"))
            and str(slide.get("evidence_role")) == "open_question"
            and claim_strength not in {"open_question", "hypothesis"}
        ):
            warnings.append(f"{prefix}: open_question evidence_role should align with open_question/hypothesis claim_strength")

        issue_ids = selected_issue_analysis_ids(slide)
        if not issue_ids:
            errors.append(f"{prefix}: issue_analysis_ids must select at least one issue analysis")
        missing_issue_ids = [analysis_id for analysis_id in issue_ids if analysis_id not in analyses_by_id]
        if missing_issue_ids:
            errors.append(f"{prefix}: issue_analysis_ids not found: {', '.join(missing_issue_ids)}")

        selected_metric_ids = _collect_selected_metric_ids(analyses_by_id, issue_ids)
        selected_evidence_ids = _collect_selected_evidence_ids(analyses_by_id, issue_ids)
        visual_plan = visual_plan_from_blueprint_slide(slide)
        page_type = str(slide.get("selected_page_type") or "").strip()
        slide_variants = variants_by_slide.get(slide_no, {})
        variant = slide_variants.get(page_type)
        required_fields = _required_body_fields_for_variant(variant, page_type, slide)
        if not variant:
            errors.append(
                f"{prefix}: selected_page_type '{page_type}' is not registered for this slide. "
                f"{_registered_page_types_hint(slide_no, slide_variants)}"
            )
            _append_repair_target(
                error_repair_targets,
                repair_fields=[f"slides[{slide_no}].selected_page_type"],
                repair_hint=(
                    f"Choose one of the formal-allowed page types for slide {slide_no}: {', '.join(sorted(slide_variants)) or 'none available'}. "
                    f"Then rerun validation. {_registered_page_types_hint(slide_no, slide_variants)}"
                ),
                slide_no=int(slide_no),
                error_text=f"{prefix}: selected_page_type '{page_type}' is not registered for this slide",
                active_fields=required_fields,
            )
        elif variant.get("formal_allowed") is not True:
            errors.append(
                f"{prefix}: selected_page_type '{page_type}' is not formal_allowed. "
                f"{_registered_page_types_hint(slide_no, slide_variants)}"
            )
            _append_repair_target(
                error_repair_targets,
                repair_fields=[f"slides[{slide_no}].selected_page_type"],
                repair_hint="Use a formal_allowed page type for all formal runs. Compare against template registry output."
                ,
                slide_no=int(slide_no),
                error_text=f"{prefix}: selected_page_type '{page_type}' is not formal_allowed",
                active_fields=required_fields,
            )
        targeted_fields: dict[str, int] = {}
        for block_idx, block in enumerate(_body_blocks(slide), start=1):
            target = _block_target_field(block)
            if not target:
                continue
            if target not in required_fields:
                errors.append(
                    f"{prefix}: body_blocks[{block_idx}] target_field '{target}' is not active for selected_page_type '{page_type}'. "
                    f"{_active_fields_hint(slide_no, page_type, required_fields)}"
                )
                _append_repair_target(
                    error_repair_targets,
                    repair_fields=[f"slides[{slide_no}].body_blocks[{block_idx}].target_field"],
                    repair_hint=(
                        "Use one of the active body fields shown in the validator message, or remove target_field and "
                        "let compiler map by role."
                    ),
                    slide_no=int(slide_no),
                    error_text=f"{prefix}: body_blocks[{block_idx}] target_field '{target}' is not active",
                    active_fields=required_fields,
                )
            elif target in targeted_fields:
                errors.append(
                    f"{prefix}: body_blocks[{block_idx}] duplicates target_field '{target}' already used by body_blocks[{targeted_fields[target]}]. "
                    f"{_active_fields_hint(slide_no, page_type, required_fields)}"
                )
                _append_repair_target(
                    error_repair_targets,
                    repair_fields=[f"slides[{slide_no}].body_blocks[{block_idx}].target_field", f"slides[{slide_no}].body_blocks[{targeted_fields[target]}].target_field"],
                    repair_hint="Use unique target_field values so each active template field receives at most one block.",
                    slide_no=int(slide_no),
                    error_text=f"{prefix}: body_blocks[{block_idx}] duplicates target_field '{target}'",
                    active_fields=required_fields,
                )
            else:
                targeted_fields[target] = block_idx
        if isinstance(slide.get("body_copy"), dict):
            missing_fields = [field for field in required_fields if not str(slide["body_copy"].get(field, "")).strip()]
            if missing_fields:
                warnings.append(
                    f"{prefix}: body_copy does not fill active template field(s): {', '.join(missing_fields)}. "
                    "This is a renderer/fit risk, not an evidence-boundary failure; prefer editing the page thesis "
                    "or selecting a simpler template instead of padding weak copy."
                )
        else:
            block_count = len(_body_blocks(slide))
            if block_count < len(required_fields):
                warnings.append(
                    f"{prefix}: body_blocks has {block_count} item(s), while selected template has "
                    f"{len(required_fields)} active body field(s). Compiler will map available blocks only; "
                    "choose a simpler template or add genuinely distinct copy if the page would feel thin."
                )

        _check_text_quality(slide, prefix, errors, warnings)

        proof_points = proof_points_from_blueprint_slide(slide)
        if not proof_points:
            errors.append(f"{prefix}: at least one body/visual proof point is required")
        body_evidence_ids: list[str] = []
        body_metric_ids: list[str] = []
        for point_idx, point in enumerate(proof_points, start=1):
            source_analysis_ids = unique([str(item).strip() for item in as_list(point.get("source_analysis_ids")) if str(item).strip()])
            evidence_ids = unique([str(item).strip() for item in as_list(point.get("evidence_ids")) if str(item).strip()])
            metric_ids = unique([str(item).strip() for item in as_list(point.get("metric_ids")) if str(item).strip()])
            body_evidence_ids.extend(evidence_ids)
            body_metric_ids.extend(metric_ids)
            missing_sources = [analysis_id for analysis_id in source_analysis_ids if analysis_id not in issue_ids]
            if missing_sources:
                errors.append(f"{prefix}: proof point {point_idx} source_analysis_ids outside slide issue_analysis_ids: {', '.join(missing_sources)}")
            evidence_outside = [ev_id for ev_id in evidence_ids if ev_id not in selected_evidence_ids]
            metric_outside = [met_id for met_id in metric_ids if met_id not in selected_metric_ids]
            if evidence_outside:
                errors.append(f"{prefix}: proof point {point_idx} evidence_ids outside selected issue analyses: {', '.join(evidence_outside)}")
            if metric_outside:
                errors.append(f"{prefix}: proof point {point_idx} metric_ids outside selected issue analyses: {', '.join(metric_outside)}")
            body_permitted = _ids_permitted_by_source_analyses(
                analyses_by_id,
                ids=evidence_ids,
                source_analysis_ids=source_analysis_ids,
                id_kind="evidence",
                permission_field="body_copy_allowed",
            )
            body_forbidden = sorted(set(evidence_ids) - body_permitted)
            if evidence_ids and body_forbidden:
                errors.append(f"{prefix}: proof point {point_idx} evidence lacks body_copy_allowed permission: {', '.join(body_forbidden)}")

        visual_metric_ids = visual_plan.get("visual_metric_ids") or metric_ids_from_visual(slide)
        if visual_plan.get("required_capability") in METRIC_VISUAL_CAPABILITIES and visual_metric_ids:
            visual_permitted: set[str] = set()
            for point in proof_points:
                source_ids = unique([str(item).strip() for item in as_list(point.get("source_analysis_ids")) if str(item).strip()])
                point_metric_ids = unique([str(item).strip() for item in as_list(point.get("metric_ids")) if str(item).strip()])
                visual_permitted.update(
                    _ids_permitted_by_source_analyses(
                        analyses_by_id,
                        ids=point_metric_ids,
                        source_analysis_ids=source_ids,
                        id_kind="metric",
                        permission_field="chart_allowed",
                    )
                )
            visual_forbidden = sorted(set(visual_metric_ids) - visual_permitted)
            if visual_forbidden:
                errors.append(f"{prefix}: visual metrics lack downstream_permission.chart_allowed: {', '.join(visual_forbidden)}")

        headline_permitted = any(_usage(analyses_by_id.get(analysis_id) or {}).get("headline_allowed") is True for analysis_id in issue_ids)
        if not headline_permitted and claim_strength not in {"hypothesis", "open_question"}:
            errors.append(f"{prefix}: no selected issue analysis permits headline usage")
        if not unique(body_evidence_ids) and not unique(body_metric_ids) and not as_list(slide.get("open_questions")):
            errors.append(f"{prefix}: page has no evidence, metrics, or open_questions")

    missing = set(FIXED_PAGE_ROLES) - seen
    if missing:
        errors.append("missing slide_no entries: " + ", ".join(str(num) for num in sorted(missing)))

    normalized = normalize_deck_blueprint_for_page_plan(deck_blueprint)
    if len(normalized.get("slides") or []) != len(slides):
        errors.append("deck_blueprint cannot be normalized into a page plan")
    return errors, warnings, error_repair_targets


_LAYOUT_BUDGET_HARD_OVERFLOW = 1.30  # > 130% of budget is an error


def check_layout_budget(
    deck_blueprint: dict[str, Any],
    layout_budget: dict[str, Any],
    errors: list[str],
    warnings: list[str],
) -> None:
    """Estimate body_copy field sizes against layout budget at blueprint stage.

    This catches content overload early, before template_fit or rendering.
    """
    if not isinstance(layout_budget, dict):
        return

    global_rules = layout_budget.get("global", {})
    global_body = global_rules.get("body_copy", {})
    default_limit = float(global_body.get("max_bullet_units_default", 88))

    slides = deck_blueprint.get("slides") if isinstance(deck_blueprint, dict) else None
    if not isinstance(slides, list):
        return

    for slide in slides:
        if not isinstance(slide, dict):
            continue
        slide_no = int(slide.get("slide_no") or 0)
        page_type = str(slide.get("selected_page_type") or "")
        rules = layout_rules_for(slide_no, page_type, layout_budget)
        if not isinstance(rules, dict):
            continue

        body_copy = slide.get("body_copy")
        if not isinstance(body_copy, dict):
            continue

        field_limits = rules.get("body_fields_max_units", {})
        for field_name, value in body_copy.items():
            if not isinstance(value, str) or not value.strip():
                continue
            field_limit = float(field_limits.get(field_name, default_limit))
            actual = display_units(value)
            if actual > field_limit * _LAYOUT_BUDGET_HARD_OVERFLOW:
                errors.append(
                    f"slide {slide_no}: '{field_name}' is {actual:.1f} layout units, "
                    f"budget is {field_limit:.1f} ({actual / field_limit:.0%}); "
                    f"reduce copy before downstream artifacts are generated"
                )
            elif actual > field_limit:
                warnings.append(
                    f"slide {slide_no}: '{field_name}' is {actual:.1f} layout units, "
                    f"budget is {field_limit:.1f} ({actual / field_limit:.0%}); "
                    f"consider trimming for cleaner template fit"
                )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deck-blueprint", required=True)
    parser.add_argument("--issue-analysis", required=True)
    parser.add_argument("--template-registry", required=True)
    parser.add_argument("--layout-budget", help="Optional layout_budget.json for early content-size checks.")
    parser.add_argument("--output")
    args = parser.parse_args()

    try:
        deck_blueprint_path = Path(args.deck_blueprint)
        issue_analysis_path = Path(args.issue_analysis)
        template_registry_path = Path(args.template_registry)
        deck_data = load_json_file(deck_blueprint_path)
        errors, warnings, repair_targets = validate(
            deck_data,
            load_json_file(issue_analysis_path),
            load_json_file(template_registry_path),
        )
        errors.extend(
            assert_formal_upstream_valid(
                [deck_blueprint_path, issue_analysis_path, template_registry_path],
                expected_names={"deck_blueprint.json", "industry_issue_analysis.json", "template_registry.json"},
                validation_rels=DECK_BLUEPRINT_UPSTREAM_VALIDATIONS,
                stage_name="deck_blueprint",
            )
        )
        if args.layout_budget:
            try:
                layout_budget = load_json_file(Path(args.layout_budget))
                check_layout_budget(deck_data, layout_budget, errors, warnings)
            except Exception as exc:
                warnings.append(f"layout budget check skipped: {exc}")
    except Exception as exc:
        errors, warnings, repair_targets = [str(exc)], [], []

    result = {
        "is_valid": not errors,
        "deck_blueprint": args.deck_blueprint,
        "issue_analysis": args.issue_analysis,
        "template_registry": args.template_registry,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "repair_plan": _build_error_repair_plan(errors, repair_targets),
        "warning_repair_plan": build_warning_repair_plan(warnings),
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
