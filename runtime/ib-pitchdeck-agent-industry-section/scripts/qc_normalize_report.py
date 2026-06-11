#!/usr/bin/env python3
"""Normalize legacy validator/router reports into the QC repair schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from json_utils import load_json_file


BLOCKING_SEVERITIES = {"blocking", "error", "failed", "missing", "stale", "blocked"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _default_message(report: dict[str, Any]) -> str:
    for key in ("message", "state_message", "error", "status"):
        value = _text(report.get(key))
        if value:
            return value
    return "QC report indicates a blocking issue."


def _severity(value: Any, *, fallback: str = "blocking") -> str:
    candidate = _text(value).lower()
    if candidate in {"warning", "info", "none"}:
        return candidate
    if candidate in BLOCKING_SEVERITIES:
        return "blocking"
    return fallback


def _issue(
    idx: int,
    *,
    severity: str,
    layer: str,
    artifact: str,
    field_path: str,
    message: str,
    why_it_matters: str,
    repair_owner: str,
    repair_action: str,
    rerun_command: str,
    downstream_blocked: bool,
) -> dict[str, Any]:
    return {
        "issue_id": f"QC-{idx:03d}",
        "severity": severity,
        "layer": layer,
        "artifact": artifact,
        "field_path": field_path,
        "message": message,
        "why_it_matters": why_it_matters,
        "repair_owner": repair_owner,
        "repair_action": repair_action,
        "rerun_command": rerun_command,
        "downstream_blocked": downstream_blocked,
    }


def _issues_from_repair_targets(
    report: dict[str, Any],
    *,
    default_layer: str,
    default_artifact: str,
    rerun_command: str,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    repair_targets = _list(report.get("repair_targets"))
    if isinstance(report.get("repair_plan"), dict):
        repair_targets.extend(_list(report["repair_plan"].get("targets")))
    repair_targets.extend(_list(report.get("repair_issues")))
    repair_targets.extend(_list(report.get("root_causes")))

    for item in repair_targets:
        if not isinstance(item, dict):
            continue
        layer = _text(item.get("repair_target_layer") or item.get("layer") or item.get("owner_stage") or default_layer)
        artifact = _text(item.get("repair_target_artifact") or item.get("repair_target") or item.get("artifact") or default_artifact)
        message = _text(item.get("message") or item.get("recommended_action") or item.get("repair_action") or item.get("code"))
        issues.append(
            _issue(
                len(issues) + 1,
                severity=_severity(item.get("severity"), fallback="blocking"),
                layer=layer or default_layer,
                artifact=artifact or default_artifact,
                field_path=_text(item.get("field_path") or item.get("path")),
                message=message or _default_message(report),
                why_it_matters=_text(item.get("why_it_matters") or "Downstream artifacts depend on this gate being valid."),
                repair_owner=_text(item.get("repair_owner") or layer or default_layer),
                repair_action=_text(item.get("repair_action") or item.get("recommended_action") or "Repair the listed artifact and rerun validation."),
                rerun_command=_text(item.get("rerun_command") or rerun_command),
                downstream_blocked=bool(item.get("downstream_blocked", True)),
            )
        )
    return issues


def _issues_from_errors(
    report: dict[str, Any],
    *,
    default_layer: str,
    default_artifact: str,
    rerun_command: str,
    start_idx: int,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    errors = _list(report.get("errors"))
    for error in errors:
        message = _text(error)
        if not message:
            continue
        issues.append(
            _issue(
                start_idx + len(issues),
                severity="blocking",
                layer=default_layer,
                artifact=default_artifact,
                field_path="",
                message=message,
                why_it_matters="This validator failed; downstream workflow stages cannot rely on the artifact.",
                repair_owner=default_layer,
                repair_action="Repair the upstream artifact identified by this validator, then rerun the command.",
                rerun_command=rerun_command,
                downstream_blocked=True,
            )
        )
    return issues


def _issues_from_run_state(
    report: dict[str, Any],
    *,
    default_layer: str,
    default_artifact: str,
    rerun_command: str,
    start_idx: int,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    owner = _text(report.get("repair_target_role") or report.get("owner_role") or default_layer)
    artifact = _text(report.get("repair_target_artifact") or default_artifact)
    for missing in _list(report.get("missing_artifacts")):
        issues.append(
            _issue(
                start_idx + len(issues),
                severity="blocking",
                layer=owner,
                artifact=_text(missing) or artifact,
                field_path="",
                message=f"missing {_text(missing)}",
                why_it_matters="The workflow cannot advance until the required artifact exists.",
                repair_owner=owner,
                repair_action=_text(report.get("recommended_action") or "Create or regenerate the missing artifact."),
                rerun_command=rerun_command,
                downstream_blocked=True,
            )
        )
    for failed in _list(report.get("failed_validations")):
        if not isinstance(failed, dict):
            continue
        errors = _list(failed.get("errors"))
        message = "; ".join(_text(item) for item in errors if _text(item)) or _text(failed.get("error") or failed.get("status"))
        issues.append(
            _issue(
                start_idx + len(issues),
                severity="blocking",
                layer=_text(failed.get("repair_owner") or owner),
                artifact=_text(failed.get("path") or artifact),
                field_path=_text(failed.get("field_path")),
                message=message or _default_message(report),
                why_it_matters="The failed validation blocks downstream generation or delivery.",
                repair_owner=_text(failed.get("repair_owner") or owner),
                repair_action=_text(failed.get("repair_action") or report.get("recommended_action") or "Repair the failed validation target."),
                rerun_command=rerun_command,
                downstream_blocked=True,
            )
        )
    for stale in _list(report.get("stale_validations")):
        if not isinstance(stale, dict):
            continue
        issues.append(
            _issue(
                start_idx + len(issues),
                severity="blocking",
                layer=owner,
                artifact=_text(stale.get("validation") or artifact),
                field_path="",
                message=f"stale validation: {_text(stale.get('validation'))}",
                why_it_matters="The validation is older than its inputs and cannot be trusted.",
                repair_owner=owner,
                repair_action="Rerun the validator after regenerating changed inputs.",
                rerun_command=rerun_command,
                downstream_blocked=True,
            )
        )
    return issues


def normalize_report(
    report: dict[str, Any],
    *,
    default_layer: str = "qc",
    default_artifact: str = "",
    rerun_command: str = "",
) -> dict[str, Any]:
    issues = _issues_from_repair_targets(
        report,
        default_layer=default_layer,
        default_artifact=default_artifact,
        rerun_command=rerun_command,
    )
    issues.extend(
        _issues_from_errors(
            report,
            default_layer=default_layer,
            default_artifact=default_artifact,
            rerun_command=rerun_command,
            start_idx=len(issues) + 1,
        )
    )
    issues.extend(
        _issues_from_run_state(
            report,
            default_layer=default_layer,
            default_artifact=default_artifact,
            rerun_command=rerun_command,
            start_idx=len(issues) + 1,
        )
    )
    if not issues and report.get("is_valid") is False:
        issues.append(
            _issue(
                1,
                severity="blocking",
                layer=default_layer,
                artifact=default_artifact,
                field_path="",
                message=_default_message(report),
                why_it_matters="The report is invalid and blocks downstream workflow stages.",
                repair_owner=default_layer,
                repair_action="Inspect the validator output, repair the upstream artifact, and rerun the command.",
                rerun_command=rerun_command,
                downstream_blocked=True,
            )
        )

    blocking_count = sum(1 for item in issues if item.get("downstream_blocked") and item.get("severity") in {"blocking", "error"})
    report_is_valid = report.get("is_valid")
    if report_is_valid is None:
        report_is_valid = report.get("status") == "passed"
    return {
        "schema_version": "qc_repair_report_v1",
        "is_valid": bool(report_is_valid) and blocking_count == 0,
        "blocking_issue_count": blocking_count,
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--layer", default="qc")
    parser.add_argument("--artifact", default="")
    parser.add_argument("--rerun-command", default="")
    parser.add_argument("--output")
    args = parser.parse_args()

    payload = load_json_file(Path(args.report))
    if not isinstance(payload, dict):
        payload = {"is_valid": False, "errors": [f"{args.report} is not a JSON object"]}
    normalized = normalize_report(
        payload,
        default_layer=args.layer,
        default_artifact=args.artifact,
        rerun_command=args.rerun_command,
    )
    text = json.dumps(normalized, ensure_ascii=False, indent=2)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if normalized["is_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
