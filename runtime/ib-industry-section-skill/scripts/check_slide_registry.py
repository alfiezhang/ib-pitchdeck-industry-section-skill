#!/usr/bin/env python3
"""Check slide-variant config files against slide_registry.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from slide_registry import load_slide_registry, page_type_to_slide_entries, slides_by_no, variant_page_types


ROOT_DIR = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def check_page_type_rules(registry: dict[str, Any], errors: list[str]) -> None:
    page_rules = load_json(ROOT_DIR / "templates" / "page_type_rules.json")
    rule_by_no = {int(item.get("slide_no")): item for item in page_rules.get("slides") or []}
    for slide_no, slide in slides_by_no(registry).items():
        rule = rule_by_no.get(slide_no)
        if not rule:
            errors.append(f"page_type_rules.json missing slide {slide_no}")
            continue
        registry_types = set((slide.get("variants") or {}).keys())
        rule_types = set(rule.get("page_types") or [])
        if registry_types != rule_types:
            errors.append(
                f"slide {slide_no}: page_type_rules page_types {sorted(rule_types)} "
                f"do not match slide_registry variants {sorted(registry_types)}"
            )
        if rule.get("selection_mode") != slide.get("selection_mode"):
            errors.append(
                f"slide {slide_no}: page_type_rules selection_mode {rule.get('selection_mode')!r} "
                f"does not match slide_registry {slide.get('selection_mode')!r}"
            )


def check_slide_layout_library(registry: dict[str, Any], errors: list[str]) -> None:
    layout_library = load_json(ROOT_DIR / "templates" / "slide_layout_library.json")
    expected = page_type_to_slide_entries(registry)
    actual = layout_library.get("slides") or []
    if expected != actual:
        errors.append("slide_layout_library.json does not match slide_registry physical slide mapping")


def check_renderer_spec_schema(registry: dict[str, Any], errors: list[str]) -> None:
    schema = load_json(ROOT_DIR / "templates" / "renderer_spec_schema.json")
    required = set(schema.get("properties", {}).get("slides", {}).get("items", {}).get("required", []))
    expected_required = {
        "slide_no",
        "fixed_page_role",
        "selected_page_type",
        "primary_issue_analysis_id",
        "issue_analysis_ids",
        "claim_strength",
        "headline",
        "main_message",
        "body_copy",
        "source_note",
    }
    missing = sorted(expected_required - required)
    if missing:
        errors.append("renderer_spec_schema missing required slide field(s): " + ", ".join(missing))
    for slide_no, (_binding_key, valid_types) in variant_page_types(registry).items():
        if not valid_types:
            errors.append(f"slide_registry slide {slide_no} has no registered page variants")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check slide registry consistency.")
    parser.add_argument("--registry", default=str(ROOT_DIR / "templates" / "slide_registry.json"))
    args = parser.parse_args()

    registry = load_slide_registry(Path(args.registry))
    errors: list[str] = []
    check_page_type_rules(registry, errors)
    check_slide_layout_library(registry, errors)
    check_renderer_spec_schema(registry, errors)

    report = {"is_valid": not errors, "error_count": len(errors), "errors": errors}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
