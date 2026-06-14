#!/usr/bin/env python3
"""Normalize common LLM-shaped issue analysis drafts into the formal contract.

This script performs mechanical contract repairs only. It does not invent new
analysis, evidence, metrics, or research conclusions.
"""

from __future__ import annotations

# Runtime scripts can be run directly. Shared helpers remain in runtime
# `scripts/`; production tools live under role scripts; validators live under QC.
import sys as _ib_sys
from pathlib import Path as _IbPath
_IB_ROLE_SCRIPT_DIR = _IbPath(__file__).resolve().parent
_IB_RUNTIME_ROOT = next(
    _p for _p in _IbPath(__file__).resolve().parents
    if (_p / 'templates').is_dir() and (_p / 'skills').is_dir() and (_p / 'scripts').is_dir()
)
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts"
_IB_ROLE_SCRIPT_DIRS = sorted((_IB_RUNTIME_ROOT / 'skills').glob('*/scripts'))
_IB_QC_VALIDATOR_DIRS = sorted((_IB_RUNTIME_ROOT / 'skills' / 'qc' / 'scripts' / 'validators').glob('*'))
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
import re
from datetime import date
from pathlib import Path
from typing import Any

from json_utils import load_json_file
from validate_issue_analysis import (
    ISSUE_TOPICS_BY_AREA,
    VALID_ANALYSIS_TYPES,
    VALID_BACKLOG_PERMISSIONS,
    VALID_CONFIDENCE_STATUS,
    VALID_EVIDENCE_STATUS,
    VALID_HYPOTHESIS_RESOLUTION,
    VALID_EVIDENCE_SUFFICIENCY,
    VALID_POINT_ROLES,
    VALID_RESEARCH_ACTIONS,
)


TYPE_ALIASES = {
    "market_size": "descriptive_market_fact",
    "market_fact": "descriptive_market_fact",
    "growth": "driver_analysis",
    "growth_driver": "driver_analysis",
    "driver": "driver_analysis",
    "segmentation": "structure_analysis",
    "market_structure": "structure_analysis",
    "profit_pool": "profit_pool_analysis",
    "value_chain": "profit_pool_analysis",
    "barrier": "barrier_analysis",
    "moat": "barrier_analysis",
    "peer": "peer_profile",
    "competition": "competitive_dynamic",
    "competitive_landscape": "competitive_dynamic",
    "trend": "trend_or_risk",
    "risk": "trend_or_risk",
    "target_context": "pitch_context",
    "pitch_relevance": "pitch_context",
    "open_question": "evidence_gap",
}

DEFAULT_SUBISSUE_BY_AREA = {
    "market_size_growth": "current_market_size",
    "demand_customer_logic": "demand_drivers",
    "industry_structure": "value_chain",
    "key_trends_drivers": "secular_tailwinds",
    "competitive_landscape": "peer_universe",
    "competitive_dynamics": "basis_of_competition",
    "pitch_relevance_target_context": "why_sector_relevant",
}

AREA_BY_SUBISSUE = {
    subissue: area
    for area, subissues in ISSUE_TOPICS_BY_AREA.items()
    for subissue in subissues
}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _clean_id_list(value: Any, prefix: str) -> list[str]:
    result: list[str] = []
    pattern = re.compile(rf"\b{prefix}-\d{{3}}\b")
    for item in _as_list(value):
        for match in pattern.findall(str(item)):
            if match not in result:
                result.append(match)
    return result


def _normalize_analysis_type(value: Any) -> str:
    text = str(value or "").strip()
    lowered = text.lower()
    candidate = TYPE_ALIASES.get(lowered, lowered or "analytical_judgment")
    return candidate if candidate in VALID_ANALYSIS_TYPES else "analytical_judgment"


def _normalize_status(value: Any, sufficiency: str) -> str:
    text = str(value or "").strip().lower()
    aliases = {
        "active": "validated",
        "valid": "validated",
        "confirmed": "validated",
        "supported": "validated",
        "partially_supported": "partially_validated",
        "partial": "partially_validated",
        "pending": "unverified",
        "unknown": "unverified",
        "open": "unverified",
    }
    candidate = aliases.get(text, text)
    if candidate in VALID_CONFIDENCE_STATUS:
        return candidate
    if sufficiency == "sufficient":
        return "validated"
    if sufficiency == "thin":
        return "partially_validated"
    return "unverified"


