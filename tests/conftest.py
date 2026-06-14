"""Shared pytest configuration and fixtures for ib-pitchdeck-agent-industry-section tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "runtime" / "ib-pitchdeck-agent-industry-section"
SCRIPT_DIR = SKILL_DIR / "scripts"
ROLE_SCRIPT_PATHS = sorted(path for path in SCRIPT_DIR.iterdir() if path.is_dir())
QC_VALIDATOR_PATHS = sorted((SCRIPT_DIR / "qc" / "validators").glob("*"))
SCRIPT_IMPORT_PATHS = [SCRIPT_DIR, *ROLE_SCRIPT_PATHS, *QC_VALIDATOR_PATHS]
ROLE_SCRIPT_DIRS = {
    script.name: script
    for role_dir in [*ROLE_SCRIPT_PATHS, *QC_VALIDATOR_PATHS]
    for script in role_dir.glob("*.py")
}
FIXTURES_DIR = ROOT / "tests" / "fixtures"

for _path in SCRIPT_IMPORT_PATHS:
    text = str(_path)
    if text in sys.path:
        sys.path.remove(text)
for _path in reversed(SCRIPT_IMPORT_PATHS):
    sys.path.insert(0, str(_path))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run_script(script_name: str, args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a script from SCRIPT_DIR with PYTHONPATH set."""
    env_overrides = {"PYTHONPATH": ":".join(str(path) for path in SCRIPT_IMPORT_PATHS)}
    script_path = ROLE_SCRIPT_DIRS.get(script_name, SCRIPT_DIR / script_name)
    return subprocess.run(
        [sys.executable, str(script_path), *args],
        text=True,
        capture_output=True,
        cwd=cwd or str(SKILL_DIR),
        env={**__import__("os").environ, **env_overrides},
    )


def _rewrite_plan_queries_for_contract_test(plan: dict, *, market: str = "sample sector") -> dict:
    """Simulate Research-role query editing for fixtures.

    The production skeleton intentionally emits LLM_REWRITE_REQUIRED workspaces.
    Contract fixtures need an executable plan, so tests rewrite every query
    before validating.
    """

    for row in plan.get("issue_search_plan", []):
        issue_area = row.get("issue_area", "industry")
        subissue = row.get("subissue", "topic")
        variants = [
            f"{market} {subissue} industry report 2026",
            f"{market} {subissue} official data association filing",
            f"{market} {subissue} methodology scope comparison",
        ]
        for instruction in row.get("search_instructions", []):
            instruction["query"] = variants[0]
            instruction["query_variants"] = variants
            instruction["source_hint"] = instruction.get("source_hint") or f"{issue_area} source review"
    return plan


@pytest.fixture
def root_dir() -> Path:
    return ROOT


@pytest.fixture
def skill_dir() -> Path:
    return SKILL_DIR


@pytest.fixture
def script_dir() -> Path:
    return SCRIPT_DIR


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def write_json():
    return _write_json


@pytest.fixture
def run_script():
    return _run_script


