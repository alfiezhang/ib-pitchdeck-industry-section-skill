#!/usr/bin/env python3
"""Final deterministic gate for a generated industry-section run."""

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
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts"
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
import subprocess
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
from research_evidence_db import validate_db as validate_research_evidence_db_data
from validate_page_evidence_contract import validate as validate_page_evidence_contract_data
from validate_deck_blueprint import validate as validate_deck_blueprint_data
from validate_formal_research_execution import validate as validate_formal_research_execution_data
from validate_renderer_spec import validate as validate_renderer_spec_data
from validate_replacement_dict import validate as validate_replacement_dict_data
from validate_run_artifacts import validate as validate_run_artifacts
from validate_stage_gate import validate_stage as validate_stage_gate_data
from validate_source_archive import validate as validate_source_archive_data
from validate_template_registry import validate as validate_template_registry_data
from validate_formal_search_plan import validate as validate_formal_search_plan_data
from qc_repair_targets import collect_repair_targets, unique_repair_targets
from validation_common import unique_preserve_order


REPO_ROOT = _IB_RUNTIME_ROOT
TEMPLATE_PROFILE_SCHEMA_VERSION = "template_profile_v1"
TEMPLATE_FIT_SCHEMA_VERSION = "template_fit_v1"
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
QC_WARNING_ACCEPTED_DISPOSITIONS = {"advisory_only", "qc_accept_with_limits"}
QC_WARNING_BLOCKING_DISPOSITIONS = {"unresolved", "repair_before_downstream"}
QC_WARNING_SCAN_SKIP = {
    "final_delivery_validation.json",
    "qc_repair_brief.json",
    "qc_router_report.json",
    "qc_warning_disposition.json",
}

RESEARCH_EVIDENCE_ERROR_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bformal\s+search\b", re.IGNORECASE),
    re.compile(r"\bsearch[\s_-]*plan\b", re.IGNORECASE),
    re.compile(r"\bsearch_log\b|\bsearch[\s_-]*log\b", re.IGNORECASE),
    re.compile(r"\bsearch\s+execution\s+accounting\b", re.IGNORECASE),
    re.compile(r"\bsearch\s+attempt[s]?\b", re.IGNORECASE),
    re.compile(r"\bresearch\s+pack\b", re.IGNORECASE),
    re.compile(r"\bresearch\s+evidence\b", re.IGNORECASE),
    re.compile(r"\bsource\s+classification\b", re.IGNORECASE),
    re.compile(r"\bsource\s+review[s]?\b", re.IGNORECASE),
    re.compile(r"\bresearch_evidence_db\b", re.IGNORECASE),
    re.compile(r"\bresearch_evidence\s+db\b", re.IGNORECASE),
    re.compile(r"\bindustry_research_pack\b", re.IGNORECASE),
    re.compile(r"\bformal_research\b", re.IGNORECASE),
    re.compile(r"\bMET-[0-9]+\b", re.IGNORECASE),
    re.compile(r"\bEV-[0-9]+\b", re.IGNORECASE),
)


def _looks_like_research_error(error_text: Any) -> bool:
    message = str(error_text).lower()
    return any(pattern.search(message) for pattern in RESEARCH_EVIDENCE_ERROR_PATTERNS)


def _evidence_readiness_payload(run_dir: Path) -> dict[str, Any]:
    db_path = run_dir / "artifacts" / "research_evidence_db.json"
    issue_analysis_path = run_dir / "industry_issue_analysis.json"
    accepted_statuses = {"llm_decided", "qc_confirmed"}
    accepted_owners = {"reasoning", "qc"}
    issue_payload = {}
    if issue_analysis_path.exists():
        try:
            issue_payload = load_json_file(issue_analysis_path)
        except Exception:
            issue_payload = {}
    issue_readiness = issue_payload.get("evidence_readiness")
    if isinstance(issue_readiness, dict):
        decision_status = str(issue_readiness.get("decision_status") or "needs_llm_decision")
        decision_owner = str(issue_readiness.get("decision_owner") or "reasoning")
        has_decision = decision_status in accepted_statuses and decision_owner in accepted_owners
        enough = bool(issue_readiness.get("enough_for_client_pitch", False)) if has_decision else False
        evidence_limited = bool(issue_readiness.get("evidence_limited_pitch_outline", True)) if has_decision else True
        research_first_required = bool(issue_readiness.get("research_first_required", True)) if has_decision else True
        critical_gap_count = int(issue_readiness.get("critical_gap_count", 0) or 0)
        evidence_row_count = int(issue_readiness.get("evidence_row_count", 0) or 0)
        metric_row_count = int(issue_readiness.get("metric_row_count", 0) or 0)
        return {
            "decision_status": decision_status,
            "decision_owner": decision_owner,
            "decision_missing": not has_decision,
            "decision_note": str(issue_readiness.get("decision_note") or ""),
            "enough_for_client_pitch": enough,
            "evidence_limited_pitch_outline": evidence_limited,
            "research_first_required": research_first_required,
            "critical_gap_count": critical_gap_count,
            "evidence_row_count": evidence_row_count,
            "metric_row_count": metric_row_count,
        }

    evidence_rows = 0
    metric_rows = 0
    if db_path.exists():
        try:
            db = load_json_file(db_path)
        except Exception:
            db = {}
        evidence_rows = len(db.get("evidence_ledger", [])) if isinstance(db, dict) else 0
        metric_rows = len(db.get("metric_reconciliation", [])) if isinstance(db, dict) else 0

    return {
        "decision_status": "needs_llm_decision",
        "decision_owner": "reasoning",
        "decision_missing": True,
        "decision_note": "No issue_analysis evidence_readiness decision found. Reasoning/QC must decide deliverable depth.",
        "enough_for_client_pitch": False,
        "evidence_limited_pitch_outline": True,
        "research_first_required": evidence_rows == 0 and metric_rows == 0,
        "critical_gap_count": 0,
        "evidence_row_count": int(evidence_rows),
        "metric_row_count": int(metric_rows),
    }


def _append_repair_targets(
    target_list: list[dict[str, Any]],
    report: dict[str, Any] | None,
    *,
    default_layer: str = "unknown",
    default_artifact: str = "",
) -> None:
    if target_list is None or report is None:
        return
    target_list.extend(
        collect_repair_targets(
            report,
            default_layer=default_layer,
            default_artifact=default_artifact,
        )
    )


def _append_validation_issue(
    target_list: list[dict[str, Any]],
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
            "recommended_action": recommended_action or f"Repair and rerun validation for {artifact}.",
            "forbidden_action": forbidden_action,
        },
        default_layer=layer,
        default_artifact=artifact,
    )


