#!/usr/bin/env python3
"""State-first research graph compiler for IB industry-section research.

This module keeps the existing IB artifact contracts intact while replacing
multi-file hand synchronization with one structured research graph state.
External workers, including an open_deep_research/LangGraph adapter, should
fill `research_graph_state.json`; this compiler emits the canonical artifacts
consumed by QC, Knowledge, Reasoning, and Generation.
"""

from __future__ import annotations

# Runtime scripts can be run directly. Shared helpers remain in runtime
# `scripts/`; production tools live under role scripts; validators live under QC.
import sys as _ib_sys
from pathlib import Path as _IbPath

_IB_ROLE_SCRIPT_DIR = _IbPath(__file__).resolve().parent
_IB_RUNTIME_ROOT = next(
    _p for _p in _IbPath(__file__).resolve().parents
    if (_p / "configs").is_dir() and (_p / "scripts").is_dir()
)
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts" / "_lib"
_IB_ROLE_SCRIPT_DIRS = sorted(_p for _p in (_IB_RUNTIME_ROOT / "scripts").iterdir() if _p.is_dir())
_IB_QC_VALIDATOR_DIRS = sorted((_IB_RUNTIME_ROOT / "scripts" / "qc" / "validators").glob("*"))
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
from datetime import date, datetime
from pathlib import Path
from typing import Any

from issue_taxonomy import ISSUE_TOPICS_BY_AREA
from json_utils import load_json_file
from material_intake_common import classify_access, normalize_source_type
from unit_normalizer import normalize_metric_row


