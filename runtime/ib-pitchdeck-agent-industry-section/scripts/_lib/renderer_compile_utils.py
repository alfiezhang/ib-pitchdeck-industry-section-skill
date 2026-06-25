#!/usr/bin/env python3
"""Compile banker-page-native deck_blueprint.json into renderer inputs."""

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

import copy
import re
from typing import Any

from deck_blueprint_utils import (
    FIXED_PAGE_ROLES,
    active_body_fields,
    as_list,
    banker_page_id_for_slide,
    metric_ids_from_visual,
    proof_points_from_blueprint_slide,
    required_body_fields,
    template_variants_by_slide,
    unique,
    visual_plan_from_blueprint_slide,
)
from runtime_utils import load_json_file


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
}

DEFAULT_SLIDE_REGISTRY_PATH = _IB_RUNTIME_ROOT / "configs" / "slide_registry.json"


def split_table_cells(text: str) -> list[str]:
    """Split display-only table text while preserving blank cells."""
    if "｜" in text:
        return [part.strip() for part in text.split("｜")]
    if "|" in text:
        stripped = text.strip().strip("|")
        return [part.strip() for part in stripped.split("|")]
    return [text.strip()] if text.strip() else []


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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _ids_from_blocks(slide: dict[str, Any], field: str) -> list[str]:
    values: list[str] = []
    for block in as_list(slide.get("body_blocks")):
        if isinstance(block, dict):
            values.extend(_text(item) for item in as_list(block.get(field)) if _text(item))
    return values


