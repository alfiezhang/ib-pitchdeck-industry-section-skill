#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from conftest import SCRIPT_IMPORT_PATHS, SKILL_DIR, _write_json


def _run_validate(run_dir: Path) -> subprocess.CompletedProcess:
    env = {**__import__("os").environ, "PYTHONPATH": ":".join(str(path) for path in SCRIPT_IMPORT_PATHS)}
    return subprocess.run(
        [
            sys.executable,
            "scripts/pipeline.py",
            "review",
            "--artifact",
            "research_request_queue",
            "--run-dir",
            str(run_dir),
        ],
        text=True,
        capture_output=True,
        cwd=str(SKILL_DIR),
        env=env,
    )


def _valid_queue() -> dict:
    return {
        "schema_version": "research_request_queue",
        "loop_control": {
            "current_cycle": 1,
            "max_cycles": 2,
            "cycle_goal": "Resolve only evidence gaps that change deck inclusion, key data audit, or exhibit readiness.",
        },
        "requests": [
            {
                "active": True,
                "page_ref": "BP-002",
                "research_question": "Which public source confirms the category growth claim?",
                "would_change": "Whether the page can use the claim in the headline and chart.",
                "source_direction": "Try official statistics, industry association, or named sector report first.",
                "stop_condition": "Close after a named source supports the metric, or after three searches show only secondary commentary.",
            }
        ],
    }


