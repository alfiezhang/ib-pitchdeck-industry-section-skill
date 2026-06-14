"""Contract tests: Groups 7-8, 12 - renderer spec validation, page evidence contract validation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1] / "runtime" / "ib-pitchdeck-agent-industry-section"
SCRIPT_DIR = SKILL_DIR / "scripts"
FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    env = {**__import__("os").environ, "PYTHONPATH": str(SCRIPT_DIR)}
    return subprocess.run(args, text=True, capture_output=True, cwd=str(SKILL_DIR), env=env)


class TestPageEvidenceContractValidation:
    def test_valid_contract_passes(self, deck_blueprint_path, template_registry_path, compiled_artifacts):
        result = _run([
            sys.executable, "skills/qc/scripts/validators/generation/validate_page_evidence_contract.py",
            "--issue-analysis", str(FIXTURES_DIR / "valid_issue_analysis.json"),
            "--deck-blueprint", str(deck_blueprint_path),
            "--page-contract", str(compiled_artifacts["page_evidence_contract"]),
            "--output", str(compiled_artifacts["page_evidence_contract"].parent / "page_evidence_contract_validation.json"),
        ])
        assert result.returncode == 0, result.stdout + result.stderr

    def test_chart_forbidden_permission_blocks_contract(self, deck_blueprint_path, template_registry_path, tmp_path):
        """When issue analysis forbids charts, page evidence contract must fail."""
        issue = json.loads((FIXTURES_DIR / "valid_issue_analysis.json").read_text(encoding="utf-8"))
        for item in issue["issue_analyses"]:
            if item.get("analysis_id") == "IA-001":
                item["downstream_permission"]["chart_allowed"] = False
        bad_issue = tmp_path / "issue_analysis_chart_forbidden.json"
        bad_issue.write_text(json.dumps(issue, ensure_ascii=False, indent=2), encoding="utf-8")
        bad_contract = tmp_path / "page_evidence_contract_chart_forbidden.json"
        env = {**__import__("os").environ, "PYTHONPATH": str(SCRIPT_DIR)}
        subprocess.run(
            [sys.executable, "skills/generation/scripts/compile_deck_blueprint.py",
             "--issue-analysis", str(bad_issue),
             "--deck-blueprint", str(deck_blueprint_path),
             "--template-registry", str(template_registry_path),
             "--page-contract-output", str(bad_contract),
             "--renderer-spec-output", str(tmp_path / "renderer_spec_forbidden.json")],
            text=True, capture_output=True, cwd=str(SKILL_DIR), env=env, check=True,
        )
        result = _run([
            sys.executable, "skills/qc/scripts/validators/generation/validate_page_evidence_contract.py",
            "--issue-analysis", str(bad_issue),
            "--deck-blueprint", str(deck_blueprint_path),
            "--page-contract", str(bad_contract),
        ])
        assert result.returncode != 0, "page evidence contract must fail when chart proof metrics lack chart_allowed permission"
        assert "downstream_permission.chart_allowed" in result.stdout, result.stdout + result.stderr


class TestRendererSpecValidation:
    def test_valid_renderer_spec_passes(self, deck_blueprint_path, template_registry_path, compiled_artifacts, tmp_path):
        result = _run([
            sys.executable, "skills/qc/scripts/validators/generation/validate_renderer_spec.py",
            "--renderer-spec", str(compiled_artifacts["renderer_spec"]),
            "--template-registry", str(template_registry_path),
            "--deck-blueprint", str(deck_blueprint_path),
            "--page-contract", str(compiled_artifacts["page_evidence_contract"]),
            "--output", str(tmp_path / "renderer_spec_validation.json"),
        ])
        assert result.returncode == 0, result.stdout + result.stderr
