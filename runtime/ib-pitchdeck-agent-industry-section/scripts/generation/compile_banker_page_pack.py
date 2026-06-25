#!/usr/bin/env python3
"""Compile banker_page_pack.json into renderer-facing artifacts."""

from __future__ import annotations

import sys as _ib_sys
from pathlib import Path as _IbPath

_IB_ROLE_SCRIPT_DIR = _IbPath(__file__).resolve().parent
_IB_RUNTIME_ROOT = next(
    _p for _p in _IbPath(__file__).resolve().parents
    if (_p / "configs").is_dir() and (_p / "scripts").is_dir()
)
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts" / "_lib"
_IB_ROLE_SCRIPT_DIRS = sorted(_p for _p in (_IB_RUNTIME_ROOT / "scripts").iterdir() if _p.is_dir())
_IB_QC_VALIDATOR_DIRS = sorted((_IB_RUNTIME_ROOT / "scripts" / "qc" / "validators").glob("*"))
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
from pathlib import Path
from typing import Any

from deck_blueprint_utils import (
    FIXED_PAGE_ROLES,
    as_list,
    banker_page_id_for_slide,
    metric_ids_from_visual,
    proof_points_from_blueprint_slide,
    unique,
    visual_plan_from_blueprint_slide,
)
from json_utils import load_json_file
from renderer_compile_utils import build_renderer_spec_from_deck_blueprint


def text(value: Any) -> str:
    return str(value or "").strip()


def _ids_from_blocks(slide: dict[str, Any], field: str) -> list[str]:
    values: list[str] = []
    for block in as_list(slide.get("body_blocks")):
        if isinstance(block, dict):
            values.extend(text(item) for item in as_list(block.get(field)) if text(item))
    return values


