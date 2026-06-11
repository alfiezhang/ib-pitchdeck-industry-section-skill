#!/usr/bin/env python3
"""Detect duplicate entries already in the repository index."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from repository_common import load_fingerprints, load_jsonl_records, repository_root_default, text


def dedupe(repository_root: Path) -> dict[str, Any]:
    repository_jsonl = repository_root / "index" / "research_repository.jsonl"
    index_path = repository_root / "index" / "source_fingerprints.json"

    by_hash: dict[str, list[str]] = defaultdict(list)
    by_key: dict[str, list[str]] = defaultdict(list)
    for row in load_jsonl_records(repository_jsonl):
        source_id = text(row.get("source_id"))
        if not source_id:
            continue
        by_hash[text(row.get("source_hash"))].append(source_id)
        by_key[text(row.get("normalized_key"))].append(source_id)

    duplicate_hash_groups = [
        {"kind": "source_hash", "value": key, "source_ids": ids, "count": len(ids)}
        for key, ids in by_hash.items()
        if key and len(ids) > 1
    ]
    duplicate_key_groups = [
        {"kind": "normalized_key", "value": key, "source_ids": ids, "count": len(ids)}
        for key, ids in by_key.items()
        if key and len(ids) > 1
    ]

    index_payload = load_fingerprints(index_path)
    index_sources = index_payload.get("sources") if isinstance(index_payload.get("sources"), dict) else {}
    missing_in_index = []
    valid_source_ids = set(index_sources)
    for row in load_jsonl_records(repository_jsonl):
        source_id = text(row.get("source_id"))
        if source_id and source_id not in valid_source_ids:
            missing_in_index.append(source_id)

    duplicate_count = len(duplicate_hash_groups) + len(duplicate_key_groups)
    result = {
        "schema_version": "repository_dedupe_v1",
        "duplicate_groups": duplicate_hash_groups + duplicate_key_groups,
        "duplicate_group_count": duplicate_count,
        "missing_from_index": sorted(set(missing_in_index)),
        "is_valid": duplicate_count == 0 and not missing_in_index,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=str(repository_root_default()))
    args = parser.parse_args()

    result = dedupe(Path(args.repository_root))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["is_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
