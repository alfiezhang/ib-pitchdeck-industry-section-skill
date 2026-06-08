#!/usr/bin/env python3
"""Helpers that stop downstream validators from passing failed formal runs."""

from __future__ import annotations

import json
from pathlib import Path


BASE_RESEARCH_VALIDATIONS = (
    "artifacts/industry_scope_pack_validation.json",
    "artifacts/formal_search_plan_validation.json",
    "artifacts/formal_research_execution_validation.json",
    "artifacts/source_archive_validation.json",
    "artifacts/source_reviews_validation.json",
    "artifacts/stage_gate_pre_research_pack_validation.json",
    "artifacts/research_pack_validation.json",
)

ISSUE_ANALYSIS_UPSTREAM_VALIDATIONS = BASE_RESEARCH_VALIDATIONS

DECK_BLUEPRINT_UPSTREAM_VALIDATIONS = BASE_RESEARCH_VALIDATIONS + (
    "artifacts/issue_analysis_validation.json",
    "artifacts/template_registry_validation.json",
)

COMPILE_UPSTREAM_VALIDATIONS = DECK_BLUEPRINT_UPSTREAM_VALIDATIONS + (
    "artifacts/deck_blueprint_validation.json",
)

RENDERER_SPEC_UPSTREAM_VALIDATIONS = COMPILE_UPSTREAM_VALIDATIONS + (
    "artifacts/page_evidence_contract_validation.json",
)


def maybe_run_dir_from_inputs(paths: list[Path], expected_names: set[str]) -> Path | None:
    parents = [path.resolve().parent for path in paths if path.name in expected_names]
    if len(parents) < len(expected_names):
        return None
    first = parents[0]
    if all(parent == first for parent in parents) and (first / "artifacts").is_dir():
        return first
    return None


def upstream_validation_errors(run_dir: Path, validation_rels: tuple[str, ...]) -> list[str]:
    errors: list[str] = []
    for rel in validation_rels:
        path = run_dir / rel
        if not path.exists():
            errors.append(f"missing {rel}")
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"cannot read {rel}: {exc}")
            continue
        if payload.get("is_valid") is not True:
            errors.append(f"{rel} is_valid=false")
    return errors


def assert_formal_upstream_valid(
    paths: list[Path],
    *,
    expected_names: set[str],
    validation_rels: tuple[str, ...],
    stage_name: str,
) -> list[str]:
    run_dir = maybe_run_dir_from_inputs(paths, expected_names)
    if run_dir is None:
        return []
    blocking = upstream_validation_errors(run_dir, validation_rels)
    if not blocking:
        return []
    detail = "; ".join(blocking[:10])
    return [
        f"cannot validate {stage_name} for a formal run with incomplete upstream gates: {detail}. "
        "Run scripts/workflow.py status/next, fix the failed upstream gate, then rerun this validator."
    ]
