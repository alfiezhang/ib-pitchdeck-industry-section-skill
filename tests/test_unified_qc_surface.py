#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import subprocess
import sys
import zipfile
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
    assert not (SKILL_DIR / "configs/research_issue_taxonomy.json").exists()
    assert not (SKILL_DIR / "configs/page_type_rules.json").exists()
    assert not (SKILL_DIR / "configs/slide_layout_library.json").exists()
    assert not (SKILL_DIR / "scripts/_lib/layout_config.py").exists()
    assert not (SKILL_DIR / "scripts/_lib/material_extractors.py").exists()
    assert not (SKILL_DIR / "scripts/_lib/json_utils.py").exists()
    assert not (SKILL_DIR / "scripts/_lib/material_intake_common.py").exists()
    assert not (SKILL_DIR / "scripts/_lib/slide_registry.py").exists()
    assert not (SKILL_DIR / "scripts/_lib/renderer_token_source.py").exists()
    assert not (SKILL_DIR / "scripts/_lib/template_contract_utils.py").exists()
    assert not (SKILL_DIR / "scripts/_lib/unit_normalizer.py").exists()
    assert not (SKILL_DIR / "scripts/_lib/validation_common.py").exists()
    assert not (SKILL_DIR / "configs/workflow_policy.json").exists()
    assert not (SKILL_DIR / "scripts/template/template_fit.py").exists()
    assert not (SKILL_DIR / "schemas/issue_analysis_schema.json").exists()
    assert not (SKILL_DIR / "schemas/industry_scope_pack_v2_schema.json").exists()
    assert not (SKILL_DIR / "schemas/qc_repair_schema.json").exists()
    assert not (SKILL_DIR / "schemas/qc_warning_disposition_schema.json").exists()
    assert not (SKILL_DIR / "configs/authoring_shape_hints").exists()
    fixture_dir = SKILL_DIR.parents[1] / "tests" / "fixtures"
    assert not (fixture_dir / "valid_issue_analysis.json").exists()
    assert not (fixture_dir / "invalid_issue_analysis.json").exists()


def test_search_connectors_are_optional_not_packaged_requirements() -> None:
    requirements = (SKILL_DIR / "requirements.txt").read_text(encoding="utf-8")
    research_policy = (SKILL_DIR / "references/research_policy.md").read_text(encoding="utf-8")
    output = (SKILL_DIR / "references/output.md").read_text(encoding="utf-8")

    assert "python-pptx" in requirements
    assert "tavily" not in requirements.lower()
    assert "ddgs" not in requirements.lower()
    assert "duckduckgo" not in requirements.lower()
    assert "Python search connectors are optional" in research_policy
    assert "agent-native web search" in research_policy
    assert "Choose sources by evidence need rather than from a fixed source-pack registry" in research_policy
    assert "Strict runtime readiness should pause only for missing PPT/runtime imports" in output
    assert not (SKILL_DIR / "configs/source_registry.json").exists()
    assert "preferred_source_packs" not in research_policy


def test_runtime_readiness_treats_python_search_connectors_as_advisory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import pipeline

    def fake_import_check(_python_cmd: str, module_name: str) -> dict:
        if module_name in {"pptx", "lxml.etree"}:
            return {"module": module_name, "available": True, "version": "fixture", "error": ""}
        return {"module": module_name, "available": False, "version": "", "error": "fixture missing optional module"}

    monkeypatch.setattr(pipeline, "_python_import_check", fake_import_check)
    monkeypatch.setattr(pipeline, "_searxng_config", lambda: (False, ""))
    monkeypatch.setattr(pipeline.shutil, "which", lambda _name: None)

    payload, missing = pipeline._runtime_dependency_payload("python")

    assert missing == []
    assert payload["is_ready_for_ppt_pipeline"] is True
    assert payload["is_ready_for_e2e_research"] is True
    assert payload["python_connector_research_ready"] is False
    assert payload["search_connectors_optional"] is True
    assert payload["agent_native_web_search_expected"] is True
    assert payload["has_fallback_search"] is True

    stderr = pipeline._runtime_readiness_stderr(payload, missing)
    assert "WARN: No optional Python web-search connector" in stderr
    assert "WARN: No Python PDF extraction capability found" in stderr
    assert "ERROR: No configured web-search provider" not in stderr

    assert pipeline._check_runtime_readiness(tmp_path / "run", "python", strict=True) is True


def test_no_readiness_retry_side_channel_remains() -> None:
    runtime_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (SKILL_DIR / "scripts").rglob("*.py")
    )

    assert "readiness_retry_state" not in runtime_text
    assert "max_repair_cycles" not in runtime_text
    assert "workflow_policy" not in runtime_text
    assert "targeted_research_markers" not in runtime_text
    assert "client_ready_markers" not in runtime_text
    assert "research_limit_markers" not in runtime_text
    assert "_infer_readiness_from_note" not in runtime_text
    assert "clear_markers" not in runtime_text
    assert "blocking_markers" not in runtime_text
    assert "_boundary_review_blocks_prepare" not in runtime_text
    assert "_request_is_active" not in runtime_text
    assert "_research_request_is_active" not in runtime_text


def test_template_profile_is_runtime_generated_not_static_config() -> None:
    manifest = json.loads((SKILL_DIR / "configs/artifact_manifest.json").read_text(encoding="utf-8"))
    runtime_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (SKILL_DIR / "scripts").rglob("*.py")
    )

    assert not (SKILL_DIR / "configs/template_profile.json").exists()
    assert not (SKILL_DIR / "configs/layout_config.json").exists()
    assert manifest["artifacts"]["template_profile"]["path"] == "artifacts/template_profile.json"
    assert "configs/template_profile.json" not in runtime_text


def test_schema_surface_stays_small_and_purposeful() -> None:
    assert not (SKILL_DIR / "schemas").exists()
    assert not (SKILL_DIR / "configs/mechanical_schemas").exists()


def test_runtime_helper_surface_does_not_regrow_legacy_script_sprawl() -> None:
    scripts = [
        path.relative_to(SKILL_DIR).as_posix()
        for path in (SKILL_DIR / "scripts").rglob("*.py")
    ]
    assert len(scripts) <= 10


def test_runtime_has_no_empty_legacy_workflow_dirs() -> None:
    assert not (SKILL_DIR / "runs").exists()
    for path in (
        SKILL_DIR / "scripts/generation",
        SKILL_DIR / "scripts/industry-scoping",
        SKILL_DIR / "scripts/reasoning",
    ):
        assert not path.exists()


def test_pipeline_is_only_public_script_surface() -> None:
    assert not (SKILL_DIR / "configs/script_role_map.json").exists()

    guidance_paths = [SKILL_DIR / "SKILL.md", SKILL_DIR / "configs/artifact_manifest.json"]
    guidance_paths.extend((SKILL_DIR / "references").glob("*.md"))

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

    internal_script_ref = re.compile(r"scripts/(?!pipeline\.py\b)[A-Za-z0-9_-]+/[A-Za-z0-9_-]+\.py")
    hits: list[str] = []
    for path in guidance_paths:
        text = path.read_text(encoding="utf-8")
        for match in internal_script_ref.finditer(text):
            hits.append(f"{path.relative_to(SKILL_DIR)}: {match.group(0)}")

    assert hits == []


def test_pipeline_does_not_use_source_marker_integrity_gate() -> None:
    pipeline_text = (SKILL_DIR / "scripts/pipeline.py").read_text(encoding="utf-8")

    assert "_check_tool_integrity" not in pipeline_text
    assert "tool integrity" not in pipeline_text
    assert "do not modify pipeline.py" not in pipeline_text
    assert "expected marker" not in pipeline_text


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


def test_skill_keeps_concise_operating_contract_sections() -> None:
    skill_text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

    required_sections = [
        "## Output Contract",
        "## Operating Modes",
        "## Preference Hierarchy",
        "## Helper Tools",
    ]
    for section in required_sections:
        assert section in skill_text

    assert "Use review points rather than silent forward motion." in skill_text
    assert "Use helpers after the owning LLM work product exists" in skill_text
    assert "Do not start a run by chasing helper output" in skill_text
    assert "Templates are style references by default" in skill_text
    assert "Do not create a review copy as the first stopping point" in skill_text
    assert "```bash" not in skill_text
    assert "scripts/pipeline.py" not in skill_text
    assert "pipeline.py start-brief" not in skill_text
    assert "evidence-build" not in skill_text
    assert "scripts/pipeline.py gate" not in skill_text
    assert "scripts/pipeline.py checkpoint" not in skill_text
    assert "or `checkpoint`" not in skill_text
    assert "deck_blueprint.json" not in skill_text
    assert "page_evidence_contract.json" not in skill_text
    assert "renderer_spec.json" not in skill_text
    assert "read/search/build only that" not in skill_text
    assert "Build the evidence database" not in skill_text
    assert "For each page, write the client-facing argument, headline" not in skill_text
    assert "client-facing page brief, not as a slot-filling file" in skill_text
    assert "visible title or title-ready argument" in skill_text
    assert "otherwise omit it so helpers do not repeat" in skill_text
    assert "working market, parent market, broader market" not in skill_text
    assert "the market lens for this pitch" in skill_text


def test_reference_guidance_keeps_qc_judgment_not_fixed_report_shape() -> None:
    anti_patterns = (SKILL_DIR / "references/critical-anti-patterns.md").read_text(encoding="utf-8")
    qc = (SKILL_DIR / "references/qc.md").read_text(encoding="utf-8")
    content_quality = (SKILL_DIR / "references/content-quality.md").read_text(encoding="utf-8")
    ppt_visual_qc = (SKILL_DIR / "references/ppt_visual_qc.md").read_text(encoding="utf-8")

    assert "Review pattern:" in anti_patterns
    assert "Symptom:" in anti_patterns
    assert "Risk:" in anti_patterns
    assert "Repair:" in anti_patterns
    assert "If the intended visual role is crowded" in anti_patterns
    assert "If a slot overflows" not in anti_patterns
    assert "## Review Judgment" in qc
    assert "without turning them into a scorecard" in qc
    assert "## Severity Language" in qc
    assert "They are not a required report template" in qc
    assert "**Critical:**" in qc
    assert "**Important:**" in qc
    assert "**Minor:**" in qc
    assert "## Review Report Shape" not in qc
    assert "For each finding" not in qc
    assert "Return accept, repair-needed, or escalate" not in qc
    assert "Close with a concise disposition only when it helps" in qc
    assert "Strong pages earn trust through a practical mix of" in content_quality
    assert "Do not force every page to contain every element" in content_quality
    assert "fewer than three meaningful cards" not in ppt_visual_qc
    assert "too little structured content to carry the page argument" in ppt_visual_qc
    assert "scripts/pipeline.py gate" not in qc


def test_evidence_limited_status_requires_bounded_research_or_source_limit() -> None:
    skill_text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    generation = (SKILL_DIR / "references/generation.md").read_text(encoding="utf-8")
    content_quality = (SKILL_DIR / "references/content-quality.md").read_text(encoding="utf-8")
    output = (SKILL_DIR / "references/output.md").read_text(encoding="utf-8")
    role_packets = (SKILL_DIR / "references/role_job_packets.md").read_text(encoding="utf-8")

    assert "Do not create a review copy as the first stopping point" in skill_text
    assert "leave an actionable handoff" in skill_text
    assert "Caps are ceilings, not quotas" in skill_text
    assert "not ready because evidence is missing" in output
    assert "Rely on the inherited caps because the policy budget applies by default" in generation
    assert "add cycle bookkeeping only after a cycle outcome" in generation
    assert "After each cycle, update the queue with what changed" not in skill_text
    assert "do not rerun the same active requests" not in skill_text
    assert "include `loop_control.current_cycle`" not in skill_text
    assert "deliverable_readiness.business_action" in generation
    assert "deliverable_readiness.next_step" not in generation
    assert "First decide the next action in business terms" in generation
    assert "not as the judgment itself" in generation
    assert "`client_ready`, `targeted_research`, `repair_page_pack`, and `qc_user_decision`" not in generation
    assert "write one bounded research brief with the exact gap" in generation
    assert "create a research-limited review copy while targeted research could still change the answer" in generation
    assert "Do not force a sparse client deck" in generation
    assert "the policy budget applies by default" in generation
    assert "give every active request a bounded search budget" not in generation
    assert "A negative readiness note should either point to a bounded targeted queue" not in generation
    assert "A negative readiness note must either" not in generation
    assert "must remain visible" not in generation
    assert "Create a research-limited review copy only after the targeted research loop cap" in content_quality
    assert "not ready because evidence is missing" in output
    assert "making the final delivery call before the parent loop has a concrete gap" in role_packets


def test_research_packets_inherit_bounded_loop_budget() -> None:
    role_packets = (SKILL_DIR / "references/role_job_packets.md").read_text(encoding="utf-8")

    assert "give the inherited policy cap or any narrower structured request budget" in role_packets
    assert "Include cycle number and max cycles when" in role_packets
    assert "3 actual searches, 4 opened/reviewed sources, and 2 promoted sources" in role_packets
    assert "return a cycle outcome when that budget is spent" in role_packets
    assert "should not recommend another broad pass" in role_packets
    assert "available boundary, evidence, or page context needed for that request" in role_packets
    assert "backfilling missing early workbenches for appearance" in role_packets
    assert "read the scope pack and research queue" not in role_packets


def test_skill_reference_map_keeps_optional_process_guides_out_of_default_load_path() -> None:
    skill_text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

    assert "Do not load a full role bundle" in skill_text
    assert "read `references/generation.md`" in skill_text
    assert "add `references/reasoning.md` only when deciding claim strength or targeted research" in skill_text
    assert "read `references/drilldown-roles.md` only when a structural drilldown page needs" in skill_text
    assert "read `references/role_job_packets.md` only when delegating one bounded task" in skill_text
    assert "read `references/operating_model.md` only when debugging or changing the workflow" in skill_text
    assert "- Page writing: `references/reasoning.md`, `references/generation.md`, `references/content-quality.md`, `references/drilldown-roles.md`." not in skill_text
    assert "- Review and escalation: `references/qc.md`, `references/critical-anti-patterns.md`, `references/role_job_packets.md`." not in skill_text


def test_client_visible_language_guidance_uses_positive_editorial_rewrite_instructions() -> None:
    generation = (SKILL_DIR / "references/generation.md").read_text(encoding="utf-8")
    content_quality = (SKILL_DIR / "references/content-quality.md").read_text(encoding="utf-8")
    scoping = (SKILL_DIR / "references/industry-scoping.md").read_text(encoding="utf-8")
    combined = generation + "\n" + content_quality

    assert "should not appear in headlines" in generation
    assert "Rewrite the point as a market conclusion" in generation
    assert "Internal market-definition slot labels" in generation
    assert "process-stage wording" in generation
    assert "internal workpaper language" in content_quality
    assert "Do not merely delete the sentence" in content_quality
    assert "面部底妆兼具肤质适配、复购和内容种草属性" in content_quality
    assert "面部彩妆视角更贴近品牌收入来源、渠道竞争和交易叙事" in generation
    assert "以面部彩妆视角更能解释品牌增长、渠道竞争和交易叙事" in content_quality
    assert "品类结构与渠道效率共同支撑控股权出售沟通的行业逻辑" in content_quality
    assert "market point, transaction relevance, source caveat" in combined
    assert "Treat the field names as internal artifact labels" in scoping
    assert "do not reuse scoping slot labels as slide wording" in scoping


