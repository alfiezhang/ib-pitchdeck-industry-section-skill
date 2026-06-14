#!/usr/bin/env python3
"""Validate repository artifacts and return normalized repair hints."""

from __future__ import annotations

# Runtime scripts can be run directly. Shared helpers remain in runtime
# `scripts/`; production tools live under role scripts; validators live under QC.
import sys as _ib_sys
from pathlib import Path as _IbPath
_IB_ROLE_SCRIPT_DIR = _IbPath(__file__).resolve().parent
_IB_RUNTIME_ROOT = next(
    _p for _p in _IbPath(__file__).resolve().parents
    if (_p / 'configs').is_dir() and (_p / 'scripts').is_dir()
)
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts"
_IB_ROLE_SCRIPT_DIRS = sorted(_p for _p in (_IB_RUNTIME_ROOT / 'scripts').iterdir() if _p.is_dir())
_IB_QC_VALIDATOR_DIRS = sorted((_IB_RUNTIME_ROOT / 'scripts' / 'qc' / 'validators').glob('*'))
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

from repository_common import load_fingerprints, load_jsonl_records, repository_root_default, text


def _as_bool(value: Any) -> bool:
    return bool(value is True)


def validate(repository_root: Path) -> dict[str, Any]:
    repository_jsonl = repository_root / "index" / "research_repository.jsonl"
    index_path = repository_root / "index" / "source_fingerprints.json"
    source_root = repository_root / "sources"

    errors: list[str] = []
    warnings: list[str] = []

    if not repository_jsonl.exists():
        errors.append("research_repository.jsonl missing")
    if not index_path.exists():
        errors.append("source_fingerprints.json missing")
    if not source_root.exists():
        warnings.append("sources directory missing; new ingests should create it")

    rows = load_jsonl_records(repository_jsonl) if repository_jsonl.exists() else []
    index_payload = load_fingerprints(index_path) if index_path.exists() else {}
    row_ids = set()
    for idx, row in enumerate(rows, start=1):
        source_id = text(row.get("source_id"))
        if not source_id:
            errors.append(f"row {idx} missing source_id")
            continue
        if source_id in row_ids:
            errors.append(f"duplicate source_id in jsonl: {source_id}")
        row_ids.add(source_id)

        for required in ("source_hash", "normalized_key", "source_type", "text_snapshot_path", "imported_at"):
            if not text(row.get(required)):
                errors.append(f"{source_id}: missing required field {required}")
        snapshot_path = Path(text(row.get("text_snapshot_path")))
        if snapshot_path and not snapshot_path.exists():
            warnings.append(f"{source_id}: snapshot path not found {snapshot_path}")

    index_sources = index_payload.get("sources") if isinstance(index_payload.get("sources"), dict) else {}
    by_hash = index_payload.get("by_source_hash") if isinstance(index_payload.get("by_source_hash"), dict) else {}
    by_key = index_payload.get("by_normalized_key") if isinstance(index_payload.get("by_normalized_key"), dict) else {}
    missing_from_jsonl = [str(source_id) for source_id in index_sources if str(source_id) not in row_ids]
    if missing_from_jsonl:
        warnings.append(f"index lists sources not present in jsonl: {', '.join(sorted(missing_from_jsonl))}")

    duplicate_mappings = any(len(v) > 1 for v in by_hash.values()) or any(len(v) > 1 for v in by_key.values())
    if duplicate_mappings:
        warnings.append("fingerprint mappings contain duplicate assignments")

    result = {
        "schema_version": "repository_validation_v1",
        "errors": errors,
        "warnings": warnings,
        "is_valid": not errors,
        "record_count": len(rows),
        "index_source_count": len(index_sources),
        "duplicate_mappings": duplicate_mappings,
        "snapshot_dir_exists": source_root.exists(),
        "repository_jsonl": repository_jsonl.as_posix(),
        "source_fingerprints": index_path.as_posix(),
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=str(repository_root_default()))
    parser.add_argument("--output")
    args = parser.parse_args()

    result = validate(Path(args.repository_root))
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["is_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
