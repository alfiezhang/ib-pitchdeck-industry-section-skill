#!/usr/bin/env python3
"""Build an industry_issue_analysis.json skeleton from the research pack.

This script performs mechanical structuring only: it reads IB Issue Fact
Inventory plus the formal research execution report, creates IA rows for
sufficient/thin/not_applicable subissues, and creates complete backlog rows for
unsupported subissues. The generated IA text intentionally contains placeholder
markers that validate_issue_analysis.py will block until the LLM writes real
analysis.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from issue_taxonomy import ISSUE_TOPICS_BY_AREA
from json_utils import load_json_file
from validate_research_pack import issue_fact_inventory_rows


ANALYSIS_CANDIDATE_STATUSES = {"sufficient", "thin", "not_applicable"}


def _as_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _allowed_deck_usage(fact_status: str, metric_ids: list[str]) -> dict[str, bool]:
    return {
        "headline": False,
        "main_message": False,
        "chart": False,
        "body_copy": False,
    }


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _load_optional_json(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    data = load_json_file(p)
    return data if isinstance(data, dict) else {}


def _ids(raw: str, prefix: str) -> list[str]:
    import re

    return sorted(set(re.findall(rf"\b{prefix}-\d{{3}}\b", str(raw or ""))))


def _meta_from_pack(text: str) -> dict[str, str]:
    fields = {
        "target_company": "Target Company",
        "industry": "Industry",
        "geography": "Geography",
        "research_as_of_date": "Research As-Of Date",
    }
    result = {
        "target_company": "Unknown Target",
        "industry": "Unknown industry",
        "geography": "Unknown geography",
        "research_as_of_date": date.today().isoformat(),
    }
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        for target, label in fields.items():
            if key.lower() == label.lower() and value:
                result[target] = value
    return result


def _meta_from_db(db: dict[str, Any]) -> dict[str, str]:
    meta = db.get("meta") if isinstance(db.get("meta"), dict) else {}
    return {
        "target_company": _text(meta.get("target_company")) or "Unknown Target",
        "industry": _text(meta.get("industry")) or "Unknown industry",
        "geography": _text(meta.get("geography")) or "Unknown geography",
        "research_as_of_date": _text(meta.get("research_as_of_date")) or date.today().isoformat(),
    }


def _evidence_readiness_from_db(db: dict[str, Any]) -> dict[str, Any]:
    evidence_rows = _as_int(len(_as_list(db.get("evidence_ledger"))))
    metric_rows = _as_int(len(_as_list(db.get("metric_reconciliation"))))
    gap_audit = db.get("research_gap_audit") if isinstance(db.get("research_gap_audit"), dict) else {}
    critical_gaps = len(_as_list(gap_audit.get("critical_gaps")))
    return {
        "schema_version": "evidence_readiness_v1",
        "decision_status": "needs_llm_decision",
        "decision_owner": "reasoning",
        "decision_note": "Skeleton telemetry only. LLM must decide deliverable depth after reviewing evidence quality and gaps.",
        "enough_for_client_pitch": False,
        "evidence_limited_pitch_outline": True,
        "research_first_required": evidence_rows == 0 and metric_rows == 0,
        "critical_gap_count": critical_gaps,
        "evidence_row_count": evidence_rows,
        "metric_row_count": metric_rows,
        "research_pack_exists": True,
        "telemetry_only": True,
    }


def _db_inventory_rows(db: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in _as_list(db.get("issue_fact_inventory")):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "Issue Area": _text(item.get("issue_area")),
                "Subissue": _text(item.get("subissue")),
                "Evidence IDs": ", ".join(_text(ev) for ev in _as_list(item.get("evidence_ids")) if _text(ev)),
                "Metric IDs": ", ".join(_text(met) for met in _as_list(item.get("metric_ids")) if _text(met)),
                "Fact Status": _text(item.get("fact_status")),
                "Notes": _text(item.get("notes")),
            }
        )
    return rows


def _result_by_pair(report: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for result in _as_list(report.get("issue_results")):
        if not isinstance(result, dict):
            continue
        area = _text(result.get("issue_area"))
        subissue = _text(result.get("subissue"))
        if area and subissue:
            out[(area, subissue)] = result
    return out


def _analysis_type(area: str, subissue: str) -> str:
    if area == "market_size_growth":
        return "descriptive_market_fact" if subissue in {"current_market_size", "historical_growth", "forecast_growth", "market_segmentation"} else "analytical_judgment"
    if area == "demand_customer_logic":
        return "driver_analysis"
    if area == "industry_structure":
        if subissue == "profit_pool":
            return "profit_pool_analysis"
        if subissue == "barriers_to_entry":
            return "barrier_analysis"
        return "structure_analysis"
    if area == "key_trends_drivers":
        return "trend_or_risk"
    if area == "competitive_landscape":
        return "peer_profile"
    if area == "competitive_dynamics":
        return "competitive_dynamic"
    if area == "pitch_relevance_target_context":
        return "pitch_context"
    return "analytical_judgment"


def _status_for_fact_status(fact_status: str) -> str:
    # Script-generated issue analysis is a decision workspace. The Reasoning/QC
    # role must decide validation status after reviewing source quality.
    return "unverified"


def _permission(fact_status: str, metric_ids: list[str]) -> dict[str, bool]:
    return {
        "headline_allowed": False,
        "chart_allowed": False,
        "body_copy_allowed": False,
    }


def _source_result_ids(result: dict[str, Any], fallback_index: int) -> list[str]:
    result_id = _text(result.get("result_id"))
    if result_id:
        return [result_id]
    return [f"FR-{fallback_index:03d}"]


def _needed_evidence(area: str, subissue: str, result: dict[str, Any]) -> list[str]:
    question = _text(result.get("research_question"))
    if question:
        return [f"Reviewed source evidence answering: {question}"]
    return [f"Reviewed evidence or metric support for {area}/{subissue} with source locator, scope, period, geography, and limitation."]


def build_issue_analysis_skeleton(
    research_pack_path: Path | None,
    execution_report: dict[str, Any],
    research_evidence_db: dict[str, Any] | None = None,
) -> dict[str, Any]:
    db = research_evidence_db or {}
    if db:
        text = ""
        rows = _db_inventory_rows(db)
        evidence_readiness = _evidence_readiness_from_db(db)
    elif research_pack_path:
        text = research_pack_path.read_text(encoding="utf-8")
        rows = issue_fact_inventory_rows(text)
        evidence_readiness = {
            "schema_version": "evidence_readiness_v1",
            "decision_status": "needs_llm_decision",
            "decision_owner": "reasoning",
            "decision_note": "Skeleton telemetry only. LLM must decide deliverable depth after reviewing evidence quality and gaps.",
            "enough_for_client_pitch": False,
            "evidence_limited_pitch_outline": True,
            "research_first_required": True,
            "critical_gap_count": 0,
            "evidence_row_count": len({ev for row in rows for ev in _ids(row.get("Evidence IDs", ""), "EV")}),
            "metric_row_count": len({met for row in rows for met in _ids(row.get("Metric IDs", ""), "MET")}),
            "research_pack_exists": True,
            "telemetry_only": True,
        }
    else:
        text = ""
        rows = []
        evidence_readiness = {
            "schema_version": "evidence_readiness_v1",
            "decision_status": "needs_llm_decision",
            "decision_owner": "reasoning",
            "decision_note": "Skeleton telemetry only. LLM must decide deliverable depth after reviewing evidence quality and gaps.",
            "enough_for_client_pitch": False,
            "evidence_limited_pitch_outline": True,
            "research_first_required": True,
            "critical_gap_count": 0,
            "evidence_row_count": 0,
            "metric_row_count": 0,
            "research_pack_exists": False,
            "telemetry_only": True,
        }
    rows_by_pair: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        area = _text(row.get("Issue Area"))
        subissue = _text(row.get("Subissue") or row.get("Issue Topic"))
        if area and subissue:
            rows_by_pair[(area, subissue)] = row

    results_by_pair = _result_by_pair(execution_report)
    issue_analyses: list[dict[str, Any]] = []
    backlog: list[dict[str, Any]] = []
    fallback_fr_index = 1

    for area, subissues in ISSUE_TOPICS_BY_AREA.items():
        for subissue in sorted(subissues):
            row = rows_by_pair.get((area, subissue), {})
            result = results_by_pair.get((area, subissue), {})
            fact_status = _text(row.get("Fact Status")) or "insufficient"
            evidence_ids = _ids(row.get("Evidence IDs", ""), "EV")
            metric_ids = _ids(row.get("Metric IDs", ""), "MET")
            notes = _text(row.get("Notes")) or _text(result.get("findings_summary"))
            source_result_ids = _source_result_ids(result, fallback_fr_index)
            fallback_fr_index += 1

            if fact_status in ANALYSIS_CANDIDATE_STATUSES and (fact_status == "not_applicable" or evidence_ids or metric_ids):
                analysis_id = f"IA-{len(issue_analyses) + 1:03d}"
                point_role = "open_gap" if fact_status == "not_applicable" else "primary_fact"
                issue_analyses.append(
                    {
                        "analysis_id": analysis_id,
                        "source_execution_result_ids": source_result_ids,
                        "issue_area": area,
                        "subissue": subissue,
                        "analysis_type": "evidence_gap" if fact_status == "not_applicable" else _analysis_type(area, subissue),
                        "evidence_status": "insufficient",
                        "hypothesis_resolution": "not_researched",
                        "llm_decision_required": True,
                        "candidate_fact_status": fact_status,
                        "core_statement": f"TODO_REPLACE_WITH_CORE_STATEMENT for {area}/{subissue}. Current inventory note: {notes}",
                        "analysis_text": (
                            f"TODO_REPLACE_WITH_SUBSTANTIVE_ANALYSIS for {area}/{subissue}. "
                            "Write a banker-quality issue paragraph using the research evidence pack: state the finding, cite the evidence/metric logic, explain the mechanism, identify limitations, and say why it matters for the pitch discussion. "
                            f"Current inventory note: {notes}"
                        ),
                        "supporting_points": [
                            {
                                "point": f"TODO_REPLACE_WITH_SOURCE_FAITHFUL_SUPPORTING_POINT for {area}/{subissue}.",
                                "evidence_ids": evidence_ids,
                                "metric_ids": metric_ids,
                                "role": point_role,
                                "evidence_sufficiency": "insufficient",
                            }
                        ],
                        "evidence_sufficiency": "insufficient",
                        "status": "unverified",
                        "allowed_deck_usage": _allowed_deck_usage(fact_status, metric_ids),
                        "evidence_ids": evidence_ids,
                        "metric_ids": metric_ids,
                        "limitations": [
                            _text(item)
                            for item in _as_list(result.get("limitations"))
                            if _text(item)
                        ]
                        or ([notes] if notes else ["LLM must add limitations from the research evidence pack."]),
                        "downstream_permission": _permission("insufficient", []),
                    }
                )
            else:
                backlog.append(
                    {
                        "issue_area": area,
                        "subissue": subissue,
                        "attempted_statement": notes,
                        "reason": notes
                        or "Research evidence pack does not yet provide sufficient EV/MET support for a confident issue analysis.",
                        "needed_evidence": _needed_evidence(area, subissue, result),
                        "research_action": "run_targeted_search",
                        "downstream_permission": "do_not_use_for_strong_claim",
                    }
                )

    return {
        "meta": _meta_from_db(db) if db else _meta_from_pack(text),
        "evidence_readiness": evidence_readiness,
        "issue_analyses": issue_analyses,
        "research_backlog": backlog,
        "rejected_or_deprioritized_analyses": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research-pack")
    parser.add_argument("--research-evidence-db")
    parser.add_argument("--formal-research-execution-report")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not args.research_pack and not args.research_evidence_db:
        parser.error("--research-pack or --research-evidence-db is required")

    output = build_issue_analysis_skeleton(
        research_pack_path=Path(args.research_pack) if args.research_pack else None,
        execution_report=_load_optional_json(args.formal_research_execution_report),
        research_evidence_db=_load_optional_json(args.research_evidence_db),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "is_valid": True,
                "output": str(output_path),
                "issue_analysis_skeleton_count": len(output["issue_analyses"]),
                "research_backlog_count": len(output["research_backlog"]),
                "note": "Skeleton contains TODO markers and must be substantively edited before validate_issue_analysis.py can pass.",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
