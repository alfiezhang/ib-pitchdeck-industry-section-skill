#!/usr/bin/env python3
"""Load the canonical slide/page-variant registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = ROOT_DIR / "configs" / "slide_registry.json"


def load_slide_registry(path: Optional[Path] = None) -> dict[str, Any]:
    registry_path = path or DEFAULT_REGISTRY_PATH
    with registry_path.open("r", encoding="utf-8") as handle:
        registry = json.load(handle)
    if not isinstance(registry, dict) or not isinstance(registry.get("slides"), list):
        raise ValueError(f"Invalid slide registry: {registry_path}")
    return registry


def slides_by_no(registry: dict[str, Any]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for slide in registry.get("slides") or []:
        slide_no = int(slide.get("slide_no") or 0)
        if not slide_no:
            raise ValueError("slide_registry contains a slide without slide_no")
        if slide_no in result:
            raise ValueError(f"slide_registry contains duplicate slide_no {slide_no}")
        variants = slide.get("variants")
        if not isinstance(variants, dict) or not variants:
            raise ValueError(f"slide_registry slide {slide_no} must define variants")
        result[slide_no] = slide
    return result


def variant_page_types(registry: dict[str, Any]) -> dict[int, tuple[str, set[str]]]:
    variants: dict[int, tuple[str, set[str]]] = {}
    for slide_no, slide in slides_by_no(registry).items():
        if slide.get("selection_mode") != "controlled_choice":
            continue
        binding_key = str(slide.get("binding_key") or "")
        if not binding_key:
            raise ValueError(f"slide_registry slide {slide_no} is controlled_choice but has no binding_key")
        variants[slide_no] = (binding_key, set((slide.get("variants") or {}).keys()))
    return variants


def fixed_page_types(registry: dict[str, Any]) -> dict[int, str]:
    fixed: dict[int, str] = {}
    for slide_no, slide in slides_by_no(registry).items():
        if slide.get("selection_mode") != "fixed":
            continue
        page_types = list((slide.get("variants") or {}).keys())
        if len(page_types) != 1:
            raise ValueError(f"slide_registry fixed slide {slide_no} must have exactly one variant")
        fixed[slide_no] = page_types[0]
    return fixed


def controlled_layout_variants(registry: dict[str, Any]) -> dict[str, list[str]]:
    variants: dict[str, list[str]] = {}
    for slide in registry.get("slides") or []:
        if slide.get("selection_mode") != "controlled_choice":
            continue
        slide_key = str(slide.get("slide_key") or "")
        variants[slide_key] = list((slide.get("variants") or {}).keys())
    return variants


def get_variant_contract(registry: dict[str, Any], slide_no: int, page_type: str) -> dict[str, Any]:
    slide = slides_by_no(registry).get(slide_no)
    if not slide:
        raise KeyError(f"slide {slide_no} is not registered")
    variants = slide.get("variants") or {}
    if page_type not in variants:
        allowed = ", ".join(variants.keys())
        raise KeyError(f"slide {slide_no} page_type {page_type!r} is not registered. Allowed: {allowed}")
    variant = variants[page_type]
    return {
        "slide_no": slide_no,
        "slide_key": slide.get("slide_key", ""),
        "selection_mode": slide.get("selection_mode", ""),
        "binding_key": slide.get("binding_key", ""),
        "page_type": page_type,
        "renderer": variant.get("renderer", ""),
        "render_layout_key": variant.get("render_layout_key", page_type),
        "physical_slide": variant.get("physical_slide", ""),
        "renderer_contract": variant.get("renderer_contract", {}),
        "token_contract": variant.get("token_contract", {}),
    }


def page_type_to_slide_entries(registry: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for slide_no, slide in sorted(slides_by_no(registry).items()):
        entries.append(
            {
                "slide_no": slide_no,
                "slide_key": slide.get("slide_key", ""),
                "page_type_to_slide": {
                    page_type: variant.get("physical_slide", "")
                    for page_type, variant in (slide.get("variants") or {}).items()
                },
            }
        )
    return entries
