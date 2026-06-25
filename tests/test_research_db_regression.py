from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "runtime" / "ib-pitchdeck-agent-industry-section" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pipeline import _write_run_flags  # noqa: E402
from research_evidence_db import build_db, export_markdown, validate_db  # noqa: E402
from validate_artifact import validate_artifact  # noqa: E402


def minimal_research_db() -> dict:
    return {
        "schema_version": "research_evidence_db_v1",
        "source_of_truth": True,
        "meta": {
            "target_company": "Sample Target",
            "transaction_type": "control sale",
            "industry": "sample sector",
            "subsector": "sample subsector",
            "geography": "Sampleland",
            "language": "English",
            "prepared_date": "2026-06-09",
            "research_as_of_date": "2026-06-09",
        },
        "scope_summary": {
            "working_market": "sample market",
            "parent_market": "sample parent market",
            "sub_markets": ["sample product"],
            "excluded_scope": ["unrelated market"],
        },
        "formal_research_results": [
            {
                "result_id": "FR-001",
                "issue_area": "market_size_growth",
                "subissue": "current_market_size",
                "research_question": "What is the current market size?",
                "status": "supported",
                "terminal_status": "executed_with_evidence",
                "downstream_permission": "may_support_claim",
                "minimum_actual_searches": 1,
                "actual_search_attempt_count": 1,
                "search_instruction_ids": ["FS-001"],
                "search_attempt_ids": ["S-001"],
                "source_review_ids": ["SRC-001"],
                "evidence_ids": ["EV-001"],
                "metric_ids": ["MET-001"],
                "findings_summary": "Reviewed source supports sample market size.",
                "limitations": ["Contract fixture only."],
                "research_pack_handling": "Use as a fixture row.",
            }
        ],
        "formal_research_extracts": [
            {
                "extract_id": "FX-001",
                "result_id": "FR-001",
                "issue_area": "market_size_growth",
                "subissue": "current_market_size",
                "source_review_id": "SRC-001",
                "search_attempt_ids": ["S-001"],
                "source_url": "https://example.com/report",
                "source_locator": "section 1",
                "reviewed_excerpt_or_paraphrase": "The sample market was RMB 100bn in 2026.",
                "extracted_fact_or_metric_candidate": "Sample market size was RMB 100bn in 2026.",
                "status": "supported",
                "terminal_status": "executed_with_evidence",
                "promoted_evidence_ids": ["EV-001"],
                "promoted_metric_ids": ["MET-001"],
                "limitations": ["Contract fixture only."],
            }
        ],
        "source_materials": [
            {
                "source_review_id": "SRC-001",
                "source_name": "Example Industry Report",
                "source_type": "industry_report",
                "source_date": "2026-06-01",
                "geography": "Sampleland",
                "source_reliability": "high",
                "evidence_use_tier": "primary",
                "claim_use_scope": "industry-level",
                "usable_as_evidence": True,
                "source_url": "https://example.com/report",
                "source_locator": "section 1",
                "reviewed_excerpt": "The sample market was RMB 100bn in 2026.",
                "limitations": "Contract fixture only.",
                "archive_status": "manual_verified_excerpt",
                "archive_path": "artifacts/source_archive/SRC-001.md",
                "secondary_verification": "verified",
                "secondary_verification_notes": "Regression fixture manually verifies the excerpt against the source.",
            }
        ],
        "evidence_ledger": [
            {
                "evidence_id": "EV-001",
                "claim_or_metric": "Sample market size was RMB 100bn in 2026.",
                "claim_scope": "industry-level",
                "source_review_id": "SRC-001",
                "source_name": "Example Industry Report",
                "source_url": "https://example.com/report",
                "source_type": "industry_report",
                "evidence_status": "primary-reviewed",
                "source_date": "2026-06-01",
                "data_period": "2026",
                "source_locator": "section 1",
                "raw_excerpt": "The sample market was RMB 100bn in 2026.",
                "reliability": "high",
                "confidence": "high",
            }
        ],
        "metric_reconciliation": [
            {
                "audit_level": "audited_metric",
                "metric_group": "Market sizing",
                "metric_id": "MET-001",
                "metric_name": "Sample market size",
                "metric_type": "retail_sales",
                "market_definition": "sample market",
                "channel_scope": "all_channel",
                "geography": "Sampleland",
                "data_period": "2026",
                "value": "100",
                "unit": "RMB bn",
                "comparable_with": "",
                "parent_metric_id": "",
                "cagr_endpoint_ids": "",
                "conflict_status": "single-source",
                "resolution": "Use only as a contract fixture.",
                "chart_ready": True,
                "source_review_id": "SRC-001",
                "source_name": "Example Industry Report",
                "source_url": "https://example.com/report",
                "source_type": "industry_report",
                "source_locator": "section 1",
                "raw_excerpt": "The sample market was RMB 100bn in 2026.",
                "audit_note": "Contract fixture metric; use only as a regression fixture.",
            }
        ],
        "issue_fact_inventory": [
            {
                "issue_area": "market_size_growth",
                "subissue": "current_market_size",
                "evidence_ids": ["EV-001"],
                "metric_ids": ["MET-001"],
                "fact_status": "sufficient",
                "notes": "Fixture inventory row.",
            }
        ],
        "research_gap_audit": {
            "deliverable_constraint": "evidence_limited_outline_only",
            "evidence_limited_rationale": "Minimal regression fixture intentionally carries fewer rows than a formal client-ready research base.",
            "critical_gaps": [],
            "metric_consistency_check": {
                "GMV vs revenue": "No conflict.",
                "Cross-slide repeated metric consistency": "No repeated metric conflict.",
                "Target financials consistency": "No target financials.",
                "User-provided vs external-source discrepancy": "No discrepancy.",
                "Chart number consistency": "MET-001 is chart ready.",
            },
        },
    }


