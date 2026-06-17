#!/usr/bin/env python3
"""Shared template/page-type contract helpers.

Keep renderer-facing decisions here instead of re-implementing small special
cases across compile, validation, token-source, and post-processing scripts.
"""

from __future__ import annotations

from typing import Any


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def variants_by_slide(template_registry: dict[str, Any]) -> dict[int, dict[str, dict[str, Any]]]:
    """Return slide_no -> page_type -> variant for extracted or static registries."""
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
            for variant in raw_variants:
                if isinstance(variant, dict) and variant.get("page_type"):
                    variants[str(variant.get("page_type"))] = variant
        result[int(slide["slide_no"])] = variants
    return result


def variant_for(template_registry: dict[str, Any], slide_no: int, page_type: str) -> dict[str, Any]:
    return variants_by_slide(template_registry).get(int(slide_no), {}).get(str(page_type), {})


def required_body_fields(template_registry: dict[str, Any], slide_no: int, page_type: str) -> list[str]:
    variant = variant_for(template_registry, slide_no, page_type)
    fields = variant.get("required_body_fields")
    if fields is None and isinstance(variant.get("renderer_contract"), dict):
        fields = variant["renderer_contract"].get("required_body_fields")
    if fields is None and isinstance(variant.get("token_contract"), dict):
        fields = variant["token_contract"].get("required_body_fields")
    return [str(item) for item in _as_list(fields)]


def active_body_fields(required_fields: list[str], page_type: str, slide_data: dict[str, Any]) -> list[str]:
    """Return body fields the LLM/compiler must populate for this page.

    Native-object fields such as Slide 6 compare-table rows are generated from
    structured payloads and should not also be required in body_copy.
    """
    fields = list(required_fields)
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
    """Infer page visual capability from the template variant contract."""
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
    preferred = {str(item).lower() for item in _as_list(contract.get("preferred_objects"))}
    required = {str(item).lower() for item in _as_list(contract.get("required_objects"))}
    conditional = {
        str(item.get("object") or "").lower()
        for item in _as_list(contract.get("conditional_required_objects"))
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
