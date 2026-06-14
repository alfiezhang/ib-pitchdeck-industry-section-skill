#!/usr/bin/env python3
"""Append one canonical S-xxx search attempt to artifacts/search_log.md."""

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
import re
from pathlib import Path


SEARCH_HEADING_RE = re.compile(
    r"^###\s+(?:Search\s+)?(?:#?\s*)?(?:S-?)?(\d+)\b.*?$",
    flags=re.MULTILINE | re.IGNORECASE,
)


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search-log", required=True, help="Path to artifacts/search_log.md")
    parser.add_argument("--query", required=True)
    parser.add_argument("--provider", default="WebSearch")
    parser.add_argument(
        "--stage",
        required=True,
        choices=("broad_discovery", "source_planning", "formal_research_execution", "latest_check", "peer_check"),
        help="Research phase for this actual search attempt.",
    )
    parser.add_argument("--fs-id", action="append", help="Planned FS-xxx instruction ID. May be repeated or comma-separated.")
    parser.add_argument("--selected-source", action="append", help="Exact selected URL. May be repeated or comma-separated.")
    parser.add_argument("--result-count", type=int)
    parser.add_argument("--opened-reviewed", default="no", choices=("yes", "no"))
    parser.add_argument("--locator-excerpt", default="")
    parser.add_argument("--source-review-id", action="append")
    parser.add_argument("--source-archive-path", action="append")
    parser.add_argument("--lead-only-source", action="append")
    parser.add_argument("--rejected-source", action="append")
    parser.add_argument("--dimension", default="")
    parser.add_argument("--selected-source-reason", default="")
    parser.add_argument("--domain-constraint", default="")
    parser.add_argument("--source-pack", default="")
    parser.add_argument("--mode", default="unrestricted")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

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


if __name__ == "__main__":
    raise SystemExit(main())
