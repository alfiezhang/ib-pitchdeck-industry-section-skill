#!/usr/bin/env python3
"""Promote unresolved research requests into the formal search plan."""

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
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts"
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from json_utils import load_json_file


FS_RE = re.compile(r"^FS-(\d{3})$")


ALLOWED_DOWNSTREAM_PERMISSIONS = {
    "headline_disallowed",
    "caveat_or_diligence_question_only",
    "context_only",
    "body_only",
    "disallowed_as_claim",
}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def as_text(value: Any) -> str:
    return str(value or "").strip()


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def parse_formal_search_plan(path: Path) -> dict[str, Any]:
    payload = load_json_file(path)
    if not isinstance(payload, dict):
        raise ValueError(f"formal-search plan is not an object: {path}")
    return payload


def parse_requests(path: Path) -> list[dict[str, Any]]:
    payload = load_json_file(path)
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [item for item in as_list(payload.get("requests")) if isinstance(item, dict)]
    return []


def next_fs_id(plan: dict[str, Any]) -> str:
    max_fs = 0
    for item in as_list(plan.get("issue_search_plan")):
        if not isinstance(item, dict):
            continue
        for instruction in as_list(item.get("search_instructions")):
            instruction_id = as_text(instruction.get("instruction_id"))
            match = FS_RE.fullmatch(instruction_id)
            if match:
                max_fs = max(max_fs, int(match.group(1)))
    return f"FS-{max_fs + 1:03d}"


def _next_fs_seq(plan: dict[str, Any]) -> int:
    return int(next_fs_id(plan).split("-")[1])


def _source_hint(required_source_type: str) -> str:
    source_type = as_text(required_source_type).lower()
    if source_type == "repository_retrieval":
        return "industry report or repository source"
    if source_type == "user_curated_industry_report":
        return "curated industry report or filing list"
    if source_type == "manual_url_ingestion":
        return "manual URL or user-curated source list"
    return "public search with verified source and date"


def _fallback_issue_area(request: dict[str, Any]) -> tuple[str, str]:
    issue_area = as_text(
        request.get("origin_issue_area")
        or request.get("issue_area")
        or request.get("issue_analysis_area")
        or "pitch_relevance_target_context"
    )
    issue_subissue = as_text(
        request.get("origin_issue_subissue")
        or request.get("issue_subissue")
        or request.get("issue_analysis_subissue")
        or "evidence_limits"
    )
    return issue_area, issue_subissue


def _execution_expectation(request: dict[str, Any]) -> tuple[str, int, str]:
    minimum = _as_int(request.get("minimum_actual_searches"), 1)
    if minimum < 0:
        minimum = 1
    if minimum >= 2:
        return (
            "deep_search",
            minimum,
            "Follow-up request row for unresolved research request; use at least two source channels when feasible.",
        )
    if minimum == 0:
        return (
            "accounting_only",
            minimum,
            "Unresolved request currently has no required search quota; keep coverage row pending until a real execution plan is approved.",
        )
    return (
        "light_search",
        minimum,
        "Follow-up request row for unresolved research request.",
    )


def _build_search_query(request: dict[str, Any], issue_area: str, issue_subissue: str) -> str:
    question = as_text(request.get("research_question"))
    if question:
        return f"LLM_REWRITE_REQUIRED: rewrite research request into executable source-specific query: {question}"
    return f"LLM_REWRITE_REQUIRED: write executable source-specific query for {issue_area}/{issue_subissue}"


