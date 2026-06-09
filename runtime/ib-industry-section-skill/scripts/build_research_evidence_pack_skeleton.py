#!/usr/bin/env python3
"""Build an industry_research_pack.md evidence-binder skeleton.

This builder does not create final research judgment. It transcribes the
machine-readable research controls into a source-level extraction workspace:
formal research results, reviewed source locators/excerpts, issue fact
inventory rows, and empty EV/MET ledgers for the LLM to populate from reviewed
evidence.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from issue_taxonomy import ISSUE_TOPICS_BY_AREA
from json_utils import load_json_file


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _load_optional(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    data = load_json_file(p)
    return data if isinstance(data, dict) else {}


def _pipe(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    return text.replace("|", "/").replace("\n", " ").strip()


def _join(values: Any) -> str:
    items = [_text(item) for item in _as_list(values) if _text(item)]
    return ", ".join(items)


def _reviews(data: dict[str, Any]) -> list[dict[str, Any]]:
    raw = data.get("reviews")
    if raw is None:
        raw = data.get("source_reviews")
    return [item for item in _as_list(raw) if isinstance(item, dict)]


def _review_id(review: dict[str, Any]) -> str:
    return _text(review.get("source_review_id") or review.get("review_id") or review.get("source_id") or review.get("id"))


def _review_url(review: dict[str, Any]) -> str:
    return _text(review.get("url") or review.get("source_url") or review.get("source") or review.get("source_link"))


def _review_title(review: dict[str, Any]) -> str:
    return _text(review.get("title") or review.get("source_title") or review.get("source_name") or review.get("name"))


def _review_locator(review: dict[str, Any]) -> str:
    return _text(review.get("locator") or review.get("source_locator") or review.get("methodology_locator"))


def _review_excerpt(review: dict[str, Any]) -> str:
    return _text(review.get("excerpt") or review.get("raw_excerpt") or review.get("reviewed_excerpt"))


def _source_reviews_by_id(source_reviews: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {_review_id(review): review for review in _reviews(source_reviews) if _review_id(review)}


def _meta(input_card: dict[str, Any], scope_pack: dict[str, Any]) -> dict[str, str]:
    input_meta = input_card.get("meta") if isinstance(input_card.get("meta"), dict) else {}
    scope_meta = scope_pack.get("meta") if isinstance(scope_pack.get("meta"), dict) else {}
    return {
        "target_company": _text(input_card.get("target_company") or input_meta.get("target_company") or scope_meta.get("target_company")),
        "transaction_type": _text(input_card.get("transaction_type") or input_meta.get("transaction_type") or scope_meta.get("transaction_type")),
        "industry": _text(input_card.get("industry") or input_meta.get("industry") or scope_meta.get("industry")),
        "subsector": _text(input_card.get("subsector") or input_meta.get("subsector") or scope_meta.get("subsector")),
        "geography": _text(input_card.get("geography") or input_meta.get("geography") or scope_meta.get("geography")),
        "language": _text(input_card.get("language") or input_meta.get("language") or scope_meta.get("language") or "English"),
        "prepared_date": date.today().isoformat(),
        "research_as_of_date": _text(input_meta.get("research_as_of_date") or scope_meta.get("research_as_of_date") or date.today().isoformat()),
    }


def _scope_summary(scope_pack: dict[str, Any]) -> dict[str, Any]:
    value = scope_pack.get("scope_summary")
    return value if isinstance(value, dict) else {}


def _issue_fact_status(result: dict[str, Any]) -> str:
    status = _text(result.get("status"))
    has_ids = bool(_as_list(result.get("evidence_ids")) or _as_list(result.get("metric_ids")))
    if status == "supported" and has_ids:
        return "sufficient"
    if status in {"supported", "thin"} and has_ids:
        return "thin"
    if status == "unavailable_after_research":
        return "unavailable_after_research"
    return "insufficient"


def _result_by_pair(report: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    output: dict[tuple[str, str], dict[str, Any]] = {}
    for result in _as_list(report.get("issue_results")):
        if not isinstance(result, dict):
            continue
        area = _text(result.get("issue_area"))
        subissue = _text(result.get("subissue"))
        if area and subissue:
            output[(area, subissue)] = result
    return output


def _formal_execution_rows(report: dict[str, Any]) -> list[str]:
    rows = [
        "| Result ID | Issue Area | Subissue | Research Question | Status | Search Attempt IDs | Source Review IDs | Evidence IDs | Metric IDs | Limitations / Research Pack Handling |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for result in _as_list(report.get("issue_results")):
        if not isinstance(result, dict):
            continue
        limitations = "; ".join([_text(item) for item in _as_list(result.get("limitations")) if _text(item)])
        handling = _text(result.get("research_pack_handling"))
        rows.append(
            "| "
            + " | ".join(
                [
                    _pipe(result.get("result_id")),
                    _pipe(result.get("issue_area")),
                    _pipe(result.get("subissue")),
                    _pipe(result.get("research_question")),
                    _pipe(result.get("status")),
                    _pipe(_join(result.get("search_attempt_ids"))),
                    _pipe(_join(result.get("source_review_ids"))),
                    _pipe(_join(result.get("evidence_ids"))),
                    _pipe(_join(result.get("metric_ids"))),
                    _pipe("; ".join(part for part in (limitations, handling) if part)),
                ]
            )
            + " |"
        )
    return rows


def _formal_extract_rows(report: dict[str, Any], source_reviews: dict[str, Any]) -> list[str]:
    reviews_by_id = _source_reviews_by_id(source_reviews)
    rows = [
        "| Result ID | Source Review ID | Search Attempt IDs | Source URL | Locator | Reviewed Excerpt / Paraphrase | Extracted Fact Or Metric Candidate | Status | Promoted EV/MET IDs | Limitations |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for result in _as_list(report.get("issue_results")):
        if not isinstance(result, dict):
            continue
        source_review_ids = [_text(item) for item in _as_list(result.get("source_review_ids")) if _text(item)]
        if not source_review_ids:
            rows.append(
                "| "
                + " | ".join(
                    [
                        _pipe(result.get("result_id")),
                        "",
                        _pipe(_join(result.get("search_attempt_ids"))),
                        "",
                        "",
                        "",
                        "LLM extract after additional source review, or keep as research gap",
                        _pipe(result.get("status")),
                        _pipe(_join(result.get("evidence_ids")) + (" / " if _join(result.get("evidence_ids")) and _join(result.get("metric_ids")) else "") + _join(result.get("metric_ids"))),
                        _pipe("; ".join([_text(item) for item in _as_list(result.get("limitations")) if _text(item)])),
                    ]
                )
                + " |"
            )
            continue
        for src_id in source_review_ids:
            review = reviews_by_id.get(src_id, {})
            promoted = _join(result.get("evidence_ids"))
            metric_ids = _join(result.get("metric_ids"))
            if promoted and metric_ids:
                promoted = f"{promoted} / {metric_ids}"
            elif metric_ids:
                promoted = metric_ids
            rows.append(
                "| "
                + " | ".join(
                    [
                        _pipe(result.get("result_id")),
                        _pipe(src_id),
                        _pipe(_join(result.get("search_attempt_ids"))),
                        _pipe(_review_url(review)),
                        _pipe(_review_locator(review)),
                        _pipe(_review_excerpt(review)),
                        "LLM must extract the exact fact/metric candidate from this reviewed source",
                        _pipe(result.get("status")),
                        _pipe(promoted),
                        _pipe("; ".join([_text(item) for item in _as_list(result.get("limitations")) if _text(item)])),
                    ]
                )
                + " |"
            )
    return rows


def _issue_inventory_rows(report: dict[str, Any]) -> list[str]:
    by_pair = _result_by_pair(report)
    rows = [
        "| Issue Area | Subissue | Evidence IDs | Metric IDs | Fact Status | Notes |",
        "|---|---|---|---|---|---|",
    ]
    for area, subissues in ISSUE_TOPICS_BY_AREA.items():
        for subissue in sorted(subissues):
            result = by_pair.get((area, subissue), {})
            rows.append(
                "| "
                + " | ".join(
                    [
                        area,
                        subissue,
                        _pipe(_join(result.get("evidence_ids"))),
                        _pipe(_join(result.get("metric_ids"))),
                        _issue_fact_status(result) if result else "insufficient",
                        _pipe(_text(result.get("findings_summary")) if result else "No formal result found; keep as research gap until searched."),
                    ]
                )
                + " |"
            )
    return rows


def _source_material_rows(source_reviews: dict[str, Any]) -> list[str]:
    rows: list[str] = []
    for idx, review in enumerate(_reviews(source_reviews), start=1):
        rows.extend(
            [
                f"#### Source {idx}",
                f"Source Review ID: {_review_id(review)}",
                f"Source Name: {_review_title(review)}",
                f"Source Type: {_text(review.get('source_type'))}",
                f"Source Date: {_text(review.get('source_date'))}",
                f"Geography: {_text(review.get('geography'))}",
                f"Source Reliability: {_text(review.get('reliability'))}",
                f"Evidence Use Tier: {_text(review.get('evidence_use_tier'))}",
                f"Claim Use Scope: {_text(review.get('claim_use_scope'))}",
                f"Usable As Evidence: {_text(review.get('usable_as_evidence'))}",
                f"URL: {_review_url(review)}",
                f"Locator: {_review_locator(review)}",
                f"Reviewed Excerpt: {_review_excerpt(review)}",
                f"Notes: {_text(review.get('limitations'))}",
                "",
            ]
        )
    return rows


def build_pack(
    *,
    input_card: dict[str, Any],
    scope_pack: dict[str, Any],
    formal_search_plan: dict[str, Any],
    execution_report: dict[str, Any],
    source_reviews: dict[str, Any],
) -> str:
    meta = _meta(input_card, scope_pack)
    scope = _scope_summary(scope_pack)
    lines: list[str] = []
    lines.extend(
        [
            "# industry research evidence pack",
            "",
            "> Evidence binder, not a narrative memo. Preserve source-level extracts, EV/MET candidates, limitations, and issue fact status. Do not write page strategy or slide copy here.",
            "",
            "## Project Meta",
            f"Target Company: {meta['target_company']}",
            f"Transaction Type: {meta['transaction_type']}",
            f"Industry: {meta['industry']}",
            f"Subsector: {meta['subsector']}",
            f"Geography: {meta['geography']}",
            f"Output Language: {meta['language']}",
            f"Prepared Date: {meta['prepared_date']}",
            f"Research As-Of Date: {meta['research_as_of_date']}",
            "User Material Data Cutoff:",
            "research pack Version: evidence_pack_skeleton_v1",
            "",
            "---",
            "",
            "## search plan",
            "search plan Artifact: artifacts/formal_search_plan.json",
            "search plan Validation: artifacts/formal_search_plan_validation.json",
            "Priority Websites (user-specified):",
            "Preferred Domains:",
            "Preferred Source Packs (from templates/source_registry.json):",
            "Default Source Packs Applied (explicit only):",
            "Source Registry Read As Menu Before Search:",
            "Initial Broad Discovery Queries:",
            "Selected Source Packs / Domains:",
            "Added Industry-Specific Domains:",
            "Excluded Packs / Domains:",
            "Source Selection Rationale:",
            "Latest Search Rule:",
            "Peer Set:",
            "Avoid Topics / Sources:",
            "",
            "---",
            "",
            "## Scope Boundary",
            "Engagement Context: pre_mandate_transaction_pitch",
            "Purpose: demonstrate sector understanding, transaction relevance, and selective target context or open questions where supported",
            "Not A Generic Industry Report: yes",
            "Not A Full Consulting Study: yes",
            "Not A Company Deep Dive: yes",
            "Not A Valuation Report: yes",
            "Fixed 8-Slide Structure Preserved: yes",
            "",
            "---",
            "",
            "## Scope Pack And Formal Research Execution Summary",
            "Scope Boundary Check:",
            f"- LLM definition draft: {_pipe((scope_pack.get('llm_definition_draft') if isinstance(scope_pack.get('llm_definition_draft'), str) else 'See artifacts/industry_scope_pack.json'))}",
            "- Scoping search queries used to verify/refine draft: See artifacts/search_log.md broad_discovery entries",
            f"- Relevant market: {_pipe(scope.get('working_market'))}",
            f"- Parent market: {_pipe(scope.get('parent_market'))}",
            f"- Sub-markets: {_pipe(', '.join(_as_list(scope.get('sub_markets'))))}",
            f"- Excluded scope: {_pipe(', '.join(_as_list(scope.get('excluded_scope'))))}",
            "- Ambiguous definitions requiring validation: See artifacts/industry_scope_pack.json",
            "",
            "Project Classification:",
            "- Sector type:",
            f"- Transaction type: {meta['transaction_type']}",
            "- Target business model:",
            "- Likely buyer / investor angle:",
            "- Key transaction question:",
            "",
            "Formal Research Execution Results:",
        ]
    )
    lines.extend(_formal_execution_rows(execution_report))
    lines.extend(
        [
            "",
            "---",
            "",
            "## Formal Research Extracts",
            "> LLM task: for each row, replace the extraction placeholder with a source-faithful fact or metric candidate, then promote only supported items into Evidence Ledger / Metric Reconciliation.",
            "",
        ]
    )
    lines.extend(_formal_extract_rows(execution_report, source_reviews))
    lines.extend(
        [
            "",
            "---",
            "",
            "## IB Issue Fact Inventory",
            "> LLM task: after populating EV/MET ledgers, update Fact Status and IDs. Do not mark sufficient/thin without EV/MET support.",
            "",
        ]
    )
    lines.extend(_issue_inventory_rows(execution_report))
    lines.extend(
        [
            "",
            "Allowed `Fact Status`: `sufficient`, `thin`, `insufficient`, `not_applicable`.",
            "",
            "## Deal Context",
            "",
            "## Target Business Summary",
            "",
            "## Industry Definition",
            f"Working Market: {_pipe(scope.get('working_market'))}",
            f"Parent Market: {_pipe(scope.get('parent_market'))}",
            f"Broader Market: {_pipe(scope.get('broader_market'))}",
            "",
            "## Source Materials",
            "",
            "### Provided Material Sources",
            "",
            "### Online Research Sources",
            "",
        ]
    )
    lines.extend(_source_material_rows(source_reviews))
    lines.extend(
        [
            "---",
            "",
            "## Evidence Promotion Gate",
            "A source can be promoted into the Evidence Ledger only after the exact claim/datapoint has been located in the reviewed source context and its scope, period, geography, unit, and limitation are recorded.",
            "",
            "## Evidence Ledger",
            "> LLM task: populate formal EV rows from Formal Research Extracts only. Do not add lead-only rows here.",
            "",
            "| Evidence ID | Claim / Metric | Claim Scope | Source Name | Source URL | Source Type | Evidence Status | Source Date | Data Period | Source Locator | Raw Excerpt | Reliability | Confidence |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
            "",
            "## Metric Reconciliation",
            "> LLM task: populate MET rows only for quantitative facts that have clean source scope. Add chart_ready notes below the table.",
            "",
            "| Metric Group | Metric ID | Metric Name | Metric Type | Market Definition | Channel Scope | Geography | Data Period | Value | Unit | Comparable With | Parent Metric ID | CAGR Endpoint IDs | Conflict Status | Resolution |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
            "",
            "## Known Pitch-Relevant Observations",
            "- Populate only after EV/MET rows are assigned.",
            "",
            "## Known Risks or Open Questions",
            "- Populate after reviewing insufficient/thin FR rows.",
            "",
            "## Management-Provided Claims To Verify",
            "- Populate from input_card target-specific facts that lack external support.",
            "",
            "## Peer Set",
            "- Populate from competitive_landscape peer_universe / competitor_profiles extracts.",
            "",
            "## Additional Sector-Specific Notes",
            "Insufficient data",
            "",
            "## Research Gap Audit",
            "",
            "### Critical Gaps",
            "- Resolve before validation: populate Evidence Ledger, Metric Reconciliation, and update IB Issue Fact Inventory from Formal Research Extracts.",
            "",
            "### Optional Gaps",
            "- Populate if useful but not blocking.",
            "",
            "### Intentionally Excluded Topics",
            "- Populate with rationale.",
            "",
            "### Metric Consistency Check",
            "- GMV vs revenue:",
            "- Cross-slide repeated metric consistency:",
            "- Target financials consistency:",
            "- User-provided vs external-source discrepancy:",
            "- Chart number consistency:",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-card", required=True)
    parser.add_argument("--scope-pack", required=True)
    parser.add_argument("--formal-search-plan", required=True)
    parser.add_argument("--formal-research-execution-report", required=True)
    parser.add_argument("--source-reviews", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output = build_pack(
        input_card=_load_optional(args.input_card),
        scope_pack=_load_optional(args.scope_pack),
        formal_search_plan=_load_optional(args.formal_search_plan),
        execution_report=_load_optional(args.formal_research_execution_report),
        source_reviews=_load_optional(args.source_reviews),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output, encoding="utf-8")
    print(json.dumps({"is_valid": True, "output": str(output_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
