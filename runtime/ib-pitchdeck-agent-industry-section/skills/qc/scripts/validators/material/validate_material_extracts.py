#!/usr/bin/env python3
"""Validate material_extracts.json after LLM material fact extraction.

Raw text capture is only proof that the material can be read. It is not proof
that the material has been understood or can support evidence. Source-faithful
facts, metrics, quotes, unknowns, and claim-use limits must be supplied by the
Material/Knowledge LLM before this validator should pass.
"""

from __future__ import annotations

# Runtime scripts can be run directly. Shared helpers remain in runtime
# `scripts/`; production tools live under role scripts; validators live under QC.
import sys as _ib_sys
from pathlib import Path as _IbPath
_IB_ROLE_SCRIPT_DIR = _IbPath(__file__).resolve().parent
_IB_RUNTIME_ROOT = next(
    _p for _p in _IbPath(__file__).resolve().parents
    if (_p / 'templates').is_dir() and (_p / 'skills').is_dir() and (_p / 'scripts').is_dir()
)
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts"
_IB_ROLE_SCRIPT_DIRS = sorted((_IB_RUNTIME_ROOT / 'skills').glob('*/scripts'))
_IB_QC_VALIDATOR_DIRS = sorted((_IB_RUNTIME_ROOT / 'skills' / 'qc' / 'scripts' / 'validators').glob('*'))
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
        if not text(item.get("extracted_text_path")) and not text(item.get("raw_text_path")):
            warnings.append(f"{material_id}: extracted_text_path/raw_text_path is required for content capture")
        if not text(item.get("extraction_limitations")):
            warnings.append(f"{material_id}: extraction_limitations is empty; use `none` if no limitation")
        status = text(item.get("extraction_status"))
        raw_text_available = bool(item.get("raw_text_available")) or status == "complete"
        llm_status = text(item.get("llm_extraction_status")) or "pending_llm_extraction"
        facts = as_list(item.get("extracted_facts"))
        metrics = as_list(item.get("extracted_metrics"))
        quotes = as_list(item.get("quoted_excerpts"))
        completed_no_evidence_statuses = {
            "project_brief_transcribed_to_input_card",
            "not_relevant_for_knowledge",
            "no_extractable_facts",
            "blocked_no_readable_text",
        }
        completed_extraction_statuses = {
            "industry_facts_extracted",
            "complete",
            "reviewed",
            "llm_extracted",
        }
        if raw_text_available and llm_status in {"", "pending", "pending_llm_extraction"}:
            errors.append(
                f"{material_id}: raw content is captured but LLM extraction is pending. "
                "After reading captured content, set llm_extraction_status to "
                "project_brief_transcribed_to_input_card, industry_facts_extracted, "
                "not_relevant_for_knowledge, or no_extractable_facts."
            )
        if llm_status in completed_extraction_statuses and not facts and not metrics and not as_list(item.get("unknowns_or_conflicts")):
            errors.append(
                f"{material_id}: llm_extraction_status={llm_status} requires extracted_facts, "
                "extracted_metrics, or explicit unknowns_or_conflicts"
            )
        if llm_status in completed_no_evidence_statuses and item.get("can_be_used_as_evidence") is True:
            errors.append(
                f"{material_id}: llm_extraction_status={llm_status} cannot have can_be_used_as_evidence=true"
            )
        if item.get("can_be_used_as_evidence") is True:
            if llm_status not in completed_extraction_statuses:
                errors.append(
                    f"{material_id}: can_be_used_as_evidence=true requires llm_extraction_status=industry_facts_extracted/complete/reviewed/llm_extracted"
                )
            if not facts and not metrics:
                errors.append(
                    f"{material_id}: can_be_used_as_evidence=true requires extracted_facts or extracted_metrics"
                )
            if not quotes:
                errors.append(
                    f"{material_id}: can_be_used_as_evidence=true requires quoted_excerpts with locators"
                )
            if status != "complete" and not raw_text_available:
                errors.append(
                    f"{material_id}: can_be_used_as_evidence=true requires captured raw text"
                )
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
    repair_plan = {}
    if errors or warnings:
        repair_plan = {
            "primary_repair_target": "artifacts/material_extracts.json",
            "repair_target_role": "material-intake",
            "repair_action": (
                "Run this validator only after LLM extraction. The Material/Knowledge LLM must "
                "read captured content, transcribe project facts into input_card or extract "
                "industry facts/metrics/quotes for Knowledge, then set llm_extraction_status "
                "and can_be_used_as_evidence intentionally."
            ),
        }
    result = {
        "is_valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "repair_plan": repair_plan,
    }
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["is_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
