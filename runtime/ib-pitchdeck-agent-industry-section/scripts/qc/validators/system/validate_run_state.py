#!/usr/bin/env python3
"""Read-only state inspector for an IB industry-section run directory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
_RUNTIME_ROOT = next(
    parent for parent in [SCRIPT_DIR, *SCRIPT_DIR.parents]
    if (parent / "configs").is_dir() and (parent / "scripts").is_dir()
)
_SHARED_SCRIPT_DIR = _RUNTIME_ROOT / "scripts" / "_lib"
if str(_SHARED_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SHARED_SCRIPT_DIR))

from gate_retry_state import load_state as load_gate_retry_state
from gate_names import (
    CONTENT_QUALITY,
    CHART_METRIC_BINDING,
    FILLED_PPT,
    FINAL_DELIVERY,
    BOUNDARY_LOOP,
    INDUSTRY_BOUNDARY_QC,
    EXECUTABLE_SEARCH_BATCH,
    FORMAL_SEARCH_PLAN,
    INDUSTRY_SCOPE_PACK,
    INPUT_CARD,
    ISSUE_ANALYSIS,
    HYPOTHESIS_STORE,
    PAGE_ARGUMENT_PACK,
    RESEARCH_PACK,
    DECK_BLUEPRINT,
    PAGE_EVIDENCE_CONTRACT,
    PRE_RESEARCH_PACK,
    RESEARCH_EVIDENCE_DB,
    PRE_PPT,
    RENDERER_SPEC,
    REPLACEMENT_DICT,
    SOURCE_ARCHIVE,
    FORMAL_RESEARCH_EXECUTION,
    TEMPLATE_REGISTRY,
    TEMPLATE_PROFILE,
    TEMPLATE_FIT_VALIDATION,
)
from runtime_paths import find_runtime_root


DOWNSTREAM_ACTIONS = [
    "write_research_pack",
    "generate_issue_analysis",
    "extract_template_registry",
    "write_deck_blueprint",
    "compile_deck_blueprint",
    "run_ppt_pipeline",
    "publish_final",
    "copy_debug_ppt_to_final_name",
]

READINESS_DECISION_STATUSES = {"llm_decided", "qc_confirmed"}
READINESS_DECISION_OWNERS = {"reasoning", "qc"}

ROOT_DIR = find_runtime_root(__file__)
DEFAULT_ARTIFACT_MANIFEST = ROOT_DIR / "configs" / "artifact_manifest.json"
DEFAULT_MISSION_STATE = "artifacts/mission_state.json"
DEFAULT_FAILURE_MEMORY = "artifacts/failure_memory.jsonl"

ROLE_BY_STAGE = {
    "MATERIAL_INTAKE_MISSING_OR_FAILED": "material-intake",
    "INPUT_CARD_MISSING": "material-intake",
    "INDUSTRY_SCOPE_PACK_MISSING": "industry-scoping",
    "INDUSTRY_BOUNDARY_QC_REQUIRED": "qc",
    "INDUSTRY_SCOPE_FORMAT_MISSING_OR_FAILED": "industry-scoping",
    "FORMAL_SEARCH_PLAN_MISSING": "research-external-evidence",
    "EXECUTABLE_SEARCH_BATCH_MISSING_OR_FAILED": "research-external-evidence",
    "SOURCE_ARCHIVE_MISSING_OR_FAILED": "research-external-evidence",
    "FORMAL_RESEARCH_EXECUTION_MISSING_OR_FAILED": "research-external-evidence",
    "PRE_RESEARCH_PACK_GATE_FAILED": "qc",
    "RESEARCH_EVIDENCE_DB_MISSING_OR_FAILED": "knowledge-repository",
    "RESEARCH_PACK_MISSING_OR_FAILED": "knowledge-repository",
    "ISSUE_ANALYSIS_MISSING_OR_FAILED": "reasoning",
    "HYPOTHESIS_STORE_MISSING_OR_FAILED": "reasoning",
    "PAGE_ARGUMENT_PACK_MISSING_OR_FAILED": "reasoning",
    "TEMPLATE_REGISTRY_MISSING_OR_FAILED": "generation",
    "DECK_BLUEPRINT_MISSING_OR_FAILED": "generation",
    "PAGE_EVIDENCE_CONTRACT_MISSING_OR_FAILED": "generation",
    "RENDERER_SPEC_MISSING_OR_FAILED": "generation",
    "TEMPLATE_PROFILE_MISSING_OR_FAILED": "template",
    "TEMPLATE_FIT_FAILED": "template",
    "CHART_METRIC_BINDING_FAILED": "qc",
    "CONTENT_QUALITY_FAILED": "qc",
    "PRE_PPT_GATE_FAILED": "qc",
    "REPLACEMENT_DICT_MISSING_OR_FAILED": "output",
    "FILLED_PPT_VALIDATION_FAILED": "output",
    "FINAL_DELIVERY_NOT_READY": "qc",
    "STOP_AND_REPORT": "orchestrator",
    "CLIENT_READY": "output",
}

ROLE_SKILL_PATH = {
    "orchestrator": "SKILL.md",
    "material-intake": "references/material-intake.md",
    "knowledge-repository": "references/knowledge-repository.md",
    "industry-scoping": "references/industry-scoping.md",
    "research-external-evidence": "references/research-external-evidence.md",
    "reasoning": "references/reasoning.md",
    "generation": "references/generation.md",
    "template": "references/template.md",
    "qc": "references/qc.md",
    "output": "references/output.md",
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_json_for_state(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"cannot read JSON: {exc}") from exc


def load_artifact_manifest(path: Path = DEFAULT_ARTIFACT_MANIFEST) -> dict[str, Any]:
    data = load_json(path)
    if not isinstance(data.get("artifacts"), dict) or not isinstance(data.get("gates"), list):
        return {"artifacts": {}, "gates": []}
    return data


def boundary_qc_contract_errors(payload: dict[str, Any]) -> list[str]:
    """Check that a boundary pass carries usable Research handoff context."""

    errors: list[str] = []
    if str(payload.get("decision") or "").strip() != "pass":
        return errors
    rationale = str(payload.get("boundary_quality_rationale") or payload.get("rationale") or "").strip()
    if len(rationale) < 20:
        errors.append("industry_boundary_qc pass requires boundary_quality_rationale of at least 20 characters")
    validated_scope = payload.get("validated_scope")
    if not isinstance(validated_scope, dict):
        errors.append("industry_boundary_qc pass requires validated_scope")
        validated_scope = {}
    for field in ("working_market", "parent_market", "broader_market"):
        if not str(validated_scope.get(field) or "").strip():
            errors.append(f"industry_boundary_qc.validated_scope.{field} is required for pass")
    for field in (
        "areas_confirmed",
        "areas_uncertain",
        "excluded_scope_confirmed",
        "boundary_validation_requests",
        "formal_research_allowed_scope",
        "do_not_research_as_market_scope",
    ):
        if not isinstance(payload.get(field), list):
            errors.append(f"industry_boundary_qc.{field} must be an array")
    return errors


def manifest_gate_inputs(manifest: dict[str, Any], gate_id: str) -> list[str]:
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    gates = manifest.get("gates") if isinstance(manifest.get("gates"), list) else []
    artifact_key = ""
    for item in gates:
        if isinstance(item, dict) and item.get("gate") == gate_id:
            artifact_key = str(item.get("artifact") or "")
            break
    if not artifact_key:
        return []
    artifact = artifacts.get(artifact_key)
    if not isinstance(artifact, dict):
        return []
    input_keys = artifact.get("inputs")
    if not isinstance(input_keys, list):
        return []
    paths: list[str] = []
    for key in input_keys:
        source = artifacts.get(str(key))
        if isinstance(source, dict) and source.get("path"):
            paths.append(str(source["path"]))
    return paths


def manifest_gate_artifact(manifest: dict[str, Any], gate_id: str) -> tuple[dict[str, Any], bool]:
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    gates = manifest.get("gates") if isinstance(manifest.get("gates"), list) else []
    for item in gates:
        if not isinstance(item, dict) or item.get("gate") != gate_id:
            continue
        artifact_key = str(item.get("artifact") or "")
        artifact = artifacts.get(artifact_key)
        if isinstance(artifact, dict):
            return artifact, bool(item.get("require_client_ready"))
    return {}, False


def stale_validation_details(run_dir: Path, validation_rels: list[str], input_rels: list[str]) -> list[dict[str, str]]:
    stale: list[dict[str, str]] = []
    seen_inputs = []
    for rel in input_rels:
        if rel and rel not in seen_inputs:
            seen_inputs.append(rel)
    for validation_rel in validation_rels:
        validation_path = run_dir / validation_rel
        if not validation_path.exists():
            continue
        try:
            validation_mtime = validation_path.stat().st_mtime
        except OSError:
            continue
        for input_rel in seen_inputs:
            if input_rel == validation_rel:
                continue
            input_path = run_dir / input_rel
            if not input_path.exists():
                continue
            try:
                input_mtime = input_path.stat().st_mtime
            except OSError:
                continue
            if input_mtime > validation_mtime:
                stale.append(
                    {
                        "validation": validation_rel,
                        "stale_because_input_is_newer": input_rel,
                    }
                )
    return stale


def validation_passed(path: Path, *, require_client_ready: bool = False) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"
    data = load_json(path)
    if not data:
        return False, "unreadable"
    if data.get("is_valid") is not True:
        return False, "failed"
    if require_client_ready and data.get("client_ready") is not True:
        return False, "not_client_ready"
    return True, "passed"


def _read_jsonl_tail(path: Path, limit: int = 10) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines[-limit:]:
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _manifest_name(path: Path | str) -> str:
    return str(path)


def _default_mission_state(run_dir: Path, stage: str, status: str) -> dict[str, Any]:
    return {
        "schema_version": "mission_state_v1",
        "run_dir": str(run_dir),
        "current_delivery_type": "Pre-mandate Client Pitchbook Industry Section",
        "current_mission": "Build and validate a pre-mandate client-facing industry section only",
        "target_product": "industry section for pre-mandate client mandate prep",
        "not_cim_or_dd": "CIM, DD, and generic industry report outputs are prohibited unless explicitly approved by user",
        "current_stage": stage,
        "current_phase": stage,
        "current_evidence_stage": stage,
        "status": status,
        "enough_for_client_pitch": False,
        "evidence_limited_pitch_outline": True,
        "research_first_required": True,
        "can_publish_client_ready": False,
        "ready_for_next_stage": True,
        "evidence_readiness_note": "Run has not yet produced final evidence readiness telemetry.",
        "current_forbidden": ["hand-edit replacement_dict", "rebuild template_profile manually", "manually drop S-xxx IDs"],
    }


def _load_or_default_mission_state(run_dir: Path, stage: str, status: str) -> dict[str, Any]:
    path = run_dir / DEFAULT_MISSION_STATE
    if not path.exists():
        return _default_mission_state(run_dir, stage, status)
    payload = load_json(path)
    if not isinstance(payload, dict):
        return _default_mission_state(run_dir, stage, status)
    payload.setdefault("schema_version", "mission_state_v1")
    payload.setdefault("run_dir", str(run_dir))
    payload.setdefault("current_delivery_type", "Pre-mandate Client Pitchbook Industry Section")
    payload.setdefault("current_mission", "Build and validate a pre-mandate client-facing industry section only")
    payload.setdefault("current_evidence_stage", stage)
    payload.setdefault("current_stage", stage)
    payload.setdefault("current_phase", stage)
    payload.setdefault("ready_for_next_stage", True)
    payload.setdefault("status", status)
    payload.setdefault("can_publish_client_ready", False)
    payload.setdefault("enough_for_client_pitch", False)
    payload.setdefault("evidence_limited_pitch_outline", True)
    payload.setdefault("research_first_required", True)
    return payload


def _coerce_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _merge_evidence_readiness(
    mission_state: dict[str, Any],
    readiness: dict[str, Any],
) -> dict[str, Any]:
    mission_state["enough_for_client_pitch"] = bool(readiness.get("enough_for_client_pitch", False))
    mission_state["evidence_limited_pitch_outline"] = bool(readiness.get("evidence_limited_pitch_outline", False))
    mission_state["research_first_required"] = bool(readiness.get("research_first_required", False))
    mission_state["critical_gap_count"] = _coerce_int(readiness.get("critical_gap_count"), default=0)
    mission_state["research_pack_exists"] = bool(readiness.get("research_pack_exists", False))
    mission_state["evidence_row_count"] = _coerce_int(readiness.get("evidence_row_count"), default=0)
    mission_state["metric_row_count"] = _coerce_int(readiness.get("metric_row_count"), default=0)
    mission_state["evidence_readiness_decision_status"] = str(readiness.get("decision_status") or "needs_llm_decision")
    mission_state["evidence_readiness_decision_owner"] = str(readiness.get("decision_owner") or "reasoning")
    mission_state["evidence_readiness_note"] = str(
        readiness.get("decision_note")
        or "Evidence readiness is telemetry until Reasoning/QC records an explicit decision."
    )
    return mission_state


def _evidence_readiness_metrics(run_dir: Path, current_stage: str) -> dict[str, Any]:
    db_path = run_dir / "artifacts" / "research_evidence_db.json"
    pack_path = run_dir / "industry_research_pack.md"
    issue_analysis_path = run_dir / "industry_issue_analysis.json"
    gap_count = 0
    evidence_rows = 0
    metric_rows = 0
    if db_path.exists():
        payload = load_json(db_path)
        evidence_rows = len(_as_list(payload.get("evidence_ledger")))
        metric_rows = len(_as_list(payload.get("metric_reconciliation")))
        gap_audit = payload.get("research_gap_audit") if isinstance(payload.get("research_gap_audit"), dict) else {}
        gap_count = len(_as_list(gap_audit.get("critical_gaps")))

    pack_exists = pack_path.exists()
    decision_status = "needs_llm_decision"
    decision_owner = "reasoning"
    decision_note = "Evidence counts are telemetry only; Reasoning/QC has not recorded a readiness decision."
    enough_for_client_pitch = False
    outline_mode = True
    research_first_required = not pack_exists or (evidence_rows == 0 and metric_rows == 0)
    if issue_analysis_path.exists():
        try:
            issue_payload = load_json(issue_analysis_path)
        except Exception:
            issue_payload = {}
        issue_readiness = issue_payload.get("evidence_readiness") if isinstance(issue_payload, dict) else {}
        if isinstance(issue_readiness, dict):
            decision_status = str(issue_readiness.get("decision_status") or decision_status).strip().lower()
            decision_owner = str(issue_readiness.get("decision_owner") or decision_owner).strip().lower()
            decision_note = str(issue_readiness.get("decision_note") or decision_note)
            if decision_status in READINESS_DECISION_STATUSES and decision_owner in READINESS_DECISION_OWNERS:
                enough_for_client_pitch = bool(issue_readiness.get("enough_for_client_pitch", False))
                outline_mode = bool(issue_readiness.get("evidence_limited_pitch_outline", not enough_for_client_pitch))
                research_first_required = bool(issue_readiness.get("research_first_required", research_first_required))
    return {
        "decision_status": decision_status,
        "decision_owner": decision_owner,
        "decision_note": decision_note,
        "enough_for_client_pitch": enough_for_client_pitch,
        "evidence_limited_pitch_outline": outline_mode,
        "research_first_required": research_first_required,
        "evidence_row_count": evidence_rows,
        "metric_row_count": metric_rows,
        "critical_gap_count": gap_count,
        "research_pack_exists": pack_exists,
    }


def _gate_artifact_io(manifest: dict[str, Any], state: dict[str, Any]) -> tuple[list[str], list[str]]:
    stage_gate = str(state.get("gate") or "")
    artifact_spec, _ = manifest_gate_artifact(manifest, stage_gate)
    if not artifact_spec:
        return [], []
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    inputs = artifact_spec.get("inputs")
    input_paths: list[str] = []
    for item in _as_list(inputs):
        source = artifacts.get(str(item))
        if isinstance(source, dict) and source.get("path"):
            input_paths.append(str(source["path"]))
        else:
            input_paths.append(str(item))
    outputs = [str(artifact_spec.get("path") or artifact_spec.get("validation") or "")]
    validation = str(artifact_spec.get("validation") or "")
    if validation and validation not in outputs:
        outputs.append(validation)
    return input_paths, outputs


def _template_profile_check(run_dir: Path) -> dict[str, Any] | None:
    renderer_spec_path = run_dir / "renderer_spec.json"
    if not renderer_spec_path.exists():
        return None
    profile_path = run_dir / "artifacts" / "template_profile.json"
    if not profile_path.exists():
        return {
            "stage": "TEMPLATE_PROFILE_MISSING_OR_FAILED",
            "artifact": "artifacts/template_profile.json",
            "gate": TEMPLATE_PROFILE,
            "status": "missing",
            "allowed": ["run_template_analyzer", "rerun_template_analyzer", "rerun_pre_ppt_gate", "rerun_pipeline_validate_pre_ppt"],
            "forbidden": ["run_ppt_pipeline", "publish_final"],
            "missing_artifacts": ["artifacts/template_profile.json"],
        }
    try:
        profile = load_json_for_state(profile_path)
        if not isinstance(profile, dict):
            raise ValueError("template_profile.json must be an object")
    except Exception as exc:
        return {
            "stage": "TEMPLATE_PROFILE_MISSING_OR_FAILED",
            "artifact": "artifacts/template_profile.json",
            "gate": TEMPLATE_PROFILE,
            "status": "failed",
            "failed_validations": [
                {
                    "path": "artifacts/template_profile.json",
                    "status": "unreadable",
                    "error": str(exc),
                }
            ],
            "allowed": ["run_template_analyzer", "rerun_template_analyzer", "rerun_pre_ppt_gate", "rerun_pipeline_validate_pre_ppt"],
            "forbidden": ["run_ppt_pipeline", "publish_final"],
        }

    required_keys = ["schema_version", "template_file", "layout", "visual_style"]
    if profile.get("schema_version") != "template_profile_v1" or any(key not in profile for key in required_keys):
        missing = [key for key in required_keys if key not in profile]
        if profile.get("schema_version") != "template_profile_v1":
            errors = [f"template_profile.json schema_version must be template_profile_v1 (got {profile.get('schema_version')})"]
        else:
            errors = [f"template_profile.json missing required key(s): {', '.join(missing)}"]
        return {
            "stage": "TEMPLATE_PROFILE_MISSING_OR_FAILED",
            "artifact": "artifacts/template_profile.json",
            "gate": TEMPLATE_PROFILE,
            "status": "failed",
            "failed_validations": [
                {
                    "path": "artifacts/template_profile.json",
                    "status": "failed",
                    "errors": errors,
                }
            ],
            "allowed": ["run_template_analyzer", "rerun_template_analyzer", "rerun_pre_ppt_gate", "rerun_pipeline_validate_pre_ppt"],
            "forbidden": ["run_ppt_pipeline", "publish_final"],
        }
    return None


def _template_fit_validation_check(run_dir: Path) -> dict[str, Any] | None:
    validation_path = run_dir / "artifacts" / "template_fit_validation.json"
    profile_path = run_dir / "artifacts" / "template_profile.json"
    renderer_spec_path = run_dir / "renderer_spec.json"
    if not renderer_spec_path.exists():
        return None
    if not validation_path.exists():
        return {
            "stage": "TEMPLATE_FIT_FAILED",
            "artifact": "artifacts/template_fit_validation.json",
            "gate": TEMPLATE_FIT_VALIDATION,
            "status": "missing",
            "allowed": ["run_template_fit", "run_template_fit_analysis", "rerun_template_fit", "rerun_pre_ppt_gate", "rerun_pipeline_validate_pre_ppt"],
            "forbidden": ["run_ppt_pipeline", "publish_final"],
            "missing_artifacts": ["artifacts/template_fit_validation.json"],
        }
    try:
        fit_data = load_json_for_state(validation_path)
        if not isinstance(fit_data, dict):
            raise ValueError("template_fit_validation.json must be an object")
    except Exception as exc:
        return {
            "stage": "TEMPLATE_FIT_FAILED",
            "artifact": "artifacts/template_fit_validation.json",
            "gate": TEMPLATE_FIT_VALIDATION,
            "status": "failed",
            "failed_validations": [
                {
                    "path": "artifacts/template_fit_validation.json",
                    "status": "unreadable",
                    "error": str(exc),
                }
            ],
            "allowed": ["run_template_fit", "run_template_fit_analysis", "rerun_template_fit", "rerun_pre_ppt_gate", "rerun_pipeline_validate_pre_ppt"],
            "forbidden": ["run_ppt_pipeline", "publish_final"],
        }
    if fit_data.get("is_valid") is not True:
        error_text = "template_fit_validation.json is_valid=false"
        capacity_conflicts = fit_data.get("capacity_conflicts") if isinstance(fit_data.get("capacity_conflicts"), list) else []
        return {
            "stage": "TEMPLATE_FIT_FAILED",
            "artifact": "artifacts/template_fit_validation.json",
            "gate": TEMPLATE_FIT_VALIDATION,
            "status": "failed",
            "failed_validations": [
                {
                    "path": "artifacts/template_fit_validation.json",
                    "status": "failed",
                    "errors": [error_text] + [str(item) for item in fit_data.get("errors", [])],
                    "capacity_conflicts": capacity_conflicts,
                    "repair_owner": "generation" if fit_data.get("template_capacity_conflict") else "template",
                    "repair_action": "repair deck_blueprint/renderer_spec content density or choose a compatible template; do not truncate content silently"
                    if fit_data.get("template_capacity_conflict")
                    else "rerun template_fit.py and repair template profile or renderer inputs",
                }
            ],
            "allowed": ["run_template_fit", "run_template_fit_analysis", "rerun_template_fit", "rerun_pre_ppt_gate", "rerun_pipeline_validate_pre_ppt"],
            "forbidden": ["run_ppt_pipeline", "publish_final"],
        }
    try:
        validation_time = validation_path.stat().st_mtime
        if profile_path.exists() and profile_path.stat().st_mtime > validation_time + 1.0:
            return {
                "stage": "TEMPLATE_FIT_FAILED",
                "artifact": "artifacts/template_fit_validation.json",
                "gate": TEMPLATE_FIT_VALIDATION,
                "status": "stale",
                "allowed": ["run_template_fit", "run_template_fit_analysis", "rerun_template_fit", "rerun_pre_ppt_gate", "rerun_pipeline_validate_pre_ppt"],
                "forbidden": ["run_ppt_pipeline", "publish_final"],
                "stale_validations": [
                    {
                        "validation": "artifacts/template_fit_validation.json",
                        "stale_because_input_is_newer": "artifacts/template_profile.json",
                    }
                ],
            }
        if renderer_spec_path.exists() and renderer_spec_path.stat().st_mtime > validation_time + 1.0:
            return {
                "stage": "TEMPLATE_FIT_FAILED",
                "artifact": "artifacts/template_fit_validation.json",
                "gate": TEMPLATE_FIT_VALIDATION,
                "status": "stale",
                "allowed": ["run_template_fit", "run_template_fit_analysis", "rerun_template_fit", "rerun_pre_ppt_gate", "rerun_pipeline_validate_pre_ppt"],
                "forbidden": ["run_ppt_pipeline", "publish_final"],
                "stale_validations": [
                    {
                        "validation": "artifacts/template_fit_validation.json",
                        "stale_because_input_is_newer": "renderer_spec.json",
                    }
                ],
            }
    except OSError:
        pass
    return None


def gate_is_currently_valid(run_dir: Path, gate_id: str, manifest: dict[str, Any]) -> bool:
    """Return True when a previously blocked gate now has fresh passing validation.

    Repair attempts sometimes rerun a validator directly without recording the
    gate in gate_retry_state.json. In that case a stale retry block should not
    mask the real next failed gate.
    """
    artifact, require_client_ready = manifest_gate_artifact(manifest, gate_id)
    artifact_rel = str(artifact.get("path") or "")
    validation_rel = str(artifact.get("validation") or "")
    if not artifact_rel or not (run_dir / artifact_rel).exists():
        return False
    if not validation_rel:
        return True
    passed, _ = validation_passed(run_dir / validation_rel, require_client_ready=require_client_ready)
    if not passed:
        return False
    input_rels = [artifact_rel]
    input_rels.extend(manifest_gate_inputs(manifest, gate_id))
    return not stale_validation_details(run_dir, [validation_rel], input_rels)


def blocked_retry_gate(run_dir: Path) -> Optional[dict[str, Any]]:
    """Return a deterministic stop state when repeated repair has failed."""
    manifest = load_artifact_manifest()
    retry_state = load_gate_retry_state(run_dir)
    gates = retry_state.get("gates") if isinstance(retry_state, dict) else {}
    if not isinstance(gates, dict):
        return None
    for gate, gate_state in gates.items():
        if not isinstance(gate_state, dict):
            continue
        if gate_state.get("status") != "blocked":
            continue
        if gate_is_currently_valid(run_dir, str(gate), manifest):
            continue
        return {
            "stage": "STOP_AND_REPORT",
            "gate": str(gate),
            "status": "blocked",
            "allowed": ["report_blocker_to_user", "audit_recent_artifact_edits"],
            "forbidden": DOWNSTREAM_ACTIONS
            + [
                "schema_chasing_patch_loop",
                "remove_evidence_to_pass_validator",
                "clear_source_domains_to_reduce_count",
            ],
            "retry_state": gate_state,
            "failed_validations": [
                {
                    "path": "artifacts/gate_retry_state.json",
                    "status": "repair_limit_exceeded",
                    "failed_validation_count": gate_state.get("failed_validation_count", 0),
                    "max_repair_cycles": gate_state.get("max_repair_cycles", 3),
                    "last_errors": gate_state.get("last_errors", []),
                }
            ],
        }
    return None


def first_failed_gate(run_dir: Path) -> dict[str, Any]:
    manifest = load_artifact_manifest()

    checks = [
        {
            "stage": "MATERIAL_INTAKE_MISSING_OR_FAILED",
            "artifact": "artifacts/material_manifest.json",
            "validation": "artifacts/material_manifest_validation.json",
            "gate": "material_intake",
            "allowed": ["run_material_ingest", "rerun_material_intake", "run_material_manifest_validation"],
            "forbidden": [
                "create_material_only_summary",
                "write_industry_scope_pack",
                "write_formal_search_plan",
                "run_ppt_pipeline",
                "publish_final",
            ],
            "extra_artifacts": ["artifacts/material_extracts.json", "artifacts/source_classification.json"],
        },
        {
            "stage": "INPUT_CARD_MISSING",
            "artifact": "input_card.json",
            "validation": "artifacts/input_card_validation.json",
            "gate": INPUT_CARD,
            "allowed": ["create_input_card", "rerun_input_card_validation"],
            "forbidden": ["write_research_pack", "compile_deck_blueprint", "run_ppt_pipeline", "publish_final"],
        },
        {
            "stage": "INDUSTRY_SCOPE_PACK_MISSING",
            "artifact": "artifacts/industry_scope_pack.json",
            "validation": "",
            "gate": INDUSTRY_SCOPE_PACK,
            "allowed": ["create_industry_scope_pack"],
            "forbidden": ["write_research_pack", "compile_deck_blueprint", "run_ppt_pipeline", "publish_final"],
        },
        {
            "stage": "INDUSTRY_BOUNDARY_QC_REQUIRED",
            "artifact": "artifacts/industry_boundary_qc.json",
            "validation": "",
            "gate": INDUSTRY_BOUNDARY_QC,
            "allowed": ["run_llm_industry_boundary_qc", "repair_industry_scope_pack_from_qc_feedback", "create_boundary_research_requests_from_qc"],
            "forbidden": [
                "write_formal_search_plan",
                "run_formal_research",
                "run_ppt_pipeline",
                "publish_final",
                "build_formal_search_plan",
            ],
        },
        {
            "stage": "INDUSTRY_SCOPE_FORMAT_MISSING_OR_FAILED",
            "artifact": "artifacts/industry_scope_pack_validation.json",
            "validation": "artifacts/industry_scope_pack_validation.json",
            "gate": INDUSTRY_SCOPE_PACK,
            "allowed": ["rerun_industry_scope_pack_validation", "repair_scope_format_from_python_feedback"],
            "forbidden": ["write_research_pack", "compile_deck_blueprint", "run_ppt_pipeline", "publish_final"],
            "validation_inputs": ["artifacts/industry_scope_pack.json", "artifacts/industry_boundary_qc.json"],
        },
        {
            "stage": "FORMAL_SEARCH_PLAN_MISSING",
            "artifact": "artifacts/formal_search_plan.json",
            "validation": "artifacts/formal_search_plan_validation.json",
            "gate": FORMAL_SEARCH_PLAN,
            "allowed": ["create_formal_search_plan", "rerun_formal_search_plan_validation"],
            "forbidden": ["write_research_pack", "compile_deck_blueprint", "run_ppt_pipeline", "publish_final"],
        },
        {
            "stage": "EXECUTABLE_SEARCH_BATCH_MISSING_OR_FAILED",
            "artifact": "artifacts/executable_search_batch.json",
            "validation": "artifacts/executable_search_batch_validation.json",
            "gate": EXECUTABLE_SEARCH_BATCH,
            "allowed": ["author_executable_search_batch_with_llm", "rerun_executable_search_batch_validation"],
            "forbidden": ["run_formal_searches", "compile_research_graph", "write_research_pack", "compile_deck_blueprint", "run_ppt_pipeline", "publish_final"],
        },
        {
            "stage": "SOURCE_ARCHIVE_MISSING_OR_FAILED",
            "artifact": "artifacts/source_archive/source_archive_index.json",
            "validation": "artifacts/source_archive_validation.json",
            "gate": SOURCE_ARCHIVE,
            "allowed": ["run_formal_searches", "create_source_archive_snapshots_from_search_log", "fix_source_archive_index", "rerun_source_archive_validation"],
            "forbidden": ["write_research_pack", "compile_deck_blueprint", "run_ppt_pipeline", "publish_final"],
        },
        {
            "stage": "FORMAL_RESEARCH_EXECUTION_MISSING_OR_FAILED",
            "artifact": "artifacts/formal_research_execution_report.json",
            "validation": "artifacts/formal_research_execution_validation.json",
            "gate": FORMAL_RESEARCH_EXECUTION,
            "allowed": ["build_formal_research_execution_report", "fix_formal_research_execution_report", "rerun_formal_research_execution_validation"],
            "forbidden": ["write_research_pack", "compile_deck_blueprint", "run_ppt_pipeline", "publish_final"],
        },
        {
            "stage": "PRE_RESEARCH_PACK_GATE_FAILED",
            "artifact": "artifacts/stage_gate_pre_research_pack_validation.json",
            "validation": "artifacts/stage_gate_pre_research_pack_validation.json",
            "gate": PRE_RESEARCH_PACK,
            "allowed": ["fix_research_artifacts", "rerun_pre_research_pack_gate"],
            "forbidden": ["write_research_pack", "compile_deck_blueprint", "run_ppt_pipeline", "publish_final"],
        },
        {
            "stage": "RESEARCH_EVIDENCE_DB_MISSING_OR_FAILED",
            "artifact": "artifacts/research_evidence_db.json",
            "validation": "artifacts/research_evidence_db_validation.json",
            "gate": RESEARCH_EVIDENCE_DB,
            "allowed": ["build_research_evidence_db", "fix_research_evidence_db", "export_research_pack_from_db"],
            "forbidden": [
                "hand_write_research_pack",
                "generate_issue_analysis",
                "extract_template_registry",
                "write_deck_blueprint",
                "compile_deck_blueprint",
                "run_ppt_pipeline",
                "publish_final",
            ],
        },
        {
            "stage": "RESEARCH_PACK_MISSING_OR_FAILED",
            "artifact": "industry_research_pack.md",
            "validation": "artifacts/research_pack_validation.json",
            "gate": RESEARCH_PACK,
            "allowed": [
                "export_research_pack_from_db",
                "rerun_research_pack_validation",
                "fix_research_evidence_db_if_exported_pack_fails",
            ],
            "forbidden": [
                "hand_edit_research_pack",
                "generate_issue_analysis",
                "extract_template_registry",
                "write_deck_blueprint",
                "compile_deck_blueprint",
                "run_ppt_pipeline",
                "publish_final",
            ],
        },
        {
            "stage": "ISSUE_ANALYSIS_MISSING_OR_FAILED",
            "artifact": "industry_issue_analysis.json",
            "validation": "artifacts/issue_analysis_validation.json",
            "gate": ISSUE_ANALYSIS,
            "allowed": ["fix_issue_analysis", "rerun_issue_analysis_validation"],
            "forbidden": ["write_deck_blueprint", "compile_deck_blueprint", "run_ppt_pipeline", "publish_final"],
        },
        {
            "stage": "HYPOTHESIS_STORE_MISSING_OR_FAILED",
            "artifact": "artifacts/hypothesis_store.json",
            "validation": "artifacts/hypothesis_store_validation.json",
            "gate": HYPOTHESIS_STORE,
            "allowed": ["build_hypothesis_store_skeleton", "resolve_hypotheses_with_llm", "rerun_hypothesis_store_validation"],
            "forbidden": ["write_page_argument_pack", "write_deck_blueprint", "compile_deck_blueprint", "run_ppt_pipeline", "publish_final"],
        },
        {
            "stage": "PAGE_ARGUMENT_PACK_MISSING_OR_FAILED",
            "artifact": "artifacts/page_argument_pack.json",
            "validation": "artifacts/page_argument_pack_validation.json",
            "gate": PAGE_ARGUMENT_PACK,
            "allowed": ["build_page_argument_pack_skeleton", "author_page_argument_pack_with_llm", "rerun_page_argument_pack_validation"],
            "forbidden": ["write_deck_blueprint", "compile_deck_blueprint", "run_ppt_pipeline", "publish_final"],
        },
        {
            "stage": "TEMPLATE_REGISTRY_MISSING_OR_FAILED",
            "artifact": "template_registry.json",
            "validation": "artifacts/template_registry_validation.json",
            "gate": TEMPLATE_REGISTRY,
            "allowed": ["extract_template_registry", "rerun_template_registry_validation"],
            "forbidden": ["write_deck_blueprint", "compile_deck_blueprint", "run_ppt_pipeline", "publish_final"],
        },
        {
            "stage": "DECK_BLUEPRINT_MISSING_OR_FAILED",
            "artifact": "deck_blueprint.json",
            "validation": "artifacts/deck_blueprint_validation.json",
            "gate": DECK_BLUEPRINT,
            "allowed": ["write_deck_blueprint", "fix_deck_blueprint", "rerun_deck_blueprint_validation"],
            "forbidden": ["compile_deck_blueprint", "run_ppt_pipeline", "publish_final"],
        },
        {
            "stage": "PAGE_EVIDENCE_CONTRACT_MISSING_OR_FAILED",
            "artifact": "page_evidence_contract.json",
            "validation": "artifacts/page_evidence_contract_validation.json",
            "gate": PAGE_EVIDENCE_CONTRACT,
            "allowed": ["compile_deck_blueprint", "rerun_page_evidence_contract_validation"],
            "forbidden": ["run_ppt_pipeline", "publish_final"],
        },
        {
            "stage": "RENDERER_SPEC_MISSING_OR_FAILED",
            "artifact": "renderer_spec.json",
            "validation": "artifacts/renderer_spec_validation.json",
            "gate": RENDERER_SPEC,
            "allowed": ["fix_deck_blueprint", "compile_deck_blueprint", "rerun_renderer_spec_validation"],
            "forbidden": ["run_ppt_pipeline", "publish_final"],
        },
        {
            "stage": "CHART_METRIC_BINDING_FAILED",
            "artifact": "artifacts/chart_metric_binding_validation.json",
            "validation": "artifacts/chart_metric_binding_validation.json",
            "gate": CHART_METRIC_BINDING,
            "allowed": ["fix_chart_data_or_metric_reconciliation", "rerun_chart_metric_binding_validation", "run_python_pipeline_render"],
            "forbidden": ["publish_final"],
        },
        {
            "stage": "CONTENT_QUALITY_FAILED",
            "artifact": "artifacts/content_quality_validation.json",
            "validation": "artifacts/content_quality_validation.json",
            "gate": CONTENT_QUALITY,
            "allowed": ["fix_renderer_spec_or_research_pack", "rerun_content_quality_validation", "run_python_pipeline_render"],
            "forbidden": ["publish_final"],
        },
        {
            "stage": "PRE_PPT_GATE_FAILED",
            "artifact": "artifacts/stage_gate_pre_ppt_validation.json",
            "validation": "artifacts/stage_gate_pre_ppt_validation.json",
            "gate": PRE_PPT,
            "allowed": ["fix_upstream_artifacts", "rerun_pre_ppt_gate"],
            "forbidden": ["run_ppt_pipeline", "publish_final"],
        },
        {
            "stage": "REPLACEMENT_DICT_MISSING_OR_FAILED",
            "artifact": "replacement_dict.json",
            "validation": "artifacts/replacement_dict_validation.json",
            "gate": REPLACEMENT_DICT,
            "allowed": ["run_ppt_pipeline", "regenerate_replacement_dict", "rerun_replacement_dict_validation"],
            "forbidden": ["publish_final"],
        },
        {
            "stage": "FILLED_PPT_VALIDATION_FAILED",
            "artifact": "industry_section_filled_clean.pptx",
            "validation": "filled_ppt_validation.json",
            "gate": FILLED_PPT,
            "allowed": ["fix_renderer_spec_or_template_inputs", "rerun_ppt_pipeline"],
            "forbidden": ["publish_final"],
        },
        {
            "stage": "FINAL_DELIVERY_NOT_READY",
            "artifact": "artifacts/final_delivery_validation.json",
            "validation": "artifacts/final_delivery_validation.json",
            "gate": FINAL_DELIVERY,
            "require_client_ready": True,
            "allowed": ["fix_final_delivery_blocker", "rerun_final_delivery_gate"],
            "forbidden": ["publish_final"],
        },
    ]

    for idx, check in enumerate(checks):
        missing = []
        artifact = run_dir / check["artifact"]
        if not artifact.exists():
            missing.append(check["artifact"])
        for rel in check.get("extra_artifacts", []):
            if not (run_dir / rel).exists():
                missing.append(rel)
        if missing:
            return {**check, "status": "missing", "missing_artifacts": missing}

        if str(check.get("gate") or "") == INDUSTRY_BOUNDARY_QC:
            qc_payload = load_json(run_dir / check["artifact"])
            decision = str(qc_payload.get("decision") or "").strip()
            contract_errors = boundary_qc_contract_errors(qc_payload)
            if decision != "pass":
                return {
                    **check,
                    "status": "failed",
                    "failed_validations": [
                        {
                            "path": check["artifact"],
                            "status": f"qc_decision={decision or 'missing'}",
                            "message": (
                                "QC did not grant boundary pass. Route feedback to Scoping or run boundary "
                                "validation searches before formal search planning."
                            ),
                        }
                    ],
                }
            if contract_errors:
                return {
                    **check,
                    "status": "failed",
                    "failed_validations": [
                        {
                            "path": check["artifact"],
                            "status": "qc_contract_failed",
                            "message": "; ".join(contract_errors),
                        }
                    ],
                }

        validations = [rel for rel in [check.get("validation", "")] + list(check.get("extra_validations", [])) if rel]
        failed = []
        for rel in validations:
            passed, status = validation_passed(run_dir / rel, require_client_ready=bool(check.get("require_client_ready")))
            if not passed:
                failed.append({"path": rel, "status": status})
        if failed:
            return {**check, "status": "failed", "failed_validations": failed}

        # `extra_artifacts` are presence requirements for the stage, not
        # automatically provenance inputs for the primary validation. For
        # example, material_manifest_validation should not become stale merely
        # because material_extracts.json was later updated by LLM extraction.
        input_artifacts = [check["artifact"]] + list(check.get("validation_inputs", []))
        input_artifacts.extend(manifest_gate_inputs(manifest, str(check.get("gate") or "")))
        stale = stale_validation_details(run_dir, validations, input_artifacts)
        if stale:
            return {**check, "status": "stale", "stale_validations": stale}

        # After RENDERER_SPEC passes, check template layer before chart/content gates
        if str(check.get("gate") or "") == RENDERER_SPEC:
            template_profile_state = _template_profile_check(run_dir)
            if template_profile_state is not None:
                return template_profile_state
            template_fit_state = _template_fit_validation_check(run_dir)
            if template_fit_state is not None:
                return template_fit_state

    return {
        "stage": "CLIENT_READY",
        "gate": "",
        "status": "passed",
        "allowed": ["publish_final"],
        "forbidden": ["use_debug_output_as_final"],
    }


def validate_run_state(run_dir: Path, *, write_mission_state: bool = False) -> dict[str, Any]:
    debug_only = (run_dir / "DEBUG_OUTPUT_ONLY.txt").exists()
    draft_only = (run_dir / "DRAFT_NOT_CLIENT_READY.txt").exists()
    run_flags = load_json(run_dir / "artifacts" / "run_flags.json")
    if run_flags.get("debug_output_only") is True:
        debug_only = True
    if run_flags.get("draft_output_only") is True:
        draft_only = True

    state = blocked_retry_gate(run_dir) or first_failed_gate(run_dir)
    manifest = load_artifact_manifest()
    input_artifacts, output_artifacts = _gate_artifact_io(manifest, state)
    mission_state = _load_or_default_mission_state(run_dir, str(state.get("stage", "")), str(state.get("status", "")))
    evidence_readiness = _evidence_readiness_metrics(run_dir, state.get("stage", ""))
    _merge_evidence_readiness(mission_state, evidence_readiness)
    mission_state_path = run_dir / DEFAULT_MISSION_STATE
    if write_mission_state:
        mission_state_path.parent.mkdir(parents=True, exist_ok=True)
        mission_state_path.write_text(
            json.dumps(mission_state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    owner_role = ROLE_BY_STAGE.get(str(state.get("stage") or ""), "orchestrator")
    final_gate = load_json(run_dir / "artifacts" / "final_delivery_validation.json")
    final_delivery_valid = (
        final_gate.get("is_valid") is True
        and final_gate.get("client_ready") is True
        and not debug_only
        and not draft_only
    )

    forbidden = list(state.get("forbidden", []))
    if debug_only or draft_only:
        if "publish_final" not in forbidden:
            forbidden.append("publish_final")
        if "copy_debug_ppt_to_final_name" not in forbidden:
            forbidden.append("copy_debug_ppt_to_final_name")
        if draft_only and "call_draft_client_ready" not in forbidden:
            forbidden.append("call_draft_client_ready")

    return {
        "schema_version": "run_state_v1",
        "run_dir": str(run_dir),
        "current_stage": state["stage"],
        "owner_role": owner_role,
        "owner_skill": ROLE_SKILL_PATH.get(owner_role, ""),
        "repair_target_role": owner_role,
        "status": state["status"],
        "blocking_gate": state.get("gate", ""),
        "input_artifacts": input_artifacts,
        "output_artifacts": output_artifacts,
        "missing_artifacts": state.get("missing_artifacts", []),
        "failed_validations": state.get("failed_validations", []),
        "stale_validations": state.get("stale_validations", []),
        "retry_state": state.get("retry_state", {}),
        "allowed_next_actions": state.get("allowed", []),
        "forbidden_actions": forbidden,
        "debug_only": debug_only,
        "draft_only": draft_only,
        "final_delivery_valid": final_delivery_valid,
        "source_run_dir": run_flags.get("source_run_dir") or "",
        "output_run_dir": run_flags.get("output_run_dir") or str(run_dir),
        "package_of_record": run_flags.get("package_of_record") or str(run_dir),
        "mission_state": mission_state,
        "evidence_readiness": evidence_readiness,
        "failure_memory_tail": _read_jsonl_tail(run_dir / DEFAULT_FAILURE_MEMORY),
        "current_phase": state.get("stage", ""),
        "current_mission": mission_state.get("current_mission", ""),
        "message": message_for_state(state, debug_only),
    }


def message_for_state(state: dict[str, Any], debug_only: bool) -> str:
    if state.get("stage") == "STOP_AND_REPORT":
        gate = state.get("gate") or "current gate"
        retry = state.get("retry_state") if isinstance(state.get("retry_state"), dict) else {}
        count = retry.get("failed_validation_count", 0)
        limit = retry.get("max_repair_cycles", 3)
        return (
            f"{gate} exceeded the repair limit ({count}/{limit}). Stop generating downstream artifacts, "
            "report the blocker, and audit whether recent edits weakened evidence integrity."
        )
    if debug_only:
        return "Run is debug-only and cannot be delivered. Fix the formal gate instead of publishing PPT output."
    if state.get("status") == "stale":
        gate = state.get("gate") or "current gate"
        return f"{gate} validation is stale because an upstream artifact changed. Rerun this gate; do not edit downstream artifacts."
    stage = state.get("stage")
    if stage == "CLIENT_READY":
        return "Run is client-ready. Publish only the PPT referenced by the latest-final pointer."
    if stage in {"INDUSTRY_BOUNDARY_QC_REQUIRED"}:
        return (
            "Industry boundary QC is required. QC LLM must review boundary quality and grant "
            "decision=pass before formal research planning."
        )
    if stage in {"INDUSTRY_SCOPE_FORMAT_MISSING_OR_FAILED"}:
        return (
            "Boundary QC passed; run deterministic industry_scope_pack format/red-line validation "
            "before formal research planning."
        )
    if stage == "FORMAL_RESEARCH_EXECUTION_MISSING_OR_FAILED":
        return (
            "formal_research_execution is not complete. Reconcile every planned FS-xxx row against actual S-xxx searches; "
            "mark unexecuted rows explicitly and do not create fake S-xxx IDs or downstream evidence."
        )
    if stage == "RESEARCH_EVIDENCE_DB_MISSING_OR_FAILED":
        return (
            "research_evidence_db is not complete. Promote only reviewed SRC-backed executed evidence; planned-only or unexecuted "
            "FS rows belong in the gap audit, not EV/MET rows."
        )
    gate = state.get("gate") or "current gate"
    return f"{gate} is not complete. Route the smallest upstream repair to the owner role before downstream delivery work."


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a run directory and report allowed/forbidden next actions.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output", help="Optional JSON output path")
    parser.add_argument(
        "--write-state",
        action="store_true",
        help="Explicitly write artifacts/mission_state.json. Default is read-only dashboard behavior.",
    )
    args = parser.parse_args()

    result = validate_run_state(Path(args.run_dir), write_mission_state=args.write_state)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
