#!/usr/bin/env python3
"""Build a non-blocking banker review packet for deck content QC.

This is not a validator and does not add a gate. It gathers page thesis, copy,
visual intent, EV/MET bindings, and contract limits into a compact Markdown
packet so an LLM can review the deck like a banker instead of chasing JSON
fields.
"""

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
from pathlib import Path
from typing import Any

from json_utils import load_json_file


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _load_optional(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    data = load_json_file(p)
    return data if isinstance(data, dict) else {}


def _slides(data: dict[str, Any]) -> list[dict[str, Any]]:
    raw = data.get("slides")
    if raw is None:
        raw = data.get("pages")
    return [item for item in _as_list(raw) if isinstance(item, dict)]


def _slide_no(slide: dict[str, Any], fallback: int) -> int:
    raw = slide.get("slide_no") or slide.get("page_no") or slide.get("slide_number")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return fallback


def _body_blocks(slide: dict[str, Any]) -> list[str]:
    blocks: list[str] = []
    raw = slide.get("body_blocks")
    if isinstance(raw, list):
        for block in raw:
            if isinstance(block, dict):
                role = _text(block.get("role") or block.get("target_field"))
                copy = _text(block.get("copy") or block.get("text") or block.get("body"))
                if copy:
                    blocks.append(f"- {role + ': ' if role else ''}{copy}")
            elif _text(block):
                blocks.append(f"- {_text(block)}")
    body_copy = slide.get("body_copy")
    if isinstance(body_copy, dict):
        for key, value in body_copy.items():
            if _text(value):
                blocks.append(f"- {key}: {_text(value)}")
    return blocks


def _contract_by_slide(page_contract: dict[str, Any]) -> dict[int, dict[str, Any]]:
    output: dict[int, dict[str, Any]] = {}
    for idx, page in enumerate(_slides(page_contract), start=1):
        output[_slide_no(page, idx)] = page
    return output


def _ids(value: Any) -> str:
    return ", ".join(_text(item) for item in _as_list(value) if _text(item))


def build_packet(deck_blueprint: dict[str, Any], page_contract: dict[str, Any], renderer_spec: dict[str, Any]) -> str:
    contract = _contract_by_slide(page_contract)
    renderer_by_slide = {_slide_no(slide, idx): slide for idx, slide in enumerate(_slides(renderer_spec), start=1)}
    lines: list[str] = [
        "# Banker Review Packet",
        "",
        "> Non-blocking LLM review aid. Review page quality and evidence use; repair upstream `deck_blueprint.json` or research artifacts, then recompile. Do not patch renderer output directly.",
        "",
        "## Review Questions",
        "- Does each page answer one investor question?",
        "- Is the headline a banker-style point, not a raw fact label?",
        "- Does body copy have enough evidence, mechanism, or implication density?",
        "- Does the visual intent support the page thesis?",
        "- Are platform/channel/proxy metrics labeled so they are not overgeneralized?",
        "- Are user-provided target facts separated from externally validated industry facts?",
        "- Are weak/thin findings caveated rather than promoted to headline/chart?",
        "- Are adjacent pages non-duplicative?",
        "",
    ]
    for idx, slide in enumerate(_slides(deck_blueprint), start=1):
        slide_no = _slide_no(slide, idx)
        contract_slide = contract.get(slide_no, {})
        renderer_slide = renderer_by_slide.get(slide_no, {})
        lines.extend(
            [
                f"## Slide {slide_no}",
                f"- Page role: {_text(slide.get('page_role') or slide.get('slide_key') or renderer_slide.get('slide_key'))}",
                f"- Selected page type: {_text(slide.get('selected_page_type') or renderer_slide.get('selected_page_type'))}",
                f"- Investor question: {_text(slide.get('investor_question'))}",
                f"- Page thesis / answer: {_text(slide.get('page_thesis') or slide.get('page_answer'))}",
                f"- Headline: {_text(slide.get('headline') or renderer_slide.get('headline'))}",
                f"- Main message: {_text(slide.get('main_message') or renderer_slide.get('main_message'))}",
                f"- Claim strength: {_text(slide.get('claim_strength') or renderer_slide.get('claim_strength'))}",
                f"- Evidence IDs: {_ids(slide.get('evidence_ids')) or _ids(contract_slide.get('body_evidence_ids'))}",
                f"- Metric IDs: {_ids(slide.get('metric_ids')) or _ids(contract_slide.get('chart_metric_ids'))}",
                f"- Contract caveats: {_ids(contract_slide.get('caveats'))}",
                "",
                "Body blocks:",
            ]
        )
        blocks = _body_blocks(slide) or _body_blocks(renderer_slide)
        lines.extend(blocks if blocks else ["-"])
        visual = slide.get("visual_design") or slide.get("visual_plan") or renderer_slide.get("chart_data") or {}
        if isinstance(visual, dict):
            lines.extend(
                [
                    "",
                    f"Visual intent/type: {_text(visual.get('type') or visual.get('chart_type') or visual.get('required_capability'))}",
                    f"Visual rationale: {_text(visual.get('purpose') or visual.get('chart_rationale') or visual.get('rationale'))}",
                ]
            )
        lines.extend(
            [
                "",
                "Reviewer notes:",
                "- Page quality:",
                "- Evidence support:",
                "- Copy density:",
                "- Visual support:",
                "- Repair target:",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deck-blueprint", required=True)
    parser.add_argument("--page-contract")
    parser.add_argument("--renderer-spec")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    packet = build_packet(
        _load_optional(args.deck_blueprint),
        _load_optional(args.page_contract),
        _load_optional(args.renderer_spec),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(packet, encoding="utf-8")
    print(json.dumps({"is_valid": True, "output": str(output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
