#!/usr/bin/env python3
"""Validate material_manifest.json for the Material Intake role."""

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
from source_classification import CANONICAL_SOURCE_TYPES, normalize_source_type


def text(value: Any) -> str:
    return str(value or "").strip()


def validate_manifest(payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("schema_version") != "material_manifest_v1":
        errors.append("schema_version must be material_manifest_v1")
    materials = payload.get("materials")
    if not isinstance(materials, list):
        errors.append("materials must be an array")
        return errors, warnings
    seen: set[str] = set()
    for idx, item in enumerate(materials, start=1):
        if not isinstance(item, dict):
            errors.append(f"materials[{idx}] must be an object")
            continue
        material_id = text(item.get("material_id"))
        if not material_id:
            errors.append(f"materials[{idx}].material_id is required")
        elif material_id in seen:
            errors.append(f"duplicate material_id: {material_id}")
        seen.add(material_id)
        source_type = text(item.get("source_type"))
        if not source_type:
            errors.append(f"{material_id or idx}: source_type is required")
        elif normalize_source_type(source_type) not in CANONICAL_SOURCE_TYPES:
            warnings.append(f"{material_id or idx}: source_type normalized to other")
        if not text(item.get("material_kind")):
            errors.append(f"{material_id or idx}: material_kind is required")
        if not text(item.get("file_path_or_url")):
            errors.append(f"{material_id or idx}: file_path_or_url is required")
        if not text(item.get("source_access")):
            warnings.append(f"{material_id or idx}: source_access is recommended")
        if not text(item.get("extraction_status")):
            warnings.append(f"{material_id or idx}: extraction_status is required (pending/complete/failed)")
        if "extraction_limitations" not in item:
            warnings.append(f"{material_id or idx}: extraction_limitations is required")
        if text(item.get("locator")) and text(item.get("file_path_or_url")) == "inline_user_text":
            warnings.append(f"{material_id or idx}: locator should not replace file_path_or_url for text material")
        if text(item.get("file_path_or_url")) == "inline_user_text" and normalize_source_type(source_type) != "project_specific_material":
            errors.append(f"{material_id or idx}: inline_user_text must be project_specific_material, not {source_type}")
        if text(item.get("source_type")) == "user_curated_industry_report" and text(item.get("can_be_used_as_evidence")) == "true":
            warnings.append(f"{material_id or idx}: user_curated_industry_report should remain false until formal review")
    if not materials:
        warnings.append("material_manifest has no materials; direct input_card transcription may still be possible")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--material-manifest", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    path = Path(args.material_manifest)
    try:
        payload = load_json_file(path)
        errors, warnings = validate_manifest(payload)
    except Exception as exc:
        errors, warnings = [f"cannot read material manifest: {exc}"], []
    result = {
        "is_valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "repair_plan": {
            "primary_repair_target": "artifacts/material_manifest.json",
            "repair_target_role": "material-intake",
        } if errors else {},
    }
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["is_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
