"""Contract tests: research evidence DB and research pack.

Covers Groups 16d-16e from the monolith (lines 1204-1391).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1] / "runtime" / "ib-pitchdeck-agent-industry-section"
SCRIPT_DIR = SKILL_DIR / "scripts"
FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures"

sys.path.insert(0, str(SCRIPT_DIR))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run(args: list[str]) -> subprocess.CompletedProcess:
    env = {**__import__("os").environ, "PYTHONPATH": str(SCRIPT_DIR)}
    return subprocess.run(args, text=True, capture_output=True, cwd=str(SKILL_DIR), env=env)


def test_pre_research_pack_readiness_review_is_removed() -> None:
    from validate_artifact import ARTIFACT_PATHS

    assert "pre_research_pack" not in ARTIFACT_PATHS


def test_research_pack_missing_db_routes_repair_to_knowledge_db(tmp_path: Path) -> None:
    from validate_artifact import validate_artifact

    (tmp_path / "industry_research_pack.md").write_text("EV-001 placeholder export\n", encoding="utf-8")

    errors, warnings = validate_artifact("research_pack", tmp_path)

    assert warnings == []
    assert any("research pack is a derived export" in error for error in errors)
    assert any("Knowledge must author or repair the evidence DB first" in error for error in errors)
    assert not any("industry_boundary_qc" in error for error in errors)


def test_source_archive_validator_checks_compiled_entries_archive_paths(tmp_path: Path) -> None:
    from validate_artifact import validate_artifact

    archive_dir = tmp_path / "artifacts" / "source_archive"
    archive_dir.mkdir(parents=True)
    _write_json(
        archive_dir / "source_archive_index.json",
        {
            "schema_version": "source_archive_index_v1",
            "entries": [
                {
                    "source_review_id": "SRC-001",
                    "archive_status": "saved_text",
                    "archive_path": "artifacts/source_archive/missing.md",
                }
            ],
        },
    )

    errors, warnings = validate_artifact("source_archive", tmp_path)

    assert warnings == []
    assert any("archive file not found: artifacts/source_archive/missing.md" in error for error in errors)


class TestResearchEvidenceDB:
    def test_build_validate_export(self, _pipeline_run_dir):
        from research_evidence_db import build_db as build_research_evidence_db
        from research_evidence_db import validate_db as validate_research_evidence_db
        from research_evidence_db import export_markdown as export_research_pack_from_db
        artifacts = _pipeline_run_dir["artifacts"]
        report = json.loads((artifacts / "formal_research_execution_report.json").read_text(encoding="utf-8"))
        source_reviews = _pipeline_run_dir["embedded_reviews"]
        source_archive_index = json.loads((artifacts / "source_archive" / "source_archive_index.json").read_text(encoding="utf-8"))
        plan = json.loads((artifacts / "formal_search_plan.json").read_text(encoding="utf-8"))
        scope_pack = _pipeline_run_dir["scope_pack"]

        research_db = build_research_evidence_db(
            input_card={"target_company": "Sample Target", "industry": "sample sector", "geography": "Samplestan"},
            scope_pack=scope_pack, formal_search_plan=plan,
            execution_report=report, source_reviews=source_reviews,
            source_archive_index=source_archive_index,
        )
        # Fill extracts
        for extract in research_db["formal_research_extracts"]:
            extract["extracted_fact_or_metric_candidate"] = "Source-faithful contract-test extract with scope and limitation."
            extract["promoted_evidence_ids"] = list(extract.get("candidate_evidence_ids") or [])
            extract["promoted_metric_ids"] = list(extract.get("candidate_metric_ids") or [])
        source_by_id = {source["source_review_id"]: source for source in research_db["source_materials"]}
        ev_to_source = {}
        met_to_source = {}
        for extract in research_db["formal_research_extracts"]:
            for ev_id in extract.get("candidate_evidence_ids") or []:
                ev_to_source.setdefault(ev_id, extract["source_review_id"])
            for met_id in extract.get("candidate_metric_ids") or []:
                met_to_source.setdefault(met_id, extract["source_review_id"])
        research_db["evidence_ledger"] = [
            {
                "evidence_id": ev_id,
                "claim_or_metric": "Knowledge LLM promoted fixture claim.",
                "claim_scope": "industry-level",
                "source_review_id": src_id,
                "source_name": source_by_id[src_id]["source_name"],
                "source_url": source_by_id[src_id]["source_url"],
                "source_type": source_by_id[src_id]["source_type"],
                "evidence_status": "primary-reviewed",
                "source_date": source_by_id[src_id].get("source_date", ""),
                "data_period": "2026",
                "source_locator": source_by_id[src_id]["source_locator"],
                "raw_excerpt": source_by_id[src_id]["reviewed_excerpt"],
                "reliability": source_by_id[src_id]["source_reliability"],
                "confidence": "high",
            }
            for ev_id, src_id in sorted(ev_to_source.items())
        ]
        research_db["metric_reconciliation"] = [
            {
                "audit_level": "audited_metric",
                "metric_group": "Market sizing",
                "metric_id": met_id,
                "metric_name": "Knowledge LLM promoted fixture metric",
                "metric_type": "market_size",
                "market_definition": "sample sector market",
                "channel_scope": "all_channel",
                "geography": "Samplestan",
                "data_period": "2026",
                "value": "100",
                "unit": "RMB bn",
                "comparable_with": "",
                "parent_metric_id": "",
                "cagr_endpoint_ids": "",
                "conflict_status": "single-source",
                "resolution": "Use as contract-test metric only.",
                "chart_ready": True,
                "source_review_id": src_id,
                "source_name": source_by_id[src_id]["source_name"],
                "source_url": source_by_id[src_id]["source_url"],
                "source_type": source_by_id[src_id]["source_type"],
                "source_locator": source_by_id[src_id]["source_locator"],
                "raw_excerpt": source_by_id[src_id]["reviewed_excerpt"],
                "audit_note": "Contract fixture audit note; source locator and excerpt are inherited from SRC review.",
            }
            for met_id, src_id in sorted(met_to_source.items())
        ]
        # Fill evidence
        for ev in research_db["evidence_ledger"]:
            if ev["evidence_id"] == "EV-001":
                ev.update({
                    "claim_or_metric": "Current market size is source-backed with explicit scope.",
                    "claim_scope": "industry-level", "source_type": "industry_report",
                    "evidence_status": "primary-reviewed",
                    "reliability": "reviewed_source", "confidence": "high", "data_period": "2026",
                })
            if ev["evidence_id"] == "EV-002":
                ev.update({
                    "claim_or_metric": "Value-chain economics are directionally supported.",
                    "claim_scope": "industry-level", "source_type": "industry_report",
                    "evidence_status": "primary-reviewed",
                    "reliability": "reviewed_source", "confidence": "high", "data_period": "2026",
                })
            if ev["evidence_id"] == "EV-003":
                ev.update({
                    "claim_or_metric": "Market segmentation is source-backed with explicit segment basis.",
                    "claim_scope": "industry-level", "source_type": "industry_report",
                    "evidence_status": "primary-reviewed",
                    "reliability": "reviewed_source", "confidence": "high", "data_period": "2026",
                })
        # Fill metrics
        for met in research_db["metric_reconciliation"]:
            if met.get("metric_id") == "MET-002":
                met.update({
                    "audit_level": "audited_metric",
                    "metric_name": "Segment A share", "metric_type": "market_share",
                    "market_definition": "sample sector market", "channel_scope": "all_channel",
                    "geography": "Samplestan", "data_period": "2026",
                    "value": "45", "unit": "%",
                    "conflict_status": "single-source",
                    "resolution": "Use as contract-test segmentation metric only.", "chart_ready": True,
                    "audit_note": "Contract fixture audit note; source locator and excerpt are inherited from SRC review.",
                })
            else:
                met.update({
                    "audit_level": "audited_metric",
                    "metric_name": "Current market size", "metric_type": "market_size",
                    "market_definition": "sample sector market", "channel_scope": "all_channel",
                    "geography": "Samplestan", "data_period": "2026",
                    "value": "100", "unit": "RMB bn",
                    "conflict_status": "single-source",
                    "resolution": "Use as contract-test metric only.", "chart_ready": True,
                    "audit_note": "Contract fixture audit note; source locator and excerpt are inherited from SRC review.",
                })
        research_db["research_gap_audit"]["critical_gaps"] = []
        research_db["research_gap_audit"]["metric_consistency_check"] = {
            "GMV vs revenue": "No GMV/revenue conflict in contract fixture.",
            "Cross-slide repeated metric consistency": "Repeated metrics use MET-001 and MET-002 consistently.",
            "Target financials consistency": "No target financials in contract fixture.",
            "User-provided vs external-source discrepancy": "No discrepancy in contract fixture.",
            "Chart number consistency": "Chart numbers should bind to MET-001 and MET-002.",
        }
        for row in research_db.get("page_evidence_inventory", []):
            if row.get("fact_status") == "needs_knowledge_llm":
                has_promoted_support = bool(row.get("evidence_ids") or row.get("metric_ids"))
                row["fact_status"] = "sufficient" if has_promoted_support else "insufficient"

        # Validate
        db_errors, db_warnings, db_metrics = validate_research_evidence_db(research_db)
        assert not db_errors, db_errors
        assert db_metrics["evidence_ledger_row_count"] == 3, db_metrics
        assert db_metrics["metric_reconciliation_row_count"] == 2, db_metrics
        _write_json(artifacts / "research_evidence_db.json", research_db)
        _write_json(artifacts / "research_evidence_db_validation.json", {"is_valid": True, "errors": [], "warnings": db_warnings})

        # Export
        exported = export_research_pack_from_db(research_db)
        assert "Generated readable export" in exported, exported[:300]
        assert "## Evidence Notes" in exported
        assert "## Evidence Promotion Review" not in exported
        assert "Evidence Promotion Gate" not in exported
        assert "search plan Validation" not in exported
        assert "Registry-Defined Slide Structure Preserved" not in exported
        assert "LLM definition draft" not in exported
        assert "Project Classification:" not in exported
        assert "Working Market:" not in exported
        assert "Parent Market:" not in exported
        assert "Broader Market:" not in exported
        assert "Focused Category:" in exported
        assert "Relevant Broader Category:" in exported
        assert "Recommended `Fact Status`" not in exported
        assert "Evidence Use Tier" not in exported
        assert "Usable As Evidence" not in exported
        assert "Evidence Status" not in exported
        assert "Chart Ready" not in exported
        assert "Audit Level" not in exported
        assert "CAGR Endpoint IDs" not in exported
        assert "## Metric Reconciliation" not in exported
        assert "Claim Use Scope" not in exported
        assert "| Source ID | Source Name | Type | Date / Geography | URL / Path | Locator | Reviewed Excerpt | Source Use Notes |" in exported
        assert "## Research Execution Summary" in exported
        assert "## Source Extracts" in exported
        assert "## Metric Audit Table" in exported
        assert "Exhibit Use" in exported
        assert "usable in sourced exhibit" in exported
        assert "Metric Evidence Level" in exported
        assert "| EV-001 | Current market size" in exported, exported[:4000]

    def test_export_validates_without_chart_ready_warning(self, _pipeline_run_dir):
        from validate_artifact import validate_artifact
        artifacts = _pipeline_run_dir["artifacts"]
        errors, warnings = validate_artifact("research_pack", _pipeline_run_dir["run_dir"])
        result = {"is_valid": not errors, "errors": errors, "warnings": warnings}
        assert result["is_valid"], result
        assert not any("chart_ready flags" in w for w in result["warnings"]), result
