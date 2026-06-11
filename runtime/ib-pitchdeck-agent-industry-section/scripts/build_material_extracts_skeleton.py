#!/usr/bin/env python3
"""Build material_extracts.json skeleton from a material manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from json_utils import load_json_file
from material_intake_common import text


def text(value: Any) -> str:
    return str(value or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--material-manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    manifest = load_json_file(Path(args.material_manifest))
    extracts = []
    for item in manifest.get("materials") or []:
        if not isinstance(item, dict):
            continue
        extracts.append(
            {
                "material_id": text(item.get("material_id")),
                "source_type": text(item.get("source_type")),
                "source_access": text(item.get("source_access") or item.get("access_level") or "user_provided"),
                "file_path_or_url": text(item.get("file_path_or_url") or item.get("locator")),
                "material_kind": text(item.get("material_kind") or ("url" if text(item.get("file_path_or_url") or item.get("locator")).startswith(("http://", "https://")) else "file")),
                "locator": text(item.get("locator") or item.get("file_path_or_url")),
                "extraction_status": "pending_llm_extraction",
                "extracted_facts": [],
                "extracted_metrics": [],
                "quoted_excerpts": [],
                "unknowns_or_conflicts": [],
                "claim_use_limitations": "Do not use until facts/metrics are extracted with locator and source type.",
                "extraction_limitations": "not_processed",
                "can_be_used_as_evidence": False,
                "extracted_text_path": "",
                "evidence_snapshot": "",
            }
        )
    payload = {
        "schema_version": "material_extracts_v1",
        "materials_source": str(args.material_manifest),
        "extracts": extracts,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"is_valid": True, "output": str(out), "extract_count": len(extracts)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
