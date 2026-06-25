#!/usr/bin/env python3
"""Check slide_registry coverage across renderer/layout/template/token mapping."""

from __future__ import annotations

# Runtime scripts can be run directly. Shared helpers remain in runtime
# `scripts/`; production tools live under role scripts; validators live under QC.
import sys as _ib_sys
from pathlib import Path as _IbPath
_IB_ROLE_SCRIPT_DIR = _IbPath(__file__).resolve().parent
_IB_REPO_ROOT = _IbPath(__file__).resolve().parents[2]
_IB_RUNTIME_ROOT = _IB_REPO_ROOT / "runtime" / "ib-pitchdeck-agent-industry-section"
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts"
_IB_ROLE_SCRIPT_DIRS = sorted(_p for _p in (_IB_RUNTIME_ROOT / 'scripts').iterdir() if _p.is_dir())
_IB_QC_VALIDATOR_DIRS = sorted((_IB_RUNTIME_ROOT / 'scripts' / 'qc' / 'validators').glob('*'))
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
import sys
from pathlib import Path
from zipfile import ZipFile
from typing import Any

from json_utils import load_json_file
from slide_registry import load_slide_registry, slides_by_no


ROOT_DIR = _IB_RUNTIME_ROOT
KNOWN_RENDERERS = {
    "overview_dynamic",
    "overview_summary",
    "chart",
    "chart_plus_table",
    "driver_cards",
    "value_chain",
    "barrier_cards",
    "compare_table",
    "matrix",
    "trend_cards",
    "timeline",
    "transaction_summary",
}
RENDER_LAYOUT_REQUIRED = {"overview_dynamic", "chart", "chart_plus_table", "compare_table", "matrix"}


def _layout_config_paths(path: Path | str) -> dict[str, Path]:
    config_path = Path(path)
    if not config_path.is_absolute():
        candidate = Path.cwd() / config_path
        config_path = candidate if candidate.exists() else ROOT_DIR / config_path
    config = load_json_file(config_path)
    if config.get("schema_version") != "layout_config_v1":
        raise ValueError(f"{config_path} must use schema_version layout_config_v1")
    files = config.get("files")
    if not isinstance(files, dict):
        raise ValueError(f"{config_path} must define object field 'files'")
    resolved: dict[str, Path] = {}
    for key, raw in files.items():
        candidate = Path(str(raw))
        resolved[key] = candidate if candidate.is_absolute() else ROOT_DIR / candidate
    return resolved


def _ppt_slide_names(template_path: Path) -> set[str]:
    with ZipFile(template_path, "r") as archive:
        return {
            Path(name).name
            for name in archive.namelist()
            if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        }


