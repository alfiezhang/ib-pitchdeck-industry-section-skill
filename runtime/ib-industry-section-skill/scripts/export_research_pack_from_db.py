#!/usr/bin/env python3
"""Export industry_research_pack.md from artifacts/research_evidence_db.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from json_utils import load_json_file
from research_evidence_db import export_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research-evidence-db", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    db_path = Path(args.research_evidence_db)
    payload = load_json_file(db_path)
    output = export_markdown(payload)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output, encoding="utf-8")
    print(json.dumps({"is_valid": True, "research_evidence_db": str(db_path), "output": str(output_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