def test_guidance_uses_workspace_not_skeleton_language_for_knowledge_authoring() -> None:
    checked_paths = [
        SKILL_DIR / "SKILL.md",
        SKILL_DIR / "references/research_policy.md",
        SKILL_DIR / "references/knowledge-repository.md",
        SKILL_DIR / "scripts/knowledge-repository/research_evidence_db.py",
        SKILL_DIR / "scripts/pipeline.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in checked_paths)

    assert "Knowledge candidate workspace" in combined
    assert "Candidate workspace contains extracted leads" in combined
    assert "Knowledge skeleton" not in combined
    assert "skeleton rows" not in combined
    assert "Skeleton contains" not in combined
    assert "skeleton helper" not in combined


def test_knowledge_db_uses_page_evidence_inventory_language() -> None:
    old_key = "issue" + "_fact_inventory"
    checked_paths = [
        SKILL_DIR / "scripts/knowledge-repository/research_evidence_db.py",
        SKILL_DIR / "references/knowledge-repository.md",
        Path(__file__).parent / "fixtures/minimal_research_db/research_evidence_db.json",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in checked_paths)

    assert old_key not in combined
    assert "page_evidence_inventory" in combined
    assert "page_evidence_inventory_row_count" in combined
    assert "Page Evidence Inventory" in checked_paths[0].read_text(encoding="utf-8")


def test_operating_model_keeps_llm_python_freedom_boundary() -> None:
    operating_model = (SKILL_DIR / "references/operating_model.md").read_text(encoding="utf-8")

    assert "## Freedom Model" in operating_model
    assert "Use high LLM freedom where multiple good answers can exist:" in operating_model
    assert "Use Python only where repeatability matters:" in operating_model
    assert "Structure/helper checks should not choose the story" in operating_model


def test_research_policy_does_not_present_script_checklist_as_research_flow() -> None:
    research_policy = (SKILL_DIR / "references/research_policy.md").read_text(encoding="utf-8")

    assert "## Helper Tools" in research_policy
    assert "Do not run a command list as proof that research is complete" in research_policy
    assert "The planning helper can create workbench files" in research_policy
    assert "research-prepare" not in research_policy
    assert "evidence-build" not in research_policy
    assert "research-prepare --run-dir" not in research_policy
    assert "validate --artifact formal_search_plan" not in research_policy
    assert "validate --artifact research_evidence_db" not in research_policy
    assert "```bash" not in research_policy


def test_knowledge_reference_describes_no_evidence_judgment_without_field_filling() -> None:
    knowledge = (SKILL_DIR / "references/knowledge-repository.md").read_text(encoding="utf-8")

    assert "If no EV row is source-supported enough for the page claim" in knowledge
    assert "Record the source limitation, the missing evidence, and the next honest action" in knowledge
    assert "While the bounded targeted research loop can still change deck inclusion" in knowledge
    assert "hand the limitation to Reasoning/QC instead of upgrading weak evidence" in knowledge
    assert "research_gap_audit.no_client_ready_evidence=true" not in knowledge
    assert "no_client_ready_evidence_rationale" not in knowledge
    assert "deliverable_constraint" not in knowledge


def test_content_quality_flags_internal_chinese_workpaper_language() -> None:
    content_quality = (SKILL_DIR / "references/content-quality.md").read_text(encoding="utf-8")

    assert "scope-card slot labels" in content_quality
    assert "review-task phrasing" in content_quality
    assert "evidence-use labels" in content_quality
    assert "process-status language" in content_quality
    assert "translate the intent into client-facing banker language" in content_quality


def test_content_quality_does_not_force_numbered_slide_roles() -> None:
    content_quality = (SKILL_DIR / "references/content-quality.md").read_text(encoding="utf-8")
    drilldown = (SKILL_DIR / "references/drilldown-roles.md").read_text(encoding="utf-8")

    assert "Each page should have a distinct job" in content_quality
    assert "Use only the jobs that the evidence and pitch need" in content_quality
    assert "not from a fixed industry template or a mandatory second-page role" in drilldown
    assert "Slide 3 is about" not in content_quality
    assert "Slide 7 is about" not in content_quality
    assert "Slide 2 should" not in content_quality
    assert "The best Slide 2" not in drilldown


def test_public_references_do_not_present_bash_runbooks() -> None:
    paths = [SKILL_DIR / "SKILL.md", *sorted((SKILL_DIR / "references").glob("*.md"))]
    offenders = [path.relative_to(SKILL_DIR).as_posix() for path in paths if "```bash" in path.read_text(encoding="utf-8")]

    assert offenders == []


def test_public_guidance_does_not_point_to_pipeline_commands_as_workflow() -> None:
    paths = [SKILL_DIR / "SKILL.md", *sorted((SKILL_DIR / "references").glob("*.md"))]
    offenders = [
        path.relative_to(SKILL_DIR).as_posix()
        for path in paths
        if re.search(r"(scripts/)?pipeline\.py\s+[A-Za-z-]+", path.read_text(encoding="utf-8"))
    ]

    assert offenders == []


def test_industry_scoping_reference_does_not_use_json_skeleton() -> None:
    scoping = (SKILL_DIR / "references/industry-scoping.md").read_text(encoding="utf-8")

    assert "```json" not in scoping
    assert "Boundary Card Contents" in scoping
    assert "brief shape reminder" in scoping
    assert "boundary check" in scoping
    assert "boundary validation" not in scoping
    assert "Do not copy empty template fields" in scoping


def test_public_references_do_not_present_json_skeletons() -> None:
    paths = [SKILL_DIR / "SKILL.md", *sorted((SKILL_DIR / "references").glob("*.md"))]
    offenders = [path.relative_to(SKILL_DIR).as_posix() for path in paths if "```json" in path.read_text(encoding="utf-8")]

    assert offenders == []


def test_no_blank_authoring_shape_hint_files_remain() -> None:
    assert not (SKILL_DIR / "configs" / "authoring_shape_hints").exists()
    assert list(SKILL_DIR.rglob("*.shape_hint.json")) == []


def test_generation_and_qc_do_not_present_validation_as_page_quality() -> None:
    generation = (SKILL_DIR / "references/generation.md").read_text(encoding="utf-8")
    qc = (SKILL_DIR / "references/qc.md").read_text(encoding="utf-8")

    assert "reads like a real client-facing section" in generation
    assert "client-facing page brief for judgment, exhibits, and source support" in generation
    assert "direct composition or the structured-render helper" in generation
    assert "LLM-authored writing surface" not in generation
    assert "## Structure Signals" in qc
    assert "cannot tell you that a page is persuasive" in qc
    assert "```bash" not in generation
    assert "```bash" not in qc
    assert "validate --artifact banker_page_pack" not in generation
    assert "validate --artifact banker_page_pack" not in qc


def test_generation_reference_is_composition_first_not_field_menu() -> None:
    generation = (SKILL_DIR / "references/generation.md").read_text(encoding="utf-8")

    assert "Own the page composition before choosing page-pack containers" in generation
    assert "First decide what the reader should see" in generation
    assert "These containers are carriers, not slots or a checklist" in generation
    assert "If the best exhibit does not fit a familiar container" in generation
    assert "Do not add prose blocks, summary metadata, or placeholder field maps merely to satisfy a template" in generation
    assert "Use `chart_data` for charts/cards/matrices" not in generation
    assert "Fill template alignment fields" not in generation


def test_research_queue_guidance_is_brief_not_field_checklist() -> None:
    reasoning = (SKILL_DIR / "references/reasoning.md").read_text(encoding="utf-8")
    policy = (SKILL_DIR / "configs/research_planning_policy.json").read_text(encoding="utf-8")
    combined = "\n".join([reasoning, policy])

    assert "A good request names the question" in reasoning
    assert "Without that decision anchor" in reasoning
    assert "do not rely on status wording to close a request" in reasoning
    assert "Close, exhaust, defer, or drop a request in plain language" in reasoning
    assert "Use `active=false` to close" not in reasoning
    assert "If a request cannot name that decision" not in reasoning
    assert "as a concise brief, not a form" in policy
    assert "Add loop_control or numeric sub-budgets only after a cycle outcome" in policy
    assert "Missing loop_control inherits the policy cap" in policy
    assert "For each active request, include" not in combined
    assert "For each active request, say" not in combined
    assert "include `loop_control.current_cycle`" not in combined


def test_template_reference_exposes_style_guidance_not_mechanical_files() -> None:
    template = (SKILL_DIR / "references/template.md").read_text(encoding="utf-8")
    output = (SKILL_DIR / "references/output.md").read_text(encoding="utf-8")

    assert "Pass on style guidance, not a slot map" in template
    assert "Template Files" not in template
    assert "template_fit_validation" not in template
    assert "template_registry.json" not in template
    assert "artifacts/template_profile.json" not in template
    assert "artifacts/template_selection.json" not in output
    assert "artifacts/runtime_dependencies.json" not in output
    assert "render_deck.py" not in output
    assert "template source selected during intake or template review" in output


def test_direct_ppt_composition_is_allowed_without_renderer_intermediate_lockin() -> None:
    skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    template = (SKILL_DIR / "references/template.md").read_text(encoding="utf-8")
    output = (SKILL_DIR / "references/output.md").read_text(encoding="utf-8")
    operating = (SKILL_DIR / "references/operating_model.md").read_text(encoding="utf-8")
    combined = "\n".join([skill, template, output, operating])

    assert "Direct PPT composition" in skill
    assert "Direct PPT composition" in template
    assert "Direct PPT composition is a valid output path" in output
    assert "direct editable PPT composition is better than structured rendering" in operating
    assert "Output Path Selection" in operating
    assert "Visual / Source QC" in operating
    assert "Compile / Template Fit" not in operating
    assert "Produce the PPT from the current upstream files" in output
    assert "copy the selected PPTX" in skill
    assert "duplicate a low-content or blank template page" in output
    assert "Do not create every structured-render intermediate merely because the helper exists" in output
    assert "Keep the evidence/page-pack judgment record" in skill
    assert "skip only the unnecessary derived render intermediates, not the thinking" in template
    assert "force every derived renderer artifact" in combined
    assert "must use renderer_spec" not in combined


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


def test_page_type_rules_have_been_folded_into_slide_registry() -> None:
    assert not (SKILL_DIR / "configs/page_type_rules.json").exists()
    assert not (SKILL_DIR / "configs/slide_layout_library.json").exists()
    assert not (SKILL_DIR / "configs/layout_config.json").exists()
    assert (SKILL_DIR / "configs/slide_registry.json").exists()
    assert (SKILL_DIR / "configs/render_layouts.json").exists()


def test_slide_registry_is_style_reference_not_standard_sequence() -> None:
    path = SKILL_DIR / "configs/slide_registry.json"
    text = path.read_text(encoding="utf-8")
    payload = json.loads(text)

    assert payload["workflow_scope"] == "style_reference"
    assert "rendering compatibility" in payload["description"]
    assert "Page sequence, page strategy, and LLM authoring decisions come from the banker page pack" in payload["description"]
    assert "slide_registry_defined_standard" not in text
    assert "standard page sequence" not in text


def test_style_guided_layout_rules_are_described_as_advisory() -> None:
    layout_budget = json.loads((SKILL_DIR / "configs/layout_budget.json").read_text(encoding="utf-8"))
    text_fit_rules = json.loads((SKILL_DIR / "configs/text_fit_rules.json").read_text(encoding="utf-8"))

    descriptions = [
        layout_budget.get("_description", ""),
        text_fit_rules.get("_description", ""),
    ]
    joined = "\n".join(str(item) for item in descriptions)

    assert "style-guided mode" in joined
    assert "advisory" in joined
    assert "hard-constrained" not in joined
    assert "hard constrained" not in joined


def test_text_fit_rules_use_strict_layout_pause_names() -> None:
    paths = [
        SKILL_DIR / "configs/text_fit_rules.json",
    ]
    hits: list[str] = []
    for path in paths:
        source = path.read_text(encoding="utf-8")
        if "block_if_exceeds_max_lines" in source.replace("strict_layout_pause_if_exceeds_max_lines", ""):
            hits.append(path.relative_to(SKILL_DIR).as_posix())
        assert "strict_layout_pause_if_exceeds_max_lines" in source

    assert hits == []


def test_layout_budget_uses_advisory_names_for_style_guided_visual_preferences() -> None:
    paths = [
        SKILL_DIR / "configs/layout_budget.json",
    ]
    forbidden_terms = [
        "must_be_investment_thesis",
        "required_visual",
        "required_numeric_xy",
        "forbid_terminal_punctuation",
        "forbid_paragraphs",
        "forbid_instructional_chart_titles",
        "forbid_none_unless_no_verified_metrics",
    ]

    hits: list[str] = []
    for path in paths:
        source = path.read_text(encoding="utf-8")
        for term in forbidden_terms:
            if term in source:
                hits.append(f"{path.relative_to(SKILL_DIR)}: {term}")

    assert hits == []

    layout_budget = json.loads((SKILL_DIR / "configs/layout_budget.json").read_text(encoding="utf-8"))
    layout_text = json.dumps(layout_budget, ensure_ascii=False)

    assert "preferred_investment_thesis_signal" in layout_text
    assert "preferred_visual_payload" in layout_text
    assert "preferred_numeric_xy_payload" in layout_text
    assert "avoid_terminal_punctuation" in layout_text
    assert "avoid_paragraphs" in layout_text
    assert "avoid_instructional_chart_titles" in layout_text
    assert "avoid_none_unless_no_verified_metrics" in layout_text


def test_python_does_not_default_evidence_limited_exhibit_language() -> None:
    paths = [
        SKILL_DIR / "scripts/_lib/deck_blueprint_utils.py",
        SKILL_DIR / "scripts/_lib/renderer_compile_utils.py",
    ]
    forbidden = [
        "default_evidence_limited_exhibit_plan",
        "evidence_limited_exhibit_plan",
        "Route back to banker_page_pack if evidence is insufficient",
    ]
    hits: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for term in forbidden:
            if term in text:
                hits.append(f"{path.relative_to(SKILL_DIR)}: {term}")
    assert hits == []


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
        "due diligence",
        "diligence",
        "diligence implication",
        "client_question",
        "client-question",
        "investor_question",
        "open_questions",
        "open_question",
        "fallback_if_data_limited",
        "fallback_if_data_insufficient",
        "default_visual_fallback",
        "后续验证点",
        "后续验证",
        "客户关注点",
        "客户关注",
        "task list",
        "future verification",
        "client concern",
        "follow-up",
        "diagnostic checklist",
        "evidence_gap_matrix",
        "evidence-gap matrix",
        "validation point",
        "project implication",
        "target implication",
        "pitch implication",
        "transaction implication",
        "implication",
        "implications",
        "to_test_in_project",
        "industry_changes_to_test_in_project",
        "your job is",
        "how to work",
        "core questions",
        "judgment boundary",
        "job packet use",
        "visual qc checklist",
        "recognition test",
        "correct approach",
        "why it is wrong",
        "what happens",
        "pairing constraints",
        "candidate roles",
        "selection logic",
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


def test_main_skill_tells_style_guided_render_to_start_from_selected_pptx() -> None:
    skill_text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    output_text = (SKILL_DIR / "references/output.md").read_text(encoding="utf-8")
    template_text = (SKILL_DIR / "references/template.md").read_text(encoding="utf-8")

    assert "start from the selected PPTX package" in skill_text
    assert "do not create an unrelated new presentation" in skill_text
    assert "start from the selected PPTX package" in output_text
    assert "It should not create an unrelated new PowerPoint document" in template_text


def test_llm_guidance_uses_page_use_not_permission_language() -> None:
    paths = [
        SKILL_DIR / "SKILL.md",
        SKILL_DIR / "references/generation.md",
        SKILL_DIR / "references/reasoning.md",
        SKILL_DIR / "references/research-external-evidence.md",
        SKILL_DIR / "configs/research_planning_policy.json",
    ]
    forbidden_terms = [
        "page permission",
        "permission decision",
        "page-permission",
        "deck permission",
        "claim permission",
    ]

    hits: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8").lower()
        for term in forbidden_terms:
            if term in text:
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
        SKILL_DIR / "references/generation.md",
        SKILL_DIR / "references/reasoning.md",
        SKILL_DIR / "scripts/_lib/deck_blueprint_utils.py",
    ]

    hits: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for term in forbidden_terms:
            if term in text:
                hits.append(f"{path.relative_to(SKILL_DIR)}: {term}")

    assert hits == []


