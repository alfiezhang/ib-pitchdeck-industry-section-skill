"""Contract tests: Group 15 - replacement dict generation and validation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1] / "runtime" / "ib-pitchdeck-agent-industry-section"
SCRIPT_DIR = SKILL_DIR / "scripts"
FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures"

sys.path.insert(0, str(SCRIPT_DIR))


def _run(args: list[str]) -> subprocess.CompletedProcess:
    env = {**__import__("os").environ, "PYTHONPATH": str(SCRIPT_DIR)}
    return subprocess.run(args, text=True, capture_output=True, cwd=str(SKILL_DIR), env=env)


class TestReplacementDict:
    def test_build_and_validate(self, compiled_artifacts, tmp_path):
        """Build replacement_dict from renderer_spec and validate against ppt_mapping."""
        from generate_replacement_dict import build_replacement_dict
        from renderer_token_source import build_token_source

        renderer = json.loads(compiled_artifacts["renderer_spec"].read_text(encoding="utf-8"))
        ppt_mapping = json.loads((SKILL_DIR / "configs" / "ppt_mapping.json").read_text(encoding="utf-8"))
        replacements = build_replacement_dict(
            build_token_source(renderer)["token_source"],
            ppt_mapping,
            keep_unmapped_empty=False,
            renderer_spec_path=compiled_artifacts["renderer_spec"],
            ppt_mapping_path=SKILL_DIR / "configs" / "ppt_mapping.json",
        )
        replacement_path = tmp_path / "replacement_dict.json"
        replacement_path.write_text(json.dumps(replacements, ensure_ascii=False, indent=2), encoding="utf-8")
        result = _run([
            sys.executable, "scripts/qc/validate_artifact.py",
            "--artifact", "replacement_dict",
            "--run-dir", str(compiled_artifacts["renderer_spec"].parent),
            "--path", str(replacement_path),
        ])
        assert result.returncode == 0, result.stdout + result.stderr
