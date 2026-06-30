#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from conftest import SCRIPT_IMPORT_PATHS, SKILL_DIR, _minimal_scope_pack, _write_json


def _run(args: list[str]) -> subprocess.CompletedProcess:
    env = {**__import__("os").environ, "PYTHONPATH": ":".join(str(path) for path in SCRIPT_IMPORT_PATHS)}
    return subprocess.run(args, text=True, capture_output=True, cwd=str(SKILL_DIR), env=env)


def test_research_graph_prepare_helper_writes_plan_batch_and_graph_state(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    _write_json(run_dir / "input_card.json", {"industry": "sample sector", "geography": "Samplestan"})
    _write_json(artifacts / "industry_scope_pack.json", _minimal_scope_pack())
    _write_json(
        artifacts / "industry_boundary_qc.json",
        {"schema_version": "industry_boundary_qc", "decision": "Boundary is clear for formal research.",
            "business_action": "research_ready"},
    )

    result = _run([
        sys.executable,
        "scripts/research-external-evidence/ib_research_graph.py",
        "prepare-workbench",
        "--run-dir",
        str(run_dir),
    ])

    assert result.returncode == 0, result.stderr
    assert (artifacts / "formal_search_plan.json").exists()
    assert (artifacts / "coverage_map.json").exists()
    assert (artifacts / "executable_search_batch.json").exists()
    assert (artifacts / "research_graph_state.json").exists()
    plan = json.loads((artifacts / "formal_search_plan.json").read_text(encoding="utf-8"))
    plan_text = json.dumps(plan, ensure_ascii=False)
    assert "coverage_requirement" not in plan
    assert "issue_search_plan" not in plan
    assert len(plan["core_research_threads"]) == 3
    assert len(plan["core_research_threads"]) <= 4
    assert plan["plan_mode"] == "core_threads_plus_llm_expansion"
    assert "allowed_issue_taxonomy" not in plan
    assert "suggested_issue_menu" not in plan
    assert "taxonomy completion sheet" not in plan_text
    assert "terminal_status" not in plan_text
    assert "minimum_actual_searches" not in plan_text
    assert "coverage_required" not in plan_text
    assert plan["research_discipline"] == {
        "formal_validation_lives_in": "artifacts/formal_research_execution_report.json",
        "query_authoring_artifact": "artifacts/executable_search_batch.json",
        "planned_rows_are_not_evidence": True,
    }
    batch = json.loads((artifacts / "executable_search_batch.json").read_text(encoding="utf-8"))
    batch_text = json.dumps(batch, ensure_ascii=False)
    assert "LLM_REWRITE_REQUIRED" not in batch_text
    assert "needs_authoring" not in batch_text
    assert "query_status" not in batch_text
    first_batch = batch["batches"][0]
    assert first_batch["queries"] == []
    assert "query_brief" in first_batch
    assert "research_thread" in first_batch
    assert "issue_area" not in first_batch
    assert "subissue" not in first_batch
    assert "english_query" not in first_batch
    assert "chinese_query" not in first_batch
    assert "source_specific_query" not in first_batch
    graph = json.loads((artifacts / "research_graph_state.json").read_text(encoding="utf-8"))
    graph_text = json.dumps(graph, ensure_ascii=False)
    assert "executable_query_status" not in graph_text
    assert "needs_authoring" not in graph_text
    assert "issue_area" not in graph_text
    assert "subissue" not in graph_text
    assert "minimum_actual_searches" not in graph_text
    assert "coverage_required" not in graph_text


def test_research_graph_prepare_does_not_require_boundary_qc_gate(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    _write_json(run_dir / "input_card.json", {"industry": "sample sector", "geography": "Samplestan"})
    _write_json(artifacts / "industry_scope_pack.json", _minimal_scope_pack())

    result = _run([
        sys.executable,
        "scripts/research-external-evidence/ib_research_graph.py",
        "prepare-workbench",
        "--run-dir",
        str(run_dir),
    ])

    assert result.returncode == 0, result.stderr
    assert (artifacts / "formal_search_plan.json").exists()
    assert (artifacts / "executable_search_batch.json").exists()
    assert (artifacts / "research_graph_state.json").exists()


def test_research_graph_prepare_stops_when_boundary_qc_requests_scope_repair(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    _write_json(run_dir / "input_card.json", {"industry": "sample sector", "geography": "Samplestan"})
    _write_json(artifacts / "industry_scope_pack.json", _minimal_scope_pack())
    _write_json(
        artifacts / "industry_boundary_qc.json",
        {
            "schema_version": "industry_boundary_qc",
            "decision": "Scope needs repair before research.",
            "business_action": "repair_scope",
            "rationale": "Working market is still confused with a channel.",
        },
    )

    result = _run([
        sys.executable,
        "scripts/research-external-evidence/ib_research_graph.py",
        "prepare-workbench",
        "--run-dir",
        str(run_dir),
    ])

    assert result.returncode != 0
    assert "business_action=repair_scope" in result.stderr


def test_research_graph_prepare_does_not_infer_natural_boundary_qc_routing(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    _write_json(run_dir / "input_card.json", {"industry": "sample sector", "geography": "Samplestan"})
    _write_json(artifacts / "industry_scope_pack.json", _minimal_scope_pack())
    _write_json(
        artifacts / "industry_boundary_qc.json",
        {
            "schema_version": "industry_boundary_qc",
            "decision": "Do not start research yet; the scope needs boundary validation and repair.",
            "rationale": "Working market is still confused with a channel.",
        },
    )

    result = _run([
        sys.executable,
        "scripts/research-external-evidence/ib_research_graph.py",
        "prepare-workbench",
        "--run-dir",
        str(run_dir),
    ])

    assert result.returncode == 0, result.stderr
    assert (artifacts / "formal_search_plan.json").exists()


def test_research_graph_prepare_stops_when_boundary_business_action_requests_check(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    _write_json(run_dir / "input_card.json", {"industry": "sample sector", "geography": "Samplestan"})
    _write_json(artifacts / "industry_scope_pack.json", _minimal_scope_pack())
    _write_json(
        artifacts / "industry_boundary_qc.json",
        {
            "schema_version": "industry_boundary_qc",
            "decision": "A small boundary check should run before formal research.",
            "business_action": "boundary_check",
            "rationale": "Working market is still confused with a channel.",
        },
    )

    result = _run([
        sys.executable,
        "scripts/research-external-evidence/ib_research_graph.py",
        "prepare-workbench",
        "--run-dir",
        str(run_dir),
    ])

    assert result.returncode != 0
    assert "business_action=boundary_check" in result.stderr


def test_validate_artifact_rejects_unwritten_query_batch(tmp_path: Path) -> None:
    from ib_research_graph import build_executable_search_batch, build_formal_search_plan
    from validate_artifact import validate_artifact

    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    plan = build_formal_search_plan({"industry": "sample sector", "geography": "Samplestan"}, _minimal_scope_pack())
    _write_json(artifacts / "executable_search_batch.json", build_executable_search_batch(plan))

    errors, _ = validate_artifact("executable_search_batch", run_dir)

    assert any("missing active boolean" in error for error in errors), errors


def test_search_batch_validator_does_not_infer_deferred_rows_from_text_markers() -> None:
    validator_text = (SKILL_DIR / "scripts/qc/validate_artifact.py").read_text(encoding="utf-8")

    assert "INACTIVE_QUERY_MARKERS" not in validator_text
    assert "INACTIVE_QUERY_STATUSES" not in validator_text
    assert "_inactive_query_reason" not in validator_text
    assert "any(marker in combined" not in validator_text


def test_validate_artifact_allows_deferred_query_rows_without_filler(tmp_path: Path) -> None:
    from validate_artifact import validate_artifact

    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    _write_json(
        artifacts / "executable_search_batch.json",
        {
            "schema_version": "search_batch_v1",
            "batches": [
                {
                    "search_instruction_id": "FS-001",
                    "active": True,
                    "queries": [
                        {"query": "China base makeup market size 2024 report"},
                        {"query": "中国 底妆 市场规模 2024 报告"},
                        {"query": "site:stats.gov.cn 化妆品类 零售额 2024"},
                    ],
                },
                {
                    "search_instruction_id": "FS-002",
                    "active": False,
                    "query_text": "LLM_REWRITE_REQUIRED: low-priority peer long tail",
                    "backlog_reason": "Low priority backlog until the main market-sizing thread is supported.",
                },
            ],
        },
    )

    errors, warnings = validate_artifact("executable_search_batch", run_dir)

    assert errors == []
    assert any("active=false row still carries placeholder query text" in warning for warning in warnings)


def test_validate_artifact_requires_active_boolean_for_deferred_query_row(tmp_path: Path) -> None:
    from validate_artifact import validate_artifact

    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    _write_json(
        artifacts / "executable_search_batch.json",
        {
            "schema_version": "search_batch_v1",
            "batches": [
                {
                    "search_instruction_id": "FS-001",
                    "active": True,
                    "queries": [{"query": "中国 底妆 市场规模 2024 报告"}],
                    "why_this_search_matters": "Core market-sizing thread.",
                },
                {
                    "search_instruction_id": "FS-002",
                    "selection_decision": "暂缓：不是本轮能改变页面授权或图表设计的核心问题。",
                },
            ],
        },
    )

    errors, warnings = validate_artifact("executable_search_batch", run_dir)

    assert any("missing active boolean" in error for error in errors), errors
    assert "暂缓" not in "\n".join(warnings)


def test_validate_artifact_allows_explicit_deferred_query_row_without_query_text(tmp_path: Path) -> None:
    from validate_artifact import validate_artifact

    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    _write_json(
        artifacts / "executable_search_batch.json",
        {
            "schema_version": "search_batch_v1",
            "batches": [
                {
                    "search_instruction_id": "FS-001",
                    "active": True,
                    "queries": [{"query": "中国 底妆 市场规模 2024 报告"}],
                    "why_this_search_matters": "Core market-sizing thread.",
                },
                {
                    "search_instruction_id": "FS-002",
                    "active": False,
                    "selection_note": "暂缓：不是本轮能改变页面授权或图表设计的核心问题。",
                },
            ],
        },
    )

    errors, warnings = validate_artifact("executable_search_batch", run_dir)

    assert errors == []
    assert not any("query_status" in warning for warning in warnings)


def test_validate_artifact_allows_single_targeted_query_without_filler_variants(tmp_path: Path) -> None:
    from validate_artifact import validate_artifact

    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    _write_json(
        artifacts / "executable_search_batch.json",
        {
            "schema_version": "search_batch_v1",
            "batches": [
                {
                    "search_instruction_id": "FS-001",
                    "active": True,
                    "query_text": "site:stats.gov.cn 化妆品类 零售额 2024",
                    "why_this_search_matters": "Targeted official statistics source for market context.",
                }
            ],
        },
    )

    errors, warnings = validate_artifact("executable_search_batch", run_dir)

    assert errors == []
    assert not any("only one executable query was supplied" in warning for warning in warnings)


def test_validate_artifact_rejects_legacy_three_column_query_batch(tmp_path: Path) -> None:
    from validate_artifact import validate_artifact

    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    _write_json(
        artifacts / "executable_search_batch.json",
        {
            "schema_version": "search_batch_v1",
            "batches": [
                {
                    "search_instruction_id": "FS-001",
                    "active": True,
                    "english_query": "China base makeup market size 2024 report",
                    "chinese_query": "中国 底妆 市场规模 2024 报告",
                    "source_specific_query": "site:stats.gov.cn 化妆品类 零售额 2024",
                }
            ],
        },
    )

    errors, _ = validate_artifact("executable_search_batch", run_dir)

    assert any("legacy query columns are not allowed" in error for error in errors), errors


def test_validate_artifact_rejects_authored_batch_without_any_query_text(tmp_path: Path) -> None:
    from validate_artifact import validate_artifact

    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    _write_json(
        artifacts / "executable_search_batch.json",
        {
            "schema_version": "search_batch_v1",
            "batches": [
                {
                    "search_instruction_id": "FS-001",
                    "active": True,
                    "why_this_search_matters": "This row is marked executable but lacks a query.",
                }
            ],
        },
    )

    errors, _ = validate_artifact("executable_search_batch", run_dir)

    assert any("active=true rows need at least one concrete query" in error for error in errors), errors


def test_validate_artifact_rejects_query_fields_in_formal_plan(tmp_path: Path) -> None:
    from ib_research_graph import build_formal_search_plan
    from validate_artifact import validate_artifact

    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    plan = build_formal_search_plan({"industry": "sample sector", "geography": "Samplestan"}, _minimal_scope_pack())
    plan["core_research_threads"][0]["query"] = "this belongs in executable batch"
    _write_json(artifacts / "formal_search_plan.json", plan)

    errors, _ = validate_artifact("formal_search_plan", run_dir)

    assert any("must not contain executable query fields" in error for error in errors), errors


def test_validate_artifact_rejects_legacy_taxonomy_fields_in_formal_plan(tmp_path: Path) -> None:
    from ib_research_graph import build_formal_search_plan
    from validate_artifact import validate_artifact

    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    plan = build_formal_search_plan({"industry": "sample sector", "geography": "Samplestan"}, _minimal_scope_pack())
    plan["issue_search_plan"] = [{"issue_area": "old taxonomy"}]
    plan["core_research_threads"][0]["minimum_actual_searches"] = 3
    _write_json(artifacts / "formal_search_plan.json", plan)

    errors, _ = validate_artifact("formal_search_plan", run_dir)

    assert any("must not contain legacy taxonomy/query-control fields" in error for error in errors), errors


def test_executable_batch_builder_does_not_consume_legacy_issue_search_plan() -> None:
    from ib_research_graph import build_executable_search_batch

    batch = build_executable_search_batch(
        {
            "schema_version": "formal_search_plan",
            "issue_search_plan": [
                {
                    "issue_area": "legacy market size",
                    "research_question": "Old taxonomy row should not become a query workbench row.",
                    "search_instructions": [{"instruction_id": "FS-999", "source_hint": "legacy source"}],
                }
            ],
            "core_research_threads": [
                {
                    "thread": "Current evidence thread",
                    "research_question": "What source-backed evidence should the LLM inspect now?",
                    "source_direction": "named industry report",
                }
            ],
        }
    )

    assert len(batch["batches"]) == 1
    assert batch["batches"][0]["research_thread"] == "Current evidence thread"
    assert "legacy market size" not in json.dumps(batch, ensure_ascii=False)


def test_validate_artifact_scope_pack_rejects_old_memo_schema(tmp_path: Path) -> None:
    from validate_artifact import validate_artifact

    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    _write_json(artifacts / "industry_scope_pack.json", {"schema_version": "industry_scope_pack_v1"})

    errors, _ = validate_artifact("industry_scope_pack", run_dir)

    assert any("industry_scope_pack_boundary_card" in error for error in errors), errors
