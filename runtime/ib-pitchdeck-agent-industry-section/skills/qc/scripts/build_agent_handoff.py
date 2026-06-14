#!/usr/bin/env python3
"""Build role-specific handoff packets for the IB industry-section workflow.

This is a local coordination tool, not an external multi-agent runtime. It
creates concise packets for specialized LLM roles so one agent does not have to
hold the whole workflow in its head or hand-maintain mechanical IDs.
"""

from __future__ import annotations

# Runtime scripts can be run directly. Shared helpers remain in runtime
# `scripts/`; production tools live under role scripts; validators live under QC.
import sys as _ib_sys
from pathlib import Path as _IbPath
_IB_ROLE_SCRIPT_DIR = _IbPath(__file__).resolve().parent
_IB_RUNTIME_ROOT = next(
    _p for _p in _IbPath(__file__).resolve().parents
    if (_p / 'templates').is_dir() and (_p / 'skills').is_dir() and (_p / 'scripts').is_dir()
)
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts"
_IB_ROLE_SCRIPT_DIRS = sorted((_IB_RUNTIME_ROOT / 'skills').glob('*/scripts'))
_IB_QC_VALIDATOR_DIRS = sorted((_IB_RUNTIME_ROOT / 'skills' / 'qc' / 'scripts' / 'validators').glob('*'))
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
from datetime import date
from pathlib import Path
from typing import Any

from validate_run_state import validate_run_state


ROLES: dict[str, dict[str, Any]] = {
    "research_planner": {
        "title": "Research Planner",
        "mission": "Define industry scope and turn every canonical issue/subissue into executable search instructions.",
        "owns": ["industry_scope_pack.json", "formal_search_plan.json"],
        "must_not": ["write investment conclusions", "write slide/page claims", "promote unvalidated numbers"],
        "inputs": ["input_card.json", "artifacts/industry_scope_pack.json", "templates/source_registry.json"],
        "outputs": ["artifacts/industry_scope_pack.json", "artifacts/formal_search_plan.json"],
        "helpers": ["build_formal_search_plan_skeleton.py", "validate_industry_scope_pack.py", "validate_formal_search_plan.py"],
    },
    "source_analyst": {
        "title": "Source Analyst",
        "mission": "Run planned searches, record locators/excerpts, and preserve source archive snapshots.",
        "owns": ["search_log.md", "source_archive/"],
        "must_not": ["invent S-xxx IDs", "cite root domains as evidence", "treat archived candidates as final evidence decisions"],
        "inputs": ["artifacts/formal_search_plan.json", "artifacts/search_log.md"],
        "outputs": ["artifacts/search_log.md", "artifacts/source_archive/source_archive_index.json"],
        "helpers": ["append_search_attempt.py", "edit_search_attempt.py", "build_source_archive.py", "validate_source_archive.py"],
    },
    "evidence_extractor": {
        "title": "Evidence Extractor",
        "mission": "Extract source-faithful facts/metrics into research_evidence_db; do not write polished memo conclusions.",
        "owns": ["artifacts/research_evidence_db.json"],
        "must_not": ["hand-edit industry_research_pack.md", "collapse research into a short memo", "promote lead-only sources", "mix incomparable metric scopes"],
        "inputs": [
            "artifacts/formal_research_execution_report.json",
            "artifacts/source_archive/source_archive_index.json",
        ],
        "outputs": [
            "artifacts/research_evidence_db.json",
            "artifacts/research_evidence_db_validation.json",
            "industry_research_pack.md",
            "artifacts/research_pack_validation.json",
        ],
        "helpers": [
            "build_research_evidence_db.py",
            "validate_research_evidence_db.py",
            "export_research_pack_from_db.py",
            "validate_research_pack.py",
        ],
    },
    "issue_analyst": {
        "title": "Issue Analyst",
        "mission": "Convert evidence binder rows into substantive issue-by-issue banker analysis and backlog.",
        "owns": ["industry_issue_analysis.json"],
        "must_not": ["write slide numbers", "write template choices", "leave skeleton placeholders", "invent coverage claims"],
        "inputs": ["industry_research_pack.md", "artifacts/formal_research_execution_report.json"],
        "outputs": ["industry_issue_analysis.json", "artifacts/issue_analysis_validation.json"],
        "helpers": ["build_issue_analysis_skeleton.py", "normalize_issue_analysis.py", "validate_issue_analysis.py"],
    },
    "page_editor": {
        "title": "Page Editor",
        "mission": "Turn issue analysis into conclusion-led, evidence-backed deck_blueprint pages.",
        "owns": ["deck_blueprint.json"],
        "must_not": ["hand-write renderer_spec", "guess inactive placeholders", "duplicate the same fact across body fields"],
        "inputs": ["industry_issue_analysis.json", "template_registry.json"],
        "outputs": ["deck_blueprint.json", "page_evidence_contract.json", "renderer_spec.json"],
        "helpers": ["extract_template_registry.py", "validate_deck_blueprint.py", "compile_deck_blueprint.py"],
    },
    "banker_reviewer": {
        "title": "Banker Reviewer",
        "mission": "Review deck pages for storyline, content density, evidence fit, and pitchbook quality.",
        "owns": ["banker_review_packet.md", "banker_review_report.json"],
        "must_not": ["patch renderer_spec directly", "treat body-length warnings as permission to delete proof", "turn thin evidence into confident headlines"],
        "inputs": ["deck_blueprint.json", "page_evidence_contract.json", "renderer_spec.json"],
        "outputs": ["artifacts/banker_review_packet.md", "artifacts/banker_review_report.json"],
        "helpers": ["build_banker_review_packet.py", "build_banker_review_report_skeleton.py", "validate_content_quality.py"],
    },
    "format_qc": {
        "title": "PPT Render And Format QC",
        "mission": "Run deterministic PPT rendering, PPT validation, final delivery gate, and run quality summary.",
        "owns": ["replacement_dict.json", "industry_section_filled_clean.pptx", "final_delivery_validation.json", "run_quality_summary.md"],
        "must_not": ["bypass pre-PPT gate", "create ad-hoc python-pptx output", "call a non-client-ready PPT final"],
        "inputs": ["renderer_spec.json", "page_evidence_contract.json", "artifacts/stage_gate_pre_ppt_validation.json"],
        "outputs": ["replacement_dict.json", "industry_section_filled_clean.pptx", "artifacts/final_delivery_validation.json", "artifacts/run_quality_summary.md"],
        "helpers": ["pipeline.py render", "pipeline.py finalize", "validate_filled_ppt.py", "validate_final_delivery.py"],
    },
}


