#!/usr/bin/env python3

import argparse
import json
from pathlib import Path
from typing import Optional


TOP_LEVEL_FIELDS = {
    "selected_page_type",
    "slide_title",
    "main_takeaway",
    "chart_title",
    "source_footer",
    "speaker_note",
}


def load_json(path: Path):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"JSON file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def get_slide_lookup(ppt_copy: dict) -> dict:
    slides = ppt_copy.get("ppt_copy_slides", [])
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
        if force_include or value or keep_unmapped_empty:
            replacements[placeholder] = value


def build_replacement_dict(
    ppt_copy: dict,
    ppt_mapping: dict,
    keep_unmapped_empty: bool,
    *,
    ppt_copy_path: Path,
    ppt_mapping_path: Path,
) -> dict:
    slide_lookup = get_slide_lookup(ppt_copy)
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
                f"Checked ppt_copy={ppt_copy_path}."
            )
        if selected_page_type and selected_page_type not in controlled_variants:
            allowed = ", ".join(controlled_variants.keys())
            raise ValueError(
                f"Invalid selected_page_type in slide_no={slide_no}, slide_key={mapping_slide.get('slide_key', '')}. "
                f"Found '{selected_page_type}' in ppt_copy={ppt_copy_path}. "
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


def main():
    parser = argparse.ArgumentParser(
        description="Generate a PPT placeholder replacement dictionary from industry_section_ppt_copy.json."
    )
    parser.add_argument(
        "--ppt-copy",
        default="industry_section_ppt_copy.json",
        help="Path to the ppt copy JSON file.",
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
        help="Retained for compatibility. Active placeholders are included with empty-string values by default.",
    )
    args = parser.parse_args()

    ppt_copy_path = Path(args.ppt_copy)
    ppt_mapping_path = Path(args.ppt_mapping)
    output_path = Path(args.output)

    try:
        ppt_copy = load_json(ppt_copy_path)
        ppt_mapping = load_json(ppt_mapping_path)
    except Exception as exc:
        raise SystemExit(str(exc)) from exc
    try:
        replacements = build_replacement_dict(
            ppt_copy,
            ppt_mapping,
            args.keep_empty,
            ppt_copy_path=ppt_copy_path,
            ppt_mapping_path=ppt_mapping_path,
        )
    except Exception as exc:
        raise SystemExit(str(exc)) from exc

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(replacements, f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
