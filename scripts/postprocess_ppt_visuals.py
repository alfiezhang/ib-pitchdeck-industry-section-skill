#!/usr/bin/env python3

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Union

try:
    from pptx import Presentation
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE, XL_DATA_LABEL_POSITION, XL_LEGEND_POSITION
    from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Emu, Pt
    from pptx.dml.color import RGBColor
except ImportError as exc:
    raise SystemExit(
        "python-pptx is required for postprocess_ppt_visuals.py. "
        "Run this script with a Python environment that has the `pptx` package installed, "
        "such as the project virtualenv created by `./setup.sh`."
    ) from exc


SCAFFOLD_LABELS = {
    "PRIMARY CHART",
    "CHART / VISUAL",
    "MINI TABLE / SEGMENT CUT",
    "POINT 1",
    "POINT 2",
    "POINT 3",
    "STANDARD",
    "SUMMARY_PAGE",
    "CHART_PAGE",
    "CHART_PLUS_MINI_TABLE_PAGE",
    "DRIVER_CARD_PAGE",
    "VALUE_CHAIN_PAGE",
    "MOAT_PAGE",
    "COMPARE_TABLE_PAGE",
    "MATRIX_PAGE",
    "TREND_PAGE",
    "TIMELINE_PAGE",
    "industry_overview",
    "market_size_segmentation",
    "key_industry_drivers",
    "value_chain_profit_pool",
    "key_barriers_value_drivers",
    "competitive_landscape",
    "industry_trends_future_evolution",
    "key_takeaways_for_target",
}

SLIDE_LAYOUTS = {
    1: {
        "summary_page": {
            "title_box": (3785616, 1655064, 7607808, 360000),
            "visual_box": (3920000, 2350000, 7300000, 2850000),
        }
    },
    2: {
    "chart_page": {
        "title_box": (896112, 1655064, 4764024, 360000),
        "chart_box": (1000000, 2200000, 4450000, 3000000),
    },
    "chart_plus_mini_table_page": {
        "title_box": (896112, 1655064, 4764024, 360000),
        "chart_box": (1000000, 2200000, 4450000, 3000000),
    },
    },
    6: {
        "matrix_page": {
            "matrix_box": (3980000, 2380000, 4100000, 2500000),
        },
    },
}

BRAND_BLUE = RGBColor(0x0D, 0x57, 0xAA)
GRID_GRAY = RGBColor(0xD9, 0xD9, 0xD9)
TEXT_GRAY = RGBColor(0x55, 0x55, 0x55)
ACCENT_RED = RGBColor(0xC0, 0x3C, 0x28)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(data: dict, path: Path) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def clear_text(shape) -> None:
    if not hasattr(shape, "text_frame"):
        return
    text_frame = shape.text_frame
    text_frame.clear()


def set_single_paragraph(shape, text: str) -> None:
    text_frame = shape.text_frame
    text_frame.clear()
    paragraph = text_frame.paragraphs[0]
    run = paragraph.add_run()
    run.text = text


def remove_scaffold_labels(prs: Presentation) -> list[dict]:
    removed = []
    for slide_idx, slide in enumerate(prs.slides, start=1):
        for shape in slide.shapes:
            if not hasattr(shape, "text"):
                continue
            text = shape.text.strip()
            if text in SCAFFOLD_LABELS:
                clear_text(shape)
                removed.append({"slide_no": slide_idx, "label": text, "shape_name": shape.name})
    return removed


def find_slide_data(storyboard: dict, slide_no: int) -> Optional[dict]:
    for slide in storyboard.get("slides", []):
        if slide.get("slide_no") == slide_no:
            return slide
    return None


def apply_chart_title(slide, text: str, layout: dict) -> bool:
    if not text:
        return False
    left, top, width, height = layout["title_box"]
    candidates = []
    for shape in slide.shapes:
        if not hasattr(shape, "text_frame"):
            continue
        if abs(shape.left - left) < 20000 and abs(shape.top - top) < 20000:
            candidates.append(shape)
    if not candidates:
        return False
    target = sorted(candidates, key=lambda shp: (abs(shp.width - width), abs(shp.height - height)))[0]
    set_single_paragraph(target, text)
    paragraph = target.text_frame.paragraphs[0]
    if paragraph.runs:
        font = paragraph.runs[0].font
        font.size = Pt(10)
        font.color.rgb = TEXT_GRAY
        font.bold = False
    return True


