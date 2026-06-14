#!/usr/bin/env python3
"""Validate renderer-spec chart datapoints against research pack MET rows.

This gate isolates a common failure mode from the broader content-quality gate:
the renderer spec draws a chart using MET-IDs whose value, unit, period, or allowed
page-contract scope does not match the research pack. The output is intentionally
root-cause oriented so agents fix the chart or metric contract instead of
schema-chasing downstream PPT fields.
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
import sys
from pathlib import Path
from typing import Any, Optional

from json_utils import load_json_file
from validate_content_quality import (
    _is_percent_metric,
    _is_percent_source_row,
    _is_time_series_chart,
    _normalized_for_compare,
    _normalized_scope,
    _parse_chart_number,
    _row_category,
    _row_period,
    _row_series_name,
    chart_datapoint_count,
    chart_expected_datapoints,
    collect_chart_source_rows,
    collect_secondary_source_rows,
    parse_metric_reconciliation,
)


MET_RE = re.compile(r"^MET-\d{3}$")


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _metric_ids_in_value(value: Any) -> set[str]:
    ids: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "metric_id":
                text = str(child or "").strip()
                if text:
                    ids.add(text)
            elif key == "metric_ids":
                ids.update(str(item).strip() for item in _as_list(child) if str(item).strip())
            else:
                ids.update(_metric_ids_in_value(child))
    elif isinstance(value, list):
        for child in value:
            ids.update(_metric_ids_in_value(child))
    return ids


def _contract_by_slide(page_contract: Optional[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    if not isinstance(page_contract, dict):
        return {}
    by_slide: dict[int, dict[str, Any]] = {}
    for entry in page_contract.get("slides") or []:
        if not isinstance(entry, dict):
            continue
        try:
            by_slide[int(entry.get("slide_no"))] = entry
        except (TypeError, ValueError):
            continue
    return by_slide


def _add(
    root_causes: list[dict[str, Any]],
    errors: list[str],
    *,
    code: str,
    slide_no: Any,
    path: str,
    message: str,
    repair_hint: str,
) -> None:
    item = {
        "severity": "error",
        "code": code,
        "slide_no": slide_no,
        "path": path,
        "message": message,
        "repair_hint": repair_hint,
    }
    root_causes.append(item)
    errors.append(f"slide {slide_no}: {code}: {message}")


def _expected_for_row(
    row: dict[str, Any],
    idx: int,
    expected_datapoints: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    row_series = _normalized_scope(_row_series_name(row))
    row_category = _normalized_scope(_row_category(row))
    if row_series or row_category:
        for expected in expected_datapoints:
            expected_series = _normalized_scope(expected.get("series_name"))
            expected_category = _normalized_scope(expected.get("category"))
            series_matches = not row_series or not expected_series or row_series == expected_series
            category_matches = not row_category or not expected_category or row_category in expected_category
            if series_matches and category_matches:
                return expected
    return expected_datapoints[idx - 1] if idx - 1 < len(expected_datapoints) else None


def validate(
    renderer_spec: dict[str, Any],
    memo_text: str,
    page_contract: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    root_causes: list[dict[str, Any]] = []

    metrics = parse_metric_reconciliation(memo_text)
    contracts = _contract_by_slide(page_contract)

    for slide in renderer_spec.get("slides") or []:
        if not isinstance(slide, dict):
            continue
        slide_no = slide.get("slide_no")
        chart_data = slide.get("chart_data")
        if not isinstance(chart_data, dict):
            continue
        chart_type = str(chart_data.get("chart_type") or "").strip().lower()
        if chart_type in {"", "none", "no_chart", "text"}:
            continue

        primary_rows = collect_chart_source_rows(chart_data)
        secondary_rows = collect_secondary_source_rows(chart_data)
        if not primary_rows and not secondary_rows:
            continue

        contract = contracts.get(int(slide_no)) if str(slide_no).isdigit() else None
        contract_metric_ids = {
            str(item).strip()
            for item in _as_list(contract.get("chart_metric_ids") if isinstance(contract, dict) else [])
            if str(item).strip()
        }
        if isinstance(contract, dict) and contract.get("chart_allowed") is False and primary_rows:
            _add(
                root_causes,
                errors,
                code="CHART_NOT_ALLOWED",
                slide_no=slide_no,
                path="chart_data",
                message="chart_data is present but page_evidence_contract.chart_allowed=false",
                repair_hint="Remove chart_data or update the page evidence contract before renderer spec validation.",
            )

        expected_datapoints = chart_expected_datapoints(chart_data)
        datapoint_count = chart_datapoint_count(chart_data)
        if datapoint_count and len(primary_rows) < datapoint_count:
            _add(
                root_causes,
                errors,
                code="MISSING_CHART_SOURCE_ROWS",
                slide_no=slide_no,
                path="chart_data.source_rows",
                message=f"chart has {datapoint_count} datapoint(s) but only {len(primary_rows)} primary source_rows",
                repair_hint="Bind each primary chart datapoint to one explicit source_rows item and MET-ID.",
            )

        chart_metric_ids: list[str] = []
        is_time_series = _is_time_series_chart(chart_data)

        def validate_row(
            row: dict[str, Any],
            idx: int,
            row_path: str,
            *,
            collect_for_chart: bool,
            expected: Optional[dict[str, Any]] = None,
        ) -> None:
            metric_id = str(row.get("metric_id") or "").strip()
            value = row.get("value")
            path = f"{row_path}[{idx}]"
            has_numeric_value = isinstance(value, (int, float)) or bool(re.search(r"\d", str(value or "")))
            if has_numeric_value and not metric_id:
                _add(
                    root_causes,
                    errors,
                    code="MISSING_CHART_METRIC_ID",
                    slide_no=slide_no,
                    path=path,
                    message="quantitative chart source row has no metric_id",
                    repair_hint="Use an existing MET-ID from the research pack Metric Reconciliation or remove this datapoint.",
                )
                return
            if not metric_id:
                return
            if not MET_RE.match(metric_id) or metric_id not in metrics:
                _add(
                    root_causes,
                    errors,
                    code="UNKNOWN_CHART_METRIC",
                    slide_no=slide_no,
                    path=path,
                    message=f"chart source row references unknown {metric_id}",
                    repair_hint="Do not invent MET-IDs. Add the metric to the research pack reconciliation or bind an existing MET-ID.",
                )
                return
            if collect_for_chart:
                chart_metric_ids.append(metric_id)
            if contract_metric_ids and collect_for_chart and metric_id not in contract_metric_ids:
                _add(
                    root_causes,
                    errors,
                    code="UNALLOWED_CHART_METRIC",
                    slide_no=slide_no,
                    path=path,
                    message=f"{metric_id} is outside page_evidence_contract.chart_metric_ids",
                    repair_hint="Either change the chart datapoint or update page_evidence_contract through the issue-analysis/page-contract step.",
                )

            metric_row = metrics[metric_id]
            source_value = _parse_chart_number(value)
            metric_value = _parse_chart_number(metric_row.get("Value", ""))
            if source_value is not None and metric_value is not None:
                source_candidates = _normalized_for_compare(source_value, _is_percent_source_row(row, chart_data))
                metric_candidates = _normalized_for_compare(metric_value, _is_percent_metric(metric_row))
                if not any(
                    abs(source - metric) <= max(0.05, abs(metric) * 0.02)
                    for source in source_candidates
                    for metric in metric_candidates
                ):
                    _add(
                        root_causes,
                        errors,
                        code="MET_VALUE_MISMATCH",
                        slide_no=slide_no,
                        path=path,
                        message=f"value {value} does not match {metric_id} value {metric_row.get('Value', '')}",
                        repair_hint="Fix the chart value or bind the datapoint to the correct research pack MET-ID.",
                    )

            source_period = _row_period(row)
            metric_period = str(metric_row.get("Data Period") or "").strip()
            if source_period and metric_period and _normalized_scope(source_period) not in _normalized_scope(metric_period):
                _add(
                    root_causes,
                    errors,
                    code="MET_PERIOD_MISMATCH",
                    slide_no=slide_no,
                    path=path,
                    message=f"source row period '{source_period}' does not match {metric_id} Data Period '{metric_period}'",
                    repair_hint="Use the same period as the research pack metric, or create a separate metric row with the correct period.",
                )

            if expected:
                expected_series = str(expected.get("series_name") or "").strip()
                row_series = _row_series_name(row)
                if expected_series and row_series and _normalized_scope(row_series) != _normalized_scope(expected_series):
                    _add(
                        root_causes,
                        errors,
                        code="CHART_SERIES_MISMATCH",
                        slide_no=slide_no,
                        path=path,
                        message=f"source row series '{row_series}' does not align with chart series '{expected_series}'",
                        repair_hint="Align source_rows ordering/labels with chart_data.series and categories.",
                    )
                expected_category = str(expected.get("category") or "").strip()
                row_category = _row_category(row)
                if row_category and expected_category and _normalized_scope(row_category) not in _normalized_scope(expected_category):
                    _add(
                        root_causes,
                        errors,
                        code="CHART_CATEGORY_MISMATCH",
                        slide_no=slide_no,
                        path=path,
                        message=f"source row category/period '{row_category}' does not align with chart category '{expected_category}'",
                        repair_hint="Align source_rows categories with the chart axis before rendering.",
                    )

            if _is_percent_source_row(row, chart_data) and not _is_percent_metric(metric_row):
                _add(
                    root_causes,
                    errors,
                    code="MET_UNIT_MISMATCH",
                    slide_no=slide_no,
                    path=path,
                    message=f"percentage/share-like row binds to {metric_id} ({metric_row.get('Metric Type', '')} / {metric_row.get('Unit', '')})",
                    repair_hint="Bind share/rate datapoints only to share/rate MET rows, not market-size or revenue MET rows.",
                )

        for idx, row in enumerate(primary_rows, start=1):
            validate_row(
                row,
                idx,
                "chart_data.source_rows",
                collect_for_chart=True,
                expected=_expected_for_row(row, idx, expected_datapoints),
            )
        for idx, row in enumerate(secondary_rows, start=1):
            validate_row(row, idx, "chart_data.secondary_module.rows", collect_for_chart=False)

        unique_chart_ids = list(dict.fromkeys(chart_metric_ids))
        if len(unique_chart_ids) >= 2:
            rows_by_id = [metrics[met_id] for met_id in unique_chart_ids if met_id in metrics]
            if len(chart_metric_ids) != len(set(chart_metric_ids)) and datapoint_count > len(set(chart_metric_ids)):
                _add(
                    root_causes,
                    errors,
                    code="REUSED_CHART_METRIC_ID",
                    slide_no=slide_no,
                    path="chart_data.source_rows",
                    message="chart_data reuses MET-IDs across multiple distinct datapoints",
                    repair_hint="Each distinct datapoint should bind to its own MET-ID unless the value is intentionally repeated as context.",
                )

            comparable_fields = ["Metric Type", "Geography", "Unit"]
            if chart_type not in {"line", "line_chart"} and not is_time_series:
                comparable_fields.append("Data Period")
            for field in comparable_fields:
                values = {
                    str(metric_row.get(field) or "").strip().lower()
                    for metric_row in rows_by_id
                    if str(metric_row.get(field) or "").strip()
                }
                if len(values) > 1:
                    detail = ", ".join(
                        f"{met_id}={metrics[met_id].get(field, '')}"
                        for met_id in unique_chart_ids
                        if met_id in metrics
                    )
                    _add(
                        root_causes,
                        errors,
                        code="MIXED_CHART_SCOPE",
                        slide_no=slide_no,
                        path="chart_data.source_rows",
                        message=f"chart compares MET-IDs with mixed {field}: {detail}",
                        repair_hint="Use separate visuals, normalize the metric, or explicitly choose comparable metrics before charting.",
                    )
            for met_id in unique_chart_ids:
                status = str(metrics[met_id].get("Conflict Status") or "").strip().lower()
                if status in {"conflicting", "not_comparable", "unresolved"}:
                    _add(
                        root_causes,
                        errors,
                        code="UNRESOLVED_CHART_METRIC",
                        slide_no=slide_no,
                        path="chart_data.source_rows",
                        message=f"chart_data uses {met_id} with Conflict Status '{status}'",
                        repair_hint="Resolve the metric conflict or remove the chart datapoint from formal delivery.",
                    )

        explicit_ids = _metric_ids_in_value(chart_data)
        orphan_ids = sorted(met_id for met_id in explicit_ids if not MET_RE.match(met_id))
        for met_id in orphan_ids:
            warnings.append(f"slide {slide_no}: noncanonical chart metric id '{met_id}' found in chart_data")

    return {
        "is_valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "root_cause_count": len(root_causes),
        "root_causes": root_causes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate chart datapoint MET bindings before content-quality gate.")
    parser.add_argument("--renderer-spec", dest="renderer_spec", required=True, help="Path to renderer_spec.json.")
    parser.add_argument("--research-pack", dest="research_pack", required=True)
    parser.add_argument("--page-contract", help="Optional page_evidence_contract.json.")
    parser.add_argument("--output", help="Optional JSON report path.")
    args = parser.parse_args()

    renderer_spec_path = Path(args.renderer_spec)
    memo_path = Path(args.research_pack)
    page_contract_path = Path(args.page_contract) if args.page_contract else None

    renderer_spec = load_json_file(renderer_spec_path)
    memo_text = memo_path.read_text(encoding="utf-8")
    page_contract = load_json_file(page_contract_path) if page_contract_path and page_contract_path.exists() else None
    result = validate(renderer_spec, memo_text, page_contract)
    result.update(
        {
            "renderer_spec": str(renderer_spec_path),
            "research_pack": str(memo_path),
            "page_contract": str(page_contract_path) if page_contract_path else "",
        }
    )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["is_valid"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
