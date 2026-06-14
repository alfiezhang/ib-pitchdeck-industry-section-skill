#!/usr/bin/env python3
"""Delete or update a canonical S-xxx search attempt in search_log.md.

This is a mechanical search-log editor. It does not decide source quality or
whether a search should count as evidence. Use it when an agent accidentally
created the wrong S-xxx row, or when a known field such as Result Count needs a
deterministic correction.
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
import re
from pathlib import Path
from typing import Any


SEARCH_HEADING_RE = re.compile(
    r"^###\s+(?:Search\s+)?(?:#?\s*)?(?:S-?)?(\d+)\b.*?$",
    flags=re.MULTILINE | re.IGNORECASE,
)
FIELD_RE = re.compile(r"^-\s+\*\*(?P<label>[^*]+)\*\*:\s*(?P<value>.*)$")


def _attempt_no(value: str) -> int:
    text = str(value or "").strip().upper().replace("S-", "")
    try:
        return int(text)
    except Exception as exc:
        raise argparse.ArgumentTypeError(f"invalid S-xxx attempt id: {value}") from exc


def _split_blocks(text: str) -> tuple[str, list[tuple[int, int, int]]]:
    matches = list(SEARCH_HEADING_RE.finditer(text))
    blocks: list[tuple[int, int, int]] = []
    for idx, match in enumerate(matches):
        attempt_no = int(match.group(1))
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        blocks.append((attempt_no, start, end))
    prefix = text[: matches[0].start()] if matches else text
    return prefix, blocks


def delete_attempt(text: str, attempt_no: int) -> tuple[str, bool]:
    _, blocks = _split_blocks(text)
    for number, start, end in blocks:
        if number != attempt_no:
            continue
        updated = text[:start].rstrip() + "\n\n" + text[end:].lstrip()
        return updated.rstrip() + "\n", True
    return text, False


def update_attempt_fields(text: str, attempt_no: int, updates: dict[str, str]) -> tuple[str, bool, list[str]]:
    _, blocks = _split_blocks(text)
    for number, start, end in blocks:
        if number != attempt_no:
            continue
        block = text[start:end]
        lines = block.splitlines()
        seen: set[str] = set()
        output: list[str] = []
        for line in lines:
            match = FIELD_RE.match(line)
            if not match:
                output.append(line)
                continue
            label = match.group("label").strip()
            key = label.lower()
            if key in updates:
                output.append(f"- **{label}**: {updates[key]}")
                seen.add(key)
            else:
                output.append(line)
        missing = [key for key in updates if key not in seen]
        for key in missing:
            label = " ".join(part.capitalize() for part in key.split())
            output.append(f"- **{label}**: {updates[key]}")
        updated = text[:start] + "\n".join(output).rstrip() + "\n" + text[end:]
        return updated, True, missing
    return text, False, []


def _parse_set_field(values: list[str]) -> dict[str, str]:
    updates: dict[str, str] = {}
    for raw in values:
        if "=" not in raw:
            raise argparse.ArgumentTypeError("--set-field must use Label=Value")
        label, value = raw.split("=", 1)
        label = label.strip().strip("*").lower()
        if not label:
            raise argparse.ArgumentTypeError("--set-field label cannot be empty")
        updates[label] = value.strip()
    return updates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search-log", required=True, help="Path to artifacts/search_log.md")
    parser.add_argument("--attempt-id", required=True, type=_attempt_no, help="S-xxx id, e.g. S-023 or 23")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--delete", action="store_true", help="Delete the selected S-xxx block.")
    mode.add_argument(
        "--set-field",
        action="append",
        default=[],
        help="Update a markdown field in the selected block, e.g. 'Result Count=5'. May be repeated.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    path = Path(args.search_log)
    text = path.read_text(encoding="utf-8")
    if args.delete:
        updated, found = delete_attempt(text, args.attempt_id)
        missing_fields: list[str] = []
        action = "delete"
    else:
        updates = _parse_set_field(args.set_field)
        updated, found, missing_fields = update_attempt_fields(text, args.attempt_id, updates)
        action = "update"

    if not found:
        raise SystemExit(f"S-{args.attempt_id:03d} not found in {path}")
    if not args.dry_run:
        path.write_text(updated, encoding="utf-8")
    print(
        json.dumps(
            {
                "is_valid": True,
                "action": action,
                "search_log": str(path),
                "attempt_id": f"S-{args.attempt_id:03d}",
                "dry_run": bool(args.dry_run),
                "appended_missing_fields": missing_fields,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
