#!/usr/bin/env python3
"""Route current run-state/QC failures to the correct repair role."""

from __future__ import annotations

# Runtime scripts can be run directly. Shared helpers remain in runtime
# `scripts/`; production tools live under role scripts; validators live under QC.
import sys as _ib_sys
from pathlib import Path as _IbPath
_IB_ROLE_SCRIPT_DIR = _IbPath(__file__).resolve().parent
_IB_RUNTIME_ROOT = next(
    _p for _p in _IbPath(__file__).resolve().parents
    if (_p / 'configs').is_dir() and (_p / 'scripts').is_dir()
)
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts"
_IB_ROLE_SCRIPT_DIRS = sorted(_p for _p in (_IB_RUNTIME_ROOT / 'scripts').iterdir() if _p.is_dir())
_IB_QC_VALIDATOR_DIRS = sorted((_IB_RUNTIME_ROOT / 'scripts' / 'qc' / 'validators').glob('*'))
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
import re
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
    "orchestrator": "Stop downstream work, report blocker, and resume from state_report.py next.",
}

VALIDATION_ARTIFACT_SKIP = {
    "final_delivery_validation.json",
    "qc_repair_brief.json",
    "qc_router_report.json",
    "qc_warning_disposition.json",
}


def _infer_layer_for_artifact(path: Path) -> str:
    name = path.name
    text = str(path).lower()
    if "material" in text or "input_card" in text:
        return "material-intake"
    if "scope" in text or "boundary" in text:
        return "industry-scoping"
    if any(token in text for token in ("search", "source", "formal_research", "archive")):
        return "research-external-evidence"
    if any(token in text for token in ("research_evidence_db", "research_pack")):
        return "knowledge-repository"
    if "issue_analysis" in text:
        return "reasoning"
    if any(token in text for token in ("deck_blueprint", "page_evidence", "renderer", "content_quality")):
        return "generation"
    if "template" in text:
        return "template"
    if any(token in name for token in ("replacement", "filled_ppt")):
        return "output"
    return "qc"


def _renumber_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for idx, issue in enumerate(issues, start=1):
        issue["issue_id"] = f"QC-{idx:03d}"
    return issues


def _validation_reports_for_run(run_dir: Path) -> list[Path]:
    paths: list[Path] = []
    artifacts = run_dir / "artifacts"
    if artifacts.exists():
        for path in sorted(artifacts.glob("*.json")):
            if path.name in VALIDATION_ARTIFACT_SKIP:
                continue
            if "validation" in path.name or path.name.endswith("_status.json"):
                paths.append(path)
    filled = run_dir / "filled_ppt_validation.json"
    if filled.exists():
        paths.append(filled)
    return paths


