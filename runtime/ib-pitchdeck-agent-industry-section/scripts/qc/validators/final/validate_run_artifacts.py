#!/usr/bin/env python3
"""Validate that a run directory contains the required research and PPT artifacts."""

from __future__ import annotations

# Runtime scripts can be run directly. Shared helpers remain in runtime
# `scripts/`; production tools live under role scripts; validators live under QC.
import sys as _ib_sys
from pathlib import Path as _IbPath
_IB_ROLE_SCRIPT_DIR = _IbPath(__file__).resolve().parent
_IB_RUNTIME_ROOT = next(
    _p for _p in _IbPath(__file__).resolve().parents
    if (_p / 'configs').is_dir() and (_p / 'scripts').is_dir()
)
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts" / "_lib"
_IB_ROLE_SCRIPT_DIRS = sorted(_p for _p in (_IB_RUNTIME_ROOT / 'scripts').iterdir() if _p.is_dir())
_IB_QC_VALIDATOR_DIRS = sorted((_IB_RUNTIME_ROOT / 'scripts' / 'qc' / 'validators').glob('*'))
_IB_IMPORT_PATHS = [str(_IB_ROLE_SCRIPT_DIR)]
for _ib_dir in [*_IB_ROLE_SCRIPT_DIRS, *_IB_QC_VALIDATOR_DIRS]:
    _ib_text = str(_ib_dir)
    if _ib_text not in _IB_IMPORT_PATHS:
        _IB_IMPORT_PATHS.append(_ib_text)
_IB_IMPORT_PATHS.append(str(_IB_SHARED_SCRIPT_DIR))
for _ib_path in list(_IB_IMPORT_PATHS):
    if _ib_path in _ib_sys.path:
        _ib_sys.path.remove(_ib_path)
for _ib_path in reversed(_IB_IMPORT_PATHS):
    _ib_sys.path.insert(0, _ib_path)

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from json_utils import load_json_file
from validate_formal_research_execution import parse_search_attempts


REQUIRED_CORE_FILES = [
    "input_card.json",
    "artifacts/research_evidence_db.json",
    "industry_research_pack.md",
    "deck_blueprint.json",
    "renderer_spec.json",
    "replacement_dict.json",
    "industry_section_filled_clean.pptx",
    "filled_ppt_validation.json",
    "artifacts/input_card_validation.json",
    "artifacts/renderer_spec_validation.json",
    "artifacts/chart_metric_binding_validation.json",
    "artifacts/content_quality_validation.json",
    "artifacts/research_evidence_db_validation.json",
    "artifacts/replacement_dict_validation.json",
    "artifacts/stage_gate_pre_ppt_validation.json",
]

REQUIRED_RESEARCH_FILES = [
    "artifacts/industry_scope_pack.json",
    "artifacts/industry_scope_pack_validation.json",
    "artifacts/formal_search_plan.json",
    "artifacts/formal_search_plan_validation.json",
    "artifacts/formal_research_execution_report.json",
    "artifacts/formal_research_execution_validation.json",
    "artifacts/stage_gate_pre_research_pack_validation.json",
    "artifacts/research_evidence_db.json",
    "artifacts/research_evidence_db_validation.json",
    "artifacts/research_pack_validation.json",
    "artifacts/search_log.md",
    "artifacts/source_archive/source_archive_index.json",
    "artifacts/source_archive_validation.json",
    "industry_issue_analysis.json",
    "template_registry.json",
    "page_evidence_contract.json",
    "artifacts/issue_analysis_validation.json",
    "artifacts/template_registry_validation.json",
    "artifacts/deck_blueprint_validation.json",
    "artifacts/page_evidence_contract_validation.json",
]