def build_chart(slide, slide_data: dict, layout: dict) -> dict:
    chart_data = slide_data.get("chart_data") or {}
    series = chart_data.get("series") or []
    categories = chart_data.get("categories") or []
    if not series or not categories:
        return {"rendered": False, "reason": "missing chart_data series/categories"}

    chart_series = series[0]
    values = chart_series.get("values") or []
    if len(values) != len(categories):
        return {"rendered": False, "reason": "series/category length mismatch"}

    chart_title = chart_data.get("title") or ""
    apply_chart_title(slide, chart_title, layout)

    chart_payload = CategoryChartData()
    chart_payload.categories = categories
    chart_payload.add_series(chart_series.get("name") or "", values)

    left, top, width, height = layout["chart_box"]
    graphic_frame = slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED,
        Emu(left),
        Emu(top),
        Emu(width),
        Emu(height),
        chart_payload,
    )
    chart = graphic_frame.chart
    chart.has_title = False
    chart.has_legend = len(series) > 1
    if chart.has_legend:
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False

    category_axis = chart.category_axis
    category_axis.tick_labels.font.size = Pt(9)
    category_axis.tick_labels.font.color.rgb = TEXT_GRAY

    value_axis = chart.value_axis
    value_axis.has_major_gridlines = True
    value_axis.major_gridlines.format.line.color.rgb = GRID_GRAY
    value_axis.tick_labels.font.size = Pt(9)
    value_axis.tick_labels.font.color.rgb = TEXT_GRAY
    value_axis.format.line.color.rgb = GRID_GRAY

    plot = chart.plots[0]
    plot.has_data_labels = True
    data_labels = plot.data_labels
    data_labels.position = XL_DATA_LABEL_POSITION.OUTSIDE_END
    data_labels.font.size = Pt(9)
    data_labels.font.bold = True
    data_labels.number_format = '#,##0'

    for s in chart.series:
        fill = s.format.fill
        fill.solid()
        fill.fore_color.rgb = BRAND_BLUE
        s.format.line.color.rgb = BRAND_BLUE

    return {
        "rendered": True,
        "chart_title": chart_title,
        "chart_type": chart_data.get("chart_type"),
        "categories": categories,
        "series_name": chart_series.get("name") or "",
    }


def _coerce_float(value, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _matrix_points_from_chart_data(chart_data: dict) -> list[dict]:
    rows = chart_data.get("source_rows") or []
    points = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or "").strip()
        x = _coerce_float(row.get("x"))
        y = _coerce_float(row.get("y"))
        if x is None or y is None:
            value = row.get("value")
            if isinstance(value, dict):
                x = _coerce_float(value.get("x"))
                y = _coerce_float(value.get("y"))
            elif isinstance(value, (list, tuple)) and len(value) >= 2:
                x = _coerce_float(value[0])
                y = _coerce_float(value[1])
        if label and x is not None and y is not None:
            points.append({"label": label, "x": x, "y": y, "note": row.get("note", "")})

    if points:
        return points

    categories = chart_data.get("categories") or []
    series = chart_data.get("series") or []
    if len(series) < 2:
        return []
    x_values = series[0].get("values") or []
    y_values = series[1].get("values") or []
    for idx, label in enumerate(categories):
        if idx >= len(x_values) or idx >= len(y_values):
            continue
        x = _coerce_float(x_values[idx])
        y = _coerce_float(y_values[idx])
        if label and x is not None and y is not None:
            points.append({"label": str(label), "x": x, "y": y, "note": ""})
    return points


def _normalize(value: float, values: list[float]) -> float:
    min_value = min(values)
    max_value = max(values)
    if max_value == min_value:
        return 0.5
    return (value - min_value) / (max_value - min_value)


def _add_textbox(slide, left: int, top: int, width: int, height: int, text: str, font_size: int = 8, bold: bool = False) -> None:
    textbox = slide.shapes.add_textbox(Emu(left), Emu(top), Emu(width), Emu(height))
    tf = textbox.text_frame
    tf.clear()
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = text
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.color.rgb = TEXT_GRAY