def _warning_issues_for_run(run_dir: Path) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for report_path in _validation_reports_for_run(run_dir):
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        has_warnings = bool(payload.get("warnings")) or int(payload.get("warning_count") or 0) > 0
        if not has_warnings:
            continue
        rel_artifact = str(report_path.relative_to(run_dir)) if report_path.is_relative_to(run_dir) else str(report_path)
        normalized = normalize_report(
            payload,
            default_layer=_infer_layer_for_artifact(report_path),
            default_artifact=rel_artifact,
            rerun_command=f"$PYTHON_CMD scripts/qc/qc_router.py --run-dir {run_dir}",
        )
        for issue in normalized.get("issues", []):
            if isinstance(issue, dict) and issue.get("severity") == "warning":
                issue["source_report"] = rel_artifact
                issues.append(issue)
    return issues


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
        "issue_type": "state_blocker" if state.get("status") != "passed" else "none",
        "severity": "blocking" if state.get("status") in {"missing", "failed", "stale", "blocked"} else "none",
        "repair_target_role": role,
        "repair_target_skill": state.get("owner_skill", ""),
        "repair_target_artifact": (state.get("missing_artifacts") or [""])[0]
        if state.get("missing_artifacts")
        else blocking_gate,
        "recommended_action": ROLE_ACTIONS.get(role, ROLE_ACTIONS["orchestrator"]),
        "downstream_risk_action": state.get("forbidden_actions", []),
        "state_message": state.get("message", ""),
        "missing_artifacts": state.get("missing_artifacts", []),
        "failed_validations": state.get("failed_validations", []),
        "stale_validations": state.get("stale_validations", []),
    }
    normalized = normalize_report(
        payload,
        default_layer=role,
        default_artifact=str(payload.get("repair_target_artifact") or blocking_gate),
        rerun_command=f"$PYTHON_CMD scripts/state_report.py next --run-dir {run_dir}",
    )
    payload["repair_schema_version"] = normalized["schema_version"]
    issues = list(normalized["issues"])
    issues.extend(_warning_issues_for_run(run_dir))
    issues = _renumber_issues(issues)
    blocking_count = sum(
        1
        for issue in issues
        if issue.get("downstream_blocked")
        and (
            issue.get("severity") in {"blocking", "error"}
            or issue.get("requires_qc_disposition") is True
        )
    )
    payload["is_valid"] = normalized["is_valid"] and blocking_count == 0
    payload["blocking_issue_count"] = blocking_count
    payload["warning_issue_count"] = sum(1 for issue in issues if issue.get("severity") == "warning")
    payload["requires_qc_disposition_count"] = sum(1 for issue in issues if issue.get("requires_qc_disposition") is True)
    payload["issues"] = issues
    return payload


def _issue_affected_slides(field_path: str, message: str) -> list[str]:
    text = " ".join([field_path or "", message or ""]).lower()
    values: list[str] = []
    patterns = (
        r"slide\[(\d+)\]",
        r"slide_no\s*[=:]\s*(\d+)",
        r"\bslide\s+(\d+)\b",
        r"\bslide_(\d+)\b",
    )
    for pattern in patterns:
        for match in re.findall(pattern, text):
            label = f"slide:{match}"
            if label not in values:
                values.append(label)
    return values[:3]


def _root_cause_key(issue: dict[str, Any]) -> tuple[str, str, str]:
    message = str(issue.get("message") or "").lower()
    owner = str(issue.get("repair_owner") or issue.get("layer") or "orchestrator")
    if "render layout" in message or "template profile has no variant" in message:
        return (
            "template_layout_contract",
            "Template profile / registry layout contract mismatch",
            "Template must regenerate or repair layout contracts; do not patch derived profile by hand.",
        )
    if "table_header" in message or "table_row" in message or "compare_table_data" in message:
        return (
            "table_payload_mapping",
            "Structured table payload not mapped into template/table fields",
            "Compiler/Template should map compare_table_data to table fields or return to Generation for a supported table page.",
        )
    if "min recommended" in message or "too short" in message or "only " in message and "body_copy" in message:
        return (
            "page_density",
            "Page copy density is below pitchbook standard",
            "Generation should enrich or restructure affected slides; QC may accept only with explicit client-readiness limits.",
        )
    if "label rather than a conclusion" in message:
        return (
            "conclusion_led_title",
            "Slide title reads like a label instead of a conclusion",
            "Generation should rewrite headlines as banker judgments supported by evidence.",
        )
    if "all non-user source_reviews" in message or "weak-source" in message or "repost" in message:
        return (
            "source_quality_disposition",
            "Source quality needs LLM/QC disposition",
            "Research/QC should classify source quality and set claim-use limits before evidence promotion or headline use.",
        )
    if "locator should not replace" in message or "material" in message and "locator" in message:
        return (
            "material_locator_hygiene",
            "Material locator/source fields are not clean",
            "Material Intake should repair source registration so later provenance remains clear.",
        )
    if "evidence-backed" in message or "one ev-id" in message or "supported_inference" in message:
        return (
            "evidence_support_depth",
            "Evidence support is too thin or not clearly bound to the claim",
            "Reasoning/QC should decide whether to triangulate, caveat, downgrade, or request more research.",
        )
    if "drilldown_role" in message or "drill_down_from_slide" in message or "new_information_added" in message:
        return (
            "page_role_contract",
            "Page role / drilldown contract is incomplete",
            "Generation should repair page role metadata and ensure the page adds distinct insight.",
        )
    if "visible numeric context" in message:
        return (
            "metric_binding",
            "Visible metric is not bound to a material claim location",
            "Generation/Research should bind the metric to a claim or remove it from client-facing copy.",
        )
    return (
        f"{owner}_repair",
        f"{owner} repair required",
        str(issue.get("repair_action") or "Repair the affected artifact and rerun QC."),
    )


