#!/usr/bin/env python3
"""Validate page_argument_pack.json before deck generation."""

from __future__ import annotations

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
    rows = payload.get("page_arguments")
    if not isinstance(rows, list):
        errors.append("page_arguments must be an array")
        return errors, warnings
    if not rows:
        errors.append("page_arguments must contain at least one candidate page argument")
    allowed_usage = {"headline_allowed", "body_only", "context_only", "caveat_or_diligence_question_only", "not_allowed_in_headline", "not_allowed"}
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
        if usage in {"caveat_or_diligence_question_only", "not_allowed_in_headline"}:
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
