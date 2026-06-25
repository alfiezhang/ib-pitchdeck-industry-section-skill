#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from conftest import ROLE_SCRIPT_DIRS, SCRIPT_IMPORT_PATHS, SKILL_DIR, SLIDE_NUMBERS, _write_json


def _body_copy_for(slide_no: int, page_type: str, template_registry: dict, blocks: list[dict]) -> dict[str, str]:
    from template_contract_utils import required_body_fields

    fields = required_body_fields(template_registry, slide_no, page_type)
    result: dict[str, str] = {}
    for idx, field in enumerate(fields):
        result[field] = blocks[idx % len(blocks)]["copy"]
    return result


def _banker_page_pack(deck_blueprint_data: dict, template_registry: dict) -> dict:
    slides = []
    for slide in deck_blueprint_data["slides"]:
        slide_no = int(slide["slide_no"])
        page_evidence_ids = [
            f"EV-{((slide_no - 1) % 6) + 1:03d}",
            f"EV-{((slide_no) % 6) + 1:03d}",
        ]
        evidence_ids = sorted(
            {
                *page_evidence_ids,
                *(item for item in slide.get("evidence_ids", []) if item),
                *(
                    item
                    for block in slide.get("body_blocks", [])
                    for item in block.get("evidence_ids", [])
                    if item
                ),
            }
        ) or ["EV-001"]
        metric_id = f"MET-{((slide_no - 1) % 4) + 1:03d}"
        secondary_metric_id = f"MET-{((slide_no) % 4) + 1:03d}"
        metric_ids = sorted(
            {
                metric_id,
                secondary_metric_id,
                *(item for item in slide.get("metric_ids", []) if item),
                *(
                    item
                    for block in slide.get("body_blocks", [])
                    for item in block.get("metric_ids", [])
                    if item
                ),
            }
        )
        blocks = [
            {
                "role": f"point_{idx}",
                "copy": (
                    f"Page {slide_no} point {idx} interprets evidence for a pre-mandate client discussion, "
                    "linking industry structure, transaction framing, and market economics rather than listing generic facts."
                ),
                "evidence_ids": evidence_ids,
                "metric_ids": [metric_id] if idx in {1, 2} else [],
                "claim_strength": "supported_inference",
            }
            for idx in range(1, 5)
        ]
        chart_data = slide.get("chart_data") if isinstance(slide.get("chart_data"), dict) else {}
        compare_table_data = slide.get("compare_table_data") if isinstance(slide.get("compare_table_data"), dict) else {}
        if slide_no in {1, 2}:
            chart_data = {
                "chart_type": "bar",
                "title": f"Slide {slide_no} metric trend",
                "categories": ["2022", "2023", "2024"],
                "series": [{"name": "Indexed metric", "values": [80.0 + slide_no, 92.0 + slide_no, 108.0 + slide_no]}],
                "unit": "index",
                "source_rows": [
                    {"label": "2022", "value": 80.0 + slide_no, "metric_id": metric_id},
                    {"label": "2023", "value": 92.0 + slide_no, "metric_id": secondary_metric_id},
                    {"label": "2024", "value": 108.0 + slide_no, "metric_id": metric_id},
                ],
            }
        if slide_no in {3, 5}:
            compare_table_data = {
                "headers": ["Dimension", "Evidence-backed read", "Pitch implication"],
                "rows": [
                    {"label": "Demand", "cells": ["Supported by EV/MET linkage", "Repeatability should be framed with evidence boundaries"]},
                    {"label": "Competition", "cells": ["Differentiation varies by capability", "Positioning should avoid unsupported share claims"]},
                    {"label": "Economics", "cells": ["Profit pool evidence remains central", "Transaction story must connect to margin control"]},
                ],
            }
        slides.append(
            {
                "slide_no": slide_no,
                "fixed_page_role": slide["fixed_page_role"],
                "page_primary_subject": "industry" if slide_no <= 6 else "industry_with_project_relevance",
                "page_question": f"What industry point must page {slide_no} prove for the pitch?",
                "banker_judgment": (
                    f"Page {slide_no} should communicate a banker judgment about market structure, transaction framing, "
                    "and sector economics using evidence rather than broad industry commentary, while also explaining "
                    "how the client should frame growth quality, competitive risk, and transaction logic before a mandate is signed."
                ),
                "page_argument": slide["page_argument"],
                "selected_page_type": slide["selected_page_type"],
                "claim_strength": "supported_inference",
                "headline": slide["headline"],
                "main_message": (
                    f"Page {slide_no} connects sourced evidence, visible data, and industry implications so the page reads as banker judgment instead of a sparse research summary, "
                    "with enough detail to support client discussion and enough caution to preserve evidence boundaries."
                ),
                "exhibit": {
                    **slide["exhibit"],
                    "data_or_evidence_inputs": [*evidence_ids, *metric_ids],
                    "visual_structure": "A dense exhibit using chart/table/card fields plus body blocks to fill the formal page.",
                },
                "body_blocks": blocks,
                "body_copy": _body_copy_for(slide_no, slide["selected_page_type"], template_registry, blocks),
                "evidence_ids": evidence_ids,
                "metric_ids": metric_ids,
                "visible_metric_claims": [
                    {
                        "location": "main exhibit",
                        "display_text": f"Indexed metric supports page {slide_no}",
                        "metric_ids": [metric_id],
                        "usage_type": "context_only",
                        "basis_note": "Test fixture metric binding.",
                    }
                ],
                "chart_data": chart_data,
                "compare_table_data": compare_table_data,
                "project_relevance_note": (
                    f"For a pre-mandate pitch, page {slide_no} turns the industry evidence into a transaction-framing discussion point."
                    if slide_no in {7, 8}
                    else ""
                ),
                "source_note": "Sources: " + "; ".join(evidence_ids),
                "caveats": [],
                "evidence_boundary_notes": [],
            }
        )
    return {
        "schema_version": "banker_page_pack",
        "section_meta": {"target_company": "Example Target", "industry": "Example sector"},
        "deck_storyline": (
            "The section moves from industry scale and structure into competition, economics, and project implications, "
            "using traceable data and banker judgment to support a pre-mandate client conversation. It should make the bank's industry view visible through charts, tables, caveats, and selective project relevance rather than through generic summary language."
        ),
        "evidence_policy": {
            "important_data": "Use MET rows from research_evidence_db with audit-grade source fields.",
            "normal_claims": "Use EV/source IDs and visible caveats.",
        },
        "deliverable_readiness": {
            "decision_status": "llm_decided",
            "decision_owner": "generation",
            "enough_for_client_pitch": True,
            "evidence_limited_pitch_outline": False,
            "research_first_required": False,
            "decision_note": "Fixture has enough evidence-linked page copy, visible metrics, and exhibits to proceed as a pre-mandate client pitch section.",
        },
        "key_data_audit": [
            {
                "metric_id": f"MET-{idx:03d}",
                "indicator": f"Fixture indexed metric {idx}",
                "value": str(100 + idx),
                "unit": "index",
                "period": "2024",
                "geography": "Fixture market",
                "source": "Contract fixture source",
                "original_location": "Fixture table 1",
                "original_excerpt": "Fixture excerpt supports the indexed value.",
                "usage_in_deck": "Visible metric claim and exhibit support.",
                "remarks": "Contract-test audit row.",
            }
            for idx in range(1, 5)
        ],
        "conflict_data_notes": [],
        "slides": slides,
    }


