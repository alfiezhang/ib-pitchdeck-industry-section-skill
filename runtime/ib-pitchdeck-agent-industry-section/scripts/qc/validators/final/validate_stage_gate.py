#!/usr/bin/env python3
"""Deterministic stage gates for the industry-section workflow."""

from __future__ import annotations

# Runtime scripts can be run directly. Shared helpers remain in runtime
# `scripts/`; production tools live under role scripts; validators live under QC.
import sys as _ib_sys
from pathlib import Path as _IbPath
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
from pathlib import Path
from typing import Any, Optional

from deck_blueprint_utils import normalize_deck_blueprint_for_page_plan
from json_utils import load_json_file
from validate_content_quality import validate as validate_content_quality
from validate_chart_metric_binding import validate as validate_chart_metric_binding
from validate_industry_scope_pack import validate as validate_industry_scope_pack
from validate_issue_analysis import validate as validate_issue_analysis
from validate_research_pack import validate as validate_research_pack
from research_evidence_db import validate_db as validate_research_evidence_db_data
from validate_page_evidence_contract import validate as validate_page_evidence_contract
from validate_deck_blueprint import validate as validate_deck_blueprint
from validate_renderer_spec import validate as validate_renderer_spec
from validate_run_artifacts import validate_search_log
from validate_source_archive import validate as validate_source_archive
from validate_template_registry import validate as validate_template_registry
from validate_formal_research_execution import validate as validate_formal_research_execution
from validate_formal_search_plan import validate as validate_formal_search_plan
from qc_repair_targets import collect_repair_targets, unique_repair_targets


REPO_ROOT = _IB_RUNTIME_ROOT


def resolve_repo_path(path: Optional[Path]) -> Optional[Path]:
    if path is None:
        return None
    if path.is_absolute() or path.exists():
        return path
    return REPO_ROOT / path


def _append_repair_targets(
    target_list: Optional[list[dict[str, Any]]],
    report: dict[str, Any] | None,
    *,
    default_layer: str = "unknown",
    default_artifact: str = "",
) -> None:
    if target_list is None or not isinstance(report, dict):
        return
    target_list.extend(
        collect_repair_targets(
            report,
            default_layer=default_layer,
            default_artifact=default_artifact,
        )
    )


def _append_validation_issue(
    target_list: Optional[list[dict[str, Any]]],
    *,
    artifact: str,
    layer: str,
    errors: list[str],
    recommended_action: str = "",
    forbidden_action: str = "",
) -> None:
    if not errors:
        return
    _append_repair_targets(
        target_list,
        {
            "is_valid": False,
            "errors": errors,
            "repair_target_layer": layer,
            "repair_target_artifact": artifact,
            "recommended_action": recommended_action or f"Fix and re-run validation for {artifact}.",
            "forbidden_action": forbidden_action,
        },
        default_layer=layer,
        default_artifact=artifact,
    )


def load_json_if_exists(path: Path, errors: list[str]) -> Optional[dict[str, Any]]:
    if not path.exists():
        errors.append(f"missing required artifact: {path}")
        return None
    try:
        data = load_json_file(path)
    except Exception as exc:
        errors.append(f"cannot read {path}: {exc}")
        return None
    if not isinstance(data, dict):
        errors.append(f"{path} must contain a JSON object")
        return None
    return data


def require_valid_artifact(
    path: Path,
    errors: list[str],
    warnings: list[str],
    repair_targets: Optional[list[dict[str, Any]]] = None,
    *,
    default_layer: str = "unknown",
    default_artifact: str = "",
) -> Optional[dict[str, Any]]:
    data = load_json_if_exists(path, errors)
    if data is None:
        _append_validation_issue(
            repair_targets,
            artifact=default_artifact or str(path.name),
            layer=default_layer,
            errors=[f"missing required artifact: {path}"],
            recommended_action="Re-run the corresponding validation step and fix upstream inputs before proceeding.",
            forbidden_action="Do not proceed to downstream artifacts while this validation is missing.",
        )
        return None
    if not data:
        return None
    _append_repair_targets(
        repair_targets,
        data,
        default_layer=default_layer,
        default_artifact=default_artifact or str(path.name),
    )
    if isinstance(data, dict) and data.get("is_valid") is False:
        _append_repair_targets(
            repair_targets,
            data,
            default_layer=default_layer,
            default_artifact=default_artifact or str(path.name),
        )
    if data.get("is_valid") is False:
        errors.append(f"{path.name} is_valid=false")
    for key in ("errors", "blocking_issues"):
        values = data.get(key, [])
        if isinstance(values, list):
            warnings.extend(str(item) for item in values)
    return data


