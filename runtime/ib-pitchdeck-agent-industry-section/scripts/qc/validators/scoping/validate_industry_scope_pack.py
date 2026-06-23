#!/usr/bin/env python3
"""Validate industry_scope_pack.json as a brief boundary card."""

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

from json_utils import load_json_file


SCHEMA_VERSION = "industry_scope_pack_v2"
TOP_LEVEL_KEYS = {
    "schema_version",
    "meta",
    "scope_summary",
    "scope_classification",
    "must_reconcile",
    "boundary_validation_needed",
    "handoff_to_research",
    "do_not_use_as_claims",
}
LEGACY_V1_FIELDS = {
    "llm_definition_draft",
    "market_definitions",
    "ambiguous_boundaries",
    "data_hierarchy",
    "unvalidated_leads",
    "required_reconciliations",
    "formal_research_seed_questions",
    "scope_confidence_rationale",
    "reconciliation_policy",
    "scope_stage_instruction",
}
META_FIELDS = ("target_disclosure_status", "transaction_type", "geography", "language", "prepared_date")
SCOPE_SUMMARY_FIELDS = ("working_market", "parent_market", "broader_market")
CLASSIFICATION_LIMITS = {"core": 6, "broad": 6, "adjacent": 6, "excluded": 8}

NUMERIC_METRIC_RE = re.compile(
    r"(?:\d+(?:\.\d+)?\s*(?:%|％|亿元|亿|万亿元|万|百万|百万元|billion|million|bn|m|x|倍|bp|bps)|(?:千亿|百亿|万亿))",
    re.IGNORECASE,
)
FORBIDDEN_CLAIM_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "market size",
        re.compile(
            r"(?:market\s+size|市场规模|规模).{0,30}"
            r"(?:\d+(?:\.\d+)?\s*(?:%|％|亿元|亿|万亿元|万|百万|百万元|billion|million|bn|m)|千亿|百亿|万亿)",
            re.IGNORECASE,
        ),
    ),
    (
        "growth rate",
        re.compile(
            r"(?:CAGR|growth\s+rate|同比|YoY|复合增长|增长率|增速).{0,30}"
            r"(?:\d+(?:\.\d+)?\s*(?:%|％|bp|bps)|\d+(?:\.\d+)?)",
            re.IGNORECASE,
        ),
    ),
    (
        "share",
        re.compile(
            r"(?:market\s+share|share|市占率|份额).{0,30}"
            r"(?:\d+(?:\.\d+)?\s*(?:%|％)|Top\s*\d+|TOP\s*\d+)",
            re.IGNORECASE,
        ),
    ),
    (
        "ranking",
        re.compile(r"(?:rank(?:ed|ing)?|No\.?\s*\d+|#\s*\d+|Top\s*\d+|TOP\s*\d+|排名|位列|第\s*\d+)", re.IGNORECASE),
    ),
    (
        "valuation",
        re.compile(r"(?:valuation|估值|P/E|EV/EBITDA|EV/Revenue|P/S|倍数|\bPE\b|\bPS\b)", re.IGNORECASE),
    ),
    (
        "transaction conclusion",
        re.compile(r"(?:transaction\s+conclusion|investment\s+thesis|投资亮点|交易观点|建议.{0,12}(?:出售|收购|并购)|适合.{0,12}(?:出售|收购|并购))", re.IGNORECASE),
    ),
    (
        "page-ready claim",
        re.compile(r"(?:page-ready|slide\s+headline|deck\s+headline|可直接上页|页面结论|标题可用|核心结论)", re.IGNORECASE),
    ),
)
UNVERIFIED_RECONCILE_RE = re.compile(
    r"(?:user[-\s]?provided|management[-\s]?provided|用户提供|管理层|未验证|待核验|需验证|需要验证|核验|验证|verify|unverified|not\s+verified|external\s+verification)",
    re.IGNORECASE,
)


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


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


def _cjk_count(text: str) -> int:
    return len(re.findall(r"[\u3400-\u9fff]", text))


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9/._+-]*", text))


def _too_long_for_short_item(text: str) -> bool:
    return _cjk_count(text) > 25 or _word_count(text) > 20 or len(text) > 140


def _memo_like(text: str) -> bool:
    return "\n" in text.strip() or _cjk_count(text) > 80 or _word_count(text) > 40


def _sentence_count(text: str) -> int:
    chunks = [item for item in re.split(r"[。！？.!?]+", text.strip()) if item.strip()]
    return len(chunks)


def _validate_object(value: Any, path: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{path} must be an object")
        return {}
    return value


def _validate_string_field(container: dict[str, Any], field: str, path: str, errors: list[str]) -> str:
    value = container.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path}.{field} is required")
        return ""
    if "\n" in value:
        errors.append(f"{path}.{field} must be one line")
    return value.strip()


