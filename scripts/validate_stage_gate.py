#!/usr/bin/env python3
"""Deterministic stage gates for the industry-section workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Optional

from json_utils import load_json_file
from validate_content_quality import validate as validate_content_quality
from validate_memo import validate as validate_memo
from validate_research_plan import validate as validate_research_plan
from validate_run_artifacts import validate_search_log
from validate_storyboard import validate as validate_storyboard


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
    for key in ("errors", "blocking_warnings"):
        values = data.get(key, [])
        if isinstance(values, list):
            warnings.extend(str(item) for item in values)
    return data


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


def validate_research_plan_gate(
    run_dir: Path,
    source_registry: Optional[Path],
    errors: list[str],
    warnings: list[str],
) -> None:
    artifacts = run_dir / "artifacts"
    plan_path = artifacts / "research_plan.json"
    validation_path = artifacts / "research_plan_validation.json"
    search_log_path = artifacts / "search_log.md"

    plan_data = load_json_if_exists(plan_path, errors)
    require_valid_artifact(validation_path, errors, warnings)

    if not search_log_path.exists():
        errors.append(f"missing required artifact: {search_log_path}")
    else:
        search_errors, search_warnings = validate_search_log(search_log_path)
        errors.extend(search_errors)
        warnings.extend(search_warnings)

    registry_data = load_source_registry(source_registry, errors)
    if isinstance(plan_data, dict):
        current_result = validate_research_plan(plan_data, registry_data, stage="formal")
        if current_result.get("is_valid") is False:
            errors.append("current formal research plan validation failed")
        warnings.extend(str(item) for item in current_result.get("errors", []))
        warnings.extend(str(item) for item in current_result.get("blocking_warnings", []))


def validate_memo_gate(
    run_dir: Path,
    source_registry: Optional[Path],
    errors: list[str],
    warnings: list[str],
) -> None:
    memo_path = run_dir / "industry_input_memo.md"
    artifact_path = run_dir / "artifacts" / "memo_validation.json"

    if not memo_path.exists():
        errors.append(f"missing required artifact: {memo_path}")
    require_valid_artifact(artifact_path, errors, warnings)

    if memo_path.exists():
        current_result = validate_memo(memo_path, run_dir=run_dir, source_registry_path=resolve_repo_path(source_registry))
        if current_result.get("is_valid") is False:
            errors.append("current memo validation failed")
        warnings.extend(str(item) for item in current_result.get("errors", []))


def validate_storyboard_gate(run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    storyboard_path = run_dir / "industry_storyboard.json"
    artifact_path = run_dir / "artifacts" / "storyboard_validation.json"

    if not storyboard_path.exists():
        errors.append(f"missing required artifact: {storyboard_path}")
    require_valid_artifact(artifact_path, errors, warnings)

    if storyboard_path.exists():
        current_result = validate_storyboard(
            storyboard_path,
            schema_path=REPO_ROOT / "templates" / "storyboard_schema.json",
            text_fit_rules_path=REPO_ROOT / "templates" / "text_fit_rules.json",
            layout_budget_path=REPO_ROOT / "templates" / "layout_budget.json",
        )
        if current_result.get("is_valid") is False:
            errors.append("current storyboard validation failed")
        warnings.extend(str(item) for item in current_result.get("errors", []))


def validate_content_gate(run_dir: Path, errors: list[str], warnings: list[str]) -> None:
    artifact_path = run_dir / "artifacts" / "content_quality_validation.json"
    storyboard_path = run_dir / "industry_storyboard.json"
    memo_path = run_dir / "industry_input_memo.md"

    require_valid_artifact(artifact_path, errors, warnings)

    if storyboard_path.exists():
        current_result = validate_content_quality(
            storyboard_path,
            memo_path if memo_path.exists() else None,
            REPO_ROOT / "templates" / "content_quality_rules.json",
        )
        if current_result.get("is_valid") is False:
            errors.append("current content quality validation failed")
        warnings.extend(str(item) for item in current_result.get("errors", []))
        warnings.extend(str(item) for item in current_result.get("blocking_warnings", []))
    else:
        errors.append(f"missing required artifact: {storyboard_path}")


def validate_stage(stage: str, run_dir: Path, source_registry: Optional[Path]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if stage in {"pre_memo", "pre_storyboard", "pre_ppt"}:
        validate_research_plan_gate(run_dir, source_registry, errors, warnings)

    if stage in {"pre_storyboard", "pre_ppt"}:
        validate_memo_gate(run_dir, source_registry, errors, warnings)

    if stage == "pre_ppt":
        validate_storyboard_gate(run_dir, errors, warnings)
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
    parser.add_argument("--stage", required=True, choices=["pre_memo", "pre_storyboard", "pre_ppt"])
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
