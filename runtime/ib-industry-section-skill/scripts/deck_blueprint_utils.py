#!/usr/bin/env python3
"""Helpers for the LLM-first deck_blueprint artifact."""

from __future__ import annotations

import re
from typing import Any


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

VALID_CLAIM_STRENGTHS = {
    "hard_fact",
    "supported_inference",
    "directional_inference",
    "management_claim",
    "hypothesis",
    "open_question",
}

METRIC_VISUAL_CAPABILITIES = {"chart", "table", "matrix", "cards"}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def template_variants_by_slide(template_registry: dict[str, Any]) -> dict[int, dict[str, dict[str, Any]]]:
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


def analysis_index(issue_analysis: dict[str, Any]) -> dict[str, dict[str, Any]]:
    analyses = issue_analysis.get("issue_analyses") if isinstance(issue_analysis, dict) else []
    if not isinstance(analyses, list):
        return {}
    return {
        str(item.get("analysis_id")): item
        for item in analyses
        if isinstance(item, dict) and item.get("analysis_id")
    }


def analysis_metric_ids(analysis: dict[str, Any]) -> set[str]:
    values = {str(item).strip() for item in as_list(analysis.get("metric_ids")) if str(item).strip()}
    for point in as_list(analysis.get("supporting_points")):
        if isinstance(point, dict):
            values.update(str(item).strip() for item in as_list(point.get("metric_ids")) if str(item).strip())
    return values


def analysis_evidence_ids(analysis: dict[str, Any]) -> set[str]:
    values = {str(item).strip() for item in as_list(analysis.get("evidence_ids")) if str(item).strip()}
    for point in as_list(analysis.get("supporting_points")):
        if isinstance(point, dict):
            values.update(str(item).strip() for item in as_list(point.get("evidence_ids")) if str(item).strip())
    return values


def selected_issue_analysis_ids(slide: dict[str, Any]) -> list[str]:
    values = slide.get("issue_analysis_ids")
    if isinstance(values, list):
        return unique([str(item).strip() for item in values if str(item).strip()])
    primary = str(slide.get("primary_issue_analysis_id") or "").strip()
    supporting = [str(item).strip() for item in as_list(slide.get("supporting_issue_analysis_ids")) if str(item).strip()]
    return unique(([primary] if primary else []) + supporting)


def visual_plan_from_blueprint_slide(slide: dict[str, Any]) -> dict[str, Any]:
    visual = slide.get("visual_design") if isinstance(slide.get("visual_design"), dict) else {}
    selected_page_type = str(slide.get("selected_page_type") or "").strip()
    capability = str(visual.get("required_capability") or visual.get("type") or "").strip()
    capability_map = {
        "bar_chart": "chart",
        "line_chart": "chart",
        "stacked_bar": "chart",
        "bubble_chart": "chart",
        "driver_matrix": "matrix",
        "peer_table": "table",
        "comparison_table": "table",
        "fact_cards": "cards",
        "driver_cards": "cards",
    }
    capability = capability_map.get(capability, capability)
    if not capability:
        page_type_capability_map = {
            "industry_overview_dynamic_page": "chart",
            "chart_page": "chart",
            "chart_plus_mini_table_page": "chart",
            "compare_table_page": "table",
            "matrix_page": "matrix",
            "driver_card_page": "cards",
            "driver_card_5_page": "cards",
            "driver_card_6_page": "cards",
            "moat_page": "cards",
            "trend_page": "cards",
            "trend_4_card_page": "cards",
            "trend_5_card_page": "cards",
            "trend_6_card_page": "cards",
            "timeline_page": "cards",
            "summary_page": "cards",
        }
        capability = page_type_capability_map.get(selected_page_type, "")
    if not capability:
        if "chart" in selected_page_type:
            capability = "chart"
        elif "table" in selected_page_type:
            capability = "table"
        elif "matrix" in selected_page_type:
            capability = "matrix"
        elif "card" in selected_page_type or selected_page_type in {"moat_page", "trend_page"}:
            capability = "cards"
        else:
            capability = "text"
    metric_ids = [
        str(item).strip()
        for item in as_list(visual.get("visual_metric_ids") or slide.get("visual_metric_ids"))
        if str(item).strip()
    ]
    if not metric_ids:
        metric_ids = metric_ids_from_visual(slide)
    return {
        "required_capability": capability,
        "preferred_template_variant": selected_page_type,
        "visual_metric_ids": unique(metric_ids),
        "fallback_if_data_insufficient": str(
            visual.get("fallback_if_data_insufficient")
            or slide.get("evidence_gap_handling")
            or "Downgrade to a caveated text/table page if evidence is insufficient."
        ).strip(),
    }