def _run(script_name: str, args: list[str]) -> subprocess.CompletedProcess:
    script_path = SKILL_DIR / "scripts" / "pipeline.py" if script_name == "pipeline.py" else ROLE_SCRIPT_DIRS[script_name]
    return subprocess.run(
        [sys.executable, str(script_path), *args],
        text=True,
        capture_output=True,
        cwd=str(SKILL_DIR),
        env={**__import__("os").environ, "PYTHONPATH": ":".join(str(path) for path in SCRIPT_IMPORT_PATHS)},
    )


def test_banker_page_pack_rejects_sparse_page(tmp_path: Path) -> None:
    pack = {
        "schema_version": "banker_page_pack",
        "section_meta": {},
        "deck_storyline": "too short",
        "slides": [
            {
                "slide_no": idx,
                "fixed_page_role": "industry_overview",
                "page_primary_subject": "industry",
                "page_question": "Question?",
                "banker_judgment": "thin",
                "page_argument": "thin",
                "selected_page_type": "summary_page",
                "claim_strength": "supported_inference",
                "headline": "Thin page",
                "main_message": "thin",
                "exhibit": {"exhibit_type": "driver_cards", "data_or_evidence_inputs": ["EV-001"], "visual_structure": "thin"},
                "body_blocks": [],
                "evidence_ids": ["EV-001"],
                "metric_ids": [],
                "project_relevance_note": "",
                "source_note": "Sources: EV-001",
            }
            for idx in SLIDE_NUMBERS
        ],
    }
    path = tmp_path / "banker_page_pack.json"
    _write_json(path, pack)

    result = _run("pipeline.py", ["validate", "--artifact", "banker_page_pack", "--run-dir", str(tmp_path), "--path", str(path)])
    assert result.returncode != 0
    assert "body_blocks is required" in result.stdout


