#!/usr/bin/env python3
"""Validate repository artifacts and return normalized repair hints."""

from __future__ import annotations

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
