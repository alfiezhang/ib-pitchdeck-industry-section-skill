#!/usr/bin/env python3
"""Build boundary validation research requests from boundary QC warnings/failures."""

from __future__ import annotations

# Runtime scripts can be run directly. Shared helpers remain in runtime
# `scripts/`; production tools live under role scripts; validators live under QC.
import sys as _ib_sys
from pathlib import Path as _IbPath
_IB_ROLE_SCRIPT_DIR = _IbPath(__file__).resolve().parent
_IB_RUNTIME_ROOT = next(
    _p for _p in _IbPath(__file__).resolve().parents
    if (_p / 'templates').is_dir() and (_p / 'skills').is_dir() and (_p / 'scripts').is_dir()
)
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts"
_IB_ROLE_SCRIPT_DIRS = sorted((_IB_RUNTIME_ROOT / 'skills').glob('*/scripts'))
_IB_QC_VALIDATOR_DIRS = sorted((_IB_RUNTIME_ROOT / 'skills' / 'qc' / 'scripts' / 'validators').glob('*'))
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boundary-qc", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    qc = load_json_file(Path(args.boundary_qc))
    requests: list[dict[str, Any]] = []
    for request in qc.get("boundary_validation_requests") or []:
        if not isinstance(request, dict):
            continue
        question = text(request.get("research_question") or request.get("question") or request.get("request"))
        if not question:
            continue
        requests.append(
            {
                "boundary_request_id": text(request.get("boundary_request_id")) or f"BRQ-{len(requests) + 1:03d}",
                "source_check_id": text(request.get("source_check_id") or request.get("issue_id")),
                "research_question": question,
                "search_intent": "boundary_validation_only",
                "allowed_sources": request.get("allowed_sources")
                if isinstance(request.get("allowed_sources"), list)
                else ["industry taxonomy", "industry report methodology", "association/regulator definition", "company comparable descriptions"],
                "forbidden": request.get("forbidden")
                if isinstance(request.get("forbidden"), list)
                else ["market_size_claim", "growth_claim", "valuation_claim", "page_thesis"],
                "status": text(request.get("status")) or "pending_boundary_validation",
            }
        )
    for check in qc.get("checks") or []:
        if not isinstance(check, dict) or check.get("status") not in {"fail", "warning"}:
            continue
        check_name = text(check.get("check"))
        if check_name == "excluded_scope_present":
            question = "Which adjacent categories or applications should be excluded from the core target industry definition?"
        elif check_name == "parent_vs_core_distinguished":
            question = "How do authoritative reports distinguish the core target industry from its parent market?"
        elif check_name == "adjacent_scope_present":
            question = "Which adjacent themes should be treated as background rather than core industry scope?"
        elif check_name == "reconciliation_map":
            question = "Which metric definitions or category scopes require reconciliation before formal research?"
        else:
            question = text(check.get("finding")) or f"Resolve boundary check {check_name}"
        requests.append(
            {
                "boundary_request_id": f"BRQ-{len(requests) + 1:03d}",
                "source_check_id": text(check.get("check_id")),
                "research_question": question,
                "search_intent": "boundary_validation_only",
                "allowed_sources": ["industry taxonomy", "industry report methodology", "association/regulator definition", "company comparable descriptions"],
                "forbidden": ["market_size_claim", "growth_claim", "valuation_claim", "page_thesis"],
                "status": "pending_boundary_validation",
            }
        )
    payload = {
        "schema_version": "boundary_research_requests_v1",
        "policy_context": "pre_mandate_client_pitch",
        "requests": requests,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"is_valid": True, "output": str(output), "request_count": len(requests)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
