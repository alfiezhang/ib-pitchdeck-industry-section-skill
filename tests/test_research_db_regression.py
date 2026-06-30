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
        "page_evidence_inventory": [
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
            "research_gap_note": "Minimal regression fixture intentionally carries fewer rows than a formal final-delivery research base.",
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
    assert "Exhibit Use" in pack
    assert "Chart Ready" not in pack
    (run_dir / "industry_research_pack.md").write_text(pack, encoding="utf-8")

    errors, warnings = validate_artifact("research_pack", run_dir)
    assert not errors, errors
    assert not any("chart_ready flags" in warning for warning in warnings)


def test_research_db_preserves_natural_chinese_disclosure_status_without_warning() -> None:
    db = minimal_research_db()
    db["meta"]["target_company"] = ""
    db["meta"]["target_disclosure_status"] = "未披露项目"

    errors, warnings, _ = validate_db(db)

    assert errors == []
    assert not any("target_disclosure_status" in warning for warning in warnings)


def test_research_db_allows_unrecognized_disclosure_wording_without_enum_warning() -> None:
    db = minimal_research_db()
    db["meta"]["target_disclosure_status"] = "early conversation project"

    errors, warnings, _ = validate_db(db)

    assert errors == []
    assert not any("target_disclosure_status" in warning for warning in warnings)


def test_research_db_has_no_disclosure_keyword_classifier() -> None:
    runtime_text = (
        ROOT
        / "runtime"
        / "ib-pitchdeck-agent-industry-section"
        / "scripts"
        / "knowledge-repository"
        / "research_evidence_db.py"
    ).read_text(encoding="utf-8")

    assert "undisclosed_markers" not in runtime_text
    assert "disclosed_markers" not in runtime_text
    assert "any(marker in raw" not in runtime_text


def test_no_promoted_evidence_db_does_not_require_metric_consistency_template() -> None:
    db = {
        "schema_version": "research_evidence_db_v1",
        "source_of_truth": True,
        "meta": {
            "target_disclosure_status": "undisclosed",
            "transaction_type": "pre-mandate pitch",
            "industry": "sample sector",
            "geography": "Sampleland",
            "research_as_of_date": "2026-06-09",
        },
        "source_materials": [],
        "formal_research_results": [],
        "formal_research_extracts": [],
        "research_context": [],
        "evidence_ledger": [],
        "metric_reconciliation": [],
        "page_evidence_inventory": [
            {
                "issue_area": "market_size_growth",
                "subissue": "current_market_size",
                "evidence_ids": [],
                "metric_ids": [],
                "fact_status": "insufficient",
                "notes": "No source was strong enough to promote into an EV or MET row.",
            }
        ],
        "research_gap_audit": {
            "research_gap_note": (
                "Public and user-provided materials did not provide opened, source-located evidence strong enough "
                "to support a final-delivery industry claim."
            ),
            "deliverable_constraint": "research_required_before_deck",
            "critical_gaps": ["Find source-located public market evidence before rendering a final deck."],
        },
    }

    errors, warnings, metrics = validate_db(db)

    assert errors == []
    assert metrics["evidence_ledger_row_count"] == 0
    assert metrics["metric_reconciliation_row_count"] == 0
    assert any("no promoted EV rows" in warning for warning in warnings)


def test_no_promoted_evidence_db_accepts_natural_gap_audit() -> None:
    db = {
        "schema_version": "research_evidence_db_v1",
        "source_of_truth": True,
        "meta": {
            "target_disclosure_status": "undisclosed",
            "transaction_type": "pre-mandate pitch",
            "industry": "sample sector",
            "geography": "Sampleland",
            "research_as_of_date": "2026-06-09",
        },
        "source_materials": [],
        "formal_research_results": [],
        "formal_research_extracts": [],
        "research_context": [],
        "evidence_ledger": [],
        "metric_reconciliation": [],
        "page_evidence_inventory": [
            {
                "research_thread": "Market evidence readiness",
                "evidence_ids": [],
                "metric_ids": [],
                "fact_status": "insufficient",
                "notes": "Public sources were not source-located enough for final-delivery evidence.",
            }
        ],
        "research_gap_audit": {
            "critical_gaps": [
                "No opened public source currently supports the load-bearing market-size page. Route one bounded targeted research pass before final rendering."
            ],
            "optional_gaps": [],
            "metric_consistency_check": {},
        },
    }

    errors, warnings, metrics = validate_db(db)

    assert errors == []
    assert metrics["evidence_ledger_row_count"] == 0
    assert any("natural research_gap_audit" in warning for warning in warnings)
    assert any("no promoted EV rows" in warning for warning in warnings)


def test_no_promoted_evidence_gap_audit_does_not_require_keyword_match() -> None:
    db = {
        "schema_version": "research_evidence_db_v1",
        "source_of_truth": True,
        "meta": {
            "target_disclosure_status": "undisclosed",
            "transaction_type": "pre-mandate pitch",
            "industry": "sample sector",
            "geography": "Sampleland",
            "research_as_of_date": "2026-06-09",
        },
        "source_materials": [],
        "formal_research_results": [],
        "formal_research_extracts": [],
        "research_context": [],
        "evidence_ledger": [],
        "metric_reconciliation": [],
        "page_evidence_inventory": [
            {
                "research_thread": "Market evidence readiness",
                "evidence_ids": [],
                "metric_ids": [],
                "fact_status": "insufficient",
                "notes": "The available material is too thin for the proposed chart.",
            }
        ],
        "research_gap_audit": {
            "critical_gaps": [
                "The proposed exhibit should pause because the currently reviewed material is too narrow for the intended client page."
            ],
            "optional_gaps": [],
            "metric_consistency_check": {},
        },
    }

    errors, warnings, metrics = validate_db(db)
    runtime_text = (
        ROOT
        / "runtime"
        / "ib-pitchdeck-agent-industry-section"
        / "scripts"
        / "knowledge-repository"
        / "research_evidence_db.py"
    ).read_text(encoding="utf-8")

    assert errors == []
    assert metrics["evidence_ledger_row_count"] == 0
    assert any("natural research_gap_audit" in warning for warning in warnings)
    assert not any("should make the source limit or next evidence action explicit" in warning for warning in warnings)
    assert '"research" in combined_gap_text.lower()' not in runtime_text
    assert '"来源" in combined_gap_text' not in runtime_text


def test_build_db_defaults_no_evidence_decision_to_llm_required() -> None:
    db = build_db(
        input_card={"target_company": "Sample Target", "industry": "sample sector", "geography": "Sampleland"},
        scope_pack={"scope_summary": {"working_market": "sample market"}},
        formal_search_plan={"issue_search_plan": []},
        execution_report={"issue_results": []},
        source_reviews={"source_reviews": []},
    )

    gap_audit = db["research_gap_audit"]
    assert gap_audit["client_ready_evidence_decision"] == "llm_decision_required"
    assert any("bounded targeted research loop" in gap for gap in gap_audit["critical_gaps"])

    errors, _, _ = validate_db(db)
    assert any("candidate-workspace no-evidence prompt" in error for error in errors)
    assert any("Do not fabricate EV rows" in error for error in errors)


def test_no_evidence_delivery_constraint_uses_pause_language() -> None:
    source = (SCRIPT_DIR.parent / "scripts/knowledge-repository/research_evidence_db.py").read_text(encoding="utf-8")

    assert "block_client_ready_deck" not in source
    assert "final delivery should pause" in source


def test_page_evidence_inventory_allows_industry_specific_rows() -> None:
    db = minimal_research_db()
    db["page_evidence_inventory"][0]["research_thread"] = "Industry-specific channel economics"
    db["page_evidence_inventory"][0]["thread_focus"] = "Platform live-stream take rate"
    db["page_evidence_inventory"][0].pop("issue_area", None)
    db["page_evidence_inventory"][0].pop("subissue", None)

    errors, warnings, metrics = validate_db(db)

    assert errors == []
    assert metrics["page_evidence_inventory_row_count"] == 1
    assert not any("custom issue_area" in warning for warning in warnings)


def test_page_evidence_inventory_empty_warns_not_fails() -> None:
    db = minimal_research_db()
    db["page_evidence_inventory"] = []

    errors, warnings, metrics = validate_db(db)

    assert errors == []
    assert metrics["page_evidence_inventory_row_count"] == 0
    assert any("page_evidence_inventory is empty" in warning for warning in warnings)


def test_page_evidence_inventory_subjective_status_without_ids_warns_not_fails() -> None:
    db = minimal_research_db()
    db["page_evidence_inventory"][0]["fact_status"] = "thin"
    db["page_evidence_inventory"][0]["evidence_ids"] = []
    db["page_evidence_inventory"][0]["metric_ids"] = []

    errors, warnings, _ = validate_db(db)

    assert errors == []
    assert any("thin fact_status has no evidence_ids or metric_ids" in warning for warning in warnings)


def test_page_evidence_inventory_missing_thread_warns_not_fails() -> None:
    db = minimal_research_db()
    db["page_evidence_inventory"][0].pop("research_thread", None)
    db["page_evidence_inventory"][0].pop("topic", None)
    db["page_evidence_inventory"][0].pop("issue_area", None)

    errors, warnings, _ = validate_db(db)

    assert errors == []
    assert any("research_thread omitted" in warning for warning in warnings)


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


def test_research_db_warns_when_metric_explicitly_lacks_external_verification() -> None:
    db = minimal_research_db()
    db["source_materials"][0]["source_type"] = "project_specific_material"
    db["source_materials"][0]["source_access"] = "user_provided"
    db["metric_reconciliation"][0]["metric_name"] = "Target GMV"
    db["metric_reconciliation"][0]["metric_type"] = "target_traction"
    db["metric_reconciliation"][0]["source_type"] = "project_specific_material"
    db["metric_reconciliation"][0]["external_verification_status"] = "management_provided_only"

    errors, warnings, _ = validate_db(db)

    assert not errors, errors
    assert any("external verification is limited" in warning for warning in warnings), warnings


def test_research_db_does_not_classify_project_metric_from_names_or_scope_tokens() -> None:
    db = minimal_research_db()
    db["metric_reconciliation"][0]["metric_name"] = "Platform GMV for sample category"
    db["metric_reconciliation"][0]["metric_type"] = "target_traction"
    db["metric_reconciliation"][0]["source_type"] = "project_specific_material"
    db["source_materials"][0]["source_type"] = "project_specific_material"
    db["source_materials"][0]["source_access"] = "user_provided"

    errors, warnings, _ = validate_db(db)
    runtime_text = (
        ROOT
        / "runtime"
        / "ib-pitchdeck-agent-industry-section"
        / "scripts"
        / "knowledge-repository"
        / "research_evidence_db.py"
    ).read_text(encoding="utf-8")

    assert not errors, errors
    assert not any("external verification is limited" in warning for warning in warnings), warnings
    assert "PROJECT_SPECIFIC_METRIC_NAME_TOKENS" not in runtime_text
    assert "PROJECT_SPECIFIC_METRIC_SCOPE_VALUES" not in runtime_text
    assert "PROJECT_SPECIFIC_SOURCE_TYPES" not in runtime_text
    assert "project_specific_metric_source" not in runtime_text
    assert "metric_name for token" not in runtime_text


def test_research_db_allows_natural_language_claim_scope_without_enum_warning() -> None:
    db = minimal_research_db()
    db["evidence_ledger"][0]["claim_scope"] = (
        "China base-makeup category context only; not target-company verification or a full cosmetics market proxy"
    )

    errors, warnings, _ = validate_db(db)

    assert not errors, errors
    assert not any("claim_scope uses natural wording" in warning for warning in warnings), warnings


def test_research_db_rejects_placeholder_claim_scope() -> None:
    db = minimal_research_db()
    db["evidence_ledger"][0]["claim_scope"] = "needs_knowledge_llm_claim_scope"

    errors, _, _ = validate_db(db)

    assert any("claim_scope still contains placeholder text" in error for error in errors), errors


def test_research_db_allows_natural_language_evidence_status_without_enum_warning() -> None:
    db = minimal_research_db()
    db["evidence_ledger"][0]["evidence_status"] = "manual-reviewed official report excerpt"

    errors, warnings, _ = validate_db(db)

    assert not errors, errors
    assert not any("evidence_status uses natural wording" in warning for warning in warnings), warnings


def test_research_db_rejects_lead_only_evidence_status() -> None:
    db = minimal_research_db()
    db["evidence_ledger"][0]["evidence_status"] = "search_lead"

    errors, _, _ = validate_db(db)

    assert any("cannot be promoted into evidence_ledger" in error for error in errors), errors


def test_research_db_does_not_classify_evidence_status_by_substring_tokens() -> None:
    db = minimal_research_db()
    db["evidence_ledger"][0]["evidence_status"] = "reviewed source snippet summary from archived page"

    errors, warnings, _ = validate_db(db)
    runtime_text = (
        ROOT
        / "runtime"
        / "ib-pitchdeck-agent-industry-section"
        / "scripts"
        / "knowledge-repository"
        / "research_evidence_db.py"
    ).read_text(encoding="utf-8")

    assert not errors, errors
    assert not any("evidence_status uses natural wording" in warning for warning in warnings), warnings
    assert "NON_PROMOTABLE_EVIDENCE_STATUS_TOKENS" not in runtime_text
    assert "token in lowered_evidence_status" not in runtime_text


def test_research_db_does_not_classify_raw_excerpt_by_snippet_wording() -> None:
    db = minimal_research_db()
    db["evidence_ledger"][0]["raw_excerpt"] = "The report describes a snippet of surveyed market demand from reviewed pages."

    errors, _, _ = validate_db(db)
    runtime_text = (
        ROOT
        / "runtime"
        / "ib-pitchdeck-agent-industry-section"
        / "scripts"
        / "knowledge-repository"
        / "research_evidence_db.py"
    ).read_text(encoding="utf-8")

    assert not errors, errors
    assert "raw_excerpt looks like a search snippet" not in runtime_text
    assert "'snippet' in text(row.get(" not in runtime_text


def test_research_db_allows_natural_language_fact_status_without_enum_warning() -> None:
    db = minimal_research_db()
    db["page_evidence_inventory"][0]["fact_status"] = (
        "directionally supported by one reviewed source, but not enough for a headline"
    )

    errors, warnings, _ = validate_db(db)

    assert not errors, errors
    assert not any("fact_status uses natural wording" in warning for warning in warnings), warnings


def test_research_db_allows_missing_fact_status_with_warning() -> None:
    db = minimal_research_db()
    db["page_evidence_inventory"][0].pop("fact_status")

    errors, warnings, _ = validate_db(db)

    assert not errors, errors
    assert any("fact_status omitted" in warning for warning in warnings), warnings


def test_research_db_allows_omitted_subjective_review_labels_with_warnings() -> None:
    db = minimal_research_db()
    for field in ("evidence_status", "reliability", "confidence"):
        db["evidence_ledger"][0].pop(field)
    for field in ("conflict_status", "resolution"):
        db["metric_reconciliation"][0].pop(field)

    errors, warnings, _ = validate_db(db)

    assert not errors, errors
    assert any("evidence_status omitted" in warning for warning in warnings), warnings
    assert any("reliability omitted" in warning for warning in warnings), warnings
    assert any("confidence omitted" in warning for warning in warnings), warnings
    assert any("conflict_status omitted" in warning for warning in warnings), warnings
    assert any("resolution omitted" in warning for warning in warnings), warnings


def test_source_material_source_type_missing_warns_not_fails() -> None:
    db = minimal_research_db()
    db["source_materials"][0].pop("source_type", None)

    errors, warnings, _ = validate_db(db)

    assert errors == []
    assert any("source_materials.source_type omitted" in warning for warning in warnings), warnings


def test_research_db_metric_row_does_not_require_fixed_audit_level_label() -> None:
    db = minimal_research_db()
    db["metric_reconciliation"][0].pop("audit_level")

    errors, warnings, _ = validate_db(db)

    assert not errors, errors
    assert not any("audit_level is required" in warning for warning in warnings), warnings


def test_research_db_rejects_metric_row_explicitly_marked_context_only() -> None:
    db = minimal_research_db()
    db["metric_reconciliation"][0]["audit_level"] = "research_context"

    errors, _, _ = validate_db(db)

    assert any("context-only or unaudited numbers belong in research_context" in error for error in errors), errors


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
    inventory_row = next(
        row for row in db["page_evidence_inventory"]
        if row["research_thread"] == "market_size_growth" and row["thread_focus"] == "market_segmentation"
    )
    assert "issue_area" not in inventory_row
    assert "subissue" not in inventory_row
    assert inventory_row["fact_status"] == "needs_knowledge_llm"
    errors, warnings, _ = validate_db(db)
    assert any("candidate-workspace no-evidence prompt" in error for error in errors)
    assert any("fact_status still looks like a candidate workspace note" in warning for warning in warnings)


def test_pipeline_run_flags_written_for_formal_package(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    _write_run_flags(tmp_path, entrypoint="pytest")
    flags = json.loads((tmp_path / "artifacts" / "run_flags.json").read_text(encoding="utf-8"))
    assert flags["schema_version"] == "run_flags_v1"
    assert flags["research_readiness"] == 1
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
        row for row in db["page_evidence_inventory"]
        if row["research_thread"] == "market_size_growth" and row["thread_focus"] == "current_market_size"
    )
    assert "issue_area" not in inventory_row
    assert "subissue" not in inventory_row
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
