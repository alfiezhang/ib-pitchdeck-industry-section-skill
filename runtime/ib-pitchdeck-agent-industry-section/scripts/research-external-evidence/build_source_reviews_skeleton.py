#!/usr/bin/env python3
"""Build source_reviews.json skeleton from search_log.md.

The generated file is a review workspace, not a source-quality judgment. It
mechanically maps real S-xxx search attempts and selected URLs into SRC-xxx
review cards so the LLM can focus on source assessment, locator/excerpt quality,
and claim-use limits. EV IDs are assigned later by the research evidence DB
layer; do not invent them in source_reviews.json.
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
from datetime import date
from pathlib import Path
from typing import Any

from json_utils import load_json_file
from source_classification import is_material_type, normalize_source_type
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


def _looks_like_http_url(url: str) -> bool:
    lowered = url.lower()
    return lowered.startswith("http://") or lowered.startswith("https://")


def _selected_urls(raw: str) -> list[str]:
    return [_norm_url(item) for item in URL_EXTRACT_RE.findall(raw or "")]


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


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


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


def _source_review_template(
    review_id: str,
    *,
    url: str,
    title: str,
    source_type: str,
    source_access: str,
    source_access_path: str,
    locator: str,
    excerpt: str,
    source_date: str,
    geography: str,
    fact_type: str,
) -> dict[str, Any]:
    access_path = source_access_path or ""
    normalized_source_type = normalize_source_type(source_type)
    return {
        "source_review_id": review_id,
        "url": url,
        "title": title,
        "source_type": normalized_source_type,
        "source_access": source_access,
        "source_access_path": access_path,
        "locator": locator
        or "LLM must open/review exact source and replace with page, section, table, paragraph, or URL anchor.",
        "excerpt": excerpt
        or "LLM must add a source-faithful excerpt or paraphrase before promotion.",
        "search_attempt_ids": [],
        "evidence_ids": [],
        "evidence_use_tier": "lead_only",
        "fact_type": fact_type or "factual",
        "claim_use_scope": "Not usable for deck or research-pack claims until LLM reviews exact source, scope, period, and limitations.",
        "usable_as_evidence": False,
        "review_status": "needs_llm_source_review",
        "limitations": "",
        "original_url": access_path if _looks_like_http_url(access_path) else "",
        "methodology_locator": "",
        "source_date": source_date,
        "geography": geography,
        "data_period": "",
        "review_instruction": "Review source metadata and locator/excerpt before marking usability.",
    }


def _load_input_materials(path: Path | None) -> list[dict[str, Any]]:
    if not path or not path.exists():
        return []
    try:
        data = load_json_file(path)
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    return [item for item in _as_list(data.get("source_materials")) if isinstance(item, dict)]


def build_source_reviews(
    search_log_path: Path,
    *,
    formal_only: bool,
    input_card_path: Path | None = None,
) -> dict[str, Any]:
    attempts = parse_search_attempts(search_log_path) if search_log_path.exists() else {}
    reviews: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()

    for material in _load_input_materials(input_card_path):
        source_name = _text(material.get("source_name") or material.get("title") or material.get("name"))
        source_path = _text(
            material.get("source_access_path")
            or material.get("source_path")
            or material.get("source_url")
            or material.get("path")
        )
        source_type = normalize_source_type(material.get("source_type"))
        source_access = _text(material.get("source_access") or ("user_provided" if is_material_type(source_type) else "public_search"))
        source_date = _text(material.get("source_date"))
        geography = _text(material.get("geography"))
        fact_type = _text(material.get("fact_type") or "factual")

        if not source_name and not source_path:
            continue

        url = source_path if _looks_like_http_url(source_path) else "user-provided"
        if source_access == "public_search" and not _looks_like_http_url(source_path):
            source_access = "user_provided"

        review_key = (_norm_url(url), source_type)
        if review_key in seen_keys:
            continue
        seen_keys.add(review_key)

        reviews.append(
            _source_review_template(
                f"SRC-{len(reviews) + 1:03d}",
                url=url,
                title=source_name or source_type,
                source_type=source_type,
                source_access=source_access,
                source_access_path=source_path,
                locator=_text(material.get("locator") or material.get("location") or material.get("methodology_locator")),
                excerpt=_text(material.get("excerpt") or material.get("notes")),
                source_date=source_date,
                geography=geography,
                fact_type=fact_type,
            )
        )

    for attempt_id in sorted(attempts):
        attempt = attempts[attempt_id]
        if formal_only and not _is_formal_stage(attempt):
            continue
        selected_urls = _selected_urls(attempt.get("selected sources", ""))
        if not selected_urls:
            continue
        locator_excerpt = _locator_excerpt(attempt)
        for url in selected_urls:
            review_key = (_norm_url(url), "web_search_result")
            if review_key in seen_keys:
                continue
            seen_keys.add(review_key)
            review_id = f"SRC-{len(reviews) + 1:03d}"
            reviews.append(
                {
                    **_source_review_template(
                        review_id,
                        url=_norm_url(url),
                        title=_short_title(url),
                        source_type="web_search_result",
                        source_access="public_search",
                        source_access_path="",
                        locator=locator_excerpt,
                        excerpt=locator_excerpt,
                        source_date="",
                        geography="",
                        fact_type="factual",
                    ),
                    "search_attempt_ids": [attempt_id],
                    "review_status": _review_status(attempt),
                    "review_instruction": (
                        "Assess whether this is core_evidence, contextual_evidence, directional_only, lead_only, or rejected. "
                        "Only set usable_as_evidence=true after adding a specific locator/excerpt and reviewed claim_use_scope. "
                        "Do not invent EV IDs here; Evidence DB promotion assigns EV IDs later."
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
    parser.add_argument("--input-card")
    args = parser.parse_args()

    output = build_source_reviews(
        Path(args.search_log),
        formal_only=not args.include_broad_discovery,
        input_card_path=Path(args.input_card) if args.input_card else None,
    )
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
