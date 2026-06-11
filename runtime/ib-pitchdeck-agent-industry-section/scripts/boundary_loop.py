#!/usr/bin/env python3
"""Run the industry boundary control loop status computation."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from json_utils import load_json_file


LOOP_STATUSES = {
    "boundary_draft_missing",
    "boundary_validation_needed",
    "boundary_conflict_found",
    "boundary_ready",
}
SCHEMA_VERSION = "boundary_loop_status_v1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _extract_paths(scope_pack: dict[str, Any]) -> tuple[str, str, str]:
    scope = _as_dict(scope_pack.get("scope_summary"))
    classification = _as_dict(scope_pack.get("scope_classification"))
    draft = _as_dict(scope_pack.get("llm_definition_draft"))
    return _text(scope.get("working_market")), _text(scope.get("parent_market")), _text(scope.get("broader_market"))


def _walk_text_fields(payload: Any) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            items.extend(_walk_text_fields(value))
    elif isinstance(payload, list):
        for item in payload:
            items.extend(_walk_text_fields(item))
    else:
        if isinstance(payload, (str, int, float, bool)):
            items.append(("", str(payload)))
    return items


def _contains_keywords(value: Any, keywords: tuple[str, ...]) -> bool:
    for _, text_value in _walk_text_fields(value):
        lower_text = text_value.lower()
        if any(keyword in lower_text for keyword in keywords):
            return True
    return False


def _missing_scope_field_errors(scope_pack: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(scope_pack, dict):
        return ["industry_scope_pack must be an object"]
    working, parent, broader = _extract_paths(scope_pack)
    if not working:
        errors.append("scope_summary.working_market is required")
    if not parent:
        errors.append("scope_summary.parent_market is required")
    if not broader:
        errors.append("scope_summary.broader_market is required")
    if not _as_list(scope_pack.get("formal_research_seed_questions")):
        errors.append("formal_research_seed_questions are required to support narrow core definitions")
    if not _as_list(_as_dict(scope_pack.get("scope_classification")).get("core")):
        errors.append("scope_classification.core is required")
    if not _as_list(_as_dict(scope_pack.get("scope_classification")).get("adjacent")):
        errors.append("scope_classification.adjacent is required")
    draft = _as_dict(scope_pack.get("llm_definition_draft"))
    if not _text(draft.get("working_market_draft")):
        errors.append("llm_definition_draft.working_market_draft is required")
    if len(_as_list(draft.get("scoping_search_queries"))) < 2:
        errors.append("llm_definition_draft.scoping_search_queries must contain at least 2 items")
    return errors


def _boundary_validation_needed(scope_pack: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    working, parent, broader = _extract_paths(scope_pack)
    classification = _as_dict(scope_pack.get("scope_classification"))
    if working and parent and working == parent:
        reasons.append("working_market and parent_market are identical; scope may be too broad")
    if working and broader and working == broader:
        reasons.append("working_market and broader_market are identical; narrower definitions needed")

    if not _as_list(classification.get("excluded")):
        reasons.append("excluded scope is empty; explicit exclusions are needed to prevent boundary drift")
    if not _as_list(_as_dict(scope_pack.get("scope_summary")).get("adjacent_markets")):
        reasons.append("adjacent_markets is empty; adjacent categories should be documented")
    if not _as_list(scope_pack.get("ambiguous_boundaries")) and not _text(scope_pack.get("scope_confidence_rationale")):
        reasons.append("ambiguous boundaries are not listed; provide scope confidence rationale if intentionally empty")
    return reasons


def _conflict_signals(
    research_evidence_db: dict[str, Any] | None,
    boundary_search_results: str | None,
) -> list[str]:
    if not isinstance(research_evidence_db, dict):
        return []
    conflict_markers = (
        "conflict",
        "inconsistent",
        "cannot be compared",
        "不可比",
        "不一致",
        "冲突",
        "scope mismatch",
        "definition conflict",
        "cross",
    )
    conflicts: list[str] = []
    for row in _as_list(research_evidence_db.get("metric_reconciliation")):
        if any(
            keyword in str(row.get("conflict_status") or "").lower()
            for keyword in ("conflict", "inconsistent", "disagree", "not comparable")
        ):
            conflicts.append(f"metric_reconciliation conflict: {row.get('metric_id') or row.get('metric_name') or row.get('resolution')}")
            break
    if boundary_search_results and _contains_keywords(
        boundary_search_results,
        ("conflict", "definition conflict", "scope conflict", "boundary conflict", "inconsistent", "cross-market", "cannot be compared", "不可比", "不一致", "冲突"),
    ):
        conflicts.append("boundary search log includes conflict signals requiring correction before formal research conclusions")
    return conflicts


def run_boundary_loop(
    scope_pack: Path | None = None,
    material_extracts: Path | None = None,
    research_evidence_db: Path | None = None,
    boundary_search_results: Path | None = None,
) -> dict[str, Any]:
    try:
        scope_payload = load_json_file(scope_pack) if scope_pack else {}
    except Exception as exc:
        scope_payload = {"_load_error": str(exc)}
    try:
        extracts_payload = load_json_file(material_extracts) if material_extracts else {}
    except Exception:
        extracts_payload = {}
    try:
        evidence_payload = load_json_file(research_evidence_db) if research_evidence_db else {}
    except Exception:
        evidence_payload = {}
    boundary_text = None
    if boundary_search_results:
        try:
            boundary_text = boundary_search_results.read_text(encoding="utf-8")
        except Exception:
            boundary_text = None

    status = "boundary_ready"
    errors: list[str] = []
    warnings: list[str] = []
    required_scope_errors = _missing_scope_field_errors(scope_payload)
    if required_scope_errors or not scope_payload:
        status = "boundary_draft_missing"
        errors.extend(required_scope_errors or ["industry_scope_pack.json missing or not readable"])
        return _build_status(status, errors, warnings, [], scope_payload, extracts_payload, evidence_payload)

    draft_validation = _boundary_validation_needed(scope_payload)
    conflict_flags = _conflict_signals(evidence_payload if isinstance(evidence_payload, dict) else None, boundary_text)
    if conflict_flags:
        status = "boundary_conflict_found"
        errors.append("Boundary evidence conflict detected between scope and research evidence.")
        errors.extend(conflict_flags[:3])
        return _build_status(status, errors, warnings, _repair_actions(status, scope_payload), scope_payload, extracts_payload, evidence_payload)

    if draft_validation:
        status = "boundary_validation_needed"
        warnings.extend(draft_validation)
        return _build_status(status, errors, warnings, _repair_actions(status, scope_payload), scope_payload, extracts_payload, evidence_payload)

    if not scope_payload.get("do_not_use_as_claims", True):
        warnings.append("industry_scope_pack should keep do_not_use_as_claims true when still in boundary phase")

    return _build_status(status, errors, warnings, [], scope_payload, extracts_payload, evidence_payload)


def _repair_actions(status: str, scope_pack: dict[str, Any]) -> list[dict[str, str]]:
    working, parent, _ = _extract_paths(scope_pack)
    if status == "boundary_draft_missing":
        return [
            {
                "issue_id": "BL-001",
                "owner": "industry-scoping",
                "action": "Repair industry_scope_pack.json to include working/parent/broader market, scope_classification, and draft fields before rerunning boundary loop.",
                "repair_owner": "industry-scoping",
                "rerun_command": "python3 scripts/boundary_loop.py --scope-pack artifacts/industry_scope_pack.json --material-extracts artifacts/material_extracts.json --research-evidence-db artifacts/research_evidence_db.json --boundary-search-results artifacts/search_log.md --output artifacts/boundary_loop_status.json",
            }
        ]
    if status == "boundary_validation_needed":
        return [
            {
                "issue_id": "BL-002",
                "owner": "industry-scoping",
                "action": "Refine scope definition, add excluded scope and adjacent themes, and run broad-discovery boundary validation before formal planning repair.",
                "repair_owner": "industry-scoping",
                "rerun_command": "python3 scripts/boundary_loop.py --scope-pack artifacts/industry_scope_pack.json --material-extracts artifacts/material_extracts.json --research-evidence-db artifacts/research_evidence_db.json --boundary-search-results artifacts/search_log.md --output artifacts/boundary_loop_status.json",
            }
        ]
    if status == "boundary_conflict_found":
        return [
            {
                "issue_id": "BL-003",
                "owner": "industry-scoping",
                "action": f"Resolve boundary conflicts between {working} and {parent} definitions before drafting formal market claims.",
                "repair_owner": "industry-scoping",
                "rerun_command": "python3 scripts/boundary_loop.py --scope-pack artifacts/industry_scope_pack.json --material-extracts artifacts/material_extracts.json --research-evidence-db artifacts/research_evidence_db.json --boundary-search-results artifacts/search_log.md --output artifacts/boundary_loop_status.json",
            }
        ]
    return []


def _build_status(
    status: str,
    errors: list[str],
    warnings: list[str],
    repair_actions: list[dict[str, str]],
    scope_pack: dict[str, Any],
    material_extracts: dict[str, Any],
    research_evidence_db: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status if status in LOOP_STATUSES else "boundary_draft_missing",
        "boundary_loop_status": status,
        "is_valid": status == "boundary_ready",
        "created_at": _now_iso(),
        "errors": errors,
        "warnings": warnings,
        "repair_actions": repair_actions,
        "boundary_inputs": {
            "scope_pack": bool(scope_pack),
            "material_extracts": bool(material_extracts),
            "research_evidence_db": bool(research_evidence_db),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope-pack", required=True)
    parser.add_argument("--material-extracts", default="")
    parser.add_argument("--research-evidence-db", default="")
    parser.add_argument("--boundary-search-results", default="")
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = run_boundary_loop(
        scope_pack=Path(args.scope_pack),
        material_extracts=Path(args.material_extracts) if args.material_extracts else None,
        research_evidence_db=Path(args.research_evidence_db) if args.research_evidence_db else None,
        boundary_search_results=Path(args.boundary_search_results) if args.boundary_search_results else None,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["is_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
