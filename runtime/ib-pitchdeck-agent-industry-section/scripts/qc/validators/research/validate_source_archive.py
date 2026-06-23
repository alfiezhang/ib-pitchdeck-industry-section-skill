#!/usr/bin/env python3
"""Validate archived source snapshots for formal evidence sources."""

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
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts" / "_lib"
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

from json_utils import load_json_file
SCHEMA_VERSION = "source_archive_index_v1"
VALID_ARCHIVE_STATUSES = {
    "saved_html",
    "saved_text",
    "saved_pdf",
    "manual_verified_excerpt",
    "needs_research_verification",
    "search_snippet_only",
    "excerpt_snapshot",
    "archive_unavailable",
    "user_provided",
    "research_context",
}
VALID_VERIFICATION_METHODS = {
    "opened_original_url",
    "user_provided_pdf",
    "archived_copy_reviewed",
    "official_filing_reviewed",
    "manual_source_reviewed",
}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _load_archive_entries(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        data = load_json_file(path)
    except Exception as exc:
        return [], [f"cannot read source_archive_index.json: {exc}"]
    if not isinstance(data, dict):
        return [], ["source_archive_index.json must be a JSON object"]
    errors: list[str] = []
    if data.get("schema_version") and data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"source_archive_index.json schema_version must be {SCHEMA_VERSION}")
    entries = data.get("entries")
    if entries is None:
        entries = data.get("archive_entries")
    if not isinstance(entries, list):
        return [], errors + ["source_archive_index.json entries must be an array"]
    return [_canonical_archive_entry(item) for item in entries if isinstance(item, dict)], errors


def _first_present(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, list) and value:
            return value
        if value not in (None, ""):
            return value
    return None


def _canonical_archive_entry(entry: dict[str, Any]) -> dict[str, Any]:
    canonical = dict(entry)
    aliases = {
        "source_review_id": ("source_review_id", "review_id", "archive_id", "source_id"),
        "archive_status": ("archive_status", "snapshot_type", "status"),
        "archive_path": ("archive_path", "snapshot_path", "path"),
        "reviewed_excerpt": ("reviewed_excerpt", "excerpt", "raw_excerpt"),
        "archive_unavailable_reason": ("archive_unavailable_reason", "unavailable_reason", "reason"),
    }
    for target, keys in aliases.items():
        if target not in canonical or not _text(canonical.get(target)):
            value = _first_present(entry, keys)
            if value not in (None, ""):
                canonical[target] = value
    return canonical


def _resolve_archive_path(run_dir: Path, archive_path: str) -> Path:
    candidate = Path(archive_path)
    if candidate.is_absolute():
        return candidate
    return run_dir / archive_path


def _path_is_within_run(path: Path, run_dir: Path) -> bool:
    try:
        path.resolve().relative_to(run_dir.resolve())
        return True
    except Exception:
        return False


def _archive_reviewed_excerpt_text(text: str) -> str:
    """Return the human-reviewed excerpt body from a markdown archive snapshot."""
    marker = "## Reviewed Excerpt / Faithful Paraphrase"
    if marker not in text:
        return ""
    body = text.split(marker, 1)[1]
    if "## Archive Note" in body:
        body = body.split("## Archive Note", 1)[0]
    return body.strip()