def _root_cause_groups(summary_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for row in summary_rows:
        key, title, action = _root_cause_key(
            {
                "message": row.get("root_cause"),
                "repair_owner": row.get("repair_owner"),
                "layer": row.get("affected_layer"),
                "repair_action": row.get("exact_next_action"),
            }
        )
        group = groups.setdefault(
            key,
            {
                "root_cause_id": key,
                "title": title,
                "repair_owner": row.get("repair_owner") or row.get("affected_layer") or "orchestrator",
                "issue_count": 0,
                "affected_artifacts": [],
                "affected_slides": [],
                "representative_issues": [],
                "recommended_next_action": action,
            },
        )
        group["issue_count"] += 1
        artifact = str(row.get("affected_artifact") or "")
        if artifact and artifact not in group["affected_artifacts"]:
            group["affected_artifacts"].append(artifact)
        for slide in row.get("affected_slides") or []:
            if slide and slide not in group["affected_slides"]:
                group["affected_slides"].append(slide)
        if len(group["representative_issues"]) < 3:
            group["representative_issues"].append(row.get("issue_id"))
    return sorted(groups.values(), key=lambda item: (-int(item.get("issue_count") or 0), str(item.get("root_cause_id") or "")))


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
                "severity": str(issue.get("severity") or ""),
                "root_cause": root_cause,
                "affected_layer": issue_layer,
                "affected_artifact": issue_artifact,
                "affected_slides": affected_slides,
                "repair_owner": str(issue.get("repair_owner") or issue_layer),
                "exact_next_action": str(issue.get("repair_action") or issue.get("message") or ""),
                "forbidden_action": str(issue.get("forbidden_action") or ""),
                "warning_disposition": str(issue.get("warning_disposition") or ""),
                "downstream_limit": str(issue.get("downstream_limit") or ""),
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
                "exact_next_action": "refresh state_report.py next from the current run directory.",
                "downstream_risk_action": "Avoid rewriting derived artifacts without a deterministic rebuild signal.",
            }
        ]

    groups = _root_cause_groups(summary_rows)
    blocked = [item for item in summary_rows if str(item.get("repair_owner") or "")]
    owner_groups: dict[str, int] = {}
    for row in summary_rows:
        owner = str(row.get("repair_owner") or "orchestrator")
        owner_groups[owner] = owner_groups.get(owner, 0) + 1
    return {
        "schema_version": "qc_repair_brief_v1",
        "run_dir": qc_payload.get("run_dir"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "blocking_issue_count": len(blocked),
            "total_issues": len(summary_rows),
            "warning_issue_count": int(qc_payload.get("warning_issue_count") or 0),
            "requires_qc_disposition_count": int(qc_payload.get("requires_qc_disposition_count") or 0),
            "status": "repair_required" if qc_payload.get("is_valid") is False else "pass_through",
            "next_focus": groups[0].get("repair_owner") if groups else (blocked[0].get("repair_owner") if blocked else "orchestrator"),
            "next_root_cause": groups[0].get("root_cause_id") if groups else "",
            "owner_groups": owner_groups,
        },
        "root_cause_groups": groups,
        "issues": summary_rows,
    }


