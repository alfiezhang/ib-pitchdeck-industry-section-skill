#!/usr/bin/env python3
"""Compile deck_blueprint.json into internal PPT renderer inputs."""

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
import re
from pathlib import Path
from typing import Any

from build_page_evidence_contract import build_page_evidence_contract
from compare_table_utils import split_table_cells
from deck_blueprint_utils import (
    FIXED_PAGE_ROLES,
    as_list,
    metric_ids_from_visual,
    normalize_deck_blueprint_for_page_plan,
    proof_points_from_blueprint_slide,
    selected_issue_analysis_ids,
    template_variants_by_slide,
    unique,
    visual_plan_from_blueprint_slide,
)
from json_utils import load_json_file
from template_contract_utils import active_body_fields, required_body_fields


ROLE_FIELD_ALIASES = {
    "upstream": "top_left",
    "raw_materials": "top_left",
    "supply": "top_left",
    "manufacturing": "top_center",
    "production": "top_center",
    "operations": "top_center",
    "brand": "top_right",
    "brand_owner": "top_right",
    "brands": "top_right",
    "channel": "bottom_left",
    "distribution": "bottom_left",
    "sales_channel": "bottom_left",
    "profit_pool": "bottom_center",
    "margin_pool": "bottom_center",
    "economics": "bottom_center",
    "value_accrual": "bottom_center",
    "target_implication": "bottom_right",
    "pitch_implication": "bottom_right",
    "transaction_implication": "bottom_right",
}


UPSTREAM_VALIDATION_ARTIFACTS = (
    "artifacts/industry_scope_pack_validation.json",
    "artifacts/formal_search_plan_validation.json",
    "artifacts/formal_research_execution_validation.json",
    "artifacts/source_archive_validation.json",
    "artifacts/stage_gate_pre_research_pack_validation.json",
    "artifacts/research_pack_validation.json",
    "artifacts/issue_analysis_validation.json",
    "artifacts/deck_blueprint_validation.json",
    "artifacts/template_registry_validation.json",
)


def _maybe_run_dir_from_inputs(paths: list[Path]) -> Path | None:
    parents = [path.resolve().parent for path in paths if path.name in {"industry_issue_analysis.json", "deck_blueprint.json", "template_registry.json"}]
    if len(parents) < 3:
        return None
    first = parents[0]
    if all(parent == first for parent in parents) and (first / "artifacts").is_dir():
        return first
    return None


def _assert_upstream_package_valid(run_dir: Path) -> None:
    blocking: list[str] = []
    for rel in UPSTREAM_VALIDATION_ARTIFACTS:
        path = run_dir / rel
        if not path.exists():
            blocking.append(f"missing {rel}")
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            blocking.append(f"cannot read {rel}: {exc}")
            continue
        if payload.get("is_valid") is False:
            blocking.append(f"{rel} is_valid=false")
    if blocking:
        detail = "; ".join(blocking[:8])
        raise ValueError(
            "cannot compile deck_blueprint for a formal run with incomplete upstream gates: "
            f"{detail}. Fix upstream validation or use a separate temporary diagnostic directory."
        )


