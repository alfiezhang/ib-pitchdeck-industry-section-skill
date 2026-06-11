#!/usr/bin/env python3
"""Validate hypothesis_store.json and enforce hypothesis-is-not-conclusion discipline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from json_utils import load_json_file


def text(value: Any) -> str:
    return str(value or "").strip()


def validate(payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("schema_version") != "hypothesis_store_v1":
        errors.append("schema_version must be hypothesis_store_v1")
    hypotheses = payload.get("hypotheses")
    if not isinstance(hypotheses, list):
        errors.append("hypotheses must be an array")
        return errors, warnings
    seen: set[str] = set()
    allowed_resolution = {"pending_resolution", "research_required", "supported", "directional", "caveat_only", "rejected"}
    allowed_usage = {"headline_allowed", "body_only", "context_only", "caveat_or_diligence_question_only", "not_allowed_in_headline", "not_allowed"}
    for idx, item in enumerate(hypotheses, start=1):
        if not isinstance(item, dict):
            errors.append(f"hypotheses[{idx}] must be an object")
            continue
        hyp_id = text(item.get("hypothesis_id"))
        if not hyp_id:
            errors.append(f"hypotheses[{idx}].hypothesis_id is required")
        elif hyp_id in seen:
            errors.append(f"duplicate hypothesis_id: {hyp_id}")
        seen.add(hyp_id)
        if not text(item.get("hypothesis")):
            errors.append(f"{hyp_id or idx}: hypothesis is required")
        resolution = text(item.get("resolution_status"))
        if resolution not in allowed_resolution:
            errors.append(f"{hyp_id or idx}: resolution_status must be one of {sorted(allowed_resolution)}")
        usage = text(item.get("allowed_use_before_resolution"))
        if usage and usage not in allowed_usage:
            errors.append(f"{hyp_id or idx}: allowed_use_before_resolution must be one of {sorted(allowed_usage)}")
        if resolution in {"pending_resolution", "research_required"} and usage == "headline_allowed":
            errors.append(f"{hyp_id or idx}: unresolved hypothesis cannot be headline_allowed")
        if resolution == "supported" and not text(item.get("supporting_evidence_ids")):
            warnings.append(f"{hyp_id or idx}: supported hypothesis should list supporting_evidence_ids")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hypothesis-store", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        payload = load_json_file(Path(args.hypothesis_store))
        errors, warnings = validate(payload)
    except Exception as exc:
        errors, warnings = [f"cannot read hypothesis store: {exc}"], []
    result = {
        "is_valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "repair_plan": {
            "primary_repair_target": "artifacts/hypothesis_store.json",
            "repair_target_role": "reasoning",
        } if errors else {},
    }
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["is_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
