#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "runtime" / "ib-pitchdeck-agent-industry-section" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from gate_report import build_gate_report  # noqa: E402
from workflow import next_payload  # noqa: E402


FIXTURE_DIR = ROOT / "tests" / "fixtures" / "minimal_research_db"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _seed_material_intake(run_dir: Path) -> None:
    artifacts = run_dir / "artifacts"
    _write_json(
        run_dir / "input_card.json",
        {"target_company": "Sample Target", "industry": "sample sector", "geography": "Sampleland"},
    )
    _write_json(artifacts / "input_card_validation.json", {"is_valid": True})
    _write_json(
        artifacts / "material_manifest.json",
        {
            "schema_version": "material_manifest_v1",
            "created_at": "2026-01-01T00:00:00+00:00",
            "policy_context": "pre_mandate_client_pitch",
            "materials": [
                {
                    "material_id": "MAT-001",
                    "source_type": "project_specific_material",
                    "source_access": "user_provided",
                    "file_path_or_url": "artifacts/material_texts/sample_contract.txt",
                    "material_kind": "text",
                    "extraction_status": "complete",
                    "extraction_limitations": "none",
                    "can_be_used_as_evidence": True,
                }
            ],
            "source_type_policy": {},
        },
    )
    _write_json(
        artifacts / "material_extracts.json",
        {
            "schema_version": "material_extracts_v1",
            "materials_source": "artifacts/material_manifest.json",
            "extracts": [
                {
                    "material_id": "MAT-001",
                    "source_type": "project_specific_material",
                    "source_access": "user_provided",
                    "file_path_or_url": "artifacts/material_texts/sample_contract.txt",
                    "extracted_text_path": "artifacts/material_texts/MAT-001.txt",
                    "extraction_status": "complete",
                    "extraction_limitations": "none",
                    "can_be_used_as_evidence": True,
                }
            ],
        },
    )
    _write_json(
        artifacts / "source_classification.json",
        {
            "schema_version": "source_classification_v1",
            "generated_at": "2026-01-01T00:00:00+00:00",
            "materials": [
                {
                    "material_id": "MAT-001",
                    "source_type": "project_specific_material",
                    "source_access": "user_provided",
                    "file_path_or_url": "artifacts/material_texts/sample_contract.txt",
                    "source_hash": "",
                    "source_date": "2026-01-01T00:00:00+00:00",
                }
            ],
        },
    )
    _write_json(artifacts / "material_manifest_validation.json", {"is_valid": True})
    _write_json(artifacts / "material_extracts_validation.json", {"is_valid": True})


def _seed_research_pack_ready(run_dir: Path) -> None:
    artifacts = run_dir / "artifacts"
    artifacts.mkdir()
    _seed_material_intake(run_dir)

    _write_json(artifacts / "industry_scope_pack.json", {"schema_version": "industry_scope_pack_v1", "scope_summary": {"working_market": "sample"}})
    _write_json(
        artifacts / "industry_scope_pack_validation.json",
        {"is_valid": True, "errors": [], "warnings": []},
    )

    _write_json(artifacts / "formal_search_plan.json", {"issue_search_plan": []})
    _write_json(
        artifacts / "formal_search_plan_validation.json",
        {"is_valid": True, "errors": [], "warnings": []},
    )

    _write_json(artifacts / "source_reviews.json", {"schema_version": "source_reviews_v1", "reviews": []})
    _write_json(
        artifacts / "source_reviews_validation.json",
        {"is_valid": True, "errors": [], "warnings": []},
    )

    _write_json(artifacts / "source_archive" / "source_archive_index.json", {"schema_version": "source_archive_index_v1", "entries": []})
    _write_json(
        artifacts / "source_archive_validation.json",
        {"is_valid": True, "errors": [], "warnings": []},
    )

    _write_json(artifacts / "formal_research_execution_report.json", {"issue_results": []})
    _write_json(
        artifacts / "formal_research_execution_validation.json",
        {"is_valid": True, "errors": [], "warnings": []},
    )

    _write_json(artifacts / "stage_gate_pre_research_pack_validation.json", {"is_valid": True})

    _write_json(artifacts / "research_evidence_db.json", json.loads((FIXTURE_DIR / "research_evidence_db.json").read_text(encoding="utf-8")))
    _write_json(
        artifacts / "research_evidence_db_validation.json",
        {"is_valid": True, "errors": [], "warnings": []},
    )
    _seed_boundary_loop_ready(run_dir)


