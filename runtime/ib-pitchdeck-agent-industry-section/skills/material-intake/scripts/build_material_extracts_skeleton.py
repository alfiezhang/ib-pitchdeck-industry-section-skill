#!/usr/bin/env python3
"""Build material_extracts.json skeleton from a material manifest.

This artifact is a content-capture and LLM-extraction workspace. It is not a
claim that the material is evidence-ready.
"""

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
                "raw_text_available": False,
                "raw_text_path": "",
                "raw_text_extraction_status": "not_processed",
                "content_capture_status": "not_processed",
                "llm_extraction_status": "pending_llm_extraction",
                "extracted_facts": [],
                "extracted_metrics": [],
                "quoted_excerpts": [],
                "unknowns_or_conflicts": [],
                "claim_use_limitations": (
                    "Do not use until content is captured and a role LLM extracts facts/metrics/"
                    "quoted excerpts with locators and source type."
                ),
                "extraction_limitations": "not_processed",
                "can_be_used_as_evidence": False,
                "extracted_text_path": "",
                "evidence_snapshot": "",
            }
        )
    payload = {
        "schema_version": "material_extracts_v1",
        "artifact_semantics": (
            "Content capture plus LLM extraction workspace. Raw text availability does not mean evidence usability."
        ),
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