def test_llm_expression_surface_stays_natural_not_schema_driven() -> None:
    generation = (SKILL_DIR / "references/generation.md").read_text(encoding="utf-8")
    validator = (SKILL_DIR / "scripts/qc/validate_artifact.py").read_text(encoding="utf-8")
    manifest = json.loads((SKILL_DIR / "configs/artifact_manifest.json").read_text(encoding="utf-8"))

    assert not (SKILL_DIR / "configs/mechanical_schemas").exists()
    assert "schema" not in manifest["artifacts"]["banker_page_pack"]
    assert "title-ready page argument" in generation
    assert "If the page argument itself is already suitable as the slide title" in generation
    assert "Inferred page type follows the authored content" in generation
    assert "will not turn internal EV IDs into client-facing source text" in generation
    assert "write a plain note in `deck_use`" in generation
    assert "page, metric, headline, key data, or exhibit decision" in generation
    assert "research_first_required" not in validator
    assert "evidence_limited_pitch_outline" not in validator
    assert "valid_claim_strengths" not in validator
    assert "allowed_deck_usage" not in generation
    assert "selected_page_type" not in generation
    assert not (SKILL_DIR / "configs/generation_policy.json").exists()


def test_deck_use_crosswalk_is_internal_not_llm_config() -> None:
    from deck_blueprint_utils import normalize_allowed_deck_usage

    generation = (SKILL_DIR / "references/generation.md").read_text(encoding="utf-8")
    utils_text = (SKILL_DIR / "scripts/_lib/deck_blueprint_utils.py").read_text(encoding="utf-8")

    assert not (SKILL_DIR / "configs/generation_policy.json").exists()
    assert normalize_allowed_deck_usage("可作标题") == "headline_allowed"
    assert normalize_allowed_deck_usage("只用于正文") == "body_only"
    assert normalize_allowed_deck_usage("仅作限定说明") == "caveat_only"
    assert "valid_allowed_deck_usages" not in utils_text
    assert "allowed_deck_usage_aliases" not in utils_text
    assert "deck_use_phrase_aliases" not in utils_text
    assert "`allowed_deck_usage`" not in generation
    assert "write a plain note in `deck_use`" in generation
    assert "never let that internal note appear as visible slide copy" in generation


def test_visual_capability_hints_are_internal_not_llm_config() -> None:
    utils_text = (SKILL_DIR / "scripts/_lib/deck_blueprint_utils.py").read_text(encoding="utf-8")

    assert not (SKILL_DIR / "configs/generation_policy.json").exists()
    assert "metric_visual_capabilities" not in utils_text
    assert "structured_exhibit_types" not in utils_text
    assert "page_type_default_capabilities" not in utils_text


def test_renderer_contract_is_internal_not_llm_schema_surface() -> None:
    check_slide_registry = (SKILL_DIR.parents[1] / "devtools/checks/check_slide_registry.py").read_text(encoding="utf-8")
    renderer_utils = (SKILL_DIR / "scripts/_lib/renderer_compile_utils.py").read_text(encoding="utf-8")

    assert not (SKILL_DIR / "configs/mechanical_schemas").exists()
    assert "RENDERER_SPEC_REQUIRED_SLIDE_FIELDS" in check_slide_registry
    assert "mechanical_schemas" not in check_slide_registry
    assert "claim_strength" not in check_slide_registry
    assert "drilldown_role" not in renderer_utils
    assert "drill_down_from_slide" not in renderer_utils
    assert "new_information_added" not in renderer_utils


def test_template_diagnostics_do_not_publish_slot_filling_terms() -> None:
    runtime_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in [
            SKILL_DIR / "scripts/qc/validate_artifact.py",
            SKILL_DIR / "scripts/_lib/renderer_compile_utils.py",
            SKILL_DIR / "scripts/template/template_analyzer.py",
        ]
    )

    forbidden_terms = [
        "active body fields",
        "active template fields",
        "template_field_contract_mode",
        "active_template_body_fields",
        "template_body_field_hints",
        "body_field_unit_limits",
        "unit budgets are style cues",
        "content-field contract",
    ]

    assert all(term not in runtime_text for term in forbidden_terms)


def test_renderer_rules_do_not_require_source_footer_in_style_guided_mode() -> None:
    from renderer_compile_utils import build_token_source

    renderer_spec = {
        "schema_version": "renderer_spec_v1",
        "rendering_policy": {"template_contract_mode": "style_guided"},
        "slides": [
            {
                "slide_no": 1,
                "selected_page_type": "overview",
                "headline": "Market framing",
                "main_message": "The page can be visually styled without a global footer mandate.",
                "body_copy": {"main_body": "Concise market point."},
            }
        ],
    }

    rules = build_token_source(renderer_spec)["token_source"]["rules"]

    assert rules["source_footer_available"] is True
    assert "source_footer_required" not in rules
    assert rules["source_footer_required_in_strict_layout"] is False
    assert "title_should_be_conclusion_led" not in rules
    assert "takeaway_one_sentence_only" not in rules
    assert "style_hint" in " ".join(rules)


def test_template_metadata_uses_strict_layout_body_field_language() -> None:
    slide_registry_text = (SKILL_DIR / "configs/slide_registry.json").read_text(encoding="utf-8")

    assert "required_fields" not in slide_registry_text
    assert "required_objects" not in slide_registry_text
    assert "conditional_required_objects" not in slide_registry_text
    assert "required_body_fields" not in slide_registry_text
    assert "strict_layout_fields" in slide_registry_text
    assert "strict_layout_objects" in slide_registry_text
    assert "conditional_strict_layout_objects" in slide_registry_text
    assert "strict_layout_body_fields" in slide_registry_text


def test_template_metadata_does_not_keep_required_body_field_compatibility() -> None:
    runtime_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            SKILL_DIR / "scripts/_lib/deck_blueprint_utils.py",
            SKILL_DIR / "scripts/template/template_analyzer.py",
        ]
    )

    assert "required_body_fields" not in runtime_text


def test_visual_plan_surface_uses_visual_type_not_required_capability() -> None:
    runtime_paths = [
        SKILL_DIR / "scripts/_lib/deck_blueprint_utils.py",
        SKILL_DIR / "scripts/_lib/renderer_compile_utils.py",
        SKILL_DIR / "references/generation.md",
    ]
    runtime_text = "\n".join(path.read_text(encoding="utf-8") for path in runtime_paths)

    assert "required_capability" not in runtime_text
    assert "visual_type" in runtime_text


def test_banker_page_pack_client_ready_warns_without_blocking_missing_visible_headline(
    tmp_path: Path,
) -> None:
    from validate_artifact import validate_artifact, validate_client_ready_page_pack

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {"business_action": "client_ready"},
            "slides": [
                {
                    "body_blocks": [
                        {
                            "copy": "This page has draft substance, but the LLM has not yet converted it into a client-facing page argument and headline."
                        }
                    ],
                    "deck_use": "只用于正文",
                }
            ],
        },
    )

    draft_errors, draft_warnings = validate_artifact("banker_page_pack", run_dir)

    assert draft_errors == []
    assert any("no page argument/thesis was found" in warning for warning in draft_warnings)
    assert any("no headline/title was found" in warning for warning in draft_warnings)
    assert any("LLM editorial prompt" in warning for warning in draft_warnings)

    client_ready_errors: list[str] = []
    client_ready_warnings: list[str] = []
    validate_client_ready_page_pack(run_dir, client_ready_errors, client_ready_warnings)

    assert not any("lack a page argument/thesis" in error for error in client_ready_errors)
    assert any("lack a page argument/thesis" in warning for warning in client_ready_warnings)
    assert any("LLM editorial prompt" in warning for warning in client_ready_warnings)
    assert not any("lack both headline/title and page argument" in error for error in client_ready_errors)
    assert any("lack both headline/title and page argument" in warning for warning in client_ready_warnings)


def test_client_ready_page_pack_allows_title_derivation_from_page_argument(
    tmp_path: Path,
) -> None:
    from validate_artifact import validate_client_ready_page_pack

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {"business_action": "client_ready"},
            "slides": [
                {
                    "page_argument": "底妆品类的增长逻辑正在从泛流量转向肤质适配、复购和内容转化的组合能力。",
                    "deck_use": "只用于正文",
                    "body_blocks": [
                        {"copy": "页面已经有可见正文和清晰论点，标题可由页面论点派生后再由 LLM/QC 审阅。"}
                    ],
                    "source_note": "Source: fixture evidence",
                }
            ],
        },
    )

    errors: list[str] = []
    warnings: list[str] = []
    validate_client_ready_page_pack(run_dir, errors, warnings)

    assert errors == []
    assert any("structured-render helper can derive a title from the page argument" in warning for warning in warnings)


def test_client_ready_page_pack_allows_visual_led_page_without_internal_page_argument(
    tmp_path: Path,
) -> None:
    from validate_artifact import validate_client_ready_page_pack

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {"business_action": "client_ready"},
            "slides": [
                {
                    "headline": "渠道结构变化正在重塑底妆品牌的增长质量",
                    "deck_use": "可作标题",
                    "chart_data": {
                        "chart_type": "bar",
                        "categories": ["内容种草", "直播转化", "复购沉淀"],
                        "series": [{"name": "证据强度", "values": [3, 4, 3]}],
                    },
                    "body_blocks": [
                        {"copy": "页面由可见标题、图表和正文共同承载判断，内部 page_argument 可由 LLM 后续补充。"}
                    ],
                    "source_note": "Source: fixture evidence",
                }
            ],
        },
    )

    errors: list[str] = []
    warnings: list[str] = []
    validate_client_ready_page_pack(run_dir, errors, warnings)

    assert errors == []
    assert not any("lack a page argument/thesis" in warning for warning in warnings)


def test_client_ready_page_pack_warns_when_headline_only_has_no_page_argument(
    tmp_path: Path,
) -> None:
    from validate_artifact import validate_client_ready_page_pack

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {"business_action": "client_ready"},
            "slides": [
                {
                    "headline": "底妆市场渠道结构正在变化",
                    "deck_use": "可作标题",
                    "source_note": "Source: fixture evidence",
                }
            ],
        },
    )

    errors: list[str] = []
    warnings: list[str] = []
    validate_client_ready_page_pack(run_dir, errors, warnings)

    assert errors == []
    assert any("lack a page argument/thesis" in warning for warning in warnings)
    assert any("LLM editorial prompt" in warning for warning in warnings)


def test_client_ready_page_pack_allows_not_for_deck_editing_decision_in_style_guided_mode(
    tmp_path: Path,
) -> None:
    from validate_artifact import validate_client_ready_page_pack

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {"business_action": "client_ready"},
            "slides": [
                {
                    "headline": "This candidate page should be skipped",
                    "page_argument": "The LLM decided this page duplicates the next page.",
                    "deck_use": "不可用于页面",
                    "body_blocks": [{"copy": "Candidate content retained for reviewer context only."}],
                    "source_note": "Source: fixture evidence",
                },
                {
                    "headline": "Category economics support a focused market discussion",
                    "page_argument": "The retained page carries the client-facing market point.",
                    "deck_use": "可作标题",
                    "body_blocks": [{"copy": "Visible retained page content is ready for style-guided rendering."}],
                    "source_note": "Source: fixture evidence",
                },
            ],
        },
    )

    errors: list[str] = []
    warnings: list[str] = []
    validate_client_ready_page_pack(run_dir, errors, warnings)

    assert errors == []
    assert any("style-guided structured render will skip these pages" in warning for warning in warnings)


def test_client_ready_page_pack_requires_explicit_business_action_with_chinese_ready_note(
    tmp_path: Path,
) -> None:
    from validate_artifact import validate_client_ready_page_pack

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": "证据足够，当前范围可正式交付并支持正式渲染。",
            "slides": [
                {
                    "headline": "底妆品牌增长正在从流量红利转向产品复购与内容转化",
                    "page_argument": "公开证据和用户材料已足够支持当前范围的客户版行业判断。",
                    "deck_use": "可作标题",
                    "body_blocks": [{"copy": "页面有清晰客户化表达、来源备注和可审阅的论点。"}],
                    "source_note": "Source: fixture evidence",
                }
            ],
        },
    )

    errors: list[str] = []
    warnings: list[str] = []
    validate_client_ready_page_pack(run_dir, errors, warnings)

    assert errors == []
    assert any("does not give automation a clear final-output next action" in warning for warning in warnings)
    assert any("do not infer final delivery readiness from prose" in warning for warning in warnings)


def test_client_ready_page_pack_accepts_business_action_as_readiness_decision(
    tmp_path: Path,
) -> None:
    from validate_artifact import validate_client_ready_page_pack

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {
                "business_action": "client_ready",
                "readiness_note": "证据、页面密度和来源说明足够支持当前范围的正式渲染。",
            },
            "slides": [
                {
                    "headline": "底妆品牌增长正在从流量红利转向产品复购与内容转化",
                    "page_argument": "公开证据和用户材料已足够支持当前范围的客户版行业判断。",
                    "deck_use": "可作标题",
                    "body_blocks": [{"copy": "页面有清晰客户化表达、来源备注和可审阅的论点。"}],
                    "source_note": "Source: fixture evidence",
                }
            ],
        },
    )

    errors: list[str] = []
    warnings: list[str] = []
    validate_client_ready_page_pack(run_dir, errors, warnings)

    assert errors == []
    assert not any("does not give automation a clear final-output next action" in warning for warning in warnings)


