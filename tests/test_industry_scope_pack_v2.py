#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "runtime" / "ib-pitchdeck-agent-industry-section" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from conftest import _minimal_scope_pack  # noqa: E402
from validate_industry_scope_pack import validate as validate_industry_scope_pack  # noqa: E402


def _scope() -> dict:
    return json.loads(json.dumps(_minimal_scope_pack()))


def test_v2_minimal_valid_scope_pack_passes() -> None:
    errors, warnings = validate_industry_scope_pack(_scope())

    assert not errors, errors
    assert not warnings, warnings


def test_long_memo_like_field_fails() -> None:
    scope = _scope()
    scope["handoff_to_research"]["research_scope"] = (
        "This is a long scoping memo paragraph that explains the market in a narrative way, "
        "adds context that belongs in a research note, keeps going beyond the boundary card, "
        "and starts to read like a page-ready summary instead of a concise scope definition. "
        "It should fail because the scope pack is only a boundary card."
    )

    errors, _ = validate_industry_scope_pack(scope)

    assert any("memo-like paragraph" in error or "no more than 2 sentences" in error for error in errors), errors


def test_market_growth_and_share_claims_fail() -> None:
    scope = _scope()
    scope["scope_summary"]["working_market"] = "example market size reached 100亿元"
    scope["scope_classification"]["broad"][0] = "category CAGR 12%"
    scope["handoff_to_research"]["must_label_when_used"] = ["leader share 35%"]

    errors, _ = validate_industry_scope_pack(scope)

    assert any("market size claim" in error for error in errors), errors
    assert any("growth rate claim" in error for error in errors), errors
    assert any("share claim" in error for error in errors), errors


def test_empty_boundary_validation_needed_allowed() -> None:
    scope = _scope()
    scope["boundary_validation_needed"] = []

    errors, _ = validate_industry_scope_pack(scope)

    assert not errors, errors


def test_undisclosed_target_allowed_with_status() -> None:
    scope = _scope()
    scope["meta"]["target_company"] = ""
    scope["meta"]["target_disclosure_status"] = "undisclosed"

    errors, _ = validate_industry_scope_pack(scope)

    assert not errors, errors


def test_user_provided_unverified_ranking_can_be_reconciled() -> None:
    scope = _scope()
    scope["must_reconcile"] = [
        {
            "topic": "用户提供抖音榜单Top 1",
            "why_it_matters": "未验证排名不能作为外部证据",
            "research_instruction": "需验证原始平台或第三方来源；未验证前标注user-provided",
        }
    ]

    errors, _ = validate_industry_scope_pack(scope)

    assert not errors, errors


def test_confirmed_ranking_claim_still_fails_outside_reconciliation_queue() -> None:
    scope = _scope()
    scope["scope_classification"]["core"] = ["Top 1 winning category"]

    errors, _ = validate_industry_scope_pack(scope)

    assert any("ranking claim" in error for error in errors), errors


def test_max_list_lengths_enforced() -> None:
    scope = _scope()
    scope["scope_classification"]["core"] = [f"core {idx}" for idx in range(7)]
    scope["must_reconcile"] = [
        {"topic": f"topic {idx}", "why_it_matters": "scope comparability", "research_instruction": "label source scope"}
        for idx in range(6)
    ]

    errors, _ = validate_industry_scope_pack(scope)

    assert any("scope_classification.core has 7 items" in error for error in errors), errors
    assert any("must_reconcile has 6 items" in error for error in errors), errors


def test_v1_scope_pack_fails_with_migration_message() -> None:
    errors, _ = validate_industry_scope_pack({"schema_version": "industry_scope_pack_v1"})

    assert any("industry_scope_pack_v2" in error and "v1 scope memo artifacts" in error for error in errors), errors