HANDOFF_PACKETS: dict[str, dict[str, Any]] = {
    "handoff_material_to_scoping": {
        "from_role": "material-intake",
        "to_role": "industry-scoping",
        "title": "Material → Scoping",
        "completed": [
            "material manifest extracted and validated",
            "material content-capture workspace generated; raw text is not evidence-ready until LLM fact extraction",
        ],
        "available_evidence": [
            "artifacts/material_manifest.json",
            "artifacts/material_extracts.json",
            "artifacts/source_classification.json",
            "artifacts/material_manifest_validation.json",
            "artifacts/material_extracts_validation.json",
        ],
        "required_for_next": [
            "artifacts/source_classification.json",
            "artifacts/material_extracts.json",
            "artifacts/material_manifest.json",
        ],
        "downstream_not_allowed": [
            "draft template_profile.json",
            "draft template_fit_validation.json",
            "deck_blueprint.json",
            "industry_issue_analysis.json",
            "page_evidence_contract.json",
            "renderer_spec.json",
        ],
    },
    "handoff_scoping_to_research": {
        "from_role": "industry-scoping",
        "to_role": "research-external-evidence",
        "title": "Scoping → Research",
        "completed": [
            "industry boundary defined",
            "QC LLM granted boundary pass or wrote boundary validation requests",
            "formal search plan seeded from canonical taxonomy",
        ],
        "available_evidence": [
            "artifacts/industry_scope_pack.json",
            "artifacts/industry_boundary_qc.json",
            "artifacts/boundary_research_requests.json",
            "artifacts/formal_search_plan.json",
        ],
        "required_for_next": [
            "artifacts/industry_scope_pack.json",
            "artifacts/industry_boundary_qc.json",
            "artifacts/formal_search_plan.json",
        ],
        "downstream_not_allowed": [
            "manually edited search results without append_search_attempt",
            "final deck artifacts (deck_blueprint.json, replacement_dict.json)",
            "industry_section_filled_clean.pptx",
        ],
    },
    "handoff_research_to_reasoning": {
        "from_role": "research-external-evidence",
        "to_role": "reasoning",
        "title": "Research → Reasoning",
        "completed": [
            "formal searches executed and reconciled",
            "sources archived with locator/excerpts",
            "research evidence DB built from reviewed sources only",
            "coverage accounting records not executed rows",
        ],
        "available_evidence": [
            "artifacts/formal_research_execution_report.json",
            "artifacts/source_archive/source_archive_index.json",
            "artifacts/research_evidence_db.json",
            "industry_research_pack.md",
            "artifacts/formal_research_execution_validation.json",
            "artifacts/research_evidence_db_validation.json",
        ],
        "required_for_next": [
            "artifacts/formal_research_execution_report.json",
            "artifacts/research_evidence_db.json",
        ],
        "downstream_not_allowed": [
            "draft deck_blueprint.json",
            "renderer_spec.json",
            "replacement_dict.json",
            "template_profile.json",
            "template_fit_validation.json",
        ],
    },
    "handoff_reasoning_to_generation": {
        "from_role": "reasoning",
        "to_role": "generation",
        "title": "Reasoning → Generation",
        "completed": [
            "issue analysis written per-subissue with evidence-backed statements",
            "research requests represented as actionable caveats and blockers",
            "research gaps separated from validated findings",
        ],
        "available_evidence": [
            "industry_issue_analysis.json",
            "artifacts/hypothesis_store.json",
            "artifacts/research_request_queue.json",
            "artifacts/issue_analysis_validation.json",
        ],
        "required_for_next": [
            "industry_issue_analysis.json",
            "artifacts/issue_analysis_validation.json",
        ],
        "downstream_not_allowed": [
            "hand-edit renderer_spec.json",
            "append deck text directly without issue permissions",
            "skip source-backed evidence mapping in deck_blueprint.json",
        ],
    },
    "handoff_generation_to_template": {
        "from_role": "generation",
        "to_role": "template",
        "title": "Generation → Template",
        "completed": [
            "deck blueprint mapped to source-evidence contract",
            "chart/table placement and page-type intention resolved",
        ],
        "available_evidence": [
            "deck_blueprint.json",
            "artifacts/page_argument_pack.json",
            "template_registry.json",
        ],
        "required_for_next": [
            "deck_blueprint.json",
            "template_registry.json",
            "artifacts/issue_analysis_validation.json",
        ],
        "downstream_not_allowed": [
            "hand-edit template_profile.json",
            "run replacement dict before pre-ppt gate",
            "insert S-IDs into PPT without renderer_spec mapping",
        ],
    },
    "handoff_template_to_output": {
        "from_role": "template",
        "to_role": "output",
        "title": "Template → Output",
        "completed": [
            "template profile and fit validated for target PPT",
            "page evidence contract + renderer spec generated",
        ],
        "available_evidence": [
            "artifacts/template_profile.json",
            "artifacts/template_fit_validation.json",
            "artifacts/template_fit_plan.json",
            "page_evidence_contract.json",
            "renderer_spec.json",
        ],
        "required_for_next": [
            "artifacts/template_profile.json",
            "artifacts/template_fit_validation.json",
            "page_evidence_contract.json",
            "renderer_spec.json",
            "template_registry.json",
            "deck_blueprint.json",
        ],
        "downstream_not_allowed": [
            "manual replacement_dict edits",
            "run copy into final output before validate_final_delivery passes",
            "edit artifact values in output files to pass gates",
        ],
    },
}