def require_no_blocking_artifact(
    path: Path,
    errors: list[str],
    warnings: list[str],
    repair_targets: Optional[list[dict[str, Any]]] = None,
    *,
    default_layer: str = "unknown",
    default_artifact: str = "",
) -> None:
    data = load_json_if_exists(path, errors)
    if data is None:
        _append_validation_issue(
            repair_targets,
            artifact=default_artifact or str(path.name),
            layer=default_layer,
            errors=[f"missing required artifact: {path}"],
            recommended_action="Re-run this validator before any downstream action.",
            forbidden_action="Do not proceed downstream until this blocker is cleared.",
        )
        return
    if not data:
        return
    _append_repair_targets(
        repair_targets,
        data,
        default_layer=default_layer,
        default_artifact=default_artifact or str(path.name),
    )
    if isinstance(data, dict) and data.get("is_valid") is False:
        _append_repair_targets(
            repair_targets,
            data,
            default_layer=default_layer,
            default_artifact=default_artifact or str(path.name),
        )
    if data.get("is_valid") is False:
        errors.append(f"{path.name} is_valid=false")
    blocking_items = data.get("blocking_issues") or []
    if blocking_items:
        errors.append(f"{path.name} contains {len(blocking_items)} blocking issue(s)")
    for key in ("errors", "blocking_issues", "warnings"):
        values = data.get(key, [])
        if isinstance(values, list):
            warnings.extend(str(item) for item in values)


def load_source_registry(path: Optional[Path], errors: list[str]) -> Optional[dict[str, Any]]:
    resolved = resolve_repo_path(path)
    if not resolved:
        return None
    if not resolved.exists():
        errors.append(f"source registry not found: {resolved}")
        return None
    try:
        data = load_json_file(resolved)
    except Exception as exc:
        errors.append(f"cannot read source registry {resolved}: {exc}")
        return None
    if not isinstance(data, dict):
        errors.append(f"source registry must be a JSON object: {resolved}")
        return None
    return data


def check_formal_search_plan_presence(
    run_dir: Path,
    errors: list[str],
    warnings: list[str],
    repair_targets: Optional[list[dict[str, Any]]] = None,
) -> None:
    artifacts = run_dir / "artifacts"
    plan_path = artifacts / "formal_search_plan.json"
    search_log_path = artifacts / "search_log.md"

    validation_path = artifacts / "formal_search_plan_validation.json"
    require_valid_artifact(
        validation_path,
        errors,
        warnings,
        repair_targets,
        default_layer="research",
        default_artifact="artifacts/formal_search_plan_validation.json",
    )
    plan_data = load_json_if_exists(plan_path, errors)
    if isinstance(plan_data, dict):
        plan_errors, plan_warnings = validate_formal_search_plan(plan_data)
        if plan_errors:
            errors.append("current formal search plan validation failed")
            errors.extend(str(item) for item in plan_errors)
            _append_validation_issue(
                repair_targets,
                artifact="artifacts/formal_search_plan.json",
                layer="research",
                errors=[str(item) for item in plan_errors],
                recommended_action="Fix execution expectation and taxonomy in formal_search_plan.json.",
                forbidden_action="Do not create archive/source IDs from unexecuted FS rows.",
            )
        warnings.extend(str(item) for item in plan_warnings)

    if not search_log_path.exists():
        errors.append(f"missing required artifact: {search_log_path}")
    else:
        search_errors, search_warnings = validate_search_log(search_log_path)
        errors.extend(search_errors)
        warnings.extend(search_warnings)


