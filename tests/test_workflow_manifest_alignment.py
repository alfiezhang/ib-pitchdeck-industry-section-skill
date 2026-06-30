#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime" / "ib-pitchdeck-agent-industry-section"
DEVTOOLS = ROOT / "devtools"


def _manifest() -> dict:
    return json.loads((RUNTIME / "configs" / "artifact_manifest.json").read_text(encoding="utf-8"))


def test_artifact_manifest_covers_formal_artifact_flow() -> None:
    manifest = _manifest()
    artifacts = manifest["artifacts"]
    required_path = [
        "material_manifest",
        "material_extracts",
        "research_evidence_db",
        "industry_scope_pack",
        "industry_boundary_qc",
        "formal_search_plan",
        "search_log",
        "source_archive",
        "formal_research_execution_report",
        "research_pack",
        "banker_page_pack",
        "research_request_queue",
        "deck_blueprint",
        "template_profile",
        "template_fit_validation",
        "template_fit_plan",
        "page_evidence_contract",
        "renderer_spec",
        "filled_ppt",
        "final_delivery",
    ]

    missing = [name for name in required_path if name not in artifacts]
    assert not missing
    for name in required_path:
        assert artifacts[name].get("path"), name


def test_artifact_manifest_layers_reference_known_artifacts() -> None:
    manifest = _manifest()
    known = set(manifest["artifacts"])
    unknown: list[str] = []

    for layer in manifest["artifact_layers"].values():
        unknown.extend([name for name in layer.get("artifacts", []) if name not in known])
    for role in manifest["role_layers"].values():
        unknown.extend([name for name in role.get("artifacts", []) if name not in known])
    assert "gates" not in manifest
    assert "checkpoints" not in manifest
    assert "validation" not in manifest["artifact_layers"]
    assert "readiness" in manifest["artifact_layers"]
    assert not any("validation" in artifact for artifact in manifest["artifacts"].values())
    for review in manifest["readiness_reviews"]:
        artifact = review.get("artifact", "")
        if artifact not in known:
            unknown.append(artifact)

    assert not sorted(set(unknown))


def test_authoring_layer_contains_only_llm_editable_workbenches() -> None:
    manifest = _manifest()
    authoring = set(manifest["artifact_layers"]["authoring"]["artifacts"])
    derived = set(manifest["artifact_layers"]["derived"]["artifacts"])

    expected_authoring = {
        "material_extracts",
        "input_card",
        "industry_scope_pack",
        "formal_search_plan",
        "executable_search_batch",
        "research_graph_state",
        "research_evidence_db",
        "research_request_queue",
        "banker_page_pack",
    }
    must_stay_derived = {
        "material_manifest",
        "source_classification",
        "coverage_map",
        "search_log",
        "formal_research_execution_report",
        "coverage_accounting",
        "deck_blueprint",
        "page_evidence_contract",
        "renderer_spec",
        "filled_ppt",
    }

    assert authoring == expected_authoring
    assert must_stay_derived <= derived
    assert not (authoring & must_stay_derived)


def test_industry_boundary_qc_is_optional_not_default_authoring_path() -> None:
    manifest = _manifest()

    authoring_layer = manifest["artifact_layers"]["authoring"]
    assert "main_llm_authoring_path" not in authoring_layer
    assert "material_extracts" not in authoring_layer["from_scratch_context_sequence"]
    assert "industry_boundary_qc" not in authoring_layer["from_scratch_context_sequence"]
    assert "industry_boundary_qc" not in manifest["artifact_layers"]["authoring"]["artifacts"]
    assert "industry_boundary_qc" in manifest["artifact_layers"]["diagnostic"]["artifacts"]
    assert "industry_boundary_qc" in manifest["role_layers"]["industry-scoping"]["artifacts"]


def test_template_registry_is_not_a_banker_page_pack_authoring_dependency() -> None:
    manifest = _manifest()
    banker_inputs = set(manifest["artifacts"]["banker_page_pack"].get("inputs", []))
    derived = set(manifest["artifact_layers"]["derived"]["artifacts"])

    assert "template_registry" in derived
    assert "template_registry" not in banker_inputs


def test_final_delivery_does_not_require_compiled_renderer_artifacts() -> None:
    manifest = _manifest()
    final_delivery = manifest["artifacts"]["final_delivery"]
    inputs = set(final_delivery.get("inputs", []))
    optional_trace_inputs = set(final_delivery.get("optional_trace_inputs", []))
    internal_compile_artifacts = {"deck_blueprint", "page_evidence_contract", "renderer_spec"}

    assert {"input_card", "research_evidence_db", "banker_page_pack", "filled_ppt"} <= inputs
    assert not (internal_compile_artifacts & inputs)
    assert internal_compile_artifacts <= optional_trace_inputs


def test_filled_ppt_manifest_supports_direct_composition_path() -> None:
    manifest = _manifest()
    filled_ppt = manifest["artifacts"]["filled_ppt"]
    inputs = set(filled_ppt.get("inputs", []))
    optional_trace_inputs = set(filled_ppt.get("optional_trace_inputs", []))
    internal_compile_artifacts = {"page_evidence_contract", "renderer_spec"}

    assert {"banker_page_pack", "template_selection", "template_profile"} <= inputs
    assert not (internal_compile_artifacts & inputs)
    assert internal_compile_artifacts <= optional_trace_inputs


