"""Contract tests: evidence candidates, research evidence DB, research pack, issue analysis skeleton.

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


class TestEvidenceCandidateSkeleton:
    def test_build_from_execution_report(self, _pipeline_run_dir):
        from build_evidence_candidate_skeleton import build_candidates as build_evidence_candidate_skeleton
        artifacts = _pipeline_run_dir["artifacts"]
        report = json.loads((artifacts / "formal_research_execution_report.json").read_text(encoding="utf-8"))
        source_reviews = json.loads((artifacts / "source_reviews.json").read_text(encoding="utf-8"))
        skeleton = build_evidence_candidate_skeleton(report, source_reviews)
        assert skeleton["evidence_candidates"], skeleton
        assert any(item["candidate_evidence_id"] == "EV-001" for item in skeleton["evidence_candidates"]), skeleton
        assert skeleton["metric_candidates"], skeleton
        assert skeleton["metric_candidates"][0]["promotion_decision"] == "pending_llm_review", skeleton


class TestStageGate:
    def test_pre_research_pack_gate_passes(self, _pipeline_run_dir):
        from validate_stage_gate import validate_stage
        artifacts = _pipeline_run_dir["artifacts"]
        result = validate_stage("pre_research_pack", _pipeline_run_dir["run_dir"], None)
        assert result["is_valid"], result
        _write_json(artifacts / "stage_gate_pre_research_pack_validation.json", result)


class TestResearchEvidenceDB:
    def test_build_validate_export(self, _pipeline_run_dir):
        from research_evidence_db import build_db as build_research_evidence_db
        from research_evidence_db import validate_db as validate_research_evidence_db
        from research_evidence_db import export_markdown as export_research_pack_from_db
        artifacts = _pipeline_run_dir["artifacts"]
        report = json.loads((artifacts / "formal_research_execution_report.json").read_text(encoding="utf-8"))
        source_reviews = json.loads((artifacts / "source_reviews.json").read_text(encoding="utf-8"))
        plan = json.loads((artifacts / "formal_search_plan.json").read_text(encoding="utf-8"))
        scope_pack = _pipeline_run_dir["scope_pack"]

        research_db = build_research_evidence_db(
            input_card={"target_company": "Sample Target", "industry": "sample sector", "geography": "Samplestan"},
            scope_pack=scope_pack, formal_search_plan=plan,
            execution_report=report, source_reviews=source_reviews,
        )
        # Fill extracts
        for extract in research_db["formal_research_extracts"]:
            extract["extracted_fact_or_metric_candidate"] = "Source-faithful contract-test extract with scope and limitation."
        # Fill evidence
        for ev in research_db["evidence_ledger"]:
            if ev["evidence_id"] == "EV-001":
                ev.update({
                    "claim_or_metric": "Current market size is source-backed with explicit scope.",
                    "claim_scope": "industry-level", "source_type": "industry_report",
                    "reliability": "reviewed_source", "data_period": "2026",
                })
            if ev["evidence_id"] == "EV-002":
                ev.update({
                    "claim_or_metric": "Value-chain economics are directionally supported.",
                    "claim_scope": "industry-level", "source_type": "industry_report",
                    "reliability": "reviewed_source", "data_period": "2026",
                })
        # Fill metrics
        for met in research_db["metric_reconciliation"]:
            met.update({
                "metric_name": "Current market size", "metric_type": "market_size",
                "market_definition": "sample sector market", "channel_scope": "all_channel",
                "geography": "Samplestan", "data_period": "2026",
                "value": "100", "unit": "RMB bn",
                "conflict_status": "single-source",
                "resolution": "Use as contract-test metric only.", "chart_ready": True,
            })
        research_db["research_gap_audit"]["critical_gaps"] = []
        research_db["research_gap_audit"]["metric_consistency_check"] = {
            "GMV vs revenue": "No GMV/revenue conflict in contract fixture.",
            "Cross-slide repeated metric consistency": "Repeated metrics use MET-001 only.",
            "Target financials consistency": "No target financials in contract fixture.",
            "User-provided vs external-source discrepancy": "No discrepancy in contract fixture.",
            "Chart number consistency": "Chart numbers should bind to MET-001.",
        }

        # Validate
        db_errors, db_warnings, db_metrics = validate_research_evidence_db(research_db)
        assert not db_errors, db_errors
        assert db_metrics["evidence_ledger_row_count"] == 2, db_metrics
        _write_json(artifacts / "research_evidence_db.json", research_db)
        _write_json(artifacts / "research_evidence_db_validation.json", {"is_valid": True, "errors": [], "warnings": db_warnings})

        # Export
        exported = export_research_pack_from_db(research_db)
        assert "Generated readable export" in exported, exported[:300]
        assert "| EV-001 | Current market size" in exported, exported[:4000]
        assert "Chart Ready" in exported, exported[:5000]

    def test_export_validates_without_chart_ready_warning(self, _pipeline_run_dir):
        from validate_research_pack import validate as validate_research_pack
        artifacts = _pipeline_run_dir["artifacts"]
        result = validate_research_pack(
            _pipeline_run_dir["run_dir"] / "industry_research_pack.md",
            run_dir=_pipeline_run_dir["run_dir"],
        )
        assert result["is_valid"], result
        assert not any("chart_ready flags" in w for w in result["warnings"]), result


class TestIssueAnalysisSkeleton:
    def test_skeleton_from_db_fails_validation(self, _pipeline_run_dir):
        """Issue analysis skeleton from DB should fail validation (has placeholder text)."""
        from build_issue_analysis_skeleton import build_issue_analysis_skeleton
        artifacts = _pipeline_run_dir["artifacts"]
        report = json.loads((artifacts / "formal_research_execution_report.json").read_text(encoding="utf-8"))
        research_db = json.loads((artifacts / "research_evidence_db.json").read_text(encoding="utf-8"))
        skeleton = build_issue_analysis_skeleton(None, report, research_db)
        assert skeleton["issue_analyses"], skeleton
        assert skeleton["issue_analyses"][0]["evidence_ids"], skeleton["issue_analyses"][0]
        skeleton_path = _pipeline_run_dir["run_dir"] / "industry_issue_analysis_skeleton.json"
        skeleton_path.write_text(json.dumps(skeleton, ensure_ascii=False, indent=2), encoding="utf-8")
        result = _run([
            sys.executable, "skills/qc/scripts/validators/reasoning/validate_issue_analysis.py",
            "--issue-analysis", str(skeleton_path),
            "--research-pack", str(_pipeline_run_dir["run_dir"] / "industry_research_pack.md"),
        ])
        assert result.returncode != 0, result.stdout
        assert "skeleton placeholder" in result.stdout, result.stdout