def _seed_boundary_loop_ready(run_dir: Path) -> None:
    artifacts = run_dir / "artifacts"
    _write_json(
        artifacts / "boundary_loop_status.json",
        {
            "schema_version": "boundary_loop_status_v1",
            "status": "boundary_ready",
            "boundary_loop_status": "boundary_ready",
            "is_valid": True,
            "created_at": "2026-01-01T00:00:00Z",
            "errors": [],
            "warnings": [],
            "repair_actions": [],
            "boundary_inputs": {
                "scope_pack": True,
                "material_extracts": True,
                "research_evidence_db": True,
            },
        },
    )
    _write_json(
        artifacts / "industry_boundary_qc.json",
        {
            "schema_version": "industry_boundary_qc_v1",
            "decision": "pass",
            "rationale": "synthetic boundary QC pass for workflow fixture",
            "feedback": [],
            "boundary_validation_requests": [],
        },
    )
    if (artifacts / "industry_scope_pack_validation.json").exists():
        _write_json(
            artifacts / "industry_scope_pack_validation.json",
            {"is_valid": True, "errors": [], "warnings": []},
        )


def _seed_template_layer_artifacts(run_dir: Path) -> None:
    artifacts = run_dir / "artifacts"
    _write_json(
        artifacts / "template_profile.json",
        {
            "schema_version": "template_profile_v1",
            "template_file": str(ROOT / "runtime/ib-pitchdeck-agent-industry-section/assets/industry_section_template_master.pptx"),
            "layout": {},
            "visual_style": {},
        },
    )
    _write_json(
        artifacts / "template_fit_validation.json",
        {
            "schema_version": "template_fit_v1",
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "template_profile": str(artifacts / "template_profile.json"),
            "renderer_spec": str(run_dir / "renderer_spec.json"),
            "analysis_source": "template_fit.py",
        },
    )


