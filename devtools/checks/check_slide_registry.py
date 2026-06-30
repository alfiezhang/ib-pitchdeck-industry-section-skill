#!/usr/bin/env python3
"""Check slide-variant config files against slide_registry.json."""

from __future__ import annotations

# Runtime scripts can be run directly. Shared helpers remain in runtime
# `scripts/`; production tools live under role scripts; validators live under QC.
import sys as _ib_sys
from pathlib import Path as _IbPath
_ib_sys.dont_write_bytecode = True
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
from typing import Any

ROOT_DIR = _IB_RUNTIME_ROOT
RENDERER_SPEC_REQUIRED_SLIDE_FIELDS = {
    "slide_no",
    "fixed_page_role",
    "selected_page_type",
    "banker_page_id",
    "headline",
    "main_message",
    "body_copy",
    "source_note",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def load_slide_registry(path: Path) -> dict[str, Any]:
    registry = load_json(path)
    if not isinstance(registry.get("slides"), list):
        raise ValueError(f"Invalid slide registry: {path}")
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


def check_renderer_contract(registry: dict[str, Any], errors: list[str]) -> None:
    for slide_no, (_binding_key, valid_types) in variant_page_types(registry).items():
        if not valid_types:
            errors.append(f"slide_registry slide {slide_no} has no registered page variants")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check slide registry consistency.")
    parser.add_argument("--registry", default=str(ROOT_DIR / "configs" / "slide_registry.json"))
    args = parser.parse_args()

    registry = load_slide_registry(Path(args.registry))
    errors: list[str] = []
    check_renderer_contract(registry, errors)

    report = {"is_valid": not errors, "error_count": len(errors), "errors": errors}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
