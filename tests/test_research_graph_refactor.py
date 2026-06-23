from __future__ import annotations

import json
from pathlib import Path

from conftest import _minimal_scope_pack, _rewrite_plan_queries_for_contract_test
from ib_research_graph import build_formal_search_plan, compile_graph_state, init_graph_state
from unit_normalizer import normalize_metric_row
from validate_formal_research_execution import validate as validate_formal_research_execution
from validate_research_evidence_db import validate_db as validate_research_evidence_db
from validate_source_archive import validate as validate_source_archive


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
    execution_errors, execution_warnings = validate_formal_research_execution(
        report,
        plan,
        artifacts / "search_log.md",
    )
    assert not execution_errors, execution_errors
    assert report["coverage_summary"]["planned_fs_rows"] == len(plan["issue_search_plan"])
    assert report["coverage_summary"]["actual_search_attempts"] == 2
    assert report["coverage_summary"]["fs_rows_executed_with_evidence"] == 1
    assert report["coverage_summary"]["fs_rows_not_executed"] == len(plan["issue_search_plan"]) - 2
    assert report["issue_results"][1]["terminal_status"] == "directional_only"
    assert any("80%+" in warning or "all formal" in warning for warning in execution_warnings)

    archive_validation = validate_source_archive(
        source_archive_index_path=artifacts / "source_archive" / "source_archive_index.json",
        run_dir=run_dir,
    )
    assert archive_validation["is_valid"] is True, archive_validation
    assert archive_validation["evidence_ready_archive_count"] == 1
    archive_index = json.loads((artifacts / "source_archive" / "source_archive_index.json").read_text(encoding="utf-8"))
    archive_entry = archive_index["entries"][0]
    context_archive_entry = archive_index["entries"][1]
    assert archive_entry["archive_status"] == "saved_text"
    assert archive_entry["raw_archive_path"].startswith("artifacts/source_archive/raw/")
    assert (run_dir / archive_entry["raw_archive_path"]).exists()
    assert context_archive_entry["archive_status"] == "research_context"
    assert context_archive_entry["archive_path"] == ""

    research_db = json.loads((artifacts / "research_evidence_db.json").read_text(encoding="utf-8"))
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

    pack = (run_dir / "industry_research_pack.md").read_text(encoding="utf-8")
    assert "EV-001" in pack
    assert "MET-001" in pack
    assert "RMB bn" in pack
    assert "## Research Context" in pack