def _validate_required(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        if version == "industry_scope_pack_v1":
            errors.append("schema_version must be industry_scope_pack_v2; v1 scope memo artifacts are no longer accepted")
        else:
            errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if data.get("do_not_use_as_claims") is not True:
        errors.append("do_not_use_as_claims must be true")

    missing = [key for key in TOP_LEVEL_KEYS if key not in data]
    errors.extend(f"{key} is required" for key in sorted(missing))
    for key in sorted(set(data) - TOP_LEVEL_KEYS):
        if key in LEGACY_V1_FIELDS:
            errors.append(f"{key} is a legacy v1 memo field and is not allowed in industry_scope_pack_v2")
        else:
            errors.append(f"{key} is not allowed in industry_scope_pack_v2")

    meta = _validate_object(data.get("meta"), "meta", errors)
    for field in META_FIELDS:
        _validate_string_field(meta, field, "meta", errors)
    target_disclosure_status = _text(meta.get("target_disclosure_status")).lower()
    if target_disclosure_status not in {"disclosed", "undisclosed"}:
        errors.append("meta.target_disclosure_status must be disclosed or undisclosed")
    if target_disclosure_status == "disclosed":
        _validate_string_field(meta, "target_company", "meta", errors)
    elif "target_company" in meta and not isinstance(meta.get("target_company"), str):
        errors.append("meta.target_company must be a string when provided")

    scope_summary = _validate_object(data.get("scope_summary"), "scope_summary", errors)
    for field in SCOPE_SUMMARY_FIELDS:
        _validate_string_field(scope_summary, field, "scope_summary", errors)

    classification = _validate_object(data.get("scope_classification"), "scope_classification", errors)
    for field, limit in CLASSIFICATION_LIMITS.items():
        raw_values = classification.get(field)
        if not isinstance(raw_values, list):
            errors.append(f"scope_classification.{field} must be an array")
            continue
        if len(raw_values) > limit:
            errors.append(f"scope_classification.{field} has {len(raw_values)} items; maximum is {limit}")
        if field == "core" and not raw_values:
            errors.append("scope_classification.core must include at least one item")
        for idx, item in enumerate(raw_values, start=1):
            if not isinstance(item, str) or not item.strip():
                errors.append(f"scope_classification.{field}[{idx}] must be a non-empty string")

    _validate_reconcile_rows(data.get("must_reconcile"), errors)
    _validate_boundary_rows(data.get("boundary_validation_needed"), errors)

    handoff = _validate_object(data.get("handoff_to_research"), "handoff_to_research", errors)
    research_scope = _validate_string_field(handoff, "research_scope", "handoff_to_research", errors)
    if research_scope and _sentence_count(research_scope) > 2:
        errors.append("handoff_to_research.research_scope must be no more than 2 sentences")
    for field in ("do_not_use_as_market_scope", "must_label_when_used"):
        if not isinstance(handoff.get(field), list):
            errors.append(f"handoff_to_research.{field} must be an array")
        else:
            for idx, item in enumerate(handoff[field], start=1):
                if not isinstance(item, str):
                    errors.append(f"handoff_to_research.{field}[{idx}] must be a string")
    return errors


def _validate_reconcile_rows(value: Any, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append("must_reconcile must be an array")
        return
    if len(value) > 5:
        errors.append(f"must_reconcile has {len(value)} items; maximum is 5")
    for idx, row in enumerate(value, start=1):
        if not isinstance(row, dict):
            errors.append(f"must_reconcile[{idx}] must be an object")
            continue
        for field in ("topic", "why_it_matters", "research_instruction"):
            _validate_string_field(row, field, f"must_reconcile[{idx}]", errors)
        for field in set(row) - {"topic", "why_it_matters", "research_instruction"}:
            errors.append(f"must_reconcile[{idx}].{field} is not allowed")


def _validate_boundary_rows(value: Any, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append("boundary_validation_needed must be an array")
        return
    if len(value) > 5:
        errors.append(f"boundary_validation_needed has {len(value)} items; maximum is 5")
    for idx, row in enumerate(value, start=1):
        if not isinstance(row, dict):
            errors.append(f"boundary_validation_needed[{idx}] must be an object")
            continue
        for field in ("question", "why_needed", "suggested_validation_source"):
            _validate_string_field(row, field, f"boundary_validation_needed[{idx}]", errors)
        for field in set(row) - {"question", "why_needed", "suggested_validation_source"}:
            errors.append(f"boundary_validation_needed[{idx}].{field} is not allowed")


def _validate_length(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for path, value in _walk(data):
        if not isinstance(value, str) or not value.strip():
            continue
        if path.startswith("meta."):
            continue
        if _memo_like(value):
            errors.append(f"{path}: memo-like paragraph is not allowed in a boundary card")
            continue
        if path.startswith("scope_classification.") and _too_long_for_short_item(value):
            errors.append(f"{path}: item is too long for a boundary card")
            continue
        if (
            path.startswith("must_reconcile[")
            or path.startswith("boundary_validation_needed[")
            or path.startswith("handoff_to_research.do_not_use_as_market_scope[")
            or path.startswith("handoff_to_research.must_label_when_used[")
        ) and _too_long_for_short_item(value):
            warnings.append(f"{path}: keep item close to 25 Chinese characters or 20 English words")
    return errors, warnings


def _is_allowed_unverified_reconcile(data: dict[str, Any], path: str) -> bool:
    match = re.match(r"must_reconcile\[(\d+)\]", path)
    if not match:
        return False
    rows = data.get("must_reconcile")
    if not isinstance(rows, list):
        return False
    index = int(match.group(1))
    if index >= len(rows) or not isinstance(rows[index], dict):
        return False
    combined = " ".join(_text(value) for value in rows[index].values())
    return bool(UNVERIFIED_RECONCILE_RE.search(combined))


def _validate_no_claim_pollution(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for path, value in _walk(data):
        if not isinstance(value, str) or not value.strip() or path.startswith("meta."):
            continue
        if path == "schema_version":
            continue
        if _is_allowed_unverified_reconcile(data, path):
            continue
        text = value.strip()
        for label, pattern in FORBIDDEN_CLAIM_PATTERNS:
            if pattern.search(text):
                errors.append(f"{path}: {label} claim belongs in formal research, not industry_scope_pack_v2")
                break
        else:
            if NUMERIC_METRIC_RE.search(text) and not path.endswith(".prepared_date"):
                errors.append(f"{path}: numeric market/metric finding belongs in formal research, not industry_scope_pack_v2")
    return errors


def validate(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors = _validate_required(data)
    length_errors, warnings = _validate_length(data)
    errors.extend(length_errors)
    errors.extend(_validate_no_claim_pollution(data))
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