def metric_ids_from_visual(slide: dict[str, Any]) -> list[str]:
    ids: list[str] = []

    def scan(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"metric_id", "metric_ids"}:
                    if isinstance(item, list):
                        ids.extend(str(part).strip() for part in item if str(part).strip())
                    else:
                        text = str(item or "").strip()
                        if text:
                            ids.append(text)
                else:
                    scan(item)
        elif isinstance(value, list):
            for item in value:
                scan(item)

    visual = slide.get("visual_design") if isinstance(slide.get("visual_design"), dict) else {}
    scan(visual)
    scan(slide.get("chart_data"))
    scan(slide.get("compare_table_data"))
    return unique([item for item in ids if item.startswith("MET-")])


def evidence_ids_from_visual(slide: dict[str, Any]) -> list[str]:
    ids: list[str] = []

    def scan(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"evidence_id", "evidence_ids"}:
                    if isinstance(item, list):
                        ids.extend(str(part).strip() for part in item if str(part).strip())
                    else:
                        text = str(item or "").strip()
                        if text:
                            ids.append(text)
                else:
                    scan(item)
        elif isinstance(value, list):
            for item in value:
                scan(item)

    visual = slide.get("visual_design") if isinstance(slide.get("visual_design"), dict) else {}
    scan(visual)
    scan(slide.get("chart_data"))
    scan(slide.get("compare_table_data"))
    return unique([item for item in ids if item.startswith("EV-")])


def proof_points_from_blueprint_slide(slide: dict[str, Any]) -> list[dict[str, Any]]:
    issue_ids = selected_issue_analysis_ids(slide)
    points: list[dict[str, Any]] = []
    for block in as_list(slide.get("body_blocks")):
        if not isinstance(block, dict):
            continue
        source_analysis_ids = [
            str(item).strip()
            for item in as_list(block.get("source_analysis_ids"))
            if str(item).strip()
        ] or issue_ids
        points.append(
            {
                "point": str(block.get("copy") or block.get("point") or "").strip(),
                "source_analysis_ids": unique(source_analysis_ids),
                "evidence_ids": unique([str(item).strip() for item in as_list(block.get("evidence_ids")) if str(item).strip()]),
                "metric_ids": unique([str(item).strip() for item in as_list(block.get("metric_ids")) if str(item).strip()]),
                "claim_strength": str(block.get("claim_strength") or slide.get("claim_strength") or "supported_inference").strip(),
                "visual_role": str(block.get("role") or block.get("visual_role") or "").strip(),
            }
        )
    visual_metric_ids = metric_ids_from_visual(slide)
    visual_evidence_ids = evidence_ids_from_visual(slide)
    if visual_metric_ids or visual_evidence_ids:
        points.append(
            {
                "point": str(
                    (slide.get("visual_design") if isinstance(slide.get("visual_design"), dict) else {}).get("purpose")
                    or "Primary visual evidence"
                ).strip(),
                "source_analysis_ids": issue_ids,
                "evidence_ids": visual_evidence_ids,
                "metric_ids": visual_metric_ids,
                "claim_strength": str(slide.get("claim_strength") or "supported_inference").strip(),
                "visual_role": "primary_visual",
            }
        )
    return [point for point in points if point.get("point") or point.get("evidence_ids") or point.get("metric_ids")]


def normalize_deck_blueprint_for_page_plan(deck_blueprint: dict[str, Any]) -> dict[str, Any]:
    slides = []
    for slide in deck_blueprint.get("slides") or []:
        if not isinstance(slide, dict):
            continue
        slide_no = slide.get("slide_no")
        issue_ids = selected_issue_analysis_ids(slide)
        primary = issue_ids[0] if issue_ids else ""
        supporting = issue_ids[1:]
        slides.append(
            {
                "slide_no": slide_no,
                "fixed_page_role": slide.get("fixed_page_role") or slide.get("page_role") or FIXED_PAGE_ROLES.get(int(slide_no or 0), ""),
                "investor_question": slide.get("investor_question", ""),
                "page_answer": slide.get("page_thesis") or slide.get("page_answer") or slide.get("headline") or "",
                "primary_issue_analysis_id": primary,
                "supporting_issue_analysis_ids": supporting,
                "analysis_use": [
                    {"analysis_id": analysis_id, "use_as": "selected_page_support"}
                    for analysis_id in issue_ids
                ],
                "proof_points": proof_points_from_blueprint_slide(slide),
                "visual_plan": visual_plan_from_blueprint_slide(slide),
                "claim_strength": slide.get("claim_strength", "supported_inference"),
                "caveats": slide.get("caveats", []),
                "open_questions": slide.get("open_questions", []),
                "strategy_checks": slide.get("strategy_checks", {}),
            }
        )
    return {
        "schema_version": "deck_blueprint_page_plan_v1",
        "slides": sorted(slides, key=lambda item: int(item.get("slide_no") or 0)),
    }


def normalize_text(value: Any) -> str:
    raw = str(value or "").strip().lower()
    raw = re.sub(r"^[•\-–—]+\s*", "", raw)
    raw = re.sub(r"[\s\W_]+", "", raw, flags=re.UNICODE)
    return raw
