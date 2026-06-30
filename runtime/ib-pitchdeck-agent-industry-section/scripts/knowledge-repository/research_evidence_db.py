"""Internal pipeline helper for the Knowledge evidence workspace.

The JSON database is the Knowledge LLM-authored evidence record. This module
prepares a candidate workspace, validates structure, and exports the readable
research pack. It does not judge source quality or promote evidence on its own.
"""

from __future__ import annotations

# Runtime scripts can be run directly. Shared helpers remain in runtime
# `scripts/`; production tools live under role scripts; validators live under QC.
import sys as _ib_sys
from pathlib import Path as _IbPath
_ib_sys.dont_write_bytecode = True
_IB_ROLE_SCRIPT_DIR = _IbPath(__file__).resolve().parent
_IB_RUNTIME_ROOT = next(
    _p for _p in _IbPath(__file__).resolve().parents
    if (_p / 'configs').is_dir() and (_p / 'scripts').is_dir()
)
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts" / "_lib"
_IB_ROLE_SCRIPT_DIRS = sorted(_p for _p in (_IB_RUNTIME_ROOT / 'scripts').iterdir() if _p.is_dir())
_IB_QC_VALIDATOR_DIRS = sorted((_IB_RUNTIME_ROOT / 'scripts' / 'qc' / 'validators').glob('*'))
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

from runtime_utils import is_material_type, load_json_file, normalize_source_type
EV_RE = re.compile(r"^EV-\d{3}$")
MET_RE = re.compile(r"^MET-\d{3}$")
NO_EVIDENCE_TERMINAL_STATUSES = {"not_executed", "not_material", "accounting_only"}
EVIDENCE_TERMINAL_STATUS = "executed_with_evidence"
EVIDENCE_READY_ARCHIVE_STATUSES = {"saved_html", "saved_text", "saved_pdf", "user_provided", "manual_verified_excerpt"}
NON_EVIDENCE_ARCHIVE_STATUSES = {"needs_research_verification", "search_snippet_only", "archive_unavailable", "excerpt_snapshot"}
RESEARCH_CONTEXT_ARCHIVE_STATUSES = {"research_context"}
AUDITED_METRIC_LEVEL = "audited_metric"
RESEARCH_CONTEXT_LEVEL = "research_context"
NON_PROMOTABLE_EVIDENCE_STATUS_VALUES = {
    "lead_only",
    "search_lead",
    "search_snippet_only",
    "unopened",
    "unreviewed",
    "needs_review",
    "candidate_only",
}
EXTERNAL_VERIFICATION_LIMITED_VALUES = {
    "not_externally_verified",
    "management_provided_only",
    "user_provided_only",
    "unaudited_project_context",
    "needs_external_verification",
}
NON_PROMOTABLE_METRIC_AUDIT_LEVEL_VALUES = {
    "research_context",
    "context_only",
    "contextual_only",
    "unaudited",
    "not_audited",
    "not_audited_metric",
    "not_chart_ready",
    "lead_only",
    "candidate_only",
}
PLACEHOLDER_MARKERS = (
    "TODO",
    "TODO_REPLACE",
    "LLM must",
    "LLM MUST",
    "replace with",
    "needs_knowledge_llm",
    "placeholder",
    "skeleton",
    "占位",
)


def text(value: Any) -> str:
    return str(value or "").strip()