def _build_qc_warning_disposition(qc_payload: dict[str, Any]) -> dict[str, Any]:
    warnings: list[dict[str, Any]] = []
    for idx, issue in enumerate(qc_payload.get("issues", []), start=1):
        if not isinstance(issue, dict) or issue.get("severity") != "warning":
            continue
        disposition = str(issue.get("warning_disposition") or "unresolved")
        warnings.append(
            {
                "warning_id": f"WARN-{len(warnings) + 1:03d}",
                "source_issue_id": str(issue.get("issue_id") or f"QC-{idx:03d}"),
                "source_report": str(issue.get("source_report") or issue.get("artifact") or ""),
                "category": str(issue.get("layer") or "qc"),
                "layer": str(issue.get("layer") or "qc"),
                "artifact": str(issue.get("artifact") or ""),
                "field_path": str(issue.get("field_path") or ""),
                "message": str(issue.get("message") or ""),
                "repair_owner": str(issue.get("repair_owner") or issue.get("layer") or "qc"),
                "disposition": disposition,
                "requires_qc_disposition": bool(issue.get("requires_qc_disposition", disposition == "unresolved")),
                "downstream_blocked": bool(issue.get("downstream_blocked", disposition == "unresolved")),
                "downstream_limit": str(issue.get("downstream_limit") or ""),
                "accepted_by": str(issue.get("accepted_by") or ""),
                "acceptance_rationale": str(issue.get("acceptance_rationale") or ""),
                "rerun_command": str(issue.get("rerun_command") or ""),
            }
        )
    return {
        "schema_version": "qc_warning_disposition_v1",
        "run_dir": qc_payload.get("run_dir"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "warning_count": len(warnings),
        "unresolved_warning_count": sum(1 for item in warnings if item.get("requires_qc_disposition")),
        "warnings": warnings,
    }


def _brief_markdown(qc_payload: dict[str, Any]) -> str:
    brief = _build_qc_repair_brief(qc_payload)
    summary = brief.get("summary") if isinstance(brief.get("summary"), dict) else {}
    groups = brief.get("root_cause_groups") if isinstance(brief.get("root_cause_groups"), list) else []
    lines = [
        "# QC Repair Brief",
        f"Run Dir: `{qc_payload.get('run_dir')}`",
        f"Status: {'BLOCKED' if qc_payload.get('is_valid') is False else 'PASS'}",
        f"Blocking issues: {qc_payload.get('blocking_issue_count', 0)}",
        f"Next focus: {summary.get('next_focus', 'orchestrator')}",
        f"Next root cause: {summary.get('next_root_cause', '') or 'n/a'}",
        "",
        "## Root Cause Groups",
    ]
    for group in groups:
        if not isinstance(group, dict):
            continue
        lines.extend(
            [
                f"### {group.get('root_cause_id', 'root_cause')}: {group.get('title', '')}",
                f"- issue count: {group.get('issue_count', 0)}",
                f"- repair owner: {group.get('repair_owner', '')}",
                f"- affected artifacts: {', '.join(group.get('affected_artifacts') or []) or 'n/a'}",
                f"- affected slides: {', '.join(group.get('affected_slides') or []) or 'n/a'}",
                f"- recommended next action: {group.get('recommended_next_action', '')}",
                f"- representative issues: {', '.join(str(item) for item in (group.get('representative_issues') or [])) or 'n/a'}",
                "",
            ]
        )
    issues = [item for item in qc_payload.get("issues", []) if isinstance(item, dict)]
    if issues:
        lines.extend(["## Issue Detail Sample"])
        for issue in issues[:12]:
            lines.extend(
                [
                    f"### {issue.get('issue_id', 'QC-000')}: {issue.get('repair_owner', 'orchestrator')}",
                    f"- message: {issue.get('message') or issue.get('repair_action') or ''}",
                    f"- affected artifact: {issue.get('artifact', '-')}",
                    f"- exact next action: {issue.get('repair_action', '')}",
                    f"- downstream limit: {issue.get('downstream_limit') or 'n/a'}",
                    "",
                ]
            )
        if len(issues) > 12:
            lines.append(f"... {len(issues) - 12} additional issue(s) omitted from Markdown sample; see qc_repair_brief.json for full detail.")
    else:
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
        warning_disposition = out.parent / "qc_warning_disposition.json"
        warning_disposition.write_text(
            json.dumps(_build_qc_warning_disposition(payload), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