def validate_industry_scope_pack_gate(
    run_dir: Path,
    errors: list[str],
    warnings: list[str],
    repair_targets: Optional[list[dict[str, Any]]] = None,
) -> None:
    artifacts = run_dir / "artifacts"
    scope_path = artifacts / "industry_scope_pack.json"
    validation_path = artifacts / "industry_scope_pack_validation.json"

    require_valid_artifact(
        validation_path,
        errors,
        warnings,
        repair_targets,
        default_layer="industry",
        default_artifact="artifacts/industry_scope_pack_validation.json",
    )
    scope_data = load_json_if_exists(scope_path, errors)
    if isinstance(scope_data, dict):
        current_errors, current_warnings = validate_industry_scope_pack(scope_data)
        if current_errors:
            errors.append("current industry scope pack validation failed")
            errors.extend(current_errors)
            _append_validation_issue(
                repair_targets,
                artifact="artifacts/industry_scope_pack.json",
                layer="industry",
                errors=[str(item) for item in current_errors],
                recommended_action=(
                    "Repair scope definitions, exclusions, and confidence markers in industry_scope_pack.json."
                ),
            )
        warnings.extend(current_warnings)
        _append_repair_targets(
            repair_targets,
            {"is_valid": not current_errors},
            default_layer="industry",
            default_artifact="artifacts/industry_scope_pack.json",
        )


def validate_formal_research_execution_gate(
    run_dir: Path,
    errors: list[str],
    warnings: list[str],
    repair_targets: Optional[list[dict[str, Any]]] = None,
) -> None:
    artifacts = run_dir / "artifacts"
    report_path = artifacts / "formal_research_execution_report.json"
    validation_path = artifacts / "formal_research_execution_validation.json"
    plan_path = artifacts / "formal_search_plan.json"
    search_log_path = artifacts / "search_log.md"

    report_data = load_json_if_exists(report_path, errors)
    require_valid_artifact(
        validation_path,
        errors,
        warnings,
        repair_targets,
        default_layer="research",
        default_artifact="artifacts/formal_research_execution_validation.json",
    )
    plan_data = load_json_if_exists(plan_path, errors)
    _append_repair_targets(
        repair_targets,
        report_data if isinstance(report_data, dict) else None,
        default_layer="research",
        default_artifact="artifacts/formal_research_execution_report.json",
    )
    if isinstance(plan_data, dict):
        _append_repair_targets(
            repair_targets,
            {
                "is_valid": True,
                "repair_target_artifact": "artifacts/formal_search_plan.json",
                "repair_target_layer": "research",
            },
            default_layer="research",
            default_artifact="artifacts/formal_search_plan.json",
        )

    if not search_log_path.exists():
        errors.append(f"missing required artifact: {search_log_path}")
        _append_validation_issue(
            repair_targets,
            artifact="artifacts/search_log.md",
            layer="research",
            errors=[f"missing required artifact: {search_log_path}"],
            recommended_action="Re-run the search execution and append review-ready rows before generating FR report.",
            forbidden_action="Do not create FR accounting rows from planned entries.",
        )
        return

    if isinstance(report_data, dict) and isinstance(plan_data, dict):
        current_errors, current_warnings = validate_formal_research_execution(
            report_data,
            plan_data,
            search_log_path,
        )
        if current_errors:
            errors.append("current formal research execution report validation failed")
            errors.extend(current_errors)
            _append_validation_issue(
                repair_targets,
                artifact="artifacts/formal_research_execution_report.json",
                layer="research",
                errors=[str(item) for item in current_errors],
                recommended_action=(
                    "Repair terminal status and S-ID mapping in each FR row, then rerun this validator."
                ),
                forbidden_action="Do not treat FS-only evidence as executed.",
            )
        warnings.extend(current_warnings)


_SEARCH_COVERAGE_MIN = 0.60