def test_banker_page_pack_leaves_target_drift_to_llm_qc(tmp_path: Path) -> None:
    slides = []
    for idx in SLIDE_NUMBERS:
        slides.append(
            {
                "slide_no": idx,
                "fixed_page_role": "industry_overview",
                "page_primary_subject": "industry",
                "page_question": "What industry point matters?",
                "banker_judgment": "Industry judgment with source-backed market mechanism.",
                "page_argument": "Industry page argument with evidence and implication.",
                "selected_page_type": "summary_page",
                "claim_strength": "supported_inference",
                "headline": "标的公司具备强交易故事",
                "main_message": "Industry message.",
                "exhibit": {
                    "exhibit_type": "driver_cards",
                    "why_this_exhibit": "Shows market mechanisms.",
                    "data_or_evidence_inputs": ["EV-001"],
                    "visual_structure": "Four industry cards.",
                    "density_target": "Dense.",
                    "fallback_if_data_limited": "Use evidence-gap matrix.",
                },
                "body_blocks": [
                    {
                        "role": f"point_{n}",
                        "copy": "Industry mechanism with evidence and implication.",
                        "evidence_ids": ["EV-001"],
                        "metric_ids": [],
                        "claim_strength": "supported_inference",
                    }
                    for n in range(4)
                ],
                "evidence_ids": ["EV-001"],
                "metric_ids": [],
                "project_relevance_note": "",
                "source_note": "Sources: EV-001",
            }
        )
    pack = {
        "schema_version": "banker_page_pack",
        "section_meta": {},
        "deck_storyline": "Industry-led storyline.",
        "deliverable_readiness": {
            "decision_status": "llm_decided",
            "decision_owner": "generation",
            "enough_for_client_pitch": True,
            "decision_note": "Fixture.",
        },
        "slides": slides,
    }
    path = tmp_path / "banker_page_pack.json"
    _write_json(path, pack)

    result = _run("pipeline.py", ["validate", "--artifact", "banker_page_pack", "--run-dir", str(tmp_path), "--path", str(path)])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "headline contains target/project terms" not in result.stdout
    qc_text = (SKILL_DIR / "references/qc.md").read_text(encoding="utf-8")
    assert "target-context drift" in qc_text


