#!/usr/bin/env python3
"""Validate JSON files and report smart/Chinese quote errors clearly."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from json_utils import load_json_file, smart_quote_locations


DEFAULT_EXCLUDES = {".git", ".venv", "venv", "dist", "__pycache__", ".claude"}


def discover_json_files(root: Path, include_ignored_outputs: bool) -> list[Path]:
    paths = []
    excludes = set(DEFAULT_EXCLUDES)
    if not include_ignored_outputs:
        excludes.add("runs")
    for path in root.rglob("*.json"):
        if any(part in excludes for part in path.parts):
            continue
        paths.append(path)
    return sorted(paths)


def check_file(path: Path) -> dict:
    text = ""
    try:
        text = path.read_text(encoding="utf-8")
        load_json_file(path)
    except Exception as exc:
        return {
            "path": str(path),
            "is_valid": False,
            "error": str(exc),
            "smart_quotes": smart_quote_locations(text) if text else [],
        }
    return {"path": str(path), "is_valid": True, "error": "", "smart_quotes": []}


def main() -> None:
    parser = argparse.ArgumentParser(description="Check JSON files with smart-quote diagnostics.")
    parser.add_argument("paths", nargs="*", help="JSON files or directories to check.")
    parser.add_argument("--root", default=".", help="Root to search when no paths are provided.")
    parser.add_argument("--include-runs", action="store_true", help="Include ignored run outputs.")
    parser.add_argument("--output", help="Optional JSON report path.")
    args = parser.parse_args()

    targets: list[Path] = []
    if args.paths:
        for raw in args.paths:
            path = Path(raw)
            if path.is_dir():
                targets.extend(discover_json_files(path, include_ignored_outputs=True))
            else:
                targets.append(path)
    else:
        targets = discover_json_files(Path(args.root), args.include_runs)

    results = [check_file(path) for path in targets]
    failed = [item for item in results if not item["is_valid"]]
    report = {
        "checked_count": len(results),
        "failed_count": len(failed),
        "is_valid": not failed,
        "files": results,
    }

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
