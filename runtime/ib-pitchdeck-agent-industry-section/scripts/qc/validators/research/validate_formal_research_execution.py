#!/usr/bin/env python3
"""Validate formal research execution against the industry issue taxonomy.

The search plan is intentionally lightweight. This validator is the formal
research gate: it checks that the agent actually ran issue/subissue research,
reviewed sources, recorded limitations, and did not promote unresolved gaps as
usable research findings.
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


RESULT_ID_RE = re.compile(r"^FR-\d{3}$")
EV_RE = re.compile(r"\bEV-\d{3}\b")
MET_RE = re.compile(r"\bMET-\d{3}\b")
FS_RE = re.compile(r"^FS-\d{3}$")
FULL_URL_RE = re.compile(r"^https?://[^\s\]|)）>]+$", flags=re.IGNORECASE)
FIELD_LINE_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\*\*)?([^:*#][^:]*?)(?:\*\*)?\s*:\s*(.*?)\s*$"
)
SEARCH_HEADING_RE = re.compile(
    r"^###\s+(?:Search\s+)?(?:#?\s*)?(?:S-?)?(\d+)\b.*?$",
    flags=re.MULTILINE | re.IGNORECASE,
)
FORMAL_STAGES = {
    "formal_research",
    "formal research",
    "formal_research_execution",
    "formal research execution",
    "latest_check",
    "latest",
    "peer_check",
    "peer check",
}
BROAD_STAGES = {"broad_discovery", "broad discovery", "scoping", "industry_scope"}
VALID_RESULT_STATUS = {
    "supported",
    "thin",
    "conflicting",
    "not_comparable",
    "insufficient",
    "unavailable_after_research",
}
EVIDENCE_STATUSES = {"supported", "thin", "conflicting", "not_comparable"}
UNRESOLVED_STATUSES = {"insufficient", "unavailable_after_research"}
VALID_TERMINAL_STATUSES = {
    "executed_with_evidence",
    "executed_no_usable_source",
    "directional_only",
    "not_executed",
    "not_material",
    "accounting_only",
}
NO_ATTEMPT_TERMINAL_STATUSES = {"not_executed", "not_material", "accounting_only"}
VALID_DOWNSTREAM_PERMISSIONS = {"may_support_claim", "contextual_only", "research_backlog_only", "not_allowed"}
REPORT_STRUCTURE_HINT = (
    "Start from configs/artifact_templates/formal_research_execution_report.skeleton.json. "
    "For each executed FS-xxx, create one FR-xxx issue_results[] entry and copy "
    "issue_area, subissue, and research_question from the owning formal_search_plan issue_search_plan[] item."
)
ATTEMPT_ID_HINT = (
    "search_instruction_ids must contain planned FS-xxx IDs from formal_search_plan.json; "
    "search_attempt_ids must contain actual S-xxx search attempts from search_log.md. "
    "If no S-xxx exists for an FS-xxx, run the real formal search and append it to search_log.md first."
)


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _normalize_attempt_id(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    match = re.search(r"(\d+)", text)
    if not match:
        return text.upper()
    return f"S-{int(match.group(1)):03d}"


def parse_search_attempts(search_log_path: Path) -> dict[str, dict[str, str]]:
    text = search_log_path.read_text(encoding="utf-8")
    matches = list(SEARCH_HEADING_RE.finditer(text))
    attempts: dict[str, dict[str, str]] = {}
    for idx, match in enumerate(matches):
        number = int(match.group(1))
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        block = text[start:end]
        fields: dict[str, str] = {}
        for line in block.splitlines():
            field_match = FIELD_LINE_RE.match(line)
            if not field_match:
                continue
            key = re.sub(r"\s+", " ", field_match.group(1).strip().strip("*")).strip().lower()
            value = field_match.group(2).strip()
            if value and not value.startswith("#"):
                fields[key] = value
        fields["attempt_id"] = f"S-{number:03d}"
        attempts[fields["attempt_id"]] = fields
    return attempts


def _stage(attempt: dict[str, str]) -> str:
    return attempt.get("search stage", "").strip().lower()


def _stage_is_formal(attempt: dict[str, str]) -> bool:
    return _stage(attempt) in FORMAL_STAGES


def _stage_is_broad(attempt: dict[str, str]) -> bool:
    return _stage(attempt) in BROAD_STAGES


def _planned_pairs(formal_search_plan: dict[str, Any]) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for item in _as_list(formal_search_plan.get("issue_search_plan")):
        if not isinstance(item, dict):
            continue
        area = _text(item.get("issue_area"))
        subissue = _text(item.get("subissue"))
        if area and subissue:
            pairs.add((area, subissue))
    return pairs


def _planned_instructions(formal_search_plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    instructions: dict[str, dict[str, Any]] = {}
    for item in _as_list(formal_search_plan.get("issue_search_plan")):
        if not isinstance(item, dict):
            continue
        area = _text(item.get("issue_area"))
        subissue = _text(item.get("subissue"))
        if not area or not subissue:
            continue
        for instruction in _as_list(item.get("search_instructions")):
            if not isinstance(instruction, dict):
                continue
            instruction_id = _text(instruction.get("instruction_id"))
            if instruction_id:
                instructions[instruction_id] = {
                    "issue_area": area,
                    "subissue": subissue,
                    "priority": _text(item.get("priority")).lower(),
                    "execution_expectation": _text(item.get("execution_expectation")).lower(),
                    "minimum_actual_searches": item.get("minimum_actual_searches") if isinstance(item.get("minimum_actual_searches"), int) else 0,
                }
    return instructions


def _validate_attempts(
    *,
    prefix: str,
    result: dict[str, Any],
    attempts: dict[str, dict[str, str]],
    errors: list[str],
    warnings: list[str],
    require_attempt: bool = True,
) -> tuple[bool, bool]:
    formal_seen = False
    broad_seen = False
    result_instruction_ids = {
        _text(item) for item in _as_list(result.get("search_instruction_ids")) if _text(item)
    }

    formal_attempt_ids: list[str] = []
    for raw_item in _as_list(result.get("search_attempt_ids")):
        raw_attempt_id = _text(raw_item)
        if not raw_attempt_id:
            continue
        if FS_RE.fullmatch(raw_attempt_id):
            errors.append(
                f"{prefix}: search_attempt_ids contains {raw_attempt_id}, but FS-xxx is a planned search instruction, "
                f"not an executed search attempt. {ATTEMPT_ID_HINT}"
            )
            continue
        attempt_id = _normalize_attempt_id(raw_attempt_id)
        if attempt_id:
            formal_attempt_ids.append(attempt_id)
    if not formal_attempt_ids and require_attempt:
        errors.append(
            f"{prefix}: search_attempt_ids must include at least 1 real formal/latest/peer S-xxx search attempt. {ATTEMPT_ID_HINT}"
        )

    for attempt_id in formal_attempt_ids:
        attempt = attempts.get(attempt_id)
        if not attempt:
            errors.append(f"{prefix}: search_attempt_id {attempt_id} not found in search_log.md")
            continue
        if not _stage_is_formal(attempt):
            errors.append(
                f"{prefix}: search_attempt_id {attempt_id} has stage '{attempt.get('search stage', '')}', "
                "expected formal_research, formal_research_execution, latest_check, or peer_check. "
                "Do not remove broad_discovery IDs to pass validation; add a real formal search and keep broad searches in source_discovery_attempt_ids."
            )
            continue
        attempt_instruction_ids = set(re.findall(r"FS-\d{3}", attempt.get("search instruction ids", "")))
        if not attempt_instruction_ids:
            errors.append(
                f"{prefix}: search_attempt_id {attempt_id} is formal but search_log.md has no Search Instruction IDs"
            )
        elif result_instruction_ids and attempt_instruction_ids.isdisjoint(result_instruction_ids):
            errors.append(
                f"{prefix}: search_attempt_id {attempt_id} Search Instruction IDs "
                f"{sorted(attempt_instruction_ids)} do not match result search_instruction_ids {sorted(result_instruction_ids)}"
            )
        formal_seen = True

    discovery_attempt_ids = [_normalize_attempt_id(item) for item in _as_list(result.get("source_discovery_attempt_ids"))]
    discovery_attempt_ids = [item for item in discovery_attempt_ids if item]
    for attempt_id in discovery_attempt_ids:
        attempt = attempts.get(attempt_id)
        if not attempt:
            errors.append(f"{prefix}: source_discovery_attempt_id {attempt_id} not found in search_log.md")
            continue
        if _stage_is_broad(attempt):
            broad_seen = True
        elif not _stage_is_formal(attempt):
            warnings.append(
                f"{prefix}: source_discovery_attempt_id {attempt_id} has non-standard stage '{attempt.get('search stage', '')}'"
            )
    return formal_seen, broad_seen


def _formal_attempt_ids(attempts: dict[str, dict[str, str]]) -> set[str]:
    output: set[str] = set()
    for attempt_id, attempt in attempts.items():
        if _stage_is_formal(attempt):
            output.add(attempt_id)
    return output


def validate(
    report: dict[str, Any],
    formal_search_plan: dict[str, Any],
    search_log_path: Path,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if report.get("schema_version") != "formal_research_execution_report_v1":
        errors.append(f"schema_version must be formal_research_execution_report_v1. {REPORT_STRUCTURE_HINT}")
    for field in ("formal_research_completed_at", "search_log"):
        if not _non_empty_text(report.get(field)):
            errors.append(f"{field} is required. {REPORT_STRUCTURE_HINT}")

    try:
        attempts = parse_search_attempts(search_log_path)
    except Exception as exc:
        errors.append(f"cannot parse search_log.md: {exc}")
        attempts = {}
    if not attempts:
        errors.append("search_log.md has no parseable Search attempts")

    results = report.get("issue_results")
    if not isinstance(results, list) or not results:
        errors.append(f"issue_results must be a non-empty array. {REPORT_STRUCTURE_HINT}")
        results = []

    planned_pairs = _planned_pairs(formal_search_plan) if isinstance(formal_search_plan, dict) else set()
    planned_instructions = _planned_instructions(formal_search_plan) if isinstance(formal_search_plan, dict) else {}
    actual_formal_attempt_ids = _formal_attempt_ids(attempts)
    seen_pairs: set[tuple[str, str]] = set()
    seen_result_ids: set[str] = set()
    seen_instruction_ids: set[str] = set()
    formal_attempt_referenced = False
    status_counts: dict[str, int] = {}
    computed_fs_status: dict[str, dict[str, Any]] = {}

    for idx, result in enumerate(results, start=1):
        if not isinstance(result, dict):
            errors.append(f"issue_results[{idx}] must be an object")
            continue

        result_id = _text(result.get("result_id"))
        prefix = result_id or f"issue_results[{idx}]"
        if not result_id:
            errors.append(f"{prefix}: result_id is required. Use FR-001, FR-002, etc. {REPORT_STRUCTURE_HINT}")
        elif not RESULT_ID_RE.match(result_id):
            errors.append(f"{prefix}: result_id must follow FR-001 format")
        elif result_id in seen_result_ids:
            errors.append(f"{prefix}: duplicate result_id")
        else:
            seen_result_ids.add(result_id)

        issue_area = _text(result.get("issue_area"))
        subissue = _text(result.get("subissue"))
        if not is_valid_issue_pair(issue_area, subissue):
            errors.append(
                f"{prefix}: invalid issue_area/subissue pair '{issue_area}/{subissue}'. "
                "Do not choose taxonomy here; copy issue_area/subissue from the formal_search_plan item "
                "associated with this result's FS-xxx instruction."
            )
        else:
            seen_pairs.add((issue_area, subissue))

        for field in ("research_question", "findings_summary", "research_pack_handling"):
            if not _non_empty_text(result.get(field)):
                errors.append(f"{prefix}: {field} is required")

        status = _text(result.get("status"))
        if status:
            status_counts[status] = status_counts.get(status, 0) + 1
        if status not in VALID_RESULT_STATUS:
            errors.append(f"{prefix}: status must be one of {sorted(VALID_RESULT_STATUS)}")

        terminal_status = _text(result.get("terminal_status"))
        if terminal_status not in VALID_TERMINAL_STATUSES:
            errors.append(f"{prefix}: terminal_status must be one of {sorted(VALID_TERMINAL_STATUSES)}")
        downstream_permission = _text(result.get("downstream_permission"))
        if downstream_permission not in VALID_DOWNSTREAM_PERMISSIONS:
            errors.append(f"{prefix}: downstream_permission must be one of {sorted(VALID_DOWNSTREAM_PERMISSIONS)}")
        if terminal_status in NO_ATTEMPT_TERMINAL_STATUSES and downstream_permission not in {"research_backlog_only", "not_allowed"}:
            errors.append(f"{prefix}: terminal_status={terminal_status} must use downstream_permission=research_backlog_only or not_allowed")
        actual_search_attempt_count = result.get("actual_search_attempt_count")
        if not isinstance(actual_search_attempt_count, int) or actual_search_attempt_count < 0:
            errors.append(f"{prefix}: actual_search_attempt_count must be a non-negative integer")
            actual_search_attempt_count = len(_as_list(result.get("search_attempt_ids")))
        minimum_actual_searches = result.get("minimum_actual_searches")
        if not isinstance(minimum_actual_searches, int) or minimum_actual_searches < 0:
            errors.append(f"{prefix}: minimum_actual_searches must be a non-negative integer")
            minimum_actual_searches = 0

        instruction_ids = [_text(item) for item in _as_list(result.get("search_instruction_ids")) if _text(item)]
        if not instruction_ids:
            errors.append(f"{prefix}: search_instruction_ids must reference at least one FS-xxx instruction from formal_search_plan.json")
        for instruction_id in instruction_ids:
            if not FS_RE.fullmatch(instruction_id):
                errors.append(f"{prefix}: invalid search_instruction_id '{instruction_id}'")
                continue
            planned_instruction = planned_instructions.get(instruction_id)
            if not planned_instruction:
                errors.append(
                    f"{prefix}: search_instruction_id {instruction_id} not found in formal_search_plan.json. "
                    "Use only executed FS-xxx instructions that exist in artifacts/formal_search_plan.json."
                )
                continue
            planned_pair = (planned_instruction["issue_area"], planned_instruction["subissue"])
            if planned_pair != (issue_area, subissue):
                errors.append(
                    f"{prefix}: search_instruction_id {instruction_id} belongs to "
                    f"{planned_pair[0]}/{planned_pair[1]}, not {issue_area}/{subissue}. "
                    "Copy issue_area/subissue from the owning formal_search_plan item instead of reclassifying the result."
                )
                continue
            seen_instruction_ids.add(instruction_id)
            expected_min = int(planned_instruction.get("minimum_actual_searches") or 0)
            if minimum_actual_searches != expected_min:
                warnings.append(
                    f"{prefix}: minimum_actual_searches={minimum_actual_searches} differs from formal_search_plan {instruction_id} minimum {expected_min}"
                )
            computed_fs_status[instruction_id] = {
                "result_id": result_id,
                "issue_area": issue_area,
                "subissue": subissue,
                "terminal_status": terminal_status,
                "downstream_permission": downstream_permission,
                "minimum_actual_searches": expected_min,
                "actual_search_attempt_count": actual_search_attempt_count,
                "search_attempt_ids": [_normalize_attempt_id(item) for item in _as_list(result.get("search_attempt_ids")) if _text(item)],
            }

        require_attempt = terminal_status not in NO_ATTEMPT_TERMINAL_STATUSES
        has_formal_attempt, _ = _validate_attempts(
            prefix=prefix,
            result=result,
            attempts=attempts,
            errors=errors,
            warnings=warnings,
            require_attempt=require_attempt,
        )
        formal_attempt_referenced = formal_attempt_referenced or has_formal_attempt
        normalized_attempt_ids = [_normalize_attempt_id(item) for item in _as_list(result.get("search_attempt_ids")) if _text(item)]
        if actual_search_attempt_count != len(normalized_attempt_ids):
            errors.append(
                f"{prefix}: actual_search_attempt_count={actual_search_attempt_count} does not match search_attempt_ids count {len(normalized_attempt_ids)}"
            )
        if terminal_status in NO_ATTEMPT_TERMINAL_STATUSES and normalized_attempt_ids:
            errors.append(f"{prefix}: terminal_status={terminal_status} cannot carry actual S-xxx search_attempt_ids")

        selected_urls = [_text(item) for item in _as_list(result.get("selected_source_urls")) if _text(item)]
        for url in selected_urls:
            if not FULL_URL_RE.match(url):
                errors.append(f"{prefix}: selected_source_urls contains non-URL value '{url}'")

        source_review_ids = [_text(item) for item in _as_list(result.get("source_review_ids")) if _text(item)]
        evidence_ids = [_text(item) for item in _as_list(result.get("evidence_ids")) if _text(item)]
        metric_ids = [_text(item) for item in _as_list(result.get("metric_ids")) if _text(item)]
        for ev_id in evidence_ids:
            if not EV_RE.fullmatch(ev_id):
                errors.append(f"{prefix}: invalid evidence_id '{ev_id}'")
        for met_id in metric_ids:
            if not MET_RE.fullmatch(met_id):
                errors.append(f"{prefix}: invalid metric_id '{met_id}'")

        if status in EVIDENCE_STATUSES:
            if terminal_status in NO_ATTEMPT_TERMINAL_STATUSES:
                errors.append(f"{prefix}: status={status} cannot be paired with terminal_status={terminal_status}")
            if not selected_urls:
                errors.append(f"{prefix}: status={status} requires selected_source_urls")
            if not source_review_ids:
                errors.append(f"{prefix}: status={status} requires source_review_ids")
            if status == "supported" and not (evidence_ids or metric_ids):
                warnings.append(
                    f"{prefix}: supported issue has no EV/MET IDs yet; research pack must assign them before issue_analysis"
                )

        limitations = [_text(item) for item in _as_list(result.get("limitations")) if _text(item)]
        if status in {"thin", "conflicting", "not_comparable"} and not limitations:
            errors.append(f"{prefix}: status={status} requires limitations")
        if status in UNRESOLVED_STATUSES:
            if not limitations:
                errors.append(f"{prefix}: status={status} requires limitations")
            if evidence_ids or metric_ids:
                errors.append(f"{prefix}: unresolved issue cannot carry EV/MET IDs as usable findings")
            if terminal_status == "executed_with_evidence":
                errors.append(f"{prefix}: unresolved status cannot use terminal_status=executed_with_evidence")
            if "backlog" not in _text(result.get("research_pack_handling")).lower() and "gap" not in _text(result.get("research_pack_handling")).lower():
                warnings.append(f"{prefix}: unresolved issue should be handled as a research gap/backlog in the research pack")

    missing_planned = sorted(planned_pairs - seen_pairs)
    if missing_planned:
        errors.append(
            "formal research execution report missing planned issue/subissue result(s): "
            + ", ".join(f"{area}/{subissue}" for area, subissue in missing_planned[:20])
            + ". Add an FR-xxx result for each executed or unresolved planned issue/subissue. Do not remove taxonomy rows from formal_search_plan.json to reduce coverage."
        )
        if len(missing_planned) > 20:
            errors.append(f"...and {len(missing_planned) - 20} more planned issue/subissue result(s)")

    if not formal_attempt_referenced:
        errors.append("formal research execution report references no formal/latest/peer search attempts")

    if len(results) >= 5:
        unresolved_count = sum(status_counts.get(status, 0) for status in UNRESOLVED_STATUSES)
        if unresolved_count == len(results):
            warnings.append(
                "all formal research execution results are unresolved. This may be legitimate, but verify this is not a batch downgrade to pass validation; normally rerun or broaden formal searches before moving to research_pack/deck_blueprint."
            )
        elif unresolved_count / len(results) >= 0.8:
            warnings.append(
                "80%+ of formal research execution results are unresolved. Treat this as a research-coverage problem, not a JSON-format repair; continue targeted research or keep downstream claims explicitly caveated."
            )

    missing_instructions = sorted(set(planned_instructions) - seen_instruction_ids)
    if missing_instructions:
        errors.append(
            "formal research execution report did not account for planned search instruction(s): "
            + ", ".join(missing_instructions[:20])
            + ". Add FR rows with terminal_status=executed_with_evidence/executed_no_usable_source/not_executed/not_material/accounting_only. "
            + "Do not create fake S-xxx IDs for unexecuted rows and do not delete planned taxonomy coverage."
        )
        if len(missing_instructions) > 20:
            errors.append(f"...and {len(missing_instructions) - 20} more unaccounted planned search instruction(s)")

    coverage = report.get("coverage_summary")
    if not isinstance(coverage, dict):
        errors.append("coverage_summary is missing; include planned-vs-actual FS/S accounting before downstream research pack")
    else:
        expected_numbers = {
            "planned_fs_rows": len(planned_instructions),
            "actual_search_attempts": len(actual_formal_attempt_ids),
            "fs_rows_accounted": len(computed_fs_status),
            "fs_rows_executed_with_evidence": sum(1 for row in computed_fs_status.values() if row.get("terminal_status") == "executed_with_evidence"),
            "fs_rows_executed_without_evidence": sum(1 for row in computed_fs_status.values() if row.get("terminal_status") == "executed_no_usable_source"),
            "fs_rows_not_executed": sum(1 for row in computed_fs_status.values() if row.get("terminal_status") in {"not_executed", "accounting_only", "not_material"}),
        }
        for key, expected in expected_numbers.items():
            observed = coverage.get(key)
            if observed != expected:
                errors.append(f"coverage_summary.{key} must be {expected}, observed {observed}")
        below_minimum = sorted(
            fs_id
            for fs_id, row in computed_fs_status.items()
            if int(row.get("actual_search_attempt_count") or 0) < int(row.get("minimum_actual_searches") or 0)
        )
        reported_below_minimum = sorted(_text(item) for item in _as_list(coverage.get("high_priority_rows_below_minimum")) if _text(item))
        if reported_below_minimum != below_minimum:
            errors.append(
                "coverage_summary.high_priority_rows_below_minimum must match computed below-minimum FS rows: "
                + ", ".join(below_minimum)
            )
        covered_areas = set(_as_list(coverage.get("covered_issue_areas")))
        known_areas = set(ISSUE_TOPICS_BY_AREA)
        unknown = sorted(str(item) for item in covered_areas if item not in known_areas)
        if unknown:
            errors.append("coverage_summary.covered_issue_areas contains unknown issue area(s): " + ", ".join(unknown))

    fs_rows = report.get("fs_row_execution_status")
    if not isinstance(fs_rows, list) or not fs_rows:
        errors.append("fs_row_execution_status must be a non-empty array accounting for every planned FS-xxx row")
    else:
        rows_by_fs: dict[str, dict[str, Any]] = {}
        for idx, row in enumerate(fs_rows, start=1):
            if not isinstance(row, dict):
                errors.append(f"fs_row_execution_status[{idx}] must be an object")
                continue
            fs_id = _text(row.get("fs_id"))
            prefix = f"fs_row_execution_status[{idx}]"
            if not FS_RE.fullmatch(fs_id):
                errors.append(f"{prefix}: fs_id must follow FS-001 format")
                continue
            if fs_id in rows_by_fs:
                errors.append(f"{prefix}: duplicate fs_id {fs_id}")
            rows_by_fs[fs_id] = row
            if fs_id not in planned_instructions:
                errors.append(f"{prefix}: fs_id {fs_id} not found in formal_search_plan.json")
            terminal_status = _text(row.get("terminal_status"))
            if terminal_status not in VALID_TERMINAL_STATUSES:
                errors.append(f"{prefix}: terminal_status must be one of {sorted(VALID_TERMINAL_STATUSES)}")
            downstream_permission = _text(row.get("downstream_permission"))
            if downstream_permission not in VALID_DOWNSTREAM_PERMISSIONS:
                errors.append(f"{prefix}: downstream_permission must be one of {sorted(VALID_DOWNSTREAM_PERMISSIONS)}")
            actual_ids = [_normalize_attempt_id(item) for item in _as_list(row.get("actual_search_attempt_ids")) if _text(item)]
            if row.get("actual_search_attempt_count") != len(actual_ids):
                errors.append(f"{prefix}: actual_search_attempt_count does not match actual_search_attempt_ids count")
            for attempt_id in actual_ids:
                attempt = attempts.get(attempt_id)
                if not attempt:
                    errors.append(f"{prefix}: actual_search_attempt_id {attempt_id} not found in search_log.md")
                elif not _stage_is_formal(attempt):
                    errors.append(f"{prefix}: actual_search_attempt_id {attempt_id} is not a formal/latest/peer search")
            if terminal_status in NO_ATTEMPT_TERMINAL_STATUSES and actual_ids:
                errors.append(f"{prefix}: terminal_status={terminal_status} cannot carry actual_search_attempt_ids")
        missing_fs_rows = sorted(set(planned_instructions) - set(rows_by_fs))
        if missing_fs_rows:
            errors.append(
                "fs_row_execution_status missing planned FS row(s): "
                + ", ".join(missing_fs_rows[:20])
            )
        mismatch_fs_rows = sorted(
            fs_id
            for fs_id, computed in computed_fs_status.items()
            if fs_id in rows_by_fs
            and (
                _text(rows_by_fs[fs_id].get("terminal_status")) != computed.get("terminal_status")
                or _text(rows_by_fs[fs_id].get("downstream_permission")) != computed.get("downstream_permission")
                or [_normalize_attempt_id(item) for item in _as_list(rows_by_fs[fs_id].get("actual_search_attempt_ids")) if _text(item)] != computed.get("search_attempt_ids")
            )
        )
        if mismatch_fs_rows:
            errors.append(
                "fs_row_execution_status differs from issue_results for FS row(s): "
                + ", ".join(mismatch_fs_rows[:20])
            )

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, help="Path to formal_research_execution_report.json")
    parser.add_argument("--formal-search-plan", required=True, help="Path to formal_search_plan.json")
    parser.add_argument("--search-log", required=True, help="Path to search_log.md")
    parser.add_argument("--output", help="Optional JSON report path")
    args = parser.parse_args()

    try:
        report = load_json_file(Path(args.report))
        plan = load_json_file(Path(args.formal_search_plan))
    except Exception as exc:
        result = {
            "is_valid": False,
            "error_count": 1,
            "warning_count": 0,
            "errors": [str(exc)],
            "warnings": [],
            "report": args.report,
        }
    else:
        errors, warnings = validate(report, plan, Path(args.search_log))
        result = {
            "is_valid": not errors,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "errors": errors,
            "warnings": warnings,
            "report": args.report,
            "formal_search_plan": args.formal_search_plan,
            "search_log": args.search_log,
        }

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["is_valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
