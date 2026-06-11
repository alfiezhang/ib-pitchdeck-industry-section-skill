#!/usr/bin/env python3
"""Validate industry_issue_analysis.json before deck blueprint.

The issue analysis artifact is intentionally not a short "insight list". Each
analysis block covers one IB industry subissue with a substantive paragraph,
supporting points, evidence sufficiency, and downstream permissions.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from issue_taxonomy import ISSUE_TOPICS_BY_AREA, VALID_ISSUE_AREAS, VALID_SUBISSUES
from json_utils import load_json_file
from upstream_validation import ISSUE_ANALYSIS_UPSTREAM_VALIDATIONS, assert_formal_upstream_valid


ANALYSIS_ID_RE = re.compile(r"^IA-\d{3}$")
VALID_CONFIDENCE_STATUS = {"validated", "partially_validated", "unverified", "rejected"}
VALID_ANALYSIS_TYPES = {
    "descriptive_market_fact",
    "analytical_judgment",
    "driver_analysis",
    "structure_analysis",
    "profit_pool_analysis",
    "barrier_analysis",
    "peer_profile",
    "competitive_dynamic",
    "trend_or_risk",
    "pitch_context",
    "evidence_gap",
}
VALID_EVIDENCE_STATUS = {
    "supported",
    "thin",
    "insufficient",
    "not_applicable",
    "unavailable_after_research",
    "not_researched",
    "caveat_only",
}
VALID_HYPOTHESIS_RESOLUTION = {"resolved", "not_researched", "caveat_only", "deprioritized", "rejected"}
VALID_EVIDENCE_SUFFICIENCY = {
    "sufficient",
    "thin",
    "insufficient",
    "not_applicable",
    "unavailable_after_research",
}
VALID_POINT_ROLES = {
    "primary_fact",
    "secondary_fact",
    "calculation",
    "counterpoint",
    "caveat",
    "peer_fact",
    "open_gap",
}
VALID_BACKLOG_PERMISSIONS = {
    "do_not_use_for_strong_claim",
    "use_only_as_context",
    "supplemental_research_required",
}
VALID_RESEARCH_ACTIONS = {
    "run_targeted_search",
    "review_company_filings",
    "review_peer_data",
    "request_user_or_management_input",
    "mark_unavailable_after_research",
}
PLACEHOLDER_MARKERS = (
    "TODO",
    "TODO_REPLACE",
    "LLM must",
    "LLM MUST",
    "replace with",
    "mechanical placeholder",
    "skeleton",
    "占位",
)
PAGE_SPECIFIC_FIELDS = {
    "recommended_slide_roles",
    "slide_no",
    "fixed_page_role",
    "page_role",
    "page_question",
    "page_answer",
    "intended_headline_claim",
    "headline_claim",
    "chart_metric_ids",
    "body_evidence_ids",
    "selected_insight_ids",
    "selected_analysis_ids",
    "primary_insight_id",
    "primary_issue_analysis_id",
    "supporting_issue_analysis_ids",
}

def _non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _load_id_sets(memo_path: Path | None) -> tuple[set[str], set[str]]:
    if not memo_path:
        return set(), set()
    try:
        text = memo_path.read_text(encoding="utf-8")
    except OSError:
        return set(), set()
    return set(re.findall(r"\bEV-\d{3}\b", text)), set(re.findall(r"\bMET-\d{3}\b", text))


def _markdown_table_rows(section: str) -> list[dict[str, str]]:
    header: list[str] = []
    rows: list[dict[str, str]] = []
    for line in section.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if not cells:
            continue
        if not header:
            header = cells
            continue
        if all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        row: dict[str, str] = {}
        for idx, cell in enumerate(cells):
            key = header[idx] if idx < len(header) else f"col_{idx}"
            row[key] = cell
        rows.append(row)
    return rows


def _section_text(text: str, heading: str) -> str:
    match = re.search(rf"^##\s+{re.escape(heading)}\b.*$", text, flags=re.MULTILINE | re.IGNORECASE)
    if not match:
        return ""
    next_match = re.search(r"^##\s+", text[match.end():], flags=re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(text)
    return text[match.end():end]


def _load_fact_inventory(memo_path: Path | None) -> dict[tuple[str, str], dict[str, Any]]:
    if not memo_path:
        return {}
    try:
        text = memo_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    section = _section_text(text, "IB Issue Fact Inventory")
    if not section:
        return {}
    inventory: dict[tuple[str, str], dict[str, Any]] = {}
    for row in _markdown_table_rows(section):
        area = (row.get("Issue Area") or row.get("Area") or "").strip()
        subissue = (
            row.get("Subissue")
            or row.get("Issue Topic")
            or row.get("Topic")
            or ""
        ).strip()
        if not area or not subissue:
            continue
        inventory[(area, subissue)] = {
            "status": (row.get("Fact Status") or row.get("Status") or "").strip(),
            "evidence_ids": re.findall(r"\bEV-\d{3}\b", row.get("Evidence IDs", "")),
            "metric_ids": re.findall(r"\bMET-\d{3}\b", row.get("Metric IDs", "")),
            "notes": (row.get("Notes") or "").strip(),
        }
    return inventory


def _supporting_point_ids(analysis: dict[str, Any], key: str) -> list[str]:
    values: list[str] = []
    prefix = "EV" if key == "evidence_ids" else "MET"
    pattern = re.compile(rf"\b{prefix}-\d{{3}}\b")
    for point in _as_list(analysis.get("supporting_points")):
        if not isinstance(point, dict):
            continue
        for item in _as_list(point.get(key)):
            for match in pattern.findall(str(item)):
                if match not in values:
                    values.append(match)
    return values


def _contains_placeholder(value: Any) -> bool:
    text = str(value or "")
    return any(marker in text for marker in PLACEHOLDER_MARKERS)


def _analysis_ids_by_subissue(analyses: list[dict[str, Any]]) -> set[tuple[str, str]]:
    covered: set[tuple[str, str]] = set()
    for analysis in analyses:
        if not isinstance(analysis, dict):
            continue
        area = str(analysis.get("issue_area") or "").strip()
        subissue = str(analysis.get("subissue") or "").strip()
        if area and subissue:
            covered.add((area, subissue))
    return covered


def _backlog_subissues(backlog: list[Any]) -> set[tuple[str, str]]:
    covered: set[tuple[str, str]] = set()
    for item in backlog:
        if not isinstance(item, dict):
            continue
        area = str(item.get("issue_area") or "").strip()
        subissue = str(item.get("subissue") or "").strip()
        if area and subissue:
            covered.add((area, subissue))
    return covered


def validate(pool: dict[str, Any], memo_path: Path | None = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    meta = pool.get("meta")
    if not isinstance(meta, dict):
        errors.append("meta must be an object")
    else:
        for field in ("target_company", "industry", "geography", "research_as_of_date"):
            if not _non_empty_text(meta.get(field)):
                errors.append(f"meta.{field} is required")

    analyses = pool.get("issue_analyses")
    if not isinstance(analyses, list) or not analyses:
        errors.append("issue_analyses must be a non-empty array")
        analyses = []

    backlog = pool.get("research_backlog")
    if not isinstance(backlog, list):
        errors.append("research_backlog must be an array")
        backlog = []
    evidence_readiness = pool.get("evidence_readiness")
    if evidence_readiness is not None and not isinstance(evidence_readiness, dict):
        errors.append("evidence_readiness must be an object")
    elif isinstance(evidence_readiness, dict):
        if not isinstance(evidence_readiness.get("enough_for_client_pitch"), bool):
            warnings.append("evidence_readiness.enough_for_client_pitch should be boolean")
        if not isinstance(evidence_readiness.get("evidence_limited_pitch_outline"), bool):
            warnings.append("evidence_readiness.evidence_limited_pitch_outline should be boolean")
        if not isinstance(evidence_readiness.get("research_first_required"), bool):
            warnings.append("evidence_readiness.research_first_required should be boolean")
        for field in ("critical_gap_count", "evidence_row_count", "metric_row_count"):
            if not isinstance(evidence_readiness.get(field), int):
                try:
                    int(evidence_readiness.get(field) or 0)
                except Exception:
                    warnings.append(f"evidence_readiness.{field} should be an integer")
        if evidence_readiness.get("research_pack_exists") is False:
            warnings.append("research_pack_exists is false; deck should be an evidence-limited outline until research pack is complete.")
        if evidence_readiness.get("evidence_limited_pitch_outline") is True:
            warnings.append("evidence_limited_pitch_outline is true; recommend issue-analysis depth guard before full deck claims.")

    memo_ev_ids, memo_met_ids = _load_id_sets(memo_path)
    fact_inventory = _load_fact_inventory(memo_path)
    seen_ids: set[str] = set()

    for idx, analysis in enumerate(analyses, start=1):
        if not isinstance(analysis, dict):
            errors.append(f"issue_analyses[{idx}] must be an object")
            continue

        analysis_id = str(analysis.get("analysis_id") or "").strip()
        prefix = analysis_id or f"issue_analyses[{idx}]"
        for field in sorted(PAGE_SPECIFIC_FIELDS):
            if field in analysis:
                errors.append(
                    f"{prefix}: page-specific field '{field}' does not belong in issue analysis; "
                    "move page selection, headline, chart, and evidence-contract decisions to deck_blueprint/compiled page_evidence_contract"
                )
        if not analysis_id:
            errors.append(f"{prefix}: analysis_id is required")
        elif not ANALYSIS_ID_RE.match(analysis_id):
            errors.append(f"{prefix}: analysis_id must follow IA-001 format")
        elif analysis_id in seen_ids:
            errors.append(f"{prefix}: duplicate analysis_id")
        else:
            seen_ids.add(analysis_id)

        for field in ("core_statement", "analysis_text", "analysis_type", "issue_area", "subissue", "status", "evidence_sufficiency"):
            if not _non_empty_text(analysis.get(field)):
                errors.append(f"{prefix}: {field} is required")
        for field in ("core_statement", "analysis_text"):
            if _contains_placeholder(analysis.get(field)):
                errors.append(
                    f"{prefix}: {field} still contains skeleton placeholder text; replace it with substantive issue analysis from the research pack"
                )

        source_execution_result_ids = [
            str(item).strip()
            for item in _as_list(analysis.get("source_execution_result_ids"))
            if str(item).strip()
        ]
        if not source_execution_result_ids:
            errors.append(f"{prefix}: source_execution_result_ids must have at least 1 FR-ID")
        for source_execution_result_id in source_execution_result_ids:
            if not re.match(r"^FR-\d{3}$", source_execution_result_id):
                errors.append(f"{prefix}: invalid source_execution_result_ids value '{source_execution_result_id}'")

        issue_area = str(analysis.get("issue_area") or "").strip()
        subissue = str(analysis.get("subissue") or "").strip()
        if issue_area and issue_area not in VALID_ISSUE_AREAS:
            errors.append(f"{prefix}: invalid issue_area '{issue_area}'")
        if subissue and subissue not in VALID_SUBISSUES:
            errors.append(f"{prefix}: invalid subissue '{subissue}'")
        elif issue_area and subissue and subissue not in ISSUE_TOPICS_BY_AREA.get(issue_area, set()):
            errors.append(f"{prefix}: subissue '{subissue}' does not belong to issue_area '{issue_area}'")

        if fact_inventory and issue_area and subissue:
            inventory = fact_inventory.get((issue_area, subissue))
            if not inventory:
                errors.append(f"{prefix}: subissue {issue_area}/{subissue} is missing from research pack IB Issue Fact Inventory")
            elif str(inventory.get("status") or "").strip() == "insufficient":
                errors.append(
                    f"{prefix}: subissue {issue_area}/{subissue} is insufficient in research pack; put it in research_backlog instead of issue_analyses"
                )

        analysis_type = str(analysis.get("analysis_type") or "").strip()
        if analysis_type and analysis_type not in VALID_ANALYSIS_TYPES:
            errors.append(f"{prefix}: invalid analysis_type '{analysis_type}'")

        evidence_status = str(analysis.get("evidence_status") or "").strip()
        if evidence_status and evidence_status not in VALID_EVIDENCE_STATUS:
            errors.append(f"{prefix}: evidence_status must be one of {sorted(VALID_EVIDENCE_STATUS)}")
        hypothesis_resolution = str(analysis.get("hypothesis_resolution") or "").strip()
        if hypothesis_resolution and hypothesis_resolution not in VALID_HYPOTHESIS_RESOLUTION:
            errors.append(f"{prefix}: hypothesis_resolution must be one of {sorted(VALID_HYPOTHESIS_RESOLUTION)}")

        status = str(analysis.get("status") or "").strip()
        if status and status not in VALID_CONFIDENCE_STATUS:
            errors.append(f"{prefix}: status must be one of {sorted(VALID_CONFIDENCE_STATUS)}")
        if status == "rejected":
            errors.append(f"{prefix}: rejected analyses belong in rejected_or_deprioritized_analyses, not issue_analyses")
        if hypothesis_resolution == "rejected" and status != "rejected":
            errors.append(f"{prefix}: hypothesis_resolution=rejected requires status=rejected")
        if hypothesis_resolution == "not_researched" and evidence_status != "not_researched":
            errors.append(f"{prefix}: hypothesis_resolution=not_researched requires evidence_status=not_researched")
        if hypothesis_resolution == "caveat_only" and evidence_status != "caveat_only":
            errors.append(f"{prefix}: hypothesis_resolution=caveat_only requires evidence_status=caveat_only")

        sufficiency = str(analysis.get("evidence_sufficiency") or "").strip()
        if sufficiency and sufficiency not in VALID_EVIDENCE_SUFFICIENCY:
            errors.append(f"{prefix}: evidence_sufficiency must be one of {sorted(VALID_EVIDENCE_SUFFICIENCY)}")

        evidence_ids = [str(item).strip() for item in _as_list(analysis.get("evidence_ids")) if str(item).strip()]
        metric_ids = [str(item).strip() for item in _as_list(analysis.get("metric_ids")) if str(item).strip()]
        limitations = [str(item).strip() for item in _as_list(analysis.get("limitations")) if str(item).strip()]
        supporting_points = _as_list(analysis.get("supporting_points"))
        if not supporting_points:
            errors.append(f"{prefix}: supporting_points must have at least 1 point; do not use issue analysis as a one-sentence idea list")

        analysis_text = " ".join(str(analysis.get("analysis_text") or "").split())
        if sufficiency in {"sufficient", "thin"} and len(analysis_text) < 120:
            errors.append(
                f"{prefix}: analysis_text is too short for a substantive issue analysis; "
                "write a paragraph that explains evidence, mechanism, and caveat"
            )

        point_evidence_ids = _supporting_point_ids(analysis, "evidence_ids")
        point_metric_ids = _supporting_point_ids(analysis, "metric_ids")
        for point_idx, point in enumerate(supporting_points, start=1):
            point_prefix = f"{prefix}: supporting_points[{point_idx}]"
            if not isinstance(point, dict):
                errors.append(f"{point_prefix} must be an object")
                continue
            if not _non_empty_text(point.get("point")):
                errors.append(f"{point_prefix}.point is required")
            elif _contains_placeholder(point.get("point")):
                errors.append(f"{point_prefix}.point still contains skeleton placeholder text")
            role = str(point.get("role") or "").strip()
            if role not in VALID_POINT_ROLES:
                errors.append(f"{point_prefix}.role must be one of {sorted(VALID_POINT_ROLES)}")
            point_sufficiency = str(point.get("evidence_sufficiency") or "").strip()
            if point_sufficiency not in VALID_EVIDENCE_SUFFICIENCY:
                errors.append(f"{point_prefix}.evidence_sufficiency must be one of {sorted(VALID_EVIDENCE_SUFFICIENCY)}")
            point_evs = [str(item).strip() for item in _as_list(point.get("evidence_ids")) if str(item).strip()]
            point_mets = [str(item).strip() for item in _as_list(point.get("metric_ids")) if str(item).strip()]
            if role not in {"open_gap", "caveat"} and not (point_evs or point_mets):
                errors.append(f"{point_prefix} must cite evidence_ids or metric_ids unless it is open_gap/caveat")

        missing_from_top_evidence = sorted(set(point_evidence_ids) - set(evidence_ids))
        if missing_from_top_evidence:
            errors.append(
                f"{prefix}: evidence_ids must include all supporting_points evidence IDs: {', '.join(missing_from_top_evidence)}"
            )
        missing_from_top_metric = sorted(set(point_metric_ids) - set(metric_ids))
        if missing_from_top_metric:
            errors.append(
                f"{prefix}: metric_ids must include all supporting_points metric IDs: {', '.join(missing_from_top_metric)}"
            )

        if sufficiency == "sufficient" and not (evidence_ids or metric_ids):
            errors.append(f"{prefix}: sufficient issue analysis must have evidence_ids or metric_ids")
        if sufficiency == "thin" and not (evidence_ids or metric_ids or limitations):
            errors.append(f"{prefix}: thin issue analysis needs evidence, metrics, or limitations")
        if sufficiency in {"insufficient", "unavailable_after_research"} and status == "validated":
            errors.append(f"{prefix}: insufficient/unavailable analysis cannot be status=validated")

        downstream = analysis.get("downstream_permission")
        if not isinstance(downstream, dict):
            errors.append(f"{prefix}: downstream_permission is required")
            downstream = {}
        for field in ("headline_allowed", "chart_allowed", "body_copy_allowed"):
            if not isinstance(downstream.get(field), bool):
                errors.append(f"{prefix}: downstream_permission.{field} must be boolean")
        allowed_deck_usage = analysis.get("allowed_deck_usage")
        if not isinstance(allowed_deck_usage, dict):
            errors.append(f"{prefix}: allowed_deck_usage is required")
            allowed_deck_usage = {}
        for field in ("headline", "main_message", "chart", "body_copy"):
            if not isinstance(allowed_deck_usage.get(field), bool):
                errors.append(f"{prefix}: allowed_deck_usage.{field} must be boolean")
        if downstream.get("headline_allowed") and sufficiency not in {"sufficient", "thin"}:
            errors.append(f"{prefix}: headline_allowed requires sufficient or thin evidence_sufficiency")
        if downstream.get("headline_allowed"):
            point_sufficiencies = {
                str(point.get("evidence_sufficiency") or "").strip()
                for point in supporting_points
                if isinstance(point, dict)
            }
            if "sufficient" not in point_sufficiencies:
                errors.append(f"{prefix}: headline_allowed requires at least one sufficient supporting_point")
        if downstream.get("chart_allowed") and not metric_ids:
            errors.append(f"{prefix}: chart_allowed requires non-empty metric_ids")
        if sufficiency in {"insufficient", "unavailable_after_research"} and (
            downstream.get("headline_allowed") or downstream.get("chart_allowed")
        ):
            errors.append(f"{prefix}: insufficient/unavailable analysis cannot allow headlines or charts")
        if evidence_status in {"not_researched", "caveat_only"}:
            if downstream.get("headline_allowed"):
                errors.append(f"{prefix}: evidence_status={evidence_status} cannot allow headline_allowed")
            if downstream.get("body_copy_allowed"):
                errors.append(f"{prefix}: evidence_status={evidence_status} cannot allow body_copy_allowed")
            if allowed_deck_usage.get("headline"):
                errors.append(f"{prefix}: evidence_status={evidence_status} cannot allow allowed_deck_usage.headline")
            if allowed_deck_usage.get("main_message"):
                errors.append(f"{prefix}: evidence_status={evidence_status} cannot allow allowed_deck_usage.main_message")

        if memo_ev_ids:
            missing = sorted(set(evidence_ids) - memo_ev_ids)
            if missing:
                warnings.append(f"{prefix}: evidence_ids not found in research pack: {', '.join(missing)}")
        if memo_met_ids:
            missing = sorted(set(metric_ids) - memo_met_ids)
            if missing:
                warnings.append(f"{prefix}: metric_ids not found in research pack: {', '.join(missing)}")

    for idx, item in enumerate(backlog, start=1):
        prefix = f"research_backlog[{idx}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        issue_area = str(item.get("issue_area") or "").strip()
        subissue = str(item.get("subissue") or "").strip()
        if issue_area not in VALID_ISSUE_AREAS:
            errors.append(f"{prefix}: invalid issue_area '{issue_area}'")
        if subissue not in VALID_SUBISSUES:
            errors.append(f"{prefix}: invalid subissue '{subissue}'")
        elif issue_area and subissue not in ISSUE_TOPICS_BY_AREA.get(issue_area, set()):
            errors.append(f"{prefix}: subissue '{subissue}' does not belong to issue_area '{issue_area}'")
        for field in ("reason", "downstream_permission", "research_action"):
            if not _non_empty_text(item.get(field)):
                errors.append(f"{prefix}: {field} is required")
        permission = str(item.get("downstream_permission") or "").strip()
        if permission and permission not in VALID_BACKLOG_PERMISSIONS:
            errors.append(f"{prefix}: downstream_permission must be one of {sorted(VALID_BACKLOG_PERMISSIONS)}")
        research_action = str(item.get("research_action") or "").strip()
        if research_action and research_action not in VALID_RESEARCH_ACTIONS:
            errors.append(f"{prefix}: research_action must be one of {sorted(VALID_RESEARCH_ACTIONS)}")
        needed = [str(value).strip() for value in _as_list(item.get("needed_evidence")) if str(value).strip()]
        if not needed:
            errors.append(f"{prefix}: needed_evidence must have at least 1 item")
        if permission == "supplemental_research_required":
            errors.append(
                f"{prefix}: supplemental_research_required blocks deck blueprint; run the requested research and update the research pack before proceeding"
            )

    covered = _analysis_ids_by_subissue(analyses) | _backlog_subissues(backlog)
    for area, subissues in sorted(ISSUE_TOPICS_BY_AREA.items()):
        missing = sorted((area, subissue) for subissue in subissues if (area, subissue) not in covered)
        for missing_area, missing_subissue in missing:
            errors.append(
                f"missing issue coverage for {missing_area}/{missing_subissue}; add issue_analyses or research_backlog"
            )

    rejected = pool.get("rejected_or_deprioritized_analyses")
    if not isinstance(rejected, list):
        errors.append("rejected_or_deprioritized_analyses must be an array")

    return errors, warnings


def _repair_class(error: str) -> str:
    if "issue_analyses must be a non-empty array" in error:
        return "missing_issue_analysis"
    if "status must be one of" in error or "analysis_type must be one of" in error or "evidence_sufficiency must be one of" in error:
        return "mechanical_alias_or_enum"
    if "analysis_text is too short" in error:
        return "thin_analysis_text"
    if "supporting_points" in error and "must cite evidence_ids or metric_ids" in error:
        return "uncited_supporting_point"
    if "skeleton placeholder" in error:
        return "skeleton_placeholder"
    if "chart_allowed requires" in error:
        return "invalid_downstream_permission"
    if error.startswith("missing issue coverage"):
        return "missing_issue_coverage"
    if "research_backlog" in error:
        return "backlog_shape"
    if "missing from research pack IB Issue Fact Inventory" in error:
        return "research_pack_inventory_mismatch"
    if "page-specific field" in error:
        return "page_logic_in_issue_analysis"
    return "other"


REPAIR_PROFILES: dict[str, dict[str, Any]] = {
    "missing_issue_analysis": {
        "repair_target": "industry_issue_analysis.json",
        "repair_hint": "Rebuild issue_analyses from the research pack IB Issue Fact Inventory and formal_research_execution_report. Do not proceed to deck_blueprint with an empty analysis array.",
        "repair_fields": ["issue_analyses", "research_backlog"],
    },
    "mechanical_alias_or_enum": {
        "repair_target": "industry_issue_analysis.json",
        "repair_hint": "Run scripts/normalize_issue_analysis.py first, then revalidate. This handles common aliases such as sufficient/thin statuses and renamed fields.",
        "repair_fields": ["issue_analyses[].status", "issue_analyses[].analysis_type", "issue_analyses[].evidence_sufficiency"],
        "helper": "scripts/normalize_issue_analysis.py",
    },
    "thin_analysis_text": {
        "repair_target": "industry_issue_analysis.json",
        "repair_hint": "Expand each analysis_text into a substantive issue paragraph using the research pack: evidence, mechanism, limitation, and why it matters for the pitch. Do not shorten to pass PPT copy limits.",
        "repair_fields": ["issue_analyses[].analysis_text", "issue_analyses[].core_statement", "issue_analyses[].limitations"],
    },
    "skeleton_placeholder": {
        "repair_target": "industry_issue_analysis.json",
        "repair_hint": "A helper generated issue-analysis structure, but the LLM has not written the banker analysis yet. Replace TODO/skeleton text with core_statement, analysis_text, and supporting point language grounded in the research evidence pack.",
        "repair_fields": ["issue_analyses[].core_statement", "issue_analyses[].analysis_text", "issue_analyses[].supporting_points[].point"],
    },
    "uncited_supporting_point": {
        "repair_target": "industry_issue_analysis.json",
        "repair_hint": "Attach existing EV/MET IDs from the research pack to factual supporting points. If no evidence exists, change the point role to caveat/open_gap or move it to research_backlog.",
        "repair_fields": ["issue_analyses[].supporting_points[]"],
    },
    "invalid_downstream_permission": {
        "repair_target": "industry_issue_analysis.json",
        "repair_hint": "If an analysis lacks chart-ready MET IDs or sufficient evidence, set chart_allowed/headline_allowed false. Only add MET IDs when they already exist in Metric Reconciliation.",
        "repair_fields": ["issue_analyses[].downstream_permission", "issue_analyses[].metric_ids"],
    },
    "backlog_shape": {
        "repair_target": "industry_issue_analysis.json",
        "repair_hint": "Complete each research_backlog item with reason, needed_evidence, research_action, and downstream_permission. Backlog is a valid way to cover unsupported subissues.",
        "repair_fields": ["research_backlog[]"],
    },
    "missing_issue_coverage": {
        "repair_target": "industry_issue_analysis.json",
        "repair_hint": "For each missing issue/subissue, either add a supported issue analysis or add a research_backlog item explaining why evidence is insufficient. Do not invent a confident analysis just to cover taxonomy.",
        "repair_fields": ["issue_analyses[]", "research_backlog[]"],
    },
    "research_pack_inventory_mismatch": {
        "repair_target": "industry_research_pack.md",
        "repair_hint": "Align issue_area/subissue with the IB Issue Fact Inventory, or update the research pack inventory if the analysis is genuinely supported by formal evidence.",
        "repair_fields": ["IB Issue Fact Inventory", "issue_analyses[].issue_area", "issue_analyses[].subissue"],
    },
    "page_logic_in_issue_analysis": {
        "repair_target": "industry_issue_analysis.json",
        "repair_hint": "Move slide numbers, page roles, headline claims, chart fields, and page evidence decisions to deck_blueprint/compiled artifacts. Issue analysis only owns research judgment and downstream permissions.",
        "repair_fields": ["issue_analyses[]"],
    },
    "other": {
        "repair_target": "industry_issue_analysis.json",
        "repair_hint": "Read the validator error literally, repair the upstream research judgment artifact, then rerun validate_issue_analysis.py.",
        "repair_fields": ["issue_analyses", "research_backlog"],
    },
}


def build_repair_plan(errors: list[str]) -> dict[str, Any]:
    if not errors:
        return {
            "status": "no_issue_analysis_repairs_required",
            "primary_repair_targets": [],
            "targets": [],
            "rerun_steps": [],
        }
    grouped: dict[str, list[str]] = {}
    for error in errors:
        grouped.setdefault(_repair_class(str(error)), []).append(str(error))
    ordered_keys = [
        "missing_issue_analysis",
        "mechanical_alias_or_enum",
        "thin_analysis_text",
        "skeleton_placeholder",
        "uncited_supporting_point",
        "invalid_downstream_permission",
        "backlog_shape",
        "missing_issue_coverage",
        "research_pack_inventory_mismatch",
        "page_logic_in_issue_analysis",
        "other",
    ]
    targets: list[dict[str, Any]] = []
    primary_targets: list[str] = []
    for key in ordered_keys:
        issues = grouped.get(key)
        if not issues:
            continue
        profile = REPAIR_PROFILES[key]
        target = str(profile["repair_target"])
        if target not in primary_targets:
            primary_targets.append(target)
        entry = {
            "issue_class": key,
            "count": len(issues),
            "sample_errors": issues[:6],
            "repair_target": target,
            "repair_fields": profile["repair_fields"],
            "repair_hint": profile["repair_hint"],
        }
        if profile.get("helper"):
            entry["helper"] = profile["helper"]
        targets.append(entry)
    return {
        "status": "repair_required",
        "instruction": (
            "Do not proceed to deck_blueprint or PPT while issue_analysis is invalid. "
            "Repair the listed upstream artifacts in the same RUN_DIR, rerun validate_issue_analysis.py, "
            "then run workflow.py next before moving downstream."
        ),
        "primary_repair_targets": primary_targets,
        "targets": targets,
        "rerun_steps": [
            "scripts/normalize_issue_analysis.py if mechanical_alias_or_enum appears",
            "scripts/validate_issue_analysis.py",
            "scripts/workflow.py next --run-dir $RUN_DIR",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("issue_analysis_positional", nargs="?", help="Path to industry_issue_analysis.json")
    parser.add_argument("--issue-analysis", dest="issue_analysis_flag", help="Path to industry_issue_analysis.json")
    parser.add_argument("--research-pack", dest="research_pack", help="Optional industry_research_pack.md for EV/MET reference warnings")
    parser.add_argument("--output", help="Optional path to write validation report JSON")
    args = parser.parse_args()

    issue_analysis_path = Path(args.issue_analysis_flag or args.issue_analysis_positional or "")
    if not str(issue_analysis_path):
        parser.error("provide an issue analysis path")

    try:
        pool = load_json_file(issue_analysis_path)
        errors, warnings = validate(pool, Path(args.research_pack) if args.research_pack else None)
        upstream_errors = assert_formal_upstream_valid(
            [issue_analysis_path, Path(args.research_pack) if args.research_pack else issue_analysis_path],
            expected_names={"industry_issue_analysis.json", "industry_research_pack.md"},
            validation_rels=ISSUE_ANALYSIS_UPSTREAM_VALIDATIONS,
            stage_name="issue_analysis",
        )
        errors.extend(upstream_errors)
    except Exception as exc:
        errors, warnings = [str(exc)], []

    result = {
        "is_valid": not errors,
        "issue_analysis": str(issue_analysis_path),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "repair_plan": build_repair_plan(errors),
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