def test_banker_page_pack_leaves_subject_mix_to_llm_qc(tmp_path: Path) -> None:
    slides = []
    for idx in SLIDE_NUMBERS:
        slides.append(
            {
                "slide_no": idx,
                "fixed_page_role": "industry_overview",
                "page_primary_subject": "industry_with_project_relevance",
                "page_question": "What industry point matters?",
                "banker_judgment": "Industry judgment with source-backed market mechanism.",
                "page_argument": "Industry page argument with evidence and implication.",
                "selected_page_type": "summary_page",
                "claim_strength": "supported_inference",
                "headline": "Industry structure is the primary page subject",
                "main_message": "Industry message.",
                "exhibit": {
                    "exhibit_type": "driver_cards",
                    "why_this_exhibit": "Shows market mechanisms.",
                    "data_or_evidence_inputs": ["EV-001"],
                    "visual_structure": "Four industry cards.",
                    "density_target": "Dense.",
                    "fallback_if_data_limited": "Use evidence-gap matrix.",
                },
                "body_blocks": [
                    {
                        "role": f"point_{n}",
                        "copy": "Industry mechanism with evidence and implication.",
                        "evidence_ids": ["EV-001"],
                        "metric_ids": [],
                        "claim_strength": "supported_inference",
                    }
                    for n in range(4)
                ],
                "evidence_ids": ["EV-001"],
                "metric_ids": [],
                "project_relevance_note": "Short project bridge.",
                "source_note": "Sources: EV-001",
            }
        )
    pack = {
        "schema_version": "banker_page_pack",
        "section_meta": {},
        "deck_storyline": "Industry-led storyline.",
        "deliverable_readiness": {
            "decision_status": "llm_decided",
            "decision_owner": "generation",
            "enough_for_client_pitch": True,
            "decision_note": "Fixture.",
        },
        "slides": slides,
    }
    path = tmp_path / "banker_page_pack.json"
    _write_json(path, pack)

    result = _run("pipeline.py", ["validate", "--artifact", "banker_page_pack", "--run-dir", str(tmp_path), "--path", str(path)])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "fewer industry-primary pages than the advisory target" not in result.stdout
    assert "more project_relevance_note pages than the advisory target" not in result.stdout
    assert "references/content-quality.md" in (SKILL_DIR / "references/qc.md").read_text(encoding="utf-8")


def test_banker_page_pack_leaves_mixed_axis_units_to_llm_qc(
    tmp_path: Path,
    deck_blueprint_data: dict,
    template_registry_path: Path,
) -> None:
    template_registry = json.loads(template_registry_path.read_text(encoding="utf-8"))
    pack = _banker_page_pack(deck_blueprint_data, template_registry)
    pack["slides"][0]["chart_data"]["source_rows"] = [
        {"label": "market size", "value": 100, "unit": "RMB bn", "metric_id": "MET-001"},
        {"label": "target sales", "value": 470, "unit": "万件", "metric_id": "MET-002"},
    ]
    path = tmp_path / "banker_page_pack.json"
    _write_json(path, pack)

    result = _run("pipeline.py", ["validate", "--artifact", "banker_page_pack", "--run-dir", str(tmp_path), "--path", str(path)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "chart_data mixes units on one chart axis" not in result.stdout
    assert "mixed units" in (SKILL_DIR / "references/qc.md").read_text(encoding="utf-8")


def test_banker_page_pack_validates_and_compiles(
    tmp_path: Path,
    deck_blueprint_data: dict,
    template_registry_path: Path,
) -> None:
    template_registry = json.loads(template_registry_path.read_text(encoding="utf-8"))
    pack = _banker_page_pack(deck_blueprint_data, template_registry)
    pack_path = tmp_path / "banker_page_pack.json"
    _write_json(pack_path, pack)
    (tmp_path / "template_registry.json").write_text(template_registry_path.read_text(encoding="utf-8"), encoding="utf-8")

    validation = _run("pipeline.py", ["validate", "--artifact", "banker_page_pack", "--run-dir", str(tmp_path), "--path", str(pack_path)])
    assert validation.returncode == 0, validation.stdout + validation.stderr

    deck_blueprint = tmp_path / "deck_blueprint.json"
    page_contract = tmp_path / "page_evidence_contract.json"
    renderer_spec = tmp_path / "renderer_spec.json"
    result = subprocess.run(
        [sys.executable, str(SKILL_DIR / "scripts" / "pipeline.py"), "compile", "--run-dir", str(tmp_path)],
        text=True,
        capture_output=True,
        cwd=str(SKILL_DIR),
        env={**__import__("os").environ, "PYTHONPATH": ":".join(str(path) for path in SCRIPT_IMPORT_PATHS)},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    compiled_deck = json.loads(deck_blueprint.read_text(encoding="utf-8"))
    assert compiled_deck["authoring_status"] == "derived_from_banker_page_pack"
    assert "page_" + "argument_ids" not in json.dumps(compiled_deck)
    assert "issue_" + "analysis_ids" not in json.dumps(compiled_deck)
    contract = json.loads(page_contract.read_text(encoding="utf-8"))
    assert all(slide.get("banker_page_id", "").startswith("BP-") for slide in contract["slides"])
    renderer = json.loads(renderer_spec.read_text(encoding="utf-8"))
    assert len(renderer["slides"]) == 8
    assert all(slide.get("source_note") for slide in renderer["slides"])
