#!/usr/bin/env python3
"""Final deterministic gate for a generated industry-section run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from check_json_files import check_file
from json_utils import load_json_file
from validate_content_quality import validate as validate_content_quality
from deck_blueprint_utils import normalize_deck_blueprint_for_page_plan
from validate_industry_scope_pack import validate as validate_industry_scope_pack_data
from validate_issue_analysis import validate as validate_issue_analysis_data
from validate_input_card import validate as validate_input_card_data
from validate_research_pack import validate as validate_research_pack_data
from validate_page_evidence_contract import validate as validate_page_evidence_contract_data
from validate_deck_blueprint import validate as validate_deck_blueprint_data
from validate_formal_research_execution import validate as validate_formal_research_execution_data
from validate_renderer_spec import validate as validate_renderer_spec_data
from validate_replacement_dict import validate as validate_replacement_dict_data
from validate_run_artifacts import validate as validate_run_artifacts
from validate_stage_gate import validate_stage as validate_stage_gate_data
from validate_source_reviews import validate as validate_source_reviews_data
from validate_template_registry import validate as validate_template_registry_data
from validate_formal_search_plan import validate as validate_formal_search_plan_data


REPO_ROOT = Path(__file__).resolve().parents[1]
FINAL_BLOCKING_CONTENT_WARNING_KEYS = (
    "source_warnings",
    "generic_copy_warnings",
    "evidence_warnings",
    "claim_strength_warnings",
    "consistency_warnings",
)
BENIGN_FINAL_WARNING_FRAGMENTS = (
    "outside material claim",
)


def unique_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item)
        if text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def json_files_under(run_dir: Path) -> list[Path]:
    return sorted(path for path in run_dir.rglob("*.json") if "__pycache__" not in path.parts)


def validate_content_quality_artifact(path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not path.exists():
        errors.append("missing content quality validation artifact")
        return errors, warnings
    data = load_json_file(path)
    if data.get("is_valid") is False:
        errors.append("content_quality_validation.json is_valid=false")
    warning_count = int(data.get("warning_count") or 0)
    if warning_count:
        warnings.append(f"content_quality_validation.json has {warning_count} advisory warning(s)")
    blocking_items = data.get("blocking_issues") or []
    if blocking_items:
        errors.append(f"content_quality_validation.json contains {len(blocking_items)} blocking issue(s)")
    for key in FINAL_BLOCKING_CONTENT_WARNING_KEYS:
        values = data.get(key, [])
        if not isinstance(values, list):
            continue
        for item in values:
            text = str(item)
            lowered = text.lower()
            if any(fragment in lowered for fragment in BENIGN_FINAL_WARNING_FRAGMENTS):
                continue
            errors.append(f"content_quality_validation.json final-readiness issue in {key}: {text}")
    for key in (
        "warnings",
        "blocking_issues",
        "density_warnings",
        "source_warnings",
        "chart_data_warnings",
        "generic_copy_warnings",
        "evidence_warnings",
        "metric_id_warnings",
        "layout_warnings",
        "claim_strength_warnings",
        "consistency_warnings",
    ):
        values = data.get(key, [])
        if isinstance(values, list):
            warnings.extend(str(item) for item in values)
    return errors, warnings


def is_within_run(path_text: str, run_dir: Path) -> bool:
    if not path_text:
        return True
    try:
        candidate = Path(path_text).expanduser()
        if not candidate.is_absolute():
            return True
        candidate.resolve().relative_to(run_dir.resolve())
        return True
    except Exception:
        return False


def validate_artifact_provenance(run_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    checks = {
        "artifacts/input_card_validation.json": ["input_card"],
        "artifacts/industry_scope_pack_validation.json": ["scope_pack"],
        "artifacts/formal_search_plan_validation.json": ["formal_search_plan"],
        "artifacts/content_quality_validation.json": ["renderer_spec", "research_pack"],
        "artifacts/renderer_spec_validation.json": ["renderer_spec", "template_registry", "deck_blueprint", "page_contract"],
        "artifacts/research_pack_validation.json": ["research_pack", "run_dir"],
        "artifacts/source_reviews_validation.json": ["source_reviews"],
        "artifacts/source_archive_validation.json": ["source_archive_index"],
        "artifacts/formal_research_execution_validation.json": ["formal_research_execution_report", "formal_search_plan", "search_log"],
        "artifacts/stage_gate_pre_research_pack_validation.json": ["run_dir"],
        "artifacts/issue_analysis_validation.json": ["issue_analysis"],
        "artifacts/template_registry_validation.json": ["template_registry"],
        "artifacts/deck_blueprint_validation.json": ["issue_analysis", "template_registry", "deck_blueprint"],
        "artifacts/page_evidence_contract_validation.json": ["issue_analysis", "deck_blueprint", "page_contract"],
        "artifacts/replacement_dict_validation.json": ["replacement_dict", "renderer_spec"],
        "filled_ppt_validation.json": ["summary.filled_ppt", "summary.clean_ppt", "summary.control_file", "summary.replacement_dict"],
    }
    source_files_by_artifact = {
        "artifacts/input_card_validation.json": [
            run_dir / "input_card.json",
        ],
        "artifacts/industry_scope_pack_validation.json": [
            run_dir / "artifacts" / "industry_scope_pack.json",
        ],
        "artifacts/formal_search_plan_validation.json": [
            run_dir / "artifacts" / "formal_search_plan.json",
            run_dir / "artifacts" / "industry_scope_pack.json",
        ],
        "artifacts/content_quality_validation.json": [
            run_dir / "renderer_spec.json",
            run_dir / "industry_research_pack.md",
        ],
        "artifacts/renderer_spec_validation.json": [
            run_dir / "renderer_spec.json",
            run_dir / "template_registry.json",
            run_dir / "deck_blueprint.json",
            run_dir / "page_evidence_contract.json",
        ],
        "artifacts/research_pack_validation.json": [
            run_dir / "industry_research_pack.md",
        ],
        "artifacts/source_reviews_validation.json": [
            run_dir / "artifacts" / "source_reviews.json",
            run_dir / "artifacts" / "source_archive" / "source_archive_index.json",
            run_dir / "artifacts" / "search_log.md",
            run_dir / "artifacts" / "formal_research_execution_report.json",
            run_dir / "industry_research_pack.md",
        ],
        "artifacts/source_archive_validation.json": [
            run_dir / "artifacts" / "source_reviews.json",
            run_dir / "artifacts" / "source_archive" / "source_archive_index.json",
        ],
        "artifacts/formal_research_execution_validation.json": [
            run_dir / "artifacts" / "formal_research_execution_report.json",
            run_dir / "artifacts" / "formal_search_plan.json",
            run_dir / "artifacts" / "formal_search_plan_validation.json",
            run_dir / "artifacts" / "search_log.md",
        ],
        "artifacts/stage_gate_pre_research_pack_validation.json": [
            run_dir / "artifacts" / "industry_scope_pack.json",
            run_dir / "artifacts" / "industry_scope_pack_validation.json",
            run_dir / "artifacts" / "formal_search_plan_validation.json",
            run_dir / "artifacts" / "formal_research_execution_report.json",
            run_dir / "artifacts" / "formal_research_execution_validation.json",
            run_dir / "artifacts" / "source_reviews.json",
            run_dir / "artifacts" / "source_reviews_validation.json",
            run_dir / "artifacts" / "formal_search_plan.json",
            run_dir / "artifacts" / "search_log.md",
        ],
        "artifacts/issue_analysis_validation.json": [
            run_dir / "industry_issue_analysis.json",
            run_dir / "industry_research_pack.md",
        ],
        "artifacts/template_registry_validation.json": [
            run_dir / "template_registry.json",
        ],
        "artifacts/deck_blueprint_validation.json": [
            run_dir / "industry_issue_analysis.json",
            run_dir / "template_registry.json",
            run_dir / "deck_blueprint.json",
        ],
        "artifacts/page_evidence_contract_validation.json": [
            run_dir / "industry_issue_analysis.json",
            run_dir / "deck_blueprint.json",
            run_dir / "page_evidence_contract.json",
        ],
        "artifacts/replacement_dict_validation.json": [
            run_dir / "replacement_dict.json",
            run_dir / "renderer_spec.json",
            REPO_ROOT / "templates/ppt_mapping.json",
        ],
        "filled_ppt_validation.json": [
            run_dir / "renderer_spec.json",
            run_dir / "replacement_dict.json",
            run_dir / "industry_section_filled.pptx",
            run_dir / "industry_section_filled_clean.pptx",
        ],
    }

    for rel, fields in checks.items():
        artifact_path = run_dir / rel
        if not artifact_path.exists():
            continue
        try:
            data = load_json_file(artifact_path)
        except Exception as exc:
            errors.append(f"cannot check artifact provenance for {rel}: {exc}")
            continue
        for field in fields:
            cursor: Any = data
            for part in field.split("."):
                cursor = cursor.get(part, {}) if isinstance(cursor, dict) else {}
            if isinstance(cursor, str) and not is_within_run(cursor, run_dir):
                errors.append(f"{rel} field '{field}' points outside current run: {cursor}")
        try:
            artifact_mtime = artifact_path.stat().st_mtime
        except OSError:
            continue
        source_files = source_files_by_artifact.get(rel, [])
        newer_sources = [path.name for path in source_files if path.exists() and path.stat().st_mtime > artifact_mtime + 1.0]
        if newer_sources:
            errors.append(f"{rel} is older than source file(s): {', '.join(newer_sources)}; rerun validation")
    return errors, warnings


def validate_formal_research_execution_artifact(run_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    plan_path = run_dir / "artifacts/formal_search_plan.json"
    report_path = run_dir / "artifacts/formal_research_execution_report.json"
    artifact_path = run_dir / "artifacts/formal_research_execution_validation.json"
    search_log_path = run_dir / "artifacts/search_log.md"
    if not plan_path.exists():
        errors.append("missing formal_search_plan.json")
    if not report_path.exists():
        errors.append("missing formal_research_execution_report.json")
    if not search_log_path.exists():
        errors.append("missing search_log.md")
    if errors:
        return errors, warnings

    try:
        plan_data = load_json_file(plan_path)
        report_data = load_json_file(report_path)
    except Exception as exc:
        errors.append(f"cannot load formal research artifacts: {exc}")
        return errors, warnings

    current_errors, current_warnings = validate_formal_research_execution_data(report_data, plan_data, search_log_path)
    if current_errors:
        errors.append("current formal research execution validation failed")
        errors.extend(str(item) for item in current_errors)
    warnings.extend(str(item) for item in current_warnings)

    if artifact_path.exists():
        try:
            artifact = load_json_file(artifact_path)
        except Exception as exc:
            errors.append(f"cannot read formal_research_execution_validation.json: {exc}")
        else:
            if artifact.get("is_valid") is False:
                errors.append("formal_research_execution_validation.json is_valid=false")
            if artifact.get("warning_count", 0):
                warnings.append(f"formal_research_execution_validation.json contains {artifact.get('warning_count')} warning(s)")
    else:
        errors.append("missing formal_research_execution_validation.json")

    return errors, warnings


def validate_formal_search_plan_artifact(run_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    plan_path = run_dir / "artifacts/formal_search_plan.json"
    artifact_path = run_dir / "artifacts/formal_search_plan_validation.json"
    if not plan_path.exists():
        return ["missing formal_search_plan.json"], warnings
    try:
        plan_data = load_json_file(plan_path)
    except Exception as exc:
        return [f"cannot read formal_search_plan.json: {exc}"], warnings

    current_errors, current_warnings = validate_formal_search_plan_data(plan_data)
    if current_errors:
        errors.append("current formal search plan validation failed")
        errors.extend(str(item) for item in current_errors)
    warnings.extend(str(item) for item in current_warnings)

    if artifact_path.exists():
        try:
            artifact = load_json_file(artifact_path)
        except Exception as exc:
            errors.append(f"cannot read formal_search_plan_validation.json: {exc}")
        else:
            if artifact.get("is_valid") is False:
                errors.append("formal_search_plan_validation.json is_valid=false")
    else:
        errors.append("missing formal_search_plan_validation.json")
    return errors, warnings


def validate_industry_scope_pack_artifact(run_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    scope_path = run_dir / "artifacts/industry_scope_pack.json"
    artifact_path = run_dir / "artifacts/industry_scope_pack_validation.json"
    if not scope_path.exists():
        return ["missing industry_scope_pack.json"], warnings
    try:
        scope_data = load_json_file(scope_path)
    except Exception as exc:
        return [f"cannot read industry_scope_pack.json: {exc}"], warnings

    current_errors, current_warnings = validate_industry_scope_pack_data(scope_data)
    if current_errors:
        errors.append("current industry scope pack validation failed")
        errors.extend(str(item) for item in current_errors)
    warnings.extend(str(item) for item in current_warnings)

    if artifact_path.exists():
        try:
            artifact = load_json_file(artifact_path)
        except Exception as exc:
            errors.append(f"cannot read industry_scope_pack_validation.json: {exc}")
        else:
            if artifact.get("is_valid") is False:
                errors.append("industry_scope_pack_validation.json is_valid=false")
    else:
        errors.append("missing industry_scope_pack_validation.json")

    return errors, warnings


def validate_current_content_quality(run_dir: Path, rules_path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    renderer_spec_path = run_dir / "renderer_spec.json"
    memo_path = run_dir / "industry_research_pack.md"
    if not renderer_spec_path.exists():
        return ["cannot recompute content quality: missing renderer_spec.json"], warnings

    result = validate_content_quality(
        renderer_spec_path,
        memo_path if memo_path.exists() else None,
        rules_path,
        text_fit_rules_path=REPO_ROOT / "templates/text_fit_rules.json",
        layout_budget_path=REPO_ROOT / "templates/layout_budget.json",
    )
    if result.get("is_valid") is False:
        errors.append("current content quality validation failed")
        warnings.extend(str(item) for item in result.get("errors", []))
    if int(result.get("warning_count") or 0):
        warnings.append(f"current content quality validation has {result.get('warning_count')} advisory warning(s)")
        warnings.extend(str(item) for item in result.get("warnings", []))
    for key in FINAL_BLOCKING_CONTENT_WARNING_KEYS:
        values = result.get(key, [])
        if not isinstance(values, list):
            continue
        for item in values:
            text = str(item)
            lowered = text.lower()
            if any(fragment in lowered for fragment in BENIGN_FINAL_WARNING_FRAGMENTS):
                continue
            errors.append(f"current content quality final-readiness issue in {key}: {text}")

    blocking_issues = result.get("blocking_issues") or []
    if blocking_issues:
        errors.append(
            "current content quality validation contains blocking source/layout issues; resolve before delivery"
        )
        warnings.extend(str(item) for item in blocking_issues)
    return errors, warnings


def validate_postprocess_artifact(run_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    renderer_spec_path = run_dir / "renderer_spec.json"
    log_path = run_dir / "artifacts/postprocess_ppt_visuals.log.json"
    if not renderer_spec_path.exists():
        return errors, warnings

    try:
        renderer_spec = load_json_file(renderer_spec_path)
    except Exception as exc:
        return [f"cannot validate postprocess outputs: cannot read renderer_spec: {exc}"], warnings

    slides = renderer_spec.get("slides", [])
    if not isinstance(slides, list):
        return errors, warnings

    selected_by_slide = {
        int(slide.get("slide_no")): slide.get("selected_page_type")
        for slide in slides
        if isinstance(slide, dict) and isinstance(slide.get("slide_no"), int)
    }
    required_real_tables = []
    if selected_by_slide.get(2) == "chart_plus_mini_table_page":
        required_real_tables.append((2, "Slide 2 mini table"))
    if selected_by_slide.get(6) == "compare_table_page":
        required_real_tables.append((6, "Slide 6 compare table"))
    if not required_real_tables:
        return errors, warnings

    if not log_path.exists():
        errors.append("missing postprocess_ppt_visuals.log.json; cannot verify required real table rendering")
        return errors, warnings

    try:
        log_data = load_json_file(log_path)
    except Exception as exc:
        errors.append(f"cannot read postprocess_ppt_visuals.log.json: {exc}")
        return errors, warnings

    render_entries = log_data.get("chart_rendering", [])
    if not isinstance(render_entries, list):
        errors.append("postprocess_ppt_visuals.log.json missing chart_rendering list")
        return errors, warnings

    entries_by_slide = {
        entry.get("slide_no"): entry
        for entry in render_entries
        if isinstance(entry, dict)
    }
    for slide_no, label in required_real_tables:
        entry = entries_by_slide.get(slide_no)
        if not isinstance(entry, dict):
            errors.append(f"{label} was selected but has no postprocess rendering log entry")
            continue
        if slide_no == 2:
            table_result = entry.get("table", {})
            if not isinstance(table_result, dict) or table_result.get("rendered") is not True:
                errors.append(f"{label} did not render as a real PPT table object")
        elif slide_no == 6:
            if entry.get("rendered") is not True:
                errors.append(f"{label} did not render as a real PPT table object")
    return errors, warnings


def validate_issue_artifacts(run_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    issue_analysis_path = run_dir / "industry_issue_analysis.json"
    template_registry_path = run_dir / "template_registry.json"
    deck_blueprint_path = run_dir / "deck_blueprint.json"
    page_contract_path = run_dir / "page_evidence_contract.json"
    memo_path = run_dir / "industry_research_pack.md"

    required_files = {
        "industry_issue_analysis.json": issue_analysis_path,
        "template_registry.json": template_registry_path,
        "deck_blueprint.json": deck_blueprint_path,
        "page_evidence_contract.json": page_contract_path,
    }
    for name, path in required_files.items():
        if not path.exists():
            errors.append(f"missing required issue analysis artifact: {name}")
    if errors:
        return errors, warnings

    try:
        issue_analysis = load_json_file(issue_analysis_path)
        template_registry = load_json_file(template_registry_path)
        deck_blueprint = load_json_file(deck_blueprint_path)
        page_contract = load_json_file(page_contract_path)
    except Exception as exc:
        errors.append(f"cannot load issue analysis artifacts: {exc}")
        return errors, warnings

    issue_errors, issue_warnings = validate_issue_analysis_data(
        issue_analysis,
        memo_path if memo_path.exists() else None,
    )
    if issue_errors:
        errors.append("current issue analysis validation failed")
        errors.extend(str(item) for item in issue_errors)
    warnings.extend(str(item) for item in issue_warnings)

    template_registry_errors, template_registry_warnings = validate_template_registry_data(template_registry)
    if template_registry_errors:
        errors.append("current template registry validation failed")
        errors.extend(str(item) for item in template_registry_errors)
    warnings.extend(str(item) for item in template_registry_warnings)

    deck_errors, deck_warnings = validate_deck_blueprint_data(deck_blueprint, issue_analysis, template_registry)
    if deck_errors:
        errors.append("current deck blueprint validation failed")
        errors.extend(str(item) for item in deck_errors)
    warnings.extend(str(item) for item in deck_warnings)

    page_contract_errors, page_contract_warnings = validate_page_evidence_contract_data(
        issue_analysis,
        normalize_deck_blueprint_for_page_plan(deck_blueprint),
        page_contract,
    )
    if page_contract_errors:
        errors.append("current page evidence contract validation failed")
        errors.extend(str(item) for item in page_contract_errors)
    warnings.extend(str(item) for item in page_contract_warnings)

    for artifact_name in (
        "issue_analysis_validation.json",
        "template_registry_validation.json",
        "deck_blueprint_validation.json",
        "page_evidence_contract_validation.json",
    ):
        artifact_path = run_dir / "artifacts" / artifact_name
        if not artifact_path.exists():
            errors.append(f"missing {artifact_name}")
            continue
        try:
            artifact = load_json_file(artifact_path)
        except Exception as exc:
            errors.append(f"cannot read {artifact_name}: {exc}")
            continue
        if artifact.get("is_valid") is False:
            errors.append(f"{artifact_name} is_valid=false")

    return errors, warnings


def validate_renderer_spec_artifact(run_dir: Path) -> tuple[list[str], list[str]]:
    renderer_spec_path = run_dir / "renderer_spec.json"
    if not renderer_spec_path.exists():
        return ["missing renderer_spec.json"], []
    errors: list[str] = []
    warnings: list[str] = []
    try:
        result_errors, result_warnings = validate_renderer_spec_data(
            load_json_file(renderer_spec_path),
            load_json_file(run_dir / "template_registry.json"),
            normalize_deck_blueprint_for_page_plan(load_json_file(run_dir / "deck_blueprint.json")),
            load_json_file(run_dir / "page_evidence_contract.json"),
        )
    except Exception as exc:
        return [f"current renderer spec validation failed: {exc}"], warnings
    if result_errors:
        errors.append("current renderer spec validation failed")
        errors.extend(str(item) for item in result_errors)
    warnings.extend(str(item) for item in result_warnings)
    return errors, warnings


def validate_replacement_dict_artifact(run_dir: Path) -> tuple[list[str], list[str]]:
    replacement_path = run_dir / "replacement_dict.json"
    renderer_spec_path = run_dir / "renderer_spec.json"
    ppt_mapping_path = REPO_ROOT / "templates/ppt_mapping.json"
    artifact_path = run_dir / "artifacts/replacement_dict_validation.json"
    errors: list[str] = []
    warnings: list[str] = []
    if not replacement_path.exists():
        errors.append("missing replacement_dict.json")
        return errors, warnings
    if not artifact_path.exists():
        errors.append("missing replacement_dict_validation.json")
    else:
        try:
            artifact = load_json_file(artifact_path)
        except Exception as exc:
            errors.append(f"cannot read replacement_dict_validation.json: {exc}")
        else:
            if artifact.get("is_valid") is False:
                errors.append("replacement_dict_validation.json is_valid=false")
            warnings.extend(str(item) for item in artifact.get("warnings", []))
    try:
        result_errors, result_warnings = validate_replacement_dict_data(
            load_json_file(replacement_path),
            load_json_file(renderer_spec_path),
            load_json_file(ppt_mapping_path),
            renderer_spec_path=renderer_spec_path,
            ppt_mapping_path=ppt_mapping_path,
        )
    except Exception as exc:
        errors.append(f"current replacement dict validation failed: {exc}")
        return errors, warnings
    if result_errors:
        errors.append("current replacement dict validation failed")
        errors.extend(str(item) for item in result_errors)
    warnings.extend(str(item) for item in result_warnings)
    return errors, warnings


def validate_research_pack_artifact(run_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    memo_path = run_dir / "industry_research_pack.md"
    if not memo_path.exists():
        return ["missing industry_research_pack.md"], warnings

    result = validate_research_pack_data(memo_path, run_dir)
    if result.get("is_valid") is False:
        errors.append("current research pack validation failed")
        errors.extend(str(item) for item in result.get("errors", []))
    warnings.extend(str(item) for item in result.get("warnings", []))

    artifact_path = run_dir / "artifacts/research_pack_validation.json"
    if artifact_path.exists():
        try:
            artifact = load_json_file(artifact_path)
        except Exception as exc:
            errors.append(f"cannot read research_pack_validation.json: {exc}")
        else:
            if artifact.get("is_valid") is False:
                errors.append("research_pack_validation.json is_valid=false")
    else:
        errors.append("missing research_pack_validation.json")
    return errors, warnings


def validate_source_reviews_artifact(run_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    source_reviews_path = run_dir / "artifacts/source_reviews.json"
    source_archive_index_path = run_dir / "artifacts/source_archive/source_archive_index.json"
    result = validate_source_reviews_data(
        source_reviews_path,
        search_log_path=run_dir / "artifacts/search_log.md",
        formal_research_execution_report_path=run_dir / "artifacts/formal_research_execution_report.json",
        memo_path=run_dir / "industry_research_pack.md",
        source_archive_index_path=source_archive_index_path,
        run_dir=run_dir,
    )
    if result.get("is_valid") is False:
        errors.append("current source review validation failed")
        errors.extend(str(item) for item in result.get("errors", []))
    warnings.extend(str(item) for item in result.get("warnings", []))

    artifact_path = run_dir / "artifacts/source_reviews_validation.json"
    if artifact_path.exists():
        try:
            artifact = load_json_file(artifact_path)
        except Exception as exc:
            errors.append(f"cannot read source_reviews_validation.json: {exc}")
        else:
            if artifact.get("is_valid") is False:
                errors.append("source_reviews_validation.json is_valid=false")
    else:
        errors.append("missing source_reviews_validation.json")
    archive_artifact_path = run_dir / "artifacts/source_archive_validation.json"
    if archive_artifact_path.exists():
        try:
            archive_artifact = load_json_file(archive_artifact_path)
        except Exception as exc:
            errors.append(f"cannot read source_archive_validation.json: {exc}")
        else:
            if archive_artifact.get("is_valid") is False:
                errors.append("source_archive_validation.json is_valid=false")
    else:
        errors.append("missing source_archive_validation.json")
    return errors, warnings


def validate(run_dir: Path, source_registry: Optional[Path] = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    technical_delivery_valid = True
    research_evidence_valid = True

    if (run_dir / "DEBUG_OUTPUT_ONLY.txt").exists():
        errors.append(
            "run is marked DEBUG_OUTPUT_ONLY; debug/ungated PPTs must not be validated or delivered as final"
        )
        technical_delivery_valid = False

    run_flags_path = run_dir / "artifacts/run_flags.json"
    if not run_flags_path.exists():
        errors.append("missing artifacts/run_flags.json; final delivery requires recorded pipeline flags")
    else:
        try:
            run_flags = load_json_file(run_flags_path)
        except Exception as exc:
            errors.append(f"cannot read artifacts/run_flags.json: {exc}")
            run_flags = {}
        if isinstance(run_flags, dict):
            if run_flags.get("research_gate") != 1:
                errors.append("run_flags.json indicates research_gate was disabled; debug runs cannot be final")
            if run_flags.get("issue_analysis_layer") != 1:
                errors.append("run_flags.json indicates issue_analysis_layer was disabled; non-issue-analysis runs cannot be final")
            if run_flags.get("debug_output_only") is True:
                errors.append("run_flags.json marks this as debug_output_only; debug runs cannot be final")

    artifact_result = validate_run_artifacts(run_dir, require_research=True)
    errors.extend(artifact_result["errors"])
    warnings.extend(artifact_result["warnings"])

    provenance_errors, provenance_warnings = validate_artifact_provenance(run_dir)
    errors.extend(provenance_errors)
    warnings.extend(provenance_warnings)

    for path in json_files_under(run_dir):
        result = check_file(path)
        if not result["is_valid"]:
            errors.append(f"invalid JSON: {path}: {result['error']}")

    input_card = run_dir / "input_card.json"
    if input_card.exists():
        try:
            input_result = validate_input_card_data(load_json_file(input_card))
        except Exception as exc:
            errors.append(f"cannot validate input_card.json: {exc}")
        else:
            errors.extend(input_result["errors"])
            warnings.extend(input_result["warnings"])

    content_errors, content_warnings = validate_content_quality_artifact(
        run_dir / "artifacts/content_quality_validation.json"
    )
    errors.extend(content_errors)
    warnings.extend(content_warnings)

    scope_errors, scope_warnings = validate_industry_scope_pack_artifact(run_dir)
    errors.extend(scope_errors)
    warnings.extend(scope_warnings)

    plan_errors, plan_warnings = validate_formal_search_plan_artifact(run_dir)
    errors.extend(plan_errors)
    warnings.extend(plan_warnings)

    research_errors, research_warnings = validate_formal_research_execution_artifact(run_dir)
    errors.extend(research_errors)
    warnings.extend(research_warnings)

    source_review_errors, source_review_warnings = validate_source_reviews_artifact(run_dir)
    errors.extend(source_review_errors)
    warnings.extend(source_review_warnings)

    memo_errors, memo_warnings = validate_research_pack_artifact(run_dir)
    errors.extend(memo_errors)
    warnings.extend(memo_warnings)

    stage_gate_artifact = run_dir / "artifacts/stage_gate_pre_ppt_validation.json"
    if not stage_gate_artifact.exists():
        errors.append("missing stage_gate_pre_ppt_validation.json")
    else:
        try:
            stage_gate_data = load_json_file(stage_gate_artifact)
        except Exception as exc:
            errors.append(f"cannot read stage_gate_pre_ppt_validation.json: {exc}")
        else:
            if stage_gate_data.get("is_valid") is False:
                errors.append("stage_gate_pre_ppt_validation.json is_valid=false")

    current_stage_gate = validate_stage_gate_data("pre_ppt", run_dir, source_registry)
    if current_stage_gate.get("is_valid") is False:
        errors.append("current pre-PPT stage gate validation failed")
        errors.extend(str(item) for item in current_stage_gate.get("errors", []))
    warnings.extend(str(item) for item in current_stage_gate.get("warnings", []))

    issue_errors, issue_warnings = validate_issue_artifacts(run_dir)
    errors.extend(issue_errors)
    warnings.extend(issue_warnings)

    renderer_spec_errors, renderer_spec_warnings = validate_renderer_spec_artifact(run_dir)
    errors.extend(renderer_spec_errors)
    warnings.extend(renderer_spec_warnings)

    replacement_errors, replacement_warnings = validate_replacement_dict_artifact(run_dir)
    errors.extend(replacement_errors)
    warnings.extend(replacement_warnings)

    current_content_errors, current_content_warnings = validate_current_content_quality(
        run_dir,
        REPO_ROOT / "templates/content_quality_rules.json",
    )
    errors.extend(current_content_errors)
    warnings.extend(current_content_warnings)

    postprocess_errors, postprocess_warnings = validate_postprocess_artifact(run_dir)
    errors.extend(postprocess_errors)
    warnings.extend(postprocess_warnings)

    ppt_paths = {
        "filled_ppt_path": run_dir / "industry_section_filled.pptx",
        "clean_ppt_path": run_dir / "industry_section_filled_clean.pptx",
        "control_file_path": run_dir / "renderer_spec.json",
        "replacement_dict_path": run_dir / "replacement_dict.json",
        "ppt_mapping_path": REPO_ROOT / "templates/ppt_mapping.json",
    }
    if all(path.exists() for path in ppt_paths.values()):
        try:
            from validate_filled_ppt import build_report

            ppt_report = build_report(**ppt_paths)
        except Exception as exc:
            errors.append(f"cannot validate final PPT: {exc}")
            technical_delivery_valid = False
        else:
            if not ppt_report["summary"]["is_valid"]:
                errors.append("final PPT validation failed")
                technical_delivery_valid = False
                for issue in ppt_report.get("visible_scaffold_label_issues", []):
                    warnings.append(f"visible scaffold label: slide {issue['slide_no']} {issue['text']}")
                for issue in ppt_report.get("page_number_check", {}).get("issues", []):
                    warnings.append(
                        f"page number issue: slide {issue['slide_no']} expected {issue['expected']} found {issue['found']}"
                    )
    else:
        missing = [name for name, path in ppt_paths.items() if not path.exists()]
        errors.append("missing final PPT validation input(s): " + ", ".join(missing))
        technical_delivery_valid = False

    research_error_terms = (
        "research",
        "formal search",
        "search plan",
        "search_log",
        "search log",
        "research pack",
        "evidence",
        "metric",
        "MET-",
        "EV-",
        "source",
        "content quality",
        "issue analysis",
        "renderer",
        "deck blueprint",
        "page plan",
        "stage_gate",
    )
    research_evidence_valid = not any(
        any(term.lower() in str(error).lower() for term in research_error_terms)
        for error in errors
    )
    errors = unique_preserve_order(errors)
    warnings = unique_preserve_order(warnings)
    client_ready = technical_delivery_valid and research_evidence_valid and not errors

    return {
        "is_valid": not errors,
        "technical_delivery_valid": technical_delivery_valid,
        "research_evidence_valid": research_evidence_valid,
        "client_ready": client_ready,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "run_dir": str(run_dir),
        "source_registry": str(source_registry) if source_registry else "",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the final delivery gate for an industry section output.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--source-registry", default="templates/source_registry.json")
    parser.add_argument("--output", help="Optional JSON report path")
    parser.add_argument(
        "--require-client-ready",
        action="store_true",
        help="Exit non-zero unless the run is client_ready=true, not merely technically valid.",
    )
    args = parser.parse_args()

    result = validate(Path(args.run_dir), Path(args.source_registry) if args.source_registry else None)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["is_valid"]:
        sys.exit(1)
    if args.require_client_ready and not result.get("client_ready"):
        sys.exit(1)


if __name__ == "__main__":
    main()
