#!/usr/bin/env python3
"""Helpers for the LLM-first deck_blueprint artifact."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _runtime_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "configs").is_dir() and (parent / "scripts").is_dir():
            return parent
    raise RuntimeError("Cannot locate runtime root for deck blueprint utils")


def _load_fixed_page_roles() -> dict[int, str]:
    path = _runtime_root() / "configs" / "slide_registry.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    slides = payload.get("slides") if isinstance(payload, dict) else []
    result: dict[int, str] = {}
    for slide in slides if isinstance(slides, list) else []:
        if not isinstance(slide, dict):
            continue
        slide_no = slide.get("slide_no")
        slide_key = str(slide.get("slide_key") or "").strip()
        if isinstance(slide_no, int) and slide_key:
            result[slide_no] = slide_key
    if not result:
        raise ValueError(f"{path} did not define any slide_no / slide_key pairs")
    return result


def _load_generation_policy() -> dict[str, Any]:
    path = _runtime_root() / "configs" / "generation_policy.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _generation_list(key: str) -> list[str]:
    values = _load_generation_policy().get(key)
    if not isinstance(values, list) or not values:
        raise ValueError(f"configs/generation_policy.json must define non-empty list {key}")
    return [str(item).strip() for item in values if str(item).strip()]


def _generation_dict(key: str) -> dict[str, str]:
    values = _load_generation_policy().get(key)
    if not isinstance(values, dict) or not values:
        raise ValueError(f"configs/generation_policy.json must define non-empty object {key}")
    return {str(k).strip(): str(v).strip() for k, v in values.items() if str(k).strip() and str(v).strip()}


def _generation_text(key: str) -> str:
    value = str(_load_generation_policy().get(key) or "").strip()
    if not value:
        raise ValueError(f"configs/generation_policy.json must define non-empty string {key}")
    return value


FIXED_PAGE_ROLES = _load_fixed_page_roles()

VALID_CLAIM_STRENGTHS = set(_generation_list("valid_claim_strengths"))

PAGE_PRIMARY_SUBJECTS = set(_generation_list("page_primary_subjects"))

METRIC_VISUAL_CAPABILITIES = set(_generation_list("metric_visual_capabilities"))

STRUCTURED_EXHIBIT_TYPES = set(_generation_list("structured_exhibit_types"))


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def template_variants_by_slide(template_registry: dict[str, Any]) -> dict[int, dict[str, dict[str, Any]]]:
    result: dict[int, dict[str, dict[str, Any]]] = {}
    for slide in template_registry.get("slides") or []:
        if not isinstance(slide, dict) or not isinstance(slide.get("slide_no"), int):
            continue
        result[int(slide["slide_no"])] = {
            str(variant.get("page_type")): variant
            for variant in slide.get("variants") or []
            if isinstance(variant, dict) and variant.get("page_type")
        }
    return result


def visual_plan_from_blueprint_slide(slide: dict[str, Any]) -> dict[str, Any]:
    visual = slide.get("visual_design") if isinstance(slide.get("visual_design"), dict) else {}
    if not visual and isinstance(slide.get("visual_plan"), dict):
        visual = slide["visual_plan"]
    exhibit = slide.get("exhibit") if isinstance(slide.get("exhibit"), dict) else {}
    selected_page_type = str(slide.get("selected_page_type") or "").strip()
    capability = str(visual.get("required_capability") or visual.get("type") or exhibit.get("exhibit_type") or "").strip()
    capability = _generation_dict("visual_capability_aliases").get(capability, capability)
    if not capability:
        capability = _generation_dict("page_type_default_capabilities").get(selected_page_type, "")
    if not capability:
        capability = _generation_text("default_visual_capability")
    metric_ids = [
        str(item).strip()
        for item in as_list(visual.get("visual_metric_ids") or slide.get("visual_metric_ids"))
        if str(item).strip()
    ]
    if not metric_ids:
        metric_ids = metric_ids_from_visual(slide)
    return {
        "required_capability": capability,
        "preferred_template_variant": selected_page_type,
        "visual_metric_ids": unique(metric_ids),
        "evidence_limited_exhibit_plan": str(
            visual.get("evidence_limited_exhibit_plan")
            or exhibit.get("evidence_limited_exhibit_plan")
            or slide.get("evidence_limited_exhibit_plan")
            or _generation_text("default_evidence_limited_exhibit_plan")
        ).strip(),
    }


def metric_ids_from_visual(slide: dict[str, Any]) -> list[str]:
    ids: list[str] = []

    def scan(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"metric_id", "metric_ids"}:
                    if isinstance(item, list):
                        ids.extend(str(part).strip() for part in item if str(part).strip())
                    else:
                        text = str(item or "").strip()
                        if text:
                            ids.append(text)
                else:
                    scan(item)
        elif isinstance(value, list):
            for item in value:
                scan(item)

    visual_design = slide.get("visual_design") if isinstance(slide.get("visual_design"), dict) else {}
    visual_plan = slide.get("visual_plan") if isinstance(slide.get("visual_plan"), dict) else {}
    scan(visual_design)
    scan(visual_plan)
    scan(slide.get("chart_data"))
    scan(slide.get("compare_table_data"))
    return unique([item for item in ids if item.startswith("MET-")])


def evidence_ids_from_visual(slide: dict[str, Any]) -> list[str]:
    ids: list[str] = []

    def scan(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"evidence_id", "evidence_ids"}:
                    if isinstance(item, list):
                        ids.extend(str(part).strip() for part in item if str(part).strip())
                    else:
                        text = str(item or "").strip()
                        if text:
                            ids.append(text)
                else:
                    scan(item)
        elif isinstance(value, list):
            for item in value:
                scan(item)

    visual_design = slide.get("visual_design") if isinstance(slide.get("visual_design"), dict) else {}
    visual_plan = slide.get("visual_plan") if isinstance(slide.get("visual_plan"), dict) else {}
    scan(visual_design)
    scan(visual_plan)
    scan(slide.get("chart_data"))
    scan(slide.get("compare_table_data"))
    return unique([item for item in ids if item.startswith("EV-")])


def banker_page_id_for_slide(slide: dict[str, Any]) -> str:
    explicit = str(slide.get("banker_page_id") or "").strip()
    if explicit:
        return explicit
    try:
        slide_no = int(slide.get("slide_no") or 0)
    except Exception:
        slide_no = 0
    return f"BP-{slide_no:03d}" if slide_no > 0 else ""


def proof_points_from_blueprint_slide(slide: dict[str, Any]) -> list[dict[str, Any]]:
    banker_page_id = banker_page_id_for_slide(slide)
    points: list[dict[str, Any]] = []
    for block in as_list(slide.get("body_blocks")):
        if not isinstance(block, dict):
            continue
        source_banker_page_ids = [
            str(item).strip()
            for item in as_list(block.get("source_banker_page_ids"))
            if str(item).strip()
        ] or ([banker_page_id] if banker_page_id else [])
        points.append(
            {
                "point": str(block.get("copy") or block.get("point") or "").strip(),
                "banker_page_ids": unique(source_banker_page_ids),
                "evidence_ids": unique([str(item).strip() for item in as_list(block.get("evidence_ids")) if str(item).strip()]),
                "metric_ids": unique([str(item).strip() for item in as_list(block.get("metric_ids")) if str(item).strip()]),
                "claim_strength": str(block.get("claim_strength") or slide.get("claim_strength") or "").strip(),
                "visual_role": str(block.get("role") or block.get("visual_role") or "").strip(),
            }
        )
    visual_metric_ids = metric_ids_from_visual(slide)
    visual_evidence_ids = evidence_ids_from_visual(slide)
    if visual_metric_ids or visual_evidence_ids:
        points.append(
            {
                "point": str(
                    (slide.get("visual_design") if isinstance(slide.get("visual_design"), dict) else {}).get("purpose")
                    or (slide.get("visual_plan") if isinstance(slide.get("visual_plan"), dict) else {}).get("purpose")
                    or "Primary visual evidence"
                ).strip(),
                "banker_page_ids": [banker_page_id] if banker_page_id else [],
                "evidence_ids": visual_evidence_ids,
                "metric_ids": visual_metric_ids,
                "claim_strength": str(slide.get("claim_strength") or "").strip(),
                "visual_role": "primary_visual",
            }
        )
    return [point for point in points if point.get("point") or point.get("evidence_ids") or point.get("metric_ids")]


def normalize_deck_blueprint_for_page_plan(deck_blueprint: dict[str, Any]) -> dict[str, Any]:
    slides = []
    for slide in deck_blueprint.get("slides") or []:
        if not isinstance(slide, dict):
            continue
        slide_no = slide.get("slide_no")
        banker_page_id = banker_page_id_for_slide(slide)
        slides.append(
            {
                "slide_no": slide_no,
                "banker_page_id": banker_page_id,
                "fixed_page_role": slide.get("fixed_page_role") or slide.get("page_role") or FIXED_PAGE_ROLES.get(int(slide_no or 0), ""),
                "page_question": slide.get("page_question", ""),
                "page_answer": slide.get("page_thesis") or slide.get("page_answer") or slide.get("headline") or "",
                "proof_points": proof_points_from_blueprint_slide(slide),
                "visual_plan": visual_plan_from_blueprint_slide(slide),
                "claim_strength": slide.get("claim_strength", ""),
                "caveats": slide.get("caveats", []),
                "evidence_boundary_notes": slide.get("evidence_boundary_notes", []),
                "strategy_checks": slide.get("strategy_checks", {}),
            }
        )
    return {
        "schema_version": "deck_blueprint_page_plan_v1",
        "slides": sorted(slides, key=lambda item: int(item.get("slide_no") or 0)),
    }


def normalize_text(value: Any) -> str:
    raw = str(value or "").strip().lower()
    raw = re.sub(r"^[•\-–—]+\s*", "", raw)
    raw = re.sub(r"[\s\W_]+", "", raw, flags=re.UNICODE)
    return raw
