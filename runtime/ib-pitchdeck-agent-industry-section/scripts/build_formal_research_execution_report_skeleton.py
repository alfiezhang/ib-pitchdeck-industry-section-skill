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
                    "priority": _text(issue.get("priority")),
                    "execution_expectation": _text(issue.get("execution_expectation")),
                    "minimum_actual_searches": issue.get("minimum_actual_searches") if isinstance(issue.get("minimum_actual_searches"), int) else 0,
                    "coverage_required": issue.get("coverage_required") is True,
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


def _formal_attempts(attempts_by_id: dict[str, dict[str, str]]) -> set[str]:
    output: set[str] = set()
    for attempt_id, attempt in attempts_by_id.items():
        stage = _text(attempt.get("search stage")).lower()
        if stage in {"formal_research", "formal research", "formal_research_execution", "formal research execution", "latest_check", "latest", "peer_check", "peer check"}:
            output.add(attempt_id)
    return output


def _terminal_status(
    *,
    attempts: list[dict[str, str]],
    usable_reviews: list[dict[str, Any]],
    instruction: dict[str, Any],
) -> tuple[str, str]:
    if usable_reviews:
        return "executed_with_evidence", "may_support_claim"
    if attempts:
        return "executed_no_usable_source", "research_backlog_only"
    if _text(instruction.get("execution_expectation")) == "accounting_only":
        return "accounting_only", "research_backlog_only"
    return "not_executed", "research_backlog_only"


def build_report(
    *,
    plan: dict[str, Any],
    search_log_path: Path,
    reviews: list[dict[str, Any]],
    search_log_ref: str,
    include_unexecuted: bool,
) -> dict[str, Any]:
    attempts_by_id = parse_search_attempts(search_log_path) if search_log_path.exists() else {}
    formal_attempt_ids = _formal_attempts(attempts_by_id)
    attempts_by_instruction: dict[str, list[dict[str, str]]] = {}
    for attempt in attempts_by_id.values():
        for fs_id in _attempt_instruction_ids(attempt):
            attempts_by_instruction.setdefault(fs_id, []).append(attempt)

    issue_results: list[dict[str, Any]] = []
    covered_issue_areas: set[str] = set()
    thin_or_unresolved: list[str] = []
    unavailable: list[str] = []
    fs_status_rows: list[dict[str, Any]] = []
    high_priority_below_minimum: list[str] = []
    fs_rows_executed_with_evidence = 0
    fs_rows_executed_without_evidence = 0
    fs_rows_not_executed = 0

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

        terminal_status, downstream_permission = _terminal_status(
            attempts=attempts,
            usable_reviews=usable_reviews,
            instruction=instruction,
        )
        actual_attempt_count = len(attempt_ids)
        minimum_actual_searches = int(instruction.get("minimum_actual_searches") or 0)
        if actual_attempt_count < minimum_actual_searches:
            high_priority_below_minimum.append(fs_id)
        if terminal_status == "executed_with_evidence":
            fs_rows_executed_with_evidence += 1
        elif terminal_status == "executed_no_usable_source":
            fs_rows_executed_without_evidence += 1
        elif terminal_status in {"not_executed", "accounting_only"}:
            fs_rows_not_executed += 1

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
            if terminal_status == "accounting_only":
                limitations = ["This planned FS-xxx row is accounting_only and has no actual S-xxx search attempt."]
                findings_summary = "Coverage-audit row has not been researched because it may be immaterial after scoping."
                handling = "Keep as research gap/backlog or mark not_material in final execution accounting; do not use as evidence."
            else:
                limitations = ["No S-xxx search attempt is linked to this planned FS-xxx instruction."]
                findings_summary = "Planned formal search instruction has not been executed."
                handling = "Run the real formal search, append an S-xxx entry to search_log.md, or explicitly keep this as not_executed/not_material backlog."
            unavailable.append(f"{instruction['issue_area']}/{instruction['subissue']}")

        result_id = f"FR-{len(issue_results) + 1:03d}"
        issue_results.append(
            {
                "result_id": result_id,
                "issue_area": instruction["issue_area"],
                "subissue": instruction["subissue"],
                "research_question": instruction["research_question"],
                "status": status,
                "terminal_status": terminal_status,
                "downstream_permission": downstream_permission,
                "minimum_actual_searches": minimum_actual_searches,
                "actual_search_attempt_count": actual_attempt_count,
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
        fs_status_rows.append(
            {
                "fs_id": fs_id,
                "result_id": result_id,
                "issue_area": instruction["issue_area"],
                "subissue": instruction["subissue"],
                "execution_expectation": _text(instruction.get("execution_expectation")),
                "minimum_actual_searches": minimum_actual_searches,
                "actual_search_attempt_ids": attempt_ids,
                "actual_search_attempt_count": actual_attempt_count,
                "terminal_status": terminal_status,
                "downstream_permission": downstream_permission,
            }
        )

    return {
        "schema_version": "formal_research_execution_report_v1",
        "formal_research_completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "search_log": search_log_ref,
        "issue_results": issue_results,
        "coverage_summary": {
            "planned_fs_rows": len(_planned_instructions(plan)),
            "actual_search_attempts": len(formal_attempt_ids),
            "fs_rows_accounted": len(fs_status_rows),
            "fs_rows_executed_with_evidence": fs_rows_executed_with_evidence,
            "fs_rows_executed_without_evidence": fs_rows_executed_without_evidence,
            "fs_rows_not_executed": fs_rows_not_executed,
            "high_priority_rows_below_minimum": sorted(set(high_priority_below_minimum)),
            "covered_issue_areas": sorted(covered_issue_areas),
            "thin_or_unresolved_subissues": sorted(set(thin_or_unresolved)),
            "not_available_after_research": sorted(set(unavailable)),
        },
        "fs_row_execution_status": fs_status_rows,
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
