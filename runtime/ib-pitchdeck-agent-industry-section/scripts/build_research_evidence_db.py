#!/usr/bin/env python3
"""Build artifacts/research_evidence_db.json skeleton from formal research artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from research_evidence_db import build_db, load_optional_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-card", required=True)
    parser.add_argument("--scope-pack", required=True)
    parser.add_argument("--formal-search-plan", required=True)
    parser.add_argument("--formal-research-execution-report", required=True)
    parser.add_argument("--source-reviews", required=True)
    parser.add_argument("--material-manifest")
    parser.add_argument("--material-extracts")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = build_db(
        input_card=load_optional_json(args.input_card),
        scope_pack=load_optional_json(args.scope_pack),
        formal_search_plan=load_optional_json(args.formal_search_plan),
        execution_report=load_optional_json(args.formal_research_execution_report),
        source_reviews=load_optional_json(args.source_reviews),
        material_manifest=load_optional_json(args.material_manifest),
        material_extracts=load_optional_json(args.material_extracts),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "is_valid": True,
                "output": str(output_path),
                "source_material_count": len(payload.get("source_materials") or []),
                "formal_extract_count": len(payload.get("formal_research_extracts") or []),
                "evidence_skeleton_count": len(payload.get("evidence_ledger") or []),
                "metric_skeleton_count": len(payload.get("metric_reconciliation") or []),
                "note": "Skeleton contains TODO markers. LLM must edit research_evidence_db.json, then validate and export industry_research_pack.md.",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