def check_search_coverage(
    run_dir: Path,
    errors: list[str],
    warnings: list[str],
    repair_targets: Optional[list[dict[str, Any]]] = None,
) -> None:
    """Check that at least 60% of planned formal searches were actually executed."""
    artifacts = run_dir / "artifacts"
    report_path = artifacts / "formal_research_execution_report.json"
    if not report_path.exists():
        return  # report missing → other gates will catch this

    try:
        report_data = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return

    results = report_data.get("issue_results", [])
    if not results:
        return

    total = len(results)
    executed = sum(
        1 for r in results
        if r.get("terminal_status") not in {"not_executed", "accounting_only"}
    )
    ratio = executed / total if total else 0.0

    if ratio < _SEARCH_COVERAGE_MIN:
        skipped = total - executed
        errors.append(
            f"search coverage too low: {executed}/{total} ({ratio:.0%}) formal searches executed; "
            f"{skipped} rows skipped. minimum required: {_SEARCH_COVERAGE_MIN:.0%}"
        )
        _append_validation_issue(
            repair_targets,
            artifact="artifacts/formal_research_execution_report.json",
            layer="research",
            errors=[
                f"only {executed}/{total} planned formal searches were executed ({ratio:.0%}); "
                f"minimum is {_SEARCH_COVERAGE_MIN:.0%}"
            ],
            recommended_action=(
                "Execute the remaining formal searches from formal_search_plan.json, "
                "or mark them as 'not_material' with justification in the execution report."
            ),
            forbidden_action="Do not skip searches and proceed to evidence DB or issue analysis.",
        )


def validate_source_archive_gate(
    run_dir: Path,
    errors: list[str],
    warnings: list[str],
    *,
    require_memo_binding: bool = False,
    repair_targets: Optional[list[dict[str, Any]]] = None,
) -> None:
    artifacts = run_dir / "artifacts"
    archive_validation_path = artifacts / "source_archive_validation.json"
    archive_index_path = run_dir / "artifacts" / "source_archive" / "source_archive_index.json"

    require_valid_artifact(
        archive_validation_path,
        errors,
        warnings,
        repair_targets,
        default_layer="knowledge",
        default_artifact="artifacts/source_archive_validation.json",
    )
    result = validate_source_archive(
        source_archive_index_path=archive_index_path,
        run_dir=run_dir,
    )
    _append_repair_targets(
        repair_targets,
        result,
        default_layer="knowledge",
        default_artifact="artifacts/source_archive/source_archive_index.json",
    )
    if result.get("is_valid") is False:
        errors.append("current source archive validation failed")
        errors.extend(str(item) for item in result.get("errors", []))
        _append_validation_issue(
            repair_targets,
            artifact="artifacts/source_archive/source_archive_index.json",
            layer="knowledge",
            errors=[str(item) for item in result.get("errors", [])],
            recommended_action="Repair archived source entries from search_log/manual sources and rerun source archive validation.",
            forbidden_action="Do not extract evidence from unarchived planned searches.",
        )
    warnings.extend(str(item) for item in result.get("warnings", []))


def validate_research_pack_gate(
    run_dir: Path,
    source_registry: Optional[Path],
    errors: list[str],
    warnings: list[str],
    repair_targets: Optional[list[dict[str, Any]]] = None,
) -> None:
    memo_path = run_dir / "industry_research_pack.md"
    artifact_path = run_dir / "artifacts" / "research_pack_validation.json"
    db_path = run_dir / "artifacts" / "research_evidence_db.json"
    db_validation_path = run_dir / "artifacts" / "research_evidence_db_validation.json"

    if not db_path.exists():
        errors.append(f"missing required artifact: {db_path}")
    require_valid_artifact(
        db_validation_path,
        errors,
        warnings,
        repair_targets,
        default_layer="knowledge",
        default_artifact="artifacts/research_evidence_db_validation.json",
    )
    if db_path.exists():
        try:
            db_errors, db_warnings, _ = validate_research_evidence_db_data(load_json_file(db_path))
        except Exception as exc:
            errors.append(f"cannot validate current research_evidence_db.json: {exc}")
            db_warnings = []
            _append_validation_issue(
                repair_targets,
                artifact="artifacts/research_evidence_db.json",
                layer="knowledge",
                errors=[str(exc)],
                recommended_action="Rebuild research_evidence_db.json from reviewed evidence and rerun validator.",
            )
        else:
            if db_errors:
                errors.append("current research evidence db validation failed")
                errors.extend(str(item) for item in db_errors)
                _append_validation_issue(
                    repair_targets,
                    artifact="artifacts/research_evidence_db.json",
                    layer="knowledge",
                    errors=[str(item) for item in db_errors],
                    recommended_action="Repair invalid rows in research_evidence_db.json and re-export evidence summary.",
                    forbidden_action="Do not create evidence ids without sourced URLs and locators.",
                )
        warnings.extend(str(item) for item in db_warnings)
        _append_repair_targets(
            repair_targets,
            {"is_valid": not db_errors if db_errors is not None else False},
            default_layer="knowledge",
            default_artifact="artifacts/research_evidence_db.json",
        )
    if not memo_path.exists():
        errors.append(f"missing required artifact: {memo_path}")
    require_valid_artifact(
        artifact_path,
        errors,
        warnings,
        repair_targets,
        default_layer="knowledge",
        default_artifact="artifacts/research_pack_validation.json",
    )

    if memo_path.exists():
        current_result = validate_research_pack(memo_path, run_dir=run_dir, source_registry_path=resolve_repo_path(source_registry))
        _append_repair_targets(
            repair_targets,
            current_result,
            default_layer="knowledge",
            default_artifact="industry_research_pack.md",
        )
        if current_result.get("is_valid") is False:
            errors.append("current research pack validation failed")
            _append_validation_issue(
                repair_targets,
                artifact="industry_research_pack.md",
                layer="knowledge",
                errors=[str(item) for item in current_result.get("errors", [])],
                recommended_action="Fix unsupported or unsupported claims in research pack then rerun validation.",
                forbidden_action="Do not skip research pack review before issue analysis.",
            )
        warnings.extend(str(item) for item in current_result.get("errors", []))