GRAPH_SCHEMA_VERSION = "ib_research_graph_state_v1"
FULL_URL_RE = re.compile(r"https?://[^\s,;，；\]|)）>]+", flags=re.IGNORECASE)
VALID_RESULT_STATUS = {
    "supported",
    "thin",
    "conflicting",
    "not_comparable",
    "insufficient",
    "unavailable_after_research",
}
EVIDENCE_STATUSES = {"supported", "thin", "conflicting", "not_comparable"}
NO_ATTEMPT_TERMINAL_STATUSES = {"not_executed", "not_material", "accounting_only"}
VALID_TERMINAL_STATUSES = {
    "executed_with_evidence",
    "executed_no_usable_source",
    "directional_only",
    "not_executed",
    "not_material",
    "accounting_only",
}
EVIDENCE_DOWNSTREAM_PERMISSIONS = {"may_support_claim", "contextual_only", "not_allowed"}
EVIDENCE_READY_ARCHIVE_STATUSES = {
    "saved_html",
    "saved_text",
    "saved_pdf",
    "manual_verified_excerpt",
    "user_provided",
}
SAVED_SOURCE_ARCHIVE_STATUSES = {"saved_html", "saved_text", "saved_pdf"}
VALID_CAPTURE_METHODS = {
    "full_page_capture",
    "downloaded_pdf",
    "user_provided_file",
    "archived_copy_reviewed",
}
NON_EVIDENCE_DOWNSTREAM_PERMISSIONS = {"contextual_only", "research_backlog_only", "not_allowed"}
RESEARCH_CONTEXT_ARCHIVE_STATUS = "research_context"
AUDITED_METRIC_LEVEL = "audited_metric"
RESEARCH_CONTEXT_LEVEL = "research_context"
ARCHIVE_STATUSES_REQUIRING_SNAPSHOT = {
    "saved_html",
    "saved_text",
    "manual_verified_excerpt",
    "needs_research_verification",
    "search_snippet_only",
    "excerpt_snapshot",
}

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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_optional_json(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    data = load_json_file(p)
    return data if isinstance(data, dict) else {}


def _assert_scope_ready_for_prepare(run_dir: Path, scope_pack: dict[str, Any], *, allow_missing_scope_bootstrap: bool) -> None:
    if allow_missing_scope_bootstrap:
        return
    if not scope_pack:
        raise ValueError(
            "research prepare requires artifacts/industry_scope_pack.json. "
            "Use --allow-missing-scope-bootstrap only for diagnostic/bootstrap runs."
        )
    if scope_pack.get("schema_version") != "industry_scope_pack_v2":
        raise ValueError(
            "research prepare requires industry_scope_pack_v2 before formal planning. "
            "Run industry scoping and boundary QC first."
        )
    qc_path = run_dir / "artifacts" / "industry_boundary_qc.json"
    if not qc_path.exists():
        raise ValueError(
            "research prepare requires artifacts/industry_boundary_qc.json with decision=pass. "
            "Run Boundary QC before formal research planning."
        )
    qc_payload = load_json_file(qc_path)
    if str((qc_payload if isinstance(qc_payload, dict) else {}).get("decision") or "").strip() != "pass":
        raise ValueError("research prepare requires industry_boundary_qc decision=pass before formal research planning.")


def _first_text(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def _unique(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        if text and text not in seen:
            output.append(text)
            seen.add(text)
    return output


def _http_urls(values: list[str]) -> list[str]:
    urls: list[str] = []
    for value in values:
        urls.extend(FULL_URL_RE.findall(_text(value)))
    return _unique(urls)


def _relative_path(run_dir: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(run_dir.resolve()))
    except Exception:
        return str(path)


def _safe_file_stem(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "source"


def _plan_rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for issue in _as_list(plan.get("issue_search_plan")):
        if not isinstance(issue, dict):
            continue
        instructions = [item for item in _as_list(issue.get("search_instructions")) if isinstance(item, dict)]
        if not instructions:
            continue
        for instruction in instructions:
            fs_id = _text(instruction.get("instruction_id"))
            if not fs_id:
                continue
            rows.append(
                {
                    "fs_id": fs_id,
                    "issue_area": _text(issue.get("issue_area")),
                    "subissue": _text(issue.get("subissue")),
                    "research_question": _text(issue.get("research_question")),
                    "priority": _text(issue.get("priority")),
                    "execution_expectation": _text(issue.get("execution_expectation")),
                    "minimum_actual_searches": int(issue.get("minimum_actual_searches") or 0),
                    "coverage_required": issue.get("coverage_required") is True,
                    "purpose": _text(instruction.get("purpose")),
                    "source_hint": _text(instruction.get("source_hint")),
                }
            )
    return rows


def _scope_summary(scope_pack: dict[str, Any]) -> dict[str, Any]:
    value = scope_pack.get("scope_summary")
    return value if isinstance(value, dict) else {}


def _expected_source_type(issue_area: str) -> str:
    return SOURCE_SPECIFIC_HINTS.get(issue_area, "public_search")


def _to_text_query(value: Any) -> str:
    return " ".join(_text(value).split()) if value is not None else ""


def _query_variant(query: str, issue_area: str) -> tuple[str, str]:
    english_query = _to_text_query(query)
    if not english_query:
        english_query = f"LLM_REWRITE_REQUIRED: write an executable English/source-specific query for {issue_area}"
    else:
        english_query = f"LLM_REWRITE_REQUIRED: rewrite research question into executable query: {english_query}"
    chinese_query = f"LLM_REWRITE_REQUIRED: write an executable Chinese/source-specific query for {issue_area}"
    return english_query, chinese_query


def build_coverage_map(plan: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for row in _as_list(plan.get("issue_search_plan")):
        if not isinstance(row, dict):
            continue
        area = _text(row.get("issue_area"))
        instructions = _as_list(row.get("search_instructions"))
        first_instruction = instructions[0] if instructions and isinstance(instructions[0], dict) else {}
        rows.append(
            {
                "issue_area": area,
                "subissue": _text(row.get("subissue")),
                "execution_expectation": _text(row.get("execution_expectation")),
                "minimum_actual_searches": int(row.get("minimum_actual_searches", 0)),
                "execution_rationale": _text(row.get("execution_rationale")),
                "source_specific_query_type": _text(row.get("execution_expectation")),
                "expected_source_type": _expected_source_type(area),
                "research_question": _text(row.get("research_question")),
                "plan_row": _text(first_instruction.get("instruction_id")),
            }
        )
    return {
        "schema_version": "coverage_map_v1",
        "coverage_mode": "canonical_taxonomy_vs_subissues",
        "language": "mixed",
        "scope": "industry_research_scope",
        "rows": rows,
    }


def build_executable_search_batch(plan: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for row in _as_list(plan.get("issue_search_plan")):
        if not isinstance(row, dict):
            continue
        issue_area = _text(row.get("issue_area"))
        subissue = _text(row.get("subissue"))
        research_question = _to_text_query(row.get("research_question"))
        english_query, chinese_query = _query_variant(research_question, issue_area)
        instructions = _as_list(row.get("search_instructions"))
        first_instruction = instructions[0] if instructions and isinstance(instructions[0], dict) else {}
        rows.append(
            {
                "search_instruction_id": _text(first_instruction.get("instruction_id")),
                "issue_area": issue_area,
                "subissue": subissue,
                "research_question": research_question,
                "query_status": "needs_authoring",
                "english_query": english_query,
                "chinese_query": chinese_query,
                "source_specific_query": f"LLM_REWRITE_REQUIRED: write an executable source-specific query for {issue_area}/{subissue}",
                "expected_source_type": _expected_source_type(issue_area),
                "source_hint": _text(first_instruction.get("source_hint")),
                "why_this_search_matters": _text(row.get("execution_rationale")) or _to_text_query(row.get("research_question")),
                "how_result_will_be_used": "Drive source-reviewed evidence for the paired issue/subissue and map it to issue analysis deck rows.",
            }
        )
    return {
        "schema_version": "search_batch_v1",
        "source_language": "mixed",
        "scope": "industry_research_scope",
        "batches": rows,
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


def _industry_specific_research_threads(scope_pack: dict[str, Any]) -> list[dict[str, Any]]:
    threads: list[dict[str, Any]] = []
    raw_items: list[tuple[str, str, str]] = []
    for item in _as_list(scope_pack.get("must_reconcile")):
        if not isinstance(item, dict):
            continue
        raw_items.append(
            (
                _first_text(item.get("topic"), "Scope reconciliation"),
                _first_text(item.get("research_instruction"), item.get("why_it_matters"), "Validate this source-scope difference before using related metrics."),
                _first_text(item.get("why_it_matters"), "Can affect metric comparability or page-claim scope."),
            )
        )
    for item in _as_list(scope_pack.get("boundary_validation_needed")):
        if not isinstance(item, dict):
            continue
        raw_items.append(
            (
                _first_text(item.get("question"), "Boundary validation question"),
                _first_text(item.get("suggested_validation_source"), item.get("why_needed"), "Find authoritative category or market-definition evidence."),
                _first_text(item.get("why_needed"), "Can affect formal research scope."),
            )
        )
    for idx, (topic, research_need, why_it_matters) in enumerate(raw_items[:8], start=1):
        topic_text = topic.lower()
        if any(token in topic_text for token in ("market", "size", "规模", "份额", "口径", "gmv", "revenue")):
            mapped_area = "market_size_growth"
        elif any(token in topic_text for token in ("channel", "platform", "渠道", "平台", "gmv")):
            mapped_area = "demand_customer_logic"
        else:
            mapped_area = "pitch_relevance_target_context"
        threads.append(
            {
                "thread_id": f"IST-{idx:03d}",
                "mapped_issue_area": mapped_area,
                "topic": topic,
                "research_need": research_need,
                "why_it_matters": why_it_matters,
                "query_authoring_artifact": "artifacts/executable_search_batch.json",
            }
        )
    return threads


def build_formal_search_plan(input_card: dict[str, Any], scope_pack: dict[str, Any]) -> dict[str, Any]:
    meta = _meta_from_inputs(input_card=input_card, scope_pack=scope_pack, formal_search_plan={})
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
            issue_search_plan.append(
                {
                    "issue_area": issue_area,
                    "subissue": subissue,
                    "plan_layer": "core_research_thread" if execution_expectation == "deep_search" else "coverage_audit_row",
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
                            "purpose": (
                                f"Find formal evidence for {issue_area}/{subissue}; capture facts, metrics, "
                                "scope, period, source authority, and limitations."
                            ),
                            "search_stage": "formal_research_execution",
                            "source_hint": SOURCE_HINTS_BY_AREA.get(issue_area, "industry report, company disclosure, official or authoritative source"),
                            "query_authoring_artifact": "artifacts/executable_search_batch.json",
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
                "Use the scope pack as a boundary card. Do not convert scope definitions, "
                "reconciliation instructions, or validation questions into findings."
            ),
        },
        "coverage_requirement": {
            "must_cover_all_canonical_subissues": True,
            "canonical_issue_area_count": len(ISSUE_TOPICS_BY_AREA),
            "canonical_subissue_count": sum(len(items) for items in ISSUE_TOPICS_BY_AREA.values()),
            "instruction": (
                "Retain every issue_search_plan row. Author executable query strings only in "
                "artifacts/executable_search_batch.json, not in this coverage plan. The taxonomy is a coverage audit, "
                "not an equal-depth search mandate: execute deep/light rows when material, and explicitly "
                "account for not_material, not_executed, or unavailable rows in formal_research_execution_report.json."
            ),
        },
        "allowed_issue_taxonomy": {area: sorted(subissues) for area, subissues in ISSUE_TOPICS_BY_AREA.items()},
        "planning_instruction": (
            "This plan intentionally covers every canonical issue/subissue to thicken upstream research. "
            "For each row, define the evidence need, source hint, and execution expectation only. "
            "Use industry_specific_research_threads for material scope-specific evidence needs that do not fit cleanly "
            "inside one canonical row. Executable queries belong in artifacts/executable_search_batch.json. Do not write "
            "investment hypotheses, validated findings, slide conclusions, or page plans. A planned FS row is not evidence."
        ),
        "issue_search_plan": issue_search_plan,
        "industry_specific_research_threads": _industry_specific_research_threads(scope_pack),
        "research_discipline": {
            "do_not_generate_hypotheses": True,
            "formal_validation_lives_in": "artifacts/formal_research_execution_report.json",
            "execution_report_inherits_plan_taxonomy": "Copy issue_area, subissue, and research_question from the owning formal_search_plan row.",
            "fs_vs_s_id_discipline": "FS-xxx IDs are planned search instructions. Real searches must be logged as S-xxx attempts.",
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


build_plan = build_formal_search_plan


def _meta_from_inputs(
    *,
    input_card: dict[str, Any],
    scope_pack: dict[str, Any],
    formal_search_plan: dict[str, Any],
) -> dict[str, str]:
    input_meta = input_card.get("meta") if isinstance(input_card.get("meta"), dict) else {}
    scope_meta = scope_pack.get("meta") if isinstance(scope_pack.get("meta"), dict) else {}
    plan_meta = formal_search_plan.get("meta") if isinstance(formal_search_plan.get("meta"), dict) else {}
    today = date.today().isoformat()
    return {
        "target_company": _first_text(input_card.get("target_company"), input_meta.get("target_company"), scope_meta.get("target_company"), plan_meta.get("target_company"), "Unknown target"),
        "transaction_type": _first_text(input_card.get("transaction_type"), input_meta.get("transaction_type"), scope_meta.get("transaction_type"), plan_meta.get("transaction_type"), "pre-mandate pitch"),
        "industry": _first_text(input_card.get("industry"), input_meta.get("industry"), scope_meta.get("industry"), plan_meta.get("industry"), "Unknown industry"),
        "subsector": _first_text(input_card.get("subsector"), input_meta.get("subsector"), scope_meta.get("subsector"), plan_meta.get("subsector")),
        "geography": _first_text(input_card.get("geography"), input_meta.get("geography"), scope_meta.get("geography"), plan_meta.get("geography"), "Unknown geography"),
        "language": _first_text(input_card.get("language"), input_meta.get("language"), scope_meta.get("language"), plan_meta.get("language"), "English"),
        "prepared_date": _first_text(input_meta.get("prepared_date"), scope_meta.get("prepared_date"), plan_meta.get("prepared_date"), today),
        "research_as_of_date": _first_text(input_meta.get("research_as_of_date"), scope_meta.get("research_as_of_date"), plan_meta.get("research_as_of_date"), today),
    }


def init_graph_state(
    *,
    formal_search_plan: dict[str, Any],
    input_card: dict[str, Any] | None = None,
    scope_pack: dict[str, Any] | None = None,
    worker_backend: str = "manual_or_external",
) -> dict[str, Any]:
    input_card = input_card or {}
    scope_pack = scope_pack or {}
    meta = _meta_from_inputs(input_card=input_card, scope_pack=scope_pack, formal_search_plan=formal_search_plan)
    scope_summary = scope_pack.get("scope_summary") if isinstance(scope_pack.get("scope_summary"), dict) else {}
    units: list[dict[str, Any]] = []
    for idx, row in enumerate(_plan_rows(formal_search_plan), start=1):
        units.append(
            {
                "research_unit_id": f"RU-{idx:03d}",
                "issue_area": row["issue_area"],
                "subissue": row["subissue"],
                "fs_ids": [row["fs_id"]],
                "research_question": row["research_question"],
                "priority": row["priority"],
                "execution_expectation": row["execution_expectation"],
                "minimum_actual_searches": row["minimum_actual_searches"],
                "query_authoring_ref": f"artifacts/executable_search_batch.json#{row['fs_id']}",
                "executable_query_status": "needs_authoring",
                "expected_source_type": row["source_hint"],
                "status": "planned",
                "terminal_status": "not_executed",
                "downstream_permission": "research_backlog_only",
                "attempts": [],
                "sources": [],
                "evidence": [],
                "metrics": [],
                "research_context": [],
                "limitations": [],
            }
        )
    return {
        "schema_version": GRAPH_SCHEMA_VERSION,
        "meta": meta,
        "scope_summary": scope_summary,
        "graph_config": {
            "orchestration_model": "state_first_research_graph",
            "worker_backend": worker_backend,
            "open_deep_research_compatible": True,
            "max_concurrent_research_units": 5,
            "state_policy": (
                "Workers fill attempts/sources/evidence/metrics on research_units; "
                "the compiler is the only writer of downstream formal artifacts."
            ),
            "operator_surface": {
                "primary_write_fields": ["research_context", "metrics", "evidence"],
                "internal_tracking_ids": ["FS", "S", "SRC"],
                "policy": "FS/S/SRC IDs are internal traceability. Operators author executable searches in executable_search_batch.json, then write ordinary background to research_context, key numbers to audited metrics, and only hard non-numeric facts to evidence.",
            },
        },
        "research_units": units,
    }


def _next_id(prefix: str, counter: dict[str, int]) -> str:
    counter[prefix] = counter.get(prefix, 0) + 1
    return f"{prefix}-{counter[prefix]:03d}"


def _normalize_source(
    source: dict[str, Any],
    *,
    source_id: str,
    unit: dict[str, Any],
    meta: dict[str, Any],
    default_attempt_ids: list[str],
) -> dict[str, Any]:
    url = _first_text(source.get("url"), source.get("source_url"), source.get("source"), "user-provided")
    source_type = normalize_source_type(source.get("source_type") or source.get("type") or "industry_report")
    reviewed_excerpt = _first_text(
        source.get("reviewed_excerpt"),
        source.get("excerpt"),
        source.get("raw_excerpt"),
        source.get("summary"),
    )
    locator = _first_text(source.get("locator"), source.get("source_locator"), source.get("methodology_locator"), "source section")
    usable = source.get("usable_as_evidence")
    usable_as_evidence = usable if isinstance(usable, bool) else False
    audit_level = _first_text(
        source.get("audit_level"),
        AUDITED_METRIC_LEVEL if usable_as_evidence else RESEARCH_CONTEXT_LEVEL,
    )
    default_archive_status = RESEARCH_CONTEXT_ARCHIVE_STATUS if audit_level == RESEARCH_CONTEXT_LEVEL and not usable_as_evidence else "needs_research_verification"
    archive_status = _first_text(
        source.get("archive_status"),
        source.get("research_archive_status"),
        default_archive_status,
    )
    if archive_status == "manual_verified_excerpt":
        secondary_verification = _text(source.get("secondary_verification"))
        verification_notes = _text(source.get("secondary_verification_notes"))
        research_archive_status = _text(source.get("research_archive_status"))
    elif archive_status == RESEARCH_CONTEXT_ARCHIVE_STATUS:
        secondary_verification = _text(source.get("secondary_verification"))
        verification_notes = _first_text(
            source.get("secondary_verification_notes"),
            "ODR-style research context retained for background only; not promoted as audit-grade evidence.",
        )
        research_archive_status = RESEARCH_CONTEXT_ARCHIVE_STATUS
    else:
        secondary_verification = _first_text(source.get("secondary_verification"), "not_verified")
        verification_notes = _first_text(source.get("secondary_verification_notes"), "Source requires additional verification before evidence promotion.")
        research_archive_status = _first_text(source.get("research_archive_status"), archive_status if archive_status == "manual_verified_excerpt" else "")
    verification_method = _text(source.get("verification_method"))
    capture_method = _text(source.get("capture_method") or source.get("archive_capture_method"))
    if archive_status in SAVED_SOURCE_ARCHIVE_STATUSES and capture_method not in VALID_CAPTURE_METHODS:
        raise ValueError(
            f"{source_id}: archive_status={archive_status} requires explicit capture_method one of "
            f"{sorted(VALID_CAPTURE_METHODS)}; the compiler must not infer saved source status from raw text or excerpt length"
        )
    review_status = _first_text(source.get("review_status"))
    if not review_status:
        review_status = (
            "research_verified_excerpt"
            if (
                archive_status == "manual_verified_excerpt"
                and secondary_verification == "verified"
                and research_archive_status == "manual_verified_excerpt"
                and verification_method
            )
            else "needs_research_secondary_verification"
        )
    return {
        "source_review_id": source_id,
        "url": url,
        "title": _first_text(source.get("title"), source.get("source_name"), source.get("name"), f"{source_id} source"),
        "source_type": source_type,
        "source_access": _first_text(source.get("source_access"), classify_access(source_type, url)),
        "source_access_path": _first_text(source.get("source_access_path"), source.get("archive_path"), url),
        "source_date": _text(source.get("source_date")),
        "geography": _first_text(source.get("geography"), meta.get("geography")),
        "source_reliability": _first_text(source.get("source_reliability"), source.get("reliability"), "reviewed_source"),
        "reliability": _first_text(source.get("reliability"), source.get("source_reliability"), "reviewed_source"),
        "confidence": _first_text(source.get("confidence"), "medium"),
        "fact_type": _first_text(source.get("fact_type"), unit.get("issue_area")),
        "scope": _first_text(source.get("scope"), unit.get("research_question")),
        "audit_level": audit_level,
        "evidence_use_tier": _first_text(source.get("evidence_use_tier"), "core_evidence" if usable_as_evidence else "candidate"),
        "claim_use_scope": _first_text(
            source.get("claim_use_scope"),
            "Use only for source-scoped claims captured in the graph state."
            if usable_as_evidence
            else "Research context only; cannot support key numbers, charts, or slide claims unless promoted to EV/MET.",
        ),
        "usable_as_evidence": usable_as_evidence,
        "source_url": url,
        "source_locator": locator,
        "locator": locator,
        "reviewed_excerpt": reviewed_excerpt,
        "excerpt": reviewed_excerpt,
        "limitations": _first_text(source.get("limitations"), "Use only within stated source scope, period, geography, and methodology."),
        "archive_status": archive_status,
        "archive_path": _text(source.get("archive_path")),
        "raw_archive_path": _text(source.get("raw_archive_path")),
        "raw_archive_text": _text(source.get("raw_archive_text") or source.get("raw_text") or source.get("raw_content")),
        "raw_archive_content_type": _text(source.get("raw_archive_content_type") or source.get("content_type")),
        "archive_unavailable_reason": _text(source.get("archive_unavailable_reason")),
        "excerpt_origin": _first_text(source.get("excerpt_origin"), "opened_page"),
        "verification_method": verification_method,
        "capture_method": capture_method,
        "secondary_verification": secondary_verification,
        "secondary_verification_notes": verification_notes,
        "research_archive_status": research_archive_status,
        "review_status": review_status,
        "search_attempt_ids": [_text(item) for item in _as_list(source.get("search_attempt_ids")) if _text(item)] or default_attempt_ids,
        "evidence_ids": [_text(item) for item in _as_list(source.get("evidence_ids")) if _text(item)],
        "metric_ids": [_text(item) for item in _as_list(source.get("metric_ids")) if _text(item)],
        "data_period": _text(source.get("data_period")),
        "methodology_locator": _text(source.get("methodology_locator")),
    }


def _normalize_research_context(
    context: dict[str, Any],
    *,
    context_id: str,
    unit: dict[str, Any],
    source_ids: list[str],
    attempt_ids: list[str],
) -> dict[str, Any]:
    requested_source_ids = [_text(item) for item in _as_list(context.get("source_review_ids")) if _text(item)]
    if not requested_source_ids and _text(context.get("source_review_id")):
        requested_source_ids = [_text(context.get("source_review_id"))]
    linked_sources = [src_id for src_id in requested_source_ids if src_id in source_ids] or source_ids
    return {
        "context_id": context_id,
        "audit_level": RESEARCH_CONTEXT_LEVEL,
        "issue_area": _first_text(context.get("issue_area"), unit.get("issue_area")),
        "subissue": _first_text(context.get("subissue"), unit.get("subissue")),
        "topic": _first_text(context.get("topic"), context.get("claim"), unit.get("research_question")),
        "summary": _first_text(context.get("summary"), context.get("note"), context.get("finding"), unit.get("findings_summary")),
        "source_review_ids": linked_sources,
        "search_attempt_ids": [_text(item) for item in _as_list(context.get("search_attempt_ids")) if _text(item)] or attempt_ids,
        "confidence": _first_text(context.get("confidence"), "medium"),
        "limitations": _first_text(
            context.get("limitations"),
            "Context-only research note; do not use for key figures, charts, or hard claims without EV/MET promotion.",
        ),
    }


def _normalize_compiled_units(state: dict[str, Any], plan: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    counters: dict[str, int] = {}
    assigned = {
        "attempt_ids": set(),
        "source_ids": set(),
        "evidence_ids": set(),
        "metric_ids": set(),
        "context_ids": set(),
    }
    meta = state.get("meta") if isinstance(state.get("meta"), dict) else {}
    plan_by_fs = {row["fs_id"]: row for row in _plan_rows(plan)}
    compiled_units: list[dict[str, Any]] = []
    all_unit_rows = [item for item in _as_list(state.get("research_units")) if isinstance(item, dict)]

    for unit_index, raw_unit in enumerate(all_unit_rows, start=1):
        fs_ids = [_text(item) for item in _as_list(raw_unit.get("fs_ids")) if _text(item)]
        if not fs_ids:
            fs_id = _text(raw_unit.get("fs_id"))
            fs_ids = [fs_id] if fs_id else []
        plan_row = plan_by_fs.get(fs_ids[0], {}) if fs_ids else {}
        unit = dict(raw_unit)
        unit.setdefault("research_unit_id", f"RU-{unit_index:03d}")
        unit["fs_ids"] = fs_ids
        unit["issue_area"] = _first_text(unit.get("issue_area"), plan_row.get("issue_area"))
        unit["subissue"] = _first_text(unit.get("subissue"), plan_row.get("subissue"))
        unit["research_question"] = _first_text(unit.get("research_question"), plan_row.get("research_question"))
        unit["minimum_actual_searches"] = int(unit.get("minimum_actual_searches") or plan_row.get("minimum_actual_searches") or 0)
        raw_sources = [item for item in _as_list(unit.get("sources")) if isinstance(item, dict)]
        raw_evidence = [item for item in _as_list(unit.get("evidence")) if isinstance(item, dict)]
        raw_metrics = [item for item in _as_list(unit.get("metrics")) if isinstance(item, dict)]
        raw_context = [item for item in _as_list(unit.get("research_context")) if isinstance(item, dict)]
        raw_attempts = [item for item in _as_list(unit.get("attempts")) if isinstance(item, dict)]
        if not raw_attempts and (raw_sources or raw_evidence or raw_metrics or raw_context):
            trace_note = (
                "Research graph state contained sources/evidence/metrics/context without any explicit executed "
                "attempt. Compiler ignored those rows; rerun Research with a real attempts[] entry or explicit "
                "manual-source intake trace before evidence promotion."
            )
            unit["execution_trace_status"] = "missing_attempt_trace"
            unit["limitations"] = _as_list(unit.get("limitations")) + [trace_note]
            raw_sources = []
            raw_evidence = []
            raw_metrics = []
            raw_context = []

        attempts: list[dict[str, Any]] = []
        for raw_attempt in raw_attempts:
            attempt_id = _first_text(raw_attempt.get("search_attempt_id"), raw_attempt.get("attempt_id"), raw_attempt.get("id"))
            if not attempt_id or attempt_id in assigned["attempt_ids"]:
                attempt_id = _next_id("S", counters)
            assigned["attempt_ids"].add(attempt_id)
            attempts.append(
                {
                    "attempt_id": attempt_id,
                    "query": _first_text(raw_attempt.get("query"), raw_attempt.get("executed_query")),
                    "provider": _first_text(raw_attempt.get("provider"), "research_graph"),
                    "domain_constraint": _text(raw_attempt.get("domain_constraint")),
                    "source_pack": _text(raw_attempt.get("source_pack")),
                    "stage": _first_text(raw_attempt.get("stage"), raw_attempt.get("search_stage"), "formal_research_execution"),
                    "fs_ids": [_text(item) for item in _as_list(raw_attempt.get("fs_ids")) if _text(item)] or fs_ids,
                    "mode": _first_text(raw_attempt.get("mode"), "graph_worker"),
                    "dimension": _first_text(raw_attempt.get("dimension"), unit.get("issue_area")),
                    "selected_source_reason": _first_text(raw_attempt.get("selected_source_reason"), "Selected by research graph worker for this FS unit."),
                    "result_count": raw_attempt.get("result_count") if raw_attempt.get("result_count") is not None else len(_http_urls(_as_list(raw_attempt.get("selected_source_urls")))),
                    "selected_source_urls": _http_urls(_as_list(raw_attempt.get("selected_source_urls"))),
                    "opened_reviewed": _first_text(raw_attempt.get("opened_reviewed"), "yes" if raw_sources else "no"),
                    "locator_excerpt": _first_text(raw_attempt.get("locator_excerpt"), raw_attempt.get("source_locator_raw_excerpt"), raw_attempt.get("excerpt")),
                    "excerpt_origin": _first_text(raw_attempt.get("excerpt_origin"), "opened_page" if raw_sources else "unknown"),
                    "secondary_verification": _first_text(raw_attempt.get("secondary_verification"), "not_verified"),
                    "secondary_verification_notes": _text(raw_attempt.get("secondary_verification_notes")),
                    "research_archive_status": _text(raw_attempt.get("research_archive_status")),
                    "source_review_ids": [_text(item) for item in _as_list(raw_attempt.get("source_review_ids")) if _text(item)],
                    "lead_only_sources": [_text(item) for item in _as_list(raw_attempt.get("lead_only_sources")) if _text(item)],
                    "rejected_sources": [_text(item) for item in _as_list(raw_attempt.get("rejected_sources")) if _text(item)],
                    "notes": _first_text(raw_attempt.get("notes"), "Compiled from research_graph_state."),
                }
            )

        attempt_ids = [attempt["attempt_id"] for attempt in attempts]
        sources: list[dict[str, Any]] = []
        for raw_source in raw_sources:
            source_id = _first_text(raw_source.get("source_review_id"), raw_source.get("review_id"), raw_source.get("source_id"), raw_source.get("id"))
            if not source_id or source_id in assigned["source_ids"]:
                source_id = _next_id("SRC", counters)
            assigned["source_ids"].add(source_id)
            sources.append(_normalize_source(raw_source, source_id=source_id, unit=unit, meta=meta, default_attempt_ids=attempt_ids))

        source_ids = [source["source_review_id"] for source in sources]
        for attempt in attempts:
            if not attempt["selected_source_urls"]:
                attempt["selected_source_urls"] = _http_urls([source.get("url", "") for source in sources])
            explicit_source_ids = [source_id for source_id in _as_list(attempt.get("source_review_ids")) if source_id in source_ids]
            attempt["source_review_ids"] = _unique(explicit_source_ids) or source_ids
            archive_paths = [_text(source.get("archive_path")) for source in sources if _text(source.get("archive_path"))]
            attempt["source_archive_paths"] = archive_paths

        context_rows: list[dict[str, Any]] = []
        for raw_ctx in raw_context:
            context_id = _first_text(raw_ctx.get("context_id"), raw_ctx.get("id"))
            if not context_id or context_id in assigned["context_ids"]:
                context_id = _next_id("CTX", counters)
            assigned["context_ids"].add(context_id)
            context_rows.append(
                _normalize_research_context(
                    raw_ctx,
                    context_id=context_id,
                    unit=unit,
                    source_ids=source_ids,
                    attempt_ids=attempt_ids,
                )
            )

        evidence_rows: list[dict[str, Any]] = []
        for raw_ev in raw_evidence:
            ev_id = _first_text(raw_ev.get("evidence_id"), raw_ev.get("id"))
            if not ev_id or ev_id in assigned["evidence_ids"]:
                ev_id = _next_id("EV", counters)
            assigned["evidence_ids"].add(ev_id)
            requested_src_id = _text(raw_ev.get("source_review_id"))
            src_id = requested_src_id if requested_src_id in source_ids else (source_ids[0] if source_ids else "")
            source = next((item for item in sources if item["source_review_id"] == src_id), sources[0] if sources else {})
            evidence_rows.append(
                {
                    "evidence_id": ev_id,
                    "audit_level": _first_text(raw_ev.get("audit_level"), RESEARCH_CONTEXT_LEVEL),
                    "claim_or_metric": _first_text(raw_ev.get("claim_or_metric"), raw_ev.get("claim"), raw_ev.get("metric"), unit.get("findings_summary"), "Source-backed research graph finding."),
                    "claim_scope": _first_text(raw_ev.get("claim_scope"), "industry-level"),
                    "source_review_id": src_id,
                    "source_name": _first_text(raw_ev.get("source_name"), source.get("title")),
                    "source_url": _first_text(raw_ev.get("source_url"), source.get("url")),
                    "source_type": normalize_source_type(raw_ev.get("source_type") or source.get("source_type") or "industry_report"),
                    "evidence_status": _first_text(raw_ev.get("evidence_status"), "primary-reviewed"),
                    "source_date": _text(raw_ev.get("source_date") or source.get("source_date")),
                    "data_period": _text(raw_ev.get("data_period")),
                    "source_locator": _first_text(raw_ev.get("source_locator"), raw_ev.get("locator"), source.get("source_locator")),
                    "raw_excerpt": _first_text(raw_ev.get("raw_excerpt"), raw_ev.get("reviewed_excerpt"), source.get("reviewed_excerpt")),
                    "reliability": _first_text(raw_ev.get("reliability"), source.get("reliability"), "reviewed_source"),
                    "confidence": _first_text(raw_ev.get("confidence"), source.get("confidence"), "medium"),
                }
            )

        metric_rows: list[dict[str, Any]] = []
        unit_conversion_audit: list[dict[str, Any]] = []
        for raw_metric in raw_metrics:
            met_id = _first_text(raw_metric.get("metric_id"), raw_metric.get("id"))
            if not met_id or met_id in assigned["metric_ids"]:
                met_id = _next_id("MET", counters)
            assigned["metric_ids"].add(met_id)
            requested_src_id = _text(raw_metric.get("source_review_id"))
            src_id = requested_src_id if requested_src_id in source_ids else (source_ids[0] if source_ids else "")
            source = next((item for item in sources if item["source_review_id"] == src_id), sources[0] if sources else {})
            metric = {
                "audit_level": AUDITED_METRIC_LEVEL,
                "metric_group": _first_text(raw_metric.get("metric_group"), unit.get("issue_area")),
                "metric_id": met_id,
                "metric_name": _first_text(raw_metric.get("metric_name"), raw_metric.get("name"), raw_metric.get("claim_or_metric"), "Research graph metric"),
                "metric_type": _first_text(raw_metric.get("metric_type"), "market_size"),
                "market_definition": _first_text(raw_metric.get("market_definition"), unit.get("research_question"), "Source-defined market"),
                "channel_scope": _first_text(raw_metric.get("channel_scope"), "all_channel"),
                "geography": _first_text(raw_metric.get("geography"), meta.get("geography")),
                "data_period": _first_text(raw_metric.get("data_period"), raw_metric.get("period"), "latest"),
                "value": raw_metric.get("value"),
                "unit": _text(raw_metric.get("unit")),
                "comparable_with": _text(raw_metric.get("comparable_with")),
                "parent_metric_id": _text(raw_metric.get("parent_metric_id")),
                "cagr_endpoint_ids": _text(raw_metric.get("cagr_endpoint_ids")),
                "conflict_status": _first_text(raw_metric.get("conflict_status"), "single-source"),
                "resolution": _first_text(raw_metric.get("resolution"), "Use only with the source definition, period, geography, and methodology captured in this row."),
                "chart_ready": raw_metric.get("chart_ready") if isinstance(raw_metric.get("chart_ready"), bool) else True,
                "source_review_id": src_id,
                "source_name": _first_text(raw_metric.get("source_name"), source.get("title")),
                "source_url": _first_text(raw_metric.get("source_url"), source.get("url")),
                "source_access_path": _first_text(raw_metric.get("source_access_path"), source.get("source_access_path"), source.get("archive_path")),
                "source_type": normalize_source_type(raw_metric.get("source_type") or source.get("source_type") or "industry_report"),
                "source_date": _first_text(raw_metric.get("source_date"), source.get("source_date")),
                "source_locator": _first_text(raw_metric.get("source_locator"), raw_metric.get("locator"), source.get("source_locator")),
                "raw_excerpt": _first_text(raw_metric.get("raw_excerpt"), raw_metric.get("reviewed_excerpt"), source.get("reviewed_excerpt")),
                "audit_note": _first_text(raw_metric.get("audit_note"), raw_metric.get("remarks"), raw_metric.get("notes"), raw_metric.get("resolution"), "Use only with the captured source scope and limitations."),
            }
            normalized_metric, audit = normalize_metric_row(metric)
            unit_conversion_audit.append({"metric_id": met_id, **audit})
            metric_rows.append(normalized_metric)

        for source in sources:
            source["evidence_ids"] = _unique(
                source.get("evidence_ids", [])
                + [ev["evidence_id"] for ev in evidence_rows if ev.get("source_review_id") == source["source_review_id"]]
            )
            source["metric_ids"] = _unique(
                source.get("metric_ids", [])
                + [met["metric_id"] for met in metric_rows if met.get("source_review_id") == source["source_review_id"]]
            )

        unit["attempts"] = attempts
        unit["sources"] = sources
        unit["evidence"] = evidence_rows
        unit["metrics"] = metric_rows
        unit["research_context"] = context_rows
        unit["unit_conversion_audit"] = unit_conversion_audit
        compiled_units.append(unit)
    return compiled_units, {"assigned_counts": counters}


def _search_log(attempts: list[dict[str, Any]], *, research_as_of_date: str) -> str:
    lines = [
        "# Search Log",
        "",
        "> Written incrementally during the research phase. `FS-xxx` IDs are planned search instructions; `S-xxx` IDs are real executed search attempts.",
        "",
        "## Research Configuration",
        "",
        f"Research As-Of Date: {research_as_of_date}",
        "",
        "---",
        "",
        "## Search Attempts",
    ]
    for attempt in attempts:
        number = int(re.search(r"\d+", attempt["attempt_id"]).group(0))
        lines.extend(
            [
                "",
                f"### Search {number}",
                f"- **Query**: {_text(attempt.get('query'))}",
                f"- **Provider**: {_text(attempt.get('provider'))}",
                f"- **Site / Domain Constraint**: {_text(attempt.get('domain_constraint'))}",
                f"- **Source Pack**: {_text(attempt.get('source_pack'))}",
                f"- **Search Stage**: {_text(attempt.get('stage'))}",
                f"- **Search Instruction IDs**: {', '.join(_as_list(attempt.get('fs_ids')))}",
                f"- **Mode**: {_text(attempt.get('mode'))}",
                f"- **Dimension**: {_text(attempt.get('dimension'))}",
                f"- **Selected Source Reason**: {_text(attempt.get('selected_source_reason'))}",
                f"- **Result Count**: {attempt.get('result_count') if attempt.get('result_count') is not None else ''}",
                f"- **Selected Sources**: {', '.join(_as_list(attempt.get('selected_source_urls')))}",
                f"- **Opened / Reviewed**: {_text(attempt.get('opened_reviewed'))}",
                f"- **Source Locator / Raw Excerpt**: {_text(attempt.get('locator_excerpt'))}",
                f"- **Excerpt Origin**: {_text(attempt.get('excerpt_origin'))}",
                f"- **Secondary Verification**: {_text(attempt.get('secondary_verification'))}",
                f"- **Secondary Verification Notes**: {_text(attempt.get('secondary_verification_notes'))}",
                f"- **Research Archive Status**: {_text(attempt.get('research_archive_status'))}",
                f"- **Source Review IDs**: {', '.join(_as_list(attempt.get('source_review_ids')))}",
                f"- **Source Archive IDs / Paths**: {', '.join(_as_list(attempt.get('source_archive_paths')))}",
                f"- **Lead-only Sources**: {', '.join(_as_list(attempt.get('lead_only_sources')))}",
                f"- **Rejected Sources (with reason)**: {'; '.join(_as_list(attempt.get('rejected_sources')))}",
                f"- **Notes**: {_text(attempt.get('notes'))}",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _raw_archive_suffix(content_type: str) -> str:
    lowered = content_type.lower()
    if "html" in lowered:
        return ".html"
    if "json" in lowered:
        return ".json"
    return ".txt"


def _archive_snapshot(source: dict[str, Any], *, captured_at: str, archive_status: str, raw_archive_path: str = "") -> str:
    lines = [
        f"# {source['source_review_id']} Source Archive Snapshot",
        "",
        f"- Source Review ID: {source['source_review_id']}",
        f"- Title: {_text(source.get('title'))}",
        f"- URL: {_text(source.get('url'))}",
        f"- Captured At: {captured_at}",
        f"- Archive Status: {archive_status}",
        f"- Locator: {_text(source.get('locator'))}",
        f"- Evidence IDs: {', '.join(_as_list(source.get('evidence_ids')))}",
        f"- Limitations: {_text(source.get('limitations'))}",
    ]
    if raw_archive_path:
        lines.append(f"- Raw Archive Path: {raw_archive_path}")
    lines.extend(
        [
            f"- Excerpt Origin: {_text(source.get('excerpt_origin'))}",
            f"- Capture Method: {_text(source.get('capture_method'))}",
            f"- Verification Method: {_text(source.get('verification_method'))}",
            f"- Secondary Verification: {_text(source.get('secondary_verification'))}",
            f"- Secondary Verification Notes: {_text(source.get('secondary_verification_notes'))}",
            f"- Research Archive Status: {_text(source.get('research_archive_status'))}",
            "",
            "## Reviewed Excerpt / Faithful Paraphrase",
            "",
            _text(source.get("reviewed_excerpt")),
            "",
            "## Archive Note",
            "",
            "Compiled from research_graph_state. It preserves the selected URL, locator/excerpt/paraphrase, search linkage, raw archive path when available, and limitations for downstream Knowledge/QC review.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_archive_index(
    *,
    sources: list[dict[str, Any]],
    run_dir: Path,
    archive_dir: Path,
    captured_at: str,
) -> dict[str, Any]:
    archive_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    for source in sources:
        archive_status = _text(source.get("archive_status")) or "needs_research_verification"
        archive_path = _text(source.get("archive_path"))
        raw_archive_path = _text(source.get("raw_archive_path"))
        raw_archive_text = _text(source.get("raw_archive_text"))
        if raw_archive_text and not raw_archive_path:
            raw_dir = archive_dir / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            raw_file = raw_dir / f"{_safe_file_stem(source['source_review_id'])}_raw{_raw_archive_suffix(_text(source.get('raw_archive_content_type')))}"
            if not raw_file.exists():
                raw_file.write_text(raw_archive_text, encoding="utf-8")
            raw_archive_path = _relative_path(run_dir, raw_file)
            source["raw_archive_path"] = raw_archive_path
        if archive_status in ARCHIVE_STATUSES_REQUIRING_SNAPSHOT:
            if not archive_path:
                archive_file = archive_dir / f"{_safe_file_stem(source['source_review_id'])}.md"
                archive_path = _relative_path(run_dir, archive_file)
                source["archive_path"] = archive_path
            else:
                archive_file = run_dir / archive_path if not Path(archive_path).is_absolute() else Path(archive_path)
            if not archive_file.exists():
                archive_file.parent.mkdir(parents=True, exist_ok=True)
                archive_file.write_text(
                    _archive_snapshot(
                        source,
                        captured_at=captured_at,
                        archive_status=archive_status,
                        raw_archive_path=raw_archive_path,
                    ),
                    encoding="utf-8",
                )
        entries.append(
            {
                "source_review_id": source["source_review_id"],
                "url": _text(source.get("url")),
                "title": _text(source.get("title")),
                "archive_status": archive_status,
                "archive_path": archive_path,
                "raw_archive_path": raw_archive_path,
                "captured_at": captured_at,
                "source_type": normalize_source_type(source.get("source_type")),
                "search_attempt_ids": _as_list(source.get("search_attempt_ids")),
                "evidence_ids": _as_list(source.get("evidence_ids")),
                "metric_ids": _as_list(source.get("metric_ids")),
                "audit_level": _text(source.get("audit_level")),
                "evidence_use_tier": _text(source.get("evidence_use_tier")),
                "usable_as_evidence": source.get("usable_as_evidence") is True,
                "review_status": _text(source.get("review_status")),
                "claim_use_scope": _text(source.get("claim_use_scope")),
                "locator": _text(source.get("locator")),
                "reviewed_excerpt": _text(source.get("reviewed_excerpt"))[:4000],
                "archive_unavailable_reason": _text(source.get("archive_unavailable_reason")),
                "excerpt_origin": _text(source.get("excerpt_origin")),
                "capture_method": _text(source.get("capture_method")),
                "verification_method": _text(source.get("verification_method")),
                "secondary_verification": _text(source.get("secondary_verification")),
                "secondary_verification_notes": _text(source.get("secondary_verification_notes")),
                "research_archive_status": _text(source.get("research_archive_status")),
                "source_date": _text(source.get("source_date")),
                "geography": _text(source.get("geography")),
                "data_period": _text(source.get("data_period")),
                "methodology_locator": _text(source.get("methodology_locator")),
            }
        )
    return {
        "schema_version": "source_archive_index_v1",
        "generated_at": captured_at,
        "policy": "Compiled from research_graph_state. Audited EV/MET sources receive reviewable snapshots or raw archive paths; research_context sources retain URL/title/summary without audit-grade snapshot requirements.",
        "entries": entries,
    }


def _terminal_status(unit: dict[str, Any], *, attempts: list[dict[str, Any]], evidence_ids: list[str], metric_ids: list[str], source_ids: list[str], plan_row: dict[str, Any]) -> tuple[str, str, str]:
    raw_terminal = _text(unit.get("terminal_status"))
    raw_status = _text(unit.get("status"))
    raw_permission = _text(unit.get("downstream_permission"))
    explicit_evidence_authorization = (
        raw_terminal == "executed_with_evidence"
        and raw_status in EVIDENCE_STATUSES
        and raw_permission in EVIDENCE_DOWNSTREAM_PERMISSIONS
        and source_ids
        and attempts
        and (evidence_ids or metric_ids)
    )
    if explicit_evidence_authorization:
        terminal = raw_terminal
    elif raw_terminal in {"executed_no_usable_source", "directional_only"} and attempts:
        terminal = raw_terminal
    elif raw_terminal in {"not_material", "accounting_only"}:
        terminal = raw_terminal
    elif source_ids and attempts and (evidence_ids or metric_ids):
        terminal = "executed_no_usable_source"
    elif attempts and _as_list(unit.get("research_context")):
        terminal = "directional_only"
    elif attempts:
        terminal = "executed_no_usable_source"
    elif _text(plan_row.get("execution_expectation")) == "accounting_only":
        terminal = "accounting_only"
    else:
        terminal = "not_executed"

    if terminal == "executed_with_evidence":
        status = raw_status
        permission = raw_permission
    elif terminal == "directional_only":
        status = raw_status if raw_status in VALID_RESULT_STATUS else "thin"
        permission = raw_permission if raw_permission in NON_EVIDENCE_DOWNSTREAM_PERMISSIONS else "contextual_only"
    elif terminal == "executed_no_usable_source":
        status = raw_status if raw_status in VALID_RESULT_STATUS else "insufficient"
        if status in EVIDENCE_STATUSES and not source_ids:
            status = "insufficient"
        permission = raw_permission if raw_permission in NON_EVIDENCE_DOWNSTREAM_PERMISSIONS else "research_backlog_only"
    else:
        status = raw_status if raw_status in {"insufficient", "unavailable_after_research"} else "insufficient"
        permission = raw_permission if raw_permission in NON_EVIDENCE_DOWNSTREAM_PERMISSIONS else "research_backlog_only"
    return status, terminal, permission


def _compile_execution_report(
    *,
    plan: dict[str, Any],
    units: list[dict[str, Any]],
    search_log_ref: str,
    captured_at: str,
) -> dict[str, Any]:
    rows = _plan_rows(plan)
    units_by_fs: dict[str, dict[str, Any]] = {}
    for unit in units:
        for fs_id in _as_list(unit.get("fs_ids")):
            units_by_fs.setdefault(_text(fs_id), unit)

    issue_results: list[dict[str, Any]] = []
    fs_status_rows: list[dict[str, Any]] = []
    covered_areas: set[str] = set()
    thin_or_unresolved: list[str] = []
    unavailable: list[str] = []
    all_attempt_ids: set[str] = set()

    for idx, row in enumerate(rows, start=1):
        unit = units_by_fs.get(row["fs_id"], {})
        attempts = [item for item in _as_list(unit.get("attempts")) if isinstance(item, dict)]
        source_ids = [source["source_review_id"] for source in _as_list(unit.get("sources")) if isinstance(source, dict)]
        evidence_ids = [ev["evidence_id"] for ev in _as_list(unit.get("evidence")) if isinstance(ev, dict)]
        metric_ids = [met["metric_id"] for met in _as_list(unit.get("metrics")) if isinstance(met, dict)]
        attempt_ids = [attempt["attempt_id"] for attempt in attempts]
        all_attempt_ids.update(attempt_ids)
        status, terminal, permission = _terminal_status(
            unit,
            attempts=attempts,
            evidence_ids=evidence_ids,
            metric_ids=metric_ids,
            source_ids=source_ids,
            plan_row=row,
        )
        missing_explicit_evidence_authorization = (
            bool(source_ids)
            and bool(attempts)
            and bool(evidence_ids or metric_ids)
            and terminal != "executed_with_evidence"
        )
        selected_urls = _http_urls(
            [url for attempt in attempts for url in _as_list(attempt.get("selected_source_urls"))]
            + [source.get("url", "") for source in _as_list(unit.get("sources")) if isinstance(source, dict)]
        )
        limitations = [_text(item) for item in _as_list(unit.get("limitations")) if _text(item)]
        if not limitations:
            if terminal == "executed_with_evidence":
                limitations = ["Use only within source-defined scope, period, geography, and methodology."]
            elif missing_explicit_evidence_authorization:
                limitations = [
                    "Candidate EV/MET rows exist in research_graph_state, but Research did not explicitly authorize terminal_status/status/downstream_permission for evidence use."
                ]
            else:
                limitations = ["No usable formal evidence has been compiled for this planned FS row."]
        if terminal == "executed_with_evidence":
            findings = _first_text(unit.get("findings_summary"), f"Research graph compiled reviewed evidence for {row['issue_area']}/{row['subissue']}.")
            handling = _first_text(unit.get("research_pack_handling"), "Promote the linked EV/MET rows with their source scope and limitations.")
            covered_areas.add(row["issue_area"])
            if status != "supported":
                thin_or_unresolved.append(f"{row['issue_area']}/{row['subissue']}")
        else:
            findings = _first_text(
                unit.get("findings_summary"),
                (
                    f"Candidate evidence exists for {row['issue_area']}/{row['subissue']}, but explicit Research authorization is missing."
                    if missing_explicit_evidence_authorization
                    else f"No usable promoted evidence has been compiled for {row['issue_area']}/{row['subissue']}."
                ),
            )
            handling = _first_text(
                unit.get("research_pack_handling"),
                (
                    "Keep candidate EV/MET rows out of Knowledge promotion until Research explicitly sets terminal_status, status, and downstream_permission."
                    if missing_explicit_evidence_authorization
                    else "Keep as a research gap/backlog; do not use as deck evidence until a reviewed source is compiled."
                ),
            )
            unavailable.append(f"{row['issue_area']}/{row['subissue']}")
        result_id = f"FR-{idx:03d}"
        if terminal in NO_ATTEMPT_TERMINAL_STATUSES:
            attempt_ids = []
            source_ids = []
            evidence_ids = []
            metric_ids = []
            selected_urls = []
        elif terminal != "executed_with_evidence":
            evidence_ids = []
            metric_ids = []
        result = {
            "result_id": result_id,
            "issue_area": row["issue_area"],
            "subissue": row["subissue"],
            "research_question": row["research_question"],
            "status": status,
            "terminal_status": terminal,
            "downstream_permission": permission,
            "minimum_actual_searches": row["minimum_actual_searches"],
            "actual_search_attempt_count": len(attempt_ids),
            "search_instruction_ids": [row["fs_id"]],
            "search_attempt_ids": attempt_ids,
            "source_discovery_attempt_ids": [],
            "selected_source_urls": selected_urls,
            "source_review_ids": source_ids,
            "evidence_ids": evidence_ids,
            "metric_ids": metric_ids,
            "findings_summary": findings,
            "limitations": limitations,
            "research_pack_handling": handling,
        }
        issue_results.append(result)
        fs_status_rows.append(
            {
                "fs_id": row["fs_id"],
                "result_id": result_id,
                "issue_area": row["issue_area"],
                "subissue": row["subissue"],
                "execution_expectation": row["execution_expectation"],
                "minimum_actual_searches": row["minimum_actual_searches"],
                "actual_search_attempt_ids": attempt_ids,
                "actual_search_attempt_count": len(attempt_ids),
                "terminal_status": terminal,
                "downstream_permission": permission,
            }
        )

    return {
        "schema_version": "formal_research_execution_report_v1",
        "formal_research_completed_at": captured_at,
        "search_log": search_log_ref,
        "issue_results": issue_results,
        "coverage_summary": {
            "planned_fs_rows": len(rows),
            "actual_search_attempts": len(all_attempt_ids),
            "fs_rows_accounted": len(fs_status_rows),
            "fs_rows_executed_with_evidence": sum(1 for item in fs_status_rows if item["terminal_status"] == "executed_with_evidence"),
            "fs_rows_executed_without_evidence": sum(1 for item in fs_status_rows if item["terminal_status"] == "executed_no_usable_source"),
            "fs_rows_not_executed": sum(1 for item in fs_status_rows if item["terminal_status"] in {"not_executed", "accounting_only", "not_material"}),
            "high_priority_rows_below_minimum": sorted(
                item["fs_id"] for item in fs_status_rows if item["actual_search_attempt_count"] < item["minimum_actual_searches"]
            ),
            "covered_issue_areas": sorted(covered_areas),
            "thin_or_unresolved_subissues": sorted(set(thin_or_unresolved)),
            "not_available_after_research": sorted(set(unavailable)),
        },
        "fs_row_execution_status": fs_status_rows,
        "unresolved_issues": sorted(set(unavailable)),
        "compiler_note": "Generated by ib_research_graph.py from research_graph_state.json.",
    }


def build_coverage_accounting(report: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    counters = {
        "planned": 0,
        "executed": 0,
        "not_executed": 0,
        "not_material": 0,
        "executed_with_evidence": 0,
        "executed_no_usable_source": 0,
    }
    for item in _as_list(report.get("fs_row_execution_status")):
        if not isinstance(item, dict):
            continue
        terminal_status = _text(item.get("terminal_status"))
        counters["planned"] += 1
        if terminal_status == "executed_with_evidence":
            coverage_status = "executed"
            counters["executed"] += 1
            counters["executed_with_evidence"] += 1
        elif terminal_status == "executed_no_usable_source":
            coverage_status = "executed"
            counters["executed"] += 1
            counters["executed_no_usable_source"] += 1
        elif terminal_status in {"accounting_only", "not_material"}:
            coverage_status = "not_material"
            counters["not_material"] += 1
        else:
            coverage_status = "not_executed"
            counters["not_executed"] += 1
        rows.append(
            {
                "fs_id": _text(item.get("fs_id")),
                "result_id": _text(item.get("result_id")),
                "issue_area": _text(item.get("issue_area")),
                "subissue": _text(item.get("subissue")),
                "execution_expectation": _text(item.get("execution_expectation")),
                "minimum_actual_searches": int(item.get("minimum_actual_searches") or 0),
                "actual_search_attempt_count": int(item.get("actual_search_attempt_count") or 0),
                "actual_search_attempt_ids": _as_list(item.get("actual_search_attempt_ids")),
                "terminal_status": terminal_status,
                "coverage_status": coverage_status,
                "downstream_permission": _text(item.get("downstream_permission")),
                "can_support_evidence": terminal_status == "executed_with_evidence",
                "can_support_deck_claim": (
                    terminal_status == "executed_with_evidence"
                    and _text(item.get("downstream_permission")) == "may_support_claim"
                ),
            }
        )
    return {
        "schema_version": "coverage_accounting_v1",
        "source_artifact": "artifacts/formal_research_execution_report.json",
        "summary": counters,
        "rows": rows,
        "policy": {
            "planned_rows_are_not_evidence": True,
            "not_executed_rows_cannot_support_research_pack": True,
            "not_material_rows_are_accounting_only": True,
            "knowledge_db_must_be_built_after_execution_compile": True,
        },
    }


def _archive_capture_reviews_artifact(sources: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "archive_capture_reviews_v1",
        "source_of_truth": "artifacts/research_evidence_db.json",
        "policy": "Archive/capture review export from research_graph_state. Knowledge LLM records final source usability and claim-use limits inside research_evidence_db.json.",
        "reviews": sources,
    }


def compile_graph_state(
    *,
    state: dict[str, Any],
    formal_search_plan: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:
    if state.get("schema_version") != GRAPH_SCHEMA_VERSION:
        raise ValueError(f"research graph state schema_version must be {GRAPH_SCHEMA_VERSION}")
    run_dir = Path(run_dir)
    artifacts = run_dir / "artifacts"
    archive_dir = artifacts / "source_archive"
    captured_at = datetime.now().astimezone().isoformat(timespec="seconds")
    units, normalization_meta = _normalize_compiled_units(state, formal_search_plan)
    attempts = [attempt for unit in units for attempt in _as_list(unit.get("attempts")) if isinstance(attempt, dict)]
    sources = [source for unit in units for source in _as_list(unit.get("sources")) if isinstance(source, dict)]
    archive_index = _write_archive_index(sources=sources, run_dir=run_dir, archive_dir=archive_dir, captured_at=captured_at)
    archive_path_by_source = {
        entry["source_review_id"]: entry.get("archive_path", "")
        for entry in _as_list(archive_index.get("entries"))
        if isinstance(entry, dict)
    }
    for source in sources:
        source["archive_path"] = archive_path_by_source.get(source["source_review_id"], _text(source.get("archive_path")))
    for attempt in attempts:
        attempt["source_archive_paths"] = [
            archive_path_by_source.get(source_id, "")
            for source_id in _as_list(attempt.get("source_review_ids"))
            if archive_path_by_source.get(source_id, "")
        ]
    search_log_text = _search_log(attempts, research_as_of_date=_text(state.get("meta", {}).get("research_as_of_date")) if isinstance(state.get("meta"), dict) else date.today().isoformat())
    execution_report = _compile_execution_report(
        plan=formal_search_plan,
        units=units,
        search_log_ref="artifacts/search_log.md",
        captured_at=captured_at,
    )
    coverage_accounting = build_coverage_accounting(execution_report)
    archive_capture_reviews = _archive_capture_reviews_artifact(sources)
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "search_log.md").write_text(search_log_text, encoding="utf-8")
    _write_json(archive_dir / "source_archive_index.json", archive_index)
    _write_json(artifacts / "archive_capture_reviews.json", archive_capture_reviews)
    _write_json(artifacts / "formal_research_execution_report.json", execution_report)
    _write_json(artifacts / "coverage_accounting.json", coverage_accounting)
    return {
        "is_valid": True,
        "run_dir": str(run_dir),
        "artifacts": {
            "search_log": str(artifacts / "search_log.md"),
            "source_archive_index": str(archive_dir / "source_archive_index.json"),
            "archive_capture_reviews": str(artifacts / "archive_capture_reviews.json"),
            "formal_research_execution_report": str(artifacts / "formal_research_execution_report.json"),
            "coverage_accounting": str(artifacts / "coverage_accounting.json"),
        },
        "compiled_counts": {
            "research_units": len(units),
            "attempts": len(attempts),
            "sources": len(sources),
            "evidence_rows": sum(len(_as_list(unit.get("evidence"))) for unit in units),
            "metric_rows": sum(len(_as_list(unit.get("metrics"))) for unit in units),
            "research_context_rows": sum(len(_as_list(unit.get("research_context"))) for unit in units),
        },
        "next_step": "Run build_research_evidence_db.py to create the Knowledge skeleton, then have Knowledge LLM author research_evidence_db.json and export industry_research_pack.md.",
        "normalization_meta": normalization_meta,
    }


def prepare_research_graph(
    *,
    input_card: dict[str, Any],
    scope_pack: dict[str, Any],
    run_dir: Path,
    worker_backend: str = "manual_or_external",
    formal_search_plan_path: Path | None = None,
    coverage_map_path: Path | None = None,
    search_batch_path: Path | None = None,
    state_path: Path | None = None,
    allow_missing_scope_bootstrap: bool = False,
) -> dict[str, Any]:
    """Build the coverage plan, executable query workbench, and graph state.

    This is the operator-facing research preparation step. Normal workflows
    prepare the research graph in one command, then compile from the edited
    state after research execution.
    """

    run_dir = Path(run_dir)
    artifacts = run_dir / "artifacts"
    _assert_scope_ready_for_prepare(
        run_dir,
        scope_pack,
        allow_missing_scope_bootstrap=allow_missing_scope_bootstrap,
    )
    plan = build_formal_search_plan(input_card, scope_pack)
    coverage_map = build_coverage_map(plan)
    executable_search_batch = build_executable_search_batch(plan)
    state = init_graph_state(
        formal_search_plan=plan,
        input_card=input_card,
        scope_pack=scope_pack,
        worker_backend=worker_backend,
    )
    formal_search_plan_path = formal_search_plan_path or artifacts / "formal_search_plan.json"
    coverage_map_path = coverage_map_path or artifacts / "coverage_map.json"
    search_batch_path = search_batch_path or artifacts / "executable_search_batch.json"
    state_path = state_path or artifacts / "research_graph_state.json"
    _write_json(formal_search_plan_path, plan)
    _write_json(coverage_map_path, coverage_map)
    _write_json(search_batch_path, executable_search_batch)
    _write_json(state_path, state)
    return {
        "is_valid": True,
        "run_dir": str(run_dir),
        "artifacts": {
            "formal_search_plan": str(formal_search_plan_path),
            "coverage_map": str(coverage_map_path),
            "executable_search_batch": str(search_batch_path),
            "research_graph_state": str(state_path),
        },
        "issue_search_plan_count": len(plan["issue_search_plan"]),
        "research_unit_count": len(state["research_units"]),
        "operator_note": "Edit executable queries and fill research_graph_state.json with research_context, evidence, and audited metrics before compile.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare", help="Prepare formal_search_plan, search batch, and research_graph_state in one operator-facing step.")
    prepare_parser.add_argument("--run-dir", required=True)
    prepare_parser.add_argument("--input-card")
    prepare_parser.add_argument("--scope-pack")
    prepare_parser.add_argument("--worker-backend", default="manual_or_external")
    prepare_parser.add_argument("--formal-search-plan")
    prepare_parser.add_argument("--coverage-map")
    prepare_parser.add_argument("--search-batch")
    prepare_parser.add_argument("--state")
    prepare_parser.add_argument(
        "--allow-missing-scope-bootstrap",
        action="store_true",
        help="Diagnostic/bootstrap mode only: allow prepare without industry_scope_pack_v2 and boundary QC pass.",
    )

    compile_parser = subparsers.add_parser("compile", help="Compile research_graph_state.json into canonical research artifacts.")
    compile_parser.add_argument("--state", required=True)
    compile_parser.add_argument("--formal-search-plan", required=True)
    compile_parser.add_argument("--run-dir", required=True)

    args = parser.parse_args()
    if args.command == "prepare":
        run_dir = Path(args.run_dir)
        input_card_path = Path(args.input_card) if args.input_card else run_dir / "input_card.json"
        scope_pack_path = Path(args.scope_pack) if args.scope_pack else run_dir / "artifacts" / "industry_scope_pack.json"
        result = prepare_research_graph(
            input_card=_load_optional_json(input_card_path),
            scope_pack=_load_optional_json(scope_pack_path),
            run_dir=run_dir,
            worker_backend=args.worker_backend,
            formal_search_plan_path=Path(args.formal_search_plan) if args.formal_search_plan else None,
            coverage_map_path=Path(args.coverage_map) if args.coverage_map else None,
            search_batch_path=Path(args.search_batch) if args.search_batch else None,
            state_path=Path(args.state) if args.state else None,
            allow_missing_scope_bootstrap=args.allow_missing_scope_bootstrap,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    state = load_json_file(Path(args.state))
    plan = load_json_file(Path(args.formal_search_plan))
    result = compile_graph_state(state=state, formal_search_plan=plan, run_dir=Path(args.run_dir))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
