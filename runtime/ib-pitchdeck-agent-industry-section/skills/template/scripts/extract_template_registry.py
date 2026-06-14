#!/usr/bin/env python3
"""Extract the formal template capability registry from deterministic config files."""

from __future__ import annotations

# Runtime scripts can be run directly. Shared helpers remain in runtime
# `scripts/`; production tools live under role scripts; validators live under QC.
import sys as _ib_sys
from pathlib import Path as _IbPath
_IB_ROLE_SCRIPT_DIR = _IbPath(__file__).resolve().parent
_IB_RUNTIME_ROOT = next(
    _p for _p in _IbPath(__file__).resolve().parents
    if (_p / 'templates').is_dir() and (_p / 'skills').is_dir() and (_p / 'scripts').is_dir()
)
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts"
_IB_ROLE_SCRIPT_DIRS = sorted((_IB_RUNTIME_ROOT / 'skills').glob('*/scripts'))
_IB_QC_VALIDATOR_DIRS = sorted((_IB_RUNTIME_ROOT / 'skills' / 'qc' / 'scripts' / 'validators').glob('*'))
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

from json_utils import load_json_file


ROOT = _IB_RUNTIME_ROOT
FIXED_PAGE_ROLES = {
    1: "industry_overview",
    2: "market_size_segmentation",
    3: "key_industry_drivers",
    4: "value_chain_profit_pool",
    5: "key_barriers_value_drivers",
    6: "competitive_landscape",
    7: "industry_trends_future_evolution",
    8: "transaction_implications",
}