def render_matrix_slide(slide, slide_data: dict, layout: dict) -> dict:
    chart_data = slide_data.get("chart_data") or {}
    body_copy = slide_data.get("body_copy") or {}
    points = _matrix_points_from_chart_data(chart_data)
    if len(points) < 2:
        return {"rendered": False, "reason": "matrix_page needs at least two points with x/y values"}

    left, top, width, height = layout["matrix_box"]
    axis_label_x = body_copy.get("matrix_label_x") or chart_data.get("x_axis_label") or "Axis X"
    axis_label_y = body_copy.get("matrix_label_y") or chart_data.get("y_axis_label") or "Axis Y"

    # Background panel.
    panel = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.RECTANGLE,
        Emu(left),
        Emu(top),
        Emu(width),
        Emu(height),
    )
    panel.fill.solid()
    panel.fill.fore_color.rgb = RGBColor(0xFA, 0xFB, 0xFC)
    panel.line.color.rgb = GRID_GRAY
    panel.line.width = Pt(1)

    mid_x = left + width // 2
    mid_y = top + height // 2
    for line_left, line_top, line_width, line_height in [
        (mid_x, top, 0, height),
        (left, mid_y, width, 0),
    ]:
        line = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.RECTANGLE,
            Emu(line_left),
            Emu(line_top),
            Emu(max(line_width, 1)),
            Emu(max(line_height, 1)),
        )
        line.fill.solid()
        line.fill.fore_color.rgb = GRID_GRAY
        line.line.color.rgb = GRID_GRAY

    _add_textbox(slide, left, top + height + 80000, width, 180000, axis_label_x, 8, True)
    _add_textbox(slide, left - 240000, top + height // 2 - 120000, 220000, 260000, axis_label_y, 8, True)

    x_values = [point["x"] for point in points]
    y_values = [point["y"] for point in points]
    bubble_size = 175000
    plotted = []
    for idx, point in enumerate(points[:8]):
        x_norm = _normalize(point["x"], x_values)
        y_norm = _normalize(point["y"], y_values)
        cx = left + int(260000 + x_norm * (width - 520000))
        cy = top + int(height - 260000 - y_norm * (height - 520000))

        bubble = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.OVAL,
            Emu(cx - bubble_size // 2),
            Emu(cy - bubble_size // 2),
            Emu(bubble_size),
            Emu(bubble_size),
        )
        bubble.fill.solid()
        bubble.fill.fore_color.rgb = BRAND_BLUE if idx else ACCENT_RED
        bubble.line.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        bubble.line.width = Pt(1)

        label_left = min(max(cx - 360000, left + 20000), left + width - 720000)
        label_top = min(max(cy + 90000, top + 20000), top + height - 220000)
        _add_textbox(slide, label_left, label_top, 720000, 180000, point["label"], 7, idx == 0)
        plotted.append({"label": point["label"], "x": point["x"], "y": point["y"]})

    return {
        "rendered": True,
        "chart_title": chart_data.get("title") or body_copy.get("matrix_title") or "",
        "chart_type": "matrix",
        "points": plotted,
    }


def add_metric_card(slide, left: int, top: int, width: int, height: int, label: str, value: str, accent: RGBColor) -> None:
    from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
    from pptx.enum.text import PP_ALIGN

    shape = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
        Emu(left),
        Emu(top),
        Emu(width),
        Emu(height),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    shape.line.color.rgb = GRID_GRAY
    shape.line.width = Pt(1)

    text_frame = shape.text_frame
    text_frame.clear()
    text_frame.word_wrap = True

    p1 = text_frame.paragraphs[0]
    p1.alignment = PP_ALIGN.CENTER
    r1 = p1.add_run()
    r1.text = label
    r1.font.size = Pt(10)
    r1.font.bold = True
    r1.font.color.rgb = TEXT_GRAY

    p2 = text_frame.add_paragraph()
    p2.alignment = PP_ALIGN.CENTER
    r2 = p2.add_run()
    r2.text = value
    r2.font.size = Pt(24)
    r2.font.bold = True
    r2.font.color.rgb = accent


def add_supporting_note(slide, left: int, top: int, width: int, height: int, text: str) -> None:
    from pptx.enum.text import PP_ALIGN

    textbox = slide.shapes.add_textbox(Emu(left), Emu(top), Emu(width), Emu(height))
    tf = textbox.text_frame
    tf.clear()
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = text
    r.font.size = Pt(10)
    r.font.color.rgb = TEXT_GRAY


def format_metric_value(label: str, value: Union[float, int], unit: str) -> str:
    if "%" in label or "同比" in label or "增速" in label:
        return f"{value:+.1f}%"
    is_integer = isinstance(value, int) or (isinstance(value, float) and value.is_integer())
    if "亿元" in label or "规模" in label or "亿元" in unit or "人民币" in unit:
        if is_integer:
            return f"{int(value):,}亿元"
        return f"{value:,.1f}亿元"
    if is_integer:
        return f"{int(value):,}"
    return f"{value:,.1f}"


def render_slide1_visual(slide, slide_data: dict, layout: dict) -> dict:
    chart_data = slide_data.get("chart_data") or {}
    rows = chart_data.get("source_rows") or []
    if len(rows) < 2:
        return {"rendered": False, "reason": "slide 1 needs at least two source_rows for metric cards"}

    chart_title = chart_data.get("title") or ""
    apply_chart_title(slide, chart_title, layout)

    left, top, width, height = layout["visual_box"]
    gap = 240000
    card_width = (width - gap) // 2
    card_height = 1500000

    first = rows[0]
    second = rows[1]
    unit = chart_data.get("unit") or ""

    add_metric_card(
        slide,
        left,
        top,
        card_width,
        card_height,
        first.get("label", ""),
        format_metric_value(first.get("label", ""), first.get("value", 0), unit),
        RGBColor(0xC0, 0x3C, 0x28),
    )
    add_metric_card(
        slide,
        left + card_width + gap,
        top,
        card_width,
        card_height,
        second.get("label", ""),
        format_metric_value(second.get("label", ""), second.get("value", 0), unit),
        BRAND_BLUE,
    )

    notes = chart_data.get("notes") or ""
    if notes:
        add_supporting_note(slide, left, top + card_height + 220000, width, 600000, notes)

    return {
        "rendered": True,
        "chart_title": chart_title,
        "chart_type": chart_data.get("chart_type"),
        "mode": "metric_cards",
    }


def render_quant_slide(prs: Presentation, storyboard: dict, slide_no: int) -> dict:
    slide_data = find_slide_data(storyboard, slide_no)
    if not slide_data:
        return {"slide_no": slide_no, "rendered": False, "reason": f"slide {slide_no} not found in storyboard"}

    page_type = slide_data.get("selected_page_type")
    slide_layouts = SLIDE_LAYOUTS.get(slide_no, {})
    layout = slide_layouts.get(page_type)
    if not layout:
        return {"slide_no": slide_no, "rendered": False, "reason": f"unsupported page type: {page_type}"}

    if len(prs.slides) < slide_no:
        return {"slide_no": slide_no, "rendered": False, "reason": "clean deck has fewer slides than expected"}

    slide = prs.slides[slide_no - 1]
    if page_type == "matrix_page":
        result = render_matrix_slide(slide, slide_data, layout)
    elif slide_no == 1:
        result = render_slide1_visual(slide, slide_data, layout)
    else:
        result = build_chart(slide, slide_data, layout)
    result["slide_no"] = slide_no
    result["selected_page_type"] = page_type
    return result


def save_presentation(prs: Presentation, output_path: Path) -> None:
    if output_path.exists():
        with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        prs.save(tmp_path)
        shutil.move(str(tmp_path), output_path)
        return
    prs.save(output_path)


def postprocess(input_ppt: Path, storyboard_path: Path, output_ppt: Path) -> dict:
    storyboard = load_json(storyboard_path)
    prs = Presentation(str(input_ppt))

    removed_labels = remove_scaffold_labels(prs)
    chart_results = []
    for slide_data in storyboard.get("slides", []):
        if slide_data.get("chart_data"):
            chart_results.append(render_quant_slide(prs, storyboard, int(slide_data["slide_no"])))

    save_presentation(prs, output_ppt)

    return {
        "input_ppt": str(input_ppt),
        "storyboard": str(storyboard_path),
        "output_ppt": str(output_ppt),
        "removed_scaffold_labels": removed_labels,
        "chart_rendering": chart_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Post-process filled PPT with object-level visual cleanup and chart rendering."
    )
    parser.add_argument("--input-ppt", required=True, help="Path to cleaned PPTX input.")
    parser.add_argument("--storyboard", required=True, help="Path to industry_storyboard.json.")
    parser.add_argument("--output", required=True, help="Path to write the post-processed PPTX.")
    parser.add_argument("--log", help="Optional path to write a JSON log.")
    parser.add_argument(
        "--fail-on-unrendered",
        action="store_true",
        help="Exit non-zero if any slide with chart_data could not be rendered.",
    )
    args = parser.parse_args()

    result = postprocess(Path(args.input_ppt), Path(args.storyboard), Path(args.output))
    if args.log:
        save_json(result, Path(args.log))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.fail_on_unrendered:
        failed = [item for item in result["chart_rendering"] if not item.get("rendered")]
        if failed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