def _normalize_sufficiency(value: Any, evidence_ids: list[str], metric_ids: list[str]) -> str:
    text = str(value or "").strip().lower()
    aliases = {
        "supported": "sufficient",
        "enough": "sufficient",
        "partial": "thin",
        "limited": "thin",
        "weak": "thin",
        "missing": "insufficient",
        "gap": "insufficient",
        "n/a": "not_applicable",
        "na": "not_applicable",
    }
    candidate = aliases.get(text, text)
    if candidate in VALID_EVIDENCE_SUFFICIENCY:
        return candidate
    return "insufficient"


def _normalize_evidence_status(value: Any, sufficiency: str) -> str:
    text = str(value or "").strip().lower().replace("-", "_")
    aliases = {
        "supported": "supported",
        "thin": "thin",
        "weak": "thin",
        "insufficient": "insufficient",
        "no": "not_researched",
        "not_researched": "not_researched",
        "unavailable": "unavailable_after_research",
        "unavailable_after_research": "unavailable_after_research",
        "not_applicable": "not_applicable",
        "caveat": "caveat_only",
        "caveat_only": "caveat_only",
    }
    candidate = aliases.get(text, "")
    if candidate in VALID_EVIDENCE_STATUS:
        return candidate
    return "insufficient"


def _normalize_hypothesis_resolution(value: Any, evidence_status: str, status: str) -> str:
    text = str(value or "").strip().lower().replace("-", "_")
    aliases = {
        "resolved": "resolved",
        "confirm": "resolved",
        "confirmed": "resolved",
        "not_researched": "not_researched",
        "no_evidence": "not_researched",
        "caveat": "caveat_only",
        "deprioritized": "deprioritized",
        "rejected": "rejected",
    }
    candidate = aliases.get(text, text)
    if candidate in VALID_HYPOTHESIS_RESOLUTION:
        return candidate
    if evidence_status in {"not_researched", "caveat_only"}:
        return evidence_status
    return "deprioritized"


def _normalize_issue_area(value: Any, subissue: str) -> str:
    text = str(value or "").strip()
    if text in ISSUE_TOPICS_BY_AREA:
        return text
    return AREA_BY_SUBISSUE.get(subissue, "market_size_growth")


def _normalize_subissue(value: Any, issue_area: str) -> str:
    text = str(value or "").strip()
    if text in AREA_BY_SUBISSUE:
        return text
    return DEFAULT_SUBISSUE_BY_AREA.get(issue_area, "current_market_size")


def _normalize_permission(value: Any, *, sufficiency: str, metric_ids: list[str]) -> dict[str, bool]:
    if isinstance(value, dict):
        return {
            "headline_allowed": bool(value.get("headline_allowed")),
            "chart_allowed": bool(value.get("chart_allowed")),
            "body_copy_allowed": bool(value.get("body_copy_allowed")),
        }
    return {"headline_allowed": False, "chart_allowed": False, "body_copy_allowed": False}


def _normalize_meta(meta: Any, pool: dict[str, Any]) -> dict[str, str]:
    meta_obj = meta if isinstance(meta, dict) else {}
    return {
        "target_company": str(
            meta_obj.get("target_company")
            or meta_obj.get("target_name")
            or pool.get("target_company")
            or "Unknown Target"
        ),
        "industry": str(meta_obj.get("industry") or pool.get("industry") or "Unknown industry"),
        "geography": str(meta_obj.get("geography") or pool.get("geography") or "Unknown geography"),
        "research_as_of_date": str(
            meta_obj.get("research_as_of_date")
            or meta_obj.get("generated_date")
            or pool.get("research_as_of_date")
            or date.today().isoformat()
        ),
    }