def _load_artifact_payload(
    artifact_path: Path,
    repair_targets: list[dict[str, Any]],
    errors: list[str],
    *,
    layer: str,
    artifact: str,
    missing_message: str,
    missing_recommended_action: str,
    missing_forbidden_action: str = "",
    read_recommended_action: str | None = None,
) -> dict[str, Any] | None:
    """Load an artifact JSON payload and normalize repair targets."""
    if not artifact_path.exists():
        errors.append(missing_message)
        _append_validation_issue(
            repair_targets,
            artifact=artifact,
            layer=layer,
            errors=[missing_message],
            recommended_action=missing_recommended_action,
            forbidden_action=missing_forbidden_action,
        )
        return None
    try:
        payload = load_json_file(artifact_path)
    except Exception as exc:
        message = f"cannot read {artifact}: {exc}"
        errors.append(message)
        _append_validation_issue(
            repair_targets,
            artifact=artifact,
            layer=layer,
            errors=[message],
            recommended_action=(
                read_recommended_action or f"Re-run validation for {artifact} and keep it valid."
            ),
        )
        return None
    _append_repair_targets(
        repair_targets,
        payload,
        default_layer=layer,
        default_artifact=artifact,
    )
    return payload


def _append_payload_validity_messages(
    payload: dict[str, Any],
    errors: list[str],
    warnings: list[str],
    *,
    artifact: str,
    failed_label: str,
    warning_key: str = "warnings",
) -> None:
    """Append generic validity and warning messages from a validation payload."""
    if payload.get("is_valid") is not True:
        errors.append(f"{artifact} {failed_label}")
    for item in payload.get(warning_key, []):
        warnings.append(str(item))


def _load_saved_validation_artifact(
    artifact_path: Path,
    repair_targets: list[dict[str, Any]],
    errors: list[str],
    *,
    layer: str,
    artifact: str,
    missing_recommended_action: str,
    read_recommended_action: str | None = None,
    check_warning_count: bool = False,
) -> dict[str, Any] | None:
    """Load a saved *_validation.json artifact and check its is_valid flag.

    Returns the loaded payload, or None if the artifact is missing/unreadable.
    Appends errors and repair targets as side effects.
    """
    if not artifact_path.exists():
        errors.append(f"missing {artifact}")
        _append_validation_issue(
            repair_targets,
            artifact=artifact,
            layer=layer,
            errors=[f"missing {artifact}"],
            recommended_action=missing_recommended_action,
        )
        return None
    try:
        payload = load_json_file(artifact_path)
    except Exception as exc:
        message = f"cannot read {artifact}: {exc}"
        errors.append(message)
        _append_validation_issue(
            repair_targets,
            artifact=artifact,
            layer=layer,
            errors=[message],
            recommended_action=read_recommended_action or f"Re-run validation for {artifact}.",
        )
        return None
    _append_repair_targets(
        repair_targets,
        payload,
        default_layer=layer,
        default_artifact=artifact,
    )
    if payload.get("is_valid") is False:
        errors.append(f"{artifact} is_valid=false")
    if check_warning_count and payload.get("warning_count", 0):
        errors.append(f"{artifact} contains {payload.get('warning_count')} warning(s)")
    return payload


def _validation_warning_artifacts(run_dir: Path) -> list[str]:
    """Return validation artifacts that currently contain warnings.

    This is intentionally broad and mechanical. QC owns deciding whether these
    warnings are advisory, repaired, or accepted with limits.
    """
    out: list[str] = []
    candidates: list[Path] = []
    artifacts = run_dir / "artifacts"
    if artifacts.exists():
        candidates.extend(sorted(artifacts.glob("*.json")))
    filled = run_dir / "filled_ppt_validation.json"
    if filled.exists():
        candidates.append(filled)
    for path in candidates:
        if path.name in QC_WARNING_SCAN_SKIP:
            continue
        if "validation" not in path.name and not path.name.endswith("_status.json"):
            continue
        try:
            payload = load_json_file(path)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        has_warnings = bool(payload.get("warnings")) or int(payload.get("warning_count") or 0) > 0
        if has_warnings:
            try:
                out.append(str(path.relative_to(run_dir)))
            except ValueError:
                out.append(str(path))
    return unique_preserve_order(out)


def _validate_qc_warning_disposition(
    run_dir: Path,
    current_warnings: list[str],
    repair_targets: list[dict[str, Any]],
) -> tuple[list[str], list[str], dict[str, Any]]:
    """Validate QC handling for advisory warnings before final delivery."""
    errors: list[str] = []
    warnings: list[str] = []
    warning_artifacts = _validation_warning_artifacts(run_dir)
    warnings_present = bool(current_warnings) or bool(warning_artifacts)
    disposition_path = run_dir / "artifacts" / "qc_warning_disposition.json"
    summary: dict[str, Any] = {
        "warnings_present": warnings_present,
        "warning_artifacts": warning_artifacts,
        "disposition_artifact": "artifacts/qc_warning_disposition.json",
        "disposition_present": disposition_path.exists(),
        "warning_count": 0,
        "unresolved_warning_count": 0,
        "accepted_with_limits_count": 0,
    }

    if not warnings_present:
        return errors, warnings, summary

    if not disposition_path.exists():
        message = (
            "validation warnings are present but artifacts/qc_warning_disposition.json is missing; "
            "run qc_router.py and let QC classify each warning before treating the run as client-ready"
        )
        warnings.append(message)
        _append_repair_targets(
            repair_targets,
            {
                "is_valid": True,
                "warnings": [message],
                "repair_targets": [
                    {
                        "severity": "warning",
                        "repair_target_layer": "qc",
                        "repair_target_artifact": "artifacts/qc_warning_disposition.json",
                        "message": message,
                        "why_it_matters": "Warnings need explicit routing or acceptance limits before downstream reliance.",
                        "repair_action": "Run qc_router.py, review qc_warning_disposition.json, and repair or accept warnings with limits.",
                        "rerun_command": f"$PYTHON_CMD scripts/qc/qc_router.py --run-dir {run_dir} --output {run_dir}/artifacts/qc_router_report.json",
                        "downstream_blocked": False,
                    }
                ],
            },
            default_layer="qc",
            default_artifact="artifacts/qc_warning_disposition.json",
        )
        return errors, warnings, summary

    try:
        payload = load_json_file(disposition_path)
    except Exception as exc:
        errors.append(f"cannot read artifacts/qc_warning_disposition.json: {exc}")
        return errors, warnings, summary

    if not isinstance(payload, dict):
        warnings.append("artifacts/qc_warning_disposition.json is not a JSON object; QC disposition could not be read")
        return errors, warnings, summary
    if payload.get("schema_version") != "qc_warning_disposition_v1":
        warnings.append("artifacts/qc_warning_disposition.json has invalid schema_version; treating it as advisory QC metadata")

    rows = payload.get("warnings", [])
    if not isinstance(rows, list):
        warnings.append("artifacts/qc_warning_disposition.json missing warnings list; QC should rewrite it, but final blocking depends on explicit unresolved/repair decisions")
        rows = []
    summary["warning_count"] = len(rows)
    for row in rows:
        if not isinstance(row, dict):
            continue
        disposition = str(row.get("disposition") or "unresolved")
        blocked = bool(row.get("downstream_blocked")) or bool(row.get("requires_qc_disposition"))
        if disposition in QC_WARNING_BLOCKING_DISPOSITIONS or blocked:
            errors.append(
                "unresolved QC warning disposition: "
                f"{row.get('warning_id', '')} {row.get('source_report', '')} {row.get('message', '')}"
            )
            summary["unresolved_warning_count"] = int(summary["unresolved_warning_count"]) + 1
        elif disposition == "qc_accept_with_limits":
            summary["accepted_with_limits_count"] = int(summary["accepted_with_limits_count"]) + 1
            if not str(row.get("downstream_limit") or "").strip():
                warnings.append(f"{row.get('warning_id', 'warning')} accepts with limits but downstream_limit is blank")
            if not str(row.get("acceptance_rationale") or "").strip():
                warnings.append(f"{row.get('warning_id', 'warning')} accepts with limits but acceptance_rationale is blank")
            if not str(row.get("accepted_by") or "").strip():
                warnings.append(f"{row.get('warning_id', 'warning')} accepts with limits but accepted_by is blank")
        elif disposition == "advisory_only":
            if not str(row.get("acceptance_rationale") or "").strip():
                warnings.append(f"{row.get('warning_id', 'warning')} marked advisory_only without acceptance_rationale")
        elif disposition not in QC_WARNING_ACCEPTED_DISPOSITIONS:
            errors.append(f"{row.get('warning_id', 'warning')} has unknown warning disposition: {disposition}")
    return errors, warnings, summary


