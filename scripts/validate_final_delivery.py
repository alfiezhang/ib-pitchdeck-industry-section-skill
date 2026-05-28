#!/usr/bin/env python3
"""Final deterministic gate for a generated industry-section run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from check_json_files import check_file
from json_utils import load_json_file
from validate_content_quality import validate as validate_content_quality
from validate_filled_ppt import build_report
from validate_input_card import validate as validate_input_card_data
from validate_memo import validate as validate_memo_data
from validate_research_plan import validate as validate_research_plan_data
from validate_run_artifacts import validate as validate_run_artifacts


REPO_ROOT = Path(__file__).resolve().parents[1]


def json_files_under(run_dir: Path) -> list[Path]:
    return sorted(path for path in run_dir.rglob("*.json") if "__pycache__" not in path.parts)


def validate_content_quality_artifact(path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not path.exists():
        errors.append("missing content quality validation artifact")
        return errors, warnings
    data = load_json_file(path)
    if data.get("is_valid") is False:
        errors.append("content_quality_validation.json is_valid=false")
    return errors, warnings


def is_within_run(path_text: str, run_dir: Path) -> bool:
    if not path_text:
        return True
    try:
        candidate = Path(path_text).expanduser()
        if not candidate.is_absolute():
            return True
        candidate.resolve().relative_to(run_dir.resolve())
        return True
    except Exception:
        return False


def validate_artifact_provenance(run_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    checks = {
        "artifacts/content_quality_validation.json": ["storyboard", "memo"],
        "artifacts/storyboard_validation.json": ["storyboard"],
        "artifacts/memo_validation.json": ["memo", "run_dir"],
        "artifacts/research_plan_validation.json": ["plan"],
        "filled_ppt_validation.json": ["summary.filled_ppt", "summary.clean_ppt", "summary.control_file", "summary.replacement_dict"],
    }
    source_files = [
        run_dir / "industry_input_memo.md",
        run_dir / "industry_storyboard.json",
        run_dir / "industry_section_ppt_copy.json",
        run_dir / "replacement_dict.json",
    ]

    for rel, fields in checks.items():
        artifact_path = run_dir / rel
        if not artifact_path.exists():
            continue
        try:
            data = load_json_file(artifact_path)
        except Exception as exc:
            errors.append(f"cannot check artifact provenance for {rel}: {exc}")
            continue
        for field in fields:
            cursor: Any = data
            for part in field.split("."):
                cursor = cursor.get(part, {}) if isinstance(cursor, dict) else {}
            if isinstance(cursor, str) and not is_within_run(cursor, run_dir):
                errors.append(f"{rel} field '{field}' points outside current run: {cursor}")
        try:
            artifact_mtime = artifact_path.stat().st_mtime
        except OSError:
            continue
        newer_sources = [path.name for path in source_files if path.exists() and path.stat().st_mtime > artifact_mtime + 1.0]
        if newer_sources:
            errors.append(f"{rel} is older than source file(s): {', '.join(newer_sources)}; rerun validation")
    return errors, warnings


def validate_research_plan_artifact(run_dir: Path, source_registry: Optional[Path]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    plan_path = run_dir / "artifacts/research_plan.json"
    artifact_path = run_dir / "artifacts/research_plan_validation.json"
    if not plan_path.exists():
        errors.append("missing research_plan.json")
        return errors, warnings

    registry_data = None
    if source_registry and not source_registry.exists() and not source_registry.is_absolute():
        source_registry = REPO_ROOT / source_registry
    if source_registry and source_registry.exists():
        try:
            registry_data = load_json_file(source_registry)
        except Exception as exc:
            errors.append(f"cannot load source registry for research plan validation: {exc}")

    try:
        plan_data = load_json_file(plan_path)
    except Exception as exc:
        errors.append(f"cannot load research_plan.json: {exc}")
        return errors, warnings

    current_result = validate_research_plan_data(plan_data, registry_data, stage="formal")
    if current_result.get("is_valid") is False:
        errors.append("formal research plan validation failed")
        warnings.extend(str(item) for item in current_result.get("blocking_warnings", []))
        warnings.extend(str(item) for item in current_result.get("errors", []))

    if artifact_path.exists():
        try:
            artifact = load_json_file(artifact_path)
        except Exception as exc:
            errors.append(f"cannot read research_plan_validation.json: {exc}")
        else:
            if artifact.get("warning_count", 0):
                warnings.append(
                    f"research_plan_validation.json contains {artifact.get('warning_count')} warning(s); "
                    "resolve them or regenerate the artifact with the formal plan"
                )
            metrics = artifact.get("metrics", {})
            if isinstance(metrics, dict):
                if int(metrics.get("targeted_validation_query_count") or 0) == 0:
                    errors.append("research_plan_validation.json records zero targeted validation queries")
                if int(metrics.get("resolved_high_priority_domain_count") or 0) == 0:
                    errors.append("research_plan_validation.json records zero selected high-priority domains")
    else:
        errors.append("missing research_plan_validation.json")

    return errors, warnings


def validate_current_content_quality(run_dir: Path, rules_path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    storyboard_path = run_dir / "industry_storyboard.json"
    memo_path = run_dir / "industry_input_memo.md"
    if not storyboard_path.exists():
        return ["cannot recompute content quality: missing industry_storyboard.json"], warnings

    result = validate_content_quality(
        storyboard_path,
        memo_path if memo_path.exists() else None,
        rules_path,
    )
    if result.get("is_valid") is False:
        errors.append("current content quality validation failed")
        warnings.extend(str(item) for item in result.get("errors", []))

    blocking_warnings = result.get("blocking_warnings", [])
    if blocking_warnings:
        errors.append(
            "current content quality validation contains blocking source/layout warnings; resolve before delivery"
        )
        warnings.extend(str(item) for item in blocking_warnings)
    return errors, warnings


def validate_postprocess_artifact(run_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    storyboard_path = run_dir / "industry_storyboard.json"
    log_path = run_dir / "artifacts/postprocess_ppt_visuals.log.json"
    if not storyboard_path.exists():
        return errors, warnings

    try:
        storyboard = load_json_file(storyboard_path)
    except Exception as exc:
        return [f"cannot validate postprocess outputs: cannot read storyboard: {exc}"], warnings

    slides = storyboard.get("slides", [])
    if not isinstance(slides, list):
        return errors, warnings

    selected_by_slide = {
        int(slide.get("slide_no")): slide.get("selected_page_type")
        for slide in slides
        if isinstance(slide, dict) and isinstance(slide.get("slide_no"), int)
    }
    required_real_tables = []
    if selected_by_slide.get(2) == "chart_plus_mini_table_page":
        required_real_tables.append((2, "Slide 2 mini table"))
    if selected_by_slide.get(6) == "compare_table_page":
        required_real_tables.append((6, "Slide 6 compare table"))
    if not required_real_tables:
        return errors, warnings

    if not log_path.exists():
        errors.append("missing postprocess_ppt_visuals.log.json; cannot verify required real table rendering")
        return errors, warnings

    try:
        log_data = load_json_file(log_path)
    except Exception as exc:
        errors.append(f"cannot read postprocess_ppt_visuals.log.json: {exc}")
        return errors, warnings

    render_entries = log_data.get("chart_rendering", [])
    if not isinstance(render_entries, list):
        errors.append("postprocess_ppt_visuals.log.json missing chart_rendering list")
        return errors, warnings

    entries_by_slide = {
        entry.get("slide_no"): entry
        for entry in render_entries
        if isinstance(entry, dict)
    }
    for slide_no, label in required_real_tables:
        entry = entries_by_slide.get(slide_no)
        if not isinstance(entry, dict):
            errors.append(f"{label} was selected but has no postprocess rendering log entry")
            continue
        if slide_no == 2:
            table_result = entry.get("table", {})
            if not isinstance(table_result, dict) or table_result.get("rendered") is not True:
                errors.append(f"{label} did not render as a real PPT table object")
        elif slide_no == 6:
            if entry.get("rendered") is not True:
                errors.append(f"{label} did not render as a real PPT table object")
    return errors, warnings


def validate_memo_artifact(run_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    memo_path = run_dir / "industry_input_memo.md"
    if not memo_path.exists():
        return ["missing industry_input_memo.md"], warnings

    result = validate_memo_data(memo_path, run_dir)
    if result.get("is_valid") is False:
        errors.append("current memo validation failed")
        errors.extend(str(item) for item in result.get("errors", []))
    warnings.extend(str(item) for item in result.get("warnings", []))

    artifact_path = run_dir / "artifacts/memo_validation.json"
    if artifact_path.exists():
        try:
            artifact = load_json_file(artifact_path)
        except Exception as exc:
            errors.append(f"cannot read memo_validation.json: {exc}")
        else:
            if artifact.get("is_valid") is False:
                errors.append("memo_validation.json is_valid=false")
    else:
        errors.append("missing memo_validation.json")
    return errors, warnings


def validate(run_dir: Path, source_registry: Optional[Path] = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    artifact_result = validate_run_artifacts(run_dir, require_research=True)
    errors.extend(artifact_result["errors"])
    warnings.extend(artifact_result["warnings"])

    provenance_errors, provenance_warnings = validate_artifact_provenance(run_dir)
    errors.extend(provenance_errors)
    warnings.extend(provenance_warnings)

    for path in json_files_under(run_dir):
        result = check_file(path)
        if not result["is_valid"]:
            errors.append(f"invalid JSON: {path}: {result['error']}")

    input_card = run_dir / "input_card.json"
    if input_card.exists():
        try:
            input_result = validate_input_card_data(load_json_file(input_card))
        except Exception as exc:
            errors.append(f"cannot validate input_card.json: {exc}")
        else:
            errors.extend(input_result["errors"])
            warnings.extend(input_result["warnings"])

    content_errors, content_warnings = validate_content_quality_artifact(
        run_dir / "artifacts/content_quality_validation.json"
    )
    errors.extend(content_errors)
    warnings.extend(content_warnings)

    research_errors, research_warnings = validate_research_plan_artifact(run_dir, source_registry)
    errors.extend(research_errors)
    warnings.extend(research_warnings)

    memo_errors, memo_warnings = validate_memo_artifact(run_dir)
    errors.extend(memo_errors)
    warnings.extend(memo_warnings)

    current_content_errors, current_content_warnings = validate_current_content_quality(
        run_dir,
        REPO_ROOT / "templates/content_quality_rules.json",
    )
    errors.extend(current_content_errors)
    warnings.extend(current_content_warnings)

    postprocess_errors, postprocess_warnings = validate_postprocess_artifact(run_dir)
    errors.extend(postprocess_errors)
    warnings.extend(postprocess_warnings)

    ppt_paths = {
        "filled_ppt_path": run_dir / "industry_section_filled.pptx",
        "clean_ppt_path": run_dir / "industry_section_filled_clean.pptx",
        "control_file_path": run_dir / "industry_storyboard.json",
        "replacement_dict_path": run_dir / "replacement_dict.json",
        "ppt_mapping_path": REPO_ROOT / "templates/ppt_mapping.json",
    }
    if all(path.exists() for path in ppt_paths.values()):
        try:
            ppt_report = build_report(**ppt_paths)
        except Exception as exc:
            errors.append(f"cannot validate final PPT: {exc}")
        else:
            if not ppt_report["summary"]["is_valid"]:
                errors.append("final PPT validation failed")
                for issue in ppt_report.get("visible_scaffold_label_issues", []):
                    warnings.append(f"visible scaffold label: slide {issue['slide_no']} {issue['text']}")
                for issue in ppt_report.get("page_number_check", {}).get("issues", []):
                    warnings.append(
                        f"page number issue: slide {issue['slide_no']} expected {issue['expected']} found {issue['found']}"
                    )
    else:
        missing = [name for name, path in ppt_paths.items() if not path.exists()]
        errors.append("missing final PPT validation input(s): " + ", ".join(missing))

    return {
        "is_valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "run_dir": str(run_dir),
        "source_registry": str(source_registry) if source_registry else "",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the final delivery gate for an industry section output.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--source-registry", default="templates/source_registry.json")
    parser.add_argument("--output", help="Optional JSON report path")
    args = parser.parse_args()

    result = validate(Path(args.run_dir), Path(args.source_registry) if args.source_registry else None)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["is_valid"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