def validate_renderer_spec_gate(
    run_dir: Path,
    errors: list[str],
    warnings: list[str],
    repair_targets: Optional[list[dict[str, Any]]] = None,
) -> None:
    renderer_spec_path = run_dir / "renderer_spec.json"
    template_registry_path = run_dir / "template_registry.json"
    deck_blueprint_path = run_dir / "deck_blueprint.json"
    page_contract_path = run_dir / "page_evidence_contract.json"
    artifact_path = run_dir / "artifacts" / "renderer_spec_validation.json"

    if not renderer_spec_path.exists():
        errors.append(f"missing required artifact: {renderer_spec_path}")
    require_valid_artifact(
        artifact_path,
        errors,
        warnings,
        repair_targets,
        default_layer="generation",
        default_artifact="artifacts/renderer_spec_validation.json",
    )

    if renderer_spec_path.exists() and template_registry_path.exists() and deck_blueprint_path.exists() and page_contract_path.exists():
        try:
            deck_blueprint = load_json_file(deck_blueprint_path)
            current_errors, current_warnings = validate_renderer_spec(
                load_json_file(renderer_spec_path),
                load_json_file(template_registry_path),
                normalize_deck_blueprint_for_page_plan(deck_blueprint),
                load_json_file(page_contract_path),
            )
        except Exception as exc:
            errors.append(f"current renderer spec validation failed: {exc}")
            _append_validation_issue(
                repair_targets,
                artifact="renderer_spec.json",
                layer="generation",
                errors=[f"current renderer spec validation failed: {exc}"],
                recommended_action="Re-run compile_deck_blueprint.py after fixing deck blueprint and page evidence contract.",
                forbidden_action="Do not patch renderer_spec manually.",
            )
            return
        if current_errors:
            errors.append("current renderer spec validation failed")
            errors.extend(current_errors)
            _append_validation_issue(
                repair_targets,
                artifact="renderer_spec.json",
                layer="generation",
                errors=[str(item) for item in current_errors],
                recommended_action="Fix schema or field mapping mismatch in deck_blueprint.json, then recompile.",
            )
        warnings.extend(current_warnings)
        _append_repair_targets(
            repair_targets,
            {"is_valid": not current_errors, "repair_target_artifact": "renderer_spec.json"},
            default_layer="generation",
            default_artifact="renderer_spec.json",
        )


