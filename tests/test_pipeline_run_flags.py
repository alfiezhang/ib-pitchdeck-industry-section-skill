#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "runtime" / "ib-pitchdeck-agent-industry-section" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pipeline import _clear_draft_state, _write_run_flags  # noqa: E402


def test_pipeline_run_flags_preserve_formal_defaults(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_run_flags(run_dir, entrypoint="pytest")
    run_flags = json.loads((run_dir / "artifacts" / "run_flags.json").read_text(encoding="utf-8"))
    assert run_flags["schema_version"] == "run_flags_v1", run_flags
    assert run_flags["research_gate"] == 1, run_flags
    assert run_flags["banker_page_pack_layer"] == 1, run_flags
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
        "banker_page_pack_layer": 1,
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


def test_pipeline_run_flags_can_replace_draft_flags_for_formal_render(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "run_flags.json").write_text(
        json.dumps(
            {
                "schema_version": "run_flags_v1",
                "research_gate": 0,
                "banker_page_pack_layer": 0,
                "quality_gate": 0,
                "debug_output_only": True,
                "draft_output_only": True,
                "pipeline_entrypoint": "draft-test",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "DRAFT_NOT_CLIENT_READY.txt").write_text("draft\n", encoding="utf-8")

    _clear_draft_state(run_dir)
    _write_run_flags(run_dir, entrypoint="scripts/pipeline.py render")

    run_flags = json.loads((run_dir / "artifacts" / "run_flags.json").read_text(encoding="utf-8"))
    assert run_flags["debug_output_only"] is False, run_flags
    assert run_flags.get("draft_output_only") is not True, run_flags
    assert run_flags["pipeline_entrypoint"] == "scripts/pipeline.py render", run_flags
    assert not (run_dir / "DRAFT_NOT_CLIENT_READY.txt").exists()


def test_pipeline_draft_command_is_not_available(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "pipeline.py"), "draft", "--run-dir", str(run_dir)],
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "invalid choice" in result.stderr