def _json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _exists(run_dir: Path, rels: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rel in rels:
        path = run_dir / rel
        rows.append({"path": rel, "exists": path.exists()})
    return rows


def _status_lines(run_dir: Path, rels: list[str]) -> tuple[list[str], list[str]]:
    available: list[str] = []
    unavailable: list[str] = []
    for rel in rels:
        if (run_dir / rel).exists():
            available.append(rel)
        else:
            unavailable.append(rel)
    return available, unavailable


def _packet_lines(path: Path, title: str, packet: dict[str, Any], available: list[str], unavailable: list[str]) -> str:
    unavailable_lines = ["- none"] if not unavailable else [f"- {item}" for item in unavailable]
    current_gap_lines = [f"- {item}" for item in packet.get("required_for_next", []) if item in unavailable]
    if not current_gap_lines:
        current_gap_lines = ["- none"]
    lines = [
        f"# {title} Packet",
        f"Run Dir: `{path}`",
        f"Date: {date.today().isoformat()}",
        f"From: `{packet['from_role']}`",
        f"To: `{packet['to_role']}`",
        "",
        "## 已完成什么",
    ]
    for item in packet.get("completed", []):
        lines.append(f"- {item}")
    lines.extend([
        "",
        "## 可用 evidence",
        *(f"- {item}" for item in available),
        "",
        "## 不可用 evidence",
        *unavailable_lines,
        "",
        "## 当前缺口",
        *current_gap_lines,
    ])
    lines.extend([
        "",
        "## 下游禁止误用什么",
        *(f"- {item}" for item in packet.get("downstream_not_allowed", [])),
    ])
    if not packet.get("downstream_not_allowed"):
        lines.append("- none")
    return "\n".join(lines)


def _build_handoff_packet(run_dir: Path, packet_key: str, packet: dict[str, Any]) -> dict[str, Any]:
    completed = packet.get("completed", [])
    available_evidence_keys = list(packet.get("available_evidence", []))
    unavailable_evidence_keys = list(packet.get("available_evidence", []))
    available, unavailable = _status_lines(run_dir, available_evidence_keys)
    return {
        "schema_version": "handoff_packet_v1",
        "handoff_id": packet_key,
        "run_dir": str(run_dir),
        "from_role": packet.get("from_role", ""),
        "to_role": packet.get("to_role", ""),
        "completed": completed,
        "available_evidence": {
            "present": available,
            "missing": unavailable,
        },
        "current_gaps": [path for path in packet.get("required_for_next", []) if path in unavailable],
        "forbidden_for_downstream": packet.get("downstream_not_allowed", []),
    }


def _md_packet(role_key: str, role: dict[str, Any], run_dir: Path, state: dict[str, Any]) -> str:
    lines = [
        f"# {role['title']} Handoff",
        "",
        f"Run Dir: `{run_dir}`",
        f"Date: {date.today().isoformat()}",
        f"Current Stage: `{state.get('current_stage')}` (`{state.get('status')}`)",
        f"Blocking Gate: `{state.get('blocking_gate') or ''}`",
        "",
        "## Mission",
        role["mission"],
        "",
        "## Owns",
        *[f"- {item}" for item in role["owns"]],
        "",
        "## Inputs To Read",
        *[f"- {item}" for item in role["inputs"]],
        "",
        "## Outputs To Produce Or Repair",
        *[f"- {item}" for item in role["outputs"]],
        "",
        "## Helpers To Prefer",
        *[f"- `scripts/{item}`" for item in role["helpers"]],
        "",
        "## Do Not",
        *[f"- {item}" for item in role["must_not"]],
        "",
        "## Input Availability",
    ]
    for row in _exists(run_dir, role["inputs"]):
        lines.append(f"- {row['path']}: {'exists' if row['exists'] else 'missing'}")
    lines.extend(
        [
            "",
            "## Role Instruction",
            "Use this packet to work only on your role's artifacts. If the current state blocker is upstream of your role, report that upstream blocker instead of fabricating downstream files.",
            "",
        ]
    )
    return "\n".join(lines)


def build_handoff(run_dir: Path, output_dir: Path) -> dict[str, Any]:
    state = validate_run_state(run_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    roles: list[dict[str, Any]] = []
    for role_key, role in ROLES.items():
        path = output_dir / f"{role_key}.md"
        path.write_text(_md_packet(role_key, role, run_dir, state), encoding="utf-8")
        roles.append(
            {
                "role": role_key,
                "title": role["title"],
                "mission": role["mission"],
                "packet": str(path),
                "inputs": _exists(run_dir, role["inputs"]),
                "outputs": role["outputs"],
                "helpers": role["helpers"],
            }
        )
    handoff_entries: list[dict[str, Any]] = []
    for packet_key, packet in HANDOFF_PACKETS.items():
        json_path = output_dir / f"{packet_key}.json"
        payload = _build_handoff_packet(run_dir, packet_key, packet)
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        md_path = output_dir / f"{packet_key}.md"
        available = payload["available_evidence"]["present"]
        unavailable = payload["available_evidence"]["missing"]
        md_path.write_text(
            _packet_lines(run_dir, packet["title"], packet, available, unavailable) + "\n",
            encoding="utf-8",
        )
        handoff_entries.append(
            {
                "handoff_id": packet_key,
                "from": packet["from_role"],
                "to": packet["to_role"],
                "packet_json": str(json_path),
                "packet_md": str(md_path),
                "completed": payload["completed"],
                "current_gaps": payload["current_gaps"],
                "forbidden_for_downstream": payload["forbidden_for_downstream"],
            }
        )
    index = {
        "schema_version": "agent_handoff_index_v1",
        "run_dir": str(run_dir),
        "created_date": date.today().isoformat(),
        "current_stage": state.get("current_stage"),
        "workflow_status": state.get("status"),
        "blocking_gate": state.get("blocking_gate"),
        "roles": roles,
        "handoff_packets": handoff_entries,
    }
    (output_dir / "agent_handoff_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return index


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output-dir", help="Defaults to <run-dir>/artifacts/agent_handoff")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    output_dir = Path(args.output_dir) if args.output_dir else run_dir / "artifacts" / "agent_handoff"
    index = build_handoff(run_dir, output_dir)
    print(json.dumps({"is_valid": True, "output_dir": str(output_dir), "role_count": len(index["roles"])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