def validate_issue_analysis_gate(
    run_dir: Path,
    errors: list[str],
    warnings: list[str],
    repair_targets: Optional[list[dict[str, Any]]] = None,
) -> None:
    issue_analysis_path = run_dir / "industry_issue_analysis.json"
    page_argument_pack_path = run_dir / "artifacts" / "page_argument_pack.json"
    template_registry_path = run_dir / "template_registry.json"
    deck_blueprint_path = run_dir / "deck_blueprint.json"
    page_contract_path = run_dir / "page_evidence_contract.json"
    memo_path = run_dir / "industry_research_pack.md"

    missing = [
        str(path)
        for path in (issue_analysis_path, page_argument_pack_path, template_registry_path, deck_blueprint_path, page_contract_path)
        if not path.exists()
    ]
    if missing:
        errors.extend(f"missing required issue analysis artifact: {path}" for path in missing)
        return

    issue_analysis = load_json_if_exists(issue_analysis_path, errors)
    page_argument_pack = load_json_if_exists(page_argument_pack_path, errors)
    template_registry = load_json_if_exists(template_registry_path, errors)
    deck_blueprint = load_json_if_exists(deck_blueprint_path, errors)
    page_contract = load_json_if_exists(page_contract_path, errors)
    if not issue_analysis or not page_argument_pack or not template_registry or not deck_blueprint or not page_contract:
        return

    issue_result_errors, issue_result_warnings = validate_issue_analysis(
        issue_analysis,
        memo_path if memo_path.exists() else None,
    )
    issue_result = {
        "is_valid": not issue_result_errors,
        "errors": issue_result_errors,
        "warnings": issue_result_warnings,
        "repair_plan": {"targets": []},
    }
    _append_repair_targets(
        repair_targets,
        issue_result,
        default_layer="reasoning",
        default_artifact="industry_issue_analysis.json",
    )
    if issue_result.get("is_valid") is False:
        errors.append("current issue analysis validation failed")
        errors.extend(str(item) for item in issue_result.get("errors", []))
        _append_validation_issue(
            repair_targets,
            artifact="industry_issue_analysis.json",
            layer="reasoning",
            errors=[str(item) for item in issue_result_errors],
            recommended_action="Repair issue analyses and rerun validate_issue_analysis.py.",
            forbidden_action="Do not edit deck blueprint before issue analysis is valid.",
        )
    warnings.extend(str(item) for item in issue_result.get("warnings", []))

    template_registry_errors, template_registry_warnings = validate_template_registry(template_registry)
    _append_repair_targets(
        repair_targets,
        {
            "is_valid": not template_registry_errors,
            "errors": template_registry_errors,
            "repair_target_layer": "generation",
            "repair_target_artifact": "template_registry.json",
            "repair_targets": [],
            "repair_plan": {},
        },
        default_layer="generation",
        default_artifact="template_registry.json",
    )
    if template_registry_errors:
        errors.append("current template registry validation failed")
        errors.extend(str(item) for item in template_registry_errors)
        _append_validation_issue(
            repair_targets,
            artifact="template_registry.json",
            layer="generation",
            errors=[str(item) for item in template_registry_errors],
            recommended_action="Fix template_registry.json generation or source template input and rerun registry validator.",
            forbidden_action="Do not proceed deck compile until registry matches template.",
        )
    warnings.extend(str(item) for item in template_registry_warnings)

    deck_errors, deck_warnings, _ = validate_deck_blueprint(
        page_argument_pack=page_argument_pack,
        template_registry=template_registry,
        deck_blueprint=deck_blueprint,
        issue_analysis=issue_analysis,
    )
    _append_repair_targets(
        repair_targets,
        {
            "is_valid": not deck_errors,
            "errors": deck_errors,
            "repair_plan": {"targets": []},
            "repair_target_layer": "generation",
            "repair_target_artifact": "deck_blueprint.json",
        },
        default_layer="generation",
        default_artifact="deck_blueprint.json",
    )
    if deck_errors:
        errors.append("current deck blueprint validation failed")
        errors.extend(str(item) for item in deck_errors)
        _append_validation_issue(
            repair_targets,
            artifact="deck_blueprint.json",
            layer="generation",
            errors=[str(item) for item in deck_errors],
            recommended_action="Repair deck_blueprint.json and rerun validate_deck_blueprint.py before page contract compile.",
            forbidden_action="Do not manually edit renderer_spec.json for deck failures.",
        )
    warnings.extend(str(item) for item in deck_warnings)

    page_contract_errors, page_contract_warnings = validate_page_evidence_contract(
        page_argument_pack,
        normalize_deck_blueprint_for_page_plan(deck_blueprint),
        page_contract,
    )
    page_contract_result = {
        "is_valid": not page_contract_errors,
        "errors": page_contract_errors,
        "warnings": page_contract_warnings,
    }
    if page_contract_result.get("is_valid") is False:
        errors.append("current page evidence contract validation failed")
        errors.extend(str(item) for item in page_contract_result.get("errors", []))
        _append_validation_issue(
            repair_targets,
            artifact="page_evidence_contract.json",
            layer="generation",
            errors=[str(item) for item in page_contract_errors],
            recommended_action="Fix page evidence decisions and rerun validate_page_evidence_contract.py.",
        )
    warnings.extend(str(item) for item in page_contract_result.get("warnings", []))
    _append_repair_targets(
        repair_targets,
        {
            "is_valid": page_contract_result.get("is_valid"),
            "repair_plan": {
                "targets": [
                    {
                        "issue_type": "PAGE_EVIDENCE_CONTRACT",
                        "repair_target_artifact": "page_evidence_contract.json",
                    }
                ]
            },
            "repair_target_artifact": "page_evidence_contract.json",
            "repair_target_layer": "generation",
        },
        default_layer="generation",
        default_artifact="page_evidence_contract.json",
    )


