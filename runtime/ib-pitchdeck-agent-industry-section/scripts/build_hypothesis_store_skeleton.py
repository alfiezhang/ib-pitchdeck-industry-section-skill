#!/usr/bin/env python3
"""Build a hypothesis store skeleton from issue analysis and evidence gaps."""

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
    parser.add_argument("--issue-analysis")
    parser.add_argument("--research-evidence-db")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    issue_analysis = load_json_file(Path(args.issue_analysis)) if args.issue_analysis and Path(args.issue_analysis).exists() else {}
    db = load_json_file(Path(args.research_evidence_db)) if args.research_evidence_db and Path(args.research_evidence_db).exists() else {}
    hypotheses: list[dict[str, Any]] = []

    for idx, item in enumerate(as_list(issue_analysis.get("issue_analyses")), start=1):
        if not isinstance(item, dict):
            continue
        support = text(item.get("evidence_status") or item.get("status") or item.get("support_status"))
        if support in {"thin", "directional", "unverified", "partially_validated", "insufficient", "not_researched"}:
            hypotheses.append(
                {
                    "hypothesis_id": f"HYP-{len(hypotheses) + 1:03d}",
                    "source_artifact": "industry_issue_analysis.json",
                    "issue_analysis_id": text(item.get("analysis_id") or item.get("issue_analysis_id") or f"IA-{idx:03d}"),
                    "issue_area": text(item.get("issue_area")),
                    "issue_subissue": text(item.get("subissue")),
                    "hypothesis": text(item.get("judgment") or item.get("finding") or item.get("headline") or item.get("summary")),
                    "current_support": support or "unverified",
                    "resolution_status": "pending_resolution",
                    "allowed_use_before_resolution": "not_allowed_in_headline",
                    "research_request_id": "",
                    "caveat_text": "",
                }
            )

    gap_audit = db.get("research_gap_audit") if isinstance(db.get("research_gap_audit"), dict) else {}
    for gap in as_list(gap_audit.get("critical_gaps")):
        if text(gap):
            hypotheses.append(
                {
                    "hypothesis_id": f"HYP-{len(hypotheses) + 1:03d}",
                    "source_artifact": "artifacts/research_evidence_db.json",
                    "issue_analysis_id": "",
                    "issue_area": "",
                    "issue_subissue": "",
                    "hypothesis": text(gap),
                    "current_support": "not_researched",
                    "resolution_status": "research_required",
                    "allowed_use_before_resolution": "caveat_or_diligence_question_only",
                    "research_request_id": "",
                    "caveat_text": text(gap),
                }
            )

    payload = {
        "schema_version": "hypothesis_store_v1",
        "policy_context": "pre_mandate_client_pitch",
        "hypotheses": hypotheses,
        "resolution_policy": {
            "supported": "May become supported judgment and page argument.",
            "directional": "Body/context only; not headline.",
            "caveat_only": "Caveat or diligence question only.",
            "not_researched": "Not allowed in deck claim.",
        },
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"is_valid": True, "output": str(out), "hypothesis_count": len(hypotheses)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
