from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "runtime" / "ib-pitchdeck-agent-industry-section" / "scripts"
DEVTOOLS_DIAGNOSTICS = ROOT / "devtools" / "diagnostics"
for path in (SCRIPT_DIR, DEVTOOLS_DIAGNOSTICS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from conftest import _rewrite_plan_queries_for_contract_test  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _seed_material_intake(run_dir: Path) -> None:
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "material_manifest.json").write_text(
        '{"schema_version":"material_manifest_v1","created_at":"2026-01-01T00:00:00+00:00","policy_context":"pre_mandate_client_pitch","materials":[{"material_id":"MAT-001","source_type":"project_specific_material","source_access":"user_provided","file_path_or_url":"artifacts/material_texts/sample_contract.txt","material_kind":"text","extraction_status":"complete","extraction_limitations":"none","can_be_used_as_evidence":true}],"source_type_policy":{}}',
        encoding="utf-8",
    )
    (artifacts / "source_classification.json").write_text(
        '{"schema_version":"source_classification_v1","generated_at":"2026-01-01T00:00:00+00:00","materials":[{"material_id":"MAT-001","source_type":"project_specific_material","source_access":"user_provided","file_path_or_url":"artifacts/material_texts/sample_contract.txt","source_hash":"","source_date":"2026-01-01T00:00:00+00:00"}]}',
        encoding="utf-8",
    )
    (artifacts / "material_extracts.json").write_text(
        '{"schema_version":"material_extracts_v1","materials_source":"artifacts/material_manifest.json","extracts":[{"material_id":"MAT-001","source_type":"project_specific_material","source_access":"user_provided","file_path_or_url":"artifacts/material_texts/sample_contract.txt","extracted_text_path":"artifacts/material_texts/MAT-001.txt","extraction_status":"complete","extraction_limitations":"none","can_be_used_as_evidence":true,"quoted_excerpts":[]}]',
        encoding="utf-8",
    )
    (artifacts / "material_manifest_validation.json").write_text('{"is_valid": true}', encoding="utf-8")
    (artifacts / "material_extracts_validation.json").write_text('{"is_valid": true}', encoding="utf-8")


def _seed_boundary_loop_ready(run_dir: Path) -> None:
    artifacts = run_dir / "artifacts"
    (artifacts / "boundary_loop_status.json").write_text(
        '{"schema_version": "boundary_loop_status_v1", "status": "boundary_ready", "boundary_loop_status": "boundary_ready", '
        '"is_valid": true, "created_at": "2026-01-01T00:00:00Z", "errors": [], "warnings": [], '
        '"repair_actions": [], "boundary_inputs": {"scope_pack": true, "material_extracts": true, "research_evidence_db": true}}',
        encoding="utf-8",
    )

import check_runtime_dependencies  # noqa: E402
import pipeline  # noqa: E402
from doctor_runtime import runtime_diagnostic_payload  # noqa: E402
from gate_guard import _looks_like_formal_run  # noqa: E402
from ib_research_graph import build_plan  # noqa: E402
from pipeline import PipelineError, finalize  # noqa: E402
from validate_final_delivery import _looks_like_research_error, _template_layer_validation  # noqa: E402
from validate_formal_search_plan import validate as validate_formal_search_plan  # noqa: E402
from validate_input_card import validate as validate_input_card  # noqa: E402
from validate_run_state import validate_run_state  # noqa: E402
from state_report import next_payload  # noqa: E402


def test_finalize_short_circuits_on_validation_failure(tmp_path: Path) -> None:
    run_dir = tmp_path / "attempt_001"
    run_dir.mkdir(parents=True)

    call_count = {"run": 0}

    def fake_run(*_args: object, **_kwargs: object) -> None:
        call_count["run"] += 1

    original_run = pipeline._run
    original_run_returncode = pipeline._run_returncode

    try:
        pipeline._run = fake_run
        pipeline._run_returncode = lambda *args, **kwargs: 1  # validation failed
        try:
            finalize(run_dir, "python3", require_client_ready=False)
        except PipelineError:
            pass
        else:
            raise AssertionError("finalize should raise PipelineError when validate_final_delivery fails")
    finally:
        pipeline._run = original_run
        pipeline._run_returncode = original_run_returncode

    assert call_count["run"] == 0, f"generate_run_quality_summary/update_runs_index should not run on failure: {call_count['run']}"
    assert (run_dir / "NOT_CLIENT_READY_OUTPUT.txt").exists()
    assert not (run_dir.parent / "ACTIVE_ATTEMPT.txt").exists()