def _build_plan_row(
    request: dict[str, Any],
    fs_id: str,
    issue_area: str,
    issue_subissue: str,
) -> dict[str, Any]:
    execution_expectation, minimum_actual_searches, rationale = _execution_expectation(request)
    required_source_type = as_text(request.get("required_source_type") or "public_search")
    request_id = as_text(request.get("request_id") or request.get("research_request_id"))
    hypothesis_id = as_text(request.get("hypothesis_id"))
    query = _build_search_query(request, issue_area, issue_subissue)

    return {
        "issue_area": issue_area,
        "subissue": issue_subissue,
        "priority": "medium",
        "execution_expectation": execution_expectation,
        "minimum_actual_searches": minimum_actual_searches,
        "coverage_required": True,
        "terminal_status": "pending",
        "execution_rationale": rationale,
        "research_question": query,
        "request_id": request_id,
        "origin_issue_id": as_text(request.get("origin_issue_id") or request.get("issue_analysis_id")),
        "hypothesis_id": hypothesis_id,
        "downstream_permission_if_unresolved": as_text(
            request.get("downstream_permission_if_unresolved")
            or request.get("downstream_permission_until_resolved")
            or "caveat_or_diligence_question_only"
        ),
        "required_source_type": required_source_type,
        "search_instructions": [
            {
                "instruction_id": fs_id,
                "query": query,
                "query_variants": [
                    query,
                    f"LLM_REWRITE_REQUIRED: authority/source-specific query for {issue_area}/{issue_subissue}",
                    f"LLM_REWRITE_REQUIRED: reconciliation query for {issue_area}/{issue_subissue}",
                ],
                "purpose": "Promote unresolved hypothesis to formal execution queue.",
                "search_stage": "formal_research_execution",
                "source_hint": _source_hint(required_source_type),
                "request_id": request_id,
                "hypothesis_id": hypothesis_id,
            }
        ],
        "promotion_metadata": {
            "promoted_from_research_request_queue": True,
            "promoted_by": "scripts/reasoning/promote_research_requests.py",
            "promoted_at": datetime.now(timezone.utc).isoformat(),
            "required_source_type": required_source_type,
            "origin_request": as_text(request.get("origin") or "reasoning"),
        },
    }


def _already_promoted(plan: dict[str, Any], request_id: str, hypothesis_id: str) -> bool:
    if not (request_id or hypothesis_id):
        return False

    for item in as_list(plan.get("issue_search_plan")):
        if not isinstance(item, dict):
            continue
        if request_id and as_text(item.get("request_id")) == request_id:
            return True
        if hypothesis_id and as_text(item.get("hypothesis_id")) == hypothesis_id:
            return True

        metadata = item.get("promotion_metadata")
        if isinstance(metadata, dict):
            if request_id and as_text(metadata.get("request_id")) == request_id:
                return True
            if hypothesis_id and as_text(metadata.get("hypothesis_id")) == hypothesis_id:
                return True

        for instr in as_list(item.get("search_instructions")):
            if not isinstance(instr, dict):
                continue
            if request_id and as_text(instr.get("request_id")) == request_id:
                return True
            if hypothesis_id and as_text(instr.get("hypothesis_id")) == hypothesis_id:
                return True
    return False


def _normalize_queue_path(path: Path) -> Path:
    return path


def _canonical_downstream_permission(value: str) -> str:
    candidate = as_text(value).lower()
    if not candidate:
        return "caveat_or_diligence_question_only"
    if candidate == "headline_allowed":
        return "headline_allowed"
    if candidate in ALLOWED_DOWNSTREAM_PERMISSIONS:
        return candidate
    return "caveat_or_diligence_question_only"