def validate_content_gate(
    run_dir: Path,
    errors: list[str],
    warnings: list[str],
    repair_targets: Optional[list[dict[str, Any]]] = None,
) -> None:
    artifact_path = run_dir / "artifacts" / "content_quality_validation.json"
    renderer_spec_path = run_dir / "renderer_spec.json"
    memo_path = run_dir / "industry_research_pack.md"

    require_no_blocking_artifact(
        artifact_path,
        errors,
        warnings,
        repair_targets,
        default_layer="generation",
        default_artifact="artifacts/content_quality_validation.json",
    )

    if renderer_spec_path.exists():
        current_result = validate_content_quality(
            renderer_spec_path,
            memo_path if memo_path.exists() else None,
            REPO_ROOT / "configs" / "content_quality_rules.json",
            text_fit_rules_path=REPO_ROOT / "configs" / "text_fit_rules.json",
            layout_budget_path=REPO_ROOT / "configs" / "layout_budget.json",
        )
        if current_result.get("is_valid") is False:
            errors.append("current content quality validation failed")
        warnings.extend(str(item) for item in current_result.get("errors", []))
        warnings.extend(str(item) for item in current_result.get("warnings", []))
        warnings.extend(str(item) for item in current_result.get("blocking_issues", []))
        _append_repair_targets(
            repair_targets,
            current_result,
            default_layer="generation",
            default_artifact="renderer_spec.json",
        )
    else:
        errors.append(f"missing required artifact: {renderer_spec_path}")
        _append_validation_issue(
            repair_targets,
            artifact="renderer_spec.json",
            layer="generation",
            errors=[f"missing required artifact: {renderer_spec_path}"],
            recommended_action="Generate renderer_spec.json before content-quality validation.",
            forbidden_action="Do not patch downstream PPT files before content quality passes.",
        )


def validate_template_fit_gate(
    run_dir: Path,
    errors: list[str],
    warnings: list[str],
    repair_targets: Optional[list[dict[str, Any]]] = None,
) -> None:
    artifact_path = run_dir / "artifacts" / "template_fit_validation.json"
    require_no_blocking_artifact(
        artifact_path,
        errors,
        warnings,
        repair_targets,
        default_layer="generation",
        default_artifact="artifacts/template_fit_validation.json",
    )