def _load(path: Path) -> dict[str, Any]:
    data = load_json_file(path)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _ppt_mapping_by_slide(ppt_mapping: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {
        int(item["slide_no"]): item
        for item in ppt_mapping.get("slides", [])
        if isinstance(item, dict) and isinstance(item.get("slide_no"), int)
    }


def _layout_binding_by_slide(ppt_mapping: dict[str, Any]) -> dict[int, dict[str, Any]]:
    raw = ppt_mapping.get("layout_binding_by_slide", {})
    if not isinstance(raw, dict):
        return {}
    return {int(key): value for key, value in raw.items() if str(key).isdigit() and isinstance(value, dict)}


def _supports(renderer: str, page_type: str, deck_contract: dict[str, Any]) -> dict[str, bool]:
    required = set(deck_contract.get("required_objects") or [])
    preferred = set(deck_contract.get("preferred_objects") or [])
    objects = required | preferred
    return {
        "chart": "chart" in objects or "chart" in renderer or "chart" in page_type,
        "table": "table" in objects or "table" in renderer or "table" in page_type,
        "matrix": "matrix" in renderer or "matrix" in page_type,
        "cards": "card" in renderer or "card" in page_type or page_type in {"moat_page", "trend_page"},
    }


def _variant_field_roles(
    slide_no: int,
    page_type: str,
    ppt_mapping_by_slide: dict[int, dict[str, Any]],
    layout_binding: dict[int, dict[str, Any]],
) -> dict[str, str]:
    binding = layout_binding.get(slide_no, {})
    if page_type in (binding.get("variants") or {}):
        return dict((binding["variants"][page_type].get("field_roles") or {}))
    if binding.get("selected_page_type") == page_type:
        return dict(binding.get("field_roles") or {})

    mapping_entry = ppt_mapping_by_slide.get(slide_no, {})
    if "tokens" in mapping_entry:
        return {
            token.get("field_name", ""): token.get("role", token.get("field_name", ""))
            for token in mapping_entry.get("tokens", [])
            if isinstance(token, dict) and token.get("field_name")
        }
    variant = (mapping_entry.get("controlled_variants") or {}).get(page_type, {})
    return {
        token.get("field_name", ""): token.get("role", token.get("field_name", ""))
        for token in variant.get("tokens", [])
        if isinstance(token, dict) and token.get("field_name")
    }


def build_registry(
    *,
    template: Path,
    slide_registry_path: Path,
    page_type_rules_path: Path,
    ppt_mapping_path: Path,
    layout_budget_path: Path,
    text_fit_rules_path: Path,
) -> dict[str, Any]:
    slide_registry = _load(slide_registry_path)
    page_type_rules = _load(page_type_rules_path)
    ppt_mapping = _load(ppt_mapping_path)
    layout_budget = _load(layout_budget_path)
    text_fit_rules = _load(text_fit_rules_path)

    allowed_by_slide = {
        int(item["slide_no"]): set(item.get("page_types") or [])
        for item in page_type_rules.get("slides", [])
        if isinstance(item, dict) and isinstance(item.get("slide_no"), int)
    }
    ppt_mapping_by_slide = _ppt_mapping_by_slide(ppt_mapping)
    layout_binding = _layout_binding_by_slide(ppt_mapping)
    budget_by_key = layout_budget.get("slide_budgets", {}) if isinstance(layout_budget, dict) else {}
    text_fit_by_key = text_fit_rules.get("fields", {}) if isinstance(text_fit_rules, dict) else {}

    slides = []
    for item in slide_registry.get("slides", []):
        slide_no = int(item.get("slide_no"))
        variants = []
        for page_type, variant in (item.get("variants") or {}).items():
            renderer_contract = variant.get("renderer_contract") or {}
            token_contract = variant.get("token_contract") or {}
            field_roles = _variant_field_roles(slide_no, page_type, ppt_mapping_by_slide, layout_binding)
            key = f"{slide_no}:{page_type}"
            variants.append(
                {
                    "page_type": page_type,
                    "renderer": str(variant.get("renderer") or ""),
                    "formal_allowed": page_type in allowed_by_slide.get(slide_no, set()),
                    "render_layout_key": str(variant.get("render_layout_key") or page_type),
                    "physical_slide": str(variant.get("physical_slide") or ""),
                    "supports": _supports(str(variant.get("renderer") or ""), page_type, renderer_contract),
                    "required_body_fields": list(token_contract.get("required_body_fields") or []),
                    "field_roles": field_roles,
                    "capacity_notes": {
                        "layout_budget": budget_by_key.get(key, {}),
                        "text_fit_fields": {
                            field_key: value
                            for field_key, value in text_fit_by_key.items()
                            if str(field_key).startswith(key + ":")
                        },
                    },
                    "deprecation_status": "active" if page_type in allowed_by_slide.get(slide_no, set()) else "deprecated",
                }
            )
        slides.append(
            {
                "slide_no": slide_no,
                "fixed_page_role": FIXED_PAGE_ROLES.get(slide_no, ""),
                "slide_key": str(item.get("slide_key") or ""),
                "selection_mode": str(item.get("selection_mode") or ""),
                "default_variant": str(item.get("default_variant") or ""),
                "variants": variants,
            }
        )

    return {
        "schema_version": "template_registry_v1",
        "template_file": str(template),
        "slides": sorted(slides, key=lambda row: row["slide_no"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", default=str(ROOT / "assets/industry_section_template_master.pptx"))
    parser.add_argument("--slide-registry", default=str(ROOT / "templates/slide_registry.json"))
    parser.add_argument("--page-type-rules", default=str(ROOT / "templates/page_type_rules.json"))
    parser.add_argument("--ppt-mapping", default=str(ROOT / "templates/ppt_mapping.json"))
    parser.add_argument("--layout-budget", default=str(ROOT / "templates/layout_budget.json"))
    parser.add_argument("--text-fit-rules", default=str(ROOT / "templates/text_fit_rules.json"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    registry = build_registry(
        template=Path(args.template),
        slide_registry_path=Path(args.slide_registry),
        page_type_rules_path=Path(args.page_type_rules),
        ppt_mapping_path=Path(args.ppt_mapping),
        layout_budget_path=Path(args.layout_budget),
        text_fit_rules_path=Path(args.text_fit_rules),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"is_valid": True, "output": str(output_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