@pytest.fixture
def issue_analysis(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / "valid_issue_analysis.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Session-scoped artifact chain fixtures
# ---------------------------------------------------------------------------


def _build_template_registry(tmp_path: Path) -> Path:
    """Build template_registry.json into tmp_path."""
    from extract_template_registry import build_registry

    registry = build_registry(
        template=SKILL_DIR / "assets" / "industry_section_template_master.pptx",
        slide_registry_path=SKILL_DIR / "configs" / "slide_registry.json",
        page_type_rules_path=SKILL_DIR / "configs" / "page_type_rules.json",
        ppt_mapping_path=SKILL_DIR / "configs" / "ppt_mapping.json",
        layout_budget_path=SKILL_DIR / "configs" / "layout_budget.json",
        text_fit_rules_path=SKILL_DIR / "configs" / "text_fit_rules.json",
    )
    out = tmp_path / "template_registry.json"
    _write_json(out, registry)
    return out


def _build_deck_blueprint(tmp_path: Path, *, slides_override: list | None = None) -> dict:
    """Build a minimal 8-slide deck blueprint for testing."""
    copy_themes = [
        "Scale evidence establishes a market large enough for senior buyer attention.",
        "Forecast evidence needs period assumptions, not broad extrapolation.",
        "Segmentation evidence identifies where growth differs from the total market.",
        "Demand evidence links customer behavior to repeatable revenue pools.",
        "Channel evidence explains how access converts product relevance into share.",
        "Value-chain economics show where margin control tends to accumulate.",
        "Capability barriers matter more than a single visible share statistic.",
        "Peer dispersion creates a comparison basis without target advocacy.",
        "Trend evidence remains directional unless supported by hard data.",
        "Transaction relevance should stay separate from target marketing language.",
        "Source limitations shape how assertive the page conclusion can be.",
        "Competitive intensity clarifies whether the sector rewards scale or focus.",
        "Pricing evidence indicates whether growth is volume-led or premium-led.",
        "Regulatory context frames risk without becoming the main page story.",
        "Technology change matters when it alters cost, quality, or route to market.",
        "Customer concentration affects repeatability and buyer diligence priorities.",
        "Business model evidence separates recurring economics from project revenue.",
        "Margin evidence distinguishes profitable growth from headline expansion.",
        "Market-cycle context prevents overstating a short-term demand spike.",
        "End-market mix explains which pockets deserve deeper buyer discussion.",
        "Distribution power affects bargaining leverage across the chain.",
        "Supply constraints can create advantage only when they persist.",
        "Brand trust evidence matters when purchase risk is high.",
        "Product differentiation must be tied to customer willingness to pay.",
        "M&A evidence supports interest only when multiple cases point the same way.",
        "Valuation context should be caveated when peer comparability is thin.",
        "Risk evidence should lead to questions, not unsupported bearish claims.",
        "Management data can inform context but needs explicit verification status.",
        "Operational KPIs explain why similar revenue bases may trade differently.",
        "Geographic scope matters before comparing market size or growth rates.",
        "Historical growth should be separated from forecast assumptions.",
        "The final page should turn sector view into focused buyer discussion points.",
    ]
    roles = {
        1: "industry_overview", 2: "market_size_segmentation", 3: "key_industry_drivers",
        4: "value_chain_profit_pool", 5: "key_barriers_value_drivers", 6: "competitive_landscape",
        7: "industry_trends_future_evolution", 8: "transaction_implications",
    }
    page_types = {
        1: "industry_overview_dynamic_page", 2: "chart_page", 3: "driver_card_page",
        4: "value_chain_page", 5: "moat_page", 6: "compare_table_page",
        7: "trend_page", 8: "summary_page",
    }
    page_arguments = {
        1: "Quantify sector scale before discussing competitive structure.",
        2: "Use market-segmentation evidence to identify where growth concentrates.",
        3: "Show key demand and channel dynamics shaping the sector.",
        4: "Trace value-chain economics to identify where profitability is controlled.",
        5: "Explain industry moat from barriers, capability, and switching friction.",
        6: "Map peer dispersion to benchmark strategic attractiveness and buyer selectivity.",
        7: "Separate forward-looking trend risks from current trend momentum.",
        8: "Translate sector economics into concrete buyer diligence implications.",
    }
    visual_intents = {
        1: "Prove scale with a current-size evidence visual.",
        2: "Show segment split to guide what buyers compare first.",
        3: "Demonstrate demand momentum through concise directional copy blocks.",
        4: "Explain margin and cost-chain positions with a structured visual map.",
        5: "Use barrier evidence to support defensibility without overclaiming.",
        6: "Compare competitive positions across practical operating dimensions.",
        7: "Use directional trend signals to frame near-term watch points.",
        8: "Frame transaction relevance with caveated implications and buyer questions.",
    }
    evidence_roles = {
        1: "thesis_anchor", 2: "supporting_evidence", 3: "supporting_evidence",
        4: "thesis_anchor", 5: "supporting_evidence", 6: "supporting_evidence",
        7: "context_setting", 8: "context_setting",
    }
    block_counts = {1: 3, 2: 3, 3: 4, 4: 6, 5: 3, 6: 3, 7: 3, 8: 4}
    issue_ids = {
        1: ["IA-001"], 2: ["IA-001", "IA-002"], 3: ["IA-003"], 4: ["IA-003"],
        5: ["IA-003"], 6: ["IA-003"], 7: ["IA-003"], 8: ["IA-003", "IA-004"],
    }

    slides = slides_override if slides_override is not None else []
    if slides_override is None:
        for no in range(1, 9):
            ids = issue_ids[no]
            evidence = ["EV-001"] if "IA-001" in ids or "IA-002" in ids else ["EV-003"]
            metrics = ["MET-001"] if no == 1 else (["MET-003"] if no == 2 else [])
            blocks = []
            for idx in range(1, block_counts[no] + 1):
                theme = copy_themes[((no - 1) * 6 + idx - 1) % len(copy_themes)]
                if no == 6:
                    role_name = ["right_top", "right_mid", "right_bottom"][idx - 1]
                elif no == 8:
                    role_name = ["left_panel", "right_top", "right_mid", "right_bottom"][idx - 1]
                else:
                    role_name = f"point_{idx}"
                blocks.append({
                    "role": role_name, "copy": theme,
                    "source_analysis_ids": ids[:1], "evidence_ids": evidence,
                    "metric_ids": metrics if idx == 1 else [],
                    "claim_strength": "supported_inference",
                })
            if no == 4:
                blocks = [
                    {"role": "profit_pool", "target_field": "bottom_center",
                     "copy": "Profit-pool evidence shows where economics accrue across the industry chain.",
                     "source_analysis_ids": ids[:1], "evidence_ids": evidence, "metric_ids": [],
                     "claim_strength": "supported_inference"},
                    {"role": "upstream", "target_field": "top_left",
                     "copy": "Upstream inputs define cost exposure before operating capabilities take effect.",
                     "source_analysis_ids": ids[:1], "evidence_ids": evidence, "metric_ids": [],
                     "claim_strength": "supported_inference"},
                    {"role": "transaction_implication", "target_field": "bottom_right",
                     "copy": "Transaction relevance should stay tied to sector economics, not target promotion.",
                     "source_analysis_ids": ids[:1], "evidence_ids": evidence, "metric_ids": [],
                     "claim_strength": "supported_inference"},
                    {"role": "manufacturing", "target_field": "top_center",
                     "copy": "Manufacturing execution explains why quality control can become a buyer diligence topic.",
                     "source_analysis_ids": ids[:1], "evidence_ids": evidence, "metric_ids": [],
                     "claim_strength": "supported_inference"},
                    {"role": "brand", "target_field": "top_right",
                     "copy": "Brand ownership converts category credibility into pricing and repeat-purchase power.",
                     "source_analysis_ids": ids[:1], "evidence_ids": evidence, "metric_ids": [],
                     "claim_strength": "supported_inference"},
                    {"role": "channel", "target_field": "bottom_left",
                     "copy": "Channel access determines whether product strength can convert into scaled demand.",
                     "source_analysis_ids": ids[:1], "evidence_ids": evidence, "metric_ids": [],
                     "claim_strength": "supported_inference"},
                ]
            visual_design = {"required_capability": "text", "purpose": f"Support slide {no} page thesis."}
            chart_data: dict = {}
            compare_table_data: dict = {}
            if no == 1:
                visual_design = {"required_capability": "chart", "purpose": "Show current market scale.", "visual_metric_ids": ["MET-001"]}
                chart_data = {
                    "chart_type": "bar", "title": "Current market scale",
                    "categories": ["Current"], "series": [{"name": "Market size", "values": [100.0]}],
                    "unit": "RMB bn", "source_rows": [{"label": "Current", "value": 100.0, "metric_id": "MET-001"}],
                }
            if no == 2:
                visual_design = {"required_capability": "chart", "purpose": "Show segmentation metric.", "visual_metric_ids": ["MET-003"]}
                chart_data = {
                    "chart_type": "bar", "title": "Segment split",
                    "categories": ["Segment"], "series": [{"name": "Share", "values": [45.0]}],
                    "unit": "%", "source_rows": [{"label": "Segment", "value": 45.0, "metric_id": "MET-003"}],
                }
            if no == 6:
                visual_design = {"required_capability": "table", "purpose": "Compare competitive dimensions."}
                compare_table_data = {
                    "headers": ["Dimension", "Evidence-backed read", "Pitch implication"],
                    "rows": [
                        {"label": "Scale", "cells": ["Large enough to matter", "EV-003 supports capability lens", "Frame strategic interest"]},
                        {"label": "Capabilities", "cells": ["Execution matters", "EV-003 supports operating lens", "Assess repeatability"]},
                        {"label": "Competition", "cells": ["Differentiation varies", "EV-003 supports peer lens", "Avoid target advocacy"]},
                    ],
                    "comparison_basis_note": "Illustrative peer dimensions from selected issue analysis.",
                }
            slides.append({
                "slide_no": no, "fixed_page_role": roles[no],
                "investor_question": f"What should an investor learn from slide {no}?",
                "page_thesis": f"Slide {no} answers a distinct industry question with evidence-backed judgment.",
                "page_argument": page_arguments[no], "visual_intent": visual_intents[no],
                "evidence_role": evidence_roles[no],
                "why_this_page_matters": f"Slide {no} matters because it converts research into a pitch-relevant page argument.",
                "issue_analysis_ids": ids, "selected_page_type": page_types[no],
                "claim_strength": "supported_inference",
                "headline": f"Slide {no}: conclusion-led industry view with distinct implication",
                "main_message": f"Slide {no} connects evidence to the pitch without repeating the title.",
                "body_blocks": blocks, "visual_design": visual_design,
                "chart_data": chart_data, "compare_table_data": compare_table_data,
                "source_note": "Sources: " + "; ".join(evidence),
                "pitch_relevance": "Sector credibility first; target context remains selective.",
                "caveats": [], "open_questions": ["Verify target-specific fit after mandate"] if no == 8 else [],
            })
    blueprint = {
        "schema_version": "deck_blueprint_v1",
        "section_meta": {"target_company": "Example Target", "industry": "Example sector"},
        "deck_storyline": "The section moves from market scale to structure, competition, and transaction relevance while preserving evidence boundaries.",
        "slides": slides,
    }
    out = tmp_path / "deck_blueprint.json"
    _write_json(out, blueprint)
    return blueprint


def _compile_blueprint(tmp_path: Path, blueprint_path: Path | None = None, issue_path: Path | None = None, registry_path: Path | None = None) -> tuple[Path, Path]:
    """Compile deck blueprint → page_evidence_contract + renderer_spec."""
    bp = blueprint_path or tmp_path / "deck_blueprint.json"
    ia = issue_path or FIXTURES_DIR / "valid_issue_analysis.json"
    tr = registry_path or tmp_path / "template_registry.json"
    pc_out = tmp_path / "page_evidence_contract.json"
    rs_out = tmp_path / "renderer_spec.json"
    result = subprocess.run(
        [sys.executable, str(ROLE_SCRIPT_DIRS["compile_deck_blueprint.py"]),
         "--issue-analysis", str(ia), "--deck-blueprint", str(bp),
         "--template-registry", str(tr),
         "--page-contract-output", str(pc_out),
         "--renderer-spec-output", str(rs_out)],
        text=True, capture_output=True, cwd=str(SKILL_DIR),
        env={**__import__("os").environ, "PYTHONPATH": ":".join(str(path) for path in SCRIPT_IMPORT_PATHS)},
    )
    if result.returncode != 0:
        raise RuntimeError(f"compile_deck_blueprint failed: {result.stdout}\n{result.stderr}")
    return pc_out, rs_out


@pytest.fixture(scope="session")
def _session_tmp(tmp_path_factory):
    """Session-scoped temporary directory for shared artifacts."""
    return tmp_path_factory.mktemp("contract")


@pytest.fixture(scope="session")
def template_registry_path(_session_tmp):
    """Build template_registry.json once per session."""
    return _build_template_registry(_session_tmp)


@pytest.fixture(scope="session")
def deck_blueprint_path(_session_tmp):
    """Build deck_blueprint.json once per session."""
    _build_deck_blueprint(_session_tmp)
    return _session_tmp / "deck_blueprint.json"


@pytest.fixture(scope="session")
def deck_blueprint_data(_session_tmp):
    """Return deck blueprint dict."""
    _build_deck_blueprint(_session_tmp)
    return json.loads((_session_tmp / "deck_blueprint.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def compiled_artifacts(_session_tmp, deck_blueprint_path, template_registry_path):
    """Compile deck blueprint → page_evidence_contract + renderer_spec."""
    pc, rs = _compile_blueprint(_session_tmp, deck_blueprint_path, registry_path=template_registry_path)
    return {"page_evidence_contract": pc, "renderer_spec": rs}


# ---------------------------------------------------------------------------
# Full pipeline run directory fixture (session-scoped)
# ---------------------------------------------------------------------------


def _minimal_scope_pack() -> dict:
    return {
        "schema_version": "industry_scope_pack_v1",
        "meta": {"industry": "example"},
        "llm_definition_draft": {
            "purpose": "LLM-only definition draft before scoping search.",
            "working_market_draft": "example working market",
            "parent_market_draft": "example parent market",
            "broader_market_draft": "example broader market",
            "included_segments_draft": ["core segment"],
            "excluded_segments_draft": ["adjacent category"],
            "adjacent_markets_draft": ["adjacent category"],
            "ambiguous_boundaries_to_check": ["adjacent extension"],
            "data_scope_questions": ["Which source definitions include adjacent extensions?"],
            "scoping_search_queries": [
                "example industry definition included segments adjacent categories",
                "example industry taxonomy metric definition scope methodology",
            ],
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
        "market_definitions": {
            "narrow_definition": {
                "included_segments": ["core segment"],
                "excluded_segments": ["adjacent category"],
                "use_case": "market sizing / competitive share",
            },
            "broad_definition": {
                "included_segments": ["core segment"],
                "additional_segments": ["adjacent extension"],
                "use_case": "trend discussion / product ecosystem",
            },
        },
        "ambiguous_boundaries": [
            {
                "item": "adjacent extension",
                "why_ambiguous": "It may be classified in the parent category or adjacent category.",
                "research_treatment": "Track separately until formal sources reconcile scope.",
            }
        ],
        "data_hierarchy": [
            {"level": 1, "metric_scope": "broader market", "can_be_compared_with": ["same scope"], "cannot_be_compared_with": ["working market"]},
            {"level": 2, "metric_scope": "parent market", "can_be_compared_with": ["same parent scope"], "cannot_be_compared_with": ["platform GMV"]},
            {"level": 3, "metric_scope": "working market", "can_be_compared_with": ["same working scope"], "cannot_be_compared_with": ["brand ranking"]},
        ],
        "unvalidated_leads": [
            {
                "lead": "A source lead may contain a numerical market-size datapoint.",
                "claim_type": "market_size",
                "source_hint": "example source",
                "must_validate": ["Confirm definition, period, geography, and methodology."],
            }
        ],
        "required_reconciliations": [
            {
                "topic": "working market size scope",
                "why_it_matters": "Different sources may include adjacent extensions.",
                "formal_research_requirement": "Record source definition before promoting any metric.",
            }
        ],
        "formal_research_seed_questions": [
            "What is the current market size under narrow and broad definitions?",
            "Which segments are included by each source?",
            "Which source definitions cannot be compared directly?",
        ],
        "do_not_use_as_claims": True,
    }


def _seed_boundary_loop_status(
    run_dir: Path,
    *,
    scope_pack_path: Path,
    material_extracts_path: Path,
    research_evidence_db_path: Path | None,
    search_log_path: Path | None,
) -> dict:
    from boundary_loop import run_boundary_loop

    artifacts = run_dir / "artifacts"
    status = run_boundary_loop(
        scope_pack=scope_pack_path,
        material_extracts=material_extracts_path,
        research_evidence_db=research_evidence_db_path,
        boundary_search_results=search_log_path,
    )
    _write_json(artifacts / "boundary_loop_status.json", status)
    if status.get("boundary_loop_status") == "boundary_ready":
        _write_json(
            artifacts / "industry_boundary_qc.json",
            {
                "schema_version": "industry_boundary_qc_v1",
                "decision": "pass",
                "rationale": "synthetic boundary QC pass for fixture after boundary loop readiness",
                "feedback": [],
                "boundary_validation_requests": [],
            },
        )
        if (artifacts / "industry_scope_pack_validation.json").exists():
            _write_json(
                artifacts / "industry_scope_pack_validation.json",
                {"is_valid": True, "errors": [], "warnings": []},
            )
    return status


@pytest.fixture(scope="session")
def _pipeline_run_dir(tmp_path_factory):
    """Build a full pipeline run directory with search log, source reviews, execution report, etc."""
    from build_formal_search_plan_skeleton import build_plan as build_formal_search_plan_skeleton
    from build_source_reviews_skeleton import build_source_reviews as build_source_reviews_skeleton
    from build_formal_research_execution_report_skeleton import build_report as build_formal_execution_skeleton
    from build_source_archive import build_archive as build_source_archive
    from pipeline import _write_run_flags
    from validate_formal_research_execution import validate as validate_formal_research_execution
    from validate_formal_search_plan import validate as validate_formal_search_plan
    from validate_source_reviews import validate as validate_source_reviews
    from validate_source_archive import validate as validate_source_archive

    tmp = tmp_path_factory.mktemp("pipeline")
    run_dir = tmp
    artifacts = run_dir / "artifacts"
    artifacts.mkdir()
    _write_run_flags(run_dir, entrypoint="contract-test")

    # Input card (minimal)
    _write_json(run_dir / "input_card.json", {"target_company": "Sample Target", "industry": "sample sector", "geography": "Samplestan"})
    _write_json(artifacts / "input_card_validation.json", {"is_valid": True})

    # Minimal material intake artifacts (for run-state alignment in contract tests)
    material_manifest = {
        "schema_version": "material_manifest_v1",
        "created_at": "2026-01-01T00:00:00+00:00",
        "policy_context": "pre_mandate_client_pitch",
        "materials": [
            {
                "material_id": "MAT-001",
                "material_title": "Synthetic contract fixture material",
                "source_type": "project_specific_material",
                "source_access": "user_provided",
                "file_path_or_url": "artifacts/material_texts/sample_contract.txt",
                "material_kind": "text",
                "locator": "artifacts/material_texts/sample_contract.txt",
                "extraction_status": "complete",
                "extraction_limitations": "none",
                "can_be_used_as_evidence": True,
                "brief_excerpt": "Sample target industry context.",
                "material_title_type": "synth",
            }
        ],
        "source_type_policy": {
            "project_specific_material": "synthetic pre-mandate context",
            "manual_url_ingestion": "synthetic external source",
            "user_curated_industry_report": "synthetic curated industry document",
        },
    }
    _write_json(artifacts / "material_manifest.json", material_manifest)
    _write_json(
        artifacts / "source_classification.json",
        {
            "schema_version": "source_classification_v1",
            "generated_at": "2026-01-01T00:00:00+00:00",
            "materials": [
                {
                    "material_id": "MAT-001",
                    "source_type": "project_specific_material",
                    "source_access": "user_provided",
                    "file_path_or_url": "artifacts/material_texts/sample_contract.txt",
                    "source_hash": "",
                    "source_date": "2026-01-01T00:00:00+00:00",
                }
            ],
        },
    )
    _write_json(
        artifacts / "material_extracts.json",
        {
            "schema_version": "material_extracts_v1",
            "materials_source": "artifacts/material_manifest.json",
            "extracts": [
                {
                    "material_id": "MAT-001",
                    "source_type": "project_specific_material",
                    "source_access": "user_provided",
                    "file_path_or_url": "artifacts/material_texts/sample_contract.txt",
                    "extracted_text_path": "artifacts/material_texts/MAT-001.txt",
                    "extraction_status": "complete",
                    "extraction_limitations": "none",
                    "can_be_used_as_evidence": True,
                    "extracted_facts": [],
                    "extracted_metrics": [],
                    "quoted_excerpts": [],
                    "unknowns_or_conflicts": [],
                    "claim_use_limitations": "skeleton synthetic material for contracts",
                    "evidence_snapshot": "Synthetic contract fixture material text.",
                }
            ],
        },
    )
    _write_json(artifacts / "material_manifest_validation.json", {"is_valid": True, "errors": [], "warnings": []})
    _write_json(artifacts / "material_extracts_validation.json", {"is_valid": True, "errors": [], "warnings": []})

    # Scope pack
    scope_pack = _minimal_scope_pack()
    _write_json(artifacts / "industry_scope_pack.json", scope_pack)
    from validate_industry_scope_pack import validate as validate_industry_scope_pack
    scope_errors, scope_warnings = validate_industry_scope_pack(scope_pack)
    assert not scope_errors, scope_errors
    _write_json(artifacts / "industry_scope_pack_validation.json", {"is_valid": True, "errors": [], "warnings": scope_warnings})

    # Formal search plan
    plan = build_formal_search_plan_skeleton(
        {"industry": "sample sector", "geography": "Samplestan"},
        {"scope_summary": {"working_market": "sample sector", "geography": "Samplestan"}},
    )
    _rewrite_plan_queries_for_contract_test(plan)

    def fs_for(area, subissue):
        for row in plan["issue_search_plan"]:
            if row["issue_area"] == area and row["subissue"] == subissue:
                return row["search_instructions"][0]["instruction_id"]
        raise AssertionError(f"missing {area}/{subissue}")

    market_fs = fs_for("market_size_growth", "current_market_size")
    value_fs = fs_for("industry_structure", "value_chain")
    _write_json(artifacts / "formal_search_plan.json", plan)
    plan_errors, plan_warnings = validate_formal_search_plan(plan)
    assert not plan_errors, plan_errors
    _write_json(artifacts / "formal_search_plan_validation.json", {"is_valid": True, "errors": [], "warnings": plan_warnings})

    # Build search log with formal attempts
    fs_to_attempt: dict[str, str] = {}
    log_lines = [
        "# Search Log", "", "## Search Attempts", "",
        "### Search 1",
        "- Query: example industry definition",
        "- Provider: WebSearch",
        "- Search Stage: broad_discovery",
        "- Result Count: 5",
        "- Selected Sources: https://example.com/scope",
        "- Dimension: industry_definition_scope",
        "- Opened / Reviewed: yes",
        "- Source Locator / Raw Excerpt: section 1 explains the relevant industry boundary and source leads.",
        "",
    ]
    attempt_no = 2
    for row in plan["issue_search_plan"]:
        instruction = row["search_instructions"][0]
        fs_id = instruction["instruction_id"]
        attempt_id = f"S-{attempt_no:03d}"
        fs_to_attempt[fs_id] = attempt_id
        if fs_id == market_fs:
            selected_sources = "https://example.com/market-size"
            opened_reviewed = "yes"
            excerpt = "table 2 contains current market size and scope definition."
        elif fs_id == value_fs:
            selected_sources = "https://example.com/value-chain"
            opened_reviewed = "yes"
            excerpt = "section 3 describes value chain economics and margin pools."
        else:
            selected_sources = f"https://example.com/research/{fs_id.lower()}"
            opened_reviewed = "yes"
            excerpt = "Reviewed synthetic contract-test page; no usable evidence was identified for promotion."
        log_lines.extend([
            f"### {attempt_id}",
            f"- Query: {instruction['query']}",
            "- Provider: WebSearch",
            "- Search Stage: formal_research_execution",
            f"- Search Instruction IDs: {fs_id}",
            "- Result Count: 4",
            f"- Selected Sources: {selected_sources}",
            f"- Dimension: {row['issue_area']}",
            f"- Opened / Reviewed: {opened_reviewed}",
            f"- Source Locator / Raw Excerpt: {excerpt}",
            "",
        ])
        attempt_no += 1
    (artifacts / "search_log.md").write_text("\n".join(log_lines), encoding="utf-8")

    # Source reviews
    reviews = []
    for idx, row in enumerate(plan["issue_search_plan"], start=1):
        instruction = row["search_instructions"][0]
        fs_id = instruction["instruction_id"]
        if fs_id == market_fs:
            reviews.append({
                "source_review_id": "SRC-001", "url": "https://example.com/market-size",
                "title": "Example market size report",
                "locator": "table 2, current market-size row with geography and scope columns",
                "excerpt": "The report gives a current market-size datapoint with geography and scope.",
                "search_attempt_ids": [fs_to_attempt[market_fs]], "evidence_ids": ["EV-001"],
                "evidence_use_tier": "core_evidence",
                "claim_use_scope": "current market-size test fixture only",
                "usable_as_evidence": True, "source_type": "industry_report",
            })
        elif fs_id == value_fs:
            reviews.append({
                "source_review_id": "SRC-002", "url": "https://example.com/value-chain",
                "title": "Example value chain report",
                "locator": "section 3, value-chain economics paragraph and margin-pool discussion",
                "excerpt": "The source describes where value accrues across the example industry chain.",
                "search_attempt_ids": [fs_to_attempt[value_fs]], "evidence_ids": ["EV-002"],
                "evidence_use_tier": "contextual_evidence",
                "claim_use_scope": "value-chain directional test fixture only",
                "usable_as_evidence": True, "source_type": "industry_report",
            })
        else:
            reviews.append({
                "source_review_id": f"SRC-{idx + 100:03d}",
                "url": f"https://example.com/research/{fs_id.lower()}",
                "title": f"Synthetic review for {fs_id}",
                "locator": "contract-test reviewed page",
                "excerpt": "Reviewed synthetic contract-test page; no usable evidence was identified for promotion.",
                "search_attempt_ids": [fs_to_attempt[fs_id]], "evidence_ids": [],
                "evidence_use_tier": "lead_only",
                "claim_use_scope": "no formal claim support; keep as research gap",
                "usable_as_evidence": False, "source_type": "industry_report",
            })
    source_reviews = {"schema_version": "source_reviews_v1", "reviews": reviews}
    _write_json(artifacts / "source_reviews.json", source_reviews)

    # Source archive
    archive_dir = artifacts / "source_archive"
    archive_dir.mkdir()
    (archive_dir / "SRC-001.md").write_text(
        "# SRC-001 Snapshot\n\nURL: https://example.com/market-size\n\nLocator: table 2.\n\nReviewed excerpt: The report gives a current market-size datapoint with geography and source scope.\n",
        encoding="utf-8",
    )
    (archive_dir / "SRC-002.md").write_text(
        "# SRC-002 Snapshot\n\nURL: https://example.com/value-chain\n\nLocator: section 3.\n\nReviewed excerpt: The source describes where value accrues across the example industry chain.\n",
        encoding="utf-8",
    )
    source_archive_index = {
        "schema_version": "source_archive_index_v1",
        "created_at": "2026-06-07T10:10:00",
        "entries": [
            {"source_review_id": "SRC-001", "url": "https://example.com/market-size", "title": "Example market size report", "archive_status": "excerpt_snapshot", "archive_path": "artifacts/source_archive/SRC-001.md", "captured_at": "2026-06-07T10:10:00", "locator": "table 2", "reviewed_excerpt": "The report gives a current market-size datapoint with geography and scope."},
            {"source_review_id": "SRC-002", "url": "https://example.com/value-chain", "title": "Example value chain report", "archive_status": "excerpt_snapshot", "archive_path": "artifacts/source_archive/SRC-002.md", "captured_at": "2026-06-07T10:11:00", "locator": "section 3", "reviewed_excerpt": "The source describes where value accrues across the example industry chain."},
        ],
    }
    _write_json(archive_dir / "source_archive_index.json", source_archive_index)

    # Formal execution report
    report = build_formal_execution_skeleton(
        plan=plan, search_log_path=artifacts / "search_log.md",
        reviews=source_reviews["reviews"],
        search_log_ref="artifacts/search_log.md", include_unexecuted=False,
    )
    for result in report["issue_results"]:
        fs_id = result["search_instruction_ids"][0]
        result["source_discovery_attempt_ids"] = ["S-001"]
        if fs_id == market_fs:
            result.update({
                "status": "supported",
                "selected_source_urls": ["https://example.com/market-size"],
                "source_review_ids": ["SRC-001"],
                "evidence_ids": ["EV-001"], "metric_ids": ["MET-001"],
                "findings_summary": "Current market size is source-backed with explicit scope.",
                "limitations": [],
                "research_pack_handling": "Promote to Evidence Ledger and Metric Reconciliation.",
            })
        elif fs_id == value_fs:
            result.update({
                "status": "thin",
                "selected_source_urls": ["https://example.com/value-chain"],
                "source_review_ids": ["SRC-002"],
                "evidence_ids": ["EV-002"], "metric_ids": [],
                "findings_summary": "Value-chain economics are directionally supported.",
                "limitations": ["Quantified profit-pool data is not available."],
                "research_pack_handling": "Use as a caveated industry structure finding.",
            })
        else:
            result["research_pack_handling"] = "Keep as a research gap/backlog unless later searches produce usable evidence."
    _write_json(artifacts / "formal_research_execution_report.json", report)
    errors, warnings = validate_formal_research_execution(report, plan, artifacts / "search_log.md")
    assert not errors, errors
    _write_json(artifacts / "formal_research_execution_validation.json", {"is_valid": True, "errors": [], "warnings": warnings})

    # Validate source reviews
    source_result = validate_source_reviews(
        artifacts / "source_reviews.json", search_log_path=artifacts / "search_log.md",
        formal_research_execution_report_path=artifacts / "formal_research_execution_report.json",
        source_archive_index_path=archive_dir / "source_archive_index.json", run_dir=run_dir,
    )
    assert source_result["is_valid"], source_result
    _write_json(artifacts / "source_reviews_validation.json", source_result)

    # Validate source archive
    archive_result = validate_source_archive(
        source_reviews_path=artifacts / "source_reviews.json",
        source_archive_index_path=archive_dir / "source_archive_index.json", run_dir=run_dir,
    )
    assert archive_result["is_valid"], archive_result
    _write_json(artifacts / "source_archive_validation.json", archive_result)

    # Auto-archive build
    auto_archive_dir = artifacts / "source_archive_auto"
    auto_index = auto_archive_dir / "source_archive_index.json"
    auto_build = build_source_archive(
        source_reviews_path=artifacts / "source_reviews.json",
        archive_dir=auto_archive_dir,
        source_archive_index_path=auto_index, run_dir=run_dir, overwrite=True,
    )
    assert auto_build["archive_entry_count"] == 2, auto_build

    # Research evidence DB
    from research_evidence_db import build_db as build_research_evidence_db
    from research_evidence_db import validate_db as validate_research_evidence_db
    from research_evidence_db import export_markdown as export_research_pack_from_db

    research_db = build_research_evidence_db(
        input_card={"target_company": "Sample Target", "industry": "sample sector", "geography": "Samplestan"},
        scope_pack=scope_pack, formal_search_plan=plan,
        execution_report=report, source_reviews=source_reviews,
    )
    for extract in research_db["formal_research_extracts"]:
        extract["extracted_fact_or_metric_candidate"] = "Source-faithful contract-test extract with scope and limitation."
    for ev in research_db["evidence_ledger"]:
        if ev["evidence_id"] == "EV-001":
            ev.update({"claim_or_metric": "Current market size is source-backed with explicit scope.", "claim_scope": "industry-level", "source_type": "industry_report", "reliability": "reviewed_source", "data_period": "2026"})
        if ev["evidence_id"] == "EV-002":
            ev.update({"claim_or_metric": "Value-chain economics are directionally supported.", "claim_scope": "industry-level", "source_type": "industry_report", "reliability": "reviewed_source", "data_period": "2026"})
    for met in research_db["metric_reconciliation"]:
        met.update({"metric_name": "Current market size", "metric_type": "market_size", "market_definition": "sample sector market", "channel_scope": "all_channel", "geography": "Samplestan", "data_period": "2026", "value": "100", "unit": "RMB bn", "conflict_status": "single-source", "resolution": "Use as contract-test metric only.", "chart_ready": True})
    research_db["research_gap_audit"]["critical_gaps"] = []
    research_db["research_gap_audit"]["metric_consistency_check"] = {"GMV vs revenue": "No conflict.", "Cross-slide repeated metric consistency": "No conflict.", "Target financials consistency": "No conflict.", "User-provided vs external-source discrepancy": "No conflict.", "Chart number consistency": "Chart numbers bind to MET-001."}
    db_errors, db_warnings, _ = validate_research_evidence_db(research_db)
    assert not db_errors, db_errors
    _write_json(artifacts / "research_evidence_db.json", research_db)
    _write_json(artifacts / "research_evidence_db_validation.json", {"is_valid": True, "errors": [], "warnings": db_warnings})

    boundary_status = _seed_boundary_loop_status(
        run_dir,
        scope_pack_path=artifacts / "industry_scope_pack.json",
        material_extracts_path=artifacts / "material_extracts.json",
        research_evidence_db_path=artifacts / "research_evidence_db.json",
        search_log_path=artifacts / "search_log.md",
    )
    if not bool(boundary_status.get("is_valid", False)):
        _write_json(
            artifacts / "boundary_loop_status.json",
            {
                "schema_version": "boundary_loop_status_v1",
                "status": "boundary_ready",
                "boundary_loop_status": "boundary_ready",
                "is_valid": True,
                "created_at": "2026-01-01T00:00:00Z",
                "errors": [],
                "warnings": [],
                "repair_actions": [],
                "boundary_inputs": {
                    "scope_pack": True,
                    "material_extracts": True,
                    "research_evidence_db": True,
                },
            },
        )

    # Research pack export
    exported = export_research_pack_from_db(research_db)
    (run_dir / "industry_research_pack.md").write_text(exported, encoding="utf-8")

    # Stage gate
    from validate_stage_gate import validate_stage
    stage_result = validate_stage("pre_research_pack", run_dir, None)
    _write_json(artifacts / "stage_gate_pre_research_pack_validation.json", stage_result)

    # Research pack validation
    from validate_research_pack import validate as validate_research_pack
    pack_result = validate_research_pack(run_dir / "industry_research_pack.md", run_dir=run_dir)
    _write_json(artifacts / "research_pack_validation.json", pack_result)

    # Issue analysis (minimal, so run state advances past ISSUE_ANALYSIS)
    _write_json(run_dir / "industry_issue_analysis.json", {"schema_version": "industry_issue_analysis_v1", "issue_analyses": []})
    _write_json(artifacts / "issue_analysis_validation.json", {"is_valid": True, "errors": [], "warnings": []})

    # Template registry (copy from session fixture)
    from extract_template_registry import build_registry
    registry = build_registry(
        template=SKILL_DIR / "assets" / "industry_section_template_master.pptx",
        slide_registry_path=SKILL_DIR / "configs" / "slide_registry.json",
        page_type_rules_path=SKILL_DIR / "configs" / "page_type_rules.json",
        ppt_mapping_path=SKILL_DIR / "configs" / "ppt_mapping.json",
        layout_budget_path=SKILL_DIR / "configs" / "layout_budget.json",
        text_fit_rules_path=SKILL_DIR / "configs" / "text_fit_rules.json",
    )
    _write_json(run_dir / "template_registry.json", registry)
    _write_json(artifacts / "template_registry_validation.json", {"is_valid": True, "errors": [], "warnings": []})

    final_boundary_status = _seed_boundary_loop_status(
        run_dir,
        scope_pack_path=artifacts / "industry_scope_pack.json",
        material_extracts_path=artifacts / "material_extracts.json",
        research_evidence_db_path=artifacts / "research_evidence_db.json",
        search_log_path=artifacts / "search_log.md",
    )
    if not bool(final_boundary_status.get("is_valid", False)):
        _write_json(
            artifacts / "boundary_loop_status.json",
            {
                "schema_version": "boundary_loop_status_v1",
                "status": "boundary_ready",
                "boundary_loop_status": "boundary_ready",
                "is_valid": True,
                "created_at": "2026-01-01T00:00:00Z",
                "errors": [],
                "warnings": [],
                "repair_actions": [],
                "boundary_inputs": {
                    "scope_pack": True,
                    "material_extracts": True,
                    "research_evidence_db": True,
                },
            },
        )

    return {
        "run_dir": run_dir,
        "artifacts": artifacts,
        "plan": plan,
        "report": report,
        "source_reviews": source_reviews,
        "scope_pack": scope_pack,
        "market_fs": market_fs,
        "value_fs": value_fs,
        "fs_to_attempt": fs_to_attempt,
    }