def _metric_ids_from_visible_claims(slide: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for claim in as_list(slide.get("visible_metric_claims")):
        if isinstance(claim, dict):
            values.extend(text(item) for item in as_list(claim.get("metric_ids")) if text(item))
    return values


def _evidence_status(claim_strength: str) -> str:
    if claim_strength in {"hard_fact", "supported_inference"}:
        return "supported"
    if claim_strength in {"directional_inference", "management_claim"}:
        return "thin"
    if claim_strength == "hypothesis":
        return "caveat_only"
    return "not_researched"


def _allowed_usage(claim_strength: str) -> str:
    if claim_strength in {"hard_fact", "supported_inference"}:
        return "headline_allowed"
    if claim_strength in {"directional_inference", "management_claim"}:
        return "body_only"
    if claim_strength == "hypothesis":
        return "caveat_only"
    return "not_allowed"


def _permission(usage: str) -> dict[str, bool]:
    return {
        "headline_allowed": usage == "headline_allowed",
        "main_message_allowed": usage == "headline_allowed",
        "chart_allowed": usage in {"headline_allowed", "body_only"},
        "body_copy_allowed": usage in {"headline_allowed", "body_only", "supporting_context", "context_only", "caveat_only"},
    }


def build_internal_deck_blueprint(banker_page_pack: dict[str, Any]) -> dict[str, Any]:
    slides: list[dict[str, Any]] = []
    for slide in as_list(banker_page_pack.get("slides")):
        if not isinstance(slide, dict):
            continue
        slide_no = int(slide.get("slide_no") or len(slides) + 1)
        banker_page_id = text(slide.get("banker_page_id")) or f"BP-{slide_no:03d}"
        project_relevance_note = text(slide.get("project_relevance_note"))
        blocks: list[dict[str, Any]] = []
        for block in as_list(slide.get("body_blocks")):
            if not isinstance(block, dict):
                continue
            item = dict(block)
            item.setdefault("source_banker_page_ids", [banker_page_id])
            if not text(item.get("claim_strength")):
                item["claim_strength"] = text(slide.get("claim_strength"))
            blocks.append(item)
        slides.append(
            {
                "slide_no": slide_no,
                "banker_page_id": banker_page_id,
                "fixed_page_role": text(slide.get("fixed_page_role")) or FIXED_PAGE_ROLES.get(slide_no, ""),
                "page_primary_subject": text(slide.get("page_primary_subject")),
                "investor_question": text(slide.get("client_question")),
                "page_thesis": text(slide.get("banker_judgment")),
                "page_argument": text(slide.get("page_argument")),
                "visual_intent": text(slide.get("visual_intent") or slide.get("exhibit", {}).get("why_this_exhibit")),
                "evidence_role": text(slide.get("evidence_role") or "thesis_anchor"),
                "exhibit": slide.get("exhibit") if isinstance(slide.get("exhibit"), dict) else {},
                "why_this_page_matters": project_relevance_note,
                "selected_page_type": text(slide.get("selected_page_type")),
                "claim_strength": text(slide.get("claim_strength")),
                "headline": text(slide.get("headline")),
                "main_message": text(slide.get("main_message")),
                "body_blocks": blocks,
                "body_copy": slide.get("body_copy") if isinstance(slide.get("body_copy"), dict) else {},
                "visual_design": slide.get("visual_design") if isinstance(slide.get("visual_design"), dict) else {},
                "chart_data": slide.get("chart_data") if isinstance(slide.get("chart_data"), dict) else {},
                "compare_table_data": slide.get("compare_table_data") if isinstance(slide.get("compare_table_data"), dict) else {},
                "visible_metric_claims": [item for item in as_list(slide.get("visible_metric_claims")) if isinstance(item, dict)],
                "source_note": text(slide.get("source_note")),
                "pitch_relevance": project_relevance_note,
                "caveats": [text(item) for item in as_list(slide.get("caveats")) if text(item)],
                "open_questions": [text(item) for item in as_list(slide.get("open_questions")) if text(item)],
                "strategy_checks": {
                    "new_information_added": [
                        text(slide.get("banker_judgment")),
                        project_relevance_note,
                    ],
                    "source_artifact": "banker_page_pack.json",
                },
                "derived_from": "banker_page_pack",
            }
        )
    return {
        "schema_version": "deck_blueprint_v1",
        "section_meta": banker_page_pack.get("section_meta") if isinstance(banker_page_pack.get("section_meta"), dict) else {},
        "deck_storyline": text(banker_page_pack.get("deck_storyline")),
        "slides": sorted(slides, key=lambda item: int(item.get("slide_no") or 0)),
        "authoring_status": "derived_from_banker_page_pack",
    }


def _visual_metric_ids(slide: dict[str, Any]) -> list[str]:
    return unique(metric_ids_from_visual(slide) + _metric_ids_from_visible_claims(slide))


def _metric_ids_for_slide(slide: dict[str, Any]) -> list[str]:
    return unique(
        [text(item) for item in as_list(slide.get("metric_ids")) if text(item)]
        + _ids_from_blocks(slide, "metric_ids")
        + _visual_metric_ids(slide)
    )


def _evidence_ids_for_slide(slide: dict[str, Any]) -> list[str]:
    return unique(
        [text(item) for item in as_list(slide.get("evidence_ids")) if text(item)]
        + _ids_from_blocks(slide, "evidence_ids")
    )


def _proof_standard(claim_strength: str, usage: str) -> str:
    if usage == "headline_allowed":
        return "Headline, main message, body copy, and material visuals may use this page's EV/MET IDs."
    if usage == "body_only":
        return "Use this page's EV/MET IDs in body copy and supporting visuals; avoid unqualified headline claims."
    if usage == "caveat_only":
        return "Use only as caveated context or route back to Research before promotion."
    return "Do not use as a deck claim until LLM authoring resolves evidence sufficiency."


def build_banker_page_contract(deck_blueprint: dict[str, Any]) -> dict[str, Any]:
    contract_slides: list[dict[str, Any]] = []
    for slide in as_list(deck_blueprint.get("slides")):
        if not isinstance(slide, dict):
            continue
        slide_no = int(slide.get("slide_no") or len(contract_slides) + 1)
        banker_page_id = banker_page_id_for_slide(slide) or f"BP-{slide_no:03d}"
        claim_strength = text(slide.get("claim_strength"))
        usage = _allowed_usage(claim_strength)
        permission = _permission(usage)
        proof_points = proof_points_from_blueprint_slide(slide)
        body_evidence_ids = unique(
            _evidence_ids_for_slide(slide)
            + [
                text(item)
                for point in proof_points
                for item in as_list(point.get("evidence_ids"))
                if text(item)
            ]
        )
        body_metric_ids = unique(
            _metric_ids_for_slide(slide)
            + [
                text(item)
                for point in proof_points
                for item in as_list(point.get("metric_ids"))
                if text(item)
            ]
        )
        visual_plan = visual_plan_from_blueprint_slide(slide)
        visual_metric_ids = unique(_visual_metric_ids(slide) + [text(item) for item in as_list(visual_plan.get("visual_metric_ids")) if text(item)])
        chart_metric_ids = visual_metric_ids if visual_plan.get("required_capability") == "chart" else []
        contract_slides.append(
            {
                "slide_no": slide_no,
                "banker_page_id": banker_page_id,
                "page_role": text(slide.get("fixed_page_role") or slide.get("page_role")) or FIXED_PAGE_ROLES.get(slide_no, ""),
                "page_question": text(slide.get("investor_question") or slide.get("client_question")),
                "headline_claim": text(slide.get("headline")),
                "proof_standard": _proof_standard(claim_strength, usage),
                "headline_allowed": permission["headline_allowed"],
                "main_message_allowed": permission["main_message_allowed"],
                "downstream_permission": permission,
                "evidence_status": _evidence_status(claim_strength),
                "chart_allowed": permission["chart_allowed"],
                "visual_metric_allowed": permission["chart_allowed"] and bool(visual_metric_ids),
                "chart_metric_ids": chart_metric_ids,
                "allowed_visual_metric_ids": visual_metric_ids if permission["chart_allowed"] else [],
                "body_evidence_ids": body_evidence_ids if permission["body_copy_allowed"] else [],
                "body_metric_ids": body_metric_ids if permission["body_copy_allowed"] else [],
                "proof_points": proof_points if permission["body_copy_allowed"] else [],
                "claim_strength": claim_strength,
                "evidence_gap_handling": text(
                    visual_plan.get("fallback_if_data_insufficient")
                    or slide.get("evidence_gap_handling")
                    or "Route back to banker_page_pack if evidence is insufficient."
                ),
                "caveats": [text(item) for item in as_list(slide.get("caveats")) if text(item)],
                "open_questions": [text(item) for item in as_list(slide.get("open_questions")) if text(item)],
            }
        )
    return {"schema_version": "page_evidence_contract_v1", "slides": sorted(contract_slides, key=lambda item: int(item.get("slide_no") or 0))}


def compile_banker_page_pack(
    banker_page_pack: dict[str, Any],
    template_registry: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    deck_blueprint = build_internal_deck_blueprint(banker_page_pack)
    page_contract = build_banker_page_contract(deck_blueprint)
    renderer_spec = build_renderer_spec_from_deck_blueprint(deck_blueprint, template_registry, page_contract)
    return deck_blueprint, page_contract, renderer_spec


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--banker-page-pack", required=True)
    parser.add_argument("--template-registry", required=True)
    parser.add_argument("--deck-blueprint-output")
    parser.add_argument("--page-contract-output", required=True)
    parser.add_argument("--renderer-spec-output", required=True)
    args = parser.parse_args()

    deck_blueprint, page_contract, renderer_spec = compile_banker_page_pack(
        load_json_file(Path(args.banker_page_pack)),
        load_json_file(Path(args.template_registry)),
    )
    if args.deck_blueprint_output:
        _write_json(Path(args.deck_blueprint_output), deck_blueprint)
    _write_json(Path(args.page_contract_output), page_contract)
    _write_json(Path(args.renderer_spec_output), renderer_spec)
    print(
        json.dumps(
            {
                "is_valid": True,
                "source": str(Path(args.banker_page_pack)),
                "deck_blueprint_output": args.deck_blueprint_output or "",
                "page_contract_output": args.page_contract_output,
                "renderer_spec_output": args.renderer_spec_output,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