def test_json_helper_raises_on_corrupt_payload(tmp_path: Path) -> None:
    bad_json = tmp_path / "artifacts" / "run_flags.json"
    bad_json.parent.mkdir(parents=True, exist_ok=True)
    bad_json.write_text("{", encoding="utf-8")

    try:
        pipeline._json(bad_json)
    except PipelineError as exc:
        assert "Invalid JSON" in str(exc)
    else:
        raise AssertionError("corrupt run_flags.json must raise PipelineError")


def test_research_error_matching_is_specific() -> None:
    assert _looks_like_research_error("missing formal search instruction IDs for high-priority subissue")
    assert _looks_like_research_error("search_plan execution not complete")
    assert _looks_like_research_error("industry_research_pack was not generated")
    assert _looks_like_research_error("Missing source classification result")
    assert not _looks_like_research_error("source file path is not readable")
    assert not _looks_like_research_error("renderer spec schema invalid")


def test_formal_search_plan_rejects_query_fields_in_plan() -> None:
    plan = build_plan({}, {})
    _rewrite_plan_queries_for_contract_test(plan)
    for issue in plan["issue_search_plan"]:
        if issue.get("priority") == "high":
            issue["search_instructions"][0]["query"] = "sample sector official market query"
            break
    errors, warnings = validate_formal_search_plan(plan)
    assert any("executable query fields belong only" in error for error in errors)
    assert not any("high-priority issue has only" in warning for warning in warnings)


def test_formal_looks_like_formal_run_requires_multiple_markers(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)

    assert not _looks_like_formal_run(run_dir)
    (run_dir / "input_card.json").write_text("{}", encoding="utf-8")
    assert not _looks_like_formal_run(run_dir)


