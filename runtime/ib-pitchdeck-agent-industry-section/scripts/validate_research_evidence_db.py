#!/usr/bin/env python3
"""Validate artifacts/research_evidence_db.json before exporting the Markdown research pack."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from json_utils import load_json_file
from research_evidence_db import validate_db


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research-evidence-db", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    path = Path(args.research_evidence_db)
    try:
        payload = load_json_file(path)
    except Exception as exc:
        result = {
            "is_valid": False,
            "error_count": 1,
            "warning_count": 0,
            "errors": [f"cannot read research evidence db: {exc}"],
            "warnings": [],
            "research_evidence_db": str(path),
        }
    else:
        errors, warnings, metrics = validate_db(payload)
        result = {
            "is_valid": not errors,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "errors": errors,
            "warnings": warnings,
            "research_evidence_db": str(path),
            "metrics": metrics,
            "repair_plan": {
                "primary_repair_target": "artifacts/research_evidence_db.json",
                "do_not_edit": ["industry_research_pack.md", "industry_issue_analysis.json", "deck_blueprint.json"],
                "rerun_steps": [
                    "scripts/validate_research_evidence_db.py",
                    "scripts/export_research_pack_from_db.py",
                    "scripts/validate_research_pack.py",
                ],
            }
            if errors
            else {},
        }
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["is_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
