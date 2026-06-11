#!/usr/bin/env python3
"""Generate a concise markdown quality summary for an industry-section run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from json_utils import load_json_file
from validate_final_delivery import validate as validate_final_delivery_current
from validate_run_state import validate_run_state


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
SOURCE_REGISTRY = ROOT_DIR / "templates" / "source_registry.json"


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = load_json_file(path)
    except Exception as exc:
        return {"_load_error": str(exc)}
    return data if isinstance(data, dict) else {}


def count_search_attempts(path: Path) -> int:
    if not path.exists():
        return 0
    text = path.read_text(encoding="utf-8")
    return sum(1 for line in text.splitlines() if line.lstrip().startswith("### Search"))


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _first_items(value: Any, limit: int = 8) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value[:limit]]


def _validation_snapshot(path: Path) -> dict[str, Any]:
    data = load_optional_json(path)
    return {
        "path": str(path),
        "exists": path.exists(),
        "is_valid": data.get("is_valid"),
        "client_ready": data.get("client_ready"),
        "error_count": data.get("error_count", len(data.get("errors", []) or [])),
        "warning_count": data.get("warning_count", len(data.get("warnings", []) or [])),
        "errors": _first_items(data.get("errors")),
        "warnings": _first_items(data.get("warnings")),
        "repair_plan": data.get("repair_plan", {}),
    }


def build_summary_payload(run_dir: Path) -> dict[str, Any]:
    artifacts = run_dir / "artifacts"
    input_card = load_optional_json(artifacts / "input_card_validation.json")
    formal_execution = load_optional_json(artifacts / "formal_research_execution_validation.json")
    source_reviews = load_optional_json(artifacts / "source_reviews_validation.json")
    source_archive = load_optional_json(artifacts / "source_archive_validation.json")
    research_pack = load_optional_json(artifacts / "research_pack_validation.json")
    issue_analysis = load_optional_json(artifacts / "issue_analysis_validation.json")
    content = load_optional_json(artifacts / "content_quality_validation.json")
    deck_blueprint = load_optional_json(artifacts / "deck_blueprint_validation.json")
    renderer_spec = load_optional_json(artifacts / "renderer_spec_validation.json")
    page_contract = load_optional_json(artifacts / "page_evidence_contract_validation.json")
    chart_binding = load_optional_json(artifacts / "chart_metric_binding_validation.json")
    replacement = load_optional_json(artifacts / "replacement_dict_validation.json")
    final_delivery = load_optional_json(artifacts / "final_delivery_validation.json")
    banker_review = load_optional_json(artifacts / "banker_review_report.json")
    ppt = load_optional_json(run_dir / "filled_ppt_validation.json")
    current_final = validate_final_delivery_current(run_dir, SOURCE_REGISTRY)
    workflow_state = validate_run_state(run_dir)

    ppt_summary = ppt.get("summary", {}) if isinstance(ppt.get("summary"), dict) else {}
    slide_reviews = banker_review.get("slide_reviews") if isinstance(banker_review.get("slide_reviews"), list) else []
    banker_flags: list[dict[str, Any]] = []
    for item in slide_reviews:
        if not isinstance(item, dict):
            continue
        flags = item.get("mechanical_flags")
        if flags:
            banker_flags.append(
                {
                    "slide_no": item.get("slide_no"),
                    "selected_page_type": item.get("selected_page_type"),
                    "mechanical_flags": flags,
                    "repair_target": item.get("repair_target", "deck_blueprint.json"),
                }
            )

    client_ready = current_final.get("client_ready") is True
    verdict = "CLIENT_READY" if client_ready else "NOT_CLIENT_READY"
    next_repair_targets: list[str] = []
    for source in (issue_analysis, deck_blueprint, content, replacement, final_delivery, current_final):
        repair_plan = source.get("repair_plan") if isinstance(source.get("repair_plan"), dict) else {}
        for target in repair_plan.get("primary_repair_targets", []) or []:
            text = str(target)
            if text not in next_repair_targets:
                next_repair_targets.append(text)
    if not next_repair_targets and not client_ready:
        gate = workflow_state.get("blocking_gate") or workflow_state.get("current_stage") or "current gate"
        next_repair_targets.append(str(gate))

    validations = {
        "input_card": _validation_snapshot(artifacts / "input_card_validation.json"),
        "industry_scope_pack": _validation_snapshot(artifacts / "industry_scope_pack_validation.json"),
        "formal_search_plan": _validation_snapshot(artifacts / "formal_search_plan_validation.json"),
        "formal_research_execution": _validation_snapshot(artifacts / "formal_research_execution_validation.json"),
        "source_reviews": _validation_snapshot(artifacts / "source_reviews_validation.json"),
        "source_archive": _validation_snapshot(artifacts / "source_archive_validation.json"),
        "pre_research_pack": _validation_snapshot(artifacts / "stage_gate_pre_research_pack_validation.json"),
        "research_pack": _validation_snapshot(artifacts / "research_pack_validation.json"),
        "issue_analysis": _validation_snapshot(artifacts / "issue_analysis_validation.json"),
        "deck_blueprint": _validation_snapshot(artifacts / "deck_blueprint_validation.json"),
        "page_evidence_contract": _validation_snapshot(artifacts / "page_evidence_contract_validation.json"),
        "renderer_spec": _validation_snapshot(artifacts / "renderer_spec_validation.json"),
        "chart_metric_binding": _validation_snapshot(artifacts / "chart_metric_binding_validation.json"),
        "content_quality": _validation_snapshot(artifacts / "content_quality_validation.json"),
        "pre_ppt": _validation_snapshot(artifacts / "stage_gate_pre_ppt_validation.json"),
        "replacement_dict": _validation_snapshot(artifacts / "replacement_dict_validation.json"),
        "filled_ppt": _validation_snapshot(run_dir / "filled_ppt_validation.json"),
        "final_delivery": _validation_snapshot(artifacts / "final_delivery_validation.json"),
    }

    return {
        "schema_version": "run_quality_summary_v2",
        "run_dir": str(run_dir),
        "verdict": verdict,
        "client_ready": client_ready,
        "current_stage": workflow_state.get("current_stage"),
        "workflow_status": workflow_state.get("status"),
        "blocking_gate": workflow_state.get("blocking_gate"),
        "next_repair_targets": next_repair_targets,
        "final_delivery": current_final,
        "validations": validations,
        "research_audit": {
            "search_attempt_count": count_search_attempts(artifacts / "search_log.md"),
            "formal_research_execution_warning_count": formal_execution.get("warning_count", 0),
            "formal_research_execution_error_count": formal_execution.get("error_count", 0),
            "source_review_warning_count": source_reviews.get("warning_count", 0),
            "source_review_error_count": source_reviews.get("error_count", 0),
            "source_archive_valid": source_archive.get("is_valid") is True,
            "research_pack_valid": research_pack.get("is_valid") is True,
        },
        "banker_review": {
            "exists": bool(banker_review),
            "slide_review_count": len(slide_reviews),
            "flagged_slides": banker_flags,
        },
        "content_quality": {
            "is_valid": content.get("is_valid") is True,
            "blocking_issue_count": content.get("blocking_issue_count", 0),
            "source_warning_count": len(content.get("source_warnings", []) or []),
            "density_warning_count": len(content.get("density_warnings", []) or []),
            "layout_warning_count": len(content.get("layout_warnings", []) or []),
            "chart_data_warning_count": len(content.get("chart_data_warnings", []) or []),
            "repair_plan": content.get("repair_plan", {}),
        },
        "ppt_integrity": {
            "replacement_valid": replacement.get("is_valid") is True,
            "filled_ppt_valid": ppt_summary.get("is_valid") is True or ppt.get("is_valid") is True,
            "remaining_placeholder_count": ppt_summary.get("remaining_placeholder_count", "n/a"),
            "visible_scaffold_label_count": ppt_summary.get("visible_scaffold_label_count", "n/a"),
            "page_number_issue_count": ppt_summary.get("page_number_issue_count", "n/a"),
            "actual_kept_slide_count": ppt_summary.get("actual_kept_slide_count", "n/a"),
        },
        "selected_gate_errors": {
            "issue_analysis": _first_items(issue_analysis.get("errors")),
            "deck_blueprint": _first_items(deck_blueprint.get("errors")),
            "page_evidence_contract": _first_items(page_contract.get("errors")),
            "renderer_spec": _first_items(renderer_spec.get("errors")),
            "chart_metric_binding": _first_items(chart_binding.get("errors")),
            "content_quality": _first_items(content.get("errors")),
            "replacement_dict": _first_items(replacement.get("errors")),
            "final_delivery": _first_items(current_final.get("errors")),
        },
    }


def build_summary(run_dir: Path) -> str:
    payload = build_summary_payload(run_dir)
    validations = payload["validations"]
    research_audit = payload["research_audit"]
    content = payload["content_quality"]
    ppt_integrity = payload["ppt_integrity"]
    banker = payload["banker_review"]

    lines = [
        "# Run Quality Summary",
        "",
        f"Run Dir: `{run_dir}`",
        f"Verdict: **{payload['verdict']}**",
        f"Current workflow stage: `{payload['current_stage']}` (`{payload['workflow_status']}`)",
        f"Blocking gate: `{payload['blocking_gate'] or ''}`",
        f"Next repair targets: {', '.join(payload['next_repair_targets']) if payload['next_repair_targets'] else 'none'}",
        "",
        "## Gates",
        "",
        f"- Input card valid: {yes_no(validations['input_card']['is_valid'] is True)}",
        f"- formal research execution valid: {yes_no(validations['formal_research_execution']['is_valid'] is True)}",
        f"- Source reviews valid: {yes_no(validations['source_reviews']['is_valid'] is True)}",
        f"- Source archive valid: {yes_no(validations['source_archive']['is_valid'] is True)}",
        f"- Research pack valid: {yes_no(validations['research_pack']['is_valid'] is True)}",
        f"- Issue analysis valid: {yes_no(validations['issue_analysis']['is_valid'] is True)}",
        f"- Deck blueprint valid: {yes_no(validations['deck_blueprint']['is_valid'] is True)}",
        f"- Renderer spec valid: {yes_no(validations['renderer_spec']['is_valid'] is True)}",
        f"- Replacement dict valid: {yes_no(validations['replacement_dict']['is_valid'] is True)}",
        f"- Content quality valid: {yes_no(validations['content_quality']['is_valid'] is True)}",
        f"- PPT validation valid: {yes_no(validations['filled_ppt']['is_valid'] is True)}",
        f"- Final delivery artifact valid: {yes_no(validations['final_delivery']['is_valid'] is True)}",
        f"- Current final delivery gate valid: {yes_no(payload['final_delivery'].get('is_valid') is True)}",
        f"- Technical delivery valid: {yes_no(payload['final_delivery'].get('technical_delivery_valid') is True)}",
        f"- Research evidence valid: {yes_no(payload['final_delivery'].get('research_evidence_valid') is True)}",
        f"- Client-ready: {yes_no(payload['client_ready'])}",
        "",
        "## Research Audit",
        "",
        f"- Search attempts logged: {research_audit['search_attempt_count']}",
        f"- formal research execution warnings: {research_audit['formal_research_execution_warning_count']}",
        f"- formal research execution errors: {research_audit['formal_research_execution_error_count']}",
        f"- Source review warnings: {research_audit['source_review_warning_count']}",
        f"- Source review errors: {research_audit['source_review_error_count']}",
        f"- Source archive valid: {yes_no(research_audit['source_archive_valid'])}",
        "",
        "## Source And Copy Quality",
        "",
        f"- Source warnings: {content['source_warning_count']}",
        f"- Blocking content issues: {content['blocking_issue_count']}",
        f"- Density warnings: {content['density_warning_count']}",
        f"- Layout warnings: {content['layout_warning_count']}",
        f"- Chart data warnings: {content['chart_data_warning_count']}",
        "",
        "## Banker Review",
        "",
        f"- Banker review report exists: {yes_no(banker['exists'])}",
        f"- Slide review count: {banker['slide_review_count']}",
        f"- Flagged slides: {len(banker['flagged_slides'])}",
        "",
        "## PPT Integrity",
        "",
        f"- Replacement dict valid: {yes_no(ppt_integrity['replacement_valid'])}",
        f"- Filled PPT valid: {yes_no(ppt_integrity['filled_ppt_valid'])}",
        f"- Remaining placeholders: {ppt_integrity['remaining_placeholder_count']}",
        f"- Visible scaffold labels: {ppt_integrity['visible_scaffold_label_count']}",
        f"- Page number issues: {ppt_integrity['page_number_issue_count']}",
        f"- Actual kept slides: {ppt_integrity['actual_kept_slide_count']}",
        "",
    ]

    notable: list[str] = []
    for key, source in validations.items():
        for item in source.get("errors", [])[:5]:
            notable.append(f"- {key} error: {item}")
        for item in source.get("warnings", [])[:3]:
            notable.append(f"- {key} advisory: {item}")
    for item in _first_items(payload["final_delivery"].get("errors")):
        notable.append(f"- current final delivery error: {item}")
    for item in banker["flagged_slides"][:8]:
        notable.append(
            f"- banker review flag: slide {item.get('slide_no')} {item.get('mechanical_flags')} -> {item.get('repair_target')}"
        )

    if notable:
        lines.extend(["## Notable Issues", "", *notable, ""])
    else:
        lines.extend(["## Notable Issues", "", "- None reported by deterministic gates.", ""])

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate artifacts/run_quality_summary.md for a run.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output", help="Defaults to <run-dir>/artifacts/run_quality_summary.md")
    parser.add_argument("--json-output", help="Defaults to <run-dir>/artifacts/run_quality_summary.json")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    output = Path(args.output) if args.output else run_dir / "artifacts/run_quality_summary.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_summary(run_dir), encoding="utf-8")
    json_output = Path(args.json_output) if args.json_output else run_dir / "artifacts/run_quality_summary.json"
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(build_summary_payload(run_dir), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(str(output))


if __name__ == "__main__":
    main()
