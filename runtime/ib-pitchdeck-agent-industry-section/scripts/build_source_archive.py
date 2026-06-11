#!/usr/bin/env python3
"""Build source_archive excerpt snapshots from source_reviews.json."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from json_utils import load_json_file
from source_classification import is_material_type, normalize_source_type


SRC_RE = re.compile(r"^SRC-\d{3}$")


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _is_user_source(review: dict[str, Any]) -> bool:
    source_type = normalize_source_type(review.get("source_type"))
    if is_material_type(source_type):
        return True
    if _text(review.get("source_access")).strip().lower() == "user_provided":
        return True
    value = _text(review.get("url"))
    return value.strip().lower() in {"user-provided", "user provided", "input_card", "management", "company/user-provided"}


def _first_present(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, bool):
            return value
        if isinstance(value, list) and value:
            return value
        if value not in (None, ""):
            return value
    return None


def _canonical_review(review: dict[str, Any]) -> dict[str, Any]:
    canonical = dict(review)
    aliases = {
        "source_review_id": ("source_review_id", "review_id", "source_id", "id"),
        "url": ("url", "source_url", "source", "source_link"),
        "title": ("title", "source_title", "source_name", "name"),
        "locator": ("locator", "source_locator", "location", "source_location"),
        "excerpt": ("excerpt", "raw_excerpt", "reviewed_excerpt", "source_excerpt"),
        "evidence_ids": ("evidence_ids", "ev_ids"),
    }
    for target, keys in aliases.items():
        if target not in canonical or not _text(canonical.get(target)):
            value = _first_present(review, keys)
            if value not in (None, ""):
                canonical[target] = value
    return canonical


def _load_reviews(path: Path) -> list[dict[str, Any]]:
    data = load_json_file(path)
    if isinstance(data, list):
        raw = data
    elif isinstance(data, dict):
        raw = data.get("reviews") if "reviews" in data else data.get("source_reviews", [])
    else:
        raw = []
    return [_canonical_review(item) for item in raw if isinstance(item, dict)]


def _review_is_usable(review: dict[str, Any]) -> bool:
    usable = review.get("usable_as_evidence")
    if isinstance(usable, bool):
        return usable
    status = str(review.get("evidence_status") or review.get("status") or "").strip().lower()
    return status in {"primary-reviewed", "secondary-reviewed", "reviewed", "usable"}


def _markdown_snapshot(review: dict[str, Any], captured_at: str) -> str:
    source_review_id = _text(review.get("source_review_id"))
    title = _text(review.get("title")) or source_review_id
    url = _text(review.get("url"))
    locator = _text(review.get("locator"))
    excerpt = _text(review.get("excerpt"))
    limitations = _text(review.get("limitations"))
    evidence_ids = ", ".join(_text(item) for item in _as_list(review.get("evidence_ids")) if _text(item))
    methodology = _text(review.get("methodology_locator"))
    original_url = _text(review.get("original_url"))

    lines = [
        f"# {source_review_id} Source Archive Snapshot",
        "",
        f"- Source Review ID: {source_review_id}",
        f"- Title: {title}",
        f"- URL: {url}",
        f"- Captured At: {captured_at}",
        f"- Archive Status: excerpt_snapshot",
        f"- Locator: {locator}",
        f"- Evidence IDs: {evidence_ids}",
    ]
    if original_url:
        lines.append(f"- Original URL: {original_url}")
    if methodology:
        lines.append(f"- Methodology Locator: {methodology}")
    if limitations:
        lines.append(f"- Limitations: {limitations}")
    lines.extend(
        [
            "",
            "## Reviewed Excerpt / Faithful Paraphrase",
            "",
            excerpt,
            "",
            "## Archive Note",
            "",
            "This file was generated from source_reviews.json as an excerpt_snapshot. It preserves the reviewed URL, locator, excerpt/paraphrase, evidence linkage, and limitations for downstream audit. It is not a full-page scrape unless explicitly replaced by a saved_text or saved_pdf archive.",
            "",
        ]
    )
    return "\n".join(lines)


def _relative_archive_path(run_dir: Path, archive_file: Path) -> str:
    try:
        return str(archive_file.resolve().relative_to(run_dir.resolve()))
    except Exception:
        return str(archive_file)


def build_archive(
    *,
    source_reviews_path: Path,
    archive_dir: Path,
    source_archive_index_path: Path,
    run_dir: Path,
    overwrite: bool,
) -> dict[str, Any]:
    captured_at = datetime.now().astimezone().isoformat(timespec="seconds")
    reviews = _load_reviews(source_reviews_path)
    archive_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    skipped: list[str] = []
    written: list[str] = []

    for review in reviews:
        source_review_id = _text(review.get("source_review_id"))
        url = _text(review.get("url"))
        if not source_review_id or not SRC_RE.fullmatch(source_review_id):
            skipped.append(source_review_id or "(missing SRC ID)")
            continue
        if not _review_is_usable(review):
            skipped.append(source_review_id)
            continue

        archive_status = "excerpt_snapshot"
        archive_path = ""
        if _is_user_source(review):
            archive_status = "user_provided"
        else:
            archive_file = archive_dir / f"{source_review_id}.md"
            if overwrite or not archive_file.exists():
                archive_file.write_text(_markdown_snapshot(review, captured_at), encoding="utf-8")
                written.append(str(archive_file))
            archive_path = str(archive_file)
        entries.append(
            {
                "source_review_id": source_review_id,
                "url": url,
                "title": _text(review.get("title")),
                "archive_status": archive_status,
                "archive_path": archive_path if archive_status == "user_provided" else _relative_archive_path(run_dir, Path(archive_path)),
                "captured_at": captured_at,
                "source_type": normalize_source_type(review.get("source_type")),
                "locator": _text(review.get("locator")),
                "reviewed_excerpt": _text(review.get("excerpt")),
                "archive_unavailable_reason": "",
            }
        )

    index = {
        "schema_version": "source_archive_index_v1",
        "created_at": captured_at,
        "purpose": "Archive reviewable snapshots for formal usable evidence sources. Generated from source_reviews.json by build_source_archive.py.",
        "entries": entries,
    }
    source_archive_index_path.parent.mkdir(parents=True, exist_ok=True)
    source_archive_index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "is_valid": True,
        "source_review_count": len(reviews),
        "archive_entry_count": len(entries),
        "written_snapshot_count": len(written),
        "skipped_review_ids": skipped,
        "source_archive_index": str(source_archive_index_path),
    }


def _default_paths(source_reviews_path: Path, run_dir_arg: str | None) -> tuple[Path, Path, Path]:
    if run_dir_arg:
        run_dir = Path(run_dir_arg)
    else:
        run_dir = source_reviews_path.parent.parent if source_reviews_path.parent.name == "artifacts" else source_reviews_path.parent
    archive_dir = run_dir / "artifacts" / "source_archive"
    index_path = archive_dir / "source_archive_index.json"
    return run_dir, archive_dir, index_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-reviews", required=True)
    parser.add_argument("--run-dir")
    parser.add_argument("--archive-dir")
    parser.add_argument("--source-archive-index")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing SRC-xxx.md excerpt snapshots.")
    args = parser.parse_args()

    source_reviews_path = Path(args.source_reviews)
    run_dir, default_archive_dir, default_index_path = _default_paths(source_reviews_path, args.run_dir)
    archive_dir = Path(args.archive_dir) if args.archive_dir else default_archive_dir
    index_path = Path(args.source_archive_index) if args.source_archive_index else default_index_path

    result = build_archive(
        source_reviews_path=source_reviews_path,
        archive_dir=archive_dir,
        source_archive_index_path=index_path,
        run_dir=run_dir,
        overwrite=args.overwrite,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