def test_client_ready_page_pack_does_not_infer_research_route_from_chinese_evidence_gap_note(
    tmp_path: Path,
) -> None:
    from validate_artifact import validate_client_ready_page_pack

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {
                "readiness_note": "需要补充公开来源：底妆市场规模来源会改变第2页图表能否使用。"
            },
            "slides": [
                {
                    "headline": "底妆品牌增长正在从流量红利转向产品复购与内容转化",
                    "page_argument": "当前页面判断仍缺少一个会影响图表使用的公开来源。",
                    "deck_use": "只用于正文",
                    "body_blocks": [{"copy": "该页面应先回到有上限的定向研究，再决定是否正式渲染。"}],
                    "source_note": "Source: fixture evidence",
                }
            ],
        },
    )

    errors: list[str] = []
    warnings: list[str] = []
    validate_client_ready_page_pack(run_dir, errors, warnings)

    assert errors == []
    assert not any("explicitly routes to targeted research" in warning for warning in warnings)
    assert any("does not give automation a clear final-output next action" in warning for warning in warnings)


def test_client_ready_page_pack_does_not_infer_source_limit_route_from_note(
    tmp_path: Path,
) -> None:
    from validate_artifact import validate_client_ready_page_pack

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {
                "readiness_note": "证据不足，但定向研究已达上限；公开来源不可得，需要QC/user决定是否接受证据受限版本。"
            },
            "slides": [
                {
                    "headline": "底妆品牌增长正在从流量红利转向产品复购与内容转化",
                    "page_argument": "剩余缺口已经不能通过默认循环继续推进。",
                    "deck_use": "只用于正文",
                    "body_blocks": [{"copy": "应由QC/user选择补材料、缩范围或接受证据受限审阅稿。"}],
                    "source_note": "Source: fixture evidence",
                }
            ],
        },
    )

    errors: list[str] = []
    warnings: list[str] = []
    validate_client_ready_page_pack(run_dir, errors, warnings)

    assert errors == []
    assert any("does not give automation a clear final-output next action" in warning for warning in warnings)
    assert not any("explicitly routes to targeted research" in warning for warning in warnings)


def test_client_ready_page_pack_does_not_route_copy_gap_to_targeted_research(
    tmp_path: Path,
) -> None:
    from validate_artifact import validate_client_ready_page_pack

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {
                "readiness_note": "不可正式交付：页面文案仍像内部工作纸，需要改成客户版 pitchbook 表达。"
            },
            "slides": [
                {
                    "headline": "底妆品牌增长正在从流量红利转向产品复购与内容转化",
                    "page_argument": "证据不是当前阻塞点；阻塞点是客户化表达和页面密度。",
                    "deck_use": "只用于正文",
                    "body_blocks": [{"copy": "应修 banker_page_pack，而不是启动 research loop。"}],
                    "source_note": "Source: fixture evidence",
                }
            ],
        },
    )

    errors: list[str] = []
    warnings: list[str] = []
    validate_client_ready_page_pack(run_dir, errors, warnings)

    assert errors == []
    assert any("does not give automation a clear final-output next action" in warning for warning in warnings)
    assert not any("explicitly routes to targeted research" in warning for warning in warnings)


def test_client_ready_page_pack_does_not_route_wording_pass_to_targeted_research(
    tmp_path: Path,
) -> None:
    from validate_artifact import validate_client_ready_page_pack

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {
                "readiness_note": (
                    "Not client-ready: the page needs one more wording pass and stronger visual density; "
                    "no additional source would change the page decision."
                )
            },
            "slides": [
                {
                    "headline": "底妆品牌增长正在从流量红利转向产品复购与内容转化",
                    "page_argument": "证据不是当前阻塞点；阻塞点是客户化表达和页面密度。",
                    "deck_use": "只用于正文",
                    "body_blocks": [{"copy": "应修 banker_page_pack，而不是启动 research loop。"}],
                    "source_note": "Source: fixture evidence",
                }
            ],
        },
    )

    errors: list[str] = []
    warnings: list[str] = []
    validate_client_ready_page_pack(run_dir, errors, warnings)

    assert errors == []
    assert any("does not give automation a clear final-output next action" in warning for warning in warnings)
    assert not any("explicitly routes to targeted research" in warning for warning in warnings)


def test_llm_facing_guidance_hides_internal_deck_use_tokens() -> None:
    paths = [
        SKILL_DIR / "SKILL.md",
        *sorted((SKILL_DIR / "references").glob("*.md")),
    ]
    internal_tokens = [
        "headline_allowed",
        "body_only",
        "supporting_context",
        "caveat_only",
        "not_allowed",
    ]

    hits: list[str] = []
    for path in paths:
        body = path.read_text(encoding="utf-8")
        for token in internal_tokens:
            if token in body:
                hits.append(f"{path.relative_to(SKILL_DIR)}: {token}")

    assert hits == []


def test_llm_facing_research_guidance_hides_internal_execution_status_tokens() -> None:
    paths = [
        SKILL_DIR / "references/research_policy.md",
        SKILL_DIR / "references/research-external-evidence.md",
        SKILL_DIR / "references/role_job_packets.md",
    ]
    forbidden_terms = [
        "status=supported",
        "terminal_status=executed_with_evidence",
        "`research_context_only`",
        "`needs_research_authorization`",
        "`research_gap`",
        "`not_executed`",
        "`unavailable_after_research`",
        "Allowed status values",
        "`completed_with_limits`",
        "`needs_parent_decision`",
        "query_status=",
        "`query_status`",
        "backlog_not_executed",
        "`not_selected`",
    ]

    hits: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for term in forbidden_terms:
            if term in text:
                hits.append(f"{path.relative_to(SKILL_DIR)}: {term}")

    assert hits == []


def test_llm_facing_knowledge_guidance_hides_evidence_status_label_prompts() -> None:
    paths = [
        SKILL_DIR / "references/knowledge-repository.md",
        SKILL_DIR / "references/reasoning.md",
    ]
    forbidden_terms = [
        "evidence_status",
        "fact_status",
        "primary-reviewed",
        "secondary-reviewed",
        "Recommended labels",
        "recommended labels",
        "needs_knowledge_llm",
        "unavailable_after_research",
        "not_applicable",
    ]

    hits: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for term in forbidden_terms:
            if term in text:
                hits.append(f"{path.relative_to(SKILL_DIR)}: {term}")

    assert hits == []


def test_research_request_policy_does_not_alias_private_terms_to_public_search() -> None:
    policy = json.loads((SKILL_DIR / "configs/research_planning_policy.json").read_text(encoding="utf-8"))
    queue_policy = policy.get("research_request_queue", {})
    aliases = queue_policy.get("source_type_alias_terms", {})
    public_aliases = {str(item).lower() for item in aliases.get("public_search", [])}
    private_terms = {"client", "confidential", "internal", "sensitive", "private"}

    assert public_aliases.isdisjoint(private_terms)


def test_industry_boundary_qc_has_no_copyable_blank_shape_file() -> None:
    assert not (SKILL_DIR / "configs/authoring_shape_hints/industry_boundary_qc.shape_hint.json").exists()