def test_research_request_queue_depends_on_page_pack_not_optional_boundary_review() -> None:
    manifest = _manifest()
    queue_inputs = set(manifest["artifacts"]["research_request_queue"].get("inputs", []))

    assert {"banker_page_pack", "research_evidence_db"} <= queue_inputs
    assert "industry_boundary_qc" not in queue_inputs
    assert "Optional LLM boundary review signal" in manifest["artifacts"]["industry_boundary_qc"]["purpose"]


def test_artifact_owners_do_not_present_scripts_as_content_owners() -> None:
    manifest = _manifest()
    forbidden_exact = {"script", "compiler", "builder"}
    bad = [
        name
        for name, artifact in manifest["artifacts"].items()
        if str(artifact.get("owner") or "") in forbidden_exact
        or str(artifact.get("owner") or "").startswith("script_")
    ]

    assert not bad


def test_artifact_manifest_declares_owner_action_first_guidance() -> None:
    manifest = _manifest()
    readiness_reviews = {review["review"]: review["artifact"] for review in manifest["readiness_reviews"]}

    assert "command index" in manifest["description"]
    assert "owner-action first" in manifest["operator_guidance"]
    assert "Helper tools live in pipeline/status helpers" in manifest["operator_guidance"]
    assert "LLM roles author boundaries, evidence decisions, page arguments, and readiness calls" in manifest["operator_guidance"]
    assert "context sequence is only a from-scratch orientation" in manifest["operator_guidance"]
    assert "repair that source of truth instead of recreating earlier workbenches" in manifest["operator_guidance"]
    assert "not a requirement to backfill earlier workbenches" in manifest["artifact_layers"]["authoring"]["description"]
    assert "from_scratch_context_sequence" in manifest["artifact_layers"]["authoring"]
    assert "main_llm_authoring_path" not in manifest["artifact_layers"]["authoring"]
    assert "readiness_reviews" in manifest
    assert readiness_reviews == {
        "pre_ppt": "pre_ppt_readiness",
        "final_delivery": "final_delivery",
    }
    final_review = next(review for review in manifest["readiness_reviews"] if review["review"] == "final_delivery")
    assert final_review["require_final_delivery_authorization"] is True
    assert "require_client_ready" not in final_review
    assert "checkpoints" not in manifest


def test_artifact_manifest_does_not_expose_command_recipes() -> None:
    manifest = _manifest()
    artifacts = manifest["artifacts"]
    forbidden_keys = {"builder", "validator", "helper_command", "review_command", "check_output", "validation"}

    offenders = {
        name: sorted(forbidden_keys & set(artifact))
        for name, artifact in artifacts.items()
        if forbidden_keys & set(artifact)
    }
    assert offenders == {}


def test_artifact_manifest_does_not_keep_failure_memory_side_channel() -> None:
    manifest = _manifest()
    manifest_text = (RUNTIME / "configs" / "artifact_manifest.json").read_text(encoding="utf-8")
    workflow_text = (RUNTIME / "scripts" / "pipeline.py").read_text(encoding="utf-8")

    assert "failure_memory" not in manifest["artifacts"]
    assert "failure_memory" not in manifest_text
    assert "failure_memory" not in workflow_text
    assert "append_failure" not in workflow_text


def test_artifact_manifest_descriptions_use_owner_action_not_gate_language() -> None:
    manifest_text = (RUNTIME / "configs" / "artifact_manifest.json").read_text(encoding="utf-8")

    assert "boundary validation" not in manifest_text
    assert "claim can be promoted" not in manifest_text
    assert "claim permission" not in manifest_text
    assert "permission decision" not in manifest_text
    assert "boundary review" in manifest_text
    assert "page inclusion, headline assertiveness, key data audit, or exhibit readiness" in manifest_text


def test_industry_scope_pack_is_boundary_card() -> None:
    manifest = _manifest()
    scope_artifact = manifest["artifacts"]["industry_scope_pack"]

    assert scope_artifact["owner"] == "industry-scoping"
    assert scope_artifact["purpose"] == "brief boundary card"
    assert scope_artifact["schema_version"] == "industry_scope_pack_boundary_card"
    assert not (RUNTIME / "configs" / "authoring_shape_hints").exists()


def test_status_surface_owns_helper_check_commands() -> None:
    workflow_text = (RUNTIME / "scripts" / "pipeline.py").read_text(encoding="utf-8")
    manifest = _manifest()

    assert "scripts/pipeline.py review" in workflow_text
    assert "helper_check_command" in workflow_text
    assert not any("review_command" in artifact for artifact in manifest["artifacts"].values())


def test_development_package_scripts_are_outside_runtime() -> None:
    manifest = _manifest()
    assert "skill_package_validation" not in manifest["artifacts"]
    assert "legacy_install_audit" not in manifest["artifacts"]
    assert not (RUNTIME / "scripts" / "package_skill.py").exists()
    assert not (RUNTIME / "scripts" / "install_skill_local.py").exists()
    assert not (RUNTIME / "scripts" / "remove_legacy_installs.py").exists()
    assert (DEVTOOLS / "package" / "package_skill.py").exists()
    assert (DEVTOOLS / "install" / "install_skill_local.py").exists()
    assert (DEVTOOLS / "install" / "remove_legacy_installs.py").exists()
