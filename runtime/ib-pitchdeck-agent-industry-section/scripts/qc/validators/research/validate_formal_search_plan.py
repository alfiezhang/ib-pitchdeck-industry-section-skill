#!/usr/bin/env python3
"""Validate the formal search plan before execution.

The plan is not a findings gate. It checks that research is executable,
taxonomy-safe, and broad enough to prevent thin downstream issue analysis.
"""

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
import sys
from pathlib import Path
from typing import Any

from issue_taxonomy import ISSUE_TOPICS_BY_AREA, is_valid_issue_pair
from json_utils import load_json_file


SCHEMA_VERSION = "formal_search_plan_v1"
FS_RE = re.compile(r"^FS-\d{3}$")
PLACEHOLDER_RE = re.compile(
    r"(<[^>]+>|TODO|TBD|N/A|xxxx|yyyy|placeholder|LLM_REWRITE_REQUIRED|待补|待搜索|示例|example)",
    flags=re.IGNORECASE,
)
PAGE_PLAN_MARKERS = (
    "slide_no",
    "selected_page_type",
    "page_thesis",
    "headline",
    "main_message",
    "deck_blueprint",
    "renderer_spec",
    "ppt",
    "storyboard",
    "页面标题",
    "页标题",
    "幻灯片",
)
PREMATURE_FINDING_MARKERS = (
    "validated finding",
    "confirmed finding",
    "investment thesis",
    "page conclusion",
    "already proven",
    "已验证结论",
    "确认结论",
    "投资结论",
    "页面结论",
)
VALID_PRIORITIES = {"high", "medium", "low"}
VALID_EXECUTION_EXPECTATIONS = {"deep_search", "light_search", "accounting_only"}
PLANNED_SEARCH_STAGE = "formal_research_execution"
VALID_PLAN_TERMINAL_STATUSES = {"pending"}
REQUIRED_PAIRS = {
    (issue_area, subissue)
    for issue_area, subissues in ISSUE_TOPICS_BY_AREA.items()
    for subissue in subissues
}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _walk_text(value: Any) -> list[str]:
    texts: list[str] = []
    if isinstance(value, dict):
        for child in value.values():
            texts.extend(_walk_text(child))
    elif isinstance(value, list):
        for child in value:
            texts.extend(_walk_text(child))
    elif isinstance(value, str):
        texts.append(value)
    return texts


def _contains_marker(text: str, markers: tuple[str, ...]) -> str:
    lowered = text.lower()
    for marker in markers:
        if marker.lower() in lowered:
            return marker
    return ""


def _taxonomy_hint(issue_area: str) -> str:
    if issue_area in ISSUE_TOPICS_BY_AREA:
        valid = ", ".join(sorted(ISSUE_TOPICS_BY_AREA[issue_area]))
        return f" Valid subissues for '{issue_area}': {valid}."
    valid_areas = ", ".join(sorted(ISSUE_TOPICS_BY_AREA))
    return f" Valid issue_area values: {valid_areas}."


