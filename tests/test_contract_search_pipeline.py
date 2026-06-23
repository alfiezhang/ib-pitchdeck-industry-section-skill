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

    def test_market_size_claim_in_scope_summary_rejected(self):
        from validate_industry_scope_pack import validate as validate_industry_scope_pack
        scope = json.loads(json.dumps(_minimal_scope_pack()))
        scope["scope_summary"]["working_market"] = "example market size reached 100亿元"
        errors, _ = validate_industry_scope_pack(scope)
        assert any("market size claim belongs in formal research" in e for e in errors), errors

    def test_empty_boundary_validation_needed_allowed(self):
        from validate_industry_scope_pack import validate as validate_industry_scope_pack
        scope = json.loads(json.dumps(_minimal_scope_pack()))
        scope["boundary_validation_needed"] = []
        errors, _ = validate_industry_scope_pack(scope)
        assert not errors, errors

    def test_legacy_v1_scope_pack_rejected(self):
        from validate_industry_scope_pack import validate as validate_industry_scope_pack
        scope = {"schema_version": "industry_scope_pack_v1", "scope_summary": {"working_market": "sample"}}
        errors, _ = validate_industry_scope_pack(scope)
        assert any("v1 scope memo artifacts are no longer accepted" in e for e in errors), errors

    def test_legacy_v1_fields_rejected(self):
        from validate_industry_scope_pack import validate as validate_industry_scope_pack
        scope = json.loads(json.dumps(_minimal_scope_pack()))
        scope["llm_definition_draft"] = {"working_market_draft": "old memo field"}
        errors, _ = validate_industry_scope_pack(scope)
        assert any("legacy v1 memo field" in e for e in errors), errors


# ---------------------------------------------------------------------------
# Formal search plan
# ---------------------------------------------------------------------------


class TestFormalSearchPlan:
    def test_build_and_validate(self, tmp_path):
        from ib_research_graph import build_formal_search_plan
        from validate_formal_search_plan import validate as validate_formal_search_plan
        plan = build_formal_search_plan(
            {"industry": "sample sector", "geography": "Samplestan"},
            {"scope_summary": {"working_market": "sample sector", "geography": "Samplestan"}},
        )
        skeleton_errors, _ = validate_formal_search_plan(plan)
        assert not skeleton_errors, skeleton_errors
        _rewrite_plan_queries_for_contract_test(plan)
        errors, warnings = validate_formal_search_plan(plan)
        assert not errors, errors
        assert len(plan["issue_search_plan"]) >= 40, len(plan["issue_search_plan"])
        _write_json(tmp_path / "formal_search_plan.json", plan)

    def test_prepare_cli_writes_plan_batch_and_graph_state(self, tmp_path):
        run_dir = tmp_path / "run"
        artifacts = run_dir / "artifacts"
        artifacts.mkdir(parents=True)
        input_card = run_dir / "input_card.json"
        scope_pack = artifacts / "industry_scope_pack.json"
        input_card.write_text(
            json.dumps({"industry": "sample sector", "geography": "Samplestan"}),
            encoding="utf-8",
        )
        scope_pack.write_text(
            json.dumps({"scope_summary": {"working_market": "sample sector", "geography": "Samplestan"}}),
            encoding="utf-8",
        )

        result = _run([
            sys.executable,
            str(SCRIPT_DIR / "research-external-evidence" / "ib_research_graph.py"),
            "prepare",
            "--run-dir", str(run_dir),
        ])

        assert result.returncode == 0, result.stderr
        output = artifacts / "formal_search_plan.json"
        coverage_map = artifacts / "coverage_map.json"
        executable_batch = artifacts / "executable_search_batch.json"
        state_path = artifacts / "research_graph_state.json"
        assert output.exists()
        assert coverage_map.exists()
        assert executable_batch.exists()
        assert state_path.exists()
        batch = json.loads(executable_batch.read_text(encoding="utf-8"))
        assert batch["schema_version"] == "search_batch_v1"
        assert batch["batches"], batch
        assert "LLM_REWRITE_REQUIRED" in batch["batches"][0]["english_query"]
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert state["graph_config"]["open_deep_research_compatible"] is True
        assert state["graph_config"]["operator_surface"]["primary_write_fields"] == ["research_context", "metrics", "evidence"]
        assert state["research_units"], state

    def test_duplicate_instruction_id_rejected(self, tmp_path):
        from ib_research_graph import build_formal_search_plan
        from validate_formal_search_plan import validate as validate_formal_search_plan
        plan = build_formal_search_plan(
            {"industry": "sample sector", "geography": "Samplestan"},
            {"scope_summary": {"working_market": "sample sector", "geography": "Samplestan"}},
        )
        invalid_plan = json.loads(json.dumps(plan))
        invalid_plan["issue_search_plan"][1]["search_instructions"][0]["instruction_id"] = "FS-001"
        invalid_plan["issue_search_plan"][1]["search_instructions"][0]["query"] = "<industry> placeholder"
        errors, _ = validate_formal_search_plan(invalid_plan)
        assert any("duplicate instruction_id" in e for e in errors), errors
        assert any("executable query fields belong only" in e for e in errors), errors

    def test_invalid_taxonomy_rejected(self, tmp_path):
        from ib_research_graph import build_formal_search_plan
        from validate_formal_search_plan import validate as validate_formal_search_plan
        plan = build_formal_search_plan(
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
        assert any("ib_research_graph.py compile" in e for e in errors), errors
        assert any("copies issue_area, subissue, and research_question" in e for e in errors), errors
