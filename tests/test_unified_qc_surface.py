#!/usr/bin/env python3

from __future__ import annotations

import json
import re
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
    assert not (SKILL_DIR / "scripts/bootstrap_runtime.py").exists()
    assert not (SKILL_DIR / "scripts/status.py").exists()
    assert not (SKILL_DIR / "scripts/qc/check_runtime_dependencies.py").exists()
    assert not (SKILL_DIR / "scripts/industry-scoping/boundary_loop.py").exists()
    assert not (SKILL_DIR / "scripts/knowledge-repository/repository.py").exists()
    assert not (SKILL_DIR / "scripts/output/update_runs_index.py").exists()
    assert not (SKILL_DIR / "scripts/output/generate_replacement_dict.py").exists()
    assert not (SKILL_DIR / "scripts/output/fill_ppt_tokens.py").exists()
    assert not (SKILL_DIR / "scripts/output/clean_filled_ppt.py").exists()
    assert not (SKILL_DIR / "scripts/template/select_template.py").exists()
    assert not (SKILL_DIR / "scripts/template/extract_template_registry.py").exists()
    assert not (SKILL_DIR / "scripts/start_case_from_brief.py").exists()
    assert not (SKILL_DIR / "scripts/knowledge-repository/build_research_evidence_db.py").exists()
    assert not (SKILL_DIR / "scripts/knowledge-repository/export_research_pack_from_db.py").exists()
    assert not (SKILL_DIR / "scripts/generation/compile_banker_page_pack.py").exists()
    assert not (SKILL_DIR / "scripts/_lib/compare_table_utils.py").exists()
    assert not (SKILL_DIR / "scripts/_lib/gate_guard.py").exists()
    assert not (SKILL_DIR / "scripts/_lib/gate_retry_state.py").exists()
    assert not (SKILL_DIR / "scripts/_lib/issue_taxonomy.py").exists()
    assert not (SKILL_DIR / "scripts/_lib/layout_config.py").exists()
    assert not (SKILL_DIR / "scripts/_lib/material_extractors.py").exists()
    assert not (SKILL_DIR / "scripts/_lib/slide_registry.py").exists()
    assert not (SKILL_DIR / "scripts/_lib/renderer_token_source.py").exists()
    assert not (SKILL_DIR / "scripts/_lib/template_contract_utils.py").exists()
    assert not (SKILL_DIR / "scripts/_lib/unit_normalizer.py").exists()
    assert not (SKILL_DIR / "scripts/_lib/validation_common.py").exists()
    assert not (SKILL_DIR / "scripts/template/template_fit.py").exists()
    assert not (SKILL_DIR / "schemas/issue_analysis_schema.json").exists()
    assert not (SKILL_DIR / "schemas/industry_scope_pack_v2_schema.json").exists()
    assert not (SKILL_DIR / "schemas/qc_repair_schema.json").exists()
    assert not (SKILL_DIR / "schemas/qc_warning_disposition_schema.json").exists()
    assert not (SKILL_DIR / "configs/artifact_templates/formal_research_execution_report.skeleton.json").exists()
    assert not (SKILL_DIR / "configs/artifact_templates/source_archive_index.template.json").exists()


def test_schema_surface_stays_small_and_purposeful() -> None:
    schemas = {path.name for path in (SKILL_DIR / "schemas").glob("*.json")}
    assert schemas == {"banker_page_pack_schema.json", "renderer_spec_schema.json"}


def test_runtime_python_surface_stays_small() -> None:
    scripts = [
        path.relative_to(SKILL_DIR).as_posix()
        for path in (SKILL_DIR / "scripts").rglob("*.py")
    ]
    assert len(scripts) <= 11


def test_pipeline_is_only_public_script_surface() -> None:
    assert not (SKILL_DIR / "configs/script_role_map.json").exists()

    guidance_paths = [SKILL_DIR / "SKILL.md", SKILL_DIR / "configs/artifact_manifest.json"]
    guidance_paths.extend((SKILL_DIR / "references").glob("*.md"))
    guidance_paths.extend((SKILL_DIR / "configs" / "artifact_templates").glob("*.json"))

    forbidden_public_entries = [
        "bootstrap_runtime.py",
        "template_analyzer.py",
        "generate_replacement_dict.py",
        "fill_ppt_tokens.py",
        "clean_filled_ppt.py",
        "postprocess_ppt_visuals.py",
        "script_role_map",
        "script mapping",
        "script mappings",
    ]

    hits: list[str] = []
    for path in guidance_paths:
        text = path.read_text(encoding="utf-8")
        for entry in forbidden_public_entries:
            if entry in text:
                hits.append(f"{path.relative_to(SKILL_DIR)}: {entry}")

    assert hits == []


