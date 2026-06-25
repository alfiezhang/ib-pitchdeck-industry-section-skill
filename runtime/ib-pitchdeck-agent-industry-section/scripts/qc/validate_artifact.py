#!/usr/bin/env python3
"""Unified deterministic validator for the industry-section workflow.

This script deliberately checks only mechanical conditions: files exist, JSON is
parseable, IDs and cross-references are coherent, and renderer/PPT inputs can be
used by deterministic tooling. Content quality, page density, source judgment,
and pitch relevance are LLM responsibilities.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
RUNTIME_ROOT = next(
    parent for parent in Path(__file__).resolve().parents
    if (parent / "configs").is_dir() and (parent / "scripts").is_dir()
)
for path in [
    RUNTIME_ROOT / "scripts",
    RUNTIME_ROOT / "scripts" / "_lib",
    RUNTIME_ROOT / "scripts" / "knowledge-repository",
]:
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from deck_blueprint_utils import (
    FIXED_PAGE_ROLES,
    PAGE_PRIMARY_SUBJECTS,
    STRUCTURED_EXHIBIT_TYPES,
    VALID_CLAIM_STRENGTHS,
    as_list,
    banker_page_id_for_slide,
    unique,
)
from json_utils import load_json_file
from material_intake_common import normalize_source_type
from renderer_token_source import build_token_source
from research_evidence_db import validate_db as validate_research_db
from template_contract_utils import required_body_fields


EV_RE = re.compile(r"^EV-\d{3}$")
MET_RE = re.compile(r"^MET-\d{3}$")
BP_RE = re.compile(r"^BP-\d{3}$")
SRC_RE = re.compile(r"^SRC-\d{3}$")
BAD_PPT_GLYPHS = {"�", "□", "▯", "\ufffd"}


ARTIFACT_PATHS = {
    "material_manifest": "artifacts/material_manifest.json",
    "material_extracts": "artifacts/material_extracts.json",
    "input_card": "input_card.json",
    "industry_scope_pack": "artifacts/industry_scope_pack.json",
    "formal_search_plan": "artifacts/formal_search_plan.json",
    "executable_search_batch": "artifacts/executable_search_batch.json",
    "formal_research_execution": "artifacts/formal_research_execution_report.json",
    "source_archive": "artifacts/source_archive/source_archive_index.json",
    "research_evidence_db": "artifacts/research_evidence_db.json",
    "research_pack": "industry_research_pack.md",
    "research_request_queue": "artifacts/research_request_queue.json",
    "banker_page_pack": "banker_page_pack.json",
    "template_registry": "template_registry.json",
    "deck_blueprint": "deck_blueprint.json",
    "page_evidence_contract": "page_evidence_contract.json",
    "renderer_spec": "renderer_spec.json",
    "replacement_dict": "replacement_dict.json",
    "filled_ppt": "filled_ppt_validation.json",
    "pre_research_pack": "artifacts/stage_gate_pre_research_pack_validation.json",
    "pre_ppt": "artifacts/stage_gate_pre_ppt_validation.json",
    "final_delivery": "artifacts/final_delivery_validation.json",
}


VALIDATION_OUTPUTS = {
    "material_manifest": "artifacts/material_manifest_validation.json",
    "material_extracts": "artifacts/material_extracts_validation.json",
    "input_card": "artifacts/input_card_validation.json",
    "industry_scope_pack": "artifacts/industry_scope_pack_validation.json",
    "formal_search_plan": "artifacts/formal_search_plan_validation.json",
    "executable_search_batch": "artifacts/executable_search_batch_validation.json",
    "formal_research_execution": "artifacts/formal_research_execution_validation.json",
    "source_archive": "artifacts/source_archive_validation.json",
    "research_evidence_db": "artifacts/research_evidence_db_validation.json",
    "research_pack": "artifacts/research_pack_validation.json",
    "research_request_queue": "artifacts/research_request_queue_validation.json",
    "banker_page_pack": "artifacts/banker_page_pack_validation.json",
    "template_registry": "artifacts/template_registry_validation.json",
    "deck_blueprint": "artifacts/deck_blueprint_validation.json",
    "page_evidence_contract": "artifacts/page_evidence_contract_validation.json",
    "renderer_spec": "artifacts/renderer_spec_validation.json",
    "replacement_dict": "artifacts/replacement_dict_validation.json",
    "filled_ppt": "filled_ppt_validation.json",
    "pre_research_pack": "artifacts/stage_gate_pre_research_pack_validation.json",
    "pre_ppt": "artifacts/stage_gate_pre_ppt_validation.json",
    "final_delivery": "artifacts/final_delivery_validation.json",
}


def text(value: Any) -> str:
    return str(value or "").strip()


def _quality_rules() -> dict[str, Any]:
    path = RUNTIME_ROOT / "configs" / "content_quality_rules.json"
    try:
        payload = load_json_file(path)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _quality_list(key: str) -> list[str]:
    values = _quality_rules().get(key)
    return [text(item) for item in as_list(values) if text(item)]


def _advisory_target(key: str) -> int:
    targets = _quality_rules().get("qc_advisory_targets")
    if not isinstance(targets, dict):
        return 0
    try:
        return int(targets.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _min_chars(field_type: str) -> int:
    values = _quality_rules().get("min_chars_by_field_type")
    if not isinstance(values, dict):
        return 0
    try:
        return int(values.get(field_type) or 0)
    except (TypeError, ValueError):
        return 0


def _project_specific_source_types() -> set[str]:
    return set(_quality_list("project_specific_source_types"))


def _axis_chart_types() -> set[str]:
    return set(_quality_list("axis_chart_types"))


def _contains_target_context_terms(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_target_context_terms(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_target_context_terms(item) for item in value)
    value_text = text(value).lower()
    return any(term.lower() in value_text for term in _quality_list("target_context_terms"))


def _json(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"missing required file: {path}")
        return {}
    try:
        payload = load_json_file(path)
    except Exception as exc:
        errors.append(f"cannot read JSON {path}: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{path}: top-level JSON must be an object")
        return {}
    return payload


def _ids(payload: dict[str, Any], ledger_name: str, id_keys: tuple[str, ...]) -> set[str]:
    rows = payload.get(ledger_name)
    if not isinstance(rows, list):
        return set()
    result: set[str] = set()
    for row in rows:
        if isinstance(row, dict):
            for key in id_keys:
                value = text(row.get(key))
                if value:
                    result.add(value)
                    break
    return result


def _scan_ids(value: Any, key_names: set[str]) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in key_names:
                if isinstance(item, list):
                    found.extend(text(part) for part in item if text(part))
                elif text(item):
                    found.append(text(item))
            else:
                found.extend(_scan_ids(item, key_names))
    elif isinstance(value, list):
        for item in value:
            found.extend(_scan_ids(item, key_names))
    return unique(found)


def _project_specific_source(source: dict[str, Any] | None) -> bool:
    if not isinstance(source, dict):
        return False
    project_specific_types = _project_specific_source_types()
    source_type = normalize_source_type(source.get("source_type"))
    source_access = text(source.get("source_access"))
    source_name = text(source.get("source_name")).lower()
    source_url = text(source.get("source_url")).lower()
    if source_type in project_specific_types:
        return True
    if source_access == "user_provided" and source_type not in {"user_curated_industry_report", "industry_report", "official_filing", "database", "regulator"}:
        return True
    return source_url in {"", "user-provided"} and any(
        token.lower() in source_name for token in _quality_list("project_specific_source_name_tokens")
    )


def _metric_source_index(db: dict[str, Any]) -> dict[str, dict[str, Any]]:
    sources = {
        text(row.get("source_review_id")): row
        for row in as_list(db.get("source_materials"))
        if isinstance(row, dict) and text(row.get("source_review_id"))
    }
    result: dict[str, dict[str, Any]] = {}
    for row in as_list(db.get("metric_reconciliation")):
        if not isinstance(row, dict):
            continue
        metric_id = text(row.get("metric_id"))
        if metric_id:
            result[metric_id] = {
                "metric": row,
                "source": sources.get(text(row.get("source_review_id")), {}),
            }
    return result


def _chart_type(slide: dict[str, Any]) -> str:
    chart_data = slide.get("chart_data") if isinstance(slide.get("chart_data"), dict) else {}
    exhibit = slide.get("exhibit") if isinstance(slide.get("exhibit"), dict) else {}
    return text(chart_data.get("chart_type") or exhibit.get("exhibit_type")).lower()


def _chart_units(slide: dict[str, Any]) -> set[str]:
    chart_data = slide.get("chart_data") if isinstance(slide.get("chart_data"), dict) else {}
    units: set[str] = set()
    if text(chart_data.get("unit")):
        units.add(text(chart_data.get("unit")))
    for row in as_list(chart_data.get("source_rows")):
        if isinstance(row, dict):
            unit = text(row.get("unit") or row.get("value_unit"))
            if unit:
                units.add(unit)
    for row in as_list(chart_data.get("data_series")):
        if isinstance(row, dict):
            unit = text(row.get("unit") or row.get("value_unit"))
            if unit:
                units.add(unit)
    return units


def _slide_text_chars(slide: dict[str, Any]) -> int:
    parts = [
        text(slide.get("headline")),
        text(slide.get("main_message")),
        text(slide.get("page_argument")),
        text(slide.get("banker_judgment")),
        text(slide.get("source_note")),
    ]
    for block in as_list(slide.get("body_blocks")):
        if isinstance(block, dict):
            parts.append(text(block.get("copy")))
    body_copy = slide.get("body_copy")
    if isinstance(body_copy, dict):
        parts.extend(text(value) for value in body_copy.values())
    return sum(len(part) for part in parts if part)


def _structured_exhibit(slide: dict[str, Any]) -> bool:
    exhibit = slide.get("exhibit") if isinstance(slide.get("exhibit"), dict) else {}
    chart_data = slide.get("chart_data") if isinstance(slide.get("chart_data"), dict) else {}
    compare_table = slide.get("compare_table_data") if isinstance(slide.get("compare_table_data"), dict) else {}
    exhibit_type = text(exhibit.get("exhibit_type")).lower()
    if chart_data or compare_table:
        return True
    return exhibit_type in STRUCTURED_EXHIBIT_TYPES


def _ppt_slide_texts(pptx_path: Path) -> list[str]:
    with zipfile.ZipFile(pptx_path) as archive:
        slide_names = sorted(
            (name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
            key=lambda name: int(re.search(r"slide(\d+)\.xml", name).group(1)),  # type: ignore[union-attr]
        )
        texts: list[str] = []
        for name in slide_names:
            xml = archive.read(name).decode("utf-8", errors="replace")
            chunks = re.findall(r"<a:t[^>]*>(.*?)</a:t>", xml, flags=re.DOTALL)
            texts.append(" ".join(html.unescape(re.sub(r"<[^>]+>", "", chunk)) for chunk in chunks))
        return texts


def _slide_index(payload: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {
        int(slide.get("slide_no")): slide
        for slide in as_list(payload.get("slides"))
        if isinstance(slide, dict) and isinstance(slide.get("slide_no"), int)
    }


def _assert_artifact_report(path: Path, errors: list[str]) -> None:
    payload = _json(path, errors)
    if payload and payload.get("is_valid") is False:
        errors.append(f"{path.name} is_valid=false")


def validate_material_like(artifact: str, path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    if artifact == "input_card" and not (payload.get("raw_brief") or payload.get("explicit_user_facts") or payload.get("brief_text")):
        warnings.append("input_card has no obvious raw brief or explicit facts")


def _research_request_queue_policy() -> dict[str, Any]:
    try:
        payload = load_json_file(RUNTIME_ROOT / "configs" / "research_planning_policy.json")
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    policy = payload.get("research_request_queue")
    return policy if isinstance(policy, dict) else {}


def _policy_values(policy: dict[str, Any], key: str) -> set[str]:
    return {text(item) for item in as_list(policy.get(key)) if text(item)}


def validate_research_request_queue(path: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    if payload.get("schema_version") != "research_request_queue_v1":
        errors.append("research_request_queue must use schema_version research_request_queue_v1")
    if payload.get("authoring_mode") != "llm_authored":
        errors.append("research_request_queue.authoring_mode must be llm_authored; do not generate this artifact with a builder script")

    requests = payload.get("requests")
    if not isinstance(requests, list):
        errors.append("research_request_queue.requests must be a list")
        return
    if not requests:
        warnings.append("research_request_queue has no active requests")

    policy = _research_request_queue_policy()
    allowed_source_types = _policy_values(policy, "allowed_source_types")
    downstream_permissions = _policy_values(policy, "downstream_permissions")
    statuses = _policy_values(policy, "statuses")
    if not statuses:
        statuses = {text(policy.get("default_status")), "pending_public_evidence", "in_research", "resolved", "cancelled"}

    seen: set[str] = set()
    for idx, request in enumerate(requests, start=1):
        if not isinstance(request, dict):
            errors.append(f"research_request_queue.requests[{idx}] must be an object")
            continue
        request_id = text(request.get("request_id") or request.get("research_request_id"))
        if not re.fullmatch(r"RQ-\d{3}", request_id):
            errors.append(f"research_request_queue.requests[{idx}].request_id must look like RQ-001")
        elif request_id in seen:
            errors.append(f"duplicate research request id: {request_id}")
        seen.add(request_id)
        if not text(request.get("research_question")):
            errors.append(f"{request_id or f'request {idx}'} missing research_question")
        if not (
            text(request.get("origin_artifact"))
            or text(request.get("origin_ref_id"))
            or text(request.get("origin_issue_id"))
            or text(request.get("origin_page_argument_id"))
            or text(request.get("boundary_request_id"))
        ):
            errors.append(f"{request_id or f'request {idx}'} must cite its origin artifact or source ref")

        required_source_type = text(request.get("required_source_type"))
        if allowed_source_types and required_source_type not in allowed_source_types:
            errors.append(f"{request_id or f'request {idx}'} required_source_type is not allowed: {required_source_type}")
        minimum = request.get("minimum_actual_searches")
        if not isinstance(minimum, int) or minimum < 0:
            errors.append(f"{request_id or f'request {idx}'} minimum_actual_searches must be a non-negative integer")
        permission = text(request.get("downstream_permission_if_unresolved"))
        if downstream_permissions and permission not in downstream_permissions:
            errors.append(f"{request_id or f'request {idx}'} downstream_permission_if_unresolved is not allowed: {permission}")
        status = text(request.get("status"))
        if statuses and status not in statuses:
            errors.append(f"{request_id or f'request {idx}'} status is not allowed: {status}")
        if not text(request.get("success_criteria")):
            warnings.append(f"{request_id or f'request {idx}'} has no success_criteria")


def validate_scope(path: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    if payload.get("schema_version") != "industry_scope_pack_v2":
        errors.append("industry_scope_pack must use schema_version industry_scope_pack_v2")
    if payload.get("do_not_use_as_claims") is not True:
        errors.append("industry_scope_pack.do_not_use_as_claims must be true")
    summary = payload.get("scope_summary") if isinstance(payload.get("scope_summary"), dict) else {}
    for field in ("working_market", "parent_market", "broader_market"):
        if not text(summary.get(field)):
            errors.append(f"scope_summary.{field} is required")


def _contains_key(value: Any, keys: set[str]) -> bool:
    if isinstance(value, dict):
        return any(key in keys or _contains_key(item, keys) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_key(item, keys) for item in value)
    return False


def validate_formal_plan(path: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    if _contains_key(payload, {"query", "query_variants", "english_query", "chinese_query"}):
        errors.append("formal_search_plan must not contain executable query fields")
    rows = payload.get("issue_search_plan")
    if not isinstance(rows, list) or not rows:
        errors.append("formal_search_plan.issue_search_plan must be a non-empty list")


def validate_search_batch(path: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    raw = json.dumps(payload, ensure_ascii=False)
    if "LLM_REWRITE_REQUIRED" in raw:
        errors.append("executable_search_batch still contains LLM_REWRITE_REQUIRED")
    if "needs_authoring" in raw:
        errors.append("executable_search_batch still contains needs_authoring rows")
    rows = payload.get("batches")
    if isinstance(rows, list):
        for idx, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                continue
            status = text(row.get("query_status"))
            if status != "authored":
                fs_id = text(row.get("search_instruction_id")) or f"row {idx}"
                errors.append(f"executable_search_batch {fs_id}: query_status must be authored before execution")
            for field in ("english_query", "chinese_query", "source_specific_query"):
                if not text(row.get(field)):
                    fs_id = text(row.get("search_instruction_id")) or f"row {idx}"
                    errors.append(f"executable_search_batch {fs_id}: {field} is required")


def validate_execution(path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    search_log = run_dir / "artifacts/search_log.md"
    if not search_log.exists():
        errors.append("formal research execution requires artifacts/search_log.md")
    coverage = payload.get("coverage_summary") if isinstance(payload.get("coverage_summary"), dict) else {}
    status_rows = as_list(payload.get("fs_row_execution_status"))
    below_minimum = [
        text(row.get("fs_id"))
        for row in status_rows
        if isinstance(row, dict)
        and text(row.get("execution_expectation")) == "deep_search"
        and int(row.get("actual_search_attempt_count") or 0) < int(row.get("minimum_actual_searches") or 0)
        and text(row.get("fs_id"))
    ]
    if below_minimum:
        warnings.append(
            "formal research execution is below minimum search coverage for planned rows: "
            + ", ".join(below_minimum[:12])
            + (f"; plus {len(below_minimum) - 12} more" if len(below_minimum) > 12 else "")
        )
    executed_with_evidence = int(coverage.get("fs_rows_executed_with_evidence") or 0)
    minimum_evidence_rows = _advisory_target("formal_execution_evidence_rows")
    if minimum_evidence_rows and executed_with_evidence < minimum_evidence_rows:
        warnings.append(
            f"formal research execution has only {executed_with_evidence} evidence-bearing FS rows; "
            f"advisory target is {minimum_evidence_rows}. QC should decide whether to continue, repair research, "
            "or mark the output evidence-limited."
        )


def validate_source_archive(path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    rows = payload.get("sources") or payload.get("source_archive") or payload.get("archives") or []
    if not isinstance(rows, list):
        errors.append("source archive index must contain a source list")
        return
    for idx, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        source_id = text(row.get("source_id") or row.get("id"))
        if source_id and not SRC_RE.fullmatch(source_id):
            errors.append(f"source archive row {idx}: invalid source_id {source_id}")
        status = text(row.get("research_archive_status") or row.get("archive_status"))
        archive_path = text(row.get("archive_path") or row.get("saved_path") or row.get("local_path"))
        if status in {"saved_html", "saved_text", "saved_pdf", "downloaded_pdf"} and archive_path:
            candidate = run_dir / archive_path if not Path(archive_path).is_absolute() else Path(archive_path)
            if not candidate.exists():
                errors.append(f"source archive row {idx}: archive file not found: {archive_path}")


def validate_research_evidence_db(path: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    db_result = validate_research_db(payload)
    db_errors = db_result[0] if len(db_result) > 0 else []
    db_warnings = db_result[1] if len(db_result) > 1 else []
    errors.extend(str(item) for item in db_errors)
    warnings.extend(str(item) for item in db_warnings)


def validate_research_pack(path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    if not path.exists():
        errors.append(f"missing required file: {path}")
        return
    text_body = path.read_text(encoding="utf-8", errors="replace")
    if "EV-" not in text_body and "MET-" not in text_body:
        warnings.append("research pack contains no visible EV/MET IDs")
    db_path = run_dir / "artifacts/research_evidence_db.json"
    if not db_path.exists():
        errors.append("research pack requires artifacts/research_evidence_db.json as source of truth")


def validate_banker_page_pack(path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    if payload.get("schema_version") != "banker_page_pack":
        errors.append("banker_page_pack.schema_version must be banker_page_pack")
    slides = payload.get("slides")
    expected_slide_count = len(FIXED_PAGE_ROLES)
    if not isinstance(slides, list) or len(slides) != expected_slide_count:
        errors.append(f"banker_page_pack must contain exactly {expected_slide_count} slides from slide_registry.json")
        return
    db_path = run_dir / "artifacts/research_evidence_db.json"
    db = _json(db_path, []) if db_path.exists() else {}
    ev_ids = _ids(db, "evidence_ledger", ("evidence_id", "id"))
    met_ids = _ids(db, "metric_reconciliation", ("metric_id", "id"))
    metric_sources = _metric_source_index(db)
    readiness = payload.get("deliverable_readiness") if isinstance(payload.get("deliverable_readiness"), dict) else {}
    client_ready_intended = readiness.get("enough_for_client_pitch") is not False
    industry_subject_slides = 0
    target_context_slides = 0
    project_relevance_slides = 0
    unique_ev_refs: set[str] = set()
    unique_met_refs: set[str] = set()
    metric_slide_count = 0
    structured_exhibit_count = 0
    for idx, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            errors.append(f"slide {idx}: must be an object")
            continue
        slide_no = int(slide.get("slide_no") or 0)
        expected_id = f"BP-{slide_no:03d}" if slide_no else ""
        if text(slide.get("banker_page_id") or expected_id) != expected_id:
            errors.append(f"slide {slide_no}: banker_page_id must be {expected_id}")
        if text(slide.get("claim_strength")) not in VALID_CLAIM_STRENGTHS:
            errors.append(f"slide {slide_no}: invalid claim_strength")
        subject = text(slide.get("page_primary_subject"))
        if subject not in PAGE_PRIMARY_SUBJECTS:
            errors.append(f"slide {slide_no}: page_primary_subject must be one of {sorted(PAGE_PRIMARY_SUBJECTS)}")
        if subject == "industry":
            industry_subject_slides += 1
        if subject == "target_context":
            target_context_slides += 1
        if text(slide.get("project_relevance_note")):
            project_relevance_slides += 1
        if text(slide.get("transaction_readthrough")):
            errors.append(f"slide {slide_no}: transaction_readthrough is deprecated; use project_relevance_note")
        for field in ("fixed_page_role", "client_question", "banker_judgment", "page_argument", "headline", "main_message", "selected_page_type", "source_note"):
            if not text(slide.get(field)):
                errors.append(f"slide {slide_no}: {field} is required")
        if client_ready_intended:
            min_headline_chars = _min_chars("title")
            min_message_chars = _min_chars("main_takeaway")
            if min_headline_chars and len(text(slide.get("headline"))) < min_headline_chars:
                warnings.append(f"slide {slide_no}: headline is shorter than advisory banker-page target")
            if min_message_chars and len(text(slide.get("main_message"))) < min_message_chars:
                warnings.append(f"slide {slide_no}: main_message is shorter than advisory banker-page target")
        note = text(slide.get("project_relevance_note"))
        max_project_note_chars = _advisory_target("project_relevance_note_chars")
        if max_project_note_chars and len(note) > max_project_note_chars:
            warnings.append(f"slide {slide_no}: project_relevance_note is longer than advisory target")
        if note and subject == "industry":
            warnings.append(f"slide {slide_no}: project_relevance_note appears on an industry-primary page; QC should verify this is intentional")
        if subject != "target_context":
            for field in ("headline", "main_message"):
                if _contains_target_context_terms(slide.get(field)):
                    warnings.append(f"slide {slide_no}: {field} contains target/project terms while page_primary_subject is {subject}")
            for block_idx, block in enumerate(as_list(slide.get("body_blocks")), start=1):
                if isinstance(block, dict) and _contains_target_context_terms(block.get("copy")):
                    warnings.append(f"slide {slide_no} body block {block_idx}: target/project terms appear outside a target_context page")
        body_blocks = as_list(slide.get("body_blocks"))
        if not body_blocks:
            errors.append(f"slide {slide_no}: body_blocks is required")
        elif client_ready_intended:
            min_blocks = _advisory_target("body_blocks_per_slide")
            if min_blocks and len(body_blocks) < min_blocks:
                warnings.append(f"slide {slide_no}: fewer body_blocks than advisory target")
        if client_ready_intended:
            min_body_chars = _min_chars("bullet")
            for block_idx, block in enumerate(body_blocks, start=1):
                if min_body_chars and isinstance(block, dict) and len(text(block.get("copy"))) < min_body_chars:
                    warnings.append(f"slide {slide_no} body block {block_idx}: copy is shorter than advisory density target")
            min_slide_chars = _advisory_target("slide_text_chars")
            if min_slide_chars and _slide_text_chars(slide) < min_slide_chars:
                warnings.append(f"slide {slide_no}: total page text is below advisory density target")
        slide_ev_ids = _scan_ids(slide, {"evidence_id", "evidence_ids"})
        slide_met_ids = _scan_ids(slide, {"metric_id", "metric_ids"})
        unique_ev_refs.update(ev_id for ev_id in slide_ev_ids if EV_RE.fullmatch(ev_id))
        unique_met_refs.update(metric_id for metric_id in slide_met_ids if MET_RE.fullmatch(metric_id))
        if slide_met_ids:
            metric_slide_count += 1
        if _structured_exhibit(slide):
            structured_exhibit_count += 1
        chart_type = _chart_type(slide)
        chart_units = _chart_units(slide)
        if chart_type in _axis_chart_types() and len(chart_units) > 1:
            warnings.append(
                f"slide {slide_no}: chart_data mixes units on one chart axis ({', '.join(sorted(chart_units))}); "
                "QC should decide whether to use metric cards, a table, or separate charts"
            )
        chart_data = slide.get("chart_data") if isinstance(slide.get("chart_data"), dict) else {}
        chart_metric_ids = _scan_ids(chart_data, {"metric_id", "metric_ids"})
        if chart_type in _axis_chart_types() and len(chart_metric_ids) < 2:
            warnings.append(f"slide {slide_no}: axis chart has fewer than two linked MET IDs; verify chart is not a weak single-point visual")
        for metric_id in slide_met_ids:
            metric_info = metric_sources.get(metric_id, {})
            metric = metric_info.get("metric") if isinstance(metric_info.get("metric"), dict) else {}
            source = metric_info.get("source") if isinstance(metric_info.get("source"), dict) else {}
            if _project_specific_source(source) or normalize_source_type(metric.get("source_type")) in _project_specific_source_types():
                warnings.append(
                    f"slide {slide_no}: metric {metric_id} comes from project-specific / management-provided material; "
                    "QC should verify it is labeled as unaudited project context before client use"
                )
        for ev_id in slide_ev_ids:
            if not EV_RE.fullmatch(ev_id):
                errors.append(f"slide {slide_no}: invalid evidence id {ev_id}")
            elif ev_ids and ev_id not in ev_ids:
                errors.append(f"slide {slide_no}: evidence id {ev_id} not found in research_evidence_db")
        for metric_id in slide_met_ids:
            if not MET_RE.fullmatch(metric_id):
                errors.append(f"slide {slide_no}: invalid metric id {metric_id}")
            elif met_ids and metric_id not in met_ids:
                errors.append(f"slide {slide_no}: metric id {metric_id} not found in research_evidence_db")
    max_target_pages = _advisory_target("target_context_slides")
    min_industry_pages = _advisory_target("industry_subject_slides")
    max_project_notes = _advisory_target("project_relevance_note_slides")
    if max_target_pages and target_context_slides > max_target_pages:
        warnings.append("banker_page_pack has more target_context pages than the advisory target")
    if min_industry_pages and industry_subject_slides < min_industry_pages:
        warnings.append("banker_page_pack has fewer industry-primary pages than the advisory target")
    if max_project_notes and project_relevance_slides > max_project_notes:
        warnings.append("banker_page_pack has more project_relevance_note pages than the advisory target")
    if client_ready_intended:
        min_ev_refs = _advisory_target("unique_ev_refs")
        min_met_refs = _advisory_target("unique_met_refs")
        min_metric_slides = _advisory_target("metric_supported_slides")
        min_structured_exhibits = _advisory_target("structured_exhibit_slides")
        if min_ev_refs and len(unique_ev_refs) < min_ev_refs:
            warnings.append(
                f"client-ready banker_page_pack uses only {len(unique_ev_refs)} unique EV IDs; "
                f"advisory target is {min_ev_refs}. QC should decide whether to continue or mark evidence-limited."
            )
        if min_met_refs and len(unique_met_refs) < min_met_refs:
            warnings.append(
                f"client-ready banker_page_pack uses only {len(unique_met_refs)} unique MET IDs; "
                f"advisory target is {min_met_refs}. QC should decide whether to continue or mark evidence-limited."
            )
        if min_metric_slides and metric_slide_count < min_metric_slides:
            warnings.append(
                f"client-ready banker_page_pack has metrics on only {metric_slide_count} slides; "
                f"advisory target is {min_metric_slides} metric-supported slides."
            )
        if min_structured_exhibits and structured_exhibit_count < min_structured_exhibits:
            warnings.append(
                f"client-ready banker_page_pack has only {structured_exhibit_count} structured exhibit slides; "
                f"advisory target is {min_structured_exhibits}."
            )


def validate_template_registry(path: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    slides = payload.get("slides")
    if not isinstance(slides, list) or not slides:
        errors.append("template_registry.slides must be a non-empty list")
        return
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        if not isinstance(slide.get("slide_no"), int):
            errors.append("template_registry slide missing integer slide_no")
        if not as_list(slide.get("variants")):
            warnings.append(f"template_registry slide {slide.get('slide_no')}: no variants")


def validate_deck_blueprint(path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    slides = payload.get("slides")
    expected_slide_count = len(FIXED_PAGE_ROLES)
    if not isinstance(slides, list) or len(slides) != expected_slide_count:
        errors.append(f"deck_blueprint must contain exactly {expected_slide_count} slides from slide_registry.json")
        return
    template = _json(run_dir / "template_registry.json", []) if (run_dir / "template_registry.json").exists() else {}
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        slide_no = int(slide.get("slide_no") or 0)
        expected = FIXED_PAGE_ROLES.get(slide_no)
        if expected and text(slide.get("fixed_page_role")) != expected:
            errors.append(f"slide {slide_no}: fixed_page_role must be {expected}")
        banker_page_id = banker_page_id_for_slide(slide)
        if not BP_RE.fullmatch(banker_page_id):
            errors.append(f"slide {slide_no}: invalid banker_page_id")
        for field in ("headline", "main_message", "body_blocks", "selected_page_type"):
            if field == "body_blocks":
                if not as_list(slide.get(field)):
                    errors.append(f"slide {slide_no}: body_blocks is required")
            elif not text(slide.get(field)):
                errors.append(f"slide {slide_no}: {field} is required")
        if template:
            try:
                required_body_fields(template, slide_no, text(slide.get("selected_page_type")))
            except Exception as exc:
                errors.append(f"slide {slide_no}: template field mapping failed: {exc}")


def validate_page_contract(path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    slides = payload.get("slides")
    expected_slide_count = len(FIXED_PAGE_ROLES)
    if not isinstance(slides, list) or len(slides) != expected_slide_count:
        errors.append(f"page_evidence_contract must contain exactly {expected_slide_count} slides from slide_registry.json")
        return
    deck = _json(run_dir / "deck_blueprint.json", []) if (run_dir / "deck_blueprint.json").exists() else {}
    deck_by_no = _slide_index(deck)
    for entry in slides:
        if not isinstance(entry, dict):
            continue
        slide_no = int(entry.get("slide_no") or 0)
        expected_id = f"BP-{slide_no:03d}"
        if text(entry.get("banker_page_id")) != expected_id:
            errors.append(f"slide {slide_no}: banker_page_id must be {expected_id}")
        permission = entry.get("downstream_permission")
        if not isinstance(permission, dict):
            errors.append(f"slide {slide_no}: downstream_permission object is required")
        deck_slide = deck_by_no.get(slide_no)
        if deck_slide and text(entry.get("banker_page_id")) != banker_page_id_for_slide(deck_slide):
            errors.append(f"slide {slide_no}: banker_page_id mismatch with deck_blueprint")


def validate_renderer_spec(path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    if payload.get("schema_version") != "renderer_spec_v1":
        errors.append("renderer_spec.schema_version must be renderer_spec_v1")
    slides = payload.get("slides")
    expected_slide_count = len(FIXED_PAGE_ROLES)
    if not isinstance(slides, list) or len(slides) != expected_slide_count:
        errors.append(f"renderer_spec must contain exactly {expected_slide_count} slides from slide_registry.json")
        return
    try:
        build_token_source(payload)
    except Exception as exc:
        errors.append(f"renderer_spec cannot be converted into token source: {exc}")


def validate_replacement_dict(path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    def scan_values(value: Any) -> bool:
        if isinstance(value, dict):
            return any(scan_values(item) for item in value.values())
        if isinstance(value, list):
            return any(scan_values(item) for item in value)
        return isinstance(value, str) and ("{{" in value or "}}" in value)

    if scan_values(payload):
        errors.append("replacement_dict contains unresolved placeholder braces in replacement values")
    if not (run_dir / "renderer_spec.json").exists():
        errors.append("replacement_dict requires renderer_spec.json")


def validate_filled_ppt(path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    candidates = [
        run_dir / "industry_section_filled_clean.pptx",
        run_dir / "industry_section_filled.pptx",
        run_dir / "filled_output_clean.pptx",
        run_dir / "filled_output.pptx",
        run_dir / "NOT_CLIENT_READY_industry_section_filled_clean.pptx",
        run_dir / "NOT_CLIENT_READY_industry_section_filled.pptx",
    ]
    existing = [candidate for candidate in candidates if candidate.exists()]
    if not existing:
        errors.append("missing filled PPT output")
        return
    target = existing[0]
    if target.name.startswith("NOT_CLIENT_READY_"):
        warnings.append(f"{target.name} exists but final delivery is not client-ready")
    try:
        with zipfile.ZipFile(target) as archive:
            names = set(archive.namelist())
            if "[Content_Types].xml" not in names:
                errors.append(f"{target.name} is not a valid pptx package")
    except Exception as exc:
        errors.append(f"cannot inspect PPT package {target}: {exc}")
        return
    try:
        slide_texts = _ppt_slide_texts(target)
    except Exception as exc:
        warnings.append(f"could not extract PPT slide text for visual QC: {exc}")
        slide_texts = []
    for idx, slide_text in enumerate(slide_texts, start=1):
        bad = sorted(char for char in BAD_PPT_GLYPHS if char in slide_text)
        if bad:
            errors.append(f"slide {idx}: PPT text contains missing-glyph/tofu characters: {' '.join(bad)}")
        if idx <= 8 and len(slide_text.strip()) < 260:
            warnings.append(f"slide {idx}: rendered PPT text appears sparse; inspect page density visually")
    postprocess_log = run_dir / "artifacts/postprocess_ppt_visuals.log.json"
    if postprocess_log.exists():
        log = _json(postprocess_log, [])
        for item in as_list(log.get("chart_rendering")):
            if not isinstance(item, dict):
                continue
            if item.get("required_render", True) is not False and item.get("rendered") is not True:
                chart = item.get("chart") if isinstance(item.get("chart"), dict) else {}
                errors.append(
                    f"slide {item.get('slide_no', '?')}: required visual renderer failed: "
                    f"{text(item.get('reason')) or text(chart.get('reason'))}"
                )


def validate_stage(artifact: str, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    if artifact == "pre_research_pack":
        required = [
            "artifacts/industry_scope_pack.json",
            "artifacts/formal_search_plan.json",
            "artifacts/formal_research_execution_report.json",
            "artifacts/source_archive/source_archive_index.json",
        ]
    elif artifact == "pre_ppt":
        required = [
            "banker_page_pack.json",
            "template_registry.json",
            "deck_blueprint.json",
            "page_evidence_contract.json",
            "renderer_spec.json",
        ]
    else:
        required = [
            "banker_page_pack.json",
            "renderer_spec.json",
            "replacement_dict.json",
        ]
    for rel in required:
        if not (run_dir / rel).exists():
            errors.append(f"missing required upstream artifact: {rel}")
    if errors:
        return

    if artifact == "pre_research_pack":
        validate_scope(run_dir / "artifacts/industry_scope_pack.json", errors, warnings)
        validate_formal_plan(run_dir / "artifacts/formal_search_plan.json", errors, warnings)
        validate_execution(run_dir / "artifacts/formal_research_execution_report.json", run_dir, errors, warnings)
        validate_source_archive(run_dir / "artifacts/source_archive/source_archive_index.json", run_dir, errors, warnings)
    elif artifact == "pre_ppt":
        validate_banker_page_pack(run_dir / "banker_page_pack.json", run_dir, errors, warnings)
        validate_template_registry(run_dir / "template_registry.json", errors, warnings)
        validate_deck_blueprint(run_dir / "deck_blueprint.json", run_dir, errors, warnings)
        validate_page_contract(run_dir / "page_evidence_contract.json", run_dir, errors, warnings)
        validate_renderer_spec(run_dir / "renderer_spec.json", run_dir, errors, warnings)
    elif artifact == "final_delivery":
        validate_stage("pre_ppt", run_dir, errors, warnings)
        validate_replacement_dict(run_dir / "replacement_dict.json", run_dir, errors, warnings)
        validate_filled_ppt(run_dir / "filled_ppt_validation.json", run_dir, errors, warnings)


def validate_artifact(artifact: str, run_dir: Path, path: Path | None = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    target = path or run_dir / ARTIFACT_PATHS.get(artifact, "")
    if artifact in {"material_manifest", "material_extracts", "input_card"}:
        validate_material_like(artifact, target, run_dir, errors, warnings)
    elif artifact == "research_request_queue":
        validate_research_request_queue(target, errors, warnings)
    elif artifact == "industry_scope_pack":
        validate_scope(target, errors, warnings)
    elif artifact == "formal_search_plan":
        validate_formal_plan(target, errors, warnings)
    elif artifact == "executable_search_batch":
        validate_search_batch(target, errors, warnings)
    elif artifact == "formal_research_execution":
        validate_execution(target, run_dir, errors, warnings)
    elif artifact == "source_archive":
        validate_source_archive(target, run_dir, errors, warnings)
    elif artifact == "research_evidence_db":
        validate_research_evidence_db(target, errors, warnings)
    elif artifact == "research_pack":
        validate_research_pack(target, run_dir, errors, warnings)
    elif artifact == "banker_page_pack":
        validate_banker_page_pack(target, run_dir, errors, warnings)
    elif artifact == "template_registry":
        validate_template_registry(target, errors, warnings)
    elif artifact == "deck_blueprint":
        validate_deck_blueprint(target, run_dir, errors, warnings)
    elif artifact == "page_evidence_contract":
        validate_page_contract(target, run_dir, errors, warnings)
    elif artifact == "renderer_spec":
        validate_renderer_spec(target, run_dir, errors, warnings)
    elif artifact == "replacement_dict":
        validate_replacement_dict(target, run_dir, errors, warnings)
    elif artifact == "filled_ppt":
        validate_filled_ppt(target, run_dir, errors, warnings)
    elif artifact in {"pre_research_pack", "pre_ppt", "final_delivery"}:
        validate_stage(artifact, run_dir, errors, warnings)
    else:
        errors.append(f"unknown artifact: {artifact}")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True, choices=sorted(ARTIFACT_PATHS))
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--path", help="Optional explicit artifact path.")
    parser.add_argument("--output")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    path = Path(args.path) if args.path else None
    errors, warnings = validate_artifact(args.artifact, run_dir, path)
    result = {
        "is_valid": not errors,
        "artifact": args.artifact,
        "run_dir": str(run_dir),
        "path": str(path or run_dir / ARTIFACT_PATHS[args.artifact]),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "validation_policy": "mechanical_only",
    }
    output = json.dumps(result, ensure_ascii=False, indent=2)
    output_path = Path(args.output) if args.output else run_dir / VALIDATION_OUTPUTS.get(args.artifact, f"artifacts/{args.artifact}_validation.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