def _run_validator_and_report(
    data: dict[str, Any],
    validator: Any,
    validator_args: tuple[Any, ...] | None,
    repair_targets: list[dict[str, Any]],
    errors: list[str],
    warnings: list[str],
    *,
    layer: str,
    artifact: str,
    fail_label: str,
    recommended_action: str,
    forbidden_action: str = "",
) -> None:
    """Run a domain validator, collect errors/warnings, and append repair targets."""
    args = validator_args or ()
    current_errors, current_warnings = validator(data, *args)
    _append_repair_targets(
        repair_targets,
        {
            "is_valid": not current_errors,
            "errors": current_errors,
            "repair_target_artifact": artifact,
            "repair_target_layer": layer,
            "repair_plan": {"targets": []},
        },
        default_layer=layer,
        default_artifact=artifact,
    )
    if current_errors:
        errors.append(fail_label)
        errors.extend(str(item) for item in current_errors)
        _append_validation_issue(
            repair_targets,
            artifact=artifact,
            layer=layer,
            errors=[str(item) for item in current_errors],
            recommended_action=recommended_action,
            forbidden_action=forbidden_action,
        )
    warnings.extend(str(item) for item in current_warnings)


def _template_layer_validation(
    run_dir: Path,
    repair_targets: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    template_profile_path = run_dir / "artifacts" / "template_profile.json"
    template_fit_path = run_dir / "artifacts" / "template_fit_validation.json"
    renderer_spec_path = run_dir / "renderer_spec.json"
    profile_exists = template_profile_path.exists()
    fit_exists = template_fit_path.exists()
    if not profile_exists:
        errors.append("missing artifacts/template_profile.json")
        _append_validation_issue(
            repair_targets,
            artifact="artifacts/template_profile.json",
            layer="generation",
            errors=["missing artifacts/template_profile.json"],
            recommended_action=(
                "Run template_analyzer.py to generate artifacts/template_profile.json "
                "before pre-PPT checks or final delivery."
            ),
            forbidden_action="Do not proceed to delivery while template profile is missing.",
        )
    else:
        try:
            profile_data = load_json_file(template_profile_path)
        except Exception as exc:
            errors.append(f"cannot read template_profile.json: {exc}")
            _append_validation_issue(
                repair_targets,
                artifact="artifacts/template_profile.json",
                layer="generation",
                errors=[f"cannot read template_profile.json: {exc}"],
                recommended_action=(
                    "Re-run template_analyzer.py and verify rendered artifacts/template_profile.json is a valid JSON object."
                ),
            )
            profile_data = None
        else:
            _append_repair_targets(
                repair_targets,
                profile_data,
                default_layer="generation",
                default_artifact="artifacts/template_profile.json",
            )
            if profile_data.get("schema_version") != TEMPLATE_PROFILE_SCHEMA_VERSION:
                errors.append(
                    f"template_profile.json schema_version is {profile_data.get('schema_version')}; expected {TEMPLATE_PROFILE_SCHEMA_VERSION}"
                )
            if not isinstance(profile_data.get("layout"), dict):
                errors.append("template_profile.json missing required object field: layout")
            if not isinstance(profile_data.get("visual_style"), dict):
                errors.append("template_profile.json missing required object field: visual_style")
            if not isinstance(profile_data.get("template_file"), str) or not profile_data.get("template_file").strip():
                errors.append("template_profile.json missing required string field: template_file")

    if not fit_exists:
        errors.append("missing artifacts/template_fit_validation.json")
        _append_validation_issue(
            repair_targets,
            artifact="artifacts/template_fit_validation.json",
            layer="generation",
            errors=["missing artifacts/template_fit_validation.json"],
            recommended_action=(
                "Run template_fit.py with renderer_spec.json and artifacts/template_profile.json "
                "before final delivery."
            ),
            forbidden_action="Do not finalize while template fit is not validated.",
        )
    else:
        try:
            fit_data = load_json_file(template_fit_path)
        except Exception as exc:
            errors.append(f"cannot read template_fit_validation.json: {exc}")
            _append_validation_issue(
                repair_targets,
                artifact="artifacts/template_fit_validation.json",
                layer="generation",
                errors=[f"cannot read template_fit_validation.json: {exc}"],
                recommended_action=(
                    "Re-run template_fit.py and repair the template_fit_validation.json payload."
                ),
            )
            fit_data = None
        else:
            _append_repair_targets(
                repair_targets,
                fit_data,
                default_layer="generation",
                default_artifact="artifacts/template_fit_validation.json",
            )
            if fit_data.get("schema_version") != TEMPLATE_FIT_SCHEMA_VERSION:
                errors.append(
                    f"template_fit_validation.json schema_version is {fit_data.get('schema_version')}; "
                    f"expected {TEMPLATE_FIT_SCHEMA_VERSION}"
                )
            if fit_data.get("is_valid") is not True:
                errors.append("template_fit_validation.json is_valid=false")
            if profile_exists and fit_exists and template_profile_path.stat().st_mtime > template_fit_path.stat().st_mtime + 1.0:
                errors.append("artifacts/template_fit_validation.json is older than artifacts/template_profile.json")
            if renderer_spec_path.exists() and renderer_spec_path.stat().st_mtime > template_fit_path.stat().st_mtime + 1.0:
                errors.append("artifacts/template_fit_validation.json is older than renderer_spec.json")
                warnings.append(
                    "rerun template_fit.py after regenerating renderer_spec.json"
                )

    return errors, warnings


def json_files_under(run_dir: Path) -> list[Path]:
    return sorted(path for path in run_dir.rglob("*.json") if "__pycache__" not in path.parts)


def validate_content_quality_artifact(
    path: Path,
    repair_targets: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    data = _load_artifact_payload(
        path,
        repair_targets,
        errors,
        layer="generation",
        artifact="artifacts/content_quality_validation.json",
        missing_message="missing content quality validation artifact",
        missing_recommended_action="Run validate_content_quality.py after generating renderer_spec.json.",
        missing_forbidden_action="Do not deliver until content quality blocker is cleared.",
        read_recommended_action="Re-run validate_content_quality.py with updated renderer_spec and research_pack paths.",
    )
    if data is None:
        return errors, warnings
    _append_payload_validity_messages(
        data,
        errors,
        warnings,
        artifact="content_quality_validation.json",
        failed_label="is_valid=false",
    )
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


# Mapping from stale validation artifact to the command that regenerates it.
# Commands use {run_dir} and {python} placeholders.
_STALE_RERUN_COMMANDS: dict[str, list[str]] = {
    "artifacts/deck_blueprint_validation.json": [
        "{python}", "scripts/qc/validators/generation/validate_deck_blueprint.py",
        "--deck-blueprint", "{run_dir}/deck_blueprint.json",
        "--issue-analysis", "{run_dir}/industry_issue_analysis.json",
        "--template-registry", "{run_dir}/template_registry.json",
        "--layout-budget", "configs/layout_budget.json",
        "--output", "{run_dir}/artifacts/deck_blueprint_validation.json",
    ],
    "artifacts/renderer_spec_validation.json": [
        "{python}", "scripts/qc/validators/generation/validate_renderer_spec.py",
        "--renderer-spec", "{run_dir}/renderer_spec.json",
        "--template-registry", "{run_dir}/template_registry.json",
        "--deck-blueprint", "{run_dir}/deck_blueprint.json",
        "--page-contract", "{run_dir}/page_evidence_contract.json",
        "--output", "{run_dir}/artifacts/renderer_spec_validation.json",
    ],
    "artifacts/page_evidence_contract_validation.json": [
        "{python}", "scripts/qc/validators/generation/validate_page_evidence_contract.py",
        "--page-contract", "{run_dir}/page_evidence_contract.json",
        "--deck-blueprint", "{run_dir}/deck_blueprint.json",
        "--issue-analysis", "{run_dir}/industry_issue_analysis.json",
        "--output", "{run_dir}/artifacts/page_evidence_contract_validation.json",
    ],
}


def _try_rerun_stale_validators(
    stale_artifacts: list[str],
    run_dir: Path,
    python_cmd: str,
    errors: list[str],
    warnings: list[str],
) -> None:
    """Attempt to rerun validators whose results are stale.

    If rerun succeeds, the stale artifact is refreshed and removed from the
    error list. If rerun fails, an error is added.
    """
    if not stale_artifacts:
        return

    for artifact_rel in stale_artifacts:
        cmd_template = _STALE_RERUN_COMMANDS.get(artifact_rel)
        if not cmd_template:
            errors.append(
                f"{artifact_rel} is stale and no auto-rerun command is defined; "
                "manually rerun the validator"
            )
            continue

        cmd = [
            part.replace("{run_dir}", str(run_dir)).replace("{python}", python_cmd)
            for part in cmd_template
        ]
        try:
            result = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                warnings.append(f"{artifact_rel} was stale; auto-reran validator successfully")
            else:
                stderr_tail = (result.stderr or "")[-200:]
                errors.append(
                    f"{artifact_rel} is stale and auto-rerun failed (exit {result.returncode}): {stderr_tail}"
                )
        except Exception as exc:
            errors.append(f"{artifact_rel} is stale and auto-rerun raised: {exc}")


def validate_artifact_provenance(run_dir: Path) -> tuple[list[str], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    stale_artifacts: list[str] = []
    checks = {
        "artifacts/input_card_validation.json": ["input_card"],
        "artifacts/industry_scope_pack_validation.json": ["scope_pack"],
        "artifacts/formal_search_plan_validation.json": ["formal_search_plan"],
        "artifacts/template_profile.json": ["template_profile"],
        "artifacts/template_fit_validation.json": ["template_profile", "renderer_spec"],
        "artifacts/content_quality_validation.json": ["renderer_spec", "research_pack"],
        "artifacts/renderer_spec_validation.json": ["renderer_spec", "template_registry", "deck_blueprint", "page_contract"],
        "artifacts/research_pack_validation.json": ["research_pack", "run_dir"],
        "artifacts/research_evidence_db_validation.json": ["research_evidence_db"],
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
        "artifacts/template_profile.json": [],
        "artifacts/template_fit_validation.json": [
            run_dir / "artifacts" / "template_profile.json",
            run_dir / "renderer_spec.json",
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
            run_dir / "artifacts" / "research_evidence_db.json",
            run_dir / "industry_research_pack.md",
        ],
        "artifacts/research_evidence_db_validation.json": [
            run_dir / "artifacts" / "research_evidence_db.json",
        ],
        "artifacts/source_archive_validation.json": [
            run_dir / "artifacts" / "source_archive" / "source_archive_index.json",
            run_dir / "artifacts" / "search_log.md",
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
            run_dir / "artifacts" / "source_archive" / "source_archive_index.json",
            run_dir / "artifacts" / "source_archive_validation.json",
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
            REPO_ROOT / "configs/ppt_mapping.json",
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
            stale_artifacts.append(rel)
            warnings.append(f"{rel} is older than source file(s): {', '.join(newer_sources)}; will attempt auto-rerun")
    return errors, warnings, stale_artifacts


def validate_formal_research_execution_artifact(
    run_dir: Path,
    repair_targets: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    plan_path = run_dir / "artifacts/formal_search_plan.json"
    report_path = run_dir / "artifacts/formal_research_execution_report.json"
    artifact_path = run_dir / "artifacts/formal_research_execution_validation.json"
    search_log_path = run_dir / "artifacts/search_log.md"
    if not plan_path.exists():
        errors.append("missing formal_search_plan.json")
        _append_validation_issue(
            repair_targets,
            artifact="artifacts/formal_search_plan.json",
            layer="research",
            errors=["missing formal_search_plan.json"],
            recommended_action="Build formal_search_plan.json before rerunning formal execution validation.",
        )
    if not report_path.exists():
        errors.append("missing formal_research_execution_report.json")
        _append_validation_issue(
            repair_targets,
            artifact="artifacts/formal_research_execution_report.json",
            layer="research",
            errors=["missing formal_research_execution_report.json"],
            recommended_action="Regenerate formal_research_execution_report.json from search log and plan.",
        )
    if not search_log_path.exists():
        errors.append("missing search_log.md")
        _append_validation_issue(
            repair_targets,
            artifact="artifacts/search_log.md",
            layer="research",
            errors=["missing search_log.md"],
            recommended_action="Run or append search log before rerunning formal execution checks.",
        )
    if errors:
        return errors, warnings

    try:
        plan_data = load_json_file(plan_path)
        report_data = load_json_file(report_path)
    except Exception as exc:
        errors.append(f"cannot load formal research artifacts: {exc}")
        _append_validation_issue(
            repair_targets,
            artifact="artifacts/formal_research_execution_report.json",
            layer="research",
            errors=[f"cannot load formal research artifacts: {exc}"],
            recommended_action="Repair missing or unreadable formal execution artifacts.",
        )
        return errors, warnings

    current_errors, current_warnings = validate_formal_research_execution_data(report_data, plan_data, search_log_path)
    _append_repair_targets(
        repair_targets,
        {
            "is_valid": not current_errors,
            "errors": current_errors,
            "repair_target_artifact": "artifacts/formal_research_execution_report.json",
            "repair_target_layer": "research",
            "repair_plan": {"targets": []},
        },
        default_layer="research",
        default_artifact="artifacts/formal_research_execution_report.json",
    )
    if current_errors:
        errors.append("current formal research execution validation failed")
        errors.extend(str(item) for item in current_errors)
        _append_validation_issue(
            repair_targets,
            artifact="artifacts/formal_research_execution_report.json",
            layer="research",
            errors=[str(item) for item in current_errors],
            recommended_action="Repair formal research execution plan/report consistency and rerun validator.",
        )
    warnings.extend(str(item) for item in current_warnings)

    saved = _load_saved_validation_artifact(
        artifact_path,
        repair_targets,
        errors,
        layer="research",
        artifact="artifacts/formal_research_execution_validation.json",
        missing_recommended_action="Run validate_formal_research_execution.py and write validation artifact.",
        read_recommended_action="Re-run validator after fixing formal research execution report artifacts.",
    )
    if saved is not None and saved.get("warning_count", 0):
        warnings.append(f"formal_research_execution_validation.json contains {saved.get('warning_count')} warning(s)")

    return errors, warnings


def validate_formal_search_plan_artifact(
    run_dir: Path,
    repair_targets: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    plan_path = run_dir / "artifacts/formal_search_plan.json"
    artifact_path = run_dir / "artifacts/formal_search_plan_validation.json"
    plan_data = _load_artifact_payload(
        plan_path,
        repair_targets,
        errors,
        layer="research",
        artifact="artifacts/formal_search_plan.json",
        missing_message="missing formal_search_plan.json",
        missing_recommended_action="Create or repair formal_search_plan.json with scoped search rows.",
        read_recommended_action="Rebuild formal_search_plan.json and rerun this validator.",
    )
    if plan_data is None:
        return errors, warnings

    _run_validator_and_report(
        plan_data,
        validate_formal_search_plan_data,
        None,
        repair_targets,
        errors,
        warnings,
        layer="research",
        artifact="artifacts/formal_search_plan.json",
        fail_label="current formal search plan validation failed",
        recommended_action="Fix execution expectation and taxonomy in formal_search_plan.json.",
        forbidden_action="Do not map FS rows to source rows without executed attempts.",
    )

    _load_saved_validation_artifact(
        artifact_path,
        repair_targets,
        errors,
        layer="research",
        artifact="artifacts/formal_search_plan_validation.json",
        missing_recommended_action="Run validate_formal_search_plan.py and persist output.",
        read_recommended_action="Re-run formal_search_plan validator.",
    )
    return errors, warnings


def validate_industry_scope_pack_artifact(
    run_dir: Path,
    repair_targets: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    scope_path = run_dir / "artifacts/industry_scope_pack.json"
    artifact_path = run_dir / "artifacts/industry_scope_pack_validation.json"
    scope_data = _load_artifact_payload(
        scope_path,
        repair_targets,
        errors,
        layer="industry",
        artifact="artifacts/industry_scope_pack.json",
        missing_message="missing industry_scope_pack.json",
        missing_recommended_action="Repair industry_scope_pack.json before final delivery check.",
        missing_forbidden_action="Do not run final delivery while scope is missing.",
        read_recommended_action="Rebuild industry_scope_pack.json and rerun validator.",
    )
    if scope_data is None:
        return errors, warnings

    _run_validator_and_report(
        scope_data,
        validate_industry_scope_pack_data,
        None,
        repair_targets,
        errors,
        warnings,
        layer="industry",
        artifact="artifacts/industry_scope_pack.json",
        fail_label="current industry scope pack validation failed",
        recommended_action="Repair boundary definitions and exclusions in industry scope pack.",
    )

    _load_saved_validation_artifact(
        artifact_path,
        repair_targets,
        errors,
        layer="industry",
        artifact="artifacts/industry_scope_pack_validation.json",
        missing_recommended_action="Run industry scope validator and save artifact.",
        read_recommended_action="Re-run industry scope pack validator.",
    )
    return errors, warnings


def validate_current_content_quality(
    run_dir: Path,
    rules_path: Path,
    repair_targets: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    renderer_spec_path = run_dir / "renderer_spec.json"
    memo_path = run_dir / "industry_research_pack.md"
    if not renderer_spec_path.exists():
        message = "cannot recompute content quality: missing renderer_spec.json"
        errors.append(message)
        _append_validation_issue(
            repair_targets,
            artifact="renderer_spec.json",
            layer="generation",
            errors=[message],
            recommended_action="Generate renderer_spec.json before current content-quality pass.",
        )
        return errors, warnings

    result = validate_content_quality(
        renderer_spec_path,
        memo_path if memo_path.exists() else None,
        rules_path,
        text_fit_rules_path=REPO_ROOT / "configs/text_fit_rules.json",
        layout_budget_path=REPO_ROOT / "configs/layout_budget.json",
    )
    _append_repair_targets(
        repair_targets,
        result,
        default_layer="generation",
        default_artifact="renderer_spec.json",
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


def validate_issue_artifacts(
    run_dir: Path,
    repair_targets: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
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
        for artifact_name in required_files:
            _append_validation_issue(
                repair_targets,
                artifact=artifact_name,
                layer="reasoning",
                errors=[f"missing required issue analysis artifact: {artifact_name}"],
                recommended_action="Run issue analysis and related upstream validators before final delivery.",
                forbidden_action="Do not proceed to deck compile/final delivery while core reasoning artifacts are missing.",
            )
        return errors, warnings

    try:
        issue_analysis = load_json_file(issue_analysis_path)
        template_registry = load_json_file(template_registry_path)
        deck_blueprint = load_json_file(deck_blueprint_path)
        page_contract = load_json_file(page_contract_path)
    except Exception as exc:
        errors.append(f"cannot load issue analysis artifacts: {exc}")
        _append_validation_issue(
            repair_targets,
            artifact="industry_issue_analysis.json",
            layer="reasoning",
            errors=[f"cannot load issue analysis artifacts: {exc}"],
            recommended_action="Repair issue analysis and dependent artifacts, then rerun validators.",
            forbidden_action="Do not finalize without valid issue-analysis core artifacts.",
        )
        return errors, warnings

    issue_errors, issue_warnings = validate_issue_analysis_data(
        issue_analysis,
        memo_path if memo_path.exists() else None,
    )
    _append_repair_targets(
        repair_targets,
        {
            "is_valid": not issue_errors,
            "errors": issue_errors,
            "repair_target_layer": "reasoning",
            "repair_target_artifact": "industry_issue_analysis.json",
        },
        default_layer="reasoning",
        default_artifact="industry_issue_analysis.json",
    )
    if issue_errors:
        errors.append("current issue analysis validation failed")
        errors.extend(str(item) for item in issue_errors)
        _append_validation_issue(
            repair_targets,
            artifact="industry_issue_analysis.json",
            layer="reasoning",
            errors=[str(item) for item in issue_errors],
            recommended_action="Fix unsupported or unsupported claims in issue analysis then rerun validate_issue_analysis.py.",
            forbidden_action="Do not edit deck blueprint before issue analysis is valid.",
        )
    warnings.extend(str(item) for item in issue_warnings)

    template_registry_errors, template_registry_warnings = validate_template_registry_data(template_registry)
    _append_repair_targets(
        repair_targets,
        {
            "is_valid": not template_registry_errors,
            "errors": template_registry_errors,
            "repair_target_layer": "generation",
            "repair_target_artifact": "template_registry.json",
            "repair_plan": {"targets": []},
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
            recommended_action="Fix template registry and rerun validate_template_registry.py.",
            forbidden_action="Do not generate deck artifacts while template registry remains invalid.",
        )
    warnings.extend(str(item) for item in template_registry_warnings)

    deck_errors, deck_warnings, _ = validate_deck_blueprint_data(deck_blueprint, issue_analysis, template_registry)
    _append_repair_targets(
        repair_targets,
        {
            "is_valid": not deck_errors,
            "errors": deck_errors,
            "repair_target_layer": "generation",
            "repair_target_artifact": "deck_blueprint.json",
            "repair_plan": {"targets": []},
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
            recommended_action="Repair deck blueprint schema/logic and rerun validate_deck_blueprint.py.",
            forbidden_action="Do not compile renderer spec until deck blueprint passes.",
        )
    warnings.extend(str(item) for item in deck_warnings)

    page_contract_errors, page_contract_warnings = validate_page_evidence_contract_data(
        issue_analysis,
        normalize_deck_blueprint_for_page_plan(deck_blueprint),
        page_contract,
    )
    _append_repair_targets(
        repair_targets,
        {
            "is_valid": not page_contract_errors,
            "errors": page_contract_errors,
            "repair_target_layer": "generation",
            "repair_target_artifact": "page_evidence_contract.json",
        },
        default_layer="generation",
        default_artifact="page_evidence_contract.json",
    )
    if page_contract_errors:
        errors.append("current page evidence contract validation failed")
        errors.extend(str(item) for item in page_contract_errors)
        _append_validation_issue(
            repair_targets,
            artifact="page_evidence_contract.json",
            layer="generation",
            errors=[str(item) for item in page_contract_errors],
            recommended_action="Repair page evidence contract against deck blueprint and rerun validation.",
            forbidden_action="Do not finalize renderer spec before page evidence contract passes.",
        )
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
            _append_validation_issue(
                repair_targets,
                artifact=f"artifacts/{artifact_name}",
                layer="generation",
                errors=[f"missing {artifact_name}"],
                recommended_action="Run the corresponding validator and save the validation artifact.",
            )
            continue
        try:
            artifact = load_json_file(artifact_path)
        except Exception as exc:
            errors.append(f"cannot read {artifact_name}: {exc}")
            _append_validation_issue(
                repair_targets,
                artifact=f"artifacts/{artifact_name}",
                layer="generation",
                errors=[f"cannot read {artifact_name}: {exc}"],
                recommended_action="Re-run the corresponding validator and fix malformed artifact.",
            )
            continue
        _append_repair_targets(
            repair_targets,
            artifact,
            default_layer="generation",
            default_artifact=f"artifacts/{artifact_name}",
        )
        if artifact.get("is_valid") is False:
            errors.append(f"{artifact_name} is_valid=false")

    return errors, warnings


def validate_renderer_spec_artifact(
    run_dir: Path,
    repair_targets: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    renderer_spec_path = run_dir / "renderer_spec.json"
    template_registry_path = run_dir / "template_registry.json"
    deck_blueprint_path = run_dir / "deck_blueprint.json"
    page_contract_path = run_dir / "page_evidence_contract.json"
    errors: list[str] = []
    warnings: list[str] = []
    if not renderer_spec_path.exists():
        _append_validation_issue(
            repair_targets,
            artifact="renderer_spec.json",
            layer="generation",
            errors=["missing renderer_spec.json"],
            recommended_action="Compile deck blueprint to produce renderer_spec.json.",
            forbidden_action="Do not proceed to replacement dict or PPT generation until renderer spec exists.",
        )
        return ["missing renderer_spec.json"], []
    if not template_registry_path.exists():
        _append_validation_issue(
            repair_targets,
            artifact="template_registry.json",
            layer="generation",
            errors=["missing template_registry.json"],
            recommended_action="Extract template registry before renderer spec validation.",
        )
        errors.append("missing template_registry.json")
    if not deck_blueprint_path.exists():
        _append_validation_issue(
            repair_targets,
            artifact="deck_blueprint.json",
            layer="generation",
            errors=["missing deck_blueprint.json"],
            recommended_action="Validate issue analysis and regenerate deck blueprint.",
        )
        errors.append("missing deck_blueprint.json")
    if not page_contract_path.exists():
        _append_validation_issue(
            repair_targets,
            artifact="page_evidence_contract.json",
            layer="generation",
            errors=["missing page_evidence_contract.json"],
            recommended_action="Compile deck blueprint to regenerate page evidence contract.",
        )
        errors.append("missing page_evidence_contract.json")
    if errors:
        return errors, warnings

    try:
        result_errors, result_warnings = validate_renderer_spec_data(
            load_json_file(renderer_spec_path),
            load_json_file(template_registry_path),
            normalize_deck_blueprint_for_page_plan(load_json_file(deck_blueprint_path)),
            load_json_file(page_contract_path),
        )
    except Exception as exc:
        _append_validation_issue(
            repair_targets,
            artifact="renderer_spec.json",
            layer="generation",
            errors=[f"current renderer spec validation failed: {exc}"],
            recommended_action="Repair schema or field mapping mismatch and rerun compile_deck_blueprint.py.",
            forbidden_action="Do not patch renderer_spec.json manually.",
        )
        return [f"current renderer spec validation failed: {exc}"], warnings

    _append_repair_targets(
        repair_targets,
        {
            "is_valid": not result_errors,
            "errors": result_errors,
            "repair_target_layer": "generation",
            "repair_target_artifact": "renderer_spec.json",
        },
        default_layer="generation",
        default_artifact="renderer_spec.json",
    )
    if result_errors:
        errors.append("current renderer spec validation failed")
        errors.extend(str(item) for item in result_errors)
        _append_validation_issue(
            repair_targets,
            artifact="renderer_spec.json",
            layer="generation",
            errors=[str(item) for item in result_errors],
            recommended_action="Fix template-bound field mapping and rerun compile_deck_blueprint.py.",
        )
    warnings.extend(str(item) for item in result_warnings)
    return errors, warnings


def validate_replacement_dict_artifact(
    run_dir: Path,
    repair_targets: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    replacement_path = run_dir / "replacement_dict.json"
    renderer_spec_path = run_dir / "renderer_spec.json"
    ppt_mapping_path = REPO_ROOT / "configs/ppt_mapping.json"
    artifact_path = run_dir / "artifacts/replacement_dict_validation.json"
    errors: list[str] = []
    warnings: list[str] = []
    if not replacement_path.exists():
        errors.append("missing replacement_dict.json")
        _append_validation_issue(
            repair_targets,
            artifact="replacement_dict.json",
            layer="generation",
            errors=["missing replacement_dict.json"],
            recommended_action="Regenerate replacement_dict.json from successful pipeline render.",
            forbidden_action="Do not generate final PPT without replacement_dict.json.",
        )
        return errors, warnings

    saved = _load_saved_validation_artifact(
        artifact_path,
        repair_targets,
        errors,
        layer="generation",
        artifact="artifacts/replacement_dict_validation.json",
        missing_recommended_action="Run validate_replacement_dict.py and persist artifact.",
        read_recommended_action="Re-run replacement-dict validation after path normalization.",
    )
    if saved is not None:
        warnings.extend(str(item) for item in saved.get("warnings", []))

    if not renderer_spec_path.exists():
        errors.append("missing renderer_spec.json")
        _append_validation_issue(
            repair_targets,
            artifact="renderer_spec.json",
            layer="generation",
            errors=["missing renderer_spec.json"],
            recommended_action="Compile renderer spec before validating replacement mapping.",
        )
        return errors, warnings
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
        _append_validation_issue(
            repair_targets,
            artifact="replacement_dict.json",
            layer="generation",
            errors=[f"current replacement dict validation failed: {exc}"],
            recommended_action="Fix replacement_dict schema or ensure renderer_spec keys align.",
        )
        return errors, warnings
    _append_repair_targets(
        repair_targets,
        {
            "is_valid": not result_errors,
            "errors": result_errors,
            "repair_target_layer": "generation",
            "repair_target_artifact": "replacement_dict.json",
        },
        default_layer="generation",
        default_artifact="replacement_dict.json",
    )
    if result_errors:
        errors.append("current replacement dict validation failed")
        errors.extend(str(item) for item in result_errors)
        _append_validation_issue(
            repair_targets,
            artifact="replacement_dict.json",
            layer="generation",
            errors=[str(item) for item in result_errors],
            recommended_action="Regenerate replacement_dict after fixing renderer spec content and mapping.",
        )
    warnings.extend(str(item) for item in result_warnings)
    return errors, warnings


def validate_research_pack_artifact(
    run_dir: Path,
    repair_targets: list[dict[str, Any]],
    source_registry: Optional[Path] = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    db_path = run_dir / "artifacts/research_evidence_db.json"
    db_validation_path = run_dir / "artifacts/research_evidence_db_validation.json"
    if not db_path.exists():
        errors.append("missing artifacts/research_evidence_db.json")
        _append_validation_issue(
            repair_targets,
            artifact="artifacts/research_evidence_db.json",
            layer="knowledge",
            errors=["missing artifacts/research_evidence_db.json"],
            recommended_action="Build research evidence db from reviewed research attempts.",
        )
    else:
        try:
            db_errors, db_warnings, _ = validate_research_evidence_db_data(load_json_file(db_path))
        except Exception as exc:
            errors.append(f"cannot validate research_evidence_db.json: {exc}")
            _append_validation_issue(
                repair_targets,
                artifact="artifacts/research_evidence_db.json",
                layer="knowledge",
                errors=[f"cannot validate research_evidence_db.json: {exc}"],
                recommended_action="Repair malformed research evidence DB and rerun validation.",
            )
        else:
            _append_repair_targets(
                repair_targets,
                {
                    "is_valid": not db_errors,
                    "errors": db_errors,
                    "repair_target_layer": "knowledge",
                    "repair_target_artifact": "artifacts/research_evidence_db.json",
                },
                default_layer="knowledge",
                default_artifact="artifacts/research_evidence_db.json",
            )
            if db_errors:
                errors.append("current research evidence db validation failed")
                errors.extend(str(item) for item in db_errors)
                _append_validation_issue(
                    repair_targets,
                    artifact="artifacts/research_evidence_db.json",
                    layer="knowledge",
                    errors=[str(item) for item in db_errors],
                    recommended_action="Repair DB rows to include full evidence and metric context.",
                    forbidden_action="Do not promote unreviewed evidence into research pack or later layers.",
                )
            warnings.extend(str(item) for item in db_warnings)
    if db_validation_path.exists():
        try:
            db_artifact = load_json_file(db_validation_path)
        except Exception as exc:
            errors.append(f"cannot read research_evidence_db_validation.json: {exc}")
            _append_validation_issue(
                repair_targets,
                artifact="artifacts/research_evidence_db_validation.json",
                layer="knowledge",
                errors=[f"cannot read research_evidence_db_validation.json: {exc}"],
                recommended_action="Re-run research evidence DB validation.",
            )
        else:
            _append_repair_targets(
                repair_targets,
                db_artifact,
                default_layer="knowledge",
                default_artifact="artifacts/research_evidence_db_validation.json",
            )
            if db_artifact.get("is_valid") is False:
                errors.append("research_evidence_db_validation.json is_valid=false")
                _append_validation_issue(
                    repair_targets,
                    artifact="artifacts/research_evidence_db_validation.json",
                    layer="knowledge",
                    errors=["research_evidence_db_validation.json is_valid=false"],
                    recommended_action="Fix research evidence DB and rerun validation before final delivery.",
                )
    else:
        errors.append("missing research_evidence_db_validation.json")
        _append_validation_issue(
            repair_targets,
            artifact="artifacts/research_evidence_db_validation.json",
            layer="knowledge",
            errors=["missing research_evidence_db_validation.json"],
            recommended_action="Run validate_research_evidence_db.py and persist output.",
        )

    memo_path = run_dir / "industry_research_pack.md"
    if not memo_path.exists():
        return ["missing industry_research_pack.md"], warnings
    try:
        result = validate_research_pack_data(
            memo_path,
            run_dir,
            source_registry_path=source_registry,
        )
    except Exception as exc:
        errors.append(f"current research pack validation failed: {exc}")
        _append_validation_issue(
            repair_targets,
            artifact="industry_research_pack.md",
            layer="knowledge",
            errors=[f"current research pack validation failed: {exc}"],
            recommended_action="Fix research pack format and rerun validate_research_pack.py.",
        )
        return errors, warnings
    _append_repair_targets(
        repair_targets,
        result,
        default_layer="knowledge",
        default_artifact="industry_research_pack.md",
    )
    if result.get("is_valid") is False:
        errors.append("current research pack validation failed")
        errors.extend(str(item) for item in result.get("errors", []))
        _append_validation_issue(
            repair_targets,
            artifact="industry_research_pack.md",
            layer="knowledge",
            errors=[str(item) for item in result.get("errors", [])],
            recommended_action="Repair evidence ledger gaps and rerun research pack validation.",
            forbidden_action="Do not run issue analysis with unresolved critical research-pack gaps.",
        )
    warnings.extend(str(item) for item in result.get("warnings", []))

    artifact_path = run_dir / "artifacts/research_pack_validation.json"
    if artifact_path.exists():
        try:
            artifact = load_json_file(artifact_path)
        except Exception as exc:
            errors.append(f"cannot read research_pack_validation.json: {exc}")
            _append_validation_issue(
                repair_targets,
                artifact="artifacts/research_pack_validation.json",
                layer="knowledge",
                errors=[f"cannot read research_pack_validation.json: {exc}"],
                recommended_action="Re-run validate_research_pack.py.",
            )
        else:
            _append_repair_targets(
                repair_targets,
                artifact,
                default_layer="knowledge",
                default_artifact="artifacts/research_pack_validation.json",
            )
            if artifact.get("is_valid") is False:
                errors.append("research_pack_validation.json is_valid=false")
                _append_validation_issue(
                    repair_targets,
                    artifact="artifacts/research_pack_validation.json",
                    layer="knowledge",
                    errors=["research_pack_validation.json is_valid=false"],
                    recommended_action="Fix research_pack.md content and rerun validator.",
                )
    else:
        errors.append("missing research_pack_validation.json")
        _append_validation_issue(
            repair_targets,
            artifact="artifacts/research_pack_validation.json",
            layer="knowledge",
            errors=["missing research_pack_validation.json"],
            recommended_action="Run validate_research_pack.py and persist output.",
        )
    return errors, warnings


def validate_source_archive_artifact(
    run_dir: Path,
    repair_targets: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    source_archive_index_path = run_dir / "artifacts/source_archive/source_archive_index.json"
    result = validate_source_archive_data(
        source_archive_index_path=source_archive_index_path,
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
            recommended_action="Repair archived source rows from search_log/manual sources and rerun source archive validation.",
            forbidden_action="Do not extract evidence from unarchived planned searches.",
        )
    warnings.extend(str(item) for item in result.get("warnings", []))

    archive_saved = _load_saved_validation_artifact(
        run_dir / "artifacts/source_archive_validation.json",
        repair_targets,
        errors,
        layer="knowledge",
        artifact="artifacts/source_archive_validation.json",
        missing_recommended_action="Generate and validate source archive index before final delivery.",
        read_recommended_action="Run source archive validator after fixing source archive index.",
    )
    if archive_saved is not None and archive_saved.get("is_valid") is False:
        _append_validation_issue(
            repair_targets,
            artifact="artifacts/source_archive_validation.json",
            layer="knowledge",
            errors=["source_archive_validation.json is_valid=false"],
            recommended_action="Fix source_archive index and rerun source archive validation.",
        )
    return errors, warnings


def validate(run_dir: Path, source_registry: Optional[Path] = None, python_cmd: str = sys.executable) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    technical_delivery_valid = True
    research_evidence_valid = True
    repair_targets: list[dict[str, Any]] = []

    if (run_dir / "DEBUG_OUTPUT_ONLY.txt").exists():
        errors.append(
            "run is marked DEBUG_OUTPUT_ONLY; debug/ungated PPTs must not be validated or delivered as final"
        )
        technical_delivery_valid = False
    if (run_dir / "DRAFT_NOT_CLIENT_READY.txt").exists():
        errors.append(
            "run is marked DRAFT_NOT_CLIENT_READY; evidence-limited draft PPTs must not be delivered as final"
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
            if run_flags.get("draft_output_only") is True:
                errors.append("run_flags.json marks this as draft_output_only; draft runs cannot be final")
            if run_flags.get("preflight_skipped") is True:
                errors.append("run_flags.json indicates --skip-preflight was used; degraded pipeline runs cannot be client-ready")

    artifact_result = validate_run_artifacts(run_dir, require_research=True)
    errors.extend(artifact_result["errors"])
    warnings.extend(artifact_result["warnings"])

    provenance_errors, provenance_warnings, stale_artifacts = validate_artifact_provenance(run_dir)
    # Attempt to auto-rerun stale validators before treating them as errors
    if stale_artifacts:
        _try_rerun_stale_validators(stale_artifacts, run_dir, python_cmd, provenance_errors, provenance_warnings)
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
        run_dir / "artifacts/content_quality_validation.json",
        repair_targets,
    )
    errors.extend(content_errors)
    warnings.extend(content_warnings)

    scope_errors, scope_warnings = validate_industry_scope_pack_artifact(
        run_dir,
        repair_targets,
    )
    errors.extend(scope_errors)
    warnings.extend(scope_warnings)

    plan_errors, plan_warnings = validate_formal_search_plan_artifact(
        run_dir,
        repair_targets,
    )
    errors.extend(plan_errors)
    warnings.extend(plan_warnings)

    research_errors, research_warnings = validate_formal_research_execution_artifact(
        run_dir,
        repair_targets,
    )
    errors.extend(research_errors)
    warnings.extend(research_warnings)

    source_review_errors, source_review_warnings = validate_source_archive_artifact(
        run_dir,
        repair_targets,
    )
    errors.extend(source_review_errors)
    warnings.extend(source_review_warnings)

    memo_errors, memo_warnings = validate_research_pack_artifact(
        run_dir,
        repair_targets,
        source_registry=source_registry,
    )
    errors.extend(memo_errors)
    warnings.extend(memo_warnings)

    template_profile_errors, template_profile_warnings = _template_layer_validation(
        run_dir,
        repair_targets,
    )
    errors.extend(template_profile_errors)
    warnings.extend(template_profile_warnings)

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

    issue_errors, issue_warnings = validate_issue_artifacts(run_dir, repair_targets)
    errors.extend(issue_errors)
    warnings.extend(issue_warnings)

    renderer_spec_errors, renderer_spec_warnings = validate_renderer_spec_artifact(
        run_dir,
        repair_targets,
    )
    errors.extend(renderer_spec_errors)
    warnings.extend(renderer_spec_warnings)

    replacement_errors, replacement_warnings = validate_replacement_dict_artifact(
        run_dir,
        repair_targets,
    )
    errors.extend(replacement_errors)
    warnings.extend(replacement_warnings)

    current_content_errors, current_content_warnings = validate_current_content_quality(
        run_dir,
        REPO_ROOT / "configs/content_quality_rules.json",
        repair_targets,
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
        "ppt_mapping_path": REPO_ROOT / "configs/ppt_mapping.json",
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

    research_evidence_valid = not any(_looks_like_research_error(error) for error in errors)
    evidence_readiness = _evidence_readiness_payload(run_dir)
    if evidence_readiness.get("decision_missing"):
        errors.append(
            "missing Reasoning/QC evidence readiness decision: industry_issue_analysis.json "
            "must set evidence_readiness.decision_status to llm_decided or qc_confirmed before final delivery"
        )
        research_evidence_valid = False
    warning_disposition_errors, warning_disposition_warnings, warning_disposition = _validate_qc_warning_disposition(
        run_dir,
        warnings,
        repair_targets,
    )
    errors.extend(warning_disposition_errors)
    warnings.extend(warning_disposition_warnings)
    content_ready_threshold = bool(evidence_readiness.get("enough_for_client_pitch", False))
    errors = unique_preserve_order(errors)
    warnings = unique_preserve_order(warnings)
    technical_client_ready = bool(technical_delivery_valid and not errors)
    content_client_ready = bool(technical_client_ready and research_evidence_valid and content_ready_threshold)
    client_ready = technical_client_ready and content_client_ready

    return {
        "is_valid": not errors,
        "technical_delivery_valid": technical_delivery_valid,
        "research_evidence_valid": research_evidence_valid,
        "technical_client_ready": technical_client_ready,
        "content_client_ready": content_client_ready,
        "delivery_mode": "evidence_limited_outline" if not content_client_ready else "full_pitchbook",
        "client_ready": client_ready,
        "evidence_readiness": evidence_readiness,
        "warning_disposition": warning_disposition,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "run_dir": str(run_dir),
        "source_registry": str(source_registry) if source_registry else "",
        "repair_targets": unique_repair_targets(repair_targets),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the final delivery gate for an industry section output.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--source-registry", default="configs/source_registry.json")
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
