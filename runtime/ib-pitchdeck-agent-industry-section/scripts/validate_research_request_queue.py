#!/usr/bin/env python3
"""Validate public research request queue for pre-mandate workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from json_utils import load_json_file


ALLOWED_SOURCE_TYPES = {
    "public_search",
    "user_curated_industry_report",
    "manual_url_ingestion",
    "repository_retrieval",
    "internal_data_request",
}

ALLOWED_DOWNSTREAM_PERMISSION = {
    "headline_disallowed",
    "caveat_or_diligence_question_only",
    "context_only",
    "body_only",
    "disallowed_as_claim",
}


def text(value: Any) -> str:
    return str(value or "").strip()


def validate(payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("schema_version") != "research_request_queue_v1":
        errors.append("schema_version must be research_request_queue_v1")
    requests = payload.get("requests")
    if not isinstance(requests, list):
        errors.append("requests must be an array")
        return errors, warnings

    seen: set[str] = set()
    for idx, item in enumerate(requests, start=1):
        if not isinstance(item, dict):
            errors.append(f"requests[{idx}] must be an object")
            continue

        req_id = text(item.get("request_id") or item.get("research_request_id"))
        if not req_id:
            errors.append(f"requests[{idx}].request_id is required")
        elif req_id in seen:
            errors.append(f"duplicate request_id: {req_id}")
        seen.add(req_id)

        if not text(item.get("origin_issue_id")):
            warnings.append(f"{req_id or idx}: origin_issue_id is recommended for traceability")

        if not text(item.get("hypothesis_id")):
            errors.append(f"{req_id or idx}: hypothesis_id is required")

        if not text(item.get("research_question")):
            errors.append(f"{req_id or idx}: research_question is required")

        source_type = text(item.get("required_source_type"))
        if source_type not in ALLOWED_SOURCE_TYPES:
            warnings.append(f"{req_id or idx}: unsupported required_source_type '{source_type}', treat as public_search")

        minimum_actual_searches = item.get("minimum_actual_searches")
        if not isinstance(minimum_actual_searches, int) or minimum_actual_searches < 0:
            errors.append(f"{req_id or idx}: minimum_actual_searches must be a non-negative integer")

        downstream_permission = text(item.get("downstream_permission_if_unresolved") or item.get("downstream_permission_until_resolved"))
        if not downstream_permission:
            errors.append(f"{req_id or idx}: downstream_permission_if_unresolved is required")
        elif downstream_permission not in ALLOWED_DOWNSTREAM_PERMISSION:
            warnings.append(
                f"{req_id or idx}: downstream_permission_if_unresolved '{downstream_permission}' is not a canonical value. "
                "Use caveat_or_diligence_question_only for unresolved queue rows."
            )
            if downstream_permission.lower() == "headline_allowed":
                errors.append(f"{req_id or idx}: unresolved research request cannot be headline_allowed")

        question_text = text(item.get("research_question")).lower()
        if "client" in question_text and any(token in question_text for token in ["internal", "confidential", "sensitive", "management data"]):
            errors.append(f"{req_id or idx}: research request appears to ask client for sensitive internal data")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research-request-queue", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        payload = load_json_file(Path(args.research_request_queue))
        errors, warnings = validate(payload)
    except Exception as exc:
        errors, warnings = [f"cannot read research request queue: {exc}"], []

    result = {
        "is_valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "repair_plan": {
            "primary_repair_target": "artifacts/research_request_queue.json",
            "repair_target_role": "reasoning",
        }
        if errors
        else {},
    }
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["is_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

