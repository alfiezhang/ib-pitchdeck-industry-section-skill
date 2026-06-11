#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "runtime" / "ib-pitchdeck-agent-industry-section" / "scripts"

sys.path.insert(0, str(SCRIPT_DIR))

from promote_research_requests import promote_requests  # noqa: E402
from validate_research_request_queue import validate as validate_research_request_queue  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _base_formal_search_plan() -> dict:
    return {
        "schema_version": "formal_search_plan_v1",
        "meta": {},
        "plan_mode": "coverage_audit",
        "industry_scope_pack": {},
        "issue_search_plan": [
            {
                "issue_area": "market_size_growth",
                "subissue": "current_market_size",
                "request_id": "RQ-COVERAGE-001",
                "hypothesis_id": "HYP-COVERAGE-001",
                "search_instructions": [
                    {
                        "instruction_id": "FS-005",
                        "query": "existing coverage row",
                    }
                ],
            }
        ],
    }


def _valid_queue_payload() -> dict:
    return {
        "schema_version": "research_request_queue_v1",
        "requests": [
            {
                "request_id": "RQ-001",
                "hypothesis_id": "HYP-001",
                "origin_issue_id": "IA-001",
                "research_question": "What is the practical adoption curve and what evidence supports it?",
                "required_source_type": "public_search",
                "minimum_actual_searches": 1,
                "downstream_permission_if_unresolved": "caveat_or_diligence_question_only",
            },
            {
                "request_id": "RQ-002",
                "hypothesis_id": "HYP-002",
                "origin_issue_area": "pitch_relevance_target_context",
                "origin_issue_subissue": "evidence_limits",
                "research_question": "What regulatory constraints should we caveat explicitly?",
                "required_source_type": "repository_retrieval",
                "minimum_actual_searches": 2,
                "downstream_permission_if_unresolved": "context_only",
            },
        ],
    }


def test_research_request_queue_rejects_internal_data_request() -> None:
    payload = {
        "schema_version": "research_request_queue_v1",
        "requests": [
            {
                "request_id": "RQ-001",
                "hypothesis_id": "HYP-001",
                "origin_issue_id": "IA-001",
                "research_question": "Can the client provide confidential internal management data?",
                "required_source_type": "internal_data_request",
                "minimum_actual_searches": 0,
                "downstream_permission_if_unresolved": "caveat_or_diligence_question_only",
            }
        ],
    }

    errors, warnings = validate_research_request_queue(payload)

    assert any("internal_data_request is not allowed" in item for item in errors)
    assert warnings


