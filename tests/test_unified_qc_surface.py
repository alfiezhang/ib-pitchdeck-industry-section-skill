#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from conftest import SCRIPT_IMPORT_PATHS, SKILL_DIR, _write_json


def _run(args: list[str]) -> subprocess.CompletedProcess:
    env = {**__import__("os").environ, "PYTHONPATH": ":".join(str(path) for path in SCRIPT_IMPORT_PATHS)}
    return subprocess.run(args, text=True, capture_output=True, cwd=str(SKILL_DIR), env=env)


def test_old_qc_entrypoints_are_removed() -> None:
    assert not (SKILL_DIR / ("scripts/state_" + "report.py")).exists()
    assert not (SKILL_DIR / ("scripts/qc/gate_" + "report.py")).exists()
    assert not (SKILL_DIR / ("scripts/qc/qc_" + "router.py")).exists()
    assert not (SKILL_DIR / ("scripts/qc/" + "validators")).exists()
    assert not (SKILL_DIR / "scripts/industry-scoping/boundary_loop.py").exists()
    assert not (SKILL_DIR / "scripts/knowledge-repository/repository.py").exists()
    assert not (SKILL_DIR / "scripts/output/update_runs_index.py").exists()
    assert not (SKILL_DIR / "scripts/template/select_template.py").exists()


def test_status_next_reports_missing_first_artifact(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    result = _run([sys.executable, "scripts/status.py", "next", "--run-dir", str(run_dir)])

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "status_report_v1"
    assert payload["current_stage"] == "input_card"
    assert payload["current_state"] == "missing"
    assert "scripts/qc/validate_artifact.py" in payload["recommended_next_commands"][-1]


def test_validate_artifact_cli_writes_output(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_json(run_dir / "input_card.json", {"raw_brief": "Sample brief"})
    output = run_dir / "artifacts/input_card_validation.json"

    result = _run([
        sys.executable,
        "scripts/qc/validate_artifact.py",
        "--artifact",
        "input_card",
        "--run-dir",
        str(run_dir),
        "--output",
        str(output),
    ])

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["is_valid"] is True
    assert payload["validation_policy"] == "mechanical_only"
