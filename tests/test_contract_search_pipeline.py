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


def test_prepare_cli_writes_plan_batch_and_graph_state(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    _write_json(run_dir / "input_card.json", {"industry": "sample sector", "geography": "Samplestan"})
    _write_json(artifacts / "industry_scope_pack.json", _minimal_scope_pack())
    _write_json(
        artifacts / "industry_boundary_qc.json",
        {"schema_version": "industry_boundary_qc_v1", "decision": "pass"},
    )

    result = _run([
        sys.executable,
        "scripts/pipeline.py",
        "research-prepare",
        "--run-dir",
        str(run_dir),
    ])

    assert result.returncode == 0, result.stderr
    assert (artifacts / "formal_search_plan.json").exists()
    assert (artifacts / "coverage_map.json").exists()
    assert (artifacts / "executable_search_batch.json").exists()
    assert (artifacts / "research_graph_state.json").exists()
    batch = json.loads((artifacts / "executable_search_batch.json").read_text(encoding="utf-8"))
    assert "LLM_REWRITE_REQUIRED" in json.dumps(batch)


def test_validate_artifact_rejects_unwritten_query_batch(tmp_path: Path) -> None:
    from ib_research_graph import build_executable_search_batch, build_formal_search_plan
    from validate_artifact import validate_artifact

    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    plan = build_formal_search_plan({"industry": "sample sector", "geography": "Samplestan"}, _minimal_scope_pack())
    _write_json(artifacts / "executable_search_batch.json", build_executable_search_batch(plan))

    errors, _ = validate_artifact("executable_search_batch", run_dir)

    assert any("LLM_REWRITE_REQUIRED" in error for error in errors), errors


def test_validate_artifact_rejects_query_fields_in_formal_plan(tmp_path: Path) -> None:
    from ib_research_graph import build_formal_search_plan
    from validate_artifact import validate_artifact

    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    plan = build_formal_search_plan({"industry": "sample sector", "geography": "Samplestan"}, _minimal_scope_pack())
    plan["issue_search_plan"][0]["search_instructions"][0]["query"] = "this belongs in executable batch"
    _write_json(artifacts / "formal_search_plan.json", plan)

    errors, _ = validate_artifact("formal_search_plan", run_dir)

    assert any("must not contain executable query fields" in error for error in errors), errors


def test_validate_artifact_scope_pack_requires_v2(tmp_path: Path) -> None:
    from validate_artifact import validate_artifact

    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    _write_json(artifacts / "industry_scope_pack.json", {"schema_version": "industry_scope_pack_v1"})

    errors, _ = validate_artifact("industry_scope_pack", run_dir)

    assert any("industry_scope_pack_boundary_card" in error for error in errors), errors
