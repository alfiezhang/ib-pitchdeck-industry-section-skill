#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

from conftest import _minimal_scope_pack, _write_json


def test_boundary_card_minimal_valid_scope_pack_passes(tmp_path: Path) -> None:
    from validate_artifact import validate_artifact

    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    _write_json(artifacts / "industry_scope_pack.json", _minimal_scope_pack())

    errors, warnings = validate_artifact("industry_scope_pack", run_dir)

    assert not errors, errors
    assert not warnings, warnings


def test_scope_pack_template_copy_fails_validation(tmp_path: Path) -> None:
    from validate_artifact import validate_artifact

    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    _write_json(
        artifacts / "industry_scope_pack.json",
        {
            "schema_version": "industry_scope_pack_boundary_card",
            "_shape_hint_only": True,
            "meta": {},
            "scope_summary": {"working_market": "", "parent_market": "", "broader_market": ""},
            "scope_classification": {"core": [], "broad": [], "adjacent": [], "excluded": []},
            "must_reconcile": [],
            "boundary_checks_if_needed": [],
        },
    )

    errors, _ = validate_artifact("industry_scope_pack", run_dir)

    assert any("_shape_hint_only=true" in error for error in errors), errors


def test_scope_pack_validation_is_mechanical_not_memo_author(tmp_path: Path) -> None:
    from validate_artifact import validate_artifact

    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    scope = json.loads(json.dumps(_minimal_scope_pack()))
    scope["scope_summary"]["working_market"] = "example market size reached 100亿元"
    _write_json(artifacts / "industry_scope_pack.json", scope)

    errors, _ = validate_artifact("industry_scope_pack", run_dir)

    assert not errors, errors


def test_scope_pack_missing_required_summary_field_fails(tmp_path: Path) -> None:
    from validate_artifact import validate_artifact

    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    scope = json.loads(json.dumps(_minimal_scope_pack()))
    scope["scope_summary"]["working_market"] = ""
    _write_json(artifacts / "industry_scope_pack.json", scope)

    errors, _ = validate_artifact("industry_scope_pack", run_dir)

    assert any("scope_summary.working_market" in error for error in errors), errors


def test_scope_pack_missing_do_not_use_as_claims_warns_not_fails(tmp_path: Path) -> None:
    from validate_artifact import validate_artifact

    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    scope = json.loads(json.dumps(_minimal_scope_pack()))
    scope.pop("do_not_use_as_claims", None)
    _write_json(artifacts / "industry_scope_pack.json", scope)

    errors, warnings = validate_artifact("industry_scope_pack", run_dir)

    assert not errors, errors
    assert any("boundary card only" in warning for warning in warnings), warnings
