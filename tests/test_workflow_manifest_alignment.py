#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime" / "ib-pitchdeck-agent-industry-section"


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
        "source_reviews",
        "source_archive",
        "formal_research_execution_report",
        "research_pack",
        "hypothesis_store",
        "research_request_queue",
        "incremental_search_plan",
        "page_argument_pack",
        "issue_analysis",
        "deck_blueprint",
        "template_profile",
        "template_fit_validation",
        "template_fit_plan",
        "page_evidence_contract",
        "renderer_spec",
        "replacement_dict",
        "filled_ppt",
        "final_delivery",
        "skill_package_validation",
        "legacy_install_audit",
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


def test_state_report_commands_generate_incremental_and_template_fit_plan() -> None:
    workflow_text = (RUNTIME / "scripts" / "state_report.py").read_text(encoding="utf-8")

    assert "--incremental-search-plan {{run_dir}}/artifacts/incremental_search_plan.json" in workflow_text
    assert "--fit-plan-output {{run_dir}}/artifacts/template_fit_plan.json" in workflow_text


def test_runtime_package_scripts_for_packaging_and_legacy_audit_are_registered() -> None:
    manifest = _manifest()
    package = manifest["artifacts"]["skill_package_validation"]
    legacy = manifest["artifacts"]["legacy_install_audit"]

    assert package["builder"] == "scripts/qc/validators/system/validate_skill_package.py"
    assert legacy["builder"] == "scripts/audit_legacy_installs.py"
    assert (RUNTIME / "scripts" / "package_skill.py").exists()
    assert (RUNTIME / "scripts" / "install_skill_local.py").exists()
    assert (RUNTIME / "scripts" / "remove_legacy_installs.py").exists()
