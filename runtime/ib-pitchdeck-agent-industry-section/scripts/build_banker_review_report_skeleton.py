#!/usr/bin/env python3
"""Build a structured banker-review report skeleton for deck_blueprint QC.

This is not a gate. It creates per-slide review slots and a small set of
mechanical signals so the LLM can review page quality, evidence fit, content
density, and visual support without hand-chasing schema fields.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from json_utils import load_json_file


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _load_optional(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    data = load_json_file(p)
    return data if isinstance(data, dict) else {}


def _slides(data: dict[str, Any]) -> list[dict[str, Any]]:
    raw = data.get("slides")
    if raw is None:
        raw = data.get("pages")
    return [item for item in _as_list(raw) if isinstance(item, dict)]


def _slide_no(slide: dict[str, Any], fallback: int) -> int:
    try:
        return int(slide.get("slide_no") or slide.get("page_no") or fallback)
    except (TypeError, ValueError):
        return fallback


def _body_blocks(slide: dict[str, Any]) -> list[dict[str, Any]]:
    blocks = slide.get("body_blocks")
    return [item for item in _as_list(blocks) if isinstance(item, dict)]


def _wordish_len(text: str) -> int:
    return len(" ".join(text.split()))


def _contract_by_slide(page_contract: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {_slide_no(slide, idx): slide for idx, slide in enumerate(_slides(page_contract), start=1)}


def _renderer_by_slide(renderer_spec: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {_slide_no(slide, idx): slide for idx, slide in enumerate(_slides(renderer_spec), start=1)}


def _block_metric_ids(blocks: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for block in blocks:
        for metric_id in _as_list(block.get("metric_ids")):
            text = _text(metric_id)
            if text and text not in out:
                out.append(text)
    return out


def _block_evidence_ids(blocks: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for block in blocks:
        for evidence_id in _as_list(block.get("evidence_ids")):
            text = _text(evidence_id)
            if text and text not in out:
                out.append(text)
    return out


def _mechanical_flags(slide: dict[str, Any], contract_slide: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    headline = _text(slide.get("headline"))
    main_message = _text(slide.get("main_message"))
    if headline and main_message and headline == main_message:
        flags.append("headline_equals_main_message")
    blocks = _body_blocks(slide)
    if len(blocks) < 3:
        flags.append("low_body_block_count")
    copies = [_text(block.get("copy")) for block in blocks if _text(block.get("copy"))]
    if len(set(copies)) < len(copies):
        flags.append("duplicate_body_copy")
    if sum(_wordish_len(copy) for copy in copies) < 180:
        flags.append("thin_body_copy_density")
    visual = slide.get("visual_design") if isinstance(slide.get("visual_design"), dict) else {}
    required_capability = _text(visual.get("required_capability") or visual.get("type"))
    if required_capability in {"chart", "table", "matrix", "cards"} and not (slide.get("chart_data") or slide.get("compare_table_data")):
        flags.append("visual_intent_without_structured_data")
    contract_caveats = _as_list(contract_slide.get("caveats"))
    if contract_caveats and not _as_list(slide.get("caveats")):
        flags.append("contract_caveats_not_visible_in_blueprint")
    return flags


def build_report(deck_blueprint: dict[str, Any], page_contract: dict[str, Any], renderer_spec: dict[str, Any]) -> dict[str, Any]:
    contract = _contract_by_slide(page_contract)
    renderer = _renderer_by_slide(renderer_spec)
    reviews: list[dict[str, Any]] = []
    for idx, slide in enumerate(_slides(deck_blueprint), start=1):
        slide_no = _slide_no(slide, idx)
        blocks = _body_blocks(slide)
        contract_slide = contract.get(slide_no, {})
        renderer_slide = renderer.get(slide_no, {})
        evidence_ids = _block_evidence_ids(blocks) or _as_list(contract_slide.get("body_evidence_ids"))
        metric_ids = _block_metric_ids(blocks) or _as_list(contract_slide.get("chart_metric_ids"))
        flags = _mechanical_flags(slide, contract_slide)
        reviews.append(
            {
                "slide_no": slide_no,
                "selected_page_type": _text(slide.get("selected_page_type") or renderer_slide.get("selected_page_type")),
                "investor_question": _text(slide.get("investor_question")),
                "page_thesis": _text(slide.get("page_thesis") or slide.get("page_answer")),
                "headline": _text(slide.get("headline") or renderer_slide.get("headline")),
                "main_message": _text(slide.get("main_message") or renderer_slide.get("main_message")),
                "body_block_count": len(blocks),
                "body_copy_char_count": sum(_wordish_len(_text(block.get("copy"))) for block in blocks),
                "evidence_ids": evidence_ids,
                "metric_ids": metric_ids,
                "mechanical_flags": flags,
                "review_status": "pending_llm_banker_review",
                "page_quality": "pending",
                "evidence_support": "pending",
                "copy_density": "pending",
                "visual_support": "pending",
                "repair_target": "deck_blueprint.json",
                "llm_review_instruction": (
                    "Review like a banker: is the page conclusion-led, evidence-backed, dense enough, non-repetitive, and visually supported? "
                    "If not, repair deck_blueprint.json or upstream research/issue analysis, then recompile."
                ),
            }
        )
    return {
        "schema_version": "banker_review_report_skeleton_v1",
        "meta": {
            "created_by": "build_banker_review_report_skeleton.py",
            "created_date": date.today().isoformat(),
            "non_blocking": True,
            "skeleton_note": "LLM must fill review judgments; this file is a page-editor workspace, not a validator.",
        },
        "slide_reviews": reviews,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deck-blueprint", required=True)
    parser.add_argument("--page-contract")
    parser.add_argument("--renderer-spec")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    report = build_report(
        _load_optional(args.deck_blueprint),
        _load_optional(args.page_contract),
        _load_optional(args.renderer_spec),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "is_valid": True,
                "output": str(output_path),
                "slide_review_count": len(report["slide_reviews"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
