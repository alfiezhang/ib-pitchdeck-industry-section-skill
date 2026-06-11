#!/usr/bin/env python3
"""Build boundary validation research requests from boundary QC warnings/failures."""

from __future__ import annotations

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
