#!/usr/bin/env python3
"""Deterministic stage gates for the industry-section workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Optional

from deck_blueprint_utils import normalize_deck_blueprint_for_page_plan
from json_utils import load_json_file
from validate_content_quality import validate as validate_content_quality
from validate_chart_metric_binding import validate as validate_chart_metric_binding
from validate_industry_scope_pack import validate as validate_industry_scope_pack
from validate_issue_analysis import validate as validate_issue_analysis
from validate_research_pack import validate as validate_research_pack
from validate_page_evidence_contract import validate as validate_page_evidence_contract
from validate_deck_blueprint import validate as validate_deck_blueprint
from validate_renderer_spec import validate as validate_renderer_spec
from validate_run_artifacts import validate_search_log
from validate_source_reviews import validate as validate_source_reviews
from validate_template_registry import validate as validate_template_registry
from validate_formal_research_execution import validate as validate_formal_research_execution
from validate_formal_search_plan import validate as validate_formal_search_plan


REPO_ROOT = Path(__file__).resolve().parents[1]


def resolve_repo_path(path: Optional[Path]) -> Optional[Path]:
    if path is None:
        return None
    if path.is_absolute() or path.exists():
        return path
    return REPO_ROOT / path


def load_json_if_exists(path: Path, errors: list[str]) -> Optional[dict[str, Any]]:
    if not path.exists():
        errors.append(f"missing required artifact: {path}")
        return None
    try:
        data = load_json_file(path)
    except Exception as exc:
        errors.append(f"cannot read {path}: {exc}")
        return None
    if not isinstance(data, dict):
        errors.append(f"{path} must contain a JSON object")
        return None
    return data


def require_valid_artifact(path: Path, errors: list[str], warnings: list[str]) -> Optional[dict[str, Any]]:
    data = load_json_if_exists(path, errors)
    if not data:
        return None
    if data.get("is_valid") is False:
        errors.append(f"{path.name} is_valid=false")
    for key in ("errors", "blocking_issues"):
        values = data.get(key, [])
        if isinstance(values, list):
            warnings.extend(str(item) for item in values)
    return data


def require_no_blocking_artifact(path: Path, errors: list[str], warnings: list[str]) -> None:
    data = load_json_if_exists(path, errors)
    if not data:
        return
    if data.get("is_valid") is False:
        errors.append(f"{path.name} is_valid=false")
    blocking_items = data.get("blocking_issues") or []
    if blocking_items:
        errors.append(f"{path.name} contains {len(blocking_items)} blocking issue(s)")
    for key in ("errors", "blocking_issues", "warnings"):
        values = data.get(key, [])
        if isinstance(values, list):
            warnings.extend(str(item) for item in values)


def load_source_registry(path: Optional[Path], errors: list[str]) -> Optional[dict[str, Any]]:
    resolved = resolve_repo_path(path)
    if not resolved:
        return None
    if not resolved.exists():
        errors.append(f"source registry not found: {resolved}")
        return None
    try:
        data = load_json_file(resolved)
    except Exception as exc:
        errors.append(f"cannot read source registry {resolved}: {exc}")
        return None
    if not isinstance(data, dict):
        errors.append(f"source registry must be a JSON object: {resolved}")
        return None
    return data


def check_formal_search_plan_presence(
    run_dir: Path,
    errors: list[str],
    warnings: list[str],
) -> None:
    artifacts = run_dir / "artifacts"
    plan_path = artifacts / "formal_search_plan.json"
    search_log_path = artifacts / "search_log.md"

    validation_path = artifacts / "formal_search_plan_validation.json"
    require_valid_artifact(validation_path, errors, warnings)
    plan_data = load_json_if_exists(plan_path, errors)
    if isinstance(plan_data, dict):
        plan_errors, plan_warnings = validate_formal_search_plan(plan_data)
        if plan_errors:
            errors.append("current formal search plan validation failed")
            errors.extend(str(item) for item in plan_errors)
        warnings.extend(str(item) for item in plan_warnings)

    if not search_log_path.exists():
        errors.append(f"missing required artifact: {search_log_path}")
    else:
        search_errors, search_warnings = validate_search_log(search_log_path)
        errors.extend(search_errors)
        warnings.extend(search_warnings)


def validate_industry_scope_pack_gate(
    run_dir: Path,
    errors: list[str],
    warnings: list[str],
) -> None:
    artifacts = run_dir / "artifacts"
    scope_path = artifacts / "industry_scope_pack.json"
    validation_path = artifacts / "industry_scope_pack_validation.json"

    require_valid_artifact(validation_path, errors, warnings)
    scope_data = load_json_if_exists(scope_path, errors)
    if isinstance(scope_data, dict):
        current_errors, current_warnings = validate_industry_scope_pack(scope_data)
        if current_errors:
            errors.append("current industry scope pack validation failed")
            errors.extend(current_errors)
        warnings.extend(current_warnings)


def validate_formal_research_execution_gate(
    run_dir: Path,
    errors: list[str],
    warnings: list[str],
) -> None:
    artifacts = run_dir / "artifacts"
    report_path = artifacts / "formal_research_execution_report.json"
    validation_path = artifacts / "formal_research_execution_validation.json"
    plan_path = artifacts / "formal_search_plan.json"
    search_log_path = artifacts / "search_log.md"

    report_data = load_json_if_exists(report_path, errors)
    require_valid_artifact(validation_path, errors, warnings)
    plan_data = load_json_if_exists(plan_path, errors)

    if not search_log_path.exists():
        errors.append(f"missing required artifact: {search_log_path}")
        return

    if isinstance(report_data, dict) and isinstance(plan_data, dict):
        current_errors, current_warnings = validate_formal_research_execution(
            report_data,
            plan_data,
            search_log_path,
        )
        if current_errors:
            errors.append("current formal research execution report validation failed")
            errors.extend(current_errors)
        warnings.extend(current_warnings)


def validate_source_reviews_gate(
    run_dir: Path,
    errors: list[str],
    warnings: list[str],
    *,
    require_memo_binding: bool = False,
) -> None:
    artifacts = run_dir / "artifacts"
    source_reviews_path = artifacts / "source_reviews.json"
    validation_path = artifacts / "source_reviews_validation.json"
    archive_validation_path = artifacts / "source_archive_validation.json"
    search_log_path = artifacts / "search_log.md"
    report_path = artifacts / "formal_research_execution_report.json"
    memo_path = run_dir / "industry_research_pack.md"
    archive_index_path = run_dir / "artifacts" / "source_archive" / "source_archive_index.json"

    require_valid_artifact(validation_path, errors, warnings)
    require_valid_artifact(archive_validation_path, errors, warnings)
    result = validate_source_reviews(
        source_reviews_path,
        search_log_path=search_log_path if search_log_path.exists() else None,
        formal_research_execution_report_path=report_path if report_path.exists() else None,
        memo_path=memo_path if require_memo_binding and memo_path.exists() else None,
        source_archive_index_path=archive_index_path,
        run_dir=run_dir,
    )
    if result.get("is_valid") is False:
        errors.append("current source review validation failed")
        errors.extend(str(item) for item in result.get("errors", []))
    warnings.extend(str(item) for item in result.get("warnings", []))


def validate_research_pack_gate(
    run_dir: Path,
    source_registry: Optional[Path],
    errors: list[str],
    warnings: list[str],
) -> None:
    memo_path = run_dir / "industry_research_pack.md"
    artifact_path = run_dir / "artifacts" / "research_pack_validation.json"

    if not memo_path.exists():
        errors.append(f"missing required artifact: {memo_path}")
    require_valid_artifact(artifact_path, errors, warnings)

    if memo_path.exists():
        current_result = validate_research_pack(memo_path, run_dir=run_dir, source_registry_path=resolve_repo_path(source_registry))
        if current_result.get("is_valid") is False:
            errors.append("current research pack validation failed")
        warnings.extend(str(item) for item in current_result.get("errors", []))


def validate_renderer_spec_gate(run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    renderer_spec_path = run_dir / "renderer_spec.json"
    template_registry_path = run_dir / "template_registry.json"
    deck_blueprint_path = run_dir / "deck_blueprint.json"
    page_contract_path = run_dir / "page_evidence_contract.json"
    artifact_path = run_dir / "artifacts" / "renderer_spec_validation.json"

    if not renderer_spec_path.exists():
        errors.append(f"missing required artifact: {renderer_spec_path}")
    require_valid_artifact(artifact_path, errors, warnings)

    if renderer_spec_path.exists() and template_registry_path.exists() and deck_blueprint_path.exists() and page_contract_path.exists():
        try:
            deck_blueprint = load_json_file(deck_blueprint_path)
            current_errors, current_warnings = validate_renderer_spec(
                load_json_file(renderer_spec_path),
                load_json_file(template_registry_path),
                normalize_deck_blueprint_for_page_plan(deck_blueprint),
                load_json_file(page_contract_path),
            )
        except Exception as exc:
            errors.append(f"current renderer spec validation failed: {exc}")
            return
        if current_errors:
            errors.append("current renderer spec validation failed")
            errors.extend(current_errors)
        warnings.extend(current_warnings)


def validate_issue_analysis_gate(run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    issue_analysis_path = run_dir / "industry_issue_analysis.json"
    template_registry_path = run_dir / "template_registry.json"
    deck_blueprint_path = run_dir / "deck_blueprint.json"
    page_contract_path = run_dir / "page_evidence_contract.json"
    memo_path = run_dir / "industry_research_pack.md"

    missing = [
        str(path)
        for path in (issue_analysis_path, template_registry_path, deck_blueprint_path, page_contract_path)
        if not path.exists()
    ]
    if missing:
        errors.extend(f"missing required issue analysis artifact: {path}" for path in missing)
        return

    issue_analysis = load_json_if_exists(issue_analysis_path, errors)
    template_registry = load_json_if_exists(template_registry_path, errors)
    deck_blueprint = load_json_if_exists(deck_blueprint_path, errors)
    page_contract = load_json_if_exists(page_contract_path, errors)
    if not issue_analysis or not template_registry or not deck_blueprint or not page_contract:
        return

    issue_result_errors, issue_result_warnings = validate_issue_analysis(
        issue_analysis,
        memo_path if memo_path.exists() else None,
    )
    issue_result = {
        "is_valid": not issue_result_errors,
        "errors": issue_result_errors,
        "warnings": issue_result_warnings,
    }
    if issue_result.get("is_valid") is False:
        errors.append("current issue analysis validation failed")
        errors.extend(str(item) for item in issue_result.get("errors", []))
    warnings.extend(str(item) for item in issue_result.get("warnings", []))

    template_registry_errors, template_registry_warnings = validate_template_registry(template_registry)
    if template_registry_errors:
        errors.append("current template registry validation failed")
        errors.extend(str(item) for item in template_registry_errors)
    warnings.extend(str(item) for item in template_registry_warnings)

    deck_errors, deck_warnings = validate_deck_blueprint(issue_analysis=issue_analysis, template_registry=template_registry, deck_blueprint=deck_blueprint)
    if deck_errors:
        errors.append("current deck blueprint validation failed")
        errors.extend(str(item) for item in deck_errors)
    warnings.extend(str(item) for item in deck_warnings)

    page_contract_errors, page_contract_warnings = validate_page_evidence_contract(
        issue_analysis,
        normalize_deck_blueprint_for_page_plan(deck_blueprint),
        page_contract,
    )
    page_contract_result = {
        "is_valid": not page_contract_errors,
        "errors": page_contract_errors,
        "warnings": page_contract_warnings,
    }
    if page_contract_result.get("is_valid") is False:
        errors.append("current page evidence contract validation failed")
        errors.extend(str(item) for item in page_contract_result.get("errors", []))
    warnings.extend(str(item) for item in page_contract_result.get("warnings", []))


def validate_content_gate(run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    artifact_path = run_dir / "artifacts" / "content_quality_validation.json"
    renderer_spec_path = run_dir / "renderer_spec.json"
    memo_path = run_dir / "industry_research_pack.md"

    require_no_blocking_artifact(artifact_path, errors, warnings)

    if renderer_spec_path.exists():
        current_result = validate_content_quality(
            renderer_spec_path,
            memo_path if memo_path.exists() else None,
            REPO_ROOT / "templates" / "content_quality_rules.json",
            text_fit_rules_path=REPO_ROOT / "templates" / "text_fit_rules.json",
            layout_budget_path=REPO_ROOT / "templates" / "layout_budget.json",
        )
        if current_result.get("is_valid") is False:
            errors.append("current content quality validation failed")
        warnings.extend(str(item) for item in current_result.get("errors", []))
        warnings.extend(str(item) for item in current_result.get("warnings", []))
        warnings.extend(str(item) for item in current_result.get("blocking_issues", []))
    else:
        errors.append(f"missing required artifact: {renderer_spec_path}")


def validate_chart_metric_binding_gate(run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    artifact_path = run_dir / "artifacts" / "chart_metric_binding_validation.json"
    renderer_spec_path = run_dir / "renderer_spec.json"
    memo_path = run_dir / "industry_research_pack.md"
    page_contract_path = run_dir / "page_evidence_contract.json"

    require_no_blocking_artifact(artifact_path, errors, warnings)

    if not renderer_spec_path.exists():
        errors.append(f"missing required artifact: {renderer_spec_path}")
        return
    if not memo_path.exists():
        errors.append(f"missing required artifact: {memo_path}")
        return

    try:
        renderer_spec = load_json_file(renderer_spec_path)
        memo_text = memo_path.read_text(encoding="utf-8")
        page_contract = load_json_file(page_contract_path) if page_contract_path.exists() else None
        current_result = validate_chart_metric_binding(renderer_spec, memo_text, page_contract)
    except Exception as exc:
        errors.append(f"current chart metric binding validation failed: {exc}")
        return
    if current_result.get("is_valid") is False:
        errors.append("current chart metric binding validation failed")
    warnings.extend(str(item) for item in current_result.get("errors", []))
    warnings.extend(str(item) for item in current_result.get("warnings", []))
    for item in current_result.get("root_causes", []):
        if isinstance(item, dict):
            warnings.append(
                " | ".join(
                    part
                    for part in (
                        str(item.get("code") or ""),
                        str(item.get("message") or ""),
                        str(item.get("repair_hint") or ""),
                    )
                    if part
                )
            )


def validate_stage(stage: str, run_dir: Path, source_registry: Optional[Path]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if stage in {"pre_research_pack", "pre_renderer", "pre_ppt"}:
        validate_industry_scope_pack_gate(run_dir, errors, warnings)
        check_formal_search_plan_presence(run_dir, errors, warnings)
        validate_formal_research_execution_gate(run_dir, errors, warnings)
        validate_source_reviews_gate(run_dir, errors, warnings, require_memo_binding=stage in {"pre_renderer", "pre_ppt"})

    if stage in {"pre_renderer", "pre_ppt"}:
        validate_research_pack_gate(run_dir, source_registry, errors, warnings)
        validate_issue_analysis_gate(run_dir, errors, warnings)

    if stage == "pre_ppt":
        validate_renderer_spec_gate(run_dir, errors, warnings)
        validate_chart_metric_binding_gate(run_dir, errors, warnings)
        validate_content_gate(run_dir, errors, warnings)

    return {
        "is_valid": not errors,
        "stage": stage,
        "run_dir": str(run_dir),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate deterministic workflow stage gates.")
    parser.add_argument("--stage", required=True, choices=["pre_research_pack", "pre_renderer", "pre_ppt"])
    parser.add_argument("--run-dir", required=True, help="Run/attempt directory to validate.")
    parser.add_argument("--source-registry", default=str(REPO_ROOT / "templates" / "source_registry.json"))
    parser.add_argument("--output", help="Optional JSON report path.")
    args = parser.parse_args()

    result = validate_stage(args.stage, Path(args.run_dir), Path(args.source_registry) if args.source_registry else None)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            f.write("\n")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    if not result["is_valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
