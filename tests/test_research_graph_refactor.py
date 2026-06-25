from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import _minimal_scope_pack, _rewrite_plan_queries_for_contract_test
from ib_research_graph import build_formal_search_plan, compile_graph_state, init_graph_state, normalize_metric_row
from research_evidence_db import build_db as build_research_evidence_db
from research_evidence_db import export_markdown as export_research_pack_from_db
from research_evidence_db import validate_db as validate_research_evidence_db
from validate_artifact import validate_artifact


def test_unit_normalizer_converts_chinese_and_absolute_rmb_units() -> None:
    chinese_row, chinese_audit = normalize_metric_row({"metric_id": "MET-001", "value": "107.78", "unit": "亿元"})
    assert chinese_audit["converted"] is True
    assert chinese_row["value"] == "10.778"
    assert chinese_row["unit"] == "RMB bn"
    assert chinese_row["original_value"] == "107.78"
    assert chinese_row["original_unit"] == "亿元"

    embedded_unit_row, embedded_unit_audit = normalize_metric_row({"metric_id": "MET-001A", "value": "107.78亿元", "unit": ""})
    assert embedded_unit_audit["converted"] is True
    assert embedded_unit_row["value"] == "10.778"
    assert embedded_unit_row["unit"] == "RMB bn"

    absolute_row, absolute_audit = normalize_metric_row({"metric_id": "MET-002", "value": "10597428522.23", "unit": "CNY"})
    assert absolute_audit["converted"] is True
    assert absolute_row["value"] == "10.597"
    assert absolute_row["unit"] == "RMB bn"

    percent_row, percent_audit = normalize_metric_row({"metric_id": "MET-003", "value": "45.5", "unit": "%"})
    assert percent_audit["converted"] is False
    assert percent_row["value"] == "45.5"
    assert percent_row["unit"] == "%"


