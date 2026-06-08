#!/usr/bin/env python3
"""Build a formal_research_execution_report skeleton from plan/log/reviews.

The generated report is an execution ledger, not final research judgment. It
copies taxonomy from formal_search_plan, maps FS-xxx to real S-xxx attempts, and
maps reviewed sources to SRC-xxx rows so the LLM only has to confirm status,
findings_summary, limitations, and research_pack_handling.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from json_utils import load_json_file
from validate_formal_research_execution import parse_search_attempts


FS_RE = re.compile(r"FS-\d{3}")
FULL_URL_RE = re.compile(r"https?://[^\s,;，；\]|)）>]+", flags=re.IGNORECASE)
USER_SOURCE_VALUES = {"user-provided", "user provided", "input_card", "management", "company/user-provided"}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _norm_url(url: str) -> str:
    return url.strip().rstrip("/")


def _is_user_source_url(value: str) -> bool:
    return value.strip().lower() in USER_SOURCE_VALUES


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
        "search_attempt_ids": ("search_attempt_ids", "search_ids", "attempt_ids"),
        "evidence_ids": ("evidence_ids", "ev_ids"),
    }
    for target, keys in aliases.items():
        if target not in canonical or not _text(canonical.get(target)):
            value = _first_present(review, keys)
            if value not in (None, ""):
                canonical[target] = value
    return canonical


def _load_reviews(path: Path | None) -> list[dict[str, Any]]:
    if not path or not path.exists():
        return []
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


def _planned_instructions(plan: dict[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for issue in _as_list(plan.get("issue_search_plan")):
        if not isinstance(issue, dict):
            continue
        for instruction in _as_list(issue.get("search_instructions")):
            if not isinstance(instruction, dict):
                continue
            instruction_id = _text(instruction.get("instruction_id"))
            if not instruction_id:
                continue
            output.append(
                {
                    "instruction_id": instruction_id,
                    "issue_area": _text(issue.get("issue_area")),
                    "subissue": _text(issue.get("subissue")),
                    "research_question": _text(issue.get("research_question")),
                    "query": _text(instruction.get("query")),
                    "purpose": _text(instruction.get("purpose")),
                }
            )
    return output


def _attempt_instruction_ids(attempt: dict[str, str]) -> list[str]:
    return sorted(set(FS_RE.findall(attempt.get("search instruction ids", ""))))


def _attempt_selected_urls(attempt: dict[str, str]) -> list[str]:
    return [_norm_url(item) for item in FULL_URL_RE.findall(attempt.get("selected sources", ""))]


def _reviews_for_instruction(
    *,
    reviews: list[dict[str, Any]],
    attempts: list[dict[str, str]],
) -> list[dict[str, Any]]:
    attempt_ids = {attempt.get("attempt_id", "") for attempt in attempts}
    attempt_urls = {_norm_url(url) for attempt in attempts for url in _attempt_selected_urls(attempt)}
    matched: list[dict[str, Any]] = []
    seen: set[str] = set()
    for review in reviews:
        review_id = _text(review.get("source_review_id"))
        review_attempts = {_text(item) for item in _as_list(review.get("search_attempt_ids"))}
        review_url = _norm_url(_text(review.get("url")))
        if (review_attempts & attempt_ids) or (review_url and review_url in attempt_urls):
            key = review_id or review_url
            if key not in seen:
                matched.append(review)
                seen.add(key)
    return matched


def _unique(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        if text and text not in seen:
            output.append(text)
            seen.add(text)
    return output


def build_report(
    *,
    plan: dict[str, Any],
    search_log_path: Path,
    reviews: list[dict[str, Any]],
    search_log_ref: str,
    include_unexecuted: bool,
) -> dict[str, Any]:
    attempts_by_id = parse_search_attempts(search_log_path) if search_log_path.exists() else {}
    attempts_by_instruction: dict[str, list[dict[str, str]]] = {}
    for attempt in attempts_by_id.values():
        for fs_id in _attempt_instruction_ids(attempt):
            attempts_by_instruction.setdefault(fs_id, []).append(attempt)

    issue_results: list[dict[str, Any]] = []
    covered_issue_areas: set[str] = set()
    thin_or_unresolved: list[str] = []
    unavailable: list[str] = []

    for instruction in _planned_instructions(plan):
        fs_id = instruction["instruction_id"]
        attempts = attempts_by_instruction.get(fs_id, [])
        if not attempts and not include_unexecuted:
            continue
        matched_reviews = _reviews_for_instruction(reviews=reviews, attempts=attempts)
        usable_reviews = [review for review in matched_reviews if _review_is_usable(review)]
        attempt_ids = _unique([attempt.get("attempt_id", "") for attempt in attempts])
        selected_urls = _unique(
            [
                url
                for attempt in attempts
                for url in _attempt_selected_urls(attempt)
            ]
            + [_text(review.get("url")) for review in matched_reviews if _text(review.get("url")) and not _is_user_source_url(_text(review.get("url")))]
        )
        source_review_ids = _unique([_text(review.get("source_review_id")) for review in matched_reviews])
        evidence_ids = _unique([
            _text(ev_id)
            for review in usable_reviews
            for ev_id in _as_list(review.get("evidence_ids"))
        ])

        if usable_reviews:
            status = "thin"
            limitations = ["Auto-built skeleton: LLM must verify source support, scope, and whether status should be supported/thin/conflicting before promotion."]
            findings_summary = "Auto-built execution skeleton: reviewed source(s) are linked; confirm the finding and limitations before research-pack promotion."
            handling = "Review linked source_reviews and promote only confirmed facts/metrics into Formal Research Extracts, Evidence Ledger, and Metric Reconciliation."
            covered_issue_areas.add(instruction["issue_area"])
            thin_or_unresolved.append(f"{instruction['issue_area']}/{instruction['subissue']}")
        elif attempts:
            status = "insufficient"
            limitations = ["Formal search attempt exists, but no usable source_reviews are linked yet."]
            findings_summary = "Formal search was executed, but source review/evidence support is not yet sufficient for promotion."
            handling = "Create source_reviews/source_archive for reviewed usable sources, or keep this as a research gap/backlog."
            unavailable.append(f"{instruction['issue_area']}/{instruction['subissue']}")
        else:
            status = "insufficient"
            limitations = ["No S-xxx search attempt is linked to this planned FS-xxx instruction."]
            findings_summary = "Planned formal search instruction has not been executed."
            handling = "Run the real formal search, append an S-xxx entry to search_log.md, then rebuild this skeleton."
            unavailable.append(f"{instruction['issue_area']}/{instruction['subissue']}")

        issue_results.append(
            {
                "result_id": f"FR-{len(issue_results) + 1:03d}",
                "issue_area": instruction["issue_area"],
                "subissue": instruction["subissue"],
                "research_question": instruction["research_question"],
                "status": status,
                "search_instruction_ids": [fs_id],
                "search_attempt_ids": attempt_ids,
                "source_discovery_attempt_ids": [],
                "selected_source_urls": selected_urls,
                "source_review_ids": source_review_ids,
                "evidence_ids": evidence_ids,
                "metric_ids": [],
                "findings_summary": findings_summary,
                "limitations": limitations,
                "research_pack_handling": handling,
            }
        )

    return {
        "schema_version": "formal_research_execution_report_v1",
        "formal_research_completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "search_log": search_log_ref,
        "issue_results": issue_results,
        "coverage_summary": {
            "covered_issue_areas": sorted(covered_issue_areas),
            "thin_or_unresolved_subissues": sorted(set(thin_or_unresolved)),
            "not_available_after_research": sorted(set(unavailable)),
        },
        "unresolved_issues": sorted(set(unavailable)),
        "skeleton_note": "Generated by build_formal_research_execution_report_skeleton.py. LLM must review and edit status, findings_summary, limitations, research_pack_handling, EV/MET IDs before treating this as final research judgment.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formal-search-plan", required=True)
    parser.add_argument("--search-log", required=True)
    parser.add_argument("--source-reviews")
    parser.add_argument("--output", required=True)
    parser.add_argument("--search-log-ref", default="artifacts/search_log.md")
    parser.add_argument("--include-unexecuted", action="store_true", help="Include planned FS-xxx instructions with no S-xxx attempts as insufficient FR rows.")
    args = parser.parse_args()

    plan = load_json_file(Path(args.formal_search_plan))
    reviews = _load_reviews(Path(args.source_reviews)) if args.source_reviews else []
    report = build_report(
        plan=plan,
        search_log_path=Path(args.search_log),
        reviews=reviews,
        search_log_ref=args.search_log_ref,
        include_unexecuted=args.include_unexecuted,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"is_valid": True, "output": str(output_path), "issue_result_count": len(report["issue_results"])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