def test_industry_boundary_qc_requires_explicit_llm_decision(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    _write_json(
        artifacts / "industry_boundary_qc.json",
        {
            "schema_version": "industry_boundary_qc",
            "_shape_hint_only": True,
            "decision": "",
            "business_action": "",
        },
    )

    result = _run([
        sys.executable,
        "scripts/pipeline.py",
        "review",
        "--artifact",
        "industry_boundary_qc",
        "--run-dir",
        str(run_dir),
    ])

    assert result.returncode != 0
    assert "decision is missing" in result.stdout
    assert "industry_boundary_qc.next_step must be one of" not in result.stdout
    assert "industry_boundary_qc.business_action must be one of" not in result.stdout
    assert "_shape_hint_only=true" in result.stdout


def test_industry_boundary_qc_missing_decision_warns_without_blocking(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    _write_json(
        artifacts / "industry_boundary_qc.json",
        {
            "schema_version": "industry_boundary_qc",
            "decision": "",
            "rationale": "Optional boundary review was started but not finalized.",
        },
    )

    result = _run([
        sys.executable,
        "scripts/pipeline.py",
        "review",
        "--artifact",
        "industry_boundary_qc",
        "--run-dir",
        str(run_dir),
    ])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "decision is missing" in result.stdout


def test_industry_boundary_qc_passes_with_authored_decision(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    _write_json(
        artifacts / "industry_boundary_qc.json",
        {
            "schema_version": "industry_boundary_qc",
            "decision": "Boundary is clear for formal research.",
            "business_action": "research_ready",
            "rationale": "The working market, parent market, and exclusions are clear enough for research.",
            "reviewed_scope": {"working_market": "Sample market"},
        },
    )

    result = _run([
        sys.executable,
        "scripts/pipeline.py",
        "review",
        "--artifact",
        "industry_boundary_qc",
        "--run-dir",
        str(run_dir),
    ])

    assert result.returncode == 0, result.stdout + result.stderr


def test_industry_boundary_qc_accepts_natural_language_decision(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    _write_json(
        artifacts / "industry_boundary_qc.json",
        {
            "schema_version": "industry_boundary_qc",
            "decision": "Boundary is clear enough for formal research; no separate boundary check is needed.",
            "business_action": "research_ready",
            "rationale": "The working market and exclusions are clear enough to guide evidence collection.",
            "reviewed_scope": {"working_market": "Sample market"},
        },
    )

    result = _run([
        sys.executable,
        "scripts/pipeline.py",
        "review",
        "--artifact",
        "industry_boundary_qc",
        "--run-dir",
        str(run_dir),
    ])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "industry_boundary_qc.next_step must be one of" not in result.stdout
    assert "industry_boundary_qc.business_action must be one of" not in result.stdout


def test_industry_boundary_qc_allows_missing_business_action_as_advisory_review(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    _write_json(
        artifacts / "industry_boundary_qc.json",
        {
            "schema_version": "industry_boundary_qc",
            "decision": "Boundary is clear enough for formal research; no separate boundary check is needed.",
            "rationale": "The working market and exclusions are clear enough to guide evidence collection.",
            "reviewed_scope": {"working_market": "Sample market"},
        },
    )

    result = _run([
        sys.executable,
        "scripts/pipeline.py",
        "review",
        "--artifact",
        "industry_boundary_qc",
        "--run-dir",
        str(run_dir),
    ])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "industry_boundary_qc.next_step must be one of" not in result.stdout
    assert "industry_boundary_qc.business_action must be one of" not in result.stdout


def test_industry_boundary_qc_warns_on_nonstandard_business_action_without_blocking(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    _write_json(
        artifacts / "industry_boundary_qc.json",
        {
            "schema_version": "industry_boundary_qc",
            "decision": "Boundary looks usable, but the reviewer phrases routing naturally.",
            "business_action": "continue with the current market lens",
            "rationale": "The working market and exclusions are clear enough to guide evidence collection.",
            "reviewed_scope": {"working_market": "Sample market"},
        },
    )

    result = _run([
        sys.executable,
        "scripts/pipeline.py",
        "review",
        "--artifact",
        "industry_boundary_qc",
        "--run-dir",
        str(run_dir),
    ])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "industry_boundary_qc.business_action is nonstandard" in result.stdout


def test_input_card_has_no_copyable_blank_shape_file() -> None:
    assert not (SKILL_DIR / "configs/authoring_shape_hints/input_card.shape_hint.json").exists()


def test_input_card_template_copy_fails_validation(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_json(
        run_dir / "input_card.json",
        {
            "_shape_hint_only": True,
            "raw_brief": "",
            "explicit_user_facts": [],
            "candidate_normalizations": {},
            "source_materials": [],
            "research_direction": {},
        },
    )

    result = _run([
        sys.executable,
        "scripts/pipeline.py",
        "review",
        "--artifact",
        "input_card",
        "--run-dir",
        str(run_dir),
    ])

    assert result.returncode != 0
    assert "_shape_hint_only=true" in result.stdout
    assert "owner_repair_guidance" in result.stdout
    assert "do not invent evidence" in result.stdout
    assert "filler fields" in result.stdout
    payload = json.loads(result.stdout)
    assert payload["review_outcome"] == "needs_owner_repair"
    keys = list(payload)
    assert keys.index("review_outcome") < keys.index("is_valid")


def test_old_template_only_copy_still_fails_validation(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_json(
        run_dir / "input_card.json",
        {
            "_template_only": True,
            "raw_brief": "Copied old template marker should not pass.",
            "explicit_user_facts": ["placeholder"],
        },
    )

    result = _run([
        sys.executable,
        "scripts/pipeline.py",
        "review",
        "--artifact",
        "input_card",
        "--run-dir",
        str(run_dir),
    ])

    assert result.returncode != 0
    assert "_template_only=true" in result.stdout
    assert "replace the old copied template" in result.stdout


def test_formal_search_plan_has_no_copyable_blank_shape_file() -> None:
    assert not (SKILL_DIR / "configs/authoring_shape_hints/formal_search_plan.shape_hint.json").exists()


def test_research_policy_uses_threads_not_configured_taxonomy() -> None:
    text = (SKILL_DIR / "references/research_policy.md").read_text(encoding="utf-8")
    lowered = text.lower()

    assert "configured taxonomy" not in lowered
    assert "starter threads and optional coverage prompts" in lowered
    assert "forcing equal-depth searches" in lowered


def test_formal_search_plan_template_copy_fails_validation(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    _write_json(
        artifacts / "formal_search_plan.json",
        {
            "schema_version": "formal_search_plan",
            "_shape_hint_only": True,
            "plan_mode": "",
            "planning_instruction": "",
            "core_research_threads": [],
            "industry_specific_research_threads": [],
            "research_discipline": {"query_authoring_artifact": "artifacts/executable_search_batch.json"},
        },
    )

    result = _run([
        sys.executable,
        "scripts/pipeline.py",
        "review",
        "--artifact",
        "formal_search_plan",
        "--run-dir",
        str(run_dir),
    ])

    assert result.returncode != 0
    assert "_shape_hint_only=true" in result.stdout


def test_formal_search_plan_accepts_industry_specific_threads_without_issue_rows(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    _write_json(
        artifacts / "formal_search_plan.json",
        {
            "schema_version": "formal_search_plan",
            "industry_specific_research_threads": [
                {
                    "thread": "platform category taxonomy",
                    "evidence_need": "Confirm how major platforms classify the category before sizing the market.",
                    "source_direction": "platform taxonomy, industry report, or official category definition",
                }
            ],
        },
    )

    result = _run([
        sys.executable,
        "scripts/pipeline.py",
        "review",
        "--artifact",
        "formal_search_plan",
        "--run-dir",
        str(run_dir),
    ])

    assert result.returncode == 0, result.stdout + result.stderr


def test_formal_search_plan_rejects_authored_empty_evidence_need_map(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    _write_json(
        artifacts / "formal_search_plan.json",
        {
            "schema_version": "formal_search_plan",
            "issue_search_plan": [],
            "industry_specific_research_threads": [],
        },
    )

    result = _run([
        sys.executable,
        "scripts/pipeline.py",
        "review",
        "--artifact",
        "formal_search_plan",
        "--run-dir",
        str(run_dir),
    ])

    assert result.returncode != 0
    assert "at least one evidence-need thread" in result.stdout


def test_research_graph_state_validation_is_lightweight_workbench_check(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    _write_json(
        artifacts / "research_graph_state.json",
        {
            "schema_version": "research_graph_state_v1",
            "research_units": [
                {
                    "unit_id": "RU-001",
                    "notes": "Research records selected searches, opened-source work, and remaining gaps here.",
                }
            ],
        },
    )

    result = _run([
        sys.executable,
        "scripts/pipeline.py",
        "review",
        "--artifact",
        "research_graph_state",
        "--run-dir",
        str(run_dir),
    ])

    assert result.returncode == 0, result.stdout + result.stderr


def test_status_next_reports_missing_first_artifact(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    result = _run([sys.executable, "scripts/pipeline.py", "next", "--run-dir", str(run_dir)])

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "status_report_v1"
    assert payload["current_stage"] == "material_intake"
    assert "current_artifact" not in payload
    assert payload["current_state"] == "needs_owner_authoring"
    assert "recommended_next_commands" not in payload
    assert "recommended_check_commands" not in payload
    assert payload["recommended_next_actions"][0].startswith("Owner action: Material Intake")
    assert payload["recommended_next_actions"][0].startswith("Owner action: Material Intake")
    assert all("scripts/pipeline.py" not in item for item in payload["recommended_next_actions"])
    assert "optional_helper_checks" not in payload
    assert "debug_helper_check_commands" not in payload
    assert "policy" not in payload
    assert "status_scope" in payload
    assert "mechanical_status_only" not in json.dumps(payload)
    assert "Guides the next owner action" in payload["status_scope"]
    assert "artifacts" not in payload
    assert payload["milestones"]
    assert all("artifact" not in row for row in payload["milestones"])
    assert all("path" not in row for row in payload["milestones"])
    assert all("exists" not in row for row in payload["milestones"])
    assert all("error_count" not in row for row in payload["milestones"])
    assert all("errors" not in row for row in payload["milestones"])
    assert all("_validation.json" not in json.dumps(row) for row in payload["milestones"])
    assert all(set(row) == {"stage", "state"} for row in payload["milestones"])
    public_stages = {row["stage"] for row in payload["milestones"]}
    public_states = {row["state"] for row in payload["milestones"]}
    assert len(public_stages) == len(payload["milestones"])
    assert [row["stage"] for row in payload["milestones"]].count("material_intake") == 1
    assert not {"valid", "invalid", "unvalidated", "missing"} & public_states
    assert "research_execution" in public_stages
    assert not {
        "deck_blueprint",
        "page_evidence_contract",
        "renderer_spec",
        "replacement_dict",
        "formal_research_execution",
        "source_archive",
    } & public_stages


def test_start_brief_stdout_is_owner_facing_not_helper_log(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"

    result = _run([
        sys.executable,
        "scripts/pipeline.py",
        "start-brief",
        "--run-dir",
        str(run_dir),
        "--case-name",
        "base_makeup_check",
        "--brief-text",
        "一个底妆品牌控股权出售预沟通，需要展示行业理解、交易理解和专业判断。",
    ])

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "case_start_result_v1"
    assert payload["primary_record"] == "input_card"
    assert "input_card" in payload
    assert payload["owner_action"].startswith("Material role reviews input_card")
    assert "optional_trace_records" in payload
    assert "material_extracts" not in payload
    assert "source_classification" not in payload
    assert "material_extracts" in payload["optional_trace_records"]
    assert "source_classification" in payload["optional_trace_records"]
    assert "[pipeline]" not in result.stdout
    assert "review_outcome" not in result.stdout
    assert "helper_check_policy" not in result.stdout
    assert "input_card_validation" not in result.stdout
    assert "material_extracts_validation" not in result.stdout
    assert (run_dir / "artifacts/input_card_validation.json").exists()
    assert (run_dir / "artifacts/material_extracts_validation.json").exists()


def test_status_next_prioritizes_owner_action_over_pipeline_command(tmp_path: Path, monkeypatch) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()

    monkeypatch.setattr(pipeline, "MAIN_STATUS_PATH", ["formal_search_plan"])

    payload = pipeline.build_run_status(run_dir)

    assert payload["current_stage"] == "research_planning"
    assert payload["recommended_next_actions"][0].startswith("Owner action: Research Planning LLM")
    assert payload["recommended_next_actions"][0].startswith("Owner action: Research Planning LLM")
    assert "research-prepare" not in payload["recommended_next_actions"][0]
    assert "scripts/pipeline.py" not in payload["recommended_next_actions"][0]
    assert all("scripts/pipeline.py" not in item for item in payload["recommended_next_actions"])
    assert "recommended_check_commands" not in payload
    assert "optional_helper_checks" not in payload
    assert "debug_helper_check_commands" not in payload


def test_status_recommends_helper_check_only_after_artifact_exists(tmp_path: Path, monkeypatch) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(run_dir / "artifacts/formal_search_plan.json", {"schema_version": "formal_search_plan"})

    monkeypatch.setattr(pipeline, "MAIN_STATUS_PATH", ["formal_search_plan"])

    payload = pipeline.build_run_status(run_dir)

    assert payload["current_stage"] == "research_planning"
    assert payload["current_state"] == "ready_for_optional_check"
    assert "optional_helper_checks" not in payload
    assert "debug_helper_check_commands" not in payload

    debug_payload = pipeline.build_run_status(run_dir, include_debug_commands=True)
    assert debug_payload["optional_helper_checks"] == [
        "Optional helper check for `formal_search_plan` after the owner action; "
        "rerun status/next with --include-debug-commands only when the exact command is needed."
    ]
    assert all("scripts/pipeline.py" not in item for item in debug_payload["optional_helper_checks"])
    assert debug_payload["current_artifact"] == "formal_search_plan"
    assert any("scripts/pipeline.py review" in item for item in debug_payload["debug_helper_check_commands"])
    assert debug_payload["milestones"][0]["stage"] == "research_planning"
    assert debug_payload["artifacts"][0]["path"]
    assert "exists" in debug_payload["artifacts"][0]
    assert "error_count" in debug_payload["artifacts"][0]


def test_status_cli_hides_debug_helper_check_commands_unless_requested(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(run_dir / "input_card.json", {"schema_version": "input_card", "raw_user_brief": "brief"})

    default_result = _run([sys.executable, "scripts/pipeline.py", "next", "--run-dir", str(run_dir)])
    debug_result = _run([
        sys.executable,
        "scripts/pipeline.py",
        "next",
        "--run-dir",
        str(run_dir),
        "--include-debug-commands",
    ])

    assert default_result.returncode == 0, default_result.stdout + default_result.stderr
    assert debug_result.returncode == 0, debug_result.stdout + debug_result.stderr
    default_payload = json.loads(default_result.stdout)
    debug_payload = json.loads(debug_result.stdout)

    assert "debug_helper_check_commands" not in default_payload
    assert "artifacts" not in default_payload
    assert "milestones" in default_payload
    assert "debug_helper_check_commands" in debug_payload
    assert "artifacts" in debug_payload
    assert any("scripts/pipeline.py review" in item for item in debug_payload["debug_helper_check_commands"])


def test_status_build_hints_are_owner_actions_not_script_checklist() -> None:
    import pipeline

    script_first = [
        f"{artifact}: {hint}"
        for artifact, hint in pipeline.BUILD_HINTS.items()
        if hint.strip().startswith("scripts/pipeline.py ")
    ]

    assert script_first == []
    joined = "\n".join(pipeline.BUILD_HINTS.values())
    assert "scripts/pipeline.py" not in joined
    assert ".json" not in joined
    assert "artifacts/" not in joined
    assert "research-prepare" not in joined
    assert "evidence-build" not in joined
    assert "LLM" in pipeline.BUILD_HINTS["formal_search_plan"]
    assert "LLM" in pipeline.BUILD_HINTS["research_evidence_db"]
    assert "repair banker_page_pack" in pipeline.BUILD_HINTS["deck_blueprint"]


def test_status_path_does_not_route_through_template_registry() -> None:
    import pipeline

    assert "template_registry" not in pipeline.MAIN_STATUS_PATH


def test_status_path_does_not_route_through_pre_ppt_gate() -> None:
    import pipeline

    assert "pre_ppt" not in pipeline.MAIN_STATUS_PATH


def test_status_path_does_not_route_through_research_pack_export() -> None:
    import pipeline

    assert "research_pack" not in pipeline.MAIN_STATUS_PATH


def test_status_path_does_not_require_material_extracts_for_short_briefs() -> None:
    import pipeline

    assert "input_card" in pipeline.MAIN_STATUS_PATH
    assert "material_extracts" not in pipeline.MAIN_STATUS_PATH


def test_status_path_uses_research_graph_state_not_derived_execution_views() -> None:
    import pipeline

    assert "research_graph_state" in pipeline.MAIN_STATUS_PATH
    assert "formal_research_execution" not in pipeline.MAIN_STATUS_PATH
    assert "source_archive" not in pipeline.MAIN_STATUS_PATH


def test_status_path_does_not_route_through_internal_compile_artifacts() -> None:
    import pipeline

    internal_compile_artifacts = {
        "deck_blueprint",
        "page_evidence_contract",
        "renderer_spec",
    }

    assert not (internal_compile_artifacts & set(pipeline.MAIN_STATUS_PATH))
    assert internal_compile_artifacts <= pipeline.INTERNAL_VALIDATE_ARTIFACTS


def test_status_does_not_backfill_research_workbench_after_evidence_db_exists(tmp_path: Path) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    for artifact in ("input_card", "material_extracts", "industry_scope_pack"):
        _write_json(run_dir / pipeline.ARTIFACT_PATHS[artifact], {"schema_version": artifact})
        _write_json(
            run_dir / pipeline.VALIDATION_OUTPUTS[artifact],
            {"is_valid": True, "errors": [], "warnings": []},
        )
    _write_json(
        run_dir / pipeline.ARTIFACT_PATHS["research_evidence_db"],
        {"schema_version": "research_evidence_db_v1", "source_of_truth": True},
    )
    _write_json(
        run_dir / pipeline.VALIDATION_OUTPUTS["research_evidence_db"],
        {"is_valid": True, "errors": [], "warnings": []},
    )

    payload = pipeline.build_run_status(run_dir, include_debug_commands=True)
    milestones = {row["stage"]: row["state"] for row in payload["milestones"]}
    artifacts = {row["artifact"]: row for row in payload["artifacts"]}

    assert payload["current_stage"] == "banker_page_pack"
    assert payload["current_state"] == "needs_owner_authoring"
    assert milestones["research_planning"] == "covered_by_downstream_authoring"
    assert milestones["query_authoring"] == "covered_by_downstream_authoring"
    assert milestones["research_execution"] == "covered_by_downstream_authoring"
    assert artifacts["formal_search_plan"]["covered_by"] == "research_evidence_db"
    assert artifacts["executable_search_batch"]["covered_by"] == "research_evidence_db"
    assert artifacts["research_graph_state"]["covered_by"] == "research_evidence_db"
    assert "formal_search_plan" not in payload["recommended_next_actions"][0]
    assert "executable_search_batch" not in payload["recommended_next_actions"][0]
    assert "research_graph_state" not in payload["recommended_next_actions"][0]


def test_status_does_not_backfill_early_workbenches_after_evidence_db_exists(tmp_path: Path) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(run_dir / pipeline.ARTIFACT_PATHS["input_card"], {"schema_version": "input_card", "raw_brief": "brief"})
    _write_json(
        run_dir / pipeline.VALIDATION_OUTPUTS["input_card"],
        {"is_valid": True, "errors": [], "warnings": []},
    )
    _write_json(
        run_dir / pipeline.ARTIFACT_PATHS["research_evidence_db"],
        {"schema_version": "research_evidence_db_v1", "source_of_truth": True},
    )
    _write_json(
        run_dir / pipeline.VALIDATION_OUTPUTS["research_evidence_db"],
        {"is_valid": True, "errors": [], "warnings": []},
    )

    payload = pipeline.build_run_status(run_dir, include_debug_commands=True)
    milestones = {row["stage"]: row["state"] for row in payload["milestones"]}
    artifacts = {row["artifact"]: row for row in payload["artifacts"]}

    assert payload["current_stage"] == "banker_page_pack"
    assert payload["current_state"] == "needs_owner_authoring"
    assert milestones["material_intake"] == "structure_checked"
    assert milestones["industry_scoping"] == "covered_by_downstream_authoring"
    assert milestones["research_planning"] == "covered_by_downstream_authoring"
    assert "material_extracts" not in artifacts
    assert artifacts["industry_scope_pack"]["covered_by"] == "research_evidence_db"
    assert "material_extracts" not in payload["recommended_next_actions"][0]
    assert "industry_scope_pack" not in payload["recommended_next_actions"][0]


def test_status_routes_to_page_pack_without_template_registry_stage(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()

    def fake_status(_run_dir, artifact):
        state = "missing" if artifact == "banker_page_pack" else "valid"
        return {
            "artifact": artifact,
            "path": str(run_dir / f"{artifact}.json"),
            "exists": state == "valid",
            "check_output": str(run_dir / "artifacts" / f"{artifact}_validation.json"),
            "check_output_exists": state == "valid",
            "state": state,
            "error_count": 0,
            "errors": [],
            "helper_check_command": pipeline.helper_check_command(run_dir, artifact),
            "builder_or_owner_action": pipeline.BUILD_HINTS.get(artifact, ""),
        }

    monkeypatch.setattr(
        pipeline,
        "MAIN_STATUS_PATH",
        ["input_card", "research_pack", "banker_page_pack", "deck_blueprint"],
    )
    monkeypatch.setattr(pipeline, "artifact_status", fake_status)

    payload = pipeline.build_run_status(run_dir)

    assert payload["current_stage"] == "banker_page_pack"
    assert "Generation LLM writes the client-facing banker page pack" in payload["current_owner_action"]
    assert ".json" not in payload["current_owner_action"]
    assert "artifacts" not in payload
    assert "research_pack" not in {row["stage"] for row in payload["milestones"]}


def test_status_maps_internal_compile_artifact_to_owner_stage(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()

    def fake_status(_run_dir, artifact):
        state = "missing" if artifact == "deck_blueprint" else "valid"
        return {
            "artifact": artifact,
            "path": str(run_dir / f"{artifact}.json"),
            "exists": state == "valid",
            "check_output": str(run_dir / "artifacts" / f"{artifact}_validation.json"),
            "check_output_exists": state == "valid",
            "state": state,
            "error_count": 0,
            "errors": [],
            "helper_check_command": pipeline.helper_check_command(run_dir, artifact),
            "builder_or_owner_action": pipeline.BUILD_HINTS.get(artifact, ""),
        }

    monkeypatch.setattr(
        pipeline,
        "MAIN_STATUS_PATH",
        ["input_card", "research_pack", "banker_page_pack", "deck_blueprint"],
    )
    monkeypatch.setattr(pipeline, "artifact_status", fake_status)

    payload = pipeline.build_run_status(run_dir)

    assert payload["current_stage"] == "structured_render_helper"
    assert "current_artifact" not in payload
    debug_payload = pipeline.build_run_status(run_dir, include_debug_commands=True)
    assert debug_payload["current_artifact"] == "deck_blueprint"
    assert "do not hand-edit helper files" in payload["current_owner_action"]
    assert "deck_blueprint" not in payload["recommended_next_actions"][0]
    assert "artifacts" not in payload
    assert "deck_blueprint" not in {row["stage"] for row in payload["milestones"]}


def test_style_guided_deck_blueprint_does_not_require_template_slot_fields(tmp_path: Path) -> None:
    from validate_artifact import validate_artifact

    _write_json(
        tmp_path / "deck_blueprint.json",
        {
            "schema_version": "deck_blueprint_v1",
            "rendering_policy": {"template_contract_mode": "style_guided"},
            "slides": [
                {
                    "slide_no": 1,
                    "banker_page_id": "BP-001",
                    "headline": "A client-facing market view",
                    "page_argument": "The page has a clear market argument and a visible body module.",
                    "body_blocks": [{"copy": "Evidence-backed body copy carries the page without template slot labels."}],
                }
            ],
        },
    )

    errors, warnings = validate_artifact("deck_blueprint", tmp_path)

    assert errors == []
    assert not any("selected_page_type" in warning or "main_message" in warning for warning in warnings)


def test_style_guided_deck_blueprint_can_derive_headline_from_page_argument(tmp_path: Path) -> None:
    from renderer_compile_utils import build_banker_page_contract, build_renderer_spec_from_deck_blueprint
    from validate_artifact import validate_artifact

    deck = {
        "schema_version": "deck_blueprint_v1",
        "rendering_policy": {"template_contract_mode": "style_guided"},
        "slides": [
            {
                "slide_no": 1,
                "banker_page_id": "BP-001",
                "page_argument": "Category economics support a focused market discussion.",
                "body_blocks": [{"copy": "Evidence-backed body copy carries the page without a separate title field."}],
            }
        ],
    }
    _write_json(tmp_path / "deck_blueprint.json", deck)

    errors, _ = validate_artifact("deck_blueprint", tmp_path)
    contract = build_banker_page_contract(deck)
    renderer = build_renderer_spec_from_deck_blueprint(deck, {}, contract)

    assert errors == []
    assert renderer["slides"][0]["headline"] == "Category economics support a focused market discussion."


def test_style_guided_deck_blueprint_title_only_page_is_llm_warning_not_gate(tmp_path: Path) -> None:
    from validate_artifact import validate_artifact

    _write_json(
        tmp_path / "deck_blueprint.json",
        {
            "schema_version": "deck_blueprint_v1",
            "rendering_policy": {"template_contract_mode": "style_guided"},
            "slides": [
                {
                    "slide_no": 1,
                    "banker_page_id": "BP-001",
                    "headline": "A concise divider or title-led page may be intentional",
                    "page_argument": "LLM/QC should decide whether the page needs more substance.",
                }
            ],
        },
    )

    errors, warnings = validate_artifact("deck_blueprint", tmp_path)

    assert errors == []
    assert any("no substantive page payload" in warning for warning in warnings)
    assert any("LLM/QC should decide" in warning for warning in warnings)


def test_strict_layout_deck_blueprint_title_only_page_remains_blocked(tmp_path: Path) -> None:
    from validate_artifact import validate_artifact

    _write_json(
        tmp_path / "deck_blueprint.json",
        {
            "schema_version": "deck_blueprint_v1",
            "rendering_policy": {"template_contract_mode": "strict_layout"},
            "slides": [
                {
                    "slide_no": 1,
                    "banker_page_id": "BP-001",
                    "headline": "Strict layout needs a renderable placeholder payload",
                    "main_message": "Strict layout is intentionally constrained.",
                    "selected_page_type": "summary_page",
                }
            ],
        },
    )

    errors, warnings = validate_artifact("deck_blueprint", tmp_path)

    assert any("no substantive page payload" in error for error in errors)
    assert not any("no substantive page payload" in warning for warning in warnings)


def test_strict_layout_deck_blueprint_requires_template_slot_fields(tmp_path: Path) -> None:
    from validate_artifact import validate_artifact

    _write_json(
        tmp_path / "deck_blueprint.json",
        {
            "schema_version": "deck_blueprint_v1",
            "rendering_policy": {"template_contract_mode": "strict_layout"},
            "slides": [
                {
                    "slide_no": 1,
                    "banker_page_id": "BP-001",
                    "headline": "A client-facing market view",
                    "body_blocks": [{"copy": "Strict layout needs the template variant fields."}],
                }
            ],
        },
    )

    errors, _ = validate_artifact("deck_blueprint", tmp_path)

    assert any("main_message is required in strict_layout" in error for error in errors)
    assert any("selected_page_type is required in strict_layout" in error for error in errors)


def test_pipeline_command_surface_does_not_expose_checkpoint_alias() -> None:
    result = _run([sys.executable, "scripts/pipeline.py", "--help"])

    assert result.returncode == 0
    assert "checkpoint" not in result.stdout
    assert "route" not in result.stdout
    assert "summary" not in result.stdout
    assert "compile" not in result.stdout
    assert "review" not in result.stdout
    assert "status" in result.stdout
    assert "next" in result.stdout


def test_status_routes_structure_complete_not_ready_pack_to_targeted_research(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {
                "business_action": "targeted_research",
                "targeted_research_rationale": "Need one opened market-size source.",
            },
            "slides": [],
        },
    )

    monkeypatch.setattr(pipeline, "MAIN_STATUS_PATH", ["input_card", "banker_page_pack"])
    monkeypatch.setattr(
        pipeline,
        "artifact_status",
        lambda _run_dir, artifact: {
            "artifact": artifact,
            "path": str(run_dir / f"{artifact}.json"),
            "exists": True,
            "check_output": str(run_dir / "artifacts" / f"{artifact}_validation.json"),
            "check_output_exists": True,
            "state": "valid",
            "error_count": 0,
            "errors": [],
            "helper_check_command": pipeline.helper_check_command(run_dir, artifact),
            "builder_or_owner_action": "",
        },
    )

    payload = pipeline.build_run_status(run_dir)

    assert payload["status"] == "needs_targeted_research"
    assert payload["current_stage"] == "targeted_research_queue"
    assert payload["llm_deliverable_readiness"]["is_client_ready"] is False
    assert "route_if_not_ready" not in payload["llm_deliverable_readiness"]
    assert payload["llm_deliverable_readiness"]["next_business_action"] == (
        "run one bounded targeted research pass that could change a page decision"
    )
    assert "author a bounded targeted research queue" in payload["recommended_next_actions"][0]
    assert "artifacts/" not in payload["recommended_next_actions"][0]

    report_path = run_dir / "artifacts/status_report.md"
    pipeline.write_status_markdown(payload, report_path)
    report_text = report_path.read_text(encoding="utf-8")
    assert "LLM delivery readiness: `needs_targeted_research`" in report_text
    assert "## Next Actions" in report_text
    assert "## Mechanical Checks" not in report_text
    assert "## Optional Mechanical Checks" not in report_text
    assert "## Optional Mechanical Reviews" not in report_text
    assert "research_limited" not in report_text


def test_status_missing_ppt_offers_direct_composition_or_compiled_render(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {"business_action": "client_ready", "readiness_note": "Ready for output."},
            "slides": [
                {
                    "headline": "Category economics support the pitch",
                    "page_argument": "The page pack is ready for editable PPT output.",
                    "body_blocks": [{"copy": "A source-linked body point supports the client-facing argument."}],
                }
            ],
        },
    )
    monkeypatch.setattr(
        pipeline,
        "MAIN_STATUS_PATH",
        [
            "input_card",
            "industry_scope_pack",
            "formal_search_plan",
            "executable_search_batch",
            "research_graph_state",
            "research_evidence_db",
            "banker_page_pack",
            "filled_ppt",
        ],
    )

    def fake_artifact_status(_run_dir: Path, artifact: str) -> dict[str, object]:
        state = "missing" if artifact == "filled_ppt" else "valid"
        return {
            "artifact": artifact,
            "path": str(run_dir / pipeline.ARTIFACT_PATHS.get(artifact, f"{artifact}.json")),
            "exists": artifact != "filled_ppt",
            "check_output": str(run_dir / pipeline.VALIDATION_OUTPUTS.get(artifact, f"artifacts/{artifact}_validation.json")),
            "check_output_exists": artifact != "filled_ppt",
            "state": state,
            "error_count": 0,
            "errors": [],
            "helper_check_command": pipeline.helper_check_command(run_dir, artifact),
            "builder_or_owner_action": pipeline.BUILD_HINTS.get(artifact, ""),
        }

    monkeypatch.setattr(pipeline, "artifact_status", fake_artifact_status)

    payload = pipeline.build_run_status(run_dir)
    joined = json.dumps(payload, ensure_ascii=False)

    assert payload["current_stage"] == "ppt_render"
    assert "structured render" in joined
    assert "direct editable PPT composition" in joined
    assert "reviewed banker_page_pack" in joined
    assert "Output renders" not in joined


def test_filled_ppt_status_uses_latest_final_ppt_marker(tmp_path: Path) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    with zipfile.ZipFile(run_dir / "client_style_direct_composition.pptx", "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types></Types>")
    (run_dir / "LATEST_FINAL_PPT.txt").write_text("client_style_direct_composition.pptx\n", encoding="utf-8")

    status = pipeline.artifact_status(run_dir, "filled_ppt")

    assert status["exists"] is True
    assert status["state"] == "unvalidated"
    assert status["path"].endswith("client_style_direct_composition.pptx")
    assert status["alternate_path_used"].endswith("client_style_direct_composition.pptx")


def test_status_routes_valid_not_ready_page_pack_to_research_before_rendering(tmp_path: Path) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    authoring_path = [
        "input_card",
        "industry_scope_pack",
        "formal_search_plan",
        "executable_search_batch",
        "research_graph_state",
        "research_evidence_db",
        "banker_page_pack",
    ]
    for artifact in authoring_path:
        path = run_dir / pipeline.ARTIFACT_PATHS[artifact]
        if artifact == "banker_page_pack":
            payload = {
                "schema_version": "banker_page_pack",
                "deliverable_readiness": {
                    "business_action": "targeted_research",
                    "readiness_note": "Needs targeted research: one opened source could change chart readiness."
                },
                "slides": [
                    {
                        "page_argument": "Channel evidence is promising but the chart still needs one opened source."
                    }
                ],
            }
        else:
            payload = {"schema_version": artifact}
        _write_json(path, payload)
        _write_json(
            run_dir / pipeline.VALIDATION_OUTPUTS.get(artifact, f"artifacts/{artifact}_validation.json"),
            {"is_valid": True, "errors": [], "warnings": []},
        )

    payload = pipeline.build_run_status(run_dir)

    assert not (run_dir / pipeline.CLEAN_PPT).exists()
    assert payload["status"] == "needs_targeted_research"
    assert payload["current_stage"] == "targeted_research_queue"
    assert payload["current_state"] == "needs_llm_authoring_or_execution"
    assert "route_if_not_ready" not in payload["llm_deliverable_readiness"]
    assert payload["llm_deliverable_readiness"]["status_label"] == "needs_targeted_research"
    assert "author a bounded targeted research queue" in payload["recommended_next_actions"][0]
    assert "Output renders" not in json.dumps(payload, ensure_ascii=False)


def test_status_keeps_final_active_research_cycle_but_does_not_exceed_cap(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {
                "business_action": "targeted_research",
                "targeted_research_rationale": "Need one final source check.",
            },
            "slides": [],
        },
    )
    _write_json(
        run_dir / "artifacts/research_request_queue.json",
        {
            "schema_version": "research_request_queue",
            "loop_control": {"current_cycle": 2, "max_cycles": 2},
            "requests": [
                {
                    "active": True,
                    "request_id": "RQ-001",
                    "research_question": "Can a public source support the key exhibit metric?",
                    "origin_page_argument_id": "BP-001",
                    "status": "waiting for one final named-source check",
                }
            ],
        },
    )

    monkeypatch.setattr(pipeline, "MAIN_STATUS_PATH", ["input_card", "banker_page_pack"])
    monkeypatch.setattr(
        pipeline,
        "artifact_status",
        lambda _run_dir, artifact: {
            "artifact": artifact,
            "path": str(run_dir / f"{artifact}.json"),
            "exists": True,
            "check_output": str(run_dir / "artifacts" / f"{artifact}_validation.json"),
            "check_output_exists": True,
            "state": "valid",
            "error_count": 0,
            "errors": [],
            "helper_check_command": pipeline.helper_check_command(run_dir, artifact),
            "builder_or_owner_action": "",
        },
    )

    payload = pipeline.build_run_status(run_dir)

    assert payload["status"] == "needs_targeted_research"
    assert payload["current_stage"] == "targeted_research_queue"
    assert payload["research_loop_state"]["status_label"] == "final_targeted_research_cycle"
    assert payload["research_loop_state"]["loop_exhausted"] is False
    assert "route" not in payload["research_loop_state"]
    assert "active_request_count" not in payload["research_loop_state"]
    assert all("scripts/pipeline.py" not in item for item in payload["recommended_next_actions"])
    assert "optional_helper_checks" not in payload
    assert "debug_helper_check_commands" not in payload

    debug_payload = pipeline.build_run_status(run_dir, include_debug_commands=True)
    assert all("scripts/pipeline.py" not in item for item in debug_payload["optional_helper_checks"])
    assert debug_payload["optional_helper_checks"].count(
        "Optional helper check for `research_request_queue` after the owner action; "
        "rerun status/next with --include-debug-commands only when the exact command is needed."
    ) == 1
    assert debug_payload["debug_helper_check_commands"].count(
        pipeline.helper_check_command(run_dir, "research_request_queue")
    ) == 1

    report_path = run_dir / "artifacts/status_report.md"
    pipeline.write_status_markdown(payload, report_path)
    assert "LLM delivery readiness: `final_targeted_research_cycle`" in report_path.read_text(encoding="utf-8")
    message = pipeline._targeted_research_required_message(run_dir, "Need one final source check.")
    assert "After each cycle, update request outcomes" in message
    assert "do not rerun unchanged active requests" in message


def test_status_does_not_continue_loop_when_queue_has_no_active_requests(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {
                "business_action": "targeted_research",
                "targeted_research_rationale": "Evidence gap remains, but no targeted request is active.",
            },
            "slides": [],
        },
    )
    _write_json(
        run_dir / "artifacts/research_request_queue.json",
        {
            "schema_version": "research_request_queue",
            "loop_control": {"current_cycle": 1, "max_cycles": 2},
            "requests": [],
        },
    )

    monkeypatch.setattr(pipeline, "MAIN_STATUS_PATH", ["input_card", "banker_page_pack"])
    monkeypatch.setattr(
        pipeline,
        "artifact_status",
        lambda _run_dir, artifact: {
            "artifact": artifact,
            "path": str(run_dir / f"{artifact}.json"),
            "exists": True,
            "check_output": str(run_dir / "artifacts" / f"{artifact}_validation.json"),
            "check_output_exists": True,
            "state": "valid",
            "error_count": 0,
            "errors": [],
            "helper_check_command": pipeline.helper_check_command(run_dir, artifact),
            "builder_or_owner_action": "",
        },
    )

    payload = pipeline.build_run_status(run_dir)

    assert payload["status"] == "needs_targeted_research"
    assert payload["research_loop_state"]["status_label"] == "record_cycle_outcome_or_author_request"
    assert payload["research_loop_state"]["loop_exhausted"] is False
    assert "route" not in payload["research_loop_state"]
    message = pipeline._targeted_research_required_message(
        run_dir,
        "Evidence gap remains, but no targeted request is active.",
    )
    assert "has no active request" in message
    assert "add a narrow request" in message
    assert "ask QC/user to decide the remaining gap" in message


def test_status_treats_research_queue_missing_active_flags_as_active_warning(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {
                "business_action": "targeted_research",
                "targeted_research_rationale": "One more narrow source check could still change exhibit readiness.",
            },
            "slides": [],
        },
    )
    _write_json(
        run_dir / "artifacts/research_request_queue.json",
        {
            "schema_version": "research_request_queue",
            "loop_control": {"current_cycle": 1, "max_cycles": 2},
            "requests": [
                {
                    "request_id": "RQ-001",
                    "research_question": "Can a public source support the key exhibit metric?",
                    "status": "waiting for one final source check",
                }
            ],
        },
    )

    monkeypatch.setattr(pipeline, "MAIN_STATUS_PATH", ["input_card", "banker_page_pack"])
    monkeypatch.setattr(
        pipeline,
        "artifact_status",
        lambda _run_dir, artifact: {
            "artifact": artifact,
            "path": str(run_dir / f"{artifact}.json"),
            "exists": True,
            "check_output": str(run_dir / "artifacts" / f"{artifact}_validation.json"),
            "check_output_exists": True,
            "state": "valid",
            "error_count": 0,
            "errors": [],
            "helper_check_command": pipeline.helper_check_command(run_dir, artifact),
            "builder_or_owner_action": "",
        },
    )

    payload = pipeline.build_run_status(run_dir)

    assert payload["research_loop_state"]["status_label"] == "continue_targeted_research"
    assert "route" not in payload["research_loop_state"]
    assert "missing_active_flags" not in payload["research_loop_state"]
    assert "active_request_count" not in payload["research_loop_state"]
    assert "Some requests do not say whether they remain active" in payload["research_loop_state"]["note"]
    message = pipeline._targeted_research_required_message(
        run_dir,
        "One more narrow source check could still change exhibit readiness.",
    )
    assert "Requests missing active are treated as active" in message
    assert "close resolved or exhausted requests in the queue after the cycle" in message


def test_status_does_not_treat_early_cycle_outcome_as_loop_exhausted(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {
                "business_action": "targeted_research",
                "targeted_research_rationale": "One more narrow source check could still change exhibit readiness.",
            },
            "slides": [],
        },
    )
    _write_json(
        run_dir / "artifacts/research_request_queue.json",
        {
            "schema_version": "research_request_queue",
            "loop_control": {
                "current_cycle": 1,
                "max_cycles": 2,
                "latest_cycle_outcome": "Cycle 1 found category context but not audit-grade chart support.",
            },
            "requests": [],
        },
    )

    monkeypatch.setattr(pipeline, "MAIN_STATUS_PATH", ["input_card", "banker_page_pack"])
    monkeypatch.setattr(
        pipeline,
        "artifact_status",
        lambda _run_dir, artifact: {
            "artifact": artifact,
            "path": str(run_dir / f"{artifact}.json"),
            "exists": True,
            "check_output": str(run_dir / "artifacts" / f"{artifact}_validation.json"),
            "check_output_exists": True,
            "state": "valid",
            "error_count": 0,
            "errors": [],
            "helper_check_command": pipeline.helper_check_command(run_dir, artifact),
            "builder_or_owner_action": "",
        },
    )

    payload = pipeline.build_run_status(run_dir)

    assert payload["status"] == "needs_targeted_research"
    assert payload["research_loop_state"]["status_label"] == "narrow_next_request_or_record_source_limit"
    assert payload["research_loop_state"]["loop_exhausted"] is False
    assert "route" not in payload["research_loop_state"]
    message = pipeline._targeted_research_required_message(
        run_dir,
        "One more narrow source check could still change exhibit readiness.",
    )
    assert "prior cycle outcome but no active request" in message
    assert "loop budget remains" in message
    assert "add one narrower next-cycle request" in message
    assert "sources are unavailable" in message
    assert "bounded targeted research loop is exhausted" not in message


def test_status_treats_final_cycle_outcome_as_loop_exhausted_even_if_queue_has_active_rows(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {
                "business_action": "targeted_research",
                "targeted_research_rationale": "Final targeted searches did not change the page decision.",
            },
            "slides": [],
        },
    )
    _write_json(
        run_dir / "artifacts/research_request_queue.json",
        {
            "schema_version": "research_request_queue",
            "loop_control": {
                "current_cycle": 2,
                "max_cycles": 2,
                "latest_cycle_outcome": "Final targeted searches did not find audit-grade support.",
            },
            "requests": [
                {
                    "active": True,
                    "request_id": "RQ-001",
                    "research_question": "Can a public source support the key exhibit metric?",
                    "origin_page_argument_id": "BP-001",
                    "status": "still active",
                }
            ],
        },
    )

    monkeypatch.setattr(pipeline, "MAIN_STATUS_PATH", ["input_card", "banker_page_pack"])
    monkeypatch.setattr(
        pipeline,
        "artifact_status",
        lambda _run_dir, artifact: {
            "artifact": artifact,
            "path": str(run_dir / f"{artifact}.json"),
            "exists": True,
            "check_output": str(run_dir / "artifacts" / f"{artifact}_validation.json"),
            "check_output_exists": True,
            "state": "valid",
            "error_count": 0,
            "errors": [],
            "helper_check_command": pipeline.helper_check_command(run_dir, artifact),
            "builder_or_owner_action": "",
        },
    )

    payload = pipeline.build_run_status(run_dir)

    assert payload["status"] == "needs_qc_user_decision_after_research_loop_cap"
    assert payload["research_loop_state"]["status_label"] == "loop_exhausted_qc_user_decision"
    assert payload["research_loop_state"]["loop_exhausted"] is True
    assert "route" not in payload["research_loop_state"]

    message = pipeline._targeted_research_required_message(
        run_dir,
        "Final targeted searches did not change the page decision.",
    )
    assert "bounded targeted research loop is exhausted" in message
    assert "Do not start another search loop" in message
    assert "create only a non-final research-limited review copy" in message
    assert "accept an evidence-limited review state" not in message


def test_status_routes_exhausted_research_loop_to_qc_user_decision(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {
                "business_action": "targeted_research",
                "targeted_research_rationale": "Final targeted searches did not find support.",
            },
            "slides": [],
        },
    )
    _write_json(
        run_dir / "artifacts/research_request_queue.json",
        {
            "schema_version": "research_request_queue",
            "loop_control": {"current_cycle": 2, "max_cycles": 2},
            "requests": [
                {
                    "active": False,
                    "request_id": "RQ-001",
                    "research_question": "Can a public source support the key exhibit metric?",
                    "origin_page_argument_id": "BP-001",
                    "status": "已完成，未找到可改变页面授权的来源",
                }
            ],
        },
    )

    monkeypatch.setattr(pipeline, "MAIN_STATUS_PATH", ["input_card", "banker_page_pack"])
    monkeypatch.setattr(
        pipeline,
        "artifact_status",
        lambda _run_dir, artifact: {
            "artifact": artifact,
            "path": str(run_dir / f"{artifact}.json"),
            "exists": True,
            "check_output": str(run_dir / "artifacts" / f"{artifact}_validation.json"),
            "check_output_exists": True,
            "state": "valid",
            "error_count": 0,
            "errors": [],
            "helper_check_command": pipeline.helper_check_command(run_dir, artifact),
            "builder_or_owner_action": "",
        },
    )

    payload = pipeline.build_run_status(run_dir)

    assert payload["status"] == "needs_qc_user_decision_after_research_loop_cap"
    assert payload["current_stage"] == "banker_page_pack"
    assert payload["current_state"] == "targeted_research_loop_exhausted"
    assert payload["research_loop_state"]["status_label"] == "loop_exhausted_qc_user_decision"
    assert payload["research_loop_state"]["loop_exhausted"] is True
    assert "route" not in payload["research_loop_state"]
    assert "QC/user decision" in payload["recommended_next_actions"][0]

    report_path = run_dir / "artifacts/status_report.md"
    pipeline.write_status_markdown(payload, report_path)
    report_text = report_path.read_text(encoding="utf-8")
    assert "LLM delivery readiness: `loop_exhausted_qc_user_decision`" in report_text
    assert "research_limited" not in report_text

    message = pipeline._targeted_research_required_message(run_dir, "Final targeted searches did not find support.")
    assert "bounded targeted research loop is exhausted" in message
    assert "Do not start another search loop" in message
    assert "create only a non-final research-limited review copy" in message
    assert "choose evidence-limited review" not in json.dumps(payload, ensure_ascii=False)
    assert "accept an evidence-limited review state" not in message


def test_status_routes_missing_readiness_back_to_page_pack_decision(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "slides": [{"page_argument": "Industry argument.", "headline": "Client-facing market read"}],
        },
    )

    monkeypatch.setattr(pipeline, "MAIN_STATUS_PATH", ["input_card", "banker_page_pack"])
    monkeypatch.setattr(
        pipeline,
        "artifact_status",
        lambda _run_dir, artifact: {
            "artifact": artifact,
            "path": str(run_dir / f"{artifact}.json"),
            "exists": True,
            "check_output": str(run_dir / "artifacts" / f"{artifact}_validation.json"),
            "check_output_exists": True,
            "state": "valid",
            "error_count": 0,
            "errors": [],
            "helper_check_command": pipeline.helper_check_command(run_dir, artifact),
            "builder_or_owner_action": "",
        },
    )

    payload = pipeline.build_run_status(run_dir)

    assert payload["status"] == "needs_page_pack_readiness_decision"
    assert payload["current_stage"] == "banker_page_pack"
    assert payload["llm_deliverable_readiness"]["is_client_ready"] is False
    assert "route_if_not_ready" not in payload["llm_deliverable_readiness"]
    assert payload["llm_deliverable_readiness"]["next_business_action"] == "state the page-pack next action in business terms"
    assert "state the page-pack next action in business terms" in payload["recommended_next_actions"][0]


def test_status_uses_explicit_business_action_even_when_note_mentions_research(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {
                "business_action": "client_ready",
                "targeted_research_rationale": "Need an opened market-size source before chart use can be upgraded.",
            },
            "slides": [{"page_argument": "Industry argument.", "headline": "Client-facing market read"}],
        },
    )

    monkeypatch.setattr(pipeline, "MAIN_STATUS_PATH", ["input_card", "banker_page_pack"])
    monkeypatch.setattr(
        pipeline,
        "artifact_status",
        lambda _run_dir, artifact: {
            "artifact": artifact,
            "path": str(run_dir / f"{artifact}.json"),
            "exists": True,
            "check_output": str(run_dir / "artifacts" / f"{artifact}_validation.json"),
            "check_output_exists": True,
            "state": "valid",
            "error_count": 0,
            "errors": [],
            "helper_check_command": pipeline.helper_check_command(run_dir, artifact),
            "builder_or_owner_action": "",
        },
    )

    payload = pipeline.build_run_status(run_dir)

    assert payload["llm_deliverable_readiness"]["is_client_ready"] is True
    assert "route_if_not_ready" not in payload["llm_deliverable_readiness"]
    assert payload["llm_deliverable_readiness"]["next_business_action"] == "send final editable PPT when visual/source QC is clean"
    assert "routes to targeted research" not in payload["llm_deliverable_readiness"]["reason"]
    assert "opened market-size source" in payload["llm_deliverable_readiness"]["reason"]


def test_status_does_not_infer_targeted_research_from_natural_readiness_note(
    tmp_path: Path,
) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {
                "readiness_note": "Needs targeted research: one opened market-size source could change chart readiness."
            },
            "slides": [{"page_argument": "Industry argument.", "headline": "Client-facing market read"}],
        },
    )

    state = pipeline._llm_deliverable_readiness_state(run_dir)

    assert state["has_explicit_decision"] is False
    assert state["is_client_ready"] is False
    assert state["route_if_not_ready"] == "finish_banker_page_pack_readiness_decision"
    assert "does not give a clear final-output next action" in state["reason"]
    assert "market-size source" in state["reason"]


def test_status_routes_targeted_research_when_business_action_is_explicit(
    tmp_path: Path,
) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {
                "business_action": "targeted_research",
                "readiness_note": "需要补充公开来源：底妆市场规模来源会改变第2页图表能否使用。"
            },
            "slides": [{"page_argument": "Industry argument.", "headline": "Client-facing market read"}],
        },
    )

    state = pipeline._llm_deliverable_readiness_state(run_dir)

    assert state["has_explicit_decision"] is True
    assert state["is_client_ready"] is False
    assert state["route_if_not_ready"] == "bounded_targeted_research_then_rerender"
    assert "底妆市场规模" in state["reason"]


def test_status_routes_source_limit_readiness_to_qc_user_decision(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {
                "business_action": "qc_user_decision",
                "source_unavailable": True,
                "readiness_note": (
                    "Evidence-limited after bounded targeted research loop exhausted: "
                    "public sources unavailable for audit-grade market size."
                )
            },
            "slides": [{"page_argument": "Industry argument.", "headline": "Client-facing market read"}],
        },
    )

    state = pipeline._llm_deliverable_readiness_state(run_dir)

    assert state["has_explicit_decision"] is True
    assert state["is_client_ready"] is False
    assert state["route_if_not_ready"] == "qc_or_user_decision_after_source_limit"
    assert "asks for QC/user decision" in state["reason"]

    monkeypatch.setattr(pipeline, "MAIN_STATUS_PATH", ["input_card", "banker_page_pack"])
    monkeypatch.setattr(
        pipeline,
        "artifact_status",
        lambda _run_dir, artifact: {
            "artifact": artifact,
            "path": str(run_dir / f"{artifact}.json"),
            "exists": True,
            "check_output": str(run_dir / "artifacts" / f"{artifact}_validation.json"),
            "check_output_exists": True,
            "state": "valid",
            "error_count": 0,
            "errors": [],
            "helper_check_command": pipeline.helper_check_command(run_dir, artifact),
            "builder_or_owner_action": "",
        },
    )

    payload = pipeline.build_run_status(run_dir)

    assert payload["status"] == "needs_qc_user_decision_after_source_limit"
    assert payload["current_stage"] == "banker_page_pack"
    assert payload["current_state"] == "research_source_limit_reached"
    assert "route_if_not_ready" not in payload["llm_deliverable_readiness"]
    assert payload["llm_deliverable_readiness"]["next_business_action"] == "ask QC/user to decide after source limits"
    assert "QC/user decision" in payload["recommended_next_actions"][0]
    assert "author a bounded targeted research queue" not in json.dumps(payload, ensure_ascii=False)


def test_status_does_not_accept_bare_qc_user_decision_as_loop_escape(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {
                "business_action": "qc_user_decision",
                "readiness_note": "Evidence remains limited, so the user should decide.",
            },
            "slides": [{"page_argument": "Industry argument.", "headline": "Client-facing market read"}],
        },
    )

    state = pipeline._llm_deliverable_readiness_state(run_dir)

    assert state["has_explicit_decision"] is True
    assert state["is_client_ready"] is False
    assert state["route_if_not_ready"] == "bounded_targeted_research_then_rerender"
    assert "asks for QC/user decision" in state["reason"]
    assert "route to bounded targeted research first" in state["reason"]

    monkeypatch.setattr(pipeline, "MAIN_STATUS_PATH", ["input_card", "banker_page_pack"])
    monkeypatch.setattr(
        pipeline,
        "artifact_status",
        lambda _run_dir, artifact: {
            "artifact": artifact,
            "path": str(run_dir / f"{artifact}.json"),
            "exists": True,
            "check_output": str(run_dir / "artifacts" / f"{artifact}_validation.json"),
            "check_output_exists": True,
            "state": "valid",
            "error_count": 0,
            "errors": [],
            "helper_check_command": pipeline.helper_check_command(run_dir, artifact),
            "builder_or_owner_action": "",
        },
    )

    payload = pipeline.build_run_status(run_dir)

    assert payload["status"] == "needs_targeted_research"
    assert payload["current_stage"] == "targeted_research_queue"
    assert "author a bounded targeted research queue" in payload["recommended_next_actions"][0]


def test_status_routes_non_evidence_readiness_problem_to_page_pack_repair(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {
                "business_action": "repair_page_pack",
                "readiness_note": (
                    "Not client-ready: visible copy still sounds like internal workpaper language "
                    "and the pages need denser client-facing exhibits."
                )
            },
            "slides": [{"page_argument": "Industry argument.", "headline": "Client-facing market read"}],
        },
    )

    state = pipeline._llm_deliverable_readiness_state(run_dir)

    assert state["has_explicit_decision"] is True
    assert state["is_client_ready"] is False
    assert state["route_if_not_ready"] == "repair_banker_page_pack_before_render"

    monkeypatch.setattr(pipeline, "MAIN_STATUS_PATH", ["input_card", "banker_page_pack"])
    monkeypatch.setattr(
        pipeline,
        "artifact_status",
        lambda _run_dir, artifact: {
            "artifact": artifact,
            "path": str(run_dir / f"{artifact}.json"),
            "exists": True,
            "check_output": str(run_dir / "artifacts" / f"{artifact}_validation.json"),
            "check_output_exists": True,
            "state": "valid",
            "error_count": 0,
            "errors": [],
            "helper_check_command": pipeline.helper_check_command(run_dir, artifact),
            "builder_or_owner_action": "",
        },
    )

    payload = pipeline.build_run_status(run_dir)

    assert payload["status"] == "needs_banker_page_pack_repair"
    assert payload["current_stage"] == "banker_page_pack"
    assert "repair banker_page_pack" in payload["recommended_next_actions"][0]
    assert "do not start research unless" in payload["recommended_next_actions"][0]
    assert "route_if_not_ready" not in payload["llm_deliverable_readiness"]
    assert payload["llm_deliverable_readiness"]["next_business_action"] == (
        "repair page writing, exhibits, caveats, or density in banker_page_pack"
    )