def _entry_by_review_id(entries: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    by_id: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for idx, entry in enumerate(entries, start=1):
        source_review_id = _text(entry.get("source_review_id"))
        if not source_review_id:
            errors.append(f"entries[{idx}]: source_review_id is required")
            continue
        if source_review_id in by_id:
            errors.append(f"entries[{idx}]: duplicate source_review_id {source_review_id}")
            continue
        by_id[source_review_id] = entry
    return by_id, errors


def validate(
    *,
    source_archive_index_path: Path,
    run_dir: Path | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    run_root = run_dir or source_archive_index_path.parent.parent.parent

    if not source_archive_index_path.exists():
        return {
            "is_valid": False,
            "error_count": 1,
            "warning_count": 0,
            "errors": [f"missing required artifact: {source_archive_index_path}"],
            "warnings": [],
            "source_archive_index": str(source_archive_index_path),
        }

    entries, archive_errors = _load_archive_entries(source_archive_index_path)
    errors.extend(archive_errors)

    entries_by_id, entry_errors = _entry_by_review_id(entries)
    errors.extend(entry_errors)

    required_review_ids: set[str] = set(entries_by_id)
    evidence_ready_count = 0
    saved_count = 0
    unavailable_count = 0
    needs_verification_count = 0
    snippet_only_count = 0
    research_context_count = 0

    def validate_entry(
        *,
        review_id: str,
        entry: dict[str, Any],
    ) -> None:
        nonlocal evidence_ready_count, saved_count, unavailable_count, needs_verification_count, snippet_only_count, research_context_count
        entry_url = _text(entry.get("url"))
        if not entry_url:
            errors.append(f"{review_id}: source_archive entry requires url")
        status = _text(entry.get("archive_status"))
        if status not in VALID_ARCHIVE_STATUSES:
            errors.append(f"{review_id}: archive_status must be one of {sorted(VALID_ARCHIVE_STATUSES)}")
            return
        if status == "research_context":
            research_context_count += 1
            return
        if status == "user_provided":
            evidence_ready_count += 1
            return
        if status in {"saved_html", "saved_text", "saved_pdf", "manual_verified_excerpt", "needs_research_verification", "search_snippet_only", "excerpt_snapshot"}:
            archive_path = _text(entry.get("archive_path"))
            if not archive_path:
                errors.append(f"{review_id}: archive_path is required for archive_status={status}")
                return
            resolved = _resolve_archive_path(run_root, archive_path)
            if not _path_is_within_run(resolved, run_root):
                errors.append(f"{review_id}: archive_path must stay inside the run directory: {archive_path}")
                return
            if not resolved.exists():
                errors.append(f"{review_id}: archive_path does not exist: {archive_path}")
                return
            try:
                size = resolved.stat().st_size
            except OSError as exc:
                errors.append(f"{review_id}: cannot stat archive_path {archive_path}: {exc}")
                return
            minimum_size = 80 if status in {"manual_verified_excerpt", "needs_research_verification", "search_snippet_only", "excerpt_snapshot"} else 160
            if size < minimum_size:
                errors.append(f"{review_id}: archive file is too small to support later review: {archive_path}")
            if status in {"manual_verified_excerpt", "needs_research_verification", "search_snippet_only", "excerpt_snapshot"}:
                locator = _text(entry.get("locator"))
                reviewed_excerpt = _text(entry.get("reviewed_excerpt") or entry.get("excerpt"))
                if len(locator) < 8:
                    errors.append(
                        f"{review_id}: {status} requires a locator/page/section/table reference; "
                        "a URL/title-only archive is not enough."
                    )
                if len(reviewed_excerpt) < 40:
                    errors.append(
                        f"{review_id}: {status} requires reviewed_excerpt of at least 40 characters; "
                        "search snippets or title-only notes cannot become evidence."
                    )
                try:
                    archive_text = resolved.read_text(encoding="utf-8", errors="ignore")
                except OSError as exc:
                    errors.append(f"{review_id}: cannot read archive_path {archive_path}: {exc}")
                    return
                archived_excerpt = _archive_reviewed_excerpt_text(archive_text)
                if len(archived_excerpt) < 40:
                    errors.append(
                        f"{review_id}: archive file must contain a substantive Reviewed Excerpt / Faithful Paraphrase section; "
                        "metadata-only source snapshots are not acceptable."
                    )
            if status == "manual_verified_excerpt":
                verification = _text(entry.get("secondary_verification"))
                notes = _text(entry.get("secondary_verification_notes"))
                declared_status = _text(entry.get("research_archive_status"))
                verification_method = _text(entry.get("verification_method"))
                if declared_status != "manual_verified_excerpt":
                    errors.append(
                        f"{review_id}: manual_verified_excerpt requires research_archive_status=manual_verified_excerpt; "
                        "Research must explicitly make this judgment, not leave it to the archive builder"
                    )
                if verification != "verified":
                    errors.append(f"{review_id}: manual_verified_excerpt requires secondary_verification=verified")
                if verification_method not in VALID_VERIFICATION_METHODS:
                    errors.append(
                        f"{review_id}: manual_verified_excerpt requires verification_method one of {sorted(VALID_VERIFICATION_METHODS)}"
                    )
                if len(notes) < 30:
                    errors.append(f"{review_id}: manual_verified_excerpt requires secondary_verification_notes explaining how Research verified it")
                evidence_ready_count += 1
            elif status == "needs_research_verification":
                needs_verification_count += 1
            elif status == "search_snippet_only":
                snippet_only_count += 1
            elif status == "excerpt_snapshot":
                needs_verification_count += 1
                warnings.append(
                    f"{review_id}: archive_status=excerpt_snapshot is legacy/ambiguous; Research should rebuild as manual_verified_excerpt or needs_research_verification"
                )
            elif status in {"saved_html", "saved_text", "saved_pdf"}:
                evidence_ready_count += 1
            saved_count += 1
        elif status == "archive_unavailable":
            reason = _text(entry.get("archive_unavailable_reason"))
            excerpt = _text(entry.get("reviewed_excerpt") or entry.get("excerpt"))
            if len(reason) < 20:
                errors.append(f"{review_id}: archive_unavailable requires a specific archive_unavailable_reason")
            if len(excerpt) < 30:
                errors.append(f"{review_id}: archive_unavailable requires reviewed_excerpt with enough audit context")
            unavailable_count += 1

    for review_id, entry in entries_by_id.items():
        validate_entry(review_id=review_id, entry=entry)

    if required_review_ids and evidence_ready_count == 0:
        warnings.append(
            "no formal source is evidence-ready yet; Research must complete full-page archive or secondary verification before Knowledge promotes evidence"
        )
    if unavailable_count:
        warnings.append(f"{unavailable_count} usable formal source archive(s) are marked archive_unavailable")
    if needs_verification_count:
        warnings.append(f"{needs_verification_count} source archive(s) need Research secondary verification before evidence promotion")
    if snippet_only_count:
        warnings.append(f"{snippet_only_count} source archive(s) are search_snippet_only and must remain leads, not evidence")

    return {
        "is_valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "source_archive_index": str(source_archive_index_path),
        "required_source_count": len(required_review_ids),
        "saved_archive_count": saved_count,
        "evidence_ready_archive_count": evidence_ready_count,
        "archive_unavailable_count": unavailable_count,
        "needs_research_verification_count": needs_verification_count,
        "search_snippet_only_count": snippet_only_count,
        "research_context_count": research_context_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-archive-index", required=True)
    parser.add_argument("--run-dir")
    parser.add_argument("--output")
    args = parser.parse_args()

    result = validate(
        source_archive_index_path=Path(args.source_archive_index),
        run_dir=Path(args.run_dir) if args.run_dir else None,
    )
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["is_valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
