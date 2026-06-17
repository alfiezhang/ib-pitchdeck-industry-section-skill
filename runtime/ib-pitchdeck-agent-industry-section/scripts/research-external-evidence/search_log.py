#!/usr/bin/env python3
"""Append, update, or delete canonical S-xxx search attempts in search_log.md."""

from __future__ import annotations

# Runtime scripts can be run directly. Shared helpers remain in runtime
# `scripts/`; production tools live under role scripts; validators live under QC.
import sys as _ib_sys
from pathlib import Path as _IbPath

_IB_ROLE_SCRIPT_DIR = _IbPath(__file__).resolve().parent
_IB_RUNTIME_ROOT = next(
    _p for _p in _IbPath(__file__).resolve().parents
    if (_p / "configs").is_dir() and (_p / "scripts").is_dir()
)
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts" / "_lib"
_IB_ROLE_SCRIPT_DIRS = sorted(_p for _p in (_IB_RUNTIME_ROOT / "scripts").iterdir() if _p.is_dir())
_IB_QC_VALIDATOR_DIRS = sorted((_IB_RUNTIME_ROOT / "scripts" / "qc" / "validators").glob("*"))
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


SEARCH_HEADING_RE = re.compile(
    r"^###\s+(?:Search\s+)?(?:#?\s*)?(?:S-?)?(\d+)\b.*?$",
    flags=re.MULTILINE | re.IGNORECASE,
)
FIELD_RE = re.compile(r"^-\s+\*\*(?P<label>[^*]+)\*\*:\s*(?P<value>.*)$")


BASE_LOG = """# Search Log

> Written incrementally during the research phase. `FS-xxx` IDs are planned search instructions; `S-xxx` IDs are real executed search attempts.

## Research Configuration

Research As-Of Date:

---

## Search Attempts
"""


def _split_csv(values: list[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        for item in str(value or "").split(","):
            item = item.strip()
            if item:
                output.append(item)
    return output


def _next_attempt_number(text: str) -> int:
    numbers = [int(match.group(1)) for match in SEARCH_HEADING_RE.finditer(text)]
    return max(numbers, default=0) + 1


def _line(label: str, value: str) -> str:
    return f"- **{label}**: {value}".rstrip()


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


def build_block(args: argparse.Namespace, attempt_no: int) -> str:
    fs_ids = ", ".join(_split_csv(args.fs_id or []))
    selected_sources = ", ".join(_split_csv(args.selected_source or []))
    source_review_ids = ", ".join(_split_csv(args.source_review_id or []))
    archive_paths = ", ".join(_split_csv(args.source_archive_path or []))
    lead_only = ", ".join(_split_csv(args.lead_only_source or []))
    rejected = "; ".join(_split_csv(args.rejected_source or []))

    lines = [
        "",
        f"### Search {attempt_no}",
        _line("Query", args.query),
        _line("Provider", args.provider),
        _line("Site / Domain Constraint", args.domain_constraint or ""),
        _line("Source Pack", args.source_pack or ""),
        _line("Search Stage", args.stage),
        _line("Search Instruction IDs", fs_ids),
        _line("Mode", args.mode),
        _line("Dimension", args.dimension or ""),
        _line("Selected Source Reason", args.selected_source_reason or ""),
        _line("Result Count", str(args.result_count if args.result_count is not None else "")),
        _line("Selected Sources", selected_sources),
        _line("Opened / Reviewed", args.opened_reviewed),
        _line("Source Locator / Raw Excerpt", args.locator_excerpt or ""),
        _line("Source Review IDs", source_review_ids),
        _line("Source Archive IDs / Paths", archive_paths),
        _line("Lead-only Sources", lead_only),
        _line("Rejected Sources (with reason)", rejected),
        _line("Notes", args.notes or ""),
    ]
    return "\n".join(lines) + "\n"


def append_attempt(args: argparse.Namespace) -> int:
    path = Path(args.search_log)
    if path.exists():
        text = path.read_text(encoding="utf-8")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = BASE_LOG
    if "## Search Attempts" not in text:
        text = text.rstrip() + "\n\n## Search Attempts\n"

    attempt_no = _next_attempt_number(text)
    updated = text.rstrip() + "\n" + build_block(args, attempt_no)
    path.write_text(updated, encoding="utf-8")
    print(f"S-{attempt_no:03d}")
    return 0


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


def edit_attempt(args: argparse.Namespace) -> int:
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    append = subparsers.add_parser("append", help="Append a real executed search attempt.")
    append.add_argument("--search-log", required=True, help="Path to artifacts/search_log.md")
    append.add_argument("--query", required=True)
    append.add_argument("--provider", default="WebSearch")
    append.add_argument(
        "--stage",
        required=True,
        choices=("broad_discovery", "source_planning", "formal_research_execution", "latest_check", "peer_check"),
        help="Research phase for this actual search attempt.",
    )
    append.add_argument("--fs-id", action="append", help="Planned FS-xxx instruction ID. May be repeated or comma-separated.")
    append.add_argument("--selected-source", action="append", help="Exact selected URL. May be repeated or comma-separated.")
    append.add_argument("--result-count", type=int)
    append.add_argument("--opened-reviewed", default="no", choices=("yes", "no"))
    append.add_argument("--locator-excerpt", default="")
    append.add_argument("--source-review-id", action="append")
    append.add_argument("--source-archive-path", action="append")
    append.add_argument("--lead-only-source", action="append")
    append.add_argument("--rejected-source", action="append")
    append.add_argument("--dimension", default="")
    append.add_argument("--selected-source-reason", default="")
    append.add_argument("--domain-constraint", default="")
    append.add_argument("--source-pack", default="")
    append.add_argument("--mode", default="unrestricted")
    append.add_argument("--notes", default="")
    append.set_defaults(func=append_attempt)

    edit = subparsers.add_parser("edit", help="Update or delete one S-xxx search attempt.")
    edit.add_argument("--search-log", required=True, help="Path to artifacts/search_log.md")
    edit.add_argument("--attempt-id", required=True, type=_attempt_no, help="S-xxx id, e.g. S-023 or 23")
    mode = edit.add_mutually_exclusive_group(required=True)
    mode.add_argument("--delete", action="store_true", help="Delete the selected S-xxx block.")
    mode.add_argument(
        "--set-field",
        action="append",
        default=[],
        help="Update a markdown field in the selected block, e.g. 'Result Count=5'. May be repeated.",
    )
    edit.add_argument("--dry-run", action="store_true")
    edit.set_defaults(func=edit_attempt)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
