#!/usr/bin/env python3
"""Validate source review cards for formal research evidence.

`search_log.md` records search execution. `source_reviews.json` records which
underlying sources were actually reviewed and how they may be used. Evidence
IDs are optional at this stage because EV rows are normally assigned later by
the research evidence DB builder.
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
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from json_utils import load_json_file
from source_classification import CANONICAL_SOURCE_TYPES, is_material_type, normalize_source_type
from validate_research_pack import evidence_ledger_rows
from validate_formal_research_execution import parse_search_attempts
from validate_source_archive import validate as validate_source_archive


FULL_URL_RE = re.compile(r"^https?://[^\s\]|)）>]+$", flags=re.IGNORECASE)
EV_RE = re.compile(r"\bEV-\d{3}\b")
SRC_RE = re.compile(r"^SRC-\d{3}$")
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
EVIDENCE_USE_TIERS = {
    "core_evidence",
    "contextual_evidence",
    "directional_only",
    "lead_only",
    "rejected",
}


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


def _is_user_source(value: str, source_type: str | None = None) -> bool:
    if source_type and is_material_type(source_type):
        return True
    return value.strip().lower() in USER_SOURCE_VALUES


def _is_user_source_row(review: dict[str, Any]) -> bool:
    return _is_user_source(_text(review.get("url")), _text(review.get("source_type")))


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
        normalized.append(_canonical_review(item))
    return normalized, errors


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
    """Accept common LLM aliases while preserving canonical downstream fields."""
    canonical = dict(review)
    aliases = {
        "source_review_id": ("source_review_id", "review_id", "source_id", "id"),
        "url": ("url", "source_url", "source", "source_link"),
        "title": ("title", "source_title", "source_name", "name"),
        "locator": ("locator", "source_locator", "location", "source_location"),
        "excerpt": ("excerpt", "raw_excerpt", "reviewed_excerpt", "source_excerpt"),
        "search_attempt_ids": ("search_attempt_ids", "search_ids", "attempt_ids"),
        "evidence_ids": ("evidence_ids", "ev_ids"),
    }
    for target, keys in aliases.items():
        if target not in canonical or not _text(canonical.get(target)):
            value = _first_present(review, keys)
            if value not in (None, ""):
                canonical[target] = value
    return canonical


def _review_by_evidence(reviews: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_ev: dict[str, list[dict[str, Any]]] = {}
    for review in reviews:
        for ev_id in _as_list(review.get("evidence_ids")):
            ev = _text(ev_id)
            if EV_RE.fullmatch(ev):
                by_ev.setdefault(ev, []).append(review)
    return by_ev


def _review_by_url(reviews: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_url: dict[str, list[dict[str, Any]]] = {}
    for review in reviews:
        url = _norm_url(_text(review.get("url")))
        if url:
            by_url.setdefault(url, []).append(review)
    return by_url


def _review_by_attempt(reviews: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_attempt: dict[str, list[dict[str, Any]]] = {}
    for review in reviews:
        for attempt_id in _as_list(review.get("search_attempt_ids")):
            text = _text(attempt_id)
            match = re.search(r"(\d+)", text)
            norm = f"S-{int(match.group(1)):03d}" if match else text.upper()
            by_attempt.setdefault(norm, []).append(review)
    return by_attempt


def _review_by_id(reviews: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for review in reviews:
        source_review_id = _text(review.get("source_review_id"))
        if source_review_id:
            by_id[source_review_id] = review
    return by_id


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
    source_review_id = _text(review.get("source_review_id"))
    if not source_review_id:
        errors.append(f"{prefix}: source_review_id is required; use SRC-001, SRC-002, etc.")
    elif not SRC_RE.fullmatch(source_review_id):
        errors.append(f"{prefix}: source_review_id must follow SRC-001 format")

    url = _text(review.get("url"))
    source_type = _text(review.get("source_type"))
    normalized_source_type = normalize_source_type(source_type)
    if not source_type:
        errors.append(f"{prefix}: source_type is required")
    elif normalized_source_type not in CANONICAL_SOURCE_TYPES:
        warnings.append(f"{prefix}: source_type '{source_type}' normalized to 'other'; use one of {sorted(CANONICAL_SOURCE_TYPES)} if possible")

    if not url:
        errors.append(f"{prefix}: url is required")
    elif not _is_user_source(url, normalized_source_type):
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

    evidence_use_tier = _text(review.get("evidence_use_tier")).lower()
    if not evidence_use_tier:
        warnings.append(
            f"{prefix}: evidence_use_tier is missing; add core_evidence/contextual_evidence/"
            "directional_only/lead_only/rejected before deciding usable_as_evidence"
        )
    elif evidence_use_tier not in EVIDENCE_USE_TIERS:
        warnings.append(
            f"{prefix}: evidence_use_tier '{evidence_use_tier}' is not one of "
            f"{sorted(EVIDENCE_USE_TIERS)}"
        )
    claim_use_scope = _text(review.get("claim_use_scope"))
    if _review_is_usable(review) and len(claim_use_scope) < 20:
        warnings.append(
            f"{prefix}: usable source should define claim_use_scope so downstream pages do not overuse the source"
        )
    if evidence_use_tier in {"directional_only", "lead_only", "rejected"} and _review_is_usable(review):
        warnings.append(
            f"{prefix}: evidence_use_tier={evidence_use_tier} conflicts with usable_as_evidence=true; "
            "prefer usable_as_evidence=false unless the source has a narrow reviewed claim_use_scope"
        )

    evidence_ids = [_text(item) for item in _as_list(review.get("evidence_ids")) if _text(item)]
    for ev_id in evidence_ids:
        if not EV_RE.fullmatch(ev_id):
            errors.append(f"{prefix}: invalid evidence_id '{ev_id}'")
    if _review_is_usable(review) and not evidence_ids:
        warnings.append(
            f"{prefix}: usable source has no evidence_ids yet; this is acceptable before Evidence DB promotion, "
            "but the later Evidence Ledger must cite this source by URL or add EV links."
        )
    if evidence_ids and not _review_is_usable(review):
        errors.append(
            f"{prefix}: evidence_ids are present but usable_as_evidence is false. "
            "Do not keep EV links while downgrading the source to bypass source archive or evidence checks; "
            "either make the reviewed source usable with locator/excerpt/archive support, or remove the EV link and downgrade the related FR/research-pack finding."
        )
    if _review_is_usable(review):
        combined = _combined_review_text(review)
        matched_marker = next((marker for marker in WEAK_SOURCE_MARKERS if marker in combined), "")
        if matched_marker and not _has_original_review_support(review):
            warnings.append(
                f"{prefix}: weak-source marker '{matched_marker}' detected. "
                "LLM/QC source assessment required: confirm source quality, methodology access, and claim-use limits; "
                "do not rely on marker matching alone to accept or reject the source."
            )

    attempt_ids = [_text(item) for item in _as_list(review.get("search_attempt_ids")) if _text(item)]
    if not attempt_ids and not _is_user_source(url, normalized_source_type):
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
        if not _is_user_source_row(review)
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
    by_url = _review_by_url(reviews)
    by_attempt = _review_by_attempt(reviews)
    by_source_review_id = _review_by_id(reviews)
    review_urls = {_norm_url(_text(review.get("url"))) for review in reviews if _text(review.get("url"))}
    false_non_user_reviews = [
        review
        for review in non_user_reviews
        if not _review_is_usable(review)
    ]
    if len(non_user_reviews) >= 5 and len(false_non_user_reviews) / max(1, len(non_user_reviews)) >= 0.8:
        warnings.append(
            "80%+ of non-user source_reviews are marked usable_as_evidence=false. "
            "This may be legitimate for weak leads, but if formal research selected these sources, repair by reviewing/archiving stronger sources or downgrading FR findings with limitations; do not batch-false sources just to bypass evidence/archive checks."
        )

    if search_log_path and search_log_path.exists():
        try:
            attempts = parse_search_attempts(search_log_path)
        except Exception as exc:
            errors.append(f"cannot parse search_log.md for source review validation: {exc}")
            attempts = {}
        for review_idx, review in enumerate(reviews, start=1):
            prefix = _text(review.get("source_review_id")) or f"reviews[{review_idx}]"
            for raw_attempt_id in [_text(item) for item in _as_list(review.get("search_attempt_ids")) if _text(item)]:
                match = re.search(r"(\d+)", raw_attempt_id)
                attempt_id = f"S-{int(match.group(1)):03d}" if match else raw_attempt_id.upper()
                attempt = attempts.get(attempt_id)
                if not attempt:
                    errors.append(
                        f"{prefix}: search_attempt_id {attempt_id} not found in search_log.md. "
                        "Do not attach unexecuted S-xxx IDs to source_reviews; create SRC rows only from actual reviewed S-xxx attempts."
                    )
                    continue
                stage = attempt.get("search stage", "").strip().lower()
                if stage not in FORMAL_SEARCH_STAGES:
                    errors.append(
                        f"{prefix}: search_attempt_id {attempt_id} has stage '{stage}', not a formal/latest/peer stage. "
                        "Source reviews for formal evidence must come from actual formal searches."
                    )
                opened = attempt.get("opened / reviewed", "").lower()
                if not any(token in opened for token in POSITIVE_REVIEW_MARKERS):
                    errors.append(
                        f"{prefix}: search_attempt_id {attempt_id} was not marked Opened/Reviewed=yes in search_log.md"
                    )
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
            status = _text(result.get("status"))
            for url in [_text(item) for item in _as_list(result.get("selected_source_urls")) if _text(item)]:
                if not _is_full_url(url):
                    errors.append(f"{prefix}: selected_source_urls contains non-URL value '{url}'")
                    continue
                if _is_root_url(url):
                    errors.append(f"{prefix}: selected_source_urls must use exact page/report URLs, not root domain: {url}")
                if _norm_url(url) not in review_urls:
                    errors.append(f"{prefix}: selected_source_url has no matching source_reviews.url: {url}")
            source_review_ids = [_text(item) for item in _as_list(result.get("source_review_ids")) if _text(item)]
            missing_reviews = [source_review_id for source_review_id in source_review_ids if source_review_id not in by_source_review_id]
            if missing_reviews:
                errors.append(f"{prefix}: source_review_ids not found in source_reviews.json: {', '.join(missing_reviews)}")
            referenced_reviews = [
                by_source_review_id[source_review_id]
                for source_review_id in source_review_ids
                if source_review_id in by_source_review_id
            ]
            usable_referenced_reviews = [review for review in referenced_reviews if _review_is_usable(review)]
            evidence_ids = [_text(item) for item in _as_list(result.get("evidence_ids")) if _text(item)]
            metric_ids = [_text(item) for item in _as_list(result.get("metric_ids")) if _text(item)]
            if status in {"supported", "thin", "conflicting", "not_comparable"} and source_review_ids and not usable_referenced_reviews:
                errors.append(
                    f"{prefix}: status={status} references source_review_ids but all referenced reviews are usable_as_evidence=false. "
                    "This is likely a repair-integrity issue: review/archive a usable source, downgrade the FR status with limitations, or remove unsupported EV/MET claims."
                )
            if (evidence_ids or metric_ids) and source_review_ids and not usable_referenced_reviews:
                errors.append(
                    f"{prefix}: EV/MET IDs cannot be supported by source reviews all marked unusable. "
                    "Do not keep evidence/metric IDs while batch-downgrading sources."
                )

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
            if not ev_id or _is_user_source(source_url) or evidence_status == "lead-only":
                continue
            if not _is_full_url(source_url):
                errors.append(f"{ev_id}: Evidence Ledger Source URL must be full URL or user-provided: {source_url}")
                continue
            if _is_root_url(source_url):
                errors.append(f"{ev_id}: formal Evidence Ledger cannot cite only a root/domain URL: {source_url}")
            matching = by_ev.get(ev_id, [])
            if not matching:
                matching = by_url.get(_norm_url(source_url), [])
            if not matching:
                errors.append(f"{ev_id}: no source_reviews entry links this Evidence Ledger row by evidence_id or Source URL")
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