def validate(plan: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if plan.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if not isinstance(plan.get("meta"), dict):
        errors.append("meta must be an object")
    if _text(plan.get("plan_mode")) != "coverage_audit":
        errors.append("plan_mode must be 'coverage_audit' to mark this as a canonical coverage-audit plan")
    if not isinstance(plan.get("industry_scope_pack"), dict):
        errors.append("industry_scope_pack must be an object linking the scope artifact")

    issue_plan = plan.get("issue_search_plan")
    if not isinstance(issue_plan, list) or not issue_plan:
        errors.append("issue_search_plan must be a non-empty array")
        issue_plan = []

    seen_fs: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    for item_idx, item in enumerate(issue_plan, start=1):
        if not isinstance(item, dict):
            errors.append(f"issue_search_plan[{item_idx}] must be an object")
            continue
        prefix = f"issue_search_plan[{item_idx}]"
        issue_area = _text(item.get("issue_area"))
        subissue = _text(item.get("subissue"))
        if not is_valid_issue_pair(issue_area, subissue):
            errors.append(
                f"{prefix}: invalid issue_area/subissue pair '{issue_area}/{subissue}'."
                f"{_taxonomy_hint(issue_area)} Use scripts/issue_taxonomy.py as the canonical list."
            )
        else:
            pair = (issue_area, subissue)
            if pair in seen_pairs:
                warnings.append(f"{prefix}: duplicate issue_area/subissue pair '{issue_area}/{subissue}'")
            seen_pairs.add(pair)

        question = _text(item.get("research_question"))
        if len(question) < 12:
            errors.append(f"{prefix}: research_question is too short to guide execution")
        if _contains_marker(question, PAGE_PLAN_MARKERS):
            errors.append(f"{prefix}: research_question contains page/deck planning language")
        if _contains_marker(question, PREMATURE_FINDING_MARKERS):
            errors.append(f"{prefix}: research_question contains premature conclusion language")

        priority = _text(item.get("priority")).lower()
        if priority not in VALID_PRIORITIES:
            errors.append(f"{prefix}: priority must be one of {sorted(VALID_PRIORITIES)}")

        execution_expectation = _text(item.get("execution_expectation")).lower()
        if execution_expectation not in VALID_EXECUTION_EXPECTATIONS:
            errors.append(f"{prefix}: execution_expectation must be one of {sorted(VALID_EXECUTION_EXPECTATIONS)}")
        minimum_actual_searches_raw = item.get("minimum_actual_searches")
        if not isinstance(minimum_actual_searches_raw, int) or minimum_actual_searches_raw < 0:
            errors.append(f"{prefix}: minimum_actual_searches must be a non-negative integer")
            minimum_actual_searches = 0
        else:
            minimum_actual_searches = minimum_actual_searches_raw
        if item.get("coverage_required") is not True:
            errors.append(f"{prefix}: coverage_required must be true; taxonomy rows are coverage audit rows even when not material")
        terminal_status = _text(item.get("terminal_status")).lower()
        if terminal_status not in VALID_PLAN_TERMINAL_STATUSES:
            errors.append(f"{prefix}: terminal_status must be pending in the search plan; execution status belongs in formal_research_execution_report.json")
        if execution_expectation == "deep_search" and minimum_actual_searches < 2:
            warnings.append(f"{prefix}: deep_search rows should normally set minimum_actual_searches >= 2")
        if execution_expectation == "light_search" and minimum_actual_searches < 1:
            warnings.append(f"{prefix}: light_search rows should normally set minimum_actual_searches >= 1")
        if execution_expectation == "accounting_only" and minimum_actual_searches != 0:
            warnings.append(f"{prefix}: accounting_only rows should normally set minimum_actual_searches to 0")

        instructions = item.get("search_instructions")
        if not isinstance(instructions, list) or not instructions:
            errors.append(f"{prefix}: search_instructions must be a non-empty array")
            instructions = []
        for inst_idx, instruction in enumerate(instructions, start=1):
            inst_prefix = f"{prefix}.search_instructions[{inst_idx}]"
            if not isinstance(instruction, dict):
                errors.append(f"{inst_prefix} must be an object")
                continue
            instruction_id = _text(instruction.get("instruction_id"))
            if not FS_RE.fullmatch(instruction_id):
                errors.append(f"{inst_prefix}: instruction_id must follow FS-001 format")
            elif instruction_id in seen_fs:
                errors.append(f"{inst_prefix}: duplicate instruction_id {instruction_id}")
            else:
                seen_fs.add(instruction_id)

            purpose = _text(instruction.get("purpose"))
            search_stage = _text(instruction.get("search_stage"))
            if search_stage != PLANNED_SEARCH_STAGE:
                errors.append(
                    f"{inst_prefix}: search_stage must be '{PLANNED_SEARCH_STAGE}' to distinguish planned formal search rows from boundary scoping queries"
                )
            if "query" in instruction or "query_variants" in instruction:
                errors.append(
                    f"{inst_prefix}: executable query fields belong only in artifacts/executable_search_batch.json; "
                    "formal_search_plan is the coverage/evidence-need source of truth"
                )
            if len(purpose) < 8:
                errors.append(f"{inst_prefix}: purpose is too short")
            if _contains_marker(purpose, PAGE_PLAN_MARKERS):
                errors.append(f"{inst_prefix}: search instruction contains page/deck planning language")
            if _contains_marker(purpose, PREMATURE_FINDING_MARKERS):
                errors.append(f"{inst_prefix}: search instruction contains premature conclusion language")

        if priority == "high" and execution_expectation == "deep_search" and len(instructions) < 1:
            warnings.append(
                f"{prefix}: high-priority deep_search issue has no planned instruction. "
                "Use executable_search_batch.json for multiple concrete query attempts."
            )

    for text in _walk_text(plan.get("research_discipline", {})):
        if _contains_marker(text, PAGE_PLAN_MARKERS):
            warnings.append("research_discipline mentions page/deck terms; ensure this remains an execution rule, not page planning")

    missing_pairs = sorted(REQUIRED_PAIRS - seen_pairs)
    if missing_pairs:
        preview = ", ".join(f"{area}/{subissue}" for area, subissue in missing_pairs[:20])
        errors.append(
            "formal_search_plan must cover every canonical issue_area/subissue so upstream research is not thin. "
            "Add issue_search_plan entries with planned FS instructions for: "
            + preview
        )
        if len(missing_pairs) > 20:
            errors.append(f"...and {len(missing_pairs) - 20} more missing issue/subissue pair(s)")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formal-search-plan", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    try:
        plan = load_json_file(Path(args.formal_search_plan))
    except Exception as exc:
        result = {
            "is_valid": False,
            "error_count": 1,
            "warning_count": 0,
            "errors": [f"cannot read formal_search_plan.json: {exc}"],
            "warnings": [],
            "formal_search_plan": args.formal_search_plan,
        }
    else:
        if not isinstance(plan, dict):
            errors, warnings = ["formal_search_plan.json must be a JSON object"], []
        else:
            errors, warnings = validate(plan)
        result = {
            "is_valid": not errors,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "errors": errors,
            "warnings": warnings,
            "formal_search_plan": args.formal_search_plan,
        }

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["is_valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