def test_research_db_export_validates_without_chart_ready_warning(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    db = minimal_research_db()
    errors, _, metrics = validate_db(db)
    assert errors == []
    assert metrics["metric_reconciliation_row_count"] == 1

    run_dir = tmp_path
    artifacts = run_dir / "artifacts"
    artifacts.mkdir()
    (artifacts / "research_evidence_db.json").write_text(json.dumps(db, ensure_ascii=False), encoding="utf-8")
    (artifacts / "research_evidence_db_validation.json").write_text(
        json.dumps({"is_valid": True, "errors": [], "warnings": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    pack = export_markdown(db)
    assert "Chart Ready" in pack
    (run_dir / "industry_research_pack.md").write_text(pack, encoding="utf-8")

    errors, warnings = validate_artifact("research_pack", run_dir)
    assert not errors, errors
    assert not any("chart_ready flags" in warning for warning in warnings)


def test_research_db_rejects_extract_promoted_evidence_source_mismatch() -> None:
    db = minimal_research_db()
    db["source_materials"].append(
        {
            **db["source_materials"][0],
            "source_review_id": "SRC-002",
            "source_name": "Second Source",
            "source_url": "https://example.com/second",
        }
    )
    db["formal_research_extracts"].append(
        {
            **db["formal_research_extracts"][0],
            "extract_id": "FX-002",
            "source_review_id": "SRC-002",
            "source_url": "https://example.com/second",
            "promoted_evidence_ids": ["EV-001"],
            "promoted_metric_ids": [],
        }
    )

    errors, _, _ = validate_db(db)

    assert any("promoted_evidence_id EV-001 belongs to source_review_id SRC-001, not SRC-002" in error for error in errors), errors


def test_research_db_warns_project_specific_audited_metric() -> None:
    db = minimal_research_db()
    db["source_materials"][0]["source_type"] = "project_specific_material"
    db["source_materials"][0]["source_access"] = "user_provided"
    db["metric_reconciliation"][0]["metric_name"] = "Target GMV"
    db["metric_reconciliation"][0]["metric_type"] = "target_traction"
    db["metric_reconciliation"][0]["source_type"] = "project_specific_material"

    errors, warnings, _ = validate_db(db)

    assert not errors, errors
    assert any("project-specific / management-provided target metrics cannot be promoted" in warning for warning in warnings), warnings


def test_build_db_keeps_multi_source_evidence_source_specific() -> None:
    execution_report = {
        "issue_results": [
            {
                "result_id": "FR-001",
                "issue_area": "market_size_growth",
                "subissue": "market_segmentation",
                "research_question": "Which categories are in scope?",
                "status": "supported",
                "terminal_status": "executed_with_evidence",
                "downstream_permission": "may_support_claim",
                "minimum_actual_searches": 1,
                "actual_search_attempt_count": 1,
                "search_instruction_ids": ["FS-001"],
                "search_attempt_ids": ["S-001"],
                "source_review_ids": ["SRC-A", "SRC-B"],
                "evidence_ids": ["EV-001", "EV-002"],
                "metric_ids": [],
                "findings_summary": "Two source-specific category facts were reviewed.",
                "limitations": ["Fixture only."],
                "research_pack_handling": "Use source-specific evidence only.",
            }
        ]
    }
    archive_index = {
        "entries": [
            {
                "source_review_id": "SRC-A",
                "url": "https://example.com/a",
                "title": "Source A",
                "source_type": "company_material",
                "archive_status": "manual_verified_excerpt",
                "archive_path": "artifacts/source_archive/SRC-A.md",
                "locator": "nav A",
                "reviewed_excerpt": "Source A supports category A.",
                "evidence_ids": ["EV-001"],
                "secondary_verification": "verified",
                "verification_method": "manual_source_reviewed",
                "secondary_verification_notes": "Fixture verifies source A.",
            },
            {
                "source_review_id": "SRC-B",
                "url": "https://example.com/b",
                "title": "Source B",
                "source_type": "company_material",
                "archive_status": "manual_verified_excerpt",
                "archive_path": "artifacts/source_archive/SRC-B.md",
                "locator": "nav B",
                "reviewed_excerpt": "Source B supports category B.",
                "evidence_ids": ["EV-002"],
                "secondary_verification": "verified",
                "verification_method": "manual_source_reviewed",
                "secondary_verification_notes": "Fixture verifies source B.",
            },
        ]
    }
    graph_state = {
        "research_units": [
            {
                "evidence": [
                    {
                        "evidence_id": "EV-001",
                        "source_review_id": "SRC-A",
                        "claim_or_metric": "Source A supports category A.",
                        "claim_scope": "industry-level",
                        "source_type": "company_material",
                        "evidence_status": "primary-reviewed",
                        "source_locator": "nav A",
                        "raw_excerpt": "Source A supports category A.",
                        "reliability": "official_source",
                        "confidence": "high",
                    },
                    {
                        "evidence_id": "EV-002",
                        "source_review_id": "SRC-B",
                        "claim_or_metric": "Source B supports category B.",
                        "claim_scope": "industry-level",
                        "source_type": "company_material",
                        "evidence_status": "primary-reviewed",
                        "source_locator": "nav B",
                        "raw_excerpt": "Source B supports category B.",
                        "reliability": "official_source",
                        "confidence": "high",
                    },
                ]
            }
        ]
    }

    db = build_db(
        input_card={"target_company": "Sample Target", "industry": "sample sector", "geography": "CN"},
        scope_pack={},
        formal_search_plan={"issue_search_plan": []},
        execution_report=execution_report,
        source_reviews={},
        source_archive_index=archive_index,
        research_graph_state=graph_state,
    )

    extracts = {row["source_review_id"]: row for row in db["formal_research_extracts"]}
    assert extracts["SRC-A"]["candidate_evidence_ids"] == ["EV-001"], extracts
    assert extracts["SRC-B"]["candidate_evidence_ids"] == ["EV-002"], extracts
    assert extracts["SRC-A"]["promoted_evidence_ids"] == []
    assert extracts["SRC-B"]["promoted_evidence_ids"] == []
    assert db["evidence_ledger"] == []


def test_pipeline_run_flags_written_for_formal_package(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    _write_run_flags(tmp_path, entrypoint="pytest")
    flags = json.loads((tmp_path / "artifacts" / "run_flags.json").read_text(encoding="utf-8"))
    assert flags["schema_version"] == "run_flags_v1"
    assert flags["research_gate"] == 1
    assert flags["banker_page_pack_layer"] == 1
    assert flags["debug_output_only"] is False


def test_build_db_keeps_unexecuted_fs_rows_out_of_extracts_and_evidence() -> None:
    execution_report = {
        "issue_results": [
            {
                "result_id": "FR-001",
                "issue_area": "market_size_growth",
                "subissue": "current_market_size",
                "research_question": "What is the current market size?",
                "status": "thin",
                "terminal_status": "executed_with_evidence",
                "downstream_permission": "may_support_claim",
                "minimum_actual_searches": 1,
                "actual_search_attempt_count": 1,
                "search_instruction_ids": ["FS-001"],
                "search_attempt_ids": ["S-001"],
                "source_review_ids": ["SRC-001"],
                "evidence_ids": ["EV-001"],
                "metric_ids": [],
                "findings_summary": "Reviewed source exists.",
                "limitations": ["Fixture only."],
                "research_pack_handling": "Promote after LLM extract review.",
            },
            {
                "result_id": "FR-002",
                "issue_area": "industry_structure",
                "subissue": "value_chain",
                "research_question": "How does the value chain work?",
                "status": "insufficient",
                "terminal_status": "not_executed",
                "downstream_permission": "research_backlog_only",
                "minimum_actual_searches": 1,
                "actual_search_attempt_count": 0,
                "search_instruction_ids": ["FS-002"],
                "search_attempt_ids": [],
                "source_review_ids": [],
                "evidence_ids": [],
                "metric_ids": [],
                "findings_summary": "Planned row was not searched.",
                "limitations": ["No actual S-xxx attempt."],
                "research_pack_handling": "Keep as research gap; do not promote.",
            },
        ]
    }
    db = build_db(
        input_card={"target_company": "Sample Target", "industry": "sample sector", "geography": "Sampleland"},
        scope_pack={"scope_summary": {"working_market": "sample market"}},
        formal_search_plan={"issue_search_plan": [{}, {}]},
        execution_report=execution_report,
        source_reviews={
            "source_reviews": [
                {
                    "source_review_id": "SRC-001",
                    "url": "https://example.com/report",
                    "title": "Example report",
                    "locator": "section 1",
                    "excerpt": "Reviewed source exists.",
                    "source_type": "industry_report",
                    "usable_as_evidence": True,
                    "evidence_use_tier": "core_evidence",
                    "claim_use_scope": "fixture only",
                }
            ]
        },
        source_archive_index={
            "schema_version": "source_archive_index_v1",
            "entries": [
                {
                    "source_review_id": "SRC-001",
                    "url": "https://example.com/report",
                    "title": "Example report",
                    "source_type": "industry_report",
                    "archive_status": "manual_verified_excerpt",
                    "archive_path": "artifacts/source_archive/SRC-001.md",
                    "locator": "section 1",
                    "reviewed_excerpt": "Reviewed source exists with enough source-faithful context for fixture evidence.",
                    "secondary_verification": "verified",
                    "verification_method": "manual_source_reviewed",
                    "secondary_verification_notes": "Fixture source excerpt was treated as research-verified.",
                    "research_archive_status": "manual_verified_excerpt",
                }
            ],
        },
    )
    assert [row["result_id"] for row in db["formal_research_extracts"]] == ["FR-001"], db["formal_research_extracts"]
    assert db["formal_research_extracts"][0]["candidate_evidence_ids"] == ["EV-001"]
    assert db["evidence_ledger"] == []
    assert any("FR-002" in item and "not_executed" in item for item in db["research_gap_audit"]["critical_gaps"])


def test_build_db_does_not_promote_unverified_excerpt_to_evidence() -> None:
    execution_report = {
        "issue_results": [
            {
                "result_id": "FR-001",
                "issue_area": "market_size_growth",
                "subissue": "current_market_size",
                "research_question": "What is the market size?",
                "status": "supported",
                "terminal_status": "executed_with_evidence",
                "downstream_permission": "may_support_claim",
                "minimum_actual_searches": 1,
                "actual_search_attempt_count": 1,
                "search_instruction_ids": ["FS-001"],
                "search_attempt_ids": ["S-001"],
                "source_review_ids": ["SRC-001"],
                "evidence_ids": ["EV-001"],
                "metric_ids": ["MET-001"],
                "findings_summary": "Source looked relevant but still needs Research verification.",
                "limitations": [],
                "research_pack_handling": "Do not promote until archive verification is complete.",
            }
        ]
    }
    db = build_db(
        input_card={"target_company": "Sample Target", "industry": "sample sector", "geography": "Sampleland"},
        scope_pack={"scope_summary": {"working_market": "sample market"}},
        formal_search_plan={"issue_search_plan": [{}]},
        execution_report=execution_report,
        source_reviews={"source_reviews": []},
        source_archive_index={
            "schema_version": "source_archive_index_v1",
            "entries": [
                {
                    "source_review_id": "SRC-001",
                    "url": "https://example.com/report",
                    "title": "Example report",
                    "source_type": "web_search_result",
                    "archive_status": "needs_research_verification",
                    "archive_path": "artifacts/source_archive/SRC-001.md",
                    "locator": "section 1",
                    "reviewed_excerpt": "Opened page excerpt exists but has not been verified after download failure.",
                    "archive_unavailable_reason": "Full source page was not downloaded; Research must verify.",
                }
            ],
        },
    )

    assert db["evidence_ledger"] == []
    assert db["metric_reconciliation"] == []
    assert any("Research must complete full-page archive or secondary verification" in item for item in db["research_gap_audit"]["critical_gaps"])
    inventory_row = next(
        row for row in db["issue_fact_inventory"]
        if row["issue_area"] == "market_size_growth" and row["subissue"] == "current_market_size"
    )
    assert inventory_row["fact_status"] == "insufficient"
    assert inventory_row["evidence_ids"] == []


def test_build_db_preserves_new_material_manifest_fields() -> None:
    db = build_db(
        input_card={"target_company": "Sample Target", "industry": "sample sector", "geography": "CN"},
        scope_pack={"scope_summary": {"working_market": "sample market"}},
        formal_search_plan={"issue_search_plan": []},
        execution_report={"issue_results": []},
        source_reviews={"source_reviews": []},
        material_manifest={
            "schema_version": "material_manifest_v1",
            "materials": [
                {
                    "material_id": "MAT-001",
                    "material_title": "User Brief",
                    "source_type": "project_specific_material",
                    "source_access": "user_provided",
                    "file_path_or_url": "inline_user_text",
                    "brief_excerpt": "Target sells base makeup products in China.",
                },
                {
                    "material_id": "MAT-002",
                    "material_title": "Curated Report",
                    "source_type": "user_curated_industry_report",
                    "source_access": "user_provided",
                    "file_path_or_url": "https://example.com/report",
                    "material_kind": "url",
                    "brief_excerpt": "Report excerpt.",
                },
            ],
        },
    )

    by_id = {row["material_id"]: row for row in db["source_materials"]}
    assert by_id["MAT-001"]["source_name"] == "User Brief"
    assert by_id["MAT-001"]["source_access_path"] == "inline_user_text"
    assert by_id["MAT-001"]["reviewed_excerpt"] == "Target sells base makeup products in China."
    assert by_id["MAT-002"]["source_url"] == "https://example.com/report"