def test_status_does_not_route_wording_pass_to_targeted_research(
    tmp_path: Path,
) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {
                "business_action": "repair_page_pack",
                "readiness_note": (
                    "Not client-ready: the section needs one more wording pass and denser exhibits; "
                    "the evidence base is sufficient for the current scope."
                )
            },
            "slides": [{"page_argument": "Industry argument.", "headline": "Client-facing market read"}],
        },
    )

    state = pipeline._llm_deliverable_readiness_state(run_dir)

    assert state["has_explicit_decision"] is True
    assert state["is_client_ready"] is False
    assert state["route_if_not_ready"] == "repair_banker_page_pack_before_render"


def test_status_rejects_string_readiness_label_as_undecided(
    tmp_path: Path,
) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": "NOT_CLIENT_READY",
            "slides": [{"page_argument": "Industry argument.", "headline": "Client-facing market read"}],
        },
    )

    state = pipeline._llm_deliverable_readiness_state(run_dir)

    assert state["has_explicit_decision"] is False
    assert state["is_client_ready"] is False
    assert state["route_if_not_ready"] == "finish_banker_page_pack_readiness_decision"
    assert "does not give a clear final-output next action" in state["reason"]


def test_status_does_not_infer_client_ready_from_natural_readiness_note(
    tmp_path: Path,
) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": "Client-ready at this scope: evidence is sufficient for formal render.",
            "slides": [{"page_argument": "Industry argument.", "headline": "Client-facing market read"}],
        },
    )

    state = pipeline._llm_deliverable_readiness_state(run_dir)

    assert state["has_explicit_decision"] is False
    assert state["is_client_ready"] is False
    assert state["route_if_not_ready"] == "finish_banker_page_pack_readiness_decision"
    assert "does not give a clear final-output next action" in state["reason"]


