#!/usr/bin/env python3
"""Helpers for the LLM-first deck_blueprint artifact."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

BP_ID_RE = re.compile(r"^BP-\d{3}$")


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


FIXED_PAGE_ROLES = _load_fixed_page_roles()

DECK_USE_CROSSWALK: dict[str, list[str]] = {
    "not_allowed": ["not allowed", "not for deck", "do not use", "do not use in deck", "不要用于页面", "不可用于页面", "不能用于页面"],
    "caveat_only": ["caveat only", "only with caveat", "caveated only", "with visible caveat", "仅作限定说明", "需加限定", "只可带限定使用"],
    "body_only": ["body only", "body copy only", "body support only", "supporting bullets only", "exhibit only", "chart ready but not headline", "只用于正文", "正文可用", "图表可用但不作标题"],
    "headline_allowed": ["headline ready", "title ready", "can support headline", "can be used as headline", "可作标题", "可做标题", "可用于标题", "标题可用", "可作为主标题"],
    "supporting_context": ["supporting context", "context only", "background context", "supporting evidence only", "背景信息", "支持性信息", "仅作背景"],
}
INTERNAL_DECK_USE_CODES = set(DECK_USE_CROSSWALK)
VISUAL_CAPABILITY_ALIASES = {
    "bar_chart": "chart",
    "line_chart": "chart",
    "stacked_bar": "chart",
    "bubble_chart": "chart",
    "driver_matrix": "matrix",
    "peer_table": "table",
    "comparison_table": "table",
    "fact_cards": "cards",
    "driver_cards": "cards",
    "trend_cards": "cards",
    "kpi_cards": "cards",
    "source_limits_table": "table",
    "peer_comparison": "table",
    "sku_traction_table": "table",
    "flow": "table",
    "bridge": "table",
    "channel_flow": "table",
    "unit_economics_bridge": "table",
    "value_chain": "table",
}
PAGE_TYPE_VISUAL_HINTS = {
    "industry_overview_dynamic_page": "chart",
    "chart_page": "chart",
    "chart_plus_mini_table_page": "chart",
    "compare_table_page": "table",
    "matrix_page": "matrix",
    "driver_card_page": "cards",
    "driver_card_5_page": "cards",
    "driver_card_6_page": "cards",
    "moat_page": "cards",
    "trend_page": "cards",
    "trend_4_card_page": "cards",
    "trend_5_card_page": "cards",
    "trend_6_card_page": "cards",
    "timeline_page": "cards",
    "summary_page": "cards",
}


def compiled_page_role(slide: dict[str, Any], slide_no: int, *, strict_layout: bool = False) -> str:
    explicit = str(slide.get("fixed_page_role") or slide.get("page_role") or "").strip()
    if explicit:
        return explicit
    return FIXED_PAGE_ROLES.get(slide_no, "") if strict_layout else ""


def deck_blueprint_uses_strict_layout(deck_blueprint: dict[str, Any]) -> bool:
    policy = deck_blueprint.get("rendering_policy")
    if not isinstance(policy, dict):
        return False
    return str(policy.get("template_contract_mode") or "").strip() == "strict_layout"


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


def _usage_text(value: Any) -> str:
    return str(value or "").strip()


def _usage_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", _usage_text(value).lower()).strip()


def _usage_alias_match(value: Any) -> str:
    text_value = _usage_key(value)
    if not text_value:
        return ""
    # More restrictive permissions win when a phrase contains multiple cues.
    for canonical in ("not_allowed", "caveat_only", "body_only", "headline_allowed", "supporting_context"):
        for alias in DECK_USE_CROSSWALK.get(canonical, []):
            alias_value = _usage_key(alias)
            if alias_value and (text_value == alias_value or alias_value in text_value):
                return canonical
    return ""


def normalize_allowed_deck_usage(value: Any, *, default: str = "supporting_context") -> str:
    """Map natural deck-use wording to the internal render permission."""
    usage = _usage_text(value)
    if usage in INTERNAL_DECK_USE_CODES:
        return usage
    return _usage_alias_match(value) or default


def ids_from_aliases(source: dict[str, Any], plural_key: str, singular_key: str) -> list[str]:
    values: list[str] = []
    for key in (plural_key, singular_key):
        value = source.get(key)
        items = value if isinstance(value, list) else ([] if value is None else [value])
        values.extend(str(item or "").strip() for item in items if str(item or "").strip())
    return unique(values)


def non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def template_variants_by_slide(template_registry: dict[str, Any]) -> dict[int, dict[str, dict[str, Any]]]:
    result: dict[int, dict[str, dict[str, Any]]] = {}
    for slide in template_registry.get("slides") or []:
        if not isinstance(slide, dict) or not isinstance(slide.get("slide_no"), int):
            continue
        raw_variants = slide.get("variants") or {}
        variants: dict[str, dict[str, Any]] = {}
        if isinstance(raw_variants, dict):
            for page_type, variant in raw_variants.items():
                if isinstance(variant, dict):
                    payload = dict(variant)
                    payload.setdefault("page_type", str(page_type))
                    variants[str(page_type)] = payload
        elif isinstance(raw_variants, list):
            variants = {
                str(variant.get("page_type")): variant
                for variant in raw_variants
                if isinstance(variant, dict) and variant.get("page_type")
            }
        result[int(slide["slide_no"])] = variants
    return result


def variant_for(template_registry: dict[str, Any], slide_no: int, page_type: str) -> dict[str, Any]:
    return template_variants_by_slide(template_registry).get(int(slide_no), {}).get(str(page_type), {})


def strict_layout_body_fields(template_registry: dict[str, Any], slide_no: int, page_type: str) -> list[str]:
    variant = variant_for(template_registry, slide_no, page_type)
    fields = variant.get("strict_layout_body_fields") or variant.get("body_field_hints")
    if fields is None and isinstance(variant.get("renderer_contract"), dict):
        fields = (
            variant["renderer_contract"].get("strict_layout_body_fields")
            or variant["renderer_contract"].get("body_field_hints")
        )
    if fields is None and isinstance(variant.get("token_contract"), dict):
        fields = (
            variant["token_contract"].get("strict_layout_body_fields")
            or variant["token_contract"].get("body_field_hints")
        )
    return [str(item) for item in as_list(fields)]


def active_body_fields(strict_fields: list[str], page_type: str, slide_data: dict[str, Any]) -> list[str]:
    fields = list(strict_fields)
    visual_design = slide_data.get("visual_design") if isinstance(slide_data.get("visual_design"), dict) else {}
    visual_plan = slide_data.get("visual_plan") if isinstance(slide_data.get("visual_plan"), dict) else {}
    if page_type == "compare_table_page" and (
        isinstance(slide_data.get("compare_table_data"), dict)
        or isinstance(visual_design.get("compare_table_data"), dict)
        or isinstance(visual_plan.get("compare_table_data"), dict)
    ):
        fields = [
            field
            for field in fields
            if not (field == "table_header" or field.startswith("table_row_"))
        ]
    return fields


def page_type_capability(template_registry: dict[str, Any], slide_no: int, page_type: str) -> str:
    variant = variant_for(template_registry, slide_no, page_type)
    supports = variant.get("supports") if isinstance(variant.get("supports"), dict) else {}
    if supports.get("chart"):
        return "chart"
    if supports.get("table"):
        return "table"
    if supports.get("matrix"):
        return "matrix"
    if supports.get("cards"):
        return "cards"

    contract = variant.get("renderer_contract") if isinstance(variant.get("renderer_contract"), dict) else {}
    preferred = {str(item).lower() for item in as_list(contract.get("preferred_objects"))}
    required = {str(item).lower() for item in as_list(contract.get("strict_layout_objects"))}
    conditional = {
        str(item.get("object") or "").lower()
        for item in as_list(contract.get("conditional_strict_layout_objects"))
        if isinstance(item, dict)
    }
    objects = preferred | required | conditional
    if "chart" in objects:
        return "chart"
    if "table" in objects:
        return "table"

    page_type = str(page_type)
    if "chart" in page_type or page_type == "industry_overview_dynamic_page":
        return "chart"
    if "table" in page_type:
        return "table"
    if "matrix" in page_type:
        return "matrix"
    if "card" in page_type or page_type in {"moat_page", "trend_page", "summary_page"}:
        return "cards"
    return "text"


def page_type_has_chart(template_registry: dict[str, Any], slide_no: int, page_type: str) -> bool:
    return page_type_capability(template_registry, slide_no, page_type) == "chart"


def visual_plan_from_blueprint_slide(slide: dict[str, Any]) -> dict[str, Any]:
    visual = slide.get("visual_design") if isinstance(slide.get("visual_design"), dict) else {}
    if not visual and isinstance(slide.get("visual_plan"), dict):
        visual = slide["visual_plan"]
    exhibit = slide.get("exhibit") if isinstance(slide.get("exhibit"), dict) else {}
    selected_page_type = str(slide.get("selected_page_type") or "").strip()
    capability = str(visual.get("visual_type") or visual.get("type") or exhibit.get("exhibit_type") or "").strip()
    capability = VISUAL_CAPABILITY_ALIASES.get(capability, capability)
    if not capability:
        capability = PAGE_TYPE_VISUAL_HINTS.get(selected_page_type, "")
    if not capability:
        capability = "text"
    metric_ids = [
        str(item).strip()
        for item in as_list(visual.get("visual_metric_ids") or slide.get("visual_metric_ids"))
        if str(item).strip()
    ]
    if not metric_ids:
        metric_ids = metric_ids_from_visual(slide)
    return {
        "visual_type": capability,
        "preferred_template_variant": selected_page_type,
        "visual_metric_ids": unique(metric_ids),
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
    if explicit and BP_ID_RE.fullmatch(explicit):
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
                "point": str(block.get("copy") or block.get("point") or block.get("text") or "").strip(),
                "banker_page_ids": unique(source_banker_page_ids),
                "evidence_ids": ids_from_aliases(block, "evidence_ids", "evidence_id"),
                "metric_ids": ids_from_aliases(block, "metric_ids", "metric_id"),
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
                "visual_role": "primary_visual",
            }
        )
    return [point for point in points if point.get("point") or point.get("evidence_ids") or point.get("metric_ids")]


def normalize_deck_blueprint_for_page_plan(deck_blueprint: dict[str, Any]) -> dict[str, Any]:
    slides = []
    strict_layout = deck_blueprint_uses_strict_layout(deck_blueprint)
    for slide in deck_blueprint.get("slides") or []:
        if not isinstance(slide, dict):
            continue
        slide_no = slide.get("slide_no")
        resolved_slide_no = int(slide_no or 0)
        banker_page_id = banker_page_id_for_slide(slide)
        slides.append(
            {
                "slide_no": slide_no,
                "banker_page_id": banker_page_id,
                "fixed_page_role": compiled_page_role(slide, resolved_slide_no, strict_layout=strict_layout),
                "page_answer": slide.get("page_thesis") or slide.get("page_answer") or slide.get("headline") or "",
                "proof_points": proof_points_from_blueprint_slide(slide),
                "visual_plan": visual_plan_from_blueprint_slide(slide),
                "caveats": slide.get("caveats", []),
                "source_limitations": slide.get("source_limitations", []),
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