def test_skill_guidance_exposes_pipeline_not_internal_role_scripts() -> None:
    guidance_paths = [SKILL_DIR / "SKILL.md", SKILL_DIR / "configs/artifact_manifest.json"]
    guidance_paths.extend((SKILL_DIR / "references").glob("*.md"))
    guidance_paths.extend((SKILL_DIR / "configs" / "artifact_templates").glob("*.json"))

    internal_script_ref = re.compile(r"scripts/(?!pipeline\.py\b)[A-Za-z0-9_-]+/[A-Za-z0-9_-]+\.py")
    hits: list[str] = []
    for path in guidance_paths:
        text = path.read_text(encoding="utf-8")
        for match in internal_script_ref.finditer(text):
            hits.append(f"{path.relative_to(SKILL_DIR)}: {match.group(0)}")

    assert hits == []


def test_smoke_tests_do_not_call_internal_role_scripts() -> None:
    smoke_text = (Path(__file__).resolve().parents[1] / "tests" / "run_smoke_tests.sh").read_text(encoding="utf-8")
    internal_script_ref = re.compile(r"scripts/(?!pipeline\.py\b)[A-Za-z0-9_-]+/[A-Za-z0-9_-]+\.py")
    assert internal_script_ref.findall(smoke_text) == []


def test_all_reference_files_are_listed_in_skill_reference_map() -> None:
    skill_text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    listed = {
        match.group(1)
        for match in re.finditer(r"`references/([^`]+\.md)`", skill_text)
    }
    actual = {
        path.name
        for path in (SKILL_DIR / "references").glob("*.md")
    }

    assert actual == listed


def test_deterministic_validator_does_not_read_llm_quality_rules() -> None:
    assert not (SKILL_DIR / "configs/content_quality_rules.json").exists()
    assert not (SKILL_DIR / "configs/drilldown_role_library.json").exists()
    assert not list((SKILL_DIR / "configs").glob("*.md"))
    assert (SKILL_DIR / "references/content-quality.md").exists()
    assert (SKILL_DIR / "references/drilldown-roles.md").exists()
    assert (SKILL_DIR / "references/critical-anti-patterns.md").exists()
    deterministic_sources = [
        SKILL_DIR / "scripts/qc/validate_artifact.py",
        SKILL_DIR / "scripts/knowledge-repository/research_evidence_db.py",
    ]
    for path in deterministic_sources:
        source = path.read_text(encoding="utf-8")
        assert "content_quality_rules.json" not in source
        assert "_quality_rules" not in source
        assert "advisory target" not in source


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
        "client_question",
        "investor_question",
        "open_questions",
        "open_question",
        "fallback_if_data_limited",
        "fallback_if_data_insufficient",
        "default_visual_fallback",
        "后续验证点",
        "客户关注点",
        "客户关注",
        "client concern",
        "follow-up",
        "diagnostic checklist",
        "evidence_gap_matrix",
        "evidence-gap matrix",
        "validation point",
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


def test_llm_facing_contracts_do_not_reintroduce_old_prompt_terms() -> None:
    forbidden_terms = [
        "open_question",
        "fallback_if_data_limited",
        "fallback_if_data_insufficient",
        "default_visual_fallback",
    ]
    paths = [
        SKILL_DIR / "schemas/banker_page_pack_schema.json",
        SKILL_DIR / "schemas/renderer_spec_schema.json",
        SKILL_DIR / "configs/generation_policy.json",
    ]

    hits: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for term in forbidden_terms:
            if term in text:
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


def test_pipeline_template_registry_command_writes_and_validates(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    result = _run([
        sys.executable,
        "scripts/pipeline.py",
        "template-registry",
        "--run-dir",
        str(run_dir),
    ])

    assert result.returncode == 0, result.stdout + result.stderr
    assert (run_dir / "template_registry.json").exists()
    validation = json.loads((run_dir / "artifacts/template_registry_validation.json").read_text(encoding="utf-8"))
    assert validation["is_valid"] is True