def _metric_ids_from_visible_claims(slide: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for claim in as_list(slide.get("visible_metric_claims")):
        if isinstance(claim, dict):
            values.extend(_text(item) for item in as_list(claim.get("metric_ids")) if _text(item))
    return values


def _permission(usage: str) -> dict[str, bool]:
    return {
        "headline_allowed": usage == "headline_allowed",
        "main_message_allowed": usage == "headline_allowed",
        "chart_allowed": usage in {"headline_allowed", "body_only"},
        "body_copy_allowed": usage in {"headline_allowed", "body_only", "supporting_context", "caveat_only"},
    }


def build_internal_deck_blueprint(banker_page_pack: dict[str, Any]) -> dict[str, Any]:
    slides: list[dict[str, Any]] = []
    for slide in as_list(banker_page_pack.get("slides")):
        if not isinstance(slide, dict):
            continue
        slide_no = int(slide.get("slide_no") or len(slides) + 1)
        banker_page_id = _text(slide.get("banker_page_id")) or f"BP-{slide_no:03d}"
        project_relevance_note = _text(slide.get("project_relevance_note"))
        blocks: list[dict[str, Any]] = []
        for block in as_list(slide.get("body_blocks")):
            if not isinstance(block, dict):
                continue
            item = dict(block)
            item.setdefault("source_banker_page_ids", [banker_page_id])
            if not _text(item.get("claim_strength")):
                item["claim_strength"] = _text(slide.get("claim_strength"))
            blocks.append(item)
        slides.append(
            {
                "slide_no": slide_no,
                "banker_page_id": banker_page_id,
                "fixed_page_role": _text(slide.get("fixed_page_role")) or FIXED_PAGE_ROLES.get(slide_no, ""),
                "page_primary_subject": _text(slide.get("page_primary_subject")),
                "page_question": _text(slide.get("page_question")),
                "page_thesis": _text(slide.get("banker_judgment")),
                "page_argument": _text(slide.get("page_argument")),
                "visual_intent": _text(slide.get("visual_intent") or slide.get("exhibit", {}).get("why_this_exhibit")),
                "evidence_role": _text(slide.get("evidence_role") or "thesis_anchor"),
                "exhibit": slide.get("exhibit") if isinstance(slide.get("exhibit"), dict) else {},
                "why_this_page_matters": project_relevance_note,
                "selected_page_type": _text(slide.get("selected_page_type")),
                "claim_strength": _text(slide.get("claim_strength")),
                "allowed_deck_usage": _text(slide.get("allowed_deck_usage")),
                "headline": _text(slide.get("headline")),
                "main_message": _text(slide.get("main_message")),
                "body_blocks": blocks,
                "body_copy": slide.get("body_copy") if isinstance(slide.get("body_copy"), dict) else {},
                "visual_design": slide.get("visual_design") if isinstance(slide.get("visual_design"), dict) else {},
                "chart_data": slide.get("chart_data") if isinstance(slide.get("chart_data"), dict) else {},
                "compare_table_data": slide.get("compare_table_data") if isinstance(slide.get("compare_table_data"), dict) else {},
                "visible_metric_claims": [item for item in as_list(slide.get("visible_metric_claims")) if isinstance(item, dict)],
                "source_note": _text(slide.get("source_note")),
                "caveats": [_text(item) for item in as_list(slide.get("caveats")) if _text(item)],
                "evidence_boundary_notes": [_text(item) for item in as_list(slide.get("evidence_boundary_notes")) if _text(item)],
                "strategy_checks": {
                    "new_information_added": [
                        _text(slide.get("banker_judgment")),
                        project_relevance_note,
                    ],
                    "source_artifact": "banker_page_pack.json",
                },
                "derived_from": "banker_page_pack",
            }
        )
    return {
        "schema_version": "deck_blueprint_v1",
        "section_meta": banker_page_pack.get("section_meta") if isinstance(banker_page_pack.get("section_meta"), dict) else {},
        "deck_storyline": _text(banker_page_pack.get("deck_storyline")),
        "slides": sorted(slides, key=lambda item: int(item.get("slide_no") or 0)),
        "authoring_status": "derived_from_banker_page_pack",
    }


def _visual_metric_ids(slide: dict[str, Any]) -> list[str]:
    return unique(metric_ids_from_visual(slide) + _metric_ids_from_visible_claims(slide))


def _metric_ids_for_slide(slide: dict[str, Any]) -> list[str]:
    return unique(
        [_text(item) for item in as_list(slide.get("metric_ids")) if _text(item)]
        + _ids_from_blocks(slide, "metric_ids")
        + _visual_metric_ids(slide)
    )


def _evidence_ids_for_slide(slide: dict[str, Any]) -> list[str]:
    return unique(
        [_text(item) for item in as_list(slide.get("evidence_ids")) if _text(item)]
        + _ids_from_blocks(slide, "evidence_ids")
    )


def _proof_standard(usage: str) -> str:
    if usage == "headline_allowed":
        return "Headline, main message, body copy, and material visuals may use this page's EV/MET IDs."
    if usage == "body_only":
        return "Use this page's EV/MET IDs in body copy and supporting visuals; avoid unqualified headline claims."
    if usage == "caveat_only":
        return "Use only as caveated context or route back to Research before promotion."
    return "Do not use as a deck claim until LLM authoring resolves evidence sufficiency."


def build_banker_page_contract(deck_blueprint: dict[str, Any]) -> dict[str, Any]:
    contract_slides: list[dict[str, Any]] = []
    for slide in as_list(deck_blueprint.get("slides")):
        if not isinstance(slide, dict):
            continue
        slide_no = int(slide.get("slide_no") or len(contract_slides) + 1)
        banker_page_id = banker_page_id_for_slide(slide) or f"BP-{slide_no:03d}"
        claim_strength = _text(slide.get("claim_strength"))
        usage = _text(slide.get("allowed_deck_usage")) or "not_allowed"
        permission = _permission(usage)
        proof_points = proof_points_from_blueprint_slide(slide)
        body_evidence_ids = unique(
            _evidence_ids_for_slide(slide)
            + [
                _text(item)
                for point in proof_points
                for item in as_list(point.get("evidence_ids"))
                if _text(item)
            ]
        )
        body_metric_ids = unique(
            _metric_ids_for_slide(slide)
            + [
                _text(item)
                for point in proof_points
                for item in as_list(point.get("metric_ids"))
                if _text(item)
            ]
        )
        visual_plan = visual_plan_from_blueprint_slide(slide)
        visual_metric_ids = unique(_visual_metric_ids(slide) + [_text(item) for item in as_list(visual_plan.get("visual_metric_ids")) if _text(item)])
        chart_metric_ids = visual_metric_ids if visual_plan.get("required_capability") == "chart" else []
        contract_slides.append(
            {
                "slide_no": slide_no,
                "banker_page_id": banker_page_id,
                "page_role": _text(slide.get("fixed_page_role") or slide.get("page_role")) or FIXED_PAGE_ROLES.get(slide_no, ""),
                "page_question": _text(slide.get("page_question")),
                "headline_claim": _text(slide.get("headline")),
                "proof_standard": _proof_standard(usage),
                "allowed_deck_usage": usage,
                "headline_allowed": permission["headline_allowed"],
                "main_message_allowed": permission["main_message_allowed"],
                "downstream_permission": permission,
                "chart_allowed": permission["chart_allowed"],
                "visual_metric_allowed": permission["chart_allowed"] and bool(visual_metric_ids),
                "chart_metric_ids": chart_metric_ids,
                "allowed_visual_metric_ids": visual_metric_ids if permission["chart_allowed"] else [],
                "body_evidence_ids": body_evidence_ids if permission["body_copy_allowed"] else [],
                "body_metric_ids": body_metric_ids if permission["body_copy_allowed"] else [],
                "proof_points": proof_points if permission["body_copy_allowed"] else [],
                "claim_strength": claim_strength,
                "evidence_limited_exhibit_plan": _text(
                    visual_plan.get("evidence_limited_exhibit_plan")
                    or slide.get("evidence_limited_exhibit_plan")
                ),
                "caveats": [_text(item) for item in as_list(slide.get("caveats")) if _text(item)],
                "evidence_boundary_notes": [_text(item) for item in as_list(slide.get("evidence_boundary_notes")) if _text(item)],
            }
        )
    return {"schema_version": "page_evidence_contract_v1", "slides": sorted(contract_slides, key=lambda item: int(item.get("slide_no") or 0))}


def compile_banker_page_pack(
    banker_page_pack: dict[str, Any],
    template_registry: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    deck_blueprint = build_internal_deck_blueprint(banker_page_pack)
    page_contract = build_banker_page_contract(deck_blueprint)
    renderer_spec = build_renderer_spec_from_deck_blueprint(deck_blueprint, template_registry, page_contract)
    return deck_blueprint, page_contract, renderer_spec


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
    if isinstance(explicit, dict) and explicit:
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
        if fields and all(body.get(field) for field in fields):
            target = fields[-1]
            for idx_text in unmapped:
                block = blocks[int(idx_text) - 1]
                extra = _body_text(block)
                if extra:
                    body[target] = (body[target] + "\n" + extra).strip()
            return body
        raise ValueError(
            f"slide {slide_no}: {len(unmapped)} body block(s) could not be mapped by target_field or role: "
            f"blocks {', '.join(unmapped)}. Set target_field on those blocks or provide explicit body_copy."
        )
    return body


def _visible_metric_claims_from_blueprint(
    slide: dict[str, Any],
    body_copy: dict[str, str],
    allowed_metric_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    explicit = slide.get("visible_metric_claims")
    restrict_metrics = allowed_metric_ids is not None
    allowed = set(allowed_metric_ids or [])
    if isinstance(explicit, list) and explicit:
        if restrict_metrics and not allowed:
            return []
        filtered: list[dict[str, Any]] = []
        for item in explicit:
            if not isinstance(item, dict):
                continue
            metric_ids = unique(
                [
                    str(metric_id).strip()
                    for metric_id in as_list(item.get("metric_ids"))
                    if str(metric_id).strip() and (not restrict_metrics or str(metric_id).strip() in allowed)
                ]
            )
            if metric_ids:
                row = dict(item)
                row["metric_ids"] = metric_ids
                filtered.append(row)
        return filtered

    claims: list[dict[str, Any]] = []
    proof_points = proof_points_from_blueprint_slide(slide)
    all_metrics = unique(
        [
            str(item).strip()
            for point in proof_points
            for item in as_list(point.get("metric_ids"))
            if str(item).strip() and (not restrict_metrics or str(item).strip() in allowed)
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
            metrics = unique(
                [
                    str(item).strip()
                    for item in as_list(point.get("metric_ids"))
                    if str(item).strip() and (not restrict_metrics or str(item).strip() in allowed)
                ]
            )
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
                        if key not in {"label", "name", "metric_ids", "evidence_ids", "source_banker_page_ids"}
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
        banker_page_id = banker_page_id_for_slide(slide)
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
        allowed_visible_metric_ids = unique(
            [
                str(item).strip()
                for key in ("chart_metric_ids", "allowed_visual_metric_ids", "body_metric_ids")
                for item in as_list(contract.get(key))
                if str(item).strip()
            ]
        )
        payload = {
            "slide_no": slide_no,
            "fixed_page_role": slide.get("fixed_page_role") or slide.get("page_role") or FIXED_PAGE_ROLES.get(slide_no, ""),
            "slide_role": slide.get("fixed_page_role") or slide.get("page_role") or FIXED_PAGE_ROLES.get(slide_no, ""),
            "selected_page_type": page_type,
            "banker_page_id": banker_page_id,
            "claim_strength": str(contract.get("claim_strength") or slide.get("claim_strength") or "").strip(),
            "exhibit": slide.get("exhibit") if isinstance(slide.get("exhibit"), dict) else {},
            "headline": str(slide.get("headline") or "").strip(),
            "main_message": str(slide.get("main_message") or "").strip(),
            "body_copy": body_copy,
            "chart_data": chart_data,
            "compare_table_data": compare_table_data,
            "visible_metric_claims": _visible_metric_claims_from_blueprint(
                slide,
                body_copy,
                allowed_visible_metric_ids,
            ),
            "evidence_ids": evidence_ids,
            "source_note": _source_note(slide, evidence_ids),
            "page_role": slide.get("fixed_page_role") or slide.get("page_role") or FIXED_PAGE_ROLES.get(slide_no, ""),
            "caveats": [str(item).strip() for item in as_list(slide.get("caveats")) if str(item).strip()],
            "evidence_boundary_notes": [str(item).strip() for item in as_list(slide.get("evidence_boundary_notes")) if str(item).strip()],
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


def load_slide_registry(path: _IbPath | None = None) -> dict[str, Any]:
    registry_path = path or DEFAULT_SLIDE_REGISTRY_PATH
    registry = load_json_file(registry_path)
    if not isinstance(registry, dict) or not isinstance(registry.get("slides"), list):
        raise ValueError(f"Invalid slide registry: {registry_path}")
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


def controlled_layout_variants(registry: dict[str, Any]) -> dict[str, list[str]]:
    variants: dict[str, list[str]] = {}
    for slide in registry.get("slides") or []:
        if slide.get("selection_mode") != "controlled_choice":
            continue
        slide_key = str(slide.get("slide_key") or "")
        variants[slide_key] = list((slide.get("variants") or {}).keys())
    return variants


SLIDE_REGISTRY = load_slide_registry()


def normalize_compare_table_payload(slide_data: dict[str, Any]) -> tuple[list[str], list[list[str]]]:
    compare_table = slide_data.get("compare_table_data")
    if isinstance(compare_table, dict):
        headers = [str(item).strip() for item in compare_table.get("headers") or []]
        rows: list[list[str]] = []
        for row in compare_table.get("rows") or []:
            if not isinstance(row, dict):
                continue
            label = str(row.get("label") or "").strip()
            cells = [str(item).strip() for item in row.get("cells") or []]
            rows.append([label] + cells)
        return headers, rows
    return [], []


def _clean_source_footer(source_note: str) -> str:
    if not source_note:
        return source_note
    cleaned = re.sub(r"^(?:Sources\s*[:：]?\s*)+", "", source_note, flags=re.IGNORECASE).strip()
    return cleaned if cleaned else source_note


SLIDE_KEY_MAP = {
    "industry_overview": "industry_overview",
    "market_size_segmentation": "market_size_segmentation",
    "growth_drivers": "key_industry_drivers",
    "value_chain_profit_pool": "value_chain_profit_pool",
    "barriers_value_drivers": "key_barriers_value_drivers",
    "competitive_landscape": "competitive_landscape",
    "industry_trends_future_evolution": "industry_trends_future_evolution",
    "industry_takeaways_for_project": "industry_takeaways_for_project",
}

CHART_PAGE_TYPES = {"industry_overview_dynamic_page", "chart_page", "chart_plus_mini_table_page"}

EXPECTED_CONTENT_FIELDS = {
    1: {"industry_overview_dynamic_page": ["bullet_1", "bullet_2", "bullet_3"]},
    2: {
        "chart_page": ["bullet_1", "bullet_2", "bullet_3"],
        "chart_plus_mini_table_page": [
            "bullet_1",
            "bullet_2",
            "table_header_1",
            "table_header_2",
            "table_row_1",
            "table_row_2",
            "table_row_3",
        ],
    },
    3: {
        "driver_card_page": ["card_1", "card_2", "card_3", "card_4"],
        "driver_card_5_page": ["card_1", "card_2", "card_3", "card_4", "card_5"],
        "driver_card_6_page": ["card_1", "card_2", "card_3", "card_4", "card_5", "card_6"],
    },
    4: {
        "value_chain_page": [
            "top_left",
            "top_center",
            "top_right",
            "bottom_left",
            "bottom_center",
            "bottom_right",
        ],
    },
    5: {"moat_page": ["card_1", "card_2", "card_3"]},
    6: {
        "compare_table_page": [
            "table_header",
            "table_row_1",
            "table_row_2",
            "table_row_3",
            "table_row_4",
            "table_row_5",
            "table_row_6",
            "right_top",
            "right_mid",
            "right_bottom",
        ],
        "matrix_page": [
            "left_panel",
            "matrix_title",
            "matrix_label_x",
            "matrix_label_y",
            "right_top",
            "right_mid",
            "right_bottom",
        ],
    },
    7: {
        "trend_page": ["card_1", "card_2", "card_3"],
        "timeline_page": ["stage_1", "stage_2", "stage_3", "stage_4", "timeline_note"],
        "trend_4_card_page": ["card_1", "card_2", "card_3", "card_4"],
        "trend_5_card_page": ["card_1", "card_2", "card_3", "card_4", "card_5"],
        "trend_6_card_page": ["card_1", "card_2", "card_3", "card_4", "card_5", "card_6"],
    },
    8: {"summary_page": ["left_panel", "right_top", "right_mid", "right_bottom"]},
}


def convert_meta(renderer_spec: dict[str, Any]) -> dict[str, Any]:
    meta = renderer_spec.get("section_meta", {})
    return {
        "target_company": meta.get("target_name", ""),
        "transaction_type": "",
        "industry": meta.get("industry", ""),
        "subsector": "",
        "geography": meta.get("geography", ""),
        "language": "English" if meta.get("language") == "en" else "Chinese",
    }


def convert_slide(renderer_slide: dict[str, Any]) -> dict[str, Any]:
    slide_role = renderer_slide.get("slide_role", "")
    slide_key = SLIDE_KEY_MAP.get(slide_role, slide_role)
    page_type = renderer_slide.get("selected_page_type", "")
    chart_data = renderer_slide.get("chart_data") or {}
    if chart_data.get("title"):
        chart_title = chart_data["title"]
    elif page_type in CHART_PAGE_TYPES:
        chart_title = renderer_slide.get("visual_direction", "")
    else:
        chart_title = ""

    content = copy.deepcopy(renderer_slide.get("body_copy", {}) or {})
    if page_type == "compare_table_page":
        headers, rows = normalize_compare_table_payload(renderer_slide)
        if headers:
            content["table_header"] = "｜".join(headers)
        for idx, row_cells in enumerate(rows[:6], start=1):
            content[f"table_row_{idx}"] = "｜".join(row_cells)

    return {
        "slide_no": renderer_slide.get("slide_no", 0),
        "slide_key": slide_key,
        "selected_page_type": page_type,
        "slide_title": renderer_slide.get("headline", ""),
        "main_takeaway": renderer_slide.get("main_message", ""),
        "content": content,
        "chart_title": chart_title,
        "source_footer": _clean_source_footer(renderer_slide.get("source_note", "")),
        "speaker_note": "",
    }


def convert_rules(template_binding: dict[str, Any]) -> dict[str, Any]:
    return {
        "active_slide_keys_only": True,
        "controlled_layout_variants": controlled_layout_variants(SLIDE_REGISTRY),
        "slide_02_table_fields_only_active_for_chart_plus_mini_table_page": True,
        "inactive_variant_fields_may_remain_blank": True,
        "selected_page_type_required_for_variant_slides": True,
        "title_should_be_conclusion_led": True,
        "takeaway_one_sentence_only": True,
        "content_fields_should_follow_slide_registry": True,
        "content_fields_should_match_ppt_mapping_roles": True,
        "source_footer_required": True,
    }


def validate_variant_consistency(slides: list[dict[str, Any]], template_binding: dict[str, Any]) -> tuple[list[str], dict[int, str]]:
    warnings = []
    normalized_page_types = {}
    variant_map = {
        slide_no: (binding_key, sorted(valid_types))
        for slide_no, (binding_key, valid_types) in variant_page_types(SLIDE_REGISTRY).items()
    }
    for slide in slides:
        slide_no = slide.get("slide_no", 0)
        if slide_no not in variant_map:
            continue
        binding_key, valid_types = variant_map[slide_no]
        expected = template_binding.get(binding_key, "")
        actual = slide.get("selected_page_type", "")
        if expected and expected not in valid_types:
            raise ValueError(
                f"Slide {slide_no}: template_binding.{binding_key}='{expected}' is invalid. "
                f"Allowed values: {', '.join(valid_types)}."
            )
        if expected and actual and expected != actual:
            warnings.append(
                f"Slide {slide_no}: selected_page_type '{actual}' does not match "
                f"template_binding.{binding_key} '{expected}'. Using template_binding value."
            )
            normalized_page_types[slide_no] = expected
    return warnings, normalized_page_types


def validate_content_fields(slides: list[dict[str, Any]]) -> list[str]:
    warnings = []
    for slide in slides:
        slide_no = slide.get("slide_no", 0)
        page_type = slide.get("selected_page_type", "")
        body_copy = slide.get("content") or slide.get("body_copy") or {}
        expected_by_type = EXPECTED_CONTENT_FIELDS.get(slide_no, {})
        expected_fields = expected_by_type.get(page_type)
        if expected_fields is None:
            warnings.append(f"Slide {slide_no}: no expected content-field contract for page type '{page_type}'.")
            continue
        if slide_no == 6 and page_type == "compare_table_page":
            populated_rows = [
                field
                for field in [f"table_row_{idx}" for idx in range(1, 7)]
                if str(body_copy.get(field, "")).strip()
            ]
            if len(populated_rows) >= 3:
                missing_row_fields = [
                    field
                    for field in [f"table_row_{idx}" for idx in range(1, 7)]
                    if field not in populated_rows
                ]
                expected_fields = [field for field in expected_fields if field not in missing_row_fields]

        missing_fields = [field for field in expected_fields if field not in body_copy]
        empty_fields = [
            field
            for field in expected_fields
            if field in body_copy and str(body_copy.get(field, "")).strip() == ""
        ]
        extra_fields = sorted(set(body_copy.keys()) - set(expected_fields))
        if missing_fields:
            warnings.append(f"Slide {slide_no} ({page_type}): missing active body_copy fields: {', '.join(missing_fields)}.")
        if empty_fields:
            warnings.append(f"Slide {slide_no} ({page_type}): empty active body_copy fields: {', '.join(empty_fields)}.")
        if extra_fields:
            warnings.append(f"Slide {slide_no} ({page_type}): extra body_copy fields ignored by active layout: {', '.join(extra_fields)}.")
    return warnings


def build_token_source(renderer_spec: dict[str, Any]) -> dict[str, Any]:
    template_binding = renderer_spec.get("template_binding", {})
    renderer_slides = renderer_spec.get("slides", [])
    warnings, normalized_page_types = validate_variant_consistency(renderer_slides, template_binding)
    normalized_slides = copy.deepcopy(renderer_slides)
    for slide in normalized_slides:
        slide_no = int(slide.get("slide_no", 0) or 0)
        if slide_no in normalized_page_types:
            slide["selected_page_type"] = normalized_page_types[slide_no]
    converted_slides = [convert_slide(slide) for slide in normalized_slides]
    warnings.extend(validate_content_fields(converted_slides))
    return {
        "token_source": {
            "meta": convert_meta(renderer_spec),
            "slides": converted_slides,
            "rules": convert_rules(template_binding),
        },
        "warnings": warnings,
    }
