"""Contract tests: Group 14 - final delivery issue-artifact gates and upstream failure propagation."""

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

from conftest import _minimal_scope_pack  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run(args: list[str]) -> subprocess.CompletedProcess:
    env = {**__import__("os").environ, "PYTHONPATH": str(SCRIPT_DIR)}
    return subprocess.run(args, text=True, capture_output=True, cwd=str(SKILL_DIR), env=env)


class TestFinalDeliveryIssueArtifacts:
    def test_catches_is_valid_false(self, deck_blueprint_path, template_registry_path, page_argument_pack_path, compiled_artifacts, tmp_path):
        """validate_issue_artifacts must catch is_valid=false on any downstream validation."""
        from validate_final_delivery import validate_issue_artifacts

        run_dir = tmp_path / "issue_artifact_run"
        artifacts = run_dir / "artifacts"
        artifacts.mkdir(parents=True)
        # Copy artifacts
        (run_dir / "industry_issue_analysis.json").write_text(
            (FIXTURES_DIR / "valid_issue_analysis.json").read_text(encoding="utf-8"), encoding="utf-8"
        )
        (run_dir / "template_registry.json").write_text(
            template_registry_path.read_text(encoding="utf-8"), encoding="utf-8"
        )
        (run_dir / "deck_blueprint.json").write_text(
            deck_blueprint_path.read_text(encoding="utf-8"), encoding="utf-8"
        )
        (run_dir / "page_evidence_contract.json").write_text(
            compiled_artifacts["page_evidence_contract"].read_text(encoding="utf-8"), encoding="utf-8"
        )
        (artifacts / "page_argument_pack.json").write_text(
            page_argument_pack_path.read_text(encoding="utf-8"), encoding="utf-8"
        )
        for name in (
            "issue_analysis_validation.json",
            "page_argument_pack_validation.json",
            "template_registry_validation.json",
            "deck_blueprint_validation.json",
            "page_evidence_contract_validation.json",
        ):
            _write_json(artifacts / name, {"is_valid": True, "error_count": 0})
        # Mark deck_blueprint as failed
        _write_json(artifacts / "deck_blueprint_validation.json", {"is_valid": False, "error_count": 1})
        errors, _ = validate_issue_artifacts(run_dir, [])
        assert "deck_blueprint_validation.json is_valid=false" in errors, errors

    def test_qc_warning_disposition_blocks_unresolved_warnings(self, tmp_path):
        from validate_final_delivery import _validate_qc_warning_disposition

        run_dir = tmp_path / "warning_run"
        artifacts = run_dir / "artifacts"
        artifacts.mkdir(parents=True)
        _write_json(
            artifacts / "content_quality_validation.json",
            {"is_valid": True, "warning_count": 1, "warnings": ["slide 1 layout warning"]},
        )
        _write_json(
            artifacts / "qc_warning_disposition.json",
            {
                "schema_version": "qc_warning_disposition_v1",
                "run_dir": str(run_dir),
                "generated_at": "2026-01-01T00:00:00Z",
                "warning_count": 1,
                "unresolved_warning_count": 1,
                "warnings": [
                    {
                        "warning_id": "WARN-001",
                        "source_issue_id": "QC-001",
                        "source_report": "artifacts/content_quality_validation.json",
                        "category": "template",
                        "layer": "template",
                        "artifact": "artifacts/content_quality_validation.json",
                        "field_path": "",
                        "message": "slide 1 layout warning",
                        "repair_owner": "template",
                        "disposition": "unresolved",
                        "requires_qc_disposition": True,
                        "downstream_blocked": True,
                        "downstream_limit": "Do not finalize affected page.",
                        "accepted_by": "",
                        "acceptance_rationale": "",
                        "rerun_command": "",
                    }
                ],
            },
        )

        errors, warnings, summary = _validate_qc_warning_disposition(run_dir, [], [])
        assert any("unresolved QC warning disposition" in error for error in errors), errors
        assert not warnings
        assert summary["unresolved_warning_count"] == 1


