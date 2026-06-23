#!/usr/bin/env python3
"""Validate executable_search_batch.json after LLM query authoring."""

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
import sys
from pathlib import Path
from typing import Any

from json_utils import load_json_file


BLOCKED_MARKERS = ("LLM_REWRITE_REQUIRED", "TODO", "TBD", "PLACEHOLDER", "<", ">")
READY_STATUSES = {"authored", "ready", "ready_for_execution", "llm_authored"}
QUERY_FIELDS = ("english_query", "chinese_query", "source_specific_query")


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _has_blocked_marker(value: str) -> bool:
    upper = value.upper()
    return any(marker in upper for marker in BLOCKED_MARKERS)


def validate(payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("schema_version") != "search_batch_v1":
        errors.append("schema_version must be search_batch_v1")
    batches = payload.get("batches")
    if not isinstance(batches, list) or not batches:
        return errors + ["batches must be a non-empty array"], warnings

    seen_instruction_ids: set[str] = set()
    for idx, row in enumerate(batches, start=1):
        prefix = f"batches[{idx}]"
        if not isinstance(row, dict):
            errors.append(f"{prefix} must be an object")
            continue
        instruction_id = _text(row.get("search_instruction_id"))
        if not instruction_id:
            errors.append(f"{prefix}: search_instruction_id is required")
        elif instruction_id in seen_instruction_ids:
            errors.append(f"{prefix}: duplicate search_instruction_id {instruction_id}")
        seen_instruction_ids.add(instruction_id)

        status = _text(row.get("query_status"))
        if status not in READY_STATUSES:
            errors.append(f"{prefix}: query_status must be one of {sorted(READY_STATUSES)} after LLM query authoring")

        for field in QUERY_FIELDS:
            query = _text(row.get(field))
            if len(query) < 12:
                errors.append(f"{prefix}: {field} is too short for executable search")
            if _has_blocked_marker(query):
                errors.append(f"{prefix}: {field} still contains a placeholder marker: {query}")

        fallback_queries = [
            _text(item)
            for item in _as_list(row.get("fallback_queries"))
            if _text(item)
        ]
        if not fallback_queries:
            warnings.append(f"{prefix}: fallback_queries is empty; add fallbacks when source coverage is likely weak")
        if not _text(row.get("expected_source_type")):
            errors.append(f"{prefix}: expected_source_type is required")
        if not _text(row.get("why_this_search_matters")):
            warnings.append(f"{prefix}: why_this_search_matters is empty")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable-search-batch", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    try:
        payload = load_json_file(Path(args.executable_search_batch))
        errors, warnings = validate(payload)
    except Exception as exc:
        errors, warnings = [str(exc)], []

    result = {
        "is_valid": not errors,
        "executable_search_batch": args.executable_search_batch,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "repair_target_layer": "research",
        "primary_repair_target": "artifacts/executable_search_batch.json",
        "recommended_action": (
            "Use the Research LLM query-authoring step to replace placeholders, set query_status=authored, "
            "and preserve one row per formal_search_plan instruction."
        ),
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
