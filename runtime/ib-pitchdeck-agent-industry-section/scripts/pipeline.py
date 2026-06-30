#!/usr/bin/env python3
"""Status, structured-render, and delivery helper for IB industry sections.

Use this CLI around LLM-authored work products. It does not perform research,
write page judgments, decide source quality, or authorize final delivery.
Its purpose is to show owner-facing next actions, expose debug helper checks
only when requested, and run the structured-render path when predictable tooling
is the right output path. Direct PPT composition can bypass render helpers and
still use status/finalize checks.
"""

from __future__ import annotations

import argparse
import copy
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from json import JSONDecodeError
from pathlib import Path
from typing import Any
from zipfile import ZipFile
from xml.sax.saxutils import escape

sys.dont_write_bytecode = True
SCRIPT_DIR = Path(__file__).resolve().parent
LIB_DIR = SCRIPT_DIR / "_lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))
QC_DIR = SCRIPT_DIR / "qc"
if str(QC_DIR) not in sys.path:
    sys.path.insert(0, str(QC_DIR))

from renderer_compile_utils import build_token_source, compile_banker_page_pack
from runtime_utils import default_layout_paths
from validate_artifact import (
    ARTIFACT_PATHS,
    VALIDATION_OUTPUTS,
    banker_page_pack_template_diagnostics,
    helper_check_guidance,
    validate_artifact as run_artifact_validation,
)
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def _internal_script(relative_path: str) -> Path:
    return ROOT_DIR / "scripts" / relative_path

TEMPLATE = ROOT_DIR / "assets" / "industry_section_template_master.pptx"
LAYOUT_PATHS = default_layout_paths(ROOT_DIR)
PPT_MAPPING = LAYOUT_PATHS["ppt_mapping"]
RENDER_LAYOUTS = LAYOUT_PATHS["render_layouts"]

FILLED_PPT = "industry_section_filled.pptx"
CLEAN_PPT = "industry_section_filled_clean.pptx"
TOKEN_PATTERN = re.compile(r"\{\{[^{}]+\}\}")
PYTHON_COMMAND_TEMPLATE = "$PYTHON_CMD"
INTERNAL_VALIDATE_ARTIFACTS = {
    "deck_blueprint",
    "formal_research_execution",
    "material_manifest",
    "page_evidence_contract",
    "pre_ppt",
    "research_pack",
    "renderer_spec",
    "replacement_dict",
    "source_archive",
    "template_registry",
}
PUBLIC_VALIDATE_ARTIFACTS = sorted(
    artifact for artifact in ARTIFACT_PATHS if artifact not in INTERNAL_VALIDATE_ARTIFACTS
)
PUBLIC_VALIDATE_ARTIFACTS_HELP = "{" + ",".join(PUBLIC_VALIDATE_ARTIFACTS) + "}"
STATUS_DETAIL_ONLY_ARTIFACTS = INTERNAL_VALIDATE_ARTIFACTS | {"filled_ppt", "final_delivery"}
PUBLIC_MILESTONE_LABELS = {
    "input_card": "material_intake",
    "material_extracts": "material_intake",
    "industry_scope_pack": "industry_scoping",
    "formal_search_plan": "research_planning",
    "executable_search_batch": "query_authoring",
    "research_graph_state": "research_execution",
    "research_evidence_db": "knowledge_repository",
    "research_request_queue": "targeted_research_queue",
    "banker_page_pack": "banker_page_pack",
    "filled_ppt": "output_render",
    "final_delivery": "final_delivery_review",
}
PPT_PRESENTATION_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
PPT_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PPT_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DRAWINGML_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"
ET.register_namespace("a", "http://schemas.openxmlformats.org/drawingml/2006/main")
ET.register_namespace("r", PPT_REL_NS)
ET.register_namespace("p", PPT_PRESENTATION_NS)
ET.register_namespace("", PPT_PACKAGE_REL_NS)
REPLACEMENT_TOP_LEVEL_FIELDS = {
    "selected_page_type",
    "slide_title",
    "main_takeaway",
    "chart_title",
    "source_footer",
    "speaker_note",
}
BULLET_PREFIX = "• "
PARAGRAPH_XML_RE = re.compile(r"(<a:p\b.*?</a:p>)", re.DOTALL)
TEXT_RUN_RE = re.compile(r"(<a:t>)(.*?)(</a:t>)", re.DOTALL)
RICH_TEXT_TAG_RE = re.compile(r"\[\[(\/?)(b|hl)\]\]")
HIGHLIGHT_COLOR = "E85D04"
REQUIRED_IMPORTS = [
    {"module": "pptx", "package": "python-pptx"},
    {"module": "lxml.etree", "package": "lxml"},
]
SEARCH_MODULE_GROUPS = {
    "tavily": ["tavily"],
    "duckduckgo": ["ddgs", "duckduckgo_search"],
    "searxng": [],
}
SEARXNG_ENV_VARS = ("SEARXNG_BASE_URL", "SEARXNG_URL", "SEARXNG_ENDPOINT")
PDF_EXTRACTION_MODULES = {"pdfplumber": "pdfplumber", "pypdf": "pypdf"}
PDF_EXTRACTION_COMMANDS = ("pdftotext",)
MAIN_STATUS_PATH = [
    "input_card",
    "industry_scope_pack",
    "formal_search_plan",
    "executable_search_batch",
    "research_graph_state",
    "research_evidence_db",
    "banker_page_pack",
    "filled_ppt",
    "final_delivery",
]
BUILD_HINTS = {
    "input_card": "Material Intake preserves the user's brief, separates explicit facts from assumptions, and avoids adding industry conclusions.",
    "material_extracts": "Material Intake registers user-provided materials and extracts explicit facts without adding conclusions.",
    "industry_scope_pack": "Industry Scoping LLM writes a short boundary card before formal research.",
    "formal_search_plan": "Research Planning LLM turns the scope card into compact evidence questions and prioritizes what can change the pitch.",
    "executable_search_batch": "Query Author LLM designs concrete searches for selected evidence needs; keep generic or deferred rows out of active execution.",
    "research_graph_state": "Research records actual searches, manual-source reviews, opened sources, locators, excerpts, candidate facts, candidate metrics, and unresolved gaps.",
    "formal_research_execution": "Research executes selected queries or manual-source reviews, then synchronizes the execution record.",
    "source_archive": "Research records opened/reviewed sources and archive status after real source review.",
    "research_evidence_db": "Knowledge LLM decides which candidate facts and metrics become supported evidence, context, conflicts, or gaps; do not promote weak rows to clear a check.",
    "research_pack": "Knowledge exports the readable research pack from the authored evidence DB.",
    "template_registry": "Template role inspects the selected PPT only when template style or layout hints are needed.",
    "banker_page_pack": "Generation LLM writes the client-facing banker page pack: page arguments, exhibits, source notes, caveats, and readiness.",
    "deck_blueprint": "Optional structured-render helper derived from the reviewed banker_page_pack; repair banker_page_pack if the story is weak.",
    "page_evidence_contract": "Optional structured-render helper carrying selected deck inclusion, headline, exhibit decisions, and evidence bindings forward from banker_page_pack.",
    "renderer_spec": "Optional structured-render helper for editable render instructions after page judgment is ready.",
    "pre_ppt": "Internal output preflight checks either structured-render inputs or the direct PPT composition path; repair evidence, page pack, or template-style inputs upstream.",
    "filled_ppt": (
        "Output chooses the best editable PPT path from the reviewed banker_page_pack: structured render for repeatable "
        "packaging, or direct PPT composition from a copied template when that better preserves the user's style. "
        "Then visually review the PPT and repair upstream authored files for content problems."
    ),
    "final_delivery": "QC/Output reviews final delivery with helper checks and editorial judgment before treating it as sendable.",
}
OWNER_STAGE_OVERRIDES = {
    "deck_blueprint": (
        "structured_render_helper",
        "Optional structured-render helper derived from the reviewed banker_page_pack; repair banker_page_pack or the evidence DB if the helper result is weak, and do not hand-edit helper files.",
    ),
    "page_evidence_contract": (
        "structured_render_helper",
        "Optional structured-render helper for selected deck inclusion, headline, or exhibit decisions from banker_page_pack; repair banker_page_pack or the evidence DB, not the helper contract.",
    ),
    "renderer_spec": (
        "structured_render_helper",
        "Optional structured-render helper for editable render instructions; repair banker_page_pack or the evidence DB before refreshing this artifact if it is missing or invalid.",
    ),
    "filled_ppt": (
        "ppt_render",
        "Output chooses structured render or direct editable PPT composition from the reviewed banker_page_pack, then visually reviews the PPT; repair upstream authored files for content issues rather than patching final slides.",
    ),
}


class PipelineError(RuntimeError):
    pass


def _json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise PipelineError(f"Failed to decode JSON file as UTF-8: {path}. {exc}") from exc
    except OSError as exc:
        raise PipelineError(f"Failed to read JSON file: {path}. {exc}") from exc
    except JSONDecodeError as exc:
        raise PipelineError(f"Invalid JSON in file: {path}. {exc}") from exc


