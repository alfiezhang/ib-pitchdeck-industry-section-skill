#!/usr/bin/env python3
"""Build a material manifest placeholder from user inputs."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from source_classification import normalize_source_type
from material_intake_common import text


def _entry(*, material_id: str, source: str, source_type: str, title: str = "", notes: str = "") -> dict[str, Any]:
    source_text = text(source)
    kind = "url" if source_text.startswith(("http://", "https://")) else "file" if source_text else "text"
    return {
        "material_id": material_id,
        "material_title": title or source_text or material_id,
        "source_type": normalize_source_type(source_type),
        "source_access": "user_provided",
        "file_path_or_url": source_text,
        "material_kind": kind,
        "extraction_status": "pending",
        "extraction_limitations": "not_processed",
        "can_be_used_as_evidence": False,
        "brief_excerpt": notes,
        "locator": source_text,
        "source_classification": normalize_source_type(source_type),
    }


def build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    materials: list[dict[str, Any]] = []
    next_id = 1
    if args.brief_text:
        materials.append(
            _entry(
                material_id=f"MAT-{next_id:03d}",
                source="inline_user_text",
                source_type="project_specific_material",
                title="User inline brief",
                notes=args.brief_text.strip() if args.brief_text else "",
            )
        )
        next_id += 1
    for path in args.file or []:
        materials.append(
            _entry(
                material_id=f"MAT-{next_id:03d}",
                source=path,
                source_type=args.default_file_source_type,
            )
        )
        next_id += 1
    for url in args.url or []:
        materials.append(
            _entry(
                material_id=f"MAT-{next_id:03d}",
                source=url,
                source_type=args.default_url_source_type,
            )
        )
        next_id += 1
    return {
        "schema_version": "material_manifest_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "policy_context": "pre_mandate_client_pitch",
        "materials": materials,
        "source_type_policy": {
            "user_curated_industry_report": "High-priority candidate source, not automatically true; extract and reconcile before claim use.",
            "project_specific_material": "User-provided project fact source; mark as user-provided until externally validated.",
            "web_search_result": "Public source candidate; requires source review and archive before evidence promotion.",
        },
        "source_classification": {
            "schema_version": "source_classification_v1",
            "materials": [
                {
                    "material_id": item["material_id"],
                    "source_type": item["source_type"],
                    "source_access": item["source_access"],
                    "file_path_or_url": item["file_path_or_url"],
                    "source_hash": "",
                    "source_date": "",
                }
                for item in materials
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief-text", help="Inline user brief text to register as material.")
    parser.add_argument("--file", action="append", help="User-provided file path. Can be repeated.")
    parser.add_argument("--url", action="append", help="User-provided URL. Can be repeated.")
    parser.add_argument("--default-file-source-type", default="project_specific_material")
    parser.add_argument("--default-url-source-type", default="manual_url_ingestion")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    payload = build_manifest(args)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"is_valid": True, "output": str(output), "material_count": len(payload["materials"])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
