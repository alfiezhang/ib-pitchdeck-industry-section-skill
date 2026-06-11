#!/usr/bin/env python3
"""Route current run-state/QC failures to the correct repair role."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from qc_normalize_report import normalize_report
from validate_run_state import validate_run_state


ROLE_ACTIONS = {
    "material-intake": "Repair user material classification, extracted facts, or input_card transcription.",
    "knowledge-repository": "Repair research_evidence_db.json and regenerate derived research pack.",
    "industry-scoping": "Repair industry boundary, excluded scope, data hierarchy, or unvalidated leads.",
    "research-external-evidence": "Repair search/source/archive/formal execution accounting using actual reviewed sources only.",
    "reasoning": "Repair issue analysis, hypothesis resolution, allowed deck usage, or research request queue.",
    "generation": "Repair page arguments, deck_blueprint, evidence contract, or renderer spec by editing upstream page design.",
    "template": "Repair template profile/fit or return to generation when capacity is insufficient.",
    "qc": "Rerun or inspect gate validation and route the underlying upstream artifact.",
    "output": "Rerun deterministic output pipeline after upstream gates are current.",
    "orchestrator": "Stop downstream work, report blocker, and resume from workflow.py next.",
}


def payload_for_run(run_dir: Path) -> dict[str, Any]:
    state = validate_run_state(run_dir)
    role = str(state.get("repair_target_role") or state.get("owner_role") or "orchestrator")
    blocking_gate = str(state.get("blocking_gate") or "")
    payload = {
        "schema_version": "qc_router_report_v1",
        "run_dir": str(run_dir),
        "current_stage": state.get("current_stage"),
        "status": state.get("status"),
        "blocking_gate": blocking_gate,
        "issue_type": "workflow_gate_blocker" if state.get("status") != "passed" else "none",
        "severity": "blocking" if state.get("status") in {"missing", "failed", "stale", "blocked"} else "none",
        "repair_target_role": role,
        "repair_target_skill": state.get("owner_skill", ""),
        "repair_target_artifact": (state.get("missing_artifacts") or [""])[0]
        if state.get("missing_artifacts")
        else blocking_gate,
        "recommended_action": ROLE_ACTIONS.get(role, ROLE_ACTIONS["orchestrator"]),
        "forbidden_action": state.get("forbidden_actions", []),
        "state_message": state.get("message", ""),
        "missing_artifacts": state.get("missing_artifacts", []),
        "failed_validations": state.get("failed_validations", []),
        "stale_validations": state.get("stale_validations", []),
    }
    normalized = normalize_report(
        payload,
        default_layer=role,
        default_artifact=str(payload.get("repair_target_artifact") or blocking_gate),
        rerun_command=f"$PYTHON_CMD scripts/workflow.py next --run-dir {run_dir}",
    )
    payload["repair_schema_version"] = normalized["schema_version"]
    payload["is_valid"] = normalized["is_valid"]
    payload["blocking_issue_count"] = normalized["blocking_issue_count"]
    payload["issues"] = normalized["issues"]
    return payload


def _issue_affected_slides(field_path: str, message: str) -> list[str]:
    text = " ".join([field_path or "", message or ""]).lower()
    out: list[str] = []
    # Lightweight extraction that works for legacy issue fields like slide[3], slide_no=2, etc.
    if "slide" in text:
        marker_tokens = ("slide[", "slide_no", "slide_no=", "page", "slide ")
        for token in marker_tokens:
            idx = text.find(token)
            if idx >= 0:
                break
    parts = []
    for token in (text or "").replace("=", " ").split():
        if token.isdigit():
            parts.append(token)
    if parts:
        out = [f"slide:{value}" for value in parts[:3]]
    return out


def _build_qc_repair_brief(qc_payload: dict[str, Any]) -> dict[str, Any]:
    """Build a human-oriented repair brief for downstream commanding."""
    issues = qc_payload.get("issues") if isinstance(qc_payload.get("issues"), list) else []
    summary_rows: list[dict[str, Any]] = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        root_cause = str(issue.get("message") or "").strip()
        if not root_cause:
            root_cause = str(issue.get("repair_action") or "")
        issue_layer = str(issue.get("layer") or "").strip()
        issue_artifact = str(issue.get("artifact") or "").strip()
        affected_slides = _issue_affected_slides(str(issue.get("field_path") or ""), root_cause)
        summary_rows.append(
            {
                "issue_id": str(issue.get("issue_id") or ""),
                "root_cause": root_cause,
                "affected_layer": issue_layer,
                "affected_artifact": issue_artifact,
                "affected_slides": affected_slides,
                "repair_owner": str(issue.get("repair_owner") or issue_layer),
                "exact_next_action": str(issue.get("repair_action") or issue.get("message") or ""),
                "forbidden_action": str(issue.get("forbidden_action") or ""),
            }
        )
    if not summary_rows:
        summary_rows = [
            {
                "issue_id": "QC-000",
                "root_cause": "run is currently in a healthy state",
                "affected_layer": "orchestrator",
                "affected_artifact": "final_delivery_validation.json",
                "affected_slides": [],
                "repair_owner": "orchestrator",
                "exact_next_action": "resume workflow.py next from the current run directory.",
                "forbidden_action": "Do not rewrite derived artifacts without command signal.",
            }
        ]

    blocked = [item for item in summary_rows if str(item.get("repair_owner") or "")]
    return {
        "schema_version": "qc_repair_brief_v1",
        "run_dir": qc_payload.get("run_dir"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "blocking_issue_count": len(blocked),
            "total_issues": len(summary_rows),
            "status": "repair_required" if qc_payload.get("is_valid") is False else "pass_through",
            "next_focus": blocked[0].get("repair_owner") if blocked else "orchestrator",
        },
        "issues": summary_rows,
    }


def _brief_markdown(qc_payload: dict[str, Any]) -> str:
    lines = [
        "# QC Repair Brief",
        f"Run Dir: `{qc_payload.get('run_dir')}`",
        f"Status: {'BLOCKED' if qc_payload.get('is_valid') is False else 'PASS'}",
        f"Blocking issues: {qc_payload.get('blocking_issue_count', 0)}",
        "",
    ]
    for issue in qc_payload.get("issues", []):
        if not isinstance(issue, dict):
            continue
        lines.extend(
            [
                f"## {issue.get('issue_id', 'QC-000')}: {issue.get('repair_owner', 'orchestrator')}",
                f"- root cause: {issue.get('message') or issue.get('repair_action') or ''}",
                f"- affected layer: {issue.get('layer', '-')}",
                f"- affected artifact: {issue.get('artifact', '-')}",
                f"- affected slides: {', '.join(_issue_affected_slides(str(issue.get('field_path') or ''), str(issue.get('message') or '')) ) or 'n/a'}",
                f"- repair owner: {issue.get('repair_owner', '')}",
                f"- exact next action: {issue.get('repair_action', '')}",
                f"- forbidden action: {issue.get('forbidden_action') or 'Not specified'}",
                "",
            ]
        )
    if not qc_payload.get("issues"):
        lines.append("- No blocking action required.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    payload = payload_for_run(Path(args.run_dir))
    brief = _build_qc_repair_brief(payload)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        brief_json = out.parent / "qc_repair_brief.json"
        brief_json.write_text(json.dumps(brief, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        brief_md = out.parent / "qc_repair_brief.md"
        brief_md.write_text(_brief_markdown(payload) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