def test_research_graph_compiles_valid_legacy_research_artifacts(tmp_path: Path) -> None:
    input_card = {
        "target_company": "Sample Target",
        "transaction_type": "control sale",
        "industry": "sample sector",
        "subsector": "sample subsector",
        "geography": "Samplestan",
        "language": "English",
        "research_as_of_date": "2026-01-01",
    }
    scope_pack = _minimal_scope_pack()
    plan = build_formal_search_plan(input_card, scope_pack)
    _rewrite_plan_queries_for_contract_test(plan, market="sample sector")
    state = init_graph_state(
        formal_search_plan=plan,
        input_card=input_card,
        scope_pack=scope_pack,
        worker_backend="open_deep_research_adapter",
    )
    first_unit = state["research_units"][0]
    assert first_unit["fs_ids"] == ["FS-001"]
    first_unit.update(
        {
            "status": "supported",
            "terminal_status": "executed_with_evidence",
            "downstream_permission": "may_support_claim",
            "findings_summary": "Reviewed source supports a current sample-sector market-size metric with explicit scope.",
            "limitations": ["Synthetic fixture; use only for compiler contract validation."],
            "attempts": [
                {
                    "query": "sample sector current market size official report",
                    "provider": "open_deep_research_adapter",
                    "selected_source_urls": ["https://example.com/report"],
                    "opened_reviewed": "yes",
                    "locator_excerpt": (
                        "Section 2 states the sample sector current market-size figure, scope, geography, "
                        "and methodology context used for this compiler fixture."
                    ),
                    "excerpt_origin": "opened_page",
                    "secondary_verification": "verified",
                    "secondary_verification_notes": "Research reopened the URL and matched the paragraph against the report fixture.",
                    "research_archive_status": "manual_verified_excerpt",
                }
            ],
            "sources": [
                {
                    "url": "https://example.com/report",
                    "title": "Example Sample Sector Report",
                    "source_type": "industry_report",
                    "archive_status": "manual_verified_excerpt",
                    "locator": "Section 2, market-size table and methodology paragraph",
                    "reviewed_excerpt": (
                        "The example report states that the sample sector reached 107.78亿元 in 2024, "
                        "with a defined geography, market boundary, and methodology note for audit."
                    ),
                    "usable_as_evidence": True,
                    "evidence_use_tier": "core_evidence",
                    "claim_use_scope": "industry-level market-size claim only",
                    "secondary_verification": "verified",
                    "verification_method": "manual_source_reviewed",
                    "secondary_verification_notes": "Research reopened the report fixture and matched the reviewed paragraph.",
                    "research_archive_status": "manual_verified_excerpt",
                    "raw_archive_content_type": "text/plain",
                    "raw_archive_text": (
                        "Full archived source text for the example report. Section 2 includes the current "
                        "market-size table, methodology note, geography, period, and market boundary. "
                        "This raw text is intentionally long enough to prove the graph compiler preserves "
                        "a reviewable raw archive alongside the faithful excerpt snapshot."
                    ),
                    "limitations": "Synthetic fixture for graph compiler contract testing.",
                }
            ],
            "evidence": [
                {
                    "claim_or_metric": "Sample sector market size reached 107.78亿元 in 2024 under the report's defined scope.",
                    "claim_scope": "industry-level",
                    "evidence_status": "primary-reviewed",
                    "source_locator": "Section 2, market-size table",
                    "raw_excerpt": (
                        "The example report states that the sample sector reached 107.78亿元 in 2024, "
                        "with a defined geography and methodology note for audit."
                    ),
                    "reliability": "reviewed_source",
                    "confidence": "high",
                    "data_period": "2024A",
                }
            ],
            "metrics": [
                {
                    "metric_group": "market_size_growth",
                    "audit_level": "audited_metric",
                    "metric_name": "Sample sector market size",
                    "metric_type": "market_size",
                    "market_definition": "sample sector working market",
                    "channel_scope": "all_channel",
                    "geography": "Samplestan",
                    "data_period": "2024A",
                    "value": "107.78",
                    "unit": "亿元",
                    "conflict_status": "single-source",
                    "resolution": "Use only with the report's stated scope and period.",
                    "chart_ready": True,
                    "audit_note": "Fixture metric is explicitly authorized as audited_metric for regression validation.",
                }
            ],
        }
    )
    context_unit = state["research_units"][1]
    context_unit.update(
        {
            "status": "thin",
            "terminal_status": "directional_only",
            "downstream_permission": "contextual_only",
            "findings_summary": "ODR-style reading produced useful background context but no audited metric.",
            "limitations": ["Context fixture only; not evidence for key figures."],
            "attempts": [
                {
                    "query": "sample sector channel shift background article",
                    "provider": "open_deep_research_adapter",
                    "selected_source_urls": ["https://example.com/context"],
                    "opened_reviewed": "yes",
                    "locator_excerpt": "Article background section describes sample-sector channel shifts without numeric evidence.",
                    "excerpt_origin": "opened_page",
                }
            ],
            "sources": [
                {
                    "url": "https://example.com/context",
                    "title": "Example Sample Sector Context Article",
                    "source_type": "industry_report",
                    "locator": "Background section",
                    "reviewed_excerpt": "The article describes directional sample-sector channel shifts but does not provide a key numeric datapoint for the deck.",
                    "summary": "Context-only background source.",
                }
            ],
            "research_context": [
                {
                    "topic": "Channel shift background",
                    "summary": "Directionally useful background, not a key metric or hard slide claim.",
                    "confidence": "medium",
                }
            ],
        }
    )

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    artifacts = run_dir / "artifacts"
    artifacts.mkdir()
    (artifacts / "formal_search_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    (artifacts / "research_graph_state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    result = compile_graph_state(state=state, formal_search_plan=plan, run_dir=run_dir)
    assert result["is_valid"] is True
    assert result["compiled_counts"]["attempts"] == 2
    assert result["compiled_counts"]["sources"] == 2
    assert result["compiled_counts"]["evidence_rows"] == 1
    assert result["compiled_counts"]["metric_rows"] == 1
    assert result["compiled_counts"]["research_context_rows"] == 1

    report = json.loads((artifacts / "formal_research_execution_report.json").read_text(encoding="utf-8"))
    execution_errors, execution_warnings = validate_artifact("formal_research_execution", run_dir)
    assert not execution_errors, execution_errors
    assert any("below minimum search coverage" in warning for warning in execution_warnings), execution_warnings
    assert not any("evidence-bearing FS rows" in warning for warning in execution_warnings), execution_warnings
    assert report["coverage_summary"]["planned_fs_rows"] == len(plan["issue_search_plan"])
    assert report["coverage_summary"]["actual_search_attempts"] == 2
    assert report["coverage_summary"]["fs_rows_executed_with_evidence"] == 1
    assert report["coverage_summary"]["fs_rows_not_executed"] == len(plan["issue_search_plan"]) - 2
    assert report["issue_results"][1]["terminal_status"] == "directional_only"
    assert isinstance(execution_warnings, list)

    archive_errors, archive_warnings = validate_artifact("source_archive", run_dir)
    assert not archive_errors, archive_errors
    assert isinstance(archive_warnings, list)
    archive_index = json.loads((artifacts / "source_archive" / "source_archive_index.json").read_text(encoding="utf-8"))
    archive_entry = archive_index["entries"][0]
    context_archive_entry = archive_index["entries"][1]
    assert archive_entry["archive_status"] == "manual_verified_excerpt"
    assert archive_entry["source_reliability"] == "needs_knowledge_llm_source_reliability"
    assert archive_entry["confidence"] == "needs_knowledge_llm_source_confidence"
    assert archive_entry["raw_archive_path"].startswith("artifacts/source_archive/raw/")
    assert (run_dir / archive_entry["raw_archive_path"]).exists()
    assert context_archive_entry["archive_status"] == "research_context"
    assert context_archive_entry["archive_path"] == ""

    research_db = build_research_evidence_db(
        input_card=input_card,
        scope_pack=scope_pack,
        formal_search_plan=plan,
        execution_report=report,
        source_reviews={},
        source_archive_index=archive_index,
    )
    state_evidence = first_unit["evidence"][0]
    state_metric, _ = normalize_metric_row(first_unit["metrics"][0])
    source = research_db["source_materials"][0]
    assert source["source_reliability"] == "needs_knowledge_llm_source_reliability"
    assert source["confidence"] == "needs_knowledge_llm_source_confidence"
    research_db["evidence_ledger"] = [
        {
            **state_evidence,
            "evidence_id": "EV-001",
            "source_review_id": source["source_review_id"],
            "source_name": source["source_name"],
            "source_url": source["source_url"],
            "source_type": source["source_type"],
            "source_locator": source["source_locator"],
            "raw_excerpt": source["reviewed_excerpt"],
            "reliability": "reviewed_source",
            "confidence": "high",
        }
    ]
    research_db["metric_reconciliation"] = [
        {
            **state_metric,
            "metric_id": "MET-001",
            "source_review_id": source["source_review_id"],
            "source_name": source["source_name"],
            "source_url": source["source_url"],
            "source_type": source["source_type"],
            "source_locator": source["source_locator"],
            "raw_excerpt": source["reviewed_excerpt"],
            "audit_note": "Fixture metric normalized and source-scoped.",
        }
    ]
    for extract in research_db["formal_research_extracts"]:
        extract["promoted_evidence_ids"] = list(extract.get("candidate_evidence_ids") or [])
        extract["promoted_metric_ids"] = list(extract.get("candidate_metric_ids") or [])
        if extract.get("candidate_evidence_ids"):
            extract["extracted_fact_or_metric_candidate"] = state_evidence["claim_or_metric"]
        elif extract.get("candidate_metric_ids"):
            extract["extracted_fact_or_metric_candidate"] = state_metric["metric_name"]
        else:
            extract["extracted_fact_or_metric_candidate"] = "Context-only source reviewed; no promoted EV/MET row."
    research_db["research_gap_audit"]["critical_gaps"] = [
        item for item in research_db["research_gap_audit"].get("critical_gaps", []) if "TODO" not in item
    ]
    research_db["research_gap_audit"]["deliverable_constraint"] = "evidence_limited_outline_only"
    research_db["research_gap_audit"]["evidence_limited_rationale"] = (
        "Compiler contract fixture intentionally has one evidence row and one metric row; "
        "it validates DB honesty but cannot support formal client-ready generation."
    )
    research_db["research_gap_audit"]["metric_consistency_check"] = {
        "GMV vs revenue": "Not applicable in graph refactor fixture.",
        "Cross-slide repeated metric consistency": "MET-001 is unique and source scoped.",
        "Target financials consistency": "No target financials promoted.",
        "User-provided vs external-source discrepancy": "No user-provided conflicting metric.",
        "Chart number consistency": "Metric row preserves normalized and original values.",
    }
    (artifacts / "research_evidence_db.json").write_text(json.dumps(research_db, ensure_ascii=False, indent=2), encoding="utf-8")
    db_errors, _db_warnings, db_metrics = validate_research_evidence_db(research_db)
    assert not db_errors, db_errors
    assert db_metrics["evidence_ledger_row_count"] == 1
    assert db_metrics["metric_reconciliation_row_count"] == 1
    metric = research_db["metric_reconciliation"][0]
    assert metric["value"] == "10.778"
    assert metric["unit"] == "RMB bn"
    assert metric["original_value"] == "107.78"
    assert metric["original_unit"] == "亿元"
    assert metric["audit_level"] == "audited_metric"
    assert metric["source_locator"] == "Section 2, market-size table and methodology paragraph"
    assert research_db["research_context"][0]["audit_level"] == "research_context"
    assert research_db["research_context"][0]["confidence"] == "unreviewed"

    (run_dir / "industry_research_pack.md").write_text(export_research_pack_from_db(research_db), encoding="utf-8")
    pack = (run_dir / "industry_research_pack.md").read_text(encoding="utf-8")
    assert "EV-001" in pack
    assert "MET-001" in pack
    assert "RMB bn" in pack
    assert "## Research Context" in pack


def test_research_graph_does_not_synthesize_attempts_for_untraced_evidence(tmp_path: Path) -> None:
    input_card = {"industry": "sample sector", "geography": "Samplestan"}
    scope_pack = _minimal_scope_pack()
    plan = build_formal_search_plan(input_card, scope_pack)
    state = init_graph_state(formal_search_plan=plan, input_card=input_card, scope_pack=scope_pack)
    first_unit = state["research_units"][0]
    first_unit.update(
        {
            "status": "supported",
            "terminal_status": "executed_with_evidence",
            "findings_summary": "This should not promote because no executed attempt exists.",
            "sources": [
                {
                    "url": "https://example.com/untraced",
                    "title": "Untraced source",
                    "source_type": "industry_report",
                    "archive_status": "manual_verified_excerpt",
                    "locator": "section 1",
                    "reviewed_excerpt": "A source-looking excerpt exists but there is no attempt trace, so it cannot become evidence.",
                    "usable_as_evidence": True,
                    "secondary_verification": "verified",
                    "verification_method": "manual_source_reviewed",
                    "secondary_verification_notes": "This fixture intentionally omits attempts.",
                    "research_archive_status": "manual_verified_excerpt",
                }
            ],
            "evidence": [{"claim_or_metric": "Untraced source-backed claim."}],
            "metrics": [{"metric_name": "Untraced metric", "value": "1", "unit": "RMB bn"}],
        }
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    artifacts = run_dir / "artifacts"
    artifacts.mkdir()

    result = compile_graph_state(state=state, formal_search_plan=plan, run_dir=run_dir)

    assert result["compiled_counts"]["attempts"] == 0
    assert result["compiled_counts"]["sources"] == 0
    assert result["compiled_counts"]["evidence_rows"] == 0
    assert result["compiled_counts"]["metric_rows"] == 0
    report = json.loads((artifacts / "formal_research_execution_report.json").read_text(encoding="utf-8"))
    assert report["issue_results"][0]["terminal_status"] == "not_executed"
    assert report["issue_results"][0]["search_attempt_ids"] == []
    assert "attempt" in report["issue_results"][0]["limitations"][0].lower()


def test_research_graph_requires_explicit_evidence_authorization(tmp_path: Path) -> None:
    input_card = {"industry": "sample sector", "geography": "Samplestan"}
    scope_pack = _minimal_scope_pack()
    plan = build_formal_search_plan(input_card, scope_pack)
    state = init_graph_state(formal_search_plan=plan, input_card=input_card, scope_pack=scope_pack)
    first_unit = state["research_units"][0]
    first_unit.update(
        {
            "attempts": [
                {
                    "query": "sample sector market size report",
                    "provider": "contract_fixture",
                    "selected_source_urls": ["https://example.com/candidate"],
                    "opened_reviewed": "yes",
                    "locator_excerpt": "Candidate source was opened, but Research did not authorize downstream evidence use.",
                }
            ],
            "sources": [
                {
                    "url": "https://example.com/candidate",
                    "title": "Candidate source",
                    "source_type": "industry_report",
                    "archive_status": "manual_verified_excerpt",
                    "locator": "section 1 candidate metric",
                    "reviewed_excerpt": "Candidate excerpt mentions a metric, but this fixture omits explicit evidence authorization.",
                    "usable_as_evidence": True,
                    "secondary_verification": "verified",
                    "verification_method": "manual_source_reviewed",
                    "secondary_verification_notes": "Fixture intentionally verifies capture but not downstream evidence permission.",
                    "research_archive_status": "manual_verified_excerpt",
                }
            ],
            "evidence": [{"claim_or_metric": "Candidate claim should not be promoted."}],
            "metrics": [{"metric_name": "Candidate metric", "value": "1", "unit": "RMB bn"}],
        }
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "artifacts").mkdir()

    compile_graph_state(state=state, formal_search_plan=plan, run_dir=run_dir)

    report = json.loads((run_dir / "artifacts" / "formal_research_execution_report.json").read_text(encoding="utf-8"))
    row = report["issue_results"][0]
    assert row["terminal_status"] == "executed_no_usable_source"
    assert row["status"] == "insufficient"
    assert row["evidence_ids"] == []
    assert row["metric_ids"] == []
    assert "explicit Research authorization is missing" in row["findings_summary"]


def test_non_evidence_terminal_cannot_keep_may_support_claim(tmp_path: Path) -> None:
    input_card = {"industry": "sample sector", "geography": "Samplestan"}
    scope_pack = _minimal_scope_pack()
    plan = build_formal_search_plan(input_card, scope_pack)
    state = init_graph_state(formal_search_plan=plan, input_card=input_card, scope_pack=scope_pack)
    first_unit = state["research_units"][0]
    first_unit.update(
        {
            "status": "thin",
            "terminal_status": "directional_only",
            "downstream_permission": "may_support_claim",
            "attempts": [
                {
                    "query": "sample sector directional background",
                    "provider": "contract_fixture",
                    "selected_source_urls": ["https://example.com/background"],
                    "opened_reviewed": "yes",
                    "locator_excerpt": "Directional context only; no explicit evidence authorization is made.",
                }
            ],
            "research_context": [
                {
                    "note": "Directional context should remain contextual only.",
                    "source_url": "https://example.com/background",
                }
            ],
        }
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "artifacts").mkdir()

    compile_graph_state(state=state, formal_search_plan=plan, run_dir=run_dir)

    report = json.loads((run_dir / "artifacts" / "formal_research_execution_report.json").read_text(encoding="utf-8"))
    row = report["issue_results"][0]
    assert row["terminal_status"] == "directional_only"
    assert row["downstream_permission"] == "contextual_only"


def test_saved_text_requires_explicit_capture_method(tmp_path: Path) -> None:
    input_card = {"industry": "sample sector", "geography": "Samplestan"}
    scope_pack = _minimal_scope_pack()
    plan = build_formal_search_plan(input_card, scope_pack)
    state = init_graph_state(formal_search_plan=plan, input_card=input_card, scope_pack=scope_pack)
    first_unit = state["research_units"][0]
    first_unit.update(
        {
            "status": "supported",
            "terminal_status": "executed_with_evidence",
            "downstream_permission": "may_support_claim",
            "attempts": [
                {
                    "query": "sample sector saved source",
                    "provider": "contract_fixture",
                    "selected_source_urls": ["https://example.com/saved"],
                    "opened_reviewed": "yes",
                    "locator_excerpt": "Source claims to be saved_text but omits capture_method.",
                }
            ],
            "sources": [
                {
                    "url": "https://example.com/saved",
                    "title": "Invalid saved source",
                    "source_type": "industry_report",
                    "archive_status": "saved_text",
                    "locator": "section 1",
                    "reviewed_excerpt": "This fixture should fail because saved_text needs an explicit capture_method.",
                    "usable_as_evidence": True,
                }
            ],
            "evidence": [{"claim_or_metric": "Invalid saved source should fail before compile."}],
        }
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "artifacts").mkdir()

    with pytest.raises(ValueError, match="capture_method"):
        compile_graph_state(state=state, formal_search_plan=plan, run_dir=run_dir)


def test_raw_archive_text_does_not_upgrade_to_saved_text(tmp_path: Path) -> None:
    input_card = {"industry": "sample sector", "geography": "Samplestan"}
    scope_pack = _minimal_scope_pack()
    plan = build_formal_search_plan(input_card, scope_pack)
    state = init_graph_state(formal_search_plan=plan, input_card=input_card, scope_pack=scope_pack)
    first_unit = state["research_units"][0]
    first_unit.update(
        {
            "status": "thin",
            "terminal_status": "directional_only",
            "downstream_permission": "contextual_only",
            "attempts": [
                {
                    "query": "sample sector source with raw text",
                    "provider": "contract_fixture",
                    "selected_source_urls": ["https://example.com/raw"],
                    "opened_reviewed": "yes",
                    "locator_excerpt": "Raw text was captured but not declared as a full saved source.",
                }
            ],
            "sources": [
                {
                    "url": "https://example.com/raw",
                    "title": "Raw captured source",
                    "source_type": "industry_report",
                    "locator": "section 1 raw capture",
                    "reviewed_excerpt": "Raw capture text is long enough to create a raw file, but it is not a full-page saved source.",
                    "raw_archive_content_type": "text/plain",
                    "raw_archive_text": " ".join(["raw source text"] * 40),
                }
            ],
        }
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "artifacts").mkdir()

    compile_graph_state(state=state, formal_search_plan=plan, run_dir=run_dir)

    archive = json.loads((run_dir / "artifacts" / "source_archive" / "source_archive_index.json").read_text(encoding="utf-8"))
    entry = archive["entries"][0]
    assert entry["raw_archive_path"].startswith("artifacts/source_archive/raw/")
    assert entry["archive_status"] != "saved_text"
    assert entry["archive_status"] in {"research_context", "needs_research_verification"}
