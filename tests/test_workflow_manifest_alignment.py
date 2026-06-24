#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime" / "ib-pitchdeck-agent-industry-section"
DEVTOOLS = ROOT / "devtools"


def _manifest() -> dict:
    return json.loads((RUNTIME / "configs" / "artifact_manifest.json").read_text(encoding="utf-8"))


def test_artifact_manifest_covers_main_mental_path() -> None:
    manifest = _manifest()
    artifacts = manifest["artifacts"]
    required_path = [
        "material_manifest",
        "material_extracts",
        "repository_retrieval",
        "research_evidence_db",
        "industry_scope_pack",
        "boundary_loop_status",
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


def test_research_graph_prepare_is_operator_builder() -> None:
    manifest = _manifest()
    artifacts = manifest["artifacts"]

    assert artifacts["formal_search_plan"]["builder"].endswith("ib_research_graph.py prepare")
    assert artifacts["coverage_map"]["builder"].endswith("ib_research_graph.py prepare")
    assert artifacts["executable_search_batch"]["builder"].endswith("ib_research_graph.py prepare")


def test_industry_scope_pack_is_v2_boundary_card() -> None:
    manifest = _manifest()
    scope_artifact = manifest["artifacts"]["industry_scope_pack"]
    template = json.loads((RUNTIME / "configs" / "artifact_templates" / "industry_scope_pack.template.json").read_text(encoding="utf-8"))

    assert scope_artifact["owner"] == "industry-scoping"
    assert scope_artifact["purpose"] == "brief boundary card"
    assert scope_artifact["schema_version"] == "industry_scope_pack_v2"
    assert template["schema_version"] == "industry_scope_pack_v2"
    assert "llm_definition_draft" not in template
    assert "handoff_to_research" in template


def test_status_and_manifest_use_unified_validator() -> None:
    workflow_text = (RUNTIME / "scripts" / "status.py").read_text(encoding="utf-8")
    manifest = _manifest()

    assert "scripts/qc/validate_artifact.py" in workflow_text
    validators = [
        artifact.get("validator", "")
        for artifact in manifest["artifacts"].values()
        if artifact.get("validator")
    ]
    assert validators
    assert all("scripts/qc/validate_artifact.py" in validator for validator in validators)


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