def test_status_routes_client_ready_when_business_action_is_explicit(
    tmp_path: Path,
) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {
                "business_action": "client_ready",
                "readiness_note": "证据足够，当前范围可正式交付并支持正式渲染。",
            },
            "slides": [{"page_argument": "Industry argument.", "headline": "Client-facing market read"}],
        },
    )

    state = pipeline._llm_deliverable_readiness_state(run_dir)

    assert state["has_explicit_decision"] is True
    assert state["is_client_ready"] is True
    assert state["route_if_not_ready"] == "client_ready"


def test_status_rejects_legacy_next_step_or_route_readiness_fields(
    tmp_path: Path,
) -> None:
    import pipeline

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {
                "next_step": "client_ready",
                "route": "client_ready",
                "readiness_note": "Legacy fields should not authorize delivery.",
            },
            "slides": [{"page_argument": "Industry argument.", "headline": "Client-facing market read"}],
        },
    )

    state = pipeline._llm_deliverable_readiness_state(run_dir)

    assert state["has_explicit_decision"] is False
    assert state["is_client_ready"] is False
    assert state["route_if_not_ready"] == "finish_banker_page_pack_readiness_decision"
    assert "does not give a clear final-output next action" in state["reason"]


def test_removed_legacy_readiness_fields_are_not_runtime_contract() -> None:
    runtime_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            SKILL_DIR / "SKILL.md",
            SKILL_DIR / "references/generation.md",
            SKILL_DIR / "references/reasoning.md",
            SKILL_DIR / "references/qc.md",
            SKILL_DIR / "scripts/qc/validate_artifact.py",
            SKILL_DIR / "scripts/pipeline.py",
        ]
    )

    assert "research_first_required" not in runtime_text
    assert "evidence_limited_pitch_outline" not in runtime_text
    assert "evidence_limited_rationale" not in runtime_text


