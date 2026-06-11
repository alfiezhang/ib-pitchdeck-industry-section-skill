#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

import json
import sys


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "runtime" / "ib-pitchdeck-agent-industry-section" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from boundary_loop import run_boundary_loop  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _ready_scope_pack() -> dict:
    return {
        "schema_version": "industry_scope_pack_v1",
        "meta": {"industry": "example"},
        "llm_definition_draft": {
            "purpose": "Boundary-ready scope draft",
            "working_market_draft": "example working market",
            "parent_market_draft": "example parent market",
            "broader_market_draft": "example broader market",
            "included_segments_draft": ["core segment"],
            "excluded_segments_draft": ["adjacent category"],
            "scoping_search_queries": ["query 1", "query 2"],
        },
        "scope_summary": {
            "working_market": "example working market",
            "parent_market": "example parent market",
            "broader_market": "example broader market",
            "adjacent_markets": ["adjacent category"],
        },
        "scope_classification": {
            "core": ["core segment"],
            "broad": ["core segment", "adjacent extension"],
            "adjacent": ["adjacent category"],
            "excluded": ["non-relevant category"],
        },
        "formal_research_seed_questions": ["seed question 1", "seed question 2"],
        "ambiguous_boundaries": [
            {
                "item": "adjacent extension",
                "why_ambiguous": "Some reports include adjacent categories by default.",
                "research_treatment": "Keep scope-separated until explicit evidence appears.",
            }
        ],
        "do_not_use_as_claims": True,
    }


def test_boundary_loop_reports_draft_missing(tmp_path: Path) -> None:
    scope_pack = tmp_path / "artifacts" / "industry_scope_pack.json"
    _write_json(scope_pack, {"meta": {"industry": "example"}})
    extracts = tmp_path / "artifacts" / "material_extracts.json"
    _write_json(extracts, {"schema_version": "material_extracts_v1", "extracts": []})

    status = run_boundary_loop(scope_pack=scope_pack, material_extracts=extracts)

    assert status["status"] == "boundary_draft_missing"
    assert status["boundary_loop_status"] == "boundary_draft_missing"
    assert status["is_valid"] is False


def test_boundary_loop_reports_validation_needed_for_scope_overreach(tmp_path: Path) -> None:
    scope_pack = tmp_path / "artifacts" / "industry_scope_pack.json"
    pack = _ready_scope_pack()
    pack["llm_definition_draft"]["working_market_draft"] = "example"
    pack["scope_summary"]["working_market"] = "example"
    pack["scope_summary"]["parent_market"] = "example"
    pack["scope_summary"]["adjacent_markets"] = []
    _write_json(scope_pack, pack)

    status = run_boundary_loop(scope_pack=scope_pack)

    assert status["status"] == "boundary_validation_needed"
    assert status["boundary_loop_status"] == "boundary_validation_needed"
    assert status["is_valid"] is False
    assert status["warnings"]


def test_boundary_loop_reports_conflict_from_research_evidence(tmp_path: Path) -> None:
    scope_pack = tmp_path / "artifacts" / "industry_scope_pack.json"
    extracts = tmp_path / "artifacts" / "material_extracts.json"
    evidence = tmp_path / "artifacts" / "research_evidence_db.json"
    _write_json(scope_pack, _ready_scope_pack())
    _write_json(extracts, {"schema_version": "material_extracts_v1", "extracts": []})
    _write_json(
        evidence,
        {
            "schema_version": "research_evidence_db_v1",
            "metric_reconciliation": [
                {
                    "metric_id": "MET-001",
                    "conflict_status": "conflict",
                    "resolution": "definitions mismatched and cannot compare",
                }
            ],
        },
    )

    status = run_boundary_loop(scope_pack=scope_pack, material_extracts=extracts, research_evidence_db=evidence)

    assert status["status"] == "boundary_conflict_found"
    assert status["boundary_loop_status"] == "boundary_conflict_found"
    assert status["is_valid"] is False
    assert any("conflict" in item.lower() for item in status["errors"])


def test_boundary_loop_reports_ready_for_clean_inputs(tmp_path: Path) -> None:
    scope_pack = tmp_path / "artifacts" / "industry_scope_pack.json"
    extracts = tmp_path / "artifacts" / "material_extracts.json"
    _write_json(scope_pack, _ready_scope_pack())
    _write_json(extracts, {"schema_version": "material_extracts_v1", "extracts": []})

    status = run_boundary_loop(scope_pack=scope_pack, material_extracts=extracts)

    assert status["status"] == "boundary_ready"
    assert status["boundary_loop_status"] == "boundary_ready"
    assert status["is_valid"] is True
