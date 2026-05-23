#!/usr/bin/env python3
"""Validate that input_card.json contains only user-provided facts plus safe metadata.

The input card is a normalization layer, not a research output. Inferred peers,
risks, source preferences, and research topics belong in artifacts/research_plan.json
or industry_input_memo.md unless the user explicitly provided them.

Generation rule: build the input card in transcription mode. Copy the user's brief
faithfully into user-provided fields, perform only minimal metadata normalization,
and leave planner/research fields empty unless the user explicitly supplied them.
"""

from __future__ import annotations

import argparse
import json
import re
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

ALLOWED_LANGUAGES = {
    "Chinese",
    "English",
    "zh-CN",
    "en",
    "中文",
    "英文",
}
LANGUAGE_ALIASES = {
    "Chinese": "Chinese",
    "zh-CN": "Chinese",
    "中文": "Chinese",
    "English": "English",
    "en": "English",
    "英文": "English",
}
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


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


def request_language(data: dict[str, Any]) -> str:
    provenance = data.get("_provenance", {})
    if not isinstance(provenance, dict):
        return ""
    return str(provenance.get("request_language", "")).strip()


def canonical_language(value: str) -> str:
    return LANGUAGE_ALIASES.get(value.strip(), value.strip())


def validate(data: dict[str, Any], allow_enriched: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    user_provided = provenance_paths(data, "user_provided_paths")
    normalized = provenance_paths(data, "normalized_metadata_paths")
    req_language = request_language(data)

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

    language = str(data.get("language", "")).strip()
    if not language:
        warnings.append(
            "language is blank; default output language should follow the user's request language unless explicitly overridden"
        )
    elif language not in ALLOWED_LANGUAGES:
        warnings.append(f"language value '{language}' is non-standard; expected one of {sorted(ALLOWED_LANGUAGES)}")
    elif req_language and canonical_language(language) != canonical_language(req_language) and "language" not in user_provided:
        errors.append(
            f"language is '{language}' but request_language is '{req_language}'. "
            "Default to the user's request language unless the user explicitly asked for another output language."
        )
    elif (
        not req_language
        and language in {"English", "en", "英文"}
        and "language" not in user_provided
        and CJK_RE.search(str(data.get("target_business_summary", "")))
    ):
        errors.append(
            "language defaults to English while the user brief appears Chinese and no explicit language override is marked. "
            "Default output language should follow the user's request language."
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
