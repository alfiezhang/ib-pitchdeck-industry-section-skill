#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from conftest import SCRIPT_IMPORT_PATHS, SKILL_DIR, _write_json


def _run(args: list[str]) -> subprocess.CompletedProcess:
    env = {**__import__("os").environ, "PYTHONPATH": ":".join(str(path) for path in SCRIPT_IMPORT_PATHS)}
    return subprocess.run(args, text=True, capture_output=True, cwd=str(SKILL_DIR), env=env)


def test_old_qc_entrypoints_are_removed() -> None:
    assert not (SKILL_DIR / ("scripts/state_" + "report.py")).exists()
    assert not (SKILL_DIR / ("scripts/qc/gate_" + "report.py")).exists()
    assert not (SKILL_DIR / ("scripts/qc/qc_" + "router.py")).exists()
    assert not (SKILL_DIR / ("scripts/qc/" + "validators")).exists()
    assert not (SKILL_DIR / "scripts/status.py").exists()
    assert not (SKILL_DIR / "scripts/qc/check_runtime_dependencies.py").exists()
    assert not (SKILL_DIR / "scripts/industry-scoping/boundary_loop.py").exists()
    assert not (SKILL_DIR / "scripts/knowledge-repository/repository.py").exists()
    assert not (SKILL_DIR / "scripts/output/update_runs_index.py").exists()
    assert not (SKILL_DIR / "scripts/template/select_template.py").exists()
    assert not (SKILL_DIR / "scripts/template/extract_template_registry.py").exists()
    assert not (SKILL_DIR / "scripts/start_case_from_brief.py").exists()
    assert not (SKILL_DIR / "scripts/knowledge-repository/build_research_evidence_db.py").exists()
    assert not (SKILL_DIR / "scripts/knowledge-repository/export_research_pack_from_db.py").exists()
    assert not (SKILL_DIR / "scripts/generation/compile_banker_page_pack.py").exists()
    assert not (SKILL_DIR / "scripts/_lib/compare_table_utils.py").exists()
    assert not (SKILL_DIR / "scripts/_lib/issue_taxonomy.py").exists()
    assert not (SKILL_DIR / "scripts/_lib/layout_config.py").exists()
    assert not (SKILL_DIR / "scripts/template/template_fit.py").exists()


def test_internal_output_scripts_are_not_agent_facing() -> None:
    role_map = json.loads((SKILL_DIR / "configs/script_role_map.json").read_text(encoding="utf-8"))
    exposed = set(role_map)
    assert "pipeline.py" in exposed
    assert "generate_replacement_dict.py" not in exposed
    assert "fill_ppt_tokens.py" not in exposed
    assert "clean_filled_ppt.py" not in exposed
    assert "postprocess_ppt_visuals.py" not in exposed


def test_runtime_guidance_does_not_reintroduce_old_workflow_terms() -> None:
    forbidden_terms = [
        "repository retrieval",
        "repository reuse",
        "source repository",
        "reusable source repository",
        "issue analysis",
        "issue_analysis",
        "hypothesis_store",
        "page_argument_pack",
        "diligence implication",
        "后续验证点",
        "客户关注点",
        "客户关注",
        "client concern",
    ]
    paths = [SKILL_DIR / "SKILL.md"]
    paths.extend((SKILL_DIR / "references").glob("*.md"))
    paths.extend((SKILL_DIR / "configs").glob("*.json"))

    hits: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8").lower()
        for term in forbidden_terms:
            if term.lower() in text:
                hits.append(f"{path.relative_to(SKILL_DIR)}: {term}")

    assert hits == []


def test_status_next_reports_missing_first_artifact(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    result = _run([sys.executable, "scripts/pipeline.py", "next", "--run-dir", str(run_dir)])

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "status_report_v1"
    assert payload["current_stage"] == "input_card"
    assert payload["current_state"] == "missing"
    assert "scripts/pipeline.py validate" in payload["recommended_next_commands"][-1]


def test_validate_artifact_cli_writes_output(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(run_dir / "input_card.json", {"raw_brief": "Sample brief"})
    output = run_dir / "artifacts/input_card_validation.json"

    result = _run([
        sys.executable,
        "scripts/pipeline.py",
        "validate",
        "--artifact",
        "input_card",
        "--run-dir",
        str(run_dir),
        "--output",
        str(output),
    ])

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["is_valid"] is True
    assert payload["validation_policy"] == "mechanical_only"
