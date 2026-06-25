#!/usr/bin/env python3
"""Unified deterministic validator for the industry-section workflow.

This script deliberately checks only mechanical conditions: files exist, JSON is
parseable, IDs and cross-references are coherent, and renderer/PPT inputs can be
used by deterministic tooling. Content quality, page density, source judgment,
and transaction relevance are LLM responsibilities.
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
    RUNTIME_ROOT / "scripts" / "template",
    RUNTIME_ROOT / "scripts" / "knowledge-repository",
]:
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from deck_blueprint_utils import (
    FIXED_PAGE_ROLES,
    PAGE_PRIMARY_SUBJECTS,
    VALID_ALLOWED_DECK_USAGES,
    VALID_CLAIM_STRENGTHS,
    active_body_fields,
    as_list,
    banker_page_id_for_slide,
    required_body_fields,
    template_variants_by_slide,
    unique,
)
from runtime_utils import load_json_file
from renderer_compile_utils import _body_copy_from_blocks, build_token_source
from research_evidence_db import validate_db as validate_research_db
from template_analyzer import display_units, estimate_lines, layout_rules_for


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


def _load_config_json(relative_path: str) -> dict[str, Any]:
    try:
        payload = load_json_file(RUNTIME_ROOT / relative_path)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _int_value(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return 0


def _visual_payload(slide: dict[str, Any], key: str) -> dict[str, Any]:
    if isinstance(slide.get(key), dict):
        return slide[key]
    visual_design = slide.get("visual_design") if isinstance(slide.get("visual_design"), dict) else {}
    if isinstance(visual_design.get(key), dict):
        return visual_design[key]
    visual_plan = slide.get("visual_plan") if isinstance(slide.get("visual_plan"), dict) else {}
    if isinstance(visual_plan.get(key), dict):
        return visual_plan[key]
    return {}


def _body_field_limits(layout_budget: dict[str, Any], slide_no: int, page_type: str) -> dict[str, float]:
    rules = layout_rules_for(slide_no, page_type, layout_budget)
    limits = rules.get("body_fields_max_units") if isinstance(rules.get("body_fields_max_units"), dict) else {}
    result: dict[str, float] = {}
    for key, value in limits.items():
        try:
            result[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return result


def _default_body_limit(layout_budget: dict[str, Any]) -> float:
    global_body = layout_budget.get("global", {}).get("body_copy", {})
    try:
        return float(global_body.get("max_bullet_units_default", 88))
    except (TypeError, ValueError):
        return 88.0


def _text_fit_rule(text_fit_rules: dict[str, Any], slide_no: int, page_type: str, field: str) -> dict[str, Any]:
    aliases = text_fit_rules.get("renderer_field_aliases") if isinstance(text_fit_rules.get("renderer_field_aliases"), dict) else {}
    fields = text_fit_rules.get("fields") if isinstance(text_fit_rules.get("fields"), dict) else {}
    alias = str(aliases.get(field, field))
    rule = fields.get(f"{slide_no}:{page_type}:{alias}")
    return rule if isinstance(rule, dict) else {}


def _compare_table_data_from_slide(slide: dict[str, Any]) -> dict[str, Any]:
    return _visual_payload(slide, "compare_table_data")


def _validate_compare_table_shape(slide_no: int, data: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    headers = data.get("headers")
    columns = data.get("columns")
    header_values: list[str] = []
    if not isinstance(headers, list) or not [text(item) for item in headers if text(item)]:
        if isinstance(columns, list) and [text(item) for item in columns if text(item)]:
            header_values = [text(item) for item in columns if text(item)]
            warnings.append(
                f"slide {slide_no}: compare_table_data uses columns; compiler accepts it, but canonical key is headers"
            )
        else:
            errors.append("slide {slide_no}: compare_table_data requires non-empty headers list".format(slide_no=slide_no))
    else:
        header_values = [text(item) for item in headers if text(item)]
    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        errors.append(f"slide {slide_no}: compare_table_data requires non-empty rows list")
        return
    valid_rows = 0
    header_count = len(header_values)
    for idx, row in enumerate(rows, start=1):
        if isinstance(row, dict):
            cells = row.get("cells")
            has_label = bool(text(row.get("label") or row.get("name")))
            scalar_cells = [
                value
                for key, value in row.items()
                if key not in {"label", "name", "metric_ids", "evidence_ids", "source_banker_page_ids"}
                and not isinstance(value, (dict, list))
                and text(value)
            ]
            if not has_label and not cells and not scalar_cells:
                errors.append(f"slide {slide_no}: compare_table_data row {idx} needs label plus cells")
                continue
            if cells is not None and not isinstance(cells, list):
                errors.append(f"slide {slide_no}: compare_table_data row {idx}.cells must be a list")
                continue
            if isinstance(cells, list) and header_count:
                expected_cells = max(header_count - 1, 0) if has_label else header_count
                if len(cells) != expected_cells:
                    errors.append(
                        f"slide {slide_no}: compare_table_data row {idx} has label plus {len(cells)} cells, "
                        f"but {header_count} headers require {expected_cells} cells after label"
                    )
                    continue
            if cells is None and scalar_cells:
                expected_cells = max(header_count - 1, 0) if has_label else header_count
                if header_count and len(scalar_cells) != expected_cells:
                    errors.append(
                        f"slide {slide_no}: compare_table_data row {idx} has {len(scalar_cells)} scalar columns, "
                        f"but {header_count} headers require {expected_cells} columns after label"
                    )
                    continue
                warnings.append(
                    f"slide {slide_no}: compare_table_data row {idx} uses scalar columns; canonical row shape is {{label, cells}}"
                )
            valid_rows += 1
        elif isinstance(row, list) and row:
            if header_count and len(row) != header_count:
                errors.append(
                    f"slide {slide_no}: compare_table_data row {idx} has {len(row)} cells, "
                    f"but {header_count} headers require exactly {header_count} cells"
                )
                continue
            warnings.append(
                f"slide {slide_no}: compare_table_data row {idx} is a list; compiler accepts it, but canonical row shape is {{label, cells}}"
            )
            valid_rows += 1
        elif isinstance(row, str) and row.strip():
            warnings.append(
                f"slide {slide_no}: compare_table_data row {idx} is a string; compiler accepts it, but canonical row shape is {{label, cells}}"
            )
            valid_rows += 1
        else:
            errors.append(f"slide {slide_no}: compare_table_data row {idx} must be an object with label/cells")
    if not valid_rows:
        errors.append(f"slide {slide_no}: compare_table_data has no usable rows")


def banker_page_pack_template_diagnostics(run_dir: Path, path: Path | None = None) -> dict[str, Any]:
    target = path or run_dir / ARTIFACT_PATHS["banker_page_pack"]
    pack: dict[str, Any] = {}
    try:
        pack = load_json_file(target)
    except Exception:
        pack = {}
    if not isinstance(pack, dict):
        pack = {}
    template = {}
    template_path = run_dir / "template_registry.json"
    if template_path.exists():
        try:
            template = load_json_file(template_path)
        except Exception:
            template = {}
    template = template if isinstance(template, dict) else {}
    variants = template_variants_by_slide(template) if template else {}
    layout_budget = _load_config_json("configs/layout_budget.json")
    text_fit_rules = _load_config_json("configs/text_fit_rules.json")
    slides = pack.get("slides") if isinstance(pack.get("slides"), list) else []
    diagnostics: list[dict[str, Any]] = []
    for raw_slide in slides:
        if not isinstance(raw_slide, dict):
            continue
        slide_no = _int_value(raw_slide.get("slide_no"))
        page_type = text(raw_slide.get("selected_page_type"))
        allowed_page_types = sorted(variants.get(slide_no, {}).keys())
        required_fields = required_body_fields(template, slide_no, page_type) if template and page_type else []
        active_fields = active_body_fields(required_fields, page_type, raw_slide) if required_fields else []
        field_limits = _body_field_limits(layout_budget, slide_no, page_type)
        text_rules: dict[str, Any] = {}
        for field in ("headline", "main_message"):
            rule = _text_fit_rule(text_fit_rules, slide_no, page_type, field)
            if rule:
                text_rules[field] = {
                    "max_line_units": rule.get("max_line_units"),
                    "target_lines": rule.get("target_lines"),
                    "max_lines": rule.get("max_lines"),
                    "placeholder": rule.get("placeholder"),
                }
        diagnostics.append(
            {
                "slide_no": slide_no,
                "expected_fixed_page_role": FIXED_PAGE_ROLES.get(slide_no, ""),
                "selected_page_type": page_type,
                "allowed_page_types": allowed_page_types,
                "required_body_fields_from_template": required_fields,
                "active_body_fields": active_fields,
                "inactive_when_compare_table_data_present": (
                    [field for field in required_fields if field not in active_fields]
                    if page_type == "compare_table_page" and _compare_table_data_from_slide(raw_slide)
                    else []
                ),
                "body_field_unit_limits": field_limits,
                "default_body_field_unit_limit": _default_body_limit(layout_budget),
                "headline_main_message_line_rules": text_rules,
                "compare_table_data_contract": (
                    "Use compare_table_data.headers and rows=[{label, cells}]. Table header/row content does not belong in body_copy when compare_table_data is present."
                    if page_type == "compare_table_page"
                    else ""
                ),
            }
        )
    return {
        "schema_version": "banker_page_pack_template_diagnostics_v1",
        "banker_page_pack": str(target),
        "template_registry": str(template_path) if template_path.exists() else "",
        "has_template_registry": bool(template),
        "slides": diagnostics,
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
    if payload.get("schema_version") != "industry_scope_pack_boundary_card":
        errors.append("industry_scope_pack must use schema_version industry_scope_pack_boundary_card")
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
    slide_numbers = [_int_value(slide.get("slide_no")) for slide in slides if isinstance(slide, dict)]
    expected_numbers = sorted(FIXED_PAGE_ROLES)
    missing_numbers = [number for number in expected_numbers if number not in slide_numbers]
    duplicate_numbers = sorted({number for number in slide_numbers if number and slide_numbers.count(number) > 1})
    invalid_numbers = [number for number in slide_numbers if number not in FIXED_PAGE_ROLES]
    if missing_numbers:
        errors.append(f"banker_page_pack missing slide_no values required by template: {missing_numbers}")
    if duplicate_numbers:
        errors.append(f"banker_page_pack contains duplicate slide_no values: {duplicate_numbers}")
    if invalid_numbers:
        errors.append(f"banker_page_pack contains slide_no values not in slide_registry.json: {invalid_numbers}")
    db_path = run_dir / "artifacts/research_evidence_db.json"
    db = _json(db_path, []) if db_path.exists() else {}
    ev_ids = _ids(db, "evidence_ledger", ("evidence_id", "id"))
    met_ids = _ids(db, "metric_reconciliation", ("metric_id", "id"))
    template_path = run_dir / "template_registry.json"
    template = _json(template_path, []) if template_path.exists() else {}
    template_variants = template_variants_by_slide(template) if template else {}
    if not template:
        warnings.append(
            "banker_page_pack template-specific checks were limited because template_registry.json is missing; "
            "run scripts/pipeline.py template-registry or scripts/pipeline.py render to generate it"
        )
    layout_budget = _load_config_json("configs/layout_budget.json")
    text_fit_rules = _load_config_json("configs/text_fit_rules.json")
    for idx, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            errors.append(f"slide {idx}: must be an object")
            continue
        slide_no = _int_value(slide.get("slide_no"))
        expected_id = f"BP-{slide_no:03d}" if slide_no else ""
        if text(slide.get("banker_page_id") or expected_id) != expected_id:
            errors.append(f"slide {slide_no}: banker_page_id must be {expected_id}")
        expected_role = FIXED_PAGE_ROLES.get(slide_no)
        if expected_role and text(slide.get("fixed_page_role")) != expected_role:
            errors.append(
                f"slide {slide_no}: fixed_page_role must be '{expected_role}' for this template position; "
                f"do not move page roles by changing slide_no"
            )
        if text(slide.get("claim_strength")) not in VALID_CLAIM_STRENGTHS:
            errors.append(f"slide {slide_no}: invalid claim_strength")
        if text(slide.get("allowed_deck_usage")) not in VALID_ALLOWED_DECK_USAGES:
            errors.append(f"slide {slide_no}: allowed_deck_usage must be one of {sorted(VALID_ALLOWED_DECK_USAGES)}")
        subject = text(slide.get("page_primary_subject"))
        if subject not in PAGE_PRIMARY_SUBJECTS:
            errors.append(f"slide {slide_no}: page_primary_subject must be one of {sorted(PAGE_PRIMARY_SUBJECTS)}")
        if text(slide.get("transaction_readthrough")):
            errors.append(f"slide {slide_no}: transaction_readthrough is deprecated; use project_relevance_note")
        for field in ("fixed_page_role", "page_question", "banker_judgment", "page_argument", "headline", "main_message", "selected_page_type", "source_note"):
            if not text(slide.get(field)):
                errors.append(f"slide {slide_no}: {field} is required")
        body_blocks = as_list(slide.get("body_blocks"))
        if not body_blocks:
            errors.append(f"slide {slide_no}: body_blocks is required")
        selected_page_type = text(slide.get("selected_page_type"))
        active_fields: list[str] = []
        body_copy_for_checks: dict[str, str] = {}
        if template and selected_page_type:
            allowed_page_types = sorted(template_variants.get(slide_no, {}).keys())
            if allowed_page_types and selected_page_type not in allowed_page_types:
                errors.append(
                    f"slide {slide_no}: selected_page_type '{selected_page_type}' is not available for "
                    f"fixed_page_role '{expected_role or '?'}'; allowed page types: {allowed_page_types}"
                )
            required_fields = required_body_fields(template, slide_no, selected_page_type)
            active_fields = active_body_fields(required_fields, selected_page_type, slide)
            if selected_page_type == "compare_table_page" and _compare_table_data_from_slide(slide):
                inactive = [field for field in required_fields if field not in active_fields]
                if inactive:
                    warnings.append(
                        f"slide {slide_no}: compare_table_page table fields are supplied through compare_table_data; "
                        f"inactive body fields when compare_table_data is present: {inactive}; active body fields: {active_fields}"
                    )
            explicit_body_copy = slide.get("body_copy") if isinstance(slide.get("body_copy"), dict) else {}
            if explicit_body_copy:
                body_copy_for_checks = {str(key): str(value or "").strip() for key, value in explicit_body_copy.items()}
                extra_fields = sorted(set(body_copy_for_checks) - set(active_fields))
                if extra_fields:
                    errors.append(
                        f"slide {slide_no}: body_copy contains fields not active for {selected_page_type}: {extra_fields}. "
                        f"Active body fields: {active_fields or ['(none)']}"
                    )
                missing_fields = [field for field in active_fields if not text(body_copy_for_checks.get(field))]
                if missing_fields:
                    errors.append(
                        f"slide {slide_no}: body_copy missing active fields for {selected_page_type}: {missing_fields}. "
                        f"Active body fields: {active_fields or ['(none)']}"
                    )
            elif body_blocks:
                try:
                    body_copy_for_checks = _body_copy_from_blocks(slide, required_fields, selected_page_type)
                except Exception as exc:
                    errors.append(f"slide {slide_no}: body_blocks cannot map to active template fields: {exc}")
            if selected_page_type == "compare_table_page" and _compare_table_data_from_slide(slide):
                for block_idx, block in enumerate(body_blocks, start=1):
                    if not isinstance(block, dict):
                        continue
                    target_or_role = text(
                        block.get("target_field")
                        or block.get("template_field")
                        or block.get("body_field")
                        or block.get("field")
                        or block.get("role")
                    )
                    if target_or_role == "table_header" or target_or_role.startswith("table_row_"):
                        errors.append(
                            f"slide {slide_no}: body block {block_idx} uses '{target_or_role}', but compare_table_page "
                            "takes table content from compare_table_data; use active body fields "
                            f"{active_fields or ['right_top', 'right_mid', 'right_bottom']}"
                        )
            field_limits = _body_field_limits(layout_budget, slide_no, selected_page_type)
            default_limit = _default_body_limit(layout_budget)
            for field_name, value in body_copy_for_checks.items():
                if field_name not in active_fields:
                    continue
                limit = field_limits.get(field_name, default_limit)
                actual = display_units(value)
                if actual > limit:
                    warnings.append(
                        f"slide {slide_no}: body_copy.{field_name} is {actual:.1f} layout units vs template guidance {limit:.1f}; "
                        "compress if the rendered page looks crowded, but this body budget is advisory"
                    )
            for text_field in ("headline", "main_message"):
                value = text(slide.get(text_field))
                rule = _text_fit_rule(text_fit_rules, slide_no, selected_page_type, text_field)
                if not value or not rule:
                    continue
                max_line_units = float(rule.get("max_line_units") or 0)
                target_lines = int(rule.get("target_lines") or 0)
                max_lines = int(rule.get("max_lines") or 0)
                estimated = estimate_lines(value, max_line_units)
                placeholder = text(rule.get("placeholder"))
                if target_lines and estimated > target_lines:
                    warnings.append(
                        f"slide {slide_no}: {text_field} estimates to {estimated} lines for {placeholder}; target is {target_lines}"
                    )
                if max_lines and estimated > max_lines and rule.get("block_if_exceeds_max_lines") is not False:
                    errors.append(
                        f"slide {slide_no}: {text_field} exceeds template max lines for {placeholder}: "
                        f"estimated {estimated}, max {max_lines}; shorten before render"
                    )
        if selected_page_type == "compare_table_page":
            compare_table_data = _compare_table_data_from_slide(slide)
            if not compare_table_data:
                errors.append(
                    f"slide {slide_no}: compare_table_page requires compare_table_data with headers and rows; "
                    "do not put peer-table content in body_blocks"
                )
            else:
                _validate_compare_table_shape(slide_no, compare_table_data, errors, warnings)
        slide_ev_ids = _scan_ids(slide, {"evidence_id", "evidence_ids"})
        slide_met_ids = _scan_ids(slide, {"metric_id", "metric_ids"})
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
    if args.artifact == "banker_page_pack":
        diagnostics = banker_page_pack_template_diagnostics(run_dir, path)
        result["template_diagnostics"] = diagnostics
        diagnostics_path = run_dir / "artifacts" / "banker_page_pack_template_diagnostics.json"
        diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
        diagnostics_path.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output = json.dumps(result, ensure_ascii=False, indent=2)
    output_path = Path(args.output) if args.output else run_dir / VALIDATION_OUTPUTS.get(args.artifact, f"artifacts/{args.artifact}_validation.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
