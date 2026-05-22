#!/usr/bin/env python3
"""Final deterministic gate for a generated industry-section run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from check_json_files import check_file
from json_utils import load_json_file
from validate_content_quality import validate as validate_content_quality
from validate_filled_ppt import build_report
from validate_input_card import validate as validate_input_card_data
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

    source_warnings = result.get("source_warnings", [])
    if source_warnings:
        errors.append(
            "current content quality validation contains source_warnings; weak sources must be resolved before delivery"
        )
        warnings.extend(str(item) for item in source_warnings)
    return errors, warnings


def validate(run_dir: Path, source_registry: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    artifact_result = validate_run_artifacts(run_dir, require_research=True)
    errors.extend(artifact_result["errors"])
    warnings.extend(artifact_result["warnings"])

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

    current_content_errors, current_content_warnings = validate_current_content_quality(
        run_dir,
        REPO_ROOT / "templates/content_quality_rules.json",
    )
    errors.extend(current_content_errors)
    warnings.extend(current_content_warnings)

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
