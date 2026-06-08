#!/usr/bin/env python3
"""Validate formal research execution against the industry issue taxonomy.

The search plan is intentionally lightweight. This validator is the formal
research gate: it checks that the agent actually ran issue/subissue research,
reviewed sources, recorded limitations, and did not promote unresolved gaps as
usable research findings.
"""

from __future__ import annotations

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
REPORT_STRUCTURE_HINT = (
    "Start from templates/formal_research_execution_report.skeleton.json. "
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


def _planned_instructions(formal_search_plan: dict[str, Any]) -> dict[str, tuple[str, str]]:
    instructions: dict[str, tuple[str, str]] = {}
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
                instructions[instruction_id] = (area, subissue)
    return instructions


def _validate_attempts(
    *,
    prefix: str,
    result: dict[str, Any],
    attempts: dict[str, dict[str, str]],
    errors: list[str],
    warnings: list[str],
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
    if not formal_attempt_ids:
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
    seen_pairs: set[tuple[str, str]] = set()
    seen_result_ids: set[str] = set()
    seen_instruction_ids: set[str] = set()
    formal_attempt_referenced = False

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
        if status not in VALID_RESULT_STATUS:
            errors.append(f"{prefix}: status must be one of {sorted(VALID_RESULT_STATUS)}")

        instruction_ids = [_text(item) for item in _as_list(result.get("search_instruction_ids")) if _text(item)]
        if not instruction_ids:
            errors.append(f"{prefix}: search_instruction_ids must reference at least one FS-xxx instruction from formal_search_plan.json")
        for instruction_id in instruction_ids:
            if not FS_RE.fullmatch(instruction_id):
                errors.append(f"{prefix}: invalid search_instruction_id '{instruction_id}'")
                continue
            planned_pair = planned_instructions.get(instruction_id)
            if not planned_pair:
                errors.append(
                    f"{prefix}: search_instruction_id {instruction_id} not found in formal_search_plan.json. "
                    "Use only executed FS-xxx instructions that exist in artifacts/formal_search_plan.json."
                )
                continue
            if planned_pair != (issue_area, subissue):
                errors.append(
                    f"{prefix}: search_instruction_id {instruction_id} belongs to "
                    f"{planned_pair[0]}/{planned_pair[1]}, not {issue_area}/{subissue}. "
                    "Copy issue_area/subissue from the owning formal_search_plan item instead of reclassifying the result."
                )
                continue
            seen_instruction_ids.add(instruction_id)

        has_formal_attempt, _ = _validate_attempts(
            prefix=prefix,
            result=result,
            attempts=attempts,
            errors=errors,
            warnings=warnings,
        )
        formal_attempt_referenced = formal_attempt_referenced or has_formal_attempt

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
            if "backlog" not in _text(result.get("research_pack_handling")).lower() and "gap" not in _text(result.get("research_pack_handling")).lower():
                warnings.append(f"{prefix}: unresolved issue should be handled as a research gap/backlog in the research pack")

    missing_planned = sorted(planned_pairs - seen_pairs)
    if missing_planned:
        errors.append(
            "formal research execution report missing planned issue/subissue result(s): "
            + ", ".join(f"{area}/{subissue}" for area, subissue in missing_planned[:20])
            + ". Add an FR-xxx result for each executed or unresolved planned issue/subissue, or remove unexecuted FS-xxx from the plan before validation."
        )
        if len(missing_planned) > 20:
            errors.append(f"...and {len(missing_planned) - 20} more planned issue/subissue result(s)")

    if not formal_attempt_referenced:
        errors.append("formal research execution report references no formal/latest/peer search attempts")

    missing_instructions = sorted(set(planned_instructions) - seen_instruction_ids)
    if missing_instructions:
        errors.append(
            "formal research execution report did not execute planned search instruction(s): "
            + ", ".join(missing_instructions[:20])
            + ". Run real formal searches for these FS-xxx instructions, append S-xxx entries to search_log.md, "
            + "then reference those S-xxx IDs in search_attempt_ids; or remove truly unexecuted instructions from formal_search_plan.json before validation."
        )
        if len(missing_instructions) > 20:
            errors.append(f"...and {len(missing_instructions) - 20} more planned search instruction(s)")

    coverage = report.get("coverage_summary")
    if not isinstance(coverage, dict):
        warnings.append("coverage_summary is missing; include issue areas covered, gaps, and unavailable facts")
    else:
        covered_areas = set(_as_list(coverage.get("covered_issue_areas")))
        known_areas = set(ISSUE_TOPICS_BY_AREA)
        unknown = sorted(str(item) for item in covered_areas if item not in known_areas)
        if unknown:
            errors.append("coverage_summary.covered_issue_areas contains unknown issue area(s): " + ", ".join(unknown))

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
