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
        "replacement_dict",
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
    for gate in manifest["gates"]:
        artifact = gate.get("artifact", "")
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
        "industry_boundary_qc",
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
        "replacement_dict",
        "filled_ppt",
    }

    assert authoring == expected_authoring
    assert must_stay_derived <= derived
    assert not (authoring & must_stay_derived)


def test_research_graph_prepare_is_operator_builder() -> None:
    manifest = _manifest()
    artifacts = manifest["artifacts"]

    assert artifacts["formal_search_plan"]["builder"].endswith("pipeline.py research-prepare")
    assert artifacts["coverage_map"]["builder"].endswith("pipeline.py research-prepare")
    assert artifacts["executable_search_batch"]["builder"].endswith("pipeline.py research-prepare")


def test_industry_scope_pack_is_boundary_card() -> None:
    manifest = _manifest()
    scope_artifact = manifest["artifacts"]["industry_scope_pack"]
    template = json.loads((RUNTIME / "configs" / "artifact_templates" / "industry_scope_pack.template.json").read_text(encoding="utf-8"))

    assert scope_artifact["owner"] == "industry-scoping"
    assert scope_artifact["purpose"] == "brief boundary card"
    assert scope_artifact["schema_version"] == "industry_scope_pack_boundary_card"
    assert template["schema_version"] == "industry_scope_pack_boundary_card"
    assert "llm_definition_draft" not in template
    assert "handoff_to_research" in template


def test_status_and_manifest_use_unified_validator() -> None:
    workflow_text = (RUNTIME / "scripts" / "pipeline.py").read_text(encoding="utf-8")
    manifest = _manifest()

    assert "scripts/pipeline.py validate" in workflow_text
    validators = [
        artifact.get("validator", "")
        for artifact in manifest["artifacts"].values()
        if artifact.get("validator")
    ]
    assert validators
    assert all("scripts/pipeline.py validate" in validator for validator in validators)


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