def test_validate_artifact_cli_writes_output(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(run_dir / "input_card.json", {"raw_brief": "Sample brief"})
    output = run_dir / "artifacts/input_card_validation.json"

    result = _run([
        sys.executable,
        "scripts/pipeline.py",
        "review",
        "--artifact",
        "input_card",
        "--run-dir",
        str(run_dir),
        "--output",
        str(output),
    ])

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    keys = list(payload)
    assert keys.index("review_outcome") < keys.index("is_valid")
    assert payload["review_outcome"] == "structure_checked"
    assert payload["is_valid"] is True
    assert "validation_policy" not in payload
    assert payload["helper_check_policy"] == "structure_only"
    guidance = payload["owner_repair_guidance"]
    assert guidance["status"] == "structure_checked"
    assert "does not certify content quality" in guidance["next_action"]
    assert "final delivery quality" in guidance["next_action"]


def test_review_warnings_are_labeled_as_llm_prompts_not_validation_failures(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "input_card.json",
        {"schema_version": "input_card"},
    )

    result = _run([
        sys.executable,
        "scripts/pipeline.py",
        "review",
        "--artifact",
        "input_card",
        "--run-dir",
        str(run_dir),
    ])

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["is_valid"] is True
    assert payload["review_outcome"] == "checked_with_llm_prompts"
    assert payload["owner_repair_guidance"]["status"] == "checked_with_llm_prompts"
    assert "Use the prompts" in payload["owner_repair_guidance"]["next_action"]
    assert "reviewed_with_warnings" not in result.stdout


def test_pipeline_help_does_not_expose_template_registry_command() -> None:
    result = _run([sys.executable, "scripts/pipeline.py", "--help"])

    assert result.returncode == 0
    assert "review" not in result.stdout
    assert "compile" not in result.stdout
    assert "route" not in result.stdout
    assert "summary" not in result.stdout
    assert "validate" not in result.stdout
    assert "template-registry" not in result.stdout
    assert "validate-pre-ppt" not in result.stdout
    assert "evidence-build" not in result.stdout
    assert "evidence-export" not in result.stdout
    assert "research-prepare" not in result.stdout
    assert "research-compile" not in result.stdout
    assert "rebuild-stale" not in result.stdout


def test_pipeline_compile_is_not_a_hidden_operator_entrypoint() -> None:
    result = _run([sys.executable, "scripts/pipeline.py", "compile", "--help"])

    assert result.returncode != 0
    assert "invalid choice: 'compile'" in result.stderr


def test_pipeline_render_help_frames_render_as_optional_structured_helper() -> None:
    result = _run([sys.executable, "scripts/pipeline.py", "render", "--help"])

    assert result.returncode == 0
    assert "Structured-render helper" in result.stdout
    assert "directly compose editable text boxes" in result.stdout
    assert "without this command" in result.stdout


def test_low_level_helper_help_uses_workspace_language() -> None:
    research = _run([sys.executable, "scripts/research-external-evidence/ib_research_graph.py", "--help"])
    knowledge = _run([sys.executable, "scripts/knowledge-repository/research_evidence_db.py", "--help"])
    intake = _run([sys.executable, "scripts/material-intake/ingest_materials.py", "--help"])
    template = _run([sys.executable, "scripts/template/template_analyzer.py", "--help"])
    visual = _run([sys.executable, "scripts/output/postprocess_ppt_visuals.py", "--help"])
    qc = _run([sys.executable, "scripts/qc/validate_artifact.py", "--help"])

    assert research.returncode == 0
    assert knowledge.returncode == 0
    assert intake.returncode == 0
    assert template.returncode == 0
    assert visual.returncode == 0
    assert qc.returncode == 0
    for result in (research, knowledge, intake, template, visual, qc):
        assert "Internal" in result.stdout
    assert "prepare-workbench" in research.stdout
    assert " prepare " not in research.stdout
    assert "operator-facing" not in research.stdout
    assert "prepare-workspace" in knowledge.stdout
    assert " build " not in knowledge.stdout
    assert "Build research_evidence_db" not in knowledge.stdout
    assert "Knowledge LLM authors final EV/MET content" in knowledge.stdout
    assert "scripts/pipeline.py start-brief" in intake.stdout
    assert "scripts/pipeline.py render" in template.stdout
    assert "scripts/pipeline.py render" in visual.stdout
    assert "structure-only artifact checks" in qc.stdout
    normalized_visual_help = " ".join(visual.stdout.split())
    assert "does not author deck copy" in normalized_visual_help
    assert "final delivery quality" in normalized_visual_help


def test_pipeline_review_help_only_exposes_owner_facing_artifacts() -> None:
    result = _run([sys.executable, "scripts/pipeline.py", "review", "--help"])

    assert result.returncode == 0
    for hidden in (
        "deck_blueprint",
        "formal_research_execution",
        "material_manifest",
        "page_evidence_contract",
        "pre_ppt",
        "pre_research_pack",
        "research_pack",
        "renderer_spec",
        "source_archive",
        "template_registry",
    ):
        assert hidden not in result.stdout
    assert "banker_page_pack" in result.stdout
    assert "research_graph_state" in result.stdout
    assert "research_request_queue" in result.stdout


def test_pipeline_review_still_accepts_internal_artifact_when_explicit(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    result = _run([
        sys.executable,
        "scripts/pipeline.py",
        "review",
        "--artifact",
        "renderer_spec",
        "--run-dir",
        str(run_dir),
    ])

    assert result.returncode == 1
    assert "invalid choice" not in result.stderr
    assert "unknown artifact" not in result.stderr
    payload = json.loads(result.stdout)
    assert payload["artifact"] == "renderer_spec"


def test_pipeline_render_refreshes_structured_render_helpers_internally(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(
        run_dir / "banker_page_pack.json",
        {
            "schema_version": "banker_page_pack",
            "deliverable_readiness": {
                "business_action": "client_ready",
                "decision_note": "Enough support for a small client-facing draft.",
            },
            "slides": [
                {
                    "banker_page_id": "BP-001",
                    "slide_no": 1,
                    "headline": "Category growth supports a focused industry discussion",
                    "page_argument": "The market has enough visible demand and channel evidence to support an industry-led pitch page.",
                    "body_blocks": [
                        {
                            "copy": "Demand, channel behavior, and competitive positioning are presented as industry evidence rather than target promotion."
                        }
                    ],
                    "source_note": "Source: user-provided brief and current evidence database.",
                }
            ],
        },
    )

    result = _run([
        sys.executable,
        "scripts/pipeline.py",
        "render",
        "--run-dir",
        str(run_dir),
    ])

    assert result.returncode == 0, result.stdout + result.stderr
    assert (run_dir / "template_registry.json").exists()
    validation = json.loads((run_dir / "artifacts/template_registry_validation.json").read_text(encoding="utf-8"))
    assert validation["is_valid"] is True
    assert (run_dir / "deck_blueprint.json").exists()
    assert (run_dir / "renderer_spec.json").exists()
