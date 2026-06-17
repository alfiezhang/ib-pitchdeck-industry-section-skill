#!/usr/bin/env python3
"""Validate template_registry.json against the canonical slide registry."""

from __future__ import annotations

# Runtime scripts can be run directly. Shared helpers remain in runtime
# `scripts/`; production tools live under role scripts; validators live under QC.
import sys as _ib_sys
from pathlib import Path as _IbPath
_IB_ROLE_SCRIPT_DIR = _IbPath(__file__).resolve().parent
_IB_RUNTIME_ROOT = next(
    _p for _p in _IbPath(__file__).resolve().parents
    if (_p / 'configs').is_dir() and (_p / 'scripts').is_dir()
)
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts" / "_lib"
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


def validate(registry: dict[str, Any], slide_registry: dict[str, Any] | None = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if registry.get("schema_version") != "template_registry_v1":
        errors.append("schema_version must be template_registry_v1")
    slides = registry.get("slides")
    if not isinstance(slides, list):
        return ["slides must be an array"], warnings
    if len(slides) != 8:
        errors.append(f"slides must contain exactly 8 entries; found {len(slides)}")

    canonical_variants: dict[int, set[str]] = {}
    if slide_registry:
        for item in slide_registry.get("slides") or []:
            if isinstance(item, dict) and isinstance(item.get("slide_no"), int):
                canonical_variants[int(item["slide_no"])] = set((item.get("variants") or {}).keys())

    seen: set[int] = set()
    for slide in slides:
        if not isinstance(slide, dict):
            errors.append("slides entries must be objects")
            continue
        slide_no = slide.get("slide_no")
        prefix = f"slide {slide_no}"
        if not isinstance(slide_no, int):
            errors.append(f"{prefix}: slide_no must be integer")
            continue
        if slide_no in seen:
            errors.append(f"{prefix}: duplicate slide_no")
        seen.add(slide_no)
        expected_role = FIXED_PAGE_ROLES.get(slide_no)
        if slide.get("fixed_page_role") != expected_role:
            errors.append(f"{prefix}: fixed_page_role must be {expected_role}")
        variants = slide.get("variants")
        if not isinstance(variants, list) or not variants:
            errors.append(f"{prefix}: variants must be non-empty")
            continue
        variant_names = {str(item.get("page_type")) for item in variants if isinstance(item, dict)}
        if slide_no in canonical_variants and variant_names != canonical_variants[slide_no]:
            errors.append(
                f"{prefix}: variants differ from slide_registry; found {sorted(variant_names)}, "
                f"expected {sorted(canonical_variants[slide_no])}"
            )
        if not any(item.get("formal_allowed") is True for item in variants if isinstance(item, dict)):
            errors.append(f"{prefix}: no formal_allowed variant")
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            page_type = str(variant.get("page_type") or "")
            for key in ("renderer", "supports", "required_body_fields", "field_roles"):
                if key not in variant:
                    errors.append(f"{prefix}/{page_type}: missing {key}")
            supports = variant.get("supports")
            if not isinstance(supports, dict):
                errors.append(f"{prefix}/{page_type}: supports must be object")
            elif not all(isinstance(supports.get(k), bool) for k in ("chart", "table", "matrix", "cards")):
                errors.append(f"{prefix}/{page_type}: supports must include boolean chart/table/matrix/cards")
            if variant.get("formal_allowed") is not True:
                warnings.append(f"{prefix}/{page_type}: variant is non-formal ({variant.get('deprecation_status')})")

    missing = set(FIXED_PAGE_ROLES) - seen
    if missing:
        errors.append("missing slide_no entries: " + ", ".join(str(num) for num in sorted(missing)))
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-registry", required=True)
    parser.add_argument("--slide-registry", default=str(ROOT / "configs/slide_registry.json"))
    parser.add_argument("--output")
    args = parser.parse_args()

    try:
        registry = _load(Path(args.template_registry))
        slide_registry = _load(Path(args.slide_registry)) if args.slide_registry else None
        errors, warnings = validate(registry, slide_registry)
    except Exception as exc:
        errors, warnings = [str(exc)], []
    result = {
        "is_valid": not errors,
        "template_registry": args.template_registry,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