def test_promote_requests_appends_new_fs_rows_without_io_side_effects(tmp_path: Path) -> None:
    plan_path = tmp_path / "artifacts" / "formal_search_plan.json"
    queue_path = tmp_path / "artifacts" / "research_request_queue.json"
    output_plan = tmp_path / "artifacts" / "formal_search_plan_updated.json"

    _write_json(plan_path, _base_formal_search_plan())
    _write_json(queue_path, _valid_queue_payload())

    updated_plan, added, skipped = promote_requests(
        request_queue_path=queue_path,
        formal_search_plan_path=plan_path,
        formal_research_execution_report=None,
    )

    output_plan.write_text(json.dumps(updated_plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    assert len(added) == 2
    assert skipped == []
    assert updated_plan["issue_search_plan"][1]["search_instructions"][0]["instruction_id"] == "FS-006"
    assert updated_plan["issue_search_plan"][2]["search_instructions"][0]["instruction_id"] == "FS-007"
    assert updated_plan["issue_search_plan"][1]["request_id"] == "RQ-001"
    assert updated_plan["issue_search_plan"][2]["request_id"] == "RQ-002"
    assert updated_plan["issue_search_plan"][2]["hypothesis_id"] == "HYP-002"
    assert updated_plan["issue_search_plan"][1]["downstream_permission_if_unresolved"] == "caveat_or_diligence_question_only"
    assert updated_plan["issue_search_plan"][2]["downstream_permission_if_unresolved"] == "context_only"

    for row in updated_plan["issue_search_plan"][1:]:
        assert row["coverage_required"] is True
        assert row["minimum_actual_searches"] >= 0
        assert row["research_question"]


def test_promote_requests_is_idempotent_and_safely_skips_already_promoted_rows(tmp_path: Path) -> None:
    plan_path = tmp_path / "artifacts" / "formal_search_plan.json"
    queue_path = tmp_path / "artifacts" / "research_request_queue.json"

    payload = _base_formal_search_plan()
    payload["issue_search_plan"].append(
        {
            "issue_area": "pitch_relevance_target_context",
            "subissue": "evidence_limits",
            "request_id": "RQ-001",
            "hypothesis_id": "HYP-001",
            "search_instructions": [
                {
                    "instruction_id": "FS-001",
                    "query": "already promoted row",
                    "request_id": "RQ-001",
                }
            ],
        }
    )
    _write_json(plan_path, payload)
    _write_json(queue_path, _valid_queue_payload())

    _, added, skipped = promote_requests(request_queue_path=queue_path, formal_search_plan_path=plan_path)

    assert len(added) == 1
    assert added[0]["request_id"] == "RQ-002"
    assert any(item.get("request_id") == "RQ-001" and item.get("reason") == "already_promoted" for item in skipped)


def test_promote_requests_rejects_invalid_request_rows(tmp_path: Path) -> None:
    plan_path = tmp_path / "artifacts" / "formal_search_plan.json"
    queue_path = tmp_path / "artifacts" / "research_request_queue.json"

    _write_json(plan_path, _base_formal_search_plan())
    _write_json(
        queue_path,
        {
            "schema_version": "research_request_queue_v1",
            "requests": [
                {
                    "request_id": "",
                    "hypothesis_id": "HYP-NO-ID",
                    "research_question": "No request id",
                    "downstream_permission_if_unresolved": "context_only",
                    "minimum_actual_searches": 1,
                },
                {
                    "request_id": "RQ-NO-HYP",
                    "research_question": "No hypothesis id",
                    "downstream_permission_if_unresolved": "context_only",
                    "minimum_actual_searches": 1,
                },
                {
                    "request_id": "RQ-NEG",
                    "hypothesis_id": "HYP-NEG",
                    "research_question": "Negative minimum",
                    "downstream_permission_if_unresolved": "context_only",
                    "minimum_actual_searches": -2,
                },
                {
                    "request_id": "RQ-BAD-PERM",
                    "hypothesis_id": "HYP-BAD-PERM",
                    "research_question": "Would be headline requested",
                    "downstream_permission_if_unresolved": "headline_allowed",
                    "minimum_actual_searches": 1,
                },
            ],
        },
    )

    _, _, skipped = promote_requests(request_queue_path=queue_path, formal_search_plan_path=plan_path)

    reasons = {item["request_id"]: item["reason"] for item in skipped}
    assert reasons[""] == "missing request_id"
    assert reasons["RQ-NO-HYP"] == "missing hypothesis_id"
    assert reasons["RQ-NEG"] == "minimum_actual_searches must be >= 0"
    assert reasons["RQ-BAD-PERM"] == "unresolved request cannot be headline_allowed"


def test_promote_research_requests_cli_requires_valid_inputs(tmp_path: Path) -> None:
    plan_path = tmp_path / "artifacts" / "formal_search_plan.json"
    queue_path = tmp_path / "artifacts" / "research_request_queue.json"
    _write_json(plan_path, _base_formal_search_plan())
    _write_json(queue_path, _valid_queue_payload())

    result = subprocess.run(
        [
            sys.executable,
            "scripts/promote_research_requests.py",
            "--research-request-queue",
            str(queue_path),
            "--formal-search-plan",
            str(plan_path),
            "--output",
            str(tmp_path / "artifacts" / "formal_search_plan_next.json"),
            "--incremental-search-plan",
            str(tmp_path / "artifacts" / "incremental_search_plan.json"),
        ],
        cwd=str(SCRIPT_DIR.parent),
        text=True,
        capture_output=True,
        env={**__import__("os").environ, "PYTHONPATH": str(SCRIPT_DIR)},
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["is_valid"] is True
    assert payload["request_count"] == 2
    assert payload["request_promotions"][0]["instruction_id"]
    assert Path(payload["incremental_search_plan"]).exists()
    incremental_payload = json.loads(Path(payload["incremental_search_plan"]).read_text(encoding="utf-8"))
    assert {item["request_id"] for item in incremental_payload} == {"RQ-001", "RQ-002"}


def test_promote_requests_with_empty_queue_reports_skipped_reason(tmp_path: Path) -> None:
    plan_path = tmp_path / "artifacts" / "formal_search_plan.json"
    queue_path = tmp_path / "artifacts" / "research_request_queue.json"

    _write_json(plan_path, _base_formal_search_plan())
    _write_json(queue_path, {"schema_version": "research_request_queue_v1", "requests": []})

    _, _, skipped = promote_requests(request_queue_path=queue_path, formal_search_plan_path=plan_path)

    assert skipped and skipped[0]["reason"] == "research request queue missing or empty"
