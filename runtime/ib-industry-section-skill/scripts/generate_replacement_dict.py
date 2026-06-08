#!/usr/bin/env python3

import argparse
import json
from pathlib import Path
from typing import Optional

from gate_guard import require_pre_ppt_gate
from json_utils import load_json_file
from renderer_token_source import build_token_source


TOP_LEVEL_FIELDS = {
    "selected_page_type",
    "slide_title",
    "main_takeaway",
    "chart_title",
    "source_footer",
    "speaker_note",
}

BULLET_PREFIX = "• "


def should_prefix_bullet(field_name: str) -> bool:
    lowered = field_name.lower()
    if lowered in TOP_LEVEL_FIELDS:
        return False
    if any(key in lowered for key in ("table_", "matrix_label", "matrix_title", "chart_", "source")):
        return False
    return True


def ensure_bullet_prefix(value: str, field_name: str) -> str:
    text = value.strip()
    if not text or not should_prefix_bullet(field_name):
        return value
    if text.startswith(("•", "-", "–", "—")):
        return text
    return BULLET_PREFIX + text


def load_json(path: Path):
    return load_json_file(path)


def get_slide_lookup(token_source: dict) -> dict:
    slides = token_source.get("slides", [])
    lookup = {}
    for slide in slides:
        slide_no = slide.get("slide_no")
        if slide_no is not None:
            lookup[int(slide_no)] = slide
    return lookup


def resolve_field(slide: Optional[dict], field_name: str):
    if not slide:
        return ""
    if field_name in TOP_LEVEL_FIELDS:
        return slide.get(field_name, "")
    return slide.get("content", {}).get(field_name, "")


def stringify_value(value):
    if isinstance(value, list):
        return "; ".join(str(item) for item in value if item not in (None, ""))
    if isinstance(value, dict):
        return "; ".join(
            f"{k}: {v}" for k, v in value.items() if v not in (None, "", [], {})
        )
    if value is None:
        return ""
    return str(value)


def determine_selected_page_type(slide: Optional[dict]) -> str:
    if slide and slide.get("selected_page_type"):
        return str(slide["selected_page_type"])
    return ""


def add_tokens_for_variant(replacements, tokens, slide, keep_unmapped_empty, force_include=False):
    for token in tokens:
        placeholder = token["placeholder"]
        field_name = token["field_name"]
        value = stringify_value(resolve_field(slide, field_name))
        value = ensure_bullet_prefix(value, field_name)
        if force_include or value or keep_unmapped_empty:
            replacements[placeholder] = value


def build_replacement_dict(
    token_source: dict,
    ppt_mapping: dict,
    keep_unmapped_empty: bool,
    *,
    renderer_spec_path: Path,
    ppt_mapping_path: Path,
) -> dict:
    slide_lookup = get_slide_lookup(token_source)
    replacements = {}

    for mapping_slide in ppt_mapping.get("slides", []):
        slide_no = int(mapping_slide["slide_no"])
        slide = slide_lookup.get(slide_no)

        if "tokens" in mapping_slide:
            add_tokens_for_variant(
                replacements,
                mapping_slide["tokens"],
                slide,
                keep_unmapped_empty,
                force_include=True,
            )
            continue

        controlled_variants = mapping_slide.get("controlled_variants", {})
        selected_page_type = determine_selected_page_type(slide)

        if controlled_variants and not selected_page_type:
            raise ValueError(
                f"Missing selected_page_type for slide_no={slide_no}, slide_key={mapping_slide.get('slide_key', '')}. "
                f"Expected one of: {', '.join(controlled_variants.keys())}. "
                f"Checked renderer_spec={renderer_spec_path}."
            )
        if selected_page_type and selected_page_type not in controlled_variants:
            allowed = ", ".join(controlled_variants.keys())
            raise ValueError(
                f"Invalid selected_page_type in slide_no={slide_no}, slide_key={mapping_slide.get('slide_key', '')}. "
                f"Found '{selected_page_type}' in renderer-spec-derived token source={renderer_spec_path}. "
                f"Allowed values: {allowed}. Mapping file: {ppt_mapping_path}."
            )

        active_variant_key = selected_page_type

        for page_type, variant in controlled_variants.items():
            is_active = page_type == active_variant_key
            if is_active:
                add_tokens_for_variant(
                    replacements,
                    variant.get("tokens", []),
                    slide,
                    keep_unmapped_empty,
                    force_include=True,
                )
            else:
                for token in variant.get("tokens", []):
                    replacements[token["placeholder"]] = ""

    return replacements


def build_token_source_from_renderer_spec(renderer_spec: dict) -> dict:
    """Build the internal token source directly from the canonical renderer spec."""
    result = build_token_source(renderer_spec)
    warnings = result.get("warnings") or []
    blocking = [
        warning for warning in warnings
        if "missing active body_copy fields" in warning
        or "empty active body_copy fields" in warning
        or "extra body_copy fields ignored" in warning
    ]
    if blocking:
        raise ValueError("renderer_spec cannot be converted into token source: " + "; ".join(blocking))
    return result["token_source"]


def main():
    parser = argparse.ArgumentParser(
        description="Generate a PPT placeholder replacement dictionary from renderer_spec.json."
    )
    parser.add_argument(
        "--renderer-spec",
        default="renderer_spec.json",
        help="Path to the canonical renderer_spec JSON file.",
    )
    parser.add_argument(
        "--ppt-mapping",
        default="templates/ppt_mapping.json",
        help="Path to the ppt mapping JSON file.",
    )
    parser.add_argument(
        "--output",
        default="replacement_dict.json",
        help="Path to write the replacement dictionary JSON file.",
    )
    parser.add_argument(
        "--keep-empty",
        action="store_true",
        help="Active placeholders are included with empty-string values by default.",
    )
    parser.add_argument(
        "--allow-ungated-debug",
        action="store_true",
        help="Allow replacement_dict output without a passing pre-PPT gate only when IB_SKILL_ALLOW_UNGATED_DEBUG=1 is set.",
    )
    args = parser.parse_args()

    renderer_spec_path = Path(args.renderer_spec)
    ppt_mapping_path = Path(args.ppt_mapping)
    output_path = Path(args.output)
    try:
        require_pre_ppt_gate(output_path.parent, allow_ungated_debug=args.allow_ungated_debug)
    except Exception as exc:
        raise SystemExit(str(exc)) from exc

    try:
        renderer_spec = load_json(renderer_spec_path)
        ppt_mapping = load_json(ppt_mapping_path)
        token_source = build_token_source_from_renderer_spec(renderer_spec)
    except Exception as exc:
        raise SystemExit(str(exc)) from exc
    try:
        replacements = build_replacement_dict(
            token_source,
            ppt_mapping,
            args.keep_empty,
            renderer_spec_path=renderer_spec_path,
            ppt_mapping_path=ppt_mapping_path,
        )
    except Exception as exc:
        raise SystemExit(str(exc)) from exc

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(replacements, f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