def promote_requests(
    request_queue_path: Path,
    formal_search_plan_path: Path,
    formal_research_execution_report: Path | None = None,
    incremental_output_path: Path | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    plan = parse_formal_search_plan(formal_search_plan_path)
    if formal_research_execution_report and formal_research_execution_report.exists():
        # keep hook for future request->search lineage validation
        _ = load_json_file(formal_research_execution_report)

    issue_search_plan = as_list(plan.get("issue_search_plan"))
    if not issue_search_plan:
        issue_search_plan = []
        plan["issue_search_plan"] = issue_search_plan

    requests = parse_requests(request_queue_path)
    if not requests:
        return plan, [], [
            {
                "request_id": "",
                "reason": "research request queue missing or empty",
            }
        ]

    next_fs = _next_fs_seq(plan)
    existing_request_ids: set[str] = set()
    existing_hypothesis_ids: set[str] = set()
    for item in as_list(plan.get("issue_search_plan")):
        if not isinstance(item, dict):
            continue
        existing_request_ids.add(as_text(item.get("request_id")))
        existing_hypothesis_ids.add(as_text(item.get("hypothesis_id")))
        metadata = item.get("promotion_metadata")
        if isinstance(metadata, dict):
            existing_request_ids.add(as_text(metadata.get("request_id")))
            existing_hypothesis_ids.add(as_text(metadata.get("hypothesis_id")))
        for instr in as_list(item.get("search_instructions")):
            if not isinstance(instr, dict):
                continue
            existing_request_ids.add(as_text(instr.get("request_id")))
            existing_hypothesis_ids.add(as_text(instr.get("hypothesis_id")))

    added: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    seen_incoming_request_ids: set[str] = set()

    for request in requests:
        request_id = as_text(request.get("request_id") or request.get("research_request_id"))
        hypothesis_id = as_text(request.get("hypothesis_id"))

        if not request_id:
            skipped.append({"request_id": "", "reason": "missing request_id"})
            continue
        if request_id in seen_incoming_request_ids:
            skipped.append({"request_id": request_id, "reason": "duplicate request_id in queue"})
            continue
        seen_incoming_request_ids.add(request_id)

        if not hypothesis_id:
            skipped.append({"request_id": request_id, "reason": "missing hypothesis_id"})
            continue

        research_question = as_text(request.get("research_question"))
        if not research_question:
            skipped.append({"request_id": request_id, "reason": "missing research_question"})
            continue

        if _as_int(request.get("minimum_actual_searches"), 1) < 0:
            skipped.append({"request_id": request_id, "reason": "minimum_actual_searches must be >= 0"})
            continue

        downstream_permission = _canonical_downstream_permission(
            as_text(request.get("downstream_permission_if_unresolved") or request.get("downstream_permission_until_resolved"))
        )
        if downstream_permission == "headline_allowed":
            skipped.append(
                {
                    "request_id": request_id,
                    "reason": "unresolved request cannot be headline_allowed",
                }
            )
            continue

        if request_id in existing_request_ids or hypothesis_id in existing_hypothesis_ids:
            skipped.append({"request_id": request_id, "reason": "already_promoted"})
            continue

        issue_area, issue_subissue = _fallback_issue_area(request)
        fs_id = f"FS-{next_fs:03d}"
        next_fs += 1
        row = _build_plan_row(request, fs_id, issue_area, issue_subissue)
        row["downstream_permission_if_unresolved"] = downstream_permission
        row["search_instructions"][0]["downstream_permission_if_unresolved"] = downstream_permission

        issue_search_plan.append(row)
        added.append(
            {
                "request_id": request_id,
                "hypothesis_id": hypothesis_id,
                "instruction_id": fs_id,
            }
        )
        existing_request_ids.add(request_id)
        existing_hypothesis_ids.add(hypothesis_id)

    plan["research_request_promotion"] = {
        "schema_version": "research_request_promotion_v1",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "promoted": added,
        "skipped": skipped,
        "applied_from": str(request_queue_path),
        "incremental_output": str(incremental_output_path) if incremental_output_path else "",
    }
    return plan, added, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research-request-queue", required=True)
    parser.add_argument("--formal-search-plan", required=True)
    parser.add_argument("--formal-research-execution-report")
    parser.add_argument("--output", required=True, help="Path to write updated formal_search_plan.json")
    parser.add_argument("--incremental-search-plan", help="Optional path for request-only incremental rows")
    args = parser.parse_args()

    request_queue_path = _normalize_queue_path(Path(args.research_request_queue))
    formal_search_plan_path = Path(args.formal_search_plan)
    execution_report_path = Path(args.formal_research_execution_report) if args.formal_research_execution_report else None
    incremental_path = Path(args.incremental_search_plan) if args.incremental_search_plan else None

    try:
        updated_plan, added, skipped = promote_requests(
            request_queue_path=request_queue_path,
            formal_search_plan_path=formal_search_plan_path,
            formal_research_execution_report=execution_report_path,
            incremental_output_path=incremental_path,
        )
    except Exception as exc:
        result = {
            "is_valid": False,
            "error": str(exc),
            "request_promotions": [],
            "request_count": 0,
            "skipped": [],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(updated_plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    incremental = [row for row in added]
    if incremental_path is not None:
        incremental_rows = [
            {"request_id": row["request_id"], "instruction_id": row["instruction_id"], "hypothesis_id": row.get("hypothesis_id", "")}
            for row in incremental
        ]
        incremental_path.parent.mkdir(parents=True, exist_ok=True)
        incremental_path.write_text(json.dumps(incremental_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    result = {
        "is_valid": True,
        "updated_formal_search_plan": str(output_path),
        "request_promotions": added,
        "request_count": len(added),
        "skipped": skipped,
        "skipped_count": len(skipped),
        "incremental_search_plan": str(incremental_path) if incremental_path else "",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