def target_is_explicitly_disclosed(value: Any) -> bool:
    return text(value).lower() == "disclosed"


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_optional_json(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    data = load_json_file(p)
    return data if isinstance(data, dict) else {}


def pipe(value: Any) -> str:
    value_text = text(value)
    return value_text.replace("|", "/").replace("\n", " ").strip()


def join_values(values: Any) -> str:
    return ", ".join(text(item) for item in as_list(values) if text(item))


def reviews(source_reviews: dict[str, Any]) -> list[dict[str, Any]]:
    raw = source_reviews.get("reviews")
    if raw is None:
        raw = source_reviews.get("source_reviews")
    return [item for item in as_list(raw) if isinstance(item, dict)]


def material_manifest_items(material_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in as_list(material_manifest.get("materials")) if isinstance(item, dict)]


def material_extract_items(material_extracts: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in as_list(material_extracts.get("extracts")) if isinstance(item, dict)]


def review_id(review: dict[str, Any]) -> str:
    return text(review.get("source_review_id") or review.get("review_id") or review.get("source_id") or review.get("id"))


def review_url(review: dict[str, Any]) -> str:
    return text(review.get("url") or review.get("source_url") or review.get("source") or review.get("source_link"))


def review_title(review: dict[str, Any]) -> str:
    return text(review.get("title") or review.get("source_title") or review.get("source_name") or review.get("name"))


def review_locator(review: dict[str, Any]) -> str:
    return text(review.get("locator") or review.get("source_locator") or review.get("methodology_locator"))


def review_excerpt(review: dict[str, Any]) -> str:
    return text(review.get("excerpt") or review.get("raw_excerpt") or review.get("reviewed_excerpt"))


def source_reviews_by_id(source_reviews: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {review_id(item): item for item in reviews(source_reviews) if review_id(item)}


def archive_entries(source_archive_index: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(source_archive_index, dict):
        return []
    raw = source_archive_index.get("entries")
    if raw is None:
        raw = source_archive_index.get("archive_entries")
    return [item for item in as_list(raw) if isinstance(item, dict)]


def archive_entry_id(entry: dict[str, Any]) -> str:
    return text(entry.get("source_review_id") or entry.get("archive_id") or entry.get("source_id") or entry.get("id"))


def review_from_archive_entry(entry: dict[str, Any]) -> dict[str, Any]:
    source_id = archive_entry_id(entry)
    return {
        "source_review_id": source_id,
        "url": text(entry.get("url")),
        "title": text(entry.get("title")) or source_id,
        "source_type": normalize_source_type(entry.get("source_type") or "web_search_result"),
        "source_access": text(entry.get("source_access") or "public_search"),
        "source_access_path": text(entry.get("archive_path") or entry.get("source_access_path")),
        "locator": text(entry.get("locator")),
        "excerpt": text(entry.get("reviewed_excerpt") or entry.get("excerpt")),
        "search_attempt_ids": [text(item) for item in as_list(entry.get("search_attempt_ids")) if text(item)],
        "evidence_ids": [text(item) for item in as_list(entry.get("evidence_ids")) if text(item)],
        "metric_ids": [text(item) for item in as_list(entry.get("metric_ids")) if text(item)],
        "audit_level": text(entry.get("audit_level") or (RESEARCH_CONTEXT_LEVEL if text(entry.get("archive_status")) in RESEARCH_CONTEXT_ARCHIVE_STATUSES else "")),
        "source_reliability": text(entry.get("source_reliability") or entry.get("reliability")),
        "reliability": text(entry.get("reliability") or entry.get("source_reliability")),
        "confidence": text(entry.get("confidence") or "unreviewed"),
        "evidence_use_tier": text(entry.get("evidence_use_tier") or "candidate"),
        "claim_use_scope": text(entry.get("claim_use_scope") or "Archived source; LLM must review exact claim-use scope before promotion."),
        "usable_as_evidence": entry.get("usable_as_evidence") if isinstance(entry.get("usable_as_evidence"), bool) else False,
        "review_status": text(entry.get("review_status") or "needs_llm_source_review"),
        "limitations": text(entry.get("limitations") or entry.get("archive_unavailable_reason")),
        "archive_status": text(entry.get("archive_status")),
        "archive_path": text(entry.get("archive_path")),
        "raw_archive_path": text(entry.get("raw_archive_path")),
        "excerpt_origin": text(entry.get("excerpt_origin")),
        "secondary_verification": text(entry.get("secondary_verification")),
        "secondary_verification_notes": text(entry.get("secondary_verification_notes")),
        "source_date": text(entry.get("source_date")),
        "geography": text(entry.get("geography")),
        "data_period": text(entry.get("data_period")),
        "methodology_locator": text(entry.get("methodology_locator")),
    }


def archive_status(review: dict[str, Any]) -> str:
    return text(review.get("archive_status"))


def evidence_ready_archive(review: dict[str, Any]) -> bool:
    status = archive_status(review)
    if not status:
        return not review_url(review).startswith("http")
    return status in EVIDENCE_READY_ARCHIVE_STATUSES


def source_requires_evidence_ready_archive(source: dict[str, Any]) -> bool:
    source_access = text(source.get("source_access"))
    if source_access == "user_provided":
        return False
    source_url = text(source.get("source_url") or source.get("url"))
    return source_access == "public_search" or source_url.lower().startswith(("http://", "https://"))


def explicit_external_verification_limited(metric_row: dict[str, Any]) -> bool:
    status = normalized_status_value(
        metric_row.get("external_verification_status")
        or metric_row.get("verification_status")
        or metric_row.get("audit_context")
    )
    if status in EXTERNAL_VERIFICATION_LIMITED_VALUES:
        return True
    return metric_row.get("external_verification_obtained") is False


def merged_reviews(
    *,
    source_reviews: dict[str, Any],
    source_archive_index: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Return embedded source reviews, preferring explicit LLM reviews when present."""
    by_id: dict[str, dict[str, Any]] = {}
    for entry in archive_entries(source_archive_index):
        item = review_from_archive_entry(entry)
        item_id = review_id(item)
        if item_id:
            by_id[item_id] = item
    for item in reviews(source_reviews):
        item_id = review_id(item)
        if not item_id:
            continue
        base = by_id.get(item_id, {})
        merged = {**base, **item}
        by_id[item_id] = merged
    return [by_id[key] for key in sorted(by_id)]


def graph_row_maps(research_graph_state: dict[str, Any] | None) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    if not isinstance(research_graph_state, dict):
        return {}, {}
    evidence_by_id: dict[str, dict[str, Any]] = {}
    metric_by_id: dict[str, dict[str, Any]] = {}
    for unit in as_list(research_graph_state.get("research_units")):
        if not isinstance(unit, dict):
            continue
        for row in as_list(unit.get("evidence")):
            if not isinstance(row, dict):
                continue
            row_id = text(row.get("evidence_id") or row.get("id"))
            if row_id:
                evidence_by_id[row_id] = row
        for row in as_list(unit.get("metrics")):
            if not isinstance(row, dict):
                continue
            row_id = text(row.get("metric_id") or row.get("id"))
            if row_id:
                metric_by_id[row_id] = row
    return evidence_by_id, metric_by_id


def meta_from_inputs(input_card: dict[str, Any], scope_pack: dict[str, Any]) -> dict[str, str]:
    input_meta = input_card.get("meta") if isinstance(input_card.get("meta"), dict) else {}
    scope_meta = scope_pack.get("meta") if isinstance(scope_pack.get("meta"), dict) else {}
    scope_summary = scope_pack.get("scope_summary") if isinstance(scope_pack.get("scope_summary"), dict) else {}
    target_company = text(input_card.get("target_company") or input_meta.get("target_company") or scope_meta.get("target_company"))
    raw_target_disclosure_status = text(
        input_card.get("target_disclosure_status")
        or input_meta.get("target_disclosure_status")
        or scope_meta.get("target_disclosure_status")
    )
    target_disclosure_status = raw_target_disclosure_status or ("disclosed" if target_company else "")
    return {
        "target_company": target_company,
        "target_disclosure_status": target_disclosure_status,
        "transaction_type": text(input_card.get("transaction_type") or input_meta.get("transaction_type") or scope_meta.get("transaction_type")),
        "industry": text(input_card.get("industry") or input_meta.get("industry") or scope_meta.get("industry") or scope_summary.get("working_market")),
        "subsector": text(input_card.get("subsector") or input_meta.get("subsector") or scope_meta.get("subsector")),
        "geography": text(input_card.get("geography") or input_meta.get("geography") or scope_meta.get("geography")),
        "language": text(input_card.get("language") or input_meta.get("language") or scope_meta.get("language") or "English"),
        "prepared_date": date.today().isoformat(),
        "research_as_of_date": text(input_meta.get("research_as_of_date") or scope_meta.get("research_as_of_date") or date.today().isoformat()),
    }


def issue_fact_status(result: dict[str, Any]) -> str:
    status = text(result.get("status"))
    if status == "unavailable_after_research":
        return "unavailable_after_research"
    return "insufficient"


def result_thread_label(result: dict[str, Any]) -> str:
    return text(
        result.get("research_thread")
        or result.get("thread")
        or result.get("topic")
        or result.get("issue_area")
        or result.get("research_question")
    )


def result_focus_label(result: dict[str, Any]) -> str:
    return text(result.get("thread_focus") or result.get("subissue") or result.get("research_question"))


def build_db(
    *,
    input_card: dict[str, Any],
    scope_pack: dict[str, Any],
    formal_search_plan: dict[str, Any],
    execution_report: dict[str, Any],
    source_reviews: dict[str, Any],
    source_archive_index: dict[str, Any] | None = None,
    material_manifest: dict[str, Any] | None = None,
    material_extracts: dict[str, Any] | None = None,
    research_graph_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = meta_from_inputs(input_card, scope_pack)
    scope_summary = scope_pack.get("scope_summary") if isinstance(scope_pack.get("scope_summary"), dict) else {}
    embedded_review_rows = merged_reviews(source_reviews=source_reviews, source_archive_index=source_archive_index)
    embedded_source_reviews = {
        "schema_version": "embedded_source_reviews_v1",
        "source_of_truth": "artifacts/research_evidence_db.json",
        "policy": "Review status and evidence usability are LLM/QC judgments stored inside the evidence DB. The public workflow does not maintain a standalone source_reviews artifact.",
        "reviews": embedded_review_rows,
    }
    review_map = {review_id(item): item for item in embedded_review_rows if review_id(item)}
    graph_evidence_by_id, graph_metric_by_id = graph_row_maps(research_graph_state)

    source_materials: list[dict[str, Any]] = []
    for item in material_manifest_items(material_manifest or {}):
        material_id = text(item.get("material_id"))
        title = text(item.get("material_title") or item.get("title") or material_id)
        source_access = text(item.get("source_access") or item.get("access_level") or "user_provided")
        source_access_path = text(item.get("file_path_or_url") or item.get("locator"))
        reviewed_excerpt = text(item.get("brief_excerpt") or item.get("extracted_text_preview") or item.get("notes"))
        source_materials.append(
            {
                "source_review_id": material_id,
                "material_id": material_id,
                "source_name": title,
                "source_type": normalize_source_type(item.get("source_type")),
                "source_access": source_access,
                "source_access_path": source_access_path,
                "source_date": text(item.get("source_date")),
                "geography": text(item.get("geography")),
                "fact_type": "material_intake",
                "confidence": text(item.get("confidence") or "unreviewed"),
                "scope": text(item.get("scope")),
                "source_reliability": text(item.get("source_reliability")),
                "evidence_use_tier": "candidate",
                "audit_level": RESEARCH_CONTEXT_LEVEL,
                "claim_use_scope": "Material intake only until extracted and reconciled.",
                "usable_as_evidence": False,
                "source_url": source_access_path if text(item.get("material_kind")) == "url" else "",
                "source_locator": source_access_path,
                "reviewed_excerpt": reviewed_excerpt,
                "limitations": "Material intake record; promote through extraction/review before claim use.",
                "evidence_ids": [],
                "metric_ids": [],
            }
        )
    for item in embedded_review_rows:
        src_id = review_id(item)
        source_materials.append(
            {
                "source_review_id": src_id,
                "source_name": review_title(item),
                "source_type": normalize_source_type(item.get("source_type")),
                "source_access": text(item.get("source_access") or ("user_provided" if is_material_type(normalize_source_type(item.get("source_type"))) else "public_search")),
                "source_access_path": text(item.get("source_access_path") or item.get("source_path")),
                "source_date": text(item.get("source_date")),
                "geography": text(item.get("geography")),
                "fact_type": text(item.get("fact_type")),
                "confidence": text(item.get("confidence")),
                "scope": text(item.get("scope")),
                "source_reliability": text(item.get("reliability") or item.get("source_reliability")),
                "evidence_use_tier": text(item.get("evidence_use_tier")),
                "audit_level": text(item.get("audit_level")),
                "claim_use_scope": text(item.get("claim_use_scope")),
                "usable_as_evidence": item.get("usable_as_evidence"),
                "source_url": review_url(item),
                "source_locator": review_locator(item),
                "reviewed_excerpt": review_excerpt(item),
                "limitations": text(item.get("limitations")),
                "archive_status": text(item.get("archive_status")),
                "archive_path": text(item.get("archive_path")),
                "raw_archive_path": text(item.get("raw_archive_path")),
                "excerpt_origin": text(item.get("excerpt_origin")),
                "secondary_verification": text(item.get("secondary_verification")),
                "secondary_verification_notes": text(item.get("secondary_verification_notes")),
                "review_status": text(item.get("review_status")),
                "metric_ids": [text(metric_id) for metric_id in as_list(item.get("metric_ids")) if text(metric_id)],
                "evidence_ids": [text(evidence_id) for evidence_id in as_list(item.get("evidence_ids")) if text(evidence_id)],
            }
        )

    formal_results: list[dict[str, Any]] = []
    formal_extracts: list[dict[str, Any]] = []
    material_extraction_rows: list[dict[str, Any]] = []
    for item in material_extract_items(material_extracts or {}):
        material_extraction_rows.append(
            {
                "material_id": text(item.get("material_id")),
                "source_type": normalize_source_type(item.get("source_type")),
                "locator": text(item.get("locator")),
                "extraction_status": text(item.get("extraction_status")),
                "raw_text_available": bool(item.get("raw_text_available")),
                "raw_text_path": text(item.get("raw_text_path") or item.get("extracted_text_path")),
                "raw_text_preview": text(item.get("raw_text_preview")),
                "content_capture_status": text(item.get("content_capture_status")),
                "llm_extraction_status": text(item.get("llm_extraction_status")),
                "evidence_authorization_status": text(item.get("evidence_authorization_status") or "not_authorized_intake_only"),
                "extracted_facts": as_list(item.get("extracted_facts")),
                "extracted_metrics": as_list(item.get("extracted_metrics")),
                "quoted_excerpts": as_list(item.get("quoted_excerpts")),
                "unknowns_or_conflicts": as_list(item.get("unknowns_or_conflicts")),
                "claim_use_limitations": text(item.get("claim_use_limitations")),
            }
        )

    source_ids_by_evidence: dict[str, set[str]] = {}
    source_ids_by_metric: dict[str, set[str]] = {}
    for source in source_materials:
        if not isinstance(source, dict):
            continue
        src_id = text(source.get("source_review_id"))
        if not src_id:
            continue
        for ev_id in [text(item) for item in as_list(source.get("evidence_ids")) if text(item)]:
            source_ids_by_evidence.setdefault(ev_id, set()).add(src_id)
        for met_id in [text(item) for item in as_list(source.get("metric_ids")) if text(item)]:
            source_ids_by_metric.setdefault(met_id, set()).add(src_id)

    def source_for_evidence(ev_id: str, result_source_ids: list[str]) -> str:
        explicit = text(graph_evidence_by_id.get(ev_id, {}).get("source_review_id"))
        if explicit and explicit in result_source_ids:
            return explicit
        mapped = sorted(source_ids_by_evidence.get(ev_id, set()).intersection(result_source_ids))
        if len(mapped) == 1:
            return mapped[0]
        if len(result_source_ids) == 1:
            return result_source_ids[0]
        return ""

    def source_for_metric(met_id: str, result_source_ids: list[str]) -> str:
        explicit = text(graph_metric_by_id.get(met_id, {}).get("source_review_id"))
        if explicit and explicit in result_source_ids:
            return explicit
        mapped = sorted(source_ids_by_metric.get(met_id, set()).intersection(result_source_ids))
        if len(mapped) == 1:
            return mapped[0]
        if len(result_source_ids) == 1:
            return result_source_ids[0]
        return ""

    evidence_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    context_rows: list[dict[str, Any]] = []
    critical_gap_rows: list[str] = []
    optional_gap_rows: list[str] = []

    for idx, result in enumerate(as_list(execution_report.get("issue_results")), start=1):
        if not isinstance(result, dict):
            continue
        result_id = text(result.get("result_id")) or f"FR-{idx:03d}"
        terminal_status = text(result.get("terminal_status"))
        downstream_permission = text(result.get("downstream_permission"))
        source_review_ids = [text(item) for item in as_list(result.get("source_review_ids")) if text(item)]
        evidence_ids = [text(item) for item in as_list(result.get("evidence_ids")) if text(item)]
        metric_ids = [text(item) for item in as_list(result.get("metric_ids")) if text(item)]
        search_attempt_ids = [text(item) for item in as_list(result.get("search_attempt_ids")) if text(item)]
        formal_results.append(
            {
                "result_id": result_id,
                "research_thread": result_thread_label(result),
                "thread_focus": result_focus_label(result),
                "research_question": text(result.get("research_question")),
                "status": text(result.get("status")),
                "terminal_status": terminal_status,
                "downstream_permission": downstream_permission,
                "actual_search_attempt_count": result.get("actual_search_attempt_count"),
                "search_instruction_ids": [text(item) for item in as_list(result.get("search_instruction_ids")) if text(item)],
                "search_attempt_ids": search_attempt_ids,
                "source_review_ids": source_review_ids,
                "evidence_ids": evidence_ids,
                "metric_ids": metric_ids,
                "findings_summary": text(result.get("findings_summary")),
                "limitations": [text(item) for item in as_list(result.get("limitations")) if text(item)],
                "research_pack_handling": text(result.get("research_pack_handling")),
            }
        )
        if source_review_ids and (
            terminal_status != EVIDENCE_TERMINAL_STATUS
            or downstream_permission in {"contextual_only", "research_context"}
        ):
            context_rows.append(
                {
                    "context_id": f"RC-{len(context_rows) + 1:03d}",
                    "result_id": result_id,
                    "research_thread": result_thread_label(result),
                    "thread_focus": result_focus_label(result),
                    "topic": text(result.get("research_question")) or result_thread_label(result),
                    "summary": text(result.get("findings_summary"))
                    or "Source reviewed for context only; not promoted into EV/MET evidence.",
                    "source_review_ids": source_review_ids,
                    "search_attempt_ids": search_attempt_ids,
                    "confidence": text(result.get("confidence") or "unreviewed"),
                    "audit_level": RESEARCH_CONTEXT_LEVEL,
                    "limitations": "; ".join(text(item) for item in as_list(result.get("limitations")) if text(item))
                    or "Research context only; cannot support key numbers, charts, or hard slide claims unless promoted to EV/MET.",
                }
            )
        if terminal_status in NO_EVIDENCE_TERMINAL_STATUSES:
            critical_gap_rows.append(
                f"{result_id} {result_thread_label(result)}: "
                f"{terminal_status}; not eligible for evidence promotion until actual formal search/source review exists."
            )
        elif terminal_status != EVIDENCE_TERMINAL_STATUS:
            optional_gap_rows.append(
                f"{result_id} {result_thread_label(result)}: "
                f"{terminal_status or text(result.get('status'))}; keep as contextual/gap unless stronger sources are reviewed."
            )

        ready_candidate_ids: list[str] = []
        for src_id in source_review_ids:
            review = review_map.get(src_id, {})
            source_is_evidence_ready = evidence_ready_archive(review)
            archive_state = archive_status(review)
            source_candidate_evidence_ids = [
                ev_id
                for ev_id in evidence_ids
                if source_for_evidence(ev_id, source_review_ids) == src_id
            ]
            source_candidate_metric_ids = [
                met_id
                for met_id in metric_ids
                if source_for_metric(met_id, source_review_ids) == src_id
            ]
            source_candidate_ids = [*source_candidate_evidence_ids, *source_candidate_metric_ids]
            if terminal_status == EVIDENCE_TERMINAL_STATUS and source_candidate_ids and source_is_evidence_ready:
                ready_candidate_ids.extend(source_candidate_ids)
            elif terminal_status == EVIDENCE_TERMINAL_STATUS and source_candidate_ids:
                critical_gap_rows.append(
                    f"{result_id} {result_thread_label(result)}: "
                    f"source {src_id} archive_status={archive_state or 'missing'}; "
                    "Research must complete full-page archive or secondary verification before Knowledge can promote EV/MET rows."
                )
            formal_extracts.append(
                {
                    "extract_id": f"FX-{len(formal_extracts) + 1:03d}",
                    "result_id": result_id,
                    "research_thread": result_thread_label(result),
                    "thread_focus": result_focus_label(result),
                    "source_review_id": src_id,
                    "search_attempt_ids": search_attempt_ids,
                    "source_url": review_url(review),
                    "source_locator": review_locator(review),
                    "reviewed_excerpt_or_paraphrase": review_excerpt(review),
                    "extracted_fact_or_metric_candidate": "TODO_REPLACE_WITH_SOURCE_FAITHFUL_EXTRACT",
                    "status": text(result.get("status")),
                    "terminal_status": terminal_status,
                    "archive_status": archive_state,
                    "archive_eligibility": "evidence_ready" if source_is_evidence_ready else "research_verification_required",
                    "candidate_evidence_ids": source_candidate_evidence_ids if terminal_status == EVIDENCE_TERMINAL_STATUS and source_is_evidence_ready else [],
                    "candidate_metric_ids": source_candidate_metric_ids if terminal_status == EVIDENCE_TERMINAL_STATUS and source_is_evidence_ready else [],
                    "promoted_evidence_ids": [],
                    "promoted_metric_ids": [],
                    "limitations": [text(item) for item in as_list(result.get("limitations")) if text(item)],
                }
            )
        if terminal_status != EVIDENCE_TERMINAL_STATUS or not source_review_ids:
            continue
        if ready_candidate_ids:
            critical_gap_rows.append(
                f"{result_id} {result_thread_label(result)}: "
                "Knowledge LLM must decide whether candidate IDs "
                f"{', '.join(ready_candidate_ids)} should be promoted into evidence_ledger or metric_reconciliation."
            )

    inventory: list[dict[str, Any]] = []
    for result in as_list(execution_report.get("issue_results")):
        if not isinstance(result, dict):
            continue
        result_source_ids = [text(item) for item in as_list(result.get("source_review_ids")) if text(item)]
        result_sources_ready = (
            bool(result_source_ids)
            and all(evidence_ready_archive(review_map.get(src_id, {})) for src_id in result_source_ids)
        )
        raw_evidence_ids = [text(item) for item in as_list(result.get("evidence_ids")) if text(item)]
        raw_metric_ids = [text(item) for item in as_list(result.get("metric_ids")) if text(item)]
        if text(result.get("terminal_status")) == EVIDENCE_TERMINAL_STATUS:
            if result_sources_ready:
                fact_status = "needs_knowledge_llm"
                notes = (
                    f"{text(result.get('findings_summary'))} "
                    "Candidate evidence exists, but Knowledge LLM must promote EV/MET rows before banker_page_pack can use it."
                ).strip()
            else:
                fact_status = "insufficient"
                notes = (
                    f"{text(result.get('findings_summary'))} "
                    "Source archive is not evidence-ready; Research secondary verification is required."
                ).strip()
        else:
            fact_status = issue_fact_status(result)
            notes = text(result.get("findings_summary")) or "No usable formal result found; keep as research gap until searched."
        inventory.append(
            {
                "research_thread": result_thread_label(result),
                "thread_focus": result_focus_label(result),
                "evidence_ids": [],
                "metric_ids": [],
                "candidate_evidence_ids": raw_evidence_ids if result_sources_ready else [],
                "candidate_metric_ids": raw_metric_ids if result_sources_ready else [],
                "fact_status": fact_status,
                "notes": notes,
            }
        )

    return {
        "schema_version": "research_evidence_db_v1",
        "source_of_truth": True,
        "authoring_policy": "LLM edits this database; industry_research_pack.md is generated from it and should not be hand-authored.",
        "evidence_policy": {
            "metric_reconciliation_rule": "Every promoted MET row must carry indicator, value, unit, period, geography, source, source locator, short source excerpt, and audit note.",
            "context_rule": "Background context keeps source URLs, summaries, and notes, but cannot support key numbers, charts, or hard slide claims unless Knowledge promotes it into EV/MET.",
        },
        "meta": meta,
        "scope_summary": scope_summary,
        "formal_search_plan_summary": {
            "artifact_path": "artifacts/formal_search_plan.json",
            "research_thread_count": sum(
                len(as_list(formal_search_plan.get(field)))
                for field in ("core_research_threads", "research_threads", "industry_specific_research_threads", "custom_evidence_needs", "issue_search_plan")
            ),
        },
        "formal_research_results": formal_results,
        "source_reviews": embedded_source_reviews,
        "material_extractions": material_extraction_rows,
        "formal_research_extracts": formal_extracts,
        "research_context": context_rows,
        "source_materials": source_materials,
        "evidence_ledger": evidence_rows,
        "metric_reconciliation": metric_rows,
        "page_evidence_inventory": inventory,
        "known_transaction_relevant_observations": [],
        "known_risks_or_limits": [],
        "management_provided_claims_to_verify": [],
        "peer_set": [],
        "additional_sector_specific_notes": "Insufficient data",
        "research_gap_audit": {
            "client_ready_evidence_decision": "llm_decision_required",
            "deliverable_constraint": "",
            "critical_gaps": [
                "Resolve before validation: Knowledge LLM must review candidate extracts, promote only supported EV/MET rows, "
                "or record the source limit and the next bounded targeted research loop action."
            ]
            + critical_gap_rows,
            "optional_gaps": optional_gap_rows,
            "intentionally_excluded_topics": [],
            "metric_consistency_check": {},
        },
    }


def contains_placeholder(value: Any) -> bool:
    return any(marker in str(value or "") for marker in PLACEHOLDER_MARKERS)


def normalized_status_value(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text(value).lower()).strip("_")


def validate_db(db: dict[str, Any]) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    if db.get("schema_version") != "research_evidence_db_v1":
        errors.append("schema_version must be research_evidence_db_v1")
    if db.get("source_of_truth") is not True:
        errors.append("source_of_truth must be true")

    meta = db.get("meta") if isinstance(db.get("meta"), dict) else {}
    raw_target_disclosure_status = text(meta.get("target_disclosure_status"))
    if target_is_explicitly_disclosed(raw_target_disclosure_status) and not text(meta.get("target_company")):
        errors.append("meta.target_company is required when target_disclosure_status means the target is disclosed")
    for field in ("industry", "geography", "research_as_of_date"):
        if not text(meta.get(field)):
            errors.append(f"meta.{field} is required")

    source_ids = set()
    source_by_id: dict[str, dict[str, Any]] = {}
    for idx, source in enumerate(as_list(db.get("source_materials")), start=1):
        if not isinstance(source, dict):
            errors.append(f"source_materials[{idx}] must be an object")
            continue
        src_id = text(source.get("source_review_id"))
        if not src_id:
            errors.append(f"source_materials[{idx}]: source_review_id is required")
            continue
        if src_id in source_ids:
            errors.append(f"source_materials[{idx}]: duplicate source_review_id {src_id}")
        source_ids.add(src_id)
        source_by_id[src_id] = source
        source_type = text(source.get("source_type"))
        if not source_type:
            warnings.append(
                f"{src_id}: source_materials.source_type omitted; Knowledge/QC should label source type before using it in page-facing source notes"
            )
        if text(source.get("source_access")) not in {"", "user_provided", "public_search"}:
            warnings.append(
                f"{src_id}: source_materials.source_access is nonstandard; Python will not infer user-provided "
                "or public-search archive behavior from it"
            )
        for field in ("source_url", "source_locator", "reviewed_excerpt", "source_name"):
            if not text(source.get(field)):
                warnings.append(f"{src_id}: source_materials.{field} is empty")
        if is_material_type(source_type) and not source.get("source_access_path") and source_type not in {"", "other"} and text(source.get("source_url", "")).lower() in {"", "user-provided"}:
            warnings.append(
                f"{src_id}: source_materials.source_access_path missing for material source; add file path / URL / locator source path"
            )
        status = text(source.get("archive_status"))
        if status in NON_EVIDENCE_ARCHIVE_STATUSES:
            warnings.append(
                f"{src_id}: archive_status={status}; Research must verify/archive before this source can support promoted evidence"
            )

    formal_result_by_id: dict[str, dict[str, Any]] = {}
    ev_to_result: dict[str, dict[str, Any]] = {}
    met_to_result: dict[str, dict[str, Any]] = {}
    for idx, result in enumerate(as_list(db.get("formal_research_results")), start=1):
        if not isinstance(result, dict):
            errors.append(f"formal_research_results[{idx}] must be an object")
            continue
        result_id = text(result.get("result_id"))
        prefix = result_id or f"formal_research_results[{idx}]"
        if not result_id:
            errors.append(f"{prefix}: result_id is required")
            continue
        if result_id in formal_result_by_id:
            errors.append(f"{prefix}: duplicate result_id {result_id}")
        formal_result_by_id[result_id] = result
        terminal_status = text(result.get("terminal_status"))
        source_review_ids = [text(item) for item in as_list(result.get("source_review_ids")) if text(item)]
        evidence_ids = [text(item) for item in as_list(result.get("evidence_ids")) if text(item)]
        metric_ids = [text(item) for item in as_list(result.get("metric_ids")) if text(item)]
        search_attempt_ids = [text(item) for item in as_list(result.get("search_attempt_ids")) if text(item)]
        if terminal_status in NO_EVIDENCE_TERMINAL_STATUSES:
            if search_attempt_ids or source_review_ids or evidence_ids or metric_ids:
                errors.append(
                    f"{prefix}: terminal_status={terminal_status} cannot carry S/SRC/EV/MET IDs; "
                    "planned-but-unexecuted rows belong in research_gap_audit, not evidence promotion"
                )
        if terminal_status == EVIDENCE_TERMINAL_STATUS and not source_review_ids:
            errors.append(f"{prefix}: executed_with_evidence requires source_review_ids")
        for src_id in source_review_ids:
            if src_id not in source_ids:
                errors.append(f"{prefix}: source_review_id {src_id} not found in source_materials")
        for ev_id in evidence_ids:
            ev_to_result[ev_id] = result
        for met_id in metric_ids:
            met_to_result[met_id] = result

    extract_count = 0
    extract_promoted_ev_refs: list[tuple[str, str, str]] = []
    extract_promoted_met_refs: list[tuple[str, str, str]] = []
    for idx, extract in enumerate(as_list(db.get("formal_research_extracts")), start=1):
        if not isinstance(extract, dict):
            errors.append(f"formal_research_extracts[{idx}] must be an object")
            continue
        extract_count += 1
        extract_id = text(extract.get("extract_id")) or f"formal_research_extracts[{idx}]"
        if not text(extract.get("extract_id")):
            errors.append(f"{extract_id}: extract_id is required")
        result_id = text(extract.get("result_id"))
        result = formal_result_by_id.get(result_id)
        if not result_id or result is None:
            errors.append(f"{extract_id}: result_id must reference formal_research_results")
        elif text(result.get("terminal_status")) in NO_EVIDENCE_TERMINAL_STATUSES:
            errors.append(
                f"{extract_id}: cannot extract evidence from {result_id} with terminal_status={text(result.get('terminal_status'))}; "
                "account for it in research_gap_audit instead"
            )
        src_id = text(extract.get("source_review_id"))
        if not src_id:
            errors.append(f"{extract_id}: source_review_id is required; extracts must come from real reviewed SRC rows")
        elif src_id not in source_ids:
            errors.append(f"{extract_id}: source_review_id {src_id} not found in source_materials")
        if contains_placeholder(extract.get("extracted_fact_or_metric_candidate")):
            errors.append(f"{extract_id}: replace extracted_fact_or_metric_candidate placeholder")
        for ev_id in [text(item) for item in as_list(extract.get("promoted_evidence_ids")) if text(item)]:
            extract_promoted_ev_refs.append((extract_id, src_id, ev_id))
        for met_id in [text(item) for item in as_list(extract.get("promoted_metric_ids")) if text(item)]:
            extract_promoted_met_refs.append((extract_id, src_id, met_id))

    ev_ids: set[str] = set()
    ev_source_by_id: dict[str, str] = {}
    for idx, row in enumerate(as_list(db.get("evidence_ledger")), start=1):
        if not isinstance(row, dict):
            errors.append(f"evidence_ledger[{idx}] must be an object")
            continue
        ev_id = text(row.get("evidence_id"))
        if not EV_RE.match(ev_id):
            errors.append(f"evidence_ledger[{idx}]: evidence_id must follow EV-001 format")
            continue
        if ev_id in ev_ids:
            errors.append(f"{ev_id}: duplicate evidence_id")
        ev_ids.add(ev_id)
        source_type = text(row.get("source_type"))
        if not source_type:
            errors.append(f"{ev_id}: source_type is required")
        for field in ("claim_or_metric", "claim_scope", "source_name", "source_url", "source_type", "source_locator", "raw_excerpt"):
            if not text(row.get(field)):
                errors.append(f"{ev_id}: {field} is required")
            elif contains_placeholder(row.get(field)):
                errors.append(f"{ev_id}: {field} still contains placeholder text")
        for field in ("evidence_status", "reliability", "confidence"):
            value = text(row.get(field))
            if not value:
                warnings.append(f"{ev_id}: {field} omitted; Knowledge/QC should preserve source-use limits in notes or page caveats")
            elif contains_placeholder(value):
                errors.append(f"{ev_id}: {field} still contains placeholder text")
        evidence_status = text(row.get("evidence_status"))
        if normalized_status_value(evidence_status) in NON_PROMOTABLE_EVIDENCE_STATUS_VALUES:
            errors.append(
                f"{ev_id}: evidence_status={evidence_status!r} cannot be promoted into evidence_ledger; "
                "open/archive/extract the source first or keep it in research_gap_audit/source leads"
            )
        src_id = text(row.get("source_review_id"))
        if not src_id:
            errors.append(f"{ev_id}: source_review_id is required")
        elif src_id not in source_ids:
            errors.append(f"{ev_id}: source_review_id {src_id} not found in source_materials")
        else:
            ev_source_by_id[ev_id] = src_id
            source = source_by_id.get(src_id, {})
            source_url = text(source.get("source_url"))
            row_url = text(row.get("source_url"))
            if source_url and row_url and source_url != row_url:
                errors.append(f"{ev_id}: source_url does not match source_materials[{src_id}]")
            if source_requires_evidence_ready_archive(source):
                if not text(source.get("archive_path")):
                    errors.append(
                        f"{ev_id}: public/search source {src_id} must have archive_path before it can support promoted evidence; "
                        "search snippets, result pages, and context-only notes are leads only"
                    )
                if not evidence_ready_archive(source):
                    errors.append(
                        f"{ev_id}: source {src_id} archive_status={text(source.get('archive_status')) or 'missing'} is not evidence-ready; "
                        "Research must complete full-page archive or explicit manual verification before evidence promotion"
                    )
        source_result = ev_to_result.get(ev_id)
        if source_result and text(source_result.get("terminal_status")) != EVIDENCE_TERMINAL_STATUS:
            errors.append(
                f"{ev_id}: linked formal result {text(source_result.get('result_id'))} is "
                f"terminal_status={text(source_result.get('terminal_status'))}; only executed_with_evidence may promote EV rows"
            )
    if not ev_ids:
        no_evidence_audit = db.get("research_gap_audit") if isinstance(db.get("research_gap_audit"), dict) else {}
        gap_text_parts = [
            text(no_evidence_audit.get("client_ready_evidence_decision")),
            text(no_evidence_audit.get("deliverable_constraint")),
            text(no_evidence_audit.get("research_gap_note")),
            text(no_evidence_audit.get("source_limit")),
            text(no_evidence_audit.get("next_research_action")),
        ]
        gap_text_parts.extend(text(item) for item in as_list(no_evidence_audit.get("critical_gaps")))
        gap_text_parts.extend(text(item) for item in as_list(no_evidence_audit.get("optional_gaps")))
        combined_gap_text = " ".join(part for part in gap_text_parts if part)
        still_candidate_workspace = (
            text(no_evidence_audit.get("client_ready_evidence_decision")) == "llm_decision_required"
            or "Resolve before validation" in combined_gap_text
        )
        if still_candidate_workspace:
            errors.append(
                "research_gap_audit still carries the candidate-workspace no-evidence prompt; Knowledge LLM must either "
                "promote source-faithful EV rows or write a natural source-limit / targeted-research audit. "
                "Do not fabricate EV rows to satisfy validation; route missing evidence to the bounded targeted research loop."
            )
        elif len(combined_gap_text) >= 30:
            warnings.append(
                "research_evidence_db has no promoted EV rows and uses a natural research_gap_audit; "
                "preserve it if it explains the source limit and next action"
            )
            warnings.append(
                "research_evidence_db has no promoted EV rows; final delivery should pause, "
                "route to targeted research, narrow scope, or create a clearly labeled research-limited review copy"
            )
        else:
            errors.append(
                "research_gap_audit does not explain why no EV row was promoted; Knowledge LLM must either promote source-faithful EV rows "
                "or write a natural source-limit / targeted-research audit with the next honest action. "
                "Do not fabricate EV rows to satisfy validation; route missing evidence to the "
                "bounded targeted research loop."
            )

    met_ids: set[str] = set()
    met_source_by_id: dict[str, str] = {}
    for idx, row in enumerate(as_list(db.get("metric_reconciliation")), start=1):
        if not isinstance(row, dict):
            errors.append(f"metric_reconciliation[{idx}] must be an object")
            continue
        met_id = text(row.get("metric_id"))
        if not MET_RE.match(met_id):
            errors.append(f"metric_reconciliation[{idx}]: metric_id must follow MET-001 format")
            continue
        if met_id in met_ids:
            errors.append(f"{met_id}: duplicate metric_id")
        met_ids.add(met_id)
        audit_level = text(row.get("audit_level"))
        if contains_placeholder(audit_level):
            errors.append(f"{met_id}: audit_level still contains placeholder text")
        elif normalized_status_value(audit_level) in NON_PROMOTABLE_METRIC_AUDIT_LEVEL_VALUES:
            errors.append(
                f"{met_id}: audit_level={audit_level!r} says this is not a promoted metric; "
                "context-only or unaudited numbers belong in research_context, not metric_reconciliation"
            )
        for field in ("metric_group", "metric_name", "metric_type", "market_definition", "channel_scope", "geography", "data_period", "value", "unit"):
            if not text(row.get(field)):
                errors.append(f"{met_id}: {field} is required")
            elif contains_placeholder(row.get(field)):
                errors.append(f"{met_id}: {field} still contains placeholder text")
        for field in ("conflict_status", "resolution"):
            value = text(row.get(field))
            if not value:
                warnings.append(f"{met_id}: {field} omitted; add it when source conflict or reconciliation affects deck use")
            elif contains_placeholder(value):
                errors.append(f"{met_id}: {field} still contains placeholder text")
        for field in ("source_review_id", "source_name", "source_type", "source_locator", "raw_excerpt", "audit_note"):
            if not text(row.get(field)):
                errors.append(f"{met_id}: audited metric field {field} is required")
            elif contains_placeholder(row.get(field)):
                errors.append(f"{met_id}: audited metric field {field} still contains placeholder text")
        if not text(row.get("source_url")) and not text(row.get("source_access_path")):
            errors.append(f"{met_id}: audited metric requires source_url or source_access_path")
        src_id = text(row.get("source_review_id"))
        if src_id:
            if src_id not in source_ids:
                errors.append(f"{met_id}: source_review_id {src_id} not found in source_materials")
            else:
                met_source_by_id[met_id] = src_id
                source = source_by_id.get(src_id, {})
                source_url = text(source.get("source_url"))
                row_url = text(row.get("source_url"))
                if source_url and row_url and source_url != row_url:
                    errors.append(f"{met_id}: source_url does not match source_materials[{src_id}]")
                if explicit_external_verification_limited(row):
                    warnings.append(
                        f"{met_id}: metric row explicitly says external verification is limited; Knowledge/QC should "
                        "keep it out of audited_metric chart use unless the row records external verification, or move "
                        "it to unaudited project context / research_context"
                    )
                if source_requires_evidence_ready_archive(source):
                    if not text(source.get("archive_path")):
                        errors.append(
                            f"{met_id}: public/search source {src_id} must have archive_path before it can support an audited metric"
                        )
                    if not evidence_ready_archive(source):
                        errors.append(
                            f"{met_id}: source {src_id} archive_status={text(source.get('archive_status')) or 'missing'} is not audit-ready for MET promotion"
                        )
        if len(text(row.get("source_locator"))) < 6:
            errors.append(f"{met_id}: source_locator must identify the page, table, section, or paragraph for the metric")
        if len(text(row.get("raw_excerpt"))) < 20:
            errors.append(f"{met_id}: raw_excerpt must include a short source phrase supporting the metric")
        source_result = met_to_result.get(met_id)
        if source_result and text(source_result.get("terminal_status")) != EVIDENCE_TERMINAL_STATUS:
            errors.append(
                f"{met_id}: linked formal result {text(source_result.get('result_id'))} is "
                f"terminal_status={text(source_result.get('terminal_status'))}; only executed_with_evidence may promote MET rows"
            )

    for extract_id, src_id, ev_id in extract_promoted_ev_refs:
        if ev_id not in ev_ids:
            errors.append(f"{extract_id}: promoted_evidence_id {ev_id} not found in evidence_ledger")
            continue
        ev_src = ev_source_by_id.get(ev_id, "")
        if ev_src and src_id and ev_src != src_id:
            errors.append(
                f"{extract_id}: promoted_evidence_id {ev_id} belongs to source_review_id {ev_src}, not {src_id}"
            )

    for extract_id, src_id, met_id in extract_promoted_met_refs:
        if met_id not in met_ids:
            errors.append(f"{extract_id}: promoted_metric_id {met_id} not found in metric_reconciliation")
            continue
        met_src = met_source_by_id.get(met_id, "")
        if met_src and src_id and met_src != src_id:
            errors.append(
                f"{extract_id}: promoted_metric_id {met_id} belongs to source_review_id {met_src}, not {src_id}"
            )

    inventory_rows = [row for row in as_list(db.get("page_evidence_inventory")) if isinstance(row, dict)]
    if not inventory_rows:
        warnings.append(
            "page_evidence_inventory is empty; Reasoning can inspect EV/MET rows and research_gap_audit directly, "
            "or Knowledge can add a concise inventory only when it helps page planning"
        )
    sufficient_or_thin = 0
    for idx, row in enumerate(inventory_rows, start=1):
        research_thread = text(row.get("research_thread") or row.get("topic") or row.get("issue_area"))
        status = text(row.get("fact_status"))
        prefix = f"page_evidence_inventory[{idx}]"
        if not research_thread:
            warnings.append(
                f"{prefix}: research_thread omitted; Reasoning can still inspect EV/MET rows directly, but the inventory row is less useful"
            )
        if not status:
            warnings.append(f"{prefix}: fact_status omitted; Reasoning should inspect evidence_ids, metric_ids, and notes directly")
        elif contains_placeholder(status):
            warnings.append(f"{prefix}: fact_status still looks like a candidate workspace note; Knowledge/Reasoning should replace it when the inventory is used")
        row_ev_ids = [text(item) for item in as_list(row.get("evidence_ids")) if text(item)]
        row_met_ids = [text(item) for item in as_list(row.get("metric_ids")) if text(item)]
        missing_ev = sorted(set(row_ev_ids) - ev_ids)
        missing_met = sorted(set(row_met_ids) - met_ids)
        if missing_ev:
            errors.append(f"{prefix}: Evidence IDs not found in evidence_ledger: {', '.join(missing_ev)}")
        if missing_met:
            errors.append(f"{prefix}: Metric IDs not found in metric_reconciliation: {', '.join(missing_met)}")
        if status in {"sufficient", "thin"}:
            sufficient_or_thin += 1
            if not row_ev_ids and not row_met_ids:
                warnings.append(
                    f"{prefix}: {status} fact_status has no evidence_ids or metric_ids; Reasoning should inspect source notes directly or downgrade the inventory row"
                )
    if inventory_rows and sufficient_or_thin == 0:
        warnings.append("page_evidence_inventory has no sufficient/thin rows; banker_page_pack will likely be thin")

    gap_audit = db.get("research_gap_audit") if isinstance(db.get("research_gap_audit"), dict) else {}
    metric_check = gap_audit.get("metric_consistency_check")
    if metric_check in (None, "", {}, []):
        if met_ids:
            warnings.append(
                "research_gap_audit.metric_consistency_check is empty; Knowledge LLM should add only metric checks "
                "that matter for promoted MET rows or visible exhibits"
            )
    elif isinstance(metric_check, dict):
        if not any(text(value) for value in metric_check.values()):
            warnings.append("research_gap_audit.metric_consistency_check has no substantive notes")
    elif isinstance(metric_check, list):
        if not any(text(item) for item in metric_check):
            warnings.append("research_gap_audit.metric_consistency_check has no substantive notes")
    elif not text(metric_check):
        warnings.append("research_gap_audit.metric_consistency_check has no substantive notes")

    metrics = {
        "source_material_count": len(source_ids),
        "formal_extract_count": extract_count,
        "evidence_ledger_row_count": len(ev_ids),
        "metric_reconciliation_row_count": len(met_ids),
        "audited_metric_count": len(met_ids),
        "research_context_row_count": len([row for row in as_list(db.get("research_context")) if isinstance(row, dict)]),
        "page_evidence_inventory_row_count": len(inventory_rows),
    }
    return errors, warnings, metrics


def export_markdown(db: dict[str, Any]) -> str:
    meta = db.get("meta") if isinstance(db.get("meta"), dict) else {}
    scope = db.get("scope_summary") if isinstance(db.get("scope_summary"), dict) else {}
    lines: list[str] = [
        "# Industry Research Evidence Pack",
        "",
        "> Generated readable export from `artifacts/research_evidence_db.json`. Use this as an evidence briefing, not as client-facing slide copy. Edit the JSON database, then regenerate this Markdown pack.",
        "",
        "## Engagement Context",
        f"Target Company: {text(meta.get('target_company'))}",
        f"Transaction Type: {text(meta.get('transaction_type'))}",
        f"Industry: {text(meta.get('industry'))}",
        f"Subsector: {text(meta.get('subsector'))}",
        f"Geography: {text(meta.get('geography'))}",
        f"Output Language: {text(meta.get('language'))}",
        f"Prepared Date: {text(meta.get('prepared_date'))}",
        f"Research As-Of Date: {text(meta.get('research_as_of_date'))}",
        "",
        "## Evidence Use Guidance",
        "Important numbers need an audit row with indicator, value, unit, period, geography, source, locator, short source excerpt, and audit note.",
        "Context notes can support background framing, but key numbers, charts, and hard slide claims should use promoted EV/MET rows with source detail.",
        "",
        "---",
        "",
        "## Market Boundary",
        f"Project Context: {text(meta.get('engagement_context') or meta.get('stage') or 'pre_mandate_client_pitch')}",
        f"Focused Category: {pipe(scope.get('working_market'))}",
        f"Relevant Broader Category: {pipe(scope.get('parent_market'))}",
        f"Wider Market Context: {pipe(scope.get('broader_market'))}",
        f"Relevant Subsegments: {pipe(', '.join(as_list(scope.get('sub_markets'))))}",
        f"Out of Scope for This Section: {pipe(', '.join(as_list(scope.get('excluded_scope'))))}",
        "",
        "---",
        "",
        "## Research Execution Summary",
        "| Result ID | Research Thread | Focus | Research Question | What Was Reviewed | Source Review IDs | Evidence IDs | Metric IDs | Limitations |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for result in as_list(db.get("formal_research_results")):
        if not isinstance(result, dict):
            continue
        limitations = "; ".join(text(item) for item in as_list(result.get("limitations")) if text(item))
        handling = text(result.get("research_pack_handling"))
        reviewed_note = text(result.get("findings_summary")) or handling or text(result.get("status"))
        lines.append(
            "| "
            + " | ".join(
                [
                    pipe(result.get("result_id")),
                    pipe(result.get("research_thread") or result.get("issue_area")),
                    pipe(result.get("thread_focus") or result.get("subissue")),
                    pipe(result.get("research_question")),
                    pipe(reviewed_note),
                    pipe(join_values(result.get("source_review_ids"))),
                    pipe(join_values(result.get("evidence_ids"))),
                    pipe(join_values(result.get("metric_ids"))),
                    pipe(limitations),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "---",
            "",
            "## Source Extracts",
            "",
            "| Result ID | Source Review ID | Source URL | Locator | Reviewed Excerpt / Paraphrase | Extracted Fact Or Metric Candidate | Review Note | Promoted EV/MET IDs | Limitations |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for extract in as_list(db.get("formal_research_extracts")):
        if not isinstance(extract, dict):
            continue
        promoted = join_values(extract.get("promoted_evidence_ids"))
        metrics = join_values(extract.get("promoted_metric_ids"))
        if promoted and metrics:
            promoted = f"{promoted} / {metrics}"
        elif metrics:
            promoted = metrics
        lines.append(
            "| "
            + " | ".join(
                [
                    pipe(extract.get("result_id")),
                    pipe(extract.get("source_review_id")),
                    pipe(extract.get("source_url")),
                    pipe(extract.get("source_locator")),
                    pipe(extract.get("reviewed_excerpt_or_paraphrase")),
                    pipe(extract.get("extracted_fact_or_metric_candidate")),
                    pipe(extract.get("status")),
                    pipe(promoted),
                    pipe("; ".join(text(item) for item in as_list(extract.get("limitations")) if text(item))),
                ]
            )
            + " |"
        )
    lines.extend(["", "---", "", "## Page Evidence Inventory", "", "| Research Thread | Focus | Evidence IDs | Metric IDs | Evidence Readiness Note | Notes |", "|---|---|---|---|---|---|"])
    for row in as_list(db.get("page_evidence_inventory")):
        if not isinstance(row, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    pipe(row.get("research_thread") or row.get("issue_area")),
                    pipe(row.get("thread_focus") or row.get("subissue")),
                    pipe(join_values(row.get("evidence_ids"))),
                    pipe(join_values(row.get("metric_ids"))),
                    pipe(row.get("fact_status")),
                    pipe(row.get("notes")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Source Materials",
            "",
            "| Source ID | Source Name | Type | Date / Geography | URL / Path | Locator | Reviewed Excerpt | Source Use Notes |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for idx, source in enumerate(as_list(db.get("source_materials")), start=1):
        if not isinstance(source, dict):
            continue
        source_notes = "; ".join(
            part
            for part in (
                text(source.get("claim_use_scope")),
                text(source.get("source_reliability")),
                text(source.get("limitations")),
                text(source.get("archive_status")),
            )
            if part
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    pipe(source.get("source_review_id") or f"SRC-{idx:03d}"),
                    pipe(source.get("source_name")),
                    pipe(source.get("source_type")),
                    pipe(" / ".join(part for part in (text(source.get("source_date")), text(source.get("geography"))) if part)),
                    pipe(source.get("source_url") or source.get("source_access_path")),
                    pipe(source.get("source_locator")),
                    pipe(source.get("reviewed_excerpt")),
                    pipe(source_notes),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "---",
            "",
            "## Research Context",
            "",
            "| Context ID | Research Thread | Thread Focus | Topic | Summary | Source Review IDs | Search Attempt IDs | Confidence | Limitations |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in as_list(db.get("research_context")):
        if not isinstance(row, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    pipe(row.get("context_id")),
                    pipe(row.get("research_thread") or row.get("issue_area")),
                    pipe(row.get("thread_focus") or row.get("subissue")),
                    pipe(row.get("topic")),
                    pipe(row.get("summary")),
                    pipe(join_values(row.get("source_review_ids"))),
                    pipe(join_values(row.get("search_attempt_ids"))),
                    pipe(row.get("confidence")),
                    pipe(row.get("limitations")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "---",
            "",
            "## Evidence Notes",
            "Use EV rows only when the exact claim or datapoint has reviewed source context and recorded scope, period, geography, unit, and limitations.",
            "",
            "## Evidence Ledger",
            "",
            "| Evidence ID | Claim / Metric | Use Scope | Source Name | Source URL | Source Type | Review Note | Source Date | Data Period | Source Locator | Raw Excerpt | Reliability Note | Confidence Note |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in as_list(db.get("evidence_ledger")):
        if not isinstance(row, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    pipe(row.get("evidence_id")),
                    pipe(row.get("claim_or_metric")),
                    pipe(row.get("claim_scope")),
                    pipe(row.get("source_name")),
                    pipe(row.get("source_url")),
                    pipe(row.get("source_type")),
                    pipe(row.get("evidence_status")),
                    pipe(row.get("source_date")),
                    pipe(row.get("data_period")),
                    pipe(row.get("source_locator")),
                    pipe(row.get("raw_excerpt")),
                    pipe(row.get("reliability")),
                    pipe(row.get("confidence")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Metric Audit Table",
            "",
            "| Metric Group | Metric ID | Metric Name | Metric Type | Market Definition | Channel Scope | Geography | Data Period | Value | Unit | Comparable With | Parent Metric | CAGR Inputs | Conflict / Comparability Note | Working Treatment | Exhibit Use | Metric Evidence Level | Source Name | Source URL | Source Type | Source Locator | Raw Excerpt | Audit Note |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in as_list(db.get("metric_reconciliation")):
        if not isinstance(row, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    pipe(row.get("metric_group")),
                    pipe(row.get("metric_id")),
                    pipe(row.get("metric_name")),
                    pipe(row.get("metric_type")),
                    pipe(row.get("market_definition")),
                    pipe(row.get("channel_scope")),
                    pipe(row.get("geography")),
                    pipe(row.get("data_period")),
                    pipe(row.get("value")),
                    pipe(row.get("unit")),
                    pipe(row.get("comparable_with")),
                    pipe(row.get("parent_metric_id")),
                    pipe(row.get("cagr_endpoint_ids")),
                    pipe(row.get("conflict_status")),
                    pipe(row.get("resolution")),
                    "usable in sourced exhibit" if row.get("chart_ready") is True else "use in prose/table only until reviewed",
                    pipe(text(row.get("audit_level") or AUDITED_METRIC_LEVEL).replace("_", " ")),
                    pipe(row.get("source_name")),
                    pipe(row.get("source_url") or row.get("source_access_path")),
                    pipe(row.get("source_type")),
                    pipe(row.get("source_locator")),
                    pipe(row.get("raw_excerpt")),
                    pipe(row.get("audit_note")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Known Transaction-Relevant Observations",
            *[f"- {text(item)}" for item in as_list(db.get("known_transaction_relevant_observations"))],
            "",
            "## Known Risks or Open Questions",
            *[f"- {text(item)}" for item in as_list(db.get("known_risks_or_limits"))],
            "",
            "## Management-Provided Claims To Verify",
            *[f"- {text(item)}" for item in as_list(db.get("management_provided_claims_to_verify"))],
            "",
            "## Peer Set",
            *[f"- {text(item)}" for item in as_list(db.get("peer_set"))],
            "",
            "## Additional Sector-Specific Notes",
            text(db.get("additional_sector_specific_notes")) or "Insufficient data",
            "",
            "## Research Gap Audit",
            "",
            "### Critical Gaps",
        ]
    )
    gap_audit = db.get("research_gap_audit") if isinstance(db.get("research_gap_audit"), dict) else {}
    critical_gaps = [text(item) for item in as_list(gap_audit.get("critical_gaps")) if text(item)]
    lines.extend([f"- {item}" for item in critical_gaps] or ["- None"])
    lines.extend(["", "### Optional Gaps"])
    lines.extend([f"- {text(item)}" for item in as_list(gap_audit.get("optional_gaps")) if text(item)] or ["- None"])
    lines.extend(["", "### Intentionally Excluded Topics"])
    lines.extend([f"- {text(item)}" for item in as_list(gap_audit.get("intentionally_excluded_topics")) if text(item)] or ["- None"])
    metric_check = gap_audit.get("metric_consistency_check")
    lines.extend(["", "### Metric Consistency Check"])
    if isinstance(metric_check, dict):
        rendered = [
            f"- {text(key)}: {text(value)}"
            for key, value in metric_check.items()
            if text(key) and text(value)
        ]
    elif isinstance(metric_check, list):
        rendered = [f"- {text(item)}" for item in metric_check if text(item)]
    elif text(metric_check):
        rendered = [f"- {text(metric_check)}"]
    else:
        rendered = []
    lines.extend(rendered or ["- None"])
    lines.append("")
    return "\n".join(lines)


def cli_build(args: argparse.Namespace) -> int:
    payload = build_db(
        input_card=load_optional_json(args.input_card),
        scope_pack=load_optional_json(args.scope_pack),
        formal_search_plan=load_optional_json(args.formal_search_plan),
        execution_report=load_optional_json(args.formal_research_execution_report),
        source_reviews={},
        source_archive_index=load_optional_json(args.source_archive_index),
        research_graph_state=load_optional_json(args.research_graph_state),
        material_manifest=load_optional_json(args.material_manifest),
        material_extracts=load_optional_json(args.material_extracts),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "is_valid": True,
                "output": str(output_path),
                "source_material_count": len(payload.get("source_materials") or []),
                "formal_extract_count": len(payload.get("formal_research_extracts") or []),
                "promoted_evidence_row_count": len(payload.get("evidence_ledger") or []),
                "promoted_metric_row_count": len(payload.get("metric_reconciliation") or []),
                "note": "Candidate workspace contains extracted leads and TODO markers. Knowledge LLM must promote supported EV/MET rows, then validate and export industry_research_pack.md.",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cli_export(args: argparse.Namespace) -> int:
    db_path = Path(args.research_evidence_db)
    payload = load_json_file(db_path)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(export_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {"is_valid": True, "research_evidence_db": str(db_path), "output": str(output_path)},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Internal pipeline helper for the Knowledge evidence workspace. These commands are deterministic; "
            "the Knowledge LLM authors final EV/MET content and source-use limits."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser(
        "prepare-workspace",
        help=(
            "Prepare a candidate research_evidence_db.json workspace from formal research artifacts; "
            "LLM must author final EV/MET rows."
        ),
    )
    build_parser.add_argument("--input-card", required=True)
    build_parser.add_argument("--scope-pack", required=True)
    build_parser.add_argument("--formal-search-plan", required=True)
    build_parser.add_argument("--formal-research-execution-report", required=True)
    build_parser.add_argument("--source-archive-index", required=True)
    build_parser.add_argument("--research-graph-state", required=True)
    build_parser.add_argument("--material-manifest")
    build_parser.add_argument("--material-extracts")
    build_parser.add_argument("--output", required=True)
    build_parser.set_defaults(func=cli_build)

    export_parser = subparsers.add_parser("export", help="Export industry_research_pack.md from research_evidence_db.json.")
    export_parser.add_argument("--research-evidence-db", required=True)
    export_parser.add_argument("--output", required=True)
    export_parser.set_defaults(func=cli_export)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
