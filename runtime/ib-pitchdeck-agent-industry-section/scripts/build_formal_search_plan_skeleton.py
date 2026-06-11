#!/usr/bin/env python3
"""Build a full-taxonomy formal_search_plan skeleton.

The skeleton keeps taxonomy, FS numbering, and issue/subissue coverage
mechanical. The LLM should edit the generated research questions, queries,
purposes, and source hints using the industry_scope_pack, but it should not
delete issue/subissue rows.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from issue_taxonomy import ISSUE_TOPICS_BY_AREA
from json_utils import load_json_file


SOURCE_HINTS_BY_AREA = {
    "market_size_growth": "official statistics, industry association, broker/consulting report, market data provider",
    "demand_customer_logic": "customer/end-user/end-market research, industry report, channel/platform/user data",
    "industry_structure": "industry report, company filings, broker report, value-chain analysis",
    "key_trends_drivers": "industry report, regulator/standard body, technology report, broker report, M&A news",
    "competitive_landscape": "company filings, industry report, peer disclosures, market data provider",
    "competitive_dynamics": "industry report, company disclosures, broker report, trade media with cited data",
    "pitch_relevance_target_context": "company-provided materials, peer transactions, investor commentary, sector reports",
}

SOURCE_SPECIFIC_HINTS = {
    "market_size_growth": "official statistics, industry associations, regulatory or sector reports",
    "demand_customer_logic": "company filings, company calls/transcripts, user or purchaser research",
    "industry_structure": "industry reports, value-chain studies, financial filings",
    "key_trends_drivers": "industry report, regulator/standard body, M&A and company announcements",
    "competitive_landscape": "company filings, peer filings, transaction updates",
    "competitive_dynamics": "financial results, M&A databases, strategic announcements",
    "pitch_relevance_target_context": "company disclosures, peer transactions, sector commentary",
}

DEEP_SEARCH_PAIRS = {
    ("market_size_growth", "current_market_size"),
    ("market_size_growth", "historical_growth"),
    ("market_size_growth", "forecast_growth"),
    ("market_size_growth", "market_segmentation"),
    ("industry_structure", "value_chain"),
    ("industry_structure", "profit_pool"),
    ("industry_structure", "barriers_to_entry"),
    ("key_trends_drivers", "secular_tailwinds"),
    ("key_trends_drivers", "channel_or_go_to_market_shift"),
    ("competitive_landscape", "competitor_profiles"),
    ("competitive_landscape", "strategic_positioning"),
    ("competitive_dynamics", "consolidation_logic"),
    ("pitch_relevance_target_context", "why_sector_relevant"),
    ("pitch_relevance_target_context", "discussion_implications"),
}

ACCOUNTING_ONLY_PAIRS = {
    ("market_size_growth", "market_cycle"),
    ("key_trends_drivers", "technology_disruption"),
    ("key_trends_drivers", "regulatory_developments"),
    ("competitive_landscape", "valuation_snapshot_peer_fact"),
    ("pitch_relevance_target_context", "evidence_limits"),
}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _build_coverage_map(plan: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for row in _as_list(plan.get("issue_search_plan")):
        if not isinstance(row, dict):
            continue
        area = _text(row.get("issue_area"))
        subissue = _text(row.get("subissue"))
        rows.append(
            {
                "issue_area": area,
                "subissue": subissue,
                "execution_expectation": _text(row.get("execution_expectation")),
                "minimum_actual_searches": int(row.get("minimum_actual_searches", 0)),
                "execution_rationale": _text(row.get("execution_rationale")),
                "source_specific_query_type": _text(row.get("execution_expectation")),
                "expected_source_type": _expected_source_type(area),
                "research_question": _text(row.get("research_question")),
                "plan_row": _text(row.get("search_instructions", [{}])[0].get("instruction_id", "")) if row.get("search_instructions") else "",
            }
        )
    return {
        "schema_version": "coverage_map_v1",
        "coverage_mode": "canonical_taxonomy_vs_subissues",
        "language": "mixed",
        "scope": "industry_research_scope",
        "rows": rows,
    }


def _expected_source_type(issue_area: str) -> str:
    return SOURCE_SPECIFIC_HINTS.get(issue_area, "public_search")


def _to_text_query(text: Any) -> str:
    return " ".join(_text(text).split()) if text is not None else ""


def _query_variant(query: str, issue_area: str) -> tuple[str, str]:
    english_query = _to_text_query(query)
    if not english_query:
        english_query = f"{issue_area} evidence"
    chinese_query = f"{issue_area} {english_query}"
    return (
        english_query,
        chinese_query,
    )


def _build_search_batch(plan: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for row in _as_list(plan.get("issue_search_plan")):
        if not isinstance(row, dict):
            continue
        issue_area = _text(row.get("issue_area"))
        subissue = _text(row.get("subissue"))
        research_question = _to_text_query(row.get("research_question"))
        english_query, chinese_query = _query_variant(research_question, issue_area)
        rows.append(
            {
                "issue_area": issue_area,
                "subissue": subissue,
                "english_query": english_query,
                "chinese_query": chinese_query,
                "source_specific_query": row.get("search_instructions", [{}])[0].get("query", ""),
                "expected_source_type": _expected_source_type(issue_area),
                "why_this_search_matters": _text(row.get("execution_rationale")) or _to_text_query(row.get("research_question")),
                "how_result_will_be_used": (
                    "Drive source-reviewed evidence for the paired issue/subissue and map it to issue analysis deck rows."
                ),
            }
        )
    return {
        "schema_version": "search_batch_v1",
        "source_language": "mixed",
        "scope": "industry_research_scope",
        "batches": rows,
    }


def _text(value: Any) -> str:
    return str(value or "").strip()


def _load_optional(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    data = load_json_file(p)
    return data if isinstance(data, dict) else {}


def _first_text(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def _scope_summary(scope_pack: dict[str, Any]) -> dict[str, Any]:
    value = scope_pack.get("scope_summary")
    return value if isinstance(value, dict) else {}


def _meta_from_inputs(input_card: dict[str, Any], scope_pack: dict[str, Any]) -> dict[str, str]:
    input_meta = input_card.get("meta") if isinstance(input_card.get("meta"), dict) else {}
    scope_meta = scope_pack.get("meta") if isinstance(scope_pack.get("meta"), dict) else {}
    return {
        "target_company": _first_text(input_card.get("target_company"), input_meta.get("target_company"), scope_meta.get("target_company")),
        "transaction_type": _first_text(input_card.get("transaction_type"), input_meta.get("transaction_type"), scope_meta.get("transaction_type")),
        "industry": _first_text(input_card.get("industry"), input_meta.get("industry"), scope_meta.get("industry")),
        "subsector": _first_text(input_card.get("subsector"), input_meta.get("subsector"), scope_meta.get("subsector")),
        "geography": _first_text(input_card.get("geography"), input_meta.get("geography"), scope_meta.get("geography")),
        "language": _first_text(input_card.get("language"), input_meta.get("language"), scope_meta.get("language"), "English"),
        "prepared_date": date.today().isoformat(),
        "research_as_of_date": date.today().isoformat(),
    }


def _market_terms(meta: dict[str, str], scope_pack: dict[str, Any]) -> str:
    summary = _scope_summary(scope_pack)
    pieces = [
        _first_text(summary.get("working_market"), meta.get("subsector"), meta.get("industry"), "target industry"),
        _first_text(meta.get("geography"), summary.get("geography")),
    ]
    output: list[str] = []
    seen: set[str] = set()
    for piece in pieces:
        text = piece.strip()
        if text and text.lower() not in seen:
            output.append(text)
            seen.add(text.lower())
    return " ".join(output) or "target industry"


def _label(value: str) -> str:
    return value.replace("_", " ")


def _execution_policy(issue_area: str, subissue: str) -> tuple[str, int, str]:
    pair = (issue_area, subissue)
    if pair in DEEP_SEARCH_PAIRS:
        return (
            "deep_search",
            2,
            "Core pitch issue: run at least two actual S-xxx searches when possible, ideally authority/source-specific plus reconciliation/counter-check.",
        )
    if pair in ACCOUNTING_ONLY_PAIRS:
        return (
            "accounting_only",
            0,
            "Coverage-audit row: execute only if material after scoping; otherwise account for it as not_material or not_executed in formal execution.",
        )
    return (
        "light_search",
        1,
        "Supporting issue: run one actual S-xxx search when material, or account for why it is not material/available.",
    )


def _priority_for_expectation(expectation: str) -> str:
    if expectation == "deep_search":
        return "high"
    if expectation == "accounting_only":
        return "low"
    return "medium"


def _query_variants(market_terms: str, issue_label: str, subissue_label: str, expectation: str) -> list[str]:
    direct = f"{market_terms} {issue_label} {subissue_label} industry report"
    authority = f"{market_terms} {subissue_label} official data industry association broker report"
    reconciliation = f"{market_terms} {subissue_label} methodology scope comparison conflicting data"
    if expectation == "deep_search":
        return [direct, authority, reconciliation]
    if expectation == "light_search":
        return [direct]
    return [direct]


def build_plan(input_card: dict[str, Any], scope_pack: dict[str, Any]) -> dict[str, Any]:
    meta = _meta_from_inputs(input_card, scope_pack)
    market_terms = _market_terms(meta, scope_pack)
    issue_search_plan: list[dict[str, Any]] = []
    fs_counter = 1

    for issue_area, subissues in ISSUE_TOPICS_BY_AREA.items():
        for subissue in sorted(subissues):
            fs_id = f"FS-{fs_counter:03d}"
            fs_counter += 1
            issue_label = _label(issue_area)
            subissue_label = _label(subissue)
            execution_expectation, minimum_actual_searches, rationale = _execution_policy(issue_area, subissue)
            query_variants = _query_variants(market_terms, issue_label, subissue_label, execution_expectation)
            issue_search_plan.append(
                {
                    "issue_area": issue_area,
                    "subissue": subissue,
                    "priority": _priority_for_expectation(execution_expectation),
                    "execution_expectation": execution_expectation,
                    "minimum_actual_searches": minimum_actual_searches,
                    "coverage_required": True,
                    "terminal_status": "pending",
                    "execution_rationale": rationale,
                    "research_question": (
                        f"What evidence is available for {subissue_label} within {market_terms}, "
                        "and what source scope, period, geography, denominator, and limitations apply?"
                    ),
                    "search_instructions": [
                        {
                            "instruction_id": fs_id,
                            "query": query_variants[0],
                            "query_variants": query_variants,
                            "purpose": (
                                f"Find formal evidence for {issue_area}/{subissue}; capture facts, metrics, "
                                "scope, period, source authority, and limitations."
                            ),
                            "search_stage": "formal_research_execution",
                            "source_hint": SOURCE_HINTS_BY_AREA.get(issue_area, "industry report, company disclosure, official or authoritative source"),
                        }
                    ],
                }
            )

    return {
        "schema_version": "formal_search_plan_v1",
        "meta": meta,
        "plan_mode": "coverage_audit",
        "industry_scope_pack": {
            "artifact_path": "artifacts/industry_scope_pack.json",
            "purpose": (
                "Use the scope pack as a research map. Do not convert scope-pack leads "
                "into findings until formal research execution validates them."
            ),
        },
        "coverage_requirement": {
            "must_cover_all_canonical_subissues": True,
            "canonical_issue_area_count": len(ISSUE_TOPICS_BY_AREA),
            "canonical_subissue_count": sum(len(items) for items in ISSUE_TOPICS_BY_AREA.values()),
            "instruction": (
                "Retain every issue_search_plan row. Edit queries to fit the industry, "
                "but do not delete low-relevance subissues. The taxonomy is a coverage audit, "
                "not an equal-depth search mandate: execute deep/light rows as planned, and explicitly "
                "account for not_material, not_executed, or unavailable rows in formal_research_execution_report.json."
            ),
        },
        "allowed_issue_taxonomy": {area: sorted(subissues) for area, subissues in ISSUE_TOPICS_BY_AREA.items()},
        "planning_instruction": (
            "This plan intentionally covers every canonical issue/subissue to thicken upstream research. "
            "For each row, refine executable query variants and execution expectations. Do not write investment "
            "hypotheses, validated findings, slide conclusions, or page plans. A planned FS row or query is not evidence."
        ),
        "issue_search_plan": issue_search_plan,
        "research_discipline": {
            "do_not_generate_hypotheses": True,
            "formal_validation_lives_in": "artifacts/formal_research_execution_report.json",
            "execution_report_inherits_plan_taxonomy": (
                "Copy issue_area, subissue, and research_question from the owning formal_search_plan row."
            ),
            "fs_vs_s_id_discipline": (
                "FS-xxx IDs are planned search instructions. Real searches must be logged as S-xxx attempts."
            ),
            "planned_vs_actual_accounting": (
                "A planned FS row is not evidence. Only actually executed S-xxx attempts can support source reviews, "
                "research_evidence_db rows, issue analysis, or deck claims. Unexecuted FS rows must be accounted for "
                "as not_executed, not_material, unavailable, or research_backlog; never create fake S-xxx IDs."
            ),
            "if_evidence_is_insufficient": (
                "Record thin/insufficient/unavailable_after_research in the formal execution report and research pack; "
                "do not invent a page claim."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-card", help="Optional input_card.json path")
    parser.add_argument("--scope-pack", help="Optional artifacts/industry_scope_pack.json path")
    parser.add_argument("--output", required=True)
    parser.add_argument("--coverage-map", help="Optional artifacts/coverage_map.json output path")
    parser.add_argument("--search-batch", help="Optional artifacts/search_batch.json output path")
    args = parser.parse_args()

    input_card = _load_optional(args.input_card)
    scope_pack = _load_optional(args.scope_pack)
    plan = build_plan(input_card, scope_pack)
    coverage_map = _build_coverage_map(plan)
    search_batch = _build_search_batch(plan)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.coverage_map:
        coverage_map_path = Path(args.coverage_map)
        coverage_map_path.parent.mkdir(parents=True, exist_ok=True)
        coverage_map_path.write_text(json.dumps(coverage_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.search_batch:
        search_batch_path = Path(args.search_batch)
        search_batch_path.parent.mkdir(parents=True, exist_ok=True)
        search_batch_path.write_text(json.dumps(search_batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"is_valid": True, "output": str(output_path), "issue_search_plan_count": len(plan["issue_search_plan"])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
