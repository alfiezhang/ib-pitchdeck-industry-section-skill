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


def selected_page_argument_ids(slide: dict[str, Any]) -> list[str]:
    values = slide.get("page_argument_ids")
    if isinstance(values, list):
        return unique([str(item).strip() for item in values if str(item).strip()])
    primary = str(slide.get("page_argument_id") or "").strip()
    supporting = [str(item).strip() for item in as_list(slide.get("supporting_page_argument_ids")) if str(item).strip()]
    return unique(([primary] if primary else []) + supporting)


def page_argument_index(page_argument_pack: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = page_argument_pack.get("page_arguments") if isinstance(page_argument_pack, dict) else []
    if not isinstance(rows, list):
        return {}
    return {
        str(item.get("page_argument_id")): item
        for item in rows
        if isinstance(item, dict) and item.get("page_argument_id")
    }


def _permission_from_page_argument(argument: dict[str, Any]) -> dict[str, bool]:
    explicit = argument.get("downstream_permission")
    if isinstance(explicit, dict):
        return {
            "headline_allowed": explicit.get("headline_allowed") is True,
            "main_message_allowed": explicit.get("main_message_allowed") is True or explicit.get("headline_allowed") is True,
            "chart_allowed": explicit.get("chart_allowed") is True,
            "body_copy_allowed": explicit.get("body_copy_allowed") is True,
        }
    usage = str(argument.get("allowed_deck_usage") or "").strip()
    headline_allowed = usage == "headline_allowed"
    body_copy_allowed = usage in {"headline_allowed", "body_only", "supporting_context", "context_only", "caveat_only"}
    chart_allowed = usage in {"headline_allowed", "body_only"}
    return {
        "headline_allowed": headline_allowed,
        "main_message_allowed": headline_allowed,
        "chart_allowed": chart_allowed,
        "body_copy_allowed": body_copy_allowed,
    }


def _evidence_status_from_page_argument(argument: dict[str, Any]) -> str:
    status = str(argument.get("evidence_status") or "").strip()
    if status in {"supported", "thin", "insufficient", "not_applicable", "unavailable_after_research", "not_researched", "caveat_only"}:
        return status
    usage = str(argument.get("allowed_deck_usage") or "").strip()
    if usage == "headline_allowed":
        return "supported"
    if usage in {"caveat_only", "diligence_only"}:
        return "caveat_only"
    if usage in {"not_allowed", "research_required"}:
        return "not_researched"
    return "thin"


EVIDENCE_STATUS_RANK = {
    "supported": 0,
    "thin": 1,
    "caveat_only": 2,
    "insufficient": 3,
    "unavailable_after_research": 4,
    "not_researched": 5,
}


def _weaker_evidence_status(left: str, right: str) -> str:
    if left == "not_applicable":
        return right
    if right == "not_applicable":
        return left
    return max([left, right], key=lambda item: EVIDENCE_STATUS_RANK.get(item, -1))


def page_argument_pool_from_pack(page_argument_pack: dict[str, Any], page_argument_ids: list[str] | None = None) -> dict[str, Any]:
    """Convert page_argument_pack into the internal issue-analysis-like pool.

    Generation is sourced from page arguments. The renderer contract still uses
    lineage-compatible internal rows, so this mapping preserves
    source_issue_analysis_id lineage while keeping page_argument_pack as the
    upstream authority. When page_argument_ids is provided, only those selected
    page arguments are allowed into the pool.
    """
    by_issue: dict[str, dict[str, Any]] = {}
    restrict_to_selected = page_argument_ids is not None
    selected_ids = set(page_argument_ids or [])
    for argument in page_argument_index(page_argument_pack).values():
        argument_id = str(argument.get("page_argument_id") or "").strip()
        if restrict_to_selected and argument_id not in selected_ids:
            continue
        source_id = str(argument.get("source_issue_analysis_id") or "").strip()
        if not source_id:
            continue
        row = by_issue.setdefault(
            source_id,
            {
                "analysis_id": source_id,
                "page_argument_ids": [],
                "issue_area": str(argument.get("issue_area") or "").strip(),
                "subissue": str(argument.get("subissue") or "").strip(),
                "analysis_text": "",
                "core_statement": "",
                "evidence_status": _evidence_status_from_page_argument(argument),
                "evidence_sufficiency": _evidence_status_from_page_argument(argument),
                "evidence_ids": [],
                "metric_ids": [],
                "supporting_points": [],
                "downstream_permission": {
                    "headline_allowed": False,
                    "main_message_allowed": False,
                    "chart_allowed": False,
                    "body_copy_allowed": False,
                },
            },
        )
        row["page_argument_ids"].append(argument_id)
        row["evidence_status"] = _weaker_evidence_status(
            str(row.get("evidence_status") or "insufficient"),
            _evidence_status_from_page_argument(argument),
        )
        row["evidence_sufficiency"] = row["evidence_status"]
        statement = str(argument.get("page_argument") or "").strip()
        if statement and not row.get("core_statement"):
            row["core_statement"] = statement
        if statement:
            row["analysis_text"] = (str(row.get("analysis_text") or "") + "\n" + statement).strip()
        evidence_ids = unique([*as_list(row.get("evidence_ids")), *as_list(argument.get("evidence_ids"))])
        metric_ids = unique([*as_list(row.get("metric_ids")), *as_list(argument.get("metric_ids"))])
        row["evidence_ids"] = evidence_ids
        row["metric_ids"] = metric_ids
        point = {
            "point": statement or str(argument.get("client_question") or "").strip() or str(argument.get("page_argument_id") or "").strip(),
            "evidence_ids": unique([str(item).strip() for item in as_list(argument.get("evidence_ids")) if str(item).strip()]),
            "metric_ids": unique([str(item).strip() for item in as_list(argument.get("metric_ids")) if str(item).strip()]),
            "role": "page_argument_support",
            "evidence_sufficiency": _evidence_status_from_page_argument(argument),
        }
        row["supporting_points"].append(point)
        perm = _permission_from_page_argument(argument)
        for key, value in perm.items():
            if value is True:
                row["downstream_permission"][key] = True
        allowed_usage = {
            "headline": row["downstream_permission"]["headline_allowed"],
            "main_message": row["downstream_permission"]["main_message_allowed"],
            "chart": row["downstream_permission"]["chart_allowed"],
            "body_copy": row["downstream_permission"]["body_copy_allowed"],
        }
        row["allowed_deck_usage"] = allowed_usage
    return {"issue_analyses": list(by_issue.values())}


def visual_plan_from_blueprint_slide(slide: dict[str, Any]) -> dict[str, Any]:
    visual = slide.get("visual_design") if isinstance(slide.get("visual_design"), dict) else {}
    if not visual and isinstance(slide.get("visual_plan"), dict):
        visual = slide["visual_plan"]
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

    visual_design = slide.get("visual_design") if isinstance(slide.get("visual_design"), dict) else {}
    visual_plan = slide.get("visual_plan") if isinstance(slide.get("visual_plan"), dict) else {}
    scan(visual_design)
    scan(visual_plan)
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

    visual_design = slide.get("visual_design") if isinstance(slide.get("visual_design"), dict) else {}
    visual_plan = slide.get("visual_plan") if isinstance(slide.get("visual_plan"), dict) else {}
    scan(visual_design)
    scan(visual_plan)
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
                "claim_strength": str(block.get("claim_strength") or slide.get("claim_strength") or "").strip(),
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
                    or (slide.get("visual_plan") if isinstance(slide.get("visual_plan"), dict) else {}).get("purpose")
                    or "Primary visual evidence"
                ).strip(),
                "source_analysis_ids": issue_ids,
                "evidence_ids": visual_evidence_ids,
                "metric_ids": visual_metric_ids,
                "claim_strength": str(slide.get("claim_strength") or "").strip(),
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
        page_argument_ids = selected_page_argument_ids(slide)
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
                "page_argument_ids": page_argument_ids,
                "analysis_use": [
                    {"analysis_id": analysis_id, "use_as": "selected_page_support"}
                    for analysis_id in issue_ids
                ],
                "proof_points": proof_points_from_blueprint_slide(slide),
                "visual_plan": visual_plan_from_blueprint_slide(slide),
                "claim_strength": slide.get("claim_strength", ""),
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
