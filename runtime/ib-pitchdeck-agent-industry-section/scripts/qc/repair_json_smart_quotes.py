#!/usr/bin/env python3
"""Safely repair malformed JSON files that use smart/Chinese quotes.

The repair is conservative:
- If the original file is already valid JSON, it is not changed.
- Smart/fullwidth quotes are normalized only in a candidate copy.
- The candidate must parse as JSON before anything is written.
- Written output is canonical JSON produced by json.dumps, not hand-patched text.
"""

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
import sys
from pathlib import Path
from typing import Any

from json_utils import replace_smart_quotes, smart_quote_locations


def discover(paths: list[str]) -> list[Path]:
    found: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            found.extend(sorted(path.rglob("*.json")))
        else:
            found.append(path)
    return found


def repair_file(path: Path, *, in_place: bool, output_dir: Path | None) -> dict[str, Any]:
    item: dict[str, Any] = {
        "path": str(path),
        "is_valid_before": False,
        "smart_quote_count": 0,
        "repaired": False,
        "output_path": "",
        "error": "",
    }
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        item["error"] = f"cannot read file: {exc}"
        return item

    locations = smart_quote_locations(text)
    item["smart_quote_count"] = len(locations)
    item["smart_quotes"] = locations[:20]

    try:
        json.loads(text)
        item["is_valid_before"] = True
        return item
    except json.JSONDecodeError as original_exc:
        item["original_error"] = str(original_exc)

    candidate = replace_smart_quotes(text)
    if candidate == text:
        item["error"] = "file is invalid JSON, but no smart/fullwidth quote characters were detected"
        return item

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as repaired_exc:
        item["error"] = (
            "smart quote normalization did not produce valid JSON; rebuild the JSON from a structured object. "
            f"Parse error after normalization: {repaired_exc}"
        )
        return item

    output_text = json.dumps(parsed, ensure_ascii=False, indent=2) + "\n"
    if in_place:
        target = path
    elif output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / path.name
    else:
        item["error"] = "repair possible, but neither --in-place nor --output-dir was provided"
        return item

    try:
        target.write_text(output_text, encoding="utf-8")
    except Exception as exc:
        item["error"] = f"cannot write repaired JSON: {exc}"
        return item

    item["repaired"] = True
    item["output_path"] = str(target)
    return item


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely repair JSON files malformed by smart/Chinese quotes.")
    parser.add_argument("paths", nargs="+", help="JSON files or directories to inspect.")
    parser.add_argument("--in-place", action="store_true", help="Overwrite repairable files in place.")
    parser.add_argument("--output-dir", help="Write repaired files to this directory instead of overwriting.")
    parser.add_argument("--report", help="Optional JSON report path.")
    args = parser.parse_args()

    if args.in_place and args.output_dir:
        parser.error("use only one of --in-place or --output-dir")

    files = discover(args.paths)
    results = [
        repair_file(path, in_place=args.in_place, output_dir=Path(args.output_dir) if args.output_dir else None)
        for path in files
    ]
    failed = [item for item in results if item.get("error")]
    report = {
        "schema_version": "json_smart_quote_repair_v1",
        "checked_count": len(results),
        "repaired_count": sum(1 for item in results if item.get("repaired")),
        "failed_count": len(failed),
        "is_valid": not failed,
        "files": results,
    }

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
