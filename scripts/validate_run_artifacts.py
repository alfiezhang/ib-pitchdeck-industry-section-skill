#!/usr/bin/env python3
"""Validate that a run directory contains the required research and PPT artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from json_utils import load_json_file


REQUIRED_CORE_FILES = [
    "industry_input_memo.md",
    "industry_storyboard.json",
    "industry_section_ppt_copy.json",
    "replacement_dict.json",
    "industry_section_filled_clean.pptx",
    "filled_ppt_validation.json",
    "artifacts/storyboard_validation.json",
    "artifacts/content_quality_validation.json",
]

REQUIRED_RESEARCH_FILES = [
    "artifacts/research_plan.json",
    "artifacts/research_plan_validation.json",
    "artifacts/search_log.md",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_file_exists(run_dir: Path, relative_path: str, errors: list[str]) -> None:
    if not (run_dir / relative_path).exists():
        errors.append(f"missing required artifact: {relative_path}")


def validation_is_true(path: Path) -> tuple[bool, str]:
    data = load_json_file(path)
    if isinstance(data, dict):
        if isinstance(data.get("is_valid"), bool):
            return data["is_valid"], "is_valid"
        summary = data.get("summary")
        if isinstance(summary, dict) and isinstance(summary.get("is_valid"), bool):
            return summary["is_valid"], "summary.is_valid"
    return False, "missing is_valid"


def memo_claimed_artifacts(memo_text: str) -> list[str]:
    claimed = []
    for line in memo_text.splitlines():
        match = re.match(r"Research Plan (?:Artifact|Validation):\s*(.+?)\s*$", line)
        if match:
            value = match.group(1).strip()
            if value and value.lower() not in {"none", "n/a", "not applicable"}:
                claimed.append(value)
    return claimed


def validate_search_log(path: Path) -> list[str]:
    warnings = []
    text = read_text(path)
    if "## Search Attempts" not in text:
        warnings.append("search_log.md missing '## Search Attempts' section")
    if "## Coverage Checklist" not in text:
        warnings.append("search_log.md missing '## Coverage Checklist' section")
    if "broad_discovery" not in text:
        warnings.append("search_log.md has no broad_discovery stage")
    if "targeted_validation" not in text and "latest_check" not in text:
        warnings.append("search_log.md has no targeted_validation/latest_check stage")
    attempt_count = len(re.findall(r"^### Search\s+\d+", text, flags=re.MULTILINE))
    if attempt_count < 3:
        warnings.append(f"search_log.md has only {attempt_count} search attempt(s); expected at least 3")
    return warnings


def validate(run_dir: Path, require_research: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if not run_dir.exists():
        return {
            "is_valid": False,
            "error_count": 1,
            "warning_count": 0,
            "errors": [f"run directory not found: {run_dir}"],
            "warnings": [],
        }

    for relative in REQUIRED_CORE_FILES:
        check_file_exists(run_dir, relative, errors)

    if require_research:
        for relative in REQUIRED_RESEARCH_FILES:
            check_file_exists(run_dir, relative, errors)

    memo_path = run_dir / "industry_input_memo.md"
    if memo_path.exists():
        for claimed in memo_claimed_artifacts(read_text(memo_path)):
            if not (run_dir / claimed).exists():
                errors.append(f"memo claims artifact exists but file is missing: {claimed}")

    for relative in [
        "artifacts/storyboard_validation.json",
        "artifacts/research_plan_validation.json",
        "filled_ppt_validation.json",
    ]:
        path = run_dir / relative
        if not path.exists():
            continue
        try:
            ok, field = validation_is_true(path)
        except Exception as exc:
            errors.append(f"cannot read validation artifact {relative}: {exc}")
            continue
        if not ok:
            errors.append(f"validation artifact is not passing: {relative} ({field}=false)")

    content_quality_path = run_dir / "artifacts/content_quality_validation.json"
    if content_quality_path.exists():
        try:
            content_quality = load_json_file(content_quality_path)
        except Exception as exc:
            errors.append(f"cannot read content quality artifact: {exc}")
        else:
            if isinstance(content_quality, dict) and content_quality.get("is_valid") is False:
                errors.append("content_quality_validation.json is_valid=false")

    search_log = run_dir / "artifacts/search_log.md"
    if search_log.exists():
        warnings.extend(validate_search_log(search_log))

    return {
        "is_valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "require_research": require_research,
        "run_dir": str(run_dir),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a generated run directory's required artifacts.")
    parser.add_argument("--run-dir", required=True, help="Run directory, e.g. runs/attempt_...")
    parser.add_argument("--output", help="Optional JSON report path")
    parser.add_argument(
        "--no-research-required",
        action="store_true",
        help="Do not require research_plan/search_log artifacts. Use only for PPT-only debug runs.",
    )
    parser.add_argument("--warnings-as-errors", action="store_true")
    args = parser.parse_args()

    result = validate(Path(args.run_dir), require_research=not args.no_research_required)
    if args.warnings_as_errors and result["warnings"]:
        result["is_valid"] = False

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["is_valid"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
