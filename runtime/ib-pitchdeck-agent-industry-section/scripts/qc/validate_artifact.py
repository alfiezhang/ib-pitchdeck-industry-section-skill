#!/usr/bin/env python3
"""Internal pipeline helper for structure-only artifact checks.

This script deliberately checks only structure/helper conditions: files exist, JSON is
parseable, IDs and cross-references are coherent, and renderer/PPT inputs can be
used by deterministic tooling. Content quality, page density, source judgment,
and transaction relevance are LLM responsibilities.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any


sys.dont_write_bytecode = True
SCRIPT_DIR = Path(__file__).resolve().parent
RUNTIME_ROOT = next(
    parent for parent in Path(__file__).resolve().parents
    if (parent / "configs").is_dir() and (parent / "scripts").is_dir()
)
for path in [
    RUNTIME_ROOT / "scripts",
    RUNTIME_ROOT / "scripts" / "_lib",
    RUNTIME_ROOT / "scripts" / "template",
    RUNTIME_ROOT / "scripts" / "knowledge-repository",
]:
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from deck_blueprint_utils import (
    FIXED_PAGE_ROLES,
    active_body_fields,
    as_list,
    banker_page_id_for_slide,
    normalize_allowed_deck_usage,
    strict_layout_body_fields,
    template_variants_by_slide,
    unique,
)
from runtime_utils import load_json_file
from renderer_compile_utils import _body_copy_from_blocks, build_token_source, infer_selected_page_type, split_table_cells
from research_evidence_db import validate_db as validate_research_db
from template_analyzer import display_units, estimate_lines, layout_rules_for


EV_RE = re.compile(r"^EV-\d{3}$")
MET_RE = re.compile(r"^MET-\d{3}$")
BP_RE = re.compile(r"^BP-\d{3}$")
SRC_RE = re.compile(r"^SRC-\d{3}$")
BAD_PPT_GLYPHS = {"�", "□", "▯", "\ufffd"}
CLIENT_VISIBLE_EDITORIAL_HINT_TERMS = {
    "working market": "market-boundary slot label",
    "parent market": "market-boundary slot label",
    "broader market": "market-boundary slot label",
    "scope card": "market-boundary workpaper label",
    "boundary card": "market-boundary workpaper label",
    "diligence": "post-mandate workstream language",
    "due diligence": "post-mandate workstream language",
    "not_client_ready": "delivery-status label",
    "client-ready": "delivery-status label",
    "evidence-limited": "delivery-status label",
    "targeted research": "research workflow label",
    "research request": "research workflow label",
    "工作市场": "market-boundary slot label",
    "父市场": "market-boundary slot label",
    "边界卡": "market-boundary workpaper label",
    "后续验证点": "research workflow label",
    "后续验证": "research workflow label",
    "客户关注点": "question-bucket label",
    "尽调": "post-mandate workstream language",
    "尽职调查": "post-mandate workstream language",
}
VISIBLE_TEXT_KEYS = {
    "headline",
    "title",
    "slide_title",
    "page_title",
    "main_message",
    "page_argument",
    "page_thesis",
    "banker_judgment",
    "page_answer",
    "copy",
    "point",
    "text",
    "label",
    "display_text",
    "value_label",
    "claim",
    "source_note",
    "project_relevance_note",
    "caveat",
    "caveats",
    "source_limitations",
}
VISIBLE_CONTAINER_KEYS = {
    "body_blocks",
    "body_copy",
    "chart_data",
    "compare_table_data",
    "visible_metric_claims",
    "visual_design",
    "visual_plan",
    "source_note",
    "project_relevance_note",
    "caveats",
    "source_limitations",
}
NON_VISIBLE_TEXT_KEY_FRAGMENTS = {
    "metric",
    "evidence",
    "source_banker_page",
    "audit",
    "readiness",
    "deck_use",
    "allowed_deck_usage",
    "selected_page_type",
    "fixed_page_role",
}


ARTIFACT_PATHS = {
    "material_manifest": "artifacts/material_manifest.json",
    "material_extracts": "artifacts/material_extracts.json",
    "input_card": "input_card.json",
    "industry_scope_pack": "artifacts/industry_scope_pack.json",
    "industry_boundary_qc": "artifacts/industry_boundary_qc.json",
    "formal_search_plan": "artifacts/formal_search_plan.json",
    "executable_search_batch": "artifacts/executable_search_batch.json",
    "research_graph_state": "artifacts/research_graph_state.json",
    "formal_research_execution": "artifacts/formal_research_execution_report.json",
    "source_archive": "artifacts/source_archive/source_archive_index.json",
    "research_evidence_db": "artifacts/research_evidence_db.json",
    "research_pack": "industry_research_pack.md",
    "research_request_queue": "artifacts/research_request_queue.json",
    "banker_page_pack": "banker_page_pack.json",
    "template_registry": "template_registry.json",
    "deck_blueprint": "deck_blueprint.json",
    "page_evidence_contract": "page_evidence_contract.json",
    "renderer_spec": "renderer_spec.json",
    "replacement_dict": "replacement_dict.json",
    "filled_ppt": "filled_ppt_validation.json",
    "pre_ppt": "artifacts/pre_ppt_readiness.json",
    "final_delivery": "artifacts/final_delivery_validation.json",
}


VALIDATION_OUTPUTS = {
    "material_manifest": "artifacts/material_manifest_validation.json",
    "material_extracts": "artifacts/material_extracts_validation.json",
    "input_card": "artifacts/input_card_validation.json",
    "industry_scope_pack": "artifacts/industry_scope_pack_validation.json",
    "industry_boundary_qc": "artifacts/industry_boundary_qc_validation.json",
    "formal_search_plan": "artifacts/formal_search_plan_validation.json",
    "executable_search_batch": "artifacts/executable_search_batch_validation.json",
    "research_graph_state": "artifacts/research_graph_state_validation.json",
    "formal_research_execution": "artifacts/formal_research_execution_validation.json",
    "source_archive": "artifacts/source_archive_validation.json",
    "research_evidence_db": "artifacts/research_evidence_db_validation.json",
    "research_pack": "artifacts/research_pack_validation.json",
    "research_request_queue": "artifacts/research_request_queue_validation.json",
    "banker_page_pack": "artifacts/banker_page_pack_validation.json",
    "template_registry": "artifacts/template_registry_validation.json",
    "deck_blueprint": "artifacts/deck_blueprint_validation.json",
    "page_evidence_contract": "artifacts/page_evidence_contract_validation.json",
    "renderer_spec": "artifacts/renderer_spec_validation.json",
    "replacement_dict": "artifacts/replacement_dict_validation.json",
    "filled_ppt": "filled_ppt_validation.json",
    "pre_ppt": "artifacts/pre_ppt_readiness.json",
    "final_delivery": "artifacts/final_delivery_validation.json",
}


def helper_check_guidance(artifact: str, errors: list[str], warnings: list[str]) -> dict[str, str]:
    if errors:
        status = "needs_owner_repair"
        next_action = (
            f"Repair `{artifact}` or its owning upstream artifact. Treat errors as helper-check signals; "
            "do not invent evidence, hidden permissions, or filler fields merely to clear the review."
        )
    elif warnings:
        status = "checked_with_llm_prompts"
        next_action = (
            f"Use the prompts for `{artifact}` as editorial or helper-check signals, then rely on LLM judgment "
            "for source quality, page density, and final delivery quality."
        )
    else:
        status = "structure_checked"
        next_action = (
            f"`{artifact}` has no helper-check errors. This does not certify content quality, "
            "evidence strength, page density, or final delivery quality."
        )
    return {
        "status": status,
        "scope": "structure, file presence, IDs, cross-references, and deterministic render inputs only",
        "next_action": next_action,
    }


def text(value: Any) -> str:
    return str(value or "").strip()


def _json(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"missing required file: {path}")
        return {}
    try:
        payload = load_json_file(path)
    except Exception as exc:
        errors.append(f"cannot read JSON {path}: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{path}: top-level JSON must be an object")
        return {}
    return payload


def _ids(payload: dict[str, Any], ledger_name: str, id_keys: tuple[str, ...]) -> set[str]:
    rows = payload.get(ledger_name)
    if not isinstance(rows, list):
        return set()
    result: set[str] = set()
    for row in rows:
        if isinstance(row, dict):
            for key in id_keys:
                value = text(row.get(key))
                if value:
                    result.add(value)
                    break
    return result


def _scan_ids(value: Any, key_names: set[str]) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in key_names:
                if isinstance(item, list):
                    found.extend(text(part) for part in item if text(part))
                elif text(item):
                    found.append(text(item))
            else:
                found.extend(_scan_ids(item, key_names))
    elif isinstance(value, list):
        for item in value:
            found.extend(_scan_ids(item, key_names))
    return unique(found)


def _ppt_slide_texts(pptx_path: Path) -> list[str]:
    with zipfile.ZipFile(pptx_path) as archive:
        slide_names = sorted(
            (name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
            key=lambda name: int(re.search(r"slide(\d+)\.xml", name).group(1)),  # type: ignore[union-attr]
        )
        texts: list[str] = []
        for name in slide_names:
            xml = archive.read(name).decode("utf-8", errors="replace")
            chunks = re.findall(r"<a:t[^>]*>(.*?)</a:t>", xml, flags=re.DOTALL)
            texts.append(" ".join(html.unescape(re.sub(r"<[^>]+>", "", chunk)) for chunk in chunks))
        return texts


def _slide_index(payload: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {
        int(slide.get("slide_no")): slide
        for slide in as_list(payload.get("slides"))
        if isinstance(slide, dict) and isinstance(slide.get("slide_no"), int)
    }


def _load_config_json(relative_path: str) -> dict[str, Any]:
    try:
        payload = load_json_file(RUNTIME_ROOT / relative_path)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _int_value(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return 0


def _visual_payload(slide: dict[str, Any], key: str) -> dict[str, Any]:
    if isinstance(slide.get(key), dict):
        return slide[key]
    visual_design = slide.get("visual_design") if isinstance(slide.get("visual_design"), dict) else {}
    if isinstance(visual_design.get(key), dict):
        return visual_design[key]
    visual_plan = slide.get("visual_plan") if isinstance(slide.get("visual_plan"), dict) else {}
    if isinstance(visual_plan.get(key), dict):
        return visual_plan[key]
    return {}


def _body_field_limits(layout_budget: dict[str, Any], slide_no: int, page_type: str) -> dict[str, float]:
    rules = layout_rules_for(slide_no, page_type, layout_budget)
    limits = rules.get("body_fields_max_units") if isinstance(rules.get("body_fields_max_units"), dict) else {}
    result: dict[str, float] = {}
    for key, value in limits.items():
        try:
            result[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return result


def _default_body_limit(layout_budget: dict[str, Any]) -> float:
    global_body = layout_budget.get("global", {}).get("body_copy", {})
    try:
        return float(global_body.get("max_bullet_units_default", 88))
    except (TypeError, ValueError):
        return 88.0


def _text_fit_rule(text_fit_rules: dict[str, Any], slide_no: int, page_type: str, field: str) -> dict[str, Any]:
    aliases = text_fit_rules.get("renderer_field_aliases") if isinstance(text_fit_rules.get("renderer_field_aliases"), dict) else {}
    fields = text_fit_rules.get("fields") if isinstance(text_fit_rules.get("fields"), dict) else {}
    alias = str(aliases.get(field, field))
    rule = fields.get(f"{slide_no}:{page_type}:{alias}")
    return rule if isinstance(rule, dict) else {}


def _strict_layout_blocks_line_overflow(rule: dict[str, Any]) -> bool:
    if "strict_layout_pause_if_exceeds_max_lines" in rule:
        return rule.get("strict_layout_pause_if_exceeds_max_lines") is not False
    if "strict_layout_block_if_exceeds_max_lines" in rule:
        return rule.get("strict_layout_block_if_exceeds_max_lines") is not False
    return rule.get("block_if_exceeds_max_lines") is not False


def _compare_table_data_from_slide(slide: dict[str, Any]) -> dict[str, Any]:
    return _visual_payload(slide, "compare_table_data")


def _chart_data_from_slide(slide: dict[str, Any]) -> dict[str, Any]:
    return _visual_payload(slide, "chart_data")


def _body_blocks_have_visible_copy(slide: dict[str, Any]) -> bool:
    for block in as_list(slide.get("body_blocks")):
        if isinstance(block, dict) and text(block.get("copy") or block.get("point") or block.get("text")):
            return True
    return False


def _body_copy_has_visible_copy(slide: dict[str, Any]) -> bool:
    body_copy = slide.get("body_copy")
    if not isinstance(body_copy, dict):
        return False
    return any(text(value) for value in body_copy.values())


def _chart_data_has_visible_payload(data: dict[str, Any]) -> bool:
    series = data.get("series")
    categories = data.get("categories")
    source_rows = data.get("source_rows")
    if isinstance(series, list) and series and isinstance(categories, list) and categories:
        return True
    if isinstance(source_rows, list) and source_rows:
        return True
    return False


def _table_data_has_visible_payload(data: dict[str, Any]) -> bool:
    headers = data.get("headers") or data.get("columns")
    has_headers = isinstance(headers, list) and any(text(item) for item in headers)
    if not has_headers:
        has_headers = bool(split_table_cells(text(data.get("table_header"))))
    rows = data.get("rows")
    has_rows = isinstance(rows, list) and bool(rows)
    if not has_rows:
        has_rows = any(text(data.get(f"table_row_{idx}")) for idx in range(1, 7))
    return has_headers and has_rows


def _visual_payload_has_visible_content(value: Any) -> bool:
    if isinstance(value, str):
        return bool(text(value))
    if isinstance(value, (int, float, bool)):
        return True
    if isinstance(value, list):
        return any(_visual_payload_has_visible_content(item) for item in value)
    if isinstance(value, dict):
        return any(_visual_payload_has_visible_content(item) for item in value.values())
    return False


def _visual_design_has_visible_payload(slide: dict[str, Any]) -> bool:
    visual_design = slide.get("visual_design") if isinstance(slide.get("visual_design"), dict) else {}
    visual_plan = slide.get("visual_plan") if isinstance(slide.get("visual_plan"), dict) else {}
    for payload in (visual_design, visual_plan):
        for key in ("cards", "items", "stages", "rows", "points", "modules", "nodes"):
            value = payload.get(key)
            if isinstance(value, list) and value:
                return True
        if _visual_payload_has_visible_content(payload):
            return True
    return False


def _visible_metric_claims_have_payload(slide: dict[str, Any]) -> bool:
    for claim in as_list(slide.get("visible_metric_claims")):
        if not isinstance(claim, dict):
            continue
        if any(
            text(claim.get(field))
            for field in ("display_text", "claim", "text", "label", "value_label", "metric_id")
        ):
            return True
        if any(text(item) for item in as_list(claim.get("metric_ids"))):
            return True
    return False


def _key_data_audit_has_payload(slide: dict[str, Any]) -> bool:
    for row in as_list(slide.get("key_data_audit")):
        if not isinstance(row, dict):
            continue
        if any(
            text(row.get(field))
            for field in (
                "metric_id",
                "indicator",
                "metric",
                "value",
                "display_value",
                "source",
                "source_note",
            )
        ):
            return True
    return False


def _has_substantive_page_content(slide: dict[str, Any]) -> bool:
    return (
        _body_blocks_have_visible_copy(slide)
        or _body_copy_has_visible_copy(slide)
        or _chart_data_has_visible_payload(_chart_data_from_slide(slide))
        or _table_data_has_visible_payload(_compare_table_data_from_slide(slide))
        or _visual_design_has_visible_payload(slide)
        or _visible_metric_claims_have_payload(slide)
        or _key_data_audit_has_payload(slide)
    )


def _slide_page_argument(slide: dict[str, Any]) -> str:
    return text(
        slide.get("page_argument")
        or slide.get("page_thesis")
        or slide.get("banker_judgment")
        or slide.get("page_answer")
    )


def _slide_headline(slide: dict[str, Any]) -> str:
    return text(
        slide.get("headline")
        or slide.get("title")
        or slide.get("slide_title")
        or slide.get("page_title")
    )


def _field_path(path: str, key: str | int) -> str:
    if isinstance(key, int):
        return f"{path}[{key}]"
    return f"{path}.{key}" if path else key


def _looks_non_visible_key(key: str) -> bool:
    lowered = key.lower()
    if lowered == "id" or lowered.endswith("_id") or lowered.endswith("_ids"):
        return True
    return any(fragment in lowered for fragment in NON_VISIBLE_TEXT_KEY_FRAGMENTS)


def _iter_visible_strings(value: Any, path: str = "") -> list[tuple[str, str]]:
    if isinstance(value, str):
        return [(path, value)] if text(value) else []
    if isinstance(value, list):
        result: list[tuple[str, str]] = []
        for idx, item in enumerate(value, start=1):
            result.extend(_iter_visible_strings(item, _field_path(path, idx)))
        return result
    if not isinstance(value, dict):
        return []
    result: list[tuple[str, str]] = []
    for key, item in value.items():
        key_text = str(key)
        child_path = _field_path(path, key_text)
        if key_text in VISIBLE_TEXT_KEYS:
            result.extend(_iter_visible_strings(item, child_path))
        elif key_text in VISIBLE_CONTAINER_KEYS or not _looks_non_visible_key(key_text):
            result.extend(_iter_visible_strings(item, child_path))
    return result


def _client_visible_editorial_hits(slide: dict[str, Any]) -> list[tuple[str, str]]:
    scoped: dict[str, Any] = {}
    for key in (
        "headline",
        "title",
        "slide_title",
        "page_title",
        "main_message",
        "page_argument",
        "page_thesis",
        "banker_judgment",
        "page_answer",
        "body_blocks",
        "body_copy",
        "chart_data",
        "compare_table_data",
        "visible_metric_claims",
        "visual_design",
        "visual_plan",
        "source_note",
        "project_relevance_note",
        "caveats",
        "source_limitations",
    ):
        if key in slide:
            scoped[key] = slide.get(key)
    hits: list[tuple[str, str]] = []
    for path, value in _iter_visible_strings(scoped):
        lowered = value.lower()
        categories: set[str] = set()
        for term, category in CLIENT_VISIBLE_EDITORIAL_HINT_TERMS.items():
            if term.lower() in lowered:
                categories.add(category)
        for category in sorted(categories):
            hits.append((path, category))
    return hits


def _template_contract_mode(run_dir: Path, payload: dict[str, Any] | None = None) -> str:
    sources: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        sources.append(payload)
    for path in (
        run_dir / "artifacts/rendering_policy.json",
        run_dir / "artifacts/template_selection.json",
    ):
        if path.exists():
            try:
                item = load_json_file(path)
            except Exception:
                item = {}
            if isinstance(item, dict):
                sources.append(item)
    for source in sources:
        nested = source.get("rendering_policy")
        if isinstance(nested, dict):
            mode = text(nested.get("template_contract_mode"))
            if mode:
                return mode if mode in {"style_guided", "strict_layout"} else "style_guided"
        mode = text(source.get("template_contract_mode"))
        if mode:
            return mode if mode in {"style_guided", "strict_layout"} else "style_guided"
        rendering = source.get("rendering")
        if isinstance(rendering, dict):
            mode = text(rendering.get("template_contract_mode"))
            if mode:
                return mode if mode in {"style_guided", "strict_layout"} else "style_guided"
    return "style_guided"


def _strict_layout(run_dir: Path, payload: dict[str, Any] | None = None) -> bool:
    return _template_contract_mode(run_dir, payload) == "strict_layout"


def _validate_compare_table_shape(
    slide_no: int,
    data: dict[str, Any],
    errors: list[str],
    warnings: list[str],
    *,
    strict_layout: bool = False,
) -> None:
    def table_shape_issue(message: str) -> None:
        if strict_layout:
            errors.append(message)
        else:
            warnings.append(message + "; style-guided render treats this table payload as advisory")

    headers = data.get("headers")
    columns = data.get("columns")
    header_values: list[str] = []
    if not isinstance(headers, list) or not [text(item) for item in headers if text(item)]:
        if isinstance(columns, list) and [text(item) for item in columns if text(item)]:
            header_values = [text(item) for item in columns if text(item)]
            if strict_layout:
                warnings.append(
                    f"slide {slide_no}: compare_table_data uses columns; structured-render helper accepts it and will normalize to headers"
                )
        elif split_table_cells(text(data.get("table_header"))):
            header_values = split_table_cells(text(data.get("table_header")))
            if strict_layout:
                warnings.append(
                    f"slide {slide_no}: compare_table_data uses table_header; structured-render helper accepts it and will normalize to headers"
                )
        else:
            table_shape_issue(
                "slide {slide_no}: compare_table_data requires non-empty headers list".format(slide_no=slide_no)
            )
    else:
        header_values = [text(item) for item in headers if text(item)]
    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        row_texts = [text(data.get(f"table_row_{idx}")) for idx in range(1, 7) if text(data.get(f"table_row_{idx}"))]
        if row_texts:
            rows = row_texts
            if strict_layout:
                warnings.append(
                    f"slide {slide_no}: compare_table_data uses table_row_* fields; structured-render helper accepts them and will normalize to rows"
                )
        else:
            table_shape_issue(f"slide {slide_no}: compare_table_data requires non-empty rows list")
            return
    valid_rows = 0
    header_count = len(header_values)
    for idx, row in enumerate(rows, start=1):
        if isinstance(row, dict):
            cells = row.get("cells")
            has_label = bool(text(row.get("label") or row.get("name")))
            scalar_cells = [
                value
                for key, value in row.items()
                if key not in {"label", "name", "cells", "metric_ids", "evidence_ids", "source_banker_page_ids"}
                and not isinstance(value, (dict, list))
                and text(value)
            ]
            if not has_label and not cells and not scalar_cells:
                table_shape_issue(f"slide {slide_no}: compare_table_data row {idx} needs label plus cells")
                continue
            cell_values: list[str] = []
            if cells is not None and not isinstance(cells, list):
                if strict_layout:
                    errors.append(f"slide {slide_no}: compare_table_data row {idx}.cells must be a list")
                    continue
                cell_values = split_table_cells(text(cells))
                warnings.append(
                    f"slide {slide_no}: compare_table_data row {idx}.cells is scalar; "
                    "style-guided render will normalize it into cells"
                )
            elif isinstance(cells, list):
                cell_values = [text(item) for item in cells if text(item)]
            if cell_values and header_count:
                expected_cells = max(header_count - 1, 0) if has_label else header_count
                if len(cell_values) != expected_cells:
                    message = (
                        f"slide {slide_no}: compare_table_data row {idx} has label plus {len(cell_values)} cells, "
                        f"but {header_count} headers require {expected_cells} cells after label"
                    )
                    if strict_layout:
                        errors.append(message)
                        continue
                    warnings.append(message + "; style-guided render will merge extra cells or pad missing cells")
            if cells is None and scalar_cells:
                expected_cells = max(header_count - 1, 0) if has_label else header_count
                if header_count and len(scalar_cells) != expected_cells:
                    message = (
                        f"slide {slide_no}: compare_table_data row {idx} has {len(scalar_cells)} scalar columns, "
                        f"but {header_count} headers require {expected_cells} columns after label"
                    )
                    if strict_layout:
                        errors.append(message)
                        continue
                    warnings.append(message + "; style-guided render will merge extra columns or pad missing columns")
                if strict_layout:
                    warnings.append(
                        f"slide {slide_no}: compare_table_data row {idx} uses scalar columns; structured-render helper accepts it and will normalize to {{label, cells}}"
                    )
            valid_rows += 1
        elif isinstance(row, list) and row:
            if header_count and len(row) != header_count:
                message = (
                    f"slide {slide_no}: compare_table_data row {idx} has {len(row)} cells, "
                    f"but {header_count} headers require exactly {header_count} cells"
                )
                if strict_layout:
                    errors.append(message)
                    continue
                warnings.append(message + "; style-guided render will merge extra cells or pad missing cells")
            if strict_layout:
                warnings.append(
                    f"slide {slide_no}: compare_table_data row {idx} is a list; structured-render helper accepts it and will normalize to {{label, cells}}"
                )
            valid_rows += 1
        elif isinstance(row, str) and row.strip():
            if strict_layout:
                warnings.append(
                    f"slide {slide_no}: compare_table_data row {idx} is a string; structured-render helper accepts it and will normalize to {{label, cells}}"
                )
            valid_rows += 1
        else:
            table_shape_issue(f"slide {slide_no}: compare_table_data row {idx} must be an object with label/cells")
    if not valid_rows:
        table_shape_issue(f"slide {slide_no}: compare_table_data has no usable rows")


def banker_page_pack_template_diagnostics(run_dir: Path, path: Path | None = None) -> dict[str, Any]:
    target = path or run_dir / ARTIFACT_PATHS["banker_page_pack"]
    pack: dict[str, Any] = {}
    try:
        pack = load_json_file(target)
    except Exception:
        pack = {}
    if not isinstance(pack, dict):
        pack = {}
    template = {}
    template_path = run_dir / "template_registry.json"
    if template_path.exists():
        try:
            template = load_json_file(template_path)
        except Exception:
            template = {}
    template = template if isinstance(template, dict) else {}
    variants = template_variants_by_slide(template) if template else {}
    layout_budget = _load_config_json("configs/layout_budget.json")
    text_fit_rules = _load_config_json("configs/text_fit_rules.json")
    slides = pack.get("slides") if isinstance(pack.get("slides"), list) else []
    diagnostics: list[dict[str, Any]] = []
    strict_layout = _strict_layout(run_dir, pack)
    for raw_slide in slides:
        if not isinstance(raw_slide, dict):
            continue
        slide_no = _int_value(raw_slide.get("slide_no"))
        page_type = text(raw_slide.get("selected_page_type"))
        allowed_page_types = sorted(variants.get(slide_no, {}).keys())
        strict_fields = strict_layout_body_fields(template, slide_no, page_type) if strict_layout and template and page_type else []
        active_fields = active_body_fields(strict_fields, page_type, raw_slide) if strict_fields else []
        field_limits = _body_field_limits(layout_budget, slide_no, page_type)
        text_rules: dict[str, Any] = {}
        for field in ("headline", "main_message"):
            rule = _text_fit_rule(text_fit_rules, slide_no, page_type, field)
            if rule:
                text_rules[field] = {
                    "max_line_units": rule.get("max_line_units"),
                    "target_lines": rule.get("target_lines"),
                    "max_lines": rule.get("max_lines"),
                    "placeholder": rule.get("placeholder"),
                }
        diagnostics.append(
            {
                "slide_no": slide_no,
                "expected_fixed_page_role": FIXED_PAGE_ROLES.get(slide_no, ""),
                "selected_page_type": page_type,
                "allowed_page_types": allowed_page_types,
                "template_fit_mode": "strict_placeholder_layout" if strict_layout else "style_guided",
                "style_guided_template_note": (
                    ""
                    if strict_layout
                    else "Template sample boxes, columns, and page roles are style cues only; write the page composition that best carries the banker argument."
                ),
                "strict_layout_placeholders": strict_fields if strict_layout else [],
                "strict_layout_active_placeholders": active_fields if strict_layout else [],
                "strict_layout_inactive_table_placeholders": (
                    [field for field in strict_fields if field not in active_fields]
                    if strict_layout and page_type == "compare_table_page" and _compare_table_data_from_slide(raw_slide)
                    else []
                ),
                "strict_layout_capacity_hints": (
                    {
                        "body_placeholder_unit_limits": field_limits,
                        "default_body_placeholder_unit_limit": _default_body_limit(layout_budget),
                        "headline_main_message_line_rules": text_rules,
                    }
                    if strict_layout
                    else {}
                ),
                "compare_table_data_guidance": (
                    (
                        "Strict placeholder layout takes table content from compare_table_data; use active side-panel placeholders only for side-panel copy."
                        if strict_layout
                        else "Use the table shape that best explains the page. The structured-render helper accepts headers/columns and row objects/lists/strings, then normalizes them."
                    )
                    if page_type == "compare_table_page"
                    else ""
                ),
            }
        )
    return {
        "schema_version": "banker_page_pack_template_diagnostics_v1",
        "banker_page_pack": str(target),
        "template_contract_mode": _template_contract_mode(run_dir, pack),
        "template_registry": str(template_path) if template_path.exists() else "",
        "has_template_registry": bool(template),
        "slides": diagnostics,
    }


def _assert_artifact_report(path: Path, errors: list[str]) -> None:
    payload = _json(path, errors)
    if payload and payload.get("is_valid") is False:
        errors.append(f"{path.name} is_valid=false")


def _reject_shape_hint_copy(payload: dict[str, Any], artifact: str, errors: list[str], instruction: str) -> None:
    if payload.get("_shape_hint_only") is True:
        errors.append(f"{artifact} still has _shape_hint_only=true; {instruction}")
    if payload.get("_template_only") is True:
        errors.append(f"{artifact} still has _template_only=true; replace the old copied template with authored content. {instruction}")


def validate_material_like(artifact: str, path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    _reject_shape_hint_copy(payload, artifact, errors, "LLM must author the actual artifact from the user materials")
    if artifact == "input_card" and not (
        payload.get("raw_brief")
        or payload.get("explicit_user_facts")
        or payload.get("brief_text")
        or payload.get("deal_context")
        or payload.get("target_business_summary")
        or payload.get("user_provided_target_facts")
    ):
        warnings.append("input_card has no obvious raw brief or explicit facts")


def _research_request_queue_policy() -> dict[str, Any]:
    try:
        payload = load_json_file(RUNTIME_ROOT / "configs" / "research_planning_policy.json")
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    policy = payload.get("research_request_queue")
    return policy if isinstance(policy, dict) else {}


def _request_active_value(request: dict[str, Any]) -> bool | None:
    value = request.get("active")
    return value if isinstance(value, bool) else None


def _request_counts_as_active(request: dict[str, Any]) -> bool:
    active_value = _request_active_value(request)
    if active_value is not None:
        return active_value
    return True


def validate_research_request_queue(path: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    if payload.get("schema_version") != "research_request_queue":
        errors.append("research_request_queue must use schema_version research_request_queue")
    _reject_shape_hint_copy(
        payload,
        "research_request_queue",
        errors,
        "Reasoning LLM must author targeted requests or leave the queue absent",
    )
    requests = payload.get("requests")
    if not isinstance(requests, list):
        errors.append("research_request_queue.requests must be a list")
        return
    if not requests:
        warnings.append("research_request_queue has no active requests")

    policy = _research_request_queue_policy()
    loop_policy = policy.get("targeted_loop_policy") if isinstance(policy.get("targeted_loop_policy"), dict) else {}
    max_cycles = loop_policy.get("max_cycles_before_user_or_qc_decision")
    loop_control = payload.get("loop_control")
    loop_budget = loop_control if isinstance(loop_control, dict) else {}
    active_requests = [
        request
        for request in requests
        if isinstance(request, dict)
        and _request_counts_as_active(request)
    ]
    max_active_requests = loop_policy.get("max_active_requests_per_cycle")
    if isinstance(max_active_requests, int) and max_active_requests >= 0:
        if len(active_requests) > max_active_requests:
            errors.append(
                f"research_request_queue has {len(active_requests)} active request(s), "
                f"above targeted-loop cap {max_active_requests}; keep only research that can change deck inclusion, key data audit, or exhibit readiness"
            )
    if not isinstance(loop_control, dict):
        default_max_note = (
            f" and max_cycles={max_cycles}" if isinstance(max_cycles, int) and max_cycles > 0 else ""
        )
        warnings.append(
            "research_request_queue.loop_control omitted; helper assumes current_cycle=1"
            f"{default_max_note} from policy. Add loop_control after a cycle outcome or when overriding the default cap."
        )
    else:
        current_cycle = loop_control.get("current_cycle")
        declared_max = loop_control.get("max_cycles")
        if not isinstance(current_cycle, int) or current_cycle < 1:
            warnings.append(
                "research_request_queue.loop_control.current_cycle is missing or invalid; helper assumes current_cycle=1 for advisory routing"
            )
        if declared_max is None:
            inherited_note = (
                f"max_cycles={max_cycles}" if isinstance(max_cycles, int) and max_cycles > 0 else "the policy max cycle cap"
            )
            warnings.append(
                f"research_request_queue.loop_control.max_cycles omitted; helper inherits {inherited_note}"
            )
        if declared_max is not None and (not isinstance(declared_max, int) or declared_max < 1):
            errors.append("research_request_queue.loop_control.max_cycles, when present, must be a positive integer")
        effective_max = declared_max if isinstance(declared_max, int) and declared_max > 0 else max_cycles
        if isinstance(max_cycles, int) and max_cycles > 0 and isinstance(declared_max, int) and declared_max > max_cycles:
            errors.append(
                f"research_request_queue.loop_control.max_cycles exceeds policy cap {max_cycles}"
            )
        if isinstance(current_cycle, int) and isinstance(effective_max, int) and effective_max > 0:
            if current_cycle > effective_max:
                errors.append(
                    f"research_request_queue.loop_control.current_cycle={current_cycle} exceeds max_cycles={effective_max}; "
                    "route to QC/user decision instead of starting another research loop"
                )
            elif current_cycle == effective_max:
                latest_outcome = text(loop_control.get("latest_cycle_outcome"))
                if latest_outcome and active_requests:
                    errors.append(
                        "research_request_queue final targeted cycle already has latest_cycle_outcome, "
                        "but active requests remain. Close resolved/exhausted requests and route remaining gaps "
                        "to QC/user decision instead of rerunning the same search loop."
                    )
                elif not latest_outcome and not active_requests:
                    errors.append(
                        "research_request_queue final targeted cycle has no active requests but no latest_cycle_outcome; "
                        "record what changed or why sources were unavailable before routing to QC/user decision"
                    )
                else:
                    warnings.append(
                        "research_request_queue is on its final targeted cycle; unresolved gaps after this cycle must route to QC/user decision"
                    )
            elif not active_requests and not text(loop_control.get("latest_cycle_outcome")):
                warnings.append(
                    "research_request_queue has no active requests and no latest_cycle_outcome; "
                    "add one narrow request within the remaining loop budget or record why another search will not change the page decision"
                )
    seen: set[str] = set()
    for idx, request in enumerate(requests, start=1):
        if not isinstance(request, dict):
            errors.append(f"research_request_queue.requests[{idx}] must be an object")
            continue
        request_id = text(request.get("request_id") or request.get("research_request_id"))
        request_label = request_id or f"request {idx}"
        if request_id and not re.fullmatch(r"RQ-\d{3}", request_id):
            warnings.append(f"research_request_queue.requests[{idx}].request_id does not look like RQ-001; array order can still be used")
        elif request_id in seen:
            errors.append(f"duplicate research request id: {request_id}")
        if request_id:
            seen.add(request_id)
        active_value = _request_active_value(request)
        if active_value is None:
            warnings.append(
                f"{request_label} missing active boolean; helper treats it as active for this cycle. "
                "Set active=false after the request is closed, exhausted, or deferred."
            )
        if not (text(request.get("research_question")) or text(request.get("question"))):
            errors.append(f"{request_label} missing research_question")
        if active_value is True:
            if not _has_request_decision_anchor(request):
                warnings.append(
                    f"LLM research prompt: {request_label} does not name the page, metric, headline, key data, "
                    "or exhibit decision it could change; LLM/QC should narrow active requests before execution "
                    "instead of running open-ended exploration"
                )
            if not _has_request_close_condition(request):
                warnings.append(
                    f"LLM research prompt: {request_label} does not name a stop condition or close rule; "
                    "LLM/QC should add when to close, narrow, or escalate this request so the next cycle does not rerun it unchanged"
                )
            max_searches = loop_policy.get("max_actual_searches_per_request")
            if isinstance(max_searches, int) and max_searches >= 0:
                explicit_budgets = _explicit_search_budget_values(request)
                inherited_search_budgets = _explicit_search_budget_values(loop_budget)
                oversized = [value for value in explicit_budgets + inherited_search_budgets if value > max_searches]
                if oversized:
                    errors.append(
                        f"{request_label} search_budget exceeds policy cap {max_searches} actual search(es) per request"
                    )
            max_sources = loop_policy.get("max_opened_sources_per_request")
            if isinstance(max_sources, int) and max_sources >= 0:
                source_budget_values = _explicit_source_review_budget_values(request)
                inherited_source_budget_values = _explicit_source_review_budget_values(loop_budget)
                if any(value > max_sources for value in source_budget_values + inherited_source_budget_values):
                    errors.append(
                        f"{request_label} source_review_budget exceeds policy cap {max_sources} opened/reviewed source(s) per request"
                    )
            max_promoted = loop_policy.get("max_promoted_sources_per_request")
            if isinstance(max_promoted, int) and max_promoted >= 0:
                promoted_budget_values = _explicit_promoted_source_budget_values(request)
                inherited_promoted_budget_values = _explicit_promoted_source_budget_values(loop_budget)
                if any(value > max_promoted for value in promoted_budget_values + inherited_promoted_budget_values):
                    errors.append(
                        f"{request_label} promoted-source budget exceeds policy cap {max_promoted} promoted source(s) per request"
                    )


def _has_request_decision_anchor(request: dict[str, Any]) -> bool:
    anchor_fields = (
        "origin_ref_id",
        "origin_page_argument_id",
        "boundary_request_id",
        "banker_page_id",
        "page_id",
        "page_ref",
        "page_refs",
        "slide_no",
        "metric_id",
        "metric_ids",
        "evidence_id",
        "evidence_ids",
        "claim_ref",
        "exhibit_ref",
        "target_decision",
        "decision_to_change",
        "decision_anchor",
        "decision",
        "page_use_decision",
        "claim_decision",
        "chart_decision",
        "table_decision",
        "exhibit_decision",
        "key_data_decision",
        "would_change",
    )
    for field in anchor_fields:
        value = request.get(field)
        if isinstance(value, list) and any(text(item) for item in value):
            return True
        if text(value):
            return True
    return False


def _has_request_close_condition(request: dict[str, Any]) -> bool:
    close_fields = (
        "stop_condition",
        "stop_rule",
        "close_rule",
        "close_when",
        "close_condition",
        "when_to_stop",
        "stop_or_close_rule",
        "do_not_rerun_when",
        "success_criteria",
        "failure_condition",
        "escalation_condition",
        "if_unresolved",
        "outcome_rule",
        "cycle_close_rule",
        "expected_resolution",
    )
    for field in close_fields:
        value = request.get(field)
        if isinstance(value, list) and any(text(item) for item in value):
            return True
        if isinstance(value, dict) and any(text(item) for item in value.values()):
            return True
        if text(value):
            return True
    return False


def _integer_values_from_fields(payload: dict[str, Any], fields: tuple[str, ...]) -> list[int]:
    return [payload[field] for field in fields if isinstance(payload.get(field), int)]


def _explicit_search_budget_values(request: dict[str, Any]) -> list[int]:
    return _integer_values_from_fields(
        request,
        (
        "max_searches",
        "max_actual_searches",
        "actual_search_budget",
        "search_budget_count",
        "search_limit",
        ),
    )


def _explicit_source_review_budget_values(request: dict[str, Any]) -> list[int]:
    return _integer_values_from_fields(
        request,
        (
        "max_opened_sources",
        "max_sources_reviewed",
        "max_reviewed_sources",
        "opened_source_limit",
        "source_review_limit",
        "source_review_budget_count",
        ),
    )


def _explicit_promoted_source_budget_values(request: dict[str, Any]) -> list[int]:
    return _integer_values_from_fields(
        request,
        (
        "max_promoted_sources",
        "max_sources_promoted",
        "promoted_source_limit",
        "promotion_limit",
        "promoted_source_budget_count",
        "promotion_budget_count",
        ),
    )


def validate_scope(path: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    if payload.get("schema_version") != "industry_scope_pack_boundary_card":
        errors.append("industry_scope_pack must use schema_version industry_scope_pack_boundary_card")
    _reject_shape_hint_copy(
        payload,
        "industry_scope_pack",
        errors,
        "Industry Scoping LLM must author the actual boundary card",
    )
    if payload.get("do_not_use_as_claims") is not True:
        warnings.append(
            "industry_scope_pack.do_not_use_as_claims is not true; LLM/QC should treat the scope pack as a boundary card only, not as page evidence or market findings"
        )
    if "boundary_validation_needed" in payload:
        errors.append("industry_scope_pack uses removed field boundary_validation_needed; use boundary_checks_if_needed")
    summary = payload.get("scope_summary") if isinstance(payload.get("scope_summary"), dict) else {}
    for field in ("working_market", "parent_market", "broader_market"):
        if not text(summary.get(field)):
            errors.append(f"scope_summary.{field} is required")


def validate_industry_boundary_qc(path: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    if payload.get("schema_version") != "industry_boundary_qc":
        errors.append("industry_boundary_qc must use schema_version industry_boundary_qc")
    _reject_shape_hint_copy(payload, "industry_boundary_qc", errors, "LLM QC must author the actual boundary review")
    decision = text(payload.get("decision"))
    if not decision:
        warnings.append(
            "industry_boundary_qc.decision is missing; LLM boundary QC should write a short natural-language review decision when this optional diagnostic artifact is used"
        )
    business_action = text(payload.get("business_action")).lower()
    if business_action and business_action not in {"research_ready", "boundary_check", "repair_scope"}:
        warnings.append(
            "industry_boundary_qc.business_action is nonstandard; helpers only honor exact research_ready, "
            "boundary_check, or repair_scope, and otherwise treat the optional boundary review as advisory"
        )
    if "validated_scope" in payload:
        errors.append("industry_boundary_qc uses removed field validated_scope; use reviewed_scope")
    if "boundary_validation_requests" in payload:
        errors.append("industry_boundary_qc uses removed field boundary_validation_requests; use rationale, scope_adjustments, or research_handoff_note")
    if business_action == "research_ready" and not text(payload.get("rationale")):
        warnings.append("industry_boundary_qc.business_action=research_ready should include a short rationale for Research handoff")
    if business_action == "research_ready":
        reviewed_scope = payload.get("reviewed_scope") if isinstance(payload.get("reviewed_scope"), dict) else {}
        if not any(text(reviewed_scope.get(field)) for field in ("working_market", "parent_market", "broader_market")):
            warnings.append("industry_boundary_qc.business_action=research_ready should restate at least the working market in reviewed_scope")


def _contains_key(value: Any, keys: set[str]) -> bool:
    if isinstance(value, dict):
        return any(key in keys or _contains_key(item, keys) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_key(item, keys) for item in value)
    return False


def _has_substantive_thread(value: Any) -> bool:
    if isinstance(value, str):
        return bool(text(value))
    if isinstance(value, dict):
        return any(_has_substantive_thread(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_substantive_thread(item) for item in value)
    return value is not None


def _executable_query_texts(row: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for field in ("query_text", "search_query"):
        if text(row.get(field)):
            values.append(text(row.get(field)))
    for item in as_list(row.get("queries") or row.get("query_set") or row.get("search_queries")):
        if isinstance(item, str) and text(item):
            values.append(text(item))
        elif isinstance(item, dict):
            for field in ("query", "query_text", "search_query", "text"):
                if text(item.get(field)):
                    values.append(text(item.get(field)))
                    break
    return unique(values)


def _query_placeholder_texts(query_texts: list[str]) -> list[str]:
    return [
        value
        for value in query_texts
        if "LLM_REWRITE_REQUIRED" in value or "needs_authoring" in value
    ]


def _query_row_active_value(row: dict[str, Any]) -> bool | None:
    value = row.get("active")
    return value if isinstance(value, bool) else None


def _query_row_has_reason(row: dict[str, Any]) -> bool:
    return any(
        text(row.get(field))
        for field in (
            "why_this_search_matters",
            "selection_note",
            "decision_note",
            "defer_reason",
            "backlog_reason",
            "why_not_run",
        )
    )


def validate_formal_plan(path: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    _reject_shape_hint_copy(
        payload,
        "formal_search_plan",
        errors,
        "Research Planning LLM must author the actual evidence-need map",
    )
    if _contains_key(payload, {"query", "query_variants", "english_query", "chinese_query"}):
        errors.append("formal_search_plan must not contain executable query fields")
    legacy_plan_fields = {"issue_search_plan", "issue_area", "subissue", "minimum_actual_searches", "coverage_required"}
    if _contains_key(payload, legacy_plan_fields):
        errors.append(
            "formal_search_plan must not contain legacy taxonomy/query-control fields "
            "(issue_search_plan, issue_area, subissue, minimum_actual_searches, coverage_required); "
            "write compact evidence-need threads instead"
        )
    thread_fields = (
        "industry_specific_research_threads",
        "core_research_threads",
        "custom_evidence_needs",
        "research_threads",
    )
    if not any(_has_substantive_thread(payload.get(field)) for field in thread_fields):
        errors.append(
            "formal_search_plan must include at least one evidence-need thread in "
            "core_research_threads, industry_specific_research_threads, custom_evidence_needs, or research_threads"
        )


def validate_search_batch(path: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    rows = payload.get("batches")
    if isinstance(rows, list):
        for idx, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                continue
            fs_id = text(row.get("search_instruction_id")) or f"row {idx}"
            if "query_status" in row:
                errors.append(
                    f"executable_search_batch {fs_id}: query_status is no longer a routing field; "
                    "use active=true for rows to execute now and active=false for deferred rows"
                )
            legacy_fields = [field for field in ("english_query", "chinese_query", "source_specific_query") if field in row]
            if legacy_fields:
                errors.append(
                    f"executable_search_batch {fs_id}: legacy query columns are not allowed "
                    f"({', '.join(legacy_fields)}); use queries[] or query_text"
                )
            query_texts = _executable_query_texts(row)
            placeholder_texts = _query_placeholder_texts(query_texts)
            active_value = _query_row_active_value(row)
            if active_value is None:
                errors.append(
                    f"executable_search_batch {fs_id}: missing active boolean; use active=true for rows to execute now "
                    "and active=false for deferred/not-material rows. Python does not infer execution intent from notes."
                )
                continue
            if active_value is False:
                if placeholder_texts:
                    warnings.append(
                        f"executable_search_batch {fs_id}: active=false row still carries placeholder query text; "
                        "delete query placeholders from deferred rows"
                    )
                if query_texts and not placeholder_texts:
                    warnings.append(
                        f"executable_search_batch {fs_id}: active=false row carries query text; "
                        "Research should ignore it unless Query Author changes active to true"
                    )
                if not _query_row_has_reason(row):
                    warnings.append(f"executable_search_batch {fs_id}: active=false row should explain why it is not run now")
                continue
            if placeholder_texts:
                errors.append(f"executable_search_batch {fs_id}: query text still contains placeholder text")
            if not query_texts:
                errors.append(
                    f"executable_search_batch {fs_id}: active=true rows need at least one concrete query "
                    "in query_text or queries[]"
                )


def validate_research_graph_state(path: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    units = payload.get("research_units")
    if units is None:
        units = payload.get("units")
    if units is not None and not isinstance(units, list):
        errors.append("research_graph_state research_units/units must be a list when present")
    if not units:
        warnings.append(
            "research_graph_state has no visible research units; Research should record selected searches or manual-source reviews here before Knowledge authoring"
        )


def validate_execution(path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    search_log = run_dir / "artifacts/search_log.md"
    if not search_log.exists():
        errors.append("formal research execution requires artifacts/search_log.md")


def validate_source_archive(path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    rows = (
        payload.get("entries")
        or payload.get("sources")
        or payload.get("source_archive")
        or payload.get("archives")
        or []
    )
    if not isinstance(rows, list):
        errors.append("source archive index must contain a source list")
        return
    for idx, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        source_id = text(row.get("source_review_id") or row.get("source_id") or row.get("id"))
        if source_id and not SRC_RE.fullmatch(source_id):
            errors.append(f"source archive row {idx}: invalid source_id {source_id}")
        status = text(row.get("research_archive_status") or row.get("archive_status"))
        archive_path = text(row.get("archive_path") or row.get("saved_path") or row.get("local_path"))
        if status in {"saved_html", "saved_text", "saved_pdf", "downloaded_pdf"} and archive_path:
            candidate = run_dir / archive_path if not Path(archive_path).is_absolute() else Path(archive_path)
            if not candidate.exists():
                errors.append(f"source archive row {idx}: archive file not found: {archive_path}")


def validate_research_evidence_db(path: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    db_result = validate_research_db(payload)
    db_errors = db_result[0] if len(db_result) > 0 else []
    db_warnings = db_result[1] if len(db_result) > 1 else []
    errors.extend(str(item) for item in db_errors)
    warnings.extend(str(item) for item in db_warnings)


def validate_research_pack(path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    if not path.exists():
        errors.append(f"missing required file: {path}")
        return
    text_body = path.read_text(encoding="utf-8", errors="replace")
    if "EV-" not in text_body and "MET-" not in text_body:
        warnings.append("research pack contains no visible EV/MET IDs")
    db_path = run_dir / "artifacts/research_evidence_db.json"
    if not db_path.exists():
        errors.append(
            "research pack is a derived export, but artifacts/research_evidence_db.json is missing; "
            "Knowledge must author or repair the evidence DB first, then regenerate the pack"
        )


def validate_banker_page_pack(path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    if payload.get("schema_version") != "banker_page_pack":
        errors.append("banker_page_pack.schema_version must be banker_page_pack")
    slides = payload.get("slides")
    if not isinstance(slides, list) or not slides:
        errors.append("banker_page_pack.slides must contain at least one LLM-authored page")
        return
    db_path = run_dir / "artifacts/research_evidence_db.json"
    db = _json(db_path, []) if db_path.exists() else {}
    ev_ids = _ids(db, "evidence_ledger", ("evidence_id", "id"))
    met_ids = _ids(db, "metric_reconciliation", ("metric_id", "id"))
    template_path = run_dir / "template_registry.json"
    template = _json(template_path, []) if template_path.exists() else {}
    strict_layout = _strict_layout(run_dir, payload)
    raw_slide_numbers = [_int_value(slide.get("slide_no")) for slide in slides if isinstance(slide, dict)]
    missing_numbers = [idx for idx, number in enumerate(raw_slide_numbers, start=1) if not number]
    if strict_layout and missing_numbers:
        errors.append(f"banker_page_pack has slide(s) missing positive slide_no at positions: {missing_numbers}")
    elif missing_numbers:
        warnings.append(
            f"banker_page_pack omits slide_no at positions {missing_numbers}; style-guided validation will use array order"
        )
    resolved_slide_numbers = [
        number if number else idx
        for idx, number in enumerate(raw_slide_numbers, start=1)
    ]
    duplicate_numbers = sorted({number for number in resolved_slide_numbers if number and resolved_slide_numbers.count(number) > 1})
    if strict_layout and duplicate_numbers:
        errors.append(f"banker_page_pack contains duplicate resolved slide_no values: {duplicate_numbers}")
    elif duplicate_numbers:
        warnings.append(
            f"banker_page_pack contains duplicate slide_no hints {duplicate_numbers}; "
            "style-guided structured render will use array order and normalize internal page IDs"
        )
    if strict_layout and any(number and number not in FIXED_PAGE_ROLES for number in resolved_slide_numbers):
        errors.append("strict_layout banker_page_pack slide_no values must align with the template registry")
    not_allowed_numbers = [
        number if number else idx
        for idx, (slide, number) in enumerate(zip(slides, resolved_slide_numbers), start=1)
        if isinstance(slide, dict)
        and normalize_allowed_deck_usage(slide.get("allowed_deck_usage") or slide.get("deck_use")) == "not_allowed"
    ]
    if not_allowed_numbers:
        message = (
            f"banker_page_pack contains page(s) marked not for deck: {not_allowed_numbers}; "
            "style-guided structured render will skip these pages, while strict_layout requires removing or repairing them before render"
        )
        (errors if strict_layout else warnings).append(message)
    template_variants = template_variants_by_slide(template) if template else {}
    if not template:
        warnings.append(
            "banker_page_pack template-specific checks were limited because template_registry.json is missing; "
            "structured render can generate the internal template registry when template-specific rendering is needed"
        )
    layout_budget = _load_config_json("configs/layout_budget.json")
    text_fit_rules = _load_config_json("configs/text_fit_rules.json")
    for idx, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            errors.append(f"slide {idx}: must be an object")
            continue
        raw_slide_no = _int_value(slide.get("slide_no"))
        slide_no = raw_slide_no if strict_layout and raw_slide_no else idx
        expected_id = f"BP-{slide_no:03d}" if slide_no else ""
        explicit_banker_page_id = text(slide.get("banker_page_id"))
        if explicit_banker_page_id and explicit_banker_page_id != expected_id:
            warnings.append(
                f"slide {slide_no}: banker_page_id {explicit_banker_page_id!r} will be normalized to {expected_id}; "
                "omit internal IDs unless they help coordination"
            )
        expected_role = FIXED_PAGE_ROLES.get(slide_no)
        fixed_page_role = text(slide.get("fixed_page_role"))
        if strict_layout and expected_role and fixed_page_role != expected_role:
            errors.append(
                f"slide {slide_no}: fixed_page_role differs from registry role '{expected_role}'. "
                "strict_layout mode requires registry alignment."
            )
        elif not strict_layout and fixed_page_role and expected_role and fixed_page_role != expected_role:
            warnings.append(
                f"slide {slide_no}: fixed_page_role '{fixed_page_role}' differs from bundled registry role "
                f"'{expected_role}'; style-guided rendering treats this as a template hint, not a content contract"
            )
        if text(slide.get("transaction_readthrough")):
            errors.append(
                f"slide {slide_no}: transaction_readthrough is a legacy internal field; "
                "write current client-facing project_relevance_note instead"
            )
        page_argument = _slide_page_argument(slide)
        headline = _slide_headline(slide)
        if not page_argument:
            warnings.append(
                f"slide {slide_no}: LLM editorial prompt: no page argument/thesis was found; "
                "drafting can continue, but LLM/QC should decide whether the visible headline, exhibit, "
                "and body copy already carry a clear client-facing industry judgment before rendering"
            )
        if not headline and not page_argument:
            warnings.append(
                f"slide {slide_no}: LLM editorial prompt: no headline/title was found; drafting can continue, "
                "but LLM/QC should provide client-facing slide language or confirm another visible element can "
                "carry the page title before rendering"
            )
        strict_fields = []
        if strict_layout:
            strict_fields.insert(0, "fixed_page_role")
            strict_fields.append("selected_page_type")
        for field in strict_fields:
            if not text(slide.get(field)):
                errors.append(f"slide {slide_no}: {field} is required")
        slide_evidence_ids = sorted(_scan_ids(slide, {"evidence_id", "evidence_ids"}))
        slide_metric_ids_for_source = sorted(_scan_ids(slide, {"metric_id", "metric_ids"}))
        if not text(slide.get("source_note")):
            if not slide_evidence_ids and not slide_metric_ids_for_source:
                warnings.append(
                    f"slide {slide_no}: LLM evidence prompt: source_note omitted and no EV/MET bindings were found; "
                    "LLM/QC should either add readable provenance/evidence bindings or mark the page as caveated, "
                    "project-context, or needing targeted research"
                )
        body_blocks = as_list(slide.get("body_blocks"))
        if not _has_substantive_page_content(slide):
            warnings.append(
                f"slide {slide_no}: LLM editorial prompt: page lacks substantive visible content; "
                "repair the page pack with body copy, a chart/table/card/matrix, or an intentional merge/drop decision "
                "instead of filling template slots automatically"
            )
        editorial_hits = _client_visible_editorial_hits(slide)
        if editorial_hits:
            hit_summaries = []
            seen_hit_summaries: set[str] = set()
            for field_path, category in editorial_hits:
                summary = f"{field_path} ({category})"
                if summary not in seen_hit_summaries:
                    seen_hit_summaries.add(summary)
                    hit_summaries.append(summary)
            warnings.append(
                f"slide {slide_no}: LLM editorial prompt: client-visible copy may contain internal workpaper language "
                f"in {', '.join(hit_summaries[:6])}. Rewrite as a market point, source caveat, or transaction relevance bridge before final render."
            )
        explicit_selected_page_type = text(slide.get("selected_page_type"))
        selected_page_type = explicit_selected_page_type
        if not selected_page_type and not strict_layout:
            selected_page_type = infer_selected_page_type(slide, slide_no, template)
        active_fields: list[str] = []
        body_copy_for_checks: dict[str, str] = {}
        if template and selected_page_type:
            allowed_page_types = sorted(template_variants.get(slide_no, {}).keys())
            if allowed_page_types and selected_page_type not in allowed_page_types:
                if strict_layout:
                    errors.append(
                        f"slide {slide_no}: selected_page_type '{selected_page_type}' is not available for "
                        f"fixed_page_role '{expected_role or '?'}'; allowed page types: {allowed_page_types}"
                    )
            strict_fields = strict_layout_body_fields(template, slide_no, selected_page_type) if strict_layout else []
            active_fields = active_body_fields(strict_fields, selected_page_type, slide) if strict_layout else []
            if strict_layout and selected_page_type == "compare_table_page" and _compare_table_data_from_slide(slide):
                inactive = [field for field in strict_fields if field not in active_fields]
                if inactive:
                    warnings.append(
                        f"slide {slide_no}: compare_table_page table fields are supplied through compare_table_data; "
                        f"inactive strict-layout placeholders when compare_table_data is present: {inactive}; "
                        f"active strict-layout placeholders: {active_fields}"
                    )
            explicit_body_copy = slide.get("body_copy") if isinstance(slide.get("body_copy"), dict) else {}
            if strict_layout and explicit_body_copy:
                body_copy_for_checks = {str(key): str(value or "").strip() for key, value in explicit_body_copy.items()}
                extra_fields = sorted(set(body_copy_for_checks) - set(active_fields))
                if extra_fields:
                    message = (
                        f"slide {slide_no}: body_copy contains strict-layout placeholders not active for {selected_page_type}: {extra_fields}. "
                        f"Active strict-layout placeholders: {active_fields or ['(none)']}"
                    )
                    (errors if strict_layout else warnings).append(message)
                missing_fields = [field for field in active_fields if not text(body_copy_for_checks.get(field))]
                if missing_fields:
                    message = (
                        f"slide {slide_no}: body_copy missing active strict-layout placeholders for {selected_page_type}: {missing_fields}. "
                        f"Active strict-layout placeholders: {active_fields or ['(none)']}"
                    )
                    (errors if strict_layout else warnings).append(message)
            elif body_blocks:
                try:
                    body_copy_for_checks = _body_copy_from_blocks(
                        slide,
                        strict_fields,
                        selected_page_type,
                        strict_layout=strict_layout,
                    )
                except Exception as exc:
                    (errors if strict_layout else warnings).append(
                        f"slide {slide_no}: body_blocks cannot map to strict-layout placeholders: {exc}"
                    )
            if strict_layout and selected_page_type == "compare_table_page" and _compare_table_data_from_slide(slide):
                for block_idx, block in enumerate(body_blocks, start=1):
                    if not isinstance(block, dict):
                        continue
                    target_or_role = text(
                        block.get("target_field")
                        or block.get("template_field")
                        or block.get("body_field")
                        or block.get("field")
                        or block.get("role")
                    )
                    if target_or_role == "table_header" or target_or_role.startswith("table_row_"):
                        message = (
                            f"slide {slide_no}: body block {block_idx} uses '{target_or_role}', but compare_table_page "
                            "takes table content from compare_table_data; use active side-panel placeholders "
                            f"{active_fields or ['right_top', 'right_mid', 'right_bottom']}"
                        )
                        (errors if strict_layout else warnings).append(message)
            field_limits = _body_field_limits(layout_budget, slide_no, selected_page_type)
            default_limit = _default_body_limit(layout_budget)
            for field_name, value in body_copy_for_checks.items():
                if field_name not in active_fields:
                    continue
                limit = field_limits.get(field_name, default_limit)
                actual = display_units(value)
                if actual > limit:
                    warnings.append(
                        f"slide {slide_no}: body_copy.{field_name} is {actual:.1f} layout units vs template guidance {limit:.1f}; "
                        "compress if the rendered page looks crowded, but this body budget is advisory"
                    )
            for text_field in ("headline", "main_message"):
                value = text(slide.get(text_field))
                rule = _text_fit_rule(text_fit_rules, slide_no, selected_page_type, text_field)
                if not value or not rule:
                    continue
                max_line_units = float(rule.get("max_line_units") or 0)
                target_lines = int(rule.get("target_lines") or 0)
                max_lines = int(rule.get("max_lines") or 0)
                estimated = estimate_lines(value, max_line_units)
                placeholder = text(rule.get("placeholder"))
                if target_lines and estimated > target_lines:
                    warnings.append(
                        f"slide {slide_no}: {text_field} estimates to {estimated} lines for {placeholder}; target is {target_lines}"
                    )
                if max_lines and estimated > max_lines:
                    if strict_layout and _strict_layout_blocks_line_overflow(rule):
                        errors.append(
                            f"slide {slide_no}: {text_field} exceeds template max lines for {placeholder}: "
                            f"estimated {estimated}, max {max_lines}; shorten before render"
                        )
                    elif not strict_layout:
                        warnings.append(
                            f"slide {slide_no}: {text_field} line-fit advisory for {placeholder}: "
                            f"estimated {estimated} lines vs template hint {max_lines}; "
                            "in style-guided mode, preserve the page argument and choose rewrite, split-page, "
                            "or layout adjustment only if the rendered page looks crowded"
                        )
        if selected_page_type == "compare_table_page":
            compare_table_data = _compare_table_data_from_slide(slide)
            if not compare_table_data:
                message = (
                    f"slide {slide_no}: compare_table_page needs a compare_table_data payload; "
                    "style-guided mode accepts headers/columns/table_header and row objects/lists/strings/table_row_* "
                    "and will normalize them. Do not put peer-table content only in body_blocks."
                )
                (errors if strict_layout else warnings).append(message)
            else:
                _validate_compare_table_shape(
                    slide_no,
                    compare_table_data,
                    errors,
                    warnings,
                    strict_layout=strict_layout,
                )
        slide_ev_ids = _scan_ids(slide, {"evidence_id", "evidence_ids"})
        slide_met_ids = _scan_ids(slide, {"metric_id", "metric_ids"})
        for ev_id in slide_ev_ids:
            if not EV_RE.fullmatch(ev_id):
                errors.append(f"slide {slide_no}: invalid evidence id {ev_id}")
            elif ev_ids and ev_id not in ev_ids:
                errors.append(f"slide {slide_no}: evidence id {ev_id} not found in research_evidence_db")
        for metric_id in slide_met_ids:
            if not MET_RE.fullmatch(metric_id):
                errors.append(f"slide {slide_no}: invalid metric id {metric_id}")
            elif met_ids and metric_id not in met_ids:
                errors.append(f"slide {slide_no}: metric id {metric_id} not found in research_evidence_db")


def validate_template_registry(path: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    slides = payload.get("slides")
    if not isinstance(slides, list) or not slides:
        errors.append("template_registry.slides must be a non-empty list")
        return
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        if not isinstance(slide.get("slide_no"), int):
            errors.append("template_registry slide missing integer slide_no")
        if not as_list(slide.get("variants")):
            warnings.append(f"template_registry slide {slide.get('slide_no')}: no variants")


def validate_deck_blueprint(path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    slides = payload.get("slides")
    if not isinstance(slides, list) or not slides:
        errors.append("deck_blueprint.slides must contain at least one page")
        return
    template = _json(run_dir / "template_registry.json", []) if (run_dir / "template_registry.json").exists() else {}
    strict_layout = _strict_layout(run_dir, payload)
    if strict_layout and len(slides) > 12:
        errors.append(
            f"deck_blueprint has {len(slides)} pages; strict_layout requires the fixed template page set"
        )
    seen_slide_numbers: list[int] = []
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        slide_no = int(slide.get("slide_no") or 0)
        seen_slide_numbers.append(slide_no)
        expected = FIXED_PAGE_ROLES.get(slide_no)
        if expected and text(slide.get("fixed_page_role")) != expected:
            if strict_layout:
                errors.append(
                    f"slide {slide_no}: fixed_page_role differs from registry role {expected}; "
                    "strict_layout mode requires registry alignment"
                )
        banker_page_id = banker_page_id_for_slide(slide)
        if not BP_RE.fullmatch(banker_page_id):
            errors.append(f"slide {slide_no}: invalid banker_page_id")
        if not _slide_headline(slide) and not _slide_page_argument(slide):
            warnings.append(
                f"slide {slide_no}: deck_blueprint has no headline/title or page argument; "
                "renderer can still proceed, but LLM/QC should confirm the visible page has a client-facing title or another clear focal point"
            )
        if strict_layout:
            for field in ("main_message", "selected_page_type"):
                if not text(slide.get(field)):
                    errors.append(f"slide {slide_no}: {field} is required in strict_layout")
        if not _has_substantive_page_content(slide):
            message = (
                f"slide {slide_no}: deck_blueprint has no substantive page payload beyond title/argument fields. "
                "LLM/QC should decide whether this is an intentional divider, a page to merge/drop, or a page-pack repair; "
                "do not hand-author helper render artifacts to hide a weak page."
            )
            (errors if strict_layout else warnings).append(message)
        if template and strict_layout and text(slide.get("selected_page_type")):
            try:
                strict_layout_body_fields(template, slide_no, text(slide.get("selected_page_type")))
            except Exception as exc:
                errors.append(f"slide {slide_no}: strict placeholder mapping failed: {exc}")
    duplicates = sorted({number for number in seen_slide_numbers if number and seen_slide_numbers.count(number) > 1})
    if duplicates:
        errors.append(f"deck_blueprint contains duplicate slide_no values: {duplicates}")


def validate_page_contract(path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    slides = payload.get("slides")
    if not isinstance(slides, list) or not slides:
        errors.append("page_evidence_contract.slides must contain at least one page")
        return
    deck = _json(run_dir / "deck_blueprint.json", []) if (run_dir / "deck_blueprint.json").exists() else {}
    strict_layout = _strict_layout(run_dir, deck)
    if strict_layout and len(slides) > 12:
        errors.append(
            f"page_evidence_contract has {len(slides)} pages; strict_layout requires the fixed template page set"
        )
    deck_by_no = _slide_index(deck)
    for entry in slides:
        if not isinstance(entry, dict):
            continue
        slide_no = int(entry.get("slide_no") or 0)
        expected_id = f"BP-{slide_no:03d}"
        if text(entry.get("banker_page_id")) != expected_id:
            errors.append(f"slide {slide_no}: banker_page_id must be {expected_id}")
        permission = entry.get("downstream_permission")
        if not isinstance(permission, dict):
            errors.append(f"slide {slide_no}: downstream_permission object is required")
        deck_slide = deck_by_no.get(slide_no)
        if deck_slide and text(entry.get("banker_page_id")) != banker_page_id_for_slide(deck_slide):
            errors.append(f"slide {slide_no}: banker_page_id mismatch with deck_blueprint")


def validate_renderer_spec(path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    if payload.get("schema_version") != "renderer_spec_v1":
        errors.append("renderer_spec.schema_version must be renderer_spec_v1")
    slides = payload.get("slides")
    if not isinstance(slides, list) or not slides:
        errors.append("renderer_spec.slides must contain at least one page")
        return
    strict_layout = _strict_layout(run_dir, payload)
    if strict_layout and len(slides) > 12:
        errors.append(
            f"renderer_spec has {len(slides)} pages; strict_layout requires the fixed template page set"
        )
    try:
        build_token_source(payload)
    except Exception as exc:
        errors.append(f"renderer_spec cannot be converted into token source: {exc}")


def _has_structured_qc_user_decision_basis(readiness: Any) -> bool:
    if not isinstance(readiness, dict):
        return False
    if (
        readiness.get("targeted_research_loop_exhausted") is True
        or readiness.get("source_unavailable") is True
        or readiness.get("realistic_sources_unavailable") is True
        or readiness.get("operator_authorized_stop_research") is True
    ):
        return True
    source_limit = readiness.get("source_limit")
    if isinstance(source_limit, dict):
        return (
            source_limit.get("source_unavailable") is True
            or source_limit.get("realistic_sources_unavailable") is True
            or source_limit.get("no_material_page_impact") is True
        )
    return False


def validate_client_ready_page_pack(run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    path = run_dir / "banker_page_pack.json"
    payload = _json(path, errors)
    if not payload:
        return
    readiness_raw = payload.get("deliverable_readiness")
    readiness = readiness_raw if isinstance(readiness_raw, dict) else {}
    readiness_note = _readiness_note_from_page_pack(readiness_raw)
    business_action = str(readiness.get("business_action") or "").strip().lower()
    has_readiness_decision = bool(business_action)
    calls_for_research = business_action == "targeted_research"
    strict_layout = _strict_layout(run_dir, payload)
    if not has_readiness_decision:
        warnings.append(
            "LLM readiness prompt: banker_page_pack does not give automation a clear final-output next action. "
            "LLM/QC should state the business decision in the page pack, preferably as deliverable_readiness.business_action: "
            "send, repair page writing/exhibits, run one bounded research request, "
            "or ask QC/user after source limits. Helper checks do not infer final delivery readiness from prose or legacy boolean fields."
        )
    if calls_for_research:
        warnings.append(
            "LLM readiness prompt: banker_page_pack asks for bounded targeted research; "
            "run only the bounded, decision-changing research request, then let LLM/QC decide whether the page pack "
            "can render or should ask QC/user after the loop cap."
        )
    if business_action == "qc_user_decision" and not _has_structured_qc_user_decision_basis(readiness):
        warnings.append(
            "LLM readiness prompt: qc_user_decision should not be used as a bare stop label. "
            "Use targeted_research while another bounded pass could change deck inclusion, key data audit, or exhibit readiness; "
            "otherwise state the basis clearly: targeted research is exhausted, realistic sources are unavailable, another pass would not change the page, "
            "or the operator explicitly authorized stopping research."
        )
    slides = [slide for slide in as_list(payload.get("slides")) if isinstance(slide, dict)]
    not_allowed = [
        int(slide.get("slide_no") or 0)
        for slide in slides
        if normalize_allowed_deck_usage(slide.get("allowed_deck_usage") or slide.get("deck_use")) == "not_allowed"
    ]
    if not_allowed:
        message = (
            f"banker_page_pack contains page(s) marked not for deck: {not_allowed}; "
            "style-guided structured render will skip these pages, while strict_layout requires removing or repairing them before render."
        )
        (errors if strict_layout else warnings).append(message)
    renderable = [
        slide
        for slide in slides
        if normalize_allowed_deck_usage(slide.get("allowed_deck_usage") or slide.get("deck_use")) in {"headline_allowed", "body_only", "supporting_context", "caveat_only"}
    ]
    missing_arguments = [
        int(slide.get("slide_no") or idx)
        for idx, slide in enumerate(renderable, start=1)
        if not _slide_page_argument(slide)
        and not (_slide_headline(slide) and _has_substantive_page_content(slide))
    ]
    if missing_arguments:
        warnings.append(
            f"LLM editorial prompt: renderable page(s) lack a page argument/thesis: {missing_arguments}; "
            "LLM/QC should confirm the visible headline, exhibit, and body copy carry a clear client-facing industry judgment"
        )
    missing_headline_and_argument = [
        int(slide.get("slide_no") or idx)
        for idx, slide in enumerate(renderable, start=1)
        if not _slide_headline(slide)
        and not _slide_page_argument(slide)
    ]
    missing_headline_with_argument = [
        int(slide.get("slide_no") or idx)
        for idx, slide in enumerate(renderable, start=1)
        if not _slide_headline(slide)
        and _slide_page_argument(slide)
    ]
    if missing_headline_and_argument:
        warnings.append(
            f"renderable page(s) lack both headline/title and page argument: {missing_headline_and_argument}; "
            "LLM/QC should confirm another visible element carries the page claim, or repair banker_page_pack with "
            "client-facing slide language before treating the output as final"
        )
    if missing_headline_with_argument:
        warnings.append(
            f"LLM editorial prompt: renderable page(s) lack an explicit headline/title but have a page argument: {missing_headline_with_argument}; "
            "structured-render helper can derive a title from the page argument, but LLM/QC should confirm the visible slide language after render"
        )


def _readiness_note_from_page_pack(readiness: Any) -> str:
    if isinstance(readiness, str):
        return readiness.strip()
    if not isinstance(readiness, dict):
        return ""
    fields = (
        "readiness_note",
        "decision_note",
        "targeted_research_rationale",
        "rationale",
        "reason",
    )
    return " ".join(text(readiness.get(field)) for field in fields if text(readiness.get(field)))


def validate_replacement_dict(path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _json(path, errors)
    if not payload:
        return
    def scan_values(value: Any) -> bool:
        if isinstance(value, dict):
            return any(scan_values(item) for item in value.values())
        if isinstance(value, list):
            return any(scan_values(item) for item in value)
        return isinstance(value, str) and ("{{" in value or "}}" in value)

    if scan_values(payload):
        errors.append("replacement_dict contains unresolved placeholder braces in replacement values")
    if not (run_dir / "renderer_spec.json").exists():
        warnings.append(
            "replacement_dict exists without renderer_spec.json; treat it as a direct-composition/debug artifact, "
            "not as proof that the structured-render path is available"
        )


def validate_filled_ppt(path: Path, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    marker_candidates: list[Path] = []
    marker = run_dir / "LATEST_FINAL_PPT.txt"
    if marker.exists():
        try:
            marker_lines = marker.read_text(encoding="utf-8").splitlines()
            marker_value = text(marker_lines[0] if marker_lines else "")
        except Exception as exc:
            marker_value = ""
            warnings.append(f"could not read LATEST_FINAL_PPT.txt: {exc}")
        if marker_value:
            marker_path = Path(marker_value)
            if not marker_path.is_absolute():
                marker_path = run_dir / marker_path
            if marker_path.suffix.lower() != ".pptx":
                warnings.append("LATEST_FINAL_PPT.txt does not point to a .pptx file")
            marker_candidates.append(marker_path)
        else:
            warnings.append("LATEST_FINAL_PPT.txt is empty; falling back to default PPT filenames")
    candidates = [
        *marker_candidates,
        run_dir / "industry_section_filled_clean.pptx",
        run_dir / "industry_section_filled.pptx",
        run_dir / "RESEARCH_LIMITED_REVIEW_industry_section_filled_clean.pptx",
        run_dir / "RESEARCH_LIMITED_REVIEW_industry_section_filled.pptx",
    ]
    unique_candidates = list(dict.fromkeys(candidates))
    existing = [candidate for candidate in unique_candidates if candidate.exists()]
    if not existing:
        marker_note = ""
        if marker_candidates:
            marker_note = f"; LATEST_FINAL_PPT.txt points to {marker_candidates[0]}"
        errors.append(f"missing filled PPT output{marker_note}")
        return
    target = existing[0]
    if target.name.startswith("RESEARCH_LIMITED_REVIEW_"):
        warnings.append(
            f"{target.name} exists as a research-limited review copy; targeted research or QC acceptance is still required before final delivery"
        )
    try:
        with zipfile.ZipFile(target) as archive:
            names = set(archive.namelist())
            if "[Content_Types].xml" not in names:
                errors.append(f"{target.name} is not a valid pptx package")
    except Exception as exc:
        errors.append(f"cannot inspect PPT package {target}: {exc}")
        return
    try:
        slide_texts = _ppt_slide_texts(target)
    except Exception as exc:
        warnings.append(f"could not extract PPT slide text for visual QC: {exc}")
        slide_texts = []
    for idx, slide_text in enumerate(slide_texts, start=1):
        bad = sorted(char for char in BAD_PPT_GLYPHS if char in slide_text)
        if bad:
            errors.append(f"slide {idx}: PPT text contains missing-glyph/tofu characters: {' '.join(bad)}")
        lowered = slide_text.lower()
        matched_categories = sorted(
            {
                category
                for term, category in CLIENT_VISIBLE_EDITORIAL_HINT_TERMS.items()
                if term.lower() in lowered
            }
        )
        if matched_categories:
            warnings.append(
                f"slide {idx}: LLM visual/editorial prompt: rendered PPT text may contain internal workpaper language "
                f"({', '.join(matched_categories)}). Repair banker_page_pack visible copy and rerender before final delivery."
            )
    postprocess_log = run_dir / "artifacts/postprocess_ppt_visuals.log.json"
    if postprocess_log.exists():
        log = _json(postprocess_log, [])
        for item in as_list(log.get("chart_rendering")):
            if not isinstance(item, dict):
                continue
            if item.get("required_render", True) is not False and item.get("rendered") is not True:
                chart = item.get("chart") if isinstance(item.get("chart"), dict) else {}
                errors.append(
                    f"slide {item.get('slide_no', '?')}: required visual renderer failed: "
                    f"{text(item.get('reason')) or text(chart.get('reason'))}"
                )


def _compiled_render_artifacts_present(run_dir: Path) -> bool:
    return all(
        (run_dir / rel).exists()
        for rel in (
            "deck_blueprint.json",
            "page_evidence_contract.json",
            "renderer_spec.json",
        )
    )


def _validate_compiled_render_path(run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    required = [
        "banker_page_pack.json",
        "template_registry.json",
        "deck_blueprint.json",
        "page_evidence_contract.json",
        "renderer_spec.json",
    ]
    for rel in required:
        if not (run_dir / rel).exists():
            errors.append(f"missing required upstream artifact: {rel}")
    if errors:
        return
    validate_banker_page_pack(run_dir / "banker_page_pack.json", run_dir, errors, warnings)
    validate_client_ready_page_pack(run_dir, errors, warnings)
    validate_template_registry(run_dir / "template_registry.json", errors, warnings)
    validate_deck_blueprint(run_dir / "deck_blueprint.json", run_dir, errors, warnings)
    validate_page_contract(run_dir / "page_evidence_contract.json", run_dir, errors, warnings)
    validate_renderer_spec(run_dir / "renderer_spec.json", run_dir, errors, warnings)


def _validate_direct_ppt_composition_path(run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    if not (run_dir / "banker_page_pack.json").exists():
        errors.append("missing required upstream artifact: banker_page_pack.json")
        return
    validate_banker_page_pack(run_dir / "banker_page_pack.json", run_dir, errors, warnings)
    validate_client_ready_page_pack(run_dir, errors, warnings)
    warnings.append(
        "direct PPT composition path: structured-render helper artifacts are absent, so deterministic checks cover "
        "the banker_page_pack and PPT package only. LLM/QC must review the actual PPT for source notes, "
        "client-facing language, exhibit density, and template-style fidelity."
    )


def validate_stage(artifact: str, run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    if artifact == "pre_ppt":
        if _compiled_render_artifacts_present(run_dir):
            _validate_compiled_render_path(run_dir, errors, warnings)
        else:
            _validate_direct_ppt_composition_path(run_dir, errors, warnings)
        return
    else:
        required = []
    for rel in required:
        if not (run_dir / rel).exists():
            errors.append(f"missing required upstream artifact: {rel}")
    if errors:
        return

    if artifact == "pre_ppt":
        if _compiled_render_artifacts_present(run_dir):
            _validate_compiled_render_path(run_dir, errors, warnings)
        else:
            _validate_direct_ppt_composition_path(run_dir, errors, warnings)
    elif artifact == "final_delivery":
        if _compiled_render_artifacts_present(run_dir):
            _validate_compiled_render_path(run_dir, errors, warnings)
        else:
            _validate_direct_ppt_composition_path(run_dir, errors, warnings)
        if (run_dir / "replacement_dict.json").exists():
            validate_replacement_dict(run_dir / "replacement_dict.json", run_dir, errors, warnings)
        validate_filled_ppt(run_dir / "filled_ppt_validation.json", run_dir, errors, warnings)


def validate_artifact(artifact: str, run_dir: Path, path: Path | None = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    target = path or run_dir / ARTIFACT_PATHS.get(artifact, "")
    if artifact in {"material_manifest", "material_extracts", "input_card"}:
        validate_material_like(artifact, target, run_dir, errors, warnings)
    elif artifact == "research_request_queue":
        validate_research_request_queue(target, errors, warnings)
    elif artifact == "industry_scope_pack":
        validate_scope(target, errors, warnings)
    elif artifact == "industry_boundary_qc":
        validate_industry_boundary_qc(target, errors, warnings)
    elif artifact == "formal_search_plan":
        validate_formal_plan(target, errors, warnings)
    elif artifact == "executable_search_batch":
        validate_search_batch(target, errors, warnings)
    elif artifact == "research_graph_state":
        validate_research_graph_state(target, errors, warnings)
    elif artifact == "formal_research_execution":
        validate_execution(target, run_dir, errors, warnings)
    elif artifact == "source_archive":
        validate_source_archive(target, run_dir, errors, warnings)
    elif artifact == "research_evidence_db":
        validate_research_evidence_db(target, errors, warnings)
    elif artifact == "research_pack":
        validate_research_pack(target, run_dir, errors, warnings)
    elif artifact == "banker_page_pack":
        validate_banker_page_pack(target, run_dir, errors, warnings)
    elif artifact == "template_registry":
        validate_template_registry(target, errors, warnings)
    elif artifact == "deck_blueprint":
        validate_deck_blueprint(target, run_dir, errors, warnings)
    elif artifact == "page_evidence_contract":
        validate_page_contract(target, run_dir, errors, warnings)
    elif artifact == "renderer_spec":
        validate_renderer_spec(target, run_dir, errors, warnings)
    elif artifact == "replacement_dict":
        validate_replacement_dict(target, run_dir, errors, warnings)
    elif artifact == "filled_ppt":
        validate_filled_ppt(target, run_dir, errors, warnings)
    elif artifact in {"pre_ppt", "final_delivery"}:
        validate_stage(artifact, run_dir, errors, warnings)
    else:
        errors.append(f"unknown artifact: {artifact}")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True, choices=sorted(ARTIFACT_PATHS))
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--path", help="Optional explicit artifact path.")
    parser.add_argument("--output")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    path = Path(args.path) if args.path else None
    errors, warnings = validate_artifact(args.artifact, run_dir, path)
    owner_guidance = helper_check_guidance(args.artifact, errors, warnings)
    result = {
        "artifact": args.artifact,
        "review_outcome": owner_guidance["status"],
        "owner_repair_guidance": owner_guidance,
        "helper_check_policy": "structure_only",
        "is_valid": not errors,
        "run_dir": str(run_dir),
        "path": str(path or run_dir / ARTIFACT_PATHS[args.artifact]),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
    if args.artifact == "banker_page_pack":
        diagnostics = banker_page_pack_template_diagnostics(run_dir, path)
        diagnostics_path = run_dir / "artifacts" / "banker_page_pack_template_diagnostics.json"
        diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
        diagnostics_path.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result["template_diagnostics_path"] = str(diagnostics_path)
    output = json.dumps(result, ensure_ascii=False, indent=2)
    output_path = Path(args.output) if args.output else run_dir / VALIDATION_OUTPUTS.get(args.artifact, f"artifacts/{args.artifact}_validation.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
