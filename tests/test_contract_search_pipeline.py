"""Contract tests: search log, scope pack, formal search plan, source reviews, execution report.

Covers Groups 16a-16c from the monolith (lines 798-1297).
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

from conftest import _rewrite_plan_queries_for_contract_test, _write_json, _minimal_scope_pack  # noqa: E402


def _run(args: list[str]) -> subprocess.CompletedProcess:
    env = {**__import__("os").environ, "PYTHONPATH": str(SCRIPT_DIR)}
    return subprocess.run(args, text=True, capture_output=True, cwd=str(SKILL_DIR), env=env)


# ---------------------------------------------------------------------------
# Scope pack
# ---------------------------------------------------------------------------


class TestScopePackValidation:
    def test_valid_scope_pack_passes(self):
        from validate_industry_scope_pack import validate as validate_industry_scope_pack
        scope = _minimal_scope_pack()
        errors, warnings = validate_industry_scope_pack(scope)
        assert not errors, errors

    def test_numeric_finding_in_scope_summary_rejected(self):
        from validate_industry_scope_pack import validate as validate_industry_scope_pack
        scope = json.loads(json.dumps(_minimal_scope_pack()))
        scope["scope_summary"]["working_market"] = "example market is 100亿元 and already validated"
        errors, _ = validate_industry_scope_pack(scope)
        assert any("numeric finding appears outside unvalidated_leads" in e for e in errors), errors

    def test_research_query_in_scoping_rejected(self):
        from validate_industry_scope_pack import validate as validate_industry_scope_pack
        scope = json.loads(json.dumps(_minimal_scope_pack()))
        scope["llm_definition_draft"]["scoping_search_queries"][0] = "example industry market size growth 2026"
        errors, _ = validate_industry_scope_pack(scope)
        assert any("broad discovery must validate definition/scope only" in e for e in errors), errors

    def test_no_gap_scope_passes(self):
        from validate_industry_scope_pack import validate as validate_industry_scope_pack
        scope = json.loads(json.dumps(_minimal_scope_pack()))
        scope["ambiguous_boundaries"] = []
        scope["required_reconciliations"] = []
        scope["scope_confidence_rationale"] = "No material category boundary ambiguity was identified from the brief at scoping stage."
        scope["reconciliation_policy"] = "No material metric-scope conflict was identified at scoping stage; formal research will still record source definitions."
        errors, _ = validate_industry_scope_pack(scope)
        assert not errors, errors

    def test_missing_policy_fields_rejected(self):
        from validate_industry_scope_pack import validate as validate_industry_scope_pack
        scope = json.loads(json.dumps(_minimal_scope_pack()))
        scope["ambiguous_boundaries"] = []
        scope["required_reconciliations"] = []
        scope["scope_confidence_rationale"] = ""
        scope["reconciliation_policy"] = ""
        errors, _ = validate_industry_scope_pack(scope)
        assert any("scope_confidence_rationale" in e for e in errors), errors
        assert any("reconciliation_policy" in e for e in errors), errors


# ---------------------------------------------------------------------------
# Search log and attempts
# ---------------------------------------------------------------------------


class TestSearchLogAndAttempts:
    def test_auto_search_log(self, tmp_path):
        from validate_formal_research_execution import parse_search_attempts
        search_log = tmp_path / "search_log_auto.md"
        _run([
            sys.executable, "scripts/research-external-evidence/search_log.py", "append",
            "--search-log", str(search_log),
            "--query", "example industry formal source",
            "--stage", "formal_research_execution",
            "--fs-id", "FS-001",
            "--selected-source", "https://example.com/auto-source",
            "--result-count", "3",
            "--opened-reviewed", "yes",
            "--locator-excerpt", "table 1 contains reviewed source context.",
        ])
        attempts = parse_search_attempts(search_log)
        assert "S-001" in attempts, attempts
        assert attempts["S-001"]["search instruction ids"] == "FS-001", attempts

    def test_templated_search_log(self, tmp_path):
        from validate_formal_research_execution import parse_search_attempts
        search_log = tmp_path / "search_log_from_template.md"
        template = SKILL_DIR / "references" / "search_log_template.md"
        search_log.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
        _run([
            sys.executable, "scripts/research-external-evidence/search_log.py", "append",
            "--search-log", str(search_log),
            "--query", "example broad definition source",
            "--stage", "broad_discovery",
            "--selected-source", "https://example.com/definition-source",
            "--result-count", "2",
            "--opened-reviewed", "yes",
            "--locator-excerpt", "section 1 contains reviewed definition context.",
        ])
        attempts = parse_search_attempts(search_log)
        assert "S-001" in attempts, attempts

    def test_edit_search_attempt_updates_known_field(self, tmp_path):
        from validate_formal_research_execution import parse_search_attempts
        search_log = tmp_path / "search_log_edit.md"
        _run([
            sys.executable, "scripts/research-external-evidence/search_log.py", "append",
            "--search-log", str(search_log),
            "--query", "example industry formal source",
            "--stage", "formal_research_execution",
            "--fs-id", "FS-001",
            "--selected-source", "https://example.com/source",
            "--result-count", "0",
            "--opened-reviewed", "yes",
            "--locator-excerpt", "section 1 contains reviewed source context.",
        ])
        result = _run([
            sys.executable, "scripts/research-external-evidence/search_log.py", "edit",
            "--search-log", str(search_log),
            "--attempt-id", "S-001",
            "--set-field", "Result Count=5",
        ])
        assert result.returncode == 0, result.stderr
        attempts = parse_search_attempts(search_log)
        assert attempts["S-001"]["result count"] == "5", attempts

    def test_edit_search_attempt_deletes_accidental_row(self, tmp_path):
        from validate_formal_research_execution import parse_search_attempts
        search_log = tmp_path / "search_log_delete.md"
        for query in ("first query", "accidental query"):
            _run([
                sys.executable, "scripts/research-external-evidence/search_log.py", "append",
                "--search-log", str(search_log),
                "--query", query,
                "--stage", "formal_research_execution",
                "--fs-id", "FS-001",
                "--selected-source", "https://example.com/source",
                "--result-count", "1",
                "--opened-reviewed", "yes",
                "--locator-excerpt", "section 1 contains reviewed source context.",
            ])
        result = _run([
            sys.executable, "scripts/research-external-evidence/search_log.py", "edit",
            "--search-log", str(search_log),
            "--attempt-id", "S-002",
            "--delete",
        ])
        assert result.returncode == 0, result.stderr
        attempts = parse_search_attempts(search_log)
        assert "S-001" in attempts, attempts
        assert "S-002" not in attempts, attempts


# ---------------------------------------------------------------------------
# Formal search plan
# ---------------------------------------------------------------------------


class TestFormalSearchPlan:
    def test_build_and_validate(self, tmp_path):
        from build_formal_search_plan_skeleton import build_plan as build_formal_search_plan_skeleton
        from validate_formal_search_plan import validate as validate_formal_search_plan
        plan = build_formal_search_plan_skeleton(
            {"industry": "sample sector", "geography": "Samplestan"},
            {"scope_summary": {"working_market": "sample sector", "geography": "Samplestan"}},
        )
        skeleton_errors, _ = validate_formal_search_plan(plan)
        assert skeleton_errors
        _rewrite_plan_queries_for_contract_test(plan)
        errors, warnings = validate_formal_search_plan(plan)
        assert not errors, errors
        assert len(plan["issue_search_plan"]) >= 40, len(plan["issue_search_plan"])
        _write_json(tmp_path / "formal_search_plan.json", plan)

    def test_duplicate_instruction_id_rejected(self, tmp_path):
        from build_formal_search_plan_skeleton import build_plan as build_formal_search_plan_skeleton
        from validate_formal_search_plan import validate as validate_formal_search_plan
        plan = build_formal_search_plan_skeleton(
            {"industry": "sample sector", "geography": "Samplestan"},
            {"scope_summary": {"working_market": "sample sector", "geography": "Samplestan"}},
        )
        invalid_plan = json.loads(json.dumps(plan))
        invalid_plan["issue_search_plan"][1]["search_instructions"][0]["instruction_id"] = "FS-001"
        invalid_plan["issue_search_plan"][1]["search_instructions"][0]["query"] = "<industry> placeholder"
        errors, _ = validate_formal_search_plan(invalid_plan)
        assert any("duplicate instruction_id" in e for e in errors), errors
        assert any("placeholder" in e for e in errors), errors

    def test_invalid_taxonomy_rejected(self, tmp_path):
        from build_formal_search_plan_skeleton import build_plan as build_formal_search_plan_skeleton
        from validate_formal_search_plan import validate as validate_formal_search_plan
        plan = build_formal_search_plan_skeleton(
            {"industry": "sample sector", "geography": "Samplestan"},
            {"scope_summary": {"working_market": "sample sector", "geography": "Samplestan"}},
        )
        bad_plan = json.loads(json.dumps(plan))
        bad_plan["issue_search_plan"][0]["subissue"] = "made_up_subissue"
        errors, _ = validate_formal_search_plan(bad_plan)
        assert any("Valid subissues for 'market_size_growth'" in e for e in errors), errors


# ---------------------------------------------------------------------------
# Source archive
# ---------------------------------------------------------------------------


class TestSourceArchive:

    def test_source_archive_rejects_metadata_only_excerpt_snapshot(self, tmp_path):
        from validate_source_archive import validate as validate_source_archive
        run_dir = tmp_path / "run"
        archive_dir = run_dir / "artifacts" / "source_archive"
        archive_dir.mkdir(parents=True)
        (archive_dir / "SRC-001.md").write_text(
            "# SRC-001 Source Archive Snapshot\n\n"
            "- Title: Example source\n"
            "- URL: https://example.com/source\n\n"
            "## Archive Note\n\nMetadata only.\n",
            encoding="utf-8",
        )
        index_path = archive_dir / "source_archive_index.json"
        _write_json(
            index_path,
            {
                "schema_version": "source_archive_index_v1",
                "entries": [
                    {
                        "source_review_id": "SRC-001",
                        "url": "https://example.com/source",
                        "title": "Example source",
                        "archive_status": "excerpt_snapshot",
                        "archive_path": "artifacts/source_archive/SRC-001.md",
                        "locator": "",
                        "reviewed_excerpt": "",
                    }
                ],
            },
        )

        result = validate_source_archive(source_archive_index_path=index_path, run_dir=run_dir)

        assert result["is_valid"] is False, result
        assert any("reviewed_excerpt" in error for error in result["errors"]), result
        assert any("Reviewed Excerpt" in error for error in result["errors"]), result


# ---------------------------------------------------------------------------
# Formal execution report edge cases
# ---------------------------------------------------------------------------


class TestFormalExecutionEdgeCases:
    def test_invalid_search_attempt_id_rejected(self, _pipeline_run_dir):
        from validate_formal_research_execution import validate as validate_formal_research_execution
        artifacts = _pipeline_run_dir["artifacts"]
        report = json.loads((artifacts / "formal_research_execution_report.json").read_text(encoding="utf-8"))
        plan = json.loads((artifacts / "formal_search_plan.json").read_text(encoding="utf-8"))
        invalid_report = json.loads(json.dumps(report))
        invalid_report["issue_results"][0]["search_attempt_ids"] = ["S-001"]
        errors, _ = validate_formal_research_execution(invalid_report, plan, artifacts / "search_log.md")
        assert any("expected formal_research" in e for e in errors), errors

    def test_fs_as_attempt_id_rejected(self, _pipeline_run_dir):
        from validate_formal_research_execution import validate as validate_formal_research_execution
        artifacts = _pipeline_run_dir["artifacts"]
        report = json.loads((artifacts / "formal_research_execution_report.json").read_text(encoding="utf-8"))
        plan = json.loads((artifacts / "formal_search_plan.json").read_text(encoding="utf-8"))
        fs_report = json.loads(json.dumps(report))
        fs_report["issue_results"][0]["search_attempt_ids"] = ["FS-001"]
        errors, _ = validate_formal_research_execution(fs_report, plan, artifacts / "search_log.md")
        assert any("FS-xxx is a planned search instruction" in e for e in errors), errors
        assert any("search_attempt_ids must contain actual S-xxx" in e for e in errors), errors

    def test_bad_structure_report_rejected(self, _pipeline_run_dir):
        from validate_formal_research_execution import validate as validate_formal_research_execution
        artifacts = _pipeline_run_dir["artifacts"]
        plan = json.loads((artifacts / "formal_search_plan.json").read_text(encoding="utf-8"))
        bad_report = {"issue_results": [{}]}
        errors, _ = validate_formal_research_execution(bad_report, plan, artifacts / "search_log.md")
        assert any("formal_research_execution_report.skeleton.json" in e for e in errors), errors
        assert any("copy issue_area, subissue, and research_question" in e for e in errors), errors
