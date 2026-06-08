#!/usr/bin/env python3
"""Validate industry_scope_pack.json as a scoping artifact, not a mini memo."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from json_utils import load_json_file


SCHEMA_VERSION = "industry_scope_pack_v1"
CLAIMY_KEYS = {
    "summary",
    "findings",
    "conclusion",
    "market_size",
    "growth_rate",
    "market_share",
    "channel_ranking",
    "competitive_landscape",
    "valuation",
}
FORBIDDEN_CLAIM_PATTERNS = (
    re.compile(r"\b(?:CAGR|YoY|同比|复合增长|增长率)\b", re.IGNORECASE),
    re.compile(r"\b(?:market share|市占率|份额|排名|Top\s*\d+|TOP\s*\d+)\b", re.IGNORECASE),
    re.compile(r"\b(?:valuation|估值|PE|P/E|EV/EBITDA|EV/Revenue|PS|P/S)\b", re.IGNORECASE),
    re.compile(r"\b(?:confirmed|validated|proven|已验证|确定|明确|领跑|超越|主导)\b", re.IGNORECASE),
)
NUMERIC_CLAIM_RE = re.compile(
    r"(?:\d+(?:\.\d+)?\s*(?:%|％|亿元|亿|万亿元|万|x|倍|bp|bps)|(?:千亿|百亿|万亿))",
    flags=re.IGNORECASE,
)


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _walk(value: Any, path: str = "") -> list[tuple[str, Any]]:
    items: list[tuple[str, Any]] = [(path, value)]
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            items.extend(_walk(child, child_path))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            child_path = f"{path}[{idx}]"
            items.extend(_walk(child, child_path))
    return items


def _is_under(path: str, allowed_roots: tuple[str, ...]) -> bool:
    return any(path == root or path.startswith(root + ".") or path.startswith(root + "[") for root in allowed_roots)


def _validate_required(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = [
        "schema_version",
        "meta",
        "scope_summary",
        "market_definitions",
        "ambiguous_boundaries",
        "data_hierarchy",
        "unvalidated_leads",
        "required_reconciliations",
        "formal_research_seed_questions",
        "do_not_use_as_claims",
    ]
    for key in required:
        if key not in data:
            errors.append(f"{key} is required")
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if data.get("do_not_use_as_claims") is not True:
        errors.append("do_not_use_as_claims must be true")

    scope_summary = data.get("scope_summary")
    if not isinstance(scope_summary, dict):
        errors.append("scope_summary must be an object")
    else:
        if not str(scope_summary.get("working_market") or "").strip():
            errors.append("scope_summary.working_market is required")
        if not isinstance(scope_summary.get("adjacent_markets"), list):
            errors.append("scope_summary.adjacent_markets must be an array")

    definitions = data.get("market_definitions")
    if not isinstance(definitions, dict):
        errors.append("market_definitions must be an object")
    else:
        for key in ("narrow_definition", "broad_definition"):
            item = definitions.get(key)
            if not isinstance(item, dict):
                errors.append(f"market_definitions.{key} must be an object")
                continue
            if not _as_list(item.get("included_segments")):
                errors.append(f"market_definitions.{key}.included_segments must be populated")
            if not str(item.get("use_case") or "").strip():
                errors.append(f"market_definitions.{key}.use_case is required")

    if len(_as_list(data.get("data_hierarchy"))) < 3:
        errors.append("data_hierarchy must include at least 3 levels")
    if len(_as_list(data.get("formal_research_seed_questions"))) < 3:
        errors.append("formal_research_seed_questions must include at least 3 questions")
    if not _as_list(data.get("ambiguous_boundaries")) and not str(data.get("scope_confidence_rationale") or "").strip():
        errors.append(
            "ambiguous_boundaries may be empty only when scope_confidence_rationale explains why no material boundary ambiguity was identified"
        )
    if not _as_list(data.get("required_reconciliations")) and not str(data.get("reconciliation_policy") or "").strip():
        errors.append(
            "required_reconciliations may be empty only when reconciliation_policy explains why no material scope/metric conflict was identified"
        )
    return errors


def _validate_no_claim_pollution(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    allowed_numeric_roots = ("unvalidated_leads",)
    allowed_topic_roots = (
        "scope_stage_instruction",
        "data_hierarchy",
        "required_reconciliations",
        "formal_research_seed_questions",
        "unvalidated_leads",
    )
    for path, value in _walk(data):
        if not path:
            continue
        key = path.split(".")[-1].split("[")[0]
        if key in CLAIMY_KEYS:
            warnings.append(f"{path}: claim-like key should usually move to formal research or unvalidated_leads")
        if not isinstance(value, str) or not value.strip():
            continue
        if _is_under(path, allowed_numeric_roots):
            continue
        if NUMERIC_CLAIM_RE.search(value):
            errors.append(
                f"{path}: numeric finding appears outside unvalidated_leads; scope pack must not contain confirmed market/growth/share/valuation claims"
            )
            continue
        if _is_under(path, allowed_topic_roots):
            continue
        for pattern in FORBIDDEN_CLAIM_PATTERNS:
            if pattern.search(value):
                errors.append(
                    f"{path}: conclusion-like or metric claim language belongs in formal research execution, not industry_scope_pack"
                )
                break
    return errors, warnings


def _validate_unvalidated_leads(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for idx, lead in enumerate(_as_list(data.get("unvalidated_leads")), start=1):
        if not isinstance(lead, dict):
            errors.append(f"unvalidated_leads[{idx}] must be an object")
            continue
        lead_text = str(lead.get("lead") or "")
        if NUMERIC_CLAIM_RE.search(lead_text) and not _as_list(lead.get("must_validate")):
            errors.append(f"unvalidated_leads[{idx}]: numeric lead requires must_validate[] instructions")
    return errors


def validate(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors = _validate_required(data)
    warnings: list[str] = []
    pollution_errors, pollution_warnings = _validate_no_claim_pollution(data)
    errors.extend(pollution_errors)
    warnings.extend(pollution_warnings)
    errors.extend(_validate_unvalidated_leads(data))
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope-pack", required=True, help="Path to artifacts/industry_scope_pack.json")
    parser.add_argument("--output", help="Optional validation JSON output path")
    args = parser.parse_args()

    path = Path(args.scope_pack)
    try:
        data = load_json_file(path)
    except Exception as exc:
        result = {
            "is_valid": False,
            "error_count": 1,
            "warning_count": 0,
            "errors": [f"cannot read industry_scope_pack.json: {exc}"],
            "warnings": [],
            "scope_pack": str(path),
        }
    else:
        if not isinstance(data, dict):
            errors, warnings = ["industry_scope_pack.json must be a JSON object"], []
        else:
            errors, warnings = validate(data)
        result = {
            "is_valid": not errors,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "errors": errors,
            "warnings": warnings,
            "scope_pack": str(path),
        }

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["is_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
