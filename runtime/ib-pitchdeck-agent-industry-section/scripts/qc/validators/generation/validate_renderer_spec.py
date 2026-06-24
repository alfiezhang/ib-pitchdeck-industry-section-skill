#!/usr/bin/env python3
"""Validate renderer_spec.json as the formal PPT renderer input."""

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
import sys
from pathlib import Path
from typing import Any

from deck_blueprint_utils import normalize_deck_blueprint_for_page_plan
from json_utils import load_json_file
from renderer_token_source import build_token_source
from template_contract_utils import active_body_fields
from upstream_validation import RENDERER_SPEC_UPSTREAM_VALIDATIONS, assert_formal_upstream_valid


DRAFT_MARKERS = (
    "DRAFT_REWRITE_REQUIRED",
    "TODO_REPLACE",
    "TODO:",
    "PLACEHOLDER",
)

FIXED_PAGE_ROLES = {
    1: "industry_overview",
    2: "market_size_segmentation",
    3: "key_industry_drivers",
    4: "value_chain_profit_pool",
    5: "key_barriers_value_drivers",
    6: "competitive_landscape",
    7: "industry_trends_future_evolution",
    8: "transaction_implications",
}

VALID_EXHIBIT_TYPES = {
    "chart",
    "table",
    "matrix",
    "flow",
    "bridge",
    "value_chain",
    "kpi_cards",
    "driver_cards",
    "trend_cards",
    "diligence_grid",
    "peer_comparison",
    "channel_flow",
    "unit_economics_bridge",
    "sku_traction_table",
    "evidence_gap_matrix",
}

CHART_TYPES = {
    "bar",
    "column",
    "clustered_bar",
    "clustered_column",
    "stacked_bar",
    "stacked_column",
    "line",
    "line_chart",
}

TABLE_EXHIBIT_TYPES = {
    "table",
    "matrix",
    "diligence_grid",
    "peer_comparison",
    "sku_traction_table",
    "evidence_gap_matrix",
}

