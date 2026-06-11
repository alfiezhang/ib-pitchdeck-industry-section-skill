#!/usr/bin/env python3
"""Validate material_extracts.json for explicit source-faithful extraction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from json_utils import load_json_file
from material_intake_common import text


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def validate(payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("schema_version") != "material_extracts_v1":
        errors.append("schema_version must be material_extracts_v1")
    extracts = payload.get("extracts")
    if not isinstance(extracts, list):
        errors.append("extracts must be an array")
        return errors, warnings
    for idx, item in enumerate(extracts, start=1):
        if not isinstance(item, dict):
            errors.append(f"extracts[{idx}] must be an object")
            continue
        material_id = text(item.get("material_id")) or f"extracts[{idx}]"
        if not text(item.get("source_type")):
            errors.append(f"{material_id}: source_type is required")
        if not text(item.get("file_path_or_url")):
            errors.append(f"{material_id}: file_path_or_url is required")
        if not text(item.get("source_access")):
            warnings.append(f"{material_id}: source_access is missing")
        if not text(item.get("extracted_text_path")):
            warnings.append(f"{material_id}: extracted_text_path is required")
        if not text(item.get("extraction_limitations")):
            warnings.append(f"{material_id}: extraction_limitations is empty; use `none` if no limitation")
        status = text(item.get("extraction_status"))
        if status in {"usable"}:
            if not as_list(item.get("extracted_facts")) and not as_list(item.get("extracted_metrics")):
                warnings.append(f"{material_id}: usable extraction should include extracted_facts or extracted_metrics")
        if not as_list(item.get("quoted_excerpts")):
            warnings.append(f"{material_id}: quote placeholders are helpful but optional at skeleton stage")
        if item.get("can_be_used_as_evidence") is True and text(item.get("extraction_status")) != "complete":
            warnings.append(f"{material_id}: can_be_used_as_evidence=true should align with extraction_status=complete")
        for fact_idx, fact in enumerate(as_list(item.get("extracted_facts")), start=1):
            if not isinstance(fact, dict):
                errors.append(f"{material_id}.extracted_facts[{fact_idx}] must be an object")
                continue
            for field in ("fact", "locator", "source_type"):
                if not text(fact.get(field)):
                    errors.append(f"{material_id}.extracted_facts[{fact_idx}].{field} is required")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--material-extracts", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        payload = load_json_file(Path(args.material_extracts))
        errors, warnings = validate(payload)
    except Exception as exc:
        errors, warnings = [f"cannot read material extracts: {exc}"], []
    result = {
        "is_valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "repair_plan": {
            "primary_repair_target": "artifacts/material_extracts.json",
            "repair_target_role": "material-intake",
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
