#!/usr/bin/env python3
"""Lightweight workflow harness for formal run state and next actions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from validate_run_state import validate_run_state

PYTHON_COMMAND_TEMPLATE = '"$PYTHON_CMD"'

GLOBAL_QC_PROTOCOL: dict[str, Any] = {
    "principle": "LLM QC judges quality and routes repairs; Python checks deterministic structure, provenance, stale state, and renderability.",
    "no_qc_validator_loop": True,
    "main_agent_receives_script_output_first": True,
    "default_rules": [
        "If an LLM QC decision is not pass, do not run the downstream Python format validator; follow the QC route first.",
        "If an LLM QC decision is pass but the Python validator fails, route to the owner role to repair format/red-line issues and rerun the same validator.",
        "Do not re-run LLM QC after pure format repair unless the repair changes substantive judgment, scope, source use, evidence status, or page argument.",
        "Warnings require owner repair or QC disposition; they are not silent permission to proceed.",
        "QC artifacts are authored by the QC role. Do not add separate validators whose only job is to judge whether QC wrote enough prose.",
    ],
}


QC_POLICY_BY_STAGE: dict[str, dict[str, Any]] = {
    "INPUT_CARD_MISSING": {
        "checkpoint": "Material/Input transcription",
        "qc_mode": "No LLM QC required unless material meaning is ambiguous; Python validates transcription and required fields.",
        "if_not_ok": "Material role repairs material capture/input_card, then reruns material/input-card validators.",
    },
    "INDUSTRY_SCOPE_PACK_MISSING": {
        "checkpoint": "Scoping authoring",
        "qc_mode": "Scoping writes scope pack first; do not run format validation until boundary QC has reviewed the substantive boundary.",
        "if_not_ok": "Scoping rewrites industry_scope_pack before QC or Research proceeds.",
    },
    "INDUSTRY_BOUNDARY_QC_REQUIRED": {
        "checkpoint": "Industry Boundary QC",
        "qc_mode": "QC LLM decides pass / needs_scope_repair / needs_boundary_validation using boundary-validation search when needed.",
        "if_pass": "Run validate_industry_scope_pack.py.",
        "if_needs_scope_repair": "Scoping repairs industry_scope_pack from QC feedback, then QC reviews again.",
        "if_needs_boundary_validation": "Research executes the requested boundary checks; Knowledge records sources; QC reviews again.",
    },
    "INDUSTRY_SCOPE_FORMAT_MISSING_OR_FAILED": {
        "checkpoint": "Scope format/red-line check",
        "qc_mode": "Boundary QC already passed; Python now checks deterministic scope schema and prohibited confirmed claims.",
        "if_not_ok": "Scoping repairs format/red-line issues and reruns validate_industry_scope_pack.py; re-QC only if the boundary changed.",
    },
    "FORMAL_SEARCH_PLAN_MISSING": {
        "checkpoint": "Research planning quality",
        "qc_mode": "Research owns executable query quality; Python validates taxonomy coverage and non-empty executable searches.",
        "if_not_ok": "Research rewrites coverage/search batch. QC may route poor query quality but should not accept generic unusable queries.",
    },
    "SOURCE_REVIEWS_MISSING_OR_FAILED": {
        "checkpoint": "Source review quality",
        "qc_mode": "Research judges source usability; QC adjudicates source-quality warnings. Python checks actual S/SRC linkage, locators, and required fields.",
        "if_not_ok": "Research repairs source_reviews or runs better searches. QC decides downgrade/reject/limited-use when quality is debatable.",
    },
    "SOURCE_ARCHIVE_MISSING_OR_FAILED": {
        "checkpoint": "Source archive integrity",
        "qc_mode": "Python archives reviewed sources. QC only routes archive failures; it does not create source evidence.",
        "if_not_ok": "Research/Output repairs archive inputs or source review links and reruns archive validation.",
    },
    "FORMAL_RESEARCH_EXECUTION_MISSING_OR_FAILED": {
        "checkpoint": "Planned-vs-actual research accounting",
        "qc_mode": "Python checks accounting consistency; Research owns truthful execution status. QC routes any attempt to fake S-xxx or promote planned-only evidence.",
        "if_not_ok": "Research reconciles every FS row against real S rows, marks gaps explicitly, and reruns validation.",
    },
    "PRE_RESEARCH_PACK_GATE_FAILED": {
        "checkpoint": "Pre evidence-pack gate",
        "qc_mode": "QC groups upstream research/source/archive failures and routes to the smallest owner repair.",
        "if_not_ok": "Repair the upstream research artifact; do not build evidence DB or issue analysis.",
    },
    "RESEARCH_EVIDENCE_DB_MISSING_OR_FAILED": {
        "checkpoint": "Knowledge/evidence extraction",
        "qc_mode": "Knowledge extracts facts/metrics/limits; QC reviews evidence quality/use limits. Python checks schema, IDs, and provenance.",
        "if_not_ok": "Knowledge repairs extraction. QC routes thin/unsupported evidence to Research or Reasoning, not downstream deck generation.",
    },
    "RESEARCH_PACK_MISSING_OR_FAILED": {
        "checkpoint": "Evidence-pack export",
        "qc_mode": "Research pack is derived from evidence DB; Python validates the export. QC routes content weaknesses back to Knowledge/Research, not the Markdown export.",
        "if_not_ok": "Fix research_evidence_db or upstream source reviews, re-export, rerun validation.",
    },
    "ISSUE_ANALYSIS_MISSING_OR_FAILED": {
        "checkpoint": "Reasoning/readiness judgment",
        "qc_mode": "Reasoning decides supported judgments, hypotheses, and evidence_readiness; QC may confirm or reject readiness. Python checks required reasoning fields.",
        "if_not_ok": "Reasoning repairs issue_analysis/evidence_readiness. If evidence is too thin, route to Research Request Queue instead of forcing an 8-page deck.",
    },
    "TEMPLATE_REGISTRY_MISSING_OR_FAILED": {
        "checkpoint": "Template registry extraction",
        "qc_mode": "Python extracts template registry; Generation uses it. QC routes extraction failures, not style judgment.",
        "if_not_ok": "Generation/Template repairs template extraction inputs and reruns validation.",
    },
    "DECK_BLUEPRINT_MISSING_OR_FAILED": {
        "checkpoint": "Generation/page argument quality",
        "qc_mode": "Generation writes page arguments and slide drafts; QC reviews whether pages are thin, unsupported, or off-mission. Python validates fields and template compatibility.",
        "if_not_ok": "Generation repairs deck_blueprint; Reasoning/Research repair only if the root cause is unsupported judgment or missing evidence.",
    },
    "PAGE_EVIDENCE_CONTRACT_MISSING_OR_FAILED": {
        "checkpoint": "Compiled evidence contract",
        "qc_mode": "Python compiles and validates evidence bindings. QC routes unsupported claim issues back to Generation/Reasoning.",
        "if_not_ok": "Repair deck_blueprint or issue_analysis, then recompile.",
    },
    "RENDERER_SPEC_MISSING_OR_FAILED": {
        "checkpoint": "Renderer spec determinism",
        "qc_mode": "Python checks renderer data; QC routes content/evidence problems upstream when renderer errors reveal them.",
        "if_not_ok": "Repair deck_blueprint/template inputs and recompile.",
    },
    "TEMPLATE_PROFILE_MISSING_OR_FAILED": {
        "checkpoint": "Template analysis",
        "qc_mode": "Template role owns style/profile; Python analyzes deterministic template properties. QC routes missing profile or manual patch attempts.",
        "if_not_ok": "Template role reruns analyzer or fixes template input; do not hand-patch derived template_profile.",
    },
    "TEMPLATE_FIT_FAILED": {
        "checkpoint": "Template fit QC",
        "qc_mode": "Template role decides fit repairs without changing core judgment; QC routes whether the fix belongs to Template or Generation.",
        "if_not_ok": "Template adjusts fit/profile; Generation compresses/restructures only when content exceeds capacity.",
    },
    "CHART_METRIC_BINDING_FAILED": {
        "checkpoint": "Chart/evidence binding",
        "qc_mode": "Python checks MET bindings. QC routes missing/weak metrics to Knowledge/Reasoning/Generation.",
        "if_not_ok": "Fix metric reconciliation or chart intent upstream; do not fabricate chart-ready metrics.",
    },
    "CONTENT_QUALITY_FAILED": {
        "checkpoint": "Generation/content QC",
        "qc_mode": "QC interprets content-quality findings and assigns repair owner. Python reports density/source/evidence/text issues but does not decide pitch quality alone.",
        "if_not_ok": "Generation repairs page copy/layout; Reasoning repairs unsupported claims; Knowledge/Research repairs evidence gaps.",
    },
    "PRE_PPT_GATE_FAILED": {
        "checkpoint": "Pre-PPT aggregate QC",
        "qc_mode": "QC groups chart/content/template/source blockers before render.",
        "if_not_ok": "Repair upstream artifacts; do not render PPT to bypass the gate.",
    },
    "REPLACEMENT_DICT_MISSING_OR_FAILED": {
        "checkpoint": "Output token mapping",
        "qc_mode": "Output/Python owns deterministic token mapping. QC routes if mapping failure exposes upstream renderer/template issues.",
        "if_not_ok": "Rerun pipeline after upstream fix; do not hand-write replacement_dict.",
    },
    "FILLED_PPT_VALIDATION_FAILED": {
        "checkpoint": "Filled PPT validation",
        "qc_mode": "Output owns render defects. QC routes if the defect is actually template fit or renderer input.",
        "if_not_ok": "Repair renderer/template/output inputs and rerun pipeline.",
    },
    "FINAL_DELIVERY_NOT_READY": {
        "checkpoint": "Final QC",
        "qc_mode": "QC decides whether final blockers are content readiness, evidence limits, template defects, or output mechanics. Python checks package integrity/client_ready flags.",
        "if_not_ok": "Route to the smallest upstream owner; do not report a PPT as complete.",
    },
}


COMMAND_TEMPLATES_BY_STAGE: dict[str, list[dict[str, str]]] = {
    "INPUT_CARD_MISSING": [
        {
            "purpose": "required: register materials and capture readable content before input-card transcription; captured text is not evidence-ready until LLM fact extraction",
            "command": (
                f"{PYTHON_COMMAND_TEMPLATE} scripts/ingest_materials.py "
                "--brief-text '<paste exact user brief or omit if using files/URLs>' "
                "--file '<path/to/file1>' --file '<path/to/file2>' "
                "--url '<https://source1>' --url '<https://source2>' "
                "--output-manifest {{run_dir}}/artifacts/material_manifest.json "
                "--output-extracts {{run_dir}}/artifacts/material_extracts.json "
                "--output-source-classification {{run_dir}}/artifacts/source_classification.json"
            ),
        },
        {
            "purpose": "validate intake artifacts before transcribing input card",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/validate_material_manifest.py --material-manifest {{run_dir}}/artifacts/material_manifest.json --output {{run_dir}}/artifacts/material_manifest_validation.json",
        },
        {
            "purpose": "validate input card after transcription-only creation",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/validate_input_card.py --input-card {{run_dir}}/input_card.json --output {{run_dir}}/artifacts/input_card_validation.json",
        },
    ],
    "INDUSTRY_SCOPE_PACK_MISSING": [
        {
            "purpose": "create industry_scope_pack.json as a scoping artifact only; do not run Python format validation until QC LLM has reviewed boundary quality",
            "command": "LLM task: industry-scoping writes {run_dir}/artifacts/industry_scope_pack.json from input_card and captured materials; no market-size/growth/share/valuation/page claims.",
        },
    ],
    "INDUSTRY_BOUNDARY_QC_REQUIRED": [
        {
            "purpose": "required: QC LLM reviews industry boundary quality and uses boundary-validation search/sources as needed; write pass/needs_boundary_validation/needs_scope_repair into industry_boundary_qc.json",
            "command": (
                "LLM task: QC reads {run_dir}/input_card.json, {run_dir}/artifacts/material_extracts.json, "
                "{run_dir}/artifacts/industry_scope_pack.json; performs boundary validation search when needed; "
                "writes {run_dir}/artifacts/industry_boundary_qc.json with decision, rationale, feedback, and any boundary_validation_requests."
            ),
        },
        {
            "purpose": "if QC decision is needs_boundary_validation, convert QC requests into boundary research request artifact",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/build_boundary_research_requests.py --boundary-qc {{run_dir}}/artifacts/industry_boundary_qc.json --output {{run_dir}}/artifacts/boundary_research_requests.json",
        },
    ],
    "INDUSTRY_SCOPE_FORMAT_MISSING_OR_FAILED": [
        {
            "purpose": "QC has passed boundary quality; now run deterministic format/red-line validation on scope pack",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/validate_industry_scope_pack.py --scope-pack {{run_dir}}/artifacts/industry_scope_pack.json --output {{run_dir}}/artifacts/industry_scope_pack_validation.json",
        },
    ],
    "FORMAL_SEARCH_PLAN_MISSING": [
        {
            "purpose": "export searchable coverage map and executable search batch for downstream planning and repair traceability",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/build_formal_search_plan_skeleton.py --input-card {{run_dir}}/input_card.json --scope-pack {{run_dir}}/artifacts/industry_scope_pack.json --output {{run_dir}}/artifacts/formal_search_plan.json --coverage-map {{run_dir}}/artifacts/coverage_map.json --search-batch {{run_dir}}/artifacts/search_batch.json",
        },
        {
            "purpose": "validate formal search plan after editing executable queries",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/validate_formal_search_plan.py --formal-search-plan {{run_dir}}/artifacts/formal_search_plan.json --output {{run_dir}}/artifacts/formal_search_plan_validation.json",
        },
    ],
    "FORMAL_RESEARCH_EXECUTION_MISSING_OR_FAILED": [
        {
            "purpose": "rebuild planned-vs-actual execution accounting from plan/log/reviews; include unexecuted FS rows explicitly",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/build_formal_research_execution_report_skeleton.py --formal-search-plan {{run_dir}}/artifacts/formal_search_plan.json --search-log {{run_dir}}/artifacts/search_log.md --source-reviews {{run_dir}}/artifacts/source_reviews.json --include-unexecuted --output {{run_dir}}/artifacts/formal_research_execution_report.json --coverage-accounting {{run_dir}}/artifacts/coverage_accounting.json",
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
            "command": (
                f"{PYTHON_COMMAND_TEMPLATE} scripts/repository_retrieve.py --max-results 200 --output {{run_dir}}/artifacts/repository_retrieval.json "
                f"&& {PYTHON_COMMAND_TEMPLATE} scripts/build_research_evidence_db.py --input-card {{run_dir}}/input_card.json --scope-pack {{run_dir}}/artifacts/industry_scope_pack.json --formal-search-plan {{run_dir}}/artifacts/formal_search_plan.json --formal-research-execution-report {{run_dir}}/artifacts/formal_research_execution_report.json --source-reviews {{run_dir}}/artifacts/source_reviews.json --material-manifest {{run_dir}}/artifacts/material_manifest.json --material-extracts {{run_dir}}/artifacts/material_extracts.json --repository-sources {{run_dir}}/artifacts/repository_retrieval.json --output {{run_dir}}/artifacts/research_evidence_db.json"
            ),
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
        {
            "purpose": "optional: build hypothesis store for unresolved/directional reasoning",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/build_hypothesis_store_skeleton.py --issue-analysis {{run_dir}}/industry_issue_analysis.json --research-evidence-db {{run_dir}}/artifacts/research_evidence_db.json --output {{run_dir}}/artifacts/hypothesis_store.json",
        },
        {
            "purpose": "optional: build public research request queue from unresolved hypotheses",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/build_research_request_queue.py --hypothesis-store {{run_dir}}/artifacts/hypothesis_store.json --output {{run_dir}}/artifacts/research_request_queue.json",
        },
        {
            "purpose": "optional: validate research request queue before promotion",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/validate_research_request_queue.py --research-request-queue {{run_dir}}/artifacts/research_request_queue.json --output {{run_dir}}/artifacts/research_request_queue_validation.json",
        },
        {
            "purpose": "optional: promote unresolved research requests into formal search plan rows before downstream planning",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/promote_research_requests.py --research-request-queue {{run_dir}}/artifacts/research_request_queue.json --formal-search-plan {{run_dir}}/artifacts/formal_search_plan.json --output {{run_dir}}/artifacts/formal_search_plan.json --incremental-search-plan {{run_dir}}/artifacts/incremental_search_plan.json",
        },
        {
            "purpose": "optional: re-validate formal search plan after promotion rows are appended",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/validate_formal_search_plan.py --formal-search-plan {{run_dir}}/artifacts/formal_search_plan.json --output {{run_dir}}/artifacts/formal_search_plan_validation.json",
        },
        {
            "purpose": "optional: build page argument pack from issue analysis and resolved hypotheses",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/build_page_argument_pack.py --issue-analysis {{run_dir}}/industry_issue_analysis.json --hypothesis-store {{run_dir}}/artifacts/hypothesis_store.json --output {{run_dir}}/artifacts/page_argument_pack.json",
        },
        {
            "purpose": "optional: validate page argument pack before deck blueprint writing",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/validate_page_argument_pack.py --page-argument-pack {{run_dir}}/artifacts/page_argument_pack.json --output {{run_dir}}/artifacts/page_argument_pack_validation.json",
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
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/validate_deck_blueprint.py --deck-blueprint {{run_dir}}/deck_blueprint.json --issue-analysis {{run_dir}}/industry_issue_analysis.json --template-registry {{run_dir}}/template_registry.json --layout-budget templates/layout_budget.json --output {{run_dir}}/artifacts/deck_blueprint_validation.json",
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
    "TEMPLATE_PROFILE_MISSING_OR_FAILED": [
        {
            "purpose": "analyze template and generate run-level template profile",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/template_analyzer.py --template assets/industry_section_template_master.pptx --layout-config templates/layout_config.json --output {{run_dir}}/artifacts/template_profile.json",
        },
        {
            "purpose": "rerun pre-PPT validation after template profile is generated",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/pipeline.py validate-pre-ppt --run-dir {{run_dir}}",
        },
        {
            "purpose": "rerun full formal render pipeline after template profile refresh",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/pipeline.py render --run-dir {{run_dir}}",
        },
    ],
    "TEMPLATE_FIT_FAILED": [
        {
            "purpose": "run template fit checks against latest renderer spec and template profile",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/template_fit.py --renderer-spec {{run_dir}}/renderer_spec.json --template-profile {{run_dir}}/artifacts/template_profile.json --output {{run_dir}}/artifacts/template_fit_validation.json --fit-plan-output {{run_dir}}/artifacts/template_fit_plan.json",
        },
        {
            "purpose": "rerun pre-PPT stage gate after template fit refresh",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/pipeline.py validate-pre-ppt --run-dir {{run_dir}}",
        },
        {
            "purpose": "rerun formal render after template fit refresh",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/pipeline.py render --run-dir {{run_dir}}",
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
    mission_state = dict(state.get("mission_state") or {}) if isinstance(state.get("mission_state"), dict) else {}
    mission_state.update(
        {
            "current_stage": state["current_stage"],
            "current_phase": state["current_stage"],
            "current_evidence_stage": state["current_stage"],
            "status": state["status"],
            "blocking_gate": state["blocking_gate"],
            "owner_role": state.get("owner_role", "orchestrator"),
        }
    )
    payload = {
        "schema_version": "workflow_next_v1",
        "run_dir": state["run_dir"],
        "current_mission": state.get("current_mission") or mission_state.get("current_mission", ""),
        "current_phase": state.get("current_stage", ""),
        "source_run_dir": state.get("source_run_dir", ""),
        "output_run_dir": state.get("output_run_dir", state["run_dir"]),
        "package_of_record": state.get("package_of_record", state["run_dir"]),
        "current_stage": state["current_stage"],
        "owner_role": state.get("owner_role", "orchestrator"),
        "owner_skill": state.get("owner_skill", ""),
        "repair_target_role": state.get("repair_target_role", state.get("owner_role", "orchestrator")),
        "status": state["status"],
        "blocking_gate": state["blocking_gate"],
        "input_artifacts": state.get("input_artifacts", []),
        "output_artifacts": state.get("output_artifacts", []),
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
        "mission_state": mission_state,
        "evidence_readiness": state.get("evidence_readiness", {}),
        "handoff_packet_targets": [
            "artifacts/handoff_material_to_scoping.json",
            "artifacts/handoff_scoping_to_research.json",
            "artifacts/handoff_research_to_reasoning.json",
            "artifacts/handoff_reasoning_to_generation.json",
            "artifacts/handoff_generation_to_template.json",
            "artifacts/handoff_template_to_output.json",
        ],
        "failure_memory_tail": state.get("failure_memory_tail", []),
        "message": state["message"],
    }
    payload["qc_protocol"] = GLOBAL_QC_PROTOCOL
    payload["current_qc_policy"] = QC_POLICY_BY_STAGE.get(
        state["current_stage"],
        {
            "checkpoint": state["current_stage"],
            "qc_mode": "Use workflow state and QC role to route warnings/failures; Python validators do not replace LLM quality judgment.",
            "if_not_ok": "Repair the current owner artifact, rerun the same check, then return to workflow.py next.",
        },
    )
    if state.get("owner_skill"):
        payload["role_routing"] = {
            "read_this_role_skill_before_repairing": state["owner_skill"],
            "do_not_bulk_read_unrelated_role_skills": True,
        }
    payload["qc_router_command"] = f"{PYTHON_COMMAND_TEMPLATE} scripts/qc_router.py --run-dir {run_dir} --output {run_dir}/artifacts/qc_router_report.json"
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
