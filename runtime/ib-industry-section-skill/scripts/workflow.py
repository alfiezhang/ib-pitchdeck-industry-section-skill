#!/usr/bin/env python3
"""Lightweight workflow harness for formal run state and next actions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from validate_run_state import validate_run_state


def recommended_commands(state: dict[str, Any]) -> list[dict[str, str]]:
    """Return concrete next commands for common gate states.

    These commands are advisory and use the formal run directory as package of
    record. They are intentionally explicit so agents do not improvise ad-hoc
    repair scripts or bypass the validated path.
    """
    run_dir = state["run_dir"]
    stage = state["current_stage"]
    py = '"$PYTHON_CMD"'
    commands_by_stage: dict[str, list[dict[str, str]]] = {
        "INPUT_CARD_MISSING": [
            {
                "purpose": "validate input card after transcription-only creation",
                "command": f"{py} scripts/validate_input_card.py --input-card {run_dir}/input_card.json --output {run_dir}/artifacts/input_card_validation.json",
            }
        ],
        "INDUSTRY_SCOPE_PACK_MISSING_OR_FAILED": [
            {
                "purpose": "validate scope pack after definition/scoping repair",
                "command": f"{py} scripts/validate_industry_scope_pack.py --scope-pack {run_dir}/artifacts/industry_scope_pack.json --output {run_dir}/artifacts/industry_scope_pack_validation.json",
            }
        ],
        "FORMAL_SEARCH_PLAN_MISSING": [
            {
                "purpose": "build full-taxonomy formal search plan skeleton",
                "command": f"{py} scripts/build_formal_search_plan_skeleton.py --input-card {run_dir}/input_card.json --scope-pack {run_dir}/artifacts/industry_scope_pack.json --output {run_dir}/artifacts/formal_search_plan.json",
            },
            {
                "purpose": "validate formal search plan after editing executable queries",
                "command": f"{py} scripts/validate_formal_search_plan.py --formal-search-plan {run_dir}/artifacts/formal_search_plan.json --output {run_dir}/artifacts/formal_search_plan_validation.json",
            },
        ],
        "FORMAL_RESEARCH_EXECUTION_MISSING_OR_FAILED": [
            {
                "purpose": "rebuild execution report skeleton from plan/log/reviews",
                "command": f"{py} scripts/build_formal_research_execution_report_skeleton.py --formal-search-plan {run_dir}/artifacts/formal_search_plan.json --search-log {run_dir}/artifacts/search_log.md --source-reviews {run_dir}/artifacts/source_reviews.json --include-unexecuted --output {run_dir}/artifacts/formal_research_execution_report.json",
            },
            {
                "purpose": "validate formal research execution",
                "command": f"{py} scripts/validate_formal_research_execution.py --report {run_dir}/artifacts/formal_research_execution_report.json --formal-search-plan {run_dir}/artifacts/formal_search_plan.json --search-log {run_dir}/artifacts/search_log.md --output {run_dir}/artifacts/formal_research_execution_validation.json",
            },
        ],
        "SOURCE_REVIEWS_MISSING_OR_FAILED": [
            {
                "purpose": "append each real formal search attempt before source review; repeat per FS-xxx",
                "command": f"{py} scripts/append_search_attempt.py --search-log {run_dir}/artifacts/search_log.md --query '<exact query searched>' --stage formal_research_execution --fs-id FS-001 --selected-source '<exact reviewed URL>' --opened-reviewed yes --locator-excerpt '<page/section/table and short excerpt or limitation>'",
            },
            {
                "purpose": "build source review skeleton from search log selected URLs",
                "command": f"{py} scripts/build_source_reviews_skeleton.py --search-log {run_dir}/artifacts/search_log.md --output {run_dir}/artifacts/source_reviews.json",
            },
            {
                "purpose": "validate reviewed sources after LLM fills locator/excerpt/use decisions",
                "command": f"{py} scripts/validate_source_reviews.py --source-reviews {run_dir}/artifacts/source_reviews.json --search-log {run_dir}/artifacts/search_log.md --output {run_dir}/artifacts/source_reviews_validation.json",
            },
        ],
        "SOURCE_ARCHIVE_MISSING_OR_FAILED": [
            {
                "purpose": "build source archive from source reviews",
                "command": f"{py} scripts/build_source_archive.py --source-reviews {run_dir}/artifacts/source_reviews.json --run-dir {run_dir} --overwrite",
            }
        ],
        "PRE_RESEARCH_PACK_GATE_FAILED": [
            {
                "purpose": "rerun pre-research-pack gate after repairing execution/source/archive artifacts",
                "command": f"{py} scripts/validate_stage_gate.py --stage pre_research_pack --run-dir {run_dir} --output {run_dir}/artifacts/stage_gate_pre_research_pack_validation.json",
            }
        ],
        "RESEARCH_EVIDENCE_DB_MISSING_OR_FAILED": [
            {
                "purpose": "build research evidence database skeleton from reviewed formal research",
                "command": f"{py} scripts/build_research_evidence_db.py --input-card {run_dir}/input_card.json --scope-pack {run_dir}/artifacts/industry_scope_pack.json --formal-search-plan {run_dir}/artifacts/formal_search_plan.json --formal-research-execution-report {run_dir}/artifacts/formal_research_execution_report.json --source-reviews {run_dir}/artifacts/source_reviews.json --output {run_dir}/artifacts/research_evidence_db.json",
            },
            {
                "purpose": "validate research evidence database after LLM fills extracts/EV/MET/inventory fields",
                "command": f"{py} scripts/validate_research_evidence_db.py --research-evidence-db {run_dir}/artifacts/research_evidence_db.json --output {run_dir}/artifacts/research_evidence_db_validation.json",
            },
        ],
        "RESEARCH_PACK_MISSING_OR_FAILED": [
            {
                "purpose": "export readable research pack from research evidence database",
                "command": f"{py} scripts/export_research_pack_from_db.py --research-evidence-db {run_dir}/artifacts/research_evidence_db.json --output {run_dir}/industry_research_pack.md",
            },
            {
                "purpose": "validate generated research evidence pack",
                "command": f"{py} scripts/validate_research_pack.py --research-pack {run_dir}/industry_research_pack.md --run-dir {run_dir} --source-registry templates/source_registry.json --output {run_dir}/artifacts/research_pack_validation.json",
            },
        ],
        "ISSUE_ANALYSIS_MISSING_OR_FAILED": [
            {
                "purpose": "build issue analysis skeleton from research-pack inventory",
                "command": f"{py} scripts/build_issue_analysis_skeleton.py --research-evidence-db {run_dir}/artifacts/research_evidence_db.json --formal-research-execution-report {run_dir}/artifacts/formal_research_execution_report.json --output {run_dir}/industry_issue_analysis.json",
            },
            {
                "purpose": "normalize common LLM-shaped issue analysis aliases",
                "command": f"{py} scripts/normalize_issue_analysis.py --input {run_dir}/industry_issue_analysis.json --output {run_dir}/industry_issue_analysis.json --report {run_dir}/artifacts/issue_analysis_normalization.json",
            },
            {
                "purpose": "validate issue analysis after replacing skeleton placeholders with substantive analysis",
                "command": f"{py} scripts/validate_issue_analysis.py --issue-analysis {run_dir}/industry_issue_analysis.json --research-pack {run_dir}/industry_research_pack.md --output {run_dir}/artifacts/issue_analysis_validation.json",
            },
        ],
        "TEMPLATE_REGISTRY_MISSING_OR_FAILED": [
            {
                "purpose": "extract template registry",
                "command": f"{py} scripts/extract_template_registry.py --output {run_dir}/template_registry.json",
            },
            {
                "purpose": "validate template registry",
                "command": f"{py} scripts/validate_template_registry.py --template-registry {run_dir}/template_registry.json --slide-registry templates/slide_registry.json --output {run_dir}/artifacts/template_registry_validation.json",
            }
        ],
        "DECK_BLUEPRINT_MISSING_OR_FAILED": [
            {
                "purpose": "validate deck blueprint after page-editor repair",
                "command": f"{py} scripts/validate_deck_blueprint.py --deck-blueprint {run_dir}/deck_blueprint.json --issue-analysis {run_dir}/industry_issue_analysis.json --template-registry {run_dir}/template_registry.json --output {run_dir}/artifacts/deck_blueprint_validation.json",
            }
        ],
        "PAGE_EVIDENCE_CONTRACT_MISSING_OR_FAILED": [
            {
                "purpose": "compile blueprint into deterministic downstream artifacts",
                "command": f"{py} scripts/compile_deck_blueprint.py --issue-analysis {run_dir}/industry_issue_analysis.json --deck-blueprint {run_dir}/deck_blueprint.json --template-registry {run_dir}/template_registry.json --page-contract-output {run_dir}/page_evidence_contract.json --renderer-spec-output {run_dir}/renderer_spec.json",
            }
        ],
        "RENDERER_SPEC_MISSING_OR_FAILED": [
            {
                "purpose": "recompile renderer spec from repaired deck blueprint",
                "command": f"{py} scripts/compile_deck_blueprint.py --issue-analysis {run_dir}/industry_issue_analysis.json --deck-blueprint {run_dir}/deck_blueprint.json --template-registry {run_dir}/template_registry.json --page-contract-output {run_dir}/page_evidence_contract.json --renderer-spec-output {run_dir}/renderer_spec.json",
            }
        ],
        "CONTENT_QUALITY_FAILED": [
            {
                "purpose": "rerun content quality after repairing deck_blueprint/recompiling",
                "command": f"{py} scripts/validate_content_quality.py --renderer-spec {run_dir}/renderer_spec.json --research-pack {run_dir}/industry_research_pack.md --rules templates/content_quality_rules.json --text-fit-rules templates/text_fit_rules.json --layout-budget templates/layout_budget.json --output {run_dir}/artifacts/content_quality_validation.json",
            },
        ],
        "PRE_PPT_GATE_FAILED": [
            {
                "purpose": "run deterministic PPT pipeline after upstream repairs; it refreshes pre-PPT gate first",
                "command": f"{py} scripts/pipeline.py render --run-dir {run_dir}",
            }
        ],
        "REPLACEMENT_DICT_MISSING_OR_FAILED": [
            {
                "purpose": "run formal PPT pipeline in the current package-of-record attempt",
                "command": f"{py} scripts/pipeline.py render --run-dir {run_dir}",
            }
        ],
        "FINAL_DELIVERY_NOT_READY": [
            {
                "purpose": "rerun formal PPT pipeline after repairing final-delivery blockers",
                "command": f"{py} scripts/pipeline.py render --run-dir {run_dir}",
            }
        ],
    }
    return commands_by_stage.get(stage, [])


def status_payload(run_dir: Path) -> dict[str, Any]:
    return validate_run_state(run_dir)


def next_payload(run_dir: Path) -> dict[str, Any]:
    state = validate_run_state(run_dir)
    payload = {
        "schema_version": "workflow_next_v1",
        "run_dir": state["run_dir"],
        "source_run_dir": state.get("source_run_dir", ""),
        "output_run_dir": state.get("output_run_dir", state["run_dir"]),
        "package_of_record": state.get("package_of_record", state["run_dir"]),
        "current_stage": state["current_stage"],
        "status": state["status"],
        "blocking_gate": state["blocking_gate"],
        "missing_artifacts": state.get("missing_artifacts", []),
        "failed_validations": state.get("failed_validations", []),
        "stale_validations": state.get("stale_validations", []),
        "retry_state": state.get("retry_state", {}),
        "allowed_next_actions": state["allowed_next_actions"],
        "recommended_next_commands": recommended_commands(state),
        "forbidden_actions": state["forbidden_actions"],
        "debug_only": state["debug_only"],
        "final_delivery_valid": state["final_delivery_valid"],
        "message": state["message"],
    }
    if state["status"] in {"missing", "failed", "stale"}:
        payload["gate_policy"] = {
            "must_not_proceed_to_downstream": True,
            "must_fix_current_gate_first": True,
            "must_not_call_validator_failure_a_parsing_edge_case": True,
            "forbidden_until_gate_passes": state["forbidden_actions"],
        }
    if state["current_stage"] == "STOP_AND_REPORT":
        payload["repair_policy"] = {
            "must_stop_downstream_generation": True,
            "must_report_blocker_to_user": True,
            "must_audit_recent_edits": [
                "changed Opened/Reviewed to yes without source review",
                "removed broad_discovery search IDs instead of creating formal_research_execution searches",
                "cleared source_pack fields only to reduce domain count",
                "replaced official/filing domains with lower-authority media domains",
                "removed evidence or metric IDs only to pass validators",
            ],
        }
    return payload


def write_or_print(payload: dict[str, Any], output: str | None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
    print(text)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report formal workflow status and allowed next actions for a run directory."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("status", "next"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--run-dir", required=True)
        sub.add_argument("--output")

    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    if args.command == "status":
        payload = status_payload(run_dir)
    else:
        payload = next_payload(run_dir)
    write_or_print(payload, args.output)


if __name__ == "__main__":
    main()