def _normalize_supporting_points(raw: dict[str, Any], evidence_ids: list[str], metric_ids: list[str], sufficiency: str) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for item in _as_list(raw.get("supporting_points", raw.get("supporting_facts"))):
        if not isinstance(item, dict):
            continue
        point_evidence = _clean_id_list(item.get("evidence_ids"), "EV")
        point_metrics = _clean_id_list(item.get("metric_ids"), "MET")
        role = str(item.get("role") or "primary_fact").strip()
        if role not in VALID_POINT_ROLES:
            role = "primary_fact"
        point_sufficiency = _normalize_sufficiency(item.get("evidence_sufficiency", item.get("fact_status")), point_evidence, point_metrics)
        points.append(
            {
                "point": str(item.get("point") or item.get("fact") or "").strip(),
                "evidence_ids": point_evidence,
                "metric_ids": point_metrics,
                "role": role,
                "evidence_sufficiency": point_sufficiency,
            }
        )
    if points:
        return points
    return [
        {
            "point": str(raw.get("supporting_point") or raw.get("fact") or raw.get("core_statement") or "").strip(),
            "evidence_ids": evidence_ids,
            "metric_ids": metric_ids,
            "role": "primary_fact" if (evidence_ids or metric_ids) else "open_gap",
            "evidence_sufficiency": sufficiency,
        }
    ]