def test_workflow_next_prefers_template_profile_repair_stage(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    _seed_research_pack_ready(run_dir)
    # Seed research pack + validation so pipeline advances past RESEARCH_PACK stage
    artifacts = run_dir / "artifacts"
    (run_dir / "industry_research_pack.md").write_text("# Research Pack\n", encoding="utf-8")
    _write_json(artifacts / "research_pack_validation.json", {"is_valid": True, "errors": [], "warnings": []})
    # Seed issue analysis + validation
    _write_json(run_dir / "industry_issue_analysis.json", {"issues": []})
    _write_json(artifacts / "issue_analysis_validation.json", {"is_valid": True, "errors": [], "warnings": []})
    # Seed template registry + validation
    _write_json(run_dir / "template_registry.json", {"slides": []})
    _write_json(artifacts / "template_registry_validation.json", {"is_valid": True, "errors": [], "warnings": []})
    # Seed deck blueprint + validation
    _write_json(run_dir / "deck_blueprint.json", {"slides": []})
    _write_json(artifacts / "deck_blueprint_validation.json", {"is_valid": True, "errors": [], "warnings": []})
    # Seed page evidence contract + validation
    _write_json(run_dir / "page_evidence_contract.json", {"pages": []})
    _write_json(artifacts / "page_evidence_contract_validation.json", {"is_valid": True, "errors": [], "warnings": []})
    # Seed renderer spec + validation
    _write_json(
        run_dir / "renderer_spec.json",
        {"schema_version": "renderer_spec_v1", "slides": [], "layout_version": "v1"},
    )
    _write_json(artifacts / "renderer_spec_validation.json", {"is_valid": True, "errors": [], "warnings": []})
    # No template_profile.json → should fire TEMPLATE_PROFILE_MISSING_OR_FAILED

    payload = next_payload(run_dir)
    assert payload["current_stage"] == "TEMPLATE_PROFILE_MISSING_OR_FAILED", payload
    command_text = "\n".join(item["command"] for item in payload["recommended_next_commands"])
    assert "template_analyzer.py" in command_text
    assert "pipeline.py validate-pre-ppt" in command_text
    assert "pipeline.py render" in command_text


def test_workflow_next_produces_pack_stage_repair_commands(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    _seed_research_pack_ready(run_dir)
    _seed_template_layer_artifacts(run_dir)
    _write_json(
        run_dir / "renderer_spec.json",
        {"schema_version": "renderer_spec_v1", "slides": [], "layout_version": "v1"},
    )

    payload = next_payload(run_dir)
    assert payload["current_stage"] == "RESEARCH_PACK_MISSING_OR_FAILED", payload
    command_text = "\n".join(item["command"] for item in payload["recommended_next_commands"])
    assert "export_research_pack_from_db.py" in command_text, payload["recommended_next_commands"]
    assert "validate_research_pack.py" in command_text, payload["recommended_next_commands"]
    assert "--source-registry templates/source_registry.json" in command_text, payload["recommended_next_commands"]


def test_workflow_next_empty_run_returns_input_card_missing(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    payload = next_payload(run_dir)
    assert payload["current_stage"] == "MATERIAL_INTAKE_MISSING_OR_FAILED", payload
    assert "scripts/gate_report.py" in payload["gate_report_command"], payload


def test_gate_report_empty_run_groups_material_root_causes(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    report = build_gate_report(run_dir)
    assert report["schema_version"] == "gate_report_v1", report
    assert report["report_role"] == "dashboard_triage_not_new_gate", report
    assert report["overall"] == "needs_fix", report
    assert report["hard_block_final_delivery"] is True, report
    assert {group["artifact"] for group in report["root_cause_groups"]} == {
        "artifacts/material_manifest.json",
        "artifacts/material_extracts.json",
        "artifacts/source_classification.json",
    }
    assert {group["repair_owner"] for group in report["root_cause_groups"]} == {"material-intake"}
    command_text = "\n".join(item["command"] for item in report["public_next_actions"])
    assert "skills/material-intake/scripts/ingest_materials.py" in command_text
    assert "/skills/material-intake/skills/material-intake/" not in command_text


def _seed_full_research_ready(run_dir: Path) -> None:
    """Seed all artifacts needed to pass research/issue/deck gates."""
    _seed_research_pack_ready(run_dir)
    _seed_boundary_loop_ready(run_dir)
    artifacts = run_dir / "artifacts"
    # Research pack file and validation
    (run_dir / "industry_research_pack.md").write_text("# Research Pack\n", encoding="utf-8")
    _write_json(artifacts / "research_pack_validation.json", {"is_valid": True, "errors": [], "warnings": []})
    # Issue analysis
    _write_json(run_dir / "industry_issue_analysis.json", {"issues": []})
    _write_json(artifacts / "issue_analysis_validation.json", {"is_valid": True, "errors": [], "warnings": []})
    # Template registry
    _write_json(run_dir / "template_registry.json", {"slides": []})
    _write_json(artifacts / "template_registry_validation.json", {"is_valid": True, "errors": [], "warnings": []})
    # Deck blueprint
    _write_json(run_dir / "deck_blueprint.json", {"slides": []})
    _write_json(artifacts / "deck_blueprint_validation.json", {"is_valid": True, "errors": [], "warnings": []})
    # Page evidence contract
    _write_json(run_dir / "page_evidence_contract.json", {"pages": []})
    _write_json(artifacts / "page_evidence_contract_validation.json", {"is_valid": True, "errors": [], "warnings": []})
    # Renderer spec
    _write_json(
        run_dir / "renderer_spec.json",
        {"schema_version": "renderer_spec_v1", "slides": [], "layout_version": "v1"},
    )
    _write_json(artifacts / "renderer_spec_validation.json", {"is_valid": True, "errors": [], "warnings": []})
    # Chart metric binding
    _write_json(artifacts / "chart_metric_binding_validation.json", {"is_valid": True, "errors": [], "warnings": []})
    # Content quality
    _write_json(artifacts / "content_quality_validation.json", {"is_valid": True, "errors": [], "warnings": []})
    # Pre-PPT stage gate
    _write_json(artifacts / "stage_gate_pre_ppt_validation.json", {"is_valid": True})
    # Replacement dict
    _write_json(run_dir / "replacement_dict.json", {"tokens": {}})
    _write_json(artifacts / "replacement_dict_validation.json", {"is_valid": True, "errors": [], "warnings": []})
    # Filled PPT
    (run_dir / "industry_section_filled_clean.pptx").write_bytes(b"PK\x03\x04")
    _write_json(run_dir / "filled_ppt_validation.json", {"is_valid": True, "errors": [], "warnings": []})
    # Final delivery
    _write_json(artifacts / "final_delivery_validation.json", {"is_valid": True, "client_ready": True, "errors": [], "warnings": []})


def test_workflow_next_renderer_spec_without_template_profile(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    _seed_full_research_ready(run_dir)
    payload = next_payload(run_dir)
    assert payload["current_stage"] == "TEMPLATE_PROFILE_MISSING_OR_FAILED", payload
    command_text = "\n".join(item["command"] for item in payload["recommended_next_commands"])
    assert "template_analyzer.py" in command_text


def test_workflow_next_template_profile_without_template_fit(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    _seed_full_research_ready(run_dir)
    artifacts = run_dir / "artifacts"
    _write_json(
        artifacts / "template_profile.json",
        {
            "schema_version": "template_profile_v1",
            "template_file": str(ROOT / "runtime/ib-pitchdeck-agent-industry-section/assets/industry_section_template_master.pptx"),
            "layout": {},
            "visual_style": {},
        },
    )
    payload = next_payload(run_dir)
    assert payload["current_stage"] == "TEMPLATE_FIT_FAILED", payload
    command_text = "\n".join(item["command"] for item in payload["recommended_next_commands"])
    assert "template_fit.py" in command_text