class TestUpstreamFailurePropagation:
    @pytest.fixture
    def bad_upstream_run(self, deck_blueprint_path, template_registry_path, page_argument_pack_path, tmp_path):
        """Create a run directory with failed source_archive_validation."""
        run_dir = tmp_path / "bad_upstream_run"
        artifacts = run_dir / "artifacts"
        artifacts.mkdir(parents=True)
        # Copy valid upstream artifacts
        for source, name in (
            (FIXTURES_DIR / "valid_issue_analysis.json", "industry_issue_analysis.json"),
            (template_registry_path, "template_registry.json"),
            (deck_blueprint_path, "deck_blueprint.json"),
        ):
            (run_dir / name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        (artifacts / "page_argument_pack.json").write_text(page_argument_pack_path.read_text(encoding="utf-8"), encoding="utf-8")
        (run_dir / "industry_research_pack.md").write_text("# Too Short\n", encoding="utf-8")
        for name in (
            "industry_scope_pack_validation.json",
            "formal_search_plan_validation.json",
            "formal_research_execution_validation.json",
            "stage_gate_pre_research_pack_validation.json",
            "research_evidence_db_validation.json",
            "research_pack_validation.json",
            "issue_analysis_validation.json",
            "hypothesis_store_validation.json",
            "page_argument_pack_validation.json",
            "deck_blueprint_validation.json",
            "template_registry_validation.json",
        ):
            _write_json(artifacts / name, {"is_valid": True, "error_count": 0})
        _write_json(artifacts / "industry_scope_pack.json", _minimal_scope_pack())
        _write_json(artifacts / "research_evidence_db.json", {"schema_version": "research_evidence_db_v1", "source_of_truth": True})
        _write_json(artifacts / "source_archive_validation.json", {"is_valid": False, "error_count": 1})
        return run_dir

    def test_research_pack_surfaces_failed_source_archive(self, bad_upstream_run):
        from validate_research_pack import validate as validate_research_pack
        result = validate_research_pack(bad_upstream_run / "industry_research_pack.md", run_dir=bad_upstream_run)
        assert any("source_archive_validation.json is_valid=false" in e for e in result["errors"]), result

    def test_issue_analysis_rejects_failed_source_archive(self, bad_upstream_run):
        result = _run([
            sys.executable, "scripts/qc/validators/reasoning/validate_issue_analysis.py",
            "--issue-analysis", str(bad_upstream_run / "industry_issue_analysis.json"),
            "--research-pack", str(bad_upstream_run / "industry_research_pack.md"),
        ])
        assert result.returncode != 0, "validate_issue_analysis must reject formal run with failed source_archive_validation"
        assert "source_archive_validation.json is_valid=false" in result.stdout + result.stderr

    def test_deck_blueprint_rejects_failed_source_archive(self, bad_upstream_run):
        result = _run([
            sys.executable, "scripts/qc/validators/generation/validate_deck_blueprint.py",
            "--page-argument-pack", str(bad_upstream_run / "artifacts/page_argument_pack.json"),
            "--issue-analysis", str(bad_upstream_run / "industry_issue_analysis.json"),
            "--deck-blueprint", str(bad_upstream_run / "deck_blueprint.json"),
            "--template-registry", str(bad_upstream_run / "template_registry.json"),
        ])
        assert result.returncode != 0, "validate_deck_blueprint must reject formal run with failed source_archive_validation"
        assert "source_archive_validation.json is_valid=false" in result.stdout + result.stderr

    def test_compile_rejects_failed_source_archive(self, bad_upstream_run):
        result = _run([
            sys.executable, "scripts/generation/compile_deck_blueprint.py",
            "--page-argument-pack", str(bad_upstream_run / "artifacts/page_argument_pack.json"),
            "--issue-analysis", str(bad_upstream_run / "industry_issue_analysis.json"),
            "--deck-blueprint", str(bad_upstream_run / "deck_blueprint.json"),
            "--template-registry", str(bad_upstream_run / "template_registry.json"),
            "--page-contract-output", str(bad_upstream_run / "page_evidence_contract.json"),
            "--renderer-spec-output", str(bad_upstream_run / "renderer_spec.json"),
        ])
        assert result.returncode != 0, "compile_deck_blueprint must reject formal run with failed source_archive_validation"
        assert "source_archive_validation.json is_valid=false" in result.stdout + result.stderr
