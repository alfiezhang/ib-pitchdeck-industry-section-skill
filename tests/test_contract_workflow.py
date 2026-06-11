"""Contract tests: workflow next commands, run state, agent handoff, run quality, pipeline status.

Covers Groups 16f-16h from the monolith (lines 1388-1447) and Group 18.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1] / "runtime" / "ib-pitchdeck-agent-industry-section"
SCRIPT_DIR = SKILL_DIR / "scripts"

sys.path.insert(0, str(SCRIPT_DIR))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run(args: list[str]) -> subprocess.CompletedProcess:
    env = {**__import__("os").environ, "PYTHONPATH": str(SCRIPT_DIR)}
    return subprocess.run(args, text=True, capture_output=True, cwd=str(SKILL_DIR), env=env)


def _seed_boundary_loop_ready(run_dir: Path) -> None:
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    _write_json(
        artifacts / "boundary_loop_status.json",
        {
            "schema_version": "boundary_loop_status_v1",
            "status": "boundary_ready",
            "boundary_loop_status": "boundary_ready",
            "is_valid": True,
            "created_at": "2026-01-01T00:00:00Z",
            "errors": [],
            "warnings": [],
            "repair_actions": [],
            "boundary_inputs": {
                "scope_pack": True,
                "material_extracts": True,
                "research_evidence_db": True,
            },
        },
    )


class TestRunState:
    def test_run_state_after_full_pipeline(self, _pipeline_run_dir):
        from validate_run_state import validate_run_state
        run_dir = _pipeline_run_dir["run_dir"]
        _seed_boundary_loop_ready(run_dir)
        state = validate_run_state(run_dir)
        # The fixture seeds artifacts through research_pack + template_registry,
        # so the pipeline should be past the research stages.
        assert state["current_stage"] not in {"INPUT_CARD_MISSING", "INDUSTRY_SCOPE_PACK_MISSING_OR_FAILED"}, state
        assert state["current_stage"] in {
            "RESEARCH_PACK_MISSING_OR_FAILED", "ISSUE_ANALYSIS_MISSING_OR_FAILED",
            "TEMPLATE_REGISTRY_MISSING_OR_FAILED", "DECK_BLUEPRINT_MISSING_OR_FAILED",
        }, state


class TestWorkflowNextCommands:
    def test_source_review_commands(self, _pipeline_run_dir):
        from workflow import recommended_commands
        run_dir = str(_pipeline_run_dir["run_dir"])
        commands = recommended_commands({"run_dir": run_dir, "current_stage": "SOURCE_REVIEWS_MISSING_OR_FAILED"})
        validation_cmds = [c["command"] for c in commands if "validate_source_reviews.py" in c["command"]]
        assert validation_cmds, commands
        assert "--formal-research-execution-report" not in validation_cmds[0], validation_cmds
        assert "--source-archive-index" not in validation_cmds[0], validation_cmds

    def test_source_archive_commands(self, _pipeline_run_dir):
        from workflow import recommended_commands
        run_dir = str(_pipeline_run_dir["run_dir"])
        commands = recommended_commands({"run_dir": run_dir, "current_stage": "SOURCE_ARCHIVE_MISSING_OR_FAILED"})
        assert commands and "scripts/build_source_archive.py" in commands[0]["command"], commands
        assert "--run-dir" in commands[0]["command"], commands
        assert "--output-dir" not in commands[0]["command"], commands

    def test_execution_commands(self, _pipeline_run_dir):
        from workflow import recommended_commands
        run_dir = str(_pipeline_run_dir["run_dir"])
        commands = recommended_commands({"run_dir": run_dir, "current_stage": "FORMAL_RESEARCH_EXECUTION_MISSING_OR_FAILED"})
        validation_cmds = [c["command"] for c in commands if "validate_formal_research_execution.py" in c["command"]]
        assert validation_cmds, commands
        assert "--report" in validation_cmds[0], validation_cmds
        assert "--formal-research-execution-report" not in validation_cmds[0], validation_cmds

    def test_research_evidence_db_commands(self, _pipeline_run_dir):
        from workflow import recommended_commands
        run_dir = str(_pipeline_run_dir["run_dir"])
        commands = recommended_commands({"run_dir": run_dir, "current_stage": "RESEARCH_EVIDENCE_DB_MISSING_OR_FAILED"})
        assert commands and "scripts/build_research_evidence_db.py" in commands[0]["command"], commands

    def test_research_pack_commands(self, _pipeline_run_dir):
        from workflow import recommended_commands
        run_dir = str(_pipeline_run_dir["run_dir"])
        commands = recommended_commands({"run_dir": run_dir, "current_stage": "RESEARCH_PACK_MISSING_OR_FAILED"})
        assert commands and "scripts/export_research_pack_from_db.py" in commands[0]["command"], commands
        validation_cmds = [c["command"] for c in commands if "validate_research_pack.py" in c["command"]]
        assert validation_cmds and "--source-registry templates/source_registry.json" in validation_cmds[0], validation_cmds

    def test_replacement_dict_commands(self, _pipeline_run_dir):
        from workflow import recommended_commands
        run_dir = str(_pipeline_run_dir["run_dir"])
        commands = recommended_commands({"run_dir": run_dir, "current_stage": "REPLACEMENT_DICT_MISSING_OR_FAILED"})
        assert commands and "scripts/pipeline.py render" in commands[0]["command"], commands

    def test_final_delivery_commands(self, _pipeline_run_dir):
        from workflow import recommended_commands
        run_dir = str(_pipeline_run_dir["run_dir"])
        commands = recommended_commands({"run_dir": run_dir, "current_stage": "FINAL_DELIVERY_NOT_READY"})
        assert commands and "scripts/pipeline.py render" in commands[0]["command"], commands


class TestAgentHandoff:
    def test_build_handoff(self, _pipeline_run_dir):
        from build_agent_handoff import build_handoff
        run_dir = _pipeline_run_dir["run_dir"]
        handoff = build_handoff(run_dir, run_dir / "artifacts" / "agent_handoff")
        assert handoff["schema_version"] == "agent_handoff_index_v1", handoff
        assert len(handoff["roles"]) == 7, handoff
        assert (run_dir / "artifacts" / "agent_handoff" / "format_qc.md").exists()


class TestRunQualitySummary:
    def test_build_summary(self, _pipeline_run_dir):
        from generate_run_quality_summary import build_summary_payload
        quality = build_summary_payload(_pipeline_run_dir["run_dir"])
        assert quality["schema_version"] == "run_quality_summary_v2", quality
        assert quality["verdict"] == "NOT_CLIENT_READY", quality
        assert quality["next_repair_targets"], quality


class TestPipelineStatus:
    def test_pipeline_status_reports_stage(self, _pipeline_run_dir):
        result = _run([
            sys.executable, "scripts/pipeline.py", "status",
            "--run-dir", str(_pipeline_run_dir["run_dir"]),
        ])
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["current_stage"] not in {"INPUT_CARD_MISSING", "INDUSTRY_SCOPE_PACK_MISSING_OR_FAILED"}, payload
