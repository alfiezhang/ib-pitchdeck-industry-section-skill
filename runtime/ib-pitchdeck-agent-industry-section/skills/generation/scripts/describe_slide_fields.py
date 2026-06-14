#!/usr/bin/env python3
"""Describe renderer-spec body_copy fields for a registered slide variant.

This is a deterministic helper for agents. It does not validate content and it
does not encode industry logic; it only exposes the slide registry contract in a
compact, human-readable form.
"""

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

from slide_registry import get_variant_contract, load_slide_registry


FIELD_HINTS = {
    "bullet_1": "First supporting argument for the slide conclusion.",
    "bullet_2": "Second supporting argument for the slide conclusion.",
    "bullet_3": "Third supporting argument for the slide conclusion.",
    "card_1": "First driver/barrier/trend card.",
    "card_2": "Second driver/barrier/trend card.",
    "card_3": "Third driver/barrier/trend card.",
    "card_4": "Fourth driver/barrier/trend card.",
    "card_5": "Fifth driver/barrier/trend card.",
    "card_6": "Sixth driver/barrier/trend card.",
    "left_panel": "Left-side narrative panel.",
    "right_top": "Top item in the right-side panel.",
    "right_mid": "Middle item in the right-side panel.",
    "right_bottom": "Bottom item in the right-side panel.",
    "top_left": "Top-left value-chain/profit-pool cell.",
    "top_center": "Top-center value-chain/profit-pool cell.",
    "top_right": "Top-right value-chain/profit-pool cell.",
    "bottom_left": "Bottom-left value-chain/profit-pool cell.",
    "bottom_center": "Bottom-center value-chain/profit-pool cell.",
    "bottom_right": "Bottom-right value-chain/profit-pool cell.",
}


def field_description(field: str) -> str:
    if field in FIELD_HINTS:
        return FIELD_HINTS[field]
    if field.startswith("table_"):
        return "Legacy token field; prefer structured table payload when available."
    return "Registered body_copy field."


def describe_variant(registry_path: Path, slide_no: int, page_type: str) -> dict[str, Any]:
    registry = load_slide_registry(registry_path)
    contract = get_variant_contract(registry, slide_no, page_type)
    renderer_contract = contract.get("renderer_contract") or {}
    token_contract = contract.get("token_contract") or {}
    body_fields = list(renderer_contract.get("required_body_fields") or [])
    return {
        "slide_no": slide_no,
        "slide_key": contract.get("slide_key", ""),
        "page_type": page_type,
        "renderer": contract.get("renderer", ""),
        "render_layout_key": contract.get("render_layout_key", ""),
        "required_renderer_fields": renderer_contract.get("required_fields") or [],
        "required_body_copy_fields": [
            {"field": field, "hint": field_description(str(field))}
            for field in body_fields
        ],
        "token_body_fields": token_contract.get("required_body_fields") or [],
        "required_ppt_objects": (contract.get("renderer_contract") or {}).get("required_objects") or [],
        "preferred_ppt_objects": (contract.get("renderer_contract") or {}).get("preferred_objects") or [],
    }


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"Slide {payload['slide_no']} / {payload['page_type']}",
        f"slide_key: {payload['slide_key']}",
        f"renderer: {payload['renderer']}",
        f"render_layout_key: {payload['render_layout_key']}",
        "required_renderer_fields: " + ", ".join(payload["required_renderer_fields"]),
        "required_body_copy_fields:",
    ]
    for item in payload["required_body_copy_fields"]:
        lines.append(f"  - {item['field']}: {item['hint']}")
    required_objects = payload.get("required_ppt_objects") or []
    preferred_objects = payload.get("preferred_ppt_objects") or []
    lines.append("required_ppt_objects: " + (", ".join(required_objects) if required_objects else "none"))
    lines.append("preferred_ppt_objects: " + (", ".join(preferred_objects) if preferred_objects else "none"))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slide-no", type=int, required=True)
    parser.add_argument("--page-type", required=True)
    parser.add_argument("--registry", default=str(_IB_RUNTIME_ROOT / "templates" / "slide_registry.json"))
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()

    payload = describe_variant(Path(args.registry), args.slide_no, args.page_type)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_text(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
