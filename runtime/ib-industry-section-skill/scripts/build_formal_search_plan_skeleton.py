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
    "demand_customer_logic": "consumer survey, customer research, industry report, platform/user data",
    "industry_structure": "industry report, company filings, broker report, value-chain analysis",
    "key_trends_drivers": "industry report, regulator/standard body, technology report, broker report, M&A news",
    "competitive_landscape": "company filings, industry report, peer disclosures, market data provider",
    "competitive_dynamics": "industry report, company disclosures, broker report, trade media with cited data",
    "pitch_relevance_target_context": "company-provided materials, peer transactions, investor commentary, sector reports",
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
            issue_search_plan.append(
                {
                    "issue_area": issue_area,
                    "subissue": subissue,
                    "priority": "medium",
                    "research_question": (
                        f"What evidence is available for {subissue_label} within {market_terms}, "
                        "and what source scope, period, geography, denominator, and limitations apply?"
                    ),
                    "search_instructions": [
                        {
                            "instruction_id": fs_id,
                            "query": f"{market_terms} {issue_label} {subissue_label} industry report source",
                            "purpose": (
                                f"Find formal evidence for {issue_area}/{subissue}; capture facts, metrics, "
                                "scope, period, source authority, and limitations."
                            ),
                            "source_hint": SOURCE_HINTS_BY_AREA.get(issue_area, "industry report, company disclosure, official or authoritative source"),
                        }
                    ],
                }
            )

    return {
        "schema_version": "formal_search_plan_v1",
        "meta": meta,
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
                "but do not delete low-relevance subissues; execute the search and mark "
                "the result thin/insufficient/unavailable in formal_research_execution_report.json if needed."
            ),
        },
        "allowed_issue_taxonomy": {area: sorted(subissues) for area, subissues in ISSUE_TOPICS_BY_AREA.items()},
        "planning_instruction": (
            "This plan intentionally covers every canonical issue/subissue to thicken upstream research. "
            "For each row, write or refine one clear executable search instruction. Do not write investment "
            "hypotheses, validated findings, slide conclusions, or page plans."
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
    args = parser.parse_args()

    input_card = _load_optional(args.input_card)
    scope_pack = _load_optional(args.scope_pack)
    plan = build_plan(input_card, scope_pack)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"is_valid": True, "output": str(output_path), "issue_search_plan_count": len(plan["issue_search_plan"])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
