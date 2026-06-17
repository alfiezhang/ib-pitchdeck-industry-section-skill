#!/usr/bin/env python3
"""Build a public research request queue from unresolved hypotheses."""

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
from pathlib import Path
from typing import Any

from json_utils import load_json_file


def text(value: Any) -> str:
    return str(value or "").strip()


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


ALLOWED_SOURCE_TYPES = {
    "public_search",
    "user_curated_industry_report",
    "manual_url_ingestion",
    "repository_retrieval",
}
DOWNSTREAM_PERMISSIONS = {
    "headline_disallowed",
    "caveat_or_diligence_question_only",
    "context_only",
    "body_only",
    "disallowed_as_claim",
}


def _clamp_source_type(value: str) -> str:
    candidate = text(value)
    if candidate in ALLOWED_SOURCE_TYPES:
        return candidate
    if candidate and "repo" in candidate.lower():
        return "repository_retrieval"
    if candidate and "manual" in candidate.lower():
        return "manual_url_ingestion"
    if candidate and "industry report" in candidate.lower():
        return "user_curated_industry_report"
    if candidate and any(token in candidate.lower() for token in ["client", "confidential", "internal", "sensitive"]):
        return "public_search"
    return "public_search"


def _downstream_permission(candidate: str) -> str:
    value = text(candidate)
    if value in {"headline_allowed", "headline"}:
        return "caveat_or_diligence_question_only"
    if value == "not_allowed_in_headline":
        return "caveat_or_diligence_question_only"
    if value in DOWNSTREAM_PERMISSIONS:
        return value
    return "caveat_or_diligence_question_only"


def _minimum_searches(candidate: Any) -> int:
    if isinstance(candidate, int) and candidate >= 0:
        return candidate
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hypothesis-store", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    store = load_json_file(Path(args.hypothesis_store))
    requests: list[dict[str, Any]] = []
    for item in as_list(store.get("hypotheses")):
        if not isinstance(item, dict):
            continue
        resolution = text(item.get("resolution_status"))
        if resolution not in {"research_required", "pending_resolution"}:
            continue
        hypothesis_id = text(item.get("hypothesis_id"))
        issue_analysis_id = text(item.get("issue_analysis_id") or item.get("issue_id"))
        request_id = f"RQ-{len(requests) + 1:03d}"
        requests.append(
            {
                "request_id": request_id,
                "origin_issue_id": issue_analysis_id,
                "hypothesis_id": hypothesis_id,
                "research_question": text(item.get("hypothesis")),
                "required_source_type": _clamp_source_type(text(item.get("required_source_type") or item.get("source_type"))),
                "minimum_actual_searches": _minimum_searches(item.get("minimum_actual_searches")),
                "downstream_permission_if_unresolved": _downstream_permission(text(item.get("allowed_use_before_resolution"))),
                # compatibility aliases for existing downstream scripts/notes
                "research_request_id": request_id,
                "allowed_source_types": [
                    "public_search",
                    "user_curated_industry_report",
                    "manual_url_ingestion",
                    "repository_retrieval",
                ],
                "status": "pending_public_evidence",
                "downstream_permission_until_resolved": _downstream_permission(text(item.get("allowed_use_before_resolution"))),
                "required_source_type_hint": text(item.get("source_type")),
                "origin_issue_area": text(item.get("issue_area")),
                "origin_issue_subissue": text(item.get("issue_subissue")),
                "allowed_use_before_resolution": text(item.get("allowed_use_before_resolution")) or "not_allowed_in_headline",
            }
        )
    payload = {
        "schema_version": "research_request_queue_v1",
        "policy_context": "pre_mandate_client_pitch",
        "requests": requests,
        "build_rule": "requests are generated from unresolved hypotheses only; unresolved requests must stay as unresolved until formal execution creates evidence",
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"is_valid": True, "output": str(out), "request_count": len(requests)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