def normalize(pool: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    raw_analyses = pool.get("issue_analyses")
    if raw_analyses is None:
        warnings.append("issue_analyses is missing; normalizer will emit an empty issue_analyses array")

    normalized: dict[str, Any] = {
        "meta": _normalize_meta(pool.get("meta"), pool),
        "issue_analyses": [],
        "research_backlog": [],
        "rejected_or_deprioritized_analyses": [],
    }

    for idx, raw in enumerate(_as_list(raw_analyses), start=1):
        if not isinstance(raw, dict):
            warnings.append(f"issue_analyses[{idx}] was not an object and was skipped")
            continue
        analysis_id = str(raw.get("analysis_id") or f"IA-{idx:03d}").strip()
        subissue = _normalize_subissue(raw.get("subissue", raw.get("issue_topic")), str(raw.get("issue_area") or ""))
        issue_area = _normalize_issue_area(raw.get("issue_area"), subissue)
        subissue = _normalize_subissue(raw.get("subissue", raw.get("issue_topic")), issue_area)
        evidence_ids = _clean_id_list(raw.get("evidence_ids"), "EV")
        metric_ids = _clean_id_list(raw.get("metric_ids"), "MET")
        sufficiency = _normalize_sufficiency(raw.get("evidence_sufficiency", raw.get("confidence")), evidence_ids, metric_ids)
        status = _normalize_status(raw.get("status"), sufficiency)
        source_execution_result_ids = _clean_id_list(
            raw.get("source_execution_result_ids", raw.get("formal_research_result_ids")),
            "FR",
        )
        if not source_execution_result_ids:
            source_execution_result_ids = [f"FR-{idx:03d}"]
            warnings.append(f"{analysis_id}: source_execution_result_ids missing; filled {source_execution_result_ids[0]} as mechanical placeholder")

        evidence_status = _normalize_evidence_status(raw.get("evidence_status"), sufficiency)
        hypothesis_resolution = _normalize_hypothesis_resolution(raw.get("hypothesis_resolution"), evidence_status, status)
        allowed_deck_usage = raw.get("allowed_deck_usage") if isinstance(raw.get("allowed_deck_usage"), dict) else {}
        normalized_allowed = {
            "headline": bool(allowed_deck_usage.get("headline")),
            "main_message": bool(allowed_deck_usage.get("main_message")),
            "chart": bool(allowed_deck_usage.get("chart")),
            "body_copy": bool(allowed_deck_usage.get("body_copy")),
        }
        if status in {"rejected", "unverified"} and not any(normalized_allowed.values()):
            normalized_allowed["body_copy"] = False
            if evidence_status not in {"not_researched", "caveat_only"}:
                normalized_allowed["body_copy"] = False
        if evidence_status in {"not_researched", "caveat_only"}:
            normalized_allowed = {"headline": False, "main_message": False, "chart": False, "body_copy": False}

        normalized_analysis = {
            "analysis_id": analysis_id,
            "source_execution_result_ids": source_execution_result_ids,
            "issue_area": issue_area,
            "subissue": subissue,
            "analysis_type": _normalize_analysis_type(raw.get("analysis_type", raw.get("type"))),
            "core_statement": str(raw.get("core_statement") or raw.get("finding") or "").strip(),
            "analysis_text": str(raw.get("analysis_text") or raw.get("so_what_for_pitch") or raw.get("so_what") or "").strip(),
            "supporting_points": _normalize_supporting_points(raw, evidence_ids, metric_ids, sufficiency),
            "evidence_status": evidence_status,
            "hypothesis_resolution": hypothesis_resolution,
            "evidence_sufficiency": sufficiency,
            "status": status,
            "evidence_ids": evidence_ids,
            "metric_ids": metric_ids,
            "limitations": [str(item).strip() for item in _as_list(raw.get("limitations")) if str(item).strip()],
            "downstream_permission": _normalize_permission(raw.get("downstream_permission", raw.get("usage_permission")), sufficiency=sufficiency, metric_ids=metric_ids),
            "allowed_deck_usage": normalized_allowed,
        }
        if raw.get("candidate_use_cases") is not None:
            normalized_analysis["candidate_use_cases"] = [
                str(item).strip()
                for item in _as_list(raw.get("candidate_use_cases"))
                if str(item).strip()
            ]
        normalized["issue_analyses"].append(normalized_analysis)

    for idx, raw in enumerate(_as_list(pool.get("research_backlog")), start=1):
        if not isinstance(raw, dict):
            warnings.append(f"research_backlog[{idx}] was not an object and was skipped")
            continue
        subissue = _normalize_subissue(raw.get("subissue", raw.get("issue_topic")), str(raw.get("issue_area") or ""))
        issue_area = _normalize_issue_area(raw.get("issue_area"), subissue)
        attempted_statement = str(raw.get("attempted_statement") or raw.get("attempted_judgment") or "").strip()
        reason = str(raw.get("reason") or "").strip()
        if not reason:
            reason = "Current research pack does not provide sufficient EV/MET support for a confident issue analysis."
        needed_evidence = [str(item).strip() for item in _as_list(raw.get("needed_evidence")) if str(item).strip()]
        if not needed_evidence:
            needed_evidence = [f"Additional reviewed evidence for {issue_area}/{subissue} with clear source locator and scope."]
        normalized["research_backlog"].append(
            {
                "issue_area": issue_area,
                "subissue": _normalize_subissue(raw.get("subissue", raw.get("issue_topic")), issue_area),
                "attempted_statement": attempted_statement,
                "reason": reason,
                "needed_evidence": needed_evidence,
                "research_action": str(raw.get("research_action") or "run_targeted_search").strip()
                if str(raw.get("research_action") or "run_targeted_search").strip() in VALID_RESEARCH_ACTIONS
                else "run_targeted_search",
                "downstream_permission": str(raw.get("downstream_permission") or "do_not_use_for_strong_claim").strip()
                if str(raw.get("downstream_permission") or "do_not_use_for_strong_claim").strip() in VALID_BACKLOG_PERMISSIONS
                else "do_not_use_for_strong_claim",
            }
        )

    rejected_raw = pool.get("rejected_or_deprioritized_analyses", [])
    for idx, raw in enumerate(_as_list(rejected_raw), start=1):
        if not isinstance(raw, dict):
            continue
        source_execution_result_id = str(raw.get("source_execution_result_id") or raw.get("formal_research_result_id") or f"FR-{idx:03d}").strip()
        normalized["rejected_or_deprioritized_analyses"].append(
            {
                "source_execution_result_id": source_execution_result_id,
                "attempted_statement": str(raw.get("attempted_statement") or raw.get("finding") or "").strip(),
                "reason": str(raw.get("reason") or raw.get("limitations") or "Rejected or deprioritized during research validation.").strip(),
                "evidence_ids": _clean_id_list(raw.get("evidence_ids"), "EV"),
            }
        )

    return normalized, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Draft industry_issue_analysis.json")
    parser.add_argument("--output", required=True, help="Normalized industry_issue_analysis.json")
    parser.add_argument("--report", help="Optional JSON report path")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    pool = load_json_file(input_path)
    if not isinstance(pool, dict):
        raise SystemExit("input must be a JSON object")
    normalized, warnings = normalize(pool)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = {
        "is_valid": True,
        "input": str(input_path),
        "output": str(output_path),
        "warning_count": len(warnings),
        "warnings": warnings,
    }
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