def test_llm_authored_research_request_queue_passes(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_json(run_dir / "artifacts/research_request_queue.json", _valid_queue())

    result = _run_validate(run_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["is_valid"] is True


def test_research_request_queue_allows_natural_language_brief_without_enum_fields(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    output = json.loads(result.stdout)
    assert output["is_valid"] is True


def test_research_request_queue_allows_natural_search_budget_note(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload["requests"][0]["search_budget"] = "Try up to three source-specific searches if the first named-source search fails."
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "minimum_actual_searches" not in result.stdout
    assert "search_budget exceeds" not in result.stdout


def test_research_request_queue_validator_does_not_parse_budget_prose() -> None:
    validator_text = (SKILL_DIR / "scripts/qc/validate_artifact.py").read_text(encoding="utf-8")

    assert "_SEARCH_BUDGET_WORDS" not in validator_text
    assert "budget_values_near" not in validator_text
    assert "search_markers" not in validator_text
    assert "source_markers" not in validator_text
    assert "promotion_markers" not in validator_text
    assert "open_ended_markers" not in validator_text
    assert "_search_budget_is_open_ended" not in validator_text
    assert "_source_review_budget_is_open_ended" not in validator_text
    assert "_promoted_source_budget_is_open_ended" not in validator_text


def test_research_request_queue_targeting_prompts_are_not_hard_gates() -> None:
    validator_text = (SKILL_DIR / "scripts/qc/validate_artifact.py").read_text(encoding="utf-8")
    policy = json.loads((SKILL_DIR / "configs/research_planning_policy.json").read_text(encoding="utf-8"))
    note = policy["research_request_queue"]["helper_check_note"]

    assert "Page anchors and stop/close rules are LLM prompt warnings, not hard gates" in note
    assert "not a form" in policy["research_request_queue"]["authoring_guidance"]
    assert "LLM research prompt: {request_label} does not name the page" in validator_text
    assert "LLM research prompt: {request_label} does not name a stop condition" in validator_text
    assert "errors.append(\n                    f\"{request_label} does not name the page" not in validator_text
    assert "errors.append(\n                    f\"{request_label} does not name a stop condition" not in validator_text
    assert "search_budget exceeds policy cap" in validator_text
    assert "current_cycle={current_cycle} exceeds max_cycles={effective_max}" in validator_text


def test_research_request_queue_allows_chinese_natural_brief_fields(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload["loop_control"]["default_request_budget"] = (
        "默认最多三次搜索，打开审阅最多四个来源，最多提升两个来源。"
    )
    payload["requests"][0].pop("page_ref", None)
    payload["requests"][0].pop("would_change", None)
    payload["requests"][0].pop("stop_condition", None)
    payload["requests"][0]["decision_anchor"] = (
        "决定BP-002市场规模图表是否可进入正式页面，或降级为限定说明。"
    )
    payload["requests"][0]["why_it_matters"] = (
        "避免把泛化妆品大盘误当成底妆赛道证据。"
    )
    payload["requests"][0]["close_when"] = (
        "找到带口径和时间范围的公开来源后关闭；三次搜索后仍无来源则记录来源限制，不要重复搜索。"
    )
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    output = json.loads(result.stdout)
    assert output["is_valid"] is True


def test_research_request_queue_warns_when_why_it_matters_is_only_anchor(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    for field in ("page_ref", "would_change"):
        payload["requests"][0].pop(field, None)
    payload["requests"][0]["why_it_matters"] = (
        "这个问题很重要，会影响市场理解和后续叙事。"
    )
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    output = json.loads(result.stdout)
    assert output["is_valid"] is True
    assert "does not name the page, metric, headline, key data, or exhibit decision it could change" in result.stdout
    assert "LLM research prompt" in result.stdout


def test_research_request_queue_warns_when_origin_artifact_is_only_anchor(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    for field in ("page_ref", "would_change"):
        payload["requests"][0].pop(field, None)
    payload["requests"][0]["origin_artifact"] = "banker_page_pack"
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    output = json.loads(result.stdout)
    assert output["is_valid"] is True
    assert "does not name the page, metric, headline, key data, or exhibit decision it could change" in result.stdout
    assert "LLM research prompt" in result.stdout


def test_research_request_queue_inherits_policy_budget_without_filling_budget_fields(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    assert "search_budget" not in payload["requests"][0]
    assert "source_review_budget" not in payload["requests"][0]
    assert "default_request_budget" not in payload["loop_control"]
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    output = json.loads(result.stdout)
    assert output["is_valid"] is True


def test_research_request_queue_warns_when_close_rule_missing(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload["requests"][0].pop("stop_condition")
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    output = json.loads(result.stdout)
    assert output["is_valid"] is True
    assert "does not name a stop condition or close rule" in result.stdout
    assert "does not rerun it unchanged" in result.stdout


def test_research_request_queue_enforces_targeted_loop_caps(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload["requests"][0]["request_id"] = "RQ-001"
    for idx in range(2, 7):
        request = dict(payload["requests"][0])
        request["request_id"] = f"RQ-{idx:03d}"
        request["research_question"] = f"Targeted evidence question {idx}?"
        payload["requests"].append(request)
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode != 0
    assert "above targeted-loop cap 5" in result.stdout
    assert "minimum_actual_searches" not in result.stdout


def test_research_request_queue_inherits_policy_loop_when_cycle_tracking_is_omitted(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload.pop("loop_control")
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "loop_control omitted" in result.stdout
    assert "helper assumes current_cycle=1" in result.stdout


def test_research_request_queue_allows_empty_queue_without_cycle_tracking(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload.pop("loop_control")
    payload["requests"] = []
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "research_request_queue has no active requests" in result.stdout
    assert "loop_control omitted" in result.stdout


def test_research_request_queue_inherits_policy_cap_when_max_cycles_is_omitted(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload["loop_control"].pop("max_cycles")
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "loop_control.max_cycles omitted" in result.stdout
    assert "helper inherits max_cycles=2" in result.stdout


def test_research_request_queue_rejects_cycles_above_policy_cap(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload["loop_control"]["current_cycle"] = 3
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode != 0
    assert "current_cycle=3 exceeds max_cycles=2" in result.stdout


def test_research_request_queue_warns_on_final_targeted_cycle(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload["loop_control"]["current_cycle"] = 2
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "final targeted cycle" in result.stdout


def test_research_request_queue_rejects_final_cycle_outcome_with_active_requests(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload["loop_control"]["current_cycle"] = 2
    payload["loop_control"]["latest_cycle_outcome"] = (
        "Final targeted searches did not find an audit-grade source for the requested metric."
    )
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode != 0
    assert "final targeted cycle already has latest_cycle_outcome" in result.stdout
    assert "Close resolved/exhausted requests" in result.stdout


def test_research_request_queue_rejects_final_cycle_without_active_request_or_outcome(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload["loop_control"]["current_cycle"] = 2
    payload["requests"] = [
        {
            "active": False,
            "request_id": "RQ-001",
            "research_question": "Can a public source support the key exhibit metric?",
            "status": "已完成，未找到可改变页面授权的来源",
        }
    ]
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode != 0
    assert "final targeted cycle has no active requests but no latest_cycle_outcome" in result.stdout
    assert "record what changed or why sources were unavailable" in result.stdout


def test_research_request_queue_allows_natural_execution_fields_without_enum_warnings(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload["requests"][0]["required_source_type"] = "expert_call"
    payload["requests"][0]["status"] = "waiting_for_specialist"
    payload["requests"][0]["downstream_permission_if_unresolved"] = "use_with_partner_note"
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "non-standard required_source_type" not in result.stdout
    assert "non-standard status" not in result.stdout
    assert "non-standard downstream_permission_if_unresolved" not in result.stdout


def test_research_request_queue_policy_does_not_publish_status_or_permission_enums() -> None:
    policy = json.loads((SKILL_DIR / "configs/research_planning_policy.json").read_text(encoding="utf-8"))
    queue_policy = policy.get("research_request_queue", {})
    forbidden = {
        "suggested_statuses",
        "suggested_downstream_permissions",
        "headline_aliases",
        "headline_alias_downgrade_permission",
        "default_permission_if_unresolved",
        "default_status",
        "default_allowed_use_before_resolution",
    }

    assert forbidden.isdisjoint(queue_policy)


def test_research_request_queue_warns_active_request_when_decision_anchor_is_missing(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    for field in ("page_ref", "would_change"):
        payload["requests"][0].pop(field, None)
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    output = json.loads(result.stdout)
    assert output["is_valid"] is True
    assert "does not name the page, metric, headline, key data, or exhibit decision it could change" in result.stdout
    assert "open-ended exploration" in result.stdout


def test_research_request_queue_rejects_structured_search_budget_above_policy_cap(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload["requests"][0]["max_searches"] = 5
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode != 0
    assert "search_budget exceeds policy cap 3" in result.stdout


def test_research_request_queue_allows_missing_search_budget_when_policy_cap_applies(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload["requests"][0].pop("search_budget", None)
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "missing bounded search budget" not in result.stdout


def test_research_request_queue_allows_missing_source_review_budget_when_policy_cap_applies(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload["requests"][0].pop("source_review_budget", None)
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "missing bounded source review budget" not in result.stdout


def test_research_request_queue_rejects_structured_loop_default_budget_above_policy_cap(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload["loop_control"]["max_searches"] = 5
    payload["loop_control"]["max_opened_sources"] = 6
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode != 0
    assert "search_budget exceeds policy cap 3" in result.stdout
    assert "source_review_budget exceeds policy cap 4" in result.stdout


def test_research_request_queue_treats_open_ended_budget_text_as_llm_note_not_routing_input(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload["loop_control"]["default_request_budget"] = "Search until found and open as many sources as needed."
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "open-ended" not in result.stdout


def test_research_request_queue_rejects_structured_source_review_budget_above_policy_cap(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload["requests"][0]["max_opened_sources"] = 6
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode != 0
    assert "source_review_budget exceeds policy cap 4" in result.stdout


def test_research_request_queue_treats_open_ended_source_review_budget_text_as_note(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload["requests"][0]["source_review_budget"] = "Open as many sources as needed until found."
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "open-ended" not in result.stdout


def test_research_request_queue_rejects_structured_promoted_source_budget_above_policy_cap(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload["loop_control"]["max_promoted_sources"] = 3
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode != 0
    assert "promoted-source budget exceeds policy cap 2" in result.stdout


def test_research_request_queue_treats_open_ended_promoted_source_budget_text_as_note(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload["requests"][0]["promoted_source_budget"] = "Promote as many sources as needed until found."
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "open-ended" not in result.stdout


def test_research_request_queue_treats_open_ended_search_budget_text_as_note(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload["requests"][0]["search_budget"] = "Search until found."
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "open-ended" not in result.stdout


def test_research_request_queue_request_id_is_optional(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload["requests"][0].pop("request_id", None)
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode == 0, result.stdout + result.stderr


def test_research_request_queue_warns_on_nonstandard_request_id(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload["requests"][0]["request_id"] = "request-one"
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "request_id does not look like RQ-001" in result.stdout


def test_research_request_queue_rejects_duplicate_request_id(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload["requests"][0]["request_id"] = "RQ-001"
    duplicate = dict(payload["requests"][0])
    duplicate["research_question"] = "Which public source confirms the second evidence gap?"
    payload["requests"].append(duplicate)
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode != 0
    assert "duplicate research request id: RQ-001" in result.stdout


def test_research_request_queue_requires_a_research_question(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload["requests"][0].pop("research_question")
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode != 0
    assert "missing research_question" in result.stdout


def test_research_request_queue_warns_missing_active_boolean(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload["requests"][0].pop("active")
    payload["requests"][0]["status"] = "waiting for one final source check"
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "missing active boolean" in result.stdout
    assert "helper treats it as active" in result.stdout


def test_research_request_queue_template_copy_fails_validation(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_json(
        run_dir / "artifacts/research_request_queue.json",
        {
            "schema_version": "research_request_queue",
            "_shape_hint_only": True,
            "loop_control": {
                "current_cycle": 1,
                "max_cycles": 2,
                "default_request_budget": {
                    "max_searches": 3,
                    "max_sources_to_review": 4,
                    "max_promoted_sources": 2,
                },
            },
            "requests": [],
        },
    )

    result = _run_validate(run_dir)

    assert result.returncode != 0
    assert "_shape_hint_only=true" in result.stdout


def test_research_request_queue_builder_script_removed() -> None:
    assert not (SKILL_DIR / "scripts/reasoning/build_research_request_queue.py").exists()
