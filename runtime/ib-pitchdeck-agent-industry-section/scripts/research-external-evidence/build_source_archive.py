#!/usr/bin/env python3
"""Build source_archive snapshots from actual searched or user-provided sources.

The archive is the handoff from Research into Knowledge. It is built directly
from search_log.md selected/opened URLs. Source usability is a Knowledge/QC
judgment stored inside research_evidence_db.json, not a separate artifact.
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
from html.parser import HTMLParser
import json
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from material_intake_common import normalize_source_type
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
RESEARCH_DECLARED_ARCHIVE_STATUSES = {
    "manual_verified_excerpt",
    "needs_research_verification",
    "search_snippet_only",
    "archive_unavailable",
}
MAX_FETCH_BYTES = 5_000_000
FETCH_TIMEOUT_SECONDS = 20


class _HTMLTextExtractor(HTMLParser):
    """Small stdlib HTML-to-text extractor for archive review snapshots."""

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag.lower() in {"p", "br", "div", "section", "article", "li", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if tag.lower() in {"p", "div", "section", "article", "li", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = " ".join(data.split())
        if text:
            self.parts.append(text)

    def text(self) -> str:
        body = " ".join(self.parts)
        body = re.sub(r"\s*\n\s*", "\n", body)
        body = re.sub(r"[ \t]{2,}", " ", body)
        body = re.sub(r"\n{3,}", "\n\n", body)
        return body.strip()


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


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
        attempt.get("source locator / raw excerpt")
        or attempt.get("locator / excerpt")
        or attempt.get("locator excerpt")
        or attempt.get("locator")
        or attempt.get("reviewed excerpt")
        or attempt.get("notes")
    )


def _attempt_excerpt_origin(attempt: dict[str, str]) -> str:
    value = _text(attempt.get("excerpt origin")).lower()
    return value or "opened_page"


def _attempt_secondary_verification(attempt: dict[str, str]) -> str:
    value = _text(attempt.get("secondary verification")).lower()
    return value or "not_done"


def _attempt_secondary_verification_notes(attempt: dict[str, str]) -> str:
    return _text(attempt.get("secondary verification notes"))


def _attempt_research_archive_status(attempt: dict[str, str]) -> str:
    value = _text(attempt.get("research archive status")).lower()
    return value if value in RESEARCH_DECLARED_ARCHIVE_STATUSES else ""


def _safe_filename(source_review_id: str, content_type: str) -> str:
    suffix = ".html" if "html" in content_type.lower() else ".txt"
    return f"{source_review_id}_raw{suffix}"


def _decode_body(body: bytes, content_type: str) -> str:
    charset_match = re.search(r"charset=([A-Za-z0-9._-]+)", content_type or "", flags=re.IGNORECASE)
    encodings = [charset_match.group(1)] if charset_match else []
    encodings.extend(["utf-8", "gb18030", "latin-1"])
    for encoding in encodings:
        try:
            return body.decode(encoding, errors="replace")
        except LookupError:
            continue
    return body.decode("utf-8", errors="replace")


def _html_to_text(html: str) -> str:
    parser = _HTMLTextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return " ".join(re.sub(r"<[^>]+>", " ", html).split())
    return parser.text()


def _fetch_url(url: str) -> dict[str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; IBPitchdeckSkill/1.0; source archive)",
            "Accept": "text/html,application/xhtml+xml,application/xml,text/plain;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            content_type = response.headers.get("Content-Type", "")
            raw = response.read(MAX_FETCH_BYTES + 1)
            truncated = len(raw) > MAX_FETCH_BYTES
            raw = raw[:MAX_FETCH_BYTES]
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "ok": "",
            "reason": f"Could not download full source page: {exc}",
        }
    decoded = _decode_body(raw, content_type)
    text = _html_to_text(decoded) if "html" in content_type.lower() or "<html" in decoded[:500].lower() else decoded.strip()
    if truncated:
        text = f"{text}\n\n[Archive note: response was truncated at {MAX_FETCH_BYTES} bytes.]"
    return {
        "ok": "1",
        "content_type": content_type or "application/octet-stream",
        "raw_text": decoded,
        "review_text": text.strip(),
        "truncated": "1" if truncated else "",
    }


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
        excerpt_origin = _attempt_excerpt_origin(attempt)
        secondary_verification = _attempt_secondary_verification(attempt)
        secondary_verification_notes = _attempt_secondary_verification_notes(attempt)
        research_archive_status = _attempt_research_archive_status(attempt)
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
                    "excerpt_origin": excerpt_origin,
                    "secondary_verification": secondary_verification,
                    "secondary_verification_notes": secondary_verification_notes,
                    "research_archive_status": research_archive_status,
                }
            )
    return reviews


def _markdown_snapshot(
    review: dict[str, Any],
    captured_at: str,
    *,
    archive_status: str,
    reviewed_text: str,
    raw_archive_path: str = "",
    archive_unavailable_reason: str = "",
    excerpt_origin: str = "",
    secondary_verification: str = "",
    secondary_verification_notes: str = "",
    research_archive_status: str = "",
) -> str:
    source_review_id = _text(review.get("source_review_id"))
    title = _text(review.get("title")) or source_review_id
    url = _text(review.get("url"))
    locator = _text(review.get("locator"))
    excerpt = reviewed_text or _text(review.get("excerpt"))
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
        f"- Archive Status: {archive_status}",
        f"- Locator: {locator}",
        f"- Evidence IDs: {evidence_ids}",
    ]
    if original_url:
        lines.append(f"- Original URL: {original_url}")
    if methodology:
        lines.append(f"- Methodology Locator: {methodology}")
    if limitations:
        lines.append(f"- Limitations: {limitations}")
    if raw_archive_path:
        lines.append(f"- Raw Archive Path: {raw_archive_path}")
    if archive_unavailable_reason:
        lines.append(f"- Archive Unavailable Reason: {archive_unavailable_reason}")
    if excerpt_origin:
        lines.append(f"- Excerpt Origin: {excerpt_origin}")
    if secondary_verification:
        lines.append(f"- Secondary Verification: {secondary_verification}")
    if secondary_verification_notes:
        lines.append(f"- Secondary Verification Notes: {secondary_verification_notes}")
    if research_archive_status:
        lines.append(f"- Research Archive Status: {research_archive_status}")
    lines.extend(
        [
            "",
            "## Reviewed Excerpt / Faithful Paraphrase",
            "",
            excerpt,
            "",
            "## Archive Note",
            "",
            "This file was generated as an archive-first source snapshot. It preserves the selected URL, locator/excerpt/paraphrase, search linkage, and limitations for downstream Knowledge/QC review. If Archive Status is saved_html/saved_text, a full-page raw archive was attempted and the extracted text above is the review workspace. If Archive Status is manual_verified_excerpt, Research explicitly declared that status after secondary verification.",
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
    search_log_path: Path | None = None,
    archive_dir: Path,
    source_archive_index_path: Path,
    run_dir: Path,
    overwrite: bool,
    fetch_web: bool = True,
) -> dict[str, Any]:
    captured_at = datetime.now().astimezone().isoformat(timespec="seconds")
    reviews = _reviews_from_search_log(
        search_log_path,
        starting_index=0,
        seen_urls=set(),
    )
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
        archive_status = "archive_unavailable"
        archive_path = ""
        archive_file = archive_dir / f"{source_review_id}.md"
        raw_relative_path = ""
        archive_unavailable_reason = ""
        reviewed_text = ""
        fetch_result: dict[str, str] = {}
        excerpt_origin = _text(review.get("excerpt_origin")) or "opened_page"
        secondary_verification = _text(review.get("secondary_verification")) or "not_done"
        secondary_verification_notes = _text(review.get("secondary_verification_notes"))
        research_archive_status = _text(review.get("research_archive_status"))
        if fetch_web and url.lower().startswith(("http://", "https://")):
            fetch_result = _fetch_url(url)
        if fetch_result.get("ok"):
            raw_dir = archive_dir / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            raw_file = raw_dir / _safe_filename(source_review_id, fetch_result.get("content_type", ""))
            if overwrite or not raw_file.exists():
                raw_file.write_text(fetch_result.get("raw_text", ""), encoding="utf-8")
            raw_relative_path = _relative_archive_path(run_dir, raw_file)
            reviewed_text = fetch_result.get("review_text", "")
            archive_status = "saved_html" if raw_file.suffix == ".html" else "saved_text"
            if len(reviewed_text) < 80:
                archive_status = "archive_unavailable"
                archive_unavailable_reason = "Downloaded source page produced too little readable text for audit extraction."
        else:
            archive_unavailable_reason = fetch_result.get("reason") or "Full source page was not downloaded."
            reviewed_text = _text(review.get("excerpt"))
            if research_archive_status:
                archive_status = research_archive_status
                archive_unavailable_reason = (
                    f"{archive_unavailable_reason} Research declared archive_status={research_archive_status}."
                )
            elif excerpt_origin == "search_snippet":
                archive_status = "search_snippet_only"
                archive_unavailable_reason = (
                    f"{archive_unavailable_reason} Excerpt origin is search_snippet, so this remains a lead until Research opens and verifies the source. "
                    "Research Archive Status was not explicitly declared."
                )
            elif len(reviewed_text) >= 80:
                archive_status = "needs_research_verification"
                archive_unavailable_reason = (
                    f"{archive_unavailable_reason} Research must explicitly declare Research Archive Status before Knowledge can promote this excerpt."
                )
        if overwrite or not archive_file.exists():
            archive_file.write_text(
                _markdown_snapshot(
                    review,
                    captured_at,
                    archive_status=archive_status,
                    reviewed_text=reviewed_text,
                    raw_archive_path=raw_relative_path,
                    archive_unavailable_reason=archive_unavailable_reason,
                    excerpt_origin=excerpt_origin,
                    secondary_verification=secondary_verification,
                    secondary_verification_notes=secondary_verification_notes,
                    research_archive_status=research_archive_status,
                ),
                encoding="utf-8",
            )
            written.append(str(archive_file))
        archive_path = str(archive_file)
        entries.append(
            {
                "source_review_id": source_review_id,
                "url": url,
                "title": _text(review.get("title")),
                "archive_status": archive_status,
                "archive_path": _relative_archive_path(run_dir, Path(archive_path)),
                "raw_archive_path": raw_relative_path,
                "captured_at": captured_at,
                "source_type": normalize_source_type(review.get("source_type")),
                "search_attempt_ids": [_text(item) for item in _as_list(review.get("search_attempt_ids")) if _text(item)],
                "evidence_use_tier": _text(review.get("evidence_use_tier")),
                "usable_as_evidence": review.get("usable_as_evidence") if isinstance(review.get("usable_as_evidence"), bool) else False,
                "review_status": (
                    "research_verified_excerpt"
                    if archive_status == "manual_verified_excerpt"
                    else "needs_research_secondary_verification"
                    if archive_status == "needs_research_verification"
                    else "lead_only_search_snippet"
                    if archive_status == "search_snippet_only"
                    else _text(review.get("review_status")) or "needs_llm_source_review"
                ),
                "claim_use_scope": _text(review.get("claim_use_scope")),
                "locator": _text(review.get("locator")),
                "reviewed_excerpt": reviewed_text[:4000],
                "archive_unavailable_reason": archive_unavailable_reason,
                "excerpt_origin": excerpt_origin,
                "secondary_verification": secondary_verification,
                "secondary_verification_notes": secondary_verification_notes,
                "research_archive_status": research_archive_status,
            }
        )

    index = {
        "schema_version": "source_archive_index_v1",
        "created_at": captured_at,
        "purpose": "Archive reviewable snapshots for actual searched or user-provided sources before Knowledge/LLM evidence extraction. Source usability is reviewed inside research_evidence_db.json.",
        "entries": entries,
    }
    source_archive_index_path.parent.mkdir(parents=True, exist_ok=True)
    source_archive_index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "is_valid": True,
        "source_review_count": len(reviews),
        "archive_entry_count": len(entries),
        "written_snapshot_count": len(written),
        "full_page_fetch_attempted": bool(fetch_web),
        "skipped_review_ids": skipped,
        "source_archive_index": str(source_archive_index_path),
    }


def _default_paths(search_log_path: Path | None, run_dir_arg: str | None) -> tuple[Path, Path, Path]:
    if run_dir_arg:
        run_dir = Path(run_dir_arg)
    elif search_log_path:
        run_dir = search_log_path.parent.parent if search_log_path.parent.name == "artifacts" else search_log_path.parent
    else:
        run_dir = Path.cwd()
    archive_dir = run_dir / "artifacts" / "source_archive"
    index_path = archive_dir / "source_archive_index.json"
    return run_dir, archive_dir, index_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search-log", required=True, help="Archive-first input: artifacts/search_log.md")
    parser.add_argument("--run-dir")
    parser.add_argument("--archive-dir")
    parser.add_argument("--source-archive-index")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing SRC-xxx.md excerpt snapshots.")
    parser.add_argument("--no-fetch-web", action="store_true", help="Do not attempt to download selected source URLs; write excerpt/unavailable snapshots only.")
    args = parser.parse_args()

    search_log_path = Path(args.search_log)
    run_dir, default_archive_dir, default_index_path = _default_paths(search_log_path, args.run_dir)
    archive_dir = Path(args.archive_dir) if args.archive_dir else default_archive_dir
    index_path = Path(args.source_archive_index) if args.source_archive_index else default_index_path

    result = build_archive(
        search_log_path=search_log_path,
        archive_dir=archive_dir,
        source_archive_index_path=index_path,
        run_dir=run_dir,
        overwrite=args.overwrite,
        fetch_web=not args.no_fetch_web,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
