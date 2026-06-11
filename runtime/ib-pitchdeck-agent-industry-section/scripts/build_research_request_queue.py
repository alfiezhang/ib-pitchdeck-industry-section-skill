#!/usr/bin/env python3
"""Build a public research request queue from unresolved hypotheses."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from json_utils import load_json_file


def text(value: Any) -> str:
    return str(value or "").strip()


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


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
        requests.append(
            {
                "research_request_id": f"RRQ-{len(requests) + 1:03d}",
                "hypothesis_id": text(item.get("hypothesis_id")),
                "research_question": text(item.get("hypothesis")),
                "allowed_source_types": ["public_search", "user_curated_industry_report", "manual_url_ingestion", "repository_retrieval"],
                "forbidden": ["ask_potential_client_for_sensitive_internal_data", "use_hypothesis_as_conclusion"],
                "status": "pending_public_evidence",
                "downstream_permission_until_resolved": "caveat_or_diligence_question_only",
            }
        )
    payload = {
        "schema_version": "research_request_queue_v1",
        "policy_context": "pre_mandate_client_pitch",
        "requests": requests,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"is_valid": True, "output": str(out), "request_count": len(requests)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