def _load_json_lenient(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def artifact_path(run_dir: Path, artifact: str) -> Path:
    return run_dir / ARTIFACT_PATHS[artifact]


def _latest_final_ppt_path(run_dir: Path) -> Path | None:
    marker = run_dir / "LATEST_FINAL_PPT.txt"
    if not marker.exists():
        return None
    try:
        lines = marker.read_text(encoding="utf-8").splitlines()
    except Exception:
        return None
    if not lines:
        return None
    value = str(lines[0] or "").strip()
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = run_dir / path
    if path.suffix.lower() != ".pptx":
        return None
    return path


def check_output_path(run_dir: Path, artifact: str) -> Path:
    return run_dir / VALIDATION_OUTPUTS.get(artifact, f"artifacts/{artifact}_validation.json")


def helper_check_command(run_dir: Path, artifact: str) -> str:
    return (
        f"{PYTHON_COMMAND_TEMPLATE} scripts/pipeline.py review "
        f"--artifact {artifact} --run-dir {run_dir} --output {check_output_path(run_dir, artifact)}"
    )


def helper_check_note(command: str) -> str:
    parts = command.split()
    artifact = ""
    if "--artifact" in parts:
        idx = parts.index("--artifact")
        if idx + 1 < len(parts):
            artifact = parts[idx + 1]
    if artifact:
        return (
            f"Optional helper check for `{artifact}` after the owner action; "
            "rerun status/next with --include-debug-commands only when the exact command is needed."
        )
    return (
        "Optional helper check after the owner action; "
        "rerun status/next with --include-debug-commands only when the exact command is needed."
    )


def owner_action_from_hint(run_dir: Path, hint: str) -> str:
    hint = hint.strip()
    if not hint:
        return ""
    if hint.startswith("scripts/pipeline.py ") and "," not in hint and " then " not in hint:
        return f"{PYTHON_COMMAND_TEMPLATE} {hint} --run-dir {run_dir}"
    return f"Owner action: {hint}"


def _owner_stage_for_artifact(artifact: str, default_action: str) -> tuple[str, str]:
    override = OWNER_STAGE_OVERRIDES.get(artifact)
    if override:
        return override
    return artifact, default_action


PUBLIC_STATE_LABELS = {
    "missing": "needs_owner_authoring",
    "invalid": "needs_owner_repair",
    "unvalidated": "ready_for_optional_check",
    "valid": "structure_checked",
    "covered_by_downstream_authoring": "covered_by_downstream_authoring",
}


def public_state_label(state: Any) -> str:
    state_text = str(state or "")
    return PUBLIC_STATE_LABELS.get(state_text, state_text)


def artifact_status(run_dir: Path, artifact: str) -> dict[str, Any]:
    path = artifact_path(run_dir, artifact)
    alternate_path: Path | None = None
    if artifact == "filled_ppt" and not path.exists():
        marker_path = _latest_final_ppt_path(run_dir)
        if marker_path and marker_path.exists():
            alternate_path = marker_path
            path = marker_path
    check_output = check_output_path(run_dir, artifact)
    exists = path.exists()
    check_payload = _load_json_lenient(check_output) if check_output.exists() else {}
    is_valid = check_payload.get("is_valid")
    if not exists:
        state = "missing"
    elif is_valid is False:
        state = "invalid"
    elif is_valid is True:
        state = "valid"
    else:
        state = "unvalidated"
    return {
        "artifact": artifact,
        "path": str(path),
        "alternate_path_used": str(alternate_path) if alternate_path else "",
        "exists": exists,
        "check_output": str(check_output),
        "check_output_exists": check_output.exists(),
        "state": state,
        "error_count": check_payload.get("error_count", 0),
        "errors": check_payload.get("errors", []),
        "helper_check_command": helper_check_command(run_dir, artifact),
        "builder_or_owner_action": BUILD_HINTS.get(artifact, ""),
    }


def public_artifact_status(row: dict[str, Any], *, include_details: bool = False) -> dict[str, Any] | None:
    if str(row.get("artifact") or "") in STATUS_DETAIL_ONLY_ARTIFACTS:
        return None
    if not include_details:
        public_row = {
            "artifact": row.get("artifact"),
            "state": row.get("state"),
        }
        public_row["state"] = public_state_label(public_row.get("state"))
        return public_row
    internal_status_fields = {
        "helper_check_command",
        "builder_or_owner_action",
        "check_output",
        "check_output_exists",
    }
    public_row = {
        key: value
        for key, value in row.items()
        if key not in internal_status_fields
    }
    if "state" in public_row:
        public_row["state"] = public_state_label(public_row.get("state"))
    return public_row


def public_milestone_status(row: dict[str, Any]) -> dict[str, Any] | None:
    artifact = str(row.get("artifact") or "")
    if artifact in STATUS_DETAIL_ONLY_ARTIFACTS:
        return None
    return {
        "stage": PUBLIC_MILESTONE_LABELS.get(artifact, artifact),
        "state": public_state_label(row.get("state")),
    }


def public_milestone_progress(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority = {
        "needs_owner_repair": 0,
        "needs_owner_authoring": 1,
        "ready_for_optional_check": 2,
        "covered_by_downstream_authoring": 3,
        "structure_checked": 3,
    }
    progress: list[dict[str, Any]] = []
    by_stage: dict[str, dict[str, Any]] = {}
    for row in rows:
        milestone = public_milestone_status(row)
        if not milestone:
            continue
        stage = str(milestone.get("stage") or "")
        state = str(milestone.get("state") or "")
        existing = by_stage.get(stage)
        if existing is None:
            by_stage[stage] = milestone
            progress.append(milestone)
            continue
        if priority.get(state, 99) < priority.get(str(existing.get("state") or ""), 99):
            existing["state"] = state
    return progress


def public_current_stage(artifact: str, owner_stage: str) -> str:
    if artifact in OWNER_STAGE_OVERRIDES:
        return owner_stage
    return PUBLIC_MILESTONE_LABELS.get(artifact, owner_stage)


def public_deliverable_readiness(readiness_state: dict[str, Any]) -> dict[str, Any]:
    if not readiness_state:
        return {}
    route = str(readiness_state.get("route_if_not_ready") or "")
    is_ready = bool(readiness_state.get("is_client_ready"))
    if is_ready:
        status_label = "client_ready"
        next_action = "send final editable PPT when visual/source QC is clean"
    elif route == "bounded_targeted_research_then_rerender":
        status_label = "needs_targeted_research"
        next_action = "run one bounded targeted research pass that could change a page decision"
    elif route == "qc_or_user_decision_after_source_limit":
        status_label = "source_limit_qc_user_decision"
        next_action = "ask QC/user to decide after source limits"
    elif route == "repair_banker_page_pack_before_render":
        status_label = "needs_banker_page_pack_repair"
        next_action = "repair page writing, exhibits, caveats, or density in banker_page_pack"
    elif route in {"author_banker_page_pack", "repair_banker_page_pack", "finish_banker_page_pack_readiness_decision"}:
        status_label = "needs_page_pack_next_action"
        next_action = "state the page-pack next action in business terms"
    else:
        status_label = "needs_owner_judgment"
        next_action = "inspect the page pack and choose the next business action"
    return {
        "is_client_ready": is_ready,
        "has_explicit_decision": bool(readiness_state.get("has_explicit_decision")),
        "status_label": status_label,
        "next_business_action": next_action,
        "reason": str(readiness_state.get("reason") or ""),
    }


def public_research_loop_state(loop_state: dict[str, Any]) -> dict[str, Any]:
    if not loop_state:
        return {}
    route = str(loop_state.get("route") or "")
    queue_exists = bool(loop_state.get("queue_exists"))
    loop_exhausted = bool(loop_state.get("loop_exhausted"))
    current_cycle = loop_state.get("current_cycle")
    max_cycles = loop_state.get("max_cycles")
    if not queue_exists:
        status_label = "needs_targeted_research_queue"
        next_action = "write one bounded targeted research request"
    elif route == "repair_research_request_queue":
        status_label = "repair_research_request_queue"
        next_action = "repair the targeted research queue before execution"
    elif route == "execute_final_targeted_cycle":
        status_label = "final_targeted_research_cycle"
        next_action = "execute the final bounded targeted research cycle"
    elif route == "continue_targeted_research":
        status_label = "continue_targeted_research"
        next_action = "execute the active bounded targeted research request"
    elif route == "author_narrow_next_request_or_record_source_limit":
        status_label = "narrow_next_request_or_record_source_limit"
        next_action = "author one narrower request or record why more research will not change the page"
    elif route == "author_targeted_request_or_record_cycle_outcome":
        status_label = "record_cycle_outcome_or_author_request"
        next_action = "record what the last cycle found, or author one decision-changing request"
    elif route == "qc_or_user_decision_after_loop_cap":
        status_label = "loop_exhausted_qc_user_decision"
        next_action = "ask QC/user to decide after the targeted research cap"
    else:
        status_label = "needs_research_owner_judgment"
        next_action = "inspect the research queue and choose the next bounded action"
    payload: dict[str, Any] = {
        "queue_exists": queue_exists,
        "loop_exhausted": loop_exhausted,
        "status_label": status_label,
        "next_business_action": next_action,
    }
    if isinstance(current_cycle, int) and isinstance(max_cycles, int):
        payload["cycle_summary"] = f"cycle {current_cycle} of {max_cycles}"
    notes: list[str] = []
    if loop_state.get("read_error"):
        notes.append(str(loop_state.get("read_error") or ""))
    if loop_state.get("loop_control_missing"):
        notes.append("Missing cycle bookkeeping; helper assumes first cycle under the policy cap.")
    if loop_state.get("missing_active_flags"):
        notes.append(
            "Some requests do not say whether they remain active; treat them as active until closed in plain language."
        )
    if notes:
        payload["note"] = " ".join(note for note in notes if note)
    return payload


def _apply_downstream_authoring_coverage(run_dir: Path, rows: list[dict[str, Any]]) -> None:
    """Avoid forcing early workbench repair after the Knowledge DB exists.

    The evidence DB is the authored source of truth for usable evidence. If it
    already exists, missing/stale intake extracts, scope cards, query-planning,
    or research-execution workbench artifacts should not become the current
    status blocker. They remain visible as covered milestones so an operator can
    inspect provenance if needed.
    """
    if not artifact_path(run_dir, "research_evidence_db").exists():
        return
    covered_upstream_workbench = {
        "industry_scope_pack",
        "formal_search_plan",
        "executable_search_batch",
        "research_graph_state",
    }
    for row in rows:
        artifact = str(row.get("artifact") or "")
        if artifact not in covered_upstream_workbench:
            continue
        if row.get("state") not in {"missing", "invalid", "unvalidated"}:
            continue
        row["state"] = "covered_by_downstream_authoring"
        row["covered_by"] = "research_evidence_db"
        row["builder_or_owner_action"] = (
            "Knowledge evidence DB already exists and is the evidence source of truth; "
            "do not backfill this earlier workbench solely for status. Repair the DB if evidence is weak."
        )


def _state_is_ready_for_downstream(row: dict[str, Any]) -> bool:
    return row.get("state") in {"valid", "covered_by_downstream_authoring"}


def build_run_status(run_dir: Path, *, include_debug_commands: bool = False) -> dict[str, Any]:
    rows = [artifact_status(run_dir, artifact) for artifact in MAIN_STATUS_PATH]
    _apply_downstream_authoring_coverage(run_dir, rows)
    current = next((row for row in rows if row["state"] in {"missing", "invalid", "unvalidated"}), rows[-1] if rows else {})
    structure_complete = bool(rows) and all(_state_is_ready_for_downstream(row) for row in rows)
    page_pack_exists = (run_dir / "banker_page_pack.json").exists()
    page_pack_structure_ready = False
    for idx, row in enumerate(rows):
        if row.get("artifact") == "banker_page_pack":
            page_pack_structure_ready = bool(page_pack_exists) and all(
                _state_is_ready_for_downstream(prior) for prior in rows[: idx + 1]
            )
            break
    readiness_state: dict[str, Any] = {}
    readiness_ready = True
    if page_pack_exists:
        readiness_state = _llm_deliverable_readiness_state(run_dir)
        readiness_ready = bool(readiness_state["is_client_ready"])
    commands: list[str] = []
    if current:
        artifact = str(current.get("artifact") or "")
        _owner_stage, hint = _owner_stage_for_artifact(artifact, str(current.get("builder_or_owner_action") or ""))
        owner_action = owner_action_from_hint(run_dir, hint)
        if owner_action:
            commands.append(owner_action)
        if current.get("exists") or current.get("state") != "missing":
            commands.append(str(current.get("helper_check_command") or ""))
    status = "complete" if structure_complete else "needs_work"
    if page_pack_structure_ready and not readiness_ready:
        if readiness_state.get("route_if_not_ready") == "finish_banker_page_pack_readiness_decision":
            status = "needs_page_pack_readiness_decision"
            current = {
                "artifact": "banker_page_pack",
                "state": "needs_llm_readiness_decision",
                "builder_or_owner_action": (
                    "Generation/Reasoning LLM states the next business action in the page pack: "
                    "send, repair page writing/exhibits, run one bounded research request, or ask QC/user after source limits"
                ),
            }
            commands = [
                "LLM: state the page-pack next action in business terms; use a bounded targeted research queue only if evidence could change the page decision",
                str(helper_check_command(run_dir, "banker_page_pack")),
            ]
        elif readiness_state.get("route_if_not_ready") == "repair_banker_page_pack_before_render":
            status = "needs_banker_page_pack_repair"
            current = {
                "artifact": "banker_page_pack",
                "state": "needs_llm_repair",
                "builder_or_owner_action": (
                    "Generation/Reasoning LLM repairs banker_page_pack page judgment, client-facing wording, page density, "
                    "source caveats, or exhibit design. Route to targeted research only if a specific evidence gap could "
                    "change deck inclusion, key data audit, or exhibit readiness."
                ),
            }
            commands = [
                "LLM: repair banker_page_pack for client-facing story, density, source caveats, or exhibit design; do not start research unless a concrete evidence gap would change a page decision",
                str(helper_check_command(run_dir, "banker_page_pack")),
            ]
        elif readiness_state.get("route_if_not_ready") == "qc_or_user_decision_after_source_limit":
            status = "needs_qc_user_decision_after_source_limit"
            current = {
                "artifact": "banker_page_pack",
                "state": "research_source_limit_reached",
                "builder_or_owner_action": (
                    "QC/user decision required: the LLM says targeted research is exhausted or realistic sources are unavailable. "
                    "Provide new sources, narrow the page scope, explicitly authorize another targeted cycle, or create only a non-final research-limited review copy; "
                    "do not start another search loop without explicit operator direction."
                ),
            }
            commands = [
                "QC/user decision: bounded research/source limit reached; provide sources, narrow banker_page_pack, explicitly authorize another cycle, or create only a non-final review copy",
                str(helper_check_command(run_dir, "banker_page_pack")),
                str(helper_check_command(run_dir, "research_request_queue")),
            ]
        else:
            loop_state = _research_queue_loop_state(run_dir)
            if loop_state.get("loop_exhausted"):
                status = "needs_qc_user_decision_after_research_loop_cap"
                current = {
                    "artifact": "banker_page_pack",
                    "state": "targeted_research_loop_exhausted",
                    "builder_or_owner_action": (
                        "QC/user decision required: the bounded targeted research loop is exhausted. "
                        "Provide new sources, revise banker_page_pack scope, explicitly authorize another targeted cycle, or create only a non-final research-limited review copy; "
                        "do not start another search loop without explicit operator direction."
                    ),
                }
                commands = [
                    "QC/user decision: targeted research loop cap reached; provide sources, narrow/repair banker_page_pack, explicitly authorize another cycle, or create only a non-final review copy",
                    str(helper_check_command(run_dir, "banker_page_pack")),
                    str(helper_check_command(run_dir, "research_request_queue")),
                ]
            else:
                status = "needs_targeted_research"
                current = {
                    "artifact": "research_request_queue",
                    "state": "needs_llm_authoring_or_execution",
                    "builder_or_owner_action": "Reasoning LLM authors or repairs a bounded targeted research queue, then Research executes only the evidence gaps that could change a page decision",
                }
                queue_path = run_dir / "artifacts/research_request_queue.json"
                commands = [
                    str(helper_check_command(run_dir, "research_request_queue")) if queue_path.exists()
                    else "Reasoning LLM: author a bounded targeted research queue for the unresolved evidence gaps",
                ]
    command_list = [command for command in commands if command]
    action_list = [command for command in command_list if "scripts/pipeline.py" not in command]
    current_artifact = str(current.get("artifact") or "")
    owner_stage, owner_action = _owner_stage_for_artifact(current_artifact, str(current.get("builder_or_owner_action") or ""))
    if not action_list and owner_action:
        action_list = [f"Owner action: {owner_action}"]
    check_commands = [command for command in command_list if "scripts/pipeline.py" in command]
    helper_checks = [helper_check_note(command) for command in check_commands] if include_debug_commands else []
    current_stage = public_current_stage(current_artifact, owner_stage)
    raw_research_loop_state = _research_queue_loop_state(run_dir) if page_pack_exists and not readiness_ready else {}
    report = {
        "schema_version": "status_report_v1",
        "run_dir": str(run_dir),
        "status": status,
        "current_stage": current_stage,
        "current_state": public_state_label(current.get("state", "")),
        "current_owner_action": owner_action,
        "recommended_next_actions": action_list,
        "llm_deliverable_readiness": public_deliverable_readiness(readiness_state) if page_pack_exists else {},
        "research_loop_state": public_research_loop_state(raw_research_loop_state),
        "milestones": public_milestone_progress(rows),
        "status_scope": (
            "Guides the next owner action; debug mode can expose exact helper-check commands, but "
            "it does not certify source quality, page density, or final delivery quality."
        ),
    }
    if helper_checks:
        report["optional_helper_checks"] = helper_checks
    if include_debug_commands:
        report["current_artifact"] = current_artifact
        report["debug_helper_check_commands"] = check_commands
        report["artifacts"] = [
            public_row
            for row in rows
            if (public_row := public_artifact_status(row, include_details=True)) is not None
        ]
    return report


def write_status_markdown(report: dict[str, Any], path: Path) -> None:
    readiness = report.get("llm_deliverable_readiness") if isinstance(report.get("llm_deliverable_readiness"), dict) else {}
    loop_state = report.get("research_loop_state") if isinstance(report.get("research_loop_state"), dict) else {}
    lines: list[str] = [
        "# Status Report",
        "",
        f"- Run: `{report.get('run_dir')}`",
        f"- Status: `{report.get('status')}`",
        f"- Current stage: `{report.get('current_stage')}`",
    ]
    if report.get("current_artifact") and report.get("current_artifact") != report.get("current_stage"):
        lines.append(f"- Debug artifact: `{report.get('current_artifact')}`")
    if report.get("current_owner_action"):
        lines.append(f"- Owner action: {report.get('current_owner_action')}")
    actions = report.get("recommended_next_actions") if isinstance(report.get("recommended_next_actions"), list) else []
    if actions:
        lines.extend(["", "## Next Actions", ""])
        for action in actions:
            lines.append(f"- {action}")
    check_commands = (
        report.get("optional_helper_checks")
        if isinstance(report.get("optional_helper_checks"), list)
        else []
    )
    if check_commands:
        lines.extend(["", "## Optional Helper Checks", ""])
        for command in check_commands:
            lines.append(f"- `{command}`")
    if readiness:
        readiness_label = str(readiness.get("status_label") or "")
        if not readiness_label:
            readiness_label = "client_ready" if readiness.get("is_client_ready") else "needs_owner_judgment"
        loop_label = str(loop_state.get("status_label") or "")
        if loop_label in {"final_targeted_research_cycle", "loop_exhausted_qc_user_decision"}:
            readiness_label = loop_label
        lines.append(
            f"- LLM delivery readiness: `{readiness_label}`"
        )
        if readiness.get("next_business_action"):
            lines.append(f"- Next business action: {readiness.get('next_business_action')}")
        if readiness.get("reason"):
            lines.append(f"- Readiness note: {readiness.get('reason')}")
    if loop_state:
        if loop_state.get("next_business_action"):
            lines.append(f"- Research loop action: {loop_state.get('next_business_action')}")
        if loop_state.get("cycle_summary"):
            lines.append(f"- Research loop: {loop_state.get('cycle_summary')}")
        if loop_state.get("note"):
            lines.append(f"- Research loop note: {loop_state.get('note')}")
    lines.extend(["", "## Milestone Progress", ""])
    for row in report.get("milestones", []):
        lines.append(f"- `{row['stage']}`: {row['state']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_status_json(report: dict[str, Any], path: Path | None) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _collect_template_tokens(pptx_path: Path) -> dict[str, list[str]]:
    token_locations: dict[str, list[str]] = defaultdict(list)
    try:
        archive = ZipFile(pptx_path)
    except FileNotFoundError as exc:
        raise PipelineError(f"PPTX template not found: {pptx_path}") from exc
    except Exception as exc:
        raise PipelineError(f"Failed to open PPTX template {pptx_path}: {exc}") from exc
    with archive:
        for name in archive.namelist():
            if not (name.startswith("ppt/slides/slide") and name.endswith(".xml")):
                continue
            root = ET.fromstring(archive.read(name))
            for elem in root.iter():
                if not elem.tag.endswith("}p"):
                    continue
                paragraph_text = "".join(
                    child.text for child in elem.iter() if child.tag.endswith("}t") and child.text
                )
                for token in TOKEN_PATTERN.findall(paragraph_text):
                    token_locations[token].append(name)
    return dict(token_locations)


def _collect_mapping_tokens(mapping: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tokens: dict[str, dict[str, Any]] = {}
    for slide in mapping.get("slides", []):
        if not isinstance(slide, dict):
            continue
        slide_no = slide.get("slide_no")
        slide_key = slide.get("slide_key")
        if "tokens" in slide:
            for token in slide.get("tokens", []):
                if not isinstance(token, dict):
                    continue
                placeholder = str(token.get("placeholder") or "").strip()
                if placeholder:
                    tokens[placeholder] = {
                        "slide_no": slide_no,
                        "slide_key": slide_key,
                        "field_name": token.get("field_name", ""),
                        "selected_page_type": slide.get("selected_page_type", ""),
                        "variant_key": "",
                    }
            continue
        variants = slide.get("controlled_variants") if isinstance(slide.get("controlled_variants"), dict) else {}
        for page_type, variant in variants.items():
            if not isinstance(variant, dict):
                continue
            for token in variant.get("tokens", []):
                if not isinstance(token, dict):
                    continue
                placeholder = str(token.get("placeholder") or "").strip()
                if placeholder:
                    tokens[placeholder] = {
                        "slide_no": slide_no,
                        "slide_key": slide_key,
                        "field_name": token.get("field_name", ""),
                        "selected_page_type": page_type,
                        "variant_key": variant.get("variant_key", ""),
                    }
    return tokens


def _normalize_replacement_value(value: Any) -> str:
    return html.unescape(str(value))


def _ensure_paragraph_properties(paragraph: ET.Element) -> ET.Element:
    properties = paragraph.find(f"{{{DRAWINGML_NS}}}pPr")
    if properties is None:
        properties = ET.Element(f"{{{DRAWINGML_NS}}}pPr")
        paragraph.insert(0, properties)
    return properties


def _apply_bullet_properties(paragraph: ET.Element) -> None:
    properties = _ensure_paragraph_properties(paragraph)
    properties.set("marL", "228600")
    properties.set("indent", "-152400")
    for tag in ("buNone", "buAutoNum", "buBlip", "buChar"):
        for child in list(properties.findall(f"{{{DRAWINGML_NS}}}{tag}")):
            properties.remove(child)
    ET.SubElement(properties, f"{{{DRAWINGML_NS}}}buChar", {"char": "•"})


def _parse_rich_text_segments(text: str) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    state = {"b": 0, "hl": 0}
    cursor = 0
    for match in RICH_TEXT_TAG_RE.finditer(text):
        if match.start() > cursor:
            segments.append(
                {
                    "text": text[cursor:match.start()],
                    "bold": state["b"] > 0,
                    "highlight": state["hl"] > 0,
                }
            )
        closing, tag = match.groups()
        state[tag] = max(0, state[tag] - 1) if closing else state[tag] + 1
        cursor = match.end()
    if cursor < len(text):
        segments.append(
            {
                "text": text[cursor:],
                "bold": state["b"] > 0,
                "highlight": state["hl"] > 0,
            }
        )

    merged: list[dict[str, Any]] = []
    for segment in segments:
        if not segment["text"]:
            continue
        if merged and merged[-1]["bold"] == segment["bold"] and merged[-1]["highlight"] == segment["highlight"]:
            merged[-1]["text"] += segment["text"]
        else:
            merged.append(segment)
    return merged


def _strip_rich_text_markup(text: str) -> str:
    return RICH_TEXT_TAG_RE.sub("", text)


def _has_rich_text_markup(text: str) -> bool:
    return bool(RICH_TEXT_TAG_RE.search(text))


def _ensure_text_space(node: ET.Element, text: str) -> None:
    if text[:1].isspace() or text[-1:].isspace():
        node.set(f"{{{XML_NS}}}space", "preserve")


def _build_styled_runs(paragraph_xml: str, updated: str) -> str:
    wrapper = f'<root xmlns:a="{DRAWINGML_NS}">{paragraph_xml}</root>'
    root = ET.fromstring(wrapper)
    paragraph = root[0]
    bullet_paragraph = updated.startswith(BULLET_PREFIX)
    if bullet_paragraph:
        updated = updated[len(BULLET_PREFIX):].lstrip()
        _apply_bullet_properties(paragraph)

    text_containers: list[ET.Element] = []
    first_run_template: ET.Element | None = None
    first_run_properties: ET.Element | None = None
    for child in list(paragraph):
        if child.tag == f"{{{DRAWINGML_NS}}}r":
            text_containers.append(child)
            if first_run_template is None:
                first_run_template = child
            if first_run_properties is None:
                first_run_properties = child.find(f"{{{DRAWINGML_NS}}}rPr")
        elif child.tag == f"{{{DRAWINGML_NS}}}fld":
            text_containers.append(child)
            if first_run_properties is None:
                first_run_properties = child.find(f"{{{DRAWINGML_NS}}}rPr")

    if first_run_properties is None:
        first_run_properties = ET.Element(f"{{{DRAWINGML_NS}}}rPr")

    for child in text_containers:
        paragraph.remove(child)

    end_para = paragraph.find(f"{{{DRAWINGML_NS}}}endParaRPr")
    children = list(paragraph)
    insert_at = children.index(end_para) if end_para is not None and end_para in children else len(children)

    new_nodes: list[ET.Element] = []
    segments = (
        _parse_rich_text_segments(updated)
        if _has_rich_text_markup(updated)
        else [{"text": updated, "bold": False, "highlight": False}]
    )
    for segment in segments:
        parts = str(segment["text"]).split("\n")
        for idx, part in enumerate(parts):
            if idx > 0:
                new_nodes.append(ET.Element(f"{{{DRAWINGML_NS}}}br"))
            if first_run_template is not None:
                run = copy.deepcopy(first_run_template)
                for child in list(run):
                    if child.tag != f"{{{DRAWINGML_NS}}}rPr":
                        run.remove(child)
                run_properties = run.find(f"{{{DRAWINGML_NS}}}rPr")
                if run_properties is None:
                    run_properties = ET.Element(f"{{{DRAWINGML_NS}}}rPr")
                    run.insert(0, run_properties)
            else:
                run = ET.Element(f"{{{DRAWINGML_NS}}}r")
                run_properties = copy.deepcopy(first_run_properties)
                run.append(run_properties)
            if segment["bold"] or segment["highlight"]:
                run_properties.set("b", "1")
            if segment["highlight"]:
                for fill in list(run_properties.findall(f"{{{DRAWINGML_NS}}}solidFill")):
                    run_properties.remove(fill)
                solid_fill = ET.SubElement(run_properties, f"{{{DRAWINGML_NS}}}solidFill")
                ET.SubElement(solid_fill, f"{{{DRAWINGML_NS}}}srgbClr", {"val": HIGHLIGHT_COLOR})
            text_node = ET.SubElement(run, f"{{{DRAWINGML_NS}}}t")
            text_node.text = _strip_rich_text_markup(part)
            _ensure_text_space(text_node, text_node.text or "")
            new_nodes.append(run)

    for offset, node in enumerate(new_nodes):
        paragraph.insert(insert_at + offset, node)
    return ET.tostring(paragraph, encoding="unicode")


def _rewrite_paragraph(paragraph_xml: str, replacements: dict[str, str]) -> tuple[str, int]:
    matches = list(TEXT_RUN_RE.finditer(paragraph_xml))
    if not matches:
        return paragraph_xml, 0

    original = "".join(match.group(2) for match in matches)
    updated = original
    replacement_count = 0
    for placeholder, value in replacements.items():
        occurrences = updated.count(placeholder)
        if occurrences:
            updated = updated.replace(placeholder, value)
            replacement_count += occurrences
    if updated == original:
        return paragraph_xml, 0

    if updated.startswith(BULLET_PREFIX) or _has_rich_text_markup(updated) or "\n" in updated:
        return _build_styled_runs(paragraph_xml, updated), replacement_count

    escaped_updated = escape(updated)
    new_parts = [escaped_updated] + [""] * (len(matches) - 1)
    rebuilt: list[str] = []
    last_end = 0
    for match, new_text in zip(matches, new_parts):
        rebuilt.append(paragraph_xml[last_end:match.start(2)])
        rebuilt.append(new_text)
        last_end = match.end(2)
    rebuilt.append(paragraph_xml[last_end:])
    return "".join(rebuilt), replacement_count


def _replace_tokens_in_slide(xml_bytes: bytes, replacements: dict[str, str]) -> tuple[bytes, int, int]:
    text = xml_bytes.decode("utf-8")
    updated_text = text
    replaced_paragraphs = 0
    replacement_count = 0

    if PARAGRAPH_XML_RE.findall(text):
        rebuilt: list[str] = []
        last_end = 0
        for match in PARAGRAPH_XML_RE.finditer(text):
            rewritten, count = _rewrite_paragraph(match.group(1), replacements)
            rebuilt.append(text[last_end:match.start(1)])
            rebuilt.append(rewritten)
            last_end = match.end(1)
            if count:
                replaced_paragraphs += 1
                replacement_count += count
        rebuilt.append(text[last_end:])
        updated_text = "".join(rebuilt)
    else:
        for placeholder, value in replacements.items():
            occurrences = updated_text.count(placeholder)
            if occurrences:
                updated_text = updated_text.replace(placeholder, escape(value))
                replacement_count += occurrences
        replaced_paragraphs = 1 if updated_text != text else 0
    return updated_text.encode("utf-8"), replaced_paragraphs, replacement_count


def fill_ppt(template: Path, replacement_dict: Path, output: Path) -> dict[str, Any]:
    replacements = {
        str(key): _normalize_replacement_value(value)
        for key, value in _json(replacement_dict).items()
    }
    replaced_files = 0
    replaced_paragraphs = 0
    replaced_tokens = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        try:
            with ZipFile(template, "r") as zin:
                zin.extractall(tmpdir_path)
        except FileNotFoundError as exc:
            raise PipelineError(f"PPTX template not found: {template}") from exc
        except Exception as exc:
            raise PipelineError(f"Failed to open PPTX template {template}: {exc}") from exc

        for slide_xml in sorted((tmpdir_path / "ppt" / "slides").glob("slide*.xml")):
            updated_bytes, paragraph_count, token_count = _replace_tokens_in_slide(slide_xml.read_bytes(), replacements)
            if paragraph_count:
                slide_xml.write_bytes(updated_bytes)
                replaced_files += 1
                replaced_paragraphs += paragraph_count
                replaced_tokens += token_count

        with ZipFile(output, "w") as zout:
            for file_path in sorted(tmpdir_path.rglob("*")):
                if file_path.is_file():
                    zout.write(file_path, file_path.relative_to(tmpdir_path))

    return {
        "template": str(template),
        "replacement_dict": str(replacement_dict),
        "output": str(output),
        "replaced_files": replaced_files,
        "replaced_paragraphs": replaced_paragraphs,
        "replaced_tokens": replaced_tokens,
        "replacement_key_count": len(replacements),
    }


def _slide_layouts_from_registry(path: Path | None = None) -> dict[int, dict[str, Any]]:
    payload = _json(path or ROOT_DIR / "configs" / "slide_registry.json")
    slides = payload.get("slides")
    if not isinstance(slides, list):
        raise PipelineError("slide_registry.json must contain list field 'slides'")

    library: dict[int, dict[str, Any]] = {}
    for item in slides:
        if not isinstance(item, dict):
            continue
        slide_no = item.get("slide_no")
        slide_key = item.get("slide_key")
        variants = item.get("variants")
        if not isinstance(slide_no, int) or not slide_key or not isinstance(variants, dict):
            raise PipelineError(
                "invalid slide registry entry for physical layout mapping: "
                f"slide_no={slide_no}, slide_key={slide_key}, variants={variants}"
            )
        page_type_to_slide = {
            str(page_type): str(variant.get("physical_slide") or "")
            for page_type, variant in variants.items()
            if isinstance(variant, dict) and variant.get("physical_slide")
        }
        if not page_type_to_slide:
            raise PipelineError(f"slide_registry slide_no={slide_no} has no physical_slide mappings")
        library[slide_no] = {
            "slide_key": slide_key,
            "page_type_to_slide": page_type_to_slide,
        }
    return library


def _renderer_slides(control_data: dict[str, Any], control_file_path: Path) -> list[dict[str, Any]]:
    slides = control_data.get("slides")
    if isinstance(slides, list) and slides:
        return [slide for slide in slides if isinstance(slide, dict)]
    raise PipelineError(f"{control_file_path} must contain non-empty slides array")


def _selected_slide_files(control_data: dict[str, Any], control_file_path: Path) -> set[str]:
    keep: set[str] = set()
    by_no = {int(slide["slide_no"]): slide for slide in _renderer_slides(control_data, control_file_path) if slide.get("slide_no")}
    for slide_no, config in _slide_layouts_from_registry().items():
        page = by_no.get(slide_no)
        if not page:
            raise PipelineError(f"renderer_spec missing slide_no={slide_no} for {config['slide_key']}")
        selected_page_type = str(page.get("selected_page_type") or "").strip()
        slide_name = config["page_type_to_slide"].get(selected_page_type)
        if not slide_name:
            allowed = ", ".join(config["page_type_to_slide"].keys())
            raise PipelineError(
                f"invalid selected_page_type for slide_no={slide_no}, slide_key={config['slide_key']}: "
                f"{selected_page_type!r}; allowed={allowed}"
            )
        keep.add(str(slide_name))
    return keep


def clean_presentation(pptx_path: Path, control_file_path: Path, output_path: Path) -> dict[str, Any]:
    keep_slides = _selected_slide_files(_json(control_file_path), control_file_path)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        try:
            with ZipFile(pptx_path, "r") as zin:
                zin.extractall(tmpdir_path)
        except FileNotFoundError as exc:
            raise PipelineError(f"filled PPTX not found: {pptx_path}") from exc
        except Exception as exc:
            raise PipelineError(f"failed to open filled PPTX {pptx_path}: {exc}") from exc

        presentation_xml = tmpdir_path / "ppt" / "presentation.xml"
        rels_xml = tmpdir_path / "ppt" / "_rels" / "presentation.xml.rels"
        presentation_tree = ET.parse(presentation_xml)
        presentation_root = presentation_tree.getroot()
        rels_tree = ET.parse(rels_xml)
        rels_root = rels_tree.getroot()

        rel_targets = {
            rel.attrib["Id"]: rel.attrib["Target"].split("/")[-1]
            for rel in rels_root.findall(f"{{{PPT_PACKAGE_REL_NS}}}Relationship")
            if rel.attrib.get("Type", "").endswith("/slide")
        }
        slide_id_list = presentation_root.find(f"{{{PPT_PRESENTATION_NS}}}sldIdLst")
        if slide_id_list is None:
            raise PipelineError(f"presentation.xml is missing p:sldIdLst in {pptx_path}")

        kept_rids: set[str] = set()
        for slide_id in list(slide_id_list):
            rid = slide_id.attrib.get(f"{{{PPT_REL_NS}}}id")
            target_name = rel_targets.get(rid, "")
            if target_name not in keep_slides:
                slide_id_list.remove(slide_id)
            elif rid:
                kept_rids.add(rid)

        for rel in list(rels_root.findall(f"{{{PPT_PACKAGE_REL_NS}}}Relationship")):
            if rel.attrib.get("Type", "").endswith("/slide") and rel.attrib.get("Id") not in kept_rids:
                rels_root.remove(rel)

        presentation_tree.write(presentation_xml, encoding="UTF-8", xml_declaration=True)
        rels_tree.write(rels_xml, encoding="UTF-8", xml_declaration=True)
        with ZipFile(output_path, "w") as zout:
            for file_path in sorted(tmpdir_path.rglob("*")):
                if file_path.is_file():
                    zout.write(file_path, file_path.relative_to(tmpdir_path))

    return {
        "input_pptx": str(pptx_path),
        "control_file": str(control_file_path),
        "output_pptx": str(output_path),
        "kept_slide_files": sorted(keep_slides),
        "kept_slide_count": len(keep_slides),
    }


def build_template_token_report(template_path: Path, ppt_mapping_path: Path) -> dict[str, Any]:
    template_tokens = _collect_template_tokens(template_path)
    mapping_tokens = _collect_mapping_tokens(_json(ppt_mapping_path))
    template_set = set(template_tokens)
    mapping_set = set(mapping_tokens)
    missing_in_mapping = sorted(template_set - mapping_set)
    missing_in_template = sorted(mapping_set - template_set)
    matched = sorted(template_set & mapping_set)
    return {
        "summary": {
            "template_token_count": len(template_set),
            "mapping_token_count": len(mapping_set),
            "matched_token_count": len(matched),
            "missing_in_mapping_count": len(missing_in_mapping),
            "missing_in_template_count": len(missing_in_template),
            "is_consistent": not missing_in_mapping and not missing_in_template,
        },
        "missing_in_mapping": [
            {"placeholder": token, "template_locations": template_tokens[token]}
            for token in missing_in_mapping
        ],
        "missing_in_template": [
            {"placeholder": token, "mapping_entry": mapping_tokens[token]}
            for token in missing_in_template
        ],
        "matched_tokens": [
            {
                "placeholder": token,
                "template_locations": template_tokens[token],
                "mapping_entry": mapping_tokens[token],
            }
            for token in matched
        ],
    }


def _write_template_token_report(template_path: Path, ppt_mapping_path: Path, output_path: Path) -> None:
    report = build_template_token_report(template_path, ppt_mapping_path)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not report.get("summary", {}).get("is_consistent"):
        raise PipelineError("template tokens and ppt_mapping.json are inconsistent")


def should_prefix_bullet(field_name: str) -> bool:
    lowered = field_name.lower()
    if lowered in REPLACEMENT_TOP_LEVEL_FIELDS:
        return False
    if any(key in lowered for key in ("table_", "matrix_label", "matrix_title", "chart_", "source")):
        return False
    return True


def ensure_bullet_prefix(value: str, field_name: str) -> str:
    text_value = value.strip()
    if not text_value or not should_prefix_bullet(field_name):
        return value
    if text_value.startswith(("•", "-", "–", "—")):
        return text_value
    return BULLET_PREFIX + text_value


def get_slide_lookup(token_source: dict[str, Any]) -> dict[int, dict[str, Any]]:
    lookup: dict[int, dict[str, Any]] = {}
    for slide in token_source.get("slides", []):
        if not isinstance(slide, dict):
            continue
        slide_no = slide.get("slide_no")
        if slide_no is not None:
            lookup[int(slide_no)] = slide
    return lookup


def resolve_replacement_field(slide: dict[str, Any] | None, field_name: str) -> Any:
    if not slide:
        return ""
    if field_name in REPLACEMENT_TOP_LEVEL_FIELDS:
        return slide.get(field_name, "")
    content = slide.get("content") if isinstance(slide.get("content"), dict) else {}
    return content.get(field_name, "")


def stringify_replacement_value(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value if item not in (None, ""))
    if isinstance(value, dict):
        return "; ".join(
            f"{key}: {item}" for key, item in value.items() if item not in (None, "", [], {})
        )
    if value is None:
        return ""
    return str(value)


def determine_selected_page_type(slide: dict[str, Any] | None) -> str:
    if slide and slide.get("selected_page_type"):
        return str(slide["selected_page_type"])
    return ""


def add_tokens_for_variant(
    replacements: dict[str, str],
    tokens: list[dict[str, Any]],
    slide: dict[str, Any] | None,
    keep_unmapped_empty: bool,
    *,
    force_include: bool = False,
) -> None:
    for token in tokens:
        placeholder = str(token["placeholder"])
        field_name = str(token["field_name"])
        value = stringify_replacement_value(resolve_replacement_field(slide, field_name))
        value = ensure_bullet_prefix(value, field_name)
        if force_include or value or keep_unmapped_empty:
            replacements[placeholder] = value


def build_replacement_dict(
    token_source: dict[str, Any],
    ppt_mapping: dict[str, Any],
    keep_unmapped_empty: bool,
    *,
    renderer_spec_path: Path,
    ppt_mapping_path: Path,
) -> dict[str, str]:
    slide_lookup = get_slide_lookup(token_source)
    replacements: dict[str, str] = {}

    for mapping_slide in ppt_mapping.get("slides", []):
        slide_no = int(mapping_slide["slide_no"])
        slide = slide_lookup.get(slide_no)

        if "tokens" in mapping_slide:
            add_tokens_for_variant(
                replacements,
                mapping_slide["tokens"],
                slide,
                keep_unmapped_empty,
                force_include=True,
            )
            continue

        controlled_variants = mapping_slide.get("controlled_variants", {})
        selected_page_type = determine_selected_page_type(slide)

        if controlled_variants and not selected_page_type:
            raise ValueError(
                f"Missing selected_page_type for slide_no={slide_no}, slide_key={mapping_slide.get('slide_key', '')}. "
                f"Expected one of: {', '.join(controlled_variants.keys())}. "
                f"Checked renderer_spec={renderer_spec_path}."
            )
        if selected_page_type and selected_page_type not in controlled_variants:
            allowed = ", ".join(controlled_variants.keys())
            raise ValueError(
                f"Invalid selected_page_type in slide_no={slide_no}, slide_key={mapping_slide.get('slide_key', '')}. "
                f"Found '{selected_page_type}' in renderer-spec-derived token source={renderer_spec_path}. "
                f"Allowed values: {allowed}. Mapping file: {ppt_mapping_path}."
            )

        for page_type, variant in controlled_variants.items():
            is_active = page_type == selected_page_type
            if is_active:
                add_tokens_for_variant(
                    replacements,
                    variant.get("tokens", []),
                    slide,
                    keep_unmapped_empty,
                    force_include=True,
                )
            else:
                for token in variant.get("tokens", []):
                    replacements[str(token["placeholder"])] = ""

    return replacements


def build_token_source_from_renderer_spec(renderer_spec: dict[str, Any]) -> dict[str, Any]:
    result = build_token_source(renderer_spec)
    warnings = result.get("warnings") or []
    policy = renderer_spec.get("rendering_policy") if isinstance(renderer_spec.get("rendering_policy"), dict) else {}
    strict_layout = str(policy.get("template_contract_mode") or "style_guided") == "strict_layout"
    blocking = []
    if strict_layout:
        blocking = [
            warning for warning in warnings
            if "missing active body_copy fields" in warning
            or "empty active body_copy fields" in warning
            or "extra body_copy fields ignored" in warning
        ]
    if blocking:
        raise ValueError("renderer_spec cannot be converted into token source: " + "; ".join(blocking))
    return result["token_source"]


def template_contract_mode(run_dir: Path, renderer_spec: dict[str, Any] | None = None) -> str:
    sources: list[dict[str, Any]] = []
    if isinstance(renderer_spec, dict):
        sources.append(renderer_spec)
    for path in (
        run_dir / "artifacts/rendering_policy.json",
        run_dir / "artifacts/template_selection.json",
    ):
        if path.exists():
            try:
                item = _json(path)
            except Exception:
                item = {}
            if isinstance(item, dict):
                sources.append(item)
    for source in sources:
        nested = source.get("rendering_policy")
        if isinstance(nested, dict):
            mode = str(nested.get("template_contract_mode") or "").strip()
            if mode:
                return mode if mode in {"style_guided", "strict_layout"} else "style_guided"
        mode = str(source.get("template_contract_mode") or "").strip()
        if mode:
            return mode if mode in {"style_guided", "strict_layout"} else "style_guided"
        rendering = source.get("rendering")
        if isinstance(rendering, dict):
            mode = str(rendering.get("template_contract_mode") or "").strip()
            if mode:
                return mode if mode in {"style_guided", "strict_layout"} else "style_guided"
    return "style_guided"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    echo: bool = True,
) -> None:
    printable = " ".join(str(part) for part in cmd)
    if echo:
        print(f"[pipeline] {printable}")
    subprocess.run([str(part) for part in cmd], cwd=str(cwd or ROOT_DIR), env=env, check=True)


def _run_returncode(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> int:
    printable = " ".join(str(part) for part in cmd)
    print(f"[pipeline] {printable}")
    completed = subprocess.run([str(part) for part in cmd], cwd=str(cwd or ROOT_DIR), env=env, check=False)
    return completed.returncode


def _ensure_run_dir(run_dir: Path) -> Path:
    run_dir = run_dir.resolve()
    if not run_dir.exists() or not run_dir.is_dir():
        raise PipelineError(f"run directory not found: {run_dir}")
    if run_dir.name == "runs":
        raise PipelineError("run-dir points to a runs/ directory; pass the concrete attempt directory")
    return run_dir


def _preflight(run_dir: Path) -> None:
    required = [
        "banker_page_pack.json",
        "template_registry.json",
        "deck_blueprint.json",
        "page_evidence_contract.json",
        "renderer_spec.json",
    ]
    missing = [rel for rel in required if not (run_dir / rel).exists()]
    if missing:
        state = build_run_status(run_dir)
        raise PipelineError(
            "run is not ready for deterministic PPT rendering. "
            f"missing={missing}. current_stage={state.get('current_stage')} status={state.get('status')}. "
            "Run scripts/pipeline.py next --run-dir <run_dir> and repair the upstream artifact first."
        )


def _python_import_check(python_cmd: str, module_name: str) -> dict[str, Any]:
    code = (
        "import importlib, json\n"
        f"module_name = {module_name!r}\n"
        "try:\n"
        "    module = importlib.import_module(module_name)\n"
        "    print(json.dumps({'module': module_name, 'available': True, 'version': str(getattr(module, '__version__', '')), 'error': ''}))\n"
        "except Exception as exc:\n"
        "    print(json.dumps({'module': module_name, 'available': False, 'version': '', 'error': type(exc).__name__ + ': ' + str(exc)}))\n"
    )
    completed = subprocess.run([str(python_cmd), "-c", code], cwd=str(ROOT_DIR), text=True, capture_output=True, check=False)
    try:
        payload = json.loads(completed.stdout or "{}")
    except JSONDecodeError:
        payload = {"module": module_name, "available": False, "version": "", "error": completed.stderr.strip() or completed.stdout.strip()}
    if completed.returncode != 0 and not payload.get("error"):
        payload["error"] = completed.stderr.strip() or f"{python_cmd} returned {completed.returncode}"
    return payload


def _searxng_config() -> tuple[bool, str]:
    for env_var in SEARXNG_ENV_VARS:
        value = str(os.environ.get(env_var, "")).strip()
        if value:
            return True, value
    return False, ""


def _runtime_dependency_payload(python_cmd: str) -> tuple[dict[str, Any], list[str]]:
    required_checks: dict[str, Any] = {}
    missing_required: list[str] = []
    for item in REQUIRED_IMPORTS:
        result = _python_import_check(python_cmd, item["module"])
        required_checks[item["package"]] = result
        if not result.get("available"):
            missing_required.append(item["package"])

    search_providers: dict[str, bool] = {}
    search_provider_details: dict[str, Any] = {}
    searxng_configured, searxng_url = _searxng_config()
    for provider, module_names in SEARCH_MODULE_GROUPS.items():
        checks = [_python_import_check(python_cmd, module_name) for module_name in module_names]
        search_provider_details[provider] = checks
        search_providers[provider] = any(item.get("available") for item in checks)
    search_provider_details["searxng"] = {
        "configured": searxng_configured,
        "url": searxng_url,
        "module_checks": [],
        "env_ready": searxng_configured,
    }
    search_providers["searxng"] = searxng_configured

    pdf_module_checks = {
        name: _python_import_check(python_cmd, module_name)
        for name, module_name in PDF_EXTRACTION_MODULES.items()
    }
    pdf_command_checks = {
        name: {"command": name, "available": bool(shutil.which(name)), "path": shutil.which(name) or ""}
        for name in PDF_EXTRACTION_COMMANDS
    }
    has_pdf_extraction = any(item.get("available") for item in pdf_module_checks.values()) or any(
        item.get("available") for item in pdf_command_checks.values()
    )
    has_python_search_connector = any(search_providers.values())
    is_ready_for_ppt_pipeline = not missing_required
    payload = {
        "python": python_cmd,
        "required": required_checks,
        "search_providers": search_providers,
        "search_provider_details": search_provider_details,
        "search_connectors_optional": True,
        "agent_native_web_search_expected": True,
        "agent_native_web_search_note": (
            "Python search connectors are optional diagnostics. Formal research may use the agent's native web search, "
            "reviewable user-provided sources, and manual URL/PDF intake when those sources are opened and recorded."
        ),
        "pdf_extraction": {
            "modules": pdf_module_checks,
            "commands": pdf_command_checks,
        },
        "has_pdf_extraction": has_pdf_extraction,
        "manual_source_mode_supported": True,
        "manual_source_mode_is_fallback": False,
        "paid_search_optional": True,
        "paid_search_available": search_providers.get("tavily", False) or search_providers.get("duckduckgo", False),
        "is_ready_for_ppt_pipeline": is_ready_for_ppt_pipeline,
        "is_ready_for_e2e_research": is_ready_for_ppt_pipeline,
        "python_connector_research_ready": has_python_search_connector and has_pdf_extraction,
        "has_search_provider": has_python_search_connector,
        "has_python_search_connector": has_python_search_connector,
        "has_fallback_search": True,
    }
    return payload, missing_required


def _runtime_readiness_stderr(payload: dict[str, Any], missing_required: list[str]) -> str:
    lines: list[str] = []
    if missing_required:
        lines.append("ERROR: Required import(s) failed: " + ", ".join(missing_required))
    if not payload.get("has_search_provider"):
        lines.append(
            "WARN: No optional Python web-search connector is configured. "
            "Use agent-native web search, reviewable user-provided sources, or manual URL/PDF intake; "
            "record opened sources and limitations in the research state."
        )
        search_providers = payload.get("search_providers") if isinstance(payload.get("search_providers"), dict) else {}
        if not search_providers.get("searxng"):
            lines.append("Optional: set SEARXNG_BASE_URL for Python connector execution.")
    if not payload.get("has_pdf_extraction"):
        lines.append(
            "WARN: No Python PDF extraction capability found. Use agent-native PDF reading, user-provided extracts, "
            "or manual source review; record limitations before relying on filings/prospectuses/annual reports."
        )
    return "\n".join(lines)


def _check_runtime_readiness(run_dir: Path, python_cmd: str, *, strict: bool = False) -> bool:
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    payload, missing_required = _runtime_dependency_payload(str(python_cmd))
    stderr = _runtime_readiness_stderr(payload, missing_required)
    (artifacts / "runtime_dependencies.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if stderr:
        (artifacts / "runtime_dependencies.stderr.txt").write_text(stderr + "\n", encoding="utf-8")
    else:
        (artifacts / "runtime_dependencies.stderr.txt").unlink(missing_ok=True)
    if missing_required:
        message = (
            "runtime readiness diagnostics found missing required PPT/runtime imports. "
            f"See {artifacts / 'runtime_dependencies.json'} and {artifacts / 'runtime_dependencies.stderr.txt'}."
        )
        if strict:
            raise PipelineError(message)
        print(f"[pipeline] WARNING: {message}")
        return False
    if stderr:
        print(
            "[pipeline] NOTE: runtime diagnostics recorded optional connector/PDF advisories. "
            f"See {artifacts / 'runtime_dependencies.json'} and {artifacts / 'runtime_dependencies.stderr.txt'}."
        )
    return True


def validate_artifact_entry(
    run_dir: Path,
    artifact: str,
    *,
    path: Path | None = None,
    output: Path | None = None,
    print_result: bool = True,
) -> dict[str, Any]:
    run_dir = _ensure_run_dir(run_dir)
    if artifact not in ARTIFACT_PATHS:
        available = ", ".join(PUBLIC_VALIDATE_ARTIFACTS)
        raise PipelineError(
            f"unknown artifact '{artifact}'. Public owner-facing artifacts: {available}. "
            "Internal compiled artifacts are accepted only by exact name when a status report asks for them."
        )
    errors, warnings = run_artifact_validation(artifact, run_dir, path)
    owner_guidance = helper_check_guidance(artifact, errors, warnings)
    result = {
        "artifact": artifact,
        "review_outcome": owner_guidance["status"],
        "owner_repair_guidance": owner_guidance,
        "helper_check_policy": "structure_only",
        "is_valid": not errors,
        "run_dir": str(run_dir),
        "path": str(path or run_dir / ARTIFACT_PATHS[artifact]),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
    if artifact == "banker_page_pack":
        diagnostics = banker_page_pack_template_diagnostics(run_dir, path)
        diagnostics_path = run_dir / "artifacts" / "banker_page_pack_template_diagnostics.json"
        diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
        diagnostics_path.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result["template_diagnostics_path"] = str(diagnostics_path)
    output_path = output or run_dir / VALIDATION_OUTPUTS.get(artifact, f"artifacts/{artifact}_validation.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if print_result:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def _validate_artifact(
    run_dir: Path,
    python_cmd: str,
    artifact: str,
    output: Path | None = None,
    *,
    print_result: bool = True,
) -> None:
    result = validate_artifact_entry(run_dir, artifact, output=output, print_result=print_result)
    if not result["is_valid"]:
        raise PipelineError(f"{artifact} validation failed")


def _readiness_note_from_payload(readiness: Any) -> str:
    if isinstance(readiness, str):
        return readiness.strip()
    if not isinstance(readiness, dict):
        return ""
    parts = [
        readiness.get("readiness_note"),
        readiness.get("decision_note"),
        readiness.get("targeted_research_rationale"),
        readiness.get("rationale"),
        readiness.get("reason"),
    ]
    return " ".join(str(part).strip() for part in parts if str(part or "").strip())


def _readiness_business_action(readiness: Any) -> str:
    if not isinstance(readiness, dict):
        return ""
    return str(readiness.get("business_action") or "").strip().lower()


def _explicit_qc_user_decision_basis(readiness: Any) -> str:
    if not isinstance(readiness, dict):
        return ""
    if readiness.get("targeted_research_loop_exhausted") is True:
        return "targeted_research_loop_exhausted"
    if readiness.get("source_unavailable") is True or readiness.get("realistic_sources_unavailable") is True:
        return "source_unavailable"
    if readiness.get("operator_authorized_stop_research") is True:
        return "operator_authorized_stop_research"
    source_limit = readiness.get("source_limit")
    if isinstance(source_limit, dict):
        if source_limit.get("source_unavailable") is True or source_limit.get("realistic_sources_unavailable") is True:
            return "source_limit.source_unavailable"
        if source_limit.get("no_material_page_impact") is True:
            return "source_limit.no_material_page_impact"
    return ""


def _qc_user_decision_is_authorized(run_dir: Path, readiness: Any) -> tuple[bool, str]:
    loop_state = _research_queue_loop_state(run_dir)
    if loop_state.get("loop_exhausted"):
        return True, "bounded targeted research queue is exhausted"
    basis = _explicit_qc_user_decision_basis(readiness)
    if basis:
        return True, f"deliverable_readiness.{basis}=true"
    return False, (
        "qc_user_decision needs an exhausted research queue, a structured source-unavailable/no-page-impact basis, "
        "or explicit operator authorization; otherwise route to bounded targeted research first"
    )


def _llm_deliverable_readiness_state(run_dir: Path) -> dict[str, Any]:
    page_pack_path = run_dir / "banker_page_pack.json"
    if not page_pack_path.exists():
        return {
            "is_client_ready": False,
            "reason": "banker_page_pack.json is missing",
            "route_if_not_ready": "author_banker_page_pack",
            "has_explicit_decision": False,
        }
    try:
        page_pack = _json(page_pack_path)
    except Exception as exc:
        return {
            "is_client_ready": False,
            "reason": f"cannot read banker_page_pack.json: {exc}",
            "route_if_not_ready": "repair_banker_page_pack",
            "has_explicit_decision": False,
        }
    readiness = page_pack.get("deliverable_readiness")
    note = _readiness_note_from_payload(readiness)
    business_action = _readiness_business_action(readiness)
    business_action_routes = {
        "client_ready": "client_ready",
        "targeted_research": "bounded_targeted_research_then_rerender",
        "repair_page_pack": "repair_banker_page_pack_before_render",
        "qc_user_decision": "qc_or_user_decision_after_source_limit",
    }
    route = business_action_routes.get(business_action, "")
    has_decision = bool(route)
    enough = business_action == "client_ready"
    targeted_research = business_action == "targeted_research"
    research_limit_reached = business_action == "qc_user_decision"
    reasons: list[str] = []
    if not has_decision:
        if business_action:
            reasons.append(
                "deliverable_readiness gives a nonstandard business action; state the judgment in prose and use a standard business_action only if helper automation needs it"
            )
        else:
            reasons.append(
                "banker_page_pack does not give a clear final-output next action; LLM/QC should state whether to send, repair page writing/exhibits, run one bounded research request, or ask QC/user after source limits"
            )
    elif route == "repair_banker_page_pack_before_render":
        reasons.append("page pack asks for page-pack repair before render")
    if targeted_research:
        reasons.append("page pack asks for bounded targeted research")
    if research_limit_reached:
        authorized, authorization_reason = _qc_user_decision_is_authorized(run_dir, readiness)
        if authorized:
            reasons.append(f"page pack asks for QC/user decision: {authorization_reason}")
        else:
            route = "bounded_targeted_research_then_rerender"
            targeted_research = True
            reasons.append(f"page pack asks for QC/user decision, but {authorization_reason}")
    if note:
        reasons.append(note)
    ready = bool(has_decision and enough and not targeted_research)
    if not has_decision:
        route = "finish_banker_page_pack_readiness_decision"
    return {
        "is_client_ready": ready,
        "reason": "; ".join(reasons) if reasons else "LLM authorized final delivery from the page pack",
        "route_if_not_ready": route,
        "has_explicit_decision": has_decision,
    }


def _llm_deliverable_readiness(run_dir: Path) -> tuple[bool, str]:
    state = _llm_deliverable_readiness_state(run_dir)
    return bool(state["is_client_ready"]), str(state["reason"])


def _research_loop_policy() -> dict[str, Any]:
    try:
        policy = _json(ROOT_DIR / "configs" / "research_planning_policy.json")
    except Exception:
        return {}
    queue_policy = policy.get("research_request_queue") if isinstance(policy.get("research_request_queue"), dict) else {}
    loop_policy = queue_policy.get("targeted_loop_policy") if isinstance(queue_policy.get("targeted_loop_policy"), dict) else {}
    return loop_policy


def _research_request_active_value(request: dict[str, Any]) -> bool | None:
    value = request.get("active")
    return value if isinstance(value, bool) else None


def _research_request_counts_as_active(request: dict[str, Any]) -> bool:
    active_value = _research_request_active_value(request)
    if active_value is not None:
        return active_value
    return True


def _research_queue_loop_state(run_dir: Path) -> dict[str, Any]:
    queue_path = run_dir / "artifacts" / "research_request_queue.json"
    policy = _research_loop_policy()
    policy_max_cycles = policy.get("max_cycles_before_user_or_qc_decision", 2)
    state: dict[str, Any] = {
        "queue_exists": queue_path.exists(),
        "current_cycle": None,
        "max_cycles": policy_max_cycles,
        "active_request_count": None,
        "loop_exhausted": False,
        "route": "author_targeted_research_queue",
    }
    if not queue_path.exists():
        return state
    try:
        payload = _json(queue_path)
    except Exception as exc:
        state["route"] = "repair_research_request_queue"
        state["read_error"] = str(exc)
        return state
    raw_loop_control = payload.get("loop_control")
    loop_control = raw_loop_control if isinstance(raw_loop_control, dict) else {}
    loop_control_missing = not isinstance(raw_loop_control, dict)
    raw_current_cycle = loop_control.get("current_cycle")
    declared_max = loop_control.get("max_cycles")
    latest_cycle_outcome = str(loop_control.get("latest_cycle_outcome") or "").strip()
    if isinstance(declared_max, int) and declared_max > 0:
        max_cycles = declared_max
    else:
        max_cycles = policy_max_cycles
    if isinstance(raw_current_cycle, int) and raw_current_cycle > 0:
        current_cycle = raw_current_cycle
    else:
        current_cycle = 1
    requests = payload.get("requests") if isinstance(payload.get("requests"), list) else []
    missing_active_flags = [
        idx
        for idx, request in enumerate(requests, start=1)
        if isinstance(request, dict) and _research_request_active_value(request) is None
    ]
    active_requests = [
        request
        for request in requests
        if isinstance(request, dict)
        and _research_request_counts_as_active(request)
    ]
    state.update(
        {
            "current_cycle": current_cycle,
            "max_cycles": max_cycles,
            "active_request_count": len(active_requests),
            "loop_control_missing": loop_control_missing,
            "current_cycle_defaulted": not (isinstance(raw_current_cycle, int) and raw_current_cycle > 0),
            "missing_active_flags": missing_active_flags,
        }
    )
    if not isinstance(max_cycles, int) or max_cycles < 1:
        state["route"] = "repair_research_request_queue"
        return state
    if not active_requests:
        if current_cycle >= max_cycles:
            state["loop_exhausted"] = True
            state["route"] = "qc_or_user_decision_after_loop_cap"
        elif latest_cycle_outcome:
            state["route"] = "author_narrow_next_request_or_record_source_limit"
        else:
            state["route"] = "author_targeted_request_or_record_cycle_outcome"
        return state
    if (
        current_cycle > max_cycles
        or (current_cycle >= max_cycles and latest_cycle_outcome)
    ):
        state["loop_exhausted"] = True
        state["route"] = "qc_or_user_decision_after_loop_cap"
    elif current_cycle >= max_cycles:
        state["route"] = "execute_final_targeted_cycle"
    else:
        state["route"] = "continue_targeted_research"
    return state


def _targeted_research_required_message(run_dir: Path, readiness_reason: str) -> str:
    policy = _research_loop_policy()
    max_cycles = policy.get("max_cycles_before_user_or_qc_decision", 2)
    max_requests = policy.get("max_active_requests_per_cycle", 5)
    max_searches = policy.get("max_actual_searches_per_request", 3)
    loop_state = _research_queue_loop_state(run_dir)
    if loop_state.get("loop_exhausted"):
        return (
            "LLM marked the page pack not ready for client delivery, and the bounded targeted research loop is exhausted. "
            f"Reason: {readiness_reason}. "
            f"Current cycle: {loop_state.get('current_cycle')}; max cycles: {loop_state.get('max_cycles')}; "
            f"active requests: {loop_state.get('active_request_count')}. "
            "Do not start another search loop by default. QC/user should choose whether to provide new source materials, "
            "narrow the page scope, explicitly authorize another targeted cycle, or create only a non-final research-limited review copy."
        )
    queue_path = run_dir / "artifacts" / "research_request_queue.json"
    if queue_path.exists() and loop_state.get("route") == "repair_research_request_queue":
        queue_state = "Repair the existing bounded targeted research queue before execution."
    elif queue_path.exists() and loop_state.get("active_request_count") == 0:
        if loop_state.get("route") == "author_narrow_next_request_or_record_source_limit":
            queue_state = (
                "The research queue has a prior cycle outcome but no active request, and loop budget remains. "
                "Reasoning LLM should either add one narrower next-cycle request whose answer could change deck inclusion, "
                "key data audit, or exhibit readiness, or explicitly record why sources are unavailable / another "
                "search would not change the page decision and ask QC/user for disposition."
            )
        else:
            queue_state = (
                "The research queue exists but has no active request. Reasoning LLM should either add a narrow request "
                "whose answer could change deck inclusion, key data audit, or exhibit readiness, or record the latest cycle "
                "outcome and ask QC/user to decide the remaining gap."
            )
    elif queue_path.exists():
        queue_state = "Execute or repair the existing bounded targeted research queue."
        if loop_state.get("loop_control_missing"):
            queue_state += " loop_control is omitted, so helpers assume cycle 1 and the policy cap."
        if loop_state.get("missing_active_flags"):
            queue_state += " Requests missing active are treated as active for this cycle; close resolved or exhausted requests in the queue after the cycle."
    else:
        queue_state = "Reasoning LLM should author a bounded targeted research queue before more rendering."
    return (
        "LLM marked the page pack not ready for client delivery; the next business action is targeted research before formal render. "
        f"Reason: {readiness_reason}. "
        f"{queue_state} Keep the loop bounded: max {max_cycles} targeted cycle(s), "
        f"max {max_requests} active request(s) per cycle, max {max_searches} actual search(es) per request. "
        "Only research gaps that could change deck inclusion, key data audit, or exhibit readiness. "
        "After each cycle, update request outcomes and close resolved/exhausted requests; do not rerun unchanged active requests. "
        "Use --allow-research-limited-review-render only when the operator explicitly wants a layout or editorial-direction review copy."
    )


def _readiness_decision_required_message(readiness_reason: str) -> str:
    return (
        "banker_page_pack is structurally valid, but it does not give a clear final-output next action. "
        f"Reason: {readiness_reason}. "
        "Generation/Reasoning LLM should state the business action: send the section, repair page writing/exhibits, "
        "run one bounded targeted research request, or ask QC/user after source limits. Create a research-limited review copy only after the loop cap, clear "
        "source unavailability, or explicit operator direction. Do not render a final PPT from an undecided page pack."
    )


def _page_pack_missing_render_message(run_dir: Path) -> str:
    return (
        "banker_page_pack.json is missing, so render cannot start. "
        "Generation LLM should author the banker page pack first: client-facing page arguments, exhibits, "
        "source notes, caveats, and deliverable_readiness. "
        f"Run status for next owner action: {run_dir / 'artifacts/status_report.json'} can be generated with "
        "scripts/pipeline.py next --run-dir <run_dir>."
    )


def _page_pack_repair_required_message(readiness_reason: str) -> str:
    return (
        "LLM marked the page pack not ready for client delivery, but did not identify a targeted evidence gap "
        "that would change deck inclusion, key data audit, or exhibit readiness. "
        f"Reason: {readiness_reason}. "
        "Repair banker_page_pack first: client-facing wording, page density, source caveats, exhibit design, "
        "or claim scope. Route to targeted research only after naming the specific evidence question and the "
        "page decision it could change."
    )


def _source_limit_decision_required_message(readiness_reason: str) -> str:
    return (
        "LLM marked the page pack not ready for client delivery because the bounded targeted research loop is exhausted "
        "or realistic source availability has been reached. "
        f"Reason: {readiness_reason}. "
        "Do not start another search loop by default. QC/user should choose whether to provide new source materials, "
        "narrow the page scope, explicitly authorize another targeted cycle, or create only a non-final research-limited review copy."
    )


def _research_limited_owner_action(readiness_state: dict[str, Any]) -> str:
    if readiness_state.get("route_if_not_ready") == "qc_or_user_decision_after_source_limit":
        return (
            "Default owner action is QC/user decision on the remaining source limit: provide new source material, "
            "narrow the page scope, explicitly authorize another targeted cycle, or create only a non-final research-limited review copy."
        )
    return (
        "Default owner action is targeted research on the unresolved evidence gaps, then refresh the page pack and render through the standard output path."
    )


def _mark_research_limited_review(run_dir: Path, reason: str | None = None, owner_action: str | None = None) -> None:
    for name in (CLEAN_PPT, FILLED_PPT):
        source = run_dir / name
        dest = run_dir / f"RESEARCH_LIMITED_REVIEW_{name}"
        if source.exists():
            if dest.exists():
                dest.unlink()
            source.rename(dest)
    marker = run_dir / "RESEARCH_LIMITED_REVIEW_OUTPUT.txt"
    message = (
        "Generated PPT is a research-limited review copy, not a final client delivery.\n"
        "Any generated PPT was renamed with RESEARCH_LIMITED_REVIEW_ and must be used only to inspect layout or editorial direction.\n"
        f"Reason: {reason or 'upstream readiness or helper checks did not pass'}.\n"
        f"{owner_action or _research_limited_owner_action({})}\n"
    )
    marker.write_text(message, encoding="utf-8")


def _clear_research_limited_review(run_dir: Path) -> None:
    for name in (CLEAN_PPT, FILLED_PPT):
        review_copy = run_dir / f"RESEARCH_LIMITED_REVIEW_{name}"
        if review_copy.exists():
            review_copy.unlink()
    marker = run_dir / "RESEARCH_LIMITED_REVIEW_OUTPUT.txt"
    if marker.exists():
        marker.unlink()


def _clear_draft_state(run_dir: Path) -> None:
    """Remove draft-only markers before a formal render attempt.

    Draft output is an internal preview path, not a permanent run mode. Once the
    upstream package is repaired, a formal render in the same attempt should be
    able to replace draft flags with formal run flags. Explicit debug markers
    are intentionally not cleared here.
    """

    run_flags_path = run_dir / "artifacts" / "run_flags.json"
    existing = _json(run_flags_path)
    if existing.get("draft_output_only") is True and existing.get("debug_output_only") is True:
        run_flags_path.unlink(missing_ok=True)
    for rel in (
        "DRAFT_RESEARCH_LIMITED_REVIEW.txt",
        "artifacts/draft_delivery_manifest.json",
    ):
        path = run_dir / rel
        if path.exists():
            path.unlink()


def _write_run_flags(run_dir: Path, *, entrypoint: str, preflight_skipped: bool = False) -> None:
    """Record formal pipeline mode for final delivery.

    The Python pipeline is the formal controller, so it writes the
    package-of-record flags itself. Existing debug flags are preserved so a
    debug run cannot be accidentally promoted by calling finalize.
    """

    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    path = artifacts / "run_flags.json"
    existing = _json(path)
    if (run_dir / "DEBUG_OUTPUT_ONLY.txt").exists():
        return
    if existing.get("debug_output_only") is True and existing.get("draft_output_only") is not True:
        return
    payload = {
        "schema_version": "run_flags_v1",
        "research_readiness": 1,
        "banker_page_pack_layer": 1,
        "quality_readiness": 1,
        "source_run_dir": str(run_dir),
        "output_run_dir": str(run_dir),
        "package_of_record": str(run_dir),
        "debug_output_only": False,
        "debug_reason": "",
        "pipeline_entrypoint": entrypoint,
        "preflight_skipped": preflight_skipped,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _resolve_template_path(path_text: str, run_dir: Path) -> Path:
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return path
    candidate = (run_dir / path).resolve()
    if candidate.exists():
        return candidate
    if path.exists():
        return path.resolve()
    return (ROOT_DIR / path).resolve()


def _registered_template_material(run_dir: Path) -> tuple[Path | None, str]:
    manifest = _json(run_dir / "artifacts/material_manifest.json")
    for item in manifest.get("materials") or []:
        if not isinstance(item, dict):
            continue
        source_type = str(item.get("source_type") or "").strip().lower()
        material_kind = str(item.get("material_kind") or "").strip().lower()
        path_text = str(item.get("file_path_or_url") or "").strip()
        if not path_text.lower().endswith((".pptx", ".potx", ".ppt")):
            continue
        if source_type == "ppt_template" or material_kind == "ppt_template":
            path = _resolve_template_path(path_text, run_dir)
            if path.exists():
                return path, str(item.get("material_id") or "")
    return None, ""


def _select_template_for_run(run_dir: Path, python_cmd: str, explicit_template: Path | None = None) -> Path:
    """Resolve the effective PPT template for this run.

    This is deterministic bookkeeping inside the render controller, not a
    separate role step.
    """

    del python_cmd
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    selection_path = artifacts / "template_selection.json"
    selected_material_id = ""
    if explicit_template is not None:
        selected = explicit_template.expanduser().resolve()
        source = "explicit_user_template"
        reason = "explicit --template value provided"
    else:
        registered, selected_material_id = _registered_template_material(run_dir)
        if registered is not None:
            selected = registered.resolve()
            source = "user_provided_template_material"
            reason = "first registered ppt_template material"
        else:
            selected = TEMPLATE.resolve()
            source = "bundled_default"
            reason = "no user-provided PPT template was registered"
    payload = {
        "schema_version": "template_selection_v1",
        "selected_template_path": str(selected),
        "selection_source": source,
        "selected_material_id": selected_material_id,
        "bundled_template_path": str(TEMPLATE.resolve()),
        "selection_rule": "explicit_user_template > registered ppt_template material > bundled_default",
        "reason": reason,
        "selected_template_exists": selected.exists(),
        "created_by": "scripts/pipeline.py",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    selection_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not selected.exists():
        raise PipelineError(f"selected template does not exist: {selected}")
    return selected


def validate_pre_ppt(run_dir: Path, python_cmd: str, *, template_path: Path | None = None) -> None:
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(exist_ok=True)
    template_path = _select_template_for_run(run_dir, python_cmd, template_path)
    template_profile_path = artifacts / "template_profile.json"
    _run(
        [
            python_cmd,
            _internal_script("template/template_analyzer.py"),
            "--template",
            template_path,
            "--output",
            template_profile_path,
        ]
    )
    _run(
        [
            python_cmd,
            _internal_script("template/template_analyzer.py"),
            "fit",
            "--renderer-spec",
            run_dir / "renderer_spec.json",
            "--template-profile",
            template_profile_path,
            "--output",
            artifacts / "template_fit_validation.json",
            "--fit-plan-output",
            artifacts / "template_fit_plan.json",
        ]
    )
    _validate_artifact(run_dir, python_cmd, "pre_ppt", artifacts / "pre_ppt_readiness.json")


def render(
    run_dir: Path,
    python_cmd: str,
    *,
    skip_preflight: bool = False,
    template_path: Path | None = None,
    strict_runtime_readiness: bool = False,
    allow_research_limited_review_render: bool = False,
) -> None:
    run_dir = _ensure_run_dir(run_dir)
    if not (run_dir / "banker_page_pack.json").exists():
        raise PipelineError(_page_pack_missing_render_message(run_dir))
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(exist_ok=True)
    pre_render_readiness_state: dict[str, Any] = {}
    pre_render_readiness_state = _llm_deliverable_readiness_state(run_dir)
    if not pre_render_readiness_state["is_client_ready"]:
        readiness_reason = str(pre_render_readiness_state["reason"])
        route = pre_render_readiness_state.get("route_if_not_ready")
        if route == "finish_banker_page_pack_readiness_decision":
            raise PipelineError(_readiness_decision_required_message(readiness_reason))
        if route == "repair_banker_page_pack_before_render":
            raise PipelineError(_page_pack_repair_required_message(readiness_reason))
        if route == "qc_or_user_decision_after_source_limit" and not allow_research_limited_review_render:
            raise PipelineError(_source_limit_decision_required_message(readiness_reason))
        if not allow_research_limited_review_render:
            raise PipelineError(_targeted_research_required_message(run_dir, readiness_reason))
    template_path = _select_template_for_run(run_dir, python_cmd, template_path)
    _clear_draft_state(run_dir)
    _check_runtime_readiness(run_dir, python_cmd, strict=strict_runtime_readiness)
    build_template_registry(run_dir, python_cmd, template_path=template_path)
    compile_page_pack(run_dir, python_cmd)
    if not skip_preflight:
        _preflight(run_dir)
    _write_run_flags(run_dir, entrypoint="scripts/pipeline.py render", preflight_skipped=skip_preflight)

    try:
        readiness_state = pre_render_readiness_state or _llm_deliverable_readiness_state(run_dir)
        validate_pre_ppt(run_dir, python_cmd, template_path=template_path)
        renderer_spec = _json(run_dir / "renderer_spec.json")
        mode = template_contract_mode(run_dir, renderer_spec)
        if mode == "strict_layout":
            _write_template_token_report(template_path, PPT_MAPPING, artifacts / "template_token_check.json")
            replacements = build_replacement_dict(
                build_token_source_from_renderer_spec(renderer_spec),
                _json(PPT_MAPPING),
                False,
                renderer_spec_path=run_dir / "renderer_spec.json",
                ppt_mapping_path=PPT_MAPPING,
            )
            _write_json(run_dir / "replacement_dict.json", replacements)
            _validate_artifact(run_dir, python_cmd, "replacement_dict", artifacts / "replacement_dict_validation.json")
            _write_json(
                artifacts / "fill_ppt_tokens.log.json",
                fill_ppt(template_path, run_dir / "replacement_dict.json", run_dir / FILLED_PPT),
            )
            _write_json(
                artifacts / "clean_filled_ppt.log.json",
                clean_presentation(run_dir / FILLED_PPT, run_dir / "renderer_spec.json", run_dir / CLEAN_PPT),
            )
            _run(
                [
                    python_cmd,
                    _internal_script("output/postprocess_ppt_visuals.py"),
                    "--input-ppt",
                    run_dir / CLEAN_PPT,
                    "--renderer-spec",
                    run_dir / "renderer_spec.json",
                    "--output",
                    run_dir / CLEAN_PPT,
                    "--template-profile",
                    artifacts / "template_profile.json",
                    "--render-layouts",
                    RENDER_LAYOUTS,
                    "--log",
                    artifacts / "postprocess_ppt_visuals.log.json",
                    "--fail-on-unrendered",
                ]
            )
        else:
            _run(
                [
                    python_cmd,
                    _internal_script("output/postprocess_ppt_visuals.py"),
                    "--style-guided-render",
                    "--input-ppt",
                    template_path,
                    "--renderer-spec",
                    run_dir / "renderer_spec.json",
                    "--output",
                    run_dir / FILLED_PPT,
                    "--template-profile",
                    artifacts / "template_profile.json",
                    "--render-layouts",
                    RENDER_LAYOUTS,
                    "--log",
                    artifacts / "postprocess_ppt_visuals.log.json",
                ]
            )
            shutil.copy2(run_dir / FILLED_PPT, run_dir / CLEAN_PPT)
            _write_json(
                artifacts / "clean_filled_ppt.log.json",
                {
                    "input_pptx": str(run_dir / FILLED_PPT),
                    "output_pptx": str(run_dir / CLEAN_PPT),
                    "render_mode": "style_guided",
                    "template_contract_mode": mode,
                },
            )
        _validate_artifact(run_dir, python_cmd, "filled_ppt", run_dir / "filled_ppt_validation.json")
        finalize(run_dir, python_cmd, require_final_delivery_authorization=False)
        if readiness_state["is_client_ready"]:
            _clear_research_limited_review(run_dir)
        else:
            _mark_research_limited_review(
                run_dir,
                reason=str(readiness_state["reason"]),
                owner_action=_research_limited_owner_action(readiness_state),
            )
            validate_artifact_entry(
                run_dir,
                "final_delivery",
                output=artifacts / "final_delivery_validation.json",
            )
    except Exception:
        _mark_research_limited_review(run_dir, reason="render or final delivery mechanics failed")
        raise


def finalize(run_dir: Path, python_cmd: str, *, require_final_delivery_authorization: bool) -> None:
    run_dir = _ensure_run_dir(run_dir)
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(exist_ok=True)
    _write_run_flags(run_dir, entrypoint="scripts/pipeline.py finalize")
    result = validate_artifact_entry(
        run_dir,
        "final_delivery",
        output=artifacts / "final_delivery_validation.json",
    )
    if not result["is_valid"]:
        _mark_research_limited_review(run_dir, reason="final delivery helper check failed")
        raise PipelineError(
            "final delivery readiness check failed; see artifacts/final_delivery_validation.json "
            "and artifacts/run_quality_summary.json for repair targets"
        )
    readiness_state = _llm_deliverable_readiness_state(run_dir)
    if require_final_delivery_authorization and not readiness_state["is_client_ready"]:
        readiness_reason = str(readiness_state["reason"])
        _mark_research_limited_review(run_dir, reason=readiness_reason)
        if readiness_state.get("route_if_not_ready") == "finish_banker_page_pack_readiness_decision":
            raise PipelineError(
                "LLM deliverable_readiness is undecided; final delivery requires a page-pack readiness decision "
                "before rendering can be treated as final"
            )
        if readiness_state.get("route_if_not_ready") == "repair_banker_page_pack_before_render":
            raise PipelineError(
                "LLM deliverable_readiness says the page pack needs client-facing story, density, source-caveat, "
                "exhibit-design, or claim-scope repair before final delivery. Do not route this to research unless "
                "a specific evidence gap could change deck inclusion, key data audit, or exhibit readiness."
            )
        if readiness_state.get("route_if_not_ready") == "qc_or_user_decision_after_source_limit":
            raise PipelineError(
                "LLM deliverable_readiness says bounded targeted research is exhausted or realistic sources are unavailable. "
                "Final delivery requires QC/user acceptance, new source material, or a narrower page scope; "
                "do not start another search loop without explicit operator direction."
            )
        raise PipelineError(
            "LLM deliverable_readiness has not authorized final client delivery; render can be used for review only when explicitly allowed, "
            "but final delivery requires upstream targeted research or explicit QC acceptance after the loop cap"
        )
    summary = build_run_status(run_dir)
    summary["view"] = "summary"
    write_status_json(summary, artifacts / "status_report.json")
    if run_dir.name.startswith("attempt_"):
        runs_dir = run_dir.parent
        (runs_dir / "ACTIVE_ATTEMPT.txt").write_text(run_dir.name + "\n", encoding="utf-8")


def start_brief(
    run_dir: Path,
    python_cmd: str,
    *,
    case_name: str,
    brief_text: str | None = None,
    brief_file: Path | None = None,
    files: list[str] | None = None,
    urls: list[str] | None = None,
    template_files: list[str] | None = None,
    target_company: str = "",
    transaction_type: str = "",
    industry: str = "",
    subsector: str = "",
    geography: str = "",
) -> None:
    args: list[Any] = [
        python_cmd,
        _internal_script("material-intake/ingest_materials.py"),
        "start-brief",
        "--case-name",
        case_name,
        "--run-dir",
        run_dir,
    ]
    if brief_text:
        args.extend(["--brief-text", brief_text])
    if brief_file:
        args.extend(["--brief-file", brief_file])
    for item in files or []:
        args.extend(["--file", item])
    for item in urls or []:
        args.extend(["--url", item])
    for item in template_files or []:
        args.extend(["--template-file", item])
    for flag, value in (
        ("--target-company", target_company),
        ("--transaction-type", transaction_type),
        ("--industry", industry),
        ("--subsector", subsector),
        ("--geography", geography),
    ):
        if value:
            args.extend([flag, value])
    _run(args, echo=False)
    _validate_artifact(
        run_dir,
        python_cmd,
        "input_card",
        run_dir / "artifacts/input_card_validation.json",
        print_result=False,
    )
    _validate_artifact(
        run_dir,
        python_cmd,
        "material_extracts",
        run_dir / "artifacts/material_extracts_validation.json",
        print_result=False,
    )


def compile_page_pack(run_dir: Path, python_cmd: str, *, template_path: Path | None = None) -> None:
    run_dir = _ensure_run_dir(run_dir)
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(exist_ok=True)
    if not (run_dir / "banker_page_pack.json").exists():
        raise PipelineError("cannot compile page pack: missing banker_page_pack.json")
    if template_path is not None or not (run_dir / "template_registry.json").exists():
        build_template_registry(run_dir, python_cmd, template_path=template_path)
    _validate_artifact(run_dir, python_cmd, "banker_page_pack", artifacts / "banker_page_pack_validation.json")
    _validate_artifact(run_dir, python_cmd, "template_registry", artifacts / "template_registry_validation.json")
    print("[pipeline] refresh structured-render helpers from banker_page_pack.json")
    deck_blueprint, page_contract, renderer_spec = compile_banker_page_pack(
        _json(run_dir / "banker_page_pack.json"),
        _json(run_dir / "template_registry.json"),
    )
    _write_json(run_dir / "deck_blueprint.json", deck_blueprint)
    _write_json(run_dir / "page_evidence_contract.json", page_contract)
    _write_json(run_dir / "renderer_spec.json", renderer_spec)
    _validate_artifact(run_dir, python_cmd, "deck_blueprint", run_dir / "artifacts/deck_blueprint_validation.json")
    _validate_artifact(run_dir, python_cmd, "page_evidence_contract", run_dir / "artifacts/page_evidence_contract_validation.json")
    _validate_artifact(run_dir, python_cmd, "renderer_spec", run_dir / "artifacts/renderer_spec_validation.json")


def build_template_registry(run_dir: Path, python_cmd: str, *, template_path: Path | None = None) -> None:
    run_dir = _ensure_run_dir(run_dir)
    template_path = _select_template_for_run(run_dir, python_cmd, template_path)
    _run(
        [
            python_cmd,
            _internal_script("template/template_analyzer.py"),
            "registry",
            "--template",
            template_path,
            "--output",
            run_dir / "template_registry.json",
        ]
    )
    _validate_artifact(run_dir, python_cmd, "template_registry", run_dir / "artifacts/template_registry_validation.json")


def status_view(
    run_dir: Path,
    view: str,
    output: Path | None = None,
    markdown_output: Path | None = None,
    *,
    include_debug_commands: bool = False,
) -> None:
    run_dir = _ensure_run_dir(run_dir)
    report = build_run_status(run_dir, include_debug_commands=include_debug_commands)
    if view == "status":
        report["view"] = view
    if output is None and view == "next":
        output = run_dir / "artifacts/status_report.json"
    write_status_json(report, output)
    if markdown_output:
        write_status_markdown(report, markdown_output)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _hidden_review_command(argv: list[str]) -> int | None:
    root_parser = argparse.ArgumentParser(add_help=False)
    root_parser.add_argument("--python", default=sys.executable)
    try:
        _root_args, rest = root_parser.parse_known_args(argv)
    except SystemExit:
        return None
    if not rest or rest[0] != "review":
        return None
    parser = argparse.ArgumentParser(
        prog="pipeline.py review",
        description=(
            "Internal/debug helper-check command. Default status stays owner-action focused; "
            "use this only when exact file/ID/render-input checks are needed."
        ),
    )
    parser.add_argument("--run-dir", required=True)
    parser.add_argument(
        "--artifact",
        required=True,
        metavar=PUBLIC_VALIDATE_ARTIFACTS_HELP,
        help=(
            "Owner-facing artifact to check. Internal compiled artifacts remain accepted by exact name "
            "when a status report requests a helper check."
        ),
    )
    parser.add_argument("--path", help="Optional explicit artifact path.")
    parser.add_argument("--output")
    args = parser.parse_args(rest[1:])
    try:
        result = validate_artifact_entry(
            _ensure_run_dir(Path(args.run_dir)),
            args.artifact,
            path=Path(args.path) if args.path else None,
            output=Path(args.output) if args.output else None,
        )
        if not result["is_valid"]:
            return 1
    except subprocess.CalledProcessError as exc:
        return exc.returncode or 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    hidden_review_result = _hidden_review_command(raw_argv)
    if hidden_review_result is not None:
        return hidden_review_result
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable, help="Python interpreter used for child scripts.")
    sub = parser.add_subparsers(dest="command", required=True)
    start_brief_parser = None
    render_parser = None
    finalize_parser = None
    status_parsers = []
    command_help = {
        "status": "Show owner-facing run state without listing every helper artifact.",
        "next": "Write the next owner action for the current run.",
        "start-brief": "Create intake records from the user's brief and materials.",
        "render": "Run the structured-render helper when tooling is the right output path; direct PPT composition can bypass this command.",
        "finalize": "Check final delivery readiness for the current editable PPT.",
    }
    command_descriptions = {
        "render": (
            "Structured-render helper for LLM-authored banker_page_pack.json. "
            "Use it when predictable tooling should translate the page pack into PPT. "
            "For simple style-reference templates, agents may instead copy the selected PPTX, duplicate "
            "a low-content or blank template page, and directly compose editable text boxes, tables, "
            "charts, cards, and shapes without this command."
        ),
    }
    for name in (
        "status",
        "next",
        "start-brief",
        "render",
        "finalize",
    ):
        p = sub.add_parser(
            name,
            help=command_help[name],
            description=command_descriptions.get(name),
        )
        p.add_argument("--run-dir", required=True)
        if name in {"status", "next"}:
            status_parsers.append(p)
        elif name == "start-brief":
            start_brief_parser = p
        elif name == "render":
            render_parser = p
        elif name == "finalize":
            finalize_parser = p

    if (
        start_brief_parser is None
        or render_parser is None
        or finalize_parser is None
    ):
        raise RuntimeError("failed to construct parser for pipeline commands")

    render_parser.add_argument(
        "--template",
        default="",
        help="Optional explicit user PPTX/POTX template. If omitted, pipeline selects a registered ppt_template material or the bundled template.",
    )
    for status_parser in status_parsers:
        status_parser.add_argument("--output")
        status_parser.add_argument("--markdown-output")
        status_parser.add_argument(
            "--include-debug-commands",
            action="store_true",
            help=(
                "Include exact helper-check commands and artifact diagnostics for operator debugging. "
                "Omit by default so status stays owner-action focused."
            ),
        )
    start_brief_parser.add_argument("--case-name", required=True)
    start_brief_parser.add_argument("--brief-text")
    start_brief_parser.add_argument("--brief-file")
    start_brief_parser.add_argument("--file", action="append", default=[])
    start_brief_parser.add_argument("--url", action="append", default=[])
    start_brief_parser.add_argument("--template-file", action="append", default=[])
    start_brief_parser.add_argument("--target-company", default="")
    start_brief_parser.add_argument("--transaction-type", default="")
    start_brief_parser.add_argument("--industry", default="")
    start_brief_parser.add_argument("--subsector", default="")
    start_brief_parser.add_argument("--geography", default="")
    render_parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Only when the operator has independently confirmed structured-render inputs; does not bypass content readiness.",
    )
    render_parser.add_argument(
        "--strict-runtime-readiness",
        action="store_true",
        help="Fail render when search/PDF runtime diagnostics are missing instead of recording an advisory warning.",
    )
    render_parser.add_argument(
        "--allow-research-limited-review-render",
        action="store_true",
        help="Explicitly render a RESEARCH_LIMITED_REVIEW copy when LLM readiness says targeted research should happen first.",
    )
    finalize_parser.add_argument("--require-final-delivery-authorization", action="store_true")
    args = parser.parse_args(raw_argv)

    try:
        run_dir = Path(args.run_dir)
        if args.command in {"status", "next"}:
            status_view(
                run_dir,
                args.command,
                output=Path(args.output) if args.output else None,
                markdown_output=Path(args.markdown_output) if args.markdown_output else None,
                include_debug_commands=bool(getattr(args, "include_debug_commands", False)),
            )
        elif args.command == "start-brief":
            start_brief(
                run_dir,
                args.python,
                case_name=args.case_name,
                brief_text=args.brief_text,
                brief_file=Path(args.brief_file) if args.brief_file else None,
                files=args.file,
                urls=args.url,
                template_files=args.template_file,
                target_company=args.target_company,
                transaction_type=args.transaction_type,
                industry=args.industry,
                subsector=args.subsector,
                geography=args.geography,
            )
        elif args.command == "render":
            render(
                _ensure_run_dir(run_dir),
                args.python,
                skip_preflight=args.skip_preflight,
                template_path=Path(args.template) if args.template else None,
                strict_runtime_readiness=args.strict_runtime_readiness,
                allow_research_limited_review_render=args.allow_research_limited_review_render,
            )
        elif args.command == "finalize":
            finalize(
                _ensure_run_dir(run_dir),
                args.python,
                require_final_delivery_authorization=args.require_final_delivery_authorization,
            )
    except subprocess.CalledProcessError as exc:
        return exc.returncode or 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
