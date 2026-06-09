#!/usr/bin/env python3
"""Read-only state inspector for an IB industry-section run directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Optional

from gate_retry_state import load_state as load_gate_retry_state
from gate_names import (
    CONTENT_QUALITY,
    CHART_METRIC_BINDING,
    FILLED_PPT,
    FINAL_DELIVERY,
    FORMAL_SEARCH_PLAN,
    INDUSTRY_SCOPE_PACK,
    INPUT_CARD,
    ISSUE_ANALYSIS,
    RESEARCH_PACK,
    DECK_BLUEPRINT,
    PAGE_EVIDENCE_CONTRACT,
    PRE_RESEARCH_PACK,
    PRE_PPT,
    RENDERER_SPEC,
    REPLACEMENT_DICT,
    SOURCE_ARCHIVE,
    SOURCE_REVIEWS,
    FORMAL_RESEARCH_EXECUTION,
    TEMPLATE_REGISTRY,
)


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

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
DEFAULT_ARTIFACT_MANIFEST = ROOT_DIR / "templates" / "artifact_manifest.json"


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_artifact_manifest(path: Path = DEFAULT_ARTIFACT_MANIFEST) -> dict[str, Any]:
    data = load_json(path)
    if not isinstance(data.get("artifacts"), dict) or not isinstance(data.get("gates"), list):
        return {"artifacts": {}, "gates": []}
    return data


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
            "stage": "INPUT_CARD_MISSING",
            "artifact": "input_card.json",
            "validation": "artifacts/input_card_validation.json",
            "gate": INPUT_CARD,
            "allowed": ["create_input_card", "rerun_input_card_validation"],
            "forbidden": ["write_research_pack", "compile_deck_blueprint", "run_ppt_pipeline", "publish_final"],
        },
        {
            "stage": "INDUSTRY_SCOPE_PACK_MISSING_OR_FAILED",
            "artifact": "artifacts/industry_scope_pack.json",
            "validation": "artifacts/industry_scope_pack_validation.json",
            "gate": INDUSTRY_SCOPE_PACK,
            "allowed": ["create_industry_scope_pack", "rerun_industry_scope_pack_validation"],
            "forbidden": ["write_research_pack", "compile_deck_blueprint", "run_ppt_pipeline", "publish_final"],
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
            "stage": "SOURCE_REVIEWS_MISSING_OR_FAILED",
            "artifact": "artifacts/source_reviews.json",
            "validation": "artifacts/source_reviews_validation.json",
            "gate": SOURCE_REVIEWS,
            "allowed": ["run_formal_searches", "create_source_reviews", "fix_source_reviews", "rerun_source_reviews_validation"],
            "forbidden": ["write_research_pack", "compile_deck_blueprint", "run_ppt_pipeline", "publish_final"],
        },
        {
            "stage": "SOURCE_ARCHIVE_MISSING_OR_FAILED",
            "artifact": "artifacts/source_archive/source_archive_index.json",
            "validation": "artifacts/source_archive_validation.json",
            "gate": SOURCE_ARCHIVE,
            "allowed": ["create_source_archive_snapshots", "fix_source_archive_index", "rerun_source_archive_validation"],
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
            "stage": "RESEARCH_PACK_MISSING_OR_FAILED",
            "artifact": "industry_research_pack.md",
            "validation": "artifacts/research_pack_validation.json",
            "gate": RESEARCH_PACK,
            "allowed": ["fix_research_pack", "rerun_research_pack_validation"],
            "forbidden": [
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

    for check in checks:
        missing = []
        artifact = run_dir / check["artifact"]
        if not artifact.exists():
            missing.append(check["artifact"])
        for rel in check.get("extra_artifacts", []):
            if not (run_dir / rel).exists():
                missing.append(rel)
        if missing:
            return {**check, "status": "missing", "missing_artifacts": missing}

        validations = [rel for rel in [check.get("validation", "")] + list(check.get("extra_validations", [])) if rel]
        failed = []
        for rel in validations:
            passed, status = validation_passed(run_dir / rel, require_client_ready=bool(check.get("require_client_ready")))
            if not passed:
                failed.append({"path": rel, "status": status})
        if failed:
            return {**check, "status": "failed", "failed_validations": failed}

        input_artifacts = [check["artifact"]] + list(check.get("extra_artifacts", []))
        input_artifacts.extend(manifest_gate_inputs(manifest, str(check.get("gate") or "")))
        stale = stale_validation_details(run_dir, validations, input_artifacts)
        if stale:
            return {**check, "status": "stale", "stale_validations": stale}

    return {
        "stage": "CLIENT_READY",
        "gate": "",
        "status": "passed",
        "allowed": ["publish_final"],
        "forbidden": ["use_debug_output_as_final"],
    }


def validate_run_state(run_dir: Path) -> dict[str, Any]:
    debug_only = (run_dir / "DEBUG_OUTPUT_ONLY.txt").exists()
    run_flags = load_json(run_dir / "artifacts" / "run_flags.json")
    if run_flags.get("debug_output_only") is True:
        debug_only = True

    state = blocked_retry_gate(run_dir) or first_failed_gate(run_dir)
    final_gate = load_json(run_dir / "artifacts" / "final_delivery_validation.json")
    final_delivery_valid = final_gate.get("is_valid") is True and final_gate.get("client_ready") is True and not debug_only

    forbidden = list(state.get("forbidden", []))
    if debug_only:
        if "publish_final" not in forbidden:
            forbidden.append("publish_final")
        if "copy_debug_ppt_to_final_name" not in forbidden:
            forbidden.append("copy_debug_ppt_to_final_name")

    return {
        "schema_version": "run_state_v1",
        "run_dir": str(run_dir),
        "current_stage": state["stage"],
        "status": state["status"],
        "blocking_gate": state.get("gate", ""),
        "missing_artifacts": state.get("missing_artifacts", []),
        "failed_validations": state.get("failed_validations", []),
        "stale_validations": state.get("stale_validations", []),
        "retry_state": state.get("retry_state", {}),
        "allowed_next_actions": state.get("allowed", []),
        "forbidden_actions": forbidden,
        "debug_only": debug_only,
        "final_delivery_valid": final_delivery_valid,
        "source_run_dir": run_flags.get("source_run_dir") or "",
        "output_run_dir": run_flags.get("output_run_dir") or str(run_dir),
        "package_of_record": run_flags.get("package_of_record") or str(run_dir),
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
    gate = state.get("gate") or "current gate"
    return f"{gate} is not complete. Do not proceed to downstream stages until this gate passes."


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a run directory and report allowed/forbidden next actions.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output", help="Optional JSON output path")
    args = parser.parse_args()

    result = validate_run_state(Path(args.run_dir))
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
