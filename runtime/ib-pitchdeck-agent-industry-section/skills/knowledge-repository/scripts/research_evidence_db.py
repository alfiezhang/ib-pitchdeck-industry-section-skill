"""Research evidence database helpers.

The JSON database is the source of truth for research evidence. The Markdown
research pack is a readable export generated from this database.
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

import re
from datetime import date
from pathlib import Path
from typing import Any

from issue_taxonomy import ISSUE_TOPICS_BY_AREA
from json_utils import load_json_file
from source_classification import CANONICAL_SOURCE_TYPES, is_material_type, normalize_source_type


EV_RE = re.compile(r"^EV-\d{3}$")
MET_RE = re.compile(r"^MET-\d{3}$")
NO_EVIDENCE_TERMINAL_STATUSES = {"not_executed", "not_material", "accounting_only"}
EVIDENCE_TERMINAL_STATUS = "executed_with_evidence"
PLACEHOLDER_MARKERS = (
    "TODO",
    "TODO_REPLACE",
    "LLM must",
    "LLM MUST",
    "replace with",
    "placeholder",
    "skeleton",
    "占位",
)


def text(value: Any) -> str:
    return str(value or "").strip()


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
        "evidence_use_tier": text(entry.get("evidence_use_tier") or "candidate"),
        "claim_use_scope": text(entry.get("claim_use_scope") or "Archived source; LLM must review exact claim-use scope before promotion."),
        "usable_as_evidence": entry.get("usable_as_evidence") if isinstance(entry.get("usable_as_evidence"), bool) else False,
        "review_status": text(entry.get("review_status") or "needs_llm_source_review"),
        "limitations": text(entry.get("limitations") or entry.get("archive_unavailable_reason")),
        "archive_status": text(entry.get("archive_status")),
        "archive_path": text(entry.get("archive_path")),
        "source_date": text(entry.get("source_date")),
        "geography": text(entry.get("geography")),
        "data_period": text(entry.get("data_period")),
        "methodology_locator": text(entry.get("methodology_locator")),
    }


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


def meta_from_inputs(input_card: dict[str, Any], scope_pack: dict[str, Any]) -> dict[str, str]:
    input_meta = input_card.get("meta") if isinstance(input_card.get("meta"), dict) else {}
    scope_meta = scope_pack.get("meta") if isinstance(scope_pack.get("meta"), dict) else {}
    return {
        "target_company": text(input_card.get("target_company") or input_meta.get("target_company") or scope_meta.get("target_company")),
        "transaction_type": text(input_card.get("transaction_type") or input_meta.get("transaction_type") or scope_meta.get("transaction_type")),
        "industry": text(input_card.get("industry") or input_meta.get("industry") or scope_meta.get("industry")),
        "subsector": text(input_card.get("subsector") or input_meta.get("subsector") or scope_meta.get("subsector")),
        "geography": text(input_card.get("geography") or input_meta.get("geography") or scope_meta.get("geography")),
        "language": text(input_card.get("language") or input_meta.get("language") or scope_meta.get("language") or "English"),
        "prepared_date": date.today().isoformat(),
        "research_as_of_date": text(input_meta.get("research_as_of_date") or scope_meta.get("research_as_of_date") or date.today().isoformat()),
    }


def issue_fact_status(result: dict[str, Any]) -> str:
    status = text(result.get("status"))
    has_ids = bool(as_list(result.get("evidence_ids")) or as_list(result.get("metric_ids")))
    if status == "supported" and has_ids:
        return "sufficient"
    if status in {"supported", "thin"} and has_ids:
        return "thin"
    if status == "unavailable_after_research":
        return "unavailable_after_research"
    if status == "not_comparable":
        return "thin" if has_ids else "insufficient"
    return "insufficient"


def result_by_pair(execution_report: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    output: dict[tuple[str, str], dict[str, Any]] = {}
    for item in as_list(execution_report.get("issue_results")):
        if not isinstance(item, dict):
            continue
        area = text(item.get("issue_area"))
        subissue = text(item.get("subissue"))
        if area and subissue:
            output[(area, subissue)] = item
    return output


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
    repository_sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    meta = meta_from_inputs(input_card, scope_pack)
    scope_summary = scope_pack.get("scope_summary") if isinstance(scope_pack.get("scope_summary"), dict) else {}
    embedded_review_rows = merged_reviews(source_reviews=source_reviews, source_archive_index=source_archive_index)
    embedded_source_reviews = {
        "schema_version": "embedded_source_reviews_v1",
        "source_of_truth": "artifacts/research_evidence_db.json",
        "policy": "Review status and evidence usability are LLM/QC judgments stored inside the evidence DB. Standalone source_reviews.json is legacy/diagnostic only.",
        "reviews": embedded_review_rows,
    }
    review_map = {review_id(item): item for item in embedded_review_rows if review_id(item)}

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
                "claim_use_scope": "Material intake only until extracted and reconciled.",
                "usable_as_evidence": False,
                "source_url": source_access_path if text(item.get("material_kind")) == "url" else "",
                "source_locator": source_access_path,
                "reviewed_excerpt": reviewed_excerpt,
                "limitations": "Material intake record; promote through extraction/review before claim use.",
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
                "claim_use_scope": text(item.get("claim_use_scope")),
                "usable_as_evidence": item.get("usable_as_evidence"),
                "source_url": review_url(item),
                "source_locator": review_locator(item),
                "reviewed_excerpt": review_excerpt(item),
                "limitations": text(item.get("limitations")),
                "archive_status": text(item.get("archive_status")),
                "archive_path": text(item.get("archive_path")),
                "review_status": text(item.get("review_status")),
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
                "content_capture_status": text(item.get("content_capture_status")),
                "llm_extraction_status": text(item.get("llm_extraction_status")),
                "can_be_used_as_evidence": bool(item.get("can_be_used_as_evidence")),
                "extracted_facts": as_list(item.get("extracted_facts")),
                "extracted_metrics": as_list(item.get("extracted_metrics")),
                "quoted_excerpts": as_list(item.get("quoted_excerpts")),
                "unknowns_or_conflicts": as_list(item.get("unknowns_or_conflicts")),
                "claim_use_limitations": text(item.get("claim_use_limitations")),
            }
        )

    for item in _repository_sources_to_source_material_rows(repository_sources or [], source_ids={item["source_review_id"] for item in source_materials}):
        source_materials.append(item)
    evidence_seen: set[str] = set()
    metric_seen: set[str] = set()
    evidence_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
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
                "issue_area": text(result.get("issue_area")),
                "subissue": text(result.get("subissue")),
                "research_question": text(result.get("research_question")),
                "status": text(result.get("status")),
                "terminal_status": terminal_status,
                "downstream_permission": downstream_permission,
                "minimum_actual_searches": result.get("minimum_actual_searches"),
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
        if terminal_status in NO_EVIDENCE_TERMINAL_STATUSES:
            critical_gap_rows.append(
                f"{result_id} {text(result.get('issue_area'))}/{text(result.get('subissue'))}: "
                f"{terminal_status}; not eligible for evidence promotion until actual formal search/source review exists."
            )
        elif terminal_status != EVIDENCE_TERMINAL_STATUS:
            optional_gap_rows.append(
                f"{result_id} {text(result.get('issue_area'))}/{text(result.get('subissue'))}: "
                f"{terminal_status or text(result.get('status'))}; keep as contextual/gap unless stronger sources are reviewed."
            )

        for src_id in source_review_ids:
            review = review_map.get(src_id, {})
            formal_extracts.append(
                {
                    "extract_id": f"FX-{len(formal_extracts) + 1:03d}",
                    "result_id": result_id,
                    "issue_area": text(result.get("issue_area")),
                    "subissue": text(result.get("subissue")),
                    "source_review_id": src_id,
                    "search_attempt_ids": search_attempt_ids,
                    "source_url": review_url(review),
                    "source_locator": review_locator(review),
                    "reviewed_excerpt_or_paraphrase": review_excerpt(review),
                    "extracted_fact_or_metric_candidate": "TODO_REPLACE_WITH_SOURCE_FAITHFUL_EXTRACT",
                    "status": text(result.get("status")),
                    "terminal_status": terminal_status,
                    "promoted_evidence_ids": evidence_ids if terminal_status == EVIDENCE_TERMINAL_STATUS else [],
                    "promoted_metric_ids": metric_ids if terminal_status == EVIDENCE_TERMINAL_STATUS else [],
                    "limitations": [text(item) for item in as_list(result.get("limitations")) if text(item)],
                }
            )
        primary_review = review_map.get(source_review_ids[0], {}) if source_review_ids else {}
        if terminal_status != EVIDENCE_TERMINAL_STATUS or not source_review_ids:
            continue
        for ev_id in evidence_ids:
            if ev_id in evidence_seen:
                continue
            evidence_seen.add(ev_id)
            evidence_rows.append(
                {
                    "evidence_id": ev_id,
                    "claim_or_metric": "TODO_REPLACE_WITH_PROMOTED_CLAIM",
                    "claim_scope": "industry-level",
                    "source_review_id": source_review_ids[0] if source_review_ids else "",
                    "source_name": review_title(primary_review),
                    "source_url": review_url(primary_review),
                    "source_type": text(primary_review.get("source_type")),
                    "evidence_status": "primary-reviewed" if text(result.get("status")) == "supported" else "secondary-reviewed",
                    "source_date": text(primary_review.get("source_date")),
                    "data_period": "",
                    "source_locator": review_locator(primary_review),
                    "raw_excerpt": review_excerpt(primary_review),
                    "reliability": text(primary_review.get("reliability") or primary_review.get("source_reliability")),
                    "confidence": "medium",
                }
            )
        for met_id in metric_ids:
            if met_id in metric_seen:
                continue
            metric_seen.add(met_id)
            metric_rows.append(
                {
                    "metric_group": text(result.get("issue_area")),
                    "metric_id": met_id,
                    "metric_name": "TODO_REPLACE_WITH_METRIC_NAME",
                    "metric_type": "TODO_REPLACE_WITH_METRIC_TYPE",
                    "market_definition": "TODO_REPLACE_WITH_MARKET_DEFINITION",
                    "channel_scope": "TODO_REPLACE_WITH_CHANNEL_SCOPE",
                    "geography": meta.get("geography", ""),
                    "data_period": "TODO_REPLACE_WITH_DATA_PERIOD",
                    "value": "TODO_REPLACE_WITH_VALUE",
                    "unit": "TODO_REPLACE_WITH_UNIT",
                    "comparable_with": "",
                    "parent_metric_id": "",
                    "cagr_endpoint_ids": "",
                    "conflict_status": "single-source",
                    "resolution": "TODO_REPLACE_WITH_RESOLUTION",
                    "chart_ready": False,
                }
            )

    results = result_by_pair(execution_report)
    inventory: list[dict[str, Any]] = []
    for area, subissues in ISSUE_TOPICS_BY_AREA.items():
        for subissue in sorted(subissues):
            result = results.get((area, subissue), {})
            inventory.append(
                {
                    "issue_area": area,
                    "subissue": subissue,
                    "evidence_ids": [text(item) for item in as_list(result.get("evidence_ids")) if text(item)],
                    "metric_ids": [text(item) for item in as_list(result.get("metric_ids")) if text(item)],
                    "fact_status": issue_fact_status(result) if result else "insufficient",
                    "notes": text(result.get("findings_summary")) if result else "No formal result found; keep as research gap until searched.",
                }
            )

    return {
        "schema_version": "research_evidence_db_v1",
        "source_of_truth": True,
        "authoring_policy": "LLM edits this database; industry_research_pack.md is generated from it and should not be hand-authored.",
        "meta": meta,
        "scope_summary": scope_summary,
        "formal_search_plan_summary": {
            "artifact_path": "artifacts/formal_search_plan.json",
            "issue_search_plan_count": len(as_list(formal_search_plan.get("issue_search_plan"))),
        },
        "formal_research_results": formal_results,
        "source_reviews": embedded_source_reviews,
        "material_extractions": material_extraction_rows,
        "formal_research_extracts": formal_extracts,
        "source_materials": source_materials,
        "evidence_ledger": evidence_rows,
        "metric_reconciliation": metric_rows,
        "issue_fact_inventory": inventory,
        "known_pitch_relevant_observations": [],
        "known_risks_or_open_questions": [],
        "management_provided_claims_to_verify": [],
        "peer_set": [],
        "additional_sector_specific_notes": "Insufficient data",
        "research_gap_audit": {
            "critical_gaps": [
                "Resolve before validation: replace TODO extracts, populate promoted evidence/metric fields, and update issue fact inventory from source-faithful evidence."
            ]
            + critical_gap_rows,
            "optional_gaps": optional_gap_rows,
            "intentionally_excluded_topics": [],
            "metric_consistency_check": {
                "GMV vs revenue": "",
                "Cross-slide repeated metric consistency": "",
                "Target financials consistency": "",
                "User-provided vs external-source discrepancy": "",
                "Chart number consistency": "",
            },
        },
    }


def _repository_sources_to_source_material_rows(
    repository_sources: list[dict[str, Any]], source_ids: set[str]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in repository_sources:
        source_id = text(item.get("source_id")) or text(item.get("normalized_key"))
        if not source_id:
            continue
        if source_id in source_ids:
            continue
        source_ids.add(source_id)
        rows.append(
            {
                "source_review_id": source_id,
                "material_id": source_id,
                "source_name": text(item.get("source_title") or item.get("source_path") or item.get("normalized_key")),
                "source_type": normalize_source_type(item.get("source_type") or "repository_retrieval"),
                "source_access": "repository_retrieval",
                "source_access_path": text(item.get("source_path") or item.get("normalized_key")),
                "source_date": text(item.get("time_period") or item.get("source_date")),
                "geography": text(item.get("geography")),
                "fact_type": "repository_import",
                "confidence": "unreviewed",
                "scope": text(item.get("scope") or ""),
                "source_reliability": text(item.get("source_quality") or item.get("source_reliability")),
                "evidence_use_tier": "repository_candidate",
                "claim_use_scope": "Needs re-review in current project",
                "usable_as_evidence": False,
                "source_url": text(item.get("source_path") or item.get("normalized_key")),
                "source_locator": text(item.get("source_path") or ""),
                "reviewed_excerpt": text(item.get("reviewed_excerpt") or item.get("snapshot_excerpt")),
                "limitations": text(
                    "; ".join(item.get("reuse_limitations", []))
                    if isinstance(item.get("reuse_limitations"), list)
                    else item.get("reuse_limitations")
                )
                or "repository retrieval; re-review required for current project",
            }
        )
    return rows


def contains_placeholder(value: Any) -> bool:
    return any(marker in str(value or "") for marker in PLACEHOLDER_MARKERS)


def validate_db(db: dict[str, Any]) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    if db.get("schema_version") != "research_evidence_db_v1":
        errors.append("schema_version must be research_evidence_db_v1")
    if db.get("source_of_truth") is not True:
        errors.append("source_of_truth must be true")

    meta = db.get("meta") if isinstance(db.get("meta"), dict) else {}
    for field in ("target_company", "industry", "geography", "research_as_of_date"):
        if not text(meta.get(field)):
            errors.append(f"meta.{field} is required")

    source_ids = set()
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
        source_type = text(source.get("source_type"))
        normalized_source_type = normalize_source_type(source_type)
        if not source_type:
            errors.append(f"{src_id}: source_materials.source_type is required")
        elif normalized_source_type not in CANONICAL_SOURCE_TYPES:
            warnings.append(
                f"{src_id}: source_type '{source_type}' normalized to 'other'; use one of {sorted(CANONICAL_SOURCE_TYPES)} if possible"
            )
        if text(source.get("source_access")) not in {"", "user_provided", "public_search", "repository_retrieval"}:
            warnings.append(f"{src_id}: source_materials.source_access should be one of user_provided/public_search/repository_retrieval")
        for field in ("source_url", "source_locator", "reviewed_excerpt", "source_name"):
            if not text(source.get(field)):
                warnings.append(f"{src_id}: source_materials.{field} is empty")
        if is_material_type(source_type) and not source.get("source_access_path") and source_type not in {"", "other"} and text(source.get("source_url", "")).lower() in {"", "user-provided"}:
            warnings.append(
                f"{src_id}: source_materials.source_access_path missing for material source; add file path / URL / locator source path"
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

    ev_ids: set[str] = set()
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
        normalized_source_type = normalize_source_type(source_type)
        if not source_type:
            errors.append(f"{ev_id}: source_type is required")
        elif normalized_source_type not in CANONICAL_SOURCE_TYPES:
            warnings.append(
                f"{ev_id}: source_type '{source_type}' normalized to 'other'; use one of {sorted(CANONICAL_SOURCE_TYPES)} if possible"
            )
        for field in ("claim_or_metric", "claim_scope", "source_name", "source_url", "source_type", "evidence_status", "source_locator", "raw_excerpt", "reliability", "confidence"):
            if not text(row.get(field)):
                errors.append(f"{ev_id}: {field} is required")
            elif contains_placeholder(row.get(field)):
                errors.append(f"{ev_id}: {field} still contains placeholder text")
        if text(row.get("claim_scope")) not in {"industry-level", "target-level", "transaction-inference"}:
            errors.append(f"{ev_id}: claim_scope must be industry-level, target-level, or transaction-inference")
        if text(row.get("evidence_status")) not in {"primary-reviewed", "secondary-reviewed", "lead-only"}:
            errors.append(f"{ev_id}: evidence_status must be primary-reviewed, secondary-reviewed, or lead-only")
        src_id = text(row.get("source_review_id"))
        if not src_id:
            errors.append(f"{ev_id}: source_review_id is required")
        elif src_id not in source_ids:
            errors.append(f"{ev_id}: source_review_id {src_id} not found in source_materials")
        source_result = ev_to_result.get(ev_id)
        if source_result and text(source_result.get("terminal_status")) != EVIDENCE_TERMINAL_STATUS:
            errors.append(
                f"{ev_id}: linked formal result {text(source_result.get('result_id'))} is "
                f"terminal_status={text(source_result.get('terminal_status'))}; only executed_with_evidence may promote EV rows"
            )
    if not ev_ids:
        errors.append("evidence_ledger must contain at least one promoted EV row")

    met_ids: set[str] = set()
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
        for field in ("metric_group", "metric_name", "metric_type", "market_definition", "channel_scope", "geography", "data_period", "value", "unit", "conflict_status", "resolution"):
            if not text(row.get(field)):
                errors.append(f"{met_id}: {field} is required")
            elif contains_placeholder(row.get(field)):
                errors.append(f"{met_id}: {field} still contains placeholder text")
        source_result = met_to_result.get(met_id)
        if source_result and text(source_result.get("terminal_status")) != EVIDENCE_TERMINAL_STATUS:
            errors.append(
                f"{met_id}: linked formal result {text(source_result.get('result_id'))} is "
                f"terminal_status={text(source_result.get('terminal_status'))}; only executed_with_evidence may promote MET rows"
            )

    inventory_rows = [row for row in as_list(db.get("issue_fact_inventory")) if isinstance(row, dict)]
    if not inventory_rows:
        errors.append("issue_fact_inventory must contain canonical issue/subissue rows")
    sufficient_or_thin = 0
    for idx, row in enumerate(inventory_rows, start=1):
        area = text(row.get("issue_area"))
        subissue = text(row.get("subissue"))
        status = text(row.get("fact_status"))
        prefix = f"issue_fact_inventory[{idx}]"
        if area not in ISSUE_TOPICS_BY_AREA:
            errors.append(f"{prefix}: invalid issue_area {area!r}")
        elif subissue not in ISSUE_TOPICS_BY_AREA.get(area, set()):
            errors.append(f"{prefix}: subissue {subissue!r} does not belong to issue_area {area!r}")
        if status not in {"sufficient", "thin", "insufficient", "not_applicable", "unavailable_after_research"}:
            errors.append(f"{prefix}: invalid fact_status {status!r}")
        if status in {"sufficient", "thin"}:
            sufficient_or_thin += 1
            missing_ev = sorted(set(text(item) for item in as_list(row.get("evidence_ids")) if text(item)) - ev_ids)
            missing_met = sorted(set(text(item) for item in as_list(row.get("metric_ids")) if text(item)) - met_ids)
            if missing_ev:
                errors.append(f"{prefix}: Evidence IDs not found in evidence_ledger: {', '.join(missing_ev)}")
            if missing_met:
                errors.append(f"{prefix}: Metric IDs not found in metric_reconciliation: {', '.join(missing_met)}")
            if not as_list(row.get("evidence_ids")) and not as_list(row.get("metric_ids")):
                errors.append(f"{prefix}: {status} fact_status requires evidence_ids or metric_ids")
    if sufficient_or_thin == 0:
        warnings.append("issue_fact_inventory has no sufficient/thin rows; issue analysis will likely be thin")

    gap_audit = db.get("research_gap_audit") if isinstance(db.get("research_gap_audit"), dict) else {}
    metric_check = gap_audit.get("metric_consistency_check") if isinstance(gap_audit.get("metric_consistency_check"), dict) else {}
    for label in (
        "GMV vs revenue",
        "Cross-slide repeated metric consistency",
        "Target financials consistency",
        "User-provided vs external-source discrepancy",
        "Chart number consistency",
    ):
        if not text(metric_check.get(label)):
            errors.append(f"research_gap_audit.metric_consistency_check.{label} is required")

    metrics = {
        "source_material_count": len(source_ids),
        "formal_extract_count": extract_count,
        "evidence_ledger_row_count": len(ev_ids),
        "metric_reconciliation_row_count": len(met_ids),
        "issue_fact_inventory_row_count": len(inventory_rows),
    }
    return errors, warnings, metrics


def export_markdown(db: dict[str, Any]) -> str:
    meta = db.get("meta") if isinstance(db.get("meta"), dict) else {}
    scope = db.get("scope_summary") if isinstance(db.get("scope_summary"), dict) else {}
    lines: list[str] = [
        "# industry research evidence pack",
        "",
        "> Generated readable export from `artifacts/research_evidence_db.json`. Edit the JSON database, then regenerate this Markdown pack.",
        "",
        "## Project Meta",
        f"Target Company: {text(meta.get('target_company'))}",
        f"Transaction Type: {text(meta.get('transaction_type'))}",
        f"Industry: {text(meta.get('industry'))}",
        f"Subsector: {text(meta.get('subsector'))}",
        f"Geography: {text(meta.get('geography'))}",
        f"Output Language: {text(meta.get('language'))}",
        f"Prepared Date: {text(meta.get('prepared_date'))}",
        f"Research As-Of Date: {text(meta.get('research_as_of_date'))}",
        "User Material Data Cutoff:",
        "research pack Version: generated_from_research_evidence_db_v1",
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
        f"Engagement Context: {text(meta.get('engagement_context') or meta.get('stage') or 'pre_mandate_client_pitch')}",
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
        "- LLM definition draft: See artifacts/industry_scope_pack.json",
        "- Scoping search queries used to verify/refine draft: See artifacts/search_log.md broad_discovery entries",
        f"- Relevant market: {pipe(scope.get('working_market'))}",
        f"- Parent market: {pipe(scope.get('parent_market'))}",
        f"- Sub-markets: {pipe(', '.join(as_list(scope.get('sub_markets'))))}",
        f"- Excluded scope: {pipe(', '.join(as_list(scope.get('excluded_scope'))))}",
        "- Ambiguous definitions requiring validation: See artifacts/industry_scope_pack.json",
        "",
        "Project Classification:",
        "- Sector type:",
        f"- Transaction type: {text(meta.get('transaction_type'))}",
        "- Target business model:",
        "- Likely buyer / investor angle:",
        "- Key transaction question:",
        "",
        "Formal Research Execution Results:",
        "| Result ID | Issue Area | Subissue | Research Question | Status | Terminal Status | Downstream Permission | Search Attempt IDs | Source Review IDs | Evidence IDs | Metric IDs | Limitations / Research Pack Handling |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for result in as_list(db.get("formal_research_results")):
        if not isinstance(result, dict):
            continue
        limitations = "; ".join(text(item) for item in as_list(result.get("limitations")) if text(item))
        handling = text(result.get("research_pack_handling"))
        lines.append(
            "| "
            + " | ".join(
                [
                    pipe(result.get("result_id")),
                    pipe(result.get("issue_area")),
                    pipe(result.get("subissue")),
                    pipe(result.get("research_question")),
                    pipe(result.get("status")),
                    pipe(result.get("terminal_status")),
                    pipe(result.get("downstream_permission")),
                    pipe(join_values(result.get("search_attempt_ids"))),
                    pipe(join_values(result.get("source_review_ids"))),
                    pipe(join_values(result.get("evidence_ids"))),
                    pipe(join_values(result.get("metric_ids"))),
                    pipe("; ".join(part for part in (limitations, handling) if part)),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "---",
            "",
            "## Formal Research Extracts",
            "",
            "| Result ID | Source Review ID | Search Attempt IDs | Source URL | Locator | Reviewed Excerpt / Paraphrase | Extracted Fact Or Metric Candidate | Status | Promoted EV/MET IDs | Limitations |",
            "|---|---|---|---|---|---|---|---|---|---|",
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
                    pipe(join_values(extract.get("search_attempt_ids"))),
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
    lines.extend(["", "---", "", "## IB Issue Fact Inventory", "", "| Issue Area | Subissue | Evidence IDs | Metric IDs | Fact Status | Notes |", "|---|---|---|---|---|---|"])
    for row in as_list(db.get("issue_fact_inventory")):
        if not isinstance(row, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    pipe(row.get("issue_area")),
                    pipe(row.get("subissue")),
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
            "Allowed `Fact Status`: `sufficient`, `thin`, `insufficient`, `not_applicable`, `unavailable_after_research`.",
            "",
            "## Deal Context",
            "",
            "## Target Business Summary",
            "",
            "## Industry Definition",
            f"Working Market: {pipe(scope.get('working_market'))}",
            f"Parent Market: {pipe(scope.get('parent_market'))}",
            f"Broader Market: {pipe(scope.get('broader_market'))}",
            "",
            "## Source Materials",
            "",
            "### Provided Material Sources",
            "",
            "### Online Research Sources",
            "",
        ]
    )
    for idx, source in enumerate(as_list(db.get("source_materials")), start=1):
        if not isinstance(source, dict):
            continue
        lines.extend(
            [
                f"#### Source {idx}",
                f"Source Review ID: {text(source.get('source_review_id'))}",
                f"Source Name: {text(source.get('source_name'))}",
                f"Source Type: {text(source.get('source_type'))}",
                f"Source Date: {text(source.get('source_date'))}",
                f"Geography: {text(source.get('geography'))}",
                f"Source Reliability: {text(source.get('source_reliability'))}",
                f"Evidence Use Tier: {text(source.get('evidence_use_tier'))}",
                f"Claim Use Scope: {text(source.get('claim_use_scope'))}",
                f"Usable As Evidence: {text(source.get('usable_as_evidence'))}",
                f"URL: {text(source.get('source_url'))}",
                f"Locator: {text(source.get('source_locator'))}",
                f"Reviewed Excerpt: {text(source.get('reviewed_excerpt'))}",
                f"Notes: {text(source.get('limitations'))}",
                "",
            ]
        )
    lines.extend(
        [
            "---",
            "",
            "## Evidence Promotion Gate",
            "A source can be promoted into the Evidence Ledger only after the exact claim/datapoint has been located in the reviewed source context and its scope, period, geography, unit, and limitation are recorded.",
            "",
            "## Evidence Ledger",
            "",
            "| Evidence ID | Claim / Metric | Claim Scope | Source Name | Source URL | Source Type | Evidence Status | Source Date | Data Period | Source Locator | Raw Excerpt | Reliability | Confidence |",
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
            "## Metric Reconciliation",
            "",
            "| Metric Group | Metric ID | Metric Name | Metric Type | Market Definition | Channel Scope | Geography | Data Period | Value | Unit | Comparable With | Parent Metric ID | CAGR Endpoint IDs | Conflict Status | Resolution | Chart Ready |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
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
                    "true" if row.get("chart_ready") is True else "false",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Known Pitch-Relevant Observations",
            *[f"- {text(item)}" for item in as_list(db.get("known_pitch_relevant_observations"))],
            "",
            "## Known Risks or Open Questions",
            *[f"- {text(item)}" for item in as_list(db.get("known_risks_or_open_questions"))],
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
    metric_check = gap_audit.get("metric_consistency_check") if isinstance(gap_audit.get("metric_consistency_check"), dict) else {}
    lines.extend(
        [
            "",
            "### Metric Consistency Check",
            f"- GMV vs revenue: {text(metric_check.get('GMV vs revenue'))}",
            f"- Cross-slide repeated metric consistency: {text(metric_check.get('Cross-slide repeated metric consistency'))}",
            f"- Target financials consistency: {text(metric_check.get('Target financials consistency'))}",
            f"- User-provided vs external-source discrepancy: {text(metric_check.get('User-provided vs external-source discrepancy'))}",
            f"- Chart number consistency: {text(metric_check.get('Chart number consistency'))}",
            "",
        ]
    )
    return "\n".join(lines)