def test_template_layer_validation_detects_missing_and_invalid_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / "attempt_001"
    run_dir.mkdir(parents=True)
    repair_targets: list[dict[str, object]] = []
    errors, warnings = _template_layer_validation(run_dir, repair_targets)
    assert any("missing artifacts/template_profile.json" in error for error in errors)
    assert any("missing artifacts/template_fit_validation.json" in error for error in errors)
    assert any(
        bool(target.get("repair_target_artifact"))
        for target in repair_targets
    )
    assert warnings == []

    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "template_profile.json").write_text(
        json.dumps(
            {
                "schema_version": "template_profile_v1",
                "template_file": "assets/industry_section_template_master.pptx",
                "layout": {},
                "visual_style": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (artifacts / "template_fit_validation.json").write_text(
        json.dumps(
            {
                "schema_version": "template_fit_v1",
                "is_valid": True,
                "renderer_spec": str(run_dir / "renderer_spec.json"),
                "template_profile": str(artifacts / "template_profile.json"),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    repair_targets = []
    errors, warnings = _template_layer_validation(run_dir, repair_targets)
    assert not errors
    assert not warnings

    (artifacts / "research_evidence_db.json").write_text("{}", encoding="utf-8")
    (artifacts / "formal_search_plan.json").write_text("{}", encoding="utf-8")
    assert _looks_like_formal_run(run_dir)


def test_runtime_dependency_payload_exposes_search_and_paid_flags() -> None:
    provider_payload = check_runtime_dependencies.get_search_provider_payload()
    pdf_payload = check_runtime_dependencies.get_pdf_extraction_payload()
    doctor_payload = runtime_diagnostic_payload()
    assert provider_payload["search_providers"] == doctor_payload["search_providers"]
    assert provider_payload["search_provider_details"] == doctor_payload["search_provider_details"]
    assert pdf_payload["has_pdf_extraction"] == doctor_payload["has_pdf_extraction"]
    assert "is_ready_for_e2e_research" in doctor_payload
    assert "has_search_provider" in doctor_payload
    assert doctor_payload["manual_source_mode_supported"] is True
    assert doctor_payload["manual_source_mode_is_fallback"] is False
    assert doctor_payload["paid_search_optional"] is True


def test_empty_run_returns_input_card_missing(tmp_path: Path) -> None:
    run_dir = tmp_path / "empty_run"
    run_dir.mkdir(parents=True)
    state = validate_run_state(run_dir)
    assert state["current_stage"] == "MATERIAL_INTAKE_MISSING_OR_FAILED", state


def test_template_profile_requires_renderer_spec(tmp_path: Path) -> None:
    """Template profile check must not fire when renderer_spec.json does not exist."""
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    artifacts = run_dir / "artifacts"
    artifacts.mkdir()
    # Seed input card so INPUT_CARD_MISSING doesn't fire
    (run_dir / "input_card.json").write_text("{}", encoding="utf-8")
    (artifacts / "input_card_validation.json").write_text(
        '{"is_valid": true}', encoding="utf-8"
    )
    (artifacts / "material_manifest.json").write_text(
        '{"schema_version":"material_manifest_v1","created_at":"2026-01-01T00:00:00+00:00","policy_context":"pre_mandate_client_pitch","materials":[{"material_id":"MAT-001","source_type":"project_specific_material","source_access":"user_provided","file_path_or_url":"artifacts/material_texts/sample_contract.txt","material_kind":"text","extraction_status":"complete","extraction_limitations":"none","can_be_used_as_evidence":true}],"source_type_policy":{}}',
        encoding="utf-8",
    )
    (artifacts / "source_classification.json").write_text(
        '{"schema_version":"source_classification_v1","generated_at":"2026-01-01T00:00:00+00:00","materials":[{"material_id":"MAT-001","source_type":"project_specific_material","source_access":"user_provided","file_path_or_url":"artifacts/material_texts/sample_contract.txt","source_hash":"","source_date":"2026-01-01T00:00:00+00:00"}]}',
        encoding="utf-8",
    )
    (artifacts / "material_extracts.json").write_text(
        '{"schema_version":"material_extracts_v1","materials_source":"artifacts/material_manifest.json","extracts":[{"material_id":"MAT-001","source_type":"project_specific_material","source_access":"user_provided","file_path_or_url":"artifacts/material_texts/sample_contract.txt","extracted_text_path":"artifacts/material_texts/MAT-001.txt","extraction_status":"complete","extraction_limitations":"none","can_be_used_as_evidence":true,"extracted_facts":[],"extracted_metrics":[],"quoted_excerpts":[],"unknowns_or_conflicts":[],"claim_use_limitations":"synthetic","evidence_snapshot":"synthetic"}]}',
        encoding="utf-8",
    )
    (artifacts / "material_manifest_validation.json").write_text('{"is_valid": true}', encoding="utf-8")
    (artifacts / "material_extracts_validation.json").write_text('{"is_valid": true}', encoding="utf-8")
    state = validate_run_state(run_dir)
    # Without renderer_spec, template checks should be skipped
    assert state["current_stage"] != "TEMPLATE_PROFILE_MISSING_OR_FAILED", state
    assert state["current_stage"] == "INDUSTRY_SCOPE_PACK_MISSING", state


def test_template_profile_defers_to_earlier_gates(tmp_path: Path) -> None:
    """Template profile check must not fire when earlier gates (e.g. scope_pack) are missing."""
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    artifacts = run_dir / "artifacts"
    artifacts.mkdir()
    (run_dir / "input_card.json").write_text("{}", encoding="utf-8")
    (artifacts / "input_card_validation.json").write_text('{"is_valid": true}', encoding="utf-8")
    (artifacts / "material_manifest.json").write_text(
        '{"schema_version":"material_manifest_v1","created_at":"2026-01-01T00:00:00+00:00","policy_context":"pre_mandate_client_pitch","materials":[{"material_id":"MAT-001","source_type":"project_specific_material","source_access":"user_provided","file_path_or_url":"artifacts/material_texts/sample_contract.txt","material_kind":"text","extraction_status":"complete","extraction_limitations":"none","can_be_used_as_evidence":true}],"source_type_policy":{}}',
        encoding="utf-8",
    )
    (artifacts / "source_classification.json").write_text(
        '{"schema_version":"source_classification_v1","generated_at":"2026-01-01T00:00:00+00:00","materials":[{"material_id":"MAT-001","source_type":"project_specific_material","source_access":"user_provided","file_path_or_url":"artifacts/material_texts/sample_contract.txt","source_hash":"","source_date":"2026-01-01T00:00:00+00:00"}]}',
        encoding="utf-8",
    )
    (artifacts / "material_extracts.json").write_text(
        '{"schema_version":"material_extracts_v1","materials_source":"artifacts/material_manifest.json","extracts":[{"material_id":"MAT-001","source_type":"project_specific_material","source_access":"user_provided","file_path_or_url":"artifacts/material_texts/sample_contract.txt","extracted_text_path":"artifacts/material_texts/MAT-001.txt","extraction_status":"complete","extraction_limitations":"none","can_be_used_as_evidence":true,"extracted_facts":[],"extracted_metrics":[],"quoted_excerpts":[],"unknowns_or_conflicts":[],"claim_use_limitations":"synthetic","evidence_snapshot":"synthetic"}]}',
        encoding="utf-8",
    )
    (artifacts / "material_manifest_validation.json").write_text('{"is_valid": true}', encoding="utf-8")
    (artifacts / "material_extracts_validation.json").write_text('{"is_valid": true}', encoding="utf-8")
    (run_dir / "renderer_spec.json").write_text("{}", encoding="utf-8")
    state = validate_run_state(run_dir)
    # scope_pack is missing, so it fires before template profile
    assert state["current_stage"] == "INDUSTRY_SCOPE_PACK_MISSING", state


def test_template_profile_fires_after_renderer_spec(tmp_path: Path) -> None:
    """Template profile check must fire right after renderer_spec passes, not after chart/content/final gates."""
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    artifacts = run_dir / "artifacts"
    artifacts.mkdir()
    _seed_material_intake(run_dir)
    # Seed everything through renderer_spec
    (run_dir / "input_card.json").write_text("{}", encoding="utf-8")
    (artifacts / "input_card_validation.json").write_text('{"is_valid": true}', encoding="utf-8")
    (artifacts / "industry_scope_pack.json").write_text("{}", encoding="utf-8")
    _write_json(
        artifacts / "industry_boundary_qc.json",
        {
            "schema_version": "industry_boundary_qc_v1",
            "decision": "pass",
            "boundary_quality_rationale": "Synthetic boundary QC pass for renderer-order regression fixture.",
            "validated_scope": {
                "working_market": "sample sector",
                "parent_market": "sample parent market",
                "broader_market": "sample broader market",
            },
            "areas_confirmed": ["working market"],
            "areas_uncertain": [],
            "excluded_scope_confirmed": ["excluded adjacent scope"],
            "boundary_validation_requests": [],
            "formal_research_allowed_scope": ["sample sector"],
            "do_not_research_as_market_scope": ["sample adjacent scope"],
        },
    )
    (artifacts / "industry_scope_pack_validation.json").write_text('{"is_valid": true}', encoding="utf-8")
    (artifacts / "formal_search_plan.json").write_text("{}", encoding="utf-8")
    (artifacts / "formal_search_plan_validation.json").write_text('{"is_valid": true}', encoding="utf-8")
    (artifacts / "executable_search_batch.json").write_text('{"schema_version": "search_batch_v1", "batches": []}', encoding="utf-8")
    (artifacts / "executable_search_batch_validation.json").write_text('{"is_valid": true}', encoding="utf-8")
    (artifacts / "source_archive").mkdir(parents=True, exist_ok=True)
    (artifacts / "source_archive" / "source_archive_index.json").write_text("{}", encoding="utf-8")
    (artifacts / "source_archive_validation.json").write_text('{"is_valid": true}', encoding="utf-8")
    (artifacts / "formal_research_execution_report.json").write_text("{}", encoding="utf-8")
    (artifacts / "formal_research_execution_validation.json").write_text('{"is_valid": true}', encoding="utf-8")
    (artifacts / "stage_gate_pre_research_pack_validation.json").write_text('{"is_valid": true}', encoding="utf-8")
    (artifacts / "research_evidence_db.json").write_text("{}", encoding="utf-8")
    (artifacts / "research_evidence_db_validation.json").write_text('{"is_valid": true}', encoding="utf-8")
    (run_dir / "industry_research_pack.md").write_text("# Pack\n", encoding="utf-8")
    (artifacts / "research_pack_validation.json").write_text('{"is_valid": true}', encoding="utf-8")
    (run_dir / "industry_issue_analysis.json").write_text("{}", encoding="utf-8")
    (artifacts / "issue_analysis_validation.json").write_text('{"is_valid": true}', encoding="utf-8")
    _write_json(
        artifacts / "hypothesis_store.json",
        {
            "schema_version": "hypothesis_store_v1",
            "hypotheses": [],
            "resolution_summary": "No unresolved, directional, or thinly supported judgments identified.",
        },
    )
    _write_json(artifacts / "hypothesis_store_validation.json", {"is_valid": True, "errors": [], "warnings": []})
    _write_json(
        artifacts / "page_argument_pack.json",
        {
            "schema_version": "page_argument_pack_v1",
            "page_arguments": [
                {
                    "page_argument_id": "PA-001",
                    "source_issue_analysis_id": "IA-001",
                    "page_argument": "Fixture page argument bridges issue analysis to deck generation.",
                    "evidence_status": "directional",
                    "allowed_deck_usage": "body_only",
                }
            ],
        },
    )
    _write_json(artifacts / "page_argument_pack_validation.json", {"is_valid": True, "errors": [], "warnings": []})
    (run_dir / "template_registry.json").write_text("{}", encoding="utf-8")
    (artifacts / "template_registry_validation.json").write_text('{"is_valid": true}', encoding="utf-8")
    (run_dir / "deck_blueprint.json").write_text("{}", encoding="utf-8")
    (artifacts / "deck_blueprint_validation.json").write_text('{"is_valid": true}', encoding="utf-8")
    (run_dir / "page_evidence_contract.json").write_text("{}", encoding="utf-8")
    (artifacts / "page_evidence_contract_validation.json").write_text('{"is_valid": true}', encoding="utf-8")
    (run_dir / "renderer_spec.json").write_text("{}", encoding="utf-8")
    (artifacts / "renderer_spec_validation.json").write_text('{"is_valid": true}', encoding="utf-8")
    _seed_boundary_loop_ready(run_dir)
    # No template_profile.json → should fire right after renderer_spec
    state = validate_run_state(run_dir)
    assert state["current_stage"] == "TEMPLATE_PROFILE_MISSING_OR_FAILED", state
    assert state["blocking_gate"] == "template_profile"


def test_source_materials_validation_catches_errors() -> None:
    data = {
        "_provenance": {
            "request_language": "English",
            "user_provided_paths": ["source_materials"],
            "normalized_metadata_paths": [],
        },
        "target_company": "TestCo",
        "industry": "tech",
        "geography": "US",
        "language": "English",
        "source_materials": [
            {
                "source_name": "Report",
                "source_type": "company_material",
                "source_access": "public_search",
                "source_access_path": "",
                "notes": "some notes",
            },
            {
                "source_name": "",
                "source_type": "bad_type",
                "source_access": "user_provided",
                "source_access_path": "https://example.com",
                "notes": "",
            },
            {
                "source_name": "Bad URL",
                "source_type": "company_material",
                "source_access": "public_search",
                "source_access_path": "not a url",
                "notes": "",
            },
        ],
    }
    result = validate_input_card(data)
    assert not result["is_valid"]
    error_text = " ".join(result["errors"])
    assert "public_search" in error_text
    assert "bad_type" in error_text
    assert "not a valid URL" in error_text


def test_source_materials_skips_template_placeholder() -> None:
    data = {
        "_provenance": {
            "request_language": "English",
            "user_provided_paths": [],
            "normalized_metadata_paths": [],
        },
        "target_company": "",
        "industry": "",
        "geography": "",
        "language": "",
        "source_materials": [
            {
                "source_name": "",
                "source_type": "project_specific_material | user_curated_industry_report | other",
                "source_access": "user_provided | public_search",
                "source_access_path": "file path, internal path, or URL",
                "notes": "",
            }
        ],
    }
    result = validate_input_card(data)
    error_text = " ".join(result["errors"])
    assert "source_materials" not in error_text


def test_check_runtime_dependencies_source_registry_path() -> None:
    from check_runtime_dependencies import SOURCE_REGISTRY
    assert SOURCE_REGISTRY.exists(), f"SOURCE_REGISTRY path does not exist: {SOURCE_REGISTRY}"
    assert SOURCE_REGISTRY.name == "source_registry.json"