FULL_URL_RE = re.compile(r"https?://[^\s\]|)）>]+", flags=re.IGNORECASE)
RAW_CONTEXT_RE = re.compile(
    r"raw excerpt|原文|excerpt|opened|reviewed|打开|已读|locator|定位|page|section|paragraph|table|页|节|段|表",
    flags=re.IGNORECASE,
)
TEMPLATE_PLACEHOLDER_RE = re.compile(r"^\s*(?:#.*)?$", flags=re.IGNORECASE)
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
        match = re.match(r"search plan (?:Artifact|Validation):\s*(.+?)\s*$", line)
        if match:
            value = match.group(1).strip()
            value = re.split(r"\s+\(", value, maxsplit=1)[0].strip()
            if value and value.lower() not in {"none", "n/a", "not applicable"}:
                claimed.append(value)
    return claimed


def validate_search_log(path: Path) -> tuple[list[str], list[str]]:
    errors = []
    warnings = []
    text = read_text(path)
    filled_attempts = []
    try:
        attempts = parse_search_attempts(path)
    except Exception as exc:
        return [f"cannot parse search_log.md: {exc}"], warnings
    for attempt_id in sorted(attempts):
        lines_by_field = attempts[attempt_id]
        fields: dict[str, str] = {}
        for field in (
            "Query",
            "Provider",
            "Search Stage",
            "Result Count",
            "Selected Sources",
            "Dimension",
            "Opened / Reviewed",
            "Source Locator / Raw Excerpt",
        ):
            value = lines_by_field.get(field.lower(), "")
            fields[field] = "" if not value or value.startswith("#") else value
        if fields.get("Query") and fields.get("Provider") and fields.get("Search Stage"):
            filled_attempts.append(fields)

    filled_attempt_count = len(filled_attempts)
    if not re.search(r"^##\s+Search Attempts\s*$", text, flags=re.MULTILINE):
        errors.append("search_log.md missing '## Search Attempts' section")

    stages = " ".join(attempt.get("Search Stage", "") for attempt in filled_attempts).lower()
    if "broad_discovery" not in stages and "broad discovery" not in stages:
        errors.append("search_log.md has no completed broad_discovery search attempt")
    has_explicit_validation = any(token in stages for token in ("formal_research_execution", "latest_check", "formal research execution", "latest"))
    validation_quality_attempts = []
    for attempt in filled_attempts:
        selected_sources = attempt.get("Selected Sources", "")
        opened = attempt.get("Opened / Reviewed", "").lower()
        locator_excerpt = attempt.get("Source Locator / Raw Excerpt", "")
        dimension = attempt.get("Dimension", "")
        if (
            FULL_URL_RE.search(selected_sources)
            and any(token in opened for token in ("yes", "y", "true", "opened", "reviewed", "是", "已"))
            and len(locator_excerpt.strip()) >= 20
            and dimension.strip()
        ):
            validation_quality_attempts.append(attempt)
    if not has_explicit_validation:
        if len(validation_quality_attempts) >= 3:
            warnings.append(
                "search_log.md has validation-quality searches but none are labelled formal_research_execution/latest_check; "
                "future runs should label post-discovery verification searches explicitly"
            )
        else:
            errors.append("search_log.md has no completed formal_research_execution/latest_check search attempt")
    if filled_attempt_count < 3:
        errors.append(f"search_log.md has only {filled_attempt_count} completed search attempt(s); expected at least 3")

    if filled_attempt_count and len(FULL_URL_RE.findall(text)) < filled_attempt_count:
        errors.append(
            "search_log.md does not contain enough full URLs for completed search attempts; "
            "record exact source URLs, not only source names or domains"
        )
    if filled_attempt_count and len(RAW_CONTEXT_RE.findall(text)) < filled_attempt_count:
        errors.append(
            "search_log.md lacks opened/reviewed/source-locator/raw-excerpt context for completed searches; "
            "search-result snippets alone are not formal research evidence"
        )

    for idx, attempt in enumerate(filled_attempts, start=1):
        if not attempt.get("Result Count"):
            errors.append(f"search_log.md completed search {idx} is missing Result Count")
        if not attempt.get("Selected Sources"):
            errors.append(f"search_log.md completed search {idx} is missing Selected Sources")
        selected_sources = attempt.get("Selected Sources", "")
        if selected_sources and not FULL_URL_RE.search(selected_sources):
            errors.append(
                f"search_log.md completed search {idx} has Selected Sources without a full URL; "
                "use exact article/report/PDF URLs"
            )
        if selected_sources and TEMPLATE_PLACEHOLDER_RE.match(selected_sources):
            errors.append(f"search_log.md completed search {idx} appears to have placeholder Selected Sources")
        opened = attempt.get("Opened / Reviewed", "").lower()
        if not any(token in opened for token in ("yes", "y", "true", "opened", "reviewed", "是", "已")):
            errors.append(
                f"search_log.md completed search {idx} is missing positive Opened / Reviewed confirmation"
            )
        locator_excerpt = attempt.get("Source Locator / Raw Excerpt", "")
        if not locator_excerpt or TEMPLATE_PLACEHOLDER_RE.match(locator_excerpt):
            errors.append(
                f"search_log.md completed search {idx} is missing Source Locator / Raw Excerpt"
            )
        elif len(locator_excerpt.strip()) < 20:
            errors.append(
                f"search_log.md completed search {idx} Source Locator / Raw Excerpt is too short to audit"
            )

    return errors, warnings


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

    nested_runs = run_dir / "runs"
    if nested_runs.exists():
        errors.append(
            "nested runs directory found inside run package; use one run directory as the package of record "
            "instead of creating runs/attempt_* under an existing attempt directory"
        )

    if (run_dir / "DEBUG_OUTPUT_ONLY.txt").exists():
        final_like_outputs = [
            "industry_section_filled.pptx",
            "industry_section_filled_clean.pptx",
            "artifacts/final_delivery_validation.json",
        ]
        present = [rel for rel in final_like_outputs if (run_dir / rel).exists()]
        if present:
            errors.append(
                "debug-only run contains final-delivery artifact(s): "
                + ", ".join(present)
                + ". Ungated debug outputs must keep debug filenames and cannot be promoted to final."
            )

    for relative in REQUIRED_CORE_FILES:
        check_file_exists(run_dir, relative, errors)

    if require_research:
        for relative in REQUIRED_RESEARCH_FILES:
            check_file_exists(run_dir, relative, errors)

    memo_path = run_dir / "industry_research_pack.md"
    if memo_path.exists():
        for claimed in memo_claimed_artifacts(read_text(memo_path)):
            if not (run_dir / claimed).exists():
                errors.append(f"research pack claims artifact exists but file is missing: {claimed}")

    if (run_dir / "input_card.json").exists():
        check_file_exists(run_dir, "artifacts/input_card_validation.json", errors)

    for relative in [
        "artifacts/input_card_validation.json",
        "artifacts/industry_scope_pack_validation.json",
        "artifacts/formal_search_plan_validation.json",
        "artifacts/renderer_spec_validation.json",
        "artifacts/chart_metric_binding_validation.json",
        "artifacts/stage_gate_pre_ppt_validation.json",
        "artifacts/stage_gate_pre_research_pack_validation.json",
        "artifacts/formal_research_execution_validation.json",
        "artifacts/research_pack_validation.json",
        "artifacts/issue_analysis_validation.json",
        "artifacts/template_registry_validation.json",
        "artifacts/deck_blueprint_validation.json",
        "artifacts/page_evidence_contract_validation.json",
        "artifacts/replacement_dict_validation.json",
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
            warning_count = int(content_quality.get("warning_count") or 0) if isinstance(content_quality, dict) else 0
            if warning_count:
                warnings.append(f"content_quality_validation.json has {warning_count} advisory warning(s)")
            blocking_items = (
                content_quality.get("blocking_issues")
                or []
            ) if isinstance(content_quality, dict) else []
            if blocking_items:
                errors.append(f"content_quality_validation.json contains {len(blocking_items)} blocking issue(s)")

    search_log = run_dir / "artifacts/search_log.md"
    if search_log.exists():
        search_errors, search_warnings = validate_search_log(search_log)
        errors.extend(search_errors)
        warnings.extend(search_warnings)

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
        help="Do not require formal_search_plan/search_log artifacts. Use only for PPT-only debug runs.",
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
