#!/usr/bin/env python3
"""Aggregate state/gate observations into one repair report.

This is a dashboard/triage script, not a new gate. It does not introduce new
blocking rules. It reads the current state report and existing validation
artifacts, then summarizes root causes, repair owners, and next public actions
so agents do not have to browse many `validate_*` scripts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from state_report import next_payload

PYTHON_COMMAND_TEMPLATE = '"$PYTHON_CMD"'

VALIDATION_REPORT_NAMES = {
    "material_manifest_validation.json",
    "material_extracts_validation.json",
    "input_card_validation.json",
    "industry_scope_pack_validation.json",
    "formal_search_plan_validation.json",
    "source_archive_validation.json",
    "formal_research_execution_validation.json",
    "stage_gate_pre_research_pack_validation.json",
    "research_evidence_db_validation.json",
    "research_pack_validation.json",
    "issue_analysis_validation.json",
    "template_registry_validation.json",
    "deck_blueprint_validation.json",
    "page_evidence_contract_validation.json",
    "renderer_spec_validation.json",
    "template_fit_validation.json",
    "chart_metric_binding_validation.json",
    "content_quality_validation.json",
    "stage_gate_pre_ppt_validation.json",
    "replacement_dict_validation.json",
    "final_delivery_validation.json",
}


def _load_json(path: Path) -> tuple[dict[str, Any], str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, str(exc)
    if not isinstance(payload, dict):
        return {}, "JSON payload is not an object"
    return payload, ""


def _rel(run_dir: Path, path: Path | str) -> str:
    path = Path(path)
    try:
        return str(path.relative_to(run_dir))
    except ValueError:
        return str(path)


def _artifact_layer(path: str, fallback: str = "qc") -> str:
    text = path.lower()
    if "input_card" in text or "material" in text or "source_classification" in text:
        return "material-intake"
    if "scope" in text or "boundary" in text:
        return "industry-scoping"
    if any(token in text for token in ("search", "source", "archive", "formal_research", "coverage")):
        return "research-external-evidence"
    if any(token in text for token in ("research_evidence_db", "research_pack", "repository")):
        return "knowledge-repository"
    if any(token in text for token in ("issue_analysis", "hypothesis", "research_request", "page_argument")):
        return "reasoning"
    if any(token in text for token in ("deck_blueprint", "page_evidence", "renderer", "content_quality")):
        return "generation"
    if "template" in text:
        return "template"
    if any(token in text for token in ("replacement", "filled_ppt", "final_delivery", "ppt")):
        return "output"
    return fallback


def _owner_action(layer: str) -> str:
    return {
        "material-intake": "Material/Intake repairs source registration, extraction, or input-card transcription.",
        "industry-scoping": "Scoping repairs boundary, excluded scope, data hierarchy, or unvalidated leads.",
        "research-external-evidence": "Research repairs actual searches, source reviews, archive, or planned-vs-actual accounting.",
        "knowledge-repository": "Knowledge repairs research_evidence_db.json, then regenerates the readable evidence pack.",
        "reasoning": "Reasoning repairs evidence readiness, hypotheses, issue analysis, or research-request routing.",
        "generation": "Generation repairs page arguments, deck blueprint, claim binding, or renderer inputs.",
        "template": "Template repairs profile/fit; Generation repairs only if content exceeds template capacity.",
        "output": "Output reruns deterministic rendering after upstream artifacts are current.",
        "qc": "QC groups warnings/failures and routes the smallest upstream repair.",
        "orchestrator": "Main agent decides the real owner and stops downstream work until the blocker is resolved.",
    }.get(layer, "Route to the smallest correct owner role.")


def _first_messages(payload: dict[str, Any], key: str, limit: int = 4) -> list[str]:
    value = payload.get(key)
    if isinstance(value, list):
        out: list[str] = []
        for item in value[:limit]:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                message = item.get("message") or item.get("error") or item.get("repair_action") or item
                out.append(json.dumps(message, ensure_ascii=False) if isinstance(message, (dict, list)) else str(message))
            else:
                out.append(str(item))
        return out
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _validation_paths(run_dir: Path) -> list[Path]:
    paths: list[Path] = []
    artifacts = run_dir / "artifacts"
    if artifacts.exists():
        for path in sorted(artifacts.glob("*.json")):
            if path.name in VALIDATION_REPORT_NAMES or "validation" in path.name or path.name.endswith("_status.json"):
                paths.append(path)
    filled = run_dir / "filled_ppt_validation.json"
    if filled.exists():
        paths.append(filled)
    return paths


def _summarize_validation(path: Path, run_dir: Path) -> dict[str, Any] | None:
    payload, error = _load_json(path)
    rel_path = _rel(run_dir, path)
    layer = _artifact_layer(rel_path)
    if error:
        return {
            "path": rel_path,
            "layer": layer,
            "is_valid": False,
            "client_ready": False,
            "error_count": 1,
            "warning_count": 0,
            "sample_errors": [f"cannot read validation JSON: {error}"],
            "sample_warnings": [],
        }
    errors = _first_messages(payload, "errors")
    warnings = _first_messages(payload, "warnings")
    issues = payload.get("issues")
    if isinstance(issues, list):
        for issue in issues:
            if not isinstance(issue, dict):
                continue
            severity = str(issue.get("severity") or "").lower()
            message = str(issue.get("message") or issue.get("repair_action") or "").strip()
            if not message:
                continue
            if severity in {"blocking", "error", "fatal"} and len(errors) < 4:
                errors.append(message)
            elif severity == "warning" and len(warnings) < 4:
                warnings.append(message)
    error_count = int(payload.get("error_count") or len(errors) or 0)
    warning_count = int(payload.get("warning_count") or len(warnings) or 0)
    is_valid = payload.get("is_valid")
    client_ready = payload.get("client_ready")
    if is_valid is True and not warnings:
        return None
    if is_valid is None and not errors and not warnings:
        return None
    return {
        "path": rel_path,
        "layer": layer,
        "is_valid": bool(is_valid),
        "client_ready": bool(client_ready),
        "error_count": error_count,
        "warning_count": warning_count,
        "sample_errors": errors[:4],
        "sample_warnings": warnings[:4],
    }


def _command_items(payload: dict[str, Any]) -> list[dict[str, str]]:
    run_dir = str(payload.get("run_dir") or "")
    commands: list[dict[str, str]] = [
        {
            "purpose": "refresh observed state after any repair",
            "command": f"{PYTHON_COMMAND_TEMPLATE} scripts/state_report.py next --run-dir {run_dir}",
        }
    ]
    shortest = payload.get("shortest_repair_path") if isinstance(payload.get("shortest_repair_path"), dict) else {}
    if shortest.get("available") and shortest.get("command"):
        commands.append({"purpose": str(shortest.get("why") or "shortest deterministic repair"), "command": str(shortest["command"])})
    for item in payload.get("recommended_next_commands") or []:
        if isinstance(item, dict) and item.get("command"):
            commands.append({"purpose": str(item.get("purpose") or "recommended next action"), "command": str(item["command"])})
    if payload.get("status") in {"missing", "failed", "stale", "blocked"} and payload.get("qc_router_command"):
        commands.append({"purpose": "group warnings/failures into QC repair targets", "command": str(payload["qc_router_command"])})
    draft = payload.get("internal_draft_option") if isinstance(payload.get("internal_draft_option"), dict) else {}
    if draft.get("available") and draft.get("command"):
        commands.append({"purpose": str(draft.get("use_only_for") or "internal draft only"), "command": str(draft["command"])})
    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for item in commands:
        command = item["command"]
        if command in seen:
            continue
        seen.add(command)
        deduped.append(item)
    return deduped[:8]


def _state_root_cause_groups(state_payload: dict[str, Any]) -> list[dict[str, Any]]:
    stage = str(state_payload.get("current_stage") or "")
    owner = str(state_payload.get("repair_target_role") or state_payload.get("owner_role") or "orchestrator")
    groups: list[dict[str, Any]] = []
    for path in state_payload.get("missing_artifacts") or []:
        layer = _artifact_layer(str(path), owner)
        groups.append(
            {
                "group_id": f"missing:{path}",
                "severity": "blocking",
                "layer": layer,
                "artifact": str(path),
                "root_cause": "Required artifact is missing.",
                "repair_owner": layer,
                "repair_action": _owner_action(layer),
                "why_it_matters": "Downstream work would be based on an incomplete package of record.",
            }
        )
    for item in state_payload.get("failed_validations") or []:
        path = str(item.get("path") if isinstance(item, dict) else item)
        layer = _artifact_layer(path, owner)
        groups.append(
            {
                "group_id": f"failed:{path or stage}",
                "severity": "blocking",
                "layer": layer,
                "artifact": path,
                "root_cause": str(item.get("status") or "Validation failed") if isinstance(item, dict) else "Validation failed",
                "repair_owner": layer,
                "repair_action": _owner_action(layer),
                "why_it_matters": "The current artifact does not satisfy deterministic structure/provenance/render requirements.",
            }
        )
    for item in state_payload.get("stale_validations") or []:
        path = str(item.get("validation") if isinstance(item, dict) else item)
        source = str(item.get("stale_because_input_is_newer") or "") if isinstance(item, dict) else ""
        layer = _artifact_layer(path, owner)
        groups.append(
            {
                "group_id": f"stale:{path}:{source}",
                "severity": "blocking",
                "layer": layer,
                "artifact": path,
                "root_cause": f"Validation is stale because {source or 'an upstream artifact'} changed.",
                "repair_owner": layer,
                "repair_action": "Use pipeline.py rebuild-stale when available; otherwise rerun the named deterministic check after repairing the owner artifact.",
                "why_it_matters": "Stale validation makes downstream artifacts untrustworthy even when files exist.",
            }
        )
    if state_payload.get("debug_only"):
        groups.append(
            {
                "group_id": "debug_only_output",
                "severity": "blocking",
                "layer": "output",
                "artifact": "DEBUG_OUTPUT_ONLY.txt",
                "root_cause": "Run is explicitly marked debug/draft only.",
                "repair_owner": "output",
                "repair_action": "Repair the formal blockers and rerun the formal pipeline; do not rename a draft as final.",
                "why_it_matters": "Debug or draft output cannot be presented as client-ready.",
            }
        )
    return groups


def _validation_root_cause_groups(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for item in summaries:
        errors = item.get("sample_errors") or []
        warnings = item.get("sample_warnings") or []
        if errors:
            severity = "blocking"
            root = "; ".join(str(msg) for msg in errors[:2])
        elif warnings:
            severity = "warning"
            root = "; ".join(str(msg) for msg in warnings[:2])
        else:
            continue
        layer = str(item.get("layer") or "qc")
        groups.append(
            {
                "group_id": f"{severity}:{item.get('path')}",
                "severity": severity,
                "layer": layer,
                "artifact": item.get("path"),
                "root_cause": root,
                "repair_owner": layer if severity == "blocking" else "qc",
                "repair_action": _owner_action(layer) if severity == "blocking" else "QC classifies the warning as advisory, repair-required, or accepted with limits.",
                "why_it_matters": "Warnings and errors must be routed before final delivery; warnings are not silent permission to proceed.",
            }
        )
    return groups


def _dedupe_groups(groups: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for group in groups:
        key = str(group.get("group_id") or group.get("artifact") or group.get("root_cause"))
        if key in seen:
            continue
        seen.add(key)
        group = dict(group)
        group["group_id"] = f"GR-{len(deduped) + 1:03d}"
        deduped.append(group)
        if len(deduped) >= limit:
            break
    return deduped


def build_gate_report(run_dir: Path) -> dict[str, Any]:
    state_payload = next_payload(run_dir)
    validation_summaries = [
        summary
        for path in _validation_paths(run_dir)
        for summary in [_summarize_validation(path, run_dir)]
        if summary is not None
    ]
    root_cause_groups = _dedupe_groups(
        _state_root_cause_groups(state_payload)
        + _validation_root_cause_groups(validation_summaries)
    )
    status = str(state_payload.get("status") or "")
    client_ready = state_payload.get("current_stage") == "CLIENT_READY" and state_payload.get("final_delivery_valid") is True
    has_blocker = any(group.get("severity") == "blocking" for group in root_cause_groups)
    has_warning = any(group.get("severity") == "warning" for group in root_cause_groups)
    if client_ready:
        overall = "client_ready"
    elif has_blocker or status in {"missing", "failed", "stale", "blocked"}:
        overall = "needs_fix"
    elif has_warning:
        overall = "needs_qc_disposition"
    else:
        overall = "pass"
    return {
        "schema_version": "gate_report_v1",
        "report_role": "dashboard_triage_not_new_gate",
        "run_dir": str(run_dir),
        "overall": overall,
        "current_stage": state_payload.get("current_stage"),
        "status": state_payload.get("status"),
        "owner_role": state_payload.get("owner_role"),
        "repair_target_role": state_payload.get("repair_target_role"),
        "blocking_gate": state_payload.get("blocking_gate"),
        "hard_block_final_delivery": overall != "client_ready",
        "allowed_to_continue_authoring": overall in {"pass", "needs_qc_disposition"} and not has_blocker,
        "llm_judgment_required": overall in {"needs_qc_disposition"} or any(
            group.get("repair_owner") in {"qc", "reasoning", "research-external-evidence", "generation"}
            for group in root_cause_groups
        ),
        "state_message": state_payload.get("message"),
        "root_cause_groups": root_cause_groups,
        "validation_summaries": validation_summaries[:20],
        "public_next_actions": _command_items(state_payload),
        "do_not": [
            "Do not browse all validate_* scripts as a process menu.",
            "Do not patch derived artifacts or validation JSON by hand.",
            "Do not report a PPT as complete while hard_block_final_delivery=true.",
            "Do not treat this report as banker judgment; route semantic issues to the owner role/QC.",
        ],
        "internal_validator_policy": (
            "Direct validate_* scripts are precision tools. Use them only when state_report.py next, "
            "gate_report.py, qc_router.py, or the owner role names the exact artifact check."
        ),
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Gate Report",
        "",
        f"- Overall: `{report.get('overall')}`",
        f"- Current stage: `{report.get('current_stage')}`",
        f"- Owner role: `{report.get('owner_role')}`",
        f"- Hard block final delivery: `{report.get('hard_block_final_delivery')}`",
        "",
        "## Root Cause Groups",
    ]
    groups = report.get("root_cause_groups") or []
    if not groups:
        lines.append("")
        lines.append("No blocking root-cause groups were detected from current state artifacts.")
    for group in groups:
        lines.extend(
            [
                "",
                f"### {group.get('group_id')} | {group.get('severity')} | {group.get('repair_owner')}",
                f"- Artifact: `{group.get('artifact')}`",
                f"- Root cause: {group.get('root_cause')}",
                f"- Why it matters: {group.get('why_it_matters')}",
                f"- Repair action: {group.get('repair_action')}",
            ]
        )
    lines.extend(["", "## Public Next Actions"])
    for item in report.get("public_next_actions") or []:
        lines.extend(["", f"- {item.get('purpose')}", "", f"```bash\n{item.get('command')}\n```"])
    lines.extend(["", "## Do Not"])
    for item in report.get("do_not") or []:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def write_outputs(report: dict[str, Any], output: str | None, markdown_output: str | None) -> None:
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    if markdown_output:
        path = Path(markdown_output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_markdown(report), encoding="utf-8")
    print(text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate current state/gate observations into one repair report.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output", help="Optional JSON output path")
    parser.add_argument("--markdown-output", help="Optional Markdown output path")
    args = parser.parse_args()

    report = build_gate_report(Path(args.run_dir))
    write_outputs(report, args.output, args.markdown_output)


if __name__ == "__main__":
    main()
