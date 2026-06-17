#!/usr/bin/env python3
"""State dashboard for an IB industry-section run directory.

This script reports observable facts, candidate commands, and downstream risks.
It is not a workflow controller. The main LLM agent remains the engagement lead:
it decides owner routing, whether a warning is acceptable, and whether the
current evidence can support a pre-mandate client pitch.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
LIB_DIR = ROOT_DIR / "scripts" / "_lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))
QC_SYSTEM_VALIDATORS = ROOT_DIR / "scripts" / "qc" / "validators" / "system"
if str(QC_SYSTEM_VALIDATORS) not in sys.path:
    sys.path.insert(0, str(QC_SYSTEM_VALIDATORS))

from validate_run_state import validate_run_state

PYTHON_COMMAND_TEMPLATE = sys.executable


def _validate_state(run_dir: Path, *, write_state: bool = False) -> dict[str, Any]:
    try:
        return validate_run_state(run_dir, write_mission_state=write_state)
    except TypeError as exc:
        # Contract tests and older host integrations may monkeypatch
        # validate_run_state(run_dir). Preserve compatibility while production
        # calls remain explicit about state writes.
        if "write_mission_state" not in str(exc):
            raise
        return validate_run_state(run_dir)


def _load_script_entrypoint_map() -> dict[str, str]:
    path = ROOT_DIR / "configs" / "script_role_map.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        str(script): str(entrypoint)
        for script, entrypoint in payload.items()
        if str(script).endswith(".py") and str(entrypoint).strip()
    }


SCRIPT_ENTRYPOINT_BY_NAME = _load_script_entrypoint_map()

DETERMINISTIC_REBUILD_STAGES = {
    "SOURCE_ARCHIVE_MISSING_OR_FAILED",
    "FORMAL_RESEARCH_EXECUTION_MISSING_OR_FAILED",
    "PRE_RESEARCH_PACK_GATE_FAILED",
    "RESEARCH_PACK_MISSING_OR_FAILED",
    "PAGE_EVIDENCE_CONTRACT_MISSING_OR_FAILED",
    "RENDERER_SPEC_MISSING_OR_FAILED",
    "TEMPLATE_PROFILE_MISSING_OR_FAILED",
    "TEMPLATE_FIT_FAILED",
    "CHART_METRIC_BINDING_FAILED",
    "CONTENT_QUALITY_FAILED",
    "PRE_PPT_GATE_FAILED",
}


def _prefer_role_local_entrypoints(command: str) -> str:
    """Rewrite suggested CLI entrypoints to indexed role/QC-local paths."""
    rewritten = command
    for script_name, entrypoint in sorted(SCRIPT_ENTRYPOINT_BY_NAME.items(), key=lambda item: len(item[0]), reverse=True):
        if entrypoint in rewritten:
            continue
        rewritten = rewritten.replace(
            f"scripts/{script_name}",
            entrypoint,
        )
    return _make_runtime_paths_absolute(rewritten)


def _make_runtime_paths_absolute(command: str) -> str:
    """Return commands that work outside the skill runtime cwd."""
    preserved_source_registry = "__IB_SOURCE_REGISTRY_RELATIVE__"
    command = command.replace(" configs/source_registry.json", f" {preserved_source_registry}")
    replacements = {
        " scripts/": f" {ROOT_DIR}/scripts/",
        " configs/": f" {ROOT_DIR}/configs/",
        " assets/": f" {ROOT_DIR}/assets/",
    }
    rewritten = command
    for needle, replacement in replacements.items():
        rewritten = rewritten.replace(needle, replacement)
    return rewritten.replace(preserved_source_registry, "configs/source_registry.json")


def _pipeline_rebuild_command(run_dir: str) -> dict[str, str]:
    return {
        "purpose": "shortest deterministic repair: rebuild current stale derived artifacts without hand-editing downstream files",
        "command": _make_runtime_paths_absolute(f"{PYTHON_COMMAND_TEMPLATE} scripts/pipeline.py rebuild-stale --run-dir {run_dir}"),
    }


GLOBAL_QC_PROTOCOL: dict[str, Any] = {
    "principle": "LLM QC judges quality and routes repairs; Python checks deterministic structure, provenance, stale state, and renderability.",
    "no_qc_validator_loop": True,
    "main_agent_receives_script_output_first": True,
    "default_rules": [
        "If an LLM QC decision is not pass, route repair to the owner role before relying on downstream Python format validators.",
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
    "SOURCE_ARCHIVE_MISSING_OR_FAILED": {
        "checkpoint": "Source archive integrity",
        "qc_mode": "Research archives actual searched/manual sources before evidence extraction. Source usability is reviewed inside research_evidence_db.",
        "if_not_ok": "Research repairs search_log selected URLs or archive inputs and reruns archive validation.",
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
        "if_not_ok": "Fix research_evidence_db or upstream source archive/execution accounting, re-export, rerun validation.",
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
    "MATERIAL_INTAKE_MISSING_OR_FAILED": [
        {
            "purpose": "lowest-friction start for a plain brief: register materials, save exact brief text, create input_card.json, and mark the brief as transcribed-not-evidence",
            "command": (
                f"{PYTHON_COMMAND_TEMPLATE} scripts/start_case_from_brief.py "
                "--case-name '<case_name>' --run-dir {{run_dir}} "
                "--brief-text '<paste exact user brief>' "
                "--template-file '<optional user PPT/POTX template path>'"
            ),
        },
        {
            "purpose": "advanced intake: register multiple files/URLs/templates and capture readable content before input-card transcription",
            "command": (
                f"{PYTHON_COMMAND_TEMPLATE} scripts/material-intake/ingest_materials.py "
                "--brief-text '<paste exact user brief or omit if using files/URLs>' "
                "--file '<path/to/file1>' --file '<path/to/file2>' "
                "--template-file '<optional user PPT/POTX template path>' "
                "--url '<https://source1>' --url '<https://source2>' "
                f"--output-manifest {{run_dir}}/artifacts/material_manifest.json "
                f"--output-extracts {{run_dir}}/artifacts/material_extracts.json "
                f"--output-source-classification {{run_dir}}/artifacts/source_classification.json"
            ),
        },
        {
            "purpose": "validate material manifest after registration",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/qc/validators/material/validate_material_manifest.py --material-manifest {{run_dir}}/artifacts/material_manifest.json --output {{run_dir}}/artifacts/material_manifest_validation.json",
        },
        {
            "purpose": "validate material extracts after Material/Knowledge has completed fact/metric extraction, not immediately after raw text capture",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/qc/validators/material/validate_material_extracts.py --material-extracts {{run_dir}}/artifacts/material_extracts.json --material-manifest {{run_dir}}/artifacts/material_manifest.json --output {{run_dir}}/artifacts/material_extracts_validation.json",
        },
    ],
    "INPUT_CARD_MISSING": [
        {
            "purpose": "lowest-friction start for a plain brief: register materials, save exact brief text, create input_card.json, and mark the brief as transcribed-not-evidence",
            "command": (
                f"{PYTHON_COMMAND_TEMPLATE} scripts/start_case_from_brief.py "
                "--case-name '<case_name>' --run-dir {{run_dir}} "
                "--brief-text '<paste exact user brief>' "
                "--template-file '<optional user PPT/POTX template path>'"
            ),
        },
        {
            "purpose": "advanced intake: register multiple files/URLs/templates and capture readable content before input-card transcription",
            "command": (
                f"{PYTHON_COMMAND_TEMPLATE} scripts/material-intake/ingest_materials.py "
                "--brief-text '<paste exact user brief or omit if using files/URLs>' "
                "--file '<path/to/file1>' --file '<path/to/file2>' "
                "--template-file '<optional user PPT/POTX template path>' "
                "--url '<https://source1>' --url '<https://source2>' "
                f"--output-manifest {{run_dir}}/artifacts/material_manifest.json "
                f"--output-extracts {{run_dir}}/artifacts/material_extracts.json "
                f"--output-source-classification {{run_dir}}/artifacts/source_classification.json"
            ),
        },
        {
            "purpose": "validate intake artifacts before transcribing input card",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/qc/validators/material/validate_material_manifest.py --material-manifest {{run_dir}}/artifacts/material_manifest.json --output {{run_dir}}/artifacts/material_manifest_validation.json",
        },
        {
            "purpose": "validate input card after transcription-only creation",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/qc/validators/material/validate_input_card.py --input-card {{run_dir}}/input_card.json --output {{run_dir}}/artifacts/input_card_validation.json",
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
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/industry-scoping/build_boundary_research_requests.py --boundary-qc {{run_dir}}/artifacts/industry_boundary_qc.json --output {{run_dir}}/artifacts/boundary_research_requests.json",
        },
    ],
    "INDUSTRY_SCOPE_FORMAT_MISSING_OR_FAILED": [
        {
            "purpose": "QC has passed boundary quality; now run deterministic format/red-line validation on scope pack",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/qc/validators/scoping/validate_industry_scope_pack.py --scope-pack {{run_dir}}/artifacts/industry_scope_pack.json --output {{run_dir}}/artifacts/industry_scope_pack_validation.json",
        },
    ],
    "FORMAL_SEARCH_PLAN_MISSING": [
        {
            "purpose": "export searchable coverage map and executable search batch for downstream planning and repair traceability",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/research-external-evidence/build_formal_search_plan_skeleton.py --input-card {{run_dir}}/input_card.json --scope-pack {{run_dir}}/artifacts/industry_scope_pack.json --output {{run_dir}}/artifacts/formal_search_plan.json --coverage-map {{run_dir}}/artifacts/coverage_map.json --search-batch {{run_dir}}/artifacts/search_batch.json",
        },
        {
            "purpose": "validate formal search plan after editing executable queries",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/qc/validators/research/validate_formal_search_plan.py --formal-search-plan {{run_dir}}/artifacts/formal_search_plan.json --output {{run_dir}}/artifacts/formal_search_plan_validation.json",
        },
    ],
    "FORMAL_RESEARCH_EXECUTION_MISSING_OR_FAILED": [
        {
            "purpose": "rebuild planned-vs-actual execution accounting from plan/log/archive; include unexecuted FS rows explicitly",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/research-external-evidence/build_formal_research_execution_report_skeleton.py --formal-search-plan {{run_dir}}/artifacts/formal_search_plan.json --search-log {{run_dir}}/artifacts/search_log.md --source-archive-index {{run_dir}}/artifacts/source_archive/source_archive_index.json --include-unexecuted --output {{run_dir}}/artifacts/formal_research_execution_report.json --coverage-accounting {{run_dir}}/artifacts/coverage_accounting.json",
        },
        {
            "purpose": "validate formal research execution accounting; planned FS rows without actual S-xxx attempts must be marked not_executed/not_material/accounting_only, not faked",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/qc/validators/research/validate_formal_research_execution.py --report {{run_dir}}/artifacts/formal_research_execution_report.json --formal-search-plan {{run_dir}}/artifacts/formal_search_plan.json --search-log {{run_dir}}/artifacts/search_log.md --output {{run_dir}}/artifacts/formal_research_execution_validation.json",
        },
    ],
    "SOURCE_ARCHIVE_MISSING_OR_FAILED": [
        {
            "purpose": "build source archive directly from actual search log selected/opened sources",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/research-external-evidence/build_source_archive.py --search-log {{run_dir}}/artifacts/search_log.md --run-dir {{run_dir}} --overwrite",
        },
        {
            "purpose": "validate source archive integrity",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/qc/validators/research/validate_source_archive.py --source-archive-index {{run_dir}}/artifacts/source_archive/source_archive_index.json --run-dir {{run_dir}} --output {{run_dir}}/artifacts/source_archive_validation.json",
        },
        {
            "purpose": "append each real formal search attempt before archive; S-xxx IDs are only for actual searches, never for unexecuted FS rows",
            "command": (
                f"{PYTHON_COMMAND_TEMPLATE} scripts/research-external-evidence/search_log.py append --search-log {{run_dir}}/artifacts/search_log.md "
                "--query '<exact query searched>' --stage formal_research_execution --fs-id FS-001 --selected-source '<exact reviewed URL>' "
                "--opened-reviewed yes --locator-excerpt '<page/section/table and short excerpt or limitation>'"
            ),
        },
        {
            "purpose": "if an accidental S-xxx row was appended, delete it mechanically instead of hand-editing markdown",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/research-external-evidence/search_log.py edit --search-log {{run_dir}}/artifacts/search_log.md --attempt-id S-023 --delete",
        },
        {
            "purpose": "if a known search-log field is wrong or blank, update only that field mechanically",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/research-external-evidence/search_log.py edit --search-log {{run_dir}}/artifacts/search_log.md --attempt-id S-001 --set-field 'Result Count=5'",
        },
    ],
    "PRE_RESEARCH_PACK_GATE_FAILED": [
        {
            "purpose": "refresh the pre-research deterministic gate through the pipeline facade instead of calling raw gate scripts",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/pipeline.py rebuild-stale --run-dir {{run_dir}}",
        },
    ],
    "RESEARCH_EVIDENCE_DB_MISSING_OR_FAILED": [
        {
            "purpose": "build research evidence database skeleton from archived formal sources; source reviews are embedded in the DB for LLM/QC judgment",
            "command": (
                f"{PYTHON_COMMAND_TEMPLATE} scripts/knowledge-repository/repository.py retrieve --max-results 200 --output {{run_dir}}/artifacts/repository_retrieval.json "
                f"&& {PYTHON_COMMAND_TEMPLATE} scripts/knowledge-repository/build_research_evidence_db.py --input-card {{run_dir}}/input_card.json --scope-pack {{run_dir}}/artifacts/industry_scope_pack.json --formal-search-plan {{run_dir}}/artifacts/formal_search_plan.json --formal-research-execution-report {{run_dir}}/artifacts/formal_research_execution_report.json --source-archive-index {{run_dir}}/artifacts/source_archive/source_archive_index.json --material-manifest {{run_dir}}/artifacts/material_manifest.json --material-extracts {{run_dir}}/artifacts/material_extracts.json --repository-sources {{run_dir}}/artifacts/repository_retrieval.json --output {{run_dir}}/artifacts/research_evidence_db.json"
            ),
        },
        {
            "purpose": "validate research evidence database after LLM fills extracts/EV/MET/inventory fields",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/qc/validators/knowledge/validate_research_evidence_db.py --research-evidence-db {{run_dir}}/artifacts/research_evidence_db.json --output {{run_dir}}/artifacts/research_evidence_db_validation.json",
        },
    ],
    "RESEARCH_PACK_MISSING_OR_FAILED": [
        {
            "purpose": "export readable research pack from research evidence database",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/knowledge-repository/export_research_pack_from_db.py --research-evidence-db {{run_dir}}/artifacts/research_evidence_db.json --output {{run_dir}}/industry_research_pack.md",
        },
        {
            "purpose": "validate generated research evidence pack",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/qc/validators/knowledge/validate_research_pack.py --research-pack {{run_dir}}/industry_research_pack.md --run-dir {{run_dir}} --source-registry {ROOT_DIR}/configs/source_registry.json --output {{run_dir}}/artifacts/research_pack_validation.json",
        },
    ],
    "ISSUE_ANALYSIS_MISSING_OR_FAILED": [
        {
            "purpose": "build issue analysis skeleton from research-pack inventory",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/reasoning/build_issue_analysis_skeleton.py --research-evidence-db {{run_dir}}/artifacts/research_evidence_db.json --formal-research-execution-report {{run_dir}}/artifacts/formal_research_execution_report.json --output {{run_dir}}/industry_issue_analysis.json",
        },
        {
            "purpose": "validate issue analysis after replacing skeleton placeholders with substantive analysis",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/qc/validators/reasoning/validate_issue_analysis.py --issue-analysis {{run_dir}}/industry_issue_analysis.json --research-pack {{run_dir}}/industry_research_pack.md --output {{run_dir}}/artifacts/issue_analysis_validation.json",
        },
        {
            "purpose": "optional: build hypothesis store for unresolved/directional reasoning",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/reasoning/build_hypothesis_store_skeleton.py --issue-analysis {{run_dir}}/industry_issue_analysis.json --research-evidence-db {{run_dir}}/artifacts/research_evidence_db.json --output {{run_dir}}/artifacts/hypothesis_store.json",
        },
        {
            "purpose": "optional: build public research request queue from unresolved hypotheses",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/reasoning/build_research_request_queue.py --hypothesis-store {{run_dir}}/artifacts/hypothesis_store.json --output {{run_dir}}/artifacts/research_request_queue.json",
        },
        {
            "purpose": "optional: validate research request queue before promotion",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/qc/validators/reasoning/validate_research_request_queue.py --research-request-queue {{run_dir}}/artifacts/research_request_queue.json --output {{run_dir}}/artifacts/research_request_queue_validation.json",
        },
        {
            "purpose": "optional: promote unresolved research requests into formal search plan rows before downstream planning",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/reasoning/promote_research_requests.py --research-request-queue {{run_dir}}/artifacts/research_request_queue.json --formal-search-plan {{run_dir}}/artifacts/formal_search_plan.json --output {{run_dir}}/artifacts/formal_search_plan.json --incremental-search-plan {{run_dir}}/artifacts/incremental_search_plan.json",
        },
        {
            "purpose": "optional: re-validate formal search plan after promotion rows are appended",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/qc/validators/research/validate_formal_search_plan.py --formal-search-plan {{run_dir}}/artifacts/formal_search_plan.json --output {{run_dir}}/artifacts/formal_search_plan_validation.json",
        },
        {
            "purpose": "optional: build page argument pack from issue analysis and resolved hypotheses",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/reasoning/build_page_argument_pack.py --issue-analysis {{run_dir}}/industry_issue_analysis.json --hypothesis-store {{run_dir}}/artifacts/hypothesis_store.json --output {{run_dir}}/artifacts/page_argument_pack.json",
        },
        {
            "purpose": "optional: validate page argument pack before deck blueprint writing",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/qc/validators/reasoning/validate_page_argument_pack.py --page-argument-pack {{run_dir}}/artifacts/page_argument_pack.json --output {{run_dir}}/artifacts/page_argument_pack_validation.json",
        },
    ],
    "TEMPLATE_REGISTRY_MISSING_OR_FAILED": [
        {
            "purpose": "select the effective template before registry/template work",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/template/select_template.py --run-dir {{run_dir}} --output {{run_dir}}/artifacts/template_selection.json",
        },
        {
            "purpose": "extract template registry",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/template/extract_template_registry.py --output {{run_dir}}/template_registry.json",
        },
        {
            "purpose": "validate template registry",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/qc/validators/template/validate_template_registry.py --template-registry {{run_dir}}/template_registry.json --slide-registry configs/slide_registry.json --output {{run_dir}}/artifacts/template_registry_validation.json",
        },
    ],
    "DECK_BLUEPRINT_MISSING_OR_FAILED": [
        {
            "purpose": "validate deck blueprint after page-editor repair",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/qc/validators/generation/validate_deck_blueprint.py --deck-blueprint {{run_dir}}/deck_blueprint.json --issue-analysis {{run_dir}}/industry_issue_analysis.json --template-registry {{run_dir}}/template_registry.json --layout-budget configs/layout_budget.json --output {{run_dir}}/artifacts/deck_blueprint_validation.json",
        },
    ],
    "PAGE_EVIDENCE_CONTRACT_MISSING_OR_FAILED": [
        {
            "purpose": "compile blueprint into deterministic downstream artifacts",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/generation/compile_deck_blueprint.py --issue-analysis {{run_dir}}/industry_issue_analysis.json --deck-blueprint {{run_dir}}/deck_blueprint.json --template-registry {{run_dir}}/template_registry.json --page-contract-output {{run_dir}}/page_evidence_contract.json --renderer-spec-output {{run_dir}}/renderer_spec.json",
        },
    ],
    "RENDERER_SPEC_MISSING_OR_FAILED": [
        {
            "purpose": "recompile renderer spec from repaired deck blueprint",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/generation/compile_deck_blueprint.py --issue-analysis {{run_dir}}/industry_issue_analysis.json --deck-blueprint {{run_dir}}/deck_blueprint.json --template-registry {{run_dir}}/template_registry.json --page-contract-output {{run_dir}}/page_evidence_contract.json --renderer-spec-output {{run_dir}}/renderer_spec.json",
        },
    ],
    "TEMPLATE_PROFILE_MISSING_OR_FAILED": [
        {
            "purpose": "select user-provided template if registered; otherwise record bundled default",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/template/select_template.py --run-dir {{run_dir}} --output {{run_dir}}/artifacts/template_selection.json",
        },
        {
            "purpose": "analyze template and generate run-level template profile",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/template/template_analyzer.py --template-selection {{run_dir}}/artifacts/template_selection.json --layout-config configs/layout_config.json --output {{run_dir}}/artifacts/template_profile.json",
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
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/template/template_fit.py --renderer-spec {{run_dir}}/renderer_spec.json --template-profile {{run_dir}}/artifacts/template_profile.json --output {{run_dir}}/artifacts/template_fit_validation.json --fit-plan-output {{run_dir}}/artifacts/template_fit_plan.json",
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
            "purpose": "refresh chart/content/pre-PPT deterministic checks through the pipeline facade after Generation/Reasoning repairs",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/pipeline.py rebuild-stale --run-dir {{run_dir}}",
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
        "command": _prefer_role_local_entrypoints(item["command"].format(run_dir=run_dir)),
    }


def recommended_commands(state: dict[str, Any]) -> list[dict[str, str]]:
    """Return concrete suggested commands for common gate states."""
    stage = state["current_stage"]
    run_dir = str(state["run_dir"])
    return [_render_command_template(item, run_dir=run_dir) for item in COMMAND_TEMPLATES_BY_STAGE.get(stage, [])]


def _public_state_payload(state: dict[str, Any], *, schema_version: str) -> dict[str, Any]:
    payload = dict(state)
    payload["schema_version"] = schema_version
    if "allowed_next_actions" in payload:
        payload["candidate_next_actions"] = payload.pop("allowed_next_actions")
    if "forbidden_actions" in payload:
        payload["downstream_risks"] = payload.pop("forbidden_actions")
    payload.setdefault("state_report_role", "dashboard_not_driver")
    payload.setdefault("agent_driven_policy", {
        "script_authority": "observed_state_only",
        "main_agent_is_driver": True,
    })
    return payload


def status_payload(run_dir: Path, *, write_state: bool = False) -> dict[str, Any]:
    return _public_state_payload(
        _validate_state(run_dir, write_state=write_state),
        schema_version="state_status_v1",
    )


def next_payload(run_dir: Path, *, write_state: bool = False) -> dict[str, Any]:
    state = _validate_state(run_dir, write_state=write_state)
    next_commands = dedupe_commands(recommended_commands(state))
    run_dir_str = str(state["run_dir"])
    deterministic_rebuild_available = (
        state.get("status") in {"failed", "stale"}
        and state.get("current_stage") in DETERMINISTIC_REBUILD_STAGES
    )
    deterministic_rebuild_command = _pipeline_rebuild_command(run_dir_str)
    if deterministic_rebuild_available:
        next_commands = dedupe_commands([deterministic_rebuild_command] + next_commands)
    blocking_risks: list[str] = []
    if state.get("missing_artifacts"):
        blocking_risks.append("missing_artifacts")
    if state.get("failed_validations"):
        blocking_risks.append("failed_validations")
    if state.get("stale_validations"):
        blocking_risks.append("stale_validations")
    if state.get("debug_only"):
        blocking_risks.append("debug_output_only")
    if state.get("draft_only"):
        blocking_risks.append("draft_not_client_ready")
    if state.get("final_delivery_valid") is False and state.get("current_stage") in {
        "FINAL_DELIVERY_NOT_READY",
        "STOP_AND_REPORT",
    }:
        blocking_risks.append("final_delivery_not_client_ready")
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
        "schema_version": "state_report_v1",
        "state_report_role": "dashboard_not_driver",
        "agent_driven_policy": {
            "script_authority": "observed_state_and_suggested_actions_only",
            "main_agent_is_driver": True,
            "validator_pass_is_not_pitch_quality_pass": True,
            "must_use_engagement_judgment": True,
            "do_not_say_state_report_told_me_to_continue": True,
            "use_gate_report_for_multi_issue_triage": True,
        },
        "run_dir": state["run_dir"],
        "current_mission": state.get("current_mission") or mission_state.get("current_mission", ""),
        "current_phase": state.get("current_stage", ""),
        "source_run_dir": state.get("source_run_dir", ""),
        "output_run_dir": state.get("output_run_dir", state["run_dir"]),
        "package_of_record": state.get("package_of_record", state["run_dir"]),
        "current_stage": state["current_stage"],
        "observed_state": {
            "stage": state["current_stage"],
            "status": state["status"],
            "blocking_gate": state["blocking_gate"],
            "missing_artifacts": state.get("missing_artifacts", []),
            "failed_validations": state.get("failed_validations", []),
            "stale_validations": state.get("stale_validations", []),
            "debug_only": state.get("debug_only", False),
            "draft_only": state.get("draft_only", False),
            "final_delivery_valid": state.get("final_delivery_valid", False),
        },
        "owner_role": state.get("owner_role", "orchestrator"),
        "recommended_role": state.get("owner_role", "orchestrator"),
        "owner_skill": state.get("owner_skill", ""),
        "repair_target_role": state.get("repair_target_role", state.get("owner_role", "orchestrator")),
        "status": state["status"],
        "blocking_gate": state["blocking_gate"],
        "blocking_risks": blocking_risks,
        "input_artifacts": state.get("input_artifacts", []),
        "output_artifacts": state.get("output_artifacts", []),
        "missing_artifacts": state.get("missing_artifacts", []),
        "failed_validations": state.get("failed_validations", []),
        "stale_validations": state.get("stale_validations", []),
        "retry_state": state.get("retry_state", {}),
        "candidate_next_actions": state["allowed_next_actions"],
        "recommended_next_command": next_commands[0]["command"] if next_commands else "",
        "recommended_next_commands": next_commands,
        "suggested_next_actions": next_commands,
        "shortest_repair_path": {
            "available": bool(deterministic_rebuild_available),
            "why": (
                "current blocker is a stale deterministic artifact chain"
                if deterministic_rebuild_available and state.get("status") == "stale"
                else "current blocker is a deterministic aggregate check that can be refreshed from upstream artifacts"
                if deterministic_rebuild_available
                else "current blocker needs owner-role judgment/authoring or is not stale"
            ),
            "command": deterministic_rebuild_command["command"] if deterministic_rebuild_available else "",
            "do_not": [
                "Avoid hand-editing validation artifacts.",
                "Avoid patching derived artifacts when a deterministic rebuild command exists.",
                "Use owner-role judgment before relying on downstream output.",
            ],
        },
        "render_policy": {
            "mode": "formal_pipeline_only",
            "reason": "Render only through formal pipeline after required upstream artifacts are ready.",
            "do_not": "Do not create ad-hoc render_deck.py files or render from page_argument_pack.json.",
        },
        "orchestrator_decision_required": {
            "required": True,
            "decision_prompt": (
                "Before acting, decide whether the real root cause is material, knowledge, "
                "scoping, research, reasoning, generation, template, output, QC, or engagement-context mismatch."
            ),
            "may_override_recommended_role_with_rationale": True,
            "must_preserve_downstream_risk_limits": True,
        },
        "downstream_risk_actions": state["forbidden_actions"],
        "downstream_risks": state["forbidden_actions"],
        "debug_only": state["debug_only"],
        "draft_only": state.get("draft_only", False),
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
    payload["gate_report_command"] = (
        _make_runtime_paths_absolute(
            f"{PYTHON_COMMAND_TEMPLATE} scripts/qc/gate_report.py --run-dir {run_dir} "
            f"--output {run_dir}/artifacts/gate_report.json "
            f"--markdown-output {run_dir}/artifacts/gate_report.md"
        )
    )
    payload["qc_protocol"] = GLOBAL_QC_PROTOCOL
    payload["current_qc_policy"] = QC_POLICY_BY_STAGE.get(
        state["current_stage"],
        {
            "checkpoint": state["current_stage"],
            "qc_mode": "Use state_report and QC role judgment to route warnings/failures; Python validators do not replace LLM quality judgment.",
            "if_not_ok": "Repair the current owner artifact, rerun the same check, then refresh state_report.py.",
        },
    )
    if state.get("owner_skill"):
        payload["role_routing"] = {
            "read_this_role_skill_before_repairing": state["owner_skill"],
            "do_not_bulk_read_unrelated_role_skills": True,
        }
    payload["qc_router_command"] = _make_runtime_paths_absolute(
        f"{PYTHON_COMMAND_TEMPLATE} scripts/qc/qc_router.py --run-dir {run_dir} --output {run_dir}/artifacts/qc_router_report.json"
    )
    if state["status"] in {"missing", "failed", "stale"}:
        payload["gate_policy"] = {
            "route_repair_before_downstream_delivery": True,
            "smallest_upstream_repair_first": True,
            "must_not_call_validator_failure_a_parsing_edge_case": True,
            "downstream_risk_actions": state["forbidden_actions"],
        }
    if state["current_stage"] == "FORMAL_RESEARCH_EXECUTION_MISSING_OR_FAILED":
        payload["planned_vs_actual_search_policy"] = {
            "fs_rows_are": "planned coverage instructions",
            "s_rows_are": "actual executed search attempts",
            "must_account_for_every_planned_fs_row": True,
            "unexecuted_fs_rows": "mark as not_executed, not_material, accounting_only, insufficient, or backlog",
            "do_not": [
                "Do not create fake S-xxx IDs for unexecuted FS rows.",
                "Do not create archive/source IDs for unexecuted FS rows.",
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
                "changed Opened/Reviewed to yes without a real opened source/archive snapshot",
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
        description="Report observable run state, candidate actions, and downstream risks for a run directory."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("status", "next"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--run-dir", required=True)
        sub.add_argument("--output")
        sub.add_argument(
            "--write-state",
            action="store_true",
            help="Explicitly write artifacts/mission_state.json. Default dashboard behavior is read-only.",
        )

    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    if args.command == "status":
        payload = status_payload(run_dir, write_state=args.write_state)
    else:
        payload = next_payload(run_dir, write_state=args.write_state)
    write_or_print(payload, args.output)


if __name__ == "__main__":
    main()
