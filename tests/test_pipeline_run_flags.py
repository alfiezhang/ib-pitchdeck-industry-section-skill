#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "runtime" / "ib-industry-section-skill" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pipeline import _write_run_flags  # noqa: E402


def test_pipeline_run_flags_preserve_formal_defaults(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_run_flags(run_dir, entrypoint="pytest")
    run_flags = json.loads((run_dir / "artifacts" / "run_flags.json").read_text(encoding="utf-8"))
    assert run_flags["schema_version"] == "run_flags_v1", run_flags
    assert run_flags["research_gate"] == 1, run_flags
    assert run_flags["issue_analysis_layer"] == 1, run_flags
    assert run_flags["quality_gate"] == 1, run_flags
    assert run_flags["debug_output_only"] is False, run_flags
    assert run_flags["pipeline_entrypoint"] == "pytest", run_flags


def test_pipeline_run_flags_preserves_debug_only_when_set(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    original = {
        "schema_version": "run_flags_v1",
        "research_gate": 1,
        "issue_analysis_layer": 1,
        "quality_gate": 1,
        "source_run_dir": "debug-source",
        "output_run_dir": "debug-output",
        "package_of_record": "debug-package",
        "debug_output_only": True,
        "debug_reason": "explicit-debug-mode",
        "pipeline_entrypoint": "scripts/pipeline.py render",
        "recorded_at": "2026-06-10T00:00:00",
    }
    (artifacts / "run_flags.json").write_text(json.dumps(original, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _write_run_flags(run_dir, entrypoint="scripts/pipeline.py render")
    run_flags = json.loads((artifacts / "run_flags.json").read_text(encoding="utf-8"))
    assert run_flags["debug_output_only"] is True, run_flags
    assert run_flags["debug_reason"] == "explicit-debug-mode", run_flags
    assert run_flags["package_of_record"] == "debug-package", run_flags


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        test_pipeline_run_flags_preserve_formal_defaults(tmp_path / "formal")
        test_pipeline_run_flags_preserves_debug_only_when_set(tmp_path / "debug")
    print("pipeline run_flags regression tests passed.")
