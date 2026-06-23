#!/usr/bin/env python3
"""Validate page_argument_pack.json before deck generation."""

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
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts" / "_lib"
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
from pathlib import Path
from typing import Any

from json_utils import load_json_file


PA_RE = re.compile(r"^PA-\d{3}$")
IA_RE = re.compile(r"^IA-\d{3}$")
EV_RE = re.compile(r"^EV-\d{3}$")
MET_RE = re.compile(r"^MET-\d{3}$")
PERMISSION_FIELDS = ("headline_allowed", "main_message_allowed", "chart_allowed", "body_copy_allowed")


def text(value: Any) -> str:
    return str(value or "").strip()


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _issue_analysis_ids(payload: dict[str, Any] | None) -> set[str]:
    if not isinstance(payload, dict):
        return set()
    return {
        text(item.get("analysis_id") or item.get("issue_analysis_id") or item.get("id"))
        for item in as_list(payload.get("issue_analyses"))
        if isinstance(item, dict) and text(item.get("analysis_id") or item.get("issue_analysis_id") or item.get("id"))
    }


def _permission_from_usage(usage: str) -> dict[str, bool]:
    return {
        "headline_allowed": usage == "headline_allowed",
        "main_message_allowed": usage == "headline_allowed",
        "chart_allowed": usage in {"headline_allowed", "body_only"},
        "body_copy_allowed": usage in {"headline_allowed", "body_only", "supporting_context", "context_only", "caveat_only"},
    }


def _permission_shape(value: Any) -> dict[str, bool] | None:
    if not isinstance(value, dict):
        return None
    if any(not isinstance(value.get(field), bool) for field in PERMISSION_FIELDS):
        return None
    return {field: bool(value.get(field) is True) for field in PERMISSION_FIELDS}


def validate(payload: dict[str, Any], issue_analysis: dict[str, Any] | None = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("schema_version") != "page_argument_pack_v1":
        errors.append("schema_version must be page_argument_pack_v1")
    if text(payload.get("authoring_status")) == "skeleton_for_llm_reasoning_authoring":
        errors.append("page_argument_pack is still a Python-generated skeleton; Reasoning LLM must author the final pack before validation")
    rows = payload.get("page_arguments")
    if not isinstance(rows, list):
        errors.append("page_arguments must be an array")
        return errors, warnings
    if not rows:
        errors.append("page_arguments must contain at least one candidate page argument")
    seen_ids: set[str] = set()
    valid_issue_ids = _issue_analysis_ids(issue_analysis)
    allowed_usage = {
        "headline_allowed",
        "body_only",
        "supporting_context",
        "context_only",
        "caveat_only",
        "diligence_only",
        "caveat_or_diligence_question_only",
        "not_allowed_in_headline",
        "not_allowed",
    }
    for idx, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"page_arguments[{idx}] must be an object")
            continue
        arg_id = text(row.get("page_argument_id")) or f"page_arguments[{idx}]"
        if not PA_RE.fullmatch(arg_id):
            errors.append(f"{arg_id}: page_argument_id must follow PA-001 format")
        elif arg_id in seen_ids:
            errors.append(f"{arg_id}: duplicate page_argument_id")
        else:
            seen_ids.add(arg_id)
        for field in ("source_issue_analysis_id", "page_argument", "evidence_status", "allowed_deck_usage"):
            if not text(row.get(field)):
                errors.append(f"{arg_id}: {field} is required")
        source_ia = text(row.get("source_issue_analysis_id"))
        if source_ia and not IA_RE.fullmatch(source_ia):
            errors.append(f"{arg_id}: source_issue_analysis_id must follow IA-001 format")
        if valid_issue_ids and source_ia and source_ia not in valid_issue_ids:
            errors.append(f"{arg_id}: source_issue_analysis_id {source_ia} not found in issue_analysis")
        usage = text(row.get("allowed_deck_usage"))
        if usage not in allowed_usage:
            errors.append(f"{arg_id}: allowed_deck_usage must be one of {sorted(allowed_usage)}")
        permission = _permission_shape(row.get("downstream_permission"))
        if permission is None:
            errors.append(f"{arg_id}: downstream_permission must contain boolean fields {list(PERMISSION_FIELDS)}")
            permission = _permission_from_usage(usage)
        expected_floor = _permission_from_usage(usage)
        if usage == "headline_allowed" and not permission["headline_allowed"]:
            errors.append(f"{arg_id}: headline_allowed usage requires downstream_permission.headline_allowed=true")
        if usage in {"body_only", "supporting_context", "context_only", "caveat_only"} and permission["headline_allowed"]:
            errors.append(f"{arg_id}: {usage} cannot set downstream_permission.headline_allowed=true")
        if expected_floor["body_copy_allowed"] and not permission["body_copy_allowed"]:
            errors.append(f"{arg_id}: {usage} requires downstream_permission.body_copy_allowed=true")
        if usage == "headline_allowed" and not (as_list(row.get("evidence_ids")) or as_list(row.get("metric_ids"))):
            errors.append(f"{arg_id}: headline_allowed requires evidence_ids or metric_ids")
        for ev_id in as_list(row.get("evidence_ids")):
            if not EV_RE.fullmatch(text(ev_id)):
                errors.append(f"{arg_id}: invalid evidence_id '{text(ev_id)}'")
        for met_id in as_list(row.get("metric_ids")):
            if not MET_RE.fullmatch(text(met_id)):
                errors.append(f"{arg_id}: invalid metric_id '{text(met_id)}'")
        evidence_status = text(row.get("evidence_status"))
        if usage == "headline_allowed" and evidence_status != "supported":
            errors.append(f"{arg_id}: headline_allowed requires evidence_status=supported")
        if text(row.get("evidence_status")) in {"not_researched", "rejected"} and usage != "not_allowed":
            errors.append(f"{arg_id}: not_researched/rejected evidence cannot be used in deck")
        if not text(row.get("hypothesis_resolution_status")):
            if usage in {"headline_allowed", "body_only", "supporting_context", "context_only"}:
                errors.append(f"{arg_id}: usable page arguments require hypothesis_resolution_status")
            else:
                warnings.append(f"{arg_id}: hypothesis_resolution_status is missing; link page arguments back to hypothesis resolution when available")
        if usage in {"caveat_only", "diligence_only", "caveat_or_diligence_question_only", "not_allowed_in_headline"}:
            warnings.append(f"{arg_id}: cannot be used as headline; keep as caveat/body/open question")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page-argument-pack", required=True)
    parser.add_argument("--issue-analysis", help="Optional lineage cross-check artifact.")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        payload = load_json_file(Path(args.page_argument_pack))
        issue_analysis = load_json_file(Path(args.issue_analysis)) if args.issue_analysis else None
        errors, warnings = validate(payload, issue_analysis)
    except Exception as exc:
        errors, warnings = [f"cannot read page argument pack: {exc}"], []
    result = {
        "is_valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "repair_plan": {
            "primary_repair_target": "artifacts/page_argument_pack.json",
            "repair_target_role": "reasoning",
            "do_not_edit": ["deck_blueprint.json", "renderer_spec.json"],
        } if errors else {},
    }
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["is_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
