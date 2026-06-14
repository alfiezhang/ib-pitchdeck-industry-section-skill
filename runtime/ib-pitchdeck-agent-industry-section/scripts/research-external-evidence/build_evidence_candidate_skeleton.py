#!/usr/bin/env python3
"""Build EV/MET candidate skeleton from formal research and source reviews.

This helper assigns candidate IDs and review workspaces. It does not promote
facts into the Evidence Ledger or Metric Reconciliation. The LLM must extract
source-faithful facts/metrics, decide promotion status, and then promote only
supported rows into artifacts/research_evidence_db.json. The Markdown
industry_research_pack.md is generated from that database.
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


METRIC_HINT_RE = re.compile(
    r"(market size|revenue|gmv|cagr|growth|share|margin|ebitda|profit|multiple|valuation|capacity|utilization|price|volume|规模|收入|增速|增长|份额|利润率|毛利率|净利率|估值|倍数|产能|利用率|价格|销量)",
    flags=re.IGNORECASE,
)


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _load_optional(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    data = load_json_file(p)
    return data if isinstance(data, dict) else {}


def _reviews(data: dict[str, Any]) -> list[dict[str, Any]]:
    raw = data.get("source_reviews")
    if raw is None:
        raw = data.get("reviews")
    return [item for item in _as_list(raw) if isinstance(item, dict)]


def _review_id(review: dict[str, Any]) -> str:
    return _text(review.get("source_review_id") or review.get("review_id") or review.get("source_id") or review.get("id"))


def _review_text(review: dict[str, Any]) -> str:
    parts = [
        _text(review.get("title")),
        _text(review.get("locator")),
        _text(review.get("excerpt")),
        _text(review.get("claim_use_scope")),
    ]
    return " ".join(part for part in parts if part)


def _review_usable(review: dict[str, Any]) -> bool:
    value = review.get("usable_as_evidence")
    return bool(value) if isinstance(value, bool) else False


def _review_attempt_ids(review: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for item in _as_list(review.get("search_attempt_ids")):
        text = _text(item)
        match = re.search(r"(\d+)", text)
        if match:
            result.add(f"S-{int(match.group(1)):03d}")
    return result


def _review_by_id(source_reviews: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {_review_id(review): review for review in _reviews(source_reviews) if _review_id(review)}


def _reviews_for_result(result: dict[str, Any], reviews_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for src_id in [_text(item) for item in _as_list(result.get("source_review_ids")) if _text(item)]:
        review = reviews_by_id.get(src_id)
        if review:
            output.append(review)
    return output


def _metric_candidate_needed(result: dict[str, Any], reviews: list[dict[str, Any]]) -> bool:
    text = " ".join(
        [
            _text(result.get("research_question")),
            _text(result.get("findings_summary")),
            " ".join(_text(item) for item in _as_list(result.get("limitations"))),
            " ".join(_review_text(review) for review in reviews),
        ]
    )
    return bool(METRIC_HINT_RE.search(text))


def build_candidates(execution_report: dict[str, Any], source_reviews: dict[str, Any]) -> dict[str, Any]:
    reviews_by_id = _review_by_id(source_reviews)
    evidence_candidates: list[dict[str, Any]] = []
    metric_candidates: list[dict[str, Any]] = []

    for result in _as_list(execution_report.get("issue_results")):
        if not isinstance(result, dict):
            continue
        result_id = _text(result.get("result_id"))
        reviews = _reviews_for_result(result, reviews_by_id)
        if not reviews:
            evidence_candidates.append(
                {
                    "candidate_evidence_id": f"EV-{len(evidence_candidates) + 1:03d}",
                    "source_execution_result_id": result_id,
                    "issue_area": _text(result.get("issue_area")),
                    "subissue": _text(result.get("subissue")),
                    "source_review_id": "",
                    "source_url": "",
                    "source_locator": "",
                    "candidate_claim_or_metric": "No reviewed source linked yet; add source_reviews or keep this FR as a research gap.",
                    "claim_scope": "",
                    "extraction_status": "needs_source_review",
                    "promotion_decision": "pending_llm_review",
                    "promotion_instruction": "Do not promote without source review locator/excerpt.",
                }
            )
            continue
        for review in reviews:
            src_id = _review_id(review)
            evidence_candidates.append(
                {
                    "candidate_evidence_id": f"EV-{len(evidence_candidates) + 1:03d}",
                    "source_execution_result_id": result_id,
                    "issue_area": _text(result.get("issue_area")),
                    "subissue": _text(result.get("subissue")),
                    "source_review_id": src_id,
                    "source_url": _text(review.get("url")),
                    "source_locator": _text(review.get("locator")),
                    "source_excerpt_or_paraphrase": _text(review.get("excerpt")),
                    "candidate_claim_or_metric": "LLM extracts one source-faithful claim here.",
                    "claim_scope": _text(review.get("claim_use_scope")),
                    "evidence_use_tier": _text(review.get("evidence_use_tier")),
                    "usable_as_evidence": _review_usable(review),
                    "search_attempt_ids": sorted(_review_attempt_ids(review)),
                    "extraction_status": "ready_for_llm_extraction" if _review_usable(review) else "source_not_yet_promotable",
                    "promotion_decision": "pending_llm_review",
                    "promotion_instruction": "Promote to Evidence Ledger only after scope, period, geography, source reliability, and limitation are explicit.",
                }
            )
        if _metric_candidate_needed(result, reviews):
            metric_candidates.append(
                {
                    "candidate_metric_id": f"MET-{len(metric_candidates) + 1:03d}",
                    "source_execution_result_id": result_id,
                    "issue_area": _text(result.get("issue_area")),
                    "subissue": _text(result.get("subissue")),
                    "source_review_ids": [_review_id(review) for review in reviews if _review_id(review)],
                    "metric_name": "LLM extracts metric name from reviewed source.",
                    "metric_type": "",
                    "market_definition": "",
                    "channel_scope": "",
                    "geography": "",
                    "data_period": "",
                    "value": "",
                    "unit": "",
                    "conflict_status": "pending_reconciliation",
                    "chart_ready": False,
                    "promotion_decision": "pending_llm_review",
                    "promotion_instruction": "Promote to Metric Reconciliation only after unit, scope, period, and comparability are clear.",
                }
            )

    return {
        "schema_version": "evidence_candidate_skeleton_v1",
        "meta": {
            "created_by": "build_evidence_candidate_skeleton.py",
            "created_date": date.today().isoformat(),
            "skeleton_note": "Mechanical candidate IDs only; not a validated evidence ledger.",
        },
        "evidence_candidates": evidence_candidates,
        "metric_candidates": metric_candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formal-research-execution-report", required=True)
    parser.add_argument("--source-reviews", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output = build_candidates(
        execution_report=_load_optional(args.formal_research_execution_report),
        source_reviews=_load_optional(args.source_reviews),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "is_valid": True,
                "output": str(output_path),
                "evidence_candidate_count": len(output["evidence_candidates"]),
                "metric_candidate_count": len(output["metric_candidates"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
