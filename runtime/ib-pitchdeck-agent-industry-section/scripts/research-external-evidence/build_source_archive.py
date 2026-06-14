#!/usr/bin/env python3
"""Build source_archive snapshots from actual searched or user-provided sources.

The archive is the handoff from Research into Knowledge. It can be built
directly from search_log.md selected/opened URLs, with source_reviews.json used
only as an optional compatibility/enrichment input.
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
from datetime import datetime
from pathlib import Path
from typing import Any

from json_utils import load_json_file
from source_classification import is_material_type, normalize_source_type
from validate_formal_research_execution import parse_search_attempts


SRC_RE = re.compile(r"^SRC-\d{3}$")
FULL_URL_RE = re.compile(r"https?://[^\s,;，；\]|)）>]+", flags=re.IGNORECASE)
FORMAL_STAGES = {
    "formal_research",
    "formal research",
    "formal_research_execution",
    "formal research execution",
    "latest_check",
    "latest",
    "peer_check",
    "peer check",
}


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
    if not path.exists():
        return []
    data = load_json_file(path)
    if isinstance(data, list):
        raw = data
    elif isinstance(data, dict):
        raw = data.get("reviews") if "reviews" in data else data.get("source_reviews", [])
    else:
        raw = []
    return [_canonical_review(item) for item in raw if isinstance(item, dict)]


def _stage_is_formal(attempt: dict[str, str]) -> bool:
    return _text(attempt.get("search stage")).lower() in FORMAL_STAGES


def _opened(attempt: dict[str, str]) -> bool:
    value = _text(attempt.get("opened / reviewed")).lower()
    return value in {"yes", "y", "true", "opened", "reviewed", "是", "已"}


def _selected_urls(raw: str) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for item in FULL_URL_RE.findall(raw or ""):
        url = item.strip().rstrip("/")
        if url and url not in seen:
            output.append(url)
            seen.add(url)
    return output


def _short_title(url: str) -> str:
    cleaned = re.sub(r"^https?://", "", url, flags=re.IGNORECASE)
    return cleaned[:120] or "Archived source"


def _attempt_locator_excerpt(attempt: dict[str, str]) -> str:
    return _text(
        attempt.get("locator / excerpt")
        or attempt.get("locator excerpt")
        or attempt.get("locator")
        or attempt.get("reviewed excerpt")
        or attempt.get("notes")
    )


def _reviews_from_search_log(path: Path | None, *, starting_index: int, seen_urls: set[str]) -> list[dict[str, Any]]:
    if not path or not path.exists():
        return []
    attempts = parse_search_attempts(path)
    reviews: list[dict[str, Any]] = []
    next_index = starting_index
    for attempt_id in sorted(attempts):
        attempt = attempts[attempt_id]
        if not _stage_is_formal(attempt) or not _opened(attempt):
            continue
        urls = _selected_urls(attempt.get("selected sources", ""))
        if not urls:
            continue
        locator_excerpt = _attempt_locator_excerpt(attempt)
        for url in urls:
            norm_url = url.rstrip("/")
            if norm_url in seen_urls:
                continue
            seen_urls.add(norm_url)
            next_index += 1
            reviews.append(
                {
                    "source_review_id": f"SRC-{next_index:03d}",
                    "url": norm_url,
                    "title": _short_title(norm_url),
                    "source_type": "web_search_result",
                    "source_access": "public_search",
                    "locator": locator_excerpt,
                    "excerpt": locator_excerpt,
                    "search_attempt_ids": [attempt_id],
                    "evidence_ids": [],
                    "evidence_use_tier": "candidate",
                    "claim_use_scope": "Archived from actual search_log source; Knowledge/LLM must review before claim use.",
                    "usable_as_evidence": False,
                    "review_status": "needs_llm_source_review",
                    "limitations": "Archive-first candidate. Source quality and claim-use scope are decided inside research_evidence_db.",
                }
            )
    return reviews


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
            "This file was generated as an archive-first source snapshot. It preserves the selected URL, locator/excerpt/paraphrase, search linkage, and limitations for downstream Knowledge/QC review. It is not a full-page scrape unless explicitly replaced by a saved_text or saved_pdf archive.",
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
    source_reviews_path: Path | None = None,
    search_log_path: Path | None = None,
    archive_dir: Path,
    source_archive_index_path: Path,
    run_dir: Path,
    overwrite: bool,
) -> dict[str, Any]:
    captured_at = datetime.now().astimezone().isoformat(timespec="seconds")
    reviews = _load_reviews(source_reviews_path) if source_reviews_path else []
    seen_urls = {_text(review.get("url")).rstrip("/") for review in reviews if _text(review.get("url"))}
    reviews.extend(
        _reviews_from_search_log(
            search_log_path,
            starting_index=len(reviews),
            seen_urls=seen_urls,
        )
    )
    archive_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    skipped: list[str] = []
    written: list[str] = []

    archive_all_candidates = bool(search_log_path)
    for review in reviews:
        source_review_id = _text(review.get("source_review_id"))
        url = _text(review.get("url"))
        if not source_review_id or not SRC_RE.fullmatch(source_review_id):
            skipped.append(source_review_id or "(missing SRC ID)")
            continue
        if not archive_all_candidates and not _review_is_usable(review):
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
                "search_attempt_ids": [_text(item) for item in _as_list(review.get("search_attempt_ids")) if _text(item)],
                "evidence_use_tier": _text(review.get("evidence_use_tier")),
                "usable_as_evidence": review.get("usable_as_evidence") if isinstance(review.get("usable_as_evidence"), bool) else False,
                "review_status": _text(review.get("review_status")) or "needs_llm_source_review",
                "claim_use_scope": _text(review.get("claim_use_scope")),
                "locator": _text(review.get("locator")),
                "reviewed_excerpt": _text(review.get("excerpt")),
                "archive_unavailable_reason": "",
            }
        )

    index = {
        "schema_version": "source_archive_index_v1",
        "created_at": captured_at,
        "purpose": "Archive reviewable snapshots for actual searched or user-provided sources before Knowledge/LLM evidence extraction. source_reviews.json is optional compatibility input.",
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


def _default_paths(source_reviews_path: Path | None, search_log_path: Path | None, run_dir_arg: str | None) -> tuple[Path, Path, Path]:
    if run_dir_arg:
        run_dir = Path(run_dir_arg)
    elif source_reviews_path:
        run_dir = source_reviews_path.parent.parent if source_reviews_path.parent.name == "artifacts" else source_reviews_path.parent
    elif search_log_path:
        run_dir = search_log_path.parent.parent if search_log_path.parent.name == "artifacts" else search_log_path.parent
    else:
        run_dir = Path.cwd()
    archive_dir = run_dir / "artifacts" / "source_archive"
    index_path = archive_dir / "source_archive_index.json"
    return run_dir, archive_dir, index_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-reviews", help="Optional legacy/enrichment source_reviews.json")
    parser.add_argument("--search-log", help="Preferred archive-first input: artifacts/search_log.md")
    parser.add_argument("--run-dir")
    parser.add_argument("--archive-dir")
    parser.add_argument("--source-archive-index")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing SRC-xxx.md excerpt snapshots.")
    args = parser.parse_args()

    source_reviews_path = Path(args.source_reviews) if args.source_reviews else None
    search_log_path = Path(args.search_log) if args.search_log else None
    if not source_reviews_path and not search_log_path:
        parser.error("provide --search-log and/or --source-reviews")
    run_dir, default_archive_dir, default_index_path = _default_paths(source_reviews_path, search_log_path, args.run_dir)
    archive_dir = Path(args.archive_dir) if args.archive_dir else default_archive_dir
    index_path = Path(args.source_archive_index) if args.source_archive_index else default_index_path

    result = build_archive(
        source_reviews_path=source_reviews_path,
        search_log_path=search_log_path,
        archive_dir=archive_dir,
        source_archive_index_path=index_path,
        run_dir=run_dir,
        overwrite=args.overwrite,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
