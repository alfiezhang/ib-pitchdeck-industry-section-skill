#!/usr/bin/env python3
"""Compatibility status helper for the industry boundary loop.

The primary boundary decision is now authored by the Scoping/QC roles in
industry_boundary_qc.json. This helper remains as a machine-readable telemetry
step for older workflow/tests: it reports whether the scope draft is missing,
needs boundary validation, conflicts with later evidence, or is ready.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from json_utils import load_json_file


SCHEMA_VERSION = "boundary_loop_status_v1"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        payload = load_json_file(path)
        return payload if isinstance(payload, dict) else {}
    except Exception as exc:
        return {"_load_error": str(exc)}


def _walk_text(payload: Any) -> list[str]:
    if isinstance(payload, dict):
        values: list[str] = []
        for value in payload.values():
            values.extend(_walk_text(value))
        return values
    if isinstance(payload, list):
        values: list[str] = []
        for item in payload:
            values.extend(_walk_text(item))
        return values
    if isinstance(payload, (str, int, float, bool)):
        return [str(payload)]
    return []


def _scope_required_errors(scope_pack: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    scope_summary = _as_dict(scope_pack.get("scope_summary"))
    classification = _as_dict(scope_pack.get("scope_classification"))
    draft = _as_dict(scope_pack.get("llm_definition_draft"))
    if not _text(scope_summary.get("working_market")):
        errors.append("scope_summary.working_market is required")
    if not _text(scope_summary.get("parent_market")):
        errors.append("scope_summary.parent_market is required")
    if not _text(scope_summary.get("broader_market")):
        errors.append("scope_summary.broader_market is required")
    if not _as_list(classification.get("core")):
        errors.append("scope_classification.core is required")
    if not _as_list(classification.get("adjacent")):
        errors.append("scope_classification.adjacent is required")
    if not _text(draft.get("working_market_draft")):
        errors.append("llm_definition_draft.working_market_draft is required")
    if len(_as_list(draft.get("scoping_search_queries"))) < 2:
        errors.append("llm_definition_draft.scoping_search_queries must contain at least 2 items")
    if not _as_list(scope_pack.get("formal_research_seed_questions")):
        errors.append("formal_research_seed_questions are required")
    return errors


def _validation_needed(scope_pack: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    scope_summary = _as_dict(scope_pack.get("scope_summary"))
    classification = _as_dict(scope_pack.get("scope_classification"))
    working = _text(scope_summary.get("working_market"))
    parent = _text(scope_summary.get("parent_market"))
    broader = _text(scope_summary.get("broader_market"))
    if working and parent and working == parent:
        warnings.append("working_market and parent_market are identical; scope may be too broad")
    if working and broader and working == broader:
        warnings.append("working_market and broader_market are identical; narrower definitions needed")
    if not _as_list(scope_summary.get("adjacent_markets")):
        warnings.append("adjacent_markets is empty; adjacent categories should be documented")
    if not _as_list(classification.get("excluded")):
        warnings.append("excluded scope is empty; explicit exclusions are needed")
    if not _as_list(scope_pack.get("ambiguous_boundaries")) and not _text(scope_pack.get("scope_confidence_rationale")):
        warnings.append("ambiguous boundaries are not listed; provide scope confidence rationale if intentionally empty")
    return warnings


def _conflict_signals(research_evidence_db: dict[str, Any], boundary_text: str | None) -> list[str]:
    markers = ("conflict", "inconsistent", "not comparable", "不可比", "不一致", "冲突", "scope mismatch", "definition conflict")
    conflicts: list[str] = []
    for row in _as_list(research_evidence_db.get("metric_reconciliation")):
        if not isinstance(row, dict):
            continue
        combined = " ".join(_walk_text(row)).lower()
        if any(marker in combined for marker in markers):
            conflicts.append(f"metric_reconciliation conflict: {_text(row.get('metric_id') or row.get('metric_name') or row.get('resolution'))}")
            break
    if boundary_text and any(marker in boundary_text.lower() for marker in markers):
        conflicts.append("boundary search results include conflict signals requiring Scoping/QC review")
    return conflicts


def _repair_actions(status: str) -> list[dict[str, str]]:
    owner = "industry-scoping" if status != "boundary_conflict_found" else "industry-scoping"
    return [
        {
            "issue_id": "BL-001",
            "owner": owner,
            "repair_owner": owner,
            "action": "Repair industry scope/boundary artifacts, then rerun boundary_loop.py.",
            "rerun_command": (
                "python3 scripts/boundary_loop.py --scope-pack artifacts/industry_scope_pack.json "
                "--material-extracts artifacts/material_extracts.json "
                "--research-evidence-db artifacts/research_evidence_db.json "
                "--boundary-search-results artifacts/search_log.md "
                "--output artifacts/boundary_loop_status.json"
            ),
        }
    ]


def _status_payload(status: str, errors: list[str], warnings: list[str], repair_actions: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "boundary_loop_status": status,
        "is_valid": status == "boundary_ready" and not errors,
        "generated_at": _now_iso(),
        "errors": errors,
        "warnings": warnings,
        "repair_actions": repair_actions,
    }


def run_boundary_loop(
    scope_pack: Path | None = None,
    material_extracts: Path | None = None,
    research_evidence_db: Path | None = None,
    boundary_search_results: Path | None = None,
) -> dict[str, Any]:
    del material_extracts  # Material extraction is assessed by dedicated Material/Knowledge checks.
    scope_payload = _load_json(scope_pack)
    evidence_payload = _load_json(research_evidence_db)
    boundary_text = None
    if boundary_search_results:
        try:
            boundary_text = boundary_search_results.read_text(encoding="utf-8")
        except Exception:
            boundary_text = None

    required_errors = _scope_required_errors(scope_payload)
    if required_errors or not scope_payload:
        return _status_payload("boundary_draft_missing", required_errors or ["industry_scope_pack.json missing or unreadable"], [], _repair_actions("boundary_draft_missing"))

    conflicts = _conflict_signals(evidence_payload, boundary_text)
    if conflicts:
        return _status_payload("boundary_conflict_found", ["Boundary evidence conflict detected."] + conflicts, [], _repair_actions("boundary_conflict_found"))

    warnings = _validation_needed(scope_payload)
    if warnings:
        return _status_payload("boundary_validation_needed", [], warnings, _repair_actions("boundary_validation_needed"))

    return _status_payload("boundary_ready", [], [], [])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope-pack")
    parser.add_argument("--material-extracts")
    parser.add_argument("--research-evidence-db")
    parser.add_argument("--boundary-search-results")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = run_boundary_loop(
        scope_pack=Path(args.scope_pack) if args.scope_pack else None,
        material_extracts=Path(args.material_extracts) if args.material_extracts else None,
        research_evidence_db=Path(args.research_evidence_db) if args.research_evidence_db else None,
        boundary_search_results=Path(args.boundary_search_results) if args.boundary_search_results else None,
    )
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("is_valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
