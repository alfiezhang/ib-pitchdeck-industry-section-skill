#!/usr/bin/env python3
"""Repair and audit renderer-spec visible_metric_claims.

This helper addresses a common LLM failure mode: partial visible metric claims
such as {"location": "main_message", "metric_ids": ["MET-001"]}. It fills
mechanical fields from the existing renderer spec text and reports unresolved
material numeric locations. It never invents MET-IDs. Claims must live at the
renderer spec slide level.
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
import re
from pathlib import Path
from typing import Any

from json_utils import load_json_file
from validate_content_quality import (
    QUANT_CLAIM_RE,
    is_material_numeric_claim_location,
    parse_metric_reconciliation,
    visible_text_fields,
)


RANKING_RE = re.compile(r"(top\s*\d+|第[一二三四五六七八九十\d]+|排名|榜|rank|ranking)", re.I)
PEER_RE = re.compile(r"(peer|compare|comparison|对比|同行|竞品|同业|vs|VS|高于|低于)", re.I)
CALC_RE = re.compile(r"(/|÷|=|≈|约|推算|测算|calculated|derived|inferred|implied|隐含|计算)")
MET_RE = re.compile(r"^MET-\d{3}$")


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _claim_location(claim: dict[str, Any]) -> str:
    return str(claim.get("location") or claim.get("field") or "").strip()


def _infer_usage_type(location: str, text: str) -> str:
    lowered = f"{location} {text}"
    if RANKING_RE.search(lowered):
        return "ranking"
    if location.startswith("compare_table_data.") or PEER_RE.search(lowered):
        return "peer_comparison"
    if CALC_RE.search(lowered):
        return "calculated_display"
    return "direct_display"


def _display_text_for_location(fields_by_loc: dict[str, str], location: str) -> str:
    return fields_by_loc.get(location, "")


def _normalize_metric_ids(value: Any) -> list[str]:
    ids = []
    for item in _as_list(value):
        text = str(item or "").strip()
        if text:
            ids.append(text)
    return ids


def _metric_value(row: dict[str, str]) -> str:
    for key in ("Value", "value", "数值"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _metric_unit(row: dict[str, str]) -> str:
    for key in ("Unit", "unit", "单位"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _metric_name(row: dict[str, str]) -> str:
    for key in ("Metric Name", "metric_name", "Metric", "指标"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _numeric_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for match in re.finditer(r"\d+(?:\.\d+)?", str(text or "")):
        tokens.add(match.group(0))
    return tokens


def _candidate_metrics(text: str, metrics: dict[str, dict[str, str]]) -> list[str]:
    text_tokens = _numeric_tokens(text)
    if not text_tokens:
        return []
    candidates = []
    lowered = str(text or "").lower()
    for met_id, row in metrics.items():
        value = _metric_value(row)
        unit = _metric_unit(row)
        name = _metric_name(row)
        value_tokens = _numeric_tokens(value)
        if value_tokens and text_tokens & value_tokens:
            candidates.append(met_id)
            continue
        if name and name.lower() in lowered:
            candidates.append(met_id)
            continue
        if value and unit and f"{value}{unit}" in str(text):
            candidates.append(met_id)
    return sorted(set(candidates))


def repair_renderer_spec(renderer_spec: dict[str, Any], memo_text: str) -> tuple[dict[str, Any], dict[str, Any]]:
    metrics = parse_metric_reconciliation(memo_text) if memo_text else {}
    report: dict[str, Any] = {
        "schema_version": "visible_metric_claim_repair_v1",
        "changed": False,
        "slides": [],
        "unresolved_count": 0,
        "repaired_count": 0,
        "unknown_metric_ids": [],
        "notes": [
            "This helper never invents MET-IDs. It repairs claim structure and reports unresolved locations."
        ],
    }
    repaired = json.loads(json.dumps(renderer_spec, ensure_ascii=False))
    for slide in repaired.get("slides") or []:
        if not isinstance(slide, dict):
            continue
        slide_no = slide.get("slide_no")
        fields = visible_text_fields(slide)
        fields_by_loc = {loc: text for loc, text in fields}
        material_locations = [
            (loc, text)
            for loc, text in fields
            if QUANT_CLAIM_RE.search(text) and is_material_numeric_claim_location(loc, text)
        ]

        existing_claims = [item for item in _as_list(slide.get("visible_metric_claims")) if isinstance(item, dict)]

        normalized: dict[str, dict[str, Any]] = {}
        slide_report = {
            "slide_no": slide_no,
            "repaired": [],
            "unresolved": [],
            "ignored_claims": [],
        }

        for claim in existing_claims:
            location = _claim_location(claim)
            if not location:
                slide_report["ignored_claims"].append({"reason": "missing location", "claim": claim})
                continue
            display_text = str(claim.get("display_text") or "").strip()
            if not display_text:
                display_text = _display_text_for_location(fields_by_loc, location)
            metric_ids = _normalize_metric_ids(claim.get("metric_ids"))
            usage_type = str(claim.get("usage_type") or "").strip()
            if not usage_type:
                usage_type = _infer_usage_type(location, display_text)
            repaired_claim = {
                "location": location,
                "display_text": display_text,
                "metric_ids": metric_ids,
                "usage_type": usage_type,
            }
            for optional_key in ("calculation_note", "basis_note", "scope_group"):
                if str(claim.get(optional_key) or "").strip():
                    repaired_claim[optional_key] = str(claim.get(optional_key)).strip()
            if usage_type == "ranking" and "basis_note" not in repaired_claim:
                repaired_claim["basis_note"] = "State period, platform/source, and ranked population before formal delivery."
            if usage_type == "calculated_display" and "calculation_note" not in repaired_claim:
                repaired_claim["calculation_note"] = "Review calculation basis before formal delivery."
            normalized[location] = repaired_claim
            report["repaired_count"] += 1
            slide_report["repaired"].append(location)
            report["changed"] = True
            for met_id in metric_ids:
                if not MET_RE.match(met_id) or (metrics and met_id not in metrics):
                    report["unknown_metric_ids"].append({"slide_no": slide_no, "location": location, "metric_id": met_id})

        for location, text in material_locations:
            if location in normalized:
                continue
            candidates = _candidate_metrics(text, metrics)
            slide_report["unresolved"].append(
                {
                    "location": location,
                    "display_text": text,
                    "candidate_metric_ids": candidates,
                    "repair_hint": "Choose an existing MET-ID from Metric Reconciliation, move incidental numeric text to source_note, or downgrade the claim.",
                }
            )
            report["unresolved_count"] += 1

        if normalized:
            slide["visible_metric_claims"] = [normalized[key] for key in sorted(normalized.keys())]
        elif "visible_metric_claims" in slide and not material_locations:
            del slide["visible_metric_claims"]
            report["changed"] = True

        if slide_report["repaired"] or slide_report["unresolved"] or slide_report["ignored_claims"]:
            report["slides"].append(slide_report)

    report["unknown_metric_ids"] = sorted(
        report["unknown_metric_ids"],
        key=lambda item: (str(item.get("slide_no")), str(item.get("location")), str(item.get("metric_id"))),
    )
    return repaired, report


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair renderer-spec visible_metric_claims without inventing MET-IDs.")
    parser.add_argument("--renderer-spec", dest="renderer_spec", required=True)
    parser.add_argument("--research-pack", dest="research_pack", required=True)
    parser.add_argument("--output", help="Write repaired renderer spec JSON here. Omit for validate/report only.")
    parser.add_argument("--report", help="Write repair report JSON here.")
    parser.add_argument("--in-place", action="store_true", help="Overwrite --renderer-spec with the repaired JSON.")
    args = parser.parse_args()
    renderer_spec_path = Path(args.renderer_spec)
    memo_path = Path(args.research_pack)
    renderer_spec = load_json_file(renderer_spec_path)
    memo_text = memo_path.read_text(encoding="utf-8")
    repaired, report = repair_renderer_spec(renderer_spec, memo_text)

    output_path = renderer_spec_path if args.in_place else Path(args.output) if args.output else None
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(repaired, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["unresolved_count"] == 0 and not report["unknown_metric_ids"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
