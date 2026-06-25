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
            "scripts/qc/validate_artifact.py",
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
        "schema_version": "research_request_queue_v1",
        "authoring_mode": "llm_authored",
        "policy_context": "pre_mandate_client_pitch",
        "requests": [
            {
                "request_id": "RQ-001",
                "origin_artifact": "banker_page_pack.json",
                "origin_ref_id": "BP-002",
                "research_question": "Which public source confirms the category growth claim?",
                "required_source_type": "public_search",
                "minimum_actual_searches": 2,
                "downstream_permission_if_unresolved": "caveat_or_evidence_boundary_only",
                "status": "pending_public_evidence",
                "reason_needed": "The current page argument has only directional evidence.",
                "success_criteria": "A primary or named industry report source with an opened locator.",
                "forbidden_use": "Do not use as a headline until resolved.",
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


def test_research_request_queue_rejects_builder_style_payload(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    payload = _valid_queue()
    payload.pop("authoring_mode")
    _write_json(run_dir / "artifacts/research_request_queue.json", payload)

    result = _run_validate(run_dir)

    assert result.returncode != 0
    assert "authoring_mode must be llm_authored" in result.stdout


def test_research_request_queue_builder_script_removed() -> None:
    assert not (SKILL_DIR / "scripts/reasoning/build_research_request_queue.py").exists()