def _mapping_by_slide(mapping: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {
        int(slide.get("slide_no")): slide
        for slide in mapping.get("slides") or []
        if isinstance(slide, dict) and str(slide.get("slide_no") or "").isdigit()
    }


def _registry_pairs(registry: dict[str, Any]) -> set[tuple[int, str]]:
    pairs: set[tuple[int, str]] = set()
    for slide_no, slide in slides_by_no(registry).items():
        for page_type in (slide.get("variants") or {}).keys():
            pairs.add((slide_no, str(page_type)))
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(description="Check registry coverage across downstream contracts.")
    parser.add_argument("--layout-config", default=str(ROOT_DIR / "configs" / "layout_config.json"))
    parser.add_argument("--registry")
    parser.add_argument("--render-layouts")
    parser.add_argument("--ppt-mapping")
    parser.add_argument("--layout-budget")
    parser.add_argument("--text-fit-rules")
    parser.add_argument("--template", default=str(ROOT_DIR / "assets" / "industry_section_template_master.pptx"))
    args = parser.parse_args()

    layout_paths = _layout_config_paths(Path(args.layout_config))
    registry_path = Path(args.registry) if args.registry else layout_paths["slide_registry"]
    render_layouts_path = Path(args.render_layouts) if args.render_layouts else layout_paths["render_layouts"]
    ppt_mapping_path = Path(args.ppt_mapping) if args.ppt_mapping else layout_paths["ppt_mapping"]
    layout_budget_path = Path(args.layout_budget) if args.layout_budget else layout_paths["layout_budget"]
    text_fit_rules_path = Path(args.text_fit_rules) if args.text_fit_rules else layout_paths["text_fit_rules"]

    registry = load_slide_registry(registry_path)
    render_layouts = load_json_file(render_layouts_path).get("slides") or {}
    ppt_mapping_raw = load_json_file(ppt_mapping_path)
    ppt_mapping = _mapping_by_slide(ppt_mapping_raw)
    layout_budget = load_json_file(layout_budget_path)
    text_fit_rules = load_json_file(text_fit_rules_path)
    physical_slides = _ppt_slide_names(Path(args.template))
    registry_pairs = _registry_pairs(registry)

    errors: list[str] = []
    for slide_key, slide_layouts in render_layouts.items():
        if not str(slide_key).isdigit():
            errors.append(f"render_layouts.json slide key {slide_key!r} must be numeric")
            continue
        slide_no = int(slide_key)
        for page_type in (slide_layouts or {}).keys():
            if (slide_no, str(page_type)) not in registry_pairs:
                errors.append(f"render_layouts.json has unregistered page type {slide_no}:{page_type}")

    for key in (layout_budget.get("slide_budgets") or {}).keys():
        parts = str(key).split(":", 1)
        if len(parts) != 2 or not parts[0].isdigit():
            errors.append(f"layout_budget.json slide_budgets key {key!r} must be '<slide_no>:<page_type>'")
            continue
        if (int(parts[0]), parts[1]) not in registry_pairs:
            errors.append(f"layout_budget.json has unregistered slide/page key {key}")

    for key in (text_fit_rules.get("fields") or {}).keys():
        parts = str(key).split(":")
        if len(parts) < 3 or not parts[0].isdigit():
            errors.append(f"text_fit_rules.json field key {key!r} must be '<slide_no>:<page_type>:<field>'")
            continue
        pair = (int(parts[0]), parts[1])
        if pair not in registry_pairs:
            errors.append(f"text_fit_rules.json has unregistered slide/page key {parts[0]}:{parts[1]}")

    for slide in ppt_mapping_raw.get("slides") or []:
        if not isinstance(slide, dict) or not str(slide.get("slide_no") or "").isdigit():
            continue
        slide_no = int(slide.get("slide_no"))
        for page_type in (slide.get("controlled_variants") or {}).keys():
            if (slide_no, str(page_type)) not in registry_pairs:
                errors.append(f"ppt_mapping.json has unregistered controlled variant {slide_no}:{page_type}")
        fixed_type = str(slide.get("selected_page_type") or "").strip()
        if fixed_type and (slide_no, fixed_type) not in registry_pairs:
            errors.append(f"ppt_mapping.json has unregistered selected_page_type {slide_no}:{fixed_type}")

    for slide_no, slide in slides_by_no(registry).items():
        slide_layouts = render_layouts.get(str(slide_no), {})
        mapping_slide = ppt_mapping.get(slide_no, {})
        mapping_variants = set((mapping_slide.get("controlled_variants") or {}).keys())
        mapping_fixed_type = str(mapping_slide.get("selected_page_type") or "")
        for page_type, variant in (slide.get("variants") or {}).items():
            renderer = str(variant.get("renderer") or "")
            if renderer not in KNOWN_RENDERERS:
                errors.append(f"slide {slide_no}/{page_type}: unknown renderer {renderer!r}")
            if renderer in RENDER_LAYOUT_REQUIRED and page_type not in slide_layouts:
                errors.append(f"slide {slide_no}/{page_type}: renderer {renderer!r} requires render_layouts entry")
            physical_slide = str(variant.get("physical_slide") or "")
            if physical_slide not in physical_slides:
                errors.append(f"slide {slide_no}/{page_type}: physical slide {physical_slide!r} not found in PPT template")
            if mapping_variants:
                if page_type not in mapping_variants:
                    errors.append(f"slide {slide_no}/{page_type}: missing controlled variant in ppt_mapping.json")
            elif mapping_fixed_type and page_type != mapping_fixed_type:
                registry_variants = slide.get("variants") or {}
                physical_set = {
                    str(item.get("physical_slide") or "")
                    for item in registry_variants.values()
                }
                fixed_mapping_is_shared_canvas = (
                    mapping_fixed_type in registry_variants
                    and len(physical_set) == 1
                )
                if not fixed_mapping_is_shared_canvas:
                    errors.append(
                        f"slide {slide_no}/{page_type}: ppt_mapping fixed selected_page_type is {mapping_fixed_type!r}"
                    )

    report = {"is_valid": not errors, "error_count": len(errors), "errors": errors}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