BODY_STRUCTURED_EXHIBIT_TYPES = {
    "flow",
    "bridge",
    "value_chain",
    "channel_flow",
    "unit_economics_bridge",
    "driver_cards",
    "trend_cards",
    "kpi_cards",
}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _page_plan_index(page_plan: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {
        int(item.get("slide_no")): item
        for item in page_plan.get("slides") or []
        if isinstance(item, dict) and isinstance(item.get("slide_no"), int)
    }


def _contract_index(page_contract: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {
        int(item.get("slide_no")): item
        for item in page_contract.get("slides") or []
        if isinstance(item, dict) and isinstance(item.get("slide_no"), int)
    }


def _template_variants(template_registry: dict[str, Any]) -> dict[int, dict[str, dict[str, Any]]]:
    result: dict[int, dict[str, dict[str, Any]]] = {}
    for slide in template_registry.get("slides") or []:
        if not isinstance(slide, dict) or not isinstance(slide.get("slide_no"), int):
            continue
        result[int(slide["slide_no"])] = {
            str(variant.get("page_type")): variant
            for variant in slide.get("variants") or []
            if isinstance(variant, dict) and variant.get("page_type")
        }
    return result


def _metric_ids_in_value(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for item in value.values():
            found.update(_metric_ids_in_value(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_metric_ids_in_value(item))
    elif isinstance(value, str) and value.startswith("MET-"):
        found.add(value)
    return found


def _exhibit(slide: dict[str, Any]) -> dict[str, Any]:
    return slide.get("exhibit") if isinstance(slide.get("exhibit"), dict) else {}


def _exhibit_type(slide: dict[str, Any]) -> str:
    return str(_exhibit(slide).get("exhibit_type") or "").strip()


def _chart_datapoint_count(chart_data: dict[str, Any]) -> int:
    series = chart_data.get("series") if isinstance(chart_data.get("series"), list) else []
    count = 0
    for item in series:
        if isinstance(item, dict) and isinstance(item.get("values"), list):
            count += len(item.get("values") or [])
    if count:
        return count
    source_rows = chart_data.get("source_rows") if isinstance(chart_data.get("source_rows"), list) else []
    return len([row for row in source_rows if isinstance(row, dict)])


def _compare_table_row_count(table_data: dict[str, Any]) -> int:
    rows = table_data.get("rows") if isinstance(table_data.get("rows"), list) else []
    count = len([row for row in rows if isinstance(row, (dict, list, str)) and str(row).strip()])
    if count:
        return count
    for idx in range(1, 8):
        if str(table_data.get(f"table_row_{idx}") or "").strip():
            count += 1
    return count


def _filled_body_copy_count(body_copy: dict[str, Any]) -> int:
    return len([value for value in body_copy.values() if str(value or "").strip()])


def _contains_draft_marker(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_draft_marker(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_draft_marker(item) for item in value)
    if isinstance(value, str):
        return any(marker.lower() in value.lower() for marker in DRAFT_MARKERS)
    return False


def _normalize(text: Any) -> str:
    import re

    raw = str(text or "").strip().lower()
    raw = re.sub(r"^[•\-–—]+\s*", "", raw)
    raw = re.sub(r"[\s\W_]+", "", raw, flags=re.UNICODE)
    return raw


def validate(
    renderer_spec: dict[str, Any],
    template_registry: dict[str, Any],
    page_plan: dict[str, Any],
    page_contract: dict[str, Any],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if renderer_spec.get("schema_version") != "renderer_spec_v1":
        errors.append("schema_version must be renderer_spec_v1")

    strategy_by_no = _page_plan_index(page_plan)
    contract_by_no = _contract_index(page_contract)
    variants_by_slide = _template_variants(template_registry)
    structured_exhibit_count = 0

    slides = renderer_spec.get("slides") if isinstance(renderer_spec, dict) else None
    if not isinstance(slides, list):
        return ["slides must be an array"], warnings
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
        fixed_role = str(slide.get("fixed_page_role") or slide.get("slide_role") or "").strip()
        if fixed_role != expected_role:
            errors.append(f"{prefix}: fixed_page_role must be '{expected_role}'")

        strategy = strategy_by_no.get(slide_no)
        contract = contract_by_no.get(slide_no)
        if not strategy:
            errors.append(f"{prefix}: missing page plan entry")
            strategy = {}
        if not contract:
            errors.append(f"{prefix}: missing page_evidence_contract entry")
            contract = {}
        page_type = str(slide.get("selected_page_type") or "").strip()
        visual_plan = strategy.get("visual_plan") if isinstance(strategy.get("visual_plan"), dict) else {}
        if page_type != str(visual_plan.get("preferred_template_variant") or "").strip():
            errors.append(f"{prefix}: selected_page_type must match page plan preferred_template_variant")
        variant = variants_by_slide.get(slide_no, {}).get(page_type)
        if not variant:
            errors.append(f"{prefix}: selected_page_type '{page_type}' is not registered")
            variant = {}
        elif variant.get("formal_allowed") is not True:
            errors.append(f"{prefix}: selected_page_type '{page_type}' is not formal_allowed")

        primary = str(slide.get("primary_issue_analysis_id") or "").strip()
        if primary != str(strategy.get("primary_issue_analysis_id") or "").strip():
            errors.append(f"{prefix}: primary_issue_analysis_id must match page plan")
        if primary != str(contract.get("primary_issue_analysis_id") or "").strip():
            errors.append(f"{prefix}: primary_issue_analysis_id must match page_evidence_contract")

        issue_analysis_ids = {str(item).strip() for item in _as_list(slide.get("issue_analysis_ids")) if str(item).strip()}
        allowed_analysis_ids = {str(strategy.get("primary_issue_analysis_id") or "").strip()}
        allowed_analysis_ids.update(str(item).strip() for item in _as_list(strategy.get("supporting_issue_analysis_ids")) if str(item).strip())
        invalid_analysis_ids = sorted(issue_analysis_ids - allowed_analysis_ids)
        if invalid_analysis_ids:
            errors.append(f"{prefix}: issue_analysis_ids outside page plan: {', '.join(invalid_analysis_ids)}")

        claim_strength = str(slide.get("claim_strength") or "").strip()
        if contract.get("claim_strength") and claim_strength != str(contract.get("claim_strength")):
            errors.append(f"{prefix}: claim_strength must match page_evidence_contract")

        body_copy = slide.get("body_copy")
        if not isinstance(body_copy, dict):
            errors.append(f"{prefix}: body_copy must be object")
            body_copy = {}
        if (
            _contains_draft_marker(slide.get("headline"))
            or _contains_draft_marker(slide.get("main_message"))
            or _contains_draft_marker(body_copy)
            or _contains_draft_marker(slide.get("chart_data"))
            or _contains_draft_marker(slide.get("compare_table_data"))
            or _contains_draft_marker(slide.get("exhibit"))
        ):
            errors.append(f"{prefix}: renderer_spec still contains draft/TODO markers; complete the slide-copy pass before validation")

        exhibit = _exhibit(slide)
        exhibit_type = _exhibit_type(slide)
        if not exhibit:
            errors.append(f"{prefix}: exhibit is required; renderer_spec must preserve the blueprint's exhibit-first contract")
        else:
            structured_exhibit_count += 1
            if exhibit_type not in VALID_EXHIBIT_TYPES:
                errors.append(f"{prefix}: exhibit.exhibit_type '{exhibit_type or '(missing)'}' is invalid")
            for field in ("why_this_exhibit", "visual_structure", "density_target", "fallback_if_data_limited"):
                if not str(exhibit.get(field) or "").strip():
                    errors.append(f"{prefix}: exhibit.{field} is required")
            inputs = [str(item).strip() for item in _as_list(exhibit.get("data_or_evidence_inputs")) if str(item).strip()]
            if not inputs:
                errors.append(f"{prefix}: exhibit.data_or_evidence_inputs must not be empty")

        template_required_fields = [str(item) for item in (variant.get("required_body_fields") or [])]
        required_fields = active_body_fields(template_required_fields, page_type, slide)
        missing_fields = [field for field in required_fields if not str(body_copy.get(field, "")).strip()]
        if missing_fields:
            errors.append(f"{prefix}: missing/empty required body_copy fields: {', '.join(missing_fields)}")
        extra_fields = sorted(set(body_copy) - set(required_fields))
        if extra_fields:
            errors.append(f"{prefix}: extra body_copy fields ignored by template: {', '.join(extra_fields)}")

        headline_norm = _normalize(slide.get("headline"))
        main_norm = _normalize(slide.get("main_message"))
        if headline_norm and main_norm and headline_norm == main_norm:
            errors.append(f"{prefix}: headline and main_message must not be identical")
        normalized_body_values: dict[str, list[str]] = {}
        for field, value in body_copy.items():
            norm = _normalize(value)
            if len(norm) >= 8:
                normalized_body_values.setdefault(norm, []).append(str(field))
        for _, fields in normalized_body_values.items():
            if len(fields) >= 2:
                errors.append(f"{prefix}: duplicate body_copy values across fields: {', '.join(fields)}")

        chart_data = slide.get("chart_data")
        chart_metric_ids = _metric_ids_in_value(chart_data)
        contract_chart_ids = {str(item).strip() for item in _as_list(contract.get("chart_metric_ids")) if str(item).strip()}
        has_chart = isinstance(chart_data, dict) and str(chart_data.get("chart_type") or "").lower() not in {"", "none", "no_chart", "text"}
        chart_type = str(chart_data.get("chart_type") or "").lower() if isinstance(chart_data, dict) else ""
        chart_datapoints = _chart_datapoint_count(chart_data) if isinstance(chart_data, dict) else 0
        if has_chart and contract.get("chart_allowed") is not True:
            errors.append(f"{prefix}: chart_data present but page_evidence_contract.chart_allowed=false")
        invalid_chart_ids = sorted(chart_metric_ids - contract_chart_ids)
        if invalid_chart_ids:
            errors.append(f"{prefix}: chart metric IDs outside page_evidence_contract.chart_metric_ids: {', '.join(invalid_chart_ids)}")
        if exhibit_type == "chart":
            if not has_chart:
                errors.append(f"{prefix}: chart exhibit requires chart_data")
            elif chart_type not in CHART_TYPES:
                errors.append(f"{prefix}: chart exhibit uses unsupported chart_data.chart_type '{chart_type or '(missing)'}'")
            elif chart_datapoints < 2:
                errors.append(
                    f"{prefix}: chart exhibit has only {chart_datapoints} datapoint(s); "
                    "single-point charts are not valid formal exhibits"
                )
        elif has_chart and chart_type in CHART_TYPES and chart_datapoints < 2:
            errors.append(f"{prefix}: chart_data has only {chart_datapoints} datapoint(s); use a table/KPI-card exhibit instead of a single-point chart")

        compare_table_data = slide.get("compare_table_data") if isinstance(slide.get("compare_table_data"), dict) else {}
        if exhibit_type in TABLE_EXHIBIT_TYPES and _compare_table_row_count(compare_table_data) < 3 and chart_datapoints < 2:
            errors.append(f"{prefix}: {exhibit_type} exhibit needs at least 3 compare_table_data rows or at least 2 matrix/chart datapoints")
        if exhibit_type in BODY_STRUCTURED_EXHIBIT_TYPES:
            min_fields = 6 if exhibit_type == "value_chain" else 3
            if _filled_body_copy_count(body_copy) < min_fields:
                errors.append(f"{prefix}: {exhibit_type} exhibit needs at least {min_fields} filled body_copy fields")

        evidence_ids = {str(item).strip() for item in _as_list(slide.get("evidence_ids")) if str(item).strip()}
        contract_evidence_ids = {str(item).strip() for item in _as_list(contract.get("body_evidence_ids")) if str(item).strip()}
        invalid_evidence_ids = sorted(evidence_ids - contract_evidence_ids)
        if invalid_evidence_ids:
            errors.append(f"{prefix}: evidence_ids outside page_evidence_contract.body_evidence_ids: {', '.join(invalid_evidence_ids)}")

    missing = set(FIXED_PAGE_ROLES) - seen
    if missing:
        errors.append("missing slide_no entries: " + ", ".join(str(num) for num in sorted(missing)))
    if structured_exhibit_count < 6:
        errors.append(
            f"renderer_spec has only {structured_exhibit_count} structured exhibit slide(s); "
            "formal output needs at least 6 exhibit-led pages"
        )

    try:
        token_result = build_token_source(renderer_spec)
    except Exception as exc:
        errors.append(f"renderer_spec cannot be converted into token source: {exc}")
    else:
        for warning in token_result.get("warnings") or []:
            if (
                "missing active body_copy fields" in warning
                or "empty active body_copy fields" in warning
                or "extra body_copy fields ignored" in warning
            ):
                errors.append(warning)
            else:
                warnings.append(warning)
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--renderer-spec", required=True)
    parser.add_argument("--template-registry", required=True)
    parser.add_argument("--deck-blueprint", required=True)
    parser.add_argument("--page-contract", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    try:
        renderer_spec_path = Path(args.renderer_spec)
        template_registry_path = Path(args.template_registry)
        deck_blueprint_path = Path(args.deck_blueprint)
        page_contract_path = Path(args.page_contract)
        renderer_spec = load_json_file(renderer_spec_path)
        template_registry = load_json_file(template_registry_path)
        page_plan = normalize_deck_blueprint_for_page_plan(load_json_file(deck_blueprint_path))
        page_contract = load_json_file(page_contract_path)
        errors, warnings = validate(renderer_spec, template_registry, page_plan, page_contract)
        errors.extend(
            assert_formal_upstream_valid(
                [renderer_spec_path, template_registry_path, deck_blueprint_path, page_contract_path],
                expected_names={"renderer_spec.json", "template_registry.json", "deck_blueprint.json", "page_evidence_contract.json"},
                validation_rels=RENDERER_SPEC_UPSTREAM_VALIDATIONS,
                stage_name="renderer_spec",
            )
        )
    except Exception as exc:
        errors, warnings = [str(exc)], []

    result = {
        "is_valid": not errors,
        "renderer_spec": args.renderer_spec,
        "template_registry": args.template_registry,
        "deck_blueprint": args.deck_blueprint,
        "page_contract": args.page_contract,
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