def validate_chart_metric_binding_gate(
    run_dir: Path,
    errors: list[str],
    warnings: list[str],
    repair_targets: Optional[list[dict[str, Any]]] = None,
) -> None:
    artifact_path = run_dir / "artifacts" / "chart_metric_binding_validation.json"
    renderer_spec_path = run_dir / "renderer_spec.json"
    memo_path = run_dir / "industry_research_pack.md"
    page_contract_path = run_dir / "page_evidence_contract.json"

    require_no_blocking_artifact(
        artifact_path,
        errors,
        warnings,
        repair_targets,
        default_layer="generation",
        default_artifact="artifacts/chart_metric_binding_validation.json",
    )

    if not renderer_spec_path.exists():
        errors.append(f"missing required artifact: {renderer_spec_path}")
        _append_validation_issue(
            repair_targets,
            artifact="renderer_spec.json",
            layer="generation",
            errors=[f"missing required artifact: {renderer_spec_path}"],
            recommended_action="Run pipeline render compile path to regenerate renderer_spec.json.",
        )
        return
    if not memo_path.exists():
        errors.append(f"missing required artifact: {memo_path}")
        _append_validation_issue(
            repair_targets,
            artifact="industry_research_pack.md",
            layer="research",
            errors=[f"missing required artifact: {memo_path}"],
            recommended_action="Export or fix research pack before chart metric binding checks.",
        )
        return

    try:
        renderer_spec = load_json_file(renderer_spec_path)
        memo_text = memo_path.read_text(encoding="utf-8")
        page_contract = load_json_file(page_contract_path) if page_contract_path.exists() else None
        current_result = validate_chart_metric_binding(renderer_spec, memo_text, page_contract)
    except Exception as exc:
        errors.append(f"current chart metric binding validation failed: {exc}")
        _append_validation_issue(
            repair_targets,
            artifact="artifacts/chart_metric_binding_validation.json",
            layer="generation",
            errors=[str(exc)],
            recommended_action="Fix chart metric inputs in deck_blueprint and regenerate renderer_spec.",
        )
        return
    _append_repair_targets(
        repair_targets,
        current_result,
        default_layer="generation",
        default_artifact="renderer_spec.json",
    )
    if current_result.get("is_valid") is False:
        errors.append("current chart metric binding validation failed")
        _append_validation_issue(
            repair_targets,
            artifact="renderer_spec.json",
            layer="generation",
            errors=[str(item) for item in current_result.get("errors", [])],
            recommended_action="Repair chart metric binding in deck_blueprint.json and recompile.",
        )
    warnings.extend(str(item) for item in current_result.get("errors", []))
    warnings.extend(str(item) for item in current_result.get("warnings", []))
    for item in current_result.get("root_causes", []):
        if isinstance(item, dict):
            warnings.append(
                " | ".join(
                    part
                    for part in (
                        str(item.get("code") or ""),
                        str(item.get("message") or ""),
                        str(item.get("repair_hint") or ""),
                    )
                    if part
                )
            )


def validate_stage(stage: str, run_dir: Path, source_registry: Optional[Path]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    repair_targets: list[dict[str, Any]] = []

    if stage in {"pre_research_pack", "pre_renderer", "pre_ppt"}:
        validate_industry_scope_pack_gate(run_dir, errors, warnings, repair_targets=repair_targets)
        check_formal_search_plan_presence(run_dir, errors, warnings, repair_targets=repair_targets)
        validate_source_archive_gate(
            run_dir,
            errors,
            warnings,
            require_memo_binding=stage in {"pre_renderer", "pre_ppt"},
            repair_targets=repair_targets,
        )
        validate_formal_research_execution_gate(run_dir, errors, warnings, repair_targets=repair_targets)
        check_search_coverage(run_dir, errors, warnings, repair_targets=repair_targets)

    if stage in {"pre_renderer", "pre_ppt"}:
        validate_research_pack_gate(run_dir, source_registry, errors, warnings, repair_targets=repair_targets)
        validate_issue_analysis_gate(run_dir, errors, warnings, repair_targets=repair_targets)

    if stage == "pre_ppt":
        validate_template_fit_gate(run_dir, errors, warnings, repair_targets=repair_targets)
        validate_renderer_spec_gate(run_dir, errors, warnings, repair_targets=repair_targets)
        validate_chart_metric_binding_gate(run_dir, errors, warnings, repair_targets=repair_targets)
        validate_content_gate(run_dir, errors, warnings, repair_targets=repair_targets)

    return {
        "is_valid": not errors,
        "stage": stage,
        "run_dir": str(run_dir),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "repair_targets": unique_repair_targets(repair_targets),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate deterministic workflow stage gates.")
    parser.add_argument("--stage", required=True, choices=["pre_research_pack", "pre_renderer", "pre_ppt"])
    parser.add_argument("--run-dir", required=True, help="Run/attempt directory to validate.")
    parser.add_argument("--source-registry", default=str(REPO_ROOT / "configs" / "source_registry.json"))
    parser.add_argument("--output", help="Optional JSON report path.")
    args = parser.parse_args()

    result = validate_stage(args.stage, Path(args.run_dir), Path(args.source_registry) if args.source_registry else None)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            f.write("\n")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    if not result["is_valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
