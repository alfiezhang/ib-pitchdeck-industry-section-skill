from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "runtime" / "ib-industry-section-skill" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import pipeline  # noqa: E402
from pipeline import PipelineError, finalize  # noqa: E402
from validate_final_delivery import _looks_like_research_error  # noqa: E402
from validate_formal_search_plan import validate as validate_formal_search_plan  # noqa: E402
from gate_guard import _looks_like_formal_run  # noqa: E402
from build_formal_search_plan_skeleton import build_plan  # noqa: E402


def test_finalize_short_circuits_on_validation_failure(tmp_path: Path) -> None:
    run_dir = tmp_path / "attempt_001"
    run_dir.mkdir(parents=True)

    call_count = {"run": 0}

    def fake_run(*_args: object, **_kwargs: object) -> None:
        call_count["run"] += 1

    original_run = pipeline._run
    original_run_returncode = pipeline._run_returncode

    try:
        pipeline._run = fake_run
        pipeline._run_returncode = lambda *args, **kwargs: 1  # validation failed
        try:
            finalize(run_dir, "python3", require_client_ready=False)
        except PipelineError:
            pass
        else:
            raise AssertionError("finalize should raise PipelineError when validate_final_delivery fails")
    finally:
        pipeline._run = original_run
        pipeline._run_returncode = original_run_returncode

    assert call_count["run"] == 0, f"generate_run_quality_summary/update_runs_index should not run on failure: {call_count['run']}"
    assert (run_dir / "NOT_CLIENT_READY_OUTPUT.txt").exists()
    assert not (run_dir.parent / "ACTIVE_ATTEMPT.txt").exists()


def test_json_helper_raises_on_corrupt_payload(tmp_path: Path) -> None:
    bad_json = tmp_path / "artifacts" / "run_flags.json"
    bad_json.parent.mkdir(parents=True, exist_ok=True)
    bad_json.write_text("{", encoding="utf-8")

    try:
        pipeline._json(bad_json)
    except PipelineError as exc:
        assert "Invalid JSON" in str(exc)
    else:
        raise AssertionError("corrupt run_flags.json must raise PipelineError")


def test_research_error_matching_is_specific() -> None:
    assert _looks_like_research_error("missing formal search instruction IDs for high-priority subissue")
    assert _looks_like_research_error("search_plan execution not complete")
    assert _looks_like_research_error("industry_research_pack was not generated")
    assert _looks_like_research_error("Missing source classification result")
    assert not _looks_like_research_error("source file path is not readable")
    assert not _looks_like_research_error("renderer spec schema invalid")


def test_formal_search_plan_high_priority_warning_allows_multivariants() -> None:
    plan = build_plan({}, {})
    for issue in plan["issue_search_plan"]:
        if issue.get("priority") == "high":
            issue["search_instructions"] = [
                {
                    "instruction_id": issue["search_instructions"][0]["instruction_id"],
                    "query": issue["search_instructions"][0]["query"],
                    "query_variants": ["Variant A for verification", "Variant B for verification"],
                    "purpose": issue["search_instructions"][0]["purpose"],
                    "search_stage": "formal_research_execution",
                }
            ]
            break
    errors, warnings = validate_formal_search_plan(plan)
    assert not errors
    assert not any("high-priority issue has only" in warning for warning in warnings)


def test_formal_looks_like_formal_run_requires_multiple_markers(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)

    assert not _looks_like_formal_run(run_dir)
    (run_dir / "input_card.json").write_text("{}", encoding="utf-8")
    assert not _looks_like_formal_run(run_dir)
    (run_dir / "artifacts").mkdir(parents=True)
    (run_dir / "artifacts" / "research_evidence_db.json").write_text("{}", encoding="utf-8")
    assert _looks_like_formal_run(run_dir)

    (run_dir / "artifacts" / "run_flags.json").write_text("{}", encoding="utf-8")
    assert _looks_like_formal_run(run_dir)



def main() -> int:
    with __import__("tempfile").TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        test_finalize_short_circuits_on_validation_failure(tmp_path / "run")
        test_json_helper_raises_on_corrupt_payload(tmp_path / "json")
        test_formal_looks_like_formal_run_requires_multiple_markers(tmp_path / "run2")
    test_formal_search_plan_high_priority_warning_allows_multivariants()
    test_research_error_matching_is_specific()
    print("Issue fix regression tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
