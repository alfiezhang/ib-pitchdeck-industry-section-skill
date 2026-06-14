#!/usr/bin/env python3
"""Retrieve candidate source rows from the cross-project repository."""

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

from repository_common import as_list, load_jsonl_records, repository_root_default, text


def _match_row(row: dict[str, Any], query: dict[str, Any]) -> bool:
    source_type = text(row.get("source_type"))
    if query.get("source_type"):
        if source_type and source_type != text(query["source_type"]):
            return False
    if query.get("normalized_key"):
        if text(row.get("normalized_key")) != text(query["normalized_key"]):
            return False
    if query.get("geography"):
        if text(row.get("geography")) != text(query["geography"]):
            return False
    if query.get("time_period"):
        if text(row.get("time_period")) != text(query["time_period"]):
            return False
    if query.get("source_hash"):
        if text(row.get("source_hash")) != text(query["source_hash"]):
            return False

    tags = {text(tag).lower() for tag in as_list(row.get("industry_tags"))}
    query_tags = {text(tag).lower() for tag in as_list(query.get("industry_tags"))}
    if query_tags and not query_tags.issubset(tags):
        return False

    if query.get("contains_text"):
        snippet = text(query["contains_text"]).lower()
        if snippet and snippet not in text(row.get("source_title")).lower():
            return False
    return True


def retrieve(
    *,
    repository_root: Path,
    query: dict[str, Any],
    max_results: int | None = None,
    output: Path | None = None,
) -> dict[str, Any]:
    repository_jsonl = repository_root / "index" / "research_repository.jsonl"
    rows = [row for row in load_jsonl_records(repository_jsonl) if _match_row(row, query)]
    rows.sort(key=lambda item: text(item.get("imported_at")), reverse=True)
    if max_results and max_results > 0:
        rows = rows[:max_results]
    result = {"schema_version": "repository_retrieval_v1", "query": query, "count": len(rows), "sources": rows}
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=str(repository_root_default()))
    parser.add_argument("--query", help="JSON string query")
    parser.add_argument("--source-type", default="")
    parser.add_argument("--industry-tag", action="append", default=[])
    parser.add_argument("--geography", default="")
    parser.add_argument("--time-period", default="")
    parser.add_argument("--max-results", type=int, default=50)
    parser.add_argument("--output")
    args = parser.parse_args()

    query: dict[str, Any] = {}
    if args.query:
        query.update(json.loads(args.query))
    if args.source_type:
        query["source_type"] = args.source_type
    if args.industry_tag:
        query["industry_tags"] = args.industry_tag
    if args.geography:
        query["geography"] = args.geography
    if args.time_period:
        query["time_period"] = args.time_period

    retrieve(
        repository_root=Path(args.repository_root),
        query=query,
        max_results=args.max_results if args.max_results > 0 else None,
        output=Path(args.output) if args.output else None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
