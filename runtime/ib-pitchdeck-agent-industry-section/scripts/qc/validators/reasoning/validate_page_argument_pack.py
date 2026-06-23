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
from pathlib import Path
from typing import Any

from json_utils import load_json_file


def text(value: Any) -> str:
    return str(value or "").strip()


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def validate(payload: dict[str, Any]) -> tuple[list[str], list[str]]:
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
        for field in ("source_issue_analysis_id", "page_argument", "evidence_status", "allowed_deck_usage"):
            if not text(row.get(field)):
                errors.append(f"{arg_id}: {field} is required")
        usage = text(row.get("allowed_deck_usage"))
        if usage not in allowed_usage:
            errors.append(f"{arg_id}: allowed_deck_usage must be one of {sorted(allowed_usage)}")
        if usage == "headline_allowed" and not (as_list(row.get("evidence_ids")) or as_list(row.get("metric_ids"))):
            errors.append(f"{arg_id}: headline_allowed requires evidence_ids or metric_ids")
        if text(row.get("evidence_status")) in {"not_researched", "rejected"} and usage != "not_allowed":
            errors.append(f"{arg_id}: not_researched/rejected evidence cannot be used in deck")
        if not text(row.get("hypothesis_resolution_status")):
            warnings.append(f"{arg_id}: hypothesis_resolution_status is missing; link page arguments back to hypothesis resolution when available")
        if usage in {"caveat_only", "diligence_only", "caveat_or_diligence_question_only", "not_allowed_in_headline"}:
            warnings.append(f"{arg_id}: cannot be used as headline; keep as caveat/body/open question")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page-argument-pack", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        payload = load_json_file(Path(args.page_argument_pack))
        errors, warnings = validate(payload)
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
