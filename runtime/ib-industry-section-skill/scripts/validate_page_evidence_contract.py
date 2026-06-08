#!/usr/bin/env python3
"""Validate page_evidence_contract.json against issue analysis and page-plan artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from deck_blueprint_utils import normalize_deck_blueprint_for_page_plan
from json_utils import load_json_file
from upstream_validation import COMPILE_UPSTREAM_VALIDATIONS, assert_formal_upstream_valid


VALID_SLIDE_ROLES = {
    1: "industry_overview",
    2: "market_size_segmentation",
    3: "key_industry_drivers",
    4: "value_chain_profit_pool",
    5: "key_barriers_value_drivers",
    6: "competitive_landscape",
    7: "industry_trends_future_evolution",
    8: "transaction_implications",
}
VALID_CLAIM_STRENGTHS = {
    "hard_fact",
    "supported_inference",
    "directional_inference",
    "management_claim",
    "hypothesis",
    "open_question",
}
METRIC_VISUAL_CAPABILITIES = {"chart", "table", "matrix", "cards"}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _analysis_index(pool: dict[str, Any]) -> dict[str, dict[str, Any]]:
    analyses = pool.get("issue_analyses") if isinstance(pool, dict) else []
    if not isinstance(analyses, list):
        return {}
    return {str(item.get("analysis_id")): item for item in analyses if isinstance(item, dict) and item.get("analysis_id")}


def _page_plan_index(page_plan: dict[str, Any]) -> dict[int, dict[str, Any]]:
    slides = page_plan.get("slides") if isinstance(page_plan, dict) else []
    if not isinstance(slides, list):
        return {}
    return {int(item.get("slide_no")): item for item in slides if isinstance(item, dict) and isinstance(item.get("slide_no"), int)}


def _usage(analysis: dict[str, Any]) -> dict[str, Any]:
    usage = analysis.get("downstream_permission")
    return usage if isinstance(usage, dict) else {}


def _analysis_metric_ids(analysis: dict[str, Any]) -> set[str]:
    values = {str(item).strip() for item in _as_list(analysis.get("metric_ids")) if str(item).strip()}
    for point in _as_list(analysis.get("supporting_points")):
        if isinstance(point, dict):
            values.update(str(item).strip() for item in _as_list(point.get("metric_ids")) if str(item).strip())
    return values


def _analysis_evidence_ids(analysis: dict[str, Any]) -> set[str]:
    values = {str(item).strip() for item in _as_list(analysis.get("evidence_ids")) if str(item).strip()}
    for point in _as_list(analysis.get("supporting_points")):
        if isinstance(point, dict):
            values.update(str(item).strip() for item in _as_list(point.get("evidence_ids")) if str(item).strip())
    return values


def _selected_analysis_ids(strategy_entry: dict[str, Any]) -> set[str]:
    values = {str(item).strip() for item in _as_list(strategy_entry.get("supporting_issue_analysis_ids")) if str(item).strip()}
    primary = str(strategy_entry.get("primary_issue_analysis_id") or "").strip()
    if primary:
        values.add(primary)
    return values


def _proof_metric_ids(strategy_entry: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for point in _as_list(strategy_entry.get("proof_points")):
        if isinstance(point, dict):
            values.update(str(item).strip() for item in _as_list(point.get("metric_ids")) if str(item).strip())
    return values


def _strategy_visual_metric_ids(strategy_entry: dict[str, Any], fallback_metric_ids: set[str]) -> set[str]:
    visual_plan = strategy_entry.get("visual_plan") if isinstance(strategy_entry.get("visual_plan"), dict) else {}
    if isinstance(visual_plan.get("visual_metric_ids"), list):
        return {str(item).strip() for item in visual_plan.get("visual_metric_ids") if str(item).strip()}
    return set(fallback_metric_ids)


def _proof_evidence_ids(strategy_entry: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for point in _as_list(strategy_entry.get("proof_points")):
        if isinstance(point, dict):
            values.update(str(item).strip() for item in _as_list(point.get("evidence_ids")) if str(item).strip())
    return values


def _normalized_proof_points(entry: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for point in _as_list(entry.get("proof_points")):
        if not isinstance(point, dict):
            continue
        normalized = {
            "point": str(point.get("point") or "").strip(),
            "source_analysis_ids": [
                str(item).strip()
                for item in _as_list(point.get("source_analysis_ids"))
                if str(item).strip()
            ],
            "evidence_ids": [
                str(item).strip()
                for item in _as_list(point.get("evidence_ids"))
                if str(item).strip()
            ],
            "metric_ids": [
                str(item).strip()
                for item in _as_list(point.get("metric_ids"))
                if str(item).strip()
            ],
            "claim_strength": str(point.get("claim_strength") or "").strip(),
        }
        visual_role = str(point.get("visual_role") or "").strip()
        if visual_role:
            normalized["visual_role"] = visual_role
        caveat = str(point.get("caveat") or "").strip()
        if caveat:
            normalized["caveat"] = caveat
        result.append(normalized)
    return result


def _proof_ids_with_permission(
    strategy_entry: dict[str, Any],
    analyses_by_id: dict[str, dict[str, Any]],
    *,
    id_field: str,
    permission_field: str,
) -> set[str]:
    values: set[str] = set()
    for point in _as_list(strategy_entry.get("proof_points")):
        if not isinstance(point, dict):
            continue
        point_ids = {str(item).strip() for item in _as_list(point.get(id_field)) if str(item).strip()}
        if not point_ids:
            continue
        source_ids = [str(item).strip() for item in _as_list(point.get("source_analysis_ids")) if str(item).strip()]
        permitted: set[str] = set()
        for analysis_id in source_ids:
            analysis = analyses_by_id.get(analysis_id) or {}
            if _usage(analysis).get(permission_field) is not True:
                continue
            if id_field == "metric_ids":
                permitted.update(_analysis_metric_ids(analysis))
            elif id_field == "evidence_ids":
                permitted.update(_analysis_evidence_ids(analysis))
        values.update(point_ids & permitted)
    return values


def _proof_ids_without_permission(
    strategy_entry: dict[str, Any],
    analyses_by_id: dict[str, dict[str, Any]],
    *,
    id_field: str,
    permission_field: str,
) -> set[str]:
    all_ids: set[str] = set()
    for point in _as_list(strategy_entry.get("proof_points")):
        if isinstance(point, dict):
            all_ids.update(str(item).strip() for item in _as_list(point.get(id_field)) if str(item).strip())
    return all_ids - _proof_ids_with_permission(
        strategy_entry,
        analyses_by_id,
        id_field=id_field,
        permission_field=permission_field,
    )


def _mapped_metric_ids(analyses_by_id: dict[str, dict[str, Any]], analysis_ids: set[str]) -> set[str]:
    values: set[str] = set()
    for analysis_id in analysis_ids:
        analysis = analyses_by_id.get(analysis_id) or {}
        values.update(str(item).strip() for item in _as_list(analysis.get("metric_ids")) if str(item).strip())
        for point in _as_list(analysis.get("supporting_points")):
            if isinstance(point, dict):
                values.update(str(item).strip() for item in _as_list(point.get("metric_ids")) if str(item).strip())
    return values


def _mapped_evidence_ids(analyses_by_id: dict[str, dict[str, Any]], analysis_ids: set[str]) -> set[str]:
    values: set[str] = set()
    for analysis_id in analysis_ids:
        analysis = analyses_by_id.get(analysis_id) or {}
        values.update(str(item).strip() for item in _as_list(analysis.get("evidence_ids")) if str(item).strip())
        for point in _as_list(analysis.get("supporting_points")):
            if isinstance(point, dict):
                values.update(str(item).strip() for item in _as_list(point.get("evidence_ids")) if str(item).strip())
    return values


def _strength_rank(value: str) -> int:
    order = {
        "open_question": 0,
        "hypothesis": 1,
        "management_claim": 2,
        "directional_inference": 3,
        "supported_inference": 4,
        "hard_fact": 5,
    }
    return order.get(value, -1)


def validate(pool: dict[str, Any], page_plan: dict[str, Any], page_contract: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    analyses_by_id = _analysis_index(pool)
    strategy_by_no = _page_plan_index(page_plan)

    slides = page_contract.get("slides") if isinstance(page_contract, dict) else None
    if not isinstance(slides, list):
        return ["slides must be an array"], warnings
    if len(slides) != 8:
        errors.append(f"slides must contain exactly 8 entries; found {len(slides)}")

    seen_slide_numbers: set[int] = set()
    for idx, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            errors.append(f"slides[{idx}] must be an object")
            continue
        slide_no = slide.get("slide_no")
        prefix = f"slide {slide_no or idx}"
        if not isinstance(slide_no, int):
            errors.append(f"{prefix}: slide_no must be an integer")
            continue
        if slide_no in seen_slide_numbers:
            errors.append(f"{prefix}: duplicate slide_no")
        seen_slide_numbers.add(slide_no)

        expected_role = VALID_SLIDE_ROLES.get(slide_no)
        page_role = str(slide.get("page_role") or "").strip()
        if page_role != expected_role:
            errors.append(f"{prefix}: page_role must be '{expected_role}', found '{page_role}'")

        for field in ("page_question", "proof_standard", "evidence_gap_handling"):
            if not _non_empty_text(slide.get(field)):
                errors.append(f"{prefix}: {field} is required")

        strategy_entry = strategy_by_no.get(slide_no)
        if not strategy_entry:
            errors.append(f"{prefix}: missing matching slide in page plan")
            mapped_ids: set[str] = set()
            proof_metric_ids: set[str] = set()
            proof_evidence_ids: set[str] = set()
            expected_proof_points: list[dict[str, Any]] = []
            strategy_visual_plan: dict[str, Any] = {}
        else:
            if page_role != str(strategy_entry.get("fixed_page_role") or "").strip():
                errors.append(f"{prefix}: page_role does not match page plan fixed_page_role")
            if str(slide.get("page_question") or "").strip() != str(strategy_entry.get("investor_question") or "").strip():
                errors.append(f"{prefix}: page_question must match page plan investor_question")
            if str(slide.get("headline_claim") or "").strip() != str(strategy_entry.get("page_answer") or "").strip():
                errors.append(f"{prefix}: headline_claim must match page plan page_answer/page_thesis")
            mapped_ids = _selected_analysis_ids(strategy_entry)
            proof_metric_ids = _proof_metric_ids(strategy_entry)
            strategy_visual_metric_ids = _strategy_visual_metric_ids(strategy_entry, proof_metric_ids)
            proof_evidence_ids = _proof_evidence_ids(strategy_entry)
            expected_proof_points = _normalized_proof_points(strategy_entry)
            strategy_visual_plan = strategy_entry.get("visual_plan") if isinstance(strategy_entry.get("visual_plan"), dict) else {}

        primary_id = str(slide.get("primary_issue_analysis_id") or "").strip()
        if strategy_entry and primary_id != str(strategy_entry.get("primary_issue_analysis_id") or "").strip():
            errors.append(f"{prefix}: primary_issue_analysis_id must match page plan primary_issue_analysis_id")
        primary = analyses_by_id.get(primary_id)
        if not primary:
            errors.append(f"{prefix}: primary_issue_analysis_id {primary_id or '<blank>'} not found in issue analysis")

        supporting_ids = {str(item).strip() for item in _as_list(slide.get("supporting_issue_analysis_ids")) if str(item).strip()}
        invalid_supporting = sorted(supporting_ids - mapped_ids)
        if invalid_supporting:
            errors.append(f"{prefix}: supporting_issue_analysis_ids not selected in page plan: {', '.join(invalid_supporting)}")

        claim_strength = str(slide.get("claim_strength") or "").strip()
        if claim_strength not in VALID_CLAIM_STRENGTHS:
            errors.append(f"{prefix}: claim_strength must be one of {sorted(VALID_CLAIM_STRENGTHS)}")
        strategy_strength = str((strategy_entry or {}).get("claim_strength") or "").strip()
        if strategy_strength in VALID_CLAIM_STRENGTHS and claim_strength in VALID_CLAIM_STRENGTHS:
            if _strength_rank(claim_strength) > _strength_rank(strategy_strength):
                errors.append(f"{prefix}: page contract claim_strength cannot be stronger than page plan claim_strength")

        headline_allowed = slide.get("headline_allowed") is True
        chart_allowed = slide.get("chart_allowed") is True
        visual_metric_allowed = slide.get("visual_metric_allowed") is True
        if headline_allowed and primary and _usage(primary).get("headline_allowed") is not True:
            errors.append(f"{prefix}: headline_allowed=true but primary issue analysis does not allow headlines")
        capability = str(strategy_visual_plan.get("required_capability") or "")
        visual_permitted_metrics = (
            _proof_ids_with_permission(
                strategy_entry or {},
                analyses_by_id,
                id_field="metric_ids",
                permission_field="chart_allowed",
            )
            if strategy_entry
            else set()
        )
        if not strategy_entry:
            strategy_visual_metric_ids = set()
        chart_permission_failures = set(strategy_visual_metric_ids) - visual_permitted_metrics
        expected_visual_metric_allowed = (
            capability in METRIC_VISUAL_CAPABILITIES
            and bool(strategy_visual_metric_ids)
            and not chart_permission_failures
        )
        body_permission_failures = (
            _proof_ids_without_permission(
                strategy_entry or {},
                analyses_by_id,
                id_field="evidence_ids",
                permission_field="body_copy_allowed",
            )
            if strategy_entry
            else set()
        )
        if capability in METRIC_VISUAL_CAPABILITIES and chart_permission_failures:
            errors.append(
                f"{prefix}: visual_plan.visual_metric_ids require downstream_permission.chart_allowed=true: "
                + ", ".join(sorted(chart_permission_failures))
            )
        if body_permission_failures:
            errors.append(
                f"{prefix}: body evidence proof_points require downstream_permission.body_copy_allowed=true: "
                + ", ".join(sorted(body_permission_failures))
            )
        if strategy_entry and visual_metric_allowed != expected_visual_metric_allowed:
            errors.append(
                f"{prefix}: visual_metric_allowed must match page plan visual required_capability "
                f"in {sorted(METRIC_VISUAL_CAPABILITIES)}"
            )
        allowed_visual_metric_ids = {
            str(item).strip()
            for item in _as_list(slide.get("allowed_visual_metric_ids"))
            if str(item).strip()
        }
        if visual_metric_allowed:
            outside_visual_permission = sorted(allowed_visual_metric_ids - visual_permitted_metrics)
            if outside_visual_permission:
                errors.append(
                    f"{prefix}: allowed_visual_metric_ids not permitted by source issue analyses: "
                    + ", ".join(outside_visual_permission)
                )
            missing_visual_metrics = sorted(strategy_visual_metric_ids - allowed_visual_metric_ids)
            if missing_visual_metrics:
                errors.append(
                    f"{prefix}: allowed_visual_metric_ids must include page plan visual_metric_ids: "
                    + ", ".join(missing_visual_metrics)
                )
        elif allowed_visual_metric_ids:
            errors.append(f"{prefix}: allowed_visual_metric_ids must be empty when visual_metric_allowed=false")
        if chart_allowed:
            chart_metric_ids = {str(item).strip() for item in _as_list(slide.get("chart_metric_ids")) if str(item).strip()}
            if not chart_metric_ids:
                errors.append(f"{prefix}: chart_allowed=true requires non-empty chart_metric_ids")
            chart_permitted_metrics = _proof_ids_with_permission(
                strategy_entry or {},
                analyses_by_id,
                id_field="metric_ids",
                permission_field="chart_allowed",
            )
            outside_chart_permission = sorted(chart_metric_ids - chart_permitted_metrics)
            if outside_chart_permission:
                errors.append(
                    f"{prefix}: chart_metric_ids not permitted by source issue analyses: "
                    + ", ".join(outside_chart_permission)
                )
            mapped_metrics = _mapped_metric_ids(analyses_by_id, mapped_ids)
            missing_metrics = sorted(chart_metric_ids - mapped_metrics)
            if missing_metrics:
                errors.append(f"{prefix}: chart_metric_ids not present in mapped issue analyses: {', '.join(missing_metrics)}")
            metrics_outside_proof = sorted(chart_metric_ids - proof_metric_ids)
            if metrics_outside_proof:
                errors.append(f"{prefix}: chart_metric_ids not present in page plan proof_points: {', '.join(metrics_outside_proof)}")
            missing_proof_metrics = sorted(strategy_visual_metric_ids - chart_metric_ids)
            if str(strategy_visual_plan.get("required_capability") or "") == "chart" and missing_proof_metrics:
                errors.append(f"{prefix}: chart_metric_ids must include page plan visual_metric_ids: {', '.join(missing_proof_metrics)}")
        if strategy_entry:
            expected_chart_allowed = capability == "chart" and bool(strategy_visual_metric_ids) and not chart_permission_failures
            if chart_allowed != expected_chart_allowed:
                errors.append(f"{prefix}: chart_allowed must match chart capability plus downstream_permission.chart_allowed")
        actual_proof_points = _normalized_proof_points(slide)
        if actual_proof_points != expected_proof_points:
            errors.append(f"{prefix}: proof_points must match page plan proof_points exactly")

        body_evidence_ids = {str(item).strip() for item in _as_list(slide.get("body_evidence_ids")) if str(item).strip()}
        body_permitted_evidence = _proof_ids_with_permission(
            strategy_entry or {},
            analyses_by_id,
            id_field="evidence_ids",
            permission_field="body_copy_allowed",
        )
        outside_body_permission = sorted(body_evidence_ids - body_permitted_evidence)
        if outside_body_permission:
            errors.append(
                f"{prefix}: body_evidence_ids not permitted by source issue analyses: "
                + ", ".join(outside_body_permission)
            )
        mapped_evidence = _mapped_evidence_ids(analyses_by_id, mapped_ids)
        missing_evidence = sorted(body_evidence_ids - mapped_evidence)
        if missing_evidence:
            errors.append(f"{prefix}: body_evidence_ids not present in mapped issue analyses: {', '.join(missing_evidence)}")
        evidence_outside_proof = sorted(body_evidence_ids - proof_evidence_ids)
        if evidence_outside_proof:
            errors.append(f"{prefix}: body_evidence_ids not present in page plan proof_points: {', '.join(evidence_outside_proof)}")
        missing_proof_evidence = sorted(proof_evidence_ids - body_evidence_ids)
        if missing_proof_evidence:
            errors.append(f"{prefix}: body_evidence_ids must include all evidence_ids from page plan proof_points: {', '.join(missing_proof_evidence)}")

        if claim_strength == "hard_fact" and not (body_evidence_ids or _as_list(slide.get("chart_metric_ids"))):
            errors.append(f"{prefix}: hard_fact requires body_evidence_ids or chart_metric_ids")
        if claim_strength in {"hypothesis", "open_question"} and headline_allowed and slide_no != 8:
            errors.append(f"{prefix}: hypothesis/open_question cannot be a confident headline except on slide 8")
        if not body_evidence_ids and not _as_list(slide.get("chart_metric_ids")) and not _as_list(slide.get("open_questions")):
            errors.append(f"{prefix}: slide has no evidence, metrics, or open_questions")

    missing_slide_numbers = set(VALID_SLIDE_ROLES) - seen_slide_numbers
    if missing_slide_numbers:
        errors.append("missing slide_no entries: " + ", ".join(str(num) for num in sorted(missing_slide_numbers)))

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue-analysis", required=True)
    parser.add_argument("--deck-blueprint", required=True)
    parser.add_argument("--page-contract", required=True)
    parser.add_argument("--output", help="Optional path to write validation report JSON")
    args = parser.parse_args()

    pool_path = Path(args.issue_analysis)
    page_plan_path = Path(args.deck_blueprint)
    contract_path = Path(args.page_contract)
    try:
        pool = load_json_file(pool_path)
        page_plan = normalize_deck_blueprint_for_page_plan(load_json_file(page_plan_path))
        page_contract = load_json_file(contract_path)
        errors, warnings = validate(pool, page_plan, page_contract)
        errors.extend(
            assert_formal_upstream_valid(
                [pool_path, page_plan_path, contract_path],
                expected_names={"industry_issue_analysis.json", "deck_blueprint.json", "page_evidence_contract.json"},
                validation_rels=COMPILE_UPSTREAM_VALIDATIONS,
                stage_name="page_evidence_contract",
            )
        )
    except Exception as exc:
        errors, warnings = [str(exc)], []

    result = {
        "is_valid": not errors,
        "issue_analysis": str(pool_path),
        "page_plan": str(page_plan_path),
        "page_plan_kind": "deck_blueprint",
        "page_contract": str(contract_path),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
    result_json = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result_json + "\n", encoding="utf-8")
    print(result_json)
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
