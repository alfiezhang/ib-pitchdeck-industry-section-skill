# QC scripts and validators

QC owns every deterministic validator and the repair-routing scripts. Public state dashboards stay in root `scripts/`; QC validators live here so agents do not confuse validation ownership with artifact authoring ownership.

Public QC tools:
- `build_agent_handoff.py`
- `check_artifact_manifest.py`
- `check_json_files.py`
- `check_runtime_dependencies.py`
- `doctor_runtime.py`
- `generate_run_quality_summary.py`
- `qc_normalize_report.py`
- `qc_repair_targets.py`
- `qc_router.py`
- `repair_json_smart_quotes.py`
- `repair_visible_metric_claims.py`
- `report_run_status.py`

Validator folders:

## final
- `validators/final/validate_chart_metric_binding.py`
- `validators/final/validate_content_quality.py`
- `validators/final/validate_final_delivery.py`
- `validators/final/validate_run_artifacts.py`
- `validators/final/validate_stage_gate.py`

## generation
- `validators/generation/validate_deck_blueprint.py`
- `validators/generation/validate_page_evidence_contract.py`
- `validators/generation/validate_renderer_spec.py`

## knowledge
- `validators/knowledge/validate_research_evidence_db.py`
- `validators/knowledge/validate_research_pack.py`

## material
- `validators/material/validate_input_card.py`
- `validators/material/validate_material_extracts.py`
- `validators/material/validate_material_manifest.py`

## output
- `validators/output/validate_filled_ppt.py`
- `validators/output/validate_replacement_dict.py`

## reasoning
- `validators/reasoning/validate_hypothesis_store.py`
- `validators/reasoning/validate_issue_analysis.py`
- `validators/reasoning/validate_page_argument_pack.py`
- `validators/reasoning/validate_research_request_queue.py`

## research
- `validators/research/validate_formal_research_execution.py`
- `validators/research/validate_formal_search_plan.py`
- `validators/research/validate_source_archive.py`
- `validators/research/validate_source_reviews.py`

## scoping
- `validators/scoping/validate_industry_scope_pack.py`

## system
- `validators/system/validate_skill_package.py`
- `validators/system/validate_run_state.py`

## template
- `validators/template/validate_template_registry.py`

Format validators report deterministic red-lines. QC interprets those reports, performs LLM quality review where needed, and routes repair to the owning role.
