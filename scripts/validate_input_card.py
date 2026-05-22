#!/usr/bin/env python3
"""Validate that input_card.json contains only user-provided facts plus safe metadata.

The input card is a normalization layer, not a research output. Inferred peers,
risks, source preferences, and research topics belong in artifacts/research_plan.json
or industry_input_memo.md unless the user explicitly provided them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from json_utils import load_json_file


HIGH_RISK_INFERRED_PATHS = {
    "known_investment_highlights",
    "known_risks_or_open_questions",
    "management_hypotheses",
    "peer_set",
    "must_cover_topics",
    "must_avoid_topics",
    "research_direction.priority_websites",
    "research_direction.preferred_source_domains",
    "research_direction.preferred_source_packs",
    "research_direction.priority_topics",
    "research_direction.peer_set",
    "research_direction.avoid_topics",
    "research_direction.avoid_sources",
}

LOW_RISK_NORMALIZED_PATHS = {
    "industry",
    "subsector",
    "geography",
    "language",
    "transaction_type",
}


def get_path(data: dict[str, Any], path: str) -> Any:
    cur: Any = data
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def is_non_empty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def provenance_paths(data: dict[str, Any], key: str) -> set[str]:
    provenance = data.get("_provenance", {})
    if not isinstance(provenance, dict):
        return set()
    values = provenance.get(key, [])
    if not isinstance(values, list):
        return set()
    return {str(item).strip() for item in values if str(item).strip()}


def validate(data: dict[str, Any], allow_enriched: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    user_provided = provenance_paths(data, "user_provided_paths")
    normalized = provenance_paths(data, "normalized_metadata_paths")

    if allow_enriched:
        warnings.append("allow_enriched=true: inferred input-card fields are not treated as errors")

    for path in sorted(HIGH_RISK_INFERRED_PATHS):
        value = get_path(data, path)
        if is_non_empty(value) and path not in user_provided and not allow_enriched:
            errors.append(
                f"{path} is populated but not marked as user-provided. "
                "Do not enrich input_card with inferred peers, sources, risks, or must-cover topics; "
                "put planner-generated items in artifacts/research_plan.json."
            )

    for path in sorted(LOW_RISK_NORMALIZED_PATHS):
        value = get_path(data, path)
        if is_non_empty(value) and path not in user_provided and path not in normalized:
            warnings.append(
                f"{path} is populated without provenance; mark it as user_provided or normalized_metadata"
            )

    return {
        "is_valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "high_risk_paths": sorted(HIGH_RISK_INFERRED_PATHS),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate input_card.json provenance and anti-enrichment rules.")
    parser.add_argument("--input-card", required=True, help="Path to input_card.json")
    parser.add_argument("--output", help="Optional JSON report path")
    parser.add_argument(
        "--allow-enriched",
        action="store_true",
        help="Allow populated research/planner fields even without user_provided_paths provenance.",
    )
    args = parser.parse_args()

    try:
        data = load_json_file(Path(args.input_card))
    except Exception as exc:
        result = {
            "is_valid": False,
            "error_count": 1,
            "warning_count": 0,
            "errors": [str(exc)],
            "warnings": [],
        }
    else:
        result = validate(data, args.allow_enriched)
        result["input_card"] = args.input_card

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["is_valid"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
