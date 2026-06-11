#!/usr/bin/env python3
"""Build role-specific handoff packets for the IB industry-section workflow.

This is a local coordination tool, not an external multi-agent runtime. It
creates concise packets for specialized LLM roles so one agent does not have to
hold the whole workflow in its head or hand-maintain mechanical IDs.
"""

from __future__ import annotations

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
        "mission": "Run planned searches, review exact sources, record locators/excerpts, and preserve source archive snapshots.",
        "owns": ["search_log.md", "source_reviews.json", "source_archive/"],
        "must_not": ["batch-fill usable_as_evidence", "cite root domains as evidence", "keep EV IDs on unusable sources"],
        "inputs": ["artifacts/formal_search_plan.json", "artifacts/search_log.md"],
        "outputs": ["artifacts/search_log.md", "artifacts/source_reviews.json", "artifacts/source_archive/source_archive_index.json"],
        "helpers": ["append_search_attempt.py", "build_source_reviews_skeleton.py", "build_source_archive.py", "validate_source_reviews.py"],
    },
    "evidence_extractor": {
        "title": "Evidence Extractor",
        "mission": "Extract source-faithful facts/metrics into research_evidence_db; do not write polished memo conclusions.",
        "owns": ["artifacts/research_evidence_db.json"],
        "must_not": ["hand-edit industry_research_pack.md", "collapse research into a short memo", "promote lead-only sources", "mix incomparable metric scopes"],
        "inputs": [
            "artifacts/formal_research_execution_report.json",
            "artifacts/source_reviews.json",
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
            "Use this packet to work only on your role's artifacts. If the current workflow gate is upstream of your role, stop and report that upstream gate instead of fabricating downstream files.",
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
    index = {
        "schema_version": "agent_handoff_index_v1",
        "run_dir": str(run_dir),
        "created_date": date.today().isoformat(),
        "current_stage": state.get("current_stage"),
        "workflow_status": state.get("status"),
        "blocking_gate": state.get("blocking_gate"),
        "roles": roles,
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
