#!/usr/bin/env python3
"""Build source_reviews.json skeleton from search_log.md.

The generated file is a review workspace, not a source-quality judgment. It
mechanically maps real S-xxx search attempts and selected URLs into SRC-xxx
review cards so the LLM can focus on source assessment, locator/excerpt quality,
and evidence promotion decisions.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from validate_formal_research_execution import parse_search_attempts


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
USER_SOURCE_VALUES = {"user-provided", "user provided", "input_card", "management", "company/user-provided"}
URL_EXTRACT_RE = re.compile(r"https?://[^\s,;，；\]|)）>]+", flags=re.IGNORECASE)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _norm_url(url: str) -> str:
    return url.strip().rstrip("/")


def _selected_urls(raw: str) -> list[str]:
    return [_norm_url(item) for item in URL_EXTRACT_RE.findall(raw or "")]


def _stage(attempt: dict[str, str]) -> str:
    return attempt.get("search stage", "").strip().lower()


def _is_formal_stage(attempt: dict[str, str]) -> bool:
    return _stage(attempt) in FORMAL_STAGES


def _opened(attempt: dict[str, str]) -> bool:
    value = attempt.get("opened / reviewed", "").strip().lower()
    return value in {"yes", "y", "true", "opened", "reviewed", "是", "已"}


def _short_title(url: str) -> str:
    if url.lower() in USER_SOURCE_VALUES:
        return "User-provided material"
    cleaned = re.sub(r"^https?://", "", url, flags=re.IGNORECASE)
    return cleaned[:120] or "Source title to review"


def _locator_excerpt(attempt: dict[str, str]) -> str:
    return _text(
        attempt.get("locator / excerpt")
        or attempt.get("locator excerpt")
        or attempt.get("locator")
        or attempt.get("reviewed excerpt")
    )


def _review_status(attempt: dict[str, str]) -> str:
    if _opened(attempt):
        return "needs_llm_source_review"
    return "selected_but_not_reviewed"


def build_source_reviews(search_log_path: Path, *, formal_only: bool) -> dict[str, Any]:
    attempts = parse_search_attempts(search_log_path) if search_log_path.exists() else {}
    reviews: list[dict[str, Any]] = []
    seen_urls: set[tuple[str, str]] = set()

    for attempt_id in sorted(attempts):
        attempt = attempts[attempt_id]
        if formal_only and not _is_formal_stage(attempt):
            continue
        selected_urls = _selected_urls(attempt.get("selected sources", ""))
        if not selected_urls:
            continue
        locator_excerpt = _locator_excerpt(attempt)
        for url in selected_urls:
            key = (attempt_id, _norm_url(url))
            if key in seen_urls:
                continue
            seen_urls.add(key)
            review_id = f"SRC-{len(reviews) + 1:03d}"
            reviews.append(
                {
                    "source_review_id": review_id,
                    "url": _norm_url(url),
                    "title": _short_title(url),
                    "locator": locator_excerpt
                    or "LLM must open/review exact source and replace with page, section, table, paragraph, or URL anchor.",
                    "excerpt": locator_excerpt
                    or "LLM must add a source-faithful excerpt or paraphrase before promotion.",
                    "search_attempt_ids": [attempt_id],
                    "evidence_ids": [],
                    "evidence_use_tier": "lead_only",
                    "claim_use_scope": "Not usable for deck or research-pack claims until LLM reviews exact source, scope, period, method, and limitations.",
                    "usable_as_evidence": False,
                    "review_status": _review_status(attempt),
                    "review_instruction": (
                        "Assess whether this is core_evidence, contextual_evidence, directional_only, lead_only, or rejected. "
                        "Only set usable_as_evidence=true after adding a specific locator/excerpt and linking promoted EV IDs."
                    ),
                }
            )

    return {
        "schema_version": "source_reviews_v1",
        "meta": {
            "created_by": "build_source_reviews_skeleton.py",
            "created_date": date.today().isoformat(),
            "search_log": str(search_log_path),
            "skeleton_note": "Mechanical SRC skeleton. LLM must review each exact source before evidence promotion.",
        },
        "source_reviews": reviews,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search-log", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--include-broad-discovery",
        action="store_true",
        help="Include broad discovery selected URLs. Default keeps only formal/latest/peer attempts.",
    )
    args = parser.parse_args()

    output = build_source_reviews(Path(args.search_log), formal_only=not args.include_broad_discovery)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "is_valid": True,
                "output": str(output_path),
                "source_review_count": len(output["source_reviews"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