def _contract_index(page_contract: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {
        int(item.get("slide_no")): item
        for item in page_contract.get("slides") or []
        if isinstance(item, dict) and isinstance(item.get("slide_no"), int)
    }


def _slide_index(deck_blueprint: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {
        int(item.get("slide_no")): item
        for item in deck_blueprint.get("slides") or []
        if isinstance(item, dict) and isinstance(item.get("slide_no"), int)
    }


def _body_text(block: dict[str, Any]) -> str:
    return str(block.get("copy") or block.get("point") or "").strip()


def _block_target_field(block: dict[str, Any]) -> str:
    for key in ("target_field", "template_field", "body_field", "field"):
        value = str(block.get(key) or "").strip()
        if value:
            return value
    return ""


def _active_fields_hint(slide_no: int, page_type: str, fields: list[str]) -> str:
    allowed = ", ".join(fields) if fields else "(none)"
    return (
        f"Allowed active body fields: {allowed}. "
        "Use one of these values, or remove target_field and let the compiler map by role."
    )


def _normalize_field_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _candidate_fields_for_role(role: str, fields: list[str]) -> list[str]:
    normalized_role = _normalize_field_key(role)
    normalized_fields = {_normalize_field_key(field): field for field in fields}
    candidates: list[str] = []
    if normalized_role in normalized_fields:
        candidates.append(normalized_fields[normalized_role])
    alias = ROLE_FIELD_ALIASES.get(normalized_role)
    if alias in fields:
        candidates.append(alias)

    match = re.search(r"(\d+)$", normalized_role)
    if match:
        number = match.group(1)
        for prefix in ("card", "bullet", "stage", "point", "table_row"):
            field = f"{prefix}_{number}"
            if field in fields:
                candidates.append(field)
    return unique(candidates)


def _body_copy_from_blocks(slide: dict[str, Any], required_fields: list[str], page_type: str) -> dict[str, str]:
    slide_no = int(slide.get("slide_no") or 0)
    explicit = slide.get("body_copy")
    if isinstance(explicit, dict):
        return {str(key): str(value or "").strip() for key, value in explicit.items()}
    fields = active_body_fields(required_fields, page_type, slide)
    blocks = [block for block in as_list(slide.get("body_blocks")) if isinstance(block, dict)]
    body: dict[str, str] = {field: "" for field in fields}
    assigned_block_indexes: set[int] = set()

    for idx, block in enumerate(blocks):
        target = _block_target_field(block)
        if not target:
            continue
        if target not in fields:
            raise ValueError(
                f"slide {slide_no}: body block target_field '{target}' is not active for {page_type}. "
                f"{_active_fields_hint(slide_no, page_type, fields)}"
            )
        if body.get(target):
            raise ValueError(
                f"slide {slide_no}: duplicate body block target_field '{target}'. "
                f"{_active_fields_hint(slide_no, page_type, fields)}"
            )
        body[target] = _body_text(block)
        assigned_block_indexes.add(idx)

    for idx, block in enumerate(blocks):
        if idx in assigned_block_indexes:
            continue
        role = str(block.get("role") or "").strip()
        for field in _candidate_fields_for_role(role, fields):
            if not body.get(field):
                body[field] = _body_text(block)
                assigned_block_indexes.add(idx)
                break

    if len(assigned_block_indexes) < len(blocks):
        unmapped = [str(idx + 1) for idx in range(len(blocks)) if idx not in assigned_block_indexes]
        raise ValueError(
            f"slide {slide_no}: {len(unmapped)} body block(s) could not be mapped by target_field or role: "
            f"blocks {', '.join(unmapped)}. Set target_field on those blocks or provide explicit body_copy."
        )
    return body


def _visible_metric_claims_from_blueprint(slide: dict[str, Any], body_copy: dict[str, str]) -> list[dict[str, Any]]:
    explicit = slide.get("visible_metric_claims")
    if isinstance(explicit, list) and explicit:
        return [item for item in explicit if isinstance(item, dict)]

    claims: list[dict[str, Any]] = []
    proof_points = proof_points_from_blueprint_slide(slide)
    all_metrics = unique(
        [
            str(item).strip()
            for point in proof_points
            for item in as_list(point.get("metric_ids"))
            if str(item).strip()
        ]
    )
    headline = str(slide.get("headline") or "").strip()
    main_message = str(slide.get("main_message") or "").strip()
    for location, text in (("headline", headline), ("main_message", main_message)):
        if all_metrics and any(ch.isdigit() for ch in text):
            claims.append(
                {
                    "location": location,
                    "display_text": text,
                    "metric_ids": all_metrics,
                    "usage_type": "direct_display",
                }
            )
    for field, text in body_copy.items():
        for point in proof_points:
            point_text = str(point.get("point") or "").strip()
            metrics = unique([str(item).strip() for item in as_list(point.get("metric_ids")) if str(item).strip()])
            if metrics and point_text and point_text == text and any(ch.isdigit() for ch in text):
                claims.append(
                    {
                        "location": f"body_copy.{field}",
                        "display_text": text,
                        "metric_ids": metrics,
                        "usage_type": "direct_display",
                    }
                )
    return claims


def _visual_payload(slide: dict[str, Any], key: str) -> dict[str, Any]:
    if isinstance(slide.get(key), dict):
        return slide[key]
    visual = slide.get("visual_design") if isinstance(slide.get("visual_design"), dict) else {}
    if isinstance(visual.get(key), dict):
        return visual[key]
    visual_plan = slide.get("visual_plan") if isinstance(slide.get("visual_plan"), dict) else {}
    if isinstance(visual_plan.get(key), dict):
        return visual_plan[key]
    return {}


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _category_from_row(row: dict[str, Any], fallback: str = "") -> str:
    return _first_text(
        row.get("category"),
        row.get("label"),
        row.get("period"),
        row.get("year"),
        row.get("segment"),
        row.get("name"),
        fallback,
    )


def _value_from_row(row: dict[str, Any]) -> tuple[Any, str]:
    for key in (
        "value",
        "metric_value",
        "growth_rate",
        "growth",
        "share",
        "percentage",
        "percent",
        "rate",
        "margin",
        "amount",
        "revenue",
        "gmv",
        "sales",
        "market_size",
        "y",
    ):
        if key in row and row.get(key) not in (None, ""):
            return row.get(key), key
    return "", ""


def _series_name_from_raw(raw: dict[str, Any]) -> str:
    series = raw.get("series")
    if isinstance(series, list) and series:
        first = series[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return _first_text(first.get("name"), first.get("label"))
    return _first_text(raw.get("series_name"), raw.get("value_label"), raw.get("unit"), "Value")


def _metric_for_index(metric_ids: list[str], idx: int) -> str:
    if not metric_ids:
        return ""
    if idx < len(metric_ids):
        return metric_ids[idx]
    if len(metric_ids) == 1:
        return metric_ids[0]
    return ""


def _source_rows_from_series(categories: list[str], series: list[dict[str, Any]], metric_ids: list[str], unit: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    metric_idx = 0
    for chart_series in series:
        name = _first_text(chart_series.get("name"), chart_series.get("label"))
        values = chart_series.get("values") if isinstance(chart_series.get("values"), list) else []
        row_metric_ids = chart_series.get("metric_ids") if isinstance(chart_series.get("metric_ids"), list) else []
        for idx, category in enumerate(categories):
            value = values[idx] if idx < len(values) else ""
            metric_id = (
                str(row_metric_ids[idx]).strip()
                if idx < len(row_metric_ids) and str(row_metric_ids[idx]).strip()
                else _metric_for_index(metric_ids, metric_idx)
            )
            rows.append(
                {
                    "series_name": name,
                    "category": category,
                    "label": category,
                    "value": value,
                    "unit": unit,
                    "metric_id": metric_id,
                }
            )
            metric_idx += 1
    return rows


def _normalize_chart_data(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return {}
    chart = dict(raw)
    title = _first_text(chart.get("title"), chart.get("chart_title"))
    if title:
        chart["title"] = title

    metric_ids = [
        str(item).strip()
        for item in (chart.get("metric_ids") if isinstance(chart.get("metric_ids"), list) else [])
        if str(item).strip()
    ]
    unit = _first_text(chart.get("unit"), chart.get("value_unit"))

    categories = [str(item).strip() for item in chart.get("categories") or [] if str(item).strip()]
    series: list[dict[str, Any]] = []
    raw_series = chart.get("series")
    if isinstance(raw_series, list) and raw_series and all(isinstance(item, dict) for item in raw_series):
        for item in raw_series:
            values = item.get("values") if isinstance(item.get("values"), list) else []
            series.append(
                {
                    **item,
                    "name": _first_text(item.get("name"), item.get("label"), "Value"),
                    "values": values,
                }
            )

    data_series = chart.get("data_series")
    if not series and isinstance(data_series, list) and data_series:
        if all(isinstance(item, dict) and "values" in item for item in data_series):
            for item in data_series:
                values = item.get("values") if isinstance(item.get("values"), list) else []
                series.append(
                    {
                        **item,
                        "name": _first_text(item.get("name"), item.get("label"), _series_name_from_raw(chart)),
                        "values": values,
                    }
                )
        elif all(isinstance(item, dict) for item in data_series):
            if not categories:
                categories = [_category_from_row(item, str(idx + 1)) for idx, item in enumerate(data_series)]
            value_pairs = [_value_from_row(item) for item in data_series]
            values = [value for value, _ in value_pairs]
            row_metric_ids = [
                str(item.get("metric_id") or "").strip()
                for item in data_series
            ]
            series.append(
                {
                    "name": _series_name_from_raw(chart),
                    "values": values,
                    "metric_ids": row_metric_ids,
                }
            )
            if not unit:
                unit = _first_text(*(item.get("unit") for item in data_series if isinstance(item, dict)))
            if not unit and any(key in {"growth_rate", "growth", "share", "percentage", "percent", "rate", "margin"} for _, key in value_pairs):
                unit = "%"

    if not series and isinstance(raw_series, list) and raw_series and all(isinstance(item, str) for item in raw_series):
        # Keep categories, but leave values empty. Validators will provide a
        # clear repair item instead of letting postprocess crash.
        series.append({"name": raw_series[0], "values": []})

    if categories:
        chart["categories"] = categories
    if series:
        chart["series"] = series
    if unit:
        chart["unit"] = unit

    source_rows = chart.get("source_rows")
    if not isinstance(source_rows, list):
        if isinstance(source_rows, str) and source_rows.strip():
            chart.setdefault("source_note", source_rows.strip())
        generated_rows = _source_rows_from_series(categories, series, metric_ids, unit)
        if generated_rows:
            chart["source_rows"] = generated_rows

    return chart


def _normalize_compare_table_data(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return {}
    table = dict(raw)
    headers = [str(item).strip() for item in table.get("headers") or [] if str(item).strip()]
    if not headers and str(table.get("table_header") or "").strip():
        headers = split_table_cells(str(table.get("table_header") or ""))

    rows: list[dict[str, Any]] = []
    raw_rows = table.get("rows")
    if isinstance(raw_rows, list):
        for row in raw_rows:
            if isinstance(row, dict):
                label = _first_text(row.get("label"), row.get("name"))
                cells = [str(item).strip() for item in row.get("cells") or []]
                if not cells:
                    cells = [
                        str(value).strip()
                        for key, value in row.items()
                        if key not in {"label", "name", "metric_ids", "evidence_ids", "source_analysis_ids"}
                        and not isinstance(value, (dict, list))
                        and str(value).strip()
                    ]
                if not label and cells:
                    label, cells = cells[0], cells[1:]
                rows.append({"label": label, "cells": cells})
            elif isinstance(row, list) and row:
                cells = [str(item).strip() for item in row]
                rows.append({"label": cells[0], "cells": cells[1:]})
            elif isinstance(row, str) and row.strip():
                cells = split_table_cells(row)
                if cells:
                    rows.append({"label": cells[0], "cells": cells[1:]})

    if not rows:
        for idx in range(1, 7):
            text = str(table.get(f"table_row_{idx}") or "").strip()
            if not text:
                continue
            cells = split_table_cells(text)
            if cells:
                rows.append({"label": cells[0], "cells": cells[1:]})

    if headers:
        table["headers"] = headers
    if rows:
        table["rows"] = rows
    return table


def _source_note(slide: dict[str, Any], evidence_ids: list[str]) -> str:
    explicit = str(slide.get("source_note") or "").strip()
    if explicit:
        return explicit
    ids = unique(evidence_ids)
    return "Sources: " + "; ".join(ids) if ids else ""


def _slide_numbers_from_template_registry(template_registry: dict[str, Any]) -> list[int]:
    slide_numbers: list[int] = []
    for slide in as_list(template_registry.get("slides")):
        if not isinstance(slide, dict):
            continue
        try:
            slide_no = int(slide.get("slide_no"))
        except Exception:
            continue
        if slide_no > 0:
            slide_numbers.append(slide_no)
    if not slide_numbers:
        raise ValueError("template_registry has no usable slides; run template analysis/registry extraction first")
    return sorted(set(slide_numbers))


def build_renderer_spec_from_deck_blueprint(
    deck_blueprint: dict[str, Any],
    template_registry: dict[str, Any],
    page_contract: dict[str, Any],
) -> dict[str, Any]:
    contracts = _contract_index(page_contract)
    slides_by_no = _slide_index(deck_blueprint)
    slides: list[dict[str, Any]] = []
    template_binding: dict[str, str] = {}
    section_meta = deck_blueprint.get("section_meta") if isinstance(deck_blueprint.get("section_meta"), dict) else {}
    for slide_no in _slide_numbers_from_template_registry(template_registry):
        slide = slides_by_no.get(slide_no)
        if not slide:
            raise ValueError(f"slide {slide_no}: missing from deck_blueprint")
        contract = contracts.get(slide_no, {})
        page_type = str(slide.get("selected_page_type") or "").strip()
        required_fields = required_body_fields(template_registry, slide_no, page_type)
        body_copy = _body_copy_from_blocks(slide, required_fields, page_type)
        issue_ids = selected_issue_analysis_ids(slide)
        primary = issue_ids[0] if issue_ids else ""
        evidence_ids = unique(
            [str(item).strip() for item in as_list(contract.get("body_evidence_ids")) if str(item).strip()]
            + [
                str(item).strip()
                for point in proof_points_from_blueprint_slide(slide)
                for item in as_list(point.get("evidence_ids"))
                if str(item).strip()
            ]
        )
        visual_plan = visual_plan_from_blueprint_slide(slide)
        chart_data = _normalize_chart_data(_visual_payload(slide, "chart_data"))
        compare_table_data = _normalize_compare_table_data(_visual_payload(slide, "compare_table_data"))
        payload = {
            "slide_no": slide_no,
            "fixed_page_role": slide.get("fixed_page_role") or slide.get("page_role") or FIXED_PAGE_ROLES.get(slide_no, ""),
            "slide_role": slide.get("fixed_page_role") or slide.get("page_role") or FIXED_PAGE_ROLES.get(slide_no, ""),
            "selected_page_type": page_type,
            "primary_issue_analysis_id": primary,
            "issue_analysis_ids": issue_ids,
            "claim_strength": str(contract.get("claim_strength") or slide.get("claim_strength") or "").strip(),
            "headline": str(slide.get("headline") or "").strip(),
            "main_message": str(slide.get("main_message") or "").strip(),
            "body_copy": body_copy,
            "chart_data": chart_data,
            "compare_table_data": compare_table_data,
            "visible_metric_claims": _visible_metric_claims_from_blueprint(slide, body_copy),
            "evidence_ids": evidence_ids,
            "source_note": _source_note(slide, evidence_ids),
            "pitch_relevance": str(slide.get("pitch_relevance") or slide.get("why_this_page_matters") or slide.get("investor_question") or "").strip(),
            "page_role": slide.get("fixed_page_role") or slide.get("page_role") or FIXED_PAGE_ROLES.get(slide_no, ""),
            "caveats": [str(item).strip() for item in as_list(slide.get("caveats")) if str(item).strip()],
            "open_questions": [str(item).strip() for item in as_list(slide.get("open_questions")) if str(item).strip()],
        }
        strategy_checks = slide.get("strategy_checks") if isinstance(slide.get("strategy_checks"), dict) else {}
        if str(strategy_checks.get("drilldown_role") or "").strip():
            payload["drilldown_role"] = str(strategy_checks.get("drilldown_role") or "").strip()
        if isinstance(strategy_checks.get("drill_down_from_slide"), int):
            payload["drill_down_from_slide"] = strategy_checks["drill_down_from_slide"]
        if as_list(strategy_checks.get("new_information_added")):
            payload["new_information_added"] = [
                str(item).strip()
                for item in as_list(strategy_checks.get("new_information_added"))
                if str(item).strip()
            ]
        if not payload["chart_data"] and visual_plan.get("required_capability") == "chart":
            # Leave the field empty instead of inventing chart data. Downstream
            # validators will block if the chosen page requires a chart.
            payload["chart_data"] = {}
        if not payload["compare_table_data"] and page_type == "compare_table_page":
            payload["compare_table_data"] = {}
        slides.append(payload)
        if slide_no in {1, 2, 3, 6, 7}:
            template_binding[f"slide_{slide_no}_variant"] = page_type
    return {
        "schema_version": "renderer_spec_v1",
        "section_meta": section_meta,
        "slides": slides,
        "template_binding": template_binding,
    }


def compile_deck_blueprint(
    issue_analysis: dict[str, Any],
    deck_blueprint: dict[str, Any],
    template_registry: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    page_plan = normalize_deck_blueprint_for_page_plan(deck_blueprint)
    page_contract = build_page_evidence_contract(issue_analysis, page_plan)
    renderer_spec = build_renderer_spec_from_deck_blueprint(deck_blueprint, template_registry, page_contract)
    return page_contract, renderer_spec


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue-analysis", required=True)
    parser.add_argument("--deck-blueprint", required=True)
    parser.add_argument("--template-registry", required=True)
    parser.add_argument("--page-contract-output", required=True)
    parser.add_argument("--renderer-spec-output", required=True)
    args = parser.parse_args()

    input_paths = [Path(args.issue_analysis), Path(args.deck_blueprint), Path(args.template_registry)]
    run_dir = _maybe_run_dir_from_inputs(input_paths)
    if run_dir is not None:
        try:
            _assert_upstream_package_valid(run_dir)
        except ValueError as exc:
            print(
                json.dumps(
                    {
                        "is_valid": False,
                        "error": str(exc),
                        "run_dir": str(run_dir),
                        "repair_hint": "Run scripts/state_report.py status/next, fix the failed upstream gate, then rerun compile_deck_blueprint.py. Do not compile derived renderer artifacts from a failed formal run.",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 1

    page_contract, renderer_spec = compile_deck_blueprint(
        load_json_file(input_paths[0]),
        load_json_file(input_paths[1]),
        load_json_file(input_paths[2]),
    )
    page_contract_path = Path(args.page_contract_output)
    renderer_spec_path = Path(args.renderer_spec_output)
    page_contract_path.parent.mkdir(parents=True, exist_ok=True)
    renderer_spec_path.parent.mkdir(parents=True, exist_ok=True)
    page_contract_path.write_text(json.dumps(page_contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    renderer_spec_path.write_text(json.dumps(renderer_spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "is_valid": True,
                "page_contract_output": str(page_contract_path),
                "renderer_spec_output": str(renderer_spec_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
