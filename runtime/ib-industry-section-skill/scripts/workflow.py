#!/usr/bin/env python3
"""Lightweight workflow harness for formal run state and next actions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from validate_run_state import validate_run_state

PYTHON_COMMAND_TEMPLATE = '"$PYTHON_CMD"'


COMMAND_TEMPLATES_BY_STAGE: dict[str, list[dict[str, str]]] = {
    "INPUT_CARD_MISSING": [
        {
            "purpose": "validate input card after transcription-only creation",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/validate_input_card.py --input-card {{run_dir}}/input_card.json --output {{run_dir}}/artifacts/input_card_validation.json",
        },
    ],
    "INDUSTRY_SCOPE_PACK_MISSING_OR_FAILED": [
        {
            "purpose": "validate scope pack after definition/scoping repair; boundary validation is scoping-only and uses broad_discovery, not formal research conclusions",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/validate_industry_scope_pack.py --scope-pack {{run_dir}}/artifacts/industry_scope_pack.json --output {{run_dir}}/artifacts/industry_scope_pack_validation.json",
        },
    ],
    "FORMAL_SEARCH_PLAN_MISSING": [
        {
            "purpose": "build full-taxonomy formal search plan skeleton as coverage_audit (coverage rows only, formal_research_execution stage)",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/build_formal_search_plan_skeleton.py --input-card {{run_dir}}/input_card.json --scope-pack {{run_dir}}/artifacts/industry_scope_pack.json --output {{run_dir}}/artifacts/formal_search_plan.json",
        },
        {
            "purpose": "validate formal search plan after editing executable queries",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/validate_formal_search_plan.py --formal-search-plan {{run_dir}}/artifacts/formal_search_plan.json --output {{run_dir}}/artifacts/formal_search_plan_validation.json",
        },
    ],
    "FORMAL_RESEARCH_EXECUTION_MISSING_OR_FAILED": [
        {
            "purpose": "rebuild planned-vs-actual execution accounting from plan/log/reviews; include unexecuted FS rows explicitly",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/build_formal_research_execution_report_skeleton.py --formal-search-plan {{run_dir}}/artifacts/formal_search_plan.json --search-log {{run_dir}}/artifacts/search_log.md --source-reviews {{run_dir}}/artifacts/source_reviews.json --include-unexecuted --output {{run_dir}}/artifacts/formal_research_execution_report.json",
        },
        {
            "purpose": "validate formal research execution accounting; planned FS rows without actual S-xxx attempts must be marked not_executed/not_material/accounting_only, not faked",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/validate_formal_research_execution.py --report {{run_dir}}/artifacts/formal_research_execution_report.json --formal-search-plan {{run_dir}}/artifacts/formal_search_plan.json --search-log {{run_dir}}/artifacts/search_log.md --output {{run_dir}}/artifacts/formal_research_execution_validation.json",
        },
    ],
    "SOURCE_REVIEWS_MISSING_OR_FAILED": [
        {
            "purpose": "append each real formal search attempt before source review; S-xxx IDs are only for actual searches, never for unexecuted FS rows",
            "command": (
                f"{PYTHON_COMMAND_TEMPLATE} scripts/append_search_attempt.py --search-log {{run_dir}}/artifacts/search_log.md "
                "--query '<exact query searched>' --stage formal_research_execution --fs-id FS-001 --selected-source '<exact reviewed URL>' "
                "--opened-reviewed yes --locator-excerpt '<page/section/table and short excerpt or limitation>'"
            ),
        },
        {
            "purpose": "build source review skeleton from search log selected URLs",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/build_source_reviews_skeleton.py --search-log {{run_dir}}/artifacts/search_log.md --input-card {{run_dir}}/input_card.json --output {{run_dir}}/artifacts/source_reviews.json",
        },
        {
            "purpose": "validate reviewed sources after LLM fills locator/excerpt/use decisions",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/validate_source_reviews.py --source-reviews {{run_dir}}/artifacts/source_reviews.json --search-log {{run_dir}}/artifacts/search_log.md --output {{run_dir}}/artifacts/source_reviews_validation.json",
        },
    ],
    "SOURCE_ARCHIVE_MISSING_OR_FAILED": [
        {
            "purpose": "build source archive from source reviews",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/build_source_archive.py --source-reviews {{run_dir}}/artifacts/source_reviews.json --run-dir {{run_dir}} --overwrite",
        },
    ],
    "PRE_RESEARCH_PACK_GATE_FAILED": [
        {
            "purpose": "rerun pre-research-pack gate after repairing execution/source/archive artifacts",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/validate_stage_gate.py --stage pre_research_pack --run-dir {{run_dir}} --output {{run_dir}}/artifacts/stage_gate_pre_research_pack_validation.json",
        },
    ],
    "RESEARCH_EVIDENCE_DB_MISSING_OR_FAILED": [
        {
            "purpose": "build research evidence database skeleton from reviewed formal research",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/build_research_evidence_db.py --input-card {{run_dir}}/input_card.json --scope-pack {{run_dir}}/artifacts/industry_scope_pack.json --formal-search-plan {{run_dir}}/artifacts/formal_search_plan.json --formal-research-execution-report {{run_dir}}/artifacts/formal_research_execution_report.json --source-reviews {{run_dir}}/artifacts/source_reviews.json --output {{run_dir}}/artifacts/research_evidence_db.json",
        },
        {
            "purpose": "validate research evidence database after LLM fills extracts/EV/MET/inventory fields",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/validate_research_evidence_db.py --research-evidence-db {{run_dir}}/artifacts/research_evidence_db.json --output {{run_dir}}/artifacts/research_evidence_db_validation.json",
        },
    ],
    "RESEARCH_PACK_MISSING_OR_FAILED": [
        {
            "purpose": "export readable research pack from research evidence database",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/export_research_pack_from_db.py --research-evidence-db {{run_dir}}/artifacts/research_evidence_db.json --output {{run_dir}}/industry_research_pack.md",
        },
        {
            "purpose": "validate generated research evidence pack",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/validate_research_pack.py --research-pack {{run_dir}}/industry_research_pack.md --run-dir {{run_dir}} --source-registry templates/source_registry.json --output {{run_dir}}/artifacts/research_pack_validation.json",
        },
    ],
    "ISSUE_ANALYSIS_MISSING_OR_FAILED": [
        {
            "purpose": "build issue analysis skeleton from research-pack inventory",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/build_issue_analysis_skeleton.py --research-evidence-db {{run_dir}}/artifacts/research_evidence_db.json --formal-research-execution-report {{run_dir}}/artifacts/formal_research_execution_report.json --output {{run_dir}}/industry_issue_analysis.json",
        },
        {
            "purpose": "normalize common LLM-shaped issue analysis aliases",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/normalize_issue_analysis.py --input {{run_dir}}/industry_issue_analysis.json --output {{run_dir}}/industry_issue_analysis.json --report {{run_dir}}/artifacts/issue_analysis_normalization.json",
        },
        {
            "purpose": "validate issue analysis after replacing skeleton placeholders with substantive analysis",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/validate_issue_analysis.py --issue-analysis {{run_dir}}/industry_issue_analysis.json --research-pack {{run_dir}}/industry_research_pack.md --output {{run_dir}}/artifacts/issue_analysis_validation.json",
        },
    ],
    "TEMPLATE_REGISTRY_MISSING_OR_FAILED": [
        {
            "purpose": "extract template registry",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/extract_template_registry.py --output {{run_dir}}/template_registry.json",
        },
        {
            "purpose": "validate template registry",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/validate_template_registry.py --template-registry {{run_dir}}/template_registry.json --slide-registry templates/slide_registry.json --output {{run_dir}}/artifacts/template_registry_validation.json",
        },
    ],
    "DECK_BLUEPRINT_MISSING_OR_FAILED": [
        {
            "purpose": "validate deck blueprint after page-editor repair",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/validate_deck_blueprint.py --deck-blueprint {{run_dir}}/deck_blueprint.json --issue-analysis {{run_dir}}/industry_issue_analysis.json --template-registry {{run_dir}}/template_registry.json --output {{run_dir}}/artifacts/deck_blueprint_validation.json",
        },
    ],
    "PAGE_EVIDENCE_CONTRACT_MISSING_OR_FAILED": [
        {
            "purpose": "compile blueprint into deterministic downstream artifacts",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/compile_deck_blueprint.py --issue-analysis {{run_dir}}/industry_issue_analysis.json --deck-blueprint {{run_dir}}/deck_blueprint.json --template-registry {{run_dir}}/template_registry.json --page-contract-output {{run_dir}}/page_evidence_contract.json --renderer-spec-output {{run_dir}}/renderer_spec.json",
        },
    ],
    "RENDERER_SPEC_MISSING_OR_FAILED": [
        {
            "purpose": "recompile renderer spec from repaired deck blueprint",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/compile_deck_blueprint.py --issue-analysis {{run_dir}}/industry_issue_analysis.json --deck-blueprint {{run_dir}}/deck_blueprint.json --template-registry {{run_dir}}/template_registry.json --page-contract-output {{run_dir}}/page_evidence_contract.json --renderer-spec-output {{run_dir}}/renderer_spec.json",
        },
    ],
    "CONTENT_QUALITY_FAILED": [
        {
            "purpose": "rerun content quality after repairing deck_blueprint/recompiling",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/validate_content_quality.py --renderer-spec {{run_dir}}/renderer_spec.json --research-pack {{run_dir}}/industry_research_pack.md --rules templates/content_quality_rules.json --text-fit-rules templates/text_fit_rules.json --layout-budget templates/layout_budget.json --output {{run_dir}}/artifacts/content_quality_validation.json",
        },
    ],
    "PRE_PPT_GATE_FAILED": [
        {
            "purpose": "run deterministic PPT pipeline after upstream repairs; it refreshes pre-PPT gate first",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/pipeline.py render --run-dir {{run_dir}}",
        },
    ],
    "REPLACEMENT_DICT_MISSING_OR_FAILED": [
        {
            "purpose": "run formal PPT pipeline in the current package-of-record attempt",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/pipeline.py render --run-dir {{run_dir}}",
        },
    ],
    "FINAL_DELIVERY_NOT_READY": [
        {
            "purpose": "rerun formal PPT pipeline after repairing final-delivery blockers",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/pipeline.py render --run-dir {{run_dir}}",
        },
    ],
}


def dedupe_commands(commands: list[dict[str, str]]) -> list[dict[str, str]]:
    """Keep command recommendations stable and unique by command string."""
    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for item in commands:
        command = item.get("command", "")
        if command in seen:
            continue
        seen.add(command)
        deduped.append(item)
    return deduped


def _render_command_template(item: dict[str, str], *, run_dir: str) -> dict[str, str]:
    return {
        "purpose": item["purpose"],
        "command": item["command"].format(run_dir=run_dir),
    }


def recommended_commands(state: dict[str, Any]) -> list[dict[str, str]]:
    """Return concrete next commands for common gate states."""
    stage = state["current_stage"]
    run_dir = str(state["run_dir"])
    return [_render_command_template(item, run_dir=run_dir) for item in COMMAND_TEMPLATES_BY_STAGE.get(stage, [])]


def status_payload(run_dir: Path) -> dict[str, Any]:
    return validate_run_state(run_dir)


def next_payload(run_dir: Path) -> dict[str, Any]:
    state = validate_run_state(run_dir)
    next_commands = dedupe_commands(recommended_commands(state))
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
        "recommended_next_command": next_commands[0]["command"] if next_commands else "",
        "recommended_next_commands": next_commands,
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
    if state["current_stage"] == "FORMAL_RESEARCH_EXECUTION_MISSING_OR_FAILED":
        payload["planned_vs_actual_search_policy"] = {
            "fs_rows_are": "planned coverage instructions",
            "s_rows_are": "actual executed search attempts",
            "must_account_for_every_planned_fs_row": True,
            "unexecuted_fs_rows": "mark as not_executed, not_material, accounting_only, insufficient, or backlog",
            "do_not": [
                "Do not create fake S-xxx IDs for unexecuted FS rows.",
                "Do not build source_reviews for unexecuted FS rows.",
                "Do not build research_evidence_db from planned queries.",
                "Do not write issue_analysis or deck_blueprint until execution accounting passes.",
            ],
        }
        payload["repair_target"] = {
            "artifact": "artifacts/formal_research_execution_report.json",
            "required_steps": [
                "Run build_formal_research_execution_report_skeleton --include-unexecuted to force every planned FS-xxx row into issue_results + fs_row_execution_status.",
                "In each FR row, keep search_instruction_ids aligned to its FS owner, set search_attempt_ids only for real S-xxx attempts from search_log.md.",
                "Mark each unexecuted or immaterial FS row explicitly (not_executed/not_material/accounting_only) and leave evidence IDs empty for those rows.",
            ],
        }
    if state["current_stage"] == "RESEARCH_EVIDENCE_DB_MISSING_OR_FAILED":
        payload["evidence_db_policy"] = {
            "may_promote": "only FR rows with terminal_status=executed_with_evidence and reviewed SRC support",
            "must_gap_audit": "not_executed, not_material, accounting_only, or executed_no_usable_source rows",
            "do_not": [
                "Do not create FX/EV/MET rows from planned-only FS rows.",
                "Do not use search snippets or unreviewed URLs as evidence.",
            ],
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
