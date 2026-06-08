#!/usr/bin/env python3
"""Validate source review cards for formal research evidence.

`search_log.md` records search execution. `source_reviews.json` records which
underlying sources were actually reviewed and which EV rows they support.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from json_utils import load_json_file
from validate_research_pack import evidence_ledger_rows
from validate_formal_research_execution import parse_search_attempts
from validate_source_archive import validate as validate_source_archive


FULL_URL_RE = re.compile(r"^https?://[^\s\]|)）>]+$", flags=re.IGNORECASE)
EV_RE = re.compile(r"\bEV-\d{3}\b")
FORMAL_SEARCH_STAGES = {"formal_research_execution", "latest_check", "peer_check", "formal research execution", "latest", "peer check"}
POSITIVE_REVIEW_MARKERS = ("yes", "y", "true", "opened", "reviewed", "是", "已")
USER_SOURCE_VALUES = {"user-provided", "user provided", "input_card", "management", "company/user-provided"}
WEAK_SOURCE_MARKERS = (
    "search snippet",
    "search-result",
    "search result",
    "snippet",
    "repost",
    "reposted",
    "mirror",
    "aggregator",
    "unavailable report",
    "lead-only",
    "root domain",
    "without methodology",
    "no methodology",
    "no clear original",
    "转载",
    "转引",
    "摘录",
    "聚合",
    "镜像",
    "搜索摘要",
    "搜索结果",
    "无方法论",
    "未打开原始",
    "原始来源不可访问",
)
ORIGINAL_REVIEW_FIELDS = (
    "original_url",
    "original_source_url",
    "original_report_url",
    "original_source_review_id",
    "methodology_locator",
    "source_chain",
)


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _norm_url(url: str) -> str:
    return url.strip().rstrip("/")


def _is_full_url(value: str) -> bool:
    return bool(FULL_URL_RE.match(value.strip()))


def _is_root_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    path = parsed.path or ""
    return bool(parsed.netloc) and path in {"", "/"} and not parsed.query and not parsed.fragment


def _is_user_source_url(value: str) -> bool:
    return value.strip().lower() in USER_SOURCE_VALUES


def _load_reviews(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    try:
        data = load_json_file(path)
    except Exception as exc:
        return [], [f"cannot read source_reviews.json: {exc}"]
    if isinstance(data, list):
        reviews = data
    elif isinstance(data, dict):
        has_reviews = "reviews" in data
        has_source_reviews = "source_reviews" in data
        if has_reviews and has_source_reviews:
            errors.append("source_reviews.json must use one review array key, not both reviews and source_reviews")
        reviews = data.get("reviews") if has_reviews else data.get("source_reviews", [])
        schema = str(data.get("schema_version") or "")
        if schema and schema != "source_reviews_v1":
            errors.append("source_reviews.json schema_version must be source_reviews_v1")
    else:
        return [], ["source_reviews.json must be an object with reviews[] or a reviews array"]
    if not isinstance(reviews, list):
        return [], ["source_reviews.json reviews must be an array"]
    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(reviews, start=1):
        if not isinstance(item, dict):
            errors.append(f"reviews[{idx}] must be an object")
            continue
        normalized.append(item)
    return normalized, errors


def _review_by_evidence(reviews: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_ev: dict[str, list[dict[str, Any]]] = {}
    for review in reviews:
        for ev_id in _as_list(review.get("evidence_ids")):
            ev = _text(ev_id)
            if EV_RE.fullmatch(ev):
                by_ev.setdefault(ev, []).append(review)
    return by_ev


def _review_by_attempt(reviews: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_attempt: dict[str, list[dict[str, Any]]] = {}
    for review in reviews:
        for attempt_id in _as_list(review.get("search_attempt_ids")):
            text = _text(attempt_id)
            match = re.search(r"(\d+)", text)
            norm = f"S-{int(match.group(1)):03d}" if match else text.upper()
            by_attempt.setdefault(norm, []).append(review)
    return by_attempt


def _selected_urls(raw: str) -> list[str]:
    return re.findall(r"https?://[^\s,;，；\]|)）>]+", raw or "", flags=re.IGNORECASE)


def _review_is_usable(review: dict[str, Any]) -> bool:
    usable = review.get("usable_as_evidence")
    if isinstance(usable, bool):
        return usable
    status = str(review.get("evidence_status") or review.get("status") or "").strip().lower()
    return status in {"primary-reviewed", "secondary-reviewed", "reviewed", "usable"}


def _combined_review_text(review: dict[str, Any]) -> str:
    values: list[str] = []
    for key, value in review.items():
        if isinstance(value, (str, int, float, bool)):
            values.append(str(value))
        elif isinstance(value, list):
            values.extend(str(item) for item in value if isinstance(item, (str, int, float, bool)))
    return " ".join(values).lower()


def _has_original_review_support(review: dict[str, Any]) -> bool:
    for field in ORIGINAL_REVIEW_FIELDS:
        value = review.get(field)
        if isinstance(value, str) and value.strip() and value.strip() not in {"-", "n/a", "NA"}:
            return True
        if isinstance(value, list) and any(str(item).strip() for item in value):
            return True
    return False


def _validate_review_fields(review: dict[str, Any], idx: int, errors: list[str], warnings: list[str]) -> None:
    prefix = f"reviews[{idx}]"
    url = _text(review.get("url"))
    if not url:
        errors.append(f"{prefix}: url is required")
    elif not _is_user_source_url(url):
        if not _is_full_url(url):
            errors.append(f"{prefix}: url must be a full http(s) URL or user-provided")
        elif _is_root_url(url) and _review_is_usable(review):
            errors.append(f"{prefix}: usable evidence cannot cite only a root/domain URL: {url}")

    for field, min_len in (
        ("title", 8),
        ("locator", 12),
        ("excerpt", 30),
    ):
        value = _text(review.get(field))
        if len(value) < min_len:
            errors.append(f"{prefix}: {field} is too short for auditability")

    evidence_ids = [_text(item) for item in _as_list(review.get("evidence_ids")) if _text(item)]
    for ev_id in evidence_ids:
        if not EV_RE.fullmatch(ev_id):
            errors.append(f"{prefix}: invalid evidence_id '{ev_id}'")
    if _review_is_usable(review) and not evidence_ids:
        errors.append(f"{prefix}: usable evidence must list at least one evidence_id")
    if _review_is_usable(review):
        combined = _combined_review_text(review)
        matched_marker = next((marker for marker in WEAK_SOURCE_MARKERS if marker in combined), "")
        if matched_marker and not _has_original_review_support(review):
            errors.append(
                f"{prefix}: usable_as_evidence=true conflicts with weak-source marker '{matched_marker}'. "
                "Use usable_as_evidence=false for search snippets, reposts, mirrors, aggregators, unavailable reports, "
                "or pages without clear original methodology unless a reviewed original source/methodology locator is linked."
            )

    attempt_ids = [_text(item) for item in _as_list(review.get("search_attempt_ids")) if _text(item)]
    if not attempt_ids and not _is_user_source_url(url):
        warnings.append(f"{prefix}: no search_attempt_ids; source may not be traceable to search_log.md")


def validate(
    source_reviews_path: Path,
    *,
    search_log_path: Path | None = None,
    formal_research_execution_report_path: Path | None = None,
    memo_path: Path | None = None,
    source_archive_index_path: Path | None = None,
    run_dir: Path | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if not source_reviews_path.exists():
        return {
            "is_valid": False,
            "error_count": 1,
            "warning_count": 0,
            "errors": [f"missing required artifact: {source_reviews_path}"],
            "warnings": [],
            "source_reviews": str(source_reviews_path),
        }

    reviews, load_errors = _load_reviews(source_reviews_path)
    errors.extend(load_errors)
    for idx, review in enumerate(reviews, start=1):
        _validate_review_fields(review, idx, errors, warnings)
    non_user_reviews = [
        review
        for review in reviews
        if not _is_user_source_url(_text(review.get("url")))
    ]
    missing_usable = [
        idx
        for idx, review in enumerate(reviews, start=1)
        if "usable_as_evidence" not in review
    ]
    if missing_usable:
        sample = ", ".join(f"reviews[{idx}]" for idx in missing_usable[:5])
        warnings.append(
            "source_reviews missing explicit usable_as_evidence; review each source "
            f"instead of batch-filling true. Examples: {sample}"
        )
    if len(non_user_reviews) >= 5 and all(_review_is_usable(review) for review in non_user_reviews):
        warnings.append(
            "all non-user source_reviews are marked usable_as_evidence=true; audit for search snippets, "
            "root domains, weak mirrors, or lead-only pages before promoting them into Evidence Ledger"
        )

    by_ev = _review_by_evidence(reviews)
    by_attempt = _review_by_attempt(reviews)
    review_urls = {_norm_url(_text(review.get("url"))) for review in reviews if _text(review.get("url"))}

    if search_log_path and search_log_path.exists():
        try:
            attempts = parse_search_attempts(search_log_path)
        except Exception as exc:
            errors.append(f"cannot parse search_log.md for source review validation: {exc}")
            attempts = {}
        for attempt_id, attempt in attempts.items():
            opened = attempt.get("opened / reviewed", "").lower()
            is_opened = any(token in opened for token in POSITIVE_REVIEW_MARKERS)
            if not is_opened:
                continue
            stage = attempt.get("search stage", "").strip().lower()
            selected = _selected_urls(attempt.get("selected sources", ""))
            has_review = bool(by_attempt.get(attempt_id))
            if not has_review and stage in FORMAL_SEARCH_STAGES:
                errors.append(
                    f"{attempt_id}: search_log marks Opened/Reviewed=yes for formal stage '{stage}', "
                    "but no source_reviews entry references this search_attempt_id"
                )
            elif not has_review and stage and stage not in {"broad_discovery", "broad discovery", "industry_scope", "scoping"}:
                warnings.append(
                    f"{attempt_id}: search_log marks Opened/Reviewed=yes but no source_reviews entry references it"
                )
            for url in selected:
                if _is_root_url(url) and stage in FORMAL_SEARCH_STAGES:
                    errors.append(f"{attempt_id}: formal Selected Sources must be exact page/report URLs, not root domain: {url}")
                elif stage in FORMAL_SEARCH_STAGES and _norm_url(url) not in review_urls:
                    errors.append(f"{attempt_id}: formal Selected Sources URL has no matching source_reviews.url: {url}")

    if formal_research_execution_report_path and formal_research_execution_report_path.exists():
        try:
            report = load_json_file(formal_research_execution_report_path)
        except Exception as exc:
            errors.append(f"cannot read formal_research_execution_report.json for source review validation: {exc}")
            report = {}
        for idx, result in enumerate(_as_list(report.get("issue_results")), start=1):
            if not isinstance(result, dict):
                continue
            prefix = result.get("result_id") or f"issue_results[{idx}]"
            for url in [_text(item) for item in _as_list(result.get("selected_source_urls")) if _text(item)]:
                if not _is_full_url(url):
                    errors.append(f"{prefix}: selected_source_urls contains non-URL value '{url}'")
                    continue
                if _is_root_url(url):
                    errors.append(f"{prefix}: selected_source_urls must use exact page/report URLs, not root domain: {url}")
                if _norm_url(url) not in review_urls:
                    errors.append(f"{prefix}: selected_source_url has no matching source_reviews.url: {url}")

    if memo_path and memo_path.exists():
        try:
            memo_text = memo_path.read_text(encoding="utf-8")
            rows = evidence_ledger_rows(memo_text)
        except Exception as exc:
            errors.append(f"cannot parse research pack Evidence Ledger for source review validation: {exc}")
            rows = []
        for row in rows:
            ev_id = _text(row.get("Evidence ID"))
            source_url = _text(row.get("Source URL"))
            evidence_status = _text(row.get("Evidence Status")).lower()
            if not ev_id or _is_user_source_url(source_url) or evidence_status == "lead-only":
                continue
            if not _is_full_url(source_url):
                errors.append(f"{ev_id}: Evidence Ledger Source URL must be full URL or user-provided: {source_url}")
                continue
            if _is_root_url(source_url):
                errors.append(f"{ev_id}: formal Evidence Ledger cannot cite only a root/domain URL: {source_url}")
            matching = by_ev.get(ev_id, [])
            if not matching:
                errors.append(f"{ev_id}: no source_reviews entry links this Evidence Ledger row")
                continue
            usable = [review for review in matching if _review_is_usable(review)]
            if not usable:
                errors.append(f"{ev_id}: linked source_reviews entries are not usable_as_evidence=true")

    if source_archive_index_path is not None:
        archive_result = validate_source_archive(
            source_reviews_path=source_reviews_path,
            source_archive_index_path=source_archive_index_path,
            run_dir=run_dir,
        )
        if archive_result.get("is_valid") is False:
            errors.append("current source archive validation failed")
            errors.extend(str(item) for item in archive_result.get("errors", []))
        warnings.extend(str(item) for item in archive_result.get("warnings", []))

    return {
        "is_valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "source_reviews": str(source_reviews_path),
        "review_count": len(reviews),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-reviews", required=True)
    parser.add_argument("--search-log")
    parser.add_argument("--formal-research-execution-report")
    parser.add_argument("--research-pack")
    parser.add_argument("--source-archive-index")
    parser.add_argument("--run-dir")
    parser.add_argument("--output")
    args = parser.parse_args()

    result = validate(
        Path(args.source_reviews),
        search_log_path=Path(args.search_log) if args.search_log else None,
        formal_research_execution_report_path=Path(args.formal_research_execution_report) if args.formal_research_execution_report else None,
        memo_path=Path(args.research_pack) if args.research_pack else None,
        source_archive_index_path=Path(args.source_archive_index) if args.source_archive_index else None,
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
